"""Synthetic contract probes for V3 input; these never establish human evidence."""

import copy
import json

import pytest
from conftest import refresh

from evals.intelligence_v1.annotations import claim_review_sha256, export_packet
from evals.intelligence_v1.contracts import Annotation
from evals.intelligence_v1.hashing import canonical_json, sha256_bytes


def probe():
    return dict(annotation_id="contract-only", timeline_id="DEV-02", step_id="D1",
        persona_version_id="d02:developer:1", annotation_version="g1a-annotation-v2",
        annotator_id="CONTRACT-PROBE-NOT-HUMAN", submitted_at="2026-10-23T01:00:00Z",
        guide_revision="g1a-guide-v3", packet_sha256="0"*64,
        initial_label=dict(local_event_id="local", document_version_ids=["d02:repost:1"],
            relevance=0, potential_value=0, novelty_to_persona=0, evidence_quality=0,
            graded_relevance=0, material_change="insufficient", tier="hold",
            rationale="Fabricated contract probe", uncertainty=[],
            document_relations=[dict(left_doc_version_id="d02:repost:1",
                right_doc_version_id="d02:release:1", relation="syndicated_republish",
                rationale="Fabricated contract probe", evidence_at="2026-03-02T12:00:00Z",
                record_origin="synthetic", provenance_uri="DEV-02/README.md")],
            claim_reviews=[dict(claim_text="[capability] Fabricated probe", evidence_refs=[
                dict(doc_version_id="d02:release:1", paragraph_id="p1", direction="contradicts")],
                semantic_support="uncertain", scope="Fabricated scope", limitations=[])]))


def test_v3_packet_uses_new_guide_and_human_schema(bundle, tmp_path):
    manifest = refresh(bundle)
    out = tmp_path/"packet"
    metadata = export_packet(manifest, manifest_sha256=sha256_bytes(manifest.read_bytes()),
                             timeline_id="DEV-02", step_id="D0", out=out)
    blank = json.loads((out/"blank_form.json").read_bytes())
    assert blank["guide_revision"] == "g1a-guide-v3"
    assert blank["annotation_version"] == "g1a-annotation-v2"
    assert metadata["distribution"] == "not_distributed"
    assert metadata["human_annotation"] == "not_confirmed"
    assert (out/"ANNOTATION_GUIDE_V3.md").read_bytes() == (bundle/"ANNOTATION_GUIDE_V3.md").read_bytes()
    schema = json.loads((out/"submission.schema.json").read_bytes())
    assert schema["properties"]["guide_revision"]["const"] == "g1a-guide-v3"


@pytest.mark.parametrize("word,canonical", [
    ("correction_of", "same_event_different_evidence"),
    ("superseded_by", "same_event_different_evidence"),
    ("syndicated_republish", "syndicated"), ("rewritten_derivative", "syndicated"),
    ("press_material_copy", "syndicated"), ("independent_test_of", "same_event_different_evidence"),
    ("separate_announcement_no_update", "related_distinct_event"),
])
def test_v3_mapping_preserves_original_relation_direction_and_versions(word, canonical):
    from evals.intelligence_v1.human_inputs import project_annotation

    row = probe()
    row["initial_label"]["document_relations"][0]["relation"] = word
    original = copy.deepcopy(row)
    result = project_annotation(canonical_json(row).encode())
    assert row == original
    assert result["source_sha256"] == sha256_bytes(canonical_json(row).encode())
    projected = result["canonical_projection"]
    relation = projected["initial_label"]["document_relations"][0]
    assert relation["relation"] == canonical
    assert relation["left_doc_version_id"] == "d02:repost:1"
    assert relation["right_doc_version_id"] == "d02:release:1"
    assert projected["guide_revision"] == "g1a-guide-v3"
    assert projected["annotation_version"] == "g1a-annotation-v2"
    assert projected["initial_label"]["claim_reviews"][0]["evidence_refs"][0]["direction"] == "refutes"
    assert result["formal_import_ready"] is False
    assert result["human_evidence_created"] is False
    Annotation.model_validate_json(canonical_json(projected))


def test_v3_loader_parsing_preserves_original_human_claim_hash():
    from evals.intelligence_v1.loader import parse_model

    row = probe()
    annotation = parse_model(Annotation, row)
    review = annotation.initial_label.claim_reviews[0]
    assert review.evidence_refs[0].direction == "contradicts"
    assert claim_review_sha256(review) == sha256_bytes(
        canonical_json(row["initial_label"]["claim_reviews"][0]).encode())


@pytest.mark.parametrize("field,value", [("relation", "syndicated"), ("record_origin", "authored")])
def test_v3_input_rejects_legacy_word_or_invalid_origin_without_repair(field, value):
    from evals.intelligence_v1.human_inputs import project_annotation

    row = probe()
    row["initial_label"]["document_relations"][0][field] = value
    before = copy.deepcopy(row)
    with pytest.raises(ValueError):
        project_annotation(canonical_json(row).encode())
    assert row == before


