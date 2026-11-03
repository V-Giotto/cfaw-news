# ADR 补充：PR3 材料语义、Persona 连续性与请求控制

2026-11-02。修复当前 PR3 独立审查的两项 P1 和一项 P2；待独立复审。
本补充替代 G4_RUNTIME_BRIDGE_V1.md 中“excerpt_only 改为 quoted_excerpt”及
“旧回放时刻不早于当前 Persona”的决定。旧文档与验收记录保留原字节作为历史。

## 材料类型和许可分开

G4DocumentVersion.content_kind 原样投影到 CandidateDocumentVersion。rights/retention
只约束保存、引用和展示，不是原始声明的来源证明。RSS feed_summary 即使允许引用片段，
也不能变成 quoted_excerpt/publisher_text。

当前冻结 native G2 对有正文的 excerpt_only 要求 quoted_excerpt；在不能保留原材料语义
并通过该契约时，返回 raw_news_only / G4_NATIVE_G2_REJECTED:RIGHTS_USE_NOT_ALLOWED，
没有 G2 stages、G3 context/ranking/plan 或虚构 Archive snapshot ID。原始不可变版本和
安全来源信息仍在 result.input，供后续原始资讯通路使用。

经合法绑定的 permitted + fulltext 对照可保留 feed_summary 通过正式 G2；主张仍为
secondary_material、claim_type=other、verification_state=unverified，保留 claim limitations
及 validation.coverage_gaps 中的 primary_text_unavailable。不得把原始 feed 归属为发布方声明。
支持 excerpt-only 摘要引用需要另案注册能保留 secondary-material 语义的契约，本次不改冻结 G2。

## Persona 不改变文档回放前缀

G2 回放时刻取每个真实 document available_at 加最终 as_of，不再取与当前 Persona 时间的
max。当前封套只有一个 Persona，没有历史 Persona 或可信原生前置状态。因此必须满足：
当前 Persona.available_at <= 首个文档 available_at。满足条件时，每个捕获前缀正常经过
原生证据阶段；只更新画像版本号、且画像仍在第一步可用，不改变 birth anchor 或删掉旧 claim。

不满足条件时返回 evidence_not_ready / G4_RUNTIME_PERSONA_HISTORY_REQUIRED；native 入口也
独立拒绝。保留完整输入版本、coverage，不签发新的事件身份、快照、排名或计划。
这明确阻断连续性；没有补造早期画像、倒填 Persona.available_at、静默新生事件或伪造旧状态。
当前并未实现对“用户在更正后保存画像”的连续推荐支持。后续必须输入合法历史 Persona，
或注册/验证与画像解耦的可信原生状态，不能用此错误码当作已完成该产品能力。

## 一个请求的 Control 贯穿严格重算

Control 移入 runtime_control.py，runtime.Control 保持兼容导出。ContextVar 管理同步请求
作用域；run、derive、validate_context、rank_runtime、plan_fields 和模型验证共享同一对象
及同一个 deadline，不在内部重放重置。所有 native 重放使用实际 Control.check，移除空
checkpoint。作用域 finally 退出，取消/失败不会污染下一请求。

RuntimePlan/RuntimeResult 验证保留重新计算和全字段对比；Pydantic 直接导入可用
model_validate_json(..., context={"control": control}) 传递请求控制。嵌套作用域拒绝替换
已有 Control。入口、native 输入验证后、各原生阶段、逐候选排名、预算及模型比较完成后
均检查取消与截止时间。故障注入覆盖 ranking、budget、plan-model、result-model 内部重放，
以及 native 输入验证结束的边界；触发后不得开始新的分组步骤。

这仍是同步 cooperative 停止：已经进入的一个纯函数调用可以完成，无法硬抢占它。
本次没有异步 worker、持久化任务、HTTP、数据库写入或发布。PR4 的任务/CAS/取消竞态仍需实现。

## pin 与兼容

runtime_local_v1 保持输入字段布局；注册策略升级为 g4-runtime-ranking-policy-v2，显式绑定
preserve-original-kind-v1、historical-prefix-required-v1、request-scoped-cooperative-v1。
旧 ranking/config pin 和旧结果不能改 pin 后宣称兼容；都须用本策略重新计算。
当前 Schema 放在 evals/intelligence_g4/schema/pr3_review_fix/，旧 pr3/ Schema 原字节保留，
不能作为修复后契约承诺。native engine、G2/G3 源码和 g3-grounded-fact-signature-v2 policy
SHA 保持原值；默认 B4、P1 显式实验和预算未校准状态均不变。

此轮证据为 AI-authored mock 工程验证，不是线上新闻、真实许可或用户效用证明。
