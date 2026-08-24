# E-LOOP-STABILITY

- 负责人：EuphoriaYan
- 状态：`已判读`
- 前置门：[E-LOOP-STABILITY-SUPPLY](E-LOOP-STABILITY-SUPPLY.md) 已通过
- 预注册：[模型稳定性预注册](../../readiness/2026-08-24-agent-loop-stability-preregistration.md)
- 研究问题：新增信息进入后，有界滑动上下文能否稳定、可复现且不伤害整会转写？

## 五臂设计

所有臂复用相同音频、turn、speaker、顺序、模型和decode，不选择性重听：

| 臂 | 上下文 | 回答的问题 |
|---|---|---|
| `L0-bare` | 无状态；复用完整Pass0 | 基线 |
| `L1-recent` | 当前pass最近文本尾部 | 短时上下文本身的作用 |
| `L2-global` | L1 + 有界摘要 + 全局关键词 | 整会一致化作用 |
| `L3-speaker` | L2 + 当前speaker关键词 | speaker路由增量 |
| `L4-deranged` | L2 + 等来源错配speaker记忆 | 排除通用提示偏置与错误注入 |

`L3` 还需再执行一轮，区分一次变化与跨pass收敛。状态包含来源标记：内部转写只能进入
摘要/关键词；会议语言、议程、IR材料等独立信息进入anchor区，gold永不进入模型。

## 预定判决

稳定层要求状态hash 100%复现、上下文100%不超预算、跨会议泄漏为0；`L3`相对
`L0/L1/L4`提高同speaker跨窗形式一致性，相邻pass变化下降，并且整体WER、非术语WER、
最差speaker、错误激活和语言漂移全部非劣。通过仅允许进入第二阶段策略搜索，不等于WER已改善。

正式manifest已冻结：hash `bd9d31b2875824619f76161b252e3760c9c15be7f9e4289969517dc0b4abbc7d`。
Phase1为7145次调用，L3第二轮1429次，总计8574次、25.13音频小时。模型接触后只允许执行
预建read suite一次，不得按结果修改阈值。

## 结果

8,574/8,574调用成功，判为 **`LOOP-STABILITY-NOT-REACHED`**。L3把跨窗形式一致率从
bare的75.00%提高到86.42%，4/4场方向为正；但只在2/4场优于错配speaker，第二轮变化没有
收敛（比率1.040，门槛≤0.80），WER从22.02%恶化到41.30%，unsupported activation为3.13%。

事后诊断发现recent-tail臂输出/参考长度比升至1.57，高复述率16.17%，支持“模型把上下文当成
待输出文本”的污染机制。正式结论不允许启动GRPO/GEPA/知识注入。下一设计应删除原文recent-tail
和广播式长摘要，改为每个chunk只检索少量相关候选，并保留错配负对照。

- [Flight回执](../../checks/2026-08-24-e-loop-stability-flight/README.md)
- [正式判读](../../checks/2026-08-24-e-loop-stability-read/README.md)
