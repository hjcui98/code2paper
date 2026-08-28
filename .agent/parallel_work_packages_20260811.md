# 自主 Method Agent 并行修复工作包

- Date: 2026-08-11
- Purpose: 把 `.agent/reorientation_report_20260811.md` 中的 A-H 工作包扩展成可分派给多个 Agent 的详细任务书。
- Integration owner: Codex 做最终整合验收。
- Execution style: 多 Agent 可以并行，但必须守住共享接口、文件边界和 verified-output truth gates。

Note: this file is now the fine-grained reference. For actual OpenCode conversation assignment,
prefer `.agent/merged_agent_assignments_20260811.md`, which combines these packages into 3 larger
tasks to reduce same-file conflicts.

## 0. 总体目标和验收轴

这轮不是继续做 R8/R9 闭合验收，而是恢复产品主流程：

```text
author intent / original paper / claims
  -> research agenda
  -> autonomous repository/config/data-flow/control-flow search
  -> evidence packets / code facts / atomic claims
  -> completeness status
  -> author-intent-first Method plan
  -> candidate Writer
  -> callback/resume when needed
  -> verified filtering
  -> publication_candidate + repository_verified + author_review_items
```

最终整体验收看四个结果：

1. `publication_candidate_method.md` 能覆盖作者想讲的 Method story，并显式标注缺证/待确认内容。
2. `repository_verified_method.md` 只包含 repository-supported positive implementation facts。
3. `author_review_candidates.json` 对每个关键未证点提供可编辑 `proposed_body`、问题、所需证据和建议动作。
4. Agent trace 能说明它搜索了什么、为什么支持、为什么部分支持、为什么 mismatch、为什么停止或 callback。

不要用以下结果冒充成功：

- 四项目 matrix 通过；
- 所有 obligation/move/proof exact closed；
- hash/manifest 很完整；
- 一个 Writer 样本偶然完成；
- candidate 和 verified 仍然相同但 unsupported positives 为 0。

## 1. 并行分派总览

### 1.1 推荐分派

| 包 | 主题 | 可否立即并行 | 主要文件所有权 | 主要交付 |
|---|---|---:|---|---|
| P0 | 共享产品契约薄层 | 必须最先/短任务 | `method_argument_models.py` 或新增 product models | lanes、review item、plan readiness、output bundle 契约 |
| A | 输出语义：candidate/verified/review 分离 | P0 后立即 | `publication_method_writer.py` 的输出写入区 | 三输出真正分离 |
| C | 作者意图投影 | P0 后立即 | `authoring_projection.py` | author story spine + lane-aware writer payload |
| D | Architect 分级 gate | C 契约草案后 | `method_architect.py` / argument models | candidate/verified/audit 分层 plan |
| E | Writer content-first | C/D 契约草案后 | `llm/section_writer.py` / schemas / writer input builder | prose-first writer + 后处理绑定 |
| G | 验证层分工 | A/C 契约草案后 | `final_text_claims.py` / `text_evidence_validator.py` | candidate allowed lanes + verified fail-closed |
| B | Research 主流程接入 | P0 后立即 | `research_graph.py` / new product runner | repo+intent+claims -> evidence/facts/claims |
| F | Callback/resume 闭环 | B/E 契约草案后 | `writer_research_router.py` / callback hooks | repository/config/formalization local callback + queues |
| H | 产品 CLI | A/B/C/D/E skeleton 后 | `cli/agentic_run.py` | one-command product smoke |

### 1.2 推荐执行顺序

```text
P0 shared contracts
  -> A + C + B + G initial work in parallel
  -> D after C contract skeleton
  -> E after C/D writer-plan skeleton
  -> F after B/E request/result skeleton
  -> H after A/B/C/D/E first integration
  -> Codex integration acceptance
```

### 1.3 文件冲突规则

多 Agent 并行时最容易冲突的文件是：

- `src/code2paper/agentic/publication_method_writer.py`
- `src/code2paper/agentic/method_argument_models.py`
- `src/code2paper/agentic/method_architect.py`
- `src/code2paper/llm/response_schemas.py`

规则：

1. P0 拥有共享契约新增/改名；其他 Agent 不要各自发明平行模型。
2. A 只负责输出写入、review JSON、candidate/verified 分离，不重写 Writer 调用链。
3. E 负责 Writer 输入/输出 schema 和 prose-first 生成，不重写 `_write_publication_outputs`。
4. G 负责 validation split，不改变 Writer prompt。
5. B 负责 product runner，不重写 legacy `v3_runtime.py` 兼容路径，除非只加 adapter/hook。
6. F 负责 callback execution 和 queue artifact，不修改 Research compiler 的核心事实语义。
7. 如果必须跨包改同一函数，先加小 adapter/hook，最后由整合者合并。

## P0 — 共享产品契约薄层

### 目标

