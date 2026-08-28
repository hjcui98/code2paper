# Method Authoring 原文—意图—代码—运行链质量诊断与下一阶段执行计划

- 日期：2026-08-27
- 状态：`READY_FOR_SERIAL_IMPLEMENTATION`
- 性质：2026-08-22 Method 意图优先写作执行权威之下的**下一阶段代码级工作包**。
- 证据窗口：三项目原文、作者意图、实际仓库、冻结研究及 `225116` authoring replay。
- 上位约束：
  1. `docs/agentic_robust_langgraph_research_writing_design_2026-07-19.md`；
  2. `docs/publication_ready_method_writer_design_2026-07-31.md`；
  3. `docs/post_r8_research_agent_execution_plan_2026-07-31.md`；
  4. `docs/method_intent_first_authoring_redesign_2026-08-22.md`。
- 关系：本文件不建立第二套架构，不替代以上规范；它把
  `docs/method_authoring_six_round_report_2026-08-27.md` 的表面问题推进到逐内容单元、逐阶段、
  逐代码落点的下一轮实施路线。若与上位文档冲突，以上位文档为准并返回 Codex。
- 非结论：本文不是 `publication_ready`、D5、default cutover 或 release freeze。

---

## 0. 执行裁决

下一阶段的主问题不是“Writer 还不够会润色”，也不是“maxLength 仍不够大”。三篇最终
Candidate 的主要质量损失发生在 Writer 之前，并在 Writer 之后被放大：

```text
作者叙事单元
  -> 研究没有按主链搜到，或只搜到孤立符号
  -> 证据已存在但没有绑定到作者字段/步骤/条件
  -> Planner/Architect 把多步机制压成平铺 brief 或错误 H2
  -> Formalizer 没拿到连通操作链，或生成的包没有正文消费位
  -> Writer 同时面对互相冲突的 brief、semantic frame、claim、facet 和 gate 指令
  -> 生成一段墙、极性错误、意图/实现混写或无公式正文
  -> representation/coverage/reverse gate 重写或拒绝整节
  -> callback 对已有信息重复编译，却没有产生可恢复 section
```

因此本轮只做一件完整的事：建立并消费一条**内容单元链**。它不新增事实权威，而是把现有
`AuthorMechanismFacetV1`、`SemanticArgumentFrameV1`、`MethodArgumentUnitV1`、
`SectionArgumentGraphV1` 和 Writer 输出串成可追踪的 source-to-render ledger，使每个重要
方法步骤或公式都能回答四个问题：

1. 作者为什么要求写它、它在故事中的位置是什么；
2. 仓库实际支持哪些字段、条件和数据流，哪些与作者声明冲突；
3. 它在哪个阶段丢失、被拒绝或被错误改写；
4. 下一次修复应回到 Research、Aligner、Planner、Formalizer、Writer 还是表示层。

本轮明确停止以下优化方向：

- 不再用 H2 数、字符数或 `maxLength` 单独代表质量；
- 不再把 Writer 多调用几次当作质量策略；
- 不再让 Formalizer 对“整节像不像公式”做一次宽泛生成；
- 不再为一个 callback 新事实全量重跑所有 section；
- 不把原论文文字、项目路径、项目符号或已知答案写进 generic 生产逻辑；
- 不削弱 Verified、FAC、numeric/formula、authorship、checkpoint 或 final-integrity 门；
- 不因 Candidate warning 删除已经生成的最佳正文。

---

## 1. 取证范围与判定方法

### 1.1 绑定证据

**六轮汇总与最终 authoring 产物**

- `docs/method_authoring_six_round_report_2026-08-27.md`
- `/tmp/c2p-serial-20260826-225116.log`
- `/tmp/c2p-synth-linearrag-20260826-225116`
- `/tmp/c2p-synth-dyg-20260826-225116`
- `/tmp/c2p-synth-ebcar-20260826-225116`

**冻结研究与真实研究轨迹**

- LinearRAG：`/tmp/c2p-fresh-linearrag-20260825-164605`
- DyG：`.tmp/c2p-stage1-canary/run-dyg`
- EBCAR：`.tmp/c2p-stage1-canary/run-ebcar`
- 每个冻结根下的 `artifacts/research_product/research_trace.json`、`agent_trace.json`、
  `run_summary.json` 与 `research_stage_checkpoint_v1.json`

**原文与作者意图**

- LinearRAG：仓库内 `paperdraft.md` 与
  `/data1/users/cuihengjia/code2paper/paperyaml3/LinearRAG - Linear Graph Retrieval-Augmented Generation on Large-scale Corpora.yaml`
- DyG-Mamba：仓库内 `paperdraft.md` 与
  `/data1/users/cuihengjia/code2paper/paperyaml4/DyG-Mamba_ Continuous State Space Modeling on Dynamic Graphs.yaml`
- EBCAR：仓库内 `paperdraft.md` 与
  `/data1/users/cuihengjia/code2paper/paperyaml3/EBCAR - Embedding-Based Context-Aware Reranker.yaml`

原文在本分析中是**离线质量 oracle 和 mismatch 清单**，不是实现事实授权源。真实产品可能
根本没有原论文；生产路径必须从作者意图生成同等粒度的 story/facet obligations，再用仓库证据
判定实现状态。

### 1.2 分析粒度

逐字复制原文不是目标。本文把原文每个段落、枚举步骤和公式拆成最小的“论文内容单元”：

```text
Content unit
  = story role
  + subject / operation / inputs / outputs
  + condition / polarity / order
  + equation role（若有）
  + author-intent source
  + repository evidence or mismatch
  + expected paragraph/formula position
```

一个句子若同时写“输入、变换、条件和效果”，必须允许拆成多个字段；一个公式若只是前一句
机制的数学表达，应与该机制共享 unit，而不能成为孤立的 equation sentence。分析输出按四类
归因：

