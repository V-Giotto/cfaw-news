# G4-PR1 审查修复：文档链、覆盖区间和身份绑定

日期：2026-11-02（Asia/Shanghai）。基点仍为 main@
`2655f10cf20c647bdbfd1b69a000847471b2c5a3`。范围仅为本次三个 finding。

状态：三个 finding 已修复，本轮工程自验收 PASS；最终命令/门禁状态以同目录
`REVIEW_FIX_BASELINE.json` 为准。等待独立复审，不自动开始 PR2。
原 PR1 自验收 PASS 不能关闭本次发现；原 baseline、release manifest、日志和
Schema v1 保留，不改旧 pin 来适配新代码。

## 1. [P1] 跨步骤文档链回退/分叉

用户给出的原始 rollback/fork 输入在修复前原样重跑，两项均实际 exit 0，
记录在 `.tmp/evals/g3/g4-pr1-review-fix-20261102-001/red-*.command.json`。
publishable=false 只是发布边界，没有使错误输入门槛变为通过。

现在 RuntimeInput 使用跨整个 prefix 的 document archive 与 VersionIdentity
ledger。每个已捕获 version ID 的内容、元数据和 supersedes 关系都不可变；
以所有已捕获 identity 调用原生 version_chains，要求形成唯一完整线性链。
当前选择必须是该 document 的已捕获链尾，局部 lineage 必须与完整链逐项一致。
空候选步骤不清除已捕获历史。

修复后，同一原始输入与外部 pin：

| 反例 | 实际退出/诊断 | 结果 |
|---|---|---|
| v1→v2 后重新选择 v1 | exit 1，G4_SEQUENCE_INVALID / current_document_must_be_captured_tail | 拒绝，未签发输出目录 |
| v1→v2 后 v3 直接继承 v1 | exit 1，G4_SEQUENCE_INVALID / captured_document_chain，native VERSION_CONFLICT | 拒绝，未签发输出目录 |
| local lineage 遗漏 v2 | 直接 JSON 与 CLI 均拒绝 | 不跳过中间版本 |
| 改写已捕获前驱 | G4_HASH_MISMATCH / immutable_predecessor_identity | 不接受另一个局部有效历史 |
| 消失一步后再选择 v1 | 直接 JSON 拒绝 | 已捕获 v2 不被遗忘 |
| v1→v2→v3，或再次选择 v3 | 完整 native replay 通过 | 合法链尾仍可复用 |

没有修改 G1 version_chains 或 G2/G3 算法，也没有修补输入/hash 来放行。

## 2. [P2] 来源存在性不是完整窗口覆盖

原 coverage-minute 输入在修复前实际 exit 0；原生 G2 gap 列表为空，但一天请求
只有最后一分钟有 covered 观察。原始复现和输出没有被覆盖。

现在每步结果新增必需的 `native_steps[i].coverage`，复用 G3 冻结的
requested-interval-conservative-union-v1 纯计算与 CoverageDiagnostics 严格模型。
G4 只将引用指针映射到自己的 `/input/steps/i/source_coverage/n`。原始 windows、
G2 evidence、bundle、rule 和 presentation 均不修改。

修复后的相同原始输入仍合法，actual exit 0；新诊断：

- `has_gap=true`；source 的有效状态为 partial。
- `[2026-01-01T12:00:00Z, 2026-01-02T11:59:00Z)` 为 unknown 且 unobserved，
  共 **86340 秒 = 23 小时 59 分钟**。
- 最后一分钟保留为 covered。
- 冻结的 native G2 `evidence.validation.coverage_gaps` 仍为空；消费者必须使用
  新 G4 coverage 判断请求窗口缺口，不能把原生列表当完整窗口证明。

新增正/负对照涵盖完整覆盖、相邻/重叠 covered 并集、窗口外记录、点观察不填充
正时长区间、零时长请求、failed veto、空候选池、JSON 指针解析，以及序列化结果
删除 has_gap 的拒绝。非 covered、无观察与来源存在性保持不同语义。

## 3. [P2] namespace、snapshot 与 integrity pin

已更正 ADR、入口审计和原实施报告中的错误派生关系，并明确标出审查修订。
原始文档字节保存在本轮 `.tmp/.../before/`，不伪装成原文一直正确。

