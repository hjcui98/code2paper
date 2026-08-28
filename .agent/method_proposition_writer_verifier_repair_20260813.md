# Method Proposition、Writer 与 Verifier 纵向修复计划

- 日期：2026-08-13
- 状态：`READY_FOR_IMPLEMENTATION`
- 性质：针对四项目 publication replay 的根因修复文档，不替代总体设计
- 适用基线：当前未提交 Post-R8 工作树，以及 2026-08-12/13 的四项目 frozen publication replay
- 诊断证据：
  - `/tmp/code2paper-rap-publication-concise-replay-20260812-c`
  - `/tmp/code2paper-ebcar-publication-concise-replay-20260812-c`
  - `/tmp/code2paper-linearrag-publication-concise-replay-20260812-c`
  - `/tmp/code2paper-dygmamba-publication-concise-replay-20260812-c`

本文档服从以下上位设计：

1. `docs/agentic_robust_langgraph_research_writing_design_2026-07-19.md`
2. `docs/publication_ready_method_writer_design_2026-07-31.md`
3. `docs/post_r8_research_agent_execution_plan_2026-07-31.md`
4. `docs/project_status_and_gap_report_2026-07-31.md`

本文档不修改上述设计的信任方向。它解决的是已经定位清楚的纵向接口错位：Research
Agent 已能得到代码证据，但代码级 atomic claim 被直接当成 Writer 的论文句子计划；Writer
若保留代码 token，正文像执行日志，若改写为论文语言，词汇匹配验证又容易失败。

---

## 0. 修复结论

### 0.1 当前真正缺少的层

当前链路是：

```text
CodeFact / RelationEvidence
  -> AtomicClaim
  -> MethodArgumentUnit
  -> Writer
```

`AtomicClaim` 是证据验证单元，不是论文论证单元。当前实现却在
`_section_reader_facing_claims()` 中直接把 `claim.canonical_text` 放进
`paper_statement`。典型值为：

```text
GaussianModel.construct_list_of_attributes loads weights self._features_rest
```

这会让 Writer 在“保留代码词以通过验证”和“改写为论文语言”之间冲突。

修复后的链路应为：

```text
Research Agent
  -> CodeFact / RelationEvidence / AtomicClaim
  -> Proposition candidate clustering（harness，只聚类，不写句子）
  -> Proposition Architect proposal（LLM，提议概念结构与术语角色）
  -> MethodProposition validator（harness，闭集校验和约束传播）
  -> MethodPropositionV1 + PropositionBindingSidecarV1
  -> Method Architect（按作者 story spine 放置 proposition）
  -> WriterViewV1（四层紧凑视图）
  -> Writer
  -> closed-set semantic alignment + deterministic evidence validation
  -> bounded Writer/Rewrite repair
  -> candidate / verified / review
```

### 0.2 Proposition 到底从哪里来

它不是由某一个组件独占产生，而是三步协作形成：

1. **Research Agent 负责事实来源。**
   - 自主搜索、读代码、追调用/数据流/控制流、查配置；
   - 产出 `EvidencePacketV3`、`CodeFactV1`、`RelationEvidenceV3`、
     `AtomicClaimV3` 和 typed gaps；
   - 不负责生成最终论文措辞；
   - 不把作者意图升级成实现事实。
2. **Proposition Architect 负责概念提议。**
   - 输入只能是本 obligation/section 的闭集 facts、relations、claims、作者术语和
     story node；
   - 提议哪些代码事实组成一个读者可理解的机制单元；
   - 提议 `representation / transformation / condition / output` 等语义角色；
   - 提议 paper term 与 code binding term 的对应；
   - 不能新增事实、证据、数字、公式、条件或支持状态。
3. **harness 负责校验和持久化。**
   - 校验所有 claim/fact/relation ID 属于输入闭集；
   - 校验聚合事实可连接，条件不冲突，数字/公式逐字来自授权表面；
   - 传播 qualifier、numeric、formula 和 authority lane；
   - 生成 binding sidecar 和 digest；
   - 不编写、补写或改写论文句子。

因此，更准确的定义是：

> `MethodPropositionV1` 是“证据支持的概念级论证卡片”，不是最终句子。

### 0.3 为什么不能让 harness 直接生成 proposition 句子

harness 可以确定：

- 哪些 facts 有关系边；
- 哪些 claims 有共同 subject、output 或 condition；
- 哪些 qualifier、数字、公式必须保留；
- 哪些 ID 属于闭集；
- 哪个 authority lane 可以支持哪类陈述。

harness 不应该确定：

- 论文中使用哪个自然语言主语；
- 如何把多条操作组织成流畅机制描述；
- 哪种术语最符合作者叙事；
- 如何写转折、定义、解释或段落衔接；
- 如何把 candidate intent 写成自然且明确的 caveat。

这些属于 LLM owner。规则层直接写这些内容会违反“最终 prose 只能来自 Writer、
Formalizer、Editor 或 Rewrite”的边界，也会重新滑回 deterministic template prose。

### 0.4 四层 Writer Prompt 是投影视图，不是新事实系统

四层 Writer 输入由 harness 从已验证 artifact 中投影：

1. 本节要回答什么；
2. 可正向陈述的 Method propositions；
3. 必须显式 caveat 的作者意图 propositions；
4. 不得改变的条件、数字和公式。

低层 semantic frame、fact ID、claim ID、relation ID 进入
`PropositionBindingSidecarV1`。Writer 不需要看到这些低层记录，也不能在正文中暴露它们。

Writer 可以看到紧凑的 `proposition_id`，用于结构化响应声明自己覆盖了哪些 proposition；
但 proposition ID 只能出现在 JSON metadata 中，不能进入 prose。harness 再通过 sidecar
解析到 claim/fact/evidence，完成验证和审计。

---

## 1. 已确认的根因和修复归属

### 1.1 根因 A：reader-facing claim 仍是代码级 canonical claim

现象：

- `_section_reader_facing_claims()` 将 `claim.canonical_text` 原样作为
  `paper_statement`；
- canonical text 多为函数、predicate 和 operand 序列；
- Writer Prompt 虽要求 Method language，但其句子计划仍由代码记录主导；
- 四项目仍有 1/1/1/2 个 code-trace style section。

修复归属：

- 新增 proposition compiler/architect/validator；
- Writer 以 proposition card 为内容计划；
- atomic claim 退回证据与验证角色。

### 1.2 根因 B：Writer Prompt 过长且多个 authority surface 互相竞争

当前 Writer system prompt 约 10K 字符、37 条 style rules；section payload 同时暴露：

- argument units；
- semantic frames；
- validation constraints；
- reader-facing claims；
- candidate points；
- rhetorical moves；
- callback protocol；
- binding contract；
- equation/configuration/formalization records。

本地 27B 模型往往优先完成 JSON/schema/ID copying，学术行文和 proposition coverage
被稀释。

修复归属：

- 新建紧凑 `WriterViewV1`；
- Prompt 只解释四层视图和输出职责；
- schema、binding、callback 细节尽量由 structured schema 与 sidecar 承担；
- 删除 system prompt 与 payload instruction 的重复规则。

### 1.3 根因 C：final semantic match 实际是 lexical match

