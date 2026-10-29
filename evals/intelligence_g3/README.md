# G3 offline contracts, ranking, history, budgets and acceptance (PR1–PR5)

PR5 now adds a pinned reproduction/evaluation/checks/acceptance workflow below.
The prior PR1–PR4 sections retain their historical scope. PR5 engineering
acceptance is separate from independent review, owner acceptance and G4 approval.

The current PR5 review remains open for the grounded-fact-signature P1. Its repair
uses `g3-grounded-fact-signature-v2`: every non-whitespace symbol, number and
case-sensitive unit is retained, along with native G2 grounded scope/proposition
values. Claim/document/citation IDs and span offsets are provenance, not content
identity. Persona declarations use the same content projection with the finite
G2 field grammar; this does not give a declaration evidence or verification status.
Only an explicit leading `Reprint:` label is ignored. Arbitrary paraphrases,
unit conversions and semantic equivalence are not inferred.

The independent fact-extractor version is emitted in ranking diagnostics, bound
in PR2 comparison fingerprints and PR3/PR4 configuration fingerprints, and sealed
as `fact_signature_policy.json` by reproduction. Existing score weights and wire
schema versions remain registered; their v1 strings alone do not identify the
active feature extractor. Budget validation checks the same complete policy hash.
Old rankings can remain structurally parseable, but their context fingerprints
are rejected by the current planner/acceptance; old acceptance pins cannot validate
against this working-tree release. Frozen schemas, test bodies, original campaigns and reports
are retained as historical material.

The additive `manifests/pr5_fact_signature_campaign.json` has trusted exact-byte
SHA256 `48a9f1d2c88a1cd863eefcfb84677e3bb0aab0667f4618cdea1958baf52205b9`.
It preserves all 26 old cases and labels and adds 13 authored native G2 regressions
for symbols, quantities, units, Persona/acknowledgment and unchanged reprints.
There are 39 × 3 × 11 = 1287 jobs per seed, 2574 actual predictions across the two
registered seeds. Use the PR5 CLI sequence below with this new manifest/pin and
fresh output directories. The signature cases and labels are synthetic, reused,
nonblind `ai_development`, with zero independent test families or human gold.
Do not overwrite or relabel the old campaign. Current repair evidence is in
[FACT_SIGNATURE_REVIEW_FIX.md](reports/FACT_SIGNATURE_REVIEW_FIX.md); independent
review and owner final acceptance are pending. G3 is not finally accepted and G4
is not authorized.

The owner approved PR1 on 2026-10-27 in the implementation chat, including sealed
G2 parent consumption and an additive CI compatibility checker. This package
validates and exports inputs. PR2 adds pure event ranking; PR3 adds explicit
append-only synthetic file history and a separate versioned revisit adapter below.
PR4 adds an independent budget/display planner. These are offline development
interfaces; the application has no G3 integration, evaluator, network client or
model call.

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
feedback learning or general revisit policy is implemented by the PR2 API.
The separate PR3 API below adds explicit history and migration; PR2 behavior stays versioned.
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

PR2's latest independent re-review returned PASS (2026-10-27, chat “严格审查 G3”,
turn `01a17d55-7307-7d21-86e9-5355d717e7e8`). The owner's explicit instruction
to start PR3 provides its implementation approval. Earlier PR1 and PR2 delivery
reports retain their historical stop conditions.

## PR3 append-only history and revisit API

`history_contracts.py` adds `g3-pr3-history-v1`, `g3-pr3-journal-v1`,
`g3-pr3-input-v1` and `g3-pr3-ranking-v1` schemas under `schema/v3/`.
These wrap the unchanged native PR1 replay, including all historical G2 observations.
The new interaction/mapping contracts accept **synthetic records only**. No production DB, real-user
data, implicit Persona updates, new dependencies, network or model calls are involved.

