# G1-PR1/PR2/PR3 data dictionary (g1-pr3-1)

Pydantic frozen models are the source of all 21 JSON Schemas. extra=forbid and
strict=True reject unknown fields and coercion, including bool as score/budget.
Nested collections are tuples or frozen models. Whitespace is never silently
stripped from evidence. NonEmpty requires at least one non-whitespace character.
Use model_validate_json for JSON input; strict Python tuple fields require tuples.

## Entity contracts

DocumentVersion: stable document_id and unique doc_version_id; canonical_url,
provenance_uri, cleaner_revision and supersedes_version_id are required nullable
fields. published/submitted/first_seen may be omitted or null. observed/available
are mandatory. Content uses title, nullable text_excerpt, paragraphs of
paragraph_id/text, and content_sha256. Paragraph IDs are unique per version.
Metadata-only has no excerpt, paragraphs or content hash. Title remains discovery
metadata. content_kind separates publisher_text/feed_summary/archive_authored/
quoted_excerpt/synthetic_text; archive authorship is not a publisher quotation.

PersonaVersion: persona_id, persona_version_id, available_at, persona_origin,
domain_interests, current_goals, hard_constraints, knowledge_known,
attention_budget_seconds, exploration_preference, locale. All are required.
Constructed is the fixture default, explicitly stored, not inferred by the parser.
Knowledge is an explicit list; no exposure helper changes it. Budgets are positive
integers. Same-persona equal availability is rejected as ambiguous.

ReplayStep: composite timeline_id/step_id, nonempty family_scope_ids, as_of,
persona_version_id, nullable previous_delivery_id, attention_budget_seconds,
time_window_start/end, visible_doc_version_ids, coverage_window_ids, split.
start <= end <= as_of. Visible IDs equal the stable computed version sequence in
the declared family scope, used only to construct the evaluation scenario. Family,
split and gold never appear in candidate fields. The window is not a publication
time cutoff: important older documents remain eligible. Persona must be the latest
visible version. Duplicate scope, candidate or coverage IDs are rejected.

Delivery: delivery_id, as_of, generated_at, with as_of <= generated_at. No generator
or production delivery storage. Exposure: exposure_id, delivery_id, exactly one of
event_prediction_id/reference_event_id_for_fixture, kind, occurred_at, source.
Kinds are included/rendered/opened/acknowledged/dismissed; occurred_at cannot precede
delivery generation. Fixture reference events must be synthetic. Prediction IDs
are opaque identifiers; resolving actual predicted items remains pending PR3/4.

CoverageWindow: coverage_window_id, source_id, start_at/end_at, status, observed_at,
reason. start <= end <= observed. Status is covered/partial/failed/unknown/
service_offline. Every non-covered state needs a reason. A step may reference only
closed, already observed windows. covered is limited source coverage, not proof
that the world had no updates. Coverage aggregation/reporting is deferred.

EventGroup keeps all G1 section 5.3 fields. Claim keeps section 5.4 fields, including
scope as nonempty text and limitations as explicit strings. Claim snapshots use
(claim_id, valid_as_of); the same ID cannot change claim_text. EvidenceRef has
doc_version_id, optional paragraph_id and supports/refutes/mentions/unknown.
GoldLabel uses (timeline_id, step_id, persona_version_id, event_id,
annotation_version), all four dimension scores and graded_relevance as integers
0-3, material_change, tier, supporting versions, rationale, uncertainty and
adjudication_status (pending/agreed/adjudicated/unresolved). Reference event/claim/
gold records also carry record_origin/provenance_uri, explicitly attributing even
the small schema examples. This is metadata, not completed human validation.
Programmatic reference/time validity does not assert semantic support. Labels may
refer to an available older version, including after its successor becomes visible.

FamilySplit has family_id and train/dev/test split. One map row per family. A
document's versions and explicit upstream derivatives keep the same family. All
steps of a family, timeline and persona history keep one split. Counterfactuals
must explicitly retain the original family; undeclared semantic kinship detection
and full lineage review are deferred, not claimed by this validator.

## Time and version policy

