# G2-PR1 offline contract skeleton

This package is a deterministic offline vertical slice, separate from the application and frozen
G1 code/data. It does not implement cross-document event merging, semantic Claim extraction,
independent evidence verification, focus/radar allocation, models, HTTP APIs, UI or DB migrations.
All items are **hold**. A source-attributed excerpt is not a verified technical finding.

## Reproduce a single step

From the repository root in PowerShell, using the existing virtual environment:

```powershell
& .\.venv\Scripts\python.exe -B -m evals.intelligence_g2.contracts --check-schemas
& .\.venv\Scripts\python.exe -B -m evals.intelligence_g2.replay `
  --manifest evals/intelligence_v1/manifests/dataset_manifest.json `
  --manifest-sha256 5608f6c9f20d283f9274308fa98a277c535eb0d8d828fd0d863d6e1faafde06f `
  --timeline DEV-01 --step D0 `
  --config evals/intelligence_g2/manifests/pr1_config.json `
  --config-sha256 9ff868f34f58d5196979377f8697f11ad561d3b730a6eb849cbee72a459a3c84 `
  --out .tmp/evals/g2/my-new-pr1-run
```

The output directory must not already exist. There is no overwrite/force, Oracle, network, model
or database option. The CLI accepts only the G1 bundle or controlled test copies under repository
`.tmp/`, a config under this package's `manifests/` or `.tmp/`, and output under `.tmp/evals/g2/`.
Sensitive paths, traversal, links and Windows reparse points are rejected before data access.
References under labels/events/claims are not prediction inputs. Exit codes: 0 success, 1 safe
JSON diagnostic, 2 argument error. A missing file or write failure produces `EXPORT_IO_ERROR`.

Outputs: `input_snapshot.json`, `config_snapshot.json`, `result.json`, `events.jsonl`,
`relations.jsonl`, `bundles.jsonl`, `items.jsonl`, `validation_report.json`, `run_manifest.json`,
and `trace.json`. All semantic files are canonical UTF-8/LF and deterministic for identical
inputs/configuration/runtime fingerprints. `relations.jsonl` is empty. Trace alone contains real
generation time and elapsed time; it binds the semantic manifest SHA. CLI stdout includes both
manifest and trace SHA values. The manifest does not hash itself or Trace.

The writer validates everything before staging flat artifacts and renaming the staging directory.
Write failures clean only the known staging files and never publish a partial final directory.
This is a local single-user writer, not a durable checkpoint or distributed transaction system.

## Pure API and historical bridge

```python
from evals.intelligence_g2.pipeline import run_g2_offline

result = run_g2_offline(replay_input=validated_g2_input, config=g2_config)
```

`load_replay_input()` in `bridge.py` calls pinned G1 `load_bundle/load_step`; `project_step()`
compares optional explicit candidate/context projections against that authoritative result.
The full `PredictionBundle`, paths and unselected bodies never reach the pipeline. G1 reads and
hashes whole JSONL files; the guarantee is that future bodies are not projected, validated as
current evidence or used by prediction. This is not a claim that future file bytes are never read.

G2 checks temporal metadata before serializing any nested payload, then revalidates models through
JSON, including nested `model_copy(update=...)` objects. A future object is rejected even when its
body is not serializable. It restores
origin/rights/provenance only from the selected G1 DocumentVersion. Visible lineage metadata is
retained to validate the root anchor without retaining old bodies. The pipeline is pure: it accepts
only G2 input/configuration, does no file IO, and has no tools/providers/DB/HTTP dependency.

Each document_id is a separate placeholder event. The key uses identity revision, dataset_id,
timeline_id and document_id; it excludes membership hashes, document versions, titles, as_of,
persona and dataset revision. PR2 must supply explicit identity lineage for real event merges/splits.
The first paragraph's raw prefix, at most 160 Unicode code points, is the only Claim candidate.
A blank prefix or absent paragraph yields an insufficient hold item with null factual text.
An excerpt/summary without a paragraph does not create a fake paragraph locator. Source text is
untrusted data and cannot execute instructions. Rights/origin checks are not live license audits.

## Verification and evidence boundaries

