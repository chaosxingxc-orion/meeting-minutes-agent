# E-MATERIAL-LHCP-DEVELOPMENT-PASS0

## 状态

- 状态：已判读
- 日期：2026-08-28
- 输入：25场开发会议、396个修复后切片、37,547.256音频秒
- 预注册：[2026-08-28-material-lhcp-development-pass0-preregistration](../../readiness/2026-08-28-material-lhcp-development-pass0-preregistration.md)

## 问题

固定 Omni 核心能否按切片清单顺序完成396次纯音频 Pass0，并保存可重放的 exact-wire trace？
本实验只回答 trace 是否完整，不回答 WER、说话人区分能力、专业词增益或 agent loop 效果。

## 冻结设计

输入固定为 SHA-256
`1224f0951c6b255523197974368c54e73fd27c4a9b328bf5c909eaf226d695ce`
的修复清单。每片最多一次调用，单 slot、零重试；prompt 不提供说话人标签、RTTM turn表、历史文本、
参考转写、材料或术语。预算为396 calls、37,547.2558125音频秒和202,752最大输出token。
请求、响应、索引和receipt写入D盘外部目录，仓库只保存冻结配置、readiness和后续结构读出。

清单秒数是计划边界上限；12个会议尾片因源音频结束短16--80毫秒，WAV帧实计为37,546.6638125秒。
runtime同时冻结两者，调用预算使用较大的清单上限，不把正常尾端截断当作缺片。

## 结果

readiness先完成21/21检查，随后经EuphoriaYan明确授权运行唯一flight。reference-blind reader判为
`PASS0_TRACE_COMPLETE`：25/25场、396/396响应、0空输出、0重试，exact-wire request、response、
runtime、index和receipt哈希全部闭合。总墙钟15,379.128秒，使用527,747 prompt tokens、113,459
completion tokens、641,206 total tokens；reference、材料与confirmation访问均为`NONE`。

395条响应以`stop`结束；position 301（`1109611c537` slice 13）以`length`结束并用满512 tokens。
因此trace完整性通过，但该片后续质量判读必须标记为潜在截断，不能把结构通过改写成全片内容完整。

机器回执见[实验检查](../../checks/2026-08-28-material-lhcp-development-pass0/README.md)。

## 后续

本实验只放行下一项零模型工作：冻结25场同期材料候选、确定性错配映射和逐slice查询供给。
reference评分、材料检索模型、embedding和任何 correction arm必须另行注册，不能在本实验中追加。
