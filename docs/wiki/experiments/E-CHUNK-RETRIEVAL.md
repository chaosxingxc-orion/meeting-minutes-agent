# E-CHUNK-RETRIEVAL

- 负责人：EuphoriaYan
- 状态：`已判读`
- 类型：Omni模型、完整会议、per-chunk稀疏检索稳定性

本实验是广播式上下文失败后的独立设计。上一完整pass中同一chunk的转写只作为检索query，模型
看不到原始query、recent-tail或整会摘要；每次最多看到4个标为不可信的短候选。四臂为
`R0-bare`、`R1-global`、`R2-speaker`、`R3-deranged`，随后以完整R2输出重建索引并运行
`R2-round2`。

两阶段7145/7145 calls全部成功，结构门和收敛门通过，收敛比为0.280。但R2一致性68.58%，
低于bare的75.00%（-6.42点），相对bare为0/4场胜出，相对等量错路由仅1/4场胜出。总体WER
非劣（22.00% vs 22.04%），但最差speaker恶化4.17点，unsupported candidate activation高达
54.98%。正式结论为 `CHUNK-RETRIEVAL-NOT-REACHED`。

这说明当前loop会收敛，却主要固化上一轮由同一模型提出的词形，不是可用的纠错稳定层。下一步
只能先做新的零模型leave-one-chunk-out跨出现证据审计；不能在本结果上调阈值，也不放行GRPO、
GEPA、EM更新或多模态注入。

- [预注册](../../readiness/2026-08-24-chunk-retrieval-preregistration.md)
- [冻结runtime](../../../configs/probes/chunk_retrieval/2026-08-24-runtime.json)
- [供给审计](E-CHUNK-RETRIEVAL-SUPPLY.md)
- [flight](../../checks/2026-08-24-e-chunk-retrieval-flight/README.md)
- [正式判读](../../checks/2026-08-24-e-chunk-retrieval-read/README.md)
- [阶段结论](../../readiness/2026-08-24-chunk-retrieval-verdict.md)
