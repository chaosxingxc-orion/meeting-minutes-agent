# E4-CF-MECH 冻结结果机制审计设计

日期：2026-08-21  
状态：**设计冻结；实现与测试完成后、首次读取前转为正式注册**  
类型：零模型、post-hoc exploratory；不得修改 E4-CF 的 `DIRECTIONAL-NOT-CONFIRMED`

## 1. 问题与输入

本审计解释 E4-CF 中 correct-speaker 相对 wrong/global 的小幅收益，以及 `CF2-speaker` 的 109 次 false-hint activation。只读取冻结的 Pass-0 manifest/responses、runtime/score binding、第二遍 responses 和正式 verdict；不接触模型，不输出原始 transcript、reference、实体或 target ID。

## 2. 冻结分类

对每个 carry entity，以 bare 为基准，将每个语义臂分类为：

- `repair`：bare miss、该臂 hit；
- `break`：bare hit、该臂 miss；
- `retained`：两者均 hit；
- `missed`：两者均 miss。

false hint 定义保持正式 scorer 不变：注入词不在 reference、但出现在该臂输出。每次激活在词项层面均为 `reference-inconsistent`；目标级只分类为：

- `net-carry-gain/no-wer-harm`；
- `net-carry-gain/wer-harm`；
- `no-net-carry-gain/no-wer-harm`；
- `no-net-carry-gain/wer-harm`。

其中 net carry gain 比较该臂与 bare 的 carry hit 数；WER harm 表示该臂的整句 word-error count 高于 bare。该分类是描述性关联，不解释为因果。

## 3. 运行时可见特征

使用与 binding builder 相同的 `min_evidence=1 + inventory_cap=8` 提取器重建 global、speaker、wrong 状态，并逐 target 验证重建术语与冻结 binding 完全一致。只汇总：

- inventory size；
- 每个注入词的 evidence count；
- 支持该词的历史 turn 数；
- 目标 turn 与最近一次历史 mention 的 turn-index gap；
- speaker/wrong 术语集合是否完全不重叠；
- false hint 在注入列表中的 rank。

预先固定四个候选 predicate：`all_terms_repeated`、`recent_support_le_3`、`inventory_le_4`、`speaker_wrong_disjoint`。它们只用于提出下一次独立实验假设，不能从本批结果产生确认性主张。

## 4. 三选一机器决策

每个 predicate 至少覆盖 100 targets 和 50 dialogues，且同时满足以下探索性筛选条件，才可成为 `PREREGISTER-ONE-FIXED-POLICY`：

1. speaker-global carry hit-rate 差至少 +3 pp；
2. speaker-wrong carry hit-rate 差至少 +3 pp；
3. speaker-global WER 差不大于 0；
4. speaker false-hint target rate 不高于 global 超过 1 pp。

若多个 predicate 合格，按 `all_terms_repeated → recent_support_le_3 → inventory_le_4 → speaker_wrong_disjoint` 固定顺序只选第一个。

若整体 speaker-bare WER 恶化超过 1 pp，或 speaker false-hint target rate 比 global 高至少 5 pp 且 speaker-global carry hit 差不为正，则判 `SAFETY-RISK-DOMINATES`。否则若无合格 predicate，判 `NO-ACTIONABLE-MECHANISM`。

该决策只决定是否值得起草一个新预注册，不授权模型调用，也不改变 E4-CF 正式 verdict。

## 5. 冻结输出

- 代码：`src/meeting_minutes_agent/probes/e4_mechanism.py`
- CLI：`scripts/e4_mechanism_read.py`
- 测试：`tests/unit/probes/test_e4_mechanism.py`
- 正式输出：`docs/checks/2026-08-21-e4-cf-mechanism-read/{verdict.json,report.txt,README.md}`
- 人工判读：`docs/readiness/2026-08-21-e4-cf-mechanism-verdict.md`

正式读取目录若已存在必须拒绝覆盖。完成后只允许一次 Wiki 状态更新；任何新增分层必须登记为新的 post-hoc 分析。
