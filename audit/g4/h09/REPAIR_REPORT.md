# H09 Persona/历史连续性与 raw 快照目录修复

2026-11-06，main@d82b169d72bc10bf669b51aa149ff20ce928fb47 加未提交工作树。两项 finding 已在实现方本地工程范围修复并复验，**仍待独立总审查，未批准 G4 Beta**。本轮授权扩大到这两项产品路径；没有趁机改变 G1/G2/G3 评分、数据、冻结 Schema 或生产数据库。

## 行为与安全约束

P1：保存预算会保留新的实际 Persona 版本，生成不再把该最新 Persona 套到所有历史时间。`service.py` 在受检事务内捕获实际 Persona 链和 SQLite journal 前缀；`runtime_history.py` 校验完整行成员、hash 链、来源、因果时间、目标、撤回和 stream，再映射到原有 native G3 历史协议。`g2_adapter.py` 每步选择当时可用的真实 Persona；冷启动从首份 Persona 的实际可用时间开始，旧资料原观察时间/版本不变，不伪造此前不存在的用户推断。已建立事件身份在后续预算版本保持连续。

历史交付从保存时的 immutable native basis 重演，不读取当前正文覆盖过去。旧 v1 通过原 runtime SHA 和 stage 重演检查；新 v2 把 basis SHA 写入不可变 view，避免递归嵌套旧完整历史。`g3_adapter.py` 将通过验证的交付与反馈交给原 G3 history/revisit/ranking 内核，未更改权重、重复惩罚、预算贪心或资格规则。真实记录不改标 synthetic；为真实来源单独提供协议兼容的 G4 事件类型。

included/rendered/opened/ack/dismiss/retract 仍有区别。opened 不表示知道；明确 ack 才影响实际交付的知识判断，撤回恢复后续状态。Archive 元数据反馈继续可审计，不能构造 delivery、主张支持或知识。更正后的事实不因旧 ack 被隐藏；无明确 merge/split mapping 不暗中继承反馈。

新增 home-visible visit 与卡片曝光/知识独立。前端仅在页面正面积视口相交且 document 可见时确认，幂等 intent 跨 StrictMode effect 重复保留。生成携带进入页面前的 journal sequence，后端重算并验证该 cutoff 的上次访问窗口；本会话新访问不会裁掉应回访区间。旧交互兼容、首次一天默认、超过 30 天限长均显式展示。计算期间后续访问造成 head 前移时，只在原前缀仍为祖先、epoch 与 Persona/最新发布/资料/取消守卫全部满足时重试 publication CAS；不重算或放行过期 Persona。

P2：GET `/api/intelligence/briefings` 按当前 stream 列出不可变元数据，使用固定 through_version 和 before_version 游标分页。无交互 raw 简报同样出现，未来游标/其他 stream 拒绝；读取目录与历史不会写交互或改变最新指针。前端历史按钮不再依赖 interaction rows，包含加载、失败重试、分页和按已知 ID 访问。

新 API `g4-h09-contracts-v2`，runtime envelope/config v2；旧 v1 序列化省略新增字段，保持原 bytes。新 Schema 在 `evals/intelligence_g4/schema/h09_v2/`（24 份 API/OpenAPI/Version 工件）和 `h09_native_v2/`（5 份 native Schema）。DB migration 002、checkpoint v2、corpus v1 不变，无新表。

## 当前实际验证

RUN = `.tmp/evals/g3/g4-h09-20261106-001/`。每项 exact argv/cwd/env/UTC/elapsed/exit/log SHA 见同名 command.json；JUnit/控制面和全部临时目录包含于独立新 seal。非零迭代记录同样保留。

