"""Seal only the current path/receipt repair, preserving PR1/PR2 historical receipts."""

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from cfaw_news.intelligence.contracts import canonical, digest
from cfaw_news.intelligence.migrate import MIGRATION

ROOT = Path(__file__).resolve().parents[3]
AREA = ROOT / ".tmp/evals/g3/g4-pr2-review-fix-20261102-001"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def suite(path):
    cases = list(ET.parse(path).iter("testcase"))
    counts = {name: sum(c.find(name) is not None for c in cases)
              for name in ("failure", "error", "skipped")}
    return dict(nodes=len(cases), passed=len(cases) - sum(counts.values()), **counts)


def main():
    entry = read(AREA / "entry.json")
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                   text=True).strip() == entry["head"]
    assert subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT,
                                   text=True).strip() == entry["branch"]
    assert not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT)
    changed = [p for p, pin in entry["files"].items() if sha(ROOT / p) != pin]
    assert changed == ["backend/cfaw_news/intelligence/migrate.py"]
    for name, pin in entry["review_evidence"].items():
        assert sha(ROOT / ".tmp/evals/g3/g4-pr2-review-20261102-001" / name) == pin
    source = read(AREA / "final-source-before.json")
    assert all(sha(ROOT / p) == pin for p, pin in source.items())
    parents = [ROOT / "evals/intelligence_g4/manifests" / name for name in (
        "pr1_required_tests.json", "pr1_review_required_tests.json", "pr2_required_tests.json",
        "pr2_path_review_required_tests.json")]
    expected = sorted(node for p in parents for node in read(p)["nodes"])
    cases = list(ET.parse(AREA / "g4-final.xml").iter("testcase"))
    nodes = sorted(c.get("classname").replace(".", "/") + ".py::" + c.get("name") for c in cases)
    assert nodes == expected and len(nodes) == len(set(nodes)) == 164
    for p in parents:
        assert all(sha(ROOT / name) == pin for name, pin in read(p)["test_source_sha256"].items())
    assert all(sha(ROOT / p) == pin for p, pin in read(parents[-1])["parent_manifests"].items())
    g4, legacy = suite(AREA / "g4-final.xml"), suite(AREA / "legacy.xml")
    assert g4["passed"] == 164 and legacy["passed"] == 64
    assert not any(g4[k] or legacy[k] for k in ("failure", "error", "skipped"))
    records = {p.stem.removesuffix(".command"): read(p) for p in AREA.glob("*.command.json")}
    failures = {"red-paths", "red-bounded", "green-paths-01", "ruff-01"}
    for name, record in records.items():
        assert record["exit_code"] == (1 if name in failures else 0), name
        assert sha(ROOT / record["log"]) == record["log_sha256"]
    assert {"g4-final", "legacy-related", "cli-probes-final", "schema-pr1", "schema-pr2",
            "ruff-seal"} <= set(records)
    proof_path = AREA / "probes-final/proof.json"
    proof = read(proof_path)
    assert proof["status"] == "PASS" and len(proof["executions"]) == 7
    assert all(sha(ROOT / p) == pin for p, pin in proof["source_sha256"].items())
    for execution in proof["executions"]:
        assert sha(ROOT / execution["path"]) == execution["sha256"]
        value = read(ROOT / execution["path"])
        assert value["exit_code"] == (0 if value["output"]["status"] == "PASS" else 1)
    parent = read(ROOT / "audit/g4/pr2/BASELINE.json")
    assert parent["migration"] == dict(revision=MIGRATION.REVISION,
        source_sha256=MIGRATION.source_sha256(), schema_sha256=MIGRATION.schema_sha256())
    result = dict(revision="g4-pr2-path-review-fix-v1", status="PASS_SCOPE_PENDING_INDEPENDENT_REVIEW",
        head=entry["head"], branch=entry["branch"], source=dict(files=source, sha256=digest(source)),
        results=dict(g4=g4, legacy_related=legacy, ruff="PASS", schema="PASS",
                     full_1753="HISTORICAL_NOT_RERUN", g3_630="HISTORICAL_NOT_RERUN"),
        migration=parent["migration"], commands=records,
        proof=dict(path=proof_path.relative_to(ROOT).as_posix(), sha256=sha(proof_path)),
        preservation=dict(entry_files=len(entry["files"]), allowed_changes=changed,
            review_records_unchanged=len(entry["review_evidence"]),
            original_baseline_sha256=sha(ROOT / "audit/g4/pr2/BASELINE.json"),
            original_release_sha256=sha(ROOT / "audit/g4/pr2/RELEASE_MANIFEST.json")),
        git_writes=0, user_database_writes=0, model_calls=0, live_news_network_calls=0,
        pr3_authorized=False)
    output = ROOT / "audit/g4/pr2/REVIEW_FIX_BASELINE.json"
    with output.open("xb") as stream:
        stream.write(canonical(result))
    print(json.dumps(dict(status=result["status"], source_sha256=result["source"]["sha256"],
                          baseline_sha256=sha(output), g4=g4, legacy_related=legacy)))


if __name__ == "__main__":
    main()
