# Code2Paper 自主 Method Agent 全量架构复核与重整方案

- 日期：2026-08-13
- 状态：`ACTIVE_REWORK`
- 负责人：Codex
- 产品目标：给定作者意图、原稿或 claims，Agent 自主研究代码仓库，形成真实可编辑的
  Method candidate；代码证据充分的句子进入 repository-verified 版本，剩余内容进入明确的
  candidate caveat、补证回路或作者 review。
- 本文取代 `.agent/` 中把 proposition、hash、proof closure、测试数量或四项目矩阵当作主要
  开发目标的局部修复思路。旧文档仍可作为历史诊断和实现记录，但不能继续主导产品架构。

## 1. 结论

当前系统的首要问题不是 Writer 模型不够强，也不是再缺一类 validator。首要问题是实现把
“自主研究并理解代码”的主控制权交给了规则流水线，LLM 只在若干位置做有限选择或改写。
研究阶段得到的低层代码操作又被直接当成写作内容，导致即使仓库里已经找到网络、归一化、
排序、掩码、输出等真实机制，Writer 看到的仍是 `loads / calls / range` 形式的代码流水账。

本轮 RAP 真实产物已经给出完整证据：

- author story spine 包含 15 维特征、归一化、MLP、三类 loss、soft reweighting 和无渲染推理；
- research facts 已包含 `torch.cat`、`BatchNorm1d`、`Linear`、`ReLU`、score 排序、保留比例、
  boolean mask 和 PLY 输出；
- 最终 atomic claims 却主要是 `loads weights`、`calls range`、`normalizes normalized`；
- candidate 的 Overview 是占位句，Feature extraction 是代码操作记录，Learning framework
  内容空泛或越权补全，Deployment 为空；
- research 到 30 turns 仍多次读取相同 symbol，`max_turns_reached` 却曾被报告为 trusted；
- Writer callback 所谓 fulfilled 只是在旧 frozen facts 中重新找到 span，没有产生新理解、
  新 fact 或新 proposition。

因此必须优化整条产品主链，而不是继续在最后一层 Prompt 或 hash 账本上局部雕琢。

模型质量仍会影响语言流畅度和复杂推理，但它是第二层因素。一个合格架构应允许当前本地
27B 模型做到“过得去”：研究角色看到真实代码、自己决定工具参数；语义角色把若干代码事实
合成为方法命题；Writer 专注正文；Editor 可以整节重写；确定性层只负责事实边界。

## 2. 权威设计与实现偏离

权威设计本身的核心方向仍然正确：

1. LLM 决定研究行为，代码证据决定可陈述事实；
2. Supervisor 与 ToolNode/Observation/Critic 构成可回访的研究循环；
3. atomic claim 是验证单位，不是论文写作单位；
4. author intent 是论证和行文主线，但不能授权实现事实；
5. Writer 缺信息时可以 callback 到同一个研究系统；
6. candidate、verified、review 是三个不同产品。

当前实现的主要偏离如下。

| 目标 | 当前真实行为 | 产品后果 |
|---|---|---|
| Agent 自主研究 | LLM 过去主要选择 action label，query/path/symbol 多由 deterministic fallback 填充 | 重复搜索同一目标，不能根据代码内容改变策略 |
| 模型观察代码 | supervisor 过去只看到工具名、状态和 candidate count | LLM 无法判断实现语义或下一步该追 caller/data/config |
| 部分证据可用 | obligation 要求全部 typed targets 闭合后才生成 claims | 已找到的真实机制被吞掉，宽泛作者句长期卡住 |
| 方法级理解 | 每个 fact 自动变成一条 `subject predicate object` claim | Writer 输入天然是代码流水账 |
| completeness 表示真实支持 | 通用 predicate/token overlap 可以把无关 facts 标成 partial | loss、数据集等未实现内容出现假 partial |
| Architect 组织论证 | 主要按 stage/obligation 确定性分桶 | 标题可能正确，段落内容错位，计划膨胀到 20 多节 |
| Writer 写 Method | Writer 被要求同时满足内容、ID、proof、回调和多种绑定 | 模型注意力耗在协议，正文空泛或模板化 |
| Editor 学术修订 | 只能移动/去重原句，并复制 digest/patch 字段 | 不能把代码流水账改成连贯论文段落 |
| callback 补新证据 | 在旧 fact set 中做 span overlap 重定位 | fulfilled 不等于问题被回答，resume 仍使用旧内容 |
| trusted 表示研究完成 | graph 终止曾被等价为 trusted | budget/max-turn 或 fallback 被错误包装成成功 |