| 终态 | 含义 | 修复 owner |
| --- | --- | --- |
| `not_discovered` | 仓库中存在相关主链，但 Research 没有读到或没形成可编译关系 | Research |
| `discovered_unbound_or_blocked` | span/fact/claim 已存在，但对齐、分节或 gate 清空/拒绝了它 | Aligner / Planner / Harness |
| `rendered_low_quality` | 已进入 Writer 输入且写出，但极性、结构、公式或学术表达不合格 | Writer / Formalizer / Rewrite |
| `intent_code_mismatch` | 作者目标与当前可达代码不同；必须双侧保留，不能硬合并 | Candidate policy / author review |

---

## 2. 三篇原文的真实组织逻辑与可获得来源

### 2.1 LinearRAG：先建索引，再局部激活，最后全局排序

原文不是五个等长主题段，而是一条严格的数据流：

```text
关系抽取的动机
  -> 离线 passage/entity index + sentence auxiliary lookup
  -> query seed entities（无实体时 dense fallback）
  -> 六步 local activation + prune + accumulate
  -> passage reset score
  -> personalized PageRank
  -> top-k passages / answer generation
```

逐内容单元映射如下。

| 原文位置 | 论文内容单元 | 作者意图作用 | 仓库实际证据 | 当前需要的判定 |
| --- | --- | --- | --- | --- |
| `paperdraft.md:3` | training-free、relation-free、两阶段总览 | 给 Architect 整体顺序 | `LinearRAG.graph_search` 顺序调用 entity score、passage score、PPR | 支持两阶段；“三类 graph vertex”不能由此授权 |
| `:7-17` | passage embedding、spaCy NER、passage→entity、sentence→entity、增量 JSON、双向 lookup | Offline 的输入和辅助结构 | `index` 调 embedding store、`SpacyNER.batch_ner`、JSON/lookup 更新；稀疏矩阵预计算 | 应形成多个 ordered units，不应是一段 generic overview |
| `:19-29` | graph 只有 passage/entity 两类节点；entity-passage 频率边和 adjacent-passage 边 | Offline graph 的精确定义 | `add_nodes` 只加入 passage/entity；`add_edges` 构建频率边与相邻边 | 与 YAML/总览“三节点 Tri-Graph”冲突，必须记 mismatch |
| `:37-43` | query NER、entity cosine、top-1 seed；无 entity 时 dense fallback | Retrieval 入口 | `get_seed_entities`、question NER、dot/cosine与 fallback | 冻结正文基本遗漏，应由入口数据流搜索补齐 |
| `:47-60` | sentence lookup→cosine→top-k→co-entity→父分数乘相似度→低于阈值丢弃→加和 | Stage 1 核心算法 | `calculate_entity_scores` 的 `continue`、乘法、top-k、累积；vectorized 分支也有 threshold mask | 必须保留“低于则排除”的极性和六步顺序 |
| `:62-64` | BFS 与 sparse/vectorized 两实现模式 | 配置/实现分支 | `calculate_entity_scores` 与 `calculate_entity_scores_vectorized` | 只能写代码实际共有语义；“完全等价”需额外验证 |
| `:70-83` | DPR 与 entity bonus 的 hybrid passage score、tier attenuation、scale、attribute bonus | Stage 2 reset 的构造逻辑 | `calculate_passage_scores:504` 及附近 bonus/scale/attribute 分支 | 有现成公式链；当前 Candidate 反而写得最空 |
| `:85-99` | 非负 reset、PPR、damping、PRPACK、descending top-k | 全局传播与输出 | `run_ppr` 的 clamp、igraph `personalized_pagerank`、damping、PRPACK、排序 | 公式可 repository-derived，但邻接矩阵记号属于论文表达层 |

这里有一个必须保留的原文/意图/代码冲突：原文总览和 YAML 把 LinearRAG 称为 entity、sentence、
passage 三节点图；同一原文 Offline 小节和实际 igraph 代码却只有 entity、passage 两类 vertex，sentence
是辅助字典/稀疏矩阵。`225116` Candidate 写成“directed three-type graph”且又声称索引不用外部 NER，
两者都不能由代码支持。正确正文应把“sentence-level bridge structure”与“persisted igraph vertex”分开，
并生成 author review mismatch，而不是让 Formalizer补一套三节点邻接矩阵。

### 2.2 DyG-Mamba：编码、时间感知 SSM、交互读出三层不是同一权威

原文的逻辑是：先构造时间序列及四通道表示，再定义连续 SSM 和离散化，随后说明时间间隔如何
进入步长及 B/C，最后通过 cross-attention 和 top-k router 读出。它不是统一的“五个 H2、每节一段”。

| 原文位置 | 论文内容单元 | 仓库证据 | 判定 |
| --- | --- | --- | --- |
| `paperdraft.md:5-7` | first-hop history、最近截断、padding、target 置首 | `DyGMamba.compute_src_dst_node_temporal_embeddings` 与 padding helper | 可 repository statement |
| `:9-31` | node/edge/time/co-occurrence 四信号、各自投影、stack 到 `4d_c` | `get_features`、`TimeEncoder`、`NeighborCooccurrenceEncoder`、四 projection 与 reshape | 可直接形成两到三段，不应混入最后 router |
| `:39-45` | continuous SSM 与离散 recurrence | Mamba selective-scan 参数化提供实现关系；连续方程是学术抽象 | hybrid：实现绑定 + Formalizer 学术记号 |
| `:47-59` | normalized gap、inverse length、time encoder、softplus step | `get_dt_features`、`projection_dt`、`MambaTimeDelta.dt_generate_layer` 与 `dt_proj` | 核心代码可证；“更大 gap 保证单调更大 Δ”没有被当前链证明 |
| `:61-71` | B/C 由 timespan 而不是 content 生成 | `MambaTimeDelta` 仅在 `time_mamba=True` 时走该分支；训练配置未设置该值，默认 False | author target 与当前默认可达路径 mismatch |
| `:73-83` | 双向 linear cross-attention | `CrossAttention.forward` | 可 repository statement |
| `:85-95` | gate、top-k、softmax renormalize、weighted sum、output projection | `DyGMamba.py:242-245` 及后续 pooling/output | 可 repository statement；YAML 的 mean pooling 与代码冲突 |

