# G3-PR1 evidence, content, revision and coverage repair

2026-10-27, Asia/Shanghai. Branch `main`, HEAD
`450c85edab4a1d7bdb34d638aaedb043d1cfb8cf`. Scope is the owner's four new
PR1 review findings. Earlier deliveries remain historical evidence, not proof
that the four new cases passed. No PR2, production integration or publication.

## Changes and proof boundaries

| Finding | Enforcement shared by loader/export and formal JSON parsing |
| --- | --- |
| P1 current evidence can assert independent support / dangle | `evidence.py:validate_evidence` checks current, bundle and archive assessments; independent support is rejected. Native citation/claim content checks, link/claim/ref closure, membership/event/lineage closure, exact current/bundle partitions and append-only state extension apply per observation. |
| P1 rewritten facts under original IDs/digests | `G3Candidate.linked` calls `integrity.py:validate_candidate` to compare native bundle, PR4 item, PR5 presentation and PR6 view digests. `validate_candidate_evidence` checks native fact reconstruction/bindings, claim partitions and retained uncertainty. No identity or hash is repaired. |
| P2 old event revision is only mutually referenced | Required original `ReplayObservation` records retain each step's native candidates. All published refs are reconstructed from those candidates, including their original event revisions. Delivery/history refs must match these exact refs. |
| P2 replay coverage can disappear | Each observation retains the original native `G2ReplayInput.source_coverage_digest`. It must hash the observation's exact windows; candidate coverage must equal them, and replay coverage must equal the final observation. An empty candidate pool still has an observation and coverage diagnostics. |

Relevant source anchors: `contracts.py:G3Candidate` (line 202),
`ReplayObservation` (228), `G3ReplayInput` (249);
`evidence.py:validate_evidence` (38);
`integrity.py:validate_candidate` (155), `validate_candidate_evidence` (171),
`validate_replay` (194); `bridge.py:validate_step` (109) and `adapt`.

Native contracts/checks reused without editing G2:
`pr3/validate_output.py:check_ref_bytes`, `check_claim_fields` and the native
no-independent-support policy; `pr4/snapshots.py:identify`;
`pr4/validate_output.py:check_fact`; `pr5/pipeline.py:identify`; and the exact
`pr6/contracts.py:G3InputView` fields used by `pr6/handoff.py:views`.
The adapter does not invoke native assembly, generators, model calls or evaluators.
Synthetic test factories may invoke offline native rule APIs to construct fixtures.

Historical assessment links resolve against their own step's link set, not the
latest link set. Exact archive extension prevents past assessments from being
silently replaced in the final evidence state. Historical candidates also receive
the native content/view checks and local as-of preflight.

These checks establish structural consistency and native content-addressed
identity. They do not authenticate arbitrary self-consistent fabricated JSON.
Original external input/parent pins and sealed artifact hashes remain required;
the observation archive is not a new trusted pin or a source of research evidence.

## Contract and files

Formal replay/validation/export revision: `g3-pr1-3`. Required `observations`
contains native identity state, evidence result, G3 candidates, source coverage and
the original `source_coverage_digest` for every selected prefix step. Current replay
copies must exactly equal the last observation; snapshot/published-ref archives
must exactly cover all observation candidates. Missing, duplicate, future or
reordered observations fail.

Previous formal revisions 1 and 2 are rejected; regenerate from the original
externally pinned parents. Input manifests, parent bindings, config, portable
native fixture envelopes and original trusted fixture pins remain unchanged.
Schema family remains `schema/v1/`, with 12 generated contracts including the new
`ReplayObservation.schema.json`.

Changed/new files in this repair:

* `evals/intelligence_g3/{contracts.py,bridge.py,integrity.py,evidence.py,junit_inventory.py}`
* `evals/intelligence_g3/schema/v1/{G3ReplayInput,ReplayObservation,ValidationResult}.schema.json`
* `evals/intelligence_g3/manifests/pr1_required_tests.json`
* `tests/evals/g3/test_evidence_integrity.py`
* `evals/intelligence_g3/README.md` and this report.

## Executed verification

Evidence root: `.tmp/evals/g3/pr1-review-fix2-20261027-001/`. Completed
`*.command.json` records contain actual argv/cwd/timestamps/exit codes and raw-log
SHA256. `before/` retains exact pre-repair G3 source/tests. No earlier run directory
or frozen report was overwritten.

