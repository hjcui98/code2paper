# 自主 Method Agent 重整报告与执行方案

- Date: 2026-08-11
- Owner: Codex architecture diagnosis
- Scope: read current governing docs, `.agent/` handoff, and implementation under `src/code2paper/agentic/`, `src/code2paper/llm/`, and relevant scripts.
- Purpose: stop the R8/R9 proof-closure spiral, recover the original autonomous research-writing product flow, and prepare a concrete cleanup plan.

## 1. 结论先说

当前系统不是“差一个更强 Writer 模型”这么简单。模型能力会影响文风和复杂 schema 遵循，但现在的主要问题是流程设计已经偏离了产品目标：

1. 原本合理的目标是一个自主运行的 Method Agent：作者意图驱动研究议程，Agent 搜代码/配置/数据流/控制流，编译证据，标记支持/部分支持/不匹配/外部待确认，再由 Method Architect 组织论证，Writer 写正文，缺信息时 callback 到研究/作者/文献/形式化，最后产出可编辑候选稿、verified 稿和作者 review 项。
2. 当前实现把“最终 verified 输出必须可溯源”扩大成“写作前所有高优先级义务必须闭合到 exact unit/move/proof/hash”。这会保护 verified 输出，但会压死 candidate 输出和 Agent 自主探索。
3. 作者意图现在在 writer payload 中被削弱成一个很窄的 `author_goal`，甚至被替换为“按 code order 解释 compiled mainline”。这和“按照作者意图组织行文，代码证据用于支撑/纠偏”相反。
4. `repository_verified_method.md` 和 `publication_candidate_method.md` 现在实际写入同一份文本；`author_review_candidates.json` 的 `proposed_body` 为空。这直接违背了 Method Writer 设计中两个输出状态的核心目的。
5. Writer callback 的类型和路由存在，但主图没有自然的 Writer -> Research/Author/Literature/Formalization -> resume section 闭环；外部 author/literature/empirical lane 现在基本是显式空壳。
6. 研究工具层和 V3 research subgraph 值得保留：它们已经接近“给 Agent 暴露检索工具，让它自主搜索代码”的形态。真正要改的是把它们从旧 pipeline 的前置桥接层提升为产品主流程。

所以：下一步不应该继续围绕 hash、closed-ID、四项目矩阵、强 Writer 模型做验收式补丁。下一步应该重整主流程，让系统先能完成一个真实的 autonomous author-intent-to-method run；严格验证只约束 `repository_verified_method.md` 和最终 unsupported-positive gate，不应该阻止 `publication_candidate_method.md` 携带清楚标注的作者意图和待确认内容。

## 2. 原本目标是什么

根据 governing design，产品目标可以压缩成一句话：

> 让 Agent 根据作者意图和原论文/claims 形成研究议程，自主检索代码证据；证据足够就升级为 verified method facts，证据不足就保留为 author/literature/formalization review 项；最后生成可编辑的 Method candidate 和更保守的 repository-verified 版本。

合理的主流程应该是：

```text
作者意图 / 原论文 / claims
  -> 生成研究议程
  -> Agent 自主搜索代码、读代码、查配置、追数据流/控制流
  -> 编译 evidence packet / facts / atomic claims
  -> 标记 supported / partial / mismatch / author-confirm / literature / formalization
  -> Method Architect 按作者意图组织论证结构
  -> Writer 写正文
  -> 写到缺信息时 callback 回研究/作者/文献/形式化
  -> 局部补证后恢复该小节
  -> 输出 publication_candidate + repository_verified + author_review_items
```

这里有一个关键权威方向：

- 作者意图决定“写什么、按什么叙事组织、哪些点值得调查”。
- 代码证据决定“哪些实现事实可以作为 verified positive claim”。
- 没有代码证据不等于作者意图为假；它应进入 candidate/review/callback，而不是让整个写作停摆。
- 最终 verified 输出仍然 fail-closed：不能让 unsupported implementation fact 混进去。

## 3. 当前代码实际流程

### 3.1 主 LangGraph 还是旧 pipeline 的 stage shell

