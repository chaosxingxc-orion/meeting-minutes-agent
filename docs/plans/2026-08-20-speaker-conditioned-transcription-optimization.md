# 基于说话人条件的专业会议转写优化计划

日期：2026-08-20  
状态：**执行中；RTTM-only 主讲门判为 `RUNTIME-DOMINANT-GATE-UNSAFE`；下一候选为稳定错误供给审计，agent loop 仍未放行**

## 0. 给同事的结论摘要

本研究不再优化 diarizer、切片器或音频预处理，而是在固定的短语音片段和固定说话人标签上，研究 Qwen3-Omni 能否利用会议内、说话人相关的文本状态，提高专业词转写质量。

需要把两类实验严格分开：

1. `Z-*` 是前置地板实验，研究说话人归属、标签来源和切分方式；
2. `E*/S*` 是本计划的新实验，研究已知说话人的短片段能否通过提示词、状态、工具脚本和 agent loop 改善转写文本。

当前可以冻结前端作为工程范围，但不能把截图中的“26 个点”解释为“说话人文本进入 Omni 后提高了转写”。现有 Z-turn 实现中，标签由控制器在模型外附加；该差值主要包含归属方式、音频单元和任务形式的变化。

## 1. 前置 Z 系列实验：定义、证据与缺口

### 1.1 当前仓库中已登记的定义

| 实验臂 | 仓库中的实际定义 | 当前证据 |
|---|---|---|
| `Z-turn` | 按 diarization turn 单独切音频；模型只转写；控制器附加已知 speaker | 设计来自 P-ATTR 的 `A-turn`；已采用为归属骨架 |
| `Z-free` | 90 秒 transport slice；不给转向表；要求模型自行转写并归属 | P-ATTR 已测过对应的 `A-free` |
| `A-grid` | 与 `A-free` 使用相同 90 秒音频和模板，仅增加文本转向表 | 输出格式被 grid 劫持，已淘汰 |
| `Z-nodiar` | 当前提交中没有正式定义、配置、receipt 或 verdict | **待补证据** |
| `Z-oracle` | 当前提交中没有独立实验定义；旧 G1 草案曾把 oracle turns 作为 Z-turn ceiling | **存在命名冲突** |

截图所述 `Z-turn=0.6099`、`Z-free=0.873`、`Z-nodiar=0.882`、`Z-oracle=0.6061` 尚未在当前仓库找到可复核的配置、逐会议分数、置信区间或判读文件。因此这些数字只能标为“外部汇报值，待归档”，不能作为本计划已验证的前提。

### 1.2 必须补做的 Z-AUDIT

在引用上述结论前，建立 `Z-AUDIT` 记录并完成：

1. 固定每个臂的音频 manifest、hash、speaker 来源、prompt hash、装配规则和 scorer hash；
2. 给出逐会议配对结果、bootstrap 置信区间、检验方法和 MDE；
3. 明确标签是“进入模型提示”还是“仅供控制器装配”；
4. 检查每个对照是否真的只改变一个因素；
5. 将“不显著”表述为“在当前 MDE 下未检测到差异”，除非预注册并通过等价性检验。

建议统一命名，避免继续复用含义已经变化的 `Z-turn`：

| 对照轴 | 推荐臂 | 唯一允许变化的因素 | 可回答的问题 |
|---|---|---|---|
| 模型侧转向表 | `Z-grid` vs `Z-free` | 相同长切片中是否加入文本转向表 | Omni 是否会利用转向表完成归属 |
| 控制器归属 | `Z-attach` vs `Z-blind` | 相同 turn 音频是否由控制器附加已知标签 | cpWER 中归属通道值多少分；这是结构量化，不是转写增益 |
| 标签来源 | `Z-tool` vs `Z-oracle` | 尽量固定音频单元，仅替换标签来源 | 工具标签相对人工标签的下游代价 |
| 切分几何 | `Z-turncut` vs `Z-vadcut` | 标签、提示、上下文和评分保持相同，仅改变边界 | 切分方式的独立影响 |

如果技术上无法让某组只改变一个因素，就必须称为“端到端策略对照”，不能作单因素因果解释。

## 2. 本研究的问题与边界

核心问题是：

