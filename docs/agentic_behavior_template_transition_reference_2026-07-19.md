# Code2Paper 行为模板过渡参考：真实项目 Evidence Compiler 与局部决策修复

> **Agent 自主修复原则（规范性）：**规则层发现格式、schema、证据或内容错误后，
> 必须形成 typed repair issue 并返回 owning Agent 做有界重试；禁止用静默过滤、
> deterministic fallback 冒充成功、放宽硬门或降低义务覆盖来换取通过。详见
> `docs/agentic_error_feedback_and_self_repair_principle.md`。

状态：保留为真实项目行为路径和 mutation 参考；不再是规范性主执行计划  
日期：2026-07-19  
输入诊断：`docs/agentic_real_method_quality_gemma_expanded_eval_2026-07-19.json`  
总目标：根据作者意图和代码信息，产出信息完整、组织合理、逐句可追溯、可以继续编辑成论文的 Method 正文。

## 0. 当前结论

下一步不再增加 prompt、全局 loop 或 benchmark。现有 RAP vertical slice 已证明 `EvidencePacketV3 + CodeFactV1 + AtomicClaimV3 + constrained Gemma writer + reverse validator` 可以工作：RAP 真实 Gemma 运行生成 185 词、8 个事实句，8/8 有代码支持。

当前阻塞点是 V3 仍是单项目实现。新增的 LinearRAG 串行 Gemma 全流程进一步证明，正文组织已经不是唯一问题：即使三段式草稿可读、4/4 must-cover 终态覆盖，宽 claim、重复 claim、超大 evidence union 和 run-level semantic verifier 仍会让最终 8/8 事实句全部失败。

- `evidence_compiler_v3.py::compile_evidence_v3` 用 RAP 的固定符号集合识别路径；
- `_compile_facts` 和 `_compile_claims` 内置 `F-RAP-*`、`C-RAP-*`；
- `authoring_projection.py::_build_v3_projection` 内置 RAP claim 分组、标题和写作规则；
- EBCAR、DyG-Mamba 与 LinearRAG 不命中该 profile，回退到 V2 宽 claim；
- V2 在 writer 前把每个 claim 绑定到 14--22 个 span，并依赖一个全局 semantic-verifier budget；
- 最终出现“上游 evidence support 0.882--0.939，最终 unsupported 0.929--1.0”的目标错位。

因此本批目标是把“RAP 专用编译脚本”改成“结构指纹触发、可注册、保留历史最优状态、可局部修复的跨项目 Evidence Compiler”，并用 EBCAR、DyG-Mamba、LinearRAG 三个串行 Gemma 全流程验收。

## 1. 新真实基线

| 项目 | 编译路线 | must-cover | 唯一投影 claim | 平均 evidence fan-in | 最终事实句 | 最终支持 | 结果 |
|---|---|---:|---:|---:|---:|---:|---|
| RAP | V3 | 全部终态 | 8 | 最小 packet | 8 | 8 | success |
| EBCAR | V2 fallback | 5/6 | 5 | 13.89 | 9 | 0 | blocked |
| DyG-Mamba | V2 fallback | 4/5 | 4 | 20.29 | 14 | 1 | blocked |
| LinearRAG | V2 fallback | 4/4 | 4 | 10.63 | 8 | 0 | blocked |

EBCAR、DyG-Mamba 和 LinearRAG 的干净质量运行均使用 `gemma4-31b-nvfp4`、temperature 0、cache off，并严格串行。并发启动后停止的 EBCAR/DyG r1，以及被 sandbox 阻断本地 vLLM 请求的 LinearRAG r1，不进入任何质量结论。两张 GPU 共同承载一个 TP=2 vLLM 实例；并发任务会共享 decode scheduling、KV cache、吞吐、timeout 和 retry 行为，只能用于吞吐测试，不能用于正文质量比较。

