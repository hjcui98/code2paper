# Code2Paper Agentic Refactor Final Design

> **Agent 自主修复原则（规范性）：**规则层发现格式、schema、证据或内容错误后，
> 必须形成 typed repair issue 并返回 owning Agent 做有界重试；禁止用静默过滤、
> deterministic fallback 冒充成功、放宽硬门或降低义务覆盖来换取通过。详见
> `docs/agentic_error_feedback_and_self_repair_principle.md`。

> 2026-07-19 reassessment：本文保留为 M0--P3 和早期 P4 的设计/实现历史。V2 evidence-first 原则继续有效，但当前目标已进一步升级为通用 `CodeBehaviorGraph`、LLM Research Supervisor、细粒度 LangChain 工具和局部补证循环。规范性设计见 `docs/agentic_robust_langgraph_research_writing_design_2026-07-19.md`，执行见 `docs/agentic_method_quality_next_execution_plan_2026-07-19.md`。

更新时间：2026-07-16
状态：在原有两轮迭代基础上，完成第三、第四轮“阅读现状 → 规划设计 → 批判审计”后的收敛版。

## 1. 一句话总目标

把 Code2Paper 从固定 Python 多阶段流水线升级为作者意图驱动、代码证据约束、LangGraph 编排的可决策研究写作 Agent：LangChain 负责可组合、可审计的工具协议，LangGraph 负责有预算的检索、修复、写作和图规划决策，evidence/validator/invariant 负责保证最终方法文本中的每个原子 claim、方法图中的每个节点与每条边，都能回溯到当前代码快照中的直接证据。

这里的“回溯”不能只表示“挂了一个存在的 evidence ID”，而必须同时满足：

1. evidence ID 对应不可变的代码快照、文件、符号、行区间和精确证据片段哈希；
2. claim 或图元素的实际语义由这些代码片段直接支持；
3. 绑定是从最终文本/最终图反向验证得到，而不是写作前 scaffold 的位置式猜测；
4. 最终渲染产物与通过审计的文本/图契约一致。

## 2. 最终结论先行

当前仓库已经有真实的 agentic 基座，不需要推倒重写：

- `src/code2paper/agentic/graph.py` 使用真实 `StateGraph`，存在 coverage、analysis repair、evidence sufficiency、authoring planner、revision、figure planner、invariant audit 等条件路由。
- 模型在多个决策节点只提交结构化 proposal，之后由 deterministic fallback 和 safety merge 决定最终 route，这个方向正确。
- 作者意图检索计划、symbol index、coverage/rescan、evidence freeze、claim verification、authoring context/plan、traceability ledger、readiness/evaluation report 都已有实现。
- 针对性的 88 个 agentic/traceability/figure/runner 测试当前通过，说明这套架构不是只有文档。

但它还不能宣称已经满足最终科研可信度目标。最关键的差距不再只是 T007 的 excluded claim 泄漏，而是“引用完整性”被误当成“语义可证性”：

- `claim_verifier.py` 主要验证 claim 声明状态、evidence ID 是否存在，没有验证 claim 文本是否被对应代码片段语义蕴含。
- `method_claim_map.json` 由 outline/scaffold 在正文生成前构造，并按段落位置附着；缺少精确映射时会回退到第一个 supported claim 或第一个 known evidence。这会产生结构合法但语义错误的伪绑定。
- traceability ledger 和 invariant audit 当前主要检查 ID 是否已知、是否被排除、是否在 plan 内，不能识别“合法 ID 被贴到无关句子上”。
- figure edge 默认按 stage 顺序生成，edge evidence 是两端节点证据的拼接，不能证明代码里真实存在该数据流、控制流或依赖关系。
- agentic `rendering` stage 目前只写 figure plan 和 rendering manifest，并不真正生成、再审计方法图；completion report 甚至可把“plan 通过”视为 method figure 完成。
- pre-render invariant 在渲染前运行，因此即使 plan 安全，也没有对实际 PNG/SVG 中新增标签、箭头或语义漂移做 post-render gate。
- LangChain 当前主要是 9 个 legacy stage wrapper 的 `StructuredTool` 导出与 manifest，还不是可由 Agent 动态组合的细粒度研究工具集。
- LangGraph 没有 checkpointer/resume；`AgenticRunState` 是 Pydantic 模型，但运行时仍使用 `StateGraph(dict)` 和全量路径字典。
- `pyproject.toml` 没有 `agentic` optional dependencies，也没有 agentic run/benchmark console entrypoint；README 仍以固定 Phase 1-5 流程为主。
- 当前全量测试在 collection 阶段被 `DEFAULT_FIGURE_IMAGE_MODEL` 缺失阻塞；这与上述架构缺口不同，但说明发布基线尚未收敛。

因此最终实施顺序必须是：先修“最终输出语义闭环”，再增加更多 Agent 自由度。框架完成度、artifact 数量和路由数量都不能替代科研可信度。

## 3. 不可改变的可信度不变量

### I1. 作者意图与代码证据严格分权

作者意图决定系统优先查什么、如何组织、哪些名称应保留；代码证据决定系统最终允许写什么、画什么。作者 YAML、README、注释和领域常识只能作为检索线索或软证据，不能单独支撑方法事实。

