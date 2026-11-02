# G4-PR2 独立复审关闭记录

2026-11-02。复审基点 main@2655f10cf20c647bdbfd1b69a000847471b2c5a3。

结论：**PASS，仅限 G4-PR2 本地工程范围**。原 P1（SQLite sidecar 备份冲突）和
P2（提交后才首次创建 receipt）均已独立复验关闭；当前新增/未关闭 P0/P1/P2/P3 均为 0。
这是独立 AI 只读工程审查，不是真人研究验证。

来源：聊天“审查 G4-PR1 只读范围”中的最新 PR2 复审，turn
01a19b2e-e7b9-7593-ae1c-fdbea80024b3。发布前通过 read_thread 重新读取最终结论，
并复核本地日志、JUnit、命令记录与独立探针。原 pending 报告及 release 保留原字节，
本文件追加记录后续关闭状态，不改写原来的时间线。

| 独立复审实际验证 | 结果 |
|---|---|
| G4 完整集合 | 164 passed、0 skipped、1 既有第三方警告 |
| 旧 ingestion/reading/workflow/following | 64 passed、0 skipped、1 既有第三方警告 |
| DELETE/WAL 保留 journal 备份路径 | 操作前拒绝，退出 1，数据库逻辑内容不变 |
| 正常 rollback/restore | 备份提交后存在，SHA/manifest 一致，恢复后逻辑数据与原库一致 |
| receipt=db | 退出 1，not_started，未创建数据库 |
| 提交后 receipt 写入/替换故障注入 | 退出 2，COMMITTED_RECEIPT_FAILED，保留 PREPARED |
| Ruff、PR1/PR2 Schema、修复清单/测试源码/历史工件保全 | 通过 |

本地复审工件位于 .tmp/evals/g3/g4-pr2-rereview-20261102-001/：g4.log、g4.xml、
legacy.log、legacy.xml、两份 command.json 与 independent-probes.json。
这些原始大工件留在忽略目录；公开摘要不包含用户数据库、密钥或开发日记。

本次没有重新运行全仓 1753 或完整 G3 630，亦没有操作真实用户库、进行真实采集、
许可研究或真实断电测试。上述旧全仓/G3 结果仍是历史记录。
PASS 不批准真实用户库迁移、PR3、Beta 或生产部署。用户随后明确授权将当前改动
提交并推送到 V-Giotto/cfaw-news；发布授权与实施下一 PR 的授权分别记录。
