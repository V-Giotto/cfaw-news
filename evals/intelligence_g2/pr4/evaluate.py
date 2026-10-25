"""Separate-process development checks; never changes predictions or expectations."""

import argparse
from pathlib import Path

from evals.intelligence_g2.contracts import PACKAGE, ROOT, G2Error, json_bytes, read_json
from evals.intelligence_g2.replay import OUTPUT_BASE, output_location, safe_path, write_payloads
from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.hashing import sha256_bytes

from .contracts import GenerationResult, RunManifest, data, digest, fail, parse
from .load_run import load_evidence_run
from .reference_loader import load_reference
from .replay import STREAMS, current_sources, print_error, projection_record, run_sequence


def ratio(n, d):
    return dict(numerator=n, denominator=d, value=n / d if d else None,
                unavailable_reason=None if d else "zero_denominator")


def load_item_run(directory, pin):
    directory = safe_path(directory, areas=(OUTPUT_BASE,))
    raw = safe_path(directory / "run_manifest.json", areas=(directory,)).read_bytes()
    if sha256_bytes(raw) != pin:
        fail("MANIFEST_SHA_MISMATCH", "evaluation", "run_manifest")
    manifest = parse(RunManifest, read_json(raw), stage="evaluation")
    if manifest.runtime_source_sha256 != current_sources():
        fail("RUNTIME_CODE_MISMATCH", "evaluation", "runtime_source_sha256")
    schemas = {p.relative_to(PACKAGE).as_posix(): sha256_bytes(p.read_bytes()) for p in (PACKAGE / "schema/v4").glob("*.schema.json")}
    if manifest.schema_sha256 != schemas:
        fail("SHA_MISMATCH", "evaluation", "schema_sha256")
    names = {n + ".jsonl" for n in STREAMS} | {"input_projections.jsonl", "config_snapshot.json", "validation_report.json"}
    payloads = {}
    for entry in manifest.artifacts:
        if entry.path not in names or entry.path in payloads:
            fail("PREDICTION_PATH_INVALID", "evaluation", "artifact")
        raw = safe_path(directory / entry.path, areas=(directory,)).read_bytes()
        if (sha256_bytes(raw) != entry.sha256 or len(raw) != entry.byte_count
                or entry.record_count is not None and len(raw.splitlines()) != entry.record_count):
            fail("SHA_MISMATCH", "evaluation", "artifact", entry.path)
        payloads[entry.path] = raw
    if set(payloads) != names:
        fail("G2_PR4_PARENT_RUN_MISMATCH", "evaluation", "artifacts")
    from .contracts import PR4Config
    config = parse(PR4Config, read_json(payloads["config_snapshot.json"]), stage="evaluation")
    if manifest.config_sha256 != digest(config):
        fail("CONFIG_SHA_MISMATCH", "evaluation", "config")
    parent, inputs, evidence, parent_config = load_evidence_run(ROOT / manifest.parent_run_path,
        manifest_sha256=manifest.parent_manifest_sha256, through_step=manifest.through_step)
    if manifest.dependency_lock_sha256 != parent.dependency_lock_sha256:
        fail("SHA_MISMATCH", "evaluation", "dependency_locks")
    values, expected = run_sequence(inputs, evidence, config=config, evidence_config=parent_config)
    if manifest.selected_input_sha256 != digest([digest(v) for v in values]):
        fail("G2_PR4_PARENT_RUN_MISMATCH", "evaluation", "selected_input_sha256")
    columns = {field: [read_json(line) for line in payloads[name + ".jsonl"].splitlines()] for name, field in STREAMS.items()}
    projections = [read_json(line) for line in payloads["input_projections.jsonl"].splitlines()]
    report = read_json(payloads["validation_report.json"])
    if (any(len(rows) != len(expected) for rows in columns.values()) or len(projections) != len(expected)
            or len(report["steps"]) != len(expected) or report["ok"] is not True):
        fail("G2_PR4_PARENT_RUN_MISMATCH", "evaluation", "steps")
    results = []
    for i, result in enumerate(expected):
        cursor = data(result.cursor)
        if any(rows[i]["cursor"] != cursor for rows in columns.values()) or projections[i] != read_json(json_bytes(projection_record(values[i]))):
            fail("G2_PR4_PARENT_RUN_MISMATCH", "evaluation", "cursor_projection")
        actual = parse(GenerationResult, {"cursor": cursor, **{f: rows[i][f] for f, rows in columns.items()},
            "validation": report["steps"][i]}, stage="evaluation")
        if actual != result:
            fail("G2_PR4_FACT_PROVENANCE_INVALID", "evaluation", "result", result.cursor.step_id)
        results.append(actual)
    return manifest, tuple(results)


def evaluate_run(directory, *, run_manifest_sha256, reference_manifest, reference_sha256, out):
    target = output_location(out)
    manifest, results = load_item_run(directory, run_manifest_sha256)
    refs = load_reference(reference_manifest, reference_sha256)
    case = refs.get(results[0].cursor.timeline_id)
    errors = []
    if case:
        for i, r in enumerate(results):
            actual = sorted(item.tier_candidate for item in r.items)
            if i >= len(case["tiers"]) or actual != case["tiers"][i]:
                errors.append(dict(case_id=r.cursor.timeline_id, step_id=r.cursor.step_id,
                    kind="candidate_tier", predicted=actual, expected=case["tiers"][i] if i < len(case["tiers"]) else None,
                    root_cause="policy_or_reference_review_required", label_origin="synthetic_fixture", review_origin="ai_development"))
    items = [v for r in results for v in r.items]
    citations = [v for r in results for v in r.citations]
    metrics = dict(ok=not errors, validation_scope="pr4_ai_development", reference_sha256=reference_sha256,
        prediction_manifest_sha256=run_manifest_sha256, config_sha256=manifest.config_sha256,
        tiers=ratio(len(results) - len(errors), len(results)) if case else ratio(0, 0),
        structural_citation_fidelity=ratio(len(citations), len(citations)),
        unique_citations=len({c.ref_id for c in citations}), repeated_step_citation_observations=len(citations),
        items=len(items), focus=sum(i.tier_candidate == "focus" for i in items),
        radar=sum(i.tier_candidate == "radar" for i in items), hold=sum(i.tier_candidate == "hold" for i in items),
        degradation_reasons={k: sum(k in i.tier_reason_codes for i in items) for k in sorted({k for i in items for k in i.tier_reason_codes})},
        ai_semantic_review="separate_non_blind_record", independent_research="not_evaluated", model_calls=0,
        error_count=len(errors))
    write_payloads(target, {"metrics.json": json_bytes(metrics), "errors.jsonl": b"".join(json_bytes(e) for e in errors)})
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
    except (OSError, ValueError, TypeError, KeyError):
        print_error(G2Error("G2_PR4_REFERENCE_CONFLICT", stage="evaluation", field="reference"))
        return 1
    print(json_bytes(result).decode().strip())
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
