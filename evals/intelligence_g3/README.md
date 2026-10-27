# G3 offline contracts and event ranking (PR1–PR2)

The owner approved PR1 on 2026-10-27 in the implementation chat, including sealed
G2 parent consumption and an additive CI compatibility checker. This package
validates and exports inputs. PR2 adds pure event ranking as described below.
There is no persistent history store, alias inheritance policy, budget planner,
evaluator, production integration, network client or model call.

## Trust and native contracts

`replay.load_input(manifest_path, manifest_sha256=...)` requires an external,
lowercase SHA256 of the exact G3 input manifest bytes. Missing/wrong pins fail;
the loader never computes a replacement trusted pin. The manifest pins the G3
configuration, complete selected Persona/delivery/history files and its parent:

* `accepted_g2`: independently supplied sealed G2 acceptance and prediction
  campaign pins. The acceptance must be `g2_development PASS`, offline eligible,
  full-campaign and bound to the same source/prediction release. The consumer
  checks seals, exact artifact sets/hashes, original source release, all frozen
  G1/G2 runtime/schema bytes and dependency locks. It does not call G2 acceptance,
  reproduce, generators or evaluators, and does not require today's HEAD to equal
  the historical G2 commit. Historical administrator/authorization flags are not
  rewritten. PR1 authorization comes from the current owner instruction.
* `synthetic_contract_probe`: explicitly labelled portable development snapshots,
  not G2 acceptance evidence. These contain unchanged native G2 outputs and inputs
  from three synthetic cases. Only the G3 envelope and trace paths were adapted;
  `fixtures/pr1/v1/provenance.json` retains original paths/hashes and source commit.
  Probe inputs cannot masquerade as the accepted-parent manifest variant.

The selected accepted job is exactly R1 / standard / mock / seed 1 / canonical /
non-prefix, matching PR6's `G3_HANDOFF.json` export. `job_id` plus timeline/step/
as_of select one complete registered prefix. Other strategies/expressions are not
supported in PR1. This is selection of existing immutable outputs, not rerunning
G2 or asserting new G2 acceptance.

`G3InputView` is parsed as the actual native PR6 type and compared with the parent
`StepRecord` using the native `handoff.views` projection. `G3Candidate` contains
native PR2 `EventSnapshot`, PR3 `EvidenceBundle`, PR4 `IntelligenceItem` and
`ItemSnapshot`, and PR5 `IntelligencePresentation`; it does not copy approximate
schemas or rewrite their contents. The original view digest and pinned trace
retain omitted audit fields. Native event identity state, full evidence result
(including archived claims/quotes) and exact published references are retained.
Grouping feature tables, old PR1 excerpt diagnostics and call observations are
audit-only parent artifacts, not new ranking features; the parent and trace pins
preserve access to them. `final_personalized_rank` stays absent from G3 outputs;
native views require null and `inference_is_source_fact=false`.

The formal `G3ReplayInput`, `ValidationResult` and export manifest now use
`g3-pr1-3`. Replay inputs require `document_archive` (native `VersionIdentity`
metadata, including visible version lineage, without historical document bodies)
and `item_snapshots` (the complete native PR4 prefix archive). Required
`observations` retain each prefix step's unchanged identity state, evidence result,
G3 candidates, source coverage and original G2 `source_coverage_digest`. The last
observation must equal the replay's current projection. Input manifests,
parent bindings, configuration and native probe envelopes remain `g3-pr1-1`;
their existing external pins are unchanged. Generated schemas remain in the PR1
`schema/v1/` family. Old formal replay snapshots are rejected and must be
re-exported from their original externally pinned parents; no automatic repair or
trusted-pin substitution is provided.

Both previous formal revisions (`g3-pr1-1`, `g3-pr1-2`) require re-export. The
observation archive is validation material, not a second ranking feature stream
or an independently trusted input. Externally trusted pins and sealed output
hashes remain the provenance boundary for serialized snapshots.

## Time, identity and references

G1 strict ISO timestamps and UTC normalization are reused. Every explicit supplied
Persona, delivery, interaction, coverage or candidate must be visible at `as_of`;
future rows cause an error, not silent filtering. Every selected native prefix
step is checked against its own cutoff before nested serialization, including
`model_copy`-poisoned payloads. Whole parent files can be read/hashed for integrity;
later prefix bodies remain unparsed. Counts of withheld parent steps/handoff views
are exported. Explicit-input filtering is always zero.

