# PR6 P3 — verify-only read-only correction

`verify_controls()` 只返回校验结果；持久化 `control-verification.json` 移到 `--verify-only` 返回后的正式封存分支。产品源码、G1/G2/G3 冻结资产和 v2 封存工件不改写。

本轮真实运行位于 `.tmp/evals/g3/g4-pr6-verify-only-fix-20261105-001/`：

- probe-red：exit 1，Python audit hook 在系统写入前拦截原入口的 mkdir/open 写尝试；封存文件未变。
- probe-green：exit 0，执行真实 CLI，1754 节点控制面通过，写尝试为 0；选取的五份封存文件 SHA、字节数、mtime_ns 前后一致。
- regression：10 passed，包含三个新回归（校验函数不写、verify-only 在写入前返回、正式封存分支仍保存结果）和七个已有封存器回归。
- ruff：exit 0，backend/tests/evals/audit/g4/pr6。

探针设置 `PYTHONDONTWRITEBYTECODE=1`、`GIT_OPTIONAL_LOCKS=0`，拒绝 Python 写文件及目录/链接/属性变更审计事件；这是本地定向验证，不声称可观测所有外部进程系统调用。

本次仅改 QA 脚本，没有重复前轮完整 pytest、浏览器、前端 build 或 baseline。旧 v2 seal 及其历史源码副本保留原字节；当前 QA 补丁的前后 pins、新收据和独立索引见 `VERIFY_ONLY_FIX.json`。该附录不重新签发 G4 验收或批准 Beta。
