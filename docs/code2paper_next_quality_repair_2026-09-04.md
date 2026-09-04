# Code2Paper Candidate-First Method：下一轮优化与修复执行文档

- 日期：2026-09-04
- 仓库：`hjcui98/code2paper`
- 分支：`codex/agentic-p4-benchmark-cutover`
- 当前审计提交：`6aec54b1e4760b403d8b8e960b81d53cce78c781`
- 上一轮核心修复提交：`91de13f7da5bbca32e7494726a57e4e5cc3270d4`
- 最新 live 证据：`artifacts/quality_closed_loop/2026-09-03/local-qwen36-fixed/`
- 适用对象：下一轮 Codex / 人工代码修复
- 原则：**不重构整个 Agent，不弱化 Verified fail-closed，不做 DyG/LinearRAG 项目特判，不新增大型中间表示。**

---

# 0. 结论先行

当前系统已经跨过了“整体架构不通”的阶段。上一轮 WP1–WP5 均已经进入生产代码，其中：

- **WP1 Reader-surface refresh**：已真实生效，DyG 的 Motivation 已被移动到 mechanism 之前；
- **WP2 Semantic callback**：已真实生效，callback query 不再主要搜索 `facet-* / paragraph-* / MA-S*` 等 bookkeeping id；
- **WP3 Claim-centered Formalizer**：输入侧已经按设计实现，Formalizer 现在能看到 section claim、数学目标、connected source excerpts 和 operation evidence；
- **WP4 Canonical formula ownership**：代码存在，但本轮没有 accepted formula package，因此尚未完成端到端验证；
- **WP5 Reader-facing operation projection**：已消除 `edge_memories`、`self.*` 等明显泄漏，但还停留在“删除代码痕迹”，没有稳定完成“实现操作 → 论文语义”的投影。

最新 live run 暴露出的首要瓶颈已经改变：

```text
过去：
Writer / Formalizer 没有足够信息
        ↓
正文缺失、公式缺失

现在：
Formalizer 已经拿到信息并生成 paper-level formula
        ↓
representation / symbol / operation guard
        ↓
全部 package 被拒绝
        ↓
Writer 收不到公式
```

因此下一轮不应继续扩展 Research/Writer 架构，而应优先修复下面三条闭环：

```text
P0-A  Formalizer output
      → representation normalization
      → semantic guard

P0-B  repository operation
      → semantic mathematical binding
      → paper formula

P0-C  bound callsite
      → bounded callee-body evidence
      → mechanism-local source context
```

并同时处理两类 Writer 质量问题：

```text
P0-D  Motivation/context authority isolation
P0-E  implementation operation → semantic reader surface
```

最后再用 DYG + LinearRAG live replay 做统一验收。

---

# 1. 当前真实基线

## 1.1 DyG-Mamba

上一版 `sixrepair`：

```text
valid required paragraphs: 0 / 6
valid targets:            20 / 40
witnessed slots:           9 / 17
accepted formula packages: 0
```

最新 `local-qwen36-fixed`：

```text
valid required paragraphs: 1 / 6
valid targets:            17 / 37
witnessed slots:           5 / 15
accepted formula packages: 0
consumed formula packages: 0
```

正向变化：

- Motivation 顺序修正；
- `edge_memories` 等实现泄漏消失；
- 旧版中部分过强理论表达和不可靠公式被抑制；
- Candidate 更保守、更接近 fail-closed 语义。

当前退化：

- Motivation 正文错误地写成 Mamba 底层实现：
  - `fused add norm hidden states with weight bias eps`
  - `step hidden states conv state ssm out`
- Dynamic graph encoding 仍出现机械代码改写：
  - `softmax dst router logits across dimension 1`
- Formalizer 已经提出 `A`、`\Delta t`、`B/C` 等公式，但全部未被接受；
- 技术细节和 slot coverage 低于上一版。

结论：

> DyG 当前属于 **safer but not better as a paper Method draft**。架构顺序和泄漏问题改善，但论文可用性尚未闭环。

---

## 1.2 LinearRAG

上一版 `sixrepair`：

