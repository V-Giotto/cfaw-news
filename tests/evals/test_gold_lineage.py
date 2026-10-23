"""No schema probe or pair of anonymous IDs establishes real independent annotation."""

import json

import pytest
from conftest import refresh
from pr5_support import complete_contract_probe, save_rows
from test_annotation_records import probe, save

from evals.intelligence_v1.hashing import sha256_bytes


def test_no_real_submissions_leaves_human_gate_blocked(bundle):
    from evals.intelligence_v1.annotations import audit_annotations

    manifest = refresh(bundle)
    audit = audit_annotations(manifest, manifest_sha256=sha256_bytes(manifest.read_bytes()))
    assert audit['human_gate'] == 'BLOCKED'
    assert audit['confirmed_human_annotators'] == []
    assert audit['eligible_gold_keys'] == []
    assert audit['agreement']['paired_target_count'] == 0
    assert audit['semantic_support']['value'] is None


def test_two_contract_probe_ids_cannot_unlock_human_gold(bundle):
    from evals.intelligence_v1.annotations import audit_annotations

    save(bundle, 'labels/annotations.jsonl', [probe(bundle), probe(bundle, 'probe-B')])
    manifest = refresh(bundle)
    audit = audit_annotations(manifest, manifest_sha256=sha256_bytes(manifest.read_bytes()))
    assert audit['human_gate'] == 'BLOCKED' and not audit['eligible_gold_keys']
    assert json.loads((bundle / 'labels/review_session.json').read_bytes())['status'] == 'not_started'


def test_complete_temporary_contract_probe_checks_positive_path_without_touching_human_data(bundle):
    from evals.intelligence_v1.annotations import audit_annotations
    from evals.intelligence_v1.validate import validate_dataset

    manifest, *_ = complete_contract_probe(bundle)
    audit = audit_annotations(manifest, manifest_sha256=sha256_bytes(manifest.read_bytes()))
    assert audit['errors'] == []
    assert audit['human_gate'] == 'PASS'  # Attestation is a test double, not real evidence.
    assert len(audit['complete_steps']) == 26
    assert audit['agreement']['event_pairs']['raw_agreement'] == 1
    assert validate_dataset(manifest).ok
    from conftest import SOURCE
    assert (SOURCE/'labels/g1a_v1/annotations.jsonl').read_bytes() == b''


@pytest.mark.parametrize('defect,code', [
    ('packet', 'ANNOTATION_CONTEXT_MISMATCH'), ('alignment', 'EVENT_ALIGNMENT_INVALID'),
    ('missing-prior', 'GOLD_LINEAGE_MISSING'), ('agreed-score', 'GOLD_NOT_AGREED'),
    ('early-alignment', 'ADJUDICATION_BEFORE_FREEZE'), ('duplicate-gold', 'DUPLICATE_ID'),
    ('future-packet', 'FUTURE_PACKET_DISTRIBUTED_EARLY'),
])
def test_primary_gold_rejects_adversarial_lineage(bundle, defect, code):
    from evals.intelligence_v1.annotations import audit_annotations
    from evals.intelligence_v1.hashing import canonical_json

    _, annotations, alignments, gold, session = complete_contract_probe(bundle)
    if defect == 'packet':
        annotations[0]['packet_sha256'] = '0'*64
    elif defect == 'alignment':
        alignments[0]['doc_version_ids'] = ['missing-doc']
    elif defect == 'missing-prior':
        alignments.pop(0)
    elif defect == 'agreed-score':
        gold[0]['graded_relevance'] = 3
    elif defect == 'early-alignment':
        alignments[0]['aligned_at'] = '2026-10-22T01:30:00Z'
    elif defect == 'duplicate-gold':
        gold.append(gold[0])
    elif defect == 'future-packet':
        session['packet_receipts'][2]['delivered_at'] = '2026-10-22T00:00:00Z'
    save_rows(bundle, 'labels/g1a_v1/annotations.jsonl', annotations)
    save_rows(bundle, 'labels/g1a_v1/event_alignments.jsonl', alignments)
    save_rows(bundle, 'labels/g1a_v1/gold.jsonl', gold)
    (bundle/'labels/review_session.json').write_bytes((canonical_json(session)+'\n').encode())
    manifest = refresh(bundle)
    audit = audit_annotations(manifest, manifest_sha256=sha256_bytes(manifest.read_bytes()))
    assert audit['human_gate'] == 'FAIL'
    assert code in {e['code'] for e in audit['errors']}
    assert not audit['eligible_gold_keys']


