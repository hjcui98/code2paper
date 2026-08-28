# 外部 Agent 机制落到 Code2Paper：逐函数差距审计与架构蓝图

> 日期：2026-08-10
>
> 配套证据：`reference_agent_framework_runtime_deep_dive_2026-08-10.md`
>
> 定位：对当前工作树的只读代码路径审计与参考落点，不是新的规范、执行计划或完成账本
>
> 验证边界：未运行 Code2Paper 测试、benchmark、模型或真实 API；本文发现需要后续实现与测试确认

## 1. 本文回答什么

本文不再问“参考仓库有什么”，而是回答：

1. Code2Paper 当前已经具备哪些等价或更强机制；
2. 哪些机制只有模型/辅助函数，尚未接进真实运行路径；
3. 哪些缺口会直接影响当前 Research Agent 和 Method Writer 的信任目标；
4. 如果实施，应该改哪个文件、哪个函数、建立什么不变量和测试。

所有判断受 `docs/README.md` 中的权威顺序约束。本文不能覆盖总体设计、Method Writer 设计、
R8 后执行计划或 `.agent/plan.md`。当前工作树包含大量未提交 Post-R8 变更；本文描述的是
2026-08-10 本地代码快照，不将其表述为稳定里程碑。

证据分级：

| 标签 | 含义 |
|---|---|
| `PRESENT` | 真实生产路径中已观察到机制与绑定 |
| `MODEL-ONLY` | schema/helper/tests 存在，但主调用链未完成消费或提交 |
| `PATH-GAP` | 静态调用链显示有数据在层间丢失或没有落账 |
| `RISK` | 需要 fault-injection/runtime test 才能最终裁决 |
| `PROPOSAL` | 本文建议，不是当前实现事实 |

## 2. 对第一轮报告的校正

### 2.1 已经存在，不应重复设计

| 机制 | 当前代码证据 | 判断 |
|---|---|---|
| 不可变研究循环 payload | `research_graph.py:230-517`，内容寻址文件、SHA-256、原子写、路径约束 | `PRESENT` |
| production resume fail closed | `restore_loop_state_from_snapshot(..., strict=True)`；driver 在前缀/模型前恢复 | `PRESENT` |
| Writer callback 精确绑定 | `method_argument_models.py:376-514` 绑定 request/section/unit/lane/artifact IDs | `PRESENT` |
| callback bundle 完整性 | bundle `content_digest`，持久化读取重新计算 normalized digest | `PRESENT` |
| affected-only Writer resume | `publication_method_writer.py:307-526` 只选择 resume sections，复用其他 checkpoint outputs | `PRESENT` |
| 不可变 section checkpoint | `publication_method_writer.py:3280+` 内容寻址 output、相对 ref、digest、response ref | `PRESENT` |
| source-digest authoring projection | `authoring_projection.py:253-367` 绑定 packet/fact/claim/equation/snapshot digests | `PRESENT` |
| fail-closed plan/quality/final gates | `authoring_plan_v3.py`、`publication_quality.py`、final trust path | `PRESENT`，完成度仍由正式验收裁决 |

因此不建议再建立第二套通用 EventLog、第二套 callback ticket 或第二套 immutable artifact store。
外部参考应补强现有链条的提交语义，而不是替换已有事实模型。

### 2.2 真正剩余的机制缺口

| 优先级 | 残余问题 | 静态证据 | 外部参考 |
|---|---|---|---|
| P0 | budget delta 被计算，但没有应用回循环预算 | `research_policy.py:694-737` 与 `research_nodes.py:787-818`；主循环无调用 | OpenClaw retry budget、Harness shared budget |
| P0 | QualityState 模型存在，但当前循环未从候选产物重算并提交 artifact closure | `current_quality_state` 只见初始化/恢复；selector 在 compile 前运行 | OpenClaw accepted candidate、Hermes commit fence |
| P0 | Architect/Writer 有两套 semantic frame 编译，未知 predicate 默认 transformation，关系绑定语义不一致 | `method_architect.py:492-658`；`publication_method_writer.py:2225-2335` | OpenHands property intersection |
| P1 | callback artifact 有 ID/digest，但没有绑定 request digest、validator identity/report | `WritingResearchCallbackArtifactV1` 与 repository provider 路径 | Pydantic deferred + Harness receipt |
| P1 | terminal resume identity 未直接绑定模型/角色配置/工具 manifest；终态 snapshot 发射时点需验证 | `_validate_terminal_resume()` 与 `_ctx_terminate()` | Hermes verification staleness、Harness complete snapshot |
| P1 | 工具 cache 只有成功结果，没有 started/unknown-after-crash receipt | `tool_runtime.py:61-99` | Harness step/effect persistence |
| P2 | projection 有 source digests，但没有统一 property-set/transform receipt | `authoring_projection.py` 多个投影入口 | OpenHands View + property intersection |

