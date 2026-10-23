# G1 人工作答手册 v3

规则标识：`g1a-guide-v3`；新批次标注版本：`g1a-annotation-v2`。
规则内容依据用户2026-10-22的十条规则、六项确认及两项协议选择定稿。

本文件是新人工批次的规则文件；当前冻结运行包仍为v7 / g1-pr5-3，尚未启用本手册或建立新批次。
在实际单步包、手册哈希、批次资格和接入版本登记完成前，不开始正式提交。
旧包、旧手册、旧初标及旧一致性按原版本保存，本规则不追溯改写它们。

## 1. 谁作答、怎样留原稿

- A/B必须是两名不同真人，各自阅读材料、填写全部标注内容并亲自提交。初标前不看对方答案、未来步骤、参考标签或算法输出。
- 初标和support review都必须由真人阅读原文；AI生成、AI改写、同一人使用两个ID、管理员代填不算人工证据。
- 所有录入均由标注者本人完成。管理员提供空表、当前单步包、校验器与错误位置；不代录、不补分、不替写claim、理由或scope。
- 本人可以使用只读语法校验与hash工具；这些工具不得自动生成判断、补齐缺项或改写原文件。
- 双方独立提交并冻结后，再发下一步材料。讨论和仲裁另存记录，不覆盖原稿或讨论前一致性。
- 记录真实收包、提交、冻结和复核时间及UTC偏移。不能用文件mtime替代未经核实的发包时间，不能把重冻时间当首次提交时间。
- 先披露已接触的未来材料、他人答案或参考标签。看过完整轨迹后的重做须披露，不宣称全新时序盲标。

## 2. 分开写两层最小主张

- occurrence claim：某个发布方确实说过X。
- capability claim：X在技术上成立。
- claim_text必须写清判断哪一层。可用`[occurrence]`、`[capability]`前缀帮助辨认，原始文字由本人填写。
- 将平台、性能、可获取、可依赖等不同命题分别写成最小claim，避免用一句复合主张混合评分。
- 官方页面可支持“发布方作出了这一声称”，不能仅凭其自述就支持“该技术能力已成立”。

引用方向始终相对于当前claim判断。同一段落对occurrence claim可以是supports，对对应的capability claim可能只是mentions。
不得把“厂商说过”这一有证据的事实，等同于“其能力已获得验证”。

## 3. 人工引用方向与支持判断

人工direction只用：`supports / contradicts / mentions`。

- supports：在明确范围内支持当前claim。
- contradicts：反驳当前claim。
- mentions：只提及或转述，不构成对当前claim的语义支持。

semantic_support独立填写：

- supported：引用段落在其适用范围内真正支持该claim。
- unsupported：只有断言/提及，或存在反证。
- uncertain：部分支持、语义歧义或证据不足。

mentions永远不计为支持。厂商自述对技术能力成立只能记unsupported/uncertain；对厂商确实说过才可记supported。
每条引用必须在当前as_of前可见，并准确指向文档版本和段落。可以引用已保存的历史版本比较更正；不能借未来材料改写过去判断。

## 4. scope与局限

逐条写清版本、平台、任务、测试条件、样本量/运行次数和基线。
纯发布事实等不适用的项目写“不适用”并说明；原文没有提供的项目写“未提供”，不补造条件、样本或基线。
限定范围的证据不能支持未限定claim。未限定的确定性主张只能得到窄范围结果时记unsupported；主张本身是可能性且证据不足时可记uncertain。
保留原始数据、方差、置信区间或生产验证等缺失的局限，不能由转载数量替代独立证实。

## 5. 评分与信息优先级

四维和graded_relevance分别填写0–3，graded_relevance不取四维平均值。

| 维度 | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| relevance | 与Persona无关 | 弱相关 | 明显关联兴趣或工作 | 直接关联明确目标或硬约束 |
| potential_value | 对Persona无明确潜在使用价值，或硬约束下不可用 | 有趣但用途不明 | 有合理现实或研究使用潜力 | 可能显著改善实际工具使用或研究工作 |
| novelty_to_persona | 已知且无增量 | 轻微补充 | 新事实或明确更新 | 新能力、关键约束或重大纠正 |
| evidence_quality | 无法追溯 | 单方声称 | 官方原始材料或限定范围独立验证 | 多份实质独立的直接证据且范围明确 |
| graded_relevance | 无推荐价值 | 弱参考/归档价值 | 值得知道 | 当前高优先级 |

