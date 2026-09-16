# Author Intent 主导的 Method Authoring 闭环修复执行文档（2026-09-16）

- 日期：2026-09-16
- `as_of`：2026-09-16
- 状态：根因已定位并吸收独立复核修订；生产修复、静态回归与新的 EBCAR live 验收待执行
- 绑定运行：`/tmp/c2p-production-entry-20260915-live10`
- 独立复核：[复核报告](/tmp/c2p-intent-spine-review-20260916-vp3oaaa8/review.md)与
  [验证证据](/tmp/c2p-intent-spine-review-20260916-vp3oaaa8/results.json)；历史 live source
  commit 为 `287506e3...`，当前 validator 探针绑定 `92236c25...`，两者不得混作同一代码快照
- 文档性质：细化
  [Method 意图优先写作设计](method_intent_first_authoring_redesign_2026-08-22.md)
  和
  [生产入口收敛执行文档](research_to_method_production_closure_execution_2026-09-15.md)
  的专项执行修订；不替代总体架构、Writer 多权威边界或 Verified 硬门

## 0. 结论与执行决策

用户记忆的协作原则是正确的，也是当前规范要求：**输入作者意图拥有论文的整体问题、章节、论证顺序和术语框架；代码证据只负责填充实现事实、条件、公式和可复现细节。**

本次 Authoring 没有按该原则执行，不是因为 intent 不清晰，也不是 Writer 单次采样偶然变差，而是 Unified 主线把两种“owner”混成了一种：

- 为防止无关代码被错误合并，`MechanismEvidenceClosure` 要求可执行 symbol owner；
- `NarrativePlanV3` 又直接以这些可执行 mechanism context 为章节 owner；
- 没有 symbol owner 的 story node 被保留在上游 artifact，却无法拥有 Narrative section；
- 原有五节作者计划只能在新建的两个 symbol section 之后做一次弱的反向适配；
- 最终 Writer 得到的是代码机制分页，而不是作者论证骨架。

这是**组织权威倒置**：防止证据误授权的 owner-first 规则被错误扩大成了“没有可执行 owner 就不能进入论文结构”。修复不能放宽代码证据门，也不能让 story node 直接授权实现事实；必须把“叙事 owner”和“证据 owner”拆成两个正交维度。

该倒置直接解释的是**五节作者结构为何丢失并退化为两个 `Sym:*` 节**。Research 原子化、公式身份、Writer/Binder 提交边界和最终语义验证还各有独立合同缺陷；它们会放大本次失败，但不能全部归因于同一个结构根因，必须分别修复和验收。

本文件固定以下目标架构：

```text
Author Intent Narrative Spine（章节、顺序、论证角色，组织权威）
    -> Intent Narrative Plan（story node 永不因缺代码而消失）
        -> Intent Evidence Atoms（把复合作者陈述拆成可独立判断的原子）
            -> Story <-> Mechanism 多对多绑定
                -> Repository Evidence Closure（实现事实权威）
                    -> field-level verdict / mismatch
        -> Author Formula Expectations
            -> Canonical Formula Obligations <-> Repository Evidence
                -> formula-worthiness -> accepted package -> committed consumption
        -> Paragraph contracts（按作者故事组织，按证据状态选择措辞）
            -> Writer + Binder 完整事务
                -> clean Candidate
                    -> semantic reverse validation
                        -> Verified 独立投影
```

执行顺序固定为 **P0 指标与冻结反例 → P1 叙事权威纠正 → P2 原子化 Research 闭环 → P3 公式身份桥接与筛选 → P4 Writer/Binder 事务 → P5 后处理归责 → P6 语义验证 → P7 正常产品入口 live 验收**。P0–P6 没有静态闭合前不重跑同一份全文 live。

## 1. 本次运行证明了什么

### 1.1 作者意图输入没有丢失

绑定运行中的 `author_story_spine_v1.json` 已明确给出：

1. 预计算 query/passage dense embeddings；
2. document ID 与 sinusoidal passage-position augmentation；
3. shared full attention 与 dedicated masked attention；
4. fixed-query InfoNCE training；
5. dot-product scoring 与 descending ranking。

同一运行的 legacy Method 计划也保留了五节论文顺序：motivation、embedding framework、architecture、training objective、inference。因而本次失败不在 intent intake 或作者结构本身。

### 1.2 结构丢失发生在 story 与 executable mechanism 的连接处

当前 [mechanism_context_compiler.py](../src/code2paper/agentic/mechanism_context_compiler.py) 的 `_collect_seed_data()` 只在 story node 携带显式 `mechanism_id` 或可执行 owner symbol 时，把它接入 mechanism seed；没有 executable owner 的 narrative node 会被跳过。随后 owner-first seed typing 又把 narrative-only row 从 closure merge 中排除。该限制对**证据 ownership**是正确的，但不应决定**论文 organization**。

本次 `author_story_spine_v1.json` 中的清晰 story nodes 没有 `mechanism_id`/owner symbol。结果：

- `mechanism_context_set_v1.json` 只剩两个由代码 symbol 生成的 context；
- 两个 context 的 `story_node_ids=[]`；
- `mechanism_name` 分别退化为 `Sym:9773C5Add7Af1F92` 和 `Sym:F6Cf5Bdfe2Ae16F0`；
- `reader_question` 退化为“How does mech_sym execute?”。

### 1.3 Narrative V3 是 mechanism-first，不是 intent-first

当前 [method_architect.py](../src/code2paper/agentic/method_architect.py) 的 `build_narrative_plan_v3()`：

- 主循环遍历 `contexts.contexts`；在本次 prior owner 无法证明的路径中，一个 executable mechanism 退化为一个新 section；
- `story_spine` 只通过 `story_node_ids` 参与 context 排序；
- story node 不独立创建或保有 section；
- prior plan 只有在旧 section 能证明唯一 mechanism owner 时才复用；
- 无法证明 owner 时，生成 `MA-REV-mech_sym-*` revision section。

由于本次 context 的 `story_node_ids` 为空，五节作者计划无法证明对两个 symbol mechanism 的唯一 ownership，于是被两个 `Sym:*` section 替代。

### 1.4 适配器只能事后回贴，无法恢复作者论证

当前 [publication_method_writer.py](../src/code2paper/agentic/publication_method_writer.py) 的 `_adapt_narrative_plan_to_method_section_plan()` 明确规定 section/paragraph identity 来自 Narrative plan，legacy units 只能按唯一 exact source anchor 回贴。