## 3. 研究循环调用链审计

### 3.1 当前主链

直接 driver 的核心顺序是：

```text
linear prefix
  -> supervisor proposal
  -> policy merge
  -> tool execute
  -> observation ingest
  -> behavior graph update
  -> quality selector
  -> evidence critic
  -> compile candidate / gap
  -> obligation advance
```

LangGraph topology在 `research_graph.py:1712-1781` 使用相同逻辑节点：

```text
linear_prefix -> research_supervisor -> research_tool
  -> observation_pipeline -> evidence_critic
  -> compile_candidate | gap_finalizer | supervisor
  -> obligation_advancer -> supervisor | terminator
```

这个顺序暴露两个关键落差：预算在 supervisor/policy merge 已决定，但工具前没有落账；quality selector
在 compile candidate 前执行，而且当前 quality 对象没有随 packet/fact/claim 变化而重算。

### 3.2 PATH-GAP：预算被计算但没有落账

数据链如下：

1. `research_policy.py:694-708` `_compute_consumed_budgets()` 从 accepted policy decision 的
   `selected_tool_calls` 计算 `{obligation_id: {tool_kind: count}}`；
2. `apply_policy_merge()` 把它放进 `PolicyMergeResult.consumed_budgets`；
3. `research_nodes.py:787-818` `research_supervisor_node()` 返回 merge result，只暴露为私有
   `_policy_merge_results`；
4. direct driver 只 pop `_merged_decision`，没有把 merge result 延伸进
   `loop.policy_merge_trace`，也没有调用 `apply_consumed_budgets()`；
5. LangGraph `_ctx_supervisor()` 会把 merge result 加入 trace，但同样没有更新
   `loop.per_obligation_budgets`；
6. 全仓静态搜索显示 `apply_consumed_budgets` 只有 import 和单元测试调用，没有生产调用。

结果是：`build_decision_context()` 每轮看到的 `budget.remaining()` 可能一直是初始值。已有测试
`tests/test_agentic_research_policy.py:756-836` 证明 helper 和 merge result 正确，却没有证明真实循环
连续两轮会减少预算。

#### 应保持的不变量

- 被 policy 拒绝的 proposal 消耗 0；
- 若 fallback decision 被接受，只消费 fallback 实际选择的 calls；
- schema/type error 在 dispatch 前发生时消耗 0；
- 一旦 dispatch 开始，即使工具失败或进程崩溃，本次调用也计入 hard total；
- 同一 operation/attempt 的恢复不得重复计费；
- checkpoint resume 后 remaining 与恢复前一致；
- direct driver 与 LangGraph topology 完全同语义。

#### 最窄实现切面

`PROPOSAL`：不要在 supervisor 生成 proposal 时直接消费，因为 proposal 还可能被 policy 替换。
在 policy merge 选出 decision 后、tool dispatch 前做一次 reservation/consume：

```text
merge_result.decision accepted
  -> apply_consumed_budgets(loop.per_obligation_budgets,
                            merge_result.consumed_budgets)
  -> persist budget state / attempt trace
  -> execute pending calls
```

当前循环是串行的，先做不可变 budget replacement 即可；只有真正引入并发 fan-out 时才需要
Harness 式 reservation/CAS。不要提前把串行问题扩大成分布式预算服务。

#### 必需测试

