# Code2Paper：Unified Mechanism Context 架构级重构与质量闭环执行方案

> **状态**：Architecture Approved / Execution Plan Revised after Targeted Review  
> **目标分支**：`codex/agentic-p4-benchmark-cutover`  
> **审计基线 SHA**：`a7c10318e0edd554533962d1ce6159ce51751291`  
> **日期**：2026-09-05  
> **修订版本**：v2（吸收执行前架构审核；不改变 Unified Mechanism Context 主方向）  
> **适用范围**：Method 生成主链（Author Intent → Repository Research → Intent-Code Alignment → Mechanism Context → Planning/Formalization/Writing → Binder/Validator）  
> **核心目标**：在不牺牲实现忠实度与可审计性的前提下，消除多层 technical IR 的信息漏斗，使有用的 repository/author information 以 lossless evidence closure 为基础进入同一 scientific context，再由 Formalizer、Architect、Writer 分别完成数学表达、叙事组织和正文生成。

---

## 0. Executive Decision

本次仍然**不建议继续围绕现有 `MethodUnitV2 → PublicationAuthoringPacketV2 → compact_authoring_packets_v2_for_llm()` 链路做局部补丁**。当前根因已经确认是 technical information 在多个中间 IR 中被重复解释、筛选、压缩和重新授权，最终形成 systemic information loss 与 authority drift。

但 v2 对上一版方案做一个重要收紧：**`MechanismDetailV1` 不能成为新的 technical truth，更不能替代 source operation closure。** 新架构的 technical source of truth 必须是一个双层、单一 IR：

```text
MechanismContextV1
├── EvidenceClosureV1        # lossless, source-grounded, canonical
│   ├── exact spans / facts / claims / equations
│   ├── operation nodes
│   ├── call/data/control relations
│   ├── configurations + active/default path
│   └── unresolved / budget state
│
└── PaperDetailsV1           # paper-facing annotation over EvidenceClosure
    ├── D1 -> source_operation_ids [...]
    ├── D2 -> source_operation_ids [...]
    └── witness atoms / authority / publication policy
```

目标生产链调整为：

```text
                         Author Intent
                              │
                              ▼
Repository ───────→ Research / Code Analysis
                              │
                              ▼
                    Intent-Code Alignment
                              │
                              ▼
              Unified Mechanism Context Compiler
                              │
                  MechanismContextSetV1
                  ┌───────────┴───────────┐
                  │                       │
          EvidenceClosure            PaperDetails
                  │                       │
                  └───────────┬───────────┘
                              │
                  ┌───────────▼───────────┐
                  │ Mechanism Formula     │
                  │ Obligation Compiler   │
                  └───────────┬───────────┘
                              │
             ┌────────────────┴────────────────┐
             │                                 │
             ▼                                 ▼
       Mechanism Formalizer            Narrative Architect V3
             │                                 │
       FormulaPackages                    NarrativePlanV3
             │                                 │
             └────────────────┬────────────────┘
                              ▼
                            Writer V3
                              │
                              ▼
                 Detail-Atom Binder / Validator
                              │
                              ▼
                    Candidate / Verified
```

### 本次重构的最终架构决策

1. **`MechanismContextV1` 是唯一 canonical technical IR，但它内部必须同时保留 lossless `EvidenceClosure` 与 paper-facing `PaperDetails`。** Detail 是 annotation，不是 evidence replacement。
2. **所有 bounded source operations 必须有 terminal classification。** 任何 operation 都必须被 detail 吸收、标为 supporting/side-branch、或 explicit unresolved；不得因 semantic compiler 没选中而消失。
3. **Active/default execution path 是一等 contract。** “函数存在”不等于“主 Method 使用”；core promotion 必须依赖 active/default/config-selected reachability，inactive alternative 必须显式降级。
4. **Formalizer 与 Writer 对每个 mechanism 接收 byte-identical 的 shared technical payload。** 不再只比较一个模糊 `context_digest`；必须区分 source/view/slice/shared-payload/consumer-request digest。
5. **Architect 只负责“怎么讲”，不再负责“方法是什么”。** 它只产生 section/paragraph order、mechanism/detail placement、rhetorical role、depth、formula placement 与 transition。
6. **Formula technical ownership 在 Architect 之前闭合。** 新增 mechanism-owned Formula Obligation Compiler；paragraph/section 只在后续 narrative placement 阶段绑定。
7. **`MethodUnitV2` 技术内容职责取消。** 若兼容保留，只能作为 narrative pointer / legacy adapter。
8. **`PublicationAuthoringPacketV2` 与 role-specific technical compact 在 unified 路径中取消。** Legacy replay 可以暂时保留，但不能成为新路径 authority。
9. **Binder/Validator 不弱化，而是从 legacy `facet/field/slot/edge/formula` 收敛到 `detail/formula`，并在 detail 内保留 deterministic witness atoms。** 一个粗 `detail_id` 不能自动证明完整语义。
10. **Authority 拆成三轴：`claim_kind × evidence_authority × publication_policy`。** 避免把“作者给出的 rationale”与“作者声称但代码未证实的 implementation”混成同一类。
11. **原论文 / blind baseline / oracle 仍只能做 diagnostic reference。** 项目级 hard expectation 必须记录 repo snapshot、repo-verifiability、active-path status；论文结构只进入 publication-usability 评估。
12. **采用 staged cutover。** 必须先证明 WP-2 “不丢事实”，再做 WP-3 “把事实抽象成论文语义”；不能一次把 evidence closure 与 semantic abstraction 混在一个 compiler 里。
13. **效率成为正式 cutover 维度。** 先在 WP-0 冻结 token/call/callback baseline，再在 production cutover 前检查 tokens per validated core detail、calls per validated paragraph 等 Pareto 指标。
14. **三项目不是最终充分条件。** 在 legacy cleanup 前必须加入预先冻结、未参与架构调参的 cross-repository stress set。
15. **Candidate persistence + Verified fail-closed 保留。** Rich context 不能退回“自由写作 Agent”；安全从“前置删信息”迁移到“后置逐 detail/formula 验证”。

本方案的目标函数因此改为四轴：

\[
	ext{Method Quality} pprox
	ext{Faithfulness}
+ 	ext{Mechanism Recall}
+ 	ext{Narrative Coherence}
+ 	ext{Efficiency}.
\]

其中 correctness/faithfulness 是 hard constraint，recall 与 usability 是质量目标，efficiency 是 production cutover 约束。

# 1. Evidence Basis：为什么需要架构级重构

## 1.1 当前实际生产顺序与目标架构相反

对 `src/code2paper/agentic/publication_method_writer.py` 的当前生产路径审计显示：

```text
load frozen research artifacts / plan
        ↓
replan_moves_with_trace(...)               ~ line 627
        ↓
MethodUnit / SemanticArgumentFrame refresh
        ↓
build_research_mechanism_dossiers(...)     ~ line 755
        ↓
_run_section_formalizer(...)                ~ line 854
        ↓
compile_derivation_records(...)             ~ line 885
        ↓
build_publication_authoring_packets(...)    ~ line 902
        ↓
_writer_section_inputs(...)                 ~ line 1010
        ↓
section_writer compact projection
        ↓
Writer
```

也就是说，**Architect/paragraph structure 先出现，repository-derived mechanism dossier 后出现**。这使 Research Dossier 从一开始就被 paragraph/MethodUnit scope 限制，而不是先形成完整 scientific mechanism、再由 Architect组织。

目标顺序应当反转为：

```text
Brief / Facet / Alignment + Repository Research
        ↓
MechanismContext（paragraph-independent）
        ↓
Architect only organizes contexts
```

---

## 1.2 当前 Writer 前至少存在两次主要 lossy transformation

### Loss Gate A：Research / Facet Alignment → `MethodUnitV2`

`src/code2paper/agentic/method_argument_models.py:760` 的 `MethodUnitV2` 同时承担：

- reader question / purpose；
- inputs / outputs；
- ordered operations；
- conditions；
- shape / return values；
- formalizable signatures；
- evidence spans；
- fact / claim / equation IDs；
- authority；
- paragraph placement。

这实际上是**第二份 technical IR**。而 `method_architect.py` 在编译它时只稳定吸收被 selected facets / alignments 命中的部分，因此 author intent 未逐条列出的、但对论文 Method 必要的 implementation chain 容易丢失。

更进一步，当前 Architect 为降低 paragraph fragmentation 又加入了 reader-size compaction：

- 相邻 selected facets 按最多四个一组进行 grouping；
- `_method_unit_expected_sentence_range()` 将单 unit 的建议上限压到约 6 句；
-另一 paragraph planner 上限约 5 句；
- hard publication slots 通常只保留 first input、first/last transformation、first condition、first output。

这优化的是**最小可验证叙事骨架**，不是完整 paper-usable mechanism。

### Loss Gate B：`MethodUnitV2 + ResearchMechanismDossier` → `PublicationAuthoringPacketV2` → LLM compact view

`src/code2paper/agentic/research_derived_authoring.py:645` 定义 `PublicationAuthoringPacketV2`；`build_publication_authoring_packets()` 在约 line 2160 将 dossier、MethodUnit、targets、formula、config 再包装一次。

随后 `src/code2paper/llm/section_writer.py:760` 的 `_compact_authoring_packets_v2_for_llm()` 再次：

- bounded text；
- compact target；
- compact operation；
- compact MethodUnit；
- 删除 audit/private fields；
- 过滤 implementation-like text。

最关键的是当前逻辑：

```python
has_primary_operation_chain = bool(method_unit and method_unit.ordered_operations)

compact_dossier = {
    "operation_atoms": (
        [] if has_primary_operation_chain else [...]
    ),
    ...
}
```

即：**MethodUnit 只要拥有任意 primary operation，完整 dossier operation chain 就对 Writer 隐藏。**

这意味着：

```text
Research Dossier: A → B → C → D → E → F
MethodUnit:        B → D

Writer receives:  B → D
```

即使 A/C/E/F 已经被 Research 找到，Writer 也没有机会恢复。

---

## 1.3 Formalizer 当前输入明显更丰富，但仍不是可直接复用的最终统一 IR

当前 `_invoke_section_formalizer_llm()` 内部 `_claim_centered_context()` 已经非常接近正确的共享上下文：

```python
context = {
    "scientific_goal": {
        "heading",
        "paragraph_role",
        "reader_question",
        "author_claim",
        "mathematical_goal",
    },
    "implementation": {
        "exact_excerpts",
        "connected_operations",
        "preconditions",
        "shapes",
    },
    "existing_equation_atoms",
}
```

相比 Writer，它保留了更多 exact code evidence 和 connected operations。最新 replay 的输入规模也直接证明了这一点：

| Project | Formalizer 平均输入 | Writer 平均输入 | 结论 |
|---|---:|---:|---|
| DYG | ~69.6k chars / ~25.3k prompt tokens | ~5.9k chars / ~2.6k prompt tokens | 大量内容在 Writer 前被压缩 |
| LinearRAG | ~120.4k chars / ~43.4k tokens | ~8.5k chars / ~3.6k tokens | 极强的信息漏斗 |
| EBCAR | ~42.7k chars / ~15.0k tokens | ~9.6k chars / ~4.2k tokens | Writer 仍明显更薄 |

但是不能直接将 Formalizer 当前 payload 复制给 Writer，因为它仍存在：

1. **paragraph / MethodUnit 依赖**：Formalizer section facets 会受 MethodUnit contract 限制；
2. **危险 fallback**：`consumer_evidence()` 当前有：
   ```python
   return tuple(filtered) if filtered else tuple(evidence_packs)
   ```
   当 local match 失败，会把整个 section evidence 回退给当前 consumer，导致 cross-mechanism contamination；
3. **formula-oriented schema**：缺少 Writer 必需的 explicit inputs、outputs、ordered scientific steps、data-flow edges、config/default、branch semantics、downstream interface、core/support importance 等；
4. **section/paragraph ownership 过早**：公式本质应绑定 scientific mechanism/detail，而不是先绑定 paragraph。

因此，本次重构应当**上提 Formalizer context builder 的思想，而不是直接复用其当前 paragraph-scoped 实现**。

---

## 1.4 Latest replay 说明：更多 callback / retry 不是当前主解

最新 `2026-09-05/nextrepair-8006-qwen38` replay：

- DYG：`20/31` targets；callback `fulfilled=0`，`stopped=no_progress`；56 calls，约 542k total tokens；
- LinearRAG：初始 `8/27`；callback fulfilled 3 后中间结果退化到 `0/27`，最终 rollback 回 `8/27`；94 calls，约 1.23M tokens；
- EBCAR：初始 `19/26`；callback 后中间退化到 `9/27`，最终 rollback 回 `19/26`；135 calls，约 1.16M tokens。

结论：

> 当前主要瓶颈不是“模型调用次数不够”，而是 evidence scope、technical IR 和 Writer delivery contract 本身有问题。继续增加 callback 只会放大错误路由与成本。

---

# 2. Publication-Ready Method 需要保存什么信息

本节使用三类资料做**诊断**，但这些资料在生产运行中都不能成为 implementation authority：

1. 原论文 Method：只用于判断 publication-ready Method 通常包含哪些 scientific layers；
2. blind baseline：只用于证明“仅凭 author intent + repository，哪些信息理论上是可恢复的”；
3. latest replay trace：用于定位这些可恢复信息在当前 pipeline 的哪一层消失。

原论文诊断对象：

- *DyG-Mamba: Continuous State Space Modeling on Dynamic Graphs*（NeurIPS 2025；arXiv:2408.06966）；
- *LinearRAG: Linear Graph Retrieval Augmented Generation on Large-scale Corpora*（ICLR 2026；arXiv:2510.10114）；
- *Embedding-Based Context-Aware Reranker (EBCAR)*（ICLR 2026；arXiv:2510.13329）。

## 2.1 一个完整 Method mechanism 至少需要六层内容

新的 harness 必须显式表示：

```text
1. Scientific purpose / rationale
2. Inputs / representation
3. Ordered transformations / mechanism steps
4. Conditions / configurations / branches
5. Formalization / equations / notation
6. Outputs / downstream interface
```

其中 2–6 应主要由 code/repository research 产生；1 可来自 author intent、repo design evidence 或明确 external rationale，但不能从任意 implementation operation 中“脑补动机”。

---

## 2.2 Blind baseline 证明当前系统的 recall 上限远高于 Candidate

### DYG

仅代码可恢复：

- first-hop history 的 strict-before-time filter、sort、truncate/pad；
- node / edge / temporal / co-occurrence 四路输入；
- cosine temporal encoding；
- alignment；
- Mamba residual/norm、depthwise convolution、SiLU；
- selective scan；
- `A = -exp(A_log)`；
- B/C hidden-dependent path；
- source/destination interaction；
- cross-linear attention；
- gated top-k readout；
- link/node heads 与训练/评估路径。

最新 Candidate 却没有连续恢复完整的：

```text
encoding → SSM internals → selective scan → pair interaction → readout
```

特别是 `selective_scan` 已在 Formalizer evidence 中出现，却没有进入 Writer/Candidate，属于**中游 delivery loss**；`A_log` / 部分 cross interaction 在当前 route 中未稳定进入 mechanism，则属于更早的 research/context recall 问题。

### LinearRAG

blind baseline 可恢复：

```text
query entity seeds
→ entity-to-sentence propagation
→ query-sentence similarity
→ sentence-to-entity propagation
→ dynamic threshold pruning
→ active entity frontier
→ hybrid passage initialization
→ PPR
→ descending top-k
→ dense fallback / answer generation
```

最新 trace 中 `calculate_entity_scores_vectorized` 的完整函数片段和 `iteration_threshold` 已经被某些 Research/trace 工件看到；但 Stage-1 Formalizer/Writer 没拿到完整 body，反而混入 Stage-2 PPR，最终出现 Stage1=PPR 的错误公式。

