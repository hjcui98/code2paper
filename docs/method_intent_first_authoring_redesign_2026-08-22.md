# Method 意图优先写作：质量失败诊断、架构修订与代码级执行计划

- 日期：2026-08-22
- `as_of`：2026-08-22（绑定 live `133302` 与当时工作区代码）
- 状态：Method Authoring 质量修复的**当前执行权威**；待 `/implement` 按 WP 串行落地
- 文档性质：落实
  [`publication_ready_method_writer_design_2026-07-31.md`](publication_ready_method_writer_design_2026-07-31.md)
  §1.3（代码没找到 ≠ 从故事删除）、§1.6（写作时返回研究）、§3.2（publication utility）
  与 §4.1（`formal_derivation` / `author_attested` 分车道）。
  **不是**新的总体架构规范，不替代
  [`agentic_robust_langgraph_research_writing_design_2026-07-19.md`](agentic_robust_langgraph_research_writing_design_2026-07-19.md)。
  **修订** [`method_argument_brief_compile_replacing_concept_cards_plan_2026-08-21.md`](method_argument_brief_compile_replacing_concept_cards_plan_2026-08-21.md)
  中「许可层纯确定性、无 LLM」对 **Candidate 措辞权** 的规定；**不修订** Verified 的 fail-closed。
- 绑定证据（只证明该次运行）：
  - DyG：`/tmp/c2p-wp-brief-dyg-qwen38-20260822-133302`
  - LinearRAG：`/tmp/c2p-wp-brief-linearrag-qwen38-20260822-133302`
  - 串行日志：`/tmp/c2p-wp-brief-serial-r5-20260822-133302.log`
- 非目标：Gate 6B/6C、D5、default cutover、release freeze；一次静态绿或一次 canary 成功都不构成这些门。
- 执行入口：§7 WP-L → WP-C → WP-F → WP-W → WP-R → WP-G（后接一次 DyG canary，再 LinearRAG）。
  **禁止**一次 `/implement` 铺开全部 WP。

---

## 0. 结论先行

用户对 `133302` 的判断成立，而且对应到具体代码路径，不是感觉问题。

| 用户判断 | 是否成立 | 实际发生的事 |
|---|---|---|
| 确定性 `compile_method_argument_briefs` 没把作者机制绑到证据 | **成立** | DyG 主线 `completeness=supported_by_repository`，但 7 条子句全是 `unlicensed`，`licensed_wording=""` |
| 许可规则太死板，Candidate 需要 LLM | **部分成立** | 需要 LLM 做 facet 拆分、候选召回与字段级蕴含提案；不应让 LLM 成为最终许可者。现有键提取会漏掉 `Δt`/`SSM`/`A`，但整句 LLM 授权又会误放行单调性、谱约束和理论动机 |
| 写的时候证据不足应继续搜代码 | **成立** | `133302` 因冻结根没有 `research_stage_checkpoint_v1.json`，`--repo` 也没进入 `fulfill_and_resume_writing_callbacks`；`reused_fulfilled_callback_ids=[]`，`writer_resumed_section_ids=[]` |
| `(intended design; pending…)` 壳导致没进 Candidate | **成立** | MA-S3 正文是标题 + 反复 caveat token，被 `_markdown_has_non_heading_body` 判 `section_body_missing_or_headings_only`。Planner 草稿里有 Δt/A/B/C，从未变成 `section_markdown` |
| `$x * y$` / `$$x + y$$` 不是论文公式 | **成立** | 冻结 `equation_claims_v1.json` 把 AST `computes_formula` 收成义务；Formalizer prompt 要求「不得改操作数/算子」，于是复述 `x * y`。DyG 的 `x*y` 是 `num_channels * channel_embedding_dim`；LinearRAG 的 `x+y` 是 `entity_weights + passage_weights` |
| 公式应在研究/ Formalizer 同步写，且必须是学术 LaTeX/MD | **成立** | P5（真 Formalizer、拒绝把偶然算术当成功）从未落地。`select_core_equations` 把 `computes_formula` + 裸 `mult`/`add` 当成 core |
| Rewrite 把仅有正文改成代码痕迹，这不是它的职责 | **成立** | DyG Rewrite 47 次、LinearRAG 78 次；prompt 示例是 `drop-FAC1` 空替换；`unsafe_positive_or_authority` 预算耗尽。终稿主语变成 `$DyGMamba.compute\_src\_dst\_node\_temporal\_embeddings$` |

**产品原则（本文件起对 Candidate 生效）：**

```text
作者意图机制
  -> 先拆成可独立判断的机制/动机/保证/约束/公式 facet
  -> 与仓库字段级对齐的 facet 写成证据支撑的论文叙述
  -> 对不上则按缺口有界重新搜索代码、配置与调用链
  -> 仍没有则以 author specification 写完整故事，不冒充已实现事实
  -> 对“可数学化且有论文表达价值”的机制建立公式义务
  -> Formalizer 优先从代码机制推导；证据不全时按作者声明形式化并显式写出条件
  -> 公式必须是可渲染的 Markdown + LaTeX，禁止代码味
  -> 逻辑、语句、描述与格式按计算机顶会 Method 要求
```

**信任边界不变：**

- `publication_candidate_method.md`：完整、可读的作者逻辑；未验证状态主要写入结构化 review sidecar，必要时由 Writer/Editor 生成每节至多一次的审阅注释。质量门看论证完整性，不靠删句过验证。
- `repository_verified_method.md`：只含仓库支持且通过反向验证的正向实现事实。语义许可、作者意图公式、搜索失败后的完整叙述**不得**进入 Verified。
- 未知 claim/equation/brief id 仍 fail-closed。Harness 不得发明证据 id。
- `local_text_repair` 仍不得路由回 intake（2026-07-19）。写作期搜代码走**新节点** `writing_research_continue`，不是打开 text-repair 回研究。
- LLM 可以提出语义对齐与公式候选，但**不是最终授权者**；授权必须由闭集 id、精确 span、字段级判定与确定性合并共同完成。

---

## 1. 绑定的 `133302` 证据（只读）

### 1.1 DyG Candidate 实际进了什么

`artifacts/06_authoring/publication_candidate_method.md` 只有三节：MA-S1 编码/路由、MA-S2 动机、MA-S4 下游。没有 Δt、没有 A/B/C SSM 改写。

MA-S1 主语是函数名，公式是形状乘法：

> The encoder `$DyGMamba.compute\_src\_dst\_node\_temporal\_embeddings$` … shape `$x * y$`, where `$x$` denotes the number of encoding channels …

这不是 Formalizer 写了 Δt 被滤掉，而是核心节没有可用正文。

### 1.2 MA-S3 被拒的原文

`publication_writer_result_v1.json`：

- `quality_failures`: `section_body_missing_or_headings_only`
- `section_markdown`：一个 H2 + 反复 `(intended design; pending author confirmation and repository evidence)`

`publication_method_writer._markdown_has_non_heading_body` 故意剥掉这些 token；剥完后体长 < 8，节被丢。这个门是对的，错在 Writer 产出了壳。

Planner 草稿没有变成 MA-S3 `section_markdown` 的完整调用链原因是：

```text
MechanismDraftV1 只作为 WriterView.mechanism_drafts 的可选上下文
  -> Writer schema 校验 brief/callback id，却没有 required-facet coverage
  -> prompt 同时强调 caveat 可见，模型用 pending token 交付
  -> 壳检测拒绝 section_markdown
  -> Candidate assembler 按“无可用节”跳过 MA-S3
  -> Rewrite 仍收到 unknown_style_section，继续对一个已丢节烧预算
```

所以不能靠“把 Planner draft 传进去”或放宽壳门解决；必须把草稿映射到 required facets，由
Writer/Writer Repair 生成正文，并让 issue owner router 阻止 Rewrite 接手缺内容问题。

