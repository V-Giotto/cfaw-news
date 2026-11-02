# CFAW News — G4_IMPLEMENTATION_PLAN.md

> **文档版本**：`g4-plan-v1.0`（2026-10-30）  
> **项目**：[V-Giotto/cfaw-news](https://github.com/V-Giotto/cfaw-news)  
> **仓库核对基点**：`main@2655f10cf20c647bdbfd1b69a000847471b2c5a3`（2026-10-29 提交）  
> **建议保存路径**：`docs/plans/G4_IMPLEMENTATION_PLAN.md`  
> **状态**：架构与实施建议；**不等于 G4 已执行或 G3 已获得最终管理员验收**。开始每个 PR 必须重新检查实际 HEAD、工作树、授权和上游冻结资产。  
> **定位**：单人项目所有者 + Codex 开发 + AI 独立代码审查；不设置强制第二真人审查/标注门槛。

---

## 0. 最重要的决定：G4 是「可日常使用的情报应用」，不是「重写离线研究代码」

### 0.1 目标

用户主动打开 CFAW News，几秒内理解：

- **重点情报 Focus**：真正值得深入看的技术变化；为什么重要、与我有什么关系、引用出处与风险在哪里；
- **前沿速览 Radar**：对未来可能有价值但尚未充分证实的机会，精简地留一个认知入口；
- **资料库 Archive**：完整、可追踪地检索原始材料和不适合重点展示的候选；
- **自上次访问以来**：哪些事件首次出现、哪些有实质变化、哪些只是重复，哪些时间段来源覆盖不完整；
- **简单明确的反馈**：打开、已了解、不感兴趣、更正反馈；反馈是可撤回的，不被视为用户永远掌握知识。

用户是研究生/开发者，主诉求是**减少反复检索、比较新框架、阅读论文和调试时的信息获取成本**。G4 优先做自主查看时的简报体验，而不是主动推送、自动执行、长期研究代理或花哨仪表盘。

**产品原则**：后台在明确授权的采集范围内可做有限更新；前台只在用户自主访问时展示。默认无邮件、系统通知、桌面弹窗或外部信息推送。

### 0.2 不要只做“漂亮的假首页”

用户必须能区分：

1. **真实资讯 / 原始新闻**：来自现有订阅源，允许在 `NewsLibrary` 阅读，但未必经过 G2/G3 情报验证。
2. **经过验证可展示的情报**：确有当时可用的来源版本、可核查的主张与引用、来源范围和 G2/G3 展示资格；可进入 Focus/Radar。
3. **离线演示 / synthetic**：只能在明确隔离的 Demo/Developer 模式出现，禁止与用户真实简报混排、冒充“今天的 AI 新闻”。
4. **不可确认 / hold**：可保留安全的标题、元数据、链接和原因用于 Archive / 诊断，不把无法支持的断言包装成摘要。

**G4 的首要工程难题不是 React，而是：**从当前实时 `Article`/RSS 数据建立真正有版本、时序、许可、来源与身份约束的 `G2 → G3` 运行时通路。没有这条通路，不得将离线合成 `BriefingPlan` 直接当作真实新闻推荐。

---

## 1. G3 检查结果与 G4 准入差异

### 1.1 实际读取的仓库证据

本次经 GitHub 连接读取以下文件（全部属于 `main` 基点）：

- [`docs/G3_G4_HANDOFF.md`](https://github.com/V-Giotto/cfaw-news/blob/main/docs/G3_G4_HANDOFF.md)
- [`evals/intelligence_g3/README.md`](https://github.com/V-Giotto/cfaw-news/blob/main/evals/intelligence_g3/README.md)
- [`evals/intelligence_g3/reports/PR5_ACCEPTANCE.md`](https://github.com/V-Giotto/cfaw-news/blob/main/evals/intelligence_g3/reports/PR5_ACCEPTANCE.md)
- [`evals/intelligence_g3/reports/PR5_REVIEW_FIXES.md`](https://github.com/V-Giotto/cfaw-news/blob/main/evals/intelligence_g3/reports/PR5_REVIEW_FIXES.md)
- [`evals/intelligence_g3/reports/FACT_SIGNATURE_REVIEW_FIX.md`](https://github.com/V-Giotto/cfaw-news/blob/main/evals/intelligence_g3/reports/FACT_SIGNATURE_REVIEW_FIX.md)
- [`evals/intelligence_g3/{contracts,bridge,replay,rankers,revisit,history_store,budget,budget_contracts}.py`](https://github.com/V-Giotto/cfaw-news/tree/main/evals/intelligence_g3)
- [`backend/cfaw_news/{database,main,ingestion}.py`](https://github.com/V-Giotto/cfaw-news/tree/main/backend/cfaw_news)
- [`frontend/src/App.tsx`、`NewsLibrary.tsx`、`api.ts`](https://github.com/V-Giotto/cfaw-news/tree/main/frontend/src)
- [`docs/CFAW_News_V1.md`](https://github.com/V-Giotto/cfaw-news/blob/main/docs/CFAW_News_V1.md) 与 [`AGENTS.md`](https://github.com/V-Giotto/cfaw-news/blob/main/AGENTS.md)

### 1.2 G3 已落地的内容

| 领域 | 源码证据 | 检查判断 |
|---|---|---|
| 受控离线输入 | `contracts.py`、`replay.py`、`bridge.py` | 存在原生 G2/G3 映射和外部可信 pin 机制，不是生产输入接口 |
| 排名与回访 | `rankers.py`、`revisit.py`、`history.py` | B0/B1/B3/B4/P1 的事件级对照、解释与历史状态已实现 |
| 追加历史 | `history_store.py` | 离线 synthetic JSONL + 侧车锁 + 预期 head；**不是生产 DB 持久化** |
| Focus/Radar 预算 | `budget.py`、`budget_contracts.py` | `plan_briefing()` 和 `BriefingPlan` 已实现，阅读估时未通过真人校准 |
| 数据诊断 | `BriefingPlan.archive_snapshot_ids`、`unmet_protected_event_keys`、coverage 诊断 | 适合 G4 使用，但必须保留完整候选/未展示原因 |
| 复现/验收 | `reproduce.py`、`evaluate.py`、`acceptance.py`、控制面 | 有机器运行证据和固定 pin 拒绝测试 |
| 事实签名修复 | `g3-grounded-fact-signature-v2`、修复报告 | 已修复符号/数值/单位被错误归一化的 P1 缺陷；复审状态仍需最终确认 |

### 1.3 报告记录而非本次重跑的结果

最新事实签名修复报告记载：**G3 630 passed；全仓 1753 passed、1 个既有 Windows symlink skip；2574 次确定性离线预测；当前定向验收 PASS**。这些是仓库文档的历史运行记录。本次通过 GitHub 阅读源代码/报告，**未在用户本机重跑 Ruff、pytest、浏览器烟测或 G3 验收**。其中 `.tmp` 工件根目录是用户本地 `D:\agent_project\cfaw-news\.tmp\evals\g3\...`，不代表其内容已全部提交到 GitHub。

### 1.4 G3 现存重要限制

1. **G3 最终认可状态**：交接文档仍要求独立复审和所有者批准；最新提交文字写过“PASS WITH CONDITIONS”，不能由提交标题替代逐项关闭记录。
2. **B4 暂时保留**：PR5 报告明确 P1 尚无稳定改善证据；不得默认把 P1 升级为应用排序策略。
3. **真实世界缺口**：开发数据是 synthetic/AI-development、非盲，独立测试家族为 0，尚未验证真实模型、真实来源泛化或用户价值。
4. **预算已知遗漏**：`protected6/420` 案例里 6 项最简内容合计 369 秒，却因贪心分配完整投影，411 秒只呈现 5 项；`unmet_protected_event_keys` 必须显示，不能宣称“能装下就保证都展示”。
5. **事实策略绑定**：最新签名策略版本为 `g3-grounded-fact-signature-v2`；旧 ranking/config/policy pin 不能混用。
6. **真实运行时缺口**：G3 `load_input()` 要求受控的 G2 历史/manifest，输入类型是 `accepted_g2` 或 `synthetic_contract_probe`；目前并不存在“把一篇新的生产 RSS 新闻直接喂给 G3”的已验收 API。
7. **现有 UI/DB 属于旧产品**：`App.tsx` 默认 page `library`；`NewsLibrary.tsx` 使用 `/api/articles`；`database.py` 的表是 Goals/Articles/Runs/Decisions/Schedules/SourceState 等，无 G4 briefing/event_version/exposure_journal 的生产数据表。

**准入门槛 G4-H00**：开始改代码前，Codex 必须检查本地真实 HEAD / worktree、事实签名修复的独立复审结论与所有者决定。若复审尚未关闭，应完成独立 AI 复审或记录阻断；**不要求第二名真人**。若发现时间/证据安全性阻断项，先修 G3 再启动 G4。不得偷偷修改旧报告或旧 pin。

---

## 2. 实施范围与严格非目标

### G4 必须完成

- 用户主动访问的三层情报首页 Focus / Radar / Archive；
- 正式、版本化的实时材料摄取/证据边界（不篡改旧 Article）；
- 可以安全复用 G2/G3 算法的本地运行时适配，或如实降级为原始资讯模式；
- 生产本地 SQLite 的简报快照、候选、证据指针、曝光、反馈和 trusted head 保存；
- 幂等写入、取消/失败隔离、可靠重访窗口和 provenance 诊断；
- API、React UI、可访问性、旧功能兼容以及端到端/浏览器测试；
- 一份有现实来源许可与证据约束的可核验本地测试样本（可使用明确许可的真实文章或受控真实源烟测；不得将当前合成测试冒充实时结果）。

### G4 不做

- 不新增真实 LLM API/付费推理、Dense/向量数据库、训练、联网研究 Agent、自主执行工具；
- 不实现默认桌面/系统/邮件/微信推送，不依赖用户持续在线；
- 不引入多用户认证和云服务，却声称已有多用户安全能力；
- 不强迫用户每天打开应用、打卡、持续查看消息；
- 不偷偷启用所有采集源，也不以全网覆盖为卖点；
- 不自动修改旧 Goal/Run/Decision/Schedule 业务语义；
- 不修改 G1/G2/G3 冻结资产或历史报告来让适配通过；
- 不要求两名真人标注、真实用户实验、人工独立研究审查才能完成 `g4_development` 工程验收；这些保留为可选研究轨道。

### 工程验收与产品验收分离

- **`g4_development`**：契约、安全、时序、持久化、API、UI、浏览器、兼容性、可复现测试通过。
- **`g4_beta_utility`**：至少一个真实合法来源的新条目从采集一直走到可展示/不可展示的**可解释结果**，用户能够完整看见出处、限制、反馈和重访；如全部真实候选被拒绝，必须呈现真实数据不足状态而非虚构重点简报，不能宣称已具备“智能每日推荐”的有效体验。
- **`g4_research_optional`**：新独立事件家族、外部研究者/真人验证、效用测量，为 G5 预留，不阻塞开发。

---

## 3. 目标产品体验与信息架构

### 3.1 主导航

1. **我的情报（默认主页）**：新的 Focus、Radar、回访更新、来源覆盖诊断、上次访问后变化。进入主页不等于主动通知；简报不存在时可显式生成/刷新。
2. **资讯资料库**：复用现有 `NewsLibrary` 和 `ArticleReader`，提供搜索、来源筛选、原始文章；保留并区分未经情报验证的原始资讯。
3. **我的关注/研究（兼容保留）**：现有 Goal 工作台/检查/计划日程继续使用，G4 不把点击文章自动转换为长期研究订阅。
4. **历史与设置**：简报快照列表、阅读预算、关注领域、有限探索偏好、反馈纠错/撤回、来源状态说明。

可延后独立「研究工作台」的重构；G4 不要求完整研究型 Agent。

### 3.2 首次打开、再次打开与异常场景

**首次打开**：简短的本地 Persona 设置（可跳过/修改；默认通用 AI 开发者主题），选择预算 180/420/900、允许的订阅源与是否执行首次手动刷新。没有真实合格候选时显示“暂无经过证据校验的重点情报”，同时显示原始资讯入口，不能以 synthetic 补齐。

**再次打开（相隔 1/3/7 天）**：显示从最近一次真实 `rendered` 或明确交互之后的可观察变化；如果只有 `included` 不能当作看过；开机离线期间标注 `service_offline` / source gaps，不说“过去七天我们一直盯着”。无变化也只报告“在已覆盖来源中未发现可确认增量”，不能推断全网无变化。

**刷新**：只有当前会话主动打开/用户明确授权刷新时启动有界任务；显示阶段、来源故障、取消、过期版本和断网降级。完成前保留上一份快照；**不能把正在生成中的简报半成品发布成成功结果**。

**证据卡片**：一句话“发生了什么”、为什么对目标有用、`source_attributed` 与 `independently_supported` 等准确证据状态、具体证据位置、可点开的原始材料、不确定性；不能把生产假设或者生成推断写成已证事实。

**典型卡片**：框架新版支持一种能力（明确来自官方声明）；限制是未经独立验证；用户可“打开原文 / 标记已了解 / 暂时不感兴趣”，选择不会改变新闻真伪。

### 3.3 三层展示语义

| 层级 | 用途 | 证据展示 | 限制 |
|---|---|---|---|
| Focus | 少量最重要、可深读 | 标题、变更点、为何重要、出处、风险、当前可证状态 | 不得用主观排名覆盖 G2 hold |
| Radar | 简短但可能有价值的前沿发现 | 1–2 行、原始来源、未证实风险 | 不制造确定性，不硬凑数量 |
| Archive | 完整可检索的合法材料/候选 | 版本、时间、来源、采集故障/屏蔽原因 | hold 只展示许可的安全元数据，不宣传未经证实事实 |

卡片数量由预算和资格决定，不能强行填满“2 条重点+5 条速览”。阅读秒数是 G3 未校准的估值，UI 明确写“预计阅读时间”，不是用户真实耗时。

### 3.4 可访问性与性能初始目标（工程目标，不是已经测量）

- 桌面宽屏优先，兼容常见平板窄屏；键盘操作与合理焦点恢复；语义标题和 aria 状态；减少动画偏好；重要状态不只靠颜色。
- 先显示持久化的最近一份可信快照，刷新在后续进行；避免白屏等待整条管道。
- 单次简报以最多 100 个事件作为初始受控负载测试，具体容量以 PR1 性能基线调整；不要无界遍历整个历史库。
- 任何 HTML/Markdown/新闻片段必须通过现有安全阅读器或严格输出转义；不能渲染可信程度未知的上游 HTML。

---

## 4. 核心工程难点：实时证据与 G2/G3 的正式桥接

### 4.1 不允许的捷径

以下实现不得进入 G4：

- 从 `articles.title`/summary 直接拼成 G3 `IntelligenceItem` 并将其标记 `source_attributed`；
- 使用 `synthetic_contract_probe` 生产真实今日简报；
- 在运行时调用 `G3ReplayInput.model_construct`、`model_copy(update=...)`、手改 SHA 或伪造 accepted G2 manifest 绕过校验；
- 使用当前网页正文覆盖旧版快照，或把 `published_at` 当已观察的 `available_at`；
- 因引用存在就认定 semantic support 为 true；
- 因事件标题相似就自动把两条新闻映射为同一确定事件；
- 把后评测 Gold、开发参考标签或未来 timestamp 暗中加入生产特征。

### 4.2 建议新增受控 `g4_runtime_local_v1` 通路

G3 的现有 `accepted_g2` 和 `synthetic_contract_probe` 是**离线加载入口**。G4 应建立独立、版本化、受安全审查的运行时适配层，明确 `runtime_local_v1` 与离线固定 pin 不同，不声称得到 G2 历史验收认证。

```
Existing feed/RSS ingestion -> SQL Article (unchanged)
         | transactional, observed capture
         v
G4 DocumentVersion ledger + rights/source registry + coverage
         | G2 native validators/typed inputs; bounded current session
         v
Native G2 event/claim/evidence/item pipeline (rule only, no live LLM)
         | G4 runtime integrity binding + complete versioned source snapshots
         v
G4 runtime G3 adapter -> validated typed replay/history input
         | reuse G3 pure rank_revisit and plan_briefing where contracts allow
         v
B4 (default) + registered budget policy + strict evidence eligibility
         | atomic release
         v
BriefingSnapshot + API + React
```

先由 Codex 审计 G2 native pipeline、G3 `bridge.py`/`replay.py` 和 `HistoryInput` 对真实文章/`consented_real` Persona/本地历史的兼容性。**优先复用已公开的纯函数与严格契约**，如生产生命周期不能通过当前 G3 的强冻结 envelope，需要新增受控适配契约与等价不变量测试。不要把 `evals` 下的 CLI 直接作为每次 HTTP 请求中的不受控子进程。运行时依赖必须明确列在应用依赖中、可在离线/断网下可靠启动。

必须显式证明：

1. 同一真实文章快照在 G2/G3 输入里有一致的内容摘要/hash/来源与版本；
2. 所有 as_of 相关时间不向过去泄漏；
3. 证据的源角色、许可、引用位置与是否独立来源仍准确；
4. G3 事实签名 v2 的完整 policy/hash 传递到了排名与预算；
5. source gap、unmet protected、所有 archive IDs 保留；
6. 真实 `hold` 只出现在隔离的诊断/Archive，不进 Focus/Radar；
7. 输入未达正式资格时，页面展示 `raw_news_only`/`insufficient_evidence` 等明确模式，而不是编造一份情报；
8. 正式 G1/G2/G3 离线验收工件原样可复现，新的 G4 runtime 结果独立版本化。

### 4.3 对实时输入的审慎选择

- 数据源：优先现有 `data/live_sources.json` 的官方/公开许可技术来源，不在 G4 默认扩增爬虫。
- Article 是给人阅读的当前缓存，不是天然可历史回放的不可变版本。新增独立 `G4DocumentVersion`，记录 `document_id`、`doc_version_id`、`source_id`、`canonical_url`、`content_kind`、`record_origin`、`rights`、`title`、合法引用片段/段落、`observed_at`、`available_at`、可信 `published_at`、content hash、provenance；`article_reading` 的网页正文缓存**不能直接作为事实快照**。
- 仅保留许可允许的正文/片段；`rights=unknown/metadata_only` 只能进入允许的元数据/安全链接降级，不从推理产物填充缺失正文。
- 若现有采集器无法确认原始段落的 `observed_at`，从首次真实观察开始形成新快照，不把旧缓存冒充过去的原文版本。
- 将来源覆盖记录与采集失败区间分开保存；离线/断网期间未知，不等于全网无更新。

---

## 5. 本地持久化、版本与历史

### 5.1 SQLite 新增表建议

优先使用与旧 DB 共存的**新增表**，不要一次性破坏旧表或将 `Base.metadata.create_all` 误认为完整迁移策略。实际设计以 `database.py` 审计后确定。建议：

| 表 | 关键字段 | 不变量 |
|---|---|---|
| `g4_document_versions` | doc_version_id、document_id、source_id、content_hash、observed_at/available_at、rights、metadata_json | 版本只追加；相同内容指纹幂等 |
| `g4_source_coverage` | source_id、start/end、observed_at、status、reason | 覆盖失败不可写 covered |
| `g4_event_snapshots` | snapshot_id、event_key/revision、g2_input_digest、evidence pointers、status | 不修改已发布快照 |
| `g4_briefing_runs` | run_id、status、as_of、config_hash、input_digest、error/metrics | 完整状态机、取消/过期防迟到发布 |
| `g4_briefing_snapshots` | briefing_id、run_id、generated_at/as_of、manifest/hash、plan_json、status | 仅事务发布的完整 validated plan 可被读取 |
| `g4_delivery_items` | delivery_id、snapshot_id、position、tier、content refs | `included` 与客户端 `rendered` 不混淆 |
| `g4_interactions` | interaction_id、delivery/item refs、kind、occurred/available_at、idempotency_key、retracts_id | append-only，精确绑定快照，重复写入不重复计数 |
| `g4_persona_versions` | persona_id/version、available_at、preferences_json、provenance | 版本化，改偏好不能重写过去 |
| `g4_trust_heads` | journal namespace、head/hash、revision | 与日志/事务原子提交并可检测回滚与断链 |

允许归并表，但必须保存语义和唯一键。创建显式 migration/backfill/rollback 计划：DB 备份与恢复、schema 版本检查、向前迁移/可逆迁移边界、空数据库和旧数据库测试；不得删除旧 Goals/Article/Run/Decision/Schedule。

### 5.2 生产历史写入时机

- `included`：一条候选成功进入**已发布** Delivery/BriefingPlan 时记录，不能说明用户看到；
- `rendered`：客户端用 IntersectionObserver 或等价可见性确认**对应条目实际进入视口**时上报，不能因 API 已返回或列表在 DOM 内就记录；
- `opened`：点击详情且详情已成功呈现时记录，不把它当成掌握；
- `acknowledged`：用户主动点击“已了解”；
- `dismissed`：用户主动点击“不相关/暂不关注”；
- 撤销反馈：append-only retract event，且原事件有同主体和 item/version scope；不更新旧事实。

API 写入必须支持 Idempotency-Key/唯一业务键、exact version precondition、并发 CAS、事务提交，拒绝旧版本引用、重放与不匹配的 trusted head；不因浏览器重试而生成多次曝光。单机 SQLite 在同进程锁与数据库事务下测试，遇到双实例并发要 fail-closed，不能宣称已具备多进程强一致集群。

### 5.3 隐私与权限

当前 FastAPI 是**本地单用户 starter**，不是互联网服务。G4 默认绑定 loopback、限制 Host/Origin/写请求的站点来源；只允许明确本地使用，不虚称多用户认证安全。用户 Persona 与反馈本地保存，提供导出/清空 G4 数据的明确动作和删除范围，默认无外部分析 SDK、第三方画像或自动上传。保持 `dev-diaries/`、密钥、`.local/` 数据不上 Git。

---

## 6. API 契约（建议，PR4 以代码审计后定版）

使用独立 `/api/intelligence` 路由/服务对象，避免把业务策略硬编码进 `main.py`。所有写请求使用严格请求 schema、幂等、预期版本与错误码。以下路径是**建议新增**，不是宣称已实现：

| Endpoint | 用途 | 必须满足 |
|---|---|---|
| `GET /api/intelligence/status` | 应用可用性、来源范围、最近成功简报、pipeline 模式 | 明确 `live_verified` / `raw_news_only` / `demo` / `blocked` |
| `GET /api/intelligence/briefings/latest?budget=420` | 读取最近已发布的简报快照 | 只读，不自动记录 rendered；返回 snapshot/version/ETag |
| `GET /api/intelligence/briefings/{id}` | 访问历史不可变快照 | 不将现时正文覆盖当时证据 |
| `POST /api/intelligence/briefings` | 用户授权后启动有界生成/刷新 | Idempotency-Key、接受条件、状态码、无迟到发布 |
| `GET /api/intelligence/runs/{id}` | 任务进度/失败原因 | running/failed/cancelled/completed，不能把失败当成功 |
| `POST /api/intelligence/runs/{id}/cancel` | 取消生成 | 取消后不得新发布简报 |
| `GET /api/intelligence/events/{snapshot_id}` | 证据、来源、历史版本与引用详情 | 严格引用解析，不能返回凭空文本 |
| `GET /api/intelligence/archive` | 完整候选/资料库、安全 hold 元数据 | 分页、按来源与时间过滤，保留 excluded/truncated |
| `POST /api/intelligence/interactions` | 渲染/打开/确认/不相关事件 | 精确绑定 delivery item/version、幂等、可撤回 |
| `GET/PUT /api/intelligence/persona` | 当前偏好与新增版本 | 明确时间与用户选择，禁止无确认变更重要偏好 |
| `GET /api/intelligence/coverage` | 来源区间、缺口和更新状态 | service_offline、unknown 不转成 no_change |

推荐错误码：`BRIEFING_NOT_READY`、`SOURCE_COVERAGE_INSUFFICIENT`、`EVIDENCE_NOT_ELIGIBLE`、`STALE_SNAPSHOT`、`VERSION_CONFLICT`、`UNTRUSTED_INPUT`、`CANCELLED`、`PIPELINE_UNAVAILABLE`、`PROVENANCE_INVALID`。真实命名按仓库 style 统一。

**原子发布**：运行产生候选和计划 → 全部校验和持久化 → 同一事务切换 latest pointer → 客户端读取。失败/取消/超时不得覆盖先前可信简报。可用并发测试证明。

---

## 7. 六个 PR：严格按序、每次一个

| PR | 主目标 | 主要交付 | 建议工作量（仅规划） |
|---|---|---|---|
| **G4-PR1** | 准入复审、契约与运行时可行性证明 | G3 复审结论、runtime ADR、API/DB contract、最小 vertical slice | 2–4 天 |
| **G4-PR2** | 真实来源版本化摄取与 DB 迁移 | append-only 文档快照、rights/coverage、备份恢复与 backfill 边界 | 3–5 天 |
| **G4-PR3** | 有界 G2/G3 运行时桥接与简报计算 | validated native pipeline、B4 默认、budget plan、真实输入降级 | 4–7 天 |
| **G4-PR4** | 本地历史持久化、API 与取消/幂等 | atomic briefing、delivery/exposure、feedback、接口测试 | 4–6 天 |
| **G4-PR5** | React 三层情报首页与阅读/反馈 | Focus/Radar/Archive、证据详情、coverage、UI 可访问性 | 3–6 天 |
| **G4-PR6** | E2E、真实来源烟测与 G4 Beta 验收 | Playwright、恢复/断网/失败、审查、发布与 G5 handoff | 3–5 天 |

工作量合计是排期量级而不是交付承诺，前半段真源适配可能需要额外迭代。只有完成上游 PR 的实现、独立审查、修复和管理员决策后才进入下一个 PR。

### G4-PR1：契约审计、G3 复审与运行时 vertical slice

**先决条件**：核实最新 G3 事实签名的独立 AI 复审以及所有者对 G4 的实施授权；无必要要求第二真人。审阅 `AGENTS.md`、G3→G4 handoff、G3 contracts / bridge / revisit / budget / fact_signature、G2 PR2–PR6 和原后端/前端。

**实现步骤**：

1. 生成 `audit/G4_ENTRY_REUSE_AUDIT.md` 和 `audit/G4_BASELINE.json`（仅记录本轮实际运行的输出，不复用旧日志冒充新验证）。
2. 明确“当前 G3 accepted input 与 RSS runtime 无直连”差距，画出数据血缘和时序图。
3. 提交 ADR：`G4_RUNTIME_LOCAL_V1.md`，包括现有 G2/G3 纯函数可复用比例、是否需要新的版本化 bridge、失败降级、授权/风险/可逆性。
4. 定义 G4 runtime 文档、事件、简报、交互、配置、数据来源与 `status.mode` 的严格契约；导出 Schema。
5. 建立最小纯函数 vertical slice：一个自带 provenance 的合法合成源快照 → 受控 G2/G3 验证或明确拒绝 → 结果状态；不得从未验收 fixture 生成“真实”推荐。
6. 冻结 PR1 的验收矩阵与 `BRIEFING_NOT_READY` / `hold` 决策；PR2 才接 DB。

**DoD**：列出复用清单、缺口与实施决定；输入真/假/未来/缺许可至少四组反例通过；不存在未经授权修改历史工件；后续每个 PR 的接口路径可以明确指认。

**审查重点**：是否过早宣称 G3/G2 可直接处理 live RSS；是否改变冻结模型绕过 strict 校验；是否将方案层面的合成样例描述为真实新闻验证；G3 复审条件是否有证据关闭。

### G4-PR2：版本化材料与可靠持久化底座

**实现步骤**：

1. 新增 G4 专用 SQLAlchemy 表和幂等迁移；保留旧数据库与业务表。
2. 在 `NewsIngestor` 完成已确认采集后，以事务方式生成 `G4DocumentVersion`，不得将 `article_reading` 当前网页内容静默作为证据。
3. 生成稳定 `document_id`、`doc_version_id`、规范 source、`observed_at/available_at`、可选 `published_at`、版本链与内容 hash。不得回填过去未知的版本。
4. 保存 rights、content_kind、source_role、provenance；未知许可元数据安全降级。
5. 产生 coverage windows / service_offline gaps，与已有 SourceState 联动但不篡改历史。
6. 完成 DB 备份/恢复、旧库升级/新库创建、重复 RSS、原文更正、部分网络失败、乱序重复写入、事务断电模拟测试。
7. 证明旧 `/api/articles`、NewsLibrary、Goals/Runs/Schedules 和现有 source refresh 回归不变。

**DoD**：每个真实保存的版本都有唯一 ID、内容指纹、真实观察时间和可追踪来源；旧记录未被改写；重复导入幂等；恢复/回滚边界可验证。

**审查重点**：是否把 published 当 observed；是否替换旧文本；rights 不明时错误存储/展示全文；是否有迁移破坏旧记录；source gap 被填为 covered。

### G4-PR3：G2/G3 实时受控执行与资格门禁

**实现步骤**：

1. 从 PR2 新增的 immutable snapshot 构造 G2 原生类型，按当前 G2 真实可用函数执行事件分组、主张/证据、规则情报；不得用拼接 JSON 伪造 G2 正式输出。
2. 设计并实现独立 `runtime_local_v1` integrity envelope，保留源快照、G2 typed fields、event lineage、policy hashes、版本、时间和完整候选池。
3. 经明确校验把运行时信封转换为 G3 可以处理的严格 replay/history。优先复用 G3 纯函数/验证器；若冻结的 `G3ReplayInput` 不允许真实运行时对象，**新建 G4 版本化适配，不要把 synthetic/accepted_g2 伪装成实时输入**。
4. 保留 `g3-grounded-fact-signature-v2` 策略/哈希，禁止弱化 comparison/budget 绑定。
5. 排序先用 **B4** 作为默认；P1 仅在显式的开发对照/配置中作为实验选项，不因已有模型分数而推广。
6. 使用 `plan_briefing()` 或等价的受控组合，注册一个明确版本化的 Focus/Radar profile（目前 70/30 是实验配置，不是用户阅读校准结论）。
7. 不满足证据资格时为 `raw_news_only` 或 hold；保留 archive、coverage、未显示原因和 unmet protected。`protected6` 最简可放下却遗漏的例子应当作为已知异常显示/测试，不宣称保证完整显示。
8. 资源限制：候选数量、源数、处理时间、重试、并发、取消、版本冲突；失败不得输出成功简报或改变旧结果。

**DoD**：真实来源元数据合法但证据不足时安全降级；合法且确实满足验证条件的样本能走完 native pipeline；G2/G3 模块的既有冻结/离线回归不变；运行时任何 synthetic 与 real 模式都能严格区分。

**审查重点**：来源伪造、证据/时间泄漏、G3 accepted-g2 pin 伪造、claim semantic 支持夸大、P1 默认化、错误 provenance、hold 被展示。

### G4-PR4：生产历史、简报 API、取消和幂等

**实现步骤**：

1. 建立 G4 append-only interaction journal，head 在 SQLite transaction 内可信保存，崩溃恢复与冲突拒绝；不直接调用仅供 synthetic 文件的 `history_store.append_interaction` 写生产用户日志。
2. 建立 BriefingRun/BriefingSnapshot/DeliveryItem 生命周期与 latest pointer 原子发布；取消/过期/版本冲突不能迟到写入已发布数据。
3. 实现建议的 `/api/intelligence/*` 路由和独立 Service，状态、briefing、event、archive、coverage、persona、interaction、run/cancel。
4. POST 的幂等键、expected version、SQL 事务及权限边界；rendered 只由客户端确认，不能因响应返回而自动写入。
5. 若打开页面仍有旧可信快照，先返回旧快照并标明截至时点，再可选择生成新简报；网络故障保留旧快照且提供 source gap。
6. 测试并发重复写入、双请求、取消 race、旧 snapshot event、重启/断电、断网、数据库锁、损坏 head 与回滚检测。

**DoD**：有事务/幂等/取消测试证据，未授权数据不泄露、事件不乱计；旧 API 全部回归；成功和失败的 HTTP 语义一致。

**审查重点**：重复 rendered/ack、opened 误当 learned、取消后 late publication、trusted head 只存在同一不可信日志、SQLite 原子性与本地网络访问。

### G4-PR5：React 情报首页、证据详情和反馈

**实现步骤**：

1. `App.tsx` 默认页面从 `library` 改为 `intelligence`，继续保留旧 NewsLibrary、ArticleReader、GoalWorkspace、日程和历史入口。
2. 新增 typed API、BriefingHome、FocusCards、RadarList、CoverageStatus、EvidenceDrawer、BriefingHistory、FeedbackControls；实际组件名允许按既有风格收敛。
3. 初次使用显示源范围/预算/Persona、原始资料库入口；空数据/hold-only/断网不显示假的智能建议。
4. 展示正确的“上次访问后新增/变化/更正/撤回”状态；不会因为 included 被当作 viewed；任何真实 rendered 只在元素进入视口后发送。
5. 当前证据与旧引用版分离；链接点开固定版本证据和原文，重要不确定性/更正不可隐藏在折叠里。
6. 限定展现为真实 eligible Focus/Radar；Archive 可见全部候选及 excluded/truncated/hold 安全原因。
7. 反馈（已了解/不相关/撤销）具有 pending/失败恢复提示，支持键盘、确认和幂等重试；点击/打开不等于知识已掌握。
8. 预算切换 180/420/900；显示阅读时间为估计值、来源状态、时间覆盖缺口和 `unmet_protected_event_keys`。
9. 不引入站外推送、系统通知、自动订阅或默认无限刷新的 FOMO 界面。

**DoD**：桌面 Chrome/Edge 及窄屏关键路径能完成；键盘/焦点/ARIA 通过；零数据、hold-only、少数焦点、错误/超时、覆盖缺口和历史更正均有明确 UI；旧功能未丢。

**审查重点**：伪造热点/证据、漏掉限制字段、页面渲染误计 render、stale snapshot 误作最新、对原始新闻和合成示例的混淆、交互无响应、旧工作台回归。

### G4-PR6：全链 E2E、真实材料试点与最终 G4 验收

**实现步骤**：

1. 固定 PR1–PR5 的 release、Schema、API、manifest、source policy、G3 fact policy、B4 和预算 profile；记录 source SHA 和配置 hash。
2. Playwright（或仓库已有浏览器工具）覆盖首次打开、主动刷新、Focus/Radar/Archive、证据、render/open/ack/dismiss/retract、断网、cancel、错误重试、旧版重访、来源故障、旧页面回归。
3. 新建隔离 SQLite；先运行有明确 rights/provenance 的现实历史材料的**离线可复现快照**，再在用户明确允许联网的情况下做有限实际来源 smoke。若未授权网络，记录 `live_network=not_evaluated`，不得冒充完成；不因此把工程轨道判成必然 FAIL。
4. 对照最初 V1 用户旅程，实际点击核对两条“发生了什么/为什么重要/引用”的重点路径，以及 1–2 条不确定 Radar 或诚实空态；若没有合法合格材料，不得伪造重点卡，可展示已验证的受控真实材料或标记不足。
5. 故障注入：重复 RSS、文章更正、元数据/单位差异、权限不明、来源服务离线、超长内容、阅读器 HTML 注入、取消与重启、日志 head 不匹配、旧版本事件引用。
6. 验证 G1/G2/G3 原有冻结兼容、旧数据备份恢复、完整后端 pytest、Ruff、`evals/run_baseline.py`、前端 build、Playwright，以及所需原生 G3 注册 pytest runner。
7. 保存机器报告、浏览器录像/截图（无用户隐私）、失败清单、命令与退出码、验收矩阵和成本限制。
8. 产出 `docs/G4_ACCEPTANCE.md`、`docs/G4_G5_HANDOFF.md`、`docs/G4_BETA_USER_GUIDE.md`、`audit/G4_RELEASE_MANIFEST.json`。

**DoD**：所有工程硬门槛 PASS，仍未验证的真人效用/真实模型能力单列；原生产数据保留；APP 首页可在受控真实数据下明确展示可信或不足状态；AI review P0/P1 关闭；所有者决定 Beta 和 G5 是否开始。

**审查重点**：真实数据与 synthetic 混用、测试控制面污染、报告 hash/代码不匹配、未运行命令写 PASS、未验证来源价值夸大、E2E 不实际操作、历史快照被偷改。

---

## 8. 测试设计与验收矩阵

以下为 **建议 G4-T01～T56**，Codex 可在 PR1 审计后调整编号，但必须保留覆盖，不得通过删除失败场景通过验收。

| 类别 | ID | 强制场景 |
|---|---|---|
| 准入/契约 | T01–T06 | 当前 G3/所有者状态、显式 runtime mode、错误 source pin、Schema 额外字段、未来 timestamp、synthetic/real 隔离 |
| 文档版本 | T07–T13 | 初次采集、同 hash 重复、正文更正、旧版本 immutable、unknown rights、published≠observed、断网 source gap |
| G2/G3 桥接 | T14–T23 | 原生 G2 校验、citation/ref/scope、保留独立性 unknown、hold 不晋级、未来证据、事实签名符号/单位、B4 默认、P1 实验隔离、archive 全池、unmet protected 透出 |
| 历史 DB | T24–T31 | included≠rendered、DOM 未进入视口、opened≠ack、append-only retract、幂等、重启、并发 CAS、trusted-head 回滚拒绝 |
| API | T32–T39 | 状态/briefing/event/archive/coverage、POST 幂等、取消 race、陈旧快照、404/409/422、Origin/Host 约束 |
| React | T40–T47 | 默认主页、首次空态、Focus/Radar、证据定位、Archive hold、安全 HTML、键盘焦点、预算/来源缺口 |
| E2E/回归 | T48–T56 | 1/3/7 天重访、断网/来源异常、取消后旧快照、超长卡片、反馈撤回、旧 Goal/Run、Windows 浏览器烟测、正式 source/manifest 绑定、所有 P0/P1 关闭 |

### 8.1 G4 工程门槛 H00–H12

- **H00 前置批准**：G3 的阻断性缺陷已复审关闭或有明确批准的延期处置；G4 的代码实施获所有者授权。
- **H01 来源/权利**：来源、时间、内容 hash、rights/provenance 完整；无伪造历史版本。
- **H02 运行时契约**：G2/G3 native 校验通过，或明确安全降级；无 synthetic 冒充 live。
- **H03 证据安全**：hold 不进入 Focus/Radar；引用/claim/独立性/不确定性不升级。
- **H04 排名/预算**：B4 默认、P1 实验隔离、版本 policy 绑定、archive/unmet protected 全保留。
- **H05 生产持久化**：SQLite 迁移、快照事务、历史 append-only、trusted head 和恢复测试通过。
- **H06 曝光语义**：included/rendered/opened/ack/dismiss/retract 区分，幂等和可撤回。
- **H07 取消与失败**：cancel/late-result/timeout/partial write 无静默成功；旧快照保留。
- **H08 API/隐私**：本地单用户边界如实声明，写接口校验和错误码/来源约束。
- **H09 用户体验**：用户自主打开；空态/断网/证据/Archive/反馈/可访问性完整。
- **H10 回归兼容**：旧 Goal/Run/Decision/Schedule/NewsLibrary 无意外退化，G1–G3 不被改写。
- **H11 真实浏览器**：E2E/浏览器关键场景实际执行并保存证据；未执行写 NOT_EVALUATED。
- **H12 报告诚实**：测试/命令/退出码/本地运行工件与 SHA 可复现；AI 开发与真实独立用户研究分开。

### 8.2 G4 阶段不能宣称的结果

- 不因所有 H 门槛通过就称 P1 效果更好；
- 不因 source poll 在本地运行就称 24/7 永久在线覆盖；
- 不因文章来源真实就称所有主张已经语义独立支持；
- 不因用户 opened 就称用户已了解；
- 不因浏览器显示了一个条目就认为它 `rendered`，除非视口确认上报并持久化；
- 不因模拟 E2E 通过就称真实用户效用已验证。

---

## 9. Codex 工作规程与每 PR 审查门槛

**角色**：项目所有者只负责边界、授权、验收和产品决断；Codex 实施 Agent 负责代码/测试/文档；另一 Codex 会话做只读代码审查；自动化控制面保证客观门槛。**没有强制两个真人的门槛。**

**循环**：`Plan（检查与设计）→ Agent/Code（实施单个 PR）→ 新会话只读审查 → 修复 → 复审 → 所有者决定下一 PR`。

审查发现分级：

- P0：权利/证据严重污染、未来信息/Gold 泄漏、用户数据破坏、越权推送、密钥泄漏、未授权重写冻结结果。
- P1：时间/身份/引用错误、数据原子性或取消失败、hold 展示、日志 head 不可信、浏览器关键路径不能工作。
- P2：非核心解释不足、个别异常漏诊断、可访问性不足但有可用替代、文档偏差。
- P3：美观、非核心重构和建议。

P0/P1 必须关闭；P2/P3 有记录、后续归属和所有者知情可延后。审查默认**只读**，不得顺手“重构整个仓库”或发布 PR。AI 交叉审查不能称为独立人工验证。

每个 PR 交付 `implementation_report.md`、`review_report.md`、`fix_closure.md`（有 finding 时）、`re_review.md`、测试/日志/pin 和所有者批准状态。推荐放 `audit/g4/prN/` 的非敏感摘要；较大运行工件放 `.tmp/g4/`，commit 时绝不能包含私有用户数据、密钥、`dev-diaries/`。

实际环境检查按 `AGENTS.md`：

```bash
python -m ruff check backend tests evals
python -m pytest -q
python evals/run_baseline.py
(cd frontend && npm run build)
```

**注意**：G3 最终复验需遵循其 `pytest_runner` 注册控制面，指定有界 `--basetemp`、批准插件、控制记录和实际固定 pins；新版本不得用普通 pytest 成功替代严格复验。Playwright/浏览器依赖在 PR1 审计中核对；未实际运行浏览器时不能称已完成 E2E。

**提交策略**：每个 PR 单独分支/diff/审查与验收。Codex 不得在未经所有者明确同意时执行 commit、push、merge、reset/force 等 Git 写操作；不要强制用 GitHub 网页 PR 代替本地可审查 diff。

---

## 10. 风险与应对

| 风险 | 现实证据 | 应对 |
|---|---|---|
| G3 仅支持 pinned offline inputs | G3 replay 与 G3→G4 handoff | PR1 先做 ADR；PR3 建受控 local-runtime 适配；不伪造 accepted_g2 |
| G3 G4 复审尚待关闭 | 事实签名修复报告 / handoff | G4-H00 强制处理；不能改历史报告 |
| B4/P1 无稳定差距 | PR5 验收 | 默认 B4；P1 仅可显式实验 |
| G3 贪心预算漏报可放下的保护项 | protected6/420 | UI 透出 unmet_protected；优化需另案/对照，不在 G4 偷改研究实现 |
| 真实 RSS 历史版本不足 | Article 为可变缓存 | 从首次可证明的真实观察时点开始记录 immutable DocumentVersion |
| 未知许可/来源独立性 | source rights/lineage | metadata-only、引用与安全降级，禁伪造支持 |
| 离线中断后的“7 天无更新”幻觉 | 本地进程并非 24/7 | source coverage 显示 unknown/service_offline |
| append-only 本地日志回滚 | 当前仅 synthetic JSONL | PR4 SQLite 可信 head 与双实例/备份恢复测试 |
| 全屏 UI 重写破坏旧功能 | 当前 App/NewsLibrary/Goals 稳定可用 | 新增新页面、旧功能兼容回归 |
| 用户被通知打扰 | V1 无默认站外推送 | G4 禁外部通知和不经用户允许的动作 |
| 新功能工程 scope 爆炸 | 单人开发 | PR 门禁、独立审查和 P0/P1 优先，复杂能力留 G5 |

---

## 11. 可交付文件清单（建议）

```
docs/plans/G4_IMPLEMENTATION_PLAN.md
docs/plans/CODEX_G4_EXECUTION_PROMPT.md
docs/adr/G4_RUNTIME_LOCAL_V1.md
audit/G4_ENTRY_REUSE_AUDIT.md
audit/G4_BASELINE.json
backend/cfaw_news/intelligence/   # 根据实际审计决定包结构
backend/cfaw_news/migrations/     # 或仓库惯用的显式迁移方案
frontend/src/BriefingHome.tsx
frontend/src/BriefingDetails.tsx
frontend/src/BriefingHistory.tsx
frontend/src/api.ts               # 新增严格 typed intelligence API
tests/intelligence/               # Python service/DB/contract
tests/e2e/                        # 若已有 Playwright 体系，沿用其目录
docs/G4_ACCEPTANCE.md
docs/G4_G5_HANDOFF.md
docs/G4_BETA_USER_GUIDE.md
audit/G4_RELEASE_MANIFEST.json
```

上表路径只是建议，不代表文件已存在。Codex 只能按 PR 新增必要文件，不能一开始铺满占位模块。

### 完成标准

当用户主动打开本地 CFAW News 时，能够看见从受控真实资料形成的、**明确区分已验证与未验证**的 Focus/Radar（若存在合格候选）和完整 Archive；看见来源覆盖缺口、已知风险与历史变化；能查看当时证据、反馈和撤回；断网/取消/重启均不篡改历史；旧工作台仍然可用。若情报资格不足，应明确告知并保留原始资讯功能，而不是以合成内容填补。

**G4 要将离线可复现的技术研究转化为可信任的日常工具，而非制造一份看似智能、实际上没有证据保障的新闻首页。**
