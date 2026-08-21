# P-ATTR：说话人归属能力

- 状态：`已判读`
- 结论：模型负责转写，speaker 由控制器按固定 diarization 元数据附加。

声明式 speaker grid 出现回复语法劫持，24 个切片中 22 个丢失可归属标签。自由归属的 cpWER 为 0.4352；turn-aware attribution-by-construction 的 cpWER 为 0.3657，speaker-confusion 为 0.0165。因此仓库采用后者，并淘汰要求模型从 speaker grid 自行归属的路径。

这项结果只证明“归属通道”的工程选择，不证明 speaker 文本条件能够提高 ASR。

- [正式判读](../../readiness/2026-08-18-pattr-verdict.md)
- [飞行证据](../../checks/2026-08-18-pattr-smoke-flight/README.md)
