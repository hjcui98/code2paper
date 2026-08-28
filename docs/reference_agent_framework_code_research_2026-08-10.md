# 五个 Agent 仓库的代码级参考研究：面向 Code2Paper Research Agent

> 日期：2026-08-10
>
> 性质：外部实现研究与架构参考，不是 Code2Paper 规范、状态证明或完成账本
>
> 范围：Hermes Agent、OpenClaw、OpenHands SDK、PydanticAI、PydanticAI Harness 的固定版本
>
> 方法：只读静态代码研究；未运行这些项目的测试、模型调用或真实 API

> 第二轮深化：本文保留为综合结论入口。逐调用链、状态机、失败矩阵和外部测试证明链见
> `reference_agent_framework_runtime_deep_dive_2026-08-10.md`；对当前 Code2Paper 工作树的
> 逐函数差距、已实现能力校正和实施/测试切面见
> `reference_agent_framework_code2paper_blueprint_2026-08-10.md`。

第二轮核对纠正了第一版的两个过度概括：当前 Writer callback 已有 request/section/unit/lane、
artifact digest 和 affected-only resume 的耐久闭包；研究 loop checkpoint 也已使用内容寻址的
不可变 payload。因此深化结论不再建议重建这两套机制，而聚焦其剩余的 validator receipt、
accepted artifact closure、budget 实际落账和 terminal same-identity。

## 1. 结论先行

这五个仓库没有一个可以整体替代 Code2Paper 当前架构。Code2Paper 的核心难题不是
“如何让 Agent 循环起来”，而是如何在循环、重试、回调、压缩和恢复之后，仍然证明：

1. 最终 Method 中的正面实现事实来自冻结仓库证据，并通过反向验证；
2. `EvidencePacketV3 -> CodeFactV1 -> AtomicClaimV3 -> MethodArgumentUnit -> final span`
   的绑定没有被摘要、投影、改写或恢复过程篡改；
3. 失败回到真正的 owning Agent，且只重跑受影响单元；
4. 候选尝试、最佳状态、预算、checkpoint 和最终验收属于同一运行身份；
5. 安全门和论文效用门保持正交，缺失输出不能被解释为成功。

最值得吸收的不是某个框架的表层 API，而是以下运行时不变量：

| 优先级 | 可吸收的不变量 | 最强参考来源 | 对 Code2Paper 的价值 |
|---|---|---|---|
| P0 | 权威事件/产物与面向模型的投影分离 | OpenHands `EventLog`/`View` | 压缩和上下文选择不能改变事实权威 |
| P0 | candidate 与 accepted attempt 之间的提交栅栏 | OpenClaw `run-entry.ts`、Hermes `CompressionCommitFence` | 失败候选不能污染最佳状态、checkpoint 或回调结果 |
| P0 | 精确 ID 绑定的 deferred request/result | PydanticAI `_deferred.py` | 写作回调可按 request/obligation/unit 精确恢复 |
| P0 | 从多个不变量的交集推导安全切分点 | OpenHands `View.manipulation_indices()` | 不拆开 packet/fact/claim、callback/result/resume 等原子组 |
| P1 | 副作用开始/完成/失败/崩溃未知的耐久收据 | PydanticAI Harness step persistence、OpenClaw delivery evidence | 防止 resume 后重复写入或把未知副作用当作未执行 |
| P1 | 操作 ID、输入指纹和 compare-and-set | PydanticAI Harness memory store | 使局部修复和产物提交可幂等、可检测冲突 |
| P1 | 类型化重试状态和按作用域预算 | Hermes、OpenClaw、PydanticAI | 防止全局盲重试和预算泄漏 |
| P1 | 图拓扑静态校验、计划依赖和整体批次校验 | Pydantic Graph、Harness planning | 在模型执行前拒绝死端、循环依赖和非法状态跃迁 |
| P2 | 有顺序语义的 capability/hook 组合 | PydanticAI capabilities | 将持久化、观测、预算做成正交横切层 |
| P2 | 大结果的 lossless spill + 有界句柄读取 | Harness tool output limits | 控制上下文体积而保留可追溯原文 |

同时，有几类实现不能直接照搬：fail-open 的上下文插件、best-effort checkpoint、
进程内收据、无内容摘要 digest、基于标题/关键词的“质量验证”、固定邻域的 tool-pair
搜索、截断后的摘要权威、独立子 Agent 预算，以及让 LLM judge 覆盖确定性验证结果。

## 2. 本项目的筛选基线

本报告按仓库内现有权威顺序解释需求：

1. `docs/agentic_robust_langgraph_research_writing_design_2026-07-19.md` 规定总体架构、
   `CodeBehaviorGraph`、证据层级和“LLM 提议，证据授权”的信任方向；
2. `docs/publication_ready_method_writer_design_2026-07-31.md` 规定事实层和论证层分离、
   Architect/Writer/Formalizer/Editor/Rewrite 的作者边界，以及写作返回研究；
3. `docs/post_r8_research_agent_execution_plan_2026-07-31.md` 是当前执行权威，要求
   owning Agent 修复、per-obligation budget、最佳状态、轻量 checkpoint 和同身份验证；
4. `.agent/task.md`、`.agent/plan.md` 仅作为当前 D5 round-4 的任务级补充：特别要求
   relation/predicate-aware semantic frame、精确 move authority、claimless obligation 保留、
   自然触发 callback 与 affected-only resume。

因此，外部机制只有在不改变上述事实权威和 fail-closed 门禁的前提下才可采用。

### 2.1 当前代码中的对应落点

| 现有职责 | 当前实现入口 | 本报告关注的问题 |
|---|---|---|
| 研究状态与最佳状态 | `research_models.py:730-858` `QualityStateV2`；`research_nodes.py:2778-2823` | candidate/accepted 是否明确，恢复是否仍为同一身份 |
| 图循环与 checkpoint | `research_graph.py:230-517, 603-1006, 1492-1840` | 快照引用、终态 resume、尝试边界和副作用一致性 |
| 研究工具与事实数据面 | `research_tools.py:1808-2698` | packet→fact→claim→coverage 是否保持精确 lineage |
| 原子写与工具缓存 | `tool_runtime.py:31-99` | 是否需要副作用收据、输入指纹和冲突检测 |
| Method Architect | `method_architect.py:54-78, 329-695, 1034-1065` | semantic frame、move 与 authority lane 是否精确绑定 |
| Authoring projection | `authoring_projection.py:33-252, 398-599` | 投影能否压缩但绝不成为事实源 |
| Authoring plan/gate | `authoring_plan_v3.py:113-174, 176-577, 642-701` | 拓扑、claimless obligation、非法依赖是否执行前拒绝 |
| 写作回调 | `writer_research_router.py:30-213` | request/result/affected units 是否有精确耐久绑定 |
| 形式化与作者账本 | `formalization_agent.py:18-184`；`final_text_authorship.py:22-224` | 改写后原作者和事实授权是否仍可反查 |
| 安全与效用验收 | `publication_quality.py:23-1154` | 两轴是否独立，move witness 是否绑定准确 span |
| resume 校验 | `checkpointing.py:25-193` | checkpoint 只存引用/digest 时如何检验完整闭包 |

