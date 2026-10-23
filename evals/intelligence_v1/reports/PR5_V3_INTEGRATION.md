> 已被新批次替代（2026-10-23）：本文为历史版本证据；默认流程已改为单 AI 开发，原真人待办不再是前置条件。当前批次、pin、实际验收和限制见 [PR5 AI 开发收尾](PR5_AI_DEVELOPMENT.md)。历史数据与结论未改判。

# G1-PR5：V3 输入接入、原稿保留与最终技术复核

2026-10-23，Asia/Shanghai。**技术门槛 PASS；人工门槛 BLOCKED；G1-a=NOT_MET，不能进入 G2。**
已收到两名真人的材料和共同复核，不再将现状表述为“没有第二人”或“DEV-02～05 未提交”。共同复核不能补造历史独立初标过程。

当前冻结：`pr5-five-trajectories-v8-r1 / g1-pr5-4`。

Manifest SHA-256：`ad9a58f84c25de4d60b716afb2d008739257d60d8ed68a7235cc5c72ccf6cbe4`。

Git HEAD：`e1ce349895b06dc57b40b5c5e1f75b50caf411ec`。工作区为未提交的 PR5 累积变更；本轮未 stage、commit 或 push。

## 本次修复的实际行为

- 将用户已定稿的完整 V3 手册接入离线包。手册 SHA 为 `cae5aceb2643720723faf87891ae2d0cf2fa877acdefa819341a9195991cfa7c`；原文中 2026-10-22 的 v7 准备状态保留为历史语境，当前入口说明另列。
- 新增独立的 HumanAnnotation / HumanSupportReview / HumanReviewLabel schema。人工词表原词与引用方向保留，兼容投影显式进行；旧 canonical Annotation、EvidenceRef、EventRelation 和业务 HTTP/数据库/Goal/Run/Decision/Schedule 契约不变。
- `human_inputs` 显式区分 received、initial、review 层。包含 review_label 的收到文件不是裸 Annotation；严格 received 视图拒绝该包装，指定 initial/review 才检查对应视图，完整原文件及来源链接均保留。共同复核不替换初标，也不新造独立样本。
- 关系引用可指向当步已经可见的同 family 旧版本，支持正常更正溯源；事件成员仍限定当步候选。未来、跨 family、过期成员及不存在段落继续拒绝。
- 五份正式标签文件保留历史目录 `labels/g1a_v1/`，仍为空；文件内容版本由记录及 manifest 声明。ReviewSession 为 guide-v3 / annotation-v2，状态仍 not_started，未填造参与者、收包或提交记录。

### 本次独立审查发现的 P2

初版 review 提取器对原始 claim 字典取 hash，而正式审计对验证后的模型取 canonical hash。合法省略 paragraph_id 时，模型补入 null，导致来源 hash 不同。

先在隔离契约探针复现失败，再将 `original_claim_sha256` 与正式审计统一为模型 canonical hash；另外保留 `original_claim_raw_sha256` 和收到文件 SHA。没有改写人工原词或原稿。
新增“省略字段／显式 null”两条完整 audit + strict validator 回归；36 个相关用例通过。
“审查 G1” turn `01a16770-3e25-7ea2-960c-239b7124508a` 独立关闭 P2，未发现新增 P0/P1/P2；该轮直接执行 36 项相关断言，检查 101 个源码指纹、181 个受控文件、513/388 必需节点及原稿保留。
最终保存工件另经补充独立核验通过，具体范围见本文末；代码闭环与保存工件核验分别留痕。

原两项 P1、两项 P2 的修复与复审历史仍在 `PR5_REVIEW_FIX.md` / `PR5_REREVIEW.md`；支持审查来源映射 P1 的历史闭环在 `PR5_SUPPORT_LINEAGE_FIX.md`。本次没有重新改变 gold、重要性或排序来掩盖失败。

## 收到材料的检查范围

本地原稿：`.local/evals/g1/dev02-05/`。

