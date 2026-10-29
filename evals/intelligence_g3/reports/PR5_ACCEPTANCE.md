# G3-PR5 完整离线开发验收报告

日期：2026-10-28（Asia/Shanghai）。

**结论：ai_development 离线工程 PASS。独立 PR5 审查与所有者最终验收仍待进行；G4 未授权。**

结果仅覆盖复用、非盲、合成 AI 开发回归材料。未证明独立真人 gold、真实模型效果、真实来源泛化、真实用户收益或生产就绪。没有调权重、改历史结果或降低门槛。

## 前置审查与范围

通过当前独立审查聊天核实：PR1 PASS、PR2 PASS；PR3/PR4 PASS WITH CONDITIONS，均无阻断代码项。保留项目内 basetemp；受保护 budget_unmet 中可评估的重要事件计入分母和失败案例。所有者本轮明确要求开始 PR5。823 个 PR4 受审文件在开工前全部匹配审查哈希。

仅新增复现、后评测、验收、报告及交接能力；原 PR2/PR3 ranker 和 PR4 planner/配置未改。本轮原有文件仅修改 G3 README 与增量库存，其余 821 个起始文件逐字节保留。既有未提交 PR3/PR4 与 CI/根 README 改动保留，不冒充本轮新增。

## 实际矩阵与完整回归

26 个案例 × 3 个预算 × 11 个变体 = 858 个组合/种子；两个种子实际完成 1716 次预测，语义输出逐项相同。

同池比较 B0/B1/B3/B4/P1；B2 单独作为 G2 事件池身份对照。五项评分消融：no_history、no_material、no_novelty_material、no_exploration、no_duplicate。覆盖 180/420/900 秒和 1/3/7 天。不取消证据或更正/撤回保护门槛。

完整 G3：540 passed，无 skip。全项目：1663 passed / 1 skipped，精确覆盖 1664 个节点。唯一 skip 保留既有 Windows 符号链接权限 1314 豁免；无 G3 skip。

| 检查 | 退出码 | 实测秒 | 原始日志 SHA256 |
| --- | ---: | ---: | --- |
| collect | 0 | 6.149 | `ce9ce5ee83a776a913715e50ca06a7dcf9ee42809fad8560de408e10a4d4b23b` |
| diff | 0 | 0.081 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| frontend | 0 | 4.596 | `c9aea5144f60182e4536baa618d54ee40f1407631c835dfe19873296902ea7e0` |
| full | 0 | 1003.256 | `0f241b2bd1a334ddb2f34d83ac514bdf1f58f178a4a045b277477d22fa37360b` |
| g1-strict | 0 | 1.013 | `ae200140ab0b4b55cfc9964459369e2e3a0970039dbfb7359501ad56ac18aa38` |
| g3 | 0 | 209.323 | `a26bfb77ad0aac02fdfab979141271e4540f978c1e4358c46a784081a620def9` |
| inventory | 0 | 1.056 | `23b9dc52ebbeda7fafe3d9cacb48286a6f32c3826c099ddf967ebe89e8ec4bcf` |
| junit | 0 | 1.143 | `9c039f9eaa4c9bcf64215ff38a37e8311f5f2346d5b3f55a185d4094aefd2cf5` |
| ruff | 0 | 0.217 | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| schema-g3-0 | 0 | 1.176 | `5f211f49cb13c515e6ce63841964e68606d23b2518b3ecb2f9207e7011a2ce93` |
| schema-g3-1 | 0 | 0.733 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| schema-g3-2 | 0 | 1.286 | `55ef151f6862cf7816b0eef78b92f693c38ef18f82884f7e576adcb2788c150b` |
| schema-g3-3 | 0 | 1.351 | `f5522a246648ccbec8c891b5e017bcb2547cf0aeb45607c04e419af1974c8864` |
| schema-g3-4 | 0 | 1.337 | `b304363d883e292b8b8ad8c84397dfc21c9819cefdd8fdbafee4f3c86d75438e` |
| seed | 0 | 1.123 | `1f26bc870fb9effe3673f332652c45a58d99f6a8df1bbf70932e7cd0fd4c152a` |

完整 G3、完整仓库、exact inventory/JUnit、Ruff、G1 strict、全部当前 G3 schemas、lexical baseline、离线前端兼容构建及 diff 检查均由实际命令产生。前端输出为忽略的临时构建，未修改前端源代码；没有真实 provider、新采集、生产数据库或依赖安装。

