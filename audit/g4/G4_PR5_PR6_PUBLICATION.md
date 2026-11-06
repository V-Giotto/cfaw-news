# G4 PR5 / PR6 / H09 源码发布记录

2026-11-06。用户明确授权将当前项目修改正常推送到 V-Giotto/cfaw-news 的 main。发布代码不批准 G4 Beta，不自动开始 G5 或部署公网；当前仍等待独立总审查及项目所有者批准。

## 交付范围

包含 intelligence home、Focus/Radar/Archive 与反馈 UI、不可变证据/快照目录、Persona/真实历史前缀适配、预算更新后生成、访问 cutoff、SQLite 离线恢复输入隔离，以及 PR5/PR6/H09 审查修复、Schema、测试、QA 程序和公开报告/hash 清单。

本地日记仅写入 dev-diaries/，根 .gitignore 的 /dev-diaries/ 与 AGENTS.md 禁止上传规则保留。日记、凭据、.env、.local/、.tmp/、数据库、虚拟环境、node_modules、dist 和原始 QA 输出不纳入提交。GitHub 上的 hash/报告不是完整本地证据包；其 .tmp 引用留在本机，不伪称远端包含全部原始工件。

## 发布衔接

最近的 review-fix seal 为 audit/G4_H09_REVIEW_FIX_MANIFEST.json，SHA c76a09950c3471ec7583a9a41d777b09844e68e47dcb6c38f4e6a250497959fa。当前运行源码、原回归和 Schema 与该版本逐文件一致。本轮仅对既存 .gitattributes、CI workflow 作发布衔接，并新增 CI 收据 verifier 和本记录，不重写历史 seal 或源码快照。

1. Git attributes 保全已绑定 hash 的 QA 清单/程序及 runtime_schema.py 原字节，防止 CRLF 自动转换；G1/G2/G3 冻结包、数据、Schema 与 eval 测试不变。
2. CI 明确使用已登记的 g4-exact-retry-amendment-v1，并核对原始 runner 收据、amendment/adapter hash、1754 精确节点、来源、skip/插件/argv/JUnit。旧原 profile 对授权测试变化的拒绝记录保留，不记为 PASS。
3. CI 增加完整 G4 回归和前端单测；原离线 prediction smoke、baseline、build 保留。没有增加真实新闻抓取、第三方动作或部署步骤。CI 是待推送后观察的独立证据，不能用本地通过代替。

## 本地验证边界

本轮重新运行 Ruff、lexical seed baseline、前端 14 项单测、TS/Vite build、新 CI collection/verification。命令、退出码和日志 SHA 保存在本机 .tmp/evals/g3/g4-publish-20261106-001/。

完整主套件 1753 passed / 1 skipped、G4 350 passed 是紧前一轮 review fix 对同一运行源码的实际执行；本轮通过新 CI consumer 重新核对其控制收据和 JUnit，没有冒称又执行了一遍完整套件。此前浏览器 27＋11 组/StrictMode 证据仍为历史执行。远端 Linux CI 的执行结果以对应 commit 的 Actions 页面为准。

旧 PR6 v2、H09 及本次 review fix 引用全树已实际递归复验，共 30245 目录、233707 文件；verify-only 的 263952 份含索引文件清单/大小/mtime 不变。旧目录侧文件已留证隔离，原索引/七个登记文件未改；“历史目录从未改变”的过度声明已撤回。原失败记录不删除。

实际许可材料仍 raw_news_only/hold、Focus/Radar=0；合格 UI fixture 不是现实推荐正例。网络 smoke、真人研究、阅读时间校准、算法收益与生产部署仍 not_evaluated。

发布执行会检查精确暂存文件、私密路径/凭据模式、stage/worktree 字节一致性、提交树和远端 SHA。最终 commit/远端/CI 状态记录在本地日记与 Git 历史，不在本文件中填入未经观察的成功结论。
