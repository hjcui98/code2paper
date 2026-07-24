# Code2Paper 可决策研究写作 Agent V2 执行文件

状态：当前唯一执行计划  
依赖设计：`docs/agentic_research_writing_agent_v2_design.md`  
唯一主目标：根据作者意图和代码证据，稳定产出信息充分、组织合理、逐句可追溯、可直接继续编辑的论文 Method 正文。

## 0. 当前决策

1. 当前工作不再围绕 benchmark/cutover 展开。25-run、gold、observation extractor 和 rollout 只作为未来发布验证，不决定近期架构优先级。
2. 近期主线是修复五个真实项目暴露的正文质量瓶颈，优先顺序为 RAP、EBCAR、DyG-Mamba，再回归 LinearRAG 和 Lookahead。
3. `unsupported rate = 0` 仍是不可退让的 trust gate，但不再被当作“正文可用”的充分条件。
4. P0/P1/P3 已有的 author intent、Evidence V2、freshness、LangChain tools、typed state、checkpoint/resume 继续复用。
5. P2 暂时只视为渲染与漂移审计基础；方法图不得反向拖慢正文架构，正文达到可用门槛后再补图关系与拓扑。
6. 工作区已有 raw observations fail-closed 和 fleet false-block 修复保留、测试、单独交付，但不继续扩张为本轮主任务。

## 1. 当前真实基线

| 项目 | 投影 claim / 去重 | 最终事实 claim | 正文词数 | 主要质量问题 |
|---|---:|---:|---:|---|
| RAP | 2 / 1 | 1 | 28 | 源码有 feature、MLP、权重加载、前向评分和 pruning，系统只写出 feature |
| EBCAR | 10 / 5 | 8 | 169 | 信息量尚可，但 Motivation 标题下写 inference ranking，章节语义错配 |
| DyG-Mamba | 6 / 4 | 5 | 129 | 仅保留宽泛 encode/filter/readout，关键动态状态机制展开不足 |
| LinearRAG | 7 / 3 | 3 | 116 | 可用但重复投影明显，仍缺精确的阶段/关系组织 |
| Lookahead | 2 / 1 | 1 | 32 | 只写 verifier 的最长前缀行为，方法主线严重不足 |

当前结论不是“模型不会写”，而是 writer 收到的授权事实过少、过宽或组织错误：

- 作者 YAML 被扁平化成检索 target，target 命中不能代表核心方法义务被解决；
- claim 先继承宽泛作者措辞，验证失败后整句删除，无法保留源码支持的子句；
- 单个 claim 携带 9--22 个证据 span，缺少最小证据和组合关系；
- stage name、claim、evidence、section heading 是弱连接对象；
- LangGraph 决策围绕“coverage 分数够不够”循环，没有围绕“哪个方法义务尚未解决”循环。

## 2. 质量验收模型

正文必须同时通过两个平面。

### 2.1 Trust plane

- 每个事实性原子句都引用直接 source/config/script/build 证据；
- narrative 文件只作检索 hint；
- unsupported leakage 为 0；
- partial claim 保留必要 qualifier；
- final text、claim trace、evidence snapshot 和 repo snapshot digest 一致。

Trust 失败必须阻断。

### 2.2 Usability plane

- 作者的每个 `must_cover` 方法义务都有 supported、partial 或 explicit gap 终态；
- 源码已经实现的核心机制不能静默丢失；
- 正文按计算/数据流组织，而不是机械复述 YAML 标题；
- 重复 canonical claim 只写一次；
- 每节标题与本节 claim 语义一致；
- 每个核心 claim 默认使用 1--3 个最小证据 span；
- 正文解释输入、变换、输出、条件和关键关系，而不只是列出模块名。

Usability 不足时，LangGraph 应优先定向取证或 claim decomposition；预算耗尽后只允许交付带 gap report 的不完整草稿，不能标为 usable completion。

## 3. 阶段总览

