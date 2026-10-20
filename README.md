# CFAW News

CFAW News 面向 AI 开发者，从新闻、官方材料、论文与开源项目发现值得知道的进展，形成重点情报、前沿速览和可检索资料库，在用户主动回访时补齐重要变化。

研发优先级：算法与评测质量 > 关键用户体验 > 扩展功能数量。用户自主阅读、研究和行动，不默认发送应用外提醒。

## 项目依据与当前阶段

| 文档 | 职责 |
| --- | --- |
| [CFAW News V1](docs/CFAW_News_V1.md) | 唯一产品与研究方向，定义范围和 G0–G5 门槛 |
| [G1 详细实施计划](docs/plans/G1_IMPLEMENTATION_PLAN.md) | 当前 G1 执行依据，规定 PR1–PR5、数据契约、时间可见性、B0–B4 和验收 |
| [G0 源码审计](audit/G0_REUSE_AUDIT.md) | 已核验的存量能力、复用结论、缺口和风险 |
| [G0 机器记录](audit/G0_BASELINE.json) | G0 当次环境、依赖、验证、数据库恢复及文件指纹；不是每轮自动更新的结果 |
| [AGENTS.md](AGENTS.md) | 后续 AI 和开发者必须遵守的工程规则 |

**G0、G1-PR1 及 G1-PR2 技术交付已完成，真实人工标注与独立复审仍待完成，G1 尚未整体通过。** 当前只推进独立离线的 G1 数据与评测基座；不提前开展训练、复杂 UI 重做、持续自动 Agent 或生产数据库迁移。

G1-PR1 已提供严格 Schema、Manifest、时间/版本门禁、来源许可与家族拆分校验、合成样例和回归测试。PR2 已提供 DEV-01 六时点、七份合成文档版本、Claim/事件关系、标注手册、数据卡和带外部 Manifest pin 的最小 dry-run 导出；[当前修复与验收记录](evals/intelligence_v1/reports/PR2_REVIEW_FIXES.md)明确区分技术通过与人工待完成。PR3–PR5 的完整回放、B0–B4、指标和标注验收尚未实施。情报页也属于后续设计。旧目标研究路线、24 周排期、重复交接、过渡归档和旧界面验收文档已删除，不再作为执行依据。

## 当前代码的可用能力

现有工程是独立 Python/React 本地单用户起步版，不依赖旧比赛平台。技术栈为 FastAPI、Pydantic、SQLAlchemy、SQLite、HTTPX、asyncio/SSE、React、TypeScript 和 Vite。

- 新闻来源获取、状态记录、缓存、检索筛选、分页和文章阅读；来源失败保留已有资料。来源配置在 `data/live_sources.json`，配置不保证源站当前可用。
- 中文二元词/英文词 BM25 召回及可选兼容模型。默认 `baseline` 不调用模型；无候选跳过模型。
- 旧 Goal、不可变运行快照、引用定位、用户决定和明确批准后的应用内日程。版本、取消、失效防发布和幂等规则继续保留。
- 独立的阅读正文与图片缓存。当前阅读内容不会改写历史运行证据，来源标识不冒充文章配图。

当前在线应用尚未接入 V1 文档版本库、事件/主张、情报分层、曝光历史、回访排序或时间回放。离线 PR1/PR2 中的契约与合成试点不等于这些业务能力已上线，也不构成独立研究数据集。现有文章库不能还原全部历史；引用 ID 存在不等于语义支持。

Goal/决定/日程保留兼容，不再是新产品主线。G1 不读取实际业务数据库、不加载 `.env`、不运行联网采集或实时模型，也不修改现有前端。

## 本地运行现有应用

以下用于体验兼容应用，不是 G1 离线回放入口。需要 Python 3.11+、Node.js 22.12+ 或 24；精确依赖以锁文件为准。

```powershell
cd D:\agent_project\cfaw-news
powershell -ExecutionPolicy Bypass -File scripts/start.ps1

# 首次安装和构建完成后
powershell -ExecutionPolicy Bypass -File scripts/start.ps1 -SkipInstall
```

默认打开 `http://127.0.0.1:8000`，API 文档在 `/docs`。Ctrl+C 停止；端口占用时加 `-Port 8010`。启动脚本使用本项目 `.venv`，可用 `-Python <解释器路径>` 指定创建环境的解释器。

默认数据库为 `.local/cfaw-news.db`，使用单个 Uvicorn worker。服务运行期间可按来源周期自动获取新闻；停机不采集。`NEWS_AUTO_REFRESH=false` 关闭自动获取，`NEWS_MEDIA_FETCH=false` 与 `NEWS_READING_FETCH=false` 控制配图及网页正文补抓。G1 离线执行不需要启动此应用。

需要热更新时：

```powershell
# 项目根目录
.\.venv\Scripts\python.exe -m uvicorn cfaw_news.main:create_app --factory --reload --reload-dir backend --host 127.0.0.1 --port 8000

# 另一个终端
cd D:\agent_project\cfaw-news\frontend
npm run dev
```

模型配置仅参考 `.env.example`、`.env.deepseek.example`，不要覆盖已有 `.env` 或复制其他项目的凭据。兼容接口的历史真实调用记录见 [LIVE_MODEL_CHECK.md](docs/LIVE_MODEL_CHECK.md)；该记录不是 G1/V1 质量评测，也不证明服务当前可用。真实模型验收不属于 G1 默认执行流程。

## 开发验证

```powershell
cd D:\agent_project\cfaw-news
.\.venv\Scripts\python.exe -m ruff check backend tests evals
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe evals/run_baseline.py
cd frontend
npm run build
```

也可运行 `powershell -ExecutionPolicy Bypass -File scripts/verify.ps1`。前端修改源码后构建，`frontend/dist` 是生成物。

旧 `evals/run_baseline.py` 保留为 26 条归档、3 组手选标签的 seed-sanity 烟测，不属于 G1 金标或独立算法成果。已实现的 PR1 校验和 PR2 dry-run 命令见 [离线契约与试点说明](evals/intelligence_v1/README.md)；PR1 证据见 [冻结记录](evals/intelligence_v1/G1_BASELINE_LOCK.md)，PR2 当前 pin、修复和测试见 [PR2 审查修复记录](evals/intelligence_v1/reports/PR2_REVIEW_FIXES.md)。其余 G1 命令与 T01–T26 以实施计划为准，尚未实现的 CLI 不作为可用能力。

本机检查、mock、真实模型、真实来源、远端 CI 和部署分别报告。仓库中的 Linux/Docker/GitHub Actions 配置不等于本轮已执行或部署。

## 数据、出处与工程说明

- [现有架构](docs/ARCHITECTURE.md)：兼容工程、证据/版本/取消/批准边界。
- [迁移记录](docs/MIGRATION.md)：原始资产与溯源；`data/archive/articles.json` 和 `data/sources.json` 必须保留。
- [隐私与数据说明](PRIVACY.md)：本地数据、外部请求和模型发送范围。
- [Apache-2.0](LICENSE) 与 [NOTICE](NOTICE)：代码许可、原作品、新闻与第三方资产署名。

`.env`、`.local/`、私人数据库、依赖目录、生成物和 `dev-diaries/` 不进入 Git。开发日记永远本地。公开访问来源不意味着允许公开再分发全文；V1 仍以本地单用户为验收环境，不能声称已经具备生产鉴权、多租户隔离或部署能力。
