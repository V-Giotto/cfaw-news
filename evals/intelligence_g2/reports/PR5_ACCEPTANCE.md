# G2-PR5 开发验收

当前状态：PR5 客观开发门槛通过，可提交管理员进行当前 PR 的审查与合并决断。本报告只记录当前 PR5，不代表 PR6/G2 全阶段验收。没有真实 HTTP transport、外网、模型、密钥、Goal 接入、生产 DB 或提交/推送。

## 已实现边界

- 新增独立 `pr5` 协议、Schema v5、Prompt/style catalog、mock/兼容信封 adapter、预测工件读取、表达验证、prefix CLI 和独立开发评测。
- PR4 rule Item、事实修订、事件身份、scope、风险和候选层级保持不变；接受的模型表达必须精确重建闭集句式。自由草稿只允许合成非敏感材料，始终 not_selected/not_verified，不能由 AI 复核自动升级。
- 固定 mock 默认；模型/外部请求/真实费用均 0。每 Item 请求 1、重试/repair 0、并发 1；输入/输出 32/8KiB，2 秒 mock 超时，step/run 16/128 请求；累计输入/响应预算 4/1MiB，响应按最坏上限预留。
- 结构定位、数字/scope、闭集表达与语义真实性分别记录；semantic_truth 和独立研究保持 not_evaluated。
- 现有 providers.py 仅复用设计及测试模式，不导入其 Goal/Judgment、数据库时间、Settings、密钥或 HTTP client。旧 Goal 行为必须通过回归证明兼容。

## 基线、执行与失败保留

- HEAD：`76ef14b531842ae449c4f907302218d2e2ea4c90`；G2 仍是既有未提交工作区。
- `.tmp/g2-pr5-evidence/baseline.json` 记录实施前 506 份受控文件 SHA；允许的既有文件修改仅 README 与 DATA_DICTIONARY 追加内容。冻结 G1/PR1–PR4、业务源码、锁和历史报告必须保持原字节。
- 初始门禁：52 passed / 2 failed，exit 1。两项反例在测试语义/归属前删掉了版本/来源数字，先被数字门禁拒绝。已改用保留无关绑定的定向反例，不降低拒绝或错误码断言；修正后 54 passed / exit 0。
- 初始 Ruff 的 import 排序问题已仅在 PR5 新文件修正，后续全域 Ruff exit 0。
- 合成冻结脚本首次因注入包含分号破坏已知 scope 语法，PR4 正确 hold，构造器 StopIteration / exit 1。保留该输入，不改成能得分的材料；另增不破坏语法的注入数据案例，分别检验上游 hold 与模型请求中的不可信数据。
- 本机 asyncio 探针：5 秒超时、真实 exit 3；不能改写为 PASS。随后取得本轮明确批准，按批准范围完成沙箱外离线验证；没有沿用旧授权。

实际命令、exit、UTC 起止与日志 SHA 在 `.tmp/g2-pr5-evidence/*.command.json`，JUnit 与日志使用同名前缀。初期构造探针/fixture 脚本的直接命令与异常记录见实施会话及 draft/process.json；不得当作完整测试通过。

## 开发参考与 AI 复核

`record_origin=synthetic`、`label_origin=synthetic_fixture`、`review_origin=ai_development`、`non_blind=true`、`independent_validation=false`。同一 Codex 编写与复核，无第二真人或独立研究伪称。

过程限制明确披露：初始实现草稿及未评分构造探针先于开发参考冻结；编写参考时已看过代码和门禁结果。25 组预测输入、15 份 request-SHA 对抗 mock 脚本与开发参考已在正式异步评分前冻结。旧初稿已保留；之后不为提分修改这些参考。评价不包含独立科学结论，不伪造盲审或 κ。

## 实施时门槛清单（实际完成结果见后文）

1. PR5 异步专项及 T37–T46 全部正反例。
2. 35 个 G1 时点 rule/mock、R0/R2 兼容、对抗矩阵与独立开发评测。
3. 当前源码全部 G2、六套 Schema、G1 strict、Ruff、seed、离线构建和完整 pytest。
4. 当前源码/工件 pin、AI 复核与错误分析、旧资产保全检查。

