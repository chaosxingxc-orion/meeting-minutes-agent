# E4-XDOMAIN-SUPPLY-AUDIT-v2：Earnings-22 供给审计

- 负责人：EuphoriaYan
- 状态：`已判读`
- 类型：零模型、只读文本、探索性供给审计
- 模型调用：0

本实验检验 Earnings-22 的 80 场 discovery 是否有足量、同说话人独有且低集中度的专业实体复现。它使用上游显式实体标签，避免重复使用 v1 在 AMI 上失真的大小写启发式。其余 45 场 reserve 保持不可读，供未来独立模型实验使用。

本次只允许一次 discovery 聚合读取，不下载音频，也不测量转写收益。通过只允许进入音频许可/获取决策和独立 pilot 预注册；不会覆盖 v1 的 `DOMAIN-LIMITED-SUPPLY`。

预读 schema 检查发现普通 reference 没有可用时间戳，因此已在正式读取前登记 amendment，改用同一发布中的 force-aligned reference；其余设计不变。

replacement read 的机器判决为 `EARNINGS22-SUPPLY-FEASIBLE`：80 场中 67 场 eligible，共 1,803 个 speaker-exclusive carry，最大单 surface 占比 8.87%。但 `CONTRACTION + FALLBACK` 占 70.2%，宽类表不能确认“专业实体”供给。较可信的 `ABBREVIATION + ALPHANUMERIC` 有 538 个 exclusive 单元，仍需在未读 45 场 reserve 上按新预注册独立确认。

- [中文冻结设计](../../plans/2026-08-21-e4-xdomain-supply-audit-v2.md)
- [正式预注册](../../readiness/2026-08-21-e4-xdomain-supply-audit-v2-preregistration.md)
- [预读 schema amendment](../../readiness/2026-08-21-e4-xdomain-supply-audit-v2-schema-amendment.md)
- [实现与输入冻结](../../readiness/2026-08-21-e4-xdomain-supply-audit-v2-implementation-amendment.md)
- [失败尝试记录](../../checks/2026-08-21-e4-xdomain-supply-audit-v2-attempt-1-invalid/README.md)
- [预读恢复 amendment](../../readiness/2026-08-21-e4-xdomain-supply-audit-v2-recovery-amendment.md)
- [正式判读](../../readiness/2026-08-21-e4-xdomain-supply-audit-v2-verdict.md)
- [机器结果](../../checks/2026-08-21-e4-xdomain-supply-audit-v2-read/verdict.json)
