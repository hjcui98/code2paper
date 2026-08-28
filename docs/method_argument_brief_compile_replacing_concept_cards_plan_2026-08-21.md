# Method 论证包编译：用一次综合编译替换逐 cluster Concept Card

- 日期：2026-08-21
- 状态：WP-A / WP-B / WP-C 已于 2026-08-22 只读验收 **PASS**（含当日 REPAIR 三项）。下一实现切片是 §6 WP-D（一次 DyG canary）。验收记录：`.agent/review.md`
- 文档性质：代码级修改方案。它落实
  `docs/publication_ready_method_writer_design_2026-07-31.md` §5
  （atomic claim 是验证单元；`MethodArgumentUnit` / 论证图才是写作中间层），
  **不是新的架构规范**，不替代 2026-07-19 总体设计、2026-07-31 Writer 规范、
  2026-08-17 Method Agent 主线，也不得作为一次端到端 `/implement` assignment
- Candidate 措辞权修订（2026-08-22）：live `133302` 证明确定性许可键无法把 Δt/A
  等作者机制绑到已有代码证据。Verified 仍只认本文件的确定性 `positively_licensed`。
  Candidate 语义许可、写作期回搜、学术 Formalizer 与 Rewrite 主职见
  [`method_intent_first_authoring_redesign_2026-08-22.md`](method_intent_first_authoring_redesign_2026-08-22.md)。
  本文件「compile 无 LLM」约束保留给 Verified 编译器，不再约束 Candidate 对齐层。
- 执行入口：§6 WP-D。WP-A/B/C 不得再作为新的 `/implement` 范围重开；WP-D 不得一次铺开三项 live
- 触发：冻结 Research 已有 atomic claims / completeness / story spine；
  live `--rebuild-authoring` 却仍对每个 cluster 调 Concept Architect + Evidence Judge，
  生成 Writer 最终不会采用的短语卡。用户要求：对上了用作者原词，对不上由 planner
  一次写出论文可用机制，去掉逐卡中间层

## 0. 结论先行

当前 live 主链在冻结 Research 之后多做了一层 **逐 cluster 短语卡**：

```text
冻结 claims + completeness + intent graph
  -> 按 (obligation, method_scope) 切 cluster
  -> 每 cluster：Concept Architect LLM（最多 2 次）+ Evidence Judge LLM
  -> method_concept_cards_v1（短语字段，subject≤160）
  -> Architect 把卡绑到 MethodArgumentUnit
  -> WriterView 只暴露 method_subject/operation 短语
  -> Writer 再写成论文
```

这层卡不是论文正文，却承担了几乎全部 live 重建时间和字段校验税。
110938 DyG 约 34 张卡；133605 在出卡/出 proof 阶段就因 `story_node` 160 字上限
和 `MoveAuthorityProofV1(state=anchored, unresolved_obligation_ids≠[])` 崩溃，
Writer 一次都没跑到。

目标中间产物改为 **论证包（argument brief）**：每个 story node / 义务一条，
同时带上代码证据、作者叙事、子句级许可和对账状态。

```text
冻结 claims + completeness + coverage + intent + equations
  -> 确定性 compile_method_argument_briefs（无 LLM）
  -> 仅当存在未许可子句时：一次（或每大节一次）Mechanism Planner LLM
  -> method_argument_briefs_v1
  -> Architect 按 spine 把 brief 收成 MethodArgumentUnit + SectionArgumentGraph
  -> WriterView 暴露：许可的作者原词 | 未许可意图 | 机制草稿 | 闭集 claim/equation id
  -> Writer / Formalizer / Editor / Rewrite 写正文
```

规则：

1. **子句对上了**：Writer 的机制措辞种子是作者原句，不经 Concept 重写成短语。
2. **子句没对上**：作者原句保留为意图栏，不得进入 verified；planner 用闭集
   claims/equations 写论文可用机制/公式草稿。
3. **整条义务 `supported_by_repository` 不能授权整段作者原文。** DyG 主线义务
   的 statement 把 top-k 实现和 Ebbinghaus 动机写在同一段里。
4. 卡片模块本轮不删除，live `--rebuild-authoring` 与
   `build_product_planning(..., compile_concept_cards=True)` 停止把它当作默认中间层。
5. 最终 lexical token 仍只来自 Writer / Formalizer / Editor / Rewrite。
   论证包和 planner 草稿是写作合同，不是终稿。

