# G3 事实签名 P1 与根入口状态 P3 修复报告

日期：2026-10-29（Asia/Shanghai）。

**本轮离线 ai_development 工程验收 PASS；P1 修复和 P3 根入口更新已验证，独立复审仍待关闭。G3 尚未最终验收，G4 未授权。**

## 缺陷、修复与版本

原 `_claims()` 使用检索 tokenizer，删除 <、> 等符号。Persona、acknowledged、增量与重复判断继承该碰撞。用户提供的原生 G2→G3 序列化反例在修复前经实际断言失败：B4/P1 均 known=true、protected=false、material=0、duplicate=0.35、rank=6、180 秒未展示，退出 1。原反例文件路径/观察哈希见 preflight/review_probe.sha256.json，原始文件未改。

当前统一事实签名 `g3-grounded-fact-signature-v2`，policy SHA256 `70565148fe436fa823ef6a4063cbba7abb4c994cc34f19dc44bdc2451e367450`。NFC、忽略空白、保留全部符号与字符、数值/小数点/正负号及单位大小写。绑定原生 grounded scope 的 raw/normalized value/normalizer、proposition、quantity unit/quantifier、claim type 与生命周期 marker；不以 claim/document/citation ID、来源 ID 或 span offset 判新事实。只移除明确的前置 Reprint: 编辑标签。

Persona 使用同一内容投影和 G2 有限字段语法匹配声明；占位 ref 不进入签名，不为 Persona 声明增加引用、grounding 或验证状态。历史 not_known 否决、显式谱系、更正/撤回保护、硬证据门禁、排名权重和预算规则均保留。未修改 G1/G2 代码或冻结材料。

事实提取器独立版本化，不改既有评分权重/wire schema：PR2 comparison hash 包含 policy hash，PR3 config hash 包含完整 fact policy，PR4 按同一完整 hash 校验，ranking diagnostics 输出版本和 hash。复现封存 fact_signature_policy.json，prediction manifest、evaluation 和 acceptance 显式绑定 policy。旧评分/wire v1 字符串不能单独标识当前特征语义；旧排名虽可结构解析，其旧绑定不能通过当前 planner/acceptance。

## 原生集成与对照结果

原外部反例经相同断言重跑：B4/P1 都变为 known=false、protected=true、material=1、duplicate=0、rank=1、shown=true，退出 0。首次正例尝试仍被 PR4 旧 config hash 拒绝；同步完整 policy 绑定后通过，没有放宽验证。

新增 59 项测试涵盖符号、数值/小数、正负号、单位/大小写、grounded scope 和 quantity 元数据、旧 Persona/acknowledged/二者并存、当前 Persona 已知、版本元数据更新及转载。全部通过。最初聚焦运行 53 通过/3 失败：原生 G2 正确拒绝完全重复 content hash 的新 document version；改用真实的编辑元数据变化，保留事实正文后通过，门禁未弱化。首轮 campaign authoring 还暴露严格 tuple wire 构造错误；使用正式 JSON 验证入口修复，失败输出完整保存在 preflight/failed-authoring-01，未覆盖旧数据。

下表取自新冻结 campaign 的实际 prediction 工件，独立检查 180 秒下全部 26 行；输入经过完整原生 G2 生成与 G3 序列化绑定验证。

| 案例 | 算法 | 已知 | 保护 | 实质增量 | 重复惩罚 | 排名 | 展示 |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| symbol-ack | b4 | False | True | 1 | 0 | 1 | True |
| symbol-ack | p1 | False | True | 1 | 0 | 1 | True |
| symbol-persona | b4 | False | True | 1 | 0 | 1 | True |
| symbol-persona | p1 | False | True | 1 | 0 | 1 | True |
| symbol-ack-persona | b4 | False | True | 1 | 0 | 1 | True |
| symbol-ack-persona | p1 | False | True | 1 | 0 | 1 | True |
| inclusive | b4 | False | True | 1 | 0 | 1 | True |
| inclusive | p1 | False | True | 1 | 0 | 1 | True |
| equality | b4 | False | True | 1 | 0 | 1 | True |
| equality | p1 | False | True | 1 | 0 | 1 | True |
| numeric | b4 | False | True | 1 | 0 | 1 | True |
| numeric | p1 | False | True | 1 | 0 | 1 | True |
| decimal | b4 | False | True | 1 | 0 | 1 | True |
| decimal | p1 | False | True | 1 | 0 | 1 | True |
| unit | b4 | False | True | 1 | 0 | 1 | True |
| unit | p1 | False | True | 1 | 0 | 1 | True |
| unit-case | b4 | False | True | 1 | 0 | 1 | True |
| unit-case | p1 | False | True | 1 | 0 | 1 | True |
| word-control | b4 | False | True | 1 | 0 | 1 | True |
| word-control | p1 | False | True | 1 | 0 | 1 | True |
| unchanged-version | b4 | True | False | 0 | 0.35 | 6 | False |
| unchanged-version | p1 | True | False | 0 | 0.35 | 6 | False |
| unchanged-reprint | b4 | True | False | 0 | 0.35 | 6 | False |
| unchanged-reprint | p1 | True | False | 0 | 0.35 | 6 | False |
| current-persona | b4 | True | False | 0 | 0 | 6 | False |
| current-persona | p1 | True | False | 0 | 0 | 6 | False |

