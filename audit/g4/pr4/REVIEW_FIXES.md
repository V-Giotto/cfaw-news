# G4-PR4 三项复审修复

2026-11-03。**PASS：三项修复的本地工程自测与源码/工件验证；独立复审 PENDING**。
不改写原 IMPLEMENTATION_REPORT、BASELINE、RELEASE_MANIFEST 或旧 Schema/测试清单。
原 PR4 自测 PASS 是历史记录，不能作为本次三项 finding 已关闭的证据。

## 入口与范围

核对 main@783f5428671457ea3f1f654b160152f653d2e9e0，工作区保留未提交的 PR3/PR4。
用户明确授权修复三个问题，后续“继续”沿用该任务。初始 1070 个文件与原 PR4 release
核验结果、五个拟改源码前像保存于 .tmp/evals/g3/g4-pr4-fix-20261102-001/entry.json、
before/。审查原始证据读取自 .tmp/evals/g3/g4-pr4-review-20261102-001/，仅作为修复前
复现，不混入本轮测试成绩。文件/测试方案见 REVIEW_FIX_PLAN.md。

仅更改 history_store.py、checkpoint.py、service.py、persistence_migrate.py、
persistence_schema.py；新增 corpus_trust.py、测试、版本化 Schema/manifest、ADR 附录
和审计工具。SQL 表布局、002 migration source/schema pin 未变；旧 backend、React、
G1/G2/G3、PR1–PR3、原 PR4 测试/验收资产及 dev-diaries ignore 均保持入口字节。
本轮不提交/推送、不联网、不读日记、不写真实用户数据库。

## P1：可信来源前缀

原 corpus_basis 只比较一次 run 的起止数据，不能发现已经接受的 v2 从来源表消失。
新 CorpusPrefix 绑定完整来源不可变行 SHA 及每个 document 的有序版本 ID、合法链尾、
source/url、last_observed_at 水位；重新校验 PR2 精确 Schema、版本内容/前驱/时序/
政策及 coverage/capture 关联。不可变集合包含 migration、policies、versions、captures、
coverage、service events。journal 不复制受限正文，只保存摘要与安全身份。

checkpoint v2 保存初始化/显式接管的来源基线；每次 append 的 body.corpus 保存当时
完整前缀与 SHA，纳入 entry→head→库外 checkpoint。读与写均要求当前集合完整延伸
全部已接受前缀，不能退水位、丢失/修改已知行或分叉。原 run basis、native 严格重算、
权利/资格、fact policy、取消与发布 CAS 仍保留。

发现来源丢失时首次返回 G4_CORPUS_PREFIX_LOST / G4_CORPUS_CHAIN_INVALID；将
recovery_required 持久化到外部 checkpoint，heads/epoch/latest 不变。之后要求
G4_CORPUS_EPOCH_ADOPTION_REQUIRED，即使精确补回来源、重启也不自动恢复 ready。
标记写失败返回 G4_CORPUS_RECOVERY_MARK_FAILED，拒绝服务，不假称磁盘故障时仍
持久化成功。来源问题不是公开 HTTP 删除漏洞。

旧 checkpoint v1 不能自动认领当前来源。停服务、备份后，用新 anchor 路径显式
adopt-restore + --acknowledge-restored-history 验证并创建新 epoch。旧 journal 缺少
corpus 时，核对所有原 hash-bound run.input 的版本、政策和 coverage；input 使用原
json_bytes 文件 SHA（含尾换行），不能用语义 digest 代替。历史证明 v2 而当前只剩 v1
时，确认本身不能绕过；应补全精确材料再接管，或显式恢复一致的完整旧备份到新路径。

本轮负例：发布 v1、v2 后，仅恢复 g4_ 表至 v1、精确恢复 Schema/triggers，保留全部
intelligence_ 历史与 checkpoint。status unavailable，新 POST 503，原 version=2 latest
指针保留，不产生 version=3；heads 不变，恢复要求被持久化。显式接管不一致来源也
拒绝；完整一致的 v1 备份可按显式恢复流程进入新 epoch。计算中来源回退同样不能发布。

## P2：请求命名空间

客户端/内部请求分别使用 client/system，身份 SHA([stream,namespace,raw_key])，
unique(stream,key) 的实际 key 为 client|raw_key / system|raw_key。公共 Key 文法不允许
管道字符；合法 run:{id}:terminal/start/publish 不再能占用内部任务收据。

