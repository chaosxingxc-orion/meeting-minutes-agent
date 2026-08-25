# E-MEETING-MATERIAL-RETRIEVAL-SIGNAL

- 负责人：EuphoriaYan
- 状态：`已判读`
- 类型：零模型、SAEA式Q-K-V检索信号审计
- 预注册：[检索信号预注册](../../readiness/2026-08-25-meeting-material-retrieval-signal-preregistration.md)
- 冻结配置：[signal配置](../../../configs/probes/meeting_material_retrieval/2026-08-25-signal.json)

## 研究问题

伞仓SAEA较好结果的关键不是广播更多知识，而是Q-K-V组织与retain/dispatch：默认保留直接结果，
只把检索信号充分的样本派发到证据路径。本实验把该结构迁移到会议转写，检查Pass0 chunk是否更
接近本会议官方材料，而不是等宽错配会议材料。

Q是Pass0文本，K是官方材料中的术语及原文跨度，V是未嵌入的规范词形和出处。每场只取8个
确定性key，短缩写不做字符模糊，精确词形已出现的turn不计入。本阶段不读reference、不接触
音频或Omni，也不声称能够纠错。

只有检索覆盖、正确材料归属精度、逐会分布和margin全部过门，才允许另行注册“保留原转写/高
置信派发修订”的模型能力实验。

## 判读结果

在不读取reference、音频或模型的条件下，751个turn满足查询门，729个产生正分，覆盖97.07%。
本会议材料战胜错配材料451次，归属精度61.87%，低于70%门。Galp为77.12%，但Jeronimo
Martins仅40.97%、TeamViewer仅46.94%；只有1/3场达到逐会60%门。结论为
`RETRIEVAL-SIGNAL-INSUFFICIENT`，不放行retain/dispatch Omni flight。

该结果说明单场存在可用信号，但纯词法K的跨场景扩展性不足，正好验证了“非常依赖场景”的风险。
伞仓的收益来自训练侧多维K、排序和保守BLEND，而不只是Q-K-V外形。下一合法分支是保持同一等宽
错配控制，另行注册encode-only语义text retriever；这不是在本结果上调整BM25阈值。

- [一次性结构判读](../../checks/2026-08-25-meeting-material-retrieval-signal-read/README.md)
- [阶段判决](../../readiness/2026-08-25-meeting-material-retrieval-signal-verdict.md)
