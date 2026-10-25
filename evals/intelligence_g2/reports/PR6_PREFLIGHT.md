# G2-PR6 implementation / preflight

状态：实现与提交前预检已准备，**最终 g2_development 尚未执行，不建议合并**。
本报告没有把历史 995 passed、当前 collection 或无 socket 事件循环写成新完整回归。

## 基线与范围

main / HEAD `76ef14b531842ae449c4f907302218d2e2ea4c90`。PR1–PR6 仍在未提交工作区；没有五个 G2 已合并提交。
最终验收须绑定另行批准的真实源码提交，本轮没有 stage/commit/push。
既有未跟踪协作手册不自动纳入源码提交。

新增 PR6 严格契约、角色与 source release 校验、预测 worker、reproduce/evaluate/checks/acceptance CLI、指标、JUnit inventory、只读 G3 handoff；新增 v6 Schema、固定 campaign/节点清单、29 个 synthetic 案例及开发参考/草稿/复核/修订。
CI 增加原始 nodeid/JUnit 核验及较小离线 smoke，保留 fetch-depth:0 和原有门槛；尚未执行远程 CI。
README/数据字典仅追加；docs/G2_G3_HANDOFF.md 说明交接限制。没有 G3 排序、UI、HTTP transport、密钥、网络、付费模型或生产 DB 迁移。

676 份工作树文件的首次 Git 过滤预检没有字节归一化差异；这是提交前检查，不是已提交树证明。
565 份旧文件基线仅 .gitattributes、CI、README、DATA_DICTIONARY 改变；README/字典旧前缀 SHA 仍匹配。
G1、PR1–PR5 的代码/Schema/配置/fixture/原始报告及依赖锁未改变。G1 pin 保持
`5608f6c9f20d283f9274308fa98a277c535eb0d8d828fd0d863d6e1faafde06f`。
精确字节规则新增 G2 源码、测试、报告与交接文档，避免提交时破坏指纹。

## 本轮实际执行

- 新 PR6 预检 **96 passed / exit 0**；使用无 socket 的内存事件循环，保留真实任务、wait_for、计时器和取消。该结果不是正常 asyncio 或完整回归。
- 既有 PR5 内存门禁 **113 passed / exit 0**；关键跨 PR 正常 pytest **77 passed / exit 0**，覆盖生命周期、凭据、原子发布、文档版本及 PR2 修复。
- 七套 Schema、G1 strict、全域 Ruff、seed、前端离线构建及 git diff --check 通过。
- 当前 collection **1092 节点**：G2 540（其中 PR6 96），G1 427，旧业务 125。96 份测试源码指纹和 T01–T46、H01–H10/辅助节点映射已登记。G1 原 552 节点投影及 45 份源码匹配；这不是本轮 552 节点执行通过。
- 小型 PR6 smoke 经真实阶段 API 处理全部 35 个 G1 时点及当前 29 个 synthetic 案例，双通道/早期前缀一致。
- 早一版 27 案例的扩展内存预检 **500 任务**覆盖 R0/R1 三档和 standard R2，rule/mock、canonical/seed1；当前 29 案例新增的 JSON 正反控另有专项与上述 smoke。本轮没有声称这就是当前 2040 任务正式矩阵。
- 默认 asyncio 探针 5 秒超时，实际子命令 **exit 3**。本轮没有沿用以前的单次沙箱外授权。
- 用当前 HEAD 调用正式 reproduce 实际 **exit 1 / G2_PR6_SOURCE_NOT_COMMITTED / source_files**，没有创建结果目录。这是正确拒绝未提交源码的负例。

## 保留的失败与修订

初次 PR6 测试 30 failed/28 passed：嵌套 Pydantic 值未递归转规范 JSON；只修 PR6 序列化。随后 2 failed/56 passed：一个测试使用旧 serializer，另一个新增 feed_summary+synthetic 输入违反冻结 PR1。
保留 v1–v3 输入、参考和原 JUnit；v4 参考明确登记 ORIGIN_MISMATCH。它不算摘要全链正控；既有 PR4/PR5 的 secondary 阶段正控仍须执行。

后续严格 JSON 重用时，嵌套消息字符串缺 UTF-8 编码，导致模型错误分类不符（7 failed/76 passed）；修后 83 passed。测试断言和旧标签没有为掩盖错误而放宽。
扩展矩阵首次 exit 1：6 项 R0 将冲突材料分开，使同一束冲突不可用。其算法不修改；评测将这六项保留为 is_success=false/upstream_r0_separation 的基线质量缺口，默认 R1 的冲突仍为硬正控。重跑 500 任务工程错误 0，仍保留六项基线缺口，不宣称 R0 质量通过。
新增对应回归首次发现测试 helper 改策略后未重算 job_id，修 helper 后 7 passed；旧失败保留。