先定义各包共同使用的最小产品契约，避免每个 Agent 各写一套 lane/review/status/schema。

### 当前问题

现有模型里已经有 `MethodCompletenessMatrixV1`、`WritingResearchRequestV1`、`WritingResearchCallbackArtifactV1`、`MethodSectionPlanV2`，但缺少产品层清楚区分：

- candidate 可以写什么；
- verified 可以写什么；
- review item 应带什么；
- plan 是 candidate-ready 还是 verified-ready；
- unresolved lane 是否阻塞 candidate。

### 建议实现

优先复用 `src/code2paper/agentic/method_argument_models.py`；如果担心污染现有模型，可以新增：

```text
src/code2paper/agentic/method_product_models.py
```

新增或明确这些契约：

```python
MethodEvidenceLane = Literal[
    "repository_verified",
    "repository_partial",
    "repository_mismatch",
    "author_intent_unverified",
    "author_confirmed",
    "literature_pending",
    "empirical_pending",
    "formalization_pending",
    "out_of_scope",
]

MethodPlanReadiness = Literal[
    "verified_ready",
    "candidate_ready",
    "candidate_ready_with_review",
    "blocked_for_safety",
]
```

建议模型：

```python
class MethodReviewCandidateV1(BaseModel):
    candidate_id: str
    source_obligation_id: str | None = None
    source_claim_id: str | None = None
    section_id: str | None = None
    lane: MethodEvidenceLane
    status: str
    proposed_body: str
    confirmation_question: str
    needed_evidence: list[str]
    suggested_action: str
    blocks_verified: bool = True
    blocks_candidate: bool = False
    trace_refs: list[str] = []

class MethodOutputPolicyV1(BaseModel):
    verified_positive_lanes: tuple[MethodEvidenceLane, ...]
    candidate_allowed_lanes: tuple[MethodEvidenceLane, ...]
    review_required_lanes: tuple[MethodEvidenceLane, ...]
    unsupported_positive_blocks_verified: bool = True
    unresolved_blocks_candidate: bool = False

class MethodDraftBundleV1(BaseModel):
    candidate_markdown: str
    verified_markdown: str
    review_items: list[MethodReviewCandidateV1]
    plan_readiness: MethodPlanReadiness
    blocked_reasons: list[str] = []
```

不要把这个模型设计得太重。它只是产品层分工，不是新的 proof 系统。

### 接口约定

- `repository_verified` 是唯一默认可进入 verified positive implementation facts 的 lane。
- `repository_partial` 只有保留限定词且验证通过时可进入 verified。
- `author_intent_unverified` 可进入 candidate，但必须对应 review item。
- `literature_pending` / `empirical_pending` / `formalization_pending` 可进入 candidate caveat 或 review，不进入 repository verified。
- `repository_mismatch` 不能被写成正向实现事实；candidate 可以把它写成 mismatch warning。

### 测试

新增或扩展：

- `tests/test_agentic_method_product_models.py`

覆盖：

- review item `proposed_body` 不能为空；
- `blocks_verified=True` 不等于 `blocks_candidate=True`；
- lane 枚举和 policy 默认值稳定；
- JSON roundtrip。

### 完成标准

- A/C/D/E/G/B/F/H 可以共用同一组 lane/status/review model。
- 没有引入新 hash/proof gate。

## A — 输出语义：candidate / verified / review 分离

### 目标

让输出层先恢复产品语义：证据不足时也能给用户候选稿和 review 项；verified 输出保持严格。

### 当前现状证据

主要文件：

- `src/code2paper/agentic/publication_method_writer.py`

关键函数：

- `run_publication_method_writer`
- `_write_publication_outputs`
- `_write_result_only`
- `_maybe_validate_final_text`

当前问题：

1. `_write_publication_outputs` 把同一个 `final_text` 同时写给 `repository_verified_method` 和 `publication_candidate_method`。
2. `author_review_candidates.json` 的 `proposed_body` 为空。
3. Writer 前 critical/high unplaced obligation 会直接 blocked，导致 candidate 也不生成。

### 具体修复

#### A1. 引入输出分流函数

新增内部函数，例如：

```python
def _split_candidate_and_verified_outputs(
    *,
    candidate_text: str,
    section_outputs: dict[str, PublicationMethodSectionOutputV1],
    completeness: MethodCompletenessMatrixV1,
    validation_report: Any | None,
    output_policy: MethodOutputPolicyV1,
) -> MethodDraftBundleV1:
    ...
```

最小策略：

- candidate 初期可以使用 Writer 生成的完整 section markdown；
- verified 初期从 candidate 中过滤掉未验证/需 review 的段落或句子；
- 如果还没有句级 lane split，verified 可以只输出 supported sections/spans，并把其余内容放 review；
- review items 必须补齐 `proposed_body`。