## 3. 产品成功定义

产品成功不是“所有 claim 都落到代码”，也不是“所有 obligation 都闭合”。产品成功是：

1. Agent 围绕作者想讲的方法故事自主搜索、阅读和追踪仓库；
2. 代码中存在的机制被提升为读者可理解的方法命题；
3. 作者想讲但代码只部分支持的内容被拆开：支持部分正常写，未支持部分带准确 caveat；
4. 代码和作者意图冲突时明确报告 mismatch，不静默选择其中一方；
5. 写到缺信息时，Agent 能提出精确问题并回到同一个研究循环补证；
6. candidate 是一篇有完整逻辑的可编辑 Method，而不是审计清单；
7. verified 只保留经过代码反向验证的正向实现陈述；
8. review 项给作者非空 proposed body、具体问题和真正需要的材料。

### 3.1 三类输出

`publication_candidate_method.md`

- 以作者 story spine 组织；
- 包含 repository-supported 方法内容；
- 允许 author-intent、partial、external/formalization 内容，但必须使用自然、明确的边界表达；
- 不能用 `Pending confirmation...`、`We aim to explain...` 之类占位句代替内容；
- 不能把路径、函数调用顺序和变量赋值直接当成主体 prose。

`repository_verified_method.md`

- 只含 frozen repository evidence 支持的正向实现句；
- 保留必要 branch、configuration、numeric、formula 和 qualifier；
- 每个句子经过最终 reverse validation；
- 缺证据时可以短，但不能伪造完整。

`author_review_candidates.json`

- 每个 item 对应具体 section/paragraph；
- 有可直接编辑的 `proposed_body`；
- 有精确 `confirmation_question`；
- 有 `needed_evidence` 和当前为什么不能进入 verified；
- review item 默认不阻塞 candidate，只阻塞对应事实进入 verified。

## 4. 目标架构

```text
作者意图 / 原文 / claims
        |
        v
Intent Intake：提取 story spine 与初始研究问题
        |
        v
Repository Research Manager <-------------------------------+
        |                                                    |
        | 自主选择 search/read/trace/config 工具和参数       |
        v                                                    |
Research Notebook + Evidence Ledger                          |
        |                                                    |
        v                                                    |
Method Understanding：代码片段 -> 方法级 propositions       |
        |                                                    |
        v                                                    |
Evidence Verifier：supported / partial / mismatch / unknown  |
        |                                                    |
        v                                                    |
Method Architect：story spine -> 3--6 节 + paragraph briefs |
        |                                                    |
        v                                                    |
Section Writer                                               |
        |                                                    |
        +---- 缺信息：精确 Research Question ----------------+
        |
        v
Semantic Verifier -> Academic Editor -> final reverse validation
        |
        +--> candidate
        +--> repository verified
        +--> author review / external queues
```

这是一个 Agent 产品，不是许多 Agent 名称的堆叠。默认只保留三个长期 LLM 角色：

- **Research Manager**：研究问题、工具选择、停止判断、callback 重入；不写最终 prose。
- **Writer**：根据已授权的方法命题和作者叙事写正文；不决定代码证据真假。
- **Editor**：整节改善段落、逻辑、术语和论文表达；不能引入新方法事实。

其他能力是 bounded mode/service：

- Method Understanding 与 Evidence Verifier 是低温语义服务；
- Architect 是低温 planning mode，不是常驻自治 Agent；
- Formalizer 只处理公式义务；
- Rewrite 是 Writer/Editor 的 issue-scoped repair mode；
- deterministic compiler/validator 是数据边界，不是另一个 Agent。

该模式与成熟 Agent 的共同做法一致：单一 manager 运行 tool loop，图运行时负责持久化和少量
外层分支；生成角色和评价/编辑角色分权；检索结果先形成 evidence synthesis，再交给 Writer。
参考资料：

- OpenAI Agent orchestration：<https://developers.openai.com/api/docs/guides/agents/orchestration>
- OpenAI Agent loop：<https://developers.openai.com/api/docs/guides/agents/running-agents>
- Anthropic Building effective agents：<https://www.anthropic.com/engineering/building-effective-agents>
- Anthropic Context engineering：<https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents>
- LangGraph persistence：<https://docs.langchain.com/oss/python/langgraph/persistence>

