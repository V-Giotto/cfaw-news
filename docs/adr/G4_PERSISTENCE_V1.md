# G4 本地 SQLite 历史、简报 API 与生命周期 v1

2026-11-02；G4-PR4 实施决定，待独立审查。继承 G4_RUNTIME_LOCAL_V1、
G4_RUNTIME_BRIDGE_V1 及其复审修复，不替代历史验收记录。

## 范围与资格

使用真正的文件 SQLite 保存用户画像版本、run、不可变快照、Archive、delivery、
append-only interaction、请求幂等记录和 trusted head。G3 synthetic JSONL store 不作为
用户存储，也不伪造 accepted_g2 的封存身份。算法仍由已锁定 native G2/G3 执行；
runtime_local_v1、fact signature v2 与 policy SHA 校验保持不变。默认 B4，P1 必须显式
实验；70/30 等预算 profile 仍是未校准配置，保护项可能无法装入贪心预算。

真实流当前只允许 raw_news_only 的完整 Archive 快照。必须已经完成 native 校验、证据
阶段和排序，存在实际主张与候选，且各来源最新有界轮询点是 covered。该点不能证明
两次采集之间连续覆盖；区间 unknown/gaps 原样保留。没有证据、native 不接受、晚画像、
来源失败或未来输入不能发布新快照。PR3 尚不具备真实独立支持资格，真实 plan_ready
进一步被 G4_REAL_PLAN_NOT_QUALIFIED 拒绝；不得借持久化把材料提升为 Focus/Radar。

显式 synthetic_development 使用 synthetic:local 流、测试来源及 authored provenance；
真实流使用 real:local，来源和版本必须与流一致。不混排、不以 mock 证明线上许可。
生产配置应使用独立数据库分别运行真实与合成模式；每个数据库只有一个 worker owner。

交互事实已持久化；**尚未适配进 G3 历史评分**。status/briefing 返回
history_scoring=not_applied_pr3_v2。不得宣称反馈影响排序、opened 等于 learned 或已经
实现历史连续推荐。画像版本本身可按时间读取，但 PR3 缺历史 Persona 时的连续性阻断
继续生效，不以当前画像倒填过去。后续接入须另行设计真实历史与 native 的严格映射。

## 表、身份与不可变性

独立 PersistenceBase，不向旧 Base 注册。002_g4_briefings_v1 新增 intelligence_ 前缀的
installation、heads、journal、requests、personas、runs、snapshots、deliveries、archive、
interactions 十张表，不改变 PR2 七张 g4_ 表及其 Schema。旧 Article/Goal/Run/Schedule
不是这些历史表，旧缓存和 Reader 不回填过去正文。源证据仍由 PR2 immutable 账本供给。

快照 id、run id、画像版本 id 是本地 UUID；Archive/Delivery id 绑定简报与 event snapshot。
event_key/revision、native snapshot ID 沿用 PR3 输入身份命名空间；UUID 不是新的 native
事件身份。input SHA 绑定完整输入，runtime SHA 绑定完整结果，ETag 绑定简报视图。
这些 pin 不等同于跨请求身份 registry；本 PR 不增加该 registry 或 G3 状态续接。

每个 journal entry 绑定 stream、单调 sequence、previous SHA、类型、服务端时间、指针
状态和变更行 SHA。append/head 与所有业务行同一 SQLite 事务提交。不可变表禁止更新/
删除；run 仅允许 version+1，终态不可再改，原始 input/created_at 不可改；head 更新必须
指向已插入的匹配 entry。读取验证完整链、行摘要和最终指针。大 input/runtime 正文延迟
加载，其 SHA 在 journal 中绑定，实际运行或读取 detail 时验证；status 不反复解码所有
历史大正文。故意绕过触发器篡改正文会在消费时失败，不承诺每次 status 读取全部正文。

## 独立 checkpoint 与故障恢复

数据库外 JSON checkpoint 独立保存 database UUID、epoch、各流 sequence/SHA 和 pending
intent。它不是 G3 synthetic history。持久锁文件使用进程内锁和 OS 文件锁，运行后不
删除锁文件；普通读写最多等 2 秒，维护与 worker owner 不等待。

1. 获得 checkpoint 锁，BEGIN IMMEDIATE，验证 Schema、链、行与 checkpoint。
2. 校验 expected_epoch、幂等键与 expected_head，构造业务行、journal 和 head CAS。
3. 持久化外部 intent(before/after)，再次检查请求 Control，然后 SQLite commit。
4. 原子替换 checkpoint 为 after，清除 intent。库设置要求 foreign_keys=ON、
   synchronous>=FULL；旧 Database 保持 WAL 与其原有事务设置。