旧 SHA([stream,key]) 行保留不改写：客户端同语义可重试；内部仅复用同一内部 operation
的旧收据，不把旧客户端 cancel operation 当作 run-terminal。旧冲突记录的恢复与
重启已覆盖。三个外观键的取消均返回 200，重试 deduplicated，run cancelled，服务
保持 ready；旧取消收据与新的内部终态收据可以同时存在，不触发服务级不可用。

## P2：真实计算容量

专用 ThreadPoolExecutor 与 semaphore 使用同一 max_workers。native 计算、结果重算
与发布属于同一个实际 concurrent Future；只有它真正完成才归还 permit。shield 防止
wait_for 超时/取消把底层工作伪装成完成；迟到异常被消费。超时可先记录 timed_out，
但实际工作仍占容量，后续任务只能在原 queue_limit 内等待，满队列返回 429。

关闭服务时也不提前释放 worker owner 锁；旧实际 Future 未结束，替代实例不能计算。
全部实际工作结束后才释放所有权。永久不协作线程会占住容量，不宣称能强杀线程。

本轮注入 0.08 秒限时、等待释放信号且忽略 Control 的函数：1/2 worker 下实际峰值均
等于配置，连续超时未累积超额后台计算；后续两个请求有界 queued，再请求 429。
关闭后实际任务未结束时，新实例 worker_available=false；释放信号后 owner 才释放。
原迟到结果禁止发布、取消 race 与旧快照保全测试仍通过。

## 契约与工件

新 ADR：docs/adr/G4_PERSISTENCE_REVIEW_FIX.md。原 ADR 保留，并由本附录纠正来源
可信边界与 worker 生命周期的不足。新 schema/pr4_review_fix 为 g4-pr4-contracts-v2，
20 份工件，增加 CorpusPrefix/DocumentWatermark，登记 checkpoint v2、corpus v1 和
请求域。HTTP 请求/响应字段与 OpenAPI 字节未改变，不代表存储协议仍兼容旧 checkpoint。
新的 pr4_review_required_tests.json 增量登记 23 个节点，原 293 节点及源码未动。

工件目录保留开始日期 ID 20261102；跨日后的执行记录以实际 UTC/本地时间为准。所有
测试/CLI command.json 均记录真实 argv/cwd/env/时间/退出码和 log SHA，不重命名旧日志。
当前结果与源/配置/输入/输出 pin 已保存于 REVIEW_FIX_BASELINE.json，发布工件集合由
REVIEW_FIX_RELEASE_MANIFEST.json 绑定；旧工件不改写。

## 本轮验证

统一目录 AREA=.tmp/evals/g3/g4-pr4-fix-20261102-001/；以下 AREA 是说明缩写，实际
argv 见相应 *.command.json。公共 wrapper 为 .venv/Scripts/python.exe -m
audit.g4.pr1.run_checks --out AREA --name NAME --，argv 中 python 解析为同一解释器。

| 收据名 | 实际命令/范围 | 结果 |
|---|---|---|
| existing-pr4-01 | pytest 原五个 PR4 测试文件 | 56 passed |
| review-fixes-02 / review-fixes-04 | 当时的新增负例 | 16 / 20 passed；均为中间节点数 |
| g4-final | pytest -q evals/intelligence_g4，独立 basetemp/JUnit | 315 passed，补持久恢复标记之前 |
| g4-final-02 | 同范围、全新 basetemp/JUnit | 316 passed，含持久恢复标记 |
| g4-final-03 | 最终全部 G4，含非对象 checkpoint JSON 拒绝与当前源码离线安装 | **316 passed / 0 skipped**，276.22 秒，exit 0 |
| collect / full | frozen evals.intelligence_g3.pytest_runner，原控制面/必需清单 | 1754 collected；1753 passed / 1 skipped，1122.12 秒 |
| ruff-seal-final / ruff-artifacts | python -m ruff check backend tests evals audit/g4/pr4 | PASS |
| schema-check-final | persistence_schema --directory evals/intelligence_g4/schema/pr4_review_fix --scratch AREA/schema-scratch-final --check | 20 工件 PASS，未创建 DB |
| walkthrough-final | audit.g4.pr4.review_fix_probe --out AREA/walkthrough-final | 43 个当前 mock 工件；upgrade/rollback/restore CLI exit 0 |
| baseline / frontend-build | evals/run_baseline.py / frontend 的 npm.cmd run build | PASS；无 React 修改，无模型效果验证 |
| prepare-review-seal-final / verify-review-seal | audit.g4.pr4.finalize_review_fix [--prepare] | 旧节点/源码/工件保全、严格旧控制面/JUnit、最终 core wheel 与源码、阶段日志 SHA 核验 PASS |

