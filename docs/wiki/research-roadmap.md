# 研究路线图：说话人条件专业转写

研究对象是固定 diarizer、切片器、预处理和模型后的短语音片段转写。优化变量只包括 prompt、会议内/说话人内文本状态、工具脚本和 controller policy。

| 阶段 | 目的 | 状态 | 放行条件 |
|---|---|---|---|
| E0 | 语料与实体密度审计 | 已判读 | 明确 ContextASR 与 Earnings21 的不同用途 |
| E1 | 固定无状态基线 | 已判读 | bare 基线已嵌入 C-CTX、E4 和 E4-CF，并由冻结配置/回执锁定 |
| E2 / C-CTX | 正确/错误实体条件能力 | 已判读 | 当前未达到“可达”门，需机制拆解 |
| E3 | 说话人历史状态 | 已判读 | `LEGAL-STATE-READY`；可进入固定第二遍 |
| E4 | 固定第二遍与 speaker/global 消融 | 已判读 | 上下文敏感但 speaker-specific 未达门；需独立确认 |
| E4-CF | 未见对话独立确认 | 已判读 | `DIRECTIONAL-NOT-CONFIRMED`：+2.16 pp，低于 5 pp 实用效应门 |
| E4-CF-MECH | 冻结结果机制审计 | 已判读 | 只保留 `speaker_wrong_disjoint` 固定策略假设；下一步先做零模型功效审计 |
| E4-DISJOINT-POWER | 固定策略功效与 roster 审计 | 已判读 | `INSUFFICIENT-CARRY-SUPPLY`：eligible carry 4,782，主情景需 5,774；不放行 flight |
| E4-DISJOINT-PREV | 资源受限 Pass-0 prevalence 筛查 | 已判读 | `PREVALENCE-SCREEN-PASS`：52.76%，但不含任何效果对照 |
| E4-DISJOINT-DIR | speaker 对 global 的低资源方向 pilot | 已判读 | `EXPLORATORY-HARMFUL`：carry方向小幅改善，但 false-hint +3.49 pp 超过安全门 |
| E4-SAFETY-GATE-AUDIT | 简单运行时拒绝门与内部扩展性 | 已判读 | `NO-SAFE-GATE`：有覆盖的 width≤2 门同时消除全部 carry 增益；跨领域不可识别 |
| E4-XDOMAIN-SUPPLY-AUDIT | Product/AMI 与 Academic/ICSI 的跨域供给 | 已判读 | `DOMAIN-LIMITED-SUPPLY`：Academic 通过；Product 严格技术 carry 3 < 10 |
| E4-XDOMAIN-SUPPLY-AUDIT-v2 | Earnings-22 新 business surface 的显式实体供给 | 已判读 | 广义标签机械通过；专业代理被 `CONTRACTION/FALLBACK` 污染，需在未读 reserve 上窄类确认 |
| E4-XDOMAIN-SUPPLY-AUDIT-v3 | Earnings-22 未读 reserve 的缩写/字母数字供给 | 已判读 | `EARNINGS22-NARROW-SUPPLY-FEASIBLE`：30/45场 eligible、264个 narrow exclusive carry |
| E4-XDOMAIN-AUDIO-ADMISSION | Earnings-22 音频完整性与固定前端兼容性 | 已判读 | 音频125/125完整；CSV 时长门失败，且116/125场超过4-speaker前端上限；不放行模型 pilot |
| EARNINGS22-SORTFORMER | 超过4人的电话会是否仍能保住主要主讲 | 已判读 | 30场主讲占主导目标组Top-1/Top-2错误14.30%/22.59%，条件可用；长尾72.75%不可用 |
| E-LOOP-STABILITY-SUPPLY | 跨窗滑动记忆是否有足量测量供给 | 已判读 | `LOOP-STABILITY-SUPPLY-READY`；4/4场、554个同speaker跨窗carry turn |
| E-LOOP-STABILITY | 新信息驱动的有界上下文重组是否稳定且不劣 | 已判读 | `LOOP-STABILITY-NOT-REACHED`：一致性上升，但错配分离、收敛与安全门失败 |
| E5 | Training-free GRPO/GEPA/多模态知识注入 | 未放行 | 只有E-LOOP-STABILITY通过后才搜索整体效用增益 |
| E6 | 多会议确认与最差 speaker 检验 | 未放行 | E5 尚未放行；启动前需预注册样本量、MDE、CI 和多重检验 |

稳定与优化必须分开：首次完整验证进一步表明，提高字符串一致性不等于达到安全不动点。
广播式recent-tail和长摘要导致输出膨胀、复述、非收敛与WER伤害，已被淘汰。下一候选只能是
稀疏、按chunk检索的少量候选上下文；在其通过之前，第二阶段效用搜索仍不得启动。

形式化定义、Lean 风格定理和逐步实现接口见[完整研究计划](../plans/2026-08-20-speaker-conditioned-transcription-optimization.md)。

## 2026-08-22 最近检查点

Earnings-22 窄类 reserve、音频 acquisition 和全库 Sortformer 均已完成。125场工具运行零失败；在预注册的30场“>4人但Top-2发言占比≥60%”目标组，主要主讲归属通过精度门，但长尾错误72.75%。因此不再简单按总人数否决该语料，下一检查点改为无gold dominant-cluster eligibility 门；通过后才讨论只面向主要主讲的小型模型 pilot。E5 继续不放行。详见[阶段性结论](stage-conclusions.md)和[实验总表](experiments/README.md)。
