# G3-PR5 审查修复与重新验收报告

日期：2026-10-29（Asia/Shanghai）。

**本轮 ai_development 离线工程验收 PASS；三项审查缺陷已修复并实际回归。独立复审及所有者最终验收仍待进行，G4 未授权。**

本报告替代历史 PR5 自验收作为当前代码的证据。原 `PR5_ACCEPTANCE.md` 和原始工件逐字节保留；其旧 PASS 不能关闭本轮测试控制面问题。未修改 G1/G2 冻结材料、历史测试、原有 pin、ranker/planner 或开发数据。

结果仍来自复用、非盲、合成 AI 开发材料，独立留出家族为 0；不构成独立真人 gold、真实用户效果、生产就绪或新 G4 授权。没有接入生产数据库、前端、模型或新采集，没有 commit/push。

## 三项修复及真实反例

1. **P1 测试控制面。** 修复前实际运行必失败 sentinel，退出 1；根 conftest hook 令它退出 0。保持原 prediction/evaluation/checks 三个可信 pin，旧验收仍 PASS/0，acceptance pin 保持 `6ff81f5be276b8fff1c1b5a3ed1ffa4f4f1d203f0c7b5e2ba2fa90d9dc9b4f26`。反例和真实日志保存在 `preflight/red-fixed-pin-control.json`、`red-*.command.json`；没有覆盖历史结果。

   当前 release v2 在 pytest 导入 conftest 前校验根目录及 tests 下控制文件集合和批准哈希。配置固定 pyproject、rootdir、confcutdir，禁用插件自动加载；只显式加载库存插件，并逐阶段验证已加载插件及 hook 的来源。绑定 pytest/_pytest/pluggy 源码与字节码、pytest11 安装元数据、启动路径文件及受控环境。实际 collect/G3/full 会话记录 before/after 和插件清单；verify_checks 同时核对控制记录、真实命令及完整 JUnit。环境注入和未知配置/hook/plugin 拒绝。

   已运行新的固定 pin 端到端回归：同一组新 prediction/evaluation/checks pin，干净控制面真实 PASS/0；加入根 hook 后 acceptance NOT_MET/1、注册 runner 退出 1，均报 G3_TEST_CONTROL_UNAPPROVED。hook 的顶层 marker 未执行，没有签发负例验收工件；只移除本探针创建且字节未变的 conftest，恢复前后 release 完全一致。旧历史 pin 在当前代码下也被 G3_SOURCE_MISMATCH 拒绝。

2. **P2 回访支持规模。** RevisitCoverage@1/3/7d 逐指标限定窗口，窗口外案例贡献 0 个样本/家族，并保留 outside_revisit_window。汇总按该指标适用样本与家族并集计算，dataset_support 独立列出全 cell 总量。单案例加入 crowded14 后仍为 1/1、1 个样本/1 家族，全数据 cell 才是 15/14。正式 P1 每个窗口均为 9/9、18 个相关事件状态/1 家族，全数据 cell 为 141/16。重新生成 evaluation v2、Markdown、失败案例及 acceptance v2。

3. **P3 schema 检查。** schema-g3-1 改为 ranking_schema --check-schemas，实际比较 RankingConfig/RankingResult 的完整 v2 文件集合及规范字节；冻结 schema 未改。真实正确 schema 返回 0，错误/缺失/额外 schema 各返回 1，未知参数返回 2。原 ranking_contracts 无 CLI 的忽略参数反例实际退出 0，保留在 red-schema-ignored 记录。

新增 31 项审查回归使用独立增量 manifest，旧测试正文和 required-test pins 均未改。最初新测试为 29 通过/2 失败，暴露动态插件来源异常诊断与默认 schema 目录边界错误；修正实现后聚焦测试 31/31，通过以下完整回归。最初 29/2 来自本轮实际终端输出，未补造不存在的日志。

## 完整矩阵与门禁

26 案例 × 3 预算 × 11 变体 = 858 组合/种子；种子 1/719 实际预测 1716 次，语义逐项一致；858 个语义哈希也与历史原输出逐项一致，说明未调权重或改排序/预算行为来通过门禁。780 个主比较测量，B2 的 78 个测量单独归因。包含全部五项评分消融、180/420/900 秒和 1/3/7 天矩阵。

