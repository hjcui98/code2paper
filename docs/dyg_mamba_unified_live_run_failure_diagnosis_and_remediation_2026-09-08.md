# Unified Context 第一轮修复后真实测试失败复盘、全局设计修订与第二阶段执行方案（2026-09-08）

> `as_of`: 2026-09-08
>
> 性质：上一轮 Unified Context 修复后的系统级失败复盘与第二阶段执行方案；不是 live
> acceptance、D5、cutover 或 release 结论。
>
> 上位执行依据：
> [十项目 Method 信息缺失根因、Unified Context 设计修订与优化执行方案（2026-09-06）](code2paper_unified_mechanism_context_quality_failure_diagnosis_and_optimization_execution_plan_2026-09-06.md)。
>
> 文件名保留 DyG-Mamba，是因为本轮第一份真实失败证据来自 DyG；本文范围已经提升为十项目
> 共同修复，不把 DyG 的表面症状当成局部特例。

## 1. 执行结论

上一轮修复没有走错总体方向：Unified mode 已进入真实 authoring 路径，source manifest、intent
scheduler、机制 completeness、逐页 actual request、Realizer 权限边界和独立 receipt 等关键部件在
当前代码中已经出现。DyG 真实运行失败说明的不是“再调几个阈值即可”，而是第一版实现仍把三个
用途不同的对象混在一起：

1. 完整、无损、供审计和重建使用的全量证据归档；
2. 某个消费者完成一个局部任务所需的最小闭包；
3. 模型实际要执行的有界调用计划。

当前实现把三者都表达成 `mechanism_context_page_manifest_v1`。结果是：上游 23 个没有 owner 的
seed 被并成一个“全项目机制”，全量归档被切成 189 页；Formalizer 再对 160 个公式义务逐个扫描
全部 189 页，形成最多 30,240 次请求。单次请求虽然只发送一页，系统总调用量仍然失控。

本轮 DyG 运行因此必须判为 **FAIL**，十项目 live 矩阵继续保持停止。下一阶段不能只优化 DyG
分页，也不能只减少公式义务，而应完成以下全局修订：

- 将全量归档、消费者工作集和实际调用计划拆成三层合同；
- 将调用调度从“obligation 扫描 pages”改为“page 一次处理其局部 obligations”；
- 以显式 owner 和有向 typed data/control path 划分机制，禁止弱相关证据传递合并；
- source artifact、closed-set、Research core intent、机制连通性和调用预算在首个模型请求前统一准入；
- 将 obligation、page、request、response 和 receipt 增量持久化，使中断可观测、可恢复；
- 先完成 offline 十项目重建，再按 EBCAR → LinearRAG → DyG 做三个受控 pilot，最后才启动十项目
  live matrix。

总体目标仍是上一轮方案定义的目标：从真实 repository evidence、作者意图和 Research 结果构建
无损、可追踪、可恢复、调用有界的 Method authoring 闭环，并通过十个真实项目验证信息保真；本文
不降低 Verified、evidence、formula、lexical authority 或 final-integrity gate。

## 2. 本文证据边界

### 2.1 绑定的真实运行

- 代码：`7701a7eb19c4e53a3016185898933440bc68c742`
- 模式：`unified`
- 模型：`qwen36-27b-nvfp4`
- 模型上下文：131,072
- profile：`tests/live/profiles/qwen36_vllm_budgeted.example.env`
- batch root：`/tmp/c2p-unified-live-matrix-20260908-7701a7e`
- DyG root：`/tmp/c2p-unified-live-matrix-20260908-7701a7e/dyg`
- 主日志：`/tmp/c2p-unified-live-matrix-20260908-7701a7e/logs/dyg.log`

preflight 的 `/health`、`/v1/models` 均返回 200；启动时 running=0、waiting=0、KV cache=0。没有
证据表明本次失败由启动前模型不可用或已有队列拥堵造成。

本次不是 clean-checkout acceptance。worktree 当时存在未跟踪 launcher 和其他用户文件，launcher
只记录 commit SHA，没有记录脚本 digest。该运行足以暴露生产调用结构，不能据此声明 release 状态。

### 2.2 能确认与不能确认的事实

可以确认：

- Unified context 和 189 页 manifest 已成功生成；
- 生产路径进入 Formalizer，尚未进入 Writer；
- Formalizer 的循环结构允许最多 `160 × 189 = 30,240` 次真实请求；
- 人工停止后没有 `run_end`、summary row 或最后完成位置；
- 最终 Candidate/Verified 和完整 formula/receipt 产物不存在。

不能确认：

- 实际完成了多少次模型请求；
- 最后运行到哪一个 obligation/page；
- 停止时的准确 signal、KV cache、queue 和模型端终止原因；
- Writer、Realizer、Binder 在这份 DyG 输入上的真实行为。

`dyg.log` 的 589 条 `SyntaxWarning` 来自 JSON/LaTeX response recovery 对 `ast.literal_eval` 的回退，
不能当作 589 次请求计数。当前进度没有增量 durable ledger，日志不能补足这一证据缺口。

## 3. 第一轮修复的真实状态：哪些已实现，哪些仍是假闭环

不能把旧问题列表原样搬到本轮。对当前代码复核后，状态如下。

| 旧阻断项 | 当前代码状态 | 本次真实运行能否验收 | 本轮结论 |
|---|---|---|---|
| Formalizer/Writer actual-byte identity | 两端已按单页构造实际请求，并保存 request identity | Formalizer 未返回，Writer 未开始 | 实现部分成立；端到端未验收，且总调用计划无界 |
| Writer receipt 被 Realizer 替代 | 最终 gate 已分别要求 Formalizer receipt 和精确 section Writer receipt | 未到最终 gate | 代码已修；live 未验收 |
| Realizer 越权模板造词和自造 witness | 当前 Realizer 会调用模型，校验 caller、允许的 detail/formula/witness；Composer 不再为缺失 detail 编造占位句 | 未到 Realizer | 代码已修；live 未验收 |
| source manifest 未进入 closure | 产品持久化、Writer loader 和 compiler 参数已接通 | replay 没有从 `--repo` 重建缺失 source artifacts | 产品接线改善；replay/兼容路径仍失败 |
| core-intent scheduler 未接生产图 | Research graph 已刷新 ledger 并调用 `check_next_schedule()`；operation 归属改为按 span/node 精确映射 | 本次复用了冻结 Research，没有重跑 scheduler | 代码已实现；纵向与十项目行为未验收 |
| completeness validator 未调用、`precedes` 假连通 | validator 已进入生产路径，connectivity 不再靠相邻排序边证明 | `partial` readiness 仍绕过失败 | 检查存在；准入策略仍 fail-open |
| story-spine 名称不匹配 | 产品同时写出兼容 alias，collector 也已覆盖 | replay 主要消费冻结 projection | 代码已修；旧 artifact 兼容仍需验收 |

相关实现入口：

- [formalization_agent.py](../src/code2paper/agentic/formalization_agent.py)
- [section_writer.py](../src/code2paper/llm/section_writer.py)
- [publication_method_writer.py](../src/code2paper/agentic/publication_method_writer.py)
- [mechanism_realizer_composer.py](../src/code2paper/agentic/mechanism_realizer_composer.py)
- [research_graph.py](../src/code2paper/agentic/research_graph.py)
- [autonomous_method_agent.py](../src/code2paper/agentic/autonomous_method_agent.py)
- [mechanism_context_compiler.py](../src/code2paper/agentic/mechanism_context_compiler.py)

因此第二阶段的正确起点不是重复修已经落地的局部补丁，而是补齐它们之间的产品合同、准入和真实
纵向证据。

## 4. DyG 失败链的量化诊断

### 4.1 时间线和终止边界

| 时间 | 耐久证据 | 结论 |
|---|---|---|
| 00:12:04 | `launcher.log` 的 `run_start` | DyG 启动 |
| 00:22:15 | `mechanism_context_set_v1.json` | closure/context 完成 |
| 00:22:18 | `mechanism_context_page_manifest_v1.json` | 189 页 manifest 完成 |
| 09:40:56 | `dyg.log` 最后修改 | Formalizer 阶段仍在 response recovery |
| 人工停止后 | 无 `run_end`、无 summary row | 没有正常收尾 |

缺失产物包括：

- `mechanism_formula_obligations_v1.json`
- `mechanism_formula_packages_v2.json`
- Formalizer/Writer delivery receipts
- `narrative_plan_v3.json`
- `publication_writer_result_v1.json`
- Candidate、Verified、最终 validation/quality/content trace

生产路径在 `_run_mechanism_formalizer()` 整体返回后才持久化 obligations 和 packages，见
[publication_method_writer.py](../src/code2paper/agentic/publication_method_writer.py)。所以准确边界是：
**Formalizer 已进入但未返回，Writer 尚未开始。**

### 4.2 Authoring closed-set 在模型调用前已经不一致

| 指标 | DyG 实际值 |
|---|---:|
| `authoring_projection_v1.hard_gate_passed` | false |
| projected claims | 83 |
| 未进入任何 stage packet 的 claims | 2 |
| Method sections | 5，全部 incomplete |
| argument units | 13，其中 11 unsupported |
| method units | 6，全部 `intent_specification/unresolved` |
| briefs | 23，全部 `may_enter_verified=false`、`requires_caveat=true` |
| facets / alignments | 25 / 25，全部 unresolved |
| publication field candidates | 0 |
| typed deferred fields | 25 |

冻结 baseline 的 81 个 claims 自身 hard gate 通过；rebuild 又加入 2 个 L2 math claims，stage packet
仍只覆盖 81 个，导致 83/81 closed-set 不一致。Candidate 允许语义不完整进入 review，不等于允许
集合内部不一致进入昂贵模型调用。后者是结构错误，必须在 admission 阶段阻断。

Research sidecar 还存在口径冲突：research agenda 的 29 项中有 16 pending、7 supported、6 partial，
但 obligation coverage 同时报告 5/5 must-cover 已 terminal+supported。即使 scheduler 代码已接入，旧
checkpoint 的 ledger 也不能仅凭一个聚合字段被视为闭合。

### 4.3 23 个 seed 被合成一个全项目机制

用生产 `_collect_seed_data()` 和 `_merge_mechanism_seed_rows()` 对耐久输入重放：

| 指标 | DyG 实际值 |
|---|---:|
| merge 前 seed | 23 |
| 带 explicit mechanism owner 的 seed | 0 |
| merge 后 mechanism | 1 |
| story / brief / facet | 23 / 23 / 25 |
| closure operations | 697 |
| details | 263（118 core、145 supporting） |
| edges | 728（494 feeds、234 precedes） |

