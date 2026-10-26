# G2 开发验收

**g2_development：PASS；管理员开发验收：accepted。**

验收记录时间：2026-10-26T19:32:30.046248+08:00（Asia/Shanghai）。
验收源码提交：`26826cb19658e5a6063bd3e5eb203e1d05a3ce65`；Git tree：`2b08443275abf3c6ece34e4a424c6b2b23007180`。
批准依据：项目所有者在当前会话明确表示“批准 G2 开发验收，请进行G2 开发验收”。
机器可读管理员决定：[administrator_decision.json](../.tmp/evals/g2/g2-development-acceptance-20261026-001/administrator_decision.json)。

## 验收范围与结果

覆盖 G2-PR1–PR6：as-of / Gold 隔离、事件关系与稳定身份、Claim / EvidenceBundle、
规则 IntelligenceItem、离线 mock 表达与回退，以及全链评测和稳定 G3 交接。
H01–H10 均由原生验收程序重新判定为 PASS，G2-T01–T46 均有实际 JUnit 节点映射。
当前 681 份受控源码/资产与已验收提交一致；G1 frozen pin 保持
`5608f6c9f20d283f9274308fa98a277c535eb0d8d828fd0d863d6e1faafde06f`。

本轮执行未经替换的正式 `evals.intelligence_g2.pr6.acceptance` CLI，使用正常 Windows asyncio；
实际 exit code 为 0。程序重新处理 2040 个任务（1872 个返回、
168 个受控拒绝），逐项核对保存的语义输出、候选池及除耗时外的 trace，
重算后评测，再校验 checks / JUnit / AI 复核绑定。新验收的 7 个 payload 及 manifest
与之前封存的最终验收逐字节相同；没有修改标签、断言或历史结果。

| 门槛 | 结果 |
|---|---|
| H01 输入安全；H02 稳定身份 | PASS |
| H03 引用完整性；H04 合成语义反例最低线 | PASS |
| H05 输出完整性；H06 复现性 | PASS |
| H07 回归安全；H08 AI 开发审查 | PASS |
| H09 非授权行为；H10 研究诚实性 | PASS |

## 回归与证据时点

本轮重新核验同一提交的已封存测试、原始 JUnit、完整节点集合、命令退出码和日志哈希，
没有重新运行全量 pytest、前端构建或 G1 legacy 矩阵。

| 同提交归档测试 | 实际结果 |
|---|---|
| G2 | 572 passed，0 skipped |
| evals | 998 passed，1 skipped |
| 全项目 | 1123 passed，1 skipped；1124 个节点 |

唯一 skip：`test_symlink_outside_bundle_rejected_if_supported`，
原因为 `symlink creation unavailable: 1314`。该原生权限分支仍未验证，未放宽断言。
原先失败和修复闭环保留在
[PR6_REVIEW_CLOSURE.md](../.tmp/evals/g2/pr6-review-final-001/PR6_REVIEW_CLOSURE.md)。
本轮沙箱 asyncio 探针 8 秒超时，单独记录为环境探针 timeout / 124；
随后正式命令在正常本机环境运行，不将探针当成产品测试通过。
首次保存管理员记录的辅助脚本因误用严格模型的 Python 解析接口退出 1；
改用 JSON 解析接口后完成保存，没有修改模型、断言或验收工件，也没有重跑正式验收。
失败摘要与原脚本保留在本轮目录的 `finalization-before-error.json` 和
`finalize_acceptance_before.py`；该辅助脚本失败不计为工程验收命令成功。

## 验收工件与真实命令

- [本轮工程验收](../.tmp/evals/g2/g2-development-acceptance-20261026-001/acceptance/G2_ACCEPTANCE.md)
- [原始命令、时间与退出码](../.tmp/evals/g2/g2-development-acceptance-20261026-001/acceptance.command.json)
- [原始日志](../.tmp/evals/g2/g2-development-acceptance-20261026-001/acceptance.log)
- [G3 稳定交接视图](../.tmp/evals/g2/g2-development-acceptance-20261026-001/acceptance/G3_HANDOFF.json)
- [5 条 synthetic 表现示例](../.tmp/evals/g2/g2-development-acceptance-20261026-001/acceptance/synthetic_examples.md)
- [原始全套 pins](../.tmp/evals/g2/pr6-review-final-001/FINAL_PINS.json)

完整 argv：

```text
D:\agent_project\cfaw-news\.venv\Scripts\python.exe -B -m evals.intelligence_g2.pr6.acceptance --profile g2_development --run D:\agent_project\cfaw-news\.tmp\evals\g2\pr6-review-final-001\campaign --run-manifest-sha256 f5b49c3da518e4386999c226514dfe24524a2641bd856f3cbe932fc411ea01a9 --evaluation D:\agent_project\cfaw-news\.tmp\evals\g2\pr6-review-final-001\evaluation --evaluation-manifest-sha256 a90250ea872aaa0cb0308a9239fa27d76499016091c22a08ea5c02ee8dfdbda3 --checks D:\agent_project\cfaw-news\.tmp\evals\g2\pr6-review-final-001\checks\checks.json --checks-sha256 5abf276760f4ab0f03e6ece9721202abf3f894e662265ee58dd6e2c049a88e5a --ai-review D:\agent_project\cfaw-news\.tmp\evals\g2\pr6-review-final-001\control\ai_review.jsonl --ai-review-sha256 c294d83e6004e516410b3cfc3f4091130ee958abcf55c055d481aadef80690a0 --out D:\agent_project\cfaw-news\.tmp\evals\g2\g2-development-acceptance-20261026-001\acceptance
```

| Pin | SHA256 |
|---|---|
| 验收 manifest | `0013fa327d94635d463e5df384e2074f03514b8ae4ca20b17ed426c28b800fe4` |
| 预测 manifest | `f5b49c3da518e4386999c226514dfe24524a2641bd856f3cbe932fc411ea01a9` |
| 后评测 manifest | `a90250ea872aaa0cb0308a9239fa27d76499016091c22a08ea5c02ee8dfdbda3` |
| checks | `5abf276760f4ab0f03e6ece9721202abf3f894e662265ee58dd6e2c049a88e5a` |
| AI 开发复核 | `c294d83e6004e516410b3cfc3f4091130ee958abcf55c055d481aadef80690a0` |
| 本轮验收日志 | `9e6442c55672f2d8fc101d844f40944284bc8c3a0dd7800ce624be0387af7a85` |
| 管理员决定 | `cf7680e0938df2427f5214550843176db1e84474e3182d452e8b3f5c49c41ee2` |

## 授权与限制

工程验收程序的 `administrator_acceptance=pending` 和 `g3_planning_authorized=false`
是固定的历史输出。此处管理员决定另存并绑定相同源码、工件与门槛；
未改写工程 schema 或旧封存结果。当前 G2 管理员状态以本报告和管理员决定记录为准。

G3 离线技术资格为 true；本次批准仅限 G2 开发验收。
G3 规划及实现授权均为 false，尚未启动 G3。

现有证据属于 synthetic / rule / mock / 非盲 AI 开发审查。
真实模型、真实来源泛化、独立真人审查、双标和用户研究仍为未验证或 deferred；
G2 开发通过不表示独立语义真实性、真实新闻推荐效果或用户价值已经证实。
R0 的漏合并及质量缺口继续保留，不以此宣称算法全面提升。
真实外部请求、真实模型调用及费用均为 0。

本轮只新增验收执行记录、管理员决定和本报告；未修改源码、测试、Schema、
冻结输入、标签、依赖或生产数据库，未 commit/push。
