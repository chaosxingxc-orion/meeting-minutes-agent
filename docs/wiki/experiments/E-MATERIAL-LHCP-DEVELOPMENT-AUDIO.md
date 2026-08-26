# E-MATERIAL-LHCP-DEVELOPMENT-AUDIO

- 负责人：EuphoriaYan
- 状态：`已判读`
- 证据等级：`INDEPENDENT_DEVELOPMENT_AUDIO_PRE_MODEL`
- 类型：25场开发集音频获取与零模型解码审计
- 预注册：[开发音频预注册](../../readiness/2026-08-26-material-lhcp-development-audio-preregistration.md)
- 传输修正：[修正1](../../readiness/2026-08-26-material-lhcp-development-audio-amendment-1.md)
- 判决：[开发音频判决](../../readiness/2026-08-26-material-lhcp-development-audio-verdict.md)

## 研究问题

能否只从冻结的`dev_2020 + dev_2022`读取25场音频，保持45场确认和全部reference未读，并得到
可用于真实Pass0预算的解码时长与文件哈希。

## 冻结边界

只访问6个development Parquet，投影`audio.path`和`audio.bytes`；禁止读取`transcription`或任何
test split。外部音频写到D盘，仓库只保留回执与哈希。本轮不运行Sortformer、切片、Pass0、
embedding或Omni correction。

特别注意：cohort中的历史字段`duration_s`来自Indico议程，实际单位是分钟，不能用于模型预算。
后续只能使用本实验解码所得的真实音频秒数。

第一次获取在完成5个WAV后因一个超大Range响应中断，没有成功回执。修正1只把Range拆为固定
16 MiB子请求，并要求续跑时重新下载的payload与已有WAV逐字节哈希一致；数据列、队列和门不变。

## 结果

- 判决：`LHCP_DEVELOPMENT_AUDIO_ACQUIRED`
- 25/25 WAV，共2,469,998,494 bytes、37,556.965秒（约10.43小时）
- 单场最短1,060.032秒、中位1,491.008秒、最长2,172.032秒
- 14场`dev_2020`、11场`dev_2022`；25个SHA-256全部唯一
- 离线复核：逐文件重哈希与解码，`TRACE_COMPLETE`、0错误
- confirmation/reference/Sortformer/Pass0/embedding/Omni：0/0/0/0/0/0

下一步另行注册固定16 kHz转换、TOOL-LOCKED(B) Sortformer与约90秒turn-aware切片供给审计；不能
直接把10.43小时整会音频作为25次Pass0调用。
