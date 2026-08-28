# Method Authoring R5 质量退化根因与分片执行路线图

- 日期：2026-08-20
- 状态：诊断完成；WP0 是唯一已授权、可转化为下一实现任务的切片
- 文档性质：独立的代码级诊断与分片执行路线图；不是新的架构规范，不替代
  `.agent/` 协调文件，也不得作为一次端到端 `/implement` assignment
- 执行入口：§5 WP0 任务规格。其余章节是诊断、不变量和后续切片，不是本轮授权范围

## 0. 结论先行

R5 的主要问题不是“模型不够强”，而是当前主链让模型在一个错误的产品契约上工作：

1. replay 把旧的 `authoring_projection_v1`、`method_section_plan_v2` 和可选的
   `method_concept_cards_v1` 一并冻结，实际没有重新运行当前 Concept/Architect 主链；
2. Writer 收到大量低层代码 Concept，却没有收到“本节必须先解释哪些科学机制”的精确内容契约；
3. Writer 的 concept lane 没有可验证的 `rendered_concept_keys` 见证，最终验证又把一个 Concept
   扩张到整个 source obligation 下的所有 claims，导致偶然写到的代码 guard 可以被判 supported，
   但核心方法机制是否写出不可证明；
4. Formalizer 的 schema 允许最小合法对象 `{section_id}`，而上游 equation 只有原始 AST 运算，
   所以三项的 section formula 结果全部合法地返回空；
5. callback 只检查“产生了新 ID/新 span 和若干 supported facts”，没有检查所问机制的缺失槽位
   是否被回答；旧 evidence 重新挂到 callback obligation 上也可能被算作信息增益；
6. Method plan 给每节铺了近似通用模板的 required moves，并把多类 gap 都路由成
   `limitations_or_mismatch`，Writer 被迫同时追逐过多不属于本节科学功能的义务；
7. candidate checkpoint 与 resume 后的瞬时 `accepted` 状态混用，LinearRAG 已持久化的有效
   Candidate 被最终状态报告成 `candidate_available=false`，section checkpoint 也被空状态覆盖。

因此，下一步不应继续调 prompt、增加 token 或换模型。必须先打通六条纵向契约：

> 冻结 Research 权威 → 重建 Story/Concept/Plan → 生成 section content contract →
> Writer 显式提交内容见证 → reverse validator 精确核验 → Candidate incumbent 原子提交。

目标不是放宽安全门，而是让安全、内容完整性和产品状态分别拥有可验证的真值来源。Candidate
可以包含明确 caveat 的作者意图；Verified 仍只保留通过冻结仓库证据和反向验证的正向实现事实。

这些纵向契约是最终不变量，不是一次实现的授权范围。当前只执行 WP0：先修冻结边界、执行记录与
Candidate incumbent 真值，使下一轮产物可解释。WP1–WP6 必须在前一切片形成稳定 handoff、focused
tests 记录和只读验收后再单独进入；不得把全文交给 OpenCode 一轮铺开。

## 1. 权威、范围与非目标

### 1.1 权威顺序

本方案按仓库当前权威顺序解释和细化，不修改任何既有权威：

1. `docs/agentic_robust_langgraph_research_writing_design_2026-07-19.md`：LLM 控制研究，代码证据控制正向实现事实；callback 必须由 owning Agent 处理；最终文本必须保留 authorship 与反向验证。
2. `docs/publication_ready_method_writer_design_2026-07-31.md`：atomic claim 是验证单元而不是段落模板；MethodArgumentUnit/SectionArgumentGraph 控制论述；Formalizer、Writer、Editor 权限分离；publication utility 与 safety 正交。
3. `docs/method_agent_master_agent_mainline_execution_repair_plan_2026-08-17.md`：当前 Method Agent 主线及修复范围。
4. `docs/post_r8_research_agent_execution_plan_2026-07-31.md` 与 `docs/project_status_and_gap_report_2026-07-31.md`：仅在其证据绑定范围内提供执行和状态背景。

如果实现过程中发现本方案与上述设计在 authority lane、final lexical authorship 或 fail-closed
边界上冲突，停止实现并返回 Codex；不得自行弱化 gate。

### 1.2 本次诊断证据

- 用户审阅记录：`/home/cuihengjia/.codex/attachments/65acfc07-cf42-4591-8b1f-2180d55f4b9b/pasted-text.txt`
- R5 根目录：`.tmp/c2p-opt-20260820-r5/`
- 三项 replay：
  - `.tmp/c2p-opt-20260820-r5/replay-dyg/`
  - `.tmp/c2p-opt-20260820-r5/replay-linearrag/`
  - `.tmp/c2p-opt-20260820-r5/replay-ebcar/`
- 对照 Research 冻结根：
  - `.tmp/c2p-stage1-canary/run-dyg/`
  - `.tmp/c2p-stage1-canary/run-linearrag/`
  - `.tmp/c2p-q5-batch3/run-ebcar-research/`
- 项目原始 `paperdraft.md` 只用于人工质量审计和确定缺失的科学论述类型，不得进入生产事实权威、prompt fixture、项目特判或 generic production logic。

R5 只证明其绑定代码、输入和协议下的行为。三项使用的是
`http://127.0.0.1:8006` 上的 `qwen38-27b-nvfp4`，共同的 `src/**/*.py` digest 为
`sha256:a3277c0e8a6c332f3491b3916550a635da4e37072064c248e63807aca536cbce`。
该 digest 没有覆盖 replay script 和 profile，因此不能独立证明完整执行环境。

### 1.3 允许的实现范围（按切片，不是全文白名单）

当前已授权实现的只有 WP0，文件白名单见 §5 WP0。后序切片在各自 PASS 后方可动下列区域；
本文出现这些路径不构成现在就可以改它们：

| 切片 | 可动区域 |
|---|---|
| WP0 | replay 复制边界、终态 incumbent 提交、execution record/exit；见 WP0 白名单 |
| WP1 | `intent_compiler_v2`、concept card models/compiler、`SectionArgumentGraphV1`、`WriterViewV1`、Architect |
| WP2 | Writer structured output、exact relevance、final/quality witness |
| 3A | Formalizer schema、`select_core_equations` 回落、formalization route 四元绑定 |
| 4A | callback baseline span、target-concept judgment；formalization route 复用 3A |
| 3B/4B/WP5 | 仅在前序证据要求时进入 |
| WP6 | 测试编排与 live replay，不改生产语义 |

### 1.4 非目标

- 不把原论文当作生产事实源或让生成文本复刻原文。
- 不以关键词过滤、删除难写 claim、缩小 denominator 或把空输出当成功来提高指标。
- 不用 deterministic harness 生成、补写或改写科学正文。
- 不用项目名、源码路径、已知公式或三项人工答案进入 generic production logic。
- 不因一次静态通过或一次 live sample 宣布 D5、rollout、默认切换或 release freeze 完成。
- 不把“更长文本”当作质量目标；目标是机制完整、可编辑且 authority 清楚。
- 不把 §6.1 的三项目科学不变量当作 WP0 验收；WP0 只证明产物可解释。
- 不在 WP0 修改 Concept 语义、`realizes_story_node`、标题截断、Formalizer schema、
  owning-validator 或 Writer prompt。

## 2. R5 冻结产物事实

### 2.1 产品结果

| 项目 | Candidate 字节数 | Verified 字节数 | 最终 Writer 状态 | 主要事实 |
|---|---:|---:|---|---|
| DyG-Mamba | 5780 | 903 | `incomplete` | callback 4 fulfilled、1 pending；S2/S3/S4 resume；仍缺核心机制与公式 |
| LinearRAG | 5162 | 1179 | `blocked` | 磁盘有 5148 字符 Candidate checkpoint；最终却报告无可用 Candidate；S2 复用旧 callback |
| EBCAR | 7854 | 1847 | `incomplete` | callback 2 fulfilled、1 pending；S1/S3 resume；核心 loss/attention/inference 论述不完整 |

三项 `equation_coverage` 都是 `0.0`。DyG、LinearRAG、EBCAR 分别报告约 25、30、27
个 required move 缺失；EBCAR 另有 3 个 critical/high obligation 未放置。Candidate 比 Verified
长并不代表其可替代原 Method：正文主要围绕守卫、shape、fallback、分支和未证实 caveat 展开，
没有形成输入 → 表示 → 变换/公式 → 输出 → 下游使用的连续科学论述。

