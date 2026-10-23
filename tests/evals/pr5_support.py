"""Temporary fabricated CONTRACT probes. Never copy these into a real dataset."""

import json
from datetime import datetime, timedelta, timezone

from conftest import refresh

from evals.intelligence_v1.annotations import submission_bytes
from evals.intelligence_v1.build_pr5 import ANNOTATION_VERSION, GUIDE_REVISION, PRIMARY_TIMELINES
from evals.intelligence_v1.contracts import Annotation
from evals.intelligence_v1.hashing import canonical_json, sha256_bytes
from evals.intelligence_v1.loader import load_bundle, load_step
from evals.intelligence_v1.pilot import annotation_packet_v2


def save_rows(root, name, records):
    (root/name).write_bytes(''.join(canonical_json(r)+'\n' for r in records).encode())


def complete_contract_probe(root):
    manifest = refresh(root)
    data = load_bundle(manifest, manifest_sha256=sha256_bytes(manifest.read_bytes()))
    events = [json.loads(line) for e in data.manifest.file_hashes if e.role == 'events'
              for line in (root/e.path).read_bytes().splitlines()]
    annotations, receipts, alignments, gold = [], [], [], []
    epoch = datetime(2026, 10, 22, tzinfo=timezone.utc)
    steps = sorted((s for s in data.steps if s.timeline_id in PRIMARY_TIMELINES),
                   key=lambda s: (s.timeline_id, s.as_of))
    for index, step in enumerate(steps):
        context, candidates = load_step(data, timeline_id=step.timeline_id, step_id=step.step_id, config=data.config)
        packet_hash = sha256_bytes(annotation_packet_v2(context, candidates))
        for reviewer in ('contract-probe-A', 'contract-probe-B'):
            receipts.append(dict(annotator_id=reviewer, timeline_id=step.timeline_id,
                step_id=step.step_id, packet_sha256=packet_hash,
                delivered_at=(epoch+timedelta(minutes=index*3)).isoformat()))
        for event in events:
            members = sorted(set(event['document_version_ids']) & set(context.candidate_doc_version_ids))
            if not members:
                continue
            prior_ids = []
            for reviewer in ('contract-probe-A', 'contract-probe-B'):
                identity = f"{reviewer}:{step.timeline_id}:{step.step_id}:{event['event_id']}"
                prior_ids.append(identity)
                annotations.append(dict(annotation_id=identity, timeline_id=step.timeline_id,
                    step_id=step.step_id, persona_version_id=step.persona_version_id,
                    annotation_version=ANNOTATION_VERSION, annotator_id=reviewer,
                    submitted_at=(epoch+timedelta(minutes=index*3+1)).isoformat(),
                    guide_revision=GUIDE_REVISION, packet_sha256=packet_hash,
                    initial_label=dict(local_event_id=identity, document_version_ids=members,
                        relevance=2, potential_value=2, novelty_to_persona=2, evidence_quality=2,
                        graded_relevance=2, material_change='insufficient', tier='radar',
                        rationale='Temporary contract probe, NOT real human evidence.',
                        uncertainty=['Test only'], document_relations=[], claim_reviews=[])))
            alignments.append(dict(timeline_id=step.timeline_id, step_id=step.step_id,
                persona_version_id=step.persona_version_id, annotation_version=ANNOTATION_VERSION,
                event_id=event['event_id'], prior_annotation_ids=prior_ids, doc_version_ids=members,
                status='matched', reason='Test mapping by visible membership, not by local ID.',
                aligned_by='contract-probe-admin', aligned_at='2026-10-22T03:00:00Z'))
            gold.append(dict(timeline_id=step.timeline_id, step_id=step.step_id,
                persona_version_id=step.persona_version_id, event_id=event['event_id'],
                annotation_version=ANNOTATION_VERSION, relevance=2, potential_value=2,
                novelty_to_persona=2, evidence_quality=2, graded_relevance=2,
                material_change='insufficient', tier='radar', supporting_doc_version_ids=members,
                rationale='Temporary contract probe, NOT real human evidence.', uncertainty=['Test only'],
                adjudication_status='agreed', record_origin='synthetic', provenance_uri=event['provenance_uri']))
    session = json.loads((root/'labels/review_session.json').read_bytes())
    session.update(status='adjudicated', confirmed_by='contract-probe-only-NOT-a-person',
                   confirmed_at='2026-10-22T04:00:00Z', packet_receipts=receipts)
    session['participants'] = [dict(annotator_id=reviewer, real_human_confirmed=True,
        independent_submission_confirmed=True, submission_sha256=sha256_bytes(submission_bytes([
            Annotation.model_validate_json(canonical_json(a)) for a in annotations if a['annotator_id'] == reviewer])),
        frozen_at='2026-10-22T02:00:00Z') for reviewer in ('contract-probe-A', 'contract-probe-B')]
    for name, records in (('annotations', annotations), ('gold', gold), ('event_alignments', alignments)):
        save_rows(root, f'labels/g1a_v1/{name}.jsonl', records)
    (root/'labels/review_session.json').write_bytes((canonical_json(session)+'\n').encode())
    return refresh(root), annotations, alignments, gold, session


