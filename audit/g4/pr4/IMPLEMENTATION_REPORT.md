# G4-PR4 实施报告

2026-11-02；**PASS：本地工程实施与自测范围；独立审查 PENDING**。
真实 Focus/Radar 资格仍 BLOCKED；真实交互尚未接入 G3 历史评分。本报告不作为管理员
验收、线上部署、新闻语义/许可真实性或用户价值证明。完成后停止，不启动 PR5。

## 入口、授权与上游

本轮核对 main@783f5428671457ea3f1f654b160152f653d2e9e0。初始工作区已有未提交的
PR3 实现/修复，保存 1025 个入口文件 SHA 于
.tmp/evals/g3/g4-pr4-20261102-001/entry.json。用户本轮明确要求实施 PR4，未包含
本次提交、推送、部署或真实用户库维护授权。

PR3 旧文件仍写 pending；没有修改这些历史状态。通过连接的 Codex read_thread 读取
独立复审 turn 01a19c47-e6cd-7822-9d0d-252b9f65db45 的正式 PASS，并核对其 46 个
发布文件及 25 份收据，在 audit/g4/pr3/RE_REVIEW.md 追加关闭记录。其 237 passed
是**历史复审运行**，不是本轮测试。以下 293 / 1753 结果均有本轮新命令、时间和日志。

先读 AGENTS、G4 计划/ADR/上游修复及旧 main/service/database，提交了
PLAN_AND_RISKS.md 文件/测试矩阵后实现。旧取消、事务、单用户边界的审计见该文件。

## 实施文件与行为

| 文件 | 完成内容 |
|---|---|
| backend/cfaw_news/intelligence/persistence_models.py | 十张独立 intelligence_ 表；不注册进旧 Base、不改 PR2 metadata |
| migrations/002_g4_briefings.py；persistence_migrate.py | 显式升级、备份、回滚、恢复/接管 epoch；严格路径与 receipt；DDL 源码/Schema pin |
| checkpoint.py；history_store.py | SQLite append/head 原子提交、行与完整链验证、expected-head/epoch CAS、独立 checkpoint intent 恢复、幂等记录 |
| persistence_contracts.py；publication.py | 严格版本化 HTTP 契约、原生结果投影和发布资格；完整 Archive/coverage/预算诊断 |
| service.py | SQLite run 生命周期、单 worker owner、受控 native 线程、取消/限时/重启、发布事务与旧快照保全 |
| boundary.py；routes.py | 独立 /api/intelligence、loopback/Host/Origin/JSON/大小/并发限制、ETag 与严格错误 |
| backend/cfaw_news/main.py、config.py | 默认关闭的新服务挂载与本地配置；旧 Origin 白名单不扩大 |
| intelligence/runtime.py | from_ledger 增加显式 record_origin/provenance 参数，默认真实；未改算法和资格门槛 |
| persistence_schema.py；evals/intelligence_g4/schema/pr4/ | 18 份模型/OpenAPI/Version 工件及无 DB 写入的显式导出/check |
| evals/intelligence_g4/tests/persistence_support.py、test_history_db.py、test_persistence_migration.py、test_intelligence_api.py、test_publication_races.py、test_persistence_boundaries.py | 隔离 mock/SQLite 支撑与 56 个新增必需节点 |
| docs/adr/G4_PERSISTENCE_V1.md；本目录 | 协议、时序、迁移/恢复、安全边界、生成 DDL、命令/工件 pin |

相对于入口，既有文件只改变 main.py/config.py/runtime.py；源前像与 SHA 保存于
本轮 source-before/。G1–G3 算法、历史验收数据/Schema/manifest、旧 database.py/
service.py、React、CI、根测试控制面和 /dev-diaries/ ignore 保持入口字节。
git diff --stat 只列 tracked 的 main/config，PR3/PR4 新文件仍 untracked，不能据此
漏看实现。未进行任何 Git 写操作，暂存区为空。

## 数据库与任务语义

数据库存储与 G3 synthetic JSONL 无关。快照、delivery、Archive、Persona 和交互
append-only；run 版本单调，终态不可重写。journal 绑定前驱/行 SHA/指针状态；entry、
head 和业务行同一事务提交。独立 checkpoint 的 intent→DB commit→finalize 协议只
恢复精确 before/after，断链/物化行损坏/独立 anchor 不匹配失败关闭。

提交后 finalize/receipt 失败明确区分 committed/unknown；相同幂等键可查询重试。
DB 与外部 anchor 同时回退不能检测，不宣称跨文件 ACID、防本机管理员或硬件断电保证。
首次迁移失败若留下 anchor，安全阻断并需维护者检查，不能自动删除历史 checkpoint。

迁移 002_g4_briefings_v1 使用独立 metadata；已有库先备份，rollback 仅移除 PR4 表。
旧 Article/Reader 不回填证据。restore 只写新路径，要求备份 SHA 与显式历史回退确认，
生成新 epoch 拒绝旧客户端。副本提交后再次核验备份存在和 SHA；sidecar、anchor、
manifest、receipt 与 DB 的路径冲突在变更前拒绝。默认关闭，不在应用启动迁移此表。

