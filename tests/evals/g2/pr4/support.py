"""Prediction inputs only. Expected tiers are loaded exclusively by tests/evaluator."""

from evals.intelligence_g2.contracts import PACKAGE, json_bytes, read_json
from evals.intelligence_g2.pr2.replay import run_replay as grouping_replay
from evals.intelligence_g2.pr3.replay import run_replay as evidence_replay
from evals.intelligence_g2.pr4.contracts import PR4Config
from evals.intelligence_g2.pr4.replay import run_sequence
from evals.intelligence_v1.hashing import sha256_bytes

from ..pr2.support import make_input
from ..pr3.support import evidence_for
from ..support import output_path

FIXTURE = PACKAGE / "fixtures/pr4/v2"
CONFIG = PACKAGE / "manifests/pr4_config.json"


def pin(path):
    return sha256_bytes(path.read_bytes())


def cases():
    raw = (FIXTURE / "prediction/scenarios.json").read_bytes()
    manifest = read_json((FIXTURE / "prediction/manifest.json").read_bytes())
    assert sha256_bytes(raw) == manifest["files"][0]["sha256"]
    return read_json(raw)["cases"]


def replay_values(case_id):
    case = next(c for c in cases() if c["case_id"] == case_id)
    prior, values = None, []
    for step in case["steps"]:
        value = make_input(step["documents"], timeline=case_id, day=step["day"], previous=prior)
        kinds = {s["id"]: s.get("content_kind") for s in step["documents"]}
        docs = tuple(d.model_copy(update={"candidate": d.candidate.model_copy(update={
            "content_kind": kinds[d.candidate.document_id] or d.candidate.content_kind})}) for d in value.visible_documents)
        value = value.model_copy(update={"visible_documents": docs})
        values.append(value)
        prior = value
    return tuple(values)


def run(case_id, *, config=None, strategy="r1"):
    parents, evidence = evidence_for(replay_values(case_id), strategy=strategy)
    return run_sequence(parents, evidence, config=config or PR4Config())


def export_evidence(tmp_path, case_id="T34", strategy="r1"):
    values = replay_values(case_id)
    raw = b"".join(json_bytes(v) for v in values)
    target = tmp_path / "prediction.jsonl"
    target.write_bytes(raw)
    manifest = tmp_path / "prediction-manifest.json"
    manifest.write_bytes(json_bytes({"format": "g2-pr2-prediction-v1", "record_origin": "synthetic", "files": [
        {"path": target.name, "role": "prediction", "sha256": sha256_bytes(raw)}]}))
    grouping = output_path()
    group_config = PACKAGE / "manifests/pr2_config.json"
    grouping_replay(manifest, manifest_sha256=pin(manifest), timeline_id=case_id,
        through_step=values[-1].context.step_id, strategy=strategy, config_path=group_config,
        config_sha256=pin(group_config), out=grouping)
    evidence = output_path()
    config = PACKAGE / "manifests/pr3_config.json"
    evidence_replay(grouping, grouping_manifest_sha256=pin(grouping / "run_manifest.json"),
        through_step=values[-1].context.step_id, config_path=config, config_sha256=pin(config), out=evidence)
    return evidence
