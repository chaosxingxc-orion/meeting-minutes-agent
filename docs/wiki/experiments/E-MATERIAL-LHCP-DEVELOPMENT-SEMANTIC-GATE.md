# E-MATERIAL-LHCP-DEVELOPMENT-SEMANTIC-GATE

## 状态

- 状态：开发集已判读
- 日期：2026-08-28
- 类型：开发集encode-only材料语义归属门
- 依赖：`E-MATERIAL-LHCP-DEVELOPMENT-QUERY-SUPPLY`
- 预注册：[语义归属门预注册](../../readiness/2026-08-28-material-lhcp-development-semantic-gate-preregistration.md)

## 问题

对396个逐片query，正确会议的8个官方材料key能否稳定胜过等宽错配会议？本实验只测会议材料归属
信号，不读取reference、不测WER、不调用Omni correction，也不把会议级材料解释为speaker-exclusive证据。

## 冻结设计

模型固定为SHA-256
`06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439`的
Qwen3-Embedding-0.6B-Q8_0，float32 L2归一化。200个key与396个query共596次embedding，batch 16，
最多38次HTTP请求，零重试。逐片保存正确/错配全候选分数、selector、Pass0绑定和三类向量sidecar。

reader在0.00--0.05六个阈值中选择最低过门值；precision至少70%、coverage至少20%、至少19/25场
被覆盖且中位正确减错配余弦至少0.01。错配分数只供reader使用，不能进入运行时selector。

## 放行边界

通过只证明开发集存在会议材料语义归属信号，最多允许另立correction能力实验。若失败，停止在同一
trace上调候选、query或阈值。45场confirmation在开发选择完成前继续sealed。

## 执行与结果

readiness为25/25通过；E盘未接入后，从冻结revision把同一Qwen3-Embedding模型恢复到D盘，
639,150,592字节及SHA-256均闭合。唯一flight完成38/38 batch、596/596 embedding，保存396行trace
和1,188个向量sidecar。独立validator逐项复核向量、query、候选、Pass0 request/response及哈希，判
`TRACE_COMPLETE`，0错误。

one-shot reader判`LHCP_DEVELOPMENT_SEMANTIC_SIGNAL_PRESENT`。按“最低过门阈值”规则选择0.00：
正确会议胜错配359/396，precision 90.66%，coverage 100%，覆盖25/25场，中位余弦优势0.11701；
四门全部通过。0.01--0.05也描述性过门，但不得事后替换注册选择。

## 边界与异质性

结果不是逐会均匀成功：`856696c53`仅8/19（42.11%，中位差-0.01168），`1109611c551`为9/14
（64.29%）。多说话人标签query的归属precision为88.72%，仍只能说明会议材料身份信号；候选不是
speaker-exclusive。无历史首片为24/25，而有前片关键词为335/371，因此本实验也不能单独证明历史
关键词带来增益。

机器记录见[实验检查](../../checks/2026-08-28-material-lhcp-development-semantic-gate/README.md)。
当前只放行“另行设计correction能力实验或先做reference opportunity/power audit”的决策，不自动
解封reference、confirmation或Omni。
