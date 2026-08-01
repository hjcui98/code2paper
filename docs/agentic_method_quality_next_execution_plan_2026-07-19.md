# Code2Paper 下一步优化执行文件：鲁棒 LangGraph 研究写作 Agent

> **进度状态说明（2026-07-31）：**本文保留 R0–R8 的原始实施分解和合同细节，
> 但其“当前基线”和文件状态已经落后于工作区实现。R8 之后的实际进度、代码差距、
> 修改模块和退出条件由
> [`post_r8_research_agent_execution_plan_2026-07-31.md`](post_r8_research_agent_execution_plan_2026-07-31.md)
> 跟踪；总体架构仍以本文所链接的鲁棒 Research Agent 总体设计为准。

> **Agent 自主修复原则（规范性）：**规则层发现格式、schema、证据或内容错误后，
> 必须形成 typed repair issue 并返回 owning Agent 做有界重试；禁止用静默过滤、
> deterministic fallback 冒充成功、放宽硬门或降低义务覆盖来换取通过。详见
> `docs/agentic_error_feedback_and_self_repair_principle.md`。

状态：下一执行批次的规范性主计划  
日期：2026-07-19  
最后更新：2026-07-28（正式 live API 与有界思考协议）
总体设计：`docs/agentic_robust_langgraph_research_writing_design_2026-07-19.md`  
真实诊断：`docs/agentic_real_method_quality_gemma_expanded_eval_2026-07-19.json`  
行为路径参考：`docs/agentic_behavior_template_transition_reference_2026-07-19.md`

> **2026-07-28 协议优先级：**R8 正式验收改为模型、provider 和硬件拓扑无关。
> 必须证明所有实际参与角色都调用了正式 API，并保存非缓存、未阻塞、非空响应的
> trace；provider、model、脱敏 endpoint 与 capability profile digest 必须可审计。
> TP/GPU/并发拓扑、temperature/top-p/top-k、正文输出预算与思考预算继续记录，
> 但不再作为 acceptance 硬门。证据面、holdout 禁令、最终逐句可追溯和
> `unsupported=0` 仍是硬门。

## 0. 本计划解决什么

首要目标不是增加项目 profile 数量，而是实现一个可以自主研究代码的 Agent：

1. 从作者 YAML 生成 typed writing obligations；
2. 根据当前缺口自主决定搜索什么；
3. 通过 LangChain 细粒度工具检索符号、阅读源码、追调用、追数据流、检查分支和配置；
4. 把工具 observation 增量编译为通用 `CodeBehaviorGraph`；
5. 从行为子图生成最小 `EvidencePacketV3 -> CodeFactV1 -> AtomicClaimV3`；
6. 信息不足时自主换搜索策略、补 relation、拆 packet、拆 claim 或形成 explicit gap；
7. 信息充分时规划并调用已配置的正式 API 模型写出可用 Method；
8. validator 失败时只修复相关 issue，不重跑整个流水线；
9. 始终保证最终事实句只能由 executable code evidence 授权。

新总体设计不是放任 LLM 自由生成。它把决策自由放在“研究动作”上，把科研可信度固定在 deterministic evidence plane 上。

## 1. 当前基线与停止事项

### 1.1 已确认基线

| 项目 | 当前路线 | 最终支持 | 诊断 |
|---|---|---:|---|
| RAP | RAP-specific V3 | 8/8 | typed packets/facts/claims 有效，但实现硬编码 |
| EBCAR | V2 fallback | 0/9 | 宽 claim、高 fan-in、方程 contract 断裂 |
| DyG-Mamba | V2 fallback | 1/14 | 主执行路径在 writer 前丢失 |
| LinearRAG | V2 fallback | 0/8 | 草稿可读，但句子/claim 原子性和 verifier 预算失败 |

### 1.2 当前架构限制