published_at is a publisher claim; it can be null, early or late. It never grants
availability. observed_at is observation of this exact version, not article identity.
available_at >= observed_at; only available_at <= as_of is usable. No archive
backdating exception is implemented. All times use RFC3339 with T, seconds, Z or
numeric +/-HH:MM and optional 1-6 fractional digits. Naive/date-only/invalid values
and unknown offset -00:00 are rejected. UTC aware datetimes are used for comparisons;
model serialization emits UTC Z, without rewriting source files.

Version links stay within one document, have one root, no cycle or branch, and
nondecreasing availability. Equal-time versions need explicit linear succession.
Same document/content SHA cannot create another version. PR2 observations refer
to an existing version and preserve each observation ID/time/content SHA. There
is no business observation table or automatic ingestion/version writer.
visible_versions validates chains using metadata, selects the last eligible node,
and returns documents by document_id. Published time never drives this choice.

Future corpus records are legal. Explicit future candidate references raise
FUTURE_VERSION. visible_exposures defaults to strict=True (reject future context);
strict=False projects a complete log, returning visible events plus reasons for
excluded events. previous_delivery and visible_persona reject future context.
project_candidate rechecks availability before reading selected text. It strips
family, split, gold/reference IDs and annotation rationale, not just a denylist
of known labels. Candidate projection requires provenance-validated documents;
it is not an independent rights validator.

## Hash and manifest policy

Text normalization is Unicode NFC plus CRLF/CR -> LF; no trim, truncation or case
folding. The exact content sequence is title, text_excerpt-or-empty, then paragraph
texts in order, joined by two LF characters, retaining empty/duplicate slots. Hash
UTF-8 bytes with SHA-256. Paragraph IDs, source/time/family are outside content SHA
but protected by file SHA. No body means content_sha256=null. Raw hashes, if later
introduced, require separate fields. Legacy Article.content_hash is unrelated.

Manifest declares dataset/schema/annotation/persona revisions, created/frozen
times, document-origin counts, file_hashes (path/role/sha256/record_count), registry
hash, family split counts, family_locked_v1 policy, nullable baseline config hash,
legal_notes, limitations and draft/frozen/superseded status. Frozen/superseded needs
frozen_at >= created_at. baseline_config_sha256 is null until a config exists.
Origin counts count documents only, not real registry entries. Non-record file
counts are null; source registry count is its number of source entries.

JSONL is UTF-8, no BOM, LF, one record per nonblank line, including final LF.
Duplicate JSON keys and non-finite JSON numbers are rejected. File SHA uses exact
bytes, not parsed JSON. All JSONL, package Python scripts, schemas and other manifest
JSON inputs must be listed. Model schemas must match generated bytes. Provenance
must reference a listed local support file for synthetic records. Manifest paths
are root-relative POSIX paths; no absolute, escaping, sensitive, database or outside
symlink paths. The root is the parent of manifests/. Data bytes are verified once
and those same bytes parsed; validator does not repair or rehash them. Manifest
itself is excluded to prevent self-hash recursion; report records its hash.

Revision procedure: retain old frozen bundle/manifest bytes, copy to a new revision,
record the reason/differences, recalculate content and file hashes, validate, then
freeze and pin the new manifest SHA. Never silently rehash an existing frozen
revision. A maliciously replaced manifest is outside unsigned SHA authenticity.

## Source and rights policy

Source entries contain source_id, record_origin, domain, source_type,
publisher_or_upstream, independence_relation, allowed_use, redistribution_rights,
license_url_or_note, observed_scope, checked_at, restrictions and provenance_uri.
restrictions contains nullable positive max_excerpt_chars and a nonempty note.
Unknown rights mean metadata-only allowed_use; a rights review date may be null.
Synthetic source domain is null and rights are synthetic. Real documents require
HTTPS URLs matching the registered domain and HTTPS provenance, without credentials.
HTTPS structure is not verification of existence, ownership, independence or rights.
Different hostnames do not prove independent evidence.

Unknown rights prohibit body/excerpt storage. metadata_only prohibits body storage.
excerpt_only needs quoted_excerpt, an explicit limit and permission; count all stored
excerpt/paragraph characters, including duplication. Document permissions cannot
broaden registry permissions. Real documents cannot use synthetic_text or synthetic
rights/URI; synthetic documents must use synthetic:// and local design provenance.

## Failure codes and remaining gates

