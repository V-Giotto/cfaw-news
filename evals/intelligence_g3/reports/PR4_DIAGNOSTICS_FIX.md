# G3-PR4 diagnostic repair: interval coverage and canonical interest queries

Date: 2026-10-28, Asia/Shanghai. Base HEAD remains
`fb42de414e56da7a0eb58e89d174d38a1495f02a` on `main`.

## Authorized scope and red evidence

The owner requested repair of the two P2 findings in the read-only PR4 review.
This is a PR4 repair, not authorization for PR5. Prior uncommitted PR3/PR4 work
is preserved. An initial snapshot records all 815 public file hashes, status,
combined diff and copies of files to be edited before this repair.

Read the supplied review and its actual counterexample inputs under
`C:\Users\Administrator\.codex\visualizations\2026\10\28\01a1811a-f288-7a02-bbdc-9d3ac171fce5\pr4-review-001`.
Before changing runtime code, both supplied cases reproduced their failures:

* A requested 2026-01-01 through 2026-01-02 interval, with only a covered
  2025-12-30 through 2025-12-31 window, reported `has_gap=false` and covered.
* `local`, `LOCAL`, ` local ` and `unmatched` reported four domains and 0.75
  coverage instead of two canonical lexical queries and 0.5 coverage.

`reviewer-red.json` records those two failures (exit 1). Two newly authored native
G2/G3 regression cases also failed against the original runtime (exit 1, two
failed; `tests-red.log`). They do not import the external review artifacts or
use gold labels. All grouping/evidence/item generation and G3 validation run.

## Repair behavior

`budget.py` retains raw native coverage windows/statuses and independently derives
effective coverage by source over the requested query interval. Positive-duration
queries are half-open; a zero-duration query is an explicit closed point query.
Touching boundaries and zero-length observations cannot fill a duration. Native
zero-duration observation fixtures retain their point-query semantics.

Each known source has partitioned segments, original-window pointers, observed
statuses and structured reasons. There are merged confirmed, unconfirmed and
unobserved interval unions. Adjacent/overlapping covered windows can jointly cover
the query, while holes remain unknown. Explicit non-covered observations veto
overlapping covered claims. Multiple distinct non-covered statuses are partial;
a uniform source status is retained, and mixed segment statuses are partial.
This is conservative overlap handling, not an inferred retry/supersession policy.

Raw `status_counts` still counts every supplied window. `missing_source_ids`
retains its raw meaning, while `unobserved_source_ids` exposes sources without
any applicable window for this query. Effective statuses and `has_gap` now use
the per-source query results. An empty source universe remains unknown. Coverage
does not claim absence of updates and does not change ranking or presentation.

Domain diagnostics group interests by the sorted unique token tuple from the
existing tokenizer. Each group has a stable SHA256-based `domain_key`, its query
tokens, every original label occurrence and input pointer. The first declared
label is the display label. Numerator and denominator use these canonical query
identities, including unmatched queries. Empty lexical queries form one explicit
unmatchable group; no interests means zero denominator and null aggregate.
No semantic synonym merging, Persona normalization or ranker input change occurs.

The supplied case now reports unknown coverage with an explicit full-query gap;
the alias case reports two domains, one covered and 0.5 coverage. Their original
externally supplied input pins were checked before explicit v2 replanning. Both
real pinned CLI exports exit 0, and direct wire round trips produce the same v2
plans. Original input bytes, history/Persona payloads, rankings, planned entries,
display order and complete Archive snapshot IDs remain byte-identical to the
original supplied cases. See `reviewer-green.command.json` and
`allocation-preserved.json`.

## Versioning and retained artifacts

The diagnostic semantic change is registered as `g3-budget-v2`, with
`g3-pr4-input-v2` / `g3-pr4-plan-v2`. New schemas live in `schema/v4_1/`.
`schema/v4/` remains unchanged. The original registry is preserved byte-for-byte
as `manifests/pr4_budget_configs_v1.json`; the current registry records v2 configs.
Reading rule `unicode-display-units-v1`, registered time budgets, allocation
profiles and Focus/Radar selection policy retain their definitions.

Old v1 envelopes/configs are rejected by the current loader, never silently
reinterpreted. An old trusted artifact can be explicitly replanned by validating
its unchanged `HistoryInput` and `RevisitResult`, selecting the corresponding
current profile, and saving a new bound input with a new external pin. Original
files and pins must be retained. There is no automatic migration/pin substitution.

The original 72 PR4 test nodes, source hashes and manifest pin are unchanged.
46 diagnostic regression nodes are registered separately in
`manifests/pr4_diagnostics_required_tests.json`, pin
`a6d5bde7ee1547afdf7b3565280e2df88637e6eb246e6f0cd1d0539dc6c4f6d7`.
Original PR1/PR2/PR3/frozen G1/G2 requirements and skip exemptions remain intact.

## Actual verification

Local evidence directory:
`D:\agent_project\cfaw-news\.tmp\evals\g3\pr4-diagnostics-fix-20261028-001`.
The runner's `*.command.json` retains argv, cwd, process-only environment,
timestamps, exit code, elapsed time and raw log SHA256. Existing dependencies only;
no installation, model/provider/network call or online integration was added.

