# E-MATERIAL-OMNI-CAPABILITY-CI

- 负责人：EuphoriaYan
- 状态：`未放行`
- 证据等级：`CONSTRUCTION_ISOLATED_EXPLORATORY`
- 类型：三臂Omni能力实验的零模型预算与可执行性审计
- 冻结配置：[预算与前置审计](../../../configs/probes/material_omni_capability/2026-08-26-prereg-audit.json)
- 判读：[不运行判决](../../readiness/2026-08-26-material-omni-capability-prereg-audit-verdict.md)

## 研究问题

在`E-MATERIAL-RUNTIME-GATE-CI`已证明语义dispatch信号存在后，现有冻结产物能否直接构造
`R0-retain / R1-correct-dispatch / R2-deranged-dispatch`的精确Omni runtime manifest、预算和
一次性reader。

## 零模型结果

确认集聚合记录包含850个eligible turn和636个dispatch turn。若逐turn身份已经冻结，R1与R2
各需636次调用，总预算1,272次；两条active arm的模型接触音频只能界定在7,711.296至
22,150.248秒，因为无法知道具体被dispatch的turn。

配对5个百分点效应在discordant fraction为10%、20%、30%时分别需要314、628、942对；636个
聚合dispatch只支持到约20.26%。更关键的是，当前没有冻结primary wrong-to-correct机会数，
因此不能把636直接当作功效样本量。

## 不运行原因

8月25日确认产物只保存逐会聚合，没有保存636个turn的身份、selector gap、correct candidate value
和deranged candidate value。为恢复这些字段而重新调用embedding会构成新的trace-materialization
读取，不能伪装成离线预注册，也不得改写既有确认结果。因此当前无法冻结精确runtime manifest或
绑定一次性reader，判为`NOT_RUN_MISSING_FROZEN_FLIGHT_INPUTS`。

本审计为0 embedding、0 Omni、0 reference。下一步只能二选一：在新surface上前瞻性持久化trace；
或另行注册并明确授权一次不改变阈值/判决的trace-materialization读取。

- [审计回执](../../checks/2026-08-26-material-omni-capability-prereg-audit/README.md)
