# G3 → G4 离线接口与交接清单

本交接说明约束后续设计，不授权 G4 实施。G3-PR5 仍须独立审查及所有者批准。
离线工程通过不等于生产就绪、独立真人 gold、真实来源泛化或真实用户效果。

## 必须保留的接口

1. 输入：`G3ReplayInput` (`g3-pr1-3`) 封装正式 G2 身份、事实、引用、证据、
   coverage、provenance、generation trace；必须绑定独立保存的 manifest pin。
   `HistoryInput` (`g3-pr3-input-v1`) 添加可见的追加历史与显式谱系映射。
2. 排名：`rank_revisit()` 返回 `RevisitResult`，保留所有候选和分数解释。
   B0/B1/B3/B4/P1 共享候选、as_of、Persona、历史及预算；B2 是 G2 事件池上的
   B1 身份对照。不能把 G2 合并贡献再次计为 G3 排序收益。
3. 预算：`plan_briefing()` 消费已完成排名，输出 `BriefingPlan`
   (`g3-pr4-plan-v2`, `g3-budget-v2`)。G2 candidate tier 与 G3 focus/radar
   展示 tier 分离。180/420/900 秒为未做人类阅读校准的估时预算。
4. 保留 `archive_snapshot_ids`、完整候选、未展示/截断/证据排除原因、
   `unmet_protected_event_keys`、来源区间覆盖和词法领域分母。
   unknown/partial/failed/service_offline 不表示确认没有更新。
5. PR5 的 `ScoreProjection` / `ExperimentInput` 是离线评分消融信封，
   不作为普通 `RevisitResult` 或生产接口；现有 PR2/PR3/PR4 版本未改写。

## 进入 G4 前的决定与验收

- [ ] 独立审查 PR5 代码、manifest、真实日志、JUnit、失败案例和完整 diff。
- [ ] 关闭事实签名 P1：复核 `<`/`>`、包含等号、数值/单位/单位大小写、旧
  Persona 与 acknowledged、原生 G2→G3 序列化、180 秒展示及事实不变转载对照。
  当前修复记录见 `evals/intelligence_g3/reports/FACT_SIGNATURE_REVIEW_FIX.md`；
  前一轮工程 PASS 和冻结矩阵未捕获此缺陷，不能替代本轮复审。
- [ ] 保留独立的 `g3-grounded-fact-signature-v2` 版本及 policy 工件/指纹；
  不可仅凭保留的评分权重或 wire v1 名称判断实际特征语义。旧排名工件须
  重新计算，不能修改历史结果或只更换 pin。
- [ ] 复核 PR5 审查修复：测试控制面指纹、未批准 hook 拒绝、固定三 pin 的
  端到端拒绝记录，以及真实 v2 schema 比较；历史 PASS 不能替代本轮证据。
- [ ] 核对回访指标窗口内的样本/家族与独立列出的 dataset_support；例如
  原 26 例子集的 P1 每个回访窗口 9/9、18 个相关状态/1 家族，不能报告为
  141/16；新增签名案例后的完整矩阵使用其实际窗口分母，不沿用旧总量。
- [ ] 所有者明确接受 G3 开发结果并批准 G4 的具体范围。
- [ ] 保留 B4；P1 替换需要新的稳定改善证据，当前复用开发集不能支持替换。
- [ ] 选择并注册 Focus/Radar 配置；当前 70/30 仅为冻结实验配置。
- [ ] 明确是否接受贪心分配遗漏：6 项更新最简投影可合计容纳时，先选完整投影
  仍可能少展示一项。不得宣称“只要能放下就保证全部展示”；可评估遗漏仍计分母。
- [ ] 单独设计本地持久化、身份映射升级、可信日志 head 保存、回滚与取消边界。
  当前合成追加文件日志不证明生产持久性或多用户隔离。
- [ ] 定义 included/rendered/opened/acknowledged/dismissed 的实际写入时机；
  rendered 必须由客户端确认，opened 不能转成已知；反馈更正通过追加撤销表达。
- [ ] 单独设计 API/前端适配和历史 schema 升级，保留证据与不确定性，不提高
  hold 候选可信度，不自动行动，不默认站外通知。
- [ ] 新增端到端测试：断网、取消、重复写入、旧版本输入、部分渲染、重访、
  更正/撤回、覆盖缺口、超长条目及完整 Archive 可访问性。
- [ ] 单独验证阅读估时、可理解性和主观有用性；需要研究结论时设计新的留出
  事件家族和真人研究，不能将本次非盲 AI 开发材料重命名为独立测试。

## 证据与限制

当前事实签名修复与验收见 `evals/intelligence_g3/reports/FACT_SIGNATURE_REVIEW_FIX.md`
及其外部保存的工件 pin；前次控制面修复见 `PR5_REVIEW_FIXES.md`。
`PR5_ACCEPTANCE.md` 保留为历史记录，其原 PASS 不再作为当前控制面验收依据。
复现入口见 G3 README。机器结果包括指标分子/分母、样本数、事件家族数、
undefined_reason、来源、成本/耗时、消融、预算及回访矩阵。
样本是相关的事件×案例×预算状态；两个种子不增加独立样本数。
没有未合并文档对照臂，因此 G2 合并收益不可估计。

当前没有生产 DB/API/前端接入、真实用户反馈、新采集、真实模型或付费推理。
本地 Windows 回归依赖项目内 `--basetemp` 和进程级 `PYTHONUTF8=1`；
远程 Linux CI/发布部署须单独验证。G1/G2 历史材料保持原样，本次回归不冒充
重新签发的 G1/G2 历史验收。
后续 CI 和复验须使用注册的 pytest_runner，保留显式配置、禁用自动插件加载、
批准文件/插件清单和 control 记录。修改批准控制文件或安装测试插件后必须重新
审查并生成新的检查凭据；不得复用旧 pin、修改历史输出或放宽 skip 门槛。
