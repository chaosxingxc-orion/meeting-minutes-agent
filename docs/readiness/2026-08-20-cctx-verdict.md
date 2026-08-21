# C-CTX 判读：上下文敏感，但未越过预注册可达门槛

日期：2026-08-20  
注册：`docs/readiness/2026-08-20-cctx-preregistration.md`  
冻结结果：`docs/checks/2026-08-20-cctx-read/verdict.json`

## 正式结论

> **CONTEXT-SENSITIVE-BUT-UNCONTROLLED**

Qwen3-Omni 明显利用了提示中的实体拼写，但 `C2-entity` 相对无上下文基线的 NE-WER 改善为 **4.93 个百分点**，比预注册的 5.00 点可达门槛少 **0.07 点**。不得事后下调阈值，因此本次 smoke 不能登记为 `ORACLE-CONTEXT-REACHABLE`。

## 结果

| 臂 | WER | NE-WER | NE-FNR | 提示实体激活 |
|---|---:|---:|---:|---:|
| `C0-bare` | 2.20% | 6.25% | 8.97% | — |
| `C1-domain` | 2.11% | 7.24% | 9.42% | — |
| `C2-entity` | **1.28%** | **1.32%** | **0.45%** | 225/227 |
| `C3-deranged` | 2.26% | 8.55% | 11.66% | 0/229 |
| `C4-corrupt` | 4.40% | 16.61% | 20.18% | 25/227 |

预注册对照：

| 对照 | 差值 | 配对 bootstrap 95% CI | 判读 |
|---|---:|---:|---|
| `NE-WER(C2)-NE-WER(C0)` | -4.93 pp | [-8.37, -1.78] pp | 方向稳定，但未达到 -5.00 pp 门槛 |
| `NE-WER(C2)-NE-WER(C3)` | -7.24 pp | [-12.11, -2.92] pp | 正确供给显著优于错配供给 |
| `WER(C2)-WER(C0)` | -0.92 pp | [-1.54, -0.38] pp | 没有整体转写伤害，反而改善 |

## 解释边界

1. 正确实体列表带来稳定改善，证明提示通道不是 inert；继续研究 prompt/state 有依据。
2. 错拼列表造成显著伤害，说明模型会服从错误状态；任何 agent loop 都必须控制污染和错误路由。
3. `C2` 是 gold-derived oracle supply，只证明“会使用”，不证明运行时能够发现正确词，也不证明 speaker routing 有效。
4. 32 条 smoke 的阈值近失不能通过事后改规则翻转。下一实验应扩大预注册样本，或直接进入合法状态质量实验；不得重读本批样本来调 prompt。

## 工程记录

- 32 个样本、5 臂、160/160 成功；无 retry。
- 音频预算：7,176.21/7,200 秒。
- 主模型：Q4_K_M `d9e28765…4dd85`；mmproj Q8_0 `1104376d…c8d`。
- receipt config hash：`f611f1857911f198a5b2b7d9505e4176f66c05203cdb0f67d589da6970ad8e8e`。
- 全仓离线测试：1,186 passed，9 skipped。

## 下一步

优先做合法状态构造的离线精度/污染审计，并为未见过的 ContextASR 分片注册较大 confirmatory supply 实验。只有合法状态能够达到精度门槛后，才执行固定 speaker-conditioned 第二遍；当前证据不支持直接进入选择性重听。