```powershell
& .\.venv\Scripts\python.exe -B -m pytest tests/evals/g2 -q --basetemp=.tmp/g2-new-tests
& .\.venv\Scripts\python.exe -B -m ruff check backend tests evals
& .\.venv\Scripts\python.exe -B -m evals.intelligence_v1.contracts --check-schemas
& .\.venv\Scripts\python.exe -B -m evals.intelligence_v1.validate --manifest evals/intelligence_v1/manifests/dataset_manifest.json --strict
& .\.venv\Scripts\python.exe -B -m pytest -q -o faulthandler_timeout=120 --basetemp=.tmp/g2-new-full
& .\.venv\Scripts\python.exe -B evals/run_baseline.py --output .tmp/evals/g2-new-seed.json
# In frontend: npm.cmd --offline run build
```

Use fresh evidence/temp directories. Do not install dependencies or access the production database.
The dedicated tests exercise G2-T01 through T10, all 35 existing replay steps, hash seeds 1/719,
future-poison bodies, exact candidate sets, origins/rights, citations, staging failure and audited
read/write/network boundaries. Database byte-preservation uses a synthetic temporary canary;
the real user DB is never opened even to fingerprint it. The Windows reparse test records whether
it exercised a native junction or a synthetic lstat flag when native creation is unavailable.

`fixtures/pr1/v1` contains five authored synthetic cases and separate AI draft/review history.
Only tests consume expected outcomes; prediction does not load these files. The default review
is **ai_development**, non-blind single-AI internal review, not independent human research.
There is no second-human or per-item administrator annotation gate. G1 frozen labels, reports,
manifests, original archive data, dependency locks and application behavior remain unchanged.
PR1 correctness does not establish G2 completion, G3 eligibility, semantic accuracy, algorithm gains,
real-user usefulness or production readiness. See `DATA_DICTIONARY.md` and `reports/PR1_ACCEPTANCE.md`.

## Versions and rollback

Main schema: `g2-pr1-1`; pipeline: `g2-pr1-rule-v1`; identity: `g2-document-lineage-v1`;
configuration: `g2-config-v1`; fixtures: `g2-pr1-fixtures-v1`.
Schema export is explicit (`--export-schemas`) and refuses to replace different existing schema
bytes. Future field/enum/hash/identity changes need a new revision and compatibility handling;
keep prior schemas/fixtures/results. Code hashes describe the actual working code even before a
commit; git_sha alone is not sufficient. Runtime/lock/schema fingerprints are in each manifest.
Rollback removes the G2 additions and the three new G2 .gitattributes rules; there is no DB rollback.
Keep the owner's existing untracked planning documents and all G1/legacy assets.

## PR2: relation prediction and historical event identity

`pr2/` is a separate offline package. PR1 contracts, singleton generation, schemas v1 and
fixtures remain unchanged. PR2 generates **no Claims, supporting/refuting evidence, briefing
tiers or new factual summaries**. An EventView is a representative document plus pointers to
every member/source; it is not a verified IntelligenceItem. Existing PR1 items/bundles stay immutable.

```powershell
& .\.venv\Scripts\python.exe -B -m evals.intelligence_g2.pr2.contracts --check-schemas
& .\.venv\Scripts\python.exe -B -m evals.intelligence_g2.pr2.replay `
  --manifest evals/intelligence_v1/manifests/dataset_manifest.json `
  --manifest-sha256 5608f6c9f20d283f9274308fa98a277c535eb0d8d828fd0d863d6e1faafde06f `
  --timeline DEV-01 --through-step D8 --strategy r1 `
  --config evals/intelligence_g2/manifests/pr2_config.json `
  --config-sha256 04995f9485f5f9355507e171286ac3f19daadd32b48dd58e4a0e4538c693befc `
  --out .tmp/evals/g2/my-new-pr2-r1
```

R1 is the default. Run r0/r1/r2 into three fresh directories with the **same** manifest, timeline
and cutoff. R0 calls the original G1 group_candidates with its fixed grouping defaults; no PR2
cannot-link rule repairs the R0 partition. R2 is an explicitly selected experiment, not an
automatic promotion. Neither embeddings nor a model are used. Prediction does not import the
reference loader, evaluator, G1 Oracle/full reference validator or application settings/database.

