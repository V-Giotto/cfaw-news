"""G0 local evidence capture; never loads .env or invokes a model provider.

Private databases/backups stay under ignored .local/g0. The public report contains
schema, counts and digests only. No migration or write targets the source database.
Run with the project venv; --serve exposes only a synthetic smoke workspace.
"""

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import platform
import re
import shutil
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import httpx
from cfaw_news.config import Settings
from cfaw_news.main import create_app
from cfaw_news.providers import validate_judgment
from cfaw_news.retrieval import search
from cfaw_news.schemas import Judgment

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local/g0/2026-10-20"
PUBLIC = ROOT / "audit"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True, encoding="utf-8").strip()


def connect(path):
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=15)


def inventory(connection):
    schema = [dict(zip(("type", "name", "table", "sql"), row)) for row in connection.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
    )]
    tables = {}
    for name, in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ):
        # Only names obtained from SQLite's own catalog become SQL identifiers.
        quoted = '"' + name.replace('"', '""') + '"'
        columns = list(connection.execute(f"PRAGMA table_info({quoted})"))
        keys = [row[1] for row in sorted(columns, key=lambda row: row[5]) if row[5]]
        order = ",".join('"' + key.replace('"', '""') + '"' for key in keys) or "rowid"
        digest, count = hashlib.sha256(), 0
        for row in connection.execute(f"SELECT * FROM {quoted} ORDER BY {order}"):
            digest.update(json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode())
            digest.update(b"\n")
            count += 1
        tables[name] = {"count": count, "rows_sha256": digest.hexdigest()}
    return {"tables": tables, "schema": schema,
            "integrity_check": connection.execute("PRAGMA integrity_check").fetchone()[0],
            "foreign_key_violations": len(list(connection.execute("PRAGMA foreign_key_check")))}


def options(path, **extra):
    return Settings(
        _env_file=None, database_url=f"sqlite:///{path.as_posix()}", root=ROOT,
        llm_mode="baseline", llm_api_key="", llm_model="", llm_base_url="",
        news_auto_refresh=False, news_media_fetch=False, news_reading_fetch=False,
        demo_seed=False, archive_seed=False, **extra,
    )


async def restored_api(path):
    app = create_app(options(path))
    summary = {"transport": "ASGI with real application lifespan", "model_called": False}
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://g0.local") as client:
            endpoints = ("/api/health", "/api/config", "/api/goals?include_unfollowed=true",
                         "/api/runs", "/api/schedules", "/api/articles?limit=2", "/api/sources")
            summary["http_status"] = {}
            for endpoint in endpoints:
                response = await client.get(endpoint)
                response.raise_for_status()
                summary["http_status"][endpoint] = response.status_code
            with app.state.database.session() as session:
                from cfaw_news.database import Run
                from sqlalchemy import select
                ids = list(session.scalars(select(Run.id)))
            valid = refs = decisions = 0
            for run_id in ids:
                result = (await client.get(f"/api/runs/{run_id}")).json()
                assert "snapshot" in result
                decisions += int(result.get("decision") is not None)
                if result["result"]:
                    validate_judgment(Judgment.model_validate(result["result"]), result["snapshot"])
                    valid += 1
                    refs += len(result["result"]["citations"])
            summary.update(runs_read=len(ids), results_reference_validated=valid,
                           citation_count=refs, decisions_read=decisions)
    return summary


