# G2-PR2 验收：关系预测与跨时点身份

日期：2026-10-24T09:53:53.722441+00:00。技术验收 **PASS（仅 PR2 范围）**；开发复核为非盲、同一 Codex 上下文的 **ai_development**，不是独立科研或真人验证。G2 整阶段及 G3 准入均未验收。

## 实现及真实仓库状态

- HEAD 仍为 `76ef14b531842ae449c4f907302218d2e2ea4c90`；PR1 与 PR2 均处于现有工作区，未 commit/push。既有 `.gitattributes` 修改及管理员的两份未跟踪计划文档均保留。
- 独立 `pr2/` 包、17 份 Schema v2、固定配置、12 条 synthetic 轨迹/16 个时点、独立评测与 T11–T18 测试已实现。PR1 v1 Schema、代码、配置、fixture 和验收报告保持不变。
- R1 默认，R2 明确选用；R0 原样调用 G1 group_candidates。六类关系、cannot-link、complete-linkage、代表项及全部来源指针可执行。不开发 PR3 Claim/支持判断、完整证据束、API/UI、模型或生产 DB。
- 身份按首次可见锚点注册；当前成员更新只改 revision。谱系匹配优先于强锚点，强锚点匹配须唯一。merge 追加别名，split/多对多纠错退役父键并新建全部子键，历史引用按原 key/revision/snapshot 解析。
- CLI 从轨迹首个登记时点回放到 through-step，不支持静默冷启动或外部状态恢复。输出只写新 `.tmp/evals/g2/` 目录，失败不接受半成品目录。

## 当前验证证据

| 检查 | 实际结果 |
|---|---|
| G2 专项（PR1+PR2） | 113 passed，0 skipped；其中 PR2 43 项 |
| 全部离线评测目录 | 539 passed，1 skipped |
| 项目全量 | 664 passed，1 skipped，1 warning；665 个唯一测试节点 |
| 节点范围 | G1 427；G2 113；旧业务 125 |
| Ruff / G1+PR1+PR2 Schema / G1 strict manifest | 全部退出 0 |
| lexical seed / frontend npm offline build | 退出 0；不是模型效果验证 |
| 三种策略 CLI 与独立 CLI 评测 | 全部退出 0，实际 argv/日志有记录 |
| 固定资产 | 239 个既有保护文件、29 个 PR1 指纹及 PR1 报告均无变化 |
| 输出与隔离 | hash seed 1/719 语义字节一致；G1/fixture 双路径禁止参考 stat/open、网络、私人路径、DB 和区外写入的审计通过 |

完整跳过原因：`symlink creation unavailable: 1314`。不因跳过放宽断言。当前完整回归使用获准的 Windows 本机 loopback 环境；没有外部服务或真实模型调用。

证据根目录：`D:/agent_project/cfaw-news/.tmp/g2-pr2-evidence/final/`。每项 `.command.json` 保存实际 argv、cwd、退出码、耗时和日志 SHA；`g2-current.xml`、`evals.xml`、`full-current.xml` 为实际 JUnit。`source-snapshot.json` 保存 45 个新增核心文件指纹及实际运行源码哈希。

完整矩阵：`D:/agent_project/cfaw-news/.tmp/g2-pr2-evidence/final-matrix-003/matrix.json`，包含实际执行脚本 argv、57 次预测 API 调用的参数/耗时/结果及 19 次后置评测。产物在 `.tmp/evals/g2/pr2-final-matrix-003/`。这是 API 矩阵；另有 smoke-r0/r1/r2/evaluate-smoke 的真实 CLI 命令记录，不将 API 调用伪装成独立 CLI 命令。

## 同池开发诊断

每种策略处理相同候选和前缀：G1 五条主轨迹 26 点、附属轨迹 9 点，新增 synthetic 16 点。合计每种策略 51 点、三策略 153 个 step-strategy 观察。参考仅读取 evidence_at<=as_of 的精确可见版本；没有用 G1 EventGroup/labels 填答案。

| 数据范围 / 策略 | TP | FP 误合并 | FN 漏合并 | TN | 微平均 F1 |
|---|---:|---:|---:|---:|---:|
| G1 主轨迹 / r0 | 19 | 0 | 1 | 7 | 0.974359 |
| G1 主轨迹 / r1 | 20 | 0 | 0 | 7 | 1.000000 |
| G1 主轨迹 / r2 | 20 | 0 | 0 | 7 | 1.000000 |
| 新增合成 / r0 | 45 | 1 | 4 | 14 | 0.947368 |
| 新增合成 / r1 | 48 | 0 | 1 | 15 | 0.989691 |
| 新增合成 / r2 | 49 | 0 | 0 | 15 | 1.000000 |