| 阶段 | 目标 | 退出结果 |
|---|---|---|
| Q0 Real Quality Baseline | 固化真实正文瓶颈和可复跑摘要 | 五个 sentinel 的质量基线 |
| Q1 Intent Obligations | 把 YAML 编译成待解决的方法义务 | must-cover 不再静默消失 |
| Q2 Evidence Acquisition | 按义务取得最小代码事实与关系 | 每个义务有 evidence packet 或 gap |
| Q3 Claim Compiler | 从代码事实生成窄、可写 claim | RAP 宽 claim 可拆成支持/不支持部分 |
| Q4 Narrative Decision | 按意图价值和代码流组织正文 | 可用 Method 正文，不再错配标题 |
| Q5 Figure Projection | 从已授权正文 claim 投影方法图 | 图不引入正文之外的新事实 |
| Q6 Real Sentinel Loop | 盲跑、审计、继续修复 | 五个真实项目达到 trust + usability |
| Q7 Release Verification | 最后再做 benchmark/rollout | 仅用于发布，不反向主导架构 |

## 4. Q0：真实质量基线

### Q0-01 持久化当前 observation

为五个真实项目保存以下摘要和来源 digest：

- author story/pipeline 数；
- retrieval target covered/partial/missing；
- verified supported/partial/unsupported；
- projection claim 数与去重数；
- final factual claim 数和正文长度；
- 每个 claim 的 evidence fan-in；
- section heading 与 claim 的语义一致性；
- 源码可支持但正文遗漏的机制清单；
- figure node/edge 数仅作附属诊断。

产物：`docs/agentic_real_method_quality_baseline_2026-07-18.json`。

### Q0-02 固化三个正文 regression fixture

1. RAP：宽作者 claim 中，feature、predictor、weight load、score、mask/prune 可支持，training/three losses 不可支持；
2. EBCAR：Motivation heading 不得绑定 inference ranking claim；
3. Lookahead：单一 verifier claim 不得被误判为完整可用 Method。

## 5. Q1：Intent Obligation Graph

### Q1-01 编译义务，不编译事实

新增 `IntentObligationGraphV1`：

- `pipeline_steps` -> `mechanism/stage`，默认 `must_cover`；
- `module_roles` -> `component`，默认 `should_cover`；
- `method_mainline` -> `method_mainline`，默认 `must_cover`；
- `paper_story_order` -> `organization`，只影响组织；
- `design_intents` -> `rationale_check`，只生成检索问题；
- `innovation_claims` -> `high_risk_claim`，必须验证后才能写；
- `potential_mismatches` -> `mismatch_check`，优先澄清冲突。

每个义务包含作者原文、优先级、候选路径、检索 query、状态和来源字段。作者原文永远不能直接成为正文事实。

### Q1-02 义务覆盖报告

在 authoring 之前生成：

- 已被授权 claim 覆盖的义务；
- 仅部分覆盖的义务；
- 尚未解决但仍有预算的义务；
- 代码范围内未实现/无法证明的义务；
- 无对应作者义务的已支持代码 claim。

退出门槛：每个 must-cover 义务都能追踪到 claim、repair task 或 explicit gap。

## 6. Q2：按义务取最小证据

### Q2-01 Obligation scheduler

LangGraph 每轮只选择一个高价值未解决义务，并记录：

- 为什么现在处理它；
- 要调用的 search/read/relation 工具；
- 预计新增哪些正文信息；
- 当前 attempt/budget；
- 终止条件。

调度优先级：`must_cover` > 直接影响主线的关系 > supporting component > organization。

### Q2-02 EvidencePacketV3

每个义务独立建立 packet：

- 默认 1--3 个 exact code spans；
- symbol identity、line range、excerpt digest、snapshot binding；
- caller/callee、data-flow、config binding 等 relation；
- 每个 span 的必要角色；
- 被排除的相似候选及原因。

超过 3 个 span 必须给出 composition rationale。禁止把全仓库证据并集交给一个 claim 做模糊语义匹配。

### Q2-03 定向 repair