```text
valid required paragraphs: 0 / 5
valid targets:             5 / 29
witnessed slots:           0 / 16
accepted formula packages: 0
```

最新 `local-qwen36-fixed`：

```text
valid required paragraphs: 0 / 5
valid targets:            13 / 29
witnessed slots:           5 / 15
accepted formula packages: 0
consumed formula packages: 0
```

正向变化：

- First retrieval stage 已恢复；
- semantic bridging、iterative propagation、dynamic pruning 均进入 Candidate；
- target coverage 从约 17% 提升到约 45%；
- 第二阶段 PPR / hybrid initialization 的实现 grounding 更完整。

当前不足：

- First retrieval stage 的正文主要由 facet witness 支撑，而不是 implementation slot；
- `calculate_entity_scores_vectorized(...)` 仍主要只拿到 callsite，没有拿到足够集中的 callee body；
- Formalizer 已提出 entity activation / PPR 公式，但同样被 guard 拒绝；
- 第二阶段仍出现 validation/candidate 风格句子：
  - `when the system is configured to use vectorized retrieval`
  - `remains unresolved when the configuration state is unresolved`

结论：

> LinearRAG 已从 regression 恢复为 **rough Method draft**，但 grounding 和公式链路仍不完整。

---

# 2. 下一轮总体设计原则

## 2.1 保留的系统不变量

以下不允许为了提高通过率而弱化：

1. `Verified` 必须继续 fail-closed；
2. `code_verified` formula 必须绑定真实 fact/equation；
3. author-intent / partial formula 不得升级为 code-verified；
4. Candidate 可以保留 author-intent mechanism，但必须保留 authority distinction；
5. formula consumer 必须是唯一、明确的 paragraph；
6. callback rollback 的 monotonicity 机制继续保留；
7. 不允许因为某个 benchmark/project 的名字而写 project-specific hard-code。

---

## 2.2 本轮明确不做

不要做：

- 新建 FormulaGraph / MathIR / EquationAST 等大 schema；
- 再增加一个独立 Formula Agent；
- 增加 callback rounds 试图“靠更多调用解决”；
- 增加 Writer prompt 长度来覆盖数据通路问题；
- 为 LinearRAG 单独 hard-code `PPR`；
- 为 DyG 单独 hard-code `Delta t / A / B / C`；
- 放松所有 formula guard；
- 删除现有 candidate/verified split；
- 推翻 `MethodUnitV2` / dossier / formula package 体系。

当前主要是 **边界与表示层不兼容**，不是架构缺失。

---

# 3. P0-1：Formula representation normalization 必须发生在 semantic validation 之前

## 3.1 当前代码事实

文件：

```text
src/code2paper/agentic/formalization_agent.py
```

关键函数：

```python
_normalize_formalizer_payload(...)
coerce_section_formalizer_response(...)
validate_section_formula_package(...)
canonical_formula_markdown_block(...)
```

当前 `validate_section_formula_package()` 直接执行：

```python
if "$$" in package.latex or "\\[" in package.latex or "\\]" in package.latex:
    failures.append("latex_contains_display_wrapper")
```

但 `_normalize_formalizer_payload()` 当前只做：

```python
row["markdown_block"] = canonical_formula_markdown_block(row["latex"])
```

并没有把：

```latex
$$ A = \operatorname{diag}(\lambda_1,\dots,\lambda_d) $$
```

规范成：

```latex
A = \operatorname{diag}(\lambda_1,\dots,\lambda_d)
```

结果是：

```text
模型已经生成正确公式
→ markdown_block 被重新包一次
→ latex 仍带 $$
→ semantic guard 前先死于 representation error
```

这正是最新 DYG / LinearRAG 中反复出现的：

```text
latex_contains_display_wrapper
```

---

## 3.2 修复方案

新增一个非常窄的 representation-only helper，例如：

```python
def normalize_formula_latex_body(latex: str) -> str:
    ...
```

只允许做下面的变换：

```text
$$ BODY $$        → BODY
\[ BODY \]        → BODY
\begin{equation}
BODY
\end{equation}    → BODY
```

对于：

```latex
$$
\begin{aligned}
...
\end{aligned}
$$
```