`src/code2paper/agentic/graph.py` 的 `build_code2paper_graph` 自己说明它是 “first graph-shaped shell over the legacy pipeline”，并且 authoring branch 在 MethodEvidence 和 claim maps 产出前不可达。

实际拓扑在 `src/code2paper/agentic/graph_topology.py` 中是：

```text
input_resolution
  -> intake
  -> coverage_critic
  -> analysis / intake / blocked
  -> analysis_repair_router
  -> evidence
  -> evidence_sufficiency
  -> grounding
  -> authoring_planner
  -> authoring / intake / analysis / blocked
  -> final_text_claim_extractor
  -> text_evidence_validator
  -> text_trace_builder
  -> validation / local_text_repair / blocked
  -> finalize
```

这个结构有阶段，也有部分向前/向后跳转，但它不是现在需要的产品级 Agent loop。尤其是 Writer 写作时缺信息，不能自然回到 research tools 再恢复该小节；后面的 text repair 也被限定为本地修文/绑定修复，不能重新进入研究。

### 3.2 V3 research subgraph 是好部件，但被包装成桥接层

`src/code2paper/agentic/research_graph.py` 已经有接近正确的研究循环：

```text
linear_prefix
  -> research_supervisor
  -> research_tool
  -> observation_pipeline
  -> evidence_critic
  -> compile_candidate / gap_finalizer / inspect_more / advance
```

它能调用工具、观察结果、决定继续搜索还是记录 gap，并产出 compiled evidence / facts / claims。这是应该保留和提升的核心。

但 `src/code2paper/agentic/v3_runtime.py` 明确把它定义成旧 CLI 和旧 graph 的 bridge：先跑 V3 research subgraph，再转换成 legacy `AgentDecision`，再跑 legacy `build_code2paper_graph`。这里还存在 synthetic gaps / fallback artifacts / legacy artifact merge，用来服务 R8 验收，而不是一个清爽的产品流。

### 3.3 Research tools 层基本方向正确

`src/code2paper/agentic/research_tools.py` 已经暴露了很多正确工具，例如：

- 搜索入口、符号、引用、代码片段；
- 查配置；
- 构建/查询 behavior graph；
- 追 call path / data flow / control flow；
- 比较 semantic hints 和 code；
- 编译 evidence packet / code facts / atomic claims；
- record gap / check coverage。

这部分应该作为自主 Agent 的工具面继续保留。问题不是工具太少，而是它们没有成为主流程的一等公民，后续写作也没有把 callback 自然接回这层。

### 3.4 Authoring projection 把作者意图压扁了

`src/code2paper/agentic/authoring_projection.py` 中，writer payload 的 docstring 是“only positive factual payload exposed to the writer”。V3 projection 的 `author_goal` 被硬编码为：

```text
Explain the compiled inference mainline in code order while preserving explicit code gaps.
```

这意味着 Writer 看到的中心目标不是作者想讲的 Method story，而是“按代码主线解释已编译事实”。这和目标相反：行文组织应由作者意图/原论文/claims 主导，代码证据负责支撑、限定、纠偏和标记风险。

### 3.5 Method Architect 已经从组织论证变成 proof/placement gate

`src/code2paper/agentic/method_architect.py` 和 `src/code2paper/agentic/method_argument_models.py` 里有有用的结构：`MethodArgumentUnitV1`、`SectionArgumentGraphV1`、completeness matrix、writing research request。

但 R8/R9 以后叠加了大量机制：semantic frame digest、exact endpoint、obligation move assignment、move authority proof、closed candidates、plan gate、bounded Architect proposal。它们可以作为 audit/debug，但现在被放到了主流程中心，导致产品目标被“证明每个 move 闭合”替代。

最直接的问题是 `publication_method_writer.py` 在 writer 前有 hard gate：critical/high unplaced obligation 直接 `status="blocked"`，然后不写正文。对 verified 输出可以这么严格；对 candidate 输出不应该这么做。

### 3.6 Writer 被迫做 overloaded schema，且 candidate 和 verified 没分开

`src/code2paper/agentic/publication_method_writer.py` 当前 Writer 输入里有：

- `write_only_anchored_required_moves = True`
- `positive_fact_source = argument_flow_semantic_frames_only`
- full validation constraints / semantic frames / move authority / binding contract

