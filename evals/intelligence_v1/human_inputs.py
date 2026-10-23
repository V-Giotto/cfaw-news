"""Explicit V3 human-to-machine projection. Never repairs or overwrites a submission."""

import argparse
import copy
from pathlib import Path

from pydantic import ValidationError

from .contracts import Annotation, HumanAnnotation, HumanClaimReview, HumanReviewLabel
from .exceptions import ContractError
from .hashing import canonical_json, sha256_bytes
from .loader import json_value

DIRECTIONS = {"supports": "supports", "contradicts": "refutes", "mentions": "mentions"}
RELATIONS = {
    "correction_of": "same_event_different_evidence",
    "superseded_by": "same_event_different_evidence",
    "syndicated_republish": "syndicated",
    "rewritten_derivative": "syndicated",
    "press_material_copy": "syndicated",
    "independent_test_of": "same_event_different_evidence",
    "separate_announcement_no_update": "related_distinct_event",
}


def project_annotation(raw):
    """Validate first. Retain raw-byte identity and every original mapped word."""
    value = json_value(raw)
    HumanAnnotation.model_validate_json(canonical_json(value))
    projected = copy.deepcopy(value)
    mapping = []
    for index, relation in enumerate(projected["initial_label"]["document_relations"]):
        source = relation["relation"]
        relation["relation"] = RELATIONS[source]
        mapping.append({"path": f"/initial_label/document_relations/{index}/relation",
                        "original": source, "canonical": relation["relation"]})
    for index, claim in enumerate(projected["initial_label"]["claim_reviews"]):
        for ref_index, ref in enumerate(claim["evidence_refs"]):
            source = ref["direction"]
            ref["direction"] = DIRECTIONS[source]
            mapping.append({"path": f"/initial_label/claim_reviews/{index}/evidence_refs/{ref_index}/direction",
                            "original": source, "canonical": ref["direction"]})
    Annotation.model_validate_json(canonical_json(projected))
    return {"source_sha256": sha256_bytes(raw), "original": value,
            "canonical_projection": projected, "mapping": mapping,
            "formal_import_ready": False, "human_evidence_created": False}


def extract_review_label(raw):
    """Resolve explicit review links without turning post-hoc review into initial labels."""
    value = json_value(raw)
    review = HumanReviewLabel.model_validate_json(canonical_json(value["review_label"]))
    judgment = review.model_dump(mode="json", exclude={
        "review_id", "reviewer", "reviewed_at", "guide_revision", "annotation_version"})
    sources = []
    for source_claim, target_claim in zip(value["review_label"]["claim_reviews"],
                                         judgment["claim_reviews"], strict=True):
        index = int(source_claim["derived_from"].removeprefix("initial_label.claim_reviews[").removesuffix("]"))
        try:
            original = value["initial_label"]["claim_reviews"][index]
        except (IndexError, KeyError, TypeError):
            raise ContractError("REVIEW_LINEAGE_MISSING") from None
        original_model = HumanClaimReview.model_validate_json(canonical_json(original))
        sources.append({"review_claim_id": source_claim["claim_id"],
            "annotation_id": value["annotation_id"], "original_claim_index": index,
            "original_claim_sha256": sha256_bytes(canonical_json(original_model.model_dump(mode="json")).encode()),
            "original_claim_raw_sha256": sha256_bytes(canonical_json(original).encode()),
            "review_claim_sha256": sha256_bytes(canonical_json(source_claim).encode())})
        for extra in ("claim_id", "derived_from", "layer", "support_note"):
            target_claim.pop(extra)
    return {"source_sha256": sha256_bytes(raw), "original_review": value["review_label"],
            "review_judgment_projection": judgment, "source_claim_links": sources,
            "initial_submission_replaced": False, "formal_import_ready": False,
            "human_evidence_created": False, "semantic_mapping_verified": False}


def inspect_submission(raw, *, layer="received"):
    """Check every JSONL row. A successful format check never certifies human origin."""
    errors, seen, count = [], set(), 0
    for number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        count += 1
        try:
            if layer == "review":
                projection = extract_review_label(line)
                identity = projection["original_review"]["review_id"]
            else:
                value = json_value(line)
                if layer == "initial":
                    value = {k: v for k, v in value.items() if k != "review_label"}
                projection = project_annotation(canonical_json(value).encode())
                identity = projection["original"]["annotation_id"]
            if identity in seen:
                errors.append({"line": number, "code": "DUPLICATE_ID"})
            seen.add(identity)
        except ValidationError as exc:
            errors.extend({"line": number, "code": "SCHEMA_INVALID", "path": list(e["loc"])}
                          for e in exc.errors(include_input=False))
        except ContractError as exc:
            errors.append({"line": number, "code": exc.code})
        except (ValueError, KeyError, TypeError):
            errors.append({"line": number, "code": "INVALID_JSON"})
    if not count:
        errors.append({"line": None, "code": "EMPTY_SUBMISSION"})
    return {"format_check": "FAIL" if errors else "PASS", "source_sha256": sha256_bytes(raw),
            "record_count": count, "errors": errors, "formal_import_ready": False,
            "human_evidence_created": False, "semantic_support_verified": False, "layer": layer}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--layer", choices=["received", "initial", "review"], default="received")
    args = parser.parse_args()
    result = inspect_submission(args.input.read_bytes(), layer=args.layer)
    print(canonical_json(result))
    return int(bool(result["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
