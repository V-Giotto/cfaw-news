> 已被新批次替代（2026-10-23）：本文为历史版本证据；默认流程已改为单 AI 开发，原真人待办不再是前置条件。当前批次、pin、实际验收和限制见 [PR5 AI 开发收尾](PR5_AI_DEVELOPMENT.md)。历史数据与结论未改判。

> 当前版本更新（2026-10-23）：v8-r1 / g1-pr5-4，pin `ad9a58f84c25de4d60b716afb2d008739257d60d8ed68a7235cc5c72ccf6cbe4`。V3已接入，收到DEV-02～05的40份文件及80项共同复核；全量512 passed/1 skipped、G1 387 passed/1 skipped，矩阵200预测/400评测。人工门槛仍BLOCKED，G1-a未通过；真实初标过程、D6本人修订及低一致性处理尚待闭环。最新验证及独立复审范围见 [V3收尾记录](PR5_V3_INTEGRATION.md)。下文完整保留v6及其新增问题发现时的历史语境，不将旧状态当成当前缺件结论。

# G1-PR5 v5–v6：人工准备与工程收尾

当前冻结：`pr5-five-trajectories-v6 / g1-pr5-2`。

Manifest SHA-256：`ee4a8648f832342ba415a30d5f0724d372a8a6cfd1031d51c0eb19a0fd2d5873`。

**保存的 v6 机器技术验收为 PASS；最新独立审查发现支持审查溯源 P1，正式人工导入受阻；人工标注 BLOCKED；G1-a 未通过，不能进入 G2。**

## 最新共同复核进度与新增阻断

用户确认本轮由 A/B 共同复核，已收到 43 条关系语义转换确认、7 项事件裁定及全部 material_change、50 个语义审查工作项。50 项含重复主张，不是独立样本数；8 项语义标签变化单独登记，原始初标和初标一致性未覆盖。
工作项编号从“A 全部后 B 全部”映射到现有逐步交错任务，通过 annotation_id/claim_index 保持 50 项一一对应。组级引用按各步可见时间展开，未来引用只记录排除原因；没有进入当步证据或预测。

独立审查“审查 G1”，turn `01a163e6-3048-7000-96df-b6a9c1ddf1c2`，确认新增 P1：`annotations.py:424–428` 要求双方原稿的 claim_text、evidence_refs、scope 与最终支持审查完全相同，无法记录保留不同原稿的正常共同仲裁。合成对照通过；仅改措辞、引用子集/顺序、scope 或共同裁定第三种表述均返回 SUPPORT_REVIEW_LINEAGE_INVALID。探针不是人工证据。
该问题阻断当前人工支持审查流程验收；原 v6 保存测试和工件核验 PASS 属于此前覆盖范围，不能替代此路径的修复验证。按批准计划的 P0/P1 停止条件，暂停正式导入；本轮未修改冻结代码/schema、原稿或正式 gold。
最小修复需要显式的“原始 annotation_id + 原始 ClaimReview canonical hash → 人工最终裁定”映射，并保留对齐理由、人员和实际时间；继续验证双人来源、冻结、版本、family 及可见性，新增不同原稿正例和错误映射负例，不能删除相等检查或自动模糊配对。

来源、完整裁定、编号映射、补充回答和独立复审结论保存在：
`.local/evals/g1/pr5/human-readiness-v6/human-joint-review-20261022/`。
仍缺 DEV-02～05 的 20 步双方初标、旧协议及修订史闭环、手册修订/正式重标和全量人工版本冻结验收；无需重复提交本轮已收到的裁定。

## 完成的工程工作

