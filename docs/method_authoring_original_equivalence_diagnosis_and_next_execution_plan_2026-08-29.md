# Method Authoring 原文可推断性、公式丢失根因与下一阶段执行计划（2026-08-29）

> **as_of**：2026-08-29
> **状态**：下一阶段代码级执行方案；不是完成报告、发布授权或 Verified 放宽
> **范围**：EBCAR、DyG-Mamba、LinearRAG 的 Method Candidate 质量闭环
> **上位约束**：继续受 `method_intent_first_authoring_redesign_2026-08-22.md`、
> `publication_ready_method_writer_design_2026-07-31.md`、
> `post_r8_research_agent_execution_plan_2026-07-31.md` 和总体 Research Agent 设计约束。
> 本文承接 `code2paper_research_derived_authoring_optimization_execution_2026-08-28.md`，
> 不替代总体架构，不降低 Candidate/Verified、证据、公式、回调和最终完整性硬门。

## 0. 结论先行

这轮对照可以明确回答三个问题。

1. **作者意图加代码能不能推回接近原文的 Method？**
   - EBCAR：可以，且核心主线和四至五组公式几乎都能从代码直接或等价推导。
   - LinearRAG：可以推回完整两阶段逻辑和约九个代码等价公式，但必须把原文的完整
     Tri-Graph 改写为“实体—段落执行图 + 句子辅助映射”，不能照抄原文的句子图节点说法。
   - DyG-Mamba：可以写出完整的**当前实现 Method**，包括历史序列、四通道、时间控制、
     selective scan、共享编码器、交叉线性注意力、门控 top-k 和任务头；但原文中的
     Ebbinghaus 单调函数、B/C 谱范数约束、独立双编码器、均值池化和严格稳定性结论，
     不能从当前代码正向证明，其中数项还与执行路径矛盾。

2. **为什么当前 Agent 没写出来？**
   主因不是模型不知道 InfoNCE、attention、PPR 或 SSM，而是当前流水线在 Writer 之前
   已经丢掉了连续机制：三个项目的 `research_mechanism_dossiers_v1.json` 都是空 dossier，
   `derivation_records_v1.json` 都是零条；Formalizer 随后其实生成了 EBCAR 的结构增强、
   hybrid attention 和 InfoNCE 公式，但被 `formula_package_consumer_route_ambiguous` 全包拒绝。
   Writer 最终拿到的是几十个内部 slot、零 operation atom 和零可消费公式，因此退化成泛化叙述、
   代码名堆积和世界知识补洞。

3. **下一步抓哪个点？**
   先只闭环 EBCAR，不再同时扩三项目。把当前“几十个事实 slot → Writer”改成
   “6–8 个连贯 Method Unit → 代码等价公式 → 精确路由 → Writer → 独立 Binder”。
   EBCAR 达到 7/7 故事单元、至少 4 个代码支持公式、0 个未标注越权正向结论后，
   再迁移到 LinearRAG，最后处理纸码差异最大的 DyG-Mamba。

人工盲测证明的是**信息充分性与可达到上界**，不是模型质量基准：该基线是人工编写，
没有调用 Code2Paper Writer 或外部模型。模型与设计的剩余贡献必须通过同一个 8006 模型、
同一组选定代码片段的三臂消融来隔离。

## 1. 本次问题与证据边界

### 1.1 要回答的研究问题

- RQ1：原文 Method 的主要叙事和公式，哪些能由作者意图与仓库代码推断？
- RQ2：可推断内容为何没有进入当前 Candidate，是 Research、Formalizer、Writer、Binder、
  validator 的哪一段阻塞，还是模型本身能力不足？
- RQ3：为了先产出一个在形式和内容上接近原论文、逻辑完整且有公式的项目，下一轮代码
  应如何改、按什么顺序改、用什么退出条件验收？

### 1.2 使用的证据

- 原文 Method：
  - `/data1/users/cuihengjia/code2paper/paper_final/022_EBCAR - Embedding-Based Context-Aware Reranker.md`
  - `/data1/users/cuihengjia/code2paper/paper_final/029_DyG-Mamba Continuous State Space Modeling on Dynamic Graphs.md`
  - `/data1/users/cuihengjia/code2paper/paper_final/053_LinearRAG - Linear Graph Retrieval-Augmented Generation on Large-scale Corpora.md`
- 作者意图：EBCAR/LinearRAG 的 `paperyaml3` 与 DyG-Mamba 的 `paperyaml4` YAML。
- 研究代码：`/data1/users/cuihengjia/code2paper/code_final/` 下三个对应仓库。
- 人工盲测：`/tmp/code2paper-blind-baseline-20260828/`；它只看作者意图与代码。
- 当前真实回放：`artifacts/quality_closed_loop/2026-08-29/`；运行时为
  `http://127.0.0.1:8006/v1`、模型 `qwen38-27b-nvfp4`。
- 当前生产代码：`src/code2paper/agentic/`、`src/code2paper/llm/` 中 Research-derived
  authoring、Formalizer、Writer、Binder 与质量评估链。

原文只用于本次诊断和验收 oracle，不得进入生产提示词、项目 profile、generic production
logic 或候选生成输入。

### 1.3 可推断等级

| 等级 | 含义 | Candidate 许可 | Verified 许可 |
| --- | --- | --- | --- |
| A：直接代码支持 | 操作、条件、参数流和输出可在活动代码路径定位 | 可写 | 通过既有反向证据验证后可写 |
| B：代码等价推导 | 公式是循环、矩阵运算、排序、阈值或库调用的语义保持表达 | 可写，并记录推导 | 需要操作对应与条件验证 |
| C：意图规范/纸码差异 | 作者希望如此，但代码缺失、部分实现或相反 | 只能写成规范、待确认或差异 | 不可升级为实现事实 |
| D：效果或保证 | 性能、鲁棒性、复杂度、稳定保证、优越性 | 无实验/证明时不得正向写 | 必须有冻结实验、证明或外部权威 |

