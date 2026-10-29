# G3-PR3 independent review repairs

Date: 2026-10-28, Asia/Shanghai. Base HEAD remains
`fb42de414e56da7a0eb58e89d174d38a1495f02a`; the uncommitted PR3 delivery was
preserved. This repairs the supplied one P1 and two P2 findings only. No PR4,
budget planner, final matrix, production integration, staging, commit or push.

## Corrections

**Conflicting current feedback (P1).** The original code vetoed `declared_known`
but still derived pending correction/withdrawal markers from raw positive
knowledge. A later positive record could therefore retire protection while the
same row said the user had not declared knowledge. `revisit.py` now builds one
effective knowledge set from explicit history and visible Persona declarations,
applies the unretracted not-known veto, and uses that set for declaration and
pending markers. Acknowledged/known penalty signals apply only when current
knowledge is effective. All original log signals and source references remain;
no record is rewritten. Both arrival orders are tested for known and acknowledged
on delivered current correction, withdrawal and material-constraint versions,
through B4 and P1. Retracting the negative resolves the conflict; retracting only
the positive keeps the update protected.

**Current feedback versus uncertain ancestry (P2).** The original global
`matches=[]` fallback discarded exact current history along with uncertain
inheritance. It has been removed. Unresolved mappings are excluded individually;
exact history and confirmed mappings retain their own statement sets, deliveries
and feedback. Repeat equality is computed from retained reliable matches. The
native uncertainty diagnostic remains and unsupported ancestors contribute no
knowledge/penalty. Tests cross merge/split, missing/uncertain/confirmed ancestry,
and current acknowledged/known/opened signals. Opening remains insufficient to
declare knowledge; direct current acknowledgment remains effective despite an
unresolved ancestor. Original G2 identity and source evidence are unchanged.

**Default pytest/CI paths (P2).** The eight storage/export cases now request a
per-test UUID `g3_tmp_path` fixture under `.tmp/evals/g3/tests/storage/`, independent
of pytest's OS-level temporary directory. The product writer/export path policy
is unchanged. Four additional cases verify that append, pinned
load, input export and output export still reject paths outside allowed G3 areas.
No `--basetemp` or global pytest temporary-directory override is required for G3
tests. The full default run also exposed unchanged G2 tests that require project
temporary manifest paths, so CI's complete pytest command now explicitly adds
`--basetemp=.tmp/evals/g3/ci-pytest-temp`. This aligns the runner with the existing
G2 restriction; it does not change or weaken that restriction. The basetemp is
outside the uploaded CI evidence paths, so fixture copies are not added to the
upload. Its parent already exists after the inventory collection step. No global
local pytest configuration was changed.

The repair adds 34 test nodes: 12 current-update conflict cases, 18 current exact
history/ancestry cases and four path-boundary cases. PR3 now has 139 nodes; total
G3 has 376; complete collection has 1500 (1124 frozen + 183 PR1 + 54 PR2 + 139 PR3).
Only the PR3 test-source hashes/required-node manifest and its trusted local pin
were refreshed. Original PR1/PR2/frozen G2 inventories, nodes and skip exemptions
are unchanged. PR3 manifest pin is now
`25685047495403513b51a94abfc38d11d90727f5dbcd96bf8d4f6fa36cfbfecb`.
No wire schema, numerical policy, algorithm version or dependency changed.

## Actual execution evidence

Local evidence directory:
`D:\agent_project\cfaw-news\.tmp\evals\g3\pr3-review-fix-20261028-001`.
Each `*.command.json` records actual argv/cwd/environment, exit, timestamps,
elapsed time and SHA256 of its raw log. Existing `.venv`/frontend dependencies
only; no installation or provider/model/network call was introduced.

