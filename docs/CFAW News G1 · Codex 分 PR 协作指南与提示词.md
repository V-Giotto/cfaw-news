# CFAW News — G1 × Codex 分 PR 协作指南与提示词

> **2026-10-23 修订**：本指南的 DEV-01～05 提示词默认允许 AI 完成。当前验收按 [AI 开发与验收规则](plans/G1_AI_DEVELOPMENT_RULES.md)；旧真人限定仅用于可选真人研究路径。

> 版本：1.0 · 2026-10-20  
> 对象：CFAW News 独立开发者，以 Codex 本地仓库工作方式执行 G1-PR1～PR5  
> 依据：`docs/CFAW_News_V1.md`、`docs/plans/G1_IMPLEMENTATION_PLAN.md`、`audit/G0_REUSE_AUDIT.md`、`audit/G0_BASELINE.json` 和仓库实际 `AGENTS.md`  
> 注意：本文件提供给 Codex 的**操作指令模板**；并不代表代码、数据、指标或验收已完成。仓库中的实际文件和已运行证据优先于本模板。

## 1. 一句话原则

**一次只执行一个 PR；先只读计划、再明确批准执行、再真实测试、再独立审查、再由人决定提交或合并。** 不让 Codex 在一个长目标下自行跨越 PR1～PR5 的审批边界。

G1 的最终价值在于“历史可见、独立离线、可复现、公平对照的时序情报评测”，**不**是新的 UI、在线 Agent、生产库迁移或让 B4 指标强行优于 BM25。

## 2. 模式选择

| 任务                          | 推荐                   | 原因和边界                                         |
| --------------------------- | -------------------- | --------------------------------------------- |
| 分析 G1-PRx、检查代码和写实施计划        | **Plan Mode**        | 修改源码之前先确认范围、契约、测试与风险。此轮要求只读，不允许落地实现。          |
| 已确认计划、执行一次范围明确的 PR          | **普通执行对话**           | 一个工作包结束就停，由人验收后再继续。                           |
| PR3/PR4 遇到反复回归、失败重试、基线一致性问题 | **Goal Mode（可选）**    | 仅设置当前 PR 的持久完成条件与阻断条件，完成后停止；不要设置整个 G1 的 Goal。 |
| 代码质量或安全审查                   | **独立新对话，先只读 review** | 减少实现者自评偏差，优先报告问题而非继续实现。                       |
| PR5 真实第二人标注/仲裁              | **人类标注环节**           | Codex 可以生成工具或统计报告，但不得冒充第二个人。                  |

Codex CLI 的 Goal 功能（客户端支持时）可以使用 `/goal …`；先运行 `codex --version` 确认版本和能力。`/goal pause`、`/goal resume`、`/goal clear` 为相关生命周期命令。UI/IDE/CLI 的可用选项可能不同，以已安装客户端为准。Plan 和 Goal 的语义不是简单互斥：Plan 管路径，Goal 管持续目标。

### 推荐对话节奏

1. **对话 A：Plan**。请 Codex 只读项目和 G1 文档，输出范围、设计、测试和风险，**不修改文件**。
2. **人类审批**。核对是否超范围、是否动生产库、是否错误使用金标、是否把可用时间等同发表时间。
3. **对话 B：执行**。把已批准计划作为输入，让 Codex 仅做当前 PR，运行新旧测试，最后暂停。
4. **对话 C：Review（新对话）**。只读当前 diff、对应测试和失败记录，按严重程度给问题清单。
5. **必要时对话 D：修复**。只修审查指出的问题，重跑针对性测试与回归；重新审查。
6. **人类验收和 Git 检查点**。自行确认、允许 Codex 做局部提交，或由自己提交；**不要自动 push/merge**。随后再开启下一个 PR。

PR1~PR5 的顺序应遵守阶段依赖。这里的“PR”既可是真正的 GitHub Pull Request，也可是在本地顺序完成的审查里程碑；若采用真实 PR，建议每个 PR 单独分支，合并通过后再从最新主分支创建下一个。

