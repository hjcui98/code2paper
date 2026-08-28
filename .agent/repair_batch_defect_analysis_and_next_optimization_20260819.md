# Repair 批次缺陷汇总与下一步代码级优化方案

- 日期：2026-08-19
- 性质：**只读诊断 + 实施提案**。本文不是新的验收权威，也不建立平行文档体系。
- 上位权威不变：`AGENTS.md` → `.agent/plan.md` §19 → `.agent/review.md`（当前结论仍为 `REPAIR`）→
  `docs/method_agent_master_agent_mainline_execution_repair_plan_2026-08-17.md`。
- 绑定代码态：`sha256:920dcb36db72480555478a70fe99fe89817bc83cdbe7194f3970310166c41d36`
- 绑定产物：`.tmp/c2p-repair-batch/replay-{dyg,linearrag,ebcar}`（2026-08-19 串行批次）
- 对照输入：`/data1/users/cuihengjia/code2paper/paper_final/{029_DyG-Mamba…,053_LinearRAG…,022_EBCAR…}.md`
  与各仓库根下的 `paperdraft.md`（仅作 author intent / 质量参照，不授权实现事实）
- 本文未重跑测试、模型、API、benchmark 或 replay。

---

## 0. 一句话结论

五项 REPAIR 代码义务基本落地，callback 续跑与输出语义解耦是真实进展；但**没有一项内容质量目标在实跑中达成**：
公式 0/0/1、`argument_move_coverage` 0.29/0.31/0.38、三项目 `publication_ready=false`。

本轮暴露的问题不是"再多改一个模块"，而是 **7 组缺陷 / 5 个根因**，其中两个根因是纯代码级矛盾
（不同守卫对同一对象的权威定义不一致；已实现且已单测的判定函数在产品路径上没有调用点），
调 prompt 或换更强模型都无法消除。这也解释了"静态套件 2661 passed"与"正文里仍有
`loss_i.shape[0] == 0`"为什么可以同时成立。

---

## 1. 批次事实基线

字段出处：`utility.*`/`safety.*` 在 `07_validation/publication_quality_report_v1.json`；
`candidate_generation_status`/`candidate_validation_status`/`verified_validation_status`/`publication_ready`
在 `06_authoring/publication_writer_result_v1.json`；`semantic_verifier_calls` 在
`07_validation/agentic_text_evidence_validation.json`。Verified 正文在
`06_authoring/repository_verified_method.md`。

| 指标 | DyG | LinearRAG | EBCAR |
|---|---|---|---|
| 章节 | 4/4 | 3/3 | 5/5 |
| Candidate | 6.71 KB / 947 词 | 4.98 KB / 656 词 | 8.77 KB / 1154 词 |
| Verified | 2.69 KB / 390 词 | 1.04 KB / 140 词 | 2.65 KB / 353 词 |
| candidate_generation_status | generated | generated | generated |
| candidate_validation_status | warnings | passed | passed |
| verified_validation_status | incomplete | passed | passed |
| publication_ready | false | false | false |
| unsupported_positive_claims (safety) | 4（全 `numeric_token_not_in_direct_evidence`） | 0 | 0 |
| support_precision | 0.0 | 1.0 | 1.0 |
| hard_gate_passed | false | true | true |
| 公式包（accepted） | 0 | 0 | 0 |
| 正文 LaTeX | 0 | 0 | 1（`top-$k$`） |
| equation_coverage | 0.0 | 0.0 | 0.0 |
| argument_move_coverage | 0.293 | 0.313 | 0.378 |
| supported_unit_recall | 0.556 | 0.667 | 1.0 |
| information_density | 0.060 | 0.055 | 0.073 |
| reproducibility_detail_coverage | 0.0 | 0.0 | 0.0 |
| configuration_coverage | 1.0 | 0.0 | 0.0 |
| content_role: equation / overview / transformation | missing | missing | missing |
| quality status | blocked | incomplete | incomplete |
| plan_gate_passed | true | true | true |
| utility_gate_passed | false | false | false |
| final_integrity_gate_passed | false | false | false |
| Editor 文档级决策 | **reject，reasons=[]** | **reject，reasons=[]** | accept |
| semantic_verifier_calls | 0 | 0 | 0 |
| callback fulfilled / pending | 4 / 0 | 2 / 0 | 3 / 0 |
| callback termination | 全部 `max_turns_reached` / incomplete（8 turns） | 同 | 同 |
| callback obs=0 且 facts>0 | 3/4 个 continuation | 0/2 | 1/3 |

对照原文的主线结论（§19.7.4 三项目目标）：**三项均未达到**。DyG 正文中心是 routing/top-k/padding 与
edge-bank；LinearRAG 结构最接近原文但算法与公式几乎为空；EBCAR 机制名词齐全但训练/推理/公式虚化。

---

## 2. 缺陷清单（按根因归类，每项给到文件/行）

### Cluster A — 作者意图进了系统，但被定义为"不可断言"

这是本轮最重要的发现，且与"Architect 没按作者意图分节"的直觉相反。

**A0（事实澄清）：作者意图确实完整进入了 Writer 输入。**
- `story_spine.json`：DyG 23 / LinearRAG 22 / EBCAR 30 个节点，带完整 `author_statement`。
- `authoring_projection_v1.json` 带 `author_goal` 与同一条 `author_story_spine`。
- Architect 章节标题直接取自 story 节点标题；三项目的节序与原文方法节一致。
- 作者机制文字经 `design_objective` 进入 Writer 的 `section_goal`。例如 DyG MA-S3 的 `section_goal`
  已包含"redefined Δt (timespan-dependent step size), A (stable diagonal initialization), and B/C
  (input-dependent with spectral norm constraints)"以及"Initialize A as a diagonal matrix with
  strictly negative real-part eigenvalues"。

**A1：`design_objective` 被归为 organization-only，Writer 被禁止把它写成事实句。**
- 位置：`src/code2paper/agentic/publication_method_writer.py:7609-7612`
  `organization_only_fields` 含 `heading`、`reader_question`、`research_question`、`design_objective`、`moves`。
- 位置：`src/code2paper/authoring/writer_skill.py:69`
  "Treat reader questions, design objectives, headings, method names, and rhetorical moves as
  organization context, never as repository evidence or implementation facts."
