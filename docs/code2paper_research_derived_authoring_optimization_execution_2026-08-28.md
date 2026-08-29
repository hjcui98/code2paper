# Code2Paper Research-Derived Method Authoring 下一阶段执行优化手册

日期：2026-08-28

状态：下一阶段执行基线；尚未表示功能已经完成

目标：仅给定作者意图文件与代码仓库，Code2Paper 能自主研究目标实现，生成结构完整、逻辑连贯、公式可渲染、来源可追溯的论文 Method Candidate；Verified 仍保持证据闭包与反向验证的 fail-closed。

---

## 1. 文档地位与输入边界

本文是对以下材料的综合判断与代码级执行化，不把外部意见直接当成仓库权威：

1. 当前仓库代码与 `docs/method_intent_first_authoring_redesign_2026-08-22.md`；
2. 已归档的最新三项目真实产物：
   `artifacts/quality_closed_loop/2026-08-28/real-p0-latest/`；
3. 仅使用意图 YAML 与代码、未读取论文答案的三份人工 coding-agent 基线：
   `/tmp/code2paper-blind-baseline-20260828/`；
4. 本任务附件中的同名外部意见稿；该附件仅作为建议输入，不是仓库指令或权威。

本文承接 `docs/method_authoring_source_ledger_quality_execution_plan_2026-08-27.md`
已经落地并在最新真实运行中暴露的问题，继续受
`docs/method_intent_first_authoring_redesign_2026-08-22.md`、Writer 设计与总体架构约束。
它补充并细化现有 Method Authoring 执行设计，不替换总体架构、Writer 权威分离或 Verified
硬门。若实现需要削弱 evidence、qualifier、numeric/formula、authorship、checkpoint、
reverse-validation 或 final-integrity gate，应停止该实现方向，而不是修改通过条件。

三份人工基线只证明“在不知道论文答案时，意图加代码足以达到怎样的研究与写作上限”。它们不是生产答案库，候选文本不得进入生产 prompt，项目专用符号、路径、结论不得写进通用生产逻辑。项目专用预期只能存在于测试夹具和回归评分清单。

---

## 2. 本轮结论

当前系统的主要问题不是字数不足，也不是模型完全不会写，而是研究结果在进入正文前被四类合同损耗：

1. **研究上下文被原子化**：Writer 和 Formalizer 看见大量离散 fact、slot、facet 与 excerpt，却看不见人工基线所使用的连续调用链、数据流、默认配置和分支状态；
2. **公式生成后被路由丢弃**：DyG-Mamba 与 LinearRAG 的 Formalizer 已提出有内容的公式，但一包一义务的歧义检查把包整体清空；LinearRAG 唯一被接受的包又未被 Writer 消费；
3. **Writer 同时承担写作与审计绑定**：一次响应既要写论文段落，又要填写大量 ID 和逐目标 exact witness。最新真实运行中模型普遍返回 `witnesses: []`，导致正文虽然存在，却全部不能计入结构覆盖；
4. **Candidate 表面语言与审计状态耦合**：当前 prompt 强制每个 caveated concept 显式保留 `intended`、`pending`、`unverified` 等词，模型因而写出“审计报告式正文”，不是自然的论文 Method。

因此，下一步不应继续增加更多 Writer 提示词或降低验证门。应把执行主线改为：

```text
author intent
  -> bounded repository research
  -> connected mechanism dossier
  -> typed derivation records
  -> paragraph plan + formula obligations
  -> AI Formalizer
  -> clean Writer prose
  -> separate evidence binder
  -> Candidate authority validation
  -> Candidate / Verified split
  -> existing reverse validation and final integrity gates
```

最终产品应同时回答两个不同问题：

- `candidate_complete`：研究与写作是否已经把 Method 主线写完整，并对不可闭合内容作了结构化处置；
- `verified_complete`：所有可发布正向实现事实是否都通过仓库证据闭包和反向验证。

`candidate_complete=true` 不推出 `publication_ready=true`。

---

## 3. 对意见稿的采纳决定

| 建议 | 决定 | 执行解释 |
|---|---|---|
| Clean Candidate 与审计 sidecar 分层 | 采纳，但修改 | 禁止正文反复出现内部审计词；但影响方法真实性的 intent/code mismatch 不能隐藏，必须由 Writer 用一次科学、自然的限制或差异句表达 |
| 增加 direct/static/semantic/formal/intent 推导类型 | 采纳 | 推导类型只是 provenance，不直接授予 Verified 权限；还必须记录条件、反证、claim strength 与来源 ID |
| AI-first Formalizer | 采纳 | AI 负责把连通代码机制抽象为论文公式；harness 负责闭集、路由、条件、符号和权威校验 |
| 一个公式可满足多个义务 | 采纳，但限制 | 一个 package 可有多个 `satisfied_obligation_ids`，但必须只有一个 canonical consumer paragraph；跨段冲突回到 Architect 修复 |
| Accepted formula 必须被 Writer 消费 | 采纳 | 接受后必须消费或有 typed rejection；required 公式不能被 Writer 随意拒绝 |
| EBCAR required formula 零调用断言 | 采纳并推广 | 所有项目都执行生命周期断言，不写项目专用分支 |
| Candidate 与 Verified 完成语义分离 | 采纳 | 新增独立状态与 validator，保留旧字段做兼容，不让 Candidate 状态篡改 Verified 门 |
| 复杂度、稳定性、鲁棒性可由 AI 研究得到 | 部分采纳 | 只允许在代码链和显式假设闭合时写成 `conditional_analysis`；经验效果、保证和优越性不能由结构相似性推出 |
| 作者意图缺代码时也可给公式 | 部分采纳 | 可进入 Candidate 的 `author_intent_academic`，必须 review-required，不能标 `code_verified`，不能进入 Verified |
| Clean Candidate 完全不出现任何差异说明 | 不采纳 | 会把代码冲突悄悄改写成无条件方法事实；允许一次正常论文语言的 material limitation，不允许内部流水线术语 |
| 直接删除现有 safety/trace validator | 不采纳 | 当前失败应通过更好的研究包、路由和绑定修复，不能通过过滤 claim 或放松匹配获得通过 |

