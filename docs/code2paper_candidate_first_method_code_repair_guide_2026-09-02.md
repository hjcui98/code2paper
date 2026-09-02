# Code-to-Paper Candidate-first Method：代码级修复与优化指南

- 日期：2026-09-02
- 仓库：`hjcui98/code2paper`
- 分支：`codex/agentic-p4-benchmark-cutover`
- 审计 HEAD：`2ea848648f80e9e3d8a69d5cf4806183558fea8f`
- sixrepair 主代码提交：`94f96efc40947867c6ba2c9db462bca8f865161e`
- 权威目标：`.agent/task.md` — Candidate-first Method quality repair
- 最新真实回归集：
  - `artifacts/quality_closed_loop/2026-09-01/sixrepair/ebcar/`
  - `artifacts/quality_closed_loop/2026-09-01/sixrepair/dyg/`
  - `artifacts/quality_closed_loop/2026-09-01/sixrepair/linearrag/`
- 本文目标：**给下一轮实现提供直接可执行的代码级修复方案；不重构整个 Agent，不弱化 Verified fail-closed，不做 project-specific hard-code。**

---

# 0. 结论先行

当前系统已经解决了一批底层问题：

- Candidate 可持久保存，不再被 Verified 失败删除；
- display math 能进入正文；
- `self.` 等代码泄漏显著下降；
- Formalizer 已经可以生成 academic formula；
- formula block 已 canonicalize，Markdown memo 不再整体注入正文；
- callback 可以在 no-delta 时停止；
- Verified 始终 fail-closed。

但最新 `sixrepair` 真实产物仍然没有达到统一可用 Method draft：

| 项目 | 当前评价 | 关键症状 |
|---|---|---|
| EBCAR | **rough Method draft，可继续人工改** | 重复 InfoNCE、code-shaped `logsumexp`、残缺 H2、公式 ownership 不唯一 |
| DyG-Mamba | **technical/content draft，不足以直接交稿** | Motivation 顺序错、`edge_memories` 泄漏、理论 claim 过强、部分公式并非可靠代码抽象 |
| LinearRAG | **明显 regression，不应作为当前 Method draft** | 2291 B；无 display math；第一阶段 retrieval / semantic bridging / pruning 缺失；callback no-progress |

当前最重要的共同根因不是“模型不够强”，也不是“validator 太严格”，而是三条数据通路仍不完整：

```text
1. frozen evidence
   → 旧 reader-facing MethodUnit/paragraph surface 被一起冻结

2. claim / author intent
   → Formalizer 只看到 operation atoms / 函数名
   → 没看到足够连续的实现上下文

3. private implementation representation
   → V2 Writer packet
   → subject / operands / result 等仍可能原样泄漏
```

下一轮应聚焦以下 5 个修复：

```text
P0-A  修 reuse-derived-authoring：证据可复用，reader surface 必须刷新
P0-B  修 LinearRAG research callback：从 semantic question 搜索，不搜 bookkeeping id
P0-C  Formalizer 改成 claim-centered AI code formalization
P0-D  一个 mechanism 只允许一个 canonical paper formula
P0-E  V2 Writer packet 做统一 paper-language projection
```

其他修复暂缓。

---

# 1. 最新真实产物基线

## 1.1 EBCAR

sixrepair Candidate 已经形成：

```text
Motivation
→ embedding-based reranking
→ architecture
→ training
→ inference
```

主要正向进展：

- structural augmentation 已写成 academic notation；
- hybrid attention 有 display math；
- InfoNCE 有正确 academic formula；
- inference 有公式；
- `self.` 已清零；
- Candidate 约 6 KB；
- 5/7 required paragraphs valid；
- 8/11 slots witnessed。

但存在四个明显问题：

### 问题 E1：同一 InfoNCE 被写三次

正文同时出现：

1. 一个损坏的 inline InfoNCE；
2. 一个正确的 academic display formula；
3. 一个 code-shaped：

```latex
\mathcal{L}_i =
-\text{pos_sim}
+
\text{logsumexp}(\text{all_sims}, \text{dim}=0)
```

说明 formula ownership 没闭合。

### 问题 E2：正文仍允许 Writer 自己“重新发明”公式

即使 Formalizer 已提供 canonical academic package，Writer 仍会另写 inline/formula prose。

### 问题 E3：`## Training objective:` 三轮均残缺

这属于 presentation hygiene，不应继续用复杂 Agent 处理。

### 问题 E4：部分公式和 prose 的 notation 不统一

例如 passage augmentation / contextualized passage / transformer output 的符号没有完全统一。

---

## 1.2 DyG-Mamba

sixrepair 已恢复较多内容：

- graph encoding；
- heterogeneous features；
- Δt / A；
- B/C；
- downstream；
- robustness discussion；
- 4 个 display math。

但仍有：

```text
Dynamic graph encoding
→ Motivation
→ Redesign
```

