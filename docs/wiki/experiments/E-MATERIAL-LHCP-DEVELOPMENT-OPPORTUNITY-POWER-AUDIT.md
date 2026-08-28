# E-MATERIAL-LHCP-DEVELOPMENT-OPPORTUNITY-POWER-AUDIT

## 状态

- 状态：已判读
- 日期：2026-08-28
- 类型：开发集零模型primary opportunity与功效审计
- 依赖：`E-MATERIAL-LHCP-DEVELOPMENT-SEMANTIC-GATE`
- 授权：EuphoriaYan已明确授权读取25场开发reference
- 预注册：[opportunity与功效规则](../../readiness/2026-08-28-material-lhcp-development-opportunity-power-preregistration.md)

## 问题

已经冻结的396条材料top1中，是否有足量、跨会议分布的专业词wrong-to-correct机会，值得投入约
1,188次Omni三臂调用？本实验不调用模型，也不允许用gold筛选未来具体调用。

## 冻结设计

只从固定LHCP-ASR revision的6个development Parquet读取`audio.path + transcription`，精确绑定25场；
不读取音频列、test split或45场confirmation。会议级审计覆盖全部200个材料key；逐片主审计使用
已冻结的396个semantic top1。整会Pass0到reference的确定性词边界对齐只用于估计局部窗口，并在两侧
固定加12词；它不是时间戳gold。

主机会定义为：top1 canonical在局部reference窗口精确出现、但在当前Pass0片中不出现。10个百分点
配对效应、20% discordance、双侧alpha 0.05、80% power要求157个机会。正式放行还要求覆盖至少
15场，且396条中至少70%得到局部reference支持。50个机会/10场以上但未过主门只记探索性供给。

## 边界

reference类别只能进入审计与未来一次性reader，不能进入prompt、候选选择或调用身份。任何未来
Omni flight仍必须覆盖全396条或另用reference读取前已冻结的确定性子样本；confirmation保持sealed。

## 结果

一次性reader返回`LHCP_CORRECTION_OPPORTUNITY_INSUFFICIENT`：396条激活中，56条为retain，只有
12条为wrong-to-correct机会，覆盖8/25场；其余328条为局部reference不支持。局部支持率为
17.17%，远低于70%门。主目标要求157个机会且至少覆盖15场，因此三项正式门全部失败；连
50机会/10场的探索门也未达到。

会议级200个材料key中，44个在reference出现，38个已在Pass0出现，只有7个构成整会
wrong-to-correct候选。拼接Pass0的描述性micro-WER为14.81%（14,677/99,107词）；这不是材料
纠错效果。单标签与多标签切片的局部支持率分别为16.73%和18.05%，未见speaker标签数量能修复
供给不足的迹象。

## 判决与下一步

不启动当前设计的1,188-call三臂Omni flight。90.66%的“正确会议胜错配会议”只证明会议归属，
不能推出所选canonical位于当前切片或存在可纠错错误。后续若继续，应先重新定义运行时目标：
从“每片强制选择一个会议材料key”改为可拒绝的局部实体提议或材料跨度检索，并在新的
reference-unread开发面前瞻注册；不得用本次gold类别筛选调用。45场confirmation继续sealed。

证据见[检查记录](../../checks/2026-08-28-material-lhcp-development-opportunity-power/README.md)。