---

## 4. 三份基线与最新真实产物说明了什么

### 4.1 文本长度不是瓶颈

| 项目 | 当前 Candidate | 人工盲测基线 | 关键区别 |
|---|---:|---:|---|
| EBCAR | 1177 词 | 1192 词 | 当前没有接受或消费公式；基线从调用链恢复 5 个公式义务 |
| DyG-Mamba | 1779 词 | 1425 词 | 当前更长但含大量 intended/pending；基线能区分 active code、默认关闭分支与 intent/code mismatch |
| LinearRAG | 1478 词 | 1384 词 | 当前唯一接受公式未消费；基线从代码恢复 9 个公式表达并指出并非完整 Tri-Graph |

不能再用增加段落或 token budget 作为主要修复。当前 Candidate 已经达到相近字数，但研究密度、公式密度和结构闭包显著更低。

### 4.2 最新结构出口的直接证据

| 项目 | required paragraph | witnessed slot | 公式 | 主要结构故障 |
|---|---:|---:|---:|---|
| EBCAR | `0/1` | `0/8` | accepted `0`，consumed `0` | MA-S3 有 required formula consumer，但 Formalizer `call_traces=[]` |
| DyG-Mamba | `0/10` | `0/56` | accepted `0`，consumed `0` | 三个 formula section 的两次有效提案均因 route ambiguous 被清空 |
| LinearRAG | `0/10` | `0/69`，edge `0/1` | accepted `1`，consumed `0` | 多数 paragraph 声明 slot 但 `witnesses=[]`；accepted package 未进入正文 |

三个项目的 `publication_quality_report_v1.json` 均为 `blocked`，`support_precision=0.0`，`equation_coverage=0.0`。这不是人工基线比系统“更敢写”，而是人工过程完成了连续研究、抽象、写作和审计分离，而当前流水线在这些阶段之间丢失了语义与消费关系。

### 4.3 人工基线证明的可实现能力

人工基线没有读取论文答案，却能够从代码得到：

- EBCAR：检索、相对文档 ID、归一化位置编码、混合 attention、query-anchor score、InfoNCE、推理排序，以及训练/推理 mask 与入口/checkpoint 差异；
- DyG-Mamba：严格历史截断、四通道输入、时间控制量、selective scan、`A=-exp(A_log)`、shared encoder、cross-linear attention、gated top-k pooling、任务损失与未启用分支；
- LinearRAG：实体/段落图的实际顶点类型、辅助 sentence 映射、边权、阈值传播、hybrid score、PPR、dense fallback 与 QA 下游。

这说明下一阶段应提升“从代码链形成研究结论”的能力，而不是把更多原始代码标识符直接塞给 Writer。

---

## 5. 必须保持的产品不变量

1. Author intent 决定研究范围、故事顺序和候选规格，不授权实现事实；
2. `repository_statement` 必须有直接或闭合推导证据；
3. `author_specification` 与 `mismatch_statement` 可进入 Candidate，不得进入 Verified；
4. `semantic_derived` 只能成为 Candidate 表达提案，不能直接翻转 `AuthorClauseLicenseV1`；
5. `formal_derived` 公式只有在代码操作、条件和符号都闭合时才能成为 `repository_derived`；
6. empirical improvement、competitive advantage、robustness、stability guarantee、complexity superiority 不得从模块名称或常识推出；
7. final prose token 仍只来自 Writer、Formalizer、Editor 或 Rewrite；Binder 只能复制正文 substring 并产生 metadata；
8. missing output、empty witness、unconsumed formula、unknown ID、digest mismatch 都不能当成功；
9. test fixture 可写项目预期，生产代码不得包含 EBCAR、DyG-Mamba、LinearRAG 的专用答案；
10. 本切片不宣布 D5、rollout、default cutover 或 release freeze。

---

## 6. 目标数据合同

### 6.1 `ResearchMechanismDossierV1`

新增文件：`src/code2paper/agentic/research_derived_authoring.py`。

每个 formula-worthy 或 mechanism-heavy paragraph 在 Architect 之后、Formalizer 之前得到一个连通研究包：

```python
class ResearchMechanismDossierV1(BaseModel):
    dossier_id: str
    section_id: str
    paragraph_id: str
    facet_ids: tuple[str, ...]
    author_question: str
    author_statements: tuple[str, ...]

    entry_symbol_ids: tuple[str, ...]
    ordered_operation_node_ids: tuple[str, ...]
    relation_ids: tuple[str, ...]
    call_path_relation_ids: tuple[str, ...]
    data_flow_relation_ids: tuple[str, ...]
    control_flow_relation_ids: tuple[str, ...]

    operation_atoms: tuple[dict[str, Any], ...]
    configuration_bindings: tuple[dict[str, Any], ...]
    default_activation: Literal[
        "active", "inactive", "conditional", "unknown"
    ]
    active_path_conditions: tuple[str, ...]
    unresolved_relations: tuple[str, ...]

    exact_span_ids: tuple[str, ...]
    exact_excerpts: tuple[str, ...]
    fact_ids: tuple[str, ...]
    equation_ids: tuple[str, ...]
    contradiction_ids: tuple[str, ...]
    content_digest: str
```

约束：

- dossier 必须是 `CodeBehaviorGraphV1` 上的最小连通子图，不能只是同一 section 的 fact 并集；
- 运行顺序优先使用 `NEXT_CONTROL`、`CALLS`、`RETURNS_TO`、`DATA_DEPENDS_ON`、`CONTROL_DEPENDS_ON`；
- `default_activation` 必须来自配置默认值与入口调用链，不能只因类定义存在就标 active；
- unresolved dynamic call 保留为 unresolved，不猜目标；
- `exact_excerpts` 必须由已冻结 span 读取，dossier 编译器不生成论文句子；
- 若 required mechanism 无法形成连通 dossier，产生定向 Research callback，而不是用 author text 假装代码链。

复用现有能力：

