# G2-PR1 data dictionary

Contract source: `contracts.py`; generated JSON Schema: `schema/v1/`. The tables below enumerate
every G2 model field. G1 embedded models retain their frozen definitions and are not rewritten.
Every model is strict, frozen and extra=forbid; collections are tuples in Python and arrays in JSON.
Frozen models contain some dict-valued fields; entry points round-trip/copy all input, rather than
trusting mutable nested model instances. This is an in-process purity boundary, not a Python sandbox.
Temporal metadata is inspected before the round-trip, so an injected future object is rejected
before its body can be serialized. Strict full-schema validation still follows this early gate.

## Semantics and missing values

- ID is a nonempty string containing non-whitespace; SHA is lowercase 64-digit hex.
- Instant reuses G1's offset-aware parser and UTC Z serializer. available_at, never published_at,
  decides visibility. observed_at <= available_at <= as_of; equality is visible.
- `G2ReplayInput.context` is authoritative for timeline, step, as_of and persona. The full context
  is retained for synthetic replay audit; PR1 does not use persona prose to determine facts.
- `G2VisibleDocument` wraps the exact G1 candidate plus selected-version origin/rights/provenance.
  `visible_lineage` adds body-free VersionIdentity metadata, restricted to the current document
  and versions already available at as_of. IdentitySeed must equal the root of this lineage;
  the current candidate must be its latest version. An old anchor is not citable evidence.
- Sources describe allowed use, not independent semantic support. Permission mismatches reject
  the entire result; metadata-only material has no body. Existing G1 provenance checks run in
  the bridge. Pure input validation repeats body/hash/origin/rights checks without filesystem IO.
- PR1 produces no PredictedRelation records. Its schema independently supports the six explicit
  relation labels, ordered distinct candidate IDs, equal as_of, and an optional non-calibrated
  confidence in [0,1]. Relations are never read from G1 reference files.
- StableEventIdentity is one document lineage, not a solved real-world event. Subject is null,
  event_type unknown, lineage/related empty, previous/conflict null. PR2 owns real merges/splits.
- ClaimCandidate.statement is exactly the first paragraph prefix (<=160 raw Unicode code points).
  A whitespace-only prefix yields no Claim. claim_type=source_excerpt, scope=unknown,
  verification_state=unverified, support_check_status=not_evaluated. A truncated quote records
  excerpt_truncated. Neither a valid locator nor a source title proves the asserted capability.
- EvidenceRef requires a real current candidate and paragraph, a raw prefix and exact quote SHA.
  The schema permits supports/refutes/unknown for future use, but PR1 output accepts mentions only.
  Bundle supporting/refuting lists stay empty; source independence stays unknown.
- IntelligenceItem.headline is `来源材料：` + source title. what_happened is `来源段落摘录：` + quote,
  or null without a citable paragraph. why_it_matters is null; tier is hold; change_signal is unknown.
  attributed means the excerpt is located, never verified. claim_keys link to the bundle rather
  than storing a second, potentially drifting Claim summary. record_origin follows the document.
- coverage_gaps are explicit safe identifiers, including coverage_unknown when no windows exist.
  Empty results retain this explanation in DiagnosticReport.coverage_gaps. Unknown coverage is
  not zero news or no_change. semantic_support is always not_evaluated.
- GenerationTrace alone has generated_at/elapsed time. All model usage is 0 because no model is
  called; usage_reason=not_called, model_id=null. This differs from unknown usage after a call.
- Diagnostic issues contain closed error/stage enums and safe identifiers, not evidence/error text.
  `path`, when present, is a controlled relative POSIX path without sensitive components.

## Hash and version definitions

C(x) = json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).
H(x) = SHA256(UTF8(C(x))) without trailing LF. Persisted JSON has one terminal LF, so its raw
file hash is generally different. Nonempty JSONL has a terminal LF per record; empty JSONL is
zero bytes. UTF-8 has no BOM. Object keys sort; arrays have fixed pipeline ordering.

- input_sha256 = H(canonical G2ReplayInput), after restoring G1 candidate order and sorting sources/seeds.
- config_sha256 = H(G2Config including defaults). config_file_sha256 hashes the raw pinned config file.
- source_coverage_digest = H(context.source_coverage JSON array).
- event_key = `g2:event:` + H({identity_revision,dataset_id,timeline_id,anchor_document_id}).
- event_revision = H({event_key,members:[{doc_version_id,content_sha256}]}).
- quote_sha256 = SHA256(raw UTF-8 quote), without Unicode normalization or an added LF. G1 body
  content_sha256 retains its existing NFC/LF normalization; G2 does not change it.
- claim_key = `g2:claim:` + H({event_key,refs:[complete EvidenceRef],extractor_revision}).
- bundle_sha256 = H(bundle fields excluding bundle_id and bundle_sha256); bundle_id=`g2:bundle:`+SHA.
- content_revision = H(Item fields excluding item_id and content_revision), including as_of.
- item_id = `g2:item:` + H({event_key,content_revision,schema_revision}).
- run_id = `g2:run:` + H({input_sha256,config_sha256,pipeline_revision}).
- RunManifest hashes every semantic artifact's actual bytes and records code/schema/dependency/lock
  fingerprints. It excludes itself and Trace; Trace binds the manifest SHA. CLI stdout gives
  manifest and trace raw SHA. There is no self-hash/cycle and no digital-authenticity claim.

Main objects use g2-pr1-1. Config, identity, pipeline, manifest and diagnostic revisions are
independent, enumerated values. Unsupported revisions fail; no automatic interpretation/migration.
Future contract/hash changes require a new revision and preserved old material. All PR1 semantic
text is a fixed template or raw source data, not a model completion. G2-T01–T10 assert these rules.

## Failure codes

Error stages: input, bridge, identity, evidence, item, output, export. G1 errors retain their codes;
G2Error attaches a stage and field. Literal upgrades such as hold→focus or unverified→supported
are G2_PLACEHOLDER_STATUS_INVALID; wrong versions are UNSUPPORTED_REVISION. A validation failure
publishes no result directory. CLI argument errors exit 2; other failures produce safe JSON/exit 1.

