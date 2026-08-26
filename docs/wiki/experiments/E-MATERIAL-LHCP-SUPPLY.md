# E-MATERIAL-LHCP-SUPPLY

- 负责人：EuphoriaYan
- 状态：`已判读`
- 证据等级：`INDEPENDENT_ZERO_MODEL_MATERIAL_SUPPLY`
- 类型：材料可读性与候选供给审计
- 依赖：`E-MATERIAL-LHCP-ADMISSION`
- 预注册：[供给预注册](../../readiness/2026-08-26-material-lhcp-supply-preregistration.md)
- 修正1：[非法Unicode传输修正](../../readiness/2026-08-26-material-lhcp-supply-amendment-1.md)
- 判决：[供给判决](../../readiness/2026-08-26-material-lhcp-supply-verdict.md)
- 回执：[机器回执](../../checks/2026-08-26-material-lhcp-supply/README.md)

## 研究问题

已经完成72/72元数据准入的LHCP-ASR材料，是否都能被固定工具解析，并为每场提供至少8个专业词面候选。

## 冻结设计

下载已登记的77个CERN附件到D盘并逐个校验size、MD5和本地SHA-256；所有附件都在抽样前纳入。
PDF使用`pypdf`，PPTX只读slide XML；候选提取复用仓库既有确定性规则。每场必须至少有1个可读文档、
200个可见字符和8个唯一候选，72/72全部通过才放行下一步。不使用OCR、人工别名、替换会议或读后修补。

该实验保持0 reference、0音频下载、0 Pass0、0 embedding、0 Omni。

## 执行记录

77/77附件已下载并通过size、MD5与本地SHA-256。第一次解析在写外部JSONL时因PDF提取结果含孤立
`U+D835`而停止，未产出或读取任何聚合结果；部分文件已移至独立失败目录并绑定哈希。修正1只把
非法surrogate替换为`U+FFFD`，不改变文档、候选规则或门，第二次运行使用新目录。

## 判读

判为`LHCP_ZERO_MODEL_MATERIAL_SUPPLY_INSUFFICIENT`。77/77附件下载与checksum闭合，但冻结解析器
只使70/72场通过；开发25/25、确认45/47。失败项`856696c36.wav`和`856696c52.wav`均为
`test_2020`单PDF，分别在第2页和第18页触发`pypdf LimitReachedError`，产生0字符、0候选。

其余70场供给充足：每场候选最小16、中位142，明显高于8候选门。但原注册要求72/72，因此不能
启动模型flight。下一步须在“冻结70场eligible cohort”与“另立全量备用parser实验”之间决策。