Structural: SCHEMA_INVALID, UNSUPPORTED_REVISION, INVALID_JSON, INVALID_INTERVAL,
DUPLICATE_ID, REFERENCE_NOT_FOUND, CITATION_NOT_FOUND, RECORD_COUNT_MISMATCH.
Integrity: SHA_MISMATCH, FILE_MISSING, UNLISTED_INPUT, MANIFEST_PATH_INVALID,
MANIFEST_SELF_HASH. Time: NAIVE_DATETIME, INVALID_DATETIME,
AVAILABLE_BEFORE_OBSERVED, VERSION_CHAIN_INVALID, VERSION_CONFLICT,
DUPLICATE_CONTENT_VERSION, FUTURE_VERSION/PERSONA/EXPOSURE/DELIVERY/COVERAGE/EVIDENCE,
VISIBLE_SET_MISMATCH. Source: SOURCE_NOT_FOUND, SOURCE_TYPE_MISMATCH,
SOURCE_NOT_ALLOWED, PROVENANCE_INVALID, ORIGIN_MISMATCH,
RIGHTS_UNKNOWN_FULLTEXT, RIGHTS_USE_NOT_ALLOWED. Split: FAMILY_NOT_FOUND,
CROSS_FAMILY_SPLIT. Multiple diagnostics are sorted by path, line, code, ID, field.

Pending: independent human semantic/rights review, complete lineage, real historical
materials, predictions/prompts/index/metrics, actual human submission/adjudication
and G1-a acceptance. T25 N/A. No changes to existing business contracts,
database schemas or historical audit documents.

Windows path comparisons also reject sensitive names case-insensitively, trailing
spaces/dots and multiple manifest entries resolving to the same file. Exact URL
or content-SHA identities cannot cross splits even under different declared
family IDs; this is integrity matching, not semantic grouping.

## PR2 additive records and preparation

DocumentObservation: observation_id, doc_version_id, observed_at, content_sha256,
record_origin/provenance_uri. Its target must exist with the same origin/hash and
must have been observed by this time. Multiple observations do not add versions.

EventRelation: left/right doc_version_id, relation, rationale, evidence_at,
record_origin/provenance_uri. Relations are exact_duplicate/syndicated/
same_event_different_evidence/related_distinct_event/unrelated/uncertain. Both ends
exist with compatible origins/splits and are available by evidence_at. Self-pairs
and reversed duplicate pairs at the same instant are rejected. These are reference
labels, never predicted groups or independently verified truth.

Annotation wraps annotation_id, timeline/step/persona, annotation_version,
annotator_id, submitted_at, guide_revision, packet_sha256 and initial_label.
Initial_label has a local_event_id, visible document_version_ids, the four 0-3
scores, graded_relevance, material_change, tier, rationale, uncertainty,
document_relations and claim_reviews. ClaimReview has claim_text, evidence_refs,
semantic_support=supported/unsupported/uncertain, scope and limitations. Scores,
timestamps and packet SHA are strict; a blank template is not an Annotation.
Guide revision is dev01-guide-v1, whose controlled manual is mandatory. Repeated
submissions for the same annotator/step/local event/version cannot overwrite.
Within each initial_label, an unordered document pair plus evidence_at must occur
only once, including identical or contradictory reversed entries. The same pair
may be revisited at a different instant or in a different annotator's submission.

Adjudication has adjudication_id, prior_annotation_ids, final_label (GoldLabel),
reason, adjudicator_id, adjudicated_at. Prior records must exist for at least two
different IDs, share the final scenario/version, and precede adjudication. The
final label must match an explicitly stored Gold record with status adjudicated
or unresolved. Unresolved adds unresolved_adjudication to the pending report and
is not completion. Two IDs do
not certify two real people: independent_annotation remains pending. No exporter
creates human records, Gold or arbitration automatically.

Manifest adds optional observations/event_relations/annotations/adjudications
roles. Empty human JSONL files have record_count=0. Every JSONL remains controlled;
role/schema disguise, missing files and all old path/hash guards remain errors.
The main package includes both PR1 and DEV-01, so origin counts and split counts
aggregate both. The old fixture bytes and its annotation_version remain unchanged.

