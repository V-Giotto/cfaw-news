"""Offline non-synthetic package-document pilot; no external network or user DB."""

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

import feedparser
from cfaw_news.config import Settings
from cfaw_news.database import Article
from cfaw_news.ingestion import article_row
from cfaw_news.intelligence.contracts import SourcePolicy
from cfaw_news.intelligence.document_store import add_coverage, capture_version
from cfaw_news.intelligence.persistence_migrate import maintain
from cfaw_news.main import create_app

from audit.g4.pr6.freeze import ROOT, sha, write
from evals.intelligence_g4.tests.persistence_support import LocalClient, preconditions, wait_run

SAMPLES = ROOT / "audit/g4/pr6/samples/vite-8.3.4"
SOURCE_ID = "offline-vite-distribution-readme"
SOURCE_URL = "https://www.npmjs.com/package/vite/v/8.3.4"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def freeze_sample():
    package = ROOT / "frontend/node_modules/vite"
    if SAMPLES.exists():
        for name in ("README.md", "LICENSE.md", "package.json"):
            assert sha(package / name) == sha(SAMPLES / name)
        return json.loads((SAMPLES / "PROVENANCE.json").read_text(encoding="utf-8"))
    SAMPLES.mkdir(parents=True)
    for name in ("README.md", "LICENSE.md", "package.json"):
        shutil.copyfile(package / name, SAMPLES / name)
    metadata = json.loads((package / "package.json").read_text(encoding="utf-8"))
    assert metadata["version"] == "8.3.4" and metadata["license"] == "MIT"
    lock = json.loads((ROOT / "frontend/package-lock.json").read_text(encoding="utf-8"))
    provenance = dict(record_origin="real", material="unmodified historical installed Vite release README",
        package_version=metadata["version"], source_url=SOURCE_URL, repository=metadata["repository"],
        observed_locally_at=now(), published_at=None, publication_time_status="not_known_not_invented",
        rights="MIT", rights_basis="bundled LICENSE.md core license covers associated documentation",
        rights_notice="complete bundled license retained; no statement of independent legal audit",
        lock_entry=lock["packages"]["node_modules/vite"], lock_sha256=sha(ROOT / "frontend/package-lock.json"),
        local_input_sha256={name: sha(SAMPLES / name) for name in ("README.md", "LICENSE.md", "package.json")},
        source_authenticity="local installed artifact + lock integrity metadata; remote signature not reverified",
        container="authored local RSS replay envelope; text is unmodified real material, not synthetic",
        live_network_smoke="not_evaluated", external_fetches=0)
    write(SAMPLES / "PROVENANCE.json", provenance)
    return provenance


def config(folder, port):
    root = folder / "project"
    (root / "data").mkdir(parents=True, exist_ok=True)
    catalog = dict(id=SOURCE_ID, label="Vite 8.3.4 离线发行包 · MIT", kind="rss", category="other",
        language="en", primary=True, enabled=False, url=SOURCE_URL)
    write(root / "data/sources.json", dict(sources=[catalog]))
    return Settings(_env_file=None, root=root, database_url="sqlite:///" + (folder / "pilot.db").as_posix(),
        intelligence_anchor=folder / "anchor.json", intelligence_enabled=True, llm_mode="baseline",
        news_auto_refresh=False, news_reading_fetch=False, news_media_fetch=False,
        intelligence_origins=(f"http://127.0.0.1:{port}",))


def row_and_policy():
    text = (SAMPLES / "README.md").read_text(encoding="utf-8")
    rss = ('<?xml version="1.0"?><rss version="2.0"><channel><title>Offline packaged document replay</title>'
        '<item><title>Vite 8.3.4 packaged README · MIT</title><link>' + SOURCE_URL
        + '</link><description>' + escape(text) + '</description></item></channel></rss>').encode()
    parsed = feedparser.parse(rss)
    assert not parsed.bozo and len(parsed.entries) == 1
    entry = parsed.entries[0]
    assert entry.summary == text.strip(), "RSS parsing may only trim outer whitespace"
    text = entry.summary
    row = article_row(dict(id=SOURCE_ID, label="Vite 8.3.4 离线发行包 · MIT"), SOURCE_URL,
        entry.title, text, [dict(id=f"p{i + 1}", text=part, kind="rss_body")
                            for i, part in enumerate(text.split("\n\n")) if part], None,
        coverage_note="离线真实发行包 README；保留 MIT 许可。RSS 容器为测试重放，未联网抓取，未独立验证主张。")
    policy = SourcePolicy(source_id=SOURCE_ID, source_url=SOURCE_URL, source_label=row["source"],
        source_role="official", record_origin="real", rights="permitted", allowed_use=("metadata", "excerpt", "fulltext"),
        max_excerpt_chars=16000, rights_evidence_uri=SOURCE_URL)
    return row, policy, rss