| 验证 | 结果 | 工件 |
|---|---|---|
| 注册 runner 完整 tests | 1753 passed / 1 skipped / 1 warning，926.68 秒 | full-final.xml、full-final-control.json、full-final.command.json |
| collect/插件/argv/source pins/JUnit | PASS，1754 节点，其中 G3 630 | inventory.json、collect-control.json、control-verification.json |
| 完整 G4，包括新增 H09 18 节点 | 339 passed / 1 warning，294.66 秒 | g4-final.xml、g4-final.command.json |
| 前端定向单测 | 14 passed | frontend-unit.log |
| 浏览器契约 | 27 组 PASS，含新目录分页/零交互检查 | browser-contracts-native/browser-results.json |
| 实际材料及旧流程浏览器 | 11 组 PASS，其中 3 组为明确标注的时间 UI fixtures | browser-pilot-retry/result.json |
| 开发版 StrictMode 焦点 | 5 项×3 轮 PASS | browser-retry/focus/focus-result.json |
| 浏览器服务有效参数/生命周期 | 8135/8136/5175 均 ready；STOP 后 exit 0 | browser-retry/*.service.json、lifecycle.json |
| 保存预算→native 生成及原始时间/身份 | 实际 SQLite 180/900/420 均完成；raw V2 替换后仍零交互可发现 | sqlite-proof.json、pilot-retry/ |
| 复现者所指旧 QA Persona v4/420 | 备份恢复新 epoch 副本上 420、更新 v5/180 后均完成；原备份 SHA 不变 | legacy-replay-final/result.json、budget-420.json、budget-180.json |
| Ruff、seed baseline、当前 TS/Vite 构建 | PASS | ruff-delivery、baseline-final、build-current 收据 |
| API/native Schema 与生成类型 | PASS | schema-check-final、native-schema-check、types-final 收据 |

封存后完整递归核验的目录数、文件数、hash 和字节数见 `audit/G4_H09_REPAIR_MANIFEST.json:recursive_verification`。最终源码、依赖/工具链、配置、rights、policy、DB/API Schema、真实输入及日志各自有独立目录索引/hash；QA 索引名与业务 manifest 不冲突，独占创建。

测试覆盖：晚/早首份 Persona、连续预算更新、1/3/7 天实际 SQLite/原生重访、opened≠known、重复惩罚、ack/retract、更正保护、旧 v1 delivered witness、前缀/hash/Persona/访问 cutoff 篡改、分页稳定性/跨流、native 计算期间 visit 成功与 Persona stale 拒绝。计时轨迹是受控测试时钟，工程材料/合格 delivery 不充当真实外部情报。

浏览器为 Microsoft Edge 156.0.4314.58；CFAW_PR5_OUT/URL、CFAW_PR6_RUN/PILOT/URL、Boundary URL、fixtures SHA、实际服务配置均封存。取消用 `--qa-delay 2`，CLI 与有效配置一致。自动采集、媒体和正文补抓关闭，站外浏览器请求阻断。实际旧 Goal→Run→Decision→明确本地日程批准→幂等重试→完成→历史重开通过；通知调用为零，无自动订阅/第三方动作。

## 失败和历史包

首轮完整 tests：1752 passed / 1 failed / 1 skipped。失败为未改动的 `test_retire_demo_news_keeps_feed_history_and_user_records`：interval() 每次重新取当前分钟，“精确重试”得到 409。隔离测试库保存批准时间 17:50:59.982 UTC，推断重试跨分钟改变请求；未截获第二份 payload，故此解释明确为推断。原节点独立复跑及最终完整套件通过；不改测试、业务幂等规则或冻结控制。完整日志/JUnit/失败数据库保留。

早期工程迭代中的测试时钟属性、查询白名单、旧 runtime hash 换行问题、原 API 预期，以及浏览器输出遗留“未修复”文案均保留原始记录，后续修正重新验收；不得用早期记录代表最终源码。当前 SQL 证明独立复核生成内容，不仅检查保存预算的 HTTP 成功。

入场冻结资产中 813 个 G1/G2/G3/tests/data-archive 文件及依赖 pins 保持原 hash；未重跑 2574 次研究比较矩阵，也未重新签发研究结论。旧 PR6 v1 已失效；旧 v2 seal SHA `a1f406a4c73627919afe231cc52670c624d8ca4d04df52aba75c486f7a5b876b` 的 JSON 与原登记文件未改；“封存树不改写”的原声明撤回：legacy replay 曾留下未登记 WAL/SHM。2026-11-06 修复保留侧文件证据并只隔离这两项，未改旧索引，重新核验完整引用树；详情见 `audit/g4/h09_review/REVIEW_FIXES.md`。原封存源码副本及首次失败记录保留。H09 新 seal 单独记录授权差异和当前 source-snapshot。

## 限制和停止点

g4_development = CONDITIONAL_PENDING_REVIEW；g4_beta_utility = OFFLINE_REJECTION_PILOT_PASSED_BETA_PENDING；g4_research_optional = NOT_EVALUATED。H00–H12 逐项工件/边界见 `docs/G4_ACCEPTANCE.md` 与新 manifest。

现实材料仍是本机已有、原文不改的 Vite 8.3.4 MIT README；真实发布时间未知，不倒填观察时间。实际仍 raw_news_only/hold、Focus/Radar=0，Archive 只保留许可元数据且原始资讯可读。合格反馈评分是工程轨迹验证，不证明现实推荐质量、算法收益或用户价值。外部网络 smoke、真人研究、阅读估时校准和现实合格 Focus/Radar：not_evaluated。

前缀容量上限为 128 Persona、128 delivered proofs、12000 selected rows、20000 journal entries，另有原输入字节限额；缺失/超限拒绝，不静默截断。30 天限长不代表更早时段已覆盖，无界长期历史压缩未实现。保留本地单用户、cooperative cancellation 等既有边界。

没有触碰真实用户原库，没有新外部抓取、push/commit/merge/公网部署，没有提交私密资料或 dev-diaries/。到此停止，等待独立总审查和所有者对 G4 Beta 的批准，不自动进入 G5。

本报告属于 H09 初次封存证据。当前恢复输入隔离和获准的精确重试测试变更，另见 `audit/G4_H09_REVIEW_FIX_MANIFEST.json`；原 813 文件原字节声明不扩展到这次授权修订的 tests/test_workflow.py。