### I2. 证据必须绑定代码快照

每个硬证据至少包含：`repo_snapshot_id/project_hash`、相对路径、符号、行区间、精确 excerpt hash、source type、evidence strength。运行结束时重新计算的项目 hash 不能替代 freeze 时的快照绑定。

### I3. Claim 必须是原子且语义可验证的

每条 claim 应只表达一个可审计事实。`supported` 不等于“有一个已知 ID”，而等于 claim 的主语、操作、对象、条件和限定词均可由绑定代码证据支持。

### I4. Partial claim 只能携带已支持片段

`partial` 只有在同时记录 `supported_fragment`、`unsupported_fragment`、`required_qualifiers` 和直接 evidence 时才能进入写作。正文只能写已支持片段并带限定词；不能把原始宽泛 claim 原样放行。

### I5. 最终文本反向建链

正文生成后必须重新切分句子/原子 claim，逐条验证并生成 trace。写作前 outline、prompt claim IDs 或模型自报引用只能作为候选，不能直接成为最终 ledger。

### I6. 禁止盲目重映射

不能因为一个段落引用了 excluded claim，就把它机械替换成任意 allowed claim/evidence。只有最终句子经过重新验证后，才能写入新的绑定；否则必须重写、回分析或阻塞。

### I7. 图节点和图边分别取证

节点证据不能自动证明边。每条边都必须声明关系类型，例如 `calls`、`passes_tensor`、`configures`、`precedes_by_control_flow`、`updates`，并绑定直接支持该关系的代码/配置/脚本证据。

### I8. 审计最终产物，不只审计计划

文本 formatter、LaTeX 转换、figure renderer、PaperBanana 或其他后端都可能引入漂移。pre-render gate 只授权渲染；post-render/post-format gate 才授权 finalize。

### I9. 模型只能提案，不能签发可信度

模型可以排序、分组、解释缺口、提出 route、规划段落和图布局。模型不能把 unknown 改成 supported，不能扩展 evidence 集合，不能绕过 validator，也不能自行把失败标成通过。

### I10. 所有循环都有预算、终止条件和失败产物

检索、证据修复、写作修复、图修复分别计数。预算耗尽时应输出具体 gap 和 artifact 后阻塞，不能无限循环，也不能为了完成率降低 gate。

### I11. Artifact 必须防陈旧和串跑

每个下游 artifact 记录输入 artifact digest、schema version、tool version、model call ID。输入变化后旧 validator/ledger/plan 自动失效，不能仅因文件存在就继续。

### I12. “可追溯”不夸大为形式化证明

本系统能够提供可审计、可复验的实现证据链，但不应声称对算法正确性、运行时性质或理论结论给出了数学证明。代码静态证据不充分时，应缩小 claim 或引入明确标注的运行证据。

## 4. 本轮阅读与核验范围

第三、第四轮直接复核了以下当前实现，而不是只依赖旧 handoff：

- 编排与路由：`agentic/graph.py`、`graph_topology.py`、`graph_*_nodes.py`、`routing.py`、`decision_*`。
- 工具与契约：`contracts.py`、`tool_specs.py`、`tools.py`、`langchain_tools.py`、`contract_audit.py`。
- 检索与修复：`retrieval.py`、`legacy_intake_stage_tool.py`、`evidence_repair.py`、`rescan_evidence_freeze.py`。
- evidence 与 claim：`core/schemas.py`、`pipeline/stages/evidence.py`、`claim_verifier.py`、`evidence_sufficiency.py`。
- 写作：`legacy_authoring_stage_tool.py`、`authoring_constraints.py`、`authoring_context.py`、`authoring_plan*.py`、`pipeline/stages/authoring.py`。
- 图与渲染：`figure_planner.py`、`legacy_late_stage_tools.py`、`render_authorization.py`、`rendering/figures/backend_paperbanana.py`。
- 审计与交付：`traceability_ledger.py`、`invariant_audit.py`、`readiness_report.py`、`completion_report.py`、`runner.py`。
- 发布面：`pyproject.toml`、`requirements.txt`、`README.md`、`cli/agentic_run.py`、`cli/main.py`。
- 真实产物：`/tmp/code2paper-agentic-real-T007` 及 `.agent-team/evidence/` 中的外部复核记录。

核验结果：精选 agentic 测试 88 passed；全量 `pytest -q` 当前在 `tests/test_main_cli.py` collection 时因 `src/code2paper/cli/run.py` 导入不存在的 `DEFAULT_FIGURE_IMAGE_MODEL` 失败。最终迁移计划将“测试可收集、CLI 可安装运行”设为 M0 发布门槛。

## 5. 现状能力矩阵