顺序错误。

正文还残留：

```text
(src_node, dst_node) in edge_memories
```

并出现值得怀疑的数学表达，例如：

```latex
B_i = \frac{B_i^{raw}}{\|B_i^{raw}\|_2}
```

它未必等价于源码中对 projection matrix 使用 spectral normalization。

理论 prose 还存在：

```text
invariant to scale
ensure stable selective reviewing
```

这类从局部约束升级到全局稳定/鲁棒性的风险。

---

## 1.3 LinearRAG

当前 sixrepair 是最大 regression：

```text
Candidate bytes: 2291
rendered paragraphs: 0 / 5
slots: 0 / 16
display math: 0
callback fulfilled: 0
```

正文只保留：

- Tri-Graph；
- offline construction；
- high-level PPR stage。

缺失：

- 真正的 Motivation rationale；
- semantic bridging；
- iterative entity activation；
- dynamic pruning；
- 第一阶段数学公式；
- hybrid passage initialization 的完整公式；
- 完整 PPR 数学叙述。

Formalizer trace 证明 LLM 并非不会生成：

MA-S4 author-intent lane 已生成：

```text
Initialization
Propagation
Pruning
```

公式 package，但最后只进入 `review_required`，没有消费。

MA-S5 也多次尝试生成 PPR / hybrid initialization，但因：
- code-shaped；
- document command；
- theoretical upgrade；

被 guard 拦下。

因此 LinearRAG 的根因是：

> **上游 Research/Formula packet 没把足够的实际实现上下文交给模型；author-intent fallback 又太自由。**

---

# 2. P0-A：修复 `--reuse-derived-authoring` 的语义

这是第一优先级。

---

## 2.1 当前真实代码路径

`sixrepair/run_serial.sh` 明确调用：

```bash
python -u scripts/run_authoring_replay.py \
  ... \
  --reuse-derived-authoring
```

当前 `method_architect.py`：

```python
if prior_plan is not None and prior_plan.method_units:
    method_units, graphs, method_unit_trace = _preserve_incumbent_method_unit_surface(
        prior_plan=prior_plan,
        rebuilt_sections=list(graphs),
    )
    units = list(prior_plan.argument_units)
else:
    method_units, graphs, method_unit_trace = _build_method_units_v2(...)
```

而 `_preserve_incumbent_method_unit_surface()` 当前核心行为：

```python
preserved.append(graph.model_copy(update={
    "paragraphs": prior.paragraphs,
    "argument_unit_ids": prior.argument_unit_ids,
}))

...

return (
    tuple(prior_plan.method_units),
    preserved,
    ...
)
```

这意味着：

```text
fresh evidence / fresh facets / fresh sixrepair code
        ↓
prior_plan.method_units exists
        ↓
old MethodUnits are returned wholesale
        ↓
new rationale selection / sentence budget / reader projection is bypassed
```

这正是 LinearRAG rationale 修复静态通过、live 不生效的核心原因。

---

## 2.2 正确语义

`reuse-derived-authoring` 应该复用：

```text
research evidence
facts
claims
configuration
equation atoms
stable section identity
stable source bindings where still valid
```

不应该复用：

```text
old reader-facing MethodUnit content
old paragraph semantic grouping
old selected rationale facets
old sentence budget
old section rhetorical order
```

正确关系：

```text
prior plan = identity/stability hint
current derived artifacts = reader-surface authority
```

而不是：

```text
prior plan = complete reader surface authority
```

---

## 2.3 最小实现方案

不要删除 `_preserve_incumbent_method_unit_surface()`。

把它改成 **refresh/merge**，而不是 full preserve。

建议新增：

```python
def _refresh_incumbent_method_unit_surface(
    *,
    prior_plan: MethodSectionPlanV2,
    rebuilt_method_units: tuple[MethodUnitV2, ...],
    rebuilt_sections: list[SectionArgumentGraphV1],
) -> tuple[
    tuple[MethodUnitV2, ...],
    list[SectionArgumentGraphV1],
    dict[str, Any],
]:
    ...
```

然后主路径改为：

```python
rebuilt_method_units, rebuilt_graphs, rebuilt_trace = _build_method_units_v2(
    graphs,
    units,
    argument_facets=argument_facets,
    facet_alignments=facet_alignments,
    publication_field_candidates=publication_field_candidates,
    facts=facts,
    unit_frames=unit_frames,
)

if prior_plan is not None and prior_plan.method_units:
    method_units, graphs, method_unit_trace = _refresh_incumbent_method_unit_surface(
        prior_plan=prior_plan,
        rebuilt_method_units=rebuilt_method_units,
        rebuilt_sections=rebuilt_graphs,
    )
else:
    method_units, graphs, method_unit_trace = (
        rebuilt_method_units,
        rebuilt_graphs,
        rebuilt_trace,
    )
```

---

## 2.4 Refresh 时保留什么

