# G2-PR6 审查修复：连续性硬门禁与安全 JUnit 诊断

状态：**定向修复及提交前预检完成；新提交、正常异步/完整回归及同提交最终验收待批准/执行。当前不产生新 PASS，不建议合并。**

实际记录时间：2026-10-26T14:51:18.270579+08:00（Asia/Shanghai）。
基线 HEAD：`0ba7093bd148ea1c4498390677f913c853e94f65`。开始时跟踪文件干净，既有未跟踪协作手册原样保留。没有自动 commit/amend/push。

## Before / after

### P1：已知连续性不匹配仍可满足 H02

按报告只在内存改变 DEV-01 D8 的 key；原归档不变。正控 rule/mock 均 1/1，负控均 0/1。修复前 `ok=true, errors=[], H02_condition=true`，复验 exit 1。
先添加 key 漂移、前后 step/成员缺失、正常连续性、different 参考与零分母回归。初次回归共 11 failed / 2 passed / exit 1（含 P2）。
最小修复：默认 R1 的已知不匹配加入 errors：`continuity_mismatch / identity_continuity / event_key`，record_id 对应冻结连续性案例，reason 区分 endpoint_missing 与 identity_mismatch。H02 另直接检查每个 R1 cohort 的连续性分子=分母、FP=0、无错误且 R1 cohort 存在。
R0 缺口保持在 baseline_quality 且 is_success=false；无参考仍 null/no_applicable_reference，不伪造成 100%。不同身份参考按 expected 精确判断；R2 保持补充对照。
修复后同一原复验：负控 `ok=false`、明确 continuity_mismatch、H02_condition=false，exit 0。额外测试证明即使伪造 aggregate ok=true/errors=[]，0/1 也不能通过 H02。

### P2：JUnit nodeid 参数进入公开拒绝诊断

只在内存替换 JUnit，用公开合成哨兵复现；修复前 CLI 拒绝 exit 1，但 stdout 包含哨兵，整体拒绝断言 exit 1。未读取真实凭据。
公开诊断保留已有 code/stage/field JSON 形状，不增加字段、不改 Schema；field 只含固定 node_sha256: 前缀及原 nodeid UTF-8 SHA256。failure/error/非豁免 skip 都使用该路径。内部仍保留原始 nodeid，用 Counter 精确核对全集与精确 skip 豁免，绝不拿摘要替代节点匹配。缺 property value 明确拒绝。
修复后原复验 stdout 不含哨兵，诊断仍 exit 1、整体复验 exit 0。failure/error/skip 分别断言完整 code+stage+摘要 field，并检查 stdout/stderr；普通配置、节点不一致及精确/错误 skip 豁免均保留正反控。修复前 pytest 失败工件可能包含公开 synthetic 哨兵，不含真实秘密；旧失败材料保留。

## 本轮实际验证

- 原复验 before exit 1，after exit 0；新增 20 节点，比较器/JUnit 两文件共 35 passed。
- PR6 全部内存预检 128 passed；关键跨 PR 127 passed（原子导出、PR2 身份/关系、PR3 生命周期目标、PR4 凭据、PR5 迟到错误）。均使用明确标识的无 socket 事件循环，保留真实任务/定时器/取消；不冒充正常异步或完整系统回归。
- 完整 collection 1124 节点，PR6 128；T01–T46 与 H01–H10 映射完整，JUnit 安全节点加入 H01/H09。既有测试源码与豁免未放宽。required_tests 只按新测试真实 collection 更新。
- Ruff、G1/PR1–PR6 七套 Schema、G1 strict、seed、前端 npm --offline run build、diff --check 通过。首次 Ruff 仅一项 import 排序，修正后通过；失败日志保留。
- 对旧 final-002 的 2040 任务只作当前比较器后评测兼容性复核：metrics 字节完全相同，R0/R1/R2 主集 standard/rule 连续性仍各 5/5。此项没有重跑预测，不是新源码最终验收，原 sealed 工件/hash 不变。
- 当前默认 asyncio 探针 5 秒超时，exit 3；未擅自扩大权限。正常异步、全部 G2/evals、完整 pytest 本轮尚未执行。旧 1103 passed/1 skipped 属于基线提交，不充作修复后结果。

## 文件及冻结边界

修改仅限 PR6 evaluate.py、acceptance.py、junit_inventory.py、test_evaluation.py、test_junit.py、pr6_required_tests.json；README/数据字典追加说明，新增本报告。精确 9 路径及 SHA 见 .tmp/g2-pr6-review-fixes-001/proposed-fix-files.json。
未修改 G1、PR1–PR5、冻结输入/参考/标签、Schema、Prompt、配置预算、锁文件、旧验收报告、业务代码、DB 或 UI；没有联网、真实模型、工具代理、迁移或 Git 发布。新 hash 快照和基线保护核验见同目录 frozen-proof.json。

