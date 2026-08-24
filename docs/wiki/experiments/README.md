# 实验总表

本表是当前实验进展的唯一导航页；数值结论必须跟随证据链接引用。

| ID | 研究问题 | 状态 | 当前结论 | 下一步 |
|---|---|---|---|---|
| [ENTITY-DENSITY](ENTITY-DENSITY.md) | 哪个语料适合专业词/实体优化？ | 已判读 | ContextASR 适合高密度供给能力探针；Earnings21 更适合会议内复现词表 | 按任务选择语料，不混用结论 |
| [P-ATTR](P-ATTR.md) | 说话人归属应由模型完成还是控制器装配？ | 已判读 | 采用 attribution-by-construction；模型只转写，控制器附加 speaker | 作为后续固定前端 |
| [P-PROMPT](P-PROMPT.md) | 基础转写提示词采用哪种形式？ | 已判读 | 锁定 T1-A1；腐败上下文结果不确定 | 后续新增上下文需独立验证 |
| [DIAR-SMOKE](DIAR-SMOKE.md) | 固定前端采用哪个 diarizer？ | 已判读 | 经 owner adjudication 锁定工具 B | 不再作为当前优化变量 |
| [PRECOMP](PRECOMP.md) | G1 运行所需切片与特征缓存是否备好？ | 已判读 | Wave-1 dev-18 完成；Wave-2 supplement 76/76 完成；不是模型效果结果 | 作为冻结数据供给复用 |
| [C-CTX](C-CTX.md) | Omni 能否利用文本实体条件改善短片段专业词转写？ | 已判读 | 对正确实体强响应，但未跨过预注册可达阈值，判为 `CONTEXT-SENSITIVE-BUT-UNCONTROLLED` | 后续 E3/E4/E4-CF 已完成；保留为 oracle 能力证据 |
| [E3-STATE](E3-STATE.md) | 不用 gold 能否构造低污染、按 speaker 路由的状态？ | 已判读 | `LEGAL-STATE-READY`；precision 90.04%，hallucination 9.96%，carry recall 57.50% | 状态已用于 E4 与 E4-CF；后续审计收益/污染机制 |
| [E4-CONDITIONING](E4-CONDITIONING.md) | 合法 speaker state 能否改善固定完整第二遍？ | 已判读 | `CONTEXT-SENSITIVE-NOT-SPEAKER-SPECIFIC`；修复/路由门均以 2 对 3 近失 | 未见数据的 E4-POWER/E4-CF 已完成 |
| [E4-POWER](E4-POWER.md) | 独立 confirmatory E4 需要多大样本和预算？ | 已判读 | 5 pp 需要 287 dialogues、6,922 calls、22.01 h | 已授权并完成 E4-CF |
| [E4-CONFIRMATORY](E4-CONFIRMATORY.md) | 5 pp speaker-routing 改善能否在未见对话确认？ | 已判读 | `DIRECTIONAL-NOT-CONFIRMED`；+2.16 pp、CI 为正但低于 5 pp 门 | 做冻结结果机制分析；不放行 agent loop |
| [E4-CF-MECH](E4-CF-MECH.md) | 小路由收益与 false-hint 的机制是什么？ | 已判读 | `PREREGISTER-ONE-FIXED-POLICY`；唯一入选 `speaker_wrong_disjoint` | 先做未见 surface 的零模型功效/roster 审计 |
| [E4-DISJOINT-POWER](E4-DISJOINT-POWER.md) | 固定 disjoint policy 是否有足够独立样本与可接受预算？ | 已判读 | `INSUFFICIENT-CARRY-SUPPLY`；eligible carry 4,782 < 主情景所需 5,774 | 不启动模型 flight；新数据源或新设计需重新注册 |
| [E4-DISJOINT-PREV](E4-DISJOINT-PREV.md) | 小型 Pass-0 能否支持约50%的 disjoint prevalence 假设？ | 已判读 | `PREVALENCE-SCREEN-PASS`；52.76%，80%区间46.71%–59.01%，795 calls | 只支持资源规划；效果 pilot 需另行授权和注册 |
| [E4-DISJOINT-DIR](E4-DISJOINT-DIR.md) | predicate-positive target 上 speaker 是否优于等长 global？ | 已判读 | `EXPLORATORY-HARMFUL`；carry方向小幅改善，但 false-hint +3.49 pp 超过安全门 | 不部署当前等长 speaker inventory；如继续须先注册运行时拒绝门 |
| [E4-SAFETY-GATE-AUDIT](E4-SAFETY-GATE-AUDIT.md) | 运行时拒绝门能否保留小收益并跨场景切片稳定？ | 已判读 | `NO-SAFE-GATE`；唯一有覆盖的 width≤2 门同时消除了全部 carry 增益 | 不在同一结果上继续调阈值；只考虑独立新 surface 或不同信号 |
| [E4-XDOMAIN-SUPPLY-AUDIT](E4-XDOMAIN-SUPPLY-AUDIT.md) | Product/AMI 与 Academic/ICSI 是否都有足量 speaker-exclusive 术语代理供给？ | 已判读 | `DOMAIN-LIMITED-SUPPLY`；Academic 全部门槛通过，Product 严格技术 carry 仅 3 < 10 | 不启动平衡跨域 pilot；寻找新的 Product/business surface，或另行决策 Academic 域内设计 |
| [E4-XDOMAIN-SUPPLY-AUDIT-v2](E4-XDOMAIN-SUPPLY-AUDIT-V2.md) | Earnings-22 是否有足量的 speaker-exclusive 专业实体供给？ | 已判读 | 机械通过，但 70.2% 来自 `CONTRACTION/FALLBACK`，专业代理未确认 | 如继续，在未读 45 场 reserve 上预注册窄类确认审计 |
| [E4-XDOMAIN-SUPPLY-AUDIT-v3](E4-XDOMAIN-SUPPLY-AUDIT-V3.md) | 未读 Earnings-22 reserve 是否有足量缩写/字母数字 carry？ | 已判读 | `EARNINGS22-NARROW-SUPPLY-FEASIBLE`；30/45场 eligible，264个 narrow exclusive carry | 决策音频许可与最小 acquisition；模型 pilot 仍需独立注册 |
| [E4-XDOMAIN-AUDIO-ADMISSION](E4-XDOMAIN-AUDIO-ADMISSION.md) | Earnings-22 音频是否完整且兼容固定前端？ | 已判读 | 音频125/125哈希与解码通过；CSV 时长门失败，且116/125场超过固定前端4-speaker上限 | 后续全库 Sortformer 已补做，主讲子群条件可用 |
| [EARNINGS22-SORTFORMER](EARNINGS22-SORTFORMER.md) | >4人电话会中，固定4-speaker前端能否保住1–2位主讲？ | 已判读 | 主讲占主导30场：Top-1错误14.30%、Top-2错误22.59%，`MAIN-SPEAKER-DIARIZATION-USABLE`；长尾错误72.75% | 后续无gold门已失败，不能运行时识别该子群 |
| [EARNINGS22-RUNTIME-DOMINANT-GATE](EARNINGS22-RUNTIME-DOMINANT-GATE.md) | 不看gold能否用整会占比和跨窗稳定性识别主讲可用会议？ | 已判读 | `RUNTIME-DOMINANT-GATE-UNSAFE`；precision 38.60%，29/57放行会议Top-2错误>40% | 不搜索同库阈值；另行设计稳定错误供给审计 |
| [Z-SERIES](Z-SERIES.md) | 说话人标签、归属与切分的多臂效应是什么？ | 已判读 | G1 floors 已归档；主要差异来自转向表/归属输出，纯切片差异不显著 | 作为描述性基线，不重跑、不据此选择分支 |