def prepare(folder, port):
    assert not folder.exists()
    provenance = freeze_sample()
    settings = config(folder, port)
    maintain(folder / "pilot.db", folder / "anchor.json", "upgrade")
    app = create_app(settings)
    row, policy, rss = row_and_policy()
    (folder / "offline-rss.xml").write_bytes(rss)
    write(folder / "source-policy.json", policy.model_dump(mode="json"))
    with LocalClient(app, base_url=f"http://127.0.0.1:{port}", headers={"Origin": f"http://127.0.0.1:{port}"}) as client:
        persona = client.post("/api/intelligence/persona", json=dict(**preconditions(client), idempotency_key="pilot-persona",
            expected_persona_version=0, domain_interests=["Vite build tooling"], attention_budget_seconds=420))
        assert persona.status_code == 201, persona.text
        observed = now()
        with app.state.database.session.begin() as session:
            session.add(Article(id=row["id"], origin="feed", content_hash=row["content_hash"], data=row))
            first = capture_version(session, row, policy, observed_at=observed, available_at=observed)
        with app.state.database.session.begin() as session:
            repeated_at = now()
            second = capture_version(session, row, policy, observed_at=repeated_at, available_at=repeated_at)
            assert second.doc_version_id == first.doc_version_id
            add_coverage(session, SOURCE_ID, repeated_at, repeated_at, repeated_at, "covered",
                         "bounded_parse")
        status = client.get("/api/intelligence/status").json()
        start = client.post("/api/intelligence/briefings", json=dict(**preconditions(client),
            idempotency_key="pilot-run", expected_latest_version=status["head"]["publication_version"],
            persona_version_id=status["head"]["persona_version_id"], runtime_policy_sha256=status["runtime_policy_sha256"],
            algorithm="b4", profile="focus70-radar30-v1"))
        assert start.status_code == 202, start.text
        run = wait_run(client, start.json()["resource_id"])
        assert run["status"] == "completed", run
        response = client.get("/api/intelligence/briefings/latest")
        assert response.status_code == 200, response.text
        briefing = response.json()
        assert briefing["mode"] == "real" and briefing["evidence_status"] == "raw_news_only"
        assert briefing["deliveries"] == [] and briefing["archive"] and briefing["coverage"]["has_gap"]
        detail = client.get("/api/intelligence/events/detail", params=dict(briefing_id=briefing["id"],
            event_snapshot_id=briefing["archive"][0]["event_snapshot_id"])).json()
        assert all(d["record_origin"] == "real" for d in detail["documents"])
        assert detail["documents"][0]["content"]["paragraphs"][0] == row["paragraphs"][0]["text"]
        for name, value in dict(run=run, briefing=briefing, detail=detail, document=first.model_dump(mode="json")).items():
            write(folder / (name + ".json"), value)
        write(folder / "result.json", dict(status="PASS_OFFLINE_REJECTION_PATH", record_origin="real", provenance=provenance,
            duplicate_same_version=True, briefing_id=briefing["id"], article_id=row["id"], rights="MIT",
            observed_at=observed, source_kind="offline_artifact_replay", external_fetches=0,
            text_transform="outer whitespace trim + original blank-line paragraph boundaries; complete original separately pinned",
            coverage_interpretation="bounded local replay point; not a live site poll or continuous coverage",
            live_network_smoke="not_evaluated", qualified_focus_radar=False))
    app.state.database.engine.dispose()
    print(json.dumps(dict(status="PASS_OFFLINE_REJECTION_PATH", briefing_id=briefing["id"], material_sha256=sha(SAMPLES / "README.md"))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8136)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--qa-delay", type=float, default=0, help="Bounded test-only native entry delay, seconds")
    args = parser.parse_args()
    folder = args.out.resolve()
    assert folder.is_relative_to(ROOT / ".tmp")
    if not args.serve:
        prepare(folder, args.port)
        return
    settings = config(folder, args.port)
    shutil.copytree(ROOT / "frontend/dist", settings.root / "frontend/dist", dirs_exist_ok=True)
    (settings.root / "frontend/public").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "frontend/public/icon.svg", settings.root / "frontend/public/icon.svg")
    import uvicorn
    app = create_app(settings)
    if args.qa_delay:
        assert 0 < args.qa_delay <= 3
        import time
        native = app.state.intelligence.runtime
        def delayed(*call_args, **call_kwargs):
            time.sleep(args.qa_delay)
            return native(*call_args, **call_kwargs)
        app.state.intelligence.runtime = delayed
    print("Serving PR6 isolated real-material pilot; all automatic fetches disabled", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
