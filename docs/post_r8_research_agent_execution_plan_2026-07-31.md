# Code2Paper R8 后 Research Agent 具体开发执行计划

- `as_of`: 2026-08-01
- `status`: 当前执行权威；R8 六项目 6/6 accepted，进入 post-R8 实施
- `actual_r8_evidence`: RAP、EBCAR、DyG、LinearRAG、Lookahead、Bootstrapping
  均通过统一 17 项 recheck；详见
  [`r8_acceptance_status_2026-08-01.md`](r8_acceptance_status_2026-08-01.md)
- `normative_design`:
  [`agentic_robust_langgraph_research_writing_design_2026-07-19.md`](agentic_robust_langgraph_research_writing_design_2026-07-19.md)
- `method_coverage_audit`:
  [`r8_method_paper_coverage_audit_2026-07-31.md`](r8_method_paper_coverage_audit_2026-07-31.md)
- `publication_writer_design`:
  [`publication_ready_method_writer_design_2026-07-31.md`](publication_ready_method_writer_design_2026-07-31.md)
- `supersedes`: 取代旧 R0–R8 执行文件的进度跟踪功能，不取代总体设计和历史记录

## 1. 执行结论

下一阶段仍然完整解决三类问题，不能只调 Writer prompt：

1. 通用 Research Supervisor 必须真正产生 packet/fact/claim，不能继续由具名 profile
   提供事实；
2. 原论文议程、配置分支、公式和数值必须进入完整性合同，不能继续压成 8–9 条 claim；
3. Writer 必须具有 argument graph、写作中返回研究、形式化和 Agent-owned rewrite，
   生成可投稿 Method，而不是安全短摘要。

```text
冻结 R8 证据 + 修正跨 artifact 一致性
  -> 接通真实 evidence/fact/claim tool data plane
  -> 取消 evidence profile 的事实授权能力
  -> reference coverage + active/default branch + equation/config 编译
  -> Method Architect/Writer/Formalization/Editor + 写作中返回研究
  -> owning Agent 修复 + authorship provenance + best-state 不退化
  -> 无 profile holdout + mutation
  -> checkpoint、效率和 Method 质量闭环
  -> 跨模型/语言与产品切换
```

完整架构和验收条件保留，但不在每个工作项、每个 commit、每个 Agent 完成后重复跑
全量测试、真实 API、fault injection 和 committee。测试只保护真实失败和关键不变量；
完整回归和人工评价在明确里程碑集中执行一次。

## 2. 当前真实基线

### 2.1 矩阵结果与运行成本

矩阵 `20260731T004226Z` 完成前五个 accepted 项目；Bootstrapping 在
`20260801T011526Z` 的真实主运行/resume 产物上完成修复后重检：

| 项目 | accepted | traces | Intent calls | Supervisor calls | length | elapsed |
|---|---:|---:|---:|---:|---:|---:|
| RAP | True | 115 | 12 | 91 | 5 | 4578s |
| EBCAR | True | 156 | 26 | 116 | 13 | 8315s |
| DyG | True | 116 | 13 | 81 | 17 | 5520s |
| LinearRAG | True | 103 | 10 | 77 | 13 | 4588s |
| Lookahead | True | 260 | — | — | — | 8610s |
| Bootstrapping | True | 73 | 6 | 51 | — | 3016s |

当前静态基线是 `2017 passed, 3 skipped, 12 subtests passed`；R8 定向回归为
`118 passed`。结构化恢复最终可得到合法
Intent，但调用多；checkpoint 主库约 157–324 MiB，没有保持紧凑 reference/digest。

### 2.2 实际 evidence chain

```text
自主 Research Supervisor 搜索源码
  -> 没有形成 packet/fact/claim
  -> must-cover 被 synthetic gap 终结
  -> 具名 profile 生成 packets/facts/claims
  -> profile claims 进入 Method
  -> 旧 R8 accepted
```

