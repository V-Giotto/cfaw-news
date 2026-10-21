# G1-PR3 split 隔离复审修复

日期：2026-10-21（Asia/Shanghai）。本次仅修复独立审查的一个 P1：预测入口缺少完整 split 元数据约束。
未收到额外 P0；未开展下一 PR。**状态：P1 已修复，冻结包重新验收通过；需要重新独立审查。**

## 修复与复现

- 审查结论属实。修复前，独立 test family 的同 SHA 副本以及复用同一 persona_id 的轨迹，
  均通过 load_bundle → load_step → B1.rank，生成 1 个排名；完整验证器拒绝。
- 先新增测试，首次实跑 **9 failed / 4 passed**：SHA、URL、文档 family 变化、跨 family 上游
  （跨 split 和同 split）、Persona 与其历史版本、缺失/未来上游；原有 timeline/scope 拒绝和合法 holdout 通过。
  family 用例当时在 load_step 被其他版本链错误拦下，尚未在 load_bundle 正确执行 family 契约。
- 新增 `split_metadata.py::split_metadata_issues`，由 loader 和完整验证器共用。
  文档 family 不变、非空 URL/SHA 不跨 split；上游存在、同 family、至少一个版本不晚于子文档；
  family scope 匹配 step split；timeline 和同 persona_id 的全部被引用历史版本不跨 split。
- loader 只传 DocumentIndex、Persona 身份/availability 和 ReplayStep；共用检查无 I/O、无正文/偏好、
  无参考事件/关系/Claim/Gold。只在准入侧使用全局身份元数据，不进入分词、语料统计或 ranker 上下文。
- 非法数据在 load_bundle 阶段失败，不能进入 load_step/排序；CLI 不创建输出目录。
  后补的两个删除参考文件的 CLI 拒绝回归，加上合法 train/test 的无参考文件排名对照，共新增 15 项测试。
- 不改聚合/排序算法、业务接口、Schema 或金标；已有未来正文 poison 和预测文件访问审计继续作为回归。

## 新 revision 与保全

- 起始 HEAD：`8778c029fcd318c79eada0a7bdd64e514e59a98f`；已有 PR3 工作区改动未提交。
- 修复前 `pr3-replay-v1` 完整包保存于 `.local/evals/g1/pr3-split-review/pr3-replay-v1/`，
  原 pin：`076f8f524f716d63cc4caa0bd739560a5f6e613ede8c5363ce42dd72a9f43049`。
- 当前冻结 revision：`pr3-replay-v2`；Schema 仍为 `g1-pr3-1`。
- **当前外部固定 Manifest SHA-256：`1a7eec301e355b03b388e2dafbd69e420df97f28459c36d10ba4c70b004d9ae3`。**
- 71 个受控输入，指纹见本地 `frozen-inputs.json`。全部 22 个既有 JSONL（含 gold/人工空文件）、
  21 份 Schema、评分配置/内核、其余业务源码和旧测试保持修复前字节；无数据库访问或迁移，T25=N/A。
- 本轮新增共用检查、15 项预测入口回归，并更新 loader、完整验证器、Manifest 与必要的版本/验收文档。
  用户在本轮开始前已改动的协作指南保持原字节。原 v1 验收仅加历史说明，旧结果没有改写成新验证。
- 无联网、模型调用、依赖安装、git add/commit/push；未进入 PR4/PR5。

## 验证命令与结果

项目根目录 `D:/agent_project/cfaw-news`，既有 `.venv`：

```powershell
$PY = '.\.venv\Scripts\python.exe'
$ROOT = 'evals/intelligence_v1'
$PIN = '1a7eec301e355b03b388e2dafbd69e420df97f28459c36d10ba4c70b004d9ae3'
& $PY -B -m pytest tests/evals/test_prediction_split_isolation.py -q --basetemp=.tmp/g1-pr3-split-red --junitxml=.local/evals/g1/pr3-split-review/pytest-red.xml
& $PY -B -m pytest tests/evals/test_prediction_split_isolation.py tests/evals/test_split_leakage.py tests/evals/test_loader.py tests/evals/test_prediction_isolation.py -q --basetemp=.tmp/g1-pr3-split-related --junitxml=.local/evals/g1/pr3-split-review/pytest-related.xml
& $PY -B -m pytest tests/evals -q --basetemp=.tmp/g1-pr3-split-frozen-evals --junitxml=.local/evals/g1/pr3-split-review/pytest-evals.xml
& $PY -B -m pytest -q --basetemp=.tmp/g1-pr3-split-frozen-full -o faulthandler_timeout=30 --junitxml=.local/evals/g1/pr3-split-review/pytest-full.xml
& $PY -m ruff check backend tests evals
& $PY -B -m evals.intelligence_v1.contracts --check-schemas
& $PY -B -m evals.intelligence_v1.validate --manifest "$ROOT/manifests/dataset_manifest.json" --strict
& $PY -m pip check
& $PY -B evals/run_baseline.py --output .local/evals/g1/pr3-split-review/seed-sanity.json
git diff --check
# frontend 工作目录：
npm.cmd --offline run build
```

