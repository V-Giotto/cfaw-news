"""Independent locator, provenance and safety checks plus deterministic replay checks."""

from evals.intelligence_g2.pr2.validate_output import get, instant
from evals.intelligence_g2.pr3.pipeline import bundle_digest
from evals.intelligence_g2.pr3.scope import compare_scope, lifecycle_fields
from evals.intelligence_g2.pr3.scope import value as grounded_value
from evals.intelligence_g2.pr3.validate_output import check_claim_fields, check_ref_bytes, unique

from .contracts import GenerationInput, GenerationResult, PR4Config, digest, fail, parse
from .policy import RISK_TEXT, radar_sentences, visible_text
from .sensitive import sensitive_content
from .snapshots import identify
from .templates import INFERENCE, reconstruct
from .templates import fact as expected_fact


def preflight(value):
    cutoff = get(get(value, "cursor"), "as_of")
    if cutoff is None:
        return
    cutoff = instant(cutoff)
    for window in get(value, "source_coverage", ()):
        for name in ("observed_at", "end_at"):
            time = get(window, name)
            if time is not None and instant(time) > cutoff:
                fail("FUTURE_COVERAGE", "temporal", "source_coverage." + name)
    for view in get(value, "events", ()):
        for ref in get(view, "citations", ()):
            time = get(ref, "available_at")
            if time is not None and instant(time) > cutoff:
                fail("FUTURE_VERSION", "temporal", "available_at", get(ref, "doc_version_id", ""))
        for pointer in get(view, "source_pointers", ()):
            time = get(pointer, "available_at")
            if time is not None and instant(time) > cutoff:
                fail("FUTURE_VERSION", "temporal", "available_at", get(pointer, "doc_version_id", ""))
        for claim in get(view, "claims", ()):
            time = get(claim, "first_extracted_as_of")
            if time is not None and instant(time) > cutoff:
                fail("G2_PR4_HISTORY_FUTURE", "history", "first_extracted_as_of", get(claim, "claim_key", ""))
    prior = get(value, "previous_state")
    if prior is not None:
        time = get(get(prior, "cursor"), "as_of")
        if time is not None and instant(time) >= cutoff:
            fail("G2_PR4_HISTORY_FUTURE", "history", "previous_state.cursor")
        for row in get(prior, "snapshots", ()):
            if get(row, "as_of") and time and instant(get(row, "as_of")) > instant(time):
                fail("G2_PR4_HISTORY_FUTURE", "history", "snapshot.as_of")
        for pointer in get(prior, "source_metadata", ()):
            if get(pointer, "available_at") and instant(get(pointer, "available_at")) > cutoff:
                fail("G2_PR4_HISTORY_FUTURE", "history", "source_metadata.available_at")


def check_lifecycle(view):
    claims = {c.claim_key: c for c in view.claims}
    refs = {r.ref_id: r for r in view.citations}
    for t in view.transitions:
        if not t.from_claim_keys or len(t.to_claim_keys) != 1:
            fail("G2_PR4_LIFECYCLE_INVALID", "lifecycle", "transition", t.transition_id)
        if not set(t.from_claim_keys + t.to_claim_keys) <= set(claims):
            fail("G2_PR4_LIFECYCLE_INVALID", "lifecycle", "claim_keys", t.transition_id)
        new = claims[t.to_claim_keys[0]]
        ref = refs[new.evidence_ref_ids[0]]
        marker, metric, quantities = lifecycle_fields(ref)
        if (marker != ("correction" if t.kind == "corrects" else "withdrawal")
                or not quantities or metric is None or t.trigger_ref_ids != new.evidence_ref_ids):
            fail("G2_PR4_LIFECYCLE_INVALID", "lifecycle", "target", t.transition_id)
        for key in t.from_claim_keys:
            old = claims[key]
            origin = refs[old.evidence_ref_ids[0]]
            q = old.proposition.quantities
            if (origin.document_id != ref.document_id or origin.source_id != ref.source_id
                    or grounded_value(old.proposition.metric) != grounded_value(metric)
                    or len(q) != 1 or q[0].unit != quantities[0].unit
                    or q[0].quantifier != quantities[0].quantifier
                    or grounded_value(q[0].value) != grounded_value(quantities[0].value)
                    or compare_scope(old.scope, new.scope) != "same_declared_scope"):
                fail("G2_PR4_LIFECYCLE_INVALID", "lifecycle", "target", t.transition_id)