| 检查 | 当前事实 |
|---|---|
| 文件与事件 | 40 份 A/B 文件，80 条事件记录；initial 与 review 两层均结构合法 |
| 共同复核 | 用户确认 A/B 共同、reviewed_at 为真实复核时间；216 条 claim、142 个关系 |
| 引用与来源 | 216 个 derived_from 来源链接、268 处引用、142 个关系通过结构、段落定位、时序、family 和材料来源检查 |
| 重复与完整性 | 40 项文件 checksum 匹配；records_flat 与逐文件内容相同，不当作新增样本；40 组事件×步骤共同复核一致不替代原始 κ |
| 原稿保留 | 44 个提交/索引等文件与实际接收快照逐字一致。工具仅恢复完整 GUIDE_V3.md 及更新技术 manifest 元数据，修改前均保留 |
| 资格限制 | submitted_at 为模拟场景时间；历史实际收包、首次提交、冻结、接触及修订过程未核实。当前接收快照和共同复核时间不能替代这些事实 |
| 正式导入 | 未导入任何原始初标、共同复核、仲裁、支持审查或 gold；human gate 继续 BLOCKED |

216 条包括双方同一内容，不是 216 个独立研究样本。格式及引用存在性检查不自动认定语义正确，也不认定独立性。
输入材料的人工语义复核已有收到记录；正式算法输出语义支持及变化分类指标仍未测量，human-gold 指标保持 null。

DEV-04/D6：已收到共同裁定 EQ=2、PV=2，原话保存在本地 `H2_USER_RESPONSE.json`。当前两份字段均为 2，但理由仍写 EQ1、缺使用条件。
遵守“所有录入由标注者本人完成”，不由工具改写正式理由；需本人另存 amendment，保留旧稿并写实际修改时间。
“本地 CPU 部署”是提出的使用条件；test:1 只说明 local Linux toy setup，不能记为已验证 CPU 能力。

## 实际执行与保存证据

证据根目录：`.local/evals/g1/pr5/human-followup-v8-r1-20261023/`。
下表均为本轮实际执行，不是读取旧报告转称新结果。

| 命令／检查 | 结果 |
|---|---|
| `python -B -m ruff check backend tests evals` | exit 0 |
| `python -B -m evals.intelligence_v1.contracts --check-schemas` | exit 0，34 schemas |
| `python -B -m evals.intelligence_v1.validate --manifest evals/intelligence_v1/manifests/dataset_manifest.json --strict` | exit 0 |
| `python -B -m pip check` | exit 0 |
| `python -B -m pytest tests/evals -q --basetemp=<全新本地目录> -o faulthandler_timeout=30 --junitxml=<G1.xml>` | **387 passed / 1 skipped**，388 个节点 |
| `python -B -m pytest -q --basetemp=<另一全新本地目录> -o faulthandler_timeout=30 --junitxml=<full.xml>` | **512 passed / 1 skipped / 1 warning**，513 个节点，包含原 125 项旧服务/API/Goal/Run 等 |
| `python -B evals/run_baseline.py --output <seed-sanity.json>` | exit 0；仅 seed lexical sanity，不是算法或线上效果证明 |
| frontend 内 `npm.cmd --offline run build` | exit 0，实际重新构建 |
| `git diff --check` | exit 0 |
| 冻结覆盖 | 完整 full/G1 精确节点集合、测试源码 SHA、适用 T01–T24/T26 均核验；T25=N/A |
| 全矩阵 | 200 次预测 / 400 次评测 / 655 条实际命令；1,400 个确定性工件逐字一致 |
| 公平性与保留 | 五主轨迹 26 步，辅助集另列；600 个预测/input/config 与 v4 逐字一致；86 个 JSONL 保留 |
| 正常 acceptance CLI | 实际 exit 1，technical=PASS、human=BLOCKED、G1-a=false、G2=false；失败报告正常保存 |
| 截断证据负例 | full 副本仅留 125 旧+2 G1，删除 386 个 G1 并更新 SHA；technical/temporal/regression=BLOCKED，REQUIRED_TESTS_INCOMPLETE |

唯一 skip 为 `tests.evals.test_provenance_and_rights::test_symlink_outside_bundle_rejected_if_supported`，原因 `symlink creation unavailable: 1314`。按冻结的 Windows 豁免精确匹配；没有算 passed。warning 为既有 Starlette/httpx 弃用警告，未安装或升级依赖。

`checks/*.command.json` 保存实际 argv、cwd、开始/结束、退出码、执行环境及日志/JUnit SHA；`checks/verified-evidence.json` 保存 Txx 具体节点和计数。
`matrix/reproduction.json` 保存全部命令与工件 hash；`frozen.json` 是外部 pin 与 101 项源码指纹记录。`frozen-v8-r1/` 保留完整冻结包和测试。
`acceptance/` 为正常失败报告；`truncated-evidence-negative/` 明确是篡改副本，不冒充真实执行记录。

矩阵复现命令（PowerShell，输出必须全新）：