def test_partial_labels_cannot_turn_unlabelled_events_into_negatives(bundle):
    from evals.intelligence_v1.annotations import audit_annotations

    _, _, _, gold, _ = complete_contract_probe(bundle)
    save_rows(bundle, 'labels/g1a_v1/gold.jsonl', gold[:-1])
    manifest = refresh(bundle)
    audit = audit_annotations(manifest, manifest_sha256=sha256_bytes(manifest.read_bytes()))
    assert audit['human_gate'] == 'BLOCKED' and not audit['eligible_gold_keys']
    assert audit['missing_target_count'] == 1


def test_human_confirmation_must_follow_alignment_and_adjudication(bundle):
    from evals.intelligence_v1.annotations import audit_annotations
    from evals.intelligence_v1.hashing import canonical_json

    _, _, _, _, session = complete_contract_probe(bundle)
    session['confirmed_at'] = '2026-10-22T02:30:00Z'
    (bundle/'labels/review_session.json').write_bytes((canonical_json(session)+'\n').encode())
    manifest = refresh(bundle)
    audit = audit_annotations(manifest, manifest_sha256=sha256_bytes(manifest.read_bytes()))
    assert audit['human_gate'] == 'FAIL'
    assert 'CONFIRMATION_BEFORE_REVIEW_COMPLETED' in {e['code'] for e in audit['errors']}


@pytest.mark.parametrize('missing_prior', [False, True])
def test_T17_human_support_review_has_real_denominator_and_original_claim_lineage(bundle, missing_prior):
    from evals.intelligence_v1.annotations import audit_annotations, submission_bytes
    from evals.intelligence_v1.contracts import Annotation
    from evals.intelligence_v1.hashing import canonical_json

    _, annotations, _, _, session = complete_contract_probe(bundle)
    review = dict(claim_text='The release establishes a million-fold gain on all tasks.',
        evidence_refs=[dict(doc_version_id='d01:a:1', paragraph_id='p1', direction='supports')],
        semantic_support='unsupported', scope='Temporary false-statement contract probe', limitations=['Test only'])
    for annotation in annotations[:2]:
        annotation['initial_label']['claim_reviews'] = [review]
    for p in session['participants']:
        p['submission_sha256'] = sha256_bytes(submission_bytes([
            Annotation.model_validate_json(canonical_json(a)) for a in annotations if a['annotator_id'] == p['annotator_id']]))
    support = dict(support_review_id='contract-probe-support', timeline_id='DEV-01', step_id='D0',
        persona_version_id=annotations[0]['persona_version_id'], annotation_version=annotations[0]['annotation_version'],
        prior_annotation_ids=[a['annotation_id'] for a in annotations[:2]],
        **{k: review[k] for k in ('claim_text', 'evidence_refs', 'semantic_support', 'scope')},
        reason='The existing paragraph does not support that statement; TEST ONLY.',
        reviewed_by='contract-probe-admin', reviewed_at='2026-10-22T03:30:00Z')
    if missing_prior:
        support['prior_annotation_ids'][1] = 'missing-original'
    save_rows(bundle, 'labels/g1a_v1/annotations.jsonl', annotations)
    save_rows(bundle, 'labels/g1a_v1/support_reviews.jsonl', [support])
    (bundle/'labels/review_session.json').write_bytes((canonical_json(session)+'\n').encode())
    manifest = refresh(bundle)
    audit = audit_annotations(manifest, manifest_sha256=sha256_bytes(manifest.read_bytes()))
    if missing_prior:
        assert audit['human_gate'] == 'FAIL'
        assert 'SUPPORT_REVIEW_LINEAGE_INVALID' in {e['code'] for e in audit['errors']}
        assert audit['semantic_support']['value'] is None
    else:
        assert audit['human_gate'] == 'PASS'
        assert audit['semantic_support']['value'] == 0
        assert audit['semantic_support']['denominator'] == 1


