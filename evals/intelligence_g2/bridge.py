"""The only G2 module allowed to hold a G1 PredictionBundle, never a reference dataset."""

from evals.intelligence_v1.contracts import CandidateDocumentVersion, DocumentVersion, ReplayContext
from evals.intelligence_v1.loader import load_bundle, load_step
from evals.intelligence_v1.provenance import check_document
from evals.intelligence_v1.temporal import require_visible_version, version_chains

from .contracts import (
    G2ReplayInput,
    G2SourcePolicy,
    G2VisibleDocument,
    IdentitySeed,
    VersionIdentity,
    data,
    digest,
    parse,
)
from .validate_output import checked_input, fail, unique


def project_step(bundle, *, manifest_sha256, timeline_id, step_id, config,
                 context=None, candidates=None):
    """Compare optional explicit projections with the pinned loader's authoritative projection."""
    if bundle.manifest.status != "frozen":
        fail("G2_INPUT_NOT_FROZEN", "bridge", "manifest.status")
    expected_context, expected_candidates = load_step(
        bundle, timeline_id=timeline_id, step_id=step_id, config=bundle.config)
    context = parse(ReplayContext, context if context is not None else expected_context,
                    stage="bridge")
    # Check the injected candidates' time before comparing IDs; no future payload is projected.
    supplied = expected_candidates if candidates is None else tuple(candidates)
    for candidate in supplied:
        require_visible_version(candidate, as_of=context.as_of)
    supplied = tuple(parse(CandidateDocumentVersion, d, stage="bridge") for d in supplied)
    by_id = unique(supplied, lambda d: d.doc_version_id, field="candidates")
    if set(by_id) != set(expected_context.candidate_doc_version_ids):
        fail("VISIBLE_SET_MISMATCH", "bridge", "candidate_doc_version_ids")
    if context != expected_context:
        fail("G2_CONTEXT_MISMATCH", "bridge", "context")
    for candidate in expected_candidates:
        if by_id[candidate.doc_version_id] != candidate:
            fail("G2_CONTEXT_MISMATCH", "bridge", "candidate", candidate.doc_version_id)
    # Only selected bodies are accessed; the raw bundle and paths stop at this function.
    raw_by_id = {r["doc_version_id"]: r for r in bundle.rows["documents"]}
    controlled = {e.path for e in bundle.manifest.file_hashes}
    visible, seeds = [], []
    for candidate in expected_candidates:
        version = parse(DocumentVersion, raw_by_id[candidate.doc_version_id], stage="bridge")
        check_document(version, bundle.sources, bundle.root, controlled)
        indexes = [d for d in bundle.documents if d.document_id == candidate.document_id
                   and d.available_at <= context.as_of]
        chain = version_chains(indexes)[candidate.document_id]
        lineage = tuple(parse(VersionIdentity,
            {name: data(index)[name] for name in VersionIdentity.model_fields}, stage="bridge")
            for index in chain)
        visible.append(G2VisibleDocument(candidate=candidate,
            record_origin=version.record_origin, redistribution_rights=version.redistribution_rights,
            provenance_uri=version.provenance_uri, visible_lineage=lineage))
        seeds.append(IdentitySeed(document_id=candidate.document_id,
            anchor_doc_version_id=chain[0].doc_version_id, first_visible_at=chain[0].available_at))
    sources = tuple(G2SourcePolicy(source_id=s.source_id, source_type=s.source_type,
        record_origin=s.record_origin, redistribution_rights=s.redistribution_rights,
        allowed_use=s.allowed_use, max_excerpt_chars=s.restrictions.max_excerpt_chars)
        for _, s in sorted(bundle.sources.items()))
    value = G2ReplayInput(dataset_id=bundle.manifest.dataset_id,
        dataset_revision=bundle.manifest.dataset_revision,
        input_manifest_sha256=manifest_sha256,
        context=context, visible_documents=tuple(visible), sources=sources,
        identity_seeds=tuple(seeds),
        source_coverage_digest=digest([data(w) for w in context.source_coverage]),
        pipeline_revision=config.pipeline_revision, config_sha256=digest(config))
    return checked_input(value, config)[0]


def load_replay_input(manifest_path, *, manifest_sha256, timeline_id, step_id, config):
    bundle = load_bundle(manifest_path, manifest_sha256=manifest_sha256)
    value = project_step(bundle, manifest_sha256=manifest_sha256.lower(),
                         timeline_id=timeline_id, step_id=step_id, config=config)
    metadata = {"g1_schema_revision": bundle.manifest.schema_revision,
        "runtime_source_sha256": {"evals/intelligence_v1/" + k: v
                                  for k, v in bundle.verified_hashes.items() if k.endswith(".py")}}
    metadata["runtime_source_sha256"]["backend/cfaw_news/retrieval.py"] = (
        bundle.config.retrieval_sha256)
    return value, metadata
