> 当前入口更新：本文件保留历史版本结果；当前 v6 的外部 pin、实际执行结果和人工阻断状态见 [PR5 人工准备与工程收尾](PR5_HUMAN_READINESS.md)。历史正文未作为本轮重跑结果。

> 状态更新（2026-10-22）：四项修复已通过“审查 G1”的独立复审，未发现剩余 P0/P1/P2。见 [PR5_REREVIEW.md](D:/agent_project/cfaw-news/evals/intelligence_v1/reports/PR5_REREVIEW.md)。下文保留修复当时记录，“待复审”事项现已闭环；人工与 G1-a 总验收仍未通过。

# G1-PR5 独立审查问题修复记录

日期：2026-10-22（Asia/Shanghai）。仅处理本次确认的两项 P1、两项 P2 和必要回归，未开展下一 PR。

**四项均已修复并通过本地验证；需要再次独立复审，尤其两项 P1 的门禁和仲裁路径。** 本记录不是独立复审通过结论。
当前技术门槛 PASS；真实人工标注门槛 BLOCKED；G1-a 总验收 NOT_MET，g1a_passed=false、g2_eligible=false。

## 复现与最小修复

先新增回归并运行：**11 failed、32 passed**。失败明确覆盖截断/伪计数 JUnit、正常 split/merge 仲裁正例、旧模板版本和 theme 首现类别。原完整 JUnit 没有漏测，错误在于旧验收逻辑允许不完整证据通过。原记录保留。

| 审查项 | 本次修复 | 证明 |
|---|---|---|
| P1 测试覆盖不完整仍 PASS | [verify_required_tests](D:/agent_project/cfaw-news/evals/intelligence_v1/acceptance.py:55)读取 Manifest 哈希绑定的 required_tests.json，核验完整/full 与 G1 两份 JUnit 的精确节点多重集、失败/error、未豁免 skip、T01–T24/T26 清单及测试源码 SHA；不再以旧测试数量和任意 test_pr5 为充分条件 | 缺节点、重复、逐节点 failure/error（即使 suite 计数为 0）、未豁免 skip、缺 Txx、陈旧源码清单均拒绝；完整证据接受。另有真实完整验收入口的截断副本复现，见下表 |
| P1 split/merge 仲裁无法形成 gold | [仲裁映射审计](D:/agent_project/cfaw-news/evals/intelligence_v1/annotations.py:247)区分 agreed 与 adjudicated：一致路径仍要求 matched；仲裁路径允许 split_merge_disagreement，要求明确最终成员、双方全部重叠原始组、每方对最终成员的完整覆盖、上下文/身份/冻结时间和精确仲裁引用 | split、merge 正例均通过完整 validator/audit；初标文件逐字节不变，原始 pair disagreement<1 和 unmatched targets 保留；未解决分歧、缺仲裁/缺原始组、错最终成员、过早仲裁、伪 matched 均阻断 |
| P2 四份模板使用旧手册 | DEV-02…05/annotation_template.json 同步 g1a-guide-v2，annotation_version 不变 | 逐一断言模板与 GUIDE_REVISION、ReviewSession 的手册/标注版本一致；原 CLI blank form 协议保持 |
| P2 theme 首现被标 no_change | [DEV-01 expectation 生成](D:/agent_project/cfaw-news/evals/intelligence_v1/build_pr5.py:237)按事件成员在回放步骤中的首次可见时点判 new；仅修正 d01:event:theme 的一条 authored expectation | 五轨迹首次可见事件均断言 new；生成器与实际记录一致。theme 仍 archive/grade 0，未改重要性、证据或强制排名 |

相关首轮修复测试为 43 passed；追加清单源指纹/Txx 负例后，验收模块为 13 passed。上述为有重叠的运行，不相加为独立样本。全部新增节点最终进入下面的全量回归。

仲裁正例只使用临时契约探针和明确的人工确认 test double。正式 labels/g1a_v1 的 annotations/adjudications/gold/event_alignments/support_reviews 仍为空，ReviewSession 仍 not_started；没有伪造真实双人标注或改写真实金标。

## 截断证据的完整验收复现

在隔离副本中删除当前 328 项 G1 中的 326 项，只保留 125 项旧测试与 2 项 PR5 测试；同时更新全部工件 SHA。其他条件使用本轮同一真实矩阵、Manifest、源码指纹与完整 G1 JUnit。该副本明确标记为 adversarial，不作为真实执行记录。