## 1. 权威、范围与非目标

### 1.1 权威顺序

1. `docs/agentic_robust_langgraph_research_writing_design_2026-07-19.md`
2. `docs/publication_ready_method_writer_design_2026-07-31.md` §4–§6
3. `docs/method_agent_master_agent_mainline_execution_repair_plan_2026-08-17.md`
   （主线仍有效；其中 Stage 2/3「逐 cluster 短语卡」的 **live 默认路径** 由本文替换）
4. `docs/method_authoring_r5_quality_root_cause_and_code_execution_plan_2026-08-20.md`
   （WP0 冻结边界、Candidate incumbent、Writer 见证、Formalizer/callback 门仍有效；
   WP1 把 Concept Card 写进 rebuild 主链的部分由本文改道）
5. `docs/post_r8_research_agent_execution_plan_2026-07-31.md` 与
   `docs/project_status_and_gap_report_2026-07-31.md`：仅在其证据绑定范围内作背景

冲突时停止实现并返回 Codex，不得弱化 evidence / qualifier / authorship / callback /
checkpoint / final-integrity 门。

### 1.2 冻结输入（不重搜代码）

Research 权威仍只拷贝，不在本方案重跑搜代码：

| 产物 | 路径 | 本方案中的角色 |
|---|---|---|
| atomic claims | `artifacts/atomic_claims_v3.json` | 验证单元；许可绑定的闭集 |
| completeness | `artifacts/method_completeness_matrix_v1.json` | 义务级九态对账 |
| coverage | `artifacts/obligation_coverage_v2.json` | `target_alignments`（resolved/partial/unresolved） |
| intent graph | `artifacts/intent_obligation_graph_v2.json` | `author_text` + `typed_behavior_targets` |
| equations | `artifacts/equation_claims_v1.json` | 公式闭集 |
| configurations | `artifacts/configuration_claims_v1.json` | 配置闭集 |
| packets / facts | `evidence_packets_v3` / `code_facts_v1` | span/fact 句柄；不进 Writer 短语层 |
| story spine | `build_story_spine_from_intent_graph` 现编 | 组织顺序；`author_statement` 不是仓库事实 |

冻结根（与 R5/Gate 6B 相同，不得改写）：

- `.tmp/c2p-stage1-canary/run-dyg/`
- `.tmp/c2p-stage1-canary/run-linearrag/`
- `.tmp/c2p-q5-batch3/run-ebcar-research/`

### 1.3 非目标

- 不重跑 Research Graph、不把 paperdraft 当生产事实源。
- 不用确定性 harness 生成/补写科学正文。
- 不按项目名、源码路径、已知公式或三项人工答案进入 generic production logic。
- 不恢复「每个 partial 都要求 `limitations_or_mismatch` executable_hard」。
- 不把一次静态通过或一次 live 当 D5 / rollout / 默认切换。
- 不在 WP-A 改 Writer prompt、Formalizer schema、callback 语义。
- 不在本轮删除 `method_concept_card_*.py`；只把 live 默认编译切走。

## 2. 现状调用链（必须改的落点）

### 2.1 Live rebuild 是 Concept 主链

`scripts/run_authoring_replay.py::_rebuild_derived_authoring`（约 330–452 行）在
`--rebuild-authoring` 时：

1. 加载冻结 claims / facts / equations / packets / completeness / configurations / intent
2. `build_story_spine_from_intent_graph`
3. **`compile_method_concept_cards`**（`require_evidence_judge=True`）
4. `build_method_section_plan_with_product_readiness(concept_cards=...)`
5. 写出 `method_concept_cards_v1`、`method_section_plan_v2`、projection

`src/code2paper/agentic/autonomous_method_agent.py::build_product_planning`
（约 823–968 行）在 `compile_concept_cards=True` 且 live LLM 时走同一条卡编译；
否则回落到 `compile_method_propositions`（同样是逐 cluster LLM）。两条都不是
本方案要的综合论证包。

### 2.2 卡编译为什么贵、为什么脆

`method_concept_card_compiler.py`：

- `build_concept_candidate_clusters`：按 `(obligation_id, dotted method scope)` 切 cluster；
  非 `supported_by_repository` 的 completeness 行另开 `author_intent` cluster
- `compile_method_concept_cards`：每个 cluster 调 Architect 最多 2 次，再对每个
  有卡的 cluster 调 Judge