- `graph_topology.py` 仍是固定阶段图；
- LLM 主要做固定节点路由 proposal；
- `Code2PaperStageTool` 暴露的是整阶段 `state -> result`；
- 当前没有可供 supervisor 自主组合的 symbol/search/read/trace 工具；
- `compile_evidence_v3` 依赖固定路径、符号、正则和 RAP claims；
- obligation 匹配仍有英文词面与 RAP-specific 规则；
- repair 会回到完整 intake/analysis/evidence；
- semantic verifier 使用 run-level 额度。

### 1.3 立即停止

本批不得把以下事项计为主进展：

- 再新增一个具名项目 fact/claim compiler；
- 增加全局 retrieval/evidence/authoring loop 次数；
- 扩写 prompt 代替行为图、工具和事实编译；
- 用论文文本填补代码事实；
- 在正文 contract 未通过前优化 figure；
- 推进 benchmark observation extractor、cutover 或 default-ready；
- 并发运行超过当前模型服务容量、会造成相互干扰的质量任务；具体拓扑是部署约束而非 R8 协议。

### 1.4 规范运行与测试环境

所有 Code2Paper 源码开发、LangChain/LangGraph 编排、单元测试、集成测试和 Agent 客户端运行统一使用 Conda 环境：

```text
environment: code2paper
prefix: /home/cuihengjia/miniconda3/envs/code2paper
python: /home/cuihengjia/miniconda3/envs/code2paper/bin/python
python version: 3.11.15
editable project: /home/cuihengjia/agent/Code2Paper copy
```

已验证的核心包：

```text
langchain-core==1.4.9
langgraph==1.2.8
langgraph-checkpoint==4.1.1
langgraph-checkpoint-sqlite==3.1.0
langgraph-prebuilt==1.1.0
langgraph-sdk==0.4.2
pytest==9.1.1
```

完整 `langchain` 元包不是当前依赖；工具接口使用 `langchain_core.tools.StructuredTool`。依赖安装必须从当前工作区执行：

```bash
conda run -n code2paper python -m pip install -e '.[agentic,dev]' \
  'langgraph==1.2.8' \
  'langchain-core==1.4.9' \
  'langgraph-checkpoint-sqlite==3.1.0'
```

环境验证：

```bash
conda run -n code2paper python -m pip check
conda run -n code2paper python -c \
  "from langchain_core.tools import StructuredTool; from langgraph.graph import StateGraph; import code2paper"
```

2026-07-20 迁移验证结果：`pip check` 无 broken requirements，五组核心 Agentic 定向测试共 `55 passed`。

Codex/非交互 shell 默认可能仍激活 `base`，因此规范命令必须显式使用 `conda run -n code2paper`。不得把 `base` 中偶然可导入的包当作测试通过。交互 shell 也可以先执行：

```bash
source /home/cuihengjia/miniconda3/etc/profile.d/conda.sh
conda activate code2paper
```

模型服务继续使用独立部署环境。Code2Paper Agent 在 `code2paper` 环境中通过正式 API 调用该服务；不要把 vLLM/CUDA 依赖复制进编排环境。当前 Qwen3.6/vLLM 单实例按容量串行运行，但模型、TP 和 GPU 数不是 R8 硬要求。

## 2. 目标代码结构

建议新增：

```text
src/code2paper/agentic/
  state_v3.py
  source_authority.py
  research_models.py
  research_decisioning.py
  research_policy.py
  research_supervisor.py
  research_tools.py
  research_tool_runtime.py
  research_tool_manifest.py
  graph_research_nodes.py
  graph_research_routes.py

  code_behavior_graph.py
  behavior_query.py
  behavior_path_compiler.py
  code_adapters/
    base.py
    python_ast.py

  generic_evidence_compiler.py
  generic_fact_compiler.py
  generic_claim_compiler.py
  evidence_packet_validator.py
  fact_relation_validator.py

  quality_state_v2.py
  local_repair.py

  behavior_templates/
    base.py
    registry.py
    feature_score_filter.py
    dual_attention_rerank.py
    temporal_sequence_readout.py
    sparse_propagation_ppr.py
```