| 失败类型 | 下一动作 |
|---|---|
| path/symbol 未命中 | 改 query/path seed |
| span 过宽或同名歧义 | exact symbol read |
| 调用顺序未证明 | call-flow trace |
| 输入输出关系未证明 | data-flow trace |
| 配置值无消费点 | config binding trace |
| 负面范围过宽 | 缩小到 function/module scope |
| 预算耗尽 | explicit gap，不写入正文 |

## 7. Q3：Evidence-first Claim Compiler

### Q3-01 CodeFactV1

先从代码生成类型化事实，再与作者义务对齐。首批 predicate：

- `constructs`、`loads_weights`；
- `calls`、`calls_in_order`；
- `reads`、`transforms`、`returns`；
- `filters_by`、`branches_on`；
- `computes_formula`；
- function-scoped `does_not_call`。

### Q3-02 obligation decomposition

一个宽作者句必须拆成多个可验证子义务，分别给出：

- supported subclaim；
- partial subclaim + qualifier；
- unsupported fragment；
- not implemented/gap。

RAP 的首个退出门槛：最终至少可覆盖 feature construction、PrunePredictor、checkpoint load、score inference、sorting/mask/prune path；同时继续拒绝源码缺失的 training program 和 three-loss 定义。

### Q3-03 claim 最小性

每个 `AtomicClaimV3` 显式记录：

- canonical wording；
- fact IDs；
- obligation IDs；
- direct/relation evidence IDs；
- required qualifiers；
- unsupported author fragments。

writer 只能消费 canonical wording 及其受控改写边界。

## 8. Q4：正文决策与写作

### Q4-01 Narrative planner

输入仅包括：

- authorized AtomicClaimV3；
- obligation coverage；
- code/data-flow relation；
- author organization preferences；
- explicit gap list。

模型可以决定 claim 分组、顺序、篇幅和过渡；不能引入新事实。默认章节按代码支持的主线组织：输入/表示 -> 核心变换 -> 评分/决策 -> 输出/部署路径。作者 story 只作为偏好，不作为强制标题。

### Q4-02 section semantic gate

- heading 必须由本节 canonical claims 生成，或通过 heading-to-claim 语义 validator；
- 每节至少有一个 claim；
- motivation/benefit/novelty heading 不得承载纯实现 claim，除非相应 rationale 有直接代码约束；
- 同一 canonical claim 不得跨节重复；
- qualifier 必须跟随 claim，不能在合并段落时丢失。

### Q4-03 final reverse validation

从最终 Method 反向抽取原子句，逐句重算：

- 是否映射到 authorized claim；
- 是否保留 scope/condition/qualifier；
- 是否有直接代码证据；
- 是否出现未授权的因果、效果、训练或部署泛化；
- must-cover code-supported claim 是否在正文中出现。

## 9. Q5：方法图作为正文投影

正文通过后才制图。图节点只能引用已进入 Method contract 的 claim，标签从 canonical claim 受控缩写生成；图边只能引用 relation evidence。

- 有关系证据：可生成 `method_flow`；
- 只有组件事实：生成 `component_map`；
- 只有孤立事实：生成 `evidence_atlas`，明确不是流程图；
- 无关系证据时不得用箭头、pipeline、then 等语义。

图的修复不能反向放宽正文 claim。

## 10. Q6：真实 sentinel 闭环

盲跑协议固定：

1. 只读取代码和作者 YAML；
2. 生成 obligations、evidence packets、facts、claims、Method、gap report；
3. 固定摘要和 digest；
4. 最后才读取原论文作 diagnostic 对照。

### 第一轮：RAP

目标是验证 claim decomposition 和源码 recall。不是追求复现原论文全部内容，而是把仓库真实存在的 inference/pruning 路径完整写出来，并明确训练/损失 gap。

### 第二轮：EBCAR

目标是验证章节语义、claim 去重和阶段关系。正文不得再出现 Motivation/inference 错配。

### 第三轮：DyG-Mamba

目标是验证复杂动态状态机制的最小证据组合，不用泛化的 encode/filter/readout 代替关键变换。

