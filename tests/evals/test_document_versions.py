from types import SimpleNamespace

import pytest

from evals.intelligence_v1.contracts import DocumentVersion
from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.temporal import parse_instant, project_candidate, visible_versions


def docs(bundle):
    return [DocumentVersion.model_validate_json(x)
            for x in next(bundle.rglob("documents.jsonl")).read_bytes().splitlines()]


def test_T03_returns_exact_old_text_sha_without_reading_future_payload(bundle):
    rows = docs(bundle)

    class FuturePayloadGuard:
        def __getattr__(self, key):
            if key in {"title", "text_excerpt", "paragraphs", "model_dump_json"}:
                pytest.fail("future payload was accessed")
            return getattr(rows[1], key)

    cutoff = parse_instant("2026-01-04T00:00:00Z")
    selected = visible_versions([rows[0], FuturePayloadGuard()], as_of=cutoff)
    assert selected == [rows[0]]
    candidate = project_candidate(selected[0], as_of=cutoff)
    assert candidate.paragraphs == rows[0].paragraphs
    assert candidate.content_sha256 == rows[0].content_sha256
    assert "CORRECTION_FUTURE_V2" not in candidate.model_dump_json()
    assert not {"family_id", "split", "event_id", "record_origin", "provenance_uri"} & {
        *type(candidate).model_fields
    }
    assert visible_versions(rows, as_of=rows[1].available_at)[0] == rows[1]


def test_version_selection_is_stable_and_source_filtered(bundle):
    rows = docs(bundle)
    cutoff = parse_instant("2026-10-20T00:00:00Z")
    assert visible_versions(rows, as_of=cutoff) == visible_versions(rows[::-1], as_of=cutoff)
    assert visible_versions(rows, as_of=cutoff, allowed_source_ids=frozenset()) == []


def meta(version, parent=None, *, document="doc", available=0, sha=None):
    return SimpleNamespace(doc_version_id=version, document_id=document,
                           supersedes_version_id=parent, available_at=available,
                           content_sha256=sha, source_id="source")


@pytest.mark.parametrize("rows,code", [
    ([meta("a", "missing")], "VERSION_CHAIN_INVALID"),
    ([meta("a"), meta("b", "a", document="other")], "VERSION_CHAIN_INVALID"),
    ([meta("a", available=2), meta("b", "a", available=1)], "VERSION_CHAIN_INVALID"),
    ([meta("a", "b"), meta("b", "a")], "VERSION_CHAIN_INVALID"),
    ([meta("a"), meta("b", "a"), meta("c", "a")], "VERSION_CONFLICT"),
    ([meta("a"), meta("b")], "VERSION_CONFLICT"),
    ([meta("a", sha="same"), meta("b", "a", sha="same")], "DUPLICATE_CONTENT_VERSION"),
    ([meta("a"), meta("a")], "DUPLICATE_ID"),
])
def test_VER01_invalid_chain_metadata(rows, code):
    from evals.intelligence_v1.temporal import version_chains

    with pytest.raises(ContractError, match=code):
        version_chains(rows)


def test_equal_time_explicit_linear_successor_wins(bundle):
    rows = docs(bundle)[:2]
    second = rows[1].model_copy(update={"available_at": rows[0].available_at})
    assert visible_versions([second, rows[0]], as_of=rows[0].available_at) == [second]