## 可信 pin 和指纹

输入 campaign pin：`56f2244812449db5ddb5a8bd2384cb302a3f9d66fb1205be167e9308da530daf`。

代码/测试/schema/配置/fixture/锁文件工作树语义指纹：`c4028c1840f628707ced06e3089bb6d1aafa1cb2a6650d349c74bc63f0462c60`。

锚定提交：`fb42de414e56da7a0eb58e89d174d38a1495f02a`；源码状态为 exact working tree，未伪装成新提交或发布。

| 工件 | 外部保存的 exact-byte manifest SHA256 |
| --- | --- |
| prediction | `8b0d6a9d3dbc0441375d288af54e5ac842b33fd5cd8698a7e09ab34ca7b7d2b4` |
| evaluation | `f8196587edf10349c8fa1565092410ea49b8367148e709e5d0701b76a1bc2204` |
| checks | `c3ec5b5298187c3ee263e4e06c11a7b2b86fb6a7953ca40107d43d8856ff8949` |
| acceptance | `6ff81f5be276b8fff1c1b5a3ed1ffa4f4f1d203f0c7b5e2ba2fa90d9dc9b4f26` |

每个 manifest 记录完整文件集合及原始字节哈希；缺失、额外文件和哈希不符均拒绝。验收核对同一源码/配置、完整真实命令、原始 JUnit，并重算第一种子全部预测、指标、失败案例及报告。

## 指标、错误分析与算法决定

合成产品事件家族 16 个；独立测试家族 0。分母是可评估事件，不是实际展示数；样本是相关的事件×案例×预算状态，两个种子只计一次。所有质量指标保留分子、分母、样本数、家族数、data_source、undefined_reason。

**保留 B4。P1 未获得稳定改善证据；本轮没有独立留出集，不能给出泛化、显著性或真人效果结论。五项评分消融也未改变本批数据的预算召回；这说明当前开发矩阵不足以识别评分项的效果贡献，不能推断这些特征无价值。**

| 变体 | 单元 | Important recall n/d | Important miss n/d | Duplicate n/d |
| --- | --- | --- | --- | --- |
| b0 | all/all | 90/111 | 21/111 | 27/117 |
| b0 | budget/180 | 21/37 | 16/37 | 9/30 |
| b0 | budget/420 | 32/37 | 5/37 | 9/41 |
| b0 | budget/900 | 37/37 | 0/37 | 9/46 |
| b1 | all/all | 90/111 | 21/111 | 27/117 |
| b1 | budget/180 | 21/37 | 16/37 | 9/30 |
| b1 | budget/420 | 32/37 | 5/37 | 9/41 |
| b1 | budget/900 | 37/37 | 0/37 | 9/46 |
| b3 | all/all | 90/111 | 21/111 | 27/117 |
| b3 | budget/180 | 21/37 | 16/37 | 9/30 |
| b3 | budget/420 | 32/37 | 5/37 | 9/41 |
| b3 | budget/900 | 37/37 | 0/37 | 9/46 |
| b4 | all/all | 90/111 | 21/111 | 27/117 |
| b4 | budget/180 | 21/37 | 16/37 | 9/30 |
| b4 | budget/420 | 32/37 | 5/37 | 9/41 |
| b4 | budget/900 | 37/37 | 0/37 | 9/46 |
| p1 | all/all | 90/111 | 21/111 | 27/117 |
| p1 | budget/180 | 21/37 | 16/37 | 9/30 |
| p1 | budget/420 | 32/37 | 5/37 | 9/41 |
| p1 | budget/900 | 37/37 | 0/37 | 9/46 |

全变体失败记录 528 条。完整原始案例保留在 failures.jsonl，包括参考身份、事件家族、是否受保护、未展示原因和 retained_in_denominator。下表列出 P1 的重要遗漏；重复呈现和其他变体记录见机器结果。

| 案例 | 预算秒 | P1 重要遗漏数 | 其中受保护 |
| --- | ---: | ---: | ---: |
| crowded14 | 180 | 10 | 0 |
| crowded14 | 420 | 3 | 0 |
| oversize | 180 | 1 | 0 |
| protected6 | 180 | 5 | 4 |
| protected6 | 420 | 2 | 1 |

