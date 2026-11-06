"""Seal PR5 local engineering evidence. Reads only this repo's explicitly selected files."""

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / ".tmp/evals/g3/g4-pr5-20261104-002"
OUT = ROOT / "audit/g4/pr5/PR5_BASELINE.json"
CHECKS = ("legacy-pytest", "pr4-closure-regression", "browser-fixtures", "schema-check", "types-check",
          "baseline", "ruff-assets", "frontend-build-delivery", "frontend-tests-seal", "browser-assets-final")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def junit(name):
    nodes = ET.parse(RUN / name).getroot().findall(".//testcase")
    result = dict(nodes=len(nodes), passed=0, failure=0, error=0, skipped=0)
    for node in nodes:
        category = next((kind for kind in ("failure", "error", "skipped") if node.find(kind) is not None), "passed")
        result[category] += 1
    assert result["failure"] == result["error"] == 0
    return result


def main():
    subprocess.run(["git", "diff", "--exit-code", "--", "backend", "tests", "evals", "docs/adr", "audit/g4/pr4"],
                   cwd=ROOT, check=True, capture_output=True)
    assert "/dev-diaries/" in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    receipts = {}
    for name in CHECKS:
        path = RUN / (name + ".command.json")
        value = json.loads(path.read_text(encoding="utf-8"))
        assert value["exit_code"] == 0, name
        assert sha(ROOT / value["log"]) == value["log_sha256"], name
        receipts[name] = dict(path=path.relative_to(ROOT).as_posix(), sha256=sha(path), **value)
    browser = json.loads((RUN / "browser/browser-results.json").read_text(encoding="utf-8"))
    assert browser["status"] == "PASS" and not browser["production_database_used"]
    source = [ROOT / name for name in ("frontend/src/App.tsx", "frontend/src/api.ts", "frontend/src/styles.css",
        "frontend/src/BriefingHome.tsx", "frontend/src/BriefingEvidence.tsx", "frontend/src/intelligence.ts",
        "frontend/src/intelligence.generated.ts", "frontend/tests/intelligence.test.cjs", "frontend/package.json")]
    source.extend(p for p in (ROOT / "audit/g4/pr5").iterdir() if p.is_file() and p != OUT)
    unchanged = [ROOT / name for name in ("backend/cfaw_news/intelligence/service.py", "frontend/src/NewsLibrary.tsx",
        "frontend/src/ArticleReader.tsx", "frontend/src/GoalWorkspace.tsx", "frontend/src/ActivityPages.tsx", ".gitignore")]
    preserved = {p.relative_to(ROOT).as_posix(): sha(p) for p in unchanged}
    assert preserved["backend/cfaw_news/intelligence/service.py"] == "20afee774f8c734f87650f75ba48e895f390e40af83d23dfee0e7e1d5144da83"
    screenshots = {name: sha(RUN / "browser" / name) for name in browser["screenshots"]}
    value = dict(revision="g4-pr5-ui-baseline-v1", status="IMPLEMENTED_PENDING_REVIEW",
        entry_head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        source_sha256={p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(source)}, preserved_sha256=preserved,
        receipts=receipts, legacy=junit("legacy.xml"), pr4=junit("pr4.xml"),
        browser=browser, browser_result_sha256=sha(RUN / "browser/browser-results.json"), screenshots_sha256=screenshots,
        frontend_policy_tests=10, pr4_independent_review="PENDING", pr5_independent_review="PENDING",
        owner_approval="PENDING", next_pr_started=False, production_database_used=False,
        live_news=False, live_model=False, git_writes=0, notifications_added=False)
    OUT.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(status=value["status"], legacy=value["legacy"], pr4=value["pr4"],
        browser_checks=len(browser["checks"]), manifest_sha256=sha(OUT))))


if __name__ == "__main__":
    main()