**指标限制：**G1 主轨迹只有 27 个可评分 pair 观察，167 个参考不确定；附属 9 点无可评分关系，指标为 null。新增合成的 49 个正 pair 中，45 个来自十文档重复块，微平均容易被重复块主导。矩阵同时保存轨迹宏平均、唯一 pair、重复时点计数、弃权率、混淆矩阵及阻断正关系数量；这些不是独立样本或真实新闻效果证明。

R1 保留 BRIDGE 的 1 次 FN：只有弱日期/文本依据，默认策略主动弃权。R2 在该开发样例中改善覆盖，但仍保持实验对照；它有一条正 pair 被 complete-linkage 阻断，最终聚类 FP=0 不代表六分类全对。没有按分数调整阈值或修改参考。

五条主轨迹的冻结 D0→D8 连续性案例，R0/R1/R2 均保持键稳定；新增 EVIDENCE、FUTURE 连续性亦通过。没有无法解释的换键。成员保留及代表项来源指针覆盖为 100%（空集为 null），仅是结构覆盖，未验证语义支持或来源独立性。

每个 timeline 的 metrics.json、errors.jsonl、errors.md 保存 pair、预测/参考、规则/特征/cannot-link/阻断、前后键/revision/transition、根因提示、影响及 AI 溯源。R0 的不同版本 upstream 误合并保留为对照，未修饰其结果。

## T11–T18 与 AI 自复核

| ID | 已执行的核心断言 |
|---|---|
| T11 | 十份 URL+hash 重复只有一个事件/代表项；十个成员与来源完整；漏成员拒绝 |
| T12 | 公告+明确目标测试归同事件；独立性仍 unknown；upstream 不自动判转载；否定 testing、跨语言目标有正反例 |
| T13 | 不同主体、版本、动作对象、license/theme、同 monorepo 不同产品和多主体比较不误并；硬冲突输出拒绝 |
| T14 | A–B/B–C 正、A–C 弱/冲突不桥接；R2 14 天边界、近转载、R0 原始函数一致性 |
| T15 | 增补/版本修订保键、无变化不假修订、无关候选/persona/整包 pin 不改旧身份、复现空窗恢复和文档改为不同发布；谱系匹配优先 |
| T16 | merge→split、全部新子键、历史别名按时点解析；多对多 complex、非法图拒绝；旧 PR1 item/bundle 字节保持 |
| T17 | future body poison/未来特征/未来状态先于载荷访问拒绝；边界可见后才校验/使用；cursor 和前驱篡改拒绝 |
| T18 | 两 seed/顺序/前缀确定性，同池拒绝错误输入，参考缺失可预测，审计、pin/输出篡改、原子失败及禁止覆盖 |

Codex 已保存 draft.json、review.json、revisions.json 和 fixtures/pr2/v1/manifest.json。单 AI 非盲内部复核发现并修复：否定 testing 误识别、monorepo 掩盖明确不同主体、强目标匹配抢占谱系，以及连续性统计错误地用无关 transition 解释换键。修正前后的 153 个候选分区完全一致，R0 grouping 源码未变；身份优先级修复没有改变对照的聚类分数。

开发参考在首次矩阵前冻结；修订未改标签或阈值。model_id 未知记 unknown，review_origin=ai_development，不新增双真人标注或逐条管理员审批门槛。

## 未完成尝试、环境与边界

- 首个完整 pytest 在身份优先级修正前主动中止，退出 4294967295，不能计为通过；保留 full-tests.command.json/log。当前通过证据仅使用 full-tests-current。
- matrix-current 在 Windows 暂存目录 rename 时报 WinError 5；没有接受该矩阵为成功。保留失败日志，使用新目录 final-matrix-003 完整重跑，无 force、跳过或放宽写入校验。
- 沙箱内 asyncio loopback 探测 5 秒超时；一次沙箱外自动审批因额度而无法完成，明确不是不安全判定。额度窗口恢复后重新获准，当前全量通过。没有绕过审批。
- G1 loader 仍读取/哈希完整 JSONL 字节；保证未来正文不进入预测对象或算法，不声称物理上从未读取未来文件字节。
- 规则语法范围有限，多事件文章、隐式指代、无标识跨语言或没有足够正文时可弃权。模型/embedding、PR3、生产持久化和真实用户质量尚未开发/验证。

回滚只撤回新增 PR2 子包、v2 Schema、配置、fixture、测试、报告及 README/数据字典追加段落，保留 PR1、G1、历史结果和管理员既有未跟踪文档。无 DB 回滚；没有 commit/push。
