# G1-PR1 baseline lock

Revision note: the original execution and freeze sections below describe
**historical pr1-contract-v1 only**. They do not assert that current source files
were tested by that 210-pass run. The appended v2/v3 sections identify later
source, frozen inputs and separate regression evidence.

Date: 2026-10-20 (Asia/Shanghai). Schema revision: g1-pr1-1.
HEAD: 7f7f50324156b6a6ac61480a82311ba6ebd813b2
Branch: main. Existing working-tree changes are user-owned and preserved.
Python: 3.12.14. Existing Pydantic: 2.14.1.
No installation, external request, business database access, migration or Git publication.

## Read-only starting fingerprints

| Input | SHA-256 |
|---|---|
| AGENTS.md | 63b4b30b72c0a100489abdf596a684f2482e18816cbf596c4b09a62247ce0a32 |
| docs/CFAW_News_V1.md | 93ffeb537617c088e35f5916a868de3a67379eebb3f7af7b0ff0d3c51889a5e8 |
| docs/plans/G1_IMPLEMENTATION_PLAN.md | e880df79cc6796e14286a991a0f70ffec0e112465edb0347611a5be40df15925 |
| audit/G0_REUSE_AUDIT.md | 088f95a771e500b6dbbdef7efb3c03e42a9ead6594c942b9b466424282303078 |
| audit/G0_BASELINE.json | 8c96b980bcd87b057404807dfbb4bfe1229884d0c19b52fd19ab8f6950951e75 |
| pyproject.toml | de24cd2072f46d360be071f1bb60f2b184f3ab680d0636e1e791264d356ed7da |
| requirements.lock | fb14c8af21a7af52f25e31044ad6b0101f7acfb794f6a5c8ec668d45b3f4d72d |
| frontend/package-lock.json | b867e6c2da39e9c56d9cdaeb5b7456bed8751d4355672269a459ac7c515d961f |

G0 audited_source_sha256 matched 36/36 at implementation start. All 85 existing
tracked and non-ignored untracked files were separately pinned locally before edits.
The G0 report differs from its historical audit_artifact hash because of subsequent
document cleanup, as explained in that report; it is not overwritten or re-frozen.

## Existing user changes

Modified: AGENTS.md, README.md, docs/ARCHITECTURE.md.
Deleted: docs/ROADMAP.md, TIMELINE.md, UI_REBUILD.md, VERIFICATION.md,
docs/后续开发规划.md, docs/images/calendar-smoke.jpg, workspace-smoke.jpg.
Already untracked: audit/, docs/CFAW_News_V1.md, docs/plans/, and
docs/CFAW News G1 · Codex 分 PR 协作指南与提示词.md. Index was empty.

## Validation evidence

G0 125 passed and its other checks are historical evidence, not this implementation run.
Fresh commands/results are recorded below after completion. No G1 algorithm, live
model/source, human double annotation, production or CI claim is made.

## Review boundaries

All changes are additive in evals/__init__.py, evals/intelligence_v1/ and tests/evals/.
The test-only conftest.py centralizes independent temporary bundle construction.
Reference Event/Claim/Gold include explicit origin/provenance metadata; no real labels
are created. Exact URL/content-SHA split checks supplement declared family/upstream
checks, without semantic grouping. Source permission and Windows case-insensitive
sensitive-path guards were exercised with failing tests before their fixes.

The validator has no rehash/write command. The fixture manifest stays draft during
development and is frozen once after implementation checks. Self-hash is excluded.
Baseline lock and README are review documents, not algorithm input or a signature.
A future revision must preserve the frozen files and pin its own manifest SHA.

## Historical v1 execution results (2026-10-20)

- `.venv/Scripts/python.exe -m ruff check backend tests evals`: passed.
- `.venv/Scripts/python.exe -m pip check`: no broken requirements.
- `.venv/Scripts/python.exe evals/run_baseline.py --output .local/g1-pr1/seed-sanity.json`:
  passed; seed-sanity-v1, Recall@8=1.0, MRR@8=0.8333333333333334,
  nDCG@8=0.8645724197652078. This remains a developer seed smoke check.
- `npm.cmd --offline run build` in frontend: TypeScript/Vite passed, 24 modules;
  generated dist remains ignored. No frontend source changes.
- `.venv/Scripts/python.exe -m pytest -q --basetemp=D:/agent_project/cfaw-news/.tmp/g1-pr1-full-02 -o faulthandler_timeout=30`:
  **210 passed, 1 skipped, 1 warning in 31.80s**. This includes the original
  125 tests and 85 passing new tests plus one new skipped native-symlink test.
  The warning is the existing Starlette/httpx deprecation, not a PR1 failure.
- The native symlink test is skipped when Windows denies symlink creation.
  A separate resolved-path escape test passed without that privilege.
- The suite was run outside the restricted process sandbox after the restricted
  attempt stalled in socket._fallback_socketpair / asyncio / TestClient. The
  stalled process was interrupted. No business test assertion was changed to
  bypass this environment condition. Default sandbox temp-directory creation
  also failed; explicit ignored `.tmp/` directories were used instead.