## 2. 原文与代码的可推断性

### 2.1 EBCAR：高可恢复，适合作为首个质量闭环

原文 Method 的主线是：候选检索与嵌入 → 相对文档/位置结构增强 → 查询与候选联合编码 →
全局注意力和同文档 masked attention → 固定查询锚点的 InfoNCE → 点积排序。该主线与代码
高度一致。

| 原文语义单元 | 意图 + 代码证据 | 等级 | 可生成内容 |
| --- | --- | --- | --- |
| 查询、候选段落及预计算嵌入 | dataset/vector-store 路径提供归一化查询与段落嵌入和 top-k 候选 | A | 问题定义、输入符号、候选集 |
| 相对文档 ID | dataset 重映射当前候选集内的文档 ID；模型使用文档 embedding 表 | A/B | 局部文档编号和 embedding lookup 公式 |
| 段落位置编码 | `ebcar_dedicated_attention_model.py:55-95` 生成 sin/cos 并 L2 归一化 | A/B | 位置编码和归一化公式 |
| 加性结构增强 | 同文件 `:120-133` 直接把文档和位置表示加到段落嵌入 | A | `\tilde p_i=p_i+e_{doc}(d_i)+e_{pos}(r_i)` |
| 联合序列 | `:135-184` 拼接查询与段落并送入 encoder | A | `X^{(0)}=[q;\tilde p_1;\ldots;\tilde p_k]` |
| 混合注意力 | `transformer_encoder_hybrid_attention.py:71-126` 有独立 full/masked MHA，结果相加后 residual/FFN | A/B | scaled dot-product、mask 定义和双分支融合 |
| InfoNCE | `ebcar_dedicated_attention_model.py:192-233` 有点积、温度、唯一正例断言和 logsumexp | A/B | 完整一正多负 InfoNCE |
| 推理重排 | 同文件 `:317-344` 计算分数并降序排序 | A | scoring 与 argsort/rank 公式 |
| 速度、跨段推理效果 | 仅代码结构和作者意图不足以证明 | D | 不进入实现事实；等待实验 |

需要保留两个实现边界：训练 mask 的行索引未像 `rerank` 一样加查询偏移；文档 embedding
模块上的 `requires_grad=False` 不等同于明确冻结权重。它们不阻止写出完整 Candidate，
但必须进入审阅 sidecar，不能被叙述成已经验证的设计效果。

**结论**：EBCAR 原文核心 Method 的形式、数据流和主要数学表达均可由意图与代码恢复；
当前 0/3 公式不是信息不可得。

### 2.2 LinearRAG：主线可恢复，Tri-Graph 必须按执行实现校正

原文主线是：构建 passage/sentence/entity 层次索引 → 查询实体种子 → 句子语义桥接和动态
剪枝 → 实体/段落 hybrid initialization → personalized PageRank → top-k 段落与 QA。

| 原文语义单元 | 意图 + 代码证据 | 等级 | 可生成内容 |
| --- | --- | --- | --- |
| NER 与向量索引 | `ner.py`、`embedding_store.py` 提供实体、句子、段落表示；ORDINAL/CARDINAL 是被跳过，不是保留 | A | 离线索引与实体规范化；必须保持 `continue` 的否定极性 |
| Tri-Graph | `LinearRAG.py:602-646` 的 igraph 只加入 entity/passage 节点；sentence 只存在辅助映射和稀疏矩阵 | A/C | 写成“实体—段落执行图 + 句子辅助关联”；原文完整三类图节点只能标为意图差异 |
| passage–entity 边 | 边权由实体出现次数除以段落实体总数 | A/B | occurrence-normalized edge 公式 |
| 查询实体种子 | `:533-553` 用归一化 embedding 点积和 `argmax` | A/B | 最近实体与初始激活分数 |
| 局部语义传播 | `:218-479` 用句子相似度、父实体激活、阈值和层级逐轮扩展 | A/B | 循环等价传播公式、阈值保留谓词 |
| hybrid passage score | `:481-513` 组合 dense score、实体出现、层级、`log(1+·)` 和 passage ratio | A/B | 实体 bonus 与 hybrid initialization 公式 |
| PPR | `:186-216` 重置实体/段落节点权重并调用 `personalized_pagerank` | A/B | PPR 算子级公式和按 passage score 排序 |
| 无实体回退 | `:84-129`、`:515-520` 回退到 dense ranking | A | 条件分支和 fallback |
| 线性扩展、质量/鲁棒效果 | 静态代码不足以证明 | D | 仅进入实验/证明待办 |

当前 Candidate 把 `ent.label_ == "ORDINAL" or ...: continue` 写成“只保留 ordinal/cardinal”，
这是典型的条件极性丢失，不是原文或代码缺失。原文公式 5 的矩阵传播可以用代码循环的
语义等价式表达，但不能把句子辅助映射升级成实际 PageRank 图节点。

**结论**：可以产出与原文逻辑接近、公式丰富的 LinearRAG Method；必须以当前执行图为事实
上限，并显式处理原文 Tri-Graph 与代码的差异。

### 2.3 DyG-Mamba：实现 Method 可完整恢复，原文理论重设计不可全部恢复

