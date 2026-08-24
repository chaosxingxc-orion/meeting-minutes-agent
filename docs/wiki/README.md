# 研究 Wiki

本目录是仓库内、可版本控制的研究入口，面向实验执行、复核和汇报。它只维护导航、当前状态和结论摘要；预注册、配置、回执与逐项结果仍以 `docs/readiness/`、`configs/` 和 `docs/checks/` 中的记录为准。

## 当前工作计划

- **[2026-08-22 当前工作计划](2026-08-22-work-plan.md)**：先决定是否启用 Earnings-22 的45场未读 reserve；若放行，再预注册 `ABBREVIATION/ALPHANUMERIC` 窄类确认审计。默认不下载音频、不调用模型。

## 研究与证据入口

- [2026-08-20 研究进展总结](2026-08-20-progress-summary.md)：今日完成事项、实验数字、证明边界与下一步。
- [2026-08-21 研究进展总结](2026-08-21-progress-summary.md)：机制审计结果、唯一候选策略与下一步。
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

当前优先级：不部署当前等长 speaker inventory，也不启动约31,749-call完整确认。Earnings-22 的125个官方音频已完整获取并校验，但116/125场超过固定前端4-speaker上限，兼容子集不足以支撑既有功效门。下一步决策是停止该跨域路线，或另行注册不限人数前端 smoke；模型 pilot 继续不放行。

最后同步：2026-08-22（当前工作计划置顶，移除过期的 2026-08-21 计划）。
