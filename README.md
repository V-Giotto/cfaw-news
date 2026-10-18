# CFAW News

**让新消息，与你的下一步有关。**

这是后续独立开发的起步 Demo：围绕个人目标检索新闻资料，核对保存的证据，记录用户决定，经过明确确认后保存有限核实/试用安排。前后端完全独立运行。

技术栈：**Python / FastAPI / Pydantic / SQLAlchemy / SQLite / asyncio / SSE / React / TypeScript / Vite**。

## 本机启动（Windows）

需要 Python 3.11+（本次验证为 3.12）、Node.js 22.12+ 或 24，以及首次安装时的网络连接。

```powershell
cd D:\agent_project\cfaw-news
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
```

脚本创建项目自己的 `.venv`，安装锁定依赖、构建前端，再启动服务。首次安装完成后可以跳过安装/构建：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start.ps1 -SkipInstall
```

打开 <http://127.0.0.1:8000>，接口文档在 <http://127.0.0.1:8000/docs>。终端 `Ctrl+C` 停止服务。端口被占用时加 `-Port 8010`。

如 PATH 中的 Python 指向 Windows 商店别名，用真实解释器指定，例如本机父项目已有的通用 Python：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start.ps1 -Python 'D:\agent_project\.venv\Scripts\python.exe'
```

该解释器只用来创建新环境；本项目不依赖父项目代码、账号或配置。

## 现在可以体验什么

1. 手动创建并确认自己的关注目标/条件；默认没有预置示例目标。可取消关注或恢复关注，保留历史判断与已确认日程。
2. 从已获取的新闻做中文二元词/英文词 BM25 召回，最多保留 8 篇候选；无候选时不调用模型。
3. 查看每轮不可变证据快照，分开核对摘要、归档原句、来源和采集时间。
4. 通过 SSE 查看阶段，取消任务；保存观察/已处理/不采纳决定。
5. 预览一项有限核实安排，明确确认后写入应用内日程；检查版本、冲突与重复批准。
6. 查看历史运行、耗时和保存结果。重启保留已完成记录；未完成任务标记中断，允许重新检查。
7. 在适配桌面浏览器的“新闻首页”查看十个公开来源，按频道/来源筛选、搜索、翻页和手动刷新；来源失败时保留已有资料。Hacker News 标注为社区来源，可单独选择，默认文章流不混入社区提交。
8. 阅读 GitHub Blog、阮一峰、爱范儿、MIT 的订阅正文；其他条目按需尝试网页正文提取，支持图片、链接、代码和表格。展示来源配图，缺图时显示标注“非文章配图”的来源标识；GitHub Blog 使用官方 Octicons 标识。长标题完整换行。
9. 在来源筛选、新闻卡片/列表与独立阅读面板之间浏览；布局偏好保存在当前浏览器。窄屏打开阅读时保留列表，返回后继续浏览。
10. 在分栏目标工作台查看本轮候选、判断、待核实条件与用户决定；编号引用直接定位保存的摘要或片段，日程仍须明确确认。
11. 按待完成/已完成筛选应用内日程，按目标名称和状态筛选检查记录。界面设计参照与验收范围见 [UI 重建记录](docs/UI_REBUILD.md)。

来源包括中新网、IT之家、36氪、Solidot、爱范儿、极客公园、MIT Research、GitHub Blog、阮一峰的网络日志、Hacker News 官方 API。服务运行时自动获取到期来源：中新网/IT之家/36氪/HN 每 10 分钟，Solidot/爱范儿/极客公园/GitHub Blog 每 15 分钟，MIT/阮一峰每 30 分钟。首次启动立即尝试；重启读取保存的下次获取时间，未到期不重复抓取。页面每 5 秒同步本地状态，不代表上游每 5 秒更新。设置 `NEWS_AUTO_REFRESH=false` 可关闭后台获取，手动刷新仍可用。服务停止期间不会抓取；这不是独立调度服务。

运行时来源设置在 `data/live_sources.json`，原始迁移目录 `data/sources.json` 保持原字节。刷新支持条件请求、URL 去重、首次发现/最近看见时间及来源成功/失败状态。RSS 描述、RSS 正文片段、社区文本分别标注；未把外链全文写入正文证据。HN 保存社区提交时间及讨论链接，原报道链接另存，不能把提交时间当作报道发布时间。新闻自动获取不创建目标检查、不调用模型、不写日程。

配图补全会读取有限原文 HTML，查找分享图或内容图片，Reddit 帖子使用官方 oEmbed 与嵌入预览。图片单独缓存在 `.local/media/`，不改变文字证据哈希或历史快照；设置 `NEWS_MEDIA_FETCH=false` 可关闭自动补图。来源拒绝访问、原文没有图片或本机网络不可达时，不能保证有配图。代理、DNS 回退与数据发送范围见 [数据说明](PRIVACY.md)。

