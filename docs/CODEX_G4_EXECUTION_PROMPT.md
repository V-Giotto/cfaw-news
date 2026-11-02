# CFAW News — CODEX_G4_EXECUTION_PROMPT.md

> **版本**：`g4-codex-v1.0`（2026-10-30）  
> **项目**：https://github.com/V-Giotto/cfaw-news  
> **建议仓库路径**：`docs/plans/CODEX_G4_EXECUTION_PROMPT.md`  
> **配套规格**：`docs/plans/G4_IMPLEMENTATION_PLAN.md`  
> **工作模式**：单人管理员 + Codex 实施 Agent + 新会话只读审查 Agent；每次只完成一个 PR。  
> **本文件只是提示词文档**：不表示已授权执行任何 GitHub 写操作或改变历史验收状态。

---

## 0. 操作方式：Plan 与 Agent/Code 模式怎么选

**首次启动：Plan 模式。** 将第 1 节完整复制给 Codex。Codex 先读取当前代码和 G3 最终修复证据、审计 G4 计划、识别阻断项。你只需确认产品边界、是否允许实施 G4，以及前置审查是否关闭。

**执行每个 PR：Agent/Code 模式。** 每次只复制相应的 `G4-PRN 实现提示词`。Codex 先列文件/契约/测试，再实施**这一个 PR**，实际运行适用测试，输出报告，然后停止。不要让它一次实现六个 PR。

**审查每个 PR：新 Codex 会话 + 只读要求。** 复制相应 `G4-PRN 审查提示词`。可以在 Plan/Ask 模式执行，只读取 diff、测试、报告；不自动修复。审查 findings 交给实现会话，使用第 8 节修复提示词，再新开会话复审。完成后由所有者决定是否继续。

**不要默认 commit、push、merge 或修改历史验收记录**。如果 Codex 会自动修改/提交仓库，必须显式设置适当权限和任务范围。对权利、密钥、网络/付费调用、数据库不可逆操作、删除真实用户数据，要单独获取管理员授权。

---

## 1. 开始 G4 前：仓库检查与 G3 准入复审提示词（Plan 模式）

```text
你是 CFAW News 的资深工程师、产品架构审查员和评测工程师。
现在只做 G4 开工审计与计划校正，不修改代码、不执行 Git 写操作。

以当前仓库真实 HEAD、当前工作区和 source of truth 为依据；不能只相信之前的回答或计划文件。先检查：
  git status --short
  git branch --show-current
  git rev-parse HEAD

至少读取以下文件：
  AGENTS.md
  docs/CFAW_News_V1.md
  docs/ARCHITECTURE.md
  docs/G3_G4_HANDOFF.md
  docs/plans/G3_IMPLEMENTATION_PLAN.md
  docs/plans/G4_IMPLEMENTATION_PLAN.md
  evals/intelligence_g3/README.md
  evals/intelligence_g3/reports/PR5_ACCEPTANCE.md
  evals/intelligence_g3/reports/PR5_REVIEW_FIXES.md
  evals/intelligence_g3/reports/FACT_SIGNATURE_REVIEW_FIX.md
  evals/intelligence_g3/contracts.py
  evals/intelligence_g3/bridge.py
  evals/intelligence_g3/replay.py
  evals/intelligence_g3/rankers.py
  evals/intelligence_g3/revisit.py
  evals/intelligence_g3/history.py
  evals/intelligence_g3/history_store.py
  evals/intelligence_g3/budget.py
  evals/intelligence_g3/budget_contracts.py
  evals/intelligence_g3/fact_signature.py
  evals/intelligence_g2/pr2/、pr3/、pr4/、pr5/、pr6/ 的正式 contracts/pipeline/handoff
  backend/cfaw_news/database.py
  backend/cfaw_news/ingestion.py
  backend/cfaw_news/main.py
  backend/cfaw_news/service.py
  frontend/src/App.tsx
  frontend/src/api.ts
  frontend/src/NewsLibrary.tsx
  现有相应 pytest、Schema、CI、manifest 和本地验收工件（如果存在）。

进行以下审计：
A. G3 最终事实签名修复的独立复审是否真正关闭？哪些结果是仓库报告、哪些测试本轮实际重跑？不能拿 commit message 的 PASS WITH CONDITIONS 当正式全部通过。
B. 本次管理员是否明确授权 G4 的代码实施？G3/G4 handoff 旧字段、报告和决策之间有差异时不要偷偷修改历史状态；缺明确授权则先停在 Plan。
C. 确认 G3 rank_revisit/plan_briefing 的完整输入契约，G3 accepted_g2 与 synthetic_contract_probe 的用途，以及真实 RSS 是否有合法 runtime 入口。严禁从 synthetic fixture 伪装真实新闻。
D. 校验当前事实签名 g3-grounded-fact-signature-v2 的 policy/hash 绑定；不得使用旧验收 pin 承诺兼容。
E. 解释为什么当前 G3 的 synthetic file history 不等于生产 SQLite 持久化；审计现有 Article/SourceState/ArticleReading 的可复用边界。
F. 设计 G4 runtime_local_v1 的最小安全通路，不重写 G2/G3 算法，不绕过校验或证据资格。
G. 默认 B4；P1 尚无稳定增益证据，只能显式实验；70/30 是未校准候选配置，保护事件可能因贪心预算分配被遗漏。
H. 确认旧 Goal/Run/Decision/Schedule 与 NewsLibrary 的回归范围。

输出《G4 启动审计》：HEAD/worktree、证据路径、可复用模块、必须新增契约、风险、六个 PR 的依赖/DoD、需要管理员决策的事项和阻断状态。分清源码事实、历史运行记录和本轮真实验证。

不提交/推送，不运行外部模型/付费 API，不联网采集，不写真实用户数据库，不读取/上传 dev-diaries/。
完成后停止，等待管理员确认是否实施 PR1。
```

