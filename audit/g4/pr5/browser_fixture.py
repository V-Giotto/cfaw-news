"""Isolated authored API fixture and local server for PR5 browser checks.

No user DB/env, live sources, or network. Real-mode raw output uses the actual
API; qualified-card paths are separately tested with explicitly authored HTTP mocks.
"""

import argparse
import json
import shutil
from pathlib import Path

from evals.intelligence_g4.tests.persistence_support import (
    LocalClient,
    capture,
    save_persona,
    setup_app,
    start,
    wait_run,
)

ROOT = Path(__file__).resolve().parents[3]


def native_history(folder, lifecycle):
    from evals.intelligence_g4.tests.test_pr5_review_fixes import CHANGES, FIRST
    app, clock, _, _ = setup_app(folder, mode="synthetic_development")
    snapshots = []
    with LocalClient(app, base_url="http://127.0.0.1:8000", headers={"Origin": "http://127.0.0.1:8000"}) as client:
        save_persona(client)
        for i, body in enumerate((FIRST, CHANGES[lifecycle])):
            capture(app, clock, origin="synthetic", body=body)
            response = start(client, key="history-" + str(i))
            assert wait_run(client, response.json()["resource_id"])["status"] == "completed"
            briefing = client.get("/api/intelligence/briefings/latest").json()
            snapshots.append(dict(briefing=briefing, status=client.get("/api/intelligence/status").json(),
                persona=client.get("/api/intelligence/persona").json(), interactions=[],
                detail=client.get("/api/intelligence/events/detail", params=dict(briefing_id=briefing["id"],
                    event_snapshot_id=briefing["archive"][0]["event_snapshot_id"])).json()))
    return dict(old=snapshots[0], changed=snapshots[1])


def fixture(folder, mode):
    app, clock, _, _ = setup_app(folder, mode=mode)
    with LocalClient(app, base_url="http://127.0.0.1:8000", headers={"Origin": "http://127.0.0.1:8000"}) as client:
        assert save_persona(client).status_code == 201
        capture(app, clock, origin="real" if mode == "real" else "synthetic")
        response = start(client)
        assert response.status_code == 202, response.text
        assert wait_run(client, response.json()["resource_id"])["status"] == "completed"
        briefing = client.get("/api/intelligence/briefings/latest").json()
        event = briefing["archive"][0]
        return dict(briefing=briefing, status=client.get("/api/intelligence/status").json(),
            persona=client.get("/api/intelligence/persona").json(),
            interactions=client.get("/api/intelligence/interactions").json(),
            detail=client.get("/api/intelligence/events/detail", params=dict(briefing_id=briefing["id"],
                event_snapshot_id=event["event_snapshot_id"])).json())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=8135)
    args = parser.parse_args()
    folder = args.out.resolve()
    if not folder.is_relative_to(ROOT / ".tmp"):
        parser.error("isolated output must be under repository .tmp")
    folder.mkdir(parents=True, exist_ok=True)
    if not args.serve:
        result = dict(record_origin="authored_engineering_mock_not_real_news",
            real_raw=fixture(folder / "raw", "real"),
            synthetic=fixture(folder / "synthetic", "synthetic_development"),
            native_history={state: native_history(folder / state, state) for state in ("superseded", "retracted")})
        (folder / "fixtures.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        print("PASS: isolated PR4 API fixtures, no user data")
        return
    import uvicorn
    app, _, _, _ = setup_app(folder / "server")
    root = app.state.settings.root if hasattr(app.state, "settings") else folder / "server/project"
    shutil.copytree(ROOT / "frontend/dist", root / "frontend/dist")
    (root / "frontend/public").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "frontend/public/icon.svg", root / "frontend/public/icon.svg")
    # create_app chooses static mounts at construction. Recreate using the isolated Settings.
    from cfaw_news.config import Settings
    from cfaw_news.main import create_app
    config = Settings(_env_file=None, root=root,
        database_url="sqlite:///" + (folder / "server/app.db").as_posix(), llm_mode="baseline",
        news_auto_refresh=False, news_media_fetch=False, news_reading_fetch=False,
        intelligence_enabled=True, intelligence_anchor=folder / "server/app-anchor.json",
        intelligence_origins=(f"http://127.0.0.1:{args.port}",))
    app.state.database.engine.dispose()
    app = create_app(config)
    print("Serving isolated authored browser workspace", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
