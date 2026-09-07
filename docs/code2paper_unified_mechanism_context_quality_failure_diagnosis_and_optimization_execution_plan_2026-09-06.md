# Code2Paper：十项目 Method 信息缺失根因、Unified Context 设计修订与优化执行方案

> **状态**：Root-cause diagnosis complete / Optimization execution proposed / Cutover not approved  
> **分析日期**：2026-09-06  
> **代码基线**：`87e868d`（包含 Formalizer/Writer actual byte identity gate）  
> **目标分支**：`codex/agentic-p4-benchmark-cutover`  
> **被修订的执行设计**：`docs/code2paper_unified_mechanism_context_architecture_redesign_review_revised_v2_2026-09-05.md`  
> **运行范围**：GPU 1 上的 DyG-Mamba、LinearRAG、EBCAR、RAP、Lookahead、UniMMAD、CodeQuant、Domain-Pruning、FastGS、LearNAT 共十个项目  
> **权威边界**：仓库代码与冻结运行产物决定 implementation truth；作者意图决定待解释内容；原论文只用于诊断完整性、公式与论证结构，不授权仓库未证明的实现事实。

本文是在总体 Research Agent 架构、Publication-ready Writer 规范和
`method_intent_first_authoring_redesign_2026-08-22.md` 约束下，对 2026-09-05 v2 Unified
Mechanism Context 执行方案所做的后续诊断与工作包修订。它不替代上述上位权威，也不把一次
十项目运行升级为 rollout/cutover 证明。

---

# 0. Executive Decision

十项目结果不能解释为“Unified Mechanism Context 已实测但效果不好”。更准确的结论是：

1. **十个运行均未真正进入 unified production path。** `run_publication_method_writer()` 默认仍是 `legacy`，两个生产调用方没有传 `authoring_context_mode`，运行配置也没有设置对应环境变量；十个输出目录均不存在 unified context、closure、Narrative V3、mechanism formula、payload trace 或 information-funnel 产物。
2. **当前产品结果为 0/10 publication-ready。** 九个项目生成 Candidate，但九个 `repository_verified_method.md` 均为 0 bytes；LearNAT 连 Candidate 都没有生成。
3. **作者意图“被采集”不等于“已落实”。** 九个可统计项目产生了 213 个 facet alignment，其中 `entailed=0`、`partial=29`、`unresolved=184`。也就是说，13.6% 仅得到部分代码对齐，86.4% 未对齐，完整代码蕴含为 0。211 个 argument brief 中只有 14 个（6.6%）允许进入 Verified，197 个必须带 caveat。
4. **信息损失首先发生在 Research 与运行接线，而不只发生在 Writer。** LearNAT 已读到 MCTS/AST/DPO 代码却没有把 observation 提升为 packet/fact；FastGS 已读到目标 densification 函数却被 ownership 分类为 comparand 并拒绝；Domain-Pruning 的 scope 被 vendored `sglang`、数据与非目标文件严重污染。
5. **七个运行在 callback 写回时被同一个 `NameError` 终止。** `writing_callback_fulfillment.py` 使用了未定义的 `_digest_json`。这不是模型质量波动，而是确定性的 production runtime defect。
6. **v2 的主架构方向应保留，但执行顺序和五项 contract 必须修改。** 必须先补齐 run-mode provenance、source inventory、Research observation promotion、mechanism coverage、formula semantic fidelity，再用 unified 路径重跑；否则继续扩大 live matrix 只会重复测试 legacy 失败链。

因此，本文件不推翻：

- `MechanismContextV1 = EvidenceClosure + PaperDetails`；
- Formalizer/Writer 共享同一 technical world；
- Architect 只负责叙事组织；
- formula 在 paragraph planning 前拥有独立技术 owner；
- Candidate 可保留作者意图，Verified 继续 fail-closed；
- detail/formula Binder 不得弱化。

本文件修订的是：**输入边界、运行接线、Research 闭环、semantic compiler、公式粒度、分页交付和验收顺序。**

---

# 1. Evidence Scope and Interpretation

## 1.1 十项目产物位置与结果

| 项目 | 产物根目录 | Candidate | Verified | 主要终态 |
|---|---|---:|---:|---|
| DyG-Mamba | `/tmp/c2p-gpu1-cutover-20260905-serial/dyg` | 5749 B | 0 B | Writer/结构门 incomplete |
| LinearRAG | `/tmp/c2p-gpu1-cutover-20260905-serial/linearrag` | 3593 B | 0 B | Writer/结构门 incomplete |
| EBCAR | `/tmp/c2p-gpu1-cutover-remaining-20260906-r2/ebcar` | 3731 B | 0 B | structural failure，随后 callback `NameError` |
| RAP | `/tmp/c2p-gpu1-cutover-remaining-20260906-r2/rap` | 5294 B | 0 B | callback `NameError` |
| Lookahead | `/tmp/c2p-gpu1-cutover-remaining-20260906-r2/lookahead` | 3630 B | 0 B | callback `NameError` |
| UniMMAD | `/tmp/c2p-gpu1-cutover-remaining-20260906-r2/unimmad` | 4921 B | 0 B | callback `NameError` |
| CodeQuant | `/tmp/c2p-gpu1-cutover-remaining-20260906-r2/codequant` | 4016 B | 0 B | callback `NameError` |
| Domain-Pruning | `/tmp/c2p-gpu1-cutover-remaining-20260906-r2/domain_pruning` | 4319 B | 0 B | callback `NameError` |
| FastGS | `/tmp/c2p-gpu1-cutover-remaining-20260906-r2/fastgs` | 2857 B | 0 B | callback `NameError` |
| LearNAT | `/tmp/c2p-gpu1-cutover-remaining-20260906-r2/learnat` | 无 | 无 | Research blocked；Writer 缺五个 legacy 必需输入 |

关键证据位于每个目录的：

- `artifacts/research_product/run_summary.json`：产品终态、研究终止原因和产物索引；
- `artifacts/research_product/research_trace.json`：每轮搜索、阅读、建图、编译和停止原因；
- `artifacts/implementation_scope_v1.json`：target/comparand/config/evaluation/unknown 分类；
- `artifacts/candidate_acquisition_ledger_v1.json`：候选发现、读取、接受或拒绝；
- `artifacts/behavior_graph_v1.json`：operation/relation 图；
- `artifacts/method_argument_facets_v1.json`、`facet_evidence_alignments_v1.json`、`method_argument_briefs_v1.json`：作者意图到证据许可；
- `artifacts/evidence_packets_v3.json`、`code_facts_v1.json`、`atomic_claims_v3.json`、`equation_claims_v1.json`：Research 提升后的技术信息；
- `artifacts/06_authoring/publication_writer_result_v1.json`、`publication_candidate_method.md`：Writer 输入、段落结果和 Candidate；
- `artifacts/07_validation/publication_quality_report_v1.json`：Binder/validator 和 publication gate；
- 批次日志：`/tmp/c2p-gpu1-cutover-remaining-20260906-r2/*.log` 与 `launcher.log`。

