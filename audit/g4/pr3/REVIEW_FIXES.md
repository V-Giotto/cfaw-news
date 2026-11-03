# G4-PR3 独立审查修复报告

2026-11-02。状态：实施方修复与自测，待独立复审；不宣称独立关闭。
HEAD 保持 main@783f5428671457ea3f1f654b160152f653d2e9e0，暂存区为空。
本轮只修复当前 PR3 的两项 P1、一项 P2，没有 Git 写操作、真实采集/模型、HTTP/UI、
数据库迁移或真实用户数据库写入。管理员未批准下一 PR。

## 修复结论

| Finding | 修复后的行为 | 本轮证据 | 状态 |
|---|---|---|---|
| P1 许可改写材料类型 | native_doc 原样保留 content_kind；excerpt-only RSS 被 native 权限拒绝，明确 raw 降级 | 材料同文合法绑定对照、CLI 与 PR2 隔离账本导出 | FIXED，待独立复审 |
| P1 Persona 推迟文档前缀 | 原生步骤用文档 available_at；缺历史 Persona 时 evidence_not_ready，不新生事件或遗漏后继续输出 | 早期 Persona 对照保持事件/快照及 2 条 claim；晚期 Persona 两例明确阻断 | FIXED BY EXPLICIT BLOCK，待独立复审 |
| P2 内部校验绕过控制 | 一个 Control/一个 deadline 贯穿所有嵌套重放与模型比较，finally 清理请求作用域 | ranking/budget/plan-model/result-model 各取消及超时，共 8 例；触发后新分组均 0 | FIXED，待独立复审 |

更正后的设计见 docs/adr/G4_RUNTIME_BRIDGE_REVIEW_FIX.md。原 ADR/实施报告中关于
quoted_excerpt 映射和 Persona max 时间的描述属于修复前历史，已被本补充明确替代。
原审查、实施、Schema、manifest、baseline 字节保留，没有悄悄修改旧验收状态。

## 具体边界

材料类型不再从 rights/retention 推断。excerpt-only + feed_summary 带正文时，当前冻结
native 契约给出 RIGHTS_USE_NOT_ALLOWED，结果为 raw_news_only、stages=[]、context/
ranking/plan=null。不可变输入版本及来源保留，不伪造原生证据或 Archive snapshot ID。
合规 permitted + fulltext 对照仍为 feed_summary，G2 保持 secondary_material、other、
unverified；primary_text_unavailable 在 claim limitations 和 coverage_gaps 中保留。
本轮没有注册新的摘要引用契约，不能称已支持 excerpt-only RSS 情报生成。

当前封套没有历史 Persona 或可续接的可信原生状态。因此当当前画像晚于第一份文档时，
明确返回 G4_RUNTIME_PERSONA_HISTORY_REQUIRED / evidence_not_ready；native 入口也拒绝。
没有倒填画像、生成“默认早期画像”、移动文档时刻或静默换 birth anchor。只有画像在
第一步已合法可用时才重放全部文档前缀。保存较晚画像后的连续推荐仍未实现，后续需另案。

Control 移至 runtime_control.py，runtime.Control 兼容导出。ContextVar 在当前同步请求内
传递同一对象和同一截止时间，不因调用验证器而重置；外层已有 Control 时禁止换另一个。
run/derive/validate_context/rank_runtime/plan_fields、RuntimePlan/RuntimeResult 的严格重算
和返回边界都有检查。直接模型 JSON 导入支持 context={"control": control}。
native 输入验证后、原生阶段间、逐候选排名、预算和序列化验证完成后均检查。
这仍是 cooperative 停止，不能硬抢占一个已进入的纯函数；没有异步 worker 或发布实现。

## 本轮真实验证

工件根目录：.tmp/evals/g3/g4-pr3-review-fix-20261102-001/。
每个正式检查有 command.json：实际 argv/cwd/环境/时间/退出码、原始日志及日志 SHA。
REVIEW_FIX_BASELINE.json 为当前源码、Schema、配置、输入输出、测试与探针的机器可读索引。