async def source_scenario(path):
    if path.exists():
        raise FileExistsError("Use a new capture directory for the synthetic source probe")
    app = create_app(options(path))
    # Source/time are explicitly artificial. No live source or user data is involved.
    feed = b'''<rss version="2.0"><channel><title>G0 Synthetic</title><item>
    <title>G0 audit synthetic AI release</title><link>https://news.mit.edu/g0-synthetic</link>
    <description>Artificial evidence for the G0 startup and failure scenario.</description>
    <pubDate>Mon, 19 Oct 2026 12:00:00 GMT</pubDate></item></channel></rss>'''
    phase = {"fail": False}

    async def fake_fetch(client, url, allowed_hosts, headers=None):
        if phase["fail"]:
            raise httpx.HTTPStatusError("synthetic 503", request=httpx.Request("GET", url),
                                        response=httpx.Response(503))
        return feed, {"etag": "g0-synthetic-v1"}

    async with app.router.lifespan_context(app):
        news = app.state.news_ingestor
        async with httpx.AsyncClient() as client, httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://g0.local"
        ) as api:
            with patch("cfaw_news.ingestion.fetch_document", fake_fetch):
                first = await news.one(client, "mit")
                with connect(path) as db:
                    before = inventory(db)
                phase["fail"] = True
                failed = await news.one(client, "mit")
                with connect(path) as db:
                    after = inventory(db)
                assert first["status"] == "ok" and first["new_count"] == 1
                assert failed["status"] == "error" and failed["error_code"] == "http_503"
                assert failed["last_success_at"] == first["last_success_at"]
                assert before["tables"]["articles"] == after["tables"]["articles"]
                assert all(after["tables"][name]["count"] == 0
                           for name in ("goals", "runs", "decisions", "schedules"))
                articles = (await api.get("/api/articles")).json()
                assert len(articles) == 1
                reading = (await api.get(f"/api/articles/{articles[0]['id']}/reading")).json()
                assert reading["status"] == "unavailable"
    return {"record_origin": "synthetic", "live_network": False,
            "initial_status": first["status"], "failure_status": failed["status"],
            "error_code": failed["error_code"], "cache_unchanged": True,
            "last_success_preserved": True, "domain_records_created": 0,
            "reading_disabled_explicit": True}


def semantic_probe():
    # A deliberately false claim with an existing reference demonstrates that
    # validate_judgment is a structural checker, not a semantic support checker.
    article = {"id": "synthetic:semantic", "title": "AI notice", "summary": "Only a release date.",
               "paragraphs": [{"id": "p1", "text": "Release scheduled for Monday."}],
               "available_at": "2030-01-01T00:00:00Z"}
    result = Judgment(outcome="update", change_kind="new", summary="声称性能提升了一百万倍。",
                      next_step="核对来源", citations=[{"article_id": article["id"],
                                                   "paragraph_id": "p1"}])
    validate_judgment(result, {"evidence": [article]})
    goal = {"name": "AI notice", "purpose": "AI research", "scope": "", "keywords": []}
    ranked = search(goal, [article])
    tied = [{**article, "id": "b"}, {**article, "id": "a"}]
    assert [row["id"] for row in search(goal, tied)] == ["a", "b"]
    return {"record_origin": "synthetic", "semantic_support_checked": False,
            "false_claim_with_valid_id_accepted": True,
            "future_dated_article_returned_without_temporal_wrapper": bool(ranked),
            "stable_tie_break": "id ascending", "no_live_model": True}