修改：

```text
src/code2paper/agentic/graph.py
src/code2paper/agentic/graph_topology.py
src/code2paper/agentic/llm_decision_provider.py
src/code2paper/agentic/langchain_tools.py
src/code2paper/agentic/tools.py
src/code2paper/agentic/intent_obligations.py
src/code2paper/agentic/authoring_projection.py
src/code2paper/agentic/graph_text_trust_nodes.py
src/code2paper/agentic/checkpointing.py
src/code2paper/agentic/artifact_freshness.py
src/code2paper/agentic/traceability_ledger.py
src/code2paper/agentic/invariant_audit.py
```

当前 `evidence_compiler_v3.py` 暂时保留为 RAP positive-control adapter，待通用 compiler 重建 RAP 8/8 后删除其中的事实硬编码。

## 3. 实施批次 R0：冻结 contracts 和迁移边界

### R0.1 新增核心 contracts

实现：

- `SourceAuthorityV1`
- `AgentStateV3`
- `ResearchAgendaV1`
- `ResearchAgendaItemV1`
- `ResearchDecisionV1`
- `ResearchToolCallV1`
- `ResearchObservationV1`
- `ResearchIssueV1`
- `TextRepairIssueV1`
- `QualityStateV2`

`ResearchAgendaItemV1` 至少包含：

```text
obligation_id
priority
author_text
typed_behavior_targets
status
supported_claim_ids
missing_information
attempted_actions
candidate_symbol_ids
candidate_behavior_node_ids
gap_requirements
```

### R0.2 source authority

实现统一 source classification：

- source/script/build/config -> `executable_hard`；
- tests -> `test_scoped`；
- README/Markdown/TeX/PDF/plain text -> `semantic_hint`；
- author YAML -> `author_intent`。

所有 span、tool observation、packet、fact 和 claim 都携带 authority。`authorize_atomic_claims` 必须拒绝没有 `executable_hard` anchor 的正向实现 claim。

### R0.3 迁移方式

- 新路径使用 feature flag `agentic_research_v3`；
- legacy 和当前 P3 graph 保留，便于对照；
- 不改变默认路线；
- V3 state 与 V2 artifact 通过显式 adapter 交换，禁止隐式读写同名字段；
- checkpoint version 中写入 graph/schema version。

### R0.4 测试与退出条件

新增：

```text
tests/test_agentic_state_v3.py
tests/test_agentic_source_authority.py
tests/test_agentic_research_models.py
tests/test_agentic_v2_v3_state_adapter.py
```

退出条件：

- 所有 schema `extra=forbid`；
- invalid path、authority upgrade、unknown action 均被拒绝；
- checkpoint 能区分 V2/V3；
- 当前 RAP V3 测试无回归。

## 4. 实施批次 R1：细粒度 LangChain 研究工具

### R1.1 首批只读工具

第一批必须真实可调用：

```text
list_repository_tree
find_entrypoints
search_code
search_symbols
read_symbol
read_code_span
find_references
inspect_configuration
```

第二批行为工具：

```text
build_behavior_subgraph
query_behavior_graph
trace_call_path
trace_data_flow
inspect_control_flow
compare_implementation_branches
find_output_side_effects
```

第三批 hint 工具：

```text
search_semantic_hints
derive_code_queries_from_hint
compare_hint_to_code
```

### R1.2 工具 schema

每个检索调用必须绑定：

```text
repo_snapshot_id
obligation_id
goal
path_scope
top_k / depth / node_budget
```

每个返回必须包含：

```text
status
source_authority
result_refs
exact_span_ids
truncated
input_digest
output_digest
diagnostics
```

空结果与工具错误必须区分：

