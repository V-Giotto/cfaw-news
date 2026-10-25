# G2-PR3 审查修复报告

状态：三项审查问题已修复；当前全量回归通过，可交管理员审阅合并。

验收类别：`ai_development`。同一 Codex 编写合成反例、实现与复核，非盲、非独立科研证据；未调用外部模型。

## 基线与修改边界

HEAD `76ef14b531842ae449c4f907302218d2e2ea4c90` 未变。审查前登记 359 个受控文件，其中 357 个保持原字节；仅修改 PR3 `scope.py`、`history.py`，新增专项测试和本报告。
G1 frozen、PR1/PR2、Schema v1/v2/v3、配置、fixture、参考标签、旧验收报告、锁文件、.gitattributes 及原工作区文档均未改变。旧错误输出保留为历史证据，不覆盖；修复后重新生成前缀与运行工件。未开发 PR4/PR5、UI、API 或生产持久化，未迁移数据库、联网、安装依赖或 commit/push。

## 逐项复现与最小修复

| 问题 | 修复前实际现象 | 当前修复与断言 |
|---|---|---|
| P1 / A | 原脚本 exit 1；否定撤回仍生成 retracts，旧主张 retracted，validation.ok=True | 完整肯定语法识别生命周期行为；否定、条件和未来意向 marker=none、无 transition，旧主张保持 historical/source_attributed |
| P1 / B | 原脚本 exit 1；accuracy 40 percentage points 撤回了 speed 40% | 同来源/文档、主体/版本、非歧义旧目标、指标、原数量/单位/限定词以及 same_declared_scope 全部匹配且唯一才迁移；不完整目标产生 unresolved_withdrawal |
| P2 / C | 原脚本 exit 1；PR2 已新建 v2.0 事件，旧 v1.0 Claim 仍被加入其历史 Claim | 当前版本按当前成员归属；历史 Claim 从原 membership 出发，仅沿 PR2 显式身份 transition 路径迁移；版本冲突排除、split 不唯一则弃权；无路径时保留原档案归属 |

肯定语法与 proposition 的测量歧义分开：更正段落可包含旧值与新值，仍需单独明确语法和完整旧目标；不能仅因为出现 withdraw/correction 关键词就改变历史。

迁移记录携带实际 PR2 transition ID。文档版本链仅能在已授权 split 后消歧，不能授予跨事件迁移权限。旧 Claim、旧判断快照和旧 membership 前缀保持不变；当前活动事件不包含无身份依据的旧事件主张。

## 回归、正控与交叉校验

新增 20 条测试：否定/将来/可能/条件/否定更正，指标与单位错配、限定词错配、缺指标/缺 scope，合法更正/撤回、匹配 at_most/at_least，文档改作新事件、兼容版本更新、显式 merge 的历史归属，以及伪造 transition/membership 的错误码断言。
初始 15 条新测试在修复前实际为 12 failed / 3 passed；修复后新增及相邻历史/scope 用例为 37 passed。全 G2 为 223 passed（PR1 70 + PR2 58 + PR3 95），包括 R0/R1/R2 的 35 个时点身份/分区兼容性、merge/split、时间预检、权限与预测/参考隔离。

全部断言保留业务结果和 code/stage/field/record_id 检查；没有通过改参考标签、降低业务断言或全量弃权通过正控。

| 检查 | 当前结果 |
|---|---|
| 原始 A/B/C 复验 | before 均 exit 1；after 均 exit 0 |
| 专项与 G2 | 37 passed；223 passed，均 exit 0 |
| 新矩阵 | 23 次预测 API 调用后，独立进程完成 23 次评测；35 G1 + 19 synthetic 时点，均 exit 0 |
| Ruff / 四套 Schema / G1 strict | 全部 exit 0 |
| seed / 前端 offline build | 全部 exit 0；seed 使用内存数据库 |
| 当前完整 pytest | 774 passed / 1 skipped，exit 0 |

合成评测：28/28 抽取、类型与状态，46 条方向、150/150 scope 字段、28/28 数字、3/3 必需缺口；无参考差异。G1 35 个时点只作结构回归，没有 PR3 语义参考分数。重复时点和同一 AI 复核不算独立样本。

## 真实失败、中间修订与环境边界

- 第一次修复后定向运行是 2 failed / 30 passed：一条测试错误地用排序档案首项指代旧 Claim，已改为按不可变 claim_key 精确取值（保留相等断言）；另一个反例暴露缺 Task 时生命周期语法未识别，已识别其他显式 scope 字段起点，仍由完整 scope 校验阻止变更。原测试版本与失败日志保留。
- 第一次矩阵被 OUTPUT_EXISTS 拒绝（exit 1）；运行脚本复用了旧名称，未覆盖旧结果。改用全新 review-fixes-matrix-001 目录完成，不改变产品覆盖策略。
- 当前沙箱 asyncio 本机探针 5 秒超时（exit 3），属于环境限制。管理员随后明确批准仅本轮完整 pytest 在沙箱外执行；没有扩展其他权限。

完整回归唯一跳过项（实际 JUnit）：

