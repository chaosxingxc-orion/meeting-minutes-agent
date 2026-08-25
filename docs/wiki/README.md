# 研究 Wiki

本目录是仓库内、可版本控制的研究入口，面向实验执行、复核和汇报。它只维护导航、当前状态和结论摘要；预注册、配置、回执与逐项结果仍以 `docs/readiness/`、`configs/` 和 `docs/checks/` 中的记录为准。

## 当前工作计划

- **[2026-08-26 工作计划](2026-08-26-work-plan.md)**：先完成construction-isolated三臂Omni实验的零模型预算审计、预注册和一次性reader；未获新授权不运行模型。

## 研究与证据入口

- [2026-08-20 研究进展总结](2026-08-20-progress-summary.md)：今日完成事项、实验数字、证明边界与下一步。
- [2026-08-21 研究进展总结](2026-08-21-progress-summary.md)：机制审计结果、唯一候选策略与下一步。
- [2026-08-22 工作记录](2026-08-22-work-plan.md)：Earnings-22 reserve 决策、窄类确认和当日禁止事项。
- [2026-08-24 工作总结](2026-08-24-work-plan.md)：全库前端、完整Pass0、两类稳定性实验和两类独立证据审计。
- [2026-08-25 工作总结](2026-08-25-work-plan.md)：官方材料供给、语义K、独立准入失败及construction-isolated运行时门的完整进展。
- [阶段性结论](stage-conclusions.md)：当前已证明、未证明和 agent loop 放行边界。
- [实验总表](experiments/README.md)：当前完成度、结论和下一步。
- [研究路线图](research-roadmap.md)：说话人条件专业转写的 E0–E6 路线。
- [实验登记模板](experiment-template.md)：新实验开始和结束时必须填写的字段。
- [完整研究计划](../plans/2026-08-20-speaker-conditioned-transcription-optimization.md)：形式化目标、可优化性证明与实施细节。

## 维护规则

1. 模型接触前，先在实验总表登记 ID、问题、状态、负责人和预注册链接。
2. 将数据切分、模型/工具版本、prompt、预算和判决阈值冻结到预注册及配置文件。
3. 飞行后保存回执和机器可读结果；只运行预先构建的 read suite。
4. 完成判读后更新实验页、总表和“下一步”，但不得覆盖或重写原始证据。
5. Wiki 不保存语音、数据集、权重、密钥、gold transcript 或运行时不可见的答案。

状态统一使用：`未开始`、`设计中`、`已注册`、`运行中`、`数据准备`、`已判读`、`未放行`、`已暂缓`、`已淘汰`。

## 当前总判断

合法 speaker state 已经证明可构造，但 E4-CF 的 +2.16 pp 仍低于 +5 pp 正式门。资源受限 Pass-0 在60个未见 dialogue 上测得52.76%的 `speaker_wrong_disjoint` prevalence；后续172-cell方向 pilot 显示 carry 指标小幅改善，但 false-hint 增加3.49个百分点并越过安全门，判为 `EXPLORATORY-HARMFUL`。agent loop 继续不放行。

当前优先级仍是先建立 agent-loop 稳定层，再做效用优化。广播式上下文和同chunk稀疏检索均已
失败；排除自回灌后的模糊候选虽覆盖980 turns，gold精度仅1.93%。output-only检索分支停止，
会议同期官方材料已形成3场、49项带出处库存；字符和词法router均未过门，但伞仓锁定的encode-only
Qwen3语义K在同一Q/K/V和错配控制下达到77.86%归属precision，较词法提高15.997点且3/3场过门。
后续独立准入审计确认Earnings-22的125场参考词面已被v2/v3全部读取，严格未读队列为0；
top1/top2运行时门因此没有执行。同事已接受另立证据较弱的construction-isolated复用实验，
现已冻结六场3+3队列并完成6/6场官方材料准入，共54页、1,403个原始候选；缺失Pass0已另行
注册并完成，1,639/1,639成功、0空输出、0重试。零模型开发集冻结阈值0.01，唯一确认读取达到
76.10%归属precision、74.82%覆盖和0.06154中位余弦优势，四项预注册门全部通过，判为
`CONSTRUCTION_ISOLATED_SIGNAL_PRESENT`。该路线仍不能宣称独立确认或WER增益，
training-free GRPO与多模态知识注入仍未放行。

最后同步：2026-08-26（8月25日总结已封存，8月26日计划已登记）。