- `MethodConceptCardV1.story_node` 上限 160 字
  （`method_concept_card_models.py::_SUBJECT_MAX`），却被赋值为
  `proposal.story_node or cluster.story_node`，而 `cluster.story_node` 来自
  spine `title`（整段 `author_statement`）。这就是 133605 EBCAR 崩溃

### 2.3 Architect / Writer 如何吃卡

- `method_architect.py::build_method_section_plan_with_trace`（约 462–496 行）：
  按 `bindings.source_obligation_ids ∩ unit.source_obligation_ids` 把卡塞进
  `MethodArgumentUnitV1.concept_card_ids`
- `_enrich_section_content_contracts`（约 859 行）：填
  `primary_concept_keys` / `supporting_concept_keys` / `audit_only_concept_keys`
- `publication_method_writer.py`（约 8090–8116 行）：
  `build_writer_view_from_concept_cards`
- `llm/section_writer.py::_closed_set_publication_schema`：concept mode 强制
  `rendered_concept_keys` / `deferred_concept_keys` 闭集
- `_align_final_claims_to_concept_cards`（约 4732 行）：用卡表面词 token overlap
  把终稿句绑回 concept key，再扩张到义务下 claims（R5 已诊断这会误判）

### 2.4 与论证包正交、但 live 仍会踩的 proof 不变量

`MoveAuthorityProofV1._state_closure`
（`method_argument_models.py` 约 600 行）：

```text
anchored/bridge 不得携带 unresolved_obligation_ids
```

`resolve_move_authority_proofs`（`method_architect.py` 约 3215–3333 行）在
content move 已有 `anchor_ids` 时设 `state=anchored`，同时仍把 partial
completeness 放进 `unresolved_obligation_ids`。133605 LinearRAG/DyG 死在这里。
WP-B 必须修，否则即使不再出卡，partial 义务仍会在出 plan 时崩溃。

## 3. 目标产物：`method_argument_briefs_v1`

新文件：`src/code2paper/agentic/method_argument_brief_models.py`
（不要把大段作者原文塞进现有 `MethodConceptCardV1`）。

现有 `MethodArgumentUnitV1`（`method_argument_models.py` 约 610 行）只存 id
列表，没有「许可的作者原词 / 未许可子句 / 机制草稿」。论证包是 Architect
之前的编译产物；unit 继续做节内论证原子，但改为绑定 `brief_ids` 而不是
`concept_card_ids`。

### 3.1 模型

```text
AuthorClauseLicenseV1
  clause_id                  # clause:{obligation_id}:{index}
  text                       # 作者原句，禁止截断当权威
  license                    # positively_licensed | partially_licensed | unlicensed
  bound_claim_ids            # 本义务闭集的子集
  bound_equation_ids
  bound_span_ids
  bound_target_ids           # obligation_coverage_v2.target_alignments.target_id
  missing_target_ids
  license_reason             # harness 诊断，不进 Writer 正文

MechanismDraftV1
  draft_id
  brief_id
  text                       # planner 论文可用机制/公式草稿；可空
  cited_claim_ids            # 必须 ⊆ 本 brief 闭集
  cited_equation_ids
  authority_lane             # executable_hard | formal_derivation | expository_bridge
  caveat
  status                     # not_required | empty | planner_filled | planner_failed

MethodArgumentBriefV1
  brief_id                   # brief:{story_node_id} 或 brief:{obligation_id}
  story_node_id
  intended_role              # 沿用 AuthorStoryNodeV1
  obligation_ids
  author_statement           # 完整原词，永不写入 ≤160 字段
  completeness_statuses      # 每条义务的九态
  clauses                    # AuthorClauseLicenseV1+
  licensed_wording           # 仅 positively_licensed 子句按原文顺序拼接
  claim_ids / equation_ids / configuration_ids / span_ids
  mechanism_draft            # 无未许可子句时可 status=not_required
  may_enter_verified         # 仅当存在 positively_licensed 子句且其 claim 均为 supported
  requires_caveat            # 存在 partial/unlicensed/mismatch
  content_digest

MethodArgumentBriefSetV1
  schema_version = "1.0"
  repo_snapshot_id / project_tree_hash
  claims_digest / completeness_digest / coverage_digest / intent_digest
  briefs
  planner_used: bool
  gaps                       # planner_failed / 空闭集等 typed gap，不得静默当成功
  content_digest
```