不要在 A 包里尝试重写全部验证逻辑；如果需要精细句级拆分，调用 G 包提供的 validator/splitter。

#### A2. 修改 `_write_publication_outputs`

行为改为：

```text
if status allows candidate:
  write publication_candidate_method.md = bundle.candidate_markdown
  write repository_verified_method.md = bundle.verified_markdown
  write author_review_candidates.json = bundle.review_items + research_requests
else if blocked_for_safety:
  write result only + review/block reasons
```

candidate 允许的状态：

- `success`
- `incomplete`
- `candidate_ready_with_review`
- `blocked_verified`

只有安全风险才完全不写 candidate，例如：

- Writer 输出包含不可区分的 unsupported positive implementation claim；
- final text validation 无法判断 candidate 中哪些是事实、哪些是 caveat；
- 文本来源不明，违反 authorship。

#### A3. review item 生成

把现在空的：

```python
"proposed_body": ""
```

改成真实拟文。来源优先级：

1. Writer candidate 中对应 unresolved span；
2. obligation/claim statement 的审慎改写；
3. callback request 的 exact question + suggested sentence；
4. 最后才是模板句。

示例：

```json
{
  "candidate_id": "review:MA-S2",
  "lane": "author_intent_unverified",
  "proposed_body": "The method is intended to ...; this point is currently awaiting repository or author confirmation.",
  "confirmation_question": "Should the Method claim that ...?",
  "needed_evidence": ["repository symbol or config confirming ..."],
  "suggested_action": "confirm_author_intent_or_provide_evidence",
  "blocks_verified": true,
  "blocks_candidate": false
}
```

#### A4. Candidate 不因普通缺证 blocked

把 pre-writer hard gate 从：

```text
critical/high unplaced -> blocked before Writer
```

改成：

```text
critical/high unplaced -> candidate_ready_with_review
supported positive without safe placement -> verified blocked
unsafe unsupported positive risk -> blocked_for_safety
```

这里要和 D/G 包协调：A 只消费 readiness，不独自决定所有语义。

### 禁止捷径

- 不要简单复制 candidate 到 verified。
- 不要为了让 verified 非空而过滤掉 review items。
- 不要把未证 author intent 写进 verified。
- 不要把 blocked 改名成 success。

### 测试

更新/新增：

- `tests/test_agentic_publication_method_writer.py`
- `tests/test_agentic_method_product_outputs.py`

测试场景：

1. supported claim + unverified author claim：
   - candidate 覆盖两个点；
   - verified 只覆盖 supported；
   - review item 有 proposed body。
2. repository mismatch：
   - candidate 显示 mismatch warning；
   - verified 不写正向 claim。
3. unsafe Writer positive：
   - verified blocked；
   - candidate 如果无法 caveat，也 blocked_for_safety。
4. status `incomplete` 仍写 candidate/review。

### 交付物

- 代码 diff。
- 测试命令和结果。
- 简短说明哪些状态会写 candidate，哪些状态会写 verified。

## C — 作者意图投影：author-intent-first payload

### 目标

让 Writer 和 Architect 看到作者真正想写的 Method story，而不是只看到 code-supported claims 或 code-order mainline。

### 当前现状证据

主要文件：

- `src/code2paper/agentic/authoring_projection.py`
- `src/code2paper/agentic/intent_compiler_v2.py`
- `src/code2paper/agentic/intent_obligations.py`

关键函数：

- `build_authoring_projection`
- `_build_v3_projection`
- `projection_writer_payload`
- `projection_writer_brief`
- `projected_writer_inputs`
- `_author_attested_fragments`
- `_safe_intent_spine`

当前问题：

1. V3 projection 的 `author_goal` 硬编码为按 compiled inference mainline/code order 写。
2. `projection_writer_payload` 注释说是 Writer 唯一 positive factual payload，导致 author intent 被压扁。
3. 未验证作者点容易从 writer surface 中消失，而不是进入 candidate/review。

### 具体修复

#### C1. 增加 story spine

从已有输入中抽取：

- author intent summary；
- original method draft / paper fragments；
- user claims；
- reference obligations；
- author markers。

输出字段建议：

```python
author_story_spine: list[AuthorStoryNodeV1]
```

每个 node 至少包含：

```text
story_node_id
title
author_statement
intended_role: motivation | setup | algorithm_step | training | inference | evaluation | ablation | limitation
source_refs
linked_obligation_ids
linked_claim_ids
evidence_lane
```

如果不想新增模型，也可以先用 dict，但必须 schema 稳定。

#### C2. lane-aware writer payload

`projection_writer_payload` 应返回：

```text
author_story_spine
repository_verified_facts
repository_partial_facts
repository_mismatches
author_intent_unverified_points
external_pending_points
formalization_needed_points
review_questions
writing_policy
```

关键语义：

- repository facts 是 verified authority；
- author story 是 organization/candidate authority；
- external pending 是 review/callback authority；
- forbidden claims 继续保护 verified。