---

## 2. G4-PR1：准入、契约与运行时可行性

### 2.1 实现提示词（Agent/Code 模式）

```text
开始实施 CFAW News G4-PR1。
先读 AGENTS.md、docs/plans/G4_IMPLEMENTATION_PLAN.md、前置 G4 启动审计、当前 G3_G4_HANDOFF.md。核对 HEAD/worktree、管理员对 PR1 的明确授权与 G3 复审关闭状态。

本轮只做 PR1：
1. 产出 audit/G4_ENTRY_REUSE_AUDIT.md 与 audit/G4_BASELINE.json，严禁拿旧日志当本轮测试。
2. 形成 docs/adr/G4_RUNTIME_LOCAL_V1.md，说明真实 RSS Article→immutable DocumentVersion→native G2→validated G3→BriefingPlan 的各接口、缺口、失败降级与安全边界。
3. 定义严格的版本化 G4 runtime/document/briefing/interaction/config/status 契约，优先复用已有严格模型与 pure functions，不提前创建整套生产服务。
4. 明确 runtime_local 与 accepted_g2、synthetic_contract_probe 的区别；不得伪造 G3 accepted pin 或 model_construct 绕过验证。
5. 建最小可回放 vertical slice：合成合规来源、未来时间、未知 rights、hold-only 等输入能得到可解释的合法结果或拒绝；synthetic 只用于测试。
6. 先冻结真实来源/证据/时序/资格/展示状态的硬门槛与错误码。
7. 输出 PR2～PR6 的精确文件触达与测试依赖；不实现数据库迁移、不改前端、不调用真实网络/模型。

先陈列每项改动的文件与测试矩阵，然后实现、运行当前 PR 相关测试、Ruff/Schema、适用回归；记录 argv、退出码、日志、源码/配置/输出 pin。最后生成 PR1 实施报告，区分 PASS/FAIL/BLOCKED，停止并等待审查。
```

### 2.2 独立只读审查提示词

```text
你现在是 G4-PR1 的只读审查 Agent。不要修改代码或文档，不自动修复；先核对 PR1 diff 范围、当前 HEAD、审计报告和实际测试日志。

重点检查：
1. 是否真的核对 G3 事实签名复审状态与 G4 管理员授权，是否以旧报告/commit 标题冒充全部验收；
2. G4 runtime 输入是否与 accepted_g2/synthetic_contract_probe 明确隔离；
3. 是否存在伪造 trusted pin、跳过 native G2/G3 校验、复制不完整 schema 的捷径；
4. 是否区分来自 `Article` 的缓存、阅读器抓取内容和正式不可变证据；
5. 未来时间、来源许可、hold、source gap、未知独立性是否保留；
6. B4/P1、事实签名 policy、预算 profile 结论是否符合 G3 报告；
7. `dev-diaries/`、密钥、原始 G1/G2/G3 工件是否未受影响；
8. 测试是否真实运行，负例是否有非零拒绝/明确处理；
9. PR1 是否偷偷开始 PR2 迁移、PR3 runtime 或 PR5 UI；
10. 计划/ADR 是否足以使后续 PR 不需要靠猜测命名和信任边界。

输出 P0/P1/P2/P3 findings（每条有路径/行号、证据、影响、最小修复建议），已验证项、未验证项、PASS/BLOCKED，特别指出哪些结论只基于静态阅读。不要假装真人独立评审。
```