## 全量矩阵、验收与真实命令

新 campaign pin：`48a9f1d2c88a1cd863eefcfb84677e3bb0aab0667f4618cdea1958baf52205b9`。原 26 例及其标签逐项保留，另增 13 个明确标为 synthetic、nonblind、ai_development 的定向回归。它们不是独立留出集或真人 gold。39 案例 × 3 预算 × 11 变体 = 1287 组合/种子，两个种子实际运行 2574 次，语义一致。B0/B1/B3/B4/P1 同池；B2 单列；五项消融、180/420/900 秒、1/3/7 天均执行。

原 26 例的 858 个组合与前一轮输出逐项比较，ranking.events（含特征、分数、历史判断）、plan.events、display_order 全部一致。新 policy/config/comparison/ranking 指纹有意变化，不把这些元数据变化称为行为变化；没有重写历史输出。明细见 original_case_behavior_comparison.json。

**G3 630 passed，无 skip；仓库 1753 passed、1 个既有 Windows symlink 权限 skip、1 个既有第三方弃用警告；完整 JUnit 1754 节点。** 原测试正文/required-test pin 未改，59 节点和两个新测试源文件使用独立增量 manifest。Ruff、五组 schema、G1 strict、lexical baseline、离线前端兼容构建、inventory/JUnit、frozen compatibility 和 git diff --check 通过。没有前端接入、生产数据库、真实模型或新采集。

最终新三 pin 正例验收实际 PASS/0，随后保持三 pin 注入根 conftest，acceptance 和注册 runner 均拒绝退出 1，hook 未执行、未签发负例工件，清理前后 source release 一致。测试控制面 P1 修复继续有效，没有伪造日志或重新散列未可信输入来替换 pin。

精确工作树 source release：`b9146277f948fbd666e6666bc3005012915a48a8f104442ee25b50070bc49b12`；锚定 HEAD `fb42de414e56da7a0eb58e89d174d38a1495f02a`，未提交、未推送。

| 工件 | 实际 CLI 输出的 exact-byte manifest SHA256 | final 下路径 |
| --- | --- | --- |
| prediction | `50bca89c8fc0b932b716378f9b879b49b95e31d5ea0287d196a7cf0e9e13f3a3` | `prediction` |
| evaluation | `4b5dae3bd2ba7c82759aa2ca700ddf60e2520e45090f58e9cf0fde306dce0537` | `evaluation` |
| checks | `c90c20f0cb3fab1602add1a5e539bf52a55497d056c5534804d3ef0f15f6b9db` | `checks` |
| acceptance | `6afba55474f871242a015c1a88ae31127717214b0d1b3ebca1bd1044acbb3aea` | `probe/baseline-acceptance` |
| fixed_pin_probe | `2074ff1b8c799a1ff1b314ec18220194da18951f79c901594337161d518b7705` | `probe` |

原始工件根目录：`D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final`。完整 command ledger、native_matrix_assertions、scope_audit、raw JUnit、failures、耗时、来源、undefined_reason 均保留。每条命令记录 cwd、受控环境、真实退出码、开始/结束时间、耗时与日志 SHA256。负例非零为预期拒绝，失败开发运行也保留。