- `success_empty`：搜索执行成功但未命中；
- `scope_exhausted`：给定范围已搜索；
- `truncated`：候选仍可能存在；
- `parse_failed`：不能据此形成 code gap；
- `invalid_request`：LLM 参数被 policy 拒绝。

### R1.3 LangChain 暴露

- 每个工具使用独立 Pydantic `args_schema`；
- 生成 `agentic_research_tool_manifest.json`；
- manifest 记录读写副作用、authority、预算字段和 safe recovery；
- 使用 LangGraph `ToolNode` 或等价受控 executor；
- 不向 Agent 暴露 shell、任意 Python 或任意文件写入；
- stage tools 继续存在，但不进入 Research Supervisor 的默认 tool set。

### R1.4 测试与退出条件

新增：

```text
tests/test_agentic_research_tools.py
tests/test_agentic_research_tool_security.py
tests/test_agentic_research_tool_manifest.py
tests/test_agentic_research_tool_runtime.py
```

mutation：

- snapshot 外 path 被拒绝；
- hint 文件返回不能生成 hard evidence id；
- 模型伪造 symbol id 被拒绝；
- truncated 不能被当作 search exhausted；
- 同一输入结果 digest 稳定；
- 文件内容变化后旧 observation freshness 失败。

退出条件：用工具 API 能在 RAP、EBCAR、DyG、LinearRAG 中完成“找 entrypoint -> 找核心 symbol -> 读定义 -> 找引用”，且无需调用 legacy intake stage。

## 5. 实施批次 R2：Python CodeBehaviorGraph

### R2.1 Python AST adapter

首批解析：

- module/class/function/method；
- assignment、attribute/subscript read/write；
- call 与 argument binding；
- if/else guard；
- for/while loop；
- return；
- compare；
- arithmetic/matmul；
- concat/stack/reshape；
- sort/topk/mask/filter；
- file write/serialization；
- config/default access。

首批不要求完美 whole-program analysis。动态调用、反射、monkey patch 标记 unresolved，不猜测。

### R2.2 增量图

`build_behavior_subgraph(symbol_ids, depth, node_budget)` 只解析选定范围。图节点和关系按 snapshot/symbol/span 形成稳定 ID。重复工具调用必须去重合并。

### R2.3 relation 验证

实现：

- direct call relation；
- caller/callee return relation；
- intra-function data dependency；
- branch/control dependency；
- config guard；
- side effect；
- bounded interprocedural data flow。

无法确定的 relation 状态为 `unresolved`，不能生成 `supported` fact。

### R2.4 行为等价 mutation

必须覆盖：

- 文件移动；
- symbol 改名；
- helper 抽取；
-变量改名；
- `argsort(descending=True)[:k]` 与等价 `topk`；
- mask 构造方式变化；
-配置默认值移到 dataclass/YAML。

语义等价 mutation 应保留相同 normalized predicate；语义变化 mutation 必须改变 graph。

### R2.5 测试与退出条件

新增：

```text
tests/test_agentic_code_behavior_graph.py
tests/test_agentic_python_behavior_adapter.py
tests/test_agentic_behavior_relations.py
tests/test_agentic_behavior_mutations.py
```

退出条件：

- RAP 主线可被通用 predicate 表示，不读取 `RAP` 或固定 claim 文本；
- LinearRAG 的 seed branch、dense fallback、threshold/top-k、PPR 排序可区分；
- EBCAR 两种 attention scope 和 inference sort 有 control/data relations；
- DyG 的 `dts` 传递与 gated top-k readout 可追踪。

## 6. 实施批次 R3：LangGraph 自主研究子图

### R3.1 新 graph

新增以下拓扑：

```text
input_resolution
  -> intent_compiler
  -> repository_indexer
  -> research_agenda_builder
  -> research_supervisor
  -> research_tool_node
  -> observation_ingest
  -> behavior_graph_updater
  -> evidence_critic
```

`evidence_critic` 路由：