## 3. 研究范围、版本和限制

| 仓库 | 固定 HEAD | 研究状态 |
|---|---|---|
| Hermes Agent | `326bdfb7a27e292a25aa1a8a073e6fac43460a98` | 工作树干净；读取核心运行时、压缩、工具、子 Agent 与验证账本 |
| OpenClaw | `8fdf7570a17ffbbafe825bd379bab858f263b8ca` | 工作树干净；仓库为 sparse/partial clone，只研究本地已物化文件 |
| OpenHands SDK | `be6cd3b80b706bb14c91e604581a8de75cad61cc` | 工作树干净；读取 event/view/condenser/agent/executor/goal 代码 |
| PydanticAI | `fc6a3ac506513150e2016ee5ba9785d792795150` | 工作树干净；读取 agent graph、capability、deferred、usage、graph builder |
| PydanticAI Harness | `5e180850511dec469cc50aa9853675a8031d1f19` | 工作树干净；读取 persistence/workflow/planning/compaction/memory 等模块 |

OpenClaw 的 sparse checkout 主要包含 `packages/agent-core/**`、
`src/agents/embedded-agent-runner/**`、`src/agents/agent-hooks/**`、compaction、queue、lane、
heartbeat、cron 和相关概念文档。尝试读取 sparse 集之外的对象会触发 promisor remote，
当前环境无网络而失败。因此，本报告对 OpenClaw 的结论只覆盖列出的本地代码，不声称
覆盖整个仓库。该限制不影响本文采用的 attempt、delivery evidence 和 compaction 结论。

## 4. Hermes Agent：提交栅栏、请求投影和验证证据陈旧化

Hermes 最有价值的部分不是主循环，而是它对“同一个 turn 内的可变尝试状态”做了相当
细的工程拆分。其设计适合帮助 Code2Paper 定义 attempt 层，但不能用作事实权威层。

### 4.1 上下文选择只修改请求副本

`agent/context_engine.py:89-292` 的 `ContextEngine` 将 `compress`、
`prune_tool_results_only`、`select_context` 和 `on_turn_complete` 分开。
`select_context()`（`215-247`）明确是每次请求的上下文选择接口，不应修改持久 transcript。
`agent/conversation_loop.py:1286-1368` 在应用 selection 前深复制结构，并在返回后校验。

可采用的原则：

- `AuthoringInputProjection`、Writer brief、压缩摘要都应是“请求投影”；
- 投影的输入必须是不可变 artifact ref/digest，投影结果不能回写覆盖源 artifact；
- 投影失败时可以回退到较大的安全投影，但不能绕开事实门。

需要收紧之处：Hermes 的 selection 插件倾向 fail-open；Code2Paper 对展示优化可以
fail-open，但对 authority projection 结构验证必须 fail-closed。

### 4.2 压缩进展是可计算条件，不是“模型说已压缩”

`agent/turn_context.py:292-336` 的 `compression_made_progress()` 把进展定义为消息行减少，
或 token 至少下降约 5%，并据此决定是否再进行 preflight。这个模式可用于 Code2Paper 的
no-progress 规则：每次 repair 必须带来可度量的 obligation 状态、错误集合、授权 anchor
或正文 witness 的变化，不能只比较自然语言“看起来变好了”。

### 4.3 `CompressionCommitFence` 是通用 attempt commit 模型

`agent/conversation_compression.py:284-384` 先 snapshot/restore 压缩器尝试状态；
`CompressionCommitFence`（`445-620`）区分：

- commit 前可取消；
- `begin_commit()` 取得提交权后，取消不能与提交竞态；
- admission 可以撤销；
- `commit_in_flight` 可观测；
- release 绑定实际 holder，避免旧任务释放新任务的锁（ABA 类问题）。

映射到 Code2Paper：Research/Architect/Writer/Editor 的每次输出都应先形成 candidate，
完成确定性 gate 后才一次性切换 accepted ref。取消、超时或较差 candidate 只能记录为
discarded，不能先改写 incumbent 再尝试恢复。

### 4.4 工具执行中的 exactly-once dispatch 和持久化顺序

`agent/tool_executor.py:141-157` 拒绝非 JSON object 的工具参数；`178-206` 在展示工具
进度前先 flush session DB；`391-467` 是并发 authorization gate；`482-664` 的 middleware
将授权后的 dispatch 放进锁保护路径，避免重复执行。

这提示 Code2Paper 将工具生命周期拆成：validate → authorize → reserve budget → record
started effect → execute → atomically persist artifact → record committed receipt → expose result。
当前 `tool_runtime.py` 已有原子写和幂等 cache，但尚可增加 started/unknown-after-crash
语义，而不是仅依赖“结果文件是否存在”。

### 4.5 子 Agent 句柄是能力边界，不是普通字符串

`agent/subagent_lifecycle.py:34-147` 定义不可变 launch request、带父绑定签名的 handle、
terminal state 和含 `result_hash` 的结果；`198-345` 管理 launch/wait/cancel/result/reconnect；
`408-477` 计算终态 hash；`480-540` 保证 child scope 不扩大 parent capability。

可借鉴于未来 Formalizer/Reviewer 并行化：child 只能获得明确的 artifact refs、允许工具、
预算和输出 schema，结果通过 hash/ref 返回。不能直接照搬之处是该 registry 主要是进程内
状态；Code2Paper 的验收链要求耐久 handle 和可恢复结果。

### 4.6 验证证据会随工作区编辑变陈旧

`agent/verification_evidence.py:36-48` 的 `VerificationEvidence` 记录 command、canonical
command、kind、scope、status、exit code、cwd/root/session 和输出摘要；`414-458` 分类命令；
`528-572` 记录证据；`575-626` 在工作区编辑后把既有验证标为 stale。

这是 same-identity 验收很好的最小模式。Code2Paper 应进一步绑定 repo snapshot digest、
输入矩阵 digest、模型配置、artifact closure digest 和协议版本；只有命令文本和输出摘要
仍不足以证明产物没有在验证后改变。

### 4.7 Hermes 的采用判断

| 机制 | 判断 | 原因 |
|---|---|---|
| request-only context selection | 采用并收紧 | 适合 projection；authority validation 不得 fail-open |
| candidate commit fence | 强烈采用 | 直接解决 incumbent 污染和取消/提交竞态 |
| exactly-once tool middleware | 采用其状态机 | 需换成耐久 effect receipt |
| signed child handle | 条件采用 | 未来多 Agent 有用；先做耐久 artifact binding |
| verification staleness | 强烈采用 | 是 same-identity 的必要组成 |
| 独立 child iteration budget | 不直接采用 | 无法表达整个 research/writing 树的共享总预算 |

