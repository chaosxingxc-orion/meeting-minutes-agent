# OmniMinutes proposal：training-free omni agentic memory for meeting minutes

Date: 2026-08-26. Status: research proposal, owner-requested Chinese plan. This document
defines a new research direction; it is not a preregistration and does not authorize model
contact, reference reading, dataset acquisition, or changes to frozen verdicts.

## 1. 核心主张

在冻结主模型、坚持 training-free 的前提下，研究对象不应继续收缩为“寻找更好的 omni
embedding instruction”。更有研究空间、也更符合 meeting minutes 本质的对象是：

> **一个能主动判断何时需要历史证据、需要哪一种模态、需要回看哪一段，并用可追溯证据生成会议纪要的
> omni agentic system。**

暂定系统名为 **OmniMinutes**。系统拥有一个文本/声音统一寻址的 embedding 模块，但 embedding
只是 memory addressor，不是整篇研究。主要可优化对象改为 memory action policy：何时查、查什么、
使用文本还是声音、如何组合、何时二次回听、何时拒绝写入纪要，以及如何验证最终条目。

第一阶段优先研究 memory 的**使用（use）**。收集、压缩和检索暂时作为冻结供给：保留原始波形和
时间戳，不先优化摘要、audio codec、clip selection 或 embedding。这样可以先回答一个更基础的问题：
即使已经拿到正确或足够相关的 memory，omni 主模型是否会真正利用声音；如果会，在哪些 meeting
minutes 子任务上产生纯文本系统不可替代的增益。

## 2. 什么才算 omni

“同时存了 transcript 和 wav”还不等于 omni。本文将 omni 约束为四个可检验条件：

1. **原生保真**：原始声音不会被 transcript 永久替代；memory item 保留可重放的 waveform、
   speaker、时间范围和来源哈希。
2. **跨模态可寻址**：文本问题可以找到声音，声音片段也可以找到文本或声音；embedding 可参与，
   但允许 speaker、时间、结构化索引和工具查询共同寻址。
3. **按任务选择模态**：agent 不是永远把两种模态全部塞入上下文，而是依据证据需求选择
   `text / audio / paired / abstain`。
4. **跨模态裁决**：当 transcript 与声音不一致时，系统显式记录冲突并回到声音核验，而不是静默
   拼接两个结果。

纯文本 memory 保存的是“系统曾经认为说了什么”；omni memory 还能保存“当时究竟怎么说、谁说、
何时说、是否重叠、语气是否像承诺或保留意见”。后二者正是 meeting minutes 中 decision、action
owner、agreement、uncertainty 和 speaker attribution 容易丢失的部分。

| 维度 | 纯文本 memory | Omni memory |
|---|---|---|
| 内容证据 | ASR/摘要中的词与命题 | 词与命题，加原始声学证据 |
| 说话人 | diarization 标签或姓名字符串 | 标签、声音身份线索、重叠与轮次关系 |
| 立场/承诺 | 依赖 lexical cue | 可再利用重音、停顿、语调、迟疑、笑声和 backchannel |
| 错误恢复 | 只能在已有文本之间选择 | 可绕过或复核 ASR bottleneck |
| 长程使用 | top-k 文本拼接 | agent 规划模态、时间跨度和重听动作 |
| 可验证性 | 引用 transcript span | 同时引用 transcript span 与可回放 audio span |

## 3. 文献调研得到的设计约束

这是一轮方向性调研，不是完整 systematic review，但已有证据足以支持启动 use-first 设计：

