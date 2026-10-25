"""Independent development evaluation; no result is sent back to the generator."""

import argparse
import asyncio
from pathlib import Path

from evals.intelligence_g2.contracts import PACKAGE, ROOT, G2Error, json_bytes
from evals.intelligence_g2.replay import OUTPUT_BASE, output_location, safe_path, write_payloads
from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.hashing import sha256_bytes

from .assets import asset_hashes, load_assets, strict_json
from .contracts import ExpressionTrace, PR5Config, RunManifest, data, digest, fail, parse
from .load_run import load_rule_run
from .reference_loader import load_reference
from .replay import (
    STREAMS,
    current_sources,
    print_error,
    projection_record,
    run_sequence,
    validation_report,
)


def ratio(n, d):
    return dict(numerator=n, denominator=d, value=n / d if d else None,
                unavailable_reason=None if d else "zero_denominator")


def load_expression_run(directory, pin):
    directory = safe_path(directory, areas=(OUTPUT_BASE,))
    raw = safe_path(directory / "run_manifest.json", areas=(directory,)).read_bytes()
    if sha256_bytes(raw) != pin:
        fail("MANIFEST_SHA_MISMATCH", "evaluation", "run_manifest")
    manifest = parse(RunManifest, strict_json(raw))
    if manifest.runtime_source_sha256 != current_sources():
        fail("RUNTIME_CODE_MISMATCH", "evaluation", "runtime_source_sha256")
    schemas = {p.relative_to(PACKAGE).as_posix(): sha256_bytes(p.read_bytes())
               for p in (PACKAGE / "schema/v5").glob("*.schema.json")}
    if schemas != manifest.schema_sha256:
        fail("SHA_MISMATCH", "evaluation", "schemas")
    expected_names = {n + ".jsonl" for n in STREAMS} | {
        "config_snapshot.json", "input_projections.jsonl", "validation_report.json"}
    payloads = {}
    for entry in manifest.artifacts:
        if entry.path not in expected_names or entry.path in payloads:
            fail("PREDICTION_PATH_INVALID", "evaluation", "artifact")
        raw = safe_path(directory / entry.path, areas=(directory,)).read_bytes()
        if (sha256_bytes(raw) != entry.sha256 or len(raw) != entry.byte_count
                or entry.record_count is not None and len(raw.splitlines()) != entry.record_count):
            fail("SHA_MISMATCH", "evaluation", "artifact")
        payloads[entry.path] = raw
    if set(payloads) != expected_names:
        fail("G2_PR5_OUTPUT_INVALID", "evaluation", "artifacts")
    config = parse(PR5Config, strict_json(payloads["config_snapshot.json"]))
    if digest(config) != manifest.config_sha256:
        fail("CONFIG_SHA_MISMATCH", "evaluation", "config")
    assets = load_assets(config)
    if manifest.asset_sha256 != asset_hashes(assets):
        fail("SHA_MISMATCH", "evaluation", "assets")
    parent, values, rules, rule_config = load_rule_run(ROOT / manifest.parent_run_path,
        manifest_sha256=manifest.parent_manifest_sha256, through_step=manifest.through_step)
    if parent.dependency_lock_sha256 != manifest.dependency_lock_sha256:
        fail("SHA_MISMATCH", "evaluation", "locks")
    inputs, expected = asyncio.run(run_sequence(values, rules, rule_config=rule_config,
        config=config, assets=assets, mode=manifest.mode))
    if digest([digest(v) for v in inputs]) != manifest.selected_input_sha256:
        fail("G2_PR5_OUTPUT_INVALID", "evaluation", "selected_input_sha256")
    for name, field in STREAMS.items():
        wanted = b"".join(json_bytes(dict(cursor=data(e.result.cursor), **{field:
            data(getattr(e.result, field)) if field == "next_state" else [data(v) for v in getattr(e.result, field)]}))
            for e in expected)
        if payloads[name + ".jsonl"] != wanted:
            fail("G2_PR5_OUTPUT_INVALID", "evaluation", "result")
    wanted = b"".join(json_bytes(projection_record(v)) for v in inputs)
    if payloads["input_projections.jsonl"] != wanted:
        fail("G2_PR5_OUTPUT_INVALID", "evaluation", "input_projection")
    report = validation_report(inputs, expected)
    if payloads["validation_report.json"] != json_bytes(report):
        fail("G2_PR5_OUTPUT_INVALID", "evaluation", "validation")
    trace = parse(ExpressionTrace, strict_json(safe_path(directory / "trace.json", areas=(directory,)).read_bytes()))
    attempts = tuple(t for e in expected for t in e.traces)
    if (trace.run_manifest_sha256 != pin or trace.mock_calls != sum(t.mock_calls for t in attempts)
            or [{k: v for k, v in data(t).items() if k != "elapsed_ms"} for t in trace.attempts]
            != [{k: v for k, v in data(t).items() if k != "elapsed_ms"} for t in attempts]):
        fail("G2_PR5_OUTPUT_INVALID", "evaluation", "trace")
    return manifest, tuple(e.result for e in expected)


