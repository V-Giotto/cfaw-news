# PR4 风格样例

所有材料均为合成；候选层级不表示最终个性化排序。

## pr4-T30 (synthetic / ai_development)

tier_candidate: focus

headline: 来源 pr2-source:a 的声明

what_happened: 来源 pr2-source:a 称：「Atlas Tool v1.0 claims a speed gain of 40%. Task: summarization; Dataset: ToySet; Baseline: Base v1.0; Protocol: P1; Hardware: CPU; Conditions: batch=1;」

why_it_matters: 推断：若在相同条件下复现，可作为该任务进一步评估的线索。

风险：来源声明，未独立核验；不能据此认定效果已被独立证明。

风险：仅限所列声明范围，不能外推到其他任务或真实部署。

风险：来源覆盖存在缺口；没有新材料不表示没有变化。

引用 g2:ref:66ac112ab17a339f96cf7faeaab4ce9f504a26d3eddd2b367f1fb40ff83dd8b4: a:1/p1 [0,152]

event_key: g2:event:b7206251d1b6d1cf4ae1f919b6b0209e2ba1d26d1b9b995c05ae268c8f3dbb54

content_revision: e520e76452eed2aff8a623f2fc01a15843ae3eeaab36c17e2f7a8a0afde56808

## pr4-T31 (synthetic / ai_development)

tier_candidate: radar

headline: 来源 pr2-source:a 的声明

what_happened: 来源 pr2-source:a 称：「Atlas Tool v1.0 claims it provides plugins.」

风险：来源声明，未独立核验；不能据此认定效果已被独立证明；适用范围存在未知维度，效果尚未核验；来源覆盖存在缺口；没有新材料不表示没有变化。

引用 g2:ref:927c7706cd1ff25a9b2cdfbe72c807665acc8673c702d219af5534042ee18325: a:1/p1 [0,43]

event_key: g2:event:6f2f9453172169428d42532b4f5b4bcd98525272310c4d065daa5aa57662464f

content_revision: 1711b5c9f4522385921ebd4d72255ea5fe53dbf5a110f2e2a0ecaa75bbcbea09

## pr4-T34 (synthetic / ai_development)

tier_candidate: focus

headline: 来源 pr2-source:a 的声明

what_happened: 来源生命周期记录（旧声明／当前声明）：来源 pr2-source:a 称：「Atlas Tool v1.0 claims a speed gain of 40%. Task: summarization; Dataset: ToySet; Baseline: Base v1.0; Protocol: P1; Hardware: CPU; Conditions: batch=1;」；来源 pr2-source:a 称：「Atlas Tool v1.0 correction: the previous speed gain of 40% is corrected to 4%. Task: summarization; Dataset: ToySet; Baseline: Base v1.0; Protocol: P1; Hardware: CPU; Conditions: batch=1;」

风险：来源声明，未独立核验；不能据此认定效果已被独立证明。

风险：旧声明仅作为已更正或撤回的历史记录保留。

风险：仅限所列声明范围，不能外推到其他任务或真实部署。

风险：来源覆盖存在缺口；没有新材料不表示没有变化。

引用 g2:ref:66ac112ab17a339f96cf7faeaab4ce9f504a26d3eddd2b367f1fb40ff83dd8b4: a:1/p1 [0,152]

引用 g2:ref:f41a2d5c87763a2ed618c165d6120f3a6a436e44283adad998d0004e0934c7a4: a:2/p1 [0,187]

event_key: g2:event:8cc7dee2cbd9a56eb3db316ea6ef403fb16c30c74b19185026350e23ac77e5ad

content_revision: 37bd7e29715530bb045eeaa1f57cf6490d161c757d0e6fbdfcd499b4580e217e

## pr4-CONFLICT (synthetic / ai_development)

tier_candidate: focus

headline: 来源 pr2-source:b 的声明

what_happened: 同一声明范围的相反报告：来源 pr2-source:b 称：「Atlas Tool v1.0 reports no speed gain. Task: summarization; Dataset: ToySet; Baseline: Base v1.0; Protocol: P1; Hardware: CPU; Conditions: batch=1;」；来源 pr2-source:a 称：「Atlas Tool v1.0 claims a speed gain of 40%. Task: summarization; Dataset: ToySet; Baseline: Base v1.0; Protocol: P1; Hardware: CPU; Conditions: batch=1;」

风险：来源声明，未独立核验；不能据此认定效果已被独立证明。

风险：存在相反报告，冲突尚未解决，双方均未被独立核验。

风险：仅限所列声明范围，不能外推到其他任务或真实部署。

风险：来源覆盖存在缺口；没有新材料不表示没有变化。

引用 g2:ref:66ac112ab17a339f96cf7faeaab4ce9f504a26d3eddd2b367f1fb40ff83dd8b4: a:1/p1 [0,152]

引用 g2:ref:9127f8c1b2fed6242d817c37033a7a6eb385d6a86b1acb89e009b18ff195aa0d: b:1/p1 [0,147]

event_key: g2:event:e32ae4f6f1c97234ec4866f8a22aba612965d0da9c8f687c9742b732e10a5809

content_revision: 73570008392f8366adc4596ce5e90eed0e01d75f380b0a4a79fb84496f32c54e

## pr4-T32_BODY (synthetic / ai_development)

tier_candidate: hold

暂缓生成：缺少可安全引用的正文声明。

event_key: g2:event:53aae8092dd3558c73e2391336b725b092d9f2cf37b04b6896134ef0677ec145

content_revision: 763e26527ead0ff4cb49854c3969120a86cc71568f606f4577feecf56593d4f8


## 读取说明

Radar 的全部风险字段以分号连接成第二句；详情中的 ClaimSummary 保留范围和状态。这里展示的来源 ID 是合成输入的技术标识，未虚构发布者名称。所有成文均为来源归属的原文引用，推断另列。管理员仅需选择表达风格，数据与引用校验由 AI 完成，无逐条人工标注门槛。