run 仅在完整 native 校验、输入/config/fact pin、Persona/账本/来源/版本/head 检查以及
事务成功时更新 latest。取消先提交终态；发布前和提交前复查 Control。timeout 后的
迟到线程结果无法发布。重启将遗留任务标为 interrupted，不自动补发。无证据、来源
中断、stale、磁盘失败与取消保留旧快照；已发布与取消竞争以事务提交为线性化点。

CAS 是整个 stream head：运行中追加交互也可能导致该次发布 stale，不自动 rebase。
客户端先确认观察，再请求生成；冲突后取新 head/epoch 并以新键重试。默认单 worker，
上限/历史容量见 ADR，达到限制显式拒绝，不删除链中记录。

included 与 delivery 发布同事务；GET 不写曝光。rendered 仅接受 viewport_visible
且目标为 delivery；opened 仅接受 detail_opened；ack/dismiss/retract 必须 explicit_user。
同键重试、不同键重复确认/双击有请求表/观察唯一约束和语义去重。撤回追加行，不改
过去；按 available_at/as_of 查询，客户端时间不能倒填。opened/ack 均不等于 learned，
预计阅读时间明确为 uncalibrated_estimate_not_behavior。

## API 与 Schema

前缀 /api/intelligence：GET status；POST/GET persona；GET persona/versions；
POST briefings；GET briefings/latest、briefings/{id}；GET runs/{id}、POST
runs/{id}/cancel；GET events/detail、archive、coverage；POST/GET interactions。
具体路径参数/请求/响应/错误见 schema/pr4/OpenAPI.json，新增工件共 18 份。

每份快照包含 as_of/generated_at、runtime_local_v1、真实/合成模式、evidence_status、
version/ETag、完整 Archive、coverage gaps、未满足保护项与原预算 excluded/truncated
诊断；raw-only 没有 delivery。固定旧快照引用不会被替换成 latest。detail 给出受控
版本链、候选、原生主张/引用/assessment，读取正文前验证存储结果 SHA。

实际 peer/Host 必须 loopback，POST 要求显式白名单 Origin、JSON；拒绝超限、重复
关键头/query/JSON key 与额外字段。专用 CORS 允许配置的本地 Origin，GET/HEAD/POST
及 ETag；默认 64 KiB 请求体、4 在途请求、1 worker、2 活动 run、30 秒计算期限。
这些是本地单用户边界，不是 auth/多租户隔离，不宜暴露到公网。

## 本轮真实验证

统一工件目录：.tmp/evals/g3/g4-pr4-20261102-001/。run_checks 为每条命令保留完整
argv/cwd/环境、起止 UTC、退出码、原始日志及 SHA。BASELINE.json 收录全部封存前收据；
RELEASE_MANIFEST.json 额外绑定封存命令、报告和工件。不把旧日志重标为本轮执行。

下表 argv 省略公共解释器 .venv/Scripts/python.exe 与 wrapper 前缀
`-m audit.g4.pr1.run_checks --out .tmp/evals/g3/g4-pr4-20261102-001 --name NAME --`；
完整 argv 以 *.command.json 为准，原 pytest 插件发现控制和旧必需节点清单均未修改。

| 本轮命令/收据名 | 结果 |
|---|---|
| g4-seal：python -m pytest -q evals/intelligence_g4 --basetemp=.tmp/evals/g3/g4-pr4-seal-temp-20261102-001 --junitxml=.tmp/evals/g3/g4-pr4-20261102-001/g4-seal.xml | **293 passed**，0 skipped；含旧 237 + 新 56，235.96 秒 |
| collect：python -B -m evals.intelligence_g3.pytest_runner --mode collect --inventory AREA/node_inventory.json --control-record AREA/collect.control.json | 1754 个旧必需节点，控制面验证通过 |
| full：python -B -m evals.intelligence_g3.pytest_runner --mode full --junit AREA/full.xml --basetemp .tmp/evals/g3/g4-pr4-full-temp-20261102-001 --control-record AREA/full.control.json | **1753 passed / 1 skipped**，1124.09 秒；G3 630，事实签名 59 节点 |
| ruff-seal：python -m ruff check backend tests evals audit/g4/pr4 | PASS，exit 0 |
| schema-seal：python -m cfaw_news.intelligence.persistence_schema --directory evals/intelligence_g4/schema/pr4 --scratch AREA/schema-scratch-seal --check | PASS，18 工件，未创建 DB |
| baseline：python evals/run_baseline.py | PASS，仅 seed lexical sanity，非模型/排序增益 |
| frontend-build：npm run build（cwd frontend） | PASS，React 源未改 |
| local-proof-final：python -m audit.g4.pr4.local_probe --out AREA/proof-final | PASS，43 个证据文件，三次真实 CLI upgrade/rollback/restore exit 0 |
| prepare-seal / verify-seal：python -m audit.g4.pr4.finalize [--prepare] | PASS，源码/旧资产/清单/JUnit/日志/离线 wheel 校验与 baseline 封存 |