### 1.3 许可层把主线机制判成未许可

`method_argument_briefs_v1.json` 主线 brief：

- 子句「Pass the aligned encoding through a continuous SSM…」→ `unlicensed`，`license keys hit but no supported or partial binding`
- 子句「Redefine the SSM step size Δt…」→ 同上
- 子句「Initialize the state transition matrix A…」→ `no closed-set license key hit`
- `licensed_wording=""`
- 同 brief 的 `mechanism_draft` **已经**写出 `MambaTimeDelta`、`Δt` 作为时间间隔函数、A 的稳定衰减、B/C 输入依赖。主链 Planner view 实际只带 claim/equation 文本与 fragment id；stage O-STAGE-02 的草稿才引用 `frag-43`–`frag-46`。这说明 Planner 能组织故事，**不能**说明它已经看过或验证过精确代码 span。

所以不是仓库没有 Δt，而是**确定性许可没认出来，Planner 根据闭集摘要组织出了草稿，Writer 又没有把草稿变成正文**。Planner 不是证据对齐器；它当前并未拿到精确 span excerpt。

根因在 `method_argument_brief_compiler.py`：

- `extract_license_keys`：只收 `[A-Za-z_][A-Za-z0-9_]*` 且 `len >= 4`。`Δt`、`A`、`B`、`C`、`SSM` 全部丢失。
- `_keys_hit_in_clause`：把子句压成 `[a-z0-9]+` 再做子串包含。作者说 “timespan / forgetting / diagonal / eigenvalues”，claim 说 `self.time_mamba` / `dts` / `in_proj`，字面键对不上。
- `_binding_matches_clause`：命中键后还要求区别性键（`matched - shared`）。R2 为防 `dygmamba` 污染是对的，但把「语义同一机制、词汇不同」也挡掉了。

2026-08-21 方案把这一点写成**特性**：义务级 `supported_by_repository` 不能推出所有子句许可。这个特性对 **Verified** 仍正确。对 **Candidate** 它造成：主线机制没有任何 `licensed_wording`，Writer 只看见 caveated 栏 + 草稿，模型用 caveat token 凑 `minLength`。

### 1.3.1 代码真值不能按整句二分

对 `models/mamba_simple.py` 的绑定代码只读核查表明，作者主句内部至少混有六个不同 facet：

| facet | 代码观察 | 本设计中的初始权威状态 |
|---|---|---|
| 时间间隔进入步长支路 | `dts` 被投影，并进入 `dt`、`B`、`C` 的生成 | repository-supported |
| 正步长 | 离散化前对 `dt + bias` 使用 `softplus` | repository-supported |
| `A` 为负对角参数化 | `A = -exp(A_log)` | repository-supported |
| 随原始时间间隔单调 | 前置线性投影权重未见单调约束；`softplus` 本身不足以证明复合映射单调 | unresolved / potential mismatch |
| `B/C` 的谱范数约束 | 未找到对应约束；`B/C` 在时间支路中是输入依赖量 | unresolved，不得写成实现事实 |
| Ebbinghaus 解释 | 属于作者动机/外部理论，不由仓库代码证明 | author/literature authority |

因此，新的对齐单位必须是 **facet/semantic field**，不能让 LLM 对整条复合子句给一个
`supported` 就把“时间支路存在”扩张成“单调性、谱约束和遗忘理论都已实现”。这一点也是
不能把 LLM 设成最终 license judge 的直接原因。

### 1.4 公式义务从一开始就是错的

DyG `equation_claims_v1.json` 第一条：

- `expression`: `"x * y"`
- `operation_predicates`: `["computes_formula"]`
- `operation_descriptors`: `["mult"]`
- 符号：`self.num_channels` × `self.channel_embedding_dim`

`formalization_section_results_v1.json` MA-S1/MA-S2 的 Formalizer 输出几乎逐字：

> purpose: Formalize the computes_formula that this section explains.
> latex: `x * y`
> symbol_definitions: repository operand `'self.num_channels'` …

`_equation_is_core`（`formalization_agent.py`）在描述符只有 `mult` 时，只要 fact 谓词 ∈ `_EQUATION_LICENSING_PREDICATES`（含 `computes_formula`）就判 core。于是形状乘法成为「本节核心公式」。

`_invoke_section_formalizer_llm` 的非意图车道合同写明：

> latex … preserving the exact operands, operators, numbers and dimensions of the authorized expression

`contract`: `exact_fact_equivalence_only`。Formalizer 被禁止把 `x*y` 改写成 Δt 机制。

LinearRAG Candidate 同样把 `$$x * y$$`（邻接矩阵形状积）和 `$$x + y$$`（entity_weights + passage_weights）写成「评分公式」，并带 `ent.label_ == 'ORDINAL'` 这种代码守卫。

### 1.5 写作期研究没有真正跑起来

Replay 条件（`scripts/run_authoring_replay.py`）：

```text
writer status ∈ {success, incomplete}
AND artifacts/research_stage_checkpoint_v1.json 已拷贝
AND --repo 是目录
```

才调用 `fulfill_and_resume_writing_callbacks`。

`research_stage_checkpoint_v1` 只在 `OPTIONAL_RESEARCH_ARTIFACTS` 里。`.tmp/c2p-stage1-canary/run-dyg` 没有该文件时，即使给了 DyG `--repo`，continuation 整段跳过。`execution_record.json`：`reused_fulfilled_callback_ids=[]`，`writer_resumed_section_ids=[]`。

即便 continuation 跑起来，当前链也缺三步：

1. callback 的 `exact_question` 是泛问「Which repository evidence resolves the unlicensed clause」，不是带 `Δt` / `MambaTimeDelta` / `dts` 的定向检索。
2. 新 evidence 之后**不**重新 `compile_method_argument_briefs`（`recompile_chain` 仍走 concept/placement）。
3. Writer resume 看不到更新后的 `licensed_wording` / 新公式包。

### 1.6 Rewrite 在错误目标上烧预算

`publication_writer_result_v1.json` `quality_failures` 大量：

- `rewrite:MA-S1:unsafe_positive_or_authority:attempt_budget_exhausted`
- `rewrite:MA-S1:missing_supported_proposition:…`
- `rewrite:unknown_style_section:MA-S3`（节已被丢，Rewrite 还在追）

`rewrite_agent.py` 系统提示把 `drop-FAC1` 空替换当作合法示例，并要求：

> If an offending positive assertion maps to neither surface, remove it

FAC 对不上投影 claim 时，模型删句或改成符号名。这与 `publication_quality.find_code_trace_prose_sections` / `method_language_style` 的本意相反：Rewrite 应去代码味、留机制，而不是为过验证拆掉作者故事。

---

## 2. 对用户问题的直接回答

### 2.1 「确定性 compile 没把作者机制绑到证据。规则太死板，是不是需要 LLM？」

**需要 LLM，但“让 LLM 负责许可”这句话本身有问题。** 问题不是确定性编译存在，
而是现有编译把**词法命中、证据检索、语义蕴含和最终授权**压成了一步。把这一步整体
换成 LLM，只会从“过严漏配”变成“整句过度授权”。

保留 `compile_method_argument_briefs` 作为 Verified 许可的唯一确定性来源（闭集键、未知 id
fail-closed、`may_enter_verified` 只看 `positively_licensed` 且 claim/equation 为 supported）。
Candidate 侧新增的是以下流水线，而不是一个自由裁判：

```text
LLM/embedding 召回候选 span
  -> LLM 将复合子句拆成 semantic facets
  -> 现有字段级 evidence judge 逐 facet 判断 entailed/partial/mismatch/unresolved
  -> harness 校验所有 claim/span id 属于闭集并保留精确 excerpt
  -> 确定性 policy merge 决定 Candidate prose mode
```