- `behavior_graph.py` 的 node/relation 类型；
- `behavior_graph_tools.py::build_behavior_subgraph`；
- `research_tools.py` 的 `trace_call_path`、`trace_data_flow`、`inspect_control_flow`；
- `implementation_scope.py` 的 target ownership；
- `scientific_claim_ir.py` 的 L1 operation chain；
- `configuration_claims.py` 的 default/override chain。

### 6.2 `DerivationRecordV1`

同一新模块定义轻量 provenance，不建立新的庞大 ontology：

```python
DerivationKindV1 = Literal[
    "direct",
    "static_derived",
    "semantic_derived",
    "formal_derived",
    "author_intent_only",
]

ClaimStrengthV1 = Literal[
    "descriptive",
    "structural",
    "conditional_analysis",
    "empirical",
    "guarantee",
]

class DerivationRecordV1(BaseModel):
    derivation_id: str
    section_id: str
    paragraph_id: str
    facet_id: str
    field_name: str
    semantic_atom: str
    derivation_kind: DerivationKindV1
    claim_strength: ClaimStrengthV1
    authority_status: Literal[
        "repository_supported",
        "repository_partial",
        "author_intent",
        "intent_code_mismatch",
        "unresolved",
    ]
    dossier_ids: tuple[str, ...]
    fact_ids: tuple[str, ...]
    relation_ids: tuple[str, ...]
    equation_ids: tuple[str, ...]
    assumptions: tuple[str, ...]
    active_conditions: tuple[str, ...]
    contradiction_ids: tuple[str, ...]
    confidence: float
    candidate_allowed: bool
    verified_eligible: bool
    content_digest: str
```

权限矩阵：

| derivation kind | Candidate | Verified eligibility |
|---|---|---|
| `direct` | 可按 policy 表达 | 可进入现有 deterministic/reverse-validation 路径 |
| `static_derived` | 可表达闭合变换、条件与结构 | 只有所有操作与边均为 executable authority 且反向验证通过 |
| `semantic_derived` | 可作为 Candidate proposal | 永不直接翻转 Verified license |
| `formal_derived` | 可使用 Formalizer package | 仅 `repository_derived + code_verified` 可继续 Verified |
| `author_intent_only` | 仅 `author_specification` | 永不进入 Verified |

`claim_strength` 再加一道上限：

- `descriptive`、`structural` 可由 direct/static 闭合；
- `conditional_analysis` 必须有 assumptions，正文必须保留条件；
- `empirical` 必须绑定实验产物或外部证据；
- `guarantee` 必须有明确证明或测试协议，不能由 semantic/formal 常识升级；
- `semantic_derived` 即使 confidence 高，也不能把 empirical/guarantee 变成 repository-supported。

### 6.3 扩展 `PublicationFieldCandidateV1`

文件：`src/code2paper/agentic/method_argument_brief_models.py`。

增加：

```python
derivation_record_ids: tuple[str, ...] = ()
derivation_kind: DerivationKindV1 = "direct"
claim_strength: ClaimStrengthV1 = "descriptive"
surface_mode: Literal[
    "repository_statement",
    "author_specification",
    "mismatch_statement",
    "scoped_limitation",
    "omit_and_review",
] = "omit_and_review"
```

保留原 `bound_*`、`exact_excerpts`、`render_policy`。新字段不能绕开原闭集检查；`required repository_statement` 仍必须有 evidence binding。`author_specification` 可没有 code fact，但必须有 author facet；`mismatch_statement` 必须同时有 author facet 与 contradiction record。

### 6.4 公式 package 改为多义务、单消费者

文件：`src/code2paper/agentic/formalization_agent.py`。

`SectionFormulaPackageV1` 增加：

```python
satisfied_obligation_ids: tuple[str, ...] = ()
consumer_paragraph_id: str
semantic_formula_digest: str
```

兼容规则：

- 读取旧 artifact 时，若只有 `obligation_id`，规范化为单元素 `satisfied_obligation_ids`；
- 新 artifact 写出 `satisfied_obligation_ids`，`obligation_id` 仅在单元素时保留兼容值；
- 一个 package 的所有 obligations 必须属于同一 section，且解析到同一个 `consumer_paragraph_id`；
- 同一 obligation 仍只能由一个 accepted package 满足；
- 同一 paragraph 可消费多个不同 mechanism package；
- 某个 package 路由失败时只拒绝该包，不得把该 section 其他合法包一起清空。

---

## 7. 执行切片与代码修改

## Slice 0：冻结对照与补齐观测

目的：先把当前三个故障转成自动化指标，避免修复后只能目测。

### 修改

`src/code2paper/agentic/publication_replay_diagnostics.py`

新增以下计数：

- `required_formula_consumer_sections`；
- `formalizer_invoked_sections`；
- `formalizer_zero_call_required_sections`；
- `formula_route_ambiguous_packages`；
- `accepted_formula_packages` / `consumed_formula_packages`；
- `paragraph_declared_target_count` / `paragraph_exact_witness_count`；
- `empty_witness_transaction_count`；
- `candidate_internal_audit_term_count`；
- `candidate_sentences_by_surface_mode`；
- `derivation_records_by_kind`。

`scripts/evaluate_research_derived_authoring.py`

新增一个只读 evaluator，输入一个 fresh run root，输出：

- story/paragraph/slot/edge/formula coverage；
- formula renderability 与 consumption；
- Candidate surface cleanliness；
- Candidate authority validation；
- Verified leakage；
- 与可选 test manifest 的 semantic expectation 对比。

不得用基线候选文本作字符串答案；只允许 test manifest 描述机制类别、必需差异和禁止结论。

### 退出

- 在当前归档产物上能自动复现 EBCAR zero-call、DyG route ambiguity、LinearRAG unconsumed package 和三项目 empty witness 问题；
- evaluator 不修改 artifact；
- 不改变当前运行结果。

---

## Slice 1：修复 Formalizer 生命周期与公式路由

这是第一项行为修改。当前已经有高价值公式响应，先停止丢包。

### 1.1 `formalization_agent.py`

修改：

