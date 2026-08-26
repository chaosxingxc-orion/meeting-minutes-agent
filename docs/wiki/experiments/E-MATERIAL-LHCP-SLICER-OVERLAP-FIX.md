# E-MATERIAL-LHCP-SLICER-OVERLAP-FIX

- 负责人：EuphoriaYan
- 状态：`已判读`
- 证据等级：`ENGINEERING_CORRECTION_FROZEN_RTTM`
- 研究问题：能否只修复切片边界，在不重跑Sortformer的情况下消除全部重复音频？
- 唯一允许变化：turn-aware slicer对跨分组重叠turn的打包与最终零重叠post-condition
- 固定因素：25个转换WAV、25个RTTM、`90/60/120/3`秒、16 kHz mono PCM16
- 预注册：[切片器重叠修复预注册](../../readiness/2026-08-26-material-lhcp-slicer-overlap-fix-preregistration.md)
- 修正1：[首次实现失败与原子块修正](../../readiness/2026-08-26-material-lhcp-slicer-overlap-fix-amendment-1.md)
- 最终判决：[切片器重叠修复判决](../../readiness/2026-08-26-material-lhcp-slicer-overlap-fix-verdict.md)

## 预注册策略

按起止时间排序后，将时间上连通的重叠turn合成不可拆分原子块，再按原规则贪心打包。组终点取组内
全部turn的最大终点。多turn原子块若自身超过120秒则失败；只有原有的单个超长turn可用信号/VAD
内部分片。所有slicer模式的最终出口新增相邻切片零重叠硬断言。

只允许在新的D盘目录复用冻结RTTM重新切片，不得覆盖原397片。通过门为25/25输入哈希闭合、全部
切片正时长且不超过120秒、索引连续、相邻重叠不超过`1e-9`秒、文件格式和哈希闭合、纯规划重复
执行确定。全程0 Sortformer、0 reference、0 confirmation、0 Pass0、0 embedding、0 Omni。

## 结果

- 判决：`SLICER_OVERLAP_FIX_PASSED`
- attempt-2：25/25场、396片、37,547.256音频秒、最大120秒、0重叠边界
- 结构复核：`SLICER_OVERLAP_FIX_TRACE_COMPLETE`，0错误
- 普通turn内部切点0；原有单个超长turn例外内部切点4；未覆盖的内部gap为0
- 相比失败manifest：397片变为396片，只有`856696c164`由16片变15片
- 全程：0 Sortformer、0 reference、0 confirmation、0 Pass0、0 embedding、0 Omni

首次实现失败产物继续封存在`attempt-1-failed`，没有aggregate manifest；attempt-2使用新目录，
没有覆盖原证据。该实验只证明固定RTTM可得到确定、无重复、受限的transport供给，不证明说话人
或转写质量。下一步可按396次、37,547.256秒另行注册reference-blind开发Pass0，但尚未授权。
