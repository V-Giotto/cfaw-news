# G1-PR5：DEV-01～05 AI 批次重建与开发验收

> 发布时间说明（2026-10-23）：下文 HEAD、“未 stage/commit/push”及未联网均记录验收完成时的状态。后续经项目所有者授权的 GitHub 发布以仓库提交记录为准，不改变下述冻结 pin、测试结果或结论边界。开发日记仅保存在被忽略的本地 dev-diaries/。

2026-10-23，Asia/Shanghai。默认 profile：**ai_development**。
当前结果：**开发验收 PASS；技术 PASS；G2 离线准入 true**。没有自动启动 G2。
真人研究为可选路径，不需要用户补交真人身份、手工录入、收包时间或第二人。

当前冻结：`pr5-five-trajectories-v10-ai-development-r3 / g1-pr5-6`。

Manifest SHA-256：`5608f6c9f20d283f9274308fa98a277c535eb0d8d828fd0d863d6e1faafde06f`。

Git HEAD 保持 `e1ce349895b06dc57b40b5c5e1f75b50caf411ec`；交付仍未 stage、commit 或 push。

## 当前批次与清理范围

依据已更新的 AGENTS.md 与 `docs/plans/G1_AI_DEVELOPMENT_RULES.md`，重新创建单 AI 初稿、证据复核、修订链及开发期望：

- 五条主轨迹、26 个时点、35 份原始合成文档版本，47 个事件×时点判断。
- 活跃复核稿含234条claim、90个关系；四维、graded relevance、tier、material_change、理由、引用和scope完整。
- `labels/ai_development/draft.json` 为本批 AI 初稿，`review.json` 为活跃复核稿，`batch.json` 绑定两者 SHA、真实生成区间、输入 manifest 和 AI 规则。
- `review_r0.json` / `review_r1.json` 及 `revisions*.json` 保留旧 AI 判断和精确修订；旧稿不再参与当前分母。
- `labels/expectations.jsonl` 的47条主参照由活跃 AI 复核投影，使用 fixture_expectations / synthetic-fixture；8条辅助 fixture 另列。没有导入真人 gold。
- 既有参考事件 ID 只用于评测侧对齐；本 AI 已见过参考材料和轨迹全貌，明确非盲标、非独立验证。没有伪造A/B、争议、真人冻结或Cohen κ。模型与会话精确标识无法取得，写unknown。

旧 `.local/evals/g1/dev01-human-pilot-20261022`、`dev02-05`、旧人工工作表及修正脚本已退出当前入口，完整保留在 `.local/evals/g1/pr5/ai-restart-20261023/retired-local/`。
旧 DEV-02～05 四套 authored expectations 移至 `retired-expectations/`，不与新47条重复计数；原始版本、旧冻结代码/测试和历史报告保留以便复现。
81个其余JSONL保持原字节，旧服务/API/Goal/Run/Decision/Schedule契约不变。
当前本地入口为 `.local/evals/g1/ACTIVE_BATCH.json` 与 `ai-development-20261023/`；旧HUMAN_TODO仅属历史可选研究，不是当前待办。

## 生成、复核及纠错记录

本助手离线编写，不使用外部模型API。材料仍是明确虚构的synthetic；执行者ai与材料来源分开。
初稿曾将“前一离线step已经出现”误判为“Persona已知”，复核中也发现公告scope过于概括。这些错误保留在旧稿，没有回写成正确初稿。

