# G2-PR4 导出可靠性审查修复

本报告仅覆盖当前 PR 的共享导出故障。`review_origin=ai_development`，非盲，非独立科研证据。HEAD 仍为 `76ef14b531842ae449c4f907302218d2e2ea4c90`；G2 仍为既有未提交工作区。本轮不进行 commit/push、联网、模型调用、DB 访问/迁移或后续 PR 开发。

## 审查问题与证据

P1：两次历史全量均 exit 1：`full-approved.xml` 为 852 passed / 2 failed / 1 skipped；`full-retry.xml` 为 853 passed / 1 failed / 1 skipped，位于 `.tmp/g2-pr4-review-fixes-001/`。直接栈确认共享 `write_payloads` 的目录改名 WinError 5，另一次 PR4 CLI 仅得到 `EXPORT_IO_ERROR`，不能据此断定同一底层原因。旧日志、JUnit 和原报告全部保留。

## 先复现、再修复

新增 `tests/evals/g2/test_export_reliability.py` 后，旧生产代码的受控测试为 **12 failed / 1 passed，exit 1**（`native-before.xml`）。这包括新增重试/安全诊断的契约预期；原生句柄案例分别直接抛 WinError 5、32。

原生实验使用本轮 `.tmp/evals/g2/tests/` 下合成文件及 `CreateFileW`：读取子文件但不允许 `FILE_SHARE_DELETE` 时，目录原子改名得到 WinError 5；同类目录读取句柄得到 WinError 32。句柄在失败后释放，旧实现已退出，无法恢复。初始零访问权限的目录句柄没有阻挡改名，已保留该实验及失败日志；随后使用真正的读取访问权限，未放宽目标断言。`native-probe.json`、`native-child-probe.json` 和原生测试记录保存具体 errno/winerror。

这定位了一个可复现的 OS 拒绝机制及旧导出器的单次尝试缺口，**没有识别历史运行中的句柄持有者**，不能归因为杀毒软件、沙箱、ACL 或 PR4 新规则。

## 最小修复与边界

只修改 `evals/intelligence_g2/replay.py`：共享发布路径仅对 Windows `winerror in {5,32,33}` 重试，最多 6 次，等待 0.05/0.1/0.2/0.4/0.8 秒，累计上限 1.55 秒（不含系统调用耗时）。其他错误立即失败。每次尝试重新校验目标不存在及目录路径；仍使用同卷私有 staging → 最终目录的单次原子 rename，不使用覆盖、copy 或部分发布。

重试日志仅包含固定操作、次数、errno/winerror。耗尽返回既有 `EXPORT_IO_ERROR / export / publish.rename:attempts=...:errno=...:winerror=...`；PR1–PR4 CLI 均保留该信息，不包含异常原文、路径或正文。沿用已存在的 Schema 字段，没有扩展契约、权限或依赖。

保留失败时的已知平面文件清理及不覆盖检查。测试确认持续注入改名拒绝会失败且清理 staging；重试期间竞争目标出现时返回 OUTPUT_EXISTS，空目录或既有文件均不被覆盖。中断也清理。永久 OS 拒绝仍会失败，不被标记成功；若 OS 连清理操作也永久拒绝，不能承诺强制清理或成功发布。

17 条新增测试覆盖原生 WinError 5/32、注入 5/32/33、持续拒绝/上限/安全诊断、非重试错误、竞争目标、KeyboardInterrupt 和四代 CLI 错误传输。修复后 **17 passed / exit 0**。原有失败、路径、覆盖及敏感数据负例断言保持不变。

## 当前验证

- 全部 G2：**320 passed / exit 0**，包括此前敏感文本与生命周期修复反例。
- 五套 Schema、G1 strict、Ruff、seed、前端离线构建：均 exit 0。
- 重新生成当前源码 pin 的 PR2→PR3→PR4 父链：35 个 G1 时点 + 40 个合成/兼容时点；266 份语义文件与修复前合法输出逐字节一致。旧 pin 没有自动刷新或绕过；新导出 manifest 正常记录新源码 SHA。
- 本机 asyncio 沙箱探针：exit 3（5 秒超时）。这是完整旧业务测试的执行环境缺口，与目录改名失败的归因分开。
- 本轮完整 pytest：**871 passed / 1 skipped / 0 failed，exit 0**。使用本轮明确批准的一次沙箱外执行，源码与 320 条 G2/75 步矩阵执行时完全一致。历史两次失败仍保留。导出可靠性客观门槛已关闭，可提交管理员合并审查；不自动 merge/commit/push。

