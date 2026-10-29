"""Real JSON boundaries must preserve the registered configuration and predictions."""

from evals.intelligence_g2.contracts import digest, json_bytes, read_json
from evals.intelligence_g3.artifacts import load_campaign
from evals.intelligence_g3.contracts import PACKAGE
from evals.intelligence_g3.experiments import predict
from evals.intelligence_g3.history_contracts import HistoryInput, parse_history
from evals.intelligence_g3.pr5_contracts import configuration
from evals.intelligence_g3.reproduce import jobs

PIN = "56f2244812449db5ddb5a8bd2384cb302a3f9d66fb1205be167e9308da530daf"


def test_registered_configuration_survives_the_actual_json_wire():
    value = load_campaign(PACKAGE / "manifests/pr5_campaign.json", PIN)
    config = configuration()
    assert config == read_json(json_bytes(config))
    assert digest(config) == value.config_sha256


def test_every_prediction_variant_survives_the_actual_json_wire():
    campaign = load_campaign(PACKAGE / "manifests/pr5_campaign.json", PIN)
    source = parse_history(HistoryInput, read_json(
        (PACKAGE / campaign.cases[0].input.path).read_bytes()))
    for job in jobs(campaign)[:11]:
        result = predict(source, job)
        assert result == read_json(json_bytes(result)), job.job_id
