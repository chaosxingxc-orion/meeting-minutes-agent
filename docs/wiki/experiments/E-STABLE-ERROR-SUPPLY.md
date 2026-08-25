# E-STABLE-ERROR-SUPPLY

- 状态：**已判读**
- 类型：4场整会、完整 Pass0、稳定错误供给 discovery
- 计划：[中文设计](../../plans/2026-08-24-e-stable-error-supply.md)
- 预注册：[冻结身份与预算](../../readiness/2026-08-24-e-stable-error-supply-preregistration.md)
- 飞行：[1429-call Pass0](../../checks/2026-08-24-e-stable-error-pass0-flight/README.md)
- 判读：[稳定错误供给](../../checks/2026-08-24-e-stable-error-supply-read/README.md)
- 正式结论：[verdict](../../readiness/2026-08-24-e-stable-error-supply-verdict.md)
- 模型预算：1429 calls，15077.153 音频秒

## 目的

验证优化单元是否应从独立短片段提升为整会内的 `(speaker, term)` 重复错误簇。运行时只收到
固定 turn 音频；speaker 由控制器附加。reference 和 ticker 仅在全部 Pass0 完成后的唯一一次
评分中读取。

## 结论

完整1429-call Pass0 找到13个 stable-wrong group，覆盖4/4场和70次复现；稳定错误供给门通过。
但 ticker 锚点命中0，正式判为 `STABLE-ERROR-SUPPLY-PRESENT-ANCHOR-LIMITED`，不放行Pass1。

事后诊断发现9/13只是缩写分写/连写差异，因此不能称为13个语义专业词错误。另有一场出现
125/450条稳定输出语言漂移；会议语言是合法锚点，可另行注册整会语言可控性实验，但它不是
speaker-term优化收益。