## 3. 开始前的本地准备

1. **从项目根目录打开 Codex**：`D:\agent_project\cfaw-news`，确认是在你的本机仓库而非错误的空目录或旧副本。
2. 确认 `docs/plans/G1_IMPLEMENTATION_PLAN.md` 已经落库。若仅有此前下载的 `CFAW_News_G1_详细实施计划.md`，先自行放入该路径；若文件已存在，应先 diff 比对，而非覆盖。
3. 确认 `docs/CFAW_News_V1.md`、`audit/G0_REUSE_AUDIT.md`、`audit/G0_BASELINE.json` 和 `AGENTS.md` 存在。先保留既有 `AGENTS.md`，不要为了 G1 全盘重写。
4. 检查 `git status --short`、当前分支/HEAD，保留未提交工作。G0 审计锚点 `7f7f50324156b6a6ac61480a82311ba6ebd813b2` 用作比较依据，不意味着 HEAD 仍须与它完全相同。
5. 将 `.local/`、`.env`、`dev-diaries/`、业务库、用户隐私、密钥、浏览器个人资料和缓存排除在 Codex 的任务输入与任何 Git 提交之外；不要盲目打印秘密文件。
6. 权限原则：只开放项目工作区所需的文件写权限。G1 默认无需网络抓取、联网安装新依赖、生产库操作、Git push。遇到这些动作应停下请示。**提示词里的“禁止”不能替代真实权限隔离**，有条件时同时关闭不需要的联网访问并隔离业务库。
7. 不要在 Codex 的首轮提示里粘贴整份 1,000+ 行 G1 文档；直接让它从仓库读取 **本次 PR 对应章节与依赖章节**，节省上下文且更可控。

### 建议的关键只读检查

```powershell
Set-Location D:\agent_project\cfaw-news
git status --short
git branch --show-current
git rev-parse HEAD
Test-Path docs\plans\G1_IMPLEMENTATION_PLAN.md
Test-Path audit\G0_REUSE_AUDIT.md
Test-Path audit\G0_BASELINE.json
Test-Path AGENTS.md
```

G1 现阶段无需额外复杂的多 Agent 角色或大而全的自定义 Skill。现有 `AGENTS.md` + G1 计划文档 + PR 提示词已足够。

## 4. 所有 PR 共用的不可违反约束

以下约束应写进 Plan 或执行指令；若现有 `AGENTS.md` 已明确包含，则不用重复写入全局说明：

- **唯一需求依据**：`docs/CFAW_News_V1.md` 和 `docs/plans/G1_IMPLEMENTATION_PLAN.md`；现有源码和 G0 审计决定实际复用界限。内容冲突时列出冲突，**不能默默重新定义需求**。
- **PR 边界**：只实现当前 PR 的 DoD，尽量把改动限于 `evals/intelligence_v1/`、`tests/evals/` 与明确需要的文档。旧 `evals/run_baseline.py` 和现有 API/表尽量不动。
- **离线隔离**：不加载 `.env`，不读取 `.local/cfaw-news.db`，不网络抓取，不调用真实 LLM，不操作个人浏览器或用户私有信息，不修改生产数据。
- **时间无泄漏**：`published_at`、`observed_at`、`available_at` 语义分别定义；所有时刻必须含时区并转 UTC；历史 `as_of` 只能看到当时可见的版本、用户画像和曝光。
- **金标隔离**：预测基线不得读取人工 `event_id`、gold label、仲裁记录或未来信息。`B2-oracle` 必须单独命名、单独报告，不与真实预测比较混淆。
- **来源与数据许可**：真实素材与合成 fixture 必须区分；版权不明时不能把全文放入允许再分发的数据集；禁止伪造 URL、许可、真实样本和实验结果。
- **AI 开发验收**：DEV-01～05 可由 AI 完成初标、复核和裁定，不要求第二名真人。AI 结果注明来源；真人双标、真人一致性与研究结论单列。
- **验收证据**：报告真实命令、退出状态、用例通过/失败、修改文件、误例和遗留风险。未运行即标 `NOT RUN`，不能写“全部通过”。
- **Git 改动**：不自动 commit/push/merge，不创建远程 PR，不清理/重置用户未提交改动；提交前必须得到单独批准。
- **控制范围**：遇到必须动业务库、引入重大依赖、修改旧 Goal/Run 语义、处理无权查看的文件、引入在线模型/网络等，先停止并说明最小合理备选。

