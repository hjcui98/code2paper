# Research → Method 第四次执行中方向复核（2026-09-13）

结论：继续 R10 的方向合理。当前代码已推进到提案提交、研究循环消费、promotion/retry 重算入口及
checkpoint/handoff 绑定，下一片应集中修正这些阶段之间的约束和对象一致性。
本轮复现了两个 P1、两个 P2；R10 还不能按“作者约束守恒、修订已完整消费”验收。
定向 Research 补证和实际调用计量仍需推进。本结论不要求笼统暂缓 R10，也不放宽任何准入门。

## 1. 本次观察范围与已取得的进展

- HEAD：`84371e4fee974071a580d7832af0ac14908c2d4b`，以当前大量未提交修改为有效基线。
- 本轮新跑固定范围集成/R10 测试：`39 passed`；目标提炼测试：`15 passed`，均 exit 0。
  这 54 项通过与下述跨阶段反例同时成立；不能据此声明完整 R10 或最新全量静态通过。
- 上轮 R9 发现已有对应修复接线：执行前拒绝冲突 call id、执行后冲突持久化、终态与 gap 消费端
  重新认证账本；提案请求摘要读取真实 `input_hash`，集成检查点覆盖分页到实际 Writer 请求 payload。
  旧探针的修复后结果保存在原目录，本轮没有把历史探针记录当成新跑结果。
- 新增 `research_revision_ingest.py` 和 `PROPOSE_TARGET_REVISION` 循环动作，实际应用路径已可达。
  文档中“supervisor/loop 尚未接线”已落后于代码，不能再按这个描述规划下一片。
- 组织提案仍标记 `proposal_call_accounting=recorded_not_in_invocation_plan`，请求有 trace
  不等于已纳入统一预留、发送前扣账及 durable receipt。
- 本轮只新增离线诊断和本报告、更新文档导航；未修改生产代码，未调用模型，未启动 live。

本轮探针复用了仓库现有中性项目和合法提案 fixture，经过真实 `execute_research_tool`、
代码读取账本、提案持久化与 `ingest_revision_submissions`，没有伪造 authenticated 标记。
目标提炼采用现有合法提案直接调用 `_apply_proposal`，不发送 LLM 请求。
29 个相关源码/测试文件在最终探针执行前后哈希一致；完整身份和结构化结果见：

- [探针脚本](</home/cuihengjia/agent/Code2Paper copy/.tmp/c2p-r10-direction-review-20260913/probe_boundaries.py>)
- [四组复现结果及源码哈希](</home/cuihengjia/agent/Code2Paper copy/.tmp/c2p-r10-direction-review-20260913/results.json>)
- [现有产物身份核对](</home/cuihengjia/agent/Code2Paper copy/.tmp/c2p-r10-direction-review-20260913/artifact-audit.json>)
- [本轮验证记录](</home/cuihengjia/agent/Code2Paper copy/.tmp/c2p-r10-direction-review-20260913/verification.json>)

## 2. P1-A：目标提炼之后，作者约束可以失去保护

`intent_target_proposer._apply_proposal` 整体替换 obligation 的目标，生成的每个目标都标记
`system_inferred`。随后 `revise_research_targets` 从这个当前图重新调用
`build_author_constraint_set`，后者跳过所有 `system_inferred`，没有读取提炼之前冻结的作者边界。

落点：[目标整体替换](</home/cuihengjia/agent/Code2Paper copy/src/code2paper/agentic/intent_target_proposer.py:840>)、
[新目标来源标记](</home/cuihengjia/agent/Code2Paper copy/src/code2paper/agentic/intent_target_proposer.py:894>)、
[作者约束捕获](</home/cuihengjia/agent/Code2Paper copy/src/code2paper/agentic/research_revision_contract.py:263>)。

**实测**（`cases.author_provenance`）：同一合法提炼将受保护 target IDs 从 **3 个变成 0 个**。
在原图直接删除首个作者目标被 `revision_author_constraint_deleted` 拒绝；经过提炼后，
同类删除通过实际提案入口被记为 `applied`，首个 obligation 的 graph targets 变为空，
journal 的 `coverage_denominator_ids=[]`，作者原文仍原样保留。

影响：单次提炼的谓词守恒检查无法保护后续修订；“保留作者原文”也没有保存可执行的约束边界。
这直接违背统一计划 §15.1 的要求。该探针没有生成 Candidate，不能扩展为已观察到正文错误。

**修复方向**：在 enrichment 前独立冻结真正的作者显式约束，并建立提炼目标与原约束的来源映射。
后续修订、coverage、checkpoint/resume 均读取同一冻结边界，不从可变图重建作者权威。
系统推断部分仍可修订；不能把全部 LLM 输出简单提升为作者权威。子问题也不应反向混入原始作者约束集合。