`HistoryEvent` is an immutable fact with unique interaction ID, Persona ID,
delivery ID, exact published event key/revision/item/snapshot, occurrence and
availability timestamps, constrained source and provenance. Included is a server
fact, rendered is a client confirmation, and opened/acknowledged/dismissed/feedback
are explicit user actions. They do not imply any other action. A bound delivery
also establishes inclusion, even without a redundant included log event.
Only acknowledgment, `feedback=known`, or the visible Persona's explicit statement
knowledge can declare current statements known. Opening, rendering, helpful,
irrelevant and dismissal do not. An unretracted `feedback=not_known` conservatively
vetoes known inheritance for that history, regardless of occurrence/arrival order.
Correct that conflict by explicitly retracting the negative feedback. Contradictory
explicit feedback is not implicit learning.

`retract` references an earlier acknowledged/dismissed/feedback record for the
same Persona, delivery and snapshot. Passive facts cannot be retracted. Corrections
use a retraction followed by a new explicit record; the original record remains.
Journal records have append sequence, prior digest and canonical entry digest.
Availability is append-monotone; delayed occurrence is allowed. Duplicate IDs,
backdating, invalid retractions, reordered/truncated records and invalid chains fail.

`history_store.append_interaction(path, event, expected_head=...)` uses an exclusive
sidecar lock, verifies the caller's expected head, opens JSONL in append mode and
fsyncs. Paths are restricted to `.tmp/evals/g3/` or `.local/evals/g3/`.
There is no update/truncate/delete operation. A stale head or busy lock fails;
the writer does not auto-retry or recover a crashed writer's lock.
`load_journal(path, expected_sha256=...)` requires an external exact-byte pin.
The trusted pin/head must be retained outside the journal: a hash chain alone
cannot prove absence of a rewritten prefix or rollback. This is an offline file
mechanism, not a production persistence/durability claim.

`HistoryInput` strictly rejects future interactions/mappings and delegates future
delivery/Persona/evidence checks to the native replay. Its `replay.history` must be
empty: PR1 history requires a deliberate source-preserving import, never a silent
second history channel. `select_history(replay, complete_journal, mappings)` selects
the exact visible prefix by **both** occurrence and availability at `replay.as_of`;
future rows do not enter the selected input, features or prediction fingerprint.
`select_deliveries` and `select_persona` support source-side as-of projection;
ambiguous latest Persona versions fail. Direct explicit replay inputs still reject
future delivery/Persona records. Every reference, Persona and delivery time is
revalidated through both JSON and ranking entry points.

Same-key revisions share history only when no intervening native merge/split/complex
transition occurred. A merge that retains an old event key still requires explicit
migration. `HistoryMapping` pins exact historical/current published snapshots,
the ordered G2 transition path, certainty, availability, reason and provenance.
Paths traverse native transitions, including a merge ancestor omitted from a split
child's immediate lineage; the terminal transition must bind the target lineage.
Titles, URL similarity and document overlap never establish history inheritance.
Unknown, missing and uncertain mappings retain diagnostic statuses. Those records
do not inherit knowledge or repeat penalties. Exact history for the current snapshot
and other confirmed mappings remain usable; an uncertain ancestor does not erase
a current delivery, acknowledgment or explicit feedback. Confirmed mapping means structurally explicit synthetic migration,
not independently validated semantic equivalence. Every migration is retained in
the input and referenced by the output; original journal rows remain unchanged.

`revisit.rank_revisit(HistoryInput, algorithm="p1")` and `compare_revisit()` reuse
the PR2 lexical, recency, evidence gates and weighted components. Algorithms use
new `g3-{algorithm}-revisit-v1` versions and the registered `g3-revisit-v1` policy
in `manifests/pr3_history_config.json`. B0/B1/B2/B3 scores and order retain PR2
semantics; B4/P1 use the new history policy. Every algorithm binds the same input,
candidate pool, Persona, budget and configuration. All candidates remain present.