The original G1 loader filters future source history. For accepted G1 jobs the
diagnostic counts future exposure records across that pinned source catalog
(including unrelated trajectories), and reports visible history not imported and
unresolved IDs. For already projected synthetic inputs the source-catalog count
is null, not an invented zero. G1 history remains bound by the parent pin; it is
not silently converted from member-hash identities to G2 event identities.

Persona uses native `PersonaVersion` plus explicit origin/provenance. The selected
version must be the latest supplied version for that persona; duplicate IDs or
availability instants fail. All supplied versions must already be visible.
`DeliverySnapshot` wraps native G1 `Delivery` plus exact published item references,
availability and provenance. `Interaction` keeps included/rendered/opened/
acknowledged/dismissed separate, binds its delivery and exact event/revision/item/
snapshot, and checks both occurred_at and available_at. No signal is inferred as
knowledge; no penalties, feedback revocation policy or alias inheritance are
implemented. Unknown or ambiguous targets must be resolved explicitly before
being supplied. Past references never follow today's aliases.

The adapter verifies unique IDs, complete document/event/item/view sets, cursor/
state chains, immutable claim/quote archives, quote spans/hashes/provenance,
claim/reference resolution, source pointers, bundle/item digests and unchanged
native item/expression bindings. Empty event sets retain the step, source coverage
and evidence gaps. Unknown/failed coverage is never interpreted as no world change.
Character budgets and reading estimates remain G2 data, not a G3 selection policy.

Both `load_input()` and direct `G3ReplayInput.model_validate_json()` enforce the
current candidate/bundle/active-registry/current-snapshot sets and exact published
snapshot references. A legitimate empty pool remains valid; dropping candidates
or references from a nonempty parent fails. Event anchors and creation times must
agree with the registry, creation transitions and visible document archive;
related events and feature/transition document references must resolve.
Snapshot IDs must follow native PR4 derivation. Predecessors must be unique,
strictly older and exactly match the as-of same-event/identity-transition history;
dangling, self, future, reordered or omitted predecessors fail. The bridge also
checks native PR5 expression snapshot derivation and predecessor bindings.

Shared evidence checks cover current, bundle and archived assessments, claims,
citations, links, memberships, transitions and events. Each step resolves its own
assessment links; historical links need not exist in today's current link set.
Independent support remains disabled as in native G2. State archives must extend
the previous observation exactly; unknown references and conflicting copies fail.
Native evidence counters must match their collections and keep confirmed
independent support at zero. Required unknown/failed/partial/offline coverage
diagnostics must survive even when the candidate pool is empty.

`G3Candidate` validates native bundle, PR4 item, PR5 presentation and PR6 view
digests on direct JSON parsing as well as in the bridge. Fact text/bindings are
checked with native PR4 provenance rules; selected/omitted claims partition the
bundle, and item uncertainties retain the bundle's native uncertainties. A
validator compares hashes and rejects mismatches; it never repairs them. Every
published reference, including history/delivery targets, must match the event
revision in its original candidate observation. Replay and candidate coverage
must match the retained G2 coverage digest at that step, including empty pools.

`ParentBinding` and `InputManifest` share the exclusive accepted/probe shape rule;
the pure adapter checks their job, parent pins and configuration binding agree.
Both entry points also require the canonical registered `G3Config` digest.
Observation step IDs must be unique within the replay timeline; a step cannot
name itself as its predecessor, even if other cursor/state hashes are consistent.
These are structural checks, not authentication of arbitrary serialized JSON.
Consumers still need the externally trusted input/run pins and sealed artifacts
for provenance. No external-pin bypass was established by the parent-kind defect.

## Commands and output

Run from the repository root with the existing environment; no dependency install:

```powershell
& .\.venv\Scripts\python.exe -B -m evals.intelligence_g3.contracts --check-schemas
& .\.venv\Scripts\python.exe -B -m evals.intelligence_g3.replay `
  --manifest D:\agent_project\cfaw-news\evals\intelligence_g3\manifests\pr1-E06-correction.json `
  --manifest-sha256 d037b501299e941ced69a614cc669a2323cea4d0ccd0c43b37ccb6b85b1ee380 `
  --out D:\agent_project\cfaw-news\.tmp\evals\g3\my-new-input