因此适配结果是：

- 24/28 argument units 被分配给两个 symbol section；
- 3 个 unit 对两个 section 同分而歧义；
- 4 个 unit 未分配；
- 新 section 的 argument moves、support/publication slots 没有从作者计划完整继承；
- 闭环指标最终为 `hard_targets=0`、`support_slots=0`、`publication_slots=0`；
- 最终质量报告判定 `candidate_argument_units_unrendered:0/28`。

适配器的 fail-closed 行为本身没有错误；错误在于它被放在权威方向的末端。正确方向应是“作者 section 持有身份，mechanism/detail 向 section 填充”，而不是“mechanism section 持有身份，作者 unit 尝试回贴”。

## 2. Research `44/11/25%` 的真实含义与真实缺口

### 2.1 当前指标把不同统计键和完成语义混在一起

[autonomous_method_agent.py](../src/code2paper/agentic/autonomous_method_agent.py) 的 `_write_closure_metrics()` 把 acquisition ledger 中 `ownership_role in {target_core, target_dependency}` 的 **obligation–candidate 记录数**命名为 `must_cover_candidates`。本次 44 条记录覆盖 17 个不同 symbol、6 个 obligation；44 既不是 44 个不同候选 symbol，也不是 44 个必须写入正文的 author-intent obligations。

同一函数用 `terminal_status == acquired_and_compiled` 的 11 条除以 44，得到 `target_core_packet_ratio=0.25`。但 [research_models.py](../src/code2paper/agentic/research_models.py) 又把 `resolution_status=implemented_partial` 视为 terminal；[implementation_scope.py](../src/code2paper/agentic/implementation_scope.py) 会给只有 read、behavior 或 packet 部分链的记录设置该状态。因此本次同时出现：

- 11/44 精确走完 read → behavior → packet → fact → claim；
- 其余多条只有部分链；
- `unresolved_acquisition=0`。

这个数字不能解释为“44 个必需方法点只找到 11 个”。它证明的是：**obligation–candidate 记录级全链获取率低，且当前 dashboard 不能表达 obligation/atom/field 是否真的闭合。**后续必须独立报告三种完成：搜索是否终止、Candidate 所需作者表述是否完整、仓库实现证明是否完整。三者不能互相代替。

### 2.2 仍然存在真实 Research 不完整

指标命名有误不等于 Research 已经充分。真实缺口包括：

1. 同一个 author claim 的证据分布在多个文件、symbol 和调用层级时，candidate ledger 仍按单个候选是否独立拥有 read、behavior、packet、fact、claim 全链计数，不能形成 obligation-level compositional proof。
2. 搜索与字段对齐消费的是过宽 semantic atom；例如“hybrid attention + global purpose + every layer + contextualized output”被当作一个 `operation` 字段。任何解释性部分缺少逐字代码陈述都会拖低整个字段。
3. `in every layer` 需要把 encoder 的 `ModuleList(num_layers)` 构造证据和 layer 内 shared/dedicated 两路计算证据组合起来；当前对齐输入没有形成这种跨文件、多 span 证明。
4. “global relationships”“intra-document coherence”等是作者 rationale，不应要求代码逐字证明，也不应反向授权为 repository fact。
5. 找到 partial 后没有以缺失 atom 为目标持续有界补证；宽句的搜索词继续竞争同一 Research 预算。

### 2.3 30 个旧字段中 25 个 deferred 的构成原因

当前 [method_argument_facet_aligner.py](../src/code2paper/agentic/method_argument_facet_aligner.py) 名义上支持 field-level alignment，但本次 `method_argument_facets_v1.json` 的 30 个 facet 各只有一个 semantic field，字段值往往仍是整句作者陈述；mainline 的 `formula_goal` 甚至容纳完整五步 pipeline。

形成该结果的具体路径是：

- 对 `pipeline_steps`、`key_building_blocks` 等 intent-grain 输入，`_decompose_brief()` 默认保留整条 YAML step，只有检测到 mixed authority 才调用细分 owner；
- `_facet_from_row()` 在发现 owner quote 大于 clause 时会缩窄 `exact_source_quote`，但不会同步缩窄 owner 返回的 `semantic_fields`；
- 因而 artifact 中出现“quote 是第一句、`formula_goal` 是完整五步 mainline”的内部不一致；
- alignment 虽按 field 判定，但一个 field 本身仍是复合主张；
- `compile_publication_field_candidates()` 对 unresolved/mismatch field 整体 deferred，只留下 5 个可消费字段。

所以“字段级”只落实到了 schema 名称，没有落实到最小可独立判断的语义原子。但 25 个 deferred 不能全部归因于复合字段：其中还包括作者 rationale、benchmark/外部比较、仓库输入不完整以及确实没有实现证据的字段。P0/P2 必须按 failure reason 和 authority lane 分组；原子化后的 atom 数也不要求仍为 30，只要求 30 个旧字段到新 atom/disposition 的来源覆盖可追溯且守恒。

## 3. 六类下游问题的根因与修复原则

### 3.1 证据对齐：拆叙事单元，不拆掉作者故事

一个 YAML stage 应继续作为一个 narrative unit，但其证据判定必须拆成多个 `IntentEvidenceAtom`。以 hybrid attention 为例，至少拆为：

| atom | 权威与判定 |
|---|---|
| query 与 enriched passages 进入 encoder | repository implementation |
| shared attention 实例与无 dedicated mask 的调用 | repository implementation |
| dedicated attention 实例与 mask 的调用 | repository implementation |
| 每个 encoder layer 都使用 hybrid layer | 跨构造与 forward 的 compositional repository proof |
| 输出为 contextualized passage embeddings | repository data-flow proof |
| shared 用于 global interaction | author rationale；不能要求代码逐字证明 |
| dedicated 用于 intra-document coherence | author rationale + mask implementation 分车道 |

任何一个 atom unresolved 都不能把其他已支持 atom 一起 deferred；任何 rationale 被作者声明也不能升级为仓库实现事实。

### 3.2 计划：作者 outline 必须是 section identity authority

不再从 `MechanismContextV1` 的数量推导 section 数量。新的 plan 必须先冻结：

- 作者提供的 section 顺序、heading intent、reader question；
- story node 与 argument unit 的原始归属；
- 每个 narrative unit 的 required/optional rhetorical moves。