PR2 always replays the registered prefix, including earlier steps before D8. It has no external
state-resume or silent cold-start mode. Pure APIs live in pr2.pipeline/features/relations/grouping/
identity; the main entry is `run_grouping_step(grouping_input=..., config=...)`. PR1 Bridge supplies
the checked current projection; the full bundle stops at the bridge. Feature/history temporal
preflight runs before serialization, and output validation rejects forged features or identities.

Files include input_snapshots, results, features, relations, events, event_views, compatibility_links,
identity_log and identity_states JSONL; config_snapshot, validation_report, run_manifest and trace
JSON. Each JSONL row is a step envelope. results.jsonl is the complete contract for post-hoc
validation. The manifest pins semantic artifacts, current source, schemas, locks, config and the
candidate/context pool. Trace alone contains execution time; calls/tokens/cost remain zero.

Six labels are explicit: exact_duplicate, syndicated, same_event_different_evidence,
related_distinct_event, unrelated, uncertain. Hard subject/version/action/date conflicts precede
all positive rules. Upstream alone is insufficient: a testing citation is not a reprint. Complete
linkage requires **every** cross-group pair to allow merging, and records blocked bridges.
R2 additionally requires constrained target identifiers, text thresholds and a 14-day window.
Missing markers/short bodies/ambiguous subjects may abstain. No article fetching or permission
upgrade is performed. Self-described independent tests retain independence=unknown.

Keys are registered from a first-visible birth anchor, not the current member-set hash. Evidence
additions keep keys; revisions bind current evidence and target descriptors. Merges select the
earliest registered key (then lexical key); splits retire parents and allocate all-new children.
Alias creation/retirement and lineage append records. `resolve_identity(..., as_of=...)` returns
historical resolution; retired splits have explicit multiple successors. Published references
resolve exact key/revision/snapshot, without applying today's redirects. PR1 compatibility links
are time-scoped document membership, not semantic merge assertions. Window absence creates
dormancy, not a claim that nothing changed. Explicit document repurposing can create a new event.

Evaluation runs **after** prediction artifact verification:

```powershell
& .\.venv\Scripts\python.exe -B -m evals.intelligence_g2.pr2.evaluate `
  --runs .tmp/evals/g2/my-new-pr2-r0 .tmp/evals/g2/my-new-pr2-r1 .tmp/evals/g2/my-new-pr2-r2 `
  --reference-manifest evals/intelligence_g2/fixtures/pr2/v1/reference/manifest.json `
  --reference-manifest-sha256 3302a030c68c30184b0948456f9a57eaf07472fe3d8b00f2ff29737b93753d3d `
  --out .tmp/evals/g2/my-new-pr2-evaluation
```

The comparator refuses mismatched pools, contexts, prefix, pins or runtime/configuration. Existing
G1 pair references are used only when their exact versions and evidence_at are visible; missing
references remain uncertain. Uncertain/missing labels are not negative gold. Reports separate
clustering FP/FN from pair classification, retain unique pairs and repeated time observations,
and use null for undefined ratios. Source coverage is structural retention, not semantic support.

The 12 synthetic trajectories/16 steps, plus the existing five G1 trajectories and ancillary replay
steps, are **non-blind ai_development** data. Codex authored implementation and references and
performed internal review. No second human gate or independent-research claim applies. See
reports/PR2_ACCEPTANCE.md for actual checks, metrics, failures and remaining limits. Rollback
removes only PR2 additions and these appended docs; preserve PR1, G1 and all historical outputs.

## PR3: paragraph-grounded claims and evidence

`pr3` consumes a pinned PR2 prediction run and inherits event keys/revisions exactly. It selects
whole visible paragraphs with a finite grammar, retains source attribution and grounded field
spans, and assembles bundles with scope, dependency, conflict, correction and coverage records.
`supports/refutes` describe constrained relationships between reports; they do not establish
truth. `independently_supported` is reserved and forbidden at runtime; confirmed independent
support stays zero and actual independence stays unknown. No briefing templates or LLM exist.

```powershell
python -B -m evals.intelligence_g2.pr3.contracts --check-schemas
python -B -m evals.intelligence_g2.pr3.replay --grouping-run <PR2-run> --grouping-manifest-sha256 <external-pin> --through-step D8 --config evals/intelligence_g2/manifests/pr3_config.json --config-sha256 <external-pin> --out .tmp/evals/g2/<new-directory>
python -B -m evals.intelligence_g2.pr3.evaluate --run <PR3-run> --reference-manifest evals/intelligence_g2/fixtures/pr3/v1/reference/manifest_v2.json --reference-sha256 cae113075d3fd366199e0b92886143e7dc893361b20021b50ffaeae12511bfdf --out .tmp/evals/g2/<new-evaluation-directory>
```

