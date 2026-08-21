# E4 固定 speaker-conditioned 第二遍预注册

日期：2026-08-20  
状态：**REGISTERED；尚无 E4 模型输出**

## 问题与声明边界

本实验检验：在音频、turn、匿名 speaker label、模型、decode 和候选数量固定时，从同 speaker 的合法 Pass-0 历史构造的文本状态，能否比 bare、全局状态和 wrong-speaker 状态更好地纠正重复专业实体。

这是 E3 discovery surface 上的小型能力 smoke，不是独立 confirmatory set。目标 turn 由 gold-side “存在同 speaker carry entity”定义，但 36 个合格 turn 全部运行；不根据 Pass-0 错误选择，不做选择性重听。reference、carry entity 和 Pass-0 错误只在 scorer 使用，禁止进入 launcher 请求。

## 冻结样本和输入

- Manifest：`configs/probes/contextasr/2026-08-20-e4-conditioning-36-manifest.json`
- content hash：`543b7109f35dbeccf14263e1441522122bab9c4ab8ba8751c7929d28a94f7a5d`
- file sha256：`69672edc43a7e8c92b99d8cb83f3e527bd9922245bc3050005b6afda0c607d27`
- Parent E3 responses sha256：`8962b04435055f3c62e651221d69861313217d7b3baf7298f1b08852b9c10c56`
- 36 target turns，40 个 same-speaker carry mentions；216 calls；2,429.34 audio-seconds。
- 所有 semantic state 臂逐 turn 等长；宽度为 1–8 项，分布 `{1:2, 2:5, 3:9, 4:4, 5:3, 6:4, 7:4, 8:5}`。
- Pass-0 设计审计：34/40 carry mentions 已精确命中，剩余 6 个；carry token error rate 9.375%。因此只预注册离散能力门，不作总体效应声明。

## 六臂

| 臂 | 输入 | 作用 |
|---|---|---|
| `E4-0-bare` | audio only | 同期无状态基线 |
| `E4-1-label` | 匿名 current speaker label | label-token 安慰剂 |
| `E4-2-global` | label + 全局历史的等长状态 | 不分 speaker 的供给 |
| `E4-3-speaker` | label + 正确 speaker 历史状态 | 主候选 |
| `E4-4-wrong` | label + 其他 speaker 历史的等长状态 | 路由负对照 |
| `E4-5-corrupt` | label + 机械错拼的正确 speaker 状态 | 错误供给护栏 |

各 target 的六臂按 Latin rotation 排序。提示仅要求“音频支持时才使用候选拼写”；template hash `81a8a0d09ffab9a8991cf406478c260f8df85917d5d1227e8dbc3df690e3daea`。

## 指标和机械判决

报告整体 WER、carry NE-WER、carry exact FNR、提示假激活和截断。`corrected` 是 bare 未命中但 speaker 命中的 carry entity；`broken` 是 bare 命中但 speaker 破坏的项。

按以下顺序判决：

1. speaker 相对 bare 的 WER 恶化 >1.00 pp、`broken > 1` 或 speaker 有截断：`SECOND-PASS-HARMFUL`。
2. `corrected >= 3`、`broken <= 1`、speaker 比 wrong 多至少 3 个 carry hits，且 carry NE-WER 不劣于 bare：`SPEAKER-CONDITIONING-REACHABLE`。
3. 任一 semantic state 臂的 carry hits 与 bare 不同：`CONTEXT-SENSITIVE-NOT-SPEAKER-SPECIFIC`。
4. 否则：`SPEAKER-CONDITIONING-NOT-REACHABLE`。

这些阈值只能证明/否定本表面的窄能力，不能推导大规模平均增益。

## 预算、实现和一次性读取

- 模型与 server 参数沿用 E3：Q4_K_M `d9e28765…4dd85`、mmproj `1104376…c8d`、16,384 context、单 slot。
- `temperature=0, seed=0, max_tokens=512`；零 retry；上限 216 calls / 2,500 audio-seconds。
- request module sha256：`44e4c17bd6f5b7c0e2c2023d325016bbe8c0b3a8dbc069d3b3ce8ef2dbe5bb20`
- scorer sha256：`a623050742d89e0451ba12c2ba6a715735666ebe858a0725310779dc2a680dff`
- launcher sha256：`cca915d4558e5793b4bf5cceaef9057ffef32b6160e658ba406da9c58bca6d46`
- read driver sha256：`f92a1a41a08679e39a06cb40ee08190028a53cd202df1bbe4400b79718988241`
- server script sha256：`06b23c666789cb0f626b5f37cc87c829064264db96dc2f71abc74bf06ee32a1f`
- 专项测试：3 passed；全仓：1,196 passed / 9 skipped。

Flight 只写模型文本和运行元数据。完成后仅运行一次 `scripts/e4_conditioning_read.py`，输出目录存在时拒绝覆盖。
