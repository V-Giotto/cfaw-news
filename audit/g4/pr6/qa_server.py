"""Managed loopback-only QA service with explicit effective config and stdin shutdown."""

import argparse
import shutil
import sys
import threading

import uvicorn
from cfaw_news.config import Settings
from cfaw_news.main import create_app

from audit.g4.pr5.browser_fixture import setup_app
from audit.g4.pr6.freeze import ROOT, sha
from audit.g4.pr6.pilot import config
from audit.g4.pr6.seal import write_new


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("contract", "pilot"), required=True)
    parser.add_argument("--folder", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--qa-delay", type=float, default=0)
    parser.add_argument("--config-out", required=True)
    args = parser.parse_args()
    folder = (ROOT / args.folder).resolve()
    assert folder.is_relative_to(ROOT / ".tmp") and 0 <= args.qa_delay <= 3
    if args.kind == "contract":
        app, _, _, _ = setup_app(folder / "server")
        app.state.database.engine.dispose()
        settings = Settings(_env_file=None, root=folder / "server/project",
            database_url="sqlite:///" + (folder / "server/app.db").as_posix(), llm_mode="baseline",
            news_auto_refresh=False, news_media_fetch=False, news_reading_fetch=False,
            intelligence_enabled=True, intelligence_anchor=folder / "server/app-anchor.json",
            intelligence_origins=(f"http://127.0.0.1:{args.port}", "http://127.0.0.1:5175"))
    else:
        settings = config(folder, args.port)
    served = settings.root / "frontend/dist"
    shutil.copytree(ROOT / "frontend/dist", served)
    (settings.root / "frontend/public").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "frontend/public/icon.svg", settings.root / "frontend/public/icon.svg")
    app = create_app(settings)
    if args.qa_delay:
        import time
        native = app.state.intelligence.runtime
        def delayed(*call_args, **call_kwargs):
            time.sleep(args.qa_delay)
            return native(*call_args, **call_kwargs)
        app.state.intelligence.runtime = delayed
    write_new(ROOT / args.config_out, dict(kind=args.kind, root=str(settings.root),
        database_url=settings.database_url, intelligence_anchor=str(settings.intelligence_anchor),
        intelligence_origins=list(settings.intelligence_origins), intelligence_enabled=True,
        llm_mode="baseline", news_auto_refresh=False, news_media_fetch=False, news_reading_fetch=False,
        host="127.0.0.1", port=args.port, qa_delay_seconds=args.qa_delay,
        source_catalog=str(settings.root / "data/sources.json"),
        served_build_sha256={p.relative_to(served).as_posix(): sha(p) for p in served.rglob("*") if p.is_file()}))
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=args.port, log_level="warning"))
    def stop():
        if sys.stdin.readline().strip() == "STOP":
            server.should_exit = True
    threading.Thread(target=stop, daemon=True).start()
    server.run()
    print("QA graceful service exit", flush=True)


if __name__ == "__main__":
    main()
