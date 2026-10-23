"""Audit explicitly authored AI development records, never human evidence or ranking input."""
import argparse
import re
from pathlib import Path

from .annotations import reference_records
from .build_pr5 import PRIMARY_TIMELINES
from .contracts import AIDevelopmentBatch, AIDevelopmentRecord, DocumentVersion, Manifest
from .exceptions import ContractError, DatasetValidationError
from .hashing import canonical_json, sha256_bytes
from .loader import PREDICTION_ROLES, json_value, load_bundle, load_step, parse_model, read_entry
from .pilot import annotation_packet_v2, citation_status

BATCH_PATH = "labels/ai_development/batch.json"


def payload_sha256(value):
    return sha256_bytes((canonical_json(value)+"\n").encode())


def record_sha256(record):
    return sha256_bytes(canonical_json(record.model_dump(mode="json")).encode())


def validate_personal_novelty(context, judgment):
    """Zero novelty needs version-anchored knowledge, never merely an earlier step.

    Explicit known version IDs or an acknowledged matching delivery card can
    establish this narrow audit condition. Natural-language prior knowledge is
    not guessed or automatically matched by this validator.
    """
    if judgment.novelty_to_persona != 0:
        return
    known = set(context.persona.knowledge_known)
    acknowledged = {(e.delivery_id, e.event_prediction_id) for e in context.exposure_history
                    if e.kind == "acknowledged" and e.event_prediction_id is not None}
    for delivery in context.delivery_history:
        if (delivery.delivery_id, delivery.event_prediction_id) in acknowledged:
            known.update(m.doc_version_id for m in delivery.members)
    if not set(judgment.document_version_ids) <= known:
        raise ContractError("AI_DEVELOPMENT_KNOWLEDGE_INVALID")


