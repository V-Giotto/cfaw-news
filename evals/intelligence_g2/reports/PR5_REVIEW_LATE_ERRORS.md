# G2-PR5 迟到异常审查修复

当前状态：迟到 adapter 异常的分类及遥测问题已修复；当前源码专项、矩阵、G2 与单次完整回归通过（995 passed / 1 skipped / 0 failed / exit 0）。当前 PR 可交管理员复审；不自动合并。

HEAD：`76ef14b531842ae449c4f907302218d2e2ea4c90`。G2 仍为未跟踪工作区。此前 PR5_ACCEPTANCE.md、PR5_REVIEW_FIXES.md 及 985 passed 是历史证据，不代替本轮完整回归；这些报告原字节保留。

## Before / after 与最小修复

| 迟到响应 | before 实际 code / bytes / usage | after 实际 code / bytes / SHA / usage |
|---|---|---|
| 截断信封 | OUTPUT_TRUNCATED / 96 / total_tokens=77 | TIMEOUT / 0 / null / null |
| HTTP 429 | RATE_LIMIT / 29 / total_tokens=77 | TIMEOUT / 0 / null / null |
| 非法 JSON | INVALID_JSON / 4 / null | TIMEOUT / 0 / null / null |

三类 before/after 均回退 rule，没有观察到迟到表达发布。实际各次耗时见 before.log / after.log（约 2.01–2.03 秒）；非法 JSON 的合成字节内容为 `{bad`，没有为匹配审查示例字节数伪造结果。原复验 before exit 1，after exit 0。

根因是仅正常 await 返回路径检查 deadline，异常路径仍使用 adapter 错误码和 safe_telemetry。现在在同一调用开始前建立单调时钟 deadline，ContractError 及普通 Exception 分支都先检查控制状态，再检查期限；到期固定 TIMEOUT，completion=null，failed_telemetry={}。及时错误仍保留原错误码、响应字节/SHA 和白名单 usage。CANCELLED/STALE_RESULT 保持终止语义，不转成超时回退。

仅修改 PR5 pipeline.py 和现有 test_review_regressions.py，新增本报告。未修改 adapter、Schema/版本、权限、预算、Prompt/style、prediction/mock/reference、G1 frozen、PR1–PR4、业务 provider、锁或前序报告。没有实现 PR6、真实 transport、网络/模型调用、密钥加载或数据库迁移。

## 新回归与实际断言

- 新增 10 条：三类 adapter 响应加普通传输异常的迟到/及时成对用例共 8 条；迟到错误伴随取消/失效控制共 2 条。
- 修复前新增用例 **4 failed / 6 passed / exit 1**；修复后包含上轮回归共 **18 passed / exit 0**。原失败 JUnit/日志保留。及时返回正控没有改成一律 TIMEOUT/一律清空 usage。
- 迟到错误逐项断言 TIMEOUT、fallback、精确原 rule、无草稿、bytes=0、SHA/usage=null、usage_origin=unknown、一次调用与预留预算不回收、真实请求与费用 0。
- 及时截断/429 分别保留 OUTPUT_TRUNCATED/RATE_LIMIT 与 total_tokens=77；及时非法 JSON 保留 INVALID_JSON/SHA/bytes；及时普通异常仍 INVALID_ENVELOPE。控制失效核对 code=STALE_RESULT / stage=control / field=request；取消继续抛 CancelledError，均不返回 StepExecution。
- 纯 Mock 无 socket 事件循环仅用于沙箱内复现和内存测试；保留真实 wait_for、任务、定时器及取消，不替换超时结果，也不把该检查当作正常本机事件循环或完整回归通过。

## 当前验证与未关闭项

