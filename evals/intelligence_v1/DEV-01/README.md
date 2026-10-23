> Current policy (2026-10-23): this story uses the explicit AI development batch in `../labels/ai_development/`. Original/review records and executable references are new AI-authored material; old human submissions and expectations are archived. Earlier human distribution/status statements below describe historical preparation only. Single-AI review is not blinded or independent validation.

# DEV-01 — 合成开发试点

这是 G1-PR2 §11.2 的正式 pilot / developer data，**不是历史新闻或真实实验**。
Cedar Agent、TinyBench-3、发布者、媒体和测试者全部虚构。日期仅为合成场景时钟，
不是实际采集时间、标注提交时间或许可核验时间。没有联网、LLM 调用或业务库输入。

事件家族为 `family:dev01`，全部派生材料、persona 反事实和后续标签必须留在 dev。
参考发布事件与同项目另一个公告是两个不同事件；它们的参考 ID 只用于评测。

## 研究问题与可见性

D0 = 2026-01-01；下列 as_of 都是当日 12:00:00Z，边界包含相等时间。
字母是无结果标签的文档身份；a:2 是 a:1 的正文更正，不能改写 a:1。

| step | 允许看到的版本（按 document_id 排序） | 对照意图（仅管理员可看） |
|---|---|---|
| D0 | a:1 | 发布存在；性能和平台是厂商说法 |
| D1 | a:1, b:1 | 新转载不是新事实；原文再次观察仍指向 a:1 |
| D3 | a:1, b:1, c:1, d:1 | 三份转载共用上游，不是三份独立测量 |
| D4 | a:1, b:1, c:1, d:1, e:1 | 测试只覆盖 Linux/GPU、v1.0、TinyBench-3 |
| D5 | a:2, b:1, c:1, d:1, e:1 | 官方更正 Windows CPU 支持；早期回放不知此事 |
| D8 | a:2, b:1, c:1, d:1, e:1, f:1 | 普通新公告与旧但重要的测试/更正同时保留 |

`versions/observations.jsonl` 留原始观察与重复观察；共七个内容版本，八次观察。
c/d 自报 D2 发表、D3 才观察到；D2–D3 的 service_offline 区间仍是未知覆盖。
persona 同一身份有两个历史版本，D5 起明确增加 Windows CPU 约束。
候选不按 time_window_start 截掉旧材料。关系中的 evidence_at 不早于两端版本可见时间。

## 来源与权利

来源登记中的 dev01-official / dev01-media-b/c/d / dev01-test 都是 synthetic。
正文为本项目原创合成测试文字，允许作为仓库测试材料使用；URI 使用 synthetic://。
媒体段落明确表示抄录同一官方稿；独立测试段落明确表示自行测量及其局限。
这种“独立性”是场景设计，**不是对任何真实研究者或产品的核验**。
原 PR1 GitHub Blog 登记仍为权利 unknown、只允许 metadata，DEV-01 不使用其正文。

## 人工状态与使用限制

当前 A/B 都未由人确认，初标、gold、仲裁文件为空。预置的 Claim 和事件关系是
合成设计参考，不是人的提交，不得用于计算双标一致率或证据支持准确率。
semantic_probe.json 的 unsupported 是人为设计的测试期望，不是独立人工审阅结果。
真实语义测量仍为 not_measured；结构定位通过绝不自动改成 semantic support passed。

此文件、完整数据、参考事件/Claim/关系、测试预期和可见版本总表仅给管理员。
标注者只领取一个已校验 as_of 的信息包及空白表单，不领取完整故事或未来包。
请依 ANNOTATION_GUIDE.md 记录真实初标；AI 不填写匿名“第二人”结果。

本 PR 没有 loader/replay/ranker/metrics CLI、PR3–PR5 或 G1-a 完成声明。
