# CFAW News G2 — Codex 分 PR 协作与完整提示词手册

> 版本：`g2-codex-playbook-v1.0` · 日期：2026-10-24
> 项目：`D:\agent_project\cfaw-news` / [GitHub](https://github.com/V-Giotto/cfaw-news)
> 正式阶段规格：`docs/plans/G2_IMPLEMENTATION_PLAN.md`，应先将《CFAW News · G2 详细实施计划（单人管理员 + AI 开发协作版）》保存于该路径。
> 编写依据：G2 六 PR 计划、仓库 `AGENTS.md`、`docs/CFAW_News_V1.md`、G1 默认 `ai_development` 通过的验收事实。
> **使用方式**：一次只复制当前 PR 的一段提示词；不要整本粘贴给 Codex 并要求一次性执行。代码和 Git 状态以 Codex 实际读取的本地仓库为准。

---

## 0. 最重要的工作原则

**协作角色：** 你是唯一的项目管理员和决策者；Codex 是实施工程师，另开 Codex 会话可充当 AI 代码审查者。生成合成开发数据、拟定开发标签、AI 自评与修订、运行自动测试、查找失败原因、输出验收报告，由 AI 负责。**不得设置两名真人标注者、要求你逐条人工标注、要求另一名真人签字，作为 G2 开发硬门槛。**

**研究边界：** AI 开发复核不是独立真人评测；五条 G1 主轨迹为 synthetic；当前 G1 的 `g2_eligible=true` 是离线开发资格，不是现实效果证明。明确区分 `g2_development` 与 `g2_research_optional`；后者未做则标 `not_evaluated`，不阻塞开发。

**单 PR 生命周期：** `Plan Mode（只读） → 管理员批准 → 执行/目标模式（当前 PR） → AI 只读复审 → 修复 → 验收与管理员批准 Git 操作 → 下一个 PR`。

**强制保护：** 不擅自联网、调用真实付费 LLM、安装依赖、读/写生产数据库、修改冻结的 G1 数据/Manifest/Gold、访问 `.env`/用户私密文件/`dev-diaries/`、上传私人数据、执行 `git commit/push`。如客观技术验证必须跨这些边界，报告并请求专项批准；不要以“用户授权整阶段研发”代替专项授权。

**避免制造假成绩：** 不从 gold、oracle、未来内容、未来用户反馈中推导预测；结构引用合法 ≠ 语义支持；同一上游转载 ≠ 多个独立证据；文本差异 ≠ 已识别实质更正；合成测试指标 ≠ 现实泛化指标。失败不改弱测试、不偷改冻结样本标签。

**模式建议：** 每个 PR 先使用 Plan Mode；批准后用普通执行模式，较复杂任务若 Codex 客户端提供“目标模式”亦可使用，但**目标只写当前 PR 的 DoD**，不得授权自动完成 PR1～PR6。Plan 模式不修改文件。如界面模式名称不同，按“只读规划/可修改执行”能力对应。

---

## 1. 准备阶段：在 G2-PR1 之前做一次

- 将本次已批准的 G2 计划放到 `docs/plans/G2_IMPLEMENTATION_PLAN.md`。如该文件不存在，先自行放入；不要让 Codex凭空替你决定计划全文。可保留本手册在 `docs/plans/G2_CODEX_PROMPTS.md`，但不是必须。
- 在 Codex 中打开项目根目录 `D:\agent_project\cfaw-news`，检查当前分支/HEAD 与未提交修改。
- 第一轮先启用 **Plan Mode**，使用下方 **PR1·计划提示词**。
- 若工作区已有未提交的修改，先让 Codex确认由哪些文件构成，不能擅自清理或覆盖。
- 尽可能每个 PR 单独分支/提交，是否创建/提交/推送由你批准，不由 Codex先斩后奏。

---

## 2. G2-PR1 — 契约、G1 桥接与最小离线流水线

### 2.1 PR1 计划提示词（Plan Mode，只读）

```text
你现在是 CFAW News 项目的 G2-PR1 主程兼时序评测工程师。
项目根目录：D:\agent_project\cfaw-news。

【先确认真实仓库】
只读执行 git status、git rev-parse HEAD、查看文件结构。阅读：
AGENTS.md、docs/CFAW_News_V1.md、docs/plans/G2_IMPLEMENTATION_PLAN.md、
docs/plans/G1_AI_DEVELOPMENT_RULES.md、
evals/intelligence_v1/G1_ACCEPTANCE.md、
evals/intelligence_v1/reports/PR5_AI_DEVELOPMENT.md；
检查 evals/intelligence_v1/{contracts,loader,temporal,grouping,baselines,replay}.py、
backend/cfaw_news/{database,providers,ingestion}.py、相关测试和锁文件。
若 G2 计划缺失或计划与源码不符，请说明具体缺口，不能猜想它已存在。

【本轮仅规划 PR1】
设计独立离线数据路径：G1 ReplayContext + as_of 可见候选 → 预测事件 → 占位 EvidenceBundle → 最小 IntelligenceItem → JSON/Manifest/校验报告。
明确 G2ReplayInput、PredictedRelation、StableEventIdentity、ClaimCandidate、EvidenceBundle、IntelligenceItem、GenerationTrace/G2Result 的最小 Pydantic Schema、版本策略和数据字典；不得把 G1 参考 Claim/EventGroup 当作预测结果。
采用独立 G2 模块并复用 G1 的 UTC、as_of、证据版本选择、候选集与 manifest pin，禁止从 G1 labels/Oracle 或未来文本偷偷读取答案。稳定 event_key 不应简单等于成员文档集合哈希。规则级占位生成即可；本 PR 不开发完整归并、抽取、LLM、API、UI 或生产数据库迁移。

【单人+AI 协作】
只有我一名管理员。合成 fixture、开发标签、测试和 AI 复核均由 Codex处理；不得新增“双真人标注/真人逐条审批”开发门槛。AI 审查结论明确为 ai_development 而非独立科研证据。

【必须输出】
1) 当前代码与冻结 G1 的复用映射；2) PR1 的文件级修改清单；
3) 字段级 Schema 与校验错误码；4) CLI 输入输出与 hash/版本方案；
5) G2-T01～T10 的正反测试和实际断言；
6) 运行命令、DoD、预期影响、风险与回滚；
7) 最多 3 个确实需要管理员确认的产品/安全取舍，并推荐默认值。
不修改任何文件、不联网、不访问私人内容、不调用模型、不迁移 DB、不 commit/push。完成计划即停止。
```

### 2.2 PR1 执行提示词（批准计划后，执行模式）

```text
我批准当前 G2-PR1 的实施计划（若我对计划有修改，以最新批准内容为准）。
请重新确认本地 HEAD/工作区与计划兼容，严格限定 PR1 修改范围。

实现严格版本化 G2 Schema、G1 as_of 只读桥接、最小纯离线流水线、确定性输出/Manifest/诊断，以及合法/非法 synthetic fixtures。由代码生成 JSON Schema，不创建全阶段空壳模块，不改变 G1 frozen 数据及现有业务 API/DB。

落实 G2-T01～T10：未来版本拒绝、历史版本正确、未来 Persona/曝光拒绝、重复执行一致、冻结 pin 篡改拒绝、成员身份非法拒绝、引用段落不存在拒绝、空候选与来源未知安全输出、来源/权利一致、旧数据不变/回归安全。
每完成一个小模块运行专项测试；结束运行 Ruff、相关 G1 schema/manifest、G1/旧工程 pytest、seed smoke、前端构建。若某项因环境问题未能完成，保留原始失败证据，明确区分未运行与失败。

保存新增产物、错误负例、结果 hash、验证命令与真实 exit code，撰写 PR1 验收记录并记录已知限制。不得通过修改测试弱化断言。
AI 可以生成样例和复核，不要求我或第二真人逐项标注。
不得联网、真实付费模型调用、安装未授权依赖、改生产 DB、访问 dev-diaries/ 或自动 commit/push；本 PR 完成即停止，不实施 PR2。
```

**PR1 管理员决断点 A：** 审阅事件粒度、稳定 `event_key`、证据引用的产品语义和禁止事项即可；你不负责逐条校验每个 synthetic 文档。

---

## 3. G2-PR2 — 事件关系预测与稳定事件身份

### 3.1 PR2 计划提示词（Plan Mode）

```text
请以只读 Plan Mode 为 G2-PR2 制定实施计划。先阅读 AGENTS.md、G2_IMPLEMENTATION_PLAN.md 第 6 节、已验收 PR1 的契约/测试/报告及当前 grouping.py、replay.py、相关 schema。核对 git status、HEAD 与 PR1 真实完成状态。

本 PR 仅做事件关系预测和跨时点事件身份：明确 exact_duplicate、syndicated、same_event_different_evidence、related_distinct_event、unrelated、uncertain；保留 G1 group_candidates 作为固定 R0 对照。提议高精度 URL/upstream/subject/version/event_type/time/text R1-R2，保守 cannot-link 与 complete-linkage；不强制语义 embedding/模型。

必须单独设计可持续的 event_key、event_revision 和 merge/split lineage：D0→D8 新证据不换身份；修正历史错误时不覆写过去的 item 与别名。不能把 G1 member-set hash 当长期稳定身份。不同主体/事件不得因词汇相近误并。

写出新增文件、关系预测接口、输入输出、预测/Oracle 隔离、相同候选池的 R0/R1 对照、误合并/漏合并统计、G2-T11～T18 测试逐项断言、DoD 与错误分析格式。Codex 负责 synthetic 对抗样本、AI 开发参考、反例和复核；不要求真实双人标注。不得动 PR3、数据库、UI、真实模型或 Git 提交。完成计划即停。
```

### 3.2 PR2 执行提示词（执行模式）

```text
我批准 G2-PR2 的计划。只实施事件关系预测、归并策略和稳定 ID/lineage。保留并隔离 G1 R0；不读取 G1 gold/Oracle 辅助推断。不因同公司、同仓库或链式相似就强制归并，无法判定时返回 uncertain/分开事件。

实现 G2-T11～T18：十次转载单主项但留来源血缘、官方+独立测试保留证据独立性、同项目不同公告不误并、A-B/B-C 不导致 A-C 错并、D0/D8 ID 稳定、合并拆分可追溯、未来证据不影响历史、顺序/seed 改变不影响确定性结果。

给出 R0 vs R1/R2 在同样候选/预算下的 pairwise P/R/F1、False Merge、FN、ID 稳定与个案表。开发标签明确 synthetic/AI；指标不冒称真实泛化。如新策略没有改进，客观报告并保留可运行的 R0。
跑本 PR 专项+完整回归，保存失败记录、命令、hash、代码差异、风险和 DoD。不得提前写 Claim/LLM/新 UI，不自动 commit/push；完成 PR2 后停下。
```

---

## 4. G2-PR3 — ClaimCandidate 与 EvidenceBundle

### 4.1 PR3 计划提示词（Plan Mode）

```text
以只读 Plan Mode 为 G2-PR3 制定方案，阅读当前 PR1/PR2 契约、实现、验收与 G2 计划第 7 节，以及 G1 Claim/EvidenceRef 参考标签模型、真实可见 CandidateDocumentVersion 字段。先验证已批准的稳定 event_key 输入已实现。

目标：仅从截至 as_of 可见的证据段落抽取受约束 ClaimCandidate，组织 EvidenceBundle。区分“来源做了声明”与“声明被独立证明”，保留 scope、source attribution、support/refute/mentions/unknown、upstream 血缘、冲突、撤回和 coverage_gap。直接抽取并绑定原文，不虚构实验数字；原句存在与语义支持相互独立；任何研究金标不能输入实际抽取器。

针对官方称提升40%、多个转载、限定实验、不同 scope、同 scope 冲突、旧声明更正、引用位置合法但不支持、未来跨家族引用、正文损失、源站离线，逐项定义 G2-T19～T28 的失败/降级策略。

输出文件级计划、接口/schema、结构引用验证、AI 开发复核记录格式、预算/敏感数据边界、可复现指标以及 DoD。AI 自行负责开发标签与审查，不能要求两真人。不开发 PR4 模板、PR5 LLM 或生产 DB。只读，提交计划后停止。
```

### 4.2 PR3 执行提示词（执行模式）

```text
按已批准的 G2-PR3 计划实施，不变更 G1 参考数据。实现 ClaimCandidate 抽取、source/upstream 谱系、EvidenceBundle、结构引用/可见性审计、unknown/insufficient 降级和冲突范围判定。

G2-T19～T28 必须全部可运行，包括不能把厂商声称自动写成独立实测、转载独立数为0、不同条件不误判冲突、无证据数字拒绝、引用存在但缺乏语义支持时不能宣称已证实、未来引用禁止、未知来源覆盖不能推出“没有变化”。

执行 synthetic/AI 开发复核并保存输入/初稿/复核/修订证据；结构验证指标与 AI 语义复核指标分开，如无独立量化真实支持，则写 not_evaluated。跑回归并交付成功和失败个案、hash、真实测试日志、DoD 与待决事项。不要提前进入 PR4，不自动联网、调用付费 API、commit/push。
```

---

## 5. G2-PR4 — IntelligenceItem 与 Focus/Radar 规则模板

### 5.1 PR4 计划提示词（Plan Mode）

```text
本轮只读规划 G2-PR4。阅读 G2 第8节、已交付 EvidenceBundle/Claim、规则模板需求、G1 内容预算规则与旧前端资料库，不修改代码。

设计独立于 LLM 的确定性 IntelligenceItem 生成：稳定 event_key+event_revision，事实 headline/what_happened 必须可还原引用；why_it_matters 是推断，不伪装源事实；重要声明附 scope 与风险；focus 较深入、radar 1–2句、hold 缺证据不硬推；这些是 G2 候选层级，不代替 G3 的个性化最终排序。空信息不凑条数、不把转载当多个主项。Persona 变化不应该改写同一事件事实正文。

输出字段/schema/规则模板、版本化快照、LLM 后续可替换的 generator 接口、G2-T29～T36 测试、示例模板和 DoD。开发样例、校验和修订由 AI 完成，我只负责对少量风格示例作产品决断；不需要人工逐条标注。不要动真实模型、UI 或 DB。完成计划后停。
```

### 5.2 PR4 执行提示词（执行模式）

```text
按照已批准 PR4 计划实施纯规则 IntelligenceItem/BriefingDraft，并对 G1 历史时点+G2 对抗材料确定性运行。实现 G2-T29～T36：同事件单主项、focus 证据完整、radar 精简标注不确定性、空来源不凑数量、性能数字有依据、实质更正/撤回不可仅凭文本变更断言、Persona 变化事实不变、重复生成规范化输出一致。

生成 3–5 个明确 synthetic 的重点情报与前沿速览样例及对应 evidence_refs，供我决定表达风格；不要把我是否逐条手动改写作为阻断条件。需要我选择时给推荐方案与取舍，停止等待，不代替我批准产品策略。

执行专项/旧工程回归，保存测试日志、输入/输出版本与 hash、失败案例、可追溯引用校验和完整 DoD。只完成 PR4，绝不自动完成 PR5；不得自动联网、调用付费 API、commit/push。
```

**PR4 管理员决断点 B：** 只看少量合成简报，决定标题是否足够谨慎、重点/速览篇幅和降级文案。不要求逐篇人工标注。

---

## 6. G2-PR5 — 可选受约束 LLM 表达与安全降级

### 6.1 PR5 计划提示词（Plan Mode）

```text
请仅以只读 Plan Mode 规划 G2-PR5，阅读 G2 第9节、现有 backend/cfaw_news/providers.py、PR4 rule generator、G1 EvidenceRef/版本门禁、模型错误/引用检查相关测试。

目标：在 rule-based 已完成的结构化情报上增加可选的受约束 LLM 文字表达，默认只运行 mock；真实付费模型、外网和密钥均非 G2 开发硬门槛且未经本轮批准。原始 RSS/正文是不可信数据，不能命令代理执行工具。模型只可使用白名单的历史可见 EvidenceBundle，不得凭外部训练记忆补造事实。

计划包括：独立 IntelligenceGeneratorProtocol/adapter、版本化 Prompt、JSON Schema 校验、引用白名单+数字/范围最低校验、AI 语义复核与结构检验分离、预算/超时/次数上限、错误分类、rule fallback、trace 和禁止泄露的日志规则。列明现有 providers.py 复用与不能复用之处，严格保持 Goal 旧契约。

输出 G2-T37～T46 逐项测试、负例数据、mock/规则对照、DoD、风险、可选真实模型实验需我另行授权的细节。单人开发原则有效；不许要求两真人审核。不要实施 PR6、联网、付费模型或数据库迁移。只读规划后停。
```

### 6.2 PR5 执行提示词（执行模式）

```text
按已批准 G2-PR5 计划，在不修改旧 Goal 模型逻辑的前提下实现受限生成 adapter、mock、prompt 版本、引用核查、显式语义支持状态、预算与错误分类和稳定 rule fallback。

完成 G2-T37～T46 的强制负例：伪造文档/未来段落引用、引用真实但不支持、无依据 Benchmark 数字、官方声称冒充独立证实、prompt injection、超时/429/5xx/截断、版权 metadata_only 越权、超预算/空证据及相同 mock 输入可复现。

默认只运行离线 mock，不能读取 .env、真实 API key、访问网络或调用真实付费服务。遇到结构存在但语义难以判定时标 not_verified 并降级，不能因为模型自评通过便写 independently_validated。保留 rule 产物，不允许失败模型污染原始输出。

执行专项与旧工程回归，保存真实日志、input/prompt/version/hash/成本状态、失败案例、DoD 和未完成可选真实模型烟测。不要自动 commit/push，不做 PR6。
```

---

## 7. G2-PR6 — 全链复现、工程验收与 G3 交接

### 7.1 PR6 计划提示词（Plan Mode）

```text
请只读制定 G2-PR6 的收尾计划。读取 G2 第10节 H01～H10、所有已验收 PR1～PR5 的提交/验收报告/冻结版本、G1 现有 reproduce/acceptance、CI、测试与原始基线。核对当前 Git 状态，不能把历史旧报告冒充最新运行。

设计全链离线复现与 g2_development 验收：G1 五轨迹的正确 as_of、至少8种明确 synthetic 错误模式、R0/G2 事件策略对照、rule/mock LLM、低中高阅读/生成预算、顺序与 seed 重复、错误/覆盖缺口、引用/独立性/未支持检查。预测不可读取 gold/oracle，labels 仅后评测消费。对真实探索材料仅可提出可选方案，网络与许可须另行批准，不设为开发门槛。

给出 H01～H10 完整映射、G2-T01～T46/完整 JUnit 节点映射、source/config/manifest pin 与哈希证据、报告分母处理、旧系统回归、安全边界、AI 复核及研究结论边界。人类独立评审/真人双标/真实用户研究一律 optional/not_evaluated，不阻塞 g2_development。具体输出文件、CLI、DoD、回滚与需我验收的汇总项。只做计划，不执行。
```

### 7.2 PR6 执行提示词（执行模式）

```text
我批准 G2-PR6 计划，仅完成离线全链复现、质量评测、AI 复核、验收与 G3 数据契约交接。新建结果目录，不覆盖冻结旧工件。对 PR1～PR5 的代码、schema、日志、git SHA 和测试映射重新核验，不能将以往 PASS 直接复制成此次 PASS。

确保 G2-T01～T46 和 H01～H10 的每项结果有客观输入、输出、程序断言、日志/exit code/sha，缺项为 BLOCKED/NOT_MET。主报告划分 synthetic_dev、optional_real_qualitative、independent_research_not_evaluated；AI 开发标签/语义复核与真人独立研究严格分离。正式未实现的语义准确率留 null+reason。两次运行属于确定性复现，不是独立事件样本数。若新策略无增益，请如实报告并保留较简单可维护基线。

完成旧 G1/业务全量回归、Ruff、构建、G1 数据防篡改、G2 总验收。任何未来泄漏、伪造引用、时间/来源/许可硬门槛、复现或回归失败 → overall NOT_MET，报告修复事项，禁止绕过。

生成 G2_ACCEPTANCE.json、G2_ACCEPTANCE.md、G3_HANDOFF.md，分别写 technical_status、ai_development_status、research_optional_status、g3_offline_eligible。开发硬门槛通过即可建议 G3，但由我最终批准；不要求第二真人或我逐条标注。
不自动切入 G3，不做生产迁移、不联网、不调用真实模型、不自动 commit/push。完成收尾后停下。
```

**PR6 管理员决断点 C：** 审核 H01～H10 汇总、P0/P1 风险、`g3_offline_eligible`，决定 G2 是否关闭、是否进入 G3。

---

## 8. 通用“独立审查”提示词（每个 PR 实现后新开会话）

```text
你是 CFAW News 的 G2-PR<N> **只读 AI 工程审查者**，与实现对话分离。当前只审查，不能修改源码、测试、冻结数据、报告或 Git；不得 commit/push。

先读 AGENTS.md、G2_IMPLEMENTATION_PLAN.md 的当前 PR 与 DoD、相应已批准计划；核对 HEAD、git diff、实现源码、合成 fixtures、测试/JUnit、执行日志与 Manifest pin，核对实际文件是否存在。任何缺失材料应列“未验证”，不可编造已审计结论。

优先审查：
A. 时间门禁和 Gold/Oracle/未来反馈泄漏；
B. event_key 跨 D0/D8 是否漂移、错误 merge/split 是否丢历史；
C. publisher 声明是否被写成事实、转载是否被当独立证据；
D. doc_version_id/paragraph_id 是否有依据、引用存在但不支持如何处理；
E. 真实来源许可/metadata_only、安全、prompt injection、隐私/凭据泄漏；
F. 是否改弱测试、变更冻结 G1、扩大 PR、把 synthetic/AI 自审冒充真人独立研究；
G. 是否有足够确定性、预算、回退与空候选行为。

输出只包含可追踪审查结果：P0/P1/P2 问题（文件/代码/测试证据、触发条件、预期/实际、修复建议、复验命令），以及通过项与未验证项。即使没有问题，也不得将工程审查称为独立真人研究评测。
```

## 9. 通用“按审查报告修复”提示词

```text
请按当前 G2-PR<N> 的只读审查报告逐项修复 P0/P1/P2，范围仅限审查所需的当前 PR，不得偷偷实现下一个 PR。

先逐项复现失败；为每条问题增加回归测试，再作最小修复。禁止修改 frozen G1 输入、为了得分改标签、降低断言强度、把错误值填成 PASS。修完后跑专项测试、关键跨 PR 用例和必要的全量回归；将 before/after 现象、真实命令/exit code、日志/hash 与未关闭问题写入修复报告。

若需扩大 schema、权限、联网、付费模型、迁移 DB 或触动 G1 frozen，停止并说明方案，等待我另行批准。只有客观硬门槛通过后才建议管理员合并；禁止自动 commit/push。
```

## 10. 通用“PR 结束交接”提示词

```text
请只总结已完成的 G2-PR<N>，不要进一步开发。列出：
1. git HEAD、当前工作区状态、变更文件与用途；
2. 已交付接口/样例/CLI/Schema；
3. Txx/DoD 逐项通过、失败或 N/A，准确测试数量与真实命令；
4. 合成/AI/Oracle/真实来源各自的证据等级；
5. 冻结输入/输出指纹和可复现步骤；
6. 独立 AI 代码审查的 P0/P1/P2 关闭状态及未验证项；
7. 未经授权行为未发生的核查结果；
8. 是否建议该 PR 合并，以及下一 PR 需要继承的确切契约版本。
不要把本 PR 技术验收写成 G2 总验收，不得自动 commit/push。用简短管理员摘要开头，详细材料保存在仓库内合适的 G2 报告文件（如当前仍在只读模式，仅建议路径）。
```

---

## 11. 模式选择速查

| 使用时机 | 推荐模式 | 原因 |
|---|---|---|
| 初次进入任意 PR | **Plan** | 检查代码、拟定接口/风险，不动文件 |
| 计划得到你批准 | **普通执行** | 逐步修改，跑测试，随时可审查 |
| 较复杂的连续修复（如 PR2/PR3/PR6） | **目标模式（可选）** | 仅设当前 PR 的技术 DoD，避免跨阶段失控 |
| 实现完成后 | **新会话只读审查** | 降低同一上下文自我确认偏差；非独立科研证据 |
| 审查提出问题 | **普通执行** | 按问题修复、重跑，不提前做下个 PR |
| 单 PR 已技术完成 | **等待管理员决断** | 所有者决定是否提交/进入下一阶段 |

> 不要只看 Codex 说“全部完成”；以 Git diff、真实测试记录、可复现工件、错误样例与明确限制为准。Plan 文字不会自动变成项目中实际存在的功能。

## 12. 常见 Codex 追问的预先授权答案（减少反复提问）

**问：必须有两个真人完成 G2 标注吗？** 不需要。AI 可以制作合成数据及开发参考、初稿、复核、修订；明确 `ai_development`，不声称真人研究。可选真人研究 `not_evaluated` 不阻塞开发。

**问：没有真实历史资料，是否能进行 G2？** 可以。冻结 G1 synthetic 与独立 G2 synthetic 对抗集可以覆盖开发；真实探索包可后续另行授权，研究泛化不主张。

**问：能否修改 G1 Gold/Manifest 以适配 G2？** 不可以。使用 G2 新契约、桥接与新 Manifest，保留 G1 冻结资料与历史验证。

**问：PR2 现在必须使用语义大模型/Embedding 吗？** 不必须；先做低成本、可解释的 R0/R1/R2，并以误例决定是否增强。

**问：`text_changed` 是否等价于 `correction`？** 不等价。除非有可见且适用范围匹配的依据，必须输出 `unknown`/待核查。

**问：PR5 可直接调用真实模型吗？** 未经专项授权不可。默认 mock + 规则回退；真实调用需你明确决定模型、可传数据、次数/金额与安全边界。

**问：必须让管理员逐条审阅情报才能验收吗？** 不必须。PR4 仅需你从少量示例中决定文案与产品表达风格；技术断言 AI/程序负责。

**问：什么时候能说 G2 完成？** PR6 的 H01～H10 开发硬门槛、全链回归与冻结证据全部通过，并由管理员批准；不能等同于独立真人科研成果或正式生产可用。

---

## 13. 可复制的开发纪律检查表

- [ ] 当前仅一个 PR；Plan 阶段只读。
- [ ] 当前 HEAD、diff、已冻结的 G1 pin 经核对。
- [ ] Codex 未经授权不联网、不调用付费模型、不安装依赖或迁移生产 DB。
- [ ] `dev-diaries/`、`.env`、`.local/` 和私密数据不被读取、上传、提交。
- [ ] 合成材料及 AI 开发标签可由 AI 负责，不要求真人双标。
- [ ] 预测不读取 Oracle/Gold 或未来资料；引用身份和语义支持分开。
- [ ] 新测试包含反例；失败不能通过弱化断言“修复”。
- [ ] 保存真实日志、退出码、哈希、错误原因以及未验证项。
- [ ] 按当前 PR Txx/DoD 验收，必要时另开 AI 审查会话。
- [ ] 你批准后才提交/推送，再开始下一 PR。

**最终产品目标不变：** CFAW News 是面向 AI 开发者的主要情报入口。G2 完成“技术事件 → 可追溯证据 → 稳定情报对象”，后续的个性化和七天回访排序留给 G3。