现象：

- `_projection_matches()` 主要依赖 0.45 token overlap；
- publication path 明确设置 `max_semantic_verifier_calls=0`；
- 当前 semantic verifier 即便开启，也只在 deterministic failures 为空后调用；
- 它无法救回 `no_semantically_matching_projected_claim`；
- 64 个 candidate unsupported 单元中 53 个包含该失败。

修复归属：

- proposition-level closed-set semantic aligner；
- 语义 aligner 只选择 proposition ID，不授权 evidence；
- 选中 proposition 后仍运行 qualifier/numeric/formula/evidence deterministic gate；
- 不用 LLM verdict 替换硬验证。

### 1.4 根因 D：两个确定性 validator bug

已复现：

1. Formula regex 将 `current_layer_num == 0` 从标识符末尾误提取为 `m == 0`，导致
   `formula_not_in_direct_evidence`。
2. Atomic fragment splitter 将 `returns node_features and output` 拆成
   `returns node_features` 与 `output`；裸 `output` 又被 `_FACTUAL_HINT` 当作事实子句，
   继而错误匹配其他 output claim 和 qualifier。

修复归属：

- `text_evidence_validator.py`：公式/比较式边界；
- `final_text_claims.py`：clause-aware coordination splitting；
- 先修这些 bug，再评估模型或语义 verifier。

### 1.5 根因 E：作者 intent candidate point 粒度过粗

RAP 一个 mainline point 同时包含：feature、MLP、三种 loss、inference、pruning 和
rendering-free 目标。Writer 写成多个句子后，每句对整段 point 的 overlap 不足。

修复归属：

- intent proposition decomposition；
- 每个 candidate proposition 只表达一个概念；
- 每项单独保存 lane、caveat、已支持部分、缺失部分和 review question；
- supported 子句与 unverified 子句必须拆开，不能共用模糊 authority。

### 1.6 根因 F：Writer 没有内容级自修复

Writer 当前 owner retry 主要处理 schema/binding/length。对下列问题没有 Writer 回路：

- proposition 未渲染；
- qualifier 丢失；
- formula/numeric 变形；
- unsupported sentence；
- code-trace style。

修复归属：

- 新增 section-level bounded Writer self-repair supervisor；
- 每轮验证后生成紧凑 typed repair packet；
- LLM 可决定是否继续，但有 rounds/tokens/no-progress 上限；
- 只有受影响 section 重写。

### 1.7 根因 G：Rewrite 一次承担过多问题且没有逐轮事务验收

四项目 25 次 Rewrite transition：

- 14 次 `rewrite_candidate_not_readable`；
- 10 次表面 applied；
- 1 次 provider timeout；
- 最终 16 个 section 全部与原 Writer checkpoint 一致。

一次 Rewrite 常收到 10–25 个 issue，却只能返回一个 paragraph/full-section patch。模型
常通过删除整段处理 unsupported，随后被 readability gate 拒绝。即使第一轮有改善，第二轮
也可能回写原文；最终才做全局比较，导致有用局部修改丢失。

修复归属：

- issue clustering；
- 每轮只处理一个问题簇；
- 每次 patch 后立即做 section-level validation；
- 单调改进才事务提交；
- 下一轮从已提交 section 开始，而不是旧 incumbent。

### 1.8 根因 H：Editor 职责过宽且 representation failure 会浪费整次调用

实测：

- RAP Editor 四个 patch 都丢 heading；
- EBCAR 因一个 `reason` 超过 800 字符导致整个响应 schema failure；
- LinearRAG 因 claim loss、duplicate/style regression 整体拒绝；
- Editor 目前既做跨节结构，又补事实、改风格、修 authority，职责过载。

修复归属：

- Editor 退回跨节组织、重复、段落边界、transition；
- proposition coverage 和 evidence wording 返回 Writer/Rewrite；
- representation-only heading/reason 长度问题可恢复或逐 patch 拒绝；
- 不因一个 patch 失败丢弃其他独立安全 patch。

### 1.9 根因 I：质量指标把“部分命中”误报为完整 recall

RAP/EBCAR/DyG 的 `supported_unit_recall=1.0`，但最终 reverse validation 真正支持的
positive units 只有 4/2/3。当前以 completeness row 为单位，只要一行中任一 claim 被
粗略认为 rendered 就算 covered。

修复归属：

- 分开 planned/rendered/validated proposition recall；
- completeness row coverage 不再替代 proposition coverage；
- candidate 和 verified 的安全指标分开报告。

---

## 2. 新合同设计

### 2.1 `MethodPropositionV1`

建议新文件：

```text
src/code2paper/agentic/method_proposition_models.py
```

建议模型：

```python
class PropositionAuthorityLane(str, Enum):
    repository_verified = "repository_verified"
    repository_partial = "repository_partial"
    author_intent_unverified = "author_intent_unverified"
    repository_mismatch = "repository_mismatch"
    author_attested = "author_attested"
    literature_pending = "literature_pending"
    formalization_pending = "formalization_pending"


class MethodPropositionV1(BaseModel):
    proposition_id: str
    source_obligation_ids: tuple[str, ...]
    section_hint_ids: tuple[str, ...]

    authority_lane: PropositionAuthorityLane
    may_enter_verified: bool
    requires_caveat: bool

    # 概念结构，不是最终论文句子
    reader_subject: str
    transformation: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    conditions: tuple[str, ...]
    scope_or_boundary: tuple[str, ...]
    rationale_status: Literal[
        "not_claimed", "author_intended", "partially_supported", "supported"
    ]

    paper_terms: tuple[str, ...]
    implementation_binding_terms: tuple[str, ...]

    required_qualifiers: tuple[str, ...]
    required_numeric_tokens: tuple[str, ...]
    required_formula_ids: tuple[str, ...]
    required_configuration_ids: tuple[str, ...]

    support_claim_ids: tuple[str, ...]
    support_fact_ids: tuple[str, ...]
    support_relation_ids: tuple[str, ...]
    support_equation_ids: tuple[str, ...]

    missing_or_uncertain_parts: tuple[str, ...]
    review_question_ids: tuple[str, ...]
    content_digest: str
```

约束：

- `repository_verified` 必须有非空 `support_claim_ids` 与 `support_fact_ids`；
- `may_enter_verified=True` 只允许 repository-supported lane；
- `requires_caveat=True` 时不得 `may_enter_verified=True`；
- author intent proposition 不得携带会被解释为 executable authority 的支持 ID；
- partial proposition 必须把 supported 与 uncertain 字段分开；若一句话无法分开，拆成
  两个 proposition；
- required qualifiers/numerics/formulas 只能从绑定 claims/equations/configs 传播；
- `reader_subject/transformation/inputs/outputs` 不允许包含 internal IDs；
- 模型字段不能容纳自由“benefit/novelty/performance”陈述，除非对应 authority lane
  明确提供授权 artifact。

### 2.2 `PropositionBindingSidecarV1`