| 项目 | 自主 packet/claim/gap | must-cover sidecar | profile packet/fact/claim/gap |
|---|---:|---|---:|
| RAP | 0 / 0 / 5 | 5/5 explicit gap | 3 / 13 / 8 / 3 |
| EBCAR | 0 / 0 / 6 | 6/6 explicit gap | 4 / 12 / 9 / 0 |
| DyG | 0 / 0 / 5 | 5/5 explicit gap | 6 / 10 / 9 / 4 |
| LinearRAG | 0 / 0 / 4 | 4/4 explicit gap | 7 / 10 / 9 / 6 |

最终 coverage 没有一个 `supported_must_cover`，旧 criterion 却仍让 mainline 通过，
说明 sidecar、profile coverage 和 final claim 没使用同一 provenance。

### 2.3 Supervisor 与 repair

| 项目 | SEARCH | READ | relation tools | RECORD_GAP | COMPILE/PROPOSE |
|---|---:|---:|---:|---:|---:|
| RAP | 27 | 38 | 5 | 20 | 0 |
| EBCAR | 33 | 35 | 16 | 31 | 0 |
| DyG | 14 | 28 | 10 | 26 | 0 |
| LinearRAG | 19 | 15 | 6 | 35 | 0 |

Supervisor 找到并读取真实候选，却从未进入 packet/fact 编译；同一 obligation 还能重复
`RECORD_GAP`。另外三个项目的 deterministic local repair 没有 `local_rewrite` trace，
却产生 embedding/task-head/PPR 重复、`under when`、`under in`、残句和主语删除。

### 2.4 Method 覆盖不足

- RAP 源码有 15-D features、KNN default、MLP dimensions、normalization；
- DyG 有 history padding、time-gap、SSM、cross-attention、top-k readout；
- LinearRAG 有增量 index、edge weights、BFS/default、PPR 和 answer generation；
- 四项目最终均为 0 safe equations、0 safe numeric facts；
- RAP、DyG、LinearRAG Method 只有原稿约 16%–22%；
- paper-code mismatch 没有结构化终态。

论文草稿不能授权实现事实，但必须变成 reference obligations，否则
`unsupported=0` 不能证明内容完整。

### 2.5 矩阵与代码状态

R8 六项目均已结束并通过统一 17 项重检。Bootstrapping 原 driver 中的 false 是旧
checker 将 Qwen profile 与 Gemma 固定 sampling/TP=2 比较产生的历史结果；主运行和
resume 本身均 exit 0。R0/R2 基本完成；R1/R4 工具和 compiler 部分完成；R3 已 live
但低效；R5 Intent 可用但恢复成本高；R6 repair 仍需完成 Agent-owned 闭环；R7
profile 仍拥有过多事实权限。R8 证明真实长流程可通过，但没有消除这些 post-R8 差距。

## 3. 关键架构差距

### 3.1 Tool data plane

目标链：

```text
propose_evidence_packet -> validate_evidence_packet
  -> compile_code_facts -> validate_code_facts
  -> decompose_atomic_claims -> authorize_atomic_claims
```

当前若干工具只返回 `fact:compiled:*`、`claim:decomposed:*`，真实编译由
`compile_candidate_node` 旁路完成，无法从 tool trace 独立重放和修复。

### 3.2 Profile authority

六个 `evidence_profiles/*.py` 仍包含固定路径、symbol、Packet、CodeFact、AtomicClaim
和 gap。结构 fingerprint 触发不等于通用；模板只能增强发现，不能拥有事实。

### 3.3 Provenance 与跨 artifact 一致性

新协议必须证明 V3 enabled、graph/packet/fact/claim digest 绑定、supported claim 来自
generic data plane、profile 只提供 query/role alias。同一 obligation 不能既是 gap 又
被 profile claim 当成 positive support。

### 3.4 Owning Agent repair

规则层只能修 fence、空白、闭合符号等表示问题。替换 fragment、追加 qualifier、删除
子句、插入 claim 都必须返回 Writer/Rewrite；最终正文 lexical span 必须来自 LLM
generation trace。

### 3.5 完整性终态

执行计划直接复用 Writer 设计的唯一枚举：

```text
supported_by_repository
partially_supported_by_repository
paper_code_mismatch
unverified_by_repository
author_confirmation_required
external_evidence_required
formalization_required
explicit_code_gap
out_of_scope
```

