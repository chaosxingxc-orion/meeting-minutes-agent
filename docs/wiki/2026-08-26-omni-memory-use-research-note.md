# Omni memory use：第一轮调研与设计推论

日期：2026-08-26。状态：方向性调研。本文记录 proposal 形成后的第一轮文献综合与本仓库可行性
检查；不是完整 systematic review、实验预注册或模型调用授权。

## 一句话结论

最值得研究的不是“把 audio embedding 接到 text RAG 上”，而是让 meeting agent 将 memory 当成
**多模态证据系统**：先声明当前纪要条目缺哪类证据，再选择文本、声音或二者，必要时扩大时间范围或
回听，最后只把有来源支持的 claim 写入 ledger。

## 文献矩阵

| 工作 | memory/输入形态 | 检索或规划 | memory 如何被使用 | 对本项目的启示与缺口 |
|---|---|---|---|---|
| [PlanRAG-Audio](https://arxiv.org/abs/2605.20414) | transcript、speaker、emotion、sound event 等结构化流 | planner 选择模态、步骤和时间跨度 | 聚合检索证据后回答长音频问题 | 最接近 agentic use；尚未专门约束 meeting decisions/actions 和纪要证据合同 |
| [SpeechRAG](https://arxiv.org/abs/2412.16500) | text query、audio passage | speech/text 对齐的直接语音检索 | speech LM 直接消费检索到的 audio | 证明高 WER 时绕过 ASR 可能有益；包含训练过的 adapter，不可直接当作 training-free 方法 |
| [WavRAG](https://arxiv.org/abs/2502.14727) | 统一 text-audio knowledge base | native audio/text hybrid retriever | spoken dialogue model 消费混合证据 | 支持跨模态寻址；重点仍是 QA/RAG，不是结构化 minutes |
| [AudioToolAgent](https://arxiv.org/abs/2510.02995) | 多个 audio-language tools | 中心 agent 选工具、追问、比较结果 | 多步核验后回答 | 说明 training-free tool orchestration 可行；其多模型中心 agent 与本仓库 single-core 约束不同 |
| [Speech vs. Transcript](https://aclanthology.org/2024.acl-long.790/) | 人类听 audio 或读 transcript | 无 retrieval | 直接写 speech summary | audio 影响 factuality 与 salience，不只是 ASR；是研究 audio use 的直接动机 |
| [Speaker/discourse speech summarization](https://aclanthology.org/N06-1047/) | transcript + speaker activity/turn-taking/discourse cue | 特征级选择 | 选择 summary-worthy content | 历史证据已表明纯文本不是充分统计量；现代 Omni 应重新测这些线索是否可被原生消费 |
| [Action item detection](https://aclanthology.org/W06-1314/) | meeting audio 的 lexical/temporal/syntactic/semantic/prosodic features | 局部 utterance 检测 | 识别 action-related utterance | action item 是适合观察 audio 条件增益的结构化目标 |
| [Action subdialogue](https://aclanthology.org/2007.sigdial-1.4/) | 多轮 meeting dialogue | 利用 local dialogue structure | 从提出、讨论、同意、承诺中抽取 action | memory unit 应是可扩展 episode，而不是孤立句子 |
| [MISP-Meeting](https://aclanthology.org/2025.acl-long.753/) | 长会议的 audio、video、text | 多模态前端与长程摘要 | 联合转写和摘要 | 真实会议确有多模态增益；未隔离 raw audio memory 的 use policy |
| [Multi-source meeting summarization](https://aclanthology.org/2024.emnlp-industry.69/) | transcript + slides 等材料 | 先找缺上下文 span，再补材料 | enrichment 后生成摘要 | 支持“先诊断 evidence need，再补证据，再生成”的分阶段控制流 |

## 三个关键设计推论

### 1. Omni 的最小科学问题是“条件增益”，不是“总分变高”

声音不应被预期对所有纪要条目平均有效。其独特价值应该集中在可事先定义的 strata：

- transcript disagreement 或低置信的词面；
- speaker/owner 连续性；
- proposal→discussion→commitment 的局部对话；
- agreement、rejection、defer 和 uncertainty；
- 重叠、打断、停顿、强调与群体 response 所关联的 salience。

因此主分析应是 `modality × evidence-need type` 的交互，而不是只报告一个总体 ROUGE/WER。若
paired 只在 text-sufficient 类别上提高，而在 audio-sensitive 类别不提高，说明增益很可能来自重复
context 或 second pass，不是 omni use。

### 2. Paired memory 不是简单拼接

文本和声音必须通过同一个 `item_id/start_ms/end_ms/source_hash` 对齐。系统至少需要检测三种状态：

- **agree**：text 与 audio 支持同一 claim；
- **audio-corrects-text**：声音能复核文本错误；
- **unresolved-conflict**：无法可靠裁决，纪要降级或 abstain。

必须保留 `same-text + wrong-audio` 和 `same-audio + wrong-text` 控制。否则 paired arm 的提升无法区分
“正确跨模态对齐”与“多给了一份上下文”。

### 3. Agenticness 应落在五个动作决策上

agent 的研究对象应当是：

1. 是否需要 memory；
2. 需要 lexical、speaker、discourse、stance 还是 chronology evidence；
3. 选择 text、audio、paired 还是 abstain；
4. 是否围绕命中 span 扩大时间范围或再回听一次；
5. 证据是否足以写入 atomic minutes claim。

embedding 只影响第 2/3 步之前的 candidate reachability。若 fixed bundle 的 U1 不能证明 use，继续调
embedding 没有系统意义。

## 本仓库的可行性检查

### 已有可复用的结构

- `MinutesTaskManager` 已经提供 typed task queue，可加入 evidence-need task，不必切换到自由 ReAct。
- episode state、speaker map、append-only ledger 和 receipt 方向与 provenance-aware memory 一致。
- raw audio 由外部 handle 持有、session 只传小型状态的既有设计适合 waveform memory。
- 当前失败实验已经证明必须保存逐 turn trace、候选身份、deranged control 和 one-shot reader。

### 当前明确缺口

- `LlamaServerTransport` 每次只允许一个 audio part，且 audio 必须是单个有界 slice；现阶段不能假设
  一次请求同时放当前 audio 与多个 memory audio。
- minutes head 目前主要消费 accumulated text，并以单个最后 chunk audio 作 grounding；尚无
  `EvidenceNeed/EvidencePacket/MemoryActionTrace` 合同。
- 已有 material trace 面向 official-text candidate，不等于 raw audio memory trace。
- decision/action 的 primary opportunity census 尚未建立，不能直接从已有 dispatch 数推导功效。

### v1 可行路径

把 U1 放在 Pass0 后：working transcript 和 typed evidence need 作为文本，唯一 audio slot 放一段
memory audio；paired arm 同时放该 audio 的冻结 Pass0 text。这样不改 multi-audio transport，也能
直接测试主模型如何使用 text/audio memory。若 agent 需要多个 clip，则每次 `replay` 一个并写回
带来源的 evidence card；禁止为了方便把多段 clip 无记录拼接。

candidate bundle 也必须由 Pass0 text、预测 speaker、时间邻接等 runtime-visible signal 前瞻构造。
gold decision/action 或 reference transcript 只能在 bundle、请求和回复全部冻结后由 reader 使用；
否则“正确 audio memory”本身就泄漏了答案位置，U1 测到的不是部署能力。

## 建议的研究优先级

1. **Action/decision commitment**：最能同时利用长程、speaker、dialogue structure 和声音线索；
   输出 slot 化，容易做严格 reader。
2. **Speaker/owner attribution**：声音有清晰的理论增量，且能构造 wrong-speaker audio 控制。
3. **Decision state/uncertainty**：潜在 novelty 高，但需先验证 annotation 一致性。
4. **Entity/number replay**：容易落地，适合作为低层机制 probe，但故事不应退化为 WER 修补。
5. **Overall summary salience**：最后做，因为 metric 容易遮蔽 meeting-specific failure。

## 下一轮调研问题

- AMI/ICSI 哪些 annotations 能在不向 runtime 泄漏 gold 的前提下定义 action/decision reader？
- Qwen3-Omni 在单请求中对多 audio part 的真实支持和顺序敏感性如何？在回答前不得仅根据模型报告
  推断本仓库 llama.cpp 路径具备该能力。
- raw audio memory 的 null control 应使用 silence 还是声学匹配 noise，怎样避免它本身改变输出？
- same-speaker wrong-topic 与 wrong-speaker same-topic 哪一种 derangement 更能分离 voice 与 content？
- planner 何时只返回 handle，何时生成 evidence card；后者是否会形成新的文本 bottleneck？
- 最终 minutes claim 的人类可回放证据 UI 是否属于研究评测的一部分，还是仅保留 manifest link？

对应的完整 proposal 见
[OmniMinutes proposal](../plans/2026-08-26-omni-agentic-memory-use-proposal.md)。