| 证据 | technical | temporal | regression | CLI 退出码 |
|---|---|---|---|---:|
| 完整 full 453 节点 / G1 328 节点 | PASS | PASS | PASS | 1（人工缺失，总验收未通过） |
| full 仅 127 节点，工件 SHA 已更新 | BLOCKED | BLOCKED | BLOCKED | 1（REQUIRED_TESTS_INCOMPLETE） |

后者 matrix_verified=true、checks_verified=false，说明拒绝来自测试覆盖门禁。证明及完整参数：[truncated-evidence-negative/proof.json](D:/agent_project/cfaw-news/.local/evals/g1/pr5/review-fix/truncated-evidence-negative/proof.json)。

必需节点来自实际 pytest collection，而非待验证 JUnit：保留原有 431 个节点，新增 22 个，合计 453（旧工程 125 + G1 328）。清单包含测试源码哈希和 Txx 映射，随新 Manifest 冻结。唯一 skip 豁免精确绑定 Windows、特定 symlink 节点和原因 1314；其他 skip 不授予 PASS。豁免项仍按 skip 单列，不算通过。

## 冻结身份和数据变更范围

- Git HEAD 保持 `e1ce349895b06dc57b40b5c5e1f75b50caf411ec`，本次交付未提交。
- 当前 `pr5-five-trajectories-v4` / `g1-pr5-2`，冻结时间 `2026-10-21T14:32:35.863200+00:00`。
- 外部 Manifest SHA-256：`be53d6ee40c274846bbc3867b332f77b456504e8ef39f298cb8e2a0b833ccd85`；受控文件 175 个。
- required_tests.json SHA-256：`d15896a94ee5c93340a26d2cf8883f04e504ca8a7cd3c5c193581a6d10a83cee`。
- 96 个源码/测试/锁文件等的 canonical 指纹映射 SHA-256：`e11cc10ec84763bd638c5ce2d0ea72451e2412a7b1e09bdb7e565b62957e7093`。
- 修复前完整包和测试在 `.local/evals/g1/pr5/review-fix/start/`；v4 冻结包/测试在 `frozen-v4/`。旧 v3 的 pin、运行时、测试与真实完整 JUnit 保留，不能使用旧 pin 搭配新代码。
- 唯一 authored expectation 改动为 DEV-01/D8/theme：no_change→new；tier=archive、graded_relevance=0 及其余字段保留。真实 gold、原始初标/仲裁、文档版本、Persona、事件材料及旧业务契约未改。
- 5 条合成主轨迹仍为 26 步/35 版本/47 事件观察目标；辅助集单列。全部 200 次运行的 600 个预测/输入/配置文件与修复前 v3 逐字节相同；这不意味着一处合成参考修正后的指标也必须相同。

## 实际验证命令与结果

工作目录 D:\agent_project\cfaw-news；既有 .venv，无新依赖。完整 argv/cwd/退出码及日志/JUnit SHA 见 [checks.json](D:/agent_project/cfaw-news/.local/evals/g1/pr5/review-fix/checks/checks.json)。

| 命令 | 结果 |
|---|---|
| python -B -m ruff check backend tests evals | PASS，exit 0 |
| python -B -m evals.intelligence_v1.contracts --check-schemas | PASS，exit 0 |
| python -B -m evals.intelligence_v1.validate --manifest … --strict | PASS，exit 0 |
| python -B -m pip check | PASS，exit 0；未安装依赖 |
| python -B -m pytest tests/evals -q | **327 passed、1 skipped**；exit 0 |
| python -B -m pytest -q -o faulthandler_timeout=30 | **452 passed、1 skipped、1 warning**；旧工程 125 项全部通过，exit 0 |
| python -B evals/run_baseline.py --output … | PASS，exit 0；旧 smoke Recall@8=1、MRR=0.8333333333333334、nDCG=0.8645724197652078 |
| frontend: npm.cmd --offline run build | PASS，exit 0 |
| git diff --check | PASS，exit 0 |

唯一 skip：test_symlink_outside_bundle_rejected_if_supported，Windows 权限 1314。唯一 warning：既有 Starlette/httpx TestClient 弃用提示。完整回归使用获准的本机临时测试 socketpair 环境，解决默认沙箱的既有卡住问题；未更改断言或联网。

完整路径参数和新输出目录如下；复跑须替换输出与 basetemp 目录：

