import json

import pytest
from conftest import refresh

from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.hashing import canonical_json, sha256_bytes


def run(bundle, out, algorithm="b1", **kwargs):
    from evals.intelligence_v1.replay import run_replay

    manifest = bundle / "manifests/dataset_manifest.json"
    return run_replay(manifest, manifest_sha256=sha256_bytes(manifest.read_bytes()),
                      algorithm_id=algorithm, out=out, split="dev", **kwargs)


def test_four_algorithms_share_full_input_snapshot_and_prediction_scale(bundle, tmp_path):
    snapshots = []
    for algorithm in ("b0", "b1", "b2-predicted", "b2-oracle"):
        out = tmp_path / algorithm
        metadata = run(bundle, out, algorithm)
        snapshots.append((out/"input_snapshot.json").read_bytes())
        assert metadata["validation_scope"] == "prediction_inputs"
        assert not metadata["full_dataset_validated"]
        assert metadata["network_access"] is False and metadata["live_model_called"] is False
        assert metadata["predictions_sha256"] == sha256_bytes((out/"predictions.jsonl").read_bytes())
    assert all(s == snapshots[0] for s in snapshots)


def test_empty_candidates_are_valid_and_gap_is_not_no_news(bundle, tmp_path):
    path = bundle / "timelines/steps.jsonl"
    records = [json.loads(x) for x in path.read_bytes().splitlines()]
    # D0 before the first document, retaining the already available persona.
    records[0].update(as_of="2026-01-01T01:00:00Z", time_window_end="2026-01-01T01:00:00Z",
                      visible_doc_version_ids=[])
    path.write_bytes("".join(canonical_json(r) + "\n" for r in records).encode())
    refresh(bundle)
    out = tmp_path / "empty"
    run(bundle, out)
    rows = [json.loads(x) for x in (out/"predictions.jsonl").read_bytes().splitlines()]
    assert rows[0]["ranked_items"] == []
    assert rows[0]["candidate_doc_count"] == 0
    assert all(r["coverage_interpretation"] == "observed_sources_only; gaps_are_unknown"
               for r in rows)
    assert b"no_updates" not in (out/"predictions.jsonl").read_bytes()


def test_output_never_overwrites_or_survives_invalid_input(bundle, tmp_path):
    out = tmp_path / "existing"
    out.mkdir()
    (out/"mine").write_bytes(b"keep")
    with pytest.raises(ContractError, match="OUTPUT_EXISTS"):
        run(bundle, out)
    assert list(out.iterdir()) == [out/"mine"]
    path = bundle / "timelines/steps.jsonl"
    path.write_bytes(path.read_bytes() + b" ")
    bad = tmp_path / "bad"
    with pytest.raises(ContractError, match="SHA_MISMATCH"):
        run(bundle, bad)
    assert not bad.exists()
