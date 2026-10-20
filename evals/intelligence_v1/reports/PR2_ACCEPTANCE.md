# G1-PR2 §11.2 验收记录

> 本文件保留历史 v2 的测试和冻结证据。三项独立审查修复及当前复现入口见
> [PR2_REVIEW_FIXES.md](PR2_REVIEW_FIXES.md)；不要将下文 v2 指纹用于当前 v3 输入。

日期：2026-10-20（Asia/Shanghai）。状态：**技术交付通过；真实人工初标/双标和语义测量待完成**。
不宣称 PR2 人工环节或 G1-a 全面通过。本报告不属于算法输入，避免 Manifest 自引用。

## 基点、边界与冻结

- 起始与结束 Git HEAD：`43cebab0e4e291452ec4356848017d90ae9f7128`；起始工作区干净。
- 当前 PR2 为未提交改动；验收针对工作区实际文件，不能把基点 SHA 当作包含 PR2 的提交。
- 最终数据：`pr2-dev01-v2`；Schema `g1-pr2-1`；手册 `dev01-guide-v1`。
- Manifest SHA-256：`f949daaaec802e75a0d53e2a878536f38008d361b8fdcc3d18f9fd945f8ed0e2`。
- JUnit SHA-256：`8bb54f86dffa8cd67f7b32656519c67e59731f41c51dd96465ada92a5670566a`。
- `run_metadata.json` / `frozen-inputs.json` / 测试与命令日志在忽略目录 `.local/g1-pr2/`。
- 只改 evals/intelligence_v1 和 tests/evals；没有业务库访问、迁移、联网抓取、在线 LLM、依赖安装、commit/push。
- 没有 loader/replay/rankers/metrics CLI，未实施 PR3–PR5。

PR1 v3 完整包保留于 `.local/g1-pr2/pr1-contract-v3/`，其 Manifest SHA 为
`f0661c814eb8cf1e120a6681e908cbe5be526f080d9a6a9c7f49b655d5638ccf`。
其所有受控文件已对照旧清单校验，12 个 fixtures 文件与当前包逐字节一致。
旧业务、旧六个测试文件、archive、migration provenance、依赖锁、AGENTS 和原需求均未改动。

PR2 v1 曾冻结为 `19facbf60c8bd93fffc86214b45622bd259852062d9373828987c0e75edcb062`，
全量 262 passed / 1 skipped。随后补上有限测试 Claim 的 p1 方法/范围引用（已有 p2 结果引用）。
先新增断言，观察失败，再修数据；v1 完整受控包和匹配的测试源码/指纹保留于本地
`frozen-pr2-dev01-v1/`、`frozen-v1-tests/`、`frozen-v1-inputs.json`；未在 v1 名下重哈希。
v2 不改任何文档正文、Claim 文本、gold 或人的记录，最终全量测试在 v2 冻结后执行。

## 数据与接口变更

DEV-01 为正式 pilot / developer data，全部合成。新增：

- 7 个文档内容版本 / 6 个文档身份 / 8 次观察；官方同 URL 修订、重复观察、3 篇转载、有限独立测量、同项目不同公告。
- 6 个 as_of：D0/D1/D3/D4/D5/D8；1 个 persona 的 2 个历史版本。
- 2 个参考事件、6 个成对关系、7 条 Claim 状态记录、2 个覆盖窗口、1 个 dev family。
- Claim 原文稳定，按 valid_as_of 追加状态；可见历史段落保留。独立测量同时引用 p1/p2，限制在 Linux/GPU、v1.0、TinyBench-3、两次运行。
- Observation / EventRelation / Annotation / Adjudication 严格模型和四个 Schema；原业务及文档/Claim/Gold 调用契约不变。
- 纯 pilot 帮助函数只生成单步标注包、选择评测侧 Claim 状态、报告引用定位；不做排序/自动语义裁判。
- 标注手册、数据卡、空白表单、无结果的人工状态文件；DEV-01 三个 labels 文件为空。

当前 Manifest 汇总还包含原 PR1 fixture，故总数为 11 版本、9 时点、3 个事件、8 条 Claim、
4 个 persona 版本、2 个 family。3 条 Gold 全部是原 PR1 pending synthetic fixture，
不是 DEV-01 人工 gold；annotations/adjudications 均为 0。

## 保存的可见版本与信息包

管理员明细：`DEV-01/visible_versions.json`（逐步 ID、内容 SHA、段落 ID、persona）。

| step | 可见版本 |
|---|---|
| D0 | a:1 |
| D1 | a:1, b:1 |
| D3 | a:1, b:1, c:1, d:1 |
| D4 | a:1, b:1, c:1, d:1, e:1 |
| D5 | a:2, b:1, c:1, d:1, e:1 |
| D8 | a:2, b:1, c:1, d:1, e:1, f:1 |

完整 ID 均有 d01: 前缀。候选不会因 time_window_start 排除旧的重要材料。
六步信息包在 `.local/g1-pr2/packets-a/` 和 `packets-b/` 各独立生成一次，逐字节一致，
且与管理员明细一致；SHA 记录在 `packet-index-admin.json`。尚未分发给任何标注者。
每个单步包没有人工事件/关系/Claim/gold、family/split、未来正文或未来 persona 内容。
完整校验器可在受信准备层读取全量数据与诊断，但这些对象不会作为包或预测输入。

## 真实测试证据

