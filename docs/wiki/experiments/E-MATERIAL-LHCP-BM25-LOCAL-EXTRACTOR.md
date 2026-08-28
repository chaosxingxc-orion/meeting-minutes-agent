# E-MATERIAL-LHCP-BM25-LOCAL-EXTRACTOR

## 状态

- 状态：已判读
- 日期：2026-08-28
- 类型：post-reference开发集reference-blind候选抽取发现
- 依赖：`E-MATERIAL-LHCP-FULL-POOL-CEILING`
- 模型接触：0
- 预注册：[BM25抽取规则](../../readiness/2026-08-28-material-lhcp-bm25-local-extractor-preregistration.md)

## 问题与设计

全池oracle有206个机会片，但运行时必须从每场数百个候选缩到小集合。本实验对canonical加三倍词重，
拼接固定source span，使用`k1=1.2/b=0.75`的per-meeting BM25。分别冻结`current_only`和
`current_plus_prior`查询，报告top-1/2/4/8/16中的机会命中。

主宽度top-8至少保留157机会片并覆盖15场才通过主门；50片/10场只算探索性。gold只用于
one-shot评价，不参与ranking。通过也只提名后续embedding候选池，不授权embedding或Omni；45场
confirmation保持sealed。

## 结果与判决

`current_only`的top-8命中44/206个oracle机会片（21.36%），覆盖23场；`current_plus_prior`
命中47/206（22.82%），同样覆盖23场。两者均低于50片探索门，判
`BM25_LOCAL_EXTRACTION_INSUFFICIENT`。前一片关键词只增加3个命中。

top-16描述性结果为71与73片，但主宽度已固定为8，不能事后改门；即使采用16也远低于157片
主目标。词法source-span检索不能把全池206片oracle供给压缩成有效小集合。下一分支是注册全池
semantic embedding抽取；先做331批上限的readiness，未取得新授权前不接触模型。

证据见[检查记录](../../checks/2026-08-28-material-lhcp-bm25-local-extractor/README.md)。
