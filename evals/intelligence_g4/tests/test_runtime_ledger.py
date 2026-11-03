"""PR2 immutable rows are read as one as-of snapshot, never Article/Reading backfill."""

from datetime import datetime

import pytest
from cfaw_news.database import Database
from cfaw_news.intelligence.contracts import CoverageWindow
from cfaw_news.intelligence.document_store import capture_version
from cfaw_news.intelligence.migrate import maintain
from cfaw_news.intelligence.models import G4Coverage, G4SourcePolicy, G4Version
from cfaw_news.intelligence.runtime import from_ledger, run
from cfaw_news.intelligence.runtime_contracts import RuntimeEnvelope
from sqlalchemy import select

from evals.intelligence_g2.contracts import json_bytes

from .runtime_support import END, NOW, OLD, envelope, source


def test_actual_pr2_capture_projection_read_only_and_as_of(tmp_path):
    path = tmp_path / "runtime-ledger.db"
    maintain(path, "upgrade")
    db = Database("sqlite:///" + path.as_posix())
    policy = source("real")
    raw = envelope("real")
    seed = RuntimeEnvelope.model_validate_json(json_bytes(raw))
    row = dict(id="authored", source_id=policy.source_id, source_url="https://example.com/captured",
               title="Atlas Tool v1 release", summary="", paragraphs=[
                   dict(text="Atlas Tool releases local agent tooling.")], published_at=OLD)
    with db.session.begin() as session:
        first = capture_version(session, row, policy, observed_at=NOW, available_at=NOW)
        later = "2026-01-04T00:00:00.000000+00:00"
        capture_version(session, {**row, "title": "Atlas Tool v2 correction"}, policy,
                        observed_at=later, available_at=later)
    with db.session() as session:
        before = [v.record_sha256 for v in session.scalars(select(G4Version))]
        projected = from_ledger(session, stream_id="authored-db-runtime",
            as_of=datetime.fromisoformat(END), time_window_start=datetime.fromisoformat(OLD),
            persona=seed.persona, config=seed.config)
        assert [d.doc_version_id for d in projected.versions] == [first.doc_version_id]
        assert not session.new and not session.dirty and not session.deleted
        assert [v.record_sha256 for v in session.scalars(select(G4Version))] == before
    from evals.intelligence_v1.hashing import sha256_bytes
    payload = json_bytes(projected)
    result = run(payload, expected_sha256=sha256_bytes(payload))
    assert result.state == "raw_news_only" and result.ranking is None
    assert result.reason_codes == ("G4_NATIVE_G2_REJECTED:RIGHTS_USE_NOT_ALLOWED",)
    assert result.input.versions[0].content_kind == "feed_summary"
    assert result.stages == () and result.plan is None
    db.engine.dispose()


def test_no_network_or_provider_effects(monkeypatch):
    def forbid(*args, **kwargs):
        raise AssertionError("runtime attempted external effect")
    monkeypatch.setattr("socket.getaddrinfo", forbid)
    monkeypatch.setattr("httpx.Client.request", forbid)
    monkeypatch.setattr("httpx.AsyncClient.request", forbid)
    from .runtime_support import wire
    raw, pin = wire(envelope())
    assert run(raw, expected_sha256=pin).state == "plan_ready"


@pytest.mark.parametrize("status,reason", [("failed", "source_failed"),
    ("unknown", "unobserved_between_polls"), ("service_offline", "clean_service_downtime")])
def test_failure_offline_and_unknown_windows_never_become_covered(status, reason):
    from .runtime_support import wire
    value = envelope()
    value["coverage"] = [CoverageWindow(coverage_window_id="authored-gap", source_id="official",
        start_at=OLD, end_at=NOW, observed_at=NOW, status=status, reason_code=reason).model_dump(mode="json")]
    raw, pin = wire(value)
    result = run(raw, expected_sha256=pin)
    assert result.coverage.has_gap
    assert result.coverage.sources[0].status != "covered"
    assert result.plan.coverage.has_gap


def test_result_source_pointer_and_plan_content_refs_resolve():
    from .runtime_support import wire
    raw, pin = wire(envelope())
    result = run(raw, expected_sha256=pin)
    root = result.plan.input.model_dump(mode="json")
    for event in result.plan.events:
        for pointer in event.content_refs:
            node = root
            for part in pointer.lstrip("/").split("/"):
                node = node[int(part)] if isinstance(node, list) else node[part]
            assert node is not None


@pytest.mark.parametrize("kind", ["policy", "coverage"])
def test_ledger_column_payload_binding_rejects_corrupt_rows(tmp_path, kind):
    path = tmp_path / "corrupt-row.db"
    maintain(path, "upgrade")
    db = Database("sqlite:///" + path.as_posix())
    seed = RuntimeEnvelope.model_validate_json(json_bytes(envelope("real")))
    with db.session.begin() as session:
        if kind == "policy":
            session.add(G4SourcePolicy(policy_sha256="0" * 64, source_id="official", registered_at=NOW,
                                      data=source("real").model_dump(mode="json")))
        else:
            data = CoverageWindow(coverage_window_id="g4cov:wrong", source_id="official", start_at=NOW,
                end_at=NOW, observed_at=NOW, status="unknown", reason_code="unobserved_between_polls")
            session.add(G4Coverage(coverage_window_id=data.coverage_window_id,
                source_id="official", start_at=NOW, end_at=NOW, observed_at=NOW,
                status="unknown", capture_id=None, data=data.model_dump(mode="json")))
    with db.session() as session, pytest.raises(ValueError, match="G4_RUNTIME_LEDGER_"):
        from_ledger(session, stream_id="corrupt-test", as_of=datetime.fromisoformat(END),
            time_window_start=datetime.fromisoformat(OLD), persona=seed.persona, config=seed.config)
    db.engine.dispose()


def test_captured_coverage_projection_keeps_point_observation_and_unknown_remainder(tmp_path):
    from cfaw_news.intelligence.document_store import add_coverage, register_policy
    path = tmp_path / "covered-point.db"
    maintain(path, "upgrade")
    db = Database("sqlite:///" + path.as_posix())
    seed = RuntimeEnvelope.model_validate_json(json_bytes(envelope("real")))
    with db.session.begin() as session:
        register_policy(session, source("real"), NOW)
        add_coverage(session, "official", NOW, NOW, NOW, "covered", "bounded_parse")
    with db.session() as session:
        result = from_ledger(session, stream_id="point-test", as_of=datetime.fromisoformat(END),
            time_window_start=datetime.fromisoformat(OLD), persona=seed.persona, config=seed.config)
        assert len(result.coverage) == 1 and result.coverage[0].status == "covered"
    db.engine.dispose()
