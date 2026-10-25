import json
import subprocess
import sys

import pytest

from evals.intelligence_g2.contracts import ROOT

from ..support import output_path
from .support import CONFIG, FIXTURES, pin


@pytest.mark.parametrize("kind", ["fixture", "g1"])
def test_T18_audited_prediction_never_stats_references_or_reads_private_data(tmp_path, kind):
    # Canary is synthetic. The real user database is never read, including for fingerprints.
    canary = tmp_path / "canary.db"
    canary.write_bytes(b"PR2 synthetic database canary")
    before = canary.read_bytes()
    output = output_path()
    script = r'''
import os,sys
from pathlib import Path
from evals.intelligence_g2.pr2.replay import main
from evals.intelligence_g2.contracts import ROOT,PACKAGE
fixture,out,config=map(Path,(sys.argv[1],sys.argv[2],sys.argv[4]))
runtime=[Path(sys.prefix).resolve(),Path(sys.base_prefix).resolve()]
original_stat,original_lstat=Path.stat,Path.lstat
def sensitive(path):
    path=Path(path)
    assert not any(p.lower() in {'reference','reviews','labels','claims','events','annotations','adjudications',
        '.local','dev-diaries'} or p.lower().startswith('.env') or
        p.lower().endswith(('.db','.db-wal','.db-shm')) for p in path.parts), 'sensitive read/stat'
    if path.is_relative_to(ROOT/'evals/intelligence_v1'):
        assert path.name not in {'event_relations.jsonl','events.jsonl','claims.jsonl'}, 'G1 reference access'
def stat(self,*args,**kwargs):
    sensitive(self)
    return original_stat(self,*args,**kwargs)
def lstat(self,*args,**kwargs):
    sensitive(self)
    return original_lstat(self,*args,**kwargs)
Path.stat,Path.lstat=stat,lstat
def writable(path):
    return path==out or path.is_relative_to(out) or (
        path.parent==out.parent and path.name.startswith('.'+out.name+'.staging-')) or (
        path.parent.parent==out.parent and path.parent.name.startswith('.'+out.name+'.staging-'))
def audit(event,args):
    if event.startswith('socket.'): raise AssertionError('network access')
    if event=='open' and isinstance(args[0],(str,bytes)):
        path=Path(args[0]).absolute();sensitive(path)
        if args[2] & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
            assert writable(path), 'outside write'
        else:
            code=path.suffix in {'.py','.pyc','.pyd'} and (
                path.is_relative_to(ROOT/'evals') or path.is_relative_to(ROOT/'backend') or
                any(path.is_relative_to(p) for p in runtime))
            allowed=path.is_relative_to(fixture) or path.is_relative_to(PACKAGE/'schema') or (
                path in {config,PACKAGE/'manifests/pr1_config.json',ROOT/'requirements.lock',ROOT/'frontend/package-lock.json',
                    ROOT/'evals/intelligence_v1/manifests/dataset_manifest.json',
                    ROOT/'evals/intelligence_v1/manifests/baseline_config.json'})
            assert code or allowed, 'outside read'
    if event=='os.rename': assert writable(Path(args[0])) and Path(args[1])==out
sys.addaudithook(audit)
manifest=fixture/('manifests/dataset_manifest.json' if sys.argv[6]=='g1' else 'manifest.json')
status=main(['--manifest',str(manifest),'--manifest-sha256',sys.argv[3],
    '--timeline','DEV-01' if sys.argv[6]=='g1' else 'EVIDENCE','--through-step','D8','--strategy','r1','--config',str(config),
    '--config-sha256',sys.argv[5],'--out',str(out)])
assert not {'evals.intelligence_v1.oracle','evals.intelligence_v1.evaluate','evals.intelligence_v1.validate',
    'evals.intelligence_g2.pr2.reference_loader','evals.intelligence_g2.pr2.evaluate'} & set(sys.modules)
assert not any(m.startswith('cfaw_news.') and m!='cfaw_news.retrieval' for m in sys.modules)
sys.exit(status)
'''
    source = ROOT / "evals/intelligence_v1" if kind == "g1" else FIXTURES / "prediction"
    manifest = source / ("manifests/dataset_manifest.json" if kind == "g1" else "manifest.json")
    result = subprocess.run([sys.executable, "-B", "-c", script, str(source),
        str(output), pin(manifest), str(CONFIG), pin(CONFIG), kind],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["ok"]
    assert canary.read_bytes() == before
