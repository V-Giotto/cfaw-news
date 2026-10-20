# G1-PR1: offline data contracts

This package implements schemas, source/rights checks, manifest integrity, family
split checks and pure historical selectors. It does not implement PR2-PR5, a loader,
replay engine, grouping, rankers, metrics, real annotation, collection or migration.

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

The only shipped data is the synthetic contract fixture. Rights for the configured
GitHub Blog source remain unknown and metadata-only; no network or license review
was performed. URL syntax/domain checks do not verify remote existence or truth.

Requirement coverage: T01/T02/T03/T20 and TZ01/TZ02/HASH01 at the contract boundary;
T22/T23/T26 basic negative cases; VER01/GOLD01/ISOLATION01 basic guards. T10 covers
only an empty candidate list and explicit coverage states. Index/prompt/ranker,
official-metrics blocking, real provenance, full lineage and human semantic checks
remain pending. T25 is N/A: no schema migration or business database access.

Run original Ruff, full pytest, seed-sanity, pip check and frontend build separately.
The old 26-document seed is a smoke check, not G1 gold. Local build/tests do not prove
live-model quality, live feeds, CI, production deployment or G1-a acceptance.

See DATA_DICTIONARY.md for field/serialization policy and error codes, and
G1_BASELINE_LOCK.md for the repository starting state and fresh validation evidence.