The read-only schema check and manifest CLI are run again after the one-time
freeze. They validate only the synthetic PR1 bundle; no live source/model,
ranking, metrics, independent annotation or G1-a acceptance is implied.

## Requirement-to-test mapping

| Gate | Evidence | Boundary |
|---|---|---|
| T01/T02/T20, TZ01/TZ02 | test_temporal_visibility.py; invalid/cases.json | Pure selectors and strict context, no prompt/index |
| T03/VER01 | test_document_versions.py, future payload guard | Synthetic versions, no real history import |
| T22 | test_data_manifest.py | Frozen-copy tamper stops validation; no metric runner |
| T23 | test_split_leakage.py | Declared family/upstream and exact URL/SHA, no semantic clustering |
| T26 | test_provenance_and_rights.py | Structure/permissions, real review pending |
| HASH01 | test_hashing.py | Text SHA and raw-byte file SHA independently exercised |
| GOLD01 | test_data_manifest.py | Reference/time checks, semantic support pending |
| ISOLATION01 | test_offline_isolation.py | No external data/network/write; dependency code imports allowed |
| T10 partial | test_data_manifest.py | Empty candidate input and coverage states only |
| T25 | N/A | No migration |

There is no PR2-PR5 implementation, algorithm gain, semantic-support success,
completed double annotation, real-link verification or publication claim.

## Historical v1 frozen verification

Schema --check-schemas: passed. Manifest --strict: passed, no errors.
Frozen manifest SHA-256: `ad7acacba494827b5e1ead313bca2c30efdd8ba45bc1af1dc857e0cb7c43ca5c`.
Final original-file fingerprint check: 85/85 unchanged; index unchanged.
Ruff and git diff --check passed; additive files also checked for trailing whitespace.
No source changes followed the 210-pass full suite; only review notes and the
draft-to-frozen manifest transition followed it, with final schema/CLI validation.

## Historical v2: P1 evidence-reference repairs

Dataset revision: `pr1-contract-v2`. Its frozen manifest SHA-256 is
`d8e53e3c3c5019bd1c773a1ef30e2e0392432ff3b09b7e07c130902a8ec53202`.
This superseded v1; the schema and annotation versions remained unchanged.

The P1 source change was confined to validate.py: Claim evidence must match its
Event's family split and record origin; Gold support must match its ReplayStep
split and its record origin. Tests added 16 parametrized positive/negative cases
and a temporary-document helper. All shipped JSONL, Gold, schemas and registry
bytes stayed unchanged. The new manifest pinned the changed validate.py bytes.

| v2 controlled source | SHA-256 |
|---|---|
| validate.py | 796782016a693c0025288603672032a8fea7a4e3b06681ec9a90214ebbde3448 |
| provenance.py | 4359d154dacd661c634eae76c0c87ac1d3a25956947365303f1d64a9addcb915 |

Retained complete frozen input packages (local, ignored; never execute historical
code to validate current source):

- v1: `.local/g1-pr1/review-fixes/frozen-pr1-contract-v1/`; manifest SHA
  `ad7acacba494827b5e1ead313bca2c30efdd8ba45bc1af1dc857e0cb7c43ca5c`.
- v2: `.local/g1-pr1/p2-fixes/frozen-pr1-contract-v2/`; manifest SHA as above.
  The v2 copy was made before this P2 change and every controlled input hash matched.

### Actual v2 regression evidence (historical, not this P2 run)

The P1 execution report remains `.local/g1-pr1/review-fixes/report.md`, with full
commands. Its final CLI report is `final-validation.json` in that same directory.
The full suite used the unchanged P1 source subsequently frozen as v2; only the
manifest draft-to-frozen transition followed it, with strict validation afterward.

- Before P1 repair: 8 failed / 8 passed; after: 16 passed / 28 deselected.
- `python -m pytest -q --basetemp=D:/agent_project/cfaw-news/.tmp/g1-pr1-review-full-01 -o faulthandler_timeout=30`:
  **226 passed, 1 skipped, 1 warning in 38.61s** (227 collected: 125 legacy + 102 G1).
- Ruff, pip check, seed-sanity, schema consistency, strict Manifest CLI and offline
  frontend build passed. Seed Recall@8=1, MRR@8=0.8333333333333334,
  nDCG@8=0.8645724197652078; this is only the old developer smoke test.
- The skip was unavailable Windows native symlink creation; the warning was the
  existing Starlette/httpx deprecation. The resolved-path escape test passed.
- That v2 suite did **not** cover or fix Schema-role disguise, malformed synthetic
  URLs, or NUL paths. Passing v2 regressions did not resolve those P2 findings.

No v2 or v1 record proves live-source/model quality, semantic support, human
double annotation, replay/ranking fairness, G1-a acceptance, migration or remote CI.

## Current v3: P2 guards and matching freeze evidence