- 后果：作者机制文字到了模型面前，但契约要求它只能当组织信息。Writer 唯一可以断言的内容是
  concept card / claim。**作者主线因此结构性地只能以 caveat 形式出现**，这正是三稿"intended; pending"
  句子密集的原因，模型行为是按契约正确的。

**A2：可断言的仓库 card 主语是代码函数名，不是本节作者机制。**
- DyG MA-S1 唯一 `verified` card `CK-63093ea0b9d53055`：`method_subject` =
  "routing-weighted temporal embedding aggregation"，挂在 story 节点"first-hop interaction sequence
  encoding"下。
- DyG MA-S3 唯一 `verified` card `CK-519ade78113f21d0`：`method_subject` = "filter layer forward"，
  挂在"Robust selective reviewing"下。
- 位置：`src/code2paper/agentic/method_concept_card_compiler.py`（cluster→card 构造）。card 的
  `method_subject`/`operation` 来自行为节点，**没有任何"该节点是否实现本节作者机制"的排序或降权**。
- 后果：A1 + A2 叠加 = 目录像论文、句子像代码。这不是模型选材失误，是投影层给的可断言集合本身如此。

**A3：`reader_question` 是模板，作者的科学问题从未成为本节问题。**
- 位置：`src/code2paper/agentic/method_architect.py:377`
  `reader_question=f"How does {heading.rstrip('.').lower()} transform its inputs into outputs?"`
- 实际产物：MA-S2 的问题是"How does motivation: limitations of vanilla ssms – they ignore irregular
  timespans and are vulnerable to transform its inputs into outputs?"
- 佐证该模板会污染正文：`publication_method_writer.py:4596-4600` 已存在专门剥离该句式的正则补丁。
  即已知泄漏、只治症状。
- 另有硬编码 reader_question：`method_architect.py:1135-1150`。

**A4：proposition lane 在本批次完全没有运行，proposition 指标全部空转。**
- 三个冻结研究根与三个 replay 根均**不存在** `method_propositions_v1.json`
  （`method_proposition_bindings_v1` / `_clusters_v1` 同样缺失；三者都在
  `scripts/run_authoring_replay.py:73-80` 的 `OPTIONAL_FROZEN_ARTIFACTS` 里，缺失不报错）。
- 后果 1：`build_writer_view` 从不被调用，全部走 `build_writer_view_from_concept_cards`
  （`publication_method_writer.py:7391`）；`writer_view_projection.py:176-181`
  的 proposition 级 `audit_only` 过滤在本批为空操作。
- 后果 2：质量指标空转 —— `planned_required_propositions=0`、`planned_proposition_recall=0.0`，
  而 `rendered_proposition_recall=1.0`、`validated_proposition_recall=1.0`（0/0 记为 1.0）。
  **三项目的 proposition 召回全部是无意义的 1.0。**
- 说明（避免误读）：concept-card 分支的 `audit_only` 过滤是**活的**——
  `writer_view_projection.py:269-281` 在投影时现算
  `classify_concept_card_writing_role(card)`，`exclude_audit_only_concepts=True`
  在 `publication_method_writer.py:625/7400` 已接线。
- 但 `MethodConceptCardV1` **不持久化 `writing_role`**（38/24/39 张 card 该字段全为 `None`，
  模型定义里也没有此字段）。因此"哪些 card 被判为 audit_only 而未进 Writer"在产物中无法审计。
  这是可追溯性缺口，不是过滤失效。

### Cluster B — Formalizer 实跑零产出

**B1：2048 输出上限把 native_json_schema 响应截断。**
- trace：`formalization_section_results_v1.json → formalizer_call_traces[].call_traces[]`，
  `status=schema_failed`，`error=schema_validation_failed:ValueError:no valid JSON object or array
  found after repair attempts`（DyG MA-S1/S2/S3、LinearRAG MA-S2/S3、EBCAR MA-S2/S3/S4）。
- 预算读点在 `publication_method_writer.py:2426-2435`（文档级）与 `:2942-2952`（节级）**两处**，
  默认 2048，clamp `max(1024, min(configured_budget, 8192))`。本地模型 context 131072，
  2048 预算与上下文余量严重不成比例，**上限偏小是确定的直接成因**（本项已裁决改大，见 W6.1）。
- 表示层修复（去 fence、反斜杠转义、补容器）无法救对象中途截断。

**B2：trace 不足以在产物内定位截断。**
- 现有字段仅 `attempt / status / error / response_ref / guard_failures`。
- **缺 `finish_reason`、`prompt_tokens`、`completion_tokens`、`raw_preview`。**
  "是截断还是模型输出畸形"目前只能靠翻运行日志推断，验收无法只读判定。

**B3：author-intent lane 允许 0 包且记为成功。**
- LinearRAG MA-S1 与 EBCAR MA-S1：`status=accepted`、`proposed_package_count=0`、
  `accepted_package_count=0`。
- 两个 lane contract（`publication_method_writer.py:2975-2984`）都写的是
  "at most ONE formula package" 与 "If nothing safe can be proposed, return `{"items": []}`"
  —— **契约本身给了零产出合法出口**，模型照契约返回空列表是正确行为，不是模型失误。
- 空返回后落到 `insufficient_binding`、不伪造、进 review，方向对；但缺一个
  带 owner 的 typed disposition，验收侧无法区分"模型诚实拒答"与"契约允许免答"。

**B4：确定性 core-equation lane 在三份研究输入上全空。**
- 全部 12 个 section 的 `core_equation_ids` 均为 `[]`。
- 位置：`src/code2paper/agentic/formalization_agent.py:196-203`（`_CORE_EQUATION_DESCRIPTORS`）、
  `:209-214`（`_MECHANISM_PREDICATE_TERMS`）、`:227` (`_equation_is_core`)。
- 移除裸算术算符（正确方向）之后，冻结研究里的 equation 事实**既无 mechanism 描述符也无 mechanism 谓词**。
  这是研究侧 equation 证据贫乏，不是 gate 太严。上一批 12/5/31 个包全是 `$x+y$`/`$x*y$` 垃圾，
  正是本轮要消除的对象。

**B5：`equation_coverage=0.0` 直接压死 utility gate**，与 D2 形成不可满足闭环。

