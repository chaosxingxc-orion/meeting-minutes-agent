# E4 固定第二遍判读：上下文敏感，但 speaker-specific 未达门

日期：2026-08-20  
预注册：`docs/readiness/2026-08-20-e4-conditioning-preregistration.md`  
机器结果：`docs/checks/2026-08-20-e4-conditioning-read/verdict.json`

## 正式结论

> **CONTEXT-SENSITIVE-NOT-SPEAKER-SPECIFIC**

216/216 请求成功、零重试、零截断。正确 speaker 状态方向上改善了整体和 carry 指标，但没有跨过预注册的离散 speaker-specific 能力门，不得把它翻转为“可达”。

| 臂 | WER | carry NE-WER | carry FNR | exact hits | false hint activation |
|---|---:|---:|---:|---:|---:|
| bare | 4.19% | 9.38% | 15.00% | 34/40 | 0 |
| label-only | 4.99% | 9.38% | 15.00% | 34/40 | 0 |
| global | 4.49% | 9.38% | 15.00% | 34/40 | 3 |
| **correct-speaker** | **3.89%** | **7.81%** | **12.50%** | **35/40** | 4 |
| wrong-speaker | 5.08% | 10.94% | 17.50% | 33/40 | 4 |
| corrupt | 4.29% | 15.62% | 25.00% | 30/40 | 4 |

correct-speaker 相对同期 bare 修复 2 个 carry entity、破坏 1 个，净增加 1 个命中；预注册要求至少修复 3 个。它比 wrong-speaker 多 2 个命中；预注册要求至少多 3 个。整体 WER 改善 0.30 个百分点，carry NE-WER 改善 1.56 点，没有触发伤害门，但方向改善不能替代未通过的能力门。

腐败状态将 carry NE-WER 从 9.38% 恶化到 15.62%，carry exact hits 从 34 降到 30，再次证明错误状态会污染转写。label-only 还使整体 WER 恶化 0.80 点，说明标签文本本身也不是无成本输入。

## 允许与不允许的结论

允许：合法状态会改变输出；正确路由方向优于 wrong/corrupt；继续做更有功效的独立 confirmatory surface 有依据。

不允许：当前样本不能证明 speaker-conditioned transcription 可达，不能进入 agent optimization loop，不能以选择性重听放大 2 个修复结果。该 surface 只有 6 个 Pass-0 错误机会，离散统计功效有限。

## 下一步

停止 E5/E6。先在未见 ContextASR dialogues 上做零模型样本量/错误质量规划；只有能够冻结足够多的自然 carry 错误机会，才注册较大的 confirmatory E4。新实验不得复用这 36 个 target 调 prompt 或下调 `3/3` 门槛。
