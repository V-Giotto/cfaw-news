# G1-PR1–PR5: offline development data, replay and annotation audit

## Current AI development batch (2026-10-23)

Dataset `pr5-five-trajectories-v10-ai-development-r3`, schema `g1-pr5-6`.
DEV-01…05 now use a fresh, explicitly AI-authored batch: 26 steps, 47 event
judgments, 234 claim reviews and 90 relations. Draft and evidence-review arrays
are separate under labels/ai_development/; batch.json binds their hashes, actual
processing times, packet hashes, AI guide and input snapshot. Existing V3 word
meanings remain, without its human-only execution restriction.

One assistant authored and reviewed the batch with previous reference/full-story
exposure disclosed. The evidence review corrected vague draft scopes; a later review corrected unsupported Persona-known inference from included-only exposure. Prior versions remain available. No independent AI pair, human evidence, invented disagreement
or Cohen kappa is claimed. Primary fixture_expectations are regenerated from the
reviewed records; old DEV-02…05 expectation files are retired, not mixed into the
new denominator. Eight auxiliary expectations retain their separate fixture scope.
Human annotations/adjudications/gold remain empty and optional human audit remains
BLOCKED; this does not veto the ai_development profile. Nothing starts G2 automatically.

Read-only batch audit:
`python -B -m evals.intelligence_v1.ai_development --manifest <manifest> --manifest-sha256 <pin>`

Default development acceptance additionally requires this audit, frozen exact
label coverage, all technical checks and a fresh full matrix. Complete current
results and external pin: reports/PR5_AI_DEVELOPMENT.md and G1_ACCEPTANCE.md.
Former received human materials are preserved locally under
.local/evals/g1/pr5/ai-restart-20261023/retired-local/ and are not current inputs.
Historical frozen versions/guides/reports remain available; the descriptions below
refer to those historical releases and are not new completion claims.

## Historical releases through V9

> **Current policy (2026-10-23):** DEV-01 through DEV-05 use `ai_development` acceptance. AI may author and review development labels; no second human is required. See [AI development rules](../../docs/plans/G1_AI_DEVELOPMENT_RULES.md). Historical human workflow descriptions below apply only to the optional `human_research` profile and preserved releases. This policy change alone does not pass a new acceptance run.

Current AI-development policy dataset: `pr5-five-trajectories-v9-ai-policy-r1`, schema `g1-pr5-5`. DEV-01…05 contain
26 primary states / 35 synthetic document versions / five dev families. Preserved
auxiliary fixtures add nine states / 11 versions / two families, reported separately.
Human annotations, adjudications and gold remain empty. New development acceptance must be rerun; human absence alone no longer blocks development or G2 offline eligibility.
The preserved v1 was superseded after internal review found three authored
no_change references overlapping unknown coverage. V2 marks them insufficient
and excludes unknown change labels from repeat/proxy denominators. No tier,
grade, human gold, ranking rule or baseline coefficient changed; all gates rerun.
V2 verification was interrupted after a historical-citation audit defect was
reproduced. V3 allows already available older evidence within the same story,
while event membership/ranking still uses current candidates. Guide g1a-guide-v2
explains retained prior packets; future/cross-family evidence remains rejected.
PR4 independent rereview passed; see reports/PR4_REREVIEW_GATE.md.

V8 registers the full V3 guide and human input schemas. Its original opening v7
preparation status is historical; this README and current ReviewSession describe
registration. Original human words/hashes are retained for audit; canonical
projection is explicit and cannot grant human eligibility. Received human records retain the original provenance and human-review requirements. AI development records use a separate batch and synthetic-fixture evaluation; do not import them as human gold.

V8-r1 binds extracted source links to the same parsed-model canonical claim hash
as formal audit, including optional paragraph_id:null defaults. The raw claim
dictionary hash and received-file SHA are retained separately, without converting
human direction words. This repairs a legitimate omitted-field lineage failure.

Read-only JSONL check (exit 1 on format errors, no file edits or human certification):
`python -B -m evals.intelligence_v1.human_inputs --input <submission.jsonl>`

For a received file carrying a separate review_label, explicitly select
`--layer initial` or `--layer review` to inspect that view. The strict received
view rejects this non-Annotation envelope. Review extraction preserves the
original layer, claim extras and source hashes; it never replaces initial_label
or certifies independent annotation. A joint review is not a new independent pass.

V4 addresses four independent-review findings: the frozen required_tests.json
binds the complete full/G1 JUnit nodes, Txx mapping and test-source hashes;
adjudicated split/merge mappings preserve raw partitions and disagreement;
four templates use the current guide; DEV-01 theme first appears as new while
remaining archive/grade 0. No human gold or baseline rule was changed.

V5 adds complete blank form/field templates, the exact schema and guide to each
single-step packet export. Agreement includes deterministic family bootstrap
intervals (null with a reason for fewer than two families) and distributions.
The development-only comparator keeps split/merge components intact and never
counts a human/AI comparison as independent human annotation. The .70 observation
threshold still conservatively requires remediation; it is not evidence of
algorithm improvement. AI development guide revisions may be adopted with a new version; the optional human research path retains its original review process.
V6 additionally restricts development pair comparisons to documents annotated by
both sides. Missing annotations stay missing rather than becoming negative pairs.