**B6（漏写补强）：低输出上限是系统性的，不只 Formalizer；且本次只有 Formalizer 被截断。**
- 角色默认预算（`llm/role_config.py:155-228`）：`code_intake` 2048、`authoring_planner` 2048、
  `research_supervisor` 3072、`method_proposition_architect` 3072、`local_rewrite` 3072、
  `semantic_verifier` 1024、`method_writer` 8192/extended 12288。本地 context 131072。
- `research_supervisor` 的代码注释（`:178-182`）自述曾因 1536 截断被迫提到 3072 ——
  **同类问题已在别的角色上发生过一次，是被逐个碰壁才发现的，不是一次性核对出来的。**
- 本批实测 `finish_reason`：Writer 16/13/8 次与 Rewrite 28/31/25 次**全部 `structured_complete`**
  （8192/3072 未截断）；**唯独 Formalizer 在 2048 上 `schema_failed` 截断**。
- 结论：上限偏低是确定性成因，但当前**只在 Formalizer 上显形**。其余低预算角色（planner/intake/
  proposition_architect/verifier）只是"还没碰到长输出"，不代表安全。W6 修正之后，
  应在 W8 增加一次全角色预算 vs 上下文的核对（见 W8 改动 5）。

### Cluster C — 标题权限在三个守卫之间自相矛盾（可复现的正文残句来源）

