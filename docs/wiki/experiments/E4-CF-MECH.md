# E4-CF-MECH：冻结结果机制审计

- 状态：`已判读`
- 正式机器决策：`PREREGISTER-ONE-FIXED-POLICY`
- 唯一入选 predicate：`speaker_wrong_disjoint`
- 类型：零模型、post-hoc exploratory
- 输入：E4-CF 冻结 runtime/score binding、Pass-0 与第二遍 responses
- 正式结论保护：不得修改或替换 `DIRECTIONAL-NOT-CONFIRMED`

本任务解释 speaker 相对 wrong 的 +2.16 pp 小效应、speaker 相对 global 的净差异，以及 109 次 false-hint activation。审计必须先冻结字段和变化分类，再读取分层结果；只允许使用运行时可见特征提出后续策略，禁止 gold/error selector。

输出必须在 `NO-ACTIONABLE-MECHANISM`、`PREREGISTER-ONE-FIXED-POLICY`、`SAFETY-RISK-DOMINATES` 中三选一。默认零模型调用；若建议新实验，只起草预注册，需另行授权才能接触模型。

正式读取覆盖 774 targets / 287 dialogues。speaker 相对 bare 修复 66、破坏 21，净 +45；global 和 wrong 均净 +27，因此 speaker 的额外净收益是 18 个 carry hits。109 次 speaker false hint 中有 90 次来自 evidence count=1 的词，108 次距最近历史 mention 至少 3 turns；41 次位于“无净 carry 收益且 WER 比 bare 更差”的 target。

四个冻结 predicate 中仅 `speaker_wrong_disjoint` 通过：覆盖 418 targets / 228 dialogues，speaker 相对 global +3.79 pp、相对 wrong +4.24 pp，WER 相对 global -0.49 pp，false-hint target rate 相对 global +0.96 pp。它只是后验生成的单一假设；下一策略固定为“不重叠时用 speaker，否则回退 global”，必须在新的未见 surface 上重新确认。

- [明日工作计划](../2026-08-21-work-plan.md)
- [冻结审计设计](../../plans/2026-08-21-e4-cf-mechanism-audit.md)
- [正式注册](../../readiness/2026-08-21-e4-cf-mechanism-registration.md)
- [正式判读](../../readiness/2026-08-21-e4-cf-mechanism-verdict.md)
- [机器结果](../../checks/2026-08-21-e4-cf-mechanism-read/verdict.json)
- [下一实验预注册草案](../../readiness/2026-08-21-e4-disjoint-policy-preregistration-draft.md)
- [E4-CF 正式判读](../../readiness/2026-08-20-e4-confirmatory-verdict.md)
- [E4-CF 机器结果](../../checks/2026-08-20-e4-cf-read/verdict.json)
