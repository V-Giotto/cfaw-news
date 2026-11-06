# PR6 review fixes — self-test closure candidate

本轮仅修复用户指定的三个 findings；不改 G2/G3 算法、冻结研究资产或真实用户库。不代替独立复审或 Beta 所有者批准。

## P1 Windows 业务 manifest 覆盖

只读重放 v1：7239 份目录清单、56966 个文件条目、9 处大小写别名覆盖。原件不修补、不从 hash 猜造丢失内容；旧 seal 失效并保留原 JSON。
当前完整 pytest/G4 使用全新 basetemp 重新生成业务输入/输出。封存器使用独立 `.cfaw-g4-pr6-qa-index-v2.json`，全树 preflight、casefold 冲突拒绝、`open("x")` 独占创建；业务 manifest 不排除。
发布 replacement seal 前核验所有目录身份、实际文件清单、大小写唯一性、文件字节/SHA、子索引与链接边界。7 个回归覆盖保全、预先拒绝覆盖、文件/索引/新增/缺失篡改和并行全树计数。
递归实测数量以 `REVIEW_FIX_RESULTS.json:recursive_verification` 为准，不能用仅检查根索引代替。

## P2 浏览器目标与服务收据

本轮入口显式要求目录和 URL，清除旧 CFAW QA 环境后提供有效值。浏览器收据记录 CFAW_PR5_OUT、CFAW_PR5_URL、Boundary URL、CFAW_PR6_RUN/PILOT/URL、fixtures SHA、模块路径和活动服务配置 SHA。
8135/8136/5175 均记录实际 argv/cwd/环境、PID、ready HTTP、配置、起止时间、stdin STOP 和实际退出码/日志 SHA。
pilot 配置与 CLI 均记录 `--qa-delay 2`、隔离 SQLite/anchor、baseline、禁用自动获取/媒体/正文补抓。生产契约 26 组、现实材料与旧流程 10 组的结果位于本轮新目录；站外请求阻断。

## P2 StrictMode 焦点

实际开发服务器修复前重现 `focus lost to BODY`（browser-red，exit 1）。保存首个触发元素 ref，StrictMode effect 重放不替换它，只在 dialog 真正卸载后恢复焦点。
修复后真实 Edge 开发版三轮历史引用 Escape、第二次 Escape、关闭按钮均恢复到原触发元素；生产版旧键盘回归继续运行。
产品唯一源差异为 `frontend/src/BriefingEvidence.tsx`；原入场 freeze 不改写，单独记录前后 SHA。

## 验证与边界

所有最终命令、退出码、日志、JUnit、浏览器服务与逐目录完整性结果见新 `REVIEW_FIX_RESULTS.json` 和 replacement `audit/G4_RELEASE_MANIFEST.json`。
沙箱 Proactor 挂起和用户中断造成的未完成尝试保留为非 PASS；仅新完整运行参与验收。旧受损目录不参与成功证明。
g4_development 仍 conditional/pending review；g4_beta_utility 仅现实离线拒绝路径；g4_research_optional 与 live-network smoke 均 not_evaluated。
H09 native 历史连续性边界不扩大；无公网发布、push、外部自主行动或真实用户研究结论。