LinearRAG 的新增诊断尤其重要：writer 已经产出 159 词、三个语义段落，组织顺序与源码及原论文的高层阶段一致；失败发生在 projection 和 validator contract。8 个 projected claim 只有 4 个唯一 claim，最大 direct evidence fan-in 为 21；五个普通句因一次全局 semantic-verifier 调用后预算耗尽而失败，另外还存在句子/claim 原子性不一致和无代码支撑的 pruning rationale。`method_plan_quality=100` 与最终 `0/8 supported` 再次冲突。

## 2. 目标架构

```text
Author YAML
  -> IntentObligationGraph
  -> unresolved high-value obligation
  -> structural profile matcher
  -> exact symbol/source index
  -> EvidencePacketV3 (minimal spans + relations)
  -> CodeFactV1 (typed executable facts)
  -> AtomicClaimV3 (canonical dedup + explicit gaps)
  -> obligation terminal coverage
  -> semantic stage planner
  -> Gemma Method writer
  -> sentence-level reverse validator
  -> retain best quality state
  -> local packet/fact/binding/writer repair or trusted Method
```

作者意图决定“应该解释什么和如何组织”，代码决定“允许陈述什么”。profile 只能由符号、AST、调用和数据流结构触发，禁止按项目名触发。

## 3. 批次 A：把 V3 从 RAP 硬编码拆成 profile registry

### A1. 保留通用 contract，拆出编译接口

保留已有模型：

- `EvidenceSpanV3`
- `RelationEvidenceV3`
- `EvidencePacketV3`
- `CodeFactV1`
- `AtomicClaimV3`
- `ExplicitCodeGapV1`

新增以下内部接口：

```python
class EvidenceCompilerProfile(Protocol):
    profile_id: str
    def match(index: SourceIndex) -> ProfileMatch: ...
    def build_packets(index: SourceIndex, obligations: IntentObligationGraphV1) -> list[EvidencePacketV3]: ...
    def build_facts(packets: EvidencePacketSetV3) -> list[CodeFactV1]: ...
    def build_claims(facts: CodeFactSetV1, obligations: IntentObligationGraphV1) -> AtomicClaimSetV3: ...
    def build_stage_groups(claims: AtomicClaimSetV3) -> list[SemanticStageGroupV1]: ...
```

`ProfileMatch` 必须记录 required/optional structural fingerprints、命中理由和未命中原因。`compile_evidence_v3` 只负责 registry 选择、统一校验、digest 和 artifact 输出，不再包含某个项目的事实文本。

建议文件变更：

- 保留 `src/code2paper/agentic/evidence_compiler_v3.py` 作为 contracts、orchestrator、common validators；
- 新增 `src/code2paper/agentic/evidence_profiles/base.py`；
- 新增 `src/code2paper/agentic/evidence_profiles/rap_pruning.py`，机械迁移当前 RAP profile；
- 新增 `src/code2paper/agentic/evidence_profiles/ebcar_reranker.py`；
- 新增 `src/code2paper/agentic/evidence_profiles/dynamic_graph_mamba.py`；
- 新增 `src/code2paper/agentic/evidence_profiles/linear_graph_retrieval.py`；
- 新增 `src/code2paper/agentic/evidence_profiles/registry.py`。

### A2. 让 projection 消除项目硬编码

新增 `SemanticStageGroupV1`：

- `stage_id`
- `name`
- `purpose`
- `ordered_claim_ids`
- `covers_obligation_ids`
- `relation_evidence_ids`
- `organization_priority`

`_build_v3_projection` 从 `AtomicClaimSetV3 + SemanticStageGroupV1` 通用生成 projection。删除其中固定的 `C-RAP-*` 分组、RAP 标题、Softmax column-zero 写作规则。项目特异条件只能来自 claim 的 canonical wording、conditions、qualifiers 和 explicit gaps。

退出条件：RAP 的输出与既有 V3 fixture 语义等价；EBCAR、DyG-Mamba、LinearRAG profile 可使用同一 projection 函数。

### A3. V3 不命中时 fail closed

在 Method authoring 模式中，若 must-cover obligation 存在但没有 V3 编译结果：

