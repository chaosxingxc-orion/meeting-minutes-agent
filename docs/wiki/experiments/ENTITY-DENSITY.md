# ENTITY-DENSITY：语料实体密度审计

- 状态：`已判读`
- 类型：CPU 统计，零模型接触

AMI 的 annotation-grounded proper-noun token share 仅 0.22%，每场可被 glossary 重复利用的专业名词很少，不适合单独承担供给增益验证。ContextASR-Dialogue 有高实体密度，适合做“模型是否会读取正确/错误实体提示”的能力探针，但单 episode 复现率有限。Earnings21 的 proper-name repeat payoff share 为 0.578，更适合测试会议/说话人状态从首次出现到后续片段的复用收益。

因此：C-CTX 用 ContextASR 验证供给能力；后续 E3/E4 若验证自建词表和 speaker state，应优先评估 Earnings21，而不是从 AMI 低密度结果推导不可优化。

- [完整统计与定义](../../readiness/2026-08-17-entity-density-census.md)