> 在 diarization、说话人标签、turn 边界、音频字节、预处理、模型权重和服务版本全部固定时，会议内的说话人条件文本状态，能否降低短片段专业词错误率，同时不恶化整体 WER、非专业词 WER 和最差说话人 WER？

本计划暂不假设模型能够检测自身错误、选择性重听或在两次转写中自动选优。能力未被单独验证前，最强合法策略是：对所有符合条件的 turn 执行统一的完整第二遍转写。

证明是条件性的：

- 若冻结模型对合法条件信息不敏感，则任何 prompt/GEPA/training-free GRPO/EM 式循环都不可能在该搜索空间内产生真实增益；
- 若存在可达的改进策略，并被有限搜索访问，且通过保留 incumbent 的配对验收规则，则经验损失单调不增；
- 这不预先保证改进策略一定存在，也不保证无标签自我反思能泛化到新会议。

## 3. 形式化对象与固定公理

令 `m` 表示会议，`s` 表示会议内 diarization cluster，`i` 表示固定说话人 turn：

```text
F_front = (D_diar, S_slice, P_audio)
X_m = F_front(A_m) = {x_mi}_{i=1..n_m}
x_mi = (a_mi, s_mi, b_mi, h_mi)
```

其中 `a_mi` 是音频字节，`s_mi` 是已知 cluster，`b_mi=(start,end)`，`h_mi` 是内容 hash。实验 manifest 必须冻结所有 `x_mi`。

固定公理：

```text
A1. F_front 在冻结 manifest 上确定且不变。
A2. theta = theta_0；Qwen3-Omni 参数不更新。
A3. server、model、checkpoint、decode 和 cache 控制逐臂固定。
A4. 模型只返回转写文本；speaker 由控制器附加。
A5. 所有学习状态在会议结束时销毁。
A6. reference/gold 只对 scorer 可见，不能进入运行时状态。
```

合法策略为：

```text
omega = (p, r, u, q)
```

- `p`：纯转写 prompt 及专业转写指令；
- `r`：将全局状态和说话人状态渲染为有界文本；
- `u`：从合法信息确定性构造/更新会议内状态；
- `q`：固定 rollout 日程，例如是否对全部合格 turn 执行第二遍。

任何策略不得改变音频、speaker id、边界、顺序或 hash；`q` 在 E5 前不得查看未知正确性并选择性重听。

## 4. 两遍状态与 agent loop

第一遍后构造会议全局状态和说话人状态：

```text
H_m^global = (G_m, N_m, E_m)
H_ms       = (G_ms, N_ms, V_ms, E_ms)
```

- `G`：专业术语候选；
- `N`：姓名、机构、产品、数字和缩写；
- `V`：该说话人的观测拼写变体；
- `E`：指向合法元数据或第一遍模型输出的 provenance。

对 turn `i` 的条件上下文为：

```text
C_mi(omega) = r_omega(H_m^global, H_m,s_mi)
Y_mi^0 ~ K_theta0(. | a_mi, p_0, empty_context, xi_mi0)
(H_m^global, {H_ms}) = u_omega({(x_mi, Y_mi^0)}_i, legal_metadata_m)
Y_mi^1 ~ K_theta0(. | a_mi, p_omega, C_mi(omega), xi_mi1)
U_hat_mi^k = (s_mi, Y_mi^k), k in {0,1}
```

speaker 恒等式由控制器保证：

```text
speaker(U_hat_mi^k) = s_mi
```

因此本研究优化的是 `Y_mi` 的专业转写文本，不再把 diarization 归属能力混入优化目标。

### 4.1 整会 loop 与稳定错误簇

必须区分三个粒度：执行单元是固定短音频 `x_mi`，优化单元是整会内同 speaker、同规范化
术语的重复观测簇，episode 是会议的一次完整 pass。每一轮都遍历冻结 manifest 中的全部
合格片段，不允许根据上一轮结果选择性重听。

令 `z` 为规范化术语候选，`O_msz` 为会议 `m` 中预测 speaker `s` 对 `z` 的全部复现，
`e_i` 为该复现的转写形式。定义：

```text
repeat_msz = |O_msz|
stability_msz = max_e |{i in O_msz : e_i = e}| / |O_msz|
StableWrong_msz := repeat_msz >= k and stability_msz >= tau and majority(e_i) != truth(z)
Optimizable_msz := StableWrong_msz and LegalAnchor_msz and Controllable_msz
```