## 5. OpenClaw：accepted attempt、终态事实和可观测副作用

OpenClaw 的强项是一个成熟的对话式运行器如何处理 provider fallback、终态、恢复、
context engine 和已发送副作用。它提供 attempt 层的强参考，但它的“已送达”不等于
Code2Paper 的“事实已授权”。

### 5.1 只有 accepted attempt 才推进逻辑 turn

`src/agents/embedded-agent-runner/run-entry.ts:33-124` 给候选尝试和终态结果定义类型；
`resolveTerminalStatus()`（`152-169`）将 timeout/abort/error 等收束为终态；
`canAdvanceContextEngineTurn()`（`171-187`）只允许 completed、ok、非 yield、非 abort 的
尝试推进 context engine。

同文件约 `420-508` 的关键行为是：accepted candidate 才 finalize context engine turn；
未接受候选只 discard candidate intent，`finally` 还会清理未 settle 的 intent 和 lease。

这是 Code2Paper 当前最佳状态选择应显式化的协议：

```text
attempt started
  -> candidate artifacts written under attempt_id
  -> deterministic validation report
  -> accepted: atomically repoint incumbent + checkpoint refs
  -> retry/discarded/blocked: preserve audit, do not advance accepted lineage
```

### 5.2 typed attempt recovery，避免异常字符串驱动控制流

`run/attempt-recovery.ts:39-138` 把恢复结果定义为 `complete | retry | proceed`，并将
terminal facts 结构化。`run-loop.ts:141-250` 同时维护 retry budget、context recovery、usage、
terminal retry、idle breaker、post-compaction guard 和 tool outcome ordinal。

对本项目的启发是：validator 不应只返回 message；应返回 owner、failure type、scope、
affected obligation/unit/span IDs、是否已产生外部副作用、允许的下一动作和是否计费。
这与当前 `PacketRepairRequestV1`、writing callback 路由方向一致，但还需统一 attempt terminal。

### 5.3 retry budget 区分“发起过尝试”和“应计费恢复”

`run/retry-budget.ts:1-39` 区分 dispatched attempt 和 counted recovery；某些有实际进展的
continuation 不计为 recovery。`terminal-retry-state.ts:1-22` 则把终态修订次数单独计数。

Code2Paper 可以采用“分类后计费”，但退款条件必须更严：仅 representation-only、无新模型
调用、无事实变化且协议明确授权的恢复可不消耗内容修复预算。不能因为工具“有进展”就
自动退款，否则会削弱 per-obligation 的有界性。

### 5.4 delivery evidence 让重复发送风险可判定

`src/agents/embedded-agent-runner/delivery-evidence.ts:16-99` 记录细粒度 side-effect facts
和 final source reply marker；`385-543` 聚合 committed delivery evidence。其重要判断是：
如果存在无法归因到具体 send 的粗粒度发送，就不能安全重试，因为可能已经发生外部副作用。

这应映射为 Code2Paper 的 `ArtifactEffectReceiptV1`：即使写文件通常可通过原子替换幂等，
仍需区分 started、committed、failed 和 unknown-after-crash；未知状态必须阻止自动重放，
直到通过目标 digest/readback 完成 reconcile。

`tool-send-receipts.ts` 的 consume-once map 可解释进程内去重，但不是耐久证明，不能作为
最终验收依据。

### 5.5 压缩 safeguard 可用于 UX，不可作为证据 gate

`src/agents/agent-hooks/compaction-safeguard-quality.ts:14-225` 要求摘要章节、隔离不可信
指令、提取 opaque identifiers，并用关键词重合审计摘要；`compaction-safeguard.ts` 约
`652-720` 保留 recent turns/tool pairing，约 `1041-1242` 做有界重试和 last-good fallback。

值得借鉴的是：不可信文本标记、精确 ID 保留、有界重试、失败时取消 compaction。
不能借鉴的是：用标题和 token overlap 证明事实完整。Code2Paper 的摘要必须携带源 artifact
refs/digests 和确定性 closure 校验；文字相似度最多是诊断信号。

### 5.6 lifecycle generation 防止旧运行拥有新会话

`run-state.ts:75-191` 用全局映射和 lifecycle generation 驱逐旧运行；关键顺序是先移除
旧 ownership，再 abort 旧 driver，避免旧 callback 继续以当前 owner 身份写状态。

这对 affected-only resume 很重要：每个 accepted section/unit 应绑定 generation 或
incumbent digest。旧 repair 完成时，若它的 parent digest 已非当前 incumbent，应记录为
stale candidate，不能覆盖新结果。

### 5.7 OpenClaw 的采用判断

| 机制 | 判断 | 原因 |
|---|---|---|
| accepted attempt 推进 turn | 强烈采用 | 最贴合 best-state/checkpoint 语义 |
| typed terminal/recovery facts | 强烈采用 | 可统一 validator→owner repair 控制面 |
| delivery evidence | 采用其判定思想 | 文件 artifact 需 content digest/readback |
| lifecycle generation | 采用 | 防止迟到修复覆盖新 incumbent |
| compaction exact-ID preservation | 采用 | 只保护投影，不授权事实 |
| heading/token-overlap audit | 仅诊断 | 不能证明证据和 claim 完整性 |

## 6. OpenHands SDK：事件账本、投影不变量和安全切分点

OpenHands 对 Code2Paper 最重要的贡献，是把“完整事件历史”和“给模型看的 View”明确分开，
并让 view 操作服从一组可组合的不变量。这个抽象比一般聊天摘要更接近本项目的证据链。

### 6.1 `EventLog` 是持久源，`View` 是可变投影

`openhands-sdk/openhands/sdk/conversation/event_store.py:30-57` 定义持久 `EventLog`；
`91-126` 处理 parent 兼容、root path 和 cycle；`184-228` 在 append 时加锁、同步磁盘、
拒绝重复 ID 和不存在的 parent。

`context/view/view.py:22-160` 的 `View` 则是投影。`manipulation_indices()`（`39-50`）
取所有 property 允许边界的交集；`enforce_properties()`（`74-109`）递归到 fixed point；
追加 condensation 时只改变 View，不改 EventLog。

建议映射：

- `ResearchEventLogV1` 保存 observation、packet、fact、claim、validation、callback、rewrite、
  acceptance 等不可变事件；
- `ResearchProjectionV1` 只引用 Event IDs/artifact digests，供某一 Agent 请求使用；
- checkpoint 保存 accepted head、projection recipe 和 digest，不保存可冒充事实源的自由摘要；
- 任意 projection 都能回到完整 authority closure。

### 6.2 四个 property 可推广为 Code2Paper 原子组

OpenHands 的 properties 分别位于：

