# G1-PR4 报告比较 P1 修复

日期：2026-10-21。状态：本 P1 已修复并通过自测，等待重新独立审查。
HEAD 保持 `9cd5522cb6212d11e905bef4c2a38435b823b5ac`；本轮从已有 PR4 未提交工作区开始。

## 问题与复现

独立审查确认的唯一 P1：报告允许对不同回放步骤的宏平均作差。
使用合法的原 v1 回放/评估产物复现：B1 / REVISIT-7D D3 / 180 秒的
DuplicateExposureRate 为 0.5；B3 / D8 / 180 秒为 0。原入口成功输出
`delta_vs_B1=-0.5`。时间、候选和分母均不相同，因此不能归因于算法。

先增加回归测试，得到 **7 failed、8 passed**：B3/B4 的不同单步骤、比较方缺失步骤、
B1 缺失步骤，以及同一预算覆写下的实际步骤预算不一致，均因未抛错而失败。
候选/上下文哈希负例及合法比较正例通过。原始红灯 JUnit 未被覆盖。

## 最小修复

`report.py` 在 B3/B4 与 B1 生成差值前，要求双方逐步骤输入签名完全相等：

- 键为 `(timeline_id, step_id)`，精确匹配步骤集合；不取交集后静默比较。
- 值包含实际 `budget_seconds`、`candidate_sha256`、`context_sha256`。
  上下文哈希包含完整 Persona 版本/偏好、历史输入及时间窗口。
- 不一致抛出 `COMPARISON_INPUT_MISMATCH`，不创建报告输出目录。
  原有同一步骤候选/上下文不一致的 `CANDIDATE_POOL_MISMATCH` 防线保留。
- 相同步骤的局部回放可以正常比较；B3 的开发集半衰期敏感性仍与 7 天 B1 比较。

未修改排序、预算、指标公式、任何 JSONL/gold/合成期望、旧业务源码、依赖或 Schema。
原冻结清单绑定源码哈希，因此保留 v1，必要地更新清单为 **`pr4-revisit-v2`**。

当前外部 Manifest pin：
`f2782a4da6ff8e4e34e7fd348d534422219a688564dcfc3553a96f56ad2f46ab`。
旧 v1 pin `16b1e4ac765bed22abba9496d018220c03ddc08ae1547e64840cc22733dd41f4`
及其产物仍保留，不能用于新版运行时。

## 命令与结果

在项目根目录使用已有 `.venv`，未安装依赖。完整命令的输出证据保存在
忽略目录 `.local/evals/g1/pr4/report-p1-fix-01/`，矩阵在
`.local/evals/g1/pr4/report-p1-fix-matrix-01/`。未覆盖旧测试/矩阵产物。

```powershell
$PY = '.\.venv\Scripts\python.exe'
& $PY -B -m pytest tests/evals/test_pr4_evaluation.py -q --basetemp=.tmp/pr4-report-p1-red-01 --junitxml=.local/evals/g1/pr4/report-p1-fix-01/pytest-red.xml
& $PY -B -m pytest tests/evals/test_pr4_evaluation.py tests/evals/test_pr3_evaluation.py tests/evals/test_pr4_experiment_guardrails.py tests/evals/test_metrics_denominators.py -q --basetemp=.tmp/pr4-report-p1-related-01 --junitxml=.local/evals/g1/pr4/report-p1-fix-01/pytest-related.xml
& $PY -B -m pytest -q --basetemp=.tmp/pr4-report-p1-full-01 -o faulthandler_timeout=30 --junitxml=.local/evals/g1/pr4/report-p1-fix-01/pytest-full.xml
& $PY -B -m ruff check backend tests evals
& $PY -B -m evals.intelligence_v1.contracts --check-schemas
& $PY -B -m evals.intelligence_v1.validate --manifest evals/intelligence_v1/manifests/dataset_manifest.json --strict
& $PY -B evals/run_baseline.py --output .local/evals/g1/pr4/report-p1-fix-01/seed-sanity.json
& $PY -B -m pip check
git diff --check
# frontend 工作目录：
npm.cmd --offline run build
```

| 验证 | 本轮结果 |
|---|---|
| 修复前报告测试 | 7 failed、8 passed，预期红灯 |
| 修复后相关测试 | 27 passed |
| 全量 pytest | **399 passed、1 skipped、1 warning，268.90 秒；400 collected，0 failures/errors** |
| Ruff / Schema / 严格 Manifest / pip check | PASS |
| 旧种子基线 | PASS，Recall@8=1、MRR=0.8333333333333334、nDCG=0.8645724197652078 |
| 前端离线构建 | PASS，TypeScript/Vite |
| 新 pin 六算法矩阵及双 seed 复现 | **40 次预测、80 次评测、121 条 CLI 命令通过；确定性文件逐字节一致，候选/历史相同** |
| 与 v1 排名/指标/报告结论对照 | **120 个预测/输入/配置文件逐字节相同；160 个评测文件及比较报告仅 Manifest 身份字段不同，全部指标、分母、诊断、差值和原结论不变** |
| 最终源码、数据、范围与 Git 检查 | PASS；93 个输入/34 个测试源码与新冻结指纹匹配；JSONL 全部未变，索引为空 |

全量 JUnit SHA-256：
`f0de96c537fd24153d900b21e6a32727b5434daa96e85631f0e63f50e89ef4d7`。
唯一 skip 是 Windows 创建符号链接权限不足（1314）；已有 resolved-path 越界检查通过。
唯一 warning 是 Starlette/httpx 弃用提示，没有安装或替换依赖。

矩阵复现入口（此本地脚本只编排公开的 replay/evaluate/report CLI）：

```powershell
& $PY -B .local/evals/g1/pr4/reproduce.py --pin f2782a4da6ff8e4e34e7fd348d534422219a688564dcfc3553a96f56ad2f46ab --batch report-p1-fix-matrix-01
& $PY -B .local/evals/g1/pr4/report-p1-fix-01/verify_final.py
```

全量测试在支持本机测试 socket 的环境运行，保留原业务断言。
旧归档直接在 `.local` 下运行被路径门禁拒绝，拷贝到测试目录后被源码绑定门禁
`RUNTIME_CODE_MISMATCH` 拒绝；未放宽门禁或改写旧产物，改以新版 pin 重新回放。

## 剩余项与停止状态

无尚未通过的业务断言或未解决阻断；上述符号链接 skip 单列，不称已测通过。
独立审查应重新检查本 P1、两类步骤集合负例和合法矩阵；本轮自测不代替独立复审。
真人标注、语义支持、五条完整开发轨迹和 G1-a 仍未完成。
不扩展 PR4 功能、不进入 PR5，不迁移数据库、不安装依赖、不 commit/push。
本轮只修改报告入口、必需回归测试、清单和验收记录；既有工作区改动均保留。
修复完成后停止。
