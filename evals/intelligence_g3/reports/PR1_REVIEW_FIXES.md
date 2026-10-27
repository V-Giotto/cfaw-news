# G3-PR1 independent-review fixes

Date: 2026-10-27, Asia/Shanghai. Base HEAD:
`450c85edab4a1d7bdb34d638aaedb043d1cfb8cf`, branch `main`.
Scope: the four reported PR1 contract/identity defects only. Owner authorization
is the explicit repair request. No PR2 implementation or publication.

## Repairs

| Finding | Current enforcement | Main evidence |
| --- | --- | --- |
| P1 serialized pool/reference loss | `G3ReplayInput.visible` invokes shared `validate_replay`: candidates, bundles, active registry and current snapshots have equal event sets; candidates match complete bundles and current snapshots; published references cover the full snapshot archive with exact event/item/time and current event revision. | `contracts.py:G3ReplayInput`, `integrity.py:validate_replay`, direct JSON negative tests |
| P2 dangling event identity | Shared `validate_identity` checks native graph, anchor existence/availability and lineage, registry/event anchor and creation-time agreement, creation transitions, related events, feature metadata and trigger/feature document references. | `integrity.py:validate_identity`; load/export negatives, direct JSON negatives |
| P2 snapshot identity/history | `validate_snapshots` checks the native PR4 ID formula, archive uniqueness/order, strictly earlier predecessors, exact as-of predecessor construction, lineage and change signal, registry coverage and birth observations. Bridge also compares native PR5 expression snapshots with the pure `observe` result. | `integrity.py:validate_snapshots`, `bridge.py:validate_step`; synchronized native-copy/handoff negatives for rule and expression snapshots |
| P2 mixed parent variants | `ParentBinding` and `InputManifest` share `parent_variant`; `adapt` reparses both, checks their kind, parent pins, job and configuration agreement, and checks the canonical configuration digest. | `contracts.py:parent_variant`, `bridge.py:adapt`; direct model and poisoned-model adapter negatives |

The parent-kind defect was a structural provenance classification defect. No
external-pin bypass was established. These model checks do not authenticate
arbitrary serialized JSON; trusted external pins and sealed artifact verification
remain necessary. The loader never derives a replacement trusted parent/input pin.

## Contract revision and affected files

Formal replay input/output revision is now `g3-pr1-2`. New required replay fields:

* `document_archive`: native G2 `VersionIdentity` metadata across the selected
  visible prefix, including visible version ancestors, without historical bodies.
* `item_snapshots`: the full native PR4 prefix archive, including historical and
  retired-event observations used by published references and predecessor links.

Old `g3-pr1-1` formal snapshots are explicitly rejected. Re-export from the
original externally pinned parents. The manifest, parent binding, configuration,
native probe envelopes and their trusted fixture pins remain unchanged. Schema
family remains `schema/v1`; the replay and validation schema literals distinguish
the new formal revision.

Repair changes: `contracts.py`, `bridge.py`, `replay.py`, new `integrity.py`,
`schema/v1/G3ReplayInput.schema.json`, `schema/v1/ValidationResult.schema.json`,
`junit_inventory.py`, `manifests/pr1_required_tests.json`, new
`tests/evals/g3/test_review_integrity.py`, `README.md`, this report, and an explicit
historical-status note in `reports/PR1_DELIVERY.md`.

G3 test registration now contains 134 nodes / 5 source files: the original 66
nodes plus 68 repair regressions. The frozen G2 inventory remains 1124 nodes /
97 source files. The additive union is exactly 1258 nodes / 102 source files.

## Local verification

Evidence root: `.tmp/evals/g3/pr1-review-fix-20261027-001/`. Every named command
record for a completed run contains the real argv, cwd, UTC timestamps, exit code
and raw-log SHA256. The interrupted preliminary full run is explicitly excluded
from pass evidence.
Initial G3 source/tests are retained under `before/`; historical initial output
directories were not overwritten.

| Verification | Actual result | Command record |
| --- | --- | --- |
| Pre-fix defect reproduction | Exit 1, 6 selected negatives failed with `DID NOT RAISE`; expected red evidence | `red-reproduction.command.json` |
| First repaired targeted tests | Exit 0, 102 passed (original PR1 tests plus first 45 repair cases) | `review-fixes.command.json` |
| Additional archive/native-history cases | Exit 1, 61 passed / 2 failed: test used integer revision instead of native SHA string; synthetic reappearance factory changed immutable availability. Both test fixtures corrected. | `archive-positive.command.json` |
| Corrected archive/native-history cases | Exit 0, 63 passed, including merge/split, document update and dormancy/reactivation | `archive-positive-recheck.command.json` |
| Exact collection and compatibility inventory | Exit 0, 1258 collected and exact union verified | `collection-final.command.json`, `inventory-final.command.json` |
| Ruff across backend/tests/evals | Exit 0, all checks passed | `ruff-final.command.json` |
| Eight native G1/G2/G3 schema groups | Exit 0, exact generated schema matches | `schemas.command.json` |
| G1 strict validation | Exit 0, `ok=true`; original filtering diagnostics/pending semantic gates retained | `strict-g1.command.json` |
| Seed lexical baseline | Exit 0, recall 1.0 / MRR 0.833333 / NDCG 0.864572; sanity fixture only | `seed.command.json` |
| Existing offline frontend build, output redirected to fresh evidence directory | Exit 0, TypeScript/Vite passed; source untouched | `frontend-build.command.json` |
| First sealed accepted-parent integration | Exit 1 after E06/E10 passed: DEV-01 exposed overstrict same-document feature-ref assumption | `accepted-integration.command.json` |
| Upstream regression while correcting fixture | Exit 1, 67 passed / 1 failed: positive fixture's subject did not permit native upstream inheritance; corrected to preserve native subject rules | `upstream-regression.command.json` |
| Corrected upstream positive | Exit 0, 1 passed / 67 deselected | `upstream-positive-recheck.command.json` |
| Sealed accepted-parent integration and formal JSON roundtrip | Exit 0; E06/E10 exports from initial integration roundtrip again; DEV-01 freshly exports and roundtrips. Candidate/reference counts: 1/2, 0/0, 2/7. | `accepted-integration-final.command.json` |
| Final complete G3 suite | Exit 0, 134 passed, including all 68 repair regressions | `g3-final.command.json` |
| Full project pytest | Exit 0, 1257 passed / 1 skipped / 1 existing warning, 903.17 seconds | `full-final.command.json` |
| Full JUnit completeness and frozen gate projection | Exit 0, exact 1258 nodes, all frozen requirements/gates present, exactly one exempt skip | `junit-final.command.json` |