| 测试切片 | 预期 |
|---|---|
| direct driver 连续两次同 kind | remaining 逐次下降，耗尽后 policy 阻断 |
| LangGraph 同场景 | 与 direct driver trace、remaining 一致 |
| proposal 被 policy fallback 替换 | 只消费 fallback calls |
| STOP_BLOCKED / RECORD_GAP | 无 tool budget 消费 |
| tool 返回 failure | 已 dispatch 的 hard count 仍消费一次 |
| snapshot/resume | 已消费数不重置、不重复应用 |

建议落在 `tests/test_agentic_research_policy.py` 的 helper 单测之外，再补
`tests/test_agentic_v3_e2e.py` 和 `tests/test_agentic_research_checkpoint_resume.py` 的纵向用例。

### 3.3 MODEL-ONLY/PATH-GAP：最佳状态没有绑定候选产物闭包

现有模型本身是扎实的：

- `research_models.py:730-852` `QualityStateV2` 绑定 run/snapshot/tree 和 safety/content/
  minimality/cost digest；
- `quality_state_dominates()` fail closed 地拒绝 safety、coverage、unique claim、validated sentence
  或 minimality 回退；
- `quality_state_v2.py:261-345` 可以从 coverage、claim set、validation report 计算状态；
- `tests/test_agentic_research_models.py` 与 `tests/test_agentic_quality_state_v2.py` 覆盖维度与 Pareto。

但真实 research loop 的路径是：

1. `initial_loop_state()` 产生 empty current/best；
2. `restore_loop_state_from_snapshot()` 可恢复 current/best；
3. 全仓对 `loop.current_quality_state =` 的生产赋值只出现在恢复路径；
4. observation pipeline 调 `quality_state_selector_node()` 时仍比较原 current；
5. `compile_candidate_node()` 随后才生成 `EvidencePacketSetV3`、`CodeFactSetV1`、
   `AtomicClaimSetV3` 并放入 `loop.compiled_evidence`；
6. compile success 没有计算新的 QualityState，也没有生成“这组产物被接受为 best”的清单。

`best_quality_state_ref` 当前是 quality content digest；不可变 loop payload 虽然同时保存 quality 对象和
compiled evidence，但没有一个对象明确声明“该 quality digest 精确评价哪一组 obligation artifact
digests”。因此模型与产物可能各自完整，却没有 accepted closure。

#### 不建议的修法

- 不要只在 compile 后写 `loop.current_quality_state = ...`，却仍让 best ref 指向无清单 digest；
- 不要让 candidate 覆盖 `loop.compiled_evidence` 后再尝试回滚；
- 不要把“工具写出了 artifact”当成“quality candidate 已接受”；
- 不要创建与 `EvidencePacketV3/CodeFactV1/AtomicClaimV3` 平行的新事实对象。

#### 建议的最小 accepted manifest

`PROPOSAL`：在现有不可变 artifact 之上增加控制平面封套，而不是第二套事实模型：

```text
AcceptedResearchStateV1
  manifest_id
  attempt_id
  run_id
  repo_snapshot_id
  project_tree_hash
  graph_contract_version
  agenda_digest
  predecessor_manifest_digest
  obligation_artifacts:
    obligation_id -> packet_digest / fact_digest / claim_digest / gap_digest
  quality_state_digest
  policy_trace_digest
  tool_trace_digest
  acceptance_report_digest
  terminal_status
  content_digest
```

提交协议：

```text
compile under attempt_id
  -> validate packet/fact/claim closure
  -> recompute coverage + current QualityState
  -> compare current vs incumbent best
  -> write immutable candidate manifest
  -> if dominates and safety holds: atomically switch accepted-manifest ref
  -> otherwise record discarded manifest, preserve incumbent
```

单进程串行实现可以先用内容寻址 manifest + 原子 replace 指针；不需要立刻引入数据库事务。

#### 必需测试

- compile candidate 成功后 current quality 必须非空并绑定 exact claim digest；
- inferior candidate 不改变 accepted manifest/ref；
- candidate validation 抛错时 incumbent refs 与 digest 完全不变；
- cancellation 在 commit 前后分别落 discarded/accepted；
- crash 在 candidate write 后、pointer switch 前恢复为未接受；
- crash 在 pointer switch 后可由 manifest digest reconcile；
- snapshot 中 best quality 与 accepted manifest closure 不一致时 strict resume 阻断。

### 3.4 RISK：终态 checkpoint 的发射时点

