"""Authored ledger material. Real-mode shapes are mocks, never live-source validation."""

from cfaw_news.intelligence.contracts import (
    G4DocumentVersion,
    SourcePolicy,
    digest,
    instant,
)
from cfaw_news.intelligence.runtime_contracts import RuntimeEnvelope

from evals.intelligence_g2.contracts import json_bytes

OLD, NOW, END = (instant(t) for t in ("2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z",
                                     "2026-01-03T00:00:00Z"))


def version(policy, *, body="Atlas Tool releases local agent tooling.", title="Atlas Tool v1 release",
            article="atlas", previous=None, observed=NOW):
    content = dict(title=title if policy.rights not in {"unknown", "metadata_only"} else
                   policy.source_label, text_excerpt=None,
                   paragraphs=[body] if body and policy.rights not in {"unknown", "metadata_only"} else [])
    source_pin = digest(policy.model_dump(mode="json"))
    document_id = "g4doc:" + digest([policy.source_id, "https://example.com/" + article])
    payload = digest([title, body])
    content_pin = digest(content)
    predecessor = previous.doc_version_id if previous else None
    doc_id = "g4ver:" + digest([document_id, predecessor, observed, observed, payload,
                               content_pin, source_pin])
    return G4DocumentVersion.model_validate_json(json_bytes(dict(document_id=document_id,
        doc_version_id=doc_id, source_id=policy.source_id, source_policy_sha256=source_pin,
        source_article_id="authored:" + article, canonical_url="https://example.com/" + article,
        content_kind="synthetic_text" if policy.record_origin == "synthetic" else "feed_summary",
        rights=policy.rights, record_origin=policy.record_origin, provenance="confirmed_feed_capture",
        provenance_uri=policy.source_url, observed_at=observed, available_at=observed,
        published_at=OLD, content_sha256=content_pin, payload_sha256=payload,
        supersedes_version_id=predecessor, sequence=previous.sequence + 1 if previous else 1,
        retention="metadata_only" if policy.rights in {"unknown", "metadata_only"} else "excerpt",
        content=content)))


def source(origin="synthetic", rights=None, source_id="official"):
    rights = rights or ("synthetic" if origin == "synthetic" else "excerpt_only")
    return SourcePolicy(source_id=source_id, source_url="https://example.com/feed/" + source_id,
        source_label="Authored source", source_role="official", record_origin=origin, rights=rights,
        allowed_use=("metadata",) if rights in {"unknown", "metadata_only"} else
        ("metadata", "excerpt", "fulltext") if rights == "synthetic" else ("metadata", "excerpt"),
        max_excerpt_chars=None if rights in {"unknown", "metadata_only"} else 16000,
        rights_evidence_uri=None if rights in {"unknown", "metadata_only"} else
        "https://example.test/authored-test-policy")


def envelope(origin="synthetic", *, rights=None, body="Atlas Tool releases local agent tooling."):
    policy = source(origin, rights)
    value = dict(record_origin=origin, stream_id="authored-runtime", as_of=END,
        time_window_start=OLD, time_window_end=END,
        persona=dict(persona=dict(persona_id="local", persona_version_id="local:v1",
            available_at=OLD, persona_origin="constructed" if origin == "synthetic" else "consented_real",
            domain_interests=["agent tooling"], current_goals=[], hard_constraints=[], knowledge_known=[],
            attention_budget_seconds=420, exploration_preference="off", locale="und"),
            record_origin=origin, provenance_uri="synthetic://authored-persona" if origin == "synthetic"
            else "https://example.test/consented-test-persona"),
        versions=[version(policy, body=body).model_dump(mode="json")],
        sources=[policy.model_dump(mode="json")], coverage=[],
        config=dict(budget=dict(profile="focus70-radar30-v1")))
    if origin == "synthetic":
        value["synthetic_provenance_uri"] = "evals/intelligence_g4/tests/runtime_support.py"
    return value


def wire(value):
    from evals.intelligence_v1.hashing import sha256_bytes
    model = RuntimeEnvelope.model_validate_json(json_bytes(value))
    raw = json_bytes(model)
    return raw, sha256_bytes(raw)
