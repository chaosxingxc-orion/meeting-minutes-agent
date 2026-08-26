# 阶段性结论

最后更新：2026-08-27。

## 已得到支持的结论

- 固定 diarizer、切片器和预处理后，模型会响应文本实体条件；speaker state 可在不使用 gold 的情况下合法构造。
- Academic/ICSI 有足量 speaker-exclusive 严格技术词代理供给。
- Earnings-22 discovery 有大量同说话人重复的上游标签，但这只是语料筛查结果，不是模型效果。
- Earnings-22 未读 reserve 在只保留缩写和字母数字类后仍有264个 speaker-exclusive carry，30/45场 eligible，窄类技术词供给已得到独立确认。
- Earnings-22 官方音频125/125已获取并通过 LFS SHA-256 与解码检查；音频、元数据、对齐参考 ID 完全闭合。
- Earnings-22 全库固定 Sortformer 125/125成功；在30场主讲占主导的 >4 人电话会中，Top-1/Top-2错误为14.30%/22.59%，主讲路由条件可用。
- 4场完整Omni Pass0确认整会内存在13个strict稳定错误簇，覆盖4/4场和70次复现，证明“短片段执行、整会错误簇优化”的供给机制可观测。
- 滑动记忆零模型审计在4/4场找到足量跨窗供给：1424/1429个turn有非空历史关键词记忆，554个turn有同预测speaker跨窗内容词复现；可注册稳定性能力实验。
- 稀疏per-chunk loop的结构和收敛能力成立：7145/7145 calls完整，1056个路由对照100%可分且等量，第二轮变化比为0.280。
- 会议同期官方材料可以合法形成带出处的候选库存：3场时间合规会议、49个候选全部保留文档哈希、页码和原文跨度，构造阶段未读Pass0或reference。
- encode-only语义K建立了分布式材料归属信号：dispatch覆盖52.33%，正确材料precision 77.86%，较词法K提高15.997点，3/3场超过60%逐会门。
- construction-isolated六场复用的零模型门已通过：开发集冻结最低合格阈值0.01；确认集覆盖74.82%、正确会议归属precision 76.10%、中位余弦优势0.06154，四项预注册门全部满足。
- EarningsCallVoice+FinCall新surface开发集已建立可重放Pass0基线：40/40短片段调用成功、0空输出、
  0重试，精确wire trace与receipt全部闭合；该阶段保持reference未读。
- 新surface开发集材料语义归属信号存在：正确call胜错配call 30/40（75%），中位余弦优势0.07609，
  20/20场有dispatch；40行完整trace及120个向量sidecar全部通过验证。

## 尚未得到支持的结论

- speaker-specific 文本路由没有达到预注册的 +5 pp 实用效应门。
- 当前 `speaker_wrong_disjoint` 策略在低资源独立 pilot 中增加 false hint，不能部署。
- 简单 evidence、recency 或 inventory-width gate 不能同时保留收益与安全。
- Earnings-22 的窄类供给已确认，但这些类别仍是技术词代理，不是语义命名实体，也没有证明模型收益或 false-hint 安全。
- Earnings-22 有116/125场超过4位参考说话人；全库验证推翻了“只看总人数就否决前端”的过强判断，但仍未建立无gold的主讲 eligibility 门或转写收益。
- Sortformer 对长尾 speaker 仍不可用：主讲占主导组的长尾错误72.75%，不能把主讲可用改写成完整说话人分离。
- RTTM-only 主讲门判为 `RUNTIME-DOMINANT-GATE-UNSAFE`：precision 38.60%，且29/57个放行会议的Top-2错误超过40%；稳定预测占比可能只是稳定合并。
- stable-error实验的合法ticker锚点为0，且事后诊断发现9/13 strict错误只是分隔符变体；尚无足量可识别的语义专业词纠错供给。
- 跨窗复现只证明有状态可测，不证明历史内容正确；summary/keyword loop尚未经过Omni多臂验证，GRPO与专业词纠错仍未放行。
- 首个完整滑动记忆实验虽把形式一致率提高11.42点，但未通过错配路由、收敛、WER、最差speaker和错误激活门，判为`LOOP-STABILITY-NOT-REACHED`；广播式recent-tail/长摘要不能作为稳定loop。
- 同chunk上一轮输出的稀疏检索也未形成可用稳定层：一致性较bare下降6.42点、路由仅1/4场胜出、错误候选激活54.98%；“会收敛”不能改写为“会优化”。
- 排除当前chunk后，跨chunk模糊检索有高覆盖但无相关性：候选gold精度仅1.93%，且出现`million/billion`等危险混淆；output-only字符串检索不能充当独立纠错证据。
- 每场一个外部公司身份也不足以支撑逐chunk纠错：四场仅15个纠错机会，冻结触发器precision 62.5%、recall 33.3%，且公开ticker registry不属于现有M0。
- 丰富官方材料仍未形成安全SUPPLY：30个参考机会中只正确触发3个，418次触发有415次错误，precision 0.72%、recall 10%；短缩写的字符相似匹配尤其危险。
- SAEA式Q-K-V结构不能只迁移外形：词法材料检索覆盖97.07%，但正确会议归属precision仅61.87%，只有Galp达到逐会门；跨场景retain/dispatch信号尚未建立。
- 语义归属通过仍不等于转写优化：当前未测候选wrong-to-correct、correct-to-wrong或WER，错配材料只可作为实验控制，不能作为部署选择器。
- Earnings-22已经没有严格reference-unread实验面：v2读取80场discovery，v3读取其余45场reserve；因此无法在该库建立新的独立3场开发+3场确认队列。
- 同事已接受另立construction-isolated复用实验以降低数据获取成本；其零模型门虽然通过，但不能修复历史参考暴露，也不能覆盖严格准入失败。
- construction-isolated确认集存在逐会异质性：三场precision为94.39%、77.27%和58.64%；当前只证明语义归属信号，尚未证明候选纠错、误伤控制或WER收益。
- construction-isolated确认只保存聚合指标，未保存逐turn dispatch身份与candidate value；636个聚合dispatch不能直接构造三臂runtime。primary opportunity census同样缺失，因此1,272-call Omni flight当前未放行。
- 新surface开发门选择的最低通过阈值为0.00，会全量dispatch；因此归属信号通过不能改写为已经找到
  有用拒绝门，也不能改写为WER或Omni correction增益。