## 5. Research Manager 详细设计

### 5.1 研究议程是读者语义问题，不是 predicate 清单

Intake 从 story spine 生成 5--12 个可回答的问题，例如 RAP 应至少覆盖：

- 每个 primitive 的输入表示由哪些属性构成，如何归一化？
- pruning predictor 的网络结构、输入输出和激活是什么？
- score 如何用于排序、保留比例和 mask？
- 训练目标在代码中实际包含什么？哪些只来自作者意图？
- 推理/部署是否需要 rendering，结果如何写回或导出？

每个问题可以动态拆成 subquestion，也可被合并、降级或标为 out of scope。mainline 只提供
overview 导航，不能再成为“必须一次闭合整个 Method”的巨型 obligation。

### 5.2 一次真正的研究 turn

每个 turn 必须是：

1. Manager 看到当前问题、已有结论、最近真实代码片段、候选 symbol/path 和未解决点；
2. Manager 自己选择 1 个工具，必要时可选择同类 2--3 个独立调用；
3. Manager 自己填写 query/path/symbol/direction/depth 等参数；
4. harness 只做 schema、snapshot、路径和预算校验；
5. Tool 返回有界代码 excerpt、精确 span、symbols、relations 和语义 observation；
6. Manager 根据观察决定继续读、追 caller/data/control/config、换 query，或提交当前理解；
7. evidence service 验证理解后更新问题状态。

模型不能只看到 candidate count；也不能让 harness 替它生成内容参数。模型可以新建 search
query，但 read/trace 的 path 和 symbol 必须来自已观察候选或作者显式绑定。

### 5.3 模型可见工具

迁移期可以继续使用现有具体工具，但按六类呈现并保持语义正交：

- repository orientation：`list_repository_tree`、`find_entrypoints`；
- retrieval：`search_symbols`、`search_code`；
- exact reading：`read_symbol`、`read_code_span`；
- relation tracing：`find_references`、`trace_call_path`、`trace_data_flow`；
- branch/config：`inspect_control_flow`、`inspect_configuration`；
- local understanding：`build_behavior_subgraph`。

空壳工具不能进入 ready set。后续可把这些具体工具折叠为少数统一 tool schema，但不能为了
表面简洁先加一层只转发、不增加能力的 facade。

### 5.4 Research Notebook

Notebook 是给模型使用的有界工作记忆，不是又一套 hash 账本。每个 observation 至少包含：

- 当前调用回答了什么；
- 关键代码 excerpt；
- 新发现的 path/symbol；
- call/data/control/config relations；
- 新增证据和被排除候选；
- 仍未回答的问题；
- 与上一轮相比的信息增益。

长期 state 只保留短摘要和精确引用；需要时再用 read 工具重载源码。不要把全仓 AST、全部
fact、全部 proof 一次性塞进模型上下文。

### 5.5 breadth-first 再 depth-first

RAP 的 30 turns 被前几个 obligation 吞掉，说明需要跨 story node 的覆盖策略：

1. 第一轮对每个高优先级 story question 至少做一次 orientation/search；
2. 对每个问题保存候选和粗粒度状态；
3. 再按作者优先级、候选强度和 Writer 价值选择 depth trace；
4. 单个问题不能无限占用全局 turns；
5. Writer callback 的高价值缺口可以获得有限追加预算。

### 5.6 停止状态

问题级状态：

- `supported_by_repository`
- `partially_supported`
- `paper_code_mismatch`
- `author_intent_unverified`
- `author_confirmation_required`
- `external_evidence_required`
- `formalization_required`
- `out_of_scope`
- `blocked_tool_or_snapshot`
- `budget_exhausted`

Manager 可以在上限内灵活决定调用次数。全局 `max_turns`、wall time、token 和工具预算只是安全
上限。达到上限必须报告 `incomplete`，不能变成 trusted 或 explicit gap 的证明。

真正 gap 至少要求尝试过不重复的策略，如 query 变体、symbol 读取、caller/callee、data、
branch/config 中适用的若干类。完全相同的 tool+arguments 且无新增信息时，下一轮必须换策略。

静默 deterministic fallback 只可用于显式 `degraded` 运行，不能伪装成 autonomous success。

## 6. Method Understanding：本轮最关键的新层

### 6.1 为什么现有 fact/claim 不够

低层 facts 是必要证据，例如：

