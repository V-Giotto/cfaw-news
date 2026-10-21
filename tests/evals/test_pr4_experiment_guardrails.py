import pytest
from test_prediction_split_isolation import holdout

from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.hashing import sha256_bytes
from evals.intelligence_v1.replay import run_replay


def test_sensitivity_must_not_run_on_holdout(bundle, tmp_path):
    manifest = holdout(bundle, split="test")
    output = tmp_path/"blocked-sensitivity"
    with pytest.raises(ContractError, match="SENSITIVITY_REQUIRES_DEV"):
        run_replay(manifest, manifest_sha256=sha256_bytes(manifest.read_bytes()), algorithm_id="b3",
                   split="test", half_life_days=3, out=output)
    assert not output.exists()


@pytest.mark.parametrize("options", [{"half_life_days": 7.0}, {"half_life_days": True},
                                   {"budget_seconds": 180.0}, {"budget_seconds": True}])
def test_experiment_api_rejects_non_integer_parameters(bundle, tmp_path, options):
    manifest = bundle/"manifests/dataset_manifest.json"
    output = tmp_path/"bad-parameters"
    with pytest.raises(ContractError, match="UNREGISTERED_EXPERIMENT"):
        run_replay(manifest, manifest_sha256=sha256_bytes(manifest.read_bytes()), algorithm_id="b3",
                   split="dev", out=output, **options)
    assert not output.exists()
