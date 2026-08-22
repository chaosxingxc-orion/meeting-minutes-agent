# 阶段性结论

最后更新：2026-08-21。

## 已得到支持的结论

- 固定 diarizer、切片器和预处理后，模型会响应文本实体条件；speaker state 可在不使用 gold 的情况下合法构造。
- Academic/ICSI 有足量 speaker-exclusive 严格技术词代理供给。
- Earnings-22 discovery 有大量同说话人重复的上游标签，但这只是语料筛查结果，不是模型效果。
- Earnings-22 未读 reserve 在只保留缩写和字母数字类后仍有264个 speaker-exclusive carry，30/45场 eligible，窄类技术词供给已得到独立确认。

## 尚未得到支持的结论

- speaker-specific 文本路由没有达到预注册的 +5 pp 实用效应门。
- 当前 `speaker_wrong_disjoint` 策略在低资源独立 pilot 中增加 false hint，不能部署。
- 简单 evidence、recency 或 inventory-width gate 不能同时保留收益与安全。
- Earnings-22 的窄类供给已确认，但这些类别仍是技术词代理，不是语义命名实体，也没有证明模型收益或 false-hint 安全。

## 当前研究状态

现阶段已证明“条件信息可影响模型”和“合法供给可构造”，但还没有找到经独立数据确认的安全单步优化算子。因此 training-free agent loop 的单调改进前提尚未满足，E5/E6 继续不放行。

最近的供给问题已经回答：Earnings-22 窄类 reserve 通过。下一决策是音频许可和最小 acquisition 是否可行；在音频治理解决前不启动 Earnings-22 模型 pilot。若治理失败，则优先使用已有本地音频的 Academic/ICSI 设计。