```json
[
  {
    "classname": "tests.evals.test_provenance_and_rights",
    "name": "test_symlink_outside_bundle_rejected_if_supported",
    "message": "symlink creation unavailable: 1314",
    "detail": "D:\\agent_project\\cfaw-news\\tests\\evals\\test_provenance_and_rights.py:94: symlink creation unavailable: 1314"
  }
]
```

完整日志中的依赖弃用告警如实保留；未为此安装或更改依赖。

## 实际命令、退出码与日志摘要

下列 argv 为真实子进程命令；每份 command.json 记录 cwd、UTC 起止时间、耗时、exit code 与原始日志 SHA。矩阵内部 API 调用和每个输出 manifest pin 另见 predictions/evaluation.json。

**reproduce-A-before**：exit `1`，1.620s；log SHA `e52bdd5ad79813b87d47493bafa26c62d28d00539bad57c71f4d835f07f44e29`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", ".tmp/g2-pr3-review-fixes-001/reproduce.py", "A"]
```

**reproduce-B-before**：exit `1`，1.595s；log SHA `cde9fe458ac62e606f86a778816507747caa9285024e7da8bcffc12acc2c1e90`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", ".tmp/g2-pr3-review-fixes-001/reproduce.py", "B"]
```

**reproduce-C-before**：exit `1`，1.590s；log SHA `95edee41c0bc90f1d356b12cb6a4d66c2ecd3548feb13ebedbc6d6cd6e00cd72`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", ".tmp/g2-pr3-review-fixes-001/reproduce.py", "C"]
```

**regressions-red**：exit `1`，4.001s；log SHA `9bb9c5eca3a5d11e90dfaf52133e8601bdc9ebdc5e7589562a1e06b6824ce8e9`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "pytest", "tests/evals/g2/pr3/test_review_regressions.py", "-q", "-p", "no:cacheprovider", "--basetemp=.tmp/g2-pr3-review-red", "--junitxml=.tmp/g2-pr3-review-fixes-001/regressions-red.xml"]
```

**regressions-green**：exit `1`，4.982s；log SHA `7d485df8f96b0dc9dc7b10e1a73495afeba8d2d39d0fd155d0a6b758a3c3abf2`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "pytest", "tests/evals/g2/pr3/test_review_regressions.py", "tests/evals/g2/pr3/test_history.py", "tests/evals/g2/pr3/test_scope.py", "-q", "-p", "no:cacheprovider", "--basetemp=.tmp/g2-pr3-review-green", "--junitxml=.tmp/g2-pr3-review-fixes-001/regressions-green.xml"]
```

**regressions-green-2**：exit `0`，4.118s；log SHA `196e4347ed407297fea757c73cf861550a6837a0070e8f5aa70b0704e4489ed0`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "pytest", "tests/evals/g2/pr3/test_review_regressions.py", "tests/evals/g2/pr3/test_history.py", "tests/evals/g2/pr3/test_scope.py", "-q", "-p", "no:cacheprovider", "--basetemp=.tmp/g2-pr3-review-green-2", "--junitxml=.tmp/g2-pr3-review-fixes-001/regressions-green-2.xml"]
```

**regressions-guards**：exit `0`，4.521s；log SHA `041b1bd7703bb4aea7cf921d18d565d332c2ababcf2ac841c4cdcd27a5726940`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "pytest", "tests/evals/g2/pr3/test_review_regressions.py", "tests/evals/g2/pr3/test_history.py", "tests/evals/g2/pr3/test_scope.py", "-q", "-p", "no:cacheprovider", "--basetemp=.tmp/g2-pr3-review-guards", "--junitxml=.tmp/g2-pr3-review-fixes-001/regressions-guards.xml"]
```

**reproduce-A-after**：exit `0`，1.546s；log SHA `b3f0c3cbfab938e3d23d30c459fc812992dc75a8f97f65d469f5da2188ced218`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", ".tmp/g2-pr3-review-fixes-001/reproduce.py", "A"]
```

**reproduce-B-after**：exit `0`，1.513s；log SHA `697bd221eaff6c4b59e64423512a1cb454a366a6b0d25032f84773f36b3be477`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", ".tmp/g2-pr3-review-fixes-001/reproduce.py", "B"]
```

**reproduce-C-after**：exit `0`，1.536s；log SHA `69195723e2fdbd787d8d15f88386f1682a9a2743f0ef0f5ed292c945728759e4`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", ".tmp/g2-pr3-review-fixes-001/reproduce.py", "C"]
```

**matrix-prediction**：exit `1`，1.290s；log SHA `dbddb5d384ed8ec1ef2fb7be380805f8c681c99656c838fb6e354c73e2866a12`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", ".tmp/g2-pr3-review-fixes-001/run_matrix.py", "matrix-001"]
```

**g2**：exit `0`，108.760s；log SHA `14d1cbfbb884791947cc499c817fd597456741a338c60182db9bb79b58926988`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "pytest", "tests/evals/g2", "-q", "-p", "no:cacheprovider", "--basetemp=.tmp/g2-pr3-review-g2", "--junitxml=.tmp/g2-pr3-review-fixes-001/g2.xml"]
```

