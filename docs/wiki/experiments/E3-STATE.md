# E3-STATE：合法说话人状态构造

- 状态：`已判读`
- 样本：12 个 ContextASR English dialogues，151 turns，1,747.963 秒
- 模型接触：151/151 Pass-0 成功，零重试

本实验先做无提示 Pass 0，再仅从历史模型转写构造 speaker-specific 词表；gold transcript 和实体列表只供最后评分。主候选 `first-mention-speaker` 允许一个词第一次出现后服务下一次出现，并限制为每个目标 turn 最多 8 项。

一次性 read 判为 **`LEGAL-STATE-READY`**。`first-mention-speaker` 的 support precision 为 90.04%、hallucination 9.96%、same-speaker carry recall 57.50%。全局状态的 off-speaker rate 为 49.77%，按 speaker 路由后为 0；路由没有牺牲 recall，反而提高 22.50 个百分点。默认 `min_evidence=2` recall 只有 15%，因此冻结 `min_evidence=1 + dedupe + inventory_cap=8`。

- [预注册](../../readiness/2026-08-20-e3-state-audit-preregistration.md)
- [正式判读](../../readiness/2026-08-20-e3-state-audit-verdict.md)
- [机器 verdict](../../checks/2026-08-20-e3-state-audit-read/verdict.json)
- [完整报告](../../checks/2026-08-20-e3-state-audit-read/report.txt)
- [Flight 回执](../../checks/2026-08-20-e3-state-audit-flight/README.md)
- [冻结 manifest](../../../configs/probes/contextasr/2026-08-20-e3-state-audit-12-manifest.json)

当时登记的固定第二遍已在 E4 和独立 E4-CF 中完成。E3 本身仍只证明状态质量；转写效用以 E4-CF 的 `DIRECTIONAL-NOT-CONFIRMED` 为准。
