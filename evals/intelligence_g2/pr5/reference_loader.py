"""Explicit development-reference reader, only imported by the independent evaluator."""

from evals.intelligence_g2.contracts import PACKAGE
from evals.intelligence_g2.replay import safe_path
from evals.intelligence_v1.hashing import sha256_bytes

from .assets import strict_json
from .contracts import fail


def load_reference(path, pin):
    root = PACKAGE / "fixtures/pr5/v1/reference"
    path = safe_path(path, areas=(root,), code="MANIFEST_PATH_INVALID")
    raw = path.read_bytes()
    if sha256_bytes(raw) != pin:
        fail("MANIFEST_SHA_MISMATCH", "evaluation", "reference_manifest")
    manifest = strict_json(raw)
    if (set(manifest) != {"revision", "path", "role", "sha256"}
            or manifest["revision"] != "g2-pr5-development-reference-v1"
            or manifest["path"] != "labels.json" or manifest["role"] != "reference"):
        fail("G2_PR5_REFERENCE_CONFLICT", "evaluation", "reference_manifest")
    raw = safe_path(path.parent / "labels.json", areas=(root,), code="MANIFEST_PATH_INVALID").read_bytes()
    if sha256_bytes(raw) != manifest["sha256"]:
        fail("SHA_MISMATCH", "evaluation", "reference")
    rows = strict_json(raw)
    if (rows.get("label_origin") != "synthetic_fixture" or rows.get("review_origin") != "ai_development"
            or rows.get("independent_validation") is not False or rows.get("non_blind") is not True):
        fail("G2_PR5_REFERENCE_CONFLICT", "evaluation", "provenance")
    return rows["cases"]