所有实际 argv/cwd/真实 UTC 起止/exit code/log SHA 在同名 `.command.json`。JUnit、日志及源文件快照位于 `.tmp/g2-pr4-export-fixes-001/`。下表为当前实际执行记录，`loopback-probe` 的探针进程真实 exit code 为 3。

| 运行 | exit code | log SHA256 |
|---|---:|---|
| frontend | 0 | `42c977963572fc78262656b3a6c6b96e54ff99bc4b4d89942810fb8408e2c68a` |
| g1-schema | 0 | `ad541cc67a0a6b6ce43b44815465079cd8b104a992b74d4c1a670e767b546d7d` |
| g1-strict | 0 | `ae200140ab0b4b55cfc9964459369e2e3a0970039dbfb7359501ad56ac18aa38` |
| g2 | 0 | `d4eece3cd7bf8d0341c0c9fba8a7bca329d73b08071f4982b73061647ae6d24d` |
| loopback-probe | 3 | `d11837bd9da0ceae8ceaccb4b7208dab8dcaf2e7524465bece0a0c0a5eae553a` |
| matrix | 0 | `d66d8abed65f06d7b2dadddcadd3ad69675d6f00c82a62c5a548729de686a4c8` |
| native-before | 1 | `23644438cfcf6b9ff1b451b0a5fee3bf64dfeee89c04a99990ce8f63f95ea285` |
| pr1-schema | 0 | `a809da7e3eeb608fdce4300ac3ac61ce71461ebdd5e50803baaede51ffa8f3e1` |
| pr2-schema | 0 | `ffc3a2599f9fe6d9e1046f4e8cf20d19c948e76b87b838f97e144cb2df555923` |
| pr3-schema | 0 | `27303a3b8249fbfd930481b365912d74dd58bf322a1a4e137ceee3509558cf51` |
| pr4-schema | 0 | `a01abfe266c318861e969fd32356b29343cd6052cbbc61f0d7304dc7c71279de` |
| regression-after | 0 | `39026289c35f95313ef7b95f1670fc6deb0dd72d9c079a534861ccc37e75be48` |
| regression-before | 1 | `42b3b8008c0d70cf850de565a93aae8378b9f04ed097f20d18a0c21e8b51cddc` |
| regression-final | 0 | `14ed68bed9a92ecd85e3555d4203e0d72a1377575a2170861a07d7cf11bd816a` |
| ruff | 0 | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| seed | 0 | `c95664bd62c4039642a763123114af46777d3be1699b91f83403f16960c9fc71` |

## 实际命令

```text
npm.cmd --offline run build
```

```text
.\.venv\Scripts\python.exe -B -m evals.intelligence_v1.contracts --check-schemas
```

```text
.\.venv\Scripts\python.exe -B -m evals.intelligence_v1.validate --manifest evals/intelligence_v1/manifests/dataset_manifest.json --strict
```

```text
.\.venv\Scripts\python.exe -B -m pytest tests/evals/g2 -q -p no:cacheprovider --basetemp=.tmp/g2-pr4-export-g2 --junitxml=.tmp/g2-pr4-export-fixes-001/g2.xml
```

```text
.\.venv\Scripts\python.exe -B .tmp/g2-pr2-review-fixes/loopback_probe.py
```

```text
.\.venv\Scripts\python.exe -B .tmp/g2-pr4-export-fixes-001/matrix.py
```

```text
.\.venv\Scripts\python.exe -B -m pytest tests/evals/g2/test_export_reliability.py -q -p no:cacheprovider --basetemp=.tmp/g2-pr4-export-native-before --junitxml=.tmp/g2-pr4-export-fixes-001/native-before.xml
```

```text
.\.venv\Scripts\python.exe -B -m evals.intelligence_g2.contracts --check-schemas
```

```text
.\.venv\Scripts\python.exe -B -m evals.intelligence_g2.pr2.contracts --check-schemas
```

```text
.\.venv\Scripts\python.exe -B -m evals.intelligence_g2.pr3.contracts --check-schemas
```

```text
.\.venv\Scripts\python.exe -B -m evals.intelligence_g2.pr4.contracts --check-schemas
```