`MethodArgumentUnitV1` 增补（向后兼容，默认空）：

```text
brief_ids
verified_brief_ids
caveated_brief_ids
brief_order
```

闭包校验对齐现有 concept/proposition 字段：三类集合不相交且并集等于
`brief_ids`。旧 `concept_card_*` 字段保留；**一个 unit 不得同时非空绑定
briefs 与 concept cards**（与 WriterView「命题 XOR 概念」相同）。

`SectionArgumentGraphV1` 增补：

```text
primary_brief_ids
supporting_brief_ids
```

旧 `primary_concept_keys` 在 brief 主链上保持空元组。

### 3.2 子句切分

函数：`split_author_clauses(author_text, obligation_id) -> tuple[AuthorClauseLicenseV1, ...]`
放在 brief compiler，无 LLM。

- 分隔：`. ` / `? ` / `; ` / `。` / `；`，保留原文空白语义
- 空段丢弃；顺序稳定；`clause_id` 用义务 id + 序号，不用文本 hash 当主键
- 来源优先级：spine `author_statement`（若该 node 的 `linked_obligation_ids`
  含此义务），否则 completeness `statement`，否则 intent `author_text`
- **禁止**把整段 `author_statement` 当作单条 licensed clause

### 3.3 许可规则（确定性，禁止英文词袋对账）

覆盖编译已经禁止用英文 token overlap 决定义务是否 supported
（`obligation_fact_alignment.py` 文件头）。子句许可不得再引入一套词袋义务匹配。
许可键必须来自闭集证据侧：

1. 取该义务下 claims（`covers_obligation_ids`）、其 `direct_evidence_ids` /
   `fact_ids`、绑定的 `equation_ids`
2. 取 coverage 中该义务的 `target_alignments`
3. 从 claims / equations / resolved target 的 **闭集符号** 抽出许可键：
   - claim `canonical_text` 中的 dotted identifier、snake/Camel identifier
   - equation `expression` / `concrete_expression` 中的符号字面量
   - 长度 ≥ 4 且不是通用停用词的 identifier
   - **停用**：`input` / `model` / `method` / `output` / `data` 以及
     `TypedBehaviorTargetV1.search_terms` 里长度 &lt; 4 的词
     （DyG 主线 target 的 `search_terms=["input"]` 不得单独许可整段）
4. 子句 `positively_licensed` 当且仅当：
   - 至少命中一个许可键，且该键来自 `status=supported` 的 claim，且
   - 对应 fact 落在 `target_alignments.status == "resolved"` 的 matched_fact_ids
     上，**或者**该 claim 本身已是 compiler 标记的 `supported`
     （claims 已由 facts 编成；不要要求 target 与 claim 再做一轮词袋）
5. `partially_licensed`：只命中 `claim.status=partial` 或
   `target.status=partial` 的键；`missing_target_ids` 填该义务未 resolved 的
   target
6. 其余为 `unlicensed`（典型：Ebbinghaus、保证稳定衰减、新颖性、动机）

硬不变量（测试必须钉死）：

- 义务级 `supported_by_repository` **不能**推出所有子句 `positively_licensed`
- 未命中许可键的子句即使同义务下有 30 条 supported claim，仍是 `unlicensed`
- `licensed_wording` 只能是 `positively_licensed` 子句原文拼接
- `author_statement` 全文始终保留在 brief 上，但 `may_enter_verified=False`
  只要存在 unlicensed/partial 子句
- 不得把 `unlicensed` 子句写入 `licensed_wording` 再靠 caveat 混进 verified

### 3.4 一个 brief 对应什么粒度

按 **story node** 聚合，不是按 dotted method：

- `brief_id = brief:{story_node_id}`
- `obligation_ids = node.linked_obligation_ids`
- 该 node 下所有义务的子句、claims、equations 收入同一 brief
- 没有 spine 的义务：`brief:{obligation_id}`，排在 spine 之后，避免丢失
  completeness 行

这样 Writer 看到的是「作者这一段故事 + 对上的原词 + 没对上的意图 + 证据」，
而不是 34 张 `concat/topk/softmax` 短语。

低层 claims 仍全部挂在 `claim_ids` 上供 reverse validation；没有「每条
predicate 必须成为一张卡」的配额。未许可的低层操作留在证据账本，需要写进
机制时由 planner 草稿或 Writer 依据闭集 claim 文本使用。

