# G3-PR1 registered configuration and step identity repair

2026-10-27, Asia/Shanghai. Branch `main`, HEAD
`450c85edab4a1d7bdb34d638aaedb043d1cfb8cf`. Scope: the two reported P2 formal
replay defects only. No wire fields, schema revision or original input pins change;
legitimate `g3-pr1-3` snapshots remain compatible. No PR2 or production integration.

## Implementation

* `integrity.py:31:validate_registered_config` checks the parent canonical digest
  against the registered `G3Config`. Both `bridge.py:adapt` and
  `integrity.py:200:validate_replay` call this same check (`bridge.py:264`). Unknown canonical digests
  fail with `G3_REFERENCE_MISMATCH`, field `binding.config_sha256`.
* `validate_replay` indexes observation cursor `step_id` values for uniqueness (line 206),
  failing with `G3_DUPLICATE_ID`, and explicitly rejects
  `step_id == previous_step_id` with `G3_REFERENCE_MISMATCH`, field
  `observation.self_reference` (line 213). Existing ordinal/time/parent-state checks remain.

The duplicate-ID regressions rename the native two-step E06 synthetic fixture to `D0,D0`
or `D8,D8`, retaining ordinals 0/1 and increasing times. They synchronize identity,
evidence and top-level cursor copies, recompute the identity/evidence parent
digests and grouping-state binding, and assert those invariants before parsing.
The old model accepted both; the repaired model rejects them specifically with
`G3_DUPLICATE_ID`. This differs from copying an entire observation and failing
ordinal first. A separate distinct-ID self-reference test checks the explicit
error field rather than accepting the older generic cursor failure.

Changed/new files:

* `evals/intelligence_g3/integrity.py`, `bridge.py`, `junit_inventory.py`
* `evals/intelligence_g3/manifests/pr1_required_tests.json`
* `tests/evals/g3/test_config_and_steps.py`
* `evals/intelligence_g3/README.md` and this report.

## Actual verification

Evidence: `.tmp/evals/g3/pr1-review-fix3-20261027-001/`. Completed command records
retain real argv/cwd/timestamps/exit code/raw-log SHA256. `before/` retains exact
pre-repair G3 source/tests. Earlier reports and run outputs are not overwritten.

| Check | Actual result | Command record |
| --- | --- | --- |
| Pre-fix reproduction | Exit 1: four mutations were accepted (`DID NOT RAISE`); self-reference used the generic cursor error rather than its explicit field | `red.command.json` |
| First new tests | Exit 0: 5 passed | `new-tests.command.json` |
| New tests with adapter parity | Exit 0: 6 passed | `new-tests-final.command.json` |
| Ruff | First check exit 1 on new test import formatting; formatting corrected, final check exit 0 | `ruff.command.json`, `ruff-final.command.json` |
| Eight G1/G2/G3 schema groups | Exit 0: exact generated schema matches; schemas unchanged | `schemas.command.json` |
| Exact inventory | Exit 0: 1307 nodes = frozen 1124 + G3 183; source counts 97 + 7 | `collection-final.command.json`, `inventory.command.json` |
| G1 strict validation | Exit 0, `ok=true`; native filtering diagnostics/pending semantic gates retained | `strict-g1.command.json` |
| Lexical seed sanity | Exit 0: recall 1.0 / MRR 0.833333 / NDCG 0.864572; fixture sanity only | `seed.command.json` |
| Offline frontend build | Exit 0: TypeScript/Vite passed, fresh `.tmp` output only | `frontend-build.command.json` |
| Full G3 suite | Exit 0: 183 passed | `g3.command.json` |
| Fixed sealed G2 parent loading and JSON roundtrip | Exit 0: E06/E10/DEV-01, candidates 1/0/2, observations 2/1/6, coverage 0/0/2 | `accepted.command.json` |
| Full project regression | Exit 0: 1306 passed / 1 skipped / 1 existing warning, 975.41 seconds | `full.command.json` |
| JUnit completeness | Exit 0: exact 1307 nodes, all frozen gates/requirements present, one exempt skip | `junit.command.json` |

Main commands, existing `.venv` only:

```powershell
python -B -m pytest tests/evals/g3/test_config_and_steps.py -q -p no:cacheprovider --basetemp=.tmp/evals/g3/pr1-review-fix3-20261027-001/new-tests-final-temp
python -B -m pytest tests/evals/g3 -q -p no:cacheprovider --basetemp=.tmp/evals/g3/pr1-review-fix3-20261027-001/g3-temp
python -B -m ruff check --no-cache backend tests evals
python -B -u -m pytest -q -p no:cacheprovider -p evals.intelligence_g3.junit_inventory --junitxml=.tmp/evals/g3/pr1-review-fix3-20261027-001/full.xml --basetemp=.tmp/evals/g3/pr1-review-fix3-20261027-001/full-temp -o faulthandler_timeout=120
python -B -m evals.intelligence_g3.junit_inventory --inventory .tmp/evals/g3/pr1-review-fix3-20261027-001/node_inventory_final.json --junit .tmp/evals/g3/pr1-review-fix3-20261027-001/full.xml
python -B -m evals.intelligence_v1.validate --manifest evals/intelligence_v1/manifests/dataset_manifest.json --strict
python -B evals/run_baseline.py --output .tmp/evals/g3/pr1-review-fix3-20261027-001/seed.json
# cwd frontend, existing node_modules:
npm.cmd --offline run build -- --outDir D:\agent_project\cfaw-news\.tmp\evals\g3\pr1-review-fix3-20261027-001\frontend-dist
```

The native asyncio probe timed out in the sandbox (124) and passed on the normal
Windows host (0, `ProactorEventLoop`). The full suite uses that host with unchanged
event-loop/test implementations. No dependency installation, external network or
real model call.
The sole skip is the original Windows symlink exemption,
`tests/evals/test_provenance_and_rights.py::test_symlink_outside_bundle_rejected_if_supported`,
reason `symlink creation unavailable: 1314`. No G3 test was skipped. The warning is
the existing Starlette/httpx deprecation. JUnit gate coverage is a regression
check, not a fresh G2 stage-acceptance decision.

## Boundaries and review

Initial hash/diff audit passed: all 627 protected files unchanged, no added files
in frozen/production areas, no staged files, `git diff --check` exit 0
(`boundary.command.json`). Final post-test audits also passed
(`boundary-final.command.json`, `final-audit.command.json`): 627 protected files,
27 runtime/schema/test controls and 36 original G3 input/schema/report files match
their baseline hashes. The seven repair files have an explicit before/after diff
under `repair.diff`; see `final_audit.json`. Frozen G1/G2, production code, owner plan/prompts,
original G3 fixtures/config/input pins, schemas and earlier reports are outside
this repair's modifications. The initial workflow diff predates this repair.
No staging, commit, push or PR2 work.

These structural/technical checks do not authenticate arbitrary fabricated JSON;
trusted external pins and sealed outputs remain necessary. Synthetic/AI-development
results are not independent human/semantic validation, new G2 acceptance or
ranking/user-value gains. Independent PR1 re-review remains required using
`docs/G3_CODEX_PROMPTS.md:99`, `PR1 独立审查提示词（只审查，不改代码）`.

Disposition: both reported reproductions are rejected, adapter/JSON configuration
checks share one implementation, and final local technical checks pass. No known
unresolved implementation item from these two findings remains. Submit for PR1
independent re-review; this self-review does not authorize PR2.
