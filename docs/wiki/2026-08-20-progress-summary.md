# 2026-08-20 研究进展总结

## 给同事的一句话结论

今天完成了从“Omni 是否会读取专业词提示”到“未见对话上的说话人条件独立确认”的整条实验链。结果证明：合法文本状态能显著改善专业词转写，正确 speaker 路由相对错误路由还有小而稳定的额外收益；但该额外收益为 **2.16 pp**，没有达到预注册的 **5 pp** 实用效应门。因此当前结论是“方向成立、强效应未确认”，暂不放行 training-free agent loop 或选择性重听。

## 今日完成事项

1. **收敛研究问题。** 固定 diarizer、切片器和预处理；模型只转写，speaker 标签由控制器装配。优化变量限定为 prompt、会议内/说话人内文本状态、工具脚本和 controller policy。
2. **完成形式化研究计划。** 用 Lean 风格定义状态、策略、损失、安全约束和有限候选单调改进条件；明确模型参数冻结，且“存在可改进策略”必须由实验门控证明。
3. **核验执行环境。** 确认 WSL2 Ubuntu 24.04、Python 3.12 环境可用；ContextASR 数据、Qwen3-Omni Q4_K_M、Q8_0 mmproj 和冻结 llama-server 均能实际运行。
4. **澄清 Z 系列证据。** 同事截图中的 Z-turn/Z-free/Z-nodiar/Z-oracle 数值在主仓库、GitHub Wiki、issue/PR 中没有可复核回执；按决定暂缓，不消耗算力补跑，也不把归属/切分收益解释成 speaker 文本条件收益。
5. **建立仓库治理。** 新增 `AGENTS.md`、中文研究 Wiki、实验登记模板、预注册—flight—read—verdict 证据链和日期化归档规则。
6. **完成五项实验/审计。** C-CTX、E3、E4 小样本、E4-POWER 和 E4-CF 全部完成预注册或冻结规则、执行、一次性判读和归档。

## 今日实验结果

| 实验 | 规模 | 正式判定 | 关键进展 |
|---|---:|---|---|
| C-CTX | 160/160 calls | `CONTEXT-SENSITIVE-BUT-UNCONTROLLED` | 正确实体提示使 NE-WER 改善 4.93 pp，距 5 pp 门仅 0.07 pp；错误提示会显著伤害 |
| E3-STATE | 151/151 calls | `LEGAL-STATE-READY` | 无 gold 的 Pass-0 状态 precision 90.04%，hallucination 9.96%，same-speaker recall 57.50%，off-speaker 0% |
| E4-CONDITIONING | 216/216 calls | `CONTEXT-SENSITIVE-NOT-SPEAKER-SPECIFIC` | speaker 状态方向更好，但修复门和路由门均为 2/3 近失，不能放行 loop |
| E4-POWER | 零模型 census | `CONFIRMATORY-FEASIBLE-BUT-LARGE` | 冻结 287 个未见对话；5 pp 检测目标需约 6,922 calls、22.01 重复音频小时 |
| E4-CF | 3,822 + 3,096 calls | `DIRECTIONAL-NOT-CONFIRMED` | speaker 比 wrong 命中率 +2.16 pp，95% CI `[+0.11,+4.30]`；carry NE-WER 比 bare -3.66 pp；总体 WER -1.86 pp，无伤害 |

今日共完成 **7,445 次模型调用**，全部成功、零重试；累计重复计费音频约 **90,521.72 秒（25.15 小时）**。E4-CF attrition gate 保留 832/833 个 carry mention，高于预注册的 707 门槛；正式读取采用 287 个 dialogue cluster、10,000 次 bootstrap。

## 已经证明与尚未证明

已经证明：

- Omni 会利用文本中的专业词拼写，提示通道不是无效通道。
- 只用历史模型转写即可构造低污染、可按 speaker 路由的合法状态。
- 固定完整第二遍能降低 carry 专业词错误，且没有总体 WER 伤害。
- correct-speaker 相对 wrong-speaker 的增益置信区间大于零，speaker routing 不是完全无效。

尚未证明：

- 未确认 correct-speaker 路由能达到预设的至少 5 pp 强效应。
- 未证明模型能可靠自检、选择性重听或自动在两次转写中选优。
- 未证明 GEPA、training-free GRPO、EM 等多轮更新能安全单调改善。
- 未证明当前 ContextASR 固定 turn/role 结果可直接泛化到真实 diarizer 误差。

## 当前决策与下一步

1. diarizer、切片器、预处理和模型继续冻结；Z 系列继续暂缓。
2. E4-CF 正式结论保持 `DIRECTIONAL-NOT-CONFIRMED`，不得用后验分层翻转。
3. 下一项任务是**冻结输出的探索性机制审计**：解释 `CF2-speaker` 的 109 次 false-hint activation，比较 speaker/global 的净贡献，并检查状态证据数、词表长度和收益/污染的关系。
4. 机制审计后只提出一个可证伪的固定策略修改，另行预注册；新独立 surface 通过实用效应与安全门之前，不启动 agent loop。

后续任务的执行结果见 [2026-08-21 研究进展总结](2026-08-21-progress-summary.md)。

## 证据入口

- [完整研究计划](../plans/2026-08-20-speaker-conditioned-transcription-optimization.md)
- [实验总表](experiments/README.md)
- [C-CTX 判读](../readiness/2026-08-20-cctx-verdict.md)
- [E3 判读](../readiness/2026-08-20-e3-state-audit-verdict.md)
- [E4 小样本判读](../readiness/2026-08-20-e4-conditioning-verdict.md)
- [E4 功效审计](../readiness/2026-08-20-e4-power-verdict.md)
- [E4 独立确认判读](../readiness/2026-08-20-e4-confirmatory-verdict.md)