```powershell
$PY = '.\.venv\Scripts\python.exe'
$G1 = 'evals/intelligence_v1'
$OUT = '.local/evals/g1/pr5/review-fix'
$PIN = 'be53d6ee40c274846bbc3867b332f77b456504e8ef39f298cb8e2a0b833ccd85'
& $PY -B -m pytest tests/evals -q --basetemp=.tmp/pr5-review-final-evals --junitxml="$OUT/checks/pytest-evals.xml"
& $PY -B -m pytest -q --basetemp=.tmp/pr5-review-final-full -o faulthandler_timeout=30 --junitxml="$OUT/checks/pytest-full.xml"
& $PY -B -m evals.intelligence_v1.reproduce --manifest "$G1/manifests/dataset_manifest.json" --manifest-sha256 $PIN --out "$OUT/matrix" --workers 4 --packets
& $PY -B -m evals.intelligence_v1.acceptance --manifest "$G1/manifests/dataset_manifest.json" --manifest-sha256 $PIN --runs "$OUT/matrix/primary" --checks "$OUT/checks/checks.json" --out "$OUT/acceptance"
```

实际收集命令为 `python -B .local/evals/g1/pr5/review-fix/collect_required.py`，内部仅执行 pytest --collect-only 并按 JUnit 地址规则序列化节点。[collection.txt](D:/agent_project/cfaw-news/.local/evals/g1/pr5/review-fix/collection.txt) 保存收集输出；[required_tests.json](D:/agent_project/cfaw-news/evals/intelligence_v1/manifests/required_tests.json) 是冻结的受信任输入。

本轮重跑 200 次预测、400 次评测、655 次 CLI，全部 exit 0；两 hash seeds 的 1,400 个确定性工件对应相同。主集 40 个算法/预算/半衰期/标签 cohort，各完整覆盖 26 步，每步两次重复；辅助集未混入。B3 的 3/14 天开发敏感性包含在内。全部 T01–T24/T26 技术节点通过；T25=N/A。正式人工指标仍 null，不以合成结果证明真实效果。

| 工件 | SHA-256 |
|---|---|
| [red.xml](D:/agent_project/cfaw-news/.local/evals/g1/pr5/review-fix/red.xml) | `6f9150300531a441af9f50e44e460b340bdcb4ed428d15dcc0e762d28c989950` |
| [pytest-evals.xml](D:/agent_project/cfaw-news/.local/evals/g1/pr5/review-fix/checks/pytest-evals.xml) | `5d126aa977eb8fa793bf13715ee3072d7876b1641d1bcd286ac8208467e25cfd` |
| [pytest-full.xml](D:/agent_project/cfaw-news/.local/evals/g1/pr5/review-fix/checks/pytest-full.xml) | `a3f74887ca50b31b5f6d3ce0516d2aece57eaf8cd8468dd906ad500487d1d2df` |
| [checks.json](D:/agent_project/cfaw-news/.local/evals/g1/pr5/review-fix/checks/checks.json) | `f0b0650f8a57422849154f78b23caffab90b8c6a188d5e3be4718819b787d44d` |
| [reproduction.json](D:/agent_project/cfaw-news/.local/evals/g1/pr5/review-fix/matrix/reproduction.json) | `d75f3be9bf4d6ca8f9ac9af8a41b2ec52f2b70b9dccfb9bbf90a37c1f92bb0b0` |
| [acceptance.json](D:/agent_project/cfaw-news/.local/evals/g1/pr5/review-fix/acceptance/acceptance.json) | `8f4e699cd4f964bab34ee390845c2edaf97fa73404113e460765971f9b32fcce` |

逐步分母/null/错误个案：[矩阵逐步报告](D:/agent_project/cfaw-news/.local/evals/g1/pr5/review-fix/matrix/summary/report.md)；完整节点与负例核对：[verified-evidence.json](D:/agent_project/cfaw-news/.local/evals/g1/pr5/review-fix/checks/verified-evidence.json)、[Txx 节点清单](D:/agent_project/cfaw-news/.local/evals/g1/pr5/review-fix/checks/t-matrix.json)。

## 仍未完成与复审要求

- 本轮最终软件测试无失败。Windows 原生 symlink 权限测试仍为上述明确豁免的 skip，未算通过；T25 未发生生产迁移，N/A。
- 两名真实独立标注者、真人试标、正式初标与仲裁仍未落实；human_annotation_gate=BLOCKED，G1-a NOT_MET，不能进入 G2。仲裁机制的临时正例不替代真人结果。
- 本轮两项 P1 和两项 P2 需要重新独立复审；建议核验真实截断 JUnit 拒绝路径、split/merge 完整溯源/原始统计、四模板与唯一 expectation 差异。尚未声称独立复审通过。
- 未扩展业务、训练或下一 PR；未联网采集、安装依赖、访问/迁移生产数据库；未 stage/commit/push。完成本轮修复后停止。