## 1.2 为什么这批结果不能验收 unified 实现

当前生产事实是：

```text
run_authoring_replay.py ─┐
                         ├─ run_publication_method_writer(..., no mode)
autonomous_method_agent ─┘
                                  ↓
                         effective_mode = legacy
```

具体缺口：

- `src/code2paper/agentic/publication_method_writer.py` 接受 `authoring_context_mode`，但默认值为 `legacy`；
- `scripts/run_authoring_replay.py` 的 production 调用没有传该参数；
- `src/code2paper/agentic/autonomous_method_agent.py::_run_writer_surface()` 没有传该参数；
- `src/code2paper/agentic/writing_callback_fulfillment.py` 的 resume 调用也没有恢复该参数；
- 当前 profile/launcher 没有 `CODE2PAPER_AUTHORING_CONTEXT_MODE=unified`；
- 十个输出目录没有 `mechanism_context_set_v1`、`mechanism_evidence_closures_v1`、`narrative_plan_v3`、mechanism formula、unified payload trace 或 information funnel；
- 新增测试只直接调用 `run_publication_method_writer(..., authoring_context_mode="unified")`，没有覆盖 replay CLI、产品 runner、callback resume 和真实 artifact manifest。

所以这批运行能证明：

- legacy/current product 路径的 Research、Writer、callback 与质量门现状；
- 十个代码库暴露的 scope、ownership、promotion 和 completeness 问题；
- live runtime 中存在确定性异常。

它不能证明：

- unified compiler 在真实项目上是否生成了 lossless closure；
- Formalizer/Writer byte identity gate 是否在真实调用中执行；
- Narrative V3、mechanism-owned formula、detail Binder 是否改善了正文；
- v2 的 token/call 成本是否可接受。

## 1.3 当前 byte-identity 修复的正确定位

`87e868d` 已经在 production helper 中比较：

- Formalizer 实际 `shared_payload` bytes；
- Writer 实际 `shared_contexts` bytes；
- bytes digest、shared payload digest、source context digest、view digest 和 slice digests。

这项实现应保留，并作为 P1 cutover gate。问题不是 gate 本身仍然缺失，而是：

1. 十项目没有进入会执行该 gate 的模式；
2. callback resume 没有持久化 mode；
3. runner 没有声明预期 unified 产物；
4. 当前 payload budgeting 只标记压力，没有形成可验证的分页消费合同。

---

# 2. 作者意图到底落实了多少

“落实”必须拆成四个口径，否则会把结构采集误报为实现完成。

| 口径 | 当前证据 | 结论 |
|---|---|---|
| Intent capture | 九个项目产生 facets/briefs；LearNAT 在 Research 前后链路未形成可写输入 | 结构采集约 9/10 |
| Intent-to-code grounding | 213 alignments：0 entailed、29 partial、184 unresolved | 完整对齐 0%；部分对齐 13.6%；未对齐 86.4% |
| Publication licensing | 211 briefs 中 14 个可进入 Verified，197 个需 caveat | 安全可发布单位仅 6.6%，且不等价于整篇覆盖率 |
| Final realization | 九个 Candidate、零个非空 Verified；LearNAT 无 Candidate | Verified 层落实为 0/10 |

因此，最准确的表述是：

> 作者意图大多已经被系统“看见并结构化”，但没有被完整地定位到目标代码、编译成可消费的机制/公式证据，也没有通过最终绑定。Candidate 对若干高层概念进行了转述，但经常是 caveated、泛化、错位或被错误实现替代；Verified 没有形成任何可交付正文。

这不是作者意图本身不足。十项目中存在三类不同情况：

1. **代码中明确存在，但系统未提升。** 例如 LearNAT 的 MCTS/AST、FastGS 的 `densify_and_prune_fastgs`。
2. **代码存在部分实现，论文还描述训练目标、理论或实验语义。** 例如 RAP 的推理特征与归一化可验证，但训练损失在当前仓库未找到。
3. **作者意图与当前代码或默认路径不一致。** 这类内容只能标为 `author_spec_only`、`repo_mismatch` 或 `inactive_alternative`，不能由 Candidate 的自然语言掩盖。

后续质量报告必须同时报告：

```text
intent_capture_rate
intent_grounded_exact_rate
intent_grounded_partial_rate
intent_author_spec_only_rate
intent_repo_mismatch_rate
intent_rendered_with_correct_authority_rate
verified_realization_rate
```

不得再用单个 “coverage” 混合上述状态。

---

# 3. 信息为什么没有提取到：端到端根因

## 3.1 R-Execute：模式和运行合同没有接到真实入口

这是本轮最上游、最确定的原因。

- unified 只存在于函数内部 opt-in 参数；真实 CLI/runner 没有显式选择；
- 运行记录没有持久化 `requested_mode`、`effective_mode`、`mode_source` 和 expected artifact set；
- 即使调用者以为在跑 cutover，系统也可以静默落回 legacy；
- callback resume 不继承初始 mode，可能在同一个 run 中跨技术路径；
- `run_publication_method_writer()` 在解析 mode 前就执行 legacy required-input preflight。LearNAT 缺少 legacy `method_section_plan_v2` 时直接 blocked，unified compiler 没有机会根据现有 Research/intent artifact 构建新计划；
- `autonomous_method_agent._writer_artifact_paths()` 没有传递 `method_argument_briefs_v1`、story spine、repo snapshot 和 symbol index。即使强制 unified，compiler 仍会缺少重要 author-intent 与 repository resolution 输入。

这说明 v2 缺少一个早于 WP-2 的 **Run Contract Gate**。

## 3.2 R-Scope：代码库边界与 ownership 分类错误

信息提取不是在“全仓库里找到了就算成功”。系统先决定哪些文件/符号属于目标方法，这一步在复杂仓库上不稳。

典型证据：