---

## 3. G4-PR2：真实材料版本化、来源许可与迁移

### 3.1 实现提示词

```text
实施 CFAW News G4-PR2：版本化资料账本与本地 DB 迁移。
先重新检查 HEAD/worktree、PR1 实现/独立审查/修复/管理员批准记录；没有上游关闭记录时先报告。

仅做本 PR：
1. 在与旧业务兼容的前提下新增 G4 专用 SQLAlchemy 表及显式 migration/backfill/rollback/backup 方案。
2. 接入现有 NewsIngestor 的已确认抓取写入点，生成 immutable G4DocumentVersion，保留 document_id、doc_version_id、source_id、content_kind、rights、provenance、真实 observed_at/available_at、可选 published_at、content hash、版本链。
3. 已有 Article 缓存不是历史正文快照；不得将当前 article_reading/web text 回填过去。
4. rights 为 unknown/metadata_only 时限制保存和展示，至少保留可合法显示的来源/安全元数据；引用内容必须有受控来源。
5. coverage windows 区分 covered/partial/failed/unknown/service_offline；不能在离线期写覆盖确认。
6. 重复采集/相同 hash 幂等，新内容产生新版本，旧版本不改写；事务失败不留下半条证据。
7. 测试新库、旧库升级、备份恢复、版本变更、乱序采集、重复写入、来源失败/间断、unknown rights 和旧 Article/Goals/Runs/Schedules 回归。
8. 不加入实时 G2/G3 生成，不改 G1/G2/G3 冻结数据，不做 UI、网络/模型扩权。

先提交文件变更方案与数据库风险说明，再实现。保存真实测试结果、源码/Schema/version SHA、迁移与恢复日志。输出 PR2 报告，停止等待独立审查。
```

### 3.2 独立只读审查提示词

```text
只读审查 CFAW News G4-PR2，不要修改文件。
对照 PR1 ADR、G4 计划、SQLAlchemy 现有业务表和 ingestion.py，重点审查：
1. observed_at/available_at 是否是可证明的实际观察时间，有无把 published_at 当做采集时间；
2. 文档 ID/版本 ID/内容 hash 是否稳定、不可变、唯一且可追踪；
3. 当前 article_reading 抓取文本是否被非法当作过去证据；
4. rights、source_role、来源独立性/元数据缺失是否安全降级；
5. 覆盖失败是否被错误标成 covered；
6. 旧表迁移/备份/恢复/rollback 是否真的保持 Goal/Run/Article/Decision/Schedule 不变；
7. 重复写入、事务异常、重启和 concurrent ingestion 是否有测试；
8. 旧新闻 API/Reader/SourceState 是否回归；
9. 是否意外改写 G1/G2/G3 frozen pins、历史工件或私有目录；
10. 失败、跳过、未运行测试是否如实披露。

按 P0/P1/P2/P3 输出证据化问题、路径/行号、复现方式、影响、最小修复建议；给 PASS/BLOCKED 及残余数据迁移风险。
```

---

## 4. G4-PR3：受控 G2/G3 runtime bridge 和默认 B4 简报

### 4.1 实现提示词

