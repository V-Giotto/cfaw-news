# G1-PR2 独立审查修复记录

日期：2026-10-20（Asia/Shanghai）。**R1/R2/R3 均已复现并修复，自测通过；需要独立复审。**
本次仍只做 PR2 数据准备，没有 PR3 排序/基线/指标、联网或真实模型调用。

## 冻结与保全

- HEAD 仍为 `43cebab0e4e291452ec4356848017d90ae9f7128`。原 PR1/PR2 为已有未提交工作，先保存 159 个文件指纹与完整副本后修复；没有 commit/push 或暂存操作。
- 原 v2 完整包：`.local/g1-pr2/review-fixes-v3/frozen-pr2-dev01-v2/`；Manifest SHA `f949daaaec802e75a0d53e2a878536f38008d361b8fdcc3d18f9fd945f8ed0e2`，所有受控文件校验匹配。
- 当前 revision：`pr2-dev01-v3`，Schema 仍为 `g1-pr2-1`。外部固定 Manifest SHA：`703662593c047a50675b2ea4d2b19d941df6233448f62fb32edf2552241229e7`。
- 所有 **22 个 JSONL**（含 Gold、空人工文件、版本/Claim/事件关系）均与 v2 逐字节一致；没有通过改金标解决失败。
- 新增 replay.py、test_pr2_review_fixes.py 和本报告；修改 validate.py、README、DATA_DICTIONARY、DATA_CARD、Manifest；历史 PR2_ACCEPTANCE 增加 v2 说明和当前入口指引。
- 58 个受控输入与 12 个测试源码的指纹保存在本地 frozen-inputs.json，完整测试在冻结后运行。

## 每项确认与修复

| 问题 | 复现 | 修复及验证 | 状态 |
|---|---|---|---|
| R1 初标内同对矛盾关系 | 相同 evidence_at 的 a→b syndicated / b→a unrelated 被接受 | 每份 initial_label 单独按无序文档对＋evidence_at 去重，报 DUPLICATE_ID、field=document_relations；反向同标签和正向冲突也拒绝；不同时间或不同提交仍合法。验证前后原始文件字节相同 | 已修复 |
| R2 无法保存 unresolved | 同步改 Gold 和 final_label 为 unresolved，返回 REFERENCE_NOT_FOUND | 接受 adjudicated/unresolved，仍要求原始提交、时间及存储 Gold 完全匹配；unresolved 增加 unresolved_adjudication 到 pending，不视为完成；Gold 不匹配仍拒绝 | 已修复 |
| R3 缺少可检出复现入口 | python -m ...replay --help 报模块不存在 | 仓库源码新增最小 replay 模块，仅 PR2 dry-run 导出；强制外部 pin、全量验证、单步/全步准备；不依赖 .local 脚本，不支持 --algo，不生成预测、指标或人的结果 | 已修复 |

原始记录校验只读，不删除冲突、不替人裁决。测试中 A/B/C 都是临时 contract-probe，
不是人类标注；仓库 labels 三个文件仍为空。两个不同 ID 仍不构成独立双人证明。
未决仲裁可结构合法（ok=true），但明确留在 pending；合法性不等于标注完成。

## 真实测试结果

- 先写 13 项回归：**10 failed / 3 passed**。三种 R1 反例、R2 unresolved、R3 缺模块均真实失败；合法对照通过。日志 pytest-red.txt、pytest-red.xml。
- 最小修复后：13 passed；增加 CLI 隔离检查后 **14 passed**，日志 pytest-related.txt、pytest-related.xml。
- 最终 v3 冻结后全量：**276 passed / 1 skipped / 1 warning，72.82s**。共 277 项：125 旧测试 + 152 G1 测试；0 failures/errors。
- JUnit SHA-256：`939432c6d2b5646afac192ed2ab8138679b106779624499f8a6772c7db5939a5`。日志与 XML：`.local/g1-pr2/review-fixes-v3/pytest-frozen.*`。
- Ruff、pip check、旧 seed-sanity-v1、前端 offline build、17 份 Schema 一致性、strict Manifest：全部通过。Seed 只是旧烟测，不是算法增益。
- CLI 的正反例覆盖：外部 pin 错误、文件篡改均在创建输出前失败；既有输出不覆盖；--algo 拒绝；D0 导出无未来包；两次全步导出全部字节一致。
- CLI 审计钩子实际阻止网络、敏感/库文件读取、输出外写入，并检查没有 cfaw_news 业务模块导入；该用例通过。
- 实际从项目根目录使用最终固定 pin 导出 export-a/export-b，各 14 个文件全部逐字节相同；单步 export-d0 与旧 D0 包原字节相同，尚未分发给任何人。

