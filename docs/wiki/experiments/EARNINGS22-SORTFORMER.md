# EARNINGS22-SORTFORMER：电话会议主讲人 diarization

- 负责人：EuphoriaYan
- 状态：`已判读`
- 类型：全库固定工具验证，125场
- Omni 调用：0

实验检验“电话会虽然参会人很多，但1–2位主讲占据大部分发言，因此4-speaker Sortformer
仍可能保住主讲”的假设。125场全部运行，0失败，总墙钟3.06小时。

正式主假设组为30场：参考说话人超过4位、对齐充分、Top-2发言占比至少60%。该组Top-1
归属错误率14.30%，Top-2为22.59%，均通过预注册20%/25%门，判为
`MAIN-SPEAKER-DIARIZATION-USABLE`。因此这个想法**在主讲占主导的子场景成立**。

但边界同样明确：主假设组长尾错误率72.75%，全部76场可评分 >4 人会议的Top-2错误率
升至26.99%；只有14/30场逐场Top-2错误率不超过25%。这不是“所有参会人都能分开”，而是
“主要主讲通常能保住、偶发发言者大量合并”。后续若做 Omni pilot，必须只对冻结的主讲
路由人群提出结论，并单独处理或排除长尾 speaker。

- [中文计划](../../plans/2026-08-24-earnings22-sortformer-smoke.md)
- [预注册](../../readiness/2026-08-24-earnings22-sortformer-preregistration.md)
- [正式 verdict](../../readiness/2026-08-24-earnings22-sortformer-verdict.md)
- [收据与结果](../../checks/2026-08-24-earnings22-sortformer-read/README.md)
- [机器结果](../../checks/2026-08-24-earnings22-sortformer-read/verdict.json)
