# G2-PR3 追加修复：scope 不得补齐生命周期目标

上轮 B 的关闭结论不完整：不同指标、相同单位且 scope 含指标词的组合仍会误撤回。本报告更正该关闭结论；旧修复报告和旧工件保持原字节。

当前状态：本轮复现、专项及完整回归通过，可交管理员复核合并。

## 范围与真实复现

HEAD `76ef14b531842ae449c4f907302218d2e2ea4c90` 未变。登记 361 个既有受控文件，359 个原字节不变；只修改 PR3 scope.py/history.py，新增 test_lifecycle_target_scope.py 和本报告。
Schema、版本枚举、权限、配置、G1 frozen、PR1/PR2、fixture/参考标签、锁文件、旧报告、.gitattributes 及原工作区文档均未修改。未进入 PR4/PR5，未联网、调用外部模型、迁移/访问生产 DB 或 commit/push。

原始复验实际 exit 1：旧 speed gain 40%，新语句撤回 accuracy 40%；共同 Task 为 speed gain evaluation。错误 metric 指向 Task 的字符 68–78，输出 retracts、旧状态 retracted，validation.ok=True。修复后原始复验 exit 0：metric 为语句本身 accuracy claim（39–53），无 transition，旧状态 historical，输出 unresolved_withdrawal。

## 最小修复与结构约束

- 在第一项声明式 scope 元数据前划定 proposition 语句边界；subject、metric、quantity、quantifier、否定信息不再从 metadata 补齐。scope 自身仍从完整原段落保留。
- 肯定生命周期语法对 prior_metric、prior_value/unit/quantifier、corrected_value/unit/quantifier 使用独立具名捕获；GroundedValue 均绑定原句真实跨度。accuracy 记录为 accuracy，缺目标指标保留 unknown，不回退为 scope 中的 speed_gain。
- history 从原引用重新解析生命周期目标，用该明确目标匹配旧 Claim，不复用可能混入 scope 的整段 proposition 值。旧主张的主体、版本、指标、数值、单位、限定词和完整 scope 校验继续保留。
- 不靠全部弃权修复：合法 speed 撤回、更正，以及 scope 中另含百分比/限定词的正控仍能执行；否定/意向、目标缺失或错配继续降级。

## 测试与当前检查

13 条新用例在修复前实际 12 failed / 1 passed；修复后与既有相邻用例共 50 passed。覆盖六种 scope 字段夹带 speed gain、accuracy 更正、缺目标指标、scope 中额外数量/限定词、合法撤回/更正及伪造 scope 指标出处。伪造出处断言 G2_PR3_FIELD_PROVENANCE_INVALID / scope / grounded_fields / claim_key。

| 检查 | 当前结果 |
|---|---|
| 用户原始复验 | before exit 1；after exit 0 |
| 定向 / 全 G2 | 50 passed / 236 passed，均 exit 0 |
| 新回放矩阵 | 35 G1 + 19 synthetic 时点；23 次预测 API 后由独立评测进程验证，exit 0 / 0 |
| Ruff / 四套 Schema / G1 strict / seed / offline build | 全部 exit 0 |
| 完整 pytest | 787 passed / 1 skipped，exit 0 |

矩阵仅属非盲 ai_development；合成参考未改，G1 时点只报告结构回归，不赋予语义参考分数。独立支持计数仍为 0；independently_supported 禁止，独立科研验证 not_evaluated。同一 Codex 编写/复核不称独立验证。

当前沙箱本机 asyncio 探针 5 秒超时，exit 3，是环境限制。管理员随后明确批准本轮完整 pytest 在沙箱外运行；未扩大其他权限。

唯一完整回归跳过项（实际 JUnit）：

```json
[
  {
    "classname": "tests.evals.test_provenance_and_rights",
    "name": "test_symlink_outside_bundle_rejected_if_supported",
    "message": "symlink creation unavailable: 1314"
  }
]
```

完整日志中的依赖弃用警告如实保留，未为此安装或更改依赖。

## 真实命令、exit code 与日志 hash

每份 command.json 另保存 cwd、UTC 起止时间和耗时；矩阵 API 参数及输出 manifest pin 见 predictions/evaluation.json。

**reproduce-before** — exit `1`；1.679s；日志 SHA `09ef7f4612be50573d4891dce9290768f7f79cc8c4b7aea6f9a630fcd8730f3f`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", ".tmp/g2-pr3-review-fixes-002/reproduce.py"]
```

**regressions-red** — exit `1`；5.007s；日志 SHA `d36cf71fef569c3ee90d525ecbf237c3daf6497d4e5c1ea222672d2ea2f97e56`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "pytest", "tests/evals/g2/pr3/test_lifecycle_target_scope.py", "-q", "-p", "no:cacheprovider", "--basetemp=.tmp/g2-pr3-scope-red", "--junitxml=.tmp/g2-pr3-review-fixes-002/regressions-red.xml"]
```

