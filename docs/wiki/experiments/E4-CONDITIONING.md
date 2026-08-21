# E4-CONDITIONING：固定 speaker-conditioned 第二遍

- 状态：`已判读`
- 表面：36 target turns，40 carry entities，六臂 216 calls
- 模型接触：216/216 成功，零重试、零截断

实验比较 bare、label-only、global、correct-speaker、wrong-speaker 和 corrupt state。全部 semantic state 逐 turn 等长，避免把候选数量误解释为 speaker routing 效果。所有有 carry 机会的 turn 都运行，不按错误选择、不做选择性重听。

机械判决为 **`CONTEXT-SENSITIVE-NOT-SPEAKER-SPECIFIC`**。correct-speaker 将 WER 从 4.19% 降到 3.89%、carry NE-WER 从 9.38% 降到 7.81%，但只修复 2 个、破坏 1 个，并且只比 wrong-speaker 多 2 个命中；两个门均要求 3。corrupt 状态把 carry NE-WER 恶化到 15.62%，确认错误供给风险。

- [预注册](../../readiness/2026-08-20-e4-conditioning-preregistration.md)
- [正式判读](../../readiness/2026-08-20-e4-conditioning-verdict.md)
- [机器 verdict](../../checks/2026-08-20-e4-conditioning-read/verdict.json)
- [完整报告](../../checks/2026-08-20-e4-conditioning-read/report.txt)
- [Flight 回执](../../checks/2026-08-20-e4-conditioning-flight/README.md)
- [冻结 manifest](../../../configs/probes/contextasr/2026-08-20-e4-conditioning-36-manifest.json)

高功效规划 E4-POWER 和未见对话 E4-CF 已于同日完成。E4-CF 确认路由方向为正，但 +2.16 pp 未达到 5 pp 强效应门；因此 agent loop 仍不放行，下一步改为冻结输出的机制审计。
