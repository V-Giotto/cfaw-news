# 真实模型闭环验收

## 本次结果

2026-10-16 18:27:53—18:27:57（Asia/Shanghai），经用户明确授权，将预览中的公开示例目标及固定归档证据发送至 `https://api.deepseek.com/chat/completions`。使用本项目已有配置，没有输出或改写密钥。

| 项目 | 实测结果 |
| --- | --- |
| 请求模型 / 返回模型 | `deepseek-flash` / `deepseek-flash` |
| 输入 | “每周两小时，试一个省时的 AI 工具”公开示例；从 26 条归档召回 8 篇 |
| 调用 | 1 次真实 HTTPS 请求，HTTP 200；0 次格式修正 |
| 配置 | `thinking=disabled`；单次输出上限 4096；单次 HTTP 超时 180 秒 |
| 耗时 | 供应商请求 3940 ms；Provider 全程 4037 ms；任务全程 4045 ms |
| 服务方用量 | 输入 4247、输出 657、总计 4904 Token；缓存命中 1024、未命中 3223 |
| 输出 | 首次判断 `outcome=update`、`change_kind=new`；指出设备、语言效果、账号/套餐仍需核实 |
| 引用 | 8 处引用均能定位到本轮快照的已保存片段 |
| 用户决定 | 验收脚本保存 `watch`，重读及重启后仍存在；不是替用户作出真实生活决定 |
| 无候选 | 独立目标返回证据不足，`model_called=false`，没有提议 |
| 持久化与行动 | 结果、证据、指标和决定重启后保持一致；日程始终为 0 |

Provider 返回的版本指纹为 `aeb56401ca74e127821c4f9126dcb669`。响应模型名与指纹可记录服务返回的身份信息，不保证供应商长期固定相同权重。

本机报告：`.local/live-checks/c1f89bbdf1174d23be928dfb38d7df79/report.json`；同目录保留独立数据库、`model-usage.png` 和 `citation.png`。这些本地文件不提交 Git。

## 范围与边界

验收走生产 `create_app`、API 路由、RunEngine、CompatibleProvider、SQLite 与实际外部 HTTPS；验收客户端通过进程内 ASGI 调用本地路由。随后启动独立回环 Uvicorn 服务，在浏览器查看实际保存的真实结果、模型用量和引用片段；浏览器检查没有再发起模型请求。

证据是 2026-10-13 采集的迁移归档，本次没有重新获取原文或核实其当前事实。归档编写文本、保存的原句和模型解释继续分开。引用校验仅证明 ID/段落属于快照，并不证明引用支持每一句结论；一次真实模型成功也不构成语义质量、算法提升、长期可用性或实时新闻端到端的验收。

真实接口没有人为制造 401、429、余额不足、超时或截断；这些故障路径通过 HTTP mock 验证。取消和目标修改后的迟到结果保护通过隔离测试验证，不据此宣称已验证供应商的取消计费行为。实际费用以服务方账单为准，本次只记录响应 usage，没有估算价格。

## 复现

在项目自己的 `.env` 配置 `LLM_MODE=compatible`、地址、模型和密钥。不要覆盖已有配置或读取其他项目的凭据。

```powershell
# 仅检查配置；不发送请求
.\.venv\Scripts\python.exe -m cfaw_news.live_check
# 导出公开样例预览；不发送请求
.\.venv\Scripts\python.exe -m cfaw_news.live_check --preview
# 核对发送范围和费用预算后，执行真实验收
.\.venv\Scripts\python.exe -m cfaw_news.live_check --run
```

`--run` 每次新建隔离目录，不使用 `DATABASE_URL` 指向的个人工作区。关闭来源自动刷新和配图；使用实际模型配置发送一个公开目标及候选。检查最多两次 HTTP 请求；空候选及重启检查不产生额外模型调用。成功退出码为 0；失败退出码为 1，并保存失败检查、可用指标与固定错误说明。未配置 compatible 模式时拒绝真实调用，不以 baseline 结果替代验收。

## 指标与故障

每次请求保存开始时间、耗时、HTTP 状态、结束原因、服务返回的模型/响应 ID/版本指纹；任务保存候选数、总耗时、请求数、修正次数和结构/引用校验结果。usage 只保留允许的非负整数计数，不保存原始服务错误、请求头、密钥或思考文本。失败、取消或目标过期时，已返回的用量仍保留，但不能发布判断结果。

| 错误码 | 处理 |
| --- | --- |
| `authentication` | HTTP 401/403；检查密钥与权限，不自动重试 |
| `quota` / `rate_limit` | HTTP 402 / 429；检查余额、额度或稍后重试 |
| `provider_http` / `connection` | 其他 HTTP 错误 / 网络失败；不发布结果 |
| `timeout` | 请求超时；服务方可能未返回用量，保持未知 |
| `output_truncated` | `finish_reason=length`；即使 JSON 恰好可解析也拒绝发布，不以相同预算重试 |
| `content_filtered` | 服务方未提供可用结果，不发布判断 |
| `invalid_output` | 非法 JSON、缺少最终内容、schema 或引用不合格；最多修正一次，两次仍失败则拒绝发布 |
| `input_too_large` / `configuration` | 输入超过 64KB / 无效地址；明确失败 |
| `cancelled` | 取消中的请求保留已知指标；用量可能不完整，不发布迟到结果 |

JSON object 请求格式和输出预算处理参考 [DeepSeek JSON Output 官方说明](https://api-docs.deepseek.com/guides/json_mode/)。离线回归入口仍为根目录 `AGENTS.md` 中的四项检查，不执行付费模型请求。
