# G1-PR3 实现与验收记录

> 本文是 pr3-replay-v1 的历史验收记录。2026-10-21 独立复审发现预测 loader
> 缺少全局 split 隔离检查；v1 的技术通过不能覆盖该 P1 缺口。修复后的当前 revision、
> pin 和重新验收见 [PR3_SPLIT_REVIEW_FIX.md](PR3_SPLIT_REVIEW_FIX.md)。本文其余历史证据保留。

日期：2026-10-20（Asia/Shanghai）。

**状态：PR3 技术 DoD 通过；批准后的单进程全量为 315 passed / 1 skipped / 1 warning。**
此前两次单进程全量被同一个旧 provider 测试阻断，历史失败记录完整保留。
用户随后明确批准仅扩展 `tests/test_providers.py`：已应用预先审阅的事件同步补丁，
保留所有原断言，不修改旧业务代码。目标用例及未加观察器的单进程全量均重新通过。
PR2 人工初标、手册真人试用、独立复审和 G1-a 人工门槛仍未完成；本记录不是 G1-a 验收。

## 1. 基点、冻结与保全

- 起始与结束 HEAD：`8778c029fcd318c79eada0a7bdd64e514e59a98f`；起始工作区干净。
- PR3 是未暂存、未提交的工作区改动；上面的 HEAD 不包含本轮实现。没有 commit/push。
- 输入 revision：`pr3-replay-v1`；Schema：`g1-pr3-1`；annotation version 仍为 `synthetic-fixture-v1`。
- 外部固定 Manifest SHA-256：`076f8f524f716d63cc4caa0bd739560a5f6e613ede8c5363ce42dd72a9f43049`。
- **70 个受控输入、19 个 G1 测试源码**的匹配指纹在 `.local/evals/g1/pr3/frozen-inputs.json`。
- 批准后 25 个测试源码的运行前后匹配指纹、原断言保全证明在 `approved-sync/inputs.json`；旧测试新 SHA：
  `6ee227c1b78ec37c8b34699aa9b4541bc4462a688abf5d4c2238907ca386a024`。
- PR2 的 58 个受控输入先逐项校验，完整包保存在 `.local/evals/g1/pr3/pr2-dev01-v3/`；
  其原 Manifest SHA 为 `703662593c047a50675b2ea4d2b19d941df6233448f62fb32edf2552241229e7`。
- 全部 **22 个既有 JSONL 和 17 份既有 Schema 字节不变**。DEV-01 三个人工文件仍为空。
- 原 `search()`、`tokenize()` AST 不变；归档文章、迁移溯源、依赖锁和旧业务源码不变。
- 六个旧测试文件中仅 `tests/test_providers.py` 获批修改同步逻辑；该文件其他函数 AST 和目标用例所有原断言不变。
- `.gitignore` 和 `/dev-diaries/` 规则不变，日记不在索引；无暂存操作。详细核验在 `preservation.json`。
- 冻结后没有再修改受控源码、配置、数据及 19 个 G1 测试。获批的旧测试同步变更另行记录，
  不影响数据集 Manifest pin。本报告不属于算法输入，避免 Manifest 自引用。
- 无业务数据库访问或迁移；旧回归只用临时库、内存库与 mock。T25=`N/A`。
- 无公网抓取、在线 LLM、依赖安装、前端源码修改、训练或 PR4/PR5 开发。

## 2. 变更与接口

| 子系统 | 文件与用途 |
|---|---|
| 预测装载 | `loader.py`：外部 pin、预测 role 白名单、路径/哈希/权利/版本检查；先元数据选取再验证正文；重算可见列表并拒绝冻结快照不一致 |
| 基线 | `baselines.py`：`RankerProtocol.rank(context, candidates)`、固定 persona query、B0/B1/B2-predicted；全候选评分，最终排序前无 Top8/正分过滤 |
| 聚合 | `grouping.py`：非空 URL+SHA、可见上游边、保守 complete-link 文本规则；稳定组 ID、代表版本、最大 BM25 与独立性说明 |
| Oracle | `oracle.py`：只有显式 oracle/评测路径读取参考事件；与可见候选求交，未映射候选保留 singleton，不传递未来正文或事件状态 |
| 运行与事后评测 | `replay.py` 保留 dry-run，新增四算法模式；`evaluate.py` 独立完整校验后计算 Recall@5/nDCG@5 和分组诊断，不回写预测 |
| 契约 | `contracts.py` 新增 ReplayContext、BaselineConfig、PredictedEventGroup、RankedItem 及四份派生 Schema；旧实体结构保持不变 |
| 纯评分内核 | `backend/cfaw_news/retrieval.py` 仅新增 `score_all(query, articles)`，复用既有 BM25 公式；排序词项保证跨进程确定性，零分也返回 |
| 配置/验证/文档 | 新增 `manifests/baseline_config.json`，更新新 revision 的 Manifest/来源登记头；完整验证器增加配置类型校验；更新包 README、字典、数据卡及根 README |
| 测试 | 新增七个 PR3 测试文件、39 个用例；测试副本 rehash 增加 config SHA；Schema 数改为 21；PR2 help 断言适配新模式，继续拒绝 dry-run+algo |

