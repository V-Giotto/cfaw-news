# G2-PR4 审查修复：带引号的凭据字段

状态：审查 P1 已修复；新增 15 条及全部 303 条 G2 回归通过。两次获批完整 pytest 均未通过（首次 2 failed / 852 passed；重跑 1 failed / 853 passed；各 1 skipped、exit 1）。失败均有记录，定向复测通过不替代完整回归；共享导出 IO 阻断未关闭，当前不建议合并。

本报告记录当前 PR 的修复；review_origin=ai_development，non_blind=true，independent_validation=false。未读取真实凭据；所有负例仅使用 TEST_ONLY 合成 canary。历史 PR4 验收报告、参考标签与运行工件保留，不将其全量 839 passed 计作此次修复的新证据。

## 基线、范围与修改

- HEAD：76ef14b531842ae449c4f907302218d2e2ea4c90；PR1–PR4 原本在未跟踪工作区，.gitattributes 原有修改保留。
- 本轮检查并登记 501 个已有受控文件。仅修改原有 `pr4/policy.py`、`pr4/validate_output.py`；新增 `pr4/sensitive.py`、`tests/evals/g2/pr4/test_review_credentials.py` 和本报告。
- G1、PR1–PR3、所有 Schema、锁文件、现有 fixture/labels、旧报告、业务/前端源码不变。不增加 Schema 字段、权限或依赖；不联网、不调用真实模型、不迁移 DB、不 commit/push；不实现 PR5。
- G1 外部 pin 保持 5608f6c9f20d283f9274308fa98a277c535eb0d8d828fd0d863d6e1faafde06f。

## 修复前后与最小实现

1. 先复现原问题：正常 PR3→PR4 路径生成 focus，validation.ok=True，合成值同时进入 what_happened、Citation 和完整序列化结果；复验命令 exit 1。仅记录泄漏布尔值，不导出真实凭据。
2. 先添加回归再修生产代码：新测试修复前 12 failed / 3 passed，修复后原样运行 15 passed。未删失败断言、未改变既有标签或把失败改为 PASS。
3. PR4 成文边界新增检测：保留 PR3 既有 PEM/未加引号字段检测，并识别双引号/单引号凭据键（api_key、password、access_token、secret 及原有大小写/分隔符形式）与非空带引号值。命中后直接走既有 sensitive_evidence hold，模板不被调用；事实、ClaimSummary、选中 Claim 和输出 Citation 为空，完整 GenerationResult 中无 canary。
4. 输出验证单独递归检查实际字符串值，不在转义后的外层 JSON 文本上做匹配。输出任何位置再次注入同类内容时，拒绝为 `G2_PR4_FACT_PROVENANCE_INVALID / output / sensitive_text`，诊断无原文。仍使用现有 Schema/错误码/层级语义。
5. 普通配置、api_key_enabled/api_key_name 及空凭据示例正控仍可生成有引用的 focus；不靠全部 hold 通过。

## 本轮实际命令与结果

精确 argv、cwd、UTC 时间、耗时、exit code、日志 SHA 保存在 `.tmp/g2-pr4-review-fixes-001/<name>.command.json`。这些是本轮执行结果，非历史验收复用。

| 命令记录 | exit | 日志 SHA256 |
|---|---:|---|
| before-reproduction | 1 | `14f01c4dba271b57f9f28b665e605c2101808d8e649ae256f6a3dbe8ed875b64` |
| regression-before | 1 | `ecbf0e3ba094b8bc8229025f91d567a8f8b0cc99b9a59041bae693a278065fbb` |
| after-reproduction | 0 | `9c37cd9008dce6a27e25b918defa6601ef33b2a73e6600b2677fd5b720ef0951` |
| regression-after | 0 | `ed02dfd83477d280fad84e60b2cc01095cff22e7822cdb17dd5c039ae35011ad` |
| g2 | 0 | `cd825b34a1f66df0e81c4a9d1b99ff17e88751a814128e96b78b204958e6bf51` |
| matrix | 0 | `2a2ff5bc77912a8c6d7abeaa1d173e0514b4b4c2fed71d486c1600ac90dfe6f3` |
| ruff | 0 | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| g1-schema | 0 | `ad541cc67a0a6b6ce43b44815465079cd8b104a992b74d4c1a670e767b546d7d` |
| pr1-schema | 0 | `a809da7e3eeb608fdce4300ac3ac61ce71461ebdd5e50803baaede51ffa8f3e1` |
| pr2-schema | 0 | `ffc3a2599f9fe6d9e1046f4e8cf20d19c948e76b87b838f97e144cb2df555923` |
| pr3-schema | 0 | `27303a3b8249fbfd930481b365912d74dd58bf322a1a4e137ceee3509558cf51` |
| pr4-schema | 0 | `a01abfe266c318861e969fd32356b29343cd6052cbbc61f0d7304dc7c71279de` |
| g1-strict | 0 | `ae200140ab0b4b55cfc9964459369e2e3a0970039dbfb7359501ad56ac18aa38` |
| seed | 0 | `727f90ff9bea2b3460f06a6858bb253e6afb8e5e0f8c544c85be0855f20c2b5a` |
| frontend | 0 | `e857cea320f77a369bd1aba7cac1b30fcdd6ba6ba041ab4b8ac001e725369c08` |
| loopback-probe | 3 | `d11837bd9da0ceae8ceaccb4b7208dab8dcaf2e7524465bece0a0c0a5eae553a` |

