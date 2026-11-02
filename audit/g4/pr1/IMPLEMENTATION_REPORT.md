# G4-PR1 实施报告

日期：2026-11-02（Asia/Shanghai）。实施前及交付 HEAD：
`2655f10cf20c647bdbfd1b69a000847471b2c5a3`，分支 `main`。

**本轮 PR1 离线契约/可行性工程自验收 PASS，等待独立只读审查。**
**真实 runtime G3 adapter / 生产简报发布仍为 BLOCKED，不是本 PR1 的成功能力。**
没有签发 G3 整体管理员最终验收、G4 Beta 或后续 PR 授权。

**审查修订，2026-11-02：上述 PASS 是原 PR1 的历史自验收，不足以关闭随后发现的
文档链 P1 和覆盖诊断 P2。当前修复与重新验证见 REVIEW_FIXES.md；原 baseline、
release、日志和 Schema v1 保留。以下 namespace 说明已按审查事实更正。**

## 1. 范围与授权

当前用户明确授权“开始实施 CFAW News G4-PR1”“本轮只做 PR1”。完成：

1. `audit/G4_ENTRY_REUSE_AUDIT.md` 与本轮实际证据 `audit/G4_BASELINE.json`。
2. `docs/adr/G4_RUNTIME_LOCAL_V1.md`，包含接口、失败降级、安全边界及 PR2–PR6
   精确文件/测试依赖，不创建整套生产服务。
3. `evals/intelligence_g4/` 的严格 document/runtime/config/status/briefing/interaction
   契约、10 个派生 Schema、固定错误码和纯函数回放。
4. 原生 G2 分组/证据/规则项/规则表达的有界 vertical slice；G3 runtime 未注册时
   返回明确阻断，不制造 accepted_g2 parent、trusted pin 或 runtime BriefingPlan。
5. 隔离加载已有外部 pinned G3 合成 probe，验证原 B4/planner 可用，并验证不能将
   该 plan 注入 runtime 结果。不是新的 RSS→G3 全链成功证明。

既有两个未跟踪 G4 文档保留原样。请求的 docs/plans/G4_IMPLEMENTATION_PLAN.md
不存在；本轮使用实际 docs/G4_IMPLEMENTATION_PLAN.md，不擅自迁移或覆盖。
原 G3 handoff/README/acceptance 中的 pending/false 状态保持原样；前置聊天审计的
技术复核与本轮 PR1 授权单独记录，不拿 commit 标题替代最终验收。

## 2. 文件触达

| 文件 | 改动 |
|---|---|
| evals/intelligence_g4/contracts.py | 严格版本化模型、权利/来源/时间/不可变版本/完整来源覆盖校验、真实与合成隔离、B4 固定、显式预算 profile |
| evals/intelligence_g4/slice.py | 外部输入 pin、canonical wire、资源限制、正式 native G2 pure API 回放、严格结果重算、明确非发布状态和离线 CLI |
| evals/intelligence_g4/schema.py、schema/v1/ | 实际 Schema 字节及完整集合比较；显式导出，导入无写入 |
| evals/intelligence_g4/tests/、manifests/pr1_required_tests.json | 55 个新测试、4 个测试源码 pin 与实际收集节点清单 |
| evals/intelligence_g4/README.md | 离线运行方法、独立测试轨道及能力限制 |
| audit/G4_ENTRY_REUSE_AUDIT.md、docs/adr/G4_RUNTIME_LOCAL_V1.md | 准入、复用、硬门槛与下一 PR 的依赖和 DoD |
| audit/g4/pr1/run_checks.py、finalize.py | 实际进程日志/退出码记录、工件与控制面核验、基线生成 |
| audit/G4_BASELINE.json、audit/g4/pr1/RELEASE_MANIFEST.json | 本轮命令、结果、源码/配置/输出 pins 与交付摘要 |

