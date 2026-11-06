"""Keep the PR6 entry immutable and bind the single authorized frontend correction."""

import argparse
import json
import subprocess

from audit.g4.pr6.freeze import ENTRY, ROOT, sha
from audit.g4.pr6.seal import write_new

TARGET = ROOT / "audit/g4/pr6/REVIEW_FIX_SOURCE_FREEZE.json"
FOCUS = "frontend/src/BriefingEvidence.tsx"


def check_review():
    original = json.loads(ENTRY.read_text(encoding="utf-8"))
    current = json.loads(TARGET.read_text(encoding="utf-8"))
    assert sha(ENTRY) == current["original_entry_sha256"]
    assert set(current["files"]) == set(original["files"])
    changes = [p for p, value in current["files"].items() if value != original["files"][p]]
    assert changes == [FOCUS], changes
    assert all((ROOT / p).is_file() and sha(ROOT / p) == value for p, value in current["files"].items())
    assert "/dev-diaries/" in (ROOT / ".gitignore").read_text().splitlines()
    for folder in ("evals/intelligence_v1", "evals/intelligence_g2", "evals/intelligence_g3", "tests", "data/archive"):
        subprocess.run(["git", "diff", "--exit-code", "HEAD", "--", folder], cwd=ROOT, check=True, capture_output=True)
    return original, current


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--create", action="store_true")
    args = parser.parse_args()
    if args.create:
        original = json.loads(ENTRY.read_text(encoding="utf-8"))
        files = {p: sha(ROOT / p) for p in original["files"]}
        assert [p for p in files if files[p] != original["files"][p]] == [FOCUS]
        write_new(TARGET, dict(revision="g4-pr6-review-fix-source-v1", original_entry_sha256=sha(ENTRY), files=files,
            authorized_delta={FOCUS: dict(before=original["files"][FOCUS], after=files[FOCUS],
                reason="Explicit review fix: preserve first opener and restore focus only after real unmount under StrictMode")},
            original_frozen_assets_preserved=1145, algorithm_or_database_changes=0))
    original, current = check_review()
    print(json.dumps(dict(status="PASS", files=len(current["files"]), authorized_changes=1,
                          preserved=len(original["files"]) - 1, drift=0, sha256=sha(TARGET))))


if __name__ == "__main__":
    main()
