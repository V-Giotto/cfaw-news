# G4-PR3 文件与验证矩阵

2026-11-02；实施入口 `main@783f5428671457ea3f1f654b160152f653d2e9e0`，入口工作树为空。
当前用户消息明确授权 PR3；未授权下一 PR、Git 写操作、发布或部署。
本表记录本轮实施范围；前期命令、失败与修复后执行分别保存在本轮工件目录，
不能用本表或旧 PR 报告代替实际测试。

| 新增文件 | 目的 | 本轮验证 |
|---|---|---|
| backend/cfaw_news/intelligence/native.py、native_lock.py | 固定原生源码依赖与运行配置 | 127 个原生 Python 文件及 retrieval 摘要；离线安装后篡改拒绝 |
| runtime_contracts.py、runtime_schema.py；evals/intelligence_g4/schema/pr3/*.json | 新 runtime/config/ranking/plan/result 严格版本边界 | Schema 导出/逐字节检查、直接 JSON 篡改/旧 pin/混源拒绝 |
| g2_adapter.py | PR2 账本完整前缀到正式 G2 纯阶段 | 完整链/来源/许可/时序/引用/候选池、多源同事件 |
| g3_adapter.py | 新受控封套调用冻结特征、历史与预算内核 | B4/P1 与正式 rank_revisit 全行字段对照；预算全字段对照；疑义输入拒绝计划 |
| runtime.py | 有界本地计算、只读 SQL 导出、可重放 CLI | 真实 PR2 隔离库、as_of、取消/超时、失败无结果、exact-byte 文件 pin |
| scripts/build_g4_native.py | 不改冻结 pyproject 的显式 runtime wheel 构建配置 | 两个 wheel 离线 --target 安装；仓库外运行；源码篡改拒绝 |
| evals/intelligence_g4/tests/runtime_support.py、test_runtime_{bridge,identity,equivalence,ledger,cli}.py、test_offline_install.py | 合成开发及真实形状 mock 测试 | 无联网/模型；合成和真实模式隔离；旧 wrapper 仅在对照测试使用 |
| docs/adr/G4_RUNTIME_BRIDGE_V1.md；audit/g4/pr3/ | 增量 ADR、源码/Schema/测试/产物 pin、报告 | 全部入口跟踪文件不变；旧 runner/基线/build/Ruff |

上游证据：`audit/g4/pr2/RE_REVIEW.md` 记录 PR2 独立 AI 复审 PASS 与两个路径缺陷关闭；
`audit/g4/pr2/REVIEW_FIXES.md` 保留修复细节。它们是历史记录。本轮另跑 PR1/PR2 测试。
G3 事实签名使用 v2 及其实际 policy SHA，不依据提交信息推定全能力通过。

数据库边界：只读 session 导出既有 G4 专用表；SQLite BEGIN 建立一致快照，不提交写入。
测试仅创建 `.tmp/evals/g3/` 下的隔离数据库。无迁移修改、无 Article/ArticleReading
回填、无生产 history/delivery、更无真实用户数据库操作。

不能复用的边界：G3ReplayInput 的 accepted_g2 是封存的离线证明；HistoryInput 的
synthetic journal 不是生产记录。新 runtime 不生成这两种旧封套，不伪造 parent/trace
验收身份。真实来源独立支持当前由冻结 G2 明确标为 unknown，实际产品计划安全降级。
