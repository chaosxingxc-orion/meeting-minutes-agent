# LHCP-ASR材料供给审计回执（2026-08-26）

## 判决

- 结果：`LHCP_ZERO_MODEL_MATERIAL_SUPPLY_INSUFFICIENT`
- 离线复核：`TRACE_COMPLETE`
- 材料获取：77/77，共1,648,976,797 bytes；77个MD5和77个SHA-256均唯一
- 逐场通过：70/72
- 开发集：25/25
- 确认集：45/47（`test_2020` 13/15，`test_2022` 32/32）
- reference/音频/Pass0/embedding/Omni：0/0/0/0/0

## 失败格

| 音频ID | split | 材料 | 机械原因 |
|---|---|---|---|
| `856696c36.wav` | `test_2020` | 28页PDF | 第2页触发`LimitReachedError`，0字符、0候选 |
| `856696c52.wav` | `test_2020` | 43页PDF | 第18页触发`LimitReachedError`，0字符、0候选 |

两份PDF均已通过下载checksum；失败来自冻结`pypdf`解析器的64-byte operator guard，不是404或文件
缺失。本实验禁止OCR、备用解析器、换附件和替换会议，因此严格72/72门失败，不能启动模型实验。

## 供给分布

70场通过项的候选数为最小16、中位142、最大1,205；可见字符为最小1,814、中位14,247、
最大376,649。全量读取2,255页/slide、1,994,794个可见字符，逐场唯一候选数求和13,764。
77个附件中75个解析成功，包括3/3 PPTX。

## 执行修正与证据

第一次运行在写外部JSONL时因孤立`U+D835`停止，未产出或读取聚合结果。部分trace已移至失败目录，
SHA-256为`0685f3411713625ad1640c8af8ea04b1f8c87c9ac82dd1d325945ed0c7822072`。修正1只将非法
surrogate替换为`U+FFFD`；候选规则、文档集合和门不变。

- `acquisition-receipt.json`：完整下载回执
- `attempt-1-failure.json`：第一次序列化失败回执
- `verdict-v2.json`：逐场、逐文档机械判决
- `validation-v2.json`：`TRACE_COMPLETE`
- 外部`candidate-pool.json`：16,678,499 bytes，SHA-256
  `53ee687cd6f14a6411acc1fd17784045676080351426a29ead7f8f3cba479f92`
- 外部`material-pages.jsonl`：2,532,514 bytes，SHA-256
  `4729a2a6c6a4a1ead0e4d15fc6be8ec473e59ab7786d6a71ee33d3b2ff1f7bb1`

下一步必须重新选择证据口径：冻结70场可读队列，或另立全量备用解析器实验；不得把当前失败结果
改写为72场供给通过。

共享WSL `~/.venvs/meeting`完整离线回归通过：1,588 passed、25 skipped。

## 70场eligible cohort冻结

同事选择了较窄、前瞻冻结的证据口径。`E-MATERIAL-LHCP-ELIGIBLE-COHORT`只依据上述模型前材料门，
冻结25场开发和45场一次确认；split为`dev_2020=14`、`dev_2022=11`、`test_2020=13`、
`test_2022=32`。精确排除集仍为`856696c36.wav`与`856696c52.wav`，不做parser salvage或会议替换。

- 队列判决：`LHCP_70_TALK_ELIGIBLE_COHORT_FROZEN`
- 离线复核：`TRACE_COMPLETE`，0错误
- 配置SHA-256：`9c170961bed6a112475f9e688151ae4398da81b0a079fe8f21d7992de45c0394`
- cohort manifest SHA-256：`b614e4d9ba63e94a988166d62e9d5e7a2bddc1a31ce7528753f47ebbd4e13733`
- machine verdict SHA-256：`2566041e7459e6b0b1e4a9763a6b9fc95a3ce98ea35cc055a51340fc758299b9`
- validation SHA-256：`616e4eb685c691dc44f9cd1c3a6d8139f4bd8bb73139791bfda626ad44bb0d41`
- reference/Pass0/embedding/Omni：0/0/0/0
- 冻结后共享WSL完整离线回归：1,591 passed、25 skipped

本冻结不改变原72/72供给门失败的判决。后续效果结论只能覆盖70场material-compatible子群；模型
接触、音频处理或reference读取仍需单独预注册和明确授权。

## 25场开发音频获取

`E-MATERIAL-LHCP-DEVELOPMENT-AUDIO`只读取六个development Parquet的`audio.path/audio.bytes`，
25/25 WAV解码通过，总计2,469,998,494 bytes与37,556.965秒（约10.43小时）。14场来自
`dev_2020`，11场来自`dev_2022`；25个SHA-256全部唯一。