- 内存 PR5 门禁/流程/预算 **113 passed / exit 0**；关键跨 PR **77 passed / exit 0**，含 PR3 生命周期、PR4 凭据、原子导出、文档版本及 PR2 修复。
- 六套 Schema、G1 strict、seed、前端离线构建通过。初次 Ruff exit 1，仅新增 import 的换行格式不合规；只修 import 排版后全域 Ruff exit 0，不改测试断言。原 Ruff 失败记录保留。
- 默认 asyncio 沙箱探针仍 5 秒超时，exit 3，原记录保留。本轮新授权下正常 asyncio PR5/矩阵/G2 与单次完整 pytest 均通过，没有自动重跑。
- 563 份旧文件基线仅上述 pipeline/test 改变；53 份本轮源码/资产指纹冻结，14 份输入/标签/Prompt/Mock 冻结资产原字节匹配。G1 manifest pin 不变。
- 期限处理能丢弃返回或抛出的过期结果，不能抢占永不返回的非协作 Python 代码。本 PR 无真实 transport；工程证据为 ai_development / synthetic / non_blind / independent_validation=false，不是独立科研或真实模型质量证据。
- 本轮全部客观工程门槛与最终保全检查通过，无未关闭产品测试失败。保留非协作执行与未实施能力的限制。未 commit/push/merge。

## 实际命令、退出码与 hash

完整 argv、cwd、UTC 起止、耗时及 exit 在 `.tmp/g2-pr5-late-errors-001/*.command.json`，JUnit 使用对应前缀。无覆盖旧证据；pipeline-before.py、tests-before.py 保存修复前实际字节，pipeline.diff 已核对原 SHA。

| 命令记录 | exit | 日志 SHA256 |
|---|---:|---|
| after.command.json | 0 | `99dd428cc02129a8d4a9b36532c407744fe336b9f0e8a7da5272326d93edc482` |
| before.command.json | 1 | `23c6e9b637710e695f84f9262b06d757c8ad886678968b7ef50b9ea328cf53c3` |
| cross-pr.command.json | 0 | `a9b188f24b02a9bda33db0fc5f4caf12516db69a69d420571b718c1877b0b4f0` |
| frontend.command.json | 0 | `0531a36b1129a02e76458d459539f00f1e13062d6081b05a5e9fc78effae186f` |
| g1-schema.command.json | 0 | `ad541cc67a0a6b6ce43b44815465079cd8b104a992b74d4c1a670e767b546d7d` |
| g1-strict.command.json | 0 | `ae200140ab0b4b55cfc9964459369e2e3a0970039dbfb7359501ad56ac18aa38` |
| in-memory-pr5.command.json | 0 | `2a92bed8cb8dfe32cbb5edf6aeb66241b9a84eaeb197aadf2ad6a2ec66371943` |
| loopback-probe.command.json | 3 | `d11837bd9da0ceae8ceaccb4b7208dab8dcaf2e7524465bece0a0c0a5eae553a` |
| pr1-schema.command.json | 0 | `a809da7e3eeb608fdce4300ac3ac61ce71461ebdd5e50803baaede51ffa8f3e1` |
| pr2-schema.command.json | 0 | `ffc3a2599f9fe6d9e1046f4e8cf20d19c948e76b87b838f97e144cb2df555923` |
| pr3-schema.command.json | 0 | `27303a3b8249fbfd930481b365912d74dd58bf322a1a4e137ceee3509558cf51` |
| pr4-schema.command.json | 0 | `a01abfe266c318861e969fd32356b29343cd6052cbbc61f0d7304dc7c71279de` |
| pr5-schema.command.json | 0 | `86f275951f363daa9ee1f8ebb1b605842a9fb7608f7e8039653699ec0eb7d877` |
| regressions-after.command.json | 0 | `a7070b98d1e202c52de518c0ce5d17640deab1faecdfbb5249666cf1bfb2edec` |
| regressions-before.command.json | 1 | `41f3c80a91a6b114d094b0153c721a7fb13477566e246187bd106b040152aabc` |
| ruff-verified.command.json | 0 | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| ruff.command.json | 1 | `cabdb0cf0922407925fde492f5a7e5590bf54c35ef0b417023c7f41056e5d320` |
| seed.command.json | 0 | `5bbb0242ae38c99c21c9d1df008861f7e93cbfcf5498f900f409ef147d01f440` |

