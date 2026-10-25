# G2-PR2 审查修复报告

本报告针对当前 PR2 审查中的两个 P1、一个 P2；未提供 P0。三条缺陷均已先复现、后添加失败回归、再最小修复。
**专项修复已验证；整体合并门槛尚未完成：本轮全量 pytest 等待支持本机 loopback 的执行权限批准。当前不建议合并。**

review_origin=`ai_development`，非盲开发复核，不是独立科研证据。未实现 PR3、未联网、未调用真实模型、未访问真实用户数据库或私人内容、未迁移 DB、未 commit/push。

## 基线和范围

- HEAD：`76ef14b531842ae449c4f907302218d2e2ea4c90`，修复前后相同。PR1/PR2 仍是既有未跟踪工作区资产；`.gitattributes` 是本轮开始前已有修改。
- 以修复前 316 文件 SHA 快照为 diff 基线，不把 `git diff HEAD` 当作完整变更范围。
- 修复仅改 3 个 PR2 运行文件、3 个 PR2 测试文件，新增本报告；其余 310 个基线文件字节不变。
- 既有受保护 G1/业务/锁文件 239 个、PR1 冻结快照 29 个全部匹配；PR2 剩余 39 个历史快照文件（包括全部配置、Schema、fixture、参考与 AI 复核）匹配。
- G1 manifest pin：`5608f6c9f20d283f9274308fa98a277c535eb0d8d828fd0d863d6e1faafde06f`。
- Schema/配置/阈值/参考版本和外部 pin 均未更新。相同 wire contract 下的缺陷修补由新源码 SHA 和新的运行 manifest 识别。
- 历史 PR1/PR2 验收报告、AI review 的旧源码哈希不改写；其通过结论只描述旧快照。本报告及 source-snapshot.json 绑定当前修复。

## 逐项 before / after

| 发现 | 修复前实际现象 | 最小修复 | 修复后断言 |
|---|---|---|---|
| P1-1 歧义文章同版本延续 | R0/R1/R2 均为 `G2_PR2_IDENTITY_GRAPH_INVALID / identity / birth_key`，复现 exit 1 | identity.py：同 document 的相同版本 ID 和内容 hash 延续原注册；跨文档/歧义新版本的语义匹配规则不放宽 | 三策略保留 key/revision；无新 transition；registry 仍 1 个；歧义新版本及跨文档仍不归并 |
| P1-2 比较版本污染 | R1/R2 将两文都提为 2.0，事件数 1，validation.ok=True；复现 exit 1 | features.py：版本只绑定原始标题主体短语；同时查看标题、正文及明确 release tag；冲突设 ambiguous 并清空版本 | 原复现提取 2.0/1.0，事件数 2；只有 Baseline 版本时为 null；目标版本冲突时 ambiguous；仓库主体规范化后仍保留原产品绑定 |
| P2-3 时间预检顺序 | 未来 available_at + 非法 paragraphs 先报 `SCHEMA_INVALID / input / visible_documents.0.candidate.paragraphs`；复现 exit 1 | replay.py：完整 G2ReplayInput parse 前复用 PR1 preflight_time | 优先 `FUTURE_VERSION / bridge / candidate.available_at / a:1`；完整对象 parse 与预测调用均 0；CLI exit 1 且无输出目录 |

P2 修复前仍拒绝输出，未观察到未来事实发布；本修复恢复时间预检顺序。G1 loader 读取整份预测 JSONL 字节的既有边界未改变。

新增 15 个参数化回归：连续性 3、保守歧义负例 2、主体版本/冲突 6、仓库规范化正例 2、未来正文形状及 CLI 2。修复前 13 failed / 2 passed，修复后 15 passed；没有删除原断言或改开发参考。

## 实际验证与命令

| 检查 | 实际结果 | exit code |
|---|---|---|
| before-1 / before-2 / before-3 | 三条原始触发均复现，断言失败 | 1 / 1 / 1 |
| red-tests | 13 failed / 2 passed / 41 deselected | 1 |
| after-1 / after-2 / after-3 | 同一触发脚本全部通过 | 0 / 0 / 0 |
| green-review-tests | 15 passed / 41 deselected | 0 |
| g2-tests | 128 passed，含 PR1 70 + 原 PR2 43 + 新增 15 | 0 |
| cross-pr-tests | 59 passed：G1 分组、时间可见性、版本、预测隔离、split 隔离、离线审计 | 0 |
| Ruff / G1、PR1、PR2 Schema / G1 strict manifest | 全部通过 | 全部 0 |
| seed / frontend offline build | 通过 | 0 / 0 |
| matrix | 57 次预测 + 19 次独立评测；每策略 G1 35 时点 + synthetic 16 时点；与旧冻结参考的原统计完全一致 | 0 |
| loopback-probe | 当前受限环境的 asyncio.new_event_loop 子进程 5 秒超时终止 | 3 |
| 完整 pytest | 未启动；等待批准所需执行权限；未填作 PASS，也未把环境探针冒称全量产品测试失败 | 未执行 |