### 回归：LinearRAG、Lookahead

确认新机制不会损害已有成功结果，并检查 Lookahead 是否能从代码恢复更多主线事实。

## 11. 第一执行批次

本批次只做直接影响正文的工作：

1. 新增 `IntentObligationGraphV1` 和 authoring coverage artifact；
2. 将 author intent summary 真正传入 projection 模式的 authoring planner；
3. 删除 author stage name 作为无条件正向 writer 输入的路径，heading 必须由已授权 claim 派生；
4. 增加 EBCAR heading 和 RAP obligation/decomposition 的 regression tests；
5. 持久化五项目质量基线；
6. 重跑 RAP deterministic，检查正文是否能超越单一 feature claim；
7. 若仍失败，下一批直接实现 EvidencePacketV3/CodeFactV1，不转去扩写 benchmark。

## 12. 本轮不做什么

- 不以扩大 25-run 矩阵为进展；
- 不先实现 default-ready authorization bundle；
- 不用人工 review 数量替代正文质量；
- 不用词数门槛强行拉长缺证据的正文；
- 不因图缺边阻塞 claim compiler 的实现；
- 不把原论文内容回填成源码事实。

## 13. 测试与状态规则

每批至少执行：

```bash
python -m pytest -q <本批定向测试>
python -m pytest -q tests/test_agentic_authoring_projection.py tests/test_agentic_contracts.py tests/test_agentic_final_text_trust.py
python -m pytest -q
```

阶段状态只有 `not_started`、`in_progress`、`verified`。只有 contract、定向测试和至少一个真实 sentinel 产物同时证明目标行为，才能标记 `verified`。

### 2026-07-18 首个 RAP slice 实测结论

本轮新增 obligation graph 后连续做了三次 deterministic 真跑，根目录为 `/tmp/code2paper-quality-v2-20260718`：

1. `rap-det` 证明原先共享 `evidence_revision` 预算使 obligation repair 在 authoring 前已经耗尽；同时发现 duplicate claim 的 denial qualifier 会污染正向正文，产生“supported feature; unsupported by current code evidence”的自相矛盾句。
2. `rap-det-r2` 改用独立 `obligation_revision` 后，authoring planner 确实执行两轮 `authoring_obligation_repair`；denial qualifier 已被移出正向 projection，正文不再自相矛盾。
3. `rap-det-r3` 将 obligation repair 改为先回到 targeted intake，再进入 analysis。intake snippet 从 35 增至 37，focus 已包含 `PrunePredictor.forward`、`GaussianModel.get_prune_input_f15` 和 `GaussianModel.prune_points`，但最终仍只有一个 feature claim。

这三次真跑把下一瓶颈确定为：旧 `code_facts.json` 和 evidence freeze 仍按作者 pipeline scaffold 生成宽 claim，不能从 exact symbol/call path 编译新的窄 claim。继续增加 loop 或 prompt 不会解决问题，下一批必须直接实现 Q2 EvidencePacketV3 和 Q3 CodeFactV1/claim decomposition。

同时，completion report 已增加 `method_usability` 检查。即使 trust、trace 和 package 全通过，只覆盖 1/5 must-cover obligation 的 RAP 也只能标记为 trustworthy-but-incomplete，不能再显示 complete。

当前状态：

| 阶段 | 状态 | 当前 blocker |
|---|---|---|
| Q0 | verified | 五项目基线已写入 `agentic_real_method_quality_baseline_2026-07-18.json` |
| Q1 | verified | obligation graph、coverage、独立预算和 targeted intake 路由已通过 RAP 真跑 |
| Q2 | in_progress | 已能定位 symbol，但尚未建立 1--3 span EvidencePacketV3 |
| Q3 | not_started | 尚无 evidence-first CodeFact/claim decomposition |
| Q4 | in_progress | heading 安全投影和 best-stage assignment 已完成；正文 recall 仍受 Q3 限制 |
| Q5 | not_started | 等正文 contract 稳定后再实现 |
| Q6 | in_progress | RAP 三次 slice 真跑完成；等待 Q2/Q3 后再验收正文 recall |
| Q7 | deferred | 发布前再恢复 benchmark/cutover 工作 |