def checked_input(generation_input, config):
    preflight(generation_input)
    value = parse(GenerationInput, generation_input)
    config = parse(PR4Config, config)
    if value.config_sha256 != digest(config):
        fail("CONFIG_NOT_PINNED", "input", "config_sha256")
    unique([v.bundle for v in value.events], "event_key", "input")
    prior = value.previous_state
    if prior is None:
        if value.cursor.ordinal != 0 or value.previous_state_sha256 is not None:
            fail("G2_PR4_SNAPSHOT_CHAIN_INVALID", "history", "previous_state")
    else:
        if (value.previous_state_sha256 != digest(prior) or prior.namespace != value.namespace
                or prior.config_sha256 != digest(config) or value.cursor.ordinal != prior.cursor.ordinal + 1
                or value.cursor.previous_step_id != prior.cursor.step_id):
            fail("G2_PR4_SNAPSHOT_CHAIN_INVALID", "history", "previous_state")
        seen = set()
        for row in prior.snapshots:
            if row.snapshot_id in seen or not set(row.previous_snapshot_ids) <= seen:
                fail("G2_PR4_SNAPSHOT_CHAIN_INVALID", "history", "snapshot.previous_snapshot_ids", row.snapshot_id)
            sha = digest(dict(item_id=row.item_id, as_of=row.as_of.isoformat(), bundle_sha256=row.bundle_sha256))
            if row.snapshot_id != "g2:snapshot:" + sha:
                fail("G2_PR4_SNAPSHOT_CHAIN_INVALID", "history", "snapshot_id", row.snapshot_id)
            seen.add(row.snapshot_id)
        unique(prior.source_metadata, "doc_version_id", "history")
    for window in value.source_coverage:
        # G1 validated the full window; enforce its temporal fields again on the projection.
        for name in ("observed_at", "end_at"):
            time = getattr(window, name, None)
            if time is not None and time > value.cursor.as_of:
                fail("FUTURE_COVERAGE", "temporal", "source_coverage." + name)
    for view in value.events:
        bundle = view.bundle
        if bundle.as_of != value.cursor.as_of or bundle.bundle_sha256 != bundle_digest(bundle):
            fail("G2_PR4_PARENT_RUN_MISMATCH", "input", "bundle", bundle.bundle_id)
        claims = unique(view.claims, "claim_key", "input")
        refs = unique(view.citations, "ref_id", "input")
        pointers = unique(view.source_pointers, "doc_version_id", "input")
        keys = bundle.current_claim_keys + bundle.historical_claim_keys
        if len(keys) != len(set(keys)) or set(keys) != set(claims):
            fail("G2_PR4_PARENT_RUN_MISMATCH", "input", "claim_keys", bundle.event_key)
        assessments = unique(bundle.assessments, "claim_key", "input")
        if set(assessments) != set(claims):
            fail("G2_PR4_PARENT_RUN_MISMATCH", "input", "assessments", bundle.event_key)
        for p in pointers.values():
            if (p.source_id != p.policy.source_id or p.record_origin != p.policy.record_origin
                    or p.redistribution_rights != p.policy.redistribution_rights):
                fail("ORIGIN_MISMATCH", "input", "source_policy", p.doc_version_id)
        for ref in refs.values():
            check_ref_bytes(ref)
            p = pointers.get(ref.doc_version_id)
            if (p is None or p.source_id != ref.source_id or p.document_id != ref.document_id
                    or p.content_sha256 != ref.content_sha256 or p.available_at != ref.available_at
                    or p.record_origin != ref.record_origin):
                fail("G2_PR4_FACT_PROVENANCE_INVALID", "facts", "citation.source", ref.ref_id)
        for c in claims.values():
            check_claim_fields(c, refs)
            if (c.claim_key in bundle.current_claim_keys and c.doc_version_id not in bundle.current_doc_version_ids
                    or assessments[c.claim_key].event_key != bundle.event_key
                    or assessments[c.claim_key].verification_state == "independently_supported"):
                fail("G2_PR4_PARENT_RUN_MISMATCH", "input", "claim_membership_status", c.claim_key)
        check_lifecycle(view)
    return value, config