```

All parent/file paths inside manifests are repository-relative POSIX paths with
explicit read areas. Private/reference paths, traversal, links and Windows reparse
points fail before access. Accepted parents remain under `.tmp/evals/g2`; portable
fixtures are in this package. Output is restricted to a new `.tmp/evals/g3/` child.
There is no overwrite, force, resume, live, Oracle or repair option.

Output: canonical UTF-8/LF `input_snapshot.json`, `validation_report.json`,
`run_manifest.json` and final `sealed.json`. The manifest binds the external input
pin, current G3 source/schema hashes, actual HEAD and Python version. Input binds
parent source, schema/config revisions, raw/canonical config hashes and pool SHA.
No timing fields enter deterministic input bytes. Input failure creates no output;
an IO failure may leave an unsealed partial directory, which is not success and
must not be reused. This is not a durable checkpoint or transactional publisher.

CLI exits: 0 validated export, 1 fixed JSON diagnostic, 2 argument error. New error
families: `G3_MANIFEST_SHA_MISMATCH`, `G3_SHA_MISMATCH`, `G3_PATH_INVALID`,
`G3_PARENT_INVALID`, `G3_PARENT_NOT_ELIGIBLE`, `G3_UPSTREAM_CHANGED`,
`G3_SCHEMA_INVALID`, `G3_CONFIG_INVALID`, `G3_FUTURE_INPUT`,
`G3_REFERENCE_NOT_FOUND`, `G3_REFERENCE_MISMATCH`, `G3_DUPLICATE_ID`,
`G3_INVALID_INTERVAL`, `G3_PROVENANCE_INVALID`, `G3_OUTPUT_EXISTS` and
`G3_TEST_INVENTORY_INVALID`. Native G1/G2 error codes remain observable. Diagnostics
do not return evidence bodies or original exception messages.

## Verification and CI

```powershell
& .\.venv\Scripts\python.exe -B -m pytest tests/evals/g3 -q -p no:cacheprovider
& .\.venv\Scripts\python.exe -B -m pytest tests/evals -q -p no:cacheprovider
& .\.venv\Scripts\python.exe -B -m ruff check backend tests evals
& .\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
& .\.venv\Scripts\python.exe -B evals/run_baseline.py --output .tmp/evals/g3/my-new-seed.json
# In frontend: npm.cmd --offline run build -- --outDir <new-absolute-.tmp/evals/g3-path>
```

CI collects through `-p evals.intelligence_g3.junit_inventory --g3-inventory <path>`.
Its checker requires the exact union of the frozen G2 nodes/sources and registered
G3 PR1 nodes/sources. Existing G2 files/manifests/verifiers are unchanged. A missing,
extra, duplicate or stale source/node fails; native JUnit checking still requires
original node IDs and exact legacy skip exemptions. No new G3 skip is exempted.
CI's existing G2 smoke remains separate from full stage acceptance. PR1 does
not rerun or re-sign G1/G2 stage acceptance against a new global test inventory.

See `reports/PR1_CONFIG_STEP_REVIEW_FIXES.md` for the latest configuration/step
identity repair. `reports/PR1_EVIDENCE_REVIEW_FIXES.md`, `reports/PR1_REVIEW_FIXES.md`
and `reports/PR1_DELIVERY.md` retain earlier delivery evidence.
Tests and parent examples are synthetic/AI development,
nonblind and not independent semantic, human or real-user validation. No algorithm
gain, user utility or production readiness is claimed. The latest independent
PR1 re-review in chat “严格审查 G3-PR1” returned PASS on 2026-10-27; the owner's
current instruction authorizes PR2. See `reports/PR2_DELIVERY.md` for this delivery.

## PR2 ranking API and versions

`rankers.rank(replay_input, algorithm_id, config=None)` returns one immutable
`RankingResult`; `rankers.compare(replay_input, config=None)` returns B0–B4 and
P1 against the exact same replay input and registered configuration. Use PR1's
externally pinned `load_input()` first. Ranking reparses the complete formal PR1
contract and checks future metadata before serialization, including poisoned
`model_copy` objects. Structural validation of arbitrary JSON is not provenance
authentication; the trusted parent/input pins remain necessary.

Each result binds its full input SHA, event-pool SHA, Persona version, `as_of`,
reading budget, algorithm version and complete ranking configuration/SHA. Its
`comparison_sha256` binds the common input/config/pool and excludes algorithm ID.
It does not select a reading plan or assign final Focus/Radar tiers. Every G2
candidate survives in the result, including explicitly ineligible candidates.

| ID | Registered version | Event-level definition |
| --- | --- | --- |
| B0 (`b0`) | `g3-b0-event-v1` | Latest availability among the event's **current member** source pointers, descending. Score is UTC epoch seconds; missing material time is last. Publisher date and observation time are not freshness. |
| B1 (`b1`) | `g3-b1-event-v1` | G1 `baselines.candidate_scores`, unchanged Persona query and backend `score_all` BM25. Each event projects its original rule headline plus selected claim-summary statements into one lexical document. No optional model expression or inference is retrieval text. |
| B2 (`b2`) | `g3-b2-event-v1` | Identity-preserving B1 adapter: scores/order equal B1. G2 already aggregated events; G3 does **no grouping, deduplication, or event merging**. |
| B3 (`b3`) | `g3-b3-event-v1` | G1 formula `0.75 * BM25/pool_max + 0.25 * 2**(-age_days/7)`, applied to the existing event pool without G1 grouping. |
| B4 (`b4`) | `g3-b4-event-v1` | B3 minus distinct exposure-signal weights, only for unchanged observed statement content at the latest exact-event delivery. |
| P1 (`p1`) | `g3-p1-event-v1` | `0.50R + 0.15N + 0.20Δ + 0.15T + X - D`, with the features below. These are initial rules, not fitted or validated optimal weights. |

G1's frozen B2/B3/B4 start from document grouping and member-hash history. G3
explicitly adapts these to existing G2 identities and PR1 history; the new versions
are not byte-equivalent implementations of G1. No G1/G2 runtime, fixture, manifest
or historical report is changed. Any evaluation of event-merging benefit belongs
to a separate G2/end-to-end ablation and cannot be credited as G3 ranking gain.

## Registered feature policy

The sole registered policy is `manifests/pr2_ranking_config.json`, revision
`g3-event-ranking-v1`. `RankingConfig` and `RankingResult` derive schemas under
`schema/v2/`; PR1 schemas and configuration pins are unchanged. Supplying any
different policy value fails with `G3_RANK_CONFIG_INVALID`. A new policy requires
an explicit registration/version, not ad-hoc weight tuning against labels.

* **R (explicit lexical relevance):** unchanged G1 query joins interests, goals
  and free-text constraints; unchanged BM25 uses Han bigrams, title weight 2,
  k1=1.2, b=0.75 and five decimals. Normalize by the complete event pool's maximum;
  an empty/zero-score pool yields zero. Free-text Persona constraints are query
  terms; this adapter does not claim semantic enforcement of arbitrary prose.
* **N (absence of explicit current knowledge):** zero if all qualifying current
  statements exactly match tokenized `knowledge_known` entries, or an explicit
  `acknowledged` target contains all current qualifying statement signatures.
  Otherwise one when qualifying statements exist; zero without them. This is
  a conservative rule feature, not proof that a person has never seen the news.
  Inclusion, rendering, opening and dismissal never imply knowledge.
* **Δ (supported statement increment):** one only when selected, cited,
  `source_attributed` statement signatures add content compared with the latest
  same-event delivery's original candidate observation. Current assessments, or
  explicitly marked correction/withdrawal statements, qualify. Signatures use
  tokenized statement/type/marker, not claim/document IDs or source counts.
  Reprints, event revision changes and `content_changed` alone earn no increment.
  No prior delivery gives zero; absence of observed increment is not evidence of
  no world change. This proxy does not establish independent semantic materiality.
* **T (recency):** latest current-member `available_at`, age in UTC days, half-life
  seven days. Missing optional publication/event dates have no effect. Empty
  material times get zero recency; removal of required native timestamps fails
  PR1 validation. B0's registered missing-time score is `-1e30`.
* **D (repeat exposure):** use the latest exact-event delivery, ordered by generated
  time/as-of/delivery ID/snapshot ID. Inclusion contributes 0.10; distinct rendered
  and acknowledged signals add 0.10 and 0.25. Opened/dismissed add zero. Repeated
  rows of the same signal do not multiply the penalty. Compare nonempty qualifying
  statement sets; changed/unknown content has zero penalty, so supported updates,
  corrections and withdrawals cannot be suppressed by ordinary repeat penalties.
* **X (bounded exploration):** at most 0.05, multiplied by `1-R`, only for eligible,
  unseen exact-event candidates with N=1. Preference must casefold/strip-match
  registered `bounded` or `include plausible unfamiliar methods`; unknown/off
  preferences give zero. It cannot override the hard evidence gate.

All algorithms apply the same structural gate: G2 `hold`, insufficient bundle/item
evidence, or absence of qualifying cited attributions makes an event ineligible.
Ineligible events remain at the end of the complete ranking regardless of score.
This conservative policy can additionally withhold a wholly disputed candidate;
it never upgrades G2 evidence, source independence, uncertainty or candidate tier.
Consumers must respect `eligible`; numeric score alone is not permission to show.

After the gate, sort by descending score, then event key/revision/item ID.
Non-B0 scores round to five decimals **before** this tie-break. B0 preserves its
timestamp precision. No randomness, current clock, filesystem, network, model or
reference-label input participates in the pure ranking operation.

## Explanations, history scope and verification

Every row contains native event/revision/item/snapshot/view identities, original
G2 candidate tier, eligibility, block reasons, constraint input pointers, raw
features, weighted components, score and reason codes. RFC 6901-style JSON
pointers resolve against the bound `G3ReplayInput`; lexical normalization points
to the complete pool because BM25/maximum depend on that corpus. Component sums,
configuration and input references permit score reconstruction.

Only PR1's validated, already supplied deliveries, interactions and original
candidate observations are used. History matching is **exact event key**; current
aliases do not rewrite old targets. No merge/split inheritance, persistence,
feedback learning or general revisit policy is implemented. Those remain PR3.
Reading-budget selection remains PR4; quality metrics and a complete acceptance
matrix remain PR5. Neither a high score nor a test PASS is an algorithm-gain claim.

Example using a fixed synthetic native G2 parent (no labels):

```python
from pathlib import Path
from evals.intelligence_g2.contracts import json_bytes
from evals.intelligence_g3.replay import load_input
from evals.intelligence_g3.rankers import compare