新增 PR6 全档案发布门禁：PR3 档案不能绕过 PR4 的敏感 hold；JSON canary 命中时 G2_PR6_SENSITIVE_EXPORT，整任务不发布原文/引用。新增 E11 JSON 正反控，旧输入/参考未覆盖。
两个即席材料编写错误（GBK 文档解码、预检复核目录尚不存在）已纠正，工具转录和 authoring-notes.json 留痕；没有编造不存在的原始日志/hash。
Ruff 排版/import 失败只修排版，没有禁用规则。

## 验收边界和未关闭项

1. 等待管理员另行批准受控 PR1–PR6 本地集成提交（不伪造五段提交史、不 push）；SourceRelease 必须核对真实 commit/tree。
2. 当前完整矩阵为 **2040 任务**：五轨迹 26 点、附属 9 点，29 案例/12 错误模式，R0/R1 ×三预算×rule/mock×seed1/719×canonical/reverse，standard R2、独立早期前缀；尚未在已批准源码上新生成、封存及独立评测。
3. 需要新授权后执行正常异步、G2/evals、完整一次 pytest 及旧 G1 reproduce。完整 pytest 若失败不自动重跑。旧 Oracle 仅 legacy diagnostic，不进入 G2 预测或成绩。
4. 提交后需要当前输出绑定的 AI 复核、完整 checks/JUnit 和 H01–H10 最终判定。预检 review 明确 final_acceptance_usable=false，不可充当最终复核。
5. 远程 CI 未运行；真实模型、探索集、人类独立评审、双标、用户研究及泛化仍 deferred/not_evaluated，不是开发硬门槛。

原 rule Item、身份和事实修订不被表达视图覆盖；未知独立性不填成已证明。零/缺参考分母返回 null 和原因。
预算保留 PR5 冻结上限，记录实际 mock 请求/字节、已知模拟 usage 与未知调用；真实请求/费用为 0，不以 Mock 成功声称真实模型质量。
G3 交接仅稳定对象/快照与限制；管理员验收 pending，G3 授权 false。

## 工件与 pin

完整 argv/cwd/UTC 起止/exit 在 `.tmp/g2-pr6-evidence/*.command.json`；JUnit、日志、失败与保存矩阵同目录。
source-precommit.json 是未提交指纹，不冒称 SourceRelease；proposed-source-files.json 是待批准名单，尚未暂存。

| Artifact | Raw SHA256 |
|---|---|
| `evals/intelligence_g2/manifests/pr6_campaign.json` | `4f530dd61a64b493408fdaa7ce14cf8b9cd793144f1b2ac61ff7dcbea8bc0170` |
| `evals/intelligence_g2/manifests/pr6_ci_campaign.json` | `a0c1416364fd158ed1d9d255c03bedf0eb74307ac52e360cfefde1363d858c20` |
| `evals/intelligence_g2/manifests/pr6_required_tests.json` | `7c7792c69350a74744dff4b515fa8f3efa46cd784bad669321034352bf149a35` |
| `evals/intelligence_g2/fixtures/pr6/v1/prediction/manifest_v4.json` | `2f165c80994bcd1bb9709c89c1aedffd0cba53a59d7ed76071c747e3b39bd599` |
| `evals/intelligence_g2/fixtures/pr6/v1/reference/manifest_v5.json` | `5fcf710c1901fe8dc9834ebaa932db18aef7c664905449176bf3f413c88a7bf6` |
| `evals/intelligence_g2/fixtures/pr6/v1/mock-response/manifest.json` | `3cf967585d5eb2fd71ebfa28a6de8a3030771edb1b4cd5be1836063d10d53495` |
| `evals/intelligence_g2/fixtures/pr6/v1/review/preflight.jsonl` | `c01642c846b7641c937b77262ce66dd0a160d954494b9bbaf148bf63b37ff601` |

## 命令记录

