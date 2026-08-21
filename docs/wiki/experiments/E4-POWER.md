# E4-POWER：独立确认实验功效规划

- 状态：`已判读`
- 类型：零模型 census 与预算审计
- 目的：确定检测 5 pp speaker-routing 改善所需的未见对话规模

固定假设为双侧 alpha 0.05、power 0.80、paired discordance 0.15、dialogue design effect 1.5、15% 状态不可用预留。已见的 12 个 E3/E4 dialogues 全部排除，候选按固定 hash seed 排序。

机械结论为 **`CONFIRMATORY-FEASIBLE-BUT-LARGE`**。5 pp 主情景需要 707 个可用 carry mentions；加 15% 预留后的固定 roster 为 287 个未见 dialogues、833 mentions、6,922 calls 和 22.01 小时重复计费音频。

7.5 pp 和 10 pp 情景分别需要 3,072 和 1,761 calls，但不能用预算理由替换已固定的 5 pp 研究问题。候选 roster 已生成；owner 随后授权并完成了大规模 E4-CF，正式结果见 [E4-CONFIRMATORY](E4-CONFIRMATORY.md)。

- [预注册](../../readiness/2026-08-20-e4-power-preregistration.md)
- [正式判读](../../readiness/2026-08-20-e4-power-verdict.md)
- [机器结果](../../checks/2026-08-20-e4-power/verdict.json)
- [完整报告](../../checks/2026-08-20-e4-power/report.txt)
- [候选 roster](../../../configs/probes/contextasr/2026-08-20-e4-confirmatory-candidate-roster.json)
