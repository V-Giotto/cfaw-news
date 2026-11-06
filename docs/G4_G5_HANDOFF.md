# G4 → G5 交接候选


2026-11-06 追加修复：恢复只打开验证后的离线副本；旧封存目录的未登记侧文件已保留证据后隔离，未改旧索引。日程“精确重试”复用首份 payload，并以 g4-exact-retry-amendment-v1 显式登记唯一测试来源变化；G1/G2/G3 原注册资产不改。当前证据见 `audit/g4/h09_review/REVIEW_FIXES.md`、`audit/G4_H09_REVIEW_FIX_MANIFEST.json`。旧数字及 seal 对应其历史源码，不能称为当前未修订 G3 profile 的 PASS。

2026-11-06。H09 修复等待独立总审查及所有者 Beta 批准；本文件不授权开始 G5、发布或新增抓取。当前证据见 G4_ACCEPTANCE.md、audit/g4/h09/REPAIR_REPORT.md 和 audit/G4_H09_REPAIR_MANIFEST.json；旧 PR6 v2 seal 只对应其历史源码，旧 v1 已失效。

## 可继承的工程能力

- 来源/许可隔离、不可变文档引用、source gaps、G2/G3 原生计算和安全降级。
- SQLite append-only 历史、trusted head/checkpoint、幂等、取消、备份恢复新 epoch，以及兼容旧 Goal/Run/Decision/显式 Schedule。
- 情报首页、预算投影/已用剩余估时、完整 Archive、显式反馈撤回和稳定焦点。
- 实际 Persona 历史及交互前缀适配，旧 v1 不改写，保存预算后继续 native 生成。打开不表示知道，Archive 元数据反馈不进入交付知识。
- 独立视口 home visit，以进入页面前 sequence 绑定上次访问窗口；1/3/7 天 SQLite/native 重访工程回归。当前 stream 快照分页含未交互 raw 简报，目录存在不表示看过。

## 审批前仍须决定

1. 完成组合工作树独立审查，特别核对前缀、旧 v1 replay、冷启动、访问 cutoff 和发布 CAS 并发守卫。实现方自测不替代独立结论。
2. 所有者决定是否接受 raw_news_only/hold 有限 Beta。已有 MIT 材料不构成现实合格 Focus/Radar，不得 synthetic 补首页或削弱独立性门。
3. 单独批准生产来源许可/角色/保留边界和实时网络 smoke。当前生产 rights registry 仍为空，本轮 QA 仅使用本机已有许可文本。
4. 若进入 G5，再设计真实效用、理解成本和时间校准；真人研究、语义真值与算法收益均 not_evaluated。

## 保持冻结和边界

G1/G2/G3 数据、评分、required-test/source pins、Schema 和历史验收保持原字节。默认 B4；H09 是 G4 输入适配和新版本 policy，未证明 P1 优于 B4。新 Schema 放 h09_v2/h09_native_v2，不覆盖旧目录。DB schema/migration 不变。

第一份 Persona 晚于资讯时，只从实际可用时间建立派生计算，不回填画像时间或伪造更早用户结论；原文版本/观察时间保留。明确 delivered 轨迹才计算历史规则。无显式 merge/split mapping 时保守处理，不暗中继承知识。

前缀有容量上限：128 Persona、128 delivered snapshot proofs、12000 selected rows、20000 journal entries，另有原 runtime 字节上限。超限失败需显式处置，未实现无限历史压缩或持久化前端 checkpoint。访问缺失采用旧交互兼容或一天默认；超过 30 天明确限长，不能解释为连续覆盖。

恢复先停止 worker，验证备份和来源前缀，显式创建新 epoch；后续迁移先在副本重演。未操作真实原库，未验证硬件断电、多用户认证、云部署或强制线程隔离。whole-paragraph 长引用仍可能安全拒绝，不通过改写材料放行。

保留无默认推送、无自动订阅、无未经批准第三方动作。本地日程不自动写第三方日历。禁止提交用户数据、凭据和 dev-diaries/。后续从独立审查及明确授权开始。