## 5. 第一轮：G1-PR1 的 Plan 模式提示词（直接复制）

```text
你现在是 CFAW News 的资深 Python 工程师兼时序信息检索评测工程师。我已完成 G0，接下来只规划 G1-PR1，不允许在本轮写入或修改任何文件。

项目根目录：D:\agent_project\cfaw-news。

请先只读并核对：
1. 仓库根目录及相关子目录的 AGENTS.md；
2. docs/CFAW_News_V1.md（产品和研究基准）；
3. docs/plans/G1_IMPLEMENTATION_PLAN.md 的 §0–5、§10 与 §11.1（G1-PR1）；
4. audit/G0_REUSE_AUDIT.md 和 audit/G0_BASELINE.json；
5. 与数据验证和现有评测相关的真实源码、测试、pyproject.toml 和依赖配置；
6. git status、当前分支、HEAD，识别用户既有修改。

任务：给我制定 G1-PR1 的实施计划，当前 PR 只包括 schema、Manifest、时间门禁、来源/哈希/家族规则、最小合法与非法 fixture 及对应测试。绝不能顺手实现 PR2–PR5。

请在计划中明确：
A. 真实文件路径、新增/修改文件清单、逐文件职责以及必须复用的现有函数；
B. DocumentVersion、PersonaVersion、ReplayStep、Exposure、CoverageWindow、Manifest 的最小字段与不变量；Event/Claim/Gold 在 PR1 的最低契约；
C. published_at/observed_at/available_at/as_of 的语义、UTC 处理、旧版本选择、未来曝光拒绝；
D. schema 与 runtime validator 的接口、异常码与 manifest/hash/来源许可检查；
E. T01/T02/T03/T20/T22/T23/T26、TZ01/TZ02/HASH01 的测试映射，哪些本 PR 完成、哪些后续补强；
F. 独立离线运行方案与不触碰现有业务库的方法；
G. 每个最小开发步骤的验证命令、完成条件、风险与回滚策略；
H. 与 G1 文档存在歧义或冲突的地方，提出不扩大范围的最小建议。

只输出可审查的计划与差异清单；禁止写代码、修改文档、迁移数据库、安装依赖、联网、执行 git commit/push。最后停下，等我批准再实施。不要问已经能够从仓库文档确认的问题。
```

### 审核 PR1 计划时检查这些点

- 是否把“旧文章当前态”误当作不可变历史？
- 是否把 `published_at` 当作 `available_at`，或直接按 ISO 时间字符串比较？
- 是否正确选择 **同一 document 在 `as_of` 可见的有效版本**，而不覆盖旧快照？
- 是否把有效 source、真实/合成、许可与 manifest hash 纳入校验？
- 是否避免 G1 数据验证模块依赖 FastAPI service 和生产 SQLAlchemy session？
- 是否将按计划应属 PR2/PR3 的内容提前塞进 PR1？
- 是否先有未来数据泄漏的负例，再实现过滤器？

## 6. 批准 PR1 后的执行提示词（直接复制）