protected6/420 秒复现了 PR4 的已知策略限制：6 项更新的最简投影合计 369 秒，贪心先选完整投影，用 411 秒只展示其中 5 项。未展示的受保护更新与普通重要候选仍计入分母。本 PR 不改预算策略以消除失败案例。超长条目、hold 排除和覆盖缺口亦保留原诊断。

B2 与 B1 的真实分数/顺序在验收中一致。没有未合并文档对照臂，G2 合并收益为 undefined，不能归为 G3 收益。消融仅关闭评分分量，保留硬门槛，细节和全部矩阵见下文生成报告。

## 验收拒绝与历史失败

PR5 的 46 项新测试覆盖错误 pin、配置、缺失/篡改工件、未运行/失败命令、错误日志哈希、参考遗漏/重复/身份错误、伪造评分/保护、零分母和同家族重复计数。真实工件拒绝探针记录见 controller/negative-results.json。所有负例预期为拒绝，未被统计成成功验收。辅助脚本最初用文件路径入口执行，因 sys.path 不含仓库根目录而退出 1；改为 runpy 调用后 8 项真实工件负例全部按预期拒绝，仓库源码未改。

首轮 pr5-20261028-001/checks 的 G3 测试为 534 passed / 4 setup errors（basetemp 父目录漏建），该轮未运行全仓回归且未签发通过。修复入口后在全新目录重跑。该修改导致同时运行的首轮矩阵在结束时以 G3_SOURCE_MISMATCH 退出 1，不能混用旧源码工件。原始日志与退出码均保留。第二轮矩阵 exit 0，但后评测因 Python 元组/JSON 数组的表示比较错误而 exit 1；未签发验收。该轮全仓测试主动停止，实际退出码 4294967295。新增两个真实 JSON 往返回归后，当前第三轮重新运行全部矩阵与检查。

开发早期还出现过 context 序列化错误（exit 1）、Ruff 三项问题（exit 1）及定向测试42 passed / 2 failed；修复根路径与零分母校验后，44 项定向测试通过。未伪造或回填失败运行的原始日志。

## 完整机器工件与 G4 交接

本地证据根目录：`D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-20261028-003`。

- prediction/：冻结配置/源码指纹、双种子预测/语义哈希、逐项计时及 worker 命令/日志。
- evaluation/：metrics.json、failures.jsonl、REPORT.md。
- checks/：全部命令/日志、原始 full.xml/g3.xml、完整测试库存和历史兼容检查。
- acceptance/：acceptance.json、REPORT.md、最终工件 manifest。
- controller/：外层命令、完整 commands.jsonl、拒绝探针、前置审查、最终边界与 diff；cost_latency.json 保留实际计时分子/分母、样本数、家族数、data_source 与 undefined_reason。矩阵计时不包含后评测/验收重算；后两者各自记录实际进程耗时。

G4 清单见 [G3_G4_HANDOFF.md](../../../docs/G3_G4_HANDOFF.md)：PR5 独立审查、所有者批准、B4/P1 决定、预算配置、日志 head/pin、schema 升级、客户端曝光语义、取消与回滚、端到端测试、阅读估时/理解度校准及新留出家族。当前均不授权实现 G4。

## 实际命令（完整 argv）

### worker-1 — exit 0

cwd: `D:\agent_project\cfaw-news`

```text
["D:\\agent_project\\cfaw-news\\.venv\\Scripts\\python.exe", "-B", "-m", "evals.intelligence_g3.reproduce", "--manifest", "D:\\agent_project\\cfaw-news\\evals\\intelligence_g3\\manifests\\pr5_campaign.json", "--manifest-sha256", "56f2244812449db5ddb5a8bd2384cb302a3f9d66fb1205be167e9308da530daf", "--out", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\prediction", "--worker-seed", "1"]
```

### worker-719 — exit 0

cwd: `D:\agent_project\cfaw-news`

```text
["D:\\agent_project\\cfaw-news\\.venv\\Scripts\\python.exe", "-B", "-m", "evals.intelligence_g3.reproduce", "--manifest", "D:\\agent_project\\cfaw-news\\evals\\intelligence_g3\\manifests\\pr5_campaign.json", "--manifest-sha256", "56f2244812449db5ddb5a8bd2384cb302a3f9d66fb1205be167e9308da530daf", "--out", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\prediction", "--worker-seed", "719"]
```