Mechanism context 只通过显式多对多 binding 填入上述 section。一个 story node 可由多个 executable mechanism 支撑，一个 mechanism 也可支撑多个 story node。没有 repository binding 的 story node仍保留，并按 `author_specification`、`mismatch_statement` 或 review sidecar 处理。

### 3.3 Formalizer：先统一公式身份，再判论文价值与证据

当前报告把两套没有身份交集的公式分母放在同一条漏斗中：

| 层次 | live10 实际状态 |
|---|---:|
| legacy 作者计划公式 ID | 7 个 `formula:facet:*` / `formula:section:*` |
| mechanism 公式义务 | 84 个 `ob:formula:*`，全部为 `preferred` |
| accepted mechanism packages | 26 个，全部绑定已有 mechanism obligation |
| legacy 与 mechanism obligation ID 交集 | 0 |
| closure metrics 所记正文消费 | 24 个 mechanism package |

因此不能解释为“7 个必需公式生成了 26 个包，需删除多余 19 个”。24 个消费记录也只能说明 mechanism package 被消费，不能证明 7 个作者公式需求被满足。直接缺陷是**作者公式需求与 mechanism 公式义务之间没有 canonical identity bridge**；另一个独立缺陷才是 `compile_mechanism_formula_obligations()` 将大量 transformation/training/inference detail，以及 sort、normalize、reshape、concat operation 变成缺乏发表价值的 preferred 义务。

修复顺序必须是：

1. 建立 `author formula expectation → canonical formula obligation → source proof → accepted package → committed paragraph consumption` 的完整映射；
2. 允许多个作者需求引用同一个 canonical equation，但每个合并、降级或不展示决定都必须保留 typed disposition 与来源；不能靠减少 denominator 通过；
3. 再执行独立的 `formula_worthiness`：方法定义、训练目标、评分函数、状态更新、归一化、注意力/概率关系等可进入公式；`LOAD`、`WRITE`、`RESHAPE`、默认参数、列表初始化、返回容器、纯 shape/index arithmetic、日志/序列化及无学术定义的 sort/concat 默认只进 prose/algorithm；
4. author `formula_expectation=required|preferred|none` 是组织信号，不直接授权实现操作数；repository equation/operation 是事实信号，也不直接证明值得成为 display equation；
5. 每个 canonical obligation 至多提交一个 canonical package；辅助等价式作为同包内容，不能扩充 denominator；没有 canonical obligation 的 package 禁止进入 Writer。

公式内容门还存在双路径不一致：[formalization_agent.py](../src/code2paper/agentic/formalization_agent.py) 的 Section package validator 已调用 opcode/code-trace 禁令，而 Mechanism package validator 对冻结的 `WRITE(dedicated_attention_mask)` 仍返回零失败。两条路径必须复用同一个内容门，并从真实 Unified Formalizer 调用入口验证，不能只新增 worthiness 分类或旧 Section 接口单测。

### 3.4 Writer/Binder：诊断草稿与 clean Candidate 分离

当前 Writer aggregate 正确记录 15/18 page 完成、两个 required section 均未完成，Binder 也正确记录 4/21 complete、17/21 partial；但 `_compose_candidate_markdown()` 的设计会把非空、未通过 required witness transaction 的段落继续放入 `publication_candidate_method.md`，注释还明确称其为诊断用途。

这与“Candidate 是完整、可读作者逻辑”的上位合同冲突。修复为：

- `publication_candidate_method.md` 只在全部 required paragraph/section transaction committed 后写入或更新；
- partial/rejected Writer text 写入 `publication_candidate_diagnostic.md` 或 checkpoint sidecar，不进入 clean Candidate；
- 已有上一版 complete Candidate 时，失败续跑不得覆盖它；本次 partial 只进入诊断 checkpoint；
- Binder 必须按 paragraph contract 验证 story node、evidence atom、authority surface、formula obligation 和 transition；缺一个 required target 即不提交；
- required section 的完成状态逐节记录，aggregate 不再用“只要有非空正文即可成为 Candidate”的双重语义；
- Candidate completeness 与 Verified evidence completeness 继续独立。

### 3.5 Editor/Rewrite：只修所属问题，不接管内容缺口

Editor schema 失败、Rewrite 截断/schema 失败/patch span mismatch/no-progress 都是后处理失败，但它们不应负责弥补上游缺 target：

- missing story/evidence/formula target 路由回 Research、Architect、Formalizer 或 Writer；
- Binder transaction failure 路由回 Writer content repair；
- Editor 只处理跨节重复、顺序、术语和过渡；
- Rewrite 只处理局部论文语言、限定语和已绑定公式表达，必须保持 target-set digest；
- patch 以 `section_id + paragraph_id + incumbent_digest` 定位，不依赖易漂移的全文字符 span；
- 一次 representation repair 后 schema 仍失败即保留原 committed 内容并标记 incomplete；
- `no_progress` 立即停止该 owner，不得反复烧预算，也不得把未修正文提升为 Candidate。

### 3.6 最终验证：argument brief 主线也必须有命题闭集

[autonomous_method_agent.py](../src/code2paper/agentic/autonomous_method_agent.py) 当前只在 `argument_briefs is None and concept_cards is None` 时编译 `method_propositions_v1`。本次正常主线存在 argument briefs，因此命题编译分支天然不运行；最终 `method_proposition_alignment_v1.json` 只能报告 `method_propositions_v1_missing`。

此外 [publication_method_writer.py](../src/code2paper/agentic/publication_method_writer.py) 调用 `validate_text_evidence()` 时显式设置 `require_semantic_verifier=False`、`max_semantic_verifier_calls=0`，最终事实验证只能得到 `lexical_only`。当前 [proposition_semantic_aligner.py](../src/code2paper/agentic/proposition_semantic_aligner.py) 又把词汇 overlap `>=0.72` 标成 `exact`；独立探针把“adds”改成“subtracts”或“multiplies”仍得到 `matched` 且语义调用为 0，说明该路径只是高重叠召回，不是精确语义验证。

修复为：