def evaluate_run(directory, *, run_manifest_sha256, reference_manifest, reference_sha256, out):
    out = output_location(out)
    manifest, results = load_expression_run(directory, run_manifest_sha256)
    references = load_reference(reference_manifest, reference_sha256)
    errors, checked = [], 0
    for result in results:
        target = references.get(result.cursor.timeline_id) if manifest.mode == "mock" else None
        if target:
            checked += 1
            for p, a in zip(result.presentations, result.assessments, strict=True):
                # Temporal scenarios may have earlier ordinary snapshots; expected selection stays fixed.
                if p.selection != target["selection"] or a.code != target["code"]:
                    errors.append(dict(case_id=result.cursor.timeline_id, step_id=result.cursor.step_id,
                        predicted_selection=p.selection, predicted_code=a.code, expected=target,
                        root_cause="expression_rule_mock_or_reference_review_required",
                        label_origin="synthetic_fixture", review_origin="ai_development"))
    assessments = [a for r in results for a in r.assessments]
    accepted = sum(a.status == "accepted" for a in assessments)
    attempted = sum(a.status != "skipped" for a in assessments)
    metrics = dict(ok=not errors, mode=manifest.mode,
        reference_applicability="mock_expression" if manifest.mode == "mock" else "not_applicable_rule_baseline",
        validation_scope="pr5_ai_development", independent_research="not_evaluated",
        semantic_truth="not_evaluated", ai_semantic_review="separate_non_blind_record",
        reference_sha256=reference_sha256, prediction_manifest_sha256=run_manifest_sha256,
        expression_acceptance=ratio(accepted, attempted), reference_steps=checked, reference_errors=len(errors),
        known_reference=ratio(checked - len({e['step_id'] for e in errors}), checked),
        unique_items=len({p.base_item.item_id for r in results for p in r.presentations}),
        repeated_step_observations=sum(len(r.presentations) for r in results),
        fallbacks=sum(a.status == "fallback" for a in assessments), skipped=sum(a.status == "skipped" for a in assessments),
        error_codes={c: sum(a.code == c for a in assessments) for c in sorted({a.code for a in assessments if a.code})},
        mock_calls=attempted, model_calls=0, external_requests=0, billed_cost=0)
    write_payloads(out, {"metrics.json": json_bytes(metrics), "errors.jsonl": b"".join(json_bytes(e) for e in errors)})
    return dict(ok=not errors, errors=len(errors), metrics_sha256=sha256_bytes(json_bytes(metrics)))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--run-manifest-sha256", required=True)
    parser.add_argument("--reference-manifest", type=Path, required=True)
    parser.add_argument("--reference-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = evaluate_run(args.run, run_manifest_sha256=args.run_manifest_sha256,
            reference_manifest=args.reference_manifest, reference_sha256=args.reference_sha256, out=args.out)
    except ContractError as error:
        print_error(error)
        return 1
    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
        print_error(G2Error("G2_PR5_REFERENCE_CONFLICT", stage="input", field="reference"))
        return 1
    print(json_bytes(result).decode().strip())
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