The repeat penalty applies only to identical latest delivered cited/attributed
statement sets. Distinct signals contribute included 0.10, rendered 0.10,
acknowledged/known 0.25, dismissed 0.20 and irrelevant 0.20; opened adds zero.
Known feedback and acknowledgment count once. Each additional distinct delivery
adds 0.05, capped at 0.75 total. Repeated log messages and additional reprint
documents do not multiply signals or create independent support. Knowledge declarations,
pending markers and knowledge penalties use the same effective knowledge: an unretracted
not-known veto clears effective knowledge, so a conflicting positive record cannot
retire correction/withdrawal protection or contribute an acknowledgment/known penalty.

Pending supported corrections, withdrawals and statement/constraint increments
clear the ordinary penalty. Earliest delivered statement sets per mapped event
are the pending-change anchor; merely including/rendering/opening the updated
item does not retire its protection. Acknowledgment must cover **current** statements
before it retires the update. Parent acknowledgment covers only its exact cited
statement set, never additional merged/split content. For B4/P1, eligible protected
updates precede ordinary eligible rows, then score and stable event identity break
ties. G2 hold/insufficient/no-cited-attributed-claim gates always precede protection.
This is a rule proxy for materiality, not semantic truth or a proven ranking gain.

Results include feature/component values, resolving JSON pointers into `HistoryInput`,
resolved snapshots, migration statuses, distinct delivery count, declared knowledge,
promotion and decision reasons. Unknown/partial/failed/offline coverage is diagnostic;
absence of a supported increment is never a claim of no real-world update.

```python
from evals.intelligence_g3.history import select_history
from evals.intelligence_g3.revisit import rank_revisit

# replay is a validated native PR1 input with visible deliveries and empty history.
# journal is the externally pinned complete synthetic append-only journal.
selected = select_history(replay, journal, mappings=explicit_mappings)
result = rank_revisit(selected, "p1")
```

For a saved, pinned `HistoryInput` under `.tmp/evals/g3/`, export one ranking to a
fresh directory (no planner or final acceptance matrix):

```powershell
python -B -m evals.intelligence_g3.revisit_cli --input .tmp/evals/g3/example/input.json --input-sha256 <trusted-file-sha256> --out .tmp/evals/g3/example/p1 --algorithm p1
python -B -m evals.intelligence_g3.revisit_cli --check-schemas
```

New failures include `G3_HISTORY_INVALID`, `G3_HISTORY_CHAIN_INVALID`,
`G3_HISTORY_HEAD_MISMATCH`, `G3_HISTORY_CONCURRENT_WRITE`,
`G3_HISTORY_MAPPING_INVALID` and native `G3_FUTURE_HISTORY`/`G3_FUTURE_PERSONA`.
Direct Pydantic wire validation raises `ValidationError` containing the specific
contract code; PR3's `parse_history` and ranking preserve that diagnostic as
`ContractError` without dumping rejected records.

Synthetic prediction specifications are in `fixtures/pr3/v1/scenarios.json`;
test expectations stay in `tests/evals/g3/test_history.py` and `test_revisit.py`.
The 1/3/7-day cases cover passive versus explicit actions, revisions, reprints,
constraint changes, corrections, withdrawals, unknown coverage and native
merge/split uncertainty. They are development/adversarial engineering checks,
not independent human evidence. The inventory checker appends a separately pinned
PR3 manifest; original PR1/PR2/frozen G2 requirements and skip exemptions remain.

Storage/export tests use independent `g3_tmp_path` fixtures under the allowed G3
test directory. These G3 tests require no `--basetemp` override under default pytest.
Explicit outside-directory rejection tests preserve the product path policy.
The separate unchanged G2 test suite rejects OS-temp manifest paths; CI's complete
pytest command now explicitly uses `.tmp/evals/g3/ci-pytest-temp` as its basetemp,
matching the established project-`.tmp` full regression convention. The failed
original default full run is retained separately. Local checks do not establish
remote CI success. Its parent is created by test collection, and the CI basetemp
is outside the uploaded evidence directories.
The 2026-10-28 review repair adds both orders of known/acknowledged versus not-known
on the current correction/withdrawal/material version, and exact current feedback
with missing/uncertain/confirmed merge/split ancestry. See
`reports/PR3_REVIEW_FIXES.md` for red/green and default-entry regression evidence.

