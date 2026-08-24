# E-CHUNK-RETRIEVAL-SUPPLY

- 负责人：EuphoriaYan
- 状态：`v3已判读，可注册模型实验`
- 类型：零模型、per-chunk稀疏候选供给与负对照审计

v1完全删除recent-tail和长摘要，只用上一轮同一chunk转写检索最多4个词形。4场共1056个turn
可得到speaker候选，长度预算全部通过；但正确speaker与错配speaker候选只在88.26%的eligible
turn上不同，低于90%门，判为 `SPARSE-CHUNK-RETRIEVAL-SUPPLY-INSUFFICIENT`。

v2排除了正确候选，使可分率达到100%，但固定错配speaker只有970/1056个turn能提供等量候选，
仍未放行。v3不改阈值：按固定轮转顺序选择首个能提供等量非重叠候选的其他speaker，且每个turn
只使用一个错配speaker。最终1056/1056个eligible turn同时满足100%可分、等候选数和256字符预算，
判为 `SPARSE-CHUNK-RETRIEVAL-SUPPLY-READY`。

该结论只放行正式的 `R0-bare / R1-global / R2-speaker / R3-deranged` 实验注册；不证明检索有益，
也不放行training-free GRPO或知识注入。

- [v1判读](../../checks/2026-08-24-sparse-chunk-retrieval-supply-read/README.md)
- [v2判读](../../checks/2026-08-24-sparse-chunk-retrieval-supply-v2-read/README.md)
- [v3判读](../../checks/2026-08-24-sparse-chunk-retrieval-supply-v3-read/README.md)