```text
search_more       -> research_supervisor
inspect_branch    -> research_supervisor
compile_candidate -> generic_fact_compiler
record_gap        -> gap_finalizer
ready_to_author   -> authoring_planner
blocked           -> blocked
```

### R3.2 Supervisor prompt/context

LLM 只接收紧凑 `ResearchDecisionContextV1`：

```text
active obligation
typed behavior targets
current supported facts
missing spans/relations/conditions
top candidate symbols
recent tool observations
no-progress history
remaining per-obligation budgets
allowed actions and ready tools
hard rules
```

禁止把全仓源码、完整 evidence JSON 或整个 tool history塞入 prompt。

### R3.3 模型决策与安全 merge

已配置的正式 API 模型可以提议一到多个独立工具调用；CPU 只读检索可以并行执行，LLM inference 按服务容量调度。policy merge 检查：

- action 与 issue 类型匹配；
- tool 当前 ready；
- scope 有界；
- obligation 存在；
- 没有重复无增益调用；
- 没有 authority 越权；
- budgets 可用；
- fallback 安全。

如果模型 proposal parse 失败，fallback 根据 typed issue 选择最小确定性动作，不直接阻断整个 run。

### R3.4 信息增益与预算

预算改为 per-obligation/per-tool-kind：

```text
symbol_search
code_read
call_trace
data_flow_trace
branch_inspection
hint_search
packet_repair
```

信息增益指标：

- 新 hard-source span；
- 新 symbol；
- 新 behavior predicate；
- 新 verified relation；
- obligation 缺口减少；
- candidate ambiguity 减少。

连续两轮无增益必须换策略；第三轮仍无增益才允许申请 explicit gap。禁止简单增加全局 loop。

### R3.5 测试与退出条件

新增：

```text
tests/test_agentic_research_supervisor.py
tests/test_agentic_research_policy.py
tests/test_agentic_graph_research_loop.py
tests/test_agentic_research_no_progress.py
tests/test_agentic_research_checkpoint_resume.py
```

场景测试：

- 缺 symbol -> search_symbols；
- symbol 已有但调用关系缺失 -> trace_call_path；
- 多分支 -> inspect_configuration/compare branches；
- data consumer 不明 -> trace_data_flow；
- hint/code 冲突 -> compare_hint_to_code；
- search truncated -> refine scope；
- 搜索充分仍无实现 -> explicit gap；
- checkpoint 后从 active obligation 和 best state 恢复。

退出条件：正式 API 模型在 fixture repo 中能自主完成至少三种不同工具序列，policy trace 可解释，且最终支持边界与工具顺序无关。

## 7. 实施批次 R4：通用 Evidence/Fact/Claim compiler

### R4.1 packet proposal 与 validator

LLM 通过 `propose_evidence_packet` 提交候选：

```text
obligation_id
scope
anchor_span_ids
relation_span_ids
behavior_node_ids
behavior_relation_ids
conditions
composition_rationale
rejected_candidates
```

validator 确定性检查：

- snapshot/freshness；
- source authority；
- anchor role；
- relation 是否真实存在；
- guard 是否遗漏；
- packet 是否包含无关 span；
-是否存在更小连接子图；
- rejected candidate rationale 是否成立。

### R4.2 generic facts

facts 由 behavior graph 生成，不由项目模板写死：

```text
subject = symbol/operation role
predicate = normalized behavior predicate
object = resolved operands/result
conditions = guards/config
direct spans = operation spans
relations = graph edges
```

首批支持：

```text
reads
constructs
transforms
calls_in_order
branches_on
configured_by
selects
sorts_by
filters_by
aggregates
returns
writes
loads_weights
```

### R4.3 generic claims

LLM 可以提议自然语言 claim 和 fact grouping，但 authorization 必须验证：

- claim 中每个事实成分都有 fact；
- quantifier、方向、条件、效果没有扩张；
-训练/推理、默认/可选、source/destination 等角色不混合；
- canonical identity 去重；
- rationale/effect/performance 与 implementation 分离；
- sentence-introduction claim 可独立验证。

