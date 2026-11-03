# PR4：关闭与 run-start 所有权交接

2026-11-03，补充 G4_PERSISTENCE_REVIEW_FIX；原文/验收 pins 保留。

前版只把 native 计算/发布登记为实际 Future，_running 的 asyncio.to_thread 在登记外。
这允许 A 退出后 owner 提前交接，B 在 run-start 返回时于 closed 状态再次 submit。

本版的执行单元从 _running 开始，包括其提交/返回边界、native、严格结果验证与发布。
获得 semaphore 后，在同一 computation_lock 内检查 closed/实际 owner/worker 可用性，
submit 并登记 Future；close 在同一锁内设置 closed、撤销 worker_available。callback
在锁外注册，避免已完成 Future 的同步 callback 重入死锁。async waiter 取消不会移除
仍在执行的 Future 或返还 permit。

_running 返回后再次检查关闭和 owner，已关闭则拒绝 native 入口。ready 事件在该边界
之后通知 asyncio；失败/取消的 Future 也会通知，避免 waiter 永久挂起。native Control
及 wait_for 的超时起点保持在 run-start 完成后，不将慢 run-start 偷偷计入原 native
期限；run-start 若不协作，实际占用和 owner 继续保留。

owner 释放同时要求：closed gate 已关闭新提交、close 的异步任务/终态清理已完成
（close_drained）、所有实际 Future 已退出。close 可在不协作 Future 未退出时返回，
但保留 owner；最后一个 Future 的 callback 才可释放它。替代实例须重新取得实际锁，
不会因“进程已进入 close”假装取得容量。无强杀线程或真实模型执行保证。

新增 event 驱动回归覆盖：2 workers，A 正在计算、B 在 _running 完成返回前暂停；
正常 waiter / 被取消的 waiter；A 退出后 owner 仍保留，替代实例 503；B 返回不进入
native；正常终态清理尚未完成时仍不交接；实际排空后新实例可运行 2 个计算，全程
跨实例物理峰值 <=2。全部输入为工程 mock。SQL、checkpoint、API/Schema 与算法不变。
