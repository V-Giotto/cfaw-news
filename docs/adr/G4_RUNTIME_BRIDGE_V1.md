# ADR：G4-PR3 受控本地计算桥接

日期：2026-11-02。状态：实现提交独立审查，尚无审查通过或管理员验收记录。
入口：`main@783f5428671457ea3f1f654b160152f653d2e9e0`。
本 ADR 增量说明 PR3，保留 PR1 ADR、历史验收和 Schema 原字节。

## 决定

注册 `g4-pr3-runtime-envelope-v1`，kind=`runtime_local_v1`，作为 PR2 不可变资料账本的
有界计算输入。真实和合成 origin 必须在画像、来源、文档上完全一致。合成仅用于开发，
运行结果始终 `publishable=false`，不触发 HTTP、抓取、模型、消息或持久化发布。

正式 G3 replay 的 `accepted_g2` 证明某个离线父产物已通过封存门禁；它不等于生产
runtime。`synthetic_contract_probe` 是合成契约探针，不能成为真实推荐入口。
二者的旧验证器和资产不动。真实 runtime 不实例化旧 G3ReplayInput/HistoryInput，
不填充虚构 accepted pin、delivery、反馈或 synthetic history，不用 model_construct。

## 输入、G2 与证据

`runtime.from_ledger(session, stream_id, as_of, time_window_start, persona, config)` 在 SQLite
同一只读事务内读取：当时已可用的 G4Version 全链、当时已注册的 SourcePolicy、
当时已观察的 coverage。它不读取 Article/ArticleReading，不制造过去正文。
版本列、记录 SHA、source policy 主键/数据、coverage 列/数据/捕获关联摘要分别核对。
来源配置可包含无文档的失败来源，仍进入覆盖诊断。

封套必须包含本次捕获前缀中的全部版本；document/version ID 按 PR2 公式重算。
同一 document 从 sequence=1 起形成连续、不可变、时间单调的单链；当前版本由合法链尾
导出，调用者不能选择旧头。分叉、缺中间版本、重复 ID、错 policy、未来可用性或未来
coverage 均拒绝；未来 as_of 也在严格封套导入层拒绝，不仅在 run 层检查。
没有跨请求可信 registry；调用者删掉整个尾部后作为新独立输入提交的
行为，不能由一个自包含 JSON 检测。受控账本导出负责完整前缀，PR4 必须绑定可信 head。

实际接口依次是：

```text
G4DocumentVersion + SourcePolicy + CoverageWindow
  → CandidateDocumentVersion / VersionIdentity / G2VisibleDocument
  → G2ReplayInput → checked_input
  → GroupingInput / run_grouping_step
  → EvidenceInput / run_evidence_step
  → project_step / generate_items → rule_presentation
  → G3Candidate + ReplayObservation + 完整 document_archive
  → validate_candidate_evidence / validate_identity / validate_snapshots
```

每个不同 available_at（不早于画像可用时间）和最终 as_of 都重放一个完整前缀；前一步
typed state/hash 交给原生下一步校验。最多 128 个版本、100 个文档头、32 个原生步骤、
32 个 policy 及 512 个 coverage 记录；超限拒绝，无静默裁剪。输入最多 4 MB。
每次请求从空状态全前缀重放，尚无安全增量续接、跨请求 event registry 或用户历史。

PR2 retained-content SHA 和原生 content SHA 的算法不同，投影保留两种 pin；原生摘要
由原字段正式重算。excerpt_only 且 retention=excerpt 投影为更严格的 quoted_excerpt，
权限不放大；未知语言明确为 und。未知/metadata-only 权限只使用 PR2 保留的安全元数据。
合成测试显式映射到 synthetic URI，并保留原账本 URL 和映射记录；真实 URI 永不替换成
合成 URI。native 权限/引用验证拒绝时输出 raw_news_only，保留受控错误码，不手工 verified。
同 source 的多个政策版本暂不冒充一个政策，明确安全降级 POLICY_TRANSITION_UNSUPPORTED。

## G3 计算适配及身份

新 RuntimeHistoryInput/RuntimeReplay 保存全部已验证上游数据，journal 明确为空且
not_integrated。不存在 delivery、知识声明或反馈推断。原生特征的“无已知记录”不是
“用户肯定不知道”。PR4 才实现真实 append-only 历史、映射及可信 head。

g3_adapter 仅做原生投影/编排：G1 candidate_scores、G3 _features/_contributions、
_history_features/_prefix 和 budget.derive 保持原源码；不重写排序规则、权重或预算算法。
新 rank_runtime 会重新计算完整 G2 context；plan_fields 重新计算排名并对照全字段，
RuntimePlan 与 RuntimeResult 的 JSON 导入也重新计算，截断候选池、篡改证据/快照/分数/
Archive 或更换配置不能过关。旧正式 rank_revisit 对照仅出现在测试，使用其真正封存输入。

| 绑定 | 用途 |
|---|---|
| grouping/evidence/rule namespace | 原生 dataset/timeline/strategy/identity/history/generator 配置派生身份 |
| event key/revision、snapshot ID | 原生事件历史和当时证据视图身份；不是整份输入摘要 |
| exact-byte input SHA | 独立调用者 pin；绑定规范 JSON 的所有输入与原生状态链 |
| previous-state SHA | 单次回放中每一步状态续接完整性；不能由 namespace 相同代替 |
| ENGINE_PIN / ranking_policy_sha256 | 127 个原生 Python 依赖、retrieval 及新排序注册策略 |
| candidate_pool_sha256 / context SHA | 全部 event/revision/item/snapshot/view 与实际完整 context |