```text
实施 CFAW News G4-PR3：受控本地 G2/G3 运行时桥接与排序/预算计算。
先核对 PR2 通过及修复闭环、当前 HEAD/worktree、G4_RUNTIME_LOCAL_V1 ADR、G2/G3 native pipeline 和 G3 fact_signature policy/hash。

仅做本 PR：
1. 将 PR2 的 immutable G4DocumentVersion 和 source/coverage/provenance 投影为 G2 正式、受限的原生数据模型；遵守时序与引用校验。
2. 使用 G2 正式事件→主张/证据→规则 IntelligenceItem 的纯函数/校验入口，不允许手工拼 JSON 标记证据已经 verified，不启用真实 LLM。
3. 建独立版本化 runtime_local_v1 envelope 与 G3 纯排序/预算能力的经过验证适配；不能伪造 accepted_g2 的封存身份，也不能用 synthetic_contract_probe 做真实推荐。
4. 显式校验 event_key、event_revision、快照、引用、source coverage、lineage、rights、as_of、完整候选池；保留 unknown 和 hold，不允许未来信息进入。
5. 保留 g3-grounded-fact-signature-v2 和 policy SHA 的完整绑定；旧 ranking/config pin 必须拒绝。
6. 默认 B4；P1 仅通过显式开发实验配置运行，不因 P1 已实现便默认使用。
7. 注册一个版本化 BudgetConfig/profile（当前 70/30 是实验配置），以 plan_briefing 或等价受控流程生成结果；保留 archive_snapshot_ids、unmet_protected_event_keys、coverage、excluded/truncated 及原因。
8. 对 rights/引用/资格/来源有疑义的实时输入返回 raw_news_only 或 evidence_not_ready，不生成假的 Focus/Radar；synthetic/real 模式永不混排。
9. 测试多源同事件、独立性 unknown、版权范围、未来文档、事实数值/符号、hold-only、超长、取消、限时与重复输入。
10. 暂不写 HTTP API 和前端；不修改 G1/G2/G3 历史验收资产。

必须说明：当前 G3 正式 replay 绑定的 accepted_g2 只是离线证明，不等于生产 runtime；如果无法在不绕过不变量的情况下复用 G3 算法，停止并提交 ADR 变更或安全降级，不得填补虚构字段。

完成测试、输入/输出 SHA、阶段日志和 PR3 报告，停止等待审查。
```

### 4.2 独立只读审查提示词

```text
只读独立审查 CFAW News G4-PR3。不要修改文件。
必须按数据血缘走读至少一个正常样例和一个拒绝样例，核查：
1. real Article→immutable version→G2 native→G3 ranking 的每步是否有合法契约和来源；
2. 是否伪造 accepted_g2 pin、借 synthetic probe 生产实时报表、使用 model_construct 绕过校验；
3. 是否把引用存在当语义支持、把官方声称当第三方独立验证；
4. 是否用未来网页、后评测 Gold/labels 或不合法 rights 填补当前字段；
5. event identity、revision、source coverage、claim scope、lineage 是否完整；
6. fact signature v2、config/hash/budget binding 是否准确；
7. B4 默认、P1 仅显式实验、同池公平性是否成立；
8. hold/unsupported/unknown 是否无法变成 Focus/Radar；
9. Archive 所有候选、unmet protected、truncated/excluded 理由是否保留；
10. 无法合格时是否安全返回 raw_news_only，而不是生成假的智能简报；
11. 超时/取消/失败是否停止计算，任何历史数据是否被改写；
12. PR3 是否没有越界实现 UI/生产 API/真实模型。

输出 P0/P1/P2/P3、详细代码证据、受影响的实际用户场景、建议修复、PASS/BLOCKED。不能以全部 pytest PASS 替代事实性审查。
```

---

## 5. G4-PR4：本地历史、API、取消与幂等

### 5.1 实现提示词

