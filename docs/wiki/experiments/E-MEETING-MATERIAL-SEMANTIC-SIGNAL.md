# E-MEETING-MATERIAL-SEMANTIC-SIGNAL

- 负责人：EuphoriaYan
- 状态：`已判读`
- 类型：零模型、encode-only语义K对照
- 预注册：[语义检索预注册](../../readiness/2026-08-25-meeting-material-semantic-signal-preregistration.md)
- 冻结配置：[semantic signal配置](../../../configs/probes/meeting_material_semantic_retrieval/2026-08-25-signal.json)

## 研究问题

词法Q-K-V只有61.87%正确会议归属。伞仓SAEA强结果使用更丰富的K和排序，因此本实验仅替换
ranking representation：保持同一751个Q、每场8个K、未嵌入V和错配轮换，用伞仓已锁定的
Qwen3-Embedding-0.6B做encode-only语义检索。

只有top1/top2余弦差至少0.02才dispatch。工具不能生成答案，不读reference、音频或Omni。
语义臂不仅要达到70%归属precision和逐会分布门，还必须比已冻结词法臂提高至少8个百分点。

## 判读结果

全部预注册门通过，结论为`SEMANTIC-RETRIEVAL-SIGNAL-PRESENT`。751个eligible turn中393个
通过0.02 gap门，覆盖52.33%；正确材料归属306/393，precision 77.86%。相对词法K提高
15.997个百分点。Jeronimo Martins、Galp、TeamViewer分别为69.05%、84.33%、70.65%，
三场都超过60%逐会门；median correct-minus-deranged cosine为0.0559。

这证明可迁移的是encode-only语义K排序与选择性dispatch，而不是Q-K-V名义或广播更多上下文。
但本实验没有证明术语正确性或WER收益，且错配池只可作为实验控制。下一步仅放行独立未读会议上的
retain-direct / correct-dispatch / deranged-dispatch三臂能力实验设计，不放行GRPO、GEPA或部署。

- [运行时回执](../../checks/2026-08-25-qwen3-embedding-runtime/README.md)
- [一次性判读](../../checks/2026-08-25-meeting-material-semantic-signal-read/README.md)
- [阶段判决](../../readiness/2026-08-25-meeting-material-semantic-signal-verdict.md)
- [下一实验设计](../../readiness/2026-08-25-meeting-material-retain-dispatch-next-design.md)
