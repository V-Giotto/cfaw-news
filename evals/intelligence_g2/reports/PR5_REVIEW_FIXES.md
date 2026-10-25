# G2-PR5 审查修复

当前状态：两项审查问题已修复；当前源码正常 asyncio 专项、同池矩阵、全部 G2 与完整回归均通过（985 passed / 1 skipped / 0 failed / exit 0）。当前 PR 可交管理员审查与合并决断；不自动合并。

范围仅当前 PR5；没有 P0 报告，也未据此宣称无 P0 风险。HEAD 为 `76ef14b531842ae449c4f907302218d2e2ea4c90`，G2 仍为未跟踪工作区。前一份 PR5_ACCEPTANCE.md 是修复前的历史证据，不能代替本轮回归。

## 问题与 before/after

| 问题 | 修复前实际现象 | 最小修复 | 修复后实际现象 |
|---|---|---|---|
| P1 传输吞超时取消 | 原复验在约 2.078 秒后 accepted / code=null / mock_closed；超过 2 秒期限 | 使用同一事件循环的单调时钟保存调用 deadline；wait_for 返回并检查撤销后，先检查期限，再处理返回值 | 约 2.078 秒后 fallback / TIMEOUT / rule；过期返回值不进入编排层 CompletionResult/表达校验、草稿或响应 telemetry；adapter 内的信封解析仍属于调用内部 |
| P2 非法 completion | 原复验抛 AttributeError；新负例还暴露非法模型的 telemetry 验证崩溃 | 分离 raw_completion 与严格验证成功的 completion；Schema 拒绝后 completion 保持 null | SCHEMA_INVALID / fallback，原 rule 逐字节保留，未知 usage 不填零，不复制未验证对象字段 |

原脚本：before exit 1，after exit 0。新增回归：修复前 **6 failed / 2 passed / exit 1**，修复后 **8 passed / exit 0**。不是把失败改填 PASS；原失败日志与 JUnit 保留。及时有效返回（CompletionResult 对象及合法 dict 两种）、已验证 usage 为正控；非法 dict/string/不透明对象/绕过构造的模型、吞取消后返回有效/非法内容为负控。每项核对 code/status、精确 rule、一次调用、预算、零外部成本、未验证 telemetry 与敏感哨兵不进入输出。

## 验证环境与当前结果

- 无 socket 事件循环仅用于本轮内存反例/纯 Mock 流程；保留真实 asyncio.wait_for、计时器、任务及取消逻辑。未替换超时结果、未改产品或测试断言；不把该探针当作正常事件循环/完整回归通过。
- 内存门禁、流程和预算共 **103 passed / exit 0**，其中新增 8 条；跨 PR 更正/撤回、凭据、原子导出、文档版本与 PR2 修复回归 **77 passed / exit 0**，见 cross-pr.log/JUnit。
- 六套 Schema、G1 strict、Ruff、seed、离线前端构建均 exit 0。
- 沙箱默认 asyncio 初始化探针仍 5 秒超时，实际 exit 3，原记录保留。随后取得管理员本轮明确授权，正常事件循环专项与完整 pytest 按授权在沙箱外执行并通过；没有沿用旧授权。
- 本轮正常事件循环 PR5 **114 passed**、全部 G2 **434 passed**、126 个新 rule/mock 运行与独立评测、完整 pytest **985 passed / 1 skipped / 0 failed** 均 exit 0；完整运行一次，没有自动重跑。

## 修改与保全

只有 `evals/intelligence_g2/pr5/pipeline.py` 一个既有运行文件改变；新增 `tests/evals/g2/pr5/test_review_regressions.py` 与本报告。没有修改 Schema、版本、预算、Prompt、样式、prediction/mock/reference 标签、权限、锁、前序报告或业务 provider。G1 frozen 与 PR1–PR4 保持原字节。

53 份本轮源码/Schema/配置/输入/Mock/参考指纹写入 source-snapshot.json；561 文件基线除上述 pipeline 外全部匹配，14 份冻结资产匹配。pipeline.diff 包含由原字节 SHA 核对的前后补丁。

## 未关闭项与限制

1. 两项审查问题和当前工程门槛均关闭，未留产品测试失败；以下非协作执行限制及未实施能力仍明确保留。
2. 期限检查拒绝吞取消后返回的任何过期结果。它不能抢占永不返回的非协作 Python 代码，也不宣称硬进程终止；本 PR 没有真实 transport。
3. 验证仅 ai_development/合成 Mock 工程证据，非独立科研或真实模型质量证据；不实施 PR6、网络、付费模型、密钥/生产 DB、提交或推送。

## 实际命令与日志

完整 argv/cwd/UTC/耗时/exit 保留在 `.tmp/g2-pr5-review-fixes-001/*.command.json`。每条命令有独立日志，JUnit 使用对应前缀；没有覆盖上轮文件。