| 能力 | 当前状态 | 真实评价 |
|---|---|---|
| LangGraph 条件编排 | 已实现 | 真正使用 `StateGraph`，不是伪流程图；但无 checkpoint/resume |
| 模型辅助路由 | 已实现 | proposal + deterministic safety merge 的模式正确 |
| 作者意图检索计划 | 已实现 | intent target、symbol/config/shell index、coverage/rescan 已较完整 |
| 检索反馈闭环 | 部分实现 | 有 plan/report/repair task，但 CLI 默认 evidence revision budget 为 0，且没有对应参数暴露 |
| LangChain 工具 | 过渡态 | 9 个 stage wrapper 可导出 `StructuredTool`；图仍直接调用 wrapper，缺少细粒度组合 |
| Evidence freeze | 已实现 | 有路径/符号/行号/hash；部分 ingestion 路径的 `excerpt_hash` 实际 hash 的是 summary，不是精确 excerpt |
| Claim verification | 部分实现 | 能防 missing/unknown ID；尚未做 claim-to-code 语义验证 |
| Authoring context/plan | 已实现 | 计划安全 merge 正确；正向 authoring view 仍可能暴露 excluded claim contract/stage claim |
| 正文 claim trace | 高风险过渡态 | scaffold/位置绑定，不是从最终正文抽取；存在任意 fallback evidence |
| 文本 invariant | 结构校验已实现 | 检查 known/forbidden/plan IDs，不能识别合法 ID 的语义错配 |
| Figure plan | 部分实现 | 节点有冻结 evidence；边和可变 label 缺少语义级验证 |
| Figure rendering | agentic 路线未闭环 | agentic stage 只计划并写 manifest；legacy fixed route 才调用 PaperBanana |
| Post-render audit | 未实现 | 不能保证实际图像没有新增元素 |
| Validation gate | 部分实现 | validation stage 会按 fidelity 阻塞；invariant 中却只检查 validation artifact 是否存在 |
| Completion report | 有实现但定义偏松 | figure plan 通过即可算 method figure，不要求 PNG/SVG/PDF 实际存在 |
| Packaging/docs | 未收敛 | 无 agentic extra/console entrypoint，README 仍是 legacy 主路径 |

## 6. 迭代一回顾：确认保留 agentic 主干

### 阅读结论

第一轮确认仓库已有 graph shell、stage tool contract、decision trace、claim verifier、authoring plan、figure plan、ledger 和 invariant audit。

### 设计结论

保留 `src/code2paper/agentic/` 作为迁移主干，用 adapter 包装旧 stage，逐步抽出细粒度工具，不推倒已有 pipeline。

### 批判审计

主要问题是 stage tool 太粗、README/packaging 偏 legacy，以及真实项目结论不能只听 handoff，必须直接读 artifact。

这个结论仍然成立。

## 7. 迭代二回顾：T007 authoring 泄漏

### 阅读结论

直接读取 T007 artifact 后，真实状态是 C1/C5 为 `unsupported`，authoring constraints 和 agentic authoring plan 已排除它们，但 Phase 5 仍通过完整 `MethodEvidence.claim_contracts`、stage packets、outline/scaffold 把它们重新带入 `method_claim_map`。

### 设计结论

提出 Authoring Input Projection、Authoring Plan Gate、Draft Writer、Claim Trace Reconciler 和 Authoring Repair Router。

### 批判审计

不能通过放宽 invariant 解决 T007。问题是旧 authoring view 与新 constraints 冲突，应该收紧 authoring success 定义。

这个判断正确，但“若只是 trace 误配则确定性重映射”的建议不够安全，已在第四轮中废止并替换为最终文本语义重验证。

## 8. 迭代三：从 ID 闭环推进到语义闭环

### 8.1 阅读现状

对 authoring、ledger、invariant 和 figure planner 逐函数复核后发现：

1. `apply_authoring_constraints()` 只过滤 `ClaimEvidenceMap`，没有过滤 `MethodEvidence.claim_contracts`、`stage_packets[].claim_ids/stage_claim`、outline 等正向写作输入。
2. `_outline_scaffold()` 与 `_normalize_draft_claim_map()` 仍以完整 claim contracts 为 known set；当没有匹配时可回退到首个 supported claim，evidence 为空时可回退到排序后的首个 known evidence。
3. 最终 LLM 文本不会重新产生结构化 atomic claim；grounding comment 只是按段落序号复用已有 scaffold。
4. fidelity validator 能发现无 grounding、unknown evidence、仅 soft evidence，以及 unsupported claim 的精确字符串泄漏，但不能发现 unsupported claim 的改写或允许 evidence 的语义错配。
5. traceability ledger 因此证明的是 referential integrity，而不是 semantic entailment。
6. figure plan 的顺序边由 `zip(nodes, nodes[1:])` 推断，edge evidence 来自 source/target evidence；这不足以证明关系。
7. 模型可改 node label，只要 stage/evidence ID 合法；label 自身没有 claim-level 审核。

### 8.2 第三轮设计

把 Evidence-Bound Authoring 从“输入过滤 + ID 对账”升级为完整的后验验证链：

```text
Authoring Projection
        -> Authoring Plan
        -> Draft Writer
        -> Final Text Segmenter
        -> Atomic Claim Extractor
        -> Claim-to-Code Semantic Validator
        -> Text Trace Builder
        -> General Validators
        -> Revision Router
```

同时把 Figure Planner 升级为 evidence-backed scene graph：节点、标签、边、边标签都必须有独立 claim/evidence binding。

### 8.3 第三轮批判审计

仅增加 `ClaimTraceReconciler` 仍可能形成“给不相关句子换一个合法 ID”的假闭环。最终 trace 必须由 final text 反向抽取后重建，旧 scaffold 只能提供候选对齐。

此外，单一 LLM judge 也不能成为科研可信度根基。语义验证要采用：