```powershell
Set-Location D:\agent_project\cfaw-news
& .\.venv\Scripts\python.exe -B -m evals.intelligence_v1.reproduce `
  --manifest evals/intelligence_v1/manifests/dataset_manifest.json `
  --manifest-sha256 ad9a58f84c25de4d60b716afb2d008739257d60d8ed68a7235cc5c72ccf6cbe4 `
  --out '<全新的本地目录>' --packets --workers 4
```

配置：五主轨迹 × 六算法 × 180/420/900 秒 × hash seeds 1/719；另含 B3、420 秒、3/14 天半衰期。
每个预测分别评估 gold 与 synthetic-fixture；oracle 单独标识。空 gold 不会被当成全负例。发包导出保存在管理员目录，不将全时序目录直接发给盲标者。

### 早先失败记录的边界

`.local/evals/g1/pr5/human-followup-v8-20261023/` 保留本次修复前原稿及技术记录：工作区 basetemp 红灯 14 failed/1 passed；初版 G1 384 passed/1 failed/1 skipped（旧测试把 schema 数写死为31）；中间一次改动期间出现 RUNTIME_CODE_MISMATCH。均未作为最终通过证据。
初版默认沙箱 full 在旧 API 的本地 socket 启动处阻塞，已中断并保留记录；针对该 API 的批准环境探针 1 passed，最终 full 在同一批准的本地 socket 环境完整执行成功。没有为绕过环境限制改动业务代码。
P2 原 hash 探针失败记录与最终 36 passed JUnit 在 r1 相邻证据目录保存，重叠测试次数不累加为研究样本。

## 真人仍需完成的内容

详见本地 `.local/evals/g1/pr5/human-followup-v8-20261023/HUMAN_TODO.md` 和 `human-work/`，不需要重抄整批共同复核。

1. A/B 各自亲自补实际手册阅读、初标收包/提交/冻结/接触/修改历史及已有原记录路径。覆盖五轨迹，DEV-01 额外保留旧 packet 及 D4/D5 修订历史。unknown/not_saved 如实填写，不补造过去时间。
2. D6 实质裁定已收到；本人只需保留新 amendment，将理由中的旧 EQ1 修正为 EQ2，并补 PV2 的使用条件、依据和范围，记录真实修改人/时间。
3. 原始 κ 中 potential_value=.556、evidence_quality=.259、tier=.281。按规划 §7.6 记录边界修订及实际新版本重标情况；共同复核一致不能替代独立初标 κ，也不得为凑 .70 改标签。已有答案/未来接触要披露。

上述材料齐备后才能决定实际资格、建立正式来源映射、冻结 gold，再以新 pin 重跑人工及总验收。不能用当前 joint review、结构检查或技术 PASS 自动跳过这些步骤。

真实生产数据库／物理磁盘故障写出、线上模型、生产部署、真实用户效果均未验证；临时 DB 或故障注入测试仅证明其覆盖的机制。无迁移，T25=N/A。
本轮未联网、安装依赖、迁移数据库、开展下一 PR、commit 或 push。

## 最终保存工件独立核验

“审查 G1” turn `01a16781-43b2-7af0-8e3d-0002bf9ff037` 已完成只读核验：**最终保存工件通过，无新增 P0/P1/P2，原 P2 保持关闭。**

独立核验了九项实际命令与日志/JUnit SHA、101 项源码指纹、完整 513/388 必需节点；655 份矩阵日志、1,400 个工件 hash、700 对跨 seed 工件、200/400 运行及 40 个比较组；600 个历史一致文件与 86 个 JSONL 保留。
独立重新调用验证确认截断负例仍被 REQUIRED_TESTS_INCOMPLETE 拒绝；实际正常验收仍为技术 PASS、人工 BLOCKED、整体 NOT_MET。
收到材料的检查结果与保存报告一致，D6 本人修订与历史初标过程仍缺；没有把共同复核认定为独立初标资格。
该轮未重跑 full/矩阵、未修改/导入/提交/push；原生符号链接权限 skip 未计通过，未验证生产库、线上模型或真实用户效果。

完整返回保存在本地 `review-final-artifacts.json`；代码 P2 关闭结论在 `review-code-closure.json`。最后保留检查见 `final-preservation.json`：181 个受控文件与 101 项源码指纹匹配，44 个收到的原稿/索引文件保留，正式标签仍空、过程表仍由真人待填、暂存区为空，旧业务源码未改变。