`explicit_code_gap` 不能替代 author confirmation、external evidence 或 formalization。

## 4. 具体开发批次

### D0：冻结 R8 证据并修复运行治理

目标是建立跨 artifact 一致、可复现、可终结的基线。D0 不依赖尚未实现的 Writer
ledger；正文 authorship/integrity 门放到 D4/D5。

修改：`run_r8_gemma_matrix.sh`、`r8_acceptance.py`、`runner.py`。

工作项：

1. heartbeat/lease、退出 trap、原子 finalizer；
2. PID/heartbeat 消失写 `FAILED/INTERRUPTED`；
3. manifest 记录 commit、dirty flag、profile/run/report/checkpoint digest 和终态；
4. 强制 `v3_enabled=true`，recheck 只读 manifest 指定 artifact；
5. 增加 `single_evidence_chain_consistent`、`generic_research_compiled_claims`、
   `gap_claim_noncontradiction`；
6. mainline 使用 canonical coverage；论文草稿作为 hard evidence 时失败；
7. resume 记录 model-call delta。

退出：三类中断有真实终态；manifest 可重放；all gaps + profile claims 必须失败。D0 用
现有四项目和失败 fixture 即可完成；六项目通过是 matrix 最终条件，不阻塞 D0 开发。

### D1：接通真实 Evidence/Fact/Claim 工具链

修改：`research_tools.py`、`tool_runtime.py`、`research_nodes.py`、`research_graph.py`、
三个 generic compiler、`traceability_ledger.py`。

1. packet proposal 写 artifact，validator 返回 typed failures；
2. fact compiler 消费 validated packet + behavior subgraph；
3. fact validator 重放 predicate、guard、relation、authority；
4. Agent 提议 claim grouping，通用 authorizer 授权；
5. observation 记录 input/output digest、path、validator report、semantic change；
6. `compile_candidate_node` 降为兼容 facade，稳定后删除双实现；
7. `RECORD_GAP` terminal 幂等，gap validator 检查搜索策略和缺失 relation。

退出：claim 可重放到 exact source span；没有 synthetic-only success；单项可修复；RAP
从真实 search/read 编译 packet/claim；LinearRAG 每 obligation 只有一个 terminal gap。

### D2：取消 evidence profile 的事实授权能力

修改：`evidence_profiles/`、`behavior_templates.py`、`research_supervisor.py`、
`v3_runtime.py`、`r8_acceptance.py`。

1. `BehaviorDiscoveryTemplateV2` 只允许 predicates、relations、role/stage/query hints；
2. schema 禁止 path、symbol literal、fact、claim、gap text；
3. 删除 profile `compile()` 事实权限；
4. Supervisor 可用模板选方向，但必须读取 snapshot 后形成 packet；
5. 增加 generic provenance/profile non-authoritative criterion；
6. 六项目做支持边界 equivalence。

退出：禁用 profile 后通用路径仍运行；production 不从 profile 读事实正文；支持边界由
behavior graph/fact digest 决定。

### D2.5：Reference coverage、配置分支和公式编译

修改：`research_models.py`、`intent_obligations.py`、`source_authority.py`、
`python_behavior_adapter.py`、generic compilers、`equation_claims.py`、
`authoring_projection.py`、`authoring_plan_v3.py`。

1. `ReferenceMethodObligationV1` 提取 role、statement、class、authority、query、importance；
2. `MethodCompletenessMatrixV1` 使用完整九种终态；
3. `ConfigurationClaim` 追踪定义到 entrypoint override，区分 actual/default/
   conditional/unreachable；
4. compiler 生成 implementation/configuration/equation/rationale/empirical/capability；
5. exact operations/constants/relations 编译为 `EquationClaimV1`；
6. authoring plan 为 supported unit 指定 section、claim/equation 和信息内容；
7. Writer 预算按 supported units、公式、计划段落动态计算；
8. 四项目原论文对照固化为 fixture，但不复制原文；
9. 增加 `MethodArgumentUnitV1` 和 `WritingResearchRequestV1`；
10. 交付 `repository_verified_method.md`、`publication_candidate_method.md`、
    `author_review_candidates.json`。