#### C3. 替换硬编码 author goal

不要再使用：

```text
Explain the compiled inference mainline in code order...
```

改为从 author intent 构造：

```text
Organize the Method around the author's intended contribution story, using repository evidence to verify implementation facts and marking unresolved author/literature/formalization points for review.
```

如果没有 author intent，才 fallback 到 repository behavior order，并在 trace 里记录 fallback。

#### C4. 保留缺证作者点

当 obligation 没有 repository support：

- 不进入 `repository_verified_facts`；
- 进入 `author_intent_unverified_points` 或具体 external lane；
- 生成 review question；
- 保留到 candidate planning surface。

#### C5. 输出 trace

新增或扩展 projection trace：

```text
source author text -> story node -> obligation -> evidence status -> writer payload field
```

这能帮助最终验收判断作者意图有没有被吞掉。

### 禁止捷径

- 不要把所有 author intent 都转成 positive repository claim。
- 不要因为代码搜不到就删除作者点。
- 不要把 code order 当默认组织，除非没有作者意图。
- 不要引入项目名/已知答案硬编码。

### 测试

新增/扩展：

- `tests/test_agentic_authoring_projection.py`
- `tests/test_agentic_author_intent_summary.py`
- `tests/test_agentic_intent_compiler_v2.py`

测试场景：

1. 同一 evidence，不同 author intent，生成不同 story spine 顺序。
2. 一个 unverified author point 进入 payload 的 unverified/review lane。
3. repository-supported fact 进入 verified facts。
4. mismatch 进入 mismatch lane，而不是 positive claim。
5. 无 author intent 时 fallback 到 repository behavior order，并记录 fallback reason。

### 交付物

- 新 projection fields / models。
- payload 示例 JSON。
- 测试结果。
- 简短说明哪些字段给 Architect、哪些字段给 Writer、哪些字段给 review。

## D — Method Architect：从 proof gate 回到 argument organizer

### 目标

让 Architect 按作者 story 组织 Method 论证，同时保留 verified/audit 所需绑定；不要让 exact placement/proof 阻止 candidate。

### 当前现状证据

主要文件：

- `src/code2paper/agentic/method_architect.py`
- `src/code2paper/agentic/method_argument_models.py`

关键函数/模型：

- `build_method_section_plan`
- `build_method_section_plan_with_trace`
- `build_semantic_argument_frame`
- `place_obligation_assignments`
- `resolve_move_authority_proofs`
- `MethodArgumentUnitV1`
- `SectionArgumentGraphV1`
- `MethodSectionPlanV2`
- `ObligationMoveAssignmentV1`
- `MoveAuthorityProofV1`

当前问题：

1. Architect 输出过度围绕 exact semantic frames / move authority / obligation placement。
2. supported/unplaced 或 critical/high unplaced 会影响 Writer 是否能开始，导致 candidate 停摆。
3. 章节组织更像 code facts grouping，不是 author story spine。

### 具体修复

#### D1. 引入 plan readiness 分层

在 `MethodSectionPlanV2` 或旁路模型中增加：

```text
candidate_readiness
verified_readiness
blocked_for_safety_reasons
review_required_ids
audit_warnings
```

建议语义：

- `candidate_ready`：可以写 candidate，无关键安全风险。
- `candidate_ready_with_review`：可以写 candidate，但存在未证/外部/partial/mismatch。
- `verified_ready`：所有进入 verified 的 positive facts 都已绑定且可验证。
- `blocked_for_safety`：无法安全区分 unsupported positive 或文本/事实边界。

#### D2. 改 section organization 输入

从 C 包消费：

```text
author_story_spine
repository_verified_facts
partial/mismatch/external points
```

章节生成优先级：

1. author story spine；
2. reader method logic；
3. repository behavior order；
4. code order fallback。

#### D3. 拆分 unit 类型

每个 `MethodArgumentUnitV1` 或扩展字段需要能表达：

```text
unit_authority_lane
can_enter_candidate
can_enter_verified
requires_review
requires_callback
evidence_status
```

不要要求每个 candidate unit 都有 exact semantic frame。

#### D4. 保留 proof 但降级为 audit

`place_obligation_assignments` / `resolve_move_authority_proofs` 继续可运行，但结果使用方式改为：

- verified path：需要 proof/placement 的 positive implementation fact 仍严格；
- candidate path：unplaced/external/partial 进入 review/callback，不阻止整节写作；
- audit report：记录哪些 move/proof 未闭合。

#### D5. Architect trace 改写

trace 不只记录 closed IDs，也记录：

```text
story node -> section -> units -> evidence lane -> candidate/verified/review decision
```

### 禁止捷径

- 不要删除 proof 模型来“简化”。
- 不要把 supported row 改成 external_pending 来绕过 verified gate。
- 不要让 candidate 无标记地写 unverified positive implementation facts。
- 不要以 code-order grouping 继续覆盖 author story。