- 单步 v2 导出提供完整空白 judgment、数组/引用/关系字段模板、精确 JSON schema 及受控 v2 手册；模板不含答案，不是提交。
- 修正开发比较统计的过滤分母；split/merge 以文档重叠组件记录，不再附加假漏标。
- pair 指标只比较双方均已标注的文档；缺整侧/部分标注不默认为负例。v5 复审发现的问题以两项红灯复现，在 v6 修复。
- 提供分布、原始一致率/混淆矩阵及固定 seed=719、1000 次 family-cluster bootstrap。单 family/null/退化分母明示原因；五 family 区间不作泛化证据。
- .70 观察目标及当前保守的修订/重标阻断规则未降低。真人与 AI 的比较强制保持开发用途，不能计为双人证据。
- v3 手册仅为本地待真人试用草案，未生效；当前正式协议仍 g1a-guide-v2 / g1a-annotation-v1。

## 实际验证

| 检查 | 最终结果 |
|---|---|
| 全量 pytest（含旧服务/API/Goal/Run 等原 125 项） | 462 passed / 1 skipped / 1 warning；463 个节点 |
| G1 pytest | 337 passed / 1 skipped；338 个节点 |
| Ruff / schema / strict Manifest / pip check / seed / 前端离线 build / diff check | 全部 exit 0 |
| 冻结测试覆盖 | 463 必需节点、适用 T01–T24/T26 与测试源码指纹核验；T25=N/A |
| 完整矩阵 | 200 次预测 / 400 次评测 / 655 次 CLI；1,400 个确定性工件校验 |
| 排名与数据保留 | 600 个预测/输入/config 与 v4 一致；86 个 JSONL 与 v4 一致 |
| 不完整 JUnit 端到端负例 | 只留旧 125+2 个 G1、移除 336 个 G1 并更新 SHA，仍得到 REQUIRED_TESTS_INCOMPLETE；technical/temporal/regression=BLOCKED |
| 正常验收 CLI | exit 1；technical=PASS，human=BLOCKED，g1a_passed=false，g2_eligible=false |

命令、退出码、日志、JUnit 和指纹：`.local/evals/g1/pr5/human-readiness-v6/checks/`。
矩阵、独立种子与逐步汇总：同目录 `matrix/`；正常验收：`acceptance/`；负例：`truncated-evidence-negative/`。

默认环境的单独 G1 运行曾在 600 秒超时，没有算通过；其超时记录保留，原始 stdout 未保存。随后在允许本地 socketpair 的环境用新临时目录完整重跑通过。
v5 初次矩阵有一次未复现的 EXPORT_IO_ERROR，诊断单次重放通过；后续 v5 中断和所有失败日志保留，不算完成。
最终 v6 上述矩阵所有 655 个命令均为成功记录。原生 symlink 权限 1314 为原有明确豁免 skip，不算通过。
Starlette/httpx 弃用 warning 单列，未安装新依赖处理它。无真实生产数据库或物理磁盘故障实测。

## 独立复审范围

“审查 G1”，turn `01a1638c-ea05-75e3-805c-4f49d8f2fc9a`，针对同一 v6 pin 的代码修复复审 PASS，未发现剩余 P0/P1/P2。
独立完成 11 项只读 pytest、6 次聚焦内存调用、严格 Manifest、Ruff、Schema、独立收集 463 节点。
复审核对时最终 full/checks/matrix 尚未齐全，因此当时未宣布技术整体验收 PASS；随后本线程补齐并核验上述实际工件。
原四项修复未回归。代码复审、保存工件核验和真人证据是不同范围，不能互相替代。

最终工件追加独立核验已完成：“审查 G1”，turn `01a163ca-bbdb-70b1-ade7-b7be9b415a86`，结论 PASS，未发现新增 P0/P1/P2，保存证据支持技术验收 PASS。
该次只读核对同一 pin 的 176 个受控哈希、98 项源码等指纹、9 项检查命令、全量/G1 JUnit 与冻结节点、矩阵 655 条命令和 1,400 个工件及日志哈希，并确认 700 对确定性文件一致；只读复算汇总与保存结果相同。
同时核验 86 个 JSONL、600 个预测/输入/config 与 v4 一致，重新确认截断证据被 REQUIRED_TESTS_INCOMPLETE 拒绝。完整复审结论保存在 `.local/evals/g1/pr5/human-readiness-v6/final-artifact-rereview.json`。
本次是保存工件核验，没有重新运行完整测试或矩阵，也不认证真人双标或语义支持。来源与独立性的最新用户确认见下节。

