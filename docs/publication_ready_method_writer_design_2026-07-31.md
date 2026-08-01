# Code2Paper 可投稿 Method Writer Agent 设计

- `as_of`: 2026-07-31
- `status`: 规范性设计；待按 R8 后执行计划实现
- `scope`: 从已研究的代码仓库、作者意图、论文草稿和其他冻结证据生成可直接进入
  论文编辑流程的 Method
- `trigger`: RAP、DyG、LinearRAG 的 R8 Method 仅约为原稿的 16%–22%，四项目
  最终都只有 8–9 条压缩 implementation claims，且
  `safe_equations=0`、`safe_numeric_facts=0`
- `related_evidence`:
  [R8 四项目 Method 与原论文覆盖审计](r8_method_paper_coverage_audit_2026-07-31.md)

## 1. 决策

当前系统把“事实原子化”误用成了“写作原子化”：一条 atomic claim 常被写成一条
句子，8–9 条 claim 最终只形成 8–9 个事实句。Atomic claim 应是验证单元，不是
篇幅配额、段落模板或论文论证单元。

下一阶段采用以下设计：

1. **不降低真实性门。** 不能为了写长而复制未验证原稿、虚构性能、默认配置、
   新颖性、因果效果或理论保证。
2. **不再把代码当作所有句子的唯一权威。** 代码是实现行为的首要权威；作者确认、
   实验 artifact、形式化推导和外部文献分别拥有不同的授权范围。
3. **代码中没找到不等于内容为假。** 正确终态可能是
   `unverified_by_repository`、`author_confirmation_required`、
   `external_evidence_required` 或 `paper_code_mismatch`，不能一律降成
   `explicit_code_gap` 后从故事中删除。
4. **把事实验证层与论文论证层分开。** 多条 atomic facts/claims 先组成
   `MethodArgumentUnit`；Writer 再围绕问题、直觉、定义、公式、机制、实现、
   条件和输出形成完整小节。
5. **建立真正的 Writer 工作流。** Method Architect、Section Writer、
   Formalization Agent、Cross-section Editor 和 Rewrite Agent 分工协作；最终正文
   每个 lexical span 仍必须来自 Writer/Formalizer/Editor/Rewrite 的 LLM 响应。
6. **写作时允许返回研究。** Writer 发现某个小节缺输入、关系、公式、默认值、
   rationale 或实验依据时，生成 typed research request，只重开对应义务，拿到
   新证据后继续该小节。
7. **质量不以字数判定。** 词数只作压缩异常信号；正式门检查支持内容召回、
   论证动作完整性、技术严密性、复现细节、全局连贯性和人工可编辑性。

目标不是生成“安全但贫乏的代码摘要”，而是生成**事实边界清楚、论证完整、作者
可以直接继续润色和投稿的 Method candidate**。

## 2. 当前为什么只能生成短摘要

### 2.1 输入在 Writer 前已被压扁

当前四项目的 authoring projection 只有 8–9 条宽粒度
`implementation_behavior` claim，没有 equation、numeric/config、rationale、
objective、formal object 或 empirical claim。Writer 无法从不存在的输入中恢复
15 维特征组成、归一化公式、active branch、张量关系或训练目标。

### 2.2 Planner 只有标题，没有论证结构

当前 `authoring/writing/section_planner.py` 只返回 Overview、Framework、
Components、Flow/Objective 和 Notes 等保守标题。它没有说明一个小节必须回答：

- 要解决什么局部问题；
- 为什么采用该机制；
- 输入、状态和符号如何定义；
- 算法或数据流如何变换；
- 公式如何从操作得到；
- 默认路径、条件分支和边界条件是什么；
- 输出如何被下游使用；
- 哪些结论只是直觉，哪些是实现或实验事实。

因此“规划完成”实际只代表有标题，不代表论文论证闭环。

### 2.3 Writer prompt 只强调限制，没有写作能力合同

当前 `llm/section_writer.py` 的默认提示主要要求只使用 projection、不要虚构、
每次只写一个 focused section。它没有 venue 级写作要求、rhetorical move、
符号表、论证图、段落目标、跨节接口、读者假设或 research callback。

### 2.4 输出协议仍把连续运行看得比正文完整更重要

当前 section writer 在累计预算耗尽、调用失败或空响应时填入 deterministic
placeholder，并继续拼接“连续 Method”。这可以保持流程不崩溃，但不能形成可投稿
正文，也违反“最终正文 lexical token 必须来自 LLM”的 authorship 原则。
此类状态应保存已完成小节并进入 `blocked/incomplete`，不能伪装成完整 draft。