- Domain-Pruning 的 `implementation_scope_v1` 出现约 2101 个 `target_core`、557 个 evaluation、770 个 configuration、3870 个 unknown。vendored `sglang`、数据和非目标文件进入候选空间，目标 `pruning/` 反而出现 path-scope 冲突；
- FastGS 的 `scene/gaussian_model.py::GaussianModel.densify_and_prune_fastgs` 是名称和代码都高度匹配的目标方法，却被分类为 `comparand`，随后以 `ownership_role_not_target_method` 拒绝；
- repo snapshot 当前排除了 `.git`、cache 等通用目录，但没有稳定地区分 first-party executable、vendor/submodule、generated、dataset、paper draft、test 和 configuration；
- README、paper draft 或 demo 文本可能帮助检索，却不能自动升级为 executable hard authority。

所以“没有事实”可能实际表示：

```text
目标代码存在
  ↓
source inventory 不干净 / ownership 错判
  ↓
候选被拒绝或搜索预算被 vendor 噪声消耗
  ↓
packet/fact 为空
```

## 3.3 R-Promotion：已观察信息没有变成证据

v2 的 R0 “discovery miss” 粒度不够。LearNAT 证明至少要区分：

```text
R0a not searched
R0b discovered but not read
R0c read/observed but not promoted
R0d promotion attempted but rejected
```

LearNAT trace 已搜索并阅读 `MCTS.py`、`_classify_node`、AST pruning、DPO 数据与训练逻辑；candidate acquisition ledger 也记录了多个 discovered/read symbol。但最终：

- evidence packet = 0；
- fact = 0；
- claim = 0；
- ownership role 仍为 unknown；
- behavior graph/packet/fact 编译没有完成；
- symbol-search budget 耗尽后停止。

这不是模型没有发现，而是 **observation-to-evidence promotion recall 为 0**。

Research loop 当前还存在调度问题：

- 预算按全局 turn/tool 消耗，未为每个核心 novelty obligation 保留最低预算；
- FastGS 后续大量时间转向通用 SfM initialization，没有回到 VCD/VCP 目标函数；
- RAP 找到 15D 特征与 percentile normalization 后，为寻找训练 loss 耗尽搜索预算；
- 某些 trace 出现重复 `COMPILE_EVIDENCE` 而没有新 source span、operation、fact 或 coverage delta；
- `stop_blocked`、`max_turns` 与 policy fallback 可以结束运行，但没有保证每个 core author-intent clause 都获得一次目标代码尝试与 terminal disposition。

## 3.4 R-Graph：图规模大不等于机制链完整

九个可建图项目的 behavior graph 规模从数百到上千节点，但 relation 数量相对稀疏。例如 DyG 约 1002 nodes/39 relations，EBCAR 1312/92，UniMMAD 520/21。`unresolved_relation_count=0` 也不能证明：

- 已找到目标入口；
- 已形成 input → transform → branch/config → output 的连通主链；
- 调用、数据和控制边都达到 paper mechanism 所需粒度；
- core operation 没有落在 disconnected component；
- 当前默认配置确实到达该路径。

现有 graph gate 更接近“已终止分类”，不是“机制信息完整”。

## 3.5 R-Context：deterministic PaperDetail compiler 仍会重新压缩

当前 implementation 已比初版正确：materialized slice 包含 detail、operation、edge、configuration 和 exact evidence，而不只是 ID 壳。但上游 context compiler 仍有语义风险：

- `_operation_clusters()` 会因 same span、shared relation、shared fact、文本 producer-consumer 或相同 guard 合并 operation。共同 guard/同一长 span 可能把多个科学步骤过度合并；反之，跨函数调用或改名后的 dataflow 可能未合并；
- `_detail_role()` 主要依赖 predicate 集合和首尾位置；
- `_detail_importance()` 把 unknown active path 降为 supporting，把 condition/config 默认降为 supporting，但条件、阈值、归一化和路由配置经常正是论文核心；
- `semantic_atom` 主要由 predicate/operand/result 拼接，不等于 reader-facing scientific semantics；
- `annotate_mechanism_paper_details()` 当前是 deterministic heuristic，没有执行 v2 所述的低温 semantic proposal + ordinal membership validation；
- operation 被标为 `explicitly_unresolved` 后可以使 closure audit 的 terminal coverage 达到 1.0，但这只证明“不再无状态”，不证明信息被提取；
- `evidence_authority` 只有 verified/partial/unresolved，未表达 executable、configuration、test、docs、generated、vendor 等 source kind。

因此 v2 所说的 lossless closure 需要再增加一个独立指标：

```text
terminal_classification_coverage == 1.0
```

不等于：

```text
mechanism_information_completeness == 1.0
```

## 3.6 R-Formula：一个 mechanism 一个“大公式义务”会丢数学结构

当前 `compile_mechanism_formula_obligations()` 最多为一个 mechanism 生成一个聚合 obligation，目标类似：

```text
Formalize A and B and C operations.
```

这会把多个本来独立的公式、分支、归一化、分母、reduction 和符号约束压成一个自由生成任务。典型后果：

- EBCAR 的 InfoNCE 正样本没有完整进入 denominator；
- DyG 的连续时间、SSM 参数化、交互和 gated top-k 无法靠一个 obligation 精确恢复；
- Lookahead 的有序候选/验证语义可能被写成 set union，数学上看似简洁但改变执行语义；
- RAP 的 7+8 维特征、percentile normalization 和训练目标需要不同 authority；
- author formula expectation/notation 没有稳定从 facet/story spine 进入 `MechanismContext.notation_hints`。

Formula compiler 必须以 `EquationClaim` 和 formalizable detail 为单位，不得以整 mechanism 聚合成单个 mega-obligation。

## 3.7 R-Delivery：共享 payload 已 materialize，但预算合同仍不完整

当前 projection 的优点应保留：

- slice 内有实际 technical payload；
- exact evidence 不因 nominal slice 数而静默丢失；
- actual Formalizer/Writer bytes 会 fail-closed 比较。

仍需修改：

- `MAX_EXACT_EXCERPT_TOKENS_PER_SLICE=12000` 没有形成真正 token packing；exact evidence 仍按每 10 条分块；
- `MAX_MECHANISM_SLICES=4` 只设置 `budget_exhausted`，并不限制序列化后的总 payload；
- 所有 slices 一次序列化为共享 payload，长机制可能超过模型请求预算；
- 没有 page-level delivery receipt 证明两个 consumer 都读取了全部页；
- 如果未来 section writer、prompt sanitizer 或 serializer 改写其中一页，只比较 context object 仍不够。

正确方向不是恢复 role-specific deletion，而是：**同一 immutable context manifest、同一 deterministic pages、同一页序列 bytes；Formalizer 与 Writer 分页消费并分别确认。**

## 3.8 R-Render/Runtime：Writer 不是唯一问题，但最终交付也未闭合

本轮可见的最后一层问题包括：