未修改 backend、frontend、数据库/迁移、CI、旧 tests 或 G1–G3 文件。
初始 903 个受保护文件（901 个 tracked + 两个已有未跟踪计划文件）逐字节不变。
没有 Git 写入、真实用户数据库、实际采集、真实模型/付费 API、dev-diaries 读取/上传。

## 3. 验证矩阵与本轮实际结果

| 门槛 | 本轮实际执行 | 状态 |
|---|---|---|
| 新 G4 契约/slice | 显式 pytest，55 passed、0 skipped | PASS |
| 原仓完整回归 | 注册 pytest_runner --mode full，1753 passed、1 skipped、1 warning | PASS |
| 原仓库存/JUnit | 1754 个完整节点、冻结 required-test/source pins 和唯一 skip 豁免校验 | PASS |
| 注册 pytest 控制面 | collect/full 的 before/after、精确 argv、加载插件来源核验 | PASS |
| G4 收集/源码 | 独立 collect 55 节点与新 required manifest、4 个测试源码逐项一致 | PASS |
| Ruff | backend/tests/evals 与本轮 audit 工具 | PASS |
| G4 Schema | 10 个完整派生文件；正确/篡改/额外集合回归 | PASS |
| lexical baseline | evals/run_baseline.py，内存隔离库、非模型归档烟测 | PASS |
| 前端兼容构建 | npm --offline run build，输出仅在 .tmp | PASS；不是浏览器 E2E |
| 原文件保全 | 903 个既有文件的 SHA256 比较，HEAD/branch 未变化 | PASS |
| 实际 runtime G3 / DB / API / UI / 浏览器 / 真实来源 / 远程 CI | 本轮范围外或接口尚未注册 | BLOCKED / NOT_EVALUATED，未冒充 PASS |

原仓完整回归实际 pytest 耗时 1096.97 秒；进程连同启动/控制检查耗时
1102.689 秒。唯一 skip 是既有 Windows symlink 权限 1314；G3 无跳过。
原 tests 的完整回归包括 G3 的 630 项与事实签名 59 项，不把它们重复加算成独立样本。
弃用警告来自既有 FastAPI/Starlette TestClient 与 httpx 组合。

新测试显式放在 evals/intelligence_g4/tests/，因为冻结 G3 test_sources 精确绑定
tests/ 全部 Python 文件。没有通过删除/过滤旧节点、改旧 pin 或加 skip 来接受新测试。
两条测试轨道均实际执行并保存 JUnit；普通默认 pytest 不自动发现 G4 新轨道，
README 和 ADR 已明确要求显式执行，未来 CI 接入另行审查。

### 新测试重点

- 接受规范 synthetic 开发输入；拒绝 accepted_g2 parent、Gold、额外字段和错误 pin。
- future document/persona/coverage 在特征计算前被拒绝，且早于坏正文 hash 的解析。
- real/synthetic、source policy、Persona、来源类型与 provenance 一致；未知 rights
  正文拒绝，虚构 example.com 元数据测试不被称为真实来源验证。
- hash、重复 ID、不可变 document/Persona 版本、可解析前驱和顺序回放。
- 显式 Budget profile：省略 budget 或空 budget 对象不能继承 G3 的 70/30 默认；
  P1 和未注册资源/事实策略拒绝。
- native G2 真实 pure APIs、规则 presentation 与原 item 绑定；空池/hold 保留
  coverage、Archive 和原因；没有未经资格核验的 display_order 或 plan。
- 输入/结果重放确定；篡改事实、Archive、状态、hash 或插入离线 G3 plan 均拒绝。
- 单独的 effects guard 禁止 socket/httpx/真实 DB/provider/G3 runtime 调用。
- Interaction 的 opened 保持 opened；rendered/source、反馈/撤销字段和错误形状拒绝。
  没有声称完成持久化、写入授权或用户知识学习。

## 4. 四组实际 CLI 探针

输入由测试作者准备并独立保存 exact-byte pin；slice 不自行替换可信 pin。
最终使用当前代码重新执行，全部 manifest 文件哈希及结果重算通过。

