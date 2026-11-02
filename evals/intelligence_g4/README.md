# G4 PR1 offline contract feasibility

Scope: strict runtime/document/config/status/briefing/interaction contracts and a
bounded native G2 replay. This package is not installed application functionality.
There is no DB, HTTP integration, frontend, feed fetch, provider or user-history write.

`runtime_local_v1` is separate from G3's `accepted_g2` and
`synthetic_contract_probe`. It does not issue G2/G3 acceptance. The current G3
runtime adapter is unavailable: even valid native G2 results return an explicit
nonpublishable `raw_news_only` or `insufficient_evidence` result, with no plan.

Use the existing environment from the repository root:

```powershell
python -B -m pytest -q -p no:cacheprovider evals/intelligence_g4/tests --basetemp .tmp/evals/g3/g4-pr1-tests
python -B -m evals.intelligence_g4.schema --check-schemas
python -B -m evals.intelligence_g4.slice --input <local-input.json> --input-pin <independently-saved-exact-byte-sha256> --out <fresh-local-output>
```

CLI input/output paths must be inside `.tmp/evals/g3/`. Input is canonical UTF-8
JSON (including defaults), capped at 2 MB. Do not compute a replacement trusted
pin from a rejected input. Negative validation creates no output directory.
Successful CLI execution means the bounded feasibility result was validated;
`publishable` and `g3_runtime_validated` remain false.

Current result schemas under `schema/v2` are compared against actual derived bytes
and the exact file set. Historical `schema/v1` bytes are preserved. Input wire v1
now checks the complete captured document chain across steps; rollback, forks and
missing intermediate versions are rejected. Each v2 native-step result includes
requested-window coverage diagnostics with explicit unknown/unobserved intervals;
the unchanged G2 `coverage_gaps` list is not a full-window guarantee.
Export is an explicit exclusive-file authoring action, never import IO.
The implementation, source/config pins, command logs and limitations are in
`audit/G4_BASELINE.json`, `audit/G4_ENTRY_REUSE_AUDIT.md`,
`audit/g4/pr1/IMPLEMENTATION_REPORT.md` and `docs/adr/G4_RUNTIME_LOCAL_V1.md`.
Those original pins/results are historical after review fixes; see
`audit/g4/pr1/REVIEW_FIXES.md` and its separate baseline/release pins for current code.

New tests live outside `tests/` because the frozen G3 inventory binds that entire
Python file set. They are explicitly run and independently inventoried; the old
suite and G3 inventory still run in full. No old test or frozen inventory is hidden,
skipped, rewritten or weakened. Tests are authored, synthetic, nonblind development
material. Invented real-origin example.com metadata is only a contract probe; it
is not fetched news, a license audit or real-source validation. One separate test
loads an existing externally pinned G3 synthetic probe and confirms its B4/planner
output cannot be relabelled as a runtime briefing.