**loopback-probe**：exit `3`，5.225s；log SHA `d11837bd9da0ceae8ceaccb4b7208dab8dcaf2e7524465bece0a0c0a5eae553a`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", ".tmp/g2-pr2-review-fixes/loopback_probe.py"]
```

**ruff**：exit `0`，0.320s；log SHA `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "ruff", "check", "backend", "tests", "evals"]
```

**seed**：exit `0`，1.709s；log SHA `47a34c6ad8472477a722e7e42acf81f9733057ba9b9046eccf1084995709b69f`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "evals/run_baseline.py", "--output", ".tmp/evals/g2/pr3-review-seed-001.json"]
```

**schema-g1**：exit `0`，0.982s；log SHA `ad541cc67a0a6b6ce43b44815465079cd8b104a992b74d4c1a670e767b546d7d`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "evals.intelligence_v1.contracts", "--check-schemas"]
```

**schema-pr1**：exit `0`，1.094s；log SHA `a809da7e3eeb608fdce4300ac3ac61ce71461ebdd5e50803baaede51ffa8f3e1`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "evals.intelligence_g2.contracts", "--check-schemas"]
```

**frontend**：exit `0`，9.467s；log SHA `2ebbaaf6ecf1dabe2969c999fc340d853e1c624830dc4ea84977c3f2f6b9dcd6`。

```json
["C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "npm.cmd --offline run build"]
```

**schema-pr2**：exit `0`，1.083s；log SHA `ffc3a2599f9fe6d9e1046f4e8cf20d19c948e76b87b838f97e144cb2df555923`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "evals.intelligence_g2.pr2.contracts", "--check-schemas"]
```

**schema-pr3**：exit `0`，1.138s；log SHA `27303a3b8249fbfd930481b365912d74dd58bf322a1a4e137ceee3509558cf51`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "evals.intelligence_g2.pr3.contracts", "--check-schemas"]
```

**manifest-g1**：exit `0`，1.555s；log SHA `ae200140ab0b4b55cfc9964459369e2e3a0970039dbfb7359501ad56ac18aa38`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "evals.intelligence_v1.validate", "--manifest", "evals/intelligence_v1/manifests/dataset_manifest.json", "--strict"]
```

**matrix-prediction-2**：exit `0`，18.545s；log SHA `f149d39fca8631e6291484543e3bb8cda55a08dae51ad5c49bc164df597d8b9d`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", ".tmp/g2-pr3-review-fixes-001/run_matrix.py", "review-fixes-matrix-001"]
```

**full**：exit `0`，695.032s；log SHA `2dc52157c41774f42411170b45a7b6644e0ae69d7cb20dd120793891632713b2`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "pytest", "-q", "-o", "faulthandler_timeout=120", "--basetemp=.tmp/g2-pr3-review-full", "--junitxml=.tmp/g2-pr3-review-fixes-001/full.xml"]
```

**matrix-evaluation**：exit `0`，18.726s；log SHA `3ac2876bd4ba27794466011ba43740fd794aa925f29f10e42b9d3a79f1b34ccf`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", ".tmp/g2-pr3-review-fixes-001/evaluate_matrix.py", "review-fixes-matrix-001"]
```

## Hash、复核与未关闭项

- G1 外部冻结 pin：`5608f6c9f20d283f9274308fa98a277c535eb0d8d828fd0d863d6e1faafde06f`。
- PR3 原 fixture manifest SHA：`94a8d248900af2202755d92b60631e68af24ae0ba673032503dc7492cdf6b918`（未改）。
- PR3 原参考 v2 manifest SHA：`cae113075d3fd366199e0b92886143e7dc893361b20021b50ffaeae12511bfdf`（未改）。
- 当前 runtime/test source-snapshot SHA：`dcae3f7c96886aeea0be6d73fe071f76983b0eb2181a4bdeb7f252fd18e35788`。
- 本次属于既有契约的实现缺陷修复，Schema/枚举/权限/配置及哈希材料不扩展；代码差异由 runtime source SHA 绑定。旧源码 pin 的历史工件不冒充当前复测；不混接旧状态。
- 证据目录：`D:\agent_project\cfaw-news\.tmp\g2-pr3-review-fixes-001`。before.json、before-source/、各次 JUnit、error_analysis.jsonl、preservation.json、verification-summary.json、矩阵及 artifact-index.json 保留实际记录。索引绑定报告/源码/日志，无自哈希循环。

审查列出的三项问题已关闭。请求范围内无剩余产品失败；可提交管理员审阅，Git 操作仍由管理员决定。

保留限制：有限肯定语法之外的撤回/更正（包括未支持的自然语言表达）仅保留原文并不执行生命周期变更；未知 scope/指标/单位不能匹配旧目标。无唯一身份后继时历史 Claim 留在档案，不猜测新归属。independently_supported 仍禁止，独立支持数为 0，独立研究验证 not_evaluated。

回滚仅恢复本次 scope.py/history.py 修改并移除新专项测试/报告；保留此前工作区、冻结资产及历史工件，无数据库回滚。
