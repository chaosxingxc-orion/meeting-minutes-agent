# E4-CF 未见对话独立确认实验判读

日期：2026-08-20  
预注册：`docs/readiness/2026-08-20-e4-confirmatory-preregistration.md`  
机器结果：`docs/checks/2026-08-20-e4-cf-read/verdict.json`

## 正式结论

> **DIRECTIONAL-NOT-CONFIRMED**

Pass 0 完成 3,822/3,822 次调用；attrition gate 保留 774/775 个 target、832/833 个 carry mention，高于预注册的 707 门槛。四臂第二遍完成 3,096/3,096 次调用。两阶段均零失败、零重试、零跳过。

| 臂 | WER | carry NE-WER | carry exact hit | false hint | 截断 |
|---|---:|---:|---:|---:|---:|
| CF0-bare | 5.40% | 13.90% | 665/832（79.93%） | 0 | 1 |
| CF1-global | 3.73% | 11.78% | 692/832（83.17%） | 93 | 0 |
| **CF2-speaker** | **3.54%** | **10.24%** | **710/832（85.34%）** | 109 | 0 |
| CF3-wrong | 3.57% | 11.85% | 692/832（83.17%） | 70 | 0 |

## 预注册门控

1. `CF2-speaker - CF3-wrong` carry hit rate 为 **+2.16 pp**，dialogue-cluster bootstrap 95% CI **[+0.11, +4.30] pp**。方向和显著性为正，但点估计未达到预注册的 **+5 pp** 实用效应门，因此主门失败。
2. `CF2-speaker - CF0-bare` carry NE-WER 为 **-3.66 pp**，95% CI **[-5.27, -2.13] pp**，通过。
3. `CF2-speaker - CF0-bare` 总体 WER 为 **-1.86 pp**，95% CI **[-5.44, 0.00] pp**，通过非劣门，也未触发伤害门。

## 允许与不允许的结论

允许：合法文本状态显著改善 carry 专业词；正确 speaker 路由相对 wrong-speaker 有小而稳定的额外收益；固定第二遍没有总体 WER 伤害。

不允许：不能声称已确认“至少 5 pp 的 speaker-specific 改善”，也不能据此放行 training-free agent loop 或选择性重听。下一步应先做冻结结果的机制/分层分析，解释 109 次 false-hint activation，并为更小且有明确安全约束的策略改动另行预注册。
