"""Bounded, pinned, in-memory native G2 replay. G3 runtime is explicitly unavailable."""

import argparse
import re

from evals.intelligence_g2.contracts import (
    G2Config,
    G2ReplayInput,
    IdentitySeed,
    data,
    digest,
    json_bytes,
)
from evals.intelligence_g2.pr2.contracts import GroupingInput, PR2Config, ReplayCursor
from evals.intelligence_g2.pr2.pipeline import run_grouping_step
from evals.intelligence_g2.pr3.contracts import EvidenceInput, PR3Config
from evals.intelligence_g2.pr3.pipeline import run_evidence_step
from evals.intelligence_g2.pr4.contracts import PR4Config
from evals.intelligence_g2.pr4.pipeline import generate_items
from evals.intelligence_g2.pr4.project import project_step
from evals.intelligence_g2.pr5.pipeline import rule_presentation
from evals.intelligence_g2.validate_output import checked_input
from evals.intelligence_v1.contracts import ReplayContext
from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.hashing import sha256_bytes

from .contracts import (
    NATIVE_STEP_REVISION,
    G4Error,
    RuntimeBriefing,
    RuntimeStatus,
    decode,
    fail,
    parse,
)
from .coverage import diagnose

MAX_INPUT_BYTES = 2_000_000


def derive(value, input_pin):
    """No approximate G2 schemas, grouping heuristics, rank weights or generated facts."""
    if sha256_bytes(json_bytes(value)) != input_pin:
        fail("G4_INPUT_PIN_MISMATCH", "canonical_runtime_input")
    prior_group = prior_evidence = prior_rule = None
    results = []
    try:
        for ordinal, step in enumerate(value.steps):
            documents = tuple(d.native() for d in step.documents)
            context = ReplayContext(timeline_id=value.timeline_id, step_id=step.step_id,
                as_of=step.as_of, persona=step.persona.persona,
                candidate_doc_version_ids=tuple(d.candidate.doc_version_id for d in documents),
                previous_delivery_id=None,
                attention_budget_seconds=value.config.attention_budget_seconds,
                time_window_start=step.time_window_start, time_window_end=step.time_window_end,
                source_coverage=step.source_coverage, exposure_history=())
            replay = G2ReplayInput(dataset_id="g4:runtime-local-feasibility",
                dataset_revision="runtime_local_v1", input_manifest_sha256=input_pin,
                context=context, visible_documents=documents,
                sources=tuple(s.policy for s in value.sources),
                identity_seeds=tuple(IdentitySeed(document_id=d.candidate.document_id,
                    anchor_doc_version_id=d.visible_lineage[0].doc_version_id,
                    first_visible_at=d.visible_lineage[0].available_at) for d in documents),
                source_coverage_digest=digest([data(w) for w in step.source_coverage]),
                pipeline_revision=G2Config().pipeline_revision, config_sha256=digest(G2Config()))
            replay, _ = checked_input(replay, G2Config())
            cursor = ReplayCursor(timeline_id=value.timeline_id, step_id=step.step_id,
                as_of=step.as_of, ordinal=ordinal,
                previous_step_id=prior_group.cursor.step_id if prior_group else None)
            group_input = GroupingInput(replay_input=replay, strategy="r1",
                grouping_config_sha256=digest(PR2Config()), cursor=cursor,
                previous_state=prior_group,
                previous_state_sha256=digest(prior_group) if prior_group else None)
            group = run_grouping_step(grouping_input=group_input, config=PR2Config())
            evidence_input = EvidenceInput(grouping_input=group_input, grouping_result=group,
                grouping_config=PR2Config(), config_sha256=digest(PR3Config()),
                previous_state=prior_evidence,
                previous_state_sha256=digest(prior_evidence) if prior_evidence else None)
            evidence = run_evidence_step(evidence_input=evidence_input, config=PR3Config())
            rule_input = project_step(evidence_input, evidence, previous_state=prior_rule,
                                      config=PR4Config(), evidence_config=PR3Config())
            rule = generate_items(generation_input=rule_input, config=PR4Config())
            results.append(dict(schema_revision=NATIVE_STEP_REVISION, grouping=data(group),
                                evidence=data(evidence), rule=data(rule),
                                presentations=[data(rule_presentation(i)) for i in rule.items],
                                coverage=data(diagnose(step, (s.policy.source_id for s in value.sources), ordinal))))
            prior_group, prior_evidence, prior_rule = group.next_state, evidence.next_state, rule.next_state
    except G4Error:
        raise
    except ContractError as error:
        raise G4Error("G4_NATIVE_G2_REJECTED", field=error.field, native_code=error.code) from None
    non_hold = any(i.tier_candidate != "hold" for i in rule.items)
    status = RuntimeStatus(record_origin=value.record_origin,
        state="raw_news_only" if non_hold else "insufficient_evidence",
        code="G4_G3_RUNTIME_ADAPTER_REQUIRED" if non_hold else "G4_EVIDENCE_NOT_ELIGIBLE")
    return dict(input_sha256=input_pin, config_sha256=digest(value.config), native_steps=results,
        status=data(status), archive_snapshot_ids=[s.snapshot_id for s in rule.snapshots],
        display_order=[], plan=None)