def grouping_adjudication_probe(root, kind):
    """Disagreeing raw partitions, then an explicit final mapping; TEST ONLY."""
    from copy import deepcopy

    _, annotations, alignments, gold, session = complete_contract_probe(root)
    step_annotations = [a for a in annotations if a['timeline_id'] == 'DEV-02' and a['step_id'] == 'D1']
    a_release = next(a for a in step_annotations if a['annotator_id'] == 'contract-probe-A'
                     and 'd02:release:1' in a['initial_label']['document_version_ids'])
    a_license = next(a for a in step_annotations if a['annotator_id'] == 'contract-probe-A'
                     and 'd02:license:1' in a['initial_label']['document_version_ids'])
    if kind == 'split':
        members = a_release['initial_label']['document_version_ids']
        extra = deepcopy(a_release)
        extra['annotation_id'] += ':split'
        extra['initial_label']['local_event_id'] += ':split'
        a_release['initial_label']['document_version_ids'] = members[:1]
        extra['initial_label']['document_version_ids'] = members[1:]
        assert extra['initial_label']['document_version_ids']
        annotations.append(extra)
    else:
        a_release['initial_label']['document_version_ids'] = [
            *a_release['initial_label']['document_version_ids'], *a_license['initial_label']['document_version_ids']]
        annotations.remove(a_license)
    decisions = []
    for alignment in alignments:
        if alignment['timeline_id'] != 'DEV-02' or alignment['step_id'] != 'D1':
            continue
        members = set(alignment['doc_version_ids'])
        prior = [a for a in annotations if a['timeline_id'] == 'DEV-02' and a['step_id'] == 'D1'
                 and members & set(a['initial_label']['document_version_ids'])]
        if all(set(a['initial_label']['document_version_ids']) == members for a in prior):
            continue
        alignment['status'] = 'split_merge_disagreement'
        alignment['prior_annotation_ids'] = [a['annotation_id'] for a in prior]
        label = next(g for g in gold if g['timeline_id'] == 'DEV-02' and g['step_id'] == 'D1'
                     and g['event_id'] == alignment['event_id'])
        label['adjudication_status'] = 'adjudicated'
        decisions.append(dict(adjudication_id='contract-probe:'+label['event_id'],
            prior_annotation_ids=alignment['prior_annotation_ids'], final_label=deepcopy(label),
            reason=f'Temporary {kind} disagreement: final members are explicit in alignment; preserve originals.',
            adjudicator_id='contract-probe-admin', adjudicated_at='2026-10-22T03:30:00Z'))
    for participant in session['participants']:
        participant['submission_sha256'] = sha256_bytes(submission_bytes([
            Annotation.model_validate_json(canonical_json(a)) for a in annotations
            if a['annotator_id'] == participant['annotator_id']]))
    for name, records in (('annotations', annotations), ('event_alignments', alignments),
                          ('gold', gold), ('adjudications', decisions)):
        save_rows(root, f'labels/g1a_v1/{name}.jsonl', records)
    (root/'labels/review_session.json').write_bytes((canonical_json(session)+'\n').encode())
    return refresh(root), annotations, alignments, gold, session, decisions