The current externally recorded pin and actual test results belong in
reports/PR5_HUMAN_READINESS.md. reports/PR5_REVIEW_FIX.md retains v4 evidence;
reports/PR5_ACCEPTANCE.md retains the historical v3
results; its complete JUnit was not missing tests, but its acceptance guard was
insufficient. Historical records are not fresh verification of this revision.
No dependency installation, network, production database, model call or business
API is needed. ANNOTATION_GUIDE_AI.md is the default execution guide; the preserved V3 guide supplies scoring definitions and the optional human protocol.

```powershell
$PY = '.\.venv\Scripts\python.exe'
$ROOT = 'evals/intelligence_v1'
$PIN = '<current external SHA256 recorded in reports/AI_DEVELOPMENT_POLICY.md>'
& $PY -B -m evals.intelligence_v1.annotations packet --manifest "$ROOT/manifests/dataset_manifest.json" --manifest-sha256 $PIN --timeline DEV-02 --step D0 --out .local/evals/g1/pr5/example-single-step
& $PY -B -m evals.intelligence_v1.annotations audit --manifest "$ROOT/manifests/dataset_manifest.json" --manifest-sha256 $PIN --out .local/evals/g1/pr5/example-audit
& $PY -B -m evals.intelligence_v1.annotations agreement --manifest "$ROOT/manifests/dataset_manifest.json" --manifest-sha256 $PIN --out .local/evals/g1/pr5/example-agreement
& $PY -B -m evals.intelligence_v1.reproduce --manifest "$ROOT/manifests/dataset_manifest.json" --manifest-sha256 $PIN --out .local/evals/g1/pr5/example-matrix --workers 4 --packets
& $PY -B -m evals.intelligence_v1.acceptance --manifest "$ROOT/manifests/dataset_manifest.json" --manifest-sha256 $PIN --runs .local/evals/g1/pr5/example-matrix/primary --checks .local/evals/g1/pr5/example-checks/checks.json --out .local/evals/g1/pr5/example-acceptance
```

Every output path must be new. Acceptance returns exit 1 and saves a NOT_MET report
when a required gate is missing. The default ai_development profile requires complete development labels and technical evidence; use --profile human_research for the optional human gate.
`checks.json` binds the manifest, current source/test/lock fingerprints, exact
commands, exit codes and hashed logs/JUnit, plus the prior independent review.
See acceptance.py::verify_checks for the required record shape; never invent logs.
All-step exports under administrator-packets are administrator artifacts only;
give each reviewer only their current single-step packet, blank form and guide.
The matrix runs 200 predictions/400 independent evaluations with seeds 1/719,
budgets 180/420/900 and dev-only B3 3/14-day sensitivity at 420 seconds. Its 1,400
deterministic artifact hashes exclude timing. Human gold and synthetic expectations
remain separate modes, and oracle remains separate. Repeats are not new samples.

New human records use guide g1a-guide-v3 and g1a-annotation-v2 in the existing
labels/g1a_v1/ storage directory (its historical name is not a batch version), not the preserved
legacy empty/pending records. The review session starts not_started. An actual
administrator must confirm real people, independent frozen submissions, receipts
and adjudication; a pair of IDs or programmatic probes never qualifies. Agreement
is computed from raw submissions before adjudication, with unmatched cases exposed.
Formal change/correction/withdrawal and algorithm-output semantic support remain
unmeasured; separate human support-review statistics do not change that boundary.

build_pr5 is an explicit offline authoring/freezing tool, not validator repair.
Its --build refuses existing story directories; do not rerun it on frozen data.
Preserve the old full package before a changed release and choose a new revision.
Do not derive a trusted pin from an untrusted manifest at prediction time.

## Historical implementation notes

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

The PR2 shipped data was the unchanged PR1 synthetic contract fixture plus DEV-01
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

Use the externally recorded current Manifest SHA from reports/PR5_ACCEPTANCE.md;
do not derive your trusted pin from the file being checked on each run.

```powershell
$PIN = '<SHA256 recorded in PR5_ACCEPTANCE.md>'
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

PR3 revision: `pr3-replay-v2` (historical; current release is described at the top). The v1 split isolation gap
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
$PIN = '<current SHA256 recorded in PR5_ACCEPTANCE.md; old pin requires preserved PR3 package>'
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
was corrected by the PR4 pin instructions. Current pins are in PR5_ACCEPTANCE.md; real A/B annotation remains pending.

## Historical PR4 replay, budget and report

Dataset revision `pr4-revisit-v1`, schema `g1-pr4-1`, config `pr4-baselines-v1`.
The old 22 JSONL files, including gold/annotations/adjudications, stay byte-identical.
REVISIT-7D adds seven synthetic document versions, six steps and eight explicitly
authored test expectations. They are not human submissions or gold adjudication.
Use `--label-source synthetic-fixture` explicitly to measure these technical cases;
the default `gold` mode keeps absent/pending human gold null. Never combine sources.

```powershell
$PY = '.\.venv\Scripts\python.exe'
$ROOT = 'evals/intelligence_v1'
$PIN = '<current SHA256 recorded in reports/PR5_ACCEPTANCE.md>'
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
