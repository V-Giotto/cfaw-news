"""Authored regression probes for cross-step chains, interval gaps and identity bindings."""

import json
import os
import subprocess
import sys
from copy import deepcopy
from datetime import timedelta

import pytest
from pydantic import ValidationError

from evals.intelligence_g2.contracts import data, digest, json_bytes
from evals.intelligence_g4.contracts import G4Error, RuntimeBriefing, RuntimeInput, decode, parse
from evals.intelligence_g4.slice import run_slice
from evals.intelligence_v1.contracts import Paragraph
from evals.intelligence_v1.hashing import content_sha256, sha256_bytes
from evals.intelligence_v1.temporal import format_instant, parse_instant

from .support import LATER, NOW, OLD, case


def step_at(template, number):
    step = deepcopy(template)
    stamp = format_instant(parse_instant(NOW) + timedelta(days=number))
    step.update(step_id=f"S{number}", as_of=stamp, time_window_end=stamp)
    step["source_coverage"][0].update(coverage_window_id=f"official:S{number}",
                                     end_at=stamp, observed_at=stamp)
    return step


def versions(fault=None):
    value = data(parse(RuntimeInput, case()))
    first = value["steps"][0]
    second, third = step_at(first, 1), step_at(first, 2)
    doc2 = second["documents"][0]
    c = doc2["candidate"]
    body = "Atlas Tool v1.0 releases updated local agent evaluation tooling."
    c.update(doc_version_id="atlas:v2", observed_at=LATER, available_at=LATER,
             paragraphs=[dict(paragraph_id="p1", text=body)],
             content_sha256=content_sha256(c["title"], None, (Paragraph(paragraph_id="p1", text=body),)))
    doc2["visible_lineage"].append(dict(doc_version_id="atlas:v2", document_id="atlas",
        available_at=LATER, supersedes_version_id="atlas:v1", content_sha256=c["content_sha256"]))
    doc3 = deepcopy(doc2)
    c = doc3["candidate"]
    body = "Atlas Tool v1.0 releases additional local agent evaluation tooling."
    c.update(doc_version_id="atlas:v3", observed_at=third["as_of"], available_at=third["as_of"],
             paragraphs=[dict(paragraph_id="p1", text=body)],
             content_sha256=content_sha256(c["title"], None, (Paragraph(paragraph_id="p1", text=body),)))
    doc3["visible_lineage"].append(dict(doc_version_id="atlas:v3", document_id="atlas",
        available_at=third["as_of"], supersedes_version_id="atlas:v2", content_sha256=c["content_sha256"]))
    third["documents"] = [doc3]
    value["steps"] += [second, third]
    if fault in {"rollback", "rollback-after-absence"}:
        third["documents"] = deepcopy(first["documents"])
        if fault == "rollback-after-absence":
            absent = step_at(first, 2)
            absent["documents"] = []
            third = step_at(third, 3)
            value["steps"] = [first, second, absent, third]
    elif fault == "fork":
        doc3["visible_lineage"] = [doc3["visible_lineage"][0], doc3["visible_lineage"][-1]]
        doc3["visible_lineage"][-1]["supersedes_version_id"] = "atlas:v1"
    elif fault == "missing-middle":
        doc3["visible_lineage"].pop(1)
    elif fault == "rewrite-parent":
        doc3["visible_lineage"][1]["supersedes_version_id"] = None
    return value


def result(value):
    raw = json_bytes(value)
    return run_slice(raw, expected_sha256=sha256_bytes(raw))


@pytest.mark.parametrize("entrypoint", ["parser", "direct_json"])
@pytest.mark.parametrize("fault", ["rollback", "fork", "missing-middle", "rewrite-parent",
                                  "rollback-after-absence"])
def test_entire_captured_chain_is_monotone_on_both_json_entrypoints(fault, entrypoint):
    raw = json_bytes(versions(fault))
    with pytest.raises((G4Error, ValidationError)) as caught:
        decode(raw) if entrypoint == "parser" else RuntimeInput.model_validate_json(raw)
    error = caught.value
    if isinstance(error, ValidationError):
        causes = [v.get("ctx", {}).get("error") for v in error.errors(include_input=False)]
        assert any(isinstance(v, G4Error) and v.code in
                   {"G4_SEQUENCE_INVALID", "G4_HASH_MISMATCH"} for v in causes)
    else:
        assert error.code in {"G4_SEQUENCE_INVALID", "G4_HASH_MISMATCH"}


@pytest.mark.parametrize("repeat_tail", [False, True])
def test_linear_successors_and_repeated_latest_tail_remain_legal(repeat_tail):
    value = versions()
    if repeat_tail:
        value["steps"].append(step_at(value["steps"][-1], 3))
    output = result(value)
    assert output.native_steps[-1].grouping.validation.ok
    assert output.input.steps[-1].documents[0].candidate.doc_version_id == "atlas:v3"
    assert not output.status.publishable


