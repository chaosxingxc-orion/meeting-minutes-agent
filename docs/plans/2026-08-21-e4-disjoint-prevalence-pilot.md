# E4-DISJOINT-PREV 资源受限 Pass-0 筛查设计

日期：2026-08-21  
状态：**零模型 roster 设计冻结；模型 flight 尚未注册**  
类型：staged Pass-0 prevalence screening；不运行第二遍，不测转写收益

## 1. 筛查问题

在排除全部299个已见 dialogue 后，`speaker_wrong_disjoint` 在新 Pass-0 状态中的 target prevalence 是否仍接近功效盈亏线 `q*=1963/(4782×0.85)=48.2938%`？该 pilot 只降低对 prevalence 的不确定性，不能确认 E4-DISJOINT 的 carry/WER 效果。

## 2. 冻结 roster

使用与功效审计相同的 ContextASR JSONL 和299-ID排除集。只纳入 score-side `carry_mentions >= 2` 的 dialogue，按 `sha256("e4-disjoint-prev-2026-08-21-v1:" + uniq_id)` 排序，取前60个。分级边界固定为累计20、40、60个 dialogue；不得按 transcript、实体、speaker 或预测难度挑选。

离线 roster builder 只输出 ID、turn 数、时长和 carry 计数。随后单独物化 runtime/score manifests；gold 字段只留在 score manifest，不得进入 launcher 或 prompt。

## 3. Pass-0 与 predicate

每个入选 dialogue 的全部 turn 使用与 E4-CF byte-identical 的模型、mmproj、system instruction、decode 参数和逐 turn 音频流程。状态只来自当前 dialogue 更早的 Pass-0 hypothesis，使用 `min_evidence=1`、dedupe、`inventory_cap=8`，并将 global/speaker/wrong 截成相同非零宽度。

对每个自然 carry target，若任一臂无法形成非零等宽状态则记为 attrition；否则将规范化 speaker 与 wrong 术语集合无交集记为 predicate positive。不得读取第二遍输出，因为本实验不产生第二遍。

## 4. 分级与停止规则

每级只在该级全部 Pass-0 turn 完成后读取聚合 prevalence。报告 target-level point estimate、按 dialogue 固定 seed bootstrap 的80%与90%区间、可用状态率和 cluster counts。

- 20-dialogue 级：若 point estimate `<35%`，停止为 `EARLY-LOW-PREVALENCE`；否则继续。
- 40-dialogue 级：若 point estimate `<40%`，停止为 `EARLY-LOW-PREVALENCE`；否则继续。
- 60-dialogue终点：若 point estimate `>=48.2938%`、80%区间下界 `>=40%`、且 carry-state usable fraction `>=85%`，判 `PREVALENCE-SCREEN-PASS`；若90%区间上界 `<48.2938%`，判 `LOW-PREVALENCE`; 否则判 `INCONCLUSIVE`。

所有阈值均为工程筛查门，不是确认性显著性检验。即使通过，也只允许重新评估完整 flight 的成本，不自动授权第二遍或 agent loop。

## 5. 资源与注册门

模型接触前必须由零模型 roster census 写出各级精确 calls、audio seconds、JSONL/roster/audio hashes，并冻结 launcher、scorer、最大调用数和最大音频秒数。最大预算不得超过60-dialogue roster 的精确 Pass-0 总量；每20-dialogue边界均需生成独立 receipt。

