# G2-PR4 开发验收

状态：PR4 范围 ai_development PASS。管理员已批准本轮单次沙箱外完整 pytest，当前源码全量回归通过。独立研究仍为 not_evaluated。

本报告由 Codex 编写，review_origin=ai_development，non_blind=true，independent_validation=false。所有新增开发材料均为 synthetic；不是独立研究或真实新闻质量证据。

## 基线与范围

- HEAD：76ef14b531842ae449c4f907302218d2e2ea4c90。PR1–PR3 及既有 G2 文档原本未跟踪；没有将当前全部 G2 误当作 PR4 新增。
- 新增 pr4 包、Schema v4、PR4 配置、fixture v1/v2、专项测试及本报告/风格示例；README 和数据字典仅追加。
- 保全 406 个原有受控文件：仅两份追加文档内容变化，其原字节前缀与基线 SHA 一致；G1、PR1–PR3、锁文件、业务/前端源码、既有报告、原 .gitattributes 状态保留。archive/articles.json 与 HEAD blob 字节一致。
- G1 外部 manifest pin：5608f6c9f20d283f9274308fa98a277c535eb0d8d828fd0d863d6e1faafde06f。
- 不联网、不调用模型、不访问生产 DB/私人内容、不迁移、不修改 UI、不 commit/push。完整 pytest 仅使用临时 canary/隔离测试数据。

## 最终行为

固定 PR3 预测工件 → 验证 PR2/PR3 pin/代码/Schema/锁/候选与状态链 → Persona-free 证据与权限投影 → 来源归属的原文 FactText → 候选 tier + 规则模板 → 最小引用、Item、追加式快照、校验与 manifest/trace。

每个当前事件恰好一个 Item；零事件零 Item，不套 G1 配额或排序。Focus 单源声明保留完整 scope 和未独立核验风险；Radar 的原句与分号连接的全部风险最多两句；无安全表达、权限不足、目标未解析、敏感缺口或预算不足为无事实 hold。所有规则和数字来自引用，不自由翻译，不补标题条件，不升级独立支持。

event_key/event_revision 原样继承；fact_revision 不含 Persona/生成时间/tier/推断。content_revision 不含 as_of/父文件 pin/快照链接。观察快照与内容身份分开，merge/split 保留全部前驱链接，旧对象不覆写。三档预算在开发评测前冻结，引用按段落区间取并集计费；模板重复不重复收费。

规则生成器是唯一实现。ItemGenerator 协议仅提供已批准的事实、scope、引用、状态、必需风险和字符预算；没有 LLM、PR5 mock/降级工作流或 G3 排序。

## 实际验证与可复现证据

全部命令的原始 argv、cwd、UTC 开始/结束时间、exit code 和日志 SHA 位于 `.tmp/g2-pr4-evidence/<name>.command.json`。下面是本轮实际执行，不引用 PR3 历史通过数：

| 名称 | exit | 日志 SHA256 |
|---|---:|---|
| final-boundary-review | 0 | `f1f179045311c5050507d3d8c9502025455f6688af17515da8f3fc7044333286` |
| g2-current | 0 | `dddd09269fcd7aecaf9fc8158511c29669e01c1e3ff639eb900414f8d0185a71` |
| ruff-current | 0 | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| g1-schema | 0 | `ad541cc67a0a6b6ce43b44815465079cd8b104a992b74d4c1a670e767b546d7d` |
| pr1-schema | 0 | `a809da7e3eeb608fdce4300ac3ac61ce71461ebdd5e50803baaede51ffa8f3e1` |
| pr2-schema | 0 | `ffc3a2599f9fe6d9e1046f4e8cf20d19c948e76b87b838f97e144cb2df555923` |
| pr3-schema | 0 | `27303a3b8249fbfd930481b365912d74dd58bf322a1a4e137ceee3509558cf51` |
| pr4-schema | 0 | `a01abfe266c318861e969fd32356b29343cd6052cbbc61f0d7304dc7c71279de` |
| g1-strict | 0 | `ae200140ab0b4b55cfc9964459369e2e3a0970039dbfb7359501ad56ac18aa38` |
| seed | 0 | `fa74c72cf0624fcc490c7aa4a46331009fb4e1ccdce6f4cd840a461986aff347` |
| frontend | 0 | `9049c55155f263a7a340ee6c6ad3aa462fd549981669d3300a13c1fbfe8e4b59` |
| matrix-verified | 0 | `793e3ee3c49eac067a2ad1c3b24ea559ebe9126d032cfc98e3929e5d7f86f730` |
| loopback-probe | 3 | `d11837bd9da0ceae8ceaccb4b7208dab8dcaf2e7524465bece0a0c0a5eae553a` |