旧 full 是本修复轮新执行，覆盖旧业务与 G1–G3，非引用上轮成绩；在最终恢复标记/
非对象 checkpoint 守卫前完成，后续变更仅为 G4 模块，由最终 G4 验证覆盖。旧业务
代码和测试控制面没有变化，未在这些收尾修改后重复旧完整套件。唯一 skip 为 Windows
symlink 权限 1314 既有例外；pytest 各有一条既有 FastAPI/Starlette httpx 弃用警告。

最终 G4 包含旧 293 + 新 23，覆盖：来源表局部恢复/运行中丢失；文档、版本、policy、
capture、coverage、service event 及水位损坏；合法追加/重复采集；旧 body 接管/拒绝；
精确修复后仍须新 epoch；外观键/旧收据重试与恢复；1/2 worker 存活计数及 owner 锁。
离线 wheel 在仓库外运行，缺失/篡改 native 依赖仍拒绝；最终核心文件 pin 与源码比较。

保留两次实际失败：review-fixes-01（测试在服务持有 owner 锁时备份，维护正确拒绝，
随后改为停服务再备份）；review-fixes-03（旧 input 文件 SHA 被误用语义 digest，修复为
原 json_bytes 文件 SHA；新增测试漏导入一类型）。两条收据 exit 1，日志未删除。
早期 22 节点 provisional 清单/源码快照也归档，最终 23 节点清单不冒称早期已验证。

## 当前 pins

| 内容 | SHA-256 |
|---|---|
| 31 个修复源码/测试/契约/工具工件集合 | d6caeb2a522952b0815f5ce71ac95afcbc15f6eef67df4ef0f2129267935c519 |
| REVIEW_FIX_BASELINE.json | 65e3e8f26c21eb6ea60c9d8de47c214375d291c58617d95e0081bbedb018e893 |
| 未改的 SQL migration source | 2987a61f13e0eab91c0779324f8c8f5173a8d6f36ba75ec1188047a252fd6ee3 |
| 未改的 SQL Schema | db8064532420c2a672c9013a1ee3f4a19da7c6b4484b425834cb8a2175937bc1 |
| fact_signature v2 policy | 70565148fe436fa823ef6a4063cbba7abb4c994cc34f19dc44bdc2451e367450 |
| runtime ranking policy | 696e984bfd3fc0638f925de0a2cf3bc5eb11ba34a31c3fd109f99f3c58e34243 |
| 未改的 intelligence 默认配置 | e14b2a151f238e55791fb3adbf38c2415645f790d805c25e8b57e7f55ba717c4 |
| walkthrough-final 完整 runtime input | 66e2b49c10ff381d2d40d26ca8f125ecdea86ea31abe66063f8382ccb9b5045b |
| walkthrough-final 完整 runtime output | d16f877ae12ca29dcd81836b0abe0c727cec5431a7ddc9cf357ed92196fe7583 |
| walkthrough-final/proof.json | f29511da40b7170af2844b4c737e5e242318cf4b12bc4e1d2bb38231e0629407 |

回放样例使用测试时钟与工程许可策略，仍为 raw_news_only、Archive=1、delivery=0；
secondary/unverified 语义与 GET 不记曝光保持。完整输入输出、native stages/N.json、
API 交换、迁移/备份/回滚/恢复 receipt、六个缺陷探针及离线 wheel proof 均逐项核验 SHA。

结论：本轮必需测试 **PASS**，最终无 FAIL；两次中间失败保留。三项 finding 已完成
修复与自测，**不将自测冒充独立复审关闭**。下列产品能力继续 BLOCKED/未接入。

## 当前限制与停止状态

来源摘要覆盖的是纳入初始化或 journal 的已接受前缀，不能证明从未纳入绑定的采集未
丢失；旧实现未保存的可信水位无法事后虚构。DB/journal/checkpoint 一起被特权回退仍
不可检测。全前缀保存/验证会增加存储和读成本，仅限有界本地 starter，未做硬件断电
或大规模性能证明。真实 Focus/Radar、历史 Persona 连续重放与 G3 历史评分仍受原边界
阻断/未接入；不宣称生产部署、语义真值、许可真实性或用户价值。

所有新闻/政策均为 AI-authored 工程 mock，外部模型/网络调用和真实用户 DB 写入为 0；
未改前端、未通知或执行第三方动作；未读取 dev-diaries、未 Git 写操作。最终封存后
停止等待独立复审，不实施 PR5。
