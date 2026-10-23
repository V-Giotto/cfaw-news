"""Development may proceed without humans; missing technical/label evidence still fails."""

import json
import xml.etree.ElementTree as ET
from types import SimpleNamespace

import pytest

from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.hashing import canonical_json, sha256_bytes


def check_probe(tmp_path, monkeypatch, defect=None):
    """Temporary evidence doubles, not a record of actual executed tests."""
    from evals.intelligence_v1 import acceptance
    from evals.intelligence_v1.contracts import FileEntry

    bundle = tmp_path/'bundle'
    (bundle/'manifests').mkdir(parents=True)
    manifest = bundle/'manifests/dataset_manifest.json'
    manifest.write_bytes(b'{}')
    legacy = [f'tests.test_probe::test_legacy_{i}' for i in range(125)]
    requirements = {f'T{i:02}': [f'tests.evals.test_temporal_probe::test_T{i:02}']
                    for i in range(1, 27) if i != 25}
    required = [*legacy, *(n for nodes in requirements.values() for n in nodes),
                'tests.evals.test_pr5_acceptance::test_probe_a',
                'tests.evals.test_pr5_acceptance::test_probe_b']
    fingerprints = {'tests/test_probe.py': 'a'*64}
    inventory = dict(revision='g1-required-tests-v1', nodes=required,
        requirements=requirements, not_applicable={'T25': 'No production migration'},
        test_source_sha256=fingerprints, skip_exemptions=[])
    inventory_path = bundle/'manifests/required_tests.json'
    inventory_path.write_bytes((canonical_json(inventory)+'\n').encode())
    entry = FileEntry(path='manifests/required_tests.json', role='support',
                      sha256=sha256_bytes(inventory_path.read_bytes()), record_count=None)
    data = SimpleNamespace(root=bundle, manifest=SimpleNamespace(file_hashes=[entry]))
    out = tmp_path/'.local/evals/g1/pr5/checks'
    out.mkdir(parents=True)
    monkeypatch.setattr(acceptance, '__file__', str(tmp_path/'evals/intelligence_v1/acceptance.py'))
    monkeypatch.setattr(acceptance, 'source_fingerprints', lambda repo: fingerprints)
    commands = []
    for name in sorted(acceptance.CHECK_NAMES):
        artifact = out/(name+'.xml' if name.startswith('pytest-') else name+'.txt')
        if name.startswith('pytest-'):
            nodes = [n for n in required if name == 'pytest-full' or n.startswith('tests.evals.')]
            if defect == 'partial-full' and name == 'pytest-full':
                nodes = [*legacy, *required[-2:]]
            if defect == 'partial-evals' and name == 'pytest-evals':
                nodes = required[-2:]
            suite = ET.Element('testsuite', tests=str(len(nodes)), failures='0', errors='0')
            for i, node in enumerate(nodes):
                classname, test = node.split('::')
                case = ET.SubElement(suite, 'testcase', classname=classname, name=test)
                if name == 'pytest-full' and i == 125 and defect in {'failure', 'error', 'skip'}:
                    ET.SubElement(case, 'skipped' if defect == 'skip' else defect, message='not exempt')
            if defect == 'duplicate' and name == 'pytest-full':
                suite.append(ET.fromstring(ET.tostring(suite[-1])))
            artifact.write_bytes(ET.tostring(suite))
        else:
            artifact.write_bytes(b'Temporary contract probe only')
        commands.append(dict(name=name, argv=['contract-probe'], exit_code=0,
            artifacts=[dict(path=str(artifact), sha256=sha256_bytes(artifact.read_bytes()))]))
    checks = dict(dataset_manifest_sha256=sha256_bytes(manifest.read_bytes()), source_fingerprints=fingerprints,
        commands=commands, prior_review=dict(status='PASS', head='e1ce349895b06dc57b40b5c5e1f75b50caf411ec',
        manifest_sha256='f2782a4da6ff8e4e34e7fd348d534422219a688564dcfc3553a96f56ad2f46ab',
        thread_id='contract-probe', turn_id='contract-probe'))
    path = out/'checks.json'
    path.write_bytes((canonical_json(checks)+'\n').encode())
    return data, path


