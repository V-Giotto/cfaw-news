"""AI development evidence is explicit, complete and never human gold."""
import copy
import json
from pathlib import Path

import pytest

from evals.intelligence_v1.ai_development import audit_development, verify_records
from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.hashing import canonical_json, sha256_bytes
from evals.intelligence_v1.loader import load_bundle

ROOT = Path(__file__).resolve().parents[2] / 'evals/intelligence_v1'


@pytest.fixture(scope='module')
def evidence():
    manifest = ROOT/'manifests/dataset_manifest.json'
    data = load_bundle(manifest, manifest_sha256=sha256_bytes(manifest.read_bytes()))
    directory = ROOT/'labels/ai_development'
    return data, *(json.loads((directory/name).read_bytes()) for name in ('batch.json', 'draft.json', 'review.json'))


def digest(value):
    return sha256_bytes((canonical_json(value)+'\n').encode())


def test_T17_AI_batch_covers_all_five_stories_without_human_claims(evidence):
    data, batch, drafts, reviews = evidence
    result = audit_development(data)
    assert result['status'] == 'PASS'
    assert result['primary_steps'] == 26 and result['event_records'] == 47
    assert result['human_evidence'] is False and result['independent_validation'] is False
    assert result['agreement_kappa'] is None
    assert result['disagreement_status'] == 'not_applicable_single_ai'
    assert all(r['executor_type'] == 'ai' for r in [*drafts, *reviews])
    assert batch['source_material_origin'] == 'synthetic'


@pytest.mark.parametrize('defect', [
    'missing_review', 'duplicate_review', 'packet', 'source_hash', 'future_reference',
    'cross_family', 'old_member', 'unlocated_paragraph', 'backdated_processing_time',
    'human_executor', 'independence_claim', 'mentions_as_support', 'missing_claims',
    'expectation_mismatch', 'review_hash', 'input_pin', 'generic_scope',
])
def test_T17_AI_evidence_rejects_missing_or_forged_lineage_even_after_rehash(evidence, defect):
    data, original, initial, final = evidence
    batch, drafts, reviews = copy.deepcopy((original, initial, final))
    row = next(r for r in reviews if r['timeline_id'] == 'DEV-01' and r['step_id'] == 'D0')
    if defect == 'missing_review':
        reviews.remove(row)
    elif defect == 'duplicate_review':
        reviews.append(copy.deepcopy(row))
    elif defect == 'packet':
        row['packet_sha256'] = '0'*64
    elif defect == 'source_hash':
        row['previous_record_sha256'] = '0'*64
    elif defect in {'future_reference', 'cross_family', 'unlocated_paragraph'}:
        ref = row['judgment']['claim_reviews'][0]['evidence_refs'][0]
        ref['doc_version_id'] = 'd01:a:2' if defect == 'future_reference' else 'd02:release:1' if defect == 'cross_family' else 'd01:a:1'
        if defect == 'unlocated_paragraph':
            ref['paragraph_id'] = 'missing'
    elif defect == 'old_member':
        row = next(r for r in reviews if r['timeline_id'] == 'DEV-01' and r['step_id'] == 'D5')
        row['judgment']['document_version_ids'].append('d01:a:1')
    elif defect == 'backdated_processing_time':
        row['generated_at'] = '2026-01-01T12:00:00Z'
    elif defect == 'human_executor':
        row['executor_type'] = 'human'
    elif defect == 'independence_claim':
        row['independent_validation'] = True
    elif defect == 'mentions_as_support':
        claim = row['judgment']['claim_reviews'][0]
        claim['semantic_support'] = 'supported'
        for ref in claim['evidence_refs']:
            ref['direction'] = 'mentions'
    elif defect == 'missing_claims':
        row['judgment']['claim_reviews'] = []
    elif defect == 'expectation_mismatch':
        row['judgment']['tier'] = 'focus' if row['judgment']['tier'] != 'focus' else 'hold'
    elif defect == 'input_pin':
        batch['input_manifest_sha256'] = '0'*64
    elif defect == 'generic_scope':
        row['judgment']['claim_reviews'][0]['scope'] = 'Only the supplied scenario, as stated in the document.'
    batch['draft_sha256'] = digest(drafts)
    batch['review_sha256'] = digest(reviews) if defect != 'review_hash' else '0'*64
    with pytest.raises(ContractError):
        verify_records(data, batch, drafts, reviews)


def test_T20_AI_reference_payloads_remain_outside_prediction_roles(evidence):
    from evals.intelligence_v1.loader import PREDICTION_ROLES

    data, *_ = evidence
    entries = [e for e in data.manifest.file_hashes if e.path.startswith('labels/ai_development/')]
    assert {Path(e.path).name for e in entries} >= {'batch.json', 'draft.json', 'review.json'}
    assert all(e.role == 'support' and e.role not in PREDICTION_ROLES for e in entries)
    assert not any((ROOT/'labels/g1a_v1'/name).read_bytes().strip()
                   for name in ('annotations.jsonl', 'adjudications.jsonl', 'gold.jsonl', 'support_reviews.jsonl'))


