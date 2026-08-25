# 阶段性结论

最后更新：2026-08-25。

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

## 当前研究状态

现阶段路线仍拆为两层。广播式、同chunk稀疏式和output-only跨chunk检索均已失败；字符与词法
材料路由也未过门。会议同期发布稿/演示材料已经形成合法`ORG`库存，而encode-only语义K在
同一Q/K/V和错配控制下首次通过结构门：归属precision 77.86%，较词法提高15.997点，且3/3场
过逐会门。这本来只放行独立未读会议上的retain/correct/deranged模型能力实验，但后续准入审计
确认Earnings-22严格未读会议为0，严格本会议top1/top2门因此按依赖规则停止，不能用同库复用
掩盖独立性缺口。降级的六场3+3 construction-isolated队列已完成1,639-call Pass0、开发阈值
拟合和唯一确认读取；阈值0.01在确认集达到76.10%归属precision和74.82%覆盖，证明探索性语义
dispatch信号存在。下一步可另行注册retain/correct/deranged三臂Omni能力实验，但仍须另外取得
新会议或独立测试集，才能主张泛化并测WER、误伤、最差speaker和成本。第二层training-free
GRPO、GEPA、EM或多模态知识注入继续不放行。

最近的前端问题已经进一步回答：虽然参考已知主讲占主导时固定 Sortformer 可以保住主要主讲，
但仅凭 RTTM 无法安全识别这一子群。后续完整Pass0进一步确认stable exact-form错误存在，却没有
合法term锚点，而且多数是排版变体。因此term Pass1继续不放行。新发现的一场集中输出语言漂移
可作为独立可控性旁路，但必须与speaker-term主结论隔离。