### 2.5 事实安全与写作质量用了同一种粒度

Atomic claims 对逐句反向验证有用，但一篇论文需要更高层的论证单元。同一个支持
事实可以合法支撑多种不新增事实负载的表达：

- 先给机制总览，再给细节；
- 定义符号并解释输入输出；
- 用直觉解释为什么该变换适合当前目标；
- 把多个操作重写成公式或伪代码；
- 说明默认路径与可选路径的关系；
- 给出边界条件和实现后果。

如果每次扩写都被当作“新增 implementation claim”，Writer 只能退化为 claim
复述器。

## 3. 两个正交的质量轴

系统必须分别报告：

### 3.1 Epistemic safety

回答“正文中的可核查事实由什么授权”：

- 实现行为是否来自正确 snapshot 和 active path；
- 数值、公式、配置、实验结果是否有相应 authority；
- 作者意图是否被误写成已实现或已验证效果；
- 外部文献是否被正确引用；
- 每个 factual span 是否能回溯。

### 3.2 Publication utility

回答“这是否是一段可直接编辑进论文的 Method”：

- 是否覆盖作者认为重要且已经得到支持的方法单元；
- 是否形成从问题到机制到输出的完整论证；
- 是否定义符号、公式、条件、目标和接口；
- 是否技术准确、清晰、连贯、少重复；
- 是否给出足够的复现信息；
- 是否符合 venue/page budget，而不是机械追求长短。

`unsupported=0` 只证明第一个轴的一部分。只有两个轴都通过，状态才可以是
`publication_ready`。

## 4. 多权威写作合同

### 4.1 权威通道

| authority lane | 可授权内容 | 不可授权内容 |
|---|---|---|
| `executable_hard` | 实际代码行为、控制/数据流、接口、已解析 active branch | 作者动机、理论保证、性能 |
| `configuration_resolved` | 默认值、入口覆盖、actual/default/conditional 状态 | 未传播到真实入口的表面配置 |
| `author_attested` | 作者明确确认的设计动机、术语、预期用途、仓库外方法事实 | 未经作者确认的原稿句子、实验效果 |
| `formal_derivation` | 从已声明定义、前提和支持操作推导出的公式、命题、复杂度 | 缺前提的“证明”、经验性能 |
| `empirical_artifact` | 冻结日志、表格、实验输出所支持的结果 | 未运行的预期收益 |
| `external_literature` | 引用文献中的背景、已知理论和对比事实 | 本仓库已实现某行为 |
| `expository_bridge` | 不携带新可核查事实的解释、过渡、组织和直觉 | 偷带实现、性能、新颖性或因果 claim |

`semantic_hint` 仍只能发起调查，不能直接升级为以上任一正向权威。论文草稿中的
方法事实如无法在代码中找到，可以通过作者确认升级为 `author_attested`，或通过
实验/外部资料升级到相应通道；不能静默升级。

### 4.2 “代码缺失”的精确终态

对一个 reference unit，Research Agent 必须区分：

```text
supported_by_repository
partially_supported_by_repository
paper_code_mismatch
unverified_by_repository
author_confirmation_required
external_evidence_required
formalization_required
explicit_code_gap
out_of_scope
```

其中 `explicit_code_gap` 只表示在声明的 snapshot、入口和搜索范围内，没有找到
满足该**实现义务**的证据。它不能推导出“作者的方法描述为假”，更不能自动删除
相关研究问题、动机或作者待确认内容。

### 4.3 两种可见交付状态

系统同时保留两个输出：

1. `repository_verified_method.md`：只含已经解析的多权威事实，允许不完整；
2. `publication_candidate_method.md`：允许纳入已经明确确认的
   `author_attested` 内容，以及合格的形式化/文献/实验内容。

未确认内容可以由 Agent 生成到独立的 `author_review_candidates.json`，展示拟写
正文、缺失依据和确认问题，但不能静默进入 `publication_candidate_method.md`。
作者确认后只重写受影响小节。这样既不会因为代码缺失把论文故事删空，也不会为了
完整性把猜测伪装成事实。

## 5. 从 atomic claim 到论文小节

### 5.1 `MethodArgumentUnitV1`

一个论文论证单元可以引用多条 atomic claims，也可以包含多个不新增事实负载的
expository moves：