当前不可变 checkpoint 很强，但 LangGraph 时序需要一个专门故障测试：

- `_ctx_observation()` 在 observation pipeline 末尾调用 `snapshot_loop_state(loop)`；
- 后续 critic、compile、advancer 可能修改 obligation status、compiled evidence、turn counter；
- `_ctx_terminate()` 才设置 `loop.terminated` 和 `termination_reason`；
- `_ctx_terminate()` 本身返回 `ResearchLoopResult`，未见再次发射更新后的 `loop_state_snapshot`。

这不等同于已证明存在 bug，因为外层 wrapper/checkpointer 可能另有最终保存；但仅从此路径不能证明
final state channel 一定含终态 sidecar。应添加 topology 级测试：从真实 subgraph 终止后取 checkpoint，
在新实例恢复，确认 `turns_executed=0` 且不调用 prefix/model，并且 compiled evidence 与最后 obligation
状态完整。

## 4. Semantic frame 与 Method Writer 审计

### 4.1 当前已经完成的部分

`method_architect.py:661+` 的 `replan_moves_with_trace()` 已经不只是旧的标题/关键词模板：

- 保留 frozen section/unit 结构；
- 从 supported facts、claims、equations、configurations 和 typed relations 生成 frame；
- 保留 claimless critical/high obligation 为 unresolved；
- 生成 move-specific anchor IDs；
- section dependency 只从 typed relation 的 source/target 建立，不用 scalar JSON 形状猜方向；
- trace `schema_version=1.3` 记录 input digests、frame、moves、anchors、obligations、dependencies。

`publication_method_writer.py:250-526` 也会重算 section frame 和 exact move anchors，并在 callback
resume 前校验 request/artifact 绑定。这些均应保留。

现有测试已经覆盖：

- semantic replan 基本结构；
- typed relation 的跨 section producer/consumer dependency；
- `loads_weights` scalar object 不能成为 output；
- non-inventory closed-ID frame；
- claimless gap 保留；
- limitations move 不能被无关 claim 锚定；
- gap request 路由和 affected-only resume。

### 4.2 PATH-GAP：两套 frame compiler 会漂移

当前存在两个实现：

| 实现 | 位置 | 关系绑定行为 |
|---|---|---|
| unit frame | `method_architect.py:492-568` | 每个 slot 都拿到该 unit 的全部 relation IDs |
| section frame | `publication_method_writer.py:2240-2335` | 只有 relation source/target 等于 fact.subject 时才挂到 slot |

同一事实在 Architect trace 与 Writer prompt 中可能得到不同 `relation_ids`。更具体地：

- unit frame 将 `unit_relation_ids` 无差别附到每个 input/transformation/condition/output slot；
- section frame 只按 `fact.subject` 与 relation endpoint 相等判断；若 endpoint 对应 fact.object、参数、返回值
  或 canonical symbol alias，合法关系可能丢失；
- 两套 `_fact_role()` 都把未知 predicate 默认成 `transformation`；
- list-shaped object 被转成空 `entity`，导致输入/参数集合的可读语义丢失；
- dependency 记录和 slot relation 不是从同一个 resolver 导出，可能一处接受、一处拒绝。

当前测试覆盖“scalar 不猜 output”，没有覆盖未知 predicate、relation cross-contamination、list entity、
object endpoint、alias 或 Architect/Writer frame digest 同构。

### 4.3 默认 transformation 违反 fail-closed

`_fact_role()` 的最后一行是 `return "transformation"`。这意味着任何新 predicate、拼写错误或 adapter
未升级的 predicate 都会获得正面的算法/实现 move authority。

正确语义应是：

```text
known input predicate         -> input
known output predicate        -> output
known condition predicate     -> condition
known transformation predicate-> transformation
unknown predicate             -> unresolved / no positive role
```

未知不等于“没有价值”：它可以留在 audit trace，产生 Architect issue 或 writing research request；但不能
自动进入 positive Writer facts。

### 4.4 建议的单一 semantic resolver

`PROPOSAL`：把两套私有函数收敛到一个共享、无 prose 的编译器，例如现有 agentic 子系统内的
`semantic_argument_frame.py`。不要求一定新增这个文件名，但必须只有一个权威实现。

