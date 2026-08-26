# E-MATERIAL-NEW-SURFACE-ADMISSION

- 负责人：EuphoriaYan
- 状态：`已判读`
- 证据等级：`INDEPENDENT_NEW_SURFACE`
- 类型：零模型新语料准入与前瞻trace基础设施
- 预注册：[准入预注册](../../readiness/2026-08-26-material-new-surface-admission-preregistration.md)
- 选源记录：[新surface选源](../../readiness/2026-08-26-material-new-surface-source-selection.md)
- 冻结配置：[准入配置](../../../configs/probes/material_new_surface/2026-08-26-admission.json)
- Trace合同：[逐chunk trace schema](../../../configs/probes/material_new_surface/2026-08-26-dispatch-trace.schema.json)
- 判读：[准入判决](../../readiness/2026-08-26-material-new-surface-admission-verdict.md)

## 研究问题

能否建立一个参考未读、音频与精确转写成对、又可关联同场官方材料的新短片段surface，并从
Pass0开始前瞻性保存足以重放selector与三臂输入的完整trace。

## 冻结设计

候选将EarningsCallVoice Core-100与FinCall-Surprise按`call_id`连接。前者提供经过九项人工
质量门的真实prepared/answer短音频和精确参考，后者提供整场电话会身份及同期slide。网页预览
已暴露`ECV-0001`的文本，因此在抽样前永久排除。为控制资源，本轮只取2019与2020：排除前70条，
目标冻结20条开发、40条一次确认和9条保留；2021不下载。

参考文本字段在reader冻结前不得打印、总结、分词或embedding。原始音频、PDF、prompt、response、
候选表和向量sidecar都留在`D:/datasets`，Git只保存schema、队列、哈希与回执。

## 完整trace要求

每个chunk必须保存Pass0原始请求/响应、实际转写、speaker与窗口输入、query、正确会议和错配会议的
全部候选/value/score、top-1/top-2、gap、阈值、dispatch、精确query/key向量sidecar以及所有
artifact哈希。写入为append-only并`fsync`；缺字段、重复turn、分数或判决不一致、错配会议等于
本会议、文件或向量哈希不符时一律fail closed。

## 判读

69/69个范围内非暴露候选通过全部准入门，冻结为20开发、40一次确认、9保留，判为
`NEW_SURFACE_COHORT_FROZEN`。外部快照包含138个WAV（65,228,466 bytes）与69个同场PDF
（117,765,681 bytes）。0 Pass0、0 embedding、0 Omni、0语义参考读取。

该判决只放行另行注册的开发集Pass0与前瞻trace运行，不授权直接读取参考、拟合确认集、运行Omni
或宣称完整会议泛化。

- [准入回执](../../checks/2026-08-26-material-new-surface-admission/README.md)
