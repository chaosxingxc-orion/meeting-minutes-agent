# E-MATERIAL-LHCP-DEVELOPMENT-QUERY-SUPPLY

## 状态

- 状态：已判读
- 日期：2026-08-28
- 类型：零模型材料候选与逐片查询供给冻结
- 依赖：`E-MATERIAL-LHCP-DEVELOPMENT-PASS0`
- 预注册：[2026-08-28-material-lhcp-development-query-supply-preregistration](../../readiness/2026-08-28-material-lhcp-development-query-supply-preregistration.md)

## 问题

既有同期材料候选池与396条Pass0输出，能否形成等宽、可错配、严格因果且不读取reference的逐slice
检索供给？本实验只回答输入是否完整合法，不回答语义检索能否选对材料，也不回答转写是否改善。

## 冻结设计

复用已有候选池，不重新解析PDF。每场按固定salt选择8个候选，保留原文档相对路径、页码和原文跨度；
25场共200个key。按meeting ID排序后循环右移一位，形成无固定点、等候选数的错配控制。

每条query只含当前Pass0文本、当前Sortformer说话人标签，以及同会紧邻前一片最多8个关键词；首片无历史，
不得读取未来片、其他会议、reference或45场confirmation。position 301保留并标注潜在截断，不重听。

## 放行边界

只有25场、200个候选、396条query全部通过顺序、哈希、因果、泄漏与错配审计，才可判
`LHCP_DEVELOPMENT_QUERY_SUPPLY_READY`。即使通过，也只允许另行注册embedding runtime；本实验的
模型调用预算为0。

## 结果

判为`LHCP_DEVELOPMENT_QUERY_SUPPLY_READY`。25/25场共提供4,886个候选，每场最少16、中位134；
固定选择200个key（每场8个）。396/396条query按Pass0顺序闭合，其中371条只使用同会紧邻前一片
的关键词，25条首片无历史；query最长2,546字符。错配映射是无固定点双射，正确与错配侧始终各8个key。

泄漏与执行审计均为0错误：reference、confirmation、embedding与Omni接触均为`NONE`，未出现禁止字段。
position 301是唯一潜在截断项并已标记。机器判读与外部产物哈希见[检查记录](../../checks/2026-08-28-material-lhcp-development-query-supply/README.md)。

## 结论与下一门

当前已经具备可重放、等预算的语义归属输入，可另行冻结200个key和396个query的embedding runtime，
预算上限为596个embedding、按batch 16最多38次请求。该放行不等于检索有效：133条query含多个
说话人标签，且候选仍是会议级材料；下一实验首先只测正确会议材料是否稳定胜过错配材料，不直接宣称
说话人定向纠错或WER收益。
