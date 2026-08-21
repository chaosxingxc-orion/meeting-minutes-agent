# E4-CF 未见对话独立确认实验预注册

日期：2026-08-20  
状态：**REGISTERED；owner 已明确授权 6,922-call 主设计；尚无 confirmatory 模型输出**

## 1. 研究问题和独立性

检验合法 correct-speaker 状态相对等长 wrong-speaker 状态，能否在未见 ContextASR dialogues 上带来至少 5 个百分点的 carry exact hit-rate 改善，同时相对 bare 改善 carry NE-WER 且不伤害整体 WER。

冻结 roster 含 287 个 dialogues，全部排除 E3/E4 discovery 的 12 个 dialogue；roster sha256 `0019748e…1ef6`。该 confirmatory 不复用 E4-36 调 prompt，不改变 5 pp MDE，不做选择性重听，不在运行中查看文本或指标。

## 2. 泄漏分离与冻结输入

Pass 0 runtime manifest 仅含音频定位/hash、turn 边界和匿名 speaker：

- `configs/probes/contextasr/2026-08-20-e4-cf-287-runtime-manifest.json`
- content hash `a079a997c2685c045e3823b82cfbafc353a8fdc77c17874125883aede9428546`
- file sha256 `8a70c0c1e8e9f029e5b5a2bcf3f695b71edb1f1607c2e3f336bb495b9fa5d8a1`

Score manifest 单独保存 reference/entity，launcher 不读取：

- `configs/probes/contextasr/2026-08-20-e4-cf-287-score-manifest.json`
- content hash `0612abd49228999707dc317ea97f06eb1138dff9abe1718aef5ec0fc7a04e994`
- file sha256 `68fd6eca9bd2180ef0faf6c60b9e0ee0219a1addb42c5ab2e2e2f273eb412c37`

287 个 dialogue 共 3,822 turns。原始 census 有 833 same-speaker carry mentions、775 target turns。

## 3. 两阶段执行和 attrition gate

### Pass 0

- 对 3,822 turns 全部运行 audio-only bare transcription。
- 上限 3,822 calls / 44,000 audio-seconds；实际 manifest 音频 43,528.48 秒。
- `temperature=0, seed=0, max_tokens=512`，单 slot，零 retry。
- append-only responses；若中断，只允许 `--resume` 并写新的分段 receipt，旧记录不覆盖。

### 状态构造与 gate

Pass 0 完成后，使用 score manifest 仅确定全部自然 carry target；状态内容仍只来自历史 Pass-0 hypotheses。每个 target 构造 `min_evidence=1 + dedupe + inventory_cap=8` 的 global、correct-speaker 和 wrong-speaker 状态，截成相同宽度。

- 可用 carry mentions ≥707：`ATTRITION-GATE-PASS`，冻结 runtime/score bindings 后进入第二遍。
- <707：`UNDERPOWERED-ATTRITION`，保存 summary 并停止，不进行第二遍。

### 四臂第二遍

| 臂 | 输入 |
|---|---|
| `CF0-bare` | audio only |
| `CF1-global` | 匿名 speaker + 等长全局状态 |
| `CF2-speaker` | 匿名 speaker + 等长正确 speaker 状态 |
| `CF3-wrong` | 匿名 speaker + 等长其他 speaker 状态 |

所有可用 target 全部运行，按四臂 Latin rotation；上限 3,100 calls / 36,000 audio-seconds。Pass 0 后重启 server，再开始第二遍；feature cache 可复用，但生成状态重置。Template hash `85b41c7c2ac7f11119444e131f15de701b14708a69f79dd7ed260fc5f0cc90eb`。

## 4. 指标、置信区间和机械判决

以 dialogue 为 cluster 做 10,000 次 paired bootstrap，seed `20260820`。报告四臂 WER、carry NE-WER、carry exact hit rate/FNR、false hint activation 和截断。

主对照：

1. `hit_rate(CF2)-hit_rate(CF3)`：要求点估计 ≥5 pp 且 95% CI 下界 >0。
2. `carry_NE-WER(CF2)-carry_NE-WER(CF0)`：要求 ≤-1 pp 且 95% CI 上界 <0。
3. `WER(CF2)-WER(CF0)`：95% CI 上界 ≤+1 pp。

按顺序判决：

- point WER harm >1 pp、WER CI 上界 >2 pp 或 CF2 截断：`CONFIRMATORY-HARMFUL`。
- 三个主门全部通过：`SPEAKER-CONDITIONING-CONFIRMED`。
- hit 方向为正、carry NE-WER 方向为负且 WER harm ≤1 pp，但至少一门未通过：`DIRECTIONAL-NOT-CONFIRMED`。
- 其余：`SPEAKER-CONDITIONING-NOT-CONFIRMED`。

只执行一次 read；不得因结果近失下调 5 pp 或改 CI 规则。

## 5. 冻结实现、模型和测试

- request/schema module sha256 `60d4ee5dafdf249e88b994e2132dfaf37aca5a57ac220c848e566adb14bb7981`
- scorer sha256 `49de410d60583d80eae69897d9ffc17ebdef350cdac8a3d2d3e5cfcde4e93c9e`
- Pass-0 launcher sha256 `b9bde42b25691534317276423f0f1927b1b71a2e9b5cba24e6cfa6ac6992594f`
- binding builder sha256 `b2b09fa64d674f5e056438ef06cd25d1403e46b5574319b7936ea1929823787e`
- second-pass launcher sha256 `3a549fd9162582fe66d76d1a259f3d22f8adf47c3a5ee8414bc240a5c3e8b796`
- read driver sha256 `ff7b3139fa76dda7b42bc0d96e1f09c7b170ddf22e6e47c6d73ff63b5505ce8b`
- server script sha256 `ea3716de03471a1e279d4ee89f89dc7d89fbead2eb3ccd097882490b03788e2a`
- 专项测试 3 passed；全仓 1,203 passed / 9 skipped。

模型和 server 与 E4-36 相同：Q4_K_M `d9e28765…4dd85`、mmproj Q8_0 `1104376d…c8d`、llama-server `ad694375…74fa9`，`-c 16384 -np 1 -fa on -ngl 999 -ctk q8_0 -ctv q8_0`。