### R4.4 equation

只有 `EquationClaimV1` 可以进入正文：

- expression 从 behavior operations 重建；
- symbols 绑定 fact operands；
- relation/guard 完整；
- prose 与 equation 使用同一 fact ids。

否则 `safe_equations=[]`。

### R4.5 测试与退出条件

新增：

```text
tests/test_agentic_generic_evidence_compiler.py
tests/test_agentic_evidence_packet_validator.py
tests/test_agentic_generic_fact_compiler.py
tests/test_agentic_generic_claim_compiler.py
tests/test_agentic_equation_claims.py
```

关键约束测试：

- core compiler 源码不得出现 `F-RAP-*`、`C-RAP-*`、EBCAR、DyG-Mamba、LinearRAG；
- 相同 behavior graph 产生稳定 fact identity；
-错误 sort direction、wrong span role、hint-only anchor 必须失败；
- 不同 guard 不能合并为无条件 claim；
- 支持 packet fan-in 超过 3，但必须是最小连接子图；
- semantic verifier 不能覆盖 deterministic failure。

退出条件：在不使用项目 claim literal 的情况下重建 RAP feature -> score -> rank/mask -> prune 主线，并保持最终正文 8/8 或语义等价支持。

## 8. 实施批次 R5：鲁棒 Intent Agent 与 obligation 对齐

### R5.1 intent compiler

作者 YAML 先由正式 API 模型提议 typed obligations，再确定性 normalize：

```text
kind
priority
desired_behavior_predicates
inputs
transformations
decisions
outputs
conditions
rationale_request
equation_request
organization_preference
risk_level
search_terms
aliases
```

作者 stage 名只能作为 organization preference，不能成为正向事实。

### R5.2 中英文与同义表达

删除以英文 token overlap 为主要授权依据的路径。lexical/embedding/LLM semantic match 只能产生 candidate alignment；最终 obligation coverage 由 typed behavior targets 与 authorized facts 决定。

### R5.3 mismatch 和 gap

作者请求但代码不存在的内容：

- 进入 verify-only agenda；
- Agent 可使用 hint 生成代码查询；
- 搜索充分后形成 explicit gap；
- 不反复消耗主线 search budget；
- 不进入正向 Method。

### R5.4 测试与退出条件

新增：

```text
tests/test_agentic_intent_compiler_v2.py
tests/test_agentic_intent_paraphrases.py
tests/test_agentic_intent_multilingual.py
tests/test_agentic_obligation_fact_alignment.py
```

同一意图的中文、英文、同义改写和 stage 重排必须形成等价 behavior targets。训练义务不能被推理 facts 错误覆盖。

## 9. 实施批次 R6：Authoring Agent、局部 repair 与质量状态

### R6.1 authoring

Planner 使用：

- author priorities；
- authorized unique claims；
- behavior relation order；
- partial qualifiers；
- explicit gaps；
- stage hints。

正式 API 模型决定论文组织，但 plan gate 确保：

- must-cover terminal 或明确 incomplete；
-每节有 unique claim；
- 顺序不违反 data/control path；
- 无 duplicate；
- 无 hint/gap 正向泄漏；
- equation 已授权；
- stage intro 有 claim。

### R6.2 TextRepairIssueV1

final validator 把失败映射到：

| failure | Agent 可选动作 |
|---|---|
| `no_semantically_matching_projected_claim` | 拆/补 claim 或合并句子 |
| `wrong_span_role` | 替换 packet anchor |
| missing relation | trace calls/data/config |
| missing qualifier | 局部 rewrite |
| unsupported rationale | 删除或 gap |
| formula unsupported | 删除 equation 或重建 EquationClaim |
| branch ambiguity | inspect config/branch |
| semantic verifier exhausted | 使用 deterministic fact relation，或按句独立验证 |