### 测试

新增/扩展：

- `tests/test_agentic_method_architect_product_readiness.py`
- 相关 existing publication writer/architect tests。

测试场景：

1. supported unit -> candidate + verified ready。
2. unverified author unit -> candidate_ready_with_review，不进入 verified。
3. mismatch unit -> candidate warning，不进入 positive verified。
4. exact proof missing -> audit warning，candidate 不 blocked。
5. unsafe unsupported positive -> blocked_for_safety。
6. author story order 改变 section order。

### 交付物

- readiness model/fields。
- section plan JSON 示例。
- audit warnings 示例。
- 测试结果。

## E — Writer：content-first，绑定后处理

### 目标

Writer 回到“写可读 Method 正文”的角色。它可以提出缺口和风险，但不再被迫在同一响应里完成全部 ID/move/config/equation/proof 填表。

### 当前现状证据

主要文件：

- `src/code2paper/llm/section_writer.py`
- `src/code2paper/llm/response_schemas.py`
- `src/code2paper/agentic/publication_method_writer.py`
- `src/code2paper/llm/role_config.py`

关键函数/模型：

- `write_publication_method_by_sections`
- `_closed_set_publication_schema`
- `_publication_contract_failures`
- `_decode_publication_research_requests`
- `PublicationMethodSectionOutputV1`
- `_writer_section_inputs`
- `_writer_section_inputs` / `_section_inputs_from_plan` 附近逻辑
- `METHOD_WRITER` role config

当前问题：

1. Writer 输入含 semantic frames、move proof、validation constraints、binding contract，负担过重。
2. Writer 输出 schema 同时要求正文、used IDs、moves、configs、equations、callback。
3. `METHOD_WRITER` 默认 temperature 仍偏低，不符合“decision 严谨、prose 有创作组织”的要求。

### 具体修复

#### E1. 拆 Writer 两类输出

建议模型：

```python
class SectionWriterDecisionV1(BaseModel):
    section_id: str
    decision: Literal["ready", "research_required", "author_review_required", "incomplete"]
    requests: list[WritingResearchRequestV1] = []
    review_items: list[MethodReviewCandidateV1] = []
    reason: str

class SectionWriterProseV1(BaseModel):
    section_id: str
    section_markdown: str
    unresolved_points: list[str] = []
    self_risks: list[str] = []
```

如果要减少改动，可以先保留 `PublicationMethodSectionOutputV1`，但把 full used IDs 改成 optional/auxiliary，不作为 Writer prose 成败的主条件。

#### E2. Writer input 改成 content surface

`_writer_section_inputs` / section input payload 应提供：

```text
section purpose
author story nodes
verified facts summary
partial/mismatch/external notes
candidate/review policy
allowed formulas/configs for verified facts
what must be caveated
what must not be stated as repository fact
```

不应把完整 internal IDs、move proof、semantic frame slots 当正文主输入。IDs 可以放 trace/binding side channel，不出现在 prose prompt 主体。

#### E3. 后处理绑定

Writer 写完后：

1. `final_text_claims.extract_final_text_claims` 抽取句级 claim。
2. `text_evidence_validator.validate_text_evidence` 判断哪些能进 verified。
3. 未验证但 author-intent 允许的内容进入 review/candidate lane。
4. harness 不得补造 Writer 没写的 factual content。

#### E4. callback/request 处理

如果 Writer 认为某点无法写清楚：

- repository/config/formalization：输出 `WritingResearchRequestV1`，交给 F；
- author/literature/empirical：输出 review/queue item；
- 该 section 标记 incomplete 或 candidate_with_review。

不要让 deterministic code 从空 request 推断 ready；也不要从 move proof 自动合成 callback。

#### E5. 角色温度

在 `role_config.py` 中拆或覆写：

```text
writer_decision: temperature=0.0, seed=42
writer_prose: temperature≈0.7, top_p≈0.90, seed=42
```

如果暂时无法新增 role，至少让 prose call 能显式传入中温配置，并在 trace 中记录。

### 禁止捷径

- 不要用 prompt-only 修复 schema 过载。
- 不要让 Writer prose 输出 internal IDs。
- 不要因为模型漏 ID 就让 harness 自动补齐事实绑定。
- 不要把 unverified author content 写进 verified。

### 测试

新增/扩展：

- `tests/test_llm_section_writer.py`
- `tests/test_llm_publication_schema_closed_sets.py`
- `tests/test_agentic_publication_method_writer.py`

测试场景：

1. ready decision -> prose call。
2. research_required decision -> 不写 prose，交 callback。
3. author_review_required -> candidate/review，不进 verified。
4. prose 无 IDs 但句子可后验证 -> verified binding 成功。
5. prose 有 unsupported positive -> verified reject。
6. writer prose config 使用中温，strict roles 仍低温。