- 某函数读取 `self._features_dc`；
- 某处调用 `torch.cat`；
- 模型包含 `BatchNorm1d -> Linear -> ReLU`；
- 分数经过排序并生成 boolean mask。

但论文 Method 需要的是：

- “每个 primitive 的描述符由颜色与其他属性拼接而成”；
- “预测器使用带归一化和非线性激活的多层感知机生成 pruning score”；
- “分数经排序后根据保留比例转换为选择掩码”。

这些句子不能由 harness 拼模板，也不能要求 Writer 从一堆 `CALL/LOAD` 自己猜。需要独立的
Method Understanding 层：LLM 读取若干互相关联的代码片段和作者问题，提议方法级语义；另一个
低温 verifier 对照原始片段判断支持范围。

### 6.2 最小数据对象

不要继续扩张几十个 proof schema。只新增或收敛为四个产品对象：

`ResearchQuestionV1`

- question id、story node、读者问题、priority、scope；
- status、open subquestions、budget、affected sections。

`EvidenceNoteV1`

- 它回答哪个 question；
- method-level summary；
- reader subject、inputs、transformation、outputs；
- conditions/boundaries；
- exact span/relation refs；
- conflicting or unknown parts。

`MethodPropositionV2`

- 一条可用于 paragraph brief 的原子方法命题；
- authority lane：repository supported / repository partial / author intent / mismatch /
  external / formalization；
- required caveat；
- evidence note refs；
- immutable number/formula/config/condition。

`PropositionSupportVerdictV1`

- `fully_supported / partially_supported / contradicted / not_established`；
- supported clause 与 unsupported clause 分开；
- exact evidence refs；
- verifier rationale；
- 可否进入 verified。

### 6.3 编译和验证职责

Method Understanding owner 使用低温模型完成：

1. 按 research question 聚合相关 facts、relations 和 code excerpts；
2. 把多个低层行为合成一个读者可理解的 proposition；
3. 将宽泛作者句拆成多个可独立验证的 propositions；
4. 明确哪些语义来自作者、哪些来自代码；
5. 不创造 performance、benefit、causal 或保证性语言。

Evidence Verifier 使用独立低温调用：

1. 对照 proposition 和精确源码片段；
2. 判断 inputs/transformation/outputs/condition 每个 clause 是否被支持；
3. 部分支持时切出 supported clause，不把整句吞掉；
4. 发现冲突时进入 mismatch；
5. 没建立的内容回到 candidate/review，而不是靠 lexical overlap 升级。

确定性层只负责：

- source path 在 frozen snapshot 中；
- span/relation/fact IDs 确实存在且相互连接；
- 数字、公式、configuration 和 qualifier 没被改变；
- authority lane 没有升级；
- final positive sentence 可反向定位到经过验证的 proposition/evidence。

确定性 token/predicate overlap 不再有权判断一句方法语义是否被代码蕴含。

### 6.4 现有 proposition 层的处理

当前 `method_proposition_compiler.py`、`method_proposition_provider.py`、
`proposition_semantic_aligner.py` 和 `writer_view_projection.py` 是可复用的垂直切片，但尚不能
直接视为 Method Understanding 完成：

- compiler 的 source 输入仍主要是低层 atomic claims；
- proposition proposal 的 deterministic validator 能查 closed IDs/connectivity，却不能证明
  reader-facing transformation 被代码语义蕴含；
- final aligner 主要判断 Writer 句子是否匹配 proposition，不等于 proposition 本身正确；
- 一旦 proposition authority 升级错误，后续 reverse validation 会继承错误。

因此下一步不是再给 proposition 加更多 digest，而是给 proposition 增加独立的
`PropositionSupportVerdictV1`，只有 fully supported clause 才能进入 verified。旧 V1 可作为迁移
输入，不能成为最终事实授权。

## 7. Completeness 与 Method Architect

### 7.1 completeness 改为 question/proposition 关系

旧 completeness 的核心错误是用 obligation predicate 去匹配仓库中所有相同 predicate facts。
新 completeness 只回答：

> 某个 story question 是否有经过语义验证的 Method proposition？

每个 story node 分别统计：

- verified propositions；
- partial propositions；
- author-intent candidate propositions；
- mismatch；
- open research questions；
- external/formalization/author review。

一个问题部分支持时，支持部分立即可写；未支持部分单独 callback/caveat。禁止以“整条 author
sentence 未完全闭合”为理由吞掉所有已验证内容。

