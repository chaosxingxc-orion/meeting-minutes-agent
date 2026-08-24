# E-STABLE-ERROR-SUPPLY

- 状态：**已注册**
- 类型：4场整会、完整 Pass0、稳定错误供给 discovery
- 计划：[中文设计](../../plans/2026-08-24-e-stable-error-supply.md)
- 预注册：[冻结身份与预算](../../readiness/2026-08-24-e-stable-error-supply-preregistration.md)
- 模型预算：1429 calls，15077.153 音频秒

## 目的

验证优化单元是否应从独立短片段提升为整会内的 `(speaker, term)` 重复错误簇。运行时只收到
固定 turn 音频；speaker 由控制器附加。reference 和 ticker 仅在全部 Pass0 完成后的唯一一次
评分中读取。

本实验不执行选择性重听、Pass1、prompt 搜索、GEPA、GRPO 或 EM。通过只表示存在下一步可测
的稳定错误与合法锚点供给；可控性仍需独立实验。