### R6.3 QualityStateV2

使用安全约束下的 Pareto selection：

- safety 不得回退；
- supported must-cover 不得减少；
- unique supported claims 不得减少；
- validated sentences 不得减少；
- duplicate/unjustified fan-in 不得增加；
- explicit gap 不能冒充 supported；
- 新状态不优于 best state 时不覆盖 best artifacts。

### R6.4 测试与退出条件

新增：

```text
tests/test_agentic_local_repair.py
tests/test_agentic_text_repair_supervisor.py
tests/test_agentic_quality_state_v2.py
tests/test_agentic_authoring_plan_v3.py
tests/test_agentic_final_text_trust_v3.py
```

退出条件：

- 一个句子失败不会重跑整篇；
- writer 句子拆分变化不会破坏 claim trace；
- repair 回退时恢复 best state；
- final unsupported rate 必须为 0 才能 trusted success；
- incomplete Method 可以安全输出为 incomplete，不伪装 complete。

## 10. 实施批次 R7：可组合 behavior templates

在 generic compiler 已通过后，才实现模板：

```text
feature_predict_score_rank_filter
embedding_augment_dual_attention_rerank
temporal_multichannel_sequence_readout
sparse_bipartite_propagation_ppr
```

模板只包含 graph query、role alias、stage hint 和 match score。禁止包含：

- 项目名作为 required condition；
- 绝对文件路径；
- 项目 claim 文本；
- 固定 evidence ids；
- 固定 fact ids；
-直接 authorization。

已知真实项目的作用：

| 项目 | 用于验证 |
|---|---|
| RAP | 通用 feature/score/filter path |
| EBCAR | 跨文件 attention、training/inference 分支 |
| DyG-Mamba | 复杂时序 data flow、code/paper conflict |
| LinearRAG | 稀疏传播、PPR、fallback、rationale gap |

退出条件：禁用所有模板时，generic compiler 仍能生成部分 supported claims；启用模板只提升路径发现和组织质量，不改变事实授权结果。

## 11. 实施批次 R8：真实 live API 质量验收

### R8.1 执行协议

每个项目：

1. 只读取代码和作者 YAML；
2. 使用正式 API 且 response cache off；
3. 保存 provider、model、脱敏 endpoint、capability profile digest 和全部参与角色的非空调用 trace；
4. 按模型服务容量安排串并行；TP、GPU、采样、正文输出预算和思考预算只记为执行元数据；
5. 固定 tool trace、decision trace、behavior graph、packets、facts、claims、Method、validation、quality states 和 summary digest；
6. 最后才读取原论文做 diagnostic comparison；
7. paper/README/TeX/PDF 不升级为 hard evidence。

### R8.2 开发集

顺序：

```text
RAP generic reconstruction
EBCAR
DyG-Mamba
LinearRAG
```

每个项目验收：

- Agent 至少发生一次基于 gap 的自主工具选择；
- 代码主线进入 Method；
- 无项目-specific claim literal；
- unsupported final sentences = 0；
- must-cover supported/partial/gap terminal；
- 无无证据方程/rationale；
- tool/decision trace 可复现；
- checkpoint/resume 结果一致。

### R8.3 holdout

至少：

- Lookahead；
- 一个此前未参与模板或 contract 设计的真实项目。

holdout 期间禁止添加项目专用 template、fact 或 claim 文本。允许修改：

- 通用 AST parser；
- predicate normalization；
- relation resolver；
- generic search policy；
- intent normalization；
- authoring/validator contract。

成功条件：

- 不修改项目专用代码即可找到并解释核心主线；
- 至少生成可信 incomplete Method；
- supported final sentences 全部追溯；
- 未覆盖内容是 explicit gap，不是 hallucination。

## 12. 提交边界

### Commit 1：contracts、authority、StateV3

- R0 全部；
- 不修改当前 graph 默认行为；
- 定向测试通过。