四项目内容回归：RAP 的 15-D/KNN/MLP/normalization；EBCAR 的 mask/attention/
InfoNCE/rerank；DyG 的 `time_mamba` 分支与 top-k softmax；LinearRAG 的 BFS/vectorized、
vertex/sentence mapping、index/PPR/answer generation。

退出：高优先级 unit 有终态；paperdraft 不授权 implementation；equation/config/numeric
不再全为 0；branch 不混写；mismatch 不静默选边。

### D3：无 profile holdout 与 mutation

目标是完成总体设计“至少两个 holdout 项目无需项目专用 compiler”的成功定义。

修改范围：

- `src/code2paper/agentic/python_behavior_adapter.py`
- `src/code2paper/agentic/behavior_graph_tools.py`
- `src/code2paper/agentic/research_policy.py`
- `src/code2paper/agentic/obligation_fact_alignment.py`
- blind holdout fixtures、mutation harness 和 acceptance 集成入口

1. 冻结两个未参与 template/profile/prompt 设计的真实 Python 仓库；
2. 选择前冻结协议、author intent 和禁止修改列表；
3. 禁止项目名、路径/symbol literal、fact/claim text；
4. 执行原仓库 live、文件移动、rename、helper extract/inline、默认值移动、行为变化；
5. 语义保持 mutation 维持支持边界，行为变化改变 fact/claim；
6. 证据不足允许可信 incomplete/gap。

Lookahead 已有 profile，只能作为去 profile 回归，不能计入 blind holdout。

退出条件：

- 两个真正未知 holdout 都产生至少一个 supported must-cover mainline；
- 如果证据不足，允许其中某节成为有精确原因的可信 `incomplete`，但不能 fallback；
- 所有正向句 `unsupported=0`；
- 验收期间不发生项目专用源码改动；
- mutation 满足语义保持/行为变化判别；
- explicit gap 包含实际搜索范围、工具尝试和缺失 relation。

### D4：结构化输出、自修复和 checkpoint

目标是修复真实产物中的内容退化，同时减少无信息重复、数据库膨胀和全链重跑，且
安全硬门保持不变。

修改范围：

- `src/code2paper/agentic/intent_target_proposer.py`
- `src/code2paper/agents/langgraph_utils.py`
- `src/code2paper/llm/response_schemas.py`
- `src/code2paper/agentic/text_repair_supervisor.py`
- `src/code2paper/agentic/graph_text_trust_nodes.py`
- `src/code2paper/agentic/final_text_authorship.py`
- `src/code2paper/agentic/quality_state_v2.py`
- `src/code2paper/agentic/checkpointing.py`
- `src/code2paper/agentic/research_graph.py`
- `src/code2paper/agentic/v3_runtime.py`

1. 删除 deterministic prose lexical mutation；
2. `local_rewrite` Agent 生成 scoped patch，Harness 只应用其逐字响应；
3. candidate 与 incumbent 比较，安全不回退且不新增重复/残句/qualifier 错误；
4. repair 失败恢复原 draft并保留 issue/trace；
5. `FinalTextAuthorshipLedgerV1` 映射 generation span 到 final span；
6. Intent 改为 obligation-scoped content + closed-set binding；
7. 各 repair strategy 使用统一 typed transition artifact；
8. Writer/Rewrite、packet relation、claim decomposition 做 owner-scoped fault injection；
9. 每个失败 obligation 有独立预算并轮转修复，每轮重跑对应原子 hard gate；
10. checkpoint 只保存 artifact ref/digest 和紧凑决策状态，大对象写 immutable store；
11. retention 不得删除 best state、issue trace、authorship ledger 或终态 evidence；
12. terminal resume 在任何模型调用前恢复并验证终态。

退出条件：