- 九个 Candidate 均未形成非空 Verified；
- quality report 的 completeness/formula 指标多数为 0；
- support precision 为 1 的 LinearRAG/CodeQuant 主要反映安全 abstention，不代表方法完整；
- Candidate 仍可能用泛化语言替代缺失机制，或把 author intent 写成 repository implementation；
- 存在 LaTeX/control-character 损伤，说明 representation-only sanitation 需要在正文提交前独立执行；
- 七个项目在 callback `_write_artifact()` 处因 `_digest_json` 未定义崩溃；
- 现有 unit tests 没有执行真实 runner + open callback + artifact write + resume 的纵向路径。

---

# 4. 十项目原文—代码—产物对照

下表中的原论文只用于判断“论文 Method 应当解释哪些科学单元”；最终实现真值仍由对应仓库代码决定。

| 项目 | 原文/代码中可恢复的关键内容 | 本轮为何未进入正文或被写坏 | 当前 Candidate 判断 |
|---|---|---|---|
| DyG-Mamba | first-hop 严格时间过滤、排序/补齐；node/edge/time/co-occurrence 表征；cosine time；alignment；`A=-exp(A_log)` 等 SSM；source/destination interaction；cross-linear attention；gated top-k；任务头 | Research 有较多 facts/claims，但 legacy section/packet 和公式路由未保留完整连续机制；核心公式与执行条件未逐义务闭合 | 有框架，缺连续链、精确公式和约束；部分 router/top-k 位置错位 |
| LinearRAG | Stage 1 entity activation → entity-sentence/query similarity → sentence-entity/MAX → threshold/frontier；Stage 2 hybrid passage initialization + PPR | stage/mechanism ownership 混合，Stage 1 与 Stage 2 的信息在 legacy planning 中污染 | 把 Stage 1 近似写成 PPR，阶段边界错误 |
| EBCAR | document/position ID；full + same-document mask；fixed query；精确 InfoNCE 分母 | 代码事实相对充分，但 formula obligation/consumer 与 paragraph binding 丢失；结构门失败后 callback 又崩溃 | 高层叙述尚可，InfoNCE denominator 不完整，公式 fidelity 不合格 |
| RAP | 15D 输入由 7+8 特征组成；percentile normalization；推理/剪枝链 | 训练 objective 在当前仓库未定位；后续搜索耗尽预算；不同 authority 被混在同一段 | 高层概念在，但维度、loss 和实现边界不完整，且有字符损伤 |
| Lookahead | generation config、`max_tokens=100`、`run_problem` 分支、候选/验证流程 | facts 覆盖配置和局部分支，未形成完整 verifier 与有序输出链；max-turn/incomplete | 仅有 skeleton；把有序语义写成集合；理论/异步机制缺失 |
| UniMMAD | 多模态/多域模型、MiMoE 拼接和返回、训练 loss；原文还需 FCM、routing、load balance、anomaly aggregation | 仅少量训练/forward facts 被提升，其余 facets 全 unresolved | 广泛复述作者意图，但多数为 unsupported 或泛化 loss |
| CodeQuant | rotation hooks、cluster/centroid 更新、MoE inference；原文还需 Cayley、POG、output-aware ACCF、LUT/hardware | Research 抽到外围和部分 clustering，未完成四阶段连接及公式细节 | 只有四阶段 outline，核心数学和硬件落地缺失 |
| Domain-Pruning | `pruning/` 中 mixed-domain score normalization、top-k，以及应继续定位的 expert contribution/token cosine | vendored `sglang` 与数据污染 scope；路径/ownership 判断异常；预算耗在非目标 MoE 符号 | 只写归一化与 top-k，output-aware score 仍开放，并混淆 top-K/top-M |
| FastGS | `scene/gaussian_model.py` 中目标 densification/VCD/VCP 链 | 精确目标函数被分类为 comparand 并拒绝；Research 转向通用 SfM；只留下旧 gradient densification fact | 用旧梯度 densification 替代论文 view-consistent densification，属于实质性错写 |
| LearNAT | `MCTS.py` 的搜索/AST 分类与剪枝；`data_generation.py`；`trainers.py` 的 DPO/margin 路径 | 代码已经被搜索和阅读，但 ownership 未决，observation 未提升；8 turns 后 stop_blocked；legacy preflight 再次阻断 Writer | 无 Candidate；这是最典型的 discovered-but-not-promoted |

## 4.1 质量结论

当前九篇 Candidate 的问题不是单纯“写得短”，而是三种质量损失叠加：

1. **Recall loss**：核心机制、条件、默认路径、公式没有进入可消费事实；
2. **Routing/authority loss**：不同 stage、comparand、author-spec、repository-verified 内容混合；
3. **Realization loss**：即使 facts 存在，也没有被 formula package、paragraph contract 和 Binder 完整兑现。

冻结 `publication_quality_report_v1.json` 的主要结果如下。`support precision=1` 但
`completeness=0` 表示系统安全地少写/拒写，并不表示 Method 质量高。

| 项目 | Candidate unsupported positives | Reported support precision | Completeness | Coherence |
|---|---:|---:|---:|---:|
| DyG-Mamba | 3 | 0 | 0.047619 | 0.20 |
| LinearRAG | 0 | 1 | 0 | 0 |
| EBCAR | 7 | 0 | 0 | 0.60 |
| RAP | 3 | 0 | 0 | 0.20 |
| Lookahead | 13 | 0 | 0 | 0.75 |
| UniMMAD | 7 | 0 | 0 | 0.666667 |
| CodeQuant | 0 | 1 | 0 | 0 |
| Domain-Pruning | 6 | 0 | 0 | 0.625 |
| FastGS | 10 | 0 | 0 | 0.80 |

FastGS 的较高 coherence 仍然不能抵消它把旧 gradient densification 当成论文核心 VCD 的
事实错误；Lookahead/Domain 的局部连贯也不能抵消核心机制和公式缺失。当前所有项目的
publication gate 仍为 false。

因此不能通过以下方式提升质量：

- 单纯增加 Writer token；
- 放松 Verified gate；
- 从原论文复制 Method；
- 对缺失 claim 加固定模板；
- 对 callback 失败做静默过滤；
- 仅扩大 live 项目数。

真正的提升顺序必须是：

```text
正确运行模式
  → 干净 source inventory
  → core-intent 驱动的 Research
  → observation 强制 promotion/typed rejection
  → connected mechanism closure
  → semantic details + per-formula obligations
  → identical paged delivery
  → mechanism realization draft
  → section composition
  → detail/formula Binder
```

---

# 5. 对 v2 设计必须做的修改

## 5.1 保留的架构决策

