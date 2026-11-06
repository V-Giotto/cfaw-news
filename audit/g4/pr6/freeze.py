"""PR6 QA source/dependency freeze; excludes private data and never writes Git."""

import argparse
import hashlib
import importlib.metadata
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ENTRY = ROOT / "audit/g4/pr6/ENTRY_FREEZE.json"
EXCLUDED = {"docs/G4_ACCEPTANCE.md", "docs/G4_G5_HANDOFF.md", "docs/G4_BETA_USER_GUIDE.md",
            "audit/G4_RELEASE_MANIFEST.json"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def check():
    entry = json.loads(ENTRY.read_text(encoding="utf-8"))
    drift = [name for name, pin in entry["files"].items() if not (ROOT / name).is_file() or sha(ROOT / name) != pin]
    assert not drift, drift
    assert "/dev-diaries/" in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    return entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        entry = check()
        print(json.dumps(dict(status="PASS", frozen_files=len(entry["files"]), drift=0)))
        return
    assert not ENTRY.exists(), "new freeze required; never overwrite entry"
    names = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT, text=True).splitlines()
    files = {name: sha(ROOT / name) for name in sorted(set(names))
             if name not in EXCLUDED and not name.startswith(("audit/g4/pr6/", "dev-diaries/")) and (ROOT / name).is_file()}
    for folder in ("evals/intelligence_v1", "evals/intelligence_g2", "evals/intelligence_g3", "tests", "data/archive"):
        subprocess.run(["git", "diff", "--exit-code", "HEAD", "--", folder], cwd=ROOT, check=True, capture_output=True)
    for seal in ("PR5_BASELINE.json", "PR5_REVIEW_FIX_BASELINE.json"):
        value = json.loads((ROOT / "audit/g4/pr5" / seal).read_text(encoding="utf-8"))
        if seal.startswith("PR5_REVIEW"):
            assert all(sha(ROOT / p) == pin for p, pin in value["source_sha256"].items())
    from cfaw_news.intelligence.persistence_migrate import MIGRATION
    from cfaw_news.intelligence.runtime_contracts import FACT_PIN, RANK_PIN, RuntimeConfig

    from evals.intelligence_g3.pytest_control import snapshot
    control = snapshot()
    packages = sorted({(d.metadata["Name"], d.version) for d in importlib.metadata.distributions()})
    reports = {p.relative_to(ROOT).as_posix(): sha(p) for n in range(1, 6)
               for p in (ROOT / f"audit/g4/pr{n}").glob("*.md")}
    value = dict(revision="g4-pr6-entry-v1", observed_at=datetime.now(timezone.utc).isoformat(),
        head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        branch=subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip(),
        status=subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True), files=files,
        source_tree_sha256=hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
        report_sha256=reports, python_distributions=packages, pytest_control=control,
        native_runtime_config=RuntimeConfig(budget={"profile": "focus70-radar30-v1"}).model_dump(mode="json"),
        fact_policy=FACT_PIN, rank_policy=RANK_PIN, migration_source_sha256=MIGRATION.source_sha256(),
        database_schema_sha256=MIGRATION.schema_sha256(),
        g4_api_contract=json.loads((ROOT / "evals/intelligence_g4/schema/pr5_review_fix/Version.json").read_bytes()),
        production_source_registry=json.loads((ROOT / "data/g4_source_policies.json").read_bytes()),
        review_status={"PR1": "PASS_independent_AI_via_pr2_UPSTREAM_REVIEW", "PR2": "PASS_independent_AI",
                       "PR3": "PASS_independent_AI", "PR4_shutdown": "PENDING_independent_review",
                       "PR5_fixes": "PENDING_independent_review", "G4_Beta": "PENDING_owner_approval"},
        authorization="Current user explicitly authorized PR6 QA/documents only; no external fetch/publish/deploy",
        excluded_outputs=sorted(EXCLUDED), new_qa_files_excluded_prefix="audit/g4/pr6/", git_writes=0)
    write(ENTRY, value)
    print(json.dumps(dict(status="FROZEN", files=len(files), sha256=sha(ENTRY), fact_policy=FACT_PIN)))


if __name__ == "__main__":
    main()
