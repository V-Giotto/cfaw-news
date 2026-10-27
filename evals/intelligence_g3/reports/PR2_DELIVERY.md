# G3-PR2: event baselines and explainable P1

Date: 2026-10-27, Asia/Shanghai. Base HEAD:
`450c85edab4a1d7bdb34d638aaedb043d1cfb8cf`, branch `main`.

## Entry gate and scope

Before editing, checked `git status --short`, current plans/contracts and the
latest completed independent PR1 review in chat “严格审查 G3-PR1”
(`01a1795f-0662-7831-bfa3-7f7e765e50b0`, review turn
`01a17c40-604d-7161-8828-3b3d6d8fbe96`). That review returned **PASS** with no
actionable P0/P1/P2/P3 and allowed PR2 technically, subject to owner approval.
The owner's current explicit instruction to start PR2 supplies that approval.
The older BLOCK and repair self-reports were not used as the current gate.

Initial worktree already contained `.github/workflows/ci.yml` modifications and
untracked G3 plan/prompts/package/tests. Those changes were preserved. This
delivery adds only PR2 ranking, policy, schemas, tests, incremental test inventory
and documentation. No staging, commit, push, external network/model, dependency
installation, production integration or PR3–PR5 implementation.

## Implementation

* `rankers.py`: pure `rank()` and `compare()`, complete same-pool/context/config
  fingerprints, G1 Persona query/BM25 reuse, no event regrouping, explainable
  P1 features and separate structural G2 evidence gate.
* `ranking_contracts.py`, `manifests/pr2_ranking_config.json`, `schema/v2/`:
  registered `g3-event-ranking-v1`, six `g3-{algorithm}-event-v1` versions,
  immutable finite-valued feature/component/result schemas and explicit weights,
  normalization, time/knowledge/history/missing-value/exploration/tie policies.
* `tests/evals/g3/ranking_support.py`, `test_rankers.py`: 53 synthetic tests,
  including native multi-event/hold inputs, same-pool checks, G1 lexical parity,
  no regrouping, deterministic ties/hash seeds, empty/missing-date cases,
  structural gates despite a higher held score, each exposure signal, supported
  correction, reprints, exploration limits, future poison, label rejection,
  import/read isolation, input-pointer resolution and score reconstruction.
* `junit_inventory.py`, `manifests/pr2_required_tests.json`: append 53 PR2 nodes
  and two test sources to the unchanged pinned PR1/frozen G2 inventories.
  Existing CI workflow bytes and original skip exemptions are unchanged.
* `README.md`: exact B0–B4/P1 definitions, adapters versus frozen G1 semantics,
  formulas, API example, history limitations and review/stop instructions.

B2 equals B1 on existing G2 events. B3/B4 reuse the frozen G1 scoring formula
without its document grouping. P1 is `0.50R + 0.15N + 0.20Δ + 0.15T + X - D`.
Hard evidence gates precede score ordering, retain every candidate and never
change G2 contents, citations, identity/lineage, uncertainty or independence.
Every result/row binds original input and native event/item/view references;
component input pointers resolve against the bound formal replay input.

## Actual commands and results

Execution evidence directory:
`D:\agent_project\cfaw-news\.tmp\evals\g3\pr2-20261027-001`.
Each `*.command.json` records exact argv/cwd/exit, elapsed time and raw log SHA;
`*.log` retains original output. `run_check.py` only captures execution evidence.
No test implementation or audit rule was changed for an environment failure.
The first logging wrapper also hit a GBK console-print error after saving the
child's failed-test log and exit record; later wrapper output uses UTF-8. The
original raw log and its recorded hash remain intact.

From the repository root with existing `.venv` (all commands use `-B`):

