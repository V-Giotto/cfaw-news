# ADR：G4 runtime_local_v1 的契约与最小通路

状态：PR1 已实现离线可行性契约，待独立审查；生产 runtime adapter 尚未注册。
日期：2026-11-02（Asia/Shanghai）。授权：本轮用户明确批准 G4-PR1。
实施前基点：`2655f10cf20c647bdbfd1b69a000847471b2c5a3`。

2026-11-02 审查修订：关闭跨步文档链、请求窗口诊断和 namespace 描述的修复
见 `audit/g4/pr1/REVIEW_FIXES.md`。原自验收工件/Schema v1 保留，不作为修复后的
新验收 pin；当前结果是 `g4-pr1-briefing-v2`，输入 wire 仍为 v1，但校验已加强。

## 1. 决定和边界

新增 `evals/intelligence_g4/` 作为源码检出环境下的离线契约/验证包，复用 G1/G2/G3
严格类型和纯函数。没有 HTTP、数据库、抓取器、任务调度、通知或 provider。
不更改 G1–G3 既有代码、Schema、冻结 fixture、required-test pin 或历史报告。

`runtime_local_v1` 是新捕获材料的输入契约；不是 `accepted_g2` 的历史封存身份，
也不是 `synthetic_contract_probe`。输入 SHA256 的来源是调用者独立保存的 exact-byte
pin，CLI 不替调用者计算可信 pin。摘要绑定不等于来源认证或法律许可判定。

当前 G3 parent kind 不接受 runtime，HistoryEvent/HistoryMapping 只接受 synthetic。
仅在对象外增加字段不能穿过其重新解析。PR1 不伪造 parent、trace、accepted pin，
不将 real 改成 synthetic，不通过 model_construct/model_copy 绕过验证。

## 2. 目标通路与本轮实现位置

```text
现有 RSS Article（可变阅读缓存）
  → PR2：经授权的真实观察，事务追加 immutable DocumentVersion/source policy/coverage
  → PR1 已验证接口：RuntimeInput + 外部 exact-byte pin
  → G2 checked_input → PR2 run_grouping_step → PR3 run_evidence_step
  → PR4 project_step/generate_items → PR5 rule_presentation
  → PR1 当前停止：G4_G3_RUNTIME_ADAPTER_REQUIRED 或 G4_EVIDENCE_NOT_ELIGIBLE
  → PR3 待实现：独立 runtime 校验/适配 → G3 原算法 → BriefingPlan
  → PR4：完整快照事务发布 → PR5：API/React/实际交互
```

孤立的原 G3 外部 pinned 合成输入确能调用 rank_revisit(..., "b4") 和
plan_briefing；新增测试验证该能力，同时验证不能把这个 plan 塞入 runtime 结果。
它不是新 RSS→G3 全链成功证据。允许的拒绝是本次 vertical slice 的正式结果。

## 3. 数据接口

### Article → DocumentVersion（PR2）

Article.id 是 URL 派生的当前缓存标识；Article.content_hash 的组成与 G1 原生
content_sha256 不同，不可直接替代。Article.first_seen_at 不证明更新后正文早已
可见；ArticleReading 是独立、可替换的当前阅读缓存。

PR2 从新的真实观察开始保留 source_article_id、document/version ID、原始内容类型、
合法片段及段落位置、canonical content hash、available/observed、publisher date
及其来源可信度、rights/allowed_use/来源角色/provenance 和 supersession。
旧缓存缺档时不回灌过去版本。body_is_full 不是引用许可。未知 rights 只允许元数据。

PR1 RuntimeDocument 继承 G2VisibleDocument，保留 CandidateDocumentVersion 和
VersionIdentity。前驱版本必须已在本次回放前缀捕获；同 version ID 不能改变字节
语义或前驱关系。同一 document 的全部已捕获 identity 必须形成一条完整线性链，
当前选择必须是该链尾，local lineage 必须与完整链一致。即使中间步骤没有该文档，
也不遗忘已经捕获的后继；回退、分叉、遗漏中间版本和改写旧前驱都明确拒绝。
当前不提供从 SQL Article 自动制造 snapshot 的函数。

### RuntimeInput → native G2（已实现）