- 允许 V2 继续产生 retrieval/diagnostic artifacts；
- 禁止把 V2 broad-claim projection 标为 usable authoring input；
- 产生 `compiler_profile_missing` 或 `generic_path_compilation_required`；
- 路由到 profile/generic compiler repair，而不是让 writer 生成高 fan-in 草稿后再失败。

V2 仍保留为兼容和检索层，不再作为复杂项目正文的最终授权层。

## 4. 批次 B：EBCAR vertical slice

EBCAR 优先于 DyG-Mamba：路径短、训练与推理均在同一核心类中，适合先验证 registry、跨文件 relation、equation policy 和通用 projection。

### B1. 结构指纹

profile 只在以下结构同时成立时激活：

- 某 reranker 类同时具有 `forward` 与 `rerank`；
- passage 表示与 document-id/passsage-id 表示相加；
- query 与 passages 沿序列维拼接；
- encoder layer 包含一个 unmasked attention 和一个 masked attention；
- fixed query 与 contextual passage 做矩阵乘；
- inference 对 similarity descending sort。

不得检查字符串 `EBCAR` 作为激活条件。

### B2. EvidencePacketV3

| packet | anchor | relation | 必须编译的行为 |
|---|---|---|---|
| `EP-EMBED-STRUCTURE` | `EBCarRerankerHybridAttention.forward/rerank` | `get_passage_positional_encoding`、配置分支 | document ID embedding、sin/cos passage position、与 passage embedding 相加、query/passages 拼接 |
| `EP-HYBRID-ATTN` | `TransformerEncoderLayerHybridAttention.forward` | `MultiheadAttention.forward`、mask construction | shared full attention 无 mask；dedicated attention 使用同文档+query mask；两路输出相加后进入残差/FFN |
| `EP-CONTRASTIVE` | `EBCarRerankerHybridAttention.forward` | labels、temperature、logsumexp | 保留原始 query，点积 contextual passages，temperature scaling，单正例 InfoNCE |
| `EP-RERANK` | `EBCarRerankerHybridAttention.rerank` | `evaluate_EBCAR` 调用 | contextual passages、fixed query dot product、temperature、descending sort、返回文本与分数 |

核心源文件：

- `src/model/ebcar_dedicated_attention_model.py`
- `src/model/transformer_encoder_hybrid_attention.py`
- `src/evaluate.py`
- `src/dataset/__init__.py` 仅在需要证明 dense top-k retrieval 输入时加入 packet。

每个 claim 默认 1--3 个 span；mask 构造与 attention 消费跨函数时允许 4 个 span，但必须写 composition rationale。禁止把 forward、rerank、evaluate、dataset 的全部 evidence 做并集后绑定到每句。

### B3. CodeFactV1 与 claim decomposition

至少编译：

- `constructs`：document ID table、frozen sinusoidal passage-position table、same-document mask；
- `transforms`：passage + document ID + passage position；query/passages concatenation；
- `calls_in_order`：augment -> concatenate -> hybrid encoder -> contextual passages -> dot product -> sort；
- `branches_on`：`add_positional_encoding`、`use_dedicated_attention`；
- `computes_formula`：scaled dot-product attention、InfoNCE 的实际 logsumexp 实现；
- `selects`：exactly one positive passage in training；
- `sorts_by`：similarity descending；
- `returns`：reranked text and relevance scores。

正文 stage 固定为语义分组而不是 YAML 标题复刻：

1. embedding and structural augmentation；
2. hybrid context encoder；
3. contrastive objective；
4. inference reranking。

### B4. equation policy

本 slice 默认 prose-first。方程只有在新增 `EquationClaimV1` 或等价的 `AtomicClaimV3(claim_kind=configuration_fact/implementation_behavior)` 并满足以下条件时才能进入正文：

- expression AST/token 可从 exact code operations 重建；
- symbols 绑定到 CodeFact；
- equation 绑定 direct/relation evidence；
- final text extractor 和 validator 使用同一 contract。

否则 `safe_equations=[]`。禁止继续使用 generic `MultiBranch` 等 code-pattern equation。

