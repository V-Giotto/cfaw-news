# G2-PR3 implementation and acceptance evidence

**PR3 implementation/scoped checks complete; full-regression merge gate PASS.**

Profile: `ai_development`; same Codex authored code, synthetic cases, references and internal review. Non-blind; independent research and underlying fact verification are not_evaluated. No second-human gate.

## Baseline and implementation

HEAD `76ef14b531842ae449c4f907302218d2e2ea4c90` unchanged. 327 of 329 existing baseline files are byte-identical; README/data dictionary have verified exact original prefixes plus PR3 additions. G1 frozen inputs, PR1/PR2 code/schema/fixtures/reports/labels, locks and .gitattributes are unchanged.
PR3 adds strict schema v3, whole-paragraph extraction, grounded scope/numeric values, source attribution, dependency/citation/conflict/correction/withdrawal/coverage models, append-only state, pinned parent-run loader, atomic CLI, separate evaluator and tests. Event keys/revisions are inherited from validated PR2 output. No PR4 templates, PR5 LLM, API/UI or production DB changes. No network, external model, private-data access, migration, commit or push.

Claims preserve raw paragraphs. Source attribution is distinct from truth; independently_supported is forbidden and confirmed independent support is zero. Unsupported scope/negation/units abstain; long/sensitive paragraphs are excluded whole. History stores prior extracted quotes, never reopens old/future bodies.

## Actual checks

| Check | Current result | Exit |
|---|---|---|
| Full G2 suite | 203 passed: PR1 70 + repaired PR2 58 + PR3 75 | 0 |
| PR2 identity compatibility | R0/R1/R2 each replay all 35 G1 steps; keys/revisions/partition exactly retained; inside suite | 0 |
| PR3 matrix | 23 pinned prediction API runs, then 23 evaluation API runs in a separate process; 35 G1 + 19 synthetic steps | 0 / 0 |
| Ruff, four Schema checks, strict G1 manifest | all passed, original G1 pin retained | all 0 |
| seed / offline frontend build | passed; seed uses in-memory DB, not production data | 0 / 0 |
| Current full pytest | 754 passed, 1 skipped; see full-tests-final.command.json/full-final.xml | 0 |
| Loopback environment probe | bounded child timed out; environment evidence only, not a product-suite verdict | 3 |

The full suite reports one StarletteDeprecationWarning about httpx testclient usage. No dependency was installed or changed. The sole skip is the existing G1 symlink test because Windows cannot create a symlink (1314); its test name and actual JUnit reason are retained below.

Synthetic metrics: 28/28 exact extraction, 28/28 types/states, 46 direction observations, 150/150 explicit scope fields, 28/28 numeric results, 3/3 required gaps; zero frozen-reference error records. Original extraction labels were frozen before implementation. Reference v2 direction/quality supplements were added after implementation visibility, before full metric execution; provenance is retained. These are non-blind development agreements, not generalization evidence.

G1: 35 unscored PR3 semantic steps, 137 locator observations and 218 unknown link observations. Successful structural replay is not a semantic score. Repeated time observations are not independent samples. Source-attribution review targets only that a source published the exact paragraph; it does not establish performance or independence.

## T19-T28 evidence and isolation

| Cases | Actual assertions |
|---|---|
| T19-T21 | exact paragraphs/units/quantifiers/grounded scope, no fake numbers or independent upgrades; copies dedup but citations do not prove independence |
| T22-T23 | different/incomplete scope and nonexclusive numbers abstain; same explicit scope/opposite reports yield two-sided refutes and disputed |
| T24 | explicit unique own-source correction/withdrawal, immutable old claims/assessments, no correction from unmarked edits, no repeated transition |
| T25 | legal citation locator plus unsupported target remains unknown; forged support rejected separately |
| T26 | future metadata rejects before poison access; future steps opaque early; cross-event and historical-as-current refs rejected; no result directory |
| T27-T28 | no pseudo-paragraphs, summary downgrade, table/completeness gaps, whole-quote limits, offline/unknown coverage and empty input without no_change |
| General | strict copied-model validation, time/history state tampering, budgets, merge/split births/memberships, seeds 1/719, prefix bytes, staging failure/overwrite, pin/tamper checks and audited reference/network/private/DB/outside-write denial |