可复用现有 `method_proposition_compiler.py` 的 proposition decomposition，以及
`method_proposition_evidence_provider.py` / `SEMANTIC_VERIFIER` 的字段级证据判断；不应另造
一个能直接翻转授权位的 `METHOD_CLAUSE_LICENSE_JUDGE`。LLM 可以提出“Δt facet 与
`MambaTimeDelta` span 同一机制”，但不能发明 id、不能直接设置 `may_enter_verified`，也
不能把时间支路的存在外推成单调性、谱范数保证或 Ebbinghaus 实现。

### 2.2 「研究搜代码循环还是要开，后面写的时候证据不足还可以继续搜索。」

**要开，而且必须是原研究子图的有界续跑，不是 Writer 自己编 span。**

2026-07-31 设计 §1.6 已经要求这样做。代码里 `WritingCallbackFulfillment` +
`build_research_subgraph` 是骨架，`133302` 没接通。本计划把它升级为产品状态机节点，并强制：
新 evidence → binding/coverage/equation/completeness/brief/facet policy 完整 revision compile →
重跑受影响 Formalizer/Writer → reverse validation。

冻结 replay 也必须能搜：没有 stage checkpoint 时，从冻结 `intent_obligation_graph_v2`、
`research_agenda_v1`、packets/facts/claims 与 `--repo` 构造显式
`ResearchContinuationSeedV1`。它必须记录来源 digest、`origin=reconstructed_from_frozen_authority`
和 `past_decision_trace_available=false`，不能伪装成原 Research checkpoint；也不得因为缺一个
可选 JSON 就跳过搜索。

### 2.3 「标题 + 反复 pending 壳，太机械了。」

**机械性来自合同，不是模型偶然。**

Writer schema 在 `callback_required` 时给 `section_markdown` 设 `minLength`；`content_first_instruction` 虽然禁止空壳，但 `caveated_briefs` 被写成「必须带 caveat 的意图句」，模型用重复 token 满足长度和 caveat 可见。草稿在 `mechanism_drafts` 里，没有硬门要求「`planner_filled` 草稿必须进入正文」。

修复：有 `mechanism_draft.status=planner_filled` 时，正文合同是**消化草稿覆盖的 facet，重新写成顶会 Method 段落**；不是复制草稿，也不是把草稿当证据。caveat 每机制最多一次且不得单独成段，主要审阅状态进入 sidecar。壳节重试时把草稿、缺失 facet 与公式包作为 repair input。不得为了让壳过门而放宽 `_markdown_has_non_heading_body`，也不得用字符数下限代替语义覆盖门。

### 2.4 「公式能不能在研究搜代码时就同步 Formalizer 写？没有代码就按作者意图给配套公式？」

**可以同步，但应理解为“Research 产出公式证据包，Formalizer 随证据变化重跑”，不是
Research Agent 直接写终稿公式。还必须先判断该机制是否值得公式化。**

| 车道 | 何时 | 权威 | 能否进 Verified |
|---|---|---|---|
| `repository_derived` | 代码里确有机制级运算（Δt(ΔT)、PPR、归一化、损失） | 从操作重建，符号学术化 | 仅当反向验证通过 |
| `hybrid_partial` | 代码支持骨架，但某个性质/约束只来自作者声明 | 代码项与作者项分别标注来源，并显式写适用条件 | **否**，直到所有正向字段均闭合 |
| `author_intent_academic` | 作者声明了可数学化的模块/机制，代码缺失 | Formalizer 按作者声明给定义式；领域知识只用于标准记号与等价变换 | **否** |

禁止把 AST 层 `x*y`/`x+y`（形状、config 维、邻接 `shape[0]*shape[1]`）当作任一车道的成功公式。这就是一直没做的 P5。

并非每个 intent 点都强制有公式：动机、工程流程与接口描述可能只需要文字。Architect/Facet
decomposer 必须为每个机制给 `formula_expectation=required|preferred|none`；只有 `required` 未满足
才阻塞核心节。Formalizer **不是** Research 阶段的 AST 收割器。Research 提供连通的代码
操作、条件、shape 与作者 statement；公式 lexical 所有权仍是 Formalizer。模型“以前知道的
知识”不能变成项目实现事实；若使用 Ebbinghaus 等外部理论，必须进入独立 literature/citation
authority，而不是靠模型记忆补引用。

以当前 DyG 代码为例，一个允许送给 Formalizer 的候选结构是
`δ_k=softplus(W_δ φ(ΔT_k)+b_δ)`、`A=-exp(Ã)`、
`\bar A_k=exp(δ_k A)` 及状态更新；其中“`δ_k` 对 `ΔT_k` 单调”和“B/C 谱约束”必须作为
待证条件，不能从 `softplus` 或线性层存在自动推出。该式只用于说明 lane 判定，generic 生产
逻辑不得硬编码 DyG 符号或答案。

### 2.5 「Rewrite 应该把不像论文的句子重写，代码痕迹才是它该管的。」

**是。当前 Rewrite 把验证修复误当成主业。**

Rewrite 主职：`method_language_style`（去函数名主语、去 `self.`/`pad`/`softmax` 清单、改成机制/符号/变换主语）。

Rewrite 不得：为 FAC 对不上就 `drop_or_gap` 整句作者机制；把 `$Module.fn$` 当成「更可验证」的替换。验证失败必须先由 issue owner router 分流：证据缺口回 Research、公式问题回 Formalizer、缺机制/权威口径回 Writer Repair、跨节问题回 Editor；只有纯文风和代码痕迹进入 Rewrite。Candidate 保留完整 author specification，Verified 再按绑定过滤。

---

## 3. 架构修订

### 3.1 规范关系

```text
2026-07-19 总体设计     仍约束信任平面；local_text_repair 不回 intake
2026-07-31 Writer 规范  本文件落实其 §1.3 / §1.6 / §3 / §4，不改其 Verified 门
2026-08-17 Master Agent 产品主线仍有效；本文件补其「语义 Formalizer + 写作回研究」缺口
2026-08-21 论证包       保留 brief 中间层与确定性 Verified 许可；Candidate 增加 facet 对齐 policy
本文件                  Method Authoring 质量的当前执行权威
```

OpenCode 若发现实现需要削弱 Verified 门、过滤 claim、或让 `local_text_repair` 路由回 intake，必须停下来交给 Codex，不得自行改规范。

### 3.2 产品状态机（Method Agent 主链）

当前产品路径（`autonomous_method_agent.run_autonomous_method_agent` / `run_authoring_replay --rebuild-authoring`）是**顺序 Python 阶段**，不是 `build_code2paper_graph` 那张 R8 图。R8 图继续服务 Research 冻结与 text-trust。写作回研究不得改 R8 的 `text_trace_builder → local_text_repair` 安全注释。

在产品主链上把阶段升成**显式节点**（优先 LangGraph overlay，包在 `autonomous_method_agent`；若本切片来不及挂全图，也必须用同一节点名写进 ledger，后续再 `StateGraph.add_node`）。

```text
research_frozen
  -> brief_compile            # 确定性 compile_method_argument_briefs
  -> facet_decompose          # 复用 proposition decomposition；拆复合作者子句
  -> facet_evidence_align     # 字段级 evidence judge 提案 + 确定性 merge
  -> writing_gap_router
       ├─ evidence_gap → writing_research_continue
       └─ ready/exhausted → mechanism_planner
  -> mechanism_planner        # 组织机制草稿，不承担事实授权
  -> architect                # 已有
  -> section_formalizer       # 学术公式，三车道
  -> section_writer
  -> reverse_validate
  -> issue_owner_router
       ├─ evidence → writing_research_continue
       ├─ formula → section_formalizer repair
       ├─ content/authority → section_writer repair
       ├─ cross_section → editor
       └─ style/code_trace → rewrite_method_language
  -> editor
  -> rewrite_method_language  # 只处理论文语言 / 去代码痕迹
  -> split_candidate_verified
  -> author_review_items

writing_research_continue
  -> facts/claims/equations/briefs/facets 全量依赖重编译
  -> 仅失效并恢复受影响的 architect/formalizer/writer 节
  -> reverse_validate
```

