# G2-PR1 implementation and verification

Date: 2026-10-24, Asia/Shanghai. Scope: **PR1 contract skeleton only**.
Review profile: **ai_development**, single-AI internal, non-blind. Administrator acceptance and
G2 stage completion are separate. No second-human/per-item human annotation gate is required.
Result: **PR1 technical PASS; AI development self-review complete**. Human/independent research
is not_evaluated; G2 is not complete and this report does not grant G3 eligibility.

Base HEAD: `76ef14b531842ae449c4f907302218d2e2ea4c90` (working changes are not committed).
G1: `pr5-five-trajectories-v10-ai-development-r3 / g1-pr5-6`.
Frozen manifest: `5608f6c9f20d283f9274308fa98a277c535eb0d8d828fd0d863d6e1faafde06f`.
G2 raw config: `9ff868f34f58d5196979377f8697f11ad561d3b730a6eb849cbee72a459a3c84`.

## Implemented behavior

G1's pinned loader and as_of selection feed a G2 bridge. The bridge restores selected-version
origin/rights/provenance and body-free visible lineage metadata; only immutable G2 input reaches
the pure pipeline. Eight principal contracts and supporting models have 12 generated schema files.
Each document lineage becomes a singleton placeholder event with a stable, non-member-hash key.
The first real paragraph supplies a <=160-codepoint raw excerpt. Evidence stays unverified;
all Items stay hold; absent paragraphs yield null facts and no fabricated locator. Empty results
retain explicit unknown coverage in the diagnostic report. No reference Claim/EventGroup/labels
are used as predictions. Relations are empty; semantic support is not_evaluated.

The CLI pins G1 and config bytes, writes deterministic semantic artifacts plus manifest, and keeps
actual generation time/elapsed time in a separate Trace. It rejects overwrites, sensitive paths,
traversal and Windows reparse points. Input/output are validated before staging; write failure
does not publish a partial final directory. No DB/provider/config/application modules are imported
by G2 prediction (the frozen G1 retrieval helper remains an allowed transitive dependency).

## Executed checks

Local evidence root: `.tmp/g2-pr1-evidence/`; final command records/logs/JUnit under `final/`.
Every command record includes actual argv/cwd/time/exit status and log/artifact SHA. These are
ignored local artifacts, not published CI or independent research evidence.

| Check | Current result |
|---|---|
| Dedicated G2 suite | 70 passed; 0 skipped, final/g2-current.xml |
| All 35 G1 replay states through the G2 bridge | Passed inside the dedicated suite |
| Ruff: backend/tests/evals | exit 0 |
| G1 and G2 derived-schema checks | exit 0 each |
| G1 strict manifest validator | exit 0, same frozen pin |
| Existing seed sanity evaluation | exit 0, in-memory database; not algorithm-quality evidence |
| Frontend offline build | exit 0 via PowerShell direct invocation |
| Full pytest regression | 621 passed / 1 skipped / 1 existing warning; 622 actual unique nodes, final/full-current.xml; exit 0 |
| Protected asset fingerprints | 239 tracked G1/backend/frontend-source/lock/archive/ignore files unchanged |
| Single-step CLI smoke | exit 0; .tmp/evals/g2/pr1-smoke-final-002 |

The smoke has 1 candidate/event/bundle/Claim/hold Item, 0 relations and explicit coverage gap.
Its manifest hashes semantic artifacts; Trace has model_calls/token_usage/model_cost=0,
usage_reason=not_called, model_id=null. The sample is synthetic and not a technical-news finding.

## G2-T01–T10 evidence map

| ID | Tests and actual assertions |
|---|---|
| T01 | bridge inclusive time/offset/late visibility; future→FUTURE_VERSION before body serialization, naive→NAIVE_DATETIME; CLI rejects inconsistent visible set before pipeline/write |
| T02 | old/new version exact citations; same event_key/different event_revision; poisoned future paragraphs ignored early and rejected when visible |
| T03 | nested copied future persona/exposure/coverage/delivery rejected; raw future exposures filtered by G1; persona prose does not change facts |
| T04 | schema/config version checks; pure no-IO and unchanged input; candidate/source/seed reorder invariance; hash seeds 1/719 give identical semantic files including manifest |
| T05 | manifest/document/config one-byte tampering fails without rehash/repair/output; duplicate JSON keys and unfrozen inputs rejected |
| T06 | exact event partition; absent/duplicate/foreign members rejected; absent/future identity seed rejected; six relation labels individually validated but not generated |
| T07 | missing/cross-event/modified quote/hash rejected; fake facts, supports, supported/focus upgrades rejected; long raw Unicode excerpt bounded and marked truncated |
| T08 | empty known/unknown input, no paragraph and summary-only inputs; no fictitious Item/Claim/paragraph and no no_change claim; frozen authored fixture expectations |
| T09 | origin/rights/source/type mismatches and rights limits rejected; metadata-only records yield insufficient hold without body |
| T10 | audited subprocess forbids reference stat/open, private data, network and outside writes; canary DB/copy bytes unchanged; no Oracle/full-validator/business imports; staging fault/overwrite/path escape tests |

