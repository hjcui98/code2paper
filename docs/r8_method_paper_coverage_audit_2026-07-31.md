# R8 四项目 Method 与原论文覆盖审计

> **2026-08-01 状态：**六项目 R8 已 6/6 accepted，详见
> [`r8_acceptance_status_2026-08-01.md`](r8_acceptance_status_2026-08-01.md)。本文的
> 质量差距结论仍然有效：R8 pass 不会把短正文自动提升为可投稿 Method。

- `as_of`: 2026-07-31
- `matrix_id`: `20260731T004226Z`
- `scope`: RAP、EBCAR、DyG、LinearRAG
- `purpose`: 对比当前生成 Method、仓库内 `paperdraft.md` 与可执行代码，定位信息
  丢失和错误授权发生在哪一层
- `important_limit`: `paperdraft.md` 只作为作者语义提示、覆盖清单和 mismatch
  对照，不是实现事实的正向授权源

## 1. 审计结论

当前问题不是单一的 Writer 输出过短，而是四层问题叠加：

1. 原论文和 author markers 中包含较完整的方法议程，但通用 Research sidecar
   没有编译出任何 packet/fact/claim；
2. 最终 Authoring 依赖具名 evidence profile，只得到每项目 8–9 条高度压缩的
   `implementation_behavior` claim；
3. 四项目最终投影均为 `safe_equations=0`、`safe_numeric_facts=0`，因此公式、
   默认值、张量形状、分支条件和训练/推理细节在调用 Writer 前就已丢失；
4. EBCAR、DyG、LinearRAG 随后没有调用 Rewrite Agent，而是
   `local_text_repair_node` 直接替换、删除、插入字符串，进一步产生重复和残句。

所以不能用“增大 Writer token”单独解决。正确顺序应是：

```text
原论文/作者意图生成覆盖义务（不授权事实）
  -> 解析真实入口、配置和分支
  -> 对每个义务搜索代码并编译细粒度 fact/claim/equation
  -> 形成 supported / partial / mismatch / external-evidence-required / gap
  -> Planner 按完整性矩阵组织
  -> Writer 生成正文
  -> 规则只验证并把问题返回 owning Agent
  -> Writer/Rewrite 重新生成
```

## 2. 量化对比

词数使用同一份落盘文件的英文单词统计；它只能说明信息密度差距，不是质量门本身。

| 项目 | 原 `paperdraft.md` | R8 `method_clean.md` | 比例 | V3 claims | claim kinds | safe equations / numerics |
|---|---:|---:|---:|---:|---|---:|
| RAP | 1,159 | 188 | 16% | 8 | 仅 implementation behavior | 0 / 0 |
| EBCAR | 203 | 228 | 112% | 9 | 仅 implementation behavior | 0 / 0 |
| DyG | 1,100 | 233 | 21% | 9 | 仅 implementation behavior | 0 / 0 |
| LinearRAG | 1,292 | 281 | 22% | 9 | 仅 implementation behavior | 0 / 0 |

EBCAR 是例外：仓库内原 Method 本来就很短，生成文本长度并不更短，但 repair 后
有重复、空主语和非法 qualifier。其问题主要是正文完整性和来源正确性，而不是
绝对词数。RAP、DyG、LinearRAG 则明显只保留了方法骨架。

另一个关键信号是：旧 grounding 对 DyG 已接受 4 个公式、13 个符号，对
LinearRAG 已接受 1 个公式、3 个符号；但 V3 Authoring 投影仍全部为
`safe_equations=0`。这不是 Writer 主动省略，而是跨 artifact 投影断链。

## 3. 逐项目对照

### 3.1 RAP

当前生成正文只有三段：15 维特征的概括、MLP 加载与评分、排序裁剪与输出。

原论文中缺失于生成正文、但代码已经存在的内容包括：