The field inventory below includes the complete closed ValidationIssue.code enum. Common groups:

| Concern | Codes |
|---|---|
| Structure | INVALID_JSON, SCHEMA_INVALID, UNSUPPORTED_REVISION, DUPLICATE_ID |
| Integrity | MANIFEST_SHA_MISMATCH, SHA_MISMATCH, RUNTIME_CODE_MISMATCH, CONFIG_SHA_MISMATCH, CONFIG_NOT_PINNED, G2_INPUT_NOT_FROZEN |
| Time | NAIVE_DATETIME, INVALID_DATETIME, AVAILABLE_BEFORE_OBSERVED, FUTURE_VERSION, FUTURE_PERSONA, FUTURE_EXPOSURE, FUTURE_COVERAGE, FUTURE_DELIVERY |
| Set/identity | VISIBLE_SET_MISMATCH, GROUP_MEMBERS_INVALID, G2_CONTEXT_MISMATCH, G2_IDENTITY_SEED_INVALID |
| Source/use | SOURCE_NOT_FOUND, SOURCE_TYPE_MISMATCH, ORIGIN_MISMATCH, PROVENANCE_INVALID, RIGHTS_USE_NOT_ALLOWED, RIGHTS_UNKNOWN_FULLTEXT |
| Citation/template | CITATION_NOT_FOUND, G2_EVIDENCE_NOT_IN_EVENT, G2_QUOTE_MISMATCH, G2_PLACEHOLDER_STATUS_INVALID |
| Paths/IO | MANIFEST_PATH_INVALID, PREDICTION_PATH_INVALID, OUTPUT_PATH_INVALID, OUTPUT_EXISTS, EXPORT_IO_ERROR |

Additional G1 loader/split/history codes remain listed in the schema and are propagated unchanged.
Diagnostics do not include raw ValidationError input, provider messages, API keys or private goals.

## Fixture and review provenance

fixtures/pr1/v1 cases are authored synthetic development expectations. record_origin=synthetic
describes material; label_origin=synthetic_fixture and review_origin=ai_development describe the
development process. Draft and review have actual creation times, model_id=unknown, input SHA,
non_blind=true and disclosed context. No human gold, invented disagreement, second-human signoff,
kappa or independent research is claimed. Only tests read expected outcomes. Runtime G2 never
loads the fixture cases/review or G1 reference labels. Permission-negative tests simulate real-origin
metadata contracts; they do not collect or independently authenticate real historical sources.

## Field inventory

### G2Config

| Field | JSON type / values | Default |
|---|---|---|
| `config_revision` | 'g2-config-v1' | 'g2-config-v1' |
| `pipeline_revision` | 'g2-pr1-rule-v1' | 'g2-pr1-rule-v1' |
| `identity_revision` | 'g2-document-lineage-v1' | 'g2-document-lineage-v1' |
| `event_strategy` | 'single_document_lineage_v1' | 'single_document_lineage_v1' |
| `claim_strategy` | 'paragraph_excerpt_v1' | 'paragraph_excerpt_v1' |
| `generator_revision` | 'hold_stub_v1' | 'hold_stub_v1' |
| `max_quote_chars` | 160 | 160 |

### G2ReplayInput

| Field | JSON type / values | Default |
|---|---|---|
| `schema_revision` | 'g2-pr1-1' | 'g2-pr1-1' |
| `dataset_id` | string | required |
| `dataset_revision` | string | required |
| `input_manifest_sha256` | SHA256 | required |
| `context` | ReplayContext | required |
| `visible_documents` | array[G2VisibleDocument] | required |
| `sources` | array[G2SourcePolicy] | required |
| `identity_seeds` | array[IdentitySeed] | required |
| `source_coverage_digest` | SHA256 | required |
| `pipeline_revision` | 'g2-pr1-rule-v1' | required |
| `config_sha256` | SHA256 | required |

### PredictedRelation

| Field | JSON type / values | Default |
|---|---|---|
| `schema_revision` | 'g2-pr1-1' | 'g2-pr1-1' |
| `left_doc_version_id` | string | required |
| `right_doc_version_id` | string | required |
| `predicted_relation` | exact_duplicate / syndicated / same_event_different_evidence / related_distinct_event / unrelated / uncertain | required |
| `method` | string | required |
| `evidence_reasons` | array[string] | required |
| `as_of` | Instant (UTC) | required |
| `confidence` | number >= 0 <= 1 or null | None |

### StableEventIdentity

| Field | JSON type / values | Default |
|---|---|---|
| `schema_revision` | 'g2-pr1-1' | 'g2-pr1-1' |
| `event_key` | string | required |
| `identity_revision` | 'g2-document-lineage-v1' | required |
| `first_visible_at` | Instant (UTC) | required |
| `anchor_doc_version_id` | string | required |
| `canonical_subject` | string or null | None |
| `event_type` | 'unknown' | 'unknown' |
| `member_doc_version_ids` | array[string] (nonempty) | required |
| `related_event_keys` | array[string] | [] |
| `previous_identity_key` | string or null | None |
| `identity_conflict` | string or null | None |
| `merge_lineage` | array[string] | [] |
| `event_revision` | SHA256 | required |

### ClaimCandidate

| Field | JSON type / values | Default |
|---|---|---|
| `schema_revision` | 'g2-pr1-1' | 'g2-pr1-1' |
| `claim_key` | string | required |
| `event_key` | string | required |
| `statement` | string | required |
| `claim_type` | 'source_excerpt' | 'source_excerpt' |
| `asserted_by` | string | required |
| `scope` | 'unknown' | 'unknown' |
| `evidence_refs` | array[EvidenceRef] (nonempty) | required |
| `verification_state` | 'unverified' | 'unverified' |
| `support_check_status` | 'not_evaluated' | 'not_evaluated' |
| `limitations` | array[string] | required |
| `extractor_revision` | 'paragraph_excerpt_v1' | 'paragraph_excerpt_v1' |

### EvidenceRef

| Field | JSON type / values | Default |
|---|---|---|
| `doc_version_id` | string | required |
| `paragraph_id` | string | required |
| `quote` | string | required |
| `quote_sha256` | SHA256 | required |
| `direction` | mentions / unknown / supports / refutes | required |