这会让 Writer 从“作者意图驱动的论文写作者”变成“ID 和 move proof 的 JSON 填表器”。这解释了为什么 R7 里出现“能写一点，但 callback/moves/config IDs 丢失”的失败：单个响应同时承担正文、证据绑定、move 完成、配置绑定、callback 判断，负担过重。

更严重的是 `_write_publication_outputs` 现在把两个产品输出写成同一份：

```text
repository_verified_method.md = final_text
publication_candidate_method.md = final_text
```

并且 `author_review_candidates.json` 中 `proposed_body` 为空。也就是说：

- 系统没有真正输出“按作者意图组织、但明确标记哪些需确认”的 candidate；
- 系统只输出保守 verified 文本；
- 对用户最重要的 review/edit loop 没有被实现。

### 3.7 Writer callback 还不是闭环

`src/code2paper/agentic/writer_research_router.py` 可以把 request route 到 repository/configuration/formalization 等 owner。

但当前实现明确说：

- `configuration_tools` 可执行；
- `formalization_agent` 可执行；
- `repository_tools` 只有 supplied provider 时可执行；
- `author` / `empirical` / `literature` lane 不能在这里执行，直接返回 `None`。

所以它不是一个完整 Agent callback loop，而是一个半成品路由器。对于用户目标，至少应有：

- repository/config/formalization：本地自动执行；
- author：生成明确 author questions 和 candidate proposed body；
- literature：可配置检索入口或外部待办；
- empirical：可配置 artifact/experiment evidence ingestion；
- 每个 callback 都能影响局部 section resume。

### 3.8 角色温度配置也和用户意图不一致

用户要求 deterministic roles 低温/greedy，creative Writer 温度更高。当前 `src/code2paper/llm/role_config.py` 中 `METHOD_WRITER` 仍是 `temperature=0.20`，这会抑制自然组织和成文能力。

但注意：这不是根因，只是一个局部修复项。即便调成 0.7，如果主流程仍然只让 Writer 写 anchored semantic frames 并且把 candidate=verified，产品仍然跑不通。

### 3.9 当前 `.agent/task.md` / `.agent/plan.md` 会继续带偏

当前 `.agent/task.md` 把任务写成“close Post-R8 D5 Method-quality milestone”，重点是四项目 plan-ready、two-pass Writer contract、role runtime、canary/matrix、blind eval。

当前 `.agent/plan.md` 的顺序是：

```text
freeze R8
  -> four-project plan readiness
  -> two-pass Writer owner contract
  -> role runtime/capability isolation
  -> static + fault + plan-only qualification
  -> named Writer live checkpoint
  -> RAP callback/resume canary
  -> one four-project matrix
  -> fixed blind evaluation
```

这不是用户现在要的下一步。它继续把系统推进到“验收工程”和“模型选择”上，而不是恢复产品主干。

## 4. 哪些应保留，哪些应降级，哪些应清理

### 4.1 保留

这些是对的，应保留并作为新主流程的骨架：

1. `research_tools.py`：代码搜索、符号读取、配置检查、行为图、数据流/控制流、fact/claim compiler。
2. `research_graph.py`：LLM supervisor + tool loop + evidence critic + gap finalizer 的研究循环。
3. 权威 lane 模型：repository evidence、author intent、author confirmed、literature、empirical、formalization。
4. evidence packet / code facts / atomic claims：作为 verified 输出的事实来源。
5. completeness matrix：用于告诉用户哪些 supported/partial/mismatch/external pending。
6. `MethodArgumentUnitV1` / `SectionArgumentGraphV1`：用于组织 Method 论证结构。
7. final text reverse validation：用于阻止 unsupported positive implementation facts 进入 verified 输出。
8. authorship ledger / rewrite/editor ownership：用于最后审计文本来源。

### 4.2 降级为审计/调试，不再作为 candidate 主流程硬门

这些机制可以保留，但不能再主导产品流：