Native PR2 can inherit feature refs from an older version or an explicit upstream
document (`pr2/features.py:extract_features`). Each ref is checked against the
referenced archive document's availability, not forced to match its owning
feature's version/time. The DEV-01 sealed parent exposed this distinction, and a
dedicated native upstream positive plus incorrect-ref-time negative now cover it.
The earlier full run (`full.log`) was stopped for this correction before
completion; its runner and child processes were terminated, and it supplies no
pytest exit code or pass claim. The final full command below runs the final source
and inventory from scratch in a fresh output directory.

Full-suite command (native Windows host, unchanged event loop):

```powershell
& .\.venv\Scripts\python.exe -B -u -m pytest -q -p no:cacheprovider `
  -p evals.intelligence_g3.junit_inventory `
  --junitxml=.tmp/evals/g3/pr1-review-fix-20261027-001/full-final.xml `
  --basetemp=.tmp/evals/g3/pr1-review-fix-20261027-001/pytest-full-final-temp `
  -o faulthandler_timeout=120
```

Other completed commands (using the existing `.venv` interpreter):

```powershell
python -B -m pytest tests/evals/g3 -q -p no:cacheprovider --basetemp=.tmp/evals/g3/pr1-review-fix-20261027-001/g3-final-temp
python -B -m ruff check --no-cache backend tests evals
python -B -m evals.intelligence_g3.contracts --check-schemas
python -B -m evals.intelligence_g3.junit_inventory --inventory .tmp/evals/g3/pr1-review-fix-20261027-001/node_inventory_final.json --junit .tmp/evals/g3/pr1-review-fix-20261027-001/full-final.xml
python -B -m evals.intelligence_v1.validate --manifest evals/intelligence_v1/manifests/dataset_manifest.json --strict
python -B evals/run_baseline.py --output .tmp/evals/g3/pr1-review-fix-20261027-001/seed.json
# cwd frontend, using existing node_modules:
npm.cmd --offline run build -- --outDir D:\agent_project\cfaw-news\.tmp\evals\g3\pr1-review-fix-20261027-001\frontend-dist
```

The sandbox's unmodified `asyncio.new_event_loop()` probe timed out (124); the
same probe on the normal host passed (0, `ProactorEventLoop`). Full regression
uses that host environment, without monkeypatching the event loop or weakening
tests. No dependency installation, external network or real model call.

The sole skip is the existing Windows symlink privilege exemption:
`tests/evals/test_provenance_and_rights.py::test_symlink_outside_bundle_rejected_if_supported`,
reason `symlink creation unavailable: 1314`. No G3 test was skipped. The warning is
the existing Starlette/httpx deprecation. Native JUnit gate counts above are
regression coverage, not a fresh G2 stage-acceptance decision.

## Boundaries and remaining review

Protected-file hash comparison passed: 627 baseline files unchanged, no new files
in frozen G1/G2, G2 tests, backend or frontend source areas; owner plan/prompts,
root policy, archive and locks also match the baseline. `git diff --check` passed
and the index is empty (`boundary-audit.command.json`, `boundary_audit.json`).
Untracked G3 changes were reviewed against exact pre-repair copies; their explicit
file list and unified diff are retained in `repair_changed_files.json` and
`repair.diff`. Final post-test verification also passed
(`boundary-audit-final.command.json`); all 11 final runtime/inventory/test control
hashes remained unchanged throughout the final runs
(`final_source_and_skip_audit.json`).
The original 21 G3 fixture/input-manifest/config files also retain their exact
pre-repair bytes; only the G3 required-test inventory and its code pin changed.
The initial PR1 workflow change and owner-authored G3 plan/prompts were already
present before this repair; this repair does not modify them. No staging,
commit, push or production integration.

The scenarios are synthetic/AI development and the accepted parents retain their
historical G2 status. This repair is not a fresh G1/G2 stage acceptance, independent
semantic validation or evidence of ranking/user-utility improvement.

Independent re-review is required using `docs/G3_CODEX_PROMPTS.md`, section
`PR1 独立审查提示词（只审查，不改代码）` (line 99), with the four findings and
this repair evidence included. Stop at PR1; PR2 requires review and owner approval.

Disposition: the four reported reproductions now fail closed, and local technical
regression checks pass. No known unresolved implementation defect from this
repair list remains. Submit PR1 for independent re-review; this self-review does
not authorize PR2. The intentional replay revision change requires old exports to
be regenerated from their original trusted parents.