- deterministic 前置检查：证据存在、快照一致、证据强度合格、数值/配置/符号精确匹配；
- schema-constrained semantic verdict：只在给定 claim 和最小 evidence span 上判断，不允许补领域常识；
- fail-closed merge：verifier 不确定、冲突或缺证据时降级/阻塞；
- adversarial golden set 校准，必要时对高风险 claim 使用第二 verifier 或人工 review。

## 9. 迭代四：审计“更 Agentic”是否真的更可信

### 9.1 阅读现状

进一步复核运行、工具、发布和渲染链后发现：

1. graph 直接调用 `Code2PaperStageTool.invoke()`，LangChain `StructuredTool` 主要用于导出，Agent 还没有真正基于 tool readiness 动态组合细工具。
2. `StateGraph(dict)` 没有 typed reducers、checkpointer 或 resume key；长时间真实项目失败后必须重跑。
3. `max_evidence_revision_rounds` 在 state 和路由中存在，但 agentic CLI 没有暴露该参数，正常 CLI 路径始终使用默认 0。
4. invariant 的 `validation_after_authoring` 只检查 manifest/fidelity 文件存在，不检查 validation status 必须为 passed。
5. pre-render audit 发生在 rendering 前；rendering stage 没有实际调用 renderer，completion 又把 plan 当 figure deliverable。
6. `pyproject.toml` 没有 LangGraph/LangChain optional extra 和 agentic scripts；README 无 agentic 最小使用说明。
7. 当前全量测试 collection 已失败，说明继续增加新模块前必须恢复可发布基线。

### 9.2 第四轮修订设计

最终架构采用“三平面”分工：

1. **Decision Plane（LangGraph）**：管理状态、预算、分支、循环、checkpoint 和 human interrupt。
2. **Action Plane（LangChain tools）**：执行检索、读 span、构建 evidence、验证 claim、写作、渲染等有明确 schema 的动作。
3. **Trust Plane（evidence + validators + invariants）**：独立于 planner，决定 artifact 是否可进入下一安全域。

最终授权条件不是“Agent 说完成”，而是：

```text
author intent satisfied
AND code evidence semantically supports output
AND validators pass on final artifacts
AND artifact lineage/snapshot is intact
```

### 9.3 第四轮批判审计

这套目标设计仍有四个必须承认的边界：

- 语义 verifier 仍可能误判，因此需要校准集、风险分级和 fail-closed，而不是把 LLM verdict 当真值。
- 纯静态代码不能证明所有运行时行为；涉及动态 shape、随机分支、真实默认值时，应补受控 execution trace，或缩小 claim。
- “所有元素都有 evidence ID”可能被系统刷指标；必须测语义 precision，不能只测 ID coverage。
- 过早拆成几十个工具会增加复杂度。先抽出可信度关键工具，legacy stage wrapper 在迁移期继续作为 composite tool。

## 10. 最终目标架构

```text
Author YAML / Draft Intent
          |
          v
Intent Resolver -> IntentSpec + explicit priorities/forbidden scope
          |
          v
Retrieval Planner <------------------------------+
          |                                      |
          v                                      |
Code Search / Symbol Index / Span Read Tools     |
          |                                      |
          v                                      |
Coverage Critic ---- missing targets / budget ---+
          |
          v
Analysis + Evidence Graph Builder <--------------+
          |                                      |
          v                                      |
Evidence Snapshot + Atomic Claim Contracts       |
          |                                      |
          v                                      |
Semantic Claim Verifier -- repairable gap --------+
          |
          v
Evidence Sufficiency Gate
          |
          v
Authoring Input Projection -> Authoring Plan -> Draft Writer
          |                                      |
          v                                      |
Final Text Claim Extractor -> Text Evidence Validator
          |                         |
          |                         +-- fail -> Authoring/Analysis Repair
          v
Numeric / Equation / Terminology / LaTeX / Fidelity Validators
          |
          v
Figure Scene Planner -> Direct Relation Validator
          |
          v
Pre-Render Invariant Audit
          |
          v
Structured Renderer / Locked-Contract Styler
          |
          v
Post-Render Element Audit -- fail -> Figure Repair / Block
          |
          v
Final Invariant Audit + Traceability Ledger
          |
          v
Finalize / Completion Report
```

关键拓扑变化：

- `authoring -> validation` 之间增加 final-text claim extraction 和 semantic evidence validation。
- 当前单一 `invariant_audit -> rendering -> finalize` 拆成 `pre_render_audit -> rendering -> post_render_audit -> final_invariant_audit -> finalize`。
- revision router 新增明确错误类型：`text_trace_invalid`、`claim_semantic_unsupported`、`figure_relation_unsupported`、`rendered_element_drift`、`stale_artifact`。
- 只有“可修复且预算尚存”才回环；否则输出可解释 blocked package。

## 11. 目标状态与 artifact contract

### 11.1 Typed state

将当前 path bag 逐步升级为版本化 state：

```text
AgenticRunStateV2
  run_id
  repo_snapshot_ref
  intent_ref
  budgets
  artifact_refs[name -> {path, digest, schema_version, producer}]
  retrieval_status
  evidence_status
  authoring_status
  text_validation_status
  figure_status
  finalization_status
  pending_gaps
  decisions
  loop_counters
```