### 7.2 Architect 的真实输出

Architect 是低温 planning owner，输入 story spine、validated propositions、candidate
propositions 和 open questions，输出：

- 3--6 个 reader-facing sections；
- 每节回答的 reader question；
- 每节 1--4 个 paragraph briefs；
- 每段 required propositions、optional propositions 和 caveated propositions；
- 段落间逻辑：representation -> transformation -> training -> inference/deployment；
- callback-worthy missing information；
- 哪些 detail 应省略或放 review。

Architect 不应该：

- 一条 completeness row 生成一节；
- 把 source code 顺序当论文顺序；
- 为每个 rhetorical move 建硬 proof；
- 要求每个 proposition 都必须逐 ID 渲染；
- 用 20 多节把一篇普通 Method 拆碎。

Harness 只检查 section 非空、story 顺序合理、引用 IDs 存在、authority lane 正确，以及不存在
没有 caveat 的 unsupported positive。semantic frame、move proof、exact placement 可留在 audit
sidecar，但不再决定 candidate 能否写。

## 8. Writer、Verifier 与 Editor

### 8.1 Writer 可见上下文保持四层

Writer 每节只看：

1. 本节/本段要回答什么；
2. 可正向陈述的 verified Method propositions；
3. 必须显式 caveat 的 author/partial/mismatch propositions；
4. 不得改变的条件、数字、公式和配置。

fact IDs、claim IDs、semantic frames、move proofs、digests 和完整代码 trace 留在 binding sidecar，
不进入 prose prompt。必要时可给极少量 paper-term hints，但不能把函数名和变量名当成句子计划。

Writer 对 candidate-only 内容必须写“有实质内容的 caveated Method prose”，不能写占位句。例如
可以写“作者当前设想将该 score 与三项训练目标联合优化；仓库证据尚未建立这些目标的具体组合”
，不能只写“Pending confirmation”。

### 8.2 角色采样

- Research Manager：`temperature 0--0.2`，固定 seed；
- Method Understanding / Evidence Verifier：`0--0.2`；
- Architect：`0--0.2`；
- Writer：约 `temperature 0.7`、`top_p 0.90--0.95`、固定 seed 便于复现；
- Editor：约 `0.3--0.5`，允许语义保持下的学术改写；
- Formalizer：低温；
- Rewrite：按 issue，事实修复低温，语言修复中温。

greedy 跨 GPU 输出一致是正常现象。MTP 只影响加速，不应改变 greedy 结果。需要语言多样性时才
提高 Writer/Editor 温度；研究和验证角色保持确定性。

### 8.3 Editor 必须升级为整节学术编辑

当前 Editor 被要求：保留每个 factual sentence、只移动或精确去重、复制 before digest、计算
局部 patch。这会让 27B 模型把注意力耗在协议上，也根本无法把代码流水账重写成论文段落。

新 Editor 合同：

```text
incumbent section
section purpose / paragraph briefs
allowed positive propositions
required caveated propositions
immutable constraints
verifier/style feedback
-> revised full section
-> retained proposition IDs
-> deferred proposition IDs + reason
```

模型不计算 offset、digest 或 exact original span。harness 收到完整 revised section 后自动计算
diff、附加 before digest 和 provenance。然后重新运行 proposition coverage、authority framing、
numeric/formula/qualifier 和 reverse evidence validation。只有安全维度不回退且结构/语言有真实增益
时提交；否则保留 incumbent。

Editor 可以：

- 重排段落；
- 合并重复句；
- 将代码操作总结为方法概念；
- 添加不引入新事实的逻辑过渡；
- 统一术语、标题和符号；
- 在不改变 proposition 的前提下整节重写。

Editor 不可以：

- 引入新的网络、loss、数据集、数值或性能结论；
- 删除 required caveat；
- 把 author intent 写成 repository fact；
- 修改公式和条件；
- 通过删除难句来伪造质量提升。

### 8.4 Verifier 的位置

规则 style guard 只做快速检测，例如 code identifiers 过多、重复模板、空 section、占位句。它
不应自己改文。Semantic Verifier/Editor 使用相同四层上下文判断并修复：

- 这一段是否回答 section question；
- 是否把代码细节提升为读者语义；
- 是否遗漏了核心 propositions；
- author/partial 内容是否有正确 caveat；
- 是否存在通用、重复、AI 模板化表达。

最终 deterministic reverse validator 仍是 verified 输出硬门。

