# E-MATERIAL-LHCP-FULL-POOL-CEILING

## 状态

- 状态：已判读
- 日期：2026-08-28
- 类型：post-reference开发集原始材料候选池oracle上限
- 依赖：`E-MATERIAL-LHCP-LOCAL-CANDIDATE-CEILING`
- 模型接触：0
- 预注册：[full-pool ceiling规则](../../readiness/2026-08-28-material-lhcp-full-pool-ceiling-preregistration.md)

## 问题与设计

现有8个key按salted hash抽样，不代表局部相关候选。当前实验扫描25场development的原始4,886个
材料候选，在同一整会对齐和两侧12词窗口下，统计每片是否至少存在一个reference有而Pass0没有的
canonical，并报告类别与词长分层。

157机会片/15场通过主门，50片/10场只通过探索门。全池仍不足则停止LHCP材料候选纠错分支；
全池充足而8-key不足，则下一工程目标是reference-blind局部候选抽取器。该结果使用已经打开的
development reference，只是描述性oracle上限；45场confirmation继续sealed。

## 结果与判决

reader检查81,634个slice-candidate组合，得到416个候选级wrong-to-correct机会、300个不同候选。
合并到切片后为206/396个机会片（52.02%），覆盖25/25场；379/396片至少有一个局部支持候选。
157片/15场主门全部通过，判`LHCP_FULL_MATERIAL_POOL_POWER_READY`。

机会中单词候选316个、两词68个、三词23个、四词9个；因此source coverage充足不等于安全选择。
与8-key的39片上限相比，主要损失来自salted hash候选抽取。下一步冻结reference-blind的BM25/top-k
零模型抽取诊断；只有其候选召回与局部支持安全均足够，才申请全池embedding或Omni。

证据见[检查记录](../../checks/2026-08-28-material-lhcp-full-pool-ceiling/README.md)。
