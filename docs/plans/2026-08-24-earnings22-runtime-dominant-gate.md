# Earnings-22 运行时主讲 cluster 门控审计

日期：2026-08-24
状态：**已判读：`RUNTIME-DOMINANT-GATE-UNSAFE`**

## 问题与边界

固定 Sortformer 在参考 Top-2 占主导的 30 场会议上保住了主要说话人，但运行时不能读取参考
说话人数、参考发言占比或转写答案。本实验复用已经冻结的 125 份 RTTM，不调用模型，只判断
能否从预测 cluster 的整会占比和跨时间稳定性识别适合进入后续转写 loop 的会议。

执行单元仍是固定短片段；门控、状态更新、验收和回滚的统计单元是整场会议。该审计不放行
选择性重听，也不评价长尾 speaker。

## 冻结门控

将会议划成从 0 秒开始的固定 600 秒窗。有效窗含至少 30 秒预测语音。按 RTTM 累计每个
cluster 的发言时长，取整会 Top-2 cluster。会议仅在以下条件全部成立时放行：

1. 预测语音总量至少 300 秒；
2. 整会 Top-2 占预测语音至少 60%；
3. 同一 Top-2 组合在至少 80% 的有效窗内占预测语音至少 60%；
4. 两个 Top cluster 都至少在 3 个有效窗中出现。

窗口内重叠按各 cluster 时长分别累计；分母为各 cluster 时长之和。阈值不按结果搜索。

## 一次性判读

主审计集合沿用上一实验的 `aligned_token_fraction >= 0.8`、`aligned_word_seconds >= 300`
且参考说话人数大于 4 的会议。参考只在门控结果冻结后用于评分。

门控判为 `RUNTIME-DOMINANT-GATE-USABLE` 必须同时满足：放行至少 15 场；对参考 Top-2
占比至少 60% 的 precision 不低于 70%、recall 不低于 60%；放行集合时长加权 Top-1/Top-2
归属错误分别不高于 20%/25%；逐会议 Top-2 错误超过 40% 的比例不高于 10%。覆盖不足判为
`INSUFFICIENT-RUNTIME-SUPPLY`，其余失败判为 `RUNTIME-DOMINANT-GATE-UNSAFE`。

若通过，下一步才预注册小型 Omni Pass-0；若失败，不能用 reference dominance 挑选会议，
必须寻找独立元数据或先做无需该门控的保守设计。