### collect — exit 0

cwd: `D:\agent_project\cfaw-news`

```text
["D:\\agent_project\\cfaw-news\\.venv\\Scripts\\python.exe", "-B", "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "-p", "evals.intelligence_g3.junit_inventory", "--g3-inventory", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\checks\\node_inventory.json"]
```

### diff — exit 0

cwd: `D:\agent_project\cfaw-news`

```text
["git", "diff", "--check"]
```

### frontend — exit 0

cwd: `D:\agent_project\cfaw-news\frontend`

```text
["npm.cmd", "--offline", "run", "build", "--", "--outDir", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\checks\\frontend-dist"]
```

### full — exit 0

cwd: `D:\agent_project\cfaw-news`

```text
["D:\\agent_project\\cfaw-news\\.venv\\Scripts\\python.exe", "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "evals.intelligence_g3.junit_inventory", "--junitxml=D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\checks\\full.xml", "--basetemp=D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\checks-pytest\\full", "-o", "faulthandler_timeout=120"]
```

### g1-strict — exit 0

cwd: `D:\agent_project\cfaw-news`

```text
["D:\\agent_project\\cfaw-news\\.venv\\Scripts\\python.exe", "-B", "-m", "evals.intelligence_v1.validate", "--manifest", "D:\\agent_project\\cfaw-news\\evals\\intelligence_v1\\manifests\\dataset_manifest.json", "--strict"]
```

### g3 — exit 0

cwd: `D:\agent_project\cfaw-news`

```text
["D:\\agent_project\\cfaw-news\\.venv\\Scripts\\python.exe", "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "evals.intelligence_g3.junit_inventory", "--junitxml=D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\checks\\g3.xml", "--basetemp=D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\checks-pytest\\g3", "-o", "faulthandler_timeout=120", "tests/evals/g3"]
```

### inventory — exit 0

cwd: `D:\agent_project\cfaw-news`

```text
["D:\\agent_project\\cfaw-news\\.venv\\Scripts\\python.exe", "-B", "-m", "evals.intelligence_g3.junit_inventory", "--inventory", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\checks\\node_inventory.json"]
```

### junit — exit 0

cwd: `D:\agent_project\cfaw-news`

```text
["D:\\agent_project\\cfaw-news\\.venv\\Scripts\\python.exe", "-B", "-m", "evals.intelligence_g3.junit_inventory", "--inventory", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\checks\\node_inventory.json", "--junit", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\checks\\full.xml"]
```

### ruff — exit 0

cwd: `D:\agent_project\cfaw-news`

```text
["D:\\agent_project\\cfaw-news\\.venv\\Scripts\\python.exe", "-B", "-m", "ruff", "check", "backend", "tests", "evals"]
```

### schema-g3-0 — exit 0

cwd: `D:\agent_project\cfaw-news`

```text
["D:\\agent_project\\cfaw-news\\.venv\\Scripts\\python.exe", "-B", "-m", "evals.intelligence_g3.contracts", "--check-schemas"]
```

### schema-g3-1 — exit 0

cwd: `D:\agent_project\cfaw-news`

```text
["D:\\agent_project\\cfaw-news\\.venv\\Scripts\\python.exe", "-B", "-m", "evals.intelligence_g3.ranking_contracts", "--check-schemas"]
```

### schema-g3-2 — exit 0

cwd: `D:\agent_project\cfaw-news`

```text
["D:\\agent_project\\cfaw-news\\.venv\\Scripts\\python.exe", "-B", "-m", "evals.intelligence_g3.revisit_cli", "--check-schemas"]
```

### schema-g3-3 — exit 0

cwd: `D:\agent_project\cfaw-news`

```text
["D:\\agent_project\\cfaw-news\\.venv\\Scripts\\python.exe", "-B", "-m", "evals.intelligence_g3.budget_cli", "--check-schemas"]
```

### schema-g3-4 — exit 0

cwd: `D:\agent_project\cfaw-news`

```text
["D:\\agent_project\\cfaw-news\\.venv\\Scripts\\python.exe", "-B", "-m", "evals.intelligence_g3.pr5_contracts", "--check-schemas"]
```

### seed — exit 0