保留：

```python
section_id
plan-level stable identity
compatible source obligation ids
compatible formula consumer identity
```

重新计算：

```python
required / representative rationale facets
MethodUnit ordered facets
reader-facing ordered operations
paragraph_role
expected_sentence_range
reader ordering
paragraph grouping
```

---

## 2.5 不要直接按 index 合并

避免：

```python
new_method_units[i] ↔ old_method_units[i]
```

用稳定语义 key：

```python
(section_id, source_obligation_ids)
```

或：

```python
(section_id, argument_unit_ids)
```

匹配。

只要语义 owner 变化，优先新 surface。

---

## 2.6 Fallback

如果 fresh `_build_method_units_v2()` 因 legacy artifact 缺字段无法构造：

```python
if not rebuilt_method_units:
    return _preserve_incumbent_method_unit_surface(...)
```

这样不破坏旧 replay。

---

## 2.7 必加 trace

不要加新大 schema。

现有 `method_unit_trace` 增加：

```json
{
  "reuse_mode": "refresh_reader_surface",
  "prior_method_units": 5,
  "rebuilt_method_units": 5,
  "refreshed_method_units": 5,
  "preserved_identity_count": 5,
  "preserved_surface_count": 0,
  "fallback_to_prior_surface": false
}
```

用于确认 live 到底走了哪条路径。

---

# 3. P0-A 的测试

新增一个高价值 synthetic regression：

```python
def test_reused_plan_refreshes_reader_surface_with_new_rationale():
    # prior plan:
    #   Motivation paragraph only has mechanism facet
    #
    # current facets:
    #   same section + new optional rationale facet
    #
    # expected:
    #   section id stays stable
    #   current MethodUnit contains rationale
    #   old paragraph surface is not returned wholesale
```

断言：

```python
assert refreshed.sections[0].section_id == prior.sections[0].section_id
assert rationale_facet_id in refreshed.method_units[...].facet_ids
assert trace["fallback_to_prior_surface"] is False
```

再加 reader-order regression：

```text
prior:
    mechanism
    motivation

fresh rhetorical classification:
    motivation = pure context

expected:
    motivation
    mechanism
```

---

# 4. P0-B：修 LinearRAG callback query compiler

---

## 4.1 当前问题

当前 `writer_research_router.py` 的：

```python
directed_search_terms_from_texts()
```

只是从文本 token 中抽取：

- 长单词；
- uppercase；
- 下划线 token；
- Δ / δ；
- 数字。

然后：

```python
fill_writing_research_search_terms()
```

优先把这些 token 填入：

```python
candidate_symbols_or_terms
```

这本身没错，但如果上游 `missing_parts` 包含：

```text
facet-8ce6e8dabb55bf84
```

这种 bookkeeping identity，就可能进入检索。

上一轮 replay 已经出现类似：

```text
search for conceptual aspect corresponding to facet-...
```

这是错误层级。

---

## 4.2 原则

Research callback 不应该搜索：

```text
facet id
brief id
paragraph id
obligation id
claim id
```

这些只是内部 identity。

应该搜索：

```text
author claim
semantic field
mathematical goal
reader-facing mechanism text
known nearby code symbols
```

---

## 4.3 最小代码修改

在 `writer_research_router.py` 增加 internal-id filter：

```python
_INTERNAL_ID_RE = re.compile(
    r"^(?:facet|brief|paragraph|claim|formula|obligation|method-unit|MA-S)"
    r"[-:_][A-Za-z0-9:_-]+$",
    re.IGNORECASE,
)

def _is_internal_research_identifier(token: str) -> bool:
    return bool(_INTERNAL_ID_RE.match(token.strip()))
```

在：

```python
directed_search_terms_from_texts()
```

中：

```python
if _is_internal_research_identifier(token):
    continue
```

但这只解决表面问题。

---

## 4.4 更重要的上游修改

生成 `WritingResearchRequestV1` 时，`missing_parts` 应优先放：

```python
facet.semantic_fields.values()
facet.author_statement
formula_obligation.mathematical_goal
paragraph.reader_goal
known nearby symbols
```

不要放：

```python
facet_id
target_id
paragraph_id
```

建议构造：

```python
research_texts = [
    facet.reader_facing_claim,
    *facet.semantic_fields.values(),
    author_statement,
    formula_obligation.mathematical_goal,
]
```

再：

```python
candidate_symbols_or_terms = directed_search_terms_from_texts(*research_texts)
```

---

## 4.5 不要让 token extractor 承担语义理解

如果 callback owner 本身是 LLM supervisor，可以直接给它：

```yaml
research_question:
  author_claim:
  missing_semantics:
  mathematical_goal:
  known_symbols:
```

模型生成实际 search plan。

deterministic token extractor 只作为 fallback。

---

# 5. P0-C：Formalizer 改为 claim-centered AI code formalization

这是第二个最重要的结构修复。