DyG 至少有三处必须分权威表达：

1. YAML 声称 B/C 有 spectral norm 约束，仓库搜索没有找到对应 enforcement；不得作为实现事实；
2. 原文声称 B/C 来自 timespan，但默认 `time_mamba=False` 的可达路径让 B/C 来自 content；
3. YAML 下游写 mean pooling，实际代码是 top-k routing pooling。

当前 Candidate 把这些内容揉成“repository evidence partially confirms”一段，并仍写 spectral norm；
这不是 Writer 单句措辞问题，而是上游没有给它“字段级 source conflict + active configuration path”。

### 2.3 EBCAR：原文短不代表方法缺失，作者意图补出了训练与推理

EBCAR 原文只有 Structural Augmentation 与 Hybrid-Attention 两个核心 H2；YAML 则补充检索输入、
InfoNCE 训练和 dot-product 推理。质量不能按“必须生成五个与其他项目同长 H2”评估。

| 内容单元 | 原文/意图 | 仓库证据 | 判定 |
| --- | --- | --- | --- |
| passage embedding reranker | 原文总览 + YAML retrieve/query/passages | `evaluate.py` 调 retriever/embedding 后构造候选集 | 可写输入接口；不应因上游 Contriever 未读完阻塞核心模型 |
| relative document ID | 原文 `:5-7` | `doc_embedding` 与候选集 relative doc IDs | 可 repository statement；“embedding 已冻结”当前代码写法需谨慎核验 |
| sinusoidal passage position | 原文 `:5-7` | `get_passage_positional_encoding` 与 frozen positional tensor | 可 repository statement |
| shared full attention | 原文 `:11-14` | `transformer_encoder_hybrid_attention.py` 的 `shared_attn` | 可 repository statement |
| same-document dedicated attention | 原文 `:11-14` | mask 构造 + 独立 `dedicated_attn`，两路输出相加 | 可 repository statement |
| ablation switch | YAML/配置 | flag false 时使用全零 mask，dedicated module 仍执行全局 attention | 不能写“dedicated path 被 bypass” |
| InfoNCE | YAML training | `forward` 中 original query 与 contextualized passage dot product、temperature、`logsumexp` | 可给精确公式；当前 Formalizer 零调用是路由失败 |
| rerank | YAML inference | `rerank` 中同一结构处理后 dot product、descending sort | 可 repository statement |

EBCAR 冻结研究在 5 turn 后因 Contriever 路径阻塞，仅产出 8 个事实；但核心模型文件已经在本地且
几乎逐项证明 YAML。正确调度应把“中心机制 + repo-local 可发现性”排在上游 retriever 细节之前；
一个外部/上游义务失败不能终止其余高价值本地义务。

---

## 3. `225116` 的逐阶段损失账

### 3.1 证据是否被发现

| 项目 | 已发现 | 未发现/未形成关系 | 根因 |
| --- | --- | --- | --- |
| LinearRAG | NER、实体传播、部分 PPR/score 事实大量存在 | seed fallback、六步完整顺序、hybrid score/PPR 公式没有稳定进入正确 section unit | 后半程重复研究 spaCy/PPR 单点，缺少按 story slot 的“够了”终态 |
| DyG | 56 facts，时间分支和部分编码操作存在 | first-hop→四通道→SSM→cross-attn→router 的主入口链没有按顺序闭合 | Research turn 读 CAWN、FilterLayer、EdgeBank，按符号名漂移，直到末尾才回 channel alignment |
| EBCAR | 8 facts，触及 hybrid model | structural augment、mask、InfoNCE、rerank 没成为完整证据链 | 前几 turn 卡在 Contriever 后 `policy_merge_fallback_exhausted`，没有跳过阻塞义务继续核心本地文件 |

Research 现有 `InformationGainTracker` 以新 span/symbol/ref/predicate/relation 计增益；这能防完全相同的
工具调用，却不知道一个新 span 是否填了论文内容单元的 `input/transformation/condition/output` 槽。
因此它可能为“又读到一个 PPR 配置 span”清零 no-progress，却没有使任何 section 更可写。

### 3.2 已发现但未绑定或被拦截

最终 facet 对齐分布说明“缺内容”不能简单归因为 Research：

| 项目 | facet 分布 | required facet | 说明 |
| --- | --- | --- | --- |
| LinearRAG | 22：mismatch 16、unresolved 5、entailed 1 | mismatch 6、unresolved 2、entailed 1 | 大量 claim/span 已候选绑定，但整字段 judge 判 mismatch |
| DyG | 25：mismatch 16、unresolved 7、partial 2 | mismatch 10、unresolved 2、partial 2 | 没有一个 entailed；真实时间支路也未形成可直接使用闭包 |
| EBCAR | 30：mismatch 28、unresolved 2 | mismatch 15、unresolved 1 | 核心操作代码明确，但对齐几乎全 mismatch，明显不是纯检索缺失 |

`method_argument_facet_aligner.py` 当前在 `entailed` 时要求 `supported_fields` 与 facet 字段集合完全
相等；formula 还必须已有 equation atom。任一闭集校验失败时，`normalize` 路径把 status 改为
`unresolved`，并同时清空 claim/span/equation、supported fields 和 exact excerpts。这个 fail-closed
行为对 Verified 安全，但作为 Candidate source ledger 太粗：一个字段错误会抹掉已经证明的其他字段，
后续 Writer 只看见“作者 specification”而不是“哪些部分已实现”。

具体的 discovered-but-blocked 还包括：

- DyG Downstream section 已有 2283 字符 Writer 输出，却因 `caveat_token_shell` / fused
  `## heading**Body` 表示失败被整节拒绝；
- LinearRAG 和 DyG Formalizer 各生成 2/3 组 package，但正文 `used_equation_ids` 全为 0；
- LinearRAG Writer 声明了大量 used claims，但质量报告出现 58 个
  `supported_claim_not_rendered`；DyG 为 40，EBCAR 为 8；
