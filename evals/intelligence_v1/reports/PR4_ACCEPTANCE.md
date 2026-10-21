# G1-PR4 implementation and acceptance

> Historical v1 acceptance below. The independently reported comparison P1, current
> v2 pin and repair verification are recorded in [PR4_REPORT_REVIEW_FIX.md](PR4_REPORT_REVIEW_FIX.md).

Date: 2026-10-21 (Asia/Shanghai). **PR4 technical DoD PASS on frozen inputs.**
This is synthetic offline technical evaluation, not G1-a or real-user/model validation.

## Baseline and immutable inputs

- Starting HEAD: `9cd5522cb6212d11e905bef4c2a38435b823b5ac`, main, clean worktree.
- Dataset `pr4-revisit-v1`, schema `g1-pr4-1`, config `pr4-baselines-v1`.
- **Externally recorded Manifest SHA-256: `16b1e4ac765bed22abba9496d018220c03ddc08ae1547e64840cc22733dd41f4`.**
- 93 controlled inputs; all test-source fingerprints and the complete frozen package
  are under ignored `.local/evals/g1/pr4/`. Original PR3 v2 was preserved first.
- Existing 22 JSONL files, including all gold/annotations/adjudications, are unchanged.
  New synthetic expectations match the first evaluation-red input byte-for-byte.
- No backend/frontend source, business database, archive/migration asset, dependency
  installation or lockfile change. No collection/live model, migration or Git publication.
  T25=N/A. Development diaries remain ignored and unstaged.

## PR3 independent review gate

The approved plan required independent rereview before implementation. It was found
in the separate chat **审查 G1**, thread `01a15878-eb6c-7290-a415-77f2e04c6519`,
turn `01a15cf5-8cf4-7482-9181-2cf6f7ea12d3`. The reviewer concluded no P0/P1,
confirmed the former split P1 fixed on pr3-replay-v2, and reported one P2 stale-pin
documentation issue. The reviewed pin and 71-input/26-test fingerprints matched
the starting package. A local evidence copy is `gate-review.json`.
The remaining P2 pin instructions now point to this current report; the old review
and acceptance records have not been rewritten as new verification.
PR4 itself still requires subsequent independent review; implementation self-tests
do not substitute for that review or human annotation.

## Implemented behavior

- B3: maximum-normalized representative BM25 plus UTC recency at .75/.25.
  Main half-life 7 days; 3/14-day sensitivity is restricted to dev steps.
  Time is latest visible version availability, not a gold meaningful-change time.
- B4: recent matching delivery by document identity, typed historical version/hash
  snapshots, exact time/scope/identity checks and explicit signal logs. Same-text
  included/rendered/ack penalties are .10/.10/.25 once each. Opened/dismissed add no
  weight. New hashes clear penalties; unknown hashes do not establish no-change.
  Scores can be negative. No exposure changes knowledge_known.
- All six entry points share candidates/common history. Complete ranking is kept;
  presentation is a separate prefix, first 3 focus at 90s then 12 radar at 12s.
  No skipping/demotion/gold deduplication; budgets 180/420/900. Existing B0/B1
  article duplicates incur their real card cost.
- Default human-gold mode remains null for absent/pending labels. Explicit
  synthetic-fixture mode reads a distinct expectation record, with no fabricated
  agreed/adjudicated human submissions. Macro/micro and family summaries keep the
  modes and oracle separate; repeated identical runs are not extra samples.
- Event recall/nDCG, budget misses, duplicate/repeat rates, pair metrics, 1/3/7d
  revisit coverage, gaps and proxy change measurements retain denominators/null
  reasons. Formal semantic change/correction/withdrawal predictions are not emitted.
  Their metrics stay unmeasured. Claim/support/independence metrics with no applicable
  outputs are null, not 100%. Timing is separate from deterministic metrics.
- REVISIT-7D adds 7 synthetic versions, 6 steps and 8 fixed authored expectations.
  It preserves DEV-01's D5 correction and uses a separate D6 correction.
  Counterfactuals use independent frozen bundle copies in the same family/dev split.

## Test-first evidence

| Check | Actual result |
|---|---|
| Initial B3/B4/budget/metric tests | 22 failed before implementation; 22 passed afterward |
| Evaluation/report tests | 3 failed before interfaces; related PR3/PR4 evaluation 6 passed |
| History and counterfactual cases | 17 passed |
| First broad G1 regression, before final parameter guards | 257 passed, 1 skipped; draft evidence only |
| Parameter/split guard red | 3 failed, 2 passed; expected failure and warning retained |
| Related history/ranking/evaluation/guard checks | 32 passed |
| Report metadata pin red | 1 failed; expected failure retained |
| Final report/parameter guard related checks | 8 passed |
| Frozen full regression | **387 passed / 1 skipped / 1 warning; 388 collected, 0 failures/errors** |
| Ruff/schema/strict Manifest/pip/seed/frontend build | PASS on frozen inputs |
| Frozen six-algorithm reproduction matrix | **40 prediction runs + 80 independent evaluations, 121 successful CLI commands including report; repeated deterministic bytes equal** |
| Frozen counterfactual reports | **8 variants spanning all five required families plus future feedback; inputs/outputs and reports preserved** |
| PR3 ranking preservation | 36 old algorithm/step combinations keep candidate hashes and original ranking/score/component fields |

