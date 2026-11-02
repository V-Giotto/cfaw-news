"""Fresh offline reproductions and safe rollback/restore evidence for the PR2 path review."""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

from cfaw_news.intelligence.contracts import canonical, digest
from cfaw_news.intelligence.migrate import maintain, sha

ROOT = Path(__file__).resolve().parents[3]
AREA = ROOT / ".tmp/evals/g3/g4-pr2-review-fix-20261102-001"


def snapshot(path):
    with closing(sqlite3.connect(path)) as connection:
        return digest(list(connection.iterdump()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    folder = parser.parse_args().out.resolve()
    if not folder.is_relative_to(AREA):
        parser.error("fresh authored fixture area required")
    folder.mkdir(parents=True, exist_ok=False)
    executions = []

    def cli(name, action, db, receipt, *extra, expected):
        argv = [sys.executable, "-B", "-m", "cfaw_news.intelligence.migrate", action,
                "--database", str(db), "--receipt", str(receipt), *map(str, extra)]
        result = subprocess.run(argv, cwd=ROOT, env={**os.environ,
            "PYTHONPATH": str(ROOT / "backend")}, capture_output=True, text=True)
        record = dict(argv=argv, exit_code=result.returncode, stdout=result.stdout,
                      stderr=result.stderr, output=json.loads(result.stdout))
        output = folder / (name + ".execution.json")
        output.write_bytes(canonical(record))
        executions.append(dict(path=output.relative_to(ROOT).as_posix(), sha256=sha(output)))
        assert result.returncode == expected and "Traceback" not in result.stderr
        return record["output"]

    for mode in ("DELETE", "WAL"):
        db = folder / (mode.lower() + ".db")
        maintain(db, "upgrade")
        with closing(sqlite3.connect(db)) as connection:
            assert connection.execute("PRAGMA journal_mode=" + mode).fetchone()[0] == mode.lower()
            connection.execute("CREATE TABLE legacy_preserved(value TEXT)")
            connection.execute("INSERT INTO legacy_preserved VALUES ('authored fixture only')")
            connection.commit()
        before = snapshot(db)
        try:
            maintain(db, "rollback", backup=str(db) + "-journal")
        except ValueError as error:
            assert str(error) == "G4_PATH_RESERVED"
        else:
            raise AssertionError("unsafe API input accepted")
        rejected = cli(mode + "-journal", "rollback", db, folder / (mode + "-refused.json"),
                       "--backup", str(db) + "-journal", expected=1)
        assert rejected["error_code"] == "G4_PATH_RESERVED"
        assert rejected["database_state"] == "not_started" and snapshot(db) == before
        safe = folder / (mode + "-safe-backup.db")
        result = cli(mode + "-rollback", "rollback", db, folder / (mode + "-rollback.json"),
                     "--backup", safe, expected=0)
        assert result["backup_verified_after_commit"] and safe.is_file()
        assert sha(safe) == result["backup"]["backup_sha256"]
        restored = folder / (mode + "-restored.db")
        cli(mode + "-restore", "restore", restored, folder / (mode + "-restore.json"),
            "--backup", safe, "--backup-pin", sha(safe), expected=0)
        assert snapshot(restored) == before

    new = folder / "receipt-collision.db"
    result = cli("receipt-collision", "upgrade", new, new, expected=1)
    assert result["database_state"] == "not_started" and not new.exists()
    result = dict(status="PASS", scope="authored_synthetic_offline_maintenance_probes",
                  executions=executions, source_sha256={p.relative_to(ROOT).as_posix(): sha(p)
                    for p in (ROOT / "backend/cfaw_news/intelligence/migrate.py",
                              ROOT / "backend/cfaw_news/intelligence/maintenance_io.py")},
                  real_user_database_writes=0, live_network_calls=0, model_calls=0)
    (folder / "proof.json").write_bytes(canonical(result))
    print(json.dumps(dict(status="PASS", executions=len(executions), proof_sha256=sha(
        folder / "proof.json"))))


if __name__ == "__main__":
    main()