```text
argument_unit_id
section_role
research_question
design_objective
claim_ids
equation_ids
configuration_ids
author_rationale_ids
empirical_ids
literature_ids
behavior_relation_ids
allowed_expository_moves
unresolved_inputs
```

Atomic claim 保持最小、可验证；`MethodArgumentUnitV1` 负责回答“这些事实共同
说明一个什么方法点”。它是证据层与写作层之间缺失的中间表示。

### 5.2 `SectionArgumentGraphV1`

每个 Method 小节按需要选择下列 rhetorical moves，不要求所有小节机械齐全：

```text
problem_or_local_context
design_objective
mechanism_overview
intuition_or_rationale
formal_objects_and_notation
equation_or_derivation
algorithm_or_data_flow
implementation_realization
configuration_and_branches
training_objective
inference_and_output
complexity_or_boundary_conditions
limitations_or_mismatch
transition_to_next_section
```

每个 move 记录依赖的 argument units、预计段落数、目标信息量和允许的 authority。
这让“一条核心 claim”可以发展成完整小节，但每个新增 factual span 仍有明确来源。

### 5.3 Writer 的叙事自由

Writer 可以：

- 重排已支持信息，使故事从问题和直觉进入形式化，再落到实现；
- 定义不改变事实的局部符号；
- 用多个句子解释一个复杂操作的输入、过程和输出；
- 从已支持的精确操作与前提生成等价公式、伪代码和 proof sketch；
- 解释 active/default/conditional 分支的关系；
- 写不携带新事实的过渡、总结和直觉；
- 明确区分设计目标、实现机制、经验观察和理论保证。

Writer 不可以：

- 把“这样设计可能有助于”改写成“实验表明提升”；
- 从函数名、注释或论文草稿猜测真实 active behavior；
- 把 conditional capability 写成默认路径；
- 声称新颖性、最优性、复杂度或收敛性而没有相应 authority；
- 用冗长同义改写制造篇幅；
- 在正文中暴露内部 evidence ID、机械 qualifier 或验证器语言。

## 6. 专用 Writer Agent 架构

### 6.1 Method Architect Agent

输入：

- author intent 和 reference method agenda；
- completeness matrix；
- authorized multi-lane facts/claims；
- venue/page budget；
- terminology table 和全局 story order。

输出：

- `MethodSectionPlanV2`；
- `SectionArgumentGraphV1`；
- 每节读者问题、rhetorical moves、依赖和动态深度预算；
- 未决信息列表，不输出最终正文。

Architect 不以“一条 claim 一个段落”规划，而以“一个研究问题/方法点一个论证单元”
规划。

### 6.2 Section Research Writer Agent

一次只写一个小节，但能读取：

- 当前小节 argument graph；
- 允许使用的 claims/equations/config/rationale；
- 前文摘要、术语表和下游接口；
- 该小节的已知 mismatch/gap；
- writer skill 与 venue quality rubric。

输出采用 content-first 协议：

```text
section_markdown
used_argument_unit_ids
used_claim_ids
used_equation_ids
new_research_requests
self_identified_risks
```

正文先生成，ID 和结构化绑定后生成；Harness 可以提取和组装容器，但不得改正文。

### 6.3 Formalization Agent

负责：

- 从 exact operations、shape、常数和 relations 建立符号表；
- 生成与代码等价的公式或伪代码；
- 检查维度、索引、归一化域和 branch guard；
- 对作者提供的理论命题建立 `ProofObligationV1`；
- 生成 proof sketch 时标注前提、结论和未证明步骤。

代码可以支撑算法等价公式，但不能单独证明统计性质、收敛性或泛化结论。后者必须
有完整前提和独立形式化/文献/作者确认。

### 6.4 Cross-section Editor Agent

在各节局部通过后执行一次全局编辑：

- 统一符号和术语；
- 修复跨节指代和前后顺序；
- 删除真正重复的解释，但不能删掉唯一支持内容；
- 调整段落节奏和过渡；
- 保持所有 lexical span 的 generation provenance；
- 产生 section-scoped patch，不绕过原事实门。

### 6.5 Rewrite Agent

只处理 validator 返回的精确问题。规则层不能修改正文；Rewrite 输出完整替换 span
和 provenance，然后重新跑原 schema、evidence、coverage、coherence 与 authorship
门。

## 7. 写作中返回研究

### 7.1 `WritingResearchRequestV1`

