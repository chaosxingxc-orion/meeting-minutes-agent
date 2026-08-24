# E4-XDOMAIN-AUDIO-ADMISSION：Earnings-22 音频入库

- 负责人：EuphoriaYan
- 状态：`已判读`
- 类型：零模型、音频完整性与固定前端适配诊断
- 模型调用：0

官方固定版本的125个 MP3 已全部下载到外部数据根，共1,908,056,329字节，逐文件
Git LFS SHA-256 全部匹配；音频、元数据、对齐参考三方 ID 125/125/125 零缺口，且全部
可由 `ffprobe` 打开。

预注册 verdict 为 `EARNINGS22-AUDIO-NOT-ADMITTED`：上游 `metadata.csv` 有9个时长差
超过2秒，总时长相对差0.7847%，最大差2691.512秒。对齐参考的结束时间与 MP3 一致，
支持“CSV 元数据错误”诊断，但不能事后改写冻结 verdict。

固定前端适配风险更实质：参考诊断显示116/125场超过4位说话人，而锁定 Sortformer
最多4位。兼容子集只有9场（5 discovery、4 reserve），不可能满足既有20场 eligible 门。
因此暂不启动 Omni pilot；下一步需在“停止 Earnings-22 路线”和“另行注册不限人数的
固定前端 smoke”之间决策。参考说话人数不得用于逐会议运行时路由。

后续状态：2026-08-24 的[全库 Sortformer 验证](EARNINGS22-SORTFORMER.md)已直接检验
“超过4人但主讲占主导”的情形，证明总人数并非充分否决条件；30场主讲目标组条件可用，
但长尾仍不可用。本页保留的是 acquisition 当时的门与决策，不再代表最新前端结论。

- [预注册](../../readiness/2026-08-22-earnings22-audio-admission-preregistration.md)
- [入库收据与诊断](../../checks/2026-08-22-earnings22-audio-admission/README.md)
- [机器 verdict](../../checks/2026-08-22-earnings22-audio-admission/verdict.json)