```python
class PropositionBindingV1(BaseModel):
    proposition_id: str
    claim_ids: tuple[str, ...]
    fact_ids: tuple[str, ...]
    relation_ids: tuple[str, ...]
    evidence_span_ids: tuple[str, ...]
    equation_ids: tuple[str, ...]
    configuration_ids: tuple[str, ...]
    source_digests: tuple[str, ...]
    content_digest: str


class PropositionBindingSidecarV1(BaseModel):
    schema_version: str = "1.0"
    proposition_set_digest: str
    bindings: tuple[PropositionBindingV1, ...]
    content_digest: str
```

该 sidecar 是 harness、validator 和审计使用的低层表面。默认不进入 Writer prompt。

### 2.3 `MethodPropositionSetV1`

```python
class MethodPropositionSetV1(BaseModel):
    schema_version: str = "1.0"
    project_id: str
    repo_snapshot_id: str
    intent_graph_digest: str
    claim_set_digest: str
    propositions: tuple[MethodPropositionV1, ...]
    unresolved_proposition_candidates: tuple[TypedPropositionGapV1, ...]
    content_digest: str
```

必须允许 proposition compilation 自身有 typed gap。编译失败不能用 atomic claim 的
canonical text 伪装成 reader-facing fallback。

### 2.4 `WriterViewV1`

建议新文件：

```text
src/code2paper/agentic/writer_view_projection.py
```

建议模型：

```python
class WriterSectionPurposeV1(BaseModel):
    heading: str
    reader_question: str
    section_goal: str
    preceding_context: str = ""
    following_context: str = ""


class WriterPositivePropositionV1(BaseModel):
    proposition_id: str
    reader_subject: str
    transformation: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    conditions: tuple[str, ...]
    paper_terms: tuple[str, ...]
    optional_implementation_bindings: tuple[str, ...]


class WriterCaveatedPropositionV1(BaseModel):
    proposition_id: str
    lane: str
    intended_subject: str
    intended_transformation: str
    known_parts: tuple[str, ...]
    missing_parts: tuple[str, ...]
    required_caveat_kind: Literal[
        "author_intent", "partial", "mismatch", "pending_external", "pending_formalization"
    ]
    review_question: str


class WriterImmutableConstraintV1(BaseModel):
    proposition_id: str
    required_qualifiers: tuple[str, ...]
    required_numeric_tokens: tuple[str, ...]
    formula_renderings: tuple[str, ...]
    configuration_values: tuple[str, ...]


class WriterViewV1(BaseModel):
    purpose: WriterSectionPurposeV1
    positive_propositions: tuple[WriterPositivePropositionV1, ...]
    caveated_propositions: tuple[WriterCaveatedPropositionV1, ...]
    immutable_constraints: tuple[WriterImmutableConstraintV1, ...]
    allowed_proposition_ids: tuple[str, ...]
    required_proposition_ids: tuple[str, ...]
    callback_opportunities: tuple[WritingResearchRequestPrototypeV1, ...]
    view_digest: str
```

四层恰好对应 `purpose / positive / caveated / immutable_constraints`。

### 2.5 Writer 输出合同

将 publication structured output 的主要绑定提升为 proposition：

```python
class PublicationMethodSectionOutputV2(BaseModel):
    section_id: str
    section_markdown: str
    rendered_proposition_ids: tuple[str, ...]
    deferred_proposition_ids: tuple[str, ...]
    completed_rhetorical_moves: tuple[str, ...]
    new_research_requests: tuple[WritingResearchRequestV1, ...]
    self_identified_risks: tuple[str, ...]
```

迁移期可保留 `used_claim_ids/used_equation_ids/used_configuration_ids` 只读兼容，但新
Writer prompt 不再要求模型同时复制所有低层 ID。harness 通过 proposition binding sidecar
派生这些低层集合用于验证，不把派生结果写成模型声称的事实。

---

## 3. Proposition 编译流程

### 3.1 输入

必须读取：

- `AtomicClaimSetV3`；
- `CodeFactSetV1`；
- `RelationEvidenceV3`；
- `EquationClaimSetV1`；
- `ConfigurationClaimSetV1`；
- `MethodCompletenessMatrixV1`；
- intent graph / story spine；
- 作者术语或原论文中的 semantic hints，仅用于术语和组织，不用于实现支持。

### 3.2 Harness 先产生 candidate clusters

建议文件：

```text
src/code2paper/agentic/method_proposition_compiler.py
```

聚类只使用通用结构条件：

- 同一 obligation；
- 同一或 relation-connected subject；
- DATA_DEPENDS_ON / CALLS / RETURNS_TO / NEXT_CONTROL / CONFIGURED_BY；
- 共享 produced entity；
- 同一 guard/condition；
- 明确 input -> transform -> output 链；
- 同一 equation 的组成 facts。

禁止：

- 项目名、特定源路径、已知函数名硬编码；
- 单纯 token overlap 将不相关 facts 聚在一起；
- 跨冲突 condition 合并；
- 为凑“完整段落”跨 obligation 合并；
- 用作者 intent 把缺失 code behavior 填入 positive cluster。

输出：

```python
class PropositionCandidateClusterV1(BaseModel):
    candidate_id: str
    obligation_ids: tuple[str, ...]
    allowed_claim_ids: tuple[str, ...]
    allowed_fact_ids: tuple[str, ...]
    allowed_relation_ids: tuple[str, ...]
    conditions: tuple[str, ...]
    candidate_semantic_roles: tuple[str, ...]
    author_term_hints: tuple[str, ...]
```

### 3.3 Proposition Architect 提议概念结构

这是一个低温、结构化 LLM role。建议：

```text
role=method_proposition_architect
temperature=0
seed=42
```

它的输出只允许：

- 从 candidate cluster 闭集选择 claim/fact/relation IDs；
- 将绑定项标为 reader subject/input/transformation/output/condition；
- 从作者 term hints 中选择 paper term；
- 请求拆分 cluster；
- 将无法安全聚合的 candidate 标为 unresolved；
- 对 candidate-only intent 做原子概念拆分。

它不允许：

- 写完整 Method paragraph；
- 新增数字、公式、配置、条件、benefit 或 purpose；
- 改变 support status；
- 把 semantic hint 当 repository evidence；
- 从候选闭集以外选择 ID。

### 3.4 Deterministic validation

`validate_method_proposition()` 至少验证：

1. ID closed-set；
2. 每个 positive proposition 至少一个 authorized supported claim；
3. 所有 claim fact IDs 能回到 frozen evidence span；
4. relation endpoints 与 facts 对齐；
5. conditions 为绑定 claims conditions 的并集或更强、不得更弱；
6. numeric tokens 为授权数值的子集且精确；
7. formula IDs 与 formula rendering 精确绑定；
8. configuration value 与 state/condition 一致；
9. author term 只是 alias，不改变 predicate、direction、quantity 或 effect；
10. partial/mismatch/intent lane 不得进入 verified；
11. proposition 不能同时包含互斥 branch；
12. proposition 不得把 log/debug/bookkeeping 行为升级成论文主要机制，除非作者 story
    明确要求且 Architect 选择保留；
13. 每个 proposition 的 binding sidecar 完整且 digest 一致。

失败时返回 typed issue 给 Proposition Architect；最多两次 owner repair。第二次仍失败则
持久化 `TypedPropositionGapV1`，不由 harness 生成 fallback prose。

