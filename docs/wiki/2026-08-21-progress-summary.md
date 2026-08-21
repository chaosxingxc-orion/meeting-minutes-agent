# 2026-08-21 研究进展总结

## 今日结论

今天完成了从 E4-CF 机制解释、独立供给与资源审计、低资源方向性 pilot、安全门审计，到跨领域新语料筛查的一整条证据链。最终判断不是“speaker 路由已经可用”，而是：**当前等长 speaker inventory 的小幅 carry 收益不稳定，false-hint 风险超过安全门，简单拒绝规则又会同时消除收益，因此该策略停止扩展。**

数据侧，Academic/ICSI 的严格技术 carry 供给充足，Product/AMI 不足；Earnings-22 的广义标签复现充足，但标签体系被 `CONTRACTION/FALLBACK` 主导，尚未确认专业技术词供给。今天新增的 Earnings-22 工作全部为零模型、文本层读取；45 场 reserve、音频、完整模型 flight 与 agent loop 均未启用。

## 今日完成总览

| 工作 | 结果 | 对下一步的约束 |
|---|---|---|
| 同步远端与历史证据 | 确认 PRECOMP Wave-1/2 和 G1/Z 系列已有完整证据 | 不重复造轮子，不重跑 Z 系列 |
| E4-CF 机制审计 | 只保留 `speaker_wrong_disjoint` 假设 | 只能做独立功效/方向验证 |
| E4-DISJOINT-POWER | `INSUFFICIENT-CARRY-SUPPLY` | 不启动约31,749-call完整 flight |
| E4-DISJOINT-PREV | 52.76%，`PREVALENCE-SCREEN-PASS` | 只支持低资源规划，不证明效果 |
| E4-DISJOINT-DIR | `EXPLORATORY-HARMFUL` | false-hint +3.49 pp，固定策略不可部署 |
| E4-SAFETY-GATE-AUDIT | `NO-SAFE-GATE` | 停止在同一结果上调简单阈值 |
| E4-XDOMAIN-SUPPLY-AUDIT | `DOMAIN-LIMITED-SUPPLY` | Academic 通过，Product/AMI 严格供给不足 |
| Earnings-22 获取与 v2 审计 | 文本层锁定在 D 盘；广义标签机械通过 | 先用未读 reserve 确认窄类，暂不获取音频 |

完整离线回归为 **1,508 passed、25 skipped**。所有新增实验均已登记设计、实现、失败尝试、机器结果和正式判读。

## 完成事项

1. 在读取真实分层前冻结 carry 变化分类、false-hint 分类、四个 runtime predicate、覆盖/收益/安全阈值和三选一决策顺序。
2. 新增机制审计模块、一次性 CLI 和 4 项单元测试；774/774 个状态从 Pass0 历史重建并与 binding 完全一致。
3. 执行唯一一次正式读取；E4-CF 联合回归测试 7/7 通过。
4. 归档机器结果、正式判读和输入/代码/输出哈希。
5. 起草 E4-DISJOINT 固定策略预注册；下一步只做零模型 power/roster audit，尚未授权模型接触。

## 主要发现

- Speaker 相对 bare：66 repairs、21 breaks，净 +45 carry hits。
- Global 相对 bare：50 repairs、23 breaks，净 +27。
- Wrong 相对 bare：47 repairs、20 breaks，净 +27。
- Speaker 的额外路由收益因此来自 18 个净命中。
- 109 次 speaker false hint 中，90 次来自单次证据词，108 次距最近 mention 至少 3 turns。
- 仅 1 次 false hint 与净 carry 修复且无 WER 伤害同时发生；41 次位于无净 carry 收益且 WER 更差的 target。

## Predicate 筛选

