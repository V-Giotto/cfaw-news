import json

import pytest
from pr4_support import RV, counterfactual, rows
from test_loader import step
from test_replay_end_to_end import run

from evals.intelligence_v1.hashing import canonical_json, sha256_bytes
from evals.intelligence_v1.validate import validate_dataset


@pytest.mark.parametrize("scenario", ["remove_correction", "academic_persona", "future_independent",
    "rendered", "opened", "acknowledged", "source_failure", "future_feedback"])
def test_five_counterfactual_families_with_frozen_independent_bundles(bundle, tmp_path, scenario):
    from evals.intelligence_v1.evaluate import evaluate_run

    source_documents = (bundle/RV/"documents.jsonl").read_bytes()
    base = tmp_path/"base"
    run(bundle, base, "b4", timeline_id="REVISIT-7D")
    baseline = [json.loads(line) for line in (base/"predictions.jsonl").read_bytes().splitlines()]
    gold_paths = [bundle/entry["path"] for entry in json.loads(
        (bundle/"manifests/dataset_manifest.json").read_bytes())["file_hashes"]
        if entry["role"] in {"gold", "annotations", "adjudications"}]
    gold_hashes = {str(p): sha256_bytes(p.read_bytes()) for p in gold_paths}
    manifest = counterfactual(bundle, scenario)
    assert validate_dataset(manifest).ok
    assert {str(p): sha256_bytes(p.read_bytes()) for p in gold_paths} == gold_hashes
    assert rows(bundle, "families.jsonl") == [{"family_id": "family:revisit7d", "split": "dev"}]
    out = tmp_path/"variant"
    run(bundle, out, "b4", timeline_id="REVISIT-7D")
    predictions = [json.loads(line) for line in (out/"predictions.jsonl").read_bytes().splitlines()]
    report = evaluate_run(out, manifest, manifest_sha256=sha256_bytes(manifest.read_bytes()),
        label_source="synthetic-fixture", out=tmp_path/"evaluation")
    d8 = report["steps"][-1]
    context, candidates = step(bundle, "D8", "REVISIT-7D")
    if scenario == "remove_correction":
        assert "rv:x:2" not in context.candidate_doc_version_ids
        assert all(label["material_change"] != "correction" for label in rows(bundle,"expectations.jsonl"))
        assert "rv:x:1" in context.candidate_doc_version_ids
    elif scenario == "academic_persona":
        assert (bundle/RV/"documents.jsonl").read_bytes() == source_documents
        assert [p["ranked_items"] for p in baseline] != [p["ranked_items"] for p in predictions]
        assert context.persona.persona_id == "rv:academic"
    elif scenario == "future_independent":
        assert "rv:test:1" not in context.candidate_doc_version_ids
        assert all("rv:test:1" not in r["doc_version_ids"] for r in predictions[-1]["ranked_items"])
    elif scenario in {"rendered", "opened", "acknowledged"}:
        penalty = {"rendered": .2, "opened": .1, "acknowledged": .35}[scenario]
        assert predictions[1]["ranked_items"][0]["score_components"]["penalty"] == penalty
        assert context.persona.knowledge_known == ()
        assert all(r["score_components"]["penalty"] == 0 for r in predictions[-1]["ranked_items"])
    elif scenario == "source_failure":
        assert d8["coverage"]["coverage_gap_count"] == 1
        assert d8["coverage"]["unknown_source_seconds"] == 4*86400
        assert predictions[-1]["ranked_items"] == baseline[-1]["ranked_items"]
    elif scenario == "future_feedback":
        assert (out/"predictions.jsonl").read_bytes() == (base/"predictions.jsonl").read_bytes()
        assert all(e.kind != "acknowledged" for e in context.exposure_history)
    assert len(candidates) == len(context.candidate_doc_version_ids)
    (tmp_path/"scenario-evidence.json").write_text(canonical_json({"scenario":scenario,
        "manifest_sha256":sha256_bytes(manifest.read_bytes()), "gold_unchanged":True,
        "predictions_sha256":sha256_bytes((out/"predictions.jsonl").read_bytes())})+"\n",encoding="utf-8")