### 3.5 Candidate intent decomposition

作者意图按自然概念边界拆分，而不是按原始 YAML 一整段保存。每个拆分项必须有：

- 单一设计动作或主张；
- 对应 story node/obligation；
- 当前代码支持的子集；
- 未验证/不匹配/外部依赖的子集；
- caveat kind；
- review question；
- 建议 callback owner。

若一句 intent 同时包含 supported 和 unsupported 部分，必须产生两个 proposition：

```text
P-positive: 代码已证明的变换
P-candidate: 作者希望但仓库未证明的目标/损失/效果
```

禁止产生一个混合 proposition，然后靠句首 `we aim` 把已支持和未支持内容一起模糊化。

---

## 4. Method Architect 集成

修改：

- `src/code2paper/agentic/method_argument_models.py`
- `src/code2paper/agentic/method_architect.py`
- `src/code2paper/agentic/authoring_projection.py`

### 4.1 Argument unit 增加 proposition IDs

```python
MethodArgumentUnitV1
  positive_proposition_ids
  caveated_proposition_ids
  proposition_order
```

原 `claim_ids/fact_ids/semantic_frame` 保留作 audit/binding metadata，不再作为 Writer 的
主要内容表面。

### 4.2 Section 规划原则

Architect 输入：

- author story spine；
- positive/caveated propositions；
- completeness/review/callback 状态；
- proposition dependencies。

Architect 输出：

- section question；
- section purpose；
- proposition 顺序；
- 哪些 proposition 同段、哪些应分段；
- 哪些 proposition 必须 callback 后再写；
- 哪些 candidate proposition 可带 caveat 进入 editable candidate。

Repository order 只能作为无作者组织信号时的 fallback。低层 exact placement、semantic
frame、move proof 继续作为审计和验证辅助，不再主导论文段落顺序。

### 4.3 Proposition dependency

依赖只表达论文理解顺序，例如：

```text
representation -> transformation -> objective -> inference/output
```

依赖可以由 relation graph、story spine 和 Architect proposal共同提议，但 harness 只接受
无环、闭集 proposition ID 的图。不得把所有 source control order 直接当论文顺序。

---

## 5. Writer Prompt 收缩与职责

修改：

- `src/code2paper/authoring/writer_skill.py`
- `src/code2paper/llm/section_writer.py`
- `src/code2paper/llm/response_schemas.py`
- `src/code2paper/agentic/publication_method_writer.py`

### 5.1 新 Prompt 核心

System prompt 保留五类内容：

1. 角色：论文 Method Writer；
2. authority：positive proposition 可正向写，candidate proposition 必须按指定 caveat 写；
3. fidelity：immutable constraints 不得变化；
4. style：以机制、表示、变换和输出为主语，代码名只作必要括号绑定；
5. callback：缺信息时可发 request，不得自行补事实。

不再在 system prompt 重复：

- 每种 internal ID 的复制规则；
- semantic frame 字段解释；
- validation constraint 的完整结构；
- 多遍相同的“不得编造”表述；
- schema 字段的自然语言复述；
- 与 response JSON schema 已等价的枚举约束。

### 5.2 Writer 只看到四层视图

示意：

```json
{
  "purpose": {
    "heading": "Feature representation",
    "reader_question": "How is each primitive represented before scoring?",
    "section_goal": "Explain representation construction and normalization."
  },
  "positive_propositions": [
    {
      "proposition_id": "MP-...",
      "reader_subject": "the primitive representation",
      "transformation": "combines base and residual attribute channels",
      "inputs": ["base attributes", "residual attributes"],
      "outputs": ["feature representation"],
      "conditions": [],
      "paper_terms": ["attribute feature representation"],
      "optional_implementation_bindings": ["construct_list_of_attributes"]
    }
  ],
  "caveated_propositions": [],
  "immutable_constraints": []
}
```

不再把整套 semantic frame、canonical claims、fact IDs 和 validation records 塞给 Writer。

### 5.3 Writer 内容要求

- 每个 required positive proposition 至少由一个完整句子或同一语义句组覆盖；
- 可合并有依赖关系的 propositions，但 metadata 必须声明全部 covered IDs；
- 不要求一 proposition 一句，也不要求一 claim 一句；
- 同一 proposition 不因多个 rhetorical move 重复写；
- candidate proposition 必须使用指定 caveat kind；
- 代码 binding 最多作为短括号或 implementation clause；
- 若没有足够内容，不填充通用背景，直接停止或 callback；
- Writer 不能看到或引用 claim/fact/frame ID；
- `rendered_proposition_ids` 只是模型提议，后续 validator 必须从正文验证。

### 5.4 Sampling

- Proposition Architect、semantic aligner、Verifier：`temperature=0`、`seed=42`；
- Writer：初始建议 `temperature=0.7`、`top_p=0.90`、固定 `seed=42`；
- Rewrite：建议 `temperature=0.45`、`top_p=0.90`；
- Editor：若只做结构性选择则低温；若被授权生成 transition prose，可用 0.5 左右；
- 所有有效参数写入 trace；
- 不通过换 seed 重跑同一失败请求等待幸运样本。

---

## 6. Writer section 自修复循环

建议新文件：

```text
src/code2paper/agentic/writer_section_repair.py
```

### 6.1 Repair packet

```python
class WriterSectionRepairPacketV1(BaseModel):
    section_id: str
    attempt: int
    incumbent_text: str
    missing_proposition_ids: tuple[str, ...]
    unsupported_spans: tuple[RepairSpanV1, ...]
    caveat_failures: tuple[RepairSpanV1, ...]
    qualifier_failures: tuple[ConstraintFailureV1, ...]
    numeric_formula_failures: tuple[ConstraintFailureV1, ...]
    style_failures: tuple[str, ...]
    allowed_positive_propositions: tuple[WriterPositivePropositionV1, ...]
    allowed_caveated_propositions: tuple[WriterCaveatedPropositionV1, ...]
    immutable_constraints: tuple[WriterImmutableConstraintV1, ...]
    previous_progress: WriterRepairProgressV1
```

### 6.2 循环

```text
Writer initial section
  -> proposition extraction/alignment
  -> deterministic validation
  -> style validation
  -> if clean: accept
  -> else build repair packet
  -> Writer decides regenerate/revise/callback/defer
  -> validate candidate
  -> commit only on monotonic progress
  -> repeat within budget
```

### 6.3 灵活次数与预算

不是固定“一次修复”。建议：

```python
max_writer_repair_rounds = 3
max_writer_repair_tokens_per_section = 8192
max_no_progress_rounds = 1
max_callbacks_per_section = 3
```

LLM 每轮可以返回：

- `accept_current`；
- `rewrite_section`；
- `request_research`；
- `defer_proposition`。

Supervisor 决定是否继续，停止条件：

- 所有 required propositions 已验证；
- 无 unsupported/constraint/style failure；
- 新 callback 进入研究回路；
- 连续一轮无指标改善；
- token/round budget 耗尽；
- owner 返回不可修复 typed gap。

预算耗尽时 section 保持 `incomplete`，candidate 可保留安全、caveated 内容，verified 只保留
验证通过内容。