```text
我已经审阅并批准你为 G1-PR1 制定的实施计划。现在切换到可编辑的执行工作方式，仅实现本 PR，不继续做 PR2。

请再次确认当前 git 工作区状态；如果与计划审批时不同，先解释差异，不要覆盖我的修改。

执行顺序：
1. 对时间泄漏、无时区时间、跨时区等价、未来 Persona/Exposure、篡改 Manifest、family 跨 split、权利缺失等情况，先建立可失败的自动测试/fixture。
2. 建立 evals/intelligence_v1 的最小 package、数据字典、Schema、异常码和来源登记。
3. 实现 Pydantic/JSON Schema 契约、parse_instant、visible_versions、visible_persona、visible_exposures、validate_dataset 等经过计划批准的最小接口。所有历史选择严格使用有时区 UTC datetime。
4. 新建至少一个三步 synthetic 最小样例，使 schema/时间门禁/校验可以实际运行；与 PR2 的正式 DEV-01 数据分开。
5. 运行相关新测试，然后运行现有 Ruff、完整 pytest、旧 seed-sanity、pip check，必要时验证前端构建未受影响。
6. 用只读 diff 检查是否触碰了旧 API/生产库相关路径，并检查 git diff --check。

不可违反：不读取 .env 或 .local/cfaw-news.db；不联网；不接真实模型；不修改业务表/旧 Goal/Run/Decision/Schedule 语义；不修改冻结 gold；不伪造第二人标注；不自动 commit/push/merge。

如遇阻断，明确记录失败命令、日志要点、原因和可行动的最小处理方案，不可绕过断言或把未通过测试写成通过。不要为了赶进度修改验收标准。

完成后用固定格式汇报：已实现功能、每个文件的变更与理由、Txx 测试清单及结果、全部运行命令及结果、遗留风险、是否满足 PR1 DoD、待我确认事项。完成本 PR 后立即停止。
```

> 若计划对目录/接口有合理调整，以**人类批准后的具体计划**为准；此执行提示词不能授权未批准的额外范围。

## 7. G1-PR2～PR5 每轮通用 Plan 提示词

在每个 PR 开始时，**新建或使用已完成上一个 PR 的正常 Codex 对话**，将下方模板里的 `G1-PRx`、章节和关键信息替换成对应值。新对话更能降低长期历史干扰，仓库文档和 Git 记录负责持久上下文。

```text
只做 G1-PRx 的只读规划，本轮禁止修改任何文件。

项目根目录：D:\agent_project\cfaw-news。请阅读 AGENTS.md、docs/CFAW_News_V1.md、docs/plans/G1_IMPLEMENTATION_PLAN.md 的 G1-PRx 章节和依赖章节、audit/G0_REUSE_AUDIT.md，以及已完成 PR 的代码/测试/验收记录。先检查 git status 和当前 HEAD。

当前 PR 的目标：【粘贴下文相应 PR 的目标摘要】。

请输出：
1. 上一 PR 交付是否满足本 PR 的进入条件（逐条给源码/测试证据）；
2. 当前 PR 需要新增/修改的文件与接口（不改旧业务契约）；
3. 逐步实现顺序，哪些测试先失败、哪些测试负责证明完成；
4. 哪些数据会/不会进入预测层，如何防止未来信息与 gold 泄漏；
5. 必须运行的测试命令和复现检查；
6. 三个最重要风险、阻断停止条件和 DoD；
7. 与仓库当前事实或规划不一致处（不要擅自改需求）。

只计划当前 PR，不执行开发、不联网、不迁移数据库、不安装新依赖、不 git commit/push。完成后停止，等我批准。
```

### PR 目标摘要（填进 Plan）

- **PR2**：构建 DEV-01 至少四个 `as_of`、不可变文档版本、Claim/事件关系及标注手册。AI 可完成试标与复核，不等待真人；不得伪造第二名真人或原始过程证据。
- **PR3**：搭建 as_of Replay、统一候选池与 B0/B1/B2-predicted 基线，另做 B2-oracle 诊断上界；预测不得读 gold。
- **PR4**：增加 B3 时间加权、B4 曝光增量规则、统一阅读预算、指标与七天回访反事实；不为了提升得分调整金标。
- **PR5**：扩展五条时序轨迹、AI 标注/复核记录、全量基线与开发验收；真人研究路径另报，不因缺真人阻塞开发。

