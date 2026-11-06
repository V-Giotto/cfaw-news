"""Preserve and move only the two disclosed, unindexed QA SQLite sidecars."""

import argparse

from audit.g4.h09.proof import read
from audit.g4.pr6.freeze import ROOT
from audit.g4.pr6.seal import INDEX, pin, verify_roots, write_new

RUN = ROOT / ".tmp/evals/g3/g4-h09-review-fix-20261106-001"
FOLDER = ROOT / ".tmp/evals/g3/g4-pr6-review-fix-20261105-001/restore-proof-final"
NAMES = ("backup.db-wal", "backup.db-shm")


def check_index():
    seal = read(ROOT / "audit/G4_RELEASE_MANIFEST.json")
    root = FOLDER.parent
    expected = seal["index_roots"][root.relative_to(ROOT).as_posix()]
    assert pin(root / INDEX) == expected
    expected = read(root / INDEX)["children"][FOLDER.name]
    assert pin(FOLDER / INDEX) == expected
    original = read(FOLDER / INDEX)
    assert len(original["files"]) == 7
    assert all(pin(FOLDER / n) == value for n, value in original["files"].items())
    return expected, original


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("capture", "apply"))
    args = parser.parse_args()
    assert FOLDER.resolve().is_relative_to(ROOT / ".tmp/evals/g3/g4-pr6-review-fix-20261105-001")
    expected, original = check_index()
    current = {p.name for p in FOLDER.iterdir()}
    if args.phase == "capture":
        assert current - set(original["files"]) - {INDEX} == set(NAMES)
        try:
            verify_roots({FOLDER.relative_to(ROOT).as_posix(): expected})
        except ValueError as error:
            observed = dict(status="FAIL_REPRODUCED", error=str(error))
        else:
            raise AssertionError("original inventory failure was not reproduced")
        evidence = RUN / "sidecar-evidence"
        evidence.mkdir(exist_ok=False)
        metadata = {}
        for name in NAMES:
            path = FOLDER / name
            stat = path.stat()
            assert not path.is_symlink() and not path.is_junction()
            assert stat.st_size == (0 if name.endswith("-wal") else 32768)
            (evidence / name).write_bytes(path.read_bytes())
            assert pin(evidence / name) == pin(path)
            metadata[name] = dict(**pin(path), created_ns=stat.st_birthtime_ns, modified_ns=stat.st_mtime_ns)
        write_new(RUN / "sidecar-capture.json", dict(verification=observed, original_files_verified=original["files"],
            original_index=expected, sidecars=metadata, source_directory=FOLDER.relative_to(ROOT).as_posix(),
            old_seal=pin(ROOT / "audit/G4_RELEASE_MANIFEST.json")))
        print("FAIL_REPRODUCED: original inventory differs by exactly two preserved QA sidecars; original seven files intact")
        return
    captured = read(RUN / "sidecar-capture.json")
    assert pin(ROOT / "audit/G4_RELEASE_MANIFEST.json") == captured["old_seal"]
    assert current - set(original["files"]) - {INDEX} == set(NAMES)
    destination = RUN / "quarantined-sidecars"
    destination.mkdir(exist_ok=False)
    for name in NAMES:
        source, target = FOLDER / name, destination / name
        assert source.resolve().parent == FOLDER.resolve()
        assert target.resolve().is_relative_to(RUN.resolve()) and not target.exists()
        assert pin(source) == pin(RUN / "sidecar-evidence" / name)
        assert source.stat().st_mtime_ns == captured["sidecars"][name]["modified_ns"]
        source.rename(target)  # Exact, non-recursive move; never touches indexed DB/index bytes.
    verified = verify_roots({FOLDER.relative_to(ROOT).as_posix(): expected})
    check_index()
    write_new(RUN / "sidecar-disposition.json", dict(status="PASS", action="moved_exact_two_unindexed_sidecars_to_preserved_quarantine",
        original_seven_files_unchanged=True, original_indexes_unchanged=True, original_seal_unchanged=True,
        directory_verification=verified, removed_from_original_directory=list(NAMES), evidence_retained=True))
    print("PASS: evidence retained; only the two unindexed sidecars moved; original directory index verifies without rewriting")


if __name__ == "__main__":
    main()