```text
实施 CFAW News G4-PR4：生产历史持久化、简报 API 与任务生命周期。
先审计 PR3 关闭记录、当前 HEAD/worktree、旧 backend/cfaw_news/main.py/service.py/database.py 的取消、事务和单用户约束。

仅做本 PR：
1. 建立真实本地 SQLite 的 briefing run、快照、delivery items、append-only interactions、persona versions 和 trusted heads；按 PR1 ADR/PR2 migration 方案增量实现。
2. trusted head/append entry 必须事务原子提交；验证崩溃恢复、断链检测、expected-head CAS 和重复请求去重，不能把 G3 synthetic JSONL history_store 直接作为生产用户存储。
3. 定义确切写入时机：included 在发布 delivery 后，rendered 仅收到客户端可见性确认时，opened 在实际详情打开后，ack/dismiss 由明确用户操作；opened 不等于 learned。
4. append-only 反馈撤回与历史版本时间可见；浏览器 retry/双击/断网重试使用幂等键与唯一约束，避免重复记数。
5. 实现独立 /api/intelligence 路由：status、briefings/latest、briefings/{id}、POST briefings、run status/cancel、events/detail、archive、coverage、interactions、persona；实际字段严格 Schema 化。
6. 仅在完整 G2/G3 校验和事务成功后原子发布最新快照。失败/取消/版本过期/来源中断保留旧快照，不能 late publish。
7. API 返回每份快照的 as_of/generated_at、pipeline mode、evidence status、coverage gaps、version/ETag、完整 Archive 和未满足保护项；不将计划的预计阅读时间伪装成真实行为。
8. 本地单用户 starter 必须有 Host/Origin、写接口/内容长度/并发界限；不虚构多用户 auth 或云隔离。
9. 测试负例：重复 POST、并发 commit、取消 race、旧快照引用、错误 origin、无证据、损坏 head、磁盘失败、重启、超时、旧 API 回归。
10. 不改 React；不发送系统、邮件、桌面推送；不主动执行第三方操作。

输出 OpenAPI/Schema 变更、DB migration 测试、实际命令、日志、pins 与 PR4 报告，停止等待审查。
```

### 5.2 独立只读审查提示词

```text
请只读审查 CFAW News G4-PR4，不修改文件。
重点核查：
1. 生产 DB 是否真正具备原子发布和可验证的 trusted head，是否防回滚/断链；
2. included/rendered/opened/ack/dismiss/retract 是否写入不同且正确的语义事件；
3. API 返回/DOM 存在是否被错误当作 rendered；
4. 幂等键、版本 precondition、唯一约束、重复/并发写是否完整；
5. 取消后 late result 是否还能发布，失败是否覆盖上一份可信快照；
6. SQLite 多连接/事务/重启恢复/本地双进程边界是否正确或保守 fail-closed；
7. 每份简报快照证据引用是否绑定版本，历史内容不会被当前页面替换；
8. Host/Origin/本地单用户访问边界与输入 Schema 是否合理；
9. 权利/hold/unknown/coverage/unmet protected 是否按原契约返回；
10. 旧 Goal/Run/Decision/Schedule 和 articles API 是否回归；
11. 错误码、HTTP 状态、取消行为是否由对抗测试验证；
12. 是否新增未授权外部推送或 Git/private data 写入。

输出逐项 P0/P1/P2/P3、代码路径/行号、可复现测试和最小修复建议，给 PASS/BLOCKED 及未验证项。此阶段工程 PASS 不等于生产互联网安全认证。
```

---

## 6. G4-PR5：React 情报首页与真实交互

### 6.1 实现提示词

```text
实施 CFAW News G4-PR5：React 三层情报首页及反馈 UI。
先核对 PR4 审查/修复闭环、最新 API Schema、当前 frontend/src/App.tsx/NewsLibrary.tsx/api.ts 和原有 GoalWorkspace。

仅做本 PR：
1. 默认打开页面从旧 library 转为 intelligence home；旧 NewsLibrary、ArticleReader、GoalWorkspace、历史与日程保留且可一键进入。
2. Focus/Radar/Archive 三层 UI 与“自上次访问以来”的变更/回访摘要；用户不打开应用时不发任何通知。
3. 对真实 eligible 候选才渲染 Focus/Radar。没有合格材料时诚实显示空态、raw_news_only、source gaps，绝不借 synthetic 填充首页。
4. 显示“发生了什么/为什么重要/证据状态/来源/限制/下一步可选择动作”，未验证、仅源方声称和独立支持需正确区分。
5. 展示 Archive 完整候选与 excluded/truncated/hold 安全原因；hold 只能显示许可元数据，不把其未经验证的断言写成推荐。
6. 证据详情按历史 immutable snapshot 解析引用，允许跳转原始资讯/文章阅读；不得读取当前正文覆盖过去快照。
7. rendered 由视口可见性确认（IntersectionObserver 或同等可靠逻辑）后上报；不要因为请求返回、DOM 节点挂载或预渲染就写 rendered；opened 在详情成功显示后上报。
8. ack/dismiss/retract 都由显式用户操作触发，提供按钮 pending、失败反馈、撤销、幂等重试；用户打开不等于知道。
9. 阅读预算 180/420/900 可切换，标注“估算”；来源 gap、未满足受保护项、历史时间窗口和生成时间显式可见。
10. 加强空/加载/断网/取消/权限不足/版本冲突/长内容状态，键盘焦点、aria、视觉层次和窄屏兼容。
11. 不实现系统/邮件 push、不自动订阅、不触发外部自主行动；不改 G2/G3 评分逻辑或生产数据库。

运行 TS/Vite build、可运行的组件/浏览器定向测试与原页面回归；保存截图或屏幕录像时不包含真实用户私密资料。输出 PR5 报告，停止等待审查。
```