Audit uses a synthetic canary DB and checks it unchanged; it never hashes/opens the production DB. Parent loader reads/hashes whole prediction files, but future nested bodies do not reach extraction. Cross-family research labels are evaluator-only; runtime citation authorization uses the predicted event/current version/lineage boundary.

T20 exposed conservative PR2 separation of repository and lexical subject anchors. PR3 keeps those events intact and records dependency from explicit reprint plus exact visible upstream body. No PR2 source or grouping threshold was modified.

Current full-suite counts and actual skip reasons are in verification-summary.json and full-final.xml.

## Pins and reproduction

- Config file SHA: `837ae529840f9e7f72d27a8609859db8812a60a2bef1a1785ef1e76c1ada8d42`.
- Reference v2 manifest SHA: `cae113075d3fd366199e0b92886143e7dc893361b20021b50ffaeae12511bfdf`; v1 extraction expectation SHA remains `6cf56fa720c1f8fae7528394ae1525d582e67bc590fdef9fb62ea75076289a1e`.
- Root fixture manifest SHA: `94a8d248900af2202755d92b60631e68af24ae0ba673032503dc7492cdf6b918`.
- Evidence directory: `D:\agent_project\cfaw-news\.tmp\g2-pr3-evidence`. Every command record contains actual argv/cwd/UTC times/exit/elapsed/log SHA. JUnit, source-snapshot, preservation, matrix phase records and verification-summary are retained.
- artifact-index.json binds report, source snapshots, command logs, JUnit and fixture provenance without a self-hash cycle. Source versions and limitations are in appended README/data dictionary.

Actual commands (matrix entries are API calls recorded in predictions/evaluation JSON, not claimed as separate CLI invocations):

Actual full-suite skips:

```json
[
  {
    "classname": "tests.evals.test_provenance_and_rights",
    "name": "test_symlink_outside_bundle_rejected_if_supported",
    "message": "symlink creation unavailable: 1314",
    "detail": "D:\\agent_project\\cfaw-news\\tests\\evals\\test_provenance_and_rights.py:94: symlink creation unavailable: 1314"
  }
]
```

**g2-sealed** — exit 0, 104.260s; log SHA `687bec917bc6185f811bab21a9366f9dac80d55e26e0e1f195dca3e1b2046507`.

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "pytest", "tests/evals/g2", "-q", "-p", "no:cacheprovider", "--basetemp=.tmp/g2-pr3-g2-sealed", "--junitxml=.tmp/g2-pr3-evidence/g2-sealed.xml"]
```

**matrix-prediction-sealed** — exit 0, 18.211s; log SHA `f149d39fca8631e6291484543e3bb8cda55a08dae51ad5c49bc164df597d8b9d`.

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", ".tmp/g2-pr3-evidence/run_matrix.py", "matrix-004"]
```

**matrix-evaluation-sealed** — exit 0, 16.094s; log SHA `3ac2876bd4ba27794466011ba43740fd794aa925f29f10e42b9d3a79f1b34ccf`.

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", ".tmp/g2-pr3-evidence/evaluate_matrix.py", "matrix-004"]
```

**ruff-sealed** — exit 0, 1.437s; log SHA `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`.

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "ruff", "check", "backend", "tests", "evals"]
```

**schema-g1** — exit 0, 1.129s; log SHA `ad541cc67a0a6b6ce43b44815465079cd8b104a992b74d4c1a670e767b546d7d`.

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "evals.intelligence_v1.contracts", "--check-schemas"]
```

**schema-pr1** — exit 0, 1.154s; log SHA `a809da7e3eeb608fdce4300ac3ac61ce71461ebdd5e50803baaede51ffa8f3e1`.

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "evals.intelligence_g2.contracts", "--check-schemas"]
```