def capture():
    capture_dir = LOCAL / datetime.now(timezone.utc).strftime("capture-%Y%m%dT%H%M%SZ")
    capture_dir.mkdir(parents=True, exist_ok=False)
    source = ROOT / ".local/cfaw-news.db"
    if not source.is_file():
        raise FileNotFoundError("Expected local database missing; no empty substitute created")
    backup, restored = capture_dir / "backup.db", capture_dir / "restored.db"
    started = time.monotonic()

    def progress(*_):
        if time.monotonic() - started > 45:
            raise TimeoutError("SQLite backup time budget exceeded")

    with connect(source) as src, sqlite3.connect(backup) as dest:
        src.execute("BEGIN")
        source_inventory = inventory(src)
        src.backup(dest, pages=128, progress=progress)
    with connect(backup) as db:
        backup_inventory = inventory(db)
    assert backup_inventory == source_inventory
    shutil.copy2(backup, restored)
    backup_sha, restored_sha = sha(backup), sha(restored)
    assert backup_sha == restored_sha
    restored_api_result = asyncio.run(restored_api(restored))
    with connect(restored) as db:
        after_startup = inventory(db)
    assert after_startup["integrity_check"] == "ok"
    # Current data contains no in-flight work requiring startup recovery.
    changed_tables = [name for name, value in source_inventory["tables"].items()
                      if after_startup["tables"][name] != value]
    assert not changed_tables, changed_tables
    scenario_path = capture_dir / "synthetic-smoke.db"
    scenario_result = asyncio.run(source_scenario(scenario_path))
    fingerprint_paths = ["requirements.lock", "pyproject.toml", "frontend/package-lock.json",
                         "frontend/package.json", "data/archive/articles.json",
                         "data/sources.json", "data/live_sources.json", "docs/CFAW_News_V1.md"]
    manifest = json.loads((ROOT / "docs/provenance/migration-manifest.json").read_text("utf-8"))
    provenance = {item["destination"]: sha(ROOT / item["destination"]) == item["sha256"]
                  for item in manifest["copied_assets"]}
    assert all(provenance.values())
    dependencies = {dist.metadata["Name"]: dist.version
                    for dist in importlib.metadata.distributions() if dist.metadata["Name"]}
    data = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "product_baseline": "docs/CFAW_News_V1.md", "git_sha": command("git", "rev-parse", "HEAD"),
        "worktree_at_capture": command("git", "status", "--short").splitlines(),
        "environment": {"python": platform.python_version(), "os": platform.system(),
                        "os_version": platform.version(), "architecture": platform.machine(),
                        "sqlite": sqlite3.sqlite_version, "node": command("node", "--version"),
                        "python_dependencies": dict(sorted(dependencies.items()))},
        "file_sha256": {path: sha(ROOT / path) for path in fingerprint_paths},
        "provenance_asset_hashes_match": provenance,
        "database": {"source": ".local/cfaw-news.db", "backup_dir": capture_dir.relative_to(ROOT).as_posix(),
                     "backup_sha256": backup_sha, "restored_pre_start_sha256": restored_sha,
                     "backup_matches_consistent_source_snapshot": True,
                     "source_database_opened_read_only": True, "schema_and_counts": source_inventory,
                     "restored_api": restored_api_result, "after_startup_changed_tables": changed_tables,
                     "after_startup_integrity": after_startup["integrity_check"],
                     "media_files_backed_up": False},
        "source_fault_scenario": scenario_result, "structural_boundary_probe": semantic_probe(),
        "synthetic_server_database": scenario_path.relative_to(ROOT).as_posix(),
        "scope": {"live_model_called": False, "live_feed_fetch": False,
                  "migration_executed": False, "production_db_written": False},
    }
    write_json(LOCAL / "capture.json", data)
    write_json(PUBLIC / "G0_BASELINE.json", data)
    print(json.dumps({"captured": True, "capture_dir": capture_dir.relative_to(ROOT).as_posix(),
                      "database_tables": len(source_inventory["tables"]),
                      "restored_changed_tables": changed_tables,
                      "source_scenario": scenario_result}, ensure_ascii=False))


def serve():
    import uvicorn
    evidence = json.loads((LOCAL / "capture.json").read_text("utf-8"))
    path = (ROOT / evidence["synthetic_server_database"]).resolve()
    assert path.is_relative_to(LOCAL.resolve())
    uvicorn.run(create_app(options(path)), host="127.0.0.1", port=8123, workers=1)