- [PlanRAG-Audio](https://arxiv.org/abs/2605.20414) 将长音频拆成 transcript、speaker、emotion、
  sound-event 等可检索流，再由 planner 选择模态与时间跨度；其关键贡献是 planning，而不是把整段
  长音频直接放进模型。该思路与本 proposal 最接近，但尚未专门研究 meeting minutes 的
  decision/action/speaker 证据合同。
- [SpeechRAG](https://arxiv.org/abs/2412.16500) 和
  [WavRAG](https://arxiv.org/abs/2502.14727) 都直接检索或消费语音，针对 ASR 误差较高时报告了
  相对 cascaded text pipeline 的优势。这说明 audio value 不能在进入生成器前一律转写掉。
- [Speech vs. Transcript](https://aclanthology.org/2024.acl-long.790/) 的人类实验发现，听声音写出的
  摘要与读 transcript 写出的摘要存在系统差异，前者更具事实一致性和信息选择性。这直接支持
  “声音影响的不只是 WER，也影响 salience 和事实取舍”。
- meeting 研究很早就发现 speaker activity、turn-taking、discourse cue 可以胜过仅文本方法
  （[Murray et al., 2006](https://aclanthology.org/N06-1047/)）；action item 也不是单句分类，
  而是一个包含提出、讨论、同意和承诺的局部 subdialogue
  （[Purver et al., 2007](https://aclanthology.org/2007.sigdial-1.4/)）。因此 memory unit 不应只是一条
  ASR sentence，而应允许 agent 回看一个带前后文的声音 episode。
- [MISP-Meeting](https://aclanthology.org/2025.acl-long.753/) 进一步说明，多模态线索会显著影响真实
  长会议的转写与摘要质量；[multi-source meeting summarization](https://aclanthology.org/2024.emnlp-industry.69/)
  则证明先定位缺上下文的 transcript span、再补充外部材料、最后摘要是一条有效的分阶段路线。
- [AudioToolAgent](https://arxiv.org/abs/2510.02995) 展示了 training-free 的音频工具编排、追问与
  多结果核验是可行的邻近范式。不过 OmniMinutes v1 仍遵守本仓库的单一 frozen Omni core，
  不引入第二个中心 LLM 或训练新的模型。

当前调研所见的空档是：音频 RAG 多以通用 QA/reasoning 为中心，meeting summarization 多以完整
transcript 或外部文档为中心；“面向结构化会议纪要、以声音/文本 episodic memory 为证据、并显式
优化 agent 的 modality-use policy”仍缺少清晰的可控实验。这个判断是本轮检索后的研究假设，
后续需要扩大检索范围后才能写成 novelty claim。

## 4. 研究边界

### 4.1 本阶段固定的部分

- 主模型、diarizer、chunker、预处理和 decoding 冻结。
- memory 数据先使用同一 meeting 内已经发生的 raw audio span、冻结 Pass0 transcript 和必要的
  speaker/time metadata。
- 不先学习新的 embedding，不微调模型，不训练 compressor 或 router。
- 不使用 gold transcript、gold summary、decision/action label 构造 runtime prompt、检索 query
  或 memory bundle；它们只在 one-shot reader 中评测。
- test split 继续不触碰；train/dev 可用于 discovery，最终 test 只在完整预注册后读取。
- v1 仅做 episode-local memory。跨会议持久化仍受 2026-08-17 owner boundary 约束，需要另行决策。

### 4.2 本阶段开放的部分

- agent 的 memory action schema、工具说明、触发条件和停止条件；
- 文本、声音、paired memory 的装配顺序、剂量、来源标签和冲突声明；
- 一次生成、先检索再生成、生成后核验、按需 re-listen 等控制流；
- 规则 router、同一 frozen core 生成的结构化 plan，以及二者的 hybrid policy；
- 纪要条目的 evidence contract、abstention 和 unsupported-claim gate。

这使 training-free 优化从单一 instruction 维度扩展为一个可分解的系统空间，同时仍保持模型冻结和
可复现性。

## 5. 系统设计：memory 是 evidence plane，不是 prompt 尾巴

```text
meeting audio + shipped text
          │
          ▼
  frozen perception / Pass0
          │
          ├──────────────► episode-local raw memory
          │                 audio spans + Pass0 text + speaker/time/provenance
          ▼
  MinutesTaskManager creates a typed evidence need
  {entity, speaker, decision, action, stance, chronology, summary support}
          │
          ▼
  Memory Planner ──► query/retrieve tools ──► candidate evidence handles
          │                 text_search / audio_search / speaker_lookup /
          │                 temporal_expand / replay_clip
          ▼
  Modality Router: retain | text | audio | paired | abstain
          │
          ▼
  Evidence Packer: bounded, timestamped, equal-dose, provenance-aware input
          │
          ▼
  same frozen Omni core: draft or revise one atomic minutes claim
          │
          ▼
  Evidence Verifier: accept | re-listen | downgrade uncertainty | reject
          │
          ▼
  append-only minutes ledger + audio/text evidence links + receipts
```

### 5.1 与现有 backbone 的衔接

- `MinutesTaskManager` 继续拥有确定性的 typed task queue，不改成无约束 ReAct。
- 现有 `LISTEN → SPELL → REVISE` 保留为 perception loop；新增的是 task head 前后的
  `PLAN-MEMORY → USE → VERIFY` evidence loop。
- `state/` 中的 memory 由纯文本状态扩展为 **handle ledger**。session state 只保存小型 handle、
  metadata 和 claim；PCM 仍由 constructor-injected store 持有，避免重对象进入 workflow state。
- 所有模型接触仍经由同一个 frozen-core door。若采用 model-planned action，planning call 与
  answering call 都必须单独计费、留 receipt，并受最大步数限制。
- v1 的 agentic 不是“模型自由发挥”，而是“模型或规则在冻结的 typed action set 内选择下一步”。

### 5.2 最小 memory item 合同

```text
MemoryItem
  item_id, meeting_id, source_hash
  start_ms, end_ms, predicted_speaker_id
  audio_handle                 # raw waveform span, never embedded in Git
  pass0_text                   # frozen machine output, may be empty or wrong
  predecessor_ids, successor_ids
  provenance_tier, created_by, created_at
```

v1 不保存自动 emotion label、LLM 摘要或学习出的压缩表示，避免把“压缩质量”混进 use 实验。声音
clip 只是对 raw waveform 的有界时间视图，不做内容改写。后续 compression 研究可在同一 handle
合同下加入 text summary、audio excerpt、codec token 或 structured event，但不能替换 raw source。

### 5.3 原子 use actions

| Action | 输入 | 返回 | 主要用途 |
|---|---|---|---|
| `search_text` | typed need + text query | text handles | 命题、实体、显式承诺 |
| `search_audio` | text/audio query | audio handles | ASR 不确定、声音相似、非词汇线索 |
| `lookup_speaker` | speaker/voice handle | speaker-linked history | owner 与说话人连续性 |
| `expand_time` | handle + bounded radius | 邻接 episode | proposal→discussion→commitment |
| `replay` | audio handle | 原始 audio input | 核验 wording、数字、语气、重叠 |
| `pair` | audio/text handles | 对齐 evidence packet | 联合消费与冲突检测 |
| `abstain` | reason code | no evidence | 防止无证据纪要条目 |

embedding 只服务于 `search_text/search_audio` 的一种实现。时间邻接、speaker index、关键词、精确实体
和结构化 ledger 都可以成为同等重要的 retrieval 方法。

### 5.4 当前 transport 约束与 v1 输入形态

仓库当前 `LlamaServerTransport` 的明确合同是**每次请求最多一个 audio part**，并且这个 audio 必须是
一个有界 transport slice。因此 v1 不假设可以在一次调用中同时放入“当前 audio + 多个 memory
audio”，也不把多个 clip 静默拼接成新的波形。

U1 首先落在 Pass0 之后的 atomic decision/action head：当前任务、working transcript 和 ledger state
作为文本输入，唯一 audio slot 用于一段 memory audio；paired arm 则在同一请求中提供该 audio 的
对齐 Pass0 text。这仍然是主模型的 text+audio 输入，也能直接比较 text/audio/paired memory use。
多段 memory 需要由 agent 分次 `replay`，将每次带来源的 evidence card 写回 ledger 后再裁决；原生
multi-audio request 只有在另行完成 transport、ordering、budget 和模型能力审计后才进入实验。

## 6. Meeting minutes 中声音 memory 最可能产生独特价值的地方

### 6.1 优先级 A：decision 与 action commitment

典型会议并不会在一句话里完整表达“谁、做什么、何时做”。proposal、讨论、修订、同意和承诺往往
跨多个 turn；“sure”“right”“I can do that”也需要前文和说话方式才能判断。agent 应先检索相关
subdialogue，再根据 transcript 与原声共同写入：`action / owner / due / status / evidence`。

这是首选主任务，因为它同时要求长程 memory、speaker、对话结构和声学线索，而且输出可以结构化
评估，而不必一开始依赖单一 ROUGE。

### 6.2 优先级 B：speaker/owner 归属

文本会丢失 voice continuity；diarization 标签也可能跨 chunk 漂移。声音 memory 可以让同一 frozen
Omni core 对当前承诺与历史自我介绍/发言进行对比，但必须配 wrong-speaker audio 作为等剂量控制，
否则无法证明模型真的消费了 voice evidence。

### 6.3 优先级 C：立场、确定性与最终决议

同一词面可能是同意、勉强接受、反讽或纯 backchannel。v1 不宣称可靠识别情绪，而是先测更窄的
minutes 标签：`proposed / accepted / rejected / deferred / uncertain`。如果 audio 相对 text 没有
条件增益，这一分支就停止，不用“omni”故事强行解释。

### 6.4 优先级 D：实体、数字与专有名词复核

当当前 transcript 与历史更清晰发音或官方材料冲突时，agent 可以定向 replay。该分支与仓库现有
material retrieval 证据兼容，但不应继续把整体贡献写成 WER 优化；它只是一个可解释的低层 use case。

### 6.5 优先级 E：摘要 salience

重音、重复、speaker activity、turn-taking 和群体响应可能帮助判断哪一段值得进入纪要。不过
salience 评测较难，且容易被 summary metric 掩盖，故放在结构化 decision/action 通过之后。

## 7. Use-first 实验程序

### U0 — 零模型 opportunity census

在 AMI/ICSI 的可用 discovery meetings 上统计以下机会，不调用 Omni：跨 turn decision/action、
owner 依赖、ASR disagreement、speaker ambiguity、可能依赖声学线索的 agreement/uncertainty，以及
每项可获得的 raw audio span 和非 gold runtime signal。输出逐项 handle manifest 和只供 reader 使用的
label sidecar。若任一主类别没有足量跨会议支持，不进入模型实验。

U0 不允许先看 gold 再为 U1 挑“答案所在 clip”。candidate bundle 必须由冻结 Pass0 text、预测
speaker、时间邻接和其他部署时可见信号前瞻构造；reference/annotation 只在 bundle 与模型输出全部
冻结后由 reader 标注 opportunity type 和正确性。可以用 gold 定义分析 strata，但不能用它决定哪段
声音进入 prompt。

### U1 — 固定 evidence bundle 的 modality-use capability

先把 retrieval 完全冻结，专门测“会不会用”。每个 eligible item 使用相同当前输入和相同历史时间
范围。实验对象是 Pass0 之后的 atomic minutes claim，当前 working text 固定，单一 audio slot
承载 memory clip。比较：

- `M0-no-memory`：working text + 固定 null-audio control；
- `M1-text`：加历史 Pass0 text，audio slot 仍为等时长 null control；
- `M2-audio`：加历史 raw audio，文本位置放等字符 modality placeholder；
- `M3-paired`：加对齐的历史 text + audio；
- `M4-deranged-audio`：文本不变、audio 换成等时长 wrong-speaker/wrong-episode 控制；
- `M5-deranged-text`：audio 不变、text 换成等字符错误控制。

`M3 > M1` 只说明 audio 有增量价值；还必须同时满足 `M3 > M4`，才能说明增益依赖正确声音证据，
而不是额外 token、重复指令或 second-pass 效应。类似地，`M3 > M2` 与 `M3 > M5` 用来识别文本的
条件贡献。所有 arm 必须等 audio 秒数、等文本字符、等候选数、等顺序和等解码。null audio 的
silence/noise 选择也必须先做零模型声学统计并冻结，不能依据开发结果在两者之间切换。

### U2 — Agentic modality routing

在 U1 找到至少一个 audio-positive 子任务后，再比较固定策略与 agentic policy：

- always-text；
- always-audio；
- always-paired；
- rule router；
- frozen-core planner；
- hybrid：规则给出允许动作，模型在动作内选择并可进行一次 re-listen。

目标不是让 planner 超过所有 arm 的最高 accuracy，而是在有界成本下逼近 always-paired，并减少
correct-to-wrong、unsupported claim 和无效 audio 秒数。若 planner 不能优于简单 rule router，论文
应如实把贡献收缩为 multimodal memory use，而不是 agentic policy。

### U3 — Grounded minutes assembly

将通过的 policy 接入 decision/action ledger，比较 no-memory、text-memory 与 omni-memory 的完整
四段式纪要。每个 atomic claim 必须绑定 text/audio handle；verifier 可以接受、re-listen 一次、降低
置信度或拒绝。U3 才评估整体纪要，不允许用 U3 的结果回头修改 U1/U2 的门。

## 8. 研究问题与可证伪假设

- **RQ1：声音 memory 是否存在纯文本不可替代的条件增益？**
  - H1：在 action commitment、speaker/owner 和 ASR disagreement 子集，paired memory 优于
    text-only，且优于 deranged-audio。
- **RQ2：声音的价值来自哪里？**
  - H2：增益集中在 speaker/discourse/prosody-sensitive strata，而不是所有 minutes claim 均匀提高。
- **RQ3：agent 是否会正确选择 memory 模态？**
  - H3：有界 router 以更少 audio 秒数达到接近 always-paired 的质量，并降低无效调用。
- **RQ4：omni use 是否改善最终纪要而不放大错误？**
  - H4：结构化 action/decision factuality 和 evidence support 提升，同时 worst-meeting、
    worst-speaker、correct-to-wrong 和 unsupported activation 不越安全门。
- **RQ5：embedding 是否仍然重要？**
  - H5：在 use policy 固定后，omni embedding 只改善候选可达性；若 use capability 本身不成立，
    embedding 提升不能转化为 minutes 增益。

所有假设都允许失败。尤其是“audio-only/paired 不优于 text-only”会直接否定当前 omni memory 的
核心必要性，并迫使路线回到更窄的 text agent 或声学工具任务。

## 9. 指标与安全门

### 9.1 主指标

- action item exact/slot F1：`action, owner, due, status`；
- decision state macro-F1：`proposed, accepted, rejected, deferred, uncertain`；
- atomic claim evidence precision/recall；
- correct-minus-deranged 配对差；
- supported wrong-to-correct 与 correct-to-wrong；
- speaker/owner attribution accuracy。

### 9.2 次指标

- summary factual consistency、informativeness 和 meeting-specific human error taxonomy；
- WER/cpWER/SAER-M，仅用于诊断 perception 改变；
- agent steps、audio seconds、text characters、tokens、latency、abstention 和 replay rate；
- worst-meeting、worst-speaker、按 opportunity type 的分布。

ROUGE 不能作为唯一主门。现有 meeting 评测研究已经指出，speaker dynamics、turn-taking、遗漏和
语言不准确等错误不会被通用 summary metric 充分捕捉。

### 9.3 必须保留的反事实控制

- wrong-speaker audio；
- same-speaker but wrong-topic audio；
- same-text with mismatched audio；
- time-shifted neighborhood；
- audio/text dose matching；
- audio channel present but silent/noise-matched control；
- planner action trace 与 evidence consumption trace。

没有这些控制，“加了声音后变好”不能证明系统使用了正确的 omni memory。

## 10. Training-free 优化空间

在 U1/U2 通过后，允许优化的对象包括：

1. typed evidence need 的定义与分解；
2. memory tool schema、description 和调用顺序；
3. planner 的最大步数、re-listen gate 和 stop rule；
4. modality router 与 cost-aware dispatch policy；
5. evidence packet 的排序、配对、剂量和 conflict rendering；
6. draft→verify→revise 的控制流；
7. abstention、unsupported-claim 和 deranged-evidence safety gate；
8. 最后才是 embedding instruction、query construction 与多索引融合。

GEPA/GRPO 式搜索仍需后续单独放行；在此之前只能做预注册的离散 policy 对照，不能用确认集持续
调参。这样既扩大了研究空间，也避免把“agentic”变成不可复现的 prompt search。

## 11. 论文故事与预期贡献

若关键门通过，论文故事可写成：

1. 提出 training-free **OmniMinutes**：以 frozen omni model 为唯一智能核心、以 raw audio-text
   episodic memory 为 evidence plane 的 meeting agent；
2. 建立 meeting-specific memory-use taxonomy，区分 lexical、speaker、discourse、stance 和
   chronology evidence need；
3. 提出带 modality derangement 的严格评测，证明模型是在使用正确声音，而非受 second-pass 或
   context dose 影响；
4. 证明 agentic modality routing 能在质量、安全和 audio 成本之间做出可复现取舍；
5. 生成带 text/audio provenance 的结构化 decisions、actions 和 final minutes。

如果只有 U1 通过而 U2 不通过，贡献应收缩为“native audio-text memory use for meeting minutes”；
如果只有 retrieval signal 而 U1 不通过，则不能继续宣称 omni agentic memory 有效。

## 12. 与当前实验线的关系

- 现有 material semantic gate 和 construction-isolated 结果保持原判，不改写为本 proposal 的证据。
- `E-MATERIAL-OMNI-CAPABILITY-CI` 缺逐 turn trace 的不运行判决继续有效；新 proposal 不构成恢复
  trace 或调用模型的授权。
- 现有失败结果反而给出重要设计约束：禁止广播长摘要、禁止 output-only 模糊检索、必须保留
  deranged control、逐 turn trace、primary opportunity census 和 one-shot reader。
- 新路线首先建立新的 U0 opportunity census 和 prospective trace，然后才登记 U1。它不会借用
  已读确认集事后选择候选。

## 13. 最近下一步

1. 扩展文献表：系统检索 audio RAG、speech summarization、meeting decision/action、agent memory、
   multimodal long-context 五组关键词，记录 task、memory modality、planner、generator 和评测缺口。
2. 对 AMI/ICSI 现有 annotation schema 做零模型映射，确认 decision/action/dialogue-act/speaker 与
   raw audio 的可对齐性，并估算 U0 的跨会议供给。
3. 起草 `MemoryItem`、`EvidenceNeed`、`EvidencePacket`、`MemoryActionTrace` 四个纯数据 schema；
   不实现模型调用。
4. 设计 U1 的候选构造和 derangement 规则，尤其避免 gold label 影响 runtime memory 选择。
5. 只有供给、预算、最小效应、reader 和 trace schema 全部冻结后，才建立正式实验 ID 与预注册。

## 14. 参考文献入口

- Someki et al. (2026), [PlanRAG-Audio](https://arxiv.org/abs/2605.20414).
- Chen et al. (2025), [WavRAG](https://arxiv.org/abs/2502.14727).
- Min et al. (2024), [Speech Retrieval-Augmented Generation without ASR](https://arxiv.org/abs/2412.16500).
- Wijngaard et al. (2025), [AudioToolAgent](https://arxiv.org/abs/2510.02995).
- Sharma et al. (2024), [Speech vs. Transcript](https://aclanthology.org/2024.acl-long.790/).
- Chen et al. (2025), [MISP-Meeting](https://aclanthology.org/2025.acl-long.753/).
- Murray et al. (2006), [Speaker and Discourse Features](https://aclanthology.org/N06-1047/).
- Morgan et al. (2006), [Action Items in Audio Meeting Recordings](https://aclanthology.org/W06-1314/).
- Purver et al. (2007), [Action Items in Multi-Party Dialogue](https://aclanthology.org/2007.sigdial-1.4/).
- Kirstein et al. (2024), [Multi-Source Meeting Summarization](https://aclanthology.org/2024.emnlp-industry.69/).
- Retkowski et al. (2025), [Summarizing Speech: A Comprehensive Survey](https://aclanthology.org/2025.emnlp-main.1388/).