### B5. EBCAR 验收

- profile 由结构指纹激活；
- 4 个 must-cover stage 均为 supported/partial/explicit gap；
- projection 无 canonical duplicate；
- 每个普通 claim direct fan-in <= 3，超出有 rationale；
- Method 明确写出 document/passage structure、两种 attention scope、fixed query、InfoNCE 和 descending rerank；
- 不出现无 contract 方程；
- Gemma 最终逐句 unsupported = 0；
- Method plan gate 与 final reverse validation 同时通过，不能只有 report-only 100 分。

## 5. 批次 C：DyG-Mamba vertical slice

DyG-Mamba 用于验证复杂跨函数 data flow、代码/论文冲突和局部 claim repair。

### C1. 结构指纹

- temporal embedding 方法调用 first-hop neighbor sampler；
- node/edge/time/co-occurrence 四通道被分别投影并 stack/reshape；
- elapsed-time features 被单独计算并传入 sequence encoder；
- encoder 调用接收 `dts`；
- source/destination sequence 做 cross attention；
- learned gate -> softmax -> top-k -> renormalize -> weighted sum；
- node embedding 进入 link predictor 或 node classifier。

不得用项目名、paperdraft 或论文术语激活。

### C2. packet 和事实主线

| packet | anchor | 必须证明的关系 |
|---|---|---|
| `EP-DYG-HISTORY` | `DyGMamba.compute_src_dst_node_temporal_embeddings` | first-hop sampling -> pad source/destination histories |
| `EP-DYG-CHANNELS` | 同上 | `get_features` + `NeighborCooccurrenceEncoder` + four projection layers -> stack/reshape |
| `EP-DYG-DELTAT` | `DyGMamba.get_dt_features` | timestamp differences -> normalization -> TimeEncoder -> projection -> encoder `dts` |
| `EP-DYG-SSM` | `MambaTimeDelta.forward` | input projection/conv -> dt/B/C construction -> negative exponential A -> selective scan |
| `EP-DYG-READOUT` | `DyGMamba.compute_src_dst_node_temporal_embeddings` | cross attention -> gate softmax -> top-k -> renormalization -> weighted sum -> output layer |
| `EP-DYG-TASK` | training/evaluation entrypoint | source/destination embeddings -> `MergeLayer` + sigmoid/BCE，或 node embedding -> `MLPClassifier` |

核心源文件：

- `models/DyGMamba.py`
- `models/mamba_simple.py`
- `models/modules.py`
- `train_link_prediction.py`
- `train_node_classification.py`

### C3. conflict-aware gaps

作者意图或论文提示中的以下内容不得自动成为正向事实：

- spectral norm constraints on B/C；
- MEAN pooling；
- paper 形式的 learnable exponential timespan equation；
- performance、robustness、complexity 结论。

若当前 executable path 没有找到相应操作，生成 explicit code gap 或 paper/code mismatch。当前代码实际可写的是 learned gated top-k weighted pooling；不能把 paper 的 MEAN pooling 和代码路径合并。

### C4. DyG 验收

- Method 覆盖 history -> four-channel encoding -> dt path -> Mamba -> cross attention -> gated top-k pooling -> task head；
- 每个跨函数顺序由 relation evidence 支撑；
- spectral norm、MEAN pooling 等冲突不进入正向正文；
- 不出现 positional-encoding 或 MultiBranch 等无关方程；
- canonical claim 无重复；
- 所有 must-cover 义务有终态；
- Gemma 最终逐句 unsupported = 0。

## 6. 批次 D：LinearRAG vertical slice

LinearRAG 用于验证非神经网络主线、稀疏图操作、分支路径、句子/claim 原子性和 rationale 边界。它不能只作为“已有成功项目回归”：最新干净串行 Gemma 运行已经证明 V2 草稿虽然可读，但最终仍是 `0/8 supported`。

### D1. 结构指纹

profile 只在以下结构同时成立时激活：