### EvidenceBundle

| Field | JSON type / values | Default |
|---|---|---|
| `schema_revision` | 'g2-pr1-1' | 'g2-pr1-1' |
| `bundle_id` | string | required |
| `event_key` | string | required |
| `as_of` | Instant (UTC) | required |
| `status` | 'placeholder' | 'placeholder' |
| `doc_version_ids` | array[string] (nonempty) | required |
| `claim_candidates` | array[ClaimCandidate] | required |
| `source_lineage` | array[SourceLineage] | required |
| `supporting_refs` | array[EvidenceRef] | [] |
| `refuting_refs` | array[EvidenceRef] | [] |
| `unverified_refs` | array[EvidenceRef] | required |
| `coverage_gaps` | array[string] | required |
| `uncertainties` | array[string] | required |
| `bundle_sha256` | SHA256 | required |

### IntelligenceItem

| Field | JSON type / values | Default |
|---|---|---|
| `schema_revision` | 'g2-pr1-1' | 'g2-pr1-1' |
| `item_id` | string | required |
| `content_revision` | SHA256 | required |
| `event_key` | string | required |
| `event_revision` | SHA256 | required |
| `bundle_id` | string | required |
| `as_of` | Instant (UTC) | required |
| `headline` | string | required |
| `what_happened` | string or null | required |
| `why_it_matters` | string or null | None |
| `claim_keys` | array[string] | required |
| `evidence_refs` | array[EvidenceRef] | required |
| `evidence_status` | attributed / insufficient | required |
| `uncertainties` | array[string] | required |
| `tier_candidate` | 'hold' | 'hold' |
| `change_signal` | 'unknown' | 'unknown' |
| `generator` | 'rule' | 'rule' |
| `generator_revision` | 'hold_stub_v1' | 'hold_stub_v1' |
| `source_coverage` | array[CoverageWindow] | required |
| `record_origin` | real / synthetic | required |

### GenerationTrace

| Field | JSON type / values | Default |
|---|---|---|
| `schema_revision` | 'g2-pr1-1' | 'g2-pr1-1' |
| `run_id` | string | required |
| `input_sha256` | SHA256 | required |
| `run_manifest_sha256` | SHA256 | required |
| `generated_at` | Instant (UTC) | required |
| `execution_ms` | number >= 0 | required |
| `stage_revisions` | map[string, string] | required |
| `model_id` | null | None |
| `model_calls` | 0 | 0 |
| `token_usage` | 0 | 0 |
| `model_cost` | 0 | 0 |
| `usage_reason` | 'not_called' | 'not_called' |
| `degradation` | 'placeholder' | 'placeholder' |
| `errors` | array[ValidationIssue] | [] |
| `validation_ok` | boolean | required |

### G2Result

| Field | JSON type / values | Default |
|---|---|---|
| `schema_revision` | 'g2-pr1-1' | 'g2-pr1-1' |
| `run_id` | string | required |
| `input_sha256` | SHA256 | required |
| `timeline_id` | string | required |
| `step_id` | string | required |
| `as_of` | Instant (UTC) | required |
| `relations` | array[PredictedRelation] | required |
| `events` | array[StableEventIdentity] | required |
| `bundles` | array[EvidenceBundle] | required |
| `items` | array[IntelligenceItem] | required |
| `validation` | DiagnosticReport | required |

### DiagnosticReport

| Field | JSON type / values | Default |
|---|---|---|
| `report_revision` | 'g2-validation-v1' | 'g2-validation-v1' |
| `ok` | boolean | required |
| `counts` | map[string, integer >= 0] | required |
| `coverage_gaps` | array[string] | [] |
| `errors` | array[ValidationIssue] | [] |
| `warnings` | array[ValidationIssue] | [] |
| `semantic_support` | 'not_evaluated' | 'not_evaluated' |

### RunManifest

| Field | JSON type / values | Default |
|---|---|---|
| `manifest_revision` | 'g2-manifest-v1' | 'g2-manifest-v1' |
| `run_id` | string | required |
| `dataset_id` | string | required |
| `dataset_revision` | string | required |
| `g1_schema_revision` | string | required |
| `input_manifest_sha256` | SHA256 | required |
| `schema_revision` | 'g2-pr1-1' | 'g2-pr1-1' |
| `pipeline_revision` | 'g2-pr1-rule-v1' | 'g2-pr1-rule-v1' |
| `config_revision` | 'g2-config-v1' | 'g2-config-v1' |
| `config_file_sha256` | SHA256 | required |
| `config_sha256` | SHA256 | required |
| `git_sha` | string | required |
| `runtime_source_sha256` | map[string, SHA256] | required |
| `schema_sha256` | map[string, SHA256] | required |
| `dependency_lock_sha256` | map[string, SHA256] | required |
| `python_version` | string | required |
| `dependency_versions` | map[string, string] | required |
| `input_sha256` | SHA256 | required |
| `context_sha256` | SHA256 | required |
| `candidate_sha256` | SHA256 | required |
| `source_coverage_digest` | SHA256 | required |
| `artifacts` | array[ArtifactDigest] | required |
| `validation_scope` | 'pr1_contract_skeleton' | 'pr1_contract_skeleton' |

### G2VisibleDocument

| Field | JSON type / values | Default |
|---|---|---|
| `candidate` | CandidateDocumentVersion | required |
| `record_origin` | real / synthetic | required |
| `redistribution_rights` | permitted / excerpt_only / metadata_only / unknown / synthetic | required |
| `provenance_uri` | string | required |
| `visible_lineage` | array[VersionIdentity] (nonempty) | required |

### G2SourcePolicy

| Field | JSON type / values | Default |
|---|---|---|
| `source_id` | string | required |
| `source_type` | official / paper / repository / independent_test / media / community / other | required |
| `record_origin` | real / synthetic | required |
| `redistribution_rights` | permitted / excerpt_only / metadata_only / unknown / synthetic | required |
| `allowed_use` | array[metadata / excerpt / fulltext] (nonempty) | required |
| `max_excerpt_chars` | integer or null | required |