- `context/view/properties/batch_atomicity.py:10-94`：同一 response 的 actions 是原子批；
- `observation_uniqueness.py:18-77`：每个 tool call 只认第一个 observation；
- `tool_call_matching.py:15-87`：action/observation 精确匹配，二者之间不可切分；
- `tool_loop_atomicity.py:14-116`：thinking 与连续 tool loop 构成原子组。

Code2Paper 可定义自己的投影不变量：

1. `EvidencePacketV3 -> validation -> CodeFactV1 -> validation -> AtomicClaimV3 -> authorization`
   对每个 claim 的最小权威闭包不可被切断；
2. `WritingResearchRequestV1 -> owning-agent result -> route validation -> affected-unit resume`
   不可被切断；
3. equation/config binding 与其 exact claim/obligation 不可拆开；
4. final span 与 authorship ledger entry、move witness、source anchor 不可拆开；
5. candidate attempt 的 output、gate report、usage delta 和 terminal status 不可拆开。

安全切分点应由这些 property 的交集计算，而不是维护一个易漏项的 `if type == ...` 列表。

### 6.3 typed condensation 精确记录遗忘对象

`context/condenser/llm_summarizing_condenser.py:30-160` 区分 REQUEST/TOKENS/EVENTS 原因；
`164-224` 生成包含精确 forgotten event IDs、offset 和 response ID 的 `Condensation`；
`226-291` 只在安全 manipulation indices 上选择切点，并拒绝无进展或进展不足。

这优于只存摘要文本。Code2Paper 的 projection receipt 至少应记录 source head digest、kept
IDs、omitted IDs、replacement ref、适用 properties 及其 proof digest。其 hard reset 路径会
截断历史，只适合会话可用性，不适合本项目权威账本。

### 6.4 `_ActionBatch` 先准备全部动作，再按原顺序发出结果

`agent/agent.py:186-372` 的 `_ActionBatch` 在 Finish 处截断、分离 blocked actions、可并行
执行，但 `emit()` 按原始顺序输出；只有未被阻塞的 Finish 才 finalize。
`Agent.step()`（`637-821`）优先完成 pending actions，再构造 View，再决定是否先发
condensation event 后采样模型。

这适合 Code2Paper 的批量工具：可以并行读取相互独立的 span，但必须先验证整批调用，
输出按确定顺序归并，任何共享 authority target 都不能并行覆盖。

### 6.5 资源锁和 bounded stuck detection

`agent/parallel_executor.py:51-293` 根据工具声明资源加锁，实例级 executor 避免嵌套并行
死锁，最终维持原顺序；取消会中断工具。`conversation/stuck_detector.py:24-325` 只观察
有限最近事件，识别重复 action/observation、重复 error、单调自言自语和交替循环，并对
同一 error event 只 nudge 一次。

本项目已存在 `InformationGainTracker` 和 no-progress 逻辑；可补充精确的
`(owner, obligation_id, failure_signature, parent_digest, action)` 循环指纹，避免表面文本变化
掩盖同一个失败。nudge 是提示，不应改变 terminal/gap 判定。

### 6.6 Goal controller 只能做效用诊断

`conversation/goal/controller.py:25-133` 将 goal audit 做成 transport-agnostic 的纯决策器，
返回 complete/capped/running。这适合 publication utility 的额外诊断循环，但 LLM goal
judge 不能覆盖证据、qualifier、numeric/formula、authorship 或 final-integrity 的确定性失败。

### 6.7 OpenHands 的采用判断

| 机制 | 判断 | 原因 |
|---|---|---|
| EventLog/View 二层 | 最优先采用 | 直接保护事实权威不受上下文操作影响 |
| property 交集安全边界 | 最优先采用 | 可统一压缩、局部重跑和 projection correctness |
| exact forgotten IDs | 采用并增加 digest | 形成可审计 projection receipt |
| ordered parallel action batch | 条件采用 | 仅限无共享写目标的只读/独立工具 |
| stuck detector 指纹 | 采用 | 补强 no-progress 而不弱化 gap gate |
| hard context reset | 不用于权威链 | 会丢失必要事件，只可重建非权威请求投影 |

## 7. PydanticAI：强类型运行时“窄腰”和精确 deferred work

PydanticAI 最适合作为类型和生命周期设计参考。它把模型、工具、输出、重试、usage、
capability 和 graph 都压到少数严格协议上，便于组合；但它本身不理解 Code2Paper 的
evidence authority，需要在窄腰之上保留本项目门禁。

### 7.1 run identity、state 和不完整工具调用

`pydantic_ai/_agent_graph.py:231-287` 分离 conversation ID 和 run ID，并拒绝在历史中重用
run ID；`GraphAgentState`（`293-373`）集中保存 history、usage、output retries、run step、
run/conversation ID、pending events 和 cache；`check_incomplete_tool_call()` 显式处理未完成调用。

`2599-2770` 检测 dangling calls、丢弃 orphaned results、插入或修复缺失 returns。这种
“先恢复 provider-valid transcript 再请求模型”的顺序值得采用，但合成 return 只能修复
表示层，不能合成 Code2Paper 的 evidence/fact/claim 内容。

### 7.2 deferred tool request/result 是写作回调的直接模型

`pydantic_ai/_deferred.py:26-196` 的 `DeferredToolRequests` 保存 approvals 和 calls；结果按
tool call ID 以 approved/denied/result 等 discriminated type 返回，并能计算 remaining IDs。
`_agent_graph.py:493-698` 在 UserPromptNode 恢复 deferred/suspended work。

建议将 `WritingResearchRequestV1` 升级为同类闭环：

```text
request_id
owner
origin_section_id / origin_argument_unit_id / origin_move_id
obligation_ids
required_authority_lane
input_head_digest
status = open | fulfilled | refused | blocked | stale
result_artifact_refs + result_digests
affected_unit_ids
resume_parent_digest
```

恢复时必须验证 request ID、owner、输入 head、结果 digest 和受影响单元；不能靠文本描述
把回调结果“猜”回某个 section。

### 7.3 capability hooks 给横切关注点明确顺序

`capabilities/abstract.py:289-316` 区分 per-agent 和 per-run 绑定；`474-1100` 提供 run、node、
model request、tool validate/execute、output validate/process 的 before/after/wrap/error hooks。
尤其 `668-680` 规定被拒绝 model response 仍应保留并计入 retry；`723-787` 保证参数验证后
才允许 deferral；`998-1048` 区分输出验证值和后处理值。

`capabilities/combined.py:47-107` 展平、排序并按依赖组合 capabilities，后续代码明确 wrapper
嵌套顺序。未来可以把 persistence、usage、trace、projection 和 tool-output handling 做成
capability；但 evidence validators 和 final-integrity gates 不应成为可被后续 capability
吞掉异常或替换结果的普通 hook，它们仍需作为不可绕过的核心节点。

