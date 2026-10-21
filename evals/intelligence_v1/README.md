# G1-PR1–PR4: offline contracts, replay and revisit evaluation

This package implements schemas, source/rights checks, manifest integrity, family
split checks and pure historical selectors. PR2 adds the six-step DEV-01 synthetic
pilot, observation/relation contracts, annotation preparation and a manual.
PR3 adds as_of replay, the full shared candidate pool, B0/B1/B2-predicted,
an explicitly separate B2-oracle, and post-ranking Recall@5/nDCG@5/group diagnostics.
PR4 adds B3/B4, fixed common delivery history, reading budgets, reference-separated
metrics, REVISIT-7D counterfactuals and the report CLI. Real annotation, semantic
support measurement, collection, migration and G1-a acceptance remain pending.

From D:\agent_project\cfaw-news using the existing virtual environment:

```powershell
.\.venv\Scripts\python.exe -m evals.intelligence_v1.contracts --check-schemas
.\.venv\Scripts\python.exe -m evals.intelligence_v1.validate --manifest evals/intelligence_v1/manifests/dataset_manifest.json --strict
.\.venv\Scripts\python.exe -m pytest tests/evals -q
```

The CLI prints a JSON ValidationReport and writes no reports or repaired files.
Exit status is 0 for success, 1 for invalid data, 2 for incorrect CLI arguments.
Without --strict the CLI still exits 1 for invalid data. The Python API uses
validate_dataset(path, strict=True); failure raises DatasetValidationError carrying
the same report. strict=False returns that failed report, without relaxing checks.
Diagnostics contain codes, paths, line numbers, IDs and fields, never evidence text.

Runtime dependencies are standard library and existing Pydantic 2. No Settings,
database, provider, HTTP client or collection module is imported. Only the pure
cfaw_news.retrieval scoring/tokenizer module is reused for ranking. The validator
rejects .local, .env, dev-diaries, database paths and paths escaping the bundle.
Data is read only from the explicit manifest, including local provenance files.
Full validation reads the complete bundle, including reference answers. Prediction
instead verifies only prediction roles and code/config schemas, without opening
events/relations/claims/gold/annotation/adjudication files. It records
validation_scope=prediction_inputs and full_dataset_validated=false. Removing those
reference files does not change ordinary predictions; full validation/evaluation
must fail. Raw JSONL bytes are hashed as files; metadata selects versions before
their bodies are validated, tokenized or projected to the ranker.

Schemas are generated from contracts.py. --check-schemas is read-only and checks
exact bytes and file names. There is deliberately no validator repair or rehash
command. The checked-in manifest lists other inputs, not itself; the report records
its SHA separately. SHA proves integrity relative to a trusted manifest, not the
authenticity of a replacement manifest. Future runners must pin that SHA.

The shipped data is the unchanged PR1 synthetic contract fixture plus DEV-01
(seven synthetic versions, eight observations, six steps). Rights for the configured
GitHub Blog source remain unknown and metadata-only; no network or license review
was performed. URL syntax/domain checks do not verify remote existence or truth.

Requirement coverage: T01/T02/T03/T20 and TZ01/TZ02/HASH01 at the contract boundary;
T22/T23/T26 basic negative cases; VER01/GOLD01/ISOLATION01 basic guards. T10 covers
only an empty candidate list and explicit coverage states. PR3 additionally covers
T06/T07/T15/T18, its portion of T24, GROUP01/ORACLE01 and post-ranking gold integrity.
Real provenance, semantic lineage, human support and complete PR5/G1 gates remain pending.
T25 is N/A: no schema migration or business database access.

PR2 sample checks: T04/T05/T08/T09/T16/T17/T19/T21. `pilot.py` has pure helpers for
one historical annotation packet, reference-only Claim snapshots and citation
location. A citation result always separates `location=valid` from
`semantic_support=not_measured`. Neither a reference Claim state nor an authored
synthetic negative expectation is an independent human measurement.

DEV-01/visible_versions.json records each visible version, SHA and paragraph IDs.
DATA_CARD.md documents source/rights boundaries. ANNOTATION_GUIDE.md v1 and the
blank DEV-01/annotation_template.json describe the human workflow. DEV-01 labels/
files are empty; A/B availability, actual initial submissions, semantic review and
adjudication remain unconfirmed. PR1's three pending synthetic Gold records stay
separately counted and are not human pilot labels. Do not give annotators the full
repository, administrator visibility table, future packets or reference records.
Packet helpers require provenance-validated records; they are not a sandbox or
a substitute for human confirmation of packet distribution and independence.

PR2 review fixes: one annotation cannot assign two relations to the same unordered
document pair at the same evidence_at. Adjudication can store `adjudicated` or
`unresolved`; an unresolved record explicitly adds unresolved_adjudication to
ValidationReport.pending. Raw submissions are never rewritten or auto-resolved.