**C1：Architect 产出中途截断的标题。**
- 位置：`method_architect.py:686` 调 `_truncate_heading(heading, limit=120)`；实现在 `:752-761`。
- 实际 plan 标题："Motivation: limitations of vanilla SSMs – they ignore irregular timespans and are
  vulnerable to"、"Redesign: timespan-informed Δt and A for temporally aware forgetting, and
  redefined B/C with"、"Offline Tri‑Graph construction (entities, sentences, passages,
  contain/message adjacency"。**以介词/连词/半个括号结尾。**

**C2：Rewrite 被授权缩短标题，但把 dangling tail 留在正文开头。**
- 授权位置：`src/code2paper/agentic/rewrite_agent.py:270-298`（`heading_replacement_is_coherent`
  允许 coherent 的缩短/补全）；配套 issue 构造在
  `publication_method_writer.py:4759-4811`（`truncated-heading` / `fused-heading-suffix`）。
- 实际结果（rendered ≠ plan）：
  - DyG MA-S3：rendered `## Redesign: timespan-informed Δt`，正文首句
    `A for temporally aware forgetting, and redefined B/C with (self.time_mamba and dts != None)The
    filter layer forward pass…` —— **被砍掉的标题尾巴出现在正文开头。**
  - LinearRAG MA-S1：rendered `## Offline Tri-Graph Construction`，正文首句
    `Tri‑Graph construction (entities, sentences, passages, contain/message adjacency)Offline
    tri-graph construction constructs…` —— 同一模式。
  - DyG MA-S2 / MA-S4、LinearRAG MA-S2 / MA-S3 同为 rendered 短于 plan。
- 即：标题修复只处理了标题行，**尾巴迁移进正文没有任何守卫**。

**C3：Editor 要求与 plan 标题精确一致，于是必然否决 Rewrite 的合法修复。**
- 位置：`publication_method_writer.py:3580-3583`
  `if expected_heading and not _has_exact_section_heading(proposed_text, expected_heading): rejected.append(f"{section_id}:editor_removed_or_changed_heading")`
- `expected_heading` 取自 plan（即那个截断标题）。Rewrite 已合法缩短之后，Editor 无论如何改都不匹配。
- 实测 `call_failures`：DyG `MA-S3:editor_removed_or_changed_heading`、
  LinearRAG `MA-S1:editor_removed_or_changed_heading`。
- **Rewrite 与 Editor 对"标题是什么"的权威定义不一致，这是纯代码级矛盾。**

**C4：文档级 Editor 事务以空理由回滚全部已接受补丁。**
- 产物：`publication_editor_transitions_v1.json` → DyG/LinearRAG `decision=reject`、`reasons=[]`。
- `publication_editor_result_v1.json` → `blocked_reason="editor_candidate_rejected:"`（冒号后为空）。
- 位置：`publication_method_writer.py:1575-1615`。分节阶段已经 `selected` 了补丁
  （DyG 3 个、LinearRAG 1 个），随后文档级 `_editor_candidate_decision`（`:3386`）返回
  `reject` 且 `reasons=[]`，走 `:1602` 分支把 **全部** section 回滚到 incumbent。
- `:3700-3709` 的注释表明曾针对"空理由拒绝"打过补丁，但只覆盖 `selected` 为空的 no-op 路径；
  `selected` 非空时的聚合拒绝仍可返回空理由。
- 后果：DyG 与 LinearRAG 的 Editor 实际等于完全失效，且产物里查不出原因。EBCAR（`accept`）
  是三项目里唯一真正跑过 Editor 的。

### Cluster D — move 契约与可满足性脱钩

**D1：move 集合按 unit × move 展开，单个候选 unit 拖入 6–7 个 required move。**
- DyG MA-S1 有 10 个 move，MA-S2 有 11 个；其中 `problem_or_local_context`、`design_objective`、
  `formal_objects_and_notation`、`equation_or_derivation`、`algorithm_or_data_flow`、
  `inference_and_output` **全部只绑到 `MA-S1:unit-2` 一个 unit**，且多数 `required=True`。
- 位置：`method_architect.py:335-372`（`SectionArgumentMoveV1` 构造，`required=any(...)` 在 `:356`）；
  另一处构造在 `:2113-2134`（`required=_required_move(...)`），两处口径需一并处理。

**D2：`equation_or_derivation` 恒为 required，而 Formalizer 交付 0 包 → 结构性不可满足。**
- 与 B5 形成闭环：无论模型多好，这一项都必失败。

**D3：`required_argument_move_missing` 29/22/28，是 `publication_ready=false` 的首要贡献。**
- 判定位置：`publication_quality.py:905-922`，move 由 `_move_witness_span`（`:1586`）按句级 witness 证明。
- 另有 `required_move_content_missing`（DyG 3、LinearRAG 1）："declared but no authored span realizes
  its bound content"。

**D4：Writer 只申报 `limitations_or_mismatch`。**
- 四个 DyG section 的 `completed_rhetorical_moves` 均为 `['limitations_or_mismatch']`，
  且 `used_argument_unit_ids`、`rendered_proposition_ids`、`used_claim_ids` 全空。
- 契约上 `completed_rhetorical_moves` 是可省略的辅助元数据
  （`llm/response_schemas.py:26-49`），但质量门按 witness span 独立判定，
  两套口径并存导致产物无法解释"为什么这个 move 没算过"。

**D5：content_role 轴整条空转，三项目 `equation/overview/transformation/representation/output` 全 `missing`。**
- 产物（`quality_report.utility.content_role_status`）：三项目都是
  `overview/representation/transformation/branch/equation/output = missing`，仅 `objective = covered`。
- 位置：`publication_quality.py:963-1008`。role 由 `unit.equation_ids`→equation、
  `claim_ids`→transformation/overview、config→branch/representation 推导；
  `content_covered` 要求该 role 的内容**已被渲染**（`:990-1008`）。
- 这是 `utility_gate_passed=false` 的直接组成（`:1337` 要求 `all(status != "missing")`），
  与 D3 的 `required_argument_move_missing`、B5 的 `equation_coverage=0.0` 共同压死 utility gate。
- **含义**：这不是单一 move 缺失，而是"方程/总览/变换/输出"这四类内容角色在三个项目上
  整体未被渲染。它把 B（公式）、D（move）的症状汇合到一个 gate 上，单点修任何一处都不够。

### Cluster E — 审计事实与代码数字仍进正文（audit 分类没盖住真正的可断言面）

**E1：`audit_only` 分类只作用于 concept card，不作用于 Writer 真正断言的 claim 投影面。**

这是本轮第二个结构性发现，比"某张 card 分错类"严重得多。

- 现象：EBCAR InfoNCE 节正文写着 "During loss computation, the per-sample loss tensor satisfies
  `loss_i.shape[0] == 0` under the intended batch configuration."
- 溯源：该内容**不在** EBCAR 的任何 concept card 里（39 张 card 全文无 `loss_i`）。它来自
  `authoring_projection_v1.json`：
  - `projected_claims[21].claim_text` = `EBCarRerankerHybridAttention.forward branches on loss_i.shape[0] == 0`
  - **`repository_verified_facts[21]`** 同一条
  - `atomic_claims_v3.json` 对应 claim `status=supported`、`claim_kind=implementation_behavior`
- 即：一条纯防御分支同时是 **repository_verified 的可断言事实** 和 **coverage 分母的一部分**。
  Writer 写它是按契约正确的，不写反而会掉 `supported_unit_recall`。
- 代码层事实：`audit_only` 判定只出现在 concept-card 投影
  （`writer_view_projection.py:269-281`）与公式选择
  （`formalization_agent.py:216-219` `_AUDIT_DESCRIPTOR_TERMS`）。
  `AuthoringInputProjection.projected_claims` / `repository_verified_facts` 这条通道
  **没有任何 audit 分类**。
- 这也同时解释 E2 与 E3：维度/索引数字与 `case_study` 分支走的是同一条无分类通道。

**E1-b：fact 级 audit 分类器已实现、已单测，但在产品路径上是死代码。**
- `publication_relevance.py:81 classify_fact_writing_role(fact)` 已存在，
  且 `tests/test_agentic_method_propositions.py:1050-1053` 已断言
  "防御性 fact → `audit_only`"、"循环 fact → `audit_only`"。
- 但它在 `src/` 下**只有一个生产调用点**：`method_proposition_compiler.py:1017`
  —— 即 A4 中那个**在三次实跑里根本没产出过的 proposition 编译器**。
- 结论：**这是 A4 与 E1 的交汇点。** 逻辑写对了、测试也过了，但唯一的消费者从未运行，
  所以在实际产品路径（concept card + claim 投影）上防御性事实从未被分类。
  这解释了为什么"静态套件 2661 passed"与"正文里仍有 `loss_i.shape[0] == 0`"可以同时成立。
- 因此 W5 主要是**接线**，不是新写判定逻辑。

**E2：DyG 4 条 unsupported 全为 `numeric_token_not_in_direct_evidence`（FAC19/21/23/25）。**
- 来源是把代码维度/索引数字当方法数字写出："along dimension 1"、"along dimension 2"、
  "conditional branching on index zero"、"bounded by the numeric constraint 1"。
- 应在相关性层把维度/索引数字判为 audit-only，而不是在 validator 层放宽匹配。

**E3：code-trace 散文。**
- DyG MA-S2 把 `` `case_study` `` 与 `` `i == 0 and case_study` `` 逐句粘贴（2 条
  `code_trace_prose_not_method_language`）；LinearRAG 1 条；EBCAR 2 条。
- Rewrite 已尝试并耗尽预算：`publication_rewrite_transitions_v1.json` →
  `rewrite:MA-S2:method_language_style:attempt_budget_exhausted` 等，DyG 12 条 failures。
- EBCAR 另有句中断裂："and `dim=2` before returning the normalized encoding, …"。

### Cluster F — 回调与验证的可观测性

**F1：9 个 continuation 全部 `max_turns_reached` / `final_status=incomplete`（8 tool-turns 打满）。**
- 字段在 `research_tool_data/writing_callbacks/<request_id>/research_continuation_*.json`
  的 `termination` 对象：`{"turns_executed": 8, "termination_reason": "max_turns_reached",
  "final_status": "incomplete"}`。注意聚合文件 `writing_callback_fulfillment_trace_v1.json`
  顶层是 `research_graph_continuations`（round → request_ids → continuations），不含 termination，
  termination 要进 chain 文件取。

**F2：部分 continuation `observations=0` 却产出 facts（DyG 3/4、EBCAR 1/3，LinearRAG 0/2）。**
- 实测：DyG MA-S1/MA-S2/MA-S4 `obs=0, facts=8`（MA-S3 `obs=2, facts=6`）；EBCAR 1 个 continuation
  `obs=0`；LinearRAG 两个 continuation 均有 observations。
- 链路 JSON 自称"observations → packets → facts"，但 `observations` 可以为空而 `facts` 非空 ——
  要么 observation 未持久化，要么 facts 并非来自本次 observation。两种情况都需要在产物里区分。
  （修正：不是全部 9 个，也不是固定 8–10 条；以实测为准。）

**F3：所有 callback 都是同一类型 `limitations_or_mismatch`。**
- 12 个请求全是 `request:MA-S*:limitations_or_mismatch`。Writer 从不为
  `equation_or_derivation`、`algorithm_or_data_flow`、`mechanism_overview` 发起补证，
  而这些恰是缺失最多的 move。

**F4：无 per-callback 增益度量。** 补证前后的 coverage / move / 公式差值没有记录，
  "callback 打通"与"callback 有用"当前无法分辨。

**F5：`concept_judgment: {}` 仍然 resume。** DyG MA-S4 的 concept 判定为空却照常恢复该节。

**F6：`semantic_verifier_calls: 0`（三项目）。** 语义校验器从未运行，全部判定是词法的。
  §19.5.4 要求"reader-facing condition meaning 是主要匹配面"，当前实测不成立。

### Cluster G — Verified 投影与指标卫生

**G1：EBCAR Verified 的 `## Training objective: InfoNCE…` 与 `## Inference procedure.` 只有标题+空白。**
  §14.3 明确要求拒绝空节/仅标题节；Verified 投影当前会产出它们。

**G2：被删句留下成串空格。** 三个 Verified 文件都有 `"       "` 连续空白（句子被过滤后未收敛空白）。

**G3：指标不一致/无意义。**
- `configuration_coverage`：DyG 1.0，LinearRAG 0.0，EBCAR 0.0（分母为 0 与真实覆盖混淆）。
- `reproducibility_detail_coverage`：三项目 0.0。
- `planned_proposition_recall=0.0` 与 `rendered_proposition_recall=1.0` 并存（见 A4）。

---

## 3. 根因收敛

七组缺陷收敛为 5 个真正的根因：

| 根因 | 表现 cluster | 性质 |
|---|---|---|
| **R-I 作者意图无可断言通道；可断言集合由代码函数名主导** | A1, A2, A3 | 投影层设计 |
| **R-II audit 分类器在产品路径上未接线；proposition lane 缺席使其成为死代码** | A4, E1, E1-b, E2, E3 | 接线缺口 |
| **R-III Formalizer 预算/契约/研究侧证据三处同时不足；低上限是系统性的** | B1–B6, D2 | 预算 + 契约 + 研究输入 |
| **R-IV 标题与 Editor 权限在守卫之间互相否决，且拒绝无诊断** | C1–C4 | 守卫一致性 |
| **R-V 义务与可满足性、闭环与增益都缺少绑定** | D1–D5, F1–F6, G1–G3 | 契约与可观测性 |

两点值得单独强调：

- **R-II 是"测试全绿但产物有病"的直接解释。** `classify_fact_writing_role` 逻辑正确且有单测，
  唯一生产消费者是从未运行的 proposition 编译器。这类"实现 + 单测 + 无生产调用"的缺口
  不会被任何静态套件发现，**只能靠实跑产物溯源**。建议后续把"每个新增判定函数必须有产品路径
  调用点"作为实施与验收的固定检查项。
- **R-IV 与 R-V 中的多数项是确定性缺陷**，不依赖模型采样，可用静态测试锁死，应当优先做。

---

## 4. 下一步代码级优化方案

排序原则：先修确定性矛盾与接线缺口（W1、W2、W5、W3），再修投影语义（W4），再修 Formalizer（W6），
最后补闭环与产物卫生（W7、W8）。每个工作包给出目标文件、改动要点、验收测试。
编号按主题固定，执行顺序见 §5。

### W1（P0，确定性）标题权威单一化

**问题**：C1 + C2 + C3。

**目标文件**
- `src/code2paper/agentic/method_architect.py`
- `src/code2paper/agentic/publication_method_writer.py`
- `src/code2paper/agentic/rewrite_agent.py`

**改动**
1. `_truncate_heading`（`method_architect.py:752`）不得在介词/连词/未闭合括号处结束。
   在 `limit` 内回退到最后一个完整子句边界；若回退后不足两个内容词，改用 story 节点的
   `intended_role` + 主名词短语生成短标题。**Architect 不再产出中途截断的标题**，
   这样 C2/C3 的整条修复链就不必存在。
2. 引入单一 `authorized_heading`：Rewrite 一旦合法改写标题，必须把结果写回 section 上下文，
   Editor 的 `_has_exact_section_heading`（`publication_method_writer.py:3580`）改为比对
   `authorized_heading`（Rewrite 结果优先，回落 plan 标题），而不是恒比 plan 标题。
3. 标题缩短时的 dangling tail **必须丢弃或由 Rewrite 重写为正文句**，不允许原样迁移到正文开头。
   在 section 接受路径加确定性检查：正文首句若以 plan 标题的后缀开头（归一化后前缀匹配），
   判为 `heading_tail_leaked_into_body`，路由回 Rewrite。

**验收测试**（扩展 `tests/test_agentic_publication_method_writer.py`、
`tests/test_agentic_writer_paper_language_quality.py`）
- 120 字符边界上的长 story 标题产出完整子句标题，不以 `with`/`to`/`and`/`(` 结尾；
- Rewrite 合法缩短标题后，Editor 同节补丁**不再**产生 `editor_removed_or_changed_heading`；
- 正文首句携带 plan 标题尾巴时被判 `heading_tail_leaked_into_body` 并进入 Rewrite issue；
- 仍然禁止把标题改成任意名称（原守卫不得放宽）。

### W2（P0，确定性）Editor 文档级事务必须有理由且不得整篇回滚已接受补丁

**问题**：C4。

**目标文件**：`src/code2paper/agentic/publication_method_writer.py:1575-1615`、`:3386`

**改动**
1. `_editor_candidate_decision` 返回 `reject` 时 `reasons` 不得为空。无法归因时返回显式
   `document_level_no_gain_without_reason` 并把 incumbent/candidate 快照差异（哪一维回归）写入 trace。
2. 文档级拒绝不再无条件回滚全部 section。已在分节阶段通过 Pareto/no-loss 检查的补丁保留；
   仅回滚参与回归的 section。若确需整篇回滚，必须给出逐 section 的回归原因。
3. `publication_editor_transitions_v1.json` 增加 `regressed_dimensions`（claims/equations/
   configurations/moves/duplicate/editable/coherent 逐维 before→after）。

**验收测试**（扩展 `tests/test_agentic_publication_method_writer.py`）
- 构造一个 section 回归 + 一个 section 改善的 Editor 候选：改善的 section 被保留，
  回归的被回滚，`reasons` 非空且指名回归维度；
- 文档级 `reject` 且 `reasons==[]` 的情况在测试中不可达（断言）。

### W3（P0，确定性）move 必需性与锚点可满足性绑定

**问题**：D1–D4。**注意：这不是降低门禁，而是把"缺锚点"从静默计数改为显式义务。**

**目标文件**
- `src/code2paper/agentic/method_architect.py:335-372` 与 `:2113-2134`（两处 move 构造）
- `src/code2paper/agentic/publication_quality.py:905-922`、`:1586`（`_move_witness_span`）
- `src/code2paper/llm/section_writer.py:849-866`（move 契约 schema）

**改动**
1. move 的 `required` 推导必须检查该 move 在本 section 是否存在授权锚点：
   - `equation_or_derivation` 仅在本节存在**已接受**公式包或 code-verified equation 时 required；
   - `configuration_and_branches` 仅在存在 material configuration 时 required；
   - 其余 move 保持现有规则。
2. 无锚点的 move 不再计入 `required_argument_move_missing`，而是产出
   **typed `move_unanchored` 义务**（带 owner：Formalizer / Research callback / 作者确认），
   进 `author_review_candidates.json` 且计入 `publication_ready=false` 的原因。
   **总义务数不减少，只是从"未证明"改为"有归属的未闭合"。**
3. 消除 unit × move 展开导致的重复：同一 move 绑定多个 unit 时只产生一个 section 级义务。
4. Writer 侧 `completed_rhetorical_moves` 与质量门 witness 判定统一到一个函数，
   两者不一致时在产物里记录 `move_declaration_witness_mismatch`。

**验收测试**（扩展 `tests/test_agentic_method_architect_product_readiness.py`、
`tests/test_agentic_publication_method_writer.py`）
- 无公式证据的 section 不产生 required `equation_or_derivation`，而产生 `move_unanchored`
  且 owner=Formalizer；
- 有公式包时该 move 恢复 required，未写则仍为 `required_argument_move_missing`；
- 同一 move 绑 5 个 unit 只产生 1 条义务；
- 义务总数在改动前后不减少（防止被当成放宽门禁）。

### W4（P0，语义）作者意图的可断言 caveated 通道

**问题**：A1 + A2 + A3。这是"正文像论文"的核心开关。

**目标文件**
- `src/code2paper/agentic/writer_view_projection.py`
- `src/code2paper/agentic/publication_method_writer.py:7391-7412`、`:7609-7612`
- `src/code2paper/authoring/writer_skill.py`
- `src/code2paper/agentic/method_architect.py:377`

**改动**
1. **新增 story 派生的 caveated 断言项**：把本 section 绑定的 story 节点 `author_statement`
   投影为 `WriterCaveatedPropositionV1`/等价 caveated 项（lane=`author_intent_unverified`，
   `requires_caveat=True`），而不是仅作为 `section_goal` 字符串。
   - 它可以成为事实句的主语与谓语，但**必须带可见 caveat 且不得进入 Verified**。
   - `organization_only_fields` 保留 `heading`/`reader_question`/`moves`；
     `design_objective` 从"组织信息"改为"caveated 内容来源"，并同步更新 `writer_skill.py:69`。
2. **段落优先级契约**：section 的第一段必须回答本节作者机制（story 断言 + 可用的
   code-verified 支撑），仓库实现关系写在后续段落。当前契约只说"先答 section_purpose"，
   但 purpose 是模板句，等于没有约束。
3. **`reader_question` 改为 story 派生**：`method_architect.py:377` 用 story 节点的
   `intended_role` + `author_statement` 生成真实科学问题（例如"为什么 vanilla SSM 无法处理
   不规则时间间隔，DyG-Mamba 如何重定义 Δt 与 A"），删除 transform-inputs-into-outputs 模板。
   相应地移除 `publication_method_writer.py:4596-4600` 的症状级剥离补丁（模板不存在则无需剥离）。
4. **仓库 card 的节内相关性排序**：`method_concept_card_compiler.py` 为 card 增加
   `realizes_story_node`（该行为节点是否精确实现本节 story 机制）。
   不实现本节机制的仓库 card 降级为 implementation-binding 素材（只能作为从句出现），
   不得成为 section 主语。**降级依据必须是 exact span/relation 绑定，不得用文件名或 obligation 推断。**

**验收测试**
- 同一 evidence + 不同 author story → 段落组织不同（§19.7.5 已有要求，现需真正可测）；
- 一个 section 的 story 断言进入 Candidate 首段且带 caveat，同一句被 Verified 排除；
- `method_subject` 为 "filter layer forward" 类实现操作的 card 不再成为 section 主语，
  但仍可作为实现绑定从句出现；
- Writer payload 中不含内部 ID；
- 禁止把 story 断言写成无 caveat 的肯定实现句（fail-closed 回归测试）。

### W5（P0，语义）audit 分类下沉到 claim 投影面 + proposition lane 归位

**问题**：E1（audit 分类没盖住真正的可断言面）+ E2 + E3 + A4。

**目标文件**
- `src/code2paper/agentic/authoring_projection.py:249/309/531/979`
  （构造 `projected_claims` / `repository_verified_facts` 的位置）
- `src/code2paper/agentic/publication_relevance.py:81`（复用已有 `classify_fact_writing_role`）
- `src/code2paper/agentic/method_product_models.py`（`MethodConceptCardV1` 增 `writing_role`）
- `scripts/run_authoring_replay.py:73-80`、`src/code2paper/agentic/publication_quality.py:1345-1353`

**改动**
1. **把已有的 `classify_fact_writing_role` 接到 claim 投影面（本工作包的核心，是接线不是新逻辑）**：
   `projected_claims` / `repository_verified_facts` 的每一条必须带
   `writing_role ∈ {method_positive, method_conditional, audit_only}`。
   现有唯一生产调用点 `method_proposition_compiler.py:1017` 在实跑中不可达，
   必须让分类在**产品路径**上生效。
   判为 `audit_only` 的条目：
   - 仍留在 evidence / validation sidecar（**不删证据**）；
   - 不进 Writer 可断言面；
   - **同时从 coverage 分母移除**（否则 Writer 不写就掉召回，等于强迫它写）。
   分类必须由 exact 关系/谓词判定（防御分支、空张量检查、shape/index 断言、缓存命中、
   `case_study` 类调试开关），不得用文件名、obligation 或项目名推断。
2. `MethodConceptCardV1` 持久化 `writing_role`，使"哪些 card 被 audit 过滤"可只读审计（A4 尾）。
3. **proposition lane 归位**（需裁决，见 §6）：要么真正产出 `method_propositions_v1`，
   要么正式弃用 proposition 分支并把角色统一到 card + claim 两条通道。
   **现状（两套并存、只跑一套）必须终止**，否则 §19 Q1 的验收证据与实跑长期脱节。
4. `planned_proposition_recall` 等指标在分母为 0 时输出 `null` + `not_applicable`，禁止 0/0→1.0。

**验收测试**
- `branches on X.shape[0] == 0` 类 claim 判为 `audit_only`：不进 Writer payload、
  不进 coverage 分母、仍在 evidence sidecar 中可查；
- 维度/索引数字不再作为方法数字进入正文（直接消除 E2 的 4 条 `numeric_token_not_in_direct_evidence`）；
- `case_study` 类调试分支不再作为可断言事实（配合 W1/W3 消除 E3）；
- 真实机制 claim（含 spectral norm 约束、PPR 传播、hybrid attention 掩码）**不得**被误判 audit_only
  （反向负例，防止用 audit 分类偷偷删内容）；
- card 的 `writing_role` 出现在产物中且与投影行为一致；
- proposition 缺失时指标为 `null`/`not_applicable`，不是 1.0。

### W6（P0，Formalizer）输出上限改大（已定案）+ 契约与研究侧证据

**问题**：B1–B5。**上限一项已裁决改大（见改动 1）**，其余两项（契约空包、研究侧证据）仍需处理。

**目标文件**（已核实：budget 读点在 `:2426-2435` 与 `:2942-2952` **两处**，prompt/schema 调用在 `:3014-3028`）
- `src/code2paper/agentic/publication_method_writer.py:2426-2435` 与 `:2942-2952`（两处 budget clamp）
- `src/code2paper/agentic/publication_method_writer.py:2975-3028`（lane contract + prompt）
- `src/code2paper/llm/response_schemas.py`（section formula package schema）
- `src/code2paper/agentic/formalization_agent.py:196-227`
- `src/code2paper/agentic/equation_claims.py`

**改动**
1. **输出上限改大（已定案）**：把 Formalizer 的默认预算从 2048 提到 **6144**，
   clamp 上限从 8192 提到 **16384**，两处 clamp 同步（`max(1024, min(configured_budget, 16384))`）。
   `CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_PUBLICATION_FORMALIZER` 环境变量保留可调。
   本地模型 context 131072，6144 默认预算远低于上下文余量，不会挤占 prompt。
   **schema 精简仍保留**，与预算并行做（单次只返回 1 个公式包、`prose_explanation` 限长），
   因为单纯加预算只会把截断点后移，不消除"一次返回多包 + 长散文"的结构性超长。
2. **trace 增加截断可判定性**：`formalizer_call_traces[].call_traces[]` 增加
   `finish_reason`、`completion_tokens`、`max_output_tokens`、`raw_preview`（截断前 N 字符）。
   `status` 细分 `schema_failed_truncated` 与 `schema_failed_malformed`。
   **这是上限改大后的回归判据**：预算从 2048 提到 6144 后，若仍出现 `schema_failed_truncated`
   （`finish_reason=length`），说明 schema 本身超出合理单次预算，必须回到 schema 精简而不是继续加预算。
   没有这三个字段，这个判断只能翻日志。
3. **author-intent lane 契约**：lane 被激活且本节存在 formula obligation 时，
   零包返回不再记为 `accepted`，改为 `declined_empty` 并强制产出 typed review item
   （owner=作者/形式化），进 `author_review_candidates.json`。
4. **研究侧 equation 证据增强（本轮真正的瓶颈）**：`equation_claims.py` 在编译 equation claim 时
   必须携带 mechanism 描述符/谓词来源（来自行为节点语义与关系，而非表达式本身）。
   当前 `core_equation_ids` 全空说明研究阶段没有产出任何"科学机制级"equation 事实。
   **不得通过把算术算符加回 `_CORE_EQUATION_DESCRIPTORS` 来制造覆盖率。**

**验收测试**（扩展 `tests/test_agentic_formalization_guards.py`）
- mock caller 返回被截断 JSON → `status=schema_failed_truncated` 且 trace 含 `finish_reason=length`；
- mock caller 返回空包 → `declined_empty` + review item，且不记为 accepted；
- 裸 `x+y` / shape / index 表达式仍被拒为 core formula（现有负例保持）；
- 携带 mechanism 谓词的 equation 事实产出非空 LaTeX + 符号定义 + prose explanation；
- author-intent 公式进 Candidate 带 caveat、不进 Verified；
- paper/code mismatch 两侧都保留。

### W7（P1，闭环）callback 的提问面与增益度量

**问题**：F1–F5。

**目标文件**
- `src/code2paper/agentic/writing_callback_fulfillment.py`
- `src/code2paper/agentic/writer_research_router.py`
- `src/code2paper/llm/section_writer.py`（callback 契约）

**改动**
1. Writer 必须能为 `equation_or_derivation`、`algorithm_or_data_flow`、`mechanism_overview`
   发起 callback，而不是只发 `limitations_or_mismatch`。
   与 W3 的 `move_unanchored` 义务打通：无锚点 move 直接生成对应 owner 的 callback/review。
2. continuation 记录 **per-request 增益**：补证前后的 `bound_claims`、`rendered_moves`、
   `formula_packages`、`supported_unit_recall` 差值。连续无增益即停止（§19.8.1 已要求，需落到产物）。
3. `observations=0` 且 `facts>0` 必须显式标注来源（复用既有 behavior graph 而非本次 observation），
   或修复 observation 持久化。二者都不做等于链路自述不可信。
4. `concept_judgment` 为空时不得声明该 section 的 concept 环节完成；记 `concept_judgment_absent`。

**验收测试**（扩展 `tests/test_agentic_research_graph_callback_continuation.py`）
- 无锚点 `equation_or_derivation` 触发 Formalizer owner 的 callback/review，不触发仓库检索；
- 连续两轮无增益 → 停止且保留 incumbent；
- `observations=0` 时产物带显式来源标注；
- `concept_judgment` 为空时不算完成。

### W8（P2，卫生）Verified 投影与指标

**问题**：G1–G3、F6。

**目标文件**
- `src/code2paper/agentic/text_evidence_validator.py:477-520`
- `src/code2paper/agentic/publication_quality.py`

**改动**
1. Verified 投影中，某节全部句子被过滤后**不输出该节标题**（或输出显式
   `section_withheld_no_verified_sentence` 标记），不再产出"标题 + 空白"节。
2. 句子过滤后收敛空白（表示层修复，允许）。
3. `configuration_coverage` / `numeric_coverage` 等分母为 0 时输出 `null` + `not_applicable`，
   不输出 0.0 或 1.0。
4. `semantic_verifier_calls=0` 时，验证报告必须显式声明"本次判定为词法级"
   （`verification_mode=lexical_only`），避免把词法通过读成语义通过。
5. **全角色输出预算 vs 上下文核对（承接 B6）**：对 `role_config.py:155-228` 每个
   结构化输出角色，记录默认预算、是否有截断史（如 `research_supervisor`）、以及
   `finish_reason != structured_complete` 的运行计数。产出一张预算核对表，凡
   "默认预算 << 上下文余量 且输出为结构化 JSON" 的角色统一上调，不再等逐个碰壁。
   本批只有 Formalizer 显形，不代表其余角色安全。

**验收测试**
- 全过滤 section 不产生仅标题节；
- 分母为 0 的指标为 `null`；
- 语义校验未运行时报告标注 `lexical_only`；
- 预算核对表覆盖 `role_config.py` 全部角色，且每个角色有 `finish_reason` 观测值。

---

## 5. 执行顺序与验证

依赖顺序（串行，同一 worktree）：

```text
W1 标题权威   ─┐
W2 Editor 事务 ┤
W5 audit 接线  ┼─> W3 move 锚点绑定 ──> W4 作者意图可断言通道 ──> W6 Formalizer
              ┘                                                      │
                                                                      v
                                                         W7 callback 提问面/增益
                                                                      │
                                                                      v
                                                               W8 产物卫生
```

- W1 / W2 / W5 / W3 是确定性缺陷，**先做，可全部用静态测试锁死，不需要 live**。
- W5 提前到 W3 之前：audit 分类会改变 coverage 分母，move 锚点判定必须建立在清洗后的可断言面上，
  否则 W3 会把审计事实当成合法锚点。
- W4 决定内容质量上限；W6 依赖 W3 的锚点定义与 W4 的节内相关性。
- 每个包结束跑聚焦回归，全部完成后**只跑一次**全量静态套件与**一次**三项目冻结批次。
- 不为等待幸运采样重跑不变代码与输入（`.agent/plan.md` §19.11）。

聚焦命令建议：

```text
W1/W2  python -m pytest -q tests/test_agentic_publication_method_writer.py tests/test_agentic_writer_paper_language_quality.py
W5     python -m pytest -q tests/test_agentic_authoring_projection.py tests/test_agentic_method_propositions.py tests/test_agentic_method_concept_cards.py
W3     python -m pytest -q tests/test_agentic_method_architect_product_readiness.py tests/test_agentic_publication_method_writer.py
W4     python -m pytest -q tests/test_agentic_method_concept_cards.py tests/test_agentic_writer_paper_language_quality.py tests/test_llm_section_writer.py
W6     python -m pytest -q tests/test_agentic_formalization_guards.py tests/test_llm_structured_response_recovery.py
W7     python -m pytest -q tests/test_agentic_research_graph_callback_continuation.py
W8     python -m pytest -q tests/test_agentic_final_text_trust.py tests/test_agentic_final_text_trust_v3.py
最终   python -m compileall -q src tests scripts && git diff --check && python -m pytest -q
```

下一批实测的**最低内容目标**（用于判断是否真的前进，不作为放宽依据）：
1. 三项目至少各有 1 个 accepted 机制公式包，正文渲染 LaTeX 并解释符号；或每个 formula-obligated
   section 有带 owner 的 typed disposition（不允许再出现"全 `insufficient_binding` + 无 owner"）。
2. 无正文残句、无标题尾巴泄漏、无 `case_study` 式逐句粘贴。
3. Editor 决策有非空理由；至少一个项目的 Editor 补丁被真正采纳。
4. 每个 section 首段回答本节作者机制。
5. `move_unanchored` 义务有明确 owner，且义务总数不低于本批的 29/22/28。
6. 正文中不再出现防御性分支断言（`shape[0] == 0`、空张量检查、调试开关），
   且这些事实仍可在 evidence sidecar 中查到（不是被删，而是被正确归类）。
7. 每个新增或已有判定函数在产品路径上有可达调用点（针对 R-II 类缺口的固定检查）。

---

## 6. 需要裁决的开放问题

以下涉及契约或架构选择，除第 1 项已定案外，**不应由实施方单方决定**：

1. **Formalizer 输出上限 —— 已定案（用户裁决）**：默认预算 2048 → 6144，clamp 上限 8192 → 16384，
   两处 clamp 同步。schema 精简并行保留。裁决理由：本地模型 context 131072，2048 与上下文余量
   严重不成比例，且截断是 schema_failed 的直接成因。**回归判据**是 W6.2 的 trace 字段 ——
   若 6144 下仍 `finish_reason=length`，说明问题在 schema 而非预算，回到精简而非继续加。
2. **author-intent lane 是否必须产出 ≥1 包**：强制至少一个 caveated 公式候选，
   还是接受 `declined_empty` + review item 的诚实处置？
3. **proposition lane 的归属**：真正产出 `method_propositions_v1`，还是把写作角色下移到
   concept card 并正式弃用 proposition 分支？当前两套并存、只跑一套，
   使 §19 Q1 的验收证据与实跑长期脱节。
4. **move 必需性改为锚点派生**：这会改变 `required_argument_move_missing` 的计数口径。
   本方案主张"义务不减、归属更明确"（W3.2 强制义务总数不下降），
   但口径变化必须由 Codex 明确批准，否则可能被读作放宽门禁。

---

## 7. 明确的非目标

- 不新增 hash、manifest、digest 或台账字段来替代文字质量改善。
- 不通过把算术算符加回 core descriptors 来提升 `equation_coverage`。
- 不通过删减 Candidate 句子或放宽 Verified 证据要求来消除 unsupported。
- 不在通用生产逻辑中写入 DyG/LinearRAG/EBCAR 的路径、符号、句子或已知答案。
- 不因本轮改动声明 Master-Agent 里程碑、rollout、默认切换或 release freeze。
- 不重跑不变代码与输入以获取更好样本。
