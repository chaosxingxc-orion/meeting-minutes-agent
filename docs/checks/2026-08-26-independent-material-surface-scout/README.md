# 独立材料 surface 搜索回执（2026-08-26）

## 结果

- 判决：`PRIMARY_CANDIDATE_FOUND_SOURCE_ENDPOINT_JOIN_PENDING`
- 首选：`LHCP-ASR`
- 次选：`Chinese-LiPS validation/test`
- 模型调用：0
- embedding 调用：0
- 语料下载：0 bytes
- reference 读取：0（所选 LHCP-ASR）

## 独立性审计

在写入本次记录前，对当前仓库和伞仓执行以下只读搜索，结果均为0命中：

```powershell
rg -n -i "Chinese-LiPS|Chinese LiPS|BAAI/Chinese-LiPS|LHCP-ASR|mllp/LHCP" \
  D:\repo\meeting-minutes-agent D:\repo\exploring-l4-intelligence \
  -g '!**/.git/**' -g '*.md' -g '*.json' -g '*.py' -g '*.toml'
```

本次只读取官方论文、dataset card、许可、文件树和汇总统计。未读取 LHCP-ASR 样本行、音频、
slide 或转写文本。网络检索页曾展示 Chinese-LiPS 的训练集预览和 Earnings25 的一个 segmented
样本，因此 Chinese-LiPS 只保留 validation/test，Earnings25 必须排除该 viewer-exposed source call。

## 资源核对

`mllp/LHCP-ASR` 固定 revision 为
`1583283ffe91ee22f7e547fc1248c3646f68fe43`。四个 long-form evaluation split 共17个
Parquet shard、6,705,900,572 bytes（6.25 GiB）：

| split | talks | hours | shards | bytes |
|---|---:|---:|---:|---:|
| dev_2020 | 14 | 5.6 | 3 | 1,230,987,658 |
| dev_2022 | 11 | 4.8 | 3 | 1,045,048,981 |
| test_2020 | 15 | 6.2 | 4 | 1,434,338,360 |
| test_2022 | 32 | 13.4 | 7 | 2,995,525,573 |

进一步的零下载检查确认CERN Indico官方事件`856696`（2020）和`1109611`（2022）可访问；
JSON export能返回稳定contribution ID以及附件的下载URL、文件名、size和checksum，网页也逐报告
列出slides与recording。当前阻断点已收窄为：尚未证明HF音频路径到72个Indico contribution的
精确join与72/72材料覆盖。未解决前不下载、不接触模型、不打开reference。

完整判定见[候选审计](../../readiness/2026-08-26-independent-material-surface-scout.md)。

## 后续更新

同日的`E-MATERIAL-LHCP-ADMISSION`已完成72/72精确join、72/72材料覆盖和77/77材料端点检查。
本页的`JOIN_PENDING`是搜索完成时的历史判决。
