# E-CHUNK-RETRIEVAL-LOO-SUPPLY

- 负责人：EuphoriaYan
- 状态：`已判读`
- 类型：零模型、leave-one-chunk-out独立证据供给审计

该实验不修改已经失败的同chunk检索结论。当前chunk上一轮转写只作query；候选必须来自同一
预测speaker的至少两个其他chunk，不得与query中的词完全相同。参考文本只在一次性reader中
衡量候选是否真的出现在目标音频区间，不参与候选构造。

判读发现novel候选覆盖980/1429 turns、628个不同候选，且两类泄漏均为0；但只有57/2961个
候选出现在目标参考区间，精度仅1.93%，仅53个turn有正确候选，0场达到每场20个正确turn门。
正式结论为 `INDEPENDENT-CHUNK-SUPPLY-INSUFFICIENT`。

事后描述诊断显示主要是 `thank/thanks`、`question/questions` 等与当前音频无关的词形替换，也有
`million/billion`、`next/net` 等危险混淆。当前output-only字符串模糊检索分支停止，不调阈值、
不启动模型flight。后续必须先指定带来源证明的外部独立证据。

- [预注册](../../readiness/2026-08-24-independent-chunk-retrieval-supply-preregistration.md)
- [判读前实现修订](../../readiness/2026-08-24-independent-chunk-retrieval-supply-implementation-amendment.md)
- [正式判读](../../checks/2026-08-24-independent-chunk-retrieval-supply-read/README.md)
- [阶段结论](../../readiness/2026-08-24-independent-chunk-retrieval-supply-verdict.md)
