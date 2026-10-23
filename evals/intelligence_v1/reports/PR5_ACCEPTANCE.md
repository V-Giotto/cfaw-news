> 已被新批次替代（2026-10-23）：本文为历史版本证据；默认流程已改为单 AI 开发，原真人待办不再是前置条件。当前批次、pin、实际验收和限制见 [PR5 AI 开发收尾](PR5_AI_DEVELOPMENT.md)。历史数据与结论未改判。

> 当前入口更新：本文件保留历史版本结果；当前 v6 的外部 pin、实际执行结果和人工阻断状态见 [PR5 人工准备与工程收尾](PR5_HUMAN_READINESS.md)。历史正文未作为本轮重跑结果。

> 当前入口更新（2026-10-22）：以下为 v3 历史结果，保留原记录。当前 v4 修复及验证见 [PR5_REVIEW_FIX.md](D:/agent_project/cfaw-news/evals/intelligence_v1/reports/PR5_REVIEW_FIX.md)。当前 Manifest SHA-256 为 `be53d6ee40c274846bbc3867b332f77b456504e8ef39f298cb8e2a0b833ccd85`；下文 v3 pin 只适用于保留的 v3 运行时。

# G1-PR5 技术交付与验收记录

本次完成五条合成开发轨迹、单步盲标包、标注溯源与一致性工具、全量基线复现和失败关闭的验收入口。
**技术门槛 PASS；人工门槛 BLOCKED；G1-a 总验收 NOT_MET；不得进入 G2。** 两名真实独立标注者均未落实，人工试标、初标、仲裁和真人语义支持审查均未完成。
本报告不是 PR5 独立复审结论。PR4 的独立复审已通过，并作为 PR5 技术进入证据。

## 冻结身份与进入条件

- 原始且当前 Git HEAD：`e1ce349895b06dc57b40b5c5e1f75b50caf411ec`；交付留在未提交工作区，未 stage/commit/push。
- 当前数据：`pr5-five-trajectories-v3` / `g1-pr5-2`；冻结时间 `2026-10-21T12:45:29.084934+00:00`。
- 外部记录的 Manifest SHA-256：`ea87551fd37bab2c70bf41b138c862119907bc986f9f56e9ac492758ce65fe30`。174 个受控文件与冻结存档逐字节匹配。
- 源码/测试/锁文件等 96 个文件的 canonical 指纹映射 SHA-256：`2e7eb52efd090f31f96991fb5dcf0d866276067617b4103be4fdb637566b9b65`。
- PR4 独立复审绑定 HEAD e1ce349、pr4-revisit-v2 pin f2782a4da6ff8e4e34e7fd348d534422219a688564dcfc3553a96f56ad2f46ab；原报告比较 P1 已闭环，复审未发现 P0/P1/P2。详见 [PR4 复审记录](D:/agent_project/cfaw-news/evals/intelligence_v1/reports/PR4_REREVIEW_GATE.md)。
- 已保存完整 PR4 包/测试；PR5 v1、v2、v3 包及各自测试源码也分别保存在 `.local/evals/g1/pr5/`，旧 pin 配旧运行时。
- 原有 32 个 JSONL 逐字节保留。旧 15 步在 420 秒下六算法共 90 条预测及输入/配置与 PR4 保存结果一致；最终全部 200 次运行的 600 个预测/输入/配置文件又与 PR5 v1 逐字节一致。此结论不包括修改后的评测指标。

## 数据与接口

| 主轨迹 | 回放时点 | 挑战 | 版本数 |
|---|---|---|---:|
| DEV-01 | D0/D1/D3/D4/D5/D8 | 发布、转载、限定独立测试、更正；原材料保留 | 7 |
| DEV-02 | D0/D1/D2/D3/D8 | 框架兼容性更正、旧版保存、同项目不同公告 | 7 |
| DEV-03 | D0/D1/D3/D4/D8 | 热度与实证分离、限定测试、无增量观察 | 7 |
| DEV-04 | D0/D3/D5/D6/D8 | 旧技术安全变化、未知覆盖、回访与曝光 | 7 |
| DEV-05 | D0/D1/D2/D3/D8 | 跨领域弱相关机会、Persona 改变、探索价值 | 7 |

主集为 5 个 dev 家族、26 步、35 份合成版本、47 个可见事件观察目标。辅助 SYN-PR1/REVISIT-7D 为 2 家族、9 步、11 版本，未混入主报告。整个包共 35 步/46 个合成版本；真实正文为 0。五家族、重复时点和反事实高度相关，不能作为独立用户或泛化样本。