- `MethodFormulaObligationV2`：保留单 consumer，增加可选 `mechanism_key`，供 Architect 对同一公式义务去重；
- `SectionFormulaPackageV1`：实现 `satisfied_obligation_ids`；
- `validate_section_formula_package`：
  - 每个 satisfied ID 必须属于输入闭集；
  - 所有 obligation 必须解析到同一 consumer；
  - repository lane 保持 exact operation/number/condition 闭包；
  - hybrid/author lane 保持 assumptions 与 review-required；
- `section_result_from_packages`：
  - 删除“多个 facet/equation match 即整包 ambiguous”的默认绑定；
  - 新响应必须显式返回 closed-set obligation IDs；
  - 对旧响应仅在唯一可解析时兼容绑定；
  - route failure 按 package 隔离，不清空其他 package；
  - obligation truth 从 `obligation -> package` 映射计算。

`_formula_code_trace_failures` 与理论升级检查不得放松。

### 1.2 `publication_method_writer.py`

修改：

- `_section_formula_obligations`：在同一 paragraph 内按 `mechanism_key` 合并别名义务，不把多个 facet 机械变成多个公式；
- `_run_section_formalizer`：
  - 删除 required 公式调用对全局 `l1_chain_length(facts) >= 2` 的依赖；
  - 判断改为 section-local：`required/preferred obligation + canonical consumer + caller`；
  - required 且 consumer 存在时，必须出现 LLM call 或已接受的 deterministic package；
  - caller 缺失或零调用时产生 `formalizer_not_invoked` typed disposition，required 时阻塞 Candidate；
- `_invoke_section_formalizer_llm`：
  - prompt 要求 package 显式返回 `satisfied_obligation_ids` 与 `consumer_paragraph_id`；
  - guided schema 把 IDs 约束到本 section 闭集；
  - `_bind_current_formula_route` 只用于旧响应兼容，不再从多 facet 猜唯一义务；
- `_writer_visible_formula_packages`：向 Writer 输出多义务路由；
- `_paste_missing_formula_blocks`：仅保留 representation-only fallback，必须粘到 canonical consumer，记录 transition，不得借此生成或改写公式。

### 1.3 `method_architect.py`

在 paragraph formula placement 阶段执行：

```text
same mechanism_key + same consumer paragraph
  -> one canonical formula obligation
  -> all source facet/slot ids retained as satisfied targets
```

若同一 mechanism 被安排到不同 paragraph，Architect 必须选一个 canonical owner；其他 paragraph 只能通过 narrative reference 使用，不得各自要求复制公式。

### 测试

扩展：

- `tests/test_agentic_formalization_guards.py`；
- `tests/test_agentic_formula_obligation_truths.py`；
- `tests/test_agentic_method_authoring_p0_closure.py`；
- `tests/test_agentic_intent_authoring_live_repair.py`。

至少覆盖：

1. 一个 package 满足同段两个 obligations，接受且两项 truth 均 rendered；
2. 两个 obligations 指向不同段，同包拒绝；
3. 一个坏包不清空同节好包；
4. required consumer + caller 时 call count 至少 1；
5. required consumer + zero call 产生 `formalizer_not_invoked`，不能 deterministic success；
6. author-intent package 永不 `code_verified`；
7. incidental `x+y`/`x*y` 仍不能成为 repository formula。

### 退出

- DyG-Mamba 不再出现 `formula_package_obligation_route_ambiguous` 导致整节零包；
- LinearRAG accepted package 有确定 obligation route；
- EBCAR required formula consumer 不再有 `call_traces=[]` 的无类型空洞。

---

## Slice 2：构建连续研究 dossier 与推导 provenance

### 2.1 新增 `research_derived_authoring.py`

实现以下纯函数优先的接口：

```python
build_research_mechanism_dossiers(
    *,
    plan,
    facets,
    field_candidates,
    behavior_graph,
    facts,
    claims,
    equations,
    configurations,
    evidence_packets,
    implementation_scope,
) -> tuple[ResearchMechanismDossierV1, ...]

compile_derivation_records(
    *,
    dossiers,
    facets,
    alignments,
    formula_results,
) -> tuple[DerivationRecordV1, ...]

merge_derivations_into_field_candidates(
    *,
    candidates,
    derivations,
) -> tuple[PublicationFieldCandidateV1, ...]
```

编译规则：

1. 从 paragraph 的 facet/field/slot 反查 fact 与 relation；
2. 在 behavior graph 上找覆盖这些锚点的最小连通子图；
3. 按 control/data/call relation 排序 operation atoms；
4. 附加配置默认值、入口覆盖链与 active/inactive 状态；
5. 附加 exact spans 与 unresolved relation；
6. 检查 target ownership，comparand/evaluation/configuration 不能成为目标方法正向主线；
7. 内容寻址并持久化 `research_mechanism_dossiers_v1.json` 与 `derivation_records_v1.json`。

### 2.2 Research callback

当 dossier 不连通或 required field 只有孤立 fact 时，使用已有 Research Graph 产生定向请求：

- 缺 callee：`trace_call_path` / `build_behavior_subgraph`；
- 缺数据来源或去向：`trace_data_flow`；
- 缺 active branch：`inspect_control_flow` + configuration binding；
- 缺 source body：`read_symbol`；
- 动态关系无法静态解析：保留 unresolved，不能原样重跑碰运气。

callback 返回后只重编译受影响 dossier、derivation、formula 和 section，不重跑无关项目或全量 intake。

### 2.3 Formalizer 输入升级

扩展 `MechanismEquationEvidencePackV1`，或让其引用 dossier：

```python
dossier_ids: tuple[str, ...]
ordered_operation_node_ids: tuple[str, ...]
call_path_relation_ids: tuple[str, ...]
data_flow_relation_ids: tuple[str, ...]
configuration_bindings: tuple[dict[str, Any], ...]
default_activation: str
unresolved_relations: tuple[str, ...]
```

`build_mechanism_equation_evidence_packs` 不再只按单个 equation 建包。它应按 mechanism/paragraph 聚合相连操作；允许一个 aligned LaTeX block 表达多步变换，但必须保留每步来源与条件。

### 2.4 静态与语义推导边界