完整 G3：**571 passed，无 skip**。完整仓库：**1694 passed / 1 skipped**，精确覆盖 **1695** 个节点。唯一 skip 是既有 Windows 符号链接权限 1314 豁免；保留既有第三方 TestClient 弃用警告。Ruff、五组当前 schema、G1 strict、lexical baseline、完整 inventory/JUnit、离线前端兼容构建及 diff 检查均执行成功。前端构建仅用于仓库回归，输出在忽略的临时目录，没有前端集成。

| 门禁 | 状态与证据 |
| --- | --- |
| budget_coverage_archive | PASS / recomputed_plans_and_required_regressions |
| complete_matrix_and_determinism | PASS / exact_jobs_and_two_seed_semantics |
| honest_metrics_and_failures | PASS / recomputed_reference_counts_and_report |
| inputs_time_identity_history_evidence | PASS / recomputed_predictions_and_required_regressions |
| regression_and_frozen_compatibility | PASS / exact_full_JUnit_and_frozen_source_pins |
| reproducible_source_config_tests_artifacts | PASS / three_externally_pinned_manifests |

缺工件、pin 错误、source/config 不同、命令未运行/非零、测试缺失或非豁免跳过、工件集合/哈希不符、矩阵/种子/重算不一致均拒绝。新控制面门禁叠加在既有门槛上；本轮没有降低阈值或替换历史数据。

## 可信 pin 与控制面

输入 campaign 仍为 `56f2244812449db5ddb5a8bd2384cb302a3f9d66fb1205be167e9308da530daf`。

精确工作树 release：`cd651a26a6ee11e88b2f69e52eb5e762239dfdd56761ce4bae5fe98c90676695`；锚定提交 `fb42de414e56da7a0eb58e89d174d38a1495f02a`。本轮未提交，不能把锚定提交描述为包含本轮变更的发布提交。

| 工件 | exact-byte manifest SHA256 | 本轮目录（相对 final） |
| --- | --- | --- |
| prediction | `36c1e7ffc8c74eb873adde00276b829261c99f643bbfb587c3d2821b91817fec` | `prediction` |
| evaluation | `0a5e7a752d7793c815cd54d3b514e02a6f87554b34449ec9ccfd6809fd1325f2` | `evaluation` |
| checks | `44205edfdfc5da66ec525eb8e1a6186237d2548d90dc41cf11b6c78bfab47d74` | `checks` |
| acceptance | `f3903666b989321b9c26bf128eb88a340284756de95c99355b370c2f48161845` | `probe/baseline-acceptance` |
| fixed_pin_probe | `9c773c93570b036b673dc26176962401a0a8cb39745f10ecc8c02beb2b2bd09b` | `probe` |

本地原始工件根目录：`D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final`。各 manifest 封存完整工件集合及哈希；实际 CLI 打印的输出 pin 独立保存后传递，没有将输入内部哈希重新当作可信 pin。

运行时：Python 3.12.14 / win32；pytest 9.1.1，pluggy 1.6.0。已安装 pytest11 元数据：`[{"name": "anyio", "value": "anyio.pytest_plugin", "distribution": "anyio", "version": "4.15.1"}]`；自动加载关闭。

批准控制文件仅 pyproject.toml 与 tests/evals/conftest.py 的固定哈希；合法配置变更仍须显式评审 policy 并重新检查，不能复用旧 pin。PYTEST_CURRENT_TEST 仅作诊断不参与指纹，PYTEST_VERSION 必须与单独绑定的运行时版本一致。六项子进程环境值逐命令记录，命令包含 cwd、开始/结束时间、实际退出码、耗时、日志 SHA256；worker 的不同 HASHSEED 也分别记录。

## 每条验证命令与实际退出码

包含修复前反例、修复后负例、完整矩阵/回归及最终固定 pin 回归。负例的非零退出为预期拒绝；失败记录未删除。聚焦 pytest 为补充开发检查，正式 gate 使用注册 runner 的全量会话及精确 JUnit。

完整机器命令账本：`D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\command_ledger.json`；SHA256 `d22605c3574c38497099d24b33ee0242803d0e00e46157cbf22c4e2a84e2ea67`。