### 6.2 独立只读审查提示词

```text
请只读审查 CFAW News G4-PR5，不修改文件。
重点审查真实前端代码而非仅截图：
1. App 是否真把 intelligence 设为默认且完整保留 NewsLibrary/Goal/Run/Schedule 导航；
2. Focus/Radar/Archive 信息层级是否符合 V1，是否为填满卡片数伪造或重复内容；
3. eligible/hold/placeholder/synthetic/raw 的 UI 来源隔离是否存在绕过路径；
4. 主张、限制、引用、来源覆盖、as_of 和 generated_at 是否全部传达，来源故障不被误当“无更新”；
5. rendered 是否实际可见后写入，是否会因 rerender/scroll/StrictMode 重复写；
6. opened 是否与 acknowledged 完全分离；ack/dismiss/retract 是否显式、可取消、失败恢复；
7. 历史快照引用是否仍绑定当时版本，HTML/文本是否转义；
8. Archive 是否展示被截断/被排除的安全候选而非悄悄丢弃；
9. unmet_protected_event_keys、阅读估时未校准和预算剩余是否可见；
10. 键盘、焦点、aria、空态、断网、移动窄屏和错误边界是否基本可用；
11. 是否有默认外部推送、干扰式提醒或未经批准外部操作；
12. TS build 与旧页面回归是否有真实记录。

输出 P0/P1/P2/P3 findings、路径/行号、复现路径/测试、用户影响与最小修复建议，明确 PASS/BLOCKED 及未测试浏览器/设备。
```

---

## 7. G4-PR6：端到端验收、真实来源试点与交接

### 7.1 实现提示词

```text
实施 CFAW News G4-PR6：正式端到端验收、现实来源试点和 G5 交接。
先核对 PR1–PR5 的全部实现报告、独立审查/修复闭环、当前 HEAD/worktree、G1/G2/G3 pins、数据使用权、G4 ADR、DB schema 和测试控制面。只做 QA、验收和发布文档；不趁 PR6 大改算法。

1. 冻结当前源码/依赖/Schema/config/source-rights/fact-signature policy、B4 默认、budget profile 和真实测试样本快照；所有目录输出独立 manifest/hashes。
2. Playwright 或当前仓库实际浏览器工具执行：首次进入、首页、刷新、Focus/Radar/Archive、证据详情、来源 gap、render/open/ack/dismiss/retract、预算切换、1/3/7 天回访、取消、旧版访问。
3. 使用隔离 SQLite 测试备份恢复/迁移/重复 RSS/事实更正/符号单位/unknown rights/长内容/失败/断网/重启/损坏 head/并发冲突。不得触碰真实用户原库。
4. 测试至少一条来源可核对且权利清楚的非合成历史材料；如果主张仍不足以进入 Focus/Radar，展示诚实拒绝与 Archive 原文，而不是伪造正例。未经额外授权不得做新外部网络抓取；若未做真实网络 smoke，明确写 not_evaluated。
5. 运行 Ruff、完整 pytest、seed baseline、前端 build、浏览器 E2E 和所需 G3 注册控制面复验；记录真实命令、退出码、JUnit、日志、耗时、pins。G1/G2/G3 冻结资产必须保持不变。
6. 至少验证已有旧 Goal/Run/Decision/Schedule 主流程可用；确认无自动推送和无未经用户批准的第三方操作。
7. 生成 docs/G4_ACCEPTANCE.md、docs/G4_G5_HANDOFF.md、docs/G4_BETA_USER_GUIDE.md、audit/G4_RELEASE_MANIFEST.json；真实用户研究和算法收益留给后续阶段，不得夸大。
8. 独立输出 g4_development、g4_beta_utility、g4_research_optional 三类状态；每个 H00–H12 门槛带路径、工件和失败原因，不能随意将未运行标记 PASS。

结束后停止，等待独立总审查与项目所有者对 G4 Beta 的批准。不得自动推送/部署到公网，不提交敏感文件或 dev-diaries/。
```

