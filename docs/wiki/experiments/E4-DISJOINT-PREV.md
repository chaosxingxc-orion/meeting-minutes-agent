# E4-DISJOINT-PREV：资源受限 prevalence 筛查

- 状态：`已判读`
- 正式筛查判决：`PREVALENCE-SCREEN-PASS`
- 类型：staged Pass-0；不做第二遍
- 资源：60 dialogues、795次调用、2.564小时音频

本实验回答当前推理栈在未见 dialogue 上能否产生足够比例的 `speaker_wrong_disjoint` 状态。它不比较 global/speaker 转写，也不测 carry、WER 或 false hint 效果。

实验按20/40/60 dialogue 三级执行。prevalence 依次为62.96%、54.81%、52.76%，前两级均按冻结规则继续。最终163/164个 natural carry target 状态可用，86个 predicate positive；dialogue-cluster bootstrap80%区间为46.71%–59.01%，usable carry 为99.43%。点估计高于48.29%盈亏线，因此通过工程筛查。

全部795次调用成功，零重试、零跳过，没有第二遍。3个响应达到512-token上限；它们最多影响8个 target，即使按最不利方向全部剔除，点估计仍为50.32%。

这说明50%左右的 prevalence 规划假设具有可用性，但不解决完整确认实验约31,749次调用、101.55小时的成本问题。下一步若继续，应另行预注册约172次调用的 D0-global vs D1-speaker 小型方向性 pilot；它仍然是探索性实验。

- [冻结设计](../../plans/2026-08-21-e4-disjoint-prevalence-pilot.md)
- [正式注册](../../readiness/2026-08-21-e4-disjoint-prevalence-preregistration.md)
- [Server 修订](../../readiness/2026-08-21-e4-disjoint-prevalence-server-amendment.md)
- [正式判读](../../readiness/2026-08-21-e4-disjoint-prevalence-verdict.md)
- [Flight 归档](../../checks/2026-08-21-e4-disjoint-prev-flight/README.md)
- [Read 归档](../../checks/2026-08-21-e4-disjoint-prev-read/README.md)
- [前序功效审计](E4-DISJOINT-POWER.md)