Writer 或 Formalization Agent 可在写作中发出：

```text
request_id
section_id
argument_unit_id
missing_rhetorical_move
exact_question
required_authority_lane
candidate_symbols_or_terms
current_known_facts
why_needed_for_reader
priority
```

例子：

- “RAP 的局部与全局归一化先后关系和精确常数是什么？”
- “DyG 默认 entrypoint 是否启用 time-conditioned B/C？”
- “LinearRAG 的 sentence 是 graph vertex 还是辅助 lookup？”
- “作者是否把该机制作为设计动机，还是有实验消融支持？”

### 7.2 路由

```text
Section Writer
  -> WritingResearchRequest
  -> Research Router
       executable/config -> repository tools
       author rationale  -> author confirmation queue
       empirical         -> experiment artifact tools
       literature        -> external search/read
       formalization     -> Formalization Agent
  -> updated facts/completeness/argument graph
  -> resume affected section only
```

检索与推理必须交错：Writer 已经写到哪一步会改变下一次需要查什么。不能在最前面
盲目塞入大量源码或网页，也不能每次缺信息就重跑整个 repository intake。

### 7.3 停止规则

- 高优先级 move 缺关键事实时，该小节进入 `incomplete`，不能以短摘要冒充完成；
- 多次无增益搜索后转成精确 review task，不无限循环；
- 低优先级细节可在 page budget 下延后，但必须在 completeness matrix 留下理由；
- Research 返回后只使依赖该请求的 argument unit 和 section 失效。

## 8. Writer skill 与 prompt 合同

目标实现应增加版本化的 repo-local writer skill/prompt，而不是把全部要求拼在一个
巨大 JSON schema 中。建议位置：

```text
src/code2paper/authoring/writer_skill.py
src/code2paper/agents/config/prompts/publication_method_architect.txt
src/code2paper/agents/config/prompts/publication_method_section_writer.txt
src/code2paper/agents/config/prompts/publication_method_formalizer.txt
src/code2paper/agents/config/prompts/publication_method_editor.txt
```

`PublicationMethodWriterSkillV1` 至少包含：

- audience/venue 目标；
- Method 的典型 rhetorical moves；
- 多权威边界与禁止推断；
- 公式、符号、伪代码和 proof sketch 规则；
- input → transformation → condition → output 的解释要求；
- active/default/conditional branch 写法；
- 不在正文暴露 validator 术语的要求；
- research callback 协议；
- 跨节术语和引用规范；
- “先写内容、后绑定 ID”的输出策略；
- 正反例和项目无关的 few-shot 示例。

Prompt 必须告诉 Writer“如何写好”，而不只是“什么不能写”。模型输出格式错误由
Harness 做表示级恢复；内容、引用、论证或证据错误仍返回相应 Agent。

## 9. 动态深度与预算

不设“每节至少 N 词”或“每条 claim 扩写 N 句”。Architect 根据以下因素分配：

```text
supported argument units
formalization load
branch/config complexity
reader prerequisite distance
venue/page budget
section novelty/importance
cross-section dependencies
```

每个段落都应完成一个可识别的 rhetorical move。以下情况视为无效扩写：

- 反复改写同一 canonical claim；
- 增加没有定义的新术语；
- 只写形容词和价值判断；
- 把实现细节拆成大量无信息短句；
- 用代码符号列表代替方法解释。

当某节因 `finish_reason=length` 截断时，不丢弃整份响应，也不重新从头生成：

1. 提取已经闭合的段落和未完成 move；
2. 保存已验证内容；
3. 以未完成 move 和最后上下文继续；
4. 最后由 Editor 做连接；
5. 累计安全预算按实际 argument units 动态计算，并设置全局防失控上限。

累计预算耗尽时返回 `incomplete_sections`，不得插入 deterministic prose
placeholder 后声称 Method 完整。

## 10. 质量与验收

### 10.1 事实安全门

- 每个 factual span 绑定 authority lane 和 source artifact；
- implementation/default/equation/empirical 各用正确 validator；
- author-attested 内容绑定明确确认记录；
- expository bridge 不携带新的可核查事实；
- final lexical spans 全部来自 Writer/Formalizer/Editor/Rewrite generation；
- unsupported positive claim 为 0。

### 10.2 内容完整性门

- 所有高优先级 supported reference units 已进入 argument graph；
- 每个未写 supported unit 有 page-budget 或组织理由；
- overview、formal objects、mechanism、configuration、objective、inference/output
  按项目实际需要覆盖；