See `reports/PR3_DELIVERY.md` for PR3's original commands, outcomes and limits.
Its 2026-10-28 independent re-review was PASS WITH CONDITIONS, with no remaining
code findings: complete regression retains the project-local pytest basetemp
required by unchanged G2 tests. The owner's explicit instruction to begin PR4
provides the next-stage approval. The existing uncommitted PR3 files are retained.

## PR4: separate reading-budget and Focus/Radar planner

`budget.plan_briefing(history_input, ranking, config=None)` consumes an **already
computed** native PR3 `RevisitResult` from any of B0/B1/B2/B3/B4/P1. It never calls
a ranker, changes scores, removes ranking rows or changes G2 candidate tiers.
`BriefingPlan.input` retains the entire `HistoryInput` and ranking, including all
evidence/history and unshown/held candidates. `events` retains original rank order;
`display_order` is the separate protected/Focus/Radar presentation sequence.
`archive_snapshot_ids` lists the complete current pool for future Archive/Library
consumers. Planning does not record an actual included/rendered/opened action.

`BudgetInput` binds the ranking's complete identity set, ranks, context/config/pool
hashes, as_of, Persona and registered budget to the supplied input. It independently
checks G2 hold/insufficient/no-cited-attributed-claim gates and PR3 pending-update
protection. Stage-one numerical scores are consumed as supplied; their computation
is not rerun or certified by planning. Keep a trusted external pin on saved inputs.
The output retains a digest of the exact complete ranking. Both direct JSON
validation and the public planner reject missing/duplicate/unbound rows or forged
eligibility/protection. Serialized final plans also rederive their decisions and
diagnostics; deleting an archive row or changing a budget/coverage claim fails.

The versioned `g3-budget-v2` policy supports **180 / 420 / 900 seconds** and three
registered experiment profiles: `focus60-radar40-v1`, `focus70-radar30-v1` and
`focus80-radar20-v1`. Their full definitions are in
`manifests/pr4_budget_configs.json`. The API's 70/30 development default is not an
accepted product default or a tuned optimum. Focus target seconds are
`floor(budget * focus_percent / 100)`; Radar receives the remainder.
V2 changes diagnostics only: allocation, reading rules, profiles, scores and
candidate retention retain their original definitions. The prior registry is
preserved byte-for-byte in `manifests/pr4_budget_configs_v1.json`.

Allocation is deterministic:

1. Eligible PR3 protected updates (including pending supported correction,
   withdrawal and material changes) get first access to the total budget in original
   rank order. They may borrow the Radar share; borrowed seconds are reported.
2. Other eligible rows are scanned in original rank order for the remaining Focus
   share. Rows that cannot fit are deferred, allowing later shorter rows to fit.
3. Deferred rows are scanned in the same order for the remaining Radar share and
   total budget. Ordinary rows do not borrow unused time from the other tier.

Every attempt uses estimated seconds, with no item-count cap. Protected updates
still obey G2 gates and the total budget. If protected mandatory content cannot
fit, the result explicitly records `protected_budget_unmet` and its event keys;
it does not claim that every correction was shown. Ordinary exploration scores
cannot displace protected updates or make a held row eligible. This is a greedy
registered allocation policy, not an optimal knapsack or utility claim. Its hard
ordinary shares may leave time unused even when an item fits the combined idle
time; both failed share attempts and unused seconds remain visible.

### Reading rule and complete-block projections

