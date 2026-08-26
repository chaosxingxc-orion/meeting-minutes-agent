# 本地工作档案：meeting-minutes-agent @ EuphoriaYan 机器

> 最后更新：2026-08-21。本文档是**本地记录，不提交 Git**。新开窗口时读本文件即可接手。
> 机器：Windows 11 + WSL2 Ubuntu-24.04（24 核、主机 32G 内存、RTX 5090 Laptop 24G 显存、CUDA 13.3）。

## 0. 一句话现状

复现层全部就绪：六个数据集 verify 全 PASS、pytest 全绿、三个 C++ 构建全部完成、
PRECOMP wave-1（dev-18）本地 18/18 跑完——**本机已进入 decode-only 状态，可以直接跑
G1 / E4 类实验（音频编码零重复）**。

## 1. 关键路径速查

| 用途 | 路径 |
|---|---|
| 代码仓（工作目录） | `D:\repo\meeting-minutes-agent`（WSL 下 `/mnt/d/repo/meeting-minutes-agent`） |
| **数据根**（SPEECHRL_DATA_DIR） | `D:\speechrl-data`（WSL 下 `/mnt/d/speechrl-data`） |
| 数据集 | `<数据根>/datasets/{ami,icsi,meetingqa,qmsum,m3-slu,meetingbank}` |
| 主模型 + mmproj | `<数据根>/models/qwen3-omni-30b-a3b-instruct-gguf-q4km/`（Q4_K_M 17.3G + mmproj-bf16 2.2G + mmproj-Q8_0 备用） |
| diar 检查点 | `<数据根>/models/diar-sortformer-4spk-v2/diar_streaming_sortformer_4spk-v2.q8_0.gguf`（sha256 `0679cfeb…da998a` ✓） |
| 官方 llama.cpp 构建 | `~/llama.cpp-official`（WSL home；base `fdbd6ab` + 仓内 4 补丁；二进制 `build/bin/llama-server`，17,920 B 与收据一致） |
| NeMo-Speech.cpp 构建 | `~/NeMo-Speech.cpp`（pinned `4c749a70`；二进制 `build/cuda-diar/bin/nemo-speech`） |
| 我们的 feat-cache patch（实验性） | `~/llama.cpp-featcache`（master + 自写 mmproj-free patch，未提交；含独立编码器 `mtmd-feat-encode`） |
| Python venv（主） | `~/.venvs/meeting`（uv 安装 `-e ".[dev]"` + `openjiuwen==0.1.16.post2` 手动装） |
| Python venv（数据工具） | `~/.venvs/data`（huggingface_hub 0.36） |
| AMI 标注（已解压，必需） | `<数据根>/datasets/ami/annotations/manual_1.6.2/` 和 `auto_1.5.1/` |
| precomp wave-1 产物 | 收据 `<数据根>/checks/precomp-wave1/`；RTTM+切片 `<数据根>/derived/meeting-minutes/precomp/`；特征缓存 `<数据根>/feat-cache/ami-q4km/`（9,112 条 / 7.1 GB） |
| 运维脚本（本地写的） | `<数据根>/{serve.sh, precomp-wave1.sh, precomp-wave1-resume.sh, precomp-trial.sh, arm-config.json, copy-six.sh, build-official-llama.sh, build-step2.sh, build-nemo.sh, nemo-apply-patches.sh, nemo-rebuild.sh, fix-ami-annotations.sh}` |
| E 盘旧数据根（保留） | `E:\datasets`（六个数据集的原件副本源；`E:\dl-*.sh/py/txt` 是当时下载用的脚本） |

## 2. 常规操作手册

启动服务（precomp/G1 都需要先起服务，加载约 5–7 分钟）：

```bash
MSYS2_ARG_CONV_EXCL='*' wsl -d Ubuntu-24.04 -- bash /mnt/d/speechrl-data/serve.sh
# 就绪检查：curl -s http://127.0.0.1:8080/health → {"status":"ok"}
```

续跑 precomp（断点续跑，会议粒度）：

```bash
MSYS2_ARG_CONV_EXCL='*' wsl -d Ubuntu-24.04 -- bash /mnt/d/speechrl-data/precomp-wave1-resume.sh
```

跑 pytest：

```bash
MSYS2_ARG_CONV_EXCL='*' wsl -d Ubuntu-24.04 -- bash -lc \
  'source ~/.venvs/meeting/bin/activate && cd /mnt/d/repo/meeting-minutes-agent && python -m pytest -q'
```

复核数据集：

```bash
MSYS2_ARG_CONV_EXCL='*' wsl -d Ubuntu-24.04 -- bash -c \
  'cd /mnt/d/repo/meeting-minutes-agent && SPEECHRL_DATA_DIR=/mnt/d/speechrl-data python3 scripts/data/verify.py --quiet'
```

