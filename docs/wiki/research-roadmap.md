# 研究路线图：从说话人条件转写到 OmniMinutes

下表E线记录固定 diarizer、切片器、预处理和模型后的短语音片段转写证据；其优化变量只包括
prompt、会议内/说话人内文本状态、工具脚本和 controller policy。2026-08-26起，E线作为perception
与safety基础保留，总体研究对象上移到下文U线的training-free OmniMinutes agentic memory system。

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
| E-MEETING-MATERIAL-SUPPLY-AUDIT | 会议同期官方材料能否形成安全、可追溯的逐chunk候选供给 | 已判读 | `MEETING-MATERIAL-SUPPLY-INSUFFICIENT`：49个候选有完整出处，但正确触发3/418、召回3/30；不放行Omni |
| E-MEETING-MATERIAL-SEMANTIC-SIGNAL | SAEA式encode-only语义K能否形成分布式材料归属信号 | 已判读 | `SEMANTIC-RETRIEVAL-SIGNAL-PRESENT`：77.86%，较词法+15.997点，3/3场过门；放行独立能力实验设计 |
| E-MATERIAL-SEMANTIC-ADMISSION | Earnings-22能否建立6场reference-unread开发/确认队列 | 已判读 | `ADMISSION_FAILED_NO_REFERENCE_UNREAD_MEETINGS`：v2/v3合计覆盖125/125，剩余0场 |
| E-MATERIAL-RUNTIME-GATE | 本会议语义top1/top2门能否跨开发/确认稳定 | 依赖门失败，未运行 | 严格独立队列不存在；未拟合阈值、未读Pass0、未调用模型 |
| E-MATERIAL-RUNTIME-GATE-CI | 构造隔离的六场复用能否形成语义top1/top2门 | 已判读 | `CONSTRUCTION_ISOLATED_SIGNAL_PRESENT`：阈值0.01；确认precision 76.10%、覆盖74.82%，四门全过；只放行另行注册的探索性Omni设计 |
| E-MATERIAL-OMNI-CAPABILITY-CI | 构造隔离语义门能否直接转成三臂Omni能力flight | 未放行 | `NOT_RUN_MISSING_FROZEN_FLIGHT_INPUTS`：636个聚合dispatch不足以恢复逐turn runtime；缺trace与primary opportunity census |
| E-MATERIAL-NEW-SURFACE-ADMISSION | EarningsCallVoice短片段能否与FinCall同场slide闭合独立能力surface | 已判读 | `NEW_SURFACE_COHORT_FROZEN`：69条全部闭合双音频、九项人工门与同场PDF；冻结20/40/9队列，下一步另行注册开发集Pass0与完整trace |
| E-MATERIAL-NEW-SURFACE-PASS0 | 新surface开发集能否建立reference-blind可重放基线 | 已判读 | `PASS0_TRACE_COMPLETE`：40/40成功、0空输出、0重试；reference未读 |
| E-MATERIAL-NEW-SURFACE-RUNTIME-GATE | 正确call材料能否相对错配call形成语义dispatch信号 | 开发集已判读 | 归属precision 75%、中位优势0.07609；开发门通过但冻结阈值0.00无拒绝作用 |
| E-MATERIAL-NEW-SURFACE-CONFIRMATION | 开发材料归属信号能否在40个sealed item确认 | 未放行 | Pass0 80/80完成；一场PDF抽取0候选<8，按无替换规则停止于0 embedding，尚无独立确认 |
| E-MATERIAL-LHCP-SLICER-OVERLAP-FIX | 冻结LHCP开发RTTM能否生成零重复transport供给 | 已判读 | `SLICER_OVERLAP_FIX_PASSED`：25场396片、0重叠、最大120秒；只放行另立Pass0注册 |
| E-MATERIAL-LHCP-DEVELOPMENT-PASS0 | 修复后开发切片能否形成reference-blind exact-wire基线 | 已判读 | `PASS0_TRACE_COMPLETE`：396/396、0空输出、0重试；1片潜在截断 |
| E-MATERIAL-LHCP-DEVELOPMENT-QUERY-SUPPLY | 同期材料与Pass0能否形成严格因果的逐片检索供给 | 已判读 | `QUERY_SUPPLY_READY`：25场×8个key、396条query、371条有严格前一片关键词；错配0固定点 |
| E-MATERIAL-LHCP-DEVELOPMENT-SEMANTIC-GATE | 正确会议材料能否稳定胜过固定错配会议 | 开发集已判读 | `SEMANTIC_SIGNAL_PRESENT`：359/396、90.66%、中位优势0.11701；两场低于70% |
| E-MATERIAL-LHCP-DEVELOPMENT-OPPORTUNITY-POWER-AUDIT | 冻结材料top1是否有足量纠错机会与功效 | 已判读 | `OPPORTUNITY_INSUFFICIENT`：12机会/8场/17.17%局部支持；不启动三臂Omni，改做可拒绝的局部实体提议设计 |
| E-MATERIAL-LHCP-LOCAL-CANDIDATE-CEILING | 完整8候选能否提供足量局部纠错oracle上限 | 已判读 | `POOL_INSUFFICIENT`：39机会片/14场，top1只捕获30.77%；停止8-key router调参，转向原始候选池上限 |
| E-MATERIAL-LHCP-FULL-POOL-CEILING | 原始材料候选源能否提供足量局部纠错oracle上限 | 已判读 | `FULL_POOL_POWER_READY`：206机会片/25场；材料源充足，下一步测试reference-blind BM25/top-k抽取 |
| E-MATERIAL-LHCP-BM25-LOCAL-EXTRACTOR | reference-blind词法抽取能否保留全池机会供给 | 已判读 | top-8仅44/47机会片，prior增益3片；BM25失败，转向全池semantic readiness |
| E-MATERIAL-LHCP-FULL-POOL-SEMANTIC-EXTRACTOR | 全池语义抽取能否保留足量局部机会 | 已判读 | `EXPLORATORY_ONLY`：top-8 53/206、23场，较BM25 +6；不放行Omni/confirmation |
| E5 | Training-free GRPO/GEPA/多模态知识注入 | 未放行 | 只有E-LOOP-STABILITY通过后才搜索整体效用增益 |
| E6 | 多会议确认与最差 speaker 检验 | 未放行 | E5 尚未放行；启动前需预注册样本量、MDE、CI 和多重检验 |