以下 v2 设计不应回退：

- I1：一个 canonical technical IR，内部保留 EvidenceClosure 与 PaperDetails；
- I3：bounded source operation 必须 terminal classification；
- I5：Architect 不创造技术事实；
- I8：Formalizer/Writer 共享 technical payload，并比较 actual bytes；
- I9：claim kind、evidence authority、publication policy 三轴分离；
- I10：detail 内继续保留 atomic witness；
- I12：Candidate persistence + Verified fail-closed；
- I13：信息保留之后再做输出验证；
- mechanism-owned formula、Detail Binder、semantic-delta callback 和 staged cleanup。

## 5.2 在 WP-2 之前新增 Pre-WP0：Run Contract and Vertical Smoke

v2 从 evidence baseline 直接进入 models/compiler，缺少“真实入口是否执行新路径”的门。

新增 `AuthoringRunContractV1`，至少持久化：

```text
requested_authoring_context_mode
effective_authoring_context_mode
mode_source                  # cli / API / profile / default
code_commit_sha
repo_snapshot_id
project_tree_hash
expected_artifact_keys
actual_artifact_keys
initial_mode_digest
resume_mode_digest
```

硬门：

- cutover/replay 命令若声明 `unified`，effective mode 不得是 legacy；
- `unified` 成功或 incomplete 都必须产生 context/closure/narrative/payload trace；
- callback resume 的 mode 与 initial mode 不一致时立即 blocked；
- 禁止在没有 provenance 的情况下依赖隐藏环境变量；
- unit test 必须经过 CLI/runner，而不只直接调用内部函数。

## 5.3 修改 v2 §7：在 MechanismSeed 前新增 Source Inventory Contract

新增 `RepositorySourceManifestV1`，对 snapshot 中每个 root/file 记录：

```text
source_kind:
  first_party_executable
  configuration
  test
  documentation
  generated
  vendor
  submodule
  dataset_or_checkpoint
  paper_or_draft

ownership_role:
  target_core
  target_support
  comparand
  evaluation
  unknown
```

规则：

- first-party executable 才能直接形成 implementation fact；
- config/test 可作为限定或行为 witness，但需保留 source kind；
- docs/paper draft 只可帮助 retrieval 和 author-intent alignment；
- vendor/generated/data 默认不参与目标 mechanism discovery；
- path scope 必须对 snapshot 的规范化目录做存在性检查；
- target_core 数量异常、unknown 爆炸、目标命名符号被标 comparand 时触发 scope-repair，不允许继续消耗主 Research 预算；
- repo snapshot、symbol index、source manifest 必须进入 unified loader，不得只存在于 Research runtime 内存。

## 5.4 扩展 v2 I14 的 loss taxonomy

原 R0–R4 不足以定位 LearNAT/FastGS 这类故障。修改为：

| 层 | 含义 |
|---|---|
| R0a | obligation 从未触发搜索 |
| R0b | 候选已发现但未读取 |
| R0c | 已读取/观察但未建图或未编译 evidence |
| R0d | promotion 已尝试但被 typed rejection |
| R1a | source ownership/scope 错分 |
| R1b | stage/mechanism routing 错分 |
| R2a | operation closure 缺边或 active path 未解析 |
| R2b | operation → PaperDetail 聚类/语义压缩丢失 |
| R2c | formula obligation 编译丢失 |
| R3a | payload 未交付、未分页确认或被 sanitizer 改写 |
| R3b | Narrative/Writer 未兑现已交付 detail/formula |
| R4 | rendering/LaTeX/control-character 损伤 |
| R5 | Binder/validator 拒绝、callback/runtime 中断 |

`MethodContentTraceV2` 必须能把每个 intent clause、source observation、operation、detail、formula、paragraph 和 validation result 映射到上述唯一首损失层。

## 5.5 修改 v2 §7.2–§7.11：Research/closure 必须 intent-coverage driven

每个 core author-intent clause 建立 `IntentImplementationLedger`，状态限定为：

```text
implemented_exact
implemented_partial
author_spec_only
repo_mismatch
inactive_alternative
not_found_after_bounded_search
out_of_scope
```

每个 core clause 的 Research 最低合同：

1. 至少一个 query/seed；
2. 至少一个 first-party candidate 或 typed not-found；
3. 读到 candidate 后必须尝试 graph → packet → fact promotion；
4. 未提升必须记录具体 rejection code；
5. 全局预算必须为尚未触达的 core clauses 保留预算；
6. 连续 `COMPILE_EVIDENCE` 若没有新 span/operation/fact/coverage delta，不计为进展并触发 replan；
7. 泛化 initialization/evaluation 搜索不得抢占未完成 novelty mechanism 的预算。

新增指标：

```text
core_intent_attempt_coverage
first_party_candidate_read_rate
observation_promotion_rate
typed_rejection_coverage
novelty_mechanism_budget_share
no_progress_compile_count
```

## 5.6 修改 v2 I2/I3/I4：增加 Mechanism Coverage Contract

一个 operation 全部被 terminal classification，不能代表 mechanism 已完整。每个核心 mechanism 还必须具有：

- 稳定 semantic mechanism key；
- author-intent owner 与 stage owner；
- first-party entrypoint 或 typed absence；
- 至少一条连接的 input → transform → output 路径；
- algorithm-defining condition/config/default branch；
- disconnected core component 列表；
- active-path confidence 与决定它的 config/source witness；
- paper-facing completeness disposition。

`MechanismSeedV1` 不应只从 story node ID/cluster ID 生成 identity。identity 应由：

```text
semantic mechanism key
+ stage owner
+ resolved entrypoint cluster
+ repository snapshot identity
```

共同决定，并允许多个 author facets 指向同一 mechanism、一个 facet 指向多个 stage-specific mechanisms。

## 5.7 修改 v2 §7.7–§7.9：PaperDetail annotation 不能只靠 predicate heuristic

采用两步闭环：

1. 低温 semantic annotator 仅提出 operation ordinal membership、scientific role、semantic atom、importance 和 rationale；
2. deterministic validator 校验所有 ordinal、source operation membership、active-path、authority 和 atomic witness。

必须新增：

- cluster cohesion score 与 merge reasons；
- split audit：跨函数 call/dataflow 是否被错误拆分；
- merge audit：shared guard/same span 是否把独立步骤错误合并；
- condition/config core promotion：只要它改变公式、路由、归一化或输出，即可为 core；
- semantic atom 必须描述科学作用，不能只是 `CALL x`、`NORMALIZE y`；
- unknown active path 不可直接视为 supporting；若关系到 core mechanism，必须回调 Research 或标 core unresolved。