```text
.\.venv\Scripts\python.exe -B -m pytest tests/evals/g2/test_export_reliability.py -q -p no:cacheprovider --basetemp=.tmp/g2-pr4-export-after --junitxml=.tmp/g2-pr4-export-fixes-001/regression-after.xml
```

```text
.\.venv\Scripts\python.exe -B -m pytest tests/evals/g2/test_export_reliability.py -q -p no:cacheprovider --basetemp=.tmp/g2-pr4-export-before --junitxml=.tmp/g2-pr4-export-fixes-001/regression-before.xml
```

```text
.\.venv\Scripts\python.exe -B -m pytest tests/evals/g2/test_export_reliability.py -q -p no:cacheprovider --basetemp=.tmp/g2-pr4-export-final --junitxml=.tmp/g2-pr4-export-fixes-001/regression-final.xml
```

```text
.\.venv\Scripts\python.exe -B -m ruff check backend tests evals
```

```text
.\.venv\Scripts\python.exe -B evals/run_baseline.py --output .tmp/evals/g2/pr4-export-seed.json
```

## 未关闭项与回滚

1. 本轮同一源码的完整 pytest 门槛已通过：871 passed / 1 skipped / 0 failed / exit 0；无未关闭的产品测试失败。已知 Windows 符号链接权限跳过单独记录，没有降低断言。
2. 历史瞬时失败的外部持有者未知；受控原生复现证明机制而非历史归因。新诊断为后续失败提供可区分的 OS 数值。

回滚只撤回上述共享发布重试/诊断及新增测试；保留 G1 frozen、PR4 语义规则、安全修复、历史证据和所有旧工件。没有 DB 回滚。生产代码只有这一个文件变化；受控基线中其余文件 SHA 不变。


## 全量完成记录

用户本轮回复“批准本次完整 pytest”后执行；授权范围及真实接收时间见 `full-authorization.json`。实际命令为：

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -o faulthandler_timeout=120 --basetemp=.tmp/g2-pr4-export-full-48d7c0aa31be41a992d93ddfbc172d3d --junitxml=.tmp/g2-pr4-export-fixes-001/full-approved.xml --log-file=.tmp/g2-pr4-export-fixes-001/full-runtime.log --log-file-level=WARNING
```

真实 UTC：2026-10-25T05:39:36.894311+00:00 → 2026-10-25T05:49:25.206403+00:00；耗时 588.312 秒；exit **0**。结果 **871 passed / 1 skipped / 0 failed**。

运行期日志记录 32 条安全 rename 重试消息；新增受控测试本身预期产生 32 条。因此该数字不作为历史故障进程或外部持有者的证据。完整 JUnit 的跳过原因见 `final-verification.json`，非产品断言放宽。

| 证据 | SHA256 |
|---|---|
| full-approved.log | `e23ae07ca460c0e6bf4f80b686cf467417f82750c53c10d1d0fe63404e6420f8` |
| full-approved.xml | `5c5a3078ce26b938f2cab32042683fdfa1bd14ebc580c4a6ec02574288e27812` |
| full-runtime.log | `d39431305e0a2404beb7e07b09c9277894f8a0c46baf6d53c246ed57298daa4c` |
| source-snapshot.json | `967fcb02e186620c156135bd9f52117f895298194a800b4f6007c8e9d808a927` |
| matrix-verified.json | `5e40d77b7257b780efe59a8468f84d2da1be8a7166218bcb247320ad0159a9df` |
| final-verification.json | `348f1467c8b21e9963778350f1488e53b58016ec5f4b9cf85418bd5a1e8fdc2f` |

最终保全：初始 504 份受控文件只有共享导出器这一个既有文件变化；新增 1 份测试及本报告。66 份旧修复证据文件保持 SHA 不变。G1 manifest SHA 为 `5608f6c9f20d283f9274308fa98a277c535eb0d8d828fd0d863d6e1faafde06f`，冻结输入、既有标签/Schema/锁及安全修复全部保持不变。源文件 SHA：

{
  "evals/intelligence_g2/replay.py": "d78c803ae60b4b56b2ffce44c09a9e76307c1ff0b4781617ef3c2f3629d50b91",
  "tests/evals/g2/test_export_reliability.py": "02213282d9bf235f1895cbefec53993627c0b2604a8d29919fd3c311c99b990b"
}

本轮仅建议当前 PR4 的开发验收进入管理员审查；不声明真实效果、独立研究验证、G2 全阶段或 G3 准入。