---

## 5.1 当前 Formalizer 的问题

当前已经有：

```python
MethodFormulaObligationV2
MechanismEquationEvidencePackV1
SectionFormulaPackageV1
```

这是好的。

但真实 trace 中 Formalizer 经常说：

```text
core_equations is empty
authorized_equation_ids is empty
operation atoms only describe procedural calls
therefore cannot formalize
```

说明 Formalizer 仍然把：

```text
equation_claims / operation atoms
```

当成数学信息的核心来源。

对于 Code-to-Paper 不够。

---

## 5.2 正确理念

公式的主要来源应该是：

```text
author claim
+
current paragraph scientific purpose
+
connected source code slice
+
data flow
+
tensor/shape hints
+
branch/config conditions
```

即：

```text
code = raw mathematical specification
AI = mathematical abstraction engine
rules = factual boundary validator
```

而不是：

```text
AST equation atom = formula source
AI = formatter
```

---

# 6. 复用现有 `MechanismEquationEvidencePackV1`，不要新造巨大 schema

当前已有：

```python
class MechanismEquationEvidencePackV1:
    operation_atoms
    exact_span_ids
    exact_excerpts
    preconditions
    shape_or_type_hints
    author_statements
    bound_fact_ids
    bound_equation_ids
    connected
```

这个模型足够接近需求。

不要新增 FormulaResearchGraph / MathIR / EquationAST 等大型中间层。

只做两点：

### 6.1 确保 `exact_excerpts` 是连续代码上下文

当前不能只是：

```text
calculate_entity_scores_vectorized(...)
run_ppr(...)
node_weights = entity_weights + passage_weights
```

需要把相关实现段落真正加入：

```text
function body / connected relevant slice
```

例如 LinearRAG MA-S4：

```text
entity initialization
sentence similarity
sentence → entity propagation
max / accumulation
threshold filter
```

MA-S5：

```text
passage similarity
entity occurrence contribution
hybrid passage weight
personalization vector
PPR call
ranking
```

### 6.2 给 Formalizer 明确的 paragraph claim

当前 pack 有 `author_statements`，但需要在 prompt 中明确区分：

```text
SECTION CLAIM TO FORMALIZE
```

建议调用输入至少有：

```yaml
section_id:
paragraph_id:

scientific_goal:
  heading:
  paragraph_role:
  author_claim:
  mathematical_goal:

implementation:
  exact_excerpts:
  connected_operations:
  preconditions:
  shapes:

existing_equation_atoms:
  # auxiliary only
```

不必更改 Pydantic schema，也可以在 prompt builder 中组合。

---

# 7. Formalizer prompt 修改建议

当前 Formalizer 应明确收到：

```text
Your job is not to translate operation atoms literally.
Recover the paper-level mathematical formulation that best explains
the supplied section claim using the connected implementation context.

Treat repository source code as the primary mathematical specification.
Equation atoms are auxiliary evidence only.

You may introduce paper-facing symbols that do not exist as raw Python names,
provided each symbol's semantic role is grounded in the supplied code/data flow.

Prefer one compact mechanism-level formula over a line-by-line transcription.

Do not emit:
- Python function syntax
- keyword arguments such as dim=0
- raw tuple assignments
- source variable names when a paper symbol is clearer

If an exact operation cannot be uniquely recovered:
- use the narrowest formulation supported by the connected code and author claim;
- record the ambiguity in review metadata;
- do not fabricate a global guarantee.
```

---

# 8. LinearRAG 的 Formula research 应怎样工作

以 semantic bridging 为例。

不要给模型：

```text
calculate_entity_scores_vectorized()
node_weights = entity_weights + passage_weights
```

应该给：

```text
Author claim:
Query–sentence relevance propagates through sentence–entity incidence
to iteratively activate related entities, with dynamic pruning.

Relevant source excerpts:
<完整 calculate_entity_scores_vectorized 关键 slice>

Shape/data-flow:
sentence similarities: [num_sentences]
sentence→entity incidence
entity activation vector
threshold condition
```

让模型恢复类似论文级表达，但必须以当前代码为依据，而不是复制 oracle。

关键是：

> **公式来自当前代码分析，不来自原论文答案。**

---

# 9. Formalizer rules 的正确职责

保留这些 deterministic guard：

```text
target-method ownership
unknown fact/equation id
undefined symbol
added unsupported number
code-shaped formula
document-command leakage
formula consumer mismatch
global theoretical overclaim
```

但不要让 guard 决定公式内容。

正确职责边界：

```text
AI:
    understand
    abstract
    choose notation
    derive formula
    explain symbols

rules:
    constrain
    validate
    reject obvious mismatch
    track provenance
```

---

# 10. `unsupported_theoretical_upgrade` 不要过度扩大

当前 guard 是必要的，但不能把所有：

```text
decay
stability
robustness
```

词都杀掉。

建议分成两层。