- indexing 路径执行 passage embedding、sentence segmentation/NER，并建立 entity--sentence 与 passage--entity 映射；
- retrieval 路径先从 query NER 和 entity embedding similarity 构造 seed entities；
- entity activation 路径包含 entity--sentence/sentence--entity sparse matrices、query--sentence similarity、per-entity top-k 和 threshold；
- activated entity scores 与 dense passage similarity 共同形成 graph reset/node weights；
- passage ranking调用 personalized PageRank，并按 passage score 降序返回 top-k；
- 无 seed entity 时存在 dense retrieval fallback。

不得用 `LinearRAG`、`Tri-Graph`、论文标题或 `paperdraft.md` 文本作为 profile 激活条件。

### D2. packet 和事实主线

| packet | anchor | 必须证明的关系 |
|---|---|---|
| `EP-LR-INDEX` | `LinearRAG.index` | batch NER -> entity/sentence extraction -> embeddings -> mapping -> passage/entity graph edges |
| `EP-LR-SPARSE` | `_precompute_sparse_matrices` | entity-to-sentence 与 sentence-to-entity COO sparse tensors 的 exact construction |
| `EP-LR-SEED` | `get_seed_entities` | query NER -> normalized entity embedding -> similarity argmax -> seed score |
| `EP-LR-PROPAGATE` | `calculate_entity_scores_vectorized` | threshold -> per-entity top-k unused sentences -> query-sentence weighting -> sparse propagation -> accumulation -> next active entities |
| `EP-LR-PASSAGE` | `calculate_passage_scores` | dense similarity normalization + activated-entity occurrence/tier bonus + optional attribute branch -> passage node weight |
| `EP-LR-PPR` | `graph_search_with_seed_entities` / `run_ppr` | entity and passage weights -> reset vector -> personalized PageRank -> descending passage order |
| `EP-LR-RETURN` | `retrieve` | seed branch or dense fallback -> retrieval top-k -> passages and scores |

核心源文件首先限于：

- `src/LinearRAG.py`
- `src/ner.py`
- `src/embedding_store.py`，仅在证明输入/返回 contract 时加入。

默认每个 claim 使用 1--3 个 direct span；跨函数调用顺序放入 relation evidence。禁止再次让 Tri-Graph claim 绑定 20 个 span，或让 dynamic-pruning claim绑定 index、propagation 和 retrieval 的 21-span 并集。

### D3. claim decomposition 与 rationale policy

必须把以下行为拆成不同 atomic claims：

1. offline entity/sentence extraction 与映射构造；
2. sparse adjacency tensor construction；
3. query entity matching 和 seed score；
4. thresholded active-entity selection；
5. per-entity top-k unused-sentence selection；
6. query-sentence weighted sparse propagation与 score accumulation；
7. hybrid passage initialization；
8. personalized PageRank、descending ranking和 top-k return；
9. no-entity dense fallback。

以下内容不得从阈值分支直接提升为实现事实：

- prevents exponential growth；
- improves efficiency；
- reduces noise；
- linear scalability；
- information-lossless construction；
- retrieval quality/performance。

这些属于 rationale、复杂度或经验性义务；没有可执行/构建/实验硬证据时生成 explicit gap。论文中的 compact MAX propagation equation 不能覆盖当前向量化实现；若不能从 exact sparse operations、top-k、mask、accumulation 和 threshold 重建 EquationClaim，则 `safe_equations=[]`。

句子 claim extractor 必须与 AtomicClaim 共用原子性规则。允许两种安全输出：

- writer 将“stage intro + mechanism”写为一个可匹配事实句；
- compiler 另外生成有 direct evidence 的 stage-introduction claim。

禁止出现“第一阶段激活实体”因被拆成独立句而没有 matching claim 的情况。

### D4. LinearRAG 验收