- grouping namespace：dataset_id / timeline_id / strategy / identity_revision。
- evidence namespace：dataset_id / timeline_id / strategy / history_revision / config SHA。
- rule namespace：evidence namespace + generator_revision。
- event identity：namespace、birth anchor、必要的 split/complex transition；revision
  另绑定 features/relations/lineage。
- snapshot ID：item_id、as_of、bundle_sha256。
- input pin：整份输入 exact-byte 完整性，在 grouping state 保存并用于状态续接检查。
- previous-state pin：完整 typed state 的摘要与阶段链绑定。

当前 CLI 对照仅将 G4 profile 从 70/30 改为 60/40：input/config pins 不同，
三类 namespace、event keys、snapshot IDs 相同；完整 grouping state 摘要不同。
实际记录见本轮 `namespace-current.json` 及两个 `green-namespace-*.command.json`。
相同语义身份不证明可以安全继承状态；跨请求 registry/状态续接仍未实现。

## 4. Wire、历史兼容和工件保全

- 输入仍为 runtime contracts v1，但文档链校验加强，旧非法输入不再被接受。
- 新结果为 `g4-pr1-briefing-v2`，每步为 `g4-pr1-native-step-v2`；当前 Schema
  注册在 schema/v2，coverage 是必需字段。
- schema/v1 十个文件、原 55 测试源码/required manifest、原 baseline/release
  与用户 review 输入/执行记录均保持原字节。
- 新增 26 个节点采用独立 `pr1_review_required_tests.json`，不修改原测试门槛。
- 同一旧合规输入/pin 重新计算后，grouping/evidence/rule/presentation 全部与旧输出
  一致；只有结果 envelope/coverage 的新增契约不同。旧输出不能只换 pin 当 v2。
- 原 G1/G2/G3、旧业务代码、前端、CI 与 /dev-diaries/ ignore 规则均不修改。

## 5. 本轮验证与失败记录

原始命令根目录：`.tmp/evals/g3/g4-pr1-review-fix-20261102-001/`。
每条命令保留 argv、cwd、受控环境、实际退出码、起止 UTC、耗时及原日志 SHA。

| 运行 | 实际结果 | 解释 |
|---|---|---|
| red-tests | 18 failed / 8 passed | 修复前真实失败；已能拒绝的局部错误保留为对照 |
| green-tests-01 | 25 failed / 56 passed | 新 coverage 接口首次接线错误：未将 datetime 通过严格模型序列化 |
| green-tests-02 | 81 passed，0 skipped | 改用原生严格模型构造，未放宽规则或删测试 |
| 原 review CLI | 修复前 rollback/fork exit 0，修复后 exit 1 | 保持原输入与原 pin |
| coverage-minute CLI | exit 0，并明确 unknown 86340 秒 | 不篡改原生 G2 gap 列表 |
| namespace CLI 对照 | 两项 exit 0，身份投影一致、完整性 pins 不同 | 支持修正文档关系 |
| 注册 G3 runner | 630 passed，无 skip | 本轮实际重跑 |
| 注册完整旧仓 runner | 1753 passed / 1 skipped / 1 warning | 本轮实际重跑；唯一 skip 仍为 Windows symlink 权限 1314 |
| Ruff / 当前 Schema v2 / baseline / 离线前端构建 | 全部 exit 0 | 本轮实际命令；未改前端源文件 |

完整旧仓 pytest 实测 1123.53 秒，含启动和控制面检查的命令耗时 1129.36 秒。
原 1754 节点库存与 JUnit、collect/G3/full 控制记录由修复基线生成器再次严格核验。

本轮还执行 Ruff、Schema、注册 G3 与完整旧仓回归，以及项目要求的 baseline/
前端离线兼容构建；最终数字、JUnit、控制记录核验和 source/config/output pins
见 REVIEW_FIX_BASELINE.json。历史上一次 1753/630 记录没有冒充成本轮结果。
失败日志不删除、不覆盖、不重新标为通过。修复是 AI 合成开发回归，不是独立研究。

剩余边界保持：真实 G3 runtime adapter 未注册，publishable=false，未实现 DB/API/
前端接入或跨请求续接，没有真实网络/模型调用、Git 写入或 dev-diaries 读取/上传。
