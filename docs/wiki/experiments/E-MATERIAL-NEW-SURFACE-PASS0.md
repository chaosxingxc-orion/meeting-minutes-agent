# E-MATERIAL-NEW-SURFACE-PASS0

- 负责人：EuphoriaYan
- 状态：`已判读`
- 证据等级：`INDEPENDENT_NEW_SURFACE_DEVELOPMENT`
- 类型：开发集reference-blind Omni Pass0与完整原始trace
- 前置实验：[新surface准入](E-MATERIAL-NEW-SURFACE-ADMISSION.md)
- 预注册：[Pass0预注册](../../readiness/2026-08-26-material-new-surface-pass0-preregistration.md)
- 冻结runtime：[开发集runtime](../../../configs/probes/material_new_surface/2026-08-26-pass0-development-runtime.json)

## 研究问题

冻结Omni能否在不读取参考、不注入材料或speaker文本的条件下，为新surface的20个开发item、
40段短音频生成Pass0，并从第一次调用起保存可验证的精确HTTP请求、原始响应和顺序索引。

## 冻结设计

只运行development split；confirmation与reserve继续封存。固定`transcribe-only-v1`、
`temperature=0`、`seed=0`、`max_tokens=512`、单slot和零重试。硬预算为40 calls、592.05音频秒、
20,480最大输出token。每次调用前后分别落盘并`fsync`精确request/response，随后append-only写索引；
任何哈希漂移、孤儿artifact、非前缀恢复或请求失败都立即停止。

预构建reader只判结构完整性和reference firewall，不查看gold，也不计算WER。通过只意味着
`PASS0_TRACE_COMPLETE`，不意味着模型转写准确、材料检索有效或agent loop可优化。

## 判读

冻结flight完成40/40调用，0空输出、0重试；结构reader验证了全部顺序、artifact、音频、prompt、
decoding、响应文本、usage和receipt绑定，判为`PASS0_TRACE_COMPLETE`。总用量为11,780 prompt、
2,017 completion、13,797 total tokens；精确请求25,285,676 bytes，原始响应38,076 bytes。

整个判读保持`reference_access=NONE`，因此目前只证明开发集Pass0与前瞻trace完整，不证明转写准确。
下一步另行冻结同场PDF候选抽取、错配会议映射和encode-only embedding runtime；确认集继续封存。

- [结构回执](../../checks/2026-08-26-material-new-surface-pass0/README.md)