- fence、逗号、闭合符号问题可由 harness 无损恢复并留痕；
- 内容、引用、证据错误实际调用 owning Agent，原硬门重新执行；
- EBCAR 不重复 embedding 句，并保留 shared/dedicated attention 主语；
- DyG task-head 只出现一次，不产生 `under in`；
- LinearRAG 保留 dense fallback 主语，不重复 attribute/PPR；
- generation trace 出现真实 `local_rewrite`，无效 patch 保留 repair 前正文；
- ledger 对正文 span 指向 Writer/Rewrite 响应，注入 deterministic token 时失败；
- fault injection 覆盖 Intent、packet、claim、Writer 四个 owner；
- 修复失败时恢复 best state，supported 不被 gap 替换；
- completed resume 零调用；interrupted 与 uninterrupted 支持边界一致；
- calls、length、repair、checkpoint growth 的改善不能靠减少覆盖或降低硬门获得。

### D5：Method 质量与作者可用性

目标是从“没有 unsupported 句子”提升到完整、严密、连贯、不重复、忠于作者意图且
可以直接进入论文编辑。实现以 publication writer design 为规范，不再把 claim list
或保守 projection 当最终写作方案。

主要修改范围：

- `src/code2paper/agentic/method_argument_models.py`
- `src/code2paper/agentic/method_architect.py`
- `src/code2paper/agentic/writer_research_router.py`
- `src/code2paper/agentic/formalization_agent.py`
- `src/code2paper/agentic/cross_section_editor.py`
- `src/code2paper/agentic/final_text_authorship.py`
- `src/code2paper/agentic/authoring_projection.py`
- `src/code2paper/agentic/authoring_plan_v3.py`
- `src/code2paper/authoring/writer_skill.py`
- `src/code2paper/authoring/writing/section_planner.py`
- `src/code2paper/authoring/writing/method_writer.py`
- `src/code2paper/llm/section_writer.py`
- `src/code2paper/agentic/text_repair_supervisor.py`
- `src/code2paper/agentic/r8_acceptance.py`

#### D5a Writer 核心

1. Method Architect 生成 `MethodArgumentUnitV1`、`SectionArgumentGraphV1`；
2. Section Research Writer 使用 content-first；
3. Formalization Agent 生成符号表、代码等价公式和 `ProofObligationV1`；
4. Cross-section Editor 统一术语、符号、过渡、重复；
5. writing-time callback 只恢复受影响小节；
6. 失败返回 `incomplete_sections`，删除 deterministic placeholder；
7. projection-only draft 降为 legacy/debug；
8. 固化 writer skill/prompts；
9. budget 随 argument graph 和支持信息量动态增长。

#### D5b 质量门

1. 安全指标与写作指标分开；
2. completeness、连贯、重复、stage、qualifier、information density、editability；
3. plan gate + final integrity gate；
4. validator 返回 sentence/claim/stage scoped issue；
5. matrix 对比 agenda、intent、claims、final spans；
6. overview/representation/transformation/branch/equation/objective/output 分别报告；
7. figure 只从授权 Method claim 投影；
8. precision、recall、argument moves、equation/config/numeric、reproducibility、notation、
   preference、edit distance 分开报告。

退出条件：

- safety hard gates 全通过，must-cover 与 gap 可被作者理解；
- 当前 EBCAR、DyG、LinearRAG 的退化 `method_clean.md` 被阻塞；
- RAP/DyG/LinearRAG 不再只有原论文约 16%–22% 骨架，判断依据是 supported-unit
  coverage 和人工可编辑性，不设机械词数阈值；
- 原稿内容按 repository-unverified、author confirmation、external evidence、
  formalization 或 explicit gap 分类，未经 authority 不进入正文；
- 每个核心小节有 argument graph，并完成项目需要的原理、定义、公式/伪代码、机制、
  实现、条件和输出闭环；
- Writer 至少一次发现真实缺失信息、发 research callback、获得 artifact 并只恢复
  受影响小节；
- Writer/Formalizer/Editor/Rewrite 之外不存在 final prose lexical token；
- 预算耗尽或调用失败产生可信 incomplete draft，不插 deterministic placeholder；
- 重复与碎片化低于当前基线；repair 后质量状态 Pareto 改善。

人工评价只在 D5 完整里程碑结束时集中执行一次固定盲评/配对比较，不在每个 Agent
完成后反复建立 committee。

### D6：通用语言、模型和产品切换

