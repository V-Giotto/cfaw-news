# G4-PR1 准入与复用审计

日期：2026-11-02（Asia/Shanghai）。范围：离线契约、原生纯函数可行性、计划校正。

审查修订（2026-11-02）：原 PR1 自验收未捕获跨步骤文档回退/分叉和窗口内未观察
区间；本文件的 namespace 陈述也有错误。当前修复证据见
`audit/g4/pr1/REVIEW_FIXES.md`，原基线和原 release manifest 仅作为历史记录保留。

## 基点、授权与证据等级

- 实施前分支 `main`，HEAD `2655f10cf20c647bdbfd1b69a000847471b2c5a3`。
- 实施前仅有两个未跟踪文件：`docs/G4_IMPLEMENTATION_PLAN.md`、
  `docs/CODEX_G4_EXECUTION_PROMPT.md`。保留其字节，不移动、不覆盖。
- 指定的 `docs/plans/G4_IMPLEMENTATION_PLAN.md` 不存在；实际输入是
  `docs/G4_IMPLEMENTATION_PLAN.md` (`g4-plan-v1.0`)。本轮不擅自迁移该文件。
- 当前用户明确指示“开始实施 CFAW News G4-PR1”“本轮只做 PR1”，这是本轮
  实施授权；不扩展为 PR2、Git 写入、真实数据库、采集、模型或前端授权。
- 前置《G4 启动审计》在同一聊天中完成：事实签名定向 59、完整 G3 630、
  Schema/Ruff/构建和历史工件核验。其结果是**上一轮实际记录**，不填入本轮
  `G4_BASELINE.json` 的测试结果。
- `docs/G3_G4_HANDOFF.md`、G3 README、FACT_SIGNATURE_REVIEW_FIX 仍记录独立复审/
  所有者验收待衔接；旧 acceptance 的 false/pending 字段保持原样。本轮记录
  技术复核与 PR1 授权，不冒充管理员已签发 G3 整体最终验收或 G4 Beta。

本轮命令、起止 UTC、受控环境、退出码、日志 hash、输入/配置/输出 pins 见
`audit/G4_BASELINE.json`。原始工件位于
`.tmp/evals/g3/g4-pr1-20261102-001/`。首次失败和后续修复日志分别保留。
最终实施/独立审查状态见 `audit/g4/pr1/IMPLEMENTATION_REPORT.md`。

## 已核对的 owning sources

产品及范围：`AGENTS.md`、`docs/CFAW_News_V1.md`、`docs/ARCHITECTURE.md`、
`docs/plans/G3_IMPLEMENTATION_PLAN.md`、实际 G4 计划、G3→G4 handoff。

G3：`contracts.py`、`bridge.py`、`replay.py`、`rankers.py`、`revisit.py`、
`history.py`、`history_contracts.py`、`history_store.py`、`budget.py`、
`budget_contracts.py`、`fact_signature.py`、README、三个 PR5/修复报告、
schemas、required-test manifests、注册 pytest runner/control/inventory。

G2：PR2 contracts/pipeline/validate_output；PR3 contracts/pipeline/extract；
PR4 contracts/project/pipeline/policy；PR5 contracts/rule_presentation；
PR6 contracts/handoff，以及 G2 checked_input/permissions。

兼容应用：database/ingestion/main/service、App/api/NewsLibrary、现有 workflow/
following/ingestion/reading 测试、pyproject 和 CI。

## 复用决定