### 6.4 单调进度向量

比较顺序：

```text
unsafe uncaveated positives（越少越好，最高优先）
constraint failures（越少越好）
validated required propositions（越多越好）
unrendered required propositions（越少越好）
code-trace style sections（越少越好）
duplicate rate（越少越好）
```

任何安全维度退化都拒绝。安全不退化时，只要至少一个主要质量维度严格改善即可提交。

---

## 7. Proposition-level semantic alignment

修改：

- `src/code2paper/agentic/final_text_claims.py`
- `src/code2paper/agentic/text_evidence_validator.py`
- 可新增 `src/code2paper/agentic/proposition_semantic_aligner.py`

### 7.1 两阶段匹配

第一阶段，deterministic candidate retrieval：

- 只从当前 section 的 closed proposition set 中召回；
- 使用 paper terms、concept fields、implementation binding terms、条件、输出；
- lexical exact/overlap 可以快速命中；
- 不在本节的 proposition 不参与。

第二阶段，必要时调用低温 semantic aligner：

```json
{
  "sentence": "...",
  "candidate_propositions": [
    {
      "proposition_id": "MP-...",
      "semantic_fields": {"subject": "...", "transformation": "..."},
      "constraints": {"conditions": [], "numbers": [], "formulas": []}
    }
  ]
}
```

输出只能是：

```json
{
  "status": "matched | no_match | ambiguous",
  "matched_proposition_ids": ["MP-..."],
  "preserved_roles": ["subject", "transformation", "output"],
  "missing_roles": [],
  "rationale": "..."
}
```

### 7.2 Semantic aligner 的权限边界

它可以确认 paraphrase 是否表达同一 proposition；不能：

- 新增 proposition；
- 选择本 section 闭集以外 ID；
- 授权 evidence；
- 忽略 qualifier、数字、公式或 branch；
- 将 ambiguous 当 matched；
- 把 author intent 升级成 repository positive。

匹配后，harness 仍执行：

- evidence span 存在性；
- qualifier preservation；
- numeric exactness；
- formula exactness；
- wording strength；
- authority lane；
- candidate caveat。

### 7.3 Budget

语义调用按 section 分配，避免全局普通句竞争同一额度：

```python
max_semantic_align_calls_per_section = 8
max_candidates_per_call = 6
```

只对 deterministic retrieval 召回候选但未达到 exact threshold 的句子调用。完全无候选的
domain invention 不应消耗 verifier 预算，直接判 unsupported。

---

## 8. 两个确定性 bug 的具体修复

### 8.1 Formula/condition regex 边界

目标文件：

```text
src/code2paper/agentic/text_evidence_validator.py
```

要求：

- 公式/比较式 identifier 必须从完整 identifier 边界开始；
- 支持 snake_case、dotted、indexed 和 call-shaped identifiers；
- `current_layer_num == 0` 只能提取完整 identifier，不能提取 `m == 0`；
- qualifier comparison 与普通数学公式分别分类；
- 反引号、Markdown math 和普通 prose 中表现一致；
- exact operator/value 规则保持 fail-closed。

最小回归：

```text
current_layer_num == 0        -> one exact comparison
self.cfg.mode != 1            -> one exact comparison
tensor.shape[0] > 1           -> one exact comparison
discount > 0 != count > 0     -> identifiers cannot collide
count > 10 != count > 1       -> values cannot prefix-match
```

### 8.2 Clause-aware coordination splitting

目标文件：

```text
src/code2paper/agentic/final_text_claims.py
```

要求：

- 仅当 `and/but/while/whereas` 两侧都有独立 predicate 时拆分；
- predicate 识别不能因名词 `output/input/model/method` 单独出现而成立；
- 保留 `returns x and y` 为一个 claim；
- 保留 `loads a and b` 为一个 claim；
- `computes x and returns y` 可以拆成两个；
- qualifier prefix 必须继续作用于整个 sentence unit；
- Markdown/code identifier 中包含 predicate token 不得误判。

将 `_FACTUAL_HINT` 分为：

- sentence factuality hints；
- independent clause verb hints。

不得继续用同一个包含名词的宽正则同时完成两个职责。

---

## 9. Rewrite 重构

修改：

- `src/code2paper/agentic/rewrite_agent.py`
- `src/code2paper/agentic/publication_method_writer.py`

### 9.1 Issue clustering

按优先级分组：

1. `unsafe_positive_or_authority`；
2. `qualifier_numeric_formula`；
3. `missing_supported_proposition`；
4. `method_language_style`；
5. `duplicate_or_transition`。

一次 Rewrite 只处理一个 section 的一个簇。不得一次传入 25 个混合 issue。

### 9.2 Patch 模式

- authority/constraint：精确 sentence 或 paragraph patch；
- missing proposition：完整相关 paragraph patch；
- pervasive code-trace：完整 section patch；
- duplicate/transition：Editor 优先，Rewrite 只在 section 内处理。

### 9.3 每 attempt 事务验收

每个 candidate patch 后立即：

1. 重建 section authorship ledger；
2. 运行 section proposition alignment；
3. 运行 deterministic evidence/constraint gate；
4. 运行 style detector；
5. 计算单调进度向量；
6. 接受则更新 incumbent；拒绝则保留旧 incumbent；
7. 下一 attempt 只接收尚未解决 issue。

禁止“先连续 applied 两次，最后才全局评估”，也禁止第二次用原文覆盖第一次已验证的改善。

### 9.4 删除策略

Rewrite 不得以删除整个 section 作为默认 unsupported 修复。只有以下情况可以删除 span：

- span 没有绑定 positive/candidate proposition；
- 删除后 section 仍有非空、可编辑正文；
- 不丢 required proposition；
- 不破坏 heading；
- 删除行为由 exact patch 和 response ref 记录。

---

## 10. Editor 收缩

修改：

- `src/code2paper/agentic/cross_section_editor.py`
- `src/code2paper/agentic/publication_method_writer.py`

Editor 只负责：

- section/paragraph 顺序建议；
- 跨节重复；
- transition；
- heading 保持；
- terminology consistency；
- 段落边界和整体逻辑。

Editor 不负责：

- 补写 missing proposition；
- 判断代码证据支持；
- 修 formula/numeric/qualifier；
- 将 candidate intent 升级为 positive；
- 处理 callback fulfillment。

### 10.1 Representation recovery

harness 可做的 representation-only 恢复：

- model replacement 非空但遗漏 exact unchanged heading 时，恢复原 heading；
- `reason` 超过 schema description limit 时，若 patch 其他字段已由结构化 decoder 完整返回，
  可以截断 diagnostic reason，不改变 replacement prose；
- 一个 patch schema/heading failure 只拒绝该 patch，不拒绝独立 section patch；
- 不得修正文义、补句或生成 transition。

### 10.2 Editor acceptance

逐 section transaction 接受；全局还需检查：

- section order 与 story spine；
- duplicate rate 不升；
- terminology consistency 不退化；
- proposition/evidence/constraint coverage 不退化；
- 每个修改字节有 Editor response provenance。

---

## 11. 质量指标和产品状态

修改：

- `src/code2paper/agentic/publication_quality.py`
- `src/code2paper/agentic/method_product_models.py`
- runner summary 与 artifact writer