新增 `annotations packet/audit/agreement`、`acceptance`、`reproduce` 离线 CLI。`annotations packet` 必须显式指定外部 pin、timeline、单步和新输出目录；导出 v2 packet、空表和元数据。52 个 A/B 导出仅用于管理员核对，未分发，也不是提交。

新增 ReviewSession/EventAlignment/SupportReview/AcceptanceResult 及 schema；FileEntry.annotation_version 仅为标签角色提供可选覆盖，旧 pending fixture 保持原版本。当前空人工文件使用 g1a-annotation-v1，手册为 g1a-guide-v2；协议版本不意味着标注完成。旧 v1 包与手册保留历史可复核性。

`RankerProtocol.rank(context,candidates)`、预测条目、预算规则、基线系数及旧 HTTP/Goal/Run/Decision/Schedule/生产数据库契约未改动。修改集中于离线评测、G1 测试及必要说明。

## 数据与审计修正的版本记录

V1 完成过一轮测试和矩阵，记录原样保留，未作为最终版本结果。内部检查随后发现 DEV-01/D3 release、DEV-04/D5 release/license 三条 authored no_change 参考与未知覆盖窗口重叠；V2 将其改为 insufficient，且未知变化不再进入重复/文本代理指标的负例分母。未改 grades/tiers、真人 gold、候选、排名或系数。

V2 测试与矩阵因新的历史引用负例而主动中断，其部分记录不能算通过。V3 修正“最新候选”和“已可见历史证据”的混淆：事件分组成员仍为当前候选；标注 claim/support 可引用同轨迹、available_at<=as_of 的旧版；gold 支持版本还须属于同一事件。未来/跨家族引用仍拒绝。手册升至 g1a-guide-v2，schema 升至 g1-pr5-2；无真人标签可回写或重标。

先失败记录包括初始 11 项、标注溯源 2 项、确认时序 1 项、未知分母 2 项，以及历史引用 1 项正例。均保存在本地 JUnit；最终历史引用正反例 3 passed，相关专项 27 passed，最终全量回归如下。构造探针始终只写临时副本，不进入正式人工文件。

## 实际命令与结果

环境：Windows-11-10.0.26200-SP0；Python 3.12.14；Node v24.21.0；使用既有 .venv，无依赖安装。

| 检查 | 实际结果 |
|---|---|
| tests/evals | 305 passed、1 skipped；754.29s |
| 全量 pytest | 430 passed、1 skipped、1 warning；569.67s；其中原有 125 项全部通过 |
| Ruff / schema / strict validate / pip check | 全部 exit 0 |
| 旧 seed sanity | exit 0；Recall@8=1，MRR=0.8333333333333334，nDCG=0.8645724197652078；仅 smoke |
| npm --offline run build / git diff --check | 全部 exit 0 |

唯一 skip：`tests.evals.test_provenance_and_rights::test_symlink_outside_bundle_rejected_if_supported`，Windows 创建符号链接权限不足（1314）。不计入通过；其他路径逃逸检查仍运行。唯一 warning 为既有 Starlette/httpx TestClient 弃用提示，未安装依赖以消除提示。

默认沙箱的本机 asyncio socketpair 已复现卡住，完整回归使用获准的本机临时测试套接字环境；未改变测试断言，未访问外网。tests/evals 使用默认沙箱。

```powershell
Set-Location D:\agent_project\cfaw-news
$PY = '.\.venv\Scripts\python.exe'
$PIN = 'ea87551fd37bab2c70bf41b138c862119907bc986f9f56e9ac492758ce65fe30'
$G1 = 'evals/intelligence_v1'
$OUT = '.local/evals/g1/pr5'
& $PY -B -m ruff check backend tests evals
& $PY -B -m evals.intelligence_v1.contracts --check-schemas
& $PY -B -m evals.intelligence_v1.validate --manifest "$G1/manifests/dataset_manifest.json" --strict
& $PY -B -m pip check
& $PY -B -m pytest tests/evals -q --basetemp=.tmp/pr5-v3-evals --junitxml="$OUT/v3-checks/pytest-evals.xml"
& $PY -B -m pytest -q --basetemp=.tmp/pr5-v3-full-local-sockets -o faulthandler_timeout=30 --junitxml="$OUT/v3-checks/pytest-full.xml"
& $PY -B evals/run_baseline.py --output "$OUT/v3-checks/seed-sanity.json"
Push-Location frontend
npm.cmd --offline run build
Pop-Location
git diff --check
& $PY -B -m evals.intelligence_v1.reproduce --manifest "$G1/manifests/dataset_manifest.json" --manifest-sha256 $PIN --out "$OUT/v3-matrix" --workers 4 --packets
& $PY -B -m evals.intelligence_v1.acceptance --manifest "$G1/manifests/dataset_manifest.json" --manifest-sha256 $PIN --runs "$OUT/v3-matrix/primary" --checks "$OUT/v3-checks/checks.json" --out "$OUT/v3-acceptance"
```