| 记录路径 | 退出码 | 实测秒 | 日志 SHA256 |
| --- | ---: | ---: | --- |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\collect-guard-smoke.command.json` | 0 | 11.213 | `e20d2b6a82e322f19e52456f3d2758ee3917377958035906551910439c450b00` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\collect-review.command.json` | 0 | 7.405 | `1bc5c4429d88b66f71d8db8c1c36c626bff2301670f328ed65c365b7b735b1bf` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\focused-green-01.command.json` | 0 | 44.824 | `1f6d8ae87820f7a16b0f834f123d61500345da08ca7ebde7d5fdac3e0c387a31` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\green-historical-pins-rejected.command.json` | 1 | 2.571 | `293d04fac15f0eef8a5eb649629eb565a33b531dfcbc533db62596917fc38a93` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\green-schema-changed.command.json` | 1 | 1.036 | `d03f4114b2d66ebabb6671f9f05ebec8b25294590942ffc56d58a6e6302d1cfc` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\green-schema-extra.command.json` | 1 | 0.991 | `d03f4114b2d66ebabb6671f9f05ebec8b25294590942ffc56d58a6e6302d1cfc` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\green-schema-missing.command.json` | 1 | 0.983 | `d03f4114b2d66ebabb6671f9f05ebec8b25294590942ffc56d58a6e6302d1cfc` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\green-schema-unknown.command.json` | 2 | 0.979 | `c1299d921e49dd7dbddaa47f22a6a1e5eee06d2a26a10a12d1796c19abb5cd21` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\red-body-no-hook.command.json` | 1 | 2.834 | `e067e5268b1938500ba310587c88ef3e46339071f591bebf9203e58bd8f0f2ce` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\red-body-with-hook.command.json` | 0 | 2.396 | `18d7ed42ae2657f5e655109e8219c4de53db53651e2cb8b297569b3b68056dcb` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\red-fixed-pins.command.json` | 0 | 175.711 | `60205ad293e0de2c57623f50658a53746ba8799b03f77e4371f3929dc4cfddb0` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\red-schema-ignored.command.json` | 0 | 1.287 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\final\controller\checks.command.json` | 0 | 1043.328 | `bb58c2b655f6d1973a8afa60ada14079dcbc54dfa32cca5e22fd6ce892cb40e5` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\final\controller\evaluate.command.json` | 0 | 118.443 | `207efff58c7ea4f88730020588f10013c3874ff57923f8cd5a6db55d0dafd469` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\final\controller\fixed-pin-probe.command.json` | 0 | 223.819 | `003b25a2070387d7616cf0a56736c90c71d507a733072b8e81a10c55bde08d47` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\final\controller\reproduce.command.json` | 0 | 334.316 | `70a3adce4571c21d1b5684aa4709758d13eb1a08e4b7901c05a0aa57c9aaf569` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\final\controller\scope-audit.command.json` | 0 | 3.674 | `76ad30e418afcc1706833200b8fb42126665a41308c2686a592a27854d2737c0` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\final\controller\staged-empty.command.json` | 0 | 0.053 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\final\prediction\worker-1.command.json` | 0 | 166.312 | `910e4ea5c1effdce1699a5a2f2d39124e86e672ebbe8392aa832dd22cd6a2569` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\final\prediction\worker-719.command.json` | 0 | 164.962 | `9742644257f29570e7141c3212562cff3f281c9b7e1a22dc4ab8060e7b8db7c5` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\collect.command.json` | 0 | 5.480 | `5fff7710fd7cde0a9356ee2ddc47c67f5254da046799d52133cc730b95d69e69` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\diff.command.json` | 0 | 0.082 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\frontend.command.json` | 0 | 6.088 | `d73c45e035fc07e33c10a466a1d47681e02df02ab6334ea5b76a3aaaac6eafe0` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\full.command.json` | 0 | 871.200 | `9fab0eca66577f5faf796ea1915a000e9c92dd21ab64d57ac1c48e96d6710fe0` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\g1-strict.command.json` | 0 | 1.042 | `ae200140ab0b4b55cfc9964459369e2e3a0970039dbfb7359501ad56ac18aa38` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\g3.command.json` | 0 | 139.466 | `2e240846ff1745e353bc088f7a8ec2cccaba7667d4671e894ce5fb6f1606929f` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\inventory.command.json` | 0 | 0.911 | `5c1bf989338fbf18558c5ba39056b01b4c69b24a7126e569f568aa9c6f531d9c` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\junit.command.json` | 0 | 2.398 | `cd98c0b3895c2b14a2267200e295bd6f6469d6cacb26fa4a14b4cb246e0dbd5c` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\ruff.command.json` | 0 | 0.229 | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\schema-g3-0.command.json` | 0 | 0.933 | `5f211f49cb13c515e6ce63841964e68606d23b2518b3ecb2f9207e7011a2ce93` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\schema-g3-1.command.json` | 0 | 0.876 | `8b00f5e2b5f9582e86d06ae7ab2fbdce5471c56221e35c263a8a4b3d98f7076e` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\schema-g3-2.command.json` | 0 | 1.062 | `55ef151f6862cf7816b0eef78b92f693c38ef18f82884f7e576adcb2788c150b` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\schema-g3-3.command.json` | 0 | 1.126 | `f5522a246648ccbec8c891b5e017bcb2547cf0aeb45607c04e419af1974c8864` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\schema-g3-4.command.json` | 0 | 1.154 | `b304363d883e292b8b8ad8c84397dfc21c9819cefdd8fdbafee4f3c86d75438e` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\seed.command.json` | 0 | 1.092 | `c7e8d8a08ffb6e7a65257bec57e8c61c09fb47e1622503e75aefa4fa7fa1c3e7` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\final\probe\baseline.command.json` | 0 | 217.642 | `53574531622aa8e786e40ab29e8f5e8180817c293536dd000975f1e7425ed458` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\final\probe\fixed-pins-with-hook.command.json` | 1 | 1.628 | `30e24befe7760151c9e775fc64a0098f757a84bd7afd7deb5ec548b6bff73e88` |
| `.tmp\evals\g3\pr5-review-fix-20261029-001\final\probe\runner-with-hook.command.json` | 1 | 1.465 | `7ff6d88f348c453f9f3ec4f0420ce59dc3af92362152bb4b69c50f2d7dae83d5` |

以下为逐条真实 argv；对应 cwd/环境/日志哈希见同名命令记录及上述账本。

`.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\collect-guard-smoke.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.pytest_runner --mode collect --inventory D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\guard-inventory.json --control-record D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\guard-control.json
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\collect-review.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.pytest_runner --mode collect --inventory D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\review-inventory.json --control-record D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\review-control.json
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\focused-green-01.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m pytest -q tests/evals/g3/test_pr5_review.py --basetemp=D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\focused-green-01-tmp -p no:cacheprovider
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\green-historical-pins-rejected.command.json` — exit 1

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.acceptance --run D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-20261028-003\prediction --run-pin 8b0d6a9d3dbc0441375d288af54e5ac842b33fd5cd8698a7e09ab34ca7b7d2b4 --evaluation D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-20261028-003\evaluation --evaluation-pin f8196587edf10349c8fa1565092410ea49b8367148e709e5d0701b76a1bc2204 --checks D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-20261028-003\checks --checks-pin c3ec5b5298187c3ee263e4e06c11a7b2b86fb6a7953ca40107d43d8856ff8949 --out D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\old-must-not-accept
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\green-schema-changed.command.json` — exit 1

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.ranking_schema --check-schemas --schema-dir D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\schema-changed
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\green-schema-extra.command.json` — exit 1

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.ranking_schema --check-schemas --schema-dir D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\schema-extra
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\green-schema-missing.command.json` — exit 1

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.ranking_schema --check-schemas --schema-dir D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\schema-missing
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\green-schema-unknown.command.json` — exit 2

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.ranking_schema --does-not-exist
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\red-body-no-hook.command.json` — exit 1

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -c D:\agent_project\cfaw-news\pyproject.toml --confcutdir D:\agent_project\cfaw-news D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\sentinel\test_body.py
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\red-body-with-hook.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -c D:\agent_project\cfaw-news\pyproject.toml --confcutdir D:\agent_project\cfaw-news D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\sentinel\test_body.py
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\red-fixed-pins.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.acceptance --run D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-20261028-003\prediction --run-pin 8b0d6a9d3dbc0441375d288af54e5ac842b33fd5cd8698a7e09ab34ca7b7d2b4 --evaluation D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-20261028-003\evaluation --evaluation-pin f8196587edf10349c8fa1565092410ea49b8367148e709e5d0701b76a1bc2204 --checks D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-20261028-003\checks --checks-pin c3ec5b5298187c3ee263e4e06c11a7b2b86fb6a7953ca40107d43d8856ff8949 --out D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\red-accepted
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\preflight\red-schema-ignored.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.ranking_contracts --does-not-exist
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\final\controller\checks.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.checks --out D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\final\controller\evaluate.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.evaluate --run D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\prediction --run-pin 36c1e7ffc8c74eb873adde00276b829261c99f643bbfb587c3d2821b91817fec --out D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\evaluation
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\final\controller\fixed-pin-probe.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.control_probe --run D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\prediction --run-pin 36c1e7ffc8c74eb873adde00276b829261c99f643bbfb587c3d2821b91817fec --evaluation D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\evaluation --evaluation-pin 0a5e7a752d7793c815cd54d3b514e02a6f87554b34449ec9ccfd6809fd1325f2 --checks D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks --checks-pin 44205edfdfc5da66ec525eb8e1a6186237d2548d90dc41cf11b6c78bfab47d74 --out D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\probe
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\final\controller\reproduce.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.reproduce --manifest D:\agent_project\cfaw-news\evals\intelligence_g3\manifests\pr5_campaign.json --manifest-sha256 56f2244812449db5ddb5a8bd2384cb302a3f9d66fb1205be167e9308da530daf --out D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\prediction
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\final\controller\scope-audit.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -c "import runpy; runpy.run_path('D:\\agent_project\\cfaw-news\\.tmp\\evals\\g3\\pr5-review-fix-20261029-001\\final\\audit_scope.py',run_name='__main__')"
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\final\controller\staged-empty.command.json` — exit 0

```text
git diff --cached --exit-code
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\final\prediction\worker-1.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.reproduce --manifest D:\agent_project\cfaw-news\evals\intelligence_g3\manifests\pr5_campaign.json --manifest-sha256 56f2244812449db5ddb5a8bd2384cb302a3f9d66fb1205be167e9308da530daf --out D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\prediction --worker-seed 1
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\final\prediction\worker-719.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.reproduce --manifest D:\agent_project\cfaw-news\evals\intelligence_g3\manifests\pr5_campaign.json --manifest-sha256 56f2244812449db5ddb5a8bd2384cb302a3f9d66fb1205be167e9308da530daf --out D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\prediction --worker-seed 719
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\collect.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.pytest_runner --mode collect --inventory D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\node_inventory.json --control-record D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\collect.control.json
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\diff.command.json` — exit 0

```text
git diff --check
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\frontend.command.json` — exit 0

```text
npm.cmd --offline run build -- --outDir D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\frontend-dist
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\full.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.pytest_runner --mode full --junit D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\full.xml --basetemp D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks-pytest\full --control-record D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\full.control.json
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\g1-strict.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_v1.validate --manifest D:\agent_project\cfaw-news\evals\intelligence_v1\manifests\dataset_manifest.json --strict
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\g3.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.pytest_runner --mode g3 --junit D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\g3.xml --basetemp D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks-pytest\g3 --control-record D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\g3.control.json
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\inventory.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.junit_inventory --inventory D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\node_inventory.json
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\junit.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.junit_inventory --inventory D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\node_inventory.json --junit D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\full.xml
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\ruff.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m ruff check backend tests evals
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\schema-g3-0.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.contracts --check-schemas
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\schema-g3-1.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.ranking_schema --check-schemas
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\schema-g3-2.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.revisit_cli --check-schemas
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\schema-g3-3.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.budget_cli --check-schemas
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\schema-g3-4.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.pr5_contracts --check-schemas
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\seed.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B evals/run_baseline.py --output D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks\seed.json
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\final\probe\baseline.command.json` — exit 0

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.acceptance --run D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\prediction --run-pin 36c1e7ffc8c74eb873adde00276b829261c99f643bbfb587c3d2821b91817fec --evaluation D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\evaluation --evaluation-pin 0a5e7a752d7793c815cd54d3b514e02a6f87554b34449ec9ccfd6809fd1325f2 --checks D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks --checks-pin 44205edfdfc5da66ec525eb8e1a6186237d2548d90dc41cf11b6c78bfab47d74 --out D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\probe\baseline-acceptance
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\final\probe\fixed-pins-with-hook.command.json` — exit 1

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.acceptance --run D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\prediction --run-pin 36c1e7ffc8c74eb873adde00276b829261c99f643bbfb587c3d2821b91817fec --evaluation D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\evaluation --evaluation-pin 0a5e7a752d7793c815cd54d3b514e02a6f87554b34449ec9ccfd6809fd1325f2 --checks D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\checks --checks-pin 44205edfdfc5da66ec525eb8e1a6186237d2548d90dc41cf11b6c78bfab47d74 --out D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\probe\must-not-pass
```

`.tmp\evals\g3\pr5-review-fix-20261029-001\final\probe\runner-with-hook.command.json` — exit 1

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g3.pytest_runner --mode collect --inventory D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\probe\must-not-collect.json --control-record D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\probe\must-not-run.json
```