### 11.1 新指标

```text
planned_required_propositions
rendered_required_propositions
validated_required_propositions
deferred_required_propositions
candidate_caveated_propositions
candidate_uncaveated_unsupported_units
verified_positive_units
verified_unsupported_positive_units
semantic_alignment_calls
semantic_alignment_ambiguous
writer_repair_rounds
writer_repair_commits
writer_repair_no_progress_stops
rewrite_issue_clusters_attempted
rewrite_transactions_committed
code_trace_sections
```

派生：

```text
planned_proposition_recall
rendered_proposition_recall
validated_proposition_recall
candidate_authority_precision
verified_support_precision
```

### 11.2 旧指标处理

- `supported_unit_recall` 保留兼容但标为 row-level；
- 不再把它作为“正文已覆盖 supported claims”的唯一指标；
- `support_precision=1.0` 必须明确属于 verified 或 candidate；
- candidate validation failed 不等于 verified 不安全；
- summary 同时报告 candidate 和 verified 状态。

### 11.3 状态

```text
complete
  = required proposition 全部 validated
    + callback 无本地可继续项
    + candidate 无 uncaveated unsupported
    + verified 无 unsupported
    + style/structure gate 通过

incomplete
  = candidate 安全可编辑，但仍有 deferred proposition、外部 review、callback budget
    或 publication quality issue

blocked
  = source/binding/integrity/authorship 失败，或存在无法隔离的 unsafe positive
```

不得因 verified split 能过滤 unsafe sentence 就把 candidate 标为 complete。

---

## 12. 代码级实施批次

### Batch 0：冻结诊断基线

不重新调用模型。编写只读诊断脚本或测试 fixture，从四个现有 root 提取：

- 每节原 Writer text；
- declared/rendered/validated claims；
- qualifier/formula failures；
- code-trace sections；
- Editor/Rewrite transitions；
- candidate/verified metrics。

目标是为后续前后对比提供同一口径，不把 `/tmp` artifact 当长期产品事实。

### Batch 1：修两个 deterministic bugs

文件：

- `final_text_claims.py`
- `text_evidence_validator.py`
- 对应 tests

退出条件：

- identifier suffix formula 误判消失；
- coordinated object 不被拆成裸 `output`；
- 现有 numeric/comparison/qualifier 安全测试无回归。

### Batch 2：Proposition contracts 与 compiler

新增：

- `method_proposition_models.py`
- `method_proposition_compiler.py`
- tests

修改：

- output name registry；
- authoring projection；
- artifact load/write helpers。

退出条件：

- supported facts 可形成 validated proposition；
- disconnected/conflicting facts 不能合并；
- partial/intent 拆分正确；
- sidecar 完整回放；
- compiler 不生成完整 prose fallback。

### Batch 3：Proposition Architect owner

新增 structured role 与 schema；接入 compiler 的 bounded proposal/repair。

退出条件：

- 只能选闭集 IDs；
- project-specific answer 不进入 generic code；
- unknown ID、condition weakening、numeric/formula invention 被拒绝；
- 两次失败形成 typed proposition gap。

### Batch 4：Architect 与 WriterView 集成

文件：

- `method_argument_models.py`
- `method_architect.py`
- `writer_view_projection.py`
- `publication_method_writer.py`

退出条件：

- section plan 以 story spine + propositions 组织；
- WriterView 只有四层；
- Writer payload 不含 raw fact/claim/frame records；
- sidecar 可从 proposition 回放到 evidence。

### Batch 5：Writer schema 与 Prompt 收缩

文件：

- `writer_skill.py`
- `section_writer.py`
- `response_schemas.py`
- publication writer tests

退出条件：

- system prompt 显著缩短且无重复合同；
- section schema 使用 closed proposition IDs；
- unknown proposition ID fail closed；
- missing ID 进入 content repair，不由 harness 补 prose；
- Writer 能输出自然 paragraph，不泄露 internal IDs。

### Batch 6：Writer self-repair

新增 `writer_section_repair.py` 并接入 publication writer。

退出条件：

- 缺 proposition、qualifier、formula、unsupported 和 style issue 可形成 typed packet；
- 修复轮次可配置 1–4；
- no-progress 可靠停止；
- 只重写受影响 section；
- 每轮候选事务验证和 checkpoint provenance 完整。

### Batch 7：Closed-set semantic aligner

新增 aligner，修改 final claim extraction/validation。

退出条件：

- 学术 paraphrase 可匹配同义 proposition；
- 不相关句、强度扩张、condition 丢失仍失败；
- author intent 不升级；
- semantic verifier 无法提供结果时 fail closed；
- 每节预算和 trace 完整。

### Batch 8：Rewrite transaction 与 Editor 收缩

文件：

- `rewrite_agent.py`
- `cross_section_editor.py`
- `publication_method_writer.py`

退出条件：

- 每次只处理一个 issue cluster；
- 第一轮改善不会被第二轮回滚；
- 删除整节继续被拒绝；
- Editor patch 独立提交；
- heading/reason representation recovery 不改 prose 意义。

### Batch 9：质量指标与 summary

退出条件：

- planned/rendered/validated proposition 三种 recall 分开；
- candidate/verified safety 分开；
- artifact 和 runner summary 同口径；
- 旧 row-level metric 不再误导完成状态。

### Batch 10：静态纵向验收

除 full suite 外必须有纵向 fixture：

```text
author intent
  -> facts/relations/claims
  -> propositions + sidecar
  -> story-spine section plan
  -> four-layer WriterView
  -> Writer initial failure
  -> Writer repair
  -> semantic alignment
  -> deterministic evidence validation
  -> candidate/verified/review split
```

fixture 至少覆盖：

- supported positive；
- partial supported；
- author intent caveat；
- repository mismatch；
- condition；
- numeric；
- equation；
- callback；
- paraphrase；
- unsupported benefit；
- rewrite no-progress；
- Editor independent patch。

### Batch 11：真实 API 验收

先做 frozen publication replay，确认 authoring 子系统的变化；再做 fresh end-to-end，确认新
proposition artifact 真正由研究输出产生，而不是复用旧计划。

顺序：

1. RAP authoring-only canary；
2. RAP fresh end-to-end；
3. 四项目 controlled concurrent 或资源压力下自动降级；
4. 对比原论文与 author intent 的 section logic；
5. 人工抽查 candidate 与 verified。

运行记录必须包含：

- runtime `/health` 与 `/v1/models`；
- model identity；
- role-specific temperature/top_p/seed；
- fresh output root；
- proposition counts；
- repair/semantic call counts；
- GPU running/waiting/KV/OOM/abort；
- candidate/verified/review 指标；
- exact commands 与 exit status。

---

## 13. 测试指南

### 13.1 新测试文件

建议：

```text
tests/test_agentic_method_proposition_models.py
tests/test_agentic_method_proposition_compiler.py
tests/test_agentic_method_proposition_architect.py
tests/test_agentic_writer_view_projection.py
tests/test_agentic_writer_section_repair.py
tests/test_agentic_proposition_semantic_aligner.py
tests/test_agentic_publication_proposition_metrics.py
```