### 交付物

- 新 writer schema 或兼容改造。
- prompt/input payload 示例。
- temperature trace 示例。
- 测试结果。

## G — 验证层：candidate 允许标注，verified 保持 fail-closed

### 目标

把真实性门用于正确的输出：verified 严格，candidate 可包含带 caveat/review 的作者意图内容。

### 当前现状证据

主要文件：

- `src/code2paper/agentic/final_text_claims.py`
- `src/code2paper/agentic/text_evidence_validator.py`
- `src/code2paper/agentic/publication_method_writer.py`

关键函数：

- `extract_final_text_claims`
- `validate_text_evidence`
- `_maybe_validate_final_text`
- `_final_validation_failures_by_section`

当前问题：

1. validation 的语义主要服务 final text 是否全可证。
2. candidate 中 author-intent/review/caveat 需要被识别，不应和 unsupported positive 混为一谈。
3. verified split 还不明确。

### 具体修复

#### G1. claim 分类

扩展 final text claim extraction，让每个 sentence/claim 能分类：

```text
repository_positive
author_intent_caveated
review_question
mismatch_warning
literature_pending
formalization_pending
expository_bridge
unsafe_unsupported_positive
```

分类依据可以先简单：

- 显式 caveat/review marker；
- review item refs；
- projection lane；
- repository fact match；
- numeric/formula/config token presence。

#### G2. verified filter

新增函数，例如：

```python
def build_repository_verified_text(
    *,
    candidate_text: str,
    extracted_claims: FinalTextClaims,
    validation_report: TextEvidenceValidationReport,
    output_policy: MethodOutputPolicyV1,
) -> str:
    ...
```

规则：

- only repository-supported positives；
- partial 必须保留 qualifiers；
- expository bridge 可保留，前提是不包含实现事实；
- mismatch/review/caveat 不进入 verified，除非 verified 文档允许“limitations/gaps”小节且不作为 implementation positive。

#### G3. candidate safety report

新增/扩展 report 字段：

```text
candidate_unsafe_claims
candidate_review_linked_claims
verified_included_claims
verified_excluded_claims
reason
```

这给 A 包写 output bundle 使用。

#### G4. 数值/公式/配置继续严格

candidate 中出现具体数值/公式/配置时：

- 如果作为 implementation fact，必须能验证；
- 如果不能验证，要转 review/caveat；
- 不允许裸写进 verified。

### 禁止捷径

- 不要整体关闭 reverse validation。
- 不要把所有 caveat 都当安全；含明确实现事实仍需验证或 review。
- 不要通过删除句子让 candidate 变得无用。

### 测试

新增/扩展：

- `tests/test_agentic_final_text_trust.py`
- `tests/test_agentic_candidate_verified_split.py`

测试场景：

1. supported implementation sentence -> verified included。
2. author-intent caveated sentence -> candidate included，verified excluded，review linked。
3. unsupported uncaveated implementation sentence -> unsafe。
4. formula/config numeric unsupported -> unsafe or review,不进 verified。
5. expository bridge -> 可以保留。

### 交付物

- verified split helper。
- candidate safety report。
- 测试结果。

## B — Research 主流程：从 legacy bridge 提升为 product runner

### 目标

让系统有一个清晰的产品路径：从 repo + author intent + claims 进入自主研究工具循环，产出 evidence/facts/claims/completeness，然后交给 Architect/Writer。

### 当前现状证据

主要文件：

- `src/code2paper/agentic/research_graph.py`
- `src/code2paper/agentic/research_nodes.py`
- `src/code2paper/agentic/research_tools.py`
- `src/code2paper/agentic/v3_runtime.py`
- `src/code2paper/agentic/runner.py`

关键函数/类：

- `build_research_subgraph`
- `run_research_loop`
- `ResearchLoopState`
- `ResearchLoopResult`
- `ResearchLoopDriver`
- `compile_code_facts`
- `decompose_atomic_claims`
- `GemmaSupervisorBackend`
- `DeterministicSupervisorBackend`

当前问题：

1. V3 research 是 bridge：先跑 research，再转 legacy decision，再跑 legacy graph。
2. product path 没有清楚入口。
3. synthetic gaps / fallback artifacts 是验收兼容，不应成为产品语义。

### 具体修复

#### B1. 新增 product runner

建议新增：

```text
src/code2paper/agentic/autonomous_method_agent.py
```

核心入口：

```python
def run_autonomous_method_agent(
    *,
    repo_path: str | Path,
    author_intent_path: str | Path | None = None,
    claims_path: str | Path | None = None,
    out_root: str | Path,
    llm_config: LLMConfig | None = None,
    max_research_turns: int = ...,
) -> MethodAgentRunResultV1:
    ...
```

#### B2. 输入归一化

调用 C/P0 的输入契约：