只去掉最外层 `$$`，保留 `aligned`。

严禁：

- 改变量；
- 改运算符；
- 改数字；
- 改条件；
- 改公式结构；
- 自动“修数学”。

推荐位置：

```python
_normalize_formalizer_payload()
```

中的 package normalization：

```python
latex = normalize_formula_latex_body(str(row["latex"]))
row["latex"] = latex
row["markdown_block"] = canonical_formula_markdown_block(latex)
```

然后才进入：

```python
SectionFormalizerResponseV1.model_validate(...)
validate_section_formula_package(...)
```

---

## 3.3 为什么这不弱化 Verified

这是：

```text
representation repair
```

不是：

```text
authority repair
semantic repair
```

它与当前已有：

```python
canonical_formula_markdown_block(...)
_normalize_non_code_formula_package(...)
```

属于同一层职责。

---

## 3.4 测试要求

至少新增：

```python
def test_formalizer_payload_strips_outer_dollar_display_wrapper()

def test_formalizer_payload_strips_bracket_display_wrapper()

def test_formalizer_payload_keeps_aligned_environment_inside_body()

def test_formula_normalization_does_not_change_math_body()

def test_normalized_formula_still_runs_all_semantic_guards()
```

必须保留现有：

```text
latex_contains_markdown
latex_contains_document_command
code_shaped_formula
unsupported_theoretical_upgrade
```

等真正语义/安全 gate。

---

# 4. P0-2：修复 LaTeX command false positive

## 4.1 当前代码事实

文件：

```text
src/code2paper/agentic/formalization_agent.py
```

当前 symbol closure：

```python
used_symbols = _latex_command_tokens(package.latex)

unknown_symbols = (
    used_symbols
    - declared_symbols
    - known_tokens
    - _STANDARD_LATEX_COMMANDS
    - _LATEX_GREEK_COMMANDS
    - _LATEX_TYPESETTING_COMMANDS
)
```

最新 LinearRAG 出现：

```text
undefined_symbols:\downarrow
undefined_symbols:\xrightarrow
```

检查当前 `_LATEX_TYPESETTING_COMMANDS` 可见：

```text
\rightarrow
\leftarrow
\Rightarrow
...
```

但缺少：

```text
\downarrow
\uparrow
\xrightarrow
\xleftarrow
```

因此标准排版命令被误认为数学变量。

---

## 4.2 修复方案

扩充标准 command classification，而不是在 validator 中针对某个公式跳过 symbol validation。

至少加入：

```python
r"\uparrow",
r"\downarrow",
r"\Uparrow",
r"\Downarrow",
r"\updownarrow",
r"\xrightarrow",
r"\xleftarrow",
r"\longrightarrow",
r"\longleftarrow",
```

如果当前依赖的 LaTeX parser 允许，可增加一个小的“operator/presentation command”集合，但不要使用：

```text
所有 \xxx 都自动合法
```

因为那会破坏 undefined-symbol guard。

---

## 4.3 测试要求

```python
def test_standard_arrow_commands_are_not_symbols()

def test_unknown_custom_command_still_fails_symbol_closure()
```

期望：

```text
\xrightarrow   → allowed
\downarrow     → allowed
\myUnknownVar  → undefined_symbols
```

---

# 5. P0-3：Operation guard 从 literal code binding 调整为 semantic mathematical binding

这是本轮最关键的语义修复。

---

## 5.1 当前代码事实

文件：

```text
src/code2paper/agentic/formalization_agent.py
```

关键函数：

```python
_operation_evidence_failures(...)
_operation_value_is_bound(...)
_operation_callable_is_rendered(...)
_operation_source_conditions(...)
_operation_source_shapes(...)
```

当前逻辑会从 operation atom 中遍历：

```python
for field in ("operands", "result", "output", "return_value"):
```

如果某个 identifier-shaped value 没有在 formula/symbol meanings 中被绑定，就生成：

```text
operation_operand_binding_missing:...
```

最新 LinearRAG 的典型失败：

```text
operation_operand_binding_missing:self.run_ppr
```

最新 DyG 还出现：