建议输出：

```text
SemanticArgumentFrameV1
  scope_id
  obligation_ids
  slots[]:
    role
    entity_refs[]
    fact_ids[]
    claim_ids[]
    equation_ids[]
    configuration_ids[]
    relation_ids[]
    qualifiers[]
  dependencies[]:
    relation_id
    relation_kind
    source_symbol
    target_symbol
    source_slot_ids[]
    target_slot_ids[]
  unresolved[]:
    source_id
    reason
    required_owner
  input_digests
  resolver_version
  content_digest
```

关系 resolver 必须同时满足：

1. relation ID 在 claim 的授权 relation closed set 中；
2. relation 本体存在于 frozen packet；
3. relation kind 在已知 allowlist；
4. endpoint 能通过 typed symbol/argument/output binding 连接到相应 fact；
5. 方向来自 relation 或 predicate contract，而非 list/scalar 形状；
6. 无法唯一绑定时进入 unresolved，不猜测。

Architect 与 Writer 都只消费该结构；Writer 仍拥有最终 prose，resolver 不生成句子模板。

### 4.5 move authority 应从同一 frame 导出

当前 `_move_anchor_ids()` 的方向是对的，但应收紧 anchor type：

| move | 最小有效证明 |
|---|---|
| algorithm/data flow | transformation facts + relevant relation/equation IDs |
| implementation realization | input/transformation facts，不能含未知 role |
| output/inference | closed output predicate或显式 output relation |
| configuration/branch | active/default/conditional config + condition fact |
| equation/derivation | validated equation/formalization artifact |
| limitations/mismatch | exact completeness/gap obligation，不以正面 fact 代替 |
| organization | author/literature/expository lane，不从 executable co-location 自动授权 |

move authority 输出不能只是一组无类型字符串。至少需要 `anchor_type + anchor_id + source_digest +
unresolved_obligation_ids`，否则 fact ID、equation ID、configuration ID 在消费端难以区分。

### 4.6 必需语义回归

1. 未知 predicate 产生 unresolved，不能生成 algorithm/implementation required move；
2. unit 有两条无关 relation 时，每个 slot 只携带真实 incident relation；
3. relation endpoint 对应 fact object/argument binding 时仍可精确关联；
4. list object 的 entity refs 不为空，且不会因为容器类型猜 producer；
5. claim 未授权的 packet relation 即使 endpoint 匹配也不能进入 frame；
6. relation kind 未知、endpoint ambiguous、alias collision 均 fail closed；
7. Architect frame 与 Writer frame 对同一 scope 产生相同 digest/slot closure；
8. frame serialization 继续通过 `_code_audit_sentences(...) == []`；
9. 同 unit 无关 fact 不能锚定 output/equation/config/limitations；
10. callback fulfillment 后只重算 affected section 的 move authority，其他 digest 不变。

## 5. Writer callback：已有强闭包与剩余认证缺口

### 5.1 已有完整路径

当前回调链已经接近 PydanticAI deferred work 的严格版本：

```text
Writer emits WritingResearchRequestV1
  -> route owner by authority lane
  -> owner produces WritingResearchCallbackArtifactV1
  -> bundle validates request/section/unit/lane/artifact IDs
  -> bundle digest persisted
  -> affected section checkpoint loaded and authenticated
  -> only affected Writer input receives callback artifact
  -> unaffected section output/response refs retained
```

文件型 callback artifact 还会在 prompt 前重算实际 SHA-256，missing/path escape/symlink/digest mismatch
都会阻断；opaque `span:`/`fact:` 等 ref 保持类型句柄，不被误解成本地文件。

### 5.2 PATH-GAP：`validated=True` 不是 validator receipt

`WritingResearchCallbackArtifactV1` 目前要求：

- request/section/unit/lane 精确相等；
- artifact ref 非空；
- artifact digest 以 `sha256:` 开头；
- `validated=True`。

但它没有绑定：

- 被满足的 `request.content_digest`；
- owning validator 的 ID/version；
- validation report digest；
- validator 输入 artifact digests；
- attempt/operation ID。

`writer_research_router.py` 的 repository provider 接受 dict 后，会补齐 binding 并设置
`validated=True`；Pydantic schema 能证明字段形状，不能单独证明 provider 真正执行了 owner validator。

