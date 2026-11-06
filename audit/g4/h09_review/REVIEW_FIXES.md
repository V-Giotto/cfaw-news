# H09 复审修复：离线 SQLite 输入保全与精确重试

2026-11-06。实现方本地修复/复验，等待独立复审；不批准 Beta、不进入 G5。基点 main@d82b169d72bc10bf669b51aa149ff20ce928fb47 加既有未提交 PR5/PR6/H09 工作树。只修复本轮两项 P2、保存证据并重新登记唯一获准测试变化；未改排名/预算算法或生产数据库。

工件根 RUN：`.tmp/evals/g3/g4-h09-review-fix-20261106-001/`。当前封存为 `audit/G4_H09_REVIEW_FIX_MANIFEST.json`，不覆盖两份历史 seal 或旧索引。所有实际命令、cwd、控制环境、UTC 时间、耗时、退出码和日志 SHA 见 RUN/*.command.json。

## P2：旧封存输入留下 SQLite 侧文件

实际核对发现旧 restore-proof-final 比其索引多出 backup.db-wal（0 字节）和 backup.db-shm（32768 字节）；七个原登记文件、原索引和 seal 的 hash 均匹配。用原 verifier 对该原引用目录实际复现 inventory mismatch，记录为 FAIL_REPRODUCED，不称为旧树 PASS。创建/修改时间与旧 replay 窗口一致；新建 WAL 模式离线输入的红测试也复现 mode=ro 可产生侧文件的机制，没有声称当时曾捕获完整 I/O 轨迹。

处置顺序：先保存完整字节、SHA、大小、创建/修改时间及原索引/七文件证明，再只将精确命名的两份未登记侧文件移到 RUN/quarantined-sidecars/。RUN/sidecar-evidence/ 另留原字节副本；未删除证据、未打开原备份、未改备份正文或原索引。路径先解析并限定到旧 QA 目录和新的隔离目录，非递归移动。capture/disposition 收据完整保留此次目录差异及恢复过程，不能说目录从未改变。

修复：`sqlite_input.py` 对已停止写入的离线输入校验主文件 pin，复制到新临时目录，复核副本和源 pin，然后才允许 SQLite 打开副本。非空 WAL/rollback journal 不能由主文件 pin 认证，显式拒绝 G4_BACKUP_NOT_SELF_CONTAINED，避免静默丢失未认证事务；空 WAL/SHM 不打开、不复制、不擅自清理。临时目录包含 SQLite 可能创建的所有侧文件，连接关闭后清理。原 live database 的 WAL 一致性 backup_locked 路径不变。

`migrate.restore()` 仅从隔离副本执行 integrity_check/backup，仍拒绝已有目标、错误 pin、路径冲突和坏输入；无原地恢复。`legacy_replay.py` 先把核对后的旧 QA 备份字节复制到其新输出 input/，再恢复到新数据库/epoch，比较旧输入目录全部文件的清单/hash/修改时间。`proof.readonly()` 同样用隔离副本并显式关闭连接。`protected()` 新增对旧 seal index_roots 的实际递归验证，不再只凭 seal JSON SHA 推出旧树保全；其旧测试来源 profile 不自动接受当前修订。

本轮对旧 PR6 v2 全树重新验证：7927 目录、60097 文件、40 份业务 manifest，全部引用通过。旧 H09 包：14828 目录、115347 文件、39 份业务 manifest，同样通过。旧 seal SHA 分别保持 a1f406a4…876b、851cb201…6918，详见 prior-tree-verification.json。旧声明“seal 及其封存树不改写”撤回并在当前 REPAIR_REPORT.md 更正；原 source-snapshot 中的历史声明不改写。

实际修复后恢复重放：旧 QA Persona v4/420 完成 native；保存 v5/180 后再次完成，原材料/观察时间/事件身份保持。input-preservation.json 的 before/after 相同，原备份 SHA 和输入目录文件清单/hash/修改时间均不变。实际结果仍 raw_news_only/hold，没有伪造 Focus/Radar 正例。

## P2：分钟边界上的“精确重试”

`tests/test_workflow.py` 仅增加一次 approval_payload = interval(run)，首次批准和两次重启后的重试都复用它。业务批准/幂等/冲突判断不变，原节点及断言不删、不跳过。

新边界回归执行原测试函数，首次计算时间固定在 xx:xx:59.999999，首个批准成功后推进 2 微秒；记录实际 HTTP payload，断言三次完全一致且 interval 仅调用一次。旧实现真实失败为 409，新实现通过。这证明不稳定性机制；此前 full.xml 的那一次失败没有第二份 payload，跨分钟解释仍是推断，不升级为已证实历史根因。原失败 JUnit、日志和数据库保持原字节。

## 明确的新测试控制面

旧 G3 registry 固定包含 tests/test_workflow.py 的旧 hash；直接原 profile 现在会拒绝这项获准变更。本轮保留其实际拒绝收据 original-profile-refusal.*，不记 PASS、不改旧 manifest、G3 代码、旧 pins 或历史验收。

新 profile 名称为 g4-exact-retry-amendment-v1，登记在 TEST_AMENDMENT.json（SHA 852acf44ca74dfdd90559f8c633d6f8685c3ab211c75e847455eeb80a487df35）。test_control.py 是明确的独立入口：先用原函数检查全部冻结 registry，再只为唯一获准路径登记固定 before→after hash。运行期间只在内存中安装该 required-source 登记，结束恢复；这不是未修改 G3 profile 的重验结果。所有原 1754 节点、630 G3 节点、skip 规则、插件 allowlist、argv/JUnit 校验保持，新增 G4 用例另跑。未知源、缺失/重复/伪造节点和陈旧来源仍拒绝。

新入口包裹原 runner 的真实执行，并同时保存原 runner 原始收据、amendment/adapter hash、before/after 来源和原控制快照；controls.py 逐项重验。本次完整套件保留两条 warning：既有 Starlette 弃用提示，以及显式预载 registry 导致的 pytest assertion-rewrite 提示，均未过滤或隐藏。默认旧入口/CI 不因此自动升级；当前本地使用新显式 profile，未执行或宣称 CI 通过，也未重新签发 G3 研究验收。

## 当前验证

| 检查 | 当前结果 | 工件 |
|---|---|---|
| 修复前定向回归 | 6 failed，保留真实红证据 | red.xml / red.command.json |
| 修复后恢复/分钟边界/既有迁移 | 36 passed | focused.xml |
| 完整 G4（含 11 个新增节点） | 350 passed / 1 warning，418.83 秒 | g4.xml / g4.command.json |
| 新 G4 修订 profile 完整主套件 | 1753 passed / 1 skipped / 2 warnings，1160.87 秒 | full.xml / full-control.json |
| 新 profile collection/控制面复验 | 1754 节点、630 G3；精确 argv/插件/来源/JUnit PASS | inventory.json / collect-control.json / control-verification.json |
| 原 G3 profile | 1 failed，预期拒绝，非 PASS | original-profile-refusal.xml |
| 旧 PR6 v2 / H09 引用全树 | 两者完整 PASS | prior-tree-verification.json / prior-trees.command.json |
| 隔离恢复重放与输入目录保全 | PASS，420→180 两次 native 生成 | legacy-replay/result.json、input-preservation.json |
| Ruff、seed baseline、TS/Vite、24 个 API Schema | PASS | ruff / baseline / build / schema 收据 |

最终退出码、控制面复验、目录/hash/字节数量见新 manifest 和 RUN/results.json。新封存只在当前与两份历史包的全部引用递归核验后签发，独立 QA 索引名、独占创建和业务 manifest 普通哈希规则不变。--verify-only 分支仅校验，不生成或更新工件。

本轮没有重跑浏览器（前端与 API 展示未变）；既有 27＋11 组/StrictMode 证据仍仅属于旧版本执行，不冒称本轮浏览器验收。无新网络采集，网络 smoke、真人研究、算法收益仍 not_evaluated。G1/G2/G3 包、eval 测试、数据、Schema 与评分保持；唯一获准 legacy 测试来源变化有独立 before/after 登记，不沿用“全部 813 文件仍原字节”的旧声明。

g4_development：CONDITIONAL_PENDING_REVIEW；g4_beta_utility：OFFLINE_REJECTION_PILOT_PASSED_BETA_PENDING；g4_research_optional：NOT_EVALUATED。没有访问真实用户原库，没有 commit/stage/push/merge/公网部署或提交敏感资料/dev-diaries。完成后停止，等待独立审查与所有者 Beta 决定。