### Commit 2：细粒度 research tools

- R1 全部；
- LangChain manifest 与 security tests；
- 四项目只读工具 smoke test。

### Commit 3：Python CodeBehaviorGraph

- R2 全部；
- 行为等价/变化 mutation；
- 不产生正文。

### Commit 4：Research Supervisor LangGraph

- R3 全部；
- tool-calling loop、policy merge、checkpoint；
- fixture Gemma 决策测试。

### Commit 5：generic packet/fact/claim compiler

- R4 全部；
- 通用重建 RAP；
- 删除 authoring 对 RAP-specific projection 的依赖。

### Commit 6：Intent Agent 与 obligation alignment

- R5 全部；
- 中英文、同义改写、mismatch/gap。

### Commit 7：local repair、quality state、Method Agent

- R6 全部；
- RAP 完整串行 Gemma trusted regression。

### Commit 8：behavior templates + 三项目开发验收

- R7；
- EBCAR、DyG-Mamba、LinearRAG 严格串行 Gemma；
- 按失败只修通用层。

### Commit 9：holdout 与架构收口

- R8 holdout；
- 全量测试；
- 更新总体设计、完成度审计和真实项目报告；
- benchmark/cutover 仍 deferred。

每个提交只包含当前批次源码、测试和文档。当前工作区既有改动和 `__pycache__` 不得误混入。

## 13. 每批验证命令

定向测试：

```bash
conda run -n code2paper python -m pytest -q tests/test_agentic_<current_batch>.py
```

核心 trust 回归：

```bash
conda run -n code2paper python -m pytest -q \
  tests/test_agentic_contracts.py \
  tests/test_agentic_authoring_projection.py \
  tests/test_agentic_final_text_trust.py \
  tests/test_agentic_graph_topology.py \
  tests/test_agentic_graph_decisioning.py \
  tests/test_agentic_text_trust_graph.py \
  tests/test_agentic_p3_checkpoint_tools.py
```

提交前：

```bash
conda run -n code2paper python -m pytest -q
```

真实 API 运行不能被 deterministic fixture 替代。fixture 用于 contract 和 mutation；正式 API 模型用于观察实际研究决策、工具选择、正文组织和局部修复。

## 14. 第一实施切片

下一次代码改造只做 Commit 1，不同时实现四个项目模板。具体顺序：

1. 新增 source authority contracts；
2. 新增 `AgentStateV3`、agenda、decision、observation、issue schemas；
3. 新增 V2/V3 state adapter；
4. checkpoint 写入 schema/graph version；
5. artifact freshness 支持 tool observation 和 behavior graph refs；
6. 增加上述定向测试；
7. 运行当前 RAP V3 regression，证明 contracts 引入没有破坏已有 8/8 positive control。

Commit 1 完成后进入 Commit 2，优先暴露 `find_entrypoints/search_symbols/read_symbol/find_references` 四个最小工具，再补其余工具。不得跳过工具层直接开始 EBCAR profile。

## 15. 最终完成定义

只有同时满足以下条件，才能说总目标在架构层完成：

- LangGraph 中存在真实 Research Supervisor + ToolNode 循环；
- Agent 能因信息不足或 validator issue 自主选择和调用检索/追踪/补证工具；
- generic CodeBehaviorGraph 和 fact compiler 不依赖项目名、固定文件名或具名 claim；
- behavior template 只是可选搜索增强；
- 中英文/改写作者意图能投影到等价 typed obligations；
- issue-scoped repair 替代全局 stage retry；
- best state 不因修复回退而丢失；
- RAP、EBCAR、DyG-Mamba、LinearRAG 代码主线均形成 unsupported=0 的 Method；
- 至少两个 holdout 不增加项目专用 compiler 仍能生成可信 Method；
- 所有最终实现句和方法图关系都可回溯到 executable hard evidence；
- figure 次于 Method；benchmark/cutover 最后处理。
