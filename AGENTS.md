# CFAW News development

- Product and research source of truth: `docs/CFAW_News_V1.md` (2026-10-20). V1 is an AI developer intelligence briefing with broad discovery, evidence, event grouping, focus/radar tiers, exposure history and revisit coverage. Users visit voluntarily; no default out-of-app notifications or autonomous actions.
- G1 implementation source of truth: `docs/plans/G1_IMPLEMENTATION_PLAN.md`. Its PR1-PR5 contracts, temporal/gold separation, B0-B4 baselines and acceptance gates refine the V1 specification; they are plans, not implemented capabilities.
- The previous goal-first roadmap, 24-week schedule and redundant handoff/archive documents have been removed. Do not recreate or follow them. Keep legacy goals/runs/decisions/approved schedules compatible; do not start training, broad UI redesign or continuous Agent frameworks before the V1/G1 gates are met.
- Current source-level audit and gate evidence: `audit/G0_REUSE_AUDIT.md` and `audit/G0_BASELINE.json`. Recheck current code/commands rather than treating prior audit results as newly verified.
- This is a standalone Python/React project. Runtime code must not depend on the legacy competition platform.
- Keep domain rules independent from HTTP/UI: immutable evidence, goal versions, no late publication after cancellation, explicit approval, idempotent calendar writes.
- `baseline` is lexical retrieval, not LLM reasoning. Never present fixture or mocked results as live-model validation.
- Preserve `data/archive/articles.json` and migration provenance. Curator summaries, publisher quotes and model explanations are different evidence types.
- Keep credentials and local user data out of Git. Do not read or copy another project's credentials.
- Development diaries belong in `dev-diaries/` and must remain local. Never stage, force-add, commit, push, or upload that directory or its contents; preserve its root `.gitignore` rule.
- Run `python -m ruff check backend tests evals`, `python -m pytest -q`, `python evals/run_baseline.py`, and `npm run build` in `frontend` for relevant changes.
- Frontend `dist` is generated. Change source and rebuild.
- API is a local single-user starter. Do not claim authentication, production deployment, durable checkpoints, vector retrieval or algorithm gains before implementing and verifying them.