`unicode-display-units-v1` is an **uncalibrated estimate, not actual reading or
cognitive time**. It uses fixed Unicode 3.2 category tables across Python versions:
each Han codepoint in the registered ranges counts once; contiguous other Unicode
letters/numbers count once per run. Whitespace, punctuation and symbols add no
units; combining marks do not split a run. The exact ranges and rule are in
`budget.display_units` and `ReadingRule`.

For each candidate projection:

```text
estimated seconds = 4 + ceil(display_units / 4) + 2 * distinct evidence_ref_ids
```

Units include projected statements, attribution, raw scope values, verification
and lifecycle labels, limitations, risks and uncertainties. Citation IDs are not
read as prose; the separate two-second term is an estimated checking cost. The
native G2 coarse 90/12-second values are retained in the input and are not used.
Longer content therefore costs more without changing scores or candidate count.

Focus references the full rule blocks. Radar omits the explicitly labelled
`why_it_matters` inference. If the chosen tier's normal projection does not fit,
the planner may use a minimum projection that also omits the redundant
`what_happened` block. All projections retain the headline, **every selected claim
summary with attribution/scope/limitations**, risks, uncertainties and status text.
There is no quote substring, sentence or required-evidence truncation. Complete
source items stay available in `input.history_input.replay.candidates`.

Each event records one status: `focus`, `radar`, `truncated` (displayed with whole
optional blocks omitted), `not_displayed`, or `constraint_excluded`. `tier` and
`chosen_projection` distinguish the presentation tier from truncation. All three
estimates, content/omitted JSON pointers, used seconds and structured reasons are
retained. Unshown/excluded entries use zero presentation seconds, with no false
display claim. A candidate whose minimum exceeds the total budget remains in the
full result with `minimum_exceeds_total_budget`.

### Coverage and diagnostic denominators

Source coverage is separate from candidate selection. `windows` preserves every
native window, source ID, observation time, reason and status unchanged;
`status_counts` counts all supplied **raw windows**, including old windows outside
the query period. These raw counts are distinct from effective query coverage.

`requested-interval-conservative-union-v1` computes each known source's effective
coverage within `time_window_start` / `time_window_end`. Positive-duration queries
use half-open intervals `[start, end)`: touching endpoints and point observations
do not fill a duration. A zero-duration query is a point and includes windows
containing that instant, including a point window at that instant. This convention
is registered as `half-open-duration-closed-point-v1`.

The source universe is the union of candidate source pointers and all raw window
source IDs, including when the candidate pool is empty. Windows are clipped to
the query and partitioned at every boundary. Each segment retains pointers to
its original windows, observed statuses and structured reasons. No observation
means `unknown`. Any non-covered observation conservatively vetoes overlapping
covered claims: one distinct non-covered status is retained; multiple distinct
non-covered statuses yield `partial`. This policy does not infer that a later
covered observation has superseded an earlier failure for the same interval.

Adjacent confirmed segments are merged into `confirmed_intervals`; their
complement is `unconfirmed_intervals`. `unobserved_intervals` separately identifies
parts with no observation at all. Unioning adjacent/overlapping covered windows
does not double-count coverage; holes remain explicit. A source with one uniform
segment status retains it, and a mix of segment statuses is `partial`.
Top-level `effective_statuses` summarizes those **per-source query statuses**;
`has_gap` is true unless every known source is covered throughout the query.
An empty source universe is unknown, not a coverage pass.

`missing_source_ids` retains its raw meaning: candidate sources with no supplied
window. `unobserved_source_ids` identifies sources with no window applicable to
this query, so an old `covered` observation cannot hide the current period's gap.
No synthetic observation is inserted and no native status is rewritten. Even
complete coverage never confirms absence of updates, and no coverage status
changes ranking, eligibility, allocation or candidate retention.