要求：

- graph 使用 typed state，而不是裸 `dict`。
- list/dict 字段定义 reducer，避免并发/循环时覆盖。
- graph compile 时接 checkpointer；`run_id + repo_snapshot_id` 作为 resume 身份。
- 节点幂等：相同输入 digest 产生相同 artifact 或命中缓存。
- checkpoint 不能绕过 gate；恢复时重新验证依赖 digest。

### 11.2 EvidenceSpanV2

在兼容现有 `E1/E2` 的同时新增：

- `snapshot_id`、`project_tree_hash`、可选 `git_commit`/dirty flag；
- `path`、`symbol`、`line_start/end`；
- `excerpt_digest`，必须 hash 精确 excerpt，而不是 `content_summary`；
- `file_digest`；
- `source_type`、`evidence_strength`；
- `extraction_method`、`producer_version`；
- `derived_from_evidence_ids`；
- 可选 `runtime_trace_ref`，明确区分静态与运行证据。

freeze 后 evidence 内容不可原地修改。新增证据产生新 snapshot/version，旧 claim verification 自动失效。

### 11.3 AtomicClaimV2

每条 claim 至少包含：

- `claim_id`、`claim_text`、`claim_type`；
- `subject`、`predicate`、`object`、`conditions/qualifiers`；
- `support_status`：`supported | partial | unsupported | contradicted | unverified`；
- `direct_evidence_ids` 和可选 `context_evidence_ids`；
- `supported_fragment`、`unsupported_fragment`；
- `required_qualifiers`、`allowed_wording_boundary`；
- verifier verdict、rationale、risk level、input digest。

`direct_evidence_ids` 才能授权写作；context evidence 不能单独授权。

### 11.4 EvidenceRelationV2

方法图和流程描述共用显式关系：

- `relation_id`、`relation_type`；
- `source_entity_id`、`target_entity_id`；
- `semantic_statement`；
- `direct_evidence_ids`；
- `support_status`、`conditions`。

不得通过“两个节点各有证据”自动推导它们之间存在箭头。

## 12. Evidence-Bound Authoring 最终方案

### 12.1 Authoring Input Projection

新增 `agentic_authoring_input_projection.json`，从冻结 evidence 与 verification 生成唯一正向写作视图。

投影必须过滤所有可能泄漏 claim 的字段，而不只是 `ClaimEvidenceMap`：

- `MethodEvidence.claim_contracts`；
- `stage_packets[].claim_ids`、`stage_claim`、purpose 中的宽泛 claim；
- outline/scaffold；
- author intent spine 中 unsupported 部分；
- equations、aliases、mechanisms、distinguishing points；
- grounding context 和 revision payload。

excluded/unsupported 内容只能出现在独立 `forbidden_claims` 区域，并且不提供可被复述的正向方法措辞。

### 12.2 Authoring Plan Gate

plan 是写作 contract，不只是建议：

- section 只能引用 projection 中可写的 atomic claim；
- section evidence 必须是这些 claim 的 direct evidence 并集，而不是任意 known evidence；
- partial claim 必须携带具体 caveat template；
- plan 的签名绑定 projection digest；
- plan 外 claim 不能在最终正文自动获得合法身份。

### 12.3 Draft Writer

模型负责论文组织、衔接、抽象层次和表达，不负责判定证据支持。建议让模型返回正文和候选 claim intent，但候选引用始终视为 untrusted hint。

### 12.4 Final Text Trace Builder

在所有 post-processing 后，以最终 `method_clean.md/tex` 为输入：

1. 按句子/公式/标题描述切分；
2. 将复合句拆成 atomic claims；
3. 从 authoring plan 检索候选 claim/evidence；
4. 对每个 atomic claim 执行 semantic validator；
5. 只把通过的 claim/evidence 写入 `agentic_text_claim_trace.json`；
6. paragraph ledger 由 atomic trace 聚合生成。

禁止当前的两个 fallback：无匹配时贴首个 supported claim；无 evidence 时贴首个 known evidence。

### 12.5 Text Evidence Validator

每个 atomic claim 输出：

- verdict：`supported/caveated/block`；
- 支持/冲突证据；
- 未支持的 token/语义片段；
- 是否违反 wording boundary；
- 建议 route：删句、缩写、重写、回 analysis。

只有所有正文 claim 为 supported 或合规 caveated，且不存在未绑定事实句，authoring 才算 success。

## 13. Evidence-Bound Figure 最终方案

### 13.1 FigureSceneGraph

方法图计划不再只是 stages + then edges，而是：

- `node`：element ID、可见 label、semantic statement、claim IDs、direct evidence IDs；
- `edge`：source/target、relation type、可见 label、relation ID、direct evidence IDs；
- `annotation`：数值、公式、条件、claim/evidence；
- `group/container`：分组语义及证据；
- `omitted`：因 unsupported/low relevance 被排除的元素。

模型可以选择布局、分组和可视化层级，但不能自由改写可见 label 的事实含义。

### 13.2 关系验证

Figure planner 只能使用 EvidenceRelationV2。若没有直接关系证据：

- 不画箭头；
- 或使用明确非因果的视觉邻接；
- 不能用节点 evidence 的并集伪装 edge evidence。

