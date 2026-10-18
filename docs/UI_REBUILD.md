# UI 重建记录

日期：2026-10-17。范围：独立项目 React 前端，沿用现有 API 与领域规则。

## 设计参照

| 参照 | 融入方式 |
| --- | --- |
| [Folo](https://github.com/RSSNext/Folo) | 保留应用导航；新闻按来源筛选、文章列表、正文阅读分栏；目标列表与判断正文独立滚动。 |
| [Karakeep](https://github.com/karakeep-app/karakeep) | 新闻卡片/紧凑列表切换、真实配图、来源标记、标题与摘要层级。浏览器只保存布局偏好。 |
| [Vane](https://github.com/ItzCrazyKns/Vane) | 候选来源卡片、展开全部候选、结果引用编号；点击引用定位本轮快照的摘要或片段。 |

采用这些产品的布局与交互思路，组件与样式在本项目中编写。没有引入其运行时，也没有复制其整套组件代码。引用集合属于本轮结果，未宣称已建立每句话与某条引用之间的对应关系。

## 实现范围

- `NewsLibrary.tsx`：来源与频道筛选、搜索、分页、刷新与来源状态、卡片/列表、上/下一篇、展开阅读；切换筛选关闭阅读，避免旧来源正文与新列表混淆。
- `ArticleReader.tsx`：共享阅读与证据核对；保留归档文本、RSS 片段、社区文本区别，显示采集信息与原始链接；引用片段高亮并获得键盘焦点。
- `GoalWorkspace.tsx`：目标列表、可展开条件、检查进度/取消、候选证据、判断、下一步、待核实条件、用户决定、审批入口和模型用量。
- `ActivityPages.tsx`：日程状态筛选及完成操作；检查记录按目标名称/状态筛选，回到指定历史运行。
- `styles.css`：浅色工作区、紫色选中与动作强调；保留桌面导航，窄屏使用图标导航与单栏阅读。

## 验收

执行命令：

```powershell
.\.venv\Scripts\python.exe -m ruff check backend tests evals
.\.venv\Scripts\python.exe -m pytest -q --basetemp .local/pytest-ui-20261017-unsandboxed
.\.venv\Scripts\python.exe evals/run_baseline.py
cd frontend
npm run build
```

Ruff、92 项 pytest、BM25 种子检查与 TypeScript/Vite 构建通过。pytest 保留一项上游 TestClient 弃用提示。Windows 沙箱内默认临时目录创建失败，项目内临时目录又遇到 asyncio 回环初始化阻塞；完整 pytest 在沙箱外本机执行，不是业务断言失败后绕过测试。

实际浏览器使用 `.local/ui-review/review.db`，只复制 671 条已有公开新闻缓存及其配图/来源状态，重新生成三个公开示例目标；未复制个人目标、运行、决定或日程。模型为 baseline，自动新闻获取与自动补图关闭；没有新增真实模型调用。公开缓存不是本次重新联网获取或事实复核的结果。

浏览器检查覆盖：来源筛选、搜索、卡片/列表与刷新后偏好保留、分栏阅读、长标题、真实缓存图片、引用定位和键盘焦点、全部候选展开、观察决定、预览/明确批准后写入隔离日程、标记完成、历史搜索/状态筛选与回看。桌面与 390px 窄屏检查未发现文档横向溢出。

本地浏览器截图保存在 `.local/ui-review/`，不提交 Git。原有数据与业务验收边界仍见 [验证记录](VERIFICATION.md)。
