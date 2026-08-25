# E-MEETING-MATERIAL-SUPPLY-AUDIT

- 负责人：EuphoriaYan
- 状态：`已判读`
- 类型：零模型、会议同期官方材料供给审计
- 预注册：[零模型供给审计预注册](../../readiness/2026-08-25-meeting-material-supply-audit-preregistration.md)
- 冻结来源：[官方材料来源表](../../../configs/probes/meeting_material_supply/2026-08-25-source-registry.json)

## 研究问题

与会议同时可得的官方发布稿、业绩演示或prepared remarks，能否为4场冻结Earnings-22会议提供
比单一公司身份更丰富、更准确且带出处的专业词纠错候选？本实验对应agent loop的`ORG`和
`SUPPLY`层；固定前端和`OBS`层不变，当前不接触Omni。

## 冻结设计

仅使用issuer/IR官方域名且明确对应目标季度的材料。每份材料记录发布时间、抓取时间、类型、
字节数和SHA-256；时间证据不充分即判该来源不合格。候选只从材料中构建，并保留文档哈希、
页码和原始文本。Pass0只负责触发，不负责证明候选正确；reference只在冻结所有实现后的一次性
reader中评分。

正确材料与跨会议轮换的等剂量错配材料共同判读。全部供给、精度、分布、负对照、泄漏和预算门
通过，才允许另行注册小型Omni实验；失败则归档，不在已读结果上修改候选或阈值。

## 判读结果

3场会议取得时间合规的官方材料，冻结49个带页码和原文跨度的候选；来源、泄漏和256字符预算门
均通过。一次性reader覆盖979个turn，参考中共有30个候选纠错机会。正确材料臂触发418次，但仅
3次得到参考支持：precision 0.72%、recall 10%，且3次全部集中在Jeronimo Martins一场。
错配材料臂触发336次、正确0次；正确臂只领先0.72个百分点，远低于30点门。

结论为`MEETING-MATERIAL-SUPPLY-INSUFFICIENT`。官方材料能够形成可追溯的候选库存，但当前
字符相似触发器会让`OCF`、`REE`、`LNG`等短缩写大量误触发，尚不能安全地逐chunk供给。这否定
冻结的`ORG -> SUPPLY`路由，不否定材料本身，也不回答Omni在正确路由下能否获益。按预注册不在
本结果上调阈值；后续只能在独立会议上另行注册缩写/专名分层的零模型router审计。

- [材料获取回执](../../checks/2026-08-25-meeting-material-supply-acquisition/README.md)
- [一次性判读](../../checks/2026-08-25-meeting-material-supply-read/README.md)
- [阶段判决](../../readiness/2026-08-25-meeting-material-supply-audit-verdict.md)