| Check | Actual outcome | Record |
| --- | --- | --- |
| Sandbox default-path reproduction | Exit 1: 8 setup errors because the sandbox OS temp root could not initialize; not a product reproduction | `default-path-red.command.json` |
| Normal-host default-path reproduction | Exit 1: original 8 cases all fail with `G3_PATH_INVALID`, no `--basetemp` | `default-path-host-red.command.json` |
| New feedback/mapping cases before fix | Exit 1: 16 failed / 14 passed | `feedback-mapping-red.command.json` |
| PR3 focused tests after fix, default entry | Exit 0: 139 passed, 51.25 seconds; no `--basetemp` | `focused-green.command.json` |
| Full G3, default entry | Exit 0: 376 passed, 102.08 seconds; no `--basetemp` | `g3-default.command.json` |
| Full project, original CI-style default entry | Running; failures in unchanged G2 manifest-path tests identified | `full-default.command.json` when complete |
| Unchanged G2 default-path probe | Exit 1: `MANIFEST_PATH_INVALID` for OS-temp parent manifest | `default-legacy-probe.command.json` |
| Full project, corrected CI-style workspace basetemp | Pending completion; separate from the original default-entry run | `full-workspace.command.json` when complete |
| Exact node/source collection inventory | Exit 0: 1500 nodes | `collect.command.json`, `inventory.command.json` |
| Complete JUnit verification | Pending complete regression | Follow-up record when complete |
| Ruff | Exit 0 | `ruff.command.json` |
| Lexical seed sanity | Exit 0: recall 1.0, MRR 0.833333, nDCG 0.864572; fixture sanity only | `baseline.command.json` |
| Offline frontend build | Exit 0: TypeScript/Vite passed, fresh `.tmp` output | `frontend.command.json` |
| Supplied reviewer scenario shapes rebuilt on repaired code | Exit 0: current-only conflict 8/8 and current acknowledged mapping 6/6 PASS, input bytes unchanged | `review-cases.command.json`, `review-*-fixed.json` |
| Initial repair boundary audit | Exit 0: eight existing files changed, one new report, remaining 794 initial files unchanged | `boundary.command.json` |

Commands use `-B`, per-process `PYTHONUTF8=1`, `PYTHONDONTWRITEBYTECODE=1` and
`PYTHONPATH=<repo>/backend`. Default-entry checks use normal Windows OS temporary
directories and local loopback because the restricted sandbox cannot initialize
its default pytest temp root. No tests, audit roots, sockets or skip rules were
weakened for that environment limitation.

Default full regression also exposes a separate existing G2 restriction: its
temporary parent manifests are constructed in the OS pytest directory, while the
unchanged G2 replay loader permits project `.tmp` areas. The standalone unchanged
`tests/evals/g2/pr3/test_replay.py::test_cli_hash_seeds_prefix_and_zero_model_cost`
reproduces this with `MANIFEST_PATH_INVALID` before any G3 ranking code runs.
The initial hash audit confirms those G2 files are unchanged. This repair fixes
the eight reported G3 path cases without changing frozen G2 behavior. The CI
command is explicitly aligned to the existing project-`.tmp` basetemp convention,
which is also used by the complete workspace regression. Original full default
failures are retained as failures; neither result is substituted for the other,
and no remote CI success is claimed.

Main completed/running child commands from the root (existing `.venv`):

```powershell
python -B -m pytest tests/evals/g3/test_history.py tests/evals/g3/test_revisit.py -q --tb=short -p no:cacheprovider
python -B -m pytest tests/evals/g3 -q -p no:cacheprovider
python -B -m pytest --collect-only -q -p no:cacheprovider -p evals.intelligence_g3.junit_inventory --g3-inventory .tmp/evals/g3/pr3-review-fix-20261028-001/node_inventory.json
python -B -u -m pytest -q -p no:cacheprovider -p evals.intelligence_g3.junit_inventory --junitxml=.tmp/evals/g3/pr3-review-fix-20261028-001/full-default.xml -o faulthandler_timeout=120
python -B -u -m pytest -q -p no:cacheprovider -p evals.intelligence_g3.junit_inventory --junitxml=.tmp/evals/g3/pr3-review-fix-20261028-001/full-workspace.xml --basetemp=.tmp/evals/g3/pr3-review-fix-20261028-001/full-workspace-temp -o faulthandler_timeout=120
python -B -m evals.intelligence_g3.junit_inventory --inventory .tmp/evals/g3/pr3-review-fix-20261028-001/node_inventory.json --junit .tmp/evals/g3/pr3-review-fix-20261028-001/full-workspace.xml
```

The first focused green run preceded one additional ordinary-conflict penalty
assertion; the final G3/full regressions use that assertion and the final pinned
test-source bytes. The supplied external reviewer JSON counterexamples were read
before editing; the new tests independently rebuild native synthetic G2 inputs.

## Boundary and remaining limits

The repair does not modify G1/G2 frozen data/code, original PR1/PR2 sources/tests,
production DB, frontend source, dependencies, archive data, `.gitignore`
or local diaries. Original delivery files outside the repair remain intact.
The one-line CI basetemp argument is the only runner change. Final
changed-path/hash/diff audit is recorded locally after completion.

These are synthetic, nonblind engineering checks. They do not establish semantic
truth, independent human validation, ranking gains or real-user value. The findings
are repaired locally and require independent re-review; this report does not grant
approval to begin PR4. Stop after this repair.