中新网按普通新闻正文或图集当前照片/说明的范围取图，排除导航、客户端广告及其他新闻推荐。封面校验实际图片尺寸与结构，两边至少 120 像素；过小或损坏的旧成功缓存会失效并重新获取。缓存版本更新时保留经过尺寸校验的有效封面，同时后台复核。正文确实无图时使用来源标识。阅读器使用同一正文边界，图集保留当前照片和说明。

阅读正文优先使用上述四源在 RSS/Atom 中提供的内容；无可用订阅正文时，打开文章会按需读取公开原网页并通过 Trafilatura 提取。先规范化懒加载图片，再转换为允许的结构节点，前端不执行原站脚本或注入原始 HTML。阅读缓存保存在独立的 `article_reading` 表，不扩大模型证据上下文，不改变已有运行快照；“保存的证据片段”仍是当轮引用范围。网页提取不保证完整，失败时保留摘要、片段和原文链接。`NEWS_READING_FETCH=false` 关闭网页正文补抓，已缓存订阅正文仍可阅读。RSSHub 未部署，未使用无法验证的公共实例替代官方来源。

公开可访问不代表可任意转载；本地订阅与公开再发布的内容授权须分别核对，尤其不要直接建立全文镜像。

正常启动不再装入演示目标或 26 条演示归档。旧库中未使用的示例目标会移除；带有历史记录的示例会退出关注列表，历史快照、决定与已保存日程保留。用户创建的目标和已编辑为个人目标的示例不受清理影响。日常环境使用 `DEMO_SEED=false`；显式开启示例仅供隔离开发测试。原始 `data/archive/articles.json` 保留迁移溯源，只供隔离测试、评测及模型验收使用，不进入日常检索。已移除的演示新闻不再默认展示或用作新检查上下文。

在“我的关注”的目标详情中点击“取消关注”，该目标会移出关注中列表，停止其排队或正在运行的检查。可从“已取消关注”列表恢复；恢复不会自动发起模型请求，旧版本提议仍需重新检查后才能新增日程。此操作不删除历史检查、决定或已经确认的安排，已成功日程的精确重试仍保持幂等。

默认 `baseline` **不调用大模型**。它只输出候选和核实提示，不证明适用性或语义变化；界面始终标记“BM25 开发基线”。此模式下的安排是“核实资料”，不包装为模型推荐的产品试用。

## 可选：接入自己的模型

复制配置后编辑 `.env`，不要把密钥写入源码或浏览器：

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

```dotenv
LLM_MODE=compatible
LLM_BASE_URL=https://你的兼容服务地址/v1
LLM_MODEL=你的模型ID
LLM_API_KEY=你的密钥
```

重启服务生效。适配器使用 `/chat/completions` 与 JSON object 输出模式；服务需要支持该接口格式。输出经 Pydantic 和本轮引用校验，失败最多纠正一次；鉴权/连接/超时错误明确失败，不静默替换成假模型回复。无候选不调用模型。

结构/引用校验不保证语义正确。真实服务的模型能力、费用、隐私政策和可用性由配置的服务决定。2026-10-16 已在用户授权后完成一次真实 DeepSeek 调用与隔离闭环验收，输入为公开示例目标和固定归档，不代表实时新闻质量评测。请求会发送目标、必要历史和候选证据，见 [PRIVACY.md](PRIVACY.md)。

### DeepSeek V4.1 Flash（官方 API）

