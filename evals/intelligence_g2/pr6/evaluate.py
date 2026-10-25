"""Post-seal development evaluation. Never imported by the prediction worker."""

import argparse
import asyncio
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone

from evals.intelligence_g2.contracts import read_json

from .contracts import (
    CampaignSpec,
    CaseExecution,
    DevelopmentReference,
    SourceRelease,
    StepRecord,
    cli_entry,
    data,
    digest,
    fail,
    json_bytes,
    parse,
)
from .manifest import ROOT, finish, output_location, pinned, relative, sealed, source_release
from .metrics import pair_counts, ratio, summarize


def references(path, pin):
    from pathlib import Path

    header = read_json(pinned(path, pin))
    if (
        header.get("revision") != "g2-pr6-references-v1"
        or header.get("label_origin") != "synthetic_fixture"
    ):
        fail("G2_PR6_ROLE_INVALID", "reference_manifest")
    rows = []
    seen = set()
    for e in header["files"]:
        if e["role"] != "reference" or e["path"] in seen:
            fail("G2_PR6_ROLE_INVALID", "reference_files")
        seen.add(e["path"])
        rows.extend(
            read_json(pinned(Path(path).parent / relative(e["path"]), e["sha256"]))["cases"]
        )
    rows = [data(parse(DevelopmentReference, r)) for r in rows]
    if len({r["case_id"] for r in rows}) != len(rows):
        fail("DUPLICATE_ID", "reference_cases")
    from evals.intelligence_g2.pr2.reference_loader import load_references

    upstream = header["upstream_reference"]
    _, pairs, continuity = load_references(
        ROOT / relative(upstream["path"]), pin=upstream["sha256"]
    )
    return {r["case_id"]: r for r in rows}, pairs, continuity


def check_case(execution, records, reference):
    """Frozen development checks, not an independent source-truth oracle."""
    if reference is None:
        return []
    job = execution.job
    errors = []
    expected = reference["expected_code"]
    if not execution.returned:
        if (
            expected not in {"FUTURE_VERSION", "ORIGIN_MISMATCH", "G2_PR6_SENSITIVE_EXPORT"}
            or execution.diagnostic["code"] != expected
        ):
            errors.append("unexpected_rejection")
        return errors
    if expected in {"FUTURE_VERSION", "ORIGIN_MISMATCH", "G2_PR6_SENSITIVE_EXPORT"}:
        return ["future_input_published"]
    current = records[-1]
    attempts = [a for r in records for a in r.expression.assessments if a.status != "skipped"]
    if job.mode == "mock" and expected is not None:
        if attempts:
            if any(a.code != expected or a.status != "fallback" for a in attempts):
                errors.append("wrong_expression_failure")
        elif any(
            i.tier_candidate != "hold" or i.tier_reason_codes != ("visible_budget_exceeded",)
            for r in records
            for i in r.rule.items
        ):
            errors.append("fault_not_exercised")
    if job.mode == "mock" and expected is None and any(a.status != "accepted" for a in attempts):
        errors.append("unexpected_model_fallback")
    checks = reference["checks"]
    if "no_independent_upgrade" in checks and any(
        a.independent_support_count or a.verification_state == "independently_supported"
        for r in records
        for a in r.evidence.assessments
    ):
        errors.append("independence_upgrade")
    if "scope_difference" in checks and (
        current.evidence.conflicts
        or any(link.direction in {"supports", "refutes"} for link in current.evidence.links)
    ):
        errors.append("cross_scope_support_or_conflict")
    if (
        "unresolved" in checks
        and not job.prefix
        and (
            current.evidence.transitions
            or "unresolved_withdrawal"
            not in {g.code for g in current.evidence.validation.coverage_gaps}
        )
    ):
        errors.append("incorrect_withdrawal")
    if (
        "withdrawal" in checks
        and not job.prefix
        and "retracts" not in {t.kind for t in current.evidence.transitions}
    ):
        errors.append("missing_withdrawal")
    if (
        "correction" in checks
        and not job.prefix
        and "corrects" not in {t.kind for t in current.evidence.transitions}
    ):
        errors.append("missing_correction")
    if "conflict" in checks and not current.evidence.conflicts:
        errors.append("missing_reported_conflict")
    if "repurposed" in checks and not job.prefix:
        old = {c.claim_key for c in records[0].evidence.claims}
        if old & {k for b in current.evidence.bundles for k in b.historical_claim_keys} or (
            records[0].grouping.events[0].event_key == current.grouping.events[0].event_key
        ):
            errors.append("old_claim_moved_to_new_event")
    if (
        "stable_identity" in checks
        and records[0].grouping.events[0].event_key != current.grouping.events[0].event_key
    ):
        errors.append("unexplained_identity_change")
    if "different_event" in checks and job.strategy != "r0" and len(current.grouping.events) != 2:
        errors.append("false_merge")
    if "duplicate" in checks and len(current.grouping.events) != 1:
        errors.append("missed_duplicate")
    if "body_loss" in checks and (
        current.evidence.claims
        or any(
            i.headline is not None or i.what_happened is not None or i.tier_candidate != "hold"
            for i in current.rule.items
        )
    ):
        errors.append("fabricated_body")
    if "empty_coverage" in checks and (
        current.rule.items or not current.rule.validation.coverage_gaps
    ):
        errors.append("empty_information_hidden")
    if "nonempty" in checks and not current.evidence.claims:
        errors.append("positive_control_empty")
    if "secondary" in checks and any(
        c.attribution.attribution_kind != "secondary_material" for c in current.evidence.claims
    ):
        errors.append("secondary_treated_as_primary")
    return errors