### 7.4 output retry 是类型化内容重试

`_output.py:75-126, 408-437` 将 output schema、validator 和 `ModelRetry` 串成明确 pipeline。
它比解析错误字符串更可靠，适合 Architect/Writer/Formalizer 的结构输出；不过 validator
产生的实质 failure 必须回 owning Agent，harness 只能处理 representation-only damage。

### 7.5 usage limits 的计费时点值得借鉴，但并发需 reservation

`usage.py:338-390` 的 `RunUsage` 汇总 request/tool/token/cost；`UsageLimits`（`418-562`）
分别在请求前、工具前和得到 token/cost 后检查。它准确表达了有些量只能事后获知。

对于 Code2Paper，应在并发/子任务开始前做 budget reservation，完成后以实际 usage settle，
失败则按协议释放或计费。仅共享一个可变 usage 对象会出现 check-then-increment 竞态，Harness
源码也明确记录了该 TOCTOU 限制。

### 7.6 graph builder 的结构验证可前移非法计划

`pydantic_graph/graph_builder.py:1139-1749` 构建 typed state/deps/input/output 图；
`1752-1860` 验证 start/end edges、dead ends 和 reachability，并支持 fork/join。

`AuthoringPlanV3` 已有拓扑排序和 plan gate。可以借鉴其“构建后统一结构验证”方式，增加：

- 每个 must-cover obligation 必须落到一个终态路径；
- callback 路径必须回到精确 affected units；
- 无 claim 的高优先级 completeness obligation 仍必须有 lane/status/next action；
- gate 节点没有绕行边；
- terminal resume 不再触发模型调用。

### 7.7 PydanticAI 的采用判断

| 机制 | 判断 | 原因 |
|---|---|---|
| run/conversation identity 分离 | 强烈采用 | 支持同会话多 run 与同 run 恢复 |
| deferred exact-ID 闭环 | 最优先采用 | 与 writing callback 高度同构 |
| capability 组合 | 条件采用 | 横切能力有用，事实门必须不可绕过 |
| output retry schema | 采用 | 与 owning-agent repair 分层使用 |
| usage limits | 采用并加 reservation | 原实现不足以保证并发总预算 |
| graph structural validation | 强烈采用 | 可把非法计划阻止在模型执行前 |

## 8. PydanticAI Harness：耐久步骤、副作用、计划和大上下文工具箱

Harness 提供了最接近“可直接拆取的组件集合”的实现，但它面向通用 Agent 可用性，
默认耐久性和事实权威强度低于 Code2Paper 的最终验收要求。

### 8.1 step persistence 的状态词汇可直接参考

`step_persistence/_types.py:11-47` 定义 append-only event kinds、tool effect 的
started/completed/failed/unknown-after-crash，以及 complete/interrupted snapshot；
`StepEvent`、`ContinuableSnapshot`、`ToolEffectRecord`、`RunRecord` 位于 `59-153`，都携带
conversation/run/parent/step 等 identity。

`_store.py:40-57` 用临时同目录文件加 `os.replace` 原子写；`110-129` 的 retention 永远保留
最新 snapshot 和最新 complete snapshot；`133-178` 定义 store protocol，后续给出 memory、
file、SQLite 实现。

对 Code2Paper 的增强要求：snapshot 不能只以 message history 为恢复权威，还必须保存
accepted artifact refs/digests、repo snapshot、authority closure、gate report、protocol/model
identity。任何未知 tool effect 在 reconcile 前都必须 fail-closed。

### 8.2 capability 在 provider-valid 边界保存快照

`step_persistence/_capability.py:45-187` 绑定 store 与 run lineage，并对未知 backend 失败，
不静默回退内存；`266-374` 在正常或 error 结束时保存；`411-504` 记录工具 effect；
`506-555` 在 settled CallTools 边界保存可继续快照。

`_helpers.py:21-79` 验证 provider-valid tool pair，并默认只从 complete snapshot 继续；
interrupted snapshot 只有在显式 opt-in、检查 unresolved effects 后才允许。

这是一条很好的恢复顺序：先检查副作用，再验证 provider transcript，再加载控制状态，最后
才允许模型继续。对本项目还需先验证 artifact closure digest，再进入这些步骤。

### 8.3 dynamic workflow 的隔离和预算有用，但结果必须 artifact 化

`dynamic_workflow/_capability.py` 给 sandbox workflow 独立 child history、共享 parent usage、
最大 agent calls 和非嵌套限制。`dynamic_workflow/_toolset.py:621-785` 在 dispatch 前验证类型，
同步占用 call budget，运行 sandbox，并对完成 dispatch 提供有界 preview。

问题在于 preview 不是耐久子任务结果。Code2Paper 的 child/owner repair 必须返回 schema 化
artifact refs/digests、terminal reason 和 usage receipt，而不能只把文字结果塞回父上下文。

源码在 `dynamic_workflow/_toolset.py:631-638` 也说明共享 usage 的异步 check/increment 存在
TOCTOU；生产预算需要原子 reservation ledger。

### 8.4 planning 的整体批次验证适合 Method plan gate

`planning/_types.py:11-58` 定义带 exact ID/dependencies 的 `PlanItem` 和状态；toolset 验证
duplicate、hierarchy、cycle 和 dependency transition，并先验证整个变更批再提交。
`planning/_events.py:19-90` 将计划变更做成 typed events/listeners。

这可用于 `AuthoringPlanV3`：一次 replan 先生成完整 delta，验证 move→anchor、obligation→unit、
lane、依赖和 callback 影响集合，全部通过后一次性切换 plan digest，避免半更新计划。

### 8.5 compaction receipt 是起点，不是权威证明

`compaction/_receipts.py:66-158` 生成无时间戳的确定性 receipt，记录 before/after message 和
token counts、strategy/handle，并通过 ContextVar 传递 span info。`_shared.py:351-466` 定义
必须保留 tool pair 的策略和安全 cutoff；`531-610` 枚举 pair 并重建 cleared history。

两个边界必须明确：

- `_is_safe_cutoff()` 只在约 ±5 messages 邻域扫描 call start，长距离配对可能漏掉；
- summarizing compaction 会截断 tool return 等文本，receipt 也缺 source artifact IDs/digests。

因此，只采用“确定性 receipt + 可重放 recipe”的框架；安全边界改由完整不变量索引计算，
摘要永不进入事实授权链。

### 8.6 memory store 的 CAS/operation fingerprint 很有价值

`memory/_store.py:29-114` 为文件建立 generation/version，为 mutation 建立 operation ID、
fingerprint 和 replay 结果；同一个 operation ID 配不同参数会冲突。file/SQLite 实现通过事务
或原子写实现 compare-and-set。

这个模式应移植到 artifact commit：

```text
operation_id = stable(run_id, owner, target_id, parent_digest, attempt_ordinal)
input_fingerprint = digest(schema_version, input_refs, input_digests, policy)
expected_parent_digest = incumbent digest
new_artifact_digest = candidate digest
```

