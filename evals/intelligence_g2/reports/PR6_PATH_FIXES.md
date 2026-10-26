# G2-PR6 最终校验路径修复

当前状态：最小修复和提交前回归通过；**未提交修复、未执行新的完整 pytest、最终 g2_development 尚未通过**。

## 先区分 pytest 与校验器结果

已批准集成提交：`a2f5d4c660a1fac374e30e4fbe86a7e9af743905`，没有 push。
该提交上的完整 pytest 实际为 **1091 passed / 1 skipped / exit 0**；日志
`.tmp/evals/g2/pr6-final-001/checks/pytest-full.log`，SHA
`92a9255926abb595a7b90220c4ffa225946c8a97a5b3e96793c2fd046f439a66`；JUnit
`full.xml` SHA `3c8b6604595a4f598b618b56449e2f3322cc589785029e8d7af47d8c032a21f2`。
完整节点 Counter 已对原 1092 节点清单核验通过，唯一 skip 为已登记的 Windows symlink 1314。

失败在随后 verify_checks 导入旧 G1 工件清单：`relative(name)` 拒绝 Windows 反斜杠，
抛出 MANIFEST_PATH_INVALID / pr6 / path，外层 approved-full-once **exit 1**。
不能把 pytest 成功写成最终验收成功，也不能把它描述为 pytest 测试失败。
这次完整运行授权已经使用，没有自动重跑。

同提交已有 2040 任务预测/独立评测、540 条 G2、966 passed/1 skipped evals、
200 次旧 G1 预测/400 次后评测及其他检查通过；这些工件原字节保留。
它们绑定 a2f5d4c，不冒充本次未提交修复的新证据。

## 最小变更

- checks.py：提取 legacy 工件导入函数，仅在导入旧 G1 artifact_sha256 键时将分隔符转为 POSIX，再调用原严格 relative/pinned。G1 reproduction.json 不改写，SHA/边界/reparse 检查保留。
- evaluate.py / acceptance.py / checks.py：入口目录先作 Path.absolute，再进入原 sealed/pinned 检查。没有提前 resolve 跟随链接，也没有扩大输出区或跳过 SHA。
- PR6 自有 manifest 的严格 POSIX 规则保持原样；驱动器、UNC、ADS、父目录、重复空组件继续拒绝。
- 新增 test_path_compatibility.py 的 12 条正反例；节点清单扩展到 **1104**，其中 PR6 **108**。H01/H06/H07/H09 绑定新增节点。
- README/数据字典只追加说明。没有修改 G1、PR1–PR5、Schema、配置预算、标签、参考、Prompt、生产 DB 或 UI。

## Before / after

先提取原循环（行为未改）以隔离真实失败，新增回归 **4 failed / 8 passed / exit 1**：
Windows 工件名、相对 evaluation/acceptance/checks 三入口失败。
最小修复后 **12 passed / exit 0**。六类逃逸负例和实际 SHA 错误继续逐项断言 code/stage/field。

全部 PR6 内存预检 **108 passed / exit 0**；该命令使用无 socket 事件循环，
保留真实定时器/取消，只是提交前预检，不替代正常异步或完整回归。
针对原真实 G1 复现目录，导入器实际校验 **1400** 份工件 SHA，原 reproduction.json 字节不变。
全域 Ruff、PR6 Schema 及新完整 collection/节点清单检查通过。
原失败日志、旧 required_tests、修复前源码、当前 diff/JUnit 均保存在
`.tmp/g2-pr6-path-fix-001` 和 `.tmp/g2-pr6-evidence`，不覆盖 final-001。

## 未关闭门槛与后续授权

已锁定的同源码要求仍有效：修复改变了校验器/节点清单，所以 a2f5d4c 的旧全量不能登记为新源码通过。
需管理员另行批准一个本地 PR6 修复提交，以及新提交上的离线验证和一次新的完整 pytest；失败后仍不自动重跑。
原 382 路径集成提交授权已执行，本次新增测试/报告也不偷偷混入旧提交，不 amend、不 push。
新提交后使用全新 final-002 目录生成矩阵/独立评测/检查/AI 复核/验收；旧结果保留。
没有真实模型、网络、密钥、生产数据库或 G3 实施。人类研究仍 optional/not_evaluated。
在这些客观门槛关闭前，不建议合并，不产生最终 PASS 或 G3 授权。

## 实际命令记录

完整 argv/cwd/UTC 起止/exit 位于 .tmp/g2-pr6-evidence 对应 command.json。

| Record | Exit | Log SHA256 |
|---|---:|---|
| approved-full-once | 1 | `8145efa42e3cbcca9c4b907f78d3eb254e7891466203091ca27d23580566f252` |
| path-regressions-before | 1 | `a671146484c04deb45a9d36b564dc505ce5cc8f566746262c8883304f8f4a9d9` |
| path-regressions-after | 0 | `4260d9604bc044844ffd6a676e1059b09753b6acb04b07ee8ab42ce7af471c23` |
| path-pr6-preflight | 0 | `02d67ec7863d5f05e70473bffea80503983b22f2f00d76e9b126f919502c3a2e` |
| legacy-import-fixed | 0 | `8c29b62561bf3bbdfbb10ef73b8eaf3f0b750df06fcf116b80b8905f0b0b5be4` |
| path-ruff | 0 | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| path-schema | 0 | `4cb4acf92174a3b56b040ebc4a2f84641fee099970b539f00d40679cbdb2ef40` |
| path-inventory | 0 | `6425ad567e47e0f7f25fc39d91767605e486c47d842d55505e01fa9aa454efc0` |
| path-diff-check | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
