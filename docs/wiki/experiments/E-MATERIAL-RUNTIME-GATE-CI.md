# E-MATERIAL-RUNTIME-GATE-CI

- 负责人：EuphoriaYan
- 状态：`已判读`
- 证据等级：`CONSTRUCTION_ISOLATED_EXPLORATORY`
- 类型：零模型、开发/确认语义门控复用实验
- 预注册：[construction-isolated预注册](../../readiness/2026-08-25-material-runtime-gate-ci-preregistration.md)
- Pass0预注册：[六场裸转写航班](../../readiness/2026-08-25-material-runtime-gate-ci-pass0-preregistration.md)
- Pass0运行清单：[1,639次调用](../../../configs/probes/material_runtime_gate_ci/2026-08-25-pass0-runtime.json)
- 语义门执行登记：[开发拟合与一次确认](../../readiness/2026-08-25-material-runtime-gate-ci-semantic-execution-amendment.md)
- 冻结配置：[六场会议与判决门](../../../configs/probes/material_runtime_gate_ci/2026-08-25-registration.json)

## 为什么降级复用

严格准入已经确认 Earnings-22 的 125 场参考词面都曾被 v2/v3 读取，继续寻找六场严格未读会议
不可行。本实验不改写这个失败判决，而是接受较弱证据：历史上参考已暴露，但从本次注册开始，
材料选择、候选构造、Pass0、语义检索、阈值拟合和确认读取均与参考隔离。

## 冻结队列

- 开发：`4474506` Costco、`4479944` HDFC Bank、`4483506` Sony；
- 确认：`4483633` Ferrari、`4484563` Sanofi、`4485244` KKR。

每边均含1场历史reserve和2场historical discovery。选会只使用ID、公司、日期、期间和官方材料
可得性，禁止使用参考词、speaker占比、既有逐会术语结果、WER或检索分数。任何一场不能取得
会前/当天官方材料或不足8个确定性候选，整个队列失败，不允许事后换会。

## 零模型语义门结果

开发集按冻结网格选择最低合格阈值`0.01`：479/622个eligible turn被dispatch，覆盖率77.01%，
正确会议归属precision 73.28%，正确材料相对错配材料的中位余弦优势为0.05709。阈值写入开发
结果后未再调整。

唯一一次确认读取在850个eligible turn上dispatch 636个，覆盖率74.82%；其中484次正确会议
归属胜出，precision 76.10%，中位余弦优势0.06154。确认集三场逐会precision分别为94.39%、
77.27%和58.64%，2/3场越过60%分布门；四项预注册门全部通过，机器判决为
`CONSTRUCTION_ISOLATED_SIGNAL_PRESENT`。第三场的近门结果说明信号存在明显逐会异质性。

## 当前边界与下一步

六场材料准入已通过：6/6场均取得当天或更早的官方材料，确定性快照包含54页、1,403个原始候选，
逐会候选数为81、143、167、187、391、434，全部超过8项门。原件与快照均冻结SHA-256，构造
阶段仍为零reference、零Pass0、零embedding、零Omni。

六场Pass0已在模型接触前单独注册：完整处理1,639个固定turn、22,678.133秒音频；裸`T1-A1`
提示不接收材料、参考、摘要、关键词、speaker身份或历史hypothesis。航班按逐会fail-closed阶段完成，
且只执行预先冻结的结构读取。只有随后另行执行的零模型开发门和一次确认门通过，才允许另立
探索性三臂Omni实验。即使通过，也只能写成“构造隔离信号存在”，不能写成独立确认。

Pass0现已完成：1,639/1,639成功、0空输出、0重试，结构判决`PASS0_COMPLETE`。零模型开发拟合
和一次确认门也已按单向协议完成，且未调用Omni。这只证明当前构造隔离队列中存在可dispatch的
语义归属信号；历史参考已暴露的事实不变，不能宣称独立确认、WER改善、安全纠错或可部署。
若继续，必须另行预注册并授权探索性的`R0-retain / R1-correct-dispatch /
R2-deranged-dispatch` Omni航班；同时仍应寻找新会议或外部独立测试集。

- [材料准入回执](../../checks/2026-08-25-material-runtime-gate-ci-acquisition/README.md)
- [Pass0航班回执](../../checks/2026-08-25-material-runtime-gate-ci-pass0-flight/README.md)
- [开发阈值回执](../../checks/2026-08-25-material-runtime-gate-ci-development-read/README.md)
- [一次确认回执](../../checks/2026-08-25-material-runtime-gate-ci-confirmation-read/README.md)
