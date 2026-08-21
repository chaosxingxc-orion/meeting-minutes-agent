# E4-XDOMAIN-SUPPLY-AUDIT：跨领域 speaker carry 供给审计

日期：2026-08-21  
状态：**已完成唯一一次正式读取；`DOMAIN-LIMITED-SUPPLY`**
类型：零模型、只读语料、探索性供给审计

## 研究问题与边界

本审计回答：真实会议语料中，是否同时存在足量的 Product/AMI 与 Academic/ICSI 同说话人术语复现，可支持后续平衡的跨领域方向性 pilot。它不运行 Omni，不重建 PRECOMP，不测量转写效果，也不证明术语代理是真实专业实体。

QMSum 提供统一的有序 `speaker + content` 转写，但 Product 与 Academic 没有统一实体标注。因此只使用运行时可提取的保守词项代理。既有 AMI census 已证明大写启发式会高估开放词表专名；本审计必须把结果称为“代理供给”，不能改写该结论。

## 冻结语料与隔离

- QMSum 固定提交 `83d7768c1f2b4dfeb091385d3dc7e239b8e5bb7e`。
- Product：只读 `data/Product/train/*.json`，并与 AMI role registry 的 `glossary-discovery` 角色取交集。
- Academic：只读 `data/Academic/train/*.json`；对应 ICSI 音频必须存在。
- Product/Academic 的 `val`、`test` 全部保留，不读取内容或统计。
- Committee 无本地音频，不进入本审计。
- AMI role registry SHA-256 为 `e21a297a31594204bfc96670aa507534340f329688b6baa03db1d65141e8200f`。任何未知、保留角色、缺音频或 schema 异常均使审计失败关闭。

## 冻结术语代理与 carry 定义

按转写顺序处理 segment；同一 segment 内同一 surface 只计一次。候选词为：

1. `strict_technical`：至少两个字母的全大写缩写，或同时含字母和数字的词；
2. `name_like`：非句首、长度至少三个字母的 TitleCase 单词；
3. 固定停用词、事件标记和纯数字永不进入候选。

统一小写和所有格后得到 surface。某个当前 `speaker × segment × surface` 之前若在同 speaker 的更早 segment 出现，记为 same-speaker carry；若此前从未由其他 speaker 出现，则进一步记为 `speaker_exclusive_carry`。这近似衡量 speaker 路由独有的可寻址供给，不使用 query、summary、topic 或答案字段。

## 指标与机械判决

每个领域报告会议数、音频 join、候选数、same-speaker/global-only/exclusive carry、eligible meeting 数、每场分布、候选类型和最大单 surface 集中度。eligible meeting 固定为至少 2 个 exclusive carry 单元。

单领域通过全部门槛需：会议数 ≥20、eligible meeting ≥20、exclusive carry ≥100、其中 `strict_technical` ≥10，且最大单 surface 占比 ≤20%。

判决顺序：

1. 泄漏、schema、音频 join 或输入锁失败：`INVALID-AUDIT`；
2. Product 与 Academic 均通过：`XDOMAIN-SUPPLY-FEASIBLE`；
3. 仅一个领域通过：`DOMAIN-LIMITED-SUPPLY`；
4. 均未通过：`INSUFFICIENT-XDOMAIN-SUPPLY`。

任何结果都不授权模型调用。通过仅允许另行预注册一个独立、平衡、带安全门的低资源 pilot；失败时不得在同一读取上放宽候选或阈值。

## 正式结果

Product/AMI 有 61 场会议，其中 35 场 eligible，共 187 个 speaker-exclusive carry；但严格技术型 carry 只有 3 个，未达到 10 个门槛。Academic/ICSI 的 41 场全部 eligible，共 753 个 exclusive carry、254 个严格技术型 carry，全部门槛通过。机械判决为 `DOMAIN-LIMITED-SUPPLY`：Academic 供给充分，Product 的 name-like 上界不能替代缺失的严格技术供给，因此不放行平衡跨域模型 pilot。