其中 `LegalAnchor` 必须来自运行时合法且独立的证据，例如议程、幻灯片、公开术语表或另一次
高置信观测；reference/gold 只能评分。`Controllable` 表示有界提示状态能修复该簇，同时通过
false-hint、整体 WER、非术语 WER 和最差 speaker 保护门。稳定正确簇不应被改写，不稳定簇
只能进入证据收集，不能直接生成纠错状态。

完整更新写为：

```text
Y_m^(t) = FullPass(X_m, H_m^(t), omega_t)
C_m^(t) = ClusterByMeetingSpeakerTerm(Y_m^(t))
A_m^(t) = {c in C_m^(t) | Repeated(c) and Stable(c) and LegalAnchor(c)}
H_m^(t+1) = BoundedUpdate(H_m^(t), A_m^(t))
candidate = FullPass(X_m, H_m^(t+1), omega_t)
H_m^(t+1) is accepted iff meeting-level paired utility and every safety gate pass;
otherwise rollback to H_m^(t)
```

因此“错得稳定”只提供可重复优化靶点，并不自动提供正确答案。

## 5. 指标与可达性

`T_mi` 是仅供评分器使用的参考文本。除整体 `WER` 外，定义：

```text
BWER = 专业词上的对齐错误数 / 专业词参考 token 数
UWER = 非专业词上的对齐错误数 / 非专业词参考 token 数
L_worst = max_s WER_s
GIS = glossary-induced substitutions
UAR = unsupported activation rate
```

注册损失是约束向量，而不是事后调权的单一分数：

```text
L(omega) = (BWER, WER, UWER, L_worst, GIS, UAR,
            grammar_failure, calls, audio_seconds, latency)
```

`BWER` 是主改进面；其余指标是非劣、伤害和预算约束。E0 必须在模型接触前冻结 MDE、主效应阈值和非劣界限。

可达性分四层：

```text
R_interface := 服务接受“固定音频 + 转写 prompt + 有界文本状态”
R_behavior  := 正确状态与等长错配状态产生的差异超过 decode/cache 噪声
R_route     := S3-speaker 优于 S4-deranged，且优于 S2-global
R_utility   := BWER 达到主效应阈值，且全部保护指标通过
```

其中：

```text
Delta_use   = BWER(S3) - BWER(S0)
Delta_route = BWER(S3) - BWER(S4)
Delta_spk   = BWER(S3) - BWER(S2)
```

三个差值越负越好。`Delta_route<0` 才能说明收益来自正确的说话人路由，而不只是通用词表偏置。

## 6. 可证明与不可证明的边界

### 命题 1：前端不变性

合法策略只返回文本，故不会改变 `(a_mi,s_mi,b_mi,h_mi)`。

### 命题 2：说话人保持

控制器执行 `attachSpeaker(x,text)`，因此输出 speaker 必然等于输入 `s_mi`，与模型行为无关。

### 命题 3：不敏感时不可优化

若所有合法策略在实验面上的输出分布与基线相同：

```text
forall omega in Omega_legal,
K_theta0(. | x, omega) = K_theta0(. | x, omega_0)
```

则所有策略的期望损失相同。此时增加 loop 次数、prompt mutation、GEPA、training-free GRPO 或 EM 更新都不能产生严格改进。E1/E2 用于判断是否落入该分支。

### 命题 4：有限访问集上的经验单调性

令 `Omega_visited` 包含基线和全部已评估候选；只在候选通过保护约束且配对置信规则后替换 incumbent，则每次接受后：

```text
L_hat_primary(incumbent_{t+1}) <= L_hat_primary(incumbent_t)
```

这只证明已访问集合上的经验改进，不证明 proposer 一定能找到更优策略。

### 命题 5：泛化验收

以会议而非切片为独立统计单位。新策略只有在主指标配对差异的置信上界低于零，且所有保护指标上界不超过预注册非劣界限时才能接受。自适应搜索不得反复查询最终 holdout；E6 必须划分 discovery、selection 和 untouched final roles。

### 命题 6：没有合法锚点时，稳定错误不可识别

