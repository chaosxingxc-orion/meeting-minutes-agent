# E-MATERIAL-NEW-SURFACE-CONFIRMATION

- 负责人：EuphoriaYan
- 状态：`未放行`
- 证据等级：`INDEPENDENT_NEW_SURFACE_CONFIRMATION`
- 类型：sealed confirmation材料语义归属确认
- 开发前置：[开发集runtime gate](E-MATERIAL-NEW-SURFACE-RUNTIME-GATE.md)
- 预注册：[确认预注册](../../readiness/2026-08-26-material-new-surface-confirmation-preregistration.md)

## 研究问题

开发集的正确call材料归属信号能否在40个未打开的confirmation item上，使用冻结构造和阈值0.00
得到确认。

## 冻结设计

顺序执行80个reference-blind Pass0、40场PDF snapshot和320 key + 80 query的encode-only embedding。
预算为80个Omni Pass0 call、1,193.999875音频秒、40,960最大输出token，以及最多25个embedding
batch call。保存80行完整trace和240个向量sidecar；任一前置失败即停止。

确认reader不再选阈值。归属precision≥70%、coverage≥20%、至少24/40场的逐场precision≥50%，
且中位正确减错配余弦≥0.01才判通过。reference、WER和Omni correction均不读取。

## 判读

confirmation Pass0完成80/80，0空输出、0重试，27,724 total tokens；exact-wire结构reader判为
`PASS0_TRACE_COMPLETE`，reference仍未读。

随后零模型PDF snapshot在`ECV-0067`/call `2051550`触发硬停止：绑定PDF共14页，但冻结抽取器
只得到165个字符、6个非空页和0个候选，低于每场8个的门。预注册禁止打开sealed split后再用
OCR、替换材料、修改extractor或降低width，因此snapshot没有落盘，400个confirmation embedding
和唯一reader均未运行。

判为`CONFIRMATION_NOT_RUN_MATERIAL_SNAPSHOT_INSUFFICIENT`。该结果不是语义信号确认失败，而是
确认输入供给不闭合；开发集75%归属结果仍只是开发证据。

- [确认回执](../../checks/2026-08-26-material-new-surface-confirmation/README.md)