Budget diagnostics report used/total seconds, per-tier target/used seconds,
protected borrowing and unused seconds. `canonical-token-set-with-raw-labels-v2`
deduplicates interests by `tuple(sorted(set(tokenize(label))))`, using exactly the
existing lexical matching equivalence, including case, whitespace, punctuation,
word-order and repeated-token equivalents. The stable `domain_key` is
`g3:domain-query:` plus the semantic SHA256 of that token list. Each group retains
every original label occurrence and its input pointer; the first declared label
is the display label. Persona and ranker inputs remain unchanged.

For each canonical query, **all** tokens must occur in the candidate's headline /
selected statements. Its ratio is presented matching eligible event keys / all
matching eligible event keys. Aggregate coverage is canonical queries with a
presented match / all distinct canonical queries, including unmatched queries.
For example `local`, `LOCAL` and ` local ` count once; with `unmatched`, coverage
is 1/2, not 3/4. Labels producing no tokens share one explicit unmatchable empty
query, with an `empty_interest_query_unmatchable` reason and no matched events.
No declared interests means denominator zero and aggregate null. This is a
lexical query diagnostic, not semantic domain understanding.

Event breadth is distinct presented native G2 event keys / all eligible event keys.
It does not establish independent sources, semantic independence or independent
research samples. Empty denominators produce null, with counts preserved. Diagnostics
also list truncated, unshown, constraint-excluded and unmet protected events plus
structured reason counts. These are PR4 plan diagnostics, not PR5 quality metrics.

```python
from evals.intelligence_g3.budget import plan_briefing
from evals.intelligence_g3.budget_contracts import BudgetConfig
from evals.intelligence_g3.revisit import rank_revisit

ranking = rank_revisit(selected, "p1")  # Stage one, same PR3 semantics.
plan = plan_briefing(selected, ranking, BudgetConfig(profile="focus70-radar30-v1"))
```

Save `plan.input` as canonical JSON in `.tmp/evals/g3/`, retaining an external
exact-byte SHA256. Export a single pinned planning job to a fresh output directory:

```powershell
python -B -m evals.intelligence_g3.budget_cli --input .tmp/evals/g3/example/budget_input.json --input-sha256 <trusted-file-sha256> --out .tmp/evals/g3/example/plan
python -B -m evals.intelligence_g3.budget_cli --check-schemas
python -B -m pytest tests/evals/g3/test_budget.py -q -p no:cacheprovider
```

The CLI writes the original input bytes and `briefing_plan.json`; wrong pins,
unbound inputs, existing output directories and paths outside the offline G3
areas fail. New errors include `G3_PLAN_INPUT_MISMATCH` and `G3_PLAN_INVALID`.
Current schemas are additive under `schema/v4_1/`; `schema/v4/` remains the unchanged
v1 snapshot. Current envelopes use `g3-pr4-input-v2` / `g3-pr4-plan-v2`, with
`g3-budget-v2`. Old v1 envelopes/configurations are rejected rather than silently
reinterpreted. To replan an old externally trusted input, explicitly validate its
unchanged `history_input` as `HistoryInput` and its `ranking` as `RevisitResult`,
then call `plan_briefing` with a current `BudgetConfig` preserving the chosen
profile. Save a new input and external pin; do not overwrite old artifacts or
substitute a freshly computed hash for an externally trusted pin.
The original 72 PR4 tests and their pin are unchanged; the new diagnostic tests
have their own additive manifest. PR1/PR2/PR3 and frozen G1/G2 requirements remain.

See `reports/PR4_DIAGNOSTICS_FIX.md` for the current repair checks and
`reports/PR4_DELIVERY.md` for the historical v1 delivery. This remains synthetic,
nonblind development evidence; reading-time calibration, user value, algorithm
gains and online behavior are not evaluated. PR4 stops here. PR5 requires separate
independent review and owner approval.


## PR5 full reproducibility and fail-closed development acceptance

PR1/PR2 independently passed. PR3/PR4 passed with conditions: keep the project-local
full-suite basetemp and include evaluable protected budget misses in PR5 denominators.
The current owner's PR5 start instruction supplies implementation authorization.
The 823 PR4-reviewed public files matched their review hashes before PR5 edits.
No independent PR5 review or G4 authorization is implied.