同 operation+同 fingerprint 重放返回原 receipt；同 operation+不同 fingerprint fail-closed；
parent digest 不匹配说明结果已 stale，不得覆盖 incumbent。

Harness 自己也强调 memory 是背景而非 instruction，volatile 内容要重新验证。这与本项目
“历史 profile/记忆不能授权生产事实”的边界一致。

### 8.7 大工具输出应 lossless spill，而非把截断文本当原文

`tool_output_limits/_capability.py:73-94, 193-418` 在一次 after-tool hook 中缩减/溢写结果，
`429-459` 产生 run/call/retry 相关 handle；读取接口做行数和字符数上限。

适合用于大代码搜索输出，但需改变默认失败语义：Harness 在 spill 失败时可静默回退到截断，
Code2Paper 对 evidence-bearing output 必须写入带 digest 的不可变 artifact，写入失败即不能
产生 positive authority；截断 preview 只能是诊断展示。

### 8.8 conversation search 的作用域 fail-closed

`conversation_search/_source.py` 通过 snapshot hash/overlap 重建历史并排除 summary artifacts；
`_toolset.py:247-363` 提供 BM25 和 all/conversation scope，conversation scope 没有可解析 ID
时失败，不泄漏“是否存在别的会话”。

本项目未来的 artifact search 同样应强制 repo_snapshot/run/protocol scope，任何未指定作用域
的便捷搜索只能用于发现候选，不能直接授权 claim。

### 8.9 Harness 的采用判断

| 机制 | 判断 | 原因 |
|---|---|---|
| step/effect 状态词汇 | 强烈采用 | 覆盖 crash-resume 的关键未知状态 |
| complete/interrupted resume | 采用并增强 | 先加 artifact closure 和 gate digest |
| whole-batch plan validation | 强烈采用 | 避免 partial replan |
| CAS + operation fingerprint | 最优先采用 | 解决幂等、迟到结果和冲突 |
| compaction receipts | 采用结构，不采用安全算法 | 缺 exact artifact closure，固定邻域可能漏配对 |
| lossless output spill | 条件采用 | evidence-bearing spill 失败必须 fail-closed |
| system reminders | 仅 UX | 临时提示不能承担正确性或权威 |

## 9. 跨仓库机制矩阵

| Code2Paper 问题 | Hermes | OpenClaw | OpenHands | PydanticAI | Harness | 推荐组合 |
|---|---|---|---|---|---|---|
| 权威源与请求上下文分离 | request-only selection | context engine turn | EventLog/View 最强 | message state | snapshot/search | 采用 OpenHands 二层，Hermes 约束请求副本 |
| candidate/incumbent | commit fence | accepted attempt 最强 | event parent | node/end | complete/interrupted | OpenClaw terminal + Hermes fence + CAS |
| callback 精确恢复 | child handle | attempt facts | matching property | deferred IDs 最强 | parent/run IDs | Pydantic deferred + artifact/result digest |
| 安全压缩边界 | full exchanges | pair safeguard | property 交集最强 | dangling repair | cutoff/receipt | OpenHands 全量不变量索引 + Harness receipt |
| 副作用去重 | middleware | delivery evidence | unique observation | call ID | ToolEffectRecord/CAS | Harness 状态词汇 + OpenClaw unknown-risk + readback |
| 重试/预算 | typed turn state | typed recovery/refund | stuck detector | UsageLimits | shared usage/max calls | per-obligation reservation + typed failure |
| 计划/图合法性 | 较弱 | runner control | event tree | graph validation | plan batch validation | Pydantic graph + Harness atomic plan delta |
| 并行 | auth gate | lanes | resource locks | tool graph | child isolation | 只并行独立读；共享 authority target 串行 |
| 验证陈旧化 | workspace stale 最强 | lifecycle generation | parent path | run ID | generation/CAS | snapshot+artifact+gate identity manifest |
| 大输出 | micro-compaction | compaction | condensation | history repair | spill handles 最强 | lossless artifact spill + bounded preview |

## 10. 建议的目标运行时契约

以下是从外部代码归纳出的实现建议，不是已批准的新规范。若进入实施，应由后续 Codex 计划
将它们映射到现有设计，不新增与当前模型重复的平行文档或平行状态机。

### 10.1 不新增第二套事实模型，只增加事件/尝试封套

保持现有 `EvidencePacketV3`、`CodeFactV1`、`AtomicClaimV3`、argument graph 和 authorship
对象不变；在外围增加最小运行时封套：

```python
AttemptRecordV1(
    run_id, attempt_id, parent_accepted_digest,
    owner, scope_ids, failure_type,
    input_artifact_refs, input_digest,
    candidate_artifact_refs, candidate_digest,
    validation_report_ref, validation_digest,
    usage_delta, effect_receipt_ids,
    status,  # started | candidate | accepted | retry | discarded | blocked
    terminal_reason,
)
```

关键规则：`accepted` 是唯一能推进 incumbent、checkpoint head 和 affected-unit generation 的
状态。`candidate` 文件可保留诊断，但不能进入 final projection。

### 10.2 耐久副作用收据

```python
ArtifactEffectReceiptV1(
    run_id, operation_id, attempt_id,
    target_artifact_ref, input_fingerprint,
    expected_parent_digest,
    status,  # started | committed | failed | unknown_after_crash
    committed_digest, readback_digest,
    started_at, settled_at,
)
```

写入协议：先落 `started`，写临时文件并 fsync/replace，readback 计算 digest，再落 `committed`。
resume 若看见 started 无终态，先 reconcile 目标 digest；不可直接重放。时间用于诊断，身份和
digest 才用于正确性判定。

### 10.3 projection transform receipt

```python
ProjectionTransformReceiptV1(
    projection_id, source_head_digest,
    source_event_ids, kept_event_ids, omitted_event_ids,
    replacement_artifact_ref, replacement_digest,
    enforced_property_ids, property_proof_digest,
    target_agent, token_measurement,
)
```

它证明“给模型看了什么”，不证明摘要文字本身为真。任何 final claim 仍必须沿 source IDs 回到
冻结 repo evidence。

### 10.4 writing callback ticket

第二轮代码核对确认，现有 `WritingResearchRequestV1`、`WritingResearchCallbackArtifactV1`、
`WritingResearchCallbackBundleV1` 和 `WritingResearchRouteV1` 已经绑定 request ID、origin
section/unit/move、owner lane、result ref/digest，并已实现 affected-only resume。这里不应新增
平行 ticket。残余补强是把 callback artifact 再绑定 `request.content_digest`、owning validator
ID/version、validation report digest、operation ID/input fingerprint；fulfilled 只能由 owning
validator receipt 在读回 result artifact 后设置，不能由裸 `validated=True` 自证。