以上为已执行路径；复跑须换新的输出与 basetemp 目录。最后 acceptance 实际 exit 1，已保存 NOT_MET 报告，原因是人工门槛未满足。

| 工件 | SHA-256 |
|---|---|
| [checks.json](D:/agent_project/cfaw-news/.local/evals/g1/pr5/v3-checks/checks.json) | `f838556fd5051455cc8466a96407f6ee097320fc51dd4b5ae30550979415a8b5` |
| [pytest-evals.xml](D:/agent_project/cfaw-news/.local/evals/g1/pr5/v3-checks/pytest-evals.xml) | `6fd2d2ffa7cc6bac8a931b1073e5ed569cfe055b19064a3ebab7f648182d1f53` |
| [pytest-full.xml](D:/agent_project/cfaw-news/.local/evals/g1/pr5/v3-checks/pytest-full.xml) | `6bcb4e76cee405e31da1c7908748c72ea0dee95eeea054892808f3e766b5f379` |
| [reproduction.json](D:/agent_project/cfaw-news/.local/evals/g1/pr5/v3-matrix/reproduction.json) | `3ef912bbf6371853e503b7fb1e5895b86b5b9b16bc3a05e52787f57ff7851b83` |
| [comparison.json](D:/agent_project/cfaw-news/.local/evals/g1/pr5/v3-matrix/summary/comparison.json) | `984648f0479dbcacdbe721d53fcdb7764ba73cdc685c73b2643379882c608b5a` |
| [acceptance.json](D:/agent_project/cfaw-news/.local/evals/g1/pr5/v3-acceptance/acceptance.json) | `4a2a94986f583b0afe968f2125fbdb830575c4b83cb34a37a35a80351ccac6af` |

完整命令 argv/cwd/退出码、源指纹、日志/JUnit 的 SHA 在 checks.json；矩阵每次 CLI 的 seed、日志哈希和 1,400 个确定性工件哈希在 reproduction.json。

## 全量矩阵与指标边界

5 timelines × 6 algorithms × 3 budgets(180/420/900) × 2 hash seeds(1/719) 为 180 次预测；另有 B3 在 420 秒下 3/14 天半衰期的 20 次预测。每次分别评测 gold 与 synthetic-fixture：共 200 次预测、400 次评测、655 次 CLI，全部 exit 0。主报告 40 个配置/标签 cohort，每个恰含主集 26 步、每步两次重复；没有辅助 fixture。

两 seed 的 predictions/input/config/metrics/diagnostics 共 1,400 个哈希对应相同；时间和耗时放 metadata/performance，未计入确定性内容。输入签名校验同一步的候选、Persona、历史和预算，重复运行不扩充样本数。父进程 PYTHONHASHSEED 未修改，仅在子进程环境指定。

下面仅为合成参考、420 秒/7 天的 pooled numerator/denominator。Recall 有定义的 13 个状态和无 focus 分母的 13 个状态分开；它们不是 13 个独立事件或用户。

| 算法 | 重要事件 Recall | 重复曝光 | 重复 no_change |
|---|---|---|---|
| b0 | 13/13 | 57/104 | 39/54 |
| b1 | 13/13 | 57/104 | 39/54 |
| b2-predicted | 13/13 | 12/59 | 17/24 |
| b3 | 13/13 | 12/59 | 17/24 |
| b4 | 13/13 | 12/59 | 17/24 |
| b2-oracle | 13/13 | 0/47 | 11/15 |

重复 no_change 的有定义/无定义状态数为 15/11；未知变化已排除。完整 macro/micro、每家族、逐步分子分母/null 原因见 comparison.json。B4 的重要事件 Recall 相对 B1 为 0 增益；其重复曝光指标与 B2-predicted/B3 相同，不能归因于曝光策略或泛化效果。Oracle 单独命名，不作可部署成绩。