这是典型的：

```text
repository evidence exists
→ route / ownership wrong
→ local evidence empty
→ section fallback
→ cross-mechanism contamination
```

而 `passage_ratio` / dense fallback 等则更接近 upstream research recall 不足。

### EBCAR

blind baseline 可恢复：

- dense retrieval / top-k；
- relative document ID 与 passage ID；
- document-id mapping；
- positional encoding；
- passage augmentation；
- unchanged query；
- shared full attention；
- dedicated same-document mask；
- mask 的 `0/-∞` 语义；
- residual + FFN；
- static query scoring anchor；
- temperature scaling；
- exact InfoNCE denominator（positive + negatives）；
- descending ranking；
- training/inference discrepancy。

当前 Formalizer evidence 中实际已经见到：document-id code、mask block、`torch.logsumexp(all_sims, dim=0)`、argsort 等；Writer 只保留高度概括的版本，InfoNCE 甚至在 fallback 后被写错。

---

## 2.3 现有 oracle_writer fixture 已经证明“Writer 模型能力”不是主瓶颈

`tests/fixtures/method_synthesis_funnel/baselines_v1.json` 中冻结的 LinearRAG 漏斗对比具有关键意义：

- 现有 restrictive product 路径：available 43 → compiled/bound → delivered 16 → used 8；Stage1 used 0/14；
- binding-only：used 14；Stage1 4/14；
- oracle_writer（同类 Writer 模型，但减少 FAC/L0/中间限制）：used 14；Stage1 11/14，mean realization ~3.5。

这说明：

> **Writer 并不是因为模型不会理解代码而写不完整；主要问题是 Writer 没被交付足够完整、正确分区的 technical context。**

因此这次重构必须优先解决 data path，而不是继续在 prompt 上打补丁。

---

# 3. Root Cause Taxonomy：信息到底在哪里丢

未来所有诊断都应将缺失分为以下五类，不能再统一归因于“evidence insufficient”：

| Loss Type | 定义 | 典型例子 | 责任层 |
|---|---|---|---|
| R0 Discovery Miss | repository research 根本未发现 | DYG `A_log` 某些路径；LinearRAG `passage_ratio` | Research |
| R1 Mechanism Routing Miss | 找到但归错 mechanism / 未进入目标 mechanism | LinearRAG threshold body 未进入 Stage1 | Context Compiler |
| R2 IR Compression Loss | mechanism 中有，但转换到 MethodUnit/slots 时消失 | EBCAR mask details | 当前 Architect / MethodUnit |
| R3 Writer Delivery Loss | 上游 IR 有，但 Writer-visible projection 删除 | selective_scan / dossier shadowing | AuthoringPacket / compact projection |
| R4 Rendering Loss | Writer 收到但正文没写/写错 | 某些 config/detail/公式 | Writer / Binder |

新的 trace 必须能分别度量 R0–R4，而不是只给最终 `required_target_coverage`。

---

# 4. Non-Negotiable Design Invariants

## I1. One Canonical Technical IR, Two Internal Layers

`MechanismContextV1` 是唯一 canonical technical IR，但**不是只有 `MechanismDetail` 一层**。它必须包含：

```text
EvidenceClosureV1  = source-grounded truth / exact closure
PaperDetailsV1     = paper-facing annotation over that closure
```

禁止：

```text
source operations
→ semantic compiler
→ Detail
→ discard source operations
```

正确：

```text
source operations ───────────────┐
                                │
              semantic annotation│
                                ▼
EvidenceClosureV1 ←────── PaperDetailsV1
```

`PaperDetails` 可以变化、重编、重分组；`EvidenceClosure` 不得因叙事变化而改变 source membership。

## I2. Mechanism Identity Must Be Paragraph-Independent

`mechanism_id`、`detail_id`、`source_operation_id` 不得包含：

- section index；
- paragraph index；
- Writer retry number；
- consumer paragraph ID。

论文结构可以变化，但 scientific mechanism identity 与 source closure identity 不应变化。

## I3. Lossless Source-Operation Closure

对于 compiler 已纳入一个 bounded mechanism closure 的 source operations：

```text
source_operation_terminal_coverage == 1.0
```

每个 operation 必须落入且只落入一个 terminal state：

```text
absorbed_by_detail
classified_supporting
classified_side_branch
explicitly_unresolved
```

`semantic compiler cannot alter source membership`。

对 repository-derived `implementation/interface/formalization` detail：

```text
source_operation_ids != empty
OR source_fact/span/equation closure is explicitly sufficient
```

例外：`author_intent_only` 的 rationale/specification 可以没有 repository operation，但必须绑定 author facet/brief/obligation，并且 publication policy 不能伪装成 repository implementation。

## I4. Active-Path Precedence

**Definition existence is not execution evidence.** 任何 implementation detail 不能仅因为函数/类存在就成为 mainline/core。

Core implementation detail 必须满足至少一项：

1. reachable from resolved active/default execution path；
2. explicitly selected by author/runtime configuration；
3. typed as a conditional path whose condition is part of the Method；
4. shared interface/representation that is actually consumed by an active core path。

否则必须标记为：

```text
inactive
conditional_alternative
unreachable
unknown
```

并默认不得升级为 main Method spine。

## I5. Architect Cannot Create Technical Facts

Architect 的 technical output 只能引用已有：

- `mechanism_id`；
- `detail_id`；
- `formula_package_id` / `formula_obligation_id`。

任何无法在 `MechanismContextSetV1` / Formula package set 中解析的 ID 都必须 fail-closed。

Architect 可以创建：heading、paragraph order、rhetorical role、transition、depth、placement；不能创建 operation/condition/formula semantics。

## I6. All Core Details Must Remain Consumer-Visible

对 `importance=core` 且 `publication_policy=clean_candidate` 的 detail：

- 100% 必须进入 shared consumer technical view；
- Formalizer/Writer 不能各自做 technical deletion；
- 不允许因 token compaction、paragraph budget、MethodUnit grouping 静默删除。

若预算不足：必须 explicit slice 或 typed `context_budget_exhausted`，不能截断后继续声称 context 完整。

## I7. No Scope-Widening Fallback

禁止：

```python
local_evidence or whole_section_evidence
```

正确行为：

```text
mechanism-local evidence empty
→ unresolved mechanism/detail
→ optional targeted research callback
→ never import sibling mechanism evidence
```

此条必须是 hard invariant，不是 warning。

## I8. Shared Context Must Be Provably Identical

不能只记录一个 `context_digest`。每个 mechanism 必须至少有：

```text
source_context_digest      # full MechanismContext canonical bytes
view_digest                # deterministic consumer-neutral view
slice_digest               # each serialized slice
shared_payload_digest      # ordered exact slices actually delivered
consumer_request_digest    # full role-specific request incl. task
```

对任何 Formalizer 与 Writer 都消费的 mechanism：

```text
Formalizer.shared_payload_digest == Writer.shared_payload_digest
Formalizer.core_detail_ids       == Writer.core_detail_ids
```

`consumer_request_digest` 允许不同，因为 task instruction / narrative plan / formula package 不同；**shared technical payload bytes 不允许不同**。

## I9. Authority Is Three-Dimensional

不再用单一 `DetailAuthority` 表达全部语义。必须拆成：

```text
claim_kind:
  implementation | rationale | specification | interface |
  limitation | formalization | empirical

evidence_authority:
  repository_verified | repository_partial | author_intent_only |
  mismatch | unresolved

publication_policy:
  clean_candidate | annotated_only | review_only | omit
```

例如：

```text
author rationale:
  claim_kind=rationale
  evidence_authority=author_intent_only
  publication_policy=clean_candidate   # 可以合法写成“we design ... to ...”

unsupported implementation assertion:
  claim_kind=implementation
  evidence_authority=author_intent_only
  publication_policy=annotated_only/review_only
```

这样避免把 DYG 一类 author rationale/aspiration 错升格为 implementation fact。

## I10. Detail-Level Validation Must Remain Atomic

Writer 可以只 self-report `detail_id`，但 Binder 不能因此把整个 detail 视为已证明。

每个 `MechanismDetailV1` 必须有 deterministic `witness_atoms`。Required detail 只有在所有 required witness atoms 被正文中的一个或多个唯一 prose/formula span 覆盖后才算 valid。

## I11. Original Paper / Blind Baseline Never Authorize Runtime Claims

原论文、oracle、blind baseline 只能用于：

- offline evaluation；
- diagnostic fixture；
- architecture validation；
- publication-usability reference。

任何 project fixture 的 expected unit 都必须携带：

```yaml
source: current_repo_trace | blind_code_audit | paper_structure_reference
repo_snapshot_sha: ...
repo_verifiable: true | false
active_path_status: active | conditional | inactive | unknown
runtime_authority: diagnostic_non_authorizing
```

真正 cutover hard gate 只可以使用 `repo_verifiable=true` 的 repo-derived expectation，并要求 active/conditional/inactive semantics 正确表达。论文结构 reference 不能成为 runtime compiler 规则。

## I12. Candidate Persistence, Verified Fail-Closed

- Candidate 可以在不完整时持久化；
- Verified 仍需 evidence/authority/witness/formula 全闭合；
- Binder fail 不删除 Candidate；
- unsupported/review-required formula 不进入 clean Verified。

## I13. Output Validation Happens After Information Preservation

顺序必须是：

```text
high-recall evidence closure
→ paper-facing detail annotation
→ shared technical delivery
→ Writer generation
→ deterministic Binder/authority/formula validation
```

禁止回到：

```text
为了防 hallucination
→ 先删掉大部分 source information
→ Writer 只能写很薄的 Method
```

## I14. Every Loss Is Observable

所有 technical units 具有 lifecycle：

```text
discovered
→ closed_in_evidence
→ annotated_as_detail/support/side/unresolved
→ projected
→ delivered_to_consumer
→ placed
→ rendered
→ witnessed
→ validated
```

任意阶段丢失必须能定位到 R0–R4，不允许只有最终 coverage 数字。

## I15. Shared / Secondary Ownership Is Explicit

一个 canonical detail 有且只有一个 `primary_mechanism_id`；但允许：

```text
shared_interface
shared_representation
secondary_consumer
```

其他 mechanism 通过 `SharedDetailRefV1` 引用该 canonical detail，不复制第二份技术事实，也不把 shared representation 强行塞进两个独立 detail。

## I16. Efficiency Is a Cutover Dimension, Not a Correctness Shortcut

效率不得通过 silent truncation 换取。WP-0 必须冻结：

```text
total_tokens_per_candidate
tokens_per_validated_core_detail
calls_per_validated_paragraph
callback_token_fraction
formalizer_input_tokens
writer_input_tokens
```

WP-9 前必须预先声明 production budget/tolerance；不能看到结果后再移动阈值。若质量提高但成本显著退化，必须显式 waiver，而不是默认 cutover。

# 5. Target Data Model

目标不是新增更多互相复制的 IR，而是建立**一个 canonical `MechanismContextV1`，内部同时保存 source closure 与 paper abstraction**。

## 5.1 `MechanismSeedV1`：intent/alignment → repository mechanism 的窄入口

```python
class MechanismSeedV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    seed_id: str
    story_node_ids: tuple[str, ...] = ()
    brief_ids: tuple[str, ...] = ()
    facet_ids: tuple[str, ...] = ()
    obligation_ids: tuple[str, ...] = ()

    author_statements: tuple[str, ...] = ()
    semantic_fields: tuple[dict[str, Any], ...] = ()

    bound_fact_ids: tuple[str, ...] = ()
    bound_claim_ids: tuple[str, ...] = ()
    bound_span_ids: tuple[str, ...] = ()
    bound_equation_ids: tuple[str, ...] = ()
    search_terms: tuple[str, ...] = ()

    formula_expectations: tuple[str, ...] = ()
    content_digest: str
```

Seed 只允许由已有、可审计对象产生：`MethodArgumentBriefV1`、`AuthorMechanismFacetV1`、field-level alignment、deterministic licenses、semantic stage groups、story spine exact links。Generic lexical overlap 不能合并 seed。

---

## 5.2 `MechanismEvidenceClosureV1`：lossless technical foundation

这是 v2 中最重要的新 contract。它保存**compiler 已纳入当前 mechanism scope 的完整 source-level closure**，不能被 paper abstraction 替代。

```python
ActivePathStatus = Literal[
    "active_default",
    "active_selected",
    "conditional",
    "inactive_default",
    "unreachable",
    "unknown",
]

class EvidenceOperationV1(BaseModel):
    operation_id: str
    symbol_id: str = ""
    predicate: str
    operands: tuple[str, ...] = ()
    result: str = ""
    guard: str = ""
    source_span_id: str
    relation_ids: tuple[str, ...] = ()
    active_path_status: ActivePathStatus = "unknown"
    activation_basis_ids: tuple[str, ...] = ()
    exact_excerpt: str = ""

class SourceOperationDispositionV1(BaseModel):
    operation_id: str
    disposition: Literal[
        "absorbed_by_detail",
        "classified_supporting",
        "classified_side_branch",
        "explicitly_unresolved",
    ]
    detail_ids: tuple[str, ...] = ()
    reason_code: str = ""

class MechanismEvidenceClosureV1(BaseModel):
    closure_id: str
    mechanism_id: str

    entry_symbol_ids: tuple[str, ...] = ()
    operation_nodes: tuple[EvidenceOperationV1, ...] = ()
    call_relation_ids: tuple[str, ...] = ()
    data_flow_relation_ids: tuple[str, ...] = ()
    control_flow_relation_ids: tuple[str, ...] = ()

    configuration_bindings: tuple[dict[str, Any], ...] = ()
    active_path_conditions: tuple[str, ...] = ()
    default_activation: ActivePathStatus = "unknown"

    fact_ids: tuple[str, ...] = ()
    claim_ids: tuple[str, ...] = ()
    equation_ids: tuple[str, ...] = ()
    exact_span_ids: tuple[str, ...] = ()
    exact_excerpts: tuple[str, ...] = ()
    source_digests: dict[str, str] = {}

    shape_or_type_hints: tuple[str, ...] = ()
    return_value_descriptors: tuple[str, ...] = ()
    unresolved_items: tuple[str, ...] = ()

    operation_dispositions: tuple[SourceOperationDispositionV1, ...] = ()
    source_operation_terminal_coverage: float
    budget_exhausted: bool = False
    content_digest: str
```

### Closure invariants

```text
set(disposition.operation_id) == set(operation_nodes.operation_id)
source_operation_terminal_coverage == 1.0
```

Semantic compiler 只能标注/分组 operations，不能从 closure 中删除 operation。

---

## 5.3 `DetailWitnessAtomV1`：detail 内部的 deterministic atomic contract

```python
WitnessAtomKind = Literal[
    "operation",
    "operand",
    "output",
    "condition",
    "polarity",
    "interface",
    "formal_relation",
]

class DetailWitnessAtomV1(BaseModel):
    atom_id: str
    atom_kind: WitnessAtomKind
    semantic_anchor: str
    required: bool = True
    source_operation_ids: tuple[str, ...] = ()
    source_anchor_ids: tuple[str, ...] = ()
    exact_excerpts: tuple[str, ...] = ()
    required_conditions: tuple[str, ...] = ()
    required_polarity: str = "unknown"
```

这些 atoms 由 Harness 在 detail compile 后**deterministically derive / validate**；LLM 可以提议 paper semantics，但不能自行声明某个未绑定语义已经被证明。

---

## 5.4 `MechanismDetailV1`：EvidenceClosure 上的 paper-facing annotation

`MechanismDetailV1` 是 Writer/Formalizer/Architect 使用的最小 paper-meaningful unit，但**不是 source truth replacement**。