### IdentitySeed

| Field | JSON type / values | Default |
|---|---|---|
| `document_id` | string | required |
| `anchor_doc_version_id` | string | required |
| `first_visible_at` | Instant (UTC) | required |

### VersionIdentity

| Field | JSON type / values | Default |
|---|---|---|
| `doc_version_id` | string | required |
| `document_id` | string | required |
| `available_at` | Instant (UTC) | required |
| `supersedes_version_id` | string or null | required |
| `content_sha256` | SHA256 or null | required |

### SourceLineage

| Field | JSON type / values | Default |
|---|---|---|
| `doc_version_id` | string | required |
| `source_id` | string | required |
| `upstream_document_id` | string or null | required |
| `independence` | 'unknown' | 'unknown' |

### ValidationIssue

| Field | JSON type / values | Default |
|---|---|---|
| `code` | INVALID_JSON / SCHEMA_INVALID / UNSUPPORTED_REVISION / DUPLICATE_ID / MANIFEST_SHA_MISMATCH / SHA_MISMATCH / RUNTIME_CODE_MISMATCH / CONFIG_SHA_MISMATCH / CONFIG_NOT_PINNED / NAIVE_DATETIME / INVALID_DATETIME / AVAILABLE_BEFORE_OBSERVED / FUTURE_VERSION / FUTURE_PERSONA / FUTURE_EXPOSURE / FUTURE_COVERAGE / FUTURE_DELIVERY / VISIBLE_SET_MISMATCH / GROUP_MEMBERS_INVALID / G2_CONTEXT_MISMATCH / G2_IDENTITY_SEED_INVALID / SOURCE_NOT_FOUND / SOURCE_TYPE_MISMATCH / ORIGIN_MISMATCH / PROVENANCE_INVALID / RIGHTS_USE_NOT_ALLOWED / RIGHTS_UNKNOWN_FULLTEXT / CITATION_NOT_FOUND / G2_EVIDENCE_NOT_IN_EVENT / G2_QUOTE_MISMATCH / G2_PLACEHOLDER_STATUS_INVALID / MANIFEST_PATH_INVALID / PREDICTION_PATH_INVALID / OUTPUT_PATH_INVALID / OUTPUT_EXISTS / EXPORT_IO_ERROR / RECORD_COUNT_MISMATCH / UNLISTED_INPUT / CROSS_FAMILY_SPLIT / REFERENCE_NOT_FOUND / FUTURE_EVIDENCE / VERSION_CHAIN_INVALID / VERSION_CONFLICT / DUPLICATE_CONTENT_VERSION / INVALID_INTERVAL / SOURCE_NOT_ALLOWED / HISTORY_TARGET_NOT_FOUND / HISTORY_SNAPSHOT_INVALID / G2_INPUT_NOT_FROZEN / FAMILY_NOT_FOUND / DELIVERY_SCOPE_INVALID / FUTURE_OR_STALE_HISTORY_VERSION / HISTORY_SNAPSHOT_MISMATCH / HISTORY_PREDICTION_ID_MISMATCH | required |
| `stage` | input / bridge / identity / evidence / item / output / export | required |
| `field` | string | '' |
| `record_id` | string or null | None |
| `path` | string or null | None |

### ArtifactDigest

| Field | JSON type / values | Default |
|---|---|---|
| `path` | string | required |
| `sha256` | SHA256 | required |
| `byte_count` | integer >= 0 | required |
| `record_count` | integer >= 0 or null | required |

## Example: synthetic single-document hold Item

This is an authored synthetic source excerpt, not real news or a verified capability.

```json
{
  "as_of": "2026-01-01T12:00:00Z",
  "bundle_id": "g2:bundle:156cea381777a55ddc006daa6d02d061c1414bf712e2e8dc3382891bf3d79037",
  "change_signal": "unknown",
  "claim_keys": [
    "g2:claim:4dcca1374c1fbf9c404c0c57a67348568e6e7ad1d949af61b6b17bebcc444ab8"
  ],
  "content_revision": "a01c95c208b0fa740571a2cea52fb314a06779ed35ecf951695d31f47da325fc",
  "event_key": "g2:event:c8408492db4e85d11fdfb754f1c24eca1cf41e4fdc62c504bdf0ec4eb8fd2298",
  "event_revision": "3660d92d8499c700eea27fc9ea0d3668c90cb7f724b7003b63fe3e9c3e9a12ab",
  "evidence_refs": [
    {
      "direction": "mentions",
      "doc_version_id": "d01:a:1",
      "paragraph_id": "p1",
      "quote": "Cedar Agent v1.0 is released today. This announcement reports availability, not independent testing.",
      "quote_sha256": "ad4df3e4e34b074e412d382e8a89761adf6173c03c68c7ce73657bf34c525667"
    }
  ],
  "evidence_status": "attributed",
  "generator": "rule",
  "generator_revision": "hold_stub_v1",
  "headline": "来源材料：Cedar Agent v1.0 release",
  "item_id": "g2:item:d638dfb4eea248059eb9ab69b37dcd0af626e242419cb6f17ab06e8767c81ef6",
  "record_origin": "synthetic",
  "schema_revision": "g2-pr1-1",
  "source_coverage": [],
  "tier_candidate": "hold",
  "uncertainties": [
    "pr1_placeholder",
    "semantic_support_not_evaluated",
    "observed_sources_only"
  ],
  "what_happened": "来源段落摘录：Cedar Agent v1.0 is released today. This announcement reports availability, not independent testing.",
  "why_it_matters": null
}
```

## PR2 versioned contracts (g2-pr2-1)

PR2 lives in pr2/ and schema/v2; it never broadens the g2-pr1-1 validator. Every object is strict,
frozen, extra-forbid. UTC Instant, nonblank IDs, lowercase SHA-256 and canonical serialization
retain PR1 meanings. Config= g2-pr2-config-v1; features= g2-event-features-v1;
relations= g2-relations-v1; identity= g2-event-registry-v1. Exact field/type definitions are in
the generated schemas; the following adds semantics and hash material.