| 原文语义单元 | 意图 + 代码证据 | 等级 | 可生成内容 |
| --- | --- | --- | --- |
| 严格历史序列 | `DyGMamba.py:115-140,266-320` 提取一跳历史、截断最近事件、前置目标 token 和补零 | A | 输入序列、截断和 padding |
| 四通道编码 | `:61-83,143-215` 提供 node、edge、elapsed-time、co-occurrence 并投影拼接 | A | 四通道表示与对齐式 |
| 时间控制序列 | `:346-373` 从相邻时间差构造归一化 `dt`，再经过 cosine encoder/projection | A/B | 与实际实现一致的时间控制公式 |
| Mamba 状态参数 | `mamba_simple.py:438-550` 有 `A=-exp(A_log)`、内容相关 B/C、由 dts 生成 dt 和 selective scan | A/B | 负指数初始化、选择性扫描参数流与状态更新 |
| Ebbinghaus 单调函数 | 代码未实现原文带约束的单调 learnable timespan function | C | 只能作为作者意图/待实现，不可写成当前行为 |
| 稳定与谱范数 | 未发现 B/C spectral normalization；`A_log` 可训练，负初始化不等于训练后严格保证 | C/D | 初始化事实可写，稳定/Lipschitz/鲁棒保证不可写 |
| 源/目标组合 | `DyGMamba.py:217-264` 复用同一个 encoder，之后双向 cross-linear attention 和 gated top-k pooling | A/C | 写实际共享 encoder + cross attention + top-k；不能写独立 encoder + mean pooling |
| 任务适配 | 训练入口和 task heads 支持 link prediction/node classification 与 BCE/指标 | A | 任务头、训练目标和评估接口 |
| 线性复杂度与优越性 | 需要正式复杂度分析或运行证据 | D | 当前不正向声明 |

当前 Candidate 自行发明了
`\Delta t_i^{ts}=\Delta t_i\,dts_i/\Delta t_{nominal}`、A 重缩放和“长间隔必然更快遗忘”，
这些不是代码中的 `dt_generate_layer(dts)`。这说明模型在缺少连续代码包时会用熟悉的 SSM
知识补洞；世界知识可以帮助选择数学语言，但不能授权具体实现关系。

**结论**：DyG-Mamba 可以形成完整、论文式、带七组左右代码等价公式的实现 Method；若目标是
逐项复现原文理论 Method，则必须先改代码或提供额外证明，不能靠 Writer 推断越过差异。

## 3. 人工盲测与当前 Agent 的关键差异

### 3.1 覆盖结果

| 项目 | 人工盲测故事/公式 | 8006 当前故事/公式 | 直接结论 |
| --- | --- | --- | --- |
| EBCAR | `7/7`、`5/5` | `3/28`、`0/3` | 同一份意图与代码足以写公式，流水线未保留它们 |
| DyG-Mamba | `8/8`、`9/9 addressed`（7 code-derived） | `1/23`、`0/3` | 实现主线可写，当前输出被泛化叙述替代 |
| LinearRAG | `7/7`、`9/9` | `1/19`、`0/2` | 图检索公式可由代码推导，当前还出现 NER 极性反转 |

人工盲测的 paragraph/story 分母是按完整 Method 叙事定义的 7–8 个单元；当前 Architect
却把同一主线扩成 EBCAR 29 段、DyG 22 段、LinearRAG 17 段，并要求 46、59、24 个
paragraph target。粒度差异使模型把注意力花在内部原子和回执上，而不是论文逻辑。

### 3.2 人工盲测能证明什么，不能证明什么

它能证明：

- 输入中存在足够信息；
- 代码循环、矩阵运算、阈值、排序和库调用可以转换成读者公式；
- 纸码差异可以在不制造正向事实的前提下写成完整 Candidate；
- 当前生产结果远低于信息上限。

它不能证明：

- `qwen38-27b-nvfp4` 在相同输入下必然达到人工基线；
- 去掉全部门禁就能安全地产出；
- 人工 baseline 已经过 Code2Paper 的结构、证据和 publication gate。

因此，盲测应作为**信息充分性 oracle**，不能被当作模型 A/B 的对照臂。

## 4. 当前 Agent 的确定性丢失链

```text
作者意图 + 代码
      │
      ├─ 字段候选没有绑定 fact/span/equation，paragraph 也没有可用 facet seed
      ▼
空 Research dossier（0 operation atom / 0 fact / 0 equation / 0 excerpt）
      │
      ├─ Derivation compiler 没有输入，三个项目 derivation records 均为 0
      ▼
Formalizer 退到 author-intent lane，仍能生成论文公式
      │
      ├─ 同一 package 同时满足“无 consumer 的 facet obligation”与
      │  “有 consumer 的 paragraph derivation obligation”
      ▼
formula_package_consumer_route_ambiguous → 整包拒绝
      │
      ▼
Writer 收到几十个 slot ID、零连续机制、零可消费公式
      │
      ├─ 生成泛化段落、代码配置名、世界知识补洞，并可能改写精确 LaTeX
      ▼
Binder 无法找到有效 semantic/exact witness → structural_exit=false
```

### 4.1 P0：Research dossier 在真实项目中为空

三个最终产物的 dossier 条目都存在，但以下字段全为空：

- `facet_ids`
- `author_statements`
- `entry_symbol_ids`
- `ordered_operation_node_ids`
- `operation_atoms`
- `exact_excerpts`
- `fact_ids`
- `equation_ids`

`build_research_mechanism_dossiers()` 当前主要依赖 paragraph 的
`required_field_candidate_ids` 去取得 `bound_fact_ids`、`bound_span_ids` 和候选 symbol；当上游
field candidate 没有这些绑定时，后续 connected-subgraph 算法没有种子。现有 fallback 只在
有 implementation scope entry 时生效，最终三个真实运行没有形成可用机制链。