## 结果、失败案例、成本与限制

保留 B4：P1 和 B4 重要事件召回均 90/111，重复展示均 27/117，没有稳定改善证据；五项评分消融的本批召回相同，不能据此推断特征无价值。没有未合并文档对照臂，B2=B1，仅说明 G2 已合并事件池上的身份对照，不能把 G2 合并收益归给 G3。

失败案例 `D:\agent_project\cfaw-news\.tmp\evals\g3\pr5-review-fix-20261029-001\final\evaluation\failures.jsonl` 共 528 条，保留重要遗漏与重复展示、事件家族、reference、protected、原因和是否计入分母；可评估 budget_unmet 不剔除。贪心分配不保证所有可放下的重要事件均被展示。

528 条包括 B2 控制臂在内全部 858 个组合的 231 条重要遗漏和 297 条重复展示，字节与旧失败工件一致。例如 crowded14--180--p1 的 delta 重要事件需要 34 秒，但当时 Focus/Radar 分别仅余 15/17 秒，遗漏仍计分母；repeat-ack-1d--180--p1 仍展示已确认重复的 atlas，作为重复失败保留。没有将这些不利结果改为成功。

以下为新工件生成的完整机器指标对应报告，包含预算、回访、消融、分子/分母、窗口支持、成本与不利结果。

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