@pytest.mark.parametrize('case', ['past-and-current', 'future', 'other-family'])
def test_correction_citations_distinguish_historical_evidence_from_current_candidates(bundle, case):
    from evals.intelligence_v1.annotations import audit_annotations, submission_bytes
    from evals.intelligence_v1.contracts import Annotation
    from evals.intelligence_v1.hashing import canonical_json

    _, annotations, _, gold, session = complete_contract_probe(bundle)
    prior = 'd02:release:1' if case == 'past-and-current' else (
        'd02:test:1' if case == 'future' else 'd01:a:1')
    selected = [a for a in annotations if a['timeline_id'] == 'DEV-02' and a['step_id'] == 'D2'
                and 'd02:release:2' in a['initial_label']['document_version_ids']]
    assert len(selected) == 2
    review = dict(claim_text='The current release corrects the earlier compatibility statement.',
        evidence_refs=[dict(doc_version_id=prior, paragraph_id='p1', direction='mentions'),
                       dict(doc_version_id='d02:release:2', paragraph_id='p1', direction='supports')],
        semantic_support='supported', scope='Historical compatibility comparison; test only.',
        limitations=['Contract probe, not actual people'])
    for a in selected:
        a['initial_label']['claim_reviews'] = [review]
    for g in gold:
        if g['timeline_id'] == 'DEV-02' and g['step_id'] == 'D2' and g['event_id'] == 'd02:event:release':
            g['supporting_doc_version_ids'] = [*g['supporting_doc_version_ids'], prior]
    for p in session['participants']:
        p['submission_sha256'] = sha256_bytes(submission_bytes([
            Annotation.model_validate_json(canonical_json(a)) for a in annotations if a['annotator_id'] == p['annotator_id']]))
    decision = dict(support_review_id='contract-probe-correction', timeline_id='DEV-02', step_id='D2',
        persona_version_id=selected[0]['persona_version_id'], annotation_version=selected[0]['annotation_version'],
        prior_annotation_ids=[a['annotation_id'] for a in selected],
        **{k: review[k] for k in ('claim_text', 'evidence_refs', 'semantic_support', 'scope')},
        reason='Past and current visible evidence are compared; test only.',
        reviewed_by='contract-probe-admin', reviewed_at='2026-10-22T03:30:00Z')
    save_rows(bundle, 'labels/g1a_v1/annotations.jsonl', annotations)
    save_rows(bundle, 'labels/g1a_v1/gold.jsonl', gold)
    save_rows(bundle, 'labels/g1a_v1/support_reviews.jsonl', [decision])
    (bundle/'labels/review_session.json').write_bytes((canonical_json(session)+'\n').encode())
    manifest = refresh(bundle)
    audit = audit_annotations(manifest, manifest_sha256=sha256_bytes(manifest.read_bytes()))
    if case == 'past-and-current':
        assert audit['errors'] == []
        assert audit['human_gate'] == 'PASS'
        assert audit['semantic_support']['value'] == 1
        from evals.intelligence_v1.validate import validate_dataset

        assert validate_dataset(manifest, strict=True).ok
    else:
        assert audit['human_gate'] == 'FAIL'
        assert not audit['eligible_gold_keys']


