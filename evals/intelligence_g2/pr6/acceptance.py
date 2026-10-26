"""Evidence-derived development acceptance. Human research is never a required gate."""

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path

from evals.intelligence_g2.contracts import read_json

from .checks import verify_checks
from .contracts import G2AcceptanceResult, Gate, cli_entry, fail, json_bytes
from .manifest import ROOT, finish, output_location, pinned, relative, sealed, source_release


def decide(gates, commit):
    names = {f"H{i:02}" for i in range(1, 11)}
    if not set(gates) <= names:
        fail("G2_PR6_EVIDENCE_MISMATCH", "gate_names")
    gates = {
        name: gates.get(
            name, Gate(status="BLOCKED", evidence=(), reason="Missing current evidence")
        )
        for name in sorted(names)
    }
    passed = set(gates) == {f"H{i:02}" for i in range(1, 11)} and all(
        g.status == "PASS" and g.evidence for g in gates.values()
    )
    return G2AcceptanceResult(
        source_commit=commit,
        gates=gates,
        overall_status="PASS" if passed else "NOT_MET",
        g3_offline_eligible=passed,
    )


def verify_review(path, pin, *, prediction_pin, evaluation_pin, commit, cases):
    rows = [read_json(line) for line in pinned(path, pin).splitlines()]
    if {r.get("case_id") for r in rows} != set(cases) or len(rows) != len(cases):
        fail("G2_PR6_REVIEW_INVALID", "case_coverage")
    for r in rows:
        try:
            stamp = datetime.fromisoformat(r.get("actual_created_at", ""))
            valid_time = stamp.tzinfo is not None
        except (ValueError, TypeError):
            valid_time = False
        if (
            r.get("source_commit") != commit
            or r.get("prediction_manifest_sha256") != prediction_pin
            or r.get("evaluation_manifest_sha256") != evaluation_pin
            or r.get("executor_type") != "ai"
            or r.get("review_origin") != "ai_development"
            or r.get("non_blind") is not True
            or r.get("independent_validation") is not False
            or r.get("semantic_truth") != "not_evaluated"
            or not r.get("model_id")
            or not r.get("findings")
            or not r.get("context_exposure")
            or not valid_time
        ):
            fail("G2_PR6_REVIEW_INVALID", "review_binding")
    return rows