```text
operation_shape_or_type_missing:
rearrange(self.in_proj.bias.to(dtype=xz.dtype), 'd -> d 1')
```

这与上一轮已经确定的 Formalizer 设计发生冲突：

```text
Formalizer:
raw code → paper-facing abstraction

Guard:
paper formula 必须仍显式绑定 raw callable / raw rearrange expression
```

---

## 5.2 正确职责边界

应该保持：

```text
AI:
理解机制
选择 paper notation
抽象数学关系

Rules:
确认 formula 对应的 source operation family 存在
确认 fact/equation ownership
确认关键 condition / configuration 未丢
确认没有新增 unsupported number / guarantee
确认 symbol 有定义
```

不应该要求：

```text
paper formula 必须出现 self.run_ppr
paper formula 必须出现 rearrange(...)
paper formula 必须出现 raw tuple/result name
```

---

## 5.3 最小修复方案

### A. 保留强 gate

继续强制：

```text
package.section_id
bound_fact_ids / bound_equation_ids
operation_evidence_unbound
operation_signature_mismatch
material condition mismatch
unsupported theoretical upgrade
unknown fact/equation
new unsupported number
```

### B. 区分 semantic operands 与 implementation plumbing

在 `_operation_evidence_failures()` 中，不要把所有 identifier-shaped operand 等价处理。

建议增加内部分类 helper：

```python
def _operation_binding_requirement(value, atom, package) -> Literal[
    "material",
    "semantic_alias_ok",
    "implementation_plumbing",
]:
    ...
```

典型：

```text
material:
damping value
threshold
normalization condition
branch guard
input/output scientific variable
matrix/operator actually出现在公式中

semantic_alias_ok:
self.run_ppr
calculate_entity_scores_vectorized
torch.sort / np.argsort

implementation_plumbing:
rearrange(...)
dtype conversion
temporary tuple
runtime storage handle
shape-layout plumbing
```

`implementation_plumbing` 不应该作为 formula semantic equivalence 的必要字符串绑定。

---

## 5.4 改进 `_operation_callable_is_rendered()`

当前只处理：

```python
cat → concat
concatenate → concat
argsort → sort
logsumexp → logsumexp
```

应增加 **generic callable normalization**，而不是 project hard-code。

例如：

```text
self.run_ppr
→ terminal = run_ppr
→ strip generic verb prefix "run_"
→ operator candidate = ppr
```

类似：

```text
compute_score → score
calculate_weights → weights
apply_softmax → softmax
```

允许公式：

```latex
\operatorname{PPR}(...)
```

语义绑定：

```text
self.run_ppr(...)
```

但不要要求正文出现：

```text
self.run_ppr
```

建议 generic verb prefix 只限定在：

```text
run_
compute_
calculate_
apply_
build_
get_
make_
```

并继续要求：

- 同 section；
- 同 bound fact；
- 同 operation evidence pack；
- operator family 兼容。

---

## 5.5 symbol definition 也应参与 semantic binding

现有 `_operation_value_is_bound()` 已允许：

```text
source tokens
↔ declared symbol meaning tokens
```

这条思路是对的。

下一步应强化的是：

> paper symbol 的 `meaning` 承担实现名与学术符号之间的桥梁。

例如：

```yaml
symbol: \pi
meaning: personalized PageRank score
```

可以作为：

```text
run_ppr / pagerank_scores
```

到：

```latex
\pi
```

的 semantic binding evidence。

不要要求 source variable 本身出现在公式。

---

## 5.6 shape/condition guard 收窄到 material semantics

当前把：

```text
rearrange(self.in_proj.bias.to(dtype=xz.dtype), 'd -> d 1')
```

作为 shape/type obligation 是明显过严。

建议：

- 数值 shape（如 `B × L × d`）可以保留；
- paper-relevant dimension relation 可以保留；
- branch/config condition 可以保留；
- raw tensor layout transformation、dtype conversion、rearrange syntax 不作为公式 acceptance 的强 requirement。

---

## 5.7 测试要求

新增 synthetic tests：