## 8. PR2 实施提示词（批准对应 Plan 后）

```text
执行已经批准的 G1-PR2 计划，只做 §11.2，不做 PR3–PR5。先检查 git status，保留 PR1 成果和我的其他未提交工作。

在 evals/intelligence_v1 中构建正式 DEV-01 试点：至少 4 个 as_of（落在计划允许的 3–6 回放窗口内）、多份可核验的文档版本、上游转载/不同事件/独立补充证据/内容更正的对照、Version/Claim/EventRelation/Persona 历史及段落引用。确保当前时点只读取当时实际可见的数据；文档修改不能覆盖过去版本。

完成 ANNOTATION_GUIDE.md v1 和 DATA_CARD.md；四维 0–3 评分刻度和边界案例必须可供 AI 或其他审阅者操作。真实来源需记录出处与许可状态，无法证明历史正文/再分发授权时用明确 synthetic fixture 或合法形式，不可伪造真实时间与数据。

先写 T04/T05/T08/T09/T16/T17/T19/T21 的相关测试，再实现与修正；特别确保“引用 ID 存在”与“结论受到段落语义支持”分开报告。AI 可打分并复核；明确开发标签来源和偏差，不冒称独立真人双标。

完成后运行新旧回归，保存可见版本明细和 DoD 对照。不得改业务库、调用在线 LLM、联网抓取、自动提交或自行开始 PR3。最后报告文件变更、真实测试证据、来源/版权边界及未完成的人类标注环节，立即停止。
```

## 9. PR3 实施提示词（批准对应 Plan 后）

```text
执行已批准的 G1-PR3（§11.3），只做离线回放与 B0/B1/B2 基线，不做 B3/B4。

对每个 as_of：使用 PR1/PR2 的时间门禁得到**同一份完整可见候选池**，校验已冻结可见版本；不要借助实时当前 Article 行、不要预先只取 Top8。统一 RankerProtocol 和 canonical predictions JSONL：
- B0：按可见时间倒序 + 固定 ID tie-break；
- B1：复用 backend/cfaw_news/retrieval.py 的 BM25 内核，构建 persona 查询，确保全候选评分；
- B2-predicted：仅使用 as_of 可见 URL、文本和来源派生特征保守聚合，明显转载应合并，同一项目不同公告不能仅因同名合并；
- B2-oracle：只用作诊断上界，明确标记 Oracle，不参与真实预测分数主张。

在架构上硬隔离 GoldLabel/Annotation/人工事件金标与预测层：无 gold 时必须仍可生成同样的预测，评测器才可读 gold。先写 T06/T07/T15/T18、GROUP01/ORACLE01 及可重复运行测试，再完成实现。保存候选 ID、运行配置、预测事件分组、误合并/漏合并及哈希。两次相同输入必须得到逐字节相同 canonical predictions JSONL；动态运行时间仅放 metadata。

运行 PR3 新测试及 G0 既有 Ruff/pytest/seed/pip/build。若发现接口必须侵入旧 API 或数据库，先停下说明。不得开始 PR4、自动提交或上传数据。最终汇报每个基线如何实现、候选公平性证据、gold 隔离证明、实测输出和未解决误例。
```

## 10. PR4 实施提示词（批准对应 Plan 后）