### 2026-07-19 RAP Gemma 完整复跑结论

本轮纠正了把 deterministic 诊断当作真实质量结论的问题。使用真实 RAP 代码、原始作者 YAML 和本地 `gemma4-31b-nvfp4` 完整执行 draft bootstrap、LangGraph 决策、LLM code analysis、evidence repair、authoring planner、LLM writer、逐句 validator 与 invariant audit。原论文在盲阶段摘要及 digest 固定后才读取。运行根目录为 `/tmp/code2paper-quality-v2-20260719/rap-gemma-r1`，持久化机器报告为 `docs/agentic_rap_gemma_quality_eval_2026-07-19.json`。

运行预算为 retrieval 2、evidence revision 2、authoring/obligation revision 2、figure revision 1、semantic verifier 1。最终结果不是可信完成，而是安全阻断：

- `blocked_reason=text_claim_direct_evidence_missing_budget_exhausted`；
- candidate Method 48 词、3 个事实句，仅 1 个通过直接证据验证，最终 unsupported rate 为 2/3；
- must-cover obligation 为 0/5；
- projection 只有 3 个 claim、去重后只有 2 个，其中 `C2`/`C9` 完全重复；
- Gemma writer 确实被调用一次，不能把失败归因于 deterministic writer；
- 2 次 retrieval、2 次 evidence revision、2 次 obligation revision 均耗尽，仍未形成完整正文。

这次复跑证明 retrieval 并不是主瓶颈。最终 Evidence V2 已包含：

- `E17`：`utils/gaussian_model.py:192-264`，`GaussianModel.get_prune_input_f15`；
- `E6/E8/E10`：`utils/net_utils.py` 中 `PrunePredictor`、`forward`、`load_model`；
- `E1`：`prune_percent.py:8-37`，完整 inference/ranking/mask 主路径；
- `E18`：`utils/gaussian_model.py:266-272`，`GaussianModel.prune_points`。

但是 feature claim `C2/C9` 被错误绑定到 `E57/E58`，即 `compute_sh_anisotropy_loop(_std)`，而不是 `get_prune_input_f15` 与实际 normalization spans。最终 validator 因 `direct_evidence_semantically_unrelated` 拒绝两个 feature 句。与此同时，V2 中重复出现且已支持的 predictor/score claim `C1/C3/C4/C10` 被 projection 排除，writer 没有权限恢复它。由此得到优先级结论：

1. **先修 claim-to-evidence compiler，不再加 loop。** exact spans 已经检索到，重搜不会修复错误绑定。
2. **先生成类型化 CodeFact，再做 claim。** 不允许用作者 stage scaffold 或宽 claim 去反推证据。
3. **validator 失败应路由到 packet/binding repair。** `direct_evidence_semantically_unrelated` 不应回到泛化 analysis/retrieval。
4. **semantic hint 只产生 verify-only obligation。** `paperdraft.md` 中训练集、soft pruning、three-loss、entropy 描述不得反复消耗主线预算；没有 executable evidence 时直接终结为 code gap。
5. **Gemma 决策也必须被类型化事实约束。** 本轮 coverage critic 曾把 `percentile_cutoff_normalize` 误判为 entropy regularization 的实现；后续 gate 保住了可信度，但模型判断没有推进正文。

### 下一批：RAP Evidence Compiler vertical slice

下一批不得以 prompt、额外 loop、benchmark 或 figure 为主任务。必须同时交付 `EvidencePacketV3 + CodeFactV1 + obligation/claim decomposition + AtomicClaimV3 projection`，直接编译以下源码路径：

```text
prune_percent.py:prune_pure_feature
  -> GaussianModel.get_prune_input_f15
  -> PrunePredictor.__init__ / load_model / forward
  -> scores[:, 0]
  -> scores.argsort(descending=True)
  -> top keep_num indices
  -> boolean valid_mask
  -> GaussianModel.prune_points
  -> save_ply + score npy
```