Final full JUnit SHA-256:
`7c7525ce6db840e4233e8bb081e62ca0c243d39fb99c0479f710009cb1084a5b`.
It contains 263 G1 cases (262 pass, 1 skip) and all 125 legacy cases passing.
The warning is the pre-existing Starlette/httpx deprecation; no dependency was installed.

The first restricted full run was interrupted at Windows
`socket._fallback_socketpair -> asyncio -> TestClient`, in the unchanged
`test_default_start_and_restart_have_no_example_goals`. The 30-second traceback
identified initialization hanging; it was stopped with Ctrl+C, not counted as a
pass or an assertion failure. The unchanged frozen suite then completed in the
environment permitting local test sockets. Both commands and the interruption
record are retained; no assertion or business source was changed for the rerun.

The native-symlink permission skip remains separate from the passing resolved-path
escape check. Any existing Starlette/httpx warning is reported separately.
Failed red evidence is retained under its original filename; it is not overwritten.

## Exact verification commands

Run from `D:/agent_project/cfaw-news`, existing venv, new output directories:

```powershell
$PY = '.\.venv\Scripts\python.exe'
$ROOT = 'evals/intelligence_v1'
$PIN = '16b1e4ac765bed22abba9496d018220c03ddc08ae1547e64840cc22733dd41f4'
& $PY -B -m ruff check backend tests evals
& $PY -B -m evals.intelligence_v1.contracts --check-schemas
& $PY -B -m evals.intelligence_v1.validate --manifest "$ROOT/manifests/dataset_manifest.json" --strict
& $PY -B -m pip check
& $PY -B evals/run_baseline.py --output .local/evals/g1/pr4/seed-sanity.json
& $PY -B -m pytest tests/evals -q --basetemp=.tmp/g1-pr4-evals-01 -o faulthandler_timeout=30 --junitxml=.local/evals/g1/pr4/pytest-evals-01.xml
# Historical environment interruption, not a passed result:
& $PY -B -m pytest -q --basetemp=.tmp/g1-pr4-frozen-full -o faulthandler_timeout=30 --junitxml=.local/evals/g1/pr4/pytest-frozen-full.xml
# Current completed frozen regression, local test socket initialization permitted:
& $PY -B -m pytest -q --basetemp=.tmp/g1-pr4-frozen-full-local-sockets -o faulthandler_timeout=30 --junitxml=.local/evals/g1/pr4/pytest-frozen-full-local-sockets.xml
git diff --check
# frontend working directory:
npm.cmd --offline run build
```

The G1-only command above is the recorded earlier draft run; the final full run
must verify every current G1 and legacy case. Never use the draft count as frozen proof.
Seed is the original seed-sanity smoke check, not event-level algorithm evidence.
It reports Recall@8=1, MRR@8=.8333333333333334, nDCG@8=.8645724197652078.

## Reproduction protocol (checked-in CLI only)

For b0/b1/b2-predicted/b2-oracle/b3/b4, budgets 180/420/900, half-life 7:
run each combination twice under PYTHONHASHSEED=1 and 719, with new directories.
Additionally run b3 half-life 3/14 at 420s twice on dev. For every prediction run,
evaluate both gold and synthetic-fixture in separate new output directories.

```powershell
$env:PYTHONHASHSEED = '1' # second repetition: '719'
& $PY -B -m evals.intelligence_v1.replay --manifest "$ROOT/manifests/dataset_manifest.json" --manifest-sha256 $PIN --split dev --algo $ALGO --config "$ROOT/manifests/baseline_config.json" --budget-seconds $BUDGET --half-life-days $HALF --out $RUN
& $PY -B -m evals.intelligence_v1.evaluate --manifest "$ROOT/manifests/dataset_manifest.json" --manifest-sha256 $PIN --run $RUN --label-source gold --out $GOLD_EVALUATION
& $PY -B -m evals.intelligence_v1.evaluate --manifest "$ROOT/manifests/dataset_manifest.json" --manifest-sha256 $PIN --run $RUN --label-source synthetic-fixture --out $FIXTURE_EVALUATION
& $PY -B -m evals.intelligence_v1.report --manifest "$ROOT/manifests/dataset_manifest.json" --manifest-sha256 $PIN --runs $RUN_ROOT --out $SUMMARY
```

Compare predictions.jsonl/input_snapshot.json/baseline_config.json and each label
mode's metrics.json/diagnostics.jsonl byte-for-byte. Timing stays in metadata.
Candidate/history snapshots must be equal across algorithms. Keep oracle in oracle
paths. Output paths must be new; invalid pins/inputs/metadata must fail before output.
Full expanded commands, exit codes and hashes are saved locally in reproduction records.