- sealed confirmation虽已放行并完成80/80 Pass0，但材料snapshot在`ECV-0067`得到0个候选，低于
  每场8个的硬门；按预注册停止于0 embedding。因而开发集75%归属precision尚未得到独立确认。
- 新的LHCP-ASR surface已完成严格metadata-only准入：72/72音频路径与CERN contribution一一对齐，
  0孤儿/歧义且72/72有同期材料；该准入步骤本身不证明材料可读或候选供给充足。
- LHCP-ASR材料正文随后完成零模型审计：70/72场达到可读性与8候选门，开发25/25、确认45/47；
  其余70场候选中位142。两份test_2020 PDF触发固定解析器硬限，因此严格72/72供给门仍失败。
- 在不改变上述失败判决的前提下，已前瞻冻结70场material-compatible队列：25场开发、45场一次
  确认，精确排除两个parser失败项；独立复核`TRACE_COMPLETE`，且未读reference、未接触模型。
- 70场队列中的25场开发音频已reference-blind闭合：25/25 WAV共10.43小时，逐文件哈希和解码
  `TRACE_COMPLETE`；确认音频与transcription仍未读。该结果只放行另立固定前端审计，不证明转写收益。
- LHCP-ASR开发集固定前端的25/25次Sortformer调用均成功，25个RTTM和397个切片产物哈希闭合；这
  证明工具flight可执行，但不等于切片供给通过。
- 397片中有15个相邻边界重叠，影响10/25场、累计35.900秒、最大14.948秒；零重叠硬门失败，
  `FRONTEND_TRACE_COMPLETE`只能解释为结构完整，Pass0继续不放行。
- 独立切片器修复已将重叠连通turn作为原子块：复用同一25个冻结RTTM生成396片，0重叠、最大
  120秒、普通turn内部切点0且内部gap为0，判为`SLICER_OVERLAP_FIX_PASSED`。

## 当前研究状态

现阶段路线仍拆为两层。广播式、同chunk稀疏式和output-only跨chunk检索均已失败；字符与词法
材料路由也未过门。会议同期发布稿/演示材料已经形成合法`ORG`库存，而encode-only语义K在
同一Q/K/V和错配控制下首次通过结构门：归属precision 77.86%，较词法提高15.997点，且3/3场
过逐会门。这本来只放行独立未读会议上的retain/correct/deranged模型能力实验，但后续准入审计
确认Earnings-22严格未读会议为0，严格本会议top1/top2门因此按依赖规则停止，不能用同库复用
掩盖独立性缺口。降级的六场3+3 construction-isolated队列已完成1,639-call Pass0、开发阈值
拟合和唯一确认读取；阈值0.01在确认集达到76.10%归属precision和74.82%覆盖，证明探索性语义
dispatch信号存在。8月26日零模型前置审计进一步确认：现有确认文件没有逐turn trace，也没有
primary opportunity census，因而不能直接注册retain/correct/deranged三臂Omni flight。现已选择
EarningsCallVoice Core-100与FinCall-Surprise连接的新surface，不再对旧确认集事后物化trace。
2019+2020范围在排除1条网页暴露项后有69个候选，目标冻结20开发、40一次确认和9保留；该surface
是独立短片段能力验证，不能替代完整会议agent-loop确认。新运行从Pass0起保存请求、响应、上下文、
全部正确/错配候选与分数、selector判决及精确向量sidecar。该surface确认因一场材料供给不足停止；
后续找到的LHCP-ASR已闭合72场元数据join；材料供给审计70/72通过，但两场确认PDF无法由冻结
解析器读取。现已冻结25开发+45确认的70场eligible cohort；该操作只是缩窄证据总体，不是修复
72/72失败。25场开发的固定Sortformer虽全部成功，原turn-aware slicer因跨组重叠turn使零重叠门
失败；独立工程实验现已修复该边界问题并闭合396片供给。下一步可精确注册396-call开发Pass0，
但确认集继续sealed，Pass0与Omni仍不能直接接触。
第二层training-free
GRPO、GEPA、EM或多模态知识注入继续不放行。

最近的前端问题已经进一步回答：虽然参考已知主讲占主导时固定 Sortformer 可以保住主要主讲，
但仅凭 RTTM 无法安全识别这一子群。后续完整Pass0进一步确认stable exact-form错误存在，却没有
合法term锚点，而且多数是排版变体。因此term Pass1继续不放行。新发现的一场集中输出语言漂移
可作为独立可控性旁路，但必须与speaker-term主结论隔离。