`PROPOSAL`：在不改变现有 request/result 结构的前提下，给 callback artifact 增加：

```text
request_digest
validator_id
validator_version
validation_report_ref
validation_report_digest
operation_id
input_fingerprint
```

bundle 应验证 artifact.request_digest 等于当前 request.content_digest。相同 request ID 但问题、范围或
权限 lane 改变时，旧 artifact 必须冲突而不是继续复用。

### 5.3 callback 的重放语义

借鉴 OpenClaw delivery 与 Harness receipt，应区分：

- owner route 已执行；
- artifact 已写入；
- artifact 已验证；
- Writer 已消费并重写 affected section；
- rewritten section 已通过 reverse validation；
- resume marker 已清除。

只有最后三步完成才算 callback 闭环。若进程在 artifact fulfillment 后、Writer resume 前崩溃，恢复应
继续消费一次；若 Writer 已成功写 section 但清 marker 前崩溃，应通过 section output digest 与
operation receipt reconcile，避免重复模型调用。

## 6. Authoring projection：从 source digests 到 property receipt

### 6.1 当前强项

V3 projection 已绑定：

- packet、fact、claim 的内容摘要；
- equation 与 claim fact set 的一致性；
- repo snapshot/tree identity；
- projected/forbidden claims、stage groups、writing rules；
- projection 自身 digest。

这已经满足“projection 不是事实源”的大部分要求。

### 6.2 残余问题

目前不同投影/限制函数各自执行检查，但没有一个显式 receipt 表明：

- 使用了哪一版 transform；
- 哪些 invariant properties 被执行；
- 每个输入 ID 是 selected、dropped 还是 unresolved；
- dropped 的确定原因；
- 输出是否仍闭合所有 must-cover obligation；
- revision subset 没有改变最终 gate obligations。

OpenHands 的启发不是增加可变 EventLog，而是把 property intersection 明文化。

### 6.3 建议的投影属性

`PROPOSAL`：在现有 `AuthoringInputProjection` 或其 sidecar 中加入 transform receipt：

```text
ProjectionReceiptV1
  transform_id/version
  source_digests
  property_set_digest
  checked_properties[]
  selected_ids[]
  dropped_ids[{id, reason}]
  unresolved_ids[]
  output_projection_digest
```

最小 property 集：

1. every projected claim exists in frozen claim set；
2. every direct/relation ID exists in frozen packet closure；
3. qualifiers and wording boundary preserved；
4. equations bind the same facts/claims；
5. forbidden/gap text cannot enter positive payload；
6. no packet/fact/claim atomic group is partially projected；
7. revision subset can reduce Writer view but cannot reduce validation obligations；
8. projection output is provider-size safe without truncating authority content。

任一 property 失败应阻断 Writer input；不得通过删除失败 claim 来宣告 hard gate success。

## 7. Checkpoint 与 same-identity

### 7.1 已有边界

`LoopStateSnapshot` v2.0 使用内容寻址 payload；loader 拒绝 store root 外路径并重算摘要；strict resume
拒绝 tampered schema/payload。`AgentStateV3Record` 还验证 state schema 和 graph contract version，
`validate_resume_state_v3()` 绑定 repo snapshot/tree。

### 7.2 残余身份闭包

`_validate_terminal_resume()` 本身只检查：

- run ID；
- repo snapshot ID；
- project tree hash；
- termination reason；
- terminal status。

它没有直接检查模型/role profile、tool manifest、source authority policy digest、agenda digest 或 accepted
artifact manifest。部分信息可能存在于其他 artifacts/acceptance path，但 terminal fast path 在任何 prefix
或 model call 前返回，因此应该自己持有足够的终态 identity closure。

`PROPOSAL`：终态 snapshot 或 accepted manifest 绑定：

```text
state_schema_version
graph_contract_version
agenda_digest
source_authority_policy_digest
research_tool_manifest_digest
model_role_profile_digest
accepted_research_manifest_digest
verification_protocol_digest
```

模型版本不一定要进入所有纯静态 checkpoint；但如果恢复的 terminal artifact 被用于同身份 live
acceptance，就必须证明生成/验证所用角色配置没有改变。