- `publication_quality.py` 会正确指出“声明 used 不等于正文已表达”，但修复没有回到缺失的
  semantic slot，后续只得到整节重写；
- `product_authoring_graph.persist_product_authoring_state_from_writer` 对只要存在的节点 artifact
  统一写 `information_gain=True`，导致 ledger 无法诚实区分“文件重写了”和“内容变好了”。

### 3.3 已绑定、已写出但质量不高

三个 Candidate 共同有以下表现：

1. **多步机制变成一段墙。** 最长的机制节有 3–4k 字符但仍只有一个正文段；schema 只放宽长度，
   没有要求按 argument unit / semantic flow cluster 产出段落。
2. **条件与极性丢失。** LinearRAG 把“小于阈值则 continue/排除”写成“fall below 时 admit”；
   这是 condition/polarity 没有作为必须渲染字段，而不是普通英文错误。
3. **作者意图与 active code path 混写。** DyG 把 spectral norm、timespan B/C 与真实默认分支揉成
   同一实现描述。
4. **明确公式被省略，虚构公式反而出现。** LinearRAG 的 passage score/PPR 与 EBCAR InfoNCE
   都有直接代码，而最终正文没有 display math；此前 Formalizer 却为三节点图和激活 recurrence
   生成无 fact/equation binding 的表达。
5. **L2 太抽象且失去段落归属。** `scientific_claim_ir.py` 会生成
   “Values that fail the comparison are excluded”、normalize/topk/weighted-sum 等通用句；
   `writer_view_projection.py` 又把它们统一包装为 `reader_subject="licensed technical effect"`。
   当 section 绑定不牢时，这些句子可贴到无关的 SSM 或 retrieval 段。
6. **prompt 权威互相打架。** brief lane 的 `content_first_instruction` 要求
   “Use writer_view as the only content plan”，同一 payload 的 `grounding_contract` 又规定 positive fact
   只能来自 `argument_flow.semantic_frames`。已有 semantic frame 虽被序列化，brief 主路径并没有清楚
   告诉 Writer 如何以它为步骤骨架、以 facet policy 为措辞权威，模型只能在数个平行 JSON 通道中猜。

### 3.4 影响速度但没有提高质量的步骤

| 步骤 | 绑定现象 | 为什么当前无增益 | 下一阶段处置 |
| --- | --- | --- | --- |
| Writer generic content repair | L/D/E 分别 2/4/4 轮；commit 全为 0 | 同一 section 全文重写，没有定位缺失 slot；monotonic gate 拒绝后不改变上游输入 | 一次无 semantic delta 立即停；按 owner/slot 修 |
| Formalizer section LLM | L/D/E 调用 2/3/0；正文使用 equation 为 0 | 调用单位过宽、包无消费位或无闭集绑定；EBCAR 反而未路由 | 先有 formula obligation + paragraph slot 才调用；无绑定包不进入 Writer |
| Planner batch | 非空 draft L 11/22、D 15/23、E 8/30；其余 planner_failed | 批次结构化完成不等于每个 brief 有可用机制；失败文本仍产生后续负担 | 改按 ordered content cluster；空 draft 不触发 Writer 扩写 |
| Research supervisor 思考 | DyG supervisor 约 760s、工具执行约 3s；EBCAR 约 165s/0.5s | 大量时间在选择搜索动作，未按入口和 story slot 推进 | deterministic mainline bootstrap + 只在分叉处让 LLM 选择 |
| LinearRAG callback tail | 约 65 min；相同 PPR/config 请求多轮 COMPILE_EVIDENCE；`resume_section_ids=[]` | 新事实/fulfilled 不等于 mandatory slot 闭合；每轮全量重编译 | 请求 semantic digest 去重；有 slot delta 才局部重编译和 resume |
| representation retry | missing section 最多两次 whole-section retry | heading/markdown 损伤触发昂贵内容重写，仍可能丢正文 | 先做字节保持的 representation repair；内容不变时不调 Writer |

必须保留但改变作用方式的步骤：reverse validation、Verified splitter、final-integrity 和 Candidate
warning 不能删除；它们应产出 typed issue 和 owner 路由，而不是用删除 Candidate 证明严格。

---

## 4. 目标合同：复用现有语义帧，新增 source-to-render 追踪

### 4.1 不新造事实权威

仓库已经有足够的核心模型：

- `AuthorMechanismFacetV1`：作者语义的最小判断面；
- `FacetEvidenceAlignmentV1` / `CandidateFacetPolicyV1`：Candidate 字段支持与措辞模式；
- `SemanticFlowSlotV1` / `SemanticFlowEdgeV1` / `SemanticArgumentFrameV1`：代码操作、条件与数据流；
- `MethodArgumentUnitV1` / `SectionArgumentGraphV1`：论文论证与分节；
- `WritingResearchRequestV1.mandatory_missing_slots`：写作期定向回搜；
- `PublicationMethodSectionOutputV1`：Writer 结构化回报。

本轮不再创建另一个 Concept Card/Proposition/Brief 权威。新增的 `MethodContentTraceV1` 只是**派生
观测 artifact**，把以上现有 ID 串起来；任何字段都不能凭该 trace 获得 Verified 许可。

### 4.2 字段级绑定必须保留部分真值

将 facet alignment 从“一个 facet 一个总 status”升级为闭集字段结果：

```text
FacetFieldBindingV1
  field_name                 # subject / operation / input / output / condition / effect / formula
  status                     # entailed / partial / mismatch / unresolved
  polarity                   # positive / negative / threshold_lt_excludes / ... generic enum
  bound_claim_ids
  bound_fact_ids
  bound_span_ids
  bound_equation_ids
  exact_excerpts
  active_path_conditions
  unsupported_reason
```

`FacetEvidenceAlignmentV1.status` 保留为汇总兼容字段，但规则改为：

- 有任一字段被证明时，不得因另一字段失败而清空这些字段的绑定；
- `mismatch` 只表示有实际矛盾证据，不得把“未找到”或“语义 judge 不确定”当 mismatch；
- formula 未有 equation atom 时，只让 formula 字段 unresolved，不抹掉 mechanism 字段；
- motivation/novelty/guarantee 仍不能由代码 entailed；
- `verified_directly_allowed` 仍只由 deterministic `AuthorClauseLicenseV1` 派生。

