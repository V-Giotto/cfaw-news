import json
from pathlib import Path

import pytest
from conftest import BASE, append_evidence_document, read_rows, refresh, write_rows

from evals.intelligence_v1.contracts import DocumentVersion, SourceRegistry
from evals.intelligence_v1.exceptions import ContractError, DatasetValidationError
from evals.intelligence_v1.hashing import content_sha256
from evals.intelligence_v1.provenance import check_document, controlled_path
from evals.intelligence_v1.validate import validate_dataset


def test_T26_synthetic_not_counted_as_real_news(bundle):
    report = validate_dataset(refresh(bundle))
    docs = read_rows(bundle, "documents.jsonl")
    assert all(x["record_origin"] == "synthetic" for x in docs)
    registry = json.loads((bundle / "manifests/source_registry.json").read_bytes())
    real = registry["sources"][1]
    assert real["redistribution_rights"] == "unknown"
    assert real["checked_at"] is None and real["allowed_use"] == ["metadata"]
    assert "real_provenance_and_license_review" in report.pending


def real_metadata(bundle):
    raw = read_rows(bundle, "documents.jsonl")[0]
    raw.update(source_id="github-blog", source_type="official", record_origin="real",
               canonical_url="https://github.blog/feed/", provenance_uri="https://github.blog/feed/",
               content_kind="feed_summary", redistribution_rights="unknown", paragraphs=[],
               text_excerpt=None, content_sha256=None)
    return DocumentVersion.model_validate_json(json.dumps(raw))


def sources(bundle):
    registry = SourceRegistry.model_validate_json((bundle / "manifests/source_registry.json").read_bytes())
    return {s.source_id: s for s in registry.sources}


def test_T26_unknown_rights_can_keep_only_metadata(bundle):
    doc = real_metadata(bundle)
    check_document(doc, sources(bundle), bundle, set())
    assert doc.paragraphs == () and doc.content_sha256 is None


def test_excerpt_permission_requires_limit_and_cannot_be_broadened(bundle):
    doc = real_metadata(bundle)
    registry = sources(bundle)
    original = registry["github-blog"]
    excerpt_source = original.model_copy(update={
        "redistribution_rights": "excerpt_only", "allowed_use": ("metadata", "excerpt"),
        "restrictions": original.restrictions.model_copy(update={"max_excerpt_chars": 10}),
    })
    registry["github-blog"] = excerpt_source
    excerpt = doc.model_copy(update={"redistribution_rights": "excerpt_only",
                                     "content_kind": "quoted_excerpt", "text_excerpt": "short"})
    excerpt = excerpt.model_copy(update={"content_sha256": content_sha256(
        excerpt.title, excerpt.text_excerpt, excerpt.paragraphs)})
    check_document(excerpt, registry, bundle, set())
    with pytest.raises(ContractError, match="RIGHTS_USE_NOT_ALLOWED"):
        check_document(excerpt.model_copy(update={"redistribution_rights": "permitted"}),
                       registry, bundle, set())
    for limit in (None, 2):
        registry["github-blog"] = excerpt_source.model_copy(update={
            "restrictions": original.restrictions.model_copy(update={"max_excerpt_chars": limit})
        })
        with pytest.raises(ContractError, match="RIGHTS_USE_NOT_ALLOWED"):
            check_document(excerpt, registry, bundle, set())


@pytest.mark.parametrize("url", ["synthetic://fake/real", "http://github.blog/feed/",
                                "https://forged.invalid/a", "https://other.org/a",
                                "https://user:password@github.blog/feed/"])
def test_T26_invalid_or_mismatched_real_links_rejected(bundle, url):
    doc = real_metadata(bundle).model_copy(update={"canonical_url": url})
    with pytest.raises(ContractError, match="PROVENANCE_INVALID"):
        check_document(doc, sources(bundle), bundle, set())


@pytest.mark.parametrize("relative", ["../outside", "/absolute", "C:/file", ".env", ".local/a",
                                     "dev-diaries/a", "a\\b", "a/../b", "a.db", "./a",
                                     ".ENV", ".LOCAL/a", "DEV-DIARIES/a"])