- proposition validation sidecar 与 argument brief/facet authoring 输入并行存在，不再二选一；
- 从 `IntentEvidenceAtom + PublicationFieldCandidate + CandidateFacetPolicy + MechanismDetail` 编译统一的 `MethodPropositionSetV2`；
- Writer 可继续以 briefs/plan 写作，但每个 required paragraph 必须有 proposition/author-surface 闭集供 Binder 与最终反向验证使用；闭集约束可授权对象，不能过滤掉正文中闭集外的新正向 claim；
- 词汇相似只做召回，永远不能直接产生 `matched`；deterministic exact 只有在 canonical predicate/受控等价关系、主宾与输入输出角色、极性、量词、条件、边界及不可变数值/公式 token 全部守恒时才成立；
- 无法确定性证明的 claim 进入有界 semantic verifier；semantic owner 只在闭集内提出 alignment，最终 authority 仍由 harness 的 ID、excerpt、role、polarity、quantifier、condition、boundary 和 digest 校验决定；
- 每个被抽取 claim 独立记录 `exact_verified | semantic_verified | unresolved | rejected`。全体真正 exact 时允许零模型调用；这时报告是全量 `exact_verified`，而不是靠调用次数标记的 `lexical_only`；
- `method_propositions_missing`、任一必需 claim 仅 lexical-retrieved、semantic verifier unavailable/budget exhausted 或 unresolved positive 均不得得到 `publication_ready`。

## 4. 目标数据合同

### 4.1 `IntentNarrativePlanV4`

在 V3 旁新增版本化模型，不就地改变旧 artifact digest。最小字段：

```text
plan_id
source_intent_digest
sections[]:
  section_id
  heading_intent
  reader_question
  ordered_story_node_ids[]
  ordered_argument_unit_ids[]
  paragraphs[]
section_order_source = author_intent | accepted_author_plan
```

硬不变量：

1. 每个 must-cover story node 恰好属于一个 section；
2. repository evidence 的缺失、partial 或 mismatch 不得删除、改名或重排 story node；
3. mechanism 数量变化不得改变 section identity；
4. 自动组织提案只能在同一作者 section 内安排细节，跨 section 移动必须产生显式 proposal/trace，不能静默生效；
5. heading 采用作者语义或 Writer 生成的读者标题，禁止 `Sym:*`、`mech_*` 等内部标识成为论文标题。

### 4.2 `StoryMechanismBindingV1`

这是叙事图与证据图的 join，不是新的事实 authority：

```text
story_node_id
intent_atom_ids[]
mechanism_ids[]
binding_basis_ids[]       # claim/fact/span/relation/entrypoint closed ids
binding_status            # exact | partial | mismatch | unresolved
unresolved_atom_ids[]
content_digest
```

`unresolved` binding 仍允许 story node 留在 Candidate plan；它只禁止 repository wording 和 Verified promotion。

### 4.3 `IntentEvidenceAtomV1` 与字段证明

每个 atom 只承载一个可独立判定的谓词，至少包含 subject、predicate、object/operands、polarity、quantifier、condition、boundary、authority expectation、source quote range。不得把完整 pipeline、复合 stage 或 rationale 与 implementation 塞入一个 `operation` 字段。确定性 splitter 只能提出 candidate spans；责任 Agent 必须重新确认谓词以及否定、量词和条件作用域，失败时保留原 statement 与 `unresolved`，不得把句法可切分冒充语义已修复。

跨文件事实用 `FieldEvidenceProofV2` 表示：一个结论可绑定多个 exact spans 和显式关系路径。例如“每层采用 hybrid attention”必须同时绑定 layer stack construction 和 layer forward 中的两路 attention；单个 excerpt 不必逐字出现结论，但 proof graph 必须闭合。proof 还必须绑定相同 source snapshot、可达调用链和兼容 branch conditions；不同快照、互斥分支、未执行构造或只覆盖部分 layer 的 spans 禁止拼成全称结论。

### 4.4 `IntentAtomClosureStatusV1`

每个 must-cover atom 分别记录：

```text
search_status                   # searching | terminal
evidence_disposition            # repository_exact | repository_partial | author_spec_only | mismatch | bounded_not_found | out_of_scope
candidate_surface_status        # complete | incomplete | not_applicable
repository_proof_status         # exact | partial | mismatch | unavailable | not_applicable
author_surface_receipt_id
stop_reason
review_binding_id
```

`search_status=terminal` 只表示本轮搜索依法停止。`author_spec_only` 或 `out_of_scope` 本身不能把 must-cover 内容缺口清零；只有具备合法 stop reason、完整且正确限定的 author surface、paragraph/Binder receipt 和必要 review binding 时，Candidate surface 才能独立完成。Repository proof 是否完整继续单列，不能用 Candidate 完整性覆盖。

### 4.5 `CanonicalFormulaObligationV2`

```text
canonical_formula_obligation_id
source_author_formula_ids[]
source_intent_atom_ids[]
expectation                    # required | preferred | none
source_proof_ids[]
formula_worthiness             # display | inline | prose_or_algorithm | rejected
disposition_reason
accepted_package_id
committed_paragraph_ids[]
content_digest
```

旧作者公式 ID 与 mechanism obligation ID 都只能作为来源 ID，不能直接充当统一分母。每个旧需求必须可追到一个 canonical obligation 或 typed non-display/rejected disposition；每个 accepted package 和 committed consumption 必须反向追到同一个 canonical identity。若来源 expectation 为 `required`，non-display/rejected disposition 仍保持 open，除非经过显式 author-plan revision/review；不得由 worthiness 分类自动降级并关闭。

### 4.6 `CandidateSectionTransactionV3`

一次 section 提交必须同时闭合：

```text
required_story_node_ids
required_argument_unit_ids
required_intent_atom_ids
required_repository_proposition_ids
required_author_surface_ids
required_canonical_formula_obligation_ids
required_paragraph_ids
completed_paragraph_receipt_digests
binder_status = complete
```

任一 required 集合缺失时只能保存 diagnostic/checkpoint，不能更新 clean Candidate。

### 4.7 `ClaimVerificationReceiptV2`

```text
claim_id
paragraph_id
retrieved_proposition_ids[]
verification_status            # exact_verified | semantic_verified | unresolved | rejected
predicate_role_polarity_check
quantifier_condition_boundary_check
semantic_call_receipt_id
evidence_digest
```

聚合验证模式必须由逐 claim 状态派生，而不是由“是否至少调用过一次模型”决定。词汇检索分数只能进入候选排序，不能写入 `verification_status`。

## 5. 分阶段实施工作包

### P0 — 冻结反例与指标纠正

负责文件：

- [autonomous_method_agent.py](../src/code2paper/agentic/autonomous_method_agent.py)
- [research_models.py](../src/code2paper/agentic/research_models.py)
- [implementation_scope.py](../src/code2paper/agentic/implementation_scope.py)
- 新增最小化的 EBCAR intent-first regression fixture

实施：

