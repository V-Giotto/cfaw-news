"""Append-only PR5 review-fix evidence manifest; never replaces the original seal."""

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / ".tmp/evals/g3/g4-pr5-review-20261105-001"
OUT = ROOT / "audit/g4/pr5/PR5_REVIEW_FIX_BASELINE.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def counts(name):
    nodes = ET.parse(RUN / name).getroot().findall(".//testcase")
    result = dict(passed=0, skipped=0, failure=0, error=0)
    for node in nodes:
        kind = next((kind for kind in ("skipped", "failure", "error") if node.find(kind) is not None), "passed")
        result[kind] += 1
    assert result["failure"] == result["error"] == 0
    return result


def main():
    original = ROOT / "audit/g4/pr5/PR5_BASELINE.json"
    assert sha(original) == "48fb85897bf406a1e8922f4b3a5a5145d2d6ab96a48e817c5f7144788a5e9fa6"
    old = json.loads(original.read_text(encoding="utf-8"))
    old_report = "audit/g4/pr5/IMPLEMENTATION_REPORT.md"
    assert sha(ROOT / old_report) == old["source_sha256"][old_report]
    subprocess.run(["git", "diff", "--exit-code", "--", "evals/intelligence_g2", "evals/intelligence_g3",
        "tests", "evals/intelligence_g4/schema/pr4", "evals/intelligence_g4/schema/pr4_review_fix",
        "backend/cfaw_news/intelligence/migrations", ".gitignore"], cwd=ROOT, capture_output=True, check=True)
    receipts = {}
    for name in ("legacy", "g4-final", "ruff-final", "baseline", "schema", "types", "frontend-unit", "frontend-build", "browser-final", "fixtures"):
        path = RUN / (name + ".command.json")
        receipt = json.loads(path.read_text(encoding="utf-8"))
        assert receipt["exit_code"] == 0
        assert sha(ROOT / receipt["log"]) == receipt["log_sha256"]
        receipts[name] = dict(record_sha256=sha(path), **receipt)
    sources = list((ROOT / "frontend/src").glob("*")) + list((ROOT / "frontend/tests").glob("*"))
    sources += [ROOT / "backend/cfaw_news/intelligence" / name for name in
                ("service.py", "publication.py", "persistence_contracts.py", "persistence_schema.py")]
    sources += [ROOT / "evals/intelligence_g4/tests/test_pr5_review_fixes.py"]
    sources += [p for p in (ROOT / "audit/g4/pr5").glob("*") if p.name not in (OUT.name, "PR5_BASELINE.json")]
    schemas = list((ROOT / "evals/intelligence_g4/schema/pr5_review_fix").glob("*.json"))
    browser_file = RUN / "browser/browser-results.json"
    browser = json.loads(browser_file.read_text(encoding="utf-8"))
    assert browser["status"] == "PASS" and browser["static_resource_errors"] == []
    value = dict(revision="g4-pr5-review-fix-v1", status="FIXED_PENDING_INDEPENDENT_REVIEW",
        entry_head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        original_seal_sha256=sha(original), receipts=receipts, g4=counts("g4-final.xml"), legacy=counts("legacy.xml"),
        frontend_tests=14, browser=browser, browser_sha256=sha(browser_file),
        source_sha256={p.relative_to(ROOT).as_posix(): sha(p) for p in sources if p.is_file()},
        schema_sha256={p.name: sha(p) for p in schemas},
        screenshots_sha256={name: sha(RUN / "browser" / name) for name in browser["screenshots"]},
        production_database_used=False, native_algorithms_changed=False, git_writes=0,
        independent_review="PENDING", owner_approval="PENDING", next_pr_started=False)
    OUT.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(status=value["status"], g4=value["g4"], legacy=value["legacy"],
        browser_checks=len(browser["checks"]), sha256=sha(OUT))))


if __name__ == "__main__":
    main()