The dedicated sandbox reparse test recorded `synthetic_lstat_flag`; the complete loopback-enabled
run recorded `native_junction`. Both rejection branches passed, including actual native junction
integration. This adds no skipped G2 case. The only full-suite skip is the unchanged G1 symlink
test with Windows permission 1314. The real production DB is not fingerprinted
or opened; byte-preservation uses a synthetic temporary canary and no-access uses IO auditing.

## AI draft/review and corrections

`fixtures/pr1/v1/draft.json` preserves the initial synthetic-case draft and its actual time/hash.
`review_r0.json`, final `review.json` and `revisions.json` preserve review lineage, current source
hashes, complete JUnit hashes, and the temporal-hardening red/green test. The five cases/expected
outcomes retain their initial bytes; label revisions are empty. The final fixture manifest pins
all five development files and was separately revalidated after review metadata was frozen.
The same AI wrote code, fixtures and tests and reviewed them with full implementation/G1 context.
This is non-blind development work; no human gold, independent model review or kappa is claimed.

Corrections made during implementation, without changing G1 or tuning labels against scores:

1. Initial IO audit rejected runtime dependency METADATA reads. Dependency versions now come
   from already-loaded modules; the data-read allowlist was not widened.
2. Empty output initially retained only a gap count. DiagnosticReport now retains gap identifiers
   so empty/unknown coverage has an explicit explanation.
3. Validation was tightened to reject non-placeholder states, altered excerpts/locators, omitted
   claims, unsupported uncertainty text and missing/cross-event members; the deterministic pipeline
   continues to emit only fixed template text and source data.
4. Diagnostic/manifest paths have pure relative-path validation. Windows reparse tests exercise
   a synthetic flag when native creation is unavailable, with the mode explicitly recorded.
5. A new metadata-only future-object counterexample initially returned SCHEMA_INVALID because
   nested serialization preceded the temporal check. `preflight_time` now checks only metadata
   first and returns FUTURE_VERSION without serializing that body; the red/green JUnit artifacts
   are retained. This changes no valid-input placeholder output and uses the same G1 UTC functions.

Original intermediate artifacts are retained: first G2 full attempt had 1 failure/61 passed/1 skip;
the corrected second full attempt had 63 passed plus a JUnit property warning. Final dedicated
verification has 70 passed without that warning. No original failure was deleted or counted as pass.
The first frontend command failed with cmd-wrapper syntax before build; `frontend.log` is retained.
`frontend-direct.log` records the successful exact offline npm build through PowerShell.
The first sandbox full suite stalled at socket._fallback_socketpair before the first business
assertion. The identical business test passed with local loopback allowed. The first loopback
full attempt was interrupted for final source hardening; neither incomplete run counts as PASS.
The current complete rerun uses fresh `g2-pr1-current-full` temporary state and full-current.xml.
That complete run passed: all 70 G2 nodes exactly match the dedicated 70-node suite; all 427 G1
nodes and 125 old business nodes are present. The one skip belongs to G1, so 621 actual nodes
passed. No extra human work or new dependency is required. Existing Starlette/httpx deprecation
is reported as a warning; no dependency migration was attempted.

Final commands were the README commands with fresh basetemp/JUnit/output paths. The full pytest
invocation remained `python -B -m pytest -q -o faulthandler_timeout=120`, with local loopback allowed
after the original sandbox socketpair stall. Argument/exit/log/JUnit hashes are retained in
`final/*current.command.json`; unchanged G1 schema/strict-manifest, seed and frontend checks have
their own command records. `final/source-snapshot.json` pins 29 G2 source/test/schema/config/draft
files; `final/verification-summary.json` consolidates hashes and results. The final fixture-freeze
test also passed (1 test, recorded separately, not added to the full suite's 622-node count).

## Boundaries, impact and rollback

G1 frozen assets, legacy application code, dependency locks, archive/provenance and root ignore
policy are preserved. New repo changes are the G2 package/tests and three G2 .gitattributes rules.
The two owner-provided untracked G2 documents are preserved; no stage/commit/push is performed.
No network/provider calls, private goals/credentials/user-DB access, production migrations, API/UI,
full merging/extraction or ranking algorithms are added. Test databases and provider outputs are
temporary fixtures/mocks, not production migrations or live-model validation.

Known limitations: one document may cover multiple real events; different documents about one
event stay split; excerpts can lack context; independent semantic support, real news generalization,
user utility and production behavior are not measured. PR2 must version merge/split lineage and
old-key mappings. Revert only the G2 additions and added attribute rules to roll back; no DB
rollback is needed. Preserve owner documents and all frozen G1 history.

This PR does not grant G2 completion or G3 offline eligibility. Stop at PR1.
