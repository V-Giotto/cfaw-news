"""Controlled synthetic input factory; reference files are only read by tests/evaluator."""

import json

from evals.intelligence_g2.contracts import PACKAGE, digest
from evals.intelligence_g2.pr2.contracts import PR2Config
from evals.intelligence_g2.pr2.replay import run_sequence as group_sequence
from evals.intelligence_g2.pr3.contracts import EvidenceInput, PR3Config
from evals.intelligence_g2.pr3.pipeline import run_evidence_step
from evals.intelligence_v1.hashing import sha256_bytes

from ..pr2.support import make_input

FIXTURE = PACKAGE / "fixtures/pr3/v1"
CONFIG = PACKAGE / "manifests/pr3_config.json"


def scenarios():
    raw = (FIXTURE / "prediction/scenarios.json").read_bytes()
    header = json.loads((FIXTURE / "prediction/manifest.json").read_bytes())
    assert sha256_bytes(raw) == header["files"][0]["sha256"]
    return json.loads(raw)["cases"]


def replay_values(case_id):
    case = next(c for c in scenarios() if c["case_id"] == case_id)
    previous, values = None, []
    for step in case["steps"]:
        previous = make_input(step["documents"], timeline=case_id, day=step["day"], previous=previous)
        values.append(previous)
    return values


def inputs_for(values, strategy="r1"):
    grouping_inputs, grouping_results = group_sequence(values, strategy=strategy, config=PR2Config())
    return grouping_inputs, grouping_results


def evidence_for(values, strategy="r1"):
    group_inputs, group_results = inputs_for(values, strategy)
    prior, inputs, outputs = None, [], []
    for grouping, result in zip(group_inputs, group_results, strict=True):
        value = EvidenceInput(grouping_input=grouping, grouping_result=result, grouping_config=PR2Config(),
            config_sha256=digest(PR3Config()), previous_state=prior,
            previous_state_sha256=digest(prior) if prior else None)
        result = run_evidence_step(evidence_input=value, config=PR3Config())
        inputs.append(value)
        outputs.append(result)
        prior = result.next_state
    return inputs, outputs


def run(case_id, strategy="r1"):
    return evidence_for(replay_values(case_id), strategy)


def pin(path):
    return sha256_bytes(path.read_bytes())


def export_parent(tmp_path, case="T24", strategy="r1"):
    from evals.intelligence_g2.contracts import data, json_bytes
    from evals.intelligence_g2.pr2.replay import run_replay

    from ..support import output_path

    values = replay_values(case)
    raw = b"".join(json_bytes(data(v)) for v in values)
    target = tmp_path / (case + "-inputs.jsonl")
    target.write_bytes(raw)
    header = {"format": "g2-pr2-prediction-v1", "record_origin": "synthetic", "files": [
        {"path": target.name, "role": "prediction", "sha256": sha256_bytes(raw)}]}
    manifest = tmp_path / (case + "-manifest.json")
    manifest.write_bytes(json_bytes(header))
    config = PACKAGE / "manifests/pr2_config.json"
    output = output_path()
    run_replay(manifest, manifest_sha256=pin(manifest), timeline_id=case,
        through_step=values[-1].context.step_id, strategy=strategy, config_path=config,
        config_sha256=pin(config), out=output)
    return output