第一次尝试在5个完整WAV后因大Range响应中断；修正1将Range拆成最多16 MiB，并在续跑时重新下载
源payload逐字节匹配后才复用5个文件。最终外部manifest SHA-256为
`f82e9958ed81527c89a6922bce6155488fde183699c77a11fee31a22d1661e1f`，离线验证为
`TRACE_COMPLETE`、0错误。confirmation/reference/Sortformer/Pass0/embedding/Omni均为0。

## 固定前端readiness

前端预注册固定25次TOOL-LOCKED(B) Sortformer、37,556.965输入秒、单任务、每场3,600秒超时和2小时
总墙钟；后续用`90/60/120/3`秒、零重叠的M0 turn-aware规则冻结切片。零模型preflight已复核25个
WAV、外部manifest、FFmpeg、NeMo-Speech二进制、Sortformer GGUF及切片代码锁，0错误，判为
`FRONTEND_READY_AWAITING_TOOL_AUTHORIZATION`。

readiness阶段仍为0 reference、0 confirmation、0 Sortformer、0 Omni。Pass0预算必须等完整slice
manifest后再计算，当前不允许用总时长估算后直接启动。

本轮新增音频获取、精确续跑、离线验证和前端readiness测试后，共享WSL完整离线回归为
1,598 passed、25 skipped。

## 固定前端flight最终判读

同事明确放行后，冻结flight按manifest顺序完成25/25次TOOL-LOCKED(B) Sortformer，25个RTTM均
非空，0重试、0换场、0参数修改。随后生成397个哈希绑定的16 kHz mono PCM16切片。预构建结构
reader对25个转换、25个contact receipt、25个RTTM和397个切片给出`FRONTEND_TRACE_COMPLETE`。

但冻结reader漏掉了预注册中的相邻切片零重叠断言。一次独立、只读slice bounds的确定性审计发现
15个重叠边界，影响10/25场，累计35.900秒，最大14.948秒，因此最终实验判决为
`FRONTEND_SLICE_ZERO_OVERLAP_GATE_FAILED`。该问题来自跨分组的重叠说话turn，而不是工具调用失败。

- conversion manifest SHA-256：`7e654c2229839c1da12ae9ccc32d249c87197aacf44b343f2b7695759fdae128`
- flight summary SHA-256：`9d8d5e1faed8abdac72c75f5e2e33fa256f685ba0f2599b59fa5b53d086b30fa`
- slice manifest SHA-256：`e77d75cdb40c6db6cb5c7c2cada6bbc85ee373d94cec9f8af5d8c99cfe0df917`
- 最终判决：[固定前端判决](../../readiness/2026-08-26-material-lhcp-development-frontend-verdict.md)
- reader缺陷：[reader defect](../../readiness/2026-08-26-material-lhcp-development-frontend-reader-defect.md)

本次仍为0 reference、0 confirmation、0 Pass0、0 embedding、0 Omni。Pass0不放行；修复切片边界
必须另立实验，可复用冻结RTTM，但不得覆盖本次397片及失败判决。

## 切片器重叠修复

`E-MATERIAL-LHCP-SLICER-OVERLAP-FIX`将重叠连通turn作为原子打包单位，并在slicer最终出口增加
零重叠post-condition。attempt-1因实现仍逐turn打包而在第24场被post-condition拒绝；23场部分
产物独立封存，无aggregate manifest。修正1不改变策略，只让打包器真正逐原子块迭代。

attempt-2最终判为`SLICER_OVERLAP_FIX_PASSED`：25/25场、396片、37,547.256音频秒，最大120秒，
0重叠边界、0普通turn内部切点、0内部gap。四个turn内部边界均属于原已允许的单个超长turn例外。
预建validator给出`SLICER_OVERLAP_FIX_TRACE_COMPLETE`且0错误。

- 配置SHA-256：`dae7a25c1081a37c025e4abd17118c6321f1b4868a60676cadbde8767d1eb51a`
- 新slice manifest SHA-256：`1224f0951c6b255523197974368c54e73fd27c4a9b328bf5c909eaf226d695ce`
- validation SHA-256：`66f4355163c4b8b21d522066c0d09e862c2d9e004dad17dfa8885899fda90867`
- [最终判决](../../readiness/2026-08-26-material-lhcp-slicer-overlap-fix-verdict.md)

原397片失败判决不变，新396片只放行另立开发Pass0注册。该过程为0 Sortformer、0 reference、
0 confirmation、0 Pass0、0 embedding、0 Omni。