| Record | Fields and meanings |
|---|---|
| GroupingInput | Checked PR1 replay_input; strategy r0/r1/r2; grouping_config_sha256; ReplayCursor; nullable previous_state and matching semantic-object SHA. PR1 config_sha256 inside replay_input is a separate pin. |
| ReplayCursor | timeline_id, step_id, UTC as_of, zero-based ordinal, nullable previous_step_id. The CLI supplies the complete registered prefix. |
| DocumentEventFeatures | doc_version_id/document_id; available_at/published_at; normalized canonical_url; current content SHA; visible upstream; canonical_subject and subject_candidates; ambiguous; target_version/link; event_type/action/action_object; material_role; explicit event_date; hashed title/body token sets; copy_cue; FeatureRef list. No family, reference group or source-name guessing. |
| FeatureRef | Original version, title/URL/upstream/paragraph field, optional paragraph_id, H(original field string), available_at. Historical identity-only inheritance retains old refs; it does not make old paragraphs current citations. |
| PairDecision | Ordered distinct current IDs; six-class predicted_relation; as_of; relation revision/rule/reasons; feature refs; cannot_link reasons; actual [0,1] title/body Jaccard; confidence must be null. R0 has no six-way pair decisions. |
| GroupingPartition | Exact nonoverlapping candidate partition; optional original R0 group IDs; blocked merges with offending cross-pairs. An uncertain edge does not authorize merging. |
| EventSnapshot | Registered key/revision; created_at; immutable birth anchor; canonical subject/type/version/action/object/date; current members; related keys; lineage IDs. Unknown descriptors are null/unknown; no factual summary. |
| RegisteredEvent | Key, created_at, immutable anchor, active/dormant/merged/retired_split status, last visible identity-feature prototypes, lineage IDs. Dormant prototypes may support identity, never enlarge the current candidate pool. |
| IdentityTransition | ID, birth/merge/split/complex/reactivate kind, parents/successors, effective_at/step, current trigger versions, reasons, prior semantic-state SHA. Corrections take effect when observed, not backdated to an event date. |
| AliasRecord | alias key, successor keys, created/retired, effective_at, transition ID. Original entries stay unchanged; retirement is an additional record. |
| EventView | Exactly one representative per current event; every member/source pointer; independence unknown; duplicate_or_reprint is text dependency, not external verification. Compatibility links map original PR1 document keys at this as_of, not historical item redirects. |
| IdentityState | Dataset/timeline/strategy namespace; versions/config/input pin; cursor and predecessor audit SHA; registry, transitions and alias history. No database or external state recovery. |
| GroupingResult | Input digest, cursor/strategy, features/relations/partition/events/views/transitions, next_state and contract diagnostic. Does not generate PR3 Claims or EvidenceBundles. |
| PR2RunManifest / PR2Trace | Raw artifact/code/schema/lock/config pins and candidate/context pool digest; real time/latency only in Trace. Trace binds manifest bytes; calls/tokens/cost=0, not_called. |

Feature grammar is deliberately narrow: a scoped vN/version N or release tag, explicit Target:
or release URL, title action/object and declared Event date. ABI/hardware/baseline versions do not
become target versions. Different explicit product names remain cannot-link even in one monorepo.
Shared repository/release anchors can connect languages; ungrounded translations are not invented.
Current upstream target propagation requires compatible subject/target and an identifiable material
role; inherited values preserve provenance. A negated testing mention is not an experiment cue.

Relations: exact_duplicate = nonnull equal URL+hash; syndicated = compatible visible copy lineage
or constrained R2 near-copy; same_event_different_evidence = explicit compatible target;
related_distinct_event/unrelated prohibit merging; uncertain abstains. Document measurement or
correction role differs from target event type. Self-described independence remains unknown.

R2 thresholds: title>=0.60, body>=0.80, >=12 tokens/side, <=14 days inclusive, explicit same target
version or date, compatible subject/action/object. Near-copy additionally title>=0.90/body>=0.98
and copy cue. R1 is default. R0 grouping config/source stays pinned and unmodified.

### PR2 hashes and historical resolution

- namespace = H({dataset_id,timeline_id,strategy,identity_revision}); excludes dataset revision,
  persona and whole-bundle pin. Normal birth key = g2:event: + H({namespace,birth_anchor_doc_version_id,
  birth_kind:new}). Store once, never recompute on membership changes.
- Split/complex children add split_transition_id and their birth anchor. Transition ID binds only
  that component's visible feature observations, parent keys, kind, namespace and effective as_of;
  it excludes unrelated groups, whole-bundle pin and real execution time.
- event_revision = H({event_key,current sorted features,current intra-event pair labels/rules,
  related_event_keys,lineage_ids,feature/relation/identity revisions}). Pair as_of is excluded.
- Full state digest H(IdentityState) is the predecessor audit binding. identity semantic-state
  digest excludes input_manifest_sha256/previous_state_sha256; audit pins cannot feed event keys.
- GroupingInput and run/artifact hashes bind pins for reproducibility; changing a future file may
  change those audit digests while past clustering/key/revision remain identical.
- Alias lookup requires as_of and detects cycles/missing targets. Merge chooses earliest created
  key then lexical key. Split retires the parent and all aliases reaching it, with explicit multiple
  successors. Exact historical item/key/revision/snapshot lookup never follows current aliases.

### PR2 diagnostics and development metrics

New codes: G2_PR2_PAIR_SET_INVALID (relations/grouping), G2_PR2_FEATURE_PROVENANCE_INVALID
(features/relations), G2_PR2_CANNOT_LINK_VIOLATION (grouping), G2_PR2_STATE_CHAIN_INVALID,
G2_PR2_HISTORY_FUTURE, G2_PR2_IDENTITY_GRAPH_INVALID, G2_PR2_REVISION_MISMATCH (identity),
G2_PR2_COMPARISON_POOL_MISMATCH, G2_PR2_REFERENCE_CONFLICT (evaluation). G1/PR1 codes stay
unchanged. Errors contain code/stage/field/record ID, never raw exceptions or source prose.