- profile 由结构指纹激活；
- Method 覆盖 index -> sparse matrices -> seed entities -> threshold/top-k sparse propagation -> hybrid passage initialization -> PPR/ranking/return；
- dense fallback 作为有条件 claim，而不是与 graph branch 混写；
- canonical claim 无重复，普通 direct fan-in <= 3；
- pruning 的性能/rationale 只在有独立硬证据时进入正向正文；
- 方程必须服从当前 executable path；
- 句子和 claim decomposition 一致；
- Gemma 最终逐句 unsupported = 0。

## 7. 批次 E：把全局 retry 改成局部 repair

当前 `graph_text_trust_nodes.py` 已识别 `return_to_packet_binding_repair`，但实际回到整个 evidence stage，可能重新跑 intake/analysis/grounding。新增 typed repair request：

```text
PacketRepairRequestV1
  claim_id
  packet_id
  failure_type
  offending_span_ids
  missing_relation_type
  requested_scope
  attempt
```

路由表：

| final failure | 局部动作 | 禁止动作 |
|---|---|---|
| `wrong_span_role` / `direct_evidence_semantically_unrelated` | replace/split packet span，重编受影响 fact/claim | 全仓 retrieval |
| `no_semantically_matching_projected_claim` | claim decomposition 或 writer wording repair | 扩 evidence union |
| missing call/data/control relation | trace 指定 source/target symbol | 重跑 LLM code synthesis |
| qualifier missing | authoring-only rewrite | analysis loop |
| formula unsupported | drop equation 或建立 EquationClaim | 用 semantic verifier 放行 |
| code/paper mismatch | explicit gap + code-preferred claim | 合并叙事 |

V3 的确定性 predicate/relation validator 通过后，不要求逐句再消耗 semantic verifier。V2 semantic verifier 可保留为诊断，但不能用一个 run-level 预算限制正文句数。

### E1. repair 必须质量单调

每次 repair 前后计算并持久化 `QualityStateV1`，至少包含：

```text
terminal_must_cover_count
unique_supported_claim_count
unsupported_claim_count
duplicate_claim_count
max_direct_evidence_fan_in
validated_final_sentence_count
unsupported_final_sentence_count
explicit_gap_count
```

状态选择按以下优先级比较，而不是默认接受“最新一轮”：

1. safety invariant 不能回退；
2. terminal must-cover 不能减少；
3. unique supported writable claims 不能减少；
4. unsupported/duplicate claims 不能增加；
5. evidence fan-in 不能无理由扩大；
6. 已通过逐句验证的句子不能丢失。

新状态若不优于当前 best state，则丢弃新全局 artifact，只保留 repair request 与失败诊断。checkpoint 同时保存 `current_state` 和 `best_quality_state`；resume 从 best state 继续局部 repair。LinearRAG 中间轮次出现过 must-cover 对齐回退，证明该约束是正文决策架构的一部分，不是日志优化。

## 8. 批次 F：重新定义 authoring 和 usability gate

`EvidenceBoundAuthoringPlan.hard_gate_passed` 不能再只检查“存在 section 且每节有 evidence”。必须同时满足：

- 所有 must-cover obligation 已 terminal，或明确标记 incomplete draft；
- projected claim canonical dedup 完成；
- stage group claim 顺序与 relation graph 一致；
- 普通 claim evidence fan-in 达到最小性要求；
- equation contract 与 final validator 一致；
- 每个 stage 至少一个唯一 claim；
- plan 不包含 forbidden/gap 作为正向事实。

`method_plan_quality.json` 从 report-only 诊断改成 gate 输入，或删除其授权含义。只要 final reverse validation 失败，它不得显示可授权的 100 分结果。

## 9. 实施顺序与提交边界

### Commit 1：profile registry + RAP 无回归

- 拆 registry/base/profile；
- 迁移 RAP 硬编码；
- projection 改为消费通用 stage groups；
- RAP V3 fixtures 和全量测试通过。

### Commit 2：EBCAR profile + prose-only equation gate

- 实现 EBCAR packets/facts/claims/stages；
- 禁止无 EquationClaim 的 equation；
- deterministic fixtures；
- EBCAR 串行 Gemma 全流程。

### Commit 3：DyG profile + conflict-aware gaps