cwd: `D:\agent_project\cfaw-news`

```text
["D:\\agent_project\\cfaw-news\\.venv\\Scripts\\python.exe", "-B", "evals/run_baseline.py", "--output", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\checks\\seed.json"]
```

### acceptance — exit 0

cwd: `D:\agent_project\cfaw-news`

```text
["D:\\agent_project\\cfaw-news\\.venv\\Scripts\\python.exe", "-B", "-m", "evals.intelligence_g3.acceptance", "--run", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\prediction", "--run-pin", "8b0d6a9d3dbc0441375d288af54e5ac842b33fd5cd8698a7e09ab34ca7b7d2b4", "--evaluation", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\evaluation", "--evaluation-pin", "f8196587edf10349c8fa1565092410ea49b8367148e709e5d0701b76a1bc2204", "--checks", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\checks", "--checks-pin", "c3ec5b5298187c3ee263e4e06c11a7b2b86fb6a7953ca40107d43d8856ff8949", "--out", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\acceptance"]
```

### checks — exit 0

cwd: `D:\agent_project\cfaw-news`

```text
["D:\\agent_project\\cfaw-news\\.venv\\Scripts\\python.exe", "-B", "-m", "evals.intelligence_g3.checks", "--out", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\checks"]
```

### evaluate — exit 0

cwd: `D:\agent_project\cfaw-news`

```text
["D:\\agent_project\\cfaw-news\\.venv\\Scripts\\python.exe", "-B", "-m", "evals.intelligence_g3.evaluate", "--run", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\prediction", "--run-pin", "8b0d6a9d3dbc0441375d288af54e5ac842b33fd5cd8698a7e09ab34ca7b7d2b4", "--out", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\evaluation"]
```

### negative-artifact-hash — exit 1

cwd: `D:\agent_project\cfaw-news`

```text
["D:\\agent_project\\cfaw-news\\.venv\\Scripts\\python.exe", "-B", "-m", "evals.intelligence_g3.acceptance", "--run", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\prediction", "--run-pin", "8b0d6a9d3dbc0441375d288af54e5ac842b33fd5cd8698a7e09ab34ca7b7d2b4", "--evaluation", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\controlled-negatives\\changed-evaluation", "--evaluation-pin", "f8196587edf10349c8fa1565092410ea49b8367148e709e5d0701b76a1bc2204", "--checks", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\checks", "--checks-pin", "c3ec5b5298187c3ee263e4e06c11a7b2b86fb6a7953ca40107d43d8856ff8949", "--out", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\controlled-negatives\\artifact-hash-must-not-pass"]
```

### negative-configuration-mismatch — exit 1

cwd: `D:\agent_project\cfaw-news`

```text
["D:\\agent_project\\cfaw-news\\.venv\\Scripts\\python.exe", "-B", "-m", "evals.intelligence_g3.acceptance", "--run", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\controlled-negatives\\wrong-configuration", "--run-pin", "c19d614625528c9da3f05f8cfb751d78c15a0f7e7c9a3e91c5223509e500c563", "--evaluation", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\evaluation", "--evaluation-pin", "f8196587edf10349c8fa1565092410ea49b8367148e709e5d0701b76a1bc2204", "--checks", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\checks", "--checks-pin", "c3ec5b5298187c3ee263e4e06c11a7b2b86fb6a7953ca40107d43d8856ff8949", "--out", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\controlled-negatives\\configuration-mismatch-must-not-pass"]
```

### negative-incomplete-junit — exit 1

cwd: `D:\agent_project\cfaw-news`

```text
["D:\\agent_project\\cfaw-news\\.venv\\Scripts\\python.exe", "-B", "-m", "evals.intelligence_g3.junit_inventory", "--inventory", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\checks\\node_inventory.json", "--junit", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\controlled-negatives\\incomplete.xml"]
```

### negative-missing-artifact — exit 1

cwd: `D:\agent_project\cfaw-news`

```text
["D:\\agent_project\\cfaw-news\\.venv\\Scripts\\python.exe", "-B", "-m", "evals.intelligence_g3.acceptance", "--run", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\prediction", "--run-pin", "8b0d6a9d3dbc0441375d288af54e5ac842b33fd5cd8698a7e09ab34ca7b7d2b4", "--evaluation", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\controlled-negatives\\missing-evaluation", "--evaluation-pin", "f8196587edf10349c8fa1565092410ea49b8367148e709e5d0701b76a1bc2204", "--checks", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\checks", "--checks-pin", "c3ec5b5298187c3ee263e4e06c11a7b2b86fb6a7953ca40107d43d8856ff8949", "--out", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\controlled-negatives\\missing-artifact-must-not-pass"]
```