## 未关闭项与后续授权

1. 按已锁定“提交后最终验收”规则，需管理员另批这 9 路径的一个本地修复提交；不 amend、不 push。旧两次提交授权均已使用。
2. 需另批新提交上的正常异步专项、全部 G2/evals、新 2040 任务矩阵及独立评测、G1 旧系统复现和检查；通过且源码冻结后，仅执行一次完整 pytest。此前单次授权不延续，失败不自动重跑。
3. 全部门槛通过后再运行原生 acceptance，绑定新 source/manifest/checks/review pin。旧 final-002 及历史失败保留，不改写。
本报告仅 ai_development、synthetic_fixture、同一 AI/non_blind/independent_validation=false；来源真实性、人类独立评审、用户研究及泛化 not_evaluated。只修当前 PR6，不进入 G3。

## 实际命令/exit/log hash

完整 argv/cwd/UTC 起止/exit 位于同名 .command.json；JUnit 为 before.xml、after.xml、pr6.xml、cross.xml。日志不自动改写为 PASS。

| Record | Exit | Log SHA256 |
|---|---:|---|
| archive-comparison | 0 | `43328b70ede98745c5f14977aa648c3383a536662bb086a2424b4da05d502016` |
| asyncio-probe | 3 | `e6cc29d7b90afad0ad73fa8a05c2d6ecaca6ef26ea3dec62c7ff8bb8107f9f4f` |
| collect-final | 0 | `316de49f181151d95518e54d3c949141999d2211263e61b963acc1c8de6909b1` |
| collect | 0 | `4d5edd8334ea7da07bba7f9f747cea6814a861cf579e13d000057a40edd02694` |
| cross-pr | 0 | `9ee57e53b5764c9aab0ba08530759550919a3e93e7bcf10b67290021106101cb` |
| diff-check | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| frontend | 0 | `efd18788ab9218d0547895fb0a663171df325453c45a37431b9ef5ccbd680471` |
| g1-schema | 0 | `ad541cc67a0a6b6ce43b44815465079cd8b104a992b74d4c1a670e767b546d7d` |
| g1-strict | 0 | `ae200140ab0b4b55cfc9964459369e2e3a0970039dbfb7359501ad56ac18aa38` |
| inventory | 0 | `7d3a8570a5e89532d13300aac4679291fa86a2ab56d4fa9e755509da6cebefc7` |
| pr1-schema | 0 | `a809da7e3eeb608fdce4300ac3ac61ce71461ebdd5e50803baaede51ffa8f3e1` |
| pr2-schema | 0 | `ffc3a2599f9fe6d9e1046f4e8cf20d19c948e76b87b838f97e144cb2df555923` |
| pr3-schema | 0 | `27303a3b8249fbfd930481b365912d74dd58bf322a1a4e137ceee3509558cf51` |
| pr4-schema | 0 | `a01abfe266c318861e969fd32356b29343cd6052cbbc61f0d7304dc7c71279de` |
| pr5-schema | 0 | `86f275951f363daa9ee1f8ebb1b605842a9fb7608f7e8039653699ec0eb7d877` |
| pr6-preflight | 0 | `addeda551e6d90afd0e59a0e9f3ac79a93098d1a2cc7842ca6a3598af4c8787c` |
| pr6-schema | 0 | `4cb4acf92174a3b56b040ebc4a2f84641fee099970b539f00d40679cbdb2ef40` |
| regressions-after | 0 | `b9f2594a17e2e91edc30cd9ee986a0a15c594fc093325feaaf4fa723dccd90b9` |
| regressions-before | 1 | `fb31fabede04404ed002367f3b33d3ee2f910dfb90902bb121463e562ccf0de4` |
| review-after | 0 | `2a027b8aa0283eea5113496d8f53fb79b8b82854d8ba4eb6a6cee3b31ea0663e` |
| review-before | 1 | `b531175a48239c1efcc6252a2fe7daac6bdc897cd65ec753130391a19f9742a4` |
| ruff-first | 1 | `9aa03c0c5c8a017fe4c85ff5cb351e4fbe9be6fa7fade506590a59c963140213` |
| ruff | 0 | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| seed | 0 | `85c8f38d0cd830e0ed7a5611065ad28f2853871c5d8b34f0fd30964df5c43938` |
| static-checks | 0 | `31b02b821dbfd84652874584baa8c0a48b1ffc696ce6851bf9fdc355f9a21914` |