`writing_gap_router` 预算：每节最多 `N` 次 continue（默认 2，与现 `callback-rounds` 对齐后提高到「有定向 query 的 2 轮」），全篇最多 `M` 次（默认 6）。搜索超预算 → 按 author specification 写完并记录 review sidecar，**不得**输出壳；若后续 Writer 自身仍无法覆盖 required facets，则按 WP-W 阻塞，不伪装成功。

R8 `build_code2paper_graph`：**不**增加 `authoring → intake` 边。新增独立
`product_authoring_graph.py` 承载上述产品状态；`writing_research_continue` 调用已有
`build_research_subgraph`，义务是 callback 新挂的、带定向 search terms 的义务，不是重跑整库
intake。第一批可先让顺序 Python 调用同名 node functions，但 ledger、状态 schema 和依赖失效
必须一次定义，不能长期维护第二套隐式流程。

### 3.3 Agent 职责（修订后）

| Agent / 节点 | 主职 | 禁止 |
|---|---|---|
| Brief compiler | 切子句；确定性 Verified 许可；闭集 id | 用义务级 completeness 整段授权；发明 id |
| Facet decomposer | 将复合作者句拆成机制、动机、保证、约束、公式等可独立判断字段 | 改写作者含义；把整句只给一个支持状态 |
| Evidence aligner | 召回闭集精确 span，并逐字段输出 entailed/partial/mismatch/unresolved 提案 | 直接翻转 Verified；只看 claim 摘要或 fragment id 就判支持 |
| Policy merge（harness） | 校验闭集 id/excerpt/digest，确定 Candidate prose mode | 生成论文正文；将 semantic proposal 当确定性事实 |
| Mechanism Planner | 按全部 author facets 组织机制草稿，尤其补齐 unresolved/partial 的故事连接（不是终稿） | 草稿当证据、公式或 `deterministic_generated` 终稿 |
| Architect | 按作者 spine 组节与 moves | 把未许可子句踢出故事 |
| Formalizer | 对 formula-worthy facet 产出可渲染学术公式与条件；按 repository/hybrid/author lane 分权威 | 复述 `x*y` 形状积；符号用 `self.foo`；用模型常识发明未声明算法；把意图公式标 `code_verified` |
| Section Writer | 按作者逻辑写完整顶会 Method；依据 prose mode 区分实现事实、作者 specification 与 mismatch；覆盖全部 required facet | caveat token 壳；函数名当主语；复制 Planner 草稿；漏掉核心 facet |
| Research continuation | 按子句/公式缺口定向搜代码 | 无 query 的泛搜；把旧 callback 当已完成 |
| Editor | 跨节术语、符号、重复、过渡 | 删核心机制 |
| Rewrite | 把代码走读改成论文句子 | `drop-FAC` 拆作者故事；用符号名替换机制叙述来过验证 |
| Verified splitter | 只保留确定性 `positively_licensed` 且 reverse-validation 通过的句子 | 语义许可或意图公式泄漏进 Verified |

最终 lexical token 仍只来自 Writer / Formalizer / Editor / Rewrite。Brief、草稿、语义许可、警告 JSON 都不是终稿正文来源。

### 3.4 三层授权模型：证据、Candidate 表达、Verified 发布

```text
AuthorClauseLicenseV1          # 现有；Verified 唯一确定性依据
  license: positively_licensed | partially_licensed | unlicensed
  bound_claim_ids / bound_equation_ids
  may_enter_verified 派生自本层

AuthorMechanismFacetV1         # 新增；作者语义的最小判断单位
  facet_id / clause_id / exact_source_quote
  facet_kind: mechanism | motivation | guarantee | constraint | interface | formula
  semantic_fields
  formula_expectation: required | preferred | none

FacetEvidenceAlignmentV1       # 新增；LLM 提案经 harness 闭集合并后的记录
  status: entailed | partial | mismatch | unresolved
  supported_fields / unsupported_fields
  bound_claim_ids / bound_span_ids / exact_excerpts
  search_terms / rationale / evidence_digest

CandidateFacetPolicyV1         # 确定性 policy 输出，不含论文 prose
  prose_mode: repository_statement | author_specification | mismatch_statement
  candidate_allowed: bool
  verified_directly_allowed: bool  # 只有 AuthorClauseLicenseV1 可使其为 true
  review_severity
```

Writer 选用规则：

1. 确定性 `positively_licensed` → `repository_statement`，无 intended 套话；可进入 Verified 候选。
2. 字段级 `entailed` 但未达 Verified 闭包 → Candidate 可用 `repository_statement`；sidecar 记
   `semantic_alignment_only`，不得进入 Verified。
3. `partial` → 支持字段写实现事实，剩余字段写 `author_specification`，不得合成一个无条件句。
4. `unresolved` 且搜索预算未用尽 → callback；Writer 可并行准备 author specification，不能声称已实现。
5. 搜索耗尽仍 `unresolved` → 完整写作者 specification；结构化 sidecar 记录未验证字段，正文
   只在影响审阅理解时由 Writer/Editor 生成一次简短注释，不得反复 pending。
6. `mismatch` → `mismatch_statement` 同时描述作者目标和代码观察，不删任一侧；阻止
   `publication_ready`，但不删除 Candidate 主线。

Candidate 与 Verified 的分离不能靠最终字符串正则。Writer/Editor 的每个句子或 span 必须带
`rendered_from_facet_ids`、`prose_mode` 与 authority bindings；splitter 只按这些结构化绑定和反向
验证结果组装 Verified。Review sidecar 至少写 `facet_id`、未支持字段、查询历史、停止原因和
人工决策问题。

---

## 4. 代码修改（按文件）

下列路径均相对于仓库根。未列出的模块默认不动。本节按职责便于阅读，真正实施顺序以 §7
为准（因此正文中 WP-W 出现在 WP-F 前，不代表先实现 Writer）。标为“新文件”的路径当前不存在。

### 4.0 共享模型

**`src/code2paper/agentic/method_argument_brief_models.py`**

- 保持 `AuthorClauseLicenseV1` 不变，避免把 LLM 结果混入 Verified digest。
- 新增 §3.4 的 `AuthorMechanismFacetV1`、`FacetEvidenceAlignmentV1`、
  `CandidateFacetPolicyV1`；`MethodArgumentBriefV1` 只保存它们的闭集引用与独立 digest。
- `MechanismDraftV1` 增加 `covered_facet_ids`。不要增加“草稿文本必须出现在 Candidate”的
  布尔位；真正的门是 Writer 输出覆盖 required facet，而不是字符串复制。
- 新增 `MechanismAuthoringPacketV1`：按 story 顺序携带 facets、policy、exact evidence excerpts、
  formula packages、适用条件、接口和 `required_facet_ids`。这是 Writer 的主输入。

**`src/code2paper/agentic/formalization_models.py`（若当前模型仍内嵌，则提取到邻近现有模块）**

- 新增 `MethodFormulaObligationV2`：`obligation_id`、`facet_ids`、
  `expectation=required|preferred|none`、`mathematical_goal`、`authority_requirements`。
- 新增 `MechanismEquationEvidencePackV1`：连通的 operation atoms、精确 span、前置条件、shape、
  作者声明和不支持字段；不再把一个孤立二元运算直接称为论文 equation。
