"""T41/T45: prediction has no gold, settings, DB, private files or tool capability."""

import json
import subprocess
import sys

from evals.intelligence_g2.contracts import ROOT

from ..support import output_path
from .support import CONFIG, export_rule, pin, run


def test_T41_instructions_remain_evidence_not_actions():
    _, rows, _ = run("INJECTION_DATA")
    assert rows[0].result.presentations[0].selection == "mock_closed"
    assert ".env" in rows[0].result.presentations[0].body
    assert rows[0].traces[0].mock_calls == 1
    assert rows[0].traces[0].external_requests == rows[0].traces[0].model_calls == 0


def test_T45_audited_prediction_no_reference_network_private_db_or_external_write(tmp_path):
    parent, out = export_rule(tmp_path), output_path()
    canary = tmp_path / "canary.sqlite"
    canary.write_bytes(b"synthetic immutable DB canary")
    before = canary.read_bytes()
    script = r'''
import asyncio,os,sys
from pathlib import Path
from evals.intelligence_g2.contracts import PACKAGE,ROOT
from evals.intelligence_g2.pr5 import replay
parent,out,config=map(Path,(sys.argv[1],sys.argv[2],sys.argv[4]))
chain=[parent];cursor=parent
import json
for _ in range(2):
 m=json.loads((cursor/'run_manifest.json').read_bytes());cursor=ROOT/m['parent_run_path'];chain.append(cursor)
# Trusted scheduler setup precedes the capability audit. No socket operation is allowed in generation.
loop=asyncio.new_event_loop()
replay.asyncio.run=lambda c:loop.run_until_complete(c)
runtime=[Path(sys.prefix).resolve(),Path(sys.base_prefix).resolve()]
original_stat,original_lstat=Path.stat,Path.lstat
def sensitive(p):
 p=Path(p)
 assert not any(part.casefold() in {'reference','review','reviews','labels','annotations','adjudications','.local','dev-diaries'} or part.casefold().startswith('.env') or part.casefold().endswith(('.db','.db-wal','.db-shm','.sqlite')) for part in p.parts),'private/reference'
 if p.is_relative_to(ROOT/'evals/intelligence_v1'):
  assert p.name not in {'events.jsonl','claims.jsonl','event_relations.jsonl'},'G1 reference'
def stat(self,*a,**k):sensitive(self);return original_stat(self,*a,**k)
def lstat(self,*a,**k):sensitive(self);return original_lstat(self,*a,**k)
Path.stat,Path.lstat=stat,lstat
def writable(p):
 return p==out or p.is_relative_to(out) or p.parent==out.parent and p.name.startswith('.'+out.name+'.staging-') or p.parent.parent==out.parent and p.parent.name.startswith('.'+out.name+'.staging-')
def audit(event,args):
 if event.startswith('socket.'):raise AssertionError('network/tool socket')
 if event=='open' and isinstance(args[0],(str,bytes)):
  p=Path(args[0]).absolute();sensitive(p)
  if args[2] & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):assert writable(p),'outside write'
  else:
   code=p.suffix in {'.py','.pyc','.pyd'} and (p.is_relative_to(ROOT/'evals') or p==ROOT/'backend/cfaw_news/retrieval.py' or any(p.is_relative_to(r) for r in runtime))
   allowed=any(p.is_relative_to(c) for c in chain) or p.is_relative_to(PACKAGE/'schema') or p.is_relative_to(PACKAGE/'manifests') or p.is_relative_to(PACKAGE/'fixtures/pr5/v1/prompt') or p.is_relative_to(PACKAGE/'fixtures/pr5/v1/mock-response') or p in {ROOT/'requirements.lock',ROOT/'frontend/package-lock.json'}
   assert code or allowed,'outside read'
 if event=='os.rename':assert writable(Path(args[0])) and Path(args[1])==out
sys.addaudithook(audit)
status=replay.main(['--rule-run',str(parent),'--rule-manifest-sha256',sys.argv[3],'--through-step','D8','--config',str(config),'--config-sha256',sys.argv[5],'--out',str(out)])
assert not any(m.startswith('cfaw_news.') and m!='cfaw_news.retrieval' for m in sys.modules)
assert not any(m.endswith(('.evaluate','.reference_loader','.oracle')) and m.startswith('evals.intelligence_') for m in sys.modules)
loop.close()
sys.exit(status)
'''
    proc = subprocess.run([sys.executable, "-B", "-c", script, str(parent), str(out), pin(parent / "run_manifest.json"),
        str(CONFIG), pin(CONFIG)], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["ok"] and canary.read_bytes() == before


def test_T45_reference_removed_predictions_unchanged(tmp_path):
    # The runtime never needs the fixture's research/development reference tree.
    # A subprocess denies even stat, rather than renaming or deleting frozen references.
    parent, a, b = export_rule(tmp_path), output_path(), output_path()
    from evals.intelligence_g2.pr5.replay import main

    from .support import cli_args
    assert main(cli_args(parent, a)) == 0
    script = r'''
import sys
from pathlib import Path
from evals.intelligence_g2.pr5.replay import main
original=Path.stat
def stat(p,*a,**k):
 assert 'reference' not in p.parts and 'review' not in p.parts
 return original(p,*a,**k)
Path.stat=stat
sys.exit(main(sys.argv[1:]))
'''
    proc = subprocess.run([sys.executable, "-B", "-c", script, *cli_args(parent, b)], cwd=ROOT,
        capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    for path in a.iterdir():
        if path.name != "trace.json":
            assert path.read_bytes() == (b / path.name).read_bytes(), path.name
