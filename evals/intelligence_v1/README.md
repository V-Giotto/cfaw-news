# G1-PR1/PR2: offline contracts and DEV-01 pilot

This package implements schemas, source/rights checks, manifest integrity, family
split checks and pure historical selectors. PR2 adds the six-step DEV-01 synthetic
pilot, observation/relation contracts, annotation preparation and a manual.
It does not implement PR3-PR5, a loader, replay engine, grouping, rankers, metrics,
real annotation, collection or migration. The `replay` module supports only PR2
pinned dry-run/annotation-packet preparation, not the PR3 replay/ranking pipeline.

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
database, provider, HTTP client or collection module is imported. The validator
rejects .local, .env, dev-diaries, database paths and paths escaping the bundle.
Data is read only from the explicit manifest, including local provenance files.
The complete bundle is checked for integrity before any historical projection.
That trusted validation pass can read future documents and gold; it is not a
prediction input. Selectors inspect metadata before exposing selected text.

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
only an empty candidate list and explicit coverage states. Index/prompt/ranker,
official-metrics blocking, real provenance, full lineage and human semantic checks
remain pending. T25 is N/A: no schema migration or business database access.

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

Use the externally recorded current Manifest SHA from reports/PR2_REVIEW_FIXES.md;
do not derive your trusted pin from the file being checked on each run.

```powershell
$PIN = '<SHA256 recorded in PR2_REVIEW_FIXES.md>'
.\.venv\Scripts\python.exe -B -m evals.intelligence_v1.replay --manifest evals/intelligence_v1/manifests/dataset_manifest.json --manifest-sha256 $PIN --timeline DEV-01 --dry-run --out .local/g1-pr2-review-all
.\.venv\Scripts\python.exe -B -m evals.intelligence_v1.replay --manifest evals/intelligence_v1/manifests/dataset_manifest.json --manifest-sha256 $PIN --timeline DEV-01 --dry-run --step D0 --out .local/g1-pr2-review-d0
```

The output directory must be new, outside the bundle and not a sensitive/database
path. Pin/data/schema errors fail before output creation; existing files are never
overwritten. Compare two output directories byte-for-byte. `visible_steps.jsonl`
and run_metadata.json are administrator records; distribute only the current
packets/<step>/packet.json plus blank_form.json and the manual to an annotator.
There is no dependency on ignored local scripts. The CLI performs no network/model
calls or business imports, and rejects ranking flags such as --algo. Exported
packets contain no reference event/Claim/Gold answers. They are not human results.

Run original Ruff, full pytest, seed-sanity, pip check and frontend build separately.
The old 26-document seed is a smoke check, not G1 gold. Local build/tests do not prove
live-model quality, live feeds, CI, production deployment or G1-a acceptance.

See DATA_DICTIONARY.md for field/serialization policy and error codes, and
G1_BASELINE_LOCK.md for the repository starting state and fresh validation evidence.
