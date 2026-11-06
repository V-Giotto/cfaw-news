"""Read-only reproduction of the invalid v1 seal; retain damaged evidence unchanged."""

import json

from audit.g4.pr6.freeze import ROOT, sha
from audit.g4.pr6.seal import pin, write_new

OUT = ROOT / ".tmp/evals/g3/g4-pr6-review-fix-20261105-001"


def main():
    release = ROOT / "audit/G4_RELEASE_MANIFEST.json"
    old = json.loads(release.read_text(encoding="utf-8"))
    mismatches = []
    counts = dict(directories=0, files=0)

    def walk(index):
        data = json.loads(index.read_text(encoding="utf-8"))
        assert data["revision"] == "g4-pr6-directory-manifest-v1"
        counts["directories"] += 1
        for name, expected in data["files"].items():
            path = index.parent / name
            counts["files"] += 1
            if pin(path) != expected:
                mismatches.append(dict(path=path.relative_to(ROOT).as_posix(), expected=expected,
                    actual=pin(path), case_alias=path.samefile(index), revision=json.loads(path.read_text())["revision"]))
        for name in data["children"]:
            walk(index.parent / name / "MANIFEST.json")

    for name in old["directory_manifests"]:
        walk(ROOT / name)
    assert len(mismatches) == 9 and all(x["case_alias"] for x in mismatches), mismatches
    archived = ROOT / "audit/g4/pr6/INVALIDATED_RELEASE_MANIFEST_V1.json"
    write_new(archived, old)
    result = dict(status="INVALID_V1_SEAL_DO_NOT_USE", release_sha256=sha(release),
                  archived_release=archived.relative_to(ROOT).as_posix(), counts=counts,
                  mismatches=mismatches, original_damaged_files_untouched=True,
                  remedy="Fresh complete tests in p6-fix-full/p6-fix-g4; no attempt to infer lost bytes from hashes")
    write_new(OUT / "legacy-seal-audit.json", result)
    print(json.dumps(dict(status=result["status"], **counts, mismatches=len(mismatches))))


if __name__ == "__main__":
    main()