修复矩阵的 R1/R2 主轨迹仍为 TP20/FP0/FN0/TN7；原 synthetic 集 R1 为 TP48/FP0/FN1/TN15，R2 为 TP49/FP0/FN0/TN15。这些是既有开发参考结果；45 个正 pair 来自 DUP10，不能当作独立真实效果证据。新增审查反例只加入测试，未修改冻结参考以提分。

以下为实际子进程 argv；每项的 cwd、UTC 起止、耗时、真实 exit code、完整日志 SHA 登记于同名 `.command.json`：

**before-1**（exit 1；cwd `D:\agent_project\cfaw-news`）

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", ".tmp/g2-pr2-review-fixes/reproduce.py", "1"]
```

日志 SHA256：`4fd87414fb2bc4b492d03dcc9883b3240e5dd3436290c4c34be3d0f1db1c40b3`。

**before-2**（exit 1；cwd `D:\agent_project\cfaw-news`）

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", ".tmp/g2-pr2-review-fixes/reproduce.py", "2"]
```

日志 SHA256：`4144a33257e022c787e684403493cae40b34bdda65774c71f977d6aaddfdc02a`。

**before-3**（exit 1；cwd `D:\agent_project\cfaw-news`）

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", ".tmp/g2-pr2-review-fixes/reproduce.py", "3"]
```

日志 SHA256：`c255a3750978291bf807d97ebdee231604fa2101349b3bdc277df9bc3db4374d`。

**red-tests**（exit 1；cwd `D:\agent_project\cfaw-news`）

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "pytest", "tests/evals/g2/pr2/test_identity.py", "tests/evals/g2/pr2/test_relations.py", "tests/evals/g2/pr2/test_replay.py", "-q", "-p", "no:cacheprovider", "-k", "review", "--basetemp=.tmp/g2-pr2-review-red", "--junitxml=.tmp/g2-pr2-review-fixes/red.xml"]
```

日志 SHA256：`c1ff987f1f9baab739ecde5f656519089bfc1e8fd6f7f79268565fa8bd914f43`。

**after-1**（exit 0；cwd `D:\agent_project\cfaw-news`）

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", ".tmp/g2-pr2-review-fixes/reproduce.py", "1"]
```

日志 SHA256：`ca80792cc296d33eb99b2c8599a3cf54c59c3fac647681e8ebca935adbb0fe7d`。

**after-2**（exit 0；cwd `D:\agent_project\cfaw-news`）

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", ".tmp/g2-pr2-review-fixes/reproduce.py", "2"]
```

日志 SHA256：`9649900cea732f2afd1993df3118caa62d0b1f41acfbf724b10a046c661461cb`。

**after-3**（exit 0；cwd `D:\agent_project\cfaw-news`）

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", ".tmp/g2-pr2-review-fixes/reproduce.py", "3"]
```

日志 SHA256：`f0a790280601b0200654aec0a7c42727dcedca7cd524c4d9e06e0f9cae0477b5`。

**green-review-tests**（exit 0；cwd `D:\agent_project\cfaw-news`）

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "pytest", "tests/evals/g2/pr2/test_identity.py", "tests/evals/g2/pr2/test_relations.py", "tests/evals/g2/pr2/test_replay.py", "-q", "-p", "no:cacheprovider", "-k", "review", "--basetemp=.tmp/g2-pr2-review-green", "--junitxml=.tmp/g2-pr2-review-fixes/green.xml"]
```

日志 SHA256：`803e81eae02433d6bb94cf1b9b881730dc3a3f3dcd21d4b9563b1b446755c81a`。

**g2-tests**（exit 0；cwd `D:\agent_project\cfaw-news`）

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "pytest", "tests/evals/g2", "-q", "-p", "no:cacheprovider", "--basetemp=.tmp/g2-pr2-review-g2", "--junitxml=.tmp/g2-pr2-review-fixes/g2.xml"]
```

日志 SHA256：`a37342440520fab5bcb73ddb06e8d72050b0591046915fadf894df578418bf00`。

**cross-pr-tests**（exit 0；cwd `D:\agent_project\cfaw-news`）

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "pytest", "tests/evals/test_event_grouping.py", "tests/evals/test_temporal_visibility.py", "tests/evals/test_document_versions.py", "tests/evals/test_prediction_isolation.py", "tests/evals/test_prediction_split_isolation.py", "tests/evals/test_offline_isolation.py", "-q", "-p", "no:cacheprovider", "--basetemp=.tmp/g2-pr2-review-cross", "--junitxml=.tmp/g2-pr2-review-fixes/cross-pr.xml"]
```