```text
author intent -> agenda/story obligations
claims -> initial obligations
repo -> research tool registry
```

#### B3. 研究循环

直接调用：

```python
build_research_subgraph(...)
```

或在非 LangGraph 环境用：

```python
run_research_loop(...)
```

每个 obligation 至少允许：

- search symbols/code；
- read relevant span；
- inspect config；
- trace call/data/control if needed；
- compile evidence candidate；
- record typed gap with reason when no gain。

#### B4. 输出 artifacts

product runner 至少写：

```text
evidence_packets.json
code_facts.json
atomic_claims.json
completeness_matrix.json
research_trace.json
typed_gaps.json
```

再调用 C/D/E/A/G 形成文本输出。

#### B5. legacy bridge 隔离

`v3_runtime.py` 可以保留，但 product runner 不应依赖：

- synthetic gaps；
- fallback minimal claim_set；
- legacy artifact merge；
- R8 acceptance summary。

如需复用函数，抽公共 helper，不要继续把 product path 包在 legacy graph 里。

### 禁止捷径

- 不要把 profile/hardcoded project answers 写入 generic research logic。
- 不要找不到证据就 synthetic support。
- 不要把 deterministic fallback 当长期产品 Agent。
- 不要在 product runner 里调用四项目 matrix。

### 测试

新增/扩展：

- `tests/test_agentic_autonomous_method_agent.py`
- `tests/test_agentic_research_tools.py`
- `tests/test_agentic_v3_e2e.py`

测试场景：

1. 小 fixture 中一个函数实现某 claim -> supported。
2. claim 查无 evidence -> typed gap。
3. config value -> configuration evidence。
4. no-progress budget -> stop with reason。
5. product runner 不产生 synthetic support。

### 交付物

- product runner。
- artifacts 示例。
- research trace 示例。
- 测试结果。

## F — Callback/resume：写作缺口回到研究/配置/形式化/队列

### 目标

Writer 写到缺信息时，系统能按 lane 回调本地工具或生成外部队列，并只恢复受影响 section。

### 当前现状证据

主要文件：

- `src/code2paper/agentic/writer_research_router.py`
- `src/code2paper/agentic/publication_method_writer.py`
- `src/code2paper/agentic/formalization_agent.py`
- `src/code2paper/agentic/graph.py`
- `src/code2paper/agentic/graph_topology.py`

关键函数：

- `route_writing_research_request`
- `execute_writing_research_route`
- `execute_open_requests_for_routes`
- `fulfill_writing_research_callbacks`
- `_load_callback_bundle`
- `_write_section_checkpoint`
- `formalize_code_facts`

当前问题：

1. repository route 只有 provider supplied 时执行。
2. author/literature/empirical lane 返回 `None`，缺少 queue artifact。
3. 主 graph 没有自然 Writer -> callback -> evidence update -> resume section 的产品环。

### 具体修复

#### F1. route owner 行为表

明确 route 行为：

| lane | owner | 本轮行为 |
|---|---|---|
| repository | repository_tools | 调 B 包 product research tools/provider |
| configuration | configuration_tools | 查 frozen/live config claims |
| formalization | formalization_agent | 调 formalization result / symbol/equation helper |
| author | author_queue | 生成 review item + proposed body |
| literature | literature_queue | 生成 external pending citation/search task |
| empirical | empirical_queue | 生成 artifact/experiment evidence request |

#### F2. queue artifacts

即使不能自动执行，也不要返回无声 `None`。新增 artifact：

```python
class ExternalResearchQueueItemV1(BaseModel):
    request_id: str
    lane: str
    section_id: str
    exact_question: str
    proposed_body: str | None
    needed_evidence: list[str]
    status: Literal["queued", "fulfilled", "cancelled"]
```

author/literature/empirical 应写入 callback bundle/review JSON。

#### F3. repository provider 默认接入

如果 product runner 中存在 research runtime，则 `repository_tools` route 默认可：

- search/read/trace；
- produce new evidence packet；
- update facts/claims/completeness；
- return digest/trace refs。

如果没有 runtime，返回 queued repository request，而不是 silent None。

#### F4. resume affected section

checkpoint 语义：

```text
callback fulfilled
  -> update projection/plan for affected section
  -> invalidate affected section only
  -> rerun writer decision/prose for affected section
  -> keep unaffected section markdown/digests
```

不要把所有 section 全重写作为“简单实现”。

#### F5. graph route

主产品 graph 增加：

```text
writer_decision
  -> callback_router
  -> repository/config/formalization/queue
  -> evidence_update
  -> architect_update
  -> section_resume
```

如果 B 包先做 product runner 而不是 LangGraph 主图，F 可以先实现 procedural resume，再接 graph。

### 禁止捷径

- 不要 deterministic synthesis callback。
- 不要把外部 lane 当 fulfilled。
- 不要 callback 后全局重写所有章节。
- 不要无声丢弃 request。

