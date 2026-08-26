# E-MATERIAL-LHCP-ADMISSION

- 负责人：EuphoriaYan
- 状态：`已判读`
- 证据等级：`ZERO_MODEL_METADATA_ADMISSION`
- 类型：独立surface的元数据对齐与材料覆盖审计
- 预注册：[准入预注册](../../readiness/2026-08-26-material-lhcp-admission-preregistration.md)
- 判决：[准入判决](../../readiness/2026-08-26-material-lhcp-admission-verdict.md)
- 回执：[机器回执](../../checks/2026-08-26-material-lhcp-admission/README.md)

## 研究问题

72场reference-unread的LHCP-ASR评估报告能否与CERN官方contribution一一对齐，并且每场都存在
同期PDF/PPT/PPTX材料。

## 冻结边界

只允许投影HF的split与`audio.path`，以及CERN contribution和附件元数据；CERN JSON传输中的其他字段
不得持久化、打印或参与join。禁止读取转写、音频字节、slide正文、OCR结果或任何模型输出。必须
72/72唯一对齐、0孤儿、0歧义且72/72有非空材料附件；
不允许模糊匹配、人工补配或读后增加别名。

## 判读

判为`LHCP_METADATA_JOIN_AND_MATERIAL_COVERAGE_CLOSED`。72条HF音频路径全部通过`event_id +
friendly_id`精确命中72个不同CERN contribution，0孤儿、0歧义。72/72场有同期材料，共77个唯一
附件（74 PDF、3 PPTX），77/77下载端点通过不读取正文的Range响应头检查。

本次只从6.25 GiB远端Parquet投影`audio.path`，实际传输1,116,237 bytes；reference、音频正文、
材料正文、Pass0、embedding与Omni均为0。该结果只放行另行注册的材料可读性和候选供给审计，
不证明材料能被提取、能正确归属或能改善转写。

后续`E-MATERIAL-LHCP-SUPPLY`已完成：77/77附件取得，但冻结解析器仅使70/72场通过；严格供给门
失败，不能启动模型flight。