## 4. 编译器与 Planner

### 4.1 WP-A：确定性编译（无 LLM）

新文件：`src/code2paper/agentic/method_argument_brief_compiler.py`

```text
compile_method_argument_briefs(
    *,
    claims: AtomicClaimSetV3,
    completeness: MethodCompletenessMatrixV1,
    coverage: ObligationCoverageReportV2 | None,
    intent_graph: IntentObligationGraphV2,
    story_spine: Sequence[AuthorStoryNodeV1],
    equations: EquationClaimSetV1 | None = None,
    configurations: ConfigurationClaimSetV1 | None = None,
    planner: MechanismDraftPlanner | None = None,   # WP-A 传 None
    require_planner_for_unlicensed: bool = False,   # WP-A False；WP-C live True
) -> MethodArgumentBriefSetV1
```

WP-A 行为：

- 编 briefs、切子句、打许可、填 id 闭集、digest
- 存在 `unlicensed` 或 `partially_licensed` 时：`mechanism_draft.status=empty`，
  `requires_caveat=True`，**不失败**（草稿留到 WP-C）
- `planner is None` 且 `require_planner_for_unlicensed=True` 才记 typed gap
  （给 WP-C live 用）
- 禁止调用 `compile_method_concept_cards` / `compile_method_propositions`

覆盖入口用冻结 DyG `atomic_claims_v3` + `method_completeness_matrix_v1` +
`intent_obligation_graph_v2` + `obligation_coverage_v2` 做 golden 形状测试
（见 §7），不要只用两句 RAP fixture。

### 4.2 WP-C：一次 Mechanism Planner

新文件：`src/code2paper/agentic/method_argument_brief_planner.py`

协议对齐 `method_concept_card_provider.py`：只看到闭集信封，harness 做
id 闭包和 digest。

一次请求（默认全 Method 一份；若 token 超限再按 section 切，禁止按
cluster/子句切）：

模型可见：

- 每个 brief：`intended_role`、许可子句原文、未许可子句原文、
  闭集 `frag-N`（claim canonical_text + equation expression + span id 字面量）
- completeness 九态
- **不可见**：内部 digest、项目名特判、未绑定事实 JSON 全量

模型返回（guided JSON）：

```text
drafts: [{ brief_id, text, cited_frag_ids, caveat }]
```

Harness：

- `brief_id` / `cited_frag_ids` 必须落在本请求闭集
- 映射回 claim/equation/span id
- 校验失败最多 1 次 representation repair；仍失败则该 brief
  `planner_failed` gap，不得编造草稿
- `text` 不是终稿；Writer 必须重写。draft 只授权机制/公式形状
- **禁止**把未许可作者原句标成 `executable_hard` 已实现
- 无 equation 绑定的公式句子只能进 caveat / `formal_derivation` 待 Formalizer，
  不得标 verified 公式

Judge：WP-C **不**做逐字段 LLM Judge。闭集 id +「草稿引用的 frag 必须存在」
由 harness 完成。若要语义 entailed/contradicted，只允许 **一次** 对全部
drafts 的核对，且失败不得靠丢掉草稿来让 verified 变绿。

## 5. 接入 Architect / Writer / Replay

以下全部属于 WP-B（WP-A 只编译、不改 live 入口）。WP-C 只把 planner 插进
WP-B 已接好的编译入口。

### 5.1 `build_product_planning`

文件：`autonomous_method_agent.py`

在 completeness + spine 之后：

```text
briefs = compile_method_argument_briefs(...)
# 不再默认 compile_method_concept_cards / compile_method_propositions
plan = build_method_section_plan_with_product_readiness(
    ...,
    argument_briefs=briefs,
)
```

`compile_concept_cards=True` 改为 deprecated no-op（测试断言不再出卡），
或仅当显式 `--legacy-concept-cards`（本方案默认不加该旗标）。
命题车道同样不再作为 live 回落。

规划结果 dict 增加 `argument_briefs`；artifact 写出
`method_argument_briefs_v1.json`。

### 5.2 Architect

文件：`method_architect.py`

`build_method_section_plan_with_trace` / `..._product_readiness` 增加
`argument_briefs=`。绑定逻辑对标现有 concept 段（约 462–496 行），改为：