| Predicate | 覆盖 | Speaker-global hit | Speaker-wrong hit | False-hint target 差 | 结果 |
|---|---:|---:|---:|---:|---|
| all terms repeated | 0 targets | — | — | — | 无覆盖 |
| recent support ≤3 | 68 targets | +3.85 pp | +6.41 pp | +1.47 pp | 覆盖与安全不通过 |
| inventory ≤4 | 376 targets | +5.04 pp | +5.29 pp | +2.39 pp | 安全不通过 |
| **speaker/wrong disjoint** | **418 targets** | **+3.79 pp** | **+4.24 pp** | **+0.96 pp** | **唯一入选** |

## 当日阶段性结论

1. **可达性已经部分成立。** Omni 会读取实体条件，合法的 speaker state 也可以从历史构造；因此“文本供给影响转写”不是空假设。
2. **speaker-specific 增益尚未成立。** E4-CF 只有 +2.16 pp，低于 +5 pp 门；独立方向 pilot 又被 false-hint 安全风险否决。
3. **当前 controller policy 已到停止点。** `speaker_wrong_disjoint` 和简单 evidence/recency/width gate 均没有形成安全、稳定、可扩展的策略。
4. **主要瓶颈转移到数据供给定义。** ICSI 有供给，AMI 缺严格技术 carry；Earnings-22 有重复，但“上游标签”不等于“专业实体”。
5. **agent loop 仍不可启动。** 尚不存在经独立数据验证、同时满足收益和安全门的单步改进算子，所以还不能证明多轮优化会单调改进。

## 下一步

当前 ContextASR surface 不再启动 E4-DISJOINT 模型 flight。下一研究动作只能是寻找新增独立 carry-dense 数据源，或把 staged Pass-0 作为新设计重新预注册；不得事后放宽当前门槛。

结合 Earnings-22 的最新结果，优先建议是：先决定是否消耗45场未读 reserve；若同意，则只预注册 `ABBREVIATION/ALPHANUMERIC` 窄类零模型确认审计。该结果通过前，不处理音频许可和下载，也不设计模型 pilot。

### E4-DISJOINT-POWER 续跑情况

已冻结并实现零模型功效工具，离线测试 8/8 通过，299 个排除 ID 校验通过。由于 predicate 需要新的 Pass-0 状态，零模型阶段只能做 prevalence 情景分析，不能在未见数据上直接估计 prevalence。主情景（3 pp MDE、40% prevalence）需要 5,774 个原始 carry，约占上一轮同源汇总所推算剩余供给 6,423 的 89.9%。

E: 数据盘恢复后，冻结工具完成了唯一一次正式 census，机器判决为 `INSUFFICIENT-CARRY-SUPPLY`。剩余4,974个 dialogue 共6,423个 carry，但 eligible pool 仅1,634个 dialogue、4,782个 carry，低于主情景所需5,774，短缺992。

3 pp 情景只有在假设 prevalence 至少50%时才可构造 roster，代价仍为31,749次调用、101.55小时重复音频；沿用 E4-CF 的54.01%描述值也需29,536次调用、94.51小时。因为新 surface prevalence 尚不可识别，当前不放行模型 flight，也不放行 agent loop。

### E4-DISJOINT-PREV 低资源筛查

为降低资源，新增20/40/60-dialogue staged Pass-0 pilot，上限795 calls、2.58小时音频，不运行第二遍。实际795/795成功、零重试，消耗2.564小时。

prevalence 从20级的62.96%、40级的54.81%收敛到60级的52.76%；最终163/164个 target 状态可用，80% cluster interval 为46.71%–59.01%，usable carry 99.43%，判为 `PREVALENCE-SCREEN-PASS`。这支持约50%的资源规划假设，但没有新增任何转写效果证据；完整确认的高成本问题仍然存在。

如果继续，建议只另起约172次调用的 D0-global vs D1-speaker 方向性 pilot，明确标为 underpowered exploratory；在新注册和授权前不调用第二遍。

证据入口：[机制审计判读](../readiness/2026-08-21-e4-cf-mechanism-verdict.md)、[机制机器结果](../checks/2026-08-21-e4-cf-mechanism-read/verdict.json)、[功效审计判读](../readiness/2026-08-21-e4-disjoint-power-verdict.md)、[功效机器结果](../checks/2026-08-21-e4-disjoint-power/verdict.json)。