1. 把当前 44 条精确命名为 `obligation_candidate_records`，同时报告 17 个 unique symbols、6 个 unique obligations，以及 discovered/read/behavior/packet/fact/claim/full-chain 各阶段状态。
2. 新增 `must_cover_obligations`、`must_cover_intent_atoms`、`legacy_field_to_atom_trace_coverage` 和 `required_field_disposition_coverage`；不得把记录数、unique symbol 数和 obligation 数混为同一分母。
3. 区分 `search_terminal`、`candidate_surface_complete` 与 `repository_proof_complete`；`implemented_partial` 可终止某次候选搜索，但不得算 evidence complete，`author_spec_only/out_of_scope` 也不得单独算 Candidate content complete。
4. 按 obligation 去重统计“至少一个 exact candidate 已全链闭合”“只有 partial”“mismatch”“bounded not-found”，并按 failure reason/authority lane 分解 deferred。
5. 冻结 intent、legacy formula、mechanism obligation、package、paragraph consumption 的 ID/版本/摘要，先生成公式身份守恒表，禁止后续阶段用另一分母覆盖旧需求。
6. 从本次 `/tmp` 产物提取最小、去项目路径硬编码的 fixture；测试不依赖临时目录，并记录历史 live source digest 与当前 probe code digest，禁止跨快照拼接结论。

退出条件：dashboard 不再把 44 条 obligation–candidate 记录称为 44 个必需点；不能再出现“25% full-chain、0 unresolved”却无法知道哪些 intent atom 未闭合的状态；三种完成状态与公式身份守恒表均可独立审计。

### P1 — 纠正 Narrative 权威方向

负责文件：

- [mechanism_context_models.py](../src/code2paper/agentic/mechanism_context_models.py)
- [mechanism_context_compiler.py](../src/code2paper/agentic/mechanism_context_compiler.py)
- [method_product_models.py](../src/code2paper/agentic/method_product_models.py)
- [method_architect.py](../src/code2paper/agentic/method_architect.py)
- [publication_method_writer.py](../src/code2paper/agentic/publication_method_writer.py)
- [unified_context_models.py](../src/code2paper/agentic/unified_context_models.py)
- [unified_context_compiler.py](../src/code2paper/agentic/unified_context_compiler.py)
- [narrative_organization_proposal.py](../src/code2paper/agentic/narrative_organization_proposal.py)

实施：

1. 新增 `IntentNarrativePlanV4` 与 `StoryMechanismBindingV1`，保留 V3 reader 供历史 artifact 诊断。
2. 先从 author story/order 或已接受的 intent-derived legacy plan 冻结 section identity，再编译 story↔mechanism binding。
3. `MechanismEvidenceClosure` 继续要求 executable owner；但 closure 无权创建、删除或重命名 author section。
4. 逆转当前 adapter：从 intent plan 向段落注入 mechanism/detail/formula，而不是从 mechanism plan 回贴 legacy argument units。
5. story 没有 evidence owner 时保留 paragraph slot，设置 `author_specification`/review surface；不伪造 mechanism id。
6. 禁止内部 symbol 名直接成为 heading；必要时由 Writer 在 author heading constraints 内生成标题。
7. 把当前只组织单一 `mechanism_id` 的 proposal 合同改为 section-first closed choice；同一作者 section 可绑定零个、一个或多个 mechanism，proposal 只能安排 detail，不能改变作者 section identity。
8. 做最小纵向切片，逐字核验 `section_id/story_node_id/argument_unit_id/authority surface` 从 plan 经 archive、workset、page payload、真实 Writer request 一直保留到 Binder receipt；只通过 plan 文件的 5 节检查不算完成。

EBCAR 冻结验收：五节作者结构保留；28/28 argument units 有唯一原 section；不存在 `MA-REV-mech_sym-*`/`Sym:*` 标题；mechanism context 即使仍为两个，也只能作为五节中的证据提供者。另以“有证据但无 executable story owner”“一个 section 跨多个 mechanisms”“author-only 暂无 repository evidence”三个 section 做 plan→Writer request→Binder receipt 纵向验收。

### P2 — Intent atom 驱动的 Research 与 compositional alignment

负责文件：

- [method_argument_facet_aligner.py](../src/code2paper/agentic/method_argument_facet_aligner.py)
- [intent_obligations.py](../src/code2paper/agentic/intent_obligations.py)
- [research_graph.py](../src/code2paper/agentic/research_graph.py)
- [implementation_scope.py](../src/code2paper/agentic/implementation_scope.py)
- [mechanism_context_compiler.py](../src/code2paper/agentic/mechanism_context_compiler.py)
- [writing_callback_fulfillment.py](../src/code2paper/agentic/writing_callback_fulfillment.py)

实施：

1. narrative unit 与 evidence atom 分层：YAML step 不拆出作者计划，但始终拆出独立可判定 atoms。
2. 对 owner 输出执行 source-range 校验：`semantic_fields` 不得宽于 `exact_source_quote`；违规先做一次有界语义 repair。确定性 clause/phrase splitter 只能提出候选 spans，必须保留谓词、量词、否定、条件与 boundary，并重新交责任 Agent 校验；仍未闭合则保留原 statement 和 `unresolved`，不得由 harness 宣称 atom 有效。
3. operation、scope、condition、effect、rationale、guarantee 分开；作者解释默认走 author lane。
4. Research scheduler 按缺失 atom 生成精确 query/target，不再拿整句的十几个关键词竞争同一轮。
5. 允许一个 field proof 组合多个 exact spans、symbols 和关系路径；不得因单个 excerpt 没逐字写“every layer”而拒绝已经闭合的构造+执行证明，同时要求 snapshot、call reachability 和 branch compatibility 守恒。
6. partial alignment 立即产出 supported sub-atoms；只对缺失 sub-atoms 续搜。
7. bounded search 结束必须给每个 required atom 一个 terminal disposition：`repository_exact`、`repository_partial`、`author_spec_only`、`paper_code_mismatch`、`not_found_after_bounded_search` 或 `out_of_scope`；随后分别计算 Candidate surface 与 repository proof 状态，terminal disposition 不自动清零内容缺口。
8. callback 只重编译受影响 atom、binding、paragraph contract 和下游消费者；intent/atom decomposition 或 proof policy digest 变化必须使依赖缓存失效，不重跑无关且 digest 仍合法的 Research。

EBCAR 冻结验收至少覆盖：