| 记录 | exit | 日志 SHA256 |
|---|---:|---|
| after.command.json | 0 | `2049e8ce49edd87433f17ac38c5f07ee62d7d71407fd8ec82109c100d8ca88cb` |
| before.command.json | 1 | `c108cef928777c8bdd19806e4ee189924cddb63fed018e24756a6af565ec1824` |
| cross-pr.command.json | 0 | `2c416f1afe3ebe1e0f528ca59765b579fb73a6fecf2614500df4967dc62a7aaf` |
| frontend.command.json | 0 | `49539b9f509a8b0b352dad166a02e7182af2ee008aeda94291593d1bbcde2958` |
| g1-schema.command.json | 0 | `ad541cc67a0a6b6ce43b44815465079cd8b104a992b74d4c1a670e767b546d7d` |
| g1-strict.command.json | 0 | `ae200140ab0b4b55cfc9964459369e2e3a0970039dbfb7359501ad56ac18aa38` |
| in-memory-pr5.command.json | 0 | `8c0c8875c243c38d69758d382fe809ed7fa885c13d15f08f51acd05f8fb9df6e` |
| loopback-probe.command.json | 3 | `d11837bd9da0ceae8ceaccb4b7208dab8dcaf2e7524465bece0a0c0a5eae553a` |
| pr1-schema.command.json | 0 | `a809da7e3eeb608fdce4300ac3ac61ce71461ebdd5e50803baaede51ffa8f3e1` |
| pr2-schema.command.json | 0 | `ffc3a2599f9fe6d9e1046f4e8cf20d19c948e76b87b838f97e144cb2df555923` |
| pr3-schema.command.json | 0 | `27303a3b8249fbfd930481b365912d74dd58bf322a1a4e137ceee3509558cf51` |
| pr4-schema.command.json | 0 | `a01abfe266c318861e969fd32356b29343cd6052cbbc61f0d7304dc7c71279de` |
| pr5-schema.command.json | 0 | `86f275951f363daa9ee1f8ebb1b605842a9fb7608f7e8039653699ec0eb7d877` |
| regressions-after.command.json | 0 | `c615c1aa1011caf1895c24f831e786f9dfa986321400b3851dbaf8f665704388` |
| regressions-before.command.json | 1 | `208a9a3cbad5cf186d3ebca1d8edc565c937d17dbfbd3be6cf6f4b91fe05776a` |
| ruff.command.json | 0 | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| seed.command.json | 0 | `94d3f70af8d2daa9bda292f651e37d8ff0baa91880545b46a074c577c3ed33ff` |

完整复验命令及 schema/构建等 argv 见上述 JSON。错误字段不回显原文或异常消息；仅使用合成哨兵，无真实凭据/用户 DB。

## 本轮批准后的实际验收与保全

管理员明确回复“批准本轮异步验证及一次完整 pytest”；授权记录为 authorization.json。按顺序先完成专项/矩阵/G2，再核对源码冻结，最后只执行一次完整 pytest。

- 正常 asyncio PR5 114 passed；全部 G2 434 passed；完整 **985 passed / 1 skipped / 0 failed / exit 0**。
- 矩阵 126 个新 rule/mock 运行和 126 次独立评测进程全部 exit 0；每通道 G1 35 步、合成/兼容 68 步，两个通道共 206 步观察。新旧正常 presentations.jsonl 逐字节相同，rule/mock 原 Item 相同，父运行目录 SHA 不变。预测使用记录的 run_replay API 参数；评测使用 matrix.json 中实际子进程 argv。
- 完整回归 UTC：2026-10-25T07:46:49.504886+00:00 → 2026-10-25T07:57:59.659217+00:00，耗时 670.155 秒。唯一跳过为 Windows symlink 权限 1314，完整条目见 final-verification.json/JUnit；没有改依赖或放宽断言。
- 53 份当前源码/资产冻结指纹匹配；561 份旧文件只改 PR5 pipeline，14 份开发输入/标签/Prompt/Mock 冻结资产原字节匹配。G1 pin `5608f6c9f20d283f9274308fa98a277c535eb0d8d828fd0d863d6e1faafde06f` 未变。
- 扫描 1260 份最终预测输出文件，合成凭据哨兵泄露 0；外部请求、真实模型调用与费用 0。修复后成功回归的日志不含非法 completion 哨兵，未读取真实用户 DB。

完整 pytest 实际 argv：

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -o faulthandler_timeout=120 --basetemp=.tmp/g2-pr5-review-full-4a0b4e84e6374f819cc74983d44c0273 --junitxml=.tmp/g2-pr5-review-fixes-001/full-approved.xml --log-file=.tmp/g2-pr5-review-fixes-001/full-runtime.log --log-file-level=WARNING
```

| 新增命令记录 | exit | 日志 SHA256 |
|---|---:|---|
| pr5-normal.command.json | 0 | `b284ea42f7c81640d22830da518e0853c7c4bb22489c34a19b7872e626a7d2fa` |
| g2-normal.command.json | 0 | `51c52e6ce282ca6731967991cd8e9d5cee3581a7b8c5fdcf54cb48b92bcee5a5` |
| matrix.command.json | 0 | `7ee6b338b6bbdb61a922e43d6d07658c02c5ff8851d1da2c0ebe3bd12bb85949` |
| full-approved.command.json | 0 | `674786dabac82885f26b5e53062b4036d2d3ff49a04d69c3dc21d4c29b14f371` |

| 工件 | SHA256 |
|---|---|
| full-approved.xml | `933a26a4b4001b350c5db77ee54b955ab861074953e058bc5291214fe9903367` |
| full-runtime.log | `29018bc625ae4aef71706ecfb7843297a28f7aeee1290741ad460f37e22f08b9` |
| matrix.json | `6f676ec48351cdc206610bcfdad2fdca020b2ac03eafac7a52cacc39d772c3a5` |
| source-snapshot.json | `a1603a9fafee0930a23118cbf77f32c8a6bf8c5244c31f61e1dc11abecf21c69` |
| final-verification.json | `2fd268ef27a447139ea48f524267c1d00edbf8fa9b7ff09554ea6d069cb4c9ab` |

全部命令原始日志、失败和 JUnit 保留。报告只关闭当前 PR5 审查问题与 ai_development 工程门槛；不宣称真实模型质量、独立研究证据、PR6/G2 全阶段完成或 G3 准入。未 commit/push/merge。回滚仅恢复 pipeline 的原字节并撤回本轮新增测试/报告；历史工件和前序工作区保留，无 DB 回滚。
