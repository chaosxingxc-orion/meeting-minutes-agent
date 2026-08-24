# EARNINGS22-RUNTIME-DOMINANT-GATE

- 状态：**已判读**
- 类型：冻结结果上的零模型、回顾性机制审计
- 计划：[运行时主讲 cluster 门控](../../plans/2026-08-24-earnings22-runtime-dominant-gate.md)
- 预注册：[冻结规则](../../readiness/2026-08-24-earnings22-runtime-dominant-gate-preregistration.md)
- 证据：[一次性判读](../../checks/2026-08-24-earnings22-runtime-dominant-gate-read/README.md)
- 正式结论：[verdict](../../readiness/2026-08-24-earnings22-runtime-dominant-gate-verdict.md)

## 研究问题

不读取 gold 时，Sortformer RTTM 的整会占比与跨 10 分钟窗稳定性，能否识别“少数主讲占主导、
主要 speaker 路由可用”的会议？该门只决定会议是否进入后续 Pass-0，不修改 diarizer、切片器
或预处理，也不授权 Omni 调用。

## 结论与下一步

放行57/76场，dominance precision 38.60%、recall 73.33%；放行集合 Top-1/Top-2 错误
12.36%/27.79%，其中29/57场的逐会 Top-2 错误超过40%。正式判为
`RUNTIME-DOMINANT-GATE-UNSAFE`。固定4路输出会把长尾稳定地合并进少数 cluster，因此
“预测占比稳定”不等于“真实主讲身份稳定”。不得在同一125场上继续搜索阈值。

后续所有 pass 仍须遍历固定的全部合格短片段；下一项候选是另行注册 Pass-0 转写供给审计，
优化对象为整会内按 speaker/术语聚合的重复、稳定错误簇。稳定错误还必须有独立合法锚点，
否则不能知道应改成什么。该模型实验尚未获本次零模型审计自动授权。