## Revisit metric support

Revisit metrics count candidate-event states only inside their own window. Outside-window cases contribute zero samples and zero families. dataset_support separately records the whole cell; it is never substituted for metric support.

| Variant | Window | Recall n/d | Applicable samples | Applicable families | Undefined reason |
| --- | --- | --- | --- | --- | --- |
| b0 | 1d | 9/9 | 18 | 1 |  |
| b0 | 3d | 9/9 | 18 | 1 |  |
| b0 | 7d | 9/9 | 18 | 1 |  |
| b1 | 1d | 9/9 | 18 | 1 |  |
| b1 | 3d | 9/9 | 18 | 1 |  |
| b1 | 7d | 9/9 | 18 | 1 |  |
| b3 | 1d | 9/9 | 18 | 1 |  |
| b3 | 3d | 9/9 | 18 | 1 |  |
| b3 | 7d | 9/9 | 18 | 1 |  |
| b4 | 1d | 9/9 | 18 | 1 |  |
| b4 | 3d | 9/9 | 18 | 1 |  |
| b4 | 7d | 9/9 | 18 | 1 |  |
| no_duplicate | 1d | 9/9 | 18 | 1 |  |
| no_duplicate | 3d | 9/9 | 18 | 1 |  |
| no_duplicate | 7d | 9/9 | 18 | 1 |  |
| no_exploration | 1d | 9/9 | 18 | 1 |  |
| no_exploration | 3d | 9/9 | 18 | 1 |  |
| no_exploration | 7d | 9/9 | 18 | 1 |  |
| no_history | 1d | 9/9 | 18 | 1 |  |
| no_history | 3d | 9/9 | 18 | 1 |  |
| no_history | 7d | 9/9 | 18 | 1 |  |
| no_material | 1d | 9/9 | 18 | 1 |  |
| no_material | 3d | 9/9 | 18 | 1 |  |
| no_material | 7d | 9/9 | 18 | 1 |  |
| no_novelty_material | 1d | 9/9 | 18 | 1 |  |
| no_novelty_material | 3d | 9/9 | 18 | 1 |  |
| no_novelty_material | 7d | 9/9 | 18 | 1 |  |
| p1 | 1d | 9/9 | 18 | 1 |  |
| p1 | 3d | 9/9 | 18 | 1 |  |
| p1 | 7d | 9/9 | 18 | 1 |  |

