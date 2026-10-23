# G1-PR5：支持审查溯源 P1 修复与验收

当前冻结：`pr5-five-trajectories-v7 / g1-pr5-3`。

Manifest SHA-256：`da2fba917ffc4654abb6ef2467ddc0f4796b4ef560cd7c6761f4aa2e47f7bfc4`。

原 P1 已修复并经独立复审关闭；本轮技术验收 PASS。人工门槛 BLOCKED，G1-a=NOT_MET、G2=false。

## 问题与最小修复

旧 SupportReview 要求双方初标的主张、引用和 scope 与最终裁定完全相同，无法保留正常的不同原稿后记录共同裁定。
新增可选 `source_claim_alignment`，来源以 annotation_id 与完整原始 ClaimReview 的 canonical SHA-256 显式绑定；记录对齐理由、人员和实际时间。
每个来源必须唯一解析，映射须精确覆盖全部 prior 注释及两名审阅者；检查 Persona/标注版本、原稿冻结与对齐/终审先后。
最终文字、范围和引用可以经显式人工对齐后不同，但未来、跨 family 和不存在段落的最终引用仍被拒绝。
未提供映射的旧记录继续走严格一致路径，没有自动模糊匹配或按列表位置配对。

变更限于离线契约、审计、schema、必需测试清单与版本说明。初标、gold、预测条目、排序、预算及 HTTP/数据库/Goal/Run/Decision/Schedule 契约未改。
旧 v6 的完整包、测试与身份记录保存在 `.local/evals/g1/pr5/support-lineage-v7/before/`，原有 v6 运行与复审记录保留。

## 先红后绿

- 五种差异正例在修复前均失败：措辞、引用子集、引用顺序、scope、第三种最终表述；JUnit 与日志为 `pytest-red.xml/.txt`。
- 初次相关运行两份记录各为45 passed / 1 failed：新测试错误地期望 FUTURE_EVIDENCE，而原有正确拒绝码是 FUTURE_VERSION。只更正测试期望，没有改弱时间门禁。
- 修正该项及六个 schema 拒绝样例后，聚焦7项通过。最终全量/G1均覆盖全部26个新增节点。
- 拒绝路径包括缺映射、错 hash、缺来源、单方、重复、跨步、冻结前/终审后对齐、含糊重复主张、原稿内容变化，以及未来/跨 family/缺段落引用。
- 保留两个旧严格匹配路径对照；原稿中插入另一主张不会改变 hash 定位。

所有正例中标为 PASS 的人工会话均是临时合成契约探针，不能算真实人工材料。

## 实际执行结果

| 检查 | 结果 |
|---|---|
| Ruff、派生 schema、strict Manifest、pip check | 全部 exit 0 |
| seed 基线、前端离线 build、diff check | 全部 exit 0 |
| 完整 pytest，含全部125项旧服务/API/Goal/Run等回归 | 488 passed / 1 skipped / 1 warning；489节点 |
| 独立 G1 pytest | 363 passed / 1 skipped；364节点 |
| 必需清单 | 全量489/G1 364；适用T01–T24/T26；T25=N/A |
| 复现矩阵 | 200预测 / 400评测 / 655条成功命令；1,400个确定性工件，700对一致 |
| 旧数据与排名保留 | 86个JSONL、600个预测/输入/config与旧版逐字一致 |
| 真人输入保留 | 12份原稿及本轮共同裁定、变化类别输入哈希未变 |
| 正常验收CLI | exit 1符合预期；technical=PASS、human=BLOCKED、checks/matrix_verified=true |
| 截断证据负例 | 保留125旧+2 G1，移除362 G1并更新全部SHA，仍被REQUIRED_TESTS_INCOMPLETE拒绝；technical/temporal/regression=BLOCKED |

精确 argv、cwd、退出码、环境、日志与JUnit SHA在 `.local/evals/g1/pr5/support-lineage-v7/checks/checks.json`；其余工件位于同目录的 `matrix/`、`acceptance/`、`truncated-evidence-negative/`。
主矩阵为五轨迹×六算法×180/420/900秒×seed 1/719，另含B3半衰期3/14天敏感性；gold与synthetic-fixture分别评测，oracle单列。
时间和耗时不混入确定性内容。重复运行没有扩大样本数。

Windows 原生符号链接权限1314仍为冻结清单中明确豁免的skip，不计通过。Starlette/httpx弃用warning保留；没有为消除它安装依赖。

## 独立复审

“审查 G1”代码复审 turn `01a16401-b27a-7d51-a812-27da5cf010d3`：PASS，原P1关闭，无新增P0/P1/P2。
独立通过26个新增用例、2个旧对照及8个补充探针；五个差异正例也通过完整数据校验。
最终保存工件追加核验 turn `01a1640d-3460-7f41-9e84-0d4f3bc2f32c`：PASS。该核验读取既有工件，未再次运行完整测试或矩阵。
原文分别保存在本地 `independent-code-rereview.json` 与 `independent-artifact-rereview.json`。

## 人工与验收边界

用户此前已确认两名真人，DEV-01的43条关系语义、7项完整事件裁定与50个支持工作项已登记在本地。
本轮修复提供表达其原始主张到终审裁定的契约，没有将这些记录自动导入正式gold，也没有覆盖原始判断或初标κ。
正式五类人工JSONL仍为空；冻结数据卡中的缺少人工记录描述针对本包正式记录，不否认本地已有共同复核。
旧包/修订史、手册版本与正式映射仍待闭环；DEV-02～05仍缺20步双方初标，共40份。人工总验收不能用技术探针或仲裁后共识替代。
算法输出的语义支持、真实用户效果、真实生产数据库/物理磁盘故障仍未实测。T25=N/A。

未联网、未安装依赖、未迁移生产数据库、未 commit/push。HEAD仍为 `e1ce349895b06dc57b40b5c5e1f75b50caf411ec`。