def test_no_escaping_sensitive_or_database_manifest_paths(bundle, relative):
    with pytest.raises(ContractError, match="MANIFEST_PATH_INVALID"):
        controlled_path(bundle, relative)


def test_symlink_outside_bundle_rejected_if_supported(bundle, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    link = bundle / "outside-link.md"
    try:
        link.symlink_to(outside)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable: {error.winerror if hasattr(error, 'winerror') else ''}")
    with pytest.raises(ContractError, match="MANIFEST_PATH_INVALID"):
        controlled_path(bundle, "outside-link.md")


def test_resolved_path_escape_rejected_without_symlink_privilege(bundle, monkeypatch):
    original = Path.resolve

    def resolve(path, *args, **kwargs):
        if path == bundle / "outside-link.md":
            return bundle.parent / "outside.md"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    with pytest.raises(ContractError, match="MANIFEST_PATH_INVALID"):
        controlled_path(bundle, "outside-link.md")


def test_references_and_origins_are_validated_separately_from_semantics(bundle):
    # A located quotation is not an automated assertion of semantic support.
    claims = read_rows(bundle, "claims.jsonl")
    claims[0]["claim_text"] = "This intentionally unsupported sentence is a schema probe."
    write_rows(bundle, "claims.jsonl", claims)
    report = validate_dataset(refresh(bundle))
    assert report.ok and "claim_semantic_support" in report.pending
    assert not any("semantic_support_passed" in k for k in report.to_dict())


@pytest.mark.parametrize("holder", ["claims", "gold"])
@pytest.mark.parametrize("owner_origin", ["real", "synthetic"])
@pytest.mark.parametrize("cross_origin", [False, True], ids=["same-origin", "cross-origin"])
def test_T26_evidence_origin_matches_claim_or_gold(bundle, holder, owner_origin, cross_origin):
    real_document = append_evidence_document(bundle, origin="real", family_id="family:agent-x")
    synthetic_document = read_rows(bundle, "documents.jsonl")[0]
    owner_document = real_document if owner_origin == "real" else synthetic_document
    other_document = synthetic_document if owner_origin == "real" else real_document
    events = read_rows(bundle, "events.jsonl")
    events.append({**events[0], "event_id": "event:origin-probe", "record_origin": owner_origin,
                   "provenance_uri": owner_document["provenance_uri"],
                   "document_version_ids": [owner_document["doc_version_id"]]})
    write_rows(bundle, "events.jsonl", events)
    rows = read_rows(bundle, holder + ".jsonl")
    record = {**rows[0], "event_id": "event:origin-probe", "record_origin": owner_origin,
              "provenance_uri": owner_document["provenance_uri"]}
    field = "evidence_refs" if holder == "claims" else "supporting_doc_version_ids"

    def refs(document):
        if holder == "gold":
            return [document["doc_version_id"]]
        return [dict(doc_version_id=document["doc_version_id"],
                     paragraph_id="p1" if document["paragraphs"] else None, direction="mentions")]

    if holder == "claims":
        record["claim_id"] = "claim:origin-probe"
    record[field] = refs(owner_document)
    rows.append(record)
    write_rows(bundle, holder + ".jsonl", rows)
    assert validate_dataset(refresh(bundle)).ok  # The control has a valid, same-origin chain.
    if not cross_origin:
        return
    rows[-1][field] = refs(other_document)
    write_rows(bundle, holder + ".jsonl", rows)
    manifest = refresh(bundle)
    report = validate_dataset(manifest, strict=False)
    assert not report.ok, "mixed-origin evidence was accepted as a homogeneous record"
    assert [(x.code, x.path, x.record_id, x.field) for x in report.errors] == [
        ("ORIGIN_MISMATCH", BASE + holder + ".jsonl",
         "claim:origin-probe" if holder == "claims" else record["timeline_id"], field)
    ]
    with pytest.raises(DatasetValidationError) as caught:
        validate_dataset(manifest)
    assert caught.value.report.to_dict() == report.to_dict()