Current dataset revision: `pr1-contract-v3` (supersedes v2). The current frozen
Manifest SHA-256 is `f0661c814eb8cf1e120a6681e908cbe5be526f080d9a6a9c7f49b655d5638ccf`. Schema revision g1-pr1-1 and
annotation version synthetic-fixture-v1 are unchanged. Git HEAD remains the
original dirty-worktree base; the file hashes below identify the actual tested
source, rather than pretending these uncommitted changes exist in HEAD.

Changes from v2:

- Bind each required schema path to role=schema; validate its generated content
  by the required path, independent of a caller-supplied role.
- Convert expected URL/path parsing failures at their boundaries into
  PROVENANCE_INVALID / MANIFEST_PATH_INVALID; no blanket exception suppression.
- Add seven regression cases, including schema-role disguise with valid/invalid
  content, malformed synthetic URI and NUL file-item paths through API and CLI,
  plus the Python API's NUL manifest-location case. Strict/non-strict reports agree.
- Only validate.py and provenance.py controlled input hashes changed. No data,
  Gold, schema, registry or annotation bytes were changed to make validation pass.

| Actual v3 regression input | SHA-256 |
|---|---|
| evals\intelligence_v1\validate.py | 124ee7ff8085781c184dbde0da7c970e908de5ae5edfbc425f1998e48dee7815 |
| evals\intelligence_v1\provenance.py | 799ebbb5e11b351ea1526bd903b26329272287a96a613cc24bcb339c82c16175 |
| tests\evals\test_data_manifest.py | ec76c1e4e088a72ce17c5b9e0947f3db0a016d5426a929251ad930eb6cf05592 |

### Actual v3 checks

All commands run from D:/agent_project/cfaw-news unless stated otherwise, using
its existing .venv. The seven new cases failed before the implementation change
(six API/CLI/schema cases and one additional manifest-location case); all seven
passed afterward. The related subset passed 54 tests and skipped one native
symlink case. G1 collection is now **109 tests**, up from v2's 102.

The draft-source full suite passed 233/1 skipped/1 warning in 41.11s. To remove any
ambiguity about the frozen material, the final full suite below was run **after**
v3 was frozen, against the exact Manifest and code hashes above:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=D:\agent_project\cfaw-news\.tmp\g1-pr1-p2-frozen-01 -o faulthandler_timeout=30 --junitxml=D:\agent_project\cfaw-news\.local\g1-pr1\p2-fixes\pytest-frozen.xml
```

Result: **233 passed, 1 skipped, 1 warning in 42.69s**. The 234 collected tests
are 125 legacy + 109 G1 tests. There were zero failures/errors. The environment
permits Windows local socket initialization; tests use isolated temporary
storage and mock sources, not the working database or real model/source requests.
The skip is native symlink creation unavailable on Windows; the deterministic
resolved-path escape guard passed. Warning: existing Starlette/httpx deprecation.

JUnit report: `.local/g1-pr1/p2-fixes/pytest-frozen.xml`.
JUnit SHA-256: `e43fbc318ce527a1b1b5b497390a83840e4ec22307c69545730d8233437309b9`.
Frozen-input fingerprints: `.local/g1-pr1/p2-fixes/frozen-v3-inputs.json`.
Strict validator report: `.local/g1-pr1/p2-fixes/final-validation.json`.

Other freshly executed commands (all passed):

```powershell
.\.venv\Scripts\python.exe -m ruff check backend tests evals
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe evals/run_baseline.py --output .local/g1-pr1/p2-fixes/seed-sanity.json
.\.venv\Scripts\python.exe -B -m evals.intelligence_v1.contracts --check-schemas
.\.venv\Scripts\python.exe -B -m evals.intelligence_v1.validate --manifest evals/intelligence_v1/manifests/dataset_manifest.json --strict
git diff --check
```

Frontend: `npm.cmd --offline run build` passed (TypeScript/Vite, 24 modules).
Seed-sanity remains the old developer smoke check, Recall@8=1,
MRR@8=0.8333333333333334, nDCG@8=0.8645724197652078.
No source, test or frozen input changes followed the final full suite; only this
review evidence was completed. The final audit reconfirms their hashes.

### Preservation and checks not performed

The complete pre-repair v2 package is preserved at the v2 location recorded above;
its Manifest and all controlled input hashes matched before editing. The v1 copy
also retains its original Manifest hash. Nothing was re-frozen under the old
revision. Current Gold/all JSONL remain byte-identical to v2 and v1.

No requested local regression remains pending. Native symlink creation is the
explicit skipped case, not a passed check. Live-source/license verification,
live-model/semantic-quality tests, independent human annotation, replay/rankers/
metrics/fairness, Linux/remote CI, deployment and business database migrations
were **not run**. They are outside PR1; T25 remains N/A. No dependency installation,
Git commit/push or PR2-PR5 work was performed. Prior P2-open reports are historical;
this v3 record supersedes their status for the repaired guards.
