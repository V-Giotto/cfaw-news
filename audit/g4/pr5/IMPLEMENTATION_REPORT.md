# G4-PR5：React 三层情报首页与反馈 UI

2026-11-04。状态：**实施完成，等待审查**；本文件不构成独立复审或所有者验收。

## 入口与前置核对

本轮由所有者明确授权实施 PR5，入口 `main@d82b169`，工作树干净。已读取 G4 计划、
PR4 persistence / review / shutdown ADR、发布记录、当前 API 实现与 Schema，以及
App / NewsLibrary / api / GoalWorkspace / ArticleReader。

PR4 的来源前缀恢复、客户端/内部幂等域、实际 worker 生命周期及 run-start/shutdown
交接修复已有源码与工程回归闭环。最新 `SHUTDOWN_RESERVATION_FIX.md` 仍明确记为
**独立复审 PENDING**；本轮不将它改为 accepted。PR5 授权来自本轮用户指令，不改写
旧发布记录中的 next-PR 授权状态。当前 service.py SHA 仍为
`20afee774f8c734f87650f75ba48e895f390e40af83d23dfee0e7e1d5144da83`。

当前 API 版本是 `g4-pr4-contracts-v2`，HTTP payload revision 仍为各自 v1。
`persistence_schema --check` 对 20 份工件通过；TS wire types 从封存 Schema 直接生成，
包含必填字段、默认可选字段、union、literal 与所有递归依赖，提供 `--check` 防漂移。
这只验证接口形状，不授予证据资格。

## 最终行为

- 默认进入“我的情报”，主导航一键进入原始资讯库、关注工作台、行动日程和检查记录。
  NewsLibrary、ArticleReader、GoalWorkspace、ActivityPages 源码保留。
- Focus / Radar 仅消费真实 `plan_ready` 的绑定 delivery，检查原生 tier、许可、材料类型、
  快照/事件/修订及真实文档来源；详情预取不记 opened，并发上限 2。没有合格材料时
  明示空态、`raw_news_only` 与 source gaps。synthetic 服务完全隔离，不混入首页。
- 卡片展示发生了什么、相关性推断、主张证据状态、来源、风险/不确定性与可选择动作。
  聚合 `attributed` 仅表示保留归因，不冒充主张已验证；`unverified`、
  `source_attributed`、`independently_supported`、争议/撤回分别标识。
- Archive 保留完整候选、excluded/truncated/hold 和安全原因，可搜索。hold、受限许可、
  legacy metadata 只显示安全元数据，不展示主张、引用片段或推荐摘要。
- 证据弹窗绑定 briefing ID / snapshot version / event snapshot / revision / as_of，
  按 doc_version_id 和原段落解析引用，检查 Unicode code-point span 与 quote 一致性。
  阅读保存版本始终使用 ArticleReader 的 `snapshot` 模式，不读取当前正文接口。
  外部原始网页单独标注可能已更新；正文没有 HTML 注入渲染路径。
- rendered 观察的是卡片实际标题与证据状态区域：IntersectionObserver 确认可见比例
  >=60%，持续 600ms，前台可见且无打开的 dialog 后才写入；离开页面即清理观察。
  请求返回、组件挂载、预取和 included 均不记 rendered。详情完成绑定并真实显示后才
  记 opened；后台标签页返回前台后再确认。打开不等于知道，记录不表示 learned。
- ack/dismiss/retract 只由显式按钮触发；展示 pending、失败、撤回与幂等重试。
  全局串行写入；同一意图在响应丢失后保留 key 和完整语义。只有明确 unchanged 的
  head conflict 可在同 epoch 内更新 head 重试；语义版本冲突不自动重放。
  明确未提交的冲突可显式放弃并重读；未知提交结果保持同一意图重试。
- 预算 180/420/900 秒均标“估算”，保存 Persona 后手动生成，不将新偏好误标为旧快照
  的预算。默认 B4、注册的 focus70/radar30 profile，未修改 G2/G3 排名或分配逻辑。
- “自上次访问以来”以首次状态读取时的 journal sequence 固定会话边界，只选此前的
  rendered/opened/ack/dismiss；included 不算访问，本次曝光不能改写上次访问。
  比较当时快照的新增/修订/相同/退出，并明确修订不证明实质变化、退出不等于撤回。
  历史不足、分页不完整或读失败时不推断没有变化。
- 来源窗口、生成时间、截至时点、缺失/未观察来源及未满足保护项直接可见。
  覆盖不被解释为“全网没有更新”。旧快照、历史查看、加载、离线、取消、超时、权限
  拒绝、版本冲突和长内容有明确状态。读取 15 秒、写入 20 秒请求期限；生成任务轮询
  有界，可重读或显式取消。窄屏、语义标题、aria、原生 dialog、Escape 与焦点恢复可用。

## 当前运行时限制

当前 PR4 `qualification()` 明确拒绝真实 `plan_ready`，PR3/PR4 尚不能确认真实独立支持。
因此本轮实际 PR4 API 路径验证的是真实模式的 raw/空态与 evidence_not_ready，
**没有产生真实 eligible Focus/Radar**。本 PR 保留此边界，没有修改服务器资格规则。
合格卡片 UI 由浏览器路由中的显式 authored HTTP mock 覆盖；它只存在于测试脚本，
页面截图带工程 mock 水印，不能作为真实新闻、真实许可或线上推荐的验证。