### 13.2 必须扩展的现有测试

```text
tests/test_agentic_final_text_trust.py
tests/test_agentic_publication_method_writer.py
tests/test_agentic_d4_owner_fault_injection.py
tests/test_llm_section_writer.py
tests/test_llm_publication_schema_closed_sets.py
tests/test_agentic_method_architect_product_readiness.py
tests/test_d5_consolidated_runner.py
```

### 13.3 关键 mutation tests

- proposition 更换一个 operand；
- 删除 condition；
- `>` 改为 `>=`；
- 数字 10 改为 1；
- 作者 intent proposition 改成 positive；
- semantic aligner 返回闭集外 ID；
- sidecar claim ID 篡改；
- formula ID 与 rendering 不匹配；
- Writer metadata 声称覆盖但 prose 未覆盖；
- prose 覆盖但 metadata 漏报；
- Rewrite 改善 style 但丢 qualifier；
- Editor 改善重复但丢 proposition；
- callback artifact digest 不匹配；
- checkpoint 中 proposition set digest 变化。

所有 mutation 必须 fail closed 或产生 typed incomplete，不得静默通过。

---

## 14. 四项目验收标准

### 14.1 安全硬门

四项目都必须满足：

- verified unsupported positive = 0；
- candidate uncaveated unsupported positive = 0；
- author intent 未升级为 repository evidence；
- qualifier/numeric/formula exact gate 无回归；
- provenance、authorship、snapshot、callback、checkpoint 完整；
- 无 internal claim/fact/frame IDs 进入正文。

### 14.2 内容门

每个 required proposition 必须是以下三者之一：

- validated in candidate；
- visibly caveated candidate/review；
- typed deferred with callback/review reason。

禁止 silent drop。

目标：

- `validated_proposition_recall` 相比当前 validated claim/unit baseline 显著提高；
- code-trace style section 归零；若本地模型在预算内无法完成，保持 incomplete 并保存
  exact issue，不允许通过关闭 detector 宣称成功；
- 每节至少回答其 reader question，不使用 “In this section...” 等空模板填充；
- candidate 具有作者 story spine 的基本逻辑；
- verified 是 candidate 中实际验证通过句子的严格子集。

### 14.3 不是退出条件的指标

- 字节数更长；
- Writer 调用更多；
- 测试数量更多；
- hash/digest 数量更多；
- 单个项目偶然样本更漂亮；
- verified 通过但 candidate 大量 unsafe 后被过滤。

---

## 15. 不可采用的修复方式

1. 不把 lexical threshold 简单降低到让 paraphrase 自动通过。
2. 不让 semantic verifier 直接宣告 evidence supported。
3. 不让 harness 把 atomic claims 拼成 deterministic prose。
4. 不继续向 Writer prompt 塞更多低层 records。
5. 不要求 Writer 一次同时完成 prose、所有 claim IDs、equation IDs、config IDs、move IDs。
6. 不用更高 maxLength 解决 coverage。
7. 不把所有 candidate intent 都放到 review sidecar 而不写 editable candidate。
8. 不因 verified split 安全就忽略 candidate unsafe。
9. 不通过关闭 style detector 解决 code-trace prose。
10. 不用项目特定函数名、路径或答案硬编码 proposition。
11. 不用随机 seed 重跑同一失败寻找幸运样本。
12. 不让 Editor/Rewrite 删除整个正文来“通过”验证。

---

## 16. 最小可交付切片

如果需要控制首轮工程范围，最小纵向切片仍必须同时包含：

1. 两个 deterministic bug 修复；
2. `MethodPropositionV1` + binding sidecar；
3. supported/author-intent proposition decomposition；
4. 四层 `WriterViewV1`；
5. Writer proposition binding；
6. section-level validation/repair 一轮以上的可配置循环；
7. proposition-level closed-set semantic alignment；
8. planned/rendered/validated metrics；
9. RAP live canary。

只做 Prompt 改写不构成有效切片，因为数据和 verifier 冲突仍在；只做 verifier 语义化也不
构成有效切片，因为 Writer 仍会收到代码日志式句子计划。

---

## 17. 完成定义

本修复计划完成的含义是：

```text
Research Agent 找到并冻结代码事实
  -> 系统形成概念级、证据可追溯的 proposition cards
  -> Architect 按作者意图组织 cards
  -> Writer 只从四层紧凑视图写论文语言
  -> 写作失败能返回 Writer/Research 做有界自修复
  -> semantic aligner 允许真实 paraphrase，但不拥有 evidence authority
  -> qualifier/numeric/formula/evidence gate 继续 fail closed
  -> Editor/Rewrite 的每次修改逐事务验证
  -> candidate、verified、review 三种产品语义清楚
```

它不意味着 rollout、default cutover 或 publication-ready 已自动获得授权。四项目 live
结果必须按本计划重新验收，且 fresh end-to-end artifact 要证明 proposition 的来源确实是
当前 Research Agent 的 facts/relations/claims，而不是旧 frozen profile 或手工答案。

---

## 18. 2026-08-13 Codex 实施记录

已完成代码批次 1–9 和静态纵向验收：

- 修复 formula identifier / clause coordination 两个确定性缺陷；
- 新增 Method Proposition contracts、精确 evidence-connectivity clustering、低温 bounded
  Proposition Architect、digest-pinned binding sidecar 和 typed gaps；
- 同一 obligation 的少量 repository support 不再吞掉剩余 author-intent candidate；
- Proposition 接入 story-spine plan，Writer 使用类型化四层 WriterView；模型不再看到 raw
  fact/claim/frame records 作为句子计划；
- Writer 输出使用 closed proposition IDs，并支持最多 1–4 轮可配置内容自修复、单调提交和
  no-progress 停止；
- proposition semantic aligner 已接入真实 Writer 后验路径并持久化 alignment artifact；
- Editor 收缩为结构/重复/过渡/标题/术语，Rewrite 与 Editor 保持逐 section transaction；
- Proposition Architect 现在允许将一个宽泛 author-intent/completeness 行拆成最多 12 个
  原子概念卡，避免把特征表示、归一化、网络、训练目标和部署压成一张空泛 overview；
- 每张拆分卡必须精确回指 author statement 子串，数字/公式只从该子串传播；`reason`
  被隔离为 uncertainty note，不再混入方法内容或 immutable constraints；
- 新产品 Writer 请求只暴露四层 WriterView；旧的 semantic frame、reader-facing claim、
  validation constraint 和长 `content_first_instruction` 继续留在 harness 审计面，但不再
  与四层内容计划竞争模型注意力；
- Rewrite 按 safety、constraint、missing proposition、method language、duplicate/transition
  五类逐簇执行，同一调用不再混合责任，后一簇从前一簇已提交的 incumbent 继续；
- publication quality 与 runner summary 分开报告 planned/rendered/validated/deferred
  proposition 和 semantic alignment 指标；
- `python -m pytest -q`：2458 passed、3 skipped、12 subtests；`compileall`、
  `git diff --check` 均为 0。

2026-08-13 后续收口补充：