### 远端同步更正

同步 `origin/master` 后确认，PRECOMP 已完成 Wave-1 dev-18 与 Wave-2 supplement 76/76；G1/Z 四臂也已完成 1,932-call floors campaign 和一次性描述性读取。同事截图中的 Z-turn/Z-oracle/Z-free/Z-nodiar 数值已有仓库证据，不再标记为“待归档”。该结果不改变 E4 的研究问题：G1 主要测量转向表、归属输出与切片几何，E4 测量同一固定音频片段上 speaker-specific 文本状态的增益。

### E4-DISJOINT-DIR 方向性实验

已完成冻结的86 targets、172 cells。首轮171/172后因浮点预算边界残差在网络请求前停止；登记 amendment 并获明确授权后，仅补跑机械确认的唯一缺失 cell，零重试，最终集合完整。

正式判读为 `EXPLORATORY-HARMFUL`：speaker 相对 global 的 carry hit +1.08 pp、carry NE-WER -0.70 pp、总体 WER不变，但 false-hint target rate +3.49 pp，超过预注册的+2 pp安全门；carry对比的95% cluster区间均跨零。当前等长 speaker inventory 不可部署，完整确认和 agent loop 不放行。下一步若继续，应先研究只依赖运行时可见证据的拒绝门，而不是扩大现有 flight。

### E4-SAFETY-GATE-AUDIT 零模型审计

已按读取前冻结的四个候选执行唯一一次审计，判为 `NO-SAFE-GATE`。重复证据门覆盖为0；近期门只覆盖10–11个 target、无 carry 增益并各新增1个 false hint。`inventory_le2` 是唯一通过覆盖与安全门的规则（27/86 targets、24 dialogues、false-hint增量0），但 carry hit和carry NE-WER增益也都归零。

因此简单 evidence/recency/width 门不是可扩展候选：它在当前 surface 内已无法兼顾收益与安全，跨领域能力更不可识别。停止在同一结果上继续调阈值；完整 flight、E5 和 agent loop 均不放行。

### E4-XDOMAIN-SUPPLY-AUDIT 跨领域供给审计

在不调用模型、不解码音频的条件下，冻结并读取了102场 QMSum train 会议：61场 Product/AMI `glossary-discovery` 和41场 Academic/ICSI；两个领域的 val/test 均未读取。机械判决为 `DOMAIN-LIMITED-SUPPLY`。

Academic 的41场全部 eligible，共753个 speaker-exclusive carry、254个严格技术型 carry，全部门槛通过。Product 有35场 eligible、187个 exclusive carry，总量与集中度通过，但严格技术型 carry 只有3个，低于冻结门槛10。Product 的重复主要落在容易被大写启发式高估的 `name_like` 代理上，不能事后删除严格门。因此不启动平衡跨域模型 pilot；若要继续，应先寻找新的 Product/business meeting surface，或另行决策并预注册 Academic 域内 pilot。

### Earnings-22 新 surface 审计

已将 Earnings-22 文本层固定到官方提交，按 salted SHA-256 划分为80场 discovery 与45场 reserve。首次正式读取因一个文件含官方文档所述 `wer_tags` 列而 fail closed，未输出统计；失败记录与恢复 amendment 均已提交。replacement read 模型调用为0，45场 reserve 保持未读。

机器判决为 `EARNINGS22-SUPPLY-FEASIBLE`：67/80场 eligible，1,803个 speaker-exclusive carry，最大单 surface 占8.87%。但 `CONTRACTION/FALLBACK` 占1,266个（70.2%），说明宽类表主要测到广义 WER 标签复现，不能确认专业实体供给。`ABBREVIATION/ALPHANUMERIC` 有538个 exclusive 单元，但尚无独立 meeting-level 门。若继续，应只在未读 reserve 上新注册窄类确认审计；音频、模型 pilot 与 agent loop 仍未放行。
