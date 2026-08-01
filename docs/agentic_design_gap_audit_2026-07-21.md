# 鲁棒 LangGraph Research Agent 设计差距审计

> **状态快照说明（2026-07-31）：**本文保留逐轮开发与 live 运行诊断，其中部分
> “待实现”项已在后续工作区代码中出现，不能再作为当前项目总状态来源。当前
> 当前 R8 结论、项目进度和剩余差距以
> [`project_status_and_gap_report_2026-07-31.md`](project_status_and_gap_report_2026-07-31.md)
> 为准；本文件仍用于追踪具体故障和实验历史。

> **2026-08-01 状态更新：**R8 六项目现已 6/6 accepted；matrix、17 项 recheck、
> report digest 与 resume digest 见
> [`r8_acceptance_status_2026-08-01.md`](r8_acceptance_status_2026-08-01.md)。本文下方
> “正在运行/待重跑”等表述均保留为历史快照，不再代表当前 R8 pass/fail。

> **Agent 自主修复原则（规范性）：**规则层发现格式、schema、证据或内容错误后，
> 必须形成 typed repair issue 并返回 owning Agent 做有界重试；禁止用静默过滤、
> deterministic fallback 冒充成功、放宽硬门或降低义务覆盖来换取通过。详见
> `docs/agentic_error_feedback_and_self_repair_principle.md`。

日期：2026-07-21  
基准文档：总体设计、具体改造执行计划、behavior template 过渡参考。  

> **2026-07-28 规范覆盖说明：**本文中的 Gemma-4、GPU 0/1、TP=2、MTP
> 和固定 role sampling/budget 是历史运行记录，不再是正式验收门槛。当前 R8
> 接受任一可追踪的正式 API；硬门是非缓存真实调用 provenance、各参与角色的
> 非空 response trace、trace 与本次 resolved role profile 完全一致，以及既有
> evidence/quality/holdout 约束。部署拓扑是 execution metadata；sampling、
> 正文输出预算和思考预算不要求等于历史 Gemma 值，但必须与本次运行声明的
> profile 一致，任何漂移都是硬失败。

### 2026-07-28 Qwen3.6 有界思考 live 结果

Lookahead 单项目正式运行
`/tmp/code2paper-r8-matrix-20260728T114000Z/lookahead` 已完成：

- 正式 API 为 `openai / qwen36-27b-nvfp4 / http://127.0.0.1:8003`；
- response cache 关闭，capability profile 为 `qwen36_vllm_budgeted`；
- completion/readiness 与正文 evidence 均通过；旧 checker 曾报告
  `accepted=true`，但该结论已被 2026-07-28 的 resolved-profile 硬门复核取代；
- 76 条 generation trace 覆盖 69 个唯一 call ID；所有强制 live role 均有非缓存、未阻塞的正式 API 证据；
- 实际 thinking budget 为 supervisor 512、verifier 256、intent/analyzer/writer 1024，其余 512；
- research loop 在 50 turns 以 `max_turns_reached` 收口，最终 V3 coverage 将 5 个 must-cover 义务终结为 2 supported、3 explicit gap；最终正文 unsupported=0；
- supervisor 52 次调用全部 `finish_reason=stop`，completion token 中位数 564，说明 512 thinking budget 给结构化正文留下了空间；
- intent、intake、analyzer 仍出现 `finish_reason=length`，尤其 analyzer 的非缓存调用达到 4096；这是正文输出 ceiling/重复问题，不是 thinking 无限占用，后续应单独优化 schema 输出与正文预算；
- 当前 `--resume` 仍会重入下游阶段并再次发出 API 请求。digest 一致性已通过，但“零调用 replay”尚未实现，矩阵脚本不得再如此描述。

新的硬门从该 Lookahead 运行中识别出 8 次 Intake 和 3 次 Analyzer 调用仍使用
旧 `0.2/0.9/40` 且遗漏 reasoning effort，共 44 个 resolved-profile mismatch。
兼容层现已修复为与主 agentic 路径共享 Qwen profile；因此旧报告不得继续作为
正式 accepted 证据，必须重跑 live 验收。