### 4.3 从 semantic frame 生成段落，不从长度猜段落

在 `SectionArgumentGraphV1` 中增加 `paragraphs: tuple[SectionParagraphPlanV1, ...]`，或在保持兼容的
前提下把等价字段放入已有 moves。每个 paragraph plan 至少闭集绑定：

```text
paragraph_id
paragraph_role               # overview / construction / step_sequence / formula / interface / output / mismatch
argument_unit_ids
required_facet_ids
ordered_semantic_slot_ids
required_edge_ids
formula_obligation_ids
expected_sentence_range
transition_from / transition_to
```

规则：

- 一个多步 algorithm unit 可以占多个 paragraph；多个同一操作的 rhetorical moves 不得生成重复段；
- `ordered_semantic_slot_ids` 必须保留 condition 与 output；
- formula paragraph 只有在前一机制 paragraph 有消费点时存在；
- 短方法如 EBCAR 可以只有 2–3 个核心段加训练/推理，不强造五节；
- H2 结构由作者 story spine 决定，paragraph 数由 semantic clusters 决定，字符长度仅是防截断上限。

### 4.4 Source-to-render trace

新增持久 artifact `method_content_trace_v1.json`：

```text
MethodContentTraceRowV1
  content_unit_id
  source_story_node_ids / facet_ids
  source_authority_lane
  field_bindings
  semantic_frame_id / ordered_slot_ids
  argument_unit_id / section_id / paragraph_id
  formula_obligation_ids / accepted_formula_package_ids
  writer_rendered_span_refs
  final_validation_refs
  terminal_state
  owner
  stop_reason
```

`terminal_state` 只能是：

```text
not_discovered
discovered_partial
discovered_bound
planned
rendered
rendered_invalid
blocked_representation
intent_code_mismatch
deferred_with_reason
```

这张 trace 允许报告“哪一句为什么没写”，但不能成为 Writer lexical source，也不能给 claim 许可。

---

## 5. 代码级执行工作包

实施必须串行；每包先跑聚焦回归并记录 `.agent/implementation.md`，不得一次重写整条主链。

### WP0 — 冻结逐内容单元质量 oracle

**目的：** 在改生产逻辑前，把三篇原文的段落、步骤、公式、已知 mismatch 固定为测试/评估清单，
避免后续只看字符数或幸运样本。

**修改**

- 扩展 `tests/fixtures/method_synthesis_funnel/` 下现有三项目 fixture；不复制整篇原文，只保存
  generic semantic expectations：story role、操作、条件极性、公式角色、允许 mismatch。
- 扩展 `tests/fixtures/method_synthesis_funnel/baselines_v1.json`，记录 `225116` 的 source-to-render
  基线：facet 状态、nonempty draft、Writer calls/repair commits、formula calls/used equations、
  paragraph count、dropped sections。
- `tests/test_agentic_method_content_regression.py` 新增 oracle loader 和逐 unit 断言。

**边界**

- 项目名和已知答案只允许在 fixture/评估代码；
- generic production 模块不得判断 LinearRAG/DyG/EBCAR 名称或固定 symbol；
- 原文措辞不作为 exact substring gate，使用 semantic field/flow/formula role 断言。

**退出**

- 三篇每个核心段/步骤/公式有唯一 evaluation unit；
- 三处关键 mismatch（Linear graph node types、DyG active B/C path、EBCAR dedicated ablation）可被
  fixture 表达；
- `225116` 基线能明确区分 not-discovered、blocked 和 low-quality-rendered。

### WP1 — 字段级 alignment 与内容 trace

**负责文件**

- `src/code2paper/agentic/method_argument_brief_models.py`
- `src/code2paper/agentic/method_argument_facet_aligner.py`
- `src/code2paper/agentic/method_argument_models.py`
- 新增 `src/code2paper/agentic/method_content_trace.py`
- `src/code2paper/agentic/autonomous_method_agent.py`
- `src/code2paper/agentic/product_authoring_graph.py`

**实施**

1. 增加 `FacetFieldBindingV1`，并让 alignment/policy 暴露逐字段绑定；保持现有总 status 的读取兼容。
2. `merge_facet_alignment_policy` 对未知 ID、digest 错误仍 fail-closed，但只清空失败字段，不清空
   已验证字段。
3. 增加 condition/polarity 的 generic 表示；由 comparison/control-flow relation 推导，不能靠 Writer
   重新猜 `<`/`continue` 的含义。
4. `method_content_trace.py` 从现有 artifacts 派生 trace；不接受自由文本，不生成 prose。
5. `product_authoring_graph` 的 attempt receipt 以 source trace delta 决定 `information_gain`；删除“只要
   artifact 存在就 true”的行为。

**聚焦测试**

- `tests/test_agentic_method_argument_briefs.py`
- `tests/test_agentic_method_argument_brief_integration.py`
- `tests/test_agentic_method_product_models.py`
- `tests/test_agentic_callback_semantic_contract.py`

**退出**

- 一条 compound facet 中 mechanism entailed、guarantee unresolved 时，mechanism 绑定仍保留；
- “小于阈值后 continue”被表示为 exclude，而不是无方向 comparison；
- EBCAR exact model span 不再因 InfoNCE equation 未编译而让整条 mechanism mismatch；
- trace 能显示每个 required facet 当前停在哪一阶段。

### WP2 — Research 从符号漂移改为 story-slot 主链搜索

**负责文件**

- `src/code2paper/agentic/intent_target_proposer.py`
- `src/code2paper/agentic/research_models.py`
- `src/code2paper/agentic/research_nodes.py`
- `src/code2paper/agentic/research_supervisor.py`
- `src/code2paper/agentic/research_policy.py`
- `src/code2paper/agentic/research_graph.py`
- `src/code2paper/agentic/research_tools.py`
- `src/code2paper/agentic/behavior_graph_tools.py`

**实施**

