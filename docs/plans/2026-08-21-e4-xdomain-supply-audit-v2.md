# E4-XDOMAIN-SUPPLY-AUDIT-v2：Earnings-22 专业实体供给审计

日期：2026-08-21  
状态：**replacement read 已完成；机械通过，专业代理未确认**
类型：零模型、只读文本、探索性供给审计

## 研究问题与边界

v1 已证明 Academic/ICSI 的 speaker-exclusive 词项供给充足，但 Product/AMI 的严格技术代理只有 3 个。v2 不修改 v1 的代理或阈值，而是独立检验新的 business surface：Earnings-22 discovery split 是否包含足量、低集中度、同说话人可复现的上游标注专业实体。

本实验不运行 Omni，不下载或解码音频，不估计 WER/NE-WER，也不证明提示词或 speaker 路由有效。通过只表示值得为 Earnings-22 另行解决音频许可与获取问题，并预注册独立模型 pilot。

## 冻结输入与隔离

- 上游仓库提交：`c05ab6fd8b4b627d123c922a22a39e993dd37635`。
- 只使用 `transcripts/force_aligned_nlp_references/*.aligned.nlp`；预计 125 个文件。普通 reference 的时间戳实际为空，预读 schema 检查后按 amendment 改用同源强制对齐层；无有效 `ts` 的实体 mention 保守排除并只报告聚合排除数。
- split salt：`e4-xdomain-supply-v2-2026-08-21`。按 `SHA256(salt + "\0" + file_id)`、再按 `file_id` 排序，前 80 个为 discovery，后 45 个为 reserve。
- manifest 可散列全部文件以锁定身份，但正式审计只允许解析 discovery；reserve 内容和聚合统计禁止读取。
- 文件数、表头、说话人、时间戳、标签或提交身份异常时 fail closed。

## 冻结代理与计数

按 90 秒固定时间窗形成无音频 pseudo-slice。连续且共享同一实体 ID/类别的 token 合并为实体 mention；surface 统一 Unicode NFKC、小写、折叠空白。排除 `DATE`、`TIME`、`YEAR`、`MONEY`、`PERCENT`、`CARDINAL`、`ORDINAL`、`QUANTITY`、`DURATION`、`MEASURE`；其余上游显式实体类均为 professional-entity proxy。

同一 `speaker × pseudo-slice × surface` 只计一次。若某 surface 在当前单元之前由同一 speaker 出现、且此前从未由其他 speaker 出现，则记一个 `speaker_exclusive_carry`；若此前已有其他 speaker，则分别记为 shared 或 global-only。不得保存 token、surface、实体 ID 或逐文件结果。

## 指标、判决与停止规则

主要门槛沿用 v1 的规模与集中度口径：discovery meetings ≥ 20；至少 20 场各有 ≥ 2 个 exclusive carry；exclusive carry ≥ 100；最大单 surface 占比 ≤ 20%。另报告候选 mention、same-speaker/shared/global-only carry、实体类别数和每场分布，但不据此改门。

判决仅为：全部通过得 `EARNINGS22-SUPPLY-FEASIBLE`，任一失败得 `INSUFFICIENT-EARNINGS22-SUPPLY`，完整性失败得 `INVALID-AUDIT`。只能进行一次正式 discovery 聚合读取；读取后不得放宽类表、split 或阈值。

## 正式结果与解释

首次读取因 1 个文件带官方文档所述 `wer_tags` 列而 fail closed，未产出聚合结果；恢复 amendment 冻结后完成 replacement read。80 场 discovery 中 67 场 eligible，speaker-exclusive carry 为 1,803，最大单 surface 占比 8.87%，机械判决为 `EARNINGS22-SUPPLY-FEASIBLE`。45 场 reserve 未读，模型与音频调用均为 0。

但 `CONTRACTION` 与 `FALLBACK` 占 exclusive carry 的 1,266/1,803（70.2%），证明冻结的宽类表衡量的是广义上游 WER 标签复现，而不是纯专业实体。`ABBREVIATION + ALPHANUMERIC` 有 538 个 exclusive 单元，但没有独立预注册 meeting-level 门，不能事后改写为确认结论。下一步只能在未读 reserve 上另行预注册窄类确认审计。
