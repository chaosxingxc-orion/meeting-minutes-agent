# E-LOOP-STABILITY

- 负责人：EuphoriaYan
- 状态：`设计中`
- 前置门：[E-LOOP-STABILITY-SUPPLY](E-LOOP-STABILITY-SUPPLY.md) 已通过
- 研究问题：新增信息进入后，有界滑动上下文能否稳定、可复现且不伤害整会转写？

## 五臂设计

所有臂复用相同音频、turn、speaker、顺序、模型和decode，不选择性重听：

| 臂 | 上下文 | 回答的问题 |
|---|---|---|
| `L0-bare` | 无状态；复用完整Pass0 | 基线 |
| `L1-recent` | 当前pass最近文本尾部 | 短时上下文本身的作用 |
| `L2-global` | 有界摘要 + 全局关键词 | 整会一致化作用 |
| `L3-speaker` | L2 + 当前speaker关键词 | speaker路由增量 |
| `L4-deranged` | 等来源、等长的错配speaker记忆 | 排除通用提示偏置与错误注入 |

`L3` 还需再执行一轮，区分一次变化与跨pass收敛。状态包含来源标记：内部转写只能进入
摘要/关键词；会议语言、议程、IR材料等独立信息进入anchor区，gold永不进入模型。

## 预定判决

稳定层要求状态hash 100%复现、上下文100%不超预算、跨会议泄漏为0；`L3`相对
`L0/L1/L4`提高同speaker跨窗形式一致性，相邻pass变化下降，并且整体WER、非术语WER、
最差speaker、错误激活和语言漂移全部非劣。通过仅允许进入第二阶段策略搜索，不等于WER已改善。

正式运行前仍需冻结renderer、summary/keyword规则、错配规则、score hash、效应阈值和总调用预算。
