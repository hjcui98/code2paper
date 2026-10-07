# Code2Paper 文档导航

本页是仓库文档的权威入口。文档中的日期表示快照时间，不代表它仍描述当前状态。
若历史报告与规范文档或当前状态报告冲突，以“规范 → 当前状态 → 历史证据”的顺序
解释。

## 当前状态

- [DSH M01–M03 独立验收及 P 段接续](dsh_execution_20260928/stage05_M_acceptance_20261007.md)：Gate-M PASS、28/49；当前完整2103/fresh cold1和实际多步/独立compaction/原账本/恢复释放证据闭合，审查读集释放。当前推进 P01–P04，保留 Gate-P/G0/G 阶段验收；资格限显式V2 Host API，normal JSON CLI仍V1。

- [DSH L01 独立验收及 M 段接续](dsh_execution_20260928/stage04_L01_acceptance_20261006.md)：packet26 一次真实执行，合法 research_required → waiting、usage 8055/441、自然释放，独立 Gate-L PASS；25/49，实际 primary 13，正式进入 M01–M03。完整19实际1997及 fresh cold 1；旧14费用UNKNOWN保留。兼容验收不代表正文或 Verified 完成。以下 L01 返修记录为历史快照。

- [DSH Gate-L 集中解阻与连续执行：原长期模块 §9](dsh_execution_20260928/stage04_06_long_module_execution_20261004.md#gate-l-unblock-20261005)：历史 Gate-L 解阻入口；当前已独立 PASS，M 段以本页首条和长期文档 C 段为准。该快照统一处理显式非thinking＋强制原生terminal、完整wire/服务端兼容、错误流计量及packet14具名恢复包，收口后一次完整/cold与独立QA；通过Gate-L再连续M/P/G。仅更新指导和接续字段，24/1/24、Gate-L FAIL、费用UNKNOWN/原owner held不变，未新增模型或恢复授权。

- [DSH L01 packet14 错误流与 unknown 计量返修](dsh_execution_20260928/stage04_L01_provider_error_repair_evidence_20261005.md)：一次执行遭服务端grammar FSM错误，无usage/finish/tool。实际费用UNKNOWN，原owner held；独立Gate-L FAIL/436输入及读集释放。已实施显式非thinking与独立Writer预算、原发送门、错误流矩阵及具名UNKNOWN恢复合同；首次整包QA的U1–U3已修；完整10实际1867/cold1及原两reader通过，最终QA仅U4类型弱匹配并已释放读集，集中修复后新完整11待冻结；真实终止/独立操作授权仍缺。历史完整1819仅f82/5951，24/1/24。

- [DSH L01 packet13 与原生工具选择返修（2026-10-05）](dsh_execution_20260928/stage04_L01_native_tool_choice_repair_evidence_20261005.md)：packet13领域FAIL，原费用7699/pending0、原owner自然完成释放、六条严格history、独立生命周期PASS及实际读集释放。最终tool-choice.2来源构建/wire对照、真实native三项和严格runtime审计通过；新完整/cold09待最终冻结，历史1803仅7f77/af9。24/1/24，Gate-L FAIL；新模型须fresh包具体一次授权。

- [DSH L01 packet12 未注册工具返修（2026-10-05）](dsh_execution_20260928/stage04_L01_unknown_tool_repair_evidence_20261005.md)：一次授权已消耗、原领域FAIL。受信完成/诊断/历史退役路径经真实native、聚焦和保护克隆；独立代码/方案PASS/APPLIES及实际退役PASS、读集释放，原费用7648/pending0、canonical empty、原42非lease文件/14输入及7费用事实不变。当前关闭后冻结新完整/cold（05），历史1707仅9def/7b77；Gate-L FAIL、24/1/24，新模型必须fresh具体一次授权。

- [Author Intent 主导的 Method Authoring 闭环修复执行文档（2026-09-16）](intent_spine_authoring_closure_repair_execution_2026-09-16.md)：
  绑定 `/tmp/c2p-production-entry-20260915-live10`，确认本次两节 `Sym:*` Candidate 的首因不是 intent
  缺失，而是 executable mechanism owner 被错误提升为 Narrative section owner：无 symbol owner 的 story
  node 未进入 mechanism context，五节作者计划只能事后按 exact anchor 回贴。文档同时纠正 44/11/25%
  obligation–candidate 统计键，并在独立复核后补入 7 个 legacy 公式需求与 84 个 mechanism 义务的
  canonical identity bridge、统一公式内容门、逐 claim exact/semantic 验证状态、原子化跨文件负例和 clean
  Candidate 事务。文档给出 P0–P7 实施顺序与 EBCAR 验收反例。当前为根因与执行方案，
  不表示生产代码或新 live 已完成。
- [生产入口收敛执行文档（2026-09-15，第二次核验修订）](research_to_method_production_closure_execution_2026-09-15.md)：
  当前执行入口，细化统一计划 §15.7。按 A 完整准备合同 → B 合法成果续跑与全文集成 → C 真实全文 Candidate
  及正常产品入口交付推进。有限必修项 F1–F6：row/片段、handoff 后追加导致请求漂移、正文旧计划投影、
  已结束 Formalizer 阶段读取、正常产品入口 tokenizer、Editor/Rewrite 辅助调用计量。
  新探针确认 18/18 Writer envelope 被后追加 handoff 改变；r5 的 32 个包均能从片段重建并通过当前绑定校验，
  其中 13 个来自 partial 回执。明确正常 `method-agent run` 验收，不以 replay 成功代替产品入口成功。
  prepare/execute-prepared 与统一调用账本等实现已落地；2026-09-15 后续又修复 Research 配置事实持久化、
  语义进度/质量状态、Narrative→Method 唯一锚点适配、Candidate/结构/CLI/replay 终态门、公式内部语法泄漏、
  Rewrite 上下文预算及累计 usage 账本。全量静态 3582 passed、3 skipped；新的正常入口 live Candidate
  仍待验收，不能把旧 replay 或静态通过当作产品交付。
- [全流程现状与交付纠偏（更新至 2026-09-15 r5 终态）](research_to_method_end_to_end_status_review_2026-09-14.md)：
  最新全文 r5 exit 2，在试分页请求构造时把候选小段落换回旧完整段落，误要求小页包含 detail 13；
  零网络原 helper 对照已复现，原 helper 还会丢掉 4 个新片段 ID。单页 r7 已有提交/零新增发送 resume，
  全文仍无 Candidate。r2–r5 共登记 216 次相同批次的 Formalizer
  请求，均未进入 Writer；32 个 accepted 包覆盖 83 条 preferred 义务中的 32 条，不能当作论文公式质量完成。
  当前代码已有请求计量驱动的重分页；本次零网络 r4 回放证明 payload 层 19→21 段、18 页、义务集合守恒，
  完整请求/全文验收仍未证明。具体执行以本页首条收敛文档和统一计划 §15.7 为准。
  本次 107 项相关静态通过，生产代码未修改、新模型调用 0。下列条目均按各自历史时点解释。
- [合同修复后的单页真实验收结果：统一执行计划 §15.6.8](research_to_method_unified_repair_execution_plan_2026-09-12.md)：
  两份冻结响应的离线验收通过（0 模型调用）：标题表示恢复保留 1,369/1,532 字符正文，detail 22 的
  13 个 shape atoms 不再被 `+1` 误判，repair 已展开逐 atom 缺口且单页脚本共用生产 assessor。
  全新 r3 prepare 通过；8006/qwen38 真实 live 严格发送 1 primary + 1 repair，provider prompt
  为 49,704/53,909，usage/finish 均齐全，但 required target contract 仍未闭合，两个 receipt
  均 rejected、无提交、未 resume。当前没有 Candidate；不得重放这两个失败请求或启动完整 authoring。
  [离线证据](../.tmp/c2p-s39-contract-repair-20260914/inspection.json)与
  [`live_result.json`](/tmp/c2p-s3-single-page-20260914-02a75-r3/live_result.json)绑定本片。
- [真实单页失败后的合同修复：统一执行计划 §15.6.7](research_to_method_unified_repair_execution_plan_2026-09-12.md)：
  离线对照定位标题指令冲突、CALL 的 shape 参数 `+1` 被误判为顶层加法，以及 aggregate-detail
  repair 反馈未展开 atom 的问题。分离已知标题后两次真实响应仍有 1,369/1,532 字符正文，
  格式误判消失但仅闭合 4/6 个 required atoms。先修合同与共用生产验收，再重新 prepare/live；
  本次模型请求 0，[对照证据](../.tmp/c2p-s38-next-step-review-20260914/inspection.json)。
- [S3.7 → 单页真实验收操作单与实际结果：统一执行计划 §15.6.5–§15.6.6](research_to_method_unified_repair_execution_plan_2026-09-12.md)：
  加法→乘法/丢加数/否定加法三个反例当前均拒绝。已交付单页 `prepare/live/resume` 入口并将
  实际 tokenizer/wire 计量接入发送门；原空页 02a75… 的 prepare 通过，真实 live 已执行
  1 次 primary + 1 次 repair（53,931 / 55,013 input），但两次内容验收均拒绝，未提交、未
  resume、未产生 Candidate。详见 §15.6.6 及
  [`live_result.json`](/tmp/c2p-s3-single-page-20260914-02a75-r2/live_result.json)；不得
  重复当前失败或继续完整 authoring。
- [S3.6 独立复核纠偏：统一执行计划 §15.6.4](research_to_method_unified_repair_execution_plan_2026-09-12.md)：
  Formalizer 单次真实 accepted package 保留；后续 exact-excerpt 词汇回退可将加法错写成乘法的
  正文绑定为完整 detail，必须先收紧。r6 的 24-witness 局部通过不等于 repair 提交；当前低层
  微测未覆盖统一预算/content receipt/resume。先修绑定、对齐生产微测入口和真实计量，再整链。
  本次模型请求 0，相关测试 173 passed，新增错误绑定反例仍成立；
  [反例及复核记录](../.tmp/c2p-s36-independent-review-20260914/review.md)。下列记录按各自时点解释。
- [Research → Method 统一执行计划 §15.6：S3-20 终态复核与收口（2026-09-14）](research_to_method_unified_repair_execution_plan_2026-09-12.md)：
  当前入口已跨过 S1，S2 累计发送账本已接线；S3-20 最终有 116 个 completed receipts、113 次发送及
  execution record，exit 2，仍无完整 Candidate。Formalizer 66 次调用、0 accepted packages；
  Writer 18 页最后响应为 5 空、3 仅标题、10 含正文文本（未等同内容验收）；Realizer 完成 15/18 页，
  三个 witness repair 均成功，另三个 primary 被总输入预算拒绝。下一步是失败协议记录与 Formalizer 完整 schema、
  Writer 有效段落事务、retry reserve/后续 primary 保护和真实计量，再验证恢复并做完整 authoring。
  不重做 S1/R10，不再无变化整轮重跑；本次复核模型调用 0，相关流式测试 6 passed。
  [复核结果](../.tmp/c2p-s3-review-20260914/results.json)与[文件摘要索引](../.tmp/c2p-s3-review-20260914/evidence-index.json)
  绑定本次读取的代码/产物；下列早期报告中的“当前”“未修复”按其各自时点解释。
- [Research → Method 交付检查点复核（2026-09-14）](research_to_method_delivery_checkpoint_review_2026-09-14.md)：
  S1/S2 修改前的历史检查点：三次 C 真实回放已有 111 次正文前模型调用，正文仍为 0；当时直接阻塞是 replay 继续消费冻结 Run E 的旧行为图。
  使用第三次回放的相同 facts/claims/配置/分区，仅请求当前 adapter 重建，125/185 operations 变为
  157/217（各新增 32、删除 0），两个机制完整性均通过。配置缺证不是这两处失败的直接原因。
  分支修复仍有嵌套 if/elif/提前 return 反例；提案计量尚未约束累计 run 额度，且保存失败、损坏恢复、
  未声明角色及 tokenizer 缺失仍可发送。执行顺序收敛为真实入口与当前图一致、确定性预检前移、
  累计发送预算闭环、一次受控正文交付；A/B 不再按整体完成记录。本次复核 50 项相关测试通过，
  独立对照模型调用 0，未修改生产代码。执行任务已回写统一执行计划 §15.4（S1 → S2 → S3），
  包含负责文件、验收反例与退出产物；当前协议为 8006/qwen38。旧报告与实施记录按其绑定时点保留。
- [Research → Method 产品主链诊断与推进指导（2026-09-13）](research_to_method_product_delivery_guidance_2026-09-13.md)：
  最新独立复核将当前直接阻塞定位为 AST 顺序边跨越 if/else 互斥分支，导致 dominance 伪造路径极性冲突。
  零模型因果对照仅在内存支配遍历排除两条源码证明的跨分支边，157/217 个 operation 数不变，
  6/2 个 unresolved 均归零，两个机制完整性通过；生产修复尚未落地。Candidate Research gate 已通过，
  三条 strict partial 单独保留。执行顺序收敛为分支语义修复 → Candidate 实际准入与调用计量闭环 →
  一次受控 EBCAR 正文交付；R10 已进入循环，保留现有修复，扩展不作首份正文前置。
  本条修正下列补证记录中“两个结构门直接归因配置缺证”“所有正向补证都须先关闭 frontier”及
  “合成池 7/9 resolved 等于生产补证进度”的解释。历史探针保留，不能替代真实 packet/claim/handoff 消费。
- [Research → Method 第四次执行中方向复核（2026-09-13）](research_to_method_repair_direction_review_2026-09-13_round4.md)：
  四项跨阶段反例（P1-A 作者约束经提炼失去保护、P1-B graph/agenda 目标不同步、P2-A 零额度仍可应用修订、
  P2-B 未知谓词/无关引用被接受）已在同一轮内修复，状态统一为“R10 正在实施，已进入循环，跨阶段边界已修，
  完整验收未完成”。修复后同一探针（`.tmp/c2p-r10-direction-review-20260913/results.json`，模型调用 0）
  复现结果为：提炼前后受保护目标均非空且删除被拒（`revision_author_constraint_deleted`）、
  graph 与 agenda 目标载荷逐字一致、剩余额度为 0 时四个零预算提案全部拒绝
  （`revision_application_budget_exhausted:0/3`）、未注册谓词拒绝
  （`revision_predicate_unregistered`）而“已读但无关引用”转待审（`revision_predicate_unsupported`）。
  离线证据已在本检查点重新派生：`.tmp/c2p-unified-repair-20260913-r10/offline/offline-ebcar-r10.json`
  与由它生成的 `r10-summary.json`（24 个绑定文件同源，archive `58ad15ef…`、887 atoms、131 页/4 worksets、
  三 phase 65/18/18、`failure_details` 为空、五个准入失败码不变），修正了旧汇总 archive 摘要不一致与
  7 个文件漂移。提案调用计量已实现到 caller 边界（`proposal_call_accounting.py`：planned/reserved/measured/spent/unsettled、失败/retry/resume、envelope 派生 meter 且拒绝伪造实测；11 项测试 + `artifacts/06_authoring/proposal_call_accounting_v1.json` durable 产物），剩余 run 级预留并账与真实 tokenizer 校准；五个 Research 缺口补证进行中（两轮确定性证据见上条）。本轮无模型调用、无 live。
- [Research 五缺口逐项分解与首轮定向证据（2026-09-13）](research_gap_evidence_2026-09-13.md)：
  由冻结产物与确定性检索派生的逐项分解：两个 mechanism 仍需在 `mechanism_context_set_v1.json` 上重跑
  completeness 编译器才能列出未处置 operation；三个 strict obligation 中两个各有未 resolved target
  （`FILTER`/`MASK` 等），而 `O-STAGE-01-039a963a` coverage 为 supported、没有 target 缺口，其 strict
  失败须在 claim/qualifier 侧定位；三个未 resolved target 已完成首轮定向检索（命中模型/入口文件、
  读取 span、账本回执），但 `search_frontier_closed=false`，故按 R9 规则保持 unresolved；
  第二轮确定性编译探针进一步显示两个 `FILTER`/`MASK` 缺口在冻结树中已有可编译证据
  （MASK 被生产抽取器识别并编译为 supported fact，target 对齐 resolved），Run E 未解决属搜索/
  读取覆盖问题；该结论有界（合成 obligation、整文件编译），不写回 disposition、不关闭 frontier。
  两个 mechanism 已逐 operation 分解（157/217 个 operation 中分别 6/2 个未处置，terminal coverage
  均为 1.0），8 个未处置 operation 全部落在掩码装配/传入注意力层的分支上，直接上游是
  `self.cfg.use_dedicated_attention` 配置声明 `state=unresolved`（无 definition/entrypoint span），
  两处 frontier 仍未关闭（33/6 个未读命中，回执已记录）。阻塞点是承载这些 operation 的 supporting
  detail `active_path_status=unknown`；配置选择证据本轮取得 `conf/config.yaml:19` 的
  `use_dedicated_attention: True`、`CONFIGURED_BY` 分支 `if self.cfg.use_dedicated_attention:` 与入口消费
  （`train_ebcar.py:116`、`main.py` OmegaConf loader），mechanism 2 的 active-path 已可判定，
  守卫链已完整取得（`main.py:24` hydra 装配 → `train_ebcar.py:136` 无条件构造 → `__init__:22`
  构造编码器 → `145–174` 的 `use_dedicated_attention` 分支）：mechanism 2 的 operation 位于消融
  `else` 分支（取值 `True` 下不活跃），mechanism 1 的 operation 在无条件调用链上（活跃）；
  判定所需的取值/定义/入口/守卫证据齐备，但 frontier 仍未关闭，尚无 disposition 写回。
  三条 strict 失败已精确定位：strict lane 读 research agenda，三条 must_cover 均为 `partial`
  且 `gap_requirements=0`（各自已有 1–11 条 supported claim），未满足 typed 要求分别为
  `FILTER`/`SELECT`/`TRANSFORM`/`transformations:scores`；需补证据或写 terminal `explicit_gap`。
  未满足要求的定向检索已记录线索与回执（`SELECT`→`topk`/`src/utils.py:41/51`；`scores`→
  `MS_MARCO_v2/preprocess.py`；`FILTER`→`main.py:34`；`TRANSFORM` 仅有配置/依赖噪声），
  三组 frontier 均未关闭（未读 26/16/9），未写回负结论。对候选文件的编译探针显示：三条 strict
  obligation 中 9 个相关 target 有 **7 个在冻结树内即可对齐 resolved**（TRANSFORM、SORT、MASK
  均有可编译事实），缺口属搜索/读取覆盖问题；结论有界，不写回 disposition。
- [Research → Method 第三次执行中方向复核（2026-09-13）](research_to_method_repair_direction_review_2026-09-13_round3.md)：
  原复核及修复后的独立验收合并记录，最新结论见 §5：18 个生产文件哈希一致、集成测试 4 passed，
  条件旧反例、跨修订额度、提案进入 plan 已得到验证。后续探针仍复现执行后才拒绝 ID 冲突导致候选
  未入账，以及损坏账本后的旧 gap 仍被终态/加载器接受；提案预算、请求摘要及真实分页→Writer
  请求验收仍待完成。先补这些边界，继续准备定向 Research 补证与计量校准；R10 暂缓。
  （历史快照：R10 其后已进入循环并完成跨阶段边界修复，当前状态以本页第一条与实施记录为准。）
- [Research → Method 第二次执行中方向复核（2026-09-13）](research_to_method_repair_direction_review_2026-09-13.md)：
  对当前工作树的一次独立零模型复核，给出 P1-A–P1-F 六项可复现缺陷、修复方向与执行顺序
  （先阻断未认证负证据并修条件/分页，再统一章节身份，再补 callback 权威差异与跨修订扣账，最后集成检查点）。
  本轮实施记录与证据见 `.agent/implementation.md` 的 2026-09-13 小节和
  `.tmp/c2p-unified-repair-20260913-r9/offline/r9-summary.json`。
- [Research → Method 第一次执行中方向复核（2026-09-12）](research_to_method_repair_direction_review_2026-09-12.md)：
  R5–R8 的第一轮独立复核，本轮 P1-A/P1-B/P1-C 的旧反例来源。
- [Research → Method 统一下一步修复执行文档（2026-09-12，现状更新至 2026-09-14）](research_to_method_unified_repair_execution_plan_2026-09-12.md)：
  当前执行入口为 §15.6 的 S3 收口；§15.4 保留 S1 → S2 → S3 的原验收合同。
  当前图与预检、累计账本和发送前 started 已实际消费；剩余重心是有效内容、跨阶段预算和可验证的恢复。
  R10 作者约束、提案/harness/journal、循环提交和修订绑定已有实现，保留成果，不重做 R0–R10。
  S3-20 有部分正文、仍无完整 Candidate；三条 strict partial 单列，不额外要求先完整 Research 重跑。
  §15.6 已给出负责文件、当前反例、首次至多六次微测建议和完整交付退出条件；附录 B 同步。
  模型为 8006/qwen38-27b-nvfp4，context 131072；保留上位架构、09-08 Unified 结构门与最终质量门。
  原 R0–R10 分片设计、盲修采纳及历史静态/离线数据保留在对应章节，按绑定时点解释。
- [Unified Context 第一轮修复后真实测试失败复盘、全局设计修订与第二阶段执行方案（2026-09-08）](dyg_mamba_unified_live_run_failure_diagnosis_and_remediation_2026-09-08.md)：
  以 `7701a7e` 的未完成 DyG live 为第一份真实证据，重新审计上一轮 P0–P9，而不是把 189 页和
  `160 obligations × 189 pages = 30,240` 次最坏请求当作 DyG 局部故障。确认根因是全量证据归档、
  consumer workset 和实际 invocation plan 混为一个 manifest，并伴随 source replay 断链、无 owner
  seed 传递合并、结构 gate fail-open 和不可恢复调用。本文提出三层上下文合同、owner-first closure、
  page-centric Formalizer、统一 live admission、durable receipt，以及 offline 十项目 → 三项目 pilot
  → 十项目 live 的第二阶段顺序；并进一步给出 V2 schema、逐函数修改表、严格调用上界、失败码、
  V1→V2 迁移、实施切片和测试命令。不是 live acceptance 或 cutover 结论。
- [十项目 Method 信息缺失根因、Unified Context 设计修订与优化执行方案（2026-09-06）](code2paper_unified_mechanism_context_quality_failure_diagnosis_and_optimization_execution_plan_2026-09-06.md)：
  基于 GPU 1 十项目原文、代码、Research trace、中间 IR、Candidate/Verified 和关键日志，确认
  本轮真实入口均未启用 unified、七项目 callback 命中同一未定义 digest helper、作者意图虽在
  九项目形成 213 个 facet 但完整代码蕴含为 0。本文保留 Unified Mechanism Context 主方向，
  新增 run/source/promotion/mechanism/formula/page-delivery 五类合同，并把执行顺序改为先修真实
  接线与 offline reconstruction，再做 scope、Research、context、formula、Writer 和十项目 live
  验收；不放宽 Verified 硬门，也不把原论文变成 implementation authority。
- [Method Authoring 原文可推断性、公式丢失根因与下一阶段执行计划（2026-08-29）](method_authoring_original_equivalence_diagnosis_and_next_execution_plan_2026-08-29.md)：
  对照 EBCAR、DyG-Mamba、LinearRAG 原文、作者意图、真实代码、人工盲测和 8006 最终产物，
  区分可直接恢复、代码等价推导、意图/纸码差异和不可授权效果；确认真实 dossier/derivation
  为空、Formalizer 正确公式被 consumer 路由拒绝、Writer 粒度过细和 evaluator 漏记拒包是
  当前主损失。下一步先以 EBCAR 做 Method Unit、consumer-first 公式、精确公式插入和独立
  Binder 的单项目闭环，再泛化到 LinearRAG 与 DyG-Mamba。本文承接 2026-08-28 手册，
  不替代总体架构或放宽 Verified 硬门。
- [Research-Derived Method Authoring 下一阶段执行优化手册（2026-08-28）](code2paper_research_derived_authoring_optimization_execution_2026-08-28.md)：
  基于最新 EBCAR、DyG-Mamba、LinearRAG 真实产物与只看意图/代码的人工盲测基线，确认
  当前主要损失来自连续代码链缺失、Formalizer 多义务路由丢包、Writer 同步 witness 失败及
  Candidate 审计措辞污染；给出 connected dossier、typed derivation、AI-first Formalizer、
  两阶段 Writer/Binder、Candidate/Verified 独立完成语义和三项目真实回归的代码级执行顺序。
  它承接 2026-08-27 工作包并受 2026-08-22 执行权威约束，不修改 Verified 硬门。
- [Method Authoring 原文—意图—代码—运行链质量诊断与下一阶段执行计划（2026-08-27）](method_authoring_source_ledger_quality_execution_plan_2026-08-27.md)：
  基于三篇原文、作者意图、实际代码、冻结研究轨迹与 `225116` 产物，把质量损失分为
  not-discovered、discovered-but-blocked、rendered-low-quality 和 intent-code mismatch；
  定义 source-to-render 内容追踪、字段级对齐、段落合同、consumer-first Formalizer、
  semantic-delta repair/callback 及逐文件 WP0–WP7。这是 2026-08-22 执行权威之下的下一阶段
  工作包，不替代总体架构、Writer 规范或 Verified 门。
- [Method Authoring 最近六轮产物、分析与修复汇报（2026-08-27）](method_authoring_six_round_report_2026-08-27.md)：
  绑定 2026-08-25 23:09 至 2026-08-26 23:23 的 gated replay（`230920`→`011745`→
  `090052`→四洞修复+`211757`→薄内容修复→`225116`）。只证明该窗口的代码、冻结研究、
  模型与协议；不是执行权威，不是 `publication_ready` / D5 / §8 PASS。
- [Method 意图优先写作：质量失败诊断、架构修订与代码级执行计划（2026-08-22）](method_intent_first_authoring_redesign_2026-08-22.md)：
  绑定 DyG/LinearRAG live `133302`。Candidate 改为作者逻辑完整叙述 + 语义许可 +
  写作期回搜代码 + 学术 Formalizer + Rewrite 去代码味；Verified 仍 fail-closed。
  落实 2026-07-31 Writer 规范 §1.3/§1.6，并修订 2026-08-21「许可层纯确定性」仅针对
  Candidate 措辞权。这是 Method Authoring 质量的当前执行权威；不是新的总体架构规范，
  不得一次 `/implement` 全文。
- [Method 论证包编译：用一次综合编译替换逐 cluster Concept Card（2026-08-21）](method_argument_brief_compile_replacing_concept_cards_plan_2026-08-21.md)：
  冻结 Research 之后不再默认逐 cluster 生成 Concept Card；改为子句级许可的论证包。
  WP-A/B/C 已于 2026-08-22 只读验收 PASS。Candidate 语义许可与写作回搜以 2026-08-22
  意图优先计划为准。不是新的架构规范。
- [Method Authoring R5 质量退化根因与分片执行路线图（2026-08-20）](method_authoring_r5_quality_root_cause_and_code_execution_plan_2026-08-20.md)：
  R5 冻结 authoring 质量诊断与 WP0–WP6 分片。WP0 拷贝边界与后续 Writer/Formalizer/
  callback 门仍有效；WP1 把 Concept Card 写入 `--rebuild-authoring` 主链的部分由
  2026-08-21 论证包方案改道。不是新的架构规范，不得一次 `/implement` 全文。
- [Method Agent 现状复盘、Master Agent 主线与下一阶段代码级修复方案（2026-08-17）](method_agent_master_agent_mainline_execution_repair_plan_2026-08-17.md)：
  用户确认的新 Method Agent 唯一交付主线和独立上位文档；按实际代码梳理三条现存路线、
  当前模块与调用链，定义 Master Agent 顶层 LangGraph、现有研究子图复用、Concept Card
  精确绑定、真实研究回调、Writer 兼容迁移、父子检查点、旧路线冻结、逐文件修改和故障
  测试矩阵。该文件在上述范围内取代旧执行计划，高于一次任务的 `.agent/` 协调文件，
  但不取代总体架构和 Writer 规范。
- [R8 六项目验收状态（2026-08-01）](r8_acceptance_status_2026-08-01.md)：
  当前 R8 pass/fail 的权威入口；六项目 6/6 accepted，并记录 matrix、报告 digest、
  resume digest、统一 17 项硬门以及尚待完成的 clean-checkout release freeze。
- [项目进度与目标差距报告（2026-07-31）](project_status_and_gap_report_2026-07-31.md)：
  已更新到 2026-08-01；以 R8 实际通过为基线评估产品目标剩余差距。
- [R8 后 Research Agent 具体开发执行计划](post_r8_research_agent_execution_plan_2026-07-31.md)：
  将总体设计映射到当前代码、阶段性 R8 数据、具体修改模块和逐批退出条件。
- [R8 四项目 Method 与原论文覆盖审计](r8_method_paper_coverage_audit_2026-07-31.md)：
  对照 RAP、EBCAR、DyG、LinearRAG 的原稿、代码、claims 和最终正文，定位信息
  丢失、paper-code mismatch 与 deterministic prose repair。
- [可投稿 Method Writer Agent 设计](publication_ready_method_writer_design_2026-07-31.md)：
  把事实验证与论文论证分层，定义多权威写作、argument graph、专用
  Architect/Writer/Formalization/Editor、写作中返回研究和 publication utility
  验收。
- [根 README](../README.md)：安装、入口和两条运行路线。
- [迁移与切换指南](agentic_migration_guide.md)：`shadow → opt-in → canary →
  default_ready` 的正式切换规则。

## 规范性设计

下列文档规定系统应该如何工作，而不是记录某次运行结果：

- [自主错误反馈与自修复原则](agentic_error_feedback_and_self_repair_principle.md)：
  validator 发现的实质错误必须返回 owning Agent 做有界修复；不得靠降级硬门、
  静默过滤或缩减义务来通过；最终正文词句必须来自 Writer/Rewrite。
- [结构化输出恢复策略](agentic_structured_output_recovery_strategy.md)：
  harness 可修复简单语法损伤；内容、引用和证据错误必须交回 Agent。
- [鲁棒 LangGraph Research Agent 总体设计](agentic_robust_langgraph_research_writing_design_2026-07-19.md)：
  当前自主研究写作架构与信任边界。
- [可投稿 Method Writer Agent 设计](publication_ready_method_writer_design_2026-07-31.md)：
  Writer 子系统的当前规范；说明代码缺失、作者确认、形式化、文献和实验等不同
  authority 如何在不放松真实性的前提下形成完整论文叙事。
- [Method 质量下一阶段执行计划](agentic_method_quality_next_execution_plan_2026-07-19.md)：
  R0–R8 的历史实施基线；当前进度和下一批开发由 R8 后执行计划跟踪。

## 外部实现参考

- [Code2Paper × DeepSeek Harness 插件集成设计（2026-09-22，09-28 执行拆分）](code2paper_dsh_plugin_design_20260922.md)：
  代码对照基线为 `0918ee7`，文档读取 HEAD 为 `d48b4e4`，DSH 源码参考为 `c36a83ff`；4014 passed 回执仅绑定代码基线。
  保留 DSH 执行 Agent、LangGraph 默认业务流程、Code2Paper 领域权威与验收提交；并发默认关闭。
  实施收窄为兼容性 mock → 原 owner 的不可变发布/注册修复 → 唯一 Writer 合同无模型往返 → 单 run 串行 DSH mock，
  再经单独授权验证小型 Qwen live；多步/compaction、共享调度与完整主图分别后置。
  Python 账本唯一权威，模型/Host/操作者接口分离；真实 Research 图逐节点跨进程恢复是 WP5 独立门。
  已有 `0.1.5-rc.3` [隔离环境](../integrations/dsh/dev/README.md) 保留为历史对照；2026-09-29 用户选定 `0.2.0-rc.1` 为新开发候选，
  目标补丁开发候选已于2026-10-03通过下方独立Gate-B/H验收，并完成正式Gate-K登记；日常 `0.1.7-rc.2` 保持使用，不授权生产切换。
- [Code2Paper × DSH 分阶段执行计划（2026-09-28）](dsh_execution_20260928/README.md)：
  将总设计拆成 8 份执行文档、49 个单元；明确责任文件、依赖、首次派工、共享接口和验收门。
  **2026-10-04 当前：[GC集中返修独立验收](dsh_execution_20260928/stage03_gc_repair_acceptance_20261004.md) Gate-C PASS，GC-1/2/3关闭。第01–03份完成，17 done /0 in_progress /32 planned。** 下一批扩大为[第04–06份长期模块](dsh_execution_20260928/stage04_06_long_module_execution_20261004.md)，23项连续责任，默认单主执行者、按需协作；§8可直接转交。先完成第04份七项离线工作，沿原Gate-R/V/L/M/P/G0/G接续到完整流程接线；具体live准入保持。计划扩大未计实现进度，下方旧裁决、派工和计数按各自时点解释。
  2026-10-03 最新 owner：[第03份 GC集中返修新封存](dsh_execution_20260928/stage03_gc_repair_delivery_20261003.md)，submitted_for_independent_qa；原独立 CHANGES_REQUESTED 保留，待整包复验，第04份未启动。
  2026-10-03 23:03 前次独立裁决：[第03份 r2 独立 Gate-C 验收与集中返修指令](dsh_execution_20260928/stage03_gate_c_review_and_batch_repair_20261003.md)。Gate-C CHANGES_REQUESTED；三组真实入口缺陷为 Unicode terminal 判定、旧材料 prepare、投影证据引用完整性。独立105/265/123/48及真worker主链通过；当前11 done /6 in_progress /32 planned。按新报告§3–§6一次返修并重新封存，第04份仍未启动，Gate-B/H/K已验结论保留。
  2026-10-03 18:03 [四组返修独立验收与阶段接续](dsh_execution_20260928/stage_four_group_repair_acceptance_20261003.md)：Gate-B/H PASS，四组关闭；791份未变内核与既有component结论支撑正式Gate-K PASS。两侧原93、B02 48、身份24及原来源/生命周期、真实入口反例与正常smoke独立通过；201份封存和108990个归档成员核验一致。第01/02份完成，台账11 done / 38 planned；第03份具备前置但未实施，下面旧记录按原时点解释。
  下一批按[第03份整批执行指令](dsh_execution_20260928/stage03_batch_execution_instructions_20261003.md)连续完成I01/C01/C00/C02–C04；§3/§4为两窗口责任，§5–§7为交接、测试和封存，§8可直接转发。发布派工文档未改变任务实现状态。
  2026-10-03 16:05 [冻结整包独立 Gate-H 审查](dsh_execution_20260928/stage_whole_package_review_20261003.md)：两侧原93/0skip、来源各10/10、生命周期各3/3；交付B02 26/身份24/doctor/正常HTTP与独立types通过。GHS-1/GHS-2已关闭，剩余activate/audit失败边界、smoke staging绑定及交付/回归覆盖；Gate-H/K未过。1275输入/四runtime/peer未变并明确释放，窗口二按新报告§3–§4连续收口，窗口一保持791项未变内核。
  2026-10-03 [全部剩余工作与整阶段修复指导](dsh_execution_20260928/remaining_work_and_batch_repair_guidance_20261003.md)集中核对第九轮 owner 交付、当前确定缺陷/验证缺口及后续 38 项 planned 工作；按整阶段连续修复，保持 Gate-H/K 未过与原任务依赖，不把指导或 owner 自测当作新验收结论。
  保留 `0918ee7` 与隔离 `0.1.5-rc.3` 历史基线，新目标为 `0.2.0-rc.1` 候选；单 Writer 离线闭环优先，执行组成身份、真实测试覆盖回执各设独立任务，
  完整 LangGraph 迁移、显式并发、审计 §16.3 及默认切换逐阶段验收。[B00 开发输入冻结](dsh_execution_20260928/b00_baseline_freeze.md)
  已完成并经独立 QA 通过；旧版 PASS 保留，新候选 Gate-B/H/K/C 的范围见上方裁决。当前继续按整阶段负责：
  一个主执行者依[长期模块](dsh_execution_20260928/stage04_06_long_module_execution_20261004.md)连续承担当前已激活阶段的Python、TS和联测，按需要拆分协作；
  共享协议/validator与peer/build各始终一位实际写者，单人模式均由主执行者承担；原两窗口分工只是可选方案，
  QA 按 [验证文档](dsh_execution_20260928/verification.md) 在完整阶段包就绪后启动独立验收，不常驻第三窗口；普通缺陷由原 owner 连续修复。
  单元本地合同通过即可在阶段内继续开发；原 AT、独立 QA、depends_on 完成前置与 Gate-R/V 不减少。
  2026-09-30 21:36 后，返修差分已实际验收：内核103项与K04/身份/真实调用方282项、原反例及实际consumer成立，owner4129完整全量日志/退出码已核对，K01–K04 component PASS。DSH74项与B02原目录23项、普通Web/compat真实HTTP通过，但公共同request引用和NO_ADAPTER回落仍可抢票，第01份CHANGES_REQUESTED，Gate-H/K未过；第03/04份未启动。
  QA已结束并明确释放实际读集，完整裁决见[返修差分验收](dsh_execution_20260928/stage_repair_acceptance_20260930.md)与[DSH独立报告](dsh_execution_20260928/gate_h_repair_independent_review_20260930.md)。窗口一保持已验内核候选，窗口二连续完成原剩余AT；当前分支/环境/写权与两位接手者的完整指令见执行入口§3.7和裁决§5，历史§§3.3–3.6及旧报告保留；LEAD保持协调与裁决角色。
  2026-10-01 R2历史裁决见[原报告](dsh_execution_20260928/stage_r2_acceptance_20261001.md)。11:36最新[返回闭包差分裁决](dsh_execution_20260928/stage_handle_acceptance_20261001.md)：owner84项已核对，独立原stream三个对照通过，原公开prepareCall仍能取闭包，H-R4真实exit1。Gate-H/K未过；QA已明确释放，窗口二续第01份来源及身份收口，窗口一只读调查已交付/保持component。当前安排见执行入口§3.9，原8份文档/49单元不变。
  2026-10-01当前FAIL-CLOSED候选71pass/13skip，合法child也拒绝，H04/Gate-H仍未通过；[LEAD接口裁决§6](dsh_execution_20260928/h04_loop_origin_escalation_20261001.md)已授权窗口二新隔离runtime来源补丁候选，原43490765…树保留。按执行入口§3.10连续完成可信loop派发、全部原正反例/13项恢复与新身份冻结；ALS原样方案需补public prepared入口与不可变核验边界。窗口一保持已验内核，不重复调查/全量；无常驻QA。
  2026-10-01 19:40当前[loop-origin.1独立裁决](dsh_execution_20260928/stage_loop_origin_acceptance_20261001.md)：新候选已实装，原H-R4公开prepareCall反例独立通过、合法child恢复；普通公开调用、公共NO_ADAPTER、旧manifest入口出现回归，源码/types/私有consume合同未齐。Gate-H仍CHANGES_REQUESTED，QA已明确释放实际读集，窗口二按执行入口§3.11连续整包返修；窗口一保持791条Python源/测试与六份原日志同身份的component，不重跑4129。以下阶段仍排队，原接口裁决§6继续有效。
  2026-10-02当前[返修差分裁决与完整续派](dsh_execution_20260928/stage_loop_origin_repair_acceptance_20261002.md)：原86/0skip实测记录保留，独立LO1–3通过、固定源码/types实际交付；公开admit仍可被观察者预消费，交付与source-built均有真实失败及合法对照。Gate-H/K未过。1023输入/四棵runtime/peer不变、宿主进程核对完成后明确释放；窗口二按执行入口§3.12整包返修，窗口一保持已验内核。上批候选内raw根当前不可读，历史不补造，新证据封在稳定根。两窗口环境与后续第03/04完整分工见新裁决§§2–8。
  2026-10-02 12:12最新[私有消费候选独立复核及完整返修接续](dsh_execution_20260928/stage_private_consumption_review_20261002.md)：交付原套件独立87/0skip、显式B02 24/doctor通过；两棵候选的prepared/fallback正对照通过，但同步internal/get仍能预消费公开entry-ack，公开Symbol.asyncIterator获取仍见外层来源，各2个真实失败；实际manifest/生成器漏列2份types。Gate-H/K未过。992输入/四runtime/peer未变并明确释放，窗口二按执行入口§3.13连续原整包返修，窗口一保持791源/测试未变的component。此前86/公开admit裁决保留历史范围，原8文档/49任务、后续03/04分工及所有门不变。
  2026-10-02 14:48最新[能力门控候选独立复核与整包接续](dsh_execution_20260928/stage_capability_entry_review_20261002.md)：交付原87/0skip、显式B02 24/doctor独立通过；新探针交付4/5、源码构建3/5。公开resolver转发Proxy可截获真实capability并预消费，两侧合法child error/零RDSadapter；源码侧iterator获取仍见来源。四文件清单已修，当前身份/API声明未统一。Gate-H/K未过。本批1054输入/四runtime/peer未变且自身读集已释放；另有owner源码构建验证仍活跃，窗口二先收尾它再按执行入口§3.14连续原第01份整包。窗口一保持已验component，原8文档/49任务、03/04后续分工与所有门不变；更早记录按旧候选解释。
  2026-10-02 22:10最新[模块级派发候选Gate-H独立审查](dsh_execution_20260928/stage_static_entry_gate_h_review_20261002.md)：两侧原套件各89/0skip，原三类反例、Web/compat HTTP、交付B02 24/doctor通过；公开`streamWithRegistration(...,true)`可取得受信派发并发送替换材料，销毁重建后合法回落失败，候选types非固定源码tsc输出，源码构建侧B02缺worker。Gate-H/K未过。1134输入/四runtime/peer未变，22:10:34明确释放、相关验证0；窗口二按执行入口§3.15连续原第01份整包，窗口一保持已验component，原8文档/49任务与所有门不变。
  两阶段通过后才进入第 03/04 份 Writer 合同与串行闭环集成；live、完整主图和默认切换仍另过门。
- [五个 Agent 仓库的代码级参考研究（2026-08-10）](reference_agent_framework_code_research_2026-08-10.md)：
  面向当前 Research Agent 与 Method Writer 目标，对 Hermes Agent、OpenClaw、OpenHands SDK、
  PydanticAI 和 PydanticAI Harness 的固定版本进行文件/核心代码级比较；属于架构参考，
  不替代规范、执行计划或验收状态。
- [五个 Agent 仓库运行时深挖（2026-08-10）](reference_agent_framework_runtime_deep_dive_2026-08-10.md)：
  展开关键调用链、候选/提交/崩溃状态机、失败矩阵和外部测试代码证明链，并标明源码、测试、
  推断与采用建议的证据等级。
- [外部 Agent 机制落到 Code2Paper 的逐函数蓝图（2026-08-10）](reference_agent_framework_code2paper_blueprint_2026-08-10.md)：
  校正本项目已实现机制，定位 budget、QualityState、semantic frame、callback receipt、terminal
  identity 等真实调用链缺口，并给出文件级落点与纵向故障测试矩阵。

## 操作与验证

- [Agentic 路线迁移指南](agentic_migration_guide.md)
- [R8 设计差距审计快照](agentic_design_gap_audit_2026-07-21.md)
- [Gemma-4 R8 历史进度报告](agentic_r8_gemma4_progress_report_2026-07-20.md)

R8 日志与临时产物用于诊断，不是长期文档。正式验收结论必须绑定 matrix ID、
干净检出、配置、模型/API provenance、产物摘要和最终 recheck 报告。

## 历史设计与审计

这些文档保留决策背景和演进记录，不应单独用于声明当前能力：

- [早期最终设计](agentic_refactor_final_design.md)
- [分阶段执行计划](agentic_refactor_phased_execution_plan.md)
- [早期路线图](agentic_refactor_roadmap.md)
- [V2 研究写作设计](agentic_research_writing_agent_v2_design.md)
- [V2 执行计划](agentic_research_writing_agent_v2_execution_plan.md)
- [P4 完成审计](agentic_refactor_completion_audit.md)
- [Behavior template 过渡参考](agentic_behavior_template_transition_reference_2026-07-19.md)

## 机器可读证据

`docs/*.json` 是带日期的验收、评测或 rollout 证据快照：

- `agentic_p4_*_2026-07-18.json`：P4 review、adjudication 和 rollout 记录；
- `agentic_real_*_2026-07-18.json`、`agentic_domain_pruning_*`：真实项目基线；
- `agentic_rap_gemma*_2026-07-19.json`：RAP/Gemma 质量实验；
- `agentic_cutover_review_gate_2026-07-18.json`：历史 cutover 决策。

这些文件只证明其固定 commit、输入和协议下的结果。旧协议成功不能自动升级为
当前协议成功。

## 文档维护约定

1. R8 pass/fail 更新 R8 状态报告；项目级进度更新目标差距报告；实验细节写入新的
   带日期报告。
2. 状态报告必须写明 `as_of`、实际/假设状态、范围和证据位置。
3. 规范变化直接更新规范文档，并在状态报告中说明影响。
4. 历史报告原则上不重写结论；若已过时，在顶部添加 superseded 提示。
5. 不把 `/tmp` 路径、未结束日志或工作区测试通过数写成正式验收结论。
6. 默认路线切换只能由 migration/cutover 门禁授权，不能由单次 R8 代替。

- [Gate-H 四组集中返修 owner 提交（2026-10-03）](../integrations/dsh/dev/gate_h_repair_batch_20261003.md)：两侧原93项、来源/生命周期、B02 48项、正常smoke身份和完整输入封存已交；791份内核保持。owner submitted_for_independent_qa，Gate-H仍待独立复验，正式Gate-K与后续第03份等待。

### DSH 当前实施证据（2026-10-04）

第03份[GC返修新封存](dsh_execution_20260928/stage03_gc_repair_delivery_20261003.md)经[独立复验通过Gate-C](dsh_execution_20260928/stage03_gc_repair_acceptance_20261004.md)，I01/C01/C00/C02–C04登记done，GC-1/2/3关闭；49项为17 done/32 planned。QA于00:15:40+08明确释放读集，协调更新与受测身份分开记录。下一步按[第04–06份长期模块](dsh_execution_20260928/stage04_06_long_module_execution_20261004.md)推进，默认串行负责、协作按需，当前仅发布扩大后的计划；局部pending_validation义务保留，真实live仍单独准入。
