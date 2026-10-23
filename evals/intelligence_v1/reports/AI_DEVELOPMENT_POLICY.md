> 已被新批次替代（2026-10-23）：本文为历史版本证据；默认流程已改为单 AI 开发，原真人待办不再是前置条件。当前批次、pin、实际验收和限制见 [PR5 AI 开发收尾](PR5_AI_DEVELOPMENT.md)。历史数据与结论未改判。

# DEV-01～05 AI 开发规则变更（2026-10-23）

用户要求允许 AI 完成开发轨迹，取消默认真人双标前置。当前执行依据是
`docs/plans/G1_AI_DEVELOPMENT_RULES.md`、AGENTS.md、已更新的 V1/G1 计划与协作提示词。

- 默认 `ai_development`：AI 可以初标、复核、裁定；不要求第二名真人。
- 可选 `human_research`：保留原真人身份、独立提交、仲裁及 lineage 审计。
- 新 acceptance 输出记录 profile、实际 human gate 及 human_research_passed；开发 profile
  仍要求完整冻结的开发标签覆盖，以及全部原有技术门槛。缺数据、旧检查证据和失败回归不会通过。
- 单步包附带 AI 开发规则和哈希，V3 原文继续提供评分定义及可选真人协议。
- 旧真人指南、原始提交、开发期望、文档版本和金标不改写，不将 AI 判断冒称真人证据。

新数据版本：`pr5-five-trajectories-v9-ai-policy-r1`；schema：`g1-pr5-5`。
Manifest SHA-256：`4569cf85373667a30da041c686772d4977a6cce8be2d46fed650f86b04603b90`。

旧包完整保存在本地 `.local/evals/g1/pr5/human-followup-v8-r1-20261023/frozen-v8-r1/bundle/`，
已确认其 manifest 与修改前当前 manifest 逐字节一致。本次局部备份及检查输出位于
`.local/evals/g1/pr5/ai-policy-20261023/`。

本次交付是规则及验收入口修改；没有重新生成五轨迹 AI 初标，没有运行完整的
200 预测 / 400 评测矩阵，也不把旧真人 NOT_MET 报告改判为新版本开发 PASS。
G2 尚未自动开始；真实用户价值、真人理解和独立泛化仍未测。

## 验证记录

- `.venv/Scripts/python.exe -m ruff check backend tests evals`：通过。
- `.venv/Scripts/python.exe -B -m evals.intelligence_v1.contracts --check-schemas`：通过，`g1-pr5-5`。
- `.venv/Scripts/python.exe -B -m evals.intelligence_v1.validate --manifest evals/intelligence_v1/manifests/dataset_manifest.json --strict`：通过，0 errors。
- 定向运行 `tests/evals/test_pr5_acceptance.py` 和 `tests/evals/test_annotation_packets.py`：23 passed。
  覆盖 AI 默认可通过而真人研究仍阻塞、缺失/失败技术门槛、标签逐事件覆盖、未知 profile 拒绝、包内规则及哈希。
- `.venv/Scripts/python.exe -m pytest -q --basetemp=.tmp/ai-policy-full-loopback-20261023 --junitxml=.local/evals/g1/pr5/ai-policy-20261023/pytest-full.xml`：
  **519 passed / 1 skipped / 1 warning**，594.26 秒。唯一跳过为 `symlink creation unavailable: 1314`，
  与既有 Windows skip exemption 一致；警告为 Starlette TestClient 的 httpx 弃用提示。
  JUnit 与冻结清单的 520 个节点逐项一致，测试源文件哈希仍匹配。
- `.venv/Scripts/python.exe evals/run_baseline.py`：seed-sanity-v1 通过，非算法增益证据。
- `npm run build`（`frontend/`）：通过。
- `git diff --check`：通过。
- 对新 manifest 使用旧 v8-r1 检查与矩阵：按预期 exit 1。开发标签覆盖 PASS、human 必需门槛 N/A；
  旧检查被 `CHECK_EVIDENCE_MISMATCH` 拒绝，旧运行被 `RUN_INPUT_MISMATCH` 拒绝，没有自动升级为 PASS。
- 86 个既有 JSONL、三版原标注手册及原 ReviewSession 的 SHA 与修改前相同。

详细本地核对：`.local/evals/g1/pr5/ai-policy-20261023/policy-verification.json`。
全量回归使用 `--basetemp=.tmp/ai-policy-full-loopback-20261023`，避免受保护的 `.local` 数据路径。
沙盒内全量运行在 TestClient 启动时挂起；独立 5 秒探针确认 `asyncio.new_event_loop()`
阻塞于 `socket._fallback_socketpair → accept`。允许本地回环的执行环境下同一探针 exit 0，
随后在该环境重跑全量测试。此前曾用 `.local` 作测试临时根而触发预期的
`MANIFEST_PATH_INVALID`，未修改路径或事件循环防线。
