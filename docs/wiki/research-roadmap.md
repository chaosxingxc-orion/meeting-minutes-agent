# 研究路线图：说话人条件专业转写

研究对象是固定 diarizer、切片器、预处理和模型后的短语音片段转写。优化变量只包括 prompt、会议内/说话人内文本状态、工具脚本和 controller policy。

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
| E5 | Training-free agent loop | 未放行 | E4-CF 未通过强效应门；先做冻结结果机制分析 |
| E6 | 多会议确认与最差 speaker 检验 | 未放行 | E5 尚未放行；启动前需预注册样本量、MDE、CI 和多重检验 |

当前证明只能写成条件命题：若存在一个控制策略在固定输入分布上降低预注册损失，且选择器不引入更大误选风险，则有限候选的迭代可单调改进到局部不动点。C-CTX 与 E3 已证明“模型会读取供给”和“合法状态可构造”；E4-CF 只观察到低于实用门的小幅 speaker 路由收益。后续方向 pilot 被 false-hint 安全门否决，简单拒绝门也未能保留收益，因此当前还不存在可用于 agent loop 的安全单步改进算子。

形式化定义、Lean 风格定理和逐步实现接口见[完整研究计划](../plans/2026-08-20-speaker-conditioned-transcription-optimization.md)。

## 2026-08-22 最近检查点

Earnings-22 窄类 reserve 已确认30/45场 eligible、264个 carry；随后125个官方 MP3 已完整获取并逐文件校验。音频本身、ID 联结和解码均通过，但上游 CSV 时长门失败；参考诊断还显示116/125场超过锁定 Sortformer 的4-speaker上限，兼容子集只有9场。下一检查点是决定停止这条固定前端跨域路线，还是另行注册不限人数前端 smoke；完整模型确认与 E5 继续不放行。详见[阶段性结论](stage-conclusions.md)和[实验总表](experiments/README.md)。