```text
执行已批准的 G1-PR4（§11.4），只做 B3/B4、评测指标、阅读预算与七天回访，不做 PR5。

B3 使用 UTC 规范下的 material-visibility 时间进行简易时间加权，配置明确记录半衰期，不能凭主观修改使开发集指标好看。B4 显式区分 included/rendered/opened/ack：没有新证据时对重复推荐实施可解释降权；存在可见更正或重要新增证据时不能永久压制；不得把页面展示视为用户理解。

实现统一 180/420/900 秒阅读预算与事件单主卡位截断逻辑。指标实现必须记录分子/分母、空分母 null + 原因、事件级 Recall、nDCG、重复率、变化与回访覆盖、来源覆盖缺口及运行成本；不能把停机/503/unknown 解释为无更新。

建立七天回访 fixture D0–D8，包含重要旧变化与普通新文、同一事件转载、已曝光无增量、官方更正、未来反馈和源故障，执行计划 §11.4 的五种反事实测试。先写 T10–T14/T24、METRIC01/METRIC02、BUDGET01 测试，随后实现。B0–B4 共享候选池、输出配置/哈希/逐步预测；两次重跑字节级一致，计时与随机元数据另存。

运行 G0 旧回归；输出第一版 report.md，必须列出失败、漏报、误合并与不确定性，不允许修改 gold 粉饰结果。仅本 PR，完成后停止，不自动开展 PR5、联网抓取、生产迁移或 Git push。
```

## 11. PR5 实施提示词（批准对应 Plan 后）

```text
执行已批准的 G1-PR5（§11.5），目标是严谨收口而不是制造“G1 已完成”的表面结果。

依据 DEV-01 的经批准模板扩展 DEV-02～DEV-05，每条含 3–6 个 as_of；资料的时间、出处、真实/合成、事件关系、Claim、Persona、曝光/覆盖及标签均明确，可追溯。对真实材料逐项登记内容权限；不把生产库当前态伪装成历史版本；所有相近/反事实样本按 family 分组防止数据泄漏。

按 docs/plans/G1_AI_DEVELOPMENT_RULES.md 执行：AI 完成五轨迹初标、证据复核、争议裁定与开发标签；可由同一 AI 分轮执行，不等待第二名真人。保存原稿、生成信息、修订差异和未解决项；既有真人提交保留原文。缺真人不阻塞 ai_development 验收，human_research 另列。

当两个真实标注结果存在后，才计算原始一致率/加权 kappa、分歧矩阵、仲裁及冻结 gold 版本。确保任何金标更新会产生新 revision/hash，不能为了改进 B4 指标改标签。

覆盖全部适用 T01–T24、T26 及额外隔离/确定性/许可测试；T25 在没有真实生产迁移时明确 N/A。离线运行 B0/B1/B2-predicted/B2-oracle/B3/B4，保存 manifest/代码 SHA、候选、预测、指标、分母、错误分析、来源覆盖限制；完整重跑 Ruff、pytest、旧 seed-sanity、pip check 和 frontend build。

写 G1_ACCEPTANCE.md：逐条对应 §13 硬门槛，分别报告 PASS/FAIL/BLOCKED/N/A 与证据路径；不声称合成结果证明真实用户价值或线上可靠覆盖。不自动开始 G2，不改生产库、不 push/merge。使用 ai_development profile；只有当前必需开发门槛实测通过，才报告 G1-a 开发验收通过。规则修改本身不等于通过。
```

## 12. 审查提示词（强烈建议每 PR 用新对话）

**Review 轮建议先不要让 Codex自动修复**；先独立找出实际问题，再由执行轮修复。尤其注意时间泄漏、误用 gold、引用语义误判、数据许可、ID 和不可变性。