### 2.2 不是模型偶发失手的证据

- 三个 `formalization_section_results_v1.json` 中，所有适用 section 都是
  `declined_empty`；live response 均可化约为仅含 `section_id` 的合法对象。
- 三个冻结 `method_concept_cards_v1.json` 中，`realizes_story_node` 都未持久化为 true；当前模型默认值为 false。
- Writer 结果的 `used_argument_unit_ids`、`used_claim_ids`、`used_equation_ids` 普遍为空；concept lane 没有对应的 rendered/deferred concept 字段。
- callback trace 中，多项“fulfilled”所返回的事实与问题目标不一致，例如归一化问题得到 padding/mean，filter/noise 问题得到投影调用，attention mask 问题得到 positional encoding。
- callback trace 的 baseline span count 普遍为 0；请求中的 `frag-*` 引用没有还原为真实 span，导致旧证据可被识别成“新证据”。
- LinearRAG 的 `publication_candidate_checkpoint_v1.json` 有三个 section 和非空 final text，而最终 `publication_section_checkpoint_v1.json` 为空，最终 ledger 绑定空文本。

这些现象跨三个项目、跨多个 agent 重复，说明退化来自契约和状态机，不应归因为单个采样。

## 3. 代码路径上的具体退化机制

### 3.1 Replay 冻结了正需要重建的 authoring 层

`scripts/run_authoring_replay.py::FROZEN_ARTIFACTS` 当前直接复制：

- `authoring_projection_v1`
- `method_section_plan_v2`
- `equation_claims_v1`
- 完整 research 证据产物

`OPTIONAL_FROZEN_ARTIFACTS` 又允许复制 `method_concept_cards_v1`、proposition 系列以及旧 callback。
随后 `run_publication_method_writer()` 的 `rebuild_architect_plan` 默认是 false；存在 semantic frame 时，
本次只在旧 section/unit 结构上做 `replan_typed_semantic_graph_on_frozen_structure`。R5 的 copied plan
digest 与 Writer effective plan digest 不同，但 replay 没有把这次内存中的 effective plan 当作新的主产物
显式冻结和审计。

结果是：R5 测试了新 Writer 在旧 authoring 结构上的容错，并没有测试当前 Concept Compiler 与完整
Architect 能否重新理解论文故事。LinearRAG 的原 story spine 含 Motivation/Overview，但旧 plan 只有
三个后续 section，就是这个冻结边界的直接后果。

### 3.2 标题和节结构经历了上游冻结、Writer 二次退化两次损伤

`src/code2paper/agentic/intent_compiler_v2.py::build_story_spine_from_intent_graph()` 调用
`_truncate_story_title(statement, limit=96)`。后者只避免切进单词，不保证完整从句、括号闭合或语义完整。
R5 出现的 `vulnerable to`、`B/C with`、未闭合括号以及 `the Transformer` 结尾，因此不是模型首先
“抄坏标题”，而是上游先制造了残缺 structural title。第一刀已经固化在冻结 plan：LinearRAG 的
Motivation/Overview 在进入 R5 Writer 前就不在 effective section structure 中，DyG/LinearRAG 的残句
标题也已存在。第二刀才是 Writer 或 repair 照抄、继续截短，退化成 `Offline` 之类失去辨识度的标题。
只修 Writer 既不能恢复丢失 section，也不能恢复被冻结 plan 丢掉的标题语义。

最终标题同样受 lexical authorship 边界约束：harness 不应通过字符串截断或拼接来修正文题。
正确职责是 Story 保存完整作者陈述，Architect 只提供非词法的语义目标，Writer 生成 heading，
Writer/Editor owner 处理标题语法或语义失败。

### 3.3 Repository-positive primary 契约实际为空

`method_concept_card_compiler.py` 已有 `_card_realizes_story_node()`，但 R5 没有重建 cards；旧 artifact
在 `MethodConceptCardV1.realizes_story_node=False` 的默认下加载。更严重的是，
`method_concept_card_models.py::_CARD_AUDIT_DIGEST_EXCLUDE` 排除了 `realizes_story_node`，该字段变化
不进入 card audit digest。

`writer_view_projection.py::build_writer_view_from_concept_cards()` 的 `required_keys` 计算会把所有
`realizes_story_node=false` 的 positive concept 从 required 集合中去掉。于是：

- 大量 repository-positive 的 padding、shape、branch、guard、默认值可以进入 WriterView；
- 四通道聚合、图构建/传播、混合 attention/loss 等主故事机制往往只剩 caveated author-intent；
- Writer 没有必须优先完成的 primary mechanism，只能从最容易安全复述的低层事实组织正文。

这里不能笼统表述为“整个 Concept 契约为空”：caveated story stub 仍可能进入 required set。准确问题是
repository-positive primary required contract 实际为空，系统没有把可验证的核心仓库机制设成必写内容。

这解释了为什么文本看起来“安全且具体”，但不像 Method：主语常是代码检查或防御路径，而不是
论文提出的表示、变换和信息流。

### 3.4 Concept lane 缺少精确内容见证，final validation 又做了 obligation-wide 扩张

`src/code2paper/llm/response_schemas.py::PublicationMethodSectionOutputV1` 只有：

- `rendered_proposition_ids` / `deferred_proposition_ids`
- legacy `used_argument_unit_ids` / `used_claim_ids` / `used_equation_ids`

它没有 `rendered_concept_keys` / `deferred_concept_keys`。同时
`src/code2paper/llm/section_writer.py::_closed_set_publication_schema()` 只要存在 `writer_view` 就进入
`proposition_mode`，跳过 legacy used-ID 的 closed set，而 concept lane 的 proposition IDs 又为空。
因此 Writer 可以返回非空正文和空 metadata，系统无法证明哪一句完成了哪个 primary concept。

后处理中的 `publication_method_writer.py::_concept_claim_ids()` 仍把 verified concept 映射为其
source obligation 下的全部 claims。随后 `_sentence_validated_concept_claim_ids()` 将 lexical/semantic
匹配到的 concept 再扩张成这些 claim IDs。仓库已经有 `publication_relevance.py` 的 exact
`concept_bound_fact_ids()`、`concept_bound_claim_ids()`、`concept_audit_claim_ids_exact()`，但 final/quality
路径没有统一使用它们。

这会同时造成两种错误：

- 偶然写到一个外围 guard，可能借同一 obligation 下其他 claim 获得过宽支持；
- 主机制未写时，没有精确 missing witness 可以回到 Writer 或 Research owner。

Lexical matching 可以保留为诊断候选生成器，但不能再作为 coverage、Verified 或 callback fulfilled
的 authority。

### 3.5 Formalizer 的空输出是 schema 的最优最小解

`formalization_agent.py::SectionFormulaPackageBatchV1` 把 `packages` 定义为默认空 tuple；只验证
`section_id` 非空和 package section 一致。Prompt 又允许空结果。guided decoding 因此会稳定地产生
最小合法对象，`declined_empty` 不是 representation failure，重试也不会改变策略。

上游 `equation_claims_v1` 主要是 AST 级 `x*y`、`x+y`、`matmul`。`select_core_equations()` 为避免
把任意代码算术升级成论文公式，只在 descriptor 命中有限 core set 时选择；只要 generic descriptor
存在，就不再检查 fact predicate。这个安全方向正确，但信息模型太弱：例如 EBCAR 已抽到
`-pos_sim + logsumexp(all_sims)`，descriptor 仍只是 `add`，所以被丢掉；DyG 的 Δ/A/B/C 状态变换、
LinearRAG 的边权/传播/PPR 则根本没有形成 section formula obligation。

`writer_research_router.py::_execute_formalization_route()` 还有独立错误：只要全局
`FormalizationResultV1` 有 content digest，就返回 `formalization:result` 且 `validated=True`，不检查同一
section、同一 formula obligation 是否有 accepted package。R5 因此可在零 section packages 时把
equation callback 标成 fulfilled。

### 3.6 Callback 验证的是“有产物”，不是“问题被回答”

