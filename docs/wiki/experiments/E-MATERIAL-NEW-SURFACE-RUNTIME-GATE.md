# E-MATERIAL-NEW-SURFACE-RUNTIME-GATE

- 负责人：EuphoriaYan
- 状态：`开发集已判读`
- 证据等级：`INDEPENDENT_NEW_SURFACE_DEVELOPMENT`
- 类型：同场材料encode-only语义router开发门
- 前置实验：[新surface Pass0](E-MATERIAL-NEW-SURFACE-PASS0.md)
- 预注册：[runtime gate预注册](../../readiness/2026-08-26-material-new-surface-runtime-gate-preregistration.md)

## 研究问题

在reference未读的新surface开发集上，正确call的官方slide候选能否相对等宽错配call形成稳定的
语义优势，并由只依赖本会议top1/top2 gap的selector安全dispatch。

## 冻结设计

先从20个development PDF确定性抽取候选，每场按冻结salt选8个；不足8个立即停止。40个Pass0
输出各形成一个query，answer只允许使用同item较早的reference-audio Pass0作为历史；错配控制按
call_id升序循环右移。Qwen3-Embedding-0.6B最多处理200个embedding、13个batch call。

每个chunk从第一次运行起保存全部正确/错配候选、score、selector、上下文、Pass0 artifact和精确
query/key向量sidecar。开发reader只从冻结trace在六个阈值中选择最低过门值；precision≥70%、
coverage≥20%、至少15/20场有dispatch且中位正确减错配余弦≥0.01才通过。

## 开发集判读

20/20场PDF供给通过：475页抽出3,672个候选，固定为每场8个、共160个key。embedding flight完成
13/13 batch和200/200 embedding，40行前瞻trace经独立validator检查全部Pass0 artifact、候选、
row hash和120个query/correct/deranged向量sidecar，判为`TRACE_COMPLETE`。

开发reader在最低通过阈值0.00得到正确call归属30/40（75%）、覆盖40/40、20/20场有dispatch、
中位正确减错配余弦0.07609，四门全过，判为`DEVELOPMENT_SIGNAL_PRESENT`。阈值0.02的描述性
precision为81.48%、覆盖67.50%，但冻结规则要求最低通过值，不能事后改选。

因此开发集支持“材料语义归属存在”，却没有证明有效拒绝门：冻结阈值0.00会全量dispatch。
开发阶段reference、confirmation和Omni correction均为0。sealed confirmation后来已另行放行，
但在材料snapshot供给门停止；详见[确认实验](E-MATERIAL-NEW-SURFACE-CONFIRMATION.md)。

- [开发集证据回执](../../checks/2026-08-26-material-new-surface-runtime-gate/README.md)
