# E4-XDOMAIN-SUPPLY-AUDIT：跨领域 speaker carry 供给审计

- 状态：`已判读`
- 类型：零模型、只读语料、探索性供给审计
- 模型调用：0

本实验检查 Product/AMI 与 Academic/ICSI 是否都具备足量、同说话人独有的术语代理复现，以支持后续平衡跨领域 pilot。正式判决为 **`DOMAIN-LIMITED-SUPPLY`**。

Academic/ICSI 全部 41 场会议 eligible，共有 753 个 speaker-exclusive carry，其中 254 个是缩写或字母数字型严格技术代理，所有门槛通过。Product/AMI 的 61 场中有 35 场 eligible，共 187 个 exclusive carry，会议数、总量和集中度均通过；但严格技术代理只有 3 个，低于冻结门槛 10。

因此问题不是 Product 完全没有重复词，而是它的供给主要来自 `name_like` 大写代理。既有 AMI census 已证明该启发式会显著高估开放词表专名，不能在读数后删除严格门。Academic 可以支持另行设计域内 pilot；当前数据不能支持平衡跨域 pilot，也没有测量 Omni 效果或 false-hint 安全。

- [中文冻结设计](../../plans/2026-08-21-e4-xdomain-supply-audit.md)
- [正式预注册](../../readiness/2026-08-21-e4-xdomain-supply-audit-preregistration.md)
- [实现 amendment](../../readiness/2026-08-21-e4-xdomain-supply-audit-implementation-amendment.md)
- [正式判读](../../readiness/2026-08-21-e4-xdomain-supply-audit-verdict.md)
- [机器结果](../../checks/2026-08-21-e4-xdomain-supply-audit-read/verdict.json)