```text
请以严格的独立 Code Reviewer 身份审查刚完成的 G1-PRx。此轮只读审查，不修改任何文件。

阅读本 PR 批准的实施计划、docs/plans/G1_IMPLEMENTATION_PLAN.md 对应章节及 §13、仓库 AGENTS.md、audit/G0_REUSE_AUDIT.md、git diff 和所有新增测试/数据 fixture。先识别 diff 的基准 commit 和当前状态，不要误把我的其他未提交文件归入 PR。

请按照 P0/P1/P2 严重程度报告：
1. 时间门禁、旧版本、UTC、未来 Persona/曝光是否可能泄漏；
2. gold/oracle 有没有进入预测路径，候选池/阅读预算是否公平；
3. 合成数据、版权、来源和第二人标注是否被错误表述；
4. 新增测试是否真正断言期望行为（而非永真断言），是否遗漏计划指定 Txx；
5. 是否回归破坏了旧服务、数据库、Goal/Run、seed-sanity；
6. 数据冻结、hash、稳定排序、可重复性和异常状态是否可靠；
7. 必须阻断验收的事项及最小修复建议。

每个问题提供具体文件/行号、重现方式与为什么是问题。若没有发现问题，明确说明“未发现问题”，同时列出仍未实测的风险；不要声称形式审查可代替测试。先不要修复、提交或 push。
```


### Review 有问题时的修复轮提示词

```text
以下是 G1-PRx 的独立审查问题清单：【粘贴具体 finding】。
请只修复这些经确认的 P0/P1 问题及必需回归测试；不要扩展功能、修改金标来掩盖失败、顺手开展下一 PR。先复现问题，补足会失败的测试，再做最小修复，然后运行相关测试和原工程回归。

报告：每个问题是否真正修复、验证命令/结果、仍然失败或受阻的项、是否需要重新审查。不得自动 commit/push。完成后停止。
```

## 13. 完成一轮时的交接提示词

```text
请对刚完成的 G1-PRx 制作一份准确、简短但可复现的交接摘要，供我在下一次 Codex 新对话中使用。本轮不做代码修改。

必须写明：
- 基于哪个 Git commit / 本 PR branch 和哪些批准的文档版本；
- 本 PR 真实完成与未完成的 DoD；
- 变更文件与核心接口；
- 通过、失败、未运行的测试及具体命令；
- 数据/manifest/schema revision 与新增 fixture；
- 目前 P0/P1 风险或缺失的外部资源；
- 下一 PR 的前置条件是否满足。

如仓库有既定审核记录位置，请建议使用它，但不未经批准创建额外的工作流文件或提交。不得宣称没有运行过的测试已通过。
```

## 14. 可选：PR3/PR4 用 Goal Mode 时怎么写

只有当一个 PR 已有**经过批准的具体计划**，且需要反复进行“实现→测量→修复”的闭环时，才考虑 Goal。不要把 Goal 设置成“完成全部 G1”。示例：

```text
/goal 在当前 G1-PR3 范围内实现并验证离线 Replay、B0/B1/B2-predicted 与独立的 B2-oracle，保证所有预测共享 as_of 可见候选池、预测层不能读取 gold、确定性输出与指定测试通过，同时维持旧 Ruff/pytest/seed 回归。不修改业务数据库、旧 Goal/Run、联网权限或未批准的文件；不提交或推送。每轮优先修复真实失败并记录证据；如必须扩大权限/范围、数据无法证实时停止并报告阻断。满足当前 PR 的全部 DoD 或遇到阻断即停止，不自动开始 PR4。
```

目标模式可能主动跨多个内部迭代继续工作，所以实际使用时仍需确认权限和停止条件。Goal 完成后应主动检查当前状态；如需停止，使用当前客户端支持的 Goal 生命周期控件/命令，不让旧目标残留到下一 PR。

## 15. Git 与人工验收

### PR 完成后的只读检查

```powershell
Set-Location D:\agent_project\cfaw-news
git status --short
git diff --check
git diff --stat
git diff --name-only
```

若你使用 Git 提交/推送，请先审查 `git diff` 和任何新建未跟踪文件，检查没有 `.env`、`.local/`、`dev-diaries/`、个人数据、secret、未授权全文或临时预测输出被包含。**`git diff` 默认不展示未跟踪文件，需要 `git status` 和文件级复核。**

### 回归命令（PowerShell，项目根目录）