设运行时只观察同一稳定字符串 `v`。存在两个与观测完全一致的世界：`W_correct` 中
`truth(z)=v`，`W_wrong` 中 `truth(z)≠v`。若无额外合法证据，任意更新器在两个世界接收相同
输入，必然作出相同动作；保持 `v` 会在 `W_wrong` 失败，替换 `v` 会在 `W_correct` 引入错误。
因此仅凭重复和稳定性不存在保证严格改善的纠错策略。`LegalAnchor` 不是启发式加分，而是
可识别性的必要条件。

## 7. Lean 4 结构证明草图

下列代码表达结构性结论；后续任务需在冻结的 Lean/mathlib 版本下实际编译，当前不是已机器核验的 artifact。

```lean
import Mathlib.Data.Finset.Basic
import Mathlib.Data.Rat.Defs

namespace SpeakerConditionedTx

structure TurnUnit where
  meetingId : String
  speakerId : String
  startMs   : Nat
  endMs     : Nat
  audioHash : String

structure Transcript where
  speakerId : String
  text      : String

def attachSpeaker (x : TurnUnit) (text : String) : Transcript :=
  { speakerId := x.speakerId, text := text }

theorem speaker_preserved (x : TurnUnit) (text : String) :
    (attachSpeaker x text).speakerId = x.speakerId := by
  rfl

variable {Policy : Type}

def UtilityReachable [DecidableEq Policy]
    (Omega : Finset Policy) (loss : Policy → Rat) (base : Policy) : Prop :=
  ∃ p ∈ Omega, loss p < loss base

theorem no_strict_improvement_of_constant [DecidableEq Policy]
    (Omega : Finset Policy) (loss : Policy → Rat) (base : Policy)
    (hconst : ∀ p ∈ Omega, loss p = loss base) :
    ¬ UtilityReachable Omega loss base := by
  intro h
  rcases h with ⟨p, hp, hlt⟩
  rw [hconst p hp] at hlt
  exact (lt_irrefl (loss base)) hlt

theorem selected_no_worse [DecidableEq Policy]
    (Omega : Finset Policy) (loss : Policy → Rat)
    (base selected : Policy) (hbase : base ∈ Omega)
    (hoptimal : ∀ p ∈ Omega, loss selected ≤ loss p) :
    loss selected ≤ loss base := by
  exact hoptimal base hbase

inductive AnchorWorld where
  | observedFormCorrect
  | observedFormWrong

inductive CorrectionAction where
  | keep
  | replace

def succeedsWithoutAnchor : AnchorWorld → CorrectionAction → Prop
  | .observedFormCorrect, .keep => True
  | .observedFormWrong, .replace => True
  | _, _ => False

theorem no_unanchored_action_succeeds_in_both_worlds (a : CorrectionAction) :
    ¬ (succeedsWithoutAnchor .observedFormCorrect a ∧
       succeedsWithoutAnchor .observedFormWrong a) := by
  cases a <;> simp [succeedsWithoutAnchor]

end SpeakerConditionedTx
```

## 8. 实验总表与进度

状态词固定为：`未开始`、`设计中`、`已注册`、`运行中`、`已判读`、`已暂缓`、`已淘汰`。