1. 首轮重复参照：43 passed / 1 failed发现旧四套期望与新主期望重复。旧文件归档，新增重复条目拒绝断言，不静默dict去重。
2. scope修订：208条公告类claim逐项补版本、平台、任务、条件、样本、次数、基线，未知/不适用明确记录；该轮不改分。最终复核scope缺字段会被拒绝。
3. 独立审查r1发现P1：D8安全更正等没有送达/确认，却被归档为用户已知，导致重要漏报分母消失。按实际knowledge_known为空及included-only历史重新裁定，恢复未读重要增量focus/grade3和非零个人novelty；不把world-level no_change/insufficient改成人已知。
4. 旧D8测试被放宽是不合适的，已恢复，并补未确认、确有版本知识、匹配ack卡片、旧版本不覆盖更正的正反例。程序不会把included/rendered/opened或另一个卡片的ack当理解。
5. 独立审查r1发现P2：输入快照只留1项、0项预测材料并更新hash仍PASS。现按全部允许预测材料的path/role/SHA精确比较，拒绝缺域、改role、重复，code/schema因版本变化明确排除。

标注修订依据Persona、当时证据、曝光与V3量表；没有读取算法比较得分来调整分数。AI稿的原文及before/after hash、真实修订时间均保留。参考曝光不隐瞒，也不冒充独立测量。
两项问题最初红灯2 failed；知识门禁进一步4 failed；当前相关测试为71 passed。单次测试运行有重叠，不累加为研究样本。

## 实际检查与复现

证据目录：`.local/evals/g1/pr5/ai-restart-20261023/r3/`。以下以实际工件为准：

| 检查 | 结果 |
|---|---|
| Ruff / schema / strict manifest / pip check / seed sanity / frontend build / diff | 七项实际命令均exit0，日志及SHA已核验 |
| 全量pytest（含原125项旧业务） | 551 passed / 1 skipped；552 个实际节点 |
| G1专项pytest | 426 passed / 1 skipped；427 个实际节点 |
| 必需节点和Txx | 552个full、427个G1精确节点/源码指纹；适用T01–T24/T26，T25=N/A |
| 完整矩阵 | 200预测 / 400评测 / 655 CLI；1400确定性工件一致 |
| 排名输入保留 | 600个预测/input/config与v4逐字一致；81个其余JSONL保留 |
| 默认AI验收 | PASS；exit0，g1a_passed=true，g2_eligible=true |
| 可选真人研究 | NOT_MET；不阻塞默认AI开发profile |
| 代码问题闭环独立复审 | 返回已保存，见review-code-closure.json |
| 完整矩阵和full工件独立核验 | 已通过，无新增P0/P1/P2；见review-completed-matrix-and-full.json |
| 最终保存工件独立核验 | PASS；无新增P0/P1/P2，见review-final-artifacts.json与review-final-summary.json |

唯一允许的skip为Windows原生symlink权限1314，明确豁免且不算passed；Starlette/httpx弃用warning单列。
`checks/*.command.json` 保存实际argv、退出码、环境、日志/JUnit SHA。完整节点来自pytest collection，不从待审JUnit补造。
最终矩阵使用`matrix-final/`：5轨迹×6算法×3预算(180/420/900)×2 hash seeds(1/719)，另做B3/420秒/3和14天半衰期；每次分别评估gold和synthetic-fixture，oracle单列。
未标注human gold指标仍null；AI主参照与辅助集、重复运行次数、family分母和缺失支持证据分别报告。baseline只做离线词法/分组排序，没有算法必须超过B1的通过条件。

本批非oracle配置的重要事件预算召回未记录漏报，逐步分母与结果保存在checks/verified-evidence.json；固定合成集通过不代表独立泛化。
事件命中不能替代证据完整：最终matrix-final中B3/180秒/7天半衰期的DEV-04 D8虽然ImportantEventRecall为1/1，预算内仍未呈现d04:test:1；比较报告保留此证据缺失和归并漏配，不把召回率当语义支持通过。

独立工程复审由已授权的“审查 G1”会话执行，属于另一会话的AI代码/工件审查，不是独立标注或真人语义验证。
代码/data修复闭环turn为`01a16825-ad18-7d90-b8e3-b14120a2f53c`；完整矩阵/full核验turn为`01a1685a-6663-7cd3-bafd-01ea7a454038`。
最终G1/checks/双profile验收/截断负例核验turn为`01a16864-c7aa-76d1-8cda-2ba5cf732591`，结论PASS；未发现新增P0/P1/P2。