### 13.3 渲染策略

可信度优先级：

1. 优先输出带 element IDs 的 SVG/HTML/canvas scene graph，由确定性 renderer 生成；
2. PaperBanana/生成式后端作为可选 stylist，只能消费锁定 scene contract；
3. 生成式后端不得新增 label、节点、箭头、公式和数值；
4. 无法稳定 post-validate 的纯 raster 图不能作为“全部元素可追溯”的最终交付格式。

### 13.4 Post-Render Audit

对实际 SVG/PNG/PDF 做 element manifest 对账：

- SVG：按 element ID、text、edge endpoints 直接解析；
- raster：OCR/vision 检查 label、数量、箭头和额外元素，风险等级高于 SVG；
- 任何额外事实元素、缺失必需元素或关系漂移都返回 figure repair；
- `completion_report.method_figure` 必须要求真实 asset、render manifest、post-render audit 均通过，不能只看 plan。

## 14. LangChain 工具规范化

### 14.1 工具契约

每个工具必须声明：

- Pydantic input/output schema；
- required/optional input artifacts；
- produced artifact schema/version；
- evidence policy；
- side-effect scope；
- idempotency/cache key；
- timeout/cost class；
- hard-gate 失败语义和 safe recovery；
- producer/tool version。

模型看到的是 contract view 和 artifact ref，不直接拿任意仓库路径读写。

### 14.2 P0 可信度工具

- `BuildAuthoringProjectionTool`
- `ExtractFinalTextClaimsTool`
- `ValidateClaimAgainstEvidenceTool`
- `BuildTextTraceTool`
- `ValidateFigureRelationTool`
- `ValidateRenderedFigureTool`
- `CheckArtifactFreshnessTool`

### 14.3 P1 检索/证据工具

- `BuildRetrievalPlanTool`
- `SearchCodeTool`
- `BuildSymbolIndexTool`
- `ReadEvidenceSpanTool`
- `AssessCoverageTool`
- `FreezeEvidenceSnapshotTool`
- `BuildEvidenceRelationTool`

### 14.4 迁移方式

保留现有 9 个 stage wrapper 作为 composite tools，先在其内部调用新细工具。等 artifact contract 和回归测试稳定后，LangGraph 再直接编排细工具。不要一次性拆完 7,000+ 行 legacy pipeline。

## 15. LangGraph 决策边界

### 模型可以决定

- retrieval target 优先级和 bounded rescan focus；
- 哪些 evidence gap 值得在预算内修复；
- section 顺序、标题、claim 分组和写作密度；
- 验证失败后回 authoring、analysis、retrieval 还是 block；
- 已验证 figure elements 的布局和层级。

### 模型不能决定

- 不能扩展 frozen evidence ID 集合；
- 不能把 unsupported/unverified/contradicted 改成 supported；
- 不能省略 required qualifier；
- 不能为图边复用无关节点 evidence；
- 不能在 validator failed 时直接去 rendering/finalize；
- 不能修改 loop budget 或 gate policy；
- 不能把旧 artifact 的存在当作 freshness 通过。

### 必须暴露的预算

- `max_retrieval_rounds`
- `max_evidence_revision_rounds`
- `max_authoring_revision_rounds`
- `max_figure_revision_rounds`
- `max_semantic_verifier_calls` 或等价 cost budget

所有预算都应进入 CLI、run manifest、decision trace 和 benchmark。

## 16. Validator 与 gate 分层

### Gate A：Source Integrity

验证 repo snapshot、file/excerpt digest、路径/行区间仍一致。

### Gate B：Claim Semantics

验证 claim 与直接 evidence 的语义支持、限定词、数值和公式来源。

### Gate C：Authoring Contract

验证 projection、plan、最终 atomic claims 一致，无 forbidden claim 泄漏。

### Gate D：Text Quality

运行 fidelity、numeric、equation、terminology、LaTeX 和 paper readiness；必须检查报告 status，不只是 artifact 存在。

### Gate E：Figure Contract

验证 scene graph 中每个 node/edge/annotation 的 claim 和 direct evidence。

### Gate F：Rendered Artifact

验证实际图和最终格式化文本与已审核契约一致。

### Gate G：Final Lineage

验证 final TeX/PDF/figure 来自通过上述 gate 的 exact artifact digest。

最终 invariant audit 聚合 A-G。traceability ledger 只记录通过/失败事实，不自行推断支持关系。

## 17. 目标 artifact 清单

保留现有 artifact，并新增/替换以下关键契约：

- `repo_snapshot.json`
- `intent_spec.json`
- `evidence_snapshot.json`
- `atomic_claim_contracts.json`
- `semantic_claim_verification.json`
- `agentic_authoring_input_projection.json`
- `agentic_authoring_plan.json`
- `agentic_final_text_claims.json`
- `agentic_text_claim_trace.json`
- `agentic_text_evidence_validation.json`
- `agentic_figure_scene_graph.json`
- `agentic_figure_relation_validation.json`
- `agentic_pre_render_audit.json`
- `agentic_post_render_audit.json`
- `agentic_traceability_ledger.json`
- `agentic_final_invariant_audit.json`
- `agentic_run_completion_report.json`

每个报告必须记录 `input_artifact_digests`，避免输入更新后旧报告仍被视为有效。