重启仅接受精确 before（事务未落地）或 after（已提交）状态，经全链验证后清理 intent。
其他头或断链失败关闭。DB 已提交但 checkpoint finalize 失败返回
G4_COMMITTED_ANCHOR_PENDING / database_state=committed；提交异常无法确定结果返回
G4_COMMIT_OUTCOME_UNKNOWN / unknown。客户端不得据 503 推断没有发生变更，应查询 status
并用相同幂等键重试。外部文件不是与 SQLite 的跨文件 ACID 事务，以上协议处理其间隙。

独立 checkpoint 可发现只回退 DB 的情况。DB 与 checkpoint 一起被回退，或本机管理员
同时重写两者，不能由这个协议识别；不宣称多机共识、认证、防管理员篡改或断电硬件
耐久性。测试覆盖进程 os._exit 的提交前后崩溃及故障注入，未模拟硬件断电。

## 显式迁移、备份与恢复

intelligence_enabled 默认 false，应用启动不迁移此 Schema；旧业务仍按原逻辑运行。
启用前在停止 worker 后显式调用 cfaw_news.intelligence.persistence_migrate。参数均应
使用管理员确认的绝对路径，以下为接口形式，不是本轮对用户库执行的命令：

```text
python -m cfaw_news.intelligence.persistence_migrate upgrade --database DB --anchor ANCHOR --backup BACKUP --receipt RECEIPT
python -m cfaw_news.intelligence.persistence_migrate backup --database DB --anchor ANCHOR --backup BACKUP --receipt RECEIPT
python -m cfaw_news.intelligence.persistence_migrate rollback --database DB --anchor ANCHOR --backup BACKUP --receipt RECEIPT
python -m cfaw_news.intelligence.persistence_migrate restore --database NEW_DB --anchor NEW_ANCHOR --backup BACKUP --backup-pin SHA --acknowledge-restored-history --receipt RECEIPT
```

已有库操作必须先备份；全新库 upgrade 可不带 --backup。旧库须已经通过 PR2 显式迁移，
空库则创建 PR2/PR4 Schema，均不回填历史。复用 PR2 已修复的路径/receipt 机制，并增加
anchor/lock/worker 与数据库、sidecar、备份、manifest、receipt 的别名排除。备份提交后
再核验存在性和 SHA。DDL 失败事务回滚；首次初始化若留下未提交的 anchor，下一次会
失败关闭，需要检查 receipt/实际库并由维护者处理，不能自动删除可能有用的历史 anchor。

rollback 只删除 intelligence_ 表，保留 PR2/旧表及旧 checkpoint 作为历史证据。恢复必须
使用新 DB/anchor 路径并确认历史回退；验证备份 SHA、链和外键后创建新 epoch。也提供
adopt-restore，在已还原数据库上显式确认并创建全新的 anchor。旧客户端 expected_epoch
将被拒绝，旧幂等键不会跨恢复 epoch 静默授权。checkpoint 不随 DB 备份自动回退。
receipt 提交后写失败用结构化状态区分 committed/unknown，退出 2；不得将它解释为回滚。

## 生命周期与发布原子性

POST 在服务端捕获 as_of、当前 Persona、完整账本输入、config 与 corpus basis，事务
写入 queued run。队列及数据库总容量有限，重试先查请求表，不重复启动有效任务。
单进程 owner 用 semaphore 限制 native CPU worker，CPU 计算在线程中执行，Control
贯穿内部重算、排序、预算和结果验证；持久取消状态和请求 event 都能使阶段停止。

发布前严格重验 RuntimeResult、来源观察、输入 SHA、Persona、latest version、账本
basis、fact policy 和开始计算时 trusted head/epoch；提交前再检查 Control。快照、
Archive、Delivery、included、run completed 和 latest 指针在一个事务落地。取消先
持久化终态；与发布竞争以提交线性化，已取消任务不能后发结果。失败、超时、stale、
重启中断不会覆盖旧 latest。即使故障计算不协作、线程在超时后短暂继续，也无法发布；
这不是强行终止任意 Python 线程的保证。

owner 重启将遗留 queued/running 标为 interrupted，不自动重跑或补发。另一实例只有
读写取消能力，不抢走运行中任务。全 stream head CAS 是保守边界：计算期间任何新的
journal 写入（包括交互）都可能使此次发布 stale；客户端应先提交观察，再发生成请求，
冲突后查询新 head 并用新键重试。本版不自动 rebase。两个 worker 配置同样可能互相
产生 CAS 冲突，默认一个 worker。

## 交互时序、重试与引用

included 仅记录事务成功发布的 delivery，不记录 Archive 作为 exposure；不会因 GET
而补写。rendered 要求明确 viewport_visible 且目标是 delivery；opened 要求 detail_opened，
可以指向 Archive。ack/dismiss/retract 要求 explicit_user。服务端无法证明浏览器报告
真实，故标为确认来源，不称客观行为观测。learned 恒 false；计划秒数标为未校准估计。