## 9. Callback 必须重入同一个研究循环

当前 `_BudgetedRepositoryCallbackProvider` 应退出产品主链。新 callback 流程：

1. Writer/Editor 产生精确 `ResearchQuestionV1`，包含 section、要回答的问题、已有命题、缺失
   authority 和为什么影响正文；
2. Router 将 repository/config 问题放回同一个 Research Manager；
3. Manager 在新的 scoped budget 内自由调用 1--N 次工具，次数由进展决定，上限只做安全保护；
4. 新搜索可以产生新 code excerpt、behavior relations、Evidence Notes 和 propositions；
5. Evidence Verifier 判断问题是否真正回答；
6. 只重建受影响 paragraph brief 和 section；
7. 无新证据时停止为 explicit unresolved/review，不能把“匹配到旧 fact”报告成 fulfilled。

其他 lane：

- author：生成 review item，不阻塞 candidate；
- formalization：交给 Formalizer，返回公式与条件绑定；
- literature/empirical：进入 typed external queue；没有外部集成时保持 pending；
- mismatch：默认进入 candidate caveat 和 author review，不自动选择代码或作者版本。

成功 callback 的最低标准是 evidence state 发生语义变化：新增 evidence note/fact/relation/
proposition 或把一个 unknown/partial verdict升级为 supported。只生成 artifact、digest 或旧 span
重定位不算成功。

## 10. LangGraph 的正确职责

LangGraph 保留，但降回运行时和产品状态机，而不是把每个 schema/compiler 都变成阶段节点。

主图只需少数节点：

```text
intake
  -> research_manager <-> repository_tools
  -> method_understanding <-> evidence_verifier
  -> architect
  -> writer
  -> semantic_review/editor
  -> callback_router --repository/config--> research_manager
                     --formalization------> formalizer
                     --external/author----> queues
  -> final_validation
  -> outputs
```

LangGraph 负责：

- checkpoint 和真实 resume；
- affected-section invalidation；
- 外层条件分支；
- budget/wall-time cancellation；
- run state 持久化。

普通研究动作仍是一个标准 Agent loop：model decision -> tool calls -> observations -> next
decision。不要再保留 direct driver 和 graph driver 两套权威行为。产品入口必须传 checkpointer 和
thread/run identity；checkpoint 不是证明机制，而是长任务恢复能力。

## 11. 保留、降级和移除

### 11.1 保留

- frozen repository snapshot 和 source authority；
- Python/其他语言 symbol adapters；
- 已有真实 search/read/reference/config/control/data-flow 工具；
- exact spans、relations、facts；
- EvidencePacket/CodeFact/AtomicClaim 作为审计和反向验证单位；
- author intent / repository / author / external / formalization authority lanes；
- story spine；
-四层 WriterView；
- candidate / verified / review 三输出；
- numeric、formula、condition、qualifier 和 final reverse validation；
- affected-section resume。

### 11.2 降级为 sidecar/audit

- semantic flow frames；
- move authority proofs；
- exact obligation placement；
- artifact-level多重 digest；
- plan closure matrix；
- full run matrix 和 release canary。

这些机制在审计、回放、release evaluation 时仍有价值，但不能成为 candidate 写作前的主要控制
路径，也不能成为日常开发的成功指标。

### 11.3 退出产品主链

- deterministic supervisor 的静默生产 fallback；
- all-target closure 后才允许任何 claim；
- `_COMPILE_NODE_LIMIT=3` / `_COMPILE_FACT_LIMIT=8` 代替语义充分性；
- 通用 predicate/token overlap 决定 partial；
- Mamba、PageRank、InfoNCE、15-dim 等已知项目专用生产启发式；
- 空壳或只返回字符串 ref 的 research tools；
- legacy V3 wrapper + old stage graph 双流水线；
- frozen-fact overlap callback；
- Writer/Rewrite/Editor 自己计算 offset/digest；
- 一条 completeness row 一节；
- 用测试数量、hash 数量、artifact 数量或 unsupported=0 单独宣布产品成功。

## 12. 代码级迁移顺序

下面五个切片全部要执行，但严格按依赖串行推进，避免在同一 dirty worktree 中多 Agent 同改
主文件。每个切片必须先用真实行为验收，再进入下一个。

### Slice 1 — 让 Research Manager 真正拥有工具循环

目标文件：

