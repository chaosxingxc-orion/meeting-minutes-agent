# E-MATERIAL-LHCP-LOCAL-CANDIDATE-CEILING

## 状态

- 状态：已判读
- 日期：2026-08-28
- 类型：post-reference开发集描述性候选上限审计
- 依赖：`E-MATERIAL-LHCP-DEVELOPMENT-OPPORTUNITY-POWER-AUDIT`
- 模型接触：0
- 预注册：[全候选局部机会规则](../../readiness/2026-08-28-material-lhcp-local-candidate-ceiling-preregistration.md)

## 问题

前一实验只在396个semantic top1中找到12个可纠错机会。当前实验检查每片完整的8个本会议候选，
判断失败主要来自top1路由，还是材料候选池本身缺少当前片段所需实体。

## 设计与边界

复用已经打开的25场development reference、396行semantic trace和每行8个冻结候选；沿用整会
SequenceMatcher对齐和两侧12词窗口。逐候选统计retain、wrong-to-correct与unsupported，并报告
逐片oracle机会、候选semantic rank和top1捕获率。

达到157个机会片/15场才具主实验供给，50片/10场只算探索性；低于该门则停止router优化，优先
修复候选抽取。因为development reference已经打开，本实验只能提供描述性oracle ceiling，不能
形成新策略的独立验证，也不得按gold选择未来模型调用。45场confirmation保持sealed。

## 结果与判决

reader复现了上一实验的12个top1机会。扩展到完整8候选后，共检查3,168个候选对，得到44个
candidate-level机会；合并到切片后为39/396个机会片，覆盖14场。它低于50片探索门，也远低于
157片主门，判`LHCP_LOCAL_CANDIDATE_POOL_INSUFFICIENT`。

semantic top1只捕获12/39个oracle机会片（30.77%），因此router确有损失；但完美oracle最多也只
覆盖9.85%的切片。当前主要瓶颈是随机宽度8候选抽取，而不是top1 router。停止在这8个key上调
阈值或训练free策略搜索；下一步应检查原始4,886候选池的局部oracle上限，再决定是否重做抽取。

证据见[检查记录](../../checks/2026-08-28-material-lhcp-local-candidate-ceiling/README.md)。
