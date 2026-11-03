# CFAW News G4-PR3 实施报告

日期：2026-11-02（Asia/Shanghai）。状态：**本地工程自验收，待独立审查**。
本轮只实施 PR3，没有 commit/push、HTTP、前端修改、迁移修改、真实采集或模型调用。
管理员下一 PR 批准状态：PENDING。本报告不是独立复审关闭记录。

## 入口与上游

实际入口/结束 HEAD：`783f5428671457ea3f1f654b160152f653d2e9e0`，分支 main；
入口工作树干净。入口 983 个跟踪文件在 `.tmp/evals/g3/g4-pr3-20261102-001/entry.json`
逐文件记录；结束核对全部保持原字节，新增文件独立提交审查，暂存区为空。

当前用户“实施 CFAW News G4-PR3”消息是 PR3 的明确实施授权。先前 GitHub 发布授权
不扩展为本轮发布授权。没有读取、复制或上传开发日记，也没有读写真实用户数据库。

`audit/g4/pr2/RE_REVIEW.md` 是仓库已有的独立 AI 复审关闭记录：PR2 PASS，SQLite
sidecar 备份/receipt 两项缺陷关闭。原修复/复审报告及发布 pin 全保留。本轮在新的
G4 集合中实际重跑 PR1/PR2 164 项，不能把旧复审中的测试算成本轮结果。

实际读取/复核根 AGENTS.md、docs/G4_IMPLEMENTATION_PLAN.md、PR1/PR2 ADR、
docs/G3_G4_HANDOFF.md、G3 fact_signature/contracts/bridge/replay/rankers/revisit/history/
budget、正式 G2 各阶段接口及相应严格模型。事实签名仍是 v2，不使用旧验收 pin 承诺兼容。

## 交付与状态

| 范围 | 状态 | 证据/限制 |
|---|---|---|
| PR2 真实不可变版本到正式 G2 原生模型与阶段 | PASS（隔离库/mocks） | from_ledger 只读一致快照；native checked_input、group/evidence/rule/presentation |
| runtime_local_v1 独立严格封套 | PASS | 新版本模型和 5 份 Schema；不创建 accepted_g2/synthetic_contract_probe 身份 |
| G3 原生特征、排序和预算计算复用 | PASS（本地计算） | B4/P1 逐行全字段对照；预算 derive 全字段对照；无权重/算法变更 |
| 真实 Focus/Radar 资格 | **BLOCKED** | 冻结 G2 的 independent_support=disabled / independence_unknown；真实非空主张通常 raw_news_only、plan=null |
| synthetic 开发计算 | PASS | plan_ready/hold 均合法；始终 publishable=false，不混排为真实资讯 |
| 生产历史、跨请求 trusted head、持久化发布 | NOT_IMPLEMENTED / PR4 | journal/deliveries 明确为空，不伪装真实用户知识或曝光 |
| 真实网络/模型、生产部署、浏览器 E2E/用户效用 | NOT_EVALUATED | 本轮无此授权或实现范围 |
| 独立审查、管理员验收 | PENDING | 实施 Agent 的自测不能替代另一会话只读审查 |

没有剩余的已知本轮测试 FAIL；早期失败命令全部保留并在下文列明。工程 PASS 不等于
真实来源许可已完成研究、真实事件语义已独立验证、P1 增益已证明或生产能力已经完成。

新增文件与测试矩阵见 PLAN_AND_BOUNDARIES.md；具体接口、资格与降级决策见
docs/adr/G4_RUNTIME_BRIDGE_V1.md。原 PR1 ADR 不改写，PR3 的现状在新 ADR 中追加说明。

## 校验与计算

版本链要求完整捕获前缀、不可变 predecessor、连续 sequence 和单调 observed/available，
当前头由链尾导出。原生每步使用完整可见头及 lineage，不让调用者选择旧版本。
实际 PR2 隔离数据库测试包含后续版本晚于 as_of 的选择、读取不改行、坏 policy/coverage
行拒绝，以及合法点覆盖导出。每份 SQL 数据先核对主键/列/JSON/摘要，再进入原生模型。

来源策略、rights/allowed_use、provenance、画像 origin、as_of、引用、事件 key/revision、
证据、快照和候选全集均复核。构造候选只投影正式原生生成结果，没有手写 verified。
真实 excerpt 采用更严格的 quoted_excerpt；ledger 和 native 两种 content SHA 分别保留。
未知语言为 und；未知权利只含 PR2 安全元数据；多个政策版本暂显式 raw 降级。

G3 正式 replay 绑定的 accepted_g2 是离线证明，不是生产 runtime。新封套保留真正 G2
结果并重新运行校验及原生计算内核，不生成旧 G3 父验收记录，不把 real 改成 synthetic。
真实历史在 PR4 前明确未集成，不能称已验证真实用户重访效果。重复输入确定性重算。

默认 B4。P1 仅在显式实验标记存在时运行。注册预算必须显式选择 60/40、70/30 或 80/20；
70/30 没有自动成为产品默认，所有候选均未校准。计划保留完整 Archive、excluded、
not_displayed、truncated、unmet_protected_event_keys 及原因。原生贪心预算仍可能漏掉
minimum 总和可装下的保护项，没有全局最优承诺。

