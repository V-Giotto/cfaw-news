# DEV-01～05 AI 标注规则 ai-dev-guide-v1

生效：2026-10-23。默认执行路径为 `ai_development`。完整规则见仓库内
`docs/plans/G1_AI_DEVELOPMENT_RULES.md`。

AI 可以完成初标、事件关系、主张、评分、引用语义判断、复核及裁定，单个 AI 即可。
V3 的评分、证据方向、scope、tier 和变化定义继续使用；其第 1/10 节的真人身份、
本人录入、双人冻结、不得由 AI 作答等要求仅用于可选的 `human_research` 路径。
本包附带 V3 原文用于保留冻结语义，当前 AI 执行流程以本文件为准。

1. 逐个 `as_of` 使用单步包，保留原稿及复核差异。不能用未来证据改写过去判断。
2. 单轮初稿可以由同一 AI 继续做证据复核；无须等待真人或另一个模型。已看参考答案、
   未来材料或同一轨迹全貌的，记录已知材料，不冒充盲标或独立验证。
3. 新批次附来源记录：`executor_type=ai`、真实模型/会话（无法取得写未知）、
   `guide_revision=ai-dev-guide-v1`、包 SHA、实际生成时间、初稿/复核文件 SHA、修订理由。
   材料 `record_origin` 仍按实际 `real / synthetic` 填写，合成场景时间不是实际提交时间。
4. 初稿可参考随包空表的字段与 V3 词表。新 AI 记录与来源信息放在单独开发目录，
   不当作真人 submission，不将 `real_human_confirmed` 设为 true。
5. 本批次的可执行参照使用 SyntheticExpectation 契约和 fixture_expectations 角色，
   在新 dataset revision 下冻结后用 `--label-source synthetic-fixture` 计算开发指标。
   原始 AI 理由、引用支持判断、复核差异另外保存；该简化参照不代表语义支持已测。
6. AI 复核后的不确定项可保留 uncertain/insufficient；单次输出不计算双标 κ。
   多轮差异只作内部诊断，不冒充真人一致性或算法收益，不依据算法分数调标签。
7. `annotations audit/agreement` 保留原真人审计语义。其 human_gate=BLOCKED
   不阻塞 AI 开发验收；总验收使用默认的 `acceptance --profile ai_development`。

完成条件是五轨迹开发标签覆盖与全部必需技术门槛实际通过。仅修改规则、导出空表或
存在旧开发期望，不代表新 AI 标注、真人研究或 G1 总验收已完成。