[官方发布说明](https://api-docs.deepseek.com/news/news260910/)中当前模型 ID 是 `deepseek-flash`，接口根地址为 `https://api.deepseek.com`。在 [DeepSeek 控制台](https://platform.deepseek.com/api_keys)创建 API Key；只填写到本地 `.env`。

项目提供专用示例；已有 `.env` 时只参考模板修改对应项，不要覆盖已有密钥或数据库配置：

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.deepseek.example .env }
notepad .env
```

```dotenv
LLM_MODE=compatible
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-flash
LLM_API_KEY=填入你自己的密钥
LLM_THINKING=disabled
LLM_MAX_TOKENS=4096
LLM_TIMEOUT_SECONDS=180
MAX_CONCURRENT_CHECKS=1
```

保存后先停止原服务，再执行 `powershell -ExecutionPolicy Bypass -File scripts/start.ps1 -SkipInstall`。打开 `/api/config` 应显示 `mode: compatible` 与 `model: deepseek-flash`；这只证明服务读到了配置。进入目标发起新一轮检查，成功得到模型结果才完成真实接入验证；没有候选资料时不会发起模型调用。

[DeepSeek 默认开启思考模式](https://api-docs.deepseek.com/guides/thinking_mode/)。上述模板显式关闭思考，便于先检查 JSON 输出和引用校验。需要试验思考模式时设 `LLM_THINKING=enabled`，并按任务调整 `LLM_MAX_TOKENS` 和超时（例如 16384 / 300 秒；这只是起始预算，不保证任务完成）。通用服务默认使用 `provider_default`，不发送 DeepSeek 特有的 `thinking` 字段。第三方中转的地址、模型 ID 与思考参数以该服务文档为准。

### 真实模型闭环验收

命令默认只检查配置，不发起模型调用；可先生成发送内容预览：

```powershell
.\.venv\Scripts\python.exe -m cfaw_news.live_check
.\.venv\Scripts\python.exe -m cfaw_news.live_check --preview
```

核对预览后，显式执行真实调用（可能产生 API 费用）：

```powershell
.\.venv\Scripts\python.exe -m cfaw_news.live_check --run
```

每次验收创建独立的 `.local/live-checks/<id>/check.db` 与 `report.json`，只使用公开示例目标和 2026-10-13 固定归档，不加载个人数据库，不自动获取新闻或写日程。最多发送两次请求（含一次结构/引用修正）；鉴权、限流、超时和输出截断不会自动重试。检查覆盖真实结果、引用定位、脚本保存观察决定、无候选跳过模型及重启保留记录。详细范围、错误分类与本次结果见 [真实模型验收说明](docs/LIVE_MODEL_CHECK.md)。该命令不进入离线 CI 或 `verify.ps1`。

工作台可展开“本轮模型与用量”，查看请求/返回模型、耗时、修正次数及服务方返回的 Token。结果引用可直接打开对应摘要或片段；无候选明确标记未调用模型。未知用量不按零计费，实际费用以服务方账单为准。

## 开发与验证

```powershell
# 后端热更新；先完成首次安装
.\.venv\Scripts\python.exe -m uvicorn cfaw_news.main:create_app --factory --reload --reload-dir backend --host 127.0.0.1 --port 8000

# 另一个终端运行前端；/api 代理到后端
cd frontend
npm run dev
```

完整本地检查：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify.ps1
```

或者分别执行：

```powershell
.\.venv\Scripts\python.exe -m ruff check backend tests evals
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe evals/run_baseline.py
cd frontend
npm run build
```

评测入口输出 `.local/evals/baseline.json`。它用开发者手选的三组种子相关条目检查 Recall/MRR/nDCG 的计算和排序管线，**不是独立算法 benchmark**，不能作为泛化成绩。

SQLite 数据在 `.local/cfaw-news.db`。单进程服务支持本地并发任务，使用 `MAX_CONCURRENT_CHECKS` 限制；本版不使用多个 Uvicorn worker。备份时先停止服务，再备份 `.local/`。数据库结构仍是原型阶段，后续引入 Alembic 迁移。

## Linux 与 Docker

Linux：安装 Python、Node 后执行 `bash scripts/start.sh`。Docker 配置也已提供：

```powershell
Copy-Item .env.example .env  # 已有自己的 .env 时跳过，不覆盖密钥
docker compose up --build
```

Compose 仅将端口映射到本机，SQLite 使用独立 volume。本次 Windows 验证不代表 Docker 镜像或 Linux 已验收；具体本轮检查见 [验证记录](docs/VERIFICATION.md)。

## 项目结构

```text
backend/cfaw_news/        API、领域校验、SQLite、任务、检索、模型适配、来源获取
frontend/src/            React/TypeScript 工作台
data/archive/            原作品迁移的固定归档（保持原文件字节）
data/sources.json        原作品迁移的 28 个来源目录
evals/                  可复现 BM25 种子评测入口
tests/                  领域/接口/取消/版本/幂等/适配器测试
scripts/                跨平台启动与验证入口
docs/                   架构、迁移、规划和验证边界
.github/workflows/      已配置的 CI；远端运行需推送后确认
```

本次迁移没有携带旧平台的运行时、bundle、构建补丁、原生宿主、账号、私人记录或凭据。归档、来源、图标和署名的来历见 [迁移记录](docs/MIGRATION.md)；实现边界见 [架构](docs/ARCHITECTURE.md)。

后续先完善独立时序数据集与 BM25/Dense/Hybrid/Rerank 对照，再做可训练重排、证据变化判断和 Agent 策略，详见 [开发规划](docs/ROADMAP.md)。向量检索、训练、LangGraph checkpoint、独立周期调度、多用户鉴权尚未实现。本版是这些工作的可运行起点。

代码使用 [Apache-2.0](LICENSE)。原作品归属与新闻版权保留，见 [NOTICE](NOTICE)。