1. 每个高优先级 facet 先生成 mandatory semantic slots；Research query 绑定 slot，不再只绑定宽泛
   obligation 文本。
2. 默认 bootstrap 顺序：入口/配置→主模型 forward→callee→数据流→control condition→输出。已有
   entrypoint 时先 `TRACE_CALLS/TRACE_DATA_FLOW`，不先全库符号漫游。
3. 调度优先级采用 `author importance × mainline centrality × repo-local discoverability`。某个外部或
   上游组件阻塞时记录 gap，并继续下一高价值本地 slot。
4. gain 从“新 span 数”升级为“新 slot field / active-path condition / contradiction 被闭合”；孤立新
   span 可以记录 discovery，但不能重置 semantic no-progress。
5. 编译一次后若 slot digest 不变，当前 request 终止为 precise gap；禁止多 turn 重复
   `COMPILE_EVIDENCE`。
6. 搜索不到 spectral norm 等声明时持久 negative evidence scope：读过哪些入口/配置/模块、为什么
   只能判 unresolved/mismatch；不得将字符串搜索为空直接证明全仓不存在。

**聚焦测试**

- `tests/test_agentic_graph_research_loop.py`
- `tests/test_agentic_research_no_progress.py`
- `tests/test_agentic_research_supervisor.py`
- `tests/test_agentic_research_policy.py`
- `tests/test_agentic_research_tools_extended.py`
- `tests/test_agentic_research_graph_callback_continuation.py`

**退出**

- EBCAR 风格夹具即使 upstream retriever 阻塞，也继续读本地 model forward、loss、rerank；
- DyG 风格夹具从主模型入口到 encoder/SSM/readout，不因同名 auxiliary 模块漂移；
- 相同 semantic digest 的重复 compile 不消耗第二个 LLM turn；
- 新 span 未填 mandatory slot 时 `information_gain=false`。

### WP3 — Planner/Architect 生成有序机制单元与段落合同

**负责文件**

- `src/code2paper/agentic/method_argument_brief_planner.py`
- `src/code2paper/agentic/method_argument_brief_compiler.py`
- `src/code2paper/agentic/method_architect.py`
- `src/code2paper/agentic/method_argument_models.py`
- `src/code2paper/agentic/writer_view_projection.py`
- `src/code2paper/agentic/scientific_claim_ir.py`

**实施**

1. Planner 输入以一个 story node 下的 ordered facets + field bindings + semantic frame 为单位，不再对
   每个薄 brief 分别生成可能为空的 mechanism sentence。
2. Planner 输出是结构化 `what/why/how/condition/output/formula-position`，不是终稿散文；空或 parse
   失败时保留 deterministic ordered frame，而不是写 `planner_failed` 文本交给 Writer 猜。
3. Architect 生成 `SectionParagraphPlanV1`；required paragraph 按 semantic cluster，而不是按 H2 family
   或 maxLength 推导。
4. `scientific_claim_ir` 的 L2 必须绑定原始 subject、operation、condition/polarity、producer/consumer
   section；删除可跨任意机制使用的无主语句。无法保留这些字段时不生成 L2 prose，只保留 operation
   atom 给 frame。
5. `writer_view_projection` 不再把所有 E2 统一变成
   `reader_subject="licensed technical effect"`；投影实际 subject/operation/condition 和 paragraph id。

**聚焦测试**

- `tests/test_agentic_method_argument_brief_planner.py`
- `tests/test_agentic_method_argument_brief_integration.py`
- `tests/test_agentic_method_architect_product_readiness.py`
- `tests/test_agentic_method_synthesis_output.py`
- `tests/test_agentic_method_synthesis_runtime.py`

**退出**

- 六步机制夹具得到至少两个有序 paragraph plans，并保持 prune condition；
- EBCAR 短结构不会被强行展开成五个空 H2；
- 同一 top-k/normalize operation 不会因词重叠进入无关 SSM section；
- Planner parse 失败不会丢失 deterministic semantic frame。

### WP4 — Formalizer 改为 mechanism-bound、consumer-first

**负责文件**

- `src/code2paper/agentic/equation_claims.py`
- `src/code2paper/agentic/formalization_agent.py`
- `src/code2paper/agentic/publication_method_writer.py`
- `src/code2paper/llm/response_schemas.py`

**实施**

1. `MethodFormulaObligationV2` 绑定 paragraph、facet、ordered slots、前置条件和 formula lane；整节
   `required_formula=True` 不再是主要路由条件。
2. 只有存在 Writer consumer paragraph 时才调用 Formalizer；没有消费位的 package 不生成。
3. `repository_derived` 必须绑定连通 operation chain 的 fact/equation/span；
   `author_intent_academic` 只能形式化作者已声明关系；`hybrid_partial` 逐项标 authority。
4. package validator 检查 condition/polarity、symbol table、operand closure、active configuration path；
   不允许三节点图、spectral guarantee 等未绑定关系混入 repository lane。
5. Writer 必须回报 `used_formula_package_ids` 与 `used_equation_ids`；package 没被正文使用则成为
   `formula_not_consumed` issue，不把显示公式静默贴在节尾。
6. `_paste_missing_formula_blocks` 仅承担 representation-only 恢复；不得决定公式应放在哪一段，也不得
   让贴后 spam 删除贴前正文。

**聚焦测试**

- `tests/test_agentic_formalization_guards.py`
- `tests/test_agentic_publication_method_writer.py`
- `tests/test_llm_publication_schema_closed_sets.py`
- `tests/test_agentic_method_content_regression.py`

**退出**

- code-backed hybrid score/PPR、time-gap step、InfoNCE fixture 能生成绑定公式并被指定 paragraph 使用；
- 无 active-path 支持的 timespan B/C 只可 hybrid/mismatch，不能 repository-derived；
- 无 consumer 的 Formalizer 调用数为 0；
- `used_equation_ids=0` 时不得把 package 计为质量增益。

### WP5 — Writer 使用一个主合同，按段落事务生成

**负责文件**

