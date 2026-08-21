# E4-POWER 判读：可确认，但规模较大

日期：2026-08-20  
预注册：`docs/readiness/2026-08-20-e4-power-preregistration.md`  
机器结果：`docs/checks/2026-08-20-e4-power/verdict.json`

## 正式结论

> **CONFIRMATORY-FEASIBLE-BUT-LARGE**

排除 E3/E4 已见的 12 个 dialogue 后，剩余 5,261 个未见 dialogue 中有 1,921 个至少包含 2 个同 speaker carry mentions；总供给为 7,256 mentions，因此数据面足够。问题不在数据缺失，而在严谨检测 5 pp 效应所需的运行规模。

固定 alpha 0.05、power 0.80、discordance 0.15、dialogue design effect 1.5 后，需要 **707 个可用 carry mentions**。考虑 15% 状态不可用预留，候选选择目标为 832；固定 hash 前缀实际达到 833，需要：

- 287 个未见 dialogues；
- 775 个 carry target turns；
- 3,822 次 Pass-0 calls；
- 3,100 次四臂第二遍 calls；
- 合计 **6,922 calls、79,232.49 audio-seconds（22.01 小时重复计费音频）**。

| MDE | Dialogues | Carry mentions | Total calls | Audio hours |
|---:|---:|---:|---:|---:|
| **5 pp** | **287** | **833** | **6,922** | **22.01** |
| 7.5 pp | 127 | 372 | 3,072 | 9.75 |
| 10 pp | 73 | 210 | 1,761 | 5.54 |

5 pp 与 C-CTX 的原始可达门一致，不能因为预算较大而事后改成 7.5 或 10 pp。候选 roster 已冻结，但它只是规划产物。

## 决策边界

本审计允许声称独立 confirmatory E4 在数据上可实施，并给出可直接预算的 roster。不允许自动启动 6,922-call flight，不允许把较小 MDE 情景当成已经注册的替代实验，也不允许进入 agent loop。

在获得明确算力/时间授权前，confirmatory E4 状态为 `待预算授权`。若授权，下一步需要另写模型接触预注册，重新核验音频资产、状态可构造规则、四臂 hash、失败/attrition 处理和顺序执行计划；不得直接把本 census 当作 flight registration。