coverage 使用原生保守区间并集，来源全集取配置列表，保留无候选/无 window 的来源。
未观察区间明确 unknown，失败/partial/offline 不成为 covered，点观察不能证明连续覆盖。
不修改冻结 G2 的 coverage_gaps；消费方必须使用外层 coverage.has_gap 和区间诊断。

资格疑义在 run 和预算入口同时拦截，直接调用计划函数也不能生成真实 Focus/Radar。
内部 ranking 的原生 eligible/tier 是计算诊断，不能当作外层展示许可。
取消和超时检查发生在阶段间、序列化后及返回前，不是强制中断某个正在计算的纯函数。
没有取消后发布或部分数据库写入，因为本 PR 不持久化任何运行结果。

## 本轮真实验证

所有以下执行来自 `.tmp/evals/g3/g4-pr3-20261102-001/`，每条支持命令有 argv、cwd、
环境、起止时间、退出码、原始合并日志和日志 SHA；BASELINE.json 引用这些记录。

| 最终验证 | 实际结果 |
|---|---|
| g4-final-02：全部 G4 测试 | 215 passed，0 skipped；PR1/PR2 164 + PR3 51 |
| full：冻结正式 pytest_runner --mode full | 1753 passed、1 skipped、1 warning；1754 节点库存/源码/执行控制/JUnit 全核对 |
| full 内 G3 / fact_signature | 630 / 59 项实际执行；未冒称另跑一轮独立 G3 |
| Ruff backend tests evals + 新构建脚本/审计工具 | PASS |
| PR1/PR2/PR3 Schema | PASS；旧 Schema 不变，新 PR3 5 份逐字节一致 |
| evals/run_baseline.py | PASS；仅词法基线 |
| frontend npm run build | PASS；仅兼容构建，未声称浏览器验收 |
| 原生排序等价 | B4/P1 × repeat/correction，完整 RevisitEvent 字段一致 |
| 原生预算等价 | 三个注册 profile 全字段一致；运行时只扩展配置来源全集 coverage |
| CLI 真实执行 | 7 个独立 case：合成、显式 P1、真实形状 excerpt/unknown、hold、未来时间拒绝、旧 pin 拒绝 |
| 安装隔离 | core/native wheel 离线安装到临时 target，仓库外 Python -I 运行；缺 native/改源码均拒绝 |

full 的唯一 skip 是既有 Windows symlink 权限错误 1314 豁免；警告为既有第三方
Starlette/httpx 弃用。G4 亦有同一第三方警告。没有其他 skip 或缩减库存。

覆盖案例还包括多源同事件、独立性 unknown、real/synthetic 混用拒绝、数值/符号/单位
事实签名区别、未来文档/画像/覆盖及未来截止时间、hold-only、超长输入、取消/超时、
重复输入、引用/快照/排名/候选池/计划篡改、预算 profile 改变 pin 但不改变事件 namespace。
CLI 正例阶段文件有独立 SHA，trace.path 对应实际文件，trace_pointer 对应结果中的阶段。

最后增加“直接 RuntimeEnvelope JSON 导入未来 as_of 也拒绝”后重跑 G4；之前 214 项
结果、首个内部封存 baseline（baseline-seal-01.json）、首份新增清单和源码快照保留在
本轮工件目录，均已被最终 215 项封存取代。旧套件源码和控制面未变，故 full 不重复跑。

早期保留的非零执行：runtime-01/02/03/05（文件 SHA/严格原生投影/tuple 序列化修复），
equivalence-install-01（Windows 沙箱 OS 临时目录权限，改用隔离项目临时目录重跑），
ruff-01（新文件 import 排序），schema-pr2（命令缺少 --directory，正确命令已重跑）。
这些是本轮失败记录，不能删除或算作 PASS；最终对应检查全部通过。

## pin、风险及审查交接

BASELINE.json 是最终源码、Schema、配置、native engine、ranking policy、fact policy、
完整 argv/日志和 CLI/安装输入输出摘要的机器可读索引。RELEASE_MANIFEST.json 绑定
本报告、ADR、清单、审计工具及 baseline；较大原始工件留在忽略的本地临时目录。
fact policy：g3-grounded-fact-signature-v2，SHA
`70565148fe436fa823ef6a4063cbba7abb4c994cc34f19dc44bdc2451e367450`。

127 个原生 Python 文件与 retrieval 源码锁定；新 runtime wheel 显式声明 companion native
依赖。根 pyproject 受冻结 G3 控制面绑定，保持原样；常规旧 backend 构建没有自动注册
本能力，必须使用新显式构建配置。没有打包 fixture/标签/验收证明或用户数据。

待审查风险：适配使用冻结私有计算内核，未来升级须重新注册并做等价验证；有界全前缀
重放会重复计算，不是高吞吐服务；自包含输入不能发现调用者删掉整个已捕获尾部，真实
受控入口使用完整账本导出，PR4 必须提供可信 head。SHA 绑定不是来源身份或许可认证。

管理员后续需要决定真实来源独立性证据/资格政策，以及何时授权 PR4；本轮没有替其
批准放宽资格。下一步是新会话独立只读审查 PR3，必要时修复与复审，再由管理员决定。