主要命令（.venv Python；完整精确 argv 以 command.json 为准）：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/evals/g2/pr4 -q -p no:cacheprovider --basetemp=.tmp/g2-pr4-final-boundary-review --junitxml=.tmp/g2-pr4-evidence/pr4-final.xml
.\.venv\Scripts\python.exe -B -m pytest tests/evals/g2 -q -p no:cacheprovider --basetemp=.tmp/g2-pr4-g2-current --junitxml=.tmp/g2-pr4-evidence/g2-current.xml
.\.venv\Scripts\python.exe -B -m ruff check backend tests evals
# G1 / G2 PR1 / PR2 / PR3 / PR4 contracts --check-schemas 均已执行
.\.venv\Scripts\python.exe -B -m evals.intelligence_v1.validate --manifest evals/intelligence_v1/manifests/dataset_manifest.json --strict
.\.venv\Scripts\python.exe -B evals/run_baseline.py --output .tmp/evals/g2/pr4-seed.json
# frontend 工作目录：npm.cmd --offline run build
```

- PR4：52 passed；含 T29–T36 正反例、固定配置/schema、累计权限、敏感缺口、组合生命周期/冲突和多父快照。JUnit：pr4-final.xml。
- 所有 G2：288 passed（g2-current，exit 0）；包括 PR1–PR3 及其审查修复反例，不用旧通过数代替当前回归。
- 五套 Schema（G1 加 PR1–PR4）、G1 strict、Ruff、seed、前端离线构建 exit 0。
- 矩阵：38 次成功预测后独立评测，35 个既有时点（5 主轨迹 26，其他 9），40 个开发/兼容时点；R0/R2 父分组不变。每项传承父 event_key/event_revision。
- Item 时点观察数（非独立样本）：全部 {'focus': 36, 'hold': 86, 'radar': 5}；既有 35 时点 {'focus': 4, 'hold': 80, 'radar': 3}。不宣称相对 R0 效果或真实世界泛化增益。
- 13 组 PR4 冻结开发期望无 tier 差异；结构引用校验、字节复现、正反断言是开发证据。不是独立语义金标或真实性证明；unknown/hold/未评测保留真实状态。
- reference/review 未进入预测器。审计阻断 reference stat/open、G1 gold、网络、DB、.env、私人目录和输出区外写；backend/retrieval.py 仅为继承的代码指纹白名单，不加载业务 provider/database。未读取真实用户 DB 来计算“不变”，canary 验证独立。

## T29–T36 对应断言

| 测试 | 实际检查 |
|---|---|
| T29 | 十份重复一 Item/一去重声明、十个来源可达；重复事件报 code/stage/field/record；15 独立事件不按配额裁减。 |
| T30 | 完整单源 scope focus；风险/scope/状态伪造失败；必要原句或累计额度超限安全 hold；两组更正/冲突双方超名额 hold。 |
| T31 | Radar 最多两句、全部谨慎项保留；多句引文不能藏在模板内；secondary 原文归属/unverified 有非空合成契约正控。 |
| T32 | 零事件零条、coverage gap 保留；无正文无事实 hold，不凑条数、不生成 no_change。 |
| T33 | 40→400、up to→average、版本/引用 span/slot/Task 指标伪造失败；百分点/量词不被转换为假事实。 |
| T34 | 正确更正/撤回需 PR3 transition，旧/新原文均在；否定/意向/不同指标+scope 污染不撤回；普通修订不冒作更正。 |
| T35 | 改兴趣、目标、约束、知识、locale、预算和探索偏好，投影、生成请求依据、Item/fact_revision/tier 不变，无 Persona 原文导出。 |
| T36 | Hash seed 1/719 与输入重排字节一致；D0 前缀与 D8 的 D0 行相同；旧文件/状态前缀不变；新发布不继承旧 Claim；未来坏形状先时间预检；原子失败无输出、覆盖/路径越界拒绝。 |

## 初期失败、反例与修订（保留真实记录）

- pr4-initial：4 failed / 22 passed。真实缺陷是去重摘要错误纳入引用 ID；已改为完整原句/类型去重，不把多来源当多主项。其余为初始测试适配错误：G1 字段名 persona、共享 placeholder 错误映射以及长摘要应 hold。随后另加短摘要正控，未移除长摘要 hold 负例。
- pr4-replay-initial：39 passed / 1 failed。I/O 审计漏登记继承的公开 retrieval.py 指纹读取；只增加该精确文件白名单，没有放宽业务导入、DB、标签或网络断言。
- ruff-initial：7 项 import/unused；仅修 PR4 新文件。后续全域 Ruff 通过。
- 矩阵 harness 初次因脚本 sys.path 失败；第二次同原因（修补脚本读入时 Windows GBK 解码失败）；matrix-final 因重用临时构造目录而被拒绝。保留失败命令/log，不覆盖成功产物；matrix-verified 使用新目录完成。
- AI 代码复核主动补齐：多组 mandatory lifecycle/冲突不能只选最后一组；merge 存续键也必须链接所有父快照；上游已排除敏感段落时整个 Item hold。均有新增正反断言，未触及 PR1–PR3。
- v1 输入草稿包含 https synthetic URL 和不合法 synthetic feed_summary。v2 修正成合法 synthetic 格式，v1 与其期望保留；v2 期望 tier 与 v1 完全相同，不为提分改标签。Feed-summary 另作明确的合成契约测试，不伪装为 G1 真来源端到端验证。

## Pin、工件与复核

- PR4 config 原始字节 SHA：906d0fd33dfaa70ee2a9c093d22cd4b591f1b742c503890cbaa4262ffe8d0400。canonical snapshot 与原文件格式/省略默认字段可能不同；其语义 hash 单独核验。
- `.tmp/g2-pr4-evidence/source-snapshot.json`：当前 PR4 代码/测试/Schema/配置/fixture 指纹；baseline.json/preservation-pre-full.json/archive-preservation.json：原资产保全。
- `.tmp/g2-pr4-evidence/matrix-verified.json` 逐次记录 API 调用及等价 CLI；外层 matrix-verified.command.json 是实际执行命令。不要将等价 CLI 说成本轮逐条启动过的子进程。
- `.tmp/evals/g2/pr4-matrix-verified/`：全部新运行目录及独立评测目录，manifest 记录每份语义工件 SHA/字节数/行数、源码、Schema、锁与父 pin；Trace 真实时间和零模型成本单独绑定 manifest。
- `fixtures/pr4/v2/review.jsonl`：实际创建时间、输入/参考/预测/代码 pin、已见上下文、反例与复测；同一个 AI 非盲复核，无第二真人或独立判断伪称。
- `reports/PR4_STYLE_EXAMPLES.md`：5 份可读 synthetic 示例，仅供少量风格产品决断，不要求管理员逐条标注。

## 未关闭事项与完成门槛

1. 完整 pytest 门槛已关闭：本轮管理员明确批准后在沙箱外执行，839 passed / 1 skipped，exit 0。沙箱探针 exit 3 的原始记录保留，不改写为 PASS。该次授权已经使用，不延续到后续运行。
2. 风格示例已交付；当前采用已批准的中文结构＋原词、来源归属直引版。未声称管理员已做本轮风格选择。
3. 规则覆盖有限，较多既有事件保守 hold；原始声明真伪、独立研究、真实新闻语义质量均 not_evaluated。没有引入 PR5/LLM 或 G3 来消除此限制。

本轮 PR4 客观开发门槛已通过，可提交管理员进行审查与合并决断；风格示例的产品选择单列，不伪造已确认。没有自动 commit/push，也不宣称 G2 全阶段完成或 G3 准入。回滚仅移除 PR4 新增文件及两段追加文档，保留所有前序资产和历史运行。

## 本轮授权后的完整回归

授权来源为管理员直接回复“批准本次完整 pytest”，范围仅本轮完整测试。
实际命令（cwd 为仓库根目录，沙箱外执行）：

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -o faulthandler_timeout=120 --basetemp=.tmp/g2-pr4-full-approved --junitxml=.tmp/g2-pr4-evidence/full-approved.xml
```

- 开始：2026-10-24T18:37:03.436368+00:00；结束：2026-10-24T18:46:26.940657+00:00；耗时 563.50 秒。
- 实际结果：839 passed / 1 skipped；failures=0、errors=0；exit code 0。
- 日志 SHA256：`d4ab9549048a297abd175d9fac7269ef89d892710eb4bce5cc01c453c4756a69`。
- JUnit SHA256：`5450e06a11929607150375f94eee6b01e38e8c50d613cd7d987836e0a828c46a`。
- 精确 argv/cwd/时间/退出码：`.tmp/g2-pr4-evidence/full-approved.command.json`。
- 保留本轮授权记录 `full-authorization.json`；本次未安装依赖、调用模型/外网、迁移生产 DB 或执行 Git 提交/推送。

平台跳过（原有测试行为，未削弱断言）：

- `tests.evals.test_provenance_and_rights.test_symlink_outside_bundle_rejected_if_supported`：symlink creation unavailable: 1314。

原始 pytest 警告与完整摘要保留在日志末尾；没有为隐藏警告调整依赖或测试。完整运行后 PR4 的 47 个指纹和前序 406 个受控文件再次核对，仅两份文档追加说明，G1 pin 保持不变。