The frozen `manifests/pr5_campaign.json` has trusted exact-byte SHA256:
`56f2244812449db5ddb5a8bd2384cb302a3f9d66fb1205be167e9308da530daf`.
Save this pin outside the input manifest; do not recalculate a substitute from
untrusted input. The campaign pins 26 native G2/G3 synthetic HistoryInput files and
separate AI development references. It is reused nonblind development material,
not independent test data or human gold. The authoring script `build_pr5.py` uses
prior test builders only to freeze a NEW revision; prediction reads frozen JSON
and never imports builders, labels or evaluation. Do not rerun the builder over
an existing revision or rewrite historical fixtures/reports.

858 jobs per seed = 26 cases × 3 budgets × 11 variants; seeds 1 and 719 must have
identical semantic outputs. B0/B1/B3/B4/P1 share every candidate, Persona, history,
as_of and budget. B2 is a separate identity-preserving G2 aggregation control.
The five registered score ablations are no_history, no_material,
no_novelty_material, no_exploration and no_duplicate. They zero contributions
without renormalizing and preserve all hard gates and mandatory update protection.
A separate ScoreProjection/ExperimentInput envelope identifies experimental rows;
no historical ranker/planner version is changed. The default 70/30 allocation is
frozen for this campaign; alternate PR4 profiles remain separate registered options.

Use the existing virtual environment. On Windows the checks runner gives each
child PYTHONUTF8=1 and a project-local --basetemp, with no test/skip weakening.
All output directories must be fresh and under `.tmp/evals/g3/`.

```powershell
python -B -m evals.intelligence_g3.reproduce --manifest D:/agent_project/cfaw-news/evals/intelligence_g3/manifests/pr5_campaign.json --manifest-sha256 56f2244812449db5ddb5a8bd2384cb302a3f9d66fb1205be167e9308da530daf --out D:/agent_project/cfaw-news/.tmp/evals/g3/example-pr5/prediction
python -B -m evals.intelligence_g3.evaluate --run D:/agent_project/cfaw-news/.tmp/evals/g3/example-pr5/prediction --run-pin <saved-prediction-pin> --out D:/agent_project/cfaw-news/.tmp/evals/g3/example-pr5/evaluation
python -B -m evals.intelligence_g3.checks --out D:/agent_project/cfaw-news/.tmp/evals/g3/example-pr5/checks
python -B -m evals.intelligence_g3.acceptance --run D:/agent_project/cfaw-news/.tmp/evals/g3/example-pr5/prediction --run-pin <saved-prediction-pin> --evaluation D:/agent_project/cfaw-news/.tmp/evals/g3/example-pr5/evaluation --evaluation-pin <saved-evaluation-pin> --checks D:/agent_project/cfaw-news/.tmp/evals/g3/example-pr5/checks --checks-pin <saved-checks-pin> --out D:/agent_project/cfaw-news/.tmp/evals/g3/example-pr5/acceptance
```

The reproduction/evaluation/checks CLIs print their actual sealed output pins;
retain those outside their manifests and pass them explicitly to the next stage.
The acceptance CLI exits 1 on missing/wrong pins, files, config or source hashes,
missing/nonzero commands, incomplete/failed/unexempt-skipped JUnit, incomplete
matrix, unequal seeds, or mismatching rederived predictions/metrics/failures/report.
It recomputes all first-seed predictions and reference metrics, checks B2=B1,
and binds prediction/evaluation/checks to the same exact working-tree release.
The release records source/test/config/schema/fixture/lock/build-configuration
hashes and anchor commit; it explicitly identifies uncommitted working-tree bytes.
Old G1/G2 inventories, pins, schema and historical reports are not regenerated.
44 original PR5 tests, two JSON wire regressions, 31 test-control/metric/schema
review regressions and 59 fact-signature regressions have separate additive
pinned manifests; full inventory is 1754 nodes.
Prior required-test pins and test bodies are unchanged.

