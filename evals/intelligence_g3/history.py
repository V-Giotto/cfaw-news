"""Strict as-of selection and explicit native G2 lineage bindings; no IO."""

from evals.intelligence_g2.contracts import data, digest

from .contracts import DeliverySnapshot, PersonaSnapshot, fail
from .history_contracts import HistoryInput, HistoryJournal, JournalEntry
from .history_contracts import parse_history as parse


def append_event(journal, event):
    """Return a new chain. Existing entries are retained byte-for-byte by the writer."""
    body = dict(sequence=len(journal.entries) + 1, previous_sha256=journal.head, event=data(event))
    entry = parse(JournalEntry, {**body, "sha256": digest(body)})
    return parse(HistoryJournal, dict(entries=[*data(journal)["entries"], data(entry)]))


def select_persona(personas, as_of):
    values = tuple(parse(PersonaSnapshot, data(p)) for p in personas)
    if len({p.persona.persona_id for p in values}) > 1:
        fail("G3_REFERENCE_MISMATCH", "persona_selection.persona_id")
    ids = [p.persona.persona_version_id for p in values]
    if len(ids) != len(set(ids)):
        fail("G3_DUPLICATE_ID", "persona_version_id")
    visible = [p for p in values if p.persona.available_at <= as_of]
    if not visible:
        fail("G3_FUTURE_PERSONA", "no_visible_persona")
    latest = max(p.persona.available_at for p in visible)
    selected = [p for p in visible if p.persona.available_at == latest]
    if len(selected) != 1:
        fail("G3_HISTORY_INVALID", "ambiguous_persona_version")
    return selected[0]


def select_deliveries(deliveries, as_of):
    values = tuple(parse(DeliverySnapshot, data(d)) for d in deliveries)
    ids = [d.delivery.delivery_id for d in values]
    if len(ids) != len(set(ids)):
        fail("G3_DUPLICATE_ID", "delivery_id")
    return tuple(d for d in values if max(d.available_at, d.delivery.generated_at,
                                          d.delivery.as_of) <= as_of)


def select_history(replay, journal, mappings=()):
    """Project a complete stored chain; explicit HistoryInput itself rejects future rows.

    available_at is append-monotone, so the visible chain is always an exact prefix.
    No unavailable event or mapping enters the selected input or its score fingerprint.
    """
    journal = parse(HistoryJournal, data(journal))
    visible = [e for e in journal.entries
               if e.event.available_at <= replay.as_of and e.event.occurred_at <= replay.as_of]
    return parse(HistoryInput, dict(replay=data(replay), journal=dict(entries=[data(e) for e in visible]),
        mappings=[data(m) for m in mappings if m.available_at <= replay.as_of]))


def candidate_archive(replay):
    return {c.snapshot.snapshot_id: (c, observation, f"/replay/observations/{oi}/candidates/{ci}",
                                   f"/replay/observations/{oi}/evidence")
            for oi, observation in enumerate(replay.observations)
            for ci, c in enumerate(observation.candidates)}


def disruptive(replay, old, current):
    """Trace the native graph, including ancestors absent from a split child's lineage.

    A surviving merge key still needs explicit migration. No title/member heuristics.
    """
    paths = {old.event.event_key: ()}
    for transition in replay.identity_state.transitions:
        if (transition.kind not in {"merge", "split", "complex"}
                or not old.snapshot.as_of < transition.effective_at <= current.snapshot.as_of):
            continue
        parents = set(paths).intersection(transition.from_keys)
        if not parents:
            continue
        path = min((paths[k] for k in parents), key=lambda p: (len(p), tuple(t.transition_id for t in p)))
        for key in parents:
            del paths[key]
        for key in transition.to_keys:
            paths[key] = (*path, transition)
    return paths.get(current.event.event_key, ())