### 测试

新增/扩展：

- `tests/test_agentic_writing_route_execution.py`
- `tests/test_agentic_callback_resume_product.py`
- checkpoint/resume tests。

测试场景：

1. repository callback fulfilled -> affected section resumes。
2. configuration callback fulfilled -> config evidence admitted。
3. formalization callback fulfilled -> formula/symbol review resolved。
4. author callback -> review queue item，candidate continues，verified excludes。
5. literature/empirical -> external queue item。
6. unaffected section digest unchanged。

### 交付物

- route behavior implementation。
- queue artifact JSON。
- resume trace。
- 测试结果。

## H — 产品 CLI：一个命令跑完整产品路径

### 目标

提供清晰产品入口，让用户不需要理解 R8/R9 matrix/canary，也能从 repo + author intent + claims 得到三类 Method 输出。

### 当前现状证据

主要文件：

- `src/code2paper/cli/agentic_run.py`
- `src/code2paper/agentic/runner.py`
- `scripts/run_publication_writer_from_artifacts.py`
- `scripts/run_d5_consolidated_matrix.py`
- `scripts/run_static_v3_research.py`

当前问题：

1. 有 artifact writer、matrix runner、static research runner，但没有简单 product command。
2. 用户路径被验收脚本绑架。

### 具体修复

#### H1. CLI 形态

新增或扩展：

```text
code2paper method-agent run \
  --repo <repo> \
  --author-intent <file> \
  --claims <file> \
  --out <dir> \
  [--max-research-turns N] \
  [--llm-profile <file>] \
  [--no-live-llm]
```

#### H2. 调用 product runner

CLI 调 B 包的：

```python
run_autonomous_method_agent(...)
```

不要绕去 D5 matrix。

#### H3. 输出目录

固定输出：

```text
publication_candidate_method.md
repository_verified_method.md
author_review_candidates.json
evidence_packets.json
code_facts.json
atomic_claims.json
completeness_matrix.json
agent_trace.json
run_summary.json
```

#### H4. 用户可读 summary

终端 summary 不要只打印 test-like counts。应打印：

```text
candidate written: yes/no
verified written: yes/no
verified facts: N
review items: N
callbacks fulfilled: N
external queues: N
unsafe blocked claims: N
```

### 禁止捷径

- 不要让 CLI 默认运行四项目 matrix。
- 不要要求所有 proof closed 才输出 candidate。
- 不要吞掉 review items。

### 测试

新增/扩展：

- `tests/test_agentic_run_cli.py`
- `tests/test_agentic_autonomous_method_agent_cli.py`

测试场景：

1. fixture run writes required outputs。
2. missing claim file gives clear error。
3. no-live-llm fallback still produces deterministic fixture result or typed blocked reason。
4. CLI summary includes candidate/verified/review counts。

### 交付物

- CLI command。
- fixture output root 示例。
- 测试结果。

## 2. 整合验收流程

多个 Agent 完成后，Codex 做整合验收时按这个顺序检查：

### 2.1 静态结构检查

1. 是否所有包使用同一套 P0 lane/review/readiness 契约。
2. 是否 candidate/verified/review 输出路径一致。
3. 是否仍有代码把 candidate 直接写成 verified。
4. 是否仍有普通缺证导致 candidate 完全不写。
5. 是否存在 synthetic support / silent callback drop。

### 2.2 单包测试复核

每包需在交付说明里记录：

```text
changed files
new/updated tests
exact commands
exit status
behavior summary
known limitations
```

### 2.3 产品 smoke

整合后运行一个小 fixture，而不是先跑四项目 matrix：

```text
repo fixture
author intent with:
  - one supported implementation point
  - one unverified author point
  - one mismatch or partial point
  - one callback-worthy config/formalization point
```

验收：

- candidate 非空，覆盖 story；
- verified 非空，只含 supported；
- review JSON 非空，含 proposed body；
- callback trace 有 fulfilled 或 queued；
- unsupported positive verified = 0。

### 2.4 最后才考虑广泛回归

产品 smoke 通过后再运行：

- focused tests；
- `python -m compileall -q src tests`；
- `git diff --check`；
- full suite；
- 最后才考虑 RAP/四项目 eval。

## 3. 给各 Agent 的统一边界

每个 Agent 都必须遵守：

1. 不读/写 `.agent-team/`。
2. 不 reset/clean/checkout/commit/merge。
3. 不用项目 literal 或已知答案写 generic logic。
4. 不降低 verified-output truth gates。
5. 不把 author intent 当 repository implementation fact。
6. 不把缺证当成功，也不把缺证当产品失败；缺证必须变成 review/callback/mismatch。
7. 不新增重复文档系统；交付记录写 `.agent/implementation.md` 或自己包的简短 handoff，由整合者归并。