```python
DetailRole = Literal[
    "input", "representation", "transformation", "condition",
    "configuration", "branch", "output", "interface",
    "training_objective", "inference", "rationale", "limitation",
]

DetailImportance = Literal["core", "supporting", "side_branch"]

ClaimKind = Literal[
    "implementation", "rationale", "specification", "interface",
    "limitation", "formalization", "empirical",
]

EvidenceAuthority = Literal[
    "repository_verified", "repository_partial", "author_intent_only",
    "mismatch", "unresolved",
]

PublicationPolicy = Literal[
    "clean_candidate", "annotated_only", "review_only", "omit",
]

class MechanismDetailV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    detail_id: str
    primary_mechanism_id: str
    shared_with_mechanism_ids: tuple[str, ...] = ()
    order_index: int

    role: DetailRole
    importance: DetailImportance
    claim_kind: ClaimKind
    evidence_authority: EvidenceAuthority
    publication_policy: PublicationPolicy

    semantic_atom: str
    subject: str = ""
    predicate: str = ""
    operands: tuple[str, ...] = ()
    result: str = ""
    conditions: tuple[str, ...] = ()
    polarity: str = "unknown"
    shape_or_type_hints: tuple[str, ...] = ()

    active_path_status: ActivePathStatus = "unknown"
    activation_basis_ids: tuple[str, ...] = ()

    predecessor_detail_ids: tuple[str, ...] = ()
    successor_detail_ids: tuple[str, ...] = ()

    # Annotation must bind back to closure.
    source_operation_ids: tuple[str, ...] = ()
    source_fact_ids: tuple[str, ...] = ()
    source_claim_ids: tuple[str, ...] = ()
    source_span_ids: tuple[str, ...] = ()
    source_equation_ids: tuple[str, ...] = ()
    exact_excerpts: tuple[str, ...] = ()

    source_facet_ids: tuple[str, ...] = ()
    source_brief_ids: tuple[str, ...] = ()
    source_obligation_ids: tuple[str, ...] = ()
    author_statements: tuple[str, ...] = ()
    mismatch_reason: str = ""

    formalizable: bool = False
    formula_role: str = ""
    formalizable_signatures: tuple[dict[str, Any], ...] = ()

    witness_atoms: tuple[DetailWitnessAtomV1, ...] = ()
    content_digest: str
```

### Detail validators

- `repository_verified/repository_partial` implementation/interface/formalization details 必须绑定 closure 中的 source operation/fact/span/equation；
- `author_intent_only` rationale/specification 可以没有 operation，但必须有 source facet/brief/obligation；
- `active_path_status in {inactive_default, unreachable}` 时，默认 `importance != core` 且 `publication_policy != clean_candidate`，除非 author explicit configuration 选择该 branch；
- `shared_with_mechanism_ids` 只建立 secondary reference，canonical detail 仍只有一个 primary owner；
- `witness_atoms` 的 source IDs 必须是 detail source closure 的子集。

### 为什么 `Detail` 仍比 `SemanticFlowSlot` 合适

`Detail` 仍按 paper-meaningful 粒度定义，但 v2 明确：它只是 EvidenceClosure 的 annotation。删除一个 detail 会损失论文解释层；删除 closure operation 会损失技术事实层。这两个层次不能再混为一谈。

---

## 5.5 `MechanismEdgeV1` 与 shared ownership

```python
class MechanismEdgeV1(BaseModel):
    edge_id: str
    mechanism_id: str
    source_detail_id: str
    target_detail_id: str
    relation: Literal[
        "feeds", "conditions", "branches_to", "produces",
        "consumes", "contrasts_with", "precedes",
    ]
    source_relation_ids: tuple[str, ...] = ()
    source_span_ids: tuple[str, ...] = ()
    content_digest: str

class SharedDetailRefV1(BaseModel):
    detail_id: str
    primary_mechanism_id: str
    consumer_mechanism_id: str
    role: Literal["shared_interface", "shared_representation", "secondary_consumer"]
```

共享表示不复制第二份 detail/source truth；secondary mechanism 只持有 reference。

---

## 5.6 `MechanismContextV1`

```python
class MechanismContextV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    mechanism_id: str
    mechanism_name: str

    scientific_role: str
    reader_question: str
    purpose: str
    importance: Literal["core", "supporting", "side_branch"]

    story_node_ids: tuple[str, ...] = ()
    brief_ids: tuple[str, ...] = ()
    facet_ids: tuple[str, ...] = ()
    obligation_ids: tuple[str, ...] = ()
    author_statements: tuple[str, ...] = ()
    notation_hints: tuple[str, ...] = ()

    evidence_closure: MechanismEvidenceClosureV1

    input_detail_ids: tuple[str, ...] = ()
    ordered_detail_ids: tuple[str, ...] = ()
    output_detail_ids: tuple[str, ...] = ()
    details: tuple[MechanismDetailV1, ...] = ()
    edges: tuple[MechanismEdgeV1, ...] = ()
    shared_detail_refs: tuple[SharedDetailRefV1, ...] = ()

    formalizable_signatures: tuple[dict[str, Any], ...] = ()
    contradiction_ids: tuple[str, ...] = ()
    unresolved_items: tuple[str, ...] = ()

    context_readiness: Literal[
        "repository_ready", "intent_ready", "partial", "blocked"
    ]
    readiness_failures: tuple[str, ...] = ()
    budget_exhausted: bool = False

    source_context_digest: str
```

### 关键约束

- `section_id` / `paragraph_id` 不属于 context；
- `source_context_digest` 由 canonical EvidenceClosure + PaperDetails 生成，不受 paragraph reordering 影响；
- re-running PaperDetail compiler 可产生新的 `paper_detail_digest`，但不能悄然改变 EvidenceClosure membership；
- all core details 必须能从 `ordered_detail_ids` 完整解析；
- context 不依赖 Architect technical regeneration。

---

## 5.7 `MechanismContextSetV1`

```python
class MechanismContextSetV1(BaseModel):
    schema_version: str = "1.0"
    repo_snapshot_id: str
    project_tree_hash: str
    intent_digest: str
    alignment_digest: str
    research_digest: str

    contexts: tuple[MechanismContextV1, ...]
    unresolved_seed_ids: tuple[str, ...] = ()
    compiler_diagnostics: tuple[dict[str, Any], ...] = ()

    content_digest: str
```

Artifact：

```text
artifacts/06_authoring/mechanism_contexts_v1.json
```

它应成为 Research/Alignment 与 Authoring 的稳定边界，而不是 Writer-only 临时 artifact。

# 6. Shared LLM Context：Formalizer 与 Writer 真正共享什么

两个 consumer 不能分别“从同一 context 自己 compact”，否则仍会产生第二套技术世界。因此只允许一个 deterministic projection：

`src/code2paper/agentic/mechanism_context_projection.py`

## 6.1 Digest hierarchy

```python
class MechanismContextViewV1(BaseModel):
    mechanism_id: str
    scientific_goal: dict[str, Any]
    author_intent: dict[str, Any]
    ordered_details: tuple[dict[str, Any], ...]
    edges: tuple[dict[str, Any], ...]
    configurations: tuple[dict[str, Any], ...]
    exact_evidence: tuple[dict[str, Any], ...]
    unresolved_items: tuple[str, ...]

    source_context_digest: str
    view_digest: str

class MechanismContextSliceV1(BaseModel):
    mechanism_id: str
    slice_index: int
    detail_ids: tuple[str, ...]
    exact_evidence_ids: tuple[str, ...]
    view_digest: str
    slice_digest: str
```

每次 consumer call 还必须持久化：

```text
shared_payload_digest
consumer_request_digest
core_detail_ids
slice_digests
```

定义：

- `source_context_digest`：full `MechanismContextV1` canonical serialization；
- `view_digest`：consumer-neutral reader/scientific projection；
- `slice_digest`：一个 exact serialized slice；
- `shared_payload_digest`：按稳定顺序拼接、实际送入模型的所有 shared slices；
- `consumer_request_digest`：shared payload + role-specific task 的整个 request。

## 6.2 Byte-identical shared technical payload

Formalizer：

```json
{
  "shared_context": <exact shared slices>,
  "task": {
    "type": "formalize",
    "formula_obligation_ids": ["..."]
  }
}
```

Writer：

```json
{
  "shared_contexts": [<the exact same per-mechanism shared slices>],
  "narrative_plan": {...},
  "formula_packages": [...],
  "task": {"type": "write_method"}
}
```

对 Writer/Formalizer 都涉及的 mechanism：

```text
shared payload bytes identical
shared_payload_digest identical
core_detail_ids identical
slice_digests identical and ordered identically
```

role-specific instruction、NarrativePlan、FormulaPackage 是**shared payload 外的附加信息**，不能修改 shared technical facts。

## 6.3 No role-specific technical deletion

可以不同：

- Formalizer task；
- Writer paragraph plan；
- Writer 收到的 formula output；
- response schema。

不能不同：

- core detail set；
- active/default path semantics；
- conditions/polarity；
- source evidence membership；
- shared exact evidence slices。

## 6.4 Context size control

正确顺序：

1. mechanism-level isolation；
2. all core details always present；
3. supporting/side branch按 typed policy；
4. explicit slices；
5. budget exhaustion typed failure。

初版：

```python
MAX_CORE_DETAILS_PER_MECHANISM = None
MAX_SUPPORTING_DETAILS_PER_SLICE = 24
MAX_EXACT_EXCERPT_TOKENS_PER_SLICE = 12_000
MAX_MECHANISM_SLICES = 4
```

这些是 resource caps，不是 semantic completeness caps。触发 cap 时：

- EvidenceClosure 不变；
- core semantic rows + source handles 不变；
- exact excerpts按 detail/slice 分块；
- 若仍无法把全部 core slice 送给两个 consumer，则 `context_budget_exhausted`；
- 禁止替换成 sibling/whole-section evidence。

## 6.5 Projection-level hard tests

至少包含：

```text
same_context_same_view_bytes
same_view_same_slice_bytes
formalizer_writer_same_shared_payload_bytes
formalizer_writer_same_core_detail_ids
role_specific_task_does_not_change_shared_payload_digest
slice_reorder_changes_payload_digest_and_is_rejected
```

# 7. Unified Mechanism Context Compiler

建议新增：

`src/code2paper/agentic/mechanism_context_compiler.py`

它复用 `research_derived_authoring.py` 中成熟的 exact-ID closure / graph walk / config extraction / fact-chain 能力，但**分成两个严格阶段：WP-2 先闭合 source evidence；WP-3 再做 paper abstraction**。

## 7.1 Compiler API

```python
def compile_mechanism_contexts(
    *,
    argument_briefs: MethodArgumentBriefSetV1,
    facets: Iterable[AuthorMechanismFacetV1],
    facet_alignments: Iterable[FacetEvidenceAlignmentV1],
    field_candidates: Iterable[PublicationFieldCandidateV1],
    story_spine: Iterable[AuthorStoryNodeV1],
    facts: CodeFactSetV1,
    claims: AtomicClaimSetV3,
    equations: EquationClaimSetV1,
    configurations: ConfigurationClaimSetV1,
    evidence_packets: EvidencePacketSetV3,
    behavior_graph: CodeBehaviorGraphV1 | None,
    implementation_scope: ImplementationScopeV1 | None,
    symbol_index: SymbolIndexV2 | None,
    source_provider: SourceProvider | None,
) -> MechanismContextSetV1:
    ...
```

这里没有 `plan / section_id / paragraph_id / MethodUnit`。

---

## 7.2 Stage A：Mechanism seed construction

Author story / brief 是 organization prior，不是最终 detail 限制。流程：

```text
facet/brief
→ exact aligned spans/facts/symbols
→ connected implementation closure
→ discover additional implementation details
```

两个 seed 只有满足 exact evidence/graph/producer-consumer/explicit mechanism key 等闭合条件才可合并；generic lexical overlap 不授权合并。

---

## 7.3 Stage B：Lossless evidence closure

这是 **WP-2 correctness core**。

### B1. Exact-ID fact/claim/equation closure

复用：

- exact span → facts；
- fact → direct/relation spans；
- fact → claim IDs；
- claim → fact/equation/contradiction IDs；
- equation → fact/span IDs；
- `compile_code_fact_operation_chain()`。

所有扩展必须基于 exact identity / typed graph relation；自然语言相似度只可用于 search priority，不能授予 authority。

### B2. Behavior graph closure

复用 `_graph_parts()`、`_node_anchor_ids()`、`_shortest_connected_subgraph()`、CALL/DATA/CONTROL classification，但 seed owner 改为 `MechanismSeedV1`。

无 exact seed 时：

```text
behavior_subgraph_unresolved
```

不允许 whole-graph / whole-section fallback。

### B3. Graph absence 不自动失败

若 CodeFact chain 本身 source-ordered、formalizable、exact-source closed，则 graph 可以是 optional provenance lane；不能为了追求 graph completeness 重新扩大 mechanism scope。

---

## 7.4 Stage C：DefinitionResolver + bounded source expansion

当前 callee expansion 失败的根因是只在“已经进入 evidence 的 span 集”里找 definition。必须改为：

```text
callee symbol
→ SymbolIndexV2
→ exact SymbolRef(path, qualified_name, start_line, end_line)
→ SourceProvider read exact definition body
→ PythonBehaviorAdapter.extract_operations
→ same EvidenceClosure
```

查找顺序：

1. exact `target_symbol_id`；
2. exact `(path, qualified_name)`；
3. globally unique qualified-name tail；
4. unresolved，never guess。

预算建议：

```text
max_call_depth = 2
max_callee_definitions = 6
max_source_lines_per_definition = 120
```

触发 cap 只会产生 `budget_exhausted/unresolved`；不能把未读 body 当已发现。

**重要**：DefinitionResolver 能找到函数 body ≠ 该函数自动成为 mainline。它只补全 EvidenceClosure，是否 core 由 active-path resolution 决定。

---

## 7.5 Stage D：Active/default execution path resolution

该阶段必须发生在 core/support classification 之前。

输入：

- resolved entry symbols；
- function/class defaults；
- entrypoint CLI/config overrides；
- `CONFIGURED_BY` / branch guards；
- author explicitly selected configuration；
- call/data/control reachability。

输出每个 source operation / branch 的：

```text
active_default
active_selected
conditional
inactive_default
unreachable
unknown
```

### D1. Precedence

```text
actual entrypoint override
> explicit run configuration
> function/default configuration
> symbol existence
```

### D2. Mainline rule

- `active_default / active_selected`：可成为 core；
- `conditional`：只有 condition 对 scientific behavior material 时可进入 core，正文必须写 condition；
- `inactive_default`：默认 supporting/alternative，不得因论文/oracle/函数名而提升；
- `unreachable`：side branch / audit；
- `unknown`：不能进入 repository-verified core，必要时 callback。

LinearRAG 的 vectorized path 和 DYG 的 config-controlled branches 都必须由此规则处理，而不是项目特判。

---

## 7.6 Stage E：Freeze `MechanismEvidenceClosureV1`

在任何 semantic Detail compiler 调用前，先持久化：

```text
mechanism_evidence_closures_v1.json
```

并计算：

```text
closure source operation count
exact span/fact/relation coverage
active-path classification coverage
unresolved relation count
budget exhaustion
```

**WP-2 的 Gate 不看论文写得好不好，只看“有用事实有没有被 closure 保存”。**

---

## 7.7 Stage F：Operation cluster → PaperDetail annotation

这是 **WP-3 abstraction core**，与 WP-2 必须分开。

### F1. Deterministic cluster proposal

按 producer-consumer、callee boundary、branch/config、return/output、formula-worthy multi-op chain、data-structure construction→use 等边界形成 bounded clusters。

### F2. Low-temperature semantic annotation

LLM 输入：

```text
bounded operation cluster
+ author intent context
+ active-path state
```

LLM 只能返回 supplied ordinal operation indices 与 reader-facing semantics，例如：