1. digest/hash/manifest identity：保留给 artifact reproducibility，不作为“功能是否完成”的中心叙事。
2. exact obligation placement / closed-ID move proof：保留给 verified/audit；candidate mode 允许未闭合项进入 review/callback。
3. semantic frame exact endpoint：保留为事实绑定增强；不要让 Writer 只能从 semantic frames 写所有内容。
4. pre-Writer plan hard gate：改成输出分级 gate：
   - `candidate_ready`
   - `verified_ready`
   - `candidate_with_review_items`
   - `blocked_for_safety`
5. four-project matrix/canary：保留为 release/eval 入口，不作为下一步产品主干开发入口。

### 4.3 应清理或移出主路径

1. R8/R9 acceptance-specific scripts 和 plan-only qualification 不应是默认产品路径。
2. synthetic gaps / fallback artifacts 只能用于兼容旧 artifact，不应影响主流程事实状态。
3. Writer prompt 中的 full internal ID/move proof/semantic frame 负担应移出 prose call。
4. “supported row unplaced => 不写任何正文”的行为应从 candidate path 移除。
5. `publication_candidate_method.md` 与 `repository_verified_method.md` 相同的写法应立即改掉。
6. 空 `proposed_body` 应立即改掉：review item 必须给作者可编辑的拟写正文/问题。

## 5. 当前空壳/未完成项

下面是按产品影响排序的缺口：

1. 真正的 product runner 缺失：现在有 legacy graph、V3 bridge、artifact-only writer、matrix runner，但没有一个清晰入口从 repo + author intent + claims 自动跑到三类输出。
2. Writer -> research callback 闭环缺失：有 request model 和 router，但没有主图级 resume loop。
3. author confirmation lane 缺失：现在只是 JSON review item，且 `proposed_body` 为空。
4. literature lane 缺失：没有实际检索/引用/外部待办接口。
5. empirical lane 缺失：没有统一接入实验结果、指标表、日志、figure/table artifact 的 evidence ingestion。
6. formalization lane 只部分存在：能从 code facts/equations 做守卫，但还没有作为“Writer 缺公式/符号定义时的主动协作者”接入主流程。
7. candidate/verified 双输出缺失：实际写同一文本。
8. author-intent-first architect 缺失：当前 planner 更偏 code-order + proof closure，而不是把作者 story spine 作为章节组织主轴。
9. content-first Writer 缺失：当前 Writer schema 过载，正文、ID、moves、configs、callback 一次完成；应拆成“写候选正文/提出缺口”和“后处理绑定/验证”。
10. role sampling policy 未落地：Writer prose 仍低温；应拆 decision 低温、prose 中温。

## 6. 新的目标架构

主流程应改为以下产品路径：

```text
MethodRunInput
  repo_path
  author_intent
  original_paper_or_draft
  user_claims
  optional artifacts/config profiles

-> IntakeAgent
   normalize inputs, extract author story spine, create research agenda

-> ResearchAgent loop
   plan tool calls
   search/read/trace code and configs
   compile observations
   continue when evidence insufficient
   record explicit gaps when no local evidence exists

-> EvidenceCompiler
   evidence packets
   code facts
   atomic claims
   claim status: supported / partial / mismatch / not_found / external_pending

-> MethodArchitect
   sections organized by author story spine
   each unit carries evidence state and missing lanes
   unverified author-intent content remains candidate/review material

-> SectionWriter
   write publication_candidate section from author story + verified facts + clearly marked unresolved claims
   request callback if missing info blocks readability or verification

-> CallbackRouter
   repository/config/formalization local tools
   author/literature/empirical queues or configured connectors
   resume only affected section

-> Validator
   repository_verified_method: only supported/partial-with-qualifier facts
   publication_candidate_method: includes author-intent and unresolved items with safe caveats/review markers
   author_review_candidates: questions plus proposed body

-> Final outputs
   publication_candidate_method.md
   repository_verified_method.md
   author_review_candidates.json
   evidence_packet/facts/claims/completeness_matrix/trace
```

## 7. 具体修改方案：一套按依赖排序的工作包

说明：这里的 A-H 不是“额外阶段”和后文 Step 的两套计划，而是一套执行工作包。每个工作包对应一个子系统改造；第 9 节只给这些工作包之间的推荐依赖顺序，不再定义第二套步骤。

