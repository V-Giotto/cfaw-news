"""Explicitly pinned development expectations; imported only by offline evaluation."""

from evals.intelligence_g2.contracts import PACKAGE, ROOT, read_json
from evals.intelligence_g2.replay import safe_path
from evals.intelligence_v1.hashing import sha256_bytes

from .contracts import fail


def load_reference(path, pin):
    path = safe_path(path, areas=(PACKAGE / "fixtures/pr4", ROOT / ".tmp"))
    raw = path.read_bytes()
    if sha256_bytes(raw) != pin:
        fail("MANIFEST_SHA_MISMATCH", "evaluation", "reference_manifest")
    manifest = read_json(raw)
    entries = manifest.get("files", ())
    if len(entries) != 1 or entries[0].get("role") != "reference" or entries[0].get("path") != "expectations.json":
        fail("G2_PR4_REFERENCE_CONFLICT", "evaluation", "reference_artifact")
    raw = safe_path(path.parent / "expectations.json", areas=(path.parent,)).read_bytes()
    if sha256_bytes(raw) != entries[0]["sha256"]:
        fail("SHA_MISMATCH", "evaluation", "reference_artifact")
    value = read_json(raw)
    if value.get("label_origin") != "synthetic_fixture" or value.get("review_origin") != "ai_development":
        fail("G2_PR4_REFERENCE_CONFLICT", "evaluation", "provenance")
    cases = value.get("cases", ())
    if len({c["case_id"] for c in cases}) != len(cases):
        fail("G2_PR4_REFERENCE_CONFLICT", "evaluation", "case_id")
    for case in cases:
        if any(t not in {"focus", "radar", "hold"} for row in case["tiers"] for t in row):
            fail("G2_PR4_REFERENCE_CONFLICT", "evaluation", "tier")
    return {c["case_id"]: c for c in cases}
