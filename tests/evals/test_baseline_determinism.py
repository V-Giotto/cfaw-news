import json
import os
import subprocess
import sys

import pytest
from conftest import SOURCE
from test_loader import step

from evals.intelligence_v1.hashing import sha256_bytes


@pytest.mark.parametrize("algorithm", ["b0", "b1", "b2-predicted", "b3", "b4"])
def test_T18_ranker_is_invariant_to_input_order_and_fixed_id_ties(algorithm):
    from evals.intelligence_v1.baselines import get_ranker
    from evals.intelligence_v1.contracts import BaselineConfig

    context, candidates = step()
    ranker = get_ranker(algorithm, BaselineConfig())
    assert ranker.rank(context, candidates) == ranker.rank(context, candidates[::-1])


@pytest.mark.parametrize("algorithm", ["b0", "b1", "b2-predicted", "b2-oracle", "b3", "b4"])
def test_T24_cli_canonical_bytes_across_processes_and_hash_seeds(tmp_path, algorithm):
    manifest = SOURCE / "manifests/dataset_manifest.json"
    outputs = []
    for seed in ("1", "719"):
        out = tmp_path / (algorithm + "-" + seed)
        result = subprocess.run([sys.executable, "-B", "-m", "evals.intelligence_v1.replay",
            "--manifest", str(manifest), "--manifest-sha256", sha256_bytes(manifest.read_bytes()),
            "--algo", algorithm, "--split", "dev", "--out", str(out)],
            env={**os.environ, "PYTHONHASHSEED": seed}, capture_output=True, text=True, timeout=25)
        assert result.returncode == 0, result.stderr + result.stdout
        outputs.append(out)
    for name in ("predictions.jsonl", "input_snapshot.json", "baseline_config.json"):
        assert (outputs[0]/name).read_bytes() == (outputs[1]/name).read_bytes()
    rows = [json.loads(x) for x in (outputs[0]/"predictions.jsonl").read_bytes().splitlines()]
    assert len(rows) == 35  # 26 primary states and 9 preserved auxiliary states.
    assert all(r["algorithm_id"] == algorithm and r["oracle_mode"] == (algorithm == "b2-oracle")
               for r in rows)
    assert b"execution_ms" not in (outputs[0]/"predictions.jsonl").read_bytes()
    assert b"generated_at" not in (outputs[0]/"predictions.jsonl").read_bytes()