- `repository_partial` 即使带 qualifier 也永远不能进入 verified；
- repository 与 author proposition 均必须精确绑定 `source_statement_fragments`，避免宽 cluster
  的数字、公式和条件被广播到每张概念卡；多 fact proposition 还必须形成 relation/subject/
  claim connectivity 连通子图；
- Proposition Architect 的 validator 拒绝 benefit/performance/causal authority expansion 和
  闭集外 condition，并在第一次 validator failure 后把精确失败原因交还 owner 做一次 bounded
  correction；结构化输出预算提升到 3072，采样保持 greedy（temperature 0、seed 42）；
- publication Writer 强制读取 digest-pinned binding sidecar，并校验 proposition、claim、fact、
  relation、span 与 snapshot 的闭合；缺 sidecar 或篡改 digest 会在 Writer 前 fail closed；
- Writer 内容修复现在经过真实 reverse-validation、style、proposition coverage 事务比较；失败
  candidate 不提交，允许一次带失败原因的定向纠正，并持久化 incumbent/candidate digest 与拒绝
  原因；
- Rewrite 五类 issue cluster 每轮即时事务验收，只提交 assigned-cluster 有增益且其它安全维度
  不回退的版本；后续 attempt 从最近提交版本继续；
- Editor 的局部事务新增 WriterView proposition 无损约束；positive proposition 不能被静默
  删除，candidate proposition 除语义保留外还必须保留可见 caveat；
- proposition alignment 分开报告 rendered 与 reverse-evidence-validated IDs，且拒绝 negation、
  guarantee、causal/benefit 等 authority/polarity expansion；旧的高 lexical overlap 不再自动等于
  validated；
- 新增 frozen replay 诊断脚本，Batch 0 对旧 RAP replay 的结果为 candidate 2142B、verified
  944B、reverse supported=4/unsupported=13；旧产物没有 proposition artifact，MA-S1 是空泛
  promise。这是修复前基线，不是新代码 live 成功证据。

未完成的唯一计划退出项是 Batch 11 的 fresh live API 验收。当前环境检查结果为：

- `127.0.0.1:8002` 和 `127.0.0.1:8003` 均 connection refused；
- 无 vLLM/Qwen server 进程；
- `nvidia-smi` 无法连接 NVIDIA driver。

后续再次检查结果不变：8003 `/health` 与 `/v1/models` 均 connection refused、无 vLLM/Qwen
进程，`nvidia-smi` 无法连接 NVIDIA driver。因此没有提交 RAP 或其余项目，也没有声称 live
成功。运行时恢复后必须先串行运行 fresh
RAP canary，检查 proposition/alignment/repair artifacts 和正文语义，再决定是否并发运行
EBCAR、LinearRAG、DyG-Mamba。

最终静态里程碑（后续收口代码状态）：

```text
python -m pytest -q tests/test_agentic_method_propositions.py \
  tests/test_llm_section_writer.py tests/test_agentic_publication_method_writer.py \
  tests/test_agentic_proposition_semantic_aligner.py \
  tests/test_agentic_publication_replay_diagnostics.py \
  tests/test_llm_writer_section_repair.py tests/test_llm_role_config.py
# exit 0: 226 passed, 2 warnings

python -m pytest -q
# superseded by the final record below

python -m compileall -q src tests
# exit 0

git diff --check
# exit 0
```

2026-08-13 最终纵向收口：

- proposition-to-argument-unit 绑定发现并修复一个真实断链：compiler stage group 可能不携带
  obligation ID，即使选中的 `AtomicClaimV3.covers_obligation_ids` 已明确覆盖，repository-backed
  proposition 仍会从 Writer plan 消失。Architect 现在从选中 claims 的精确 coverage 补全
  `source_obligation_ids`，不使用词法猜测；
- `MethodArgumentUnitV1` 新增 closed、acyclic `proposition_dependencies`。当前实现把 Architect
  已选择的 reader-facing proposition 顺序编码为相邻依赖边，不把 source control order 当论文
  顺序；
- reverse validator 的 proposition match 进入正式证据链：闭集 semantic match 只负责确认
  paraphrase，sidecar 再展开到 projection claim/evidence；qualifier、数字、公式、条件、wording
  strength 和 authority lane 仍逐项 fail closed；
- proposition semantic owner 的有效参数、候选闭集、响应 digest、解析结果和失败原因均进入
  trace；Architect proposal clusters、calls、alignment calls 均有注册且持久化的 artifact；
- binding sidecar 从 cluster-wide 下放为 proposal-selected claim/fact/relation/span/equation/config
  精确绑定，避免一个宽 cluster 的 qualifier、数字或配置污染全部 propositions；
- Writer repair packet 现包含 missing proposition、精确 caveat/style/unsupported span、qualifier、
  numeric/formula/config failure 和 transaction failure。未经授权的 performance/benefit/guarantee
  语言会形成 exact span；语义/证据 transaction 先返回 owner feedback，再由单调性规则决定是否
  提交，因此危险 candidate 不会提交但仍有一次定向纠正机会；
- product closure 改为 proposition 三态：每个 required proposition 必须是 evidence-validated、
  visibly caveated，或带 typed reason deferred；silent drop 与 reasonless defer 都阻止 utility gate；
- candidate-only propositions 不再进入 evidence-validation 分母，因为它们按设计不能进入
  verified；candidate unsafe-positive 指标直接取 persisted reverse-validation failures，不再在
  quality report 中错误保持默认 0；
- 新增 `tests/test_agentic_method_proposition_vertical.py`，静态纵向覆盖 facts/claims → proposition
  + sidecar → Architect plan → 四层 WriterView → typed repair → semantic alignment → reverse
  validation → candidate/verified/review 三分产品。该测试直接发现并锁定了上述 Architect 断链。

最终静态记录（当前代码状态）：

```text
python -m pytest -q tests/test_llm_writer_section_repair.py \
  tests/test_agentic_method_architect_product_readiness.py \
  tests/test_agentic_method_proposition_vertical.py \
  tests/test_agentic_publication_method_writer.py \
  tests/test_agentic_final_text_trust.py
# exit 0: 149 passed, 2 warnings

python -m pytest -q
# exit 0: 2480 passed, 3 skipped, 2 warnings, 12 subtests passed in 43.75s

python -m compileall -q src tests
# exit 0

git diff --check
# exit 0
```

最终运行时探针仍为外部阻塞，不是生成质量判定：

```text
GET http://127.0.0.1:8003/health    -> HTTP 000, curl exit 7
GET http://127.0.0.1:8003/v1/models -> HTTP 000, curl exit 7
nvidia-smi                           -> exit 9, NVIDIA driver unavailable
```

因此 Batch 1–10 的代码和静态纵向验收完成；Batch 11 的 fresh RAP 与三项目回归尚未执行，
不能声称 live 完成。运行时恢复后的顺序固定为：先 fresh RAP，确认 proposal/sidecar/WriterView/
alignment/repair/product artifacts 均出现且正文覆盖 story spine；随后才运行 EBCAR、LinearRAG、
DyG-Mamba。四项目可在 engine 明确提供足够 sequence capacity 且 running/waiting/KV 压力安全时
受控并发，最多四路、各自 fresh root；否则立即降并发，绝不以换 seed 重跑等待幸运样本。
