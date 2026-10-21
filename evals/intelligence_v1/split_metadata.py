"""Pure split/lineage checks shared by trusted loading and full validation.

Only document identity, family, availability, upstream IDs, persona identity and
step metadata are inspected. No text, preferences, references, gold or I/O.
The loader supplies metadata projections, never the future document bodies.
"""

from collections import defaultdict

from .exceptions import ContractError


def split_metadata_issues(documents, family_splits, personas, steps):
    """Yield (record, error) so the full validator can retain source locations."""
    document_families, identity_splits = {}, {}
    by_document = defaultdict(list)
    for document in documents:
        by_document[document.document_id].append(document)
        if document.family_id not in family_splits:
            yield document, ContractError("FAMILY_NOT_FOUND")
        family = document_families.setdefault(document.document_id, document.family_id)
        if family != document.family_id:
            yield document, ContractError("CROSS_FAMILY_SPLIT")
        split = family_splits.get(document.family_id)
        for kind, value in (("url", document.canonical_url), ("sha", document.content_sha256)):
            if value is not None:
                previous = identity_splits.setdefault((kind, value), split)
                if previous != split:
                    yield document, ContractError("CROSS_FAMILY_SPLIT")
    for document in documents:
        if document.upstream_document_id is None:
            continue
        parents = by_document.get(document.upstream_document_id, ())
        if not parents:
            yield document, ContractError("REFERENCE_NOT_FOUND")
        elif any(p.family_id != document.family_id for p in parents):
            yield document, ContractError("CROSS_FAMILY_SPLIT")
        elif not any(p.available_at <= document.available_at for p in parents):
            yield document, ContractError("FUTURE_EVIDENCE")
    persona_versions = {p.persona_version_id: p for p in personas}
    timeline_splits, persona_splits = {}, {}
    for step in steps:
        for family_id in step.family_scope_ids:
            if family_id not in family_splits:
                yield step, ContractError("FAMILY_NOT_FOUND")
            elif family_splits[family_id] != step.split:
                yield step, ContractError("CROSS_FAMILY_SPLIT")
        previous = timeline_splits.setdefault(step.timeline_id, step.split)
        if previous != step.split:
            yield step, ContractError("CROSS_FAMILY_SPLIT")
        persona = persona_versions.get(step.persona_version_id)
        if persona is None:
            yield step, ContractError("REFERENCE_NOT_FOUND", field="persona_version_id")
        else:
            previous = persona_splits.setdefault(persona.persona_id, step.split)
            if previous != step.split:
                yield step, ContractError("CROSS_FAMILY_SPLIT")
