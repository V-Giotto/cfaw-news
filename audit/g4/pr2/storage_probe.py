"""Offline PR2 maintenance receipt generator, restricted to fresh authored fixture DBs."""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from cfaw_news.database import Article, ArticleReading, Database, Goal
from cfaw_news.intelligence.contracts import SourcePolicy, canonical, digest
from cfaw_news.intelligence.document_store import capture_version
from cfaw_news.intelligence.migrate import sha
from cfaw_news.intelligence.models import G4Version
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[3]


def snapshot(path, *, g4=False):
    with sqlite3.connect(path) as connection:
        names = [r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table' "
                 + ("AND name LIKE 'g4_%'" if g4 else "AND name NOT LIKE 'g4_%'") + " ORDER BY name")]
        return {name: sorted(connection.execute(f'SELECT * FROM "{name}"').fetchall(), key=repr)
                for name in names}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    folder = args.out.resolve()
    if not folder.is_relative_to(ROOT / ".tmp/evals/g3/g4-pr2-20261102-001"):
        parser.error("proof must stay in this PR2 fixture area")
    folder.mkdir(parents=True, exist_ok=False)
    database = folder / "authored-old.db"
    db = Database("sqlite:///" + database.as_posix())
    db.create()
    with db.session.begin() as session:
        session.add(Article(id="authored-old", content_hash="authored-legacy-hash", origin="feed",
            data=dict(source_id="ithome", source_url="https://www.ithome.com/post/authored",
                      title="AUTHORED OLD CACHE TITLE", summary="AUTHORED OLD CACHE SUMMARY",
                      paragraphs=[dict(text="AUTHORED OLD BODY")],
                      captured_at="2020-01-01T00:00:00Z", published_at="2019-01-01T00:00:00Z")))
        session.add(Goal(id="authored-goal", data={"authored_fixture": True}))
        session.flush()
        session.add(ArticleReading(article_id="authored-old", data=dict(text="AUTHORED WEB CACHE")))
    db.engine.dispose()
    before = snapshot(database)
    commands = []

    def run(action, *, path=database, backup=None, pin=None, root=None):
        receipt = folder / (action + ("-restore" if action == "restore" else "") + ".receipt.json")
        argv = [sys.executable, "-B", "-m", "cfaw_news.intelligence.migrate", action,
                "--database", str(path), "--receipt", str(receipt)]
        if backup:
            argv += ["--backup", str(backup)]
        if pin:
            argv += ["--backup-pin", pin]
        if root:
            argv += ["--root", str(root)]
        result = subprocess.run(argv, cwd=ROOT, env={**os.environ,
            "PYTHONPATH": str(ROOT / "backend")}, capture_output=True)
        log = folder / (action + ".log")
        log.write_bytes(result.stdout + result.stderr)
        commands.append(dict(argv=argv, exit_code=result.returncode,
                             log=str(log.relative_to(ROOT)), log_sha256=sha(log),
                             receipt=str(receipt.relative_to(ROOT)), receipt_sha256=sha(receipt)))
        assert result.returncode == 0, result.stdout + result.stderr
        return json.loads(receipt.read_bytes())

    run("upgrade", backup=folder / "pre-upgrade.db")
    backfill = run("backfill", backup=folder / "pre-backfill.db", root=ROOT)
    assert snapshot(database) == before
    with db.session() as session:
        migrated = session.scalar(select(G4Version))
        assert "AUTHORED OLD" not in json.dumps(migrated.data)
        assert migrated.data["provenance"] == "legacy_cache_metadata_observed_now"
    # Explicitly synthetic author fixture, never routed into a live runtime or G3 acceptance.
    policy = SourcePolicy(source_id="authored-probe", source_url="https://example.test/feed",
        source_label="Synthetic maintenance probe", record_origin="synthetic", rights="synthetic",
        allowed_use=("metadata", "excerpt"), max_excerpt_chars=1000,
        rights_evidence_uri="https://example.test/authored-synthetic-policy")
    rows = []
    for number, title in enumerate(("Synthetic revision A", "Synthetic revision B"), 1):
        stamp = f"2026-01-01T0{number}:00:00Z"
        with db.session.begin() as session:
            v = capture_version(session, dict(id="authored-probe", source_id=policy.source_id,
                source_url="https://example.test/post/1", title=title, summary="Synthetic snippet",
                paragraphs=[], published_at=None), policy, observed_at=stamp, available_at=stamp)
            rows.append(v.model_dump(mode="json"))
    assert rows[1]["supersedes_version_id"] == rows[0]["doc_version_id"]
    db.engine.dispose()
    captured = snapshot(database, g4=True)
    rollback_backup = folder / "pre-rollback.db"
    run("rollback", backup=rollback_backup)
    assert snapshot(database) == before and snapshot(database, g4=True) == {}
    restored = folder / "authored-restored.db"
    run("restore", path=restored, backup=rollback_backup, pin=sha(rollback_backup))
    assert snapshot(restored) == before and snapshot(restored, g4=True) == captured
    report = dict(status="PASS", data_origin="authored_synthetic_fixture_not_live_evidence",
        legacy_before_sha256=digest(before), legacy_after_sha256=digest(snapshot(restored)),
        g4_before_rollback_sha256=digest(captured), g4_after_restore_sha256=digest(
            snapshot(restored, g4=True)), backfill=backfill["backfill"],
        restored_backup_sha256=sha(rollback_backup), versions=rows, commands=commands,
        external_network_calls=0, model_calls=0, user_database_writes=0)
    with (folder / "proof.json").open("xb") as stream:
        stream.write(canonical(report))
    print(json.dumps(dict(status="PASS", proof_sha256=sha(folder / "proof.json"),
                          maintenance_commands=len(commands))))


if __name__ == "__main__":
    main()
