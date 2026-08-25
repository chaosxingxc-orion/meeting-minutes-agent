# E-MATERIAL-SEMANTIC-ADMISSION

- 负责人：EuphoriaYan
- 状态：`已判读`
- 类型：零模型、独立性准入审计
- 预注册：[准入预注册](../../readiness/2026-08-25-material-semantic-admission-preregistration.md)
- 冻结配置：[准入配置](../../../configs/probes/material_semantic_admission/2026-08-25-admission.json)

## 研究问题

Earnings-22 是否还剩至少六场从未向既有实验暴露参考词面的会议，从而能建立 3 场开发、3 场
一次性确认的独立语义材料门控队列？说话人数、时序和音频哈希不算词汇污染；读取参考文本做术语
供给审计则算污染。

## 判读结果

结论为 `ADMISSION_FAILED_NO_REFERENCE_UNREAD_MEETINGS`。E4 v2 已正式读取 80 场
discovery 的参考词面，E4 v3 又正式读取其余 45 场 reserve；两者无重叠，并集覆盖冻结 roster
的 125/125 场，因此 reference-unread 数量为 0，低于六场硬门。

本次没有重读参考文本、下载材料、解码音频或调用模型。实验没有把“reference-unread”偷换成
“本次结果未读”，也没有沿用被污染的候选会议。后续若坚持严格独立性，需要新会议数据或独立
外部测试集；若接受 construction-isolated 而非 history-unread，必须另立实验并明确降低证据等级。

- [机器判读](../../checks/2026-08-25-material-semantic-admission-read/README.md)