## 18. 实施路线

### M0：恢复可发布基线

目标：先让当前路线可安装、可运行、可复验。

1. 修复 `DEFAULT_FIGURE_IMAGE_MODEL` 导入不一致，使全量测试能收集。
2. `pyproject.toml` 增加：
   - `agentic = ["langgraph", "langchain-core"]`，并以当前本地已验证的 `langgraph==1.2.8`、`langchain-core==1.4.9` 建立 lock/CI 兼容基线，再给发布包设置经过测试的版本区间；
   - `code2paper-agentic-run`、`code2paper-agentic-benchmark` scripts。
3. README 增加 agentic 最小命令、blocked semantics、核心不变量和 artifact 入口。
4. CLI 暴露 evidence/authoring/figure revision budgets。
5. 建立 FastGS 当前失败 artifact 的只读基线快照，避免修复后无法比较。

### P0：正文可信度闭环

1. 实现全字段 Authoring Input Projection，消除 C1/C5 类正向泄漏。
2. 从 `pipeline/stages/authoring.py` 移除“首个 claim/evidence fallback”。
3. 最终 post-processing 后运行 atomic claim extraction。
4. 实现 claim-to-code semantic validator 和 `agentic_text_evidence_validation.json`。
5. 根据 validation issue 明确路由回 authoring/analysis；预算耗尽后 block。
6. invariant/ledger 改为消费后验 trace，而不是预写 scaffold。
7. T007/FastGS 复跑：不要求强行 success，但不得在 final invariant 才发现已知 excluded claim 泄漏。

### P1：Evidence V2 与 freshness

1. EvidenceSpan 增加 snapshot/file/excerpt digest 和 producer version。
2. 修正所有 ingestion path，使 excerpt hash 来自精确 excerpt。
3. 引入 atomic claim、direct/context evidence 区分和 partial fragment policy。
4. validator/report 全部绑定 input digest。
5. 添加 stale artifact 检测与重新冻结 route。

### P2：方法图执行闭环

1. 引入 EvidenceRelationV2 和 FigureSceneGraph。
2. 禁止 stage-order 自动成为 supported edge。
3. agentic rendering stage 真正调用结构化 renderer；PaperBanana 作为可选 stylist。
4. 增加 post-render audit。
5. completion report 要求真实 figure asset，而不是 plan-only。

### P3：工具细化与可恢复编排

1. 抽出 P0/P1 细粒度 LangChain tools。
2. graph 改为 typed state + reducers。
3. 接入 checkpointer/resume 和 artifact cache。
4. tool selection 只在 readiness context 允许时开放。
5. 保留 legacy composite tool 作为迁移 fallback，但不能绕过新 trust gates。

### P4：评估、cutover 与 legacy 降级

1. fixed vs agentic shadow benchmark。
2. 多模型只比较 proposal 质量；trust plane 保持一致。
3. 达到验收阈值后，`code2paper run` 默认进入 agentic route，legacy route 显式保留。
4. 连续多个版本稳定后，再逐步移除重复的 legacy orchestration，而不是先删除业务逻辑。

## 19. P0 代码落点

优先修改/新增：

- `src/code2paper/agentic/authoring_projection.py`：唯一正向写作视图。
- `src/code2paper/agentic/final_text_claims.py`：最终文本原子 claim 抽取。
- `src/code2paper/agentic/text_evidence_validator.py`：claim-to-code 语义验证。
- `src/code2paper/agentic/text_trace_builder.py`：只从验证结果建 trace。
- `src/code2paper/agentic/graph_topology.py`、`graph_*_nodes.py`：加入后验文本 gate 和 repair route。
- `src/code2paper/pipeline/stages/authoring.py`：删除位置式/首项 fallback，缩小 legacy authoring 职责。
- `src/code2paper/agentic/invariant_audit.py`、`traceability_ledger.py`：消费新后验报告并检查 digests/status。
- `src/code2paper/agentic/figure_planner.py`：后续升级 relation/scene contract。
- `src/code2paper/agentic/legacy_late_stage_tools.py`：后续真正渲染并产出 post-render audit。
- `src/code2paper/agentic/contracts.py`、`tool_specs.py`、`tools.py`：版本化 artifact/tool contract。

兼容策略：旧 `method_claim_map.json` 可继续输出，但标记为 `legacy_scaffold`，不得作为 final invariant 的权威输入。

## 20. 测试与验收

### 20.1 单元测试

- projection 中所有正向字段均无 excluded claim。
- partial claim 只输出 supported fragment 和 required qualifier。
- final text 多 claim 句能拆分；无事实内容的衔接句不被强行贴 evidence。
- stale evidence digest 被拒绝。
- figure edge 无直接 relation evidence 时不生成 supported edge。
- validation manifest 存在但 status=failed 时 invariant 必须失败。
- completion 无真实 figure asset 时必须 incomplete。

### 20.2 对抗测试

- 给无关句子挂合法 evidence ID，必须失败。
- 将 unsupported claim 改写成同义句，必须失败。
- 把一个 supported claim 扩写成更强因果/性能结论，必须失败或缩写。
- 给图节点使用代码支持的 stage ID，但将 label 改成不存在的新机制，必须失败。
- 用两个合法节点的 evidence 并集支撑无代码依据的箭头，必须失败。
- 渲染器在图中增加一个标签、公式或箭头，post-render audit 必须失败。
- evidence freeze 后修改源文件，所有下游 pass 报告必须失效。