```python
def test_code_verified_paper_operator_can_bind_generic_run_callable()

def test_raw_callable_name_need_not_appear_in_paper_formula()

def test_symbol_meaning_can_bind_source_result_semantically()

def test_dtype_rearrange_plumbing_does_not_block_formula()

def test_material_branch_condition_still_must_be_preserved()

def test_operator_family_mismatch_still_fails()

def test_unbound_fact_still_fails()
```

---

# 6. P0-4：Research dossier 增加 bounded callee-body expansion

这是 LinearRAG 当前最重要的 evidence quality 修复。

---

## 6.1 当前代码事实

dossier 构造路径：

```text
publication_method_writer.py
    ↓
build_research_mechanism_dossiers(...)
    ↓
research_derived_authoring.py
    ↓
ResearchMechanismDossierV1
    ↓
build_mechanism_equation_evidence_packs(...)
    ↓
Formalizer
```

具体文件：

```text
src/code2paper/agentic/research_derived_authoring.py
```

`build_research_mechanism_dossiers()` 当前会收集：

```text
exact_span_ids
exact_excerpts
operation_atoms
formalizable_signatures
call_path_relation_ids
data_flow_relation_ids
```

随后：

```text
formalization_agent.py
build_mechanism_equation_evidence_packs()
```

基本只是把 dossier 的 `exact_excerpts` 传下去。

---

## 6.2 当前 live 失败实例

LinearRAG MA-S4 的核心 author claim 是：

```text
initialization
→ query–sentence similarity
→ sentence–entity propagation
→ iterative activation
→ threshold pruning
```

但实际 `exact_excerpts` 主要是：

```python
entity_weights, actived_entities =
    self.calculate_entity_scores_vectorized(...)

node_weights = entity_weights + passage_weights

self.run_ppr(...)

np.argsort(...)
```

即：

```text
有 callsite
没有足够完整的 calculate_entity_scores_vectorized() body
```

结果出现：

```text
evidence 很多
connected_operation_count 很高
但 mechanism locality 不够
```

---

## 6.3 修复原则

不增加新 schema。

继续复用：

```text
ResearchMechanismDossierV1.exact_span_ids
ResearchMechanismDossierV1.exact_excerpts
call_path_relation_ids
operation_atoms
```

只增强 `build_research_mechanism_dossiers()` 的证据展开。

---

## 6.4 最小 callee expansion

当满足以下条件：

1. paragraph/facet 是 mechanism-heavy；
2. 当前 code-ready dossier 中存在 `calls` operation；
3. callee 在当前 repository scope 内有已解析 symbol/span；
4. 当前 mechanism claim 与该 call 是当前 paragraph 的主要 transformation；

则允许：

```text
callsite
→ resolve direct callee
→ 加入一个 bounded function-body excerpt
```

限制：

```text
depth = 1
max callees per paragraph = 2~3
max lines per callee = 60~80
same repository only
must preserve exact span id
must preserve source digest
```

不要递归无限扩展。

---

## 6.5 locality ranking

不能把所有“相关代码”都塞进去。

建议按以下优先级选 excerpt：

```text
1. facet/alignment direct span
2. direct callee body
3. call-path immediate predecessor/successor
4. same-paragraph data-flow span
5. unrelated helper / logging / NER fallback
```

LinearRAG MA-S4 不应该在第一屏出现：

```text
ORDINAL / CARDINAL filtering
PPR sorting
logging
```

而缺少 entity propagation 的 function body。

---

## 6.6 测试要求

新增 synthetic behavior graph：

```text
graph_search()
    calls calculate_entity_scores()
        body:
            initialize
            similarity
            propagate
            threshold
```

断言：

```python
assert "calculate_entity_scores" callsite in dossier
assert core body excerpt in dossier.exact_excerpts
assert unrelated_helper not in top/local evidence
assert max_depth == 1
```

再做一个 recursive-cycle test，防止：

```text
A → B → A
```

导致无限展开。

---

# 7. P0-5：Motivation / Context section 与 mechanism operation 隔离

这是 DyG 最新 Candidate 最明显的论文质量问题。

---

## 7.1 当前问题

WP1 已经把 Motivation 调整到正确顺序：