Evaluation reads separately pinned ReferencePair and ContinuityReference records after verifying
prediction artifacts. First three relations are binary positives; related/unrelated are negatives;
reference uncertain/missing is unscored. Precision/recall/F1 use explicit zero-denominator nulls.
Clustering FP/FN differ from relation confusion: complete linkage can block a positive pair.
Repeated step-pair observations and unique pairs are both reported. Historical continuity cases
have frozen expectations; legal lineage operations and unexplained key changes are separate.

errors.jsonl includes case/timeline/step/as_of, input/config/code/reference SHA, pair, predicted and
reference relation/group, rule/refs/cannot-link/blocked merge, old/new key/revision/transition,
FP/FN and root-cause hint, impact, optional proposed rule/counterexample/retest, provenance and
non-blind disclosure. A root-cause hint is a rule diagnostic, not independent causal research.

## PR3 / g2-pr3-1

Schema v3 is additive; v1/v2 retain their original meanings. PR3Config freezes whole-paragraph
granularity and versions for extractor/scope/relations/history. Limits: 256 documents, 4096
paragraphs, 1048576 visible codepoints, 1024 quote codepoints (also source-limited), 32 claims/doc,
128 claims/event, 32768 comparisons/step and 4096 archived claims. Step budgets fail; long or
sensitive paragraphs are skipped whole with gaps. No prefix claim, redacted quote or model call.

| Record | Field meanings |
|---|---|
| Citation | ref_id, version/document/paragraph, source, available_at, content hash, origin, full raw quote and SHA; start=0/end=len(quote), Python Unicode codepoints |
| GroundedValue | raw substring, normalized string or null, Citation ref/start/end; normalization revision is pinned |
| ClaimScope | task/dataset/baseline/protocol/hardware/target_version with grounded values, conditions and explicit unknown dimensions; unknown is not a wildcard |
| Proposition | grounded subject/action/metric, quantities with raw/norm value, unit and quantifier, positive/negative/unknown polarity and ambiguity |
| ClaimCandidate | immutable claim_key, birth event/time, version, exact statement, claim type, publisher/asserted-by attribution, scope/proposition, origin refs, limitations, marker and origin |
| EvidenceLink | target/evidence Claim and citation, supports/refutes/mentions/unknown, inference basis/rule, scope comparison and rule_checked/not_evaluated; self-excerpts are mentions |
| SourceLineage | source/version/upstream, cites/copy/duplicate/unknown, dependency group and dependent/unknown independence; no independence by source name or missing upstream |
| ClaimAssessment | claim/current event/as_of, source_attributed/disputed/unverified/retracted state (independently_supported forbidden), current/historical/superseded/retracted lifecycle, links and zero confirmed independent support |
| ClaimTransition | explicit same-source, uniquely targeted corrects/retracts; effective time, old/new Claim and trigger refs; prior transitions never rewritten |
| ClaimMembership | append-only current event assignment using visible document lineage or unique PR2 identity successor; Claim birth event remains unchanged |
| EvidenceState | namespace/config/cursor/prior SHA, immutable claims/quotes, appended transitions/memberships/assessments, bound PR2 identity-state SHA |
| EvidenceBundle | inherited event key/revision, as_of/current members, current/historical Claim IDs, assessments/lineage/links/conflicts/gaps, assembled/insufficient and full payload hash |

claim_key hashes dataset ID, immutable version, paragraph/quote SHA and extraction/scope revision;
it excludes event membership, assessment, as_of and whole-run pin. Citation IDs hash all citation
fields except their own ID. Bundle SHA covers the serialized snapshot except its own SHA/ID;
bundle ID derives from that SHA. File SHA uses actual bytes; semantic digest excludes a trailing LF.

Structured scope uses explicit task/dataset/baseline/protocol/hardware/conditions markers and
paragraph-bound subject/version grammar. Missing/ambiguous values stay unknown. Narrow reported
speed-gain comparisons require the same explicit scope; nonexclusive numbers alone are not a
conflict. Unsupported negation, multiple quantities/subjects and ratio semantics abstain. Scope
and numeric fields never come from a title or a research label. Secondary summaries are mentions,
unverified and do not supply normalized experimental quantities. Missing cleaning metadata stays
unknown; only a visible omission marker establishes a specific table gap.

Validation orders time metadata, strict input/parent/state verification, current event membership,
raw quote/spans/SHA, grounded fields, then relation/status/history checks. Historical quotes are
context only. Common time/hash/rights/path errors retain their original codes. PR3-specific codes:
G2_PR3_PARENT_RUN_MISMATCH, G2_PR3_EVIDENCE_NOT_IN_EVENT, G2_PR3_HISTORICAL_REF_AS_CURRENT,
G2_PR3_SPAN_MISMATCH, G2_PR3_FIELD_PROVENANCE_INVALID, G2_PR3_UNSUPPORTED_DIRECTION,
G2_PR3_STATUS_INVALID, G2_PR3_STATE_CHAIN_INVALID, G2_PR3_HISTORY_FUTURE,
G2_PR3_LINEAGE_INVALID, G2_PR3_BUDGET_EXCEEDED and G2_PR3_REFERENCE_CONFLICT.
Issues expose only code/stage/field/record ID, not raw source or exception text.

Runtime diagnostics separately report locator/rule-contract validation and unevaluated AI/independent
review. Post-prediction reference comparison reports extraction, type/state/direction confusion,
scope field retention, numeric fidelity and required-gap recall with real denominators. These are
non-blind ai_development metrics, not independent semantic or real-world quality evidence. Full
source-attribution AI review is recorded separately; underlying truth is not_evaluated.

## PR4 — g2-pr4-1

Strict/frozen/extra-forbid models use UTC, tuples, nonblank IDs and lowercase SHA256. Unknown facts
are null; illegal enum/status/extra fields fail. Code, config, template and policy revisions are
g2-rule-items-v1, g2-pr4-config-v1, g2-zh-templates-v1 and g2-candidate-tier-v1. Breaking field,
enum, budget, hash or template semantics require new revisions and preserved old schemas/fixtures.

