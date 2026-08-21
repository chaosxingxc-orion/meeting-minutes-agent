# E4-POWER 独立确认实验功效审计预注册

日期：2026-08-20  
状态：**REGISTERED；尚未运行 census 输出**

## 目标

在不接触模型的前提下，确定一个未见 ContextASR-Dialogue confirmatory E4 为检测 speaker state 相对 wrong-speaker 的 5 个百分点 carry exact 改善，需要多少自然 carry mentions、对话、调用和音频预算。该审计不重新解释 E4-36 的 `2/3` 近失，也不授权启动 confirmatory flight。

## 冻结输入与排除

- 数据：`ContextASR-Dialogue_English.jsonl`，sha256 `4bbf64387d1c581df2c7ab5db9af4461e1112ee489377b67084c9b40cb6d45e8`。
- 排除 E3/E4 已见 12 dialogues；排除 manifest file sha256 `8adce09605db05158006bc7fd82bc77acd826e4ffd1591a8ef8eee91b045ff9f`。
- 合格单位：同一 speaker 的实体在历史 turn 出现，并在后续 target turn 再出现；每个 dialogue 至少 2 个 carry mentions。
- 排序：`sha256(seed:uniq_id)`，seed `e4-confirmatory-2026-08-20-v1`；取最短前缀达到目标质量。
- gold 只用于离线 census/候选 roster，不进入未来模型请求。

## 冻结统计假设

- 双侧 alpha 0.05，power 0.80。
- 最小有意义效应（MDE）5 pp。
- 配对二元结果 discordance rate 0.15。
- dialogue clustering design effect 1.5。
- 状态可构造/可评分比例 0.85，即额外预留 15% attrition。
- confirmatory core 只预算四臂：bare、global、correct-speaker、wrong-speaker；corrupt 风险已在 E4-36 测得，若再次运行应另设小型 sentinel，不混入主功效公式。

配对正态近似：

```text
n_effective = ceil((z_0.975 + z_0.80)^2 * discordance / MDE^2 * design_effect)
n_selection = ceil(n_effective / usable_fraction)
```

同时报告 5、7.5、10 pp 三个 MDE 情景。机械结论为：语料能提供目标前缀则 `CONFIRMATORY-FEASIBLE-BUT-LARGE`，否则 `INSUFFICIENT-CARRY-SUPPLY`。本任务不根据预算大小改变 MDE。

## 实现与输出

- 公式/census module sha256：`fda7ed2f93ee77b177c8ad113de77e73f8984ad22604134cfd8579e8ecd16b9b`
- driver sha256：`6ec3906d46859e08e5310482e9dfd3f921e35a2ef88dc337633f5ef047f24b13`
- tests sha256：`f29dc0a68dd730c512c4cec554bbbd8ecc888ecc2d72c5cab68820f091fb2fcf`
- 预建专项测试：4 passed。
- 一次性输出：`docs/checks/2026-08-20-e4-power/{verdict.json,report.txt}` 和 `configs/probes/contextasr/2026-08-20-e4-confirmatory-candidate-roster.json`；任何输出已存在时拒绝覆盖。
