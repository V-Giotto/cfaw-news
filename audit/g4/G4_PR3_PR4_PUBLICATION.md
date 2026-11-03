# G4-PR3/PR4 当前实现发布记录

2026-11-03。管理员明确要求将目前修改同步至 V-Giotto/cfaw-news，授权本次 commit/push。
发布入口为 main@783f5428671457ea3f1f654b160152f653d2e9e0，远程 main 与其一致。
这是代码/工程证据发布，不是部署、真实用户库迁移、PR4 独立验收或 PR5 授权。

## 发布范围

包含受控 runtime_local_v1 G2/G3 桥接、严格版本契约与独立安装 native profile、SQLite
用户历史/快照/交互/Persona/可信头、显式维护工具、独立默认关闭的 intelligence API，
以及材料类型/Persona/Control、来源前缀恢复、幂等域、实际 worker 和关闭交接修复。
旧 G1/G2/G3 算法与验收资产、旧业务/React 保持相应实施入口字节；旧审计不改写。

PR3 的独立 AI 复审有追加 PASS 记录。PR4 最新关闭交接修复只有本地工程自测 PASS，
仍待独立复审；本次发布不把 pending 改成 accepted。完整记录见：

- audit/g4/pr3/RE_REVIEW.md
- audit/g4/pr4/IMPLEMENTATION_REPORT.md
- audit/g4/pr4/REVIEW_FIXES.md
- audit/g4/pr4/SHUTDOWN_RESERVATION_FIX.md
- audit/g4/pr4/SHUTDOWN_FIX_BASELINE.json、SHUTDOWN_FIX_RELEASE_MANIFEST.json

本地 .tmp 工件不随源码发布；仓库内的摘要记录保留精确路径/SHA，不能把缺少原始
本地工件的远程克隆误称为完整原始验收包。源码、测试、Schema 与必要重放工具会发布。
发布暂存检查发现生成 SCHEMA.sql 的 SQLAlchemy 行尾空格，故新增仅针对该文件的
.gitattributes exact-byte/whitespace 规则，保留已封存 SQL 字节与 SHA，不改写验收工件。

## 核验与测试分类

最近实施轮真实验证为 G4 318 passed、旧后端 125 passed；Ruff、20 份当前 Schema、
baseline、前端 build、仓库外离线 core/native wheel 与依赖缺失/篡改拒绝通过。源码与
上述已封存工件在发布前逐项重验 SHA，未发生漂移。发布检查不冒称再次执行 pytest。
旧完整 1753 passed/1 skipped 是前修复轮运行记录，不是本次发布新跑。

现有 starter-checks CI 运行冻结旧套件与 smoke；其通过不代表自动重跑全部 G4 节点。
G4 本地节点清单和当前源码 pin 单独保存。最终远程 commit 与 Actions 状态以 GitHub
记录为准，不提前声明 CI success。

## 保留边界

intelligence 默认关闭，启用需显式维护。旧 checkpoint v1 要求备份后显式新 epoch 接管；
不能绕过已知来源前缀缺失。真实 Focus/Radar 仍受资格阻断，真实交互尚未进入 G3 历史
评分，晚 Persona 连续性继续阻断。默认 B4；P1 仅显式实验；预算 profile 未校准。
工程 mock 不证明线上新闻/许可真实性、模型效果、用户价值或云隔离。

本地开发日记单独写入 dev-diaries/，保留根 /dev-diaries/ ignore；没有将该目录或内容
纳入候选、暂存或发布。credentials、用户 SQLite、.local/.tmp、虚拟环境、node_modules
和生成 dist 均不上传。当前发布不触发模型/新闻网络采集、通知或第三方业务动作。