| 原论文内容 | 代码位置 | 当前丢失状态 |
|---|---|---|
| KNN 默认 `K=128`，IVF / brute force / cKDTree 三种实现 | `prune_percent.py:46-50`；`utils/gaussian_model.py:206-227` | claim 只写 “KNN statistics”，没有配置与分支 |
| SH 在 60 个 Fibonacci 方向上评估并取颜色标准差 | `utils/gaussian_model.py:235`；`utils/feature_utils.py:274-343` | 被压成 “SH anisotropy” |
| 15 个特征维度的精确组成 | `utils/gaussian_model.py:229-262` | 只保留一条合并 claim |
| 局部 z-score、全局 log z-score、1%/99% clipping 与 `[0,1]` 归一化 | `utils/feature_utils.py:345-408` | 公式、常数和逐维关系均未进入投影 |
| MLP 为 `15 -> 32 -> 32 -> 16 -> 2`、ReLU、Softmax、取第 0 类 | `utils/net_utils.py:5-29`；`prune_percent.py:18-20` | 只写“两 logits + Softmax”，隐藏层被删去 |
| `keep_num=int(N*keep_percent)`、mask 同步过滤六类 Gaussian 属性 | `prune_percent.py:22-36`；`utils/gaussian_model.py:266-272` | 主流程保留，但未解释输入输出和用户参数 |

原论文 Training 部分的 10 个场景、soft pruning、render/prune/entropy 三项损失和
15,000 iterations 在当前仓库中没有对应训练实现。它们不能为了“接近原论文长度”
直接写入实现正文，应标为 `external_evidence_required` 或代码缺失 gap。RAP 因此
需要同时展示两类结果：大量尚未编译的代码支持细节，以及确实不在仓库中的训练
内容。

### 3.2 EBCAR

生成正文基本覆盖了原短稿的结构增强和 shared/dedicated attention，并从代码增加
了 InfoNCE 与 rerank；但当前 clean text 已被规则 repair 写坏。

代码中仍有可写而未充分展开的内容：

- 正弦位置编码的计算、L2 normalization 和长度表；
- dedicated mask 如何让 passage 只看 query 与同文档 passages；
- scaled query-key、两个 attention 输出相加、residual 和 feed-forward 更新；
- exactly-one-positive 的 InfoNCE、temperature 和稳定的 `logsumexp`；
- inference 如何复用 contextual passage embedding 并降序返回文本与分数。

还存在一个需要框架语义验证的冲突：代码注释说 document-ID embedding 不更新，
并对 module 写入 `requires_grad=False`，但没有显式调用
`document_id_embedding.weight.requires_grad_(False)`；profile 直接授权为
“trainable”。Research Agent 应检查实际参数注册/optimizer 行为，输出明确
mismatch verdict，不能只靠注释或表面赋值二选一。

### 3.3 DyG

原论文的主要技术内容几乎都只剩标题级摘要。代码已包含但当前正文省略的内容有：

- 保留最近 `Lmax-1` 个历史交互、target 放在位置 0、edge 0、时间戳和 zero pad；
- node/edge/time/co-occurrence 四通道的构造、分别投影、stack 成 `4d_c`；
- 相邻时间差的 clip、归一化、inverse valid length 和第二 TimeEncoder；
- `dt_min=0.001`、`dt_max=0.1`、negative exponential `A`、softplus delta 和
  selective scan；
- bidirectional linear cross-attention 的 q/k/v、softmax 维度、residual 与
  LayerNorm；
- `top_k=64`、sequence softmax、top-k 后重新归一化、scatter 和 weighted sum；
- link-prediction MergeLayer、sigmoid 和 BCE 的训练入口。

更严重的是原论文、profile 与实际默认分支不完全一致：

- 原论文说 top-k gate 先使用 sigmoid；`DyGMamba.py:229-249` 实际直接对线性 logits
  做 sequence softmax 后 top-k；
- 原论文说 `B/C` 来自 timespan encoding；`MambaTimeDelta` 只有
  `time_mamba=True` 分支从 timespan 路径拆出 `B/C`，而
  `train_link_prediction.py:136-142` 创建的默认 `ssm_cfg` 没有启用该开关；
- 现有 `C-DYG-SSM-PARAMETERS` 却概括为 non-null `dts` 分支产生
  time-conditioned `dt, B, C`。

