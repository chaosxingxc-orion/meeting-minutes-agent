# E4-SAFETY-GATE-AUDIT：false-hint 拒绝门扩展性审计

- 状态：`已判读`
- 类型：post-hoc exploratory、零模型
- 模型调用：0

本实验不再扩大 E4 flight，而是检验一个可部署的回退策略：运行时 gate 通过时使用已冻结 speaker 输出，否则回退 global，并保留全部 target。正式判决为 **`NO-SAFE-GATE`**。

四个候选中，重复证据门覆盖为0；两个近期门仅覆盖10–11个 target，没有 carry 增益且各增加1个 false-hint target。唯一通过覆盖与安全门的 `inventory_le2` 覆盖27/86 targets、24个 dialogue，false-hint 增量为0，但 carry hit 与 carry NE-WER 增益也都变为0。因此失败发生在总体收益门，尚未到跨 fold/width 扩展性门。

这比“规则只依赖场景”更弱：简单 evidence、recency、width 阈值在当前 ContextASR surface 内就没有形成安全且有收益的策略。跨领域扩展性仍为 `not_identified`；不得继续在同一结果上调阈值。

- [中文冻结设计](../../plans/2026-08-21-e4-safety-gate-audit.md)
- [正式预注册](../../readiness/2026-08-21-e4-safety-gate-audit-preregistration.md)
- [实现 amendment](../../readiness/2026-08-21-e4-safety-gate-audit-implementation-amendment.md)
- [正式判读](../../readiness/2026-08-21-e4-safety-gate-audit-verdict.md)
- [机器结果](../../checks/2026-08-21-e4-safety-gate-audit-read/verdict.json)
- [父实验](E4-DISJOINT-DIR.md)