@pytest.mark.parametrize("word", ["refutes", "unknown"])
def test_v3_rejects_non_human_direction(word):
    from evals.intelligence_v1.human_inputs import project_annotation

    row = probe()
    row["initial_label"]["claim_reviews"][0]["evidence_refs"][0]["direction"] = word
    with pytest.raises(ValueError):
        project_annotation(canonical_json(row).encode())


def test_legacy_machine_annotation_contract_still_accepts_legacy_words():
    row = probe()
    row.update(guide_revision="g1a-guide-v2", annotation_version="g1a-annotation-v1")
    row["initial_label"]["document_relations"][0]["relation"] = "syndicated"
    row["initial_label"]["claim_reviews"][0]["evidence_refs"][0]["direction"] = "refutes"
    assert Annotation.model_validate_json(canonical_json(row)).guide_revision == "g1a-guide-v2"


def test_v3_unknown_version_pair_is_rejected():
    from evals.intelligence_v1.human_inputs import project_annotation

    row = probe()
    row["annotation_version"] = "g1a-annotation-v1"
    with pytest.raises(ValueError):
        project_annotation(canonical_json(row).encode())


def test_v3_inspection_checks_all_rows_and_never_repairs_origin():
    from evals.intelligence_v1.human_inputs import inspect_submission

    first, second = probe(), probe()
    first["initial_label"]["document_relations"][0]["record_origin"] = "authored"
    second["annotation_id"] = "other"
    raw = (canonical_json(first)+"\n"+canonical_json(second)+"\n").encode()
    result = inspect_submission(raw)
    assert result["format_check"] == "FAIL"
    assert result["record_count"] == 2
    assert result["errors"] == [{"line": 1, "code": "SCHEMA_INVALID", "path": [
        "initial_label", "document_relations", 0, "record_origin"]}]
    assert result["source_sha256"] == sha256_bytes(raw)
    assert result["formal_import_ready"] is False


def test_v3_inspection_rejects_duplicate_json_keys_and_empty_input():
    from evals.intelligence_v1.human_inputs import inspect_submission

    assert inspect_submission(b'{}\n')['format_check'] == 'FAIL'
    assert inspect_submission(b'')['format_check'] == 'FAIL'
    assert inspect_submission(b'{"annotation_id":"a","annotation_id":"b"}\n')['format_check'] == 'FAIL'


def test_v3_support_input_and_source_hash_keep_original_human_direction():
    from evals.intelligence_v1.contracts import SupportReview
    from evals.intelligence_v1.loader import parse_model

    row = probe()
    claim = row['initial_label']['claim_reviews'][0]
    review = dict(support_review_id='synthetic-only', timeline_id=row['timeline_id'], step_id=row['step_id'],
        persona_version_id=row['persona_version_id'], annotation_version=row['annotation_version'],
        prior_annotation_ids=['synthetic-A','synthetic-B'], claim_text=claim['claim_text'],
        evidence_refs=claim['evidence_refs'], scope=claim['scope'], semantic_support=claim['semantic_support'],
        reason='Synthetic contract probe', reviewed_by='NOT-HUMAN-PROBE', reviewed_at='2026-10-23T02:00:00Z')
    model = parse_model(SupportReview,review)
    assert model.evidence_refs[0].direction == 'contradicts'


@pytest.mark.parametrize('future', [False, True])
def test_v3_correction_relation_can_reference_retained_old_material_not_future(bundle, future):
    from pr5_support import complete_contract_probe, save_rows

    from evals.intelligence_v1.annotations import audit_annotations, submission_bytes
    from evals.intelligence_v1.loader import parse_model
    from evals.intelligence_v1.validate import validate_dataset

    _, annotations, _, _, session = complete_contract_probe(bundle)
    for annotation in annotations:
        if (annotation['timeline_id'],annotation['step_id']) == ('DEV-02','D2') and \
                'd02:release:2' in annotation['initial_label']['document_version_ids']:
            annotation['initial_label']['document_relations'] = [dict(
                left_doc_version_id='d02:release:2',
                right_doc_version_id='d02:test:1' if future else 'd02:release:1',
                relation='correction_of', rationale='SYNTHETIC CONTRACT PROBE',
                evidence_at='2026-03-03T12:00:00Z', record_origin='synthetic',
                provenance_uri='DEV-02/README.md')]
    for participant in session['participants']:
        participant['submission_sha256'] = sha256_bytes(submission_bytes([
            parse_model(Annotation,a) for a in annotations if a['annotator_id']==participant['annotator_id']]))
    save_rows(bundle,'labels/g1a_v1/annotations.jsonl',annotations)
    (bundle/'labels/review_session.json').write_bytes((canonical_json(session)+'\n').encode())
    manifest=refresh(bundle)
    result=audit_annotations(manifest,manifest_sha256=sha256_bytes(manifest.read_bytes()))
    if future:
        assert 'FUTURE_EVIDENCE' in {e['code'] for e in result['errors']}
    else:
        assert result['human_gate']=='PASS'  # Synthetic technical probe ONLY.
        assert validate_dataset(manifest).ok