```json
{
  "role": "transformation",
  "semantic_atom": "propagate active entity weights to associated sentences",
  "predicate": "propagate",
  "operands": ["active entity weights", "linked sentences"],
  "result": "sentence scores",
  "conditions": ["entity score >= iteration_threshold"],
  "source_operation_indices": [0, 1, 2]
}
```

Harness 再映射到 exact `source_operation_ids/fact/span`。

### F3. Semantic compiler cannot alter membership

- 它不能新增 source operation；
- 不能把 cluster 外 operation 绑定进 detail；
- 不能因为没有生成某个 detail 就删除 operation；
- 任何未吸收 operation 必须 terminal-classified。

---

## 7.8 Stage G：Witness atom compiler

Detail 生成后，Harness 产生 deterministic atomic obligations：

- transformation → operation atom；
- material inputs/operands → operand atoms；
- produced/returned value → output atom；
- branch/filter/mask/threshold → condition + polarity atoms；
- cross-component boundary → interface atom；
- formal relation → formal_relation atom。

LLM 可以提供 reader-facing wording suggestion，但 required/optional 与 source binding 由 Harness 决定。

一个 detail 可以由多句共同完成 witness；不得要求“一句话覆盖全部”。

---

## 7.9 Stage H：Importance + three-axis authority/policy

### Core

只有满足 active-path precedence 且属于以下之一才可 core：

1. author mainline + repository-supported mechanism；
2. active entry→primary output chain；
3. material representation/state/score/retrieval transformation；
4. material active/conditional branch；
5. training objective / inference scoring；
6. required downstream interface；
7. 缺失后 producer/consumer chain 断裂。

### Supporting

shape、normalization、default config、reproducibility helper、inactive alternative 等。

### Side-branch

logging/debug/serialization/evaluation-only/case-study/ablation-only/unreachable helper。

### Three-axis policy

`claim_kind`、`evidence_authority`、`publication_policy` 独立计算。特别是：

```text
author rationale != unsupported implementation
```

前者可是 clean Candidate 的 author-side framing；后者只能 annotated/review/omit，除非 repository closure 支持。

---

## 7.10 Stage I：Ownership / contamination checks

每个 canonical detail 有一个 primary mechanism，允许 shared references：

```text
primary owner
+ shared_interface/shared_representation/secondary_consumer refs
```

检查：

- sibling mechanism operator contamination；
- Stage1 引入 Stage2-only operator；
- training objective 混入 inference；
- inactive/evaluation branch 被提升 core；
- formula operands来自其他 mechanism；
- duplicated shared detail with inconsistent source closure。

建议错误码：

```text
mechanism_detail_invalid_primary_owner
shared_detail_source_divergence
cross_mechanism_operator_import
cross_stage_dataflow_gap
inactive_path_promoted_to_core
unresolved_shared_interface
```

---

## 7.11 Stage J：Final closure audit

在输出 `MechanismContextSetV1` 前必须满足：

```text
source_operation_terminal_coverage == 1.0
repository_detail_source_binding_rate == 1.0
active_path_unclassified_core_count == 0
unknown_source_operation_ids == 0
shared_detail_source_divergence == 0
```

若任何一项失败，context 可持久化为 diagnostic/partial，但不得标记 `repository_ready`。

# 8. Narrative Method Architect V3

## 8.1 Architect 的职责必须大幅收窄

新的 Architect 输入：

```text
Author story spine
+
MechanismContextSetV1 的 reader-facing summary / detail metadata
```

输出：

```text
NarrativePlanV3
```

它不再接触 raw code facts 来重建 operation frame。

---

## 8.2 `NarrativeUnitV1` / `MethodUnitV3`

```python
class NarrativeUnitV1(BaseModel):
    unit_id: str
    section_id: str

    mechanism_context_ids: tuple[str, ...]
    rhetorical_role: str
    reader_question: str

    paragraph_ids: tuple[str, ...]
    required_detail_ids: tuple[str, ...]
    optional_detail_ids: tuple[str, ...]
    formula_obligation_ids: tuple[str, ...]

    suggested_depth: Literal["brief", "standard", "detailed"]
    transition_from: str = ""
    transition_to: str = ""

    content_digest: str
```

不再包含：

```text
ordered_operations
facts
claims
exact_spans
formalizable_signatures
shape_hints
return values
```

这些只存在于 `MechanismContext`。

---

## 8.3 Paragraph planning 不再使用“4 facets / 5–6 sentences”机械压缩

新的 paragraph split 应按 scientific step complexity：

```text
overview / representation
core transformation chain
formalization / objective
output / interface
```

例如一个 mechanism 若包含：

```text
input
→ representation
→ transform A
→ transform B
→ condition
→ transform C
→ output
```

Architect 可以计划 2–3 paragraphs，而不是强制一段六句话。

### Suggested depth heuristic

```python
complexity = (
    1.0 * core_transform_count
    + 0.7 * material_condition_count
    + 0.8 * formula_obligation_count
    + 0.5 * interface_count
)

if complexity <= 3: brief
elif complexity <= 7: standard
else: detailed
```

这是 planning hint，不是 correctness truncation。

---

## 8.4 Required details 不再只取 first/last transformation

原则：

- 所有 `importance=core` 且 `publication_policy=clean_candidate` 的 details 默认进入 required set；
- supporting details 可选；
- side-branch 默认不进入主 Method；
- 若某一 core detail 因 authority 不允许进入 clean Candidate，则必须转为 explicit review/annotated item，而不是静默删掉并将 mechanism 视为完整。

---

## 8.5 Architect validation

新增：

```python
def validate_narrative_plan(
    plan: NarrativePlanV3,
    contexts: MechanismContextSetV1,
) -> tuple[str, ...]:
```

必须检查：

- referenced mechanism exists；
- referenced detail exists；
- 每个 core mechanism 被至少一个 narrative unit 负责；
- required details 没有跨 mechanism 错绑；
- formula obligation owner 与 mechanism 一致；
- side branch 不得在无 author override 时成为主 section；
- transition 不创建 technical facts。

---

# 9. Mechanism Formula Obligation Compiler + Formalizer V2

上一版把 Formalizer cutover 放在 Architect 之前是对的，但 v2 增加一个必须先完成的中间 owner：**Formula obligation 不能继续继承 legacy paragraph ownership。**

## 9.1 Mechanism Formula Obligation Compiler

先由纯 compiler 从：

```text
MechanismContextV1
+ formalizable details
+ author formula expectation / notation hint
```

产生 paragraph-independent obligation：

```python
class MechanismFormulaObligationV1(BaseModel):
    obligation_id: str
    mechanism_id: str
    source_detail_ids: tuple[str, ...]

    expectation: Literal["required", "preferred", "none"]
    mathematical_goal: str
    claim_kind: Literal["formalization", "specification"] = "formalization"
    required_evidence_authority: tuple[str, ...] = ()

    required_operator_signatures: tuple[dict[str, Any], ...] = ()
    required_operand_sets: tuple[tuple[str, ...], ...] = ()
    required_conditions: tuple[str, ...] = ()
    notation_hints: tuple[str, ...] = ()

    source_facet_ids: tuple[str, ...] = ()
    source_obligation_ids: tuple[str, ...] = ()
    source_operation_ids: tuple[str, ...] = ()
    source_fact_ids: tuple[str, ...] = ()
    source_equation_ids: tuple[str, ...] = ()

    source_context_digest: str
    content_digest: str
```

**禁止字段**：

```text
section_id
consumer_paragraph_id
paragraph_ids
ordered_semantic_slot_ids
required_edge_ids
```

这些属于 narrative placement，不属于 formula semantic ownership。

当前 `MethodFormulaObligationV2` 可保留 legacy adapter，但 unified Formalizer 不得从它决定 technical scope。

## 9.2 Obligation compiler rules

- author intent 只说明“希望 formalize 什么”，不能自动提供 implementation operands；
- repository formalizable detail 提供 operators/operands/conditions；
- 一个 obligation 必须绑定一个 mechanism 与至少一个 source detail；
- alias facets 可合并到同一 obligation，前提是 source detail set 与 mathematical goal 一致；
- cross-mechanism merge 禁止；
- author-only formalization expectation若无 code closure，应产生 `author_intent_only/review_only` obligation，不得进入 repository-derived lane。

## 9.3 Mechanism Formalizer input

只接受：

```text
byte-identical MechanismContext shared payload
+ MechanismFormulaObligationV1
```

禁止：

- whole-section fallback；
- sibling mechanism packs；
- paragraph-local empty → all evidence；
- author-intent formula 自动冒充 implementation equation。

Formalizer call trace 必须记录：

```text
source_context_digest
view_digest
slice_digests
shared_payload_digest
core_detail_ids
formula_obligation_ids
consumer_request_digest
```

## 9.4 Formula package owner

新 package：

```python
class MechanismFormulaPackageV2(BaseModel):
    package_id: str
    mechanism_id: str
    source_detail_ids: tuple[str, ...]
    satisfied_obligation_ids: tuple[str, ...]

    latex: str
    markdown_block: str
    prose_explanation: str
    symbol_definitions: tuple[tuple[str, str], ...]
    material_conditions: tuple[str, ...]
    assumptions: tuple[str, ...]

    evidence_authority: str
    formula_lane: str
    review_status: str
    risks: tuple[str, ...]
    review_question: str = ""

    bound_operation_ids: tuple[str, ...] = ()
    bound_fact_ids: tuple[str, ...] = ()
    bound_equation_ids: tuple[str, ...] = ()

    source_context_digest: str
    shared_payload_digest: str
    content_digest: str
```

**没有 paragraph/section owner。** Architect V3 后续产生独立 placement：

```python
class FormulaPlacementV1(BaseModel):
    package_id: str
    section_id: str
    paragraph_id: str
```

Legacy adapter 可以在写旧 artifact 时补回 `section_id/consumer_paragraph_id`，但它们不能反向改变 package evidence scope。

## 9.5 Formula fidelity guards

保留 wrapper/symbol/operation guards，并增加：

1. `formula_detail_ownership_mismatch`；
2. `formula_cross_mechanism_contamination`；
3. `formula_operator_mismatch`；
4. `formula_operand_set_mismatch`；
5. `formula_condition_mismatch`；
6. `formula_source_context_digest_mismatch`；
7. `formula_shared_payload_digest_mismatch`；
8. `formula_inactive_path_source`；
9. `formula_obligation_source_membership_mismatch`。

### Clean Candidate policy

默认：

```text
clean Candidate formula:
  repository_verified + repository_derived + accepted

annotated/review sidecar:
  author_intent_academic
  hybrid_partial
  review_required
  mismatch
```

如果未来产品要允许 author-specified formula 出现在 clean Candidate，应通过 explicit policy，并使用 author-specification framing；不能继续 implicit fallback。

# 10. Writer V3

## 10.1 Writer 输入必须变为三部分

```python
WriterSectionInputV3 = {
    "narrative_plan": SectionNarrativePlan,
    "shared_contexts": tuple[MechanismContextViewV1, ...],
    "formula_packages": tuple[MechanismFormulaPackageV2, ...],
    "repair_feedback": ...,
}
```

不要再构造：

```text
MethodUnit technical payload
PublicationAuthoringPacketV2
compact dossier summary
second operation inventory
```

---

## 10.2 Writer prompt 的核心任务

Writer 不需要重新“研究代码”，而是：

1. 按 NarrativePlan 的 rhetorical order 组织 mechanism；
2. 覆盖 required core details；
3. 用 supporting details 增强可读性/复现性；
4. 在适当位置插入 Formalizer canonical formula block；
5. 保持 inputs→transformations→conditions→outputs 的连续逻辑；
6. 对 mismatch/author specification 使用正确 framing；
7. 避免 source-code narration、variable-name dumping、debug branch 主线化。

---

## 10.3 不再用“缩短上下文”保证 Writer 不乱写

Writer 看到 richer context 后，安全性由：

- typed detail authority；
- render policy；
- FormulaPackage lane；
- Binder detail witness；
- Candidate/Verified split；
- post-render authority validator；

共同保证。

这比把技术内容提前删除更符合系统目标。

---

## 10.4 Writer response schema

建议段落级输出仍然保持结构化，但 target ID 简化：

```python
class PublicationParagraphV3(BaseModel):
    paragraph_id: str
    paragraph_markdown: str

    rendered_detail_ids: tuple[str, ...] = ()
    used_formula_package_ids: tuple[str, ...] = ()
    deferred_detail_ids: tuple[str, ...] = ()

    witnesses: tuple[ParagraphWitnessV2, ...] = ()
    unresolved_points: tuple[str, ...] = ()
```

不再要求 Writer 同时上报：

```text
facet IDs
field candidate IDs
slot IDs
edge IDs
claim IDs
...
```

这些 provenance 都可以从 `detail_id` 追到 source closure。

这会显著降低 response schema burden，也减少当前 Binder representation failure。

---

# 11. Binder / Validator Migration

## 11.1 保留 Paragraph Transaction 的核心思想

当前 transaction/Binder 最有价值的性质不是 facet/slot taxonomy，而是：

> **正文里的一个具体 prose/formula span 必须能够反向绑定到一个关闭的、带 source authority 的 semantic contract。**

以下能力全部保留：

- exact unique witness；
- semantic anchor；
- conditions；
- polarity；
- formula route；
- source fact/span trace；
- Candidate persistence + Verified fail-closed。

---

## 11.2 External target taxonomy 收敛为 `detail + formula`

Writer transaction 不再需要 self-report：

```text
facet / field / slot / edge / formula
```

改为：

```text
detail / formula
```

但这只是**外部 wire contract 简化**，不是语义验证简化。

---

## 11.3 Detail witness contract 必须包含 atomic obligations

```python
class DetailWitnessTargetV2(BaseModel):
    target_kind: Literal["detail", "formula"]
    target_id: str

    semantic_atom: str
    witness_atoms: tuple[DetailWitnessAtomV1, ...]

    allowed_exact_excerpts: tuple[str, ...]
    allowed_anchor_ids: tuple[str, ...]
    evidence_authority: str
    publication_policy: str
```

`DetailWitnessAtomV1` 至少支持：

```text
operation_atom
operand_atom
output_atom
condition_atom
polarity_atom
interface_atom
formal_relation_atom
```

### Example：EBCAR dedicated attention

一个 detail：

```text
dedicated same-document masked attention
```

至少可能有 required atoms：

```text
operation: dedicated attention applies a mask
operand: query key remains visible
condition: same-document passages are visible
polarity: other-document passages are forbidden
formal relation: allowed logits unchanged / forbidden logits -> -inf
```

Writer 只写“we use a dedicated mask”不能使整个 detail valid。

---

## 11.4 Witness resolution semantics

Binder 做：

```text
paragraph body
→ one or more exact sentence/formula spans
→ detail_id
→ required witness_atoms
→ source closure
```

一个 required detail `valid=True` 当且仅当：

```text
all required witness atoms are covered
AND conditions/polarity match
AND witness spans are unique/closed
```

允许：

- 一句覆盖多个 atoms；
- 多句共同覆盖一个 detail；
- 一个准确公式覆盖 formal_relation + selected operation atoms。

不允许：

- 一个 generic sentence 因 lexical overlap 覆盖整个 detail；
- detail_id self-report 自动通过；
- condition/polarity 省略但仍视为完整。

当前 `_anchor_compatible()` 与 sentence-level semantic fallback 可以复用，但打分单位从“整个 detail semantic_atom”改为 per-witness-atom contract。

---

## 11.5 Edge realization

不要求 Writer 为每个 internal edge self-report ID。`MechanismEdgeV1` 通过：

- source/target detail 均 witnessed；
- prose order / producer-consumer semantics 不矛盾；
- material condition edge 若需要则有对应 witness atom；

进行独立 realization 统计。

---

## 11.6 Formula witness

仍要求：

- exact canonical display math block；
- package ID / obligation route closed；
- package mechanism/detail owner 与 narrative placement一致；
- package digest 与 shared payload/context一致；
- accepted package 的 source details 已被 paragraph/context正确消费。

