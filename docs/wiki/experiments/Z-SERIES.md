# Z-SERIES：前置多臂实验

- 状态：`已判读`
- 当前决定：G1 floors 已完成，不重跑；结论仅作为描述性基线，不选择后续分支。

远端主仓库已归档 dev-18 四臂 G1 floors：1,932/1,932 calls 可评分，Z-turn、Z-oracle、Z-free、Z-nodiar 的平均 cpWER 分别为 `0.6099`、`0.6061`、`0.8726`、`0.8816`。这与同事截图一致，并有预注册、逐会议结果、cluster bootstrap、flight receipt 和一次性 read 支撑。

主要解释是：Z-free 相对 Z-turn 的 cpWER 高 `+0.2627`（90% CI `[+0.2286,+0.2978]`），其中约 `+0.1947` 来自 speaker assignment；Z-nodiar 相对 Z-free 仅 `+0.0091`，区间跨零。也就是说，主要价值来自把文本形式的转向表交给模型并按说话人装配输出，而不是切片边界本身。Z-turn 与 Z-oracle 的 cpWER 差 `+0.0037`，区间跨零，不能声称工具 diarizer 优于或等同 oracle；结果还受 AMI 域内 diarizer 影响。

- [正式预注册](../../readiness/2026-08-19-g1-floors-preregistration.md)
- [一次性描述性判读](../../readiness/2026-08-19-g1-floors-verdict.md)
- [Flight 回执](../../checks/2026-08-19-g1-floors-flight/README.md)
- [Read 证据](../../checks/2026-08-19-g1-floors-read/README.md)
