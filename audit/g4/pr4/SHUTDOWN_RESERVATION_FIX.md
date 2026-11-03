# G4-PR4 run-start / shutdown 交接修复

2026-11-03。**PASS：本地工程修复与本轮自测；独立复审 PENDING**。
用户提供的 rereview 复现是旧实现缺陷证据，不是本轮通过记录。原 PR4 报告与 pins
保留；本文件不将先前自测冒充此 finding 已经关闭。

核对 main@783f5428671457ea3f1f654b160152f653d2e9e0，初始工作区包含未提交的
PR3/PR4。用户明确授权本修复。入口 1100 个文件、旧 release 核验及 service.py 前像
保存于 .tmp/evals/g3/g4-pr4-shutdown-fix-20261103-001/entry.json、service-before.py。
先列 SHUTDOWN_FIX_PLAN.md 文件/测试矩阵，再实现；没有 Git 写操作。

## 修复与线性化边界

原版 _running 使用登记以外的 to_thread；只检查 await 前的 closed，A 退出便可能释放
owner，B 返回后还能 submit。现在只有 service.py 发生既有源码变更：

- computation_lock 同时保护关闭 gate、worker 可用性、实际 owner 检查、submit 与登记。
- 一个实际 Future 从 _running 开始，覆盖提交/返回边界、native、结果验证和发布；
  waiter 取消不代表实际占用消失。callback 在锁外注册，避免同步重入死锁。
- _running 返回后重新检查关闭/owner；关闭后的 B 不进入 native。ready 事件同时处理
  正常进入和失败完成，native 的 Control/wait_for 起点保持在 run-start 完成后。
- owner 释放同时要求 closed、close_drained、实际 Future 集合为空。异步终态清理未
  完成或实际 run-start/Future 仍存活时，替代实例不能计算；清理与实际执行均排空后
  才交接。关闭可返回而继续保留 owner，不声称强杀不协作线程。

具体决定见 docs/adr/G4_SHUTDOWN_HANDOFF_FIX.md。没有修改 SQL/checkpoint/HTTP 契约、
Schema、native 算法/资格、Persona、预算配置或 React。来源前缀/恢复标记、命名空间、
取消和发布 CAS 的前次修复保留。

## 当前回归与证据

新增 test_shutdown_handoff.py 两个必需节点，参数为正常 waiter / waiter 被取消。
通过 threading.Event 暂停 B 在 _running 已完成、尚未返回的位置，A 为不协作计算 mock。
同一 owner 设 2 workers，A 退出后检查 owner，随后检验替代实例与合法交接：

| 观测 | 本轮结果 |
|---|---|
| A 退出、B 返回前 | owner 保留；实际 Future 包括 B 的 reservation |
| 提前启动的替代实例 | worker_available=false；生成 POST 503 G4_WORKER_UNAVAILABLE |
| 恢复 B、旧实例 closed | 旧 native 总调用仍为 1，B 未进入 native |
| 正常 waiter 的终态清理暂停 | Future 已排空仍保留 owner，close 尚未结束 |
| 完全排空后新实例 | 能获得 owner 并运行两个 mock；跨实例物理峰值 2 |
| 发布 | mock 返回不合法结果，late publication=0；既有合法结果取消测试也通过 |

完整两个 proof.json 保存在本轮 final basetemp，各包含配置、物理计数、交接状态；
SHUTDOWN_FIX_BASELINE.json 记录路径/值/SHA。所有材料均为隔离工程 mock，不是实际
模型调用或线上新闻验证。

旧源码上先运行新增回归：**2 failed**，均失败于 B 暂停时 owner 已释放；收据
regression-red exit 1，保留原日志/JUnit。其后补充了失败路径清理和终态清理观测，
当前完整测试文件的源码 pin 属于最终绿测试，不伪称在红测试之前已冻结。

本轮真实命令统一由 .venv/Scripts/python.exe -m audit.g4.pr1.run_checks 记录，输出在
.tmp/evals/g3/g4-pr4-shutdown-fix-20261103-001/。完整 argv/cwd/env、UTC 起止、退出码
与日志 SHA 见 *.command.json；以下为内层命令说明：

| 收据 | 命令/范围 | 实际结果 |
|---|---|---|
| regression-red | pytest test_shutdown_handoff.py，修复前 | 2 failed，预期缺陷复现，46.60 秒 |
| regression-green | 新交接 + 前次 review fixes + publication races | 34 passed，中间实现 |
| g4-final | pytest -q evals/intelligence_g4，独立 basetemp/JUnit | **318 passed / 0 skipped**，246.61 秒；旧 316 + 新 2 |
| backend-regression | tests/test_workflow.py、test_following.py、test_ingestion.py、test_reading.py、test_media.py、test_providers.py | **125 passed**，18.95 秒 |
| ruff-final | python -m ruff check backend tests evals audit/g4/pr4 | PASS |
| schema-check | persistence_schema 对 schema/pr4_review_fix --check，隔离 scratch | 20 份工件 PASS，未创建 DB |
| baseline | python evals/run_baseline.py | PASS，仅 lexical seed sanity |
| frontend-build | frontend 下 npm.cmd run build | PASS；React 源码未改，非浏览器行为验证 |
| prepare-shutdown-seal / verify-shutdown-seal | audit.g4.pr4.finalize_shutdown_fix [--prepare] | 节点/源码保全、proof、当前 wheel 与服务源码、收据/log SHA 核验 PASS |

pytest 的现有 FastAPI/Starlette httpx 弃用警告仍在，无失败忽略、skip 或降门槛。
旧完整 G1–G3/后端 1753 passed / 1 skipped 为**前次修复轮历史运行**，本轮没有重跑
整套冻结 runner；本轮新验证是以上 G4 及 125 个相关后端节点。未改旧测试/控制面。
离线 core/native wheel 在仓库外运行、缺依赖/篡改拒绝仍通过，当前 service.py 与 wheel
逐字节 pin 一致，不把仓库可导入当独立安装验证。

## Pins 与保全

| 对象 | SHA-256 |
|---|---|
| service.py 修复前 | 7fff443bf5fec153e88f003f7f8b8ccc84c575900e1350cdc9739e69cb58a739 |
| service.py 修复后 | 20afee774f8c734f87650f75ba48e895f390e40af83d23dfee0e7e1d5144da83 |
| 五个修复源码/测试/ADR/manifest/工具工件集合 | d6dc4fe8dd1c6331eb2a87ff26bf80ef10a12f88142738767b50d86842c33f01 |
| SHUTDOWN_FIX_BASELINE.json | 6e09ce08cfc30c72d2bb001aeb73070d1e02c09b913c5f3e4a3d52202acdbafd |
| 正常 waiter proof | c850973ae32315bdcb7e806b01ba41835d169a71922e2e68a65e3d443c878871 |
| 取消 waiter proof | e46022449207639ecf4ee6f600e708da2a3d6b0d7ec11444c488543196585e70 |

完整源/配置/native policy/工件 pin 见 SHUTDOWN_FIX_BASELINE.json 和
SHUTDOWN_FIX_RELEASE_MANIFEST.json；旧 release 文件保持原字节。唯一改变的入口文件
为 service.py；旧 test sources、reports、manifests、Schema、database、checkpoint、
React、G1/G2/G3 与日记 ignore 均未改。

结论：P2 已修复并自测 PASS；独立复审尚未关闭。真实 Focus/Radar、历史评分及其他
原产品边界不扩大。未外部联网、调用模型、读 dev-diaries、写真实用户 DB、提交或推送。
已停止等待复审，不实施 PR5。