@pytest.mark.parametrize('defect,code', [('partial-full', 'REQUIRED_TESTS_INCOMPLETE'),
    ('partial-evals', 'REQUIRED_TESTS_INCOMPLETE'), ('duplicate', 'REQUIRED_TESTS_INCOMPLETE'),
    ('failure', 'REQUIRED_TEST_FAILED'), ('error', 'REQUIRED_TEST_FAILED'), ('skip', 'UNEXEMPT_TEST_SKIP')])
def test_required_test_evidence_rejects_missing_failed_duplicate_or_unexempt_skipped_nodes(tmp_path, monkeypatch, defect, code):
    from evals.intelligence_v1.acceptance import verify_checks

    data, path = check_probe(tmp_path, monkeypatch, defect)
    with pytest.raises(ContractError, match=code):
        verify_checks(data, path)


def test_complete_required_test_evidence_is_accepted(tmp_path, monkeypatch):
    from evals.intelligence_v1.acceptance import verify_checks

    data, path = check_probe(tmp_path, monkeypatch)
    assert verify_checks(data, path)['commands']


@pytest.mark.parametrize('defect,code', [('missing-T01', 'TEST_REQUIREMENTS_INVALID'),
    ('unlisted-node', 'TEST_REQUIREMENTS_INVALID'), ('stale-source', 'TEST_REQUIREMENTS_STALE')])
def test_required_inventory_cannot_drop_Txx_or_use_stale_test_sources(tmp_path, monkeypatch, defect, code):
    from evals.intelligence_v1.acceptance import verify_checks

    data, path = check_probe(tmp_path, monkeypatch)
    inventory_path = data.root/'manifests/required_tests.json'
    inventory = json.loads(inventory_path.read_bytes())
    if defect == 'missing-T01':
        inventory['requirements'].pop('T01')
    elif defect == 'unlisted-node':
        inventory['requirements']['T01'] = ['tests.evals.unknown::test_missing']
    else:
        inventory['test_source_sha256']['tests/test_probe.py'] = 'b'*64
    inventory_path.write_bytes((canonical_json(inventory)+'\n').encode())
    data.manifest.file_hashes[0] = data.manifest.file_hashes[0].model_copy(update={
        'sha256': sha256_bytes(inventory_path.read_bytes())})
    with pytest.raises(ContractError, match=code):
        verify_checks(data, path)


def test_partial_test_evidence_cannot_grant_temporal_or_regression_pass(tmp_path, monkeypatch):
    from evals.intelligence_v1 import acceptance

    data, path = check_probe(tmp_path, monkeypatch, 'partial-full')
    data.steps = []
    data.documents = []
    data.manifest.record_origin_breakdown = SimpleNamespace(real=0, model_dump=lambda: {'real': 0, 'synthetic': 0})
    data.manifest.limitations = ['Temporary contract probe']
    data.manifest.dataset_revision = 'contract-probe'
    monkeypatch.setattr(acceptance, 'load_bundle', lambda *a, **kw: data)
    monkeypatch.setattr(acceptance, 'validate_dataset', lambda *a, **kw: SimpleNamespace(ok=True))
    monkeypatch.setattr(acceptance, 'audit_bundle', lambda *a: {'human_gate': 'BLOCKED'})
    monkeypatch.setattr(acceptance, 'reference_records', lambda *a: [])
    monkeypatch.setattr(acceptance, 'build_report', lambda *a, **kw: {})
    monkeypatch.setattr(acceptance, 'verify_matrix', lambda *a: None)
    result = acceptance.build_acceptance(data.root/'manifests/dataset_manifest.json',
        manifest_sha256=sha256_bytes(b'{}'), runs=tmp_path/'runs', checks_path=path, out=tmp_path/'result')
    assert result['gates']['temporal']['status'] != 'PASS'
    assert result['gates']['regression']['status'] != 'PASS'


