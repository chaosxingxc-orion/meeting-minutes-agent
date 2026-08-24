# E-CHUNK-RETRIEVAL-SUPPLY

- 负责人：EuphoriaYan
- 状态：`v1已判读，v2设计中`
- 类型：零模型、per-chunk稀疏候选供给与负对照审计

v1完全删除recent-tail和长摘要，只用上一轮同一chunk转写检索最多4个词形。4场共1056个turn
可得到speaker候选，长度预算全部通过；但正确speaker与错配speaker候选只在88.26%的eligible
turn上不同，低于90%门，判为 `SPARSE-CHUNK-RETRIEVAL-SUPPLY-INSUFFICIENT`。

这不是供给不足，而是负对照不正交：多个speaker会共享会议术语。不能事后降低阈值；v2必须从
错配池显式排除正确候选，并新增“候选数相等”和100%可分门。v2通过前不接触模型。

- [v1判读](../../checks/2026-08-24-sparse-chunk-retrieval-supply-read/README.md)
