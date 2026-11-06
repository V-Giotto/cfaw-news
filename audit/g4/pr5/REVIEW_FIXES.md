# G4-PR5 审查问题修复

2026-11-05。**六项实现修复完成，工程验证 PASS；独立复审与所有者验收 PENDING。**
本文件追加于原 PR5 报告，不改写原验收工件。入口仍为 `d82b169` 加上一轮未提交的
PR5 工作树；没有 commit/push、数据库维护或 PR6 工作。

| Finding | 修复 | 回归证据 |
|---|---|---|
| P1：详情读取首条旧 assessment | 后端按快照 as_of 过滤未来记录，按时间、追加顺序取每个 claim 的最新状态；前端兼容仍返回完整历史的响应，独立选择最新记录，保留微秒精度。明确展示 current / historical / superseded / retracted。 | 原生两步更正/撤回 API 验证 current→superseded/retracted；旧快照再次读取仍 current。浏览器在同一旧主张上验证新旧两个快照，另覆盖未排序、同时间追加、未来微秒记录。 |
| P2：Archive 来源隔离不完整 | 共享 safeDetail 检查 rule item、claims、citations 及 candidate 中嵌套派生证据的 origin/材料类型/许可。identity、时间、真实文档校验单独保留；派生来源不一致时只显示经过绑定的安全文档元数据，不显示主张/引用/全文阅读/反馈，也不写 opened。 | 四种混合响应：item、claim、citation、presentation.base_item 分别标 synthetic。Focus 拒绝内容，Archive 只剩元数据，无 ack/opened/rendered。此为防御性条件，不声称正常后端会生成混合响应。 |
| P2：Radar/truncated 未执行投影 | DeliveryView 增加 projection/content_refs/omitted_refs，新发布视图逐字保留 native plan 的选择。卡片只解析允许的完整 rule-item block；Radar 不显示推断，minimum 也不显示 what_happened。保留所选主张、scope、来源归因、证据状态、限制、风险与 status。完整内容留在显式详情中。缺少/矛盾投影时停止卡片内容展示。 | Focus / Radar / minimum 的 refs→DOM 断言；minimum 缺两正文、Radar 缺推断，详情仍可查看完整内容。原生 API delivery 字段与 plan 对齐。 |
| P2：重读/导航产生新 rendered 收据 | 会话级注册表按 briefing/target/kind 保存同一个观察意图与幂等键；共享进行中的 promise 和已确认结果。失败只重试原意图。rendered 仍需新的真实视口确认，未因预取创建记录。opened 同样复用观察意图。 | 浏览器同一 delivery 首次曝光、重新读取、资料库→首页返回始终只有 1 个 rendered HTTP 请求。单元测试覆盖丢失响应、并发重试、重挂取同一 key。 |
| P2：预算剩余不可见 | 显示当前快照 budget_diagnostics 的估算已用 / 剩余秒数；无 plan 显示“未计算”，不使用当前偏好替代历史快照值。 | 三投影显示快照 used/unused；raw-only 显示未计算，原 180/420/900 切换回归保持。 |
| P2：异常 API 响应卸载整应用 | 从同一份封存 Schema 生成运行时校验表，GET 简报与事件详情在组件读取前校验嵌套结构；不通过时保留旧快照并显示错误。BriefingHome 外增加局部 ErrorBoundary，错误页含资料库入口和重新挂载重试。 | 缺 coverage 的成功响应不会移除旧导航；重读可恢复。浏览器另挂载真实 Boundary + 抛错子组件，验证局部兜底、保留旁边导航、资料库入口与修复后重试。 |

## 兼容性与契约

API Schema 新导出为 `evals/intelligence_g4/schema/pr5_review_fix/`，版本
`g4-pr5-contracts-v1`；原 PR4 导出目录保持原字节。HTTP 既有 view revision v1 保留，
只增加带默认值的 delivery 字段，写入协议、SQLite migration、checkpoint、评分/预算
算法与资格门不变。

旧持久化简报缺少投影时，GET 先校验其自己的 runtime payload SHA，再从该 runtime
保存的 plan 按 event/snapshot/估时绑定补齐响应字段，计算新的响应 ETag；不读取当前
文章、不重新运行分配、不写回 row.data/runtime/journal。回归证明输入字典和数据库
视图未变化，旧 as_of 的主张状态也未被新版本覆盖。

运行时结构校验只负责形状，不替代证据资格。来源不一致的 metadata 降级不能用于
推荐或确认已了解。观察意图注册表覆盖同一浏览器会话内的重挂、导航与重读，
没有新增本地持久化用户反馈或后台自动操作。

真实 Focus/Radar 资格仍由 PR4 阻断；没有放宽真实材料/来源独立性门槛。
浏览器的真实形状情报仍是显式 authored HTTP mock；原生历史轨迹使用隔离 synthetic
工程输入，不能作为真实新闻、许可真实性、独立语义验证或用户价值证据。

## 本轮验证

工件根目录：`.tmp/evals/g3/g4-pr5-review-20261105-001/`；精确命令、退出码、日志 SHA、
JUnit、源码和新 Schema pin 见 `PR5_REVIEW_FIX_BASELINE.json`。

- G4：**321 passed / 1 条既有弃用 warning**，含新增 3 项原生历史/旧投影回归。
- 前端策略/API/时序/校验/观察意图：**14 passed**。
- Edge/Playwright：**26 组检查通过**，包括原 15 组及本轮追加场景，无未捕获
  pageerror 或静态资源失败。ErrorBoundary 故意抛错的隔离组件另行断言恢复。
- TS/Vite build、Ruff（backend/tests/evals/PR5 工具）、lexical baseline、当前 20 份
  API Schema 和生成 TS/运行时 Schema 检查通过。
- 旧完整 pytest：**1753 passed / 1 skipped / 1 条既有弃用 warning**，1207.43 秒；
  使用项目内 basetemp，无失败忽略或门槛降低。跳过项仍为 Windows symlink 权限限制。

首轮 G4 的三个 CLI 负例因 basetemp 不在其允许的 `.tmp/evals/g3` 下，提前返回
REFERENCE_MISMATCH；已改为允许路径并完整重跑，321 passed。新测试首轮在持有
store.read 锁时又跨线程发 GET 导致 STORE_BUSY，已把 GET 移到读锁外。浏览器重读
断言首轮引用到即将卸载的旧 DOM，已等待对应响应和加载结束后再验证曝光次数。
这些中间失败保留在原日志中，没有重写成成功或降低断言。

所有 DB、输入、截图均为隔离工程构造数据，未使用生产数据库、真实私密资料或
外部模型/新闻调用。开发日记 ignore 规则保留。完成本修复后停在待复审状态；
PR4 原 shutdown 独立复审仍 PENDING，不由本报告替代。