| Model | Fields / semantics |
|---|---|
| GenerationInput | namespace, cursor, events, source_coverage, coverage_gaps, previous_state, previous_state_sha256, config_sha256. Persona-free evidence projection; cursor is the sole as_of. |
| EventEvidenceView | unchanged PR3 bundle; authorized current/historical claims and citations; verified lifecycle transitions; source_pointers; PR2 lineage_ids and predecessor_event_keys. |
| SourcePointer | doc_version_id, document_id, source_id, canonical_url nullable, available_at, content_sha256 nullable, content_kind, origin, rights, provenance_uri, source policy. Metadata captured when actually visible; it grants no new text access. |
| FactText | text, template_id, ordered claim_keys, bindings. Only exact template reconstruction passes. |
| Binding | slot, claim_key, field, ref_id, start, end, value. Statement binding is the entire exact original paragraph span; publisher_source_id binding uses a zero-width (0,0) metadata anchor checked against Claim/Citation.source_id. No title-derived experimental values. |
| ClaimSummary | claim_key, statement FactText, attribution source ID, original scope, verification_state, lifecycle, ref_ids, limitations. No independent_support upgrade. |
| Inference | text, kind=inference, fixed rule_id, premise_claim_keys, limitations. Conditional same-scope evaluation only for complete measured scope; explicitly prefixed 推断. |
| RiskNote | fixed code/text, basis_type and basis_ids. Basis: claim_status/conflict/coverage/permission/budget. Radar notes render together as one cautions sentence. |
| IntelligenceItem | item_id, content_revision, fact_revision, event_key/event_revision; headline/what_happened FactText nullable, why_it_matters Inference nullable; claim_summaries; selected/omitted claim_keys; evidence_ref_ids/source_pointers; evidence_status attributed/disputed/insufficient; risks/uncertainties/source_coverage; tier_candidate focus/radar/hold, tier_reason_codes; status_text nullable; estimated_read_seconds; fixed reading_cost_basis/generator/revisions; record_origin. |
| ItemSnapshot | snapshot_id, item_id, event_key, as_of, bundle_id/SHA, change_signal, previous_snapshot_ids, lineage_ids. Signals first_observed/content_changed/same_content_observed/identity_transition describe this observation, never user knowledge or world novelty. |
| SnapshotState | namespace/config_sha256/cursor/previous_state_sha256; source_metadata without bodies; append-only snapshots. Same-event and all explicit merge/split parents are linked. |
| GenerationRequest | selected approved claims/assessments/citations/transitions, mode, required_risks, max_visible_chars. No tool/path/Persona/identity allocation API. |
| GenerationDraft | headline/what_happened/why_it_matters/claim_summaries. The rule adapter cannot assign event/status/tier. |
| GenerationResult | cursor, items, snapshots, minimal necessary citations, next_state, validation. |
| Diagnostic/Issue | ok, counts, errors, coverage_gaps; independent_validation/semantic_truth=not_evaluated. Issue is fixed code + stage + field + record_id, with no raw text or raw exception. |
| RunManifest | parent pin/path/prefix, raw config-file and semantic config hashes, Git SHA, runtime/schema/lock hashes, dependency versions, selected-input semantic hash and raw artifact byte hashes/counts. Validation scope is pr4_deterministic_candidate_items. |
| GenerationTrace | manifest raw-byte SHA, actual UTC generated_at, execution_ms; model_calls/token_usage/model_cost=0, model_id=null, reason=not_called, degradation=rule_templates. |

`record_origin=synthetic` requires all source pointers synthetic; a mixed/real evidence view is marked
real without implying validation. AI fixture/reference/review provenance is separate from source origin.
The synthetic feed-summary positive control is contract-only, not an accepted G1 source bundle.

Fact revision hashes headline/body, scope/status-bearing summaries, selected claims, citations and
evidence status. It excludes tier, inference, actual time and Persona. Content revision hashes the
complete item semantics except derived ID/hash fields; event_revision, source metadata, risk/tier
and template revision are included. No as_of or parent file pin is included. Item ID hashes
event_key + content_revision + schema revision. Snapshot ID hashes item_id + UTC as_of + bundle SHA.
Each semantic digest uses canonical JSON without LF; file digests hash exact stored UTF-8/LF bytes.
Source intervals are unioned per paragraph/document for quotation allowance; repeated templates do
not multiply the exported quote bytes. Visible characters conservatively count repeated detail text.

Tier reasons: grounded_complete_scope_or_release, attributed_limited_evidence,
validated_lifecycle_transition, two_sided_reported_conflict; hold reasons: no_citable_claim,
ambiguous_proposition, unresolved_lifecycle_target, sensitive_evidence, quote_permission_denied,
quote_allowance_exceeded, mandatory_claims_exceed_limit, radar_sentence_limit, visible_budget_exceeded.
These are evidence/presentation conditions, not importance scores or personalized ranking.

New fixed diagnostic codes:
G2_PR4_PARENT_RUN_MISMATCH, G2_PR4_FACT_PROVENANCE_INVALID, G2_PR4_INFERENCE_IN_FACT,
G2_PR4_SCOPE_RISK_MISSING, G2_PR4_LIFECYCLE_INVALID, G2_PR4_DUPLICATE_EVENT,
G2_PR4_TIER_INVALID, G2_PR4_BUDGET_EXCEEDED, G2_PR4_SNAPSHOT_CHAIN_INVALID,
G2_PR4_HISTORY_FUTURE, G2_PR4_REFERENCE_CONFLICT.
Time/hash/rights/path and parent PR3 codes are preserved. Schema-invalid statuses map to
SCHEMA_INVALID rather than PR1's placeholder-status code. Validation order: time preflight;
parent/source/schema/pin/state validation; original quote/field provenance and lifecycle target;
template bindings; required risks/tier/permission/budget; identity and snapshot reconstruction.


## PR5 schema g2-pr5-1

`ExpressionInput`: validated PR4 generation input/result/config, mode, pinned PR5 configuration and append-only prior expression state. No Persona or Goal. `ExpressionRequest`: immutable Item/event/fact revisions, cutoff, approved Claim/Citation/risk projection, allowed mode/style and visible budget; request SHA excludes its own field. Citation identity uses ref/document/paragraph/span/quote SHA and availability.