- stack construction + layer forward 组合证明“每层两路 attention”；
- 不同 source snapshot、互斥分支、未执行构造、只有部分 layer 使用两路 attention 均不能组合成“每层”证明；
- shared/dedicated 实现事实与 global/intra-document 作者解释分车道；
- sinusoidal generation 与 frozen embedding 的真实实现状态；
- forward/rerank mask 行偏移差异形成明确 paper-code mismatch；
- fixed query、InfoNCE、dot product、descending sort 分别闭合，不互相连坐；
- 30 个旧字段全部可追到一个或多个新 atom/disposition；新 atom 数不固定，不要求把真实 mismatch 强行改成 supported。

### P3 — 公式身份桥接、价值门与单义务单包

负责文件：

- [formalization_agent.py](../src/code2paper/agentic/formalization_agent.py)
- [method_product_models.py](../src/code2paper/agentic/method_product_models.py)
- [unified_context_compiler.py](../src/code2paper/agentic/unified_context_compiler.py)
- [response_schemas.py](../src/code2paper/llm/response_schemas.py)
- [section_writer.py](../src/code2paper/llm/section_writer.py)

实施：

1. 先生成 `CanonicalFormulaObligationV2`：把 7 个 legacy 作者公式 ID 与 84 个 mechanism obligations 映射到 canonical identities，保留 required/preferred、来源、合并和 non-display disposition。
2. 新增 `FormulaWorthinessV1`，把 authority/evidence validity 与 publication worthiness 分开；普通 operation detail 不再自动创建 display obligation。
3. 删除 reshape/sort/concat 的默认 display-equation 资格；仅在作者 plan 明确要求并有学术定义时例外。
4. `LOAD/WRITE/RESHAPE`、shape/index/default/list/control plumbing 建立 negative regression set。
5. Formalizer response 必须绑定一个 canonical obligation；每个 canonical obligation 只有一个 canonical accepted package，所有 paragraph consumption 反向引用同一 ID。
6. 抽取共享 formula content guard，供 Section 与 Mechanism validator 共用；统一禁止 `self.`、`torch.`、operation opcode、函数 trace、默认参数和容器初始化，符号定义必须读者可见。
7. 测试必须穿过真实 Unified page/workset/request/response/validation/consumption 路径；冻结的 `WRITE(dedicated_attention_mask)` package 必须在 Mechanism 路径被拒绝。

EBCAR 冻结验收：7 个 legacy 作者需求、84 个 mechanism obligations、26 个 accepted packages 和 24 个消费记录全部进入可追溯的 canonical identity table；legacy→mechanism 原始交集为 0 的事实必须被桥接而非隐藏。验收不要求 package 数机械等于 7；要求每个作者需求都有 canonical/display-or-typed-non-display disposition，每个 accepted/consumed package 都反向闭合，incidental/code-trace package 为 0，任何合并或降级都有 typed diff 且不降低原始需求分母。

### P4 — Writer/Binder 完整事务与 Candidate 分流

负责文件：

- [publication_method_writer.py](../src/code2paper/agentic/publication_method_writer.py)
- [section_writer.py](../src/code2paper/llm/section_writer.py)
- [unified_context_models.py](../src/code2paper/agentic/unified_context_models.py)
- [unified_context_compiler.py](../src/code2paper/agentic/unified_context_compiler.py)
- [narrative_organization_proposal.py](../src/code2paper/agentic/narrative_organization_proposal.py)
- [method_content_trace.py](../src/code2paper/agentic/method_content_trace.py)
- [research_derived_authoring.py](../src/code2paper/agentic/research_derived_authoring.py)

实施：

1. Writer page/paragraph contract 从 `IntentNarrativePlanV4` 生成，包含 story、atom、authority surface、canonical formula 与 transition targets；P1 的 section/story identities 必须原样进入实际 Writer request 和 Binder receipt。
2. Writer 输出必须逐 paragraph 提交；Binder complete 后才能计入 section receipt。
3. aggregate `completed_section_ids` 逐节保留，不用“若非全体完成则整体置空”隐藏局部状态；另有 `all_required_sections_complete`。
4. `_compose_candidate_markdown()` 只组合 committed sections/paragraphs；partial text 改写入 diagnostic artifact。
5. clean Candidate 首次 checkpoint 必须在全体 required section complete 后；已有 complete incumbent 继续受 digest 保护。
6. `candidate_argument_units_rendered`、story node coverage 和 required atom coverage 从 Binder receipt 计算，不能靠词法出现或 section 非空推断。
7. 在此阶段冻结 proposition/authority contract IDs，供 Binder 和 P6 共用；避免到最终验证才发现 paragraph receipt 无法反向绑定。Candidate committed、Candidate publication-ready 与 Verified 始终是三个独立状态。

退出条件：类似本次 15/18 page、Binder 4 complete/17 partial 的状态只能得到 diagnostic draft 和 `incomplete`；第 25、75 行对应的缺 target 段落不能进入 clean Candidate。

### P5 — Editor/Rewrite issue ownership 与稳定 patch

负责文件：

- [publication_issue_owner_router.py](../src/code2paper/agentic/publication_issue_owner_router.py)
- [cross_section_editor.py](../src/code2paper/agentic/cross_section_editor.py)
- [rewrite_agent.py](../src/code2paper/agentic/rewrite_agent.py)
- [writer_section_repair.py](../src/code2paper/llm/writer_section_repair.py)

实施：

1. 建立 failure→owner 闭表；未知 failure fail-closed，不默认给 Rewrite。
2. content/target 缺口回 Writer/Binder；evidence 缺口回 Research；公式缺口回 Formalizer。
3. Editor 输入只含已 committed section，并以 section/paragraph digest 约束修改。
4. Rewrite patch 使用 paragraph identity 和 incumbent digest；patch 前后 required target set、authority lane 和 formula obligation set 必须相同。
5. schema/length/span/no-progress 分开记账；无语义增益不再重试。

退出条件：后处理失败不能使 clean Candidate 倒退，也不能把 diagnostic incumbent 提升为 Candidate；代码味在 Writer/Formalizer 提交前已有硬门，Editor 不再承担清洗大量 `LOAD/WRITE/RESHAPE` 的任务。

### P6 — 强制命题闭集与语义反向验证

负责文件：

- [autonomous_method_agent.py](../src/code2paper/agentic/autonomous_method_agent.py)
- [method_proposition_compiler.py](../src/code2paper/agentic/method_proposition_compiler.py)
- [proposition_semantic_aligner.py](../src/code2paper/agentic/proposition_semantic_aligner.py)
- [text_evidence_validator.py](../src/code2paper/agentic/text_evidence_validator.py)
- [publication_method_writer.py](../src/code2paper/agentic/publication_method_writer.py)