如果要分派给多个 Agent，使用 `.agent/parallel_work_packages_20260811.md`。那份文件把这里的 A-H 扩展成可并行执行的任务书，包括目标、现状证据、具体函数/文件、接口契约、测试、禁止捷径和交付物。

### 工作包 A — 先恢复产品输出语义

目标：让系统即使证据不完整，也能产出可编辑 candidate；verified 仍严格。

修改点：

1. 在 `publication_method_writer.py` 引入输出策略：
   - `repository_verified_method.md`：只含验证通过的 implementation facts；
   - `publication_candidate_method.md`：按作者意图组织，可以包含明确标注的 author-intent / literature-needed / formalization-needed 内容；
   - `author_review_candidates.json`：每个未 verified 的关键点必须有 `proposed_body`、`confirmation_question`、`needed_evidence`、`suggested_action`。
2. 移除 candidate path 的 “critical/high unplaced => blocked before Writer”。
   - 改为：如果存在 unsupported uncaveated positive implementation claim，block verified 或 block final-integrity；
   - 如果只是证据不足，candidate 继续写，review item 明确暴露。
3. `_write_publication_outputs` 不能再把 candidate 和 verified 写同一文本。

最小验收：

- 一个缺代码证据的 claim 不会让 candidate 空白；
- verified 不包含该 claim；
- review JSON 有该 claim 的拟写文本和确认问题。

### 工作包 B — 把 V3 Research loop 提升为主流程

目标：让 Agent 真正自主搜索，而不是把 V3 当 legacy 前置桥。

修改点：

1. 新增或重构 product runner，例如 `run_autonomous_method_agent`：
   - 输入 repo + author intent + claims；
   - 直接调用 `build_research_subgraph`；
   - 输出 evidence/facts/claims/completeness；
   - 再进入 architect/writer。
2. `v3_runtime.py` 的 legacy bridge 保留为兼容路径，但不再作为默认产品路径。
3. 去掉主路径中的 synthetic gaps / fallback artifacts；找不到证据时用真实 typed gap。
4. 让 analyze 阶段可调用 research tools 继续搜索，而不是只能在旧 stage 间跳。

最小验收：

- 给定一个 author claim，Agent 至少能自主调用 search/read/trace/config 工具，产出 supported 或 gap；
- 研究轨迹能解释“为什么停止搜索/为什么记录 gap”。

### 工作包 C — 重做 authoring projection：作者意图主导组织

目标：Writer 不再只看 code-supported claims，而是看到完整 Method story 与每个点的证据状态。

修改点：

1. `AuthoringInputProjection` 增加或明确字段：
   - `author_story_spine`
   - `reference_method_obligations`
   - `candidate_claims_by_lane`
   - `verified_claims`
   - `partial_claims`
   - `mismatch_claims`
   - `external_pending_claims`
   - `review_questions`
2. 删除/替换 V3 projection 中硬编码的 “compiled inference mainline in code order”。
3. `projection_writer_payload` 不再声称它是唯一 positive factual payload；改成：
   - verified facts 是唯一 repository-positive authority；
   - author intent 是 organization/candidate authority；
   - external lanes 进入 marked candidate/review，不进入 verified facts。

最小验收：

- 同一份证据，改变作者意图会改变 section organization；
- 缺证作者点不会消失，会进入 candidate/review。

### 工作包 D — 简化 Method Architect

目标：Architect 回到“组织论证结构”，不是“证明所有 move exact placement”。

修改点：

1. 保留 `MethodArgumentUnitV1` / `SectionArgumentGraphV1`，把以下内容降为可选 audit：
   - semantic frame proof closure；
   - move authority proof；
   - full obligation exact placement gate。
2. Architect 输出每个 section 的：
   - narrative purpose；
   - author-intent obligations；
   - verified evidence units；
   - partial/mismatch/external pending units；
   - writer guidance；
   - callback candidates。
3. Gate 改为三态/四态：
   - `verified_ready`
   - `candidate_ready`
   - `candidate_ready_with_review`
   - `blocked_for_safety`

最小验收：

- 有 unresolved/external item 时，plan 仍可供 candidate writer 使用；
- 只有会导致 unsupported positive 被静默写入的情况才 block。

### 工作包 E — 重做 Writer：content-first，绑定后处理

