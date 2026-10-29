# G3-PR3: append-only interactions, identity migration and revisit rules

Date: 2026-10-27, Asia/Shanghai. Base HEAD:
`fb42de414e56da7a0eb58e89d174d38a1495f02a` (`feat: add G3 offline contracts and explainable event ranking`),
branch `main`; initial worktree was clean.

## Entry gate

Read the actual completed independent reviews in chat “严格审查 G3”
(`01a1795f-0662-7831-bfa3-7f7e765e50b0`), rather than treating repair reports
or old memory as current approval:

* PR1 review turn `01a17c40-604d-7161-8828-3b3d6d8fbe96`: PASS, no remaining
  actionable P0/P1/P2/P3; PR2 technically allowed, owner approval required.
* Latest PR2 review turn `01a17d55-7307-7d21-86e9-5355d717e7e8`: PASS, prior
  budget-test P3 closed; PR3 technically allowed, owner approval required.
* The owner's explicit current instruction to start PR3 supplies that approval.

Read AGENTS, V1, G3 plan, G2/G3 handoff, native G2 identity/evidence/snapshot
types, PR1 replay validation and PR2 rankers/tests before implementation.

## Delivered behavior

* `history_contracts.py`, `history.py`: strict synthetic `HistoryEvent`, hashed
  `HistoryJournal`, explicit `HistoryMapping`, `HistoryInput`, registered policy,
  as-of selectors, visible native reference binding and append-only reduction.
* `history_store.py`: canonical JSONL compare-and-append with exclusive sidecar
  lock, trusted expected head, fsync and exact-byte externally pinned loading.
  No overwrite, truncate or delete API. Storage is restricted to ignored offline
  G3 output areas, and cannot write a production database.
* `revisit.py`: new `g3-{algorithm}-revisit-v1` adapter, sharing PR2 lexical/time
  scoring and evidence gates. Baseline B0/B1/B2/B3 scores/order remain unchanged;
  B4/P1 consume the new explicit history policy. Same pool/context/config/budget
  binding remains mandatory; every candidate is retained.
* `revisit_cli.py`: pinned saved-input export for one algorithm into a new
  directory. This is not a budget planner, metric experiment or acceptance matrix.
* `schema/v3/`, `manifests/pr3_history_config.json`: seven additive schemas and
  fixed versioned penalties/protection. PR1/PR2 schemas/configs stay unchanged.
* `fixtures/pr3/v1/scenarios.json`, three new test sources: 105 tests and authored
  1/3/7-day inputs. Test expectations are not read by prediction.
* `junit_inventory.py`, `manifests/pr3_required_tests.json`: additive PR3 inventory;
  all original PR1/PR2/frozen G2 nodes, pins and skip exemptions are retained.
  Root and G3 README describe current implementation and limits.

Included, rendered, opened, acknowledged and dismissed are distinct facts.
Only explicit acknowledgment, known feedback or visible declared Persona
statement knowledge can mark the current cited statements known. Rendering,
opening, dismissal and helpful/irrelevant feedback cannot do so. Feedback
retraction and replacement create new records, retaining the old bytes.
An unretracted explicit not-known record vetoes conflicting known/acknowledged
signals regardless of occurrence or arrival order; explicitly retract it to resolve
the conflict. A delayed old known record cannot silently undo newer uncertainty.

Strict input/ranking validation rejects future interactions, mappings, delivery
and Persona records. Source selection projects only the visible journal prefix
by occurrence and availability; late-arriving feedback is unavailable before
its recorded availability. Explicit and serialized paths both enforce bindings.
Future poison does not change the selected input or predictions.

Revision changes alone do not reset event knowledge. Cross-key migration and
same-key surviving merges require exact explicit snapshot-to-snapshot mappings
with ordered native G2 transition paths. A split child's immediate lineage may
omit its merge ancestor; the mapper traverses the full native transition graph.
Uncertain/missing mappings never silently transfer whole-event knowledge or
repeat penalties. Parent acknowledgment covers its own cited statement set only.

Identical latest delivered statement sets may receive a capped repeat penalty.
Repeated log messages/reprint documents do not multiply the same signal. Pending
supported corrections/withdrawals/constraint increments clear the penalty and
receive structural priority in B4/P1, after G2 hard evidence gates. Merely
including, rendering or opening the update does not retire protection. Current
explicit knowledge is required. Outputs retain feature/component pointers,
resolved snapshots, migration statuses, delivery counts and decision reasons.