日志 SHA256：`842e710aba59ee7da1c73762763683b9d5c809ce4b6f8d4a5225e0be1a20ce82`。

**ruff**（exit 0；cwd `D:\agent_project\cfaw-news`）

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "ruff", "check", "backend", "tests", "evals"]
```

日志 SHA256：`82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`。

**schema-g1**（exit 0；cwd `D:\agent_project\cfaw-news`）

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "evals.intelligence_v1.contracts", "--check-schemas"]
```

日志 SHA256：`ad541cc67a0a6b6ce43b44815465079cd8b104a992b74d4c1a670e767b546d7d`。

**schema-pr1**（exit 0；cwd `D:\agent_project\cfaw-news`）

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "evals.intelligence_g2.contracts", "--check-schemas"]
```

日志 SHA256：`a809da7e3eeb608fdce4300ac3ac61ce71461ebdd5e50803baaede51ffa8f3e1`。

**schema-pr2**（exit 0；cwd `D:\agent_project\cfaw-news`）

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "evals.intelligence_g2.pr2.contracts", "--check-schemas"]
```

日志 SHA256：`ffc3a2599f9fe6d9e1046f4e8cf20d19c948e76b87b838f97e144cb2df555923`。

**manifest-g1**（exit 0；cwd `D:\agent_project\cfaw-news`）

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "evals.intelligence_v1.validate", "--manifest", "evals/intelligence_v1/manifests/dataset_manifest.json", "--strict"]
```

日志 SHA256：`ae200140ab0b4b55cfc9964459369e2e3a0970039dbfb7359501ad56ac18aa38`。

**seed**（exit 0；cwd `D:\agent_project\cfaw-news`）

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "evals/run_baseline.py", "--output", ".tmp/g2-pr2-review-fixes/seed.json"]
```

日志 SHA256：`c3a5acba59816fa76e661bfe3a5d9d8f66d52f93b6991225cd4d4533f2724613`。

**frontend**（exit 0；cwd `D:\agent_project\cfaw-news\frontend`）

```json
["C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "npm.cmd --offline run build"]
```

日志 SHA256：`34f1ec9519934eca4bb12449c9216eb892e2e26ae19dc55be3c0c875aa7a4a37`。

**matrix**（exit 0；cwd `D:\agent_project\cfaw-news`）

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", ".tmp/g2-pr2-evidence/run_matrix.py", "review-fixes-001"]
```

日志 SHA256：`7377157f893b1d43040f67ece8e71adb51162a0381390397c3084443b17d9e6f`。

**loopback-probe**（exit 3；cwd `D:\agent_project\cfaw-news`）

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", ".tmp/g2-pr2-review-fixes/loopback_probe.py"]
```

日志 SHA256：`d11837bd9da0ceae8ceaccb4b7208dab8dcaf2e7524465bece0a0c0a5eae553a`。

## 证据、未关闭门槛与回滚

- 本轮证据目录：`D:\agent_project\cfaw-news\.tmp\g2-pr2-review-fixes`；包含 before.json、before/after 日志、red/green/G2/cross-PR JUnit、命令登记、preservation.json、source-snapshot.json、verification-summary.json。
- 全矩阵：`D:\agent_project\cfaw-news\.tmp\g2-pr2-evidence\review-fixes-001\matrix.json`；SHA256 `15cbcf8ab95635ba197e4660f8a2faf75e35fbc0573b4093e66b5b4986409aa3`。语义产物在 `.tmp/evals/g2/pr2-review-fixes-001/`，未覆写旧结果。
- artifact-index.json 记录上述工件、运行源码和本报告的真实文件字节 SHA；它不自哈希，避免循环依赖。
- 三条审查缺陷无未关闭项；**未关闭验收项为当前源码的全量回归**。5 秒环境探针仅说明当前本地事件循环不可用；不会代替完整测试结果。
- 下一步仅请求批准本次完整 pytest 在支持本机 loopback/socketpair 的执行环境运行，不安装依赖、不改 Schema、不迁移 DB、不触动 G1 frozen。批准前不会自行扩大权限，也不会建议合并。

待批准命令（尚未执行，不能计作验证证据）：

```powershell
& .\.venv\Scripts\python.exe -B .tmp/g2-pr2-review-fixes/record.py full-tests D:/agent_project/cfaw-news/.venv/Scripts/python.exe -B -m pytest -q -o faulthandler_timeout=120 --basetemp=.tmp/g2-pr2-review-full --junitxml=.tmp/g2-pr2-review-fixes/full.xml
```

回滚仅撤回这 3 个运行文件中的补丁、对应新增测试及本报告；保留已有 PR1/PR2 工作区、计划文档、冻结资产和历史输出。版本提取仍是保守规则语法，复杂多产品/多版本叙述允许弃权，不承诺完整实体抽取能力。