可静态推导：

- 归一化、加权和、dot product、softmax/contrastive loss、阈值传播、PPR 更新、状态更新；
- 明确循环与容器大小下的条件复杂度表达；
- 默认配置是否启用某分支；
- shared vs independent parameter object；
- mean/top-k/gated readout 的实际类型。

不可仅由结构推导：

- “更快”“更准确”“更有竞争力”；
- “稳定”“抗噪”“Lipschitz”“收敛”；
- “优于 PPR/attention/SSM”；
- 经验线性扩展、zero-token cost；
- 未运行分支的实际训练效果。

后者没有相应证据时使用 `author_intent_only`、`unresolved` 或 `conditional_analysis`，不得升级为 repository statement。

### 测试

新增 `tests/test_agentic_research_derived_authoring.py`，用通用小型 Python fixture 覆盖：

- caller -> encoder -> normalization -> score 的有序 dossier；
- configuration default 关闭分支；
- shared object identity 与两个独立实例；
- unresolved dynamic call；
- comparand/evaluation 被排除；
- connected static formula 可生成 derivation，孤立 shape arithmetic 不可；
- conditional complexity 缺 assumption 时不得 candidate-allow；
- semantic confidence 不得翻转 Verified eligibility。

### 退出

- 三项目 required mechanism paragraph 都有 dossier，或有精确 typed gap；
- Writer/Formalizer 不再主要依赖无顺序 fact 列表理解机制；
- 新 artifact 进入 freshness/digest 依赖图，evidence 或 behavior graph 变化会使受影响 dossier 失效。

---

## Slice 3：Writer 清洁表面与两阶段证据绑定

### 3.1 分离 paper surface 与 audit disposition

文件：`src/code2paper/agentic/writer_view_projection.py`。

保留 `required_caveat_kind` 作为 sidecar 状态，但 Writer 可见的主要字段改为 `surface_mode`：

- `repository_statement`：正常方法事实；
- `author_specification`：按作者设计写正常学术定义，不反复使用 intended/pending；
- `mismatch_statement`：一次自然语言同时说明规格与当前实现差异；
- `scoped_limitation`：正常论文限制句；
- `omit_and_review`：不进入 clean prose，仅进入 review sidecar。

删除以下 prompt 级强制：每个 caveated concept 都必须显式出现 intended/partial/pending/unverified token。替换为：

```text
Write normal paper prose according to surface_mode. Never mention internal
pipeline terms such as audit, callback, repository evidence, pending
formalization, sidecar, or validation status. Do not turn author_specification
or mismatch_statement into a repository-supported implementation fact. If a
material mismatch changes the described method, state it once in scientific
language; otherwise keep the status in the structured review output.
```

对应文件：

- `src/code2paper/authoring/writer_skill.py`；
- `src/code2paper/agents/config/prompts/publication_method_section_writer.txt`；
- `src/code2paper/llm/section_writer.py::_compact_writer_view_for_llm`。

### 3.2 Writer 输入只保留一个有序 authoring packet

当前 `_writer_section_inputs` 同时发送 writer view、argument units、mechanism section、brief、facet、slot 和 formula 多层重复信息。新增 `PublicationAuthoringPacketV2`，每段仅暴露：

```text
paragraph identity and rhetorical goal
ordered research-derived semantic targets
surface_mode for each target
connected mechanism dossier summary
material conditions and configuration state
formula packages owned by this paragraph
closed target IDs
preceding/following paragraph context
```

修改：

- `publication_method_writer.py::_writer_section_inputs`；
- `section_writer.py::_compact_authoring_packet_for_llm`；
- `section_writer.py::_compact_writer_view_for_llm`。

旧 payload 继续可读，但新 production path 只选 V2 packet，防止同一事实以不同措辞重复进入 prompt。

### 3.3 两阶段 paragraph transaction

当前 `PublicationMethodParagraphOutputV1` 要求模型一次完成正文、closed IDs 和 exact witnesses。真实运行表明模型会写正文并声明 IDs，却把 `witnesses` 留空。改成：

#### 阶段 A：Writer prose

Writer 输出：

```python
paragraph_id
paragraph_markdown
rendered target IDs
used_formula_package_ids
unresolved points
```

Writer 不负责 exact witness bookkeeping。公式仍必须原样包含 Formalizer `markdown_block`。

#### 阶段 B：Paragraph Evidence Binder

新增响应模型：

```python
class PublicationParagraphBindingResponseV1(BaseModel):
    paragraph_id: str
    witnesses: tuple[PublicationContentWitnessV1, ...]
    unbound_target_ids: tuple[str, ...]
```

Binder 输入只包含：

- 冻结 `paragraph_markdown`；
- paragraph-local closed target contracts；
- semantic atoms、conditions、allowed excerpts；
- formula package exact block。

Binder 只能从 paragraph 原文复制 `exact_text`，不能重写正文，不能新增 claim，不能改变 surface mode。先执行确定性 exact/anchor 匹配；剩余目标再调用一次低温 Binder。结果继续由 `assess_paragraph_transaction` 检查唯一 substring、anchor、polarity、condition 与 closed ID。

路由规则：

- Binder 输出非法 substring：Binder representation retry，最多一次；
- 正文实际缺 target：回 Writer Repair，并携带缺失 target 与前一版正文；
- 公式 block 缺失：回 Writer/Formula consumption repair；
- 证据本身不够：回 Research，不交 Rewrite；
- 纯风格问题才交 Editor/Rewrite。

修改文件：

- `src/code2paper/llm/response_schemas.py`；
- `src/code2paper/llm/section_writer.py::_closed_set_publication_schema`；
- `src/code2paper/llm/section_writer.py::_normalize_publication_paragraph_transaction`；
- `src/code2paper/agentic/publication_transaction_contract.py`；
- `src/code2paper/agentic/publication_method_writer.py::_write_paragraph_transaction_assessments`。

现有 `PublicationContentWitnessV1` 与 `assess_paragraph_transaction` 保留为单一验证权威，不能把 declared ID 本身当 witness。

### 3.4 公式消费闭环