Prediction and evaluation use separate processes. Parent artifacts and config/schema/source/lock
hashes are checked; selected-step temporal metadata precedes payload validation. Whole-file bytes
are read/hashed, including future rows, but future text is not extracted or validated as a model
until its step. A reference-free prediction path is audited. Production DB/private data/network
are outside this offline pipeline. Output is atomic, never overwritten, and restricted to `.tmp/evals/g2`.

Each JSONL stream has a cursor and its named collection. `claim_history` contains new transitions
and memberships; `evidence_states` holds append-only prior assessments/history and immutable claim
and quote archives. No full candidate/persona snapshot is re-exported. `trace.json` alone carries
actual execution time/latency and zero model usage; the manifest hashes semantic files without
self-hash cycles. Parent audit pins do not derive claim IDs.

Initial prediction/extraction labels remain frozen. Reference v2 adds explicit direction and
field/gap labels after implementation became visible; supplement_provenance.json discloses this
non-blind addition. T20's unchanged PR2 can split a repository anchor from lexically named copies;
PR3 records exact-copy dependency without repairing event grouping. See PR3_ACCEPTANCE.md for
current checks, actual pins and open gates. Rollback removes only PR3 additions and appended docs.

## PR4 deterministic candidate items

`pr4` consumes pinned PR3 prediction runs. It inherits event keys/revisions, projects event-authorized
claims/quotes and source permissions from the actually selected PR2 prefix, and runs closed Chinese
templates with original-language quotations. It does not read Persona, labels, current Article data,
production databases or providers. `focus/radar/hold` are G2 candidate tiers, not G3 ranking or quotas.
An event always has one item (possibly a fact-free hold); no events produce no items.

```powershell
$pr4Config = 'evals/intelligence_g2/manifests/pr4_config.json'
# Frozen original-byte pin; the canonical config snapshot may have different formatting/defaults.
$pr4Pin = '906d0fd33dfaa70ee2a9c093d22cd4b591f1b742c503890cbaa4262ffe8d0400'
python -B -m evals.intelligence_g2.pr4.contracts --check-schemas
python -B -m evals.intelligence_g2.pr4.replay `
  --evidence-run <PR3-run-under-.tmp/evals/g2> `
  --evidence-manifest-sha256 <externally-recorded-parent-pin> `
  --through-step D8 --config $pr4Config --config-sha256 $pr4Pin `
  --out .tmp/evals/g2/pr4-example-001
```

The pure `generate_items(generation_input=..., config=...)` accepts no paths/tools/Persona.
`ItemGenerator.generate(GenerationRequest)` is a presentation boundary only: approved claims,
citations, assessments, transitions, mandatory risks and a character ceiling. The sole implementation
is `RuleItemGenerator`. Identity, permissions, status and candidate tier remain outside the adapter.
No LLM adapter, mock, network provider or PR5 failure workflow is implemented here.

FactText bindings and template reconstruction are checked independently of citation existence.
Independent truth remains not_evaluated. Conditional interpretation starts with “推断”; full scope
and source-attributed/unverified risks accompany important claims. Mandatory lifecycle and conflict
sides share the three-claim limit; if all required sides or cautions cannot fit, the item becomes hold.
No scope, negation, number or risk is truncated. Duplicate statements have one representative and all
source pointers remain attachments. Summary rendering is explicitly secondary/unverified.

Schema v4 is separate from PR1–PR3. Three frozen character budgets are low 800/220/160,
standard 1200/320/160 and high 1800/480/160 (focus/radar/hold). The count conservatively includes
headline/body, detail summaries, inference and risk text. Radar's actual quoted body plus all required
cautions has at most two sentences; cautions render as one semicolon-separated second sentence.
The 90/12-second estimates are only legacy G1 coarse costs; its top-3/top-12 and global budgets
are not applied to PR4. Unresolved lifecycle targets, sensitivity gaps, unsafe text and permissions
produce observable hold reasons. Historical metadata/quotes never come from future or reopened bodies.

