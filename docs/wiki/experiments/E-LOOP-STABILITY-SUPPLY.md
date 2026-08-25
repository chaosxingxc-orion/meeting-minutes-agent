# E-LOOP-STABILITY-SUPPLY

- 负责人：EuphoriaYan
- 状态：`已判读`
- 类型：零模型、既有 Pass0、滑动记忆供给审计
- 预注册：[供给审计预注册](../../readiness/2026-08-24-agent-loop-stability-supply-preregistration.md)
- 判读：[供给审计结果](../../checks/2026-08-24-agent-loop-stability-supply-read/README.md)

## 目的

验证4场完整会议是否有足量跨时间窗复现，使“摘要 + 全局关键词 + speaker关键词 + 最近上下文”
能够作为下一项 Omni 多臂实验的真实输入，而不是构造一个没有 carry 机会的空实验。

本实验只读取时间上已经发生的 Pass0 输出，不读取 reference/gold，不调用模型。通过只表示
测量供给充足，不表示记忆内容正确、WER 改善或 agent loop 已可部署。

## 冻结门

- 5分钟窗口；至少3场各有至少3窗；
- 至少100个 turn 可获得非空历史关键词记忆；
- 至少20个 turn 存在同会议、同预测 speaker、跨窗口关键词复现。

## 结果与结论

机器判为 **`LOOP-STABILITY-SUPPLY-READY`**：4/4场满足窗口门，1424/1429个turn可获得
非空历史关键词记忆，727个turn有全局跨窗复现，554个turn有同预测speaker跨窗复现。

这只放行下一项 `E-LOOP-STABILITY` 模型能力实验。它不证明记忆正确、转写改善或专业词可纠错，
也不放行 training-free GRPO。下一实验必须把稳定性与效用分开评分，并加入等来源错配记忆负对照。