| 模块 | 源码事实 | PR1 决定 |
|---|---|---|
| G1 StrictModel/Instant/Persona/coverage/hash | extra forbid、strict、frozen，时间与内容摘要可复用 | 原样使用，不复制近似模型 |
| G2 原生输入/分组/证据/规则项 | 原生引用、许可、状态链校验；独立支持禁用 | 执行正式 pure APIs，不读 Gold、不改算法 |
| G2 PR5 rule_presentation | 规则表达不改变原始 item | 使用规则路径，无 mock/外部 provider 调用 |
| G3 accepted_g2 | 历史封存 campaign/acceptance，固定选择和外部可信 pins | 不能认证新 RSS；不制造这种父身份 |
| G3 synthetic_contract_probe | 明确合成、外部输入 pin 的开发入口 | 仅隔离回归，不接 runtime 输出 |
| G3 revisit/planner | 要求固定 Replay/HistoryInput；history/mapping 只接受 synthetic | PR1 在真实 runtime 适配边界明确阻断 |
| Article | 更新覆盖当前 content_hash/data | PR2 新增账本；不把当前缓存当旧版本 |
| SourceState | 最近一次成功/失败与条件请求缓存 | 可联动，不能代表连续覆盖历史 |
| ArticleReading | 按 article 保存可替换阅读缓存 | 不能直接作为事实版本账本 |
| 旧 Service | 快照、取消/失效、防迟到发布、批准幂等 | 保留；新简报不塞进 Goal/审批流程 |
| setuptools | 当前只发现 backend 包 | PR1 明确为源码检出的离线工具；生产打包由 PR3 单独决定 |

## 本轮新增边界

- `RuntimeInput.kind=runtime_local_v1` 与原 G3 两种 kind 不兼容；不接受 accepted
  pin、reference/gold 或后评测字段，不使用 model_construct 修补输入。
- DocumentVersion 是 `G2VisibleDocument` 的严格追加包装，保留原生 candidate/
  lineage/provenance；真实 rights unknown/metadata_only 不能携带可引用正文。
- Input 完整绑定 as_of、画像、来源、覆盖和文档前缀；100 文档/步、8 步、
  16 来源、2 MB wire 上限。每个来源必须有 coverage，即使没有候选。
- B4 固定，预算 profile 必须显式选择；70/30 仍是未校准候选。P1 不能静默启用。
- 原生 G2 非 hold 不等于 G3 eligible，更不等于语义独立支持。PR1 不发布计划；
  有规则候选返回 raw_news_only/adapter_required；全 hold/空池返回
  insufficient_evidence。完整当前 Archive 引用和原生前缀证据仍保留。
- Interaction 目前只是 wire 契约，没有写接口/存储。存在性、同主体撤销、
  幂等和 journal head 必须由 PR4 结合实际已发布快照校验。

## 测试路径的必要校正

G3 冻结 `test_sources()` 枚举 `tests/` 下所有 Python 文件，要求精确旧集合。
向 `tests/` 加入 G4 测试会使其完整库存拒绝。故新测试放在
`evals/intelligence_g4/tests/`，通过独立显式 pytest 命令、JUnit 和源码/节点
清单验收；旧 `tests/` 继续完整运行。没有过滤旧节点、跳过旧测试、替换控制
文件或改变 G3 库存校验。CI 接入新的 G4 轨道属于后续审查范围。

## 仍未实现与未证明

真实 runtime G3 adapter、跨请求稳定事件命名空间、生产依赖打包、可信 source
registry、DB migration/持久化、API、UI、浏览器 E2E、真实来源采集与用户效用。
native namespace 由 dataset/timeline/strategy/config revision 等原生字段派生；
input pin 另参与完整性和状态链绑定。预算 profile 改变可令 input pin 改变而不改变
namespace/event/snapshot ID。跨请求 registry/状态续接仍未实现；不能把相同身份
当作状态可安全续接的证明。详见 ADR 的分项派生关系和审查对照回归。

SQLite 同库 head 不能单独证明整库回滚不存在。预算贪心仍可能遗漏 minimum
合计可容纳的保护项；G4 必须保留 unmet_protected 和重要遗漏分母。

本轮不改历史状态、不读取 dev-diaries/、不执行 Git 写操作、不访问真实用户 DB，
不联网、不调用模型。下一步只读审查 PR1；不自动开始 PR2。