# 12. Method Content Trace V2：将“信息损失”变成一等可观测对象

当前 `MethodContentTraceRowV1` 以 paragraph/facet/slot 为核心，难以回答：

> Research 找到的这个 scientific detail，到底在哪一层消失？

新增：

```python
class MechanismDetailTraceRowV2(BaseModel):
    mechanism_id: str
    detail_id: str

    source_fact_ids: tuple[str, ...]
    source_span_ids: tuple[str, ...]
    authority: str
    importance: str

    discovered: bool
    context_included: bool
    formalizer_delivered: bool
    writer_delivered: bool
    planned: bool
    rendered: bool
    witnessed: bool
    validated: bool

    planned_paragraph_ids: tuple[str, ...] = ()
    rendered_paragraph_ids: tuple[str, ...] = ()

    terminal_state: Literal[
        "validated",
        "rendered_invalid",
        "writer_omitted",
        "not_planned",
        "context_lost",
        "research_missing",
        "review_only",
        "budget_exhausted",
    ]

    stop_reason: str
```

## 12.1 必须新增的指标

### Research → Context

```text
mechanism_discovery_recall
context_core_detail_count
context_supporting_detail_count
context_unresolved_detail_count
```

### Context → Writer

```text
writer_delivery_recall_core
writer_delivery_recall_supporting
context_to_writer_core_loss_rate
```

核心 hard gate：

```text
context_to_writer_core_loss_rate == 0
```

### Writer → Candidate

```text
rendered_core_detail_recall
rendered_supporting_detail_recall
condition_recall
configuration_recall
interface_recall
```

### Formula

```text
formula_obligation_recall
strict_verified_formula_recall
review_required_formula_count
formula_mechanism_mismatch_count
formula_operator_mismatch_count
formula_operand_set_mismatch_count
```

### Coherence

```text
mechanism_edge_realization_rate
core_step_order_violation_count
cross_mechanism_contamination_count
```

---

# 13. Research Callback V2

当前 callback 的问题不是“没用”，而是 ownership 粒度仍然是 section/paragraph，且 fulfilled 后可能触发大范围 resume，导致新的 evidence 改坏原稿。

## 13.1 Callback owner 改为 mechanism/detail

```python
class MechanismResearchRequestV2(BaseModel):
    request_id: str
    mechanism_id: str
    target_detail_id: str = ""

    unresolved_kind: Literal[
        "missing_definition",
        "missing_call_path",
        "missing_data_flow",
        "missing_condition",
        "missing_configuration",
        "missing_formula_operand",
        "authority_conflict",
    ]

    exact_question: str
    candidate_symbols_or_terms: tuple[str, ...]
    baseline_span_ids: tuple[str, ...]
    baseline_context_digest: str
```

## 13.2 Fulfilled 的定义必须是 semantic delta

不能只因为 callback 返回了 artifact 就算 fulfilled。

必须至少满足一项：

- 新增 source span/fact；
- unresolved detail → resolved/partial；
- 新增 definition body；
- 新增 material condition/config；
- formula operand closure 改善；
- context digest 改变且 target mechanism readiness 改善。

否则：

```text
fulfilled = false
reason = no_semantic_delta
```

## 13.3 Resume 粒度

```text
context changed
→ identify narrative paragraphs referencing mechanism_id
→ only rewrite affected paragraphs
```

禁止默认 resume whole section。

## 13.4 Callback pre-resume gate

在真正调用 Writer 前比较：

```text
new_context_quality > old_context_quality
```

至少要求：

- unresolved count 不增加；
- cross-mechanism contamination 不增加；
- core detail count 不减少；
- target gap 被关闭。

否则保留 incumbent，不发起 rewrite。


---

# 14. Production Orchestrator 重排

最终 `run_publication_method_writer()` 的目标顺序：

```text
load atomic claims / code facts / equations / configs
load author briefs / facets / field alignments
load behavior graph / implementation scope / symbol index
        ↓
compile_mechanism_contexts()                  [NEW]
        ↓
persist mechanism_contexts_v1.json
        ↓
build_narrative_plan_v3(contexts, story)     [Architect]
        │
        ├──────────────────────────┐
        │                          │
        ▼                          ▼
NarrativePlanV3            run_mechanism_formalizer(contexts)
        │                          │
        │                    FormulaPackagesV2
        └──────────────┬───────────┘
                       ▼
             build_writer_inputs_v3()
                       ↓
                    Writer
                       ↓
              Detail Binder / Validator
                       ↓
                 Candidate/Verified
```

## 14.1 当前 orchestrator 必须抽出的 loader

当前 behavior graph / implementation scope 在 `replan_moves_with_trace()` 之后才加载。需要抽成：

```python
def _load_repository_authoring_context(
    artifact_paths: Mapping[str, str],
) -> RepositoryAuthoringContext:
    ...
```

至少加载：

- behavior graph；
- implementation scope；
- evidence packets；
- SymbolIndexV2（若已有 artifact）；
- snapshot/source provider handle。

目标是让 MechanismContextCompiler 在 Architect 之前拥有完整 repository research inputs。

---

# 15. Code-Level Change Map

下面给出建议的代码级修改边界。实现时应以函数职责迁移为主，避免一次提交删除大量 legacy 代码导致无法对照。

## 15.1 新增文件 / 新 canonical models

### A. `src/code2paper/agentic/mechanism_context_models.py`

新增：

- `MechanismSeedV1`；
- `EvidenceOperationV1`；
- `SourceOperationDispositionV1`；
- `MechanismEvidenceClosureV1`；
- `DetailWitnessAtomV1`；
- `MechanismDetailV1`；
- `MechanismEdgeV1`；
- `SharedDetailRefV1`；
- `MechanismContextV1`；
- `MechanismContextSetV1`；
- `MechanismContextViewV1`；
- `MechanismContextSliceV1`；
- active-path / claim-kind / evidence-authority / publication-policy enums。

要求：

- frozen Pydantic models；
- `extra="forbid"`；
- deterministic canonical serialization；
- ID uniqueness + source-membership validators；
- paragraph-independent source context digest；
- repository-derived detail source binding validator；
- shared detail canonical owner validator。

### B. `src/code2paper/agentic/mechanism_context_compiler.py`

实现上明确拆成两类函数，而不是一个大函数：

```text
compile_mechanism_evidence_closures()     # WP-2
  brief/facet/alignment
  → seed
  → exact evidence closure
  → graph/callee expansion
  → active/default path
  → freeze closure

annotate_mechanism_paper_details()        # WP-3
  frozen closure
  → deterministic operation clusters
  → ordinal-only semantic annotation
  → witness atoms
  → importance / three-axis policy
  → operation dispositions
  → MechanismContextSet
```

这样 code structure 本身就强制“先不丢事实，再做抽象”。

从 `research_derived_authoring.py` 抽取通用 helpers，而不是复制第二套 graph/fact logic。

### C. `src/code2paper/agentic/mechanism_context_projection.py`

唯一 LLM-visible deterministic view：

- `build_mechanism_context_view()`；
- `build_mechanism_context_slices()`；
- `serialize_shared_mechanism_payload()`；
- `compute_source_context_digest()`；
- `compute_view_digest()`；
- `compute_slice_digest()`；
- `compute_shared_payload_digest()`；
- `assert_consumer_shared_payload_identity()`。

禁止保留一个模糊 `assert_shared_payload_digest()` 作为唯一检查；必须验证实际 ordered serialized slices 与 core detail set。

### D. Formula obligation implementation location

首版**不建议为了一个模型再新增独立 Agent/module**。可先在 `formalization_agent.py` 中增加纯函数：

```python
compile_mechanism_formula_obligations(...)
```

以及 `MechanismFormulaObligationV1` / `MechanismFormulaPackageV2` models。若后续文件职责过重，再物理拆文件；当前优先避免过度工程化。

### E. `src/code2paper/agentic/mechanism_context_trace.py`（可选）

如果 `method_content_trace.py` 继续承载 V2 lifecycle 会明显混乱，再拆独立 trace 文件；否则优先复用现有 trace infrastructure。

## 15.2 `src/code2paper/agentic/research_derived_authoring.py`

### 保留/抽取

当前高价值能力：

- `compile_code_fact_operation_chain()`；
- graph parts；
- shortest connected subgraph；
- source/excerpt filtering；
- configuration binding；
- condition extraction；
- shape / return descriptor extraction；
- relation classification；
- readiness diagnostics。

应提取为 plan-independent helpers 供 MechanismContextCompiler 调用。

### Legacy wrapper

`build_research_mechanism_dossiers()` 暂时保留：

```python
def build_research_mechanism_dossiers(...):
    if unified_contexts is available:
        return legacy_dossiers_from_contexts(...)
    return _legacy_build_research_mechanism_dossiers(...)
```

但 unified production mode 下不得反向把 legacy dossier 作为技术 authority。

### 最终删除候选

- `PublicationAuthoringPacketV2`
- `build_publication_authoring_packets()`
- 与 Writer-only dossier compaction 绑定的 adapter

删除应在 Phase 10 cleanup 之后。

---

## 15.3 `src/code2paper/agentic/method_argument_models.py`

### `MethodUnitV2`

短期：保留供 legacy plan/replay。

新增 `NarrativeUnitV1` / `MethodUnitV3`：

- only context IDs/detail IDs/formula obligations/narrative metadata；
- no operation/fact/span reconstruction。

### `SectionParagraphPlanV1`

可新增兼容字段：

```python
mechanism_context_ids: tuple[str, ...] = ()
required_detail_ids: tuple[str, ...] = ()
optional_detail_ids: tuple[str, ...] = ()
```

Legacy fields暂时保留：

```text
required_facet_ids
required_field_candidate_ids
required_publication_slot_ids
ordered_semantic_slot_ids
required_edge_ids
```

unified mode 只使用新字段；dual-run 期间可同时序列化，方便比较。

### `ParagraphWitnessTargetV1`

扩展 `target_kind` 支持：

```text
detail
formula
```

最终统一后，legacy target kinds 可 deprecated。

---

## 15.4 `src/code2paper/agentic/method_architect.py`

### 新增

```python
def build_narrative_plan_v3(
    *,
    contexts: MechanismContextSetV1,
    story_spine: ...,
    prior_plan: ... | None = None,
    proposal_caller: ... | None = None,
) -> tuple[NarrativePlanV3, dict[str, Any]]:
    ...
```

### Architect proposal schema

LLM 只能返回 ordinal context/detail references：

```json
{
  "sections": [
    {
      "heading": "...",
      "mechanism_indices": [0,1],
      "paragraphs": [
        {
          "role": "mechanism_explanation",
          "required_detail_indices": [0,1,2,3],
          "optional_detail_indices": [4],
          "formula_obligation_indices": [0]
        }
      ]
    }
  ]
}
```

Harness 再解析成 stable IDs；LLM 不能自行输出 fact/span ID。

### Legacy `replan_moves_with_trace()`

Phase 6 前保留用于 legacy/shadow；unified narrative cutover 后不再调用。

需要逐步退役：

- `_build_method_units_v2()` 的 technical compilation；
- facet groups-of-four compaction；
- slot ownership heuristic；
- first/last transformation hard-target selection；
- MethodUnit-specific witness contract rebuild。

---

## 15.5 `src/code2paper/agentic/formalization_agent.py`

### `MechanismEquationEvidencePackV1`

短期保留为 compatibility/formula-specific view，但其 source 只能来自 `MechanismContextV1.evidence_closure`：

```python
build_equation_evidence_pack_from_context(
    context: MechanismContextV1,
    detail_ids: tuple[str, ...],
)
```

它不再拥有独立 evidence discovery/fallback 权限。

### 新增 `compile_mechanism_formula_obligations()`

在 Formalizer 之前，从 context + author formula expectation 编译 paragraph-independent `MechanismFormulaObligationV1`。

禁止 unified obligation 携带：

```text
section_id
consumer_paragraph_id
paragraph_ids
ordered_semantic_slot_ids
required_edge_ids
```

### Legacy `MethodFormulaObligationV2`

保留历史 artifact/replay adapter。允许：

```text
MechanismFormulaObligationV1
→ legacy MethodFormulaObligationV2
```

不允许：

```text
legacy paragraph-owned obligation
→ decide unified technical formula scope
```

### `SectionFormulaPackageV1`

Legacy 保留；unified 内部使用 `MechanismFormulaPackageV2`。需要写旧 sidecar 时再适配 section/consumer placement。

新 package 必须记录：

```text
mechanism_id
source_detail_ids
source_context_digest
shared_payload_digest
bound_operation_ids
bound_fact_ids / bound_equation_ids
```

### Guards

新增/强化 ownership、operator、operand-set、condition、active-path、source-context/shared-payload digest guards。

## 15.6 `src/code2paper/agentic/publication_method_writer.py`

这是 orchestrator cutover 核心。

### 新 helper / owner sequence

```python
def _load_repository_authoring_context(...): ...
def _compile_mechanism_evidence_closures(...): ...
def _annotate_mechanism_paper_details(...): ...
def _build_shared_mechanism_payloads(...): ...
def _compile_mechanism_formula_obligations(...): ...
def _run_mechanism_formalizer(...): ...
def _build_narrative_plan_v3(...): ...
def _build_writer_inputs_v3(...): ...
```

### 新 mode

只增加集中开关：

```python
AuthoringContextMode = Literal[
    "legacy",
    "shadow_unified",
    "unified",
]
```

- `legacy`：当前路径；
- `shadow_unified`：新 closure/context/payload/formula 路径全跑并产 diagnostics，最终仍可由 legacy Writer 输出；
- `unified`：正式新路径。

### Unified target code sequence

当前 `run_publication_method_writer()` 的大顺序应迁移为：

```text
load frozen research artifacts
↓
WP-2 compile MechanismEvidenceClosure
↓
resolve active/default paths
↓
WP-3 annotate PaperDetails + witness atoms
↓
persist MechanismContextSet
↓
WP-4 build one shared projection/slice set
↓
WP-4.5 compile MechanismFormulaObligations
↓
WP-5 run Mechanism Formalizer
↓
WP-6 build NarrativePlanV3 + formula placement
↓
WP-7 build WriterSectionInputV3
↓
Writer
↓
WP-8 Detail-Atom Binder / Trace
```

对应当前调用：

- 约 line 627 `replan_moves_with_trace()`：unified 不再前置；由后置 `build_narrative_plan_v3()` 替代；
- 约 line 755 `build_research_mechanism_dossiers()`：legacy/shadow comparison保留，unified 不作为 technical source；
- 约 line 854 `_run_section_formalizer()`：legacy保留，unified 改 Mechanism Formalizer；
- 约 line 902 `build_publication_authoring_packets()`：unified 完全跳过；
- 约 line 1010 `_writer_section_inputs()`：unified 改 `_writer_section_inputs_v3()`。

### Shadow rule

`shadow_unified` 如果新链失败，必须记录 explicit shadow failure；可以继续用 legacy 产生用户可见 Candidate，但**不能把该 run 标成 unified success**。

## 15.7 `src/code2paper/llm/section_writer.py`

### unified path 删除的职责

`_compact_authoring_packets_v2_for_llm()` 不进入新路径。

`_llm_visible_section_payload()` 增加 V3：

```python
if section.shared_mechanism_contexts:
    return {
        "section_id": ...,
        "heading": ...,
        "narrative_plan": ...,
        "shared_contexts": [...],
        "formula_packages": [...],
        "repair_feedback": ...,
    }
```

**不要再二次 compact `shared_contexts`。**

### Prompt

增加明确要求：

- required core detail coverage；
- scientific order；
- no raw implementation narration；
- formula placement；
- authority-aware framing；
- supporting details 可用于增加深度；
- side branch 不升格为主线。

---

## 15.8 `src/code2paper/agentic/publication_transaction_contract.py`

