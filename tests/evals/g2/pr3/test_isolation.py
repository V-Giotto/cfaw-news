import json
import subprocess
import sys

import pytest

from evals.intelligence_g2.contracts import ROOT, digest
from evals.intelligence_v1.contracts import CoverageWindow

from ..support import output_path
from .support import CONFIG, evidence_for, export_parent, make_input, pin


def test_T28_offline_and_unknown_coverage_never_imply_no_change():
    value = make_input([{"id": "a"}])
    doc = value.visible_documents[0].candidate
    window = CoverageWindow(coverage_window_id="offline", source_id=doc.source_id,
        start_at=value.context.as_of, end_at=value.context.as_of, observed_at=value.context.as_of,
        status="service_offline", reason="Synthetic offline source")
    value = value.model_copy(update={"context": value.context.model_copy(update={"source_coverage": (window,)}),
                                    "source_coverage_digest": digest([window.model_dump(mode="json")])})
    _, rows = evidence_for([value])
    assert len(rows[0].claims) == 1  # Snapshot remains usable; no remote availability dependency.
    assert "source_service_offline" in {g.code for g in rows[0].validation.coverage_gaps}
    assert b"no_change" not in rows[0].model_dump_json().encode()
    empty = evidence_for([make_input([])])[1][0]
    assert empty.claims == empty.bundles == ()
    assert "coverage_unknown" in {g.code for g in empty.validation.coverage_gaps}


def test_budget_failure_is_explicit_before_publishing_more_claims():
    from evals.intelligence_g2.contracts import G2Error
    from evals.intelligence_v1.contracts import Paragraph
    from evals.intelligence_v1.hashing import content_sha256

    value = make_input([{"id": "a"}])
    wrapped = value.visible_documents[0]
    doc = wrapped.candidate
    paragraphs = tuple(Paragraph(paragraph_id="p" + str(n), text="Atlas Tool v1.0 is released.") for n in range(33))
    sha = content_sha256(doc.title, doc.text_excerpt, paragraphs)
    doc = doc.model_copy(update={"paragraphs": paragraphs, "content_sha256": sha})
    lineage = tuple(v.model_copy(update={"content_sha256": sha}) for v in wrapped.visible_lineage)
    value = value.model_copy(update={"visible_documents": (wrapped.model_copy(update={"candidate": doc,
                                                                                    "visible_lineage": lineage}),)})
    with pytest.raises(G2Error) as error:
        evidence_for([value])
    assert (error.value.code, error.value.stage, error.value.field, error.value.record_id) == (
        "G2_PR3_BUDGET_EXCEEDED", "extract", "claims_per_document", "a:1")


def test_audited_prediction_no_reference_private_db_network_or_outside_write(tmp_path):
    parent = export_parent(tmp_path)
    canary = tmp_path / "canary.db"
    canary.write_bytes(b"synthetic PR3 database canary")
    before = canary.read_bytes()
    output = output_path()
    script = r'''
import os,sys
from pathlib import Path
from evals.intelligence_g2.pr3.replay import main
from evals.intelligence_g2.contracts import ROOT,PACKAGE
parent,out,config=map(Path,(sys.argv[1],sys.argv[2],sys.argv[4]))
runtime=[Path(sys.prefix).resolve(),Path(sys.base_prefix).resolve()]
original_stat,original_lstat=Path.stat,Path.lstat
def sensitive(path):
    path=Path(path)
    assert not any(p.lower() in {'reference','reviews','labels','claims','annotations','adjudications',
        '.local','dev-diaries'} or p.lower().startswith('.env') or p.lower().endswith(('.db','.db-wal','.db-shm'))
        for p in path.parts), 'sensitive read/stat'
    if path.is_relative_to(ROOT/'evals/intelligence_v1'):
        assert path.name not in {'event_relations.jsonl','events.jsonl','claims.jsonl'}, 'reference read'
def stat(self,*a,**kw):
    sensitive(self);return original_stat(self,*a,**kw)
def lstat(self,*a,**kw):
    sensitive(self);return original_lstat(self,*a,**kw)
Path.stat,Path.lstat=stat,lstat
def writable(path):
    return path==out or path.is_relative_to(out) or (
        path.parent==out.parent and path.name.startswith('.'+out.name+'.staging-')) or (
        path.parent.parent==out.parent and path.parent.name.startswith('.'+out.name+'.staging-'))
def audit(event,args):
    if event.startswith('socket.'):raise AssertionError('network')
    if event=='open' and isinstance(args[0],(str,bytes)):
        path=Path(args[0]).absolute();sensitive(path)
        if args[2] & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
            assert writable(path), 'outside write'
        else:
            code=path.suffix in {'.py','.pyc','.pyd'} and (path.is_relative_to(ROOT/'evals') or
                path.is_relative_to(ROOT/'backend') or any(path.is_relative_to(r) for r in runtime))
            allowed=path.is_relative_to(parent) or path.is_relative_to(PACKAGE/'schema') or path in {
                config,ROOT/'requirements.lock',ROOT/'frontend/package-lock.json'}
            assert code or allowed, 'outside read'
    if event=='os.rename':assert writable(Path(args[0])) and Path(args[1])==out
sys.addaudithook(audit)
status=main(['--grouping-run',str(parent),'--grouping-manifest-sha256',sys.argv[3],
    '--through-step','D8','--config',str(config),'--config-sha256',sys.argv[5],'--out',str(out)])
assert not {'evals.intelligence_v1.oracle','evals.intelligence_v1.evaluate','evals.intelligence_v1.validate',
    'evals.intelligence_g2.pr2.reference_loader','evals.intelligence_g2.pr2.evaluate',
    'evals.intelligence_g2.pr3.reference_loader','evals.intelligence_g2.pr3.evaluate'} & set(sys.modules)
assert not any(m.startswith('cfaw_news.') and m!='cfaw_news.retrieval' for m in sys.modules)
sys.exit(status)
'''
    result = subprocess.run([sys.executable, "-B", "-c", script, str(parent), str(output),
        pin(parent / "run_manifest.json"), str(CONFIG), pin(CONFIG)], cwd=ROOT,
        capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["ok"]
    assert before == canary.read_bytes()
