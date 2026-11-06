"""Fresh licensed offline pilot, with the first actual Persona AFTER material capture."""

import argparse

from cfaw_news.database import Article
from cfaw_news.intelligence.document_store import add_coverage, capture_version
from cfaw_news.intelligence.persistence_migrate import maintain
from cfaw_news.main import create_app

from audit.g4.pr6.freeze import ROOT, write
from audit.g4.pr6.pilot import SOURCE_ID, config, freeze_sample, now, row_and_policy
from evals.intelligence_g4.tests.persistence_support import (
    LocalClient,
    preconditions,
    start,
    wait_run,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    folder = (ROOT / args.out).resolve()
    assert folder.is_relative_to(ROOT / ".tmp") and not folder.exists()
    provenance = freeze_sample()
    settings = config(folder, 8136)
    maintain(folder / "pilot.db", folder / "anchor.json", "upgrade")
    app = create_app(settings)
    row, policy, rss = row_and_policy()
    snapshots = []
    with LocalClient(app, base_url="http://127.0.0.1:8136", headers={"Origin": "http://127.0.0.1:8136"}) as client:
        observed = now()
        with app.state.database.session.begin() as session:
            session.add(Article(id=row["id"], origin="feed", content_hash=row["content_hash"], data=row))
            version = capture_version(session, row, policy, observed_at=observed, available_at=observed)
            add_coverage(session, SOURCE_ID, observed, observed, observed, "covered", "bounded_parse")
        response = client.post("/api/intelligence/persona", json=dict(**preconditions(client), idempotency_key="late-first-persona",
            expected_persona_version=0, domain_interests=["Vite build tooling"], attention_budget_seconds=420))
        assert response.status_code == 201, response.text
        persona = client.get("/api/intelligence/persona").json()
        assert persona["available_at"] > observed.replace("+00:00", "Z")
        for i in range(2):
            response = start(client, key=f"unobserved-{i}")
            assert response.status_code == 202, response.text
            terminal = wait_run(client, response.json()["resource_id"], timeout=60)
            assert terminal["status"] == "completed", terminal
            snapshots.append(client.get("/api/intelligence/briefings/" + terminal["snapshot_id"]).json())
        assert client.get("/api/intelligence/interactions").json() == []
        assert client.get("/api/intelligence/visits/latest").json() is None
    app.state.database.engine.dispose()
    write(folder / "result.json", dict(briefing_id=snapshots[-1]["id"], initial_snapshot_ids=[s["id"] for s in snapshots],
        record_origin="real", material="unmodified licensed Vite 8.3.4 README", provenance=provenance,
        observed_at=observed, persona=persona, doc_version_id=version.doc_version_id,
        external_fetches=0, live_network_smoke="not_evaluated", source_kind="offline_artifact_replay"))
    write(folder / "initial-snapshots.json", snapshots)
    (folder / "offline-rss.xml").write_bytes(rss)
    print("PASS: first real Persona after actual local material observation; two raw snapshots, zero interactions/visits")


if __name__ == "__main__":
    main()
