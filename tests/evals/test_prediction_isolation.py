import builtins
import io
import socket
import sys
from pathlib import Path

import pytest
from conftest import refresh
from test_loader import loaded

from evals.intelligence_v1.hashing import sha256_bytes

FORBIDDEN = {"gold", "events", "claims", "annotations", "adjudications", "event_relations",
             "fixture_expectations"}


@pytest.mark.parametrize("algorithm", ["b0", "b1", "b2-predicted", "b3", "b4"])
def test_GROUP01_prediction_does_not_open_reference_files_or_call_network(bundle, tmp_path,
                                                                       monkeypatch, algorithm):
    import json

    from evals.intelligence_v1.replay import run_replay

    manifest = bundle / "manifests/dataset_manifest.json"
    entries = json.loads(manifest.read_bytes())["file_hashes"]
    forbidden = {(bundle/e["path"]).resolve() for e in entries if e["role"] in FORBIDDEN}
    out = tmp_path / "predictions"
    expected = tmp_path / "expected"
    pin = sha256_bytes(manifest.read_bytes())
    run_replay(manifest, manifest_sha256=pin, algorithm_id=algorithm, out=expected, split="dev")
    for path in forbidden:
        path.unlink()

    def wrapper(original):
        def guarded(file, *args, **kwargs):
            if isinstance(file, (str, bytes, Path)):
                path = Path(file).resolve()
                assert path not in forbidden
                assert not any(p.casefold().startswith(".env") or p.casefold().endswith(".db")
                               for p in path.parts)
            return original(file, *args, **kwargs)
        return guarded

    def deny(*args, **kwargs):
        pytest.fail("network attempted")

    with monkeypatch.context() as m:
        m.setattr(builtins, "open", wrapper(builtins.open))
        m.setattr(io, "open", wrapper(io.open))
        m.setattr(socket, "getaddrinfo", deny)
        m.setattr(socket.socket, "connect", deny)
        run_replay(manifest, manifest_sha256=pin, algorithm_id=algorithm, out=out, split="dev")
    assert (out/"predictions.jsonl").read_bytes() == (expected/"predictions.jsonl").read_bytes()


def test_ORACLE01_oracle_is_explicit_and_intersects_visible_candidates(bundle):
    from evals.intelligence_v1.baselines import get_ranker
    from evals.intelligence_v1.exceptions import ContractError
    from evals.intelligence_v1.loader import load_step
    from evals.intelligence_v1.oracle import oracle_groups

    data = loaded(bundle)
    context, candidates = load_step(data, timeline_id="DEV-01", step_id="D0", config=data.config)
    with pytest.raises(ContractError, match="ORACLE_REQUIRES_EXPLICIT_PATH"):
        get_ranker("b2-oracle", data.config)
    groups = oracle_groups(data, candidates, as_of=context.as_of)
    assert [g.doc_version_ids for g in groups] == [("d01:a:1",)]
    assert all(g.predicted_event_id.startswith("oracle:") for g in groups)
    extra = candidates[0].model_copy(update={"document_id": "unmapped",
                                            "doc_version_id": "unmapped:1"})
    unmapped = oracle_groups(data, (*candidates, extra), as_of=context.as_of)
    assert {g.doc_version_ids for g in unmapped} == {("d01:a:1",), ("unmapped:1",)}


@pytest.mark.parametrize("algorithm", ["b2-predicted", "b3", "b4"])
def test_ranking_cli_audits_data_reads_writes_network_and_business_imports(bundle, tmp_path, algorithm):
    import subprocess

    manifest = refresh(bundle)
    script = r'''
import os, sys
from pathlib import Path
from evals.intelligence_v1.replay import main
root, out = Path(sys.argv[1]).resolve(), Path(sys.argv[3]).resolve()
repo = Path.cwd().resolve()
runtime = [Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve()]
code_roots = [*runtime, repo/'evals', repo/'backend/cfaw_news']
locks = {repo/'requirements.lock', repo/'frontend/package-lock.json'}
forbidden = {'gold.jsonl', 'events.jsonl', 'event_relations.jsonl', 'claims.jsonl',
             'annotations.jsonl', 'adjudications.jsonl', 'expectations.jsonl'}
def guard(event, args):
    if event.startswith('socket.'):
        raise AssertionError('network attempted')
    if event == 'open' and isinstance(args[0], (str, bytes)):
        path = Path(args[0]).resolve()
        assert path.name not in forbidden, 'reference answer read'
        assert not any(p.casefold().startswith('.env') or p.casefold().endswith('.db')
                       for p in path.parts), 'sensitive data read'
        if args[2] & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
            assert path.is_relative_to(out), 'outside write'
        else:
            code = path.suffix in {'.py','.pyc','.pyd'} and any(
                path.is_relative_to(p) for p in code_roots)
            assert path.is_relative_to(root) or code or path in locks, 'outside data read'
sys.addaudithook(guard)
status = main(['--manifest', str(root/'manifests/dataset_manifest.json'),
              '--manifest-sha256', sys.argv[2], '--algo', sys.argv[4], '--split', 'dev',
              '--out', str(out)])
assert not any(m.startswith('cfaw_news.') and m != 'cfaw_news.retrieval' for m in sys.modules)
assert 'evals.intelligence_v1.oracle' not in sys.modules
assert 'evals.intelligence_v1.validate' not in sys.modules
sys.exit(status)
'''
    result = subprocess.run([sys.executable, "-B", "-c", script, str(bundle),
                             sha256_bytes(manifest.read_bytes()), str(tmp_path/"audited"), algorithm],
                            capture_output=True, text=True, timeout=25)
    assert result.returncode == 0, result.stderr + result.stdout


def test_prediction_import_graph_does_not_import_reference_reader():
    import subprocess

    script = '''
import sys
from evals.intelligence_v1.baselines import get_ranker
from evals.intelligence_v1.loader import load_bundle
assert "evals.intelligence_v1.oracle" not in sys.modules
assert "evals.intelligence_v1.evaluate" not in sys.modules
assert "evals.intelligence_v1.validate" not in sys.modules
assert not any(x.startswith("cfaw_news.") and x != "cfaw_news.retrieval" for x in sys.modules)
'''
    result = subprocess.run([sys.executable, "-B", "-c", script], capture_output=True,
                            text=True, timeout=20)
    assert result.returncode == 0, result.stderr


def test_future_persona_and_coverage_do_not_enter_context(bundle):
    import json

    from test_loader import step

    from evals.intelligence_v1.exceptions import ContractError

    path = bundle / "timelines/steps.jsonl"
    rows = [json.loads(x) for x in path.read_bytes().splitlines()]
    rows[0]["persona_version_id"] = "dev01:developer:2"
    path.write_bytes("".join(json.dumps(r) + "\n" for r in rows).encode())
    refresh(bundle)
    with pytest.raises(ContractError, match="FUTURE_PERSONA"):
        step(bundle, "D0")