实施：

1. argument briefs 与 proposition validation set 并行编译；删除当前互斥条件。
2. 为 repository、author specification、mismatch 三种 Candidate surface 分别建立命题与可接受限定语。
3. final claim extractor 扫描所有 committed prose/formula claim；paragraph contract 的闭集用于确定“可授权到谁”，不能把闭集外新 claim 从验证输入中过滤掉。
4. lexical overlap 只召回候选。重定义 deterministic exact：canonical predicate 或注册的有向等价关系、subject/object/input/output roles、polarity、quantifier、condition、boundary、numeric/formula tokens 必须全部守恒；任一无法确定就不算 exact。
5. 非 exact claim 调用有界 semantic aligner；结果再经 exact IDs、evidence excerpts、roles、polarity、quantifier、condition、boundary、authority lane 和 digest 校验。
6. 每个 claim 写 `ClaimVerificationReceiptV2`；聚合覆盖从逐 claim 状态计算，不再由实际语义调用次数决定 `mode`。全 exact 可以合法为 0 次调用，但不能存在任何仅靠 lexical overlap 的已验证 claim。
7. 验证调用进入统一预算/receipt；预算不足返回 incomplete，不退化为 lexical-only ready。
8. quality gate 要求 claim extraction coverage、proposition render coverage、semantic ambiguity=0、unsupported positive=0；Verified 另要求 repository evidence validation 全部通过。

退出条件：有 argument briefs 的正常运行也必须生成 `method_propositions_v2` 和实际 alignment report；加法→减法/乘法、主宾反转、条件删除、量词扩大和闭集外新正向句均不能通过 lexical 路径。`method_propositions_missing`、任一必需 claim 未达到 `exact_verified|semantic_verified`、semantic verifier unavailable/budget exhausted 均阻止 `publication_ready`；`semantic_alignment_calls=0` 本身既不代表失败也不代表成功。

### P7 — 正常产品入口受控验收

P0–P6 静态与冻结集成通过后，才使用仓库指定的 `8006/qwen38-27b-nvfp4` 做一次新的 EBCAR 正常 `method-agent run`。运行前按仓库规范记录 health、models、模型/tokenizer identity、queue/KV 状态和全新 `/tmp` 输出目录；复用仍合法的 Research/Formalizer 成果时必须通过现有 digest/receipt 重验。intent、atom decomposition、formula identity/worthiness 或 proposition policy 改变时，对应旧请求必须失效；未变化且 receipt/digest 仍合法的完成分支在 resume 时应保持零新增生成调用。

不得重放本次失败 Writer 响应作为质量成功；不得为获得较好采样重复无变化全文；失败只回到所属 owner 并局部 resume。

## 6. 必须新增的反例与集成测试

优先扩展现有测试，不把项目专用路径或已知答案写入通用生产逻辑。

### 6.1 Narrative authority

- story node 没有 executable owner：仍出现在原 section，不能拥有 repository claim；
- 一个 story node 绑定两个 mechanisms：section 不分裂；
- 一个 mechanism 支撑三个 story nodes：三个 story node 仍按作者顺序出现；
- mechanism 数量从 2 变 3：author section ids/headings/order 不变；
- 内部 `sym:/mech_` 标识不能成为 heading；
- EBCAR fixture 保留五节与 28/28 units；
- 有证据但 story 无 executable owner、跨 mechanism section、author-only section 三条纵向切片从 plan、workset、page、实际 Writer request 到 Binder receipt 均保持 author IDs。

### 6.2 Research/alignment

- 宽句拆成 implementation、scope、rationale、effect 原子；
- owner quote 被缩窄时，宽于 quote 的 semantic field 进入有界语义修复；splitter 候选未保留量词、否定或条件时必须 unresolved；
- 两个文件的 spans 和显式 relation 可组成“every layer”证明；
- 不同快照、互斥分支、未执行构造、仅部分 layer 的 spans 不能组成“every layer”证明；
- 一个 atom partial 不影响兄弟 atom 进入 Candidate；
- rationale 只有作者权威时按 author specification 渲染，不能进入 Verified；
- 44 条 obligation–candidate 记录、17 symbols、6 obligations 和 atom/legacy-field trace 使用不同分母；
- search terminal、Candidate surface complete、repository proof complete 三种状态不能互相代替。

### 6.3 Formula

- 7 个 legacy 作者公式 ID 与 84 个 mechanism obligations 通过 canonical identity table 对应；原始零交集不得被静默改写；
- 两个作者需求可共享一个 canonical equation，但两个来源 ID 均保留；合并/降级有 typed diff；
- `LOAD(x)`、`WRITE(y)`、`RESHAPE(x)`、list initialization、default `None`、shape/index arithmetic 均不创建 display formula obligation；
- InfoNCE、dot-product score、真正的 normalization/update 可在有 obligation 和证据时创建；
- 一义务多包、无义务包拒绝；未声明 multi-mechanism canonical proof 的跨 mechanism 包拒绝；
- LaTeX 含 `self.`/`torch.`/trace predicate 拒绝；
- 冻结 `WRITE(dedicated_attention_mask)` 必须经过真实 Unified Mechanism validator 路径并被共享内容门拒绝。

### 6.4 Writer/Binder/Postprocess

- required page 缺 1 个：无 clean Candidate，有 diagnostic；
- Binder 20/21 complete：无 clean Candidate；
- 已有 complete Candidate + 失败 resume：旧 Candidate 保持；
- Editor schema failure：不覆盖 committed body；
- Rewrite patch digest/span mismatch：拒绝且不修改 target set；
- no-progress：不再发送同 owner 的相同请求。

### 6.5 Final validation

- argument briefs 存在时 proposition set 仍生成；
- 加法→减法/乘法、主宾反转、条件删除、否定或量词改变均只能召回，不能 deterministic exact；
- 仅当谓词、roles、极性、量词、条件、boundary 和不可变 token 全部守恒时，exact proposition 才可零 semantic call；
- 非 exact claim 必须语义调用，闭集外新正向 claim 仍须被抽取并拒绝；
- 语义 owner 试图扩大 guarantee/condition：harness 拒绝；
- 每个 claim 独立得到 `exact_verified|semantic_verified|unresolved|rejected`，聚合状态不由调用次数命名；
- propositions missing、semantic budget exhausted 或任何仅 lexical-retrieved/unresolved positive 均不能 publication-ready；
- Candidate author-spec 可 caveated，Verified 不可继承该权威。