单改 70/30→60/40 会改变 input/config pin，namespace/event/snapshot 可保持相同。
身份稳定不授予跨请求状态继承。流 ID 必须由后续可信本地服务稳定提供，不能视作认证。

fact signature 固定 `g3-grounded-fact-signature-v2`，policy SHA 为
`70565148fe436fa823ef6a4063cbba7abb4c994cc34f19dc44bdc2451e367450`；同时绑定源码树。
旧 RankingConfig 摘要不能代替新 runtime ranking/config pin，policy 字段错误即拒绝。

默认显式选择 B4。P1 需 algorithm=p1 与 experiment=p1-explicit-development-v1 同时存在。
Budget 注册为 g4-runtime-budget-v1，必须显式选择原生 60/40、70/30 或 80/20 profile；
全部标 uncalibrated_experimental_profile。无默认 70/30，无自动调参或 P1 增益承诺。

RuntimePlan 保留原生所有 PlannedEvent/BudgetDiagnostics、archive_snapshot_ids、
excluded/not_displayed/truncated、unmet_protected_event_keys、内容引用和原因。
唯一预算结果扩展是 coverage：复用原生保守区间并集内核，使用配置来源全集，包含空池或
无 window 的来源；原生 coverage_gaps 不视为完整请求窗口证明。没有观察的区间为 unknown，
点观察不证明连续覆盖。预算本身保持原生贪心，保护项即使 minimum 总和可放下也可能遗漏。

## 状态与安全降级

冻结原生 G2 的 independent_support=disabled，bundle 包含 independence_unknown。
因此当前真实非空主张输入通常只能完成 G2 和诊断排名，不能产生真实 Focus/Radar。
这不是本 PR 已补齐的能力。必须另案实现/验证独立性证据，或管理员批准新的明示资格政策。

| 条件 | 本次结果 |
|---|---|
| 真实 rights/legacy/source 角色/独立性有疑义 | raw_news_only，plan=null，保留理由及可用原生诊断 |
| 原生 G2 正式校验拒绝 | raw_news_only，G4_NATIVE_G2_REJECTED:原生码，无伪造阶段 |
| 合法开发输入有可预算项 | plan_ready，但 calculated_not_published，始终不可发布 |
| hold-only/空池/无预算可展示项 | evidence_not_ready，保留 Archive、排除原因及 coverage |
| Schema、pin、版本链或未来输入不合法 | 明确拒绝，不签发结果目录 |

资格门槛同时在预算函数入口执行，不能绕过 run 直接对疑义真实 context 生成计划。
ranking.events 的原生 tier/eligible 仅是算法诊断，消费端必须遵守外层 state/plan；
不可直接拿这些字段绘制 Focus/Radar。semantic_truth=not_evaluated。

错误码包含 G4_RUNTIME_{CONFIG_PIN_MISMATCH,INPUT_PIN_MISMATCH,CANONICAL_REQUIRED,
LINEAGE_INVALID,LEDGER_ID_MISMATCH,POLICY_MISMATCH,FUTURE_INPUT,ORIGIN_MISMATCH,
SOURCE_NOT_FOUND,DUPLICATE_ID,INTERVAL_INVALID,RESOURCE_LIMIT,CONTEXT_MISMATCH,
RANKING_BINDING_INVALID,EVIDENCE_NOT_READY,LEDGER_POLICY_MISMATCH,LEDGER_COVERAGE_MISMATCH,
CANCELLED,TIMEOUT}，以及 G4_PLAN_BINDING_INVALID/G4_RUNTIME_OUTPUT_MISMATCH。
CLI 将 Pydantic 中的受控 LedgerError 转为上述错误码，未知形状为 SCHEMA_INVALID；
错误诊断不回显来源正文。取消/超时为同步阶段间的 cooperative 检查，不是硬 CPU 抢占。
每次返回前再次检查；超时计算不返回可发布结果。PR4 仍需异步任务/CAS/取消竞态持久化。

## 安装与工件

根 pyproject 被 G3 测试控制面封存，保持不变。scripts/build_g4_native.py --core --out
显式生成 runtime 构建配置的 core wheel 和独立 native wheel；后者只含锁定 Python 源码，
不含 fixture、标签、数据集、冻结验收证明或用户数据。core 声明精确 native 版本依赖。
安装到隔离 target 后在仓库外运行，证明不依赖 CWD。缺少或改动锁定依赖明确拒绝。
此配置是本地运行时打包，不代表旧常规 backend wheel 已自动拥有此依赖。

CLI 接受规范输入文件及外部 exact-byte pin，写入新目录中的 input/result/stage_log、
每一步原生 JSON 和 manifest 文件摘要。candidate.trace.path 绑定对应阶段文件，
trace_pointer 指向完整 result 的 /stages/N。输入 SHA 不是来源身份、许可或语义真实性认证。

## 后续边界

PR4 触达 intelligence/history_store.py、service.py、routes.py、migrations/002_g4_briefings.py
及 database.py/main.py 的新增集成；测试 history_db/intelligence_api/publication_races，
依赖本 PR 严格封套与账本导出，必须实现真实历史、可信 head/CAS、取消和快照原子切换。
PR5 在 App.tsx/api.ts 集成新 Briefing 页面，测试视口 rendered、opened/ack 区分及旧导航。
PR6 单独注册新 G4 CI/清单和浏览器验收，不改旧 G1–G3 注册控制面。
以上没有本轮授权；本轮没有 HTTP、前端、迁移、真实采集或模型验证。