@pytest.mark.parametrize("fault", ["rollback", "fork", "missing-middle"])
def test_invalid_chains_are_rejected_by_real_cli_without_output(fault, tmp_path):
    raw = json_bytes(versions(fault))
    source, out = tmp_path / (fault + ".json"), tmp_path / (fault + "-out")
    source.write_bytes(raw)
    run = subprocess.run([sys.executable, "-B", "-m", "evals.intelligence_g4.slice",
        "--input", str(source), "--input-pin", sha256_bytes(raw), "--out", str(out)],
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, text=True, timeout=30)
    assert run.returncode == 1, run.stdout + run.stderr
    assert json.loads(run.stdout)["code"] == "G4_SEQUENCE_INVALID"
    assert not out.exists()


def minute_coverage():
    value = data(parse(RuntimeInput, case()))
    value["steps"][0]["source_coverage"][0].update(
        start_at="2026-01-02T11:59:00Z", status="covered", reason="Authored minute observation")
    return value


def test_observed_minute_does_not_hide_23_hours_59_minutes_unknown():
    output = result(minute_coverage())
    native = output.native_steps[0]
    # Frozen G2 reports the supplied window status; G4 must diagnose the requested interval.
    assert native.evidence.validation.coverage_gaps == ()
    coverage = native.coverage
    assert coverage.has_gap and coverage.windows == output.input.steps[0].source_coverage
    source = coverage.sources[0]
    assert [s.status for s in source.segments] == ["unknown", "covered"]
    assert source.unobserved_intervals[0].start_at == parse_instant(OLD)
    assert source.unobserved_intervals[0].end_at == parse_instant("2026-01-02T11:59:00Z")
    assert (source.unobserved_intervals[0].end_at - source.unobserved_intervals[0].start_at
            ).total_seconds() == 23 * 3600 + 59 * 60


@pytest.mark.parametrize("case_name", ["full", "adjacent", "overlap", "outside", "point-only",
                                      "zero-duration", "failed-veto", "empty-pool"])
def test_query_coverage_unions_clips_and_keeps_noncovered_veto(case_name):
    value = data(parse(RuntimeInput, case()))
    step = value["steps"][0]
    w = step["source_coverage"][0]
    w.update(status="covered", reason="Authored coverage probe")
    if case_name in {"adjacent", "overlap", "failed-veto"}:
        second = deepcopy(w)
        second.update(coverage_window_id="second", start_at="2026-01-02T00:00:00Z")
        if case_name == "adjacent":
            w["end_at"] = second["start_at"]
        if case_name == "failed-veto":
            second["status"] = "failed"
        step["source_coverage"].append(second)
    elif case_name == "outside":
        w.update(start_at=OLD, end_at=OLD)
    elif case_name == "point-only":
        w.update(start_at="2026-01-02T00:00:00Z", end_at="2026-01-02T00:00:00Z")
    elif case_name == "zero-duration":
        step["time_window_start"] = NOW
        w["start_at"] = NOW
    elif case_name == "empty-pool":
        step["documents"] = []
        w["start_at"] = "2026-01-02T11:59:00Z"
    coverage = result(value).native_steps[0].coverage
    assert coverage.has_gap is (case_name in {"outside", "point-only", "failed-veto", "empty-pool"})
    if not coverage.has_gap:
        assert len(coverage.sources[0].confirmed_intervals) == 1
    if case_name == "failed-veto":
        assert any(s.status == "failed" for s in coverage.sources[0].segments)


def test_g4_coverage_references_resolve_and_serialized_gaps_cannot_be_deleted():
    output = result(minute_coverage())
    raw = data(output)
    for source in output.native_steps[0].coverage.sources:
        for segment in source.segments:
            for pointer in segment.window_refs:
                node = raw
                for part in pointer.split("/")[1:]:
                    node = node[int(part)] if isinstance(node, list) else node[part]
                assert node in data(output.input.steps[0])["source_coverage"]
    raw["native_steps"][0]["coverage"]["has_gap"] = False
    with pytest.raises(G4Error, match="G4_OUTPUT_MISMATCH"):
        parse(RuntimeBriefing, raw)


def test_budget_profile_changes_integrity_pins_without_changing_native_identity():
    value = versions()
    other = deepcopy(value)
    other["config"]["budget"]["profile"] = "focus60-radar40-v1"
    left, right = result(value), result(other)
    assert left.input_sha256 != right.input_sha256 and left.config_sha256 != right.config_sha256
    for a, b in zip(left.native_steps, right.native_steps, strict=True):
        assert a.grouping.next_state.namespace == b.grouping.next_state.namespace
        assert a.evidence.next_state.namespace == b.evidence.next_state.namespace
        assert a.rule.next_state.namespace == b.rule.next_state.namespace
        assert [e.event_key for e in a.grouping.events] == [e.event_key for e in b.grouping.events]
        assert [s.snapshot_id for s in a.rule.snapshots] == [s.snapshot_id for s in b.rule.snapshots]
        assert a.grouping.next_state.input_manifest_sha256 == left.input_sha256
        assert b.grouping.next_state.input_manifest_sha256 == right.input_sha256
        assert digest(a.grouping.next_state) != digest(b.grouping.next_state)