| 本轮执行 | 结果 |
|---|---|
| G4 完整集合 g4-final | **237 passed、0 skipped、1 既有第三方警告**；215 原节点 + 22 新节点 |
| green-02 定向回归 | 49 passed；随后补充 native 输入验证后取消/超时，已包含在 237 项中 |
| 正式旧套件 full | **1753 passed、1 skipped、1 warning**；1754 节点的注册库存、源码、JUnit 与控制记录核对 |
| 原生排序/预算等价、安装隔离与篡改拒绝 | 已包含在本轮 G4 集合，不沿用旧执行日志 |
| Ruff backend tests evals + 构建脚本/审计工具 | PASS |
| 5 份新 Schema 导出/逐字节检查 | PASS；目录 schema/pr3_review_fix/ |
| 词法 baseline、frontend build | PASS；不宣称模型或浏览器验证 |
| 独立保存的走读/故障探针 | 13 例通过：5 个 CLI + 8 个内部故障；均为工程 mock |

full 的 skip 是既有 Windows symlink 权限错误 1314 豁免；唯一警告为既有第三方
Starlette/httpx 弃用。完整集合中的 G3 630 项及 fact_signature 59 项为本轮实际执行，
没有称为另外一轮 G3 测试。先前 PR3 的 1753/215 记录只保留作历史，本轮结果为以上新日志。

8 个内部重放探针都确认继承原请求 Control：

| 触发位置 | 触发前已完成分组 | 取消后新分组 | 超时后新分组 |
|---|---:|---:|---:|
| ranking validate_context | 3 | 0 | 0 |
| budget validate_context | 6 | 0 | 0 |
| RuntimePlan 验证 | 9 | 0 | 0 |
| RuntimeResult 验证 | 15 | 0 | 0 |

另测直接模型 JSON 传 Control、失败后下一请求不受污染、native 输入验证结束后不再开始
分组、晚画像 CLI 的合法阻断、原始摘要 CLI 的安全降级，以及旧 config pin 拒绝。
原有引用/池/快照/分数/计划篡改拒绝和未来 as_of CLI 负例继续执行。

保留失败过程：red 为 15 failed/1 passed；其中 14 项暴露修复前缺陷，另 1 项为新增
permitted 对照把 primary_text_unavailable 断言到 bundle 的测试位置错误，已改为实际
claim limitations/coverage_gaps。green-01 为 15 passed/1 failed，余下同一断言位置错误；
green-02 和最终 G4 通过。首次审计 probe 误用 G2 data 序列化 PR2 SourcePolicy 导致退出 1，
改用其正式 model_dump 后在新 proof-final 目录重跑通过。失败日志未覆盖、删除或冒称成功。

## 文件、pin 与历史保全

修改四个 PR3 源文件 g2_adapter.py、g3_adapter.py、runtime.py、runtime_contracts.py；
新增 runtime_control.py。调整三个旧 PR3 测试的错误预期：excerpt 应无原生 ranking、
账本保留 feed_summary、CLI 无 context 时不存在 trace 遍历；不是删掉原节点。
新增 test_pr3_review_fixes.py 22 个节点。旧测试清单原字节保留，新审查清单显式记录
before/after 源摘要，完整 G4 库存仍核对所有 237 个唯一节点。

ranking 策略升级为 g4-runtime-ranking-policy-v2，新 policy SHA：
696e984bfd3fc0638f925de0a2cf3bc5eb11ba34a31c3fd109f99f3c58e34243。
旧 ranking/config pin 拒绝。fact signature 仍为 g3-grounded-fact-signature-v2，policy SHA：
70565148fe436fa823ef6a4063cbba7abb4c994cc34f19dc44bdc2451e367450。
native engine 源码、G1/G2/G3 算法、验收数据、旧 Schema/manifest、pyproject、前端及旧业务
均未修改。B4 默认、P1 显式实验、预算候选未校准、Archive/预算诊断保留策略均不改变。

入口快照包括 1011 个跟踪/原有未跟踪文件，预期只变更上述 4 个源文件和 3 个测试。
修复前相关源码副本在本轮 source-before/ 中，支持审查未提交文件的精确差异。
管理员提供的 6 份独立走读/复现 JSON 逐字节保全；历史工件不是本轮运行结果。
原 /dev-diaries/ ignore 规则保留；未读取或上传该目录。

## 阻断与交接

本轮无已知未修复的三个 finding；独立复审尚未发生，不能称正式关闭。
真实来源独立性仍未实现，真实 Focus/Radar 继续安全降级；历史 Persona/state 缺口明确
阻断连续性，excerpt-only RSS 正文仍受 native 契约限制。这些未实现能力没有被测试 PASS
替代或扩权。工程 mock 不证明线上来源、真实许可、用户效用或排名增益。
完成后停止，交回独立只读复审，不进入 PR4，不执行提交/推送。