### negative-suite-r2 — exit 0

cwd: `D:\agent_project\cfaw-news`

```text
["D:\\agent_project\\cfaw-news\\.venv\\Scripts\\python.exe", "-B", "-c", "import runpy; runpy.run_path('D:/agent_project/cfaw-news/.tmp/evals/g3/pr5-20261028-003/negative_probes.py', run_name=\"__main__\")"]
```

### negative-suite — exit 1

cwd: `D:\agent_project\cfaw-news`

```text
["D:\\agent_project\\cfaw-news\\.venv\\Scripts\\python.exe", "-B", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\negative_probes.py"]
```

### negative-test-fingerprint — exit 1

cwd: `D:\agent_project\cfaw-news`

```text
["D:\\agent_project\\cfaw-news\\.venv\\Scripts\\python.exe", "-B", "-m", "evals.intelligence_g3.junit_inventory", "--inventory", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\controlled-negatives\\wrong-source-inventory.json"]
```

### negative-tests-not-run — exit 1

cwd: `D:\agent_project\cfaw-news`

```text
["D:\\agent_project\\cfaw-news\\.venv\\Scripts\\python.exe", "-B", "-m", "evals.intelligence_g3.acceptance", "--run", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\prediction", "--run-pin", "8b0d6a9d3dbc0441375d288af54e5ac842b33fd5cd8698a7e09ab34ca7b7d2b4", "--evaluation", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\evaluation", "--evaluation-pin", "f8196587edf10349c8fa1565092410ea49b8367148e709e5d0701b76a1bc2204", "--checks", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\controlled-negatives\\missing-test-evidence", "--checks-pin", "c3ec5b5298187c3ee263e4e06c11a7b2b86fb6a7953ca40107d43d8856ff8949", "--out", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\controlled-negatives\\tests-not-run-must-not-pass"]
```

### negative-wrong-external-input-pin — exit 1

cwd: `D:\agent_project\cfaw-news`

```text
["D:\\agent_project\\cfaw-news\\.venv\\Scripts\\python.exe", "-B", "-m", "evals.intelligence_g3.reproduce", "--manifest", "D:\\agent_project\\cfaw-news\\evals\\intelligence_g3\\manifests\\pr5_campaign.json", "--manifest-sha256", "0000000000000000000000000000000000000000000000000000000000000000", "--out", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\controlled-negatives\\wrong-input-must-not-exist"]
```

### negative-wrong-run-pin — exit 1

cwd: `D:\agent_project\cfaw-news`

```text
["D:\\agent_project\\cfaw-news\\.venv\\Scripts\\python.exe", "-B", "-m", "evals.intelligence_g3.acceptance", "--run", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\prediction", "--run-pin", "0000000000000000000000000000000000000000000000000000000000000000", "--evaluation", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\evaluation", "--evaluation-pin", "f8196587edf10349c8fa1565092410ea49b8367148e709e5d0701b76a1bc2204", "--checks", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\checks", "--checks-pin", "c3ec5b5298187c3ee263e4e06c11a7b2b86fb6a7953ca40107d43d8856ff8949", "--out", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\controlled-negatives\\wrong-run-pin-must-not-pass"]
```

### reproduce — exit 0

cwd: `D:\agent_project\cfaw-news`

```text
["D:\\agent_project\\cfaw-news\\.venv\\Scripts\\python.exe", "-B", "-m", "evals.intelligence_g3.reproduce", "--manifest", "D:\\agent_project\\cfaw-news\\evals\\intelligence_g3\\manifests\\pr5_campaign.json", "--manifest-sha256", "56f2244812449db5ddb5a8bd2384cb302a3f9d66fb1205be167e9308da530daf", "--out", "D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-20261028-003\\prediction"]
```

## 全部指标/消融/预算/回访报告

# G3 PR5 offline AI development report

Synthetic, nonblind, reused development regression material. No independent human gold, held-out test, production readiness or real-user effect is established.

