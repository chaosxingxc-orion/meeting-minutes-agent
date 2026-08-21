# E4-DISJOINT-POWER：固定策略功效与 roster 审计

- 状态：`已判读`
- 正式机器判决：`INSUFFICIENT-CARRY-SUPPLY`
- 类型：零模型 census
- 模型调用：未授权
- 前置结论：`E4-CF-MECH` 仅生成 `speaker_wrong_disjoint` 假设

本任务在不接触模型输出的前提下，检查独立确认实验是否具备足够样本和预算可行性。候选策略固定为：correct-speaker 与 wrong-speaker 术语集合不重叠时使用 speaker state，否则使用等宽 global state。

审计必须排除全部 299 个已见 dialogue（E4-CF 的 287 个和发现阶段的 12 个），只在离线 score-side planner 中读取语料标注来计算 carry 供给，标注不得进入 runtime。由于未见 dialogue 尚无 Pass-0 状态，predicate prevalence 只能做冻结情景分析，不能直接估计。输出包括 carry supply、dialogue clustering、最小可检测效应、调用数和重复音频时长。

在数字阈值、失败处理、一次性判读流程和 owner 预算授权全部冻结前，不得注册 flight，也不得调用模型。

## 2026-08-21 进展

零模型设计、CLI、功效模块和测试已经冻结；新旧 E4 power 测试共 8/8 通过。排除集为 12+287、零重叠、合计 299。

主情景固定为 MDE 3 pp、predicate prevalence 40%、可用状态率 85%，需要 1,963 个可分析 predicate carry，即 5,774 个原始 carry。上一轮同源汇总只能推算剩余 carry 为 6,423，因此主情景约消耗 89.9% 的剩余供给，预算风险很高。

E: 恢复后已执行唯一一次正式 census。排除299个已见 dialogue 后剩4,974个 dialogue、6,423个总 carry；但冻结的 `carry_mentions >= 2` eligible pool 只有1,634个 dialogue、4,782个 carry。主情景需要5,774，短缺992，因此判为 `INSUFFICIENT-CARRY-SUPPLY`，没有生成主 roster。

3 pp 在假设 prevalence 50%/54.01% 时数学上可行，但分别需要31,749/29,536次去重调用和101.55/94.51小时重复音频；新数据 prevalence 在 Pass-0 前不可识别。当前不启动模型 flight，不事后放宽 MDE 或 prevalence。

后续 `E4-DISJOINT-PREV` 用60个 dialogue、795次 Pass-0 调用测得52.76% prevalence，说明50%情景可用于规划，但并未降低完整确认的31,749-call成本，也没有测试策略效果。

- [预注册草案](../../readiness/2026-08-21-e4-disjoint-policy-preregistration-draft.md)
- [冻结功效设计](../../plans/2026-08-21-e4-disjoint-power-audit.md)
- [实现与阻塞记录](../../readiness/2026-08-21-e4-disjoint-power-preflight.md)
- [正式注册](../../readiness/2026-08-21-e4-disjoint-power-registration.md)
- [正式判读](../../readiness/2026-08-21-e4-disjoint-power-verdict.md)
- [机器结果](../../checks/2026-08-21-e4-disjoint-power/verdict.json)
- [机制审计判读](../../readiness/2026-08-21-e4-cf-mechanism-verdict.md)
- [机制审计实验页](E4-CF-MECH.md)
- [低资源 prevalence 筛查](E4-DISJOINT-PREV.md)