```powershell
.\.venv\Scripts\python.exe -m ruff check backend tests evals
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe evals/run_baseline.py
.\.venv\Scripts\python.exe -m pip check
Push-Location frontend
npm run build
Pop-Location
```

G1 新 CLI 的建议契约见 `docs/plans/G1_IMPLEMENTATION_PLAN.md` §12；它们在对应 PR 实现前**不能当作已有命令**。

### 每次人工验收清单

- [ ] 当前 PR 的范围与 `docs/plans/G1_IMPLEMENTATION_PLAN.md` 对齐。
- [ ] 关键失败用例已由自动测试锁定，测试是真的运行过。
- [ ] 不可变历史、时区、未来信息、金标隔离的必要门禁有效。
- [ ] 旧 Ruff / 125 项已有回归 / seed / 依赖 / 前端构建持续通过（实际项目通过数量可能因新增测试而增加，不用死守恰好 125）。
- [ ] 无生产数据库读写、敏感数据泄露或未经批准的外部操作。
- [ ] 独立 review 的 P0/P1 已处理，或明确阻断合并。
- [ ] 文档、输出、Git diff、manifest/hash/测试日志与真实状态一致。
- [ ] 人工确认后才提交、合并并进入下一 PR。

## 16. 八个反面提示词与替代写法

| 不建议这样说           | 更建议这样说                                      |
| ---------------- | ------------------------------------------- |
| “把 G1 全部实现好”     | “只做 G1-PR1，完成对应 DoD 后停下。”                   |
| “你自己看着办，功能越多越好”  | “严格按当前 PR 和数据契约，其他发现写 backlog。”             |
| “保证算法超过 BM25”    | “公平比较并忠实报告正、负、零提升。”                         |
| “读数据库重建过去的版本”    | “仅使用可证明的不可变版本或标明 synthetic 的 fixture。”      |
| “让 AI 标注两遍代替双标”  | “允许 AI 复核，注明来源；真人研究资格单列。”                      |
| “把时间排序做成字符串比较就好” | “解析 aware datetime，统一 UTC 比较，含跨 offset 负例。” |
| “有引用说明结论可靠”      | “引用定位与语义支持分离，并记录未测量范围。”                     |
| “测过就自动提交所有代码”    | “我核对测试与 diff 后另行授权提交。”                      |

## 17. 最适合你现在发送给 Codex 的实际顺序

1. 确认 `docs/plans/G1_IMPLEMENTATION_PLAN.md` 真实存在并与本地批准版本一致。
2. 打开仓库根目录的 Codex；切到 **Plan Mode**。
3. **复制第 5 节的 PR1 Plan 提示词**，要求只读审查并给出具体计划。
4. 审查计划：文件边界、接口、时间门禁、Txx 负例、无联网/业务库访问。
5. 对满意的计划，切换到可执行模式，**复制第 6 节的 PR1 执行提示词**。
6. 完成后用新对话运行第 12 节的 Review 提示词；修复发现再复测。
7. 自己检查 diff/测试并做 Git 检查点；之后再进入 PR2 的 Plan。

**最终提醒：Codex 是开发执行者，不是研究真实性的最终裁判。** 本项目关于“防未来泄漏、禁止伪金标、结果可复现”的要求，必须由可执行验证器、真实运行日志与独立审查来保证，而不能只依靠一句“请严格遵守”。

## 官方参考（2026-10-20 查询）

- [Mastering remote engineering work from your phone — Plan 与 Goal 的关系](https://developers.openai.com/blog/mastering-codex-remote-for-engineering)
- [Using Goals in Codex — Goal 用法与生命周期](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex)
- [Iterating Development Workflows with Codex — AGENTS、分阶段开发、人工审批](https://developers.openai.com/cookbook/examples/codex/iterating-development-workflows-with-codex)
- [OpenAI Codex 配置基础 — 审批与沙盒](https://developers.openai.com/zh-Hans/docs/config-file/config-basic)
