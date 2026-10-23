"""Offline annotation packets, provenance audit and pre-adjudication statistics.

Human identity and independence require a real administrator's attestation. This
module checks the attestation's traceability; it cannot establish human identity.
"""

import argparse
from itertools import combinations
from pathlib import Path

from .build_pr5 import ANNOTATION_VERSION, GUIDE_FILE, GUIDE_REVISION, PRIMARY_TIMELINES
from .contracts import (
    Adjudication,
    Annotation,
    EventAlignment,
    GoldLabel,
    HumanAnnotation,
    ReviewSession,
    SupportReview,
    schema_text,
)
from .exceptions import ContractError
from .hashing import canonical_json, sha256_bytes
from .loader import json_value, load_bundle, load_step, parse_model, read_entry, read_records
from .metrics import ratio, unavailable
from .pilot import annotation_packet_v2, citation_status
from .replay import _output_location, write_payloads

SCORES = ("relevance", "potential_value", "novelty_to_persona", "evidence_quality", "graded_relevance")
AI_GUIDE_FILE = "ANNOTATION_GUIDE_AI.md"
CATEGORIES = {"tier": ["focus", "radar", "archive", "hold"],
              "material_change": ["new", "meaningful_update", "no_change", "correction", "withdrawal", "insufficient"]}


def agreement_statistic(left, right, categories, *, weighted=False):
    if len(left) != len(right) or not categories or len(set(categories)) != len(categories):
        raise ValueError("invalid paired samples/categories")
    index = {value: i for i, value in enumerate(categories)}
    if any(value not in index for value in [*left, *right]):
        raise ValueError("unknown category")
    matrix = [[0 for _ in categories] for _ in categories]
    for a, b in zip(left, right, strict=True):
        matrix[index[a]][index[b]] += 1
    n = len(left)
    agreed = sum(matrix[i][i] for i in range(len(categories)))
    result = {"count": n, "categories": categories, "confusion_matrix": matrix,
              "distribution_left": [sum(row) for row in matrix],
              "distribution_right": [sum(row[j] for row in matrix) for j in range(len(categories))],
              "agreement_numerator": agreed, "raw_agreement": agreed/n if n else None,
              "kappa": None, "undefined_reason": "no_paired_samples" if not n else None,
              "weighting": "quadratic" if weighted else "nominal"}
    if not n:
        return result
    marginals_a = [sum(row) for row in matrix]
    marginals_b = [sum(row[j] for row in matrix) for j in range(len(categories))]
    observed = expected = 0.0
    for i in range(len(categories)):
        for j in range(len(categories)):
            weight = (i-j)**2 if weighted else int(i != j)
            observed += weight*matrix[i][j]/n
            expected += weight*marginals_a[i]*marginals_b[j]/(n*n)
    if expected:
        result["kappa"] = 1-observed/expected
    else:
        result["undefined_reason"] = "degenerate_expected_agreement"
    return result