## 人工部分的真实状态

用户最新更正并确认：A 为本人；B 是与 A 不同的第二名真人，现有 B 文件是其原稿；B 在未看 A 答案、未来材料或算法结果前独立作答，评分、理由和语义判断未经 AI 生成或实质改写。A 先前确认评分/理由未由 AI 生成或实质改写。
据此将本地现有批次登记为两名真人的 DEV-01 试标，身份与独立性依据为用户直接确认。此前“一人+AI”的来源陈述及报告以历史记录保留，已标记被最新更正替代；没有删除来源变更或修订/重冻历史。
这项更正不代表正式标签已接纳：ReviewSession 仍 not_started，正式五类人工 JSONL 均为空。当前六步选稿共 12 份、15 条格式合格记录；未改原稿、评分、gold 或实际包哈希。
当前 A 稿按用户最新指定作为后续采用版本，既有修订/重冻历史仍保留，不追改为未经修订的历史首次盲标。
活动目录及被拒候选的 .bak 按明确要求清理，审计快照保留。旧 v1 包没有被偷换为 v2 哈希。
技术比对确认旧包和当前包的文档投影、Persona 一致，但旧包缺少 8 个当前上下文字段；不据此自动授予正式兼容资格。

当前六步选稿的中性诊断已重新计算，包含全部步骤；D1 的 split/merge 保留为分组分歧，不强配评分。可对应的 6 对中，graded relevance 加权 κ=0.267、tier κ=0.091、potential value 加权 κ=0.667，均低于 .70 观察目标；不能删除争议样本或改 gold 提分。由于尚需核验初标/修订记录，这不是已认证的讨论前初标一致性；单 family 的 bootstrap 区间为 null。
最初准备了 43 条关系转换确认、7 个分歧组件和 50 个按初标展开的语义审查工作项；随后已收到本轮共同复核及变化类别补充，详见顶部最新进度。50 项含重复主张，不能当独立样本数。DEV-02～05 仍缺 20 步双方提交，即 40 份个人单步提交。
来源更正后实际运行正式 `annotations audit`，CLI exit 0、无结构错误，但 `human_gate=BLOCKED`、正式 initial_annotation_count=0；审计成功运行不等于人工门槛通过。新的 15 条严格 JSON 反序列化、原稿/转换/快照哈希检查均通过，诊断统计与原计算的纯算术部分一致。

详细人工事项、管理员表、待确认手册草案和邀请文字：
`.local/evals/g1/pr5/human-readiness-v6/human-inputs/HUMAN_ACTIONS.md`。
最新来源确认、现选稿诊断及人工待办：
`.local/evals/g1/pr5/human-readiness-v6/human-source-correction-20261022/NEXT_HUMAN_ACTIONS.md`。
该待办已标记本轮共同复核进度；最新裁定回执为 `human-joint-review-20261022/REVIEW_RECEIPT.md`。
当前 DEV-01/D0 双份空白包：`next-human-step/`，这些重新导出的包未分发，不替代历史回执。
管理员完整五轨迹导出位于 `matrix/administrator-packets/`，不能整目录交给标注者。

两名真人的存在与独立作答已经用户确认，无需重复寻找第二人。关系语义转换与 DEV-01 共同复核已收到，仍需将旧包版本和修订记录核验闭环，修复新增支持审查溯源 P1，完成手册试用/采用版本、五轨迹独立原始提交及可正式导入的仲裁、支持审查和 gold 来源。
这些完成后另行冻结真实人工版本并全量验收。来源确认、结构合格和完整人工验收是不同证据。

未联网、未迁移生产数据库、未安装依赖、未 commit/push。HEAD 仍为 `e1ce349895b06dc57b40b5c5e1f75b50caf411ec`，PR5 尚未提交。