对每个 accepted package：

```text
accepted
  -> routed to canonical paragraph
  -> exact markdown block appears in paragraph
  -> Binder creates formula witness
  -> transaction assessment counts satisfied obligations
  -> method_content_trace records one consumer
```

若 Writer 明确拒绝 package，新增 typed disposition：

```python
formula_disposition: Literal[
    "consumed",
    "writer_rejected_not_material",
    "writer_rejected_conflict",
    "missing_from_prose",
]
```

`required` package 只有 `consumed` 才能使 Candidate complete；preferred package 可在有理由时拒绝。任何 accepted package 既未消费又无 disposition，结构出口继续 fail-closed。

### 3.5 输出分层

生成：

- `publication_candidate_method.md`：clean paper surface；
- `publication_candidate_annotated.md`：可选 debug view，只在段后添加 authority/derivation 标记；
- `publication_candidate_annotations_v1.json`：sentence/paragraph 到 facet、derivation、formula、surface mode 的权威 sidecar；
- `repository_verified_method.md`：现有 Verified splitter 结果。

Annotated view 不是终稿来源；删除标记后必须逐字得到 clean Candidate。Harness 只插入 annotation markup，不改论文句子。

### 测试

扩展：

- `tests/test_llm_section_writer.py`；
- `tests/test_agentic_publication_method_writer.py`；
- `tests/test_agentic_method_content_trace.py`；
- `tests/test_agentic_callback_semantic_contract.py`；
- `tests/test_agentic_writer_paper_language_quality.py`。

必须覆盖：

1. Writer 有正文、声明 target、无 witness 时，Binder 可闭合，不再直接把正文判无效；
2. Binder 不得返回正文中不存在或重复出现的 substring；
3. Binder 不得用一个 substring 覆盖 polarity/condition 不兼容的目标；
4. 缺正文内容回 Writer，缺 evidence 回 Research；
5. required formula exact block 被消费一次；
6. accepted-unconsumed package 阻塞 Candidate；
7. clean Candidate 不含内部审计词；
8. material mismatch 仍以一次自然差异句保留；
9. author specification 不泄漏进 Verified。

### 退出

- 三项目不再普遍产生 `declared target > 0` 且 `witnesses=[]`；
- required paragraph transaction 有真实 exact witness；
- Candidate prose 可直接作为论文草稿阅读，不像流水线审计记录。

---

## Slice 4：Candidate 与 Verified 的独立完成语义

### 4.1 新状态字段

文件：`src/code2paper/agentic/publication_method_writer.py` 的结果模型增加：

```python
candidate_completion_status: Literal[
    "not_started", "incomplete", "complete", "blocked"
]
candidate_complete: bool
verified_complete: bool
candidate_blocking_reasons: tuple[str, ...]
verified_blocking_reasons: tuple[str, ...]
```

保留：

- `candidate_generation_status` 只表示文件是否生成；
- `candidate_available` 只表示 durable candidate 是否存在；
- `candidate_validation_status` 表示 Candidate authority/surface validator；
- `verified_validation_status` 表示 Verified reverse validation；
- `publication_ready` 仍需 Verified 与质量总门共同通过。

### 4.2 Candidate complete 条件

全部满足才为 true：

1. clean Candidate durable 且 digest 匹配 checkpoint；
2. 所有 required story node 和 required paragraph 都有 substantive body；
3. 所有 required mechanism facet/field 有以下之一：
   - 合法 surface mode 并被 exact witness 绑定；
   - intent/code mismatch 被一次 material mismatch statement 表达；
   - 非核心 empirical/literature/effect 项在研究预算耗尽后进入 typed review disposition；
4. required formula 全部 accepted 且 consumed；
5. required edge/slot/condition/polarity transaction 闭合；
6. Candidate authority validator 未发现“repository statement 无 evidence”或“author specification 冒充 repository statement”；
7. 没有 unknown ID、stale digest、duplicate formula consumer、untyped empty result；
8. audit shell、heading-only、重复 pending 仍判失败。

不阻塞 Candidate complete、但阻塞 Verified/publication-ready 的典型项：

- 未提供实测性能、速度、竞争力；
- author-intent-only 公式；
- 已清楚表达的 intent/code mismatch；
- 有 typed stop reason 的外部文献或实验缺口。

阻塞 Candidate complete 的典型项：

- 核心机制段缺失；
- required 公式未生成或未消费；
- 代码与意图冲突被隐藏；
- Writer 正文没有 target witness；
- 研究仍有预算却直接用 pending 壳结束；
- accepted package 或 required target 无 typed disposition。

### 4.3 Candidate validator 与 Verified validator 分离

新增 `candidate_authority_validation_v1.json`：

- 按 sentence/span binding 检查 surface mode；
- `repository_statement` 执行 evidence closure；
- `author_specification` 检查 author facet 与禁止 Verified；
- `mismatch_statement` 检查 author + contradiction 双绑定；
- `scoped_limitation` 检查不包含未授权效果升级；
- 检查 clean surface 禁止内部 audit token。

现有 `agentic_text_evidence_validation.json`、final text claim extraction、reverse validation 与 final integrity 继续服务 Verified，不通过 Candidate validator 去放宽它们。

### 4.4 状态消费方

更新：

- `completion_report.py::_check_method_usability`；
- `readiness_report.py::_check_publication_quality_contract`；
- `runner.py` 的最终状态汇总；
- `publication_quality.py`；
- `product_authoring_graph.py`；
- `callback_semantic_contract.py`；
- `artifact_freshness.py`。

`incomplete` 不再被解释为单一的“意图与证据没有对齐”。它可能表示研究、公式、写作、binding、结构或 Verified 任何一层未闭合；必须搭配 typed reasons。用户界面优先展示：

```text
candidate: complete | incomplete | blocked
verified: complete | incomplete | blocked
publication_ready: true | false
```

### 测试

- candidate complete + verified incomplete；
- candidate generated but structurally incomplete；
- candidate mismatch expressed and typed，Candidate 可 complete、Verified 不可 complete；
- required formula unconsumed，Candidate incomplete；
- candidate author-spec sentence 不能进入 Verified；
- 旧 artifact 无新字段时按兼容规则读取，不伪造 complete。

