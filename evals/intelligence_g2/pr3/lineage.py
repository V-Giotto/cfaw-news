"""Dependency is evidence-backed; absence of upstream never proves independence."""

import re

from evals.intelligence_g2.validate_output import preflight_time

from .contracts import CoverageGap, LineageResult, SourceLineage, digest, fail


def build_source_lineage(*, replay_input, grouping_result, config):
    preflight_time(replay_input)
    del config
    docs = {d.candidate.doc_version_id: d.candidate for d in replay_input.visible_documents}
    documents = {d.document_id for d in docs.values()}
    parents = {key: key for key in docs}
    kinds = {}

    def root(key):
        while parents[key] != key:
            key = parents[key]
        return key

    for pair in grouping_result.relations:
        if pair.predicted_relation not in {"exact_duplicate", "syndicated"}:
            continue
        left, right = root(pair.left_doc_version_id), root(pair.right_doc_version_id)
        parents[max(left, right)] = min(left, right)
        for key in (pair.left_doc_version_id, pair.right_doc_version_id):
            kinds[key] = "duplicate" if pair.predicted_relation == "exact_duplicate" else "copy"
    by_document = {d.document_id: d for d in docs.values()}
    for key, doc in docs.items():
        upstream = by_document.get(doc.upstream_document_id)
        if not upstream:
            continue
        text = "\n".join(p.text for p in doc.paragraphs)
        original = "\n".join(p.text for p in upstream.paragraphs)
        # An explicit reprint prefix plus an exact copied visible body establishes
        # dependency even if conservative PR2 left the documents in separate events.
        copied = re.sub(r"^\s*(?:reprint|repost|转载)\s*:\s*", "", text, count=1, flags=re.I)
        if copied != text and copied == original and original:
            left, right = root(key), root(upstream.doc_version_id)
            parents[max(left, right)] = min(left, right)
            kinds[key] = "copy"
    groups = {}
    for key in docs:
        groups.setdefault(root(key), []).append(key)
    gaps, sources = [], []
    for key, doc in sorted(docs.items()):
        upstream = doc.upstream_document_id
        if upstream == doc.document_id:
            fail("G2_PR3_LINEAGE_INVALID", "lineage", "upstream_document_id", key)
        resolved = upstream in documents if upstream else False
        if upstream and not resolved:
            gaps.append(CoverageGap(code="upstream_unresolved", source_id=doc.source_id, doc_version_id=key))
        edge = kinds.get(key, "cites" if upstream and resolved else "unknown")
        members = sorted(groups[root(key)])
        sources.append(SourceLineage(doc_version_id=key, source_id=doc.source_id,
            upstream_document_id=upstream, edge_kind=edge,
            dependency_group_key="g2:dependency:" + digest(members),
            independence="dependent" if len(members) > 1 else "unknown",
            upstream_resolved=resolved, basis=("validated_pr2_" + edge,) if key in kinds else ("visible_metadata",)))
    return LineageResult(sources=tuple(sources), coverage_gaps=tuple(gaps))