def accept(
    *, run, run_pin, evaluation, evaluation_pin, checks, checks_pin, review, review_pin, out
):
    # All calls below verify actual artifacts; no caller-provided PASS switches exist.
    from .evaluate import compare, references, verify_predictions
    from .handoff import views

    run, evaluation = Path(run).absolute(), Path(evaluation).absolute()
    pred = sealed(run, run_pin)
    ev = sealed(Path(evaluation), evaluation_pin)
    checked, coverage = verify_checks(checks, checks_pin)
    commit = checked.source_release.source_commit
    if (
        pred["source_commit"] != commit
        or ev["source_commit"] != commit
        or ev["prediction_manifest_sha256"] != run_pin
    ):
        fail("G2_PR6_EVIDENCE_MISMATCH", "source_or_prediction")
    release = source_release(commit)
    if release != checked.source_release:
        fail("RUNTIME_CODE_MISMATCH", "acceptance_source")
    campaign, executions, records = asyncio.run(verify_predictions(Path(run), pred))
    refs, pairs, continuity = references(
        ROOT / relative(ev["reference_manifest_path"]), ev["reference_manifest_sha256"]
    )
    recomputed = compare(executions, records, refs, pairs, continuity)
    metrics = read_json((Path(evaluation) / "metrics.json").read_bytes())
    if json_bytes(metrics) != json_bytes(recomputed):
        fail("G2_PR6_EVIDENCE_MISMATCH", "metrics")
    reviews = verify_review(
        review,
        review_pin,
        prediction_pin=run_pin,
        evaluation_pin=evaluation_pin,
        commit=commit,
        cases=refs,
    )
    tiers = {
        k: sum(c["metrics"]["tiers"].get(k, 0) for c in metrics["cohorts"])
        for k in ("focus", "radar", "hold")
    }
    exercised = metrics["exercised"]
    controls = all(
        exercised.get(c, 0) > 0
        for c in ("E02-negative", "E03-negative", "E04-negative", "E11-negative", "E12-negative")
    )
    modes = {c["error_mode"] for c in refs.values()}
    accepted_styles = {
        style.split("-")[0]
        for c in metrics["cohorts"]
        for style, count in c["metrics"]["accepted_styles"].items()
        if count
    }
    positive = (
        {"ordinary", "corrects", "retracts", "conflict"} <= accepted_styles
        and all(tiers.values())
        and sum(c["metrics"]["supports"] for c in metrics["cohorts"]) > 0
        and sum(c["metrics"]["refutes"] for c in metrics["cohorts"]) > 0
    )
    r1_ok = all(
        c["grouping_counts"].get("fp", 0) == 0 for c in metrics["cohorts"] if c["strategy"] == "r1"
    )
    complete = campaign.scope == "full"
    no_errors = metrics["ok"] and not metrics["errors"]
    conditions = {
        "H01": no_errors,
        "H02": no_errors and r1_ok,
        "H03": no_errors,
        "H04": no_errors and controls and positive,
        "H05": no_errors and positive,
        "H06": complete and all(metrics["determinism"].values()),
        "H07": checked.source_unchanged,
        "H08": len(reviews) == len(refs),
        "H09": metrics["external_requests"] == metrics["model_calls"] == 0,
        "H10": modes == {f"E{i:02}" for i in range(1, 13)}
        and metrics["independent_research"] == "not_evaluated",
    }
    gates = {
        name: Gate(
            status="PASS" if passed else "FAIL",
            evidence=(run_pin, evaluation_pin, checks_pin, review_pin),
            reason="Verified current-source artifacts and required tests"
            if passed
            else "Current evidence does not meet this gate",
        )
        for name, passed in conditions.items()
    }
    result = decide(gates, commit)
    target = output_location(out)
    target.mkdir(parents=True)
    samples = []
    for e in executions:
        j = e.job
        if (
            j.strategy == "r1"
            and j.profile == "standard"
            and j.seed == 1
            and j.order == "canonical"
            and j.mode == "mock"
            and not j.prefix
        ):
            for record in records.get(j.job_id, ()):
                samples.extend(views(record, e.trace_path))
    lines = [
        "# G2 development acceptance",
        "",
        f"Source commit: `{commit}`.",
        f"Engineering: **{result.overall_status}**. Administrator: pending. G3 authorization: false.",
        "",
        "| Gate | Status |",
        "|---|---|",
    ] + [f"| {n} | {g.status} |" for n, g in gates.items()]
    lines += [
        "",
        f"Prediction/evaluation/checks/review pins: {run_pin} / {evaluation_pin} / {checks_pin} / {review_pin}.",
        f"Full nodes: {coverage['full']['nodes']}; exempt skips: {coverage['full']['skipped']}; G2 T01-T46 mappings: {len(coverage['full']['requirements'])}.",
        f"Real requests/model calls/cost: {metrics['external_requests']}/{metrics['model_calls']}/0. Scope: {campaign.scope}.",
        "",
        "| Cohort | Strategy | FP | FN | Precision | Recall |",
        "|---|---|---:|---:|---|---|",
    ]
    for cohort in metrics["cohorts"]:
        if cohort["profile"] == "standard" and cohort["mode"] == "rule":
            lines.append(
                f"| {cohort['cohort']} | {cohort['strategy']} | {cohort['grouping_counts'].get('fp', 0)} | {cohort['grouping_counts'].get('fn', 0)} | {cohort['pair_precision']['value']} | {cohort['pair_recall']['value']} |"
            )
    lines += [
        "",
        "Human independent review, double annotation, user research and generalization: not_evaluated.",
        "Optional real material: deferred. No live model, network, production DB, UI or ranking integration.",
        "",
        "Administrator summary: inspect source/pins, test coverage/skips, FP/FN, budget/fallbacks and 3-5 synthetic examples.",
    ]
    example_lines = [
        "# Synthetic examples",
        "",
        "AI development; source truth not independently evaluated.",
    ]
    for e in executions:
        j = e.job
        if (
            j.case_id
            not in {
                "E04-positive",
                "E05-conflict",
                "E06-correction",
                "E09-negative",
                "E10-negative",
            }
            or j.strategy != "r1"
            or j.profile != "standard"
            or j.mode != "mock"
            or j.seed != 1
            or j.order != "canonical"
            or j.prefix
        ):
            continue
        sequence = records.get(j.job_id, ())
        if not sequence:
            continue
        example_lines.extend(["", "## " + j.case_id])
        if not sequence[-1].rule.items:
            example_lines.append("Zero event / zero Item; coverage gaps retained.")
        for presentation in sequence[-1].expression.presentations:
            example_lines.extend(
                [
                    "Tier: " + presentation.base_item.tier_candidate,
                    presentation.headline or "Hold: no factual headline",
                    presentation.body or "No factual body",
                    "Risks: " + "; ".join(r.text for r in presentation.base_item.risks),
                ]
            )
    payloads = {
        "synthetic_examples.md": ("\n".join(example_lines) + "\n").encode("utf-8"),
        "G2_ACCEPTANCE.json": json_bytes(result),
        "G2_ACCEPTANCE.md": ("\n".join(lines) + "\n").encode(),
        "G3_HANDOFF.json": json_bytes(samples),
        "G3_HANDOFF.md": b"# G3 handoff\n\nImmutable event/bundle/rule/presentation snapshots only. No personalized rank.\n",
        "requirements_coverage.json": json_bytes(coverage),
        "source_release.json": json_bytes(release),
    }
    pin = finish(
        target,
        payloads,
        dict(
            role="g2_development_acceptance",
            source_commit=commit,
            prediction_manifest_sha256=run_pin,
            evaluation_manifest_sha256=evaluation_pin,
            checks_sha256=checks_pin,
            ai_review_sha256=review_pin,
        ),
    )
    return result, pin


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--profile", choices=["g2_development"], required=True)
    for name in (
        "run",
        "run-manifest-sha256",
        "evaluation",
        "evaluation-manifest-sha256",
        "checks",
        "checks-sha256",
        "ai-review",
        "ai-review-sha256",
        "out",
    ):
        p.add_argument("--" + name, required=True)
    a = p.parse_args(argv)
    result, pin = accept(
        run=a.run,
        run_pin=a.run_manifest_sha256,
        evaluation=a.evaluation,
        evaluation_pin=a.evaluation_manifest_sha256,
        checks=a.checks,
        checks_pin=a.checks_sha256,
        review=a.ai_review,
        review_pin=a.ai_review_sha256,
        out=a.out,
    )
    print(json.dumps(dict(overall_status=result.overall_status, run_manifest_sha256=pin)))
    return 0 if result.overall_status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(cli_entry(main))