def verify_job_set(executions, campaign):
    from .reproduce import make_jobs

    if [data(e.job) for e in executions] != [data(j) for j in make_jobs(campaign)]:
        fail("G2_PR6_MATRIX_INVALID", "job_set")


async def verify_predictions(directory, manifest):
    """Exact current-source replay, including failures; do not trust ok flags or hashes alone."""
    from .predict import run_job

    if manifest.get("role") != "prediction_campaign":
        fail("G2_PR6_ROLE_INVALID", "prediction_campaign")
    campaign = parse(CampaignSpec, read_json((directory / "campaign_snapshot.json").read_bytes()))
    release = parse(SourceRelease, read_json((directory / "source_release.json").read_bytes()))
    if (
        source_release(manifest["source_commit"]) != release
        or digest(campaign) != manifest["campaign_sha256"]
    ):
        fail("RUNTIME_CODE_MISMATCH", "source_release")
    actual = tuple(
        parse(CaseExecution, e)
        for e in read_json((directory / "predictions_index.json").read_bytes())
    )
    verify_job_set(actual, campaign)
    from evals.intelligence_v1.exceptions import ContractError

    results = {}
    for e in actual:
        try:
            records, traces = await run_job(e.job, campaign)
        except ContractError as error:
            observed = dict(
                code=error.code, stage=getattr(error, "stage", "input"), field=error.field
            )
            if e.returned or e.diagnostic != observed or e.result_path is not None:
                fail("G2_PR6_REPLAY_MISMATCH", "rejected_job")
            continue
        if not e.returned or e.result_path is None or e.trace_path is None:
            fail("G2_PR6_REPLAY_MISMATCH", "missing_result")
        raw = pinned(directory / relative(e.result_path), e.semantic_sha256, areas=(directory,))
        if raw != b"".join(json_bytes(r) for r in records):
            fail("G2_PR6_REPLAY_MISMATCH", "semantic_result")
        saved = read_json(
            pinned(directory / relative(e.trace_path), e.trace_sha256, areas=(directory,))
        )

        def without_time(rows):
            return [
                {
                    "cursor": r["cursor"],
                    "attempts": [
                        {k: v for k, v in t.items() if k != "elapsed_ms"} for t in r["attempts"]
                    ],
                }
                for r in rows
            ]

        if without_time(saved) != without_time(traces):
            fail("G2_PR6_REPLAY_MISMATCH", "trace")
        if e.pool_sha256 != digest([r.pool_sha256 for r in records]):
            fail("G2_PR6_COMPARISON_POOL_MISMATCH", "pool_digest")
        results[e.job.job_id] = tuple(
            parse(StepRecord, read_json(line)) for line in raw.splitlines()
        )
    return campaign, actual, results


