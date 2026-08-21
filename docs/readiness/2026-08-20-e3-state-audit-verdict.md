# E3 合法说话人状态审计判读：LEGAL-STATE-READY

日期：2026-08-20  
预注册：`docs/readiness/2026-08-20-e3-state-audit-preregistration.md`  
机器结果：`docs/checks/2026-08-20-e3-state-audit-read/verdict.json`

## 正式结论

> **LEGAL-STATE-READY**

在 12 个 ContextASR English dialogues、151 个无提示 Pass-0 turn 上，仅从更早的模型转写构造 `first-mention-speaker` 状态，满足全部预注册质量门。151/151 请求成功、零重试；一次性 read 覆盖 62 个带 carry 机会的目标 turn。

| 状态臂 | support precision | hallucination | off-speaker | target relevance | same-speaker recall |
|---|---:|---:|---:|---:|---:|
| 默认 `gated-speaker` | 91.30% | 8.70% | 0.00% | 43.48% | 15.00% |
| **`first-mention-speaker`** | **90.04%** | **9.96%** | **0.00%** | 21.58% | **57.50%** |
| `gated-global` | 93.90% | 6.10% | 49.77% | 16.90% | 35.00% |
| `naive-speaker` | 90.04% | 9.96% | 0.00% | 20.72% | 57.50% |
| `no-carry-speaker` | 100.00% | 0.00% | 0.00% | 40.00% | 2.50% |
| `wrong-speaker` | 93.79% | 6.21% | 73.10% | 12.41% | 12.50% |

主候选相对全局状态将 off-speaker rate 从 49.77% 降到 0，改善 49.77 个百分点；same-speaker recall 反而高 22.50 点。默认 `min_evidence=2` 只达到 15% recall，说明它无法让一次首次出现服务紧接着的第二次出现；`min_evidence=1 + dedupe + inventory_cap=8` 是这次可执行的脚本修正。

## 允许与不允许的结论

允许：合法、无 gold 的 Pass-0 hypothesis 可以构造质量达门的按 speaker 文本状态；speaker routing 实质性减少跨 speaker 供给；可以注册固定完整第二遍实验。

不允许：本实验没有把状态送回 Omni，因此尚未证明 speaker-conditioned 第二遍降低 NE-WER/BWER；ContextASR 使用数据集 turn 边界和匿名 role 作为固定前端代理，不证明真实 diarizer 泛化；这是 discovery smoke，不是最终论文总体效应。

## 下一步

冻结 `first-mention-speaker`，注册固定第二遍对照：bare、label-only、global、speaker、deranged-speaker、corrupt。所有合格 target turns 都运行，不做选择性重听；主要比较 speaker vs bare/global/deranged，并同时守护整体 WER、非实体 WER、最差 speaker、诱导替换和调用成本。