用户批准的旧测试同步补丁使用 threading.Event：mock 先发出开始信号，主测试完成目标编辑后
才释放 mock 返回；等待上限为 5 秒且 PATCH 后 finally 释放，不再依赖 150ms 调度窗口。
所有旧业务断言原样保留，未跳过、放宽或改写结果。

PR2 的审计测试允许读取当前包的 Python 代码，以支持延迟导入；仍限制数据读取、写入、
网络和业务模块。新增预测进程审计单独证明仅复用 `cfaw_news.retrieval`，不导入完整验证器、
oracle、业务设置/数据库/HTTP 模块，不读取参考答案或敏感文件。

普通预测的受信装载会读取/哈希共享 JSONL 原始字节，但不会把未来正文送入验证投影、
分词、BM25 语料统计或聚合。ranker 仅接收安全上下文和 CandidateDocumentVersion。
family/split 只用于装载与切分；人工事件、关系、Claim、Gold、初标/仲裁不进入普通预测。
历史按同轨迹的先前 delivery 引用限定；未来曝光过滤，fixture 的参考事件目标剔除，不改 knowledge_known。

## 3. 基线规则与实际输出

- B0：`available_at` 倒序、版本 ID 升序；score 为 null，时间排序信号显式保留。
- B1：兴趣＋目标＋硬约束生成固定 query；标题计两次，加可见摘录/段落，复用 k1=1.2、b=.75，分数保留五位；同分按 ID。
- B2-predicted：先在同一完整语料评分，再去重；组分为 max，代表版本同分按 ID。
  文本 token-set Jaccard：正文 ≥.95、标题 ≥.80、正文至少 12 个不同 token；跨组所有文档对都必须满足。
  明确重复/转载记 not_independent，其他情况 unknown；不凭不同域名声称独立证实。
- B2-oracle：参考组仅作 synthetic diagnostic；算法、目录、预测行、组 ID、评测均显式 oracle。
  不是可部署方法，也不是独立人工测得的真实上界。
- 所有预测先完整排序；只在事后计算固定 @5。PR4 阅读秒数截断、B3/B4 与回访指标未实施。
- 每次运行产生 `input_snapshot.json`、`baseline_config.json`、`predictions.jsonl`、`run_metadata.json`。
  动态 UTC/耗时仅在 metadata；记录 Git、Python、依赖锁、源码/评分内核、配置及输入输出 SHA。
  普通运行明确 `validation_scope=prediction_inputs`、`full_dataset_validated=false`；模型调用数与 tokens 为 0。

DEV-01 主项数量（B0/B1 为文章卡，B2 为预测组）如下，四算法每步候选与内容 SHA 完全相同：

| step | 候选 | B0 | B1 | B2-predicted | B2-oracle |
|---|---:|---:|---:|---:|---:|
| D0 | 1 | 1 | 1 | 1 | 1 |
| D1 | 2 | 2 | 2 | 1 | 1 |
| D3 | 4 | 4 | 4 | 1 | 1 |
| D4 | 5 | 5 | 5 | 2 | 1 |
| D5 | 5 | 5 | 5 | 2 | 1 |
| D8 | 6 | 6 | 6 | 3 | 2 |

D8 预测版把有限独立测量 e:1 保守保留为另一组，主题公告 f:1 不与发布组混并。
事后参考比较为 TP=6、TN=5、FP=0、FN=4，15 个可比文档对，pair error=4/15；
漏合并是 e:1 与发布组四个成员的关系。此处不以改金标或调阈值隐藏误例。
这仅是一个合成开发轨迹的诊断，不能证明算法增益或自然分布性能。

DEV-01 relevance Gold 为空：Recall/nDCG 均为 null，原因 `gold_not_available`。
PR1 三条 pending fixture 记录返回 `gold_pending_or_unresolved`，不作已完成标注的分数。
公式单测使用明确合成的临时标签。重复卡位仍占位置但不重复获取 gain；每卡只按代表版本计一个事件，
错误合并不一次赚取多个事件收益。未映射事件、分子/分母及空分母原因均保留。