真实模型烟测需另行批准服务/模型/endpoint、数据外发、密钥注入和预算。建议上限 5 次、并发 1、重试 0、30 秒/次、1024 输出 token、人民币 5 元；价格或用量不明则停止。该实验不属于当前 PR5 硬门槛。


## 当前实际验收

- PR5 专项 **106 passed / exit 0**；全部 G2 **426 passed / exit 0**。对应 `pr5-final.xml` 与 `g2-verified.xml`。
- 六套 Schema、G1 strict、全域 Ruff、seed、前端离线构建均 exit 0。
- 最终矩阵为 **126 个 rule/mock 运行与 126 次独立评测进程**；每通道覆盖 G1 35 步、合成/兼容 68 步，共 206 步观察。主轨迹仍为 26 步，其他 G1 9 步另列；R0/R2 兼容没有改变父分组。
- 两通道原 rule Item 逐项完全相同；历史父目录 SHA 不变。所有最终评测进程 exit 0。rule 的模型选择参考指标为 not_applicable/零分母 null；不把未调用模型的基线记为模型能力通过。
- 结构合法的最终结果 `ok=true` 不表示模型尝试成功；对抗拒绝明确 `model_attempts_ok=false/degraded=true`，保留实际失败码与原 rule。mock token 不是消费，真实调用/费用均 0。
- 当前完整 pytest **977 passed / 1 skipped / 0 failed / exit 0**；本轮授权的单次沙箱外完整运行已经使用，未自动重跑。

### T37–T46 实际映射

| ID | 实际验证 |
|---|---|
| T37 | 五种模式/十句式正控、未知/重复/缺失/跨事件引用、文档/段落/span/SHA 负例。 |
| T38 | 合法定位不支持插件→训练速度；安全自由草稿 not_selected/not_verified，主文保留 rule；AI 语义复核独立记录。 |
| T39 | 40→400、单位、版本、量词、否定及 scope/指标污染均拒绝，不从无关字段补事实。 |
| T40 | 禁止模型写 tier/verification/独立支持/风险/行动；归属升级及删冲突一方拒绝。 |
| T41 | 数据内系统/终端/URL 指令只作引用数据；工具调用拒绝；JSON canary 不进入结果/草稿/trace/log；子进程能力审计。 |
| T42 | 401/403/402/429/500、连接、超时、截断、过滤、非法信封/JSON/重复键/NaN/超大响应；一次请求、无 repair/retry，已知 usage 保留、未知为 null；取消/失效不发布。 |
| T43 | 未来引用优先于坏 span；当前未来引用/坏 quote 先时间预检且调用 0；未来时点 poison 对早期 opaque。 |
| T44 | metadata_only/unknown 权限 hold 且不调用；摘要为显式 G2 合成契约正控，保持 unverified，不伪装真实 G1 来源端到端证据。 |
| T45 | seed 1/719、前缀、引用白名单、父工件不变、reference stat/open 拒绝；原 PR4 Persona 不变性回归及请求不含 Persona。 |
| T46 | 空/hold 无调用，无窗口时保持 coverage_unknown；32KiB/8KiB 精确字节界限、一步 16 次、累计请求/输入/响应边界及 1 单位越界，固定顺序保留所有事件。 |

### 后续发现与修订（保留失败）

- 初次异步专项：93 passed / 2 failed。摘要构造器缺少必要的 quantities 清空、polarity unknown、ambiguous true 等状态，PR3 出处检查正确拒绝；只修新测试构造器，后续 96 passed。
- 增加超大 HTTP 错误响应正交负例，尺寸门禁优先于错误正文解析，避免响应超过额度后仍保留内容。
- 初期矩阵将 rule 按 mock 专属表达选择标签计差异；最终比较器明确不适用，原开发标签没有修改。初期预测工件和差异记录保留，不把它们伪装为最终评测通过。
- 空集导出回归最初 418 passed / 1 failed：测试误以为来源窗口非空；原 fixture 明确没有窗口、只有 coverage_unknown。改为同时核对空窗口、原始缺口和零 Item，未虚构覆盖。之后完整 G2 426 passed。
- 最终矩阵脚本首次重用了原输入目录，WinError 183 / exit 1；无覆盖。改用全新 `pr5-matrix-003` 与输入目录完成，未放宽路径/覆盖断言。

## 复核、错误分析与预算观察