- 公式/numeric/config 不再因 artifact 投影断链统一为 0；
- paper-code mismatch 保留到作者 review sidecar。

### 10.3 论文写作门

- 每个核心小节形成问题/目标 → 机制 → 技术细节 → 输出/接口的闭环；
- 术语、符号、时态和 branch 叙述全局一致；
- 无重复、残句、空主语和机械 qualifier；
- 核心架构和过程足以复现，关键假设明确；
- proof sketch 给出直觉且不冒充完整证明；
- 正文不含内部证据 ID、验证器错误消息或 gap bookkeeping；
- 在完整 Writer 里程碑结束时做一次固定盲评，判断正文可直接进入论文编辑，而不是
  代码审计报告；不在每个开发批次重复组织人工验收。

### 10.4 指标

分开报告，不合成一个可被投机的总分：

```text
support precision
supported-unit recall
argument-move coverage
equation/config/numeric coverage
reproducibility detail coverage
paper-code mismatch preservation
terminology and notation consistency
duplicate information rate
expert pairwise preference
author edit distance / acceptance rate
```

原稿词数比例只作诊断。生成文本可以比原稿短或长，但不能只保留 16%–22% 的方法
骨架，也不能靠空泛扩写追平词数。

## 11. 实现映射

### 11.1 新增合同与模块

```text
src/code2paper/agentic/method_argument_models.py
  MethodArgumentUnitV1
  SectionArgumentGraphV1
  WritingResearchRequestV1
  ProofObligationV1

src/code2paper/agentic/method_architect.py
src/code2paper/agentic/writer_research_router.py
src/code2paper/agentic/formalization_agent.py
src/code2paper/agentic/cross_section_editor.py
src/code2paper/agentic/final_text_authorship.py
src/code2paper/authoring/writer_skill.py
```

### 11.2 修改当前模块

- `agentic/authoring_projection.py`：从 claim list 升级为多权威 argument input；
- `agentic/authoring_plan_v3.py`：生成 section argument graph 和深度预算；
- `authoring/writing/section_planner.py`：替换固定标题列表；
- `llm/section_writer.py`：实现 content-first、research callback、section resume 和
  incomplete 状态；删除 deterministic final placeholder；
- `authoring/writing/method_writer.py`：projection-only deterministic draft 仅可保留
  为 legacy/debug artifact，不能进入 agentic trust path；
- `agentic/graph_text_trust_nodes.py`：规则只发 issue；
- `agentic/text_repair_supervisor.py`：接入 Writer/Editor/Rewrite typed patch；
- `agentic/r8_acceptance.py`：新增多权威、argument coverage、writer provenance 和
  publication utility criterion。

### 11.3 测试与验收组织

不为每个 contract、Agent、router、validator 分别新建测试文件。优先在现有测试中
增加案例；Writer 子系统新增一个纵向集成测试文件即可，覆盖 argument graph、
research callback、formalization、section writing、editor/rewriter 和 authorship
的主链，以及当前真实产物中已经发生的短稿、公式断链、重复、残句和 deterministic
prose mutation。

RAP、EBCAR、DyG、LinearRAG 的冻结 artifact 和一个真正未知的 holdout 保留为完整
里程碑回归，但不在 W0–W5 每一步重复运行。每个小提交只运行直接受影响的现有测试；
W6 集中运行一次完整静态回归、四项目真实重跑和一次盲评，W7 再运行 holdout。
禁止为某个项目写专用 prompt、claim 文本或 section 模板。

## 12. 开发顺序

1. **W0：冻结短正文失败样例。** 把 8–9 claims、0 equation/numeric、
   deterministic repair 和当前短稿变成负回归。
2. **W1：建立多权威与 argument contracts。** 不改 Writer，先证明 claim 不再是
   写作段落单位。
3. **W2：实现 Method Architect。** 对 RAP 和 DyG 产出可人工审阅的
   `SectionArgumentGraphV1`，不生成正文。
4. **W3：实现 Section Writer + research callback。** 先完成 RAP 一个小节的
   研究—写作—复验闭环。
5. **W4：接通 Formalization。** 恢复 RAP normalization、DyG selective scan、
   LinearRAG propagation/PPR 等代码支持公式与配置。