四算法各两次的预测、输入/配置快照、指标和诊断逐字节相同；不同 PYTHONHASHSEED 的 CLI 测试也通过。
dry-run 两次全部字节一致，六步 packet 与 PR2 旧导出逐字节一致。
完整运行与命令清单在 `.local/evals/g1/pr3/reproduction.json`；大批中间输出仅保留本地。

## 4. 测试结果与未通过项

| 检查 | 结果 |
|---|---|
| **批准后单进程全量（当前）** | **315 passed / 1 skipped / 1 warning，316 项，0 failures/errors** |
| 批准后实际旧用例单独复跑 | 1 passed / 1 warning |
| 先写测试的红灯 | 第一批 22 failed，CLI/评测第二批 13 failed，均为缺实现/入口；XML 已保留 |
| 相关验证 | 38 passed，含 PR2 dry-run 审计、预测隔离和公式负例 |
| 冻结后的 G1 专项 | **190 passed / 1 skipped**，191 项，0 failures/errors |
| 历史：批准前全量第一次 | **314 passed / 1 failed / 1 skipped / 1 warning**，316 项 |
| 历史：批准前全量确认 | **314 passed / 1 failed / 1 skipped / 1 warning**，同一个失败，未隐藏/覆盖前次 XML |
| 旧用例单独原样复跑 | 1 passed / 1 warning |
| 旧六文件隔离诊断 | 125 passed / 1 warning；临时 observer 只记录目标请求时间，不改断言 |
| 历史：未应用候选补丁探针 | 临时副本中 1 passed / 1 warning；实际旧测试文件未改，不计入已交付全量通过 |
| Ruff / pip check / Schema / strict Manifest | 全部通过；21 份 Schema 与 70 个受控输入匹配 |
| 旧 seed-sanity | Recall@8=1、MRR@8=.8333333333333334、nDCG@8=.8645724197652078；只作烟测 |
| 前端 offline build | TypeScript/Vite 通过；只生成忽略的 dist，无前端源码或依赖修改 |
| 保全与 diff | 22 个旧 JSONL、17 份旧 Schema、旧检索 AST、范围外文件均不变；git diff --check 通过 |

唯一 skip 是 Windows 原生 symlink 权限；不依赖该权限的 resolved-path escape 防线通过。
warning 是既有 Starlette/httpx 弃用提示，没有安装新库规避。

受限环境的首次全量在 Windows `socket._fallback_socketpair -> asyncio -> TestClient` 初始化挂起，
30 秒堆栈已识别，使用 Ctrl+C 终止；随后在允许本地 socket 初始化的环境重跑。
这一次环境中断不算业务测试失败，也不算通过。

此前阻断是 `tests/test_providers.py::test_edited_goal_cannot_publish_but_retains_returned_usage`：
全量两次观察到 completed，而断言期待 stale。该测试以 150ms 延迟构造编辑窗口，
存在调度/顺序敏感性嫌疑，但**未证明这是唯一根因**。原样单例及旧 125 项隔离通过不能覆盖全量失败。
临时观察器记录了隔离通过时 PATCH 在返回之前完成；没有把该通过时序冒充失败时序证据。

首次执行按 G1 计划 §1.3 停在旧测试范围之外，准备了 `.local/evals/g1/pr3/legacy-test-sync.patch`
及临时副本探针。用户随后明确批准该补丁及全量重跑，当前已按原补丁应用到实际旧测试。
批准前报告和结果保存在 `approved-sync/PR3_ACCEPTANCE.blocked.md`、
`approved-sync/acceptance-results.blocked.json`；两次失败 XML 不覆盖。
批准后未加任何观察器的目标用例及完整 316 项均通过；这不构成对其他既有测试时序的稳定性保证。

## 5. 实际命令与复现

项目根目录 `D:/agent_project/cfaw-news`，使用既有 venv。所有运行输出目录必须全新：

