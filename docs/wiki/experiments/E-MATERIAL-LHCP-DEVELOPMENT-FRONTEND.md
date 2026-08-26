# E-MATERIAL-LHCP-DEVELOPMENT-FRONTEND

- 负责人：EuphoriaYan
- 状态：`已判读`
- 证据等级：`INDEPENDENT_DEVELOPMENT_FIXED_FRONTEND`
- 类型：开发集固定Sortformer与turn-aware切片供给
- 预注册：[固定前端预注册](../../readiness/2026-08-26-material-lhcp-development-frontend-preregistration.md)
- readiness：[零模型readiness判决](../../readiness/2026-08-26-material-lhcp-development-frontend-readiness-verdict.md)
- 最终判决：[固定前端判决](../../readiness/2026-08-26-material-lhcp-development-frontend-verdict.md)

## 研究问题

冻结的25场开发音频能否经现有TOOL-LOCKED(B)前端，生成完整、可哈希、最长120秒的说话人标注
transport slices，为后续Pass0/material-routing提供精确调用预算。

## 固定运行

所有音频先统一为16 kHz mono PCM16，再以固定Q8 Sortformer默认DiarStream运行25次。RTTM只作
M0 `tool-diar`边界，切片使用`90/60/120/3`秒、零重叠。不得读取reference、confirmation或材料
效果，不得基于前端输出替换会议。

EuphoriaYan已明确放行本次固定Sortformer flight。Pass0不在本实验授权范围内。

## 运行与判读结果

- 工具执行：25/25 Sortformer成功，25个非空RTTM，0重试、0换场、0参数修改
- 结构回执：397个切片及全部哈希闭合，`FRONTEND_TRACE_COMPLETE`
- 最终门控：`FRONTEND_SLICE_ZERO_OVERLAP_GATE_FAILED`
- 失败量：15个相邻边界重叠，影响10/25场，合计35.900秒，最大14.948秒
- 根因：Sortformer允许重叠说话；现有turn-aware分组边界未规范跨组重叠turn
- 全程：0 reference、0 confirmation、0 Pass0、0 embedding、0 Omni

预构建reader漏检零重叠门，已单独登记缺陷；它的`TRACE_COMPLETE`只表示产物完整，不能覆盖实验
失败。不得启动Pass0，也不得重跑Sortformer。下一步只能另行注册切片器重叠边界修复实验，并在
冻结RTTM上生成新的、不可替换本次失败证据的切片manifest。