```powershell
python -B -m pytest tests/evals/g3/test_rankers.py -q -p no:cacheprovider --basetemp=.tmp/evals/g3/pr2-20261027-001/pr2-second-temp
python -B -m pytest --collect-only -q -p no:cacheprovider -p evals.intelligence_g3.junit_inventory --g3-inventory .tmp/evals/g3/pr2-20261027-001/node_inventory.json
python -B -m evals.intelligence_g3.junit_inventory --inventory .tmp/evals/g3/pr2-20261027-001/node_inventory.json
python -B -m ruff check --no-cache backend tests evals
python -B -m evals.intelligence_v1.validate --manifest evals/intelligence_v1/manifests/dataset_manifest.json --strict
python -B evals/run_baseline.py --output .tmp/evals/g3/pr2-20261027-001/baseline.json
# cwd frontend, existing node_modules only:
npm.cmd --offline run build -- --outDir D:\agent_project\cfaw-news\.tmp\evals\g3\pr2-20261027-001\frontend-dist
```

| Check | Actual result | Evidence |
| --- | --- | --- |
| First PR2 test run | Exit 1: 6 failed / 47 passed; test delivery helper selected the first candidate, which was a valid hold. Corrected helper to select a non-hold historical target; no predictor change was required for those assertions. | `pr2-first.command.json`, `pr2-first.log` |
| PR2 final focused tests | Exit 0: 53 passed | `pr2-second.command.json` |
| Complete G3 suite | Exit 0: 236 passed | `g3.command.json` |
| Ruff | Initial direct check exit 1 for four unused/import formatting findings in new tests; fixed those new imports only. Recorded final exit 0. | `ruff.command.json` |
| Complete collection/inventory | Exit 0 each: 1360 nodes (1124 frozen + 183 PR1 + 53 PR2) | `collect.command.json`, `inventory.command.json` |
| Eight existing schema groups plus PR2 schemas | Exit 0: exact generated bytes; PR1/G1/G2 schemas unchanged | `schemas.command.json`, `verify_contracts.py` |
| G1 strict validation | Exit 0, `ok=true`; native future-source filtering and pending research diagnostics retained | `strict-g1.command.json` |
| Seed lexical sanity | Exit 0: recall 1.0 / MRR 0.833333 / NDCG 0.864572; seed fixture sanity only | `baseline.command.json` |
| Offline frontend build | Exit 0: TypeScript/Vite passed; new `.tmp` dist only | `frontend.command.json` |
| Fixed native G2 probes | Exit 0: E04/E06/E10 have 1/1/0 events; each runs all six algorithms against the same input/config; input bytes unchanged | `examples.command.json`, `*-rankings.json`, `*-input.json` |
| Native withdrawal probe | Exit 0: acknowledged/rendered history does not suppress the supported withdrawal; penalty 0, change 1, novelty 1 | `withdrawal.command.json` |
| First full project regression | Exit 1: 6 failed / 1353 passed / 1 skipped / 1 warning, 926.94 seconds; six known locale-codec audit failures | `full.command.json`, `full.log`, `full.xml` |
| First full JUnit check | Exit 1: correctly rejects that failed run | `junit-original.command.json` |
| UTF-8 complete project regression | Exit 0: 1359 passed / 1 skipped / 1 existing warning, 935.70 seconds | `full-utf8.command.json`, `full-utf8.log`, `full-utf8.xml` |
| Final complete JUnit | Exit 0: exact 1360 nodes; all frozen requirements/gates present; one original exempt skip | `junit-final.command.json` |

The sandbox asyncio probe timed out (124) after eight seconds; regression uses
normal Windows host loopback with the same tests/event-loop implementation.
The first normal-locale full run exposed existing subprocess audit failures.
Diagnostic reproduction identified a standard-library codec read through
`cpython-3.12-windows-x86_64-none`, whereas the audit's resolved runtime root is
`cpython-3.12.14-windows-x86_64-none`. The codec path was incorrectly classified
as outside read. A canonical-base-interpreter probe still failed (exit 1:
5 failed / 17 passed) because `.venv` packages were outside that interpreter's
audit roots. Those attempts are retained separately, not counted as passes.