def path_reaches(from_key, to_key, transitions):
    keys = {from_key}
    for transition in transitions:
        if not keys.intersection(transition.from_keys):
            return False
        keys.difference_update(transition.from_keys)
        keys.update(transition.to_keys)
    return to_key in keys


def validate_input(value):
    replay = value.replay
    if replay.history:
        fail("G3_HISTORY_INVALID", "legacy_history_must_be_explicitly_imported")
    refs = {r.snapshot_id: r for r in replay.published_refs}
    deliveries = {d.delivery.delivery_id: d for d in replay.deliveries}
    archive = candidate_archive(replay)
    transitions = {t.transition_id: t for t in replay.identity_state.transitions}
    for entry in value.journal.entries:
        h = entry.event
        if h.occurred_at > replay.as_of or h.available_at > replay.as_of:
            fail("G3_FUTURE_HISTORY", "journal")
        d = deliveries.get(h.delivery_id)
        if (d is None or refs.get(h.target.snapshot_id) != h.target or h.target not in d.items):
            fail("G3_REFERENCE_NOT_FOUND", "history.target_or_delivery")
        if (h.persona_id != replay.persona.persona.persona_id
                or h.occurred_at < d.delivery.generated_at or h.available_at < d.available_at):
            fail("G3_REFERENCE_MISMATCH", "history.persona_or_time")
    ids, pairs = set(), set()
    for mapping in value.mappings:
        pair = (mapping.from_target.snapshot_id, mapping.to_target.snapshot_id)
        if mapping.mapping_id in ids or pair in pairs:
            fail("G3_DUPLICATE_ID", "history_mapping")
        ids.add(mapping.mapping_id)
        pairs.add(pair)
        if mapping.available_at > replay.as_of:
            fail("G3_FUTURE_HISTORY", "mapping.available_at")
        if (refs.get(pair[0]) != mapping.from_target or refs.get(pair[1]) != mapping.to_target):
            fail("G3_REFERENCE_NOT_FOUND", "mapping.target")
        if not mapping.from_target.as_of < mapping.to_target.as_of <= mapping.available_at:
            fail("G3_INVALID_INTERVAL", "mapping")
        chain = [transitions.get(t) for t in mapping.transition_ids]
        old, current = archive[pair[0]][0], archive[pair[1]][0]
        needed = tuple(t.transition_id for t in disruptive(replay, old, current))
        if (None in chain or len(set(mapping.transition_ids)) != len(chain)
                or not needed or needed != mapping.transition_ids
                or chain[-1].transition_id not in current.event.lineage_ids
                or any(not old.snapshot.as_of < t.effective_at <= current.snapshot.as_of
                       for t in chain)
                or [t.effective_at for t in chain] != sorted(t.effective_at for t in chain)
                or not path_reaches(old.event.event_key, current.event.event_key, chain)):
            fail("G3_HISTORY_MAPPING_INVALID", "native_transition_path")


def active_events(journal):
    retracted = {e.event.retracts_id for e in journal.entries if e.event.kind == "retract"}
    return tuple((i, e.event) for i, e in enumerate(journal.entries)
                 if e.event.kind != "retract" and e.event.interaction_id not in retracted)


def resolve_target(value, old_ref, current):
    old = candidate_archive(value.replay)[old_ref.snapshot_id][0]
    transitions = disruptive(value.replay, old, current)
    if old.event.event_key == current.event.event_key and not transitions:
        return "exact_event_revision", ()
    mappings = [(i, m) for i, m in enumerate(value.mappings)
                if m.from_target == old_ref and m.to_target.snapshot_id == current.snapshot.snapshot_id]
    if mappings:
        i, mapping = mappings[0]
        refs = (f"/mappings/{i}",)
        return ("explicit_g2_lineage" if mapping.certainty == "confirmed" else "uncertain_mapping"), refs
    if transitions and path_reaches(old.event.event_key, current.event.event_key, transitions):
        return "missing_explicit_mapping", ()
    return "unmapped_target", ()