| 记录 | 退出码 | 秒 | 日志 SHA256 |
| --- | ---: | ---: | --- |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\preflight\author-new-campaign-02.command.json` | 0 | 18.971 | `12f5ee03da076d23601906ee9771f706b792d6a07c65bccddbd311e1c3d6faca` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\preflight\author-new-campaign.command.json` | 1 | 18.384 | `71ca796185fc4520163fbe9081b7d89c3d4e0362f2568fd7c7cde410d1ee1bd3` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\preflight\collect-new-tests.command.json` | 0 | 10.302 | `fb208f857bf9ef3bcb8844a8069f67d057afd470a4f405ead9ed9d216e9dc9c9` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\preflight\existing-rank-history.command.json` | 0 | 62.235 | `0c100007a4c25b499e0e9e507ecdd194b6ebb23635b05eb6b638544915241f32` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\preflight\fact-signature-focused-01.command.json` | 1 | 34.155 | `0576b93aadb1c8b374fcd817c9f97a76f0b58f746895ed05ca0ab5731a3ac127` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\preflight\fact-signature-focused-02.command.json` | 0 | 34.153 | `6a743b1668b3db583758a723bcd2fca07f69138aeb2b6f928f29284d245ce7c6` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\preflight\green-review-b4.command.json` | 1 | 1.715 | `8c3f0652b6403aefc0704a998389f0b475de8a7c4f8fcf01c41b8de240864ca0` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\preflight\green-review-v2-b4.command.json` | 0 | 1.708 | `fd824e05e0526332322d02b18a3ac8689ad20bd57a9185d55a182e55068e7a9b` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\preflight\green-review-v2-p1.command.json` | 0 | 1.650 | `8b2c2a33f4a2f0519eca9dadf3f49ed708d5d9366766b03c5fc7e5859fd8e300` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\preflight\old-acceptance-rejected.command.json` | 1 | 2.222 | `293d04fac15f0eef8a5eb649629eb565a33b531dfcbc533db62596917fc38a93` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\preflight\red-review-b4.command.json` | 1 | 1.888 | `9dec0c10fa7448c83b524224f4f06ecd2c7f6ee133fc48ace837ecac5339e874` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\preflight\red-review-p1.command.json` | 1 | 1.892 | `2526a5dfe459bbadcf2b73e226bc0bcc5ef3ade717c514098ff0accace028732` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\final\controller\checks.command.json` | 0 | 1507.176 | `0a5e693e36b35d6ae1d82da84a97c8e88b2a8351048075627081cf821dc3700f` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\final\controller\evaluate.command.json` | 0 | 536.838 | `7c02ebc36a6dad84106a64d91cb34bc2048442ddea92e4d57d9b6d8fd2e3dd2c` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\final\controller\final-diff.command.json` | 0 | 0.147 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\final\controller\fixed-pin-probe.command.json` | 0 | 444.018 | `27f1b000b1d68df4d8790e66fbf59e10d443bfe07368b0afb6e5a41ff6e1ba8e` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\final\controller\reproduce.command.json` | 0 | 966.379 | `769587e2570763165469f1b620ba88113b994048686509055c0be86acab49788` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\final\controller\staged-empty.command.json` | 0 | 0.053 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\final\prediction\worker-1.command.json` | 0 | 473.078 | `0a7bb5cee7218d9a922d9f58b616edab0015c63427f679d745aa78fba49da7a2` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\final\prediction\worker-719.command.json` | 0 | 489.212 | `cc08901425cc36d26247aed150a85e238253a8d3fed637482b156ee6168b4b5e` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\collect.command.json` | 0 | 7.483 | `18bad27d13015d2386b11350a53efd792013ccf71d6c3312495a2ee6a75aae9f` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\diff.command.json` | 0 | 0.114 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\frontend.command.json` | 0 | 4.988 | `e1f9af4ffff29729dfaac22951ad5b87c9650041ce2090ab2eadd81a5d183d64` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\full.command.json` | 0 | 1181.700 | `b9e163f6b9682cfc64c0de43a8cdc0d90319360af17c740ff0622bb8dffcd684` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\g1-strict.command.json` | 0 | 0.931 | `ae200140ab0b4b55cfc9964459369e2e3a0970039dbfb7359501ad56ac18aa38` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\g3.command.json` | 0 | 289.736 | `748d401f7d4960a2cc319dff5d114a180599e8c83577f2da1e021a3b55439dde` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\inventory.command.json` | 0 | 1.027 | `25201c50d9cadf40be91b464cedf646747aabf0601b47f78ca5e993db101685f` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\junit.command.json` | 0 | 2.667 | `f3e776fd9c2ddddf8cbe8e0fc31f6049dc0d920ac3ad16c6defad25015719e8f` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\ruff.command.json` | 0 | 0.203 | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\schema-g3-0.command.json` | 0 | 1.023 | `5f211f49cb13c515e6ce63841964e68606d23b2518b3ecb2f9207e7011a2ce93` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\schema-g3-1.command.json` | 0 | 0.926 | `8b00f5e2b5f9582e86d06ae7ab2fbdce5471c56221e35c263a8a4b3d98f7076e` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\schema-g3-2.command.json` | 0 | 1.182 | `55ef151f6862cf7816b0eef78b92f693c38ef18f82884f7e576adcb2788c150b` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\schema-g3-3.command.json` | 0 | 1.247 | `f5522a246648ccbec8c891b5e017bcb2547cf0aeb45607c04e419af1974c8864` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\schema-g3-4.command.json` | 0 | 1.272 | `b304363d883e292b8b8ad8c84397dfc21c9819cefdd8fdbafee4f3c86d75438e` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\seed.command.json` | 0 | 1.142 | `3e1f9417bb428bde02179a054b3d41807cdebc561f2af6a4868673d91d9e5f9c` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\final\probe\baseline.command.json` | 0 | 438.376 | `5e5a35db7b29286c54bbb8501a6004a1ac3084168f3f9cb94a528f56f2040d6d` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\final\probe\fixed-pins-with-hook.command.json` | 1 | 1.513 | `30e24befe7760151c9e775fc64a0098f757a84bd7afd7deb5ec548b6bff73e88` |
| `.tmp\evals\g3\claim-signature-fix-20261029-001\final\probe\runner-with-hook.command.json` | 1 | 1.472 | `7ff6d88f348c453f9f3ec4f0420ce59dc3af92362152bb4b69c50f2d7dae83d5` |

逐条实际 argv：

`.tmp\evals\g3\claim-signature-fix-20261029-001\preflight\author-new-campaign-02.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.build_fact_signature
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\preflight\author-new-campaign.command.json` — exit 1

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.build_fact_signature
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\preflight\collect-new-tests.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.pytest_runner --mode collect --inventory D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\preflight\node_inventory.json --control-record D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\preflight\collect.control.json
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\preflight\existing-rank-history.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m pytest -q tests/evals/g3/test_rankers.py tests/evals/g3/test_revisit.py --basetemp=D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\preflight\existing-rank-history-tmp -p no:cacheprovider
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\preflight\fact-signature-focused-01.command.json` — exit 1

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m pytest -q tests/evals/g3/test_fact_signature.py --basetemp=D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\preflight\fact-signature-focused-01-tmp -p no:cacheprovider
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\preflight\fact-signature-focused-02.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m pytest -q tests/evals/g3/test_fact_signature.py --basetemp=D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\preflight\fact-signature-focused-02-tmp -p no:cacheprovider
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\preflight\green-review-b4.command.json` — exit 1

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -c "import runpy; runpy.run_path('D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\claim-signature-fix-20261029-001\\preflight\\review_assertion.py',run_name='__main__')" C:\Users\Administrator\.codex\visualizations\2026\10\26\01a1795f-0662-7831-bfa3-7f7e765e50b0\pr5-r2-9e2514\.tmp\evals\g3\integration-claim-signature-180-probe.json b4
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\preflight\green-review-v2-b4.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -c "import runpy; runpy.run_path('D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\claim-signature-fix-20261029-001\\preflight\\review_assertion.py',run_name='__main__')" C:\Users\Administrator\.codex\visualizations\2026\10\26\01a1795f-0662-7831-bfa3-7f7e765e50b0\pr5-r2-9e2514\.tmp\evals\g3\integration-claim-signature-180-probe.json b4
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\preflight\green-review-v2-p1.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -c "import runpy; runpy.run_path('D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\claim-signature-fix-20261029-001\\preflight\\review_assertion.py',run_name='__main__')" C:\Users\Administrator\.codex\visualizations\2026\10\26\01a1795f-0662-7831-bfa3-7f7e765e50b0\pr5-r2-9e2514\.tmp\evals\g3\integration-claim-signature-180-probe.json p1
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\preflight\old-acceptance-rejected.command.json` — exit 1

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.acceptance --run D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\prediction --run-pin 36c1e7ffc8c74eb873adde00276b829261c99f643bbfb587c3d2821b91817fec --evaluation D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\evaluation --evaluation-pin 0a5e7a752d7793c815cd54d3b514e02a6f87554b34449ec9ccfd6809fd1325f2 --checks D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks --checks-pin 44205edfdfc5da66ec525eb8e1a6186237d2548d90dc41cf11b6c78bfab47d74 --out D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\preflight\old-must-not-accept
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\preflight\red-review-b4.command.json` — exit 1

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -c "import runpy; runpy.run_path('D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\claim-signature-fix-20261029-001\\preflight\\review_assertion.py',run_name='__main__')" C:\Users\Administrator\.codex\visualizations\2026\10\26\01a1795f-0662-7831-bfa3-7f7e765e50b0\pr5-r2-9e2514\.tmp\evals\g3\integration-claim-signature-180-probe.json b4
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\preflight\red-review-p1.command.json` — exit 1

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -c "import runpy; runpy.run_path('D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\claim-signature-fix-20261029-001\\preflight\\review_assertion.py',run_name='__main__')" C:\Users\Administrator\.codex\visualizations\2026\10\26\01a1795f-0662-7831-bfa3-7f7e765e50b0\pr5-r2-9e2514\.tmp\evals\g3\integration-claim-signature-180-probe.json p1
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\final\controller\checks.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.checks --out D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\final\controller\evaluate.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.evaluate --run D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\prediction --run-pin 50bca89c8fc0b932b716378f9b879b49b95e31d5ea0287d196a7cf0e9e13f3a3 --out D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\evaluation
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\final\controller\final-diff.command.json` — exit 0

```text
git diff --check
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\final\controller\fixed-pin-probe.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.control_probe --run D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\prediction --run-pin 50bca89c8fc0b932b716378f9b879b49b95e31d5ea0287d196a7cf0e9e13f3a3 --evaluation D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\evaluation --evaluation-pin 4b5dae3bd2ba7c82759aa2ca700ddf60e2520e45090f58e9cf0fde306dce0537 --checks D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks --checks-pin c90c20f0cb3fab1602add1a5e539bf52a55497d056c5534804d3ef0f15f6b9db --out D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\probe
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\final\controller\reproduce.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.reproduce --manifest D:\agent_project\cfaw-news\evals\intelligence_g3\manifests\pr5_fact_signature_campaign.json --manifest-sha256 48a9f1d2c88a1cd863eefcfb84677e3bb0aab0667f4618cdea1958baf52205b9 --out D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\prediction
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\final\controller\staged-empty.command.json` — exit 0

```text
git diff --cached --exit-code
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\final\prediction\worker-1.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.reproduce --manifest D:\agent_project\cfaw-news\evals\intelligence_g3\manifests\pr5_fact_signature_campaign.json --manifest-sha256 48a9f1d2c88a1cd863eefcfb84677e3bb0aab0667f4618cdea1958baf52205b9 --out D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\prediction --worker-seed 1
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\final\prediction\worker-719.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.reproduce --manifest D:\agent_project\cfaw-news\evals\intelligence_g3\manifests\pr5_fact_signature_campaign.json --manifest-sha256 48a9f1d2c88a1cd863eefcfb84677e3bb0aab0667f4618cdea1958baf52205b9 --out D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\prediction --worker-seed 719
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\collect.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.pytest_runner --mode collect --inventory D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\node_inventory.json --control-record D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\collect.control.json
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\diff.command.json` — exit 0

```text
git diff --check
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\frontend.command.json` — exit 0

```text
npm.cmd --offline run build -- --outDir D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\frontend-dist
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\full.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.pytest_runner --mode full --junit D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\full.xml --basetemp D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks-pytest\full --control-record D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\full.control.json
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\g1-strict.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_v1.validate --manifest D:\agent_project\cfaw-news\evals\intelligence_v1\manifests\dataset_manifest.json --strict
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\g3.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.pytest_runner --mode g3 --junit D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\g3.xml --basetemp D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks-pytest\g3 --control-record D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\g3.control.json
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\inventory.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.junit_inventory --inventory D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\node_inventory.json
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\junit.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.junit_inventory --inventory D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\node_inventory.json --junit D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\full.xml
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\ruff.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m ruff check backend tests evals
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\schema-g3-0.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.contracts --check-schemas
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\schema-g3-1.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.ranking_schema --check-schemas
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\schema-g3-2.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.revisit_cli --check-schemas
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\schema-g3-3.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.budget_cli --check-schemas
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\schema-g3-4.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.pr5_contracts --check-schemas
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\seed.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B evals/run_baseline.py --output D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks\seed.json
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\final\probe\baseline.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.acceptance --run D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\prediction --run-pin 50bca89c8fc0b932b716378f9b879b49b95e31d5ea0287d196a7cf0e9e13f3a3 --evaluation D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\evaluation --evaluation-pin 4b5dae3bd2ba7c82759aa2ca700ddf60e2520e45090f58e9cf0fde306dce0537 --checks D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks --checks-pin c90c20f0cb3fab1602add1a5e539bf52a55497d056c5534804d3ef0f15f6b9db --out D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\probe\baseline-acceptance
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\final\probe\fixed-pins-with-hook.command.json` — exit 1

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.acceptance --run D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\prediction --run-pin 50bca89c8fc0b932b716378f9b879b49b95e31d5ea0287d196a7cf0e9e13f3a3 --evaluation D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\evaluation --evaluation-pin 4b5dae3bd2ba7c82759aa2ca700ddf60e2520e45090f58e9cf0fde306dce0537 --checks D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\checks --checks-pin c90c20f0cb3fab1602add1a5e539bf52a55497d056c5534804d3ef0f15f6b9db --out D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\probe\must-not-pass
```