这不是 dossier 算法“连接得不够好”，而是**连接算法收到零起点仍被允许继续写作**。

### 4.2 P0：Derivation 产物为空，公式 evidence pack 没有核心方程

三个 `derivation_records_v1.json` 都是 `items: []`。同时，Formalizer trace 中所有 section 的
`core_equation_ids` 都为 0。早期 `equation_claims_v1.json` 虽有 11/12/3 条表达，但内容主要是
`x+y`、`x*y` 这种原子操作占位，不能表达 augmentation、InfoNCE、PPR 或 selective scan。

因此当前系统的“公式证据存在”多数只是 formula obligation 存在，不是机制方程已经从代码
编译出来。

### 4.3 P0：Formalizer 已写出正确公式，但 consumer 路由把它们丢掉

EBCAR 的 8006 `formalization_section_results_v1.json` 给出直接反证：

- MA-S3 两轮都提出结构增强与 hybrid attention 公式；两轮均因
  `formula_package_consumer_route_ambiguous` 拒绝。
- MA-S4 两轮都提出标准固定查询锚点 InfoNCE；两轮均因同一错误拒绝。
- MA-S5 第二轮点积包通过，但 Writer 改写后未保留 exact LaTeX，最终仍未形成有效消费。

`publication_method_writer.py::_bind_current_formula_route()` 的 fail-closed 行为本身正确：
一个包不能跨多个 paragraph consumer。真正的问题在更早的 planner：同一公式同时收到
无 consumer 的 facet obligations 和有 consumer 的 section derivation obligation，模型按提示
满足全部 obligation 后，`consumers=("", "paragraph:...")` 被判为多义。

修复方向不是放宽 guard，而是**在调用 Formalizer 前把每个 obligation 唯一路由到一个
paragraph，并按 consumer 分组调用**。

### 4.4 P0：Method 规划粒度远大于读者叙事粒度

当前计划把一个机制拆成几十个 operation/relationship slot，再把 slot 直接暴露为 Writer
ordered target。结果是：

- 同一节出现十几段重复的“first stage / second stage / relational link”；
- 一个简单 InfoNCE 被拆成多个段落与 target，却没有一个完整公式；
- Writer 可以声明 rendered slot IDs，但正文没有对应的语义锚点；
- Binder 的精确 witness 校验必然失败。

审计原子可以继续保留在 harness 内部，但 Writer 的调度单位应是 6–8 个读者可理解的
Method Unit，不应是 20–60 个底层事实槽。

### 4.5 P1：Writer 输入同时“太多 ID、太少语义”

`section_writer.py::_compact_authoring_packets_v2_for_llm()` 会向 Writer 提供 target 的
`semantic_atom`、operation atoms 和 formula block；但真实 dossier 为空后，只剩大量离散
target。Writer 看不到连续 raw-code slice、机制卡或等价推导，便出现：

- EBCAR 的“token embedding”“auxiliary output”“sole signal at every step”等无依据扩写；
- LinearRAG 对 `continue` 条件的极性反转；
- DyG-Mamba 的 nominal-step 重缩放、严格遗忘和不相关“review”叙述；
- 把系统缺证据状态写进正文，例如 “No repository-supported content was supplied”。

Candidate authority `passed` 只说明未命中审计词/泄漏规则，不代表技术内容正确或完整。

### 4.6 P1：公式从 Formalizer 到正文没有字节级存活

MA-S5 的点积 package 一度 accepted，Writer 最终把它渲染成
`s_i = q $cdot p_i = $sum...`。Binder 随后报告
`formula_body_missing_exact_latex`。公式内容不应再次交给 Writer 自由转写；Writer 只应决定
上下文与引用位置，最终公式块应直接来自已接受 Formalizer 输出。

### 4.7 P1：当前 Slice 5 evaluator 隐藏了拒包根因

三个 `*_evaluator.json` 都报告 `formula_route_ambiguous_packages: 0`，但 Formalizer call trace
中实际有 EBCAR 4 次、DyG-Mamba 6 次 consumer-route ambiguity。评估器只统计持久化后的
可见 package，拒绝包已不在结果集合中，因而把最重要的失败记成 0。

下一版必须从 `formalizer_call_traces[].guard_failures` 统计 proposed/rejected 原因，不能只看
最终 accepted package。

## 5. 设计问题与模型问题的判定

### 5.1 已能确定属于设计/编排的问题

- 可用代码链没有进入 dossier；
- derivation records 为零仍继续 Formalizer/Writer；
- formula obligations 在 planner 阶段没有唯一 consumer；
- Formalizer 正确输出被路由 guard 丢弃；
- Writer 调度粒度与论文段落粒度不一致；
- accepted formula 被 Writer 改写而失去 exact body；
- evaluator 不统计 rejected-package trace。

这些问题不依赖换模型，换更强模型最多掩盖一部分症状。

### 5.2 属于模型/提示可靠性的问题

- 在空机制包下用世界知识补出未实现的 SSM 数学关系；
- 把否定条件写成正向筛选；
- 把配置名和代码结构扩写成论文效果；
- 未稳定遵守 exact-LaTeX 复制和 paragraph witness 回执；
- 长而密集的结构化 schema 下容易重复标题、重复段落和生成元叙述。

这些需要紧凑输入、局部事务、明确的“不允许推断行为，只允许选择记号”提示和语义校验，
不应仅靠温度或换模型解决。

### 5.3 当前不能直接判定、必须消融的问题