## 5.8 修改 v2 §9：Formula Obligation 从 per-mechanism 改为 per-equation/per-relation

优先级：

```text
exact EquationClaim / source expression
  > formalizable detail with explicit operands/result
  > author-intent mathematical expectation（author-spec only）
```

每个 obligation 必须固定：

- source equation/expression identity；
- operands、operator tree、result；
- denominator membership；
- reduction axis/order；
- normalization domain；
- branch/threshold/default conditions；
- symbol map 与 units/shapes；
- allowed equivalence transformations；
- authority/policy。

禁止：

- 把多个独立公式合成一个 mega-obligation；
- Formalizer 自由补充未绑定 operand；
- 用通用数学表达替代有序执行语义；
- formula package 只验证 claim ID，不验证 operand/operator/denominator。

## 5.9 修改 v2 §6.4：共享上下文采用 immutable manifest + identical pages

目标交付合同：

```text
MechanismContext
  ↓
consumer-neutral deterministic page packer
  ↓
SharedPayloadManifest
  ├── page_0 bytes + digest
  ├── page_1 bytes + digest
  └── ...
       ↙             ↘
Formalizer receipts  Writer receipts
```

规则：

- technical page bytes 对两个 consumer 完全一致；
- role/task instruction 不属于 shared payload，可各自不同；
- page packing 使用实际 tokenizer 或可审计保守 token estimator；
- 所有 core details 与其 witnesses 同页或显式跨页引用；
- evidence 不静默截断；超预算时分多次调用，不把全部 pages 塞进一次请求；
- 两个 consumer 都必须对全部 required pages 产生 delivery receipt；
- final identity gate 比较每页 bytes、页序列 digest、source/view digest 和 slice/page digests；
- 任一 sanitizer/serializer 改变 technical bytes 均 fail-closed。

## 5.10 修改 v2 §10：Writer 改为 mechanism realization + section composition

为避免长 context 混写，Writer V3 分两步：

1. **Mechanism Realizer**：逐 mechanism/page 生成可绑定的小段，必须兑现 required details/formulas；
2. **Section Composer**：只组织已验证的 mechanism drafts、transition 和章节连贯性，不重新发明技术内容。

正文 authority 规则：

- repository-verified implementation 可以陈述为实际行为；
- implemented-partial 必须带限定；
- author-spec-only 可以进入 Candidate，但必须明确是设计目标/作者说明，不能写成已验证代码事实；
- repo-mismatch 必须进入 review/callback，不能由 Writer 选择更好听的一侧；
- formula package 通过 placeholder/ID 精确插入，Writer 不得重写数学结构；
- representation sanitizer 只能修复 Unicode/control/LaTeX 外壳，不改变内容；修复前后必须保存 digest 和 diff class。

## 5.11 修改 v2 §13：Callback 同时继承 mode 和 context identity

callback receipt 除 semantic delta 外必须包含：

```text
initial_run_mode
resume_run_mode
baseline_source_context_digest
current_source_context_digest
new_observation_ids
new_operation_ids
new_fact_ids
new_detail_ids
remaining_core_intent_ids
```

resume 前硬门：

- `_digest_json` 或统一 digest helper 必须来自单一已测试实现；
- semantic delta 为空不得标 fulfilled；
- mode/context/page manifest 不一致不得 resume；
- resume 只重编译受影响 mechanism、formula 和 paragraph，但 final section composition/Binder 必须重新验证；
- callback vertical smoke 必须实际执行 `_write_artifact()`，不能只 mock router 返回值。

---

# 6. 优化后的逐步执行计划

该顺序替换 v2 “models/compiler 已完成后直接 live cutover”的执行假设。每个阶段单独提交、单独验收；前一阶段未通过不得启动昂贵 live run。

## P0 — 修复 production runtime 与 mode wiring

**目标**：真实入口可明确、稳定地执行 unified；先消除确定性崩溃。

修改范围：

- `src/code2paper/agentic/writing_callback_fulfillment.py`
  - 使用统一 canonical digest helper，修复 `_digest_json` 未定义；
  - resume 显式继承 authoring context mode；
- `src/code2paper/agentic/publication_method_writer.py`
  - 在 legacy preflight 前解析 effective mode；
  - 为 legacy/unified 定义不同 required artifact contract；
  - 写 `AuthoringRunContractV1` 和 expected/actual artifact gate；
- `src/code2paper/agentic/autonomous_method_agent.py`
  - 产品 API/CLI 显式接收 mode；
  - `_writer_artifact_paths()` 传递 briefs、story spine、repo snapshot、symbol index/source manifest；
  - `run_summary.json` 持久化 mode provenance；
- `scripts/run_authoring_replay.py`
  - 新增 `--authoring-context-mode {legacy,shadow_unified,unified}`；
  - execution record 写 requested/effective mode 和 commit SHA；
- live profile
  - profile 可声明 mode，但 CLI 明确值优先且必须记录来源。

退出条件：

- callback open → research → `_write_artifact` → fulfill → resume 纵向测试通过；
- replay CLI 测试证明传入 unified；
- product runner 测试证明传入 unified；
- unified 缺 expected artifact 时 blocked，不允许静默成功；
- `python -m compileall`、相关 pytest、静态未定义名检查和 `git diff --check` 全部通过。

## P1 — 用现有十项目冻结产物做 offline unified reconstruction

**目标**：不调用 GPU，先证明真实 artifact manifest 能构建新链。

步骤：

1. 对九个有 research artifacts 的项目执行 unified compiler offline replay；
2. 使用 deterministic/mock Formalizer/Writer 只验证数据合同；
3. 生成 closure、context、formula obligations、Narrative V3、shared page manifest、trace；
4. 为 LearNAT 单独验证：mode-specific preflight 不再被 legacy plan 阻断，同时保持 evidence 为空时 fail-closed；
5. 汇总每个项目的 input-present/missing、operation closure、detail、formula 和 page metrics。

退出条件：

- 9/9 可用 research artifact 项目生成完整 unified diagnostic artifact set；
- LearNAT 返回 typed `research_evidence_missing`，而不是 legacy input missing；
- 100% actual Formalizer/Writer page bytes identity；
- 没有 runtime exception；
- offline 结果绑定 `87e868d` 或后续明确 SHA。

## P2 — Source inventory 与 scope repair

**目标**：先让 Research 在正确代码空间工作。

关键 fixture：Domain-Pruning、FastGS、LearNAT。

退出条件：