因此 DyG 不能仅扩写现有 claim。必须先把配置传播、true/false branch 和实际
entrypoint 解析进 BehaviorGraph，再决定哪些公式是 active implementation、
conditional capability、paper mismatch 或 gap。

### 3.4 LinearRAG

生成正文保留了 indexing、seed、稀疏传播、hybrid passage weight、PPR 和 dense
fallback 的骨架，但遗漏了：

- Parquet-backed、L2-normalized 的 passage/entity/sentence embedding stores；
- NER 排除 ORDINAL/CARDINAL、增量 JSON 和双向 entity-sentence lookup；
- igraph 中实际只有 passage/entity vertices，sentence 只是辅助映射；
- entity-passage occurrence-normalized edge、adjacent-passage edge 和 GraphML；
- BFS 与 vectorized 两条 Stage-1 路径及其逐步传播关系；
- passage 初始化的精确公式、tier/occurrence/attribute 条件；
- PPR damping、PRPACK、reset clamp 和 top-k；
- `qa()` 中 passage 拼接、LLM prompt、并行生成和答案抽取。

当前正文优先写了 “vectorized retrieval setup” 和 sparse propagation，但
`LinearRAGConfig.use_vectorized_retrieval=False`，CLI 也只有显式
`--use_vectorized_retrieval` 才启用该分支。也就是说，现有 profile 没有解析
默认 active path。

原论文自称 entity/sentence/passage heterogeneous graph，而实现的 igraph
vertices 只有 passage 与 entity；sentence 是外部 lookup/sparse structure。
生成文本对此反而较保守。未来完整性系统必须保留这种 mismatch，而不是要求
Writer 为追平原论文机械补回 “sentence graph node”。

## 4. 信息到底在哪里、在哪一层丢失

### 4.1 原始信息并未缺席

- 四个 `paperdraft.md` 都在 `repo_snapshot.json.included_files`；
- `author_markers.refined.json` 已捕获多数原论文 stage、building block、training
  objective 和 story order；
- retrieval summary 对真实源码 symbol 给出高覆盖；
- RAP、DyG、LinearRAG 的大量具体机制可在可执行代码中直接找到。

所以“仓库里没有信息”不是主要解释。

### 4.2 authority 分类存在旧链污染

旧 `evidence_raw.json` 把 RAP、EBCAR、LinearRAG 的部分 `paperdraft.md` 片段标为
`source` + `hard`。总体设计明确规定 Markdown/论文草稿只能是 `semantic_hint`。
即使 V3 最终 claim 使用了 profile 的代码 spans，这个旧链仍会污染 legacy
authoring/grounding，并使报告无法证明正向事实完全来自 executable evidence。

### 4.3 通用 Research 编译链没有产出

四项目通用 sidecar 都是 `0 packet / 0 claim`，must-cover 最终全靠 synthetic
gap 终结。Supervisor 虽然 search/read 了源码，却从未执行
`PROPOSE_PACKET`/`COMPILE_FACTS`。因此它没有把检索到的细节转成 Writer 可用的
typed data。

### 4.4 具名 profile 成为事实瓶颈

最终 8–9 条 claim 直接定义在：

- `evidence_profiles/rap_pruning.py`
- `evidence_profiles/ebcar_reranker.py`
- `evidence_profiles/dynamic_graph_mamba.py`
- `evidence_profiles/linear_graph_retrieval.py`

profile 既决定查哪些 span，也直接写 canonical claim text。它选择了少量“够过
R8 mainline”的概括句，没有按论文覆盖义务编译公式、配置、分支和完整 data flow。
Writer 输入的 canonical claims 本身约 166–198 词，最终 clean text 约 185–281
词，说明 Writer 实际主要在连接和轻微改写这些 claim，不可能凭空恢复已被上游
删掉的技术细节。

### 4.5 equation/numeric 投影断链

legacy grounding 已找到部分公式，但 V3 claim set 只有
`implementation_behavior`，没有 `EquationClaimV1`、配置/default claim 或
安全 numeric facts。Authoring projection 因而全部输出 0 equation / 0 numeric。
plan 的 `required_equation_ids` 也为空。