人工盲测不是模型输出，所以不能用它断言“模型已经能写到同样水平”。需要在同一个 8006
模型上做三臂实验：

| 实验臂 | 输入 | 目的 |
| --- | --- | --- |
| A：Direct synthesis | 作者意图 + 人工选定的连续代码片段 + 7 个故事问题 | 测模型在无现有编排阻塞时的上限 |
| B：Method Unit | 新的结构化 Method Unit + 同一批代码证据 | 测 compact schema 是否损失语义 |
| C：Full pipeline | 完整 Research → Formalizer → Writer → Binder | 测系统新增的每一级损失 |

三臂使用相同模型、采样参数、代码切片和输出预算。原文只用于盲后评分。若 A/B 成功而 C
失败，剩余问题仍是编排；若 A 就持续失败，才有依据把该部分归因于模型容量或提示设计。

## 6. 世界知识的正确使用边界

AI 的世界知识应该作为**数学记号编译器和学术表达能力**，而不是行为事实来源。

| 允许 | 不允许 |
| --- | --- |
| 把 `matmul + softmax` 写成 scaled dot-product attention | 代码没有 scale 时自行添加 `1/\sqrt d` 并说已实现 |
| 把 `-pos + logsumexp(all)` 写成 InfoNCE 等价式 | 把 batch 组织、负例来源或唯一正例条件改掉 |
| 把循环累计写成 `\sum`、阈值写成 indicator | 发明代码不存在的传播边、节点类型或归一化 |
| 把 `argmax`、top-k、descending sort 写成数学算子 | 由常见实践推断性能、鲁棒性或复杂度 |
| 把 PPR 库调用写成算子级固定点关系 | 未检查库参数时声称具体收敛保证 |
| 选择 `q,p_i,A,B,C,\Delta t` 等常用符号 | 让符号选择反向授权新的实现关系 |

新增公式 lane 应区分：

1. `code_equivalent`：代码操作的语义保持数学表达；可进入 Candidate，经过逆验证后可申请 Verified。
2. `intent_specification`：作者希望的方法规范；只能进入 Candidate 的规范/待确认表达。
3. `conventional_notation`：模型只提供符号、标准算子名和等价排版，不增加事实权威。
4. `mismatch_pending`：意图与活动代码不一致；进入 sidecar 或明确审阅语句，不进入 Verified。

## 7. 目标流水线：以 Method Unit 为中心

### 7.1 新的最小中间表示

每个项目先形成 6–8 个 `MethodUnitV2`，而不是直接形成几十个 Writer slot。建议字段：

```yaml
method_unit_id: MU-3
reader_question: How are passage embeddings contextualized?
purpose: combine global candidate interaction with same-document interaction
inputs: [query embedding, enriched passage embeddings, relative document ids]
ordered_operations:
  - concatenate query and passages
  - compute full attention
  - compute same-document masked attention
  - add branches, residual, and feed-forward transform
outputs: [contextualized passage embeddings]
conditions: [mask allows query and same-document positions]
formula_roles: [attention, mask, branch fusion]
evidence_spans: [stable source span ids]
authority: code_equivalent
intent_code_status: partial_training_mask_offset
```

硬性要求：

- 每个 unit 必须至少有一个活动代码 span 或明确的 `intent_specification` 标记；
- mechanism unit 若 operation atom、span 和 author statement 同时为空，必须在 Research 阶段
  fail，不得继续让 Writer生成“缺证据正文”；
- 原子 fact/slot 仍保留在审计 sidecar，用于 reverse validation，但不直接定义段落数量；
- 一个 unit 可覆盖多个原子事实，一个段落最多消费一个主 unit 和一个紧邻辅助 unit。

### 7.2 Research：从“搜到符号”升级为“回答机制问题”

Research 接收 unit 的 reader question，输出一个有界、连续的代码 dossier：

- entrypoint → 核心函数 → 关键 helper 的最短活动调用链；
- 按执行顺序排列的 operation atoms；
- 关键条件、默认配置、形状和返回值；
- 原始代码 span 与 digest；
- 作者意图与代码的一致、部分、冲突状态；
- 可等价形式化的操作签名。

实现上仍由确定性 AST/behavior graph 提供边界和 provenance，但允许 Research 模型在这些
冻结片段内解释“这段循环在做什么”。模型解释不能直接授权 Verified；它要被后续操作
对应校验和 exact-span Binder 约束。

### 7.3 Formula：先定 consumer，再调用 Formalizer

规划器必须先完成以下不变量：

- 每个 formula obligation 恰好有一个 `consumer_paragraph_id`；
- facet、section、derivation 三类 obligation 若表达同一数学角色，先合并成一个 canonical
  obligation，不能让 Formalizer 同时满足一个有 consumer 和一个无 consumer 的副本；
- Formalizer 每次只接收一个 consumer 的 obligations；一个 package 不跨 paragraph；
- package 只声明实际满足的 canonical obligation IDs。

Formalizer 的输入优先级应为：

1. 代码 operation/equation evidence pack；
2. 作者意图中的 mathematical role；
3. conventional notation 许可；
4. 明确的纸码差异与假设。

验证从“是否已有 exact equation ID”扩展为“公式是否与代码 operation signature 等价”：

- operand 能映射到输入、中间值或输出；
- operator 与 `matmul/softmax/exp/logsumexp/sum/max/argmax/topk/threshold/PPR` 等操作一致；
- 条件与极性保持；
- 形状和归约维度不冲突；
- 不引入新超参数、保证或效果；
- `intent_specification` 与 `code_equivalent` 不得混淆。

### 7.4 Writer：写论文，不写审计状态