def test_T17_old_expectations_cannot_be_silently_deduplicated(evidence, monkeypatch):
    from evals.intelligence_v1 import ai_development

    data, batch, drafts, reviews = evidence
    original = ai_development.reference_records

    def duplicated(bundle, role):
        rows = original(bundle, role)
        return [*rows, next(r for r in rows if r['timeline_id'] == 'DEV-01')] if role == 'fixture_expectations' else rows

    monkeypatch.setattr(ai_development, 'reference_records', duplicated)
    with pytest.raises(ContractError, match='AI_DEVELOPMENT_EXPECTATIONS_INVALID'):
        verify_records(data, batch, drafts, reviews)


def test_T05_unacknowledged_revisits_do_not_become_known_from_AI_history(evidence):
    from evals.intelligence_v1.loader import load_step

    data, _, _, reviews = evidence
    for row in reviews:
        if not row['event_id'].endswith(':release'):
            continue
        context, _ = load_step(data, timeline_id=row['timeline_id'], step_id=row['step_id'], config=data.config)
        assert context.persona.knowledge_known == ()
        assert not any(e.kind == 'acknowledged' for e in context.exposure_history)
        assert row['judgment']['novelty_to_persona'] > 0
        if row['step_id'] == 'D8':
            assert row['judgment']['tier'] == 'focus'
            assert row['judgment']['graded_relevance'] == 3


def test_T05_zero_novelty_without_confirmed_knowledge_is_rejected(evidence):
    data, original, drafts, final = evidence
    batch, reviews = copy.deepcopy((original, final))
    row = next(r for r in reviews if r['timeline_id'] == 'DEV-04' and r['step_id'] == 'D8'
               and r['event_id'].endswith(':release'))
    row['judgment']['novelty_to_persona'] = 0
    batch['review_sha256'] = digest(reviews)
    with pytest.raises(ContractError, match='AI_DEVELOPMENT_KNOWLEDGE_INVALID'):
        verify_records(data, batch, drafts, reviews)


@pytest.mark.parametrize('source', ['explicit_versions', 'acknowledged_card'])
def test_T05_confirmed_version_knowledge_can_support_known_archive(evidence, source):
    from types import SimpleNamespace

    from evals.intelligence_v1.ai_development import validate_personal_novelty

    _, _, _, reviews = evidence
    row = next(r for r in reviews if r['timeline_id'] == 'DEV-04' and r['step_id'] == 'D8'
               and r['event_id'].endswith(':release'))
    members = row['judgment']['document_version_ids']
    context = SimpleNamespace(persona=SimpleNamespace(knowledge_known=tuple(members) if source == 'explicit_versions' else ()),
        exposure_history=(SimpleNamespace(kind='acknowledged', delivery_id='control', event_prediction_id='predicted:control'),)
            if source == 'acknowledged_card' else (),
        delivery_history=(SimpleNamespace(delivery_id='control', event_prediction_id='predicted:control',
            members=[SimpleNamespace(doc_version_id=m) for m in members]),))
    judgment = SimpleNamespace(document_version_ids=members, novelty_to_persona=0, tier='archive', graded_relevance=1)
    validate_personal_novelty(context, judgment)


def test_T05_knowing_the_old_release_does_not_acknowledge_its_correction():
    from types import SimpleNamespace

    from evals.intelligence_v1.ai_development import validate_personal_novelty

    context = SimpleNamespace(persona=SimpleNamespace(knowledge_known=('d04:release:1',)),
        exposure_history=(), delivery_history=())
    judgment = SimpleNamespace(document_version_ids=['d04:release:2', 'd04:test:1'], novelty_to_persona=0)
    with pytest.raises(ContractError, match='AI_DEVELOPMENT_KNOWLEDGE_INVALID'):
        validate_personal_novelty(context, judgment)


@pytest.mark.parametrize('defect', ['all_materials', 'documents', 'personas', 'steps', 'baseline_config', 'role_change', 'duplicate'])
def test_T17_input_snapshot_cannot_omit_materials_after_rehash(evidence, monkeypatch, defect):
    from evals.intelligence_v1 import ai_development

    data, original_batch, drafts, reviews = evidence
    batch = copy.deepcopy(original_batch)
    snapshot = json.loads((ROOT/'labels/ai_development/input_manifest.json').read_bytes())
    if defect == 'all_materials':
        snapshot['file_hashes'] = [next(e for e in snapshot['file_hashes'] if e['role'] == 'schema')]
    elif defect in {'documents', 'personas', 'steps', 'baseline_config'}:
        snapshot['file_hashes'].remove(next(e for e in snapshot['file_hashes'] if e['role'] == defect))
    elif defect == 'role_change':
        next(e for e in snapshot['file_hashes'] if e['role'] == 'documents')['role'] = 'support'
    else:
        snapshot['file_hashes'].append(copy.deepcopy(next(e for e in snapshot['file_hashes'] if e['role'] == 'documents')))
    raw = (canonical_json(snapshot)+'\n').encode()
    batch['input_manifest_sha256'] = sha256_bytes(raw)
    original_read = ai_development.read_entry

    def rehashed(bundle_root, entry):
        return raw if entry.path == 'labels/ai_development/input_manifest.json' else original_read(bundle_root, entry)

    # Simulate a new outer manifest hash, not a stale-byte failure; the material
    # inventory itself must still be checked for exact completeness.
    monkeypatch.setattr(ai_development, 'read_entry', rehashed)
    with pytest.raises(ContractError, match='AI_DEVELOPMENT_INPUT_INVALID'):
        verify_records(data, batch, drafts, reviews)