### 4.6 完整性门检查“无越界”，没有检查“应写内容”

四项目 `method_plan_quality.json` 都是 `score=100, issue_count=0,
report_only=true`。现有门能判断最终句是否落在 claim 边界，却没有维护
“原论文提出了哪些方法单元、代码支持了多少、为什么未写”的 coverage matrix；
也没有要求每个 supported 单元在 final Method 中出现。

### 4.7 deterministic repair 破坏了最后一层

`graph_text_trust_nodes.py:256-382` 会从 projection 取 fragment、机械追加
`under {qualifier}`、删除 atomic span、插入 missing planned claim，再直接写回
Method。三个项目的 trace 没有 `local_rewrite` 调用。

这不是 Agent 修复。规则代码只能产生 issue、阻塞和复验，不得写最终正文词句。
当前 accepted 结果因此只能作为失败回归样例，不能作为“Agent 已成功修复”的证据。

## 5. 应新增的合同

### 5.1 `ReferenceMethodObligationV1`

从 `paperdraft.md`、author markers 和作者输入提取“需要调查的内容”，字段至少包括：

```text
reference_unit_id
section_role
author_statement
claim_class
required_authority
search_queries
expected_relations
importance
```

它只能生成 research agenda，不得授权正向实现句。

### 5.2 `MethodCompletenessMatrixV1`

每个 reference unit 必须得到一个终态：

```text
supported
partially_supported
paper_code_mismatch
external_evidence_required
explicit_code_gap
out_of_scope
```

并绑定 code spans、relations、config resolution、compiled claims/equations 和最终
正文 span。没有被写入正文的 supported unit 必须有可审计原因。

### 5.3 多类 claim authority

至少区分：

- `ImplementationBehaviorClaim`: executable hard code；
- `ConfigurationClaim`: config 定义 + entrypoint 传播 + active/default resolution；
- `EquationClaim`: 从精确操作、常数和 data relation 编译；
- `AuthorRationaleClaim`: 作者明确声明，可用于动机/设计意图，但不得暗示已实现或
  已取得效果；
- `EmpiricalClaim`: 运行结果、日志、表格或实验 artifact；
- `CapabilityClaim`: 需要入口、配置、控制流和必要依赖共同支持。

这不是放宽代码证据门，而是避免把“实现、意图、公式、性能”全部塞进一种 claim。

### 5.4 `FinalTextAuthorshipLedgerV1`

最终 Markdown 的每个 lexical span 必须绑定：

```text
generation_trace_id
agent_role = writer | formalizer | editor | rewrite
response_span
applied_patch_id
```

Harness 可以解析、验证、选择和应用上述 Agent 输出的 patch，也可以添加 Markdown
分隔符/换行；不得产生、替换、删除或拼接正文 lexical token。任何 final lexical
span 若来源为 `deterministic_generated`，验收必须失败。

## 6. 对开发顺序的影响

原计划中 D1/D2 仍是前置条件，但 D5 不能等到 holdout 后才开始。应增加一个位于
D2 与 holdout 之间的“Method coverage compiler”批次：

1. 先用四个真实项目建立 `ReferenceMethodObligationV1` 和
   `MethodCompletenessMatrixV1` fixture；
2. 修通 generic packet/fact/claim/equation/config 编译；
3. 解析 entrypoint/default/conditional branch，先处理 DyG 与 LinearRAG 的真实
   mismatch；
4. Writer 按 supported information density 获得动态正文预算；
5. 禁用 deterministic prose mutation，所有内容问题调用 Writer/Rewrite；
6. 通过 authorship ledger、完整性矩阵和 final reverse validation 后，再做未知
   项目 holdout。

仅当“支持的细节被写出、冲突被保留、缺失被明确分类、最终词句都来自 LLM”同时
成立，R8 后的 Method 才能称为可供作者继续编辑的研究正文。

本审计发现的下一层写作问题、允许的叙事权衡、多权威边界、argument graph、
专用 Writer Agent 和 writing-time research callback 已展开为
[可投稿 Method Writer Agent 设计](publication_ready_method_writer_design_2026-07-31.md)。
