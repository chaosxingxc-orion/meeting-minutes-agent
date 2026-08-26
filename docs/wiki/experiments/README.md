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
| [E-STABLE-ERROR-SUPPLY](E-STABLE-ERROR-SUPPLY.md) | 整会内是否有重复、稳定转错且具合法锚点的专业术语簇？ | 已判读 | 13个strict稳定错误但锚点0；且9/13为分隔符变体，`STABLE-ERROR-SUPPLY-PRESENT-ANCHOR-LIMITED` | 不运行term Pass1；考虑独立锚点或整会语言漂移实验 |
| [E-LOOP-STABILITY-SUPPLY](E-LOOP-STABILITY-SUPPLY.md) | 既有整会Pass0是否有足量跨窗口复现，可支撑有界滑动记忆实验？ | 已判读 | `LOOP-STABILITY-SUPPLY-READY`；4/4场、554个同speaker跨窗carry turn | 注册稳定性模型多臂；仍不放行GRPO或term纠错 |
| [E-LOOP-STABILITY](E-LOOP-STABILITY.md) | 新增信息驱动的滑动上下文重组能否稳定、可复现且不劣？ | 已判读 | `LOOP-STABILITY-NOT-REACHED`；一致性+11.42点，但不收敛且WER+19.28点 | 禁止GRPO；另行注册稀疏per-chunk检索设计 |
| [E-CHUNK-RETRIEVAL-SUPPLY](E-CHUNK-RETRIEVAL-SUPPLY.md) | 稀疏per-chunk候选是否充足且错配负对照可分？ | v3已判读 | `SUPPLY-READY`：1056个eligible turn，正确/错配100%可分且等候选数 | 注册四臂模型实验与R2第二轮 |
| [E-CHUNK-RETRIEVAL](E-CHUNK-RETRIEVAL.md) | 稀疏speaker路由候选能否形成稳定、收敛且不劣的agent loop？ | 已判读 | `NOT-REACHED`：虽收敛，但一致性-6.42点、路由1/4、错误激活54.98% | 先审计leave-one-chunk-out独立证据；不放行策略搜索 |
| [E-CHUNK-RETRIEVAL-LOO-SUPPLY](E-CHUNK-RETRIEVAL-LOO-SUPPLY.md) | 排除当前chunk后，其他同speaker chunk能否提供新且准确的纠错候选？ | 已判读 | `SUPPLY-INSUFFICIENT`：覆盖980 turns，但精度1.93%、正确供给仅53 turns | 停止output-only模糊检索；新分支须先指定独立外部证据 |
| [E-EXTERNAL-COMPANY-IDENTITY-SUPPLY](E-EXTERNAL-COMPANY-IDENTITY-SUPPLY.md) | ticker→公司品牌名能否提供准确、独立的短片段纠错候选？ | 已判读 | `SUPPLY-INSUFFICIENT`：仅15个纠错机会；触发precision 62.5%、recall 33.3% | 停止单一公司身份分支；寻找与会议同时可得的丰富材料 |
| [E-MEETING-MATERIAL-SUPPLY-AUDIT](E-MEETING-MATERIAL-SUPPLY-AUDIT.md) | 会议同期官方材料能否提供丰富、准确且带出处的逐chunk纠错候选？ | 已判读 | `MEETING-MATERIAL-SUPPLY-INSUFFICIENT`：30个机会仅触发3个正确项，precision 0.72%、recall 10%；短缩写造成大量误触发 | 不在已读结果上调参；独立会议另行注册分层router审计 |
| [E-MEETING-MATERIAL-RETRIEVAL-SIGNAL](E-MEETING-MATERIAL-RETRIEVAL-SIGNAL.md) | SAEA式Q-K-V能否让本会议材料稳定胜过等宽错配材料？ | 已判读 | `RETRIEVAL-SIGNAL-INSUFFICIENT`：覆盖97.07%，但归属precision 61.87%；仅Galp 77.12%，其余两场低于50% | 不放行Omni；准备encode-only语义K独立对照 |
| [E-MEETING-MATERIAL-SEMANTIC-SIGNAL](E-MEETING-MATERIAL-SEMANTIC-SIGNAL.md) | encode-only语义K能否跨场稳定优于词法K？ | 已判读 | `SEMANTIC-RETRIEVAL-SIGNAL-PRESENT`：precision 77.86%，较词法+15.997点，3/3场过逐会门 | 独立未读会议注册retain/correct/deranged三臂Omni能力实验 |
| [E-MATERIAL-SEMANTIC-ADMISSION](E-MATERIAL-SEMANTIC-ADMISSION.md) | Earnings-22是否仍有6场reference-unread会议可建立独立开发/确认队列？ | 已判读 | `ADMISSION_FAILED_NO_REFERENCE_UNREAD_MEETINGS`：v2读80场、v3读45场，互斥并集覆盖125/125，剩余0场 | 新会议/外部测试集；不得把outcome-unread冒充reference-unread |
| [E-MATERIAL-RUNTIME-GATE](E-MATERIAL-RUNTIME-GATE.md) | 本会议语义top1/top2差值能否形成可部署dispatch门？ | 依赖门失败，未运行 | `NOT_RUN_PREREQUISITE_FAILED`：无法冻结3场开发+3场确认；零Pass0、零embedding、零Omni | 等待新独立会议，或另行注册较弱construction-isolated设计 |
| [E-MATERIAL-RUNTIME-GATE-CI](E-MATERIAL-RUNTIME-GATE-CI.md) | 历史参考已暴露时，严格隔离当前构造能否复现语义dispatch信号？ | 已判读 | `CONSTRUCTION_ISOLATED_SIGNAL_PRESENT`：阈值0.01；确认precision 76.10%、覆盖74.82%、中位余弦优势0.06154，四门全过 | 可另行注册探索性三臂Omni能力实验；不得宣称独立确认或WER增益 |
| [E-MATERIAL-OMNI-CAPABILITY-CI](E-MATERIAL-OMNI-CAPABILITY-CI.md) | 现有冻结产物能否直接注册retain/correct/deranged三臂Omni flight？ | 未放行 | `NOT_RUN_MISSING_FROZEN_FLIGHT_INPUTS`：有636个聚合dispatch，但缺逐turn trace与primary opportunity census；无法冻结1,272-call runtime或reader | 新surface前瞻持久化trace，或另行注册并授权trace-materialization读取 |
| [E-MATERIAL-NEW-SURFACE-ADMISSION](E-MATERIAL-NEW-SURFACE-ADMISSION.md) | 新短片段surface能否闭合音频、精确参考、同场slide与完整trace？ | 已判读 | `NEW_SURFACE_COHORT_FROZEN`：69/69通过，冻结20开发、40一次确认、9保留；138 WAV与69 PDF均绑定哈希 | 另行注册开发集Pass0与完整trace；模型接触需明确授权 |
| [E-MATERIAL-NEW-SURFACE-PASS0](E-MATERIAL-NEW-SURFACE-PASS0.md) | 新surface开发集能否完成reference-blind Pass0并保存精确wire trace？ | 已判读 | `PASS0_TRACE_COMPLETE`：40/40成功、0空输出、0重试、13,797 total tokens；reference未读 | 冻结开发集PDF候选、错配映射与encode-only embedding runtime |
| [E-MATERIAL-NEW-SURFACE-RUNTIME-GATE](E-MATERIAL-NEW-SURFACE-RUNTIME-GATE.md) | 新surface正确call材料能否相对错配call形成可部署语义gap？ | 开发集已判读 | `DEVELOPMENT_SIGNAL_PRESENT`：归属30/40、precision 75%、中位优势0.07609；最低过门阈值0.00全量dispatch | 决策是否另行放行40场sealed confirmation；仍未证明拒绝门或WER收益 |
| [E-MATERIAL-NEW-SURFACE-CONFIRMATION](E-MATERIAL-NEW-SURFACE-CONFIRMATION.md) | 开发集材料归属信号能否在40个sealed item上确认？ | 未放行 | Pass0 80/80完成；`ECV-0067`材料抽取0候选<8，判`CONFIRMATION_NOT_RUN_MATERIAL_SNAPSHOT_INSUFFICIENT` | 不运行embedding；OCR/替换/降宽须另立研究分支，不能修补本确认 |
| [E-MATERIAL-INDEPENDENT-SURFACE-SCOUT](E-MATERIAL-INDEPENDENT-SURFACE-SCOUT.md) | 是否存在reference-unread、带人工逐字参考和同期材料的新surface？ | 已判读 | 首选`LHCP-ASR`：72场、25开发/47确认；检索时为`JOIN_PENDING`，后续准入已闭合 | 见`E-MATERIAL-LHCP-ADMISSION` |
| [E-MATERIAL-LHCP-ADMISSION](E-MATERIAL-LHCP-ADMISSION.md) | 72场LHCP-ASR能否与CERN contribution一一对齐且逐场有同期材料？ | 已判读 | `JOIN_AND_COVERAGE_CLOSED`：72/72唯一对齐、0孤儿/歧义，72/72有材料，77/77端点可达 | 另行注册材料可读性与零模型候选供给审计 |
| [E-MATERIAL-LHCP-SUPPLY](E-MATERIAL-LHCP-SUPPLY.md) | 72场官方材料是否均可读且逐场有至少8个候选？ | 已判读 | `SUPPLY_INSUFFICIENT`：70/72通过；开发25/25、确认45/47，2份test_2020 PDF触发解析器硬限 | 已另行冻结70场eligible cohort；原72/72失败判决保持不变 |
| [E-MATERIAL-LHCP-ELIGIBLE-COHORT](E-MATERIAL-LHCP-ELIGIBLE-COHORT.md) | 能否按模型前材料兼容性冻结25开发+45确认队列？ | 已判读 | `LHCP_70_TALK_ELIGIBLE_COHORT_FROZEN`：25开发+45确认；固定排除2项，`TRACE_COMPLETE` | 另行注册开发集模型实验；确认集继续sealed |
| [E-MATERIAL-LHCP-DEVELOPMENT-AUDIO](E-MATERIAL-LHCP-DEVELOPMENT-AUDIO.md) | 能否只获取25场开发音频并得到真实时长预算？ | 已判读 | `LHCP_DEVELOPMENT_AUDIO_ACQUIRED`：25/25、10.43小时，`TRACE_COMPLETE`；reference/confirmation/模型为0 | 另立固定Sortformer与切片供给审计 |
| [E-MATERIAL-LHCP-DEVELOPMENT-FRONTEND](E-MATERIAL-LHCP-DEVELOPMENT-FRONTEND.md) | 25场开发音频能否生成完整的固定说话人切片供给？ | 已判读 | 25/25 Sortformer成功、397片哈希闭合，但15个相邻边界在10场中重叠，判`FRONTEND_SLICE_ZERO_OVERLAP_GATE_FAILED` | 不放行Pass0；另行注册切片器重叠边界修复，不重跑Sortformer |
| [E-MATERIAL-LHCP-SLICER-OVERLAP-FIX](E-MATERIAL-LHCP-SLICER-OVERLAP-FIX.md) | 冻结RTTM能否在不重跑Sortformer时生成零重叠切片？ | 已判读 | `SLICER_OVERLAP_FIX_PASSED`：25/25场、396片、0重叠、最大120秒；普通turn内部切点0 | 另行注册396-call开发Pass0；模型仍未授权 |
| [Z-SERIES](Z-SERIES.md) | 说话人标签、归属与切分的多臂效应是什么？ | 已判读 | G1 floors 已归档；主要差异来自转向表/归属输出，纯切片差异不显著 | 作为描述性基线，不重跑、不据此选择分支 |

## 当前优先级

1. `E-CHUNK-RETRIEVAL` 已判失败：虽收敛，但一致性下降6.42点、路由仅1/4场、错误激活54.98%；禁止据此启动策略搜索。
2. leave-one-chunk-out独立证据审计也失败：字符串模糊候选精度仅1.93%；停止output-only检索分支，不得调阈值。
3. `E-LOOP-STABILITY` 已淘汰recent-tail与广播式长摘要；`E-CHUNK-RETRIEVAL` 又淘汰同chunk自回灌，二者失败机制不同。
4. `LHCP-ASR`的72场join已闭合，原72/72材料门仍失败；现已前瞻冻结70场material-compatible子群（25开发+45确认）。该冻结不授权模型flight，也不能外推到完整72场。
5. `E4-SAFETY-GATE-AUDIT` 未找到兼具覆盖、安全和收益的简单运行时门；停止在原结果上继续阈值搜索。
6. Earnings-22窄类供给和完整音频均已确认，但供给存在不等于模型收益；固定4路前端也没有安全的无gold主讲筛选门。
7. G1/Z 系列只作为描述性floors引用，不重跑、不据此选择当前分支。
