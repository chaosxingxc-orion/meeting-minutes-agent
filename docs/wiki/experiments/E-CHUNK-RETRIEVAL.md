# E-CHUNK-RETRIEVAL

- 负责人：EuphoriaYan
- 状态：`已注册，待运行`
- 类型：Omni模型、完整会议、per-chunk稀疏检索稳定性

本实验是广播式上下文失败后的独立设计。上一完整pass中同一chunk的转写只作为检索query，模型
看不到原始query、recent-tail或整会摘要；每次最多看到4个标为不可信的短候选。四臂为
`R0-bare`、`R1-global`、`R2-speaker`、`R3-deranged`，随后以完整R2输出重建索引并运行
`R2-round2`。

v3零模型审计已确认1056个eligible turn，且R2/R3候选100%可分、数量相等、均在256字符内。
正式判读还必须同时通过一致性、错路由分离、第二轮收敛、WER、最差speaker、错误激活和语言
漂移门。通过只说明该固定稀疏loop在当前数据面稳定，不自动放行跨域结论或training-free GRPO。

- [预注册](../../readiness/2026-08-24-chunk-retrieval-preregistration.md)
- [冻结runtime](../../../configs/probes/chunk_retrieval/2026-08-24-runtime.json)
- [供给审计](E-CHUNK-RETRIEVAL-SUPPLY.md)