- `src/code2paper/agentic/gemma_supervisor_backend.py`
- `src/code2paper/agentic/research_supervisor.py`
- `src/code2paper/agentic/research_models.py`
- `src/code2paper/agentic/research_tools.py`
- `src/code2paper/agentic/research_graph.py`
- `src/code2paper/agentic/autonomous_method_agent.py`

改动：

- response schema 改为 model-owned concrete tool calls；
- observation 增加 excerpt、symbols、relations 和 semantic summary；
- 接通 `read_code_span`、tree/search/read/trace/config 可达性；
- stable tool signature 阻止相同参数无增益重跑；
- 多调用按数量扣预算；
- story questions breadth-first；
- partial 作为 first-class 非终止/可推进状态；
- max-turn 和 fallback 诚实报告 incomplete/degraded。

验收：用 RAP 前 8--12 turns 检查模型是否根据 search hit 自己选择精确 read，之后至少切换到
network、selection 或 deployment 问题；不得连续重复同一 tool+args。

### Slice 2 — 建立 Method Understanding V2

目标文件：

- 新建简洁的 `method_understanding_models.py`；
- 新建或收敛 `method_understanding_agent.py`；
- 改造 `method_proposition_compiler.py`；
- 改造 `method_proposition_provider.py`；
- 改造 `proposition_semantic_aligner.py`；
- 调整 `obligation_fact_alignment.py` / completeness builder。

改动：

- research question + code excerpts + relations -> Evidence Notes；
-低温 method proposition synthesis；
-独立 support verdict；
- supported clause 和 unsupported clause 分裂；
-移除 generic predicate 假 partial；
-只有 verified proposition 可进入 repository-positive lane。

验收：RAP 的 `BatchNorm/Linear/ReLU`、cat、score/sort/mask/retention/output 至少形成多条方法级
propositions；三类 loss 若无代码证据必须是 author-unverified/partial 的准确 clause，而不是绑定
无关 MLP facts。

### Slice 3 — 收敛 Architect、Writer 与 Editor

目标文件：

- `method_architect.py`
- `method_argument_models.py`
- `writer_view_projection.py`
- `section_writer.py`
- `writer_skill.py`
- `publication_method_writer.py`
- `cross_section_editor.py`
- `rewrite_agent.py`

改动：

- Architect 输出 3--6 sections + paragraph briefs；
- core/optional/caveated proposition 分开；
- Writer 只看四层视图；
- candidate-only section 写实质 caveated prose；
- Editor 改 full-section revision schema；
- harness 计算 diff/digest，模型不处理坐标；
-每次 revision 后重新做 semantic/evidence transaction。

验收：RAP Overview 必须概括完整方法主线；Feature section 解释 representation 而不是函数调用；
Learning 说明真实网络和已证实训练机制，同时对未证实 loss 做准确 caveat；Deployment 有真实内容
或明确、具体的 review 段，不能空白。

### Slice 4 — callback 重入和单一产品图

目标文件：

- `research_graph.py`
- `autonomous_method_agent.py`
- `writer_research_router.py`
- `writing_callback_fulfillment.py`
- `formalization_agent.py`
-产品 CLI/runner。

改动：

- callback 转换为 scoped research question；
- 重入同一个 Manager 和 ToolNode；
- 新证据重新经过 Method Understanding；
-增量重建 affected section；
-引入真实 checkpointer；
-旧 frozen-fact provider 退出主线；
-收敛 direct/graph 双 driver。

验收：Writer 提一个未回答的 repository 问题后，trace 中出现新 tool calls，evidence/proposition
state 有新增或 verdict 变化，只 resume affected section；没有新证据时 callback 为 unresolved，
而不是 fulfilled。

### Slice 5 — 通用化与真实产品验收

改动：

-清除四个样例专用的 production heuristic；
-RAP 纵向调通后运行 EBCAR、LinearRAG、DyG-Mamba；
-增加至少一个未知 holdout repository；
-根据模型并发能力最多四路独立运行，监控 queue/KV/OOM/abort；
-不通过换 seed 重复相同失败等待幸运样本。

四项目不是每个 slice 的硬门；它们是主链完成后的通用性验收。

## 13. 真实验收指标

### 13.1 Research 行为

- model-owned tool call 比例；
-有效 read/trace 与重复 tool signature 比例；
-story question coverage；
-每个 supported proposition 的独立 source spans/relations；
-max-turn/budget/fallback 的诚实终态；
-callback 是否带来新 evidence state。