- canonical UTF-8 JSON，无 BOM/重复键，严格拒绝额外字段。
- kind、record_origin、provenance、timeline、显式 RuntimeConfig、sources 和 steps。
- 每步包含画像、as_of/窗口、完整可见文档、每个配置来源的 coverage。
- 外部 pin 绑定整个不可变回放；同一回放前缀共享该 pin 和原生 previous-state hash。
- 原生 checked_input 复核文档内容 hash、许可、来源、可见性、lineage/seeds/coverage；
  后续阶段使用正式 validators，不拼造结果 JSON 或重新实现算法。
- PR1 只实现有界全前缀重放，没有 checkpoint、增量 append API 或跨请求历史继承。

### native G2 → validated G3（PR3 阻断）

必须保留 event/revision、完整证据/引用/来源、规则 item/presentation/snapshot、
所有 observation、document archive、identity transitions、coverage 和精确历史引用。
G3 的 source_attributed 仅表示有归属的来源声明，不是已证明真伪或独立支持。

PR3 应提出增量严格 runtime adapter/共享纯计算入口，保留旧离线 wrapper 和 Schema。
不得复制出另一套 G2/G3 算法；如果需要调整共享入口，单独记录新 release/source pins，
以相同输入的字段、特征、资格、分数、顺序、预算和拒绝行为进行等价回归。
当前 wheel 只打包 backend；PR3 必须同时解决评测模块/只读资产的生产依赖打包，
不能在 HTTP 中调用 CLI 或依靠当前工作目录。不能在旧验收工件上仅改 pin。

以下派生关系根据原生源码及实际预算 profile 对照更正，替代原“整份 input pin
变化会重置 native namespace”的错误陈述：

| 对象 | 原生派生/绑定 | 不代表什么 |
|---|---|---|
| grouping namespace | PR2 identity.namespace：dataset_id、timeline_id、strategy、identity_revision | 不由整份 input pin 派生 |
| evidence namespace | PR3 history.namespace：dataset_id、timeline_id、strategy、history_revision、PR3 config SHA | 不是来源或输入真实性认证 |
| rule namespace | PR4 project_step：evidence namespace + generator_revision | 不是 G4 预算 profile 的身份 |
| event key / revision | namespace、birth anchor，必要的 split/complex transition；revision 另绑定可见 features/relations/lineage | 不是整份回放字节摘要 |
| item snapshot ID | PR4 observe：item_id、as_of、bundle_sha256 | 不是整份 input pin；时间或事实变化仍可能改变它 |
| input_manifest_sha256 | 绑定 exact-byte runtime 输入，在 grouping state 中保存并在续接时复核 | 不等于 namespace/event/snapshot ID |
| previous_state_sha256 | 前一 typed state 的完整摘要，各阶段检查状态链并绑定上游状态 | 不能仅凭语义 ID 相同就绕过续接校验 |

固定内容/as_of 等字段，仅将 G4 预算 profile 从 70/30 改为 60/40，input/config pins
会变化，而三种 namespace、event keys 和 snapshot IDs 保持一致；完整 grouping
state 摘要仍因 input pin 改变而不同。当前每次请求从空状态重放，没有已实现的
跨请求 registry/状态续接。PR3 必须分别设计稳定身份、输入完整性与安全状态续接，
不能依靠改 pin、重建 namespace 或相同 snapshot ID 自动继承历史。

### validated G3 → BriefingPlan（PR3）

显式 B4；当前 rank_revisit 的默认参数 P1 不作为产品默认。P1 仅能另注册显式实验。
fact policy 固定 g3-grounded-fact-signature-v2，policy SHA256
`70565148fe436fa823ef6a4063cbba7abb4c994cc34f19dc44bdc2451e367450`。
PR2 comparison/PR3 config/PR4 budget 的完整绑定不能弱化。

BudgetConfig 必须显式选择 60/40、70/30 或 80/20 的已注册候选；均未校准。
planner 不重新认证排名数值分数；排序只能来自受信任服务端运行及其绑定结果。
保留全部 archive IDs、excluded/truncated/not_displayed、coverage、unmet protected。
保护项仍受资格和总预算约束，贪心可能遗漏 minimum 总和可装下的项。

