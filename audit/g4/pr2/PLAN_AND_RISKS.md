# G4-PR2 文件方案与数据库风险

2026-11-02。基点 main@2655f10cf20c647bdbfd1b69a000847471b2c5a3。
本方案先在实施前 commentary 提交，本文保存最终限定范围；没有 Git 提交。

## 准入

- 当前用户明确要求实施 PR2。独立 AI 复审来自聊天“审查 G4-PR1 只读范围”，
  thread `01a19a2a-2b7b-75f0-8f7d-40a95bdcd803`，turn
  `01a19abe-ccc0-7432-8506-ffd33b91ef22`，结论 PR1 范围 PASS、P0/P1/P2/P3 均为 0，
  原三项 finding 关闭。原文及消息 ID 见 UPSTREAM_REVIEW.json。
- 仓库旧 PR1 报告仍写 pending；这是历史状态，保留不改。复审来源和本轮 PR2
  授权在这里追加，不伪装成旧 release 当时已批准。
- 本轮核验 PR1 修复清单 41 个文件无 SHA 差异。81/59/630/1753 是上游运行记录，
  不作为 PR2 新测试。PR2 当前运行结果单列于 IMPLEMENTATION_REPORT.md。
- PR1 真实 G3 adapter 仍未注册；本 PR 不解除该阻断，不接受 synthetic 作为真实新闻。

## 文件与测试矩阵

| 文件 | 触达及验证 |
|---|---|
| backend/cfaw_news/intelligence/contracts.py、models.py | 新增严格版本化捕获/策略/coverage 模型与独立 G4Base；哈希、时间、rights、线性前驱、SQL 不可变/唯一/FK 约束 |
| intelligence/document_store.py、source_policy.py | 事务内捕获、串行写锁、重复幂等、完整链检查、来源策略绑定、间断诊断；并发、乱序、A→B→A、未知 rights、未来时间、故障回滚 |
| intelligence/migrations/001_g4_documents.py、migrate.py | 显式 DDL、source/DDL pin、实际 Schema 校验、WAL-consistent backup、metadata-only backfill、G4-only rollback、新路径恢复 |
| intelligence/schema.py；evals/intelligence_g4/schema/pr2/ | 3 个完整模型派生 Schema；逐字节 check，不动 PR1 v1/v2 |
| data/g4_source_policies.json | 空许可 registry；未列来源统一 unknown，未替任何真实来源声明许可 |
| backend/cfaw_news/ingestion.py | 已确认抓取写入点，账本/Article/ArticleReading/成功 SourceState 同事务；未迁移时保持原业务 |
| evals/intelligence_g4/tests/test_capture.py、test_migration.py | 新测试独立轨道；保留旧测试源码/pin。包括迁移后 API、旧 Run/Approval/Schedule/NewsLibrary 数据接口回归 |
| docs/adr/G4_DOCUMENT_LEDGER_V1.md；audit/g4/pr2/ | 操作边界、实际 argv/日志/退出码、独立维护 CLI 工件、本轮 source/schema/version pins、报告 |

Database.create() 的旧 Base 无需修改；G4Base 独立，避免应用启动隐式迁移。
不触达 G1/G2/G3、前端、旧 service/main、冻结测试库存或 CI。

## 风险与控制

1. **WAL 和在线进程**：操作员先停应用。CLI 持有 BEGIN IMMEDIATE 保留写锁，
   用另一个只读连接执行 SQLite backup，包含已提交 WAL。文件直接 copy 不能替代该步骤。
   已存在数据库的维护必须给新备份路径；备份/receipt 不覆盖旧文件。
2. **DDL 中断**：所有 DDL、迁移登记在一个显式事务中，失败全部回滚；部分 Schema
   和被移除的触发器会拒绝。source/DDL pin 不匹配不自动重建或重写旧记录。
3. **并发与版本分叉**：写前加 SQLite 保留锁，校验完整链和当前 head。SQL 约束
   拒绝分叉/回退；迟到观察和同时间不同内容拒绝，不把发布时间当观察时间。
4. **历史污染**：回填只读 Article 的安全标识/来源/URL/来源报告发布时间；记录
   迁移当时 observed/available，provenance 为 legacy_cache_metadata_observed_now。
   不读取 ArticleReading，不回填旧标题、摘要或正文，不签发成功 poll/covered。
5. **许可**：未列策略只保留来源标签、规范 URL、安全时间/标识和摘要哈希；
   标题用来源标签代替，不保留 publisher title/summary/body。许可正文仅来自本次
   bounded parser payload，绑定独立本地策略和受控 rights_evidence_uri，并限制总字符数。
6. **覆盖夸大**：成功有界解析只记 partial 点；已锚定 304 只记 covered 点。
   点之间 unknown。失败记 failed，干净停机区间 service_offline，非干净重启 unknown。
   不用一次轮询证明连续覆盖；不存在观察的时期没有 covered。
7. **恢复与回滚**：rollback 先备份再删除 G4 专用表，保留旧业务表；G4 证据仅能从
   该备份恢复。restore 必须外部给定备份 SHA，只能写新路径。切换回应用由管理员执行。
   同库哈希不检测整库连 head 一起回退；后续历史续接必须明确 restore epoch/trusted checkpoint。
8. **旧缓存范围**：旧 Article/ArticleReading 行和既有阅读 UI 保持兼容；本 PR 的
   rights 限制只约束新 G4 账本及其读取内容，不能宣称已清理或重新许可全部旧缓存。

本轮所有维护仅针对 .tmp 中的自建测试库，未运行实际用户库迁移。
本 PR 不生成 G2/G3 情报、不增加网络/模型权限、不改 UI；完成后等待独立审查。