gold 模式中按人工标签决定的 Recall/nDCG/回访/变化代理等正式指标均未测量，eligible_label_count=0。两种模式保留的事件配对、重复曝光等结构诊断来自明确合成的 reference event catalog，不是新取得的人工 gold。正式 MaterialChange/Correction/Withdrawal 分类与算法输出 EvidenceSupportPrecision 仍为 null；算法未生成这些语义判定，文本增量不能冒充它们。

人工一致性配对数为 0；五个序数维度的 weighted κ、tier/change nominal κ、事件关系一致率均为 null 并注明原因。支持审查条数为 0、语义支持率 null；结构合法或引用段落存在不能授予真实独立标注或语义正确资格。

## 逐步错误个案与覆盖

以下均为 180 秒/7 天的合成诊断，不因事件命中而隐去证据遗漏：

| 个案 | 实际结果及解释 |
|---|---|
| B0，DEV-02/D8 | 事件 Recall=1/1，但更正版 d02:release:2 未呈现；另缺 discussion/repost，预算用满 180 秒 |
| B1，DEV-03/D8 | Recall=1/1，但缺 d03:release:2 与 d03:test:1；有事件命中不等于更正/独立证据覆盖 |
| B4，DEV-02/D8 和 DEV-04/D8 | Recall=1/1，各缺独立测试版本；各有 3 个 grouping FN pair、0 个 FP pair，预算 180 秒 |
| DEV-04/D5 | 官方来源 service_offline，432000 source-seconds 未知覆盖；相关参考为 insufficient，不能声称期间无变化 |

主报告的每一步均有 UTC、Persona、文档/来源/参考事件数、focus 分母、TopK/预算结果、来源窗口和漏报原因；D8 另列支持证据、重复与归并错误。详见 [全部逐步报告](D:/agent_project/cfaw-news/.local/evals/g1/pr5/v3-matrix/summary/report.md)。

## 时间、gold 与人工记录防线

普通预测只读取截止 as_of 的最新正文投影、当时 Persona、预算和过滤后的历史投递/曝光/覆盖。family/split/全局身份元数据只做准入；Claim、人工事件关系/编号、gold、初标、仲裁、理由和 synthetic expectations 在排名后才消费；只有显式 b2-oracle 读取参考分组。未来正文、Persona、反馈和事后总结不进入排名或盲标包。整包字节可为哈希而读取，不等于未来正文可参与计算。

标签门槛检查手册与单步包哈希、真实人工手动确认、原始提交冻结时间/哈希、包分发时序、文档成员对应、分歧/仲裁溯源、全步/全目标覆盖。不同局部 event ID 不按编号或位置硬配；split/merge/漏标暴露为分歧；一致性在仲裁前计算；未定义分母保留 null。真实身份仍须管理员人工核实，代码不能证明两个人确实独立。

另外实际拒绝：gold 改一字节且不自动修复、缺一个主集 step、缺一个矩阵 cohort、过期源码指纹。探针结果见 [核对与负例记录](D:/agent_project/cfaw-news/.local/evals/g1/pr5/v3-checks/verified-evidence.json)。未来引用和跨家族引用回归均通过；合法旧版+当前更正引用通过完整 validator 与 audit。

## T01–T26 与门槛

下表为本次 full JUnit 的实际节点映射；PASS 表示技术断言通过，不表示对应人工实证已完成。完整参数化节点见 [Txx 节点清单](D:/agent_project/cfaw-news/.local/evals/g1/pr5/v3-checks/t-matrix.json)。