## Interpretation and failures

B4 remains the baseline. P1 is not required to win; no independent stable improvement has been demonstrated. Per-job metrics, numerator/denominator, sample and family counts, data_source and undefined_reason are retained in metrics.json.

Failure records: 528, including every evaluable important miss and duplicate presentation. budget_unmet never removes an important event from a denominator. A protected item may fail to fit even when an alternative combination of minimum projections could fit; the registered greedy allocator does not solve a knapsack optimum.

nDCG@10 measures eligible rank order with all reference gains in IDCG; recall uses actual budget selection. Duplicate labels describe authored unchanged delivered events; opened does not establish knowledge. Domain coverage is lexical; exploration exposure is a feature proxy.

## Ablations and B2

no_history disables all history-dependent P1 score terms (novelty, material change, exploration, duplicate). no_material, no_novelty_material, no_exploration and no_duplicate zero their registered contributions without renormalization. Hard eligibility and mandatory update protection remain active in all variants. These are score ablations, not removal of safety/history validation. They use a separate experiment envelope, never a changed PR2/PR3 algorithm version.

B2 is reported separately in b2_g2_contribution. G2 already merged the event pool; B2 preserves identity and equals B1. G2 aggregation gain is undefined because there is no unmerged-document comparison arm. It is not credited to G3.

