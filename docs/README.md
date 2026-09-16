# Code2Paper 文档导航

本页是仓库文档的权威入口。文档中的日期表示快照时间，不代表它仍描述当前状态。
若历史报告与规范文档或当前状态报告冲突，以“规范 → 当前状态 → 历史证据”的顺序
解释。

## 当前状态

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