当前 Architect/replan 把多类 unresolved completeness gap 归为 `limitations_or_mismatch`，生成的问题
通常是“哪些仓库证据能补足本节缺失部分”，candidate symbols 则是大段代码/Concept 名单。Research
Agent 没有收到具体缺失的数据流关系、公式角色、条件或输出槽位。

`writing_callback_fulfillment.py::_ResearchGraphContinuationProvider._owning_validator_report()` 的通过条件
主要是：有 packet、facts supported、有绑定新 callback obligation 的 claims、有不在 baseline spans
中的 span、能命中某个 concept。它没有检查：

- 新 facts 是否回答 `missing_parts`；
- concept judgment 是否命中请求指定的 target concept；
- 新关系是否填补 input/transformation/condition/formula/output 中的 mandatory slots；
- evidence 内容是否相对 baseline 真正新增，而不是旧事实换了 obligation/ID；
- Research termination 为 incomplete/blocked 时是否仍有未满足 mandatory slot。

`_concept_judgment()` 只要新 spans 与任意已有 concept binding 重叠就接受；这解释了 callback 命中
无关的低层概念仍被标 fulfilled。fulfilled 之后只 append callback artifact，并没有要求重编 target
Concept、exact relevance、formula obligation 和 placement 后再 resume。

### 3.7 Required moves 近似通用模板，质量 denominator 被稀释

R5 每节出现 9–12 个 required moves，Motivation/Overview 也被要求 representation、transformation、
branch、equation、objective、output 等多类槽位；同时 limitations 几乎处处 required/open。一个真实
科学段落可以同时实现多个论述动作，但当前缺少 sentence/concept witness，质量层只能报告大量
`required_argument_move_missing`。

问题不应通过把 required 改成 optional 来隐藏。Architect 应先根据该 section 的 reader question、
story node 和 primary concepts 选择稀疏、section-specific 的 moves，再给每个 move 绑定可接受的 exact
concept/formula/dataflow witness。未解决事实挂回其 owning move；`limitations_or_mismatch` 只在论文
故事确实需要边界讨论时出现，而不是所有 completeness gap 的默认桶。

### 3.8 Candidate incumbent 与一次 resume attempt 混为一谈

`publication_method_writer.py` 后段用
`candidate_checkpoint_written and accepted` 计算最终 `candidate_generation_status`。这两个变量描述本次
函数调用/本轮 resume，而不是整个 run 已持久化的 incumbent。affected-only resume 失败时，即使之前
checkpoint 已有三个合法 section，当前 `accepted` 也可能为空，于是最终状态变成 failed。

该缺陷必须收窄到正常写作/affected resume 后的终态提交路径：早退 blocked 使用的
`_write_result_only()` 已经能够读取磁盘 Candidate，不应为修复本问题而重构或破坏这个正确路径。

LinearRAG 正好触发该路径：Candidate 文件与 checkpoint 非空，最终 section checkpoint 和 ledger
却绑定空结果。`scripts/run_authoring_replay.py` 在 callback 后更新 telemetry 的 `writer_status`，但退出码
仍检查 callback 前的 `result.status`，所以 execution record 可同时出现最终 writer blocked 和 exit 0。

这既是产品状态错误，也是后续质量诊断污染：同一 run 的 Candidate、checkpoint、ledger、quality、
result 和 execution record 不再指向同一 final text digest。

## 4. 目标数据契约

实现时优先扩展现有产品模型，避免平行的重复架构。若兼容性要求必须升版本，旧 V1 只能在显式
legacy/replay 模式读取；当前 mainline 不得通过默认空字段把旧 artifact 悄悄当成新契约。

### 4.1 Research-authoring 冻结边界

下一批 replay 只冻结不会由本次 authoring 修复重新计算的 authority：

- 作者意图：`intent_obligation_graph_v2`、`research_agenda_v1`；
- Research 事实：snapshot/behavior graph、`evidence_packets_v3`、`code_facts_v1`、
  `atomic_claims_v3`、`equation_claims_v1`、`configuration_claims_v1`；
- Research closure：claim/evidence map、coverage、completeness、reference agenda、checkpoint。

必须重建且不得从冻结根直接复制：

- `authoring_projection_v1`；
- Concept Cards、propositions、bindings、clusters；
- section plan、effective architect trace、section WriterView；
- formula obligations/packages；
- 本批 Writer callback、Candidate、Editor、Rewrite、validation 和 quality 产物。

历史 callback bundle 只允许用于专门的 callback-resume fixture；干净质量 replay 不复用旧 fulfilled
状态。新增 `authoring_rebuild_manifest_v1.json`，记录每个输入/输出 artifact 的路径、digest、schema、
authority class（author/research/derived-authoring）、copied/rebuilt 决策与生成代码 manifest digest。

### 4.2 Section content contract

Architect 在 Writer 前把 section-scoped contract 持久化到现有
`MethodSectionPlanV2.sections[]`（类型 `SectionArgumentGraphV1`），并由 `WriterViewV1` 投影消费。
仓库里没有名为 `MethodSectionGraph` 的类型；不得为本文新造平行类型。不得再增加一份与
plan/cards 并列的 `section_content_contracts_v1` 权威。如为审计需要输出独立 JSON，它只能是从
`SectionArgumentGraphV1` 确定性导出的只读 projection，不能拥有独立编辑或合并路径。

`SectionArgumentGraphV1` 现有字段包括 `section_id`、`heading`、`reader_question`、`moves`、
`unresolved_inputs`。WP1 在该对象上扩展 contract 字段，而不是另起权威：

```text
section_id
story_node_ids
reader_question
primary_concept_keys[]          # 有序、必须先解释的故事机制
supporting_concept_keys[]       # 实现细节，只能支持 primary mechanism
audit_only_concept_keys[]       # 不得进入正文正向陈述
required_dataflow_relation_ids[]
formula_obligation_ids[]
required_moves[] {
  move_id,
  acceptable_concept_keys,
  acceptable_formula_obligation_ids,
  acceptable_relation_ids
}
open_slots[] {
  owner,
  authority_lane,
  target_concept_key,
  slot_kind,
  blocking_for_candidate,
  blocking_for_verified
}
```

Concept 与 story 的关系必须是 digest-bound 的显式 ID 关系：使用
`realized_story_node_ids` 取代默认 false 的权威作用；`realizes_story_node` 可作为派生兼容字段但不得再
从 audit digest 排除。author-intent Concept 可以是 primary 且 candidate-only；repository-positive
Concept 只有在 exact obligation/fact/claim 关系证明时才可进入 Verified lane。

### 4.3 Writer 内容见证

升级 publication section structured output：

```text
section_id
heading_text                    # Writer lexical output
section_markdown
rendered_concept_keys[]
deferred_concept_keys[]
completed_move_ids[]
unresolved_points[] {
  target_concept_key,
  slot_kind,
  authority_lane,
  reason
}
new_research_requests[]
```

所有 key/ID 都由 `_closed_set_publication_schema()` 限制到当前 section contract。Writer 可以 defer，
但不得静默省略 primary concept；本地可研究缺口必须产生 typed callback，作者/文献/经验 lane 则进入
显式 review queue。

Writer 的声明不是最终 authority。post-processing 必须生成 sentence-scoped content witness：

```text
section_id
final_atomic_claim_id / final span
concept_key
exact_fact_ids[]
exact_claim_ids[]
equation_or_formula_package_ids[]
authority_lane
reverse_validation_status
```

只有该 witness 可驱动 move coverage、supported content recall 和 Verified；lexical matcher 只记录
candidate alignment/confidence 供诊断，不得授权 claim 或计算通过。

### 4.4 Formula obligation 与结果

不能从“发现了任意 AST equation”推导“本节需要公式”。WP1 必须在 `SectionArgumentGraphV1`
上落下每个 section 的 formula 真值，否则 Slice 3A 会把所有空 Formalizer 输出改名为
`not_applicable`，R5 的 `declined_empty` 只是换了标签。最低要求：

- 若 primary concept 或 required `equation_or_derivation` move 需要公式：写入非空
  `formula_obligation_ids`（可先引用已有 equation/fact/relation，不必等 3B 本体）；