| ID | 实验 | 状态 | 核心问题 | 输出/决策 |
|---|---|---|---|---|
| Z-AUDIT | Z 系列证据归档与正交性审计 | **已暂缓** | 截图中的四臂定义、数值和显著性是否可复核 | 用户决定暂不继续该系列 |
| E0 | 数据面与统计功效审计 | **已判读** | 固定 turns 上是否有足够专业词和可用 MDE | AMI 专业词过稀；ContextASR 适合 supply；Earnings21 适合 recurrence/glossary loop |
| E1 | 合法 speaker-conditioned 能力 smoke | **已判读** | `R_behavior/R_route/R_utility` 是否成立 | 已由 E4/E4-CF 实化：行为和路由方向成立，5 pp 强效用门未通过 |
| E2 | oracle supply 上界 | **已判读** | 理想术语/画像存在时模型能否利用 | C-CTX：`CONTEXT-SENSITIVE-BUT-UNCONTROLLED`；NE-WER 改善 4.93 pp，距 5 pp 门槛 0.07 pp |
| E3 | 合法说话人状态构造 | **已判读** | 不用 gold 能否构造精确、低污染状态 | `LEGAL-STATE-READY`：precision 90.04%，hallucination 9.96%，same-speaker recall 57.50% |
| E4 | 固定完整第二遍 | **已判读** | 完整合法策略能否满足 `R_utility` | `CONTEXT-SENSITIVE-NOT-SPEAKER-SPECIFIC`；修复 2/门槛3，路由优势 2/门槛3 |
| E4-POWER | 独立确认功效与预算 | **已判读** | 检测 5 pp 改善需要多大未见表面 | 287 dialogues，833 carry mentions，6,922 calls，22.01 audio-hours；已授权并转入 E4-CF |
| E4-CF | 未见对话独立确认 | **已判读** | 5 pp speaker-routing 改善能否复现 | `DIRECTIONAL-NOT-CONFIRMED`：speaker 比 wrong +2.16 pp，CI 为正但低于 5 pp 门；carry NE-WER -3.66 pp，无总体 WER 伤害 |
| E-STABLE-ERROR-SUPPLY | 整会稳定错误与合法锚点供给 | **已判读** | `(meeting,speaker,term)` 是否有重复稳定错误且可识别 | 13个strict stable-wrong覆盖4场，但ticker锚点0；事后诊断9/13为分隔符变体，不放行term Pass1 |
| E5 | oracle 选优/重听上界 | **未开始** | 逐 turn 选择还有多少理论空间 | 空间小则淘汰选择性重听；否则另立能力计划 |
| E6 | prompt/state 策略优化 loop | **未开始** | 有界搜索能否继续改进 incumbent | 候选档案、验收轨迹、冻结策略或 null |

后续实验不得因为代码已经方便运行而越过 entry gate。

## 9. 可直接执行的实验设计

### E0：数据面与功效审计（零模型调用）

盘点冻结的 tool-diar turn clips，输出会议数、speaker 数、turn 数、参考词数、专业词数、同会议同 speaker 的重复专业词、跨 turn 距离、排除理由、角色合法性和 audio hash。用已有合法输出估计会议级方差、MDE 和非劣界限。若 AMI 专业词密度不足，应更换专业 ASR 数据面，而不是强行飞一个低功效实验。

### E1：合法 speaker-conditioned 能力 smoke

所有臂复用 byte-identical 音频和固定 speaker 标签；reference 只供评分。

| 臂 | 输入状态 | 目的 |
|---|---|---|
| `S0-bare` | `transcribe-only-v1`，无状态 | 基线 |
| `S1-label` | 仅 cluster label | 身份 token 安慰剂 |
| `S2-global` | 等长会议全局状态 | 通用词表偏置 |
| `S3-speaker` | 正确路由的合法 `H_ms` | 说话人条件收益 |
| `S4-deranged` | 另一 speaker 的等长合法状态 | 路由负对照 |
| `S5-corrupt` | 机械破坏的等长状态 | 诱导替换/伤害对照 |

主对照为 `S3-S0`、`S3-S4`、`S3-S2`。请求顺序必须 counterbalance，或在 block 间重置 server/cache。E0 后预注册四种判读：`不可达`、`敏感但不可控`、`说话人条件可达`、`上下文有害`。

### E2：oracle supply 上界

仅作 Tier-M1 诊断。输入包含 reference-correct 拼写与匹配 decoy 的平衡列表，并设置正确、错配、破坏路由。它只检验冻结模型能否从音频中选择给定拼写，不证明运行时能够发现该拼写。若 E1、E2 均失败，则在当前数据面淘汰 speaker conditioning。

### E3：合法状态构造

只运行 Pass 0，再由同会议模型输出和合法元数据构造状态，构造完成后才与 gold 比较。测量术语 precision/recall、标准拼写正确率、speaker 路由准确率、污染和 carry；比较 `GATED`、`NAIVE_RAW`、`DERANGED`、`NO_CARRY`。gold 派生项不得回送模型。

### E4：固定完整第二遍

把 E3 胜出状态应用到每个合格 turn，按会议比较完整 `Y^1` 与完整 `Y^0`。禁止 oracle 或学习式逐 turn selector。报告 BWER、WER、UWER、macro/worst-speaker WER、GIS、UAR、grammar、调用数、音频秒数和时延。