def export_packet(manifest_path, *, manifest_sha256, timeline_id, step_id, out):
    if timeline_id not in PRIMARY_TIMELINES or not step_id:
        raise ContractError("REFERENCE_NOT_FOUND", field="timeline_or_step")
    data = load_bundle(manifest_path, manifest_sha256=manifest_sha256)
    output = _output_location(out, data.root)
    context, candidates = load_step(data, timeline_id=timeline_id, step_id=step_id, config=data.config)
    packet = annotation_packet_v2(context, candidates)
    guide_entry = next((e for e in data.manifest.file_hashes
                        if e.path == GUIDE_FILE and e.role == "support"), None)
    if guide_entry is None:
        raise ContractError("UNLISTED_INPUT", field="guide_revision")
    read_entry(data.root, guide_entry)
    ai_guide = next((e for e in data.manifest.file_hashes
                     if e.path == AI_GUIDE_FILE and e.role == "support"), None)
    if ai_guide is None:
        raise ContractError("UNLISTED_INPUT", field="ai_guide_revision")
    ai_guide_bytes = read_entry(data.root, ai_guide)
    template = {"template_only": True, "annotation_id": None, "annotator_id": None,
        "submitted_at": None, "timeline_id": timeline_id, "step_id": step_id,
        "persona_version_id": context.persona.persona_version_id, "annotation_version": ANNOTATION_VERSION,
        "guide_revision": GUIDE_REVISION, "packet_sha256": sha256_bytes(packet),
        "initial_label": {"local_event_id": None, "document_version_ids": [],
            **dict.fromkeys((*SCORES, "material_change", "tier", "rationale")),
            "uncertainty": [], "document_relations": [], "claim_reviews": []}}
    fields = {"claim_review": {"claim_text": None, "evidence_refs": [], "semantic_support": None,
                                "scope": None, "limitations": []},
              "evidence_ref": {"doc_version_id": None, "paragraph_id": None, "direction": None},
              "document_relation": dict.fromkeys(("left_doc_version_id", "right_doc_version_id",
                  "relation", "rationale", "evidence_at", "record_origin", "provenance_uri"))}
    metadata = {"packet_sha256": sha256_bytes(packet), "guide_sha256": guide_entry.sha256,
        "default_acceptance_profile": "ai_development", "ai_guide_revision": "ai-dev-guide-v1",
        "ai_guide_sha256": ai_guide.sha256,
        "dataset_manifest_sha256": manifest_sha256, "timeline_id": timeline_id, "step_id": step_id,
        "distribution": "not_distributed", "human_annotation": "not_confirmed"}
    write_payloads(output, {"packet.json": packet, "blank_form.json": (canonical_json(template)+"\n").encode(),
                            "metadata.json": (canonical_json(metadata)+"\n").encode(),
                            "field_templates.json": (canonical_json(fields)+"\n").encode(),
                            "submission.schema.json": schema_text(HumanAnnotation).encode(),
                            GUIDE_FILE: read_entry(data.root, guide_entry), AI_GUIDE_FILE: ai_guide_bytes})
    return metadata


def reference_records(data, role, model=None, *, primary_version=False):
    result = []
    for entry in data.manifest.file_hashes:
        if entry.role != role or (primary_version and (
                entry.annotation_version or data.manifest.annotation_version) != ANNOTATION_VERSION):
            continue
        for row in read_records(read_entry(data.root, entry), entry):
            result.append(parse_model(model, row) if model else row)
    return result


def submission_bytes(annotations):
    ordered = sorted(annotations, key=lambda a: (a.timeline_id, a.step_id,
                                                a.initial_label.local_event_id, a.annotation_id))
    return "".join(canonical_json(a.model_dump(mode="json"))+"\n" for a in ordered).encode()


def claim_review_sha256(claim):
    """Bind the full original ClaimReview; array order and judgments stay intact."""
    return sha256_bytes(canonical_json(claim.model_dump(mode="json")).encode("utf-8"))


def support_claim_lineage_valid(review, prior, participants):
    if len({a.annotator_id for a in prior}) != 2 or not all(
            a.timeline_id == review.timeline_id and a.step_id == review.step_id
            and a.persona_version_id == review.persona_version_id
            and a.annotation_version == review.annotation_version
            and a.annotator_id in participants
            and participants[a.annotator_id].frozen_at <= review.reviewed_at for a in prior):
        return False
    alignment = review.source_claim_alignment
    if alignment is None:
        # Historical exact-match records remain valid; differing originals need
        # explicit human correspondence, never inferred or position-based matches.
        return all(any(c.claim_text == review.claim_text and c.evidence_refs == review.evidence_refs
                       and c.scope == review.scope for c in a.initial_label.claim_reviews) for a in prior)
    if (alignment.aligned_at > review.reviewed_at
            or any(participants[a.annotator_id].frozen_at > alignment.aligned_at for a in prior)):
        return False
    originals = {a.annotation_id: a for a in prior}
    keys = [(source.annotation_id, source.claim_sha256) for source in alignment.sources]
    if len(set(keys)) != len(keys) or {key[0] for key in keys} != set(originals):
        return False
    return all(sum(claim_review_sha256(claim) == digest
                   for claim in originals[annotation_id].initial_label.claim_reviews) == 1
               for annotation_id, digest in keys)


def gold_key(label):
    return (label.timeline_id, label.step_id, label.persona_version_id, label.event_id, label.annotation_version)


def audit_annotations(manifest_path, *, manifest_sha256):
    data = load_bundle(manifest_path, manifest_sha256=manifest_sha256)
    return audit_bundle(data)


