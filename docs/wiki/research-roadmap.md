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
| E5 | Training-free agent loop | 未放行 | E4-CF 未通过强效应门；先做冻结结果机制分析 |
| E6 | 多会议确认与最差 speaker 检验 | 未放行 | E5 尚未放行；启动前需预注册样本量、MDE、CI 和多重检验 |

当前证明只能写成条件命题：若存在一个控制策略在固定输入分布上降低预注册损失，且选择器不引入更大误选风险，则有限候选的迭代可单调改进到局部不动点。C-CTX、E3 和 E4-CF 已依次证明“模型会读取供给”“合法状态可构造”“speaker 路由存在小的额外收益”。E4-CF-MECH 进一步只保留“不重叠时 speaker，否则 global”的单一假设，但它仍需独立确认；不能据此启动多轮 loop。

形式化定义、Lean 风格定理和逐步实现接口见[完整研究计划](../plans/2026-08-20-speaker-conditioned-transcription-optimization.md)。

## 2026-08-21 最近检查点

`E4-DISJOINT-PREV` 用795次 Pass-0 调用得到52.76% prevalence；172-cell的 `E4-DISJOINT-DIR` 因 false-hint +3.49个百分点判为有害。后续零模型安全门审计没有找到兼具覆盖、安全和 carry 收益的规则。跨域供给审计进一步显示 Academic/ICSI 供给充足，但 Product/AMI 的严格技术 carry 只有 3 个，不能支持平衡跨域 pilot。因此当前固定策略不可部署，完整确认与 E5 继续不放行。详见[实验总表](experiments/README.md)。