def verify_records(data, batch_value, draft_values, review_values):
    batch = parse_model(AIDevelopmentBatch, batch_value)
    source = next((e for e in data.manifest.file_hashes
                   if e.path == "labels/ai_development/input_manifest.json" and e.role == "support"), None)
    if source is None:
        raise ContractError("AI_DEVELOPMENT_INPUT_INVALID")
    raw_input = read_entry(data.root, source)
    if sha256_bytes(raw_input) != batch.input_manifest_sha256:
        raise ContractError("AI_DEVELOPMENT_INPUT_INVALID")
    input_manifest = parse_model(Manifest, json_value(raw_input))
    material_roles = PREDICTION_ROLES - {"code", "schema"}
    observed = [(e.path, e.role, e.sha256) for e in data.manifest.file_hashes if e.role in material_roles]
    supplied = [(e.path, e.role, e.sha256) for e in input_manifest.file_hashes if e.role in material_roles]
    if len(supplied) != len(set(supplied)) or sorted(supplied) != sorted(observed):
        raise ContractError("AI_DEVELOPMENT_INPUT_INVALID")
    if (payload_sha256(draft_values) != batch.draft_sha256
            or payload_sha256(review_values) != batch.review_sha256
            or batch.created_at > batch.completed_at):
        raise ContractError("AI_DEVELOPMENT_HASH_INVALID")
    drafts = [parse_model(AIDevelopmentRecord, r) for r in draft_values]
    reviews = [parse_model(AIDevelopmentRecord, r) for r in review_values]
    guide = next((e for e in data.manifest.file_hashes if e.path == "ANNOTATION_GUIDE_AI.md"
                  and e.role == "support"), None)
    if guide is None or guide.sha256 != batch.guide_sha256:
        raise ContractError("AI_DEVELOPMENT_GUIDE_INVALID")
    read_entry(data.root, guide)
    events = reference_records(data, "events")
    primary = [s for s in data.steps if s.timeline_id in PRIMARY_TIMELINES]
    contexts = {}
    required = {}
    for step in primary:
        context, candidates = load_step(data, timeline_id=step.timeline_id,
                                        step_id=step.step_id, config=data.config)
        contexts[step.timeline_id, step.step_id] = context, sha256_bytes(annotation_packet_v2(context, candidates))
        for event in events:
            members = set(event["document_version_ids"]) & set(step.visible_doc_version_ids)
            if members:
                required[step.timeline_id, step.step_id, event["event_id"]] = members
    documents = [parse_model(DocumentVersion, d) for d in data.rows["documents"]]
    document_index = {d.doc_version_id: d for d in documents}
    steps = {(s.timeline_id, s.step_id): s for s in primary}
    initial = {}
    reviewed = {}
    claims = relations = changed = 0
    for phase, records, destination in (("draft", drafts, initial), ("evidence_review", reviews, reviewed)):
        for row in records:
            key = row.timeline_id, row.step_id, row.event_id
            if key not in required or key in destination or row.phase != phase:
                raise ContractError("AI_DEVELOPMENT_COVERAGE_INVALID")
            context, packet_sha = contexts[key[:2]]
            if (row.packet_sha256 != packet_sha or row.persona_version_id != context.persona.persona_version_id
                    or set(row.judgment.document_version_ids) != required[key]
                    or not batch.created_at <= row.generated_at <= batch.completed_at):
                raise ContractError("AI_DEVELOPMENT_CONTEXT_INVALID")
            if not row.judgment.claim_reviews:
                raise ContractError("AI_DEVELOPMENT_CLAIMS_MISSING")
            step = steps[key[:2]]
            if phase == "evidence_review":
                validate_personal_novelty(context, row.judgment)
            for claim in row.judgment.claim_reviews:
                if phase == "evidence_review" and set(re.findall(
                        r"(?:^|;)\s*(version|platform|tasks|conditions|sample|runs|baseline)\s*=",
                        claim.scope.casefold())) != {"version", "platform", "tasks", "conditions", "sample", "runs", "baseline"}:
                    raise ContractError("AI_DEVELOPMENT_SCOPE_INVALID")
                if (not claim.claim_text.startswith(("[occurrence] ", "[capability] "))
                        or not claim.evidence_refs or (claim.semantic_support == "supported"
                        and not any(r.direction == "supports" for r in claim.evidence_refs))):
                    raise ContractError("AI_DEVELOPMENT_SUPPORT_INVALID")
                for ref in claim.evidence_refs:
                    citation_status(documents, ref, as_of=context.as_of)
                    if document_index[ref.doc_version_id].family_id not in step.family_scope_ids:
                        raise ContractError("AI_DEVELOPMENT_FAMILY_INVALID")
            for relation in row.judgment.document_relations:
                instant = relation.evidence_at
                for name in (relation.left_doc_version_id, relation.right_doc_version_id):
                    document = document_index.get(name)
                    if (document is None or document.family_id not in step.family_scope_ids
                            or document.available_at > instant or instant > context.as_of
                            or document.record_origin != relation.record_origin):
                        raise ContractError("AI_DEVELOPMENT_RELATION_INVALID")
            if phase == "draft":
                if row.previous_record_sha256 is not None:
                    raise ContractError("AI_DEVELOPMENT_LINEAGE_INVALID")
            else:
                source = initial.get(key)
                if (source is None or row.previous_record_sha256 != record_sha256(source)
                        or row.generated_at < source.generated_at
                        or row.executor_id != source.executor_id):
                    raise ContractError("AI_DEVELOPMENT_LINEAGE_INVALID")
                changed += row.judgment != source.judgment
                claims += len(row.judgment.claim_reviews)
                relations += len(row.judgment.document_relations)
            destination[key] = row
        if set(destination) != set(required):
            raise ContractError("AI_DEVELOPMENT_COVERAGE_INVALID")
    expected_values = [r for r in reference_records(data, "fixture_expectations")
                       if r["timeline_id"] in PRIMARY_TIMELINES]
    expected = {(r["timeline_id"], r["step_id"], r["event_id"]): r for r in expected_values}
    if len(expected) != len(expected_values) or set(expected) != set(required):
        raise ContractError("AI_DEVELOPMENT_EXPECTATIONS_INVALID")
    for key, row in reviewed.items():
        target = expected[key]
        judgment = row.judgment
        if (any(target[field] != getattr(judgment, field) for field in ("tier", "graded_relevance", "material_change"))
                or target["persona_version_id"] != row.persona_version_id
                or set(target["supporting_doc_version_ids"]) != set(judgment.document_version_ids)
                or target["provenance_uri"] != BATCH_PATH):
            raise ContractError("AI_DEVELOPMENT_EXPECTATIONS_INVALID")
    return {"status": "PASS", "batch_id": batch.batch_id, "primary_steps": len(primary),
            "event_records": len(reviewed), "review_claims": claims, "review_relations": relations,
            "changed_judgments": changed, "human_evidence": False, "independent_validation": False,
            "agreement_kappa": None, "agreement_reason": "single_ai_internal_review_not_independent_pairs",
            "disagreement_status": batch.disagreement_status}


def audit_development(data):
    def read(path):
        entry = next((e for e in data.manifest.file_hashes if e.path == path and e.role == "support"), None)
        if entry is None:
            raise ContractError("AI_DEVELOPMENT_EVIDENCE_MISSING", field=path)
        return json_value(read_entry(data.root, entry))

    batch = read(BATCH_PATH)
    parse_model(AIDevelopmentBatch, batch)
    return verify_records(data, batch, read(batch["draft_path"]), read(batch["review_path"]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        data = load_bundle(args.manifest, manifest_sha256=args.manifest_sha256)
        result = audit_development(data)
    except (ContractError, DatasetValidationError, ValueError, OSError, KeyError, TypeError) as exc:
        print(canonical_json({"ok": False, "code": getattr(exc, "code", "AI_DEVELOPMENT_INVALID")}))
        return 1
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
