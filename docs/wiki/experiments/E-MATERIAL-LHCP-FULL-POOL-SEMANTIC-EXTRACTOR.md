# E-MATERIAL-LHCP-FULL-POOL-SEMANTIC-EXTRACTOR

## 状态

- 状态：已判读
- 日期：2026-08-28
- 类型：post-reference开发集全池semantic候选抽取
- 依赖：`E-MATERIAL-LHCP-BM25-LOCAL-EXTRACTOR`
- 预注册：[full-pool semantic规则](../../readiness/2026-08-28-material-lhcp-full-pool-semantic-extractor-preregistration.md)

## 问题与预算

BM25 top-8只保留47/206个oracle机会片。本实验冻结4,886个材料key和396个current+prior query，
使用既有Qwen3 embedding做per-meeting余弦排序。总计5,282个embedding，batch 16下最多331次本地
HTTP调用；不调用Omni，不读取新reference或45场confirmation。

主宽度top-8需命中157个机会片并覆盖15场，50片/10场只算探索性。所有输入、runner、reader、
向量和exact-wire回执必须闭合。readiness通过后仍需EuphoriaYan明确授权才能启动embedding server。

## Readiness

reference-blind supply已冻结4,886个key和396个query。模型、server、supply、oracle、runner、reader、
预算、磁盘和one-shot输出目录共22/22项检查通过，判
`LHCP_FULL_POOL_SEMANTIC_READY_AWAITING_AUTHORIZATION`。预算上限为5,282 embeddings、331次
本地HTTP调用；模型接触仍为0。证据见[readiness记录](../../checks/2026-08-28-material-lhcp-full-pool-semantic-extractor/README.md)。

## Flight结果

经明确授权，唯一flight完成331/331批、5,282/5,282个embedding和396行top-16 ranking；0重试，
server已关闭。one-shot reader判`FULL_POOL_SEMANTIC_EXTRACTION_EXPLORATORY_ONLY`。

主宽度top-8命中53/206个oracle机会片（召回25.73%），覆盖23场；它刚超过50片探索门，但远低于
157片主门。top-1/2/4/16分别命中9/17/35/86片。与BM25 current+prior的top-8 47片相比，
semantic只增加6片；top-16增加13片。

## 判决

不启动Omni correction flight，也不解封45场confirmation。全池oracle supply存在，但现有Qwen3
embedding仍无法把它压缩到有功效的窄候选集。若继续，应先研究更强的局部候选表征、音素/别名匹配
或材料页面级定位，并另立开发设计；当前结果不支持事后加宽top-k或用gold选择调用。
