# 阶段性结论

最后更新：2026-08-21。

## 已得到支持的结论

- 固定 diarizer、切片器和预处理后，模型会响应文本实体条件；speaker state 可在不使用 gold 的情况下合法构造。
- Academic/ICSI 有足量 speaker-exclusive 严格技术词代理供给。
- Earnings-22 discovery 有大量同说话人重复的上游标签，但这只是语料筛查结果，不是模型效果。

## 尚未得到支持的结论

- speaker-specific 文本路由没有达到预注册的 +5 pp 实用效应门。
- 当前 `speaker_wrong_disjoint` 策略在低资源独立 pilot 中增加 false hint，不能部署。
- 简单 evidence、recency 或 inventory-width gate 不能同时保留收益与安全。
- Earnings-22 的广义标签由 `CONTRACTION/FALLBACK` 主导，不能直接等同于专业实体。

## 当前研究状态

现阶段已证明“条件信息可影响模型”和“合法供给可构造”，但还没有找到经独立数据确认的安全单步优化算子。因此 training-free agent loop 的单调改进前提尚未满足，E5/E6 继续不放行。

最近的可证伪问题是：在完全未读的 Earnings-22 reserve 上，仅保留 `ABBREVIATION/ALPHANUMERIC` 后，是否仍有足量、低集中度的 speaker-exclusive carry。该问题应先于音频获取和模型 pilot 回答。