potential_value只衡量工具的潜在使用价值，不衡量这条信息的决策价值。
工具因硬约束不可用时potential_value=0；排除不合适工具本身不加potential_value。
首次、可行动、直接影响硬约束的排除信息，其价值可以体现在focus / graded 3；已知或重复的排除可记archive / graded 1。

## 6. tier

- focus：重要、可核查，当前应优先阅读或据此行动。
- radar：潜在有用，但证据或适用范围有限。
- archive：参考或已处理的排除记录，当前无需继续主动行动。
- hold：信息当前不可用、不可验证或太不确定，暂不推荐。

工具不适配与信息是否值得关注分别判断；potential_value=0不自动推出hold。
每步按当时Persona、已知事实、投递/曝光、覆盖和可见证据判断，不按固定日期或算法结果套tier。
曝光不等于理解；没有新增信息也不能凭空断言已理解。

## 7. 事件分组及变化

按底层事件和文档成员分组，不依赖同项目名称、局部编号或列表位置。
转载、改写和复制不构成独立事件。测同一产品/同一主张的独立测试作为同一事件的新证据。
明确属于另一项公告、不是某版本更新的材料单独成事件。事件成员使用当前单步可见的最新版本，claim可引用此前已见旧版本。

material_change：

- new：该事件首次可见。
- meaningful_update：实质新事实。
- no_change：仅在已观察覆盖内没有增量。
- correction：有据可查的更正。
- withdrawal：明确撤回。
- insufficient：证据不足、未观察窗口或缺口未知。

缺口不能当作no_change；无法判断时使用insufficient。可以记录实际观察到的新事实，不将其外推为对所有来源的完整覆盖。

## 8. 固定人工relation词表

| 人工词 | 定义与left/right方向 |
|---|---|
| correction_of | left为更正材料，right为被更正的旧材料 |
| superseded_by | left为被取代的旧材料，right为取代它的新材料 |
| syndicated_republish | left为转载，right为其来源材料 |
| rewritten_derivative | left为同源改写，right为其来源材料 |
| press_material_copy | left为新闻材料复制，right为其来源材料 |
| independent_test_of | left为独立测试，right为其测试的产品/主张对应材料 |
| separate_announcement_no_update | left为另一个公告，right为用来对比且未被其更新的已有公告 |

新增类型先登记定义；不自由造同义词，也不为通过校验强填相近类型。
记录判断依据、证据上下文时间、来源与局限。同源转述不构成独立测试。

## 9. 兼容映射与原始证据

人工原词保留在本人提交的原文件中。只读适配在内存中检查下列机器投影，不覆盖原稿：

- contradicts → refutes；supports、mentions不变。
- syndicated_republish / rewritten_derivative / press_material_copy → syndicated。
- correction_of / superseded_by / independent_test_of → same_event_different_evidence。
- separate_announcement_no_update → related_distinct_event。

机器投影不能丢弃人工细分类或left/right方向；保留原文件hash、记录位置、原词和映射路径。
guide_revision仍为g1a-guide-v3，annotation_version仍为g1a-annotation-v2；不能伪装成旧手册或旧批次。
映射后的结构兼容不代表当前v7完整audit已接纳新批次，正式接入与版本冻结由工程环节完成。

## 10. 分歧、支持审查与验收

先冻结双方全部原始初标，再计算原始一致性、文档配对和split/merge分歧。
共同裁定另存；来源主张通过原始annotation_id及完整ClaimReview canonical hash显式对应，不按编号或列表位置硬配。
support review必须由真人阅读原文，写清最终主张、scope、支持判断、理由、对应来源和真实复核时间。
不确定或无法解决的情况保留，不用AI替补判断，不删除争议样本提高κ，不按算法得分调gold。
既有门槛下低一致性需要修手册并在新版本重标；讨论后的共识不能替代初标一致性。
五轨迹完整初标、溯源、仲裁和支持审查齐全后再冻结gold和总验收。当前规则定稿不等于人工门槛通过。