### 7.2 独立只读审查提示词

```text
请只读审查 CFAW News G4-PR6 的最终验收，不修改任何文件。

检查 PR6 diff、真实浏览器脚本和执行记录、JUnit、完整命令/退出码、G4_ACCEPTANCE.md、G4_G5_HANDOFF.md、G4_BETA_USER_GUIDE.md、release manifest、数据来源/rights、G1/G2/G3 相容性 pins。

重点核查：
1. 验收是否绑定当前真实提交/代码/数据，还是旧日志或旧工作树；
2. Playwright 是否实际跑过关键用户路径而非只有组件快照；
3. source/rights、time/版本、evidence/hold、history/feedback、cancel/idempotency/DB head 各门槛是否有证据；
4. 真实文章是否确实合规，是否把 synthetic fixture 作为用户真实价值证明；
5. 180/420/900、覆盖缺口、unmet protected 和历史版本是否被正确展示；
6. G3 `g3-grounded-fact-signature-v2` 策略和 B4 默认是否保持，P1 是否被未经证据推广；
7. 真实网络测试若未获授权/未运行，是否如实写 not_evaluated；
8. 完整测试、前端 build、浏览器回归、G3 注册测试控制面的结果是否可验证；
9. 旧 Goal/Run/Decision/Schedule 是否没有退化；
10. 报告中各分子/分母、环境与失败日志是否真实，是否有选择性隐藏失败；
11. 工程验收、beta utility 与真实用户研究是否清楚分离；
12. 是否存在未关闭 P0/P1、隐私泄露、站外推送或未经批准 Git 写操作。

输出逐 finding P0/P1/P2/P3、路径/行号、复现证据、影响、修复建议，并分别判断工程可接受性、Beta 是否可诚实试用、是否具备 G5 规划前置条件。未实际重跑的部分明确写“静态审阅/未复现”。
```

---

## 8. 通用审查问题修复提示词（PR1～PR6 通用）

```text
现在仅修复 G4-PR<N> 审查报告里的问题。不要开始下一个 PR，不扩展功能。

先逐条复核审查发现是否仍成立：每项输出 finding ID、代码位置、是否成立和证据。对成立问题做最小修复并增加反例回归；不成立时用原始代码/测试证据说明，不可为了清空审查报告盲目改代码。

以下做法禁止：
- 修改 G1/G2/G3 frozen data、Gold、旧验收结果或旧 pin 来消灭失败；
- 降低证据门禁、把 hold 当 focus、把 synthetic 伪装真实；
- 放宽取消/未来时间/历史身份/事务安全断言；
- 擅自写 GitHub PR、commit/push/merge 或安装付费/网络模型；
- 触碰/上传 dev-diaries、密钥或真实用户数据库。

修复后重跑受影响测试及必要回归，记录 argv、exit code、日志与 SHA。输出逐 finding 关闭表（原问题、修复、测试、状态、残余风险）和新 diff；然后停止，等待新会话独立复审。
```

---

## 9. 通用复审提示词（PR1～PR6 通用）

```text
你是 G4-PR<N> 的独立只读复审 Agent。请在新会话中检查最新 HEAD、审查 finding、修复 diff、每条关闭证据与实际测试日志。不要修改文件。

对上一轮每条 finding，判定 CLOSED / OPEN / NOT_REPRODUCIBLE / DEFERRED。只有在代码、反例测试或完整约束解释支持时才能关闭；不能仅凭 Codex 说已修复就关闭。

重新关注受修复影响的来源权利/时间/事件身份/证据等级/DB 事务/回访语义/浏览器关键路径，防止修复引入侧面退化。再次检查是否触碰 G1/G2/G3 冻结资产、用户数据、密钥或 dev-diaries。

输出新发现、未关闭 P0/P1、复审判定 PASS/BLOCKED、P2/P3 风险和是否建议所有者批准进入下一 PR。AI 复审不是独立真人验证。
```

---

## 10. G4 最终总审查提示词（在 PR6 后运行）