- 实现 DyG data-flow/SSM/readout/task packets；
- explicit mismatch/gap；
- deterministic fixtures；
- DyG 串行 Gemma 全流程。

### Commit 4：LinearRAG profile + atomicity/rationale gate

- 实现 index、seed、propagation、passage initialization、PPR packets；
- sentence/claim atomicity 共用 contract；
- rationale 和 paper/code equation gap；
- LinearRAG 串行 Gemma 全流程。

### Commit 5：local repair + best-state retention + usability gate

- PacketRepairRequestV1；
- 局部路由、freshness 与 QualityStateV1；
- checkpoint/resume 保留 best quality state；
- plan/usability gate；
- RAP、EBCAR、DyG、LinearRAG 串行回归。

每个提交只包含本批源码、测试和文档；当前工作区中已有的无关修改和生成的 `__pycache__` 不得混入。

## 10. 测试计划

定向测试至少包含：

```text
tests/test_agentic_evidence_compiler_v3.py
tests/test_agentic_evidence_profile_registry.py
tests/test_agentic_evidence_profile_ebcar.py
tests/test_agentic_evidence_profile_dyg_mamba.py
tests/test_agentic_evidence_profile_linearrag.py
tests/test_agentic_authoring_projection.py
tests/test_agentic_final_text_trust.py
tests/test_agentic_intent_obligations.py
tests/test_agentic_graph.py
tests/test_agentic_quality_state.py
```

必须新增 mutation：

- 删除/改名关键 symbol 后 profile 不得误激活；
- 把 same-document mask 改成全零后 dedicated-attention claim 必须失败；
- 把 descending sort 改为 ascending 后排序 claim 必须变化；
- 移除 DyG 的 `dts` 传递后 time-conditioned claim 必须失败；
- 移除 top-k 或 renormalization 后 readout claim 必须失败；
- 加入只存在于 README/paperdraft 的 spectral norm 文本不得产生硬事实；
- 移除 LinearRAG threshold、per-entity top-k、used-sentence mask、score accumulation 或 PPR descending sort 后相应 claim 必须失败或变化；
- 只加入“exponential growth/efficiency/noise control”论文文本不得产生 LinearRAG 正向实现 claim；
- writer 把 stage introduction 拆成独立句时必须匹配 introduction claim，或在写作前合并句子，不能留到 final validator 才失败；
- repair 后 must-cover 或 unique supported claim 回退时必须恢复 best quality state；
- equation 无 exact operation binding 时必须被 projection 删除。

## 11. 真实运行协议

每个质量运行：

1. 只读取代码和作者 YAML；
2. 使用 Gemma 完整运行，temperature 0、cache off；
3. 两张卡共同服务一个 TP=2 实例，项目严格串行；
4. 固定 Method、packets、facts、claims、coverage、validation、summary digest；
5. 最后才读取原论文作 diagnostic comparison；
6. paper/README/TeX/PDF 仍不能升级为 hard evidence。

验收顺序：EBCAR -> DyG-Mamba -> LinearRAG -> RAP regression。Lookahead 在上述三条新 profile 稳定后作为 generic compiler recall 测试，不在本批前半段扩张范围。

## 12. 本批完成定义

本批只有同时满足以下条件才完成：

- RAP 不再依赖 projection 中的项目硬编码，仍保持 8/8 trusted Method；
- EBCAR、DyG-Mamba 和 LinearRAG 均命中结构 profile 而不是 V2 authoring fallback；
- 三个新项目的 Method 都覆盖各自代码主线；
- 所有最终事实句逐句 direct/relation evidence 通过，unsupported rate = 0；
- 所有 must-cover obligation 为 supported、partial 或 explicit gap；
- 无 generic equation 泄漏；
- local repair 不再重跑无关 intake/analysis；
- repair 保留 lexicographically best quality state，不再因新一轮 artifact 覆盖而回退；
- 全量测试通过；
- benchmark/cutover 仍保持 deferred，figure 只从已通过的 Method claim 投影。