首行是修复前的真实红灯命令，当时只含最初 13 项。相关 42 项在 v2 draft 上通过；后续全套基于上面的冻结 pin。
pytest 全量只用临时库、mock 与本地 TestClient socket 初始化，不读取真实工作库或访问公网。
复现命令由本地 `reproduce.py` 顺序执行并记录在 `reproduction.json`：四算法各两次 CLI 和事后 evaluate，
PYTHONHASHSEED 分别为 1、719，全部使用固定 pin 和新目录 `<algo>-a/b`、`<algo>-a/b-evaluation`。
重跑必须更换输出目录，不能覆盖本轮证据。

| 检查 | 结果 |
|---|---|
| 首次失败测试 | 9 failed / 4 passed，预期红灯 |
| 相关测试 | 42 passed |
| 冻结 G1 测试 | **205 passed / 1 skipped**，0 failures/errors |
| 冻结工程全量 | **330 passed / 1 skipped / 1 warning**，0 failures/errors |
| Ruff / Schema / strict Manifest / pip check | 通过，Schema 21 份，Manifest 无错误 |
| 旧 seed 烟测 | Recall@8=1、MRR@8=.8333333333333334、nDCG@8=.8645724197652078 |
| 前端离线构建 | TypeScript/Vite 通过 |
| 四算法双次复现 | 预测/输入/配置/指标/诊断字节一致；四算法候选快照相同 |
| v1 → v2 行为保全 | 四算法预测、输入、配置与 v1 逐字节一致；metadata/pin 按新 revision 更新 |

## 待复审与边界

需要重新独立审查共用检查、loader 接入、拒绝测试和新 pin；本轮自测不替代独立复审。
仍只有 synthetic 开发数据；没有新增真实 holdout，也不声称观察到历史实际污染或算法效果提升。
未声明的语义派生仍需人工审查；本修复覆盖既有显式身份/上游和 Persona ID 契约，不推断新 lineage。
PR2 人工初标、手册真人试用、独立复审及 G1-a 人工门槛继续待完成。

## 最终结果与证据

当前没有仍失败的测试或未解除的执行阻断。唯一 skip 为 Windows symlink 创建权限（1314），
resolved-path escape 检查通过；唯一 warning 为既有 Starlette/httpx 弃用提示，未安装依赖规避。
全量使用允许本地 socket 初始化的测试环境，一次完成；没有并行运行另一套 pytest。
结束 HEAD 与起始相同；所有受控输入和 26 个测试源码的冻结指纹在回归后重新匹配。
验收记录、命令、红灯及当前证据仅保存本地，不覆盖 v1 的运行产物。

| JUnit | SHA-256 |
|---|---|
| pytest-red.xml | `8cec80f4ffb0c90580b69798917c2d551bbd8482d819a7a10d859394f6fd6d03` |
| pytest-related.xml | `b94809b52539ddf0b534036ce173ff3c55c2b166e45427386fbe44e051b42b84` |
| pytest-evals.xml | `c7b98fa895f2853091a2e7dbcadc009867dc118bfe39d99f5a437b5177876d4a` |
| pytest-full.xml | `fa4b919176fb3f49be7e6e93acf18f70434ea4e951ed18fb5d2758f0e1653401` |

当前 pin 只适用于 v2；旧 pin 的包在本地完整保全，不能用 v1 的运行记录充当 v2 运行。
独立审查重点为 split_metadata.py、loader.py 的元数据投影/调用、validate.py 的共用替换、
test_prediction_split_isolation.py 和 Manifest 新源码条目。自测通过不等于复审已通过。
修复完成后停止；未自动提交或推送，也未开始下一 PR。