主要运行命令（仓库根目录；完整实际 argv 见 command.json）：

```powershell
.\.venv\Scripts\python.exe -B .tmp/g2-pr4-review-fixes-001/reproduce.py
.\.venv\Scripts\python.exe -B -m pytest tests/evals/g2/pr4/test_review_credentials.py -q -p no:cacheprovider --basetemp=.tmp/g2-pr4-review-after --junitxml=.tmp/g2-pr4-review-fixes-001/regression-after.xml
.\.venv\Scripts\python.exe -B -m pytest tests/evals/g2 -q -p no:cacheprovider --basetemp=.tmp/g2-pr4-review-g2 --junitxml=.tmp/g2-pr4-review-fixes-001/g2.xml
.\.venv\Scripts\python.exe -B .tmp/g2-pr4-review-fixes-001/matrix.py
.\.venv\Scripts\python.exe -B -m ruff check backend tests evals
# G1 与 G2 PR1–PR4 的 contracts --check-schemas 各自执行
.\.venv\Scripts\python.exe -B -m evals.intelligence_v1.validate --manifest evals/intelligence_v1/manifests/dataset_manifest.json --strict
.\.venv\Scripts\python.exe -B evals/run_baseline.py --output .tmp/evals/g2/pr4-review-fixes-seed.json
# frontend：npm.cmd --offline run build
```

- 原复验脚本：before exit 1 → after exit 0；after 为 hold / sensitive_evidence，事实、引用、完整结果的泄漏布尔值均为 false。
- 新专项：15 passed，含六种凭据键/引号变体、三种普通配置正控、五种输出侧注入，以及真实离线 CLI 的所有产物字节不含 canary。强制模板 spy 证明敏感输入不会到达表达适配器。
- 全部 G2：303 passed；覆盖原 PR4 的 52 项及 PR1–PR3/历史修复，包括否定撤回、同数字不同指标、scope 指标污染、旧 Claim 归属、未来预检及预测隔离。
- 固定矩阵：38 次预测/独立评测、35 个既有时点 + 40 个开发/兼容时点，R0/R2 父分组保持；266 份合法样例语义文件与修复前逐字节相同（run_manifest/trace 因代码 pin/真实执行时间而单列）。不为此修改任何标签。
- 五套 Schema、G1 strict、全域 Ruff、seed、前端离线构建 exit 0。
- 审查仅报告的 P1 在上述复验范围已关闭；没有将本次测试称为独立研究验证或通用凭据识别能力证明。

## 证据、边界与未关闭项

- `.tmp/g2-pr4-review-fixes-001/baseline.json`、`preservation.json`：原有受控资产的 before/after SHA；Schema、labels、历史报告字节不变。
- `source-snapshot.json`：四个代码/测试文件 SHA、真实记录时间、所见上下文和非盲 AI 开发复核说明。
- `regression-before.xml`、`regression-after.xml`、`g2.xml` 及配套日志/命令记录：真实 red/green 证据。
- `matrix-verified.json`、`semantic-comparison.json`：逐次工件 pin 与 266 文件一致性检查；新预测输出只写入 `.tmp/evals/g2/pr4-review-fixes-001/`。
- 本检测是 PR4 有限文本格式的发布门禁，不是通用 DLP；任意编码、混淆或其他字段名称的凭据识别不在本次证明范围内。没有读取私人文件或真实凭据来测试。
- PR3 原始预测工件/输入可含合成 canary，属于此次复验的输入边界；保持它们原样。此次保证与断言针对 PR4 返回值、输出文件及安全诊断，不声称已清洗上游历史工件。
- 完整 pytest 未关闭：两次本轮获批的单次授权分别用于 full-approved 和 full-retry，均实际 exit 1。三项失败的定向复测通过不能替代全量；两次授权均已使用，不自动继续沙箱外重试。

回滚只撤回本轮 PR4 两处修改、新敏感检测模块和专项测试；保留新报告及本地证据、所有旧数据与工件。不涉及数据库回滚。

