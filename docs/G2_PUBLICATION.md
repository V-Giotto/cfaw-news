# G2 开发验收与发布说明

截至 2026-10-26，G2-PR1–PR6 的 `g2_development` 工程验收为 **PASS**，
项目所有者已批准 G2 开发验收，管理员决定记录为 **accepted**。
G3 离线技术资格为 true；G3 规划及实现尚未授权或启动。

验收源码提交：`26826cb19658e5a6063bd3e5eb203e1d05a3ce65`。
该提交之后的公开说明提交不改变已验收算法、测试、Schema、冻结输入或标签。

## 交付

- PR1：as-of / Gold 隔离桥接、严格契约和最小离线管线。
- PR2：事件关系、稳定 event_key、merge/split 谱系及历史快照。
- PR3：Claim、EvidenceBundle、来源归属、scope、冲突与更正/撤回历史。
- PR4：规则 IntelligenceItem 与 focus/radar/hold 候选。
- PR5：离线 rule/mock 表达、预算、超时、安全门禁和规则回退。
- PR6：完整矩阵、后评测、源码与原始 JUnit 绑定、AI 开发复核和稳定交接。

实施依据见 [G2 计划](plans/G2_IMPLEMENTATION_PLAN.md)，
使用方式见 [离线评测说明](../evals/intelligence_g2/README.md)，
后续消费者遵守 [G2 → G3 交接契约](G2_G3_HANDOFF.md)。

## 已完成的验收

H01–H10 全部通过，G2-T01–T46 均有实际 JUnit 节点映射。
2026-10-26 正式验收 CLI 重新处理 2040 个任务（1872 个返回、168 个受控拒绝），
在正常 Windows asyncio 环境返回 exit 0；新旧七份验收 payload 及 manifest 逐字节一致。
本轮验收重新核对了同一提交的 checks、JUnit、日志和 29 条 AI 复核绑定。

| 同提交归档回归 | 结果 |
|---|---|
| G2 | 572 passed |
| evals | 998 passed、1 skipped |
| 全量 | 1123 passed、1 skipped |

唯一 skip 为 Windows symlink 创建权限不足（1314）。
这些是验收源码对应的已核验回归记录，不表示每次发布说明更新都重跑过完整矩阵。

| 验收对象 | SHA256 |
|---|---|
| G1 frozen manifest | `5608f6c9f20d283f9274308fa98a277c535eb0d8d828fd0d863d6e1faafde06f` |
| G2 prediction manifest | `f5b49c3da518e4386999c226514dfe24524a2641bd856f3cbe932fc411ea01a9` |
| G2 evaluation manifest | `a90250ea872aaa0cb0308a9239fa27d76499016091c22a08ea5c02ee8dfdbda3` |
| Checks | `5abf276760f4ab0f03e6ece9721202abf3f894e662265ee58dd6e2c049a88e5a` |
| AI development review | `c294d83e6004e516410b3cfc3f4091130ee958abcf55c055d481aadef80690a0` |
| Acceptance manifest | `0013fa327d94635d463e5df384e2074f03514b8ae4ca20b17ed426c28b800fe4` |
| Administrator decision | `cf7680e0938df2427f5214550843176db1e84474e3182d452e8b3f5c49c41ee2` |

[详细验收记录](G2_DEVELOPMENT_ACCEPTANCE.md)保留实际命令及当时的授权状态。
其中指向 `.tmp/` 的链接只在原验收工作机可用；完整日志、运行工件及本地管理员记录
没有上传到 GitHub。本页提供公开摘要与哈希，不能替代缺失的原始运行工件。
源码、固定 synthetic 输入、配置、测试和复现命令已随项目公开。

## 本次发布前复验

2026-10-26 发布前重新运行了 Ruff、全量 pytest、seed sanity 和离线前端构建，
四项实际命令均 exit 0；全量结果为 **1123 passed、1 skipped、1 warning**。
skip 仍为 symlink 权限 1314，warning 为既有 Starlette/httpx 弃用提示。
seed sanity 仅是词法检索烟测，不作为算法质量或真实模型证据。
本轮全量日志 SHA256 为
`20261037ee1e417b1412c5ad3e4472e23f0ccd8340bf530fb4336b1ad5fd1f97`，
JUnit SHA256 为 `2250c5e14a86edfdf2a63fdd2bed12c0140d90702061e66d57dc5a390998ac85`。
这些日志及命令记录仍只保存在本地 `.tmp/`；远端 CI 状态另行核验。

## 限制与隐私

证据属于 synthetic / rule / mock / 非盲 AI 开发审查。
真实模型、真实来源泛化、独立真人复核、双标和用户研究均为未验证或 deferred。
R0 的漏合并和基线质量缺口保留；不以工程 PASS 宣称真实新闻推荐或用户价值已证实。
真实模型调用和费用为 0。GitHub CI、发布同步和生产部署分别核验，不能互相替代。

开发日记保存在根 `dev-diaries/`，由 `.gitignore` 的 `/dev-diaries/` 排除，
不属于公开报告或上传工件。`.tmp/`、`.local/`、凭据、数据库及生成物继续留在本地。