### 13.2 Method 内容

-story spine 核心语义召回，而不是标题召回；
- repository mechanisms 的方法级表达覆盖；
-错误 partial 和错误 authority upgrade 数量；
-section/paragraph 完整性；
-占位句、代码流水账、通用重复句比例；
-candidate 与原作者目标的逻辑一致性；
-verified 的支持精度。

### 13.3 RAP 最低可用标准

| Story 部分 | Candidate 至少应做到 | Verified 边界 |
|---|---|---|
| Overview | 概括表示、预测、训练/选择和部署主线，并标明未证实部分 | 只保留有 proposition evidence 的概括 |
| Feature extraction | 说明真实属性拼接、维度/归一化中已由代码建立的部分 | 精确保留已支持属性和处理，不猜 15 维 |
| Learning framework | 说明真实 MLP/BN/ReLU、score 输出和已证实训练连接；三 loss 无证据则 caveat | 只含实际网络与训练/评分事实 |
| Selection/reweighting | 说明排序、保留比例、mask/weight 生成的真实控制逻辑 | 必须有 data/control relation |
| Deployment | 说明真实推理输入输出和导出路径；rendering-free 未证实则 review | 只含实际执行/输出事实 |

### 13.4 轻量验证策略

不为每个字段制造测试。只保留三类高价值验证：

1. 小型 deterministic fixtures：路径边界、预算、authority、numeric/formula/qualifier；
2. 少量行为测试：模型工具参数确实被采用、partial 不吞证据、callback 真重入；
3. 真实 API 纵向样例：先 RAP，再四项目和 unknown holdout。

静态 suite 和 compile check 是回归保护，不是产品完成证明。hash 只用于 frozen source 与必要
artifact 完整性，不作为开发进度指标。

## 14. 当前已落地的第一纵向切片

截至本文建立时，主线程已经开始 Slice 1，代码中已完成：

- `ResearchObservationV1` 增加有界 notebook；
- search/read/trace/config/control/data-flow 工具返回代码 excerpt、symbols 和 relations；
- supervisor prompt 恢复真实 result refs、spans、query 和代码语义；
- Research Manager 新 schema 允许模型选择 concrete tool + typed arguments；
- harness 仅做 Pydantic/path/snapshot/budget 校验；
- deterministic fallback 事件和 LLM decision 数量可进入产品 summary；
- `max_turns_reached` 不再报告 trusted；
- graph direct loop 开始真实扣减 consumed budgets；
- obligation 推进改为 story-order round robin，partial evidence 不再让一个宽 obligation长期独占；
- Writer 前的 proposition 纵向切片保留，但被重新定位为 Method Understanding 的迁移基础，
  尚未获得最终事实授权。

这不是 Slice 1 完成声明。仍需检查模型工具可达性、stable duplicate signature、多调用预算、
live schema 行为，并用真实 RAP 前若干 turns 验证策略确实改变。

## 15. 本轮明确不做的事情

- 不再新增 move proof、placement proof 或 artifact hash 系列；
- 不为了让已有测试通过而保留错误产品合同；
- 不把四项目静态测试全绿当真实可用；
- 不继续在 22 节 plan 上调 Writer 文风；
- 不把更强模型当成架构缺陷的替代修复；
- 不让 harness 从作者意图或旧 profile 合成实现事实；
- 不通过过滤 candidate 难句获得表面 unsupported=0；
- 不在同一主文件上并行交给多个 Agent 修改。

## 16. 完成定义

架构重整只有在以下事实同时成立时才完成：

1. Research Manager 在真实 API run 中能阅读代码、自己选择参数并根据 observation 改变策略；
2. RAP 已存在代码机制被生成读者级 propositions，而不是停留在 `calls/loads`；
3. unsupported 作者内容被准确拆成 substantive caveated candidate，而不是占位或假 partial；
4. Architect 生成少量连贯 sections/paragraph briefs；
5. Writer 和 Editor 生成基本可读、逻辑完整、非代码流水账的 Method candidate；
6. callback 对一个真实缺口产生新研究证据或诚实 unresolved；
7. verified 仍保持 final positive claim 的 frozen evidence 与 reverse validation；
8. RAP 之后，其他三项目和一个未知 holdout 表明没有依赖项目硬编码。

在此之前，任何 test count、digest、manifest、single canary 或 unsupported=0 都不能单独宣称产品
达到真实可用。
