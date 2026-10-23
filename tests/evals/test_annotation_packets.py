"""Single-step v2 packets include known history without reference answers."""

import json

import pytest
from conftest import refresh
from test_loader import loaded

from evals.intelligence_v1.build_pr5 import GUIDE_FILE
from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.hashing import sha256_bytes


def test_v2_packet_history_and_temporal_projection(bundle, tmp_path):
    from evals.intelligence_v1.annotations import AI_GUIDE_FILE, export_packet

    manifest = refresh(bundle)
    pin = sha256_bytes(manifest.read_bytes())
    raw = []
    for suffix in ('a', 'b'):
        out = tmp_path / suffix
        export_packet(manifest, manifest_sha256=pin, timeline_id='DEV-02', step_id='D8',
                      out=out)
        raw.append((out / 'packet.json').read_bytes())
        assert {p.name for p in out.iterdir()} == {'packet.json', 'blank_form.json', 'metadata.json',
            'field_templates.json', 'submission.schema.json', GUIDE_FILE, AI_GUIDE_FILE}
        metadata = json.loads((out / 'metadata.json').read_bytes())
        assert metadata['default_acceptance_profile'] == 'ai_development'
        assert metadata['ai_guide_sha256'] == sha256_bytes((out / AI_GUIDE_FILE).read_bytes())
    assert raw[0] == raw[1]
    packet = json.loads(raw[0])
    assert packet['packet_revision'] == 'g1a-packet-v2'
    assert packet['context']['delivery_history']
    assert packet['context']['exposure_history']
    for forbidden in ('family_id', 'family_scope_ids', 'verification_state', 'graded_relevance',
                      'reference_event_id_for_fixture', 'adjudication_status'):
        assert forbidden not in raw[0].decode()
    assert packet['context']['persona']['knowledge_known'] == []


def test_v2_packet_does_not_interpret_future_body_or_future_feedback(bundle, tmp_path):
    from evals.intelligence_v1.annotations import export_packet

    path = bundle / 'DEV-02/documents.jsonl'
    rows = [json.loads(x) for x in path.read_bytes().splitlines()]
    rows[1]['paragraphs'] = 'FUTURE_POISON'
    from evals.intelligence_v1.hashing import canonical_json
    path.write_bytes(''.join(canonical_json(r)+'\n' for r in rows).encode())
    manifest = refresh(bundle)
    out = tmp_path / 'early'
    export_packet(manifest, manifest_sha256=sha256_bytes(manifest.read_bytes()),
                  timeline_id='DEV-02', step_id='D0', out=out)
    raw = (out / 'packet.json').read_bytes()
    assert b'FUTURE_POISON' not in raw and b'acknowledged' not in raw
    assert len(json.loads(raw)['documents']) == 1


def test_v2_packet_pin_scope_and_overwrite_guards(bundle, tmp_path):
    from evals.intelligence_v1.annotations import export_packet

    manifest = refresh(bundle)
    args = dict(manifest_sha256=sha256_bytes(manifest.read_bytes()),
                timeline_id='DEV-02', step_id='D0', out=tmp_path / 'valid')
    with pytest.raises(ContractError, match='MANIFEST_SHA_MISMATCH'):
        export_packet(manifest, **{**args, 'manifest_sha256': '0'*64})
    assert not args['out'].exists()
    export_packet(manifest, **args)
    with pytest.raises(ContractError, match='OUTPUT_EXISTS'):
        export_packet(manifest, **args)
    assert loaded(bundle).manifest.dataset_revision == 'independent-test-copy'
