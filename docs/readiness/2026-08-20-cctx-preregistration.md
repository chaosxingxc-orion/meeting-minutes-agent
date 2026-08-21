# C-CTX：Omni 专业实体上下文可达性 Smoke（已注册）

日期：2026-08-20  
状态：**REGISTERED，尚未接触模型**

## 1. 研究问题与结论边界

本实验只回答：在音频完全相同时，冻结的 Qwen3-Omni 是否能利用提示中的领域和实体拼写，提高专业实体转写。

`C2-entity` 使用数据集提供的正确 `entity_list`，属于 Tier-M1 oracle ceiling。它可以证明模型“会不会用”，不能证明会议 agent 能从合法运行时信息中发现这些词，也不能证明 speaker-conditioned routing 已经可达。

既有零模型审计已经确认：AMI 开放词表实体过稀，不适合作为专业词增益主实验；ContextASR 是高密度 supply testbed。依据见 `docs/readiness/2026-08-17-entity-density-census.md` §5。

## 2. 冻结样本

- 数据：ContextASR-Bench `ContextASR-Speech_English.jsonl`。
- 音频载体：`ContextASR-Speech_English_1.tar`。
- 样本：32 条、32 个不同领域；时长 31.52–60.95 秒，总计 1,435.24 秒/臂。
- 实体：227 个，平均 7.09 个/样本。
- 选择：按领域 round-robin；领域内按 `sha256(seed:id)` 排序。
- manifest：`configs/probes/contextasr/2026-08-20-cctx-32-manifest.json`。
- manifest hash：`ecc8bfd2a4700a19324e89584480cfeb4177f0d904278e9474db80d88d98281c`。

音频在调用前从 tar 临时解出，并逐条核对 manifest 中的 SHA-256；不把音频写入仓库。

## 3. 五个实验臂

五臂共享同一 system prompt、音频、decode 参数和输出语法，仅 supplied-text 不同：

| 臂 | supplied-text | 作用 |
|---|---|---|
| `C0-bare` | 空 | 无上下文基线 |
| `C1-domain` | 正确领域名 | 粗粒度上下文 |
| `C2-entity` | 正确领域名 + oracle 实体列表 | 正确供给上界 |
| `C3-deranged` | 正确领域名 + 等规模、目标文本中不存在的其他样本实体 | 错配供给负对照 |
| `C4-corrupt` | 正确领域名 + 对正确实体作确定性拼写破坏 | 错误拼写诱导对照 |

每个样本内按 Latin rotation 改变臂顺序，平衡 server/cache 时间漂移。禁止根据中途输出更改 prompt、样本、顺序或评分规则。

## 4. 服务、解码与预算

- 模型：`Qwen3-Omni-30B-A3B-Instruct-Q4_K_M.gguf`；mmproj Q8_0；实际路径和 hash 写入 receipt。
- 服务：仓库 featcache llama.cpp build；启动参数和 server identity 写入 receipt。
- 解码：`temperature=0`、`seed=0`、`max_tokens=1024`。
- 请求：160 次，无自动 retry；每个成功/失败请求立即追加到 JSONL。
- 音频预算：7,176.21 秒；硬上限 7,200 秒。
- 单请求硬限制：120 秒。

## 5. 指标固定

主指标采用 ContextASR-Bench 官方实现，固定到提交
`897de87bd4eb430de28dca807fc725958c7ebc85`：

- `WER`；
- `NE-WER`：对 fuzzy-matched 实体序列计算词错误率；
- `NE-FNR`：`1 - exact matched entities / reference entities`。

附加安全指标：错误列表的 exact/fuzzy activation、unsupported activation、输出为空、达到 token cap、请求失败和时延。聚合同时报告 micro 值、逐样本值和以样本为单位的 10,000 次配对 bootstrap 95% CI（固定 seed `20260820`）。

## 6. 预注册对照与判读

定义低值为优：

```text
Delta_use   = NE-WER(C2) - NE-WER(C0)
Delta_route = NE-WER(C2) - NE-WER(C3)
Delta_wer   = WER(C2)    - WER(C0)
```

判读按下列顺序执行：

1. `CONTEXT-HARMFUL`：`Delta_wer` 的 bootstrap 上界大于 `+0.02`，或 C2 出现注册外格式/失败；
2. `ORACLE-CONTEXT-REACHABLE`：`Delta_use <= -0.05`、`Delta_route <= -0.05`，两者 bootstrap 上界均 `<0`，且 `Delta_wer` 上界 `<=+0.02`；
3. `CONTEXT-SENSITIVE-BUT-UNCONTROLLED`：C2/C3/C4 相对 C0 有稳定输出或实体激活变化，但不满足第 2 条；
4. `CORE-CONTEXT-NOT-REACHABLE`：未检测到超过配对噪声的上下文效应。

这是 capability smoke，不作论文级总体效应声明。若第 2 条成立，下一步才进入合法状态构造与 speaker routing；若第 4 条成立，先停止 agent loop 工程投入。

## 7. 一次性读取纪律

运行前必须完成并通过：manifest loader、请求顺序、tar hash guard、resume、官方指标复现单元测试、缺失臂 fail-closed 测试和 verdict 分支测试。flight 完成后只运行一次冻结 read suite；任何修复必须保留原始输出并另立带版本的判读记录。