### `required_targets_from_plan_row()`

支持：

```python
"detail": _ids(row.get("required_detail_ids")),
"formula": ...
```

unified mode 不再要求 facet/field/slot/edge closure。

### `_witness_constraints_from_plan_row()`

Unified mode 不再为一个 detail 只构造一个 aggregate anchor，而是展开：

```text
detail_id
→ witness_atom_ids
→ per-atom semantic/exact/condition/polarity/source constraints
```

读取：

- detail semantic atom（仅作上层 summary）；
- `DetailWitnessAtomV1` required/optional；
- per-atom exact excerpts；
- per-atom conditions / polarity；
- source anchor IDs。

### `assess_paragraph_transaction()`

保留 exact witness uniqueness 和 semantic compatibility，并新增：

```text
required_detail_valid
= all(required witness atoms witnessed and constraint-compatible)
```

一个 detail 可以由多句覆盖；一个 generic detail-level sentence不能替代缺失的 material condition/polarity/output atom。

---

## 15.9 `src/code2paper/agentic/method_content_trace.py`

新增 V2 trace；旧 V1 保留用于历史 replay。

建议输出：

```text
method_content_trace_v2.json
mechanism_information_funnel_v1.json
```

后者专门统计：

```text
Research → Context → Architect → Writer → Candidate → Validated
```

---

## 15.10 `src/code2paper/agentic/method_content_regression.py`

现有 oracle infrastructure 不应废弃，反而应成为本次架构迁移的主要 offline regression harness。

新增指标计算：

```python
evaluate_mechanism_detail_recall(...)
evaluate_context_writer_delivery(...)
evaluate_mechanism_contamination(...)
evaluate_formula_fidelity(...)
```

Oracle 继续标注 `diagnostic_only=True`，绝不进入 production authority。

---

# 16. Migration Plan：禁止 Big-Bang Cutover

必须使用：

```text
legacy
shadow_unified
unified
```

并把“事实闭合”与“论文语义抽象”拆成两个独立阶段。

## Phase 0 / WP-0 — Freeze Evidence, Quality and Efficiency Baseline

**目标**：不改变 production output，冻结比较基线和预算。

工作：

1. 固定 SHA `a7c10318...` 三项目 replay；
2. 保存 candidate、formalizer result、content trace、token summary、callback logs；
3. 将 blind baseline 关键 unit 写成 **diagnostic_non_authorizing** fixture，并补 `repo_snapshot_sha/repo_verifiable/active_path_status`；
4. 冻结 oracle_writer fixture 结果；
5. 输出 legacy information funnel：dossier → MethodUnit → Writer-visible → rendered；
6. 冻结效率基线：
   - `total_tokens_per_candidate`；
   - `tokens_per_validated_core_detail`；
   - `calls_per_validated_paragraph`；
   - `callback_token_fraction`；
   - Formalizer/Writer input tokens；
7. **在 WP-3 tuning 前预先冻结 cross-repo holdout selection protocol。**

Gate：现有 replay 可复现、artifact digest 可比较、Candidate 不变。

---

## Phase 1 / WP-1 — Models + Canonical Digest Rules

新增/修改：

- `MechanismSeedV1`；
- `MechanismEvidenceClosureV1`；
- `EvidenceOperationV1`；
- `MechanismDetailV1`；
- `DetailWitnessAtomV1`；
- shared ownership refs；
- four/five-level digest contracts。

Gate：serialization deterministic；paragraph reorder 不改变 source context digest；digest semantics 有 byte-level tests。

---

## Phase 2 / WP-2 — Lossless Evidence Closure Compiler

**目标：不丢事实，不讨论“怎么写论文”。**

工作：

- seed compiler；
- exact fact/claim/equation closure；
- behavior graph closure；
- DefinitionResolver；
- active/default path resolution；
- bounded expansion；
- persist `mechanism_evidence_closures_v1.json`。

禁止：

- PaperDetail semantic compiler；
- paragraph/section inputs；
- original paper/oracle as source；
- whole-section fallback。

Gate：

```text
source_operation_terminal_coverage cannot yet be required
# because dispositions are WP-3,
but source operation membership is frozen and reproducible.
active_path_classification_coverage for core candidates = 1.0 or typed unknown
callee definition regression passes
no scope-widening fallback
```

三项目对 blind code audit 做 recall diagnosis，但 blind fixture不授权 compiler。

---

## Phase 3 / WP-3 — EvidenceClosure → PaperDetails

**目标：把事实抽象成论文语义，但不改变事实 membership。**

工作：

- deterministic operation clustering；
- low-temperature semantic annotation；
- detail witness atoms；
- importance；
- three-axis authority/policy；
- active-path promotion rules；
- shared ownership；
- operation terminal dispositions。

Hard Gate：

```text
source_operation_terminal_coverage == 1.0
repository_detail_source_binding_rate == 1.0
semantic_compiler_source_membership_mutation == 0
inactive_path_promoted_to_core == 0
```

---

## Phase 4 / WP-4 — Single Shared Projection + Digest Closure

**目标**：Formalizer/Writer 尚不切换，只证明 shared payload 真正可相同。

工作：

- single view builder；
- explicit slices；
- source/view/slice/shared-payload/request digests；
- byte-identical consumer fixtures。

Gate：

```text
formalizer_shadow.shared_payload_digest == writer_shadow.shared_payload_digest
formalizer_shadow.core_detail_ids == writer_shadow.core_detail_ids
shared payload bytes identical
silent truncation = 0
```

---

## Phase 4.5 / WP-4.5 — Mechanism Formula Obligation Compiler

**目标**：在 Formalizer cutover 前切断 legacy paragraph ownership。

输入：

```text
MechanismContext
+ author formula expectation
+ formalizable details
```

输出：`MechanismFormulaObligationV1`，不得含 section/paragraph/slot/edge ownership。

Gate：

- every obligation has mechanism + source details；
- no cross-mechanism obligation；
- author-only formula expectation不会升级为 repository-derived；
- legacy `MethodFormulaObligationV2` 只作为 adapter。

---

## Phase 5 / WP-5 — Mechanism Formalizer Cutover

Formalizer 使用：

```text
shared MechanismContext payload
+ MechanismFormulaObligation
```

仍输出 legacy-compatible sidecar adapter 供 shadow Writer 使用。

Gate：

- no whole-section fallback；
- source/shared digest closure；
- formula owner/operand/operator/condition guards；
- no inactive-path source promoted；
- frozen repo-derived LinearRAG/EBCAR/DYG formula diagnostics不回归。

---

## Phase 6 / WP-6 — Narrative Architect V3

Architect 完全退出 technical IR compilation。

工作：

- thin NarrativePlan；
- core detail placement；
- shared detail references；
- FormulaPackage placement；
- complexity-aware paragraph grouping。

Gate：

- no unknown technical IDs；
- each primary core detail placed exactly once；
- shared refs 可重复消费但不复制 technical truth；
- no inactive/side branch promotion；
- no core detail loss due to sentence budget。

---

## Phase 7 / WP-7 — Writer V3 Shadow / Cutover

Writer 只读：

```text
SharedContext + NarrativePlan + accepted FormulaPackages
```

不再读 AuthoringPacketV2 technical compact。

比较 legacy/unified：

- validated core detail recall；
- unsupported positive claims；
- witness atom completeness；
- formula fidelity；
- narrative continuity；
- token/call cost。

Gate：质量提升且 faithfulness 不回归。

---

## Phase 8 / WP-8 — Detail-Atom Binder + Trace V2

工作：

- detail/formula external target；
- per-detail witness atoms；
- paragraph transaction V2；
- content lifecycle trace；
- Formula placement validation。

Gate：

- required detail 任一 required atom 未 witness → invalid；
- condition/polarity mismatch fail；
- formula route fail-closed；
- Candidate persists, Verified closed。

---

## Phase 8.5 — Callback V2 + Incremental Resume

callback owner 改为 mechanism/detail/closure unresolved item。

`fulfilled` 必须有 semantic delta：新增 source closure、active-path resolution、detail source binding 或 formula closure。仅有新日志/重复 excerpt 不能 fulfilled。

Resume 只触发引用 changed mechanism/detail 的 paragraph。

---

## Phase 9 / WP-9 — Three-Project Live Replay

DYG / LinearRAG / EBCAR 做 frozen-snapshot regression。

项目 expected units 必须先经过 diagnostic metadata 分类；hard gate 只使用 repo-verifiable units。论文/oracle结构只做 usability diagnostic。

同时检查效率 Pareto 与 callback regression。

---

## Phase 9.5 / WP-9.5 — Cross-Repository Stress Set

**目的**：防止 harness 被三个已知案例的答案形状过拟合。

在 WP-3 tuning 前冻结 selection protocol，cleanup 前至少跑：

- 1 个 nested helper / wrapper-heavy repo；
- 1 个 config/branch-heavy repo；
- 1 个 formula/loss-heavy repo；
- 1 个非 graph-style method repo；
- 可包含已有 RAP fixture，但至少 3 个项目不能是 DYG/LinearRAG/EBCAR。

要求：

- 不新增 project-name/operator marker；
- 不读取 original paper 来修 production compiler；
- source_operation closure / active path / shared digest / Binder atoms 均通过；
- human/VLM 只做质量评估，不授权事实。

---

## Phase 10 / WP-10 — Legacy Cleanup

只有 Phase 9 + 9.5 + unit/integration 全部通过后删除 unified production 对：

- `PublicationAuthoringPacketV2`；
- `_compact_authoring_packets_v2_for_llm()`；
- MethodUnitV2 technical fields；
- Architect SemanticArgumentFrame technical truth；
- paragraph-bound ResearchDossier authority；
- Formalizer whole-section fallback；
- legacy paragraph-owned formula obligation。

Historical models 可以保留 deserialization compatibility，但不能继续参与 unified production technical decision。

# 17. Test Plan

## 17.1 Evidence Closure Tests

新增建议：

```text
tests/test_agentic_mechanism_context_models.py
tests/test_agentic_mechanism_evidence_closure.py
tests/test_agentic_definition_resolver.py
tests/test_agentic_active_path_resolution.py
```

覆盖：

1. stable mechanism/source-operation IDs；
2. paragraph reorder 不改变 closure digest；
3. exact span→fact closure；
4. claim→fact/equation closure；
5. behavior graph exact seed；
6. callee definition from SymbolIndexV2；
7. same-name ambiguous symbol unresolved；
8. depth/budget exhaustion typed；
9. function default vs entrypoint override precedence；
10. inactive branch 不成为 core candidate；
11. optional graph absence + complete fact chain仍可 ready；
12. no whole-section/repo fallback。

## 17.2 PaperDetail Compiler Tests

```text
tests/test_agentic_mechanism_detail_compiler.py
tests/test_agentic_detail_witness_atoms.py
```

覆盖：

- semantic compiler ordinal-only source binding；
- cannot mutate closure membership；
- source operation terminal coverage = 1.0；
- repository-derived detail has exact source closure；
- author rationale can be author-intent-only without pretending implementation；
- active/inactive importance policy；
- primary + shared ownership；
- witness atom deterministic derivation；
- mask/filter/threshold polarity atom；
- output/interface atom closure。

## 17.3 Shared Projection Tests

```text
tests/test_agentic_mechanism_context_projection.py
```

覆盖：

- source/view/slice/shared payload digest；
- byte-identical Formalizer/Writer shared payload；
- same ordered core detail IDs；
- role-specific task不改变 shared digest；
- slice reorder/replacement 被检测；
- token budget exhaustion不 silent truncate。

## 17.4 Formula Obligation / Formalizer Tests

```text
tests/test_agentic_mechanism_formula_obligations.py
tests/test_agentic_formalization_guards.py
```

覆盖：

- obligation无 paragraph/section technical ownership；
- source detail membership；
- author-only expectation stays review lane；
- cross-mechanism contamination；
- operator/operand/condition mismatch；
- active-path source guard；
- EBCAR positive-in-denominator fixture；
- LinearRAG Stage1 no-PPR repo-derived fixture；
- DYG unsupported intent不升级 code_verified。

## 17.5 Architect Tests

- Architect cannot create unknown detail/formula IDs；
- every primary core detail placed exactly once；
- shared refs可多 consumer；
- inactive branch cannot be mainline without selected configuration；
- no arbitrary fixed facet/paragraph compaction；
- formula package placement independent of technical ownership。

## 17.6 Writer Tests

- Writer receives exact shared payload recorded in trace；
- no AuthoringPacketV2 technical compact in unified mode；
- core detail IDs preserved；
- author rationale vs implementation framing；
- annotated-only detail不进入 clean Candidate；
- accepted formulas rendered exactly；
- Candidate remains when Binder fails。

## 17.7 Binder Tests

- one generic sentence cannot witness full multi-atom detail；
- multi-sentence witness can satisfy one detail；
- missing condition/polarity atom fails；
- exact formula can satisfy formal_relation atom；
- shared detail source remains canonical；
- edge realization from witnessed details；
- Formula placement/owner/digest closure。

## 17.8 Information Funnel Regression

生命周期指标：

```text
R0 not discovered
R1 closure discovered but unresolved
R2 closure preserved but PaperDetail annotation failed/lost
R3 shared payload delivery loss
R4 Writer rendering/witness loss
```

额外区分：

```text
source_operation_count
terminally_classified_operation_count
repository_detail_count
core_detail_count
delivered_core_detail_count
rendered_core_detail_count
validated_core_detail_count
required_witness_atom_count
validated_witness_atom_count
```

## 17.9 Efficiency Regression

每次 live replay persist：

```text
total_tokens_per_candidate
tokens_per_validated_core_detail
calls_per_validated_paragraph
callback_token_fraction
formalizer_input_tokens
writer_input_tokens
shared_payload_tokens
```

Threshold/tolerance 在 WP-0 预先写入 fixture/config，禁止 after-the-fact 调整。

# 18. Frozen-Project Live Acceptance Gates

DYG / LinearRAG / EBCAR 仍是重要真实 regression case，但 v2 明确区分：

```text
repo-derived hard expectation
vs
blind/oracle diagnostic gold
vs
paper-structure usability reference
```

## 18.0 Fixture provenance contract

每个 expected unit 必须写成：

```yaml
unit_id: ...
source: current_repo_trace | blind_code_audit | paper_structure_reference
repo_snapshot_sha: a7c10318e0edd554533962d1ce6159ce51751291
repo_verifiable: true | false
active_path_status: active | conditional | inactive | unknown
runtime_authority: diagnostic_non_authorizing
```

### Hard cutover 只使用

```text
repo_verifiable=true
```

且检查 active-path semantics 是否正确。`paper_structure_reference` 只能进入 human/VLM publication-usability，不可成为 compiler/operator rule。

---

## 18.1 DyG-Mamba frozen regression

### Repo-derived diagnostics（仅在 fixture 标记 repo_verifiable 后成为 hard）

可能包括：

- first-hop interaction history；
- node/edge/time/co-occurrence representation；
- active Mamba/SSM operation chain；
- actual A parameterization（如当前 snapshot 中可验证的 `A=-exp(A_log)`）；
- source/destination interaction；
- downstream readout/task interface。

### Hard invariants

- code/intent mismatch不能被升级为 repository_verified；
- unsupported monotonic Δt / spectral B/C / theoretical robustness 不能因 original paper/intent存在而变成 code fact；
- config-controlled branch（包括任何 `time_mamba` 类开关）必须依据实际 entrypoint/default/config 分类 active/conditional/inactive；
- inactive/evaluation/case-study branch不能成为 main Method spine；
- active repository-derived core chain必须到达 Writer shared payload。

Paper 中的理想化 B/C constraint、双 encoder/mean pooling 等只做 mismatch/usability reference，不成为 runtime expected code behavior。

---

## 18.2 LinearRAG frozen regression

