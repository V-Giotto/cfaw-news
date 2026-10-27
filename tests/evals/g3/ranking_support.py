"""Synthetic native G2 outputs for PR2 tests; never imported by prediction code."""

from functools import lru_cache

from evals.intelligence_g2.contracts import data, digest
from evals.intelligence_g2.pr4.contracts import PR4Config
from evals.intelligence_g2.pr4.replay import run_sequence
from evals.intelligence_g2.pr5.pipeline import rule_presentation
from evals.intelligence_g2.pr6.contracts import G3InputView
from evals.intelligence_g3.contracts import G3Candidate, G3ReplayInput, parse
from tests.evals.g2.pr2.support import sequence
from tests.evals.g2.pr3.support import evidence_for

from .support import Scenario

SPECS = [{"id": "a"}, {"id": "b", "title": "Boreal SDK v2.0 release",
         "body": "Boreal SDK provides evaluation for local agents."},
         {"id": "c", "title": "Hold Kit v3.0 release", "body": ""}]


def native_replay(steps):
    base = Scenario().load()
    values = sequence(steps)
    inputs, evidence = evidence_for(values)
    _, rules = run_sequence(inputs, evidence, config=PR4Config())
    observations, refs, documents = [], [], {}
    for value, inp, ev, rule in zip(values, inputs, evidence, rules, strict=True):
        candidates = []
        for item in rule.items:
            event = next(e for e in inp.grouping_result.events if e.event_key == item.event_key)
            bundle = next(b for b in ev.bundles if b.event_key == item.event_key)
            snap = next(s for s in rule.snapshots if s.event_key == item.event_key)
            presentation = rule_presentation(item)
            trace = base.candidates[0].trace
            pointer = "synthetic:ranking-test-trace"
            view = G3InputView(event_key=item.event_key, event_revision=item.event_revision,
                as_of=snap.as_of.isoformat(), bundle=data(bundle), rule_item=data(item),
                presentation=data(presentation), snapshot=data(snap),
                source_coverage=tuple(data(c) for c in item.source_coverage),
                lineage_ids=snap.lineage_ids, trace_pointer=pointer)
            candidate = G3Candidate(event=event, bundle=bundle, rule_item=item,
                presentation=presentation, snapshot=snap, trace=trace, trace_pointer=pointer,
                g2_view_sha256=digest(view))
            candidates.append(data(candidate))
            refs.append(dict(event_key=event.event_key, event_revision=event.event_revision,
                item_id=item.item_id, snapshot_id=snap.snapshot_id, as_of=data(snap)["as_of"]))
        observations.append(dict(schema_revision="g3-pr1-1",
            identity_state=data(inp.grouping_result.next_state), evidence=data(ev),
            candidates=candidates, source_coverage=[], source_coverage_digest=digest([])))
        for doc in value.visible_documents:
            documents.update({v.doc_version_id: data(v) for v in doc.visible_lineage})
    raw = data(base)
    raw.update(timeline_id=values[-1].context.timeline_id, step_id=values[-1].context.step_id,
        as_of=data(values[-1].context)["as_of"], time_window_start=data(values[-1].context)["time_window_start"],
        time_window_end=data(values[-1].context)["time_window_end"], source_coverage=[],
        identity_state=observations[-1]["identity_state"], evidence=observations[-1]["evidence"],
        candidates=observations[-1]["candidates"], observations=observations,
        published_refs=refs, item_snapshots=data(rules[-1].next_state)["snapshots"],
        document_archive=[documents[k] for k in sorted(documents)], history=[], deliveries=[])
    raw["parent"]["g2_input_manifest_sha256"] = values[-1].input_manifest_sha256
    return parse(G3ReplayInput, raw)


@lru_cache
def pool():
    return native_replay([(0, SPECS), (7, SPECS)])


def delivered(value, kinds=("included",), *, observation=0):
    raw = data(value)
    selected = next(c for c in raw["observations"][observation]["candidates"]
                    if c["rule_item"]["tier_candidate"] != "hold")
    target = next(r for r in raw["published_refs"] if r["snapshot_id"] ==
                  selected["snapshot"]["snapshot_id"])
    stamp = target["as_of"]
    provenance = dict(record_origin="synthetic", provenance_uri="synthetic:pr2-test")
    raw["deliveries"] = [dict(schema_revision="g3-pr1-1", persona_id=value.persona.persona.persona_id,
        delivery=dict(delivery_id="test:delivery", as_of=stamp, generated_at=stamp),
        available_at=stamp, items=[target], **provenance)]
    raw["history"] = [dict(schema_revision="g3-pr1-1", interaction_id=f"test:{i}",
        persona_id=value.persona.persona.persona_id, delivery_id="test:delivery", target=target,
        kind=kind, occurred_at=stamp, available_at=stamp, source="synthetic:test", **provenance)
        for i, kind in enumerate(kinds)]
    return parse(G3ReplayInput, raw)
