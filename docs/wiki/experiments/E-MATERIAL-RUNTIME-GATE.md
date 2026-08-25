# E-MATERIAL-RUNTIME-GATE

- 负责人：EuphoriaYan
- 状态：`依赖门失败，未运行`
- 类型：零模型、开发/确认语义门控
- 预注册：[门控预注册](../../readiness/2026-08-25-material-runtime-gate-preregistration.md)

## 研究问题

在严格独立的六场会议上，仅凭本会议材料的语义 top-1/top-2 差值，能否形成可部署的选择性
dispatch 门？错配会议只作为等宽实验对照，不允许成为运行时选择器。

## 当前结果

状态为 `NOT_RUN_PREREQUISITE_FAILED`。上游准入实验发现 Earnings-22 的 125 场参考词面
都已被 v2 或 v3 的正式供给审计读取，因此无法冻结要求的 3 场开发和 3 场确认队列。按预注册，
本实验在任何材料下载、Pass0 检查、embedding 或 Omni 调用前停止。

这不是“门控效果为负”，而是该效果尚未获得可判读的独立实验面。下一步应先补充新会议，或由
owner 明确接受较弱的 construction-isolated 复用设计后另行注册。owner 已选择后者，新的较弱
实验见 [E-MATERIAL-RUNTIME-GATE-CI](E-MATERIAL-RUNTIME-GATE-CI.md)；本页失败判决保持不变。

- [依赖判读](../../checks/2026-08-25-material-runtime-gate-read/README.md)
