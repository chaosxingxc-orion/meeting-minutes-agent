# E4-XDOMAIN-SUPPLY-AUDIT-v3：Earnings-22 窄类 reserve 审计

日期：2026-08-22
状态：**唯一 reserve 读取已完成；`EARNINGS22-NARROW-SUPPLY-FEASIBLE`**
类型：零模型、只读文本、独立保留集供给审计

## 研究问题

v2 在80场 discovery 上得到1,803个 speaker-exclusive carry，但其中70.2%来自 `CONTRACTION/FALLBACK`，只能证明广义 WER 标签复现。v3 回答更窄的问题：在完全未读的45场 reserve 上，只保留 `ABBREVIATION` 与 `ALPHANUMERIC` 后，是否仍有足量、低集中度、同说话人独有的技术词复现，可支持后续独立模型实验设计。

本实验不运行 Omni，不下载、解码或处理音频，不测量 WER/NE-WER，也不证明 speaker prompt 有效。通过仅允许进入 Earnings-22 音频许可与最小 acquisition 设计。

## 冻结输入与隔离

- 上游提交：`c05ab6fd8b4b627d123c922a22a39e993dd37635`。
- 父 manifest：`configs/probes/e4_xdomain_supply_v2/2026-08-21-input-manifest.json`，canonical content hash 为 `67f0fc955ff9057ee5819ee3f05957ad1a04d2603564ba75366d4d319e2bd313`。
- 使用父 manifest 中已按 salt `e4-xdomain-supply-v2-2026-08-21` 冻结的45个 `reserve` 文件。
- discovery 的80个文件不得由 v3 reader 打开、解析或重新统计；其结果只能用于选择本次固定类别，不能用于调整门槛。
- reserve manifest 只保存文件 ID、相对路径、字节数和哈希，不保存文本、surface、实体 ID 或逐会议统计。

## 冻结候选与 carry

只纳入上游标签类 `ABBREVIATION` 和 `ALPHANUMERIC`。`CONTRACTION`、`FALLBACK`、`RANGE`、`PHONE`、`WEBSITE` 及其他类别全部排除。无有效对齐时间戳的窄类 mention 保守排除，并只报告聚合排除数。

沿用 v2 的90秒固定 pseudo-slice、Unicode NFKC、小写和空白折叠规则。同一 `speaker × pseudo-slice × surface` 只计一次。若某 surface 在当前单元之前由同一 speaker 出现，且此前从未由其他 speaker 出现，则记一个 `speaker_exclusive_carry`。每场至少2个 exclusive carry 时记为 eligible。

## 冻结门槛与判决

门槛沿用 v2 的绝对供给尺度，不根据 discovery 的538个窄类 exclusive 单元重估：

- reserve roster 必须恰为45场；
- eligible meetings ≥ 20；
- speaker-exclusive carry ≥ 100；
- 最大单 surface 占 exclusive supply 的比例 ≤ 20%。

完整性、schema、哈希、split 或 discovery 隔离失败时判 `INVALID-AUDIT`；全部供给门通过时判 `EARNINGS22-NARROW-SUPPLY-FEASIBLE`；否则判 `INSUFFICIENT-EARNINGS22-NARROW-SUPPLY`。只能进行一次正式 reserve 聚合读取，读取后不得更换类别、阈值或 eligibility 定义。

## 正式结果

45场 reserve 全部完成唯一读取，discovery 读取数为0，模型调用和音频使用均为0。30场会议 eligible，共264个 speaker-exclusive carry，其中 `ABBREVIATION` 185个、`ALPHANUMERIC` 79个；最大单 surface 占比11.36%。三个供给门全部通过。870个无有效时间戳的窄类 mention 被保守排除，但剩余供给仍显著超过冻结门槛。

因此 Earnings-22 的窄类技术词供给在独立 reserve 上得到确认。该结果只放行音频许可与最小 acquisition 决策，不放行模型 pilot 或 agent loop。