`ClosedDraft` contains only style ID, exact approved claim order, citation records, headline and body. `FreeDraft` is never selected. Full JSON Schema validation forbids extra fields, duplicate JSON keys and NaN. Numeric/scope checks are necessary but insufficient: accepted text must exactly reconstruct a versioned closed style with original bound statements. Historical citations are authorized only by the verified PR4 event view.

`IntelligencePresentation` retains the original PR4 Item byte-equivalent as `base_item`, event_key/event_revision/fact_revision, selection (`rule|mock_closed`) and new expression identity. Content digest binds parent Item, expression and style; excludes as_of, elapsed time, request errors and parent run pin. `ExpressionSnapshot` binds expression, original rule snapshot and cutoff, with predecessor/lineage links.

`ExpressionAssessment`: separate locator/numeric_scope/closed_render outcomes; semantic_truth remains not_evaluated. `SafeDraft`: synthetic-only, not_selected/not_verified. `ExpressionState`: namespace/config/mode/cursor, prior hash, cumulative pre-reserved call/request/response budgets, immutable snapshot prefix. All amounts are nonnegative; repeated IDs fail.

`AttemptTrace`/`ExpressionTrace`: fixed status/error codes, internal IDs/hashes, numerical budgets/times, allowlisted mock usage and its origin. external_requests/model_calls/billed_cost are literal zero; absent usage/input tokens are null, not zero. No raw Prompt/response/reasoning/header/exception text is logged.

Error families: configuration/network-disabled; simulated HTTP/auth/quota/rate-limit/connection/timeout; envelope/JSON/schema/size/truncation/filter/tool-call; citation/time/span/numeric/scope/attribution/closed-render/sensitive-output; budgets/cancellation/staleness; parent/output/state/reference integrity. Diagnostics assert code, stage and field; public unknown record IDs are hashed. Fatal parent/input errors abort; model/guard failures fall back; cancellation/staleness abort.

Versioned Prompt and ten styles live under fixtures/pr5/v1/prompt/ for existing exact-byte Git protection. Mock scripts are pinned data indexed by request SHA, with deterministic SHA-based default styles; development references/reviews are never loaded by prediction. No provider, DB or key loader is imported.


## PR6 release / campaign / acceptance

Version: g2-pr6-1; campaign g2-pr6-campaign-v1. Strict frozen Pydantic contracts
and v6 JSON Schema are additive; v1–v5 meanings and bytes stay unchanged.

| Contract | Fields / invariant |
|---|---|
| CampaignSpec | external G1/prediction/mock/config FilePins; scope; exact strategy/profile/mode/seed/order axes; sequential prefix checks; worker=1 |
| SourceRelease | actual commit/tree; exact scoped file/runtime/schema/lock/report SHA maps; environment versions; all scoped bytes match commit |
| PredictionJob | stable job_id over complete config/case; cohort; timeline/through-step; strategy/profile/mode/seed/order/prefix; prediction-only raw FilePin and closed fault enum |
| CaseExecution | actual API result inside a batch subprocess; safe code/stage/field rejection OR pinned semantic/trace/pool artifacts; no fictitious per-job process exit |
| StepRecord | unchanged native GroupingResult/EvidenceResult/GenerationResult/ExpressionResult; pool SHA; aligned PR1 excerpt diagnostic; reading budget/demand |
| MetricValue | integer numerator/denominator; measured quotient or null+zero_denominator/no_applicable_reference; independent research not_evaluated |
| DevelopmentReference | synthetic case/mode/side; controlled expected rejection code; explicit closed check vocabulary; post-prediction only |
| ChecksBundle | source release digest; complete required node/test hashes; actual argv/cwd/times/exit/log/artifact pins; exact full/G2/evals JUnit; G1 compatibility |
| G2AcceptanceResult | exactly H01–H10; missing evidence BLOCKED, failed gate FAIL, only all PASS gives engineering PASS; administrator pending, G3 authorization false |
| G3InputView | immutable original event/bundle/rule/expression/snapshot/coverage/lineage and trace pointers; final_personalized_rank=null |

SHA fields distinguish raw bytes from canonical semantic digest. JSON is UTF-8/LF,
no BOM, sorted keys, no NaN or duplicate keys. Collections are fixed-order tuples.
Real times/elapsed values are trace/command observations. Only elapsed_ms is omitted
from trace repeat comparison; semantic fields are compared in full. Input JSONL is
hashed as a whole; future file bytes may be read for integrity, but selected future
bodies are time-rejected before complete model parsing or stage invocation.

New controlled failures include G2_PR6_SCHEMA_INVALID, SOURCE_NOT_COMMITTED,
ROLE_INVALID, MATRIX_INVALID, WORKER_FAILED, CAPABILITY_DENIED, UNSEALED,
REPLAY_MISMATCH, NONDETERMINISTIC, COMPARISON_POOL_MISMATCH, REFERENCE_CONFLICT,
TEST_INVENTORY_INVALID, JUNIT_INVALID, REQUIRED_TEST_FAILED, UNEXEMPT_SKIP,
CHECK_FAILED, G1_INCOMPATIBLE, REVIEW_INVALID, EVIDENCE_MISMATCH and INPUT_INVALID
(all with G2_PR6_ prefix). Existing SHA/time/path/config codes retain their meaning.
Diagnostics contain fixed code/stage/field only, not original exception messages.

Campaign/assessment artifacts have an exclusive sealed.json marker binding raw
manifest SHA and exact artifact set. Incomplete runs cannot be accepted. Child
paths remain stable throughout campaign construction. Every output uses a new
repository .tmp/evals/g2 directory, shared atomic leaf exporter and no-overwrite
rules. There is no force/resume/cold-start/live or Oracle switch.

H01 input safety; H02 identity; H03 references; H04 constrained semantics; H05
output/coverage; H06 committed reproducibility; H07 regression; H08 output-bound AI
review; H09 capability/privacy; H10 research honesty. Required-test JSON contains
expanded T01–T46 nodeids, H mappings and auxiliary nodes, not a test-count shortcut.

PR6 whole-artifact publication also rejects G2_PR6_SENSITIVE_EXPORT: native upstream archives cannot bypass the PR4 safe-hold boundary. The controlled rejection contains no credential/quote payload.