稳定与优化必须分开：首次完整验证进一步表明，提高字符串一致性不等于达到安全不动点。
广播式recent-tail和长摘要导致输出膨胀、复述、非收敛与WER伤害，已被淘汰。下一候选只能是
稀疏、按chunk检索的少量候选上下文；在其通过之前，第二阶段效用搜索仍不得启动。

形式化定义、Lean 风格定理和逐步实现接口见[完整研究计划](../plans/2026-08-20-speaker-conditioned-transcription-optimization.md)。

## 2026-08-26 Omni-agentic 新主线

研究对象从“冻结Omni下的speaker-conditioned transcription与embedding供给”上移为
**training-free omni agentic system with native audio-text memory**。现有E线继续作为perception、
稳定性和safety evidence，不被删除或改写；新U线首先隔离memory的使用能力：

| 阶段 | 目的 | 当前状态 | 放行条件 |
|---|---|---|---|
| U0 | meeting decision/action/speaker的raw-audio memory机会审计 | 设计中 | 非gold runtime signal、跨会议支持、trace与reader均可前瞻冻结 |
| U1 | 固定bundle下比较no-memory/text/audio/paired/deranged | 未开始 | paired相对text和deranged-audio均有条件增益，且安全门不过线 |
| U2 | agent选择text/audio/paired/re-listen | 未开始 | 质量接近always-paired，成本更低，且优于简单rule router或明确收缩结论 |
| U3 | 接入decision/action ledger与完整纪要 | 未开始 | factuality、evidence support、worst-meeting/speaker和成本联合通过 |
| U4 | 收集、压缩、检索与embedding联合优化 | 未放行 | U1证明memory可被正确消费，U2/U3给出稳定use policy |

完整定义、反事实控制和研究问题见
[OmniMinutes memory-use proposal](../plans/2026-08-26-omni-agentic-memory-use-proposal.md)。U线尚未
构成任何模型调用授权；`E-MATERIAL-OMNI-CAPABILITY-CI`的不运行判决继续有效。

## 2026-08-22 最近检查点

Earnings-22 窄类 reserve、音频 acquisition 和全库 Sortformer 均已完成。125场工具运行零失败；在预注册的30场“>4人但Top-2发言占比≥60%”目标组，主要主讲归属通过精度门，但长尾错误72.75%。因此不再简单按总人数否决该语料，下一检查点改为无gold dominant-cluster eligibility 门；通过后才讨论只面向主要主讲的小型模型 pilot。E5 继续不放行。详见[阶段性结论](stage-conclusions.md)和[实验总表](experiments/README.md)。