每次写要求 idempotency_key、expected_head、expected_epoch；还校验对应 run/persona/
snapshot version。相同键同语义返回原资源；不同语义冲突。库唯一约束限制重复 request、
snapshot、observation 与 retract；新键重复 rendered/opened 或未撤回的 ack/dismiss 复用
旧 interaction，不重复计数。额外请求收据仍追加链。撤回只追加指向 ack/dismiss 的行，
保留原记录与原 available_at；不覆盖过去。

客户端 client_occurred_at 只能在 snapshot.generated_at 与服务端现在之间，不能改变
available_at。读取 interactions/persona versions 支持 as_of、稳定 sequence/ordinal
顺序及分页，未来 cutoff 拒绝。固定 briefing_id/event_snapshot_id 读取旧快照，交互引用
旧快照仍按其真实 version 校验，不悄悄转向 latest。ETag 可做 latest 条件读取。

## API 与本地边界

所有接口属于 /api/intelligence；严格请求/响应模型及 OpenAPI 导出在
evals/intelligence_g4/schema/pr4，18 份工件。禁用时只有精简 status，其他新路径不可用。

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | /status | 模式、head/epoch、worker、错误、配置 profile pin |
| POST / GET | /persona | 保存不可变版本 / 读取当时可见版本 |
| GET | /persona/versions | 版本历史及 as_of 分页 |
| POST | /briefings | 幂等创建受控 run |
| GET | /briefings/latest、/briefings/{id} | latest ETag / 固定快照 |
| GET / POST | /runs/{id}、/runs/{id}/cancel | 持久状态 / 显式取消 |
| GET | /events/detail | 固定快照对应候选、版本链、主张/引用/assessment |
| GET | /archive、/coverage | 完整 Archive / coverage gaps |
| POST / GET | /interactions | 明确确认或撤回 / 按可见时间读取 |

简报包含 as_of/generated_at、mode/pipeline、evidence_status、version/ETag、完整 Archive、
archive_snapshot_ids、unmet_protected_event_keys、coverage、budget_diagnostics（含 excluded/
truncated 原因），raw-only 时没有 delivery。native_tier 是 Archive 诊断字段，不是显示
许可。完整 runtime 与阶段日志作为 hash-bound JSON 保存在 SQLite；其中 trace.path 是
逻辑阶段工件名，不是公开 HTTP 下载链接。测试探针另保存对应 stages/N.json 便于重放。

路由要求真实 peer 为 loopback，不信任转发头；Host 精确匹配 loopback 主机名，POST
必须带白名单本地 HTTP Origin 和 JSON。拒绝重复关键头、重复 query/JSON key、NaN、
额外字段；自有 CORS 仅允许配置 Origin 与 GET/HEAD/POST，暴露 ETag。未扩大旧接口
的 Origin 白名单。它是本地浏览器边界，不是多用户认证或云隔离；部署仍须监听 loopback。

默认请求体 64 KiB、在途请求 4、worker 1、活动队列 2、超时 30 秒；body 每块等待最多
5 秒，运行输入 4 MB、结果 8 MB。默认最多 256 runs、64 snapshots、128 Persona versions、
总 20000 journal entries；达到容量显式拒绝，无自动删除。长期使用须另设计归档/压缩与
容量升级，不能删除历史链中间记录。

常见错误按 Schema 返回 code/database_state：G4_EXPECTED_HEAD_CONFLICT、
G4_RECOVERY_EPOCH_CONFLICT、G4_IDEMPOTENCY_CONFLICT、G4_RUN_BASIS_STALE、
G4_TRUSTED_HEAD_MISMATCH、G4_HISTORY_CHAIN_INVALID、G4_HISTORY_RECORD_MISMATCH、
G4_SOURCE_INTERRUPTED、G4_RUNTIME_CANCELLED、G4_RUNTIME_TIMEOUT、G4_HOST_FORBIDDEN、
G4_ORIGIN_FORBIDDEN、G4_REQUEST_TOO_LARGE、G4_REQUEST_CAPACITY_EXCEEDED。
更细分 native 拒绝码保留，不通过填充虚构字段绕过。

## 验证边界

本 PR 在 .tmp 隔离库使用工程 mock，验证迁移/备份/恢复、提交前后进程退出、CAS、断链、
取消 race、超时、磁盘故障、重启、严格 HTTP 边界和旧 API 回归。无真实用户库写入、
网络采集、模型调用、React 修改或通知。实现及本轮执行证据见 audit/g4/pr4；独立审查
仍待完成，不以自测宣称生产部署、证据真值、用户价值或算法增益。