- 否则显式 `not_applicable`，并写入原因（无 primary formula role / 无绑定 equation）。

Architect/Concept Compiler 从 story、primary mechanism、exact facts 和 dataflow 生成
`SectionFormulaObligationV1`：

```text
obligation_id
section_id
target_concept_key
mechanism_relation_refs[]       # 优先引用现有 exact predicate/dataflow relation
required_operand_roles[]
required_relation_roles[]
bound_equation_ids[]
bound_fact_ids[]
authority_lane
evidence_completeness
```

第一阶段不得新建一套完整的 `mechanism_kind` 分类学。Equation extraction 保留 `ast_operator`，formula
obligation 优先引用已有 assignment target、调用/数据流关系和 exact fact predicate；generic `add/mul`
descriptor 应回落检查这些 exact relations，而不是因为 descriptor 非空就提前停止。只有现有关系无法
表达、且跨项目 fixture 证明需要时，才增加窄而有版本的派生 mechanism role。不得把所有
`computes_formula` 或所有 `add/mul` 当作 core equation。

Formalizer 返回 discriminated result：

- `rendered`：至少一个 package，绑定同一 section 的具体 obligation/equation/fact；
- `unresolved`：列出 obligation、缺失 operand/relation 和所需 authority lane；
- `not_applicable`：仅当 WP1 已为该 section 写下显式 `not_applicable`；空字段不得自行升格。

存在 required formula obligation 时，`{section_id}` 必须 schema-invalid。representation-only 错误可
由 recovery 重试；语义 unresolved 必须回到 Formalizer/Research owner，不能由 harness 填公式。

Formalization callback 只有在同一 `request_id + section_id + obligation_id` 的 accepted package 或明确
解决该请求的 typed resolution 上才能 fulfilled。全局 `formalization_result_v1` digest 不再足够。

### 4.5 Callback answer contract

扩展 `WritingResearchRequestV1`，至少加入：

```text
target_story_node_ids[]
target_concept_keys[]
target_formula_obligation_ids[]
mandatory_missing_slots[]       # input/representation/transformation/relation/condition/formula/output
baseline_fact_fingerprints[]
baseline_claim_ids[]
baseline_span_ids[]
excluded_audit_concept_keys[]
```

`baseline_span_ids` 必须由请求生成端持久化真实、可解析的 Research span。不得增加一个根据 `frag-*`
字符串猜测 span 的启发式 parser；只有存在确定且 digest-bound 的映射时才可解析，否则请求 fail closed
为 `baseline_binding_missing`，不能以空 baseline 继续。

Research 返回的 owning-validator report 必须逐槽报告 `satisfied_slots` 与 `remaining_slots`。信息增益按
canonical fact identity 判断，而不是 callback obligation ID、fact ID 或 span 列表长度。canonical
identity 至少覆盖规范化 subject/predicate/object、source snapshot/span 和 relation endpoints。

full fulfillment 的必要条件：

1. 每个 mandatory slot 被新的 exact fact/relation 或合法的 typed resolution 覆盖；
2. 新 evidence 相对 baseline canonical set 有语义增量；
3. concept judgment 只命中请求指定 target concept，并更新其 exact binding；
4. fact/claim 通过现有 compile gates；
5. callback merge 后重编 Concept → relevance → formula obligation → placement；
6. 只 resume 真正受影响的 section。

只满足部分槽位时状态保持 open/partial，并持久化剩余槽位；Research graph incomplete/blocked 且仍有
mandatory slot 时不得标 full fulfilled。`existing_behavior_graph` 可以提供答案，但只有在它包含 baseline
中未消费、且确实填补目标槽位的 canonical relation 时才算增量。

### 4.6 Candidate incumbent

引入单一的 durable incumbent 状态（可扩展现有 candidate checkpoint）：

```text
candidate_digest
section_digests {section_id -> digest}
section_outputs
authorship_bindings
last_committed_attempt_id
warnings
```

每轮 affected resume 是事务：从已校验 incumbent 开始，只替换通过 section binding/authorship gate 的
受影响 section；失败 section 保留旧版本并添加 warning。只有新组合 Candidate 完成 digest、section
checkpoint 和 ledger 一致性校验后原子提交。任何失败尝试都不能把 incumbent 覆盖为空。

最终 `candidate_generation_status` 由已认证、非空且持久化的 incumbent 决定，不由当前局部变量
`accepted` 决定。result、Candidate markdown、candidate checkpoint、section checkpoint、authorship
ledger、quality report 和 execution record 必须共享同一 final candidate digest。

## 5. OpenCode 实施工作包

以下工作包是依赖有序的路线图，不是一份可一次交给 OpenCode 的大任务。当前唯一下一执行切片是
WP0；WP1–WP6 只描述后续方向，不因出现在本文中自动获得实施授权。

每个切片必须单独形成稳定 handoff，记录 focused tests 和冻结证据，再由 Codex 按仓库流程只读验收。
PASS 后才能创建下一切片；REPAIR 在同一切片、同一 worktree 内继续，不得另起架构或跳到后续 prompt
调优。当前 dirty worktree 是基线，不得 reset、clean、checkout、commit 或丢弃用户改动。任何为通过
测试而削弱 authority/gate 的改动都视为越界。

执行切片顺序为：

| 切片 | 范围 | 下一任务资格 |
|---|---|---|
| Slice 0 | WP0：冻结边界、执行记录、Candidate incumbent | 唯一候选 |
| Slice 1 | WP1：Story/Concept/section contract 重建 | 否，等待 Slice 0 PASS |
| Slice 2 | WP2：Writer concept witness 与 exact binding | 否，等待 Slice 1 PASS |
| Slice 3A | WP3 最小公式闭环 | 否，等待 Slice 2 PASS |
| Slice 4A | WP4 callback 三项硬防线 | 否；4A.3 等待 3A。4A.1/4A.2 可与 3A 并行，不得并进 WP0 |
| Slice 3B/4B | 完整 formula obligation 与 semantic delta | 否，由前序证据决定范围 |
| Slice 5 | WP5：Writer/Editor 科学论述行为 | 否，等待内容契约稳定 |
| Slice 6 | WP6：静态集成、DyG canary、其余两项矩阵 | 否，最后执行 |

### WP0：唯一下一切片——任务规格（可直接转化为 `.agent/task.md`）

本小节是当前唯一可执行 assignment。转化任务时复制本小节，不要把 §3–§4 的后序契约或 §6.1
三项目科学不变量写进 WP0 验收。Codex 只读验收也只对照本小节。

#### 目标与非目标

目标：下一轮 authoring 的输入边界和产品真值可解释。不宣称 Method 正文质量改善。不跑 live。

禁止：

- 改 Concept 编译、`realizes_story_node`、96 字标题截断、Architect 故事脊、Writer prompt、
  Formalizer schema、`_owning_validator_report`、quality denominator。
- 为绿灯把 `rebuild_architect_plan=True` 当作 rebuild：该路径只 replan 冻结 section 结构。
- 重构或削弱 `_write_result_only()`：早退 blocked 已能读取磁盘 Candidate，保持该行为。
- 破坏 final-integrity / authorship gate 来换 incumbent 一致性。
- `git reset` / `clean` / checkout / commit / 丢弃无关用户改动。

#### 文件白名单

只允许改：

- `scripts/run_authoring_replay.py`
- `src/code2paper/agentic/publication_method_writer.py`（终态提交、affected resume 合并、
  incumbent 判断；函数约在 `candidate_checkpoint_written and accepted` 与
  `_incumbent_candidate_available`）
- Candidate / section checkpoint / writer result 的既有 product model，仅当需要
  `last_committed_attempt_id` 或 digest 对齐字段；不得改 Writer lexical schema
- `src/code2paper/agentic/writing_callback_fulfillment.py` 仅当必须把 callback 后
  `run_publication_method_writer` 的 result 交回 replay 的 status/exit；不得改 owning validator
- `tests/test_agentic_candidate_verified_split.py`
- `tests/test_agentic_replay_execution_record.py`
- `tests/test_agentic_publication_method_writer.py`
- 若 replay 需要新 fixture：只加在 `tests/` 下，不写项目特判进生产逻辑

#### 复制边界（动作 1–5）

默认只复制 research/author authority，不得复制 derived-authoring：

