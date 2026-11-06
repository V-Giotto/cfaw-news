"""Backup/restore and restart probe over the isolated real-material pilot only."""

import argparse
import json
import sqlite3

from cfaw_news.intelligence.persistence_migrate import maintain, restore_with_epoch
from cfaw_news.main import create_app

from audit.g4.pr6.freeze import ROOT, sha, write
from audit.g4.pr6.pilot import config
from evals.intelligence_g4.tests.persistence_support import LocalClient


def logical(path):
    with sqlite3.connect(path) as connection:
        tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        return {name: sorted(connection.execute('SELECT * FROM "' + name + '"').fetchall(), key=repr)
                for (name,) in tables if not name.startswith("sqlite_")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    run = (ROOT / args.run).resolve()
    assert run.is_relative_to(ROOT / ".tmp")
    folder = run / "pilot-native"
    source, anchor = folder / "pilot.db", folder / "anchor.json"
    assert source.resolve().is_relative_to(ROOT / ".tmp")
    out = run / "restore-proof-final"
    out.mkdir(exist_ok=False)
    before = logical(source)
    backup = out / "backup.db"
    receipt = maintain(source, anchor, "backup", backup=backup)
    assert logical(source) == before == logical(backup)
    restored = out / "restored.db"
    renewed = out / "restored-anchor.json"
    restoration = restore_with_epoch(backup, restored, renewed, expected_sha256=sha(backup), acknowledge_restore=True)
    assert logical(restored) == before
    old_epoch = json.loads(anchor.read_bytes())["epoch"]
    new_epoch = json.loads(renewed.read_bytes())["epoch"]
    assert old_epoch != new_epoch
    settings = config(folder, 8136).model_copy(update={"database_url": "sqlite:///" + restored.as_posix(), "intelligence_anchor": renewed})
    app = create_app(settings)
    with LocalClient(app, base_url="http://127.0.0.1:8136", headers={"Origin": "http://127.0.0.1:8136"}) as client:
        status = client.get("/api/intelligence/status").json()
        assert status["state"] == "ready" and status["head"]["epoch"] == new_epoch
        briefing = client.get("/api/intelligence/briefings/latest").json()
        assert briefing["mode"] == "real" and briefing["evidence_status"] == "raw_news_only"
        goals, runs, schedules = [client.get("/api/" + name).json() for name in ("goals", "runs", "schedules")]
        assert any(g["name"] == "PR6 Vite 工具核实" for g in goals)
        run_detail = client.get("/api/runs/" + runs[0]["id"]).json()
        assert run_detail["decision"]["choice"] == "watch"
        assert schedules[0]["status"] == "completed"
        response = client.post("/api/intelligence/persona", json=dict(idempotency_key="stale-before-restore",
            expected_head=status["head"]["sha256"], expected_epoch=old_epoch,
            expected_persona_version=0, domain_interests=["must not persist"]))
        assert response.status_code == 409 and response.json()["code"] == "G4_RECOVERY_EPOCH_CONFLICT", response.text
    app.state.database.engine.dispose()
    write(out / "result.json", dict(status="PASS", original_isolated_database_only=True,
        backup=receipt, restore=restoration, logical_rows_preserved=True,
        table_counts={name: len(rows) for name, rows in before.items()},
        epoch_changed=True, stale_client_rejected=True, old_goal_run_decision_schedule_preserved=True,
        real_material_raw_snapshot_preserved=True, backup_sha256=sha(backup), external_network_calls=0))
    print(json.dumps(dict(status="PASS", restored_tables=len(before), epoch_changed=True)))


if __name__ == "__main__":
    main()