## 本轮首次获批全量失败与定向核验

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -o faulthandler_timeout=120 --basetemp=.tmp/g2-pr4-review-full --junitxml=.tmp/g2-pr4-review-fixes-001/full-approved.xml
```

- 真实结果：2 failed / 852 passed / 1 skipped / 1 warning，exit 1，耗时 572.73 秒。
- 日志 SHA256：`ee32281cb00e22dc3eea337f8070e7baaf9fb111dce5a1137a78179d59ffb505`。
- JUnit SHA256：`0e2ec0d959076939b516b5842c09201c0bfddfb69b74f60e6585052a18136ee2`。
- `pr3/test_replay.py::test_parent_reference_artifact_is_rejected_without_opening_it`：构造父 PR2 工件时，既有共享 `write_payloads` 的 staging.rename(output) 抛出 PermissionError / WinError 5，尚未进入 PR4 生成。
- `pr4/test_replay.py::test_T36_cli_seed_prefix_snapshot_immutability_and_independent_evaluation`：CLI 返回 EXPORT_IO_ERROR；安全诊断屏蔽了底层异常，不能断言与前一项同根因，也不把它改写成环境 PASS。
- 相同源码、原断言，在默认沙箱定向重跑这两项得到 2 passed / exit 0，未修改共享写入器或遗留测试。此结果仅说明该次定向未复现，不证明根因已修复。

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/evals/g2/pr3/test_replay.py::test_parent_reference_artifact_is_rejected_without_opening_it tests/evals/g2/pr4/test_replay.py::test_T36_cli_seed_prefix_snapshot_immutability_and_independent_evaluation -q -p no:cacheprovider --basetemp=.tmp/g2-pr4-review-targeted --junitxml=.tmp/g2-pr4-review-fixes-001/full-failures-targeted.xml
```

- 定向日志 SHA256：`d908d28ebede472dfba96d442511dc50143d7eb563051ad7f3a6e09077e0d030`。完整命令/时间见 `full-failures-targeted.command.json`。
- 首次全量失败完整保留在日志、JUnit、full-failure-analysis.json；源指纹未漂移、既有文件仍只有获准的两处 PR4 源码修改。
- 不为通过全量而修改冻结 G1、放宽断言或引入共享导出重试。本轮再次完整回归若需沙箱外权限，将单独请求新的单次授权。

## 再次获批完整重跑：仍未通过

管理员直接回复“批准再完整重跑一次”。源码、断言与测试集不变，使用新临时目录。

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -o faulthandler_timeout=120 --basetemp=.tmp/g2-pr4-review-full-retry --junitxml=.tmp/g2-pr4-review-fixes-001/full-retry.xml
```

- 实际结果：1 failed / 853 passed / 1 skipped / 1 warning；exit 1，耗时 608.14 秒。
- 开始：2026-10-25T04:58:27.754011+00:00；结束：2026-10-25T05:08:35.898836+00:00。
- 日志 SHA256：`4ba5bdac61aa199021acad97f66c9925b9aaf0230a4273c0ef36fc62be34d203`。
- JUnit SHA256：`1936dc042e513d0417fdaf9d4d7a0f32132a66a93d98b9e447793c97484fa24f`。
- 失败用例为 `pr4/test_replay.py::test_path_escape_rejected_without_external_write`。错误发生在 export_evidence 构造 PR3 父工件时，`evals/intelligence_g2/replay.py:105` 的 staging.rename(output) 抛出 PermissionError / WinError 5；尚未进入 PR4 路径逃逸校验。与首次直接栈共同指向既有共享原子目录改名步骤，但具体权限/占用根因未定位，不能声称已消除或指定为某个外部程序。
- 同一源码、原断言，默认沙箱对这一个用例再定向执行：1 passed / exit 0。该结果只表示该次没有复现。

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/evals/g2/pr4/test_replay.py::test_path_escape_rejected_without_external_write -q -p no:cacheprovider --basetemp=.tmp/g2-pr4-review-path-targeted --junitxml=.tmp/g2-pr4-review-fixes-001/retry-failure-targeted.xml
```

- 定向日志 SHA256：`1e70502463637ad6afb6c8effcfa511a763c4b8c2aa3203a3733af0ab20e4e6e`。
- 新增 15 项凭据检测/普通配置/输出拒绝/CLI 产物回归，在两次完整运行中各 15 项全部通过；这是 P1 的补充证据，不把完整套件的 IO 失败改成 PASS。
- 两次完整运行的 skip 均为既有 Windows symlink 1314；warning 为既有 Starlette/TestClient 弃用提示，原始记录保留。未增加 skip、未延长测试超时来掩盖错误、未改共享写入器。

## 最终交付与仍开放的阻断

- 凭据泄漏 P1：所报合成复验已关闭，正常 PR3→PR4 路径安全 hold，完整结果与所有 PR4 CLI 产物无 canary；普通配置正控可正常 focus。AI 开发复核为非盲，不是独立研究。
- 全量门槛：**NOT_PASSED**。两次完整运行 exit 1；定向重跑均通过，但共享导出原子改名的间歇 IO 失败仍开放，首次 CLI EXPORT_IO_ERROR 的底层原因仍没有直接栈。
- 本轮保持当前 PR4 的最小修复范围，没有修改 PR1–PR3 共享导出逻辑或降低其测试断言。若要修复共享 Windows 原子导出，应先另行明确批准范围；不自动扩大本轮代码改动，也不继续盲目完整重试。
- 最终保全 501 个原有受控文件：仅两处获准的既有 PR4 源码变化；G1、PR1–PR3、所有 Schema、配置/锁、既有 fixture/labels 与旧报告原字节保持；G1 pin 不变。`final-verification.json` 登记当前源码与失败门槛。
- 不建议管理员合并。没有 commit/push、生产 DB 访问/迁移、真实模型或外网调用；两次单次沙箱外授权均已使用。