{
  "totals": {
    "accepted": 51,
    "fallback": 15,
    "skipped": 88,
    "model_calls": 0,
    "external_requests": 0
  },
  "review_cases": 25,
  "injected_fault_cases": 15
}

`fixtures/pr5/v1/review/review.jsonl` 记录实际创建时间、所见上下文、输入/参考/预测/config/source hash、定位与数值/范围检查，以及表达归属语义复核。语义 target 明确为 attributed_expression_fidelity，不是底层事实真实性。完整原句/风险保留不证明真实实验有效。

`.tmp/g2-pr5-evidence/error-analysis.jsonl` 保留对抗错误、根因、影响、反例、原 rule 保留及实际复测；没有要求管理员逐条审批或两真人标注。

## 命令、日志与 hash

完整 argv/cwd/UTC/elapsed/exit/log SHA 位于同名 `.command.json`。矩阵预测通过记录的 run_replay API 参数执行，外层脚本 argv 是实际命令；每次评测的子进程 argv/exit/stdout/stderr 另存于 matrix-final.json，不把等价命令说成实际 CLI 启动。

| 命令记录 | exit | log SHA256 |
|---|---:|---|
| collection.command.json | 0 | `c7100f1cf1cb57c639b6f87a97d6db2ae0142c6754840fb2607e156f854ec200` |
| frontend.command.json | 0 | `ccc00cb39c19873c1f4dc7a3bae23fc7a6f11649f0b561a771bcd7da02973df6` |
| g1-schema.command.json | 0 | `ad541cc67a0a6b6ce43b44815465079cd8b104a992b74d4c1a670e767b546d7d` |
| g1-strict.command.json | 0 | `ae200140ab0b4b55cfc9964459369e2e3a0970039dbfb7359501ad56ac18aa38` |
| g2-final.command.json | 1 | `dbe97795bfcca97f99ba197cbb08e92ed737469c75f3b128cd19d49ac5e575b6` |
| g2-verified.command.json | 0 | `2c248b8581e490de7857036f05db77ccd063074c778aa57374672d35cb9af3c8` |
| g2.command.json | 0 | `9ddb34ffbda4f01ac27ea5ffb4f9eeacff0c744ca15d34841368c55d6b2789ce` |
| guards-corrected.command.json | 0 | `5443d6ec6b6729330270a7766da5fae3edecc2c1face327fc67c9b2ca0020129` |
| guards-final.command.json | 0 | `f89934642dd3db97ccf37ad4d7088109bf89a0c01a96860f2c07215b5bbc2209` |
| guards-initial.command.json | 1 | `c3066a6583de85810b0c66f1ff0eba11098c09df21f5e549d1c7411dc18d0f96` |
| loopback-probe.command.json | 3 | `d11837bd9da0ceae8ceaccb4b7208dab8dcaf2e7524465bece0a0c0a5eae553a` |
| matrix-final-fresh.command.json | 0 | `a0903adf85f70b541e6a4599cf6dbee08235a1c468a13bdbda2e4fe6c2d47842` |
| matrix-final.command.json | 1 | `75c5b5d24316f9beca3bdf1c6c5af520ad69965eade02d0be862ff445053016a` |
| matrix.command.json | 0 | `a0903adf85f70b541e6a4599cf6dbee08235a1c468a13bdbda2e4fe6c2d47842` |
| pr1-schema.command.json | 0 | `a809da7e3eeb608fdce4300ac3ac61ce71461ebdd5e50803baaede51ffa8f3e1` |
| pr2-schema.command.json | 0 | `ffc3a2599f9fe6d9e1046f4e8cf20d19c948e76b87b838f97e144cb2df555923` |
| pr3-schema.command.json | 0 | `27303a3b8249fbfd930481b365912d74dd58bf322a1a4e137ceee3509558cf51` |
| pr4-schema.command.json | 0 | `a01abfe266c318861e969fd32356b29343cd6052cbbc61f0d7304dc7c71279de` |
| pr5-corrected.command.json | 0 | `3fb7c24313c7c139abf82e7e66ccf471c86f0503a16552dd18ce08cfcc7fb160` |
| pr5-final.command.json | 0 | `e41491207771676b01b0b8b318e35a7c179d5ab5ca14716cf163b51229b9dff4` |
| pr5-initial.command.json | 1 | `46b4555071729fd56e8239f9f1a25604cdef0563ee85c029f447447b13ce50b6` |
| pr5-schema-write.command.json | 0 | `86f275951f363daa9ee1f8ebb1b605842a9fb7608f7e8039653699ec0eb7d877` |
| pr5-schema.command.json | 0 | `86f275951f363daa9ee1f8ebb1b605842a9fb7608f7e8039653699ec0eb7d877` |
| pre-pr5.command.json | 0 | `5ec114817c964df90790e5c45742d4367ce302691c78d3b2ca8fc3e1a9d76a12` |
| ruff-initial.command.json | 1 | `8b52f2db77c8537a56c1f724b5223d51ba8319660dd2e097e459402be9d03f67` |
| ruff-verified.command.json | 0 | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| ruff.command.json | 0 | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| seed.command.json | 0 | `58f7ef252285f2f85998a3239a27e7e6a60352b63a2822df026bf893d38e2ce1` |

