# ADR：G4 document ledger v1 与显式 SQLite 维护

状态：G4-PR2 候选实现，待独立审查。2026-11-02。
继承 G4_RUNTIME_LOCAL_V1.md 的 runtime_local/accepted_g2/synthetic 隔离和证据资格边界；
不修改 PR1 历史工件，不注册真实 G3 runtime。

## 表与身份

G4Base 独立于 legacy Base。新增七张表：g4_migrations、g4_source_policies、
g4_documents、g4_document_versions、g4_captures、g4_coverage_windows、g4_service_events
（上述七个名称为完整集合）。

g4_documents 的 document_id 由规范 source_id+canonical_url 派生；原 Article ID
仅为 source_article_id，不充当来源许可或不可变证据。保留语义 query ID，拒绝含
凭据/敏感 query 的 URL。策略由严格 SourcePolicy 的 canonical JSON SHA 标识。
来源目录公开不代表许可；本轮空 registry 不断言任何真实来源可保存正文。

doc_version_id 绑定 document、前驱、observed/available、payload/content/策略 SHA。
payload_sha256 是本次有界解析内容的完整性摘要，未知 rights 时也可检测内容变化；
它不证明保存了发布方完整原文。content_sha256 是实际 RetainedContent canonical JSON
摘要，metadata_only 时正文为空、标题仅为来源标签；它不等于 G1 可为空的正文文本哈希。
PR3 必须经正式 native 文本/hash 构造与验证，不能直接当 G3 accepted pin。

重复当前内容与策略只复用当前版本，原 observed/available 不变，另增 poll receipt。
A→B→A 生成第三个版本；不把 A 旧版提升为 current。同 document 的全部版本形成
唯一连续链，迟到的观察和相同观察时间的新内容拒绝。BEGIN IMMEDIATE 在读取 head
前锁住写者；唯一/FK/序号约束及触发器共同守护链、head 和不可变记录。
g4_documents 只更新 head/last_observed，旧 version/policy/receipt/window/service event
禁止 UPDATE/DELETE。rollback 是显式维护动作，删除整组 G4 表并事先备份。

## 时序、rights 与来源

NewsIngestor.one 在 read/parse 完成后取真实 observed_at，在入账时取 available_at。
available 是事务内资料入账时刻；提交前不可见，成功提交后才可被读取。发布时间只
保留 source-reported 元数据，既不代替观察，也不证明发布方时钟正确。
本次 capture、Article、ArticleReading 和成功 SourceState 同事务；任何一步失败都
不留下半条成功证据。失败观察与 SourceState error 另开同一事务；账本不可写时不
伪造覆盖，保留来源错误。refreshing 是独立的瞬时状态，可由旧恢复路径识别中断。

未知/metadata_only 许可不保存 G4 publisher title、summary、paragraphs 或 _reading。
来源标签/规范链接/可选发布时间/身份/哈希可保留。明确 excerpt/fulltext 策略要求
独立 rights_evidence_uri、policy_revision 和总字符上限；只有本次已确认 parser
payload 可进入账本，提取本身仍有界。source_policy 变更产生新版本，不改写旧许可。
策略真实性由管理员审查，本轮 mock/synthetic 测试不能证明任何线上来源许可。

旧 Article/ArticleReading 是可变缓存，仍服务旧页面；本 PR 不改旧存储/展示语义。
新 G4 账本的限制不能被描述为整个旧数据库已完成版权整理或正文资格审核。
G4 没有新展示 API；后续只能在相应 retention/来源策略内展示。

## coverage

scope 固定 bounded_feed_poll。有界 feed 解析成功：partial 点；当前策略下存在确认
捕获的 304：covered 点；无锚定 304：unknown 点。迁移后的旧 ETag 不能建立正文，
首次捕获强制重新获取。每次 poll 中间的未观察区间明确 unknown；失败尝试为 failed。
干净 stopped→started 记 service_offline；unclean restart 只能确认没有观察，记 unknown。
服务生命周期沿用现有单进程部署边界；SQLite 写锁防版本分叉，不等于多进程服务租约。
离线期间不运行后台写覆盖确认，也不把 last_success 推到当前时间。
后续请求窗口继续使用 PR1 coverage 保守并集诊断；单次成功不补齐整个请求时间窗。
旧 SourceState 只保留最新健康状态，不能替代 append-only coverage ledger。

## 维护操作

下面仅为操作格式。**本轮未对实际用户库执行。** 管理员先停止应用、保留输出 pin。
数据库和 receipt 路径都必须显式指定；有现有数据的操作要求新备份路径。

```powershell
# 新库可省略 --backup；已有库必须带备份。
python -m cfaw_news.intelligence.migrate upgrade --database <db> --backup <new-backup> --receipt <new-receipt>
python -m cfaw_news.intelligence.migrate backfill --database <db> --backup <new-backup> --root <repo> --receipt <new-receipt>
python -m cfaw_news.intelligence.migrate backup --database <db> --backup <new-backup> --receipt <new-receipt>
python -m cfaw_news.intelligence.migrate rollback --database <db> --backup <new-backup> --receipt <new-receipt>
python -m cfaw_news.intelligence.migrate restore --database <new-db-path> --backup <backup> --backup-pin <external-sha256> --receipt <new-receipt>
```

upgrade：同版本幂等；未知/部分 Schema、source/DDL pin 或实际 Schema 不匹配均拒绝，
不通过更换旧 pin 自动接受。BEGIN IMMEDIATE 内执行 DDL、版本登记和 FK check。
backup：持有写保留锁，经另一个只读连接使用 SQLite backup API，包含已提交 WAL；
校验 integrity_check，写独立备份 manifest/receipt。现有备份绝不覆盖。
backfill：仅安全元数据、观察时间为本次迁移时刻，provenance 明确标 legacy；
不签发实时捕获 receipt/coverage，不读取 ArticleReading。重复 backfill 跳过已有 document。
rollback：备份当前全库，逆依赖删除 G4 专用表；旧 Goal/Run/Decision/Schedule/Article
及其他旧表逐行保持。丢弃 G4 账本是明确维护操作，恢复需使用该备份。
restore：检查外部备份 SHA/integrity，只能恢复到新路径；不会覆盖当前库或自动切换配置。
操作不触及外部任务、文件缓存或外部效果，不宣称恢复了这些状态。

同库 SHA/head 不能单独发现整库回退。restore receipt 明确标出恢复边界；后续历史
服务须加入 restore epoch/可信库外检查点或由管理员明确接受无法检测的边界。

## 验证与范围

测试在 evals/intelligence_g4/tests/test_capture.py、test_migration.py，显式执行；
Schema 在 schema/pr2，版本 g4-document-ledger-v1 / g4-source-policy-v1 /
g4-coverage-ledger-v1；不得改 PR1/G1/G2/G3 冻结文件来接受本 PR。
源码/DDL/Schema/配置/实际命令/备份恢复 pin 见 audit/g4/pr2/。
没有实时 G2/G3、UI、模型、实际联网采集或自动生产库迁移。
