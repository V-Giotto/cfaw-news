# G4-PR2 实施报告：版本化资料账本与显式本地 DB 迁移

日期：2026-11-02。分支 main，HEAD
2655f10cf20c647bdbfd1b69a000847471b2c5a3。当前均为本地候选改动，未提交/推送。

状态：**PASS，仅限 PR2 本地工程自验收，等待独立审查。**
完整旧仓回归、JUnit、节点库存、注册控制记录与封存核验均通过，最终证据在
BASELINE.json。没有签发独立审查 PASS、真实用户库迁移批准或 PR3/Beta 授权。

## 准入与授权

先检查了 git status --short、branch --show-current、rev-parse HEAD 和 AGENTS.md。
初始工作区包含未跟踪的 PR1/计划文件，tracked 无修改；本轮唯一 tracked 修改是
backend/cfaw_news/ingestion.py，其余为新增 PR2 文件。947 项入口文件 SHA 已保存。

PR1 原实施/修复/交付记录尚为历史 pending，未改写。进一步只读查阅聊天
“审查 G4-PR1 只读范围”，找到修复后的独立 AI 复审：PR1 范围 PASS，原 P1/P2/P2
关闭、未关闭/新增 findings 均为 0。该来源和原文见 UPSTREAM_REVIEW.json；本轮
复核 41 项 PR1 交付文件 SHA 及 9 份复审命令日志 SHA。它们是历史运行记录，
不是 PR2 新测试。当前用户明确要求实施 PR2，形成下一 PR 的授权。
G3 整体旧管理员状态不重写；本轮未授权 PR3 或 Beta。

文件方案与数据库风险已在实施前陈列，归档见 PLAN_AND_RISKS.md。
实施决定和操作方法见 docs/adr/G4_DOCUMENT_LEDGER_V1.md。

## 最终实现

1. 新增独立 G4Base 与 7 张专用表；legacy Base/Database.create 不隐式迁移。
   已有数据库必须显式维护并提供新备份路径，部分 Schema/source pin/实际 DDL
   不匹配均拒绝，不能重写旧 pin 强行接受。现有库未迁移时，旧抓取继续正常运行。
2. NewsIngestor 确认 read/parse 成功后，以一个事务保存不可变 G4DocumentVersion、
   Article/ArticleReading 和成功 SourceState。事务失败回滚成功证据，错误观察另行
   原子记录。抓取入口、HTTPS/允许域名、采集范围和模型权限没有扩张。
3. 稳定 document_id 绑定 source+canonical URL；新版本绑定不可变前驱、完整内容/
   策略 SHA、真实观察/入账时间。重复当前内容幂等，A→B→A 新增第三版；乱序、
   相同时间不同内容和分叉拒绝。SQLite 写保留锁、唯一/FK/SQL 触发器及完整链检查
   共同保护版本；版本/policy/receipt/coverage/service event 禁止 UPDATE/DELETE。
4. unknown/metadata_only G4 内容只保留来源标签、安全 URL/时间/标识/哈希，不存
   publisher 标题、摘要或正文。明确正文使用必须绑定独立本地 rights policy、受控
   evidence URI 和总字符额度；不读取 _reading/ArticleReading 作为 G4 正文。
   空 registry 不声明任何真实来源许可。旧缓存和旧阅读页面不属于本 PR 清理范围。
5. coverage 严格区分 partial/covered/failed/unknown/service_offline。成功 bounded
   parse 只记 partial 点，有锚定 304 只记 covered 点；点之间未知，不补连续覆盖。
   旧 ETag 不建立新账本正文。干净停机→重启记 service_offline；不干净重启记 unknown。
6. upgrade/backfill/backup/rollback/restore 显式 CLI，备份通过 SQLite API 包含 WAL；
   rollback 先全库备份，再只删 G4 表；restore 要求外部 SHA，只恢复新路径。
   backfill 只用安全 metadata，observed/available 为迁移当时，provenance 标 legacy；
   不导入当前正文到过去，不生成 RSS 成功 receipt/covered。坏 metadata 计 skipped，
   文档 savepoint 回滚，旧行原样保留。

## 本轮真实验证

工件根目录：.tmp/evals/g3/g4-pr2-20261102-001/。
每个完成命令记录 argv、cwd、环境、起止 UTC、退出码、耗时、日志 SHA；
维护 CLI 的子命令另保留 argv、退出码、receipt、备份/恢复 SHA。

