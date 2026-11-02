"""Requested-window diagnostics, separate from unchanged native G2 observations."""

from collections import Counter

from evals.intelligence_g3.budget import STATUSES, _source_coverage
from evals.intelligence_g3.budget_contracts import CoverageDiagnostics


def diagnose(step, source_ids, step_index):
    """Reuse the frozen interval-union policy, rebasing only its evidence pointers."""
    windows = step.source_coverage
    observed = {w.source_id for w in windows}
    expected = set(source_ids)
    rows = []
    for source_id in sorted(expected | observed):
        row = _source_coverage(source_id, tuple(enumerate(windows)),
                               step.time_window_start, step.time_window_end)
        # The existing helper's pointers address BudgetInput. Here they address the
        # same unchanged raw observation inside the bound G4 RuntimeBriefing input.
        def pointers(refs):
            return tuple(f"/input/steps/{step_index}/source_coverage/{r.rsplit('/', 1)[1]}"
                         for r in refs)

        row["window_refs"] = pointers(row["window_refs"])
        for segment in row["segments"]:
            segment["window_refs"] = pointers(segment["window_refs"])
        rows.append(row)
    counts = Counter(w.status for w in windows)
    statuses = tuple(sorted({s["status"] for s in rows})) or ("unknown",)
    return CoverageDiagnostics(
        requested_start_at=step.time_window_start, requested_end_at=step.time_window_end,
        windows=windows, status_counts={s: counts[s] for s in STATUSES},
        source_count=len(rows), window_count=len(windows),
        missing_source_ids=tuple(sorted(expected - observed)),
        unobserved_source_ids=tuple(s["source_id"] for s in rows if not s["window_refs"]),
        sources=tuple(rows), effective_statuses=statuses,
        has_gap=any(s != "covered" for s in statuses))
