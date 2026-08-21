# E4-XDOMAIN-SUPPLY-AUDIT-v2：Earnings-22 供给审计

- 负责人：EuphoriaYan
- 状态：`已注册`
- 类型：零模型、只读文本、探索性供给审计
- 模型调用：0

本实验检验 Earnings-22 的 80 场 discovery 是否有足量、同说话人独有且低集中度的专业实体复现。它使用上游显式实体标签，避免重复使用 v1 在 AMI 上失真的大小写启发式。其余 45 场 reserve 保持不可读，供未来独立模型实验使用。

本次只允许一次 discovery 聚合读取，不下载音频，也不测量转写收益。通过只允许进入音频许可/获取决策和独立 pilot 预注册；不会覆盖 v1 的 `DOMAIN-LIMITED-SUPPLY`。

- [中文冻结设计](../../plans/2026-08-21-e4-xdomain-supply-audit-v2.md)
- [正式预注册](../../readiness/2026-08-21-e4-xdomain-supply-audit-v2-preregistration.md)