| 检查 | 本轮结果 | 状态 |
|---|---|---|
| 最终 G4 集合 | 124 passed、1 warning；PR1 81 + PR2 43，无 skip | PASS |
| 新/旧库、重复迁移、WAL 备份、恢复/回滚、坏 metadata | 定向真实 SQLite 文件测试通过 | PASS |
| 真实 parser→写入点，模拟响应/304/更正/失败 | 无真实 DNS/HTTP，版本/coverage/事务检查通过 | PASS |
| 迁移后的旧 API、资讯库、Run、显式幂等批准、日程、重启 | TestClient 与 baseline provider 验证通过 | PASS |
| 独立维护 CLI | upgrade/backfill/rollback/restore 均 exit 0；恢复前后旧表/G4 账本摘要一致 | PASS |
| Ruff、PR1 Schema、PR2 三个 Schema、lexical baseline、离线前端 build | 完成命令均 exit 0 | PASS |
| 注册完整旧仓回归/1754 节点与控制记录 | 1753 passed、1 skipped、1 warning；JUnit/节点库存/控制记录核验通过 | PASS |
| 实际用户库迁移、真实采集/许可验证、UI/浏览器、远程 CI | 本轮未运行 | NOT_EVALUATED |
| 实时 G2/G3 生成与生产简报 | 本 PR 不实现，原 runtime adapter 仍未注册 | BLOCKED / OUT_OF_SCOPE |

完整旧仓含 G3 与事实签名测试，不把其中子集再次加算为独立测试。
pytest 实测 876.23 秒，含控制面和启动的命令耗时 881.206 秒。唯一 skip 仍为
Windows symlink 权限 1314；警告为既有 Starlette/httpx TestClient 弃用提示。
P1/P2 修复轮的 81/630/1753 和独立复审的 81/59 仅作上游记录。
本轮测试全为 authored synthetic/mock/AI development 工程验证，不是真人研究或
真实来源/许可泛化、模型能力、算法优势、生产就绪证明。

## 失败和中断保留

- 初次入口 hash 命令 exit 1：Git 非 ASCII 路径带引号；改用 ls-files -z，成功
  完成入口快照后才改 backend，不将首次失败称为通过。
- capture-01 在受限 Windows 环境 20 个进度点后停止；tool session exit 1，未取得
  pytest 最终退出码/JUnit。只记录 ABORTED，不宣称测试通过。没有该轮堆栈，
  既有 asyncio 本机回环问题仅为推测；允许测试本机回环后同范围通过。
- ruff-01 exit 1（两个未用导入）、ruff-03 exit 1（新增 import 排序）；修复后
  ruff-release exit 0。失败原日志保留。
- pr2-02 为 36 passed；pr2-03 为 41 passed；g4-all 为 122 passed；增加迁移后
  API 后 g4-final 为 123 passed；再增加坏 metadata 负例后 g4-release 为 124 passed。
  初始 42 节点 manifest 候选保存在 .tmp，最终清单增量为 43，未改旧 PR1 manifest。

## pins 和交付

- source files SHA：cf63de315ba086f9e4197931e64c6229ccab81c0c0af7f96f1f5ba968f810dba。
- migration：001_g4_documents_v1；source SHA
  4dfdb394359fa52f65529a05f6d50bfe8f35fb05e0cd654a418cef12aee64f74。
- migration DDL SHA：a9e464f74da993a79682a6cf0f7f0cd7274443f03565c79ea9e82ae5adca0fca。
- Schema/config/版本/receipt/备份/恢复 pins 的精确路径和 hash 见 BASELINE.json。
  最终验证前记录 final-source-before.json，封存时逐项比对，不能拿旧输出换 pin。

最终保全核验：入口 947 项中仅 ingestion.py 为本轮授权改动，其余 946 项原样；
PR1 修复交付清单 41 项全部原样。原 G1/G2/G3、旧测试/Schema/CI、前端源文件、
旧报告及 /dev-diaries/ 根忽略规则未变。release manifest 另绑定本轮文档和最终日志。

## 剩余边界与交接

- 本轮只写隔离 .tmp 测试库；未实际升级、回填、恢复或回滚用户库。
- source registry 初始无许可；真实来源许可真实性仍需管理员证据。没有新 G4 展示 API；
  后续展示须遵守 retention，不能从旧缓存补正文。
- PR3 仍须严格构造原生 G2/G3 输入、资格/时序/完整链、跨请求 registry 和续接；
  content_sha256 是 G4 存储摘要，不冒充 native 正文 hash 或 accepted pin。
- 同库 hash 不能检测整库回退；恢复到新路径也不恢复外部效果。后续历史服务必须
  明确 restore epoch/库外可信检查点或管理员接受的检测边界。服务生命周期限单进程。
- 没有 Git 写入、前端改动、真实网络/模型调用、dev-diaries 读取/上传；旧冻结工件
  和旧报告保留。完成本 PR 后停止，等待独立审查，不自动进入 PR3。