## 当前未关闭项

本轮完整 pytest 与最终 hash/旧资产保全确认均通过：977 passed / 1 skipped / 0 failed / exit 0。没有未关闭的产品测试失败。真实 HTTP/付费模型、独立语义研究、PR6/G3 准入仍未实施/未评测，不是本 PR 开发阻断项。


## 本轮完整回归与最终保全

授权来源：管理员直接回复“批准本轮异步验证及一次完整 pytest”，记录在 authorization.json。所有前置门槛通过后冻结源码，完整回归只执行一次。

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -o faulthandler_timeout=120 --basetemp=.tmp/g2-pr5-full-296ccc30b73b4a629961302d49befb79 --junitxml=.tmp/g2-pr5-evidence/full-approved.xml --log-file=.tmp/g2-pr5-evidence/full-runtime.log --log-file-level=WARNING
```

- 真实 UTC：2026-10-25T06:58:57.519139+00:00 → 2026-10-25T07:11:15.391991+00:00；耗时 737.872 秒。
- 实际结果：**977 passed / 1 skipped / 0 failed，exit 0**。其中当前 G2 426 条、PR5 106 条均通过。
- 原平台跳过：Windows 符号链接创建权限 1314；完整原因保留在 JUnit/final-verification.json，没有放宽断言。
- 源码/Schema/配置/输入/Mock/开发参考共 52 份冻结指纹保持不变；原 506 份受控文件仅 README/DATA_DICTIONARY 追加说明，其原前缀 hash 匹配。
- G1 frozen、PR1–PR4、旧 Goal/provider/业务源码、锁、历史报告和 archive/articles.json 字节保持不变。G1 pin 为 `5608f6c9f20d283f9274308fa98a277c535eb0d8d828fd0d863d6e1faafde06f`。
- 1260 份最终预测输出文件未出现合成凭据 canary。真实模型/外部请求/模型费用均 0；没有读取真实用户 DB 来证明“不变”。

| 证据 | SHA256 |
|---|---|
| full-approved.log | `41d5c1091f347145b6b42cda8f24787ebcfe80004c47457e383af74d7f8a3f87` |
| full-approved.xml | `b00e6b380e0f574e0e910b431b79c3b2d02bb33f560d9846a242a28f9f5198da` |
| full-runtime.log | `c0073f5ca788181eeffdd8e80fa2a3cbfd4d5c57edad2eed78cb7a3741edfe36` |
| source-snapshot.json | `83f56502b90ceab55e5e8a5bdd5f14293f5dd1769cfeecb8689f336f9568abc5` |
| matrix-final.json | `a0513f6113aeb7d2c6a2078cf404917aed18f49f046a9ec74c33cf0697311fa4` |
| final-verification.json | `44344ddefb4ea16c7eed3ac131e00a4b60fd93fcb0d88354bddd34f78df216f4` |

完整命令记录为 full-approved.command.json；所有失败的原始记录保留。报告中的 PASS 只指 PR5 ai_development 工程门槛，不指独立语义真实性、真实模型表达质量、G2 全阶段完成或 G3 准入。没有自动 commit/push/merge。

回滚只移除 PR5 新包、Schema v5、配置/Prompt/fixture/测试和两份追加文档中的 PR5 段落；保留此前工作区、冻结输入和所有历史工件。原 rule 路径继续独立可用，无数据库回滚。