## 4. PR1 状态与降级契约

RuntimeStatus 分开记录 mode、origin、native_g2_validated、g3_runtime_validated、
publishable、state/code、semantic_truth。当前后两项能力明确为 false，semantic_truth
为 not_evaluated。没有 live_verified 状态，不把结构通过命名成独立事实核验。

| 原生结果 | PR1 state/code | 展示与保留 |
|---|---|---|
| 至少一条 G2 非 hold | raw_news_only / G4_G3_RUNTIME_ADAPTER_REQUIRED | plan=null、display_order=[]；保留全部原生结果和当前 Archive |
| 全 hold 或空池 | insufficient_evidence / G4_EVIDENCE_NOT_ELIGIBLE | 同上；保留 hold 原因、引用缺口及 source coverage |
| 无效 pin/时序/许可/引用/Schema | 明确异常和固定错误码，CLI exit 1 | 不签发结果目录，不伪造成功 |

RuntimeBriefing 重新执行原生计算以校验序列化结果；篡改事实/Archive/hash/状态被拒绝。
synthetic 仅用于开发验证，不与真实来源混排或声称“今日简报”。未知权利的真实字段
测试使用未抓取的 example.com 虚构元数据，不构成真实新闻、许可或采集证明。

当前每个 `native_steps[i].coverage` 额外保存请求窗口的保守区间并集诊断，复用
冻结 G3 的 requested-interval-conservative-union-v1 纯计算策略，只将证据指针
映射到 `/input/steps/i/source_coverage/n`。原始 windows 和 G2 evidence 保持原样；
G2 的 coverage_gaps 只反映所供记录，不能作为整个请求窗口是否无缺口的判断。
G4 消费端必须读取新的 coverage.has_gap、sources.segments、unobserved_intervals
与 unconfirmed_intervals。没有观察的区间标 unknown，失败/partial/offline 不被
covered 覆盖；全候选为空也保留来源诊断。一天里只有最后一分钟 covered 时，
明确报告剩余 23 小时 59 分钟 unknown。点观察不能填充正时长窗口。

Schema v1 字节保留；当前输出/步骤修订为 g4-pr1-briefing-v2 / g4-pr1-native-step-v2，
在 schema/v2 注册必需 coverage 字段。旧结果不能作为 v2 结果导入或只更换 pin。

## 5. 冻结硬门槛与错误码 v1

| 门槛 | 契约/拒绝码 |
|---|---|
| 外部 exact-byte pin、规范字节、输入大小 | G4_INPUT_PIN_MISMATCH / G4_CANONICAL_REQUIRED / G4_RESOURCE_LIMIT |
| 严格 Schema/无 Gold/无旧 parent kind/注册配置 | G4_SCHEMA_INVALID / G4_CONFIG_INVALID |
| real/synthetic/Persona/source 类型及 provenance 一致 | G4_PROVENANCE_INVALID |
| rights、allowed use、引用额度 | G4_RIGHTS_INVALID；保留 native_code |
| 当时可用的文档/画像/coverage；合法窗口 | G4_FUTURE_INPUT / G4_INVALID_INTERVAL |
| ID 唯一、不可变版本、前驱可解析、顺序前缀 | G4_DUPLICATE_ID / G4_HASH_MISMATCH / G4_REFERENCE_MISMATCH / G4_SEQUENCE_INVALID |
| native G2 全阶段校验不放宽 | G4_NATIVE_G2_REJECTED，附 native_code，不回显正文 |
| 未注册 runtime G3 不发布、hold 不晋级 | G4_G3_RUNTIME_ADAPTER_REQUIRED / G4_EVIDENCE_NOT_ELIGIBLE |
| 结果与输入/配置/全候选绑定 | G4_OUTPUT_MISMATCH |
| 被动动作不推断已知，feedback/retract/source 形状 | G4_INTERACTION_INVALID |

G4_BRIEFING_NOT_READY 为后续服务的保留码，本 PR1 没有 API，不声称已实现 HTTP 语义。
这些 gate 是工程资格，不能替代事实性审查、来源许可核实和独立研究。

## 6. Interaction 与持久化决定（PR4）