允许：

```text
induces a decaying transition factor
bounds operator amplification
scales linearly with sequence length under fixed hidden size
```

阻止：

```text
guarantees global stability
is invariant to arbitrary input scaling
provably robust to noise
```

实现上不需要 theorem prover。

只需修改 pattern/prompt，让 guard 针对：

```text
guarantees
provably
invariant
globally stable
robust to arbitrary
```

这类 strong-upgrade。

---

# 11. P0-D：一个 mechanism 只允许一个 canonical paper formula

这是 EBCAR 当前最直接的问题。

---

## 11.1 当前错误行为

同一个 InfoNCE mechanism 出现：

```text
Writer inline formula
+
Formalizer academic formula
+
code-shaped logsumexp display formula
```

这说明：

```text
formula production ownership
```

没有唯一化。

---

## 11.2 新规则

对每一个：

```text
formula obligation / mathematical mechanism
```

最终 Candidate 只能有：

```text
0 or 1 canonical paper formula package
```

如果 Formalizer 已产生 accepted/review-allowed Candidate formula：

```text
Writer must consume it
Writer must not generate a second mathematical expression for the same mechanism
```

---

## 11.3 代码实现

在 Writer packet 增加非常简单的：

```python
canonical_formula_by_paragraph: dict[str, SectionFormulaPackageV1]
```

如果 paragraph 有 package：

```python
paragraph_payload["formula_packages"] = [canonical_package]
paragraph_payload["formula_generation_policy"] = "consume_only"
```

否则：

```python
formula_generation_policy = "prose_only_or_request_formalizer"
```

不要允许：

```text
Writer 自由生成 display formula
```

---

## 11.4 Writer prompt

增加：

```text
If formula_packages is non-empty, the supplied formula is the only authorized
paper-level mathematical rendering for that mechanism.

Do not restate the same mechanism as a second inline or display equation.
Explain the supplied formula in prose and define its symbols.
```

---

## 11.5 代码公式放 sidecar

像：

```python
-pos_sim + logsumexp(all_sims, dim=0)
```

这种 implementation realization：

- 可以用于验证 InfoNCE；
- 可以进入 evidence ledger；
- 不应该进入 `publication_candidate_method.md`。

---

# 12. Formula package acceptance：Candidate 与 Verified 继续分开

Candidate 可以接受：

```text
repository_derived
hybrid_partial
author_intent_academic
```

但必须有明显的内部 authority metadata。

Verified 仍只使用现有严格 lane。

不要为了 Candidate formula 可见而放宽：

```text
repository_verified_method.md
```

---

# 13. P0-E：V2 Writer packet 统一 paper-language projection

---

## 13.1 当前代码已经做了什么

当前 `section_writer.py` 对 MethodUnit operation：

```python
for item in ordered_operations:
    display = compact_operation(item)
```

之后主要清：

```python
guard
guard_variants
conditions
```

通过：

```python
_is_implementation_trace_text()
_strip_implementation_trace_values()
```

因此 `self.` 大幅下降。

---

## 13.2 当前漏掉什么

`compact_operation()` 仍可能保留：

```text
subject
operands
result/output
predicate
```

而这些字段可能包含：

```text
edge_memories
src_node_id
dst_node_id
tuple membership
raw cache/index variables
```

这正是 DyG：

```text
(src_node, dst_node) in edge_memories
```

仍泄漏的原因。

---

# 14. 不要继续往 leak regex 添加项目词

禁止这样修：

```python
if "edge_memories" in text:
    drop()
```

也不要维护越来越长的：

```text
logging
cache
NER
edge_memories
...
```

项目词列表。

---

# 15. 新增统一 `project_operation_to_reader_surface()`

建议在 `section_writer.py` 或现有 writer projection 模块增加：

```python
def project_operation_to_reader_surface(
    item: Mapping[str, Any],
) -> dict[str, Any] | None:
    ...
```

顺序：

```text
1. 优先 reader-facing semantic atom / description
2. 保留 scientific predicate
3. subject/operands/result 逐字段过滤 implementation trace
4. raw code only if it is a scientifically meaningful symbol
5. otherwise omit raw field
```

伪代码：

```python
def project_operation_to_reader_surface(item):
    semantic = (
        item.get("reader_facing_claim")
        or item.get("semantic_atom")
        or item.get("description")
    )

    projected = {
        "operation": bounded_text(semantic, 320) if semantic else "",
        "predicate": normalize_predicate(item.get("predicate")),
    }

    for name in ("subject", "operands", "result", "output"):
        value = item.get(name)
        safe = project_reader_value(value)
        if safe:
            projected[name] = safe

    conditions = project_reader_value(item.get("conditions"))
    if conditions:
        projected["conditions"] = conditions

    if not has_scientific_content(projected):
        return None

    return projected
```

---

# 16. `project_reader_value()` 的判断标准

不是“有没有下划线”这么简单。