```text
COPY (author/research):
  intent_obligation_graph_v2
  research_agenda_v1
  method_evidence / claim_evidence_map / obligation_coverage_v2
  reference_method_agenda_v1 / method_completeness_matrix_v1
  equation_claims_v1 / configuration_claims_v1
  evidence_packets_v3 / code_facts_v1 / atomic_claims_v3
  behavior_graph_v1（若作为 research 事实而非 authoring 推导）
  research_stage_checkpoint_v1（research 子图状态，不是 Writer callback 真值）

DO NOT COPY (derived-authoring):
  authoring_projection_v1
  method_section_plan_v2
  method_concept_cards_v1
  method_propositions_v1 / method_proposition_bindings_v1 / method_proposition_clusters_v1
  writing_research_callback_artifacts_v1
  formula packages / writer / editor / rewrite / quality / candidate 产物
```

`--rebuild-authoring` 只接线、不修编译器：

1. 调用现有生产入口（`compile_method_concept_cards` 与完整 Architect，而不是
   `replan_typed_semantic_graph_on_frozen_structure` 吃旧 cards）。
2. 不得在 WP0 修改那些 compiler 的截断、story 绑定或 move 模板。当前 compiler 仍会产出残句标题和
   `realizes_story_node=false` 的 cards——这是 WP1 的缺陷，WP0 如实记录在 manifest 的 rebuilt digest。
3. 若现有代码没有「不读冻结 plan/cards 也能 rebuild」的独立入口：flag 必须 fail-closed，typed
   reason `authoring_rebuild_entry_unavailable`，退出非 0，且不得回退为复制旧 derived artifact。
4. 另设 digest-pinned `--reuse-authoring-callbacks`（或等价 fixture flag）；clean 默认不复制旧
   callback。没有该 flag 时复制 callback 测试失败。

持久化 `authoring_rebuild_manifest_v1.json`：每个输入/输出的路径、digest、schema、authority class
（author / research / derived-authoring）、copied 或 rebuilt 或 refused、原因。执行 digest 覆盖
`src/**/*.py`、`scripts/run_authoring_replay.py`、所选 live profile、capability JSON、frozen input
manifest。缺任一则 fail-closed。不得把 git hash 当质量分。

#### Incumbent 终态（动作 6–9）

只修正常写作 / affected resume **之后** 的提交路径，不改早退 `_write_result_only()`。

缺陷位点：`publication_method_writer.py` 用本次调用的
`candidate_checkpoint_written and accepted` 设置 `candidate_generation_status`。LinearRAG R5：
candidate markdown 与 `publication_candidate_checkpoint_v1` 非空，但本轮 `accepted=[]`，于是
result JSON `failed`、`publication_section_checkpoint_v1.sections` 为空、ledger digest 为空串。

要求：

1. 终态 `candidate_generation_status` 由已校验、非空、已持久化的 incumbent digest 决定。
2. affected resume 从 incumbent 出发；只替换通过 binding/authorship 的受影响 section；失败 section
   保留旧正文并记 warning。失败 attempt 不得把 section checkpoint 或 ledger 写成空。
3. 原子提交条件：Candidate markdown、candidate checkpoint、section checkpoint、authorship ledger、
   writer result、quality report、execution record 共享同一 final candidate digest。任一层对不上
   则不提交新组合，回退到上一 incumbent。
4. 无合法 incumbent 才 `blocked` + `candidate_available=false` + 非 0。
5. `run_authoring_replay.py` 的 `writer_status`、`blocked_reason`、`resumed_section_ids`、
   `exit_code` 取 callback **之后** 的 result。第一轮 `incomplete` 不得掩盖 callback 后 `blocked`。
6. 退出语义写入 execution record：有 incumbent 且仅有 review/quality warning → 0；无 Candidate →
   非 0。记录必须能解释，禁止「正文 blocked、exit 沿用 stale success」。

#### 回归（必须全部新增，不得靠删断言变绿）

- 三节 incumbent + 两节 resume 全失败：最终仍三节，digest 与 resume 前相同。
- 一节 resume 成功：只有该节 digest 变，其余节与 ledger 仍绑定 incumbent 其余部分。
- candidate checkpoint 非空且 `accepted=[]`：`candidate_generation_status=generated`，
  `status=incomplete`（若仍有质量/callback 缺口），不是 `failed`/`blocked`。
- 无 incumbent：保持 `blocked`，exit 非 0。
- 第一轮 incomplete、callback 后 writer blocked：execution record 与 exit 反映 callback 后状态。
- 默认 `FROZEN_ARTIFACTS` / optional copy 含 derived-authoring 名 → 测试失败。
- 无 `--reuse-authoring-callbacks` 时复制旧 callback → 测试失败。
- `--rebuild-authoring` 在无独立入口时 → `authoring_rebuild_entry_unavailable`，且未复制旧 plan/cards。
- manifest 缺 replay script / profile / frozen input digest → fail closed。
- `_write_result_only` 早退 blocked + 磁盘已有 Candidate → 仍 generated/available（不得回退 r4 修复）。

验证命令（WP0 只跑这些，不跑全量 suite，不跑 live）：

```bash
python -m pytest -q \
  tests/test_agentic_candidate_verified_split.py \
  tests/test_agentic_replay_execution_record.py \
  tests/test_agentic_publication_method_writer.py
python -m compileall -q src tests
git diff --check
```

#### WP0 验收（Codex 只读；不是 §6.1）

PASS 当且仅当：

1. focused tests + `compileall` + `git diff --check` 记录在 `.agent/implementation.md`，exit 0。
2. LinearRAG 式 fixture：Candidate markdown、candidate checkpoint、section checkpoint、ledger、
   writer result、execution record 绑定同一非空 digest。
3. clean replay 默认 copy list 不含 derived-authoring；旧 plan/cards/callback 不是当前 authoring 真值。
4. `_write_result_only` 行为保持；diff 不触及 Formalizer/Concept compiler/Writer prompt。
5. 未宣称 publication_ready、D5 或正文质量提升。

BLOCKED / 停回 Codex：需要改 authorship gate、需要改 Architect 才能 rebuild、或必须把新字段默认空
以吞掉旧 artifact。

### WP1：重建 Story → Concept → section content contract

负责文件：

- `src/code2paper/agentic/intent_compiler_v2.py`
- `src/code2paper/agentic/method_concept_card_models.py`
- `src/code2paper/agentic/method_concept_card_compiler.py`
- `src/code2paper/agentic/writer_view_projection.py`
- `src/code2paper/agentic/method_architect.py`
- `src/code2paper/agentic/method_argument_models.py`
- `src/code2paper/agentic/method_product_models.py`
- `tests/test_agentic_intent_compiler_v2.py`
- `tests/test_agentic_method_concept_cards.py`
- `tests/test_agentic_method_architect_product_readiness.py`

代码动作：

1. 删除 96 字符 raw title truncation 对 semantic authority 的作用；Story 持久化完整 author statement。
2. Architect 不再把截断 statement 当最终 heading。向 Writer 提供 reader question、primary concept 和
   heading constraints；最终 `heading_text` 必须由 Writer 产生。
3. heading validator 检查长度、括号/引号闭合、结尾悬空介词/连词、非 headings-only；失败返回 Writer
   owner repair，不做 harness lexical patch。
4. 将 Concept → Story 从默认 bool 升级为 digest-bound `realized_story_node_ids`。author-intent 通过显式
   story ID 绑定；repository-positive 通过 exact obligation/fact/claim 关系绑定。模糊匹配只能提出
   review candidate，不能授权绑定。
5. 在 `SectionArgumentGraphV1` 内编译唯一的 section content contract，明确
   primary/supporting/audit-only concepts、dataflow、formula 真值、稀疏 moves 和 open slots；
   `WriterViewV1` 只能从它投影，不得创建第三份“本节该写什么”的权威。
6. 每个 section 必须有 formula 真值：非空 `formula_obligation_ids`，或显式 `not_applicable` 及原因。
   只留空字段会让 Slice 3A 把 R5 的空 Formalizer 输出改名为成功的 `not_applicable`。
7. WriterView 排序和 token budget 先服务 primary story concepts，再服务 supporting implementation；
   audit-only 永不进入正向 Writer 输入。
