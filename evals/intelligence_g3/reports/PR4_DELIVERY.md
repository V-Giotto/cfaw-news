# G3-PR4: independent reading budgets, Focus/Radar plans and coverage diagnostics

Date: 2026-10-28, Asia/Shanghai. Base HEAD:
`fb42de414e56da7a0eb58e89d174d38a1495f02a`, branch `main`.

## Entry gate and working-tree boundary

Read the latest completed independent review in chat “严格审查 G3”
(`01a1795f-0662-7831-bfa3-7f7e765e50b0`), review turn
`01a180f5-7775-7640-9c94-735cdc3ea9f4`. It concluded **PASS WITH CONDITIONS**,
with no remaining PR3 code findings and engineering permission to enter PR4.
The condition is to retain the project-local pytest basetemp for unchanged G2
tests; default OS-temp G2 manifest failures are not reclassified as passes.
The owner's explicit instruction to begin PR4 supplies owner approval.

The worktree already contained uncommitted PR3 code/tests/schema/fixtures/reports,
two README edits, its inventory addition and a CI basetemp change. An initial
exact-byte inventory of 803 public files and the original diff/status were saved
before editing. PR4 preserves those PR3 files. Its changes to pre-existing files
are limited to the two READMEs and an additive PR4 inventory registration.
In particular PR4 does not change the existing CI command, ranker, revisit policy,
G1/G2 files, dependency locks, frontend/backend source, archive data or `.gitignore`.

## Delivered behavior

* `budget_contracts.py`: versioned `ReadingRule`, `BudgetConfig`, `BudgetInput`
  and `BriefingPlan`; additive schemas under `schema/v4/`. Direct wire validation
  binds the complete source input and ranking and rederives final plan decisions.
* `budget.py`: pure stage-two planner, with no ranker invocation or numerical
  score change. Every stage-one ranking row and current candidate remains in
  `BriefingPlan.input`; `archive_snapshot_ids` retains the complete current pool.
* Registered 180/420/900-second budgets and experimental 60/40, 70/30 and 80/20
  Focus/Radar time shares. The default 70/30 policy is a development experiment,
  not an accepted product default or tuned optimum.
* Versioned Unicode display-unit reading estimate, fixed category table, item
  overhead and distinct citation checking cost. It does not use G2's coarse
  90/12 seconds or a fixed item-count cap, and is not calibrated cognitive time.
* Eligible pending corrections, withdrawals and material changes receive first
  access to the total budget, preserving rank order within that group. They can
  borrow Radar seconds, but cannot bypass G2 evidence/hold gates or exceed the
  total budget. Infeasible protected content is explicitly reported as unmet.
* Ordinary ranked first-fit Focus then Radar allocation; no ordinary share
  borrowing. Failed share attempts remain explicit, including when combined
  idle time would have fit an item. No optimality or full-utilization claim.
* Focus/Radar/minimum projections reference unchanged native blocks. Truncation
  removes whole optional inference/redundant explanation blocks only; selected
  statements, attribution, scope, limitations, risks and uncertainties remain.
  Required content that cannot fit is unshown, never cropped or deleted.
* Every candidate has an explicit focus/radar/truncated/not_displayed/
  constraint_excluded status, tier, three estimates and structured decision reasons.
  Separate display order does not overwrite original rank order or record user actions.
* Independent native source-coverage diagnostics preserve every window/status/time/
  reason. Missing windows are unknown, without fabricated observations or a
  claim of confirmed no updates. Window counts and source counts are separate.
* Budget utilization, per-tier usage/borrowing, lexical explicit-interest coverage,
  native event-key breadth and truncation/unshown/excluded/unmet diagnostics have
  fixed count denominators and null for undefined ratios. Event breadth does not
  establish source independence or independent research samples.
* `budget_cli.py`: a single externally pinned `BudgetInput` export to a fresh
  allowed G3 output directory. Preserves original input bytes; no online API,
  React, DB, quality evaluator or PR5 acceptance matrix.

Full estimator, allocation, projection and denominator definitions are in the
[package README](../README.md). New failures include `G3_PLAN_INPUT_MISMATCH`
and `G3_PLAN_INVALID`, alongside unchanged native time/path/pin failures.

## Actual verification

Local evidence: `D:\agent_project\cfaw-news\.tmp\evals\g3\pr4-20261028-001`.
The final checks' `*.command.json` record actual argv, cwd, process-only environment,
timestamps, exit code, elapsed time and SHA256 of raw logs. Dependencies were
already installed; no dependency installation, model/provider or network call
was introduced. The frontend is only an offline compatibility build.

| Check | Result | Evidence |
| --- | --- | --- |
| New PR4 tests, final full focused run | Exit 0: 72 passed | `budget.command.json`, `budget.log` |
| Complete G3 tests, normal host default entry | Exit 0: 448 passed (376 prior + 72 PR4), no basetemp override | `g3.command.json`, `g3.log` |
| Full project, required project-local basetemp | Exit 0: 1571 passed, 1 existing skip, 1 existing warning; 955.94 seconds | `full.command.json`, `full.log`, `full.xml` |
| Exact collection and inventory | Exit 0: 1572 nodes = prior 1500 + new 72 | `collect.command.json`, `inventory.command.json`, `node_inventory.json` |
| Full JUnit verification | Exit 0: exact 1572 nodes, no missing/failed/newly skipped tests | `junit.command.json`, `junit.log` |
| Ruff (`backend tests evals`) | Exit 0 | `ruff.command.json` |
| PR4 schemas | Exit 0 | `schemas.command.json` |
| Seed baseline sanity | Exit 0: recall 1.0, MRR 0.833333, nDCG 0.864572 | `baseline.command.json`; fixed seed sanity only |
| Offline frontend build, fresh ignored output | Exit 0: TypeScript/Vite passed | `frontend.command.json`, `frontend.log` |
| Two real pinned planning CLI invocations | Both exit 0; exact 180-second protected truncated plan and 164-second correction/withdrawal plan | `smoke.command.json` and saved inputs/plans |
| Initial changed-file and frozen-source audit | Exit 0: three pre-existing files changed, 800 initial files unchanged, no deletions; 554 verification source bytes stable | `boundary-initial.json`, `verification-source-hashes.json` |
| Final scope/source/diff audit | Exit 0: three existing files changed, 12 new PR4 files, 800 initial files unchanged, zero deletions; all 554 verification sources unchanged | `boundary-final.json`, `verification-source-hashes.json` |

