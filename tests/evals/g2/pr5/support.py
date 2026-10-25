import asyncio

from evals.intelligence_g2.contracts import PACKAGE, json_bytes
from evals.intelligence_g2.pr4.contracts import PR4Config
from evals.intelligence_g2.pr4.pipeline import generate_items
from evals.intelligence_g2.pr4.replay import run_replay as rule_replay
from evals.intelligence_g2.pr4.replay import run_sequence as rule_sequence
from evals.intelligence_g2.pr5.adapter import MockCompletionAdapter, MockTransport, TransportReply
from evals.intelligence_g2.pr5.assets import FIXTURE, load_config, strict_json
from evals.intelligence_g2.pr5.contracts import ExpressionInput, data, digest
from evals.intelligence_g2.pr5.project import project_request
from evals.intelligence_g2.pr5.replay import run_sequence
from evals.intelligence_v1.hashing import sha256_bytes

from ..pr2.support import make_input
from ..pr3.support import evidence_for
from ..pr4.support import export_evidence
from ..support import output_path

CONFIG = PACKAGE / "manifests/pr5_config.json"


def pin(path):
    return sha256_bytes(path.read_bytes())


def settings():
    return load_config(CONFIG, pin(CONFIG))


def cases():
    root = FIXTURE / "prediction"
    manifest = strict_json((root / "manifest.json").read_bytes())
    raw = (root / "scenarios.json").read_bytes()
    assert sha256_bytes(raw) == manifest["sha256"]
    result = strict_json(raw)["cases"]
    for name in ("adversarial", "injection"):
        extra = root / (name + "-manifest.json")
        if extra.exists():
            header = strict_json(extra.read_bytes())
            raw = (root / (name + ".json")).read_bytes()
            assert sha256_bytes(raw) == header["sha256"]
            result += strict_json(raw)["cases"]
    return result


def replay_values(case="FOCUS"):
    scenario = next(c for c in cases() if c["case_id"] == case)
    previous, values = None, []
    for step in scenario["steps"]:
        value = make_input(step["documents"], timeline=case, day=step["day"], previous=previous)
        kinds = {d["id"]: d.get("content_kind") for d in step["documents"]}
        docs = tuple(d.model_copy(update={"candidate": d.candidate.model_copy(update={
            "content_kind": kinds[d.candidate.document_id] or d.candidate.content_kind})}) for d in value.visible_documents)
        value = value.model_copy(update={"visible_documents": docs})
        values.append(value)
        previous = value
    return tuple(values)


def parent_values(case="FOCUS", strategy="r1"):
    parents, evidence = evidence_for(replay_values(case), strategy=strategy)
    return rule_sequence(parents, evidence, config=PR4Config())


def request_for(case="FOCUS", step=-1):
    config, assets = settings()
    values, rules = parent_values(case)
    value = ExpressionInput(generation_input=values[step], rule_result=rules[step],
        rule_config=PR4Config(), config_sha256=digest(config))
    item = next(i for i in rules[step].items if i.tier_candidate != "hold")
    view = next(v for v in values[step].events if v.bundle.event_key == item.event_key)
    return value, item, project_request(value, item, view, config, assets)


def secondary_values():
    """Synthetic G2 contract projection, not an end-to-end G1 real-source fixture."""
    from evals.intelligence_g2.pr3.pipeline import bundle_digest

    values, _ = parent_values("RADAR")
    value = values[0]
    view = value.events[0]
    claims = tuple(c.model_copy(update={"attribution": c.attribution.model_copy(update={
        "attribution_kind": "secondary_material", "asserted_by_source_id": None}),
        "proposition": c.proposition.model_copy(update={"quantities": (), "polarity": "unknown", "ambiguous": True}),
        "marker": "none", "claim_type": "other", "limitations": c.limitations + ("primary_text_unavailable",)})
        for c in view.claims)
    bundle = view.bundle.model_copy(update={"assessments": tuple(a.model_copy(update={
        "verification_state": "unverified"}) for a in view.bundle.assessments)})
    bundle = bundle.model_copy(update={"bundle_sha256": bundle_digest(bundle)})
    view = view.model_copy(update={"claims": claims, "bundle": bundle, "source_pointers": tuple(
        p.model_copy(update={"content_kind": "feed_summary"}) for p in view.source_pointers)})
    value = value.model_copy(update={"events": (view,)})
    return (value,), (generate_items(generation_input=value, config=PR4Config()),)


def envelope(draft, *, reason="stop", usage=None):
    content = json_bytes(data(draft)).decode() if not isinstance(draft, str) else draft
    return dict(choices=[dict(finish_reason=reason, message=dict(content=content))], usage=usage)


class ScriptedTransport:
    def __init__(self, script):
        self.script, self.calls = script, []

    async def exchange(self, raw, *, request_sha256):
        self.calls.append(raw)
        reply = self.script(raw)
        if hasattr(reply, "__await__"):
            reply = await reply
        return reply


def run(case="FOCUS", *, script=None, mode="mock", generator=None, control=None):
    config, assets = settings()
    transport = ScriptedTransport(script) if script else MockTransport(assets)
    generator = generator or MockCompletionAdapter(assets, transport)
    values, rules = parent_values(case)
    inputs, executions = asyncio.run(run_sequence(values, rules, rule_config=PR4Config(), config=config,
        assets=assets, mode=mode, generator=generator, control=control))
    return inputs, executions, transport


def export_rule(tmp_path, case="T34", strategy="r1"):
    evidence = export_evidence(tmp_path, case, strategy=strategy)
    out = output_path()
    config = PACKAGE / "manifests/pr4_config.json"
    rule_replay(evidence, evidence_manifest_sha256=pin(evidence / "run_manifest.json"),
        through_step="D8" if case == "T34" else "D0", config_path=config, config_sha256=pin(config), out=out)
    return out


def cli_args(parent, out, *, mode="mock", step="D8"):
    return ["--rule-run", str(parent), "--rule-manifest-sha256", pin(parent / "run_manifest.json"),
        "--through-step", step, "--mode", mode, "--config", str(CONFIG), "--config-sha256", pin(CONFIG),
        "--out", str(out)]


def immediate(coroutine):
    """Only immediate mock adapter coroutines; never runs a scheduler or skips a pending await."""
    try:
        try:
            coroutine.send(None)
        except StopIteration as done:
            return done.value
        raise AssertionError("unexpected async suspension in pure mock adapter")
    finally:
        coroutine.close()


def reply(raw):
    return TransportReply(json_bytes(raw))
