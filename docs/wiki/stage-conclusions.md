# 阶段性结论

最后更新：2026-08-24。

## 已得到支持的结论

- 固定 diarizer、切片器和预处理后，模型会响应文本实体条件；speaker state 可在不使用 gold 的情况下合法构造。
- Academic/ICSI 有足量 speaker-exclusive 严格技术词代理供给。
- Earnings-22 discovery 有大量同说话人重复的上游标签，但这只是语料筛查结果，不是模型效果。
- Earnings-22 未读 reserve 在只保留缩写和字母数字类后仍有264个 speaker-exclusive carry，30/45场 eligible，窄类技术词供给已得到独立确认。
- Earnings-22 官方音频125/125已获取并通过 LFS SHA-256 与解码检查；音频、元数据、对齐参考 ID 完全闭合。
- Earnings-22 全库固定 Sortformer 125/125成功；在30场主讲占主导的 >4 人电话会中，Top-1/Top-2错误为14.30%/22.59%，主讲路由条件可用。
- 4场完整Omni Pass0确认整会内存在13个strict稳定错误簇，覆盖4/4场和70次复现，证明“短片段执行、整会错误簇优化”的供给机制可观测。
- 滑动记忆零模型审计在4/4场找到足量跨窗供给：1424/1429个turn有非空历史关键词记忆，554个turn有同预测speaker跨窗内容词复现；可注册稳定性能力实验。

## 尚未得到支持的结论

- speaker-specific 文本路由没有达到预注册的 +5 pp 实用效应门。
- 当前 `speaker_wrong_disjoint` 策略在低资源独立 pilot 中增加 false hint，不能部署。
- 简单 evidence、recency 或 inventory-width gate 不能同时保留收益与安全。
- Earnings-22 的窄类供给已确认，但这些类别仍是技术词代理，不是语义命名实体，也没有证明模型收益或 false-hint 安全。
- Earnings-22 有116/125场超过4位参考说话人；全库验证推翻了“只看总人数就否决前端”的过强判断，但仍未建立无gold的主讲 eligibility 门或转写收益。
- Sortformer 对长尾 speaker 仍不可用：主讲占主导组的长尾错误72.75%，不能把主讲可用改写成完整说话人分离。
- RTTM-only 主讲门判为 `RUNTIME-DOMINANT-GATE-UNSAFE`：precision 38.60%，且29/57个放行会议的Top-2错误超过40%；稳定预测占比可能只是稳定合并。
- stable-error实验的合法ticker锚点为0，且事后诊断发现9/13 strict错误只是分隔符变体；尚无足量可识别的语义专业词纠错供给。
- 跨窗复现只证明有状态可测，不证明历史内容正确；summary/keyword loop尚未经过Omni多臂验证，GRPO与专业词纠错仍未放行。
- 首个完整滑动记忆实验虽把形式一致率提高11.42点，但未通过错配路由、收敛、WER、最差speaker和错误激活门，判为`LOOP-STABILITY-NOT-REACHED`；广播式recent-tail/长摘要不能作为稳定loop。

## 当前研究状态

现阶段路线仍拆为两层，但第一层首次模型验证已经失败：上下文能强制一致，却同时产生复述、
不收敛和严重WER伤害。第二层training-free GRPO或多模态知识注入继续不放行。若继续第一层，
只能注册新的稀疏per-chunk检索器，删除原文recent-tail与广播式长摘要，不能在本结果上调阈值。

最近的前端问题已经进一步回答：虽然参考已知主讲占主导时固定 Sortformer 可以保住主要主讲，
但仅凭 RTTM 无法安全识别这一子群。后续完整Pass0进一步确认stable exact-form错误存在，却没有
合法term锚点，而且多数是排版变体。因此term Pass1继续不放行。新发现的一场集中输出语言漂移
可作为独立可控性旁路，但必须与speaker-term主结论隔离。
