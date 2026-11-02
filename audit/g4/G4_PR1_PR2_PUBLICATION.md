# G4-PR1/PR2 发布记录

2026-11-02。发布前本地与远程 main 均为
2655f10cf20c647bdbfd1b69a000847471b2c5a3。
用户明确要求将当前全部修改更新到 https://github.com/V-Giotto/cfaw-news，
并将开发日记保留在忽略目录。本次只发布已完成的 PR1/PR2 与其计划、审计、修复材料。

## 发布范围

- G4 准入审计、实现计划、runtime_local_v1 ADR、严格离线契约/Schema/native G2 可行性回放。
- PR1 版本链、请求覆盖窗口和 namespace 文档修复及其可复验工程证据。
- G4 专用版本化资料账本、明确来源策略、rights/coverage、抓取事务接入及显式本地迁移。
- PR2 SQLite sidecar/产物别名拒绝、提交后备份验证、预备 receipt 和提交结果明确报告。
- 独立 PR1/PR2 测试清单与审查记录；不包含实际用户库或 .tmp 中的大型运行工件。
- .gitattributes 增加 G4 精确字节规则：两份 CRLF required-test 清单不被 Git 自动归一化，
  提交前逐项比较暂存 blob 与工作区字节，不重新生成旧 pin。
  两份既有计划的 Markdown 双空格换行原样保留，格式属性仅作用于这两份文档。

## 验证和审查状态

PR1 原三个 finding 和 PR2 原两项 finding 都有后续独立 AI 复审关闭记录。
PR2 记录见 pr2/RE_REVIEW.md。原报告中的 pending 是当时状态，保留不变。

| 阶段 | 实际结果 | 证据边界 |
|---|---|---|
| PR1/PR2 最终修复工程运行 | G4 164 passed；旧相关回归 64 passed；Ruff/Schema 通过 | 本地合成/mock 工程验证 |
| PR2 修复后独立 AI 复审 | G4 164 passed；旧相关回归 64 passed；两项 finding 关闭 | 复审实际重跑与静态核对；不是独立人工研究 |
| PR2 早期完整旧仓回归 | 1753 passed、1 skipped、1 warning | 历史记录，修复后及发布阶段不冒充重跑 |
| 发布阶段 | 内容/忽略/敏感文件审计、Git blob 精确字节检查；Ruff/Schema/baseline/离线 build 另存新日志 | 不复用旧日志冒充新命令 |

固定修复源码 pin：
da51ed62860a790f0d4b4a95c07537e4d29e940ef1d0918d4155ed3f670b3325。
固定修复 baseline pin：
a6db824696ac4c7f014809ddad2ca7f43d10f88eff74f36b4bea9625d98a3a15。
版本与迁移 source/DDL pin 没有因发布而改写；Schema/源码/配置/输出详细 pins
见 pr1/、pr2/ 的各个历史与当前 release manifest。

现有 GitHub Actions 验证旧仓注册测试、baseline 和前端构建；G4 的独立轨道目前
需要显式运行 python -m pytest -q evals/intelligence_g4/tests。没有把旧 CI 说成已覆盖 G4。
远程 run 状态以 GitHub 实际运行结果为准，不能用本地 PASS 代替。

## 日记与范围

开发日记在本地 dev-diaries/。根 .gitignore 已有 /dev-diaries/，并由 AGENTS.md
禁止 stage/force-add/commit/push/upload；发布前后均核验无日记进入索引/提交。
不读取既有日记，也不上传本次日记或其内容。

本次发布不执行实际采集、外部模型、真实用户库迁移、PR3、UI 或生产部署。
真实 G3 runtime adapter 仍未注册，publishable=false；未知许可不被提升为正文证据。
