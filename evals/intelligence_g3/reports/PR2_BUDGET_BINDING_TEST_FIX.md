# PR2 P3 repair: isolate the budget fingerprint test

Date: 2026-10-27, Asia/Shanghai. Scope: the owner's reported nonblocking P3
test weakness only. The supplied independent review passed PR2 technically;
this repair does not authorize or begin PR3.

## Change

`test_all_algorithms_bind_exact_same_context_config_and_pool` now saves one
`value = delivered(pool())`, verifies its history/delivery are nonempty, and
copies that exact value for the changed-budget prediction. It changes only
`attention_budget_seconds` from 420 to 180. An explicit whole-model comparison
excluding that single field confirms that every other field, including history,
delivery, candidates, Persona and configuration binding, remains equal. The
comparison fingerprint must differ, with a dedicated assertion message.

`test_budget_binding_assertion_rejects_fingerprint_omitting_budget` temporarily
patches only the ranker's local digest function to omit that field from formal
replay inputs. It runs the same complete comparison test with both the original
and changed-budget predictions under that mutation, and requires the dedicated
budget assertion to fail. Native G2/PR1 integrity digests are unaffected, and the
test fixture restores the patch after the check. This verifies the test's ability
to catch an omitted budget rather than relying on a history difference.

The current ranker already binds the budget correctly; its source, policy,
schemas and algorithm versions are unchanged. The PR2 test manifest adds only
this mutation-test node and refreshes the changed test source hash; its checker
refreshes only `PR2_REQUIRED_PIN`. Original PR1/G2 inventories remain unchanged.
Current inventory: 54 PR2 nodes, 237 G3 nodes, 1361 complete project nodes.

## Fresh verification

Evidence directory:
`D:\agent_project\cfaw-news\.tmp\evals\g3\pr2-budget-test-fix-20261027-001`.
Each `*.command.json` contains the exact command/cwd/exit and raw log hash.
Python tests use the existing `.venv`, `-B`, `-p no:cacheprovider` and per-process
`PYTHONUTF8=1`, as documented for this Windows runtime.

| Command | Result / exit | Evidence |
| --- | --- | --- |
| `python -B -m pytest tests/evals/g3/test_rankers.py -q -p no:cacheprovider -k 'same_context_config_and_pool or budget_binding_assertion' --basetemp=.tmp/evals/g3/pr2-budget-test-fix-20261027-001/budget-tests-temp` | 2 passed / 52 deselected; exit 0, including required rejection of the budget-omitting mutant | `budget-tests.command.json` |
| `python -B -m pytest --collect-only -q -p no:cacheprovider -p evals.intelligence_g3.junit_inventory --g3-inventory .tmp/evals/g3/pr2-budget-test-fix-20261027-001/node_inventory.json` | 1361 collected; exit 0 | `collect.command.json` |
| `python -B -m evals.intelligence_g3.junit_inventory --inventory .tmp/evals/g3/pr2-budget-test-fix-20261027-001/node_inventory.json` | Exact current/frozen node and source union; exit 0 | `inventory.command.json` |
| `python -B -m ruff check --no-cache backend tests evals` | Passed; exit 0 | `ruff.command.json` |
| `python -B evals/run_baseline.py --output .tmp/evals/g3/pr2-budget-test-fix-20261027-001/baseline.json` | Seed lexical sanity passed; exit 0, not algorithm-quality evidence | `baseline.command.json` |
| `python -B -m pytest tests/evals/g3 -q -p no:cacheprovider -p evals.intelligence_g3.junit_inventory --junitxml=.tmp/evals/g3/pr2-budget-test-fix-20261027-001/g3.xml --basetemp=.tmp/evals/g3/pr2-budget-test-fix-20261027-001/g3-temp` | 237 passed, no skip; exit 0 | `g3.command.json`, `g3.xml` |
| Exact G3 JUnit subset, source/diff/hash boundary audit | Exit 0: all 237 current G3 nodes, no failures/errors/skips; only the intended three original files and one added report | `audit.command.json`, `audit.json`, `repair.diff` |

This is a test-only assertion repair plus mandatory test inventory pins. The
complete project execution and frontend build were not rerun in this repair;
the prior full-run/build records in `PR2_DELIVERY.md` remain historical, not fresh
results for this test revision. There is no new algorithm, dependency, frontend,
production integration, external request or model call.

The final local diff/hash audit records all original files, the three intended
modified files, this new report, and unchanged ranker/frozen G1/G2/PR1 bytes.
No staging, commit, push, diary upload or PR3 work.
