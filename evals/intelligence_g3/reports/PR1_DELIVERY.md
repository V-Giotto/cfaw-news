# G3-PR1 delivery

Historical initial delivery. The four independent-review findings and current
repair verification are recorded in `PR1_REVIEW_FIXES.md`; the original counts
below do not verify the repaired implementation or `g3-pr1-2` snapshots.

Date: 2026-10-27, Asia/Shanghai. Base HEAD: `450c85edab4a1d7bdb34d638aaedb043d1cfb8cf`.
Owner approval: current chat explicitly approved PR1, sealed G2 parent consumption
and the additive CI compatibility checker. No commit/push or PR2 work is authorized
by this delivery. Independent PR1 review is pending.

Implementation and local technical verification are complete. Stop at PR1; this
report does not grant independent-review acceptance or permission to begin PR2.

## Result and scope

Implemented `g3-pr1-1` input contracts, native G2 bridge, strict historical
visibility/reference checks, pinned input export and CI test-inventory compatibility.
No ranker, exposure/feedback policy, budget planner, metrics pipeline, production
DB/API/UI, collector, model or external network integration was added.

`G3ReplayInput` binds parent/source/config/pool identities, selected Persona,
explicit deliveries/interactions, native candidates, full evidence/identity state,
published references, coverage and selection diagnostics. Candidate facts, rights,
source attribution, uncertainty and lifecycle history remain native G2 objects.
Input failure creates no output; success exports deterministic canonical input,
validation report, source-bound manifest and a final seal into a fresh G3 directory.

Accepted G2 inputs use sealed acceptance/campaign artifacts and original native
PR6 views/steps. They do not invoke G2 algorithms or its HEAD-bound acceptance
program. The historical release is checked against current frozen G1/G2
runtime/schema/lock bytes, while the new G3 code and CI remain a separate release.
The original administrator/authorization flags and reports are unchanged.

## Files

Only existing file modified: `.github/workflows/ci.yml` (inventory entry point and
artifact collection paths). Added:

* `evals/intelligence_g3/{__init__,contracts,bridge,replay,junit_inventory}.py`
* `evals/intelligence_g3/README.md` and this report
* 11 generated contracts under `evals/intelligence_g3/schema/v1/`
* `evals/intelligence_g3/manifests/pr1_config.json`, three pinned probe input
  manifests and `pr1_required_tests.json`
* 17 files under `evals/intelligence_g3/fixtures/pr1/v1/`: three native synthetic
  cases and their Persona/history/delivery/trace files, original source release
  and explicit nonblind synthetic provenance
* `tests/evals/g3/{__init__,support,test_pr1,test_inventory}.py`

The two initially untracked owner documents, `docs/G3_CODEX_PROMPTS.md` and
`docs/plans/G3_IMPLEMENTATION_PLAN.md`, are preserved unchanged. Frozen G1/G2,
old tests, backend, frontend source, archive provenance, locks and AGENTS are
preserved. The pre/post protection map covers 627 files; the inventory checker
also verifies all 97 frozen test-source files plus four new G3 test-source files.

Full changed-file hashes and command records are local:
`D:/agent_project/cfaw-news/.tmp/evals/g3/pr1-20261027-001/`.

## Actual verification

All Python commands used the existing `.venv/Scripts/python.exe -B`; no dependency
installation occurred. Full argv, cwd, actual UTC timestamps, exit code and raw log
SHA256 are in each `<name>.command.json` next to `<name>.log` in the local directory.
UTC timestamps correspond to 2026-10-27 in Asia/Shanghai.

| Check | Actual outcome | Command record |
|---|---|---|
| G3 PR1 tests | 66 passed; exit 0 | `pytest-g3-final.command.json` |
| All evals (G1/G2/G3) | 1064 passed, 1 skipped; exit 0 | `pytest-evals.command.json` |
| Full project | 1189 passed, 1 skipped, 1 warning; exit 0 | `pytest-full.command.json` |
| Ruff | All checks passed; exit 0 | `ruff.command.json` |
| Eight G1/G2/G3 schema groups | Exact matches; exit 0 | `schemas.command.json` |
| G1 strict dataset validation | ok=true; exit 0; semantic pending items retained | `g1-strict.command.json` |
| G3 schema CLI | g3-pr1-1; exit 0 | `g3-schema.command.json` |
| Seed sanity | exit 0; lexical smoke only | `seed.command.json` |
| Offline frontend build | npm/tsc/Vite exit 0; output in G3 temp directory | `frontend.command.json` |
| Accepted-parent adapter integration | Three selected cases succeeded; exit 0 | `accepted-integration-closed.command.json` |
| Public fixture CLI export | ok=true, one candidate; exit 0 | `g3-cli-positive.command.json` |
| Full inventory/JUnit | Exact 1190 nodes; exit 0 | `inventory.command.json`, `full-junit.command.json` |

Relevant commands (exact additional flags are retained in the records):