8. 删除用 `MA-Sx:intent:unit` 和 generic design objective 临时合成故事节点的 authority 作用；使用真实
   story node IDs 与完整 author statement。
9. required move 由 section scientific role 选择；多个 move 可以共享同一内容 witness，但必须显式绑定。
   不再给每节默认追加 limitations。

必须新增的回归：

- 长 statement 不被切成 `vulnerable to`、`B/C with`、`the Transformer` 等悬空标题；括号保持闭合；
- 中文、英文、破折号、括号和无空格长串都不发生中间字符 authority 丢失；
- primary story card 的 story IDs 进入 digest，旧缺省 false 不能悄悄通过 current schema；
- supporting guard 数量很多时，primary concepts 仍排在 WriterView 前部且保持 required；
- audit concept 不得进入 allowed positive set；
- Motivation 不会无依据地被要求 inference/equation/training 全套 moves；
- 缺失 primary concept 时 plan 明确产生 owning open slot，而不是 generic limitation。
- 每节 `formula_obligation_ids` 非空，或带原因的 `not_applicable`；禁止默认为空。

WP1 退出条件：对三个冻结 Research 根只做 deterministic authoring rebuild 时，section 数量/order 与完整
story spine 一致；每节至少有一个 primary story concept 或一个显式 blocking open slot；每节有 formula
真值；不存在残句 title。

### WP2：建立 Writer concept witness 与 exact final binding

依赖：WP1 必须先 PASS。不得在旧三节 plan、`realizes_story_node=false` 的 cards 上提前收紧 WP2；否则
只能得到更诚实的零覆盖，不能证明当前 Story/Concept 主链有效。

负责文件：

- `src/code2paper/llm/response_schemas.py`
- `src/code2paper/llm/section_writer.py`
- `src/code2paper/agentic/publication_method_writer.py`
- `src/code2paper/agentic/publication_relevance.py`
- `src/code2paper/agentic/final_text_claims.py`
- `src/code2paper/agentic/text_evidence_validator.py`
- `src/code2paper/agentic/publication_quality.py`
- `tests/test_llm_section_writer.py`
- `tests/test_agentic_publication_method_writer.py`
- `tests/test_agentic_final_text_trust.py`
- `tests/test_agentic_method_proposition_vertical.py`
- `tests/test_agentic_writer_paper_language_quality.py`

代码动作：

1. 新增 `heading_text`、`rendered_concept_keys`、`deferred_concept_keys` 与 typed unresolved points。
2. closed schema 将 concept keys 限制为 section allowed set，将 completed moves 限制为 contract moves。
3. 任何 required primary key 必须处于 rendered 或 deferred，二者互斥；静默缺失为 owner content failure。
4. 生成 sentence-scoped content witness，并把它持久化为 validation artifact。
5. 将 `_concept_claim_ids()` 的 obligation-wide expansion 从 final validation、quality、move proof、Verified
   路径移除；统一调用 `publication_relevance.py` 的 exact relation API。
6. 一个 supported sentence 只能取得其 exact concept binding 下的 claims/facts；同 obligation 的邻接
   claims 不得自动授权。
7. lexical/semantic aligner 只产生候选关联；反向验证没有 exact witness 时不计 coverage。
8. Candidate author-intent sentence 可有 caveated witness，但不得借此进入 Verified；Verified positive
   仍要求冻结 repository facts/claims 与 final atomic span 的反向验证。
9. Editor/Rewrite 改动任何 witness span 后必须重新计算 final claims、authorship 和 witness；禁止沿用旧通过。

必须新增的负例：

- 同一 obligation 下 `guard` 与 `core transformation` 两个 claims，只写 guard 时 transformation coverage=0；
- Writer 声称 rendered concept 但正文无对应 span，不得通过；
- 正文语义匹配但 concept 没有 exact claim/fact binding，不得进入 Verified；
- caveated author-intent 写入 Candidate 后仍不产生 repository-positive claim；
- Editor 改写越过 section/witness 边界时 fail closed；
- 多个 moves 共享同一 span 时，只允许 contract 明确列出的映射。

WP2 退出条件：quality 报告中的每一个 supported content/move 都能反查到
`final span → concept → exact claim/fact/equation`；删除任何一环都会 deterministic fail。

WP2 收紧后，旧的 obligation-wide 虚高 recall 和 move coverage 预期会下降。这是正确的基线校正，
不得通过删除 required moves、把 primary concept 改为 optional、过滤 final claims 或降低 denominator
把指标恢复到 R5 水平。

### WP3：分两片重建 equation 选择与 Formalizer 合约

负责文件：

- `src/code2paper/agentic/equation_claims.py`
- `src/code2paper/agentic/formalization_agent.py`
- `src/code2paper/agentic/writer_research_router.py`
- `src/code2paper/agentic/publication_method_writer.py`
- formula/relevance product models
- `tests/test_agentic_equation_claims.py`
- `tests/test_agentic_formalization_guards.py`
- `tests/test_agentic_publication_method_writer.py`

Slice 3A 是先执行的最小公式闭环。它依赖 WP1 已经给出每节 formula 真值；若 WP1 字段仍为空，本切片
不得把空输出判为 `not_applicable`。只做以下动作：

1. Formalizer schema 改为 rendered/unresolved/not_applicable discriminated union；WP1 已选出 required
   formula obligation 时，`{section_id}` 和空 packages 不是合法成功。EBCAR 的 generic `add` 回落到
   `-pos_sim + logsumexp(all_sims)` 属于 3A fixture，不必等 3B。
2. `_execute_formalization_route()` 校验 request/section/obligation/package 四元绑定与 package validation；
   删除“存在全局 `formalization_result_v1` digest 即 fulfilled”的逻辑。
3. 修正 `select_core_equations()` 的 descriptor 短路：descriptor 仅为 generic `add/mul/matmul` 时，回落检查
   已有 assignment target、exact relation 和 fact predicate；普通 shape arithmetic 仍不能单独入选。
4. Formalizer package 继续执行现有 operands/operators/numbers/dimensions 与理论升级 guard；不得为修复
   空结果把普通算术加入 `_CORE_EQUATION_DESCRIPTORS`。
5. Slice 3A 不建立新的通用 `mechanism_kind` 本体，也不尝试一次覆盖所有论文公式类型。

Slice 3B 只有在 Slice 3A 的跨项目 fixtures 证明现有 relation/predicate 不足时才进入：

1. 根据 `SectionArgumentGraphV1` 中的 section content contract 补强 formula obligations；没有 obligation 的
   普通算术继续过滤。
2. 保留原始表达式、operands、assignment target、relation facts 和 source spans；如确有必要，只增加
   窄、版本化、可由 exact relations 推导的 mechanism role，不建第二套公式本体。
3. unresolved 进入具体 formula slot callback/review，不能转成 generic limitations。
4. Writer 只接收 accepted package 或 typed unresolved；不得从 raw AST 自行创造论文公式。

必须新增的回归：

- 任意 `x+y`/shape arithmetic 不产生 core formula；
- 具备 assignment/dataflow/loss relation 的 `-pos_sim + logsumexp(all_sims)` 能形成 loss obligation candidate；
- obligation 存在时 `{section_id}` 被 schema 拒绝；
- obligation 证据不完整时生成 typed unresolved 而非假公式；
- 其他 section 的 package、全局 result digest、未验证 package 都不能 fulfill 当前 callback；
- Formula package 新增数字/operand/operator/理论性质时继续拒绝。

Slice 3A 退出条件：required formula obligation 下不存在合法空白结果；全局 digest、foreign package 和
generic arithmetic 都不能形成假 fulfilled。Slice 3B 的退出条件才是每个 section formula obligation
恰有 rendered 或 unresolved 真值。两阶段的公式 coverage 都只能由 accepted formula witness 贡献。

### WP4：先封住 callback 假 fulfilled，再建立 semantic delta

负责文件：