**验收**：串联“作者编译 → 合法提炼 → revision tool → harness → journal/resume”。
删除或泛化原作者约束必须拒绝，作者身份、具体谓词/条件/语义槽位与原始覆盖分母守恒；
合法推断层修订继续通过。单独测试作者图直接删除不足以覆盖本反例。

## 3. P1-B：修订更新了 graph，但 agenda 仍使用旧目标

`_revalidate_after_revision` 用新图计算未解析目标，却只更新 agenda item 的
`missing_information`、`status` 和 `supported_claim_ids`，没有同步 `typed_behavior_targets`。
随后又把 agenda 的 `intent_graph_digest` 改成新图摘要，形成“摘要绑定新图、目标仍属旧图”的状态。

落点：[agenda 更新集合](</home/cuihengjia/agent/Code2Paper copy/src/code2paper/agentic/research_revision_contract.py:1176>)、
[编译器从 agenda 取活动 obligation](</home/cuihengjia/agent/Code2Paper copy/src/code2paper/agentic/research_nodes.py:2685>)、
[实际对齐遍历 agenda targets](</home/cuihengjia/agent/Code2Paper copy/src/code2paper/agentic/research_nodes.py:3013>)。

**实测**（`cases.agenda_consistency`）：通过真实读取引用提交合法词表内的 `REDUCE` 新目标，
ingestion 返回 `applied`。同一 obligation 的 graph 有 **3 个目标**，agenda 仍只有 **2 个**，
但 `agenda.intent_graph_digest == graph.content_digest` 为 true。
P1-A 的删除对照也出现 graph 已删除、agenda 仍保留该目标。

影响：后续编译可能继续检查旧要求，漏掉新增要求；修订后的摘要一致不能证明实际消费一致。
本轮动态证据止于真实 runtime 对象，编译器消费来源由上述生产代码确认，未据此宣称某次终稿错误。

**修复方向**：把目标合同同步和相关派生状态重算放入同一次 revision 应用，验证 graph/agenda
按 obligation 的完整目标载荷一致后再提交摘要与 journal。新增、替换、删除三种路径都必须覆盖，
失效的目标标记也要按其所属 revision 处理。

**验收**：不能只断言 graph digest 变化或 journal entry 存在；必须检查实际 compiler 接收的新 targets，
再检查 coverage/claims、promotion/handoff 和 checkpoint/resume 使用相同修订。

## 4. P2-A：修订次数预算可被零预算提案绕过

`DEFAULT_REVISION_PROPOSAL_BUDGET=3` 注释定义为 harness 控制的每 run 修订次数上限，
实际扣减却完全使用提案者填写的 `budget_requests`；默认值及工具输入均允许 0。

落点：[接受后扣减](</home/cuihengjia/agent/Code2Paper copy/src/code2paper/agentic/research_revision_ingest.py:450>)、
[工具默认零预算](</home/cuihengjia/agent/Code2Paper copy/src/code2paper/agentic/research_tools.py:3274>)。

**实测**（`cases.zero_revision_budget`）：给 harness `remaining_budget=0`，提交四个不同 ID、
引用真实 span、使用注册谓词 `REDUCE` 的提案，全部 `applied`；四条 `budget_spent` 都是 0，
结束时 remaining 仍为 0。不是仅仅“默认上限 3 没有减到 0”，而是已经耗尽也能继续应用。

影响：新增 revision 上限没有生效。循环仍有总体 turn/tool 预算，本报告不把它描述为无限运行；
但修订还会重置该 obligation 的 post-partial retry，因此应连同跨修订历史一起核算。

**修复方向**：将 harness 修订次数上限、提案调用成本、子问题申请的研究额度明确区分。
一次应用的次数成本由 harness 决定，不能由提案者填 0 免除；搜索/模型预算从实际计划与调用计量。
把额度与已消费历史绑定 checkpoint/resume，不能重新创建上下文就恢复额度。

**验收**：零剩余额度拒绝；默认上限达到后拒绝后续不同 ID 提案；合法 replay 不重复收费；
连续 revision/resume 不重置 run 总账；拒绝和失败应用的收费策略明确且可追踪。

## 5. P2-B：封闭谓词和证据相关性检查没有覆盖真实提交入口

`build_subquestion_target` 有注册谓词/已观察谓词检查，但实际工具直接构造 `RevisionTargetV1`，
该模型没有同样的词表约束。ingestion 认证引用确实被读取，assessment 主要检查引用集合成员身份；
对新子问题没有验证该引用是否支持这次目标变更。

落点：[实际工具解析](</home/cuihengjia/agent/Code2Paper copy/src/code2paper/agentic/research_tools.py:3259>)、
[RevisionTargetV1](</home/cuihengjia/agent/Code2Paper copy/src/code2paper/agentic/research_revision_contract.py:113>)、
[证据引用检查](</home/cuihengjia/agent/Code2Paper copy/src/code2paper/agentic/research_revision_contract.py:558>)、
[仅 helper 中的词表约束](</home/cuihengjia/agent/Code2Paper copy/src/code2paper/agentic/research_revision_contract.py:874>)。