Completed matrix: 20 experiment configurations, 2 repetitions each, hash seeds 1/719.
For each repetition both label sources were evaluated separately. All six algorithms
share byte-identical candidate/history snapshots within each standard budget.
The main report, complete metric denominators and family summaries are at:
`.local/evals/g1/pr4/frozen-matrix-01-summary/report.md` and `comparison.json`.
Measured timing is in performance.json; per-step normalized latency excludes process
startup/shared initial bundle loading, while total execution_ms is separately recorded.
The 280 deterministic artifact hashes are in `reproduction-hashes.json`.
Rerun commands use fresh output paths; existing acceptance evidence is never overwritten.

Five counterfactual families were exercised through 8 frozen variants:
remove_correction, academic_persona, future_independent, rendered/opened/acknowledged,
source_failure, plus future_feedback. Their individual reports and byte-preserved
test inputs/outputs are under `.local/evals/g1/pr4/counterfactuals/`.
Archives retain original metadata paths. Fresh reruns use the archived pinned bundle
and new output paths, not rewritten old metadata. Counterfactual reference changes
implement their pre-authored logical scenarios; no original human/gold file changes.

## Measured synthetic outcome and misses

**B3/B4 show zero improvement over B1 in macro ImportantEventRecall@budget at all
three standard budgets.** No weights, thresholds or references were changed to hide it.
The following is REVISIT-7D D8 only; evidence presence means membership of a
presented card's evidence list, not a real render, reading or comprehension event.

| Budget | Algorithm | Cards | Event recall | Duplicate reference cards | D4 test / D6 correction / Y evidence |
|---|---|---:|---:|---:|---|
| 180 | B0 | 2 | 2/2 | 0/2 | no / yes / yes |
| 180 | B1, B2-predicted, B3, B4 | 2 | 2/2 | 0/2 | yes / **no** / yes |
| 180 | B2-oracle | 2 | 2/2 | 0/2 | yes / yes / yes |
| 420/900 | B0, B1 | 6 | 2/2 | 4/6 | yes / yes / yes |
| 420/900 | B2-predicted, B3, B4 | 3 | 2/2 | 1/3 | yes / yes / yes |
| 420/900 | B2-oracle | 2 | 2/2 | 0/2 | yes / yes / yes |

Important failure: event recall alone hides the missing D6 correction at 180s.
The separate supporting-evidence diagnostics reveal it. Conservative grouping
keeps the independent test separate from the release/correction group, so predicted
methods still show one duplicate reference X at the larger budgets. Oracle does
not replace this measured prediction limitation. B4 penalties change scores for
same-text history, but this small fixed-history story gives no incremental ranking
benefit over B3. At 420/900 this fixture exhausts its finite candidates; the common
card caps also remain in force. These are technical observations on authored data.

## Remaining research limits and stop status

Only contract fixtures and two invented stories exist, not five complete development
trajectories or real-world evidence. The G1 plan allows disclosed synthetic data;
this report does not introduce a real-data-only gate. Reposts/title edits can refresh B3's time proxy; hash
changes can release B4 penalties without a semantic update. Conservative grouping
can miss independent evidence merges and leave duplicate reference events.
The fixed caps can make 420s/900s identical; no effort will be made to manufacture
improvement by changing references, thresholds or weights.

Human labels, independent semantic support, real-source permissions/generalization,
PR5/G1-a and PR4 independent review remain pending. No training, new UI/Agent framework,
online collection, database migration, commit or push is included.
## DoD and final scope check

| Gate | Status |
|---|---|
| Prior independent PR3 rereview matches starting pin | PASS; no remaining P0/P1 from that review |
| B0–B4 plus separate oracle, shared candidates/history | PASS |
| T10–T15/T18/T24, METRIC01/02/BUDGET01, prior temporal/split/isolation guards | PASS in the frozen full suite |
| All five counterfactual families and D8 misses explained | PASS, 8 variants and reports archived |
| Predicted snapshots, future feedback, references and budgets isolated | PASS; full-suite negative and process-audit tests |
| Two-seed canonical reproduction, independent evaluation, no prediction rewrite | PASS |
| Old data/business contracts, legacy ranking core and regression | PASS; old 22 JSONL and all 125 old tests retained |
| Source/test fingerprints after validation and reproduction | PASS; 93 inputs and 34 test-source files match freeze |
| Semantic classification/support, human labels, five complete development trajectories, G1-a | PENDING, outside this technical completion |
| Production database migration | N/A; no access or migration |

Completion is limited to this PR. HEAD remains the starting commit; index is empty,
development diaries remain ignored, and no commit/push or PR5 work was performed.
No remaining failed test is hidden; red tests and the environment interruption are
explicit historical evidence. Subsequent independent PR4 review is still required.