返回后不要“重新生成整篇”。应使所有依赖 callback ticket 或被其新 artifact 改变 authority
set 的 unit generation +1；其他 unit 的 accepted digest 保持不变，并在最终 ledger 中证明。

### 10.5 budget reservation ledger

第二轮调用链核对发现更早的缺口：policy merge 已计算 `consumed_budgets`，helper 也有测试，但
direct/LangGraph 主循环没有把它应用回 `loop.per_obligation_budgets`。应先在 accepted decision
进入 tool dispatch 前完成一次精确落账，并证明两条 topology 与 checkpoint resume 语义一致。

只有后续引入并发 fan-out 时，才在现有 `PerObligationBudgetV1`/`GlobalSafetyBudgetV1` 外增加
reservation：

```text
available -> reserved(attempt_id) -> settled(actual usage)
                                \-> released(only if policy permits)
```

每个 action 在发起模型/工具前原子 reserve。refund 只允许明确的 representation-only、
未发生新调用路径；内容失败、owner repair 和已发出的 provider request 都应计费。这样可以
兼容并发读工具，而不会产生 check/increment 竞态。

## 11. 与当前 D5 round-4 的直接关系

本次外部研究不建议暂停当前工作去重写通用 runtime。应先把高价值机制压入当前 D5 切片。

### 11.1 立即纳入本轮设计判断（P0）

1. **Typed semantic frame 是 source-declared projection**：
   `method_architect.py:_unit_semantic_frame()` 只能从有 predicate/relation 支撑的 facts 构建
   inputs/transforms/conditions/outputs；不能重新从 claim prose 猜角色。Hermes 的 stable
   request boundary 和 OpenHands 的 projection 原则共同支持这一点。
2. **move authority 是精确 matching property**：
   每个 move 使用自己的 anchor set；同 unit 的无关 claim 不能自动成为所有 move 的依据。
   这对应 OpenHands tool-call matching，而不是关键词重合。
3. **claimless completeness obligation 必须保留为 plan event**：
   它可以是 open/blocked/gap，但不能因没有 claim 就从 plan projection 消失。Pydantic Graph
   的无死端验证和 Harness 的 plan batch validation 可作为测试模型。
4. **callback 使用 deferred exact IDs**：
   自然触发的写作回调必须绑定 origin unit/move、owner 和 input digest；返回后只提升 affected
   unit generation。PydanticAI deferred work 是最接近的代码参考。
5. **candidate 通过 gate 后才替换 incumbent**：
   局部重写、Formalizer、Editor 都遵守 OpenClaw accepted-attempt/Hermes fence 模式。
6. **同身份矩阵增加 staleness 检查**：
   canary→same-identity recheck 之间，repo snapshot、plan、projection、accepted artifacts、
   gate report 任一 digest 改变都使前次验证陈旧。
7. **先关闭已有模型与真实调用链之间的缺口**：
   policy merge 的预算增量必须在 dispatch 前落账；compile candidate 后必须从精确
   packet/fact/claim closure 重算 current quality，只有通过 gate 的 manifest 能推进 best ref。

### 11.2 D4/D5 后续硬化（P1）

1. 对 accepted manifest、callback sidecar 和真正有副作用的工具增加 effect receipt/readback；
   不给所有内容寻址纯函数工具增加无意义事务；
2. 在现有 immutable loop payload 上增加 accepted artifact closure，不另建平行 EventLog；
3. 将 no-progress fingerprint 扩展为 owner/obligation/failure/parent/action；
4. 将 plan replan 改成 whole-delta validation + CAS commit；
5. 为并发/子任务增加共享 reservation ledger；
6. 增加 interrupted/unknown-effect resume 的 fail-closed 测试。

### 11.3 D6/产品化（P2）

1. 将观测、trace、usage、persistence、output spill 做成有明确顺序的 runtime capabilities；
2. 只对无共享写目标的只读工具启用 resource-aware parallelism；
3. 建立 scoped artifact/conversation search，默认绑定 repo snapshot/run/protocol；
4. 大结果只返回 preview+immutable handle，完整内容带 digest 保存；
5. 若引入子 Agent，采用不可扩大父 scope 的耐久 handle，而不是进程内 registry。

## 12. 建议的验证切片

这些测试名称是研究建议，实际实施仍应由执行计划命名和授权。

### 12.1 attempt/commit

- gate 失败的 candidate 不改变 incumbent digest；
- 较早 generation 的迟到 candidate 不能覆盖较新 incumbent；
- cancel 与 commit 竞态只有一个确定终态；
- terminal resume 不发模型调用，且返回同 accepted artifact closure；
- 同 operation ID、不同 input fingerprint 必须冲突。

### 12.2 callback/affected-only resume

- result request ID 不匹配时 fail-closed；
- result input head 已 stale 时不得恢复原 unit；
- callback 只改变 affected unit generation；
- claimless open obligation 在 callback 前后均存在；
- callback 返回的 reference/config/formalization authority lane 不越权。

### 12.3 projection/compaction

- packet/fact/claim 原子闭包没有安全切点；
- final span/authorship/move witness/source anchor 没有安全切点；
- projection 删除任一 source ID 后 closure validation 失败；
- 摘要包含相同关键词但缺 exact ID/digest 时仍失败；
- tool call/result 相隔超过固定邻域时仍能正确识别原子组；
- spill 失败时 evidence-bearing output 不产生 positive authority。

### 12.4 budget/effect

- 并发 reservation 总和不超过 global/per-obligation budget；
- provider request 已发出后，即使 response invalid 也计费；
- representation-only、无新调用修复按协议不计内容预算；
- crash 后 started effect 进入 unknown/reconcile，不直接重放；
- target readback digest 匹配时可幂等 settle，冲突时阻断。

## 13. 明确不应复制的模式

1. **上下文插件 fail-open 到事实门**：只能用于请求可用性，不能用于 authority closure。
2. **best-effort checkpoint 写失败后继续宣称可恢复**：验收关键 artifact 必须 fail-closed。
3. **进程内 map/ContextVar/consume-once receipt 作为耐久证明**：重启后即失效。
4. **标题、关键词重合或 LLM judge 作为事实完整性证明**：只能是诊断/效用信号。
5. **固定 ±N messages 搜索 tool pair**：长距离配对会漏；应使用全量 ID 索引。
6. **摘要或截断 preview 成为 evidence source**：摘要只能引用源，不可替代源。
7. **独立子 Agent 预算当作全局预算**：需要共享、原子的 reservation/settlement。
8. **hard context reset 删除权威历史**：只能重建请求 View，不得删除 authority ledger。
9. **memory、skills、profile、作者意图授权实现事实**：它们只能影响范围、组织和候选发现。
10. **LLM recovery 吞掉 deterministic gate failure**：内容/绑定/证据错误必须回 owning Agent。
11. **spill 失败静默截断 evidence-bearing output**：应停止正面事实编译。
12. **能力 wrapper 可以任意覆盖 validator 结果**：核心证据门必须不可绕过。