其中跨文件证据必须来自：

```text
utils/gaussian_model.py  feature construction + normalization calls + tensor filtering
utils/net_utils.py       predictor structure + checkpoint loading + forward semantics
prune_percent.py         orchestration + score selection + sorting/top-k/mask + outputs
```

首批 packet 固定为：

| packet | anchor span | relation spans | 目标事实 |
|---|---|---|---|
| `EP-RAP-FEATURE` | `GaussianModel.get_prune_input_f15` | `compute_knn_z_score`、`z_score_tensor`、`percentile_cutoff_normalize` | 读取属性、构造局部/全局统计、拼接并归一化 per-primitive feature |
| `EP-RAP-PREDICTOR` | `PrunePredictor.__init__` | `load_model`、`forward` | 构造 MLP、加载 checkpoint、输出两类 Softmax，调用方选择第 0 列作为 score |
| `EP-RAP-PRUNE` | `prune_pure_feature` | `GaussianModel.prune_points`、`save_ply` | retention ratio、降序排序、top-k、布尔 mask、张量过滤与输出保存 |

`EP-RAP-FEATURE` 超过 3 个 span 时必须记录 composition rationale；不能为了满足默认 span 数量而丢掉 normalization relation。每个 packet 还必须记录 rejected candidates，例如明确说明 `compute_sh_anisotropy_loop(_std)` 只能支撑 anisotropy 子特征，不能独立支撑完整 feature-construction claim。

首批 `CodeFactV1` 至少编译：

- `reads`：position、opacity、scale、SH/DC color；
- `transforms`：KNN statistics、local/global z-score、scale sorting、volume、percentile clipping/rescaling；
- `constructs`：feature tensor、`PrunePredictor`、boolean mask；
- `loads_weights`：`net_weights_path -> PrunePredictor.load_model`；
- `calls_in_order`：feature -> predictor -> score -> ranking -> mask -> prune -> save；
- `selects`：predictor output `[:, 0]`；
- `filters_by`：`prune_points(valid_mask)` 对 Gaussian tensors 的逐项过滤；
- `writes`：pruned PLY 和 score NPY。

每个事实必须有 `scope`、direct span ids、relation span ids、conditions 和 exact source digest。随后按事实拆出窄 `AtomicClaimV3`，禁止再次生成“整个 stage 由 E1/E29 支撑”的宽 claim。canonical deduplication 以 normalized behavior + fact ids 为准；`C2/C9` 这种重复不得进入 projection。

下一次 RAP 验收必须再次使用 Gemma 完整复跑，而不是 deterministic 替代，并同时满足：

1. 原论文仍在盲产物摘要固定后才读取；
2. `EvidencePacketV3`、`CodeFactV1`、`AtomicClaimV3` 均进入 manifest、freshness 与 traceability；
3. 代码支持的 inference mainline 按 feature -> predictor -> score -> sorting/mask -> prune 顺序进入 projection；
4. must-cover 义务全部得到 supported、partial 或 explicit code gap 的终态，不能保持 unresolved；
5. 最终正文至少形成多个有语义分工的段落，而不是一条 claim 一个标题；
6. 每个最终事实句均通过 direct/relation evidence 反向验证，unsupported rate 为 0；
7. training program、DL3DV-10K、soft pruning、three-loss/entropy 继续作为 explicit gap，除非找到新的 executable evidence；
8. 若原论文与源码不一致，正文跟随源码。例如当前代码是 two-logit Softmax 并取第 0 列，不得照抄 paper 中 single sigmoid score；
9. RAP 质量验收通过前，Q7 benchmark/cutover 继续保持 deferred。

### 2026-07-19 RAP Evidence Compiler vertical slice 验收结果

本切片已按上述协议完成真实 Gemma 全量复跑。盲测固定产物为
`/tmp/code2paper-quality-v3-20260719/rap-gemma-v3-r4`，机器可读报告为
`docs/agentic_rap_gemma_v3_quality_eval_2026-07-19.json`。

