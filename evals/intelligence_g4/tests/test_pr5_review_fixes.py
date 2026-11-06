"""PR5 closure: native two-step history and immutable projection read compatibility."""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from cfaw_news.intelligence.persistence_models import BriefingSnapshot
from cfaw_news.intelligence.publication import latest_assessments, read_snapshot

from .persistence_support import LocalClient, capture, save_persona, setup_app, start, wait_run

SCOPE = " Task: summarization; Dataset: ToySet; Baseline: Base v1.0; Protocol: P1; Hardware: CPU; Conditions: batch=1;"
FIRST = "Atlas Tool v1.0 claims a speed gain of 40%." + SCOPE
CHANGES = {
    "superseded": "Atlas Tool v1.0 correction: the previous speed gain of 40% is corrected to 4%." + SCOPE,
    "retracted": "Atlas Tool v1.0 withdraws our previous speed gain of 40% claim." + SCOPE,
}


@pytest.mark.parametrize("lifecycle", CHANGES)
def test_native_detail_history_is_snapshot_relative(tmp_path, lifecycle):
    app, clock, _, _ = setup_app(tmp_path, mode="synthetic_development")
    with LocalClient(app, base_url="http://127.0.0.1:8000", headers={"Origin": "http://127.0.0.1:8000"}) as client:
        assert save_persona(client).status_code == 201
        snapshots, details = [], []
        for index, body in enumerate((FIRST, CHANGES[lifecycle])):
            capture(app, clock, origin="synthetic", body=body)
            response = start(client, key="native-history-" + str(index))
            assert response.status_code == 202, response.text
            finished = wait_run(client, response.json()["resource_id"])
            assert finished["status"] == "completed", finished
            snapshot = client.get("/api/intelligence/briefings/latest").json()
            snapshots.append(snapshot)
            detail = client.get("/api/intelligence/events/detail", params=dict(briefing_id=snapshot["id"],
                event_snapshot_id=snapshot["archive"][0]["event_snapshot_id"]))
            assert detail.status_code == 200, detail.text
            details.append(detail.json())
        key = details[0]["claims"][0]["claim_key"]
        old_state = next(a for a in details[0]["assessments"] if a["claim_key"] == key)
        new_state = next(a for a in details[1]["assessments"] if a["claim_key"] == key)
        assert old_state["lifecycle"] == "current"
        assert new_state["lifecycle"] == lifecycle
        assert len([a for a in details[1]["assessments"] if a["claim_key"] == key]) == 1
        old_again = client.get("/api/intelligence/events/detail", params=dict(briefing_id=snapshots[0]["id"],
            event_snapshot_id=snapshots[0]["archive"][0]["event_snapshot_id"])).json()
        assert old_again == details[0]
        with app.state.intelligence.store.read() as (session, _):
            row = session.get(BriefingSnapshot, snapshots[1]["id"])
            history = row.runtime["stages"][-1]["evidence"]["next_state"]["assessments"]
            assert len([a for a in history if a["claim_key"] == key]) >= 2
            # The complete appended history also resolves correctly against the old cutoff.
            assert next(a for a in latest_assessments(history, snapshots[0]["as_of"])
                        if a["claim_key"] == key)["lifecycle"] == "current"


def test_legacy_delivery_projection_hydrates_without_mutation(tmp_path):
    app, clock, _, _ = setup_app(tmp_path, mode="synthetic_development")
    with LocalClient(app, base_url="http://127.0.0.1:8000", headers={"Origin": "http://127.0.0.1:8000"}) as client:
        save_persona(client)
        capture(app, clock, origin="synthetic")
        response = start(client)
        assert wait_run(client, response.json()["resource_id"])["status"] == "completed"
        snapshot = client.get("/api/intelligence/briefings/latest").json()
        with app.state.intelligence.store.read() as (session, _):
            row = session.get(BriefingSnapshot, snapshot["id"])
            legacy = deepcopy(row.data)
            for delivery in legacy["deliveries"]:
                for name in ("projection", "content_refs", "omitted_refs"):
                    delivery.pop(name)
            before = deepcopy(legacy)
            view = read_snapshot(SimpleNamespace(data=legacy, runtime=row.runtime, runtime_sha256=row.runtime_sha256))
            assert legacy == before
            assert view.etag != legacy["etag"]
            for delivery in view.deliveries:
                planned = next(p for p in row.runtime["plan"]["events"] if p["event_key"] == delivery.event_key)
                assert delivery.projection == planned["chosen_projection"]
                assert list(delivery.content_refs) == planned["content_refs"]
                assert delivery.estimated_reading_seconds == planned["estimated_read_seconds"]
        assert client.get("/api/intelligence/briefings/latest").json() == snapshot