```text
python -B -m pytest tests/evals/g3 -q -p no:cacheprovider -p evals.intelligence_g3.junit_inventory --junitxml=<g3-final.xml> --basetemp=<fresh-temp>
python -B -m pytest tests/evals -q -p no:cacheprovider -p evals.intelligence_g3.junit_inventory --junitxml=<evals.xml> --basetemp=<fresh-temp> -o faulthandler_timeout=120
python -B -u -m pytest -q -p no:cacheprovider -p evals.intelligence_g3.junit_inventory --junitxml=<full.xml> --basetemp=<fresh-temp> -o faulthandler_timeout=120
python -B -m ruff check --no-cache backend tests evals
python -B -m evals.intelligence_v1.validate --manifest evals/intelligence_v1/manifests/dataset_manifest.json --strict
python -B -m evals.intelligence_g3.contracts --check-schemas
python -B evals/run_baseline.py --output .tmp/evals/g3/pr1-20261027-001/seed.json
cmd.exe /d /c npm.cmd --offline run build -- --outDir D:\agent_project\cfaw-news\.tmp\evals\g3\pr1-20261027-001\frontend-dist
```

The exact collected inventory is 1190 nodes: 1124 frozen nodes plus 66 G3 nodes.
Related JUnit verification confirmed exactly 1065 evals nodes, including the one
original Windows symlink permission exemption. No new G3 skip exemption was added.
Raw test results, inventory and JUnit are retained separately; this is not a new
G1/G2 stage acceptance. Remote CI and the committed-release G2 smoke were not run.

The full JUnit confirms the sole skip is
`tests/evals/test_provenance_and_rights.py::test_symlink_outside_bundle_rejected_if_supported`,
reason `symlink creation unavailable: 1314`. That native permission branch remains
unverified. The warning is the existing Starlette/httpx deprecation; no dependency
was installed to silence it. Full pytest ran once. Full raw log SHA256:
`a23ad7067b8f47dbc52b5773a06d6584a5425605298dc09552769a13dd6f33eb`.
Full JUnit SHA256:
`8a9ba2168c839056e7fb45c8100b9e4d212e729a42cbbe0c3bb01c626d472a91`.
`final_scope_check.json` confirms all 627 protected files are unchanged after
regressions; all frozen/new test-source bytes also pass the final verifier.
`git diff --check` passes; no staged files, commit or push exists. The final
`changed_files.json` contains 45 implementation-file paths and SHA256 values,
excluding the two untouched owner documents and ignored local run artifacts.

## Real parent artifact path

This is a new G3 adapter check of old immutable synthetic outputs, not a new G2
campaign or live model run. Trusted pins came from the prior audited acceptance:

* G2 source: `26826cb19658e5a6063bd3e5eb203e1d05a3ce65`
* G1 manifest: `5608f6c9f20d283f9274308fa98a277c535eb0d8d828fd0d863d6e1faafde06f`
* G2 campaign: `f5b49c3da518e4386999c226514dfe24524a2641bd856f3cbe932fc411ea01a9`
* G2 acceptance: `0013fa327d94635d463e5df384e2074f03514b8ae4ca20b17ed426c28b800fe4`

| Selected case | Final candidates | Retained published references |
|---|---:|---:|
| E06-correction | 1 | 2 |
| E10-negative | 0 | 0; unknown coverage retained |
| DEV-01 | 2 | 7 |

Local `accepted_inputs_control.json`, `accepted_integration.json`, three exported
`accepted-final-*` directories and their seals retain exact pins. Portable public
probes are explicitly `synthetic_contract_probe`; they do not fabricate acceptance.

## Failure history and closure

* First focused development run: 52 passed/1 failed because the coverage-negative
  test indexed an intentionally empty coverage array. The test now injects future
  coverage metadata before schema parsing; the final 66-node suite passes.
* Initial collection exposed a G3 plugin `read_json` import error; corrected to
  import the native JSON reader. Final collection/inventory checks pass.
* Initial accepted-parent projection exposed the difference between native
  campaign-relative trace pointers and actual repository-relative artifact paths.
  Both are now preserved separately. A follow-up found local variable shadowing;
  renamed the source-pointer variable. All three actual parent cases now pass.
* `accepted-integration.command.json` records an auxiliary script import-path
  failure; `accepted-integration-final.command.json` records the variable error.
  The successful closing record has a distinct name; earlier failures remain.
* Sandbox Windows asyncio initialization timed out after 10 seconds (124).
  A separately approved normal-host probe passed (0); regression tests used that
  environment with unchanged event loop and assertions. No external network was
  required.
* Frontend npm/tsc/Vite completed with exit 0 and complete build files. Its initial
  logging wrapper then failed printing a Unicode checkmark to GBK stdout, after
  saving the complete log and command exit 0. The wrapper output encoding was
  fixed; the successful build was not rerun or relabelled as a product failure.

## Limits and next review

Evidence remains synthetic / frozen rule/mock output / nonblind AI development.
Semantic truth, independent human review, real-user usefulness and generalization
are not evaluated. PR1 does not map G1 member-hash history or inherit history across
G2 merges/splits; it accepts only exact published targets and retains native
lineage. Feedback/revocation policy belongs to a later PR. IO failure may leave an
unsealed partial G3 directory; no durable checkpoint/transaction claim is made.

Run the **“PR1 独立审查提示词（只审查，不改代码）”** in
[`docs/G3_CODEX_PROMPTS.md`](../../../docs/G3_CODEX_PROMPTS.md), section 2.
The reviewer should inspect the actual new files, CI diff, trusted parent pins,
negative tests, original command/JUnit evidence and protected-file map. This
implementation chat is not the independent review. Stop at PR1; PR2 requires that
review and explicit owner approval.