| Check | Actual outcome | Command record |
| --- | --- | --- |
| Pre-fix reproductions | Exit 1: 14 negatives failed with `DID NOT RAISE`; one additional coverage factory setup error | `red.command.json` |
| Coverage reproduction using exact pre-repair source | Exit 1: legitimate empty pool with 2 windows loaded/roundtripped; dropping coverage failed to raise | `red-coverage-original-contract.command.json` |
| Initial repaired focused run | Exit 1: 22 failed / 88 passed / 30 errors due primarily to datetime serialization in the new adapter projection | `focused.command.json` |
| Adapter serialization correction | Exit 1: 5 failed / 154 passed; two coverage fixture serialization errors and three existing G3 error-code expectations | `focused-recheck.command.json` |
| Final fixture/error-code correction | Exit 1: 4 failed / 162 passed; new tests expected raw ContractError while Pydantic correctly wrapped rejection as ValidationError | `focused-final.command.json` |
| First new regressions | Exit 0: 41 passed, before final diagnostic hardening | `new-regressions.command.json` |
| First complete G3 suite | Exit 0: 175 passed, before final diagnostic hardening | `g3.command.json` |
| Additional diagnostic red cases | Exit 1: both dropped required gaps and false independent-support counter failed to raise | `diagnostic-red.command.json` |
| Final new regressions | Exit 0: 43 passed | `new-regressions-final.command.json` |
| Final complete G3 suite | Exit 0: 177 passed | `g3-final.command.json` |
| Exact final inventory | Exit 0: 1301 nodes, frozen 1124 plus G3 177; frozen 97 source files plus G3 6 | `collection-complete.command.json`, `inventory-complete.command.json` |
| Final Ruff | Exit 0, all checks passed | `ruff-complete.command.json` |
| Final eight G1/G2/G3 schema groups | Exit 0, exact generated matches | `schema-complete.command.json` |
| G1 strict validation | Exit 0, `ok=true`; existing filtering diagnostics and semantic pending gates retained | `strict-g1.command.json` |
| Lexical seed sanity | Exit 0: recall 1.0, MRR 0.833333, NDCG 0.864572; synthetic sanity only | `seed.command.json` |
| Existing frontend offline build | Exit 0: TypeScript/Vite passed, fresh `.tmp` output only | `frontend-build.command.json` |
| Fixed sealed accepted parents | Exit 0 before final diagnostic hardening: E06/E10/DEV-01 loaded and JSON-roundtripped; candidates 1/0/2, observations 2/1/6, coverage 0/0/2 | `accepted-recheck.command.json` |
| Final sealed parent recheck | Exit 0: E06/E10/DEV-01 loaded and roundtripped under final diagnostic checks | `accepted-final.command.json` |
| DEV-01 sealed export and coverage-loss rejection | Exit 0: sealed/reloaded revision 3, 2 candidates / 7 refs / 6 observations / 2 windows; coverage loss rejected | `accepted-dev-export.command.json` |
| Final-code DEV-01 sealed export | Exit 0: sealed and roundtripped with final runtime/schema hashes; coverage-loss mutation rejected | `accepted-dev-export-final.command.json` |
| Preliminary full regression | Explicitly interrupted for diagnostic hardening; Windows exit 4294967295, no PASS claim | `full.command.json` |
| Final full regression | Exit 0: 1300 passed / 1 skipped / 1 existing warning, 963.60 seconds | `full-final.command.json` |
| Final JUnit completeness | Exit 0: all 1301 nodes, frozen gates/requirements present, one exempt skip | `junit-final.command.json` |

Additional failed coverage harness attempts are retained in `red-coverage` and
`red-coverage-fixed-fixture` logs: source policy / serialization setup, then a
relocated checkout-root path, were corrected. The successful pre-fix reproduction
imports exact preserved G3 source, rebinding only ROOT/PACKAGE to the real checkout;
no validation check was stubbed. Initial `accepted.command.json` also failed on the
adapter datetime serialization and is superseded by the successful recheck.