## Reproduce PR2 preparation from a checkout

Use the externally recorded current Manifest SHA from reports/PR4_ACCEPTANCE.md;
do not derive your trusted pin from the file being checked on each run.

```powershell
$PIN = '<SHA256 recorded in PR4_ACCEPTANCE.md>'
.\.venv\Scripts\python.exe -B -m evals.intelligence_v1.replay --manifest evals/intelligence_v1/manifests/dataset_manifest.json --manifest-sha256 $PIN --timeline DEV-01 --dry-run --out .local/g1-pr2-review-all
.\.venv\Scripts\python.exe -B -m evals.intelligence_v1.replay --manifest evals/intelligence_v1/manifests/dataset_manifest.json --manifest-sha256 $PIN --timeline DEV-01 --dry-run --step D0 --out .local/g1-pr2-review-d0
```

The output directory must be new, outside the bundle and not a sensitive/database
path. Pin/data/schema errors fail before output creation; existing files are never
overwritten. Compare two output directories byte-for-byte. `visible_steps.jsonl`
and run_metadata.json are administrator records; distribute only the current
packets/<step>/packet.json plus blank_form.json and the manual to an annotator.
There is no dependency on ignored local scripts. The CLI performs no network/model
calls or business imports. --dry-run and --algo are mutually exclusive. Exported
packets contain no reference event/Claim/Gold answers. They are not human results.

## Historical PR3 replay and separate evaluation

PR3 revision: `pr3-replay-v2` (superseded by the current PR4 bundle). The v1 split isolation gap
is fixed by shared metadata checks in `split_metadata.py`, used by both the
prediction loader and the full validator before ranking. Document family cannot
change across versions; URL/SHA identity cannot cross splits; upstream derivations
stay in the same family; timelines and all versions of a persona stay in one split.
These checks read identity/availability metadata only, never reference answers or
future bodies/preferences. See `reports/PR3_SPLIT_REVIEW_FIX.md` for the current pin,
regression evidence and preserved v1 record. JSONL/gold and schemas are unchanged.

From the project root, with a trusted pin and new output directories:

```powershell
$PY = '.\.venv\Scripts\python.exe'
$ROOT = 'evals/intelligence_v1'
$PIN = '<current SHA256 recorded in PR4_ACCEPTANCE.md; old pin requires preserved PR3 package>'
foreach ($algo in @('b0', 'b1', 'b2-predicted', 'b2-oracle')) {
  & $PY -B -m evals.intelligence_v1.replay --manifest "$ROOT/manifests/dataset_manifest.json" --manifest-sha256 $PIN --split dev --algo $algo --config "$ROOT/manifests/baseline_config.json" --out ".local/evals/g1/pr3/$algo-a"
  & $PY -B -m evals.intelligence_v1.evaluate --manifest "$ROOT/manifests/dataset_manifest.json" --manifest-sha256 $PIN --run ".local/evals/g1/pr3/$algo-a" --out ".local/evals/g1/pr3/$algo-a-evaluation"
}
```

Optional --timeline/--step select a scenario; --step requires --timeline. With no
selection all steps run. B0 sorts by available_at descending then ID. B1 builds
the fixed interest/goals/constraints query and scores every visible document,
including zero scores, using title twice plus excerpt/paragraphs. No Top8 filter.
B2 scores that same corpus before grouping; group score is max member BM25 and
representative ties use version ID. Exact URL+non-null SHA, visible upstream edges
and complete-link conservative text rules are frozen in baseline_config.json.
Body/title token-set Jaccard thresholds are .95/.80, minimum body vocabulary 12.
Unknown upstream targets remain separate unless another observable rule matches.
Different hostnames never establish independent corroboration.

Predicted IDs hash visible membership plus rule revision; they are snapshot-local,
not a claimed persistent online event identity. The reference oracle intersects
reference event memberships with the same candidates and retains unmapped
singletons. Oracle output/evaluation directory names must contain 'oracle', with
oracle markers in rows, IDs and reports. It is a synthetic diagnostic, not a
deployable method or an independently measured human upper bound.

Each run writes input_snapshot.json, baseline_config.json, predictions.jsonl and
run_metadata.json. First three files are deterministic across runs/hash seeds;
timestamps/elapsed time live only in metadata. The run records pinned executable
source hashes, retrieval kernel SHA, Git SHA and dependency lock hashes. No LLM is
called (model_tokens=0). Full validation and evaluator run after predictions, in
separate commands, verifying inputs/artifacts and never rewriting predictions.