## Cost, reproducibility and limits

Actual prediction runs: 1716; semantic outputs per seed: 858; all cross-seed semantic hashes equal.

Measured prediction wall seconds (sum of per-job timers): 326.108445; mean 0.190040; max 1.727825. Process commands separately include startup, validation and serialization overhead.

External requests and model calls: 0, network guarded during prediction. Token count and provider cost are undefined (no model/provider invocation); no estimated billing or host electricity/hardware cost is asserted.

No confidence interval or significance claim: purposive reused nonblind families, no independent holdout. Reading time is a deterministic uncalibrated estimate. Material change uses attributed statement-set proxies. Source coverage gaps never confirm absence of updates.

The source release binds the exact working tree, anchor commit, tests, schemas, configs, frozen fixtures and pytest control plane. The approved root configuration and conftest hashes, pytest/pluggy code and bytecode, plugin discovery metadata, startup files and controlled environment are recorded. Autoload is disabled; unapproved config, hook, plugin or environment injection is rejected. Actual collect/G3/full execution records list loaded plugin origins. It does not claim these uncommitted changes are a published commit. Remote CI, Linux portability, live providers, DB/API/frontend integration and user research are not verified by this report.

G4 requires independent PR5 review and owner approval. Preserve the offline input/output contract and diagnostics before any separate integration design.


## Diff、历史保全与 G4 交接

与修复开工时 872 个公开文件逐字节比较：862 个保留、10 个限定范围文件变更，删除 0；旧 PR5 报告与 G1/G2、原有测试/fixtures/schema/manifests 均保留。新增文件为控制面实现、真实探针、schema CLI、新测试/增量清单和本报告。

修复范围的差异另以 initial 快照为基准保存，避免把既有未提交 PR3/PR4/PR5 误认为本轮改动。git diff --check 和 staged-empty 检查通过，root conftest 探针已移除，原始输出/历史工件未覆盖。

G4 检查清单见 `docs/G3_G4_HANDOFF.md`：独立复审本轮证据、所有者批准、保留 B4、显式历史状态写入、可信日志/身份升级与回滚、API/前端另案设计、阅读估时和真人效果另行验证。G4、真实提供方、真实用户效果、Linux/远程 CI 和生产部署均未验证。本轮到此停止。