- `brief.obligation_ids ∩ unit.source_obligation_ids` → `unit.brief_ids`
- `may_enter_verified` → `verified_brief_ids` 否则 `caveated_brief_ids`
- 每个 brief 只放进一个 unit（与卡相同）

`_enrich_section_content_contracts`：用 `primary_brief_ids` 替代
`primary_concept_keys` 的角色。primary = 本节 story_node 对应 brief；
supporting = 同节但非 spine 主 node 的 brief。不要再调用
`classify_concept_card_writing_role`。

**Proof 修复（与论证包同一切片，否则 live 仍崩）：**

`resolve_move_authority_proofs`：若 `anchor_ids` 非空且将设 `state=anchored`
或 `bridge`，则 `unresolved_obligation_ids` 必须为空。partial / author_confirmation
/ unverified 的义务：

- 挂在 brief 的 `requires_caveat` 与 Writer caveated 栏
- 若仍要在 proof 上暴露，只能 `state=open` 或 `external_pending`，且
  `unanchored=True`
- 不得把 partial 写进已锚定的 `mechanism_overview` proof 的
  `unresolved_obligation_ids`

回归必须用 110938 形状：义务 `partially_supported_by_repository` + 同 unit
已有 claim anchors。静态 fixture 不得再只覆盖 unverified→limitations。

`story_node` 160 类失败：brief 路径不得把 `author_statement` 拷进任何
`max_length≤160` 字段。`AuthorStoryNodeV1.title` 仍过长是 spine 既有问题；
WP-B 在 `build_story_spine_from_intent_graph` 把 `title` 改为短组织标题
（首句或 role+序号），**完整文本只留 `author_statement`**。这是组织字段，
不是截断事实权威。

### 5.3 WriterView

文件：`writer_view_projection.py`

新增（与 concept 层并列，互斥）：

```text
WriterLicensedNarrativeV1    # licensed_wording + bound claim/equation ids
WriterUnlicensedIntentV1     # unlicensed/partial 子句 + caveat kind
WriterMechanismDraftV1       # planner 草稿 + cited ids
```

`WriterViewV1` 增加对应元组与 `allowed_brief_ids` / `required_brief_ids`。
闭包：briefs XOR concepts XOR propositions。

`build_writer_view_from_argument_briefs(...)`：按 graph 的 primary/supporting
brief ids 装填。`licensed` 进 positive；`unlicensed/partial` 进 caveated；
draft 作为 immutable 机制约束（类似今日 `formula_constraints`），不是新 claim。

`publication_method_writer.py` 构造 WriterSectionInput 处（约 8090 行）：
有 briefs 则走新 view。`writer_unit_payload` 增加 `brief_ids`、
`licensed_wording` 不进 id payload（正文种子走 view）。prompt_payload 增加
`argument_briefs` 摘要：许可原词、未许可意图、草稿、闭集 claim 文本。

### 5.4 Writer schema 与 reverse validation

文件：`llm/section_writer.py`

`_closed_set_publication_schema` 增加 `brief_mode`：

- 必填 `rendered_brief_ids` / `deferred_brief_ids`
- enum = 本节 `allowed_brief_ids`
- 不得同时暴露无约束的 `deferred_concept_keys` / `deferred_proposition_ids`
  （WP2 已踩过公式 id 漏进 deferred）

`required_brief_ids` = primary briefs。缺 primary → `missing_required_briefs`，
与今日 `missing_required_concepts` 同级 fail-closed。

替换 `_align_final_claims_to_concept_cards`：终稿句绑定到
**brief.bound_claim_ids ∪ mechanism_draft.cited_claim_ids**，禁止再扩张到
该义务下全部 claims。这是 R5 第三点在 brief 主链上的对应修复。

### 5.5 Callback

`WritingResearchRequestV1` 已有 `concept_key` / `target_concept_keys`。
WP-B 增加可选 `target_brief_ids` / `target_clause_ids`（默认空）。
callback fulfillment（`writing_callback_fulfillment.py`）在 brief 主链上
用 brief 的 missing unlicensed slots / empty draft 作为「是否增益」基线，
不要再要求 target-concept judgment。

4A 的「callback 必须回答所问机制槽位」仍有效：槽位改为
`unlicensed clause` 或 `empty mechanism_draft` 或 `formula_obligation`。

### 5.6 Replay 边界

文件：`scripts/run_authoring_replay.py`