| ID | 状态 | 节点数 | 一个实际节点 |
|---|---|---:|---|
| T01 | PASS | 1 | `test_T01_future_corpus_is_valid_but_not_a_candidate` |
| T02 | PASS | 1 | `test_T02_late_observation_and_inclusive_boundary` |
| T03 | PASS | 2 | `test_T05_T03_correction_is_append_only_and_old_paragraph_stays_exact` |
| T04 | PASS | 1 | `test_T04_repeat_observation_does_not_create_a_content_version` |
| T05 | PASS | 1 | `test_T05_T03_correction_is_append_only_and_old_paragraph_stays_exact` |
| T06 | PASS | 1 | `test_T06_T07_T15_visible_upstream_and_distinct_project_announcement` |
| T07 | PASS | 1 | `test_T06_T07_T15_visible_upstream_and_distinct_project_announcement` |
| T08 | PASS | 1 | `test_T08_T09_claim_history_separates_attribution_and_scoped_measurement` |
| T09 | PASS | 1 | `test_T08_T09_claim_history_separates_attribution_and_scoped_measurement` |
| T10 | PASS | 1 | `test_T10_empty_candidates_and_unknown_coverage_are_legal` |
| T11 | PASS | 6 | `test_T11_T12_explicit_history_signal_penalties_and_no_knowledge_inference[kinds0-0.1]` |
| T12 | PASS | 6 | `test_T11_T12_explicit_history_signal_penalties_and_no_knowledge_inference[kinds0-0.1]` |
| T13 | PASS | 1 | `test_T13_new_visible_text_clears_penalty_without_claiming_correction` |
| T14 | PASS | 1 | `test_T14_candidates_are_not_filtered_to_last_24_hours` |
| T15 | PASS | 2 | `test_T06_T07_T15_visible_upstream_and_distinct_project_announcement` |
| T16 | PASS | 1 | `test_T16_missing_paragraph_is_rejected_and_T17_location_is_not_support` |
| T17 | PASS | 4 | `test_T16_missing_paragraph_is_rejected_and_T17_location_is_not_support` |
| T18 | PASS | 7 | `test_T18_ranker_is_invariant_to_input_order_and_fixed_id_ties[b0]` |
| T19 | PASS | 2 | `test_T19_persona_changes_only_context_not_the_visible_technical_evidence` |
| T20 | PASS | 1 | `test_T20_future_feedback_rejected_without_mutating_knowledge` |
| T21 | PASS | 2 | `test_T21_gap_is_explicit_and_does_not_mean_no_world_change` |
| T22 | PASS | 1 | `test_T22_one_byte_gold_tamper_stops_before_parsing_and_does_not_repair` |
| T23 | PASS | 25 | `test_T23_prediction_and_full_validation_reject_split_leakage[sha]` |
| T24 | PASS | 6 | `test_T24_cli_canonical_bytes_across_processes_and_hash_seeds[b0]` |
| T25 | N/A | 0 | `无生产迁移` |
| T26 | PASS | 15 | `test_T26_synthetic_not_counted_as_real_news` |

T17 只证明定位与语义支持的分离及审查溯源机制，真人语义支持结果未测量。符号链接权限 skip 另列，未计为 PASS。

| 门槛 | 实际状态 |
|---|---|
| baselines | PASS |
| contracts | PASS |
| dataset | PASS |
| human_annotation | BLOCKED |
| limitations | PASS |
| metrics | PASS |
| migration | N/A |
| prior_review | PASS |
| provenance | PASS |
| regression | PASS |
| reproduction | PASS |
| temporal | PASS |

## 剩余工作、风险与停止条件

1. 未来/gold 泄漏：发现未来正文、反馈或答案进入普通排名/单步包即停止正式评测；修复后新 revision/pin 全量重跑。
2. 人工资格与覆盖：没有两名真实独立标注者，或缺初标冻结/仲裁/手册版本，则人工与总门槛保持未通过。后续顺序为 DEV-01 真人试标→修订并冻结新规范/annotation_version→五轨迹独立初标→冻结原始提交→一致性/分歧→仲裁→冻结 gold。不能用模型、两个 ID 或合同探针填补。
3. 分母与归因：不得混入辅助集、将重复运行当新增样本、跨步骤/预算作差、把 unknown 当负例，或用事件 Recall 掩盖支持证据遗漏。五家族合成开发集不支持真实用户或线上覆盖主张。

PR2 人工试标、手册真人可用性和 PR5 五轨迹真人闭环仍未完成。技术工具和空白材料可以交付，PR5 完整 DoD 与 G1-a 未达到。发现 P0/P1、需要扩大业务修改或安装依赖时停止对应工作；本轮未进入 G2、未做训练/大 UI/生产数据库迁移。

依赖锁文件保持：

- `requirements.lock` SHA-256：`fb14c8af21a7af52f25e31044ad6b0101f7acfb794f6a5c8ec668d45b3f4d72d`。
- `frontend/package-lock.json` SHA-256：`b867e6c2da39e9c56d9cdaeb5b7456bed8751d4355672269a459ac7c515d961f`。
- `audit/G0_BASELINE.json` SHA-256：`8c96b980bcd87b057404807dfbb4bfe1229884d0c19b52fd19ab8f6950951e75`。

本轮未联网采集、未调用实时预测提供方、未安装依赖、未访问/迁移生产数据库、未 stage/commit/push。开发日记未纳入 Git。停止在本 PR 技术交付与明确未通过的人工/总验收状态。