**schema-pr2** — exit 0, 1.230s; log SHA `ffc3a2599f9fe6d9e1046f4e8cf20d19c948e76b87b838f97e144cb2df555923`.

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "evals.intelligence_g2.pr2.contracts", "--check-schemas"]
```

**schema-pr3** — exit 0, 1.359s; log SHA `27303a3b8249fbfd930481b365912d74dd58bf322a1a4e137ceee3509558cf51`.

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "evals.intelligence_g2.pr3.contracts", "--check-schemas"]
```

**manifest-g1** — exit 0, 1.694s; log SHA `ae200140ab0b4b55cfc9964459369e2e3a0970039dbfb7359501ad56ac18aa38`.

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "evals.intelligence_v1.validate", "--manifest", "evals/intelligence_v1/manifests/dataset_manifest.json", "--strict"]
```

**seed** — exit 0, 2.140s; log SHA `7d22a98c5abf52689934d70bc28a593f70ecdbca754290ce82a47545758888ef`.

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "evals/run_baseline.py", "--output", ".tmp/g2-pr3-evidence/seed.json"]
```

**frontend** — exit 0, 17.418s; log SHA `6e7d67d6bb62a6e9e4d6d763eb234eae6d4b1fb02feb6a620cac5cf45253bd06`.

```json
["C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "npm.cmd --offline run build"]
```

**loopback-probe** — exit 3, 5.206s; log SHA `d11837bd9da0ceae8ceaccb4b7208dab8dcaf2e7524465bece0a0c0a5eae553a`.

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", ".tmp/g2-pr2-review-fixes/loopback_probe.py"]
```

**mixed-negation-red** — exit 1, 3.255s; log SHA `74c084553f6e4eff1a05e7333bff84c4e6e578420ad233652f34a9c702ea3d70`.

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "pytest", "tests/evals/g2/pr3/test_scope.py", "-k", "positive_result", "-q", "-p", "no:cacheprovider", "--basetemp=.tmp/g2-pr3-negation-red", "--junitxml=.tmp/g2-pr3-evidence/negation-red.xml"]
```

**mixed-negation-green** — exit 0, 2.858s; log SHA `d35ef686a9206428aea4eeb773d61359d75776722cc7b0013c041982bc40b1d1`.

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "pytest", "tests/evals/g2/pr3/test_scope.py", "-k", "positive_result", "-q", "-p", "no:cacheprovider", "--basetemp=.tmp/g2-pr3-negation-green", "--junitxml=.tmp/g2-pr3-evidence/negation-green.xml"]
```

**stage-boundary-red** — exit 1, 3.266s; log SHA `df458e376279ad658ba63462353faf27ab529676d5947fc9e8aabf92a5bcc888`.

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "pytest", "tests/evals/g2/pr3/test_stage_boundaries.py", "-q", "-p", "no:cacheprovider", "--basetemp=.tmp/g2-pr3-stage-red", "--junitxml=.tmp/g2-pr3-evidence/stage-red.xml"]
```

**stage-boundary-green** — exit 0, 2.858s; log SHA `02e251eec22215a7093ce5aab89886ae775d1dc7bd3c1cca838fb2d74185701e`.

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "pytest", "tests/evals/g2/pr3/test_stage_boundaries.py", "-q", "-p", "no:cacheprovider", "--basetemp=.tmp/g2-pr3-stage-green", "--junitxml=.tmp/g2-pr3-evidence/stage-green.xml"]
```

**config-hash-red** — exit 1, 5.686s; log SHA `98b10696675a63adda3d885292fa0a423b91740c1d39450752d7e8de90a5ab01`.

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "pytest", "tests/evals/g2/pr3/test_config_hashes.py", "-q", "-p", "no:cacheprovider", "--basetemp=.tmp/g2-pr3-config-red", "--junitxml=.tmp/g2-pr3-evidence/config-red.xml"]
```

