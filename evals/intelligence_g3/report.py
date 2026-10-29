"""Reports derived from frozen counts, including unfavorable outcomes."""

from pathlib import Path

from evals.intelligence_g2.contracts import read_json

from .fact_signature import policy, policy_sha256


def markdown(metrics, run):
    lines = ["# G3 PR5 offline AI development report", "",
        "Synthetic, nonblind, reused development regression material. No independent human gold, "
        "held-out test, production readiness or real-user effect is established.", "",
        f"Fact feature policy: {policy()['revision']}; SHA256: {policy_sha256()}. "
        "Scoring weights and wire schemas retain their registered versions; the independent "
        "fact extractor revision is bound in comparisons and the reproduction policy artifact.", "",
        f"Event product families: {metrics['event_family_count']}; independent test families: 0.", "",
        "Samples below count correlated event-by-case-by-budget states. Reprints, horizons and "
        "repeated seeds are not independent samples. Seeds are checked for equality and counted once.", "",
        "| Variant | Axis/cell | Important recall n/d | Miss n/d | Duplicate n/d | nDCG DCG/IDCG | samples | families |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for row in metrics["aggregates"]:
        m = row["metrics"]
        def counts(name):
            v = m[name]
            return (f"{v['numerator']:.5g}/{v['denominator']:.5g}" if v["denominator"] else
                    "undefined: " + v["undefined_reason"])
        lines.append(f"| {row['variant']} | {row['axis']}/{row['cell']} | "
            f"{counts('ImportantEventRecall@budget')} | {counts('ImportantMissRate')} | "
            f"{counts('DuplicateExposureRate')} | {counts('nDCG@10')} | "
            f"{m['ImportantEventRecall@budget']['sample_count']} | {len(row['family_ids'])} |")
    lines += ["", "## Revisit metric support", "",
        "Revisit metrics count candidate-event states only inside their own window. Outside-window "
        "cases contribute zero samples and zero families. dataset_support separately records the "
        "whole cell; it is never substituted for metric support.", "",
        "| Variant | Window | Recall n/d | Applicable samples | Applicable families | Undefined reason |",
        "| --- | --- | --- | --- | --- | --- |"]
    for row in metrics["aggregates"]:
        if row["axis"] != "all":
            continue
        for window in (1, 3, 7):
            value = row["metrics"][f"RevisitCoverage@{window}d"]
            lines.append(f"| {row['variant']} | {window}d | {value['numerator']:g}/"
                f"{value['denominator']:g} | {value['sample_count']} | {value['event_family_count']} | "
                f"{value['undefined_reason'] or ''} |")
    lines += ["", "## Interpretation and failures", "",
        "B4 remains the baseline. P1 is not required to win; no independent stable improvement "
        "has been demonstrated. Per-job metrics, numerator/denominator, sample and family counts, "
        "data_source and undefined_reason are retained in metrics.json.", "",
        f"Failure records: {metrics['failure_count']}, including every evaluable important miss "
        "and duplicate presentation. budget_unmet never removes an important event from a denominator. "
        "A protected item may fail to fit even when an alternative combination of minimum projections "
        "could fit; the registered greedy allocator does not solve a knapsack optimum.", "",
        "nDCG@10 measures eligible rank order with all reference gains in IDCG; recall uses actual "
        "budget selection. Duplicate labels describe authored unchanged delivered events; opened "
        "does not establish knowledge. Domain coverage is lexical; exploration exposure is a feature proxy.", "",
        "## Ablations and B2", "",
        "no_history disables all history-dependent P1 score terms (novelty, material change, exploration, "
        "duplicate). no_material, no_novelty_material, no_exploration and no_duplicate zero their "
        "registered contributions without renormalization. Hard eligibility and mandatory update "
        "protection remain active in all variants. These are score ablations, not removal of safety/history "
        "validation. They use a separate experiment envelope, never a changed PR2/PR3 algorithm version.", "",
        "B2 is reported separately in b2_g2_contribution. G2 already merged the event pool; B2 preserves "
        "identity and equals B1. G2 aggregation gain is undefined because there is no unmerged-document "
        "comparison arm. It is not credited to G3.", "",
        "## Cost, reproducibility and limits", ""]
    root = Path(run)
    if (root / "summary.json").is_file():
        summary = read_json((root / "summary.json").read_bytes())
        seconds = []
        for seed in (1, 719):
            rows = read_json((root / f"timings-{seed}.json").read_bytes())
            seconds.extend(r["elapsed_seconds"] for r in rows)
        lines += [f"Actual prediction runs: {summary['actual_prediction_runs']}; semantic outputs per "
            f"seed: {summary['jobs_per_seed']}; all cross-seed semantic hashes equal.", "",
            f"Measured prediction wall seconds (sum of per-job timers): {sum(seconds):.6f}; "
            f"mean {sum(seconds) / len(seconds):.6f}; max {max(seconds):.6f}. "
            "Process commands separately include startup, validation and serialization overhead.", "",
            "External requests and model calls: 0, network guarded during prediction. Token count and "
            "provider cost are undefined (no model/provider invocation); no estimated billing or "
            "host electricity/hardware cost is asserted.", ""]
    lines += ["No confidence interval or significance claim: purposive reused nonblind families, "
        "no independent holdout. Reading time is a deterministic uncalibrated estimate. Material change "
        "uses attributed statement-set proxies. Source coverage gaps never confirm absence of updates.", "",
        "The source release binds the exact working tree, anchor commit, tests, schemas, configs, "
        "frozen fixtures and pytest control plane. The approved root configuration and conftest hashes, "
        "pytest/pluggy code and bytecode, plugin discovery metadata, startup files and controlled "
        "environment are recorded. Autoload is disabled; unapproved config, hook, plugin or environment "
        "injection is rejected. Actual collect/G3/full execution records list loaded plugin origins. "
        "It does not claim these uncommitted changes are a published commit. "
        "Remote CI, Linux portability, live providers, DB/API/frontend integration and user research "
        "are not verified by this report.", "",
        "G4 requires independent PR5 review and owner approval. Preserve the offline input/output "
        "contract and diagnostics before any separate integration design.", ""]
    return "\n".join(lines)