```text
Motivation
→ Dynamic graph encoding
→ Redesign
```

但 Motivation 正文却成为：

```text
fused add norm hidden states ...
step hidden states conv state ssm out ...
```

说明：

```text
section order 已刷新
但 Writer packet 的 authority/content selection 没有和 rhetorical role 一起收紧
```

---

## 7.2 修复原则

对于被 `_section_is_pure_context()` 判为 context/motivation 的 section：

Writer 的主信息源应优先：

```text
reader question
rationale facet
problem/context semantic atom
author statement
repository-supported limitation/context evidence
```

而不是：

```text
arbitrary low-level ordered_operations
```

---

## 7.3 推荐修改位置

主要检查：

```text
src/code2paper/agentic/research_derived_authoring.py
build_publication_authoring_packets(...)

src/code2paper/llm/section_writer.py
_compact_authoring_packets_v2_for_llm(...)
compact_operation(...)
```

不要删除 Binder/sidecar 中的 operation evidence。

只限制：

```text
哪些 operation 可以成为 Writer 的 reader-facing organization surface
```

---

## 7.4 最小规则

对于 pure context/motivation paragraph：

```text
if operation has explicit rationale/context semantic_atom:
    allow reader semantic surface
else:
    do not expose raw operation operands/result as prose material
```

仍可把这些 operation 留在：

```text
private dossier / Binder / validation sidecar
```

---

## 7.5 测试要求

构造：

```text
heading = Motivation
rationale facet = irregular timestamps hurt uniform-step SSM
raw operation = fused_add_norm(...)
```

期望：

```text
Writer-visible:
irregular timestamp rationale

Writer-hidden:
fused_add_norm raw operands
```

再构造一个真正由 implementation 支撑的 limitation operation，确认它仍可进入 reader surface。

---

# 8. P0-6：Reader projection 从“删代码”升级为“semantic-primary projection”

---

## 8.1 当前代码事实

文件：

```text
src/code2paper/llm/section_writer.py
```

当前：

```python
_project_reader_value(...)
_project_operation_to_reader_surface(...)
```

已经能过滤：

```text
self.*
torch.*
numpy.*
dim=
dtype=
device=
cache
memory
buffer
*_id
*_index
```

这是正确的。

但 live 结果显示：

```python
F.softmax(dst_router_logits, dim=1)
```

仍可能最终成为：

```text
normalizes softmax dst router logits across dimension 1
```

这只是“代码语法清洗”，不是 paper abstraction。

---

## 8.2 修复原则

当前函数已经按优先级寻找：

```python
reader_facing_claim
semantic_atom
description
statement
operation
```

这个方向应该进一步强化。

如果已经存在可靠 semantic text：

```text
semantic-primary
```

则 Writer 不应同时再收到大部分 raw：

```text
subject
operands
result
```

否则模型很容易回到 implementation narration。

---

## 8.3 推荐策略

### semantic-primary

当存在：

```text
reader_facing_claim
semantic_atom
description
statement
```

时：

Writer surface 只保留：

```text
operation
material conditions
paper-relevant shape hint
必要 output concept
```

默认不再附：

```text
raw operands
raw result
raw callable
```

### safe-structured fallback

只有在没有 semantic text 时，才使用当前 bounded structured projection：

```text
predicate
safe subject
safe operands
safe result
conditions
```

### private evidence

原始 operation row 继续留在 dossier/Binder，不丢失 provenance。

---

## 8.4 测试要求

输入：

```python
{
    "predicate": "normalizes",
    "reader_facing_claim": "normalize routing weights across candidate positions",
    "operands": ["dst_router_logits", "dim=1"],
    "result": "dst_routing_weights",
}
```

Writer-visible 应优先变成：

```text
normalize routing weights across candidate positions
```

而不是：

```text
dst_router_logits
dim=1
dst_routing_weights
```

同时保留一个没有 semantic text 的 scientific symbol case：

```latex
h_t, W, x_t
```

确保当前 scientific-symbol regression 不被破坏。

---

# 9. P1：Callback 只做审计修正，不扩大调用深度

当前 callback rollback：