**targeted** — exit `0`；5.773s；日志 SHA `b5119ce16a53b0480fafef1da12becbd642fd5257ac6fa955d4490aa758fba50`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "pytest", "tests/evals/g2/pr3/test_lifecycle_target_scope.py", "tests/evals/g2/pr3/test_review_regressions.py", "tests/evals/g2/pr3/test_history.py", "tests/evals/g2/pr3/test_scope.py", "-q", "-p", "no:cacheprovider", "--basetemp=.tmp/g2-pr3-scope-green", "--junitxml=.tmp/g2-pr3-review-fixes-002/targeted.xml"]
```

**reproduce-after** — exit `0`；1.783s；日志 SHA `5a62ae08d14077fb5b5d84e608704fbfdc62609bfa4b91887e15bea4ef2c5e2b`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", ".tmp/g2-pr3-review-fixes-002/reproduce.py"]
```

**matrix-prediction** — exit `0`；19.339s；日志 SHA `f149d39fca8631e6291484543e3bb8cda55a08dae51ad5c49bc164df597d8b9d`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", ".tmp/g2-pr3-review-fixes-002/run_matrix.py", "scope-target-matrix-001"]
```

**g2** — exit `0`；117.553s；日志 SHA `742b51984ba199fa2109799e75d97b518fce6cfbcf3a50497441335bbd3109a6`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "pytest", "tests/evals/g2", "-q", "-p", "no:cacheprovider", "--basetemp=.tmp/g2-pr3-scope-g2", "--junitxml=.tmp/g2-pr3-review-fixes-002/g2.xml"]
```

**loopback-probe** — exit `3`；5.232s；日志 SHA `d11837bd9da0ceae8ceaccb4b7208dab8dcaf2e7524465bece0a0c0a5eae553a`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", ".tmp/g2-pr2-review-fixes/loopback_probe.py"]
```

**ruff** — exit `0`；0.315s；日志 SHA `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "ruff", "check", "backend", "tests", "evals"]
```

**seed** — exit `0`；2.026s；日志 SHA `9f6b8e256e9b34c6fcce784f103d870fdfc987c1be69144b2c06548a03c06587`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "evals/run_baseline.py", "--output", ".tmp/evals/g2/pr3-scope-target-seed-001.json"]
```

**schema-g1** — exit `0`；1.038s；日志 SHA `ad541cc67a0a6b6ce43b44815465079cd8b104a992b74d4c1a670e767b546d7d`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "evals.intelligence_v1.contracts", "--check-schemas"]
```

**schema-pr1** — exit `0`；1.093s；日志 SHA `a809da7e3eeb608fdce4300ac3ac61ce71461ebdd5e50803baaede51ffa8f3e1`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "evals.intelligence_g2.contracts", "--check-schemas"]
```

**frontend** — exit `0`；18.038s；日志 SHA `af36b1328d4346bcfa639b34b82783ab403248764c3e002e185e8251ee015b23`。

```json
["C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "npm.cmd --offline run build"]
```

**schema-pr2** — exit `0`；1.132s；日志 SHA `ffc3a2599f9fe6d9e1046f4e8cf20d19c948e76b87b838f97e144cb2df555923`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "evals.intelligence_g2.pr2.contracts", "--check-schemas"]
```

**schema-pr3** — exit `0`；1.388s；日志 SHA `27303a3b8249fbfd930481b365912d74dd58bf322a1a4e137ceee3509558cf51`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "evals.intelligence_g2.pr3.contracts", "--check-schemas"]
```

**manifest-g1** — exit `0`；1.716s；日志 SHA `ae200140ab0b4b55cfc9964459369e2e3a0970039dbfb7359501ad56ac18aa38`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "evals.intelligence_v1.validate", "--manifest", "evals/intelligence_v1/manifests/dataset_manifest.json", "--strict"]
```

**matrix-evaluation** — exit `0`；20.680s；日志 SHA `3ac2876bd4ba27794466011ba43740fd794aa925f29f10e42b9d3a79f1b34ccf`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", ".tmp/g2-pr3-review-fixes-002/evaluate_matrix.py", "scope-target-matrix-001"]
```

**full** — exit `0`；673.595s；日志 SHA `561b27f35e956a9ed1218371250809f595f0a523b330daa91f358d7bb3849004`。

```json
["D:/agent_project/cfaw-news/.venv/Scripts/python.exe", "-B", "-m", "pytest", "-q", "-o", "faulthandler_timeout=120", "--basetemp=.tmp/g2-pr3-scope-full", "--junitxml=.tmp/g2-pr3-review-fixes-002/full.xml"]
```

## 工件、未关闭项与回滚

证据目录：`D:\agent_project\cfaw-news\.tmp\g2-pr3-review-fixes-002`。before.json、原源码副本、implementation.patch、JUnit、review.json、source-snapshot.json、preservation.json、verification-summary.json 和 artifact-index.json 保存本轮真实证据。
当前源码快照 SHA：`56b8e4be9323609d29d2bebb17bb01e5cc4bd9b3659abd4ddb33a1c4dd41ae17`。文件字节 SHA、运行源代码 SHA 与语义摘要分开；Schema/配置及哈希材料不扩展，历史结果不覆写、不混接旧源码状态。

本轮 P1 已修复。请求范围内无剩余产品失败，可交管理员复核合并。

保留限制：有限生命周期语法外的表达不自动更改历史；未知或歧义目标保留缺口。该修复不提供通用语义理解或独立事实验证。回滚仅恢复本轮 scope.py/history.py 和移除新增测试/报告，保留既有工作区、冻结资产及历史工件，无数据库回滚。
