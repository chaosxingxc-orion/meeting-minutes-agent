# E-EXTERNAL-COMPANY-IDENTITY-SUPPLY

- 负责人：EuphoriaYan
- 状态：`已判读`
- 类型：零模型、外部公司身份供给审计

该实验检查四场冻结 Earnings-22 会议的 ticker→公司品牌名映射，能否为短片段提供准确、独立的
纠错候选。证据面只包含 `Jeronimo Martins`、`TeamViewer`、`Galp`/`Galp Energia` 和
`SK Telecom`，不引入产品、人员或财务事实。Pass0 近似词形负责触发；参考转写只在一次性
reader 中判定目标区间是否真的提到公司身份。

一次性判读发现：参考区间共36次公司身份提及，Pass0有25个turn输出了精确词形，只剩15个纠错机会；冻结
触发器命中5个并误触发3个，precision 62.5%、recall 33.3%，仅Galp一场达到逐会分布门。
即使假设完美触发，15个机会仍低于20个总量门，因此该分支判为
`EXTERNAL-COMPANY-IDENTITY-SUPPLY-INSUFFICIENT`，不启动模型flight、不调别名或阈值。

该来源继续标记为 `PROPOSED_EXTERNAL_PUBLIC_REGISTRY`，不是随会议材料 M0。结果只否定每场一个
公司身份的稀疏证据面，不否定更丰富、与会议同时可得的独立材料。

- [预注册](../../readiness/2026-08-24-external-company-identity-supply-preregistration.md)
- [冻结配置](../../../configs/probes/external_company_identity/2026-08-24-registry.json)
- [正式判读](../../checks/2026-08-24-external-company-identity-supply-read/README.md)
- [阶段结论](../../readiness/2026-08-24-external-company-identity-supply-verdict.md)