```powershell
Set-Location D:\agent_project\cfaw-news
& .\.venv\Scripts\python.exe -B -m ruff check backend tests evals
& .\.venv\Scripts\python.exe -B -m evals.intelligence_v1.contracts --check-schemas
& .\.venv\Scripts\python.exe -B -m evals.intelligence_v1.validate --manifest evals/intelligence_v1/manifests/dataset_manifest.json --strict
& .\.venv\Scripts\python.exe -B -m pip check
& .\.venv\Scripts\python.exe -B -m pytest tests/evals -q --basetemp=.tmp/ai-final-r3-evals --junitxml=<new-G1.xml>
& .\.venv\Scripts\python.exe -B -m pytest -q -o faulthandler_timeout=120 --basetemp=.tmp/ai-final-r3-full --junitxml=<new-full.xml>
& .\.venv\Scripts\python.exe -B evals/run_baseline.py --output <new-seed.json>
# frontend内：npm.cmd --offline run build
& .\.venv\Scripts\python.exe -B -m evals.intelligence_v1.ai_development --manifest evals/intelligence_v1/manifests/dataset_manifest.json --manifest-sha256 5608f6c9f20d283f9274308fa98a277c535eb0d8d828fd0d863d6e1faafde06f
& .\.venv\Scripts\python.exe -B -m evals.intelligence_v1.reproduce --manifest evals/intelligence_v1/manifests/dataset_manifest.json --manifest-sha256 5608f6c9f20d283f9274308fa98a277c535eb0d8d828fd0d863d6e1faafde06f --out <全新目录> --packets --workers 2
# acceptance分别指定--profile ai_development与human_research；实际全部参数见acceptance-commands.json。
```

复跑须使用全新输出/临时目录，不能覆盖当前证据；上述占位符按实际路径替换。旧API完整回归需要允许本地socketpair的测试环境，不访问生产库。

## 失败、豁免与结论边界

- r0因scope自查修订主动中止，原日志/部分矩阵保留，未纳入最终PASS。
- r1实际full为191 passed/349 setup errors、G1为151 passed/264 setup errors：私有运行器错误使用不存在父目录的嵌套basetemp。原失败未删除；最终使用平级短路径，不改业务/测试防线。
- r1语义/输入快照问题及修复前红灯、原AI稿、原开发标签和历史pin全部保留；r2未宣称完整运行通过。
- r3首轮矩阵因pydantic_core DLL正被其他进程占用而退出1。同一失败评测用新目录原命令重试exit0，无源码/依赖修改。首轮部分矩阵未拼接为成功；最终以全新matrix-final、workers2完整运行验证。
- 截断JUnit负例另保留篡改副本：仅留125旧+2G1，移除425个G1并更新SHA，仍须REQUIRED_TESTS_INCOMPLETE，technical/temporal/regression=BLOCKED，不因AIprofile而放宽。
- r3首轮full发生Windows原生访问异常（3221225477），没有完整JUnit；失败点单独复跑1 passed。G1在原20分钟执行上限退出124，也不计通过。保留两份原记录；最终测试采用120秒栈诊断阈值和40分钟外层上限，测试断言及完整节点要求不变，结果以实际后续工件为准。原生异常根因未确证，不宣称已修复第三方库。
- 单AI的材料语义复核与程序引用定位分开；算法输出语义支持、真实用户效果、独立留出泛化、生产库/物理磁盘故障和线上模型均未测。T25=N/A，不伪造迁移或human研究PASS。
- 保持现有业务契约、排名器和预算规则；未联网、安装依赖、迁移数据库、自动开展G2、commit或push。

所有技术硬门槛实际通过后，AI开发profile可以通过并获得G2离线开发资格。该结论不能改称真人研究验证、独立模型验证或线上生产完成。