- Formula package 增加 `formula_lane=repository_derived|hybrid_partial|author_intent_academic`、
  `markdown_block`、`symbol_table`、`assumptions`、`bound_facet_ids` 和 `review_status`。

**`src/code2paper/llm/role_config.py`**

- 新增显式 `METHOD_SECTION_FORMALIZER`（把现在匿名的 formalizer `model_copy` 收成角色）。
- facet decomposition 优先复用 `METHOD_PROPOSITION_ARCHITECT`，字段级判断复用
  `SEMANTIC_VERIFIER`；只有现有 schema 无法兼容时才新增窄角色，不能新增“最终许可裁判”。
- `LLM_CALLING_ROLES` 登记 Formalizer。
- Formalizer：temperature ≤ 0.2，max_output 8192（公式+符号表）；**删除** prompt 侧 `exact_fact_equivalence_only` 作为意图车道合同。
- Rewrite：保持 0.35；每节每轮最多一次纯 style rewrite，全流程最多 3 次。失败类型不属于
  style/code trace 时根本不调用 Rewrite。

**`src/code2paper/llm/response_schemas.py`**

- 增加 facet decomposition 与 field-level alignment batch schema；输出 id 必须属于请求闭集。
- Formalizer 包使用三车道，`markdown_block` 必须含可渲染 display math；同时返回 symbol table、
  assumptions 和 code-smell self-check，后者由 harness 复核而非自行声明通过。

---

### WP-L  Facet 级语义对齐与 Candidate policy merge

**目的：** 让“时间间隔进入步长支路”等真实字段与代码对上，同时阻止它把单调性、谱约束
和 Ebbinghaus 一并授权。

**`src/code2paper/agentic/method_argument_brief_compiler.py`**

- 保持 `extract_license_keys` / `_license_clause` 行为作为 Verified 层；不要加入 A/B/C/Δt 的
  项目式模糊授权规则。科学符号规范化只可改善**召回**，不可直接产生 license。
- 提供稳定的 clause/facet id 与 deterministic digest；policy merge 不得修改
  `AuthorClauseLicenseV1`。

**新文件 `src/code2paper/agentic/method_argument_facet_aligner.py`**

- `decompose_and_align_argument_facets(...)` 先复用 proposition architect 拆 facet，再调用现有字段级
  evidence provider。候选 evidence 必须携带 claim canonical text、**精确 span excerpt**、路径、行号、
  fact/equation 原子和 digest；不能只传 `frag-43` 或 Planner 草稿。
- aligner 输出提案；`merge_facet_alignment_policy(...)` 校验 facet/claim/span 闭集、excerpt digest、
  supported/unsupported fields，并按 §3.4 生成 policy。未知 id、缺 excerpt、字段越权均回 unresolved。
- parse 失败保持 unresolved；动机、文献、新颖性和理论保证不能由代码 span 判 entailed。

**`src/code2paper/agentic/autonomous_method_agent.py`**
（`compile_method_argument_briefs` 之后，planner 之前）

- 插入 facet decompose/align/policy merge；单独写
  `method_argument_facets_v1.json`、`facet_evidence_alignments_v1.json`、
  `candidate_facet_policies_v1.json`，不要把 LLM 结果揉进 deterministic brief digest。
- Planner 针对所有需要组织的 author facets 工作，而不是只给 unresolved 才工作；它的产物没有证据权。

**`src/code2paper/agentic/writer_view_projection.py`**

- 生成 `MechanismAuthoringPacketV1`，把每个 facet 的 prose mode、精确 excerpt、公式期望与
  `required_facet_ids` 投影给 Writer。
- 增加 `search_terms_by_facet_id`；Planner draft 只能作为 organization seed，不能成为 excerpt 或
  evidence constraint。

**测试 `tests/test_agentic_method_argument_briefs.py` 及新
`tests/test_agentic_method_argument_facet_alignment.py`**

- 确定性：主线 statement 仍不得整段 `positively_licensed`；Ebbinghaus 仍 unlicensed。
- 复合 DyG 风格夹具拆出至少“时间支路、正步长、单调性、谱约束、理论动机”五个 facet；
  前两项可 entailed，后三项不得随之授权，`may_enter_verified` 仍 False。
- 不在闭集的 claim/span id、缺 exact excerpt、未知 facet id → 对应项 unresolved，并记 schema failure。
- Planner 只有 fragment id、没有 excerpt 时，不得使 alignment 变 entailed。

**退出：** 冻结 DyG 夹具中代码已支持字段可进入 Candidate repository statement；单调性、谱约束
和 Ebbinghaus 保持 author/unresolved；Verified 判定与旧 deterministic digest 完全不变。

---

### WP-W  Writer：草稿即正文，禁止壳

**目的：** MA-S3 必须覆盖 Planner 草稿所代表的 Δt/A required facets，并由 Writer 自己写成
段落；不是要求复制 Planner 字符串。

**`src/code2paper/agentic/publication_method_writer.py`**

- `_writer_section_inputs` / `content_first_instruction` 改为消费
  `MechanismAuthoringPacketV1`，顺序强制：
  1. 按作者 story spine 写 problem/motivation → mechanism → definition/formula → algorithm/interface → output；
  2. 覆盖每个 `required_facet_id`，并在结构化输出中回报 `rendered_from_facet_ids`；
  3. `repository_statement`、`author_specification` 与 `mismatch_statement` 不能揉成一个无条件句；
  4. 公式只使用 Formalizer package；论文主语是机制、状态和变换，标识符只可作括号级绑定；
  5. 正文审阅提示每节至多一次，禁止 pending token 壳。
- 壳或 facet coverage 检测失败时，retry payload 必须包含草稿、缺失 facet、policy、公式包和
  previous Writer attempt，不得只重复 caveat 指令。
- `_markdown_has_non_heading_body`：**不要放松**。可增加 `_looks_like_caveat_shell(markdown) -> bool`，在 Writer 合同失败里显式返回，便于重试原因不是笼统 headings-only。
- required facet 未覆盖时记 `writer_missing_required_facets`，把问题交给 **Writer Repair**；不得先交
  Rewrite，不得由 harness 或 Planner 草稿填正文。重试预算耗尽后状态是
  `blocked_authoring_incomplete`，不得把缺核心节的薄 Candidate 标为成功，也不得粘贴非授权 lexical
  source。保留最后一个非壳 Writer attempt 供诊断，并在 sidecar 记录缺失 facet。

**`src/code2paper/llm/section_writer.py`**

- 不用 `minLength>=400` 解决质量；保留最低结构长度只拦截空输出，核心门改为 required facet
  coverage、公式义务覆盖、段落/句子结构、caveat ratio 与 code-trace density。
- `callback_required` 时**仍然要求** `new_research_requests`，但 **不再**暗示“不 callback 就不能写
  机制”。Callback 与 author-specification 起草可并行：先保持完整作者逻辑，同时挂定向搜索；
  evidence 返回后再决定哪些字段可改写成 repository statement。
- `_hard_publication_binding_failures`：保持 `missing_required_briefs` 不丢 markdown（已在 R5 修复）。未知 id 仍丢。

**`src/code2paper/agentic/method_argument_brief_planner.py`**

- Planner prompt 增加：草稿是 story/move 规划而非证据或终稿；禁止 `frag-N` 出现在草稿句里
  （frag 只放结构化引用字段）。`_build_frag_catalog` 必须在需要 evidence-aware planning 时提供精确
  excerpt，而不是只给 span id。现有“公式样机制必须绑定已有 equation 才可 planner_filled”改为绑定
  `MethodFormulaObligationV2`；无 repository equation 也可交给 `author_intent_academic`，不得为了通过
  schema 绑定错误 `x*y`。

**测试**