## Actual checks

Evidence directory:
`D:\agent_project\cfaw-news\.tmp\evals\g3\pr3-20261027-001`.
Recorded `*.command.json` files contain real argv/cwd/environment, timestamps,
exit code, elapsed time and raw-log SHA256. No recorded outcome is synthesized.
The local capture helper is not a predictor or acceptance framework.

Commands use the existing `.venv`, `-B`, per-process `PYTHONUTF8=1`,
`PYTHONDONTWRITEBYTECODE=1`, and `PYTHONPATH=<repo>/backend`. No installation,
network, model or production integration was required.

| Check | Actual outcome | Record |
| --- | --- | --- |
| Initial completed focused PR3 tests | Exit 0: 103 passed, 38.23 seconds; before the two added conflict cases | `focused-fifth.command.json` |
| Conflict feedback red/green | Before fix exit 1: 1 failed / 1 passed; after fix exit 0: 2 passed | `conflict-red.command.json`, `conflict-green.command.json` |
| Initial completed G3 suite | Exit 0: 340 passed, 159.60 seconds; before conflict hardening | `g3.command.json` |
| Final complete G3 suite | Exit 0: 342 passed, including all 105 PR3 tests, 158.61 seconds | `g3-final.command.json` |
| Ruff: `python -B -m ruff check --no-cache backend tests evals` | Exit 0 after conflict hardening | `ruff-final.command.json` |
| Complete pytest collection | Exit 0: 1466 nodes = 1124 frozen + 183 PR1 + 54 PR2 + 105 PR3 | `collect-final.command.json` |
| Exact collection/source inventory | Exit 0 | `inventory-final.command.json` |
| G1/G2/PR1/PR2/PR3 schemas and registered policy bytes | Exit 0; prior schemas unchanged | `schemas-final.command.json` |
| G1 strict manifest validation | Exit 0, `ok=true`; native future-source and pending-research diagnostics retained | `strict-g1.command.json` |
| `python -B evals/run_baseline.py --output <fresh-output>` | Exit 0: recall 1.0, MRR 0.833333, nDCG 0.864572; seed lexical sanity only | `baseline.command.json` |
| Existing-dependency offline frontend build | Child exit 0; TypeScript and Vite passed | `frontend-final.command.json` |
| 15 synthetic revisit exports and four merge/split exports | Exit 0; complete source/feature/reason outputs | `examples-final.command.json`, `examples/` |
| Final full project regression | Exit 0: 1465 passed / 1 skipped / 1 existing warning, 931.79 seconds | `full-final.command.json` |
| Full JUnit inventory verification | Exit 0: exact 1466 nodes; every frozen gate/requirement present, one original exempt skip | `junit-final.command.json` |
| Initial byte/scope/whitespace audit | Exit 0: only the two README files and G3 inventory checker changed among 783 original files | `boundary-with-report.command.json`, `whitespace.command.json` |
| Actual pinned CLI export | Exit 0: 7-day withdrawal input copied exactly; protected ranking exported | `cli.command.json` |
| Final-code saved-artifact verification | Exit 0: 19 saved examples and CLI output reproduced byte-for-byte; 543 code/test/config/schema hashes unchanged | `final-artifacts.command.json` |

Core reproduction commands from the repository root:

```powershell
python -B -m pytest tests/evals/g3 -q -p no:cacheprovider --basetemp=.tmp/evals/g3/pr3-20261027-001/g3-final-temp
python -B -m pytest --collect-only -q -p no:cacheprovider -p evals.intelligence_g3.junit_inventory --g3-inventory .tmp/evals/g3/pr3-20261027-001/node_inventory_final.json
python -B -u -m pytest -q -p no:cacheprovider -p evals.intelligence_g3.junit_inventory --junitxml=.tmp/evals/g3/pr3-20261027-001/full-final.xml --basetemp=.tmp/evals/g3/pr3-20261027-001/full-final-temp -o faulthandler_timeout=120
python -B -m evals.intelligence_g3.junit_inventory --inventory .tmp/evals/g3/pr3-20261027-001/node_inventory_final.json --junit .tmp/evals/g3/pr3-20261027-001/full-final.xml
python -B -m evals.intelligence_g3.revisit_cli --check-schemas
# cwd frontend, existing dependencies only:
npm.cmd --offline run build -- --outDir D:\agent_project\cfaw-news\.tmp\evals\g3\pr3-20261027-001\frontend-dist
```