保留：

```text
Δt
A
B
C
attention mask
passage embedding
query embedding
sequence length
```

删除或改写：

```text
self.foo
dict membership
cache key
debug flag
logger
tensor storage plumbing
src_node_id / dst_node_id
```

优先交给已有 semantic projection。

deterministic rule 只负责明显 implementation syntax。

---

# 17. DyG `edge_memories` 的正确处理

Private operation 可能是：

```python
(src_node_id, dst_node_id) in edge_memories
```

Reader-facing 应该是：

```text
retrieve the stored edge representation for the queried node pair
```

如果没有 semantic projection：

```text
omit from Candidate prose
```

而不是原样暴露。

---

# 18. Heading hygiene：直接 deterministic 修复

EBCAR 三轮均：

```markdown
## Training objective:
```

不值得继续调 Writer。

增加：

```python
def normalize_publication_heading(text: str) -> str:
    text = text.strip()
    if text.endswith(":"):
        text = text[:-1].rstrip()
    return text
```

仅对：

```text
H2/H3 structural heading
```

执行。

不要修改正文 colon。

若已有更严格 truncated-heading detection，则至少将：

```text
trailing colon with no following phrase
```

视作 truncation。

---

# 19. Reader order：修 reuse surface 后再判断是否还需要 `_order_context_sections_before_mechanism`

当前：

```python
_order_context_sections_before_mechanism(
    preserved,
    units=prior_plan.argument_units,
    argument_facets=(),
)
```

注意这里：

```python
argument_facets=()
```

因此 `_section_is_pure_context()` 缺少新 facet kind 信息。

即使函数存在，也可能无法正确识别 frozen section 的新 rationale。

在 refresh path 中应调用：

```python
_order_context_sections_before_mechanism(
    rebuilt_graphs,
    units=current_units,
    argument_facets=current_argument_facets,
)
```

而不是：

```python
prior_plan.argument_units + empty facets
```

这会直接改善 DyG / LinearRAG。

---

# 20. Paragraph budget：不要再按旧 paragraph contract 冻结

当前 sixrepair 已有：

```python
_method_unit_expected_sentence_range()
```

逻辑方向合理：

```text
context facet
+
mechanism facet
+
argument unit count
→ bounded sentence range
```

问题是 reused plan 根本可能不走这条。

修完 P0-A 后，先观察真实产物。

不要再增加新的 length heuristics。

---

# 21. Candidate 完成度不要绑在 structural exit

当前：

```text
EBCAR 5/7 valid
DyG 0/6 valid
LinearRAG 0/5 valid
```

这些仍是严格 transaction/witness 语义。

不要为了让 Candidate “看起来完成”去放宽：

```text
required slot
edge
formula witness
```

Candidate quality 单独评价。

---

# 22. 建议新增一个轻量 Candidate draft audit

不是 hard gate。

可以放到现有 quality report 中：

```json
"candidate_draft": {
  "core_stage_presence": "...",
  "reader_order_ok": true,
  "raw_code_leak_count": 0,
  "duplicate_formula_mechanisms": 0,
  "truncated_heading_count": 0,
  "formula_worthy_sections_with_math": 3
}
```

如果不想改 schema，先写 test/evaluation helper。

不要影响 `eligible`。

---

# 23. 下一轮具体代码修改清单

## WP1 — Reader surface refresh

文件：

```text
src/code2paper/agentic/method_architect.py
scripts/run_authoring_replay.py  # 若需要明确 reuse flag 语义
```

改：

```text
_preserve_incumbent_method_unit_surface
build plan branch
_order_context_sections_before_mechanism call site
```

目标：

```text
reuse evidence
refresh reader surface
```

---

## WP2 — Semantic callback query

文件：

```text
src/code2paper/agentic/writer_research_router.py
生成 WritingResearchRequestV1 的上游 caller
```

改：

```text
internal ID filter
missing_parts source
semantic search terms
```

---

## WP3 — Claim-centered Formalizer

文件：

```text
src/code2paper/agentic/formalization_agent.py
src/code2paper/agentic/publication_method_writer.py
```

改：

```text
Formalizer prompt packet
connected exact excerpts
claim/mathematical_goal first
equation atoms auxiliary only
```

---

## WP4 — Canonical formula ownership

文件：

```text
src/code2paper/agentic/publication_method_writer.py
src/code2paper/llm/section_writer.py
src/code2paper/agentic/publication_transaction_contract.py
```

改：

```text
one mechanism → one formula package
Writer consume-only when package exists
duplicate formula detection
```

---

## WP5 — Reader operation projection + heading hygiene

文件：

```text
src/code2paper/llm/section_writer.py
```

改：

```text
subject / operands / result / output sanitization
reader-facing operation projection
H2 trailing-colon normalization
```

---

# 24. 推荐实现顺序

不要五项一起写完再测试。

按下面顺序：