```text
quality_regression_incumbent_restored
```

是正确机制，不应该删除。

LinearRAG 曾发生：

```text
13/29
→ callback resume
→ 1/29
→ rollback
```

说明 monotonicity gate 正在保护 incumbent。

下一轮不要先增加：

```text
callback rounds
tool turns
research breadth
```

因为当前每轮成本已经很高：

```text
DyG      ≈ 456k captured tokens
LinearRAG ≈ 1.49M captured tokens
```

应先修 P0 数据通路。

---

## 9.1 telemetry 小修

README / execution record 建议区分：

```text
temporarily_fulfilled
retained_fulfilled
```

例如：

```text
2 temporarily fulfilled before rollback
0 retained after incumbent restoration
```

避免“README 写 2 fulfilled、最终 record 写 0 fulfilled”在审计时看起来矛盾。

这属于 P1，不阻塞主修复。

---

# 10. 实施顺序

## Phase A：Formula representation closure

修改：

```text
src/code2paper/agentic/formalization_agent.py
```

完成：

```text
P0-1 display wrapper normalization
P0-2 standard LaTeX command classification
```

Gate：

```text
- existing tests 全通过
- $$ wrapper 不再导致 package rejection
- \downarrow / \xrightarrow 不再 false-fail
- unknown custom command 仍 fail
```

不要先跑完整 1.5M-token LinearRAG。

---

## Phase B：Formula semantic binding closure

修改：

```text
src/code2paper/agentic/formalization_agent.py
```

完成：

```text
P0-3 operation semantic binding
```

Gate：

```text
- self.run_ppr 不要求 literal 出现在公式
- \operatorname{PPR} / semantic symbol meaning 可正确绑定
- raw rearrange/dtype plumbing 不再阻塞
- material branch/condition 仍严格验证
- operation_signature_mismatch 仍严格验证
- unbound fact 仍严格验证
```

完成后先用 archived/synthetic Formalizer evidence 做回归。

---

## Phase C：Evidence locality + Writer reader surface

修改：

```text
src/code2paper/agentic/research_derived_authoring.py
src/code2paper/llm/section_writer.py
必要时：
src/code2paper/agentic/publication_method_writer.py
```

完成：

```text
P0-4 bounded callee-body expansion
P0-5 motivation/context isolation
P0-6 semantic-primary reader projection
```

Gate：

```text
LinearRAG MA-S4:
- dossier 必须含 calculate_entity_scores* 的核心 body slice
- 不是只有 callsite

DyG Motivation:
- Writer-visible packet 不得以 fused_add_norm / step / conv_state 为主干

DYG Dynamic encoding:
- reader surface 优先 academic semantic operation
- 不再机械复述 dst_router_logits / dim=1
```

---

## Phase D：Live acceptance

只在 A–C static/integration gate 通过后，再运行：

```text
DyG-Mamba
LinearRAG
```

如果资源允许，再用 EBCAR 做 formula dedup regression。

---

# 11. Live 验收标准

## 11.1 结构非回退 Gate

至少不能低于当前 incumbent：

### DyG

```text
valid required paragraphs >= 1 / 6
valid targets            >= 17 / 37
witnessed slots          >= 5 / 15
```

### LinearRAG

```text
valid required paragraphs >= 0 / 5
valid targets            >= 13 / 29
witnessed slots          >= 5 / 15
```

但这只是“不得回退”，不是最终成功标准。

---

## 11.2 本轮真正成功标准

### Formula

对于有 required formula obligation 且 Formalizer 已产生可支持公式的 section：

```text
accepted_formula_packages > 0
consumed_formula_packages > 0
```

至少应看到：

```text
DyG:
timespan / A / B-C 中有实际可消费 package

LinearRAG:
first-stage 或 PPR/hybrid initialization 中有实际可消费 package
```

不要硬性要求每个 section 都必须有公式。

---

## 11.3 DYG prose Gate

不得再出现类似：

```text
fused add norm hidden states with weight bias eps
step hidden states conv state ssm out
softmax dst router logits across dimension 1
```

作为论文段落主干。

Motivation 必须回答：

