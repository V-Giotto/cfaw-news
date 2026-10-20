# Annotation Guide v1 — dev01-guide-v1

适用：G1-PR2 DEV-01 合成试点；规范日期 2026-10-20。数据是 synthetic，
但标注动作必须由真实人完成。目前 A/B 未确认，不能把本手册的示例当作初标。
数据 annotation_version 暂沿用 synthetic-fixture-v1；guide_revision 单独冻结。

## 1. 管理员先做什么

1. 核对 dataset Manifest 的外部固定 SHA，运行 strict 校验。给每个信息包单独记 SHA。
2. 提供本手册、一个 as_of 的可见文档/段落、当时 persona、已知覆盖区间和空白表单。
   不提供 DEV-01/README、未来包、tests、Claim/事件参考文件、gold、模型输出或 A 的答案。
3. A/B 分别从最早时点开始。每次收回、冻结原始提交及哈希后，才给下一时点。
   包内给出所有当前可见版本；上一时点的旧引用保留，不以当前更正覆盖旧提交。
4. A 可为开发者，需承认知晓设计的偏差；B 必须是真实独立审阅者。是否到位由人确认。
   不能凭两个 ID、AI 多次调用或改写同一答案认定双人独立。若曾看到未来材料，记录污染。
5. A 初标之后可汇总困难问题；在 B 冻结前不向 B 展示 A 的答案。修手册要升版本，
   保留旧初标并按新版本重标，不能覆盖旧记录。

## 2. 每个时点的操作顺序

只依据包内资料判断；不搜索网页，不凭自己知道的后续发展补齐证据。

1. 列出可见的文档版本、来源及时间缺口。可见时间用 available_at，不用自报发表时间。
2. 对文档对标记关系并引用段落：exact_duplicate / syndicated /
   same_event_different_evidence / related_distinct_event / unrelated / uncertain。
   同 URL 同 hash 的重复观察不是第二份独立证据；same project 不是 same event。
3. 抽取一条只表达一个事实的最小主张，分清“来源说了什么”和“实际验证了什么”。
   使用自己的局部事件编号，不猜管理员参考 event_id。
4. 为每个引用分别记录定位与语义判断：supports / refutes / mentions / unknown。
   程序的 location=valid 只表示段落存在，semantic_support 仍为 not_measured，
   直到真实审阅者提交判断。合成测试题的预设答案不算真人评测。
5. 为 persona × step × 自己识别的事件填写四维评分、变化、层级及 graded relevance；
   写一句理由、段落引用、适用范围、未知项。信息不够就保留不确定，不补写世界事实。

## 3. 四维 0–3 量表

| 维度 | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| relevance | 与画像无联系 | 与宽泛兴趣弱相关 | 明确关联兴趣/工作 | 直接影响显式目标或硬约束 |
| potential_value | 无可说清的用途 | 有趣但用途不明 | 有合理应用/研究潜力 | 可能明显改变当前研究或工程选择 |
| novelty_to_persona | 已知且无增量 | 轻微补充 | 新事实或明确更新 | 新能力、关键约束或重大纠正 |
| evidence_quality | 无法追到来源 | 只有单方声称 | 官方原始材料或有限独立测量 | 多份实质独立直接证据且范围明确 |

不要将 source_type 或站点数量直接当作证据质量。官方“已发布”的直接公告可以核实
发布事实，但同一页的“所有任务更快”仍可能只有单方声称。两份媒体抄同一新闻稿，
不使“性能更快”成为两份独立佐证。evidence_quality 必须按具体主张解释。

graded_relevance 独立填写：0=无推荐价值；1=弱/备查；2=明显值得了解；3=高优先级。
不是四维平均，也不自动由 tier 推导；明显矛盾需解释并人工复查。

## 4. 变化与层级

| material_change | 操作标准 |
|---|---|
| new | 此时首次可见的事件；新增转载不是新事件 |
| meaningful_update | 新的独立证据或重要限制足以改变认知；热度和改写通常不够 |
| no_change | 对已知事件无实质新事实；只针对可观察范围，不是全世界无更新 |
| correction | 有依据的更正改变先前主张；不要扩大为全产品撤回 |
| withdrawal | 来源明确撤回某承诺或发布；找不到网页不算撤回 |
| insufficient | 无法判断有无变化；不等于 no_change |

focus：影响大或强相关且依据可核对；重要风险可突出但要明确不确定性。
radar：项目/论文存在且有潜力，收益尚需验证。
archive：普通信息、无增量转载或低优先级但可备查。
hold：来源不明、明显错误、无法合法展示或信息不足。

## 5. 边界练习（通用例子，不提供 DEV-01 答案）

- 某工具官方只写“新版本可下载”：可支持 release_fact，不能支持“速度提升百万倍”。
  引用 p1 确实存在时，定位成功与该虚假结论的语义不支持必须分开填写。
- 两个站点转述同一新闻稿：syndicated；不能标 independently_supported。
- 测试只在 Linux/GPU、指定版本和三个任务上观察到收益：只支持该 scope。
  不能扩为 Windows/CPU、所有版本或所有任务；未测平台写 unknown，不写“不支持”。
- 官方明确更正“某平台未支持”：可以 refute 先前的平台宣称，不能用这份材料修改过去标签。
- 同一项目另发许可证公告与模型发布：可能 related_distinct_event，不按名字强行合并。
- 同一证据对“找研究灵感”的人可有价值，对“必须本机 CPU 可用”的人价值可不同；
  是否存在发布和实验的技术事实不随 persona 改变。
- included / rendered / opened 都不等于已理解；只有显式提供的 knowledge_known 可作已知。
- service_offline / failed / unknown 只说明覆盖不足；没有搜到不能推断世界无变化。

## 6. 提交与仲裁

使用 DEV-01/annotation_template.json 的空白结构。每个提交包含真实匿名 annotator_id、
实际 submitted_at（不是场景 as_of）、guide_revision、packet_sha256、step/persona、
局部事件编号、四维/graded 评分、关系、主张引用、scope 和不确定性。
空白模板不是有效 Annotation，也不计为已完成。自报“独立”不是独立性的程序证明。

初标文件只追加。B 冻结后才比较 A/B；保留关系分歧、四维分歧、tier/变化分歧及理由。
仲裁记录引用原始 annotation_id，写 final_label、reason、adjudicator_id 和实际时间；
无法裁决保留 unresolved / insufficient。不得根据算法推荐调标签。当前无真实提交，
annotations/adjudications/gold 都应为空，不创建假仲裁。

两人完成后才计算：关系一致率及 positive pair P/R/F1；0–3 的 quadratic weighted κ；
tier/变化的 κ、各类混淆矩阵、样本数和原始一致率。κ≥0.70 是观察目标；低于目标
先修规范并在新版本重标，不删除争议样本凑数。PR2 不实现这些 PR5 指标。
缺 A/B 或未完成语义审阅时分别写 not_started / pending / not_measured，不能报 0% 或 100%。