结论：RAP、EBCAR、DyG-Mamba、LinearRAG 的历史 Gemma 运行均产生 content-accepted、unsupported=0、checkpoint/resume digest 一致的结果；但它们早于当前 Intent Agent 与 intake/analyzer role protocol。用当前 R8 scanner 重检会因缺少 intent artifact、且旧 intake/analyzer 误标为 supervisor 而失败，故不得称为“当前协议 accepted”。generic holdout 尚未通过最终可信 Method 验收。最新全量静态回归为 `2046 passed, 3 skipped, 12 subtests passed`。typed target 的 role/input/transformation/output/relation 已进入 authorized-fact 对齐与重放门禁；当前 P0 是先完成修复版 holdout的可解释 outcome，再按新协议重跑四个开发项目。

## 0. 2026-07-21 接管开发后的最新状态（以下内容优先于旧分批描述）

### 0.1 已完成的正式运行

| 项目 | 输出目录 | 结果 |
|---|---|---|
| RAP | `/tmp/code2paper-r8-20260721/rap-live-r5` | 历史 content acceptance：8 supported；84 decisions；92 role traces；resume digest 一致。需按当前 Intent/role protocol 重跑。 |
| EBCAR | `/tmp/code2paper-r8-20260721/ebcar-live-r2` | 历史 content acceptance：12 supported；resume digest 一致。需按当前 Intent/role protocol 重跑。 |
| DyG-Mamba | `/tmp/code2paper-r8-20260721/dyg-live-r3` | 历史 content acceptance：12 supported；resume digest 一致。需按当前 Intent/role protocol 重跑。 |
| LinearRAG | `/tmp/code2paper-r8-20260721/linearrag-live-r2` | 历史 content acceptance：12 supported；77 decisions；68 role traces；resume digest 一致。需按当前 Intent/role protocol 重跑。 |

这些历史运行的环境为物理 GPU 0/1、TP=2、MTP 服务、`max_model_len=131072`、严格串行。历史节点预算为 supervisor 1536、planner 2048、writer 8192（仅截断压测可到 12288）、local repair 3072、semantic verifier 1024；它们保留用于复现，不再作为当前 R8 硬门。

### 0.2 本轮新增的通用修复

- 修复 Python AST symbol slice 的局部行号未换算为全文件行号；此前行为节点可能声称调用 `generate()`，证据却指向文件顶部 `import` 行。
- generic evidence packet 在生产路径中读取真实源码 `exact_excerpt` 和 snapshot file digest；源码缺失、越界或摘要不符时 fail closed。
- typed `symbol:path:name:line` 现在精确绑定对应 symbol，不再因 seed path 同时存在而选择整文件全部行为节点。
- compile candidate 采用有界、obligation-scoped behavior slice；未 typed 的 obligation 不能因英文 token overlap 变成 supported。
- 最终 supported 状态必须通过 `align_target_to_facts()`；缺少谓词会形成 `typed_predicate:*` 研究需求，supervisor 改搜对应行为并读取最新候选。
- 修复 checkpoint resume/advancer 把当前仍 pending 的 obligation 排除后误报 `all_obligations_terminal` 的问题。
- intent registry 新增通用 generation、verification、result composition 概念，并移除普通单词 `output` 对完整文件 I/O 的误触发。
- Intent Agent 的预算按 live profile 解析：历史 Gemma profile 保持 full proposal 4096；当前 Qwen profile 为 full proposal 8192、repair 6144、thinking 1024。每个被拒绝 obligation 会收到包含原始 schema/semantic failure 的 typed repair issue，并由同一 Intent Agent 做至多两次纠正。仍不合格时保留原图、生成 `intent_repair_exhausted:*` 的拒绝报告并令 R8 失败；不得把 deterministic target 回填后记为 Agent 成功。
- Harness 在 Agent retry 前执行可审计的表示级兼容：已知 obligation id 只有在去除尾随空白/标点后唯一精确命中 closed allowed set 时才修复；JSON 只补齐完整 value 后缺失的外层容器。半截字段、未知引用或语义歧义仍返回 Intent Agent，所有机械修复写入 `representation_repairs` 并重跑原硬门。
- Intent repair 已升级为策略递进状态机：第一次使用完整 typed repair；若发生 length、parse failure 或无信息增益，第二次切换为单 obligation compact patch schema，而不是重复同一请求。每次响应记录有界结构诊断，compact patch 转回 domain model 后仍执行完整 mandatory/reference/R8 硬门。
- 若 compact native schema 仍发生 constrained-decoding 重复，第三层改用 prompt-only content-first + binding：Agent 先给 target 语义内容，harness 兼容提取短 JSON/marker blocks，只在单 obligation 作用域内组合缺失 routing id；冲突 id、未知 vocabulary 或缺失语义仍硬失败。
- Gemma 协议改为真正按 role 生效：intake 2048、analyzer 4096、writer 8192（仅 length retry 12288）、supervisor 1536、planner 2048、local rewrite 3072、semantic verifier 1024；24576 仅为 Method 累计。旧 authoring wrapper 的 4096 clamp 已移除。R8 不再误用全局 temperature=0，而是验证每条 trace 的 role temperature、top-p/top-k 和输出 ceiling。