- `tests/test_agentic_method_argument_brief_integration.py`：MA-S3 风格夹具（heading + 重复 pending）仍判无正文；同夹具若 `section_markdown` 含草稿改写的 Δt 句则通过。
- `tests/test_llm_section_writer.py`：Writer response 必须回报全部 required facet ids；未知或缺失 id
  fail-closed；不对 Planner 字符串做 substring 门。
- 新测试：required facet 未渲染 → `writer_missing_required_facets` 并路由 Writer Repair；三次失败后
  `blocked_authoring_incomplete`，不得输出 success Candidate。

**退出：** 静态夹具证明壳进不了 Candidate、required facet 不能静默遗漏、正文词句始终来自允许的
Agent。Live 见 §8。

---

### WP-F  Formalizer：学术公式，拒绝偶然算术（P5）

**目的：** 对 formula-worthy mechanism 产出有条件、可追溯的学术公式；不再把 `$x * y$`
当成功，也不把代码未保证的单调性/谱约束写进 repository-derived 公式。

**`src/code2paper/agentic/equation_claims.py` / 研究期编译**

- 将 AST 二元运算保留为 `CodeOperationAtomV1`（或给现有 equation claim 增加等价的
  `formula_role=operation_atom|publication_candidate|incidental`）。描述符 ⊆
  `{add,sub,mult,div}` 且操作数是 shape/dim/config/len 时，可继续作为 supported code fact，但
  `formula_role=incidental`，**不**自动生成 `MethodFormulaObligationV2`。
- 公式义务来自 author facet 的 `formula_expectation` 和机制目标；Research 按义务收集相连的
  assign/call/transform/condition operations，形成 `MechanismEquationEvidencePackV1`。单个 `*`/`+`
  不是 evidence pack。
- 不得在 generic compiler 里写 DyG/LinearRAG 字面量。用操作数角色与 descriptor 规则。

**`src/code2paper/agentic/formalization_agent.py`**

- `_equation_is_core`：`only_generic` 算术 **不再**仅因 `computes_formula` 为 True。必须还有 `_CORE_EQUATION_DESCRIPTORS` 或机制谓词且操作数不是 shape bookkeeping。
- `select_core_equations` 过滤 `formula_role=incidental`。
- `validate_section_formula_package` 拆成：
  - `repository_derived`：保留操作数/数字闭包（可把 `self.num_channels` 写成 `C`，但必须能追溯）。
  - `hybrid_partial`：逐项标记 repository vs author 来源；所有保证附带显式 assumption，整个包不得进入 Verified。
  - `author_intent_academic`：检查括号平衡、非空、符号有定义、**禁止** `self.`、`torch.`、函数名、`shape[`；只允许形式化作者已经声明的机制，不能用模型常识增加新模块、损失或保证。
- `build_deterministic_formula_packages`：若 core 为空，返回空，**禁止**再为 incidental 方程造 `x * y` 包。

**`src/code2paper/agentic/publication_method_writer.py`**

- `_run_section_formalizer` / `_invoke_section_formalizer_llm`：
  - payload 增加 `MethodFormulaObligationV2`、作者 exact source quote、Planner organization seed、
    `MechanismEquationEvidencePackV1` 与 exact code excerpts。
  - 仅 `formula_expectation=required|preferred` 的 facet 尝试产包；`required` 失败阻塞本节，
    `preferred` 失败记 review，不制造装饰性公式。
  - 无 core equation 时走 `author_intent_lane`，合同改为：按计算机顶会 Method 给出定义式（例如 `\Delta t = f(\Delta T)`、对角 `A` 的离散化），`authority_status` ∈ {author_intent, partial}，`formula_lane=author_intent_academic`。
  - 有 core 且非 incidental 时：`repository_derived`，符号必须学术化（`\Delta t` 不是 `dts`）。
  - prompt **删除**「preserving the exact operands, operators」作为意图车道约束；该句只留在 `repository_derived`。
  - 拒绝包：latex 匹配 `^\s*x\s*[*+/]\s*y\s*$` 且 purpose 含 `computes_formula` / 符号 meaning 含 `self.`。
- Formalizer 在 Writer **之前**跑（已是）；callback 重编译后对受影响节**再跑**（WP-C）。

**研究期同步（WP-C 提供数据合同，WP-F 消费）：**

- `src/code2paper/agentic/research_nodes.py` 在 `compile_code_facts` 后不要自动
  `computes_formula` → 论文公式义务。只在存在 formula-worthy facet/obligation 时，沿 data/control
  flow 收集 evidence pack；Research 不生成最终 LaTeX。

**测试**

- 现有 Formalizer 测试：incidental `x*y` 不得 `code_verified` 进节包。
- 新测试：作者语句含 “step size Δt monotonically increasing in time gap”、代码只支持
  time-gap projection + softplus → `hybrid_partial`；公式可包含 `\Delta t`，但 monotonicity 是
  assumption/author field，不能标 repository-derived。
- 无代码、仅作者声明的可数学化机制 → `author_intent_academic`；不含 `self.`，不进入 Verified。
- LinearRAG 风格 `x+y` entity_weights 若无机制描述符 → 不得作为节的唯一公式成功。
- `tests/test_agentic_formalization_agent.py`（或邻近）：`select_core_equations` 对 `descriptor=mult` + `computes_formula` + shape 操作数返回空。
- `formula_expectation=none` 的动机 facet 不得被强制生成公式；`required` 未产出则阻塞该节而不是悄悄继续。

**退出：** 静态证明 x*y 形状积不能当 Method 公式成功；意图车道能产出 Δt 类 latex。Live 见 §8。

---

### WP-R  Rewrite：论文语言，停止 drop-FAC 拆故事

**先改路由，再改 prompt。** 当前 47/78 次不是单纯 prompt 不好，而是 authority、evidence、
formula、coverage 与 style failure 全被塞给同一个 Agent。

**新文件 `src/code2paper/agentic/publication_issue_owner_router.py`**

- 将 reverse-validation issue 确定性分派：`evidence_gap` → Research continuation，
  `formula_*` → Formalizer repair，`missing_core_facet|authority_framing` → Writer repair，
  `cross_section_*` → Editor，只有 `method_language_style|code_trace_prose` → Rewrite。
- 一个 issue 只有一个 primary owner；repair 后重新做受影响门，不能把未解决 issue 改名后交给
  Rewrite。每个 issue 记录 owner、attempt、input/output digest 与 stop reason。

**`src/code2paper/agentic/rewrite_agent.py`**

- 重写系统提示。删除 `drop-FAC1` 空替换示例。
- 合同改为：
  - 主任务 `method_language_style`：机制/数学对象做主语；代码标识符最多作括号绑定；禁止把主语换成 `$Class.method$`。
  - 不再接收 `unsafe_positive_or_authority` / `missing_supported_proposition`；这些属于 Writer 或
    Research。若调度器误传，返回 `wrong_owner`，不改正文。
- `replacement_text=""` 只允许删除纯重复/模板噪声，且 section semantic coverage 校验必须证明
  没有丢 facet；`drop_or_gap` 不能用于任何 required facet。

**`src/code2paper/agentic/publication_method_writer.py`（rewrite 调度）**

- 每节每轮最多一次 style rewrite，全流程最多 3 次；每次必须降低 code-trace/style issue 数且
  required facet coverage 不下降，否则回滚到 incumbent 并停止该路由。
- MA-S3 已被 headings-only 丢掉时，**不要**再对 `unknown_style_section:MA-S3` 烧 Rewrite。

**`src/code2paper/agentic/publication_quality.py`**

- `find_code_trace_prose_sections`：`$Name.method$` 与反斜杠逃过的 `compute\_src\_dst\_...` 计为代码痕迹。失败应触发 **style rewrite**，不是 drop。

**测试**

