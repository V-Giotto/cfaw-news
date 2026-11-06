"""Reproduce the reported late Persona against a restored copy of sealed public QA data."""

import argparse
import shutil
from datetime import datetime

from cfaw_news.config import Settings
from cfaw_news.intelligence.persistence_migrate import restore_with_epoch
from cfaw_news.intelligence.persistence_models import BriefingSnapshot
from cfaw_news.main import create_app

from audit.g4.pr6.freeze import ROOT, sha, write
from evals.intelligence_g4.tests.persistence_support import (
    LocalClient,
    current_status,
    preconditions,
    start,
    wait_run,
)


def input_inventory(folder):
    return {p.name: dict(bytes=p.stat().st_size, modified_ns=p.stat().st_mtime_ns, sha256=sha(p))
            for p in folder.iterdir() if p.is_file()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    base = ROOT / ".tmp/evals/g3/g4-pr6-review-fix-20261105-001"
    backup = base / "restore-proof-final/backup.db"
    original = sha(backup)
    before = input_inventory(backup.parent)
    out = (ROOT / args.out).resolve()
    assert out.is_relative_to(ROOT / ".tmp")
    out.mkdir(exist_ok=False)
    source_copy = out / "input/backup.db"
    source_copy.parent.mkdir()
    with backup.open("rb") as source, source_copy.open("xb") as target:
        shutil.copyfileobj(source, target)
    assert sha(source_copy) == original
    restore_with_epoch(source_copy, out / "copy.db", out / "copy-anchor.json", expected_sha256=original, acknowledge_restore=True)
    assert input_inventory(backup.parent) == before
    (out / "project/data").mkdir(parents=True)
    (out / "project/data/sources.json").write_text('{"sources": []}', encoding="utf-8")
    settings = Settings(_env_file=None, root=out / "project", database_url="sqlite:///" + (out / "copy.db").as_posix(),
        intelligence_anchor=out / "copy-anchor.json", intelligence_enabled=True, llm_mode="baseline",
        news_auto_refresh=False, news_media_fetch=False, news_reading_fetch=False)
    app = create_app(settings)
    with LocalClient(app, base_url="http://127.0.0.1:8000", headers={"Origin": "http://127.0.0.1:8000"}) as client:
        persona = client.get("/api/intelligence/persona").json()
        assert persona["version"] == 4 and persona["attention_budget_seconds"] == 420, persona
        old = client.get("/api/intelligence/briefings/latest").json()
        with app.state.database.session() as session:
            old_input = session.get(BriefingSnapshot, old["id"]).runtime["input"]
        assert datetime.fromisoformat(persona["available_at"]) > datetime.fromisoformat(old_input["versions"][0]["available_at"])
        for budget in (420, 180):
            if budget == 180:
                response = client.post("/api/intelligence/persona", json=dict(**preconditions(client),
                    idempotency_key="new-budget-after-legacy", expected_persona_version=4,
                    domain_interests=persona["domain_interests"], attention_budget_seconds=180))
                assert response.status_code == 201, response.text
            response = start(client, key="replay-" + str(budget))
            assert response.status_code == 202, response.text
            terminal = wait_run(client, response.json()["resource_id"], timeout=60)
            assert terminal["status"] == "completed", terminal
            new = client.get("/api/intelligence/briefings/" + terminal["snapshot_id"]).json()
            with app.state.database.session() as session:
                result = session.get(BriefingSnapshot, new["id"]).runtime
            assert result["input"]["versions"] == old_input["versions"]
            assert result["input"]["config"]["attention_budget_seconds"] == budget
            assert new["archive"][0]["event_key"] == old["archive"][0]["event_key"]
            assert result["context"] is not None and result["ranking"] is not None
            assert result["context"]["journal"]["ignored_archive_interaction_ids"]
            write(out / (f"budget-{budget}.json"), dict(briefing=new, persona_history=result["input"]["persona_history"],
                window=result["input"]["visit_window"], reason_codes=result["reason_codes"],
                mapped_history=len(result["context"]["journal"]["entries"]),
                ignored_archive_history=result["context"]["journal"]["ignored_archive_interaction_ids"]))
        assert current_status(client)["state"] == "ready"
    app.state.database.engine.dispose()
    assert sha(backup) == original
    after = input_inventory(backup.parent)
    assert after == before
    write(out / "input-preservation.json", dict(status="PASS", before=before, after=after,
        sqlite_opened_original=False, source_copy_sha256=sha(source_copy)))
    write(out / "result.json", dict(status="PASS", source_backup_sha256=original, original_backup_unchanged=True,
        original_input_directory_unchanged=True, sqlite_opened_original=False,
        original_persona_version=4, tested_budgets=[420, 180], evidence_not_ready_persona_error_closed=True,
        material_times_and_ids_unchanged=True, event_identity_preserved=True, real_qualification="raw_news_only",
        external_network_smoke="not_evaluated", original_user_database_used=False))
    print("PASS: actual sealed QA Persona v4/420, then save v5/180; both native generations completed on a restored copy")


if __name__ == "__main__":
    main()