### 0.3 Holdout 结果与未完成 P0

无 LLM deterministic probe 未添加任何项目专用 profile/literal：

- Lookahead：从错误的 736 claims 收紧为 2 个 supported typed stages / 4 条源码锚定 claims；接入 richer semantic gate 后 deterministic replay 保留 2 个 supported stage、把角色未证实的主线保持为 partial/unresolved，并在 authoring evidence gate 处解释性阻塞。正式 `lookahead-live-r9` 已安全阻塞于 `generic_path_compilation_required`，`v3_error` 为空；重检后 Intent proposal criterion 已通过，未把“没有 writer”误报为 intent 失败。
- Bootstrapping：旧探针曾产生 epoch/router 等低相关 claims；最新 deterministic replay 走 `generic_path_compilation_required`，`v3_error` 为空，未把这些低相关候选提升为正文事实。

Lookahead 的两个 generation stage 曾可能同时绑定同一通用 `engine.generate`。现已将 `TypedBehaviorTargetV1.role/inputs/transformations/decisions/outputs/conditions/required_relations` 接入候选编译与最终 coverage/claim-binding 重放：事实持久化 source-derived `semantic_context` 和 verified `relation_kinds`，因此 checkpoint/resume 后不会退化为 predicate-only 判断。Gemma Intent Agent 还必须保留 deterministic target 的所有 predicate/relation；空 target 或删减 token 的严格 JSON 响应被原子拒绝。validator 会把精确 failure 返回同一 Intent Agent 做至多两次有界纠正；耗尽后显式阻塞并令 R8 失败，不回填规则结果冒充成功。完整修复版 Bootstrapping 正式 `bootstrapping-live-r13` 正在运行；尚待最终 V3/R8 outcome。

## 1. 分批状态

| 批次 | 状态 | 已有证据 | 主要缺口 |
|---|---|---|---|
| R0 contracts/authority/StateV3 | 基本完成 | `research_models.py`、`source_authority.py`、`state_v3.py` 及对应测试 | 需要在真实产物中复核所有 artifact reference/freshness，而不只是模型测试 |
| R1 细粒度工具 | 部分完成 | 26 个工具、schema、manifest、安全测试存在 | production research runtime 默认只开放部分工具；尚无 RAP/EBCAR/DyG/LinearRAG 四项目工具 API 退出证据 |
| R2 CodeBehaviorGraph | 部分完成 | Python adapter、行为图、relation/mutation 测试存在 | 跨函数 CALL/DATA/CONFIG relation recall 未在四项目证明；动态关系 gap 闭包未实跑 |
| R3 Research Supervisor graph | 代码路径基本完成 | 生产入口执行 9-node subgraph；真实 MemorySaver 跨实例恢复已补 | Gemma 自主完成三种工具序列、顺序无关支持边界、live policy trace 尚未验收 |
| R4 generic compiler | 部分完成 | generic packet/fact/claim compiler 已接 research loop，ML fixture 能产出 compiled evidence | equation contract 未接生产；packet proposal/validate/authorize 仍多为直接节点调用，不是完整 Agent tool loop |
| R5 intent/obligation | 基本完成（静态） | typed intent、multilingual/paraphrase tests 存在 | 四真实项目 mismatch/gap 和组织等价性尚未验证 |
| R6 authoring/local repair/quality | 主链已接通，packet research 闭环未完 | V3 plan 已在 planner 成为生产 gate；`local_text_repair`、`packet_binding_repair`、QualityState/best text artifact 已进入正式拓扑 | packet relation/code-search 请求目前 typed fail-closed，尚不能自动产出修复后的 packet；checkpoint 后 best-text restore 等价性仍需 live 验证 |
| R7 behavior templates | 组织提示已接生产，检索增强未接 | V3 wrapper 对最终 behavior graph 做结构匹配，持久化 match/stage hints；writer 仅将其作为已授权 claims 的排序提示；禁用时 generic compiler 仍产 supported facts 的测试存在 | 尚未用于 supervisor 的前瞻搜索/tool selection；四项目开关对照仍需 live 验证 |
| R8 live quality | 内容基线完成，当前协议重新验收中 | 四开发项目历史 content-accepted、unsupported=0、resume digest 一致；Lookahead/Bootstrapping deterministic replay 已无静默授权 | 旧运行缺 Intent trace 与完整 API provenance；需用正式 API 重跑，再完成两个无 profile holdout 的 outcome 与 resume 对照 |