- `DERIVED_AUTHORING_ARTIFACTS` 增加 `method_argument_briefs_v1`；
  `method_concept_cards_v1` 仍留在 derived 列表（默认不拷）
- `_rebuild_derived_authoring` 改为调用 `compile_method_argument_briefs` +
  `build_method_section_plan_with_product_readiness(argument_briefs=...)`
- 写出 `method_argument_briefs_v1` 替代 `method_concept_cards_v1`
- 不写卡即不算失败；不得为了兼容去调 Concept Architect

`publication_method_writer.py::run_publication_method_writer`：
`method_argument_briefs_v1` 若存在则优先于 concept cards。

测试：`tests/test_agentic_replay_execution_record.py` 更新 derived 集合。

CLI：`cli/agentic_run.py` 的 `--compile-concept-cards` 文档改为 deprecated；
新增 `--compile-argument-briefs` 作为 live 默认（replay rebuild 隐式打开）。

## 6. 切片、白名单、退出条件

不得一次 `/implement` 全文。每片结束后只读验收，再开下一片。

### WP-A — 确定性论证包编译

授权范围：

- `src/code2paper/agentic/method_argument_brief_models.py`（新）
- `src/code2paper/agentic/method_argument_brief_compiler.py`（新）
- `src/code2paper/agentic/method_argument_models.py` 仅增加 unit/graph 的
  `brief_*` 可选字段与闭包校验（不得改 proof 语义；那是 WP-B）
- `tests/test_agentic_method_argument_briefs.py`（新）

退出：

- 无 LLM 的 fixture：一条 supported 实现子句许可，一条同义务动机子句不许可
- 用冻结 DyG 主线义务编译：`licensed_wording` 不得等于整段 statement；
  Ebbinghaus / forgetting curve 类子句必须 `unlicensed`
- `may_enter_verified` 在存在 unlicensed 时为 False
- 无 `max_length=160` 字段能装下 `author_statement`
- focused：`python -m pytest -q tests/test_agentic_method_argument_briefs.py`
- 不跑 live，不改 replay

### WP-B — Architect / Writer / Replay 切主链 + proof 不变量

授权范围：

- `method_architect.py`（brief 绑定、content contract、`resolve_move_authority_proofs`）
- `intent_compiler_v2.py::build_story_spine_from_intent_graph`（短 title）
- `autonomous_method_agent.py::build_product_planning`
- `writer_view_projection.py`
- `publication_method_writer.py`（load briefs、view、claim 对齐）
- `llm/section_writer.py`（brief_mode schema）
- `writing_callback_fulfillment.py`（brief 槽位，最小必要）
- `scripts/run_authoring_replay.py`
- `cli/agentic_run.py`（旗标）
- 对应 tests（见 §7）

退出：

- live rebuild 路径单测：mock 无 LLM 也能从冻结形状产出 plan + briefs，
  且 **不调用** `compile_method_concept_cards`
- partial+anchored fixture 不再抛
  `anchored/bridge move authority proofs cannot carry unresolved rows`
- WriterView 有 licensed/unlicensed 分栏；二者 XOR concepts
- schema brief_mode 不含无约束 deferred proposition/concept 字段
- Gate 6A：`python -m pytest -q`（本片改动触及的全静态套件）
- 仍不跑三项 live

### WP-C — 一次 Mechanism Planner

授权范围：

- `method_argument_brief_planner.py`（新）
- `method_argument_brief_compiler.py` 接入 planner
- `_rebuild_derived_authoring` / `build_product_planning` 在 live LLM 且存在
  unlicensed/partial 时 `require_planner_for_unlicensed=True`
- `tests/test_agentic_method_argument_brief_planner.py`（新）

退出：

- stub planner：闭集外 `brief_id` / `frag` 被拒绝；合法草稿写入
  `planner_filled`
- 无 unlicensed 时不调 LLM（`planner_used=False`）
- 失败记 gap，不编造
- focused tests + Gate 6A

### WP-D — 一次 DyG canary（非 Gate 6C）

仅在 WP-C 静态通过后。协议同现 Gate 6B：