### 7.3 stale propagation

借鉴 Hermes verification evidence，任何下列变化都应使 downstream verification stale：

- source/tree；
- packet/fact/claim/equation/configuration；
- Architect plan/frame；
- Writer/Editor/Rewrite output；
- callback artifact；
- model role/profile；
- gate implementation/protocol。

stale 应沿 artifact dependency graph 传播，不依赖文件 mtime 或“命令之前跑过”。

## 8. 工具副作用与 operation receipt

### 8.1 当前能力和边界

`tool_runtime.py` 已有：

- `FineGrainedToolContract.side_effects/idempotency_fields`；
- fsync + atomic replace；
- 由 tool/version/snapshot/input/model/config/schema 组成的 cache key；
- successful result-only cache。

但 `IdempotentToolCache.invoke()` 是：exists check → execute operation → atomic write。两个进程可同时
通过 exists check 并重复执行 operation。对纯读/确定性编译通常无害；对模型调用、外部写入、callback
side effect 或非幂等工具不够。

### 8.2 分层采用，不全面加重

`PROPOSAL`：

- 内容寻址的纯 deterministic 编译器：继续使用现有 cache；
- 有费用但无外部副作用的模型调用：记录 attempt/usage receipt，允许内容 retry，但总预算只计一次 dispatch；
- 可变 manifest/callback sidecar：operation ID + fingerprint + expected version/CAS；
- 外部或不可逆副作用：started/completed/failed/unknown-after-crash effect receipt；
- 最终 publication artifact：先写 immutable candidate，再原子切 accepted manifest ref。

不要给每个本地 read/search 工具增加数据库日志；只在重放会改变外部状态、花费预算或污染 accepted
lineage 的边界使用 durable receipt。

### 8.3 建议的 receipt

```text
ArtifactEffectReceiptV1
  operation_id
  attempt_id
  tool_name
  run_id
  target_ref
  input_fingerprint
  expected_version
  status: prepared | started | completed | failed | unknown_after_crash | conflict
  expected_digest
  actual_digest
  started_at / settled_at
  error_class
  content_digest
```

恢复规则：

- `completed` + fingerprint 相同：返回既有结果；
- 相同 operation ID + fingerprint 不同：conflict；
- `started/unknown`：检查目标 actual digest/外部事实，再决定完成或阻断；
- 目标已写且 digest 正确：reconcile 为 completed，不重放；
- 目标存在但 digest 不同：conflict，绝不覆盖。

## 9. 建议实施顺序（从属现有执行权威）

本文不新建 roadmap；以下只表示技术依赖顺序。

### 9.1 第一组：先关闭当前调用链丢失

1. 把 `PolicyMergeResult.consumed_budgets` 在 dispatch 前应用到 direct/LangGraph 两条路径；
2. 建立两条 topology parity 与 checkpoint resume 回归；
3. 统一 semantic frame resolver，未知 predicate fail closed；
4. 让 Architect/Writer/move authority 只消费同一 digest-covered frame；
5. 补 relation cross-contamination、list entity、unknown predicate、frame parity 测试。

这组不需要改变事实模型，也不需要引入并发/CAS。

### 9.2 第二组：让最佳状态成为真实提交协议

1. compile candidate 后从 exact artifact closure 计算 current quality；
2. 生成 immutable candidate/accepted manifest；
3. inferior/failed candidate 保留 audit 但不推进 accepted refs；
4. strict resume 验证 quality 与 artifact closure；
5. 增加 cancellation/crash fault injection。

### 9.3 第三组：补强回调和终态身份

1. callback artifact 绑定 request digest 与 validator receipt；
2. resume marker 增加 operation/reconciliation 语义；
3. terminal checkpoint 绑定 graph/tool/model/protocol identities；
4. 验证 topology 终止后保存的是最终 sidecar，而非 observation 前快照。

### 9.4 第四组：按副作用风险引入 durable receipts

优先覆盖 accepted manifest、callback sidecar、外部工具和费用型模型调用。纯内容寻址编译器保持简单。

## 10. 文件级工作包