```text
你是 CFAW News G4 的最终只读集成审查 Agent。不要修改文件、commit、push 或部署。

以 AGENTS.md、docs/CFAW_News_V1.md、docs/G3_G4_HANDOFF.md、docs/plans/G4_IMPLEMENTATION_PLAN.md 为规范，审阅 G4-PR1～PR6 最终 diff、所有实现/独立审查/修复/复审/所有者批准记录，真实后端/前端/E2E 测试、G1/G2/G3 frozen pins、G4 runtime source registry、migration、API、UI、历史日志、release manifests。

必须独立逐项回答：
A. G3 最终阻断问题和 G4 开工授权是否可追溯；
B. 真实 RSS→immutable evidence→native G2→G3→B4→BriefingPlan 的正式路径是否可信；
C. 当前生产候选没有足够证据时，是否能诚实降级而非显示假推荐；
D. 历史 as_of、rights、provenance、claim/引用、事实签名 v2 是否保持；
E. G4 的本地 SQLite append-only/atomic release/trusted head、取消/幂等/恢复是否有真实证据；
F. included/rendered/opened/ack/dismiss/retract 是否由正确动作触发，用户不打开时是否不会外部推送；
G. Focus/Radar/Archive、证据详情、阅读估时、来源缺口、unmet protected 与错误状态是否可实际使用；
H. 旧新闻资料库、目标、检查、决定与日程是否无意外退化；
I. Playwright、Ruff、全量 pytest、G3 注册控制面、前端构建及本地恢复是否有真实 argv/exit/JUnit/日志和 hashes；
J. 是否仍存在 P0/P1，或不可复现/未经授权的修改；
K. 能否分别宣布 g4_development、g4_beta_utility、g4_research_optional 的确切状态；
L. 是否建议进入 G5 规划，以及哪一项真实来源/用户有效性仍需研究。

所有结论必须有代码路径/行号、复现命令、测试节点或 manifest pin。要区分历史报告、当前静态审查与当前实际运行证据。不得将 AI 自审称为真人研究，也不得根据合成测试推断真实用户效益。输出最终 PASS/FAIL/BLOCKED、门槛矩阵、失败案例、未验证项、残余风险及建议。
```

---

## 11. 审查分级、暂停与管理员决策模板

### 11.1 Findings 等级

- **P0**：源内容/许可严重违法规或严重失实、Gold/未来泄漏、关键用户数据损坏/秘密泄露、未经批准外部推送或破坏性 Git 行为；必须阻断。
- **P1**：不能保证引用/时间/身份/权利/hold、取消后迟到发布、日志 head 不可信、生产 DB 非原子、首页主要操作无法使用；必须阻断。
- **P2**：非核心解释不足、个别低风险 UI/测试缺口，需记录后续处置。
- **P3**：美观和非核心工程改良，可进 backlog。

P0/P1 未关闭不得建议开始依赖它的下一 PR。P2/P3 可以延期，但要说明影响与所有者接受情况。

### 11.2 统一 PR 报告框架

```markdown
# G4-PR<N> 交付/审查报告
- 日期/时区、branch、HEAD、worktree、PR 范围
- 上游报告/pins 与所有者授权
- 改动文件与原因（含 DB/API/Schema 版本）
- 主要安全不变量及正反测试
- 命令、cwd、argv、exit、测试通过/失败/跳过、日志/pins
- 受控真实材料与 synthetic provenance 分开
- P0/P1/P2/P3 finding 与关闭情况
- 尚未运行/尚未授权的检查
- 回滚方案、已知限制与下一步
- 明确：PASS / FAIL / BLOCKED，以及是否建议进入下一 PR
```

### 11.3 项目所有者的最小审批话术

- 同意进入下一 PR：`我已阅读 G4-PR<N> 的实现和审查/复审报告，批准进入 G4-PR<N+1>；仅限计划书规定的本 PR 范围，不授权额外外网调用、付费 API、数据库破坏性操作或自动 Git 写入。`
- 有问题退回：`暂不接受 G4-PR<N>，请先依据审查 findings 修复并复审，不开始下一 PR。`
- 接受有记录的低风险风险：`我接受 PR<N> 报告中的 P2/P3 作为非阻塞项，但 P0/P1 必须关闭；请记录延期归属，不扩展本 PR。`

**你只做产品和边界裁决；开发测试与 AI 辅助审查交给 Codex。**