**config-hash-green** — exit 0, 5.491s; log SHA `5421c138ab798922089ec311e1a5ea99a1372d51c25c1a2cebd74331a6e68bf5`.

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "pytest", "tests/evals/g2/pr3/test_config_hashes.py", "-q", "-p", "no:cacheprovider", "--basetemp=.tmp/g2-pr3-config-green", "--junitxml=.tmp/g2-pr3-evidence/config-green.xml"]
```

**g2-final** — exit 1, 100.371s; log SHA `db110c9c63e39869a64d6254e2694ecd616b8cff675cf6afe87c3e461def2b90`.

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "pytest", "tests/evals/g2", "-q", "-p", "no:cacheprovider", "--basetemp=.tmp/g2-pr3-g2-final", "--junitxml=.tmp/g2-pr3-evidence/g2-final.xml"]
```

**full-tests** — exit 4294967295, 191.856s; log SHA `0368eb0d75b4f5382dfdcb1861819cb08220da94f6b1234ec7d28c1b8dc14349`.

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "pytest", "-q", "-o", "faulthandler_timeout=120", "--basetemp=.tmp/g2-pr3-full", "--junitxml=.tmp/g2-pr3-evidence/full.xml"]
```

**full-tests-current** — exit 4294967295, 518.053s; log SHA `d66a2f4fad2379a9d00519d6f7dd8b21e25ad7171d40ff80c23f4739c088c7fc`.

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "pytest", "-q", "-o", "faulthandler_timeout=120", "--basetemp=.tmp/g2-pr3-full-current", "--junitxml=.tmp/g2-pr3-evidence/full-current.xml"]
```

**full-tests-final** — exit 0, 683.233s; log SHA `548c9b465a90a7cf96078f0dd1aacbd02fb3702e9eb2c8fcf7baff24208ca8fc`.

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "pytest", "-q", "-o", "faulthandler_timeout=120", "--basetemp=.tmp/g2-pr3-full-final", "--junitxml=.tmp/g2-pr3-evidence/full-final.xml"]
```

## Open gates, limitations and rollback

Remaining gate: none in the requested PR3 local regression scope; administrator merge remains manual.

Full command was executed as recorded above.

```powershell
& .\.venv\Scripts\python.exe -B .tmp/g2-pr3-evidence/record.py full-tests-final D:/agent_project/cfaw-news/.venv/Scripts/python.exe -B -m pytest -q -o faulthandler_timeout=120 --basetemp=.tmp/g2-pr3-full-final --junitxml=.tmp/g2-pr3-evidence/full-final.xml
```

Initial full-tests was deliberately stopped after a new mixed-negation counterexample; full-tests-current was deliberately stopped after config-hash-red exposed a raw-file/snapshot SHA mismatch. Both retain exit 4294967295 and partial logs, and neither is counted as PASS. g2-final recorded 1 failed/198 passed due to a parent PR2 atomic rename WinError 5; that failed attempt is preserved, with no retry/permission relaxation in runtime code. Initial review/report/root-manifest/source snapshots are retained in pre-negation/, and pre-config-fix code is retained in pre-config/. Later evidence binds current code.

Raw config bytes are pinned at the entry point; the canonical config snapshot has its own artifact SHA, and the parsed snapshot must match the semantic config digest. A whitespace-only reformat can change the raw pin without invalidating a correctly pinned producer snapshot.

Grammar is deliberately limited: implicit entities, unmarked scope, general entailment, complex units and ambiguous correction targets can remain unknown. Same-source correction currently requires same visible document lineage plus explicit previous numeric target; broader cross-document targets remain unresolved gaps. No original-source availability, external experiment replication, real-user quality, independent semantic validation, G2 completion or G3 eligibility is claimed.

Rollback removes only PR3 package/schema/config/fixtures/tests/report and appended docs. Preserve G1, PR1/PR2, initial workspace documents and all historical outputs; no DB rollback.
