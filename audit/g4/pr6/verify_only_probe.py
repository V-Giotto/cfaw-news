"""Run the real verify-only CLI while rejecting Python filesystem mutations."""

import json
import os
import runpy
import sys

from audit.g4.pr6.freeze import ROOT, sha

RUN = ROOT / ".tmp/evals/g3/g4-pr6-review-fix-20261105-001"


def state(path):
    stat = path.stat()
    return dict(sha256=sha(path), bytes=stat.st_size, mtime_ns=stat.st_mtime_ns)


def main():
    # Prevent import caches and optional Git index refreshes during the read-only probe.
    sys.dont_write_bytecode = True
    os.environ["GIT_OPTIONAL_LOCKS"] = "0"
    paths = [RUN / name for name in ("control-verification.json", "inventory.json",
        "full-final-control.json", "collect-control.json", "full-final.xml")]
    before = {str(p.relative_to(ROOT)): state(p) for p in paths}
    attempts = []
    write_flags = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
    mutation_events = {"os.mkdir", "os.remove", "os.rmdir", "os.rename", "os.chmod", "os.utime", "os.truncate",
                       "os.link", "os.symlink", "shutil.copyfile", "shutil.copymode", "shutil.copystat"}

    def guard(event, args):
        writing = event == "open" and (
            isinstance(args[1], str) and any(c in args[1] for c in "wax+") or args[2] & write_flags)
        if writing or event in mutation_events:
            attempts.append(dict(event=event, target=str(args[0])))
            raise PermissionError("read-only CLI attempted filesystem mutation: " + str(args[0]))

    sys.addaudithook(guard)
    sys.argv = [str(ROOT / "audit/g4/pr6/finalize.py"), "--verify-only"]
    try:
        runpy.run_module("audit.g4.pr6.finalize", run_name="__main__")
    finally:
        after = {str(p.relative_to(ROOT)): state(p) for p in paths}
        print(json.dumps(dict(status="PASS" if not attempts and before == after else "FAIL_WRITE_ATTEMPT",
                              write_attempts=attempts, before=before, after=after)))
        assert before == after, "sealed evidence changed"
    assert not attempts, attempts


if __name__ == "__main__":
    main()
