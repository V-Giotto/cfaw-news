# G4-PR4 文件、测试矩阵与数据库风险

入口 main@783f5428671457ea3f1f654b160152f653d2e9e0；PR3 本地未提交新增文件及其修复仍在。
原 1025 个文件及复审收据摘要保存于 .tmp/evals/g3/g4-pr4-20261102-001/entry.json。
PR3 独立 PASS 与三项 finding 关闭已追加到 audit/g4/pr3/RE_REVIEW.md；当前用户明确授权 PR4。

## 实施矩阵

| 文件 | 变更 | 验证 |
|---|---|---|
| intelligence/persistence_contracts.py、persistence_models.py | 严格 API/SQLite 记录、真实/合成流隔离、交互语义 | Schema、幂等、旧引用、不可变记录、时序 |
| intelligence/migrations/002_g4_briefings.py、persistence_migrate.py | 独立 metadata/intelligence_* 表，显式升级/备份/回滚/恢复接管 | 新库/旧 PR2 库、路径别名、备份恢复、DDL 事务、旧表逻辑保全 |
| intelligence/checkpoint.py、history_store.py | SQLite 头/append 同事务；库外 checkpoint intent/commit 恢复、CAS | 两实例冲突、坏链/坏头、整库回退、故障/崩溃恢复、幂等 |
| intelligence/service.py | run 生命周期、CPU 线程受控计算、取消、发布 CAS、旧快照保留 | late result、超时、重启、来源中断、磁盘失败、版本过期 |
| intelligence/routes.py；main.py/config.py 增量挂载 | /api/intelligence 独立路由、启用开关、Host/Origin/大小/并发界限 | HTTP 正反例、OpenAPI、ETag、旧 API 回归 |
| evals/intelligence_g4/tests/test_{history_db,intelligence_api,publication_races,persistence_migration}.py | 本地隔离 SQL/mock 工程测试 | 完整 G4、冻结旧 runner、Ruff/Schema/baseline/build |
| docs/adr/G4_PERSISTENCE_V1.md、audit/g4/pr4/ | source/config/Schema/output pin、报告 | 区分历史记录和本轮执行 |

## 旧后端审计

旧 main.py 取消先持久化 cancel_requested/terminal，再取消 asyncio task；service.py 发布前
再次检查取消、terminal、目标版本和 evidence hash。旧状态和 Schedule 的 BEGIN IMMEDIATE/
proposal_key 唯一约束可借鉴，不能把其目标业务行改成 G4。旧 task registry 仅在内存中，
启动时 queued/running 标失败，未实现 G4 用户历史。旧 database.py 有 WAL、外键、15 秒
锁等待，session.begin 事务；Base.create 不应偷偷创建 G4 表。旧 CORS 白名单不是 Host/
Origin 写防护。API 仍是本地单用户，无多用户认证或云隔离。

## 关键决定和风险

- 新表使用 intelligence_*，不污染 PR2 固定 g4_* 表/Schema 查询。旧迁移、G1–G3 源码及
  控制面保持原字节；不把 G3 synthetic JSONL 用作用户存储。
- 默认关闭新服务；必须显式迁移并配置库外 checkpoint 后启用，不在应用启动迁移真实库。
  本轮仅操作 .tmp 下隔离数据库，不改 React、不联网采集或调用模型。
- DB entry/head 原子提交；外部 checkpoint 采用先 intent、后 DB commit、再 finalize。
  崩溃后只接受 before/new 两个已验证状态，未知状态失败关闭。独立 checkpoint 不纳入
  DB 备份；整库与 checkpoint 一起回退/被管理员一起改写无法检测，不宣称抵抗本机管理员。
- 显式备份、恢复新路径与恢复 epoch 接管；不从旧缓存/Reader 或 synthetic history 回填。
- included 仅与 delivery 原子发布；rendered/opened 只由客户端相应确认 POST；GET 无观察
  副作用；ack/dismiss/retract 必须明确用户操作。opened 不代表 learned，预计阅读秒数不
  写成行为。幂等键/CAS/唯一约束保护重试和重复确认。
- PR3 仍无真实独立支持和历史 Persona 补全。本 PR 不放宽资格：完整验证的真实原始资讯
  可发布明确标为 raw 的 Archive 快照；无证据、native 拒绝、晚画像或来源中断保留旧快照。
  Focus/Radar 仅在合法合格计划时发布；synthetic developer 流必须显式隔离，不能进入真实流。
- 本 PR 持久化并暴露真实交互事实；不伪造 G3 synthetic journal，不将尚未接入排名的真实
  历史宣称已作用于 G3 特征。API 必须明确 history_scoring 状态。

完成后停止等待独立审查；不提交/推送、不启动 PR5。
