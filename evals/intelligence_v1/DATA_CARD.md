# G1-PR2 DATA CARD — pilot / developer data

日期：2026-10-20。任务是检验历史版本、引用、来源传播与标注协议，不是训练或独立测试集。
DEV-01：1 个家族、6 个 as_of、7 个文档内容版本（6 个文档身份）、8 次观察、
1 个 persona 的 2 个历史版本。所有 DEV-01 文档为 synthetic：real=0，synthetic=7。
PR1 契约样例另有 4 个 synthetic 版本、3 步，不能冒充新增试点或人工数据。

## 来源、版权与时间

Cedar Agent、媒体、测试者及 TinyBench-3 均虚构；正文是本仓库原创测试文字，
redistribution_rights=synthetic，canonical_url=synthetic://…，出处指向 DEV-01/README.md。
全部来源按 source_registry 登记：官方自述、三家共用官方上游的转载、设计为独立的
有限测试。独立性仅是合成场景的属性，不是实际来源核验结果。

既有 github-blog 条目仍为 unknown / metadata-only / checked_at=null；没有使用其正文。
本轮未抓取真实材料、未核验在线许可，不把“公开可访问”当全文再分发授权。
将来加入真实数据必须逐份提供历史内容证明、出处、权利和使用范围；缺证据只能
排除、保留合法元数据/摘录或明确采用 synthetic，不回填成真实历史。

合成 D0=2026-01-01。published_at 为场景中的发布者说法，observed_at 是模拟观察，
available_at 是允许读取该版本的最早场景时刻。它们不是实际采集日志。
JSONL 为 UTF-8/LF；content SHA 沿用 PR1 NFC/LF + 标题/摘要/段落规范，不是原网页 SHA。

## 标签、偏差与覆盖

参考事件、关系、Claim 由开发用场景设计构成，不是独立人工标签。A/B 未确认，
DEV-01 annotations/gold/adjudications 为空，语义支持准确率 not_measured。
semantic_probe 的 unsupported 只是攻击样例的预期，不算第二人结果。

样本刻意强调转载、限定测量、平台更正与旧重要信息；只覆盖一个虚构 AI 工具和
英文短文本，persona/时间点/事件关系强相关。作者知道故事目的，存在设计与选择偏差。
不能主张真实新闻覆盖、自然事件分布、算法增益、统计显著性、泛化、真实用户收益、
在线事实核验、生产可用性或持续七天监控。旧事件保留仅证明候选可见，不证明排序命中。

service_offline 是合成缺口。covered 仅指明示来源和区间，不意味着全网完整。
所有 family、转载和反事实留在 dev，不派生为独立 test 家族。

## 冻结和兼容

PR1 v3 的完整输入保存在 .local/g1-pr2/pr1-contract-v3/，且原字节可由起始 Git
43cebab0e4e291452ec4356848017d90ae9f7128 恢复。当前包使用新 pr2-dev01-v3 revision，
不是重新标记旧 v3。原三步 fixture JSONL 保持原字节；新增数据和源码重新列入 Manifest。
任何更正、标注提交或规范修订需保留旧输入并发布新 revision；不能让验证器自动修复哈希。
单人/双人提交状态由人确认，程序的结构校验不授予“真实独立”资格。
v3 只修复审查指出的关系唯一性、未决仲裁保存和有外部 Manifest pin 的 PR2 准备入口；
所有 JSONL（含空人工文件和原 gold）保持 v2 原字节。v2 完整包已先保存在本地审查证据目录。
没有业务库、ORM、HTTP/UI、依赖、旧基线或迁移资产改动；T25=N/A。

## PR3 revision 补充

当前输入为 pr3-replay-v2 / g1-pr3-1；上文 PR2 v3 和 PR3 v1 是历史冻结记录。
v2 仅修复预测入口遗漏的 split/派生隔离校验，与完整验证器共用纯元数据检查。
v1 完整包保存在 .local/evals/g1/pr3-split-review/pr3-replay-v1/；新 pin 见
reports/PR3_SPLIT_REVIEW_FIX.md。全部 JSONL（含 gold）和 Schema 字节不变。
PR2 完整包先保存在 .local/evals/g1/pr3/pr2-dev01-v3/。全部 22 个既有 JSONL、
17 份既有 Schema 和人的空记录保持原字节，统计仍为 11 个 synthetic 文档版本、
9 步，其中 DEV-01 为 7 版本/6 步。新增的排序、oracle 和事后分组诊断不增加真实样本。
DEV-01 Recall/nDCG 缺金标为 null，PR1 pending 标签不当作完成标注。
本轮只给旧 retrieval.py 添加纯评分函数，旧 search/业务契约不变；没有新依赖或业务迁移。
B3/B4、预算与七天回访仍待 PR4；人工试标、手册真人试用、独立复审和 G1-a 仍未完成。

## PR4 revision 补充（当前）

当前为 pr4-revisit-v1 / g1-pr4-1 / pr4-baselines-v1；前述 PR3 为历史记录。
PR3 v2 原包先保存在 .local/evals/g1/pr4/pr3-replay-v2/，其独立复审未发现 P0/P1；
剩余 P2 旧 pin 说明在 PR4 文档中修正。新 pin 与实际验收见 reports/PR4_ACCEPTANCE.md。

新增 REVISIT-7D：7 份合成文档版本、6 步、8 条 authored technical expectations，
一份固定 D0 投递条目及明确 inclusion 历史；不新增任何真人记录。
全部数据合计 18 个 synthetic 文档版本、15 步、3 个 dev family，分别是原契约样例、
DEV-01 与新回访故事。它们不是五条独立真实轨迹，不满足 PR5/G1-a 数据或人工门槛。
新故事日期在 2026-02，不改 DEV-01 的 D5 更正；新故事更正在 D6。
D1–D7 为七个未访问的中间日，D0→D8 实际相隔八天；回访指标明确使用末尾 1/3/7 天窗口。

现有 22 个 JSONL/gold/annotations/adjudications 保持原字节。新 expectations 与 gold
分类型、分 role、分评测模式、分报告，不以 agreed/adjudicated 伪造人的审阅。
五类反事实及未来反馈负例在同 family/dev 的隔离副本中运行，各自创建新 revision/pin。
预期由场景逻辑预先定义；不因算法分数修改期望。保留更正删除、D9 才可见测试、
来源失败以及曝光状态变化的个案证据。B2 保守漏合并独立测试可能导致重复，必须报告。

B3/B4 只是可解释的固定规则。时间代理可能把转载/轻微改写视为新鲜，新哈希可能解除
惩罚却没有实质增量；opened 不另计权重，曝光绝不等于理解。
真实语义支持、正式变化分类、标注、许可复核和泛化测量仍未完成。读时是固定代理，
不能称实测节约时间；无在线模型调用的 tokens/cost 为 0。无数据库访问或迁移，T25=N/A。