def test_acceptance_missing_checks_review_and_humans_cannot_pass():
    from evals.intelligence_v1.acceptance import decide_acceptance

    result = decide_acceptance({'dataset': 'PASS', 'temporal': 'PASS'}, human_gate='BLOCKED',
                               profile='human_research')
    assert result['overall_status'] == 'NOT_MET'
    assert result['g1a_passed'] is False and result['g2_eligible'] is False
    assert result['gates']['human_annotation']['status'] == 'BLOCKED'
    assert result['gates']['regression']['status'] == 'BLOCKED'
    assert result['gates']['migration']['status'] == 'N/A'


def test_acceptance_requires_all_technical_gates_even_when_humans_confirmed():
    from evals.intelligence_v1.acceptance import TECHNICAL_GATES, decide_acceptance

    gates = dict.fromkeys(TECHNICAL_GATES, 'PASS')
    assert decide_acceptance(gates, human_gate='PASS', profile='human_research')['g1a_passed'] is True
    gates['reproduction'] = 'FAIL'
    result = decide_acceptance(gates, human_gate='PASS', profile='human_research')
    assert result['technical_gate'] == 'FAIL' and not result['g1a_passed']


def test_development_acceptance_does_not_require_or_certify_humans():
    from evals.intelligence_v1.acceptance import TECHNICAL_GATES, decide_acceptance

    statuses = {**dict.fromkeys(TECHNICAL_GATES, 'PASS'), 'development_labels': 'PASS'}
    result = decide_acceptance(statuses, human_gate='BLOCKED')
    assert result['acceptance_profile'] == 'ai_development'
    assert result['g1a_passed'] and result['g2_eligible']
    assert result['human_annotation_gate'] == 'BLOCKED'
    assert result['human_research_passed'] is False
    assert result['gates']['human_annotation']['status'] == 'N/A'
    research = decide_acceptance(statuses, human_gate='BLOCKED', profile='human_research')
    assert not research['g1a_passed'] and not research['g2_eligible']


@pytest.mark.parametrize('defect', ['temporal', 'reproduction', 'regression', 'development_labels'])
def test_development_profile_keeps_required_evidence_gates(defect):
    from evals.intelligence_v1.acceptance import TECHNICAL_GATES, decide_acceptance

    statuses = {**dict.fromkeys(TECHNICAL_GATES, 'PASS'), 'development_labels': 'PASS'}
    statuses[defect] = 'FAIL'
    result = decide_acceptance(statuses, human_gate='BLOCKED')
    assert not result['g1a_passed'] and not result['g2_eligible']
    statuses.pop(defect)
    assert not decide_acceptance(statuses, human_gate='BLOCKED')['g1a_passed']


def test_development_labels_require_all_visible_events_not_just_one_per_step(bundle):
    from test_loader import loaded

    from evals.intelligence_v1.acceptance import development_labels_complete
    from evals.intelligence_v1.annotations import reference_records
    from evals.intelligence_v1.build_pr5 import PRIMARY_TIMELINES

    data = loaded(bundle)
    primary = [s for s in data.steps if s.timeline_id in PRIMARY_TIMELINES]
    expected = reference_records(data, 'fixture_expectations')
    assert development_labels_complete(data, primary, expected)
    kept = next(e for e in expected if e['timeline_id'] == 'DEV-01' and e['step_id'] == 'D8')
    incomplete = [e for e in expected if e['timeline_id'] != 'DEV-01' or e['step_id'] != 'D8' or e is kept]
    assert not development_labels_complete(data, primary, incomplete)
    assert not development_labels_complete(data, primary, [*expected, kept])


def test_unknown_acceptance_profile_is_rejected():
    from evals.intelligence_v1.acceptance import decide_acceptance

    with pytest.raises(ContractError, match='ACCEPTANCE_PROFILE_INVALID'):
        decide_acceptance({}, human_gate='BLOCKED', profile='skip_checks')
