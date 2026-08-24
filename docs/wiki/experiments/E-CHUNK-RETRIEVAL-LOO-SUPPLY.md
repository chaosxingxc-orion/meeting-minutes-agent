# E-CHUNK-RETRIEVAL-LOO-SUPPLY

- 负责人：EuphoriaYan
- 状态：`已注册，待判读`
- 类型：零模型、leave-one-chunk-out独立证据供给审计

该实验不修改已经失败的同chunk检索结论。当前chunk上一轮转写只作query；候选必须来自同一
预测speaker的至少两个其他chunk，不得与query中的词完全相同。参考文本只在一次性reader中
衡量候选是否真的出现在目标音频区间，不参与候选构造。

放行要求包括：至少400个novel-candidate turn、100个reference-supported turn、覆盖至少3场、
候选精度至少90%，且当前query与当前turn证据泄漏均为0。失败则停止当前output-only模糊检索
分支，不事后调阈值。

- [预注册](../../readiness/2026-08-24-independent-chunk-retrieval-supply-preregistration.md)