```powershell
$PY = '.\.venv\Scripts\python.exe'
$ROOT = 'evals/intelligence_v1'
$PIN = '076f8f524f716d63cc4caa0bd739560a5f6e613ede8c5363ce42dd72a9f43049'
& $PY -m ruff check backend tests evals
& $PY -m pip check
& $PY -B -m evals.intelligence_v1.contracts --check-schemas
& $PY -B -m evals.intelligence_v1.validate --manifest "$ROOT/manifests/dataset_manifest.json" --strict
& $PY -B evals/run_baseline.py --output .local/evals/g1/pr3/seed-sanity.json
& $PY -B -m pytest tests/evals -q --basetemp=.tmp/g1-pr3-frozen-evals --junitxml=.local/evals/g1/pr3/pytest-evals-frozen.xml
& $PY -B -m pytest tests/test_providers.py::test_edited_goal_cannot_publish_but_retains_returned_usage -q --basetemp=.tmp/g1-pr3-approved-sync-target --junitxml=.local/evals/g1/pr3/approved-sync/pytest-target.xml
& $PY -B -m pytest -q --basetemp=.tmp/g1-pr3-approved-sync-full -o faulthandler_timeout=30 --junitxml=.local/evals/g1/pr3/approved-sync/pytest-full.xml
# 以下为批准前真实失败的历史命令，不是当前 passed 结果：
& $PY -B -m pytest -q --basetemp=.tmp/g1-pr3-frozen-full-local-sockets -o faulthandler_timeout=30 --junitxml=.local/evals/g1/pr3/pytest-frozen-full.xml
& $PY -B -m pytest -q --basetemp=.tmp/g1-pr3-frozen-full-confirm -o faulthandler_timeout=30 --junitxml=.local/evals/g1/pr3/pytest-frozen-full-confirm.xml
& $PY -B -m pytest tests/test_providers.py::test_edited_goal_cannot_publish_but_retains_returned_usage -q --basetemp=.tmp/g1-pr3-legacy-race-probe --junitxml=.local/evals/g1/pr3/pytest-legacy-race-probe.xml
foreach ($algo in @('b0', 'b1', 'b2-predicted', 'b2-oracle')) {
  foreach ($rep in @('a', 'b')) {
    & $PY -B -m evals.intelligence_v1.replay --manifest "$ROOT/manifests/dataset_manifest.json" --manifest-sha256 $PIN --split dev --algo $algo --config "$ROOT/manifests/baseline_config.json" --out ".local/evals/g1/pr3/$algo-$rep"
    & $PY -B -m evals.intelligence_v1.evaluate --manifest "$ROOT/manifests/dataset_manifest.json" --manifest-sha256 $PIN --run ".local/evals/g1/pr3/$algo-$rep" --out ".local/evals/g1/pr3/$algo-$rep-evaluation"
  }
}
git diff --check
# frontend 工作目录：
npm.cmd --offline run build
```

以上输出已存在，重跑必须换新的 --out/basetemp/junitxml，不能覆盖旧证据。
旧六文件诊断实际由忽略的 `diagnose_legacy.py` 调用同一 pytest 入口，加入只观察目标请求的 hook；
该本地诊断不是运行器依赖，不是已提交的测试修复。环境/完整命令/原始输出在本地 checks/、
environment.json、acceptance-results.json、legacy-timing.json 与 reproduction.json。

| 冻结测试证据 | SHA-256 |
|---|---|
| **批准后单进程全量 JUnit（当前）** | `43608309bf1c9bb9c4da01a0659dab6ee9643419a4026498ab854979816b87b8` |
| G1 JUnit | `f158fb6a6269df730e888cb53b702d46a7ae3ec6112c991cf5a974f050607300` |
| 全量首次失败 JUnit | `937108d6ed2404657d479da6f27ad681f411f45da7032ae05b88e040135372c0` |
| 全量确认失败 JUnit | `1dcc36bde450d7b5237de1734ea74cbc812bc1364eca70dd493344f9eddcc71f` |
| 旧 125 项隔离 JUnit | `bdf0956ef3cd67c5d55f9be8faa109bf7b3502f5fa0465a9b526412bf3cad142` |

## 6. DoD 与停止状态

| 门槛 | 状态 |
|---|---|
| 四算法可运行、统一可见候选、B1 不裁 Top8/零分 | PASS |
| 普通预测不读参考答案；Oracle 例外显式标识 | PASS |
| T06/T07/T15/T18、PR3 的 T24、GROUP01/ORACLE01 与时间回归 | PASS（限本轮合成开发数据） |
| canonical 预测/快照/指标双次字节相同，动态字段仅在 metadata | PASS |
| 输入、排名、分数组件、组构成、未映射与错误诊断留痕 | PASS |
| 必需静态/依赖/seed/构建与 G1 专项 | PASS（skip 单列） |
| 单进程全量 pytest 全绿 | PASS：批准同步补丁后 315 passed / 1 skipped |
| 数据/资产/旧契约保全；无真实迁移 | PASS；T25=N/A |
| 真人标注、语义支持、独立复审、G1-a | PENDING，不属于本 PR 的完成声明 |

三个主要剩余风险：①真人标注与语义支持尚未完成；②保守规则漏合并独立证据，不能以 oracle 替代预测能力；
③全部材料为合成开发数据，不能主张真实新闻覆盖、算法增益或泛化。旧测试同步阻断已通过获批补丁解除。

停止在本 PR：批准的旧测试同步修复和单进程全量回归已完成，PR3 技术 DoD 通过。
未进入 PR4/PR5，未修改业务库或旧业务契约，未提交/推送。独立复审及人工环节仍需后续真实完成。