- Domain-Pruning vendored `sglang`、dataset/generated 文件不再进入 target core；
- `pruning/` path scope 与 snapshot 一致；
- FastGS 目标 densification 函数不再以 comparand 拒绝；
- LearNAT 的 MCTS/AST/DPO first-party symbols 获得明确 ownership；
- source-kind authority 在 packet/fact/context 中保持；
- scope cardinality anomaly 会 fail-closed 或触发 repair。

## P3 — Core-intent scheduler 与 observation promotion

**目标**：解决“读到了但没有 facts”。

关键 fixture：LearNAT discovered-but-not-promoted；FastGS wrong ownership；RAP partial repository implementation。

退出条件：

- 每个 core intent 100% 有 attempt + terminal disposition；
- 每个已读取 first-party target candidate 100% 被提升或有 typed rejection；
- 重复无 semantic delta 的 compile 不消耗有效进展轮次；
- 未触达 novelty obligation 有预算保留；
- LearNAT 能从已读代码形成 operation/packet/fact；
- RAP 的 training objective 若仓库确实缺失，被标 `author_spec_only/not_found`，不伪造实现。

## P4 — Mechanism closure、active path 与 PaperDetail semantic compiler

**目标**：避免新的 IR compression bottleneck。

关键 fixture：DyG 连续机制链、LinearRAG 两阶段隔离、FastGS densification、Domain mixed-domain pruning。

退出条件：

- operation terminal coverage = 1.0；
- 与其分开报告 mechanism information completeness；
- 所有 core mechanism 有 connected input→output path 或 typed unresolved；
- active/default/inactive 有 config/source witness；
- stage contamination = 0；
- core condition/config 不被固定降级；
- deterministic validator 能拒绝 semantic annotator 的 invalid ordinal、过度合并和 source-less atom。

## P5 — Per-equation formula compiler 与 fidelity validator

**目标**：让数学结构来自源码/EquationClaim，不由段落或通用 prompt 猜测。

关键 fixture：EBCAR denominator、DyG SSM/时间编码、RAP 7+8/归一化、Lookahead ordered semantics、CodeQuant rotation/clustering。

退出条件：

- 每个 repo-verifiable equation/formal relation 独立 obligation；
- operand/operator/denominator/reduction/condition 全部可验证；
- formula N/A 有 typed reason；
- exact source expression 优先；
- Formula package 经 Writer 插入后结构等价；
- 无 mega-obligation。

## P6 — Identical paged delivery、Mechanism Realizer 与 Binder

**目标**：同一 technical world 在预算内被两个 consumer 实际消费，并在正文逐 atom 兑现。

退出条件：

- page packing 受 token budget 约束且不丢 core/evidence；
- Formalizer/Writer 对每页 actual bytes 相同；
- required page receipt coverage = 1.0；
- 每个 mechanism draft 的 required detail/formula coverage = 1.0 或 typed callback；
- section composer 不新增未授权 positive；
- Binder 验证 detail atom、edge、formula，而不是只看粗 detail ID；
- control character = 0，LaTeX parse/render gate 通过。

## P7 — Callback V2 增量重编译

**目标**：缺失信息回到正确 owner，并只重做受影响链路。

退出条件：

- semantic delta、context digest、page manifest、mode 全部一致；
- no-progress callback 不得 fulfilled；
- operation/fact 新增后 closure/detail/formula/paragraph 依赖正确失效；
- callback 后 actual byte identity 与 Binder 全量重验；
- 七项目共同触发的旧 runtime path 有真实回归测试。

## P8 — 三项目 pilot，再执行十项目 live matrix

**Pilot 顺序**：EBCAR → LinearRAG → DyG-Mamba。

理由：EBCAR 可先验证公式 denominator 与 Binder；LinearRAG 验证 stage 隔离；DyG 验证长机制、多公式和 context paging。

Pilot 通过后才串行重跑其余七个项目。每个项目使用新输出目录，记录：

- `/health`、`/v1/models`、model identity；
- commit SHA、repo snapshot、profile digest；
- requested/effective mode；
- token/call/callback/latency；
- context/closure/formula/page/trace digests；
- Candidate、Verified、quality report；
- first loss layer 与 terminal reason。

十项目退出条件：

- 10/10 effective mode = unified；
- 10/10 expected unified artifact set 完整；
- 0 runtime exception；
- 0 silent fallback；
- 100% core intent 有 terminal disposition；
- 100% read first-party target observation 被提升或 typed rejected；
- 100% required shared pages byte-identical；
- 0 stage/ownership contamination accepted into Verified；
- Verified 中 unsupported positive = 0；
- 存在 repository-verified core detail 的项目必须产生非空 Verified；
- Candidate 中 author-spec/repo-mismatch 有明确措辞和 review binding；
- 原文诊断 rubric 相比本轮在 mechanism recall、formula fidelity、narrative coherence 上不退化；
- token/call 指标通过预先冻结的 Pareto gate。

## P9 — Holdout 与 cutover 决策

三项目和十项目都不是默认切换的充分条件。必须再使用未参与 compiler/fixture 调参的 holdout repositories：

- 不允许加入项目名、路径、符号或已知答案到 generic production logic；
- 只允许 fixture 描述 expected behavior 和 diagnostic rubric；
- holdout 通过后才讨论 default mode；
- legacy cleanup 仍属于最后阶段，不能提前删除回滚路径。

---

# 7. 测试与验收矩阵

## 7.1 必须新增的纵向测试

| 测试 | 必须捕获的现有缺陷 |
|---|---|
| replay CLI → writer unified | 防止 mode 参数未传 |
| product agent → writer unified | 防止真实产品仍为 legacy |
| initial run → callback → resume | 防止 mode/context 丢失和 `_digest_json` 未定义 |
| real artifact manifest loader | 防止 briefs/story/snapshot/symbol index 未传 |
| mode-specific preflight | 防止 LearNAT 被 legacy plan 前置阻断 |
| expected artifact gate | 防止“说是 unified，产物却不存在” |
| source inventory fixture | 防止 vendor/data 污染 target scope |
| observation promotion fixture | 防止 LearNAT 已读代码仍 0 facts |
| ownership conflict fixture | 防止 FastGS 目标函数被 comparand 拒绝 |
| mechanism connectivity | 防止大图稀疏、主链缺失仍通过 |
| formula AST fidelity | 防止 EBCAR denominator/Lookahead order 改写 |
| paged actual-byte identity | 防止 sanitizer/serializer 改写 payload |
| Binder atom coverage | 防止只绑定 detail ID 就假定语义完整 |
| representation-only sanitation | 防止 control chars/LaTeX 损伤且不改语义 |

## 7.2 三类 gate 必须分开

### Correctness hard gates