### E5：只计算 oracle 上界

使用 E4 已产生的成对结果，离线计算：

```text
L_oracle = sum_i min(L(Y_mi^0), L(Y_mi^1))
```

gold 仅用于估计上界。若 oracle 选择相对最佳固定策略的差距低于预注册阈值，淘汰选择性重听；否则另写 detector/selector 能力计划，不能直接进入实现。

### E6：有界 agent 优化

仅在 E4 证明合法效用可达后启动。GEPA、training-free group-relative 或 EM 风格更新可以提议 `p/r/u/q`，但模型参数保持冻结。每个候选必须通过泄漏、静态、预算和配对评估；baseline 与 incumbent 始终留在 archive。

## 10. 实现级优化循环

```text
front_manifest := 冻结的 tool-diar turn manifest
baseline       := 无状态 transcribe-only 策略 omega_0
incumbent      := baseline
archive        := {baseline}

Z-AUDIT: 归档并审计前置多臂实验；修复命名和因果口径
E0: 审计数据面，冻结指标、MDE 和非劣界限
E1: 测试合法 speaker conditioning 是否可达
if E1 negative:
    E2: 测试 Tier-M1 oracle 上界
    if E2 negative: 淘汰当前数据面上的 speaker conditioning

E3: 构造并验证合法的每 speaker 状态
if E3 gate fails: 停止；瓶颈是状态构造

E4: 对所有合格 turn 运行固定完整第二遍
if E4 utility gate fails: 停止；不得引入选择性重听

E5: 用 E4 成对结果计算 oracle 选择上界

E-STABLE-ERROR-SUPPLY: 在小型注册 roster 上执行完整 Pass-0
    按会议、speaker、规范化术语聚合复现
    报告 stable-correct / stable-wrong / unstable 及合法锚点覆盖
    若没有足量 Optimizable cluster: 停止；loop 缺少可识别供给

E6, 每轮有界优化:
    按会议、speaker、术语错误簇分层抽取 discovery meetings
    对冻结 manifest 执行完整 grouped rollouts，不选择性重听
    计算正确/错配/破坏条件的语义对照
    生成 prompt/render/update/fixed-rollout 候选
    拒绝违反固定前端、泄漏或预算公理的候选
    在注册 selection surface 上做会议级配对评估
    仅当置信规则及全部保护约束通过时替换 incumbent
    否则保留 incumbent
    hash 并记录候选、trace、score 和 decision

按 config/render/code hash 冻结最终 incumbent
在 untouched final meetings 上执行一次注册判读
```

## 11. 下一步与汇报规则

下一项小任务不是启动 agent loop，而是：

1. 保持 Z 系列暂缓，不消耗资源补跑；
2. 保持 E4-CF 的 `DIRECTIONAL-NOT-CONFIRMED` 为正式结论，不用 post-hoc 分层替换它；
3. 保留 Earnings-22 Sortformer 的条件性主讲结论，但依据 `RUNTIME-DOMINANT-GATE-UNSAFE` 禁止用 RTTM 占比筛选 Omni pilot；
4. `E-STABLE-ERROR-SUPPLY` 已证明 strict exact-form 稳定错误存在，但锚点为0，且9/13是分隔符变体；禁止据此启动term Pass1；
5. 下一步只能二选一：引入并独立审计新的合法专业词锚点，或把集中输出语言漂移注册成整会语言可控性实验；两者不得混为speaker-term收益；
6. 只有足量错误簇同时满足 `Repeated ∧ StableWrong ∧ LegalAnchor ∧ Controllable`，才进入一次完整 Pass-1；
7. 在新的独立 surface 通过实用效应门之前，不启动 GEPA、GRPO、EM 风格多轮 agent loop，也不引入选择性重听。

每次进展必须更新实验总表，并链接 preregistration、config、flight receipt、read artifact 和 verdict。历史失败或淘汰结论只追加，不得被后续方案重写。

2026-08-21 的执行结果已归档在 [`docs/wiki/2026-08-21-progress-summary.md`](../wiki/2026-08-21-progress-summary.md)：包含 `E4-CF-MECH`、后续固定策略实验及跨领域供给审计的完整判读。
