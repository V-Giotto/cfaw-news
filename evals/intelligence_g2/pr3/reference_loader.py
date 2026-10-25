"""Post-prediction AI-development labels. Never import from the prediction path."""

from evals.intelligence_g2.contracts import PACKAGE, ROOT, json_bytes, read_json
from evals.intelligence_g2.replay import safe_path
from evals.intelligence_v1.hashing import sha256_bytes

from .contracts import ReferenceCase, fail, parse


def load_references(path, *, pin):
    path = safe_path(path, areas=(PACKAGE / "fixtures/pr3", ROOT / ".tmp"), code="MANIFEST_PATH_INVALID")
    raw = path.read_bytes()
    if sha256_bytes(raw) != pin:
        fail("MANIFEST_SHA_MISMATCH", "evaluation", "reference_manifest")
    header = read_json(raw)
    if header.get("format") != "g2-pr3-reference-v1" or header.get("label_origin") != "synthetic_fixture":
        fail("G2_PR3_REFERENCE_CONFLICT", "evaluation", "reference_manifest")
    rows, directions, quality = [], [], []
    paths = set()
    for entry in header["files"]:
        if (entry.get("role") != "reference" or entry["path"] in paths
                or entry["path"] not in {"expected.json", "directions_v2.json", "quality_v2.json"}):
            fail("G2_PR3_REFERENCE_CONFLICT", "evaluation", "reference_files")
        paths.add(entry["path"])
        target = safe_path(path.parent / entry["path"], areas=(path.parent,), code="MANIFEST_PATH_INVALID")
        content = target.read_bytes()
        if sha256_bytes(content) != entry["sha256"]:
            fail("SHA_MISMATCH", "evaluation", "reference_file")
        if entry["path"] == "expected.json":
            rows.extend(parse(ReferenceCase, row) for row in read_json(content)["cases"])
        elif entry["path"] == "directions_v2.json":
            directions.extend(read_json(content)["cases"])
        else:
            quality.extend(read_json(content)["cases"])
    seen = set()
    for row in rows:
        key = row.case_id, row.step_id
        if key in seen:
            fail("G2_PR3_REFERENCE_CONFLICT", "evaluation", "case_id")
        seen.add(key)
    # Direction supplements are explicit post-initial-implementation labels with disclosed
    # exposure; original extraction labels and their external pin remain unchanged.
    for row in directions:
        if (row["case_id"], row["step_id"]) not in seen:
            fail("G2_PR3_REFERENCE_CONFLICT", "evaluation", "direction_case")
        for pair in row["links"]:
            if pair["direction"] not in {"supports", "refutes", "mentions", "unknown"}:
                fail("G2_PR3_REFERENCE_CONFLICT", "evaluation", "direction")
    return tuple(rows), tuple(directions), tuple(quality), sha256_bytes(json_bytes(header))