| Record | Exit | Log SHA256 |
|---|---:|---|
| audit-final | 0 | `d452a3e90a077ad8346cf575a13815caf025ee9cc7ec0cae80282fdd2b6842e5` |
| collect-final | 0 | `35f8c10eb05179996966c1545a2d6da7e18b898a9a51ef53e9f674f0de16daa6` |
| collect-frozen | 0 | `b04ddbecb27462c743119620ad6a06484814062d990da3a3a611482c95ead8b3` |
| collect-preflight | 0 | `15c963eb5c0fcd8f0d76f4314c872cacb52b037ebc345c16f11ca3aad33f424b` |
| cross-pr | 0 | `21fd48a3c7c92ad2bb8b5e2222b6cf1e861c6c5841136f13b888b7d672dc93eb` |
| diff-frozen | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| evaluation-final | 1 | `199a5dbba29f6be70aa216cd8df6e704feee6bfb3c50f0d1e3f7ea7e956a1f55` |
| evaluation-fixed | 0 | `4dbc62df0172c9eddbdeec109b09010ff6edfb486d2367f909185f736de448ba` |
| export-canary | 0 | `632a700e646444dc360c3d4d52cc14d997dd11be4571cd4ee13389891ab38a3c` |
| frontend | 0 | `e865b1021082f48cdd1647d55241ef6c7f8e7afb1cadc14dc5bb9bb914f071d4` |
| g1-strict | 0 | `ae200140ab0b4b55cfc9964459369e2e3a0970039dbfb7359501ad56ac18aa38` |
| inventory-frozen | 0 | `b47d57e149ba12290c004579077e07ac0b8b4502bfd70f44571a146c3e75045d` |
| loopback-probe | 3 | `d11837bd9da0ceae8ceaccb4b7208dab8dcaf2e7524465bece0a0c0a5eae553a` |
| matrix-preflight | 1 | `a25f673e93cafb07a2764d6875e89994ce30a6883a1f9e3d9f84245c14645dac` |
| matrix-verified | 0 | `a38f695baff189b595186fc6d71a119910ca5a22f9689c7af5743159021ef404` |
| pr5-immutable | 0 | `3b65d36a8983304b4fd860e08bbe99fe09c67316fb09848915c069306c3db717` |
| pr6-boundaries | 1 | `a468ff0f3cbbecd5ec3529fedaa33513e13dd8f64e67e8fc022750bfe29d6e8f` |
| pr6-corrected | 0 | `13718c2aa7da800899f55aac92ec64543f0f7e6818c9b89cea19491968c6c76b` |
| pr6-evaluation | 0 | `6d6d9166ce3b583a3c3b4f4216f0dc3c9a4cbfdc4a1513d8539b6cf2ed7259bc` |
| pr6-final-preflight | 0 | `552d2e96d04a942c2c6eac7e7b518ae7e2a01f529b3ba0da31a4786ca3887456` |
| pr6-frozen | 0 | `91b02fbc6db4d1e23585d3207272d70354fa7737fd4d7781b3e1984aa03ec2cc` |
| pr6-initial | 1 | `d171ddcb426a0bbc6eec3281404094ca91e6f42d227f736dda92a51316902b94` |
| pr6-matrix-first | 0 | `6e13a15de606350cd9d9a088b7bbb6f1f36fe4e2d7aadb114bba930fb0540f2d` |
| pr6-second | 1 | `724db85b65c77edcf05313f6d4f14f4d1f559378e6357c974acf5c82f8e802c2` |
| pr6-telemetry-frozen | 0 | `48759d039d61be00ba6fc007e30bbd06c78c4bc9e4e4b7b091c0a5f0edc30eb2` |
| pr6-third | 0 | `0f523eaa805f23a157563df6a0edd437650eebd08d67c208b682f7527b441b2e` |
| ruff | 0 | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| ruff-frozen | 0 | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| schema-0 | 0 | `ad541cc67a0a6b6ce43b44815465079cd8b104a992b74d4c1a670e767b546d7d` |
| schema-1 | 0 | `a809da7e3eeb608fdce4300ac3ac61ce71461ebdd5e50803baaede51ffa8f3e1` |
| schema-2 | 0 | `ffc3a2599f9fe6d9e1046f4e8cf20d19c948e76b87b838f97e144cb2df555923` |
| schema-3 | 0 | `27303a3b8249fbfd930481b365912d74dd58bf322a1a4e137ceee3509558cf51` |
| schema-4 | 0 | `a01abfe266c318861e969fd32356b29343cd6052cbbc61f0d7304dc7c71279de` |
| schema-5 | 0 | `86f275951f363daa9ee1f8ebb1b605842a9fb7608f7e8039653699ec0eb7d877` |
| schema-6 | 0 | `4cb4acf92174a3b56b040ebc4a2f84641fee099970b539f00d40679cbdb2ef40` |
| schema-6-frozen | 0 | `4cb4acf92174a3b56b040ebc4a2f84641fee099970b539f00d40679cbdb2ef40` |
| seed | 0 | `f7c083f27a0708f11a48e2de9acd0464b3e49d81c41a6ed43d8d8e94a81dc75e` |
| uncommitted-guard | 1 | `602f1d7b72da1aa012700f3034a051f4ca8dc7527b49d0ea78fa2aecf3cf0f18` |


H01–H10 最终结果由当前封存工件、真实提交、严格节点清单和输出绑定 AI 复核推导；缺证据 BLOCKED，失败 FAIL，均不得整体 PASS。
回滚仅 PR6 新模块/Schema/配置/fixture/测试/CI 增量及追加文档；保留 PR1–PR5、G1、G0 和所有历史工件，无 DB 回滚。Git 回滚须另行批准。


管理员批准本地集成提交后，首次 staged diff --check 检出精确字节 CRLF 和既有计划文档的 Markdown 双空格换行。只补相应路径 whitespace=cr-at-eol 与该 Markdown 路径 -blank-at-eol，未改代码、测试、fixture 或冻结字节；staged-whitespace-before.command.json/log 保存原 exit 2。正式验收将绑定补属性后的真实提交。
