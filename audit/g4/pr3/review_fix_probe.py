"""Current mock CLI/material/Persona/control evidence; never live news or legal proof."""

import inspect
import json
import subprocess
import sys
from pathlib import Path

from cfaw_news.intelligence import g2_adapter
from cfaw_news.intelligence.contracts import SourcePolicy
from cfaw_news.intelligence.runtime import Control, run
from cfaw_news.intelligence.runtime_control import current

from evals.intelligence_g2.contracts import data, json_bytes
from evals.intelligence_g4.tests.runtime_support import NOW, envelope, source, version, wire
from evals.intelligence_g4.tests.test_pr3_review_fixes import chain
from evals.intelligence_v1.hashing import sha256_bytes

ROOT = Path(__file__).resolve().parents[3]
AREA = ROOT / ".tmp/evals/g3/g4-pr3-review-fix-20261102-001/proof-final"


def save(name, value):
    raw = json_bytes(value)
    target = AREA / name
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as stream:
        stream.write(raw)
    return dict(path=target.relative_to(ROOT).as_posix(), sha256=sha256_bytes(raw))


def cli_case(name, value):
    folder = AREA / name
    folder.mkdir()
    raw, pin = wire(value)
    path, output = folder / "input.json", folder / "output"
    path.write_bytes(raw)
    argv = [sys.executable, "-B", "-m", "cfaw_news.intelligence.runtime", "--input", str(path),
            "--input-pin", pin, "--out", str(output)]
    process = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=60)
    (folder / "stdout.log").write_bytes(process.stdout)
    (folder / "stderr.log").write_bytes(process.stderr)
    assert process.returncode == 0, process.stderr
    result = json.loads((output / "result.json").read_bytes())
    assert not result["publishable"]
    return result, save(name + "/execution.json", dict(argv=argv, cwd=str(ROOT), exit_code=0,
        input_sha256=pin, output_sha256=sha256_bytes((output / "result.json").read_bytes()),
        state=result["state"], reasons=result["reason_codes"],
        files={p.relative_to(folder).as_posix(): sha256_bytes(p.read_bytes()) for p in folder.rglob("*") if p.is_file()}))


def in_target(target):
    frames = inspect.stack()
    names = {type(f.frame.f_locals.get("self")).__name__ for f in frames
             if f.function in {"bound", "replay"}}
    if target.endswith("_model"):
        return ("RuntimeResult" in names if target == "result_model" else
                "RuntimePlan" in names and "RuntimeResult" not in names)
    return (any(f.function == "validate_context" for f in frames)
            and not names & {"RuntimePlan", "RuntimeResult"}
            and any(f.function == "plan_fields" for f in frames) == (target == "budget"))


def fault(target, kind):
    state = dict(triggered=False, groups_before=0, groups_after=0, inherited_request_control=False)
    control = Control(cancelled=lambda: kind == "cancel" and state["triggered"], timeout_seconds=1,
                      clock=lambda: 2 if kind == "timeout" and state["triggered"] else 0)
    native, grouping = g2_adapter.run_native, g2_adapter.run_grouping_step
    def intercept(*args, **kwargs):
        if not state["triggered"] and in_target(target):
            state["inherited_request_control"] = current() is control
            state["triggered"] = True
        return native(*args, **kwargs)
    def count(*args, **kwargs):
        state["groups_after" if state["triggered"] else "groups_before"] += 1
        return grouping(*args, **kwargs)
    g2_adapter.run_native, g2_adapter.run_grouping_step = intercept, count
    raw, pin = wire(chain())
    try:
        try:
            run(raw, expected_sha256=pin, control=control)
        except ValueError as error:
            expected = "G4_RUNTIME_CANCELLED" if kind == "cancel" else "G4_RUNTIME_TIMEOUT"
            assert expected in str(error)
        else:
            raise AssertionError("cancelled/timed-out validation returned success")
    finally:
        g2_adapter.run_native, g2_adapter.run_grouping_step = native, grouping
    assert state["triggered"] and state["inherited_request_control"] and state["groups_after"] == 0
    return save(f"control/{kind}-{target}.json", dict(status="PASS", target=target, fault=kind,
        input_sha256=pin, input=data(json.loads(raw)), **state, completed_checks=control.log))


def main():
    AREA.mkdir(exist_ok=False)
    excerpt, excerpt_receipt = cli_case("excerpt", envelope("real"))
    assert excerpt["reason_codes"] == ["G4_NATIVE_G2_REJECTED:RIGHTS_USE_NOT_ALLOWED"]
    assert excerpt["input"]["versions"][0]["content_kind"] == "feed_summary" and not excerpt["stages"]
    permitted = envelope("real")
    policy = SourcePolicy.model_validate_json(json_bytes({**source("real", "permitted").model_dump(mode="json"),
        "allowed_use": ["metadata", "excerpt", "fulltext"]}))
    permitted.update(sources=[policy.model_dump(mode="json")], versions=[version(policy).model_dump(mode="json")])
    secondary, secondary_receipt = cli_case("permitted", permitted)
    evidence = secondary["stages"][-1]["evidence"]
    assert all(c["attribution"]["attribution_kind"] == "secondary_material" and c["claim_type"] == "other"
               and "primary_text_unavailable" in c["limitations"] for c in evidence["claims"])
    assert all(a["verification_state"] == "unverified" for a in evidence["assessments"])
    first, first_receipt = cli_case("persona-original", chain())
    updated = chain()
    updated["persona"]["persona"].update(persona_version_id="local:v2", available_at=NOW)
    early, early_receipt = cli_case("persona-early", updated)
    assert first["archive_snapshot_ids"] == early["archive_snapshot_ids"]
    assert len(first["stages"][-1]["evidence"]["next_state"]["claims"]) == len(
        early["stages"][-1]["evidence"]["next_state"]["claims"]) == 2
    updated["persona"]["persona"].update(available_at="2026-01-02T02:00:00Z")
    late, late_receipt = cli_case("persona-late", updated)
    assert late["reason_codes"] == ["G4_RUNTIME_PERSONA_HISTORY_REQUIRED"] and not late["stages"]
    receipts = [excerpt_receipt, secondary_receipt, first_receipt, early_receipt, late_receipt]
    for target in ("ranking", "budget", "plan_model", "result_model"):
        for kind in ("cancel", "timeout"):
            receipts.append(fault(target, kind))
    pin = save("proof.json", dict(status="PASS", receipts=receipts, fixture_origin="AI-authored engineering mock",
        live_news=False, real_rights_validation=False, user_database_writes=0, external_model_calls=0))
    print(json.dumps(dict(status="PASS", cases=len(receipts), **pin)))


if __name__ == "__main__":
    main()