目标：Writer 专心写可读 Method；证据绑定由后处理和 validator 承担。

修改点：

1. Writer 输入减少为：
   - author story；
   - section purpose；
   - verified facts summary；
   - partial/mismatch/external pending notes；
   - explicit writing policy；
   - optional formulas/configs；
   - review markers。
2. Writer 输出拆为：
   - `section_markdown`
   - `unresolved_points`
   - `new_research_requests`
   - `self_risks`
3. 不要求 Writer 在 prose call 中完整列出所有 claim/config/equation IDs。
4. 后处理从句子中抽取 claims，再与 facts/claims 反向验证，生成 `used_*_ids`。
5. Writer decision 可以低温；Writer prose 应中温，例如 `temperature=0.7/top_p=0.90/seed=42`。不要把 greedy 多卡一致当创作质量测试。

最小验收：

- Writer 能输出自然段落；
- 没有证据的实现事实不会进入 verified；
- candidate 中的 unresolved 内容有 review marker 或 review JSON 对应项；
- ID 绑定失败不会让 harness 编造 ID，只会进入 validator issue。

### 工作包 F — 实现 callback 闭环

目标：写作时发现缺口后，能回到研究/作者/文献/形式化，并只恢复相关小节。

修改点：

1. repository/config/formalization lane：
   - 直接调用现有 research tools / config claims / formalization agent；
   - 生成 callback artifact；
   - 更新 facts/matrix/section plan；
   - resume affected section。
2. author lane：
   - 写入 `author_review_candidates.json`；
   - 包含 proposed body；
   - 不阻塞 candidate，阻塞 verified。
3. literature lane：
   - 先实现可配置 external queue；
   - 后续接入检索工具时，产出 citation/evidence artifact。
4. empirical lane：
   - 先定义 artifact ingestion schema；
   - 可接入日志、指标表、实验结果、figure/table。
5. 主 LangGraph 增加 Writer callback route：

```text
writer
  -> callback_router
  -> research_subgraph / author_queue / literature_queue / formalization_agent
  -> evidence_update
  -> architect_update
  -> resume_section_writer
```

最小验收：

- Writer 发出 repository callback，系统自动补证并只重写该 section；
- Writer 发出 author callback，candidate 继续生成，verified 排除该点，review JSON 有问题和拟文。

### 工作包 G — 验证层重新分工

目标：保留真实性，不让真实性门压死产品可用性。

修改点：

1. Reverse validation 对 `repository_verified_method.md` 继续 fail-closed。
2. `publication_candidate_method.md` 允许 author-intent/external pending 内容，但必须：
   - 标记 lane；
   - 有 review item；
   - 不伪装成 repository-verified implementation fact。
3. 最终报告区分：
   - verified facts coverage；
   - candidate completeness；
   - author review burden；
   - unresolved evidence gaps；
   - mismatch warnings。

最小验收：

- unsupported positive implementation facts = 0；
- candidate 覆盖作者 story spine；
- unresolved 内容可见、可编辑、可追踪。

### 工作包 H — 产品入口和开发入口分离

目标：不再用 D5 matrix runner 代表产品。

修改点：

1. 新增或明确一个产品 CLI：

```text
code2paper method-agent run \
  --repo <repo> \
  --author-intent <file> \
  --claims <file> \
  --out <dir>
```

2. 输出必须固定包含：
   - `publication_candidate_method.md`
   - `repository_verified_method.md`
   - `author_review_candidates.json`
   - `evidence_packets.json`
   - `code_facts.json`
   - `atomic_claims.json`
   - `completeness_matrix.json`
   - `agent_trace.json`
3. R8/R9 matrix/canary scripts 移到 eval/dev-only 语义，不再作为用户主流程。

最小验收：

- 一个项目一次命令可以从 author intent 跑到三类文本/JSON 输出；
- 不需要先满足四项目矩阵闭合才能证明产品有用。

## 8. 建议立即修改的文件

按优先级：

1. `src/code2paper/agentic/publication_method_writer.py`
   - 拆 `candidate` / `verified` 输出；
   - 移除 candidate 前 hard block；
   - 填充 `author_review_candidates[].proposed_body`；
   - 降低 Writer 输入中的 exact proof/move/schema 负担。