def check_fact(fact, view):
    claims = {c.claim_key: c for c in view.claims}
    refs = {r.ref_id: r for r in view.citations}
    if "推断" in fact.text and not any("推断" in r.quote for r in refs.values()):
        fail("G2_PR4_INFERENCE_IN_FACT", "facts", "text")
    if (len(fact.claim_keys) != len(set(fact.claim_keys)) or not set(fact.claim_keys) <= set(claims)
            or {b.claim_key for b in fact.bindings} != set(fact.claim_keys)):
        fail("G2_PR4_FACT_PROVENANCE_INVALID", "facts", "claim_keys")
    for b in fact.bindings:
        c, ref = claims.get(b.claim_key), refs.get(b.ref_id)
        if c is None or ref is None or b.ref_id not in c.evidence_ref_ids:
            fail("G2_PR4_FACT_PROVENANCE_INVALID", "facts", "binding.ref_id", b.claim_key)
        expected = c.statement if b.field == "statement" else c.attribution.publisher_source_id
        span = (0, len(ref.quote)) if b.field == "statement" else (0, 0)
        if b.value != expected or (b.start, b.end) != span:
            fail("G2_PR4_FACT_PROVENANCE_INVALID", "facts", "binding.value", b.claim_key)
    expected = expected_fact(fact.template_id, tuple(claims[k] for k in fact.claim_keys), refs)
    if fact.bindings != expected.bindings:
        fail("G2_PR4_FACT_PROVENANCE_INVALID", "facts", "binding.slot", fact.claim_keys[0] if fact.claim_keys else "")
    if fact.text != reconstruct(fact):
        fail("G2_PR4_FACT_PROVENANCE_INVALID", "facts", "text", fact.claim_keys[0] if fact.claim_keys else "")


def validate_output(result, generation_input, config):
    value, config = checked_input(generation_input, config)
    if sensitive_content(result):
        fail("G2_PR4_FACT_PROVENANCE_INVALID", "output", "sensitive_text")
    result = parse(GenerationResult, result, stage="output")
    by_event = {}
    for item in result.items:
        if item.event_key in by_event:
            fail("G2_PR4_DUPLICATE_EVENT", "output", "event_key", item.event_key)
        by_event[item.event_key] = item
    if set(by_event) != {v.bundle.event_key for v in value.events}:
        fail("G2_PR4_DUPLICATE_EVENT", "output", "event_partition")
    for view in value.events:
        item = by_event[view.bundle.event_key]
        for fact in (item.headline, item.what_happened) + tuple(c.statement for c in item.claim_summaries):
            if fact:
                check_fact(fact, view)
        if item.why_it_matters and item.why_it_matters.text != INFERENCE:
            fail("G2_PR4_INFERENCE_IN_FACT", "inference", "text", item.item_id)
        if item.tier_candidate == "hold" and any((item.headline, item.what_happened, item.why_it_matters,
                item.claim_summaries, item.evidence_ref_ids)):
            fail("G2_PR4_TIER_INVALID", "output", "hold.facts", item.event_key)
        if item.tier_candidate != "hold":
            if "source_unverified" not in {r.code for r in item.risks}:
                fail("G2_PR4_SCOPE_RISK_MISSING", "output", "risks", item.event_key)
            for r in item.risks:
                text = RISK_TEXT.get(r.code)
                if text is None or r.text != (text.rstrip("。") if item.tier_candidate == "radar" else text):
                    fail("G2_PR4_SCOPE_RISK_MISSING", "output", "risks.text", item.event_key)
        if len(visible_text(item)) > getattr(config.budgets[config.budget_profile], item.tier_candidate):
            fail("G2_PR4_BUDGET_EXCEEDED", "output", "visible_chars", item.event_key)
        if item.tier_candidate == "radar" and radar_sentences(item) > 2:
            fail("G2_PR4_BUDGET_EXCEEDED", "output", "radar.sentences", item.event_key)
        if identify(item) != item:
            fail("G2_PR4_FACT_PROVENANCE_INVALID", "output", "content_revision", item.item_id)
    from .pipeline import assemble
    expected = assemble(value, config)
    if result.items != expected.items:
        fail("G2_PR4_SCOPE_RISK_MISSING", "output", "items")
    if result.snapshots != expected.snapshots or result.next_state != expected.next_state:
        fail("G2_PR4_SNAPSHOT_CHAIN_INVALID", "history", "snapshots")
    if result.citations != expected.citations:
        fail("G2_PR4_FACT_PROVENANCE_INVALID", "output", "citations")
    if result.cursor != expected.cursor or result.validation != expected.validation:
        fail("G2_PR4_PARENT_RUN_MISMATCH", "output", "validation")
    return result.validation