pilot.annotation_packet returns canonical bytes for one step after version/persona/
coverage gates, using CandidateDocumentVersion's field allowlist. It takes no
reference events, relations, Claims or Gold. pilot.visible_claim_states is reference-
only and ignores future state payload before accessing its ID/text. citation_status
checks availability and paragraph existence and always leaves semantic support
not_measured. PR2 dry-run export still requires an external Manifest SHA pin.

## PR3 prediction and evaluation interfaces

load_bundle(manifest_path, manifest_sha256, config_path=None) reads only prediction
roles. It verifies the external pin, controlled paths, unique IDs, schemas,
executable code and scoring kernel, source rights and family/split context.
As of pr3-replay-v2, split_metadata.split_metadata_issues is shared with full
validation: document family is immutable; non-null URL/SHA identities cannot
cross splits; upstream documents must exist, belong to the same family and have
an available version by the child's availability. Each timeline and persona_id
(across all persona versions referenced by steps) belongs to one split. These
global admission checks inspect metadata only; they never score future bodies or
preferences, or open reference events/labels. Illegal split reuse fails during
load_bundle with CROSS_FAMILY_SPLIT, before load_step/ranking/output creation.
It never imports the full validator or opens reference answers. Full validation
remains strict and mandatory for evaluation, not ordinary prediction.

load_step(bundle, timeline_id, step_id, config) returns ReplayContext and an
immutable tuple of CandidateDocumentVersion. Historical document/persona metadata
is selected before payload projection. Actual visible IDs must equal the frozen
step exactly (VISIBLE_SET_MISMATCH is fatal). time_window_start never removes old
visible documents. Context has scenario/time, visible Persona, candidate IDs,
previous delivery ID, budget, selected coverage and safe exposure history; it has
no family/split/reference IDs. Exposure history is scoped by preceding delivery
references in the same timeline, filtered at as_of, and retains unbound fixture
history without its reference-event target. It never mutates knowledge_known.

BaselineConfig freezes revisions, k1=1.2, b=.75, title_weight=2, five-decimal
scores, thresholds (.95 body/.80 title/min 12 tokens), metric_k=5, seed=0 and the
retrieval.py SHA. ReplayContext/PredictedEventGroup/RankedItem/BaselineConfig add
four schemas; the prior 17 schemas and all prior JSONL stay byte-identical.

RankerProtocol.rank(context, candidates) returns all RankedItems, before any
presentation truncation. Each item has rank, member version IDs, representative
version/source, nullable score and frozen score components. B0 score is null and
its available_at sort signal is explicit. B1/B2 use nonnegative BM25, including
zero. B2 adds predicted_event_id, merge_reasons and evidence_independence;
only observable duplicates/upstream yield not_independent, otherwise unknown.
No output claims independent support based merely on a source category/domain.

PredictedEventGroup has sorted unique members and an ID derived from members and
rule revision. Text joins use complete linkage, preventing transitive bridges.
oracle.py is an explicit exception that reads reference events, intersects visible
members and preserves unmapped singletons. Ordinary rankers do not import it.

evaluate_run validates the full pinned bundle and recorded run artifacts, checks
the input snapshot against rederived historical inputs, then reads reference gold.
Recall@5 counts distinct focus events from displayed representative versions;
nDCG uses 2^graded_relevance-1 and retains zero-gain duplicate positions. Each
metric includes numerator/denominator/value/undefined_reason. Missing labels yield
gold_not_available; pending/unresolved-only labels yield gold_pending_or_unresolved.
No focus events/zero ideal gain have explicit null reasons, never fake 100%.
Pair diagnostics compare all visible mapped pairs with synthetic reference groups,
record TP/TN/FP/FN and unmapped IDs. These are not independent human measurements.

Additional failures: MANIFEST_SHA_MISMATCH, CONFIG_NOT_PINNED, RUNTIME_CODE_MISMATCH,
PREDICTION_PATH_INVALID, GROUP_MEMBERS_INVALID, UNKNOWN_ALGORITHM,
ORACLE_REQUIRES_EXPLICIT_PATH, ORACLE_OUTPUT_PATH_REQUIRED, ORACLE_MARKER_INVALID,
RUN_INPUT_MISMATCH, TIMELINE_REQUIRED. No validator repairs or rehashes inputs.
PR3 does not clear the aggregate replay_rankers_metrics pending flag: B3/B4 and
complete G1 metrics/acceptance still remain outstanding.