def compare(executions, results, refs, pairs, continuity):
    if {e.job.case_id for e in executions if e.job.cohort == "synthetic"} != set(refs):
        fail("G2_PR6_REFERENCE_CONFLICT", "reference_case_set")
    errors = []
    variants = defaultdict(set)
    pools = defaultdict(set)
    channel_rules = defaultdict(dict)
    full = {}
    observations = defaultdict(list)
    grouping = defaultdict(Counter)
    continuity_counts = defaultdict(Counter)
    trajectory_counts = defaultdict(Counter)
    pair_errors = []
    baseline_quality = []
    reference_coverage = Counter()
    exercised = Counter()
    for e in executions:
        j = e.job
        records = results.get(j.job_id, ())
        key = (j.case_id, j.strategy, j.profile, j.mode, j.prefix)
        variants[key].add((e.returned, e.semantic_sha256, digest(e.diagnostic)))
        if e.returned:
            pools[(j.case_id, j.prefix)].add(e.pool_sha256)
            channel_rules[(j.case_id, j.strategy, j.profile, j.seed, j.order, j.prefix)][j.mode] = (
                digest([r.rule for r in records])
            )
        for code in check_case(e, records, refs.get(j.case_id)):
            # R0 is a frozen control. Keep its split-induced absence observable;
            # PR3 may not create cross-event support/conflict links to repair R0.
            if (
                j.strategy == "r0"
                and code == "missing_reported_conflict"
                and records
                and len({c.origin_event_key for c in records[-1].evidence.claims}) > 1
            ):
                baseline_quality.append(
                    dict(
                        job_id=j.job_id,
                        case_id=j.case_id,
                        kind=code,
                        root_cause="upstream_r0_separation",
                        stage="development_reference",
                        applicability="same_bundle_conflict_unavailable",
                        is_success=False,
                    )
                )
                continue
            errors.append(
                dict(job_id=j.job_id, case_id=j.case_id, kind=code, stage="development_reference")
            )
        if not j.prefix:
            full[(j.case_id, j.strategy, j.profile, j.mode, j.seed, j.order)] = records
        if j.prefix or j.seed != 1 or j.order != "canonical":
            continue
        cohort = (j.cohort, j.strategy, j.profile, j.mode)
        observations[cohort].extend(records)
        if j.cohort == "synthetic" and j.mode == "mock":
            for r in records:
                for a in r.expression.assessments:
                    if a.status != "skipped":
                        exercised[j.case_id] += 1
        for r in records:
            selected = [
                p
                for p in pairs
                if p.timeline_id == j.timeline_id and p.step_id == r.grouping.cursor.step_id
            ]
            references = []
            for p in selected:
                if p.as_of != r.grouping.cursor.as_of:
                    fail("G2_PR6_REFERENCE_CONFLICT", "pair_as_of")
                references.append(
                    (
                        p.left_doc_version_id,
                        p.right_doc_version_id,
                        "uncertain"
                        if p.relation == "uncertain"
                        else p.relation
                        in {"exact_duplicate", "syndicated", "same_event_different_evidence"},
                    )
                )
            counts = pair_counts(r.grouping.events, references)
            grouping[cohort].update(counts)
            trajectory_counts[(*cohort, j.timeline_id)].update(counts)
            owner = {
                m: event.event_key
                for event in r.grouping.events
                for m in event.member_doc_version_ids
            }
            reference_coverage["known_pair_observations"] += sum(
                label != "uncertain" for _, _, label in references
            )
            reference_coverage["unlabeled_candidate_pairs"] += max(
                0, len(owner) * (len(owner) - 1) // 2 - len(references)
            )
            for left, right, label in references:
                if label == "uncertain" or left not in owner or right not in owner:
                    continue
                if (owner[left] == owner[right]) != label:
                    pair_errors.append(
                        dict(
                            job_id=j.job_id,
                            case_id=j.case_id,
                            timeline_id=j.timeline_id,
                            step_id=r.grouping.cursor.step_id,
                            as_of=r.grouping.cursor.as_of.isoformat(),
                            left_doc_version_id=left,
                            right_doc_version_id=right,
                            kind="false_merge" if not label else "missed_merge",
                            strategy=j.strategy,
                            root_cause="requires_ai_review",
                            impact="event_membership",
                            review_origin="ai_development",
                        )
                    )
        by_step = {r.grouping.cursor.step_id: r for r in records}
        for c in continuity:
            if c.timeline_id != j.timeline_id:
                continue
            continuity_counts[cohort]["required"] += 1
            a = by_step.get(c.from_step_id)
            b = by_step.get(c.to_step_id)

            def owners(r):
                return (
                    {m: e.event_key for e in r.grouping.events for m in e.member_doc_version_ids}
                    if r
                    else {}
                )

            left, right = owners(a).get(c.from_doc_version_id), owners(b).get(c.to_doc_version_id)
            continuity_counts[cohort]["matched"] += bool(
                left and right and ((left == right) == (c.expected == "same"))
            )
    if any(len(values) != 1 for values in variants.values()):
        fail("G2_PR6_NONDETERMINISTIC", "seed_or_order")
    if any(len(values) != 1 for values in pools.values()):
        fail("G2_PR6_COMPARISON_POOL_MISMATCH", "same_pool")
    if any(
        len(set(values.values())) != 1 or set(values) != {"rule", "mock"}
        for values in channel_rules.values()
    ):
        fail("G2_PR6_REPLAY_MISMATCH", "immutable_rule")
    for e in executions:
        if e.job.prefix and e.returned:
            j = e.job
            baseline = full[(j.case_id, j.strategy, j.profile, j.mode, j.seed, j.order)]
            prefix = results[j.job_id]
            if data(prefix) != data(baseline[: len(prefix)]):
                fail("G2_PR6_NONDETERMINISTIC", "prefix")
    cohorts = []
    for key, records in sorted(observations.items()):
        cnt = grouping[key]
        tp, fp, fn = (cnt[k] for k in ("tp", "fp", "fn"))
        cohorts.append(
            dict(
                cohort=key[0],
                strategy=key[1],
                profile=key[2],
                mode=key[3],
                metrics=summarize(records),
                grouping_counts=dict(cnt),
                pair_precision=ratio(
                    tp,
                    tp + fp,
                    "no_applicable_reference"
                    if not sum(cnt[k] for k in ("tp", "fp", "fn", "tn"))
                    else "zero_denominator",
                ),
                pair_recall=ratio(
                    tp,
                    tp + fn,
                    "no_applicable_reference"
                    if not sum(cnt[k] for k in ("tp", "fp", "fn", "tn"))
                    else "zero_denominator",
                ),
                pair_f1=ratio(
                    2 * tp,
                    2 * tp + fp + fn,
                    "no_applicable_reference"
                    if not sum(cnt[k] for k in ("tp", "fp", "fn", "tn"))
                    else "zero_denominator",
                ),
                continuity=ratio(
                    continuity_counts[key]["matched"],
                    continuity_counts[key]["required"],
                    "no_applicable_reference",
                ),
            )
        )
    trajectories = []
    for key, cnt in sorted(trajectory_counts.items()):
        tp, fp, fn = (cnt[k] for k in ("tp", "fp", "fn"))
        trajectories.append(
            dict(
                cohort=key[0],
                strategy=key[1],
                profile=key[2],
                mode=key[3],
                timeline_id=key[4],
                counts=dict(cnt),
                precision=ratio(tp, tp + fp),
                recall=ratio(tp, tp + fn),
                f1=ratio(2 * tp, 2 * tp + fp + fn),
            )
        )
    macros = []
    for cohort in cohorts:
        selected = [
            t
            for t in trajectories
            if all(t[k] == cohort[k] for k in ("cohort", "strategy", "profile", "mode"))
        ]
        values = [t["f1"].value for t in selected if t["f1"].value is not None]
        macros.append(
            dict(
                **{k: cohort[k] for k in ("cohort", "strategy", "profile", "mode")},
                applicable_trajectories=len(values),
                total_trajectories=len(selected),
                f1=sum(values) / len(values) if values else None,
                reason=None if values else "no_applicable_reference",
            )
        )
    return dict(
        baseline_quality=baseline_quality,
        trajectories=trajectories,
        trajectory_macro=macros,
        pair_errors=pair_errors,
        reference_coverage=dict(reference_coverage),
        claim_extraction_precision=ratio(0, 0, "no_applicable_reference"),
        claim_extraction_recall=ratio(0, 0, "no_applicable_reference"),
        semantic_support="ai_review_only_not_source_truth",
        ok=not errors,
        errors=errors,
        cohorts=cohorts,
        exercised=dict(exercised),
        determinism=dict(seed_order=True, prefix=True, immutable_rule=True, same_pool=True),
        scored_reference_cases=len(refs),
        unique_cases=len({e.job.case_id for e in executions}),
        job_observations=len(executions),
        review_origin="ai_development",
        independent_validation=False,
        independent_research="not_evaluated",
        model_calls=0,
        external_requests=0,
        billed_cost=0,
    )