The sandbox asyncio probe timed out after eight seconds. The full run uses normal
Windows local loopback, the same original tests/event-loop implementation and
UTF-8 environment; no audit roots, socket implementation or skip policy was weakened.

The single skip is the unchanged Windows exemption
`tests/evals/test_provenance_and_rights.py::test_symlink_outside_bundle_rejected_if_supported`,
reason `symlink creation unavailable: 1314`. No G3 test is skipped. The warning
is the existing Starlette/httpx deprecation. JUnit gate/requirement completeness
is a regression check, not a fresh G2 acceptance decision.

Exploratory iterations are not counted as passes: first focused run had 75 failed /
24 passed, second 18 failed / 81 passed, third 4 failed / 95 passed, and the recorded
fourth had 2 failed / 101 passed. Fixes addressed strict JSON serialization and
diagnostic-code preservation, full native merge-to-split ancestry, incomplete
synthetic scope/grammar, and two invalid test setups (a supposed high-score
ordinary row was already acknowledged; an identical-content new document version
is correctly rejected by G1/G2). No frozen G1/G2 code or evidence gate was changed.

Two local helper commands initially failed imports because their script directory
was outside the repository module path; the helpers were corrected and rerun.
The first frontend wrapper invocation did not start its child due argument layout.
The corrected invocation saved the successful child build/exit/log, then its own
GBK console print failed on Vite's checkmark (outer exit 1). The raw build log
and recorded child exit 0 establish the build result; the helper's later stdout
was set to UTF-8. No source fix or repeated build was needed for that print issue.

The initial full run was deliberately stopped after a self-audit identified
arrival-order-sensitive conflicting knowledge feedback. Its partial log is
retained in `full.log`; `full.command.json` records child exit 4294967295
(outer command exit 1), not a regression PASS. The two new adversarial cases
reproduced the defect before the three-line conservative fix. The final source,
test-source hashes and complete inventory were refreshed before `full-final`.
No frozen requirements, tests, audit roots or skip policies were weakened.

Final scope: 22 PR3 files (three original files changed, nineteen added). The
other 780 original files remain byte-identical, including frozen G1/G2,
original PR1/PR2 contracts/rankers/configs/tests/schemas/inventories, CI,
backend, frontend, dependency files, archive data and `.gitignore`.
Final hashes, added paths and tracked diff are retained in `audit.json` and
`PR3-tracked.diff`; per-added-file whitespace checks are part of the boundary
audit. No Git index/history or diary contents were changed.

## Limits and stop

These are synthetic, nonblind AI-development engineering checks. Statement-set
delta and native explicit correction/withdrawal markers do not establish semantic
truth, research-grade materiality, independent human review or real-user benefit.
Coverage diagnostics never prove no world update. No claim that P1 outperforms B4,
fresh G2 stage acceptance, complete G3 acceptance or remote CI/deployment is made.

Hash chains require an external trusted digest/head to detect rewritten history
or rollback. The offline writer does not claim database transaction guarantees,
production persistence or automatic crash recovery. No implicit Persona learning.

No commit, staging, push, diary upload, production DB change, dependency change,
PR4 budget planner or PR5 final matrix. PR3 remains subject to independent review.
Use `docs/G3_CODEX_PROMPTS.md`, “PR3 独立审查提示词（只审查，不改代码）”.
Stop after PR3; independent review and owner approval are required before PR4.

## Independent review corrections, 2026-10-28

The independent review found a P1 conflicting-feedback protection defect, a P2
current-history erasure defect under uncertain ancestry, and a P2 default pytest
path-fixture defect. The earlier special-`--basetemp` regression did not establish
default pytest/CI compatibility, and the earlier conflict tests did not exercise
the already-delivered current correction/withdrawal snapshot. The historical
results above remain records of those narrower checks, not independent approval.
See `PR3_REVIEW_FIXES.md` for the repairs, expanded cases and fresh default-entry
regression. PR4 remains unstarted.