当前 blind code audit 对 snapshot 的重要诊断是：**default run path 为 non-vectorized local propagation；vectorized branch 是 optional 且 entry point 默认关闭。** 因此 v2 不再把 `calculate_entity_scores_vectorized` 的 existence 当 Stage1 mainline requirement。

### Active/default Stage 1 repo-derived expectation

若 frozen fixture 经 repo closure验证，应包含：

```text
seed entity initialization
→ linked sentence traversal / propagation
→ query-sentence relevance
→ sentence→entity propagation
→ iteration threshold / pruning
→ next active frontier / stopping
```

### Stage 2 repo-derived expectation

```text
hybrid passage initialization
→ entity contribution + dense passage score
→ PPR
→ descending passage ranking
```

### Hard gates

- default Stage1 shared context/formula **0 个 Stage2 PPR operator**；
- `iteration_threshold` 的 direction/polarity必须正确；
- PPR ownership只属于 Stage2；
- no-query-entity dense fallback按 active/config path标为 branch/interface；
- optional vectorized branch若 definition resolver 被要求展开，必须能读取真实 body，但应标记当前 snapshot 的 inactive/conditional status，**不能因为 body 可读就自动 core**；
- `calculate_entity_scores_vectorized` 作为 DefinitionResolver regression test，而不是 publication mainline hard answer；
- passage ratio/vectorized/global options全部依据 active/default config，不依据 paper/oracle强制。

---

## 18.3 EBCAR frozen regression

Repo-derived expected units必须逐项绑定 current snapshot 与 active path，例如：

- retrieval candidate input/top-k；
- relative/local document ID mapping；
- position representation；
- structural augmentation；
- unchanged/static query anchor；
- shared full attention；
- dedicated same-document mask；
- residual/FFN；
- InfoNCE construction；
- inference dot-product scoring/ranking。

### Hard gates

- 如果 current code closure证明 InfoNCE denominator 包含 positive，则生成公式必须保留 positive；若 closure不足则 unresolved，而非错误 fallback；
- dedicated mask 的 allow/forbid polarity不能被 generic “same-document mask”一句话视为完整 witness；
- document/position details不被一条 generic augmentation语句吞掉；
- ConTEB story role只在 author/paper evaluation framing中处理，不能改变 implementation context；
- training/inference discrepancy若 current repo存在，进入 mismatch/limitation/review sidecar，不自动“统一”；
- inactive helper/alternative不得因原论文结构而被强制 mainline。

---

## 18.4 Three-project gates are necessary, not sufficient

任何为解决这三项目而新增的规则如果包含：

```text
project name
known function name marker
known operator-stage hardcode
paper-derived expected implementation
```

默认视为 harness overfit，除非该规则可由通用 typed invariant 表达并通过 WP-9.5 holdout。

# 19. Quantitative Cutover Criteria

正式从 `shadow_unified` 切 `unified` 前，至少满足以下四组指标。

## 19.1 Lossless closure / architecture invariants

```text
source_operation_terminal_coverage = 1.00
repository_detail_source_binding_rate = 1.00
semantic_compiler_source_membership_mutation = 0
active_path_unclassified_core_count = 0
inactive_path_promoted_to_core = 0
cross_mechanism_contamination_count = 0
whole_section_evidence_fallback = 0
silent_context_truncation = 0
architect_unknown_detail_refs = 0
shared_detail_source_divergence = 0
```

## 19.2 Shared consumer invariants

按 mechanism 比较：

```text
formalizer_writer_shared_payload_digest_mismatch = 0
formalizer_writer_core_detail_set_mismatch = 0
formalizer_writer_shared_slice_order_mismatch = 0
```

不能只比较 source context digest。

## 19.3 Content recall / Binder completeness

对 `repo_verifiable=true + active/conditional + clean_candidate` core details：

```text
writer_delivery_recall_core = 1.00
rendered_core_detail_recall >= 0.90
required_witness_atom_delivery = 1.00
validated_required_witness_atom_recall >= 0.90
condition_recall >= 0.90
interface_recall >= 0.90
```

`annotated_only/review_only` 不进入 clean rendered denominator，但必须出现在 review trace。

## 19.4 Faithfulness / Formula fidelity

```text
unsupported_positive_claims <= legacy
critical_formula_semantic_errors = 0
cross_stage_mechanism_errors = 0
formula_operator_mismatch = 0 for accepted packages
formula_operand_set_mismatch = 0 for accepted packages
formula_condition_mismatch = 0 for accepted packages
```

## 19.5 Publication usability

Human/VLM 评估：

- mechanism completeness；
- equation usefulness/correctness；
- section-level narrative continuity；
- implementation specificity；
- paper-ready abstraction；
- no raw-code dump；
- correct distinction between implementation, rationale, specification and limitation。

## 19.6 Efficiency / production Pareto gate

WP-0 冻结 baseline，WP-9 前**预先声明** tolerance/budget：

```text
total_tokens_per_candidate
tokens_per_validated_core_detail
calls_per_validated_paragraph
callback_token_fraction
formalizer_input_tokens
writer_input_tokens
```

原则：

1. correctness 不因 token budget 被削弱；
2. unified 至少应显著改善 `tokens_per_validated_core_detail` 或 `calls_per_validated_paragraph` 中一项；
3. 若 total token/call 超过预声明 production budget，即使质量更高也不能自动 cutover，必须显式批准；
4. 不允许看到结果后移动 tolerance。

## 19.7 Cross-repo generalization gate

WP-9.5 holdout 必须满足：

```text
no project-specific marker required
lossless closure invariants pass
active-path precedence pass
shared payload invariants pass
Binder witness atoms pass
no critical formula semantic error
```

三项目通过但 holdout 失败，不得进入 WP-10 cleanup。

# 20. Risk Register & Mitigation

## Risk A：共享 context 变大，Writer 再次混写

### 原因

信息增加可能造成 sibling mechanism blending。

### Mitigation

- mechanism-first isolation；
- context 一次只包含 NarrativePlan 当前引用 mechanisms；
- stable detail IDs + edges；
- no section-wide fallback；
- side branch 默认不进入主 Writer view；
- explicit context slices。

不是通过删掉 core details解决。

---

## Risk B：Mechanism compiler 过度拆分

### Mitigation

- detail 是 paper-meaningful cluster，不是一行代码；
- structural grouping 先行；
- semantic compiler 只在 closed operation cluster 内抽象；
- downstream plan 可把多个 details 合成一个 paragraph，但不能把 source details 从 context 删除。

---

## Risk C：Mechanism compiler 过度合并

### Mitigation

- exact ownership / graph connectivity；
- stage boundary；
- producer/consumer flow；
- formula owner；
- cross-mechanism contamination validator。

LinearRAG Stage1/Stage2 作为首要 regression fixture。

---

## Risk D：新增 context schema 成为另一层过度工程化

### Mitigation

本设计必须遵循：

```text
one technical IR only
```

因此新增 `MechanismContext` 的同时必须有明确删除路径：

- MethodUnit technical payload；
- PublicationAuthoringPacketV2；
- role-specific technical compaction；
- independent formula evidence source。

如果只是“再加一层”而旧层全部保留，本次重构即失败。

---

## Risk E：Binder 从多个 legacy target 收敛成 detail 后验证变弱

### Mitigation

外部 wire target 可以收敛为 detail，但内部必须携带 `DetailWitnessAtomV1`：

- operation；
- material operand；
- output；
- condition；
- polarity；
- interface/formal relation；
- exact source anchors。

Binder 按 required atom 闭合，不按粗 `detail_id` 自动通过。因此 schema 对 Writer 更简单，但验证强度不下降。

---

## Risk F：Architect 失去技术细节后无法合理分段

### Mitigation

Architect 不需要 raw code，但可以看：

- mechanism purpose；
- ordered core detail summaries；
- detail roles；
- formula obligations；
- complexity；
- story order。

这已经足够做 narrative planning。

---

## Risk G：Formalizer 与 Writer “共享”但实际序列化仍不同

### Mitigation

- 单一 `build_mechanism_context_view()` + slice serializer；
- persisted view/slice artifact；
- source/view/slice/shared-payload/request 五级 digest；
- Formalizer/Writer shared payload byte-identical；
- core detail set equality；
- 禁止两个模块分别调用不同 compact helper。

---

## Risk H：Symbol resolver 误绑同名函数

### Mitigation

resolver 优先：

```text
symbol_id > exact path+qualified_name > globally unique qname > unresolved
```

禁止模糊猜测同名 definition。

---


## Risk I：`MechanismDetail` 重新成为 information bottleneck

### Mitigation

- EvidenceClosure 与 PaperDetails 同属一个 canonical context；
- EvidenceClosure 先冻结；
- semantic compiler无权改变 source membership；
- source_operation_terminal_coverage=1.0；
- repository detail source binding=1.0。

## Risk J：active/inactive helper 被错误提升为论文主线

### Mitigation

- active-path resolution 先于 importance；
- entrypoint/config/default precedence typed；
- inactive_default/unreachable默认非 core；
- unknown path不能 repository_verified core。

## Risk K：三项目 fixture 反向污染通用 harness

### Mitigation

- fixture metadata区分 repo-derived vs paper/oracle；
- hard gate只用 repo_verifiable；
- WP-9.5 pre-frozen holdout；
- 禁止 project-name/function-name special casing。

## Risk L：shared context “digest 相同但实际 payload 不同”

### Mitigation

- four/five-level digest；
- shared_payload_digest按实际 ordered slices计算；
- byte-identical tests；
- core detail set equality。

## Risk M：新系统质量提高但 token/call 成本失控

### Mitigation

- WP-0 先冻结成本基线与 tolerance；
- tokens_per_validated_core_detail 等 Pareto 指标；
- production budget超限需显式 waiver；
- 不允许通过 silent truncation 降成本。

# 21. Legacy Components：保留、改造、删除清单

| Component | Decision | Reason |
|---|---|---|
| `MethodArgumentBriefV1` | 保留 | author/story → technical research 的稳定意图入口 |
| `AuthorMechanismFacetV1` | 保留 | 将粗 author intent 分解为字段级 research seed |
| `FacetEvidenceAlignmentV1` | 保留 | 精确 intent-code alignment / authority |
| `PublicationFieldCandidateV1` | 可保留上游/兼容 | field-level policy有价值，但不再直接成为 Writer主要 target |
| `ResearchMechanismDossierV1` | 兼容保留 | 其内部 graph/fact logic迁移；paragraph-bound role退役 |
| `MethodUnitV2` | legacy保留 | 历史 artifact；technical role退役 |
| `SemanticArgumentFrameV1` | legacy/analysis保留 | 不再作为 Writer唯一 truth |
| `PublicationAuthoringPacketV2` | 最终删除 | redundant technical re-encoding |
| `_compact_authoring_packets_v2_for_llm` | unified路径删除 | 主要信息损失源 |
| `MechanismEquationEvidencePackV1` | 改为 context-derived adapter | formula 仍需要 narrow view |
| `MethodFormulaObligationV2` | legacy adapter | unified technical ownership改由 MechanismFormulaObligationV1；旧 paragraph fields 不得反向授权 |
| `SectionFormulaPackageV1` | legacy adapter/升级 | unified 内部用 MechanismFormulaPackageV2；保留强 formula guards |
| Binder / Transaction | 保留并简化 | 高价值后置验证 |
| Candidate/Verified split | 保留 | 核心安全与产品语义 |
| Callback supervisor | 改为 mechanism/detail owner | 降低无关重写与 regression |
| oracle / method regression | 强化 | 架构迁移核心 offline 评测 |

---

# 22. Recommended Commit / Work-Package Breakdown

为避免 schema、compiler、Formalizer、Writer、Binder 一次混合，建议按以下 commit/work-package 顺序推进。

### WP-0 — Freeze unified-context regression + efficiency baseline

- three-project replay snapshot；
- diagnostic fixture provenance metadata；
- information funnel；
- token/call/callback baseline；
- cross-repo holdout selection protocol；
- no production behavior change。

### WP-1 — Add canonical context models + digest rules

- EvidenceClosure / EvidenceOperation；
- PaperDetail；
- WitnessAtom；
- shared ownership；
- source/view/slice/shared-payload/request digest；
- serialization/validator tests。

### WP-2 — Lossless evidence closure compiler

- seed + fact/claim/equation closure；
- graph closure；
- DefinitionResolver；
- active/default path resolution；
- source membership artifact；
- **no semantic Detail compiler yet**。

### WP-3 — EvidenceClosure → PaperDetails

- deterministic clustering；
- ordinal-only semantic annotation；
- witness atoms；
- importance；
- three-axis authority/policy；
- shared ownership；
- source-operation disposition coverage；
- context quality trace。

### WP-4 — Single shared LLM projection

- one view builder；
- explicit slices；
- byte-identical shared payload tests；
- no consumers switched yet。

### WP-4.5 — Mechanism Formula Obligation Compiler

- paragraph-independent formula semantic ownership；
- source detail/operator/operand/condition contract；
- legacy `MethodFormulaObligationV2` adapter only。

### WP-5 — Mechanism Formalizer

- shared payload；
- mechanism-owned obligations；
- formula guards；
- legacy formula result adapter；
- no section fallback。

### WP-6 — Narrative Architect V3

- thin plan；
- core/shared detail placement；
- FormulaPackage placement；
- dual-run plan comparison。

### WP-7 — Writer V3 shadow/cutover

- exact shared payload；
- NarrativePlan；
- accepted FormulaPackages；
- no AuthoringPacketV2 technical compact；
- side-by-side candidate + cost metrics。

### WP-8 — Detail-atom Binder / Trace V2

- detail/formula wire target；
- atomic witness obligations；
- lifecycle funnel；
- structural exit adaptation；
- Formula placement validation。

### WP-8.5 — Callback V2

- mechanism/detail unresolved owner；
- semantic-delta fulfillment；
- incremental resume；
- callback token metrics。

### WP-9 — DYG / LinearRAG / EBCAR live replay

- repo-verifiable hard gates；
- blind/oracle diagnostics；
- formula fidelity；
- active-path semantics；
- efficiency Pareto；
- rollback evidence。

### WP-9.5 — Cross-repository stress set

- pre-frozen holdout；
- no project-specific repair rules；
- same architecture invariants；
- generalization report。

### WP-10 — Remove legacy production path dependencies

- no AuthoringPacketV2 in unified mode；
- no technical MethodUnit dependency；
- no paragraph ResearchDossier authority；
- no paragraph-owned formula obligation；
- no whole-section fallback；
- documentation cleanup。

每个 WP 独立：

```text
pytest
compileall
git diff --check
schema compatibility check
```

WP-5 后每个 work package 至少跑 one-project replay smoke；WP-9/9.5 必须完整 live replay。

# 23. Rollback Strategy

本次大修必须有明确 rollback boundary。

只保留一个 mode：

```text
legacy
shadow_unified
unified
```

任何阶段若：

- context compile fails；
- core detail recall 下降；
- formula contamination；
- Candidate critical semantic error增加；

可切回 `legacy`，而不需要 revert schema commits。

**禁止** 在 unified path 发生异常时自动 silently fallback 到 legacy technical content，并仍标记为 unified success。正确行为：

```text
unified failed
→ status=blocked/incomplete
→ explicit failure
```

否则 benchmark 无法判断新架构是否真的工作。

---

# 24. What Not To Do

本次重构明确不建议：

1. **不要**直接让 Writer 吃 Formalizer 当前 section payload；其 scope 仍是 paragraph-derived，且有 section fallback。
2. **不要**仅把 `dossier.operation_atoms=[]` 改掉然后继续现有全部 IR；这只能缓解一处 loss，无法解决多层 technical truth。
3. **不要**继续给 `MethodUnitV2` 加更多字段试图“不丢信息”；这会让第二 technical IR 越来越重。
4. **不要**把 Formalizer 与 Writer 合成同一个 LLM call；二者角色不同，统一的是数据，不是 agent。
5. **不要**删除 Binder/Verified fail-closed；富上下文不等于弱验证。
6. **不要**使用原论文或 blind baseline 作为 runtime evidence。
7. **不要**为了 recall 把整个 repository dump 给 Writer。
8. **不要**用更多 callback rounds掩盖 mechanism scope 错误。
9. **不要**使用 project-specific hard-coded marker 作为长期 mechanism taxonomy。
10. **不要**在 token budget 超限时 silently truncate core details。