| 检查 | 结果与解释 |
|---|---|
| 首批新测试先失败 | 19 failed；缺失数据/契约/单步包函数，日志 pytest-red.txt 与 XML |
| 初始新旧组合 | 19 failed（新测试）/ 233 passed / 1 skipped；原 PR1 和旧回归通过 |
| 首批实现后 | 19 passed |
| 原始人工记录防线 | origin 负例先 1 failed / 9 passed，修复后 10 passed；均为临时伪造契约探针，不是人提交 |
| Scope 引用补齐 | 先 1 failed / 18 deselected，修复后 1 passed / 18 deselected |
| G1 专项 | 137 passed / 1 skipped；最终全量也包含同一组 138 项 |
| 最终冻结 v2 全量 pytest | **262 passed / 1 skipped / 1 warning**，66.36s；125 旧项 + 138 G1 项，0 failures/errors |
| Ruff | All checks passed |
| pip check | No broken requirements found |
| 旧 seed-sanity-v1 | Recall@8=1、MRR@8=0.8333333333333334、nDCG@8=0.8645724197652078；仅烟测 |
| npm offline build | TypeScript/Vite 通过，24 modules；只生成忽略的 dist |
| Schema / strict Manifest | 17 份 Schema 一致，strict 校验 0 errors |
| 复现与保全 | 双次包逐字节一致；57 个受控输入和 11 个测试文件匹配冻结指纹；范围外原文件均未改变 |
| git diff --check | 通过；新文件也检查 UTF-8/LF 和行尾空白 |

唯一 skip：Windows 不允许创建原生 symlink；另一个不依赖该权限的 resolved-path escape 测试通过。
唯一 warning：已有 Starlette/httpx 弃用提示。没有为此安装新包。
受限环境首次卡在 socket._fallback_socketpair / asyncio / TestClient；已 Ctrl+C 中断，
在允许本地 socket 初始化的环境实跑完整回归，测试使用隔离临时库与 mock，没有改断言绕过。

实际主命令（项目根目录，frontend 除外）：

```powershell
.\.venv\Scripts\python.exe -m ruff check backend tests evals
.\.venv\Scripts\python.exe -B -m pytest tests/evals -q --basetemp=.tmp/g1-pr2-evals-02 --junitxml=.local/g1-pr2/pytest-evals-02.xml
.\.venv\Scripts\python.exe -B -m pytest -q --basetemp=.tmp/g1-pr2-v2-frozen-full -o faulthandler_timeout=30 --junitxml=.local/g1-pr2/pytest-frozen.xml
.\.venv\Scripts\python.exe -B evals/run_baseline.py --output .local/g1-pr2/seed-sanity.json
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -B -m evals.intelligence_v1.contracts --check-schemas
.\.venv\Scripts\python.exe -B -m evals.intelligence_v1.validate --manifest evals/intelligence_v1/manifests/dataset_manifest.json --strict
# frontend 工作目录
npm.cmd --offline run build
# 根目录
# v2 当时使用未交付的本地包核对脚本；该入口缺口已由 v3 仓库模块修复。
# 当前复现使用 python -B -m evals.intelligence_v1.replay，完整参数见 PR2_REVIEW_FIXES.md。
git diff --check
```

固定环境：Python 3.12.14；Node v24.21.0；npm 11.19.0；没有依赖安装或锁文件变更。
复现前须先与本报告固定 Manifest SHA 比较；strict CLI 的 hash 只能证明相对于可信清单的完整性，
不能把每次现算的替换 Manifest 当成外部可信 pin。大批原始日志和包留本地，不纳入算法输入。

## §11.2 DoD 对照与测试责任

| 要求 | 状态 | 证据 / 限制 |
|---|---|---|
| 至少四个时间点的不同可见集合 | 通过 | 6 步及独立 EXPECTED 表；test_DEV01_six_distinct_visible_sets_and_all_synthetic |
| available/observed/supersedes/段落可验证 | 通过 | T03/T04/T05、非法 observation/relation 时间、PR1 时间/hash/链回归 |
| 转载和独立新证据可复核 | 样本准备通过 | 三个 syndicated 上游、独立测量及 distinct event；T08/T09；真人审阅待完成 |
| 0–3 手册和两版 persona | 文档/数据完成 | ANNOTATION_GUIDE.md；T19 保证同证据换约束事实不变，不证明实际人会改分 |
| 陌生第二人独立操作 | **待人工** | 手册/分时点包/模板已备；B 未确认，未实际开展可用性试标 |
| T04/T05/T08/T09/T16 | 通过 | test_dev01_pilot.py，保留旧测试并显式定位 PR1 fixture |
| T17 定位与语义分开 | 机制通过；人工未测 | 存在段落的百万倍结论仍 semantic_support=not_measured；unsupported 仅 synthetic test expectation |
| T21 覆盖缺口 | 样本检查通过 | service_offline / unknown 语义；不称世界无更新或持续七天监控 |
| 数据卡与合法性 | 完成合成范围说明 | DEV-01 synthetic=7/7；无真实历史/许可验证声明 |
| A 初标、B 独立初标、分歧/仲裁 | **待人工** | A/B 都未确认；三个 DEV-01 labels 文件为空，不制造人的结果 |
| G1-a / PR3–PR5 | 未实施/未验收 | 无基线、预测、指标、双标一致率或 G1-a 完成声明 |
| T25 | N/A | 无数据库访问或迁移 |

## 来源与剩余边界

所有 DEV-01 文本和时间均为明确 synthetic；发布者、独立测试者、TinyBench-3 都是虚构，
不是实测性能或真实新闻。真实 github-blog 条目仍 unknown / metadata-only / checked_at=null，
本轮不读取它的正文、不联网核权、不推定允许全文再分发。
参考 verification_state=independently_supported 仅描述设计中的有限测试，不代表独立人工验证。
真实语义支持测量、手册可用性验证、A/B 独立初标和仲裁都未完成，保持待人确认。
完成本 PR 技术交付后停止；不自动开始 PR3，不生成额外模型判断或人工记录。
