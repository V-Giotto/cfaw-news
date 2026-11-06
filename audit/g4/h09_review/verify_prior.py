"""Verify both historical reference trees without opening any SQLite database."""

from audit.g4.h09.proof import read
from audit.g4.h09_review.quarantine import RUN
from audit.g4.pr6.freeze import ROOT
from audit.g4.pr6.seal import pin, verify_roots, write_new


def main():
    results = {}
    for name, key in (("audit/G4_RELEASE_MANIFEST.json", "index_roots"), ("audit/G4_H09_REPAIR_MANIFEST.json", "roots")):
        path = ROOT / name
        original = pin(path)
        result = verify_roots(read(path)[key])
        assert pin(path) == original
        results[name] = dict(seal=original, tree=result)
    write_new(RUN / "prior-tree-verification.json", dict(status="PASS", prior=results,
        disposition="only the disclosed unindexed sidecars were quarantined; old indexes and indexed bytes unchanged"))
    print("PASS: both historical seals and every referenced directory/file verified; no SQLite opens")


if __name__ == "__main__":
    main()
