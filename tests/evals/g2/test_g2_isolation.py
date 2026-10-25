import json
import subprocess
import sys

from evals.intelligence_g2.contracts import ROOT
from evals.intelligence_v1.hashing import sha256_bytes

from .support import CONFIG, copied_bundle, output_path


def test_G2_T10_audited_cli_no_reference_stat_open_network_private_data_or_outside_write(tmp_path):
    root = copied_bundle(tmp_path)
    canary = tmp_path / "canary.db"
    canary.write_bytes(b"synthetic database canary; not a user database")
    before_canary = canary.read_bytes()
    before = {p.relative_to(root).as_posix(): sha256_bytes(p.read_bytes())
              for p in root.rglob("*") if p.is_file()}
    output = output_path()
    script = r'''
import os,sys
from pathlib import Path
from evals.intelligence_g2.replay import main
from evals.intelligence_g2.contracts import ROOT
root,out,config=map(Path,(sys.argv[1],sys.argv[2],sys.argv[4]))
runtime=[Path(sys.prefix).resolve(),Path(sys.base_prefix).resolve()]
forbidden={'labels','claims','events','annotations','adjudications'}
original_stat,original_lstat=Path.stat,Path.lstat
def sensitive(path):
    path=Path(path)
    if path.is_relative_to(root) and set(path.relative_to(root).parts)&forbidden:
        raise AssertionError('reference path stat/open')
    assert not any(p.lower() in {'.local','dev-diaries'} or p.lower().startswith('.env')
                   or p.lower().endswith(('.db','.db-wal','.db-shm')) for p in path.parts)
def guarded_stat(self,*args,**kwargs):
    sensitive(self)
    return original_stat(self,*args,**kwargs)
def guarded_lstat(self,*args,**kwargs):
    sensitive(self)
    return original_lstat(self,*args,**kwargs)
Path.stat,Path.lstat=guarded_stat,guarded_lstat
def writes_allowed(path):
    return (path==out or path.is_relative_to(out) or
        (path.parent==out.parent and path.name.startswith('.'+out.name+'.staging-')) or
        (path.parent.parent==out.parent and path.parent.name.startswith('.'+out.name+'.staging-')))
def audit(event,args):
    if event.startswith('socket.'):
        raise AssertionError('network access')
    if event=='open' and isinstance(args[0],(str,bytes)):
        path=Path(args[0]).absolute()
        sensitive(path)
        if args[2] & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
            assert writes_allowed(path), 'outside write'
        else:
            code=(path.suffix in {'.py','.pyc','.pyd'} and
                (path.is_relative_to(ROOT/'evals') or path.is_relative_to(ROOT/'backend') or
                 any(path.is_relative_to(p) for p in runtime)))
            public=path in {ROOT/'requirements.lock',ROOT/'frontend/package-lock.json',config}
            schemas=path.is_relative_to(ROOT/'evals/intelligence_g2/schema/v1')
            assert path.is_relative_to(root) or code or public or schemas, 'outside data read'
    if event=='os.rename':
        assert writes_allowed(Path(args[0])) and Path(args[1])==out
sys.addaudithook(audit)
status=main(['--manifest',str(root/'manifests/dataset_manifest.json'),
    '--manifest-sha256',sys.argv[3],'--timeline','DEV-01','--step','D0',
    '--config',str(config),'--config-sha256',sys.argv[5],'--out',str(out)])
assert not any(m.startswith('cfaw_news.') and m!='cfaw_news.retrieval' for m in sys.modules)
assert not {'evals.intelligence_v1.oracle','evals.intelligence_v1.evaluate',
            'evals.intelligence_v1.validate'} & set(sys.modules)
sys.exit(status)
'''
    pin = sha256_bytes((root / "manifests/dataset_manifest.json").read_bytes())
    result = subprocess.run([sys.executable, "-B", "-c", script, str(root), str(output), pin,
        str(CONFIG), sha256_bytes(CONFIG.read_bytes())], cwd=ROOT, capture_output=True,
        text=True, encoding="utf-8", timeout=40)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["ok"]
    assert canary.read_bytes() == before_canary
    assert before == {p.relative_to(root).as_posix(): sha256_bytes(p.read_bytes())
                      for p in root.rglob("*") if p.is_file()}


def test_G2_T10_prediction_without_reference_files_matches_pinned_data(tmp_path):
    from .support import cli_args
    from .test_g2_cli import invoke

    root = copied_bundle(tmp_path)
    assert not (root / "labels").exists()
    assert not (root / "events").exists()
    assert not (root / "claims").exists()
    outputs = (output_path(), output_path())
    for out, args in ((outputs[0], cli_args(outputs[0])),
                      (outputs[1], cli_args(outputs[1], root))):
        result = invoke(args)
        assert result.returncode == 0, result.stdout + result.stderr
    # The copy preserves the exact manifest bytes, including the original external pin.
    for name in ("input_snapshot.json", "result.json", "events.jsonl", "items.jsonl"):
        assert (outputs[0] / name).read_bytes() == (outputs[1] / name).read_bytes()