- `src/code2paper/agentic/publication_method_writer.py`
- `src/code2paper/llm/section_writer.py`
- `src/code2paper/llm/writer_section_repair.py`
- `src/code2paper/agentic/publication_issue_owner_router.py`
- `src/code2paper/agentic/publication_quality.py`

**实施**

1. 统一 brief lane 与 semantic-frame lane：`paragraph_plan` 是组织主合同，facet policy 决定措辞模式，
   semantic frame 是实现事实源，formula package 是数学表达源。删除“writer_view only”与
   “semantic_frames only”并存的矛盾提示。
2. Writer 可一次生成整节，但结构化输出必须按 paragraph id 回报：
   `rendered_facet_ids`、`rendered_slot_ids`、`rendered_formula_package_ids`、span offsets。
3. 接受门先验证 paragraph/slot coverage，再验证长度；一个 3k 字符单段不能冒充五步已覆盖。
4. 每个条件槽必须有同 paragraph witness；比较极性靠结构化 binding 验证，不靠关键词 overlap。
5. Candidate 的 author specification/mismatch 写完整机制，warning 进入 sidecar；不得用反复
   “intended/pending”替代内容。Verified 仍只收 deterministic license + reverse validation 通过 span。
6. content repair 只重写失败 paragraph；若候选没有增加 rendered slots、修复立即 no-progress，保留
   incumbent。whole-section regeneration 仅在 response 完全不可解析且没有可保存段落时允许一次。

**表示层单独处理**

- `## heading**Body`、HTML residue、LaTeX escape、heading/body 换行属于 representation repair；
- repair 必须证明词序和正文 bytes 除分隔符外未改变；
- 修复前正文始终保留；表示失败不得升级为第二次内容生成；
- `caveat_token_shell` 只能在正文确实没有机制谓词时成立，不能因 heading 熔接把 2k 字正文判空。

**聚焦测试**

- `tests/test_llm_section_writer.py`
- `tests/test_llm_writer_section_repair.py`
- `tests/test_agentic_publication_method_writer.py`
- `tests/test_agentic_writer_paper_language_quality.py`
- `tests/test_agentic_publication_issue_owner_router.py`

**退出**

- 每个 required paragraph 和 slot 有 exact authored witness；
- LinearRAG prune 极性 mutation 会被拒绝，正确极性通过；
- DyG fused heading repair 保留完整 Downstream 正文且不新增 Writer call；
- 三个 zero-commit repair 夹具都在第一次无 delta 后停止；
- Candidate warning 不删除 incumbent，Verified 仍 fail-closed。

### WP6 — callback/resume 只为真实内容增量付费

**负责文件**

- `src/code2paper/agentic/writer_research_router.py`
- `src/code2paper/agentic/callback_semantic_contract.py`
- `src/code2paper/agentic/writing_callback_fulfillment.py`
- `src/code2paper/agentic/product_authoring_graph.py`
- `src/code2paper/agentic/autonomous_method_agent.py`

**实施**

1. request identity 由 section + argument unit + mandatory slots + authority lane + baseline semantic digest
   决定；同义 query 不得成为新请求。
2. Research 返回后先算 field/slot delta；没有 delta 时不重编译 authoring、不调用 Writer。
3. 有 delta 时只失效依赖相应 facet/frame/paragraph 的 section；禁止每轮全量重建所有计划和正文。
4. `fulfilled` 只有在 owning validator 确认 mandatory slots 闭合时成立；“新增若干 facts”不足以
   resume。
5. `resume_section_ids` 必须来自 before/after content trace 的可写性改变；若为空，立即停止该 request，
   不进入下一 callback round。
6. 每个 request 一个无增益 round 即停；全篇预算仍服从 2026-08-22 WP-C 上限。callback 耗尽后写
   author specification + precise review item，不输出壳。

**聚焦测试**

- `tests/test_agentic_autonomous_callback_fulfillment.py`
- `tests/test_agentic_callback_resume_product.py`
- `tests/test_agentic_callback_semantic_contract.py`
- `tests/test_agentic_research_graph_callback_continuation.py`
- `tests/test_agentic_research_checkpoint_resume.py`

**退出**

- LinearRAG PPR 风格请求已有事实时不重复 COMPILE_EVIDENCE；
- 新事实未闭合 mandatory slot 时不 resume；
- 闭合一个 section 的 slot 只重编译/重写该 section；
- callback trace 不再出现“fulfilled + `resume_section_ids=[]` 后继续下一轮”。

### WP7 — 质量报告从计数改为内容链审计

**负责文件**

- `src/code2paper/agentic/publication_quality.py`
- `src/code2paper/agentic/publication_replay_diagnostics.py`
- `scripts/run_authoring_replay.py`
- 相关 run summary / report renderer

**实施**

每次 authoring 输出以下分离指标，不合成总分：

- high/critical content units：discovered、field-bound、planned、rendered、validated；
- condition/polarity exact coverage；
- ordered-slot / required-edge coverage；
- formula obligations：routed、accepted package、consumed、rendered display math；
- paragraph plan：planned、rendered、wall paragraph、duplicate operation；
- intent-code mismatch preservation；
- owner repair：attempts、semantic delta、commit、stop reason；
- callback：request digest、slot delta、recompile scope、resume section；
- Candidate 与 Verified 各自状态；
- LLM 调用数、wall time、无增益调用数。

`supported_claim_not_rendered` 继续保留，但不再单独代表论文内容召回；一个 claim 可能只是实现原子，
而一个论文 unit 可能需要多个 claims/edges/conditions。

**退出**

- 报告能直接列出“原文/意图核心 unit 在哪一层丢失”；
- 任何 `information_gain=true` 都能指向新增 field/slot/paragraph/formula consumption；
- 字符变长但 semantic coverage 不变时，质量报告不记为提高。

---

## 6. 验证顺序

OpenCode 实施时按以下顺序执行并将命令、退出码、摘要和代码状态写进 `.agent/implementation.md`。
Codex 最终验收不重跑这些命令或 API。

### 6.1 每包聚焦验证

按 WP 指定测试文件运行：