```text
1. WP1 Reader surface refresh
2. 只跑 LinearRAG replay
3. WP2 callback query
4. 只跑 LinearRAG replay
5. WP3 Formalizer
6. 跑 LinearRAG + DyG
7. WP4 canonical formula ownership
8. 跑 EBCAR + DyG + LinearRAG
9. WP5 projection / heading hygiene
10. 最终三项目串行 replay
```

这样能定位 regression 来源。

---

# 25. 第一阶段只跑 LinearRAG 的原因

LinearRAG 是当前最敏感回归样本：

```text
v34p0p3: 4653 B + 2 display math
sixrepair: 2291 B + 0 display math
```

如果 WP1 修对：

至少应先看到：

```text
Motivation rationale 前置
Candidate 长度恢复
first retrieval stage 出现
```

即使 Verified 仍全部 fail。

---

# 26. LinearRAG 第一轮 acceptance

WP1 后，不要求：

```text
eligible=true
publication_ready=true
```

只要求：

```text
Candidate > sixrepair 2291 B
Motivation 不再以 “When vectorized retrieval is enabled...” 开头
semantic bridging / first-stage retrieval 至少有一段
section order 完整
```

如果这四项没发生，先不要碰 Formula。

---

# 27. Formalizer acceptance

WP3 后：

LinearRAG：

```text
至少 1 个第一阶段 mechanism-level formula
至少 1 个 PPR / hybrid init academic formula
```

DyG：

```text
Δt / A / B / C 由相关代码 slice 推导
不再用不可靠 vector normalization 代替 spectral norm
```

EBCAR：

```text
InfoNCE 保留 academic formula
不出现 code-shaped logsumexp display math
```

---

# 28. Formula ownership acceptance

每个 mechanism：

```text
canonical display formula count <= 1
```

EBCAR InfoNCE：

```text
1 academic formula
0 code-shaped formula
0 broken duplicate inline formula
```

DyG SSM：

```text
一套统一 notation
```

LinearRAG PPR：

```text
一套 initialization / propagation formula
```

---

# 29. Writer leak acceptance

全三篇：

```text
self. == 0
raw Python membership == 0
dim= == 0 in display math
logger/debug/cache plumbing == 0 in Candidate
```

注意：

```text
raw identifier count
```

不能做成绝对 0，因为 `InfoNCE`、模型名、合理变量名是合法的。

---

# 30. Static tests：控制在 10–15 个

不要扩成几百个新测试。

建议新增：

1. reused plan refreshes rationale；
2. reused plan preserves section identity；
3. reused plan refreshes reader ordering；
4. internal facet id not emitted as research search term；
5. semantic missing parts produce meaningful search terms；
6. Formalizer receives connected exact code excerpts；
7. operation atoms alone are not required for formalization；
8. canonical formula suppresses duplicate Writer equation；
9. raw `dim=0` cannot enter Candidate display formula；
10. V2 operands/result are publication-filtered；
11. scientific symbol survives operation projection；
12. trailing colon heading normalized；
13. Candidate formula may be review-required without entering Verified；
14. Verified behavior unchanged；
15. callback no-delta stop unchanged。

---

# 31. 不要修改的行为

保持：

```text
Candidate durability
Verified fail-closed
baseline/evaluation ownership isolation
source integrity
callback no-progress stop
formula canonical display block
author review sidecars
```

尤其不要因为：

```text
DyG valid paragraphs = 0
LinearRAG valid paragraphs = 0
```

去削弱 transaction validator。

---

# 32. 不建议做的“修复”

不要：

### 32.1 提高 retry

```text
Formalizer retry 2 → 5
Writer retry 2 → 6
```

不会解决输入上下文错误。

### 32.2 提高 max tokens

LinearRAG 不是因为 output token 不够。

### 32.3 给三个项目写规则

禁止：

```python
if project == "LinearRAG":
    ...
```

### 32.4 用原论文公式补答案

原论文只用于 benchmark/evaluation oracle，不能作为 generation evidence。

### 32.5 把所有 optional facet 都塞进 Method

只保留 representative rationale。

### 32.6 再造 Formula Graph / Research Graph v3

当前 schema 足够。

---

# 33. 推荐的最终数据流

下一轮修复后的理想链：

```text
Frozen research/evidence
        │
        │ reuse
        ▼
Current intent/facets/briefs
        │
        ▼
REFRESH reader-facing MethodUnits
        │
        ├── rationale / reader order / paragraph budget
        │
        ▼
Paragraph scientific claim
        │
        ├── semantic callback if evidence missing
        │
        ▼
Connected source-code slice
        │
        ▼
AI Formalizer
        │
        ├── mechanism-level paper formula
        │
        └── assumptions / provenance sidecar
        ▼
Canonical formula package
        │
        ▼
Paper-language Writer packet
        │
        ▼
Clean Candidate
        │
        ├── Candidate quality audit
        │
        └── strict reverse validation
                 │
                 ▼
          Repository-Verified subset
```

