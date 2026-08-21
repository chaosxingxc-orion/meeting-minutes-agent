# P-PROMPT：基础提示词形式

- 状态：`已判读`
- 规模：14 臂，336/336 请求

机械规则选出 **T1-A1**：system turn 中仅保留基础转写/归属指令和输出语法约束，user turn 只放音频。均值 cpWER 为 0.4789，语法合规率 1.0000。

错误 roster（X1）和陈旧跨会议 tail（X2）分别退化 `+0.0127`、`+0.0454` cpWER，均落入预注册的 `CONTEXT-INDETERMINATE` 区间。后续若重新引入 roster、glossary 或 tail，必须独立预注册；不能把本实验解释成“上下文无害”。

- [正式判读](../../readiness/2026-08-18-pprompt-verdict.md)
- [机器判决](../../checks/2026-08-18-pprompt-read/verdict.json)