---

# 25. Expected End State

如果本方案正确实施，一个完整的 mechanism 应表现为：

```text
Author intent:
  "Entity activation via semantic bridging"

Repository evidence closure:
  default non-vectorized active path
  seed entities / linked sentences
  query-sentence similarity
  sentence→entity propagation
  iteration_threshold pruning
  active frontier / stopping
  optional vectorized helper = inactive_default/alternative
  Stage2 PPR = separate mechanism

             ↓

MechanismContext: entity_activation
  EvidenceClosure: all bounded operations + active-path states
  PaperDetails:
  D1 seed initialization
  D2 entity→sentence propagation
  D3 query-sentence weighting
  D4 sentence→entity propagation
  D5 dynamic pruning
  D6 stop/frontier

             ├──────────────→ Formalizer
             │                 formula over D2–D5
             │
             └──────────────→ Architect
                               place in Stage1, 2 paragraphs
                                      │
                                      ▼
Writer receives:
  SAME D1–D6 context
  + narrative placement
  + validated formula

             ↓

Candidate:
  coherent Stage1 explanation
  + formula
  + implementation details
  + transition to Stage2

             ↓

Binder:
  sentence 1 ↔ D1/D2 required witness atoms
  formula ↔ D2–D5 formal-relation atoms
  sentence 3 ↔ D5/D6 condition/polarity/output atoms

             ↓

Verified:
  only repository-authorized details accepted
```

而不再是：

```text
Research finds D1–D6
→ MethodUnit keeps D2/D5
→ packet hides dossier
→ Formalizer falls back to whole section
→ Writer sees D2/D5 + sibling PPR
→ short paragraph + wrong formula
```

---

# 26. Final Architectural Recommendation

本次重构应被定义为：

> **从“paragraph-contract-first authoring”迁移到“mechanism-context-first authoring”。**

当前架构最初为解决 hallucination、可验证性、formula binding、paragraph transaction 等问题不断增加中间 contract，这些 contract 各自都有合理局部动机；但累积后造成了新的系统性问题：**每层都在重新解释上一层技术信息，最终 production surface 只保留最小可验证 spine。**

新的设计不应回到无约束 raw-code writing，而应收敛成三个清晰层次：

```text
1. Scientific Technical Layer
   MechanismContextV1
   ├─ EvidenceClosureV1 — lossless source truth
   └─ PaperDetailsV1 — paper-facing annotation
   — 高 recall、mechanism-local、evidence-bound

2. Narrative Layer
   NarrativePlanV3
   — 只决定怎么讲、讲多深、放哪里

3. Validation Layer
   Binder / Validator
   — 证明写出来的每个关键 detail / formula 仍然有合法来源
```

Formalizer 与 Writer 位于第 1 和第 2 层之间：

- 两者对 scientific mechanism 共享同一事实世界；
- Formalizer只增加数学表达；
- Writer只增加论文叙事；
- 谁都不能通过独立的中间投影改写 technical truth。

这同时解决当前最关键的两类质量问题：

### Faithfulness

通过：

```text
exact evidence
+ typed authority
+ detail witness atoms
+ active-path precedence
+ formula guards
+ Verified fail-closed
```

保证。

### Completeness / Publication-readiness

通过：

```text
high-recall mechanism compilation
+ core-detail preservation
+ shared Writer/Formalizer context
+ mechanism-aware paragraph planning
+ explicit information-funnel metrics
```

保证。

因此，本方案不建议继续将主要研发投入放在现有 MethodUnit compaction、slot first/last selection、AuthoringPacket compact 或更多 callback rounds 上。那些机制可以在 legacy mode 中维持稳定，但新的主线应围绕 **Unified Mechanism Context** 建立，并以 DYG、LinearRAG、EBCAR 三个真实项目的 mechanism-detail recall + formula fidelity + publication usability 作为切换依据。

---

# Appendix A. Current → Target Mapping

```text
CURRENT                                      TARGET
────────────────────────────────────────────────────────────────────────────
MethodArgumentBrief                ────────→ keep
AuthorMechanismFacet               ────────→ keep as research seed
FacetEvidenceAlignment             ────────→ keep as authority/evidence bridge
PublicationFieldCandidate          ────────→ upstream policy / compat

CodeFact / BehaviorGraph / spans    ──┐
ResearchMechanismDossier source IR  ──┼────→ MechanismEvidenceClosureV1
DefinitionResolver / configs        ──┘       (lossless source foundation)

SemanticArgumentFrame              ──┐
MethodUnitV2 technical fields       ──┼────→ MechanismDetailV1 annotations
PublicationAuthoringPacketV2       ──┘       + DetailWitnessAtomV1

MethodSectionPlanV2 technical IR   ────────→ NarrativePlanV3

MethodFormulaObligationV2          ────────→ MechanismFormulaObligationV1
                                         (semantic owner before Architect)
SectionFormulaPackageV1            ────────→ MechanismFormulaPackageV2
                                         + FormulaPlacementV1

Section Formalizer                 ────────→ Mechanism Formalizer
section/paragraph evidence packs   ────────→ shared MechanismContext payload

Writer compact packet              ────────→ shared MechanismContextView/Slices

facet/field/slot/edge transaction  ────────→ detail/formula wire contract
                                         + per-detail witness atoms

MethodContentTraceV1               ────────→ source→detail→payload→render lifecycle trace V2
```

# Appendix B. Mandatory Shadow Artifacts During Migration

建议统一输出：

```text
06_authoring/
  mechanism_evidence_closures_v1.json
  mechanism_contexts_v1.json
  mechanism_context_views_v1.json
  mechanism_context_slices_v1.json
  mechanism_formula_obligations_v1.json
  mechanism_formalization_v2.json
  narrative_plan_v3.json
  publication_writer_result_v3.json
  mechanism_information_funnel_v2.json
  consumer_payload_digest_trace_v1.json
  token_efficiency_report_v1.json

07_validation/
  source_operation_disposition_report_v1.json
  active_path_validation_v1.json
  mechanism_detail_trace_v2.json
  detail_atom_transaction_assessment_v2.json
  formula_fidelity_report_v1.json
  mechanism_contamination_report_v1.json
  publication_quality_report_v2.json
  cross_repo_generalization_report_v1.json
```

Shadow mode 下 legacy artifacts 继续存在，方便逐字段/逐 operation 对比；但 unified success 不能由 legacy fallback 掩盖。

# Appendix C. Definition of Done

本次 architecture refactor 只有同时满足以下条件才算完成：

### Canonical technical truth

- [ ] `MechanismContextV1` 是 unified production 唯一 canonical technical IR；
- [ ] Context 内显式区分 EvidenceClosure 与 PaperDetails；
- [ ] Context 在 Architect 之前生成；
- [ ] EvidenceClosure 在 Detail semantic compiler 前冻结；
- [ ] source operation membership 不被 semantic compiler 改写；
- [ ] `source_operation_terminal_coverage = 1.0`；
- [ ] repository-derived details source binding = 1.0；
- [ ] active/default path resolution 已进入 production invariant；
- [ ] inactive/unreachable helper不能默认 core。

### Shared consumer contract

- [ ] source/view/slice/shared-payload/request digest 全部实现；
- [ ] Formalizer 与 Writer 对共享 mechanism 的 payload bytes identical；
- [ ] core detail IDs identical；
- [ ] no role-specific technical deletion；
- [ ] no local→section evidence fallback；
- [ ] callee definition 可经 SymbolIndexV2 + SourceProvider 闭合。

### Formula ownership

- [ ] `MechanismFormulaObligationV1` paragraph-independent；
- [ ] unified Formalizer 不依赖 legacy paragraph/slot/edge obligation ownership；
- [ ] FormulaPackage 绑定 mechanism/detail；
- [ ] paragraph placement由 NarrativePlan后置产生；
- [ ] critical formula semantic error = 0。

### Narrative / Writer

- [ ] Architect 不再编译 technical operations；
- [ ] unified Writer 不经过 `PublicationAuthoringPacketV2` technical path；
- [ ] unified Writer 不调用 `_compact_authoring_packets_v2_for_llm()` technical compact；
- [ ] all clean-candidate core details delivered；
- [ ] claim_kind/evidence_authority/publication_policy 生效。

### Binder / trace

- [ ] Binder external taxonomy 为 detail/formula；
- [ ] 每个 required detail 有 deterministic witness atoms；
- [ ] missing required atom / condition / polarity fail；
- [ ] MethodContentTrace 能定位 R0–R4 loss；
- [ ] Candidate persistence + Verified fail-closed 未回归。

### Evaluation / generalization

- [ ] DYG/LinearRAG/EBCAR fixture 全部标注 repo_snapshot/repo_verifiable/active_path；
- [ ] hard gates只消费 repo-verifiable units；
- [ ] blind/oracle remain diagnostic_non_authorizing；
- [ ] WP-9.5 pre-frozen cross-repo stress set通过；
- [ ] no project-specific production marker；
- [ ] unsupported positive claims 不增加。

### Efficiency / cleanup

- [ ] WP-0 efficiency baseline 和 predeclared production budget 已冻结；
- [ ] token/call Pareto report通过或有显式批准；
- [ ] legacy mode 可明确回滚；
- [ ] legacy technical IR 依赖有实际删除，而非永久双轨。

---

# Appendix D. Review Decision Record（2026-09-05 targeted revision）

本附录记录对执行前审核意见的采纳决策，避免开发过程中再次重新讨论关键 contract。

| Review item | Decision | Integration |
|---|---|---|
| MechanismDetail 可能成为新的 lossy gate | **采纳，且提升为核心修正** | Context 拆为 EvidenceClosure + PaperDetails；source membership 先冻结；operation terminal coverage=1.0 |
| shared digest 不足以证明消费者看到同一信息 | **采纳** | 增加 source/view/slice/shared-payload/request digest；shared payload byte-identical |
| 三项目 hard gate 可能混入 oracle/paper knowledge | **采纳** | expected unit 增加 repo snapshot / repo_verifiable / active-path metadata；paper只做 usability |
| Binder 只用 detail_id 太粗 | **采纳** | 增加 deterministic DetailWitnessAtomV1；required atoms 全闭合才 valid |
| Formalizer cutover仍受 legacy formula ownership污染 | **采纳** | 增加 Phase/WP-4.5 Mechanism Formula Obligation Compiler |
| Authority 是单轴 | **采纳** | 拆 claim_kind / evidence_authority / publication_policy |
| Active/default path 定义不足 | **采纳** | I4 Active-Path Precedence；独立 active path compiler stage |
| mechanism/detail 单 owner 太严格 | **部分采纳** | canonical primary owner保持唯一；增加 shared/secondary refs，避免复制 truth |
| 缺少 efficiency gate | **采纳** | WP-0 冻结 token/call baseline；WP-9 production Pareto gate |
| 只用三项目 cutover 容易过拟合 | **采纳** | 新增 WP-9.5 pre-frozen cross-repo stress set |
| `calculate_entity_scores_vectorized` 必须成为 LinearRAG Stage1 主线 | **不采纳这种解读** | 它只作为 DefinitionResolver regression；active/default path决定是否 mainline。当前 frozen diagnostic显示 optional vectorized branch 默认关闭 |
| 交换 Architect 与 Formalizer 顺序 | **不采纳** | 保持 Formula technical ownership在 Architect 前；通过 WP-4.5 解耦，而不是让 Architect 决定公式语义 |

结论：审核意见没有改变 `mechanism-context-first` 总方向；它主要收紧了**losslessness、ownership、active-path、digest 与 validation granularity**，因此属于 targeted architecture revision，而不是重新设计。

---

# Appendix E. Audit Source Inventory

本方案的具体判断基于以下已实际审计材料；它们的用途被严格区分为 production truth 与 diagnostic reference。

## E.1 Current production code（production truth for architecture）

Branch/SHA：

```text
hjcui98/code2paper
codex/agentic-p4-benchmark-cutover
a7c10318e0edd554533962d1ce6159ce51751291
```

重点代码：

```text
src/code2paper/agentic/publication_method_writer.py
src/code2paper/agentic/method_architect.py
src/code2paper/agentic/method_argument_models.py
src/code2paper/agentic/method_argument_brief_models.py
src/code2paper/agentic/method_argument_brief_compiler.py
src/code2paper/agentic/method_argument_facet_aligner.py
src/code2paper/agentic/research_derived_authoring.py
src/code2paper/agentic/formalization_agent.py
src/code2paper/agentic/publication_transaction_contract.py
src/code2paper/agentic/method_content_trace.py
src/code2paper/agentic/method_content_regression.py
src/code2paper/agentic/python_behavior_adapter.py
src/code2paper/llm/section_writer.py
```

重点当前定义位置（基线 SHA）：

```text
ResearchMechanismDossierV1       research_derived_authoring.py ~515
PublicationAuthoringPacketV2     research_derived_authoring.py ~645
build_publication_authoring_packets() ~2160
MethodUnitV2                     method_argument_models.py ~760
SectionParagraphPlanV1           method_argument_models.py ~987
ParagraphWitnessTargetV1         method_argument_models.py ~854
_compact_authoring_packets_v2_for_llm() section_writer.py ~760
_llm_visible_section_payload()   section_writer.py ~1158
```

## E.2 Latest live replay artifacts（diagnostic production evidence）

```text
artifacts/quality_closed_loop/2026-09-05/nextrepair-8006-qwen38/
  dyg/
  linearrag/
  ebcar/
```

重点审计：

```text
replay.stdout.log
artifacts/research_product/method_content_trace_v1.json
artifacts/research_product/method_generation_trace_v1.json
artifacts/06_authoring/formalization_section_results_v1.json
artifacts/06_authoring/publication_writer_result_v1.json
artifacts/06_authoring/publication_candidate_method.md
artifacts/06_authoring/author_review_candidates.json
```

## E.3 Blind baselines（diagnostic high-recall reference; never runtime authority）

```text
artifacts/quality_closed_loop/2026-09-02/blind_baseline/dyg/
artifacts/quality_closed_loop/2026-09-02/blind_baseline/linearrag/
artifacts/quality_closed_loop/2026-09-02/blind_baseline/ebcar/
```

重点：

```text
method_candidate.md
baseline_audit.md
baseline_result.json
```

其意义是证明：在不看原论文的情况下，仅依靠 author intent + repository，完整 mechanism detail 的可恢复上限明显高于当前 automated Writer output。

## E.4 Existing diagnostic regression fixtures

```text
tests/fixtures/method_synthesis_funnel/original_oracle_v1.json
tests/fixtures/method_synthesis_funnel/baselines_v1.json
tests/fixtures/post_r8_method_content_regression_v1.json
```

这些 fixture 应继续保持 `diagnostic_only`，用于测量 architecture information funnel，不得向 production Candidate 提供事实。

## E.5 Original papers（diagnostic publication-structure reference only）

```text
DyG-Mamba: Continuous State Space Modeling on Dynamic Graphs
LinearRAG: Linear Graph Retrieval Augmented Generation on Large-scale Corpora
Embedding-Based Context-Aware Reranker (EBCAR)
```

审计重点不是要求 Code2Paper 复刻原文，而是检查 publication-ready Method 通常是否连续表达：

```text
rationale / purpose
→ representation / input
→ ordered mechanism transformations
→ conditions / branches
→ equations
→ outputs / downstream interface
```

所有 code-vs-paper 冲突仍以当前 repository implementation 为 Method implementation truth。