Writer 每次只处理一个 Method Unit/paragraph transaction，输入包含：

- reader question、purpose、inputs、ordered operations、outputs；
- 经过验证的条件和默认路径；
- 0–2 个已接受 formula blocks；
- 可写的纸码差异措辞；
- 前后 paragraph 的一句话衔接目标。

Writer 不再看到大批内部 slot IDs，不得输出 “no repository-supported content”、dossier、
obligation、witness、route、candidate authority 等审计词。若输入为空，返回 typed callback，
正文保持为空，由系统阻塞，不把错误报告伪装成论文段落。

### 7.5 公式块由 Formalizer 精确插入

Writer 只返回公式引用位置，例如 `[[FORMULA:pkg-id]]` 和相邻解释。harness 将已接受的
Formalizer `markdown_block` 原样替换该占位符。该替换是 Formalizer 输出的表示级拼装，
不创造新词句，符合最终正文词元来源边界。

这样可以消除 `$cdot`、丢反斜杠、公式被改写和 `formula_body_missing_exact_latex`。

### 7.6 Binder：冻结正文后做小规模语义绑定

Binder 每次只接收一个冻结段落和该段最多 3–6 个 reader-facing target：

- 返回正文中的 exact substring；
- 指明它绑定的 Method Unit、操作、条件和公式；
- harness 检查 substring 唯一性、条件极性和 source-span 对应；
- 缺失时只把“缺哪个 reader fact/condition/formula”返回 Writer，不重跑整节。

底层原子证据由 Method Unit 到 fact/span 的映射间接闭合，避免要求一句自然语言同时逐一
witness 八个内部 slot。

## 8. EBCAR 单项目闭环

### 8.1 目标 Method 结构

建议只规划七个读者单元：

1. Problem formulation and candidate inputs
2. Relative document and passage-position encoding
3. Structural embedding augmentation
4. Hybrid global/document-local Transformer encoding
5. Fixed-query contrastive training objective
6. Inference scoring and reranking
7. Implementation boundaries and evidence status（默认 sidecar，不污染主 Method）

主 Method 预计 6–8 个自然段，不再生成 29 个 paragraph transaction。

### 8.2 最小公式集

至少保留以下代码等价数学角色；符号可由 Formalizer 调整，但操作不能变化。

1. 位置编码及 L2 归一化：

   \[
   PE(r,2j)=\sin(r/10000^{2j/d}),\quad
   PE(r,2j+1)=\cos(r/10000^{2j/d}),\quad
   \bar{PE}(r)=PE(r)/\lVert PE(r)\rVert_2.
   \]

2. 结构增强与联合输入：

   \[
   \tilde p_i=p_i+E_{doc}(g(d_i))+\bar{PE}(r_i),\qquad
   X^{(0)}=[q;\tilde p_1;\ldots;\tilde p_k].
   \]

3. document-local mask 与混合注意力：

   \[
   M_{ij}=\begin{cases}
   0,& i=0\ \text{or}\ j=0\ \text{or}\ d_i=d_j,\\
   -\infty,&\text{otherwise},
   \end{cases}
   \qquad
   H=\operatorname{Attn}(X)+\operatorname{Attn}(X;M).
   \]

   训练路径的 query-row offset 差异必须绑定为审阅边界，不能把 clean mask 同时宣称为所有
   训练/推理路径的已验证事实。

4. 点积分数与 InfoNCE：

   \[
   s_i=\frac{q^{\top}\hat p_i}{\tau},\qquad
   \mathcal L=-s_{+}+\log\sum_j \exp(s_j).
   \]

5. 推理排序：

   \[
   \pi=\operatorname{argsort}_{i}(s_i;\text{descending}).
   \]

### 8.3 EBCAR 退出条件

一次 8006 fresh replay 只有同时满足以下条件才算 pilot 成功：

- 7/7 story units 被正文覆盖；
- 主 Method 为 6–10 个自然段，无重复标题和审计元叙述；
- 至少 4 个 `code_equivalent` formula package 被 proposed、routed、accepted、consumed 并
  exact-body validated；目标为上述 5 个数学角色；
- augmentation、full attention、same-document mask、InfoNCE、descending rerank 均有正文语义
  witness；
- 条件/极性错误为 0；
- 未标注 unsupported positive claim 为 0；
- Writer 不出现新的 repository symbol/config 名堆积，除非在 implementation-boundary sidecar；
- Candidate 可完整，但训练 mask/freeze 歧义继续阻止相应 Verified 事实，不得因 Candidate
  达标而放宽 Verified；
- publication quality 必须以结构、公式、内容和反向证据共同通过为准，不能再以 evaluator
  进程 exit 0 或 cleanliness `passed` 代替。

## 9. 代码级工作包

### WP0：冻结诊断 oracle 与同模型消融

**目标**：先量出模型上限和每一级系统损失，避免继续凭感觉改架构。

**修改/新增位置**：

- `src/code2paper/agentic/real_project_blind_eval.py`
- `scripts/` 下新增同模型 Method synthesis ablation 入口
- `tests/` 下新增 evaluator trace 统计测试

**动作**：

- 把人工盲测的 7/8/7 story unit 和公式角色固化成**评估清单**，不进入生成输入；
- 对 EBCAR 跑 A/B/C 三臂 8006 消融；
- evaluator 从 `formalizer_call_traces` 统计 proposed、guard-rejected、route-ambiguous、accepted、
  consumed、body-validated 六阶段漏斗；
- 记录同一输入与采样参数，原文在输出冻结后才用于语义评分。

**退出条件**：能明确回答 EBCAR 的失败从哪一臂开始，并且 rejected route 不再被统计为 0。