Event product families: 16; independent test families: 0.

Samples below count correlated event-by-case-by-budget states. Reprints, horizons and repeated seeds are not independent samples. Seeds are checked for equality and counted once.

| Variant | Axis/cell | Important recall n/d | Miss n/d | Duplicate n/d | nDCG DCG/IDCG | samples | families |
| --- | --- | --- | --- | --- | --- | --- | --- |
| b0 | all/all | 90/111 | 21/111 | 27/117 | 500.06/500.06 | 141 | 16 |
| b0 | budget/180 | 21/37 | 16/37 | 9/30 | 166.69/166.69 | 47 | 16 |
| b0 | budget/420 | 32/37 | 5/37 | 9/41 | 166.69/166.69 | 47 | 16 |
| b0 | budget/900 | 37/37 | 0/37 | 9/46 | 166.69/166.69 | 47 | 16 |
| b0 | revisit/1 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| b0 | revisit/3 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| b0 | revisit/7 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| b1 | all/all | 90/111 | 21/111 | 27/117 | 500.06/500.06 | 141 | 16 |
| b1 | budget/180 | 21/37 | 16/37 | 9/30 | 166.69/166.69 | 47 | 16 |
| b1 | budget/420 | 32/37 | 5/37 | 9/41 | 166.69/166.69 | 47 | 16 |
| b1 | budget/900 | 37/37 | 0/37 | 9/46 | 166.69/166.69 | 47 | 16 |
| b1 | revisit/1 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| b1 | revisit/3 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| b1 | revisit/7 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| b3 | all/all | 90/111 | 21/111 | 27/117 | 500.06/500.06 | 141 | 16 |
| b3 | budget/180 | 21/37 | 16/37 | 9/30 | 166.69/166.69 | 47 | 16 |
| b3 | budget/420 | 32/37 | 5/37 | 9/41 | 166.69/166.69 | 47 | 16 |
| b3 | budget/900 | 37/37 | 0/37 | 9/46 | 166.69/166.69 | 47 | 16 |
| b3 | revisit/1 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| b3 | revisit/3 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| b3 | revisit/7 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| b4 | all/all | 90/111 | 21/111 | 27/117 | 500.06/500.06 | 141 | 16 |
| b4 | budget/180 | 21/37 | 16/37 | 9/30 | 166.69/166.69 | 47 | 16 |
| b4 | budget/420 | 32/37 | 5/37 | 9/41 | 166.69/166.69 | 47 | 16 |
| b4 | budget/900 | 37/37 | 0/37 | 9/46 | 166.69/166.69 | 47 | 16 |
| b4 | revisit/1 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| b4 | revisit/3 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| b4 | revisit/7 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| no_duplicate | all/all | 90/111 | 21/111 | 27/117 | 500.06/500.06 | 141 | 16 |
| no_duplicate | budget/180 | 21/37 | 16/37 | 9/30 | 166.69/166.69 | 47 | 16 |
| no_duplicate | budget/420 | 32/37 | 5/37 | 9/41 | 166.69/166.69 | 47 | 16 |
| no_duplicate | budget/900 | 37/37 | 0/37 | 9/46 | 166.69/166.69 | 47 | 16 |
| no_duplicate | revisit/1 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| no_duplicate | revisit/3 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| no_duplicate | revisit/7 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| no_exploration | all/all | 90/111 | 21/111 | 27/117 | 500.06/500.06 | 141 | 16 |
| no_exploration | budget/180 | 21/37 | 16/37 | 9/30 | 166.69/166.69 | 47 | 16 |
| no_exploration | budget/420 | 32/37 | 5/37 | 9/41 | 166.69/166.69 | 47 | 16 |
| no_exploration | budget/900 | 37/37 | 0/37 | 9/46 | 166.69/166.69 | 47 | 16 |
| no_exploration | revisit/1 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| no_exploration | revisit/3 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| no_exploration | revisit/7 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| no_history | all/all | 90/111 | 21/111 | 27/117 | 500.06/500.06 | 141 | 16 |
| no_history | budget/180 | 21/37 | 16/37 | 9/30 | 166.69/166.69 | 47 | 16 |
| no_history | budget/420 | 32/37 | 5/37 | 9/41 | 166.69/166.69 | 47 | 16 |
| no_history | budget/900 | 37/37 | 0/37 | 9/46 | 166.69/166.69 | 47 | 16 |
| no_history | revisit/1 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| no_history | revisit/3 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| no_history | revisit/7 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| no_material | all/all | 90/111 | 21/111 | 27/117 | 500.06/500.06 | 141 | 16 |
| no_material | budget/180 | 21/37 | 16/37 | 9/30 | 166.69/166.69 | 47 | 16 |
| no_material | budget/420 | 32/37 | 5/37 | 9/41 | 166.69/166.69 | 47 | 16 |
| no_material | budget/900 | 37/37 | 0/37 | 9/46 | 166.69/166.69 | 47 | 16 |
| no_material | revisit/1 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| no_material | revisit/3 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| no_material | revisit/7 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| no_novelty_material | all/all | 90/111 | 21/111 | 27/117 | 500.06/500.06 | 141 | 16 |
| no_novelty_material | budget/180 | 21/37 | 16/37 | 9/30 | 166.69/166.69 | 47 | 16 |
| no_novelty_material | budget/420 | 32/37 | 5/37 | 9/41 | 166.69/166.69 | 47 | 16 |
| no_novelty_material | budget/900 | 37/37 | 0/37 | 9/46 | 166.69/166.69 | 47 | 16 |
| no_novelty_material | revisit/1 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| no_novelty_material | revisit/3 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| no_novelty_material | revisit/7 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| p1 | all/all | 90/111 | 21/111 | 27/117 | 500.06/500.06 | 141 | 16 |
| p1 | budget/180 | 21/37 | 16/37 | 9/30 | 166.69/166.69 | 47 | 16 |
| p1 | budget/420 | 32/37 | 5/37 | 9/41 | 166.69/166.69 | 47 | 16 |
| p1 | budget/900 | 37/37 | 0/37 | 9/46 | 166.69/166.69 | 47 | 16 |
| p1 | revisit/1 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| p1 | revisit/3 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| p1 | revisit/7 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |

