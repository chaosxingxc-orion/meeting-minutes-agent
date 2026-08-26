# E-MATERIAL-LHCP-ELIGIBLE-COHORT

- 负责人：EuphoriaYan
- 状态：`已判读`
- 证据等级：`INDEPENDENT_PRE_MODEL_ELIGIBILITY_FILTERED`
- 类型：模型接触前的材料兼容性队列冻结
- 预注册：[队列预注册](../../readiness/2026-08-26-material-lhcp-eligible-cohort-preregistration.md)
- 判决：[队列判决](../../readiness/2026-08-26-material-lhcp-eligible-cohort-verdict.md)
- 回执：[材料供给与队列冻结回执](../../checks/2026-08-26-material-lhcp-supply/README.md)

## 研究问题

能否只依据冻结的零模型材料门，把70场可读报告冻结为25场开发和45场一次确认，同时保持reference
与模型结果未读。

## 冻结规则

只排除`856696c36.wav`与`856696c52.wav`；原因是固定parser在模型接触前失败，不涉及reference或
模型效果。保留14场`dev_2020`、11场`dev_2022`、13场`test_2020`和32场`test_2022`。不得修复、
OCR、替换或把两场重新纳入本队列。

本实验只冻结队列，不授权Pass0、embedding、Omni或reference读取。后续结论只能外推到70场
material-compatible子群，不能声称覆盖完整72场release。

## 结果

- 判决：`LHCP_70_TALK_ELIGIBLE_COHORT_FROZEN`
- 数量：70场eligible；25场开发；45场一次确认；2场排除
- split：`dev_2020=14`、`dev_2022=11`、`test_2020=13`、`test_2022=32`
- 离线复核：`TRACE_COMPLETE`，0错误
- reference/Pass0/embedding/Omni：0/0/0/0
- 完整离线回归：1,591 passed、25 skipped

下一步只能另行注册70场队列上的开发集模型实验，冻结runtime、预算和reader后再申请模型授权；
45场确认在开发选择完成前保持sealed。