- `src/code2paper/agentic/research_models.py`
- `src/code2paper/agentic/method_architect.py`
- `src/code2paper/agentic/writing_callback_fulfillment.py`
- `src/code2paper/agentic/research_graph.py`
- `src/code2paper/agentic/research_nodes.py`
- `src/code2paper/agentic/writer_research_router.py`
- `tests/test_agentic_autonomous_callback_fulfillment.py`
- `tests/test_agentic_research_graph_callback_continuation.py`
- `tests/test_agentic_graph_research_loop.py`
- `tests/test_agentic_d4_owner_fault_injection.py`

Slice 4A 只做三项低风险硬防线。4A.1 与 4A.2 不依赖 Formalizer，WP2 PASS 后可与 3A 并行；4A.3
必须等 3A 的四元绑定。三者都不得并进 WP0 或 WP1。

1. 请求生成端必须持久化 exact baseline span IDs；无法从 digest-bound 引用确定还原时，返回
   `baseline_binding_missing`，不得把 `frag-*` 启发式解释成空 baseline 后放行。
2. concept judgment 限制到 request 声明的 target concept；只命中其他 concept 时记录 off-target，状态保持
   open，不得 fulfilled。
3. formalization route 复用 Slice 3A 的四元绑定；全局 Formalizer digest 不能满足当前 callback。

Slice 4A 不引入 canonical fact ontology，不修改完整 Research planning，也不声称 callback 已具备语义闭环。
它的目标只是让 R5 中已经确认的三类假 fulfilled 立即 fail closed。

Slice 4B 在 4A fixtures 稳定后再实现完整 semantic delta：

1. callback request 使用 target story/concept/formula IDs、mandatory slots 与 exact baseline；从 owning move
   生成，不再把所有 gap 降维成 `limitations_or_mismatch`。
2. 引入可审计的 canonical fact fingerprint，跨 obligation/request ID 去重；重新编译旧 evidence 不算
   新信息。若无法可靠区分“旧证据换 ID”和“真实新关系”，停止并返回 Codex，不做近似放行。
3. owning validator 逐 mandatory slot 验证 exact relation，并返回 satisfied/remaining。
4. partial answer 保持请求 open，合并 satisfied slots 后只研究 remaining slots；防止重复无变化运行。
5. merge 后按 Concept → relevance → formula → placement 顺序重编；只有 digest 与 semantic delta 均非空
   才 resume。
6. 只 resume affected sections；历史 incumbent 的其他 sections 不重写。
7. 收紧 Research Manager action schema：每回合一个合法 action；terminal action 不携带 tools；parallel
   tools 必须属于同一 move。schema/recovery 错误改变策略后再试，不做 unchanged retry。

Slice 4A 必须先新增的负例：

- 归一化问题返回 padding fact，状态保持 open/off-target；
- attention-mask 问题返回 positional encoding，状态保持 open/off-target；
- baseline refs 无法解析，不得 baseline_count=0 后继续通过；
- 全局 Formalizer digest 不得满足当前 section/obligation。

Slice 4B 再新增的负例：

- 同一事实换 obligation ID，不算 information gain；
- 只填 2/3 mandatory slots 时为 partial，remaining slot 被保留；
- Research termination incomplete 且 remaining 非空时不得 full fulfilled；
- exact target relation 新增时，更新 target card/placement 并只 resume affected section；
- callback merge 没有 authoring semantic digest 变化时停止 no_information_gain，不重跑 Writer。

Slice 4A 退出条件：unbound baseline、off-target concept 和全局 Formalizer digest 三类路径均不能
fulfilled。Slice 4B 退出条件：每个 fulfilled callback artifact 都能展示 request mandatory slots、
baseline canonical set、new exact relations、target concept 更新、受影响 section 和重编后的 digest 链；
任一缺失都不能 fulfilled。

### WP5：让 Writer/Editor 围绕科学机制组织正文

依赖：WP1、WP2、Slice 3A 和 Slice 4A 必须先 PASS。不得在旧 plan/cards 或平铺低层 Concept payload 上
提前调 Writer prompt；否则模型只会用 caveated 故事句形式化地应付“primary mechanism”要求。

负责文件：

- `src/code2paper/agentic/publication_method_writer.py`
- `src/code2paper/llm/section_writer.py`
- `src/code2paper/llm/writer_section_repair.py`
- `src/code2paper/agentic/cross_section_editor.py`
- `src/code2paper/agentic/rewrite_agent.py`
- `src/code2paper/agentic/publication_quality.py`
- `tests/test_agentic_writer_paper_language_quality.py`
- `tests/test_llm_writer_section_repair.py`
- `tests/test_agentic_candidate_verified_split.py`

代码动作：

1. Writer prompt payload 的首要结构是 reader question、ordered primary concepts、dataflow、accepted formula
   与 caveated/open slots；低层 supporting facts 放在其所属 primary concept 下，不再平铺。
2. 要求 section 至少形成输入/对象 → 核心变换 → 条件/公式 → 输出/下游使用中由 contract 指定的链；
   不用固定段落模板，也不要求每节拥有所有槽位。
3. guard、fallback、shape、assert 只能作为主机制的边界或实现佐证；不得在存在 primary mechanism 时成为
   段落中心并独占 move coverage。
4. Writer 生成 `heading_text`；不复制 structural title。heading 失败走同 owner 的 scoped repair。
5. content repair 按 missing primary concept/move/formula witness 定位；representation repair 只处理 JSON、
   截断、重复等表示损伤，两类 trace 分开。
6. Editor/Rewrite 只修明确的 issue-scoped deficits，提交新的 concept/move witness；无进展时保留 incumbent
   和 review item，不把正文削成容易过 gate 的碎片。
7. publication utility 同时报告 story primary coverage、dataflow continuity、formula obligation coverage、
   section coherence 和 reproducibility；它们不影响 repository safety verdict 的真值。

必须新增的行为测试：

- primary mechanism 和多个 guards 同时存在时，正文首个实质段落围绕 primary mechanism；
- supporting fact 不得单独满足 core transformation move；
- 作者意图缺 repository support 时可写成清晰 caveated Candidate，而不是只输出“cannot verify”；
- heading 不是 YAML statement 的截断前缀，且没有悬空语法；
- repair 只收到具体 missing witnesses，并在无进展时停止；
- Candidate 可编辑性失败不影响安全 gate，安全失败也不能被高可读性覆盖。

WP5 退出条件：冻结 fixture 上的 Candidate 每节都能由 content witness 重建出 section-specific
argument graph；删除代码 guard 段不会删除核心机制，删除核心机制段则 primary coverage 必须下降。

### WP6：静态集成、DyG canary、其余两项矩阵

在 WP0、WP1、WP2、Slice 3A、Slice 4A、WP5 以及由前序证据判定必需的 3B/4B 全部形成 PASS handoff
后，OpenCode 才进入 WP6。WP6 分三个 gate，不能把三项目同时作为第一次 live 证明。Codex acceptance
阶段只读现有 diff、`.agent/implementation.md` 和冻结产物，不重跑测试或 API。

#### Gate 6A：静态集成

静态命令建议：

```bash
python -m pytest -q \
  tests/test_agentic_intent_compiler_v2.py \
  tests/test_agentic_method_concept_cards.py \
  tests/test_agentic_method_architect_product_readiness.py \
  tests/test_agentic_equation_claims.py \
  tests/test_agentic_formalization_guards.py \
  tests/test_agentic_autonomous_callback_fulfillment.py \
  tests/test_agentic_research_graph_callback_continuation.py \
  tests/test_agentic_publication_method_writer.py \
  tests/test_agentic_candidate_verified_split.py \
  tests/test_agentic_final_text_trust.py \
  tests/test_agentic_writer_paper_language_quality.py \
  tests/test_agentic_replay_execution_record.py \
  tests/test_llm_section_writer.py \
  tests/test_llm_writer_section_repair.py
python -m compileall -q src tests
git diff --check
```

是否运行完整 `python -m pytest -q` 由当前主线 milestone 和实现影响面决定；如运行，必须记录准确命令、
退出状态、摘要和代码 digest，不能只报测试数量。

#### Gate 6B：单项目 DyG canary

Gate 6A 通过后，先且只运行一个 DyG-Mamba frozen-Research authoring replay，使用 AGENTS.md 当前指定
runtime：

- Base URL：`http://127.0.0.1:8003/v1`
- Model：`qwen36-27b-nvfp4`
- Profile：`tests/live/profiles/qwen36_vllm_budgeted.example.env`
- Context：131072