## 2. Transition Reference 状态

本节的逐 Commit 技术清单保留原计划的细节；其中“尚未运行”的历史措辞已经被第 0.1 节四个正式运行结果覆盖。后续缺口以第 1 节和第 4 节为准。

### Commit 1：profile registry + RAP 无回归

实现与 RAP 内容回归已完成；当前 role-budget policy 下仍需重跑正式验收：

- 已新增 `SemanticStageGroupV1`；
- generic claim compiler 会按 obligation 生成 stage groups；
- V3 projection 已删除 `C-RAP-*` 分组和 RAP/Softmax 固定写作规则；
- V3 authoring 缺少 validated packets/claims 时 fail closed 为 `generic_path_compilation_required`；
- 已建立 `evidence_profiles` registry seam，并加入结构匹配与 symbol mutation 测试；
- profile ID、required/optional fingerprints、命中理由和缺失指纹已写入
  `evidence_profile_match*.json`，并作为 evidence stage artifact 和 metric 进入运行状态；
- RAP packet/fact/claim 与结构指纹实现已机械迁入
  `evidence_profiles/rap_pruning.py`；公共 compiler 已无 `EP/F/C-RAP-*`、RAP symbol
  或 Softmax column-zero 项目 literal，并由静态边界测试保护；
- RAP `rap-live-r5` 已产出内容、profile、role trace 与 resume digest；但它不含当前 Intent trace，且 legacy intake/analyzer 仍用 supervisor 标签，因此必须重跑。

### Commit 2：EBCAR

确定性 vertical slice 已实现，且 `ebcar-live-r2` 已完成历史内容验收：

- 新增 `evidence_profiles/ebcar_reranker.py`，只由 forward/rerank、结构 embedding
  相加、query/passage 拼接、两种 attention scope、fixed-query 矩阵乘和 descending
  sort 的 executable fingerprints 激活；
- 在真实旧项目 snapshot 上编译得到 4 packets、12 facts、8 claims、4 semantic
  stage groups，common validator failure 为 0，claim direct fan-in 最大为 3；
- V3 projection 对该 profile 默认 `safe_equations=[]`，保持 prose-first；
- same-document mask 改成全零、descending sort 改成 ascending、只加入项目名/paper
  prose 三类 mutation 均不能继续授权该 profile；
- EBCAR 串行 Gemma 全流程、逐句 unsupported=0 与 plan/final gate 联合证据已由 `ebcar-live-r2` 产出；当前 protocol 重跑仍待执行。

### Commit 3：DyG-Mamba

确定性 vertical slice 已实现，且 `dyg-live-r3` 已完成历史内容验收：

- 新增 `evidence_profiles/dynamic_graph_mamba.py`，由 first-hop history、四通道投影、
  elapsed-time `dts` 传递、time-conditioned selective scan、cross attention、gated
  top-k renormalized readout 与 task head 的组合结构激活；
- 在真实旧项目 snapshot 上编译得到 6 packets、8 facts、7 claims、5 semantic
  stage groups，common validator failure 为 0，claim direct fan-in 最大为 3；
- spectral-norm B/C、MEAN pooling、paper-form timespan equation 和性能/鲁棒性/
  复杂度结论均进入 explicit code gap，不进入正向 claims；
- 移除 encoder `dts` 传递、移除 top-k/renormalization、只加入 paper conflict
  文本的 mutation 均不能继续授权相应 profile/claim；
- DyG-Mamba 串行 Gemma全流程和逐句 unsupported=0 证据已由 `dyg-live-r3` 产出；当前 protocol 重跑仍待执行。

### Commit 4：LinearRAG

确定性 vertical slice 已实现，且 `linearrag-live-r2` 已完成历史内容验收：

