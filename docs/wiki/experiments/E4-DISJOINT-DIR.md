# E4-DISJOINT-DIR：speaker 与 global 两臂方向性实验

- 状态：`已注册`
- 定位：低资源、低功效、探索性方向 pilot
- 授权范围：172次第二遍调用；不包括完整确认或 agent loop

实验使用 `E4-DISJOINT-PREV` 已冻结的60个未见 dialogue。机械规则选出86个 `speaker_wrong_disjoint` 自然 carry target，来自52个 dialogue，共93个 carry mention。每个 target 比较等长 `D0-global` 与 `D1-speaker`，预算172 calls、2,114.418重复音频秒。

主指标是 speaker 相对 global 的 carry exact-hit rate；同时检查 carry NE-WER、总体 WER、false-hint target rate 和截断。所有标签均为探索性，正方向也不能改写 E4-CF 的正式判定或放行 agent loop。

- [中文实验计划](../../plans/2026-08-21-e4-disjoint-direction-pilot.md)
- [正式预注册](../../readiness/2026-08-21-e4-disjoint-direction-preregistration.md)
- [父实验判读](../../readiness/2026-08-21-e4-disjoint-prevalence-verdict.md)
