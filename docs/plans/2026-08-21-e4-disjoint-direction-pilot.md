# E4-DISJOINT-DIR：两臂方向性实验计划

日期：2026-08-21

状态：**已冻结、已获实验授权；模型 flight 尚未执行**

## 研究问题

在固定 diarizer、切片、预处理、模型和提示模板下，对 `speaker_wrong_disjoint` 的自然 carry target，正确 speaker 状态是否比等长 global 状态产生一致的专业词转写改善方向？本实验只估计方向，不确认 3 pp 或 5 pp 实用效应，也不放行 agent loop。

## 冻结样本

输入是 `E4-DISJOINT-PREV` 的60个未见 dialogue 和795条完整 Pass-0 输出。target 必须同时满足：当前 reference 中存在同 speaker 先前已说过的自然 carry；global、speaker、wrong 三个 Pass-0 状态均非空且截成相同宽度；规范化 speaker 与 wrong 集合无交集。不得按 Pass-0 是否转错、模型置信度或未来第二遍结果筛选。

冻结后得到86个 target、52个 dialogue cluster、93个 carry mention。状态宽度为1–8。runtime binding 不含 reference 或 carry labels；score binding 不进入 launcher 或 prompt。

## 两臂与预算

- `D0-global`：注入等长会议全局状态。
- `D1-speaker`：注入当前说话人的等长状态。

每个 target 使用 byte-identical 音频；按 target 奇偶交替两臂先后顺序。解码固定为 temperature 0、seed 0、max tokens 512、单 slot、零自动重试。精确预算为172 calls、2,114.418重复音频秒（0.5873小时）。任何输出路径已存在均拒绝启动。

## 一次性判读

主指标为 `D1-D0` carry exact-hit rate；同时报告 carry NE-WER、总体 WER、false-hint target rate及按 dialogue cluster bootstrap 的80%和95%区间。区间只描述不确定性，不作为确认门。

判读顺序固定：任一臂截断则 `EXPLORATORY-INVALID-TRUNCATED`；若 speaker 的总体 WER 恶化超过1 pp，或 false-hint target rate 增加超过2 pp，则 `EXPLORATORY-HARMFUL`；若 carry hit 增加、carry NE-WER下降且安全门通过，则 `EXPLORATORY-SPEAKER-DIRECTION`；若 hit 不增且 NE-WER不降，则 `EXPLORATORY-NO-GAIN`；其余为 `EXPLORATORY-MIXED`。

任一请求失败都会终止 flight；不读取不完整结果，也不在同一注册下补飞。正式 read 目录必须事先不存在，只允许执行一次。

## 结论边界

即使得到正方向，也只能支持“值得寻找更大独立 carry-dense surface”，不能改写 E4-CF 的 `DIRECTIONAL-NOT-CONFIRMED`，不能下调原实用效应门，不能启动选择性重听、GEPA、GRPO、EM 或多轮 agent loop。
