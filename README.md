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

1. 三个可编辑的示例目标，或手动创建并确认自己的目标/条件。
2. 从初始 **26 条历史归档**做中文二元词/英文词 BM25 召回，最多保留 8 篇候选。
3. 查看每轮不可变证据快照，分开核对摘要、归档原句、来源和采集时间。
4. 通过 SSE 查看阶段，取消任务；保存观察/已处理/不采纳决定。
5. 预览一项有限核实安排，明确确认后写入应用内日程；检查版本、冲突与重复批准。
6. 查看历史运行、耗时和保存结果。重启保留已完成记录；未完成任务标记中断，允许重新检查。
7. 在适配桌面浏览器的“新闻首页”查看首批八个公开来源，按频道/来源筛选、搜索、翻页和手动刷新；来源失败时保留已有资料。
8. 展示来源配图，缺图时按需从公开原文或 Reddit 官方嵌入预览补全并本地缓存；分别提示无配图、来源限制和网络故障。长标题完整换行。

首批为中新网、IT之家、36氪、Solidot、爱范儿、极客公园、MIT Research、Hacker News 官方 API。服务运行时自动获取到期来源：中新网/IT之家/36氪/HN 每 10 分钟，Solidot/爱范儿/极客公园每 15 分钟，MIT 每 30 分钟。首次启动立即尝试；重启读取保存的下次获取时间，未到期不重复抓取。页面每 5 秒同步本地状态，不代表上游每 5 秒更新。设置 `NEWS_AUTO_REFRESH=false` 可关闭后台获取，手动刷新仍可用。服务停止期间不会抓取；这不是独立调度服务。

运行时来源设置在 `data/live_sources.json`，原始迁移目录 `data/sources.json` 保持原字节。刷新支持条件请求、URL 去重、首次发现/最近看见时间及来源成功/失败状态。RSS 描述、RSS 正文片段、社区文本分别标注；未把外链全文写入正文证据。HN 保存社区提交时间及讨论链接，原报道链接另存，不能把提交时间当作报道发布时间。新闻自动获取不创建目标检查、不调用模型、不写日程。

配图补全会读取有限原文 HTML，查找分享图或内容图片，Reddit 帖子使用官方 oEmbed 与嵌入预览。图片单独缓存在 `.local/media/`，不改变文字证据哈希或历史快照；设置 `NEWS_MEDIA_FETCH=false` 可关闭自动补图。来源拒绝访问、原文没有图片或本机网络不可达时，不能保证有配图。代理、DNS 回退与数据发送范围见 [数据说明](PRIVACY.md)。

公开可访问不代表可任意转载；本地订阅与公开再发布的内容授权须分别核对，尤其不要直接建立全文镜像。

初始资料来自原作品的 2026-10-13 归档，保留来源与原始说明，**本次没有重新联网验证其事实或当前可用性**。示例目标为公开演示场景，不是迁移的个人数据。

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

结构/引用校验不保证语义正确。真实服务的模型能力、费用、隐私政策和可用性由配置的服务决定；本次未使用个人密钥验证真实模型。请求会发送目标、必要历史和候选证据，见 [PRIVACY.md](PRIVACY.md)。

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