def audit_bundle(data):
    from .agreement import family_confidence_interval
    from .contracts import DocumentVersion

    session_entry = next((e for e in data.manifest.file_hashes if e.path == "labels/review_session.json"
                          and e.role == "support"), None)
    if session_entry is None:
        raise ContractError("UNLISTED_INPUT", field="review_session")
    session = parse_model(ReviewSession, json_value(read_entry(data.root, session_entry)))
    guide_entry = next((e for e in data.manifest.file_hashes if e.path == GUIDE_FILE), None)
    errors = []

    def error(code, target=""):
        errors.append({"code": code, "target": target})

    if (guide_entry is None or guide_entry.sha256 != session.guide_sha256
            or session.annotation_version != ANNOTATION_VERSION):
        error("ANNOTATION_GUIDE_MISMATCH")
    elif sha256_bytes(read_entry(data.root, guide_entry)) != session.guide_sha256:
        error("ANNOTATION_GUIDE_MISMATCH")
    annotations = reference_records(data, "annotations", Annotation, primary_version=True)
    gold = reference_records(data, "gold", GoldLabel, primary_version=True)
    alignments = reference_records(data, "event_alignments", EventAlignment, primary_version=True)
    adjudications = reference_records(data, "adjudications", Adjudication, primary_version=True)
    support = reference_records(data, "support_reviews", SupportReview, primary_version=True)
    events = {e["event_id"]: e for e in reference_records(data, "events")}
    # With no submissions there is nothing to compare or adjudicate. Do not
    # repeatedly reconstruct 26 packets for every baseline evaluation.
    if not (annotations or gold or alignments or adjudications or support or session.participants
            or session.packet_receipts):
        count = sum(bool(set(e["document_version_ids"]) & set(s.visible_doc_version_ids))
                    for s in data.steps if s.timeline_id in PRIMARY_TIMELINES
                    for e in events.values())
        statistics = {name: {**agreement_statistic([], [], list(range(4)) if name in SCORES else CATEGORIES[name],
                                                weighted=name in SCORES),
            "family_confidence_interval": family_confidence_interval([], list(range(4)) if name in SCORES
                                                                     else CATEGORIES[name], weighted=name in SCORES)}
            for name in (*SCORES, *CATEGORIES)}
        return {"dataset_manifest_sha256": sha256_bytes((data.root/"manifests/dataset_manifest.json").read_bytes()),
            "annotation_version": ANNOTATION_VERSION, "human_gate": "FAIL" if errors else "BLOCKED",
            "human_annotation": "not_confirmed", "session_status": session.status,
            "confirmed_human_annotators": [], "initial_annotation_count": 0, "expected_target_count": count,
            "eligible_gold_keys": [], "complete_steps": [], "coverage_complete": False,
            "errors": errors, "missing_target_count": count,
            "agreement": {"paired_target_count": 0, "unmatched_targets": [], "statistics": statistics,
                "event_pairs": {"comparable_pair_count": 0, "raw_agreement": None,
                    **{n: unavailable("no_positive_pairs") for n in ("a_reference_precision", "a_reference_recall",
                        "b_reference_precision", "b_reference_recall", "f1")}},
                "below_observation_threshold": [],
                "observation_threshold": .70, "remediation_required": False,
                "scope": "raw_initial_submissions_before_adjudication; five_correlated_development_families"},
            "semantic_support": unavailable("human_review_not_confirmed"), "support_review_count": 0,
            "scope": "human_audit_of_authored_synthetic_development_data_not_algorithm_output_quality"}
    documents = [parse_model(DocumentVersion, d) for d in data.rows["documents"]]
    document_index = {d.doc_version_id: d for d in documents}
    by_annotation = {a.annotation_id: a for a in annotations}
    by_reviewer = {p.annotator_id: p for p in session.participants}
    if len(by_annotation) != len(annotations) or len(by_reviewer) != len(session.participants):
        error("DUPLICATE_ID")
    steps = {(s.timeline_id, s.step_id): s for s in data.steps if s.timeline_id in PRIMARY_TIMELINES}
    contexts, packets, targets = {}, {}, {}
    for key, step in sorted(steps.items()):
        context, candidates = load_step(data, timeline_id=key[0], step_id=key[1], config=data.config)
        contexts[key] = context
        packets[key] = sha256_bytes(annotation_packet_v2(context, candidates))
        visible = set(context.candidate_doc_version_ids)
        for event_id, event in events.items():
            members = visible & set(event["document_version_ids"])
            if members and event["family_id"] in step.family_scope_ids:
                targets[(*key, step.persona_version_id, event_id, ANNOTATION_VERSION)] = members
    for participant in session.participants:
        initial = [a for a in annotations if a.annotator_id == participant.annotator_id]
        if not initial or sha256_bytes(submission_bytes(initial)) != participant.submission_sha256:
            error("INITIAL_SUBMISSION_SHA_MISMATCH", participant.annotator_id)
        if any(a.submitted_at > participant.frozen_at for a in initial):
            error("INITIAL_SUBMISSION_NOT_FROZEN", participant.annotator_id)
    receipts = {}
    for receipt in session.packet_receipts:
        key = (receipt.annotator_id, receipt.timeline_id, receipt.step_id)
        if key in receipts:
            error("DUPLICATE_ID", str(key))
        receipts[key] = receipt
        if (receipt.annotator_id not in by_reviewer
                or packets.get((receipt.timeline_id, receipt.step_id)) != receipt.packet_sha256):
            error("PACKET_RECEIPT_MISMATCH", str(key))
    submission_targets = set()
    for annotation in annotations:
        key = (annotation.timeline_id, annotation.step_id)
        context = contexts.get(key)
        participant = by_reviewer.get(annotation.annotator_id)
        receipt = receipts.get((annotation.annotator_id, *key))
        identity = (annotation.annotator_id, *key, annotation.initial_label.local_event_id)
        if identity in submission_targets:
            error("DUPLICATE_ID", annotation.annotation_id)
        submission_targets.add(identity)
        if (context is None or annotation.persona_version_id != context.persona.persona_version_id
                or annotation.annotation_version != ANNOTATION_VERSION):
            error("ANNOTATION_CONTEXT_MISMATCH", annotation.annotation_id)
            continue
        if (annotation.guide_revision != session.guide_revision or annotation.packet_sha256 != packets[key]
                or not participant or not receipt or receipt.delivered_at > annotation.submitted_at
                or annotation.submitted_at < context.as_of):
            error("ANNOTATION_CONTEXT_MISMATCH", annotation.annotation_id)
        members = annotation.initial_label.document_version_ids
        if len(set(members)) != len(members) or not set(members) <= set(context.candidate_doc_version_ids):
            error("FUTURE_EVIDENCE", annotation.annotation_id)
        relation_keys = set()
        for relation in annotation.initial_label.document_relations:
            pair = tuple(sorted((relation.left_doc_version_id, relation.right_doc_version_id)))
            relation_key = (*pair, relation.evidence_at)
            if relation_key in relation_keys or pair[0] == pair[1]:
                error("DUPLICATE_ID", annotation.annotation_id)
            relation_keys.add(relation_key)
            relation_visible = (set(context.candidate_doc_version_ids) if annotation.guide_revision != "g1a-guide-v3"
                else {d.doc_version_id for d in documents if d.available_at <= context.as_of
                      and d.family_id in steps[key].family_scope_ids})
            if (not set(pair) <= relation_visible
                    or relation.evidence_at > context.as_of):
                error("FUTURE_EVIDENCE", annotation.annotation_id)
            elif (max(document_index[k].available_at for k in pair) > relation.evidence_at
                    or any(document_index[k].record_origin != relation.record_origin for k in pair)):
                error("ANNOTATION_RELATION_INVALID", annotation.annotation_id)
        for review in annotation.initial_label.claim_reviews:
            for ref in review.evidence_refs:
                try:
                    citation_status(documents, ref, as_of=context.as_of)
                    if document_index[ref.doc_version_id].family_id not in steps[key].family_scope_ids:
                        raise ContractError("CROSS_FAMILY_SPLIT")
                except ContractError as exc:
                    error(exc.code, annotation.annotation_id)
    # Enforce sequential packet delivery using actual receipt/submission times.
    for reviewer in by_reviewer:
        for timeline in PRIMARY_TIMELINES:
            previous = []
            for key in sorted((k for k in steps if k[0] == timeline), key=lambda k: steps[k].as_of):
                current = [a for a in annotations if a.annotator_id == reviewer
                           and (a.timeline_id, a.step_id) == key]
                receipt = receipts.get((reviewer, *key))
                if receipt and previous and max(a.submitted_at for a in previous) >= receipt.delivered_at:
                    error("FUTURE_PACKET_DISTRIBUTED_EARLY", str((reviewer, *key)))
                previous += current
    aligned, valid_alignments = {}, {}
    ordinal = {name: ([], []) for name in (*SCORES, *CATEGORIES)}
    ordinal_families = []
    unmatched = []
    for alignment in alignments:
        key = gold_key(alignment)
        prior = [by_annotation.get(i) for i in alignment.prior_annotation_ids]
        if key in aligned:
            error("DUPLICATE_ID", str(key))
        aligned[key] = alignment
        valid = (key in targets and set(alignment.doc_version_ids) == targets[key]
                 and len(set(alignment.doc_version_ids)) == len(alignment.doc_version_ids)
                 and len(set(alignment.prior_annotation_ids)) == len(prior)
                 and all(a is not None for a in prior))
        if valid:
            valid = len({a.annotator_id for a in prior}) >= 2 and all(
                (a.timeline_id, a.step_id, a.persona_version_id, a.annotation_version) == key[:3]+key[4:]
                and a.submitted_at <= alignment.aligned_at for a in prior)
        if valid:
            # A raw group can overlap several final events (merge), or several
            # raw groups can cover one final event (split). Keep all originals.
            overlapping = [a for a in annotations
                if (a.timeline_id, a.step_id, a.persona_version_id, a.annotation_version) == key[:3]+key[4:]
                and set(a.initial_label.document_version_ids) & targets[key]]
            valid = (set(alignment.prior_annotation_ids) == {a.annotation_id for a in overlapping}
                and {a.annotator_id for a in prior} == set(by_reviewer)
                and all(set().union(*(set(a.initial_label.document_version_ids) & targets[key]
                    for a in prior if a.annotator_id == reviewer)) == targets[key] for reviewer in by_reviewer))
        if not valid:
            error("EVENT_ALIGNMENT_INVALID", str(key))
            continue
        members_agree = all(set(a.initial_label.document_version_ids) == targets[key] for a in prior)
        if alignment.status == "matched" and not members_agree:
            error("EVENT_ALIGNMENT_INVALID", str(key))
            continue
        valid_alignments[key] = alignment
        if alignment.status != "matched":
            unmatched.append(list(key))
            continue
        pair = sorted(prior, key=lambda a: a.annotator_id)[:2]
        ordinal_families.append(events[alignment.event_id]["family_id"])
        for name, (a_values, b_values) in ordinal.items():
            a_values.append(getattr(pair[0].initial_label, name))
            b_values.append(getattr(pair[1].initial_label, name))
    eligible, complete_steps, seen_gold = [], [], set()
    for label in gold:
        key = gold_key(label)
        if key in seen_gold:
            error("DUPLICATE_ID", str(key))
            continue
        seen_gold.add(key)
        alignment = valid_alignments.get(key)
        if label.adjudication_status in {"pending", "unresolved"}:
            continue
        # Event membership uses the latest ranking candidates. Supporting evidence
        # may also cite an earlier version of that event, visible by this step.
        context = contexts.get(key[:2])
        event = events.get(label.event_id, {})
        support_ids = {version_id for version_id in event.get("document_version_ids", ())
                       if context is not None and version_id in document_index
                       and document_index[version_id].available_at <= context.as_of
                       and document_index[version_id].family_id in steps[key[:2]].family_scope_ids}
        if not alignment or alignment.status == "unresolved" or key not in targets or not (
                set(label.supporting_doc_version_ids) and set(label.supporting_doc_version_ids) <= support_ids):
            error("GOLD_LINEAGE_MISSING", str(key))
            continue
        prior = [by_annotation.get(i) for i in alignment.prior_annotation_ids]
        if any(a is None for a in prior) or len({a.annotator_id for a in prior}) < 2:
            error("GOLD_LINEAGE_MISSING", str(key))
            continue
        if any(a.annotator_id not in by_reviewer or
               by_reviewer[a.annotator_id].frozen_at > alignment.aligned_at for a in prior):
            error("ADJUDICATION_BEFORE_FREEZE", str(key))
            continue
        if label.adjudication_status == "agreed":
            if alignment.status != "matched":
                error("GOLD_NOT_AGREED", str(key))
                continue
            if any(any(getattr(a.initial_label, n) != getattr(label, n) for n in ordinal) for a in prior):
                error("GOLD_NOT_AGREED", str(key))
                continue
        else:
            decisions = [a for a in adjudications if a.final_label == label
                         and set(a.prior_annotation_ids) == set(alignment.prior_annotation_ids)]
            if len(decisions) != 1:
                error("GOLD_LINEAGE_MISSING", str(key))
                continue
            if decisions[0].adjudicated_at < alignment.aligned_at or any(
                   a.annotator_id not in by_reviewer or by_reviewer[a.annotator_id].frozen_at > decisions[0].adjudicated_at
                   for a in prior):
                error("ADJUDICATION_BEFORE_FREEZE", str(key))
                continue
        eligible.append(key)
    for key in contexts:
        required = {k for k in targets if k[:2] == key}
        if required and required <= set(eligible):
            complete_steps.append(list(key))
    # Membership partitions, not arbitrary local event names, determine pair agreement.
    pairs_a, pairs_b, comparable = set(), set(), 0
    ids = sorted(by_reviewer)[:2]
    for key, context in contexts.items():
        if len(ids) < 2:
            continue
        assignments = []
        for reviewer in ids:
            assignment = {}
            for a in annotations:
                if a.annotator_id == reviewer and (a.timeline_id, a.step_id) == key:
                    for doc in a.initial_label.document_version_ids:
                        if doc in assignment:
                            error("ANNOTATION_PARTITION_OVERLAP", a.annotation_id)
                        assignment[doc] = a.annotation_id
            assignments.append(assignment)
        for left, right in combinations(sorted(context.candidate_doc_version_ids), 2):
            if not all(left in a and right in a for a in assignments):
                continue
            comparable += 1
            for assignment, positive in zip(assignments, (pairs_a, pairs_b), strict=True):
                if assignment[left] == assignment[right]:
                    positive.add((*key, left, right))
    tp = len(pairs_a & pairs_b)
    pair_result = {"comparable_pair_count": comparable,
        "raw_agreement": (comparable-len(pairs_a ^ pairs_b))/comparable if comparable else None,
        "a_reference_precision": ratio(tp, len(pairs_b), "no_positive_pairs"),
        "a_reference_recall": ratio(tp, len(pairs_a), "no_positive_pairs"),
        "b_reference_precision": ratio(tp, len(pairs_a), "no_positive_pairs"),
        "b_reference_recall": ratio(tp, len(pairs_b), "no_positive_pairs"),
        "f1": ratio(2*tp, len(pairs_a)+len(pairs_b), "no_positive_pairs")}
    statistics = {name: agreement_statistic(a, b, list(range(4)) if name in SCORES else CATEGORIES[name],
                                           weighted=name in SCORES) for name, (a, b) in ordinal.items()}
    for name, (a, b) in ordinal.items():
        statistics[name]["family_confidence_interval"] = family_confidence_interval(
            list(zip(ordinal_families, a, b, strict=True)),
            list(range(4)) if name in SCORES else CATEGORIES[name], weighted=name in SCORES)
    low = [n for n, v in statistics.items() if v["kappa"] is not None and v["kappa"] < .70]
    confirmed = (len(by_reviewer) == 2 and session.status == "adjudicated" and session.confirmed_by is not None
        and session.confirmed_at is not None and all(p.real_human_confirmed and p.independent_submission_confirmed
        and p.frozen_at <= session.confirmed_at for p in session.participants))
    # Every participant must cover every visible document in each of the 26 states.
    coverage_complete = bool(contexts) and len(contexts) == 26
    for key, context in contexts.items():
        for reviewer in by_reviewer:
            members = [d for a in annotations if a.annotator_id == reviewer and (a.timeline_id, a.step_id) == key
                       for d in a.initial_label.document_version_ids]
            coverage_complete &= len(members) == len(set(members)) and set(members) == set(context.candidate_doc_version_ids)
    seen_support, valid_support = set(), []
    for review in support:
        prior = [by_annotation.get(i) for i in review.prior_annotation_ids]
        context = contexts.get((review.timeline_id, review.step_id))
        identity = (review.timeline_id, review.step_id, review.persona_version_id,
                    review.claim_text, tuple((r.doc_version_id, r.paragraph_id, r.direction) for r in review.evidence_refs))
        if identity in seen_support:
            error("DUPLICATE_ID", review.support_review_id)
        seen_support.add(identity)
        valid = (context is not None and review.persona_version_id == context.persona.persona_version_id
                 and review.annotation_version == ANNOTATION_VERSION and all(a is not None for a in prior)
                 and len(set(review.prior_annotation_ids)) == len(prior))
        if valid:
            valid = support_claim_lineage_valid(review, prior, by_reviewer)
        if not valid:
            error("SUPPORT_REVIEW_LINEAGE_INVALID", review.support_review_id)
            continue
        try:
            for ref in review.evidence_refs:
                citation_status(documents, ref, as_of=context.as_of)
                if document_index[ref.doc_version_id].family_id not in steps[(review.timeline_id, review.step_id)].family_scope_ids:
                    raise ContractError("CROSS_FAMILY_SPLIT")
        except ContractError as exc:
            error(exc.code, review.support_review_id)
            continue
        valid_support.append(review)
    human_pass = confirmed and coverage_complete and len(complete_steps) == 26 and not errors and not low
    review_times = ([a.aligned_at for a in alignments] + [a.adjudicated_at for a in adjudications]
                    + [r.reviewed_at for r in support])
    if session.confirmed_at is not None and any(t > session.confirmed_at for t in review_times):
        error("CONFIRMATION_BEFORE_REVIEW_COMPLETED")
        human_pass = False
    human_gate = "FAIL" if errors else "PASS" if human_pass else "BLOCKED"
    semantic = (ratio(sum(r.semantic_support == "supported" for r in valid_support), len(valid_support),
                      "no_reviewed_cited_statements") if human_pass else unavailable("human_review_not_confirmed"))
    return {"dataset_manifest_sha256": sha256_bytes((data.root/"manifests/dataset_manifest.json").read_bytes()),
        "annotation_version": ANNOTATION_VERSION, "human_gate": human_gate,
        "human_annotation": "confirmed" if human_pass else "not_confirmed", "session_status": session.status,
        "confirmed_human_annotators": sorted(by_reviewer) if confirmed and not errors else [],
        "initial_annotation_count": len(annotations), "expected_target_count": len(targets),
        "eligible_gold_keys": [list(k) for k in sorted(eligible)] if human_pass else [],
        "complete_steps": sorted(complete_steps) if human_pass else [],
        "coverage_complete": coverage_complete and len(by_reviewer) == 2,
        "errors": errors, "missing_target_count": len(set(targets)-set(eligible)),
        "agreement": {"paired_target_count": len(next(iter(ordinal.values()))[0]),
            "unmatched_targets": unmatched, "statistics": statistics, "event_pairs": pair_result,
            "below_observation_threshold": low,
            "observation_threshold": .70, "remediation_required": bool(low),
            "scope": "raw_initial_submissions_before_adjudication; five_correlated_development_families"},
        "semantic_support": semantic, "support_review_count": len(valid_support),
        "scope": "human_audit_of_authored_synthetic_development_data_not_algorithm_output_quality"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["packet", "audit", "agreement"])
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--timeline", choices=PRIMARY_TIMELINES)
    parser.add_argument("--step")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "packet":
            result = export_packet(args.manifest, manifest_sha256=args.manifest_sha256,
                timeline_id=args.timeline, step_id=args.step, out=args.out)
        else:
            data = load_bundle(args.manifest, manifest_sha256=args.manifest_sha256)
            output = _output_location(args.out, data.root)
            result = audit_bundle(data)
            write_payloads(output, {"annotation_audit.json": (canonical_json(result)+"\n").encode()})
    except (ContractError, OSError, ValueError, KeyError) as exc:
        print(canonical_json({"ok": False, "code": getattr(exc, "code", "ANNOTATION_IO_ERROR")}))
        return 1
    print(canonical_json({"ok": not result.get("errors"), "human_gate": result.get("human_gate", "BLOCKED")}))
    return int(bool(result.get("errors")))


if __name__ == "__main__":
    raise SystemExit(main())