## 本轮批准后的完整验收

管理员明确批准“本轮异步验证及一次完整 pytest”，详见 authorization.json；先通过专项/矩阵/G2 并核对冻结指纹，再仅执行一次完整 pytest，没有自动重跑。

- 正常 asyncio PR5 **124 passed**、全部 G2 **444 passed**；完整 **995 passed / 1 skipped / 0 failed / exit 0**。
- 126 个新 rule/mock 运行及 126 次独立评测进程均 exit 0；每通道 G1 35 步、合成/兼容 68 步，共 206 个时点观察。新旧正常 presentations.jsonl 逐字节一致，rule/mock 原 Item 相同，父目录 SHA 不变。预测为记录的 run_replay API 调用，评测为 matrix.json 内实际 subprocess argv。
- 完整回归 UTC 2026-10-25T08:24:58.669733+00:00 → 2026-10-25T08:36:02.086774+00:00；耗时 663.417 秒。唯一跳过为 Windows symlink 权限 1314，完整条目保留于 JUnit/final-verification.json，没有放宽断言。
- 53 份当前源码/配置/Schema/输入/Mock/参考冻结指纹匹配；563 份旧文件仅上述 pipeline/test 改变。14 份冻结资产及 G1 pin `5608f6c9f20d283f9274308fa98a277c535eb0d8d828fd0d863d6e1faafde06f` 不变。
- 扫描 1260 份最终预测文件，合成凭据哨兵泄露 0；外部请求、真实模型调用与费用 0；没有读取真实用户 DB 或密钥。

实际完整 pytest argv：

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -o faulthandler_timeout=120 --basetemp=.tmp/g2-pr5-late-full-95a13ed85ba64a71b68ee069dbfd51d5 --junitxml=.tmp/g2-pr5-late-errors-001/full-approved.xml --log-file=.tmp/g2-pr5-late-errors-001/full-runtime.log --log-file-level=WARNING
```

| 新增命令记录 | exit | 日志 SHA256 |
|---|---:|---|
| pr5-normal.command.json | 0 | `c7f7c5fa1a3e026fd483f067b04a5071ac182398e7c73fe8a3cf907cfa89f90a` |
| g2-normal.command.json | 0 | `c76e539bd6221d686c099001ff756fa7606c967cbf00ab9e3f631877ab6d4d81` |
| matrix.command.json | 0 | `7ee6b338b6bbdb61a922e43d6d07658c02c5ff8851d1da2c0ebe3bd12bb85949` |
| full-approved.command.json | 0 | `642e2f9c3c64410fc0b027fa9ba98fa0ad37daa605636a6d044b5362494e6b9b` |

| 工件 | SHA256 |
|---|---|
| full-approved.xml | `08a49985ff3054abefa5961b39021b362b74f99187fc2322619eb690d00dd644` |
| full-runtime.log | `95e85b66f4e45be0ef7c407ec6f5b62a3145b1a911b2c6d7bc409f53497ad1d5` |
| matrix.json | `fb137521848acfbc3e97e1b0cededc5ef740929720d9b36031ac17c2bdf1a2c7` |
| source-snapshot.json | `2fc860f18f27d15fa418945763823540852fdeb5bb02048b860d544ed0ca0650` |
| final-verification.json | `c1bcee8421f6a1bae29b4ac0b9a16e177316c8584e2587ca5aebc19f55acaa2e` |

全部原始失败记录保留；本报告仅指当前 PR5 ai_development 工程门槛，不宣称真实模型质量、独立科研、PR6/G2 全阶段完成或 G3 准入。未 commit/push/merge。回滚只恢复本轮 pipeline/test 的修复前字节并撤回新报告；旧报告、前序实现、冻结资产和历史工件保留，无 DB 回滚。
