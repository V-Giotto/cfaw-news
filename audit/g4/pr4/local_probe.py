"""Standalone current-run CLI, SQLite and API evidence using authored mocks only."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from cfaw_news.intelligence.contracts import digest
from cfaw_news.intelligence.history_store import HistoryStore
from cfaw_news.intelligence.persistence_models import BriefingRun, BriefingSnapshot
from cfaw_news.intelligence.runtime_contracts import FACT_PIN, RANK_PIN
from sqlalchemy import select

from evals.intelligence_g2.contracts import json_bytes
from evals.intelligence_g4.tests.persistence_support import (
    LocalClient,
    capture,
    current_status,
    preconditions,
    save_persona,
    setup_app,
    start,
    wait_run,
)

ROOT = Path(__file__).resolve().parents[3]
AREA = None


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(json_bytes(value))


def maintenance():
    from cfaw_news.database import Database
    from cfaw_news.intelligence.migrate import sha as file_sha

    from evals.intelligence_g4.tests.test_history_db import append, head
    folder = AREA / "maintenance"
    folder.mkdir()
    database, anchor = folder / "local.db", folder / "head.json"
    receipts = []
    def cli(name, action, *extra):
        receipt = folder / (name + ".receipt.json")
        argv = [sys.executable, "-B", "-m", "cfaw_news.intelligence.persistence_migrate", action,
                "--database", str(database), "--anchor", str(anchor), "--receipt", str(receipt), *map(str, extra)]
        tick = time.perf_counter()
        process = subprocess.run(argv, cwd=ROOT, env={**os.environ}, capture_output=True, timeout=60)
        (folder / (name + ".stdout.log")).write_bytes(process.stdout)
        (folder / (name + ".stderr.log")).write_bytes(process.stderr)
        assert process.returncode == 0, process.stdout + process.stderr
        output = json.loads(process.stdout)
        assert output["status"] == "PASS" and output["receipt_written"]
        write(folder / (name + ".execution.json"), dict(argv=argv, cwd=str(ROOT), exit_code=process.returncode,
            elapsed_seconds=time.perf_counter() - tick, stdout_sha256=sha(folder / (name + ".stdout.log")),
            stderr_sha256=sha(folder / (name + ".stderr.log")), receipt_sha256=sha(receipt)))
        receipts.append(receipt.relative_to(ROOT).as_posix())
        return output
    cli("upgrade", "upgrade")
    db = Database("sqlite:///" + database.as_posix())
    store = HistoryStore(db, anchor)
    append(store, head(store))
    before = head(store)
    rolled = cli("rollback", "rollback", "--backup", folder / "complete.db")
    assert rolled["backup_verified_after_commit"]
    restored = folder / "restored.db"
    restored_anchor = folder / "restored-head.json"
    database, anchor = restored, restored_anchor
    cli("restore", "restore", "--backup", folder / "complete.db", "--backup-pin", file_sha(folder / "complete.db"),
        "--acknowledge-restored-history")
    copied = Database("sqlite:///" + restored.as_posix())
    assert head(HistoryStore(copied, restored_anchor)) == before
    write(folder / "proof.json", dict(status="PASS", receipts=receipts, logical_head_before_rollback=before,
        logical_head_after_restore=before, backup_sha256=file_sha(folder / "complete.db"),
        schema_tables_restored=True, fresh_checkpoint_epoch=True))
    db.engine.dispose()
    copied.engine.dispose()


def api():
    folder = AREA / "api"
    app, clock, _, anchor = setup_app(folder)
    exchanges = []
    with LocalClient(app, base_url="http://127.0.0.1:8000", headers={"Origin": "http://127.0.0.1:8000"}) as client:
        def record(name, response):
            value = response.json() if response.content else None
            write(folder / (name + ".json"), dict(method=response.request.method, url=str(response.request.url),
                request=json.loads(response.request.content) if response.request.content else None,
                status_code=response.status_code, etag=response.headers.get("etag"), body=value))
            exchanges.append(dict(case=name, status=response.status_code, sha256=sha(folder / (name + ".json"))))
            return value
        record("status", client.get("/api/intelligence/status"))
        record("persona", save_persona(client))
        version = capture(app, clock)
        run = record("start", start(client))
        terminal = wait_run(client, run["resource_id"])
        assert terminal["status"] == "completed", terminal
        record("run", client.get("/api/intelligence/runs/" + run["resource_id"]))
        view = record("latest", client.get("/api/intelligence/briefings/latest"))
        assert view["evidence_status"] == "raw_news_only" and not view["deliveries"]
        target = view["archive"][0]
        detail = record("detail", client.get("/api/intelligence/events/detail", params=dict(briefing_id=view["id"],
            event_snapshot_id=target["event_snapshot_id"])))
        assert detail["claims"][0]["attribution"]["attribution_kind"] == "secondary_material"
        assert all(a["verification_state"] == "unverified" for a in detail["assessments"])
        assert record("before-interactions", client.get("/api/intelligence/interactions")) == []
        response = client.post("/api/intelligence/interactions", json=dict(**preconditions(client), idempotency_key="actual-open",
            briefing_id=view["id"], expected_snapshot_version=view["version"], target_id=target["id"],
            kind="opened", confirmation="detail_opened"))
        record("opened", response)
        rows = record("after-interactions", client.get("/api/intelligence/interactions"))
        assert len(rows) == 1 and rows[0]["kind"] == "opened" and rows[0]["learned"] is False
        with app.state.intelligence.store.read() as (session, _):
            row = session.get(BriefingRun, run["resource_id"])
            raw = json_bytes(row.input)
            assert hashlib.sha256(raw).hexdigest() == row.input_sha256
            (folder / "runtime-input.json").write_bytes(raw)
            snapshot = session.scalar(select(BriefingSnapshot).where(BriefingSnapshot.id == view["id"]))
            output = json_bytes(snapshot.runtime)
            assert hashlib.sha256(output).hexdigest() == snapshot.runtime_sha256
            (folder / "runtime-output.json").write_bytes(output)
            for i, stage in enumerate(snapshot.runtime["stages"]):
                write(folder / "stages" / (str(i) + ".json"), stage)
        write(folder / "proof.json", dict(status="PASS", fixture_provenance="AI-authored real-shaped RSS / mocked clock / test policy",
            live_news=False, genuine_rights_validation=False, version_id=version.doc_version_id,
            runtime_input_sha256=sha(folder / "runtime-input.json"), runtime_output_sha256=sha(folder / "runtime-output.json"),
            state=view["evidence_status"], full_archive=len(view["archive"]), deliveries=len(view["deliveries"]),
            history_scoring=view["history_scoring"], head=current_status(client)["head"], exchanges=exchanges,
            checkpoint_sha256=sha(anchor), reading_behavior_inferred=False))


def main():
    global AREA
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    AREA = (ROOT / args.out).resolve()
    if not AREA.is_relative_to(ROOT / ".tmp/evals/g3/g4-pr4-20261102-001"):
        raise ValueError("probe output must stay in this run's artifact area")
    AREA.mkdir(exist_ok=False)
    maintenance()
    api()
    files = {p.relative_to(ROOT).as_posix(): sha(p) for p in AREA.rglob("*") if p.is_file()}
    write(AREA / "proof.json", dict(status="PASS", files=files, aggregate_sha256=digest(files),
        runtime_policy_sha256=RANK_PIN, fact_signature_policy_sha256=FACT_PIN,
        live_news_network_calls=0, external_model_calls=0, user_database_writes=0))
    print(json.dumps(dict(status="PASS", files=len(files), proof_sha256=sha(AREA / "proof.json"))))


if __name__ == "__main__":
    main()