The 43 new cases cover all four reported mutations; load/export/direct JSON
entries; coordinated copies; rewritten old observations; original-view mismatch;
native IDs deliberately reminted in tests while fact grounding or uncertainty is
still invalid; historical links absent from current links; empty-pool coverage;
future/duplicate/dropped observations; and old revisions requiring re-export.
The last two cases also reject coordinated deletion of both copies of required
coverage diagnostics and a false `confirmed_independent_support` count. Per native
PR3 coverage policy, an empty window list requires `coverage_unknown`; each
non-covered window requires its source-status diagnostic. Collection counters are
checked, including an independent-support count of zero. The first full run was
stopped when self-review found this remaining empty-pool diagnostic gap; the final
run starts from scratch with the final 1301-node inventory.

Main executed commands, existing `.venv` only:

```powershell
python -B -m pytest tests/evals/g3 -q -p no:cacheprovider --basetemp=.tmp/evals/g3/pr1-review-fix2-20261027-001/g3-final-temp
python -B -m ruff check --no-cache backend tests evals
python -B -m evals.intelligence_v1.validate --manifest evals/intelligence_v1/manifests/dataset_manifest.json --strict
python -B evals/run_baseline.py --output .tmp/evals/g3/pr1-review-fix2-20261027-001/seed.json
python -B -u -m pytest -q -p no:cacheprovider -p evals.intelligence_g3.junit_inventory --junitxml=.tmp/evals/g3/pr1-review-fix2-20261027-001/full-final.xml --basetemp=.tmp/evals/g3/pr1-review-fix2-20261027-001/full-final-temp -o faulthandler_timeout=120
python -B -m evals.intelligence_g3.junit_inventory --inventory .tmp/evals/g3/pr1-review-fix2-20261027-001/node_inventory_complete.json --junit .tmp/evals/g3/pr1-review-fix2-20261027-001/full-final.xml
# cwd frontend, existing node_modules:
npm.cmd --offline run build -- --outDir D:\agent_project\cfaw-news\.tmp\evals\g3\pr1-review-fix2-20261027-001\frontend-dist
```

The unchanged asyncio probe timed out in the sandbox (124), and passed on the
normal Windows host (0, `ProactorEventLoop`). Full regression uses the normal host
without replacing the event loop, weakening frozen tests or installing packages.
The only skip is the existing Windows symlink privilege exemption:
`tests/evals/test_provenance_and_rights.py::test_symlink_outside_bundle_rejected_if_supported`,
reason `symlink creation unavailable: 1314`. No G3 test was skipped. The warning is
the existing Starlette/httpx deprecation. JUnit gate coverage is regression
evidence, not a new G2 stage-acceptance decision.

## Scope and remaining work

Initial boundary audit passed: 627 protected files unchanged, no added files in
frozen G1/G2/G2-test/backend/frontend source areas, no staged files, and
`git diff --check` exit 0 (`boundary.command.json`). Final post-test boundary and
diff audits also passed (`boundary-final.command.json`, `final-audit.command.json`):
all 627 protected files and 26 runtime/schema/test controls are unchanged; 21
original G3 input/config/fixture files and 2 earlier reports remain byte-identical;
the final accepted export's source hashes match the final runtime. Twelve repair
files were reviewed against exact pre-repair copies; see `repair.diff`,
`repair_changed_files.json`, and `final_audit.json` in the evidence directory.
The existing CI diff and owner-authored G3 plan/prompts predate this repair.
Original G3 fixture/input/config pins and earlier G3 reports remain unchanged.

The observation archive repeats native state prefixes, increasing serialized
input size. The same pinned DEV-01 input grows from 205,829 bytes in revision 2
to 1,044,491 bytes in revision 3 (6 observations). No storage/performance
optimization or production integration is claimed.
Cases remain synthetic/AI development, nonblind, and do not establish
independent human/semantic support, ranking gains or user value. No fresh G1/G2
stage acceptance was signed.

Use `docs/G3_CODEX_PROMPTS.md:99`, `PR1 独立审查提示词（只审查，不改代码）`, for
independent re-review with these four findings and this report. Stop at PR1;
independent re-review and owner approval are still required before PR2. No
staging, commit, push, dependency installation, external network or real-model call.

Disposition: all four reported reproductions plus the two diagnostic/counter
follow-ups now fail closed, and final local technical checks pass. No known
unresolved implementation item from this repair list remains. Submit for PR1
independent re-review; this self-review does not authorize PR2. Old snapshot
re-export and the larger observation archive remain explicit compatibility costs.