Outputs: items, snapshots, minimal citations, snapshot_states, input_projections, validation_report,
config_snapshot, run_manifest and zero-model trace. Input projections export IDs/hashes and source
metadata, not Persona or the whole claim/body archive. All semantic files are canonical UTF-8/LF.
Content and snapshot identity are separate; merge/split snapshots link all predecessor identities.
Runs rebuild an auditable prefix and atomically write a new directory under `.tmp/evals/g2` only.
Whole-file hashing can read future bytes; future text objects are not validated/generated until visible.

`python -B -m evals.intelligence_g2.pr4.evaluate --help` documents the separate pinned-reference
development comparison. It verifies prediction artifacts before reading references; no metric returns
to the generator. Fixture v1 is retained as an invalid-input draft. V2 corrects synthetic URL/content
format with unchanged expected tiers; provenance records disclose this non-blind correction. Feed-summary
rendering is tested as an explicit synthetic contract projection because the frozen G1 synthetic bridge
only permits synthetic_text. It is not presented as a real-source end-to-end validation.

See `reports/PR4_ACCEPTANCE.md` and `reports/PR4_STYLE_EXAMPLES.md` for actual checks and product
examples. AI development review is non-blind and is not independent research evidence. Rollback removes
only PR4 additions and these appended sections, retaining G1/PR1–PR3 and all historical outputs.


## PR5 constrained expressions (offline mock only)

PR5 adds a presentation sidecar, never mutates PR4 rule Items or evidence. Modes are `rule` and default `mock`; no live endpoint/key/tool flags exist. `IntelligenceGeneratorProtocol` uses only an event-authorized request. Closed style reconstruction preserves exact quotations, qualifiers, scope, risks, tiers and fact revisions. Free drafts remain synthetic-only `not_selected/not_verified`; AI development review never promotes them. No independent truth verification is claimed.

```powershell
python -B -m evals.intelligence_g2.pr5.contracts --check-schemas
python -B -m evals.intelligence_g2.pr5.replay --rule-run <PR4-run> --rule-manifest-sha256 <external-pin> --through-step D8 --mode mock --config evals/intelligence_g2/manifests/pr5_config.json --config-sha256 <external-pin> --out .tmp/evals/g2/<new-run>
python -B -m evals.intelligence_g2.pr5.evaluate --run <PR5-run> --run-manifest-sha256 <external-pin> --reference-manifest evals/intelligence_g2/fixtures/pr5/v1/reference/manifest.json --reference-sha256 <external-pin> --out .tmp/evals/g2/<new-evaluation>
```

Outputs: presentations, expression snapshots/states, assessments, permitted synthetic drafts, audit-only input projections, validation report, config snapshot, manifest and separate timing/usage trace. SHA pins bind actual bytes; semantic identities exclude timing and runtime failure telemetry. One request per eligible Item, no repairs/retries, concurrency 1; 32KiB request, 8KiB response, 2s mock timeout; per-step/run request caps 16/128. Unknown usage stays null. Mock usage is never real model consumption. Input/parent failures abort without output, model failures preserve exact rule Items, external cancellation/stale requests never publish.

Tests T37-T46 and reports/PR5_ACCEPTANCE.md distinguish implemented checks, mock fixtures, AI non-blind development review and untested real providers. True HTTP transport, credentials, PR6 acceptance and production integration are deferred.


## PR6: offline closeout (g2-pr6-1)

`pr6` composes existing native PR1–PR5 stage APIs. Final release commands require
an actual approved HEAD commit and exact scoped worktree/tree bytes. No automatic
commit/push is performed. Uncommitted smoke/preflight evidence is not acceptance.

```powershell
python -B -m evals.intelligence_g2.pr6.reproduce --source-commit <approved-SHA> --campaign evals/intelligence_g2/manifests/pr6_campaign.json --campaign-sha256 <external-pin> --out .tmp/evals/g2/<new-campaign>
python -B -m evals.intelligence_g2.pr6.evaluate --run <campaign> --run-manifest-sha256 <pin> --reference-manifest evals/intelligence_g2/fixtures/pr6/v1/reference/manifest_v5.json --reference-sha256 <external-pin> --out .tmp/evals/g2/<new-evaluation>
python -B -m evals.intelligence_g2.pr6.checks --source-commit <same-SHA> --out .tmp/evals/g2/<new-checks>
python -B -m evals.intelligence_g2.pr6.acceptance --profile g2_development --run <campaign> --run-manifest-sha256 <pin> --evaluation <evaluation> --evaluation-manifest-sha256 <pin> --checks <checks.json> --checks-sha256 <pin> --ai-review <output-bound-review.jsonl> --ai-review-sha256 <pin> --out .tmp/evals/g2/<new-acceptance>
```