`.tmp\evals\g3\claim-signature-fix-20261029-001\final\probe\runner-with-hook.command.json` — exit 1

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.pytest_runner --mode collect --inventory D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\probe\must-not-collect.json --control-record D:\agent_project\cfaw-news\.tmp\evals\g3\claim-signature-fix-20261029-001\final\probe\must-not-run.json
```

## 指标、失败、耗时与限制

失败记录 572 条，包括 {'duplicate_presented': 341, 'important_miss': 231}，保留可评估重要遗漏及重复展示；未改历史结果或排除预算遗漏来改善指标。数据来源仍为合成、复用、非盲 AI 开发，独立测试家族为 0。新定向案例专门针对已知缺陷，不能把它们包装成独立测试或算法泛化提升。

| 变体 | 重要召回 n/d | 重复 n/d |
| --- | --- | --- |
| b0 | 120/141 | 31/315 |
| b1 | 120/141 | 31/315 |
| b3 | 120/141 | 31/315 |
| b4 | 120/141 | 31/315 |
| p1 | 120/141 | 31/315 |

保留 B4；P1 没有独立稳定改善证据。新增修复案例上的保护成功属于缺陷回归，不能据此宣布 P1 胜出。签名仍是保守的字面/结构变化代理，不声称语义等价推理、单位换算、事实真伪或真实用户效果。读取时间未校准，贪心预算不是最优背包。每项指标按适用窗口记录样本/家族，数据集总量单列；不同种子不增加独立样本。

# G3 PR5 offline AI development report

Synthetic, nonblind, reused development regression material. No independent human gold, held-out test, production readiness or real-user effect is established.

Fact feature policy: g3-grounded-fact-signature-v2; SHA256: 70565148fe436fa823ef6a4063cbba7abb4c994cc34f19dc44bdc2451e367450. Scoring weights and wire schemas retain their registered versions; the independent fact extractor revision is bound in comparisons and the reproduction policy artifact.

Event product families: 17; independent test families: 0.

Samples below count correlated event-by-case-by-budget states. Reprints, horizons and repeated seeds are not independent samples. Seeds are checked for equality and counted once.

| Variant | Axis/cell | Important recall n/d | Miss n/d | Duplicate n/d | nDCG DCG/IDCG | samples | families |
| --- | --- | --- | --- | --- | --- | --- | --- |
| b0 | all/all | 120/141 | 21/141 | 31/315 | 581.3/710.06 | 375 | 17 |
| b0 | budget/180 | 31/47 | 16/47 | 9/72 | 193.77/236.69 | 125 | 17 |
| b0 | budget/420 | 42/47 | 5/47 | 11/119 | 193.77/236.69 | 125 | 17 |
| b0 | budget/900 | 47/47 | 0/47 | 11/124 | 193.77/236.69 | 125 | 17 |
| b0 | revisit/1 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| b0 | revisit/3 | 39/39 | 0/39 | 13/216 | 144.24/273 | 252 | 7 |
| b0 | revisit/7 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| b1 | all/all | 120/141 | 21/141 | 31/315 | 574.87/710.06 | 375 | 17 |
| b1 | budget/180 | 31/47 | 16/47 | 9/72 | 191.62/236.69 | 125 | 17 |
| b1 | budget/420 | 42/47 | 5/47 | 11/119 | 191.62/236.69 | 125 | 17 |
| b1 | budget/900 | 47/47 | 0/47 | 11/124 | 191.62/236.69 | 125 | 17 |
| b1 | revisit/1 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| b1 | revisit/3 | 39/39 | 0/39 | 13/216 | 137.8/273 | 252 | 7 |
| b1 | revisit/7 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| b3 | all/all | 120/141 | 21/141 | 31/315 | 574.87/710.06 | 375 | 17 |
| b3 | budget/180 | 31/47 | 16/47 | 9/72 | 191.62/236.69 | 125 | 17 |
| b3 | budget/420 | 42/47 | 5/47 | 11/119 | 191.62/236.69 | 125 | 17 |
| b3 | budget/900 | 47/47 | 0/47 | 11/124 | 191.62/236.69 | 125 | 17 |
| b3 | revisit/1 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| b3 | revisit/3 | 39/39 | 0/39 | 13/216 | 137.8/273 | 252 | 7 |
| b3 | revisit/7 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| b4 | all/all | 120/141 | 21/141 | 31/315 | 710.06/710.06 | 375 | 17 |
| b4 | budget/180 | 31/47 | 16/47 | 9/72 | 236.69/236.69 | 125 | 17 |
| b4 | budget/420 | 42/47 | 5/47 | 11/119 | 236.69/236.69 | 125 | 17 |
| b4 | budget/900 | 47/47 | 0/47 | 11/124 | 236.69/236.69 | 125 | 17 |
| b4 | revisit/1 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| b4 | revisit/3 | 39/39 | 0/39 | 13/216 | 273/273 | 252 | 7 |
| b4 | revisit/7 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| no_duplicate | all/all | 120/141 | 21/141 | 31/315 | 710.06/710.06 | 375 | 17 |
| no_duplicate | budget/180 | 31/47 | 16/47 | 9/72 | 236.69/236.69 | 125 | 17 |
| no_duplicate | budget/420 | 42/47 | 5/47 | 11/119 | 236.69/236.69 | 125 | 17 |
| no_duplicate | budget/900 | 47/47 | 0/47 | 11/124 | 236.69/236.69 | 125 | 17 |
| no_duplicate | revisit/1 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| no_duplicate | revisit/3 | 39/39 | 0/39 | 13/216 | 273/273 | 252 | 7 |
| no_duplicate | revisit/7 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| no_exploration | all/all | 120/141 | 21/141 | 31/315 | 710.06/710.06 | 375 | 17 |
| no_exploration | budget/180 | 31/47 | 16/47 | 9/72 | 236.69/236.69 | 125 | 17 |
| no_exploration | budget/420 | 42/47 | 5/47 | 11/119 | 236.69/236.69 | 125 | 17 |
| no_exploration | budget/900 | 47/47 | 0/47 | 11/124 | 236.69/236.69 | 125 | 17 |
| no_exploration | revisit/1 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| no_exploration | revisit/3 | 39/39 | 0/39 | 13/216 | 273/273 | 252 | 7 |
| no_exploration | revisit/7 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| no_history | all/all | 120/141 | 21/141 | 31/315 | 710.06/710.06 | 375 | 17 |
| no_history | budget/180 | 31/47 | 16/47 | 9/72 | 236.69/236.69 | 125 | 17 |
| no_history | budget/420 | 42/47 | 5/47 | 11/119 | 236.69/236.69 | 125 | 17 |
| no_history | budget/900 | 47/47 | 0/47 | 11/124 | 236.69/236.69 | 125 | 17 |
| no_history | revisit/1 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| no_history | revisit/3 | 39/39 | 0/39 | 13/216 | 273/273 | 252 | 7 |
| no_history | revisit/7 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| no_material | all/all | 120/141 | 21/141 | 31/315 | 710.06/710.06 | 375 | 17 |
| no_material | budget/180 | 31/47 | 16/47 | 9/72 | 236.69/236.69 | 125 | 17 |
| no_material | budget/420 | 42/47 | 5/47 | 11/119 | 236.69/236.69 | 125 | 17 |
| no_material | budget/900 | 47/47 | 0/47 | 11/124 | 236.69/236.69 | 125 | 17 |
| no_material | revisit/1 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| no_material | revisit/3 | 39/39 | 0/39 | 13/216 | 273/273 | 252 | 7 |
| no_material | revisit/7 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| no_novelty_material | all/all | 120/141 | 21/141 | 31/315 | 710.06/710.06 | 375 | 17 |
| no_novelty_material | budget/180 | 31/47 | 16/47 | 9/72 | 236.69/236.69 | 125 | 17 |
| no_novelty_material | budget/420 | 42/47 | 5/47 | 11/119 | 236.69/236.69 | 125 | 17 |
| no_novelty_material | budget/900 | 47/47 | 0/47 | 11/124 | 236.69/236.69 | 125 | 17 |
| no_novelty_material | revisit/1 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| no_novelty_material | revisit/3 | 39/39 | 0/39 | 13/216 | 273/273 | 252 | 7 |
| no_novelty_material | revisit/7 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| p1 | all/all | 120/141 | 21/141 | 31/315 | 710.06/710.06 | 375 | 17 |
| p1 | budget/180 | 31/47 | 16/47 | 9/72 | 236.69/236.69 | 125 | 17 |
| p1 | budget/420 | 42/47 | 5/47 | 11/119 | 236.69/236.69 | 125 | 17 |
| p1 | budget/900 | 47/47 | 0/47 | 11/124 | 236.69/236.69 | 125 | 17 |
| p1 | revisit/1 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |
| p1 | revisit/3 | 39/39 | 0/39 | 13/216 | 273/273 | 252 | 7 |
| p1 | revisit/7 | 9/9 | 0/9 | 9/18 | 63/63 | 18 | 1 |

## Revisit metric support

Revisit metrics count candidate-event states only inside their own window. Outside-window cases contribute zero samples and zero families. dataset_support separately records the whole cell; it is never substituted for metric support.

| Variant | Window | Recall n/d | Applicable samples | Applicable families | Undefined reason |
| --- | --- | --- | --- | --- | --- |
| b0 | 1d | 9/9 | 18 | 1 |  |
| b0 | 3d | 39/39 | 252 | 7 |  |
| b0 | 7d | 9/9 | 18 | 1 |  |
| b1 | 1d | 9/9 | 18 | 1 |  |
| b1 | 3d | 39/39 | 252 | 7 |  |
| b1 | 7d | 9/9 | 18 | 1 |  |
| b3 | 1d | 9/9 | 18 | 1 |  |
| b3 | 3d | 39/39 | 252 | 7 |  |
| b3 | 7d | 9/9 | 18 | 1 |  |
| b4 | 1d | 9/9 | 18 | 1 |  |
| b4 | 3d | 39/39 | 252 | 7 |  |
| b4 | 7d | 9/9 | 18 | 1 |  |
| no_duplicate | 1d | 9/9 | 18 | 1 |  |
| no_duplicate | 3d | 39/39 | 252 | 7 |  |
| no_duplicate | 7d | 9/9 | 18 | 1 |  |
| no_exploration | 1d | 9/9 | 18 | 1 |  |
| no_exploration | 3d | 39/39 | 252 | 7 |  |
| no_exploration | 7d | 9/9 | 18 | 1 |  |
| no_history | 1d | 9/9 | 18 | 1 |  |
| no_history | 3d | 39/39 | 252 | 7 |  |
| no_history | 7d | 9/9 | 18 | 1 |  |
| no_material | 1d | 9/9 | 18 | 1 |  |
| no_material | 3d | 39/39 | 252 | 7 |  |
| no_material | 7d | 9/9 | 18 | 1 |  |
| no_novelty_material | 1d | 9/9 | 18 | 1 |  |
| no_novelty_material | 3d | 39/39 | 252 | 7 |  |
| no_novelty_material | 7d | 9/9 | 18 | 1 |  |
| p1 | 1d | 9/9 | 18 | 1 |  |
| p1 | 3d | 39/39 | 252 | 7 |  |
| p1 | 7d | 9/9 | 18 | 1 |  |

## Interpretation and failures

B4 remains the baseline. P1 is not required to win; no independent stable improvement has been demonstrated. Per-job metrics, numerator/denominator, sample and family counts, data_source and undefined_reason are retained in metrics.json.

Failure records: 572, including every evaluable important miss and duplicate presentation. budget_unmet never removes an important event from a denominator. A protected item may fail to fit even when an alternative combination of minimum projections could fit; the registered greedy allocator does not solve a knapsack optimum.

nDCG@10 measures eligible rank order with all reference gains in IDCG; recall uses actual budget selection. Duplicate labels describe authored unchanged delivered events; opened does not establish knowledge. Domain coverage is lexical; exploration exposure is a feature proxy.

## Ablations and B2

no_history disables all history-dependent P1 score terms (novelty, material change, exploration, duplicate). no_material, no_novelty_material, no_exploration and no_duplicate zero their registered contributions without renormalization. Hard eligibility and mandatory update protection remain active in all variants. These are score ablations, not removal of safety/history validation. They use a separate experiment envelope, never a changed PR2/PR3 algorithm version.

B2 is reported separately in b2_g2_contribution. G2 already merged the event pool; B2 preserves identity and equals B1. G2 aggregation gain is undefined because there is no unmerged-document comparison arm. It is not credited to G3.

## Cost, reproducibility and limits

Actual prediction runs: 2574; semantic outputs per seed: 1287; all cross-seed semantic hashes equal.

Measured prediction wall seconds (sum of per-job timers): 952.313790; mean 0.369974; max 2.304847. Process commands separately include startup, validation and serialization overhead.

External requests and model calls: 0, network guarded during prediction. Token count and provider cost are undefined (no model/provider invocation); no estimated billing or host electricity/hardware cost is asserted.

No confidence interval or significance claim: purposive reused nonblind families, no independent holdout. Reading time is a deterministic uncalibrated estimate. Material change uses attributed statement-set proxies. Source coverage gaps never confirm absence of updates.

The source release binds the exact working tree, anchor commit, tests, schemas, configs, frozen fixtures and pytest control plane. The approved root configuration and conftest hashes, pytest/pluggy code and bytecode, plugin discovery metadata, startup files and controlled environment are recorded. Autoload is disabled; unapproved config, hook, plugin or environment injection is rejected. Actual collect/G3/full execution records list loaded plugin origins. It does not claim these uncommitted changes are a published commit. Remote CI, Linux portability, live providers, DB/API/frontend integration and user research are not verified by this report.

G4 requires independent PR5 review and owner approval. Preserve the offline input/output contract and diagnostics before any separate integration design.


## 根入口、保全与 G4 清单

根 README 已更新到 PR5 复现/验收/审查修复阶段，移除当前“停在 PR4、不开始 PR5”的过时陈述，链接本报告、G3 README 与 G4 handoff。PR4/原 PR5 交付和前次修复记录继续作为历史文件保留。G3 未写成最终通过，独立复审和所有者最终验收待进行。

开工时 879 个公开文件中 868 个字节不变，修改 11 个限定文件，删除 0；原测试、旧 campaign/标签、schema 和 G1/G2/历史报告均不变。

G4 前须复核：本 P1 的原生序列化/Persona/ack/符号/数值/单位/转载对照；事实 policy 版本及旧工件拒绝；完整矩阵、失败案例、测试控制面和真实 JUnit；所有者批准具体 G4 范围。持久化、API/前端、阅读估时、真人研究、Linux/远程 CI、生产部署与真实效果仍需单独验证。清单见 docs/G3_G4_HANDOFF.md。本轮停止，不开始 G4。