1. 生产节点改为 adapter registry；
2. 实现第二语言 adapter；
3. 增加第二 provider/model capability profile；
4. execution profile 不改变 evidence/authorization 门；
5. 完成 shadow、opt-in、canary、rollback；
6. `default_ready` 后才切默认路线。

## 5. 依赖关系

```text
D1 -> D2 -> D2.5 -> D5a
                       |
D0 -------------------+--> D3 -> D5b -> D6
D4 -------------------+
```

D0 与 D1 可并行；D2 依赖 D1；D2.5 依赖 D1/D2；D3 依赖 D0、D2.5、D4、D5a；
D4 可与 D2 并行；D5b 使用未知项目；D6 不抢占 D1–D5。

## 6. 第一实施切片

### Slice A：真实失败回归

一个纵向 fixture 文件集中放入 gap/claim 冲突、mainline 错判、三项目重复/残句/
qualifier 错误和 deterministic lexical diff。实现 cross-artifact gate、integrity issue、
best-state rollback、authorship 拒绝；不为每个 failure/gate 单独建测试文件。

### Slice B：真实 tool artifact 闭环

去除 fact/claim placeholder；toy obligation 从 packet 到 authorized claim；trace 记录
digest；checkpoint 后只重放该 obligation；RAP 从 search/read 形成真实 packet/claim。

### Slice C：RAP profile 收权与 completeness

迁移 RAP compile 权限为 discovery template，建立 Reference Obligation 和 Completeness
Matrix；15-D/config/MLP/normalization 进入 Authoring，Training 保持 external gap；然后
用 DyG、LinearRAG 验证 branch/mismatch，再迁移其他 profile。

### Slice D：RAP 可投稿小节

Architect 建 graph；Formalization 恢复公式；Writer 写 problem → intuition → formalization
→ implementation → output；移除 relation 验证 callback/resume；Editor/Rewrite 只输出
LLM patch。Slice D 同时证明完整和不越界后才开始 holdout。

## 7. 测试与验收策略

1. 不按 contract、class、Agent、validator、工作项一一创建测试文件；优先扩展现有
   文件，新主题使用一个纵向集成测试文件；
2. 只自动化真实发生过的失败、真实性硬边界和无法从 artifact 观察的纯逻辑；
3. 普通提交只运行直接相关测试，不运行全量 suite、fault injection、live API 或
   committee；
4. 单个开发批次结束只运行该批次定向测试，不重复四项目 live；
5. D1–D4 形成 research-core 里程碑后，集中运行一次完整静态 suite、相关 fault
   injection 和一次 RAP live；
6. D5 完成后，集中运行一次四项目真实重跑和一次固定盲评；
7. D3/W7 运行真正未知 holdout 和必要 mutation；
8. 发布前才运行最终完整 suite、跨模型/语言和 rollout 验收；
9. 一次真实运行已直接证明的同一行为，不叠加多层等价测试。

| 时点 | 自动化 | 真实运行 | 人工评价 |
|---|---|---|---|
| 普通 commit | 受影响测试 | 无 | 无 |
| Slice A–D | 对应纵切测试 | 必要本地 artifact | 无 |
| research-core | 一次完整静态 + 定向 fault | RAP 一次 | 无 |
| D5 Writer | Writer/质量门测试 | 四项目一次 | 固定盲评一次 |
| holdout/发布 | 必要完整 suite | 未知项目/目标模型 | 需要时一次 |

不以测试数量、fixture 数量、coverage 百分比、live 次数或 committee 轮数报告进度。

## 8. 进度报告

| 字段 | 内容 |
|---|---|
| Design requirement | 对应设计章节 |
| Code changed | 模块和 contract |
| Behavior changed | Agent 新能力 |
| Trust invariant | 保持的硬门 |
| Static evidence | 本里程碑实际测试 |
| Live evidence | 仅在规定里程碑报告 |
| Efficiency | calls、repair、elapsed、checkpoint |
| User-visible result | 真实 Method 改善 |
| Remaining gap | 尚未证明的边界 |

只有 code、真实行为、trust evidence 和 Method artifact 同时改善才算 verified；新增
schema、Agent、测试文件或评审轮次本身不算结果。
