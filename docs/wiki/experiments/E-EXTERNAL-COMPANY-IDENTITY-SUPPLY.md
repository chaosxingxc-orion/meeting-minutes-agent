# E-EXTERNAL-COMPANY-IDENTITY-SUPPLY

- 负责人：EuphoriaYan
- 状态：`已注册`
- 类型：零模型、外部公司身份供给审计

该实验检查四场冻结 Earnings-22 会议的 ticker→公司品牌名映射，能否为短片段提供准确、独立的
纠错候选。证据面只包含 `Jeronimo Martins`、`TeamViewer`、`Galp`/`Galp Energia` 和
`SK Telecom`，不引入产品、人员或财务事实。Pass0 近似词形负责触发；参考转写只在一次性
reader 中判定目标区间是否真的提到公司身份。

该来源当前标记为 `PROPOSED_EXTERNAL_PUBLIC_REGISTRY`，不是随会议材料 M0。即使零模型门通过，
也只能进入来源准入决策，不能直接启动模型实验。别名、0.75 阈值、输入哈希和判决门已经冻结，
判读后不得在同一结果上调参。

- [预注册](../../readiness/2026-08-24-external-company-identity-supply-preregistration.md)
- [冻结配置](../../../configs/probes/external_company_identity/2026-08-24-registry.json)
