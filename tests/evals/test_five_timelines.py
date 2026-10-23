"""PR5 primary stories are development fixtures, never five independent users."""

import json
from collections import Counter

from conftest import SOURCE


def role_rows(role):
    manifest = json.loads((SOURCE / 'manifests/dataset_manifest.json').read_bytes())
    return [json.loads(line) for e in manifest['file_hashes'] if e['role'] == role
            for line in (SOURCE / e['path']).read_bytes().splitlines()]


def test_five_primary_timelines_have_26_states_and_35_versions():
    steps = [s for s in role_rows('steps') if s['timeline_id'].startswith('DEV-')]
    assert Counter(s['timeline_id'] for s in steps) == {
        'DEV-01': 6, 'DEV-02': 5, 'DEV-03': 5, 'DEV-04': 5, 'DEV-05': 5}
    families = {f for s in steps for f in s['family_scope_ids']}
    docs = [d for d in role_rows('documents') if d['family_id'] in families]
    assert len(families) == 5 and len(docs) == 35
    assert all(d['record_origin'] == 'synthetic' for d in docs)
    assert all(s['split'] == 'dev' for s in steps)
    expected_days = {'DEV-02': ['D0', 'D1', 'D2', 'D3', 'D8'],
                     'DEV-03': ['D0', 'D1', 'D3', 'D4', 'D8'],
                     'DEV-04': ['D0', 'D3', 'D5', 'D6', 'D8'],
                     'DEV-05': ['D0', 'D1', 'D2', 'D3', 'D8']}
    for timeline, days in expected_days.items():
        assert [s['step_id'] for s in steps if s['timeline_id'] == timeline] == days


def test_every_story_has_authored_no_change_old_value_and_distinct_events():
    expected = role_rows('fixture_expectations')
    events = role_rows('events')
    for number in range(1, 6):
        timeline = f'DEV-{number:02}'
        labels = [x for x in expected if x['timeline_id'] == timeline]
        assert any(x['material_change'] == 'no_change' for x in labels)
        assert any(x['step_id'] == 'D8' and x['tier'] == 'focus' and x['graded_relevance'] == 3 for x in labels)
        assert len([e for e in events if e['family_id'] == f'family:dev{number:02}']) >= 2
    assert not (SOURCE / 'labels/annotations.jsonl').read_bytes()
    assert not (SOURCE / 'labels/gold.jsonl').read_bytes()


def test_old_jsonl_records_are_preserved_byte_for_byte():
    import hashlib
    import subprocess

    paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', 'e1ce349',
                                    '--', 'evals/intelligence_v1'], text=True).splitlines()
    for path in paths:
        if path.endswith('.jsonl'):
            before = subprocess.check_output(['git', 'show', f'e1ce349:{path}'])
            assert hashlib.sha256((SOURCE.parents[1] / path).read_bytes()).digest() == (
                hashlib.sha256(before).digest()), path


def test_new_stories_keep_old_versions_and_T19_persona_fact_boundary():
    from test_loader import step

    context, early = step(name='D1', timeline='DEV-02')
    _, corrected = step(name='D2', timeline='DEV-02')
    assert next(d for d in early if d.document_id == 'd02:release').doc_version_id == 'd02:release:1'
    assert next(d for d in corrected if d.document_id == 'd02:release').doc_version_id == 'd02:release:2'
    assert all('CORRECTION' not in p.text for d in early for p in d.paragraphs)
    before, docs_before = step(name='D1', timeline='DEV-05')
    after, docs_after = step(name='D2', timeline='DEV-05')
    assert docs_before == docs_after
    assert before.persona.persona_version_id != after.persona.persona_version_id
    assert before.persona.knowledge_known == after.persona.knowledge_known == ()


def test_T21_unknown_coverage_cannot_supply_a_no_change_reference():
    from test_loader import step

    from evals.intelligence_v1.metrics import coverage_gaps

    for label in role_rows('fixture_expectations'):
        if not label['timeline_id'].startswith('DEV-') or label['material_change'] != 'no_change':
            continue
        context, _ = step(name=label['step_id'], timeline=label['timeline_id'])
        assert coverage_gaps(context)['coverage_gap_count'] == 0, (label['timeline_id'], label['step_id'])


def test_distributed_templates_match_current_annotation_and_guide_protocol():
    from evals.intelligence_v1.build_pr5 import ANNOTATION_VERSION, GUIDE_REVISION

    session = json.loads((SOURCE/'labels/review_session.json').read_bytes())
    for number in range(2, 6):
        template = json.loads((SOURCE/f'DEV-{number:02}/annotation_template.json').read_bytes())
        assert template['guide_revision'] == session['guide_revision'] == GUIDE_REVISION
        assert template['annotation_version'] == session['annotation_version'] == ANNOTATION_VERSION


def test_first_visible_primary_events_are_new_regardless_of_importance():
    steps = [s for s in role_rows('steps') if s['timeline_id'].startswith('DEV-')]
    events = {e['event_id']: e for e in role_rows('events')}
    for label in role_rows('fixture_expectations'):
        if not label['timeline_id'].startswith('DEV-'):
            continue
        event = events[label['event_id']]
        visible = [s for s in steps if s['timeline_id'] == label['timeline_id']
                   and set(s['visible_doc_version_ids']) & set(event['document_version_ids'])]
        first = min(visible, key=lambda s: s['as_of'])
        if label['step_id'] == first['step_id']:
            assert label['material_change'] == 'new', (label['timeline_id'], label['event_id'])
    theme = next(g for g in role_rows('fixture_expectations') if g['event_id'] == 'd01:event:theme')
    assert theme['tier'] == 'archive' and theme['graded_relevance'] == 0
    from evals.intelligence_v1.build_pr5 import dev01_expectations

    legacy_theme = next(g for g in dev01_expectations(SOURCE) if g['event_id'] == 'd01:event:theme')
    assert legacy_theme['material_change'] == 'new'
    assert legacy_theme['tier'] == 'archive' and legacy_theme['graded_relevance'] == 0
    assert theme['provenance_uri'] == 'labels/ai_development/batch.json'
