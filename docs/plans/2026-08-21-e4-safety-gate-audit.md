# E4-SAFETY-GATE-AUDIT：false-hint 拒绝门与扩展性审计

日期：2026-08-21

状态：**已冻结；逐 target 结果尚未读取**

## 研究问题

`E4-DISJOINT-DIR` 显示 speaker 状态带来很小的 carry 正方向，但 false-hint target rate 增加3.49个百分点并越过安全门。本审计检验：仅依赖运行时可见的历史证据，能否决定“使用 speaker 输出或回退 global”，并在 dialogue fold、inventory 宽度与目标密度变化下保持安全和收益方向。

本实验是 post-hoc、零模型、探索性审计。它不能证明跨领域扩展性；当前样本全部来自 ContextASR 电影对话。即使内部稳定，也只能产生 `WITHIN-SURFACE-STABLE-CANDIDATE`。

## 冻结候选策略

每个 gate 通过时选择 `D1-speaker` 已冻结输出，否则选择 `D0-global`；不得丢弃 target。候选顺序固定为：

1. `all_terms_repeated`：speaker inventory 每一项 evidence count 至少2；
2. `all_terms_recent_le3`：每一项最近一次同 speaker 支持距当前 turn 不超过3；
3. `inventory_le2`：等长 inventory 宽度不超过2；
4. `recent_le3_and_inventory_le4`：同时满足近期支持与宽度不超过4。

不得读取结果后新增阈值、改变顺序或组合规则。所有 evidence、recency、width 均从 Pass-0 hypothesis 与 runtime speaker/turn 信息重建，不使用 reference、carry label 或第二遍输出。

## 指标与稳定性门

所有差值均为 gate policy 减全局 `D0-global`，覆盖率是实际选择 speaker 的 target 比例。

- 覆盖门：至少25%的 target、至少20个 dialogue；
- 总体收益：carry hit delta `>0` 且 carry NE-WER delta `<0`；
- 总体安全：WER delta `<=0.01` 且 false-hint target-rate delta `<=0.02`；
- dialogue 稳定性：按 `sha256("e4-safety-gate-fold-v1:" + uniq_id) mod 4` 固定四折；每折至少选择3个 target，四折均通过安全门，至少三折的两个收益方向同时成立；
- width 稳定性：宽度分为1、2–4、5–8；至少两个分层各含8个被 gate 选中的 target，所有可用分层均通过安全门，至少两个分层的两个收益方向同时成立；
- target-density 只作描述：dialogue 含1个 target 与至少2个 target 两层均报告，不参与候选选择。

## 冻结决策

1. 若无候选通过覆盖门：`NO-USABLE-COVERAGE`；
2. 若候选通过覆盖门但无候选通过总体收益与安全门：`NO-SAFE-GATE`；
3. 若至少一个候选通过总体门、但无候选通过 fold 与 width 稳定性门：`SCENARIO-DEPENDENT`；
4. 否则选择固定顺序中第一个全部通过者：`WITHIN-SURFACE-STABLE-CANDIDATE`。

任何结果都不放行模型 flight、完整 E4、E5 或 agent loop。跨语料、会议类型和专业领域扩展性始终记为 `not_identified`；若要验证，必须使用独立新 surface 重新预注册。