The exact-180 CLI case uses all 180 seconds, borrowing 54 Radar seconds, with no
unmet protected event. The B0 correction/withdrawal case uses 164 seconds, borrows
38 seconds, keeps the naturally newer ordinary candidate first in the original
ranking, and shows both protected updates first in the independent display plan.
Both retain the exact complete original ranking. These are synthetic native G2
prediction cases, not live source or model results.

The sole skipped node is the existing
`tests/evals/test_provenance_and_rights.py::test_symlink_outside_bundle_rejected_if_supported`,
with the permitted reason `symlink creation unavailable: 1314`. No G3 test was
skipped. The existing FastAPI/Starlette HTTPX deprecation is the sole warning;
no dependency change was made. Full collection, JUnit requirements and source
hash verification passed. This is the required project-basetemp full regression,
not a claim that unchanged G2 tests pass with default OS-temp manifests.

Tests cover empty pools, single overlong **eligible** native candidates, Focus
share boundaries at 125/126/127 seconds, total protected boundaries at
179/180/181 seconds, tied scores, six existing algorithms, three time budgets,
three ratio profiles, correction/withdrawal/material protection, infeasible
protected sets, hold/evidence gates, all five coverage statuses, absent coverage,
domain/event denominators, safe block truncation, all unshown reasons, pointer
resolution, direct wire/public-input tampering, final-plan tampering, unregistered
policies/budgets, external pins, path restrictions and cross-process hash seeds.
No score edits or candidate deletion are used to make time-budget tests pass.

The first focused run had 13 failures in the new test constructions: its source
coverage envelope omitted the supplied native windows, and a manually constructed
ranking contained raw strings in datetime fields. Those test constructions were
corrected without weakening production validators. The next original 65 cases
passed; seven additional budget-boundary/registration cases brought the final
suite to 72. Original failure logs remain in `budget-first.log`.

The restricted sandbox's asyncio loopback probe timed out after eight seconds.
Complete regression therefore uses the original tests in the normal local
Windows loopback environment, with the required project-local basetemp and no
skip/socket/path-policy changes. The sandbox default-entry complete G3 run had
444 passed and four fixture setup errors because pytest could not initialize the
OS temporary directory (three inventory cases and one hash-seed case). This
failed run is retained as `g3-sandbox.command.json`/`g3-sandbox.log`; the same
default-entry command is separately rerun in the normal host environment.
A first frontend wrapper failed to print Vite's
Unicode checkmark after the actual build had exited 0; the wrapper output encoding
was corrected and the build reran successfully to a fresh output directory.
These helper/environment outcomes are separate from product test results.

Main commands, using the existing `.venv` and `PYTHONPATH=<repo>/backend`:

```powershell
python -B -m pytest tests/evals/g3/test_budget.py -q -p no:cacheprovider
python -B -m pytest tests/evals/g3 -q -p no:cacheprovider
python -B -m pytest --collect-only -q -p no:cacheprovider -p evals.intelligence_g3.junit_inventory --g3-inventory .tmp/evals/g3/pr4-20261028-001/node_inventory.json
python -B -m evals.intelligence_g3.junit_inventory --inventory .tmp/evals/g3/pr4-20261028-001/node_inventory.json
python -B -u -m pytest -q -p no:cacheprovider -p evals.intelligence_g3.junit_inventory --junitxml=.tmp/evals/g3/pr4-20261028-001/full.xml --basetemp=.tmp/evals/g3/pr4-20261028-001/full-temp -o faulthandler_timeout=120
python -B -m evals.intelligence_g3.junit_inventory --inventory .tmp/evals/g3/pr4-20261028-001/node_inventory.json --junit .tmp/evals/g3/pr4-20261028-001/full.xml
python -B -m ruff check backend tests evals
python -B -m evals.intelligence_g3.budget_cli --check-schemas
python -B evals/run_baseline.py
# In frontend; fresh ignored output, unchanged build script:
npm --offline run build -- --outDir ../.tmp/evals/g3/pr4-20261028-001/frontend-dist-final
```

The new separately pinned required-test manifest is
`manifests/pr4_required_tests.json`, SHA256
`3d269a4361dc67ce08db7d9ab1bb5f541a4f26971eb72cc0b88240ef25d61b8b`.
Original PR1/PR2/PR3/frozen G1/G2 test nodes, source pins and skip exemptions
are unchanged. This is additive compatibility evidence, not PR5 acceptance.

## Limits and stopping point

Reading estimates need real-user calibration; lexical domain matching is not
semantic coverage; G2 event keys are not independent research samples. Greedy
time-share allocation can leave idle time and cannot guarantee every protected
event fits. Structured reasons expose those limits. Numerical ranking quality
and original G2 semantic truth are not evaluated by this planner.

Evidence remains synthetic, nonblind engineering checks. No independent human
validation, real-world algorithm gain, user comprehension, production durability,
online integration, remote CI success or deployment is claimed. PR4 requires
independent review before any next-stage owner approval. Stop after PR4; do not
begin PR5. No commit, push or diary publication is part of this task.