| 工作包 | 主要文件 | 目标 | 不应修改的边界 |
|---|---|---|---|
| Budget wiring | `research_graph.py`、`research_nodes.py`、`research_policy.py` | accepted decision 在 dispatch 前精确落账 | 不削减 per-obligation/global gate |
| Quality commit | `quality_state_v2.py`、`research_graph.py`、`research_nodes.py`、checkpoint models | quality 绑定 artifact closure，candidate 原子接受 | 不新增平行 fact/claim 模型 |
| Semantic resolver | `method_architect.py`、`publication_method_writer.py`、argument models | 单一 frame、typed relation、unknown fail closed | 不生成 final prose，不扩大 code authority |
| Projection properties | `authoring_projection.py`、trust contracts | transform receipt 与原子组完整性 | 不用过滤失败 claim 通过 gate |
| Callback receipt | `method_argument_models.py`、`writer_research_router.py`、`publication_method_writer.py` | request digest + validator report + replay identity | 不让 harness 自证 `validated=True` |
| Terminal identity | `state_v3.py`、`checkpointing.py`、`research_graph.py` | same-identity fast resume | 不把旧运行升级成新协议成功 |
| Effect receipt | `tool_runtime.py` 及有限 side-effect callers | started/completed/unknown/CAS | 不给纯读工具增加无必要持久化 |

## 11. 纵向验收矩阵

实现后，不能只报告 helper test count。至少需要下列纵向证据：

| 场景 | 注入点 | 必须证明 |
|---|---|---|
| policy proposal 被替换 | merge 前后 | 只消费实际 decision budget |
| tool dispatch 后抛错 | tool boundary | 预算计一次；effect 状态明确 |
| candidate validation 失败 | compile/quality 之间 | incumbent refs/digests 不变 |
| cancel 与 commit 竞态 | accepted manifest switch | commit 前取消胜；commit 后可 reconcile |
| snapshot payload 篡改 | immutable loader | strict resume 阻断且零模型调用 |
| terminal checkpoint 重启 | fresh graph instance | 零 prefix/model；最后 obligation/compiled closure 不丢 |
| unknown predicate | frame compiler | 无 positive role/move authority，产生 unresolved |
| unrelated relation | frame compiler | 不污染 slot/move anchor |
| callback request 被修改但 ID 相同 | fulfill/resume | request digest conflict |
| callback artifact 已写、resume 前崩溃 | one-shot marker | 恢复后只消费一次 |
| Writer 已写、marker 未清 | section checkpoint | digest reconcile，不重复模型调用 |
| projection property 失败 | Writer input boundary | 不调用 Writer，不过滤后继续 |
| validation 后 artifact 改变 | final recheck | verification stale，不能发布 |

## 12. 明确不建议现在做的事

1. 不用 OpenHands EventLog 替换现有内容寻址 artifact/checkpoint；
2. 不在预算尚未真实落账前引入并行 Research children；
3. 不把 PydanticAI capability error hook 用作最终证据门；
4. 不把 OpenClaw delivered/committed side effect 当作内容质量通过；
5. 不让 unknown predicate 默认进入 transformation；
6. 不通过删除 claim、降低 obligation、放松 matching 或把缺失输出当成功来修复 projection；
7. 不让 callback provider 用一个裸 `validated=True` 代替 owning validator report；
8. 不把截断 tool output 当作权威 evidence；
9. 不因静态测试成功就声明 D5、rollout、default cutover 或 release freeze。

## 13. 架构结论

Code2Paper 当前并不缺“Agent 框架骨架”。它已经拥有比参考框架更严格的证据类型、写作权限分离、
不可变 payload、callback 精确恢复和最终反向验证。真正的架构风险来自**模型存在但运行链未闭合**：

- budget 计算没有变成真实消费；
- quality 比较没有变成 artifact closure 的 accepted commit；
- semantic frame 在两个消费者间有不同关系语义；
- callback 的绑定很强，但 owner validation 仍缺可审计 receipt；
- checkpoint 内容完整性很强，但终态 same-identity 与最终发射时点仍需纵向证明。

因此下一步最有价值的工作不是增加更多 Agent 或抽象层，而是把这五处边界做成一条可故障注入、
可恢复、可反查的提交链。完成后，外部框架的核心优点才真正转化为 Code2Paper 的信任能力。
