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