当前 API 没有完整 briefing-list / revisit-summary endpoint：历史入口列出交互日志关联的
最近 20 份快照，并允许按已知 ID 读取；raw-only 且从未交互的旧快照不能凭列表自动发现。
访问日志按现有分页上限读取，超限显示不完整。比较只报告可观察快照差异，
没有伪造 G3 重访评分、跨身份连续性或完整语义更正统计。真实反馈尚未用于 G3 历史评分。
正式资格、完整历史索引和最终 G4 全链验收留给后续明确授权工作。

## 验证与工件

运行目录：`.tmp/evals/g3/g4-pr5-20261104-002/`。命令的 argv/cwd/env、时间、退出码、
log SHA 和 JUnit 均保存在各收据；精确源码与最终工件 SHA 见本目录 `PR5_BASELINE.json`。

| 验证 | 结果 |
|---|---|
| TypeScript / Vite build | PASS |
| 前端策略/API/绑定/并发测试 | 10 passed |
| Edge + Playwright 浏览器定向测试 | PASS，15 组检查，无 pageerror / 静态资源错误 |
| PR4 关闭交接、复审修复、发布 race、API 回归 | 42 passed，1 条既有弃用 warning |
| `python -m pytest -q`，项目内 basetemp | 1753 passed / 1 skipped / 1 warning，1032.39 秒 |
| `python -m ruff check backend tests evals`（另含 PR5 工具） | PASS |
| `python evals/run_baseline.py` | PASS，仅 lexical seed sanity |
| 当前 PR4 Schema 与生成 TS 检查 | PASS，20 份原 Schema 保持一致 |

浏览器包括：隔离 SQLite 的实际 API 保存偏好/生成/证据不足；raw/hold/synthetic；
真实 IntersectionObserver 的屏外 0 / 视口确认 1；详情成功/失败与预取；
快照阅读不请求当前 reading API；反馈 pending、响应丢失、同 key 重试、dismiss/retract；
断网保留旧快照；预算与显式取消；版本冲突；历史修订、更正/撤回及含 emoji 的旧引用；
100 候选、Radar/truncated/excluded、长内容、权限拒绝、390px 无横向溢出；
旧资讯库/阅读器/GoalWorkspace/日程/检查历史导航与键盘焦点恢复。

截图只含工程构造材料，位于本地运行目录的 `browser/`：
`raw-desktop.png`、`qualified-http-mock.png`、`narrow-http-mock.png`、
`historical-evidence-http-mock.png`。已打开核查布局；不含真实用户数据。

首轮受沙箱 Windows socketpair 限制，进程停在 asyncio 初始化，已终止并保留日志；
002 轮在允许本机回环的环境运行。浏览器首轮 offscreen 测试假设 900px 下首卡不可见，
但实际已进入视口，故断言失败；已改为 600px 并验证实际几何位置后再断言 0，
后续全部通过。清理隔离服务时发现夹具缺少 favicon 导致静态请求 500，已补齐夹具，
并在最终浏览器检查增加非 API 静态资源错误断言；产品图标文件未变。
中间失败与收据保留，不改写为成功。前端测试使用现有 Node 24 的
experimental transform-types，未安装新依赖。普通全套 pytest 不替代冻结 G3 控制面再验收。

## 定向测试复跑

前端目录运行 `npm.cmd test` 和 `npm.cmd run build`。浏览器测试复用已安装的
Playwright / Edge，不自动安装或下载。选择新的 `.tmp` 目录后，在项目根目录运行：

```powershell
.venv/Scripts/python.exe -m audit.g4.pr5.browser_fixture --out .tmp/g4-pr5-rerun
.venv/Scripts/python.exe -m audit.g4.pr5.browser_fixture --out .tmp/g4-pr5-rerun --serve --port 8135
```

在另一个终端设置 `$env:CFAW_PR5_OUT='.tmp/g4-pr5-rerun'` 后执行：

```powershell
node audit/g4/pr5/browser_tests.cjs C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules
```

服务仅绑定本机端口，关闭时用 Ctrl+C；换目录或端口时同步设置 `CFAW_PR5_OUT` /
`CFAW_PR5_URL`。若环境阻断 Windows socketpair，需要允许隔离测试的本机回环。
Schema/TS 检查与其他实际命令见封存收据；不得把普通 UI mock 改成生产数据源。

## 待审查与范围

PR5 独立审查和所有者批准：PENDING；PR4 shutdown 独立复审仍 PENDING。
建议审查重点为资格门、hold 字段边界、历史引用绑定、视口/opened 时机、
未知提交结果的重试、历史列表限制与回访措辞。工程测试不证明独立研究或用户价值。

没有 commit/push/merge、部署或生产数据库操作，没有系统/邮件 push、自动订阅、
外部自主行动、真实新闻抓取或模型调用。没有修改旧 G2/G3 评分/冻结资产或旧审查结论。
生成 dist、测试 DB、日志和截图均在忽略目录内。根 `/dev-diaries/` 规则保留，
该目录未暂存、提交或上传。完成本报告后停止，等待审查，不启动 PR6。
