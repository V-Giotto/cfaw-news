# 迁移记录

日期：2026-10-14。源目录：用户选定的最终比赛版 `D:\Hackathon_agenticapp\workspace\cfaw-news-agent-final`。目标：`D:\agent_project\cfaw-news`。

## 直接保留的资产

| 原路径 | 新路径 | 用途 |
| --- | --- | --- |
| `src/data/ingestion/demo_news.json` | `data/archive/articles.json` | 26 条历史来源归档、原句、限制与归属 |
| `src/data/ingestion/sources.json` | `data/sources.json` | 28 个公开来源配置 |
| `bundle/assets/icon.svg` | `frontend/public/icon.svg` | 原作品图标 |
| `LICENSE` | `LICENSE` | 代码许可 |
| `NOTICE` | `docs/provenance/legacy-NOTICE.txt` | 保留原作品与上游署名 |

字节级 SHA-256 比较记录在 `docs/provenance/migration-manifest.json`。归档中“已核实”等日期继承自原记录，不代表本轮重新访问来源。所有新闻摘录仍归原发布者。

## 重新实现的业务

- 手写 BM25 用中文重叠二元词与英文词实现。初版加入标题重复权重，不逐字照搬旧标题门禁；算法版本标为 `bm25-han-bigram-v1`，不伪称与旧策略完全等价。
- 关注与目标版本 → Pydantic + SQLAlchemy。
- 本地 JSON 记录 → SQLite 表与事务；证据随 run 固定保存。
- 宿主模型调用 → 可选的独立兼容 HTTP 模型适配器；默认不调用模型。
- 界面/事件回调 → React/TypeScript + REST/SSE。
- 用户决定与批准 → 独立 API、唯一提议键、时间冲突/版本复核。
- 平台测试场景中的关键风险 → 独立 Python 集成测试。

提示词依据旧规则重新编写，没有接入旧 session/turn、日程服务或权限系统。模型本身没有写日程工具。

## 没有携带的内容

旧平台源码/二进制、宿主资源、bundle/打包工具、Makepad/WebView 原生适配、构建缓存、开发虚拟环境、用户运行数据、密钥、账号或历史日程。天气与日程改期功能也未迁入首版，防止分散核心开发工作。

## 起步版的状态边界

保留“目标—证据—用户决定—明确批准”闭环；词法基线只说明候选变化，不判断语义新事实。启用真实模型后才可能产生有证据支持的更新/撤回结论，仍需要独立质量评测。

完成结果可在进程重启后读取；正在运行的任务不做 checkpoint 恢复，会标记失败并提示重查。无独立后台监测、系统日历写入、登录或跨设备同步。
