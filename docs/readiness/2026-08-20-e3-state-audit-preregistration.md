# E3 合法说话人状态审计预注册

日期：2026-08-20  
状态：**REGISTERED；模型输出尚未产生、尚未读取**

## 1. 问题与边界

本实验检验：固定 turn 边界和匿名 speaker label 后，仅从同一对话中更早的 **Pass-0 模型转写**，能否构造高支持率、低幻觉、可路由且能覆盖后续同 speaker 实体的文本状态。

ContextASR-Dialogue 的 turn 边界和 role 仅作为固定前端代理；role 被匿名化为 `speaker_1...`，不进入模型。reference text 与 `entity_list` 只在 read 阶段评分，禁止进入 Pass 0 或状态构造。该 discovery smoke 不证明真实 diarizer 的泛化效果，也不直接测第二遍 ASR 增益。

## 2. 冻结样本与预算

- Manifest：`configs/probes/contextasr/2026-08-20-e3-state-audit-12-manifest.json`
- content hash：`d9fa2b277929d9ee7a0f51a8ac37099de2e0154de1028238bad9a8299700af9e`
- file sha256：`8adce09605db05158006bc7fd82bc77acd826e4ffd1591a8ef8eee91b045ff9f`
- 12 个未用于 C-CTX-32 的 English dialogues，151 turns，1,747.963 秒。
- 选择规则：全体 5,273 dialogues 中同 speaker carry target 至少 2 个；固定 seed 后按 SHA-256 排序取前 12。全体有 1,933 个合格 dialogue；冻结样本含 40 个同 speaker、34 个 global-only carry targets。
- Pass 0：151 次 bare transcription，`temperature=0, seed=0, max_tokens=512`；零 retry；上限 151 calls / 1,800 audio-seconds。
- 模型与 server 参数沿用 C-CTX：Q4_K_M `d9e28765…4dd85`，mmproj Q8_0 `1104376d…c8d`，`-c 16384 -np 1 -fa on -ngl 999 -ctk q8_0 -ctv q8_0`。
- prompt template hash：`be34f885d683c117520f72c16a655691f1a8b9686c6badde4c7b42e3e083cf9c`。

## 3. 状态臂

所有臂仅读取目标 turn 之前的 Pass-0 hypothesis。

| 臂 | 构造 | 目的 |
|---|---|---|
| `gated-speaker` | 同 speaker 历史，`min_evidence=2` | 当前通用 glossary 默认值 |
| `first-mention-speaker` | 同 speaker 历史，dedupe，`min_evidence=1`，最多 8 项 | 本实验主候选；允许第一次出现服务第二次出现 |
| `gated-global` | 全部 speaker 历史，`min_evidence=2` | 不分 speaker 的全局状态 |
| `naive-speaker` | 同 speaker 原始候选，不 gate | recall 上界/污染对照 |
| `no-carry-speaker` | 仅最近一个同 speaker turn | carry 消融 |
| `wrong-speaker` | 仅其他 speaker 历史 | 路由负对照 |

## 4. 指标与机械判决

`support_precision`：状态项在先前 reference speech 中有字面支持的比例；`hallucination_rate` 为其补集。`off_speaker_rate`：有历史支持但只来自其他 speaker 的比例。`target_relevance`：状态项出现在当前目标 turn 的比例。主效用为 scoring-side `same_target_recall`，即同 speaker 历史中已出现且在当前 turn 重现的登记实体被状态覆盖的比例。

`first-mention-speaker` 同时满足以下条件才判 `LEGAL-STATE-READY`：

1. `same_targets >= 30`；
2. support precision ≥ 0.70，hallucination ≤ 0.30；
3. same-speaker target recall ≥ 0.30；
4. 相对 `gated-global`，off-speaker rate 至少降低 0.10，same-target recall 损失不超过 0.10。

否则，若 `naive-speaker` recall ≥ 0.30，判 `STATE-EXTRACTION-BOTTLENECK`；再否则判 `STATE-NOT-RECOVERABLE`。规则由 `state_audit_scoring.py` 机械执行，不作事后翻转。

## 5. 设计阶段 ceiling 披露

在注册前使用 reference history 做过一次**非模型、非正式设计 ceiling**。默认 `gated-speaker` recall 仅 0.15；`naive-speaker` recall 0.575，暴露 `min_evidence=2` 无法让首次出现服务第二次出现。由此提出 `first-mention-speaker`；其设计 ceiling support precision 0.9758、hallucination 0.0242、same-target recall 0.575、off-speaker rate 0。该表面属于 discovery，不能充当最终结果；正式 read 必须使用 Pass-0 hypothesis。

## 6. 冻结实现与一次性读取

- 状态构造 sha256：`df53ac45e174e1d9c57062481bd4c7d4994c2854672b4643619a4c594e5c8f39`
- scorer sha256：`82fb9f58a57ea49706a24a55cc278481331eb1fa0533fbe6c8bfd3af536fcc03`
- launcher sha256：`92d2507a2215f405a4c998c60e5888bb0969e9f669d5d266b0da3fa7097e9faa`
- read driver sha256：`470b54cddecb59a40d2e78a547de86869e7bd6355f2e17d5f08b6b1fa8e64e55`
- server script sha256：`8f2619bbb5525c3bb4d74e4dfa716e0b4be9f3d33e17fd00f04ae734ed02a2a6`
- 预建专项测试：7 passed；全仓离线回归：1,193 passed / 9 skipped；summary preflight：12 dialogues / 151 calls / 1,747.963 s。

Flight 只写 append-only hypotheses 和 receipt，不在运行时评分。完成后仅运行一次 `scripts/e3_state_audit_read.py`，输出到新的 `docs/checks/2026-08-20-e3-state-audit-read/`，若输出已存在则拒绝覆盖。