| 输入 | 实际退出码/结果 | 说明 |
|---|---|---|
| compliant（两步合成规则输入） | 0 / raw_news_only / G4_G3_RUNTIME_ADAPTER_REQUIRED | native G2 通过，plan=null、publishable=false |
| hold-only | 0 / insufficient_evidence / G4_EVIDENCE_NOT_ELIGIBLE | hold 保留，未假造简报 |
| future | 1 / G4_FUTURE_INPUT | 预期拒绝，无结果目录 |
| unknown-rights 正文 | 1 / G4_RIGHTS_INVALID，native RIGHTS_UNKNOWN_FULLTEXT | 预期拒绝，无结果目录 |

Compliant 输出 manifest pin：
`5b98a9ef78c7db53da2a9886126e45d73ba9ce73df6194f3de1ee00b76eb1a94`。
Hold-only 输出 manifest pin：
`1b286da087e90e64b24e87e071fabcf8fa3700fea408a51ddc4805949ff66ace`。
配置 exact-byte pin、输入 pin、完整 argv/环境/日志 hash 均在 G4_BASELINE.json。
事实 policy 仍为 g3-grounded-fact-signature-v2，SHA256：
`70565148fe436fa823ef6a4063cbba7abb4c994cc34f19dc44bdc2451e367450`。

## 5. 保留的失败、修复及受限运行

| 运行 | 实际结果 | 处置 |
|---|---|---|
| focused-01 | 18 passed / 29 failed | Pydantic before-validator 破坏严格 JSON tuple 路径；将预检置于正式 wire parser，保留严格验证 |
| focused-02 | 28 passed / 19 failed | synthetic URI 与原生 G2 相对 provenance 规则不兼容；改用原生允许的作者文件指针，没有放宽 G2 |
| focused-03 | 46 passed / 1 failed | 不可变对象先报 hash 错误；修正测试构造，使缺失前驱反例单独命中引用诊断 |
| focused-04 / focused-final | 52 / 54 passed | 新增坏形状和 Persona/配置回归后的实际运行 |
| focused-release | 55 passed | 收尾新增空 budget 对象不得隐式选择 profile 的反例 |
| full（受限沙箱） | socketpair 阻塞，主动停止任务子进程；实际子进程退出 4294967295 | 保留 faulthandler 堆栈、346.37 秒记录和日志；不称为 pytest 通过，也未加 skip |
| full-loopback | 完整注册回归 PASS | 在允许 Windows 本机回环的执行环境以同 runner/临时库/mock 重跑；没有外部新闻或模型调用 |

以上失败记录不删除、不覆盖、不重新标成成功。后续运行是独立命令记录。
最初 G4 source/profile 校正不影响旧应用代码；最终 G4 源码另经 focused-release
与 schema-release 验证，旧回归覆盖的 903 个文件从实施前到交付均未改变。

## 6. 剩余阻断与交接

1. runtime G3 adapter 与跨请求 registry/状态续接尚未注册。native namespace 由
   dataset/timeline/strategy/config revision 等原生字段派生，input pin 另绑定输入
   完整性与状态链；预算 profile 改变能改变 input pin 而保持 namespace/event/
   snapshot ID 不变。相同身份不证明可安全续接，PR3 必须分别实现并验证这些边界。
2. 真实 RSS capture、rights registry、生产依赖打包、DB migration、持久化历史、
   API/前端都未实施。PR2–PR6 精确触达和测试依赖见 ADR 第 7 节。
3. Interaction 仅有 wire 校验；实际 target/主体/版本/撤销、幂等与 trusted head
   需要 PR4。SQLite 同库 head 不能独自检测整库连 head 一起回滚。
4. 保留 B4；P1 无稳定收益证据。预算未校准，保护项存在已知贪心遗漏，不能承诺最优。
5. AI/合成开发回归不等于独立研究、真人效用、真实模型/来源泛化或生产就绪。

本轮到此停止。下一步为 PR1 独立只读审查；不自动开始 PR2，不 commit/push。