def review_probe():
    row = probe()
    label = copy.deepcopy(row['initial_label'])
    label.update(review_id='review-contract-only',reviewer='contract-joint-review',
                 reviewed_at='2026-10-23T02:00:00Z',guide_revision='g1a-guide-v3',
                 annotation_version='g1a-annotation-v2')
    label['claim_reviews'][0].update(claim_id='review:claim:1',derived_from='initial_label.claim_reviews[0]',
        layer='capability',support_note='Synthetic probe only')
    row['review_label']=label
    return row


def test_joint_review_extraction_binds_source_without_replacing_initial_judgments():
    from evals.intelligence_v1.human_inputs import extract_review_label, inspect_submission

    row=review_probe()
    before=copy.deepcopy(row)
    raw=canonical_json(row).encode()
    result=extract_review_label(raw)
    assert row==before
    assert result['original_review']==row['review_label']
    assert result['source_sha256']==sha256_bytes(raw)
    assert result['source_claim_links'][0]['original_claim_sha256']==sha256_bytes(
        canonical_json(row['initial_label']['claim_reviews'][0]).encode())
    assert result['review_judgment_projection']==row['initial_label']
    assert result['initial_submission_replaced'] is False
    assert result['formal_import_ready'] is False
    assert inspect_submission(raw,layer='received')['format_check']=='FAIL'
    assert inspect_submission(raw,layer='initial')['format_check']=='PASS'
    assert inspect_submission(raw,layer='review')['format_check']=='PASS'


def test_joint_review_missing_source_claim_is_rejected():
    from evals.intelligence_v1.human_inputs import extract_review_label

    row=review_probe()
    row['review_label']['claim_reviews'][0]['derived_from']='initial_label.claim_reviews[99]'
    with pytest.raises(ValueError,match='REVIEW_LINEAGE_MISSING'):
        extract_review_label(canonical_json(row).encode())


@pytest.mark.parametrize('paragraph_form', ['omitted', 'explicit-null'])
def test_T17_review_source_hash_with_optional_paragraph_connects_to_formal_audit(bundle, paragraph_form):
    from test_support_review_lineage import persist, support_probe

    from evals.intelligence_v1.annotations import audit_annotations
    from evals.intelligence_v1.human_inputs import extract_review_label
    from evals.intelligence_v1.validate import validate_dataset

    annotations,session,review,selected=support_probe(bundle)
    for annotation,source in zip(selected,review['source_claim_alignment']['sources'],strict=True):
        original=annotation['initial_label']['claim_reviews'][0]
        if paragraph_form=='omitted':
            original['evidence_refs'][0].pop('paragraph_id')
        else:
            original['evidence_refs'][0]['paragraph_id']=None
        reviewed=copy.deepcopy(annotation['initial_label'])
        reviewed.update(review_id='review-'+annotation['annotation_id'],reviewer='CONTRACT-PROBE-ONLY',
            reviewed_at='2026-10-22T03:30:00Z',guide_revision='g1a-guide-v3',annotation_version='g1a-annotation-v2')
        for i,claim in enumerate(reviewed['claim_reviews']):
            claim.update(claim_id=f'review-claim-{i}',derived_from=f'initial_label.claim_reviews[{i}]',
                         layer='occurrence',support_note='Fabricated optional-field probe, not human evidence')
        received={**annotation,'review_label':reviewed}
        result=extract_review_label(canonical_json(received).encode())
        source['claim_sha256']=result['source_claim_links'][0]['original_claim_sha256']
        if paragraph_form=='omitted':
            assert source['claim_sha256']!=result['source_claim_links'][0]['original_claim_raw_sha256']
        assert result['original_review']==reviewed
    manifest=persist(bundle,annotations,session,review)
    before=(bundle/'labels/g1a_v1/annotations.jsonl').read_bytes()
    audit=audit_annotations(manifest,manifest_sha256=sha256_bytes(manifest.read_bytes()))
    assert audit['errors']==[]
    assert audit['human_gate']=='PASS'  # Fabricated contract probe ONLY.
    assert validate_dataset(manifest,strict=True).ok
    assert (bundle/'labels/g1a_v1/annotations.jsonl').read_bytes()==before
