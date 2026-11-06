# G4 验收候选 — H09 连续性修复


2026-11-06 追加修复：恢复只打开验证后的离线副本；旧封存目录的未登记侧文件已保留证据后隔离，未改旧索引。日程“精确重试”复用首份 payload，并以 g4-exact-retry-amendment-v1 显式登记唯一测试来源变化；G1/G2/G3 原注册资产不改。当前证据见 `audit/g4/h09_review/REVIEW_FIXES.md`、`audit/G4_H09_REVIEW_FIX_MANIFEST.json`。旧数字及 seal 对应其历史源码，不能称为当前未修订 G3 profile 的 PASS。

2026-11-06。**实现方本地工程验收，等待独立总审查及项目所有者批准 G4 Beta。** 本轮按新增授权修复历史 Persona、反馈到 native 的适配、访问窗口和无交互快照目录；没有修改 G1/G2/G3 评分、冻结资产或真实用户原库。

## 本次修复与证据

详见 `audit/g4/h09/REPAIR_REPORT.md`、`audit/G4_H09_REPAIR_MANIFEST.json`。工件根为 `.tmp/evals/g3/g4-h09-20261106-001/`（下称 RUN）。命令收据记录 argv/cwd、环境、时间、退出码、耗时和日志 SHA；浏览器另记录有效目标、fixture SHA、服务参数、配置和生命周期。

- 在 SQLite 同一受检事务捕获实际 Persona、快照、delivery、交互及请求的完整 journal 前缀。第一份 Persona 晚于材料时，从其实际可用时间建立计算冷启动，原始文档观察时间保持不变，不构造更早不存在的用户结论。已建立事件身份在预算更新后保持连续。
- 旧交付内容从不可变 native basis 重演；旧 v1 runtime 以原始 hash 和 stage 重演校验。真实来源不包装成 synthetic。opened 不表示已了解，ack/dismiss/retract 经来源和目标核对后进入原有 G3 历史规则。Archive 元数据反馈不构造 delivery 或知识。
- 页面访问由正面积视口相交及文档可见性确认，独立存为 visit；生成绑定进入页面前的 journal sequence，排除当前会话刚写入的访问。兼容旧交互记录；无确认访问用一天默认，超过 30 天明确限长并保留 gaps。
- 新增当前 stream 的不可变快照分页目录，含无交互 raw 简报。读取目录和历史不写 included/rendered/opened/ack，也不修改 latest。
- 计算后可追加确认；发布重试只允许原前缀仍为祖先、epoch 及 Persona/资料/latest/取消等守卫全部满足，不重算、不绕过过期拒绝。

实际本机 MIT 文档在资料到达后创建首份 Persona，逐次保存 180/900/420 并生成，均完成 native。此前封存 QA 第 4 版 Persona/420 的恢复副本也完成 420、更新 180 后的生成，原备份不变。真实资料仍为 raw_news_only/hold，Focus/Radar=0。

1/3/7 天后端重访使用隔离 SQLite、受控时钟及明确标注工程材料；合格 delivery 的去重/ack/撤回/更正保护也属于工程轨迹。浏览器合格卡片与时间展示使用单独标注 HTTP fixtures，不是现实合格推荐、真实等待或真人研究。

## H00–H12

最终退出码、JUnit 数量及递归核验以新 manifest 为准；旧验收数字只属于旧封存树。

| Gate | 当前状态 | 证据 / 保留边界 |
|---|---|---|
| H00 前置批准 | PENDING_REVIEW | PR4 历史独立审查保留；PR5/PR6/H09 组合变更仍待独立总审查及 owner 批准。 |
| H01 来源/权利 | PASS_OFFLINE_SAMPLE | audit/g4/pr6/samples/vite-8.3.4/、RUN/pilot-retry/result.json；已有 MIT 文本，无新增抓取。 |
| H02 runtime 契约 | PASS_LOCAL_ENGINEERING | RUN/g4-final.xml、RUN/legacy-replay-final/result.json；v1/v2 兼容和真实晚 Persona，未解决现实独立支持资格。 |
| H03 证据安全 | PASS_LOCAL_ENGINEERING | G4 全套、RUN/browser-contracts-native/browser-results.json；不可变证据及隔离，非语义真值研究。 |
| H04 排名/预算 | PASS_LOCAL_ENGINEERING | G4 全套、RUN/sqlite-proof.json；原有 G3 规则接历史前缀，B4/权重/预算算法不变，估时未校准。 |
| H05 持久化 | PASS_LOCAL_QA | G4 全套、恢复副本及旧 PR6 恢复证据；DB schema/migration 002 不变，未触原库或做硬件断电。 |
| H06 曝光/反馈 | PASS_LOCAL_QA | G4 历史轨迹、两份 browser result；实际 hold 无卡片 rendered，Archive 反馈不成为知识。 |
| H07 取消/失败 | PASS_LOCAL_QA | G4 全套、RUN/browser-pilot-retry/result.json；cooperative cancellation 边界保留。 |
| H08 API/隐私 | PASS_LOCAL_BOUNDARY | G4 全套、分页/跨流/未来 cursor 拒绝、服务配置；本地单用户，不声称认证或生产安全。 |
| H09 用户体验/重访 | PASS_LOCAL_ENGINEERING_PENDING_REVIEW | test_h09_continuity.py 的 18 节点、RUN/sqlite-proof.json、实际预算→生成及备份重放；真人效用/现实合格 delivery 未评估。 |
| H10 回归/保全 | PASS_LOCAL_QA | RUN/full-final.xml、RUN/control-verification.json、源码/依赖/pins；首轮失败保留，旧日程节点未改。 |
| H11 真实浏览器 | PASS_OFFLINE_QA | RUN/browser-retry/；契约 27 组、实际/时间 UI 11 组、StrictMode 焦点 5 项×3，服务正常退出。 |
| H12 报告诚实 | PASS_WITH_OPEN_GATES | 新 manifest 在全部引用递归核验后发布；保留失败、旧 seal 及未评估项。 |

g4_development：CONDITIONAL_PENDING_REVIEW。g4_beta_utility：OFFLINE_REJECTION_PILOT_PASSED_BETA_PENDING。g4_research_optional：NOT_EVALUATED。

## 封存与停止点

旧 PR6 v1 因 Windows 大小写覆盖 9 份业务 manifest 失效，其 invalidated seal 和原证据保留。旧 v2 `audit/G4_RELEASE_MANIFEST.json` 只证明当时 source-snapshot，不代表 H09 当前树。新 H09 seal 独立记录新版本和全部 hash；QA 索引独占创建，业务 manifest 作为普通文件哈希；只读 --verify-only 不写封存目录。

新 API g4-h09-contracts-v2、runtime envelope/config v2；旧 v1 保持原字段序列化。DB migration 002、checkpoint v2、corpus v1、fact-signature policy 不变。默认 B4、focus70-radar30-v1、420 秒。前缀缺失、损坏、超限均拒绝，不静默截断；无明确 merge/split mapping 不继承知识。

网络 smoke、现实合格 Focus/Radar、真人研究、阅读时间校准和算法收益均 not_evaluated。无系统/邮件推送、自动订阅、新来源抓取或第三方自主动作。旧 Goal→Run→Decision→显式本地 Schedule→幂等重试→完成→历史重开已验；截图只含公开许可文本与 QA 数据。

到此停止。不得依据实现方自测自动批准 Beta、进入 G5、提交敏感文件或 dev-diaries/、push、merge 或部署公网。