## 当前优先级

1. 以[今日进展总结](../2026-08-21-progress-summary.md)作为机制审计汇报入口；不得将其改写为独立确认结果。
2. `E4-DISJOINT-PREV` 支持约50%的 prevalence 规划假设，但没有提供转写效果证据。
3. `E4-DISJOINT-DIR` 已完成172-cell判读；安全门失败，完整31,749-call flight 与 agent loop 均不放行。
4. `E4-SAFETY-GATE-AUDIT` 未找到兼具覆盖、安全和收益的简单运行时门；停止在当前结果上继续阈值搜索。
5. `E4-XDOMAIN-SUPPLY-AUDIT` 只放行 Academic 的供给可行性判断；Product 严格技术供给不足，不能启动平衡跨域模型 pilot。
6. `E4-XDOMAIN-SUPPLY-AUDIT-v2` 证明广义标签复现充足，但未确认专业实体供给；45 场 reserve 仍未读，音频与模型接触未授权。
7. `E4-XDOMAIN-SUPPLY-AUDIT-v3` 已在未读 reserve 确认窄类供给，但没有放行模型实验。
8. Earnings-22 全库 Sortformer 表明参考已知的主讲占主导子群可保住Top-1/Top-2，但后续无gold运行时门失败，不能据此筛选模型 pilot。
9. G1/Z 系列已有正式仓库证据；引用时必须保留“描述性 floors、非分支 verdict”和域内 diarizer 限制。
10. RTTM 占比与跨窗稳定性门不安全；固定4路输出可能稳定合并长尾，不能据此选择 Omni pilot。
