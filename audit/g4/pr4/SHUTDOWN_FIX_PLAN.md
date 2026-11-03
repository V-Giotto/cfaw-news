# PR4 shutdown reservation 修复矩阵

2026-11-03，main@783f5428671457ea3f1f654b160152f653d2e9e0。
当前用户明确授权修复；保留所有旧审计/测试/Schema 字节，不 Git 写操作，不联网、
不写真实用户库，不读 dev-diaries/。入口/source-before/旧 manifest 核验保存于
.tmp/evals/g3/g4-pr4-shutdown-fix-20261103-001/。

| 文件 | 修改 | 当前验证 |
|---|---|---|
| intelligence/service.py | 同锁线性化 close/admission/submit/register；实际 Future 覆盖 run-start 返回边界；native 超时起点保持 | 两个 worker、A 退出/B 暂停、关闭交接；取消 async waiter 后仍保留实际占用 |
| test_shutdown_handoff.py | 确定性 event 暂停，无真实模型 | 先红后绿；阻止提前交接，合法交接后新实例可运行两个任务，总峰值不超限 |
| 新 shutdown manifest/报告/pins | 旧 316 节点不改，独立登记新节点 | 全部 G4、旧后端回归、Ruff/现有 Schema；当前源码离线 wheel；旧 full 仅作为历史记录 |

SQL migration、checkpoint、API/Schema、算法与前端不变。完成后停止等待复审。