G1 floors（下一步，服务就绪后；注意 runner 自己拉起/关闭 server 的 chunk 模式，见 `REPRODUCE.md` §11）：

```bash
python scripts/run_g1.py --mode floors --data-dir /mnt/d/speechrl-data --summary-only   # 先试这个，安全
```

## 3. 未完成的尾巴

1. **评分层缺系统包**：`meeteval==0.4.3` 编译需要 `Python.h`。需要在 WSL 里执行一次
   `sudo apt install -y python3.12-dev`（要密码），然后：
   `source ~/.venvs/meeting/bin/activate && uv pip install "meeteval==0.4.3" "jiwer==4.0.0" "rouge_score==0.1.2"`。
   装完后 pytest 基线应从 915 涨到 ~1550（对照 `REPRODUCE.md` §9）。
2. **E4-DIR 缺 1 个调用**：`docs/checks/2026-08-21-e4-disjoint-dir-flight/responses.jsonl` 有 171/172，
   缺 target `10465-5-t009` 的 D0-global 臂。按注册规则不能评分/续跑，需要 owner 批准重飞
   （172 调用约半小时，本地可以直接重飞）。
3. **wave-2**（其余 58 场 discovery 会议 precomp，夜间批量级）：未开始。

## 4. 本机环境注意事项（踩过的坑，别再踩）

- **`MSYS2_ARG_CONV_EXCL='*'` 必须加**在所有 wsl 调用前，否则 `/mnt/...` 路径被 Git Bash 改写。
- **wsl 里带 `$变量` 或 `&` 的命令一律写成脚本文件再执行**，不要内联——wsl.exe 拼接参数会丢引号，
  `$PATH`/`$!` 会被外层展开。
- **后台长任务**：kimi 会话关闭会杀它的子进程；真正独立要用 Windows 计划任务（参考已用过的
  `MMA-Dataset-Download`，现无在跑任务）或在 WSL 里 nohup（注意 WSL2 会话结束会连带杀，schtasks 最稳）。
- **WSL 内存已调至 24GB**（`C:\Users\ysq58\.wslconfig` 的 `memory=24GB`）。改动前 16G 会把
  llama-server OOM 杀掉。还原就删那一行再 `wsl --shutdown`。
- **HF 直连不通**：`huggingface.co` 超时，且 `hf` CLI 对 xet-bridge CDN 的 HEAD 会挂死。
  下载一律走 `hf-mirror.com` + aria2c 纯 GET（多连接、续传、按镜像 API 给的 LFS sha256 逐文件校验）。
  Zenodo 也慢（~35 KiB/s），用 aria2c `-x16` 可破。
- **AMI 标注必须解压**成 `annotations/manual_1.6.2/` 布局，否则 oracle 话轮源静默产 0 片且
  verify 不报警。
- **模型 hash 偏差**：主模型 Q4_K_M 本地 sha256 = `d9e28765…`（ggml-org 官方 blob），与飞行收据
  pin 的 `0751c279…` 不一致（公开渠道找不到原 blob，疑似 owner 自转换）。跑实验用 `--model-sha256
  d9e2876556e7873e02c0359f832432ee2d67ab7dd0cee3efe0f77fd7a1f4dd85`；写报告时注明。
- **robocopy 不要接 `| head/tail`**（管道关闭会杀它），日志写文件。

## 5. 研究线现状速记（2026-08-21 时点）

- Z 系列 / G1 floors：同事已飞完并读数（Z-turn 0.6099 / Z-oracle 0.6061 / Z-free 0.8726 /
  Z-nodiar 0.8816；tool-vs-oracle 差距在噪声内，DIARIZE-first 成立）。
- E4（speaker-conditioning，本机主人的主线）：E4-CF 判 `DIRECTIONAL-NOT-CONFIRMED`（+2.16pp <
  5pp 门槛）；机制审计选出 speaker/wrong disjoint 策略；功效审计 `INSUFFICIENT-CARRY-SUPPLY`；
  prevalence 筛查 PASS；E4-DIR pilot 171/172（见第 3 节尾巴）。
- agent loop（GEPA/GRPO/EM/多轮）当前**未授权**——工作计划明文禁止，别私自启动。
- 本地独有资产：自写 mmproj-free feat-cache patch（`~/llama.cpp-featcache`），实测无 mmproj
  服务省 2,914 MiB 显存、输出与带 mmproj 逐字一致；与官方热缓存 patch 的 `.feat` 格式不互通。

## 6. 原始收据位置

- 本档案：`docs/checks/2026-08-21-precomp-wave1-local-repro/README.md`（仓库工作区内，**未跟踪、不提交**）。
- wave-1 18 张会议收据 + wave-summary：`D:\speechrl-data\checks\precomp-wave1\`。
- 服务器/runner 日志：`D:\speechrl-data\checks\precomp-wave1-resume.log` 及 kimi 后台任务日志。