## 7. 验收指标

### 7.1 冻结 EBCAR 确定性验收

| 维度 | 当前失败基线 | 退出要求 |
|---|---:|---:|
| 作者 section | 5 节被投影为 2 个 `Sym:*` 节 | 5/5 保留，顺序和语义标题正确 |
| argument units | 24/28 绑定，4 未分配，3 歧义，0/28 渲染 | 28/28 保有唯一原 section；required render 由 Binder 证明 |
| story↔mechanism | context `story_node_ids=[]` | 每个 required story node 有 exact/partial/mismatch/unresolved binding disposition |
| acquisition dashboard | 44 条 obligation–candidate 记录、17 symbols、6 obligations；11 full-chain 被误称 must-cover 25% | record、symbol、obligation、atom、legacy field 五套统计键独立 |
| closure semantics | search terminal 与 evidence/content complete 混用 | search terminal、Candidate surface、repository proof 三种状态独立 |
| typed fields | 30 个旧 field 中 5 可消费、25 deferred | 30/30 旧 field 可追到新 atom/disposition；新 atom 数不固定，按 failure reason/authority lane 分组 |
| planning targets | hard/support/publication 全 0 | required story/atom/surface targets 非空且与 plan 守恒 |
| formulas | 7 legacy IDs；84 preferred mechanism obligations；26 accepted、24 consumed；两套 obligation ID 交集为 0 | canonical identity bridge 全覆盖；每个旧需求与 accepted/consumed package 可双向追溯；不以包数等于 7 验收；incidental/code-trace package=0 |
| Writer | 15/18 pages；required section complete=0 | 所有当前计划 required invocations/sections complete |
| Binder | 4/21 complete、17/21 partial | required paragraphs 全部 complete；partial 只进 diagnostic |
| proposition validation | missing/not-run | validation set 必存，render/evidence alignment 实际运行 |
| fact validation | lexical-only；加法改减法/乘法仍 lexical `matched` | 每个 claim 为 exact_verified/semantic_verified/unresolved/rejected；所有 verified claim 保持谓词/角色/极性/量词/条件，歧义为 0 |

### 7.2 新 live Candidate 验收

同时满足才可报告 Candidate 完成：

1. 正常产品入口 exit 与 `product_authoring_state` 都表示完成，不能只看文件存在；
2. clean Candidate 按作者 intent 组织，必需 story/argument/atom/formula/paragraph transaction 全闭合；
3. 标题、正文和公式无内部 ID、代码 trace、审计 bookkeeping；
4. `unsupported positive claims=0`，author-spec/mismatch 有正确可见措辞与 sidecar；
5. proposition alignment 已运行，每个 claim 有 verification receipt；真正 exact 可零调用，其他 claim 的 semantic validation 有 receipt；
6. 作者公式需求经 canonical obligation 闭合到 package 与 committed consumption，typed non-display disposition 可审计，incidental/code-trace formula 为 0；
7. Editor/Rewrite 只改 committed 内容并保持 target-set digest；
8. Verified 独立报告，不因 Candidate 完整而自动通过；
9. 同一完成目录 resume 的新增生成调用为 0；intent/atom/formula/proposition policy 改变时只使依赖分支失效；
10. 人工复核 EBCAR 的 frozen embeddings、hybrid attention、mask 路径、InfoNCE 和 rerank 描述与源码一致，并明确纸码差异。

## 8. 验证命令与执行纪律

每个工作包先跑对应文件，P6 完成后跑组合回归；进入 P7 前跑全量静态：

```bash
python -m pytest -q \
  tests/test_agentic_intent_compiler_v2.py \
  tests/test_agentic_method_argument_facet_aligner.py \
  tests/test_agentic_method_architect_product_readiness.py \
  tests/test_agentic_narrative_architect_v3.py \
  tests/test_agentic_unified_context_compiler.py \
  tests/test_agentic_mechanism_formula_obligations.py \
  tests/test_agentic_formula_obligation_truths.py \
  tests/test_agentic_formalization_guards.py \
  tests/test_agentic_publication_method_writer_unified.py \
  tests/test_agentic_detail_atom_binder_and_trace_v2.py \
  tests/test_agentic_proposition_semantic_aligner.py \
  tests/test_agentic_final_text_trust.py \
  tests/test_agentic_writer_paper_language_quality.py

python -m compileall -q src tests scripts
python -m pytest -q
git diff --check
```

实施纪律：

- 不通过降低 evidence、formula、Binder、authorship 或 final-integrity 门修复；
- 不把 author intent 当 repository evidence；
- 不把代码缺失等同 story 删除；
- 不把某个 candidate symbol 的 partial/full-chain 状态冒充 intent obligation 完整性；
- 不把 lexical overlap 冒充 exact semantic verification，也不为改变聚合标签而发送空语义调用；
- 不把两套公式 ID 的包数当成同一漏斗，不以降低、合并或改名需求分母获得通过；
- 不在通用代码中硬编码 EBCAR 路径、symbol、section 数或已知答案；
- 不在 P0–P6 尚有确定性反例时进行无变化全文 live；
- 每个 callback/retry 只重做受影响 atom、binding、formula、paragraph 与验证依赖；
- 旧 V3/V2 artifact 保持可读；新合同使用显式版本和 migration trace，未通过 P7 前不做默认 cutover。

## 9. 完成定义

本专项只有在以下三层都完成时才可关闭：

1. **架构层**：作者 narrative owner 与 executable evidence owner 已分离，intent plan 是唯一 section identity authority；
2. **确定性层**：本文件所有反例通过，冻结 EBCAR 达到 §7.1，partial 产物不能进入 clean Candidate；
3. **产品层**：一次新的正常入口 EBCAR live 达到 §7.2，并证明 resume、预算、调用 receipt 和最终语义验证可审查。

只修复 `Sym:*` 标题、只提高 Research 调用数、只让 25 个 deferred 变成 supported、只按 `26-7` 删除公式包、只让 Writer 18/18 transport 完成，均不足以关闭本专项。最终要证明的是：**作者意图稳定拥有整篇 Method 的论证结构，作者公式需求经 canonical identity 连接证据与正文消费，代码证据以原子、可组合、可反向验证的方式填入该结构，而任何中间失败都不能再次倒置或混淆这些权威与身份层。**