```text
为什么 vanilla SSM 对 irregular timespan / noise 不足
```

而不是解释底层 forward implementation。

---

## 11.4 LinearRAG grounding Gate

First retrieval stage 必须满足：

```text
semantic bridging story retained
+
至少一条 implementation-backed slot/derivation
+
callee body evidence present
```

不能退回仅 facet-backed prose。

---

## 11.5 Candidate/Verified Gate

继续要求：

```text
Candidate:
允许 author_intent / partial mechanism，但 authority 明确

Verified:
只接受 code-licensed 内容
```

不得为了提高 Candidate score 让 author intent 混入 Verified。

---

# 12. 建议新增/修改的测试文件

优先复用现有测试文件：

```text
tests/test_agentic_formalization_guards.py
tests/test_agentic_publication_method_writer.py
tests/test_llm_section_writer.py
```

并在适当位置增加：

```text
tests/test_research_derived_authoring.py
```

如果该文件已存在则直接补；不要为了本轮单独创建一整套新测试框架。

建议测试组：

```text
FormulaRepresentationTests
FormulaSemanticBindingTests
CalleeEvidenceExpansionTests
MotivationSurfaceIsolationTests
SemanticReaderProjectionTests
```

---

# 13. 建议的代码改动清单

## `src/code2paper/agentic/formalization_agent.py`

新增/调整：

```text
normalize_formula_latex_body()
_normalize_formalizer_payload()
_LATEX_TYPESETTING_COMMANDS
_operation_callable_is_rendered()
_operation_value_is_bound()
_operation_evidence_failures()
```

目标：

```text
先 normalize representation
再 validate semantics
```

---

## `src/code2paper/agentic/research_derived_authoring.py`

重点：

```text
build_research_mechanism_dossiers()
```

目标：

```text
direct callsite
→ bounded direct callee body
→ same dossier exact_excerpts
```

不新增新 dossier schema。

---

## `src/code2paper/llm/section_writer.py`

重点：

```text
_project_reader_value()
_project_operation_to_reader_surface()
_compact_authoring_packets_v2_for_llm()
```

目标：

```text
semantic text exists
→ semantic-primary Writer surface
→ raw implementation stays private
```

---

## `src/code2paper/agentic/publication_method_writer.py`

原则上只做必要接线：

```text
_run_section_formalizer()
build_mechanism_equation_evidence_packs() consumer routing
writer packet assembly
```

不要把所有新逻辑都继续堆到这个大文件中。

---

# 14. 推荐的 commit 切分

不要一口气提交全部。

建议：

```text
Commit A
fix: normalize formalizer math representation before guards

Commit B
fix: align operation formula guards with semantic paper notation

Commit C
fix: expand mechanism-local callee evidence in research dossiers

Commit D
fix: isolate context prose and prefer semantic reader surfaces

Commit E
test: archive DYG and LinearRAG post-repair live evidence
```

这样每一步都能单独 rollback 和审计。

---

# 15. 最终判断标准

下一轮不是看：

```text
tests passed
```

也不是看：

```text
Formalizer was called
```

而是看完整链路是否成立：

```text
author intent / reader goal
        ↓
mechanism-local code evidence
        ↓
claim-centered Formalizer
        ↓
paper-level formula
        ↓
representation normalization
        ↓
semantic authority validation
        ↓
canonical formula package
        ↓
unique paragraph consumer
        ↓
paper-facing Writer prose
        ↓
Candidate
        ↓
reverse validation
```

本轮最重要的成功信号应该是：

1. Formalizer 已经生成的好公式不再死于纯 representation defect；
2. Guard 验证的是 **semantic equivalence + authority**，不是强迫论文公式复写 Python；
3. LinearRAG First Stage 真正拿到核心 callee body；
4. DyG Motivation 不再被底层 Mamba operation 污染；
5. Writer 输入优先是 semantic operation，而不是清洗过的 variable names；
6. DYG / LinearRAG live Candidate 在不弱化 Verified 的前提下同时提升 grounding 和 paper usability。

如果这六点成立，Code2Paper 才算从“架构修复阶段”进入真正的“论文质量闭环阶段”。