当前合并允许 evidence overlap、fact producer/consumer 或直接 graph link 触发 union；union-find 又会把
弱相关关系传递闭包。没有 explicit owner 时，一个公共 claim/span 就可能成为合并桥。最终机制名称
来自单个 `O-COMPONENT-01`，内容却覆盖全部阶段、组件、组织说明和 rationale。这不是一个可供论文
叙述的技术机制，而是整个 authoring graph 的连通包。当前三种合并条件和 union 入口见
[mechanism_context_compiler.py#L1157](../src/code2paper/agentic/mechanism_context_compiler.py#L1157)。

编译器还把机制级 `facet_ids`、`brief_ids`、`obligation_ids`、`author_statement_ids` 复制到每一个
detail。错误机制越大，detail 和 page 中的重复 provenance 越多。

### 4.4 结构数量很大，但真实数据/调用闭包仍为空

| 指标 | DyG 实际值 |
|---|---:|
| behavior graph nodes | 1,002 |
| relations | 39 |
| `TRUE_BRANCH` / `FALSE_BRANCH` | 21 / 7 |
| `RETURNS_TO` / `NEXT_CONTROL` | 8 / 3 |
| typed call relation IDs | 0 |
| typed data relation IDs | 0 |
| typed control relation IDs | 0 |
| disconnected core details | 116 |
| active path unknown | 7 |
| completeness failures | 124 |
| readiness | `partial` |
| `connected_input_to_output` | false |

当前 completeness score 是若干布尔项的平均值，仍可得到 0.8；生产 gate 又只在
`repository_ready` 时对 validator failures 抛错。于是最需要阻断的 `partial + disconnected + unknown`
反而继续进入模型调用。validator 的生产调用与 `repository_ready` 条件门分别见
[publication_method_writer.py#L1125](../src/code2paper/agentic/publication_method_writer.py#L1125) 和
[publication_method_writer.py#L1150](../src/code2paper/agentic/publication_method_writer.py#L1150)。

修复重点不是把阈值从 0.8 改成 0.9，而是把结构完整性与语义可写性分开：source、owner、typed path、
closed-set、digest 和调用预算属于结构准入，缺任一项不得调用模型；作者意图尚未被代码验证属于语义
状态，可进入 Candidate review，但不能伪装成 repository verified。

### 4.5 source manifest 在产品路径存在，在 replay 路径消失

当前产品侧会持久化：

- `repo_snapshot_v2`
- `symbol_index_v2`
- `repository_source_manifest_v1`
- `implementation_scope_v1`

Writer loader 也能加载 source manifest 并传给 unified compiler。但 `run_authoring_replay.py` 只在冻结
目录已有这些 artifact 时复制；即使传入 `--repo`，也不会在进入 Writer 前补建它们。本次冻结 DyG
没有 source manifest、repo snapshot 或 symbol index。optional artifact 仅复制的路径见
[run_authoring_replay.py#L1660](../scripts/run_authoring_replay.py#L1660)，实际 Writer 调用只接收 copied
artifact map，见 [run_authoring_replay.py#L1865](../scripts/run_authoring_replay.py#L1865)。结果为：

| 指标 | DyG 实际值 |
|---|---:|
| details | 263 |
| `source_kind=unknown` | 263 |
| 空 `source_manifest_digest` | 263 |
| 仍标为 `repository_verified` | 256 |

`unknown` 没被列为 excluded，authority 判定又主要依赖 operation activity，于是“没有 source authority”
被误解释为“没有发现排除理由”。正确语义必须是：先按 manifest entry 拆分可分离的 source atoms；只有
命中明确允许的 owned source partition 才能成为 repository verified，剩余 `unknown`、不可拆 `mixed` 或
missing-manifest partition 一律 unresolved。

### 4.6 189 页不是安全分页，而是重复膨胀后的传输格式

| 指标 | DyG 实际值 |
|---|---:|
| pages | 189 |
| manifest bytes | 15,087,232 |
| 累计估算 token | 2,594,808 |
| page token min / mean / max | 9,960 / 13,729 / 18,724 |
| singleton / double-detail pages | 115 / 74 |
| blocking page | 0 |

主要重复字段累计体积：

| 字段 | 累计重复 bytes |
|---|---:|
| details | 3,809,223 |
| unresolved items | 1,592,514 |
| author intent | 1,318,653 |
| core detail IDs | 1,061,991 |
| scientific goal | 70,686 |

每页都携带全局 header、全部 unresolved/core IDs 和累计 provenance。`MAX_MECHANISM_SLICES=64` 也被
动态上限覆盖，实际上没有形成机制级总页数保护。manifest 只验证单页不超预算，却不验证总页数、
总 token 和计划调用次数。重复字段的构造见
[mechanism_context_projection.py#L263](../src/code2paper/agentic/mechanism_context_projection.py#L263)，动态
slice 上限见 [mechanism_context_pages.py#L205](../src/code2paper/agentic/mechanism_context_pages.py#L205)。

### 4.7 Formalizer 的真正复杂度是 `obligation × page`

本次共构建 160 个 preferred obligations：

- 153 个 detail-scoped obligation 没有 equation binding；
- 7 个绑定 equation；
- deterministic package 为 0；
- 14 个 equation span 虽都标记 supported，但多为 `x+y`、`x*y` 一类 incidental expression，不能
  直接当成目标方法公式。

Formalizer 外层遍历每个 required/preferred obligation，内层遍历全部 shared pages。某页得到有效
package 后仍继续扫描剩余页面，以完成全 manifest receipt。最坏请求数：

```text
160 obligations × 189 pages = 30,240 Formalizer calls
```

这与“单次 request 未塞入全部 pages”不矛盾：actual-byte identity 的局部修复成立，但整体调度仍是
不可接受的笛卡尔积。公式生成需要改为 page-centric batch：一页一次处理该页绑定的全部 obligations，
跨页依赖通过确定性的 join page 显式表达，失败后仅对缺失 obligation 做有界 repair。当前逐页内层
循环和“成功后仍继续”的注释见
[formalization_agent.py#L1823](../src/code2paper/agentic/formalization_agent.py#L1823)，外层 obligation 循环见
[formalization_agent.py#L1924](../src/code2paper/agentic/formalization_agent.py#L1924)。

### 4.8 中断不可恢复使成本进一步放大

当前 obligation、package、request receipt 和 progress cursor 在整个 Formalizer 返回后才写。长任务
被停止后没有 durable evidence 表明哪些调用成功，也无法从下一页继续。恢复只能从 obligation 0/page 0
重来，重复消费模型时间。

这不是单纯的日志不足，而是 checkpoint contract 缺失。每个实际 request 完成后都应原子持久化 request
digest、page ID、task IDs、response digest、解析状态和 attempt；聚合 artifact 只能由这些事件归并产生。

## 5. 从 DyG 外推到十项目的系统根因

DyG 的数字是项目特定的，以下根因是 generic production logic，十项目都受影响。

### GRC-1：Archive、workset、invocation 三种职责被同一 manifest 承担

全量归档需要无损；消费者输入需要局部最小闭包；调用计划需要有界和可恢复。让一个 page manifest
同时满足三者，必然在“丢信息”和“重复发送全部信息”之间摆动。

### GRC-2：证据相关性被误当成机制所有权

共同 span、claim、brief 或 graph 邻接可以说明两个节点有关，不能证明它们属于同一机制。当前传递式
union 会把论文组织、动机、共享数据和真正执行链合在一起，使分页、公式和 Writer scope 同时失真。

### GRC-3：Candidate 可容忍未知被扩张成结构 gate 可 fail-open

Candidate 可以叙述“作者提出但代码未确认”的内容，但 source manifest 缺失、owner 缺失、closed-set
不一致、typed path 不连通和 digest 不一致不是 Candidate 语义，它们是系统完整性错误。

### GRC-4：Receipt 被设计为“看过所有页面”，而不是“完成声明的任务闭包”

为了证明共享上下文一致，Formalizer 和 Writer 被迫消费整个 manifest。正确证明对象应是 invocation
plan 声明的 required page set；receipt 要覆盖该集合和实际 bytes，不要求每个任务重复读取所有页面。

### GRC-5：聚合 artifact 代替了事件级 durable progress

长模型阶段只有函数返回后才有正式产物，使监控、失败归因、resume 和成本核算都不可靠，也让 live
测试必须依赖稀疏日志猜测进度。

## 6. 第二阶段全局设计修订

### 6.1 三层数据合同

以下为待实现的新合同名称；在代码落地前不得把它们写成“已存在”。

#### A. `UnifiedContextArchiveV2`

用途：完整证据真相、审计、重建和 reverse validation，不直接作为每次模型请求正文。

必须包含：

- repository snapshot/tree hash、source manifest digest、authoring/research digests；
- mechanism、detail、operation、typed edge、equation、claim、intent 和 evidence 的去重表；
- primary owner、shared reference、authority、unresolved reason；
- 所有 ID 到源 artifact/span/symbol 的反向索引；
- schema、compiler version 和 deterministic archive digest。

归档必须无损，但不要求模型一次或重复读完整归档。

#### B. `ConsumerWorksetManifestV2`

用途：从 archive 中确定性投影出消费者完成局部任务所需的最小闭包。

每个 workset 包含：

- archive 中只保存一次的完整 mechanism header；
- 若干自包含的 detail/dataflow/formula technical pages；每页只物化本次调用需要的最小
  `mechanism_id/purpose/authority` header，不复制完整 author intent、全局 unresolved 或全部 core ID；
- 必要的 cross-page join pages；
- workset 对应的 mechanism、section、formula obligations 和 required page IDs；
- 从 page 中每个原子返回 archive ID 的 projection proof。

每个 LLM invocation 只携带一个自包含 technical page；跨页依赖必须先确定性物化成一个 join page，
不得让模型在运行时扫描其他页。同一个 `page_id` 在 Formalizer、Writer、Realizer/Binder 需要共享时，
其 `technical_bytes` 必须完全相同；角色 prompt 和完整 request envelope 可以不同。不要求任何角色读取
与其任务无关的页。

#### C. `ConsumerInvocationPlanV1`

用途：按 phase 冻结实际调用次数、顺序、预算和恢复点。首个模型请求前必须冻结 Formalizer phase 的
精确 plan；Writer/Realizer plan 若依赖 Formalizer/Narrative 输出，则生成带 `parent_plan_digest` 的不可变
后续 revision，并在对应 phase 第一个请求前再次 admission。

每个 invocation 明确：

- `consumer_role`、`task_ids`、`mechanism_id`、可选 `section_id`；
- 唯一 `page_id`、预期 technical-bytes digest 和该角色自己的 request-envelope digest；
- max attempts、timeout、input/output token budget；
- dependency invocation IDs；
- checkpoint key 和成功判定。

#### D. `RunInvocationBudgetEnvelopeV1`

用途：在整个 run 的第一个模型请求前冻结所有 phase 可消耗的 calls/tokens/repairs 上界。后续 plan
revision 只能在剩余 envelope 内分配，不能因已有部分结果而扩大总预算。

每个 phase plan 必须在 admission 中给出精确 planned calls 和 planned input tokens；初始 admission
同时给出后续 phase 的保守 reservation。任一 plan 或 reservation 超过 profile budget 时应在该 phase
调用前阻断，而不是运行数小时后由人工发现。

### 6.2 核心不变量

1. **归档无损**：任何被采用或拒绝的 claim/detail/formula 都可回到原始 source/intent/research 证据。
2. **page immutable**：相同 page ID 的 canonical technical bytes 在所有消费者中完全一致；不同角色的
   system prompt、task metadata 和完整 request digest 不要求相同。
3. **任务闭包明确**：workset 声明 task 所需 page 集；每个 invocation 只消费其中一个 page。跨角色
   identity 只比较 required-page 集合的交集，不强迫 section Writer 消费 Formalizer 的全部页。
4. **不做笛卡尔积**：任何 consumer 不得以 task 为外层重新扫描全 manifest；调用总量必须由冻结的
   invocation plan 直接计数。
5. **source fail-closed**：先按 source span/entry 拆分 authority 原子；允许的 first-party 原子可保留，
   excluded 原子单独拒绝；不能拆分的 unknown/mixed 原子及 missing digest 不得成为 repository verified。
6. **owner fail-closed**：有唯一 primary owner 的跨机制 detail 才能通过 `SharedDetailRefV1` 被次级引用；
   完全无 owner 的 detail 只进入 unresolved sidecar，不进入 consumer workset，core owner 缺失直接阻断。
7. **有向连通**：input→output 必须由 typed data/call/control path 证明；排序产生的 `precedes` 不算。
8. **实际请求 receipt**：receipt 只能由真实 request/response event 生成，不能预写 `accepted=true`。
9. **角色 receipt 独立**：Formalizer、section Writer、Realizer 和 Binder 的 required receipt 不可互相替代。
10. **中断可恢复**：完成的 invocation 不重复执行；resume 前校验所有 upstream/page/request digests。

### 6.3 Page-centric Formalizer

旧结构：

```text
for obligation in obligations:
    for page in all_pages:
        call_formalizer(obligation, page)
```

新结构：

```text
for page_task in invocation_plan.formalizer_pages:
    call_formalizer(page_task.local_obligations, page_task.page_bytes)

for missing_obligation in bounded_repairs:
    call_formalizer(missing_obligation, missing_obligation.repair_join_page)
```

主阶段请求数上界应为 `formalizer_page_count`，不是 `obligation_count × page_count`。同一页上的多个
obligations 用结构化 batch 一次返回；解析器逐 obligation 校验，失败项进入有界 repair，成功项不重跑。

必须同时满足以下可计算上界：

```text
C_F_main   = |formalizer_invocations|
C_F_repair <= min(|failed_obligations|, configured_repair_call_limit)
C_F_total  = C_F_main + C_F_repair

每个主 invocation：1 page，1..max_obligations_per_page 个 obligations
每个 repair invocation：1 deterministic join page，恰好 1 个 failed obligation
```

`max_obligations_per_page`、`configured_repair_call_limit`、总 input-token budget 和角色 output reserve 必须
来自 live profile；live profile 缺任一预算即 admission FAIL，不允许使用“无限制”默认值。

跨页公式不得由 Formalizer 临时搜索全 manifest。compiler 应构造 join page，包含被引用 operands、
equations、producer/consumer edges 和 source spans；Formalizer 与 Writer 共享这份 join page 的 exact bytes。

### 6.4 Section-scoped Writer

Writer 不再让每个 section 消费机制的全部 pages。Narrative planner 先确定 section 所属 mechanism、details、
formulas 和 claims，再由 workset builder 求该 section 的 required page closure。

receipt 分两级：

- `SectionWriterReceiptV2`：证明该 section 的每个 required page 被真实 request 消费且 bytes 匹配；
- `WriterAggregateReceiptV2`：证明全部要求的 section receipts 存在、无重复归属冲突，union 覆盖计划集合。

Realizer receipt 只能证明 Realizer 自己的 invocation，不能补 section Writer 缺口。Binder 只接受来自
授权 lexical producer 的文本和独立 receipt。对共享 technical page，identity gate 比较
`page_id + technical_bytes_digest`；Formalizer 和 Writer 各自保存不同的 request-envelope digest。

### 6.5 机制划分与 owner 算法

机制构建改为以下顺序：

1. narrative organization/rationale 节点只作为叙述关系，不作为 mechanism seed；
2. seed 优先来自 explicit mechanism key、MethodUnit owner、入口 symbol 或 typed graph boundary；
3. 在 directed data/call/control graph 上计算 input→output closure；真实环使用 SCC，普通顺序不建 SCC；
4. 每个 operation/detail 只能有一个 primary owner；多机制共用时建立 `SharedDetailRef`；
5. merge 仅允许相同 explicit owner，或两个 seed 被同一入口—出口有向 closure 唯一覆盖且不存在竞争
   owner；单向生产者→消费者链本身是正常机制路径，不要求虚构反向边；
6. 禁止因共享 claim、span、brief、intent 或任一邻接边直接 union；
7. 对 seed-collapse ratio、ownerless ratio、mechanism fan-in 和 details/page 设异常 gate。

若项目确实只有一个大机制，必须由 owner/path 证据证明，而不是由 union-find 的传递相关性推出。

### 6.6 Source 和 replay 合同

产品运行与 replay 必须遵守同一 source authority：

- Unified mode 强制需要 snapshot、symbol index、source manifest 和 implementation scope；
- replay 冻结目录缺 artifact 时，可以从 `--repo` 确定性补建，但必须验证 exact project tree hash；
- tree hash 不匹配或没有可核对 hash 时 typed-block，不得混用旧 Research 和新 repository；
- artifact 读取/解析失败返回 typed failure，禁止 broad exception 后变成 `None`；
- vendor/generated/data/test/third-party exclusion 与 ownership 由 manifest 决定；
- detail/operation 先按 source span 对应的 manifest entry 分组；owned first-party 分组保留，excluded 分组
  单独拒绝；只有一个不可拆事实同时绑定冲突 authority 时才保留 `mixed` 并标为 unresolved；
- `unknown`、不可拆 `mixed`、空 manifest digest 一律 unresolved；
- archive/workset/receipt 全部绑定 source manifest digest。

### 6.7 统一 live admission

在第一个 Formalizer/Writer/Realizer 模型请求前持久化 `UnifiedLiveAdmissionV1`。至少检查：

| Gate | 必须满足 |
|---|---|
| run identity | commit、dirty-state manifest、launcher digest、profile/model identity 完整 |
| source | snapshot/tree hash/source manifest/scope 存在且 digest 闭合 |
| authoring closed-set | projected claim、stage packet、unit/brief/facet 集合无孤儿和重复 |
| research | core intent ledger 口径一致；无 unsearched/pending；partial 必须有 promoted evidence、bounded-search 终态和 explicit gap，且只能进入 Candidate |
| mechanism owner | core ownerless 和 cross-owner merge 为 0；每次 merge 都有机器可核验 proof；collapse ratio 只告警、不代替 proof |
| mechanism path | core input→output typed path 成立，unknown active path 为 0 |
| formula | obligation 有 owner/page binding；incidental expression 不冒充公式 |
| workset | page canonical、projection proof 完整、单页和总预算都通过 |
| invocation | 当前 phase 每 invocation 恰好一页；精确 plan 与全 run reservation 均在 profile envelope 内，无 task×all-pages 模式 |
| resume | checkpoint directory 新鲜，或 resume digests 全部一致 |

语义上尚未被代码验证的作者意图可以以 Candidate unresolved 状态保留；上述结构 gate 任何一项失败都
不得开始真实模型调用。

### 6.8 Durable request event 和 resume

每次实际调用完成后原子写入独立的 `ActualRequestReceiptV2` 文件，而不是向一个可能半写的共享 JSONL
追加：

- run/invocation/task/page/consumer IDs；
- exact technical-page bytes digest、角色 request-envelope digest、response digest；
- started/finished time、attempt、model identity；
- parse/validation outcome 和 typed failure；
- upstream archive/workset/plan digests。

文件先写同目录临时文件，再以 `os.replace()` 发布；`invocation_id + attempt` 是幂等键。聚合
obligations/packages/section results 由 receipt 文件集合确定性重建。resume 只跳过 receipt 完整且所有
digests 匹配的 invocation；任何 page、source 或 plan 变化都使依赖调用失效，但不应使无关 mechanism
的已完成结果失效。

## 7. 上一轮 P0–P9 的重新判定

| 工作包 | 第一轮实现后的实际状态 | 本轮验收判定 | 第二阶段动作 |
|---|---|---|---|
| P0 mode/runtime wiring | replay 确实生成 unified artifacts；产品 persistence 有改善 | 部分通过；未证明完整产品纵向、launcher 不可复现 | 固化 run contract、dirty-state/launcher digest、product+replay 双入口测试 |
| P1 offline unified reconstruction | context/manifest 可生成，但后续未完成；无统一 admission | 未通过 | 先构建 archive/workset/plan/admission，全程零模型 offline 验收 |
| P2 source inventory/scope | 产品 persistence 与 Writer loader 已接；replay 缺 bridge，unknown fail-open | 未通过 | 补 repo rehydration、tree-hash binding、unknown fail-closed |
| P3 intent scheduler/promotion | scheduler 已接 Research graph，operation ownership 已收窄 | 代码完成但未 live 验收；冻结 DyG ledger 口径冲突 | 新鲜 Research pilot + checkpoint migration/consistency gate |
| P4 semantic closure/compiler | validator 已调用，排序边不再直接证明 connectivity | 未通过；23→1 collapse、116 disconnected、partial 绕过 | owner-first mechanism compiler、有向 typed path、结构 admission |
| P5 per-equation formula | detail/equation obligations 已存在，incidental expression 未直接 deterministic 通过 | 未通过；160 preferred、0 package、O×P 调度 | page-centric batch、join page、AST/source fidelity、bounded repair |
| P6 paged delivery/Realizer/Binder | 单页 actual request、独立 receipt、Realizer 权限边界已有代码 | live 未到达；总调用量无界 | 三层合同、section workset、真实 request receipt、全角色纵向捕获 |
| P7 callback incremental rebuild | 部分 digest/callback 基础存在 | 未到达，无法证明新分页架构下 resume | event ledger、局部 invalidation、kill/resume 纵向测试 |
| P8 十项目 live matrix | launcher 首个运行 DyG，未按既定 EBCAR→LinearRAG→DyG pilot 顺序；首项停止 | 未通过 | offline 10/10 后再三 pilot，再十项目 controlled concurrency |
| P9 holdout/cutover | 未开始 | 未通过 | 仅在十项目 acceptance 后执行 holdout、默认切换和 release freeze |

## 8. 第二阶段工作包

工作包必须串行过门。后一个工作包不得用“后续 live 会覆盖”代替当前退出条件。

### WP0：冻结失败证据并建立可复现运行合同

涉及：

- `scripts/run_unified_ten_project_live_matrix_20260907.sh`
- live/replay launcher 与 runtime ledger
- artifact schema/version 工具

修改：

- 将脚本纳入版本控制或记录 exact script digest；
- 在 run start 持久化 commit、dirty file manifest、CLI、profile digest、model identity、repo/tree hash；
- 对 start/end/signal/timeout/user-stop 写结构化终态；
- 禁止复用非空输出目录；resume 必须显式声明。

退出条件：同一 run identity 可由 artifact 独立复核；人工停止也有 terminal event 和最后 completed
invocation，不再依赖 shell 日志猜测。

### WP1：统一 source/replay reconstruction

涉及：

- `scripts/run_authoring_replay.py`
- `src/code2paper/agentic/autonomous_method_agent.py`
- `src/code2paper/agentic/publication_method_writer.py`
- source inventory/scope 模块

修改：

- 将产品 source artifact builder 抽为产品/replay 共用函数；
- replay 缺 artifact 时按 `--repo` 补建并核对 frozen project tree hash；
- source manifest 缺失、解析错误或 hash 不符时 typed-block；
- 按 source span/entry 拆分 mixed detail，authority 判定显式要求 allowed source kind 和非空 manifest
  digest；不可拆 mixed 保持 unresolved。

退出条件：十项目 offline reconstruction 均生成相同 schema 的 source closure；故意删除/篡改 manifest
时 10/10 在首个模型请求前失败。

### WP2：Research intent scheduler 的真实纵向闭环

涉及：

- `src/code2paper/agentic/research_graph.py`
- `src/code2paper/agentic/intent_ledger.py`
- Research checkpoint migration/validation

修改：

- 保留按 obligation span/node 的 operation 归属，禁止回退到整个 behavior graph；
- 统一 agenda、must-cover obligation 和 promotion ledger 的 terminal 定义；
- 旧 checkpoint 无法证明一致性时重建 ledger，不继承模糊完成状态；
- Research 终止前强制 `check_next_schedule()` 无 unsearched/pending core intent；`implemented_partial` 只有
  同时具备 promoted evidence、bounded-search exhaustion 和 explicit gap 才是 Candidate terminal。

退出条件：构造无关 operation 不得提升 core intent；真实 pilot 中 ledger 与 agenda 数量、状态和 evidence
可逐项对齐；partial 缺任一终态证明时不能结束 Research，证明齐全时可进入 Candidate、不能进入 Verified。

### WP3：owner-first 机制 closure compiler

涉及：

- `src/code2paper/agentic/mechanism_context_compiler.py`
- behavior graph / MethodUnit ownership adapters

修改：

- narrative node 与 executable mechanism seed 分型；
- 用 explicit owner、entry symbol 和共同入口—出口 directed typed closure 分区；
- 删除共享 span/claim/brief 导致的传递 union；
- 强化现有 `SharedDetailRefV1`，用它表达跨机制只读引用，并新增 owner conflict typed failure；
- completeness 输出结构 failure codes，不再用平均分掩盖关键失败；
- `partial` 不得绕过 source/owner/path 结构错误。

退出条件：DyG offline 不再无证据地 23→1；人工构造断链、跨 owner 共享 claim 和相邻 `precedes` 都不能
通过 connectivity。

### WP4：Archive、workset、invocation plan 三层实现

涉及：

- `src/code2paper/agentic/mechanism_context_projection.py`
- `src/code2paper/agentic/mechanism_context_pages.py`
- 新 `src/code2paper/agentic/unified_context_models.py`
- 新 `src/code2paper/agentic/unified_context_compiler.py`
- 新 `src/code2paper/agentic/unified_invocation_ledger.py`

修改：

- 全局实体去重存 archive，page 只引用必要 ID 和局部内容；
- 完整 global header 只存 archive；每页只物化完成该 invocation 所需的最小 header，unresolved/core lists
  不逐页复制；
- page 具备 canonical serializer 和 projection proof；
- profile 同时约束 per-page、total pages、total input tokens、planned calls；
- 删除动态放宽 `MAX_MECHANISM_SLICES` 的行为；
- 计划超过预算时 admission 失败并给出最大贡献机制/字段，不静默丢细节。

退出条件：同一 archive 两次编译 digest 一致；page 可逆追踪；无全局字段线性重复；任何超总预算案例在
零模型调用时被阻断。

### WP5：Page-centric formula compiler 与 AST fidelity

涉及：

- `src/code2paper/agentic/formalization_agent.py`
- formula obligation/package schemas
- response recovery 和 formula validator

修改：

- 为 obligation 建 primary detail/equation/page owner；
- 每页一次 batch 全部局部 obligations；
- 跨页依赖由 compiler 生成 join page；
- success 后不扫描无关页，repair 仅针对失败 obligation；
- 一次主调用不超过 profile 的 `max_obligations_per_page`，一次 repair 恰好处理一个 obligation；
- required 与 preferred 分开预算，preferred 不得无限扩大主路径；
- 校验 AST/operator/operand/source span fidelity，拒绝 incidental expression；
- 每次 request 后立即持久化 receipt 和 package fragment。

退出条件：`actual_main_calls == planned_formalizer_invocations`，且
`actual_repair_calls <= configured_repair_call_limit`；不存在 O×P；kill/resume 不重放成功 invocation；公式
mutation 能被 fidelity gate 捕获。

### WP6：Section workset、Realizer 和 Binder 闭环

涉及：

- `src/code2paper/llm/section_writer.py`
- `src/code2paper/agentic/publication_method_writer.py`
- `src/code2paper/agentic/mechanism_realizer_composer.py`
- Binder/final-integrity 模块

修改：

- narrative plan 先冻结 section→mechanism/detail/formula/claim ownership；
- 每个 section 只消费自己的 required pages；
- Formalizer/Writer 共用页按 `page_id + canonical technical bytes` 比较，角色 request envelope 分别计算
  digest；
- 分别强制 Formalizer、每个 section Writer、Realizer、Binder receipt；
- Binder witness 必须指向上游授权文本和 archive evidence，不能由同一生成者自证；
- 无 Writer 输出或段落不足时 fail/repair，不允许 deterministic prose 补正文。

退出条件：真实 caller 捕获测试证明 page bytes 一致；故意 sanitizer/serializer mutation 时对应角色 gate
失败；删除任一角色 receipt 不能由其他 receipt 代替。

### WP7：Callback、局部失效与 durable resume

涉及：

- callback controller/checkpoint 模块
- publication orchestration
- invocation event ledger

修改：

- callback 结果只使受影响 archive atoms、worksets 和 invocations 失效；
- upstream/source/page/plan digest 进入 checkpoint key；
- 支持在 Formalizer、section Writer、Realizer 阶段 kill 后 resume；
- retry/repair bounded，内容失败返回 owning Agent，不由 harness 改语义。

退出条件：三处受控 kill/resume 均能从最后完整 receipt 继续；已成功且未受影响的 request count 不增加；
修改一个 source span 只失效其依赖闭包。

### WP8：Offline 十项目与三项目 pilot

顺序固定：

1. 十项目 offline reconstruction，禁止模型调用；
2. EBCAR 小型 live pilot；
3. LinearRAG 中型 live pilot；
4. DyG-Mamba 大型 live pilot；
5. 三项目全部通过后才启动十项目 live matrix。

DyG 不再作为首个 smoke test，因为它已经证明是大 fan-in、高 details、高 formula obligation 的压力样本。
先用小型项目证明合同，再逐级扩大规模，不能用降低 DyG 信息量换取通过。

### WP9：十项目 acceptance、holdout 和 cutover

十项目 live 允许最多四并发，但必须根据 waiting、KV pressure、OOM、abort 动态降低并发。每项目独立
新目录、独立 terminal event 和 budget ledger。任何项目结构 admission 失败时，只修 generic logic；
禁止添加项目名、已知路径、符号或原文答案到生产代码。

全部通过后再做 holdout、clean-checkout、default mode/cutover 和 release freeze。一个 live sample 或
静态测试全绿都不能单独授权 P9。

## 9. 代码级实施规格

本节把 §6 的目标合同落实到当前代码符号。没有完成本节定义的模型、函数边界和失败码，不得仅凭
WP 描述宣称“已完成代码级修复”。

### 9.1 生产调用链的 before/after

当前 Unified 主链位于
[publication_method_writer.py#L1095](../src/code2paper/agentic/publication_method_writer.py#L1095)：

```text
_load_repository_authoring_context
→ _compile_mechanism_evidence_closures
→ _annotate_mechanism_paper_details
→ validate_mechanism_context_completeness（只阻断 repository_ready）
→ _build_shared_mechanism_payloads
→ _build_shared_mechanism_page_manifests
→ _compile_mechanism_formula_obligations
→ _run_mechanism_formalizer
→ 写 obligations/packages
→ _build_narrative_plan_v3
→ _writer_section_inputs_v3
→ write_publication_method_by_sections
→ _assert_shared_payload_delivery
```

修复后必须变成：

```text
load_repository_authoring_context_v2（typed result）
→ split_source_authority_atoms
→ compile_owner_scoped_mechanisms
→ validate_structural_mechanism_closure
→ build_unified_context_archive_v2
→ compile_formula_obligations（先落盘）
→ build_consumer_workset_manifest_v2
→ build_run_invocation_budget_envelope_v1
→ build_consumer_invocation_plan_v1(phase="formalizer", revision=1)
→ evaluate_and_persist_unified_live_admission_v1(phase="formalizer")
→ [admission PASS 后才允许第一个 LLM request]
→ execute_formalizer_invocations（每次一页、页内 batch）
→ build_narrative_plan_v3
→ extend_writer_worksets_from_narrative_plan
→ build_consumer_invocation_plan_v1(phase="writer", parent=revision-1)
→ evaluate_incremental_writer_admission（不得超过剩余 run envelope）
→ execute_writer/realizer invocations（每次一页）
→ bind_and_assert_receipts_against_plan
→ final integrity/reverse validation
```

`shadow_unified` 可以在 admission 前生成 V1/V2 对比 artifact，但不得绕过 V2 admission 发模型请求。

### 9.2 新数据模型和落盘位置

新建 `src/code2paper/agentic/unified_context_models.py`；所有模型统一使用
`ConfigDict(extra="forbid", frozen=True)`。表示集合的 ID tuple 在构造前排序去重；表示技术/叙述顺序的
tuple 必须保留 compiler 证明的顺序并单独校验唯一性，不能为了 digest 稳定而重排。所有
`content_digest` 使用现有 `canonical_json_bytes(..., exclude_fields={"content_digest"})` 和
`sha256_digest()` 计算。禁止让调用方传入一个与内容不一致但仍被接受的 digest。

| 模型 | 必填字段 | 关键 validator | artifact |
|---|---|---|---|
| `ArchiveAtomV2` | `atom_id`、`atom_kind`、可空 `primary_mechanism_id`、`source_span_ids`、`source_entry_paths`、`evidence_authority`、typed `payload` | `atom_kind` 与 payload model 严格匹配；span 必须能在 source manifest 定位；repository verified 要求全部 entry 为 allowed first-party；core atom 的 owner 不可空 | 归入 archive |
| `SourceAuthorityPartitionProofV1` | 原 semantic detail ID、partition key、child atom IDs、included/excluded span IDs、decision/reason | child 集合不重叠且精确覆盖 parent source atoms | 归入 archive diagnostics |
| `UnifiedContextArchiveV2` | snapshot/tree/source/intent/research/context digests，mechanism/detail/operation/edge/equation/evidence atoms，owner/shared-ref indexes | ID 全局唯一；所有 foreign key 闭合；每个 core atom 有唯一 primary owner；反向索引覆盖全部原子 | `unified_context_archive_v2.json` |
| `ConsumerTechnicalPageV2` | `page_id`、`page_kind`、`archive_digest`、`mechanism_id`、`atom_ids`、`technical_payload`、`technical_bytes_digest`、`token_estimate` | payload 中 atom IDs 与声明一致；所有 atom 来自 archive；单页 token 预算通过 | 归入 workset manifest |
| `ConsumerWorksetV2` | `workset_id`、`task_kind`、`task_ids`、mechanism/可选 section ID、`required_atom_ids`、`required_page_ids` | pages 的 atom union 精确覆盖 required atoms；禁止越权 atom；join page 有 dependency proof | 归入 workset manifest |
| `ConsumerWorksetManifestV2` | `archive_digest`、`source_manifest_digest`、pages、worksets、projection diagnostics | page ID/bytes 全局唯一一致；所有 workset foreign key 闭合 | `consumer_workset_manifest_v2.json` |
| `RunInvocationBudgetEnvelopeV1` | run/profile/model digests、各 role 最大 calls/tokens、总 input tokens、repair 上限 | 数值必须来自显式 live profile；后续 allocation 总和不能超过 envelope | `run_invocation_budget_envelope_v1.json` |
| `ConsumerInvocationV1` | `invocation_id`、role、phase、task IDs、唯一 `page_id`、expected technical digest、expected request-envelope digest、budgets、dependencies、max attempts | 每个 invocation 恰好一页；task/page 属于对应 workset；预算均为正且不超过剩余 envelope | 归入 plan revision |
| `ConsumerInvocationPlanV1` | revision/parent、phase、archive/workset/envelope/profile/model digests、invocations、role totals、planned calls/tokens、repair limits | DAG 无环；parent digest 连续；聚合计数由 invocations 重算；累计 allocation 不超 envelope | `consumer_invocation_plan_v1.<revision>.json` |
| `UnifiedAdmissionGateV1` | gate ID、status、failure codes、evidence artifact/digest | PASS 不得携带 failure，FAIL 不得无 failure | 归入 admission |
| `UnifiedLiveAdmissionV1` | run/phase/archive/workset/envelope/plan digests、所有 gates、phase planned totals、run reserved totals、status | 任一结构 gate FAIL 则总状态 FAIL；plan allocation 超 envelope 失败；总状态由 gates 派生 | `unified_live_admission_v1.<phase>.<revision>.json` |
| `InvocationAttemptStartedV1` | invocation/attempt/plan/page/model digests、started time | 只能引用 plan 中存在的 invocation；同 attempt 不可重复发布 | 每 invocation/attempt 独立文件 |
| `ActualRequestReceiptV2` | invocation/attempt/role/task/page IDs、actual technical/envelope digest、response/fragment digest、model、时间、`delivery_status`、`task_status`、succeeded/failed task IDs 和 failures | 不存可自报的 `accepted`；`delivery_accepted` 由 actual digest 校验派生，`task_complete` 由 task closed-set 派生；允许 delivery 成功但 task partial | 每 invocation/attempt 独立文件 |
| `SectionWriterReceiptV2` | section/workset ID、required/completed invocation IDs、output digest | completed 必须精确覆盖 required；Realizer invocation 不得出现在集合中 | 聚合生成 |
| `WriterAggregateReceiptV2` | plan digest、required/completed section IDs、section receipt digests | section 集合精确覆盖 narrative plan | `writer_aggregate_receipt_v2.json` |

`page_id` 的唯一规范定义：

```text
technical_bytes        = canonical_json_bytes(technical_payload)
technical_bytes_digest = sha256_digest(technical_bytes)
page_id                = "page:" + hashlib.sha256(
                           b"code2paper-consumer-page-v2\0"
                           + archive_digest.encode()
                           + b"\0"
                           + technical_bytes
                         ).hexdigest()
```

`technical_payload` 必须包含 `archive_digest`，因此相同文本来自不同 archive 时不会错误复用 page ID。
角色请求的 digest 单独定义：

```text
expected_request_envelope_digest = sha256_digest(canonical_json_bytes({
    "prompt_template_id": ...,
    "consumer_role": ...,
    "task_ids": sorted(...),
    "page_id": ...,
    "technical_bytes_digest": ...,
    "system_prompt_digest": ...,
    "rendered_prompt_digest": ...,
    "canonical_input_payload_digest": ...,
    "response_schema_digest": ...,
}))
```

它不把 Formalizer 和 Writer 的角色 prompt 强行设成相同；跨角色 identity 的共同真相只有
`page_id + technical_bytes_digest`。这里的 request envelope 指 Code2Paper 交给 provider adapter 的实际
`LLMRequest` canonical form；provider SDK 后加的 HTTP header、request ID 等非确定性传输字段不进入身份
比较，但 actual `prompt` 和 `input_payload` 必须进入 digest。

`ArchiveAtomV2.payload` 不能是任意 dict 通道。validator 必须按 `atom_kind` 调用对应现有 frozen model
（mechanism/detail/operation/edge/equation/evidence/intent），未知 kind 或 payload extra field 直接失败。
这样 archive normalization 不会成为绕过上游 schema 的第二条 authority 路径。

### 9.3 Source/replay 的逐函数修改

| 当前代码入口 | 必须修改的行为 | 新输出/失败 |
|---|---|---|
| `source_inventory.build_repository_source_manifest()` | 保留分类器；增加 manifest entry 对 span 的严格 lookup，返回 path normalization 冲突 | `source_span_unmapped`、`source_entry_digest_missing` |
| `publication_method_writer._load_repository_authoring_context()` | 不再 broad `except Exception: value=None`；改为 `load_repository_authoring_context_v2()`，返回模型和逐 artifact load result | `repository_authoring_context_v2` 或 typed failures |
| `scripts/run_authoring_replay.py` optional-copy block | Unified replay 缺 snapshot/index/manifest/scope 时调用与产品相同 builder；重建前核对 frozen tree hash 和 `--repo` tree hash | `unified_project_tree_hash_mismatch` 时在 Writer 前退出 2 |
| `autonomous_method_agent` artifact persistence | 继续写 source artifacts；增加四者 cross-digest 和 builder version | 产品/replay artifact schema 完全一致 |
| `mechanism_context_compiler.source_kind_for_span()` | 不再把 manifest 缺失静默转成可继续的 `unknown`；返回 `(entry, failure)` | unknown 进入 unresolved，不能进入 verified |
| `annotate_mechanism_paper_details()` | 在形成 detail 前按 source entry/authority 分组；重写子 detail ID 和边；不可拆冲突保持 mixed unresolved | `detail:<old>:src:<digest8>`，并生成 `SourceAuthorityPartitionProofV1` 保存 parent→child provenance |

source 原子拆分算法固定为：

```text
for operation/fact/equation atom:
    entries = resolve_every_source_span(atom.source_span_ids, manifest)
    if any span unresolved:
        emit unresolved atom(source_span_unmapped)
    else:
        partition by (source_kind, ownership_role, executable_authority)

for semantic detail:
    if its atoms fall in multiple partitions and can be separated by atom IDs:
        create deterministic child details; rewire only edges whose endpoint atom belongs to child
    elif partitions conflict but fact/equation is indivisible:
        retain one mixed detail with evidence_authority=unresolved
```

测试不得把所有 mixed 一刀切删除；必须证明 allowed first-party child 仍可保留，同时 excluded child 不能
支持正向实现声明。

### 9.4 Owner-first closure 的逐函数修改

#### `_collect_seed_data()`

- 给 seed 增加 `seed_kind = executable | narrative | unresolved`；
- explicit mechanism key、MethodUnit owner、target entry symbol 才能产生 executable owner anchor；
- story/brief/facet 只附着到已有 executable seed，不单独建立 owner；
- 删除“没有 seed 时把全部 fact/claim/equation 放入 `mech_core`”的全项目 fallback；
- 无 owner 的事实进入 `unresolved_seed_ids`，不得自动成为一个大机制。

#### `_merge_mechanism_seed_rows()`

保留函数名以减小调用面，但替换 union 条件。删除当前 `evidence_overlap OR fact_flow_overlap OR
direct_graph_link` 即可 union 的逻辑。每次 merge 必须生成：

```text
MechanismMergeProofV1(
    left_seed_id,
    right_seed_id,
    owner_anchor_id,
    input_node_ids,
    output_node_ids,
    directed_path_relation_ids,
    decision="merged" | "shared" | "conflict",
)
```

允许 merge 的充分条件只有：

1. 两者 explicit mechanism owner 相同；或
2. 两者被同一个 owner entry 到同一个 terminal output 的有向 executable closure 唯一覆盖，且没有第二
   owner 对任一 seed 形成同等有效覆盖。

`CALLS`、`RETURNS_TO`、`DATA_DEPENDS_ON`、`CONTROL_DEPENDS_ON`、`READS_FROM`、`WRITES_TO`、
`NEXT_CONTROL`、`TRUE_BRANCH`、`FALSE_BRANCH` 可在 adapter 明确定义方向后参与路径；`CONTAINS`、普通
文本顺序、共享 claim/span/brief 不得单独证明执行路径。`ALIAS_OF/IMPLEMENTS/OVERRIDES` 只帮助 owner
解析，不直接证明 input→output。

有真实回边时先在 executable relation 子图上计算 SCC，再在凝聚 DAG 上做 reachability。单向链是正常
闭包，不要求反向边。

#### `compile_mechanism_evidence_closures()` 与 `annotate_mechanism_paper_details()`

- closure 必须携带 merge proof IDs、owner anchor、directed path relation IDs；
- 重叠 closure 中的 operation 先选唯一 primary owner，其他机制只获得现有 `SharedDetailRefV1`；
- 无法唯一选择时 operation disposition 为 unresolved，两个机制都不能复制成 primary；
- `precedes` 只保留叙述排序，不能进入 connectivity relation set；
- `validate_mechanism_context_completeness()` 改为结构 failure 集，不再以平均分决定是否可调用模型。

结构硬门固定为：

```text
core_ownerless_count == 0
core_owner_conflict_count == 0
disconnected_core_detail_count == 0
unknown_core_active_path_count == 0
every_merge_has_valid_proof == true
```

`seed_collapse_ratio`、mechanism fan-in、details/page 是异常诊断指标，不设跨项目武断阈值；即使 23→1，
只要每次 merge proof 和最终有向 closure 都完整即可通过。反之 ratio 很小也不能掩盖一个 cross-owner merge。

### 9.5 Archive/workset/page compiler 的逐函数修改

新建 `unified_context_compiler.py`，提供下列纯函数：

```text
build_unified_context_archive_v2(context_set, source_manifest, ...)
build_consumer_workset_manifest_v2(archive, formula_obligations, narrative_plan=None)
extend_writer_worksets_from_narrative_plan(manifest, narrative_plan)
build_run_invocation_budget_envelope_v1(manifest, profile_budget, model_capabilities)
build_consumer_invocation_plan_v1(manifest, envelope, phase, parent_plan=None)
evaluate_unified_live_admission_v1(...)
```

具体规则：

- `MechanismContextV1` 先规范化为 archive atoms；同一 detail/operation/evidence 只存一次；
- workset builder 以 task owner 为根，沿声明的 data/call/control/equation/evidence foreign key 求最小闭包；
- 每页是一个自包含 invocation payload，包含最小机制 header 和局部 atoms；
- 跨页引用在编译期生成 join page，join page 自身仍是单页；
- `required_atom_ids == union(required pages.atom_ids)`，少一个或多一个都失败；
- `build_mechanism_context_slices()` 和 `build_shared_payload_manifest()` 只保留 V1 兼容/对照用途；V2
  production path 不再调用当前动态 `max_slices` 逻辑；
- page packing 按 owner、typed path 邻接和 formula dependency 排序，不能按任意 detail 顺序证明语义关系；
- 如果一个不可拆 atom 自身超过单页预算，返回 `unified_atomic_page_over_budget`，不得截断 atom。

去重和预算指标统一计算：

```text
P_unique = |unique page_id|
T_unique = Σ token_estimate(unique pages)
T_sent   = Σ invocation.page.token_estimate
D_send   = T_sent / max(1, T_unique)

coverage(task) = union(atom_ids of task.required_page_ids)
coverage(task) 必须严格等于 task.required_atom_ids
```

`D_send` 只用于定位 section 重叠；是否通过由 profile 的总调用/总 token 硬预算决定，不用一个未经十项目
校准的固定“理想去重率”替代任务完整性。

### 9.6 Formalizer 的逐函数修改

#### `_compile_mechanism_formula_obligations()`

- 在模型调用前完成并持久化 obligation artifact；
- 每个 obligation 必须有 `primary_detail_id`、`primary_page_id`；跨页依赖绑定一个 join page ID；
- `preferred` 仍是信息义务，但必须单独统计 planned budget；超预算时 admission FAIL，不能静默降为 none；
- incidental expression 只能保留为 evidence atom，除非 operator、operand、condition 和 source-equation
  fidelity 全部支持目标 formula obligation。

#### `_run_mechanism_formalizer()`

用 `execute_formalizer_invocation_plan()` 替换
[formalization_agent.py#L1809](../src/code2paper/agentic/formalization_agent.py#L1809) 的 obligation 外层、page
内层调用。新函数只遍历冻结的 formalizer invocations：

```text
for invocation in plan.where(role="formalizer", phase="main"):
    assert one page
    pending = obligations on page without accepted receipt
    if pending:
        response = caller(page, pending)
        validate each returned obligation independently
        persist one request receipt + zero or more accepted package fragments

for obligation in failed_after_main:
    if repair budget remains:
        execute exactly one declared repair invocation on its join page
```

batch response schema固定为：

```json
{
  "results": [
    {
      "obligation_id": "...",
      "latex": "...",
      "prose_explanation": "...",
      "symbol_definitions": [],
      "material_conditions": [],
      "assumptions": []
    }
  ]
}
```

未知 obligation ID、重复 result 或越权 package 使对应 task 失败，并令 invocation 的 `task_status=partial`
或 `failed`；只要实际 page/envelope digest 正确，delivery receipt 仍可证明真实传输。同一 response 中已通过
AST/source fidelity 的其他 package 必须立即持久化，repair 不得重跑它们。所有可能的单 obligation repair
invocation 在 plan 中预声明为 conditional slots，运行时只激活失败项且激活总数不超过 repair 上限。

最终断言：

```text
actual_main_calls == count(plan formalizer main invocations actually pending at run start)
actual_repair_calls <= plan.formalizer_repair_call_limit
每个 actual call 的 page_id 恰好等于对应 invocation.page_id
不存在未在 plan 中的 actual call
```

当前“没有公式义务也调用 delivery probe 遍历全部 pages”的逻辑必须删除；无 formalizer task 的 page 不需要
Formalizer receipt。共享 identity 由真正承担 formula task 的 page receipt 证明。

### 9.7 Writer、Realizer、Binder 的逐函数修改

| 当前函数 | 修改 |
|---|---|
| `_build_narrative_plan_v3()` | 输出 section→mechanism/detail/formula/claim 的 closed ownership；无 owner 的段落要求 typed-block |
| `_writer_section_inputs_v3()` | 参数改为 `workset_manifest + invocation_plan`；每个返回 input 对应一个 Writer invocation 和一个 page，不再先装入 section 全部 pages |
| `_publication_section_partitions()` | V2 输入只做“一 input/一 page”断言；不得再次拆分或重组；V1 路径保留现有兼容逻辑 |
| `write_publication_method_by_sections()` | 按 invocation ID 调用；每页输出经现有 partition merge 合成 section；partial output 只修失败 page/task |
| `_capturing_writer_caller` | 在真正 caller 边界提取 technical bytes，计算 actual page/envelope digests 后立即写 receipt |
| `MechanismRealizer.realize_draft()` | 接收 plan invocation/page；保持 missing caller、unresolved authority、detail/formula/witness 越权时 blocked |
| `SectionComposer.compose_publication_section()` | 继续只组合 accepted lexical drafts；不得为缺失机制造句 |
| `_assert_shared_payload_delivery()` | 不再要求每个 section receipt 覆盖 `range(len(all mechanism pages))`；按 plan 精确校验该 section required invocation IDs |

Formalizer/Writer identity 校验算法：

```text
shared_page_ids = intersection(
    formalizer_workset.required_page_ids,
    writer_section_workset.required_page_ids,
)
for page_id in shared_page_ids:
    assert formalizer_receipt.actual_technical_bytes_digest
           == page[page_id].technical_bytes_digest
    assert writer_receipt.actual_technical_bytes_digest
           == page[page_id].technical_bytes_digest

assert formalizer_receipt.actual_request_envelope_digest
       == formalizer_invocation.expected_request_envelope_digest
assert writer_receipt.actual_request_envelope_digest
       == writer_invocation.expected_request_envelope_digest
```

两角色没有共享 task 的 page 不需要伪造交集。section receipt 只接受 `consumer_role=writer`；Realizer receipt
只接受 `consumer_role=realizer`；Binder receipt 只接受 `consumer_role=binder`。

### 9.8 Invocation ledger、原子持久化与 resume

新建 `unified_invocation_ledger.py`。目录布局固定为：

```text
artifacts/06_authoring/invocations/
  <invocation_id>/
    attempt-0001.started.json
    attempt-0001.completed.json
    package-fragment.json          # Formalizer 成功时
    output-fragment.json           # Writer/Realizer 成功时
```

文件名中的 invocation ID 使用 plan 中内容寻址的安全 ID，不直接拼接用户文本或路径。写入流程：

1. `_atomic_write_text()` 写同目录临时文件；
2. `os.replace()` 发布 started 文件；
3. 将 package/output fragment 写临时文件并以 `os.replace()` 发布；
4. completed receipt 最后发布，引用 fragment digest，作为一次 invocation 的 commit marker；
5. 聚合 artifact 从 completed receipts 和 fragments 重建，不作为 resume 的唯一依据。

resume 算法：

```text
load current archive/workset/plan
for invocation in dependency order:
    receipts = validated completed receipts for invocation
    if exactly one receipt has accepted delivery and matches all upstream/page/envelope/model/fragment digests:
        reuse succeeded task fragments; do not replay the main invocation
        activate only declared repair slots for failed task IDs
    elif receipts conflict or digest changed:
        invalidate invocation and its downstream dependency closure
    else:
        execute next bounded attempt
```

started 但没有 completed 视为 interrupted attempt，占 attempt 历史但不算成功；是否允许重试由 plan 的
`max_attempts` 决定。用户停止、signal、timeout 和 exception 都必须写 run terminal event，记录最后一个
completed invocation ID。

### 9.9 Live budget 配置与严格上界

在 capability/profile 层新增以下必填项；测试 fixture 可以显式给小值，真实 live profile 必须在 offline
matrix 后填写，生产代码不得提供无限大默认值：

- `CODE2PAPER_UNIFIED_MAX_PAGE_INPUT_TOKENS`
- `CODE2PAPER_UNIFIED_MAX_TOTAL_INPUT_TOKENS`
- `CODE2PAPER_UNIFIED_MAX_FORMALIZER_CALLS`
- `CODE2PAPER_UNIFIED_MAX_WRITER_CALLS`
- `CODE2PAPER_UNIFIED_MAX_REALIZER_CALLS`
- `CODE2PAPER_UNIFIED_MAX_OBLIGATIONS_PER_PAGE`
- `CODE2PAPER_UNIFIED_MAX_FORMULA_REPAIR_CALLS`

每个 invocation 必须满足：

```text
page_input_tokens
+ role_prompt_tokens
+ thinking_token_budget
+ max_output_tokens
+ safety_margin_tokens
<= advertised_model_context_tokens
```

每次 run 必须满足：

```text
planned_total_input_tokens <= profile.max_total_input_tokens
planned_calls_by_role[role] <= profile.max_calls_by_role[role]
planned_formula_repairs <= profile.max_formula_repair_calls

Σ plan_revision.allocated_input_tokens <= run_envelope.max_total_input_tokens
Σ plan_revision.allocated_calls[role] <= run_envelope.max_calls_by_role[role]
```

缺配置、估算器未知或 model context 不可核对均为 admission FAIL。现有 20,000 page budget 可作为 offline
比较基线，不能自动成为所有模型和十项目的 live 总预算。初始 envelope 对尚未生成的 Writer/Realizer
workset 使用可证明的保守上界；后续 phase plan 使用精确值占用 reservation，未使用额度可以释放但不能
挪用后突破任一 role 上限。

### 9.10 统一失败码及 owner

| Failure code | 发现位置 | 修复 owner | 是否允许模型调用 |
|---|---|---|---|
| `unified_source_manifest_missing/invalid` | source loader | WP1/source | 否 |
| `unified_project_tree_hash_mismatch` | replay rehydration | WP1/replay | 否 |
| `unified_source_span_unmapped` | source atom split | WP1/source | 否；仅非 required support 可进入 unresolved sidecar |
| `unified_authoring_closed_set_mismatch` | admission | authoring projection owner | 否 |
| `unified_core_intent_unsearched` | Research termination/admission | WP2/Research | 否 |
| `unified_core_intent_partial_without_terminal_gap` | Research termination/admission | WP2/Research | 否 |
| `unified_mechanism_owner_missing/conflict` | owner compiler | WP3/compiler | 否 |
| `unified_mechanism_path_disconnected` | completeness validator | WP3/compiler/adapter | 否 |
| `unified_page_projection_incomplete/overreach` | workset validator | WP4/compiler | 否 |
| `unified_atomic_page_over_budget` | page compiler | WP4/compiler/upstream atom owner | 否 |
| `unified_invocation_budget_missing/exceeded` | admission | WP4/profile owner | 否 |
| `unified_unplanned_actual_request` | caller boundary | WP5/WP6 orchestrator | 立即停止该 run |
| `unified_actual_page_bytes_mismatch` | receipt validator | producing consumer adapter | 立即停止该 run |
| `unified_consumer_receipt_missing` | aggregate gate | 对应 Formalizer/Writer/Realizer/Binder | 否 |
| `unified_consumer_task_incomplete` | task closed-set aggregate | 对应内容 owner/有界 repair | delivery receipt 可保留，但不得进入最终完成态 |
| `unified_resume_digest_mismatch` | resume loader | WP7/checkpoint | 使受影响依赖闭包失效，不复用旧结果 |

failure code 不能在 harness 中被过滤成 warning。只有语义状态（例如已完成 bounded search 的
author-spec-only）可进入 Candidate caveat；结构 failure 必须返回 owning component。

### 9.11 V1→V2 兼容和迁移规则

- V1 context/page/receipt 继续可读，用于诊断和 shadow diff；不自动升级为 V2 accepted receipt；
- V2 archive 可以从结构闭合的 V1 context 重建，但必须重新做 source、owner、path 和 projection validation；
- V1 receipt 没有 invocation ID、单页 task owner 或 envelope digest，不能用于 V2 resume；
- 旧 checkpoint 首次进入 V2 时，从 archive/workset/plan 重新开始 authoring，不重跑已冻结 Research，前提是
  Research/source digests 和 ledger 终态验证通过；否则回到 owning Research；
- `mechanism_context_page_manifest_v1.json` 在 shadow 期继续落盘用于差异分析，V2 production consumer 只能
  读取 `consumer_workset_manifest_v2.json`；
- 不做 in-place artifact 覆盖；V1/V2 文件名、schema version 和 digest namespace 分离；
- 默认 cutover 仍由 WP9 单独批准，不能因 V2 tests 通过自动改默认 mode。

### 9.12 实施切片和每片退出条件

| 切片 | 允许修改 | 必须先通过 | 禁止提前做 |
|---|---|---|---|
| S0 run/source | run contract、strict loader、replay rehydration、source split | source mutation tests、零 LLM admission block | 真实模型调用 |
| S1 owner closure | seed/owner/merge/path/completeness | directed graph、cross-owner、DyG offline closure tests | page/公式调参 |
| S2 V2 contracts | models、archive、workset、plan、budget admission | canonical/digest/projection/property tests，offline 10/10 | Formalizer live |
| S3 Formalizer | page batch、AST fidelity、receipt fragments | actual-caller call-count、mutation、kill/resume tests | Writer live |
| S4 Writer/Realizer/Binder | section workset、role receipt、Binder | actual-caller byte intersection、角色 receipt 缺失测试 | 十项目 live |
| S5 callback/resume | dependency invalidation、terminal event | 三处 kill/resume 纵向测试 | 并发矩阵 |
| S6 pilots/matrix | launcher、telemetry、matrix report | EBCAR→LinearRAG→DyG 3/3 | holdout/cutover |

任何切片不得通过降低 obligations、移除 core details、放宽 source/owner/path gate 或加入项目特例完成退出。
每个切片结束时必须在 `.agent/implementation.md` 记录绑定的 commit/dirty-state、逐文件修改、精确测试
命令、exit status、摘要和冻结 artifact root；测试数量本身不能替代 actual-caller、resume 或十项目 matrix
证据。

### 9.13 测试文件和命令映射

扩展现有测试：

- `tests/test_agentic_source_authority.py`：positive-claim authority 边界不回退；
- `tests/test_agentic_replay_execution_record.py`：source rehydration、tree-hash mismatch、terminal event；
- `tests/test_agentic_intent_ledger.py`：partial terminal 三条件和无关 operation 不提升；
- `tests/test_agentic_mechanism_evidence_closure.py`：owner merge proof、单向 closure、SCC、cross-owner conflict；
- `tests/test_agentic_mechanism_context_projection.py`：V2 canonical page/projection exact coverage；
- `tests/test_agentic_formula_obligation_truths.py`：page batch partial success、join page 和 AST/source fidelity；
- `tests/test_agentic_publication_method_writer_unified.py`：真实 caller、按交集 identity、独立角色 receipt；
- `tests/test_agentic_mechanism_realizer_composer.py`：plan/page 越权继续 fail-closed；
- `tests/test_agentic_detail_atom_binder_and_trace_v2.py`：Binder receipt 与 archive witness 反向绑定。

新增：

- `tests/test_agentic_repository_source_manifest.py`
- `tests/test_agentic_unified_context_models_v2.py`
- `tests/test_agentic_unified_context_compiler_v2.py`
- `tests/test_agentic_unified_live_admission.py`
- `tests/test_agentic_unified_invocation_resume.py`
- `tests/test_agentic_unified_ten_project_offline_matrix.py`
- `scripts/run_unified_ten_project_offline_matrix.py`，只允许 deterministic compiler/admission，不接收
  LLM caller，并输出每项目及聚合 matrix artifact

每个切片的最小命令：

```bash
python -m pytest -q \
  tests/test_agentic_source_authority.py \
  tests/test_agentic_repository_source_manifest.py \
  tests/test_agentic_replay_execution_record.py \
  tests/test_agentic_intent_ledger.py \
  tests/test_agentic_mechanism_evidence_closure.py \
  tests/test_agentic_unified_context_models_v2.py \
  tests/test_agentic_unified_context_compiler_v2.py \
  tests/test_agentic_unified_live_admission.py
```

```bash
python -m pytest -q \
  tests/test_agentic_formula_obligation_truths.py \
  tests/test_agentic_mechanism_context_projection.py \
  tests/test_agentic_publication_method_writer_unified.py \
  tests/test_agentic_mechanism_realizer_composer.py \
  tests/test_agentic_detail_atom_binder_and_trace_v2.py \
  tests/test_agentic_unified_invocation_resume.py
```

随后执行 `python -m compileall -q src tests` 和 `git diff --check`。全静态 suite 只在 S5 完成后和三项目
pilot 前执行。`test_agentic_14_vertical_tests.py` 中只解析 CLI 或只序列化 manifest 的旧测试不算
actual-caller 纵向证据；必须由捕获到的 `LLMRequest`、调用计数和 durable receipt 断言替代。

## 10. 必须新增或升级的测试

### 10.1 单元与性质测试

- archive canonical digest 与重建确定性；
- page projection 无遗漏、无未声明重复、相同 ID bytes 恒等；
- owner merge 的正例、共享 claim/span 不合并的反例；
- directed data/call/control connectivity，`precedes` 不提供连通；
- source atoms 可分 mixed 时按 authority partition；unknown、不可拆 mixed 和 missing manifest fail-closed；
- section required-page closure；
- formula AST/operator/operand fidelity；
- invocation budget 的边界和超限阻断。

### 10.2 Actual-caller 纵向测试

测试必须捕获真实 LLM client 收到的 request bytes，不能只测试 manifest 序列化或 CLI 参数解析。

至少覆盖：

- Formalizer 一页多 obligation 只调用一次；
- Writer section 只收到声明的 required pages；
- 同 page ID 在 Formalizer/Writer 的 actual technical bytes 完全一致，各自 envelope digest 与各自 plan
  相符；
- sanitizer、serializer、ordering 任一 mutation 都使 identity gate 失败；
- Formalizer/Writer/Realizer/Binder receipt 分别缺失时分别失败；
- 成功 obligation 不继续扫描无关页；
- kill/resume 后成功调用不重复。

### 10.3 Offline 十项目 matrix

每项目至少输出：

- source manifest/snapshot/tree hash 状态；
- authoring/research closed-set；
- seed 数、mechanism 数、ownerless/shared/collapse 指标；
- core detail、typed path、active path 和 completeness failure；
- archive atoms/bytes；
- workset/page 数、去重率、total tokens；
- Formalizer/Writer/Realizer planned calls 和最大 attempts；
- admission PASS/FAIL 及 failure codes。

Offline matrix 的意义是证明调用结构和 authority 已闭合，不是预测文稿质量。FAIL 项不得进入 live。

## 11. Live acceptance 标准

### 11.1 每个项目的硬门

- run identity、source/tree hash、archive/workset/plan digests 完整；
- core intent scheduler 无 required unsearched/pending，ledger 口径一致；partial 仅在 promoted evidence、
  bounded-search 终态和 explicit gap 齐全时允许进入 Candidate；
- authoring closed-set 无孤儿 claim/unit/stage packet；
- core mechanism owner 和 directed input→output path 全部可证；
- unknown source 不进入 repository verified；
- planned calls 与实际 calls 一致，只有声明的 bounded repairs 可增加；
- per-page、total input token、wall-time 和 retry budget 全部受控；
- actual receipt 的 technical-page bytes 与真实 caller 捕获一致；角色 request-envelope digest 分别闭合；
- Writer、Realizer、Binder 无越权 lexical tokens 或自生成 witness；
- callback/resume 后 digest、计数和最终内容闭合；
- Candidate/Verified/final validation artifacts 完整，Verified 继续 fail-closed。

### 11.2 DyG 的专项回归指标

DyG 修复后不能预设一个“正确页数”或“正确机制数”，但必须满足：

- 任何 23→1 合并中的每一步都有 explicit owner 或唯一入口—出口 directed merge proof；
- ownerless seed/detail 不通过 admission；
- 116 disconnected core 和 7 unknown active path 不得以 `partial` 继续；
- 263 个 unknown source detail 不得标记 repository verified；
- manifest 不再线性重复全局 author intent、unresolved 和 core ID 列表；
- Formalizer 主调用数等于计划 page tasks，而不是 160×pages；
- 中途停止后可恢复到最后 durable invocation；
- Writer 完成后再评价 Method 信息覆盖，不能把“运行完成”误当成“内容通过”。

### 11.3 十项目质量比较

除运行安全外，仍按上一轮总体目标比较新旧结果：

- repository-backed mechanism/detail/formula recall；
- author-intent coverage 与 unresolved 的诚实表达；
- input→operation→state/data transformation→output 的叙述闭合；
- per-equation 定义、变量、计算顺序和源代码 fidelity；
- Candidate 与 Verified 的 authority separation；
- 原论文仅作盲评参考，不作为生产 fact authority；
- 不以减少 obligations/details、过滤失败 claim 或删除复杂项目换取指标改善。

## 12. 禁止的“修复”

- 直接把 189 页截成前 N 页；
- 只降低 page token 大小，却保留 obligation×page；
- 把 160 个 obligations 任意砍成少数以降低调用数；
- 用 keyword、文件名或项目名硬编码 DyG 机制边界；
- 将 unknown source 当作 clean source；
- 用 `partial` 或平均 completeness score 掩盖 source/owner/path/digest 等结构失败；
- 恢复 deterministic Realizer/Composer 正文补写；
- 让 Realizer receipt 替代 section Writer receipt；
- receipt 预写 `accepted=true`，或只验证 manifest serialization；
- 用原论文、历史 profile 或 expected answer 反向授权 implementation fact；
- 因 Candidate 允许 caveat 而放松 source、digest、owner、path 和 final-integrity gate；
- 直接重启十项目并期待随机采样更快结束。

## 13. 建议执行顺序与当前停止线

立即执行顺序：

1. 完成 WP0，冻结可复现 run contract 和事件级进度 schema；
2. 完成 WP1–WP4，只做十项目 offline reconstruction；
3. offline 10/10 结构准入通过后完成 WP5–WP7 actual-caller 与 resume 纵向测试；
4. 按 EBCAR → LinearRAG → DyG 运行三个受控 pilot；
5. pilot 3/3 通过后再运行十项目 live matrix；
6. 十项目通过后才进入 WP9 holdout/cutover。

当前停止线是：**在 `UnifiedLiveAdmissionV1`、`RunInvocationBudgetEnvelopeV1`、owner-first closure、
三层上下文合同和 page-centric Formalizer 未完成前，不恢复 DyG，也不启动其余九个真实项目。**

本文完成的是基于当前代码与 DyG 耐久产物的第二阶段设计和执行重排，不代表这些修复已经实现。

## 14. 2026-09-09 修订：离线口径、入口/路径语义与本次离线修复记录

本节是核对后对 §4、§6、§9 的修订，不是 live acceptance、D5、cutover 或 release 结论。所有记录都
限于离线、零模型调用；本次没有启动任何 pilot 或十项目 live。

### 14.1 证据边界更新

- 本文 §2.1 绑定的 `/tmp/c2p-unified-live-matrix-20260908-7701a7e` 与本轮 `0/9` 报告
  `/tmp/unified-offline-merged-20260909-d.json`、`/tmp/ebcar-current-rebuild-20260909.json` 在当前环境
  已不存在（`/tmp` 已清空）。§4 的 DyG 数字与 `0/9` 只能由会话记录复核，不能由耐久产物复核。
- 十项目的冻结 Research 输入（launcher `FROZEN_ROOTS` 指向的 `/tmp/c2p-method-authoring-*` 与
  `/tmp/c2p-gpu1-cutover-remaining-20260906-r2/*`）同样已清空，且仓库内没有第二份副本。因此在重新
  生成冻结 Research 输入之前，**offline 10/10 与三项目 pilot 均不可执行**；本节的验收只到
  "当前代码可重编的离线证据" 这一层。

### 14.2 对 §4.4 / §4.7 的修订

- 生产 Formalizer 已是 page-centric：统一模式调用 `_run_unified_v2_formalizer_phase`
  （`publication_method_writer.py:15040+`），obligation 外层 × page 内层的笛卡尔积只存在于
  `formalization_agent.py:1686` 的 `_run_mechanism_formalizer_legacy`，不再属于生产路径。
- completeness 已改为结构 failure 集（`mechanism_context_compiler.py:3894+`），并经
  `closed_set_failures` 进入 `evaluate_unified_live_admission_v1`（`publication_method_writer.py:15277-15300`）；
  统一模式下 FAIL 即返回、不发模型请求。§4.4 "只在 `repository_ready` 抛错" 描述的是已被 V2 admission
  取代的旧行为。
- 生产冻结 behavior graph 仍由 `research_nodes.behavior_graph_updater_node` 生成；本次已把
  interprocedural `CALLS` 与子模块绑定接入该路径（见 §14.5），否则持久化图仍会周期性出现 0 CALLS。

### 14.3 对 §6.5 / §9.4 的语义修订（本次已实现）

1. **入口优先序**：explicit entry hint → public lifecycle（`forward/encode/decode/infer/predict/
   generate/train/fit/run/main/rerank/retrieve/search/execute`）按父类上下文分组 → typed call-graph
   root → 末位词法车道；`get_/set_/load_/save_/make_/build_/create_/parse_/format_/validate_/_` 前缀一律
   不进入上述任何入口车道，也不能仅凭词法重合成为 `target_core`；多组同分时保持
   `target_entry_symbol_ids=()`（unresolved），不再按 symbol id 排序猜一个入口。
   `ImplementationScopeV1.entry_inference_status` 记录实际生效的 lane
   （`explicit | lifecycle | call_graph_root | lexical | unresolved_ambiguous | unresolved_missing`）；
   下游必须把 `unresolved_ambiguous` 当作"无 owner"，不得据此猜入口。
2. **core detail 合取定义**：core 必须同时满足"唯一 primary owner（机制有非空 owner anchor）+
   first-party executable source + obligation/facet 精确绑定 + 位于证据推导出的 input→output 有向路径"。
   不满足者降级为 supporting（保留在 archive，绝不删除），机制若存在可执行 operation 却没有任何 core
   detail，则报 `core_detail_missing`。
3. **路径端点必须来自证据**：input = 消费未被任何 operation 生产的操作数（或 role=input）；output =
   `RETURN`/`WRITE` 或结果不被任何 operation 消费。禁止 first/last detail 兜底；端点缺失时
   `connected_input_to_output=false` 并记 `core_path_endpoint_unknown`。
4. **operation cluster 合并条件**：只允许同一 source span，或 producer/consumer、共享 typed relation
   等有向链接；共享 fact/guard 不再单独合并；union 受 span 集约束，禁止通过无 span operation 跨 span
   传递合并。
5. **无 owner 不扩张**：`_reachable_graph_nodes` 只有在解析出 owner entry 起点时才做有向遍历；否则
   只保留精确 fact/span 命中的节点用于审计，不沿可执行边扩张。`unresolved_seed_ids` 只表示"无 owner
   anchor 的 seed"，不再把 partial/blocked 机制混入 owner 门。

### 14.4 对 §9.10 / §9.13 的修订

新增/收紧的 failure codes：

- `core_detail_missing`（机制有 operation 但无 on-path core）
- `core_path_endpoint_unknown`（无法从证据确定 input/output 端点）
- `unified_mechanism_owner_missing` 现在会因"机制有 operation 但 owner anchor 为空"触发，而不再
  仅因 `primary_mechanism_id` 为空触发
- `unified_source_rehydration_missing`（离线矩阵缺少 `--repo`，无外部 tree-hash 锚点）
- 离线矩阵分阶段失败码：`unified_<stage>_failed:<code>`，stage ∈ {budget_envelope_compile,
  workset_compile, formula_page_owner_binding, formalizer_plan_compile, formalizer_admission,
  narrative_plan_compile, writer_workset_extend, writer_plan_compile, writer_admission,
  realizer_plan_compile, realizer_admission}

新增测试文件：`tests/test_agentic_behavior_graph_calls_production.py`、
`tests/test_agentic_unified_ten_project_offline_matrix.py`。

### 14.5 对第 3 点（CALLS）的技术修正——重要

EBCAR 的 `rerank` **并不调用** `forward`。真实源码
`/data1/.../EBCAR - Embedding-Based Context-Aware Reranker/src/model/ebcar_dedicated_attention_model.py`
中：

- 唯一的同类方法调用是 `__init__` 第 43 行的 `self.get_passage_positional_encoding(...)`；
- `forward`（L97）与 `rerank`（L246）调用的是 `self.model(...)`（L182/L309）、
  `self.document_id_embedding(...)`、`self.passage_id_embedding(...)`；
- `self.model` 在 `__init__` L22 被赋值为 `TransformerEncoderWithHybridAttention`。

因此"`rerank` 沿 CALLS 到达 `forward`"需要**子模块属性绑定**，而不是同类调用解析。本次实现：
adapter 记录 `self.<attr> = <Class>(...)`（同文件类、显式 import 的类，或全仓库唯一同名类），
`_resolve_call_target` 把 `self.<attr>(...)` 绑定到该类的 `forward`（无 `forward` 时 `__call__`），
并要求唯一；`self.<a>.<b>`、`other.<method>` 不再借用同类短名绑定。实测 EBCAR：

```text
entries = [EBCarRerankerHybridAttention.rerank, EBCarRerankerHybridAttention.forward]
graph: 315 nodes / 543 relations / CALLS = 2（均绑定 target_node_id）
CALLS: rerank -> TransformerEncoderWithHybridAttention.forward
       forward -> TransformerEncoderWithHybridAttention.forward
reachable_from_entries = {TransformerEncoderWithHybridAttention.forward}
```

即链路真实形态是 `rerank → 子模块.forward → attention/output`，不是 `rerank → 自己的 forward`。
若坚持"rerank 必须到达同类 forward"，只能伪造边，禁止。

### 14.6 本次离线修复与验证记录

已修改：`mechanism_context_compiler.py`、`implementation_scope.py`、`method_architect.py`、
`behavior_graph_tools.py`、`python_behavior_adapter.py`、`research_nodes.py`、
`repository_authoring_artifacts.py`、`unified_context_compiler.py`、
`scripts/run_unified_ten_project_offline_matrix.py` 及对应测试。

其中三处属于**已存在的生产断链**（不是本次语义收紧造成）：

- `research_nodes.repository_indexer_node` 引用未定义的 `adapter.language`（NameError），任何产品
  Research 运行都会在此失败；已改为 `authoring.language`。
- JavaScript 语言车道的 `SymbolIndexV2` 从不写 `content_digest`，`build_repository_authoring_artifacts`
  直接抛错；已按 Python 车道的 canonical payload 就地补齐。
- 两个入口共享同一依赖 operation 时（EBCAR 的 `rerank` 与 `forward` 共享 32 个 operation），
  `build_unified_context_archive_v2` 会抛 `unified_mechanism_owner_conflict`。已按 `annotate` 的同一
  规则（最小 mechanism id 为 canonical owner）把该 operation 在 archive 中只存一次，并只比较
  source identity 字段（`relation_ids`/`content_digest` 属上下文局部证据，保留在各机制自己的
  closure 中）。

验证命令与结果（离线、零模型调用）：

```bash
python -m pytest -q <25 个聚焦测试文件>        # 387 passed
python -m pytest -q                            # 3172 passed, 3 skipped, 0 failed (508s)
python -m compileall -q src tests scripts      # exit 0
git diff --check                               # 无输出
```

全量静态套件此前为 `4 failed`，全部属于 dirty baseline 的过期断言，已在本轮一并修正（均不涉及放宽
任何 gate）：

- `tests/test_agentic_publication_method_writer.py` 三处 `set(outputs) == {"publication_writer_result_v1"}`
  未包含 blocked 运行必须发布的 `run_terminal_event`（§9.8/WP0 要求 stop/block/exception 都有终态事件）。
- `tests/test_agentic_14_vertical_tests.py::test_vertical_02_product_agent_to_writer_unified` 使用只含
  legacy authoring 输入的 fixture，统一模式已要求 Research/Source artifacts；改用 `_unified_artifacts`。

EBCAR 源级离线全链（无 Research facts，只走 owner/entry/graph/closure/archive/workset/plan/admission）：

```text
closures = 2（mech_sym:9773c5add7af1f92=rerank, mech_sym:f6cf5bdfe2ae16f0=forward）
每个机制：owner anchor 存在，details 72/77，core 26/26，connected_input_to_output=true，
          disconnected_core=0，completeness failures={}，info=0.8（剩余未决项为外部 unresolved CALLS）
structural gates：core_ownerless=0, owner_conflict=0, disconnected_core=0, unknown_active_path=0
archive：758 atoms / 2 mechanisms；formalizer admission = pass（该次未提供 formula obligations，
         因此 worksets/pages/invocations 均为 0；真实链路由 Research obligations 驱动）
```

§9.13 仍点名但尚未创建的测试文件：`test_agentic_repository_source_manifest.py`、
`test_agentic_unified_context_models_v2.py`、`test_agentic_unified_context_compiler_v2.py`、
`test_agentic_unified_live_admission.py`、`test_agentic_unified_invocation_resume.py`。其主题目前由
`test_agentic_unified_context_compiler.py`、`test_agentic_publication_method_writer_unified.py`、
`test_agentic_replay_execution_record.py` 等文件部分覆盖，但计划要求的独立文件尚未落地。

多项目离线抽查（无模型调用）：

| 项目 | 入口 | CALLS / 绑定 | 说明 |
|---|---|---:|---|
| EBCAR | `rerank`, `forward` | 2 / 2 | 子模块绑定生效 |
| LinearRAG | `LinearRAG.retrieve` | 8 / 4 | 入口与调用边均存在 |
| DyG / FastGS | 无（多 lifecycle 组同分） | — | 仅用一句话 intent 代理时按规则保持 unresolved；生产需真实 Research intent |

### 14.7 仍未完成 / 阻塞项

- **offline 10/10 不可执行**：冻结 Research 输入已随 `/tmp` 清空；重新生成需要 Research 阶段（模型
  调用），属于当前停止线之内，不能绕过。
- 入口 lane 在真实 Research intent 下的十项目表现未验收；DyG/FastGS 在弱 intent 下会因 owner 缺失
  而 FAIL，这是预期 fail-closed 结果，不是可调参项。
- core/path 门收紧后，历史上"几十个普通 LOAD/WRITE/CALL 被判 core"的机制会变成 supporting +
  `core_detail_missing`，需要真实 Research/owner 证据补齐后才能通过；禁止通过放宽门或删减 operation
  来"通过"。
- 未提交、未 commit、未 reset；文档修订与代码改动仍在同一 dirty worktree 中。

停止线不变：**offline 十项目结构准入、actual-caller/resume 纵向测试和三项目 pilot 全部通过前，
不恢复 DyG，也不启动其余九个真实项目。**