The v2 release also binds the pytest control plane. Collection and both suites
use `pytest_runner`, explicit pyproject/rootdir/confcutdir, disabled entry-point
autoload and an allowlist for loaded plugin and hook origins. Root and recursive
test control files are discovered before pytest imports any conftest. Only the
exact pinned `pyproject.toml` and fixture-only `tests/evals/conftest.py` are approved;
new/changed controls fail. A legitimate control change needs separate review and
an explicit policy revision, followed by new checks and pins. Runtime pytest,
_pytest and pluggy source/bytecode hashes, installed pytest11 metadata, startup
path controls and the effective six-variable child environment are fingerprinted.
Injected pytest/Python options are rejected; PYTEST_CURRENT_TEST is diagnostic,
and PYTEST_VERSION must equal the separately fingerprinted runtime version.
Each actual session emits a sealed `*.control.json` binding its exact invocation,
before/after snapshots and loaded plugins. The full-suite gate verifies these
records as well as every required JUnit result; ordinary imports do not count as
schema validation. `ranking_schema --check-schemas` compares the real v2 files,
rejecting corrupt/missing/extra schemas and unknown CLI arguments.

After fresh prediction/evaluation/checks, run the real fixed-pin regression in a
quiescent workspace, using the same three externally saved pins:

```powershell
python -B -m evals.intelligence_g3.control_probe --run <prediction-dir> --run-pin <saved-prediction-pin> --evaluation <evaluation-dir> --evaluation-pin <saved-evaluation-pin> --checks <checks-dir> --checks-pin <saved-checks-pin> --out <fresh-g3-probe-dir>
```

It first runs positive acceptance, then creates an exclusive temporary root hook
and requires both same-pin acceptance and the test runner to fail before the hook
executes. It removes only its own unchanged probe file and verifies source
restoration. It preserves all positive/negative command logs and output hashes.

Every ratio has numerator, denominator, sample_count, event_family_count,
data_source, value and undefined_reason. Samples are correlated event×case×budget
observations, never independent users; horizons share product-family identities.
nDCG@10 uses eligible rank order and all reference gains for IDCG. Recall and
miss rates include every evaluable important reference, including budget_unmet.
Undefined metrics stay null. No bootstrap interval or significance is asserted
without independent holdout families. B4 stays the baseline; P1 need not win.
Each RevisitCoverage horizon counts samples and families only from that window;
outside-window measurements carry zero support and an explicit undefined reason.
`metric_support` lists the actual families; `dataset_support` separately records
the whole cell. For the original 26-case P1 subset, each horizon is 9/9 on 18
correlated states from one family, while that dataset cell has 141 states/16
families. In the current 39-case campaign, the 3-day P1 window is 39/39 on 252
correlated states/7 authored families; 1/7-day windows remain 9/9 on 18/1. The
expanded window uses its actual support, never the old subset's totals.

Machine results are `metrics.json`, `failures.jsonl`, `predictions-*.jsonl`,
`semantic-*.json`, actual per-job timings and command records/logs. Every sealed
artifact is hashed; unexpected extra/missing files also fail. Provider calls are
zero; token count/provider cost are undefined because no model is invoked.
Reading time, lexical domain coverage and attributed statement-set material-change
proxies do not establish semantic truth or real user value.

See [PR5 review repair and fresh acceptance report](reports/PR5_REVIEW_FIXES.md) and
[G3 → G4 handoff](../../docs/G3_G4_HANDOFF.md). Offline PASS is not production
readiness, online integration, publication, independent human validation or a
real-user effect. G4 needs separate review and owner approval.
The original [PR5 acceptance report](reports/PR5_ACCEPTANCE.md) is historical and
preserved byte for byte. Its former PASS does not close the test-control finding;
fresh v2 evidence and the fixed-pin refusal must be independently reviewed.