唯一 skip 是既有 Windows 原生 symlink 创建权限；resolved-path escape 防线通过。
唯一 warning 是既有 Starlette/httpx 弃用提示。全量回归在允许本地 socket 初始化的环境运行，
避免已知受限环境 socketpair 卡住；没有修改旧业务断言或安装新依赖。

## 验证命令

项目根目录：D:/agent_project/cfaw-news。

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/evals/test_pr2_review_fixes.py -q --basetemp=.tmp/g1-pr2-review-related --junitxml=.local/g1-pr2/review-fixes-v3/pytest-related.xml
.\.venv\Scripts\python.exe -B -m pytest -q --basetemp=.tmp/g1-pr2-review-frozen-full -o faulthandler_timeout=30 --junitxml=.local/g1-pr2/review-fixes-v3/pytest-frozen.xml
.\.venv\Scripts\python.exe -m ruff check backend tests evals
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -B evals/run_baseline.py --output .local/g1-pr2/review-fixes-v3/seed-sanity.json
.\.venv\Scripts\python.exe -B -m evals.intelligence_v1.contracts --check-schemas
.\.venv\Scripts\python.exe -B -m evals.intelligence_v1.validate --manifest evals/intelligence_v1/manifests/dataset_manifest.json --strict
# frontend 工作目录
npm.cmd --offline run build
```

## 从仓库源码直接复现 PR2 准备

该 pin 来自冻结验收记录，不是在运行前从待校验文件临时算出的“可信值”。
输出目录必须全新；重复运行请用另一目录，不要覆盖既有工作。

```powershell
$PIN = '703662593c047a50675b2ea4d2b19d941df6233448f62fb32edf2552241229e7'
.\.venv\Scripts\python.exe -B -m evals.intelligence_v1.replay --help
.\.venv\Scripts\python.exe -B -m evals.intelligence_v1.replay --manifest evals/intelligence_v1/manifests/dataset_manifest.json --manifest-sha256 $PIN --timeline DEV-01 --dry-run --out .local/g1-pr2/review-fixes-v3/export-a
.\.venv\Scripts\python.exe -B -m evals.intelligence_v1.replay --manifest evals/intelligence_v1/manifests/dataset_manifest.json --manifest-sha256 $PIN --timeline DEV-01 --dry-run --out .local/g1-pr2/review-fixes-v3/export-b
.\.venv\Scripts\python.exe -B -m evals.intelligence_v1.replay --manifest evals/intelligence_v1/manifests/dataset_manifest.json --manifest-sha256 $PIN --timeline DEV-01 --dry-run --step D0 --out .local/g1-pr2/review-fixes-v3/export-d0
```

全步目录的 visible_steps.jsonl / run_metadata.json 是管理员资料；只向真实标注者提供其当前
packets/<step>/packet.json、blank_form.json 与手册。全量校验会读取完整参考材料，
但这些参考答案不进入单步包；导出不是分发，不算独立标注。没有 ranker、预测文件或指标。
磁盘 I/O 错误可能留下未完成的新目录，程序报错且不声明成功；不会覆盖旧目录或修复输入。

## 剩余项与复审

- 三项报告的问题没有剩余失败或执行阻断。跳过项/警告如上，均未标为通过。
- A/B 到位、真实初标、分歧/仲裁和语义支持测量仍待人确认，未新增人的结果；T25=N/A。
- **需要独立复审**：重点重跑 R1 无序对唯一性、R2 两种仲裁状态和 pending、R3 从仓库新入口的外部 pin/隔离/单步导出；本轮自测不替代独立复审通过。
- 未触碰业务数据库、未联网抓取、未调用在线 LLM、未自动 commit/push；完成后停止，未开展下一 PR。