DEV-01 relevance gold is absent: Recall/nDCG are null, reason=gold_not_available.
PR1's pending labels yield gold_pending_or_unresolved, not measured performance.
Formula tests use explicitly synthetic temporary labels. Event grouping errors
use synthetic reference membership only, and include comparable/unmapped counts.
One displayed representative maps to one reference event; duplicate cards retain
their positions and earn no repeated gain. There is no @budget or revisit claim.
PR3 independent rereview found no P0/P1; its remaining P2 stale-pin documentation
is corrected by the current PR4 pin instructions. Real A/B annotation remains pending.

## Current PR4 replay, budget and report

Dataset revision `pr4-revisit-v1`, schema `g1-pr4-1`, config `pr4-baselines-v1`.
The old 22 JSONL files, including gold/annotations/adjudications, stay byte-identical.
REVISIT-7D adds seven synthetic document versions, six steps and eight explicitly
authored test expectations. They are not human submissions or gold adjudication.
Use `--label-source synthetic-fixture` explicitly to measure these technical cases;
the default `gold` mode keeps absent/pending human gold null. Never combine sources.

```powershell
$PY = '.\.venv\Scripts\python.exe'
$ROOT = 'evals/intelligence_v1'
$PIN = '<SHA256 recorded in reports/PR4_ACCEPTANCE.md>'
& $PY -B -m evals.intelligence_v1.replay --manifest "$ROOT/manifests/dataset_manifest.json" --manifest-sha256 $PIN --split dev --algo b4 --budget-seconds 420 --half-life-days 7 --out .local/evals/g1/pr4-example/b4-420-a
& $PY -B -m evals.intelligence_v1.evaluate --manifest "$ROOT/manifests/dataset_manifest.json" --manifest-sha256 $PIN --run .local/evals/g1/pr4-example/b4-420-a --label-source synthetic-fixture --out .local/evals/g1/pr4-example/b4-420-a-fixture
& $PY -B -m evals.intelligence_v1.report --manifest "$ROOT/manifests/dataset_manifest.json" --manifest-sha256 $PIN --runs .local/evals/g1/pr4-example --out .local/evals/g1/pr4-example-summary
```

The same CLI accepts b0/b1/b2-predicted/b2-oracle/b3/b4. Keep `oracle` in oracle
output names. All six algorithms use identical candidates and fixed synthetic
history, without feeding their own outputs into later steps. B0/B1 keep article
duplicates and their reading cost. B2–B4 use one main card per predicted group.

B3 normalizes the maximum representative BM25 score within the visible groups;
zero maximum gives zero normalized BM25. It combines .75 relevance + .25 recency,
with `recency=2**(-age_days/half_life_days)`. Material-visibility time is the latest
visible version availability, so a repost/title edit may refresh this weak proxy.
Seven days is the frozen default; 3/14-day sensitivity is allowed only on dev steps.

B4 associates the most recent related delivery by overlapping document identities,
not snapshot-local group-ID equality. It compares non-null content hash sets.
New hashes release old penalties; unknown hashes are not declared no-change.
Included/rendered/acknowledged add .10/.10/.25 once each when no text is new;
snapshot membership itself establishes server inclusion. Opened/dismissed are
logged without extra coefficients. No signal changes knowledge_known or establishes
comprehension. Signed scores are preserved. Novel text is not semantic novelty.

Full ranked_items remain available. Presentation is a separate ranked prefix:
first 3 focus cards at 90 seconds, then at most 12 radar at 12 seconds. Stop at
the first unaffordable card, without skipping or demotion. Step budget is the
default; --budget-seconds explicitly overrides it with 180/420/900. The card caps
can make 420/900 results equal. Reading seconds are proxies, not measured savings.

Evaluation recomputes presentation, checks the run fingerprint and never rewrites
predictions. Report cohorts separate manifest/config/experiment/label source and
oracle status; repeated runs are deduplicated before macro/micro/family summaries.
Formal change/correction/withdrawal predictions are not emitted; their metrics
remain null while new-text proxy measurements are separate. No generated claims
means citation metrics have no output-claim denominator; semantic support is not_measured.
Latency is in performance.json, outside canonical deterministic metrics.

Counterfactual tests construct separate frozen bundle copies for the same dev family.
Run `python -B -m pytest tests/evals/test_revisit_counterfactuals.py -q` with a new
--basetemp and --junitxml to preserve versions, pins and scenario-evidence.json.
No product CLI depends on ignored authoring or acceptance scripts.

Run original Ruff, full pytest, seed-sanity, pip check and frontend build separately.
The old 26-document seed is a smoke check, not G1 gold. Local build/tests do not prove
live-model quality, live feeds, CI, production deployment or G1-a acceptance.

See DATA_DICTIONARY.md for field/serialization policy and error codes, and
G1_BASELINE_LOCK.md for the repository starting state and fresh validation evidence.