Create AI review after inspecting sealed predictions/evaluation. It must bind their
pins and actual source commit, record real creation time/model-or-unknown/context
and findings, and declare nonblind ai_development/independent_validation=false.
Programmatic development_checks.jsonl is not an AI review substitute.

The full campaign covers all 35 G1 steps, 29 new synthetic cases (12 error modes),
R0/R1 × three budgets × rule/mock × seeds 1/719 × canonical/reverse candidates,
plus standard R2 and independent early prefixes. Time is never reversed. Each job
restarts its own history. Prediction workers have no reference/Oracle/tool/network
capability. Mock fault scripts are closed versioned inputs, not reference-driven
answer generation. Late429 exercises real timer/cancellation handling.

The E09-secondary authored input is intentionally invalid under frozen PR1:
synthetic origin permits only synthetic_text. Its v3 input and failed preflight
remain preserved; v4 reference explicitly expects ORIGIN_MISMATCH. It is not a
successful native secondary full-chain control. Secondary expression positives
remain in unchanged PR4/PR5 stage tests. No upstream permission gate was widened.

Only complete, sealed campaigns can be evaluated. Post-evaluation recomputes stage
outputs and compares exact job sets, pools, seeds/orders, prefixes and immutable
rule Items. R0 errors remain visible. Metrics expose reference coverage and null
zero/missing denominators; no G1 Claim is relabeled as extraction gold. AI semantic
review and source-truth/independent research remain separate.

`pr6_required_tests.json` freezes complete parameterized nodeids and test-source
bytes. The pytest plugin writes original nodeids into JUnit. Verification rejects
omissions, duplicates, failures, unexpected tests and non-exempt skips. Only exact
platform/node/reason exemptions are accepted. G1's 552-node/45-source projection is
checked separately without editing its frozen acceptance inputs. Legacy G1 Oracle
runs are isolated diagnostics, never G2 predictions or scores.

Formal checks run Ruff, seven schema checks, G1 strict, G2/evals/full pytest,
legacy G1 reproduce, seed and offline frontend build once each. Failed full pytest
is retained and not retried automatically. Any required sandbox escalation needs
fresh authorization. CI smoke is smaller and is not full campaign acceptance.

See docs/G2_G3_HANDOFF.md. Optional human research does not block engineering;
G3 planning and administrator acceptance are separate decisions. No live model,
keys, production DB, UI, G3 ranking or automatic Git publication is added.


PR6 路径兼容修复：evaluate/acceptance/checks 的输入目录先转为绝对路径，再走原有边界与 reparse 检查；旧 G1 reproduction.json 中 Windows 相对工件名仅在 legacy 导入边界转换分隔符。PR6 自身 manifest 仍要求严格 POSIX 相对路径，驱动器、UNC、ADS、父路径及 SHA 错误继续拒绝。修复不修改 G1 输出字节、Schema 或预算；需新的源码提交和同提交验收，旧全量通过不冒充新源码结果。

PR6 验收门禁审查修复：默认 R1 的已知连续性参考若 key 不匹配或端点缺失，
后评测产生 `continuity_mismatch` 错误并阻断 H02。H02 还直接检查各 R1 cohort
的连续性分子等于分母，不能仅凭 `ok` 标志或 FP=0 通过。缺参考仍为
`null/no_applicable_reference`；R0 连续性缺口单列为非成功基线，不混作 R1 错误。
JUnit 内部仍精确比较原始 nodeid、Counter 和 skip 豁免；拒绝诊断的既有 `field`
仅含 `node_sha256:<64位摘要>`，不回显参数、失败文本或 skip reason。
Schema、输入/参考、预算及 PR1–PR5 不变；修复后的正式验收须另绑新提交及新执行证据。