- 路由夹具：函数名主语 → Rewrite；FAC/evidence mismatch → Research/Writer，Rewrite 不被调用。
- Rewrite 夹具：输入函数名主语 → 输出机制主语，原文 facet coverage 不下降；
  `replacement_text` 非空。
- 禁止回归：prompt 文本不再包含 `drop-FAC1`。
- 3 attempt 后记 `rewrite_budget_exhausted_kept_incumbent`，incumbent 仍是 Writer 正文而不是空节。

**退出：** 静态证明 Rewrite 只处理 style/code trace、不会以删除 required facet 为默认修复。
Live 每节 style rewrite ≤3，且 Candidate 不再以函数名为节主语。

---

### WP-C  写作期研究续跑 + brief 重编译

**`scripts/run_authoring_replay.py`**

- continuation 条件改为：`--repo` 为目录 **且**存在 open callback、unresolved/partial/mismatch
  facet、required formula evidence gap 或 reverse-validation evidence issue。Writer 是否先返回 success
  不能成为唯一前置条件。
- 若无 `research_stage_checkpoint_v1.json`：构造独立 `ResearchContinuationSeedV1`，来源包括冻结
  intent/agenda/packets/facts/claims/equations/briefs/facets 的 digest，并显式设置
  `origin=reconstructed_from_frozen_authority`、`past_decision_trace_available=false`。不要把它命名或序列化
  为 checkpoint，也不要声称拥有不存在的原 Research 历史。
- 把 `callback_fulfillment` 写入 `execution_record.json`（`133302` 没有这项，诊断被藏起来了）。

**`src/code2paper/agentic/writing_callback_fulfillment.py`**

- `_continue_graph` 之后调用与初始 Research/authoring **同一组纯编译函数**，不能维护 callback 专用
  简化链。顺序固定为：
  1. 合并新 packets/spans/facts/claims 到新 revision（保留冻结根，只追加 child digest）；
  2. 重新 claim binding 与 `build_obligation_coverage_v2`；
  3. 重新产生/授权 operation atoms 与 equation evidence packs；
  4. 重新构造 config claims、completeness matrix 与 `compile_method_argument_briefs`；
  5. 对受影响 clause 重新 facet decomposition/alignment/policy merge；
  6. 重新编译 formula obligations/evidence packs、placement 和 `MechanismAuthoringPacketV1`；
  7. 仅 invalidated section 重跑 Architect（如 placement 变）、Formalizer、Writer、reverse validation。
- “已 positively licensed 不降级”不能写死；新证据若形成 mismatch/撤销，必须允许更保守地降级并
  记录 authority diff。只允许在无相关新证据时复用旧结果。
- `exact_question` / tool 参数：从 `search_terms` 填 `candidate_symbols_or_terms`，禁止空 terms 的泛问。
- `baseline_binding_missing` 不得对 reconstructed seed 直接 `return None`；以 seed 内 frozen authority
  作为 baseline，并在 receipt 中注明没有 past decision trace。
- ledger：node、facet/obligation id、query/path/symbol terms、tool turns、新 span/fact/claim 数、
  authority diff、affected section ids、information gain、stop reason。

**`src/code2paper/agentic/autonomous_method_agent.py`**

- 已有 `fulfill_and_resume_writing_callbacks` 调用改为走共享 revision compiler；每 facet 默认最多 2
  轮、全篇最多 6 轮。每轮必须有 information gain（新 span/fact/claim、字段 status 变化或明确
  negative search receipt），否则停止并切到 author specification；不得原样 query 重跑碰运气。

**`src/code2paper/agentic/graph_topology.py` / `graph.py`**

- **不要**改 `local_text_repair` 路由。
- 本 WP 先提供可复用 node functions 与 state schema；WP-G 新建
  `src/code2paper/agentic/product_authoring_graph.py` 挂图。不要修改 R8 `local_text_repair` 路由。

**`src/code2paper/agentic/writer_research_router.py`**（若仍被引用）

- open callback 的 `required_authority_lane=executable_hard` 必须带非空 `candidate_symbols_or_terms`。

**测试**

- Replay 无 checkpoint + 有 `--repo` 夹具 → 不再 skip；ledger 有 reconstructed seed provenance，
  且不出现 `synthetic checkpoint` 假历史。
- 一次 continue 产生新 claim 后，coverage/completeness/equation evidence/brief/facet policy 均按依赖
  重编译；Writer resume 输入含新的 `MechanismAuthoringPacketV1`。
- 空 search terms 的 callback 被 harness 拒绝。
- 新证据明确冲突时，原 positive 状态可降级并留下 authority diff；禁止“只升不降”。

**退出：** 单元测试证明“无 checkpoint 也会以诚实 seed 续搜”和“搜完会做完整 revision
compile”。Live DyG 应能定向搜到 `mamba_simple.py` 的 Δt 路径，并把真实支持与未证性质拆开后
交给 MA-S3，而不是把整个作者句一键 supported。

---

### WP-G  Product authoring LangGraph 与依赖失效

**新文件 `src/code2paper/agentic/product_authoring_graph.py`**

- 定义 `ProductAuthoringStateV1`：frozen/revision digests、brief/facet/policy/formula/section ids、
  open issues、budgets、attempt receipts、affected sections 与 terminal status。
- 按 §3.2 建 node/conditional edges。任何 repair 只能返回 owning node；禁止 Rewrite 承接所有失败。
- 定义失效表：evidence 变化失效 binding→coverage→equations→completeness→brief→facet policy→
  formula/placement→section；纯 style rewrite 只失效 surface/reverse-validation，不重跑 Research。
- `autonomous_method_agent.py` 与 `run_authoring_replay.py` 调用同一 compiled graph；迁移期旧顺序入口
  只能是 adapter，不得保留不同业务规则。
- checkpoint 保存产品 authoring state；Research continuation seed/checkpoint 是其 child state，不能
  冒充 R8 根图状态。

**测试**

- topology 测试证明 evidence/formula/content/style issue 分别回到正确 owner；不存在
  `local_text_repair → intake` 或 `rewrite → research` 的直接边。
- dependency invalidation 测试证明新增 span 会重编译所有下游权威产物，而纯 style repair 不会。
- resume digest 测试证明同 revision 幂等；changed evidence digest 不会错误复用旧 formula/section。

**退出：** 产品 live/replay 使用同一状态机和 ledger，后续不再由两个顺序 Python 分支决定某次
callback 是否“碰巧接通”。

---

## 5. Prompt / Tool 合同摘要

### 5.1 Writer

- 读者是顶会审稿人。按问题 → 机制 → 定义 → 公式 → 算法 → 条件 → 输出写。
- 作者意图是叙事骨架；facet policy 决定某一字段应写成实现事实、作者 specification 或 mismatch。
- 不要用 `(intended design; pending…)` 填篇幅。
- 公式只粘贴 Formalizer 的 `markdown_block`，自己不要发明 `$x * y$`。
- 输出必须回报 sentence/span 到 facet id 的结构化绑定；不得复制 Planner 原句来伪造 coverage。

### 5.2 Formalizer

- 输出必须是可被 MD/LaTeX 渲染的 display math。
- 符号：`\Delta t`, `A`, `B`, `C`, `\mathbf{h}`，禁止 `self.`、snake_case 函数名。
- 有代码：只把 exact evidence pack 支持的运算学术化；性质与保证必须逐字段验证。
- 无代码：只形式化作者已声明的可数学化机制，`authority_status=author_intent`；领域知识用于标准
  记号与等价表达，不能发明实现细节。
- 每个符号有定义，每个保证有条件；输出 Markdown + display LaTeX，并由 renderer fixture 验证。

### 5.3 Facet decomposer / evidence aligner

- decomposer 保留作者 exact quote，将复合句拆成可独立验证字段。
- aligner 只对请求闭集中的 exact excerpts 做字段级判断，不做写作、不做公式、不设置 Verified。
- `partial` 必须列出 supported 与 unsupported fields；无法判断返回定向 search terms。