---

## Slice 5：三项目真实回归与质量收敛

### 5.1 回归原则

1. 只给系统意图文件、冻结研究输入与真实代码仓库；
2. 不给人工候选稿、审计结论或论文答案；
3. 三项目串行运行；
4. 每次使用 fresh output directory；
5. 失败按 typed owner 修复，禁止相同代码与输入原样重复运行碰采样；
6. 生产逻辑保持项目中立；项目具体预期只在 test manifest/evaluator 中。

### 5.2 EBCAR 预期

Candidate 至少完整覆盖：

- retrieval 与输入组织；
- relative document identity 与 position encoding；
- shared/dedicated attention 的实际组合；
- query-anchor scoring、训练 objective 与 inference ranking；
- 至少一个可渲染的机制公式组，并被 canonical paragraph 消费。

必须保持为 review/mismatch，不能写成无条件正向事实：

- 性能、速度、竞争力；
- document embedding 是否实际冻结；
- train/inference mask 偏移差异；
- 测试入口变量与 checkpoint 名称问题。

代码级成功信号：required formula section 有真实 call trace；accepted/consumed 不为零；required paragraph/slot witness 闭合。

### 5.3 DyG-Mamba 预期

Candidate 至少完整覆盖：

- strict-before-time history、截断与 padding；
- node/edge/time/co-occurrence 输入；
- 时间控制量与 selective scan 的关系；
- SSM 状态参数化；
- 实际 encoder sharing、cross interaction、gated top-k readout；
- link/node task 与 loss。

不得升级为 repository statement：

- 单调/Ebbinghaus 结论；
- B/C 谱范数约束、Lipschitz、抗噪性；
- 默认未启用的 `time_mamba` 被写成实际 active path；
- independent encoder、mean pooling、线性复杂度、性能提升。

代码级成功信号：原先 route-ambiguous 的有内容公式被接受并消费；多义务映射不复制公式；active/default 状态进入 dossier。

### 5.4 LinearRAG 预期

Candidate 至少完整覆盖：

- NER、embedding normalization 与实际图顶点；
- entity-sentence 辅助映射的真实角色；
- occurrence-weighted edges、局部阈值传播、hybrid score；
- PPR、dense fallback、top-k passage 与后续 QA。

不得升级为 repository statement：

- 完整 Tri-Graph；
- 代码内 passage splitting；
- pruning/multi-hop/PPR 的效果优势；
- 经验线性扩展和 zero-LLM-token indexing cost。

代码级成功信号：已接受的 MA-S4 package 被正文消费；graph vertex 与辅助结构不再混写；required edge 有 exact witness。

### 5.5 与人工基线的比较方式

不做逐句 BLEU 或答案字符串匹配。比较以下能力：

- story stage coverage；
- code-supported slot/edge coverage；
- 公式数量、可渲染性、推导来源与消费率；
- intent/code mismatch recall；
- unsupported positive claim precision；
- clean prose 内部审计词数量；
- cross-paragraph dataflow coherence；
- Candidate editability 与 Verified leakage。

人工基线的覆盖值是质量参照：EBCAR `7/7` story、5 formula；DyG `8/8` story、9 formula；LinearRAG `7/7` story、9 formula。Code2Paper 的内部 paragraph/slot denominator 不同，不要求机械复刻数量，但不能以更细的计划制造大量义务后又全部 `witnessed=0`。

---

## 8. Prompt 合同要点

### 8.1 Research/semantic proposal

模型任务是解释 bounded dossier，不是自由总结仓库：

```text
Given one author facet and one connected repository dossier, identify the
mechanism actually executed along the active path. Separate direct operations,
static consequences, semantic interpretation, author-only intent, and
contradictions. Preserve branch conditions and defaults. Do not infer empirical
benefit, stability, robustness, complexity superiority, or guarantees from a
module name. Return only typed derivation proposals over the supplied closed IDs.
```

Harness 校验 closed IDs、dossier digest、conditions 和 ownership 后再合并。

### 8.2 Formalizer

```text
Recover the smallest reader-facing mathematical formulation that explains the
connected mechanism dossier and the author question. Abstract implementation
identifiers into conventional mathematical symbols while preserving the actual
operation order, operands, conditions, parameter sharing, and active/default
path. One package may satisfy several supplied obligations only when they share
one consumer paragraph. Return all satisfied obligation IDs explicitly. Never
upgrade an author-intent or inactive-path mechanism to code_verified, and never
add a theoretical or empirical property not licensed by the dossier.
```

Repository lane 继续检查 exact operation/number closure；author lane 允许标准数学记号，但只能形式化作者已声明内容。

### 8.3 Writer

```text
Write the planned Method paragraphs as a coherent paper section. Follow the
story order and use the connected dossier to explain inputs, transformation,
conditions, interfaces, and outputs. Insert each assigned Formalizer block
exactly once in its canonical paragraph. Use surface_mode to preserve authority
without mentioning internal audit machinery. Do not invent equations, effects,
motivations, or guarantees. Report consumed closed IDs separately; exact textual
witnesses will be bound after prose generation.
```

### 8.4 Binder

```text
For each closed target actually expressed in the frozen paragraph, copy one
exact, unique substring from the paragraph. Do not rewrite text, add claims,
paraphrase a target, or bind a target whose polarity, condition, or formula is
not present. Return unbound target IDs explicitly.
```

---

## 9. 测试与验证命令

每个 Slice 先跑相关测试；Slice 4 完成后把 full static suite 作为本执行里程碑。

```bash
python -m pytest -q \
  tests/test_agentic_formalization_guards.py \
  tests/test_agentic_formula_obligation_truths.py \
  tests/test_agentic_method_authoring_p0_closure.py \
  tests/test_agentic_intent_authoring_live_repair.py

python -m pytest -q \
  tests/test_agentic_research_derived_authoring.py \
  tests/test_llm_section_writer.py \
  tests/test_agentic_publication_method_writer.py \
  tests/test_agentic_method_content_trace.py \
  tests/test_agentic_callback_semantic_contract.py \
  tests/test_agentic_writer_paper_language_quality.py

python -m compileall -q src tests
python -m pytest -q
git diff --check
```

