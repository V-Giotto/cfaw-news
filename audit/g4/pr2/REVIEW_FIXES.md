# G4-PR2 审查修复：SQLite sidecar 与 receipt 路径

2026-11-02。main@2655f10cf20c647bdbfd1b69a000847471b2c5a3。
范围仅为用户提出的 P1/P2；无 Git 写入、实际用户库操作、网络/模型扩权或后续 PR。
状态：**本轮修复工程自验收 PASS，等待独立复审**。最终门禁、源码/配置/输出 pin
以 REVIEW_FIX_BASELINE.json 为准；没有自行签发独立复审关闭结论。
原 PR2 自验收 PASS 不能关闭本次 finding。原 BASELINE/RELEASE/报告、PR1/G1/G2/G3
和原测试清单保持原字节；本轮结果、日志和 pin 单独封存，待独立复审。

## P1：SQLite 保留路径与备份存活

统一 resolve_paths/validate_paths 用于 maintain、backup_locked、restore 和 CLI：

- 规范化绝对路径，解析 symlink/junction；已有路径用 samefile 检查 hardlink。
- 拒绝文件产物相同、互为父子、数据库/备份的 -journal/-wal/-shm 及 -mj* 保留
  命名空间，包括其下级路径；检查 backup manifest、receipt 与 .pending 暂存文件。
- Windows 另拒绝 NTFS stream、尾点/尾空格别名。数据库文件按 SQLAlchemy URL
  database 参数传递，避免把文件名字符误当连接参数；不同目录同名文件仍可正常使用。
- 所有 SQLite 入口在打开/创建数据库前拒绝冲突。CLI 可先写安全且独立的失败
  receipt，但不会在冲突路径上创建产物。restore 已存在目标仍拒绝，不覆盖原库。
- 备份完成、关闭连接并 fsync 后核验文件 SHA/manifest；维护提交、连接释放后再核验
  一次。只有备份仍存在且 SHA/manifest 一致时才返回 backup_verified_after_commit=true。
- 提交后丢失或改写备份：G4_BACKUP_POSTCOMMIT_INVALID，明确 database_state=committed，
  不返回成功。commit 抛错：G4_COMMIT_OUTCOME_UNKNOWN，状态 unknown，不承诺已回滚。

SQLite Connection context manager 只管理事务；备份/恢复已改为显式 closing，避免
Windows 文件句柄延迟释放影响后续操作。没有调整 Schema、表或持久化版本 pin。

## P2：receipt 在数据库操作前准备，提交后失败明确报告

1. 先解析并检查 receipt 和 .pending 与所有输入/产物/sidecar 的关系。
2. 独占创建两个文件，写入/读回/fsync PREPARED，再开始数据库操作；不能创建或
   刷盘时不执行数据库操作。PREPARED 的 database_state=unknown，明确不是最终结果，
   不能凭该文件推断数据库未改变。
3. 最终结果写入预留 .pending，读回/fsync 后核对两个文件身份，再原子 replace
   receipt。成功后才输出 receipt_written=true；不在提交后尝试首次创建 receipt。
4. 已提交但最终 receipt 写入/替换失败：退出 **2**，stdout 为结构化
   COMMITTED_RECEIPT_FAILED、database_state=committed、receipt_written=false；保留
   PREPARED，若暂存文件已完整则保留暂存结果供核对。未知提交结果对应
   OUTCOME_UNKNOWN_RECEIPT_FAILED。不能把失败退出解释成“数据库未改变”，也不能
   自动重试破坏性操作。操作员应保留 stdout/备份/暂存文件并核对数据库。
5. 路径或准备阶段失败：退出 1、database_state=not_started；不输出 traceback。
   合法路径下的操作失败可保存最终 FAIL receipt，状态保守记录，原文件不覆盖。

文件系统可能在提交后发生独立故障；提交与库外 receipt 不构成一个事务。本修复
通过预备记录、提交后校验和明确状态处理该边界，不承诺物理文件永不丢失。
沿用管理员停服务维护、单进程和可信本地目录边界；不声称抵抗恶意并发重命名。

## 验证与记录分层

工件：.tmp/evals/g3/g4-pr2-review-fix-20261102-001/。
完成命令均有真实 argv/cwd/环境/起止时间/退出码/日志 SHA；用户原 17 项 review JSON
保持原字节。新增测试和 required manifest 独立，不改原 PR1 的 81 项或 PR2 的 43 项。

| 运行 | 本轮实际结果 |
|---|---|
| red-paths | 34 failed，退出 1，完整 JUnit；当时观察到延迟，但最终正常结束，非中断 |
| red-bounded | 32 failed、2 deselected；仅修复前排除会延迟的 restore 负例，不作为验收集合 |
| green-paths-01 | 31 passed、3 failed；hardlink 权限、restore 检查顺序、提交故障注入 |
| green-paths-02 | 36 passed，增加了备份 SHA 改写和 commit unknown 测试 |
| green-paths-03 | 39 passed，增加 Windows stream/尾点/尾空格负例 |
| 最终 G4 集合 | 164 passed、1 warning；原 124 + 新 40 个完整节点精确匹配，0 skipped |
| 旧抓取/阅读/工作流/关注 | 64 passed、1 warning，本轮实际重跑 |
| CLI/API 探针 | DELETE/WAL 原 journal 输入均拒绝；正常 rollback 备份提交后存活并可恢复；receipt=db 新路径未创建数据库 |
| Ruff / PR1、PR2 Schema | 全部 exit 0；初次 Ruff 未用导入失败保留 |

probes-final 的 7 个真实子进程保留执行记录；两种模式分别覆盖拒绝/正常回滚/恢复，
再验证 receipt 碰撞。恢复的逻辑数据摘要与原库相同，备份/manifest/receipt SHA 可核验。
写入/原子替换失败及提交不确定性为显式故障注入，全部在自建隔离库，不是真实事故证明。

最终 G4 pytest 实测 48.45 秒，命令总耗时 50.034 秒。与入口 971 项文件对比，
仅 migrate.py 是本轮改动的既有文件；其余 970 项及用户原 17 项复现 JSON 原样保留。
新增 maintenance_io.py、测试/清单与审查工具均绑定本轮源码 SHA。DDL/source migration
pin 与原 PR2 完全相同；未升级 Schema 或改写已有 g4_migrations 行。

完整旧仓 1753、G3 630 是上轮历史运行，本次没有重跑，不能冒充修复后的全量验收。
本轮只改维护代码；抓取、业务表、冻结算法/Schema/测试及前端源文件未改。未进行浏览器、
远程 CI、真实采集、许可研究或真实用户库维护。工程自验证不等于独立复审。