| Check | Actual result | Evidence |
| --- | --- | --- |
| Original supplied counterexamples before repair | Exit 1, both reproduced | `reviewer-red.json` |
| New native counterexample regressions before repair | Exit 1, two failed | `tests-red.log` |
| Final PR4 tests | Exit 0, 118 passed = 72 original + 46 diagnostic tests | `focused-green.log` |
| Complete G3, normal-host default pytest entry | Exit 0, 494 passed | `g3.command.json`, `g3.log` |
| Complete project with required project-local basetemp | Exit 0, 1617 passed / 1 existing skip / 1 existing warning, 954.85 seconds | `full.command.json`, `full.log`, `full.xml` |
| Exact collection / inventory | Exit 0, 1618 nodes | `collect.command.json`, `inventory.command.json` |
| Full JUnit verification | Exit 0, exact 1618 nodes, no G3 skips or missing/failed nodes | `junit.command.json`, `junit.log` |
| Ruff | Exit 0 | `ruff.command.json` |
| Current schemas | Exit 0 | `schemas.command.json` |
| Baseline seed sanity | Exit 0, fixed lexical seed check only | `baseline.command.json` |
| Offline frontend compatibility build | Exit 0, fresh ignored output | `frontend.command.json`, `frontend.log` |
| Both supplied cases explicitly replanned and exported by CLI | Both exit 0, correct diagnostics, complete original source/ranking retained | `reviewer-green.command.json`, `reproductions/` |
| Source/plan preservation on supplied cases | Exit 0, original entries, order, Archive IDs, history and ranking payload bytes preserved | `allocation-preserved.json` |
| Allocation/reading/gate AST preservation | Exit 0, full allocation prefix, input gates, reading rule and estimators structurally unchanged | `allocation-code-preserved.json` |
| Interim boundary / diff audit | Exit 0, seven existing files changed, 808 initial files unchanged, no deletions; 561 verification sources stable | `boundary-initial.json`, `repair-only.diff` |
| Final boundary / source / diff audit | Exit 0, seven existing files changed, eight new files, 808 initial files unchanged, no deletions; all 561 verification sources remain unchanged | `boundary-final.json` |

The sole skipped node is the existing
`tests/evals/test_provenance_and_rights.py::test_symlink_outside_bundle_rejected_if_supported`,
reason `symlink creation unavailable: 1314`; no G3 node was skipped. The sole
warning is the existing FastAPI/Starlette HTTPX deprecation. Full JUnit matches
all required nodes/source hashes and original skip exemptions. This full pass
uses the required project-local basetemp, not default OS-temp G2 manifest paths.

The first combined test run found a typo in the new test's `model_copy` call
(class rather than instance): 108 passed / one test-construction error. The call
was corrected, preserving its rejection assertion. Additional overlap and wire
tampering regressions bring the final count to 118, all green. The original
failure remains in `first-green.log`; it is not relabelled as a passed run.

Tests cover no intersection, touching endpoints, points versus durations, leading
and trailing gaps, holes in interval unions, adjacent/overlapping/nested windows,
clipping, all five explicit statuses, conservative overlap vetoes, stale failures,
multiple sources, empty candidates/source universes, case/space/punctuation/order/
repetition equivalents, empty queries/interests, raw label pointers, stable IDs,
tampered wire diagnostics, legacy revision rejection and real pinned CLI export.

Main commands (existing `.venv`, runner processes use `PYTHONUTF8=1`,
`PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=<repo>/backend`):

```powershell
python -B -m pytest tests/evals/g3/test_budget_diagnostics.py -q -p no:cacheprovider -k reviewed --tb=short
python -B -m pytest tests/evals/g3/test_budget_diagnostics.py tests/evals/g3/test_budget.py -q -p no:cacheprovider --tb=short
python -B -m pytest tests/evals/g3 -q -p no:cacheprovider
python -B -m pytest --collect-only -q -p no:cacheprovider -p evals.intelligence_g3.junit_inventory --g3-inventory .tmp/evals/g3/pr4-diagnostics-fix-20261028-001/node_inventory.json
python -B -u -m pytest -q -p no:cacheprovider -p evals.intelligence_g3.junit_inventory --junitxml=.tmp/evals/g3/pr4-diagnostics-fix-20261028-001/full.xml --basetemp=.tmp/evals/g3/pr4-diagnostics-fix-20261028-001/full-temp -o faulthandler_timeout=120
python -B -m evals.intelligence_g3.junit_inventory --inventory .tmp/evals/g3/pr4-diagnostics-fix-20261028-001/node_inventory.json --junit .tmp/evals/g3/pr4-diagnostics-fix-20261028-001/full.xml
python -B -m ruff check backend tests evals
python -B -m evals.intelligence_g3.budget_cli --check-schemas
python -B evals/run_baseline.py
# In frontend, fresh ignored output:
npm --offline run build -- --outDir ../.tmp/evals/g3/pr4-diagnostics-fix-20261028-001/frontend-dist
```

Normal Windows execution and the existing project-local full-suite basetemp are
used because prior probes demonstrated sandbox loopback/OS-temp limitations.
No sockets, product path policies, tests or skip rules were weakened.

## Scope and stopping point

Seven existing files are edited: budget code/contracts/CLI, current config
registry, the additive inventory checker, and two READMEs. Added files are the
new schema family, preserved v1 registry, one test module, its required-test
manifest and this repair record. No original tests, v1 schemas, prior delivery/
review reports, ranker/revisit definitions, G1/G2 files, backend/frontend source,
CI command, dependencies, archive data, `.gitignore` or diaries are changed.
Final source/hash/diff verification passed after full regression; original v1
schemas, old test sources and pins, and all unrelated initial files retain their
exact bytes. The v1 registry archive matches the original registry bytes.

This is synthetic, nonblind engineering evidence. Reading-time calibration,
semantic domain coverage, event/source independence, real-user utility and
ranking gains remain unevaluated. Conservative coverage overlaps do not infer
supersession between observations. The supplied source universe still comes
only from native pointers/windows; an empty universe remains unknown.

The two P2 findings are repaired locally and require independent re-review.
This record does not grant PR5 approval. Stop after this repair; no commit,
push, publication or PR5 implementation is part of this task.