- source identity/digest 一致；
- no fabricated implementation fact；
- active path/authority 明确；
- actual shared bytes identity；
- formula semantic fidelity；
- Binder/reverse validation fail-closed；
- callback semantic delta；
- no runtime exception。

### Information-recall gates

- core-intent attempt coverage；
- observation promotion；
- connected mechanism closure；
- detail/formula survival；
- terminal classification 与 information completeness 分开报告。

### Publication-utility gates

- mechanism order/section coherence；
- formula 放置与定义顺序；
- Candidate caveat 可读性；
- Verified 非空条件；
- control-character/LaTeX quality；
- 原文只作为 blind diagnostic，不成为运行 authority。

静态 suite 通过、一次 live success、或 Candidate 文件存在，均不能替代上述三类 gate。

---

# 8. 预期质量提升与可验证因果

| 改动 | 直接解决的问题 | 应观察到的指标变化 |
|---|---|---|
| mode/run contract | 十项目静默跑 legacy | unified artifacts 10/10；silent fallback 0 |
| source manifest | Domain vendor 污染、FastGS ownership 错分 | target scope 缩小；core candidate acceptance 提升 |
| intent scheduler | generic 搜索抢占 novelty | core-intent attempt 100%；untouched core 0 |
| observation promotion gate | LearNAT 已读却 0 facts | read→fact/typed rejection 100% |
| mechanism coverage contract | 大图但无主链 | connected core path 提升；disconnected core 显式化 |
| semantic detail compiler | predicate 拼接、condition 降级 | core detail recall 与 atom binding 提升 |
| per-equation obligations | denominator/order/formula 丢失 | formula AST fidelity 提升；mega-obligation 0 |
| identical pages | context 过大或被改写 | page receipt 100%；actual-byte mismatch 0 |
| mechanism realizer | section 混写和阶段污染 | detail survival、stage purity、coherence 提升 |
| callback vertical repair | 七项目确定性崩溃 | runtime exception 0；semantic-delta resume 可复现 |

如果某项改动没有产生对应指标变化，应回退并重新定位根因，不能用总体文字评分掩盖。

---

# 9. Definition of Done

本优化执行方案完成的定义不是“新增 schema 和测试类”，而是同时满足：

1. 真实 CLI、产品 runner、callback resume 都显式运行 unified；
2. source inventory 排除 vendor/generated/data 污染，并保留 source-kind authority；
3. 每个 core author intent 都被搜索、提升或 typed rejection；
4. 每个核心 mechanism 有可审计的 connected closure、active path 和 completeness disposition；
5. PaperDetails 是经过 deterministic membership 校验的 scientific annotation，不是新的 truth 或 predicate 摘要；
6. 公式按 equation/relation 独立编译并验证 operator/operand/denominator/order；
7. Formalizer 与 Writer 实际消费同一页序列的 byte-identical technical payload；
8. Writer 逐 mechanism 实现，再由 section composer 组织；
9. Binder 对 detail atoms 与 formula 做 end-to-end 绑定；
10. 十项目无 runtime exception、无 silent legacy fallback、无 Verified unsupported positive；
11. 原文诊断显示 mechanism/formula/narrative quality 明显提升，同时不放宽 repository truth；
12. holdout generalization 与 efficiency gate 通过后，才允许讨论 default cutover 和 legacy cleanup。

在这些条件满足前，当前状态应继续标记为：

> **Unified architecture implemented in code scaffolding; real product execution, information-recall closure, and publication cutover remain unverified.**

---

# Appendix A. 本轮关键数量汇总

| 项目 | facets | alignment（partial / unresolved） | facts | claims | equations | briefs | 可进 Verified briefs |
|---|---:|---:|---:|---:|---:|---:|---:|
| DyG-Mamba | 25 | 8 / 17 | 72 | 81 | 14 | 23 | 0 |
| LinearRAG | 22 | 2 / 20 | 21 | 25 | 3 | 22 | 2 |
| EBCAR | 30 | 9 / 21 | 42 | 50 | 11 | 30 | 4 |
| RAP | 23 | 1 / 22 | 12 | 12 | 3 | 23 | 0 |
| Lookahead | 21 | 2 / 19 | 26 | 26 | 3 | 21 | 3 |
| UniMMAD | 26 | 0 / 26 | 7 | 7 | 2 | 26 | 0 |
| CodeQuant | 21 | 2 / 19 | 35 | 39 | 7 | 21 | 5 |
| Domain-Pruning | 25 | 4 / 21 | 4 | 7 | 2 | 25 | 0 |
| FastGS | 20 | 1 / 19 | 1 | 1 | 0 | 20 | 0 |
| LearNAT | 未形成 | 未形成 | 0 | 0 | 0 | 未形成 | 0 |
| **合计（前九项）** | **213** | **29 / 184** | **220** | **248** | **45** | **211** | **14** |

解释：这些计数只描述本轮冻结 artifact。facts 多不代表机制完整，尤其当 facts 集中在外围配置、旧路径或单一局部时；alignment 的 aggregate status 也不能替代字段级和 active-path 验证。

# Appendix B. 与 v2 文档章节的修订映射

| v2 章节 | 本文件修订 |
|---|---|
| Executive Decision / staged cutover | 在 WP-0 前新增 run contract 与 vertical smoke |
| I2 Mechanism Identity | 加入 semantic key + stage + entrypoint + snapshot identity |
| I3 Lossless Closure | 增加 source inventory、observation promotion 和 information completeness |
| I4 Active Path | 增加 config witness、confidence、connected path gate |
| I8 Shared Context | 保留 actual-byte gate，扩展为 token-bounded identical pages + receipts |
| I14 Every Loss Observable | 从 R0–R4 扩展为 discovery/read/promotion/ownership/context/formula/delivery/render/runtime |
| §6.4 Context size control | 从“slice 标记压力”改为 deterministic token packing 与多调用消费 |
| §7 Compiler | 在 seed 前加 source manifest；semantic annotator 加 deterministic membership/merge/split audit |
| §9 Formula | 从 per-mechanism aggregate 改为 per-equation/per-formal-relation |
| §10 Writer | 增加 Mechanism Realizer → Section Composer 两步 |
| §12 Metrics | 加入 intent capture/grounding/rendering、promotion、connectivity 和 page receipt |
| §13 Callback | mode/context/page identity 随 resume 继承；真实 `_write_artifact` smoke |
| §14 Orchestrator | mode-specific preflight、完整 artifact manifest、expected artifact gate |
| §16–§19 Work packages/gates | 先 P0 wiring/P1 offline reconstruction，再 source/research/context/formula/writer/live |
