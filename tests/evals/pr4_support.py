"""Explicit counterfactual recipes; mutations only affect independent temporary bundles."""

import json

from conftest import refresh

from evals.intelligence_v1.contracts import DocumentVersion
from evals.intelligence_v1.hashing import canonical_json
from evals.intelligence_v1.temporal import parse_instant, visible_versions

RV = "fixtures/valid/revisit_7d/"


def rows(root, name):
    return [json.loads(line) for line in (root/RV/name).read_bytes().splitlines()]


def put(root, name, values):
    (root/RV/name).write_bytes("".join(canonical_json(v)+"\n" for v in values).encode())


def freeze_copy(root, name):
    path = refresh(root, frozen=True)
    manifest = json.loads(path.read_bytes())
    manifest["dataset_revision"] = "pr4-counterfactual-"+name
    path.write_bytes((canonical_json(manifest)+"\n").encode())
    return path


def counterfactual(root, name):
    # These recipes are fixed test inputs, never chosen based on algorithm scores.
    documents, expected = rows(root, "documents.jsonl"), rows(root, "expectations.jsonl")
    steps = rows(root, "steps.jsonl")
    if name == "remove_correction":
        documents = [d for d in documents if d["doc_version_id"] != "rv:x:2"]
        events = rows(root, "events.jsonl")
        for event in events:
            event["document_version_ids"] = [v for v in event["document_version_ids"] if v != "rv:x:2"]
        put(root, "events.jsonl", events)
        for label in expected:
            label["supporting_doc_version_ids"] = ["rv:x:1" if v == "rv:x:2" else v
                                                   for v in label["supporting_doc_version_ids"]]
            if label["material_change"] == "correction":
                label["material_change"] = "meaningful_update"
    elif name == "academic_persona":
        personas = rows(root, "personas.jsonl")
        personas[0].update(persona_id="rv:academic", persona_version_id="rv:academic:1",
            domain_interests=["research reliability"], current_goals=["assess evaluation methods"],
            hard_constraints=[])
        put(root, "personas.jsonl", personas)
        for record in [*steps, *expected]:
            record["persona_version_id"] = "rv:academic:1"
    elif name == "future_independent":
        for document in documents:
            if document["doc_version_id"] == "rv:test:1":
                document["available_at"] = "2026-02-10T12:00:00Z"
        for label in expected:
            label["supporting_doc_version_ids"] = [v for v in label["supporting_doc_version_ids"]
                                                   if v != "rv:test:1"]
            if not label["supporting_doc_version_ids"]:
                label.update(supporting_doc_version_ids=["rv:x:1"], material_change="no_change")
    elif name in {"rendered", "opened", "acknowledged"}:
        exposures = rows(root, "exposures.jsonl")
        exposures[0]["kind"] = name
        put(root, "exposures.jsonl", exposures)
    elif name == "future_feedback":
        exposures = rows(root, "exposures.jsonl")
        exposures.append({**exposures[0], "exposure_id": "rv:future:ack", "kind": "acknowledged",
                          "occurred_at": "2026-02-10T12:00:00Z"})
        put(root, "exposures.jsonl", exposures)
    elif name == "source_failure":
        windows = rows(root, "coverage_windows.jsonl")
        windows.append({"coverage_window_id": "rv:failed", "source_id": "revisit-official",
            "start_at": "2026-02-05T12:00:00Z", "end_at": "2026-02-09T12:00:00Z",
            "observed_at": "2026-02-09T12:00:00Z", "status": "failed",
            "reason": "Synthetic HTTP 503; coverage is unknown, not no updates."})
        put(root, "coverage_windows.jsonl", windows)
        steps[-1]["coverage_window_ids"].append("rv:failed")
    else:
        raise AssertionError("Unknown preregistered counterfactual")
    parsed = [DocumentVersion.model_validate_json(canonical_json(d)) for d in documents]
    for step in steps:
        step["visible_doc_version_ids"] = [d.doc_version_id for d in visible_versions(
            parsed, as_of=parse_instant(step["as_of"]))]
    put(root, "documents.jsonl", documents)
    put(root, "expectations.jsonl", expected)
    put(root, "steps.jsonl", steps)
    return freeze_copy(root, name)