---

# 34. 关键设计边界

## Candidate

目标：

```text
完整
可读
论文语言
尽量恢复科学语义
```

允许：

```text
direct
static-derived
semantic-derived
formal-derived
author-intent-supported
```

内部 uncertainty 放 sidecar。

---

## Verified

目标：

```text
strict repository-supported subset
```

继续 fail-closed。

---

## Formalizer

目标：

```text
AI scientific abstraction
```

不是：

```text
deterministic formula compiler
```

---

## Architect

目标：

```text
reader-facing organization
```

不是：

```text
freeze compiler-shaped old paragraph surface
```

---

# 35. 最终验收标准

下一轮三项目 replay 后，先看 Candidate，不先看 exit code。

## EBCAR

必须达到：

```text
完整 architecture / training / inference
InfoNCE only one canonical formula
无 code-shaped logsumexp
Training objective heading 正常
```

目标评级：

```text
B+ / usable Method draft
```

---

## DyG-Mamba

必须达到：

```text
Motivation before mechanism
无 edge_memories
Δt/A/B/C notation 一致
无 unsupported scale-invariance/global stability claim
```

目标评级：

```text
B / usable technical Method draft
```

---

## LinearRAG

必须恢复：

```text
Motivation rationale
Tri-Graph
stage-1 semantic bridging
iterative propagation
dynamic pruning
stage-2 hybrid PPR
至少 1–2 个 academic formulas
```

目标评级：

```text
B- or better
```

---

# 36. 建议的开发 commit 切片

为了容易回滚，建议分四笔，不要一笔塞完：

### Commit 1

```text
fix: refresh reused reader-facing method surface
```

包含：

```text
method_architect.py
tests for reused plan
```

### Commit 2

```text
fix: make writing callbacks search semantic method content
```

包含：

```text
writer_research_router.py
callback tests
```

### Commit 3

```text
feat: formalize method claims from connected code context
```

包含：

```text
formalization_agent.py
publication_method_writer.py
formalizer tests
```

### Commit 4

```text
fix: enforce canonical formulas and publication-safe writer packets
```

包含：

```text
section_writer.py
publication_transaction_contract.py
formula ownership + leak + heading tests
```

---

# 37. 推荐 live protocol

每个 code slice：

```bash
pytest focused-tests
python -m compileall -q src tests
git diff --check
```

然后：

### Commit 1

只 replay：

```text
LinearRAG
```

### Commit 2

继续：

```text
LinearRAG
```

### Commit 3

replay：

```text
LinearRAG
DyG
```

### Commit 4

串行：

```text
EBCAR
DyG
LinearRAG
```

禁止为了 sample luck 原样重复多次。

---

# 38. replay 必须记录的新诊断

不需要新大 artifact，只在 stdout / trace 增加：

```text
reader_surface_mode=rebuilt|fallback_prior
prior_method_units=N
rebuilt_method_units=N
rationale_facets_selected=N
context_reorder_applied=true|false

formalizer:
claim_context_chars=N
exact_source_excerpt_chars=N
connected_operation_count=N
academic_package_generated=N

writer:
canonical_formula_consumers=N
duplicate_formula_suppressed=N
publication_trace_fields_removed=N
```

这些值直接告诉我们修复是否真正进入 live 路径。

---

# 39. 最优先的一条代码修改

如果下一轮只能做一件事：

> **先修改 `method_architect.py`，让 `--reuse-derived-authoring` 复用 frozen evidence，但重新运行当前 `_build_method_units_v2()` 来生成 reader-facing MethodUnit surface。**

这是当前最上游的共同阻塞。

它同时影响：

- LinearRAG rationale；
- DyG ordering；
- paragraph budget；
- Formula consumer paragraph；
- Writer packet；
- 后续 callback scope。

如果这一层不修，继续调 Writer/Formalizer 很容易继续出现：

```text
static test PASS
live replay unchanged
```

---

# 40. 第二优先级

然后修 Formalizer 的输入语义：

> **让模型看到“当前段落要解释的 scientific claim + 连续源码实现”，而不是主要看到 equation atoms 和函数名。**

这是从“代码证据 Agent”升级成“代码研究 Agent”的关键一步。

---

# 41. 最终原则

本轮不要追求：

```text
eligible = true
publication_ready = true
D5
```

先把主产品修成真正的 Method draft。

正确优化目标：

```text
Candidate quality first
+
research-derived scientific abstraction
+
strict Verified projection
```

而不是：

```text
structural metric first
+
规则补丁堆叠
```

当前 Code-to-Paper 已经具备足够多的底层证据、trace、formula lane 和 Candidate/Verified 分离能力；下一步的主要工作不是再加系统，而是**让已有研究证据真正通过最新 reader surface、AI Formalizer 和 paper-language Writer 流到正文里。**