- `EvidencePacketV3=3`、`CodeFactV1=13`、`AtomicClaimV3=8`、explicit code gap `=3`；
- V3 artifacts 已进入 manifest、freshness、traceability 和 invariant audit，freshness passed、stale keys `=[]`；
- Gemma writer 真实调用 1 次，生成 3 个语义段落、8 个事实句；逐句反向验证 `8/8` supported，unsupported rate `=0`；
- projection 保持 feature -> predictor -> score column 0 -> descending sort/top retention -> boolean mask -> prune -> PLY/score NPY 的源码顺序；
- training program、DL3DV-10K、soft pruning、three-loss/entropy 终结为 explicit code gap，未进入正向实现正文；
- 最终 run `status=success`、completion `complete=true`、invariant blocking failures `=0`；
- 完整测试：`511 passed, 2 skipped, 6 subtests passed`；
- Q7 benchmark/cutover 继续 deferred。最终 PDF 因环境缺少 LaTeX compiler 使用 Pillow 可读性 fallback，不影响本 Q2/Q3 证据与正文验收，但不能视为 publication-quality PDF。

盲测摘要和 Method digest 固定后才读取原论文进行诊断。对照确认论文写的是 single-dimensional sigmoid，而当前源码实现是 two-logit Softmax 并选择第 0 列；冻结正文正确服从源码。论文中的 renderer-backed training、soft opacity/scale reweighting、three-loss/entropy、15,000 iterations 与 DL3DV-10K 十场景训练没有被无证据写入正文，继续保持 explicit code gap。

### 2026-07-19 跨项目串行 Gemma 诊断与下一执行批次

RAP V3 成功后，使用同一个双卡 TP=2 Gemma 实例严格串行完成 EBCAR 和 DyG-Mamba 全流程。此前并发启动后停止的两个 r1 运行被标记无效，不进入质量结论。干净运行结果：

| 项目 | 路线 | must-cover | 唯一 projection claim | 最终支持 | 结果 |
|---|---|---:|---:|---:|---|
| RAP | V3 compiler | 全部终态 | 8 | 8/8 | success |
| EBCAR | V2 fallback | 5/6 | 5 | 0/9 | blocked |
| DyG-Mamba | V2 fallback | 4/5 | 4 | 1/14 | blocked |

这两个新样例证明下一瓶颈是 **V3 的跨项目泛化**。当前 `compile_evidence_v3`、`_compile_facts`、`_compile_claims` 和 `_build_v3_projection` 仍内置 RAP symbol、fact、claim、stage 和写作规则；未命中的项目回退到宽 claim V2，单 claim 绑定 14--22 个 span，再由一个全局 semantic-verifier budget 承担验证，最终在 writer 后失败。

完整机器报告：`docs/agentic_real_method_quality_gemma_expanded_eval_2026-07-19.json`。下一步实现边界、EBCAR/DyG packet 主线、局部 repair 路由、mutation 和串行 Gemma 验收协议以 `docs/agentic_method_quality_next_execution_plan_2026-07-19.md` 为准。其优先级高于本文件中所有旧的 benchmark/cutover 项；figure 仍位于正文 trust + usability 通过之后。

### 2026-07-19 LinearRAG 串行 Gemma 扩展诊断

为避免只围绕神经网络项目得出局部结论，又加入 LinearRAG 作为第四个当前质量样例。有效运行根目录为 `/tmp/code2paper-quality-v3-expanded-20260719/linearrag-gemma-r2`；它使用同一个双卡 TP=2 `gemma4-31b-nvfp4` 实例，严格串行、temperature 0、cache off。此前 `/tmp/code2paper-quality-v3-expanded-20260719/linearrag-gemma-r1` 因 sandbox 阻断本地 vLLM 请求而没有有效 Gemma 推理，已排除。