### WP1：Method Unit 与非空 dossier 硬门

**目标**：把 Research 输出从 atom inventory 变成连续机制包。

**主要文件**：

- `src/code2paper/agentic/method_architect.py`
- `src/code2paper/agentic/research_derived_authoring.py`
- `src/code2paper/agentic/method_argument_brief_planner.py`
- 必要时扩展 behavior graph/equation compiler 的 operand 保真字段

**动作**：

- 引入 `MethodUnitV2` 与 unit → paragraph 映射；
- EBCAR 首轮最多 8 个 unit，机制段不得超过 2 段；
- dossier seed 优先使用 bound span/fact，其次使用 unit 绑定的 implementation-scope entry；
- 不允许无界“抓全仓库”fallback；
- mechanism unit 的 dossier 为空时在 Research 阶段 typed fail；
- operation atom 保留真实 operand/result/guard，不再把方程退化为 `x+y`。

**退出条件**：EBCAR 每个核心 unit 都有 entry symbol、连续 operation chain、exact spans 和至少
一个可形式化 operation signature；`derivation_records_v1` 非空。

### WP2：consumer-first 公式规划与代码等价 Formalizer

**目标**：保留 fail-closed guard，同时消除当前确定性的 route ambiguity。

**主要文件**：

- `src/code2paper/agentic/formalization_agent.py`
- `src/code2paper/agentic/publication_method_writer.py`
- `src/code2paper/agentic/method_architect.py`

**动作**：

- 在 Formalizer 调用前 canonicalize 重复 obligations；
- 每个 obligation 强制一个 consumer；按 consumer 分组调用；
- 新增 `code_equivalent` / `conventional_notation` 许可与操作对应验证；
- route ambiguity 继续整包失败，禁止在 guard 里猜 consumer；
- repair prompt 只返回当前 package 的具体 guard failure。

**退出条件**：EBCAR augmentation、attention、InfoNCE、score/rank 包均有单一 consumer；
`formula_package_consumer_route_ambiguous=0` 是因为调用前已唯一化，不是评估器漏记。

### WP3：公式原样插入与 Writer 单元事务

**目标**：让 Writer 专注论文解释，不再复制/改写公式或处理数十个内部 ID。

**主要文件**：

- `src/code2paper/llm/section_writer.py`
- `src/code2paper/authoring/writer_skill.py`
- `src/code2paper/agentic/publication_method_writer.py`

**动作**：

- Writer-facing packet 改为 Method Unit semantic card；
- 内部 slot/fact IDs 留在 harness sidecar；
- Writer 用 formula placeholder，harness 原样插入 Formalizer block；
- 空 packet 返回 callback，不生成元叙述；
- 一次只写/修一个 paragraph transaction。

**退出条件**：accepted package 的 LaTeX 与 Candidate 字节一致；无 `$cdot`、重复标题、空证据
说明或“first stage”机械重复。

### WP4：Binder 与局部 repair

**目标**：在正文冻结后可靠地绑定少量 reader-facing semantic targets。

**主要文件**：

- `src/code2paper/agentic/publication_transaction_contract.py`
- `src/code2paper/agentic/publication_method_writer.py`
- `src/code2paper/agentic/callback_semantic_contract.py`

**动作**：

- Binder 按 Method Unit 返回 exact substring；
- 检查语义锚点、条件极性、公式 exact body；
- 只把 missing unit/condition/formula 返回 owning Writer 或 Formalizer；
- 禁止整节重写和 harness 生成新正文。

**退出条件**：EBCAR 每个 required Method Unit 至少一个有效 witness；0 个
`missing_exact_witness` 和 0 个 condition/polarity mismatch。

### WP5：EBCAR 8006 真实闭环

**动作**：

- fresh output root；预检 `/health`、`/v1/models`、`/metrics`；
- 固定 model identity、代码 digest、意图 digest、代码输入 digest；
- 执行 Candidate + Binder + reverse validation + publication quality；
- 与原文 oracle 和人工盲测做盲后语义对照；
- 若失败，只按漏斗中第一个失效阶段修复，不重复 unchanged run。

**退出条件**：满足 §8.3；只宣布 EBCAR pilot Candidate 质量达标，不宣布 D5、rollout、
default cutover 或 Verified 全通过。

### WP6：LinearRAG 泛化

**重点回归**：

- NER 的 `continue` 极性；
- actual graph 只有 entity/passage vertices；
- sentence mapping 的辅助角色；
- occurrence edge、seed argmax、threshold propagation、hybrid score、PPR、fallback 公式；
- 不声明完整 Tri-Graph 已按原文实现。

**退出条件**：7/7 story；至少 7 个 code-equivalent formula roles；0 极性错误；Tri-Graph
纸码差异有明确 sidecar，不污染 Verified。

### WP7：DyG-Mamba 泛化

**重点回归**：

- 严格历史、四通道、实际 dt control、`A=-exp(A_log)`、B/C 内容依赖、selective scan；
- 共享 encoder、cross-linear attention、gated top-k；
- 把 Ebbinghaus 单调性、谱范数、独立 encoder、mean pooling、严格稳定和线性复杂度放入
  mismatch/pending，不得由世界知识补成实现事实。

**退出条件**：8/8 implementation story；至少 7 个代码等价公式角色；0 条未标注的 intent-code
mismatch；稳定/鲁棒/复杂度正向声明仍由相应证据门控制。

## 10. 测试与验收矩阵

### 10.1 静态测试