严格 RuntimeInteraction 复用 PublishedItemRef/动作和反馈枚举，额外绑定幂等键与
expected_snapshot_version。只有显式 acknowledged/known 表示声明已了解；opened
保持 opened。included 是服务器发布事实；rendered 必须客户端视口确认。

本 PR1 只校验形状、时间、动作来源及 retraction 字段；DB 中 target/delivery/persona
的存在、版本及同主体撤销、可见性、幂等、head/CAS 必须 PR4 实现，不能把单个
wire 校验称为写入授权。PR1 不产生任何交互事实或更新 Persona。

PR2/PR4 使用新增表和显式迁移，保留旧业务。SQLite 同库 head 可用于原子一致性，
不能单独检测整个数据库连 head 一起恢复旧快照；要么引入库外可信 checkpoint，
要么明确恢复 epoch/管理员确认与无法检测的边界。不得承诺不存在回滚。

## 7. PR2–PR6 精确触达和测试依赖

下列是限定工作清单，不表示文件已经存在或下一 PR 已获授权。

| PR | 预定文件触达 | 测试依赖 / DoD |
|---|---|---|
| PR2 文档账本 | 新增 backend/cfaw_news/intelligence/document_store.py、migrations/001_g4_documents.py；修改 backend/cfaw_news/database.py、ingestion.py；新增 source policy registry；保留本 PR1 contracts | evals/intelligence_g4/tests/test_capture.py、test_migration.py；旧 test_ingestion/test_reading/test_workflow/test_following；空/旧库升级、重复、正文更正、失败原子性、备份恢复、unknown rights、published≠observed |
| PR3 runtime bridge | 新增 backend/cfaw_news/intelligence/runtime.py、g2_adapter.py、g3_adapter.py；修改 pyproject.toml 的运行时打包方案；仅必要时新增共享 pure 入口并单独审查源指纹 | test_runtime_bridge.py、test_runtime_identity.py、test_runtime_equivalence.py、test_offline_install.py；正式 G2/G3 runner/Schema；跨请求身份、严格 real history、无 synthetic 混用、B4/policy/预算、hold/Archive/unmet |
| PR4 持久化/API | 新增 intelligence/history_store.py、service.py、routes.py、migrations/002_g4_briefings.py；修改 database.py、main.py；不改旧 service.py 的业务语义 | test_history_db.py、test_intelligence_api.py、test_publication_races.py；旧 workflow/following 全回归；CAS/幂等/撤销/取消/崩溃/恢复/Host/Origin、旧快照与 latest 原子切换 |
| PR5 React | 修改 frontend/src/App.tsx、api.ts；新增 BriefingHome.tsx、BriefingDetails.tsx、BriefingHistory.tsx 和必要样式；保持 NewsLibrary/ArticleReader/GoalWorkspace/ActivityPages | typed build；独立 G4 browser/e2e 测试；视口 rendered、成功详情 opened、显式反馈/撤销、空态/hold/离线/键盘/窄屏、旧导航与引用 |
| PR6 验收 | 新增 G4 独立 checks/inventory、浏览器配置、docs/G4_ACCEPTANCE.md、G4_G5_HANDOFF.md、audit/G4_RELEASE_MANIFEST.json；审查后增量 CI | G4 新测试显式执行 + 完整旧 tests/注册 runner + baseline/build/E2E；合法现实离线快照、故障注入、release/policy/source/Schema pins；未授权联网标 not_evaluated |

测试文件默认放 `evals/intelligence_g4/tests/`：冻结 G3 库存精确枚举 tests/，不能
为加入 G4 而改其旧 pin。PR6 另建 G4 库存与 CI 轨道，原门禁仍完整执行。
无强制第二真人；独立 AI 审查只读开展，不能称为独立人工研究。

## 8. 当前阻断及交接

- G3 全阶段最终管理员验收状态需新增决定衔接，不改写旧报告。
- 真正 RSS capture/rights registry、runtime G3 adapter、跨请求身份/真实历史、
  runtime 安装包与生产 SQLite/API/UI 均待后续 PR；本 PR1 无“全链实时简报”承诺。
- PR1 完成后停止，等待只读审查、修复闭环与管理员对下一 PR 的单独决定。
