# E-STABLE-ERROR-SUPPLY 稳定错误供给实验

日期：2026-08-24
状态：**已判读：`STABLE-ERROR-SUPPLY-PRESENT-ANCHOR-LIMITED`**

## 研究问题

在固定 Earnings-22 音频、Sortformer speaker、RTTM turn 和裸转写提示下，整场会议内是否存在
足量“同一预测 speaker、同一窄类术语、重复出现且被稳定转错”的错误簇？本实验只测供给，
不运行 Pass1，不声称优化收益。

## 冻结 roster 与预算

从已读的45场 v3 reserve 中，按 `ABBREVIATION/ALPHANUMERIC` speaker-exclusive carry 降序、
固定 salt 打破并列，选择前4场；不依据 Omni 错误或失败的 RTTM 主讲门选择。

| 会议 | 已知窄类 carry | Pass0 calls | 音频秒 |
|---|---:|---:|---:|
| 4443920 | 29 | 201 | 3226.172 |
| 4483589 | 24 | 281 | 4561.612 |
| 4461799 | 20 | 497 | 3899.568 |
| 4430051 | 20 | 450 | 3389.801 |
| 合计 | 93 | **1429** | **15077.153** |

每场全部 RTTM turn 都运行；只有超过仓库120秒传输上限的 turn 被机械拆分，speaker 不变。
运行时 manifest 不含 reference、实体或 ticker。模型采用已冻结 Qwen3-Omni Q4_K_M、Q8_0
mmproj、裸 `transcribe-only-v1`、temperature 0、seed 0、max tokens 512。

## 稳定错误定义

评分器按 `(meeting, predicted speaker, normalized reference surface)` 聚类。组内至少3次复现，
且同一输出形式占比至少70%，才称稳定；多数形式等于参考为 `stable-correct`，否则为
`stable-wrong`。模型输出形式由冻结的 token alignment 机械提取。reference 只对 scorer 可见。

唯一合法锚点是 `metadata.csv` 的 ticker exact match；它独立于 transcript，但不保证模型可控。

## 判读与停止条件

- 至少10个 stable-wrong group，且覆盖至少3场；
- 其中至少2个 ticker-anchored group，且覆盖至少2场。

全部通过：`STABLE-ERROR-SUPPLY-READY`；稳定错误通过而锚点失败：
`STABLE-ERROR-SUPPLY-PRESENT-ANCHOR-LIMITED`；否则：
`INSUFFICIENT-STABLE-ERROR-SUPPLY`。

四场全部完成后只读一次。任何缺失、重复、hash 漂移或预算越界均停止，不以已读局部结果改
roster 或阈值。即使通过，也只允许另行预注册一次完整 Pass1 controllability pilot。
