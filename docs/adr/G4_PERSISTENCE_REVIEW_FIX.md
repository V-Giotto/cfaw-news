# G4-PR4 复审修复：来源前缀、请求域与实际 worker 生命周期

2026-11-03；补充 G4_PERSISTENCE_V1，不改写原报告或验收 pin。三项 finding 的原始
证据在 .tmp/evals/g3/g4-pr4-review-20261102-001/；它们是旧实现的实际复现，修复后的
结果必须使用新目录。本实现仍待独立复审，不扩大真实推荐、历史评分或部署范围。

## 来源的可信边界

原版 trusted head 只覆盖 intelligence_ 物化历史，corpus_basis 只能比较一次运行期间
的来源集合。因此原 ADR 的整库回退检测不足以保证来源表局部恢复后的证据连续性。
本版新增严格 g4-corpus-prefix-v1，由以下内容构成，摘要不复制受限正文：

- PR2 六类不可变表的完整行身份→SHA：migration、source policies、document versions、
  captures、coverage windows、service events。
- 每个文档的 source_id、canonical_url、有序完整 version IDs、合法链尾与
  last_observed_at 水位。现存全部版本的序号、不可变前驱、时序、内容/记录 SHA、政策
  绑定和当前链尾均重新检查；coverage/capture 的结构及关联也重新核对。

g4-checkpoint-v2 的独立初始 corpus 基线绑定迁移/显式接管时的来源集。每次 journal
事务在 body.corpus 保存当前完整前缀与 SHA，entry hash→head→外部 checkpoint 间接
绑定所有后续已接受前缀。来源行不与用户历史跨事务伪装成同一次采集；“已接受”指
初始化基线或 journal 事务已经纳入的来源，不承诺发现从未纳入可信记录的外部采集丢失。

HistoryStore 的每次读/写都要求当前账本包含初始基线和所有已接受不可变行，文档链必须
逐项延伸旧前缀，观察时间不得倒退。新文档/新版本/新观察允许追加；重复内容仅推进
观察水位。丢失、改写、回退或分叉返回 G4_CORPUS_PREFIX_LOST / G4_CORPUS_CHAIN_INVALID，
不生成新 run 或发布。发布仍保留原 corpus_basis 的请求期间变化检查，不以新前缀机制
替代 Persona/latest/input/fact policy/取消和 CAS 校验。

来源不一致时 status 为 unavailable，写操作失败关闭；reconcile 将恢复要求持久化到
库外 checkpoint.recovery_required。首次返回具体来源错误，后续返回
G4_CORPUS_EPOCH_ADOPTION_REQUIRED。即使精确补回来源、重启或新建同 epoch 实例，也
不能自动清除此标记；只能显式验证并接管新 epoch。写标记失败返回
G4_CORPUS_RECOVERY_MARK_FAILED，保持服务拒绝，不承诺存储故障时仍能持久化标记。
旧 latest/snapshot 仍完整保存在
SQLite，不被覆盖；不能因服务拒绝访问就宣称旧快照丢失。部分来源表恢复不是公开 HTTP
删除漏洞。本协议仍不能识别 DB、历史 journal 和独立 checkpoint 一起被管理员回退。

## 旧格式与恢复

SQL 表/002 migration 源码和 Schema 不变，不自动修改用户数据库。checkpoint v1 明确
返回 G4_CORPUS_EPOCH_ADOPTION_REQUIRED；不能在普通 status/POST 中将当前来源静默
认作旧可信基线。停服务后必须显式维护、先备份，以新 anchor 路径和
--acknowledge-restored-history 使用 adopt-restore，创建新的 epoch；upgrade 不代替接管。

维护时验证现有 journal/物化记录；已有 corpus 绑定仍必须满足。对旧 body 缺少 corpus
的历史，重新核对全部 hash-bound run.input 的版本/政策/coverage 是否仍逐项存在，使用
原 json_bytes 的文件 SHA（包括尾换行），不能混用语义 digest。历史已证明 v2 而当前
只剩 v1 时，显式接管本身也会拒绝；确认不能使不一致材料变得合法。可补全精确可信
来源，或从一致的较早完整备份恢复到新 DB/anchor，并明确确认历史回退/新 epoch。

旧客户端 epoch 继续失效，旧 JSONL 从不接管为用户历史。来源基线与 journal 保留全部
前缀；当前是小容量本地实现，会增加存储和全链验证成本，不宣称大规模账本性能，后续
压缩/索引须保持相同不变量。现有容量与默认关闭策略不变。

## 客户端与内部请求域

新请求身份为 SHA([stream, namespace, raw_key])，namespace 只能是 client/system；
SQLite unique(stream,key) 存储 client|raw_key / system|raw_key。管道字符不在公共
Key 文法中，客户端即使使用 run:{id}:terminal/start/publish 也不能占据内部任务记录。
API 请求仍要求原 expected_head/epoch、版本和幂等语义校验，不限制合法外观键来掩盖问题。

对旧 SHA([stream,raw_key]) 收据：客户端相同语义重试仍可复用；内部只复用属于同一
内部 operation 的旧记录，忽略占用相同外观键的旧客户端操作，保留旧行/旧 hash 不改写。
终态/恢复操作进入 system 域，不会因旧取消收据冲突使全服务 unavailable。

## worker 与超时

专用 ThreadPoolExecutor 的 max_workers 与 semaphore 同界。一个实际 concurrent Future
执行 native 计算、内部结果验证和发布，只有它真正完成才归还 permit；async wait_for
等待通过 shield 包装，超时/取消不会把仍在执行的线程标成“已完成”。迟到异常会被消费。
超时可以先持久化 timed_out，队列继续受原 queue_limit 约束，后续请求可以有界等待，
不能通过连续超时积累超过配置数量的后台计算。

Control/持久取消和发布前检查保留。停止服务也不提前释放 worker owner 锁：遗留实际
Future 未退出前，替代实例不能开始计算；全部退出后才释放 owner。它不是强杀线程：
永久不协作任务会占住容量，必须由操作者处理进程，不能为恢复可用性放宽 CPU 上限。

## 新工件与验证

schema/pr4 保留原字节，schema/pr4_review_fix 导出 g4-pr4-contracts-v2，增加
CorpusPrefix/DocumentWatermark 并登记 checkpoint v2、corpus v1 和请求域。HTTP 路径/
请求字段未放宽；OpenAPI 可保持原字节相同，不能由此推断存储协议未变化。
新负例包括来源局部恢复/计算中丢失、不可变记录及水位损坏、旧 body 新 epoch 接管/
拒绝、客户端外观键/旧冲突收据、1/2 worker 实际存活数、shutdown 后 owner 保留。
精确节点、当前命令和 pins 见 audit/g4/pr4/REVIEW_FIXES.md 及独立修复 manifest。