@pytest.mark.parametrize('kind', ['split', 'merge'])
def test_adjudicated_grouping_disagreement_preserves_raw_partitions_and_statistics(bundle, kind):
    from pr5_support import grouping_adjudication_probe

    from evals.intelligence_v1.annotations import audit_annotations
    from evals.intelligence_v1.validate import validate_dataset

    manifest, _, _, _, _, decisions = grouping_adjudication_probe(bundle, kind)
    initial = (bundle/'labels/g1a_v1/annotations.jsonl').read_bytes()
    audit = audit_annotations(manifest, manifest_sha256=sha256_bytes(manifest.read_bytes()))
    assert audit['errors'] == []
    assert audit['human_gate'] == 'PASS'  # Temporary attestation double, not actual humans.
    assert audit['missing_target_count'] == 0 and len(audit['complete_steps']) == 26
    assert audit['agreement']['event_pairs']['raw_agreement'] < 1
    assert len(audit['agreement']['unmatched_targets']) == len(decisions)
    assert validate_dataset(manifest, strict=True).ok
    assert (bundle/'labels/g1a_v1/annotations.jsonl').read_bytes() == initial


@pytest.mark.parametrize('kind', ['split', 'merge'])
def test_unresolved_grouping_disagreement_remains_blocked(bundle, kind):
    from pr5_support import grouping_adjudication_probe

    from evals.intelligence_v1.annotations import audit_annotations

    _, _, alignments, gold, _, _ = grouping_adjudication_probe(bundle, kind)
    for g in gold:
        if g['adjudication_status'] == 'adjudicated':
            g['adjudication_status'] = 'unresolved'
    for alignment in alignments:
        if alignment['status'] == 'split_merge_disagreement':
            alignment['status'] = 'unresolved'
    save_rows(bundle, 'labels/g1a_v1/gold.jsonl', gold)
    save_rows(bundle, 'labels/g1a_v1/event_alignments.jsonl', alignments)
    save_rows(bundle, 'labels/g1a_v1/adjudications.jsonl', [])
    manifest = refresh(bundle)
    audit = audit_annotations(manifest, manifest_sha256=sha256_bytes(manifest.read_bytes()))
    assert audit['human_gate'] == 'BLOCKED' and not audit['eligible_gold_keys']
    assert audit['missing_target_count'] > 0
    assert audit['agreement']['event_pairs']['raw_agreement'] < 1


@pytest.mark.parametrize('defect', ['missing-decision', 'missing-overlap', 'wrong-final-members',
                                  'before-freeze', 'fake-matched'])
def test_grouping_adjudication_rejects_incomplete_or_rewritten_lineage(bundle, defect):
    from pr5_support import grouping_adjudication_probe

    from evals.intelligence_v1.annotations import audit_annotations

    _, _, alignments, _, _, decisions = grouping_adjudication_probe(bundle, 'split')
    alignment = next(a for a in alignments if a['status'] == 'split_merge_disagreement')
    if defect == 'missing-decision':
        decisions = []
    elif defect == 'missing-overlap':
        alignment['prior_annotation_ids'] = alignment['prior_annotation_ids'][1:]
        decisions[0]['prior_annotation_ids'] = alignment['prior_annotation_ids']
    elif defect == 'wrong-final-members':
        alignment['doc_version_ids'] = alignment['doc_version_ids'][:1]
    elif defect == 'before-freeze':
        decisions[0]['adjudicated_at'] = '2026-10-22T01:30:00Z'
    else:
        alignment['status'] = 'matched'
    save_rows(bundle, 'labels/g1a_v1/event_alignments.jsonl', alignments)
    save_rows(bundle, 'labels/g1a_v1/adjudications.jsonl', decisions)
    manifest = refresh(bundle)
    audit = audit_annotations(manifest, manifest_sha256=sha256_bytes(manifest.read_bytes()))
    assert audit['human_gate'] == 'FAIL' and not audit['eligible_gold_keys']