测试报告必须记录 exact command、exit status、代码 digest 和失败分类，不能只报 test count。

---

## 10. 真实运行协议

当前授权本地运行时：

- base URL：`http://127.0.0.1:8003/v1`；
- model：`qwen36-27b-nvfp4`；
- context：`131072`；
- profile：`tests/live/profiles/qwen36_vllm_budgeted.example.env`。

归档 latest run 中的 `8006/qwen38` 只说明当次产物 provenance，不是下一轮授权配置。

运行前记录：

```bash
curl -sS --max-time 8 http://127.0.0.1:8003/health
curl -sS --max-time 8 http://127.0.0.1:8003/v1/models
curl -sS --max-time 8 http://127.0.0.1:8003/metrics
```

不得打印或持久化密钥。记录 running/waiting、KV cache、OOM/abort 与 fresh output directory。

命令模板：

```bash
python scripts/run_authoring_replay.py \
  <frozen-root> \
  <fresh-output-root> \
  --repo <project-repository> \
  --run-id <unique-run-id> \
  --rebuild-authoring \
  --persist-authoring-rebuild-manifest \
  --profile tests/live/profiles/qwen36_vllm_budgeted.example.env \
  --callback-rounds 1 \
  --callback-tool-turns 8
```

运行顺序：EBCAR -> DyG-Mamba -> LinearRAG，串行。每个项目完成后立即执行 evaluator；若出现同一 typed failure，先修代码和静态测试，再运行下一个项目。

真实运行完成后归档至少：

- execution record 与 runtime ledgers；
- clean/annotated/Verified Method；
- dossier 与 derivation records；
- formula result、call traces、package routes；
- paragraph binding 与 transaction assessments；
- Candidate authority validation；
- Verified reverse validation；
- structural exit、quality report、evaluator report；
- code state digest、input digest、profile/model identity。

---

## 11. 最终验收门槛

### 11.1 通用 P0 门槛

- required formula consumer 的 zero-call 数为 0；
- route ambiguous 不再因“一个公式对应同段多个义务”触发；
- accepted required formula consumption rate 为 100%；
- required paragraph exact witness coverage 为 100%；
- Binder 不能把 declared ID 当证据；
- Candidate required story/mechanism coverage 为 100%，非核心外部效果项可 typed disposition；
- clean Candidate 内部流水线审计词为 0；
- material intent/code mismatch recall 为 100%；
- unmarked unsupported repository statements 为 0；
- Candidate author-spec/mismatch span 进入 Verified 的数量为 0；
- formula LaTeX 均可渲染、符号闭合、条件保留；
- candidate completion 与 verified completion 可独立报告。

### 11.2 质量门槛

三份 Candidate 应达到：

- 以机制、状态、变换和数据流为主语；代码符号只作括号级实现绑定；
- 公式前有定义、后有解释，并在同段被消费；
- 段落按 input -> transform -> condition -> output 或 problem -> mechanism -> objective -> inference 形成逻辑链；
- 不用 intended/pending/unverified 反复填充篇幅；
- 不把“缺实验证据”误写成“机制没有实现”；
- 不把“代码存在”误写成“默认路径启用”；
- 不把理论可解释性误写成性能或保证。

### 11.3 不在本轮宣称的门槛

即使三项目 Candidate complete，也不自动宣称：

- `publication_ready=true`；
- Verified 全量闭合；
- D5 完成；
- 默认 cutover；
- release freeze。

这些仍需现有 Verified、质量与发布流程独立证明。

---

## 12. 实施顺序与提交边界

按以下顺序执行，禁止把所有变化混成一个不可诊断的大提交：

1. Slice 0：观测与当前失败复现；
2. Slice 1：公式生命周期、多义务路由、消费闭环；
3. Slice 2：connected dossier 与 derivation provenance；
4. Slice 3：clean surface、V2 packet、Writer/Binder 分离；
5. Slice 4：Candidate/Verified 独立状态与 validator；
6. focused tests + full static milestone；
7. 三项目串行真实运行；
8. 根据 evaluator 做同方向局部修复；
9. 冻结新产物与执行记录。

建议提交粒度：

- commit A：diagnostics and lifecycle assertions；
- commit B：formula route and consumption；
- commit C：research dossier and derivation records；
- commit D：writer surface and paragraph binder；
- commit E：completion semantics and validators；
- commit F：tests and durable real-run artifacts。

每个提交必须保持工作树中无关用户修改，不读取或更新 `.agent` 协作文档，不修改项目专用仓库答案，不用旧基线正文填充新 Candidate。

---

## 13. 停止条件

出现以下任一情况应停止并回到架构判断：

- 为获得 clean Candidate，需要隐藏 material intent/code mismatch；
- 为让 Candidate complete，需要把 author intent 当 repository fact；
- 为接受公式，需要放松 added number/operator/condition/symbol closure；
- 为提高 coverage，需要过滤 required target 或把 empty witness 当成功；
- 为提高 support precision，需要跳过正向 claim 提取；
- Binder 开始改写正文；
- semantic derivation 直接翻转 Verified license；
- 生产代码需要写入 EBCAR、DyG-Mamba、LinearRAG 专用规则；
- 相同代码、输入和失败原因被要求重复运行以等待随机成功。

---

## 14. 完成定义

本执行手册的目标不是让系统“写得更长”，而是让它完成一次可审计的研究写作闭环：

```text
读懂作者要表达什么
  + 沿真实代码链确认实际执行什么
  + 从闭合操作推导可允许的公式和条件
  + 区分实现、规格、差异与未知
  + 写成自然、连续、可编辑的论文 Method
  + 以独立 sidecar 证明每段和每个公式从哪里来
```

只有当三个真实项目都能在不读取论文答案的条件下完成这一闭环，并且 Candidate 质量接近人工盲测基线、Verified 权威没有泄漏，才算本阶段实现完成。