def evaluate(run, *, run_manifest_sha256, reference_manifest, reference_sha256, out):
    from pathlib import Path

    directory = Path(run)
    manifest = sealed(directory, run_manifest_sha256)
    campaign, executions, results = asyncio.run(verify_predictions(directory, manifest))
    refs, pairs, continuity = references(reference_manifest, reference_sha256)
    expected_cases = {e.job.case_id for e in executions if e.job.cohort == "synthetic"}
    if set(refs) != expected_cases:
        fail("G2_PR6_REFERENCE_CONFLICT", "reference_case_set")
    report = compare(executions, results, refs, pairs, continuity)
    output = output_location(out)
    output.mkdir(parents=True)
    reviews = [
        dict(
            case_id=c,
            source_commit=manifest["source_commit"],
            prediction_manifest_sha256=run_manifest_sha256,
            reference_sha256=reference_sha256,
            executor_type="programmatic_check",
            review_origin="ai_development",
            independent_validation=False,
            non_blind=True,
            semantic_truth="not_evaluated",
        )
        for c in sorted(refs)
    ]
    sha = finish(
        output,
        {
            "metrics.json": json_bytes(report),
            "errors.jsonl": b"".join(
                json_bytes(e)
                for e in [*report["errors"], *report["pair_errors"], *report["baseline_quality"]]
            ),
            "errors.md": (
                "# Development errors\n\n" + "\n".join(str(e) for e in report["errors"]) + "\n"
            ).encode(),
            "development_checks.jsonl": b"".join(json_bytes(r) for r in reviews),
            "coverage_report.json": json_bytes(
                dict(
                    error_modes=sorted({r["error_mode"] for r in refs.values()}),
                    cases=sorted(refs),
                    cohorts=[
                        {k: r[k] for k in ("cohort", "strategy", "profile", "mode")}
                        for r in report["cohorts"]
                    ],
                )
            ),
            "determinism_report.json": json_bytes(report["determinism"]),
        },
        dict(
            role="development_evaluation",
            source_commit=manifest["source_commit"],
            campaign_scope=campaign.scope,
            prediction_manifest_sha256=run_manifest_sha256,
            reference_manifest_sha256=reference_sha256,
            reference_manifest_path=Path(reference_manifest).resolve().relative_to(ROOT).as_posix(),
            evaluated_at=datetime.now(timezone.utc).isoformat(),
        ),
    )
    return dict(ok=report["ok"], errors=len(report["errors"]), run_manifest_sha256=sha)


def main(argv=None):
    p = argparse.ArgumentParser()
    for name in ("run", "run-manifest-sha256", "reference-manifest", "reference-sha256", "out"):
        p.add_argument("--" + name, required=True)
    a = p.parse_args(argv)
    result = evaluate(
        a.run,
        run_manifest_sha256=a.run_manifest_sha256,
        reference_manifest=a.reference_manifest,
        reference_sha256=a.reference_sha256,
        out=a.out,
    )
    print(json.dumps(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(cli_entry(main))