AREA 仅为表中可读缩写，不是实际 shell 参数。full 在 14:20 UTC 完成；之后仅新增模块的
专用 CORS/checkpoint 临时文件保护及其测试有收尾修改，最终 14:33–14:37 的 g4-seal
覆盖最终运行源码。旧完整套件未在这两个收尾修改后再次重复，旧业务源码/路径未变。
两个 pytest 运行各有 1 条现有 FastAPI/Starlette httpx 弃用警告；唯一 skip 是 Windows
无 symlink 权限的既有例外。无忽略 failure、删节点或降低原门槛。

56 个新增节点覆盖：新库/旧库升级、保留旧表/零回填、备份/恢复 epoch、sidecar 与
receipt 冲突、提交前后实际子进程 os._exit、磁盘/anchor 故障、两 store 并发 CAS、断链/
物化/正文损坏、时钟回退、临时文件别名保护；重复 POST/确认/撤回、旧引用、GET 无
曝光、副本重启、取消 race、超时不 late publish、来源/Persona/账本变更；远端伪造
Host/Origin、JSON/query/body/并发界限、禁用及未迁移状态、局部 CORS。
旧完整套件覆盖 Goals/Runs/Decisions/Schedules、NewsLibrary 后端相关 API、PR2 与
G1–G3 回归；没有新增浏览器 E2E，不将 build 当 UI 行为验证。

测试也在仓库外 cwd 离线安装 core/native wheel，验证缺失或被篡改的 native 依赖拒绝；
最终 core wheel 每个后端源码文件与当前 source pin 一致。工程 mock 不证明线上新闻。

失败迭代原样保留：history-01（容量 fixture 用错流）、api-01（config 摘要序列化）、
api-02（详情字段/无证据状态）、api-03（正常轮询锁争用）、races-01（Windows 原子替换
短暂拒绝）。每项 exit 1，修复后由后续用例覆盖。Windows 替换重试有上限且检查文件
身份；最新临时文件冲突保护确保不删除不属于本次写入的文件。

发布清单首次封存的命令 exit 0，但独立尾检发现它收录了仍在写入的自身日志，造成
一个日志 SHA 不匹配。该清单保存在 AREA/release-manifest-attempt-01.json；最终
release-seal-final 排除正在写入的日志，并在完成后逐项重新计算全部文件 pin。此为
封存工件修复，不重标测试结果，也不隐藏原命令与日志。

## Pins 与可回放证据

| 工件 | SHA-256 |
|---|---|
| 75 个源码/测试/契约工件集合 | 21bbd83d61ec5dd092c221f7203380ae2b19f6f0753090b2108e08bac80f1826 |
| migration source | 2987a61f13e0eab91c0779324f8c8f5173a8d6f36ba75ec1188047a252fd6ee3 |
| SQLite Schema | db8064532420c2a672c9013a1ee3f4a19da7c6b4484b425834cb8a2175937bc1 |
| fact_signature v2 policy | 70565148fe436fa823ef6a4063cbba7abb4c994cc34f19dc44bdc2451e367450 |
| runtime ranking policy | 696e984bfd3fc0638f925de0a2cf3bc5eb11ba34a31c3fd109f99f3c58e34243 |
| intelligence 默认配置 | e14b2a151f238e55791fb3adbf38c2415645f790d805c25e8b57e7f55ba717c4 |
| mock API 完整 runtime input | a70515cb48a34c24b924aa34f6a3e21190ca20c9be89d42bc09c1f6bf9fcb0a5 |
| mock API 完整 runtime output | a98cd3777880241361c477eb9cdd2d2f81d3f2c6bef8b18cecec3961805eaabf |
| proof-final/proof.json | 60775e278bba7e837e395a40dd54cec2f8eb5e5891116bea1806f2ea8194a03d |

SQLite 3.53.1 / SQLAlchemy 2.1.4。本轮 migration/restore 的执行 argv/退出码/receipt/
stdout/stderr，API 请求响应、完整运行输入输出和 stages/N.json 存于 proof-final/，
与 SQLite 存储 SHA 及 native trace 文件 pin 相符。API 走读：raw_news_only，Archive=1、
delivery=0，secondary_material/unverified 保留，GET 未写 interaction，显式 opened
只写事实且 learned=false。所有材料为 AI-authored RSS mock/测试许可/模拟时钟。

## 结论与待审边界

- **PASS**：本地 SQLite 历史、严格 API、任务/取消/事务发布、迁移恢复与上述工程测试。
- **FAIL**：最终必需测试无失败；早期失败迭代未删除，不能作为 PASS 证据。
- **BLOCKED/未实现**：真实 Focus/Radar、历史 Persona 连续重放、真实交互驱动 G3 历史
  评分/精确 revisit；长期自动归档、跨请求 registry/rebase、多用户认证与云部署。
- **PENDING**：独立审查与管理员接受本 PR；未请求或执行 PR5。

没有真实网络采集、外部模型/付费 API、真实用户 DB 写入、React 修改、通知或第三方
操作；没有读取 dev-diaries/，其 ignore 规则未变；没有 commit/push。所有实现停在
可独立审查的本地工作区。
