"""PR2 authored synthetic/mocked capture cases. No real network or user database."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path

import pytest
from cfaw_news.database import Article, ArticleReading, Database, SourceState
from cfaw_news.ingestion import NewsIngestor
from cfaw_news.intelligence.contracts import (
    CoverageWindow,
    G4DocumentVersion,
    LedgerError,
    SourcePolicy,
    canonical,
    instant,
    safe_url,
)
from cfaw_news.intelligence.document_store import (
    DocumentLedger,
    capture_version,
    enabled,
    read_version,
)
from cfaw_news.intelligence.migrate import maintain
from cfaw_news.intelligence.models import G4Capture, G4Coverage, G4Document, G4Version
from cfaw_news.intelligence.source_policy import policy_for
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

ROOT = Path(__file__).resolve().parents[3]
T0, T1, T2, T3 = (instant(f"2026-01-01T0{n}:00:00Z") for n in range(4))
SOURCE = dict(id="test", label="Authored source", url="https://example.test/feed", kind="rss")


@pytest.fixture
def ledger_db(tmp_path):
    path = tmp_path / "capture.db"
    db = Database("sqlite:///" + path.as_posix())
    db.create()
    db.engine.dispose()
    maintain(path, "upgrade", backup=tmp_path / "before.db")
    yield db
    db.engine.dispose()


def policy(rights="synthetic", **kwargs):
    data = dict(source_id="test", source_url=SOURCE["url"], source_label=SOURCE["label"],
                record_origin="synthetic" if rights == "synthetic" else "real", rights=rights)
    if rights not in {"unknown", "metadata_only"}:
        data.update(allowed_use=("metadata", "excerpt"), max_excerpt_chars=160,
                    rights_evidence_uri="https://example.test/authored-policy")
    return SourcePolicy(**{**data, **kwargs})


def article(title="Authored A"):
    return dict(id="test:article", source_id="test", source_url="https://example.test/post?id=1",
                title=title, summary="Authored test excerpt", paragraphs=[dict(text="Test body")],
                published_at="2020-01-01T00:00:00Z", content_hash="legacy-not-evidence")


def write(db, row=None, stamp=T1, rights="synthetic"):
    with db.session.begin() as session:
        return capture_version(session, article() if row is None else row, policy(rights),
                               observed_at=stamp, available_at=stamp)


def versions(db):
    with db.session() as session:
        return [read_version(v) for v in session.scalars(select(G4Version).order_by(
            G4Version.sequence))]


def test_linear_versions_immutable_idempotent_and_content_return(ledger_db):
    a = write(ledger_db)
    assert write(ledger_db, stamp=T2) == a
    b = write(ledger_db, article("Authored B"), stamp=T3)
    c = write(ledger_db, stamp=instant("2026-01-01T04:00:00Z"))
    assert [v.sequence for v in versions(ledger_db)] == [1, 2, 3]
    assert b.supersedes_version_id == a.doc_version_id
    assert c.supersedes_version_id == b.doc_version_id
    assert c.payload_sha256 == a.payload_sha256 and c.doc_version_id != a.doc_version_id
    assert versions(ledger_db)[0] == a


@pytest.mark.parametrize("same_hash", [True, False])
def test_out_of_order_and_equal_time_change_rejected(ledger_db, same_hash):
    original = write(ledger_db, stamp=T2)
    with pytest.raises(LedgerError, match="G4_CAPTURE_OUT_OF_ORDER"):
        write(ledger_db, article() if same_hash else article("Older arrival"), stamp=T1)
    with pytest.raises(LedgerError, match="G4_CAPTURE_OUT_OF_ORDER"):
        write(ledger_db, article("Equal timestamp different body"), stamp=T2)
    assert versions(ledger_db) == [original]


def test_duplicate_capture_replay_and_conflicting_receipt(ledger_db):
    ledger = DocumentLedger(ROOT)
    with ledger_db.session.begin() as session:
        a = ledger.record_poll(session, SOURCE, [article()], started_at=T0, observed_at=T1,
                               available_at=T1)
    with ledger_db.session.begin() as session:
        assert ledger.record_poll(session, SOURCE, [article()], started_at=T0, observed_at=T1,
                                  available_at=T1) == a
    with pytest.raises(LedgerError, match="G4_CAPTURE_ID_CONFLICT"):
        with ledger_db.session.begin() as session:
            ledger.record_poll(session, SOURCE, [article("conflict")], started_at=T0,
                               observed_at=T1, available_at=T1)
    with ledger_db.session() as session:
        assert len(list(session.scalars(select(G4Capture)))) == 1


@pytest.mark.parametrize("rights", ["unknown", "metadata_only"])
def test_unknown_rights_stores_only_safe_metadata_and_digest(ledger_db, rights):
    row = article("FORBIDDEN publisher title")
    row["summary"] = "FORBIDDEN summary"
    row["paragraphs"] = [dict(text="FORBIDDEN body")]
    row["_reading"] = dict(text="FORBIDDEN reading cache")
    v = write(ledger_db, row, rights=rights)
    assert "FORBIDDEN" not in v.model_dump_json()
    assert v.retention == "metadata_only" and v.content.title == SOURCE["label"]
    assert v.content.text_excerpt is None and v.content.paragraphs == ()
    assert v.published_at < v.observed_at == v.available_at


def test_excerpt_allowance_bound_and_controlled_provenance(ledger_db):
    row = article("t" * 500)
    row["summary"] = "q" * 10000
    with ledger_db.session.begin() as session:
        v = capture_version(session, row, policy("excerpt_only"), observed_at=T1, available_at=T1)
    assert len(v.content.title) + len(v.content.text_excerpt or "") + sum(
        map(len, v.content.paragraphs)) <= 160
    assert v.retention == "excerpt" and v.provenance_uri == SOURCE["url"]


def test_policy_never_inferred_from_rss_or_body_flag(tmp_path):
    p = policy_for({**SOURCE, "body_is_full": True}, tmp_path / "absent.json")
    assert p.rights == "unknown" and p.allowed_use == ("metadata",)
    with pytest.raises((ValueError, LedgerError)):
        SourcePolicy(**{**p.model_dump(), "allowed_use": ("metadata", "fulltext")})
    with pytest.raises((ValueError, LedgerError)):
        policy("permitted", rights_evidence_uri=None)
    registry = tmp_path / "registry.json"
    registry.write_bytes(canonical(dict(schema_revision="g4-source-registry-v1",
                                       sources=[policy().model_dump(mode="json")])))
    with pytest.raises(LedgerError, match="G4_POLICY_SOURCE_MISMATCH"):
        policy_for(SOURCE, registry)


def test_concurrent_writers_cannot_fork(ledger_db):
    def same():
        return write(ledger_db).doc_version_id
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(lambda _: same(), range(2)))
    assert ids[0] == ids[1] and len(versions(ledger_db)) == 1


def test_transaction_failure_leaves_no_partial_evidence(ledger_db):
    with pytest.raises(RuntimeError, match="simulated loss"):
        with ledger_db.session.begin() as session:
            capture_version(session, article(), policy(), observed_at=T1, available_at=T1)
            raise RuntimeError("simulated loss")
    with ledger_db.session() as session:
        for table in (G4Document, G4Version, G4Capture, G4Coverage):
            assert list(session.scalars(select(table))) == []
        assert session.execute(text("SELECT count(*) FROM g4_source_policies")).scalar() == 0


@pytest.mark.parametrize("table", ["g4_document_versions", "g4_source_policies"])
@pytest.mark.parametrize("operation", ["UPDATE", "DELETE"])
def test_sql_immutability_guards(ledger_db, table, operation):
    write(ledger_db)
    query = (f"UPDATE {table} SET data='{{}}'" if operation == "UPDATE" else f"DELETE FROM {table}")
    with pytest.raises(IntegrityError, match="G4_IMMUTABLE_RECORD"):
        with ledger_db.session.begin() as session:
            session.execute(text(query))


def test_sql_fork_and_head_rollback_rejected(ledger_db):
    a = write(ledger_db)
    b = write(ledger_db, article("B"), stamp=T2)
    with pytest.raises(IntegrityError, match="G4_DOCUMENT_HEAD_INVALID"):
        with ledger_db.session.begin() as session:
            session.execute(text("UPDATE g4_documents SET head_version_id=:v"),
                            dict(v=a.doc_version_id))
    with pytest.raises(IntegrityError, match="G4_DOCUMENT_CHAIN_INVALID"):
        with ledger_db.session.begin() as session:
            row = session.get(G4Version, b.doc_version_id)
            data = {c.name: getattr(row, c.name) for c in row.__table__.columns}
            data.update(doc_version_id="forged-fork", sequence=3, supersedes_version_id=a.doc_version_id,
                        observed_at=T3)
            session.add(G4Version(**data))
            session.flush()


def test_coverage_gaps_failures_and_304_do_not_fill_intervals(ledger_db):
    ledger = DocumentLedger(ROOT)
    observations = [(T0, T1, [article()], False), (T2, T2, None, False), (T3, T3, None, True)]
    for start, now, rows, failed in observations:
        with ledger_db.session.begin() as session:
            ledger.record_poll(session, SOURCE, rows, started_at=start, observed_at=now,
                               available_at=now, failed=failed)
    with ledger_db.session() as session:
        cov = [CoverageWindow.model_validate_json(canonical(c.data)) for c in session.scalars(
            select(G4Coverage))]
    assert {c.status for c in cov} == {"partial", "covered", "failed", "unknown"}
    assert all(c.start_at == c.end_at for c in cov if c.status in {"covered", "partial"})
    assert any(c.start_at == T1 and c.end_at == T2 and c.status == "unknown" for c in cov)


def test_unanchored_304_and_service_downtime_are_conservative(ledger_db):
    ledger = DocumentLedger(ROOT)
    with ledger_db.session.begin() as session:
        ledger.record_poll(session, SOURCE, None, started_at=T0, observed_at=T0, available_at=T0)
        ledger.service_event(session, [SOURCE], "started", T0)
        ledger.service_event(session, [SOURCE], "stopped", T1)
        ledger.service_event(session, [SOURCE], "started", T2)
        ledger.service_event(session, [SOURCE], "started", T3)
    with ledger_db.session() as session:
        rows = list(session.scalars(select(G4Coverage)))
        assert any(c.start_at == T1 and c.end_at == T2 and c.status == "service_offline" for c in rows)
        assert any(c.start_at == T2 and c.end_at == T3 and c.status == "unknown" for c in rows)
        assert all(c.status not in {"covered", "partial"} for c in rows)


def test_new_json_gate_rejects_mutated_hash_and_continuous_coverage(ledger_db):
    v = write(ledger_db)
    data = v.model_dump(mode="json")
    data["content"]["title"] = "altered"
    with pytest.raises(ValueError, match="G4_CAPTURE_HASH_MISMATCH"):
        G4DocumentVersion.model_validate_json(canonical(data))
    with pytest.raises(ValueError, match="G4_COVERAGE_CONTINUITY_UNPROVEN"):
        CoverageWindow(coverage_window_id="test", source_id="test", start_at=T0,
                       end_at=T1, observed_at=T1, status="covered", reason_code="conditional_confirmed")


def test_url_identity_and_secret_rejection():
    assert safe_url("https://example.test/read?article=1") != safe_url(
        "https://example.test/read?article=2")
    for url in ("https://user:secret@example.test/a", "https://example.test/a?token=secret"):
        with pytest.raises(LedgerError):
            safe_url(url)


def test_unmigrated_legacy_db_still_works(tmp_path):
    db = Database("sqlite:///" + (tmp_path / "legacy.db").as_posix())
    db.create()
    with db.session() as session:
        assert not enabled(session)
    db.engine.dispose()


def ingestor(db):
    news = NewsIngestor(db, ROOT)
    news.sources["test"] = SOURCE
    news.locks["test"] = asyncio.Lock()
    return news


def test_ingestor_confirmed_write_and_failure_are_atomic(ledger_db, monkeypatch):
    news = ingestor(ledger_db)
    row = article()
    row.update(captured_at="2026-01-01T00:00:00Z", origin="feed")
    row["_reading"] = dict(text="Reader cache must not enter G4")
    async def read(*_):
        return [deepcopy(row)], {"etag": "test"}
    monkeypatch.setattr(news, "read", read)
    first = asyncio.run(news.one(None, "test"))
    assert first["status"] == "ok"
    with ledger_db.session() as session:
        assert session.get(Article, row["id"])
        assert session.get(ArticleReading, row["id"])
        assert session.get(SourceState, "test").data["status"] == "ok"
    assert "Reader cache" not in versions(ledger_db)[0].model_dump_json()
    before = versions(ledger_db)
    async def fail(*_):
        raise ValueError("authored source failure")
    monkeypatch.setattr(news, "read", fail)
    assert asyncio.run(news.one(None, "test"))["status"] == "error"
    assert versions(ledger_db) == before
    with ledger_db.session() as session:
        assert any(c.status == "failed" for c in session.scalars(select(G4Coverage)))


def test_article_write_failure_rolls_back_capture_and_reading(ledger_db, monkeypatch):
    news = ingestor(ledger_db)
    row = article()
    row.update(captured_at=T0, origin="feed", _reading=dict(text="cached"))
    async def read(*_):
        return [deepcopy(row)], {}
    monkeypatch.setattr(news, "read", read)
    original = news.write_state
    def fail(session, source_id, state):
        if state["status"] == "ok":
            raise ValueError("transaction fault after body/ledger writes")
        return original(session, source_id, state)
    monkeypatch.setattr(news, "write_state", fail)
    assert asyncio.run(news.one(None, "test"))["status"] == "error"
    with ledger_db.session() as session:
        assert session.get(Article, row["id"]) is None
        assert session.get(ArticleReading, row["id"]) is None
        assert list(session.scalars(select(G4Version))) == []
        assert [r.data["outcome"] for r in session.scalars(select(G4Capture))] == ["failed"]


def test_legacy_etag_cannot_bootstrap_g4_body(ledger_db, monkeypatch):
    news = ingestor(ledger_db)
    news.save_state("test", dict(status="ok", validators={"etag": "legacy"}))
    seen = []
    async def read(client, source, state):
        seen.append(state)
        return None, {}
    monkeypatch.setattr(news, "read", read)
    assert asyncio.run(news.one(None, "test"))["status"] == "ok"
    assert seen[0]["validators"] == {}
    with ledger_db.session() as session:
        assert list(session.scalars(select(G4Version))) == []
        assert all(c.status == "unknown" for c in session.scalars(select(G4Coverage)))


def test_future_and_reversed_capture_times_rejected_before_rows(ledger_db):
    with pytest.raises(LedgerError, match="G4_CAPTURE_INVALID_TIME"):
        write(ledger_db, stamp="2099-01-01T00:00:00Z")
    with pytest.raises(LedgerError, match="G4_CAPTURE_INVALID_TIME"):
        with ledger_db.session.begin() as s:
            capture_version(s, article(), policy(), observed_at=T2, available_at=T1)
    assert versions(ledger_db) == []


def test_real_parser_write_path_304_and_correction_with_mocked_response(ledger_db, monkeypatch):
    news = ingestor(ledger_db)
    responses = [b'''<rss version="2.0"><channel><item><title>Authored A</title>
        <link>https://example.test/post/1</link><description>Authored summary</description>
        </item></channel></rss>''', None, b'''<rss version="2.0"><channel><item>
        <title>Authored correction B</title><link>https://example.test/post/1</link>
        <description>Authored corrected summary</description></item></channel></rss>''']
    headers_seen = []
    async def fetch(client, url, allowed_hosts, headers=None):
        headers_seen.append(headers)
        return responses.pop(0), {"etag": "authored"}
    monkeypatch.setattr("cfaw_news.ingestion.fetch_document", fetch)
    for _ in range(3):
        assert asyncio.run(news.one(None, "test"))["status"] == "ok"
    assert len(versions(ledger_db)) == 2
    assert headers_seen[1] == {"If-None-Match": "authored"}
    with ledger_db.session() as s:
        captures = list(s.scalars(select(G4Capture).order_by(G4Capture.observed_at)))
        assert [c.data["outcome"] for c in captures] == ["success", "not_modified", "success"]
        assert any(c.status == "covered" for c in s.scalars(select(G4Coverage)))


def test_start_close_and_restart_write_service_offline_gap(ledger_db):
    news = ingestor(ledger_db)
    async def never_poll():
        await asyncio.Event().wait()
    news.poll = never_poll
    async def run():
        news.start()
        await news.close()
        news.start()
        await news.close()
    asyncio.run(run())
    with ledger_db.session() as s:
        cov = list(s.scalars(select(G4Coverage)))
        assert cov and all(c.status == "service_offline" for c in cov)


def test_same_display_metadata_still_versions_changed_unknown_payload(ledger_db):
    a = write(ledger_db, rights="unknown")
    b = write(ledger_db, article("Different forbidden publisher text"), T2, "unknown")
    assert a.content == b.content and a.content_sha256 == b.content_sha256
    assert a.payload_sha256 != b.payload_sha256 and a.doc_version_id != b.doc_version_id