- 新增 `evidence_profiles/linear_graph_retrieval.py`，由 offline entity/sentence
  indexing、双向 COO sparse tensors、query-entity seed、threshold/top-k/used-mask
  propagation、hybrid passage weights、personalized PageRank descending sort 和
  no-seed dense fallback 的组合结构激活；
- 在真实旧项目 snapshot 上编译得到 7 packets、10 facts、9 atomic claims、5
  semantic stage groups，common validator failure 为 0，claim direct fan-in 最大为 3；
- dense fallback 是带 `seed_entities is empty` qualifier 的独立 claim；性能、复杂度、
  noise/lossless rationale 与 paper MAX equation 共 6 项进入 explicit gap；
- 分别移除 threshold、per-entity top-k、used-sentence mask、score accumulation、PPR
  descending sort 后，相应 profile/claim 不能继续授权；paper-only rationale 不能激活；
- LinearRAG 串行 Gemma、sentence/claim atomicity 的真实 writer 输出与逐句 unsupported=0
  已由 `linearrag-live-r2` 产出；当前 protocol 重跑仍待执行。

### Commit 5：local repair + best state + usability gate

主链已接通，剩余 scoped research repair 与 usability/live gate：

- 已增加严格 `PacketRepairRequestV1`，包含 claim、packet、failure type、offending spans、missing relation、requested scope 和 attempt；
- final-text failure 的生产路由集合已移除 `intake/analysis/evidence/authoring`；
- `local_text_repair` 只允许 exact-span wording rewrite、claim/drop repair，随后回到 final claim extractor；
- packet relation/code-search 问题会持久化 typed request，并进入独立 `packet_binding_repair`；当前该节点 fail-closed，尚缺调用细粒度 research tools 后重编译单 packet 的成功路径；
- `build_authoring_plan_v3` 已在 production `authoring_planner` 构建并执行 gate，legacy plan 仅作兼容诊断；
- V3 merged claims 会先通过 typed fact IDs 绑定 obligations，再构建 coverage 与 plan；
- 每轮 final-text validation 会写 current/best `QualityStateV2` 与 best Method 快照；候选回退时恢复 best text 并重新抽取/验证；
- behavior templates 已在 production V3 wrapper 生成结构 match artifact，并以 non-authorizing stage hints 进入 writer；尚未影响 supervisor 搜索策略；
- `method_plan_quality.json` 尚未形成独立 usability gate，且 best-state checkpoint/resume 等价性尚缺 live 证据。

## 3. 必须补齐的验收证据

1. RAP profile 迁移后语义等价，projection 中无项目 literal。
2. EBCAR、DyG-Mamba、LinearRAG 由结构指纹激活，关键 symbol mutation 后不得误激活。
3. 四项目所有 must-cover obligation 均为 supported/partial/explicit gap。
4. 最终 Method 每个事实句 direct/relation evidence 可追溯，unsupported=0。
5. 一个句子失败只触发指定 packet/claim/sentence repair，不重跑 intake/analysis/整篇 authoring。
6. repair 质量回退时恢复 best artifacts，checkpoint/resume 与 uninterrupted 结果一致。
7. 禁用 templates 后 generic compiler 仍能产生 supported claims；启用模板只改善搜索和组织。
8. Lookahead 加另一个 holdout 不增加项目专用 compiler/template/claim literal。
9. 已配置正式 API 的 provider/model/脱敏 endpoint 与 capability digest 可追踪，所有参与角色都有非缓存、非空 response trace，并固定全部 digest/trace。

## 4. 后续实施顺序

下一步按风险和依赖推进：

1. 完成 Commit 5 剩余项：packet-scoped research tool loop、single-packet recompile/rebind、usability gate、checkpoint/resume best restore 对照。
2. 把 behavior template 从已接通的 writer 组织提示扩展到 supervisor 的仅检索增强，并做开关授权不变 live 对照。
3. 接通 equation contract；继续保持 EBCAR prose-first，并对有代码闭式公式的 profile 做独立授权。
4. 完成修复版 Bootstrapping 的 V3/R8 recheck；用 RAP 先证明新 Intent/role protocol 能进入 writer，再严格串行重跑 EBCAR、DyG-Mamba、LinearRAG。
5. 对 Lookahead 与第二个 holdout 做同一 policy 的 resume/对照；两者都保持无项目 literal、证据不足 fail-closed 后，才讨论 benchmark/cutover。