## Interpretation and failures

B4 remains the baseline. P1 is not required to win; no independent stable improvement has been demonstrated. Per-job metrics, numerator/denominator, sample and family counts, data_source and undefined_reason are retained in metrics.json.

Failure records: 528, including every evaluable important miss and duplicate presentation. budget_unmet never removes an important event from a denominator. A protected item may fail to fit even when an alternative combination of minimum projections could fit; the registered greedy allocator does not solve a knapsack optimum.

nDCG@10 measures eligible rank order with all reference gains in IDCG; recall uses actual budget selection. Duplicate labels describe authored unchanged delivered events; opened does not establish knowledge. Domain coverage is lexical; exploration exposure is a feature proxy.

## Ablations and B2

no_history disables all history-dependent P1 score terms (novelty, material change, exploration, duplicate). no_material, no_novelty_material, no_exploration and no_duplicate zero their registered contributions without renormalization. Hard eligibility and mandatory update protection remain active in all variants. These are score ablations, not removal of safety/history validation. They use a separate experiment envelope, never a changed PR2/PR3 algorithm version.

B2 is reported separately in b2_g2_contribution. G2 already merged the event pool; B2 preserves identity and equals B1. G2 aggregation gain is undefined because there is no unmerged-document comparison arm. It is not credited to G3.

## Cost, reproducibility and limits

Actual prediction runs: 1716; semantic outputs per seed: 858; all cross-seed semantic hashes equal.

Measured prediction wall seconds (sum of per-job timers): 419.528818; mean 0.244481; max 2.247147. Process commands separately include startup, validation and serialization overhead.

External requests and model calls: 0, network guarded during prediction. Token count and provider cost are undefined (no model/provider invocation); no estimated billing or host electricity/hardware cost is asserted.

No confidence interval or significance claim: purposive reused nonblind families, no independent holdout. Reading time is a deterministic uncalibrated estimate. Material change uses attributed statement-set proxies. Source coverage gaps never confirm absence of updates.

The source release binds the exact working tree, anchor commit, tests, schemas, configs and frozen fixtures. It does not claim these uncommitted changes are a published commit. Remote CI, Linux portability, live providers, DB/API/frontend integration and user research are not verified by this report.

G4 requires independent PR5 review and owner approval. Preserve the offline input/output contract and diagnostics before any separate integration design.