LinearRAG 仍回退到 Evidence V2，最终 `blocked_reason=text_claim_authoring_revision_budget_exhausted`。它与 EBCAR/DyG 不同：Gemma 已生成 159 词、三个组织合理的语义段落，4/4 must-cover obligation 在最后 projection 中均有终态；但 8 个 projected claim 只有 4 个唯一 claim，平均 direct evidence fan-in 10.625、最大 21，最终逐句验证仍为 `0/8 supported`。

这次新增了三条不能靠扩 prompt/loop 解决的架构事实：

1. **可读性不等于可追溯性。** Tri-Graph、entity activation、PPR 三段组织合理，但宽 claim 与 evidence union 仍无法授权具体句子。
2. **semantic verifier 预算模型错误。** 一次真实 Gemma verifier 调用后，五个普通事实句仅因 run-level budget exhausted 而失败；V3 的确定性 fact/relation 已通过时不应再次逐句竞争一个全局预算。
3. **repair 必须质量单调。** 当前修复会重建全量 intake/analysis/evidence/projection，中间 obligation 对齐出现回退，系统没有保留 lexicographically best artifact state。

盲报告固定后再读取原论文。论文确认三段高层组织正确，但也暴露了需要代码优先处理的边界：论文将 dynamic pruning 解释为防止指数增长、提高效率和降低噪声，这些不是阈值比较本身能够证明的实现事实；论文的 compact MAX propagation equation 也不等同于当前代码中的 per-entity top-k、used-sentence mask、sparse propagation、score accumulation 和 threshold 路径。

因此下一执行批次已扩展为三个新 profile：EBCAR、DyG-Mamba、LinearRAG；同时新增 `QualityStateV1`/best-state retention、sentence/claim 共用原子性 contract 和 rationale/equation gap policy。详细 packets、facts、mutation 与验收条件以更新后的 `docs/agentic_method_quality_next_execution_plan_2026-07-19.md` 为准。benchmark/cutover 继续 deferred，figure 继续位于可信可用正文之后。

### 2026-07-19 鲁棒 LangGraph Research Agent 架构纠偏

进一步审计确认：连续增加 RAP、EBCAR、DyG-Mamba、LinearRAG 项目级 compiler，只能提高已知项目覆盖，不能满足“未知项目、代码重构、意图改写后仍能自主研究并写出可信 Method”的鲁棒性目标。当前 LangGraph 的 LLM 主要在固定节点提出路由，LangChain 工具也主要包装完整 stage，尚未向 Agent 暴露可组合的符号搜索、源码阅读、调用追踪、数据流、控制流、配置检查和局部补证工具。

规范性架构现改为：

```text
Author Intent -> Typed Obligations
Repository -> Generic CodeBehaviorGraph
Obligation + Current Gaps -> Research Supervisor (Gemma)
Research Supervisor -> LangChain fine-grained tools
Tool observations -> generic packet/fact/claim compiler
Deterministic trust gates -> Method planner/writer
Typed validation issue -> local Research/Writer repair
```

LLM 获得研究决策自由：可以自主决定下一步搜索什么、调用什么工具、是否追调用/数据流/配置、是否换策略、拆 packet/claim、局部改写或形成 explicit gap；但 LLM 的所有结果只是 proposal，不能自行宣布 evidence supported。最终正向事实仍只能由 executable code spans 和 validated relations 授权。

具名项目 profile 被降级为可组合 `BehaviorTemplateV1`，只提供 graph query、role alias、stage hint 和 match score，不得包含项目 claim 文本或直接授权。核心先实现语言 adapter、`CodeBehaviorGraphV1`、Research Supervisor + ToolNode 循环和 generic fact compiler，再实现行为模板。

新的规范性总体设计为 `docs/agentic_robust_langgraph_research_writing_design_2026-07-19.md`；新的逐批执行步骤仍位于 `docs/agentic_method_quality_next_execution_plan_2026-07-19.md`。原 EBCAR/DyG/LinearRAG packet 方案已移至 `docs/agentic_behavior_template_transition_reference_2026-07-19.md`，只作为行为路径与 mutation 参考，不再驱动主架构。
