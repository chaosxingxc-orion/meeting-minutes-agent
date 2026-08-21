# E4-DISJOINT-DIR：speaker 与 global 两臂方向性实验

- 状态：`已判读`
- 定位：低资源、低功效、探索性方向 pilot
- 授权范围：172次第二遍调用；不包括完整确认或 agent loop

实验使用 `E4-DISJOINT-PREV` 已冻结的60个未见 dialogue。机械规则选出86个 `speaker_wrong_disjoint` 自然 carry target，来自52个 dialogue，共93个 carry mention。每个 target 比较等长 `D0-global` 与 `D1-speaker`，预算172 calls、2,114.418重复音频秒。

唯一一次正式判读为 **`EXPLORATORY-HARMFUL`**。speaker 相对 global 的 carry exact-hit rate 提高1.08个百分点，carry NE-WER 降低0.70个百分点，总体 WER 不变；但 false-hint target rate 从8.14%升至11.63%，增加3.49个百分点，超过预注册的+2个百分点安全门。两个 carry 对比的95% dialogue-cluster bootstrap 区间都跨零，不能声称稳定收益。

首轮在171/172后因 `1e-12` 量级浮点预算残差于网络请求前中止。经同事明确授权并在模型接触前登记 amendment，脚本机械确认唯一缺失 cell，补跑1次、零重试，最终172-cell集合完整。该结果否决直接部署当前等长 speaker inventory；不证明所有 speaker-conditioned policy 都有害，也不放行完整31,749-call flight 或 agent loop。

- [中文实验计划](../../plans/2026-08-21-e4-disjoint-direction-pilot.md)
- [正式预注册](../../readiness/2026-08-21-e4-disjoint-direction-preregistration.md)
- [预算边界 amendment](../../readiness/2026-08-21-e4-disjoint-direction-budget-amendment.md)
- [正式判读](../../readiness/2026-08-21-e4-disjoint-direction-verdict.md)
- [机器结果](../../checks/2026-08-21-e4-disjoint-dir-read/verdict.json)
- [父实验判读](../../readiness/2026-08-21-e4-disjoint-prevalence-verdict.md)