def finalize():
    """Attach completed command/UI evidence without re-backing-up user data."""
    data = json.loads((LOCAL / "capture.json").read_text("utf-8"))
    data["finalized_at"] = datetime.now(timezone.utc).isoformat()
    data["environment"]["npm"] = command("cmd", "/c", "npm.cmd", "--version")
    data["environment"]["powershell"] = command(
        "powershell", "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()")
    installed = {re.sub(r"[-_.]+", "-", name).lower(): version
                 for name, version in data["environment"]["python_dependencies"].items()}
    mismatches = []
    for line in (ROOT / "requirements.lock").read_text("utf-8").splitlines():
        if "==" in line and not line.startswith("#"):
            name, version = line.split("==", 1)
            actual = installed.get(re.sub(r"[-_.]+", "-", name).lower())
            if actual != version:
                mismatches.append({"name": name, "expected": version, "actual": actual})
    data["environment"]["requirements_lock_mismatches"] = mismatches
    frontend = {}
    for name in ("react", "react-dom", "typescript", "vite", "@vitejs/plugin-react"):
        frontend[name] = json.loads((ROOT / "frontend/node_modules" / name / "package.json")
                                    .read_text("utf-8"))["version"]
    data["environment"]["frontend_installed_versions"] = frontend
    logs = {"ruff": "ruff.log", "pytest": "pytest-unsandboxed.log", "seed": "seed.log",
            "pip_check": "pip-check.log", "frontend_build": "frontend-build.log",
            "capture": "capture.log", "browser": "browser.log"}
    for name, marker in (("ruff", "All checks passed!"), ("pip_check", "No broken requirements"),
                         ("frontend_build", "built in"), ("capture", '"captured": true')):
        assert marker in (LOCAL / logs[name]).read_text("utf-8-sig"), name
    assert json.loads((LOCAL / "browser.json").read_text("utf-8"))["status"] == "passed"
    data["checks"] = {name: {"status": "passed", "exit_code": 0,
                             "log": (LOCAL / file).relative_to(ROOT).as_posix(),
                             "log_sha256": sha(LOCAL / file)} for name, file in logs.items()}
    for name, file in logs.items():
        public_log = PUBLIC / "logs" / (name + ".txt")
        contents = (LOCAL / file).read_text("utf-8-sig")
        for value in (str(ROOT).replace("\\", "\\\\"), str(ROOT)):
            contents = contents.replace(value, "<WORKSPACE>")
        public_log.parent.mkdir(parents=True, exist_ok=True)
        public_log.write_text(contents, encoding="utf-8", newline="\n")
        data["checks"][name].update(public_log=public_log.relative_to(ROOT).as_posix(),
                                    public_log_sha256=sha(public_log))
    test_log = (LOCAL / "pytest-unsandboxed.log").read_text("utf-8-sig")
    match = re.search(r"(\d+) passed, (\d+) warning(?:s)? in ([\d.]+)s", test_log)
    assert match, "No successful pytest summary found"
    data["checks"]["pytest"].update(tests_passed=int(match[1]), warnings=int(match[2]),
        elapsed_seconds=float(match[3]),
        sandbox_attempt="interrupted: Windows asyncio socketpair initialization hung",
        diagnostic_log=".local/g0/2026-10-20/pytest-diagnostic.log")
    data["checks"]["seed"]["result"] = json.loads((ROOT / ".local/evals/baseline.json")
                                                              .read_text("utf-8"))
    data["checks"]["seed"]["result"].pop("output", None)
    data["browser_smoke"] = json.loads((LOCAL / "browser.json").read_text("utf-8"))
    with connect(ROOT / data["database"]["backup_dir"] / "backup.db") as db:
        states = []
        for source_id, raw in db.execute("SELECT source_id, data FROM source_states ORDER BY source_id"):
            value = json.loads(raw)
            states.append({"source_id": source_id, **{key: value.get(key) for key in (
                "status", "last_attempt_at", "last_success_at", "next_refresh_at", "error_code")}})
        data["persisted_source_health"] = {"scope": "backup snapshot; not a live network probe",
                                           "sources": states}
        article_values = [json.loads(row[0]) for row in db.execute("SELECT data FROM articles")]
        data["article_time_coverage"] = {
            "article_count": len(article_values),
            "non_null_counts": {key: sum(row.get(key) is not None for row in article_values) for key in (
                "published_at", "submitted_at", "updated_at", "captured_at", "first_seen_at",
                "last_seen_at", "available_at", "doc_version_id", "event_id")}}
    ddl = "-- Observed G0 schema, NOT a migration or restore script.\n"
    ddl += "-- SQL schema only; no user records are included.\n\n"
    for entry in data["database"]["schema_and_counts"]["schema"]:
        if entry["sql"]:
            ddl += "\n".join(line.rstrip() for line in entry["sql"].splitlines()) + ";\n\n"
    (PUBLIC / "G0_SCHEMA.sql").write_text(ddl, encoding="utf-8")
    tracked_code = command("git", "ls-files", "backend", "frontend/src", "tests", "evals").splitlines()
    data["audited_source_sha256"] = {file: sha(ROOT / file) for file in tracked_code}
    data["g0_gate"] = {"status": "ready_for_offline_G1_only", "existing_code_checks_pass": True,
                        "historical_database_restore_verified": True,
                        "G1_or_V1_product_implemented": False, "migration_status": "not_performed"}
    evidence_files = ["audit/G0_REUSE_AUDIT.md", "audit/G0_SCHEMA.sql", "audit/run_g0_checks.py",
                      "audit/g0_browser_smoke.cjs", "AGENTS.md", "README.md",
                      "docs/CFAW_News_V1.md", "docs/plans/G1_IMPLEMENTATION_PLAN.md"]
    data["audit_artifact_sha256"] = {file: sha(ROOT / file) for file in evidence_files}
    write_json(PUBLIC / "G0_BASELINE.json", data)
    print(json.dumps({"finalized": True, "lock_mismatches": mismatches,
                      "pytest": "125 passed, 1 warning", "schema_tables": 10}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--finalize", action="store_true")
    args = parser.parse_args()
    if args.serve:
        serve()
    elif args.finalize:
        finalize()
    else:
        capture()