输入只使用 `.tmp/c2p-stage1-canary/run-dyg/` 的 Research authority，输出必须是新的 task-specific
`/tmp` 目录。运行前记录 health、models、model identity、queue/KV-cache 和 output root；运行中监控
waiting、cache pressure、OOM、abort。该 canary 必须串行，不把资源争用混入质量结论。不得在代码和
输入不变时重复失败 run 等待“幸运样本”。

建议 replay 明确使用：

```text
--rebuild-authoring
--no-reuse-authoring-callbacks
--persist-authoring-rebuild-manifest
```

这些 flag 名称可以按现有 CLI 风格调整，但语义不得改变。

DyG 必须单独通过 §6.1 的通用不变量和 §6.2 的 DyG 人工审计点。失败时停止，不启动另外两项；把问题
返回 owning slice 做 in-direction repair。若 repair 改变代码或协议，旧 DyG 结果不再证明新状态，必须
在新 fresh root 上重新取得一次 DyG canary，而不是沿用旧 artifact。

#### Gate 6C：LinearRAG 与 EBCAR 矩阵

只有 Gate 6B PASS 后，才在与通过的 DyG 完全相同的代码 digest、profile、replay 协议和 authoring
冻结边界下，依次串行运行：

1. `.tmp/c2p-stage1-canary/run-linearrag/`；
2. `.tmp/c2p-q5-batch3/run-ebcar-research/`。

两项分别使用新的 task-specific `/tmp` 根并单独验收。DyG 只是第一道 canary，不能替代最终三项目
矩阵；LinearRAG 必须覆盖丢节和 incumbent 一致性，EBCAR 必须覆盖虚高 recall、loss equation 与
attention callback 对题性。任一项目暴露需要改代码的问题时，本轮矩阵终止；修复后重新建立同代码状态
的三项目证据，不拼接不同 code/protocol digest 的结果。

## 6. 冻结验收协议

切片验收只看该切片退出条件。§6.1–§6.3 是 WP6 三项目矩阵的硬不变量，不是 WP0–WP5 的逐片清单。
WP0 对照 §5 WP0「验收」；WP1 对照 WP1 退出条件；以此类推。Codex 不得用 Motivation 是否回到
LinearRAG、或 equation_coverage>0，来判定 WP0。

### 6.1 WP6 三项目通用硬不变量

Gate 6C 的三项都必须满足：

1. frozen manifest 中旧 `authoring_projection`、Concept、plan、formula package、callback 没有被复制为
   当前 authoring 真值；新产物有完整 digest lineage。
2. story node 数量/order 与作者意图一致；任何丢失 section 都有显式、typed、blocking 原因。
3. 不存在截断残句 heading、未闭合括号、单独介词/连词结尾或 `Offline` 这类失去辨识度的标题。
4. 每个 section 有 primary content contract；每个 required move 绑定 exact acceptable witnesses。
5. 每个 rendered primary concept 有 final sentence witness；每个 deferred primary concept 有 typed owner。
6. 每个 formula obligation 为 rendered 或 unresolved；不允许默认空成功。
7. 每个 fulfilled callback 逐槽证明 semantic delta；off-target/旧事实重挂不能 fulfilled。
8. Candidate、checkpoint、section state、ledger、quality、result、execution record 共享同一 final digest。
9. Verified 正向实现事实仍通过 repository evidence + reverse validation；Candidate-only author intent 不泄漏。
10. 没有 deterministic content repair、项目特判、原文注入或 gate 弱化。

### 6.2 WP6 三项人工科学质量审计点

以下只用于验收“论文故事是否被当前证据和作者意图正确组织”，不得写进 production logic：

- DyG-Mamba：Candidate 应连续解释四类时间输入、时间编码/状态空间变换、适用的 Δ/A/B/C 关系或其
  typed unresolved、跨通道融合、top-k/下游预测与关键复杂度边界；不能以 padding/assert 为主线。
- LinearRAG：Candidate 应包含 Motivation/Overview，并连续解释语料到异构图、边/桥接权重、种子/局部
  激活、传播或 PPR、混合初始化与检索输出；不能退化为 config/shape 列表。
- EBCAR：Candidate 应连续解释 augmentation、embedding/context 交互、hybrid attention、InfoNCE 类目标
  或其 typed unresolved、训练到 inference 的一致数据流；不能用 positional encoding 替代 attention mask。

上述内容可以分别落在 repository-positive、author-intent caveated 或 unresolved lane；不要求把作者陈述
伪装成代码事实。验收看的是机制链和 authority 是否完整，而不是与原文逐字一致。

### 6.3 WP6 质量判定

WP6 通过的最低产品条件是“三项都有非空、digest 一致、机制完整度显著提升的 editable Candidate，且
所有不确定内容 authority 可见”。Verified 可以较短，甚至因证据不足维持 incomplete；不得为了接近
原 Method 长度而扩大 Verified。WP0 完成不触发本条。

不得使用下列假通过：

- required moves 数量直接砍到指标变好；
- 把缺失 primary concept 标 optional；
- 空 formula 改名为 not applicable；
- callback 只因生成 artifact 就 fulfilled；
- 过滤 final claims 直到 reverse validation 无失败；
- 以 Candidate 文件存在掩盖 checkpoint/ledger digest 不一致；
- 仅比较字符数、关键词或与原文相似度。

## 7. 实施完成后的证据交付

OpenCode 在每个获准切片的 `.agent/implementation.md` 中按仓库流程记录，但不得修改本方案或权威设计
文档。每个切片交付必须包含：

1. 精确 diff 范围和每个工作包的实现摘要；
2. 所有 schema/version/migration 决策；
3. focused/full/static 命令、退出状态和摘要；
4. 每项 fault test 对应的不变量；
5. 未解决问题及其 owner/authority lane；
6. 对 dirty baseline 中无关用户改动的保留说明。

只有 WP6 交付再增加：live 前 runtime 健康与资源记录；先 DyG、后 LinearRAG/EBCAR 的三个 fresh root；
execution manifest 和最终 artifact digests；每项 primary content、formula、callback、incumbent 验收表。

每个切片实现完成后停止。Codex 按 AGENTS.md 做只读 acceptance：检查 authority、一致性、diff、测试
记录和该切片要求的冻结产物，给出 PASS、REPAIR 或 BLOCKED；不在 acceptance 阶段重跑测试、
benchmark、模型或真实 API。PASS 只授权进入路线图中的下一切片，不等于整条 Method 主线完成。

## 8. 执行优先级与停止条件

执行优先级为：

1. 现在只做 WP0（§5 任务规格）。转化 `.agent/task.md` 时只复制 WP0 白名单、动作、回归、验收；
   不要把后序切片写进同一任务。
2. WP1 重建 Story/Concept/`SectionArgumentGraphV1` contract，再由 WP2 建立 exact witness；两片不得
   合并或倒序。
3. Slice 3A 封公式假成功；4A.1/4A.2 可与 3A 并行，4A.3 等 3A；3B/4B 范围由证据决定。
4. WP5 最后调整 Writer/Editor 行为，不在旧契约上提前调 prompt。
5. WP6 先静态集成，再跑 DyG canary，最后在同代码/协议下跑 LinearRAG 和 EBCAR。

出现以下任一情况立即停止并返回 Codex：

- 需要让原始 `paperdraft.md`、项目路径/符号/已知答案进入 generic production logic；
- exact concept/claim/fact 关系无法在现有 authority model 内表达，需要改变架构权威；
- 为保持 backward compatibility 必须把 current schema 的新字段设为默认空并静默接受旧 artifact；
- Formalizer 只能靠 deterministic harness 补写科学公式才能通过；
- callback semantic delta 无法区分旧证据重挂与真实新关系；
- Candidate incumbent 的原子一致性需要破坏现有 final-integrity/authorship gate；
- 实现与当前主线文档产生实质冲突。

本方案的核心成功标准只有一个：系统必须能证明“每节写出了哪些科学机制、这些机制由什么 authority
支持、缺失机制回到了哪个 owner”，而不再只证明“模型返回了合法 JSON、正文里出现了若干可验证代码词”。