- dossier 无 seed/无 operation 时 fail-closed；
- 一个 formula obligation 恰好一个 consumer；
- 同一 package 不得满足跨 consumer obligations；
- duplicate facet/section obligations 可 canonicalize，但不能静默丢义务；
- code-equivalent 公式保留 operand、operator、condition、shape；
- NER `continue` 条件的极性回归；
- Formalizer block 原样插入；
- Binder exact substring 与 semantic anchor；
- evaluator 统计 rejected traces；
- Candidate/Verified 分离与 Verified leakage 继续为零。

### 10.2 真实质量指标

按以下漏斗逐项报告，不能只给最终 `passed`：

```text
story planned → researched → unit-complete → written → bound → reverse-validated
formula required → proposed → uniquely routed → accepted → consumed → exact-body valid
```

每个阶段同时报告：数量、ID、失败原因、输入/输出 digest 和 owning agent。任何一个阶段为零时，
后续“通过”不得掩盖该损失。

### 10.3 原文相似性的判定

目标不是逐句或逐公式复制原文，而是满足：

- 相同或等价的主数据流顺序；
- 核心组件、输入、输出、条件和训练/推理闭环完整；
- 关键数学角色存在且与代码语义等价；
- 原文中代码未实现的理论、保证和效果不被冒充为实现事实；
- 读者无需查看代码即可理解方法如何运行。

评分以 semantic unit 为单位，不使用原文 n-gram、路径名或已知答案注入生产 logic。

## 11. 非目标与停止条件

本轮不做：

- 为追求原文相似度而把原文公式或项目特定答案写入 generic production 代码；
- 放宽 Verified evidence、reverse validation、formula、qualifier 或 final-integrity gate；
- 把 intent-only 理论包装成 world-knowledge-supported 实现事实；
- 同时对三个项目做大范围修复；
- 用重复采样等待偶然成功；
- 用 cleanliness、进程 exit 0、无 leakage 代替 publication quality。

若 EBCAR A 臂在紧凑代码输入下仍无法稳定生成 4 个核心公式，应暂停流水线重构，先处理
模型/提示选择；若 A/B 成功而 C 失败，则继续沿第一个漏斗断点修复，不更换模型逃避设计问题。

## 12. 最终交付物

完成本文工作包后应至少产生：

1. 一份 EBCAR 原文等价语义 oracle（仅评估侧）；
2. A/B/C 同模型消融及逐阶段损失报告；
3. 非空、连贯、可追溯的 Method Unit/dossier/derivation artifacts；
4. consumer 唯一的公式包和完整生命周期 trace；
5. 形式与内容接近原文、逻辑完整、带公式的 EBCAR Candidate；
6. 独立 Binder、反向证据验证和未放宽的 Verified 结果；
7. LinearRAG 与 DyG-Mamba 的泛化回归，分别保留其纸码差异边界。

这条路线的核心不是“让模型多写一点”，而是让系统把已经存在于作者意图与代码中的连续
机制交给模型，并保证模型生成的数学表达能被唯一路由、原样消费、逐段绑定和反向验证。

## 附录 A：本次冻结证据索引

- 运行说明与三项目总结果：
  [`artifacts/quality_closed_loop/2026-08-29/README.md`](../artifacts/quality_closed_loop/2026-08-29/README.md)
- EBCAR：
  [Candidate](../artifacts/quality_closed_loop/2026-08-29/ebcar/artifacts/06_authoring/publication_candidate_method.md)、
  [dossier](../artifacts/quality_closed_loop/2026-08-29/ebcar/artifacts/06_authoring/research_mechanism_dossiers_v1.json)、
  [Formalizer trace](../artifacts/quality_closed_loop/2026-08-29/ebcar/artifacts/06_authoring/formalization_section_results_v1.json)、
  [structural exit](../artifacts/quality_closed_loop/2026-08-29/ebcar/artifacts/06_authoring/authoring_structural_exit_v1.json)、
  [evaluator](../artifacts/quality_closed_loop/2026-08-29/ebcar_evaluator.json)
- DyG-Mamba：
  [Candidate](../artifacts/quality_closed_loop/2026-08-29/dyg/artifacts/06_authoring/publication_candidate_method.md)、
  [dossier](../artifacts/quality_closed_loop/2026-08-29/dyg/artifacts/06_authoring/research_mechanism_dossiers_v1.json)、
  [Formalizer trace](../artifacts/quality_closed_loop/2026-08-29/dyg/artifacts/06_authoring/formalization_section_results_v1.json)、
  [structural exit](../artifacts/quality_closed_loop/2026-08-29/dyg/artifacts/06_authoring/authoring_structural_exit_v1.json)、
  [evaluator](../artifacts/quality_closed_loop/2026-08-29/dyg_evaluator.json)
- LinearRAG：
  [Candidate](../artifacts/quality_closed_loop/2026-08-29/linearrag/artifacts/06_authoring/publication_candidate_method.md)、
  [dossier](../artifacts/quality_closed_loop/2026-08-29/linearrag/artifacts/06_authoring/research_mechanism_dossiers_v1.json)、
  [Formalizer trace](../artifacts/quality_closed_loop/2026-08-29/linearrag/artifacts/06_authoring/formalization_section_results_v1.json)、
  [structural exit](../artifacts/quality_closed_loop/2026-08-29/linearrag/artifacts/06_authoring/authoring_structural_exit_v1.json)、
  [evaluator](../artifacts/quality_closed_loop/2026-08-29/linearrag_evaluator.json)
- 人工盲测：`/tmp/code2paper-blind-baseline-20260828/`。该目录不是长期验收证据，本文只使用
  其冻结结果做信息充分性对照；正式回归应把 oracle schema 和同模型消融产物写入新的
  task-specific fresh root，并记录代码与输入 digest。
