# E4-DISJOINT-POWER 零模型功效审计设计

日期：2026-08-21  
状态：**设计冻结；真实输入当前不可用，正式 census 尚未注册或执行**  
类型：零模型、score-side roster/power audit

## 1. 目的与证明边界

本审计只回答：在排除全部 299 个已见 dialogue 后，ContextASR 是否有足够 carry 供给，以独立确认固定 `speaker_wrong_disjoint` policy。它不验证策略效果。

该 predicate 依赖 Pass-0 假设产生的 speaker/wrong inventory，未见 dialogue 在零模型阶段没有此状态。因此新 surface 的真实 predicate prevalence 和 outcome ICC **不可由本审计识别**。工具只使用语料 score-side 标注计算 carry 供给，并对 prevalence 做冻结情景分析；这些字段不得进入运行时 prompt。

## 2. 冻结输入与排除

- ContextASR English JSONL，期望 SHA-256：`4bbf64387d1c581df2c7ab5db9af4461e1112ee489377b67084c9b40cb6d45e8`。
- 排除 E3 的 12 个 discovery dialogue。
- 排除 E4-CF candidate roster 的 287 个 dialogue。
- 合并后必须恰为 299 个不同 ID；否则失败关闭。

## 3. 冻结功效假设

- 双侧 `alpha=0.05`，power `0.80`；paired discordance `0.15`；dialogue design effect `1.5`；可用状态率 `0.85`。
- 主 MDE 为 `3 pp`，并报告 `4 pp`、`5 pp`。
- 主规划 prevalence 为保守的 `0.40`，并报告 `0.50` 和 E4-CF 描述值 `418/774`。该值不是新数据估计。
- 所需原始 carry mass 为 `ceil(required_paired_mentions / (prevalence × 0.85))`。
- roster 按 `sha256(seed:uniq_id)` 排序，只纳入至少 2 个同 speaker carry mention 的 dialogue，取达到目标 carry mass 的最短前缀。

## 4. 调用与音频预算

Pass-0 对 roster 全部 turns 执行。第二遍中 D0-global 与 D1-speaker 对全部 target 执行；D3-wrong 只对预计 disjoint target 执行。D2-policy 不产生额外调用：predicate 为真时复用 D1，否则复用 D0。预算同时报告这个去重方案和四臂朴素上界。

## 5. 机器判决与输出

若剩余语料在主假设下 carry mass 不足，判 `INSUFFICIENT-CARRY-SUPPLY`；否则判 `SCENARIO-POWER-READY-PREVALENCE-UNVERIFIED`。后一判决只允许 owner 审阅预算；在模型接触前还必须冻结 Pass-0 后的 predicate attrition gate、数值安全门、失败处理和一次性 read suite。

正式输出目录为 `docs/checks/2026-08-21-e4-disjoint-power/`，若已存在必须拒绝覆盖。当前 E: 数据盘不可用时，不得用旧汇总近似正式 verdict。