2. `src/code2paper/agentic/authoring_projection.py`
   - 恢复 author-intent-first projection；
   - 增加 story spine / review lanes / candidate claims；
   - 删除 code-order hardcoded author goal。
3. `src/code2paper/agentic/method_architect.py`
   - 把 plan gate 改成 candidate/verified 分级；
   - 将 move proof/closed placement 从 candidate blocker 降为 audit。
4. `src/code2paper/agentic/writer_research_router.py`
   - 实现 author queue artifact；
   - repository provider 默认接入 research tools；
   - literature/empirical 至少生成标准 external queue，不再无声 `None`。
5. `src/code2paper/agentic/graph.py` / `graph_topology.py`
   - 把 `research_graph` 接入主产品流；
   - 增加 Writer callback -> research/formalization/queue -> resume section route。
6. `src/code2paper/agentic/v3_runtime.py`
   - 保留 legacy bridge 为兼容；
   - 默认产品路径不再通过 synthetic/fallback legacy merge。
7. `src/code2paper/llm/role_config.py`
   - 拆 Writer decision/prose 或至少把 method_writer prose 调到中温；
   - strict verifier/formalizer/architect 保持低温/greedy。
8. `src/code2paper/llm/section_writer.py` / `response_schemas.py`
   - 简化 prose schema；
   - callback/request 与 prose 分离；
   - used IDs 以后处理为主，Writer 返回为辅助，不作为唯一事实。
9. `src/code2paper/cli/agentic_run.py`
   - 新增清晰产品入口，从 repo+intent+claims 到完整输出。

## 9. 执行顺序和依赖

不要再把这里理解成另一套 Step。真正的执行对象就是第 7 节的工作包 A-H。推荐顺序是：

```text
A 输出语义
  -> C 作者意图投影
  -> D Architect 分级 gate
  -> E Writer content-first
  -> G verified/candidate 验证分工
  -> B Research 主流程接入
  -> F Callback/resume
  -> H 产品 CLI
```

原因：

- A 必须最先做，因为 candidate/verified/review 三输出不分开，后面所有 Agent 能力都会继续被 verified gate 压住。
- C/D/E/G 是写作主干：先让作者意图进入 plan，再让 Architect 不阻断 candidate，再让 Writer 写正文，最后用验证层筛出 verified。
- B/F 是自主能力：把研究 loop 接入主流程，并让 Writer 缺信息时能回 research/config/formalization 或 author queue。
- H 是产品入口：等内部闭环能跑，再给一个干净 CLI；不要拿四项目 matrix 代替产品入口。

最小闭环验收仍然只有一个：

```text
author intent + claims
  -> research tools 搜索
  -> evidence/facts/claims
  -> completeness matrix
  -> author-intent-first section plan
  -> candidate writer
  -> verified filter
  -> review JSON
```

成功标准：

- candidate 覆盖作者想讲的 Method points；
- verified 只含 repository-supported facts；
- review items 有 proposed body 和 exact question；
- Agent trace 能说明它搜了什么、为什么停止或为什么发起 callback。

## 10. 给后续开发的边界

可以大刀阔斧改，但不要突破这些底线：

1. verified positive implementation facts 必须有 repository evidence。
2. author intent 可以组织行文、生成 candidate、生成 review 项，但不能伪装成代码事实。
3. 缺证不是失败；静默把缺证当已证才是失败。
4. Writer 应写人读的 Method，不应被迫当 ID/proof 填表器。
5. validators 应保护 verified 输出，而不是阻止 candidate/review 的生成。
6. 所有 unresolved/mismatch/external pending 都必须显式暴露给作者。

## 11. 最短可执行任务声明

下一轮不要执行旧 R9。新的任务是：

> 将 Research Agent 从 R8/R9 的闭合验收流重整为 author-intent-first 的自主 Method Agent 产品流：保留研究工具、证据编译和 verified fail-closed；降级 exact proof/placement/hash 为 audit；实现真正的 candidate/verified/review 三输出；接入 Writer callback 到本地研究/配置/形式化和外部 review queue；新增一个从 repo+intent+claims 到完整 Method artifacts 的产品入口。