The successful environment probe kept the original `.venv` and enabled standard
`PYTHONUTF8=1`: the four affected isolation files passed unchanged (exit 0,
22 passed). Exact environment/argv are in `isolation-utf8.command.json`; failed
diagnoses are in `isolation-probe`, `isolation-path`, `isolation-canonical` logs.
UTF-8 mode prevents the late locale-codec import, without weakening the audit.

The complete second run uses the same original interpreter/packages and unchanged
tests with `PYTHONUTF8=1` (per-process only):

```powershell
# Effective environment of the second child run, set by the capture wrapper:
$env:PYTHONUTF8 = '1'
python -B -u -m pytest -q -p no:cacheprovider -p evals.intelligence_g3.junit_inventory --junitxml=.tmp/evals/g3/pr2-20261027-001/full-utf8.xml --basetemp=.tmp/evals/g3/pr2-20261027-001/full-utf8-temp -o faulthandler_timeout=120
python -B -m evals.intelligence_g3.junit_inventory --inventory .tmp/evals/g3/pr2-20261027-001/node_inventory.json --junit .tmp/evals/g3/pr2-20261027-001/full-utf8.xml
```

The only skip is the unchanged Windows symlink exemption:
`tests/evals/test_provenance_and_rights.py::test_symlink_outside_bundle_rejected_if_supported`,
reason `symlink creation unavailable: 1314`. No G3 test is skipped. The warning
is the existing Starlette/httpx deprecation. The native JUnit requirement/gate
counts establish regression completeness, not a new G2 stage-acceptance decision.

## Change audit and limitations

`audit_changes.py` compares current files to the initial hashes and the exact
latest PR1 review copy for original README/inventory diff. The first audit failed
because non-NUL Git output quoted two existing Chinese filenames. The corrected
audit uses NUL-delimited Git paths and independently verifies those two files
against the PR1 review copy. Initial `boundary-corrected` exit 0: 773 original
files, 771 unchanged; only G3 README/inventory changed. All 720 original files
outside the G3 package/tests remain unchanged, including frozen G1/G2, backend,
frontend, dependencies, archive data, `.gitignore` and the pre-existing CI diff.
The PR2 diff, final hashes and exact added-file list are recorded locally in
`PR2.diff` and `audit.json`. No diary is staged or uploaded.

Final boundary audit is in `boundary-final.command.json`; only those same two
original G3 files changed and nine PR2 files were added (including this report),
for 11 PR2 files total. `diff-check-corrected.command.json` and
`diff_checks_final.json` retain the per-file `git diff --no-index --check` results:
raw exit 1 means expected content differences; all 11 checks have no whitespace
diagnostics. The first wrapper incorrectly treated that diff exit as an error
(`diff-check.command.json`, exit 1); corrected wrapper exit 0. Final Git tracked
diff whitespace check also exits 0. No whitespace repair or source change was
needed. All original G3 contracts/bridge/integrity/evidence/loader, PR1 schemas,
fixtures, pins and tests remain byte-identical.

These are synthetic/AI-development, nonblind structural and engineering checks.
Δ detects cited attributed statement increments, not independent semantic truth
or research-grade materiality. N measures absence of explicit current knowledge,
not verified unfamiliarity. Free-text Persona constraints remain G1 lexical query
terms; arbitrary prose is not semantically enforced. Exploration accepts only
registered explicit preference strings. History uses exact event keys and supplied
PR1 snapshots only; alias/merge/split inheritance and persistence remain PR3.

No ranking gain, real-user utility, independent human validation, fresh G2 stage
acceptance, complete G3 acceptance or remote CI/deployment result is claimed.
Local PR2 implementation/regression checks pass; this is a delivery self-check,
not independent PR2 approval.
Stop after PR2. Independent review uses `docs/G3_CODEX_PROMPTS.md:158`,
“PR2 独立审查提示词（只审查，不改代码）”. PR3 requires that review and owner approval.