def run_slice(raw: bytes, *, expected_sha256: str) -> RuntimeBriefing:
    """The caller supplies an independently retained exact-byte pin; never self-issue it."""
    if not isinstance(raw, bytes) or len(raw) > MAX_INPUT_BYTES:
        fail("G4_RESOURCE_LIMIT", "input_bytes")
    if (not isinstance(expected_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None
            or sha256_bytes(raw) != expected_sha256):
        fail("G4_INPUT_PIN_MISMATCH", "expected_sha256")
    value = decode(raw)
    if raw != json_bytes(value):
        fail("G4_CANONICAL_REQUIRED", "input")
    return parse(RuntimeBriefing, dict(input=data(value), **derive(value, expected_sha256)))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--input-pin", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    # This is an offline developer CLI, not an application ingestion or HTTP service.
    from evals.intelligence_g2.replay import safe_path
    from evals.intelligence_g3.contracts import ROOT

    base = ROOT / ".tmp/evals/g3"
    try:
        source = safe_path(args.input, areas=(base,), code="G4_REFERENCE_MISMATCH")
        out = safe_path(args.out, areas=(base,), code="G4_REFERENCE_MISMATCH")
        if out == base or out.exists():
            fail("G4_REFERENCE_MISMATCH", "fresh_output_directory")
        if source.stat().st_size > MAX_INPUT_BYTES:
            fail("G4_RESOURCE_LIMIT", "input_bytes")
        raw = source.read_bytes()
        result = run_slice(raw, expected_sha256=args.input_pin)
        payloads = {"runtime_input.json": raw, "result.json": json_bytes(result),
                    "config.json": json_bytes(result.input.config)}
        manifest = dict(revision=result.schema_revision, input_revision=result.input.schema_revision,
            input_pin=args.input_pin,
            record_origin=result.input.record_origin, model_calls=0, external_requests=0,
            files={name: sha256_bytes(body) for name, body in payloads.items()})
        payloads["manifest.json"] = json_bytes(manifest)
        out.mkdir(parents=True, exist_ok=False)
        for name, body in payloads.items():
            with (out / name).open("xb") as stream:
                stream.write(body)
        print(json_bytes(dict(ok=True, state=result.status.state, code=result.status.code,
            publishable=False, output_pin=sha256_bytes(payloads["manifest.json"]))).decode(), end="")
        return 0
    except (ContractError, OSError, ValueError) as error:
        print(json_bytes(dict(ok=False, code=getattr(error, "code", "G4_SCHEMA_INVALID"),
            field=getattr(error, "field", "offline_artifact"),
            native_code=getattr(error, "native_code", None))).decode(), end="")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
