"""PR4 review regression: synthetic quoted credential fields never publish."""

import json

import pytest

from evals.intelligence_g2.contracts import json_bytes
from evals.intelligence_g2.pr2.replay import run_replay as group_replay
from evals.intelligence_g2.pr3.replay import run_replay as evidence_replay
from evals.intelligence_g2.pr4.contracts import PR4Config
from evals.intelligence_g2.pr4.replay import main, run_sequence
from evals.intelligence_g2.pr4.snapshots import identify
from evals.intelligence_g2.pr4.validate_output import validate_output
from evals.intelligence_v1.hashing import sha256_bytes

from ..pr2.support import make_input
from ..pr3.support import evidence_for
from ..support import output_path
from .support import CONFIG, pin
from .test_items import rejected

CANARY = "TEST_ONLY_FAKE_CREDENTIAL_1234567890"
PREFIX = "Atlas Tool v1.0 releases plugins. Configuration example: "


def quoted_config(key="api_key", *, single=False, value=CANARY):
    if single:
        return "{'" + key + "' : '" + value + "'}"
    return json.dumps({key: value})


def generated(configuration, *, monkeypatch=None):
    parents, evidence = evidence_for([make_input([{"id": "a", "body": PREFIX + configuration + "."}])])
    # The real parent pipeline admits this sample. PR4 must protect its own boundary;
    # no injected sensitive_text_excluded marker stands in for the detection test.
    assert len(evidence[0].claims) == 1
    assert not any(g.code == "sensitive_text_excluded" for g in evidence[0].validation.coverage_gaps)
    if monkeypatch:
        from evals.intelligence_g2.pr4.templates import RuleItemGenerator

        def unexpected_generation(self, request):
            pytest.fail("sensitive evidence reached presentation adapter")
        monkeypatch.setattr(RuleItemGenerator, "generate", unexpected_generation)
    return run_sequence(parents, evidence, config=PR4Config())


@pytest.mark.parametrize("key,single", [("api_key", False), ("api_key", True), ("API-KEY", False),
    ("password", False), ("access_token", False), ("secret", False)])
def test_quoted_credentials_hold_whole_item_before_template(key, single, monkeypatch):
    values, rows = generated(quoted_config(key, single=single), monkeypatch=monkeypatch)
    assert CANARY in values[0].events[0].claims[0].statement  # Authorized input only.
    row, item = rows[0], rows[0].items[0]
    assert item.tier_candidate == "hold"
    assert item.tier_reason_codes == ("sensitive_evidence",)
    assert item.headline is item.what_happened is item.why_it_matters is None
    assert item.claim_summaries == item.selected_claim_keys == item.evidence_ref_ids == row.citations == ()
    assert item.omitted_claim_keys
    assert CANARY not in row.model_dump_json()
    assert row.validation.ok


@pytest.mark.parametrize("configuration", [
    '{"retry_count": 3, "plugin_name": "PUBLIC_SETTING_VALUE"}',
    '{"api_key_enabled": true, "api_key_name": "PUBLIC_SETTING_VALUE"}',
    '{"api_key": "", "plugin_name": "PUBLIC_SETTING_VALUE"}',
])
def test_ordinary_configuration_still_generates_grounded_focus(configuration):
    values, rows = generated(configuration)
    item = rows[0].items[0]
    assert item.tier_candidate == "focus" and item.what_happened is not None
    assert "PUBLIC_SETTING_VALUE" in item.what_happened.text
    assert len(rows[0].citations) == 1 and configuration in rows[0].citations[0].quote
    assert validate_output(rows[0], values[0], PR4Config()).ok


@pytest.mark.parametrize("field", ["what_happened", "binding", "claim_summary", "citations", "uncertainties"])
def test_output_guard_rejects_injected_quoted_credentials(field):
    values, rows = generated('{"plugin_name": "PUBLIC_SETTING_VALUE"}')
    result, item = rows[0], rows[0].items[0]
    secret = quoted_config()
    if field == "citations":
        result = result.model_copy(update={"citations": (result.citations[0].model_copy(update={"quote": secret}),)})
    elif field == "uncertainties":
        item = identify(item.model_copy(update={"uncertainties": (secret,)}))
        result = result.model_copy(update={"items": (item,)})
    else:
        if field == "what_happened":
            fact = item.what_happened.model_copy(update={"text": secret})
            item = item.model_copy(update={"what_happened": fact})
        elif field == "binding":
            fact = item.what_happened
            bindings = tuple(b.model_copy(update={"value": secret}) if b.field == "statement" else b for b in fact.bindings)
            item = item.model_copy(update={"what_happened": fact.model_copy(update={"bindings": bindings})})
        else:
            summary = item.claim_summaries[0]
            summary = summary.model_copy(update={"statement": summary.statement.model_copy(update={"text": secret})})
            item = item.model_copy(update={"claim_summaries": (summary,)})
        result = result.model_copy(update={"items": (identify(item),)})
    rejected(lambda: validate_output(result, values[0], PR4Config()),
        "G2_PR4_FACT_PROVENANCE_INVALID", "output", "sensitive_text", "")


def test_cli_serialized_artifacts_do_not_repeat_input_credentials(tmp_path, capsys):
    from evals.intelligence_g2.contracts import PACKAGE

    value = make_input([{"id": "a", "body": PREFIX + quoted_config() + "."}], timeline="PR4-REVIEW-CREDENTIAL")
    raw = json_bytes(value)
    source = tmp_path / "prediction.jsonl"
    source.write_bytes(raw)
    manifest = tmp_path / "prediction-manifest.json"
    manifest.write_bytes(json_bytes({"format": "g2-pr2-prediction-v1", "record_origin": "synthetic", "files": [
        {"path": source.name, "role": "prediction", "sha256": sha256_bytes(raw)}]}))
    grouping, evidence, out = output_path(), output_path(), output_path()
    config = PACKAGE / "manifests/pr2_config.json"
    group_replay(manifest, manifest_sha256=pin(manifest), timeline_id=value.context.timeline_id, through_step="D0",
        strategy="r1", config_path=config, config_sha256=pin(config), out=grouping)
    config = PACKAGE / "manifests/pr3_config.json"
    evidence_replay(grouping, grouping_manifest_sha256=pin(grouping / "run_manifest.json"), through_step="D0",
        config_path=config, config_sha256=pin(config), out=evidence)
    assert CANARY.encode() in (evidence / "claims.jsonl").read_bytes()
    assert main(["--evidence-run", str(evidence), "--evidence-manifest-sha256", pin(evidence / "run_manifest.json"),
        "--through-step", "D0", "--config", str(CONFIG), "--config-sha256", pin(CONFIG), "--out", str(out)]) == 0
    assert json.loads(capsys.readouterr().out)["ok"]
    assert all(CANARY.encode() not in path.read_bytes() for path in out.iterdir())
    row = json.loads((out / "items.jsonl").read_bytes())
    assert row["items"][0]["tier_candidate"] == "hold"
    assert row["items"][0]["tier_reason_codes"] == ["sensitive_evidence"]
    assert json.loads((out / "citations.jsonl").read_bytes())["citations"] == []