### 20.3 集成测试

- toy 项目：完整 success，含真实图 asset、post-render audit、final invariant。
- FastGS：真实 provider + bounded loops；success 或解释性 block 均可，但不得出现伪 trace。
- 无 LLM：deterministic fallback 仍应安全，允许能力降级但不能降低 gate。
- checkpoint：在 evidence/authoring/render 后中断并恢复，结果 digest 与一次性运行一致。

### 20.4 发布门槛

- 全量测试能 collection 且通过约定基线。
- `pip install -e .[agentic]` 后 console scripts 可运行。
- README 命令与实际 CLI 一致。
- blocked run 默认退出语义清晰；CI 可用 `--fail-on-blocked`。
- run summary、completion、readiness、evaluation 对同一状态没有互相矛盾的“success/complete”。

## 21. Benchmark 设计

不能只比较“完成率”和“有多少 evidence ID”，否则总是阻塞或随意贴 ID 都可能刷出好成绩。

核心指标：

- atomic claim semantic precision；
- unsupported/paraphrased-unsupported leakage rate；
- claim evidence recall（相对人工标注可支持事实）；
- text trace exactness；
- figure element semantic precision；
- direct edge evidence rate；
- rendered element drift rate；
- correct-block rate 与 false-block rate；
- usable completion rate；
- retrieval/evidence/authoring/figure loop 数；
- runtime、token、模型调用成本；
- checkpoint 恢复节省。

Variant 排名采用可信度硬门槛：semantic precision、unsupported leakage、post-render drift 任一低于阈值时，不得因文风或完成率胜出。

## 22. 人工 review hook

该 hook 是可选的人机协作与补证据入口，不是 cutover 的固定数量/具名签署门槛。切换授权依赖 frozen
protocol、digest-pinned automated benchmark observations、evidence/validator/final-invariant/figure gates 以及
分阶段 rollout artifacts；人工批准本身不能把 unsupported 改成 supported。

以下情况应生成明确 review request，而不是模糊报错：

- 作者核心 claim 被判 partial/unsupported；
- 需要运行证据但当前仅有静态代码；
- 两个 verifier 对高风险 claim 冲突；
- 关系证据不足导致关键箭头被删除；
- 修复预算耗尽。

review artifact 应列出：作者原意、当前可支持片段、缺失证据、建议文件/符号/运行步骤、接受后的影响范围。人工批准可以改变作者意图或提供新证据，但不能直接把 unsupported 标为 supported。

## 23. 不再发散的边界

现阶段不要做：

- 不要先做多 Agent 辩论或开放式 autonomous coding。
- 不要为了“更像 Agent”把每个 helper 都拆成 tool。
- 不要为了 FastGS 通过而放宽 partial/unsupported gate。
- 不要把 README/论文描述当硬方法证据。
- 不要用任意 evidence ID fallback 填满 trace。
- 不要在 actual figure 尚未可审计前优化花哨画风。
- 不要把 framework manifest 的通过当作科研可信度通过。

## 24. 最终 Definition of Done

只有同时满足以下条件，才能宣布目标完成：

1. 作者意图真实影响检索、section plan 和 figure emphasis。
2. 每个最终方法原子 claim 都有通过语义验证的直接代码证据。
3. 每个 partial claim 只写受支持片段并带必要限定词。
4. 最终正文 trace 从最终文本反向生成，不依赖位置式 scaffold 或首项 fallback。
5. 每个图节点、标签、边和标注都有独立的 claim/relation/evidence binding。
6. 实际方法图 asset 已生成并通过 post-render audit。
7. 所有 validator 检查的是 pass status 和 artifact digest，而不是文件存在。
8. pre-render、post-render、final invariant 均不可绕过。
9. LangGraph 决策有预算、checkpoint、resume 和完整 trace。
10. LangChain 工具具有结构化 schema、幂等/副作用声明和 evidence policy。
11. toy 与至少一个真实项目能 success 或以可信、具体、可修复的原因 block。
12. benchmark 证明 agentic route 提高或至少不降低语义证据精度，而不是只生成更流畅的文字。

## 25. 当前最短实施路径

按依赖关系，下一步固定为：

1. 恢复全量测试 collection、agentic packaging 和 CLI budgets。
2. 完成全字段 authoring projection，先封住 T007 类泄漏。
3. 删除 claim/evidence fallback，实现最终文本反向抽取与语义验证。
4. 让 revision router 在 invariant 之前修复正文 trace。
5. 引入 direct relation evidence，重做 figure edge gate。
6. 让 agentic rendering 生成真实 asset，并增加 post-render audit。
7. 再进行细粒度 LangChain tool 拆分、typed state 和 checkpoint/resume。
8. 最后做 fixed vs agentic benchmark 和默认路线 cutover。

这一路径保留了当前 LangGraph、安全 merge、检索修复和 artifact 审计方面已经正确的投入，同时把下一阶段资源集中到最重要的缺口：从“ID 看起来闭环”升级到“最终文本和最终图的语义确实能回到代码”。