**实测**（`cases.unsupported_predicates`）：两个独立 runtime 都真实读取 `compute.py:1–4`
（参数、`sum(values)` 与除法）；随后分别提交未注册的 `UNREGISTERED_REVIEW_PREDICATE`，
以及已注册但该 span 没有支持的 `SERIALIZE` 子问题，两者均 `applied`、`failures=[]`。

影响：未观察引用已被阻断，但“观察过一个 span”仍可授权无关修订；helper 的通过测试不能证明
实际入口遵守同一合同。目标仍被标为 unresolved，没有直接变成 supported；问题是错误修订被应用。

**修复方向**：把允许的 target 类型/谓词/关系和适用的精确来源检查放到统一 harness 接受边界，
所有生产者都经过它。需要语义判断时调用独立复核或保持待审，不能让提案 reason 自签。
已观察、相关、足够支持修订是不同检查，沿用现有证据与语义验证机制。

**验收**：从真实工具入口提交未知词表、未读引用、已读但无关引用、错误 parent，以及合法相关对照；
分别检查 typed failure/待审与不变的 runtime/journal/作者分母。

## 6. 当前产物能证明什么

原始离线报告仍记录 887 atoms、131 页/4 worksets、三 phase 65/18/18，`failure_details=[]`。
五个准入失败码仍是两个 `operation_disposition_unresolved` 和三条 strict
`core_intent_partial_without_terminal_gap`。这些是已有离线产物的状态，本轮未重新跑冻结 Run E。

但产物索引存在两个实测不一致：

1. `offline-ebcar-r9.json` 的 archive 为 `sha256:58ad15ef…`，同目录 `r9-summary.json`
   仍是 `sha256:6b2ec29d…`。实施记录的 schema 身份变化与原始报告一致，汇总没有同步。
2. 汇总绑定的 21 个生产文件中，当前有 7 个不匹配；新 `research_revision_ingest.py` 未列入。
   七个文件是 `autonomous_method_agent.py`、`research_graph.py`、`research_models.py`、
   `research_nodes.py`、`research_revision_contract.py`、`research_tool_manifest.py`、`research_tools.py`。

因此，实施记录中的 `3405 passed` 是已记录的历史检查点，不能覆盖之后新增的循环接线。
更新 code-state manifest 也不能替代在对应代码上真正运行检查。应在固定检查点重新生成原始报告，
自动派生汇总，并把本轮入口/合同/测试和实际输入全部纳入身份绑定。

README、主计划和补证清单同时出现“R10 已实施”“尚未接线”“R10 未开始/继续暂缓”，需要统一为
“正在实施，已进入循环，跨阶段反例待修”。历史结论可保留为有日期的快照，不能继续充当当前阻塞理由。

## 7. 建议下一片的执行顺序

1. 先补 P1-A/P1-B：冻结作者边界、同步真实 agenda targets，并把两者串成连续修订/恢复测试。
2. 同一轮入口收尾解决 P2-A/P2-B：harness 计数、子问题独立额度、封闭词表与相关证据校验。
   暂不继续扩大 revision 动作种类和自动修订策略。
3. 做一次固定范围的完整 revision 检查点：提炼 → 提交 → 接受/拒绝 → 实际编译 → promotion/handoff
   → checkpoint/resume；保留旧 R9 拒绝场景。新增测试应覆盖跨阶段不变量，不能只镜像新增字段。
4. 将现有 Research 清单落成逐项补证记录：两个 mechanism 分解到具体 unresolved operation，
   三个 obligation 分解到未满足 targets，逐项写入口/配置/关系证据、查询范围、读取和未读 frontier、
   回执、停止原因与最终 disposition。表格列出“应查什么”尚不算完成补证。
5. 同步推进提案实际调用计量：完整请求对应 planned/reserved/measured/spent/unsettled，含失败尝试、
   retry 和恢复；真实 tokenizer 校准绑定实际模型与完整序列化请求，不能用预留余量冒充实测余量。
6. 在当前代码检查点上重新绑定离线链和汇总，再依据各阶段自身准入安排真实诊断。
   定向 Research 诊断不应被依赖其结果的 Writer admission 反向卡住；authoring live 仍需自身准入。

本轮命令与结果：

```text
python -m pytest -q tests/test_agentic_third_review_integration.py tests/test_agentic_research_revision_contract.py tests/test_agentic_revision_proposal_loop.py -p no:randomly
39 passed in 3.22s；exit 0

python -m pytest -q tests/test_agentic_intent_target_proposer.py -p no:randomly
15 passed in 1.00s；exit 0

PYTHONPATH=src python .tmp/c2p-r10-direction-review-20260913/probe_boundaries.py
四组探针均完成并复现上述缺口；probe_errors={}；model_call_attempts=0；exit 0
```

以上结果只绑定本轮工作树和 fixture，不是 live、Candidate/Verified、D5 或切换验收结论。
