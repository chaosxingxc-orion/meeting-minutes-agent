# E4-SAFETY-GATE-AUDIT：false-hint 拒绝门扩展性审计

- 状态：`已注册`
- 类型：post-hoc exploratory、零模型
- 模型调用：0

本实验不再扩大 E4 flight，而是检验一个可部署的回退策略：运行时 gate 通过时使用已冻结 speaker 输出，否则回退 global，并保留全部 target。核心不是在当前样本上调出最好阈值，而是检查规则在 dialogue folds、inventory 宽度和目标密度变化下是否稳定。

候选规则在读取逐 target 结果前固定为：全部词有重复证据、全部词近期出现、inventory 宽度不超过2、近期且宽度不超过4。若规则只在部分切片有效，直接判为 `SCENARIO-DEPENDENT`。由于数据仅来自 ContextASR 电影对话，本审计无法证明跨领域扩展性；最强标签也只是 `WITHIN-SURFACE-STABLE-CANDIDATE`。

- [中文冻结设计](../../plans/2026-08-21-e4-safety-gate-audit.md)
- [正式预注册](../../readiness/2026-08-21-e4-safety-gate-audit-preregistration.md)
- [父实验](E4-DISJOINT-DIR.md)
