# G4-PR4 复审三项修复矩阵

2026-11-02，main@783f5428671457ea3f1f654b160152f653d2e9e0。
用户明确授权修复；不提交/推送，不写真实用户库、不联网、不读 dev-diaries/。
入口、原 PR4 manifest 核验与源码前像位于 .tmp/evals/g3/g4-pr4-fix-20261102-001/。
原报告与 Schema/pins 保留，新增修复报告及独立工件，不改写历史 PASS。

| Finding | 文件 | 测试/DoD |
|---|---|---|
| P1 来源账本回退 | 新 corpus_trust.py；history_store.py、checkpoint.py、persistence_migrate.py | 完整来源不可变记录摘要、版本链/文档水位绑定 journal/独立 checkpoint；合法追加与重复采集允许；已知版本/文档/coverage/政策丢失或改写拒绝；旧库必须显式新 epoch；部分恢复不得发布 |
| P2 幂等键冲突 | history_store.py、service.py | client/system 命名空间分离；相同外观的合法 API 键不能占用内部键；识别合法旧收据，旧冲突行不污染内部终态或重启 |
| P2 超时线程积累 | service.py | 专用有限 executor 与实际线程完成绑定 permit；超时先记终态，后续任务有界排队；取消、关闭和跨实例 owner 锁等到实际工作退出；迟到结果不得发布 |
| 契约/回放/报告 | persistence_schema.py、新 schema/pr4_review_fix、test_pr4_review_fixes.py、新 manifest、ADR 修复附录和审计脚本 | 原 293 节点保留、新节点显式登记；Ruff/Schema、适用回归和实际 argv/exit/log/SHA；停止待复审 |

SQL 表布局不变；checkpoint/journal 内容版本变化须显式处理旧格式，不能静默将当前
来源基线当作过去已验证。恢复接管先核对历史运行输入所证明的来源前缀，缺失已知
版本不得凭确认跳过；可从一致的较早完整备份恢复到新路径/新 epoch 并明确承认历史回退。
取消/超时是协作边界，不声称能强杀任意线程；不协作线程仍存活时不归还计算容量。