```bash
python -m pytest -q <named focused test paths>
git diff --check
```

必须包含 mutation/negative cases，而不是只测试 happy path：

- threshold polarity 反转；
- 一个 facet 部分支持、部分 unresolved；
- active/default configuration 与 dormant branch 冲突；
- formula package 有生成但无 consumer；
- heading/body 熔接但正文完整；
- callback 有新 span、无新 mandatory slot；
- Writer repair 字符变化但 rendered slot 无变化。

### 6.2 静态里程碑

WP0–WP7 全部完成后一次运行：

```bash
python -m pytest -q
python -m compileall -q src tests
git diff --check
```

完整 suite 成功只证明静态回归，不授权 live 质量 PASS。

### 6.3 冻结 authoring-only replay

先保持与六轮报告可比的协议：三个冻结研究根、fresh output、callback=0、revision budget=0。运行时使用
AGENTS.md 当前指定的 `http://127.0.0.1:8003/v1` / `qwen36-27b-nvfp4`，除非当时权威配置另有更新。
预检记录 `/health`、`/v1/models`、model identity、queue/KV-cache 和输出目录；不得打印 secret。

这一轮只回答：在相同冻结证据下，source-to-render 链是否减少上游丢失和无效重写。不得与旧
qwen38@8006 的绝对文字偏好直接混成模型对比，但可比较结构化语义指标。

每项目至少审计：

**LinearRAG**

- Offline 明确区分 sentence auxiliary structure 与 two-type igraph；
- seed + fallback、六步 activation、低于阈值排除、BFS/vectorized 分支；
- hybrid passage score 与 PPR 有正文消费的 display math；
- 不再写 directed three-node graph/no NER；
- 不是一个 3k 字单段。

**DyG-Mamba**

- encoding 四通道、time-gap step、actual B/C active path、cross-attention、top-k readout 顺序完整；
- spectral norm、mean/top-k、timespan/content B/C 冲突进入 mismatch/review，不硬合并；
- Downstream 不因 fused heading 丢失；
- 公式 lane 与 active path 一致。

**EBCAR**

- doc ID + passage sinusoid + shared/dedicated attention 写成紧凑核心，不灌五节模板；
- InfoNCE 与 rerank 从实际代码进入正文；
- flag false 的 dedicated behavior写准确；
- 不再反复声称“仓库没有证据”。

### 6.4 有界 callback 协议

只有 authoring-only replay 达到本文件的结构化退出条件后，才另开 `callback-rounds=1` 的新协议，
fresh output，不复用失败目录。它只证明 §1.6：

- request 绑定 mandatory slots；
- 新证据产生 slot delta；
- 只恢复受影响 section；
- 无 delta 一轮停止；
- wall time 不出现重复 compile 长尾。

callback=0 与 callback=1 的结果必须分开报告，不得把后者随机更长/更短文字归因给代码修复。

---

## 7. 验收门

### 7.1 必须满足

1. 三项目所有 high/critical evaluation units 都有明确 terminal state，不能无记录消失；
2. 已证明字段不因同 facet 另一字段失败而被清空；
3. Candidate 中条件/极性错误为 0；mismatch 双侧保留；
4. required semantic slot/edge/formula package 有正文 witness，不以 Writer 自报 ID 代替；
5. multi-step section 按 paragraph plan 分段；短方法不被统一模板膨胀；
6. formula-worthy code-backed unit 有被正文消费的 display math，或有精确 typed failure；
7. representation repair 不删完整正文，不触发不必要 whole-section LLM 重写；
8. Writer/Planner/Formalizer/callback 的每次额外调用都产生可追踪 semantic delta；无 delta 一轮停止；
9. Candidate 始终保留 best incumbent；Verified 与 publication readiness 继续独立、fail-closed；
10. generic 生产代码没有三个项目的名称、路径、claim 文本或已知答案。

### 7.2 可以诚实保留

- Candidate 有 author specification、mismatch 和人工 review 项；
- Verified 很短或空；
- `publication_ready=false`；
- 某些原文理论保证没有仓库证明；
- callback=0 replay 仍有 unresolved slots；
- 本地模型文风仍需 Editor/人工修改。

这些不是删减 Candidate 或放宽 Verified 的理由。

### 7.3 失败条件

- 只把 maxLength 再调大或提高重试次数；
- source trace 新增了很多 ID/哈希，却没有改变最终 unit coverage；
- 仍把新 span 数当作 section 可写性的充分条件；
- facet 部分失败继续清空全部 exact evidence；
- Formalizer 仍生成未被 Writer 使用的 package 并计为成功；
- Writer 仍主要输出一段墙、generic L2、代码审计语句或重复 caveat；
- callback 仍全量重编译且 `resume_section_ids=[]` 后继续；
- 为通过回归在 production compiler 中硬编码三个项目；
- 用删句、过滤 claim 或降低反向验证要求取得零 warning。

---

## 8. 实施返回要求

实现 Agent 完成后仅更新现有 `.agent/implementation.md`，至少包含：

- WP0–WP7 每包根因、改动文件与实际行为；
- 三篇 evaluation content ledger 的 before/after，不只报告 H2/字符数；
- not-discovered、discovered-blocked、rendered-low-quality 各自减少在哪里；
- field alignment 部分真值保留与 Verified 未升级的证据；
- paragraph plans、rendered slots、condition/polarity witnesses；
- formula routed/accepted/consumed/rendered 四阶段；
- Writer/Planner/Formalizer/callback 调用、semantic delta、commit/no-progress；
- representation repair 前后正文 digest/bytes 保留证据；
- focused/full static 命令、exit status、摘要、worktree state；
- 三个 fresh authoring replay 根与一个独立 callback=1 根（若已获准进入该里程碑）；
- 剩余问题明确归为 Research、alignment、argument planning、formalization、Writer、runtime model 或
  author review。

完成后返回 Codex 做只读验收。Codex 首先阅读 Candidate、`method_content_trace_v1.json`、formula
consumption、callback delta 和 mismatch sidecar，而不是先看测试数量或文本字节数。
