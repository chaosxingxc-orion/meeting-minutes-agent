# E4-CONFIRMATORY：未见对话独立确认

- 状态：`已判读`
- 授权：owner 已明确授权 5 pp 主设计
- 判定：`DIRECTIONAL-NOT-CONFIRMED`
- 规模：287 dialogues；3,822 Pass-0 calls；774 targets、3,096 second-pass calls

实验排除全部 12 个 E3/E4 discovery dialogues。runtime 和 score manifests 物理分离；模型侧只读取音频、turn、匿名 speaker 和由 Pass-0 hypothesis 构造的状态。

Pass 0 后必须先过 attrition gate：可用 carry mentions 至少 707。通过后运行 bare/global/correct-speaker/wrong-speaker 四臂；以 dialogue-cluster bootstrap 检验 correct-speaker 相对 wrong-speaker 至少 5 pp 的 exact hit-rate 改善，同时要求相对 bare 的 carry NE-WER 改善和整体 WER 非劣。

实际 attrition gate 保留 832/833 个 carry mention。speaker 相对 wrong 的命中率提高 2.16 pp，95% CI `[0.11, 4.30]` pp：方向显著为正，但未达到预注册的 5 pp 点估计门。speaker 相对 bare 的 carry NE-WER 改善 3.66 pp，整体 WER 改善 1.86 pp，均通过；未触发伤害门。因此确认“有小的 speaker-routing 增益”，但不能确认“至少 5 pp 的强效应”，agent loop 继续不放行。

- [正式预注册](../../readiness/2026-08-20-e4-confirmatory-preregistration.md)
- [Runtime manifest](../../../configs/probes/contextasr/2026-08-20-e4-cf-287-runtime-manifest.json)
- [Score manifest](../../../configs/probes/contextasr/2026-08-20-e4-cf-287-score-manifest.json)
- [Candidate roster](../../../configs/probes/contextasr/2026-08-20-e4-confirmatory-candidate-roster.json)
- [正式判读](../../readiness/2026-08-20-e4-confirmatory-verdict.md)
- [Pass 0 证据](../../checks/2026-08-20-e4-cf-pass0-flight/README.md)
- [绑定与 attrition 证据](../../checks/2026-08-20-e4-cf-binding/README.md)
- [第二遍证据](../../checks/2026-08-20-e4-cf-secondpass-flight/README.md)
- [一次性统计读取](../../checks/2026-08-20-e4-cf-read/README.md)