## 14. 文件级阅读索引

下面列出本报告实际使用的主要代码入口，便于后续设计或实施时定点复核。

### 14.1 Hermes Agent

- `agent/context_engine.py:89-292` — context engine、request selection、turn complete；
- `agent/turn_context.py:292-336, 402-430` — progress、preflight、turn context；
- `agent/conversation_loop.py:1286-1422` — selection 深复制、turn lifecycle；
- `agent/conversation_compression.py:284-384, 445-620` — attempt snapshot、commit fence；
- `agent/context_compressor.py:5982-6131, 6247-6277` — full-exchange micro compaction、DB sync；
- `agent/prompt_caching.py:20-35, 286-384` — frozen cache plan、稳定 transaction boundary；
- `agent/prompt_cache_boundary.py` — source-declared stable prefix、bounded LRU；
- `agent/turn_retry_state.py:32-93` — typed retry/recovery state；
- `agent/iteration_budget.py` — thread-safe consume/refund；
- `agent/tool_executor.py:141-206, 333-664` — 参数、flush、scope、authorization、dispatch；
- `agent/subagent_lifecycle.py:34-147, 198-540` — handle、terminal、hash、scope；
- `agent/verification_evidence.py:36-48, 414-656` — command evidence 与 staleness。

### 14.2 OpenClaw

- `src/agents/embedded-agent-runner/run-entry.ts:33-124, 152-221, 420-508` — candidate、终态、accepted turn；
- `src/agents/embedded-agent-runner/run-loop.ts:141-250` — retry/recovery/usage/breakers；
- `src/agents/embedded-agent-runner/run/attempt-recovery.ts:39-138` — typed recovery；
- `src/agents/embedded-agent-runner/run/retry-budget.ts:1-39` — retry classification；
- `src/agents/embedded-agent-runner/run/terminal-retry-state.ts:1-22` — terminal revision budget；
- `src/agents/embedded-agent-runner/run-state.ts:75-191` — lifecycle generation eviction；
- `packages/agent-core/src/agent-loop.ts:130-430, 535-900` — turn loop、steering、tool gate；
- `src/agents/embedded-agent-runner/delivery-evidence.ts:16-99, 385-543` — side-effect evidence；
- `src/agents/embedded-agent-runner/tool-send-receipts.ts` — process-local receipt；
- `src/agents/agent-hooks/compaction-safeguard-quality.ts:14-225` — structure/ID/overlap audit；
- `src/agents/agent-hooks/compaction-safeguard.ts:652-720, 849-1242` — pairing、boundary、retry；
- `docs/concepts/agent-loop.md`、`context-engine.md`、`compaction.md` — 本地设计说明。

### 14.3 OpenHands SDK

- `openhands-sdk/openhands/sdk/conversation/event_store.py:30-228` — persistent event tree；
- `.../conversation/state.py:48-79` — running/paused/waiting/terminal status；
- `.../context/view/view.py:22-160` — source view、property intersection、fixed point；
- `.../context/view/properties/*.py` — batch、uniqueness、matching、tool-loop atomicity；
- `.../context/condenser/base.py` — typed View/Condensation 与 hard/soft；
- `.../context/condenser/llm_summarizing_condenser.py:30-291` — reason、exact IDs、safe cutoff；
- `.../event/condenser.py` — synthetic condensation event；
- `.../agent/agent.py:186-372, 637-821` — action batch 与 step；
- `.../agent/response_dispatch.py:44-321` — pure response classification 与 correction；
- `.../agent/parallel_executor.py:51-293` — resource-aware parallel execution；
- `.../conversation/stuck_detector.py:24-325` — bounded loop signatures；
- `.../conversation/goal/controller.py:25-133` — bounded goal audit。

### 14.4 PydanticAI

- `pydantic_ai_slim/pydantic_ai/_agent_graph.py:231-373, 493-698, 1086-1777, 2599-2770`；
- `pydantic_ai_slim/pydantic_ai/_deferred.py:26-196` — deferred request/result；
- `pydantic_ai_slim/pydantic_ai/_output.py:75-126, 408-437` — output validation/retry；
- `pydantic_ai_slim/pydantic_ai/usage.py:338-390, 418-562` — usage/limits；
- `pydantic_ai_slim/pydantic_ai/capabilities/abstract.py:289-316, 474-1100` — hook contract；
- `pydantic_ai_slim/pydantic_ai/capabilities/combined.py:47-107, 286-722` — composition order；
- `pydantic_ai_slim/pydantic_ai/toolsets/approval_required.py:15-31` — approval wrapper；
- `pydantic_ai_slim/pydantic_ai/run.py:31-199, 311-584` — typed run/end/cancel；
- `pydantic_graph/pydantic_graph/graph_builder.py:1139-1860` — typed graph + structural validation。

### 14.5 PydanticAI Harness

- `pydantic_ai_harness/step_persistence/_types.py:11-153`；
- `.../step_persistence/_store.py:40-178, 426-793, 862-1313`；
- `.../step_persistence/_capability.py:45-187, 266-555`；
- `.../step_persistence/_helpers.py:21-131`；
- `.../dynamic_workflow/_capability.py`、`_toolset.py:621-785`；
- `.../planning/_types.py:11-58`、`_events.py:19-90`、`_toolset.py`；
- `.../subagents/_capability.py:289-318`、`_toolset.py:42-381`；
- `.../compaction/_receipts.py:66-158`、`_shared.py:351-610`；
- `.../compaction/_summarizing_compaction.py:375-598`、`_tiered_compaction.py:136-181`；
- `.../memory/_store.py:29-218, 427-755, 848-1082`；
- `.../memory/_capability.py:26-54`；
- `.../conversation_search/_source.py:156-166`、`_toolset.py:247-363`；
- `.../tool_output_limits/_capability.py:73-94, 193-459`、`_store.py`；
- `.../system_reminders/_capability.py:79-299`。

## 15. 最终建议

短期不要替换 LangGraph、不要整体引入某个外部 runtime，也不要先做通用多 Agent 平台。
最具收益、且与当前方向一致的顺序是：

1. 在 D5 round-4 中完成 typed semantic frame、精确 move authority、claimless obligation、
   exact-ID callback 和 affected-only resume；
2. 用 accepted-attempt + CAS commit 明确 candidate/incumbent 边界；
3. 用 event/source 与 projection/view 分离保护证据链；
4. 增加 effect receipt、staleness manifest 和 budget reservation；
5. 最后再把 persistence/trace/output spill 等横切能力模块化。

这样吸收的是五个仓库中已经被复杂 Agent 系统反复证明有价值的运行时不变量，同时不牺牲
Code2Paper 独有的“冻结证据授权最终论文事实”目标。