value = load_input(
    Path("evals/intelligence_g3/manifests/pr1-E06-correction.json").resolve(),
    manifest_sha256="d037b501299e941ced69a614cc669a2323cea4d0ccd0c43b37ccb6b85b1ee380",
)
print(json_bytes([r.model_dump(mode="json") for r in compare(value)]).decode())
```

CI's existing G3 checker now combines the unchanged, pinned PR1 manifest with an
additive pinned `pr2_required_tests.json`. It still requires the exact frozen G2
test/source union and native JUnit checks; there are no new skip exemptions.
Run `python -B -m pytest tests/evals/g3 -q -p no:cacheprovider` plus the repository
checks above. PR2 tests include valid native multi-event/hold/empty inputs,
same-pool/version binding, score reconstruction/input-pointer resolution, G1
lexical parity, no regrouping, ties, missing dates, each exposure signal, supported
correction, reprints, bounded exploration, future poisoned objects, strict label
rejection and fresh-process hash-seed/import/read isolation.

For the Windows Python runtime used in this delivery, run the suite with the
per-process environment `PYTHONUTF8=1` (also inherited by test subprocesses).
Its default GBK codec otherwise resolves through a Python-version path alias
that the frozen isolation audits reject. `PYTHONIOENCODING` alone is insufficient.
The original failed run and complete UTF-8 rerun are separately retained in the
delivery report; no audit/test rule or dependency was changed.

Stop after PR2 delivery. Use `docs/G3_CODEX_PROMPTS.md`, section “PR2 独立审查提示词
（只审查，不改代码）”; independent review and owner approval are required before PR3.