### 5.4 Rewrite

- 只改文风与代码痕迹。不接 evidence、authority、formula 或 core coverage issue，不负责“让 FAC
  集合等于投影 claim 集合”。重写后 facet coverage 不得下降。

### 5.5 Research tools

- continue 轮使用现有 `execute_research_tool` / supervisor actions（`BUILD_BEHAVIOR_SUBGRAPH`, `COMPILE_FACTS`, …）。
- 参数必须带 facet id、exact question、`search_terms`，优先携带 symbols、path hints、caller/callee
  与 config terms；禁止无参数盲扫全库。
- 每轮保留 positive/negative receipt。若使用外部理论或文献，必须走单独 citation authority 和
  可追溯来源；本地代码搜索结果不能证明 Ebbinghaus 等文献主张。

---

## 6. 明确不改什么

- Verified fail-closed、未知 id 丢 markdown、evidence/qualifier/numeric/authorship 硬门。
- 不得靠过滤 claims、放宽 matching、把缺失输出当成功来让 `publication_ready`。
- 不得把作者 YAML 当实现事实。
- 不得让 LLM semantic proposal 直接翻转 Verified 或整句 Candidate 授权；必须经过 facet 闭集与字段级 merge。
- 不得强迫动机/接口等 `formula_expectation=none` facet 生成装饰性公式。
- 不得由 harness、Brief 或 Planner 草稿生成/粘贴最终正文；预算耗尽应阻塞并留诊断，不能违反 lexical source 边界兜底。
- 不得把项目名/已知答案写进 generic compiler。
- 不得 `git reset` / commit / 切分支。
- R8 `local_text_repair cannot route to intake`。
- `_markdown_has_non_heading_body` 继续拒绝纯壳（WP-W 改的是 Writer 产出，不是门）。

---

## 7. 执行顺序与验证

同一工作树串行。每 WP 结束写 `.agent/implementation.md`：命令、exit、摘要、代码状态。Codex 只读验收。

| 顺序 | 切片 | 静态验证 | 可否 live |
|---|---|---|---|
| 1 | WP-L facet 对齐/policy | brief + proposition/evidence provider + 新 facet alignment 测试 | 否 |
| 2 | WP-C 续搜 + 完整 revision compile | callback continuation / replay reconstructed-seed / invalidation 测试 | 否 |
| 3 | WP-F Formula obligation/evidence pack/P5 | formalizer / equation / rendering 测试 | 否 |
| 4 | WP-W Writer packet/facet coverage/禁壳 | section writer + brief integration + Candidate split 测试 | 否 |
| 5 | WP-R issue owner router + style Rewrite | router / rewrite / publication_quality 测试 | 否 |
| 6 | WP-G 产品 LangGraph | topology / resume digest / dependency invalidation 测试 | **是**：先 DyG 一次，再 LinearRAG |
| 7 | 全静态 | 仅当计划写明 milestone 时 `python -m pytest -q` | — |

每个 WP 单独一次 `/implement`；若实际共享 schema 导致 WP-L/C 必须同批，执行者要先在
`.agent/implementation.md` 说明边界，不能顺手铺开 WP-F/W。Live 必须等 WP-L–G 的对应静态门
全部通过。

相关：`python -m compileall -q src tests`；`git diff --check`。

---

## 8. Live canary 协议（仅 WP-G 之后）

1. 记录 runtime：`/health`、`/v1/models`、模型 id、queue/KV、fresh output directory。当前授权运行时是
   `http://127.0.0.1:8003/v1` + `qwen36-27b-nvfp4` +
   `tests/live/profiles/qwen36_vllm_budgeted.example.env`。`133302` 的 qwen38/8006 只属于历史产物
   provenance，不得作为新 run 配置依据；不要打印密钥。
2. 新鲜目录：`/tmp/c2p-intent-dyg-<stamp>`，然后 `/tmp/c2p-intent-linearrag-<stamp>`。**串行**，禁止并行抢同一模型。
3. 冻结根仍用 `.tmp/c2p-stage1-canary/run-dyg` 与 `run-linearrag`，`--rebuild-authoring --repo <path>`。
4. 成功信号（Candidate 质量，**不是** `publication_ready`）：
   - DyG Candidate **包含** Δt / timespan-aware SSM 节的非壳正文，required facet coverage 完整；
     未证字段在 sidecar 明确，正文不反复 pending。
   - 公式是可渲染的 `\Delta t` / 状态矩阵类 LaTeX，**不是**唯一公式 `$x * y$`；单调性与谱约束
     不得错误标成 repository-derived。
   - 节主语不是 `DyGMamba.compute_src_dst_node_temporal_embeddings`。
   - `execution_record` 有 callback continuation 字段；若仍 0 fulfilled，必须有 `stopped_reason` 和
     continuation origin，不能出现伪造的 synthetic checkpoint 历史。
   - LinearRAG 不再把 `$$x + y$$` 当检索机制的唯一公式；应出现 activation / PPR 类学术式（代码支持则 derived，否则意图车道 + 警告）。
5. 每节 style Rewrite ≤3；任何 evidence/formula/coverage issue 进入 Rewrite 都算路由失败。
6. 记录而不只目测：required facet coverage、author-spec preservation、alignment field precision、
   formula obligation/lane correctness、code-trace density、shell count、callback information gain、
   affected-section precision、Candidate→Verified authority leakage。
7. `133302` 只作对照，不得当本切片通过证据。

失败不得原样重跑碰运气。对照 §1 分类：许可 / 壳 / 公式 / Rewrite / 没搜到，回到对应 WP。

---

## 9. Codex 验收信号

PASS 仅当同时满足：

- 实现落在本文件 WP 范围，未改 AGENTS 非谈判边界；
- 所列测试命令在 `.agent/implementation.md` 有 exit 0 记录；
- 未把 facet alignment 提案直接写成 `may_enter_verified`，也未用整句 supported 覆盖 partial fields；
- 未让 incidental `x*y` 再成为 `code_verified` 节公式成功路径；
- 未由 Planner/harness 生成最终 prose，required facet 缺失会阻塞而不是产出薄 Candidate；
- 研究回流后执行完整 revision compile，且 reconstructed seed 没伪装成原 checkpoint；
- Rewrite 只收到 style/code-trace issue，Candidate/Verified split 使用结构化 authority bindings；
- 若已跑 live：§8 对照表逐项绑定新 `/tmp` 路径。

REPAIR：机制对但合同/测试缺口（与 2026-08-21 R2 方程许可同类）。

BLOCKED：必须削弱 Verified 门、打开 repair→intake、把作者意图当代码事实、让模型常识冒充引用，
或违反 lexical source 边界才能“写出 Δt”。

---

## 10. 与旧 `.agent/plan.md` §19 / 2026-08-18 review 的关系

`.agent/task.md` 仍是同一产品任务（author-intent-first Method Agent）。其中「真 Formalizer、不要 x+y 包装、Writer callback 走原 Research Graph」与本文件 WP-F / WP-C **是同一缺口**，以本文件的代码级拆分为准。

2026-08-22 早些时候对 R1–R4 的 Codex `REPAIR`（方程-only license、brief callback 未进 schema 门）仍然有效，并入：

- 方程-only `positively_licensed` 可放在 WP-L 确定性修补（Verified 层，有回归测试）；
- brief callback 进 `grounding_contract.callback_required` 并入 WP-C / WP-W。
- 旧任务里“synthetic checkpoint”按本文件改为 provenance 诚实的
  `ResearchContinuationSeedV1`；目标不变，但实现不得伪造历史。

不得另开新任务。不得把 `133302` 写成 R5 PASS。