- 冻结根：`.tmp/c2p-stage1-canary/run-dyg/`
- `--rebuild-authoring --persist-authoring-rebuild-manifest`
- 禁止 `--reuse-authoring-callbacks`
- 新 `/tmp/c2p-wp-brief-dyg-qwen38-<stamp>/`
- 不得重跑 110938 / 133605 不变根
- 监控 `/health`、running/waiting、KV；Concurrency=1
- 验收：rebuild 不再先崩在 160 字或 anchored+unresolved；
  出现 `method_argument_briefs_v1`；`method_concept_cards_v1` 缺省；
  Candidate 是否 publication-ready 另判，**本次 canary 成功 ≠ Gate 6B/6C PASS**
- LinearRAG / EBCAR 只在 DyG 这一 canary 的 rebuild+Writer 都跑通后再并行

## 7. 测试矩阵

| 测试 | 切片 | 钉死的行为 |
|---|---|---|
| `tests/test_agentic_method_argument_briefs.py` | WP-A | 子句切分；supported 义务下动机子句 unlicensed；licensed_wording 闭包；digest；禁止 160 截断权威 |
| 同上，加载冻结 DyG JSON（只读） | WP-A | 主线 statement 不得整段 licensed；claims/spans 闭集非空 |
| `tests/test_agentic_method_architect_product_readiness.py` 增补 | WP-B | briefs 绑定 unit；proof partial+anchor |
| `tests/test_llm_publication_schema_closed_sets.py` 增补 | WP-B | brief_mode 字段；非法 deferred 拒绝 |
| WriterView 新测或扩 `tests/test_agentic_method_concept_cards.py` 旁路 | WP-B | XOR；licensed vs caveated |
| `tests/test_agentic_replay_execution_record.py` | WP-B | derived 含 briefs；rebuild mock 不调 concept compiler |
| `tests/test_agentic_autonomous_method_agent.py` | WP-B | `compile_concept_cards` no-op；写出 briefs |
| `tests/test_agentic_method_argument_brief_planner.py` | WP-C | 闭集、一次调用、失败 gap |
| 既有 `tests/test_agentic_method_concept_cards.py` | 全程 | **保持通过**；模块保留，不再是 live 默认 |

禁止用「过滤难写 claim / 缩小分母 / 空输出当成功」让测试变绿。

## 8. 调用量与校验量对比

以 DyG 冻结 Research 为量级（约数十条义务、数十条 claims、一次 4 节 Method）：

| 步骤 | 现在 | 目标 |
|---|---|---|
| Concept Architect | O(clusters)×(1–2) | 0 |
| Evidence Judge | O(clusters) | 0 |
| Mechanism Planner | 0 | 0（全许可）或 1（有未许可） |
| Architect plan | 1（确定性+proof） | 同左 |
| Writer | O(sections)×retries | 同左 |
| 中间 JSON 字段校验 | 每卡 ~10 个短语上限 | 每 brief：许可枚举 + id 闭集 |
| 易崩字段 | `story_node`≤160、逐卡 schema | 取消；author_statement 无短语上限 |

Writer/Formalizer/Editor 次数不在本方案承诺减少。减少的是 rebuild 前 40–90
分钟的逐卡 LLM 与其格式失败。

## 9. 实现时禁止的捷径

- 用义务级 completeness 直接 `licensed_wording = author_statement`
- 用英文词袋把子句匹配到任意 claim
- 把 planner 草稿当 Candidate 终稿或当 `deterministic_generated` 正文
- 为通过 proof 校验而清空 `unresolved_obligation_ids` 却仍把 partial 写成
  无 caveat 的 verified
- 把 Concept 编译失败改成「无卡即成功」而不产出 briefs
- 项目特判（DyG/EBCAR/LinearRAG 字符串进入 production compiler）
- 在 WP-A 顺手改 Writer / Formalizer / callback「顺便修完」

## 10. 与既有文档的关系

- 本文落实 2026-07-31 Writer 设计的论证层，纠正 2026-08-13/08-17 为防编造而
  引入的「写作再原子化」live 路径。
- 2026-08-20 方案的 WP0 拷贝边界、Candidate incumbent、Writer 内容见证、
  Formalizer 公式绑定、callback 槽位增益仍然有效；见证从
  `rendered_concept_keys` 换为 `rendered_brief_ids` + 许可 claim 闭集。
- 实现记录仍只写 `.agent/implementation.md`。本文不是 `.agent/plan.md`；
  开 WP-A 实现时由 Codex 另写 `.agent/task.md` / `.agent/plan.md`，范围仅 WP-A
  白名单。
)