6. **W5：实现全局 Editor 与真实 Rewrite。** 所有正文 token 保持 LLM provenance。
7. **W6：四项目真实重跑与一次集中盲评。** 先验证安全与完整性，再评价论文可用性；
   W0–W5 不重复组织 committee 或人工验收。
8. **W7：holdout。** 协议冻结后测试未知仓库，不允许项目特权。

W1–W4 应与 generic evidence compiler 的 D1/D2/D2.5 同步推进；没有真实
packet/fact/equation 输入时，单独调 prompt 不可能解决根因。

## 13. 研究依据

- NeurIPS Paper Checklist 要求主张与贡献及理论/实验结果一致，明确假设、提供
  完整证明，并鼓励主文 proof sketch 解释直觉；也要求架构和训练细节支持复现：
  <https://neurips.cc/public/guides/PaperChecklist>
- ICLR Author Guide 同样强调可复现性、假设和证明，说明“写得像论文”不只是文风，
  还包括可核查的技术完整性：
  <https://iclr.cc/Conferences/2025/AuthorGuide>
- STORM 把长篇、带引用写作拆成写前研究、不同视角的问题生成和大纲组织，支持
  “先研究和规划，再按章节写”的架构：
  <https://arxiv.org/abs/2402.14207>
- IRCoT 表明检索与推理交错比一次性检索更合适，因为下一步检索需求取决于已经
  推导出的内容，直接支持 writing-time research callback：
  <https://arxiv.org/abs/2212.10509>
- LongWriter 的 AgentWrite 先制作带段落目标的详细计划，再逐段生成，说明长上下文
  本身不会自动产生长而连贯的输出，任务分解和规划才是关键：
  <https://arxiv.org/abs/2408.07055>
- ALCE 分开评价 citation recall、precision 和每条陈述的支持，并指出检索质量及
  完整 passage 检查的重要性；它支持把“支持精度”和“内容召回”分开报告：
  <https://arxiv.org/abs/2305.14627>
- RARR 的 research-and-revise 流程在保留原意的同时为未支持内容检索并局部修改，
  支持规则发 issue、Agent 研究和重写、再复验的修复方式：
  <https://arxiv.org/abs/2210.08726>
- FActScore 证明长文本需要原子事实级验证；本设计保留 atomic facts 做验证，但不
  再把 atomicity 当作写作结构：
  <https://arxiv.org/abs/2305.14251>
- OpenScholar 展示了检索增强的科学综合能力，同时明确人类作者仍需负责，支持
  “自主研究写作 + 作者确认”，而不是把未验证内容自动发布：
  <https://doi.org/10.1038/s41586-025-10072-4>

这些工作提供的是设计依据，不是直接可复制的完整 Code-to-Paper 实现。Code2Paper
仍需用真实仓库、作者 review 和冻结 artifact 验证自己的多权威信任边界。

## 14. 外部检索实现说明

如果后续把 Exa 接入 `external_literature` 通道，应提供两个明确分开的 backend：

- `ExaSearchBackend`：使用 `/search` 的 raw results + highlights，适合 Writer
  发出的窄问题、已知论文查找和可逐条复核的 evidence collection；
- `ExaAgentBackend`：使用异步 Agent Runs，适合开放式综述、候选列表和需要多步
  搜索/阅读/推理的任务。

用户提供的 `exa.agent.runs.create(...); poll_until_finished(...)` 示例属于第二类。
官方文档把 Agent API 标为 beta，并要求请求携带对应 beta version；因此集成时必须
把 SDK/API version、run id、events、grounding、cost 和最终 structured output
一起冻结，不能只保存综合答案。API key 只能从 `EXA_API_KEY` 等运行时 secret
注入，禁止写入仓库、prompt、artifact 或日志。

无论使用哪个 backend，Exa 输出都只能产生 literature evidence candidate，必须
经过 source/date/statement/citation 验证后才能授权正文。Agent 的 synthesized
output 不能作为它自己所引用事实的独立来源。Agent API 参考：
<https://exa.ai/docs/reference/agent-api/overview>。

本次收到的附件把 canonical URL 写为
`https://docs.exa.ai/reference/search-api-guide-for-coding-agents`；当前官方文档
入口已是
<https://exa.ai/docs/reference/search-api-guide-for-coding-agents>。附件中的
`/search`、`contents.highlights`、search types 和 `outputSchema` 说明与当前官方
指南总体一致，但旧 hostname 已过时，开发时应以当前官方 reference 为准：
<https://exa.ai/docs/reference/search>。
