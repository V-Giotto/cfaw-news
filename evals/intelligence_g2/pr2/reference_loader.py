"""Evaluation-only development references. Never import from prediction modules."""

from evals.intelligence_g2.contracts import PACKAGE, ROOT, parse, read_json
from evals.intelligence_g2.replay import safe_path
from evals.intelligence_v1.hashing import sha256_bytes

from .contracts import (
    ContinuityReference,
    ReferenceManifest,
    ReferencePair,
    checked_relative_path,
    fail,
)


def load_references(path, *, pin):
    path = safe_path(path, areas=(PACKAGE / "fixtures/pr2", ROOT / ".tmp"))
    raw = path.read_bytes()
    if sha256_bytes(raw) != pin:
        fail("MANIFEST_SHA_MISMATCH", "evaluation", "reference_manifest")
    manifest = parse(ReferenceManifest, read_json(raw), stage="evaluation")
    results = []
    for name, model in (("pairs", ReferencePair), ("continuity", ContinuityReference)):
        relative = checked_relative_path(getattr(manifest, name + "_path"))
        target = safe_path(path.parent / relative, areas=(path.parent,))
        content = target.read_bytes()
        if sha256_bytes(content) != getattr(manifest, name + "_sha256"):
            fail("SHA_MISMATCH", "evaluation", name)
        results.append(tuple(parse(model, read_json(line), stage="evaluation")
                             for line in content.splitlines()))
    pairs, continuity = results
    keys = set()
    for pair in pairs:
        key = (pair.timeline_id, pair.step_id, pair.left_doc_version_id, pair.right_doc_version_id)
        if (pair.left_doc_version_id >= pair.right_doc_version_id or key in keys
                or pair.evidence_at > pair.as_of):
            fail("G2_PR2_REFERENCE_CONFLICT", "evaluation", "reference_pairs", pair.case_id)
        keys.add(key)
    keys = [(c.timeline_id, c.from_step_id, c.to_step_id, c.from_doc_version_id,
             c.to_doc_version_id) for c in continuity]
    if len(keys) != len(set(keys)):
        fail("G2_PR2_REFERENCE_CONFLICT", "evaluation", "continuity")
    return manifest, pairs, continuity
