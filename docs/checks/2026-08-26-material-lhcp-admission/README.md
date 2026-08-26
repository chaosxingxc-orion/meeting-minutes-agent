# LHCP-ASR元数据准入回执（2026-08-26）

## 判决

- 结果：`LHCP_METADATA_JOIN_AND_MATERIAL_COVERAGE_CLOSED`
- 离线复核：`TRACE_COMPLETE`
- HF路径：72/72唯一
- CERN contribution：72/72一一对齐
- 孤儿/歧义/重复contribution：0/0/0
- 材料覆盖：72/72场，77个唯一附件、77个唯一checksum
- 端点：77/77通过`Range: bytes=0-0`响应头检查，正文读取0 bytes
- 模型/embedding/reference：0/0/0

## 分布与资源

| split | 场数 |
|---|---:|
| `dev_2020` | 14 |
| `dev_2022` | 11 |
| `test_2020` | 15 |
| `test_2022` | 32 |

附件为74个PDF和3个PPTX；67场有1个附件，5场有2个，官方声明总大小约1.536 GiB。17个HF
long-form shard远端合计6,705,900,572 bytes；本次仅投影`audio.path`，34次HTTP Range实际传输
1,116,237 bytes，没有下载音频或完整Parquet。

## 可复核证据

- `manifest.json`：72场join与材料元数据，SHA-256
  `22d77a1dbd98b3b4344b3a54d55d09f0c62a741ab0d0408b12079747575697a2`
- `verdict.json`：机械判决
- `validation.json`：哈希、唯一性、覆盖和reference firewall复核
- `endpoints.json`：诊断性HEAD回执；CERN不支持该方法，77/77返回400
- `endpoints-v2.json`：首次Range检查，70/77成功，7个瞬时TLS错误
- `endpoints-v3.json`：冻结重试回执，77/77为HTTP 206且body读取为0

命令：

```bash
python scripts/audit_material_lhcp_admission.py \
  --config configs/probes/material_lhcp_admission/admission.json \
  --manifest-out docs/checks/2026-08-26-material-lhcp-admission/manifest.json \
  --verdict-out docs/checks/2026-08-26-material-lhcp-admission/verdict.json
python scripts/validate_material_lhcp_admission.py \
  --config configs/probes/material_lhcp_admission/admission.json \
  --manifest docs/checks/2026-08-26-material-lhcp-admission/manifest.json \
  --verdict docs/checks/2026-08-26-material-lhcp-admission/verdict.json \
  --out docs/checks/2026-08-26-material-lhcp-admission/validation.json
```

本判决只放行下一道零模型材料可读性与候选供给审计；不放行Pass0、embedding、Omni或reference读取。

执行环境为WSL `~/.venvs/data`（Python 3.12、`pyarrow==21.0.0`、`requests==2.34.2`）；
完整离线回归在`~/.venvs/meeting`通过：1,583 passed、25 skipped。
