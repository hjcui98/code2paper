# Research → Method 统一下一步修复执行文档（2026-09-12）

> 当前状态（2026-09-14，S3-20 终态复核）：**S1 已跨过真实入口，S2 的累计发送账本已接线；
> 当前执行位置是 S3，尚无完整 Candidate。按 §15.6 修复，不重新从 S1 开始。**
> S3-20 的零模型预检 pass，实际使用当前图（315 nodes / 542 relations），handoff eligible。
> 最终目录已有 `execution_record.json`：116 receipts、113 次发送，exit 2；Realizer 的三个 primary
> 被总输入预算拒绝（首个 2,006,650 > 2,000,000）。此前“98 receipts、尚无 execution record”是中途状态。
> 新复核发现 Formalizer 34 main + 32 repair 均失败，有效 package 为 0；Writer 18 页最后响应为
> 5 空、3 仅标题、10 含正文文本（尚非内容验收通过）。Realizer 三个 witness 失败均经一次 repair 成功，
> 完成 15/18 页；尾逗号不再是本 run 的最终阻塞。原有 bounded repair 与身份/证据门保留。
> Writer repair 估算扣账 381,539，超过声明 reserve 200,000；总账尚未保护后续 phase 的 primary。
> 98 次有 usage 的调用已报告 input 2,179,336，另 15 次缺 usage；bytes/4 不能继续被认作已证明保守。
> 最新证据：[S3 复核结果](../.tmp/c2p-s3-review-20260914/results.json)、
> [文件摘要索引](../.tmp/c2p-s3-review-20260914/evidence-index.json)。本次复核模型调用 0，未修改生产代码。
> R10、三条 strict partial、Candidate/Verified 区分及上位设计保持；不表示 D5、切换、发布或矩阵验收通过。

## 1. 目标、权威和执行方式

本次目标是让现有 Research 产物经正确的机制条件、源码身份、公式授权和叙事绑定进入 Writer，
得到有实际正文、可编辑、可追踪的 Candidate；Verified 继续只包含经反向验证的仓库事实。
先修 Run E 暴露的直接阻塞，再迁入盲修提交中仍适用于当前代码的增量。门禁通过与正文质量分别验收。

权威顺序不变：

1. [2026-07-19 总体架构](agentic_robust_langgraph_research_writing_design_2026-07-19.md)。
2. [2026-07-31 Writer 设计](publication_ready_method_writer_design_2026-07-31.md)。
3. [Post-R8 执行计划](post_r8_research_agent_execution_plan_2026-07-31.md)。
4. [项目状态报告](project_status_and_gap_report_2026-07-31.md)，仅使用被证据支持的状态。

Method 质量仍执行 [2026-08-22 意图优先方案](method_intent_first_authoring_redesign_2026-08-22.md)。
Unified 子系统遵守 [2026-09-08 修订方案](dyg_mamba_unified_live_run_failure_diagnosis_and_remediation_2026-09-08.md)
§6.7、§9 和 §14；尤其保留三层上下文、owner-first closure、typed path、逐页调用和 durable receipt。
本文是在这些约束下的下一阶段工作包，替换当前任务的旧实施顺序，不替换上位架构或放宽门禁。

- 按编写结束时当前 [AGENTS.md](../AGENTS.md) 的 Codex Workflow：Codex 负责诊断、计划、实现、
  验证、获准的真实运行、监控、证据分析、审查与修复。本文只规划，不在本轮启动实施。
- 本文是统一执行入口；较大修改及验证记录写入 `.agent/implementation.md`，不恢复已归档的
  task/plan/review 四件套，不要求 OpenCode 或 `/implement` 交接。
- 串行工作；不 reset、clean、checkout、丢弃文件、commit、merge 或整包覆盖远端分支。
- 每片实现与审查都在同一任务中完成；方向内问题直接修复。出现必须改变合同的证据时先完成根因与影响分析，
  修订对应条款，不另起平行架构或静默降低门禁。
- 每片保存具体 diff、命令结果与冻结证据；已通过的验证只因新增改动、失败或明确疑点重复。
- 旧任务中正文质量、Candidate 耐久性和 Verified 边界仍保留；旧日期的“Active”标题不再是本次实施入口。

工作方式说明：编写过程中工作区的 AGENTS 和 `.agent` 已迁移为上述方式；本轮未恢复被移除的旧入口，
未改动该迁移。产品设计、live 准入和证据门不因协作方式变化而变化。后续如用户明确指定另一执行者，
只调整责任归属，不改变本文技术合同。

## 2. 已知基线与必须保留的成果

### 2.1 代码与远端补丁

- 本地 HEAD：`84371e4fee974071a580d7832af0ac14908c2d4b`，其上大量未提交修复属于有效基线。
- [已归档实现记录](../.agent/archive/2026-09-12/implementation.md) 最后一次全量静态记录：
  `3240 passed, 3 skipped, 7 warnings, 12 subtests`；
  compileall 和 diff check exit 0。该记录不是本文新增验证，也不是当前端到端成功。
- 盲修提交：[f58d80688a281bfdacd90b705ff44022941aad00](https://github.com/hjcui98/code2paper/commit/f58d80688a281bfdacd90b705ff44022941aad00)，
  父提交 `284eaa9547f471e5b72c1c151a7d662cf8fb9495`。本地从该父提交之后已有五个提交；两边已经分叉。
  远端声明 698 offline tests、2 skipped、无 live acceptance；不能与本地测试相加或替代集成验证。
- 输入评审：`/tmp/code2paper-blind-f58d806-review/adoption-review.md`，文件字节 SHA-256 为
  `d6fb3e17120e8f35b6485d08fd19196aa15d276c92684da44bda1bb6f680f083`。
  本文已固化采纳决策，不依赖该临时 Markdown 永久存在；远端阅读始终固定上述 commit。

### 2.2 Run E 的真实产品状态

冻结根目录：`/tmp/ebcar-live-terminal-disposition-fix-20260911-142500`。

| 层级 | 冻结结果 | 可以证明什么 |
|---|---|---|
| 进程 | exit 0 | 正常收束，不等于产品成功 |
| Research | 17 turns；`incomplete / candidate_handoff_partial` | 满足有条件 Candidate 交接，严格闭环未完成 |
| Promotion | incomplete records=0，无 digest mismatch/partial 文件 | 旧终态与摘要问题在该输入上未复现 |
| Handoff | eligible=true；3 supported＋3 qualified partial；retry ledger 存在 | Writer 可重验并接收该 Candidate 交接 |
| Unified | Formalizer admission fail | 尚未开始该 phase 的真实生成 |
| Writer | blocked；candidate_generation_status=not_started | 无正文，不是生成后丢失 Candidate |
| 输出 | 无 Candidate/Verified；publication_ready=false | 不能评价本次正文或公式质量 |

失败码为同一个 detail 的两次结构检查结果：

```text
mech_sym:f6cf5bdfe2ae16f0:core_detail_active_path_unknown:detail:mech_sym:f6cf5bdfe2ae16f0:22
unified_core_active_path_unknown
```

该次其余八项 Formalizer admission gate 通过；不代表后续 Writer、Realizer、Binder 或质量验收通过。
严格 Research admission 保留三条 partial 的终态证明缺口；不得为了该运行把 partial 改成 supported。

### 2.3 直接根因与尚未证明的部分

同一冻结源码 span `src/model/ebcar_dedicated_attention_model.py:146–149` 的两种表示如下。
这些项目路径和 ID 只允许用于证据索引与回归 fixture，不得写入通用生产分支。

| 表示 | predicate | guard | active_path_status |
|---|---|---|---|
| fact-operation | calls | self.cfg.use_dedicated_attention | conditional |
| graph-operation | CALL | 空 | active_default |
| detail 聚合 | calls → CALL | 保留条件 | unknown |

当前 `mechanism_context_compiler._operation_status()` 对 `{conditional, active_default}` 返回 unknown。
其后 detail 仍为 core，authority 被判 unresolved，于是 completeness 与 mechanism_path 都拒绝。

另一个独立证据缺口是配置 claim：`value=null`、`state=unresolved`，definition/entrypoint spans 为空。
因此不能只加一个混合状态默认值，也不能假定配置已开启。需要区分：

- 图和 fact 已证明“在什么条件下执行”，但同一操作投影不一致；
- 尚未证明被选配置/入口，所以不能声明该分支实际启用；
- 分支条件、作用域或极性本身不明，结构仍必须保持 unknown。

Run D 的 supervisor JSON parse 失败是另一个待绑定样本。Run E 走得更远不证明其已修复；
不能确定地归为随机噪声，也不能反复运行不变输入等待幸运样本。

### 2.4 不得回退的基线

1. 四类 terminal promotion disposition 经 `_replace_promotion_record` 重算，record 非空
   `model_copy(update=...)` 禁止，ledger JSON round-trip 校验。
2. worker/supervisor attempt 绑定、有效 worker 终态优先和不伪造 fallback。此项真实信号证据绑定
   Run A `/tmp/ebcar-live-digest-attempt-fix-20260910-230600`，不能混写成 Run E 的信号测试。
3. promotion 身份索引的性能修复；不能恢复逐节点重复全量身份扫描。
4. merged canonical claim lineage、handoff/retry digest 与 Writer 独立重算。
5. 未被 compile 消费的探针使用既有 not_selected disposition；不因此授权事实或完成严格 Research。
6. source/owner/path/formula/qualifier/checkpoint/final-integrity 门、Candidate 耐久性、正文词句授权。

## 3. 盲修提交的统一采纳决策

“采纳”表示以当前代码为底迁移相应机制与回归，不表示逐文件覆盖或整提交 cherry-pick。

| 项目 | 决策 | 本文落点 |
|---|---|---|
| 实际 artifact manifest 交接、验证后冻结源码 | 增量采纳，接入当前 source/replay 合同 | R2 |
| precision 缺测/零分母/计数与正文绑定 | 优先采纳，迁移所有读者 | R3 |
| 独立 discovery 分母与 closure retention | 采纳为评估，不授予生产事实权 | R3 |
| 跨 obligation 读取与持久上下文回忆 | 采纳，保留问题级无增益界限 | R4 |
| 符号 compact ref 唯一匹配 | 小修采纳，保留当前身份层次 | R4 |
| combine/fusion 不直接推断 CONCAT | 采纳假设层修正，不删作者显式要求 | R4、R10 |
| 旧 Formalizer 的 LLMRequest/response.text/blocked | 只修有生产调用者的兼容路径，不替换 V2 | R5 |
| 公式 lane/review/authority 贯穿及 witness 隔离 | 增量采纳 | R5 |
| CLI 转发、状态回写、文件名/换行/解码 | 独立小修，不改变 artifact identity | R3、R6 |
| 输入预算 | 重做统一计量与真实请求检查，拒绝独立字节阈值门 | R6 |
| Narrative proposal 和 controller bridge | 采纳问题，使用 typed 绑定重做 | R7 |
| callback 局部保护与稳定比较分母 | 采纳问题，使用依赖图和目标摘要重做 | R8 |
| search_inconclusive / 有范围负证据 | producer→consumer 全链重做 | R9 |
| 模型修订研究假设 | 受保护的独立切片，先验证约束保全合同 | R10 |
| 同 span＋predicate 字符串相等才合并 | 不采用；会拆开 calls/CALL 掩盖 Run E | R1 |
| 变量名 regex 推导公式依赖，整机制 batch | 不覆盖当前 equation/detail 身份与逐页主路 | R5、R6 |
| 固定 caveat 正则、原始条件逐字包含 | 不采用；用语义 witness 与有界修复 | R5 |
| 重写 AGENTS、删除 .agent 历史 | 不采纳；不属于本次产品修复 | 全部 |
| callback 新增本地 _digest_json | 无需采纳；当前已从公共 digest 模块导入 | 全部 |

## 4. 分片顺序与里程碑

R0–R10 已有实现与对应阶段证据，保留为当前基线。R10 已接入循环；新增调用预算和真实入口仍有未闭合项，
不能从历史局部“完成”外推整体通过。下表保留原始技术依赖，当前执行位置以 §15.6 的 S3 收口为准，
具体状态见下方 2026-09-14 执行位置。
按依赖实施并逐片审查，不把远端多子系统改动一次整体覆盖。

| 顺序 | 切片 | 主要退出证据 |
|---|---|---|
| 0 | R0 基线与反例冻结 | 输入、代码内容、产物、采纳来源可定位 |
| 1 | R1 canonical operation / guard / status | Run E 双视图诊断与正反回归；核心门未改 |
| 2 | R2 artifact/source/admission 接线 | 新旧产物隔离、字节冻结、离线/产品准入口径一致 |
| 3 | R3 真实质量与发现指标 | 缺测无满分、精确正文绑定、独立分母 |
| 4 | R4 Research 读取、记忆、符号与 parse 样本 | 跨问题复用有增益、重复无增益停止、诚实 parse 终态 |
| 5 | R5 公式合同与条件表达 | author-intent 不升级 Verified；条件等价表达可绑定 |
| 6 | R6 预算、入口与兼容 | admission 与实际发送同口径、CLI 真入口、路径可重放 |
| 7 | R7 叙事与 controller 精确绑定 | 多机制/多章节完整映射，段落局部义务不扩散 |
| 8 | R8 局部 callback 事务 | 兄弟正文保留，受影响授权重新验证，比较分母稳定 |
| 9 | R9 搜索停止与负证据合同 | 未决不冒充不存在，终态迁移贯穿 handoff/checkpoint |
| 10 | R10 研究假设修订 | 作者约束不可缩小，revision 原子绑定全部消费者 |
| 11 | V 分层验收 | 静态、冻结离线、获准真实诊断/试点与正文分别报告 |

### 当前执行位置（2026-09-14，同一 dirty worktree）

| 范围 | 当前状态 | 直接下一步 |
|---|---|---|
| R10 修订循环与作者边界 | 已实现并有前次边界回归；保留成果，不再沿用“暂缓/未开始” | 按 §15.2 保持保护合同；只处理实际暴露的问题 |
| R1/R2 → 交付 A | S3-20 实际当前图及零模型预检已通过；相关 S1 修复保留 | 不重做旧图诊断；改动影响图/输入时才重验 |
| R6/R7 → 交付 B | 累计账本、发送前 started、恢复已接线；repair reserve、跨 phase primary 保护及真实计量仍有缺口 | §15.6：按失败样本校准并补调度边界，保留累计 fail-closed |
| 交付 C | S3-20 有部分 Writer 正文及 15/18 Realizer 完成页，无完整 Candidate | 先修复零产出/空流协议与有效段落结算，再完整 authoring |

证据见 [2026-09-14 复核](research_to_method_delivery_checkpoint_review_2026-09-14.md)。以下为旧切片的
历史检查点，解释其绑定时点；其中“未开始”“本片完成”及当时根因不再作为当前执行状态。

### 历史切片检查点（2026-09-12）

| 切片 | 状态 | 证据 |
|---|---|---|
| R0 基线与反例冻结 | 已完成 | `.tmp/c2p-unified-repair-20260912-r0r1/baseline_manifest.json`、`adoption_ledger.json`、`run_e_fixture_comparison.json`；Run E 五文件字节摘要与附录 A 一致；十项目冻结 root 均存在 |
| R1 canonical operation / guard / status | 已完成（本片代码接受） | `mechanism_context_compiler.py` 的 typed 支配恢复、同操作对应证明、证据化聚合与同 span 支配；`tests/test_agentic_mechanism_evidence_closure.py`、`test_agentic_mechanism_detail_compiler.py`、`test_agentic_unified_context_compiler.py` 正反回归；Run E 冻结输入离线重建 `unknown_core_active_path_count=0`，原两个失败码消失 |
| R2 artifact/source/admission 接线 | 已完成（本片代码接受） | 本次 persistence manifest 绑定 Writer 输入（legacy 发现需显式标记）；`VerifiedSourceBytes` 修订冻结 + digest/路径/partition/symlink/binary 校验；facts/claims 跨 run 身份拒绝；offline strict 门改为调用产品函数并显式分列 strict/Candidate（Run E：strict 三条 partial，Candidate 通过、handoff eligible）。全量静态 `3274 passed, 3 skipped`；新增 `tests/test_agentic_authoring_context_handoff.py` |
| R3 真实质量与发现指标 | 已完成（本片代码接受） | `SupportPrecisionMetricV1` + 共享 `compute_support_precision_metric`（缺测 not_measured／零分母 not_applicable／摘要或计数无效 invalid／blocked 不记满分；caveated 不并入 supported；lexical_only 不授权 Verified）；runner 改用同一 metric 并在可见状态变化时回写；funnel 的 discovery recall 改为独立 expected population 才测量（缺分母未知），closure retention 单列、零分母比率显式列出；`TextEvidenceValidationReport` 拒绝布尔计数。全量静态 `3281 passed, 3 skipped` |
| R4 Research 读取/记忆/符号/parse | 已完成（本片代码接受） | 读取身份拆为字节身份与 obligation-scoped 分析身份：同 obligation 重读仍拒绝，跨 obligation 允许复用字节并须重新编译本问题图/claim；supervisor 已读抑制、候选过滤与 prompt 的 forbidden/reusable 分区同步；新增有界可解释 `relevant_prior_reads` 投影（带选择原因/recency/截断标记，不称覆盖证明）；compact 符号仅唯一匹配；combine/merge/fuse 不再强制 CONCAT；supervisor 失败按 api/blocked/empty/parse/表示修复失败/内容错误分类记录并保留真实终态。全量静态 `3292 passed, 3 skipped` |
| R5 公式身份/授权/条件表达 | 已完成（本片代码接受） | 旧公式包适配需 repository_verified + repository_derived + accepted + 精确绑定才给 `code_verified`，author-intent/review-required 不因带 fact ID 升级；`schema_version=2.0` 的当前包缺 disposition 不再落入历史默认 accepted；条件绑定走受控等价/否定/无条件语义判定（等价通过、反向失败，无 substring 硬匹配）；compact payload 保留 lane/review/binding 元数据；legacy Formalizer 读取真实 `text`/`blocked_reason` 并分列 interface/missing/rejected/not_applicable。R5 指定批次 `169 passed` |
| R6 预算、入口与兼容 | 已完成（本片代码接受） | envelope 声明 token meter、每角色 prompt/output/thinking 预留、每请求输入上限、safety margin 与 context window，无代码内默认值；计划与实际发送用同一计量函数测同一组 parts，超过上限在发送前拒绝并持久化 receipt（formalizer 还要求计划值=实际值）；页预算按整页 payload 计量并报告超大原子贡献，冻结 Run E 的 `unified_atomic_page_over_budget` 消失（113 页 workset 通过）；安装入口 `code2paper` 转发 `method-agent`；callback 文件名可移植、幂等且不静默覆盖；冻结链 digest 跨进程可复现 |
| R7 叙事与 controller 精确绑定 | 已完成（本片代码接受；§12.2 记为未接受路径） | 旧 outline 章节按**已证 owner**（声明 mechanism_ids 或段落 mechanism_id 唯一）复用，owner 不可证明时显式阻塞，机制无对应章节时生成 `MA-REV-*` revision；段落 owner/detail 与 section/unit 的一致性纳入 validator；join 页按消费者身份区分公式 repair 与多机制 section 页（伪造 repair/缺失依赖证明失败关闭）；超预算段落按 detail 拆分为合法 fragment（plan revision，证据不截断）；§12.2 proposal caller 未消费时记 `proposal_status=not_accepted`，不计自主组织成功。冻结 Run E：131 页、4 worksets、三 phase 均编译（65/18/18 调用），`failure_details` 为空，仅余研究证据类失败码 |
| R8 局部 callback 事务 | 已完成（含 2026-09-12 复核纠偏） | typed 依赖闭包按**重建后权威差异**计算（claim 合同变化也计入），恢复范围在超出请求时扩展、目标不可映射时显式阻塞，并核对 Writer 实际采用的 section 范围（有证据才判定）；callback 轮次预算与阶段记录损坏时失败关闭，ledger 完成回执严格读取，未结算的已开始调用按计划 token 保守预留（当前尝试除外）；事务比较改用完整目标合同（qualifier/极性/authority/lane）并纳入 section 与 paragraph 公式义务，删目标或改合同不再算增益 |
| R9–R10 | 未开始 | 无 |

G1 结论：Run E 混合状态直接根因已消除；配置选择证据仍缺（`self.cfg.use_dedicated_attention`
value=null/state=unresolved），入口路径外未证操作仍产生 `operation_disposition_unresolved`，
按 §6.2/§6.3 标记 **NEEDS_RESEARCH_EVIDENCE**，不称 Run E 已解除阻塞、不宣称 authoring PASS。
冻结离线重建当时另观察到页预算失败（两页 20766/20868 tokens），已按 §16.2 列为 R6 差异并在 R6 修复。

R2 结论：产品只消费本次 persistence manifest；resolver 使用修订冻结且 digest 校验的源码字节；
offline 与产品共用同一 strict 门，并显式分列 strict/Candidate（Run E：strict 三条 partial，
Candidate 通过且 handoff 重验无失败）。全量静态 `3274 passed, 3 skipped`；未调用模型。

R3 结论：support precision 只在有绑定当前正文、计数自洽的真实验证报告时才给出数值，
缺测/零分母/无效/blocked 均不记满分，caveated 与 supported 分离，`lexical_only` 不授权 Verified；
runner 使用同一 metric 并在可见状态变化时回写；发现率改为独立 expected population 才测量，
closure retention 单列。全量静态 `3281 passed, 3 skipped`；未调用模型。

R4 结论：读取身份分为字节身份与 obligation-scoped 分析身份，同一问题重复读取仍判 no-gain，
跨问题可复用字节但必须重新编译本问题证据；决策上下文新增有界、可解释的先前读取投影（不称覆盖证明）；
compact 符号歧义不再随机绑定；combine/merge/fuse 不再被当成 CONCAT；supervisor 失败按
api/blocked/empty/parse-repair/内容错误分型记录并保留真实终态。全量静态 `3292 passed, 3 skipped`；
未调用模型。Run D 原始响应未找到，按 §9.6 记为未复现缺口。

R5 结论：公式授权按“证据权威 + lane + review 状态 + 精确绑定”四项同时成立才提供实现 witness，
author-intent/review-required 不因携带 fact/equation ID 升级；当前 `2.0` 包缺 disposition 字段保持
review_required，只有无版本或 `1.0` 历史包可走旧兼容接受；条件绑定使用等价组/否定/无条件/连接词
的受控语义判定（等价论文表述通过、反向或扩大范围失败），不使用 substring 原码匹配；旧 Formalizer
只修有生产调用者的兼容路径，接口 blocked/empty 与缺绑定/rejected/not_applicable 分列记录；
V2 page/prompt/payload/receipt 未回退。R5 指定批次 `169 passed`；未调用模型。

R6 结论：预算合同集中在 frozen envelope（meter、每角色 prompt/output/thinking 预留、每请求输入上限、
safety margin、context window），计划与发送共用同一测量函数与同一组 parts，超限在发送前拒绝并
持久化 receipt；页预算按整页 payload 计量，超预算不再以逐 atom 求和掩盖，单页原子过大时报告
obligation 与贡献原子而不截断证据；安装入口使用唯一产品 parser，callback 产物路径可移植、
幂等且禁止静默覆盖；另外修正了源身份泄漏捕获时间导致的冻结链 digest 不可复现问题。
G2 全量静态 `3316 passed, 3 skipped`（`compileall`/`git diff --check` exit 0），冻结 Run E 离线链
workset 编译通过且跨进程 digest 可复现；未调用模型。

R7 结论：叙事计划按 typed owner 证据分配旧章节身份，不再按位置重排内容；owner 不可证明的旧章节显式阻塞，
机制缺少对应章节时形成 `MA-REV-*` 明确 revision；段落 owner 必须同时属于其 section 与 unit 的机制集合，
required detail 必须属于该 owner。多机制章节的 Writer/Realizer join 页按消费者身份路由（公式 repair 页保留
obligation 检查，章节 join 页检查 section/paragraph 依赖证明），伪造身份失败关闭。超预算段落按 detail 拆为
合法 fragment（plan revision，不截断证据、不抬高页阈值）。§12.2 的 proposal 未消费时记录为未接受，
不宣称自主组织成功。

R5 纠偏（按方向复核报告）：撤回“等价短语可绑定”结论；删除通用代码中的项目配置名，条件授权改为结构判定
（AND/OR 序列、逐子句否定奇偶、比较运算符与数值、无条件标记、附加极性子句），词法匹配仅用于定位候选；
结构无法证明即失败关闭，并在 Binder 响应、确定性 Binder 与 Writer 事务评估三条路径一致执行。

R6 预算闭合（live 前）：声明 `scaffolding_token_reserve`（每角色）并计入计划上界，使计划值成为该角色真实
请求的上界；发送端先测真实 parts（不含 allowance），依次检查角色上限、计划上界与 run reservation 的原子
扣账（按 ledger 已完成 receipt、按 plan digest 过滤）。重试与 resume 复用同一 reservation，
`reservation_contract=atomic_debit_v1`。

依赖：R1 先于机制相关重组；R2/R3 是后续证据基础；R7 依赖 R5/R6；R8 依赖 R2/R7；
R10 依赖 R4/R9 以及 agenda/handoff 的 revision 设计。兼容小修可以单独形成较小子片，仍串行交付。

里程碑分开记录：

- **G1 直接根因检查点**：R0＋R1 静态及冻结证据完成。若精确配置/路径仍缺证据，标为
  `NEEDS_RESEARCH_EVIDENCE`，不得称 Run E 已解除阻塞；不妨碍后续独立静态修复。
- **G2 交接与可观测性检查点**：R2–R6 完成后运行一次全量静态；完成冻结 Run E 的完整派生链检查。
- **G3 作者到正文检查点**：R7–R10 完成后运行一次全量静态及完整离线矩阵/纵向合同测试。
- **G4 真实产品检查点**：仅在对应结构准入与 live 授权满足后运行。输出正文、条件、公式和阅读质量证据。

R7–R10 已有实现，当前缺口以最新执行位置及 §15 为准。正式 G3/矩阵的验收条件保留；
首份单项目 Candidate 诊断按 §15.4、§16.3 推进，R10 新功能扩展不额外成为其前置。
继续核对字段与失效传播，不创造第二套 authoring IR 或放松保护门。分片是技术依赖与验证边界，
常规方向内实现不要求用户反复选择；在既有授权范围内推进并记录结果。

## 5. R0：冻结输入和实施基线

**责任文件**：`.agent/implementation.md`；必要的测试 fixture/只读诊断脚本；任务专属 `/tmp` 输出。

1. 记录 Code2Paper HEAD、tracked diff 的字节摘要和每个相关 untracked 源码/测试的字节摘要。
   `git status` 只证明路径状态，不是代码内容摘要。排除凭据；记录 profile 的安全配置与摘要，不复制秘密。
2. Code2Paper 实现身份、被研究仓库 snapshot/tree hash、profile/model identity 分开写，不能把目标仓库
   commit 当作实现代码 commit。每次迁移后形成新的 code-state binding。
3. 冻结 Run E 的 facts/claims/configuration/graph/handoff/retry/promotion、机制上下文、admission 和结果文件。
   记录原始文件 SHA-256 与模型内 content_digest，二者不可混淆；不覆盖原 run。
4. 生成项目中立的最小双视图 fixture，含完整 owner、source、typed branch、fact/graph 绑定；另保留真实
   Run E 只读离线输入引用。禁止用空 facts 或删掉 formula obligations 的源级示例代表真实回放。
5. 固定远端 f58d806 逐 hunk 采纳日志：来源、当前等价实现、迁入/改写/拒绝理由、回归证据。
6. 盘点既有十项目冻结输入是否仍存在。09-09 文档记录过清空；当前不能凭路径名字假设已恢复。

**交付**：`baseline_manifest.json`、`adoption_ledger.json`、Run E 与最小 fixture 的对照摘要。
这些是任务证据文件，可放任务专属 `/tmp`；关键状态在 implementation 中有可读索引。

## 6. R1：修复同一操作的条件与路径状态

**首片允许落点**：

- `src/code2paper/agentic/mechanism_context_compiler.py`：`_fact_operation_parts`、
  `_graph_node_operation`、`compile_mechanism_evidence_closures`、`_operation_clusters`、
  `resolve_active_path_status`、`_operation_status`、`annotate_mechanism_paper_details`。
- `mechanism_context_models.py`：仅在现有 guard/activation_basis_ids/来源引用不足时补最小可验证字段。
- `configuration_claims.py::compile_configuration_claims` 与
  `implementation_scope.py::resolve_configuration_binding`：只补精确配置来源与使用点绑定，若根因确实需要。
- `tests/test_agentic_mechanism_evidence_closure.py`、`test_agentic_mechanism_detail_compiler.py`、
  `test_agentic_mechanism_formula_obligations.py`、`test_agentic_publication_method_writer_unified.py`。

### 6.1 先统一来源语义，再计算聚合状态

1. 建立现有 schema 内的操作对应证明：同 snapshot、owner、符号作用域、精确 span，且操作种类、输入、
   输出/赋值位置一致。predicate 映射只能使用通用的已有语义词汇对应，如 calls↔CALL；单靠大小写、
   span 相同或 result 名字相同不足以合并。一个 span 内的不同嵌套操作、不同 owner 必须可区分。
2. 对图操作从其已绑定的 typed TRUE_BRANCH/FALSE_BRANCH/控制依赖追溯条件和极性，限定支配范围。
   fact 的 condition 与其来源关系相互核对；不能把 packet 级 guard 扩散到同文件所有操作。
3. 嵌套条件保留必要合取、反向分支和配置引用；格式归一化不改变逻辑。同条件的字符串表示可规范化，
   不得由宽松关键词相交证明等价。
4. 图中缺省 guard 若可由冻结关系恢复，与 fact 对齐；无法恢复则记录缺失/冲突和拥有者，不凭 fact 文本
   强制升级全部图操作。保持两种原始表示和 lineage，可审计其归一化过程。

### 6.2 路径状态判定约束

| 输入事实 | 合法结果 | 禁止行为 |
|---|---|---|
| 同一操作双视图，一方带 guard；冻结控制关系证明 guard 及范围 | 对齐成已有 conditional 语义，保留条件来源 | 仅因为集合含 conditional 就返回 conditional |
| 同一操作无 guard，默认/显式选择有一致证据 | 按既有 default/selected 规则，保留选择依据 | 用模型解释替代配置取值或入口证明 |
| TRUE/FALSE 极性冲突、owner 冲突、支配关系不足 | unknown＋具体失败原因，交回拥有者 | 合并成无条件、任选一个状态 |
| guard 精确已知但选中配置取值未知 | 仅表达已被证明的条件行为；选择事实仍 unresolved | 把“若开启”改成“实际开启” |
| 本项要求证明实际选中路径，但缺配置/入口证据 | 保持 unknown，生成明确证据需求 | 把 selected 要求降成 conditional 来过门 |
| 确认 inactive/unreachable 的分支 | 保留审计和正确终态，不晋升核心实现事实 | 清空/删除分支提高 completeness |

本表不改变 `validate_mechanism_context_completeness` 或 unified admission 的通过标准。
`conditional` 只有在现行合同允许且具体控制证据成立时使用；遇到是否允许的设计歧义，提交给 Codex，
不能直接增加“混合 active 全通过”的规则。

配置证据要绑定定义、覆盖链、入口和消费位置；不存在的值保持 null。不要从 author intent、文件名、
历史 profile 或 EBCAR 已知答案推断值。若需要进一步 Research，列清 key、定义/入口缺口和查询范围。

### 6.3 重算与退出证据

- 只重建受影响的 closure/detail/context/archive/workset/plan/admission；所有内容摘要重新校验，
  旧 Research facts/claims 和 Run E 原文件不覆写，不用记录级 model_copy 绕过 validator。
- 保留现有跨 span union 约束及 owner/typed path 检查。提供原始 operation→归一化 operation→detail
  对照，证明没有删 claim、减 core、重复拆 detail 或更换 owner 来让错误消失。
- Run E 的 mixed-status 根因应被明确消除或被更准确的证据缺口替代。若仍缺选择证据，输出
  `NEEDS_RESEARCH_EVIDENCE` 及冻结失败，不宣称 authoring PASS。
- 验证同 span 不同操作、跨 owner、嵌套反向条件、无条件默认路径、配置 false/未知、顺序交换、
  JSON 持久化往返，以及完整 facts＋graph 输入通过真实 loader 到 admission 的路径。
- 负例必须在模型调用前拒绝，caller 调用数为 0；不得仅直接测私有聚合函数。

**首片聚焦命令（后续实施时执行）**：

```bash
python -m pytest -q tests/test_agentic_mechanism_evidence_closure.py tests/test_agentic_mechanism_detail_compiler.py tests/test_agentic_mechanism_formula_obligations.py tests/test_agentic_publication_method_writer_unified.py
python -m pytest -q tests/test_agentic_research_models.py tests/test_agentic_candidate_handoff.py tests/test_agentic_autonomous_method_agent.py
python -m compileall -q src tests
git diff --check
```

首片不运行全量静态、不调用真实模型。冻结离线调用如发现当前 matrix harness 的 Candidate 口径与产品不一致，
分别记录 structural mechanism 结果和 harness 差异，交 R2 修复；不为本片把 strict failure 直接过滤成 PASS。

## 7. R2：本次产物交接、源码冻结和准入口径

**落点**：`autonomous_method_agent.py::_writer_artifact_paths/persist_product_artifacts`、
`publication_method_writer.py::_load_repository_authoring_context`、`repo_snapshot.py`、`source_inventory.py`、
`authoring_context_contract.py`、`scripts/run_authoring_replay.py`、`scripts/run_unified_ten_project_offline_matrix.py`。

1. 产品直接传本次 persistence 返回的 manifest；兼容目录发现只用于明确标记的旧入口。
   callback 每轮使用该 revision 实际 manifest，不能被“目录里恰好有文件”补入旧 claims/plan。
2. 保留现有 repo_snapshot、symbol_index、source manifest、implementation_scope、canonical claims、
   handoff/retry、run identity 与 authoring artifact identity 校验。提供了损坏或异源文件时拒绝，不能吞为空。
3. 为 resolver 提供已验证的源码字节映射或等价的 digest 校验 reader；读入前核对允许的 source partition、
   路径边界和 snapshot 摘要，读入后同一 revision 固定。binary 只参与摘要验证，不当作源码文本。
   不在每个 detail/请求前重新扫描全仓，不无故重建已有 symbol index。
4. Replay 外部 `--repo` 必须与冻结 tree hash 一致；不能凭新工作目录替旧 run 发明证据。
   源码变化、symlink 越界、同名异源 helper、删除文件都得到可审计失败。
5. Offline harness 与产品使用同一严格/Candidate admission 语义，完整加载并重验 handoff/retry/promotion。
   当前 matrix `_research_gate_failures` 仍有单独 partial/gap 判定；必须显式输出 strict 结果与 Candidate
   结果，不默认把 partial 当 strict 通过，也不因为旧 harness 不识别 handoff 而伪造终态 gap。

**验收**：旧目录污染不会进入本次 manifest；loader 后修改 helper 不改变已经冻结的 bytes，再次加载报漂移；
跨 run facts 与 snapshot 错配拒绝；相同 frozen 输入在产品和 offline 的每个 gate 判断一致，区别只来自显式模式。

**测试**：扩展 `test_agentic_autonomous_method_agent.py`、`test_agentic_publication_method_writer_unified.py`、
`test_agentic_source_authority.py`、`test_agentic_replay_execution_record.py`、`test_agentic_candidate_handoff.py`、
`test_agentic_unified_ten_project_offline_matrix.py`。可新增 `test_agentic_authoring_context_handoff.py` 承接远端正反用例。

## 8. R3：质量与发现指标恢复诚实计量

**落点**：`publication_quality.py::EpistemicSafetyMetricsV1/evaluate_publication_method_quality`、
`runner.py::_reconcile_publication_quality_with_final_validation/_reconcile_publication_writer_result_with_quality`、
`method_content_trace.py::MechanismInformationFunnelV1/build_method_content_trace_v2`、Writer 对应调用端。

1. support_precision 仅从对当前正文的真实验证报告计算；检查 input_text_digest、非负整数和计数分区。
   supported 不含 caveated；unsupported 与 unverified 不可丢失。缺报告 not_measured，零分母
   not_applicable，无效摘要/计数 invalid，blocked 不得记已测满分。
2. 报告绑定“哪份正文、哪条 Candidate/Verified lane、哪个 verifier mode”。不同正文的数值不可混用。
   `lexical_only` 等模式必须可见，不能把模式较弱的 precision 当作 Verified 授权。
3. 独立 expected population 与 Research discovered IDs 才能定义发现率；缺分母保持未知。
   closure retention 另算。禁止用 closure 自身反向构造 discovery 分母；missing artifact 不等于空集合。
4. 审计所有 float 假设、CSV/JSON/Markdown 汇总和 downstream 消费者，明确 None/状态的迁移策略。
   旧 V1 报告保持可读但不追认为已测；有语义变化的持久化数据使用明确版本或兼容判定。
5. runner 即使总体状态不变，也在 candidate/verified validation status、正文摘要或质量信息变化时回写。
   无正文继续 not_started/not_run；不能用指标缺测单独删除已有 Candidate。

**验收**：缺测、零计数、计数不守恒、布尔冒充整数、旧正文、blocked、全部 caveated、不同验证模式，
以及“漏掉一个独立 expected operation”正反例。Writer 与 runner 对同一报告得出相同结论。

**测试**：`test_agentic_publication_method_writer.py`、`test_agentic_runner.py`、
`test_agentic_detail_atom_binder_and_trace_v2.py`、`test_agentic_method_content_trace.py`。

## 9. R4：Research 读取复用、记忆和失败恢复

**落点**：`research_policy.py::_no_duplicate_no_gain`、`research_supervisor.py` 的已读过滤、
`research_graph.py` 的 context 构造、`research_nodes.py::InformationGainTracker`、
`implementation_scope.py::_canonical_symbol_id`、`intent_compiler_v2.py`、
`gemma_supervisor_backend.py::_parse_proposal` 与既有 response recovery。

1. 区分 source bytes 缓存身份与 research analysis 身份。同 snapshot 的相同源码可用于新的 obligation，
   但已有 observation 不能被改写成另一 obligation 的事实证明。复用字节后仍需本问题的图/claim 编译。
2. 去重至少按 obligation＋规范参数＋源码/scope 身份判定；同一问题无增益调用继续拒绝。
   若需要再次读取，沿用现有稳定 tool-call signature，不通过 turn index 或随机 ID 逃避无增益限制；
   执行 occurrence 与 signature 分开记录，不让 receipt/observation ID 碰撞或覆盖。
3. 从持久 observation_history 投影当前问题与相关先前精确读取，按现有预算限定上下文；排序、关联选择
   可解释，全文记录仍保留。不把最后 N 条记忆称为完整研究覆盖，不添加无关全仓历史。
4. compact path/name 引用仅唯一匹配时选择；同名不同作用域、只有 path 但文件含多个候选时保持歧义。
   保留当前 explicit/lifecycle/call_graph_root/lexical 入口优先序及 unresolved_ambiguous 规则，
   不采纳远端“除 explicit 外全部清空”的范围重写。
5. 修正 combine/merge/fuse 与明确 concat 的词汇假设区别。作者明确的连接方式、顺序、条件不得变成泛化
   COMPUTE 后视为满足；自动修订已形成义务的机制留待 R10。
6. 将 Run D 的冻结原始响应、request/schema/template/model identity、parse/recovery/fallback 记录归档。
   可恢复的 JSON 表示损伤走既有恢复；内容/ID/证据错误交回 owning Agent，采用现有有界 repair。
   无响应、超时、解析失败保留真实 terminal，不变成支持事实或已生成 Candidate。
   若原始响应不存在，只记录未复现缺口，不编造同样输入；可先补协议级 synthetic 负例。

**验收**：跨问题同源读取能够提取不同关系；同问题重复无增益停止；切换 obligation、checkpoint/resume 后
历史与预算一致；歧义符号不随机绑定；合法 concat 保留；损坏 JSON 与未知 claim ID 得到不同恢复/拒绝路径。

**测试**：`test_agentic_research_policy.py`、`test_agentic_research_supervisor.py`、
`test_agentic_graph_research_loop.py`、`test_agentic_research_checkpoint_resume.py`、
`test_agentic_gemma_supervisor_backend.py`、`test_agentic_typed_refs.py`、`test_agentic_intent_compiler_v2.py`。

## 10. R5：公式身份、授权和论文条件表达

**落点**：`formalization_agent.py::adapt_mechanism_formula_package_to_legacy` 及仍被调用的 legacy caller，
`llm/section_writer.py::_compact_formula_packages_for_llm`、
`publication_transaction_contract.py::_formula_package_terminal_disposition/paragraph_binding_targets/bind_paragraph_witnesses`、
Writer 的公式路由与反向验证连接处。

1. 在消费者中统一检查 formula_lane、evidence_authority、authority_status、review_status 与精确来源绑定。
   当前包必须满足既有 repository-derived/verified 要求才提供实现 witness；author-intent 或 review-required
   不因带有 fact ID 而升级。旧包按明确版本兼容，不允许缺字段的当前包进入“历史默认 accepted”。
2. compact payload 保留这些元数据、material_conditions、assumptions 与 consumer paragraph identity。
   自然语言政策提示不替代 machine-readable lane；不把 implementation_formula 标签写进论文正文。
3. Candidate 可保留作者意图形式化和学术表达，未验证状态进入审阅 sidecar，必要注释由 Writer/Editor 生成；
   不强制每个公式段出现固定 caveat。Verified 仍执行公式、条件、极性、数字与证据反向验证。
4. 条件绑定使用已有 paragraph witness/Binder 的精确锚点与受控语义判定：等价论文表述可通过，
   条件缺失、反向或扩大适用范围失败并返回 Writer/Formalizer 修复。禁止 substring 原码硬匹配，
   也禁止只凭宽松关键词相交放行。公式插入仍只替换精确占位符和 display block。
5. 仅对有实际调用者的旧 Formalizer 修复 request 完整性、response.text、blocked_reason 与错误记录。
   当前 `run_unified_formalizer_phase_v2`、逐页 task batch、AST/source fidelity、receipt/fragment 不回退。
   正常缺包、失败包、rejected 与 not_applicable 分开；确定性 fallback 不得掩盖未发模型或接口异常。
6. 保留按 equation/detail 精确分组及分母/归约/归一化/符号条件检查。若发现局部数学依赖缺失，
   通过冻结 typed dataflow 扩展 consumer workset，保留 source equation ID 与页绑定；不引入 regex sink 作为授权。

**验收**：作者公式伪装成 repository authority 被拒；元数据往返不丢失；等价条件可绑定、相反条件不可绑定；
同一公式不得被消费到错误段落；display block 不含整篇备忘录；旧 caller 的真实 LLMRequest/LLMResponse
类型测试证明确实调用且读取 text；V2 page/prompt/payload/receipt 字节身份继续成立。

**测试**：`test_agentic_mechanism_formalizer.py`、`test_agentic_formalization_guards.py`、
`test_agentic_formula_obligation_truths.py`、`test_agentic_mechanism_formula_obligations.py`、
`test_agentic_detail_atom_binder_and_trace_v2.py`、`test_llm_section_writer.py`、
`test_agentic_publication_method_writer_unified.py`。

## 11. R6：调用预算、真实入口和可移植产物

### 11.1 请求预算合同

**落点**：`unified_context_compiler.py::build_consumer_request_payload/consumer_request_envelope_digest/`
`build_consumer_invocation_plan_v1/_per_invocation_input_budget/bound_consumer_llm_config`、
`unified_context_models.py`、`unified_invocation_ledger.py`、`llm/client.py`、`schemas.py`。

- 使用同一个版本化计量器核算计划和实际发送的 system/user 包装、payload、response schema、
  model context、输出预留与 safety margin。能获取指定模型 tokenizer 时使用它；否则保留明确标记的
  保守估算和单位，不声称通用 UTF-8 bytes 就是 token 数。
- 入参 max_input_tokens、role output budget、context window 和全 run reservation 一起限制；
  未配置时使用已声明 profile 合同，不悄悄新增 98,304 等全局默认值或“无限制”。
- 在真实网络发送前检查实际 envelope 与冻结 invocation；拒绝时持久化失败 receipt。
  admission 与 client 不建立两个互不知情的阈值，cache/dry-run 也保持明确状态语义。
- 超预算可在计划阶段重建合法页/投影及 revision，不能截断 evidence/core details、压低 obligations 或
  在 admission 后改变 technical bytes。超大原子无法合法分页时报告该原子及预算贡献。
- 后续 Narrative proposal 也纳入 role 预算与调用记录，不发送没有 budget 的全量 context details。

**验收**：CJK/代码/长 schema/输出预留，预算边界两侧，计划与发送不一致，单页超大原子，
取消和 resume 后额度；零网络调用的拒绝测试、每页调用上界和未完成任务的可恢复 receipt。

### 11.2 独立兼容小修

**落点**：`main_cli.py`、`pyproject.toml` 的既有 script 映射、`tool_runtime.py::atomic_write_bytes`、
`writing_callback_fulfillment.py` 文件路径构造、`benchmark_review_workspace.py`、
`validators/latex_smoke_validator.py`。

- 安装入口 `code2paper` 能正确转发 `method-agent` 并保留其他子命令与帮助；不新建第二套产品 parser。
- artifact ID 与文件名分离。callback 使用可移植的安全文件名与显式路径记录；哈希截断需检测冲突，
  相同 identity/digest 幂等，不同内容不能静默覆盖。保留旧 artifact 引用的兼容读取。
- 临时写文件保持同目录原子替换，短前缀不改变最终目标或 digest；固定 LF 和子进程明确解码仅影响表达层。

**测试**：`test_llm_runtime.py`、`test_agentic_unified_context_compiler.py`、
`test_agentic_publication_method_writer_unified.py`、`test_agentic_autonomous_method_agent_cli.py`、
`test_agentic_research_tool_runtime.py`、`test_agentic_autonomous_callback_fulfillment.py`、
`test_agentic_d6_portability.py`。Windows 不可用时明确平台测试未执行，不能因 Linux 通过宣称 Windows 已验收。

R2–R6 的集成改动构成 G2；此处才运行一次 `python -m pytest -q`，不在每个小片反复运行全量。

## 12. R7：Narrative proposal → controller 的精确绑定

**落点**：`method_architect.py::build_narrative_plan_v3/validate_narrative_plan`、
`publication_method_writer.py::_build_narrative_plan_v3/_writer_section_inputs_v3`、
`method_argument_models.py`、`unified_context_compiler.py::extend_writer_worksets_from_narrative_plan`。
仅在现有边界容纳不下时新增小型 typed bridge 模块，不复制远端 `_strings` 匹配器。

### 12.1 映射合同

以现有 IDs 记录每次映射：source plan digest、context digest、mechanism owner、argument unit、
目标 section/paragraph、required detail/atom、formula obligation/package、author rationale 与 dependencies。
绑定来源必须是 typed owner/claim/facet/brief/assignment 引用；section ID 相同不自动证明内容相同。

- 唯一映射时采用；多候选或零匹配时列候选与缺少的来源，不按字符串得分、位置或字母序猜一个。
- 每个 paragraph 只接收它拥有的 unit/target/formula 集合，不能复制整个 section 的所有要求给每段。
- 合并章节保留 unit、move authority、dependencies、未决问题；拆分章节按明确 owned units 分配。
  required target 不丢失，formula owner/consumer 唯一，局部约束不得变弱。
- 当前 `prior_sections > contexts` 分支使用第一 context 分配旧章节，以及普通分支按序号配对，均纳入修复；
  不能只改普通循环而遗漏 Run E 这类多章节/较少机制输入。
- 旧 controller 与 NarrativePlan 的身份映射形成可验证结果，再生成 Writer workset/plan/revision；
  不在正文写完后仅补一份“看起来一致”的 sidecar。

### 12.2 LLM 的权限与失败路径

接通现有 proposal caller，让它提出组织、阅读问题、段落深度和表达顺序；不授权事实、证据 ID 或缩减要求。
输入为预算内的意图/组织投影与所需证据引用，technical bytes 仍经既有页合同送消费者。
校验 proposal 保留必需目标、条件、公式和来源；失败走已有有界 repair，无语义增益停止。
可保留仍然有效的既有计划，但必须记录 proposal 未接受，不能计为自主组织成功。

**验收**：两机制反向排序、同名章节、共享 detail、合法合并/拆分、相同 section ID 却 owner 变化，
来源同分歧义、删除 motivation/rationale、扩大段落单位、丢失 dependency、公式被路由两次。
应通过 controller→真实 Writer request 的截获检查证明语义和闭集身份一致，而非只验证 JSON schema。

**测试**：`test_agentic_narrative_architect_v3.py`、`test_agentic_method_architect_product_readiness.py`、
`test_agentic_publication_method_writer_unified.py`、`test_llm_section_writer.py`、
`test_agentic_unified_context_compiler.py`。可新增 `test_agentic_narrative_controller_bridge.py`，明确标为新文件。

## 13. R8：局部 callback 与稳定比较分母

**落点**：`writing_callback_fulfillment.py::fulfill_and_resume_writing_callbacks/recompile_authoring_revision`、
`publication_method_writer.py::_rewrite_transaction_metrics/_rewrite_transaction_has_cluster_gain`、
`scripts/run_authoring_replay.py` 的事务快照与恢复、现有 authoring state/依赖失效路径。

1. 由请求目标及 typed authority diff 求依赖闭包：claim/fact/config/condition/formula/detail→unit→paragraph→section。
   实际影响到兄弟 section 时重新验证该 section；纯标题排序变化不使无关正文失效。不能递归扫任意字符串求交。
2. 未受影响 section 的已提交正文、authorship、witness、formula placements 和依赖绑定原样保留。
   受影响对象进入新 revision，不全局重写；不能因一个 callback 失败抹掉此前可读 Candidate。
3. 单独计算 `required_target_set_digest`，基于规范排序的目标类型/稳定 ID、必要条件/极性、authority 要求。
   不含 heading、section 排序、措辞和生成时间；不以整份 plan.content_digest 代替。所有摘要重算并持久化。
4. 同一目标集合下比较质量增益与非回归；合法新增/修订目标形成新比较基线，同时对旧目标保留交集上的
   非回归检查。删除旧 required target 不是增益，不能用分母缩小宣称 callback 改善。
5. 分开记录 research fulfilled、revision rebuilt、writer resumed、prose committed、最终验证状态。
   无 semantic delta 不恢复 Writer；缺少明确 resume section 不进入全量重跑。
6. 在 Research 完成、plan 已重建、Writer 已暂存/未提交处的异常或中断都能恢复，重放不能重复消费预算
   或把前一 revision 的 witness 用到新正文。

**验收**：只修一段兄弟字节不变；共享配置变化重新验证相关兄弟；heading 改动不改变要求摘要；
删目标被拒；新增目标不伪造增益；callback fulfillment 成功但 Writer 失败仍标未提交；三处中断恢复身份一致。

**测试**：`test_agentic_callback_resume_product.py`、`test_agentic_callback_semantic_contract.py`、
`test_agentic_research_graph_callback_continuation.py`、`test_agentic_autonomous_callback_fulfillment.py`、
`test_agentic_replay_execution_record.py`、`test_agentic_publication_method_writer.py`。

## 14. R9：搜索未决与有范围负证据的完整终态

本片是终态合同变化，不能仅移植远端字段。开始前 Codex 核对 R4 的搜索回执与当前 Candidate retry 产物，
明确版本、兼容读取和既有 `explicit_gap` 的迁移范围。

**落点**：`research_models.py::GapRequirementV1`、`research_nodes.py::InformationGainTracker/gap_finalizer_node`、
`research_tools.py::record_explicit_code_gap/execute_research_tool`、`autonomous_method_agent.py::build_typed_gaps/`
`_load_terminal_gap_artifacts`、`research_terminal.py`、`intent_ledger.py`、handoff/admission 及 checkpoint 消费者。

### 14.1 三种结果不可混用

| 结果 | 所需证明 | 下游含义 |
|---|---|---|
| search_inconclusive | 实际查询与观察、仍未回答的问题、停止原因 | 研究未决，不证明代码不存在 |
| budget_exhausted | 已用预算、剩余 frontier、未完成任务 | 有界停止，不是搜索完成 |
| unsupported_with_scoped_evidence | 冻结 scope、查询策略/覆盖前沿、读取与关系检查、可核验关闭依据 | 仅授权该 scope 与该命题范围内的负结论 |

搜索回执至少绑定 run/snapshot、obligation、规范查询和过滤范围、top_k/截断状态、结果 IDs/digest、
已读/未读候选、工具失败/预算和可核验的 frontier closure。不能仅依赖 notes 中
`search_frontier_closed=true` 或“调用过两个工具”来产生负证据。

### 14.2 Producer 与 consumer 一起迁移

- success_empty 只说明该次查询为空，不自动记整个搜索 exhausted。
- 无增益到界可以结束某次研究，但必须保存 unresolved；不写 search_complete=true。
- 有范围负证据必须验证来源和命题，无关 span、scope 之外的候选、截断 top_k、未读候选、超时都不能证明关闭。
- 旧 gap 若没有足够证书，兼容读取为未决并保留原始数据，不回填“完成”。缺字段绝不默认授权负证据。
- Candidate partial 仍要求当前 promoted evidence、retry、qualifier 与显式未决信息；
  新停止状态不绕过 must-cover 未搜索、promotion 不完整或 handoff 绑定检查。
- 不在内部 `explicit_gap` 中混入 inconclusive 却让旧读者按负证据消费；若保留旧外壳，所有读者必须显式
  分支并拒绝未知版本。新旧协议 checkpoint、coverage、plan、typed gaps、Writer 必须一起往返验证。

**验收**：空查询、被截断查询、未读候选、工具失败、预算耗尽、有完整范围证书、伪造证书、
旧 checkpoint 缺字段、已有 positive claim 与负结论冲突。所有路径同时核查 Candidate/strict/Verified 结果。

**测试**：`test_agentic_research_models.py`、`test_agentic_research_tools_extended.py`、
`test_agentic_graph_research_loop.py`、`test_agentic_intent_ledger.py`、`test_agentic_candidate_handoff.py`、
`test_agentic_research_checkpoint_resume.py`、`test_agentic_autonomous_method_agent.py`。

## 15. R10：研究假设可修订，作者约束不可缩水

### 15.1 当前状态与本节执行范围（2026-09-14）

R10 已进入循环，不能继续按“尚未开始/暂缓”执行。已有实现包括：来源与作者约束合同、
`propose_target_revision`/`PROPOSE_TARGET_REVISION`、harness 评估、revision journal、修订次数与
子问题额度分账、graph/agenda 同步、coverage/claims 适用性重算、checkpoint 与 handoff 绑定。
相关作者约束、目标同步、额度及不相关证据边界修复按已绑定的回归保留，不重做这些模块。

当前未完成的是这些成果通往正文的实际交付闭环。为让执行者只沿一个入口推进，本节 §15.4 同时安排
R1/R2 图与入口、R6/R7 计量、真实 Candidate 三个收口切片；各切片仍受对应原节和上位设计约束。
当前根因与证据以 §15.6 的 S3-18/19/20 复核为准；
[交付检查点复核](research_to_method_delivery_checkpoint_review_2026-09-14.md)保留为 S1/S2 修改前的依据。

不得将三条 strict partial、全部 R10 扩展、负证据 frontier 全部关闭或完整 Research 重跑，
额外设为首份 Candidate 的共同前置。仍需的 Research 根据真实 typed 缺口有界推进，不能用修订删除问题。

### 15.2 始终保留的修订合同

R4/R9 与 agenda/handoff 的 revision 约束继续适用。远端 `revision_reason` 放行删除目标的规则明确不采纳。

**落点**：`intent_compiler_v2.py`、`intent_target_proposer.py::_apply_proposal`、`research_models.py`、
`gemma_supervisor_backend.py`、`research_nodes.py`、`research_graph.py`、`intent_ledger.py`、
`research_revision_contract.py`、`research_revision_ingest.py`、`autonomous_method_agent.py` 的
planning/persistence、handoff/checkpoint 绑定。

1. 对目标记录来源类别：作者显式约束、系统推断假设、Research 子问题。旧数据无法证明来源时不能默认可删。
   作者 goal/约束文本、身份和不可缩小的覆盖目标集合独立保存；仅保留原文字而换掉全部 predicates 不算保全。
2. LLM 只提交 revision proposal：父 obligation、before/after target IDs、来源类型、精确观察/关系引用、
   原因、未决影响及预算。reviser 不能写 supported/verified/status，也不能自行选择事实 authority。
3. Harness 校验身份、来源、scope、版本、允许的 target 类型和不可删除集合；需要判断语义等价/保全的部分
   通过现有独立语义验证者与精确来源复核，proposal 与复核不能自签。来源不足时拒绝或待审。
4. “combine 被推断成 CONCAT，但代码与作者约束支持另一种 fusion”可以修订推断层；
   作者明确 concat/正负样本/顺序/条件不能被替换成 generic COMPUTE 规避覆盖。
5. 新子问题具有 parent provenance 和独立预算，不能替代父 must-cover 或自动增加已经完成的覆盖分母。
   入口选择仍满足现有 typed ownership 证明，不能仅以一个观察过的 CALLS span 和解释授权整条方法路径。
6. Revision journal、agenda、intent graph、coverage、claims 适用性、promotion/handoff/retry、checkpoint 和
   authoring plan 在同一 revision 下原子绑定，所有变化对象重算摘要，旧事实在新目标下重新评估适用性。
   resume 不重复应用同一 revision，旧 handoff 不得继续被新目标使用。

### 15.3 S1/S2 修改前的反例与工作起点（历史对照）

本小节描述早期交付检查点，不是 S3-20 的现状。旧反例用于保持回归，当前任务从 §15.6 开始；
不能因这里保留“必须修复”的历史表述，再次重做已消费的 S1/S2 改动。

从 `/tmp/c2p-nodec-ebcar-unified-20260913-205759` 的完整输入开始复核；冻结 Run E 作为原始观察保留。
这次回放已经携带 Candidate handoff，并跨过前两处入口阻塞，不应再次从缺 handoff 的第一轮开始。

| 已观察事实 | 对执行的约束 |
|---|---|
| replay 的旧 `behavior_graph_v1.json` 与 Run E 字节相同；offline 则传 `behavior_graph=None` | 先统一实际图来源及派生身份，不能将离线重建 pass 当成 replay 已消费 |
| 两处未知路径仍含 `path_polarity_conflict`；resolver 的 `config_bindings=[]`、`explicit_status=unknown` | 当前直接错误不靠补配置值解决；三条 strict partial 单独记录 |
| 相同其余输入下重建图：125/185 → 157/217 operations，各新增 32、删除 0，两机制完整性通过 | 这是修复方向对照，不是生产接线或完整 Candidate 已通过 |
| 普通 if/else 已修；嵌套 if 冲突 2、elif 冲突 1、return 后仍有顺序边 1 | S1 必须补齐既定分支回归，保留真正矛盾的拒绝行为 |
| 每次准入失败前先跑 7 次 draft planner 和 30 次 semantic verifier | 确定性输入/图/准入预检要在这批调用前执行，后续内容门仍保留 |
| 提案 caller 在最多 1 次/run input 400 的边界探针中发送 3 次、测量 735；损坏/写入失败仍发送 | S2 必须测试累计预算与异常路径，不能只验正常 tally 落盘 |
| 新配置需求按键最后一段匹配，`other.cfg.mode` 能消除 `self.cfg.mode` 的需求 | 进入新 Research 前修确切身份匹配；不能据旧图误诊增加一刀切实际配置前置 |

独立证据：[results.json](../.tmp/c2p-delivery-review-20260914/results.json)、
[graph-input-control.json](../.tmp/c2p-delivery-review-20260914/graph-input-control.json)、
[evidence-index.json](../.tmp/c2p-delivery-review-20260914/evidence-index.json)。本轮 50 项相关测试通过，
上述反例仍成立；不以测试总数代替这些场景的验收。

### 15.4 分片合同：S1 → S2 → S3（当前执行 S3）

S1 的当前图/入口/预检、S2 的累计账本/发送/恢复已有实现与实际消费证据。
以下保留原验收合同；当前剩余任务、失败样本和执行顺序见 §15.6，不能将 B 整体记为完全校准。

**S1：让实际入口消费当前图，并前移确定性预检。**

负责范围：`python_behavior_adapter.py`、`mechanism_context_compiler.py` 的必要消费约束、
`scripts/run_authoring_replay.py`、`publication_method_writer.py`、
`scripts/run_unified_ten_project_offline_matrix.py` 及现有源码/派生身份合同。组织在同一个有界交付切片内：

配置需求身份修复限于 `research_nodes.py` 与必要的 `research_supervisor.py` 参数接线，不借此扩展 Research 策略。

1. offline 与 replay/Writer 复用相同的冻结输入准备、图派生和 Candidate 确定性准入路径。
   历史 Research 图保留为观察，派生当前图记录 snapshot/tree、source manifest、producer/code-state、
   输入/输出图 digest 与 operation 集合差异。按现有重建/修订合同绑定消费者，不能偷偷传 None、
   删除旧图文件或过滤 operation 作为验收捷径。图派生不授权修改作者目标、facts 或 claims。
2. 修分支臂的完整祖先身份与正确汇合；嵌套 if/elif 不能跨互斥臂传播，return 后不能制造顺序执行。
   保留真正正负 typed 边矛盾、缺少支配证明、跨 owner/路径等失败；不扩成无界控制流重构。
3. 在需要模型的 argument brief/facet 重建之前完成可确定的输入身份、Candidate handoff、源码和图预检。
   依赖新生成内容的门在后续真实阶段继续执行；预检与消费必须绑定同一准备结果，避免再次各自重建。
4. 对新增配置需求仅按原 typed target/qualifier 的实际需要产生请求，按确切访问、scope 与来源解除。
   “可带条件支持”与“必须证明实际选择”分开；不得因错误根因统一强制所有分支证明实际配置值，
   也不得用另一对象的同名键消除缺口。

S1 必交产物：相同第三次回放输入下，实际入口与 offline 的图/上下文输入 digest 对照、operation
增删解释、Candidate 与 strict 分列的各阶段准入、预检模型调用为 0 的证据。正常例不再含当前两处
伪冲突；缺 handoff、坏源码/身份、不兼容历史图、真实条件矛盾等反例在模型发送前明确拒绝，或依现有
可信派生合同重建后重验。作者约束、必需 facts/claims/details 不得缩水。只有矩阵 pass 不算 S1 完成。

**S2：把非页面模型调用接入同一 run 预算权威，闭合发送和恢复。**

负责范围：`proposal_call_accounting.py`、`narrative_organization_proposal.py`、
`unified_invocation_ledger.py`、`unified_context_compiler.py`、必要的 budget model/profile 字段、
Writer 与 replay 的实际调用入口。明确采用纳入统一 run 预算的方向；单独 tally/summary 展示不作为替代。

1. 复用统一预算权威。现有页面 invocation 不能表达的提案/前置调用，作有界调用身份合同扩展，
   记录角色、用途、run/revision/envelope/model/request/attempt 绑定；保留四角色兼容性。
   不伪造 page/workset，不另建与 run 总账互不知情的权威账本，也不再停在“需要另选路线”。
2. 发送前同时检查单请求 cap、累计 role calls、run 已花费与未结算预留、下一请求预留；retry/resume
   不能重置额度，未知原计划/旧 started 不能按 0 计。authoring 范围内的前置 planner/verifier、
   组织提案与各正文 phase 都应有适用预算与可对账的范围，不能遗漏已经发生的 37 次前置调用。
3. started 在发送前原子持久化，写入失败阻止该请求；损坏/缺失且应存在的恢复记录不得退回空账本。
   完成/失败/发送结果未知分别结算或保留预留，恢复时校验身份与完整性。未发送的拒绝记录不冒称真实模型费用。
4. 真实请求计量覆盖 system/user 包装、payload、schema 和模型上下文。tokenizer 可用时记录真实身份
   并校准；按 §11.1 使用保守估算时必须由冻结协议明确声明估算方法/单位/余量，不能冒充真实 tokenizer。
   envelope 声明 model tokenizer 却未提供时不得发送；当前 8006 profile 的四角色不能自动当成提案有预算。
5. 不可用的可选组织提案走 §12.2 既有明确回退合同，记录未请求/拒绝原因与模型调用 0，plan 验证仍执行。
   这可作为合法运行状态，但不能把该功能或提案 run 并账记为已完成；启用时仍须满足全部预算边界。

S2 必验反例：累计调用超额、总 input 超额、未声明/半声明角色、tokenizer 缺失、started 写失败、
持久文件损坏、开始后中断再恢复、跨 revision 的旧额度、其他角色/模型/请求身份混用。
用实际 profile 或其明确冻结的合法修订验证，不能只用具备所有字段的理想 envelope 测试。各拒绝场景
应在假 transport 观察到 0 次发送；正常场景额度守恒、未结算预留可恢复。相应全量静态在集成节点执行一次。

**S3：当前主链 authoring，取得完整正文（执行中）。**

S3 已实际运行至 S3-20；下一轮整链之前先完成 §15.6 的小范围协议验收与预算收口。
之后按 §16.3 的既有授权与准入条件执行，使用新输出目录和绑定当前代码的真实协议。
以 Formalizer 有效产出、Writer 实质段落、完整 Candidate 及质量/反向验证结果逐级记录。
三条 strict partial 不冒充已解决，最终 Verified/公式/作者约束/措辞/完整性门保持。

若出现新下游失败，冻结该请求、响应、当前计划和第一失败码，按所属阶段有界修复，沿有效 checkpoint
及派生身份恢复；不无变化地再次重算全部前置模型调用。确认真实 Research 缺口后才运行有独立范围、
结束条件与预算的补证；当前不先要求选择“完整 Research 重跑还是配置续跑”。首份完整 Candidate
之后再按原定矩阵/质量计划扩大，单机制 smoke 或一个局部 section 不算该节点完成。

### 15.5 验证和交付记录

原 R10 回归继续保留：允许推断假设修正；拒绝删除作者显式约束、仅填 reason、无关/未观察 span、
错误 parent、伪造 revision、预算耗尽及重复 resume；目标修订不能凭空变 supported，不用缩水分母记增益。

按改动选择已存在的相关文件扩展测试：`tests/test_agentic_research_revision_contract.py`、
`tests/test_agentic_revision_proposal_loop.py`、`tests/test_agentic_branch_control_relations.py`、
`tests/test_agentic_branch_configuration_requirements.py`、`tests/test_agentic_mechanism_evidence_closure.py`、
`tests/test_agentic_mechanism_detail_compiler.py`、`tests/test_agentic_proposal_call_accounting.py`、
`tests/test_agentic_replay_execution_record.py`、`tests/test_agentic_authoring_context_handoff.py`、
`tests/test_agentic_publication_method_writer_unified.py`、`tests/test_agentic_unified_ten_project_offline_matrix.py`，
以及受影响的 checkpoint/handoff/预算套件。新增场景要进入真实 producer→consumer 入口，不只测试字段相加。

每片在新目录保存执行前后 code-state、输入/输出摘要、精确命令、exit、对照结果和剩余失败。
更新 `.agent/implementation.md` 与本节状态；不覆盖本轮或历史复核的结果文件。每次交付明确报告：
生产入口消费了什么变化、哪个当前阻塞消失、增加了哪个产品产物。没有正文时如实保持 0，
局部“代码接受”不能升级成 A/B/C 整体完成、Verified、D5、默认切换或发布。

### 15.6 S3-20 终态复核与下一步执行（2026-09-14）

**最新操作入口：§15.6.8（合同修复后的单页真实验收结果）。** §15.6.7 所列的离线验证、
重新 prepare 与一次有变更依据的同页 live 已完成：两次真实发送、内容拒绝、零提交。当前
标题表示恢复和调用参数的算术误判已消失；剩余阻塞是 required atom 的内容/绑定闭合，不得
重复当前 primary/repair 或无提交 resume。
下方记录按各自时点保留；局部绑定通过不等于生产统一入口提交。

**判断：有入口和调度进展，但还没有内容交付闭环。停止无变化的整轮重跑；先让失败请求产生有效产物。**
本节替代此前以旧图、Research 全量补证或尾逗号为当前首要阻塞的执行顺序。不更换总体架构，不降低门。

#### 15.6.1 已确认的产物、代码问题与证据边界

本次读取 `/tmp/c2p-unified-repair-20260914-s3-codex-{18,19,20}` 及当前 dirty worktree，
采用追加的独立复核目录，不修改 run 的账本、终态或响应。S3-20 在 2026-09-14 12:40:43（北京时间）
写入预算失败终态；用户此前描述的是较早的中途状态。
工作区还保存了[失败样本包](../.tmp/c2p-s3-review-20260914/failure-samples.json)：八个空/标题 Writer 页的
技术输入、两次响应与 receipt，以及一个 Formalizer 失败页和计划/预算。它是诊断子集，不能代替完整
Research authority 或已认证的 resume bundle；未保存过的 Formalizer 原始响应明确记为缺失。

| 层级 | S3-20 实际结果 | 执行含义 |
|---|---|---|
| 预检/Research admission | 当前图来源为 `current_verified_repository_source`，零模型预检 pass，handoff eligible | 旧图/配置补证不再是本次直接入口阻塞；strict partial 仍单列 |
| Formalizer | 34 main + 32 repair，66 receipts 均 `failed`，0 accepted packages | `admission_status=pass`、`assertion_failures=[]` 仅证明准入/调用约束，不证明公式成功 |
| Writer | 18 primary + 11 repair，共 29 次发送；5 页两次均空 | 空流 repair 接线已生效，未改善这五页的响应 |
| Writer 文本形状 | 每页取最后响应：5 空、3 仅标题、10 含非标题文本 | 不是 13 个已验收页面；其中一页 primary 有正文、repair 退化为标题，须核对实际 commit 选择 |
| Realizer | 15 primary 已发送，另 3 primary 发送前预算拒绝；3 次 witness repair 均成功，15/18 页完成 | 保留已有 witness 修复；不继续围绕尾逗号扩大改动 |
| 终态/交付 | 116 completed / 116 started；113 次发送；execution record、terminal event、usage summary 已存在，exit 2 | 无 Candidate、无 structural exit；不能继续写“运行仅被中断、无 execution record” |

S3-18 与 S3-20 的 66 个 Formalizer 响应摘要、18 个 Writer primary 响应摘要分别全部相同。
这证明重复整轮没有改善这些请求；不据此推断使用缓存（summary 的 cached calls 为 0）。

代码层已确认四类问题：

1. **Formalizer 的响应合同未写完整，输入还重复一份。**
   `formalization_agent.py::_run_one` 与 `unified_context_compiler.py::consumer_response_json_schema`
   各有一份 schema；`results.items` 列出六个 required 字段，却没有定义其 properties/类型或封闭对象。
   当前 system prompt 又是 user payload 的完整 JSON 副本，没有独立说明如何输出并绑定 results。
   这是确定的合同缺口；旧 run 未保存失败的原始 Formalizer 响应，不能声称已证明 backend 具体生成了什么。
2. **空流诊断在最需要它时丢失。** `llm/client.py` 在空 content 的 finish event 上立即抛错，
   后续 usage event 不会被读取；错误被转为空 `LLMResponse` 时 finish reason/usage 也未保留。
   本次假 SSE（reasoning → finish=length → usage）重现只读前两个事件。它是代码反例，
   不是 S3-20 已确认为 length/reasoning 耗尽的证据。Writer 失败 fragments 只有空文本和错误码，
   Formalizer 失败只有 response digest；目前不足以判断那五页究竟是长度、思考、协议还是 guided decoding 问题。
3. **声明的 retry reserve 未成为发送限制，未来 primary 没受全局保护。**
   Writer primary/repair 分账修复只保证本阶段 primary 的局部检查；repair 分支计算了 remaining，
   但超额条件又排除了 repair。全局 `check_run_budget_before_send` 使用 spent + pending，
   不保护尚未 started 的后续 phase primary。Writer repair 扣账 381,539 > reserve 200,000；
   Writer 总扣账 954,369 > plan reservation 838,504。随后三个 Realizer primary 被全局门诚实拒绝。
   微型反例：已花 70、后续 primary 20、当前 repair 20、总额 100，当前 guard 返回允许，
   尽管要完成已计划 primary 至少需要 110。不能以调大总 cap 掩盖这个调度问题。
4. **receipt 的 `complete` 早于正文验收。** `publication_method_writer.py::_capturing_writer_caller`
   仅以 response text 非空且无 blocked reason，将该 invocation 的全部 task IDs 写为 succeeded。
   只含标题的 JSON 也符合此条件。后续确有 paragraph/结构门，不能据此说 Candidate 已被错误放行；
   但聚合报告、修复选择和 resume 都必须区分 transport completion 与内容验收。

计量也尚未闭合：本 run 的账本估算 input 合计 1,990,033；provider summary 已知 input 为
2,179,336、output 为 110,194、total 为 2,289,530，且还有 15 次调用缺 usage。
因此“总花费”只是已知下界，`conservative_utf8_bytes_div_4` 未被当前输入证明保守。
`unknown` role 的 18 次 usage 与 Realizer 数量相符，但仍须以 invocation/attempt 身份对账，不能靠数量绑定。

#### 15.6.2 执行顺序与退出条件

**T1：先补能诊断失败的请求/响应记录，并修 Formalizer 的完整合同。**

- 负责 `llm/client.py`、`llm/generation_trace.py`、`agentic/formalization_agent.py`、
  `agentic/unified_context_compiler.py` 及其真实发送入口。复用现有 invocation ledger，
  把脱敏请求/实际 schema/模型配置摘要、原始 content 或有界片段及全文摘要、finish reason、
  reasoning 字符数、usage、异常码绑定到 invocation/attempt；失败也要保存，不能只在 run 结束时汇总。
  不保存凭据；未发送的拒绝与已发送但缺 usage 的失败分开记录，后者保守保留未结算费用。
- 在现有超时/字节界限内消费 finish 后的 terminal usage；没有 usage 时如实标 unknown，
  不等待无限流、不把 reasoning 转成正文、不把空响应按 JSON 补尾修复。
- Formalizer 由唯一的 typed response 定义生成 provider schema 与解析合同，明确六个字段及
  `symbol_definitions` 的合法形状；结果 ID 必须属于本次 obligation 闭集且恰好覆盖应答集合。
  不按返回顺序补 ID、不自动补公式正文。system prompt 写清任务，完整证据 payload 只传一份。
  schema/prompt 变化必须重算 request/plan digest 与预算，不能复用旧摘要。
- 先用完整真实页面构造请求并做零模型 schema/解析/未知 ID/遗漏/重复 ID 检查。
  然后按已冻结的小范围协议试一个 main 和一个 repair；退出要求是至少一个**经来源/条件/公式验证的 package**，
  或有明确依据的终态 disposition，不能用调用数或 assertion pass 结项。
  required 与 preferred 按原规则区分；不为了本项验收把所有 preferred 公式升级为 Candidate 必须成功，
  也不删义务或伪装 `formalizer_empty` 为公式完成。

**T2：针对五个空 Writer 页面和三个标题页面，闭合响应到有效段落的事务。**

- 负责 `llm/section_writer.py`、`agentic/publication_method_writer.py` 与既有 paragraph transaction /
  receipt / resume 接口。先选一个空页和一个标题页，以相同真实 payload/schema 从实际入口做微测，
  依据 T1 记录区分 length、reasoning-only、空 stop、schema/解码、连接错误；每次只改变一个协议变量。
  禁止凭错误码断言是模型随机性、直接切模型、无限增大 max tokens 或增加通用重试轮数。
- 有非空残片的表示修复与空 content 的 owner regeneration 分开；空 content 没有可供 Harness 补齐的正文。
  保留一次 bounded Writer repair，但当 primary 与 repair 同签名失败时停止该页，不继续碰运气。
- 使用现有 paragraph 内容/绑定评估器给出独立的 content acceptance，再决定 succeeded task IDs 和
  可复用产物。transport receipt 可以先落盘；内容结果以绑定它的追加记录表达，不改写历史 receipt。
  已发布的 `complete` 旧记录也要经正文门重验才能用于 resume。
- 复现有正文 primary → 标题 repair 的样本，验证实际 commit 保留通过门的 incumbent；
  若 primary 本身未过内容门，保留诊断但继续标 incomplete，不能仅因更长就把它升级为有效正文。
  标题、空对象、纯标点不能作成功段落；未知 ID、条件/公式丢失仍 fail-closed。
- 退出要求：五个空页、三个标题页分别有正文/绑定验收或明确未解决原因；不能只写“18 primary 已发送”。
  不用新写的测试常量替换真实失败页的输入、响应与页级闭集。

**T3：在下一次整链前，补跨 phase 预算保护和真实计量。**

- 负责 `unified_invocation_ledger.py`、`unified_context_compiler.py`、三个 consumer 发送边界与当前 profile。
  明确 planned、future-primary reserved、pending、measured、spent、unsettled 的含义；reserve 不是已经花费。
  在全局 cap 内保护未发送 primary，repair 只能消费明确的剩余额度；repair reserve 的耗尽必须在发送前拒绝。
  不能再次仅在 Writer primary 的局部条件中排除 repair 费用，或把 future reserve 从调度可行性检查中移除。
- 从现有计划预留后续 phase 的主请求上界，后续编译有变化则做有界 replan 并保留 lineage。
  若额度无法覆盖完整 primary + 所需 repair，在昂贵调用前给出可解释的不足报告；不默认释放未结算 start。
- 使用实际模型 tokenizer 或已验证的保守上界计量真实 wire messages/schema/模板；将 provider usage 按
  invocation/attempt 持久化并结算。计量规则/单位变更时明确处理旧费用和新 plan，不能混加后写成“真实 token”。
  若经重新测量确需增加 run cap，形成绑定新协议的具体预算表，再按既有授权范围执行。
- 必验真实形状边界：Writer 18 primary + 11 repair 后仍保留 Realizer primary；repair reserve 耗尽；
  多 phase/跨 revision/未结算 start；失败但已发送且缺 usage；原始 guard 的 70+20+20>100 反例。
  同时保留已有损坏、写入失败、role/model/run 身份拒绝测试；不扩大成另一轮全仓架构重写。

**T4：有验证的恢复与一次完整 Candidate 交付。**

- 冻结 S3-20，不往旧目录补写伪终态。先验证真实入口能按代码/输入/plan/schema/model/attempt 身份
  复用已验收页及有效 sibling；`--resume` 的 section 选择不等于已证明跨新目录页级复用。
  prompt/schema/输入变化导致身份不兼容时显式标 invalidated 并重算依赖，不拷贝旧 receipt 冒充新请求。
- 保留成本 lineage；失败页有限修复与未发送页继续运行，不能每个失败都从 66 次 Formalizer 开始重算。
  未实现或未验证的恢复路径先离线验，不承诺“直接 resume 即可”。
- T1/T2 的首次微测建议总计至多 6 次调用（两个 Formalizer 尝试、两个 Writer 样本各主请求+一次 repair），
  正式记录各请求额度与出口；该范围只是诊断样本，不缩小全量验收分母。
  微测和全量均遵守 §16.3 的 runtime 身份、健康状态、队列与新目录要求。
- 只有协议缺陷已有修复证据、完整 primary 预算可行、内容验收与恢复可区分后，才执行下一轮完整 authoring。
  结束时同时交付 `execution_record.json`、`publication_candidate_method.md`、
  `authoring_structural_exit_v1.json`、内容/质量/反向验证报告；若失败则保存真实第一失败及全部已验收阶段产物。
  Candidate、Verified 分别报告，不以任意非空文件、Realizer 的独立 draft 或测试总数代替正文交付。

#### 15.6.3 本次复核验证与记录要求

- `python .tmp/c2p-s3-review-20260914/review.py`：exit 0，模型调用 0，扫描 frozen artifacts 并执行
  假 SSE、schema/prompt 与 future-primary 预算反例；结果及 SHA-256 索引保存在同目录。
- `python -m pytest -q tests/test_llm_runtime.py -k stream tests/test_llm_section_writer.py -k 'stream' -p no:randomly`：
  exit 0，6 passed、115 deselected；已有测试通过不覆盖本次全部反例。
- 本轮没有重新跑全量静态；用户报告的 131 项与此前 3479 passed / 3 skipped 是历史验证，
  不能写为这次复核的新结果。实现变更后按 T1–T3 范围验证，完整整链前再做一次适用的集成静态检查。
- 每次推进至少报告：Formalizer accepted/disposition、Writer 已验收正文页、Realizer 完成页、
  Candidate/structural exit 是否存在、模型调用与完整/缺测费用、第一失败及预算终态。
本节是统一执行入口；不再新增一套平行计划，也不重跑无变化的 S1/R10/完整 Research。

**本节执行更新（2026-09-14）**：T1 已按当前源码重建 plan 后通过一个真实 Formalizer main，
取得 1 个来源/条件/公式校验通过的 package（1 main、0 repair、1 receipt）。旧 S3-20 plan 在当前
入口被 digest 检查拒绝且实际发送 0 次。冻结 S3-20 的 Writer 仍确认 5 个空流页、3 个标题-only
页和 10 个含非标题文本页；现有空/标题夹具已覆盖 rejected primary→bounded accepted repair，
且新增 provider-free 的真实冻结页回放确认两个 bounded repair 的 `page_commit_count=0`、
`resume_eligible_page_ids=[]`；但真实八页尚未重新发送并验收，故 T2 不结项。统一 ledger 另修正了持久计划读取时丢失
`is_repair` 的问题并补回归；旧 run 当前只能报告 `provider_usage_status=partial`（113 个 receipt
缺 provider usage、request accounting 1,990,033 input tokens），T3 真实计量不结项。当前不启动完整
Candidate，S3-20 的旧 execution record 与 Realizer witness 修复保留为历史证据。尝试按微测上限补 1
次真实 Writer repair 前，8006 preflight 全部 connection refused；未启动服务、未发送新 provider
request，故该部分仍待 runtime 恢复后按同一 fresh output 继续。runtime 等待期间已补回归：缺失
provider usage 的已发送 receipt 保留 request accounting 并标记 `partial`，不按零费用；未来
primary/repair 预留边界回归继续通过。

**本节执行补充（2026-09-14，Writer 失败输出合同）**：为防止非空但未提交的 repair 被最终
incumbent 回调覆盖，`section_writer.py` 现在把每个 transport/content attempt 绑定到其
content sidecar；标题-only、无进展或事务拒绝的 bounded repair 也写入 rejected sidecar。
`publication_method_writer.py` 按尚无 sidecar 的 attempt 绑定回调，因此 primary/repair 复用同一
response hash 时不会把 primary 结果写到 repair receipt，最终 accepted callback 也不会用 incumbent
覆盖已拒绝的 repair。新增统一 Writer 真实入口回归：primary 为空、repair 标题-only 时两个 sidecar
均 rejected、`resume_eligible=false`，`build_resume_plan` 返回 `execute` 而非 `reuse`。
该补充只加强失败记录与 resume 闸门，不放宽内容/绑定门，也未触碰 S3-20 或发送 live 请求。

新增验证：

- `python -m pytest -q tests/test_agentic_unified_context_compiler.py tests/test_agentic_publication_method_writer_unified.py tests/test_llm_runtime.py tests/test_llm_section_writer.py tests/test_r6_portability_and_budget_hygiene.py tests/test_agentic_formalization_guards.py tests/test_agentic_replay_execution_record.py tests/test_agentic_runner.py -p no:randomly --basetemp=/tmp/c2p-contract-final-focused-20260914-r3`：**258 passed**。
- `python -m pytest -q tests/test_agentic_unified_context_compiler.py -k 'future_primary_reservation_excludes_repairs or missing_provider_usage_without_zeroing_spend or run_reservation_is_debited_by_retries_and_resume' -p no:randomly --basetemp=/tmp/c2p-budget-boundary-20260914-r3`：**3 passed**。
- `python -m compileall -q src tests .tmp/c2p-s3-t2-replay-20260914 .tmp/c2p-s3-t2-live-repair-20260914`、`git diff --check`：exit 0。

T2 的真实空/标题页仍未取得新的 provider 内容，T3 的旧 run provider usage 仍为 partial，故不
升级 T2/T3，不启动完整 Candidate；8006 当前仍需恢复后再执行既有 fresh live probe。

**本节执行补充（2026-09-14，T2 受控 live 样本）**：sandbox 内的 Python/`curl` 预检曾因本地
网络权限失败；只读 escalated preflight 随后确认 `8006 /health`、`/v1/models`、metrics 均 200，
模型为 `qwen38-27b-nvfp4`，context 131072，队列/KV/preemption 均为 0。未启动服务。

按同一 frozen S3-20 page projection/schema 完成两个独立 fresh probe，每个只发送 1 次真实 repair，
并保留 frozen primary，不进入完整 authoring：

- 空页：[live result r3](/tmp/c2p-s3-t2-live-repair-20260914-r3/writer_repair_result.json)；真实
  repair `finish_reason=stop`、`provider_finish_reason=stop`、usage 为 50,220 prompt / 1,192
  completion，流已读到 usage；返回退化为 heading-only，内容/目标门拒绝，`repair_commits=0`、页
  incomplete。
- 标题页：[live result r5](/tmp/c2p-s3-t2-live-repair-20260914-r5/writer_repair_result.json)；真实
  repair usage 为 68,831 prompt / 1,302 completion，返回约 952 字正文，但缺 required detail
  witness，`required_target_contract` 拒绝，`repair_commits=0`、页 incomplete。

中途 r4 曾在修正 frozen title primary 的 blocked 标记前发送 1 次 provider request，已保留但不作为
验收证据；修正后的 r5 才是标题页有效样本。运行时 post-check 显示 running/waiting/KV/preemption
均为 0。这个结果关闭了“空流一定是无 usage/连接失败”的猜测，但没有关闭 T2：两个样本都没有
产生可复用正文页。另补回归锁定低层入口中带 typed content failure 的非空 repair 不计入
`writer_repair_commits`；当前聚焦集合为 **259 passed**，`compileall`、`git diff --check` 通过。

T3 的旧 S3-20 provider usage 仍为 partial，跨阶段真实计量尚未完成；Candidate/structural exit/Verified
仍不存在，故不执行完整 authoring。

**本节后续校正（2026-09-14，T2 deterministic revalidation / T3 guard）**：在上述 live probe 之后，
没有再次调用 provider，也没有改写 frozen r3/r5/r6 结果。针对实际 r6 标题响应，以当前代码离线重跑
绑定与段落事务验收：24 个 required atom witness 全部绑定，推导出
`detail:mech_sym:9773c5add7af1f92:13`，无失败项，事务有效，输出 721 字符；原始 r6 live
结果仍保留为“当时入口下未提交”的诊断样本，未被伪升级为 live commit。此校正同时固定了
V3 `detail_id` 保留、closed exact-excerpt 的受限语义回退、条件 clause 锚点，以及“required
atoms 全部完成时可推导 detail witness”的一致性。

本片还增加预算边界回归：repair 不能消耗跨阶段预留的 future primary，且超过 retry reserve
必须在发送前拒绝；缺失 provider usage 仍保持 conservative/partial，不得清零或伪造精确计量。
当前聚焦集合为 **264 passed**，`compileall` 与 `git diff --check` 通过。旧 S3-20 仍为
partial（113 个 usage 缺失；当前 ledger 的保守计量为 1,990,033 input tokens），而历史
Writer repair 已实际花费 381,539，超过其 200,000 声明 reserve；legacy plans 也没有可供恢复
的 future-primary reservation。故 profile 的 2,000,000 总上限与 200,000 retry reserve 尚未
被下一轮完整 plan 的真实计量证明，未修改该配置、未启动完整 authoring，Candidate 仍不存在。

#### 15.6.4 S3.6 独立复核纠偏（2026-09-14）

本次按当前代码及新增 r3–r10 产物复核，模型请求 0，未修改生产代码或历史 run。
完整依据与复现脚本见[独立复核](../.tmp/c2p-s36-independent-review-20260914/review.md)，
[反例结果](../.tmp/c2p-s36-independent-review-20260914/probe-result.json)绑定代码 SHA-256。

1. **P1 先修错误绑定，停止降低阈值。** 新 `_exact_excerpt_overlap` 把少量词汇重叠当作原语义
   锚点失败后的替代授权。闭集源码要求 `embeddings + bias + residual`，正文却写三项相乘，
   当前 Binder/assessor 仍 `valid=true` 并推导 detail 完整；仅在探针内禁用新增回退则拒绝。
   真实 r6 页也把“保持 batch/sequence dimensions”绑定为加法 operation，改成相乘后仍获得
   24 witnesses、无失败。收紧 atom/detail 的语义和运算验收，无法证明时返回 owning Agent；
   保留 `detail_id` 与完整且有效的 required atom 集合推导，不能用公共摘录的词汇重叠填满集合。
2. **P2 微测必须覆盖实际统一入口。** 当前 live 脚本直调低层 Writer，缺少统一 capturing
   caller、预算、content receipt、resume 及生产 transaction assessor。冻结 primary 又带旧
   `_p1__f1`，当前页要求 `_p1`，首先失败于 paragraph 身份。独立回放实际 r6 响应，局部
   normalization 虽通过，整个低层 Writer 协议仍 commit 0 / incomplete。改用
   `run_publication_method_writer`，在传输边界注入响应并使用当前 plan/page/schema；旧身份
   显式 invalidated。先验证合法 repair 提交一次、非法 repair 零提交、同身份 resume 零发送。
3. **P2 校准和微测总账不能用提额/换目录代替。** 可见 Writer 样本有 7 次 provider usage，
   已知 prompt 444,666 / completion 8,432；r7 缺 key、未发送也被脚本记成一次 provider call。
   r3/r8、r6/r9 的请求和响应摘要分别相同，停止重复。当前 profile 已是 2,500,000 总额、
   Writer 400,000 / Realizer 100,000 reserve，仍属 provisional；生产计量默认仍为 UTF-8/4。
   用实际 tokenizer/wire 输入校准后给出完整 primary、repair、future、spent、unsettled 表；
   区分 client 调用、实际发送、usage 与内容 commit，对整个微测阶段累计设限。

Formalizer 封闭 schema、失败流式诊断、空/标题拒绝、receipt 分层与预算保护保留；T1 有一个
经严格 receipt 摘要链校验的真实 accepted package，不能整体撤销。上述 P1/P2 通过后才继续
一次完整 authoring；本次没有发现完整 Candidate/Verified 已被错误发布的证据。

本次相关静态 **173 passed**，但上述新增反例仍成立；不能用历史 264 或当前测试数覆盖退化。
精确命令及日志见独立复核。不重开 S1/R10，不重跑无变化 Research。

#### 15.6.5 操作单：S3.7 → 单页真实 Writer 验收

本节回应“按什么操作”。范围是完成一个真实页面的发送、内容提交及恢复闭环，不重跑
Research、不启动完整 authoring。2026-09-14 本次只核对代码/预算表并离线执行三个错误
加法反例，均被拒绝；178 passed 是执行者报告，本次没有重复运行该测试集合或发送模型请求。
校准文件已另存为[工作区证据副本](../.tmp/c2p-s37-calibration-evidence-20260914/budget-table.json)，
[摘要索引](../.tmp/c2p-s37-calibration-evidence-20260914/source-index.json)保留 `/tmp` 来源与文件 SHA-256。

**先说明现成入口的限制。** `scripts/run_authoring_replay.py --resume` 接收 section id，
不能充当单页选择器；当前没有已验收的单页统一入口 CLI。
`.tmp/c2p-s3-t2-live-repair-20260914/live_repair.py` 仍是低层诊断脚本，不能承担本节验收。
因此执行者先交付以下两项代码接线和可运行命令，再由操作者执行 live。

**步骤 1：真实计量接入生产请求边界（零生成调用）。**

- 修改 `agentic/unified_context_compiler.py` 的计量/plan 接口及
  `agentic/publication_method_writer.py` 的 Writer capturing caller，复用统一 ledger。
  plan 与发送前使用同一模型/tokenizer/模板身份；对实际 wire messages 和模板参数计量，
  序列化复用 `llm/client.py` 的真实规则。不能只把 meter 名称改成 `model_tokenizer`，
  也不能用现有 `tokenizer.encode(str(dict))` 当作 chat 请求计量。
- provider prompt tokens、schema/scaffolding 规划余量分别列明，避免把诊断 schema 数字
  不加说明地重复计入 provider usage。每个请求发送前校验 input、output/thinking reserve、
  safety margin 和 run/repair 总额，记录 invocation/attempt、request digest 与 meter identity。
- tokenizer 不可用、身份变化或预算不足时实际发送 0；usage 缺失保留未结算估值并标 partial。
  本步不得回退到已被证明低估的 UTF-8/4 后继续发包。

**步骤 2：交付单页统一入口及离线 prepare/resume 验证（零生成调用）。**

- 选定原空页
  `page:02a75f6a1ef46816946276263439296fa93593e0f32c30694b497c72e96d484f`，
  所属 section `MA-REV-mech_sym-f6cf5bdfe2ae16f0`。冻结来源为
  `/tmp/c2p-unified-repair-20260914-s3-codex-20`；校准盘点的当前 primary 为 49,678 chat tokens，
  这是选择依据，接线后还要按最终请求重测。
- 用当前代码重建诊断计划、request/schema/paragraph 闭集，保留该页全部 technical payload、
  required detail/atom 和证据。记录父 archive/workset/plan 与新诊断计划 lineage。其余 17 页
  在全量清单中仍是未执行，不能删除后声称全量通过；旧 `_p1__f1` 与当前 `_p1` 不兼容时
  显式 invalidated，不重命名旧 receipt 或把它当作当前 primary。
- 单页执行必须复用 `run_publication_method_writer` 实际使用的 Writer capturing caller、
  transaction assessor、content sidecar、repair 选择和 `build_resume_plan`；可以增加显式
  诊断范围/阶段停止点，但不得复制另一套宽松验收器。诊断完成即停止，不触发其他页面、
  Formalizer/Realizer/Editor/Research 的生成，也不发布整篇 Candidate/Verified。
- 在上述共享入口完成合法 repair 提交一次、非法 repair 零提交、合法同身份 resume 零发送
  三项离线场景。允许在传输边界注入有标记的响应夹具；夹具不充当真实 provider 成果。
- 交付一个真正存在且已验证的 prepare、live、resume 命令，写入 implementation。
  prepare 必须产生 source/plan/schema/model/meter 摘要、实际请求计量与预算判定。
  现有 CLI 没有单页参数，不得在操作记录中直接写未经实现的 `--page-id` 命令。

本次独立诊断预算按以下上界执行，最终请求超限就发送前拒绝，不修改完整 run 的 profile：

| 项目 | 单页诊断范围 |
|---|---|
| 实际生成请求 | Writer primary 1 次；仅失败且可修复时 repair 最多 1 次；合计最多 2 次 |
| client transport attempts | 每次请求 `retry_max_attempts=1`，避免一次 owner attempt 暗含多次发送 |
| 每请求 input ceiling | 60,000；primary/repair 都按步骤 1 的同一计量检查 |
| Writer repair reserve | 60,000，包含在下述 120,000 总额内，不能重复相加 |
| 诊断 run input ceiling | 120,000；与旧 run 的历史花费分别保留 lineage，不用来释放旧 pending |
| output / context | 每请求沿用最高 8,192 output，记录实际 thinking 设置和至少 1,024 margin；总需求不超过 131,072 |
| 其他角色生成 | 0；前置产物不能通过身份校验时，prepare 明确拒绝并列出缺项 |

**步骤 3：prepare 通过后运行一次 live，再验证恢复。**

1. 操作者使用新目录 `/tmp/c2p-s38-writer-live-<唯一后缀>`，按 §16.3 保存
   `/health`、`/v1/models`、`qwen38-27b-nvfp4` 身份、context 和队列/KV 状态；命令只使用
   步骤 2 实际交付的入口。不要输出凭据或改写 S3-20。
2. 发送当前 primary，符合 owning Agent 修复条件时才发送一次 repair。primary 成功就停止
   该页生成；此时如实报告“本次未发生真实 repair”。同签名失败、预算拒绝或第二次失败均停止，
   不换目录重跑同一请求。
3. 页面通过内容门时检查真实 receipt、content acceptance、提交产物均绑定同一身份；
   然后在该诊断目录、同一代码/input/plan/schema/model/meter 下运行 resume 验证，
   验收目标页 provider 新发送数为 0。失败页应 execute/invalidate，不能被缓存或 sidecar 伪装成 reuse。
4. 交付诊断结果、原始响应/finish/usage、预算终态、content sidecar 与 resume decision；
   分别列 client 调用数、实际发送数、usage 完整数、内容 commit 数。
   微测成功仅指该页；完整 authoring 仍未结项。

**步骤 4：单页闭环后完成全阶段计量，决定一次完整 authoring 的具体预算。**

18 个 Writer primary 的已知 chat input 总计 828,590；三页分别为 66,578、68,323、73,618，
样本 repair 为 68,873。60,000 是当前配置额度，不能把“超过 60,000”解释成模型 131,072
上下文不足，也不必据此先大改分页。先补当前 Formalizer、Realizer 和有界 repair 的实际
请求上界、schema/模板开销及辅助调用费用，形成完整计划表；按表决定配置调整或分页。
任何调整均重算 profile/envelope/plan 摘要，并保留 primary/future/repair/spent/unsettled 账本门。
不因单页测试成功宣称 2,500,000 run 总额已可行。

#### 15.6.6 S3.7 实际执行结果：计量已接入，单页内容门未通过（2026-09-14）

本片已按 15.6.5 的步骤 1–3 执行，未重跑 Research、未启动完整 authoring，也没有把失败页
标记为完成。新增的统一入口为
[`scripts/run_unified_single_page_writer.py`](../scripts/run_unified_single_page_writer.py)，
共享 `VllmOpenAIChatTokenizer`、生产 Writer request 构造、预算发送门、receipt/content
acceptance、repair assessor 和 `build_resume_plan`。首次 prepare 因保留完整 section 而被当前
生产入口拒绝（`p1__f1` 的 required detail 不属于目标 p6 页）；该入口随后改为只投影目标页
自己的 paragraph/义务，并在新的目录重新 prepare，未发送模型请求。

实际命令如下；第二条使用同一 prepare 目录，没有换目录重试同一失败：

```bash
python scripts/run_unified_single_page_writer.py prepare \
  --frozen-root /tmp/c2p-unified-repair-20260914-s3-codex-20 \
  --output /tmp/c2p-s3-single-page-20260914-02a75-r2 \
  --profile tests/live/profiles/qwen38_vllm_budgeted.example.env
python scripts/run_unified_single_page_writer.py live \
  --output /tmp/c2p-s3-single-page-20260914-02a75-r2 \
  --profile tests/live/profiles/qwen38_vllm_budgeted.example.env
python scripts/run_unified_single_page_writer.py resume \
  --output /tmp/c2p-s3-single-page-20260914-02a75-r2 \
  --profile tests/live/profiles/qwen38_vllm_budgeted.example.env
```

`prepare` 已通过并生成
[`prepare_result.json`](/tmp/c2p-s3-single-page-20260914-02a75-r2/prepare_result.json)：
8006 `/health`、`/v1/models`、`/metrics` 均为 200，服务身份为
`qwen38-27b-nvfp4` / context 131072；meter identity 固定为
`vllm-openai-chat-template-v1` 加模型、base URL 和 runtime identity。目标页预算 input
为 **53,931 tokens**（chat-template 计量 49,678 + schema 2,205 + wrapper 2,048），
低于 60,000；thinking 1,024、output 8,192、margin 1,024 另用于 context 判定。
预算扣账与 provider 实际 prompt usage 分列；prepare generation/provider sends 均为 0。

`live` 已产生真实页面证据，但内容门失败：

| 项目 | primary | repair |
|---|---:|---:|
| client generation call / provider send | 1 / 1 | 1 / 1 |
| 本地同一 meter 的 input | 53,931 | 55,013 |
| provider prompt / completion / total | 49,666 / 1,370 / 51,036 | 50,748 / 1,393 / 52,141 |
| finish / usage | `structured_complete`、seen | `structured_complete`、seen |
| receipt / content acceptance | 1 / rejected | 1 / rejected |

真实结果保存在
[`live_result.json`](/tmp/c2p-s3-single-page-20260914-02a75-r2/live_result.json)、
[`last_live_receipt.json`](/tmp/c2p-s3-single-page-20260914-02a75-r2/last_live_receipt.json)
及对应 invocation 目录。两次响应均未形成 content commit；repair 仍为
`writer_repair_no_progress_stops=1`，没有生成 `single_page_submission.json`，所以不执行
resume，也不产生“新增 provider sends=0”的正向恢复声明。当前可确认的是：统一入口对
resume 前置条件 fail-closed，未把 rejected sidecar 当作可复用正文。

失败原因是内容合同而非 transport/budget：模型两次都返回非空 structured response、finish 和
usage；输出 paragraph 仍把 `##` heading 与正文放在同一行，内容验收去除 heading 行后得到
非 substantive body；同时 Binder 只闭合了 required detail 10/22 的部分 atom witnesses，
完整 required target contract 未闭合。primary 与 repair 的 rejection sidecar 均保留具体失败
项和原始 response。故本页、S3.7 和完整 Candidate 均未完成；下一退出条件是修复 heading/段落
输出合同及对应的完整 witness 交付，再单独取得新的准入证据，不能重复当前 primary/repair。

#### 15.6.7 下一步：修复真实响应暴露的 Writer/Binder 合同（2026-09-14）

两次完整响应和 usage 已通过严格 receipt 摘要链读取。本轮不发送新模型请求、不改历史 run，
使用[离线对照结果](../.tmp/c2p-s38-next-step-review-20260914/inspection.json)及同目录 probe.py
定位原因，所涉代码/输入 SHA-256 均已记录。这次不是“模型没有写正文”：精确去掉已知
标题前缀后，primary/repair 分别保留 1,369/1,532 个原文字符；仅格式失败消失，detail 仍不完整。

按以下顺序实现，保留当前账本与单页计量，不重开 Research 或无变化 live：

1. **修标题合同冲突及表示恢复。**
   `authoring/writer_skill.py` 同时发出 paragraph 禁止 heading 和无条件
   `Begin with exactly '## <supplied heading>'`。paragraph transaction 模式只要求正文，
   section heading 由既有组织层装配；legacy section 模式按其合同处理。
   `llm/section_writer.py` 在内容判定前复用/抽取已有精确 heading 边界恢复能力
   （`publication_method_writer.py::_normalize_section_heading_breaks`），只允许使用已知
   planned heading 分离结构，保持每个正文词和数字不变；不能按 `#` 丢弃整行或猜测未知边界。
   回归必须覆盖两份真实粘连响应、正常 paragraph、heading-only 仍拒绝。

2. **修运算检查的适用范围，保留加法反例拒绝。**
   `publication_transaction_contract.py::_arithmetic_relation_satisfied` 当前用源码中任意
   `+` 判断整个 target 是加法。detail 22 是 `torch.zeros` 调用，`+1` 仅在 shape 参数中，
   该规则却要求整句通过顶层求和检查；13 个 required atoms 中 11 个被该检查拒绝，连其
   完整授权源码摘录作为 witness 也被拒绝。应从表达式/target 的结构区分顶层运算、调用、
   shape 子表达式和 operand，不能靠关闭全部算术门或增加项目专用字符串例外解决。
   正向覆盖合法零张量分配及 embedding 整数索引；反向保留加法→乘法、漏加数、否定加法，
   增加 zeros→ones、shape 偏移/维数变化、整数转换丢失等真实相关反例。

3. **把剩余 atom 的问题送到正确的修复者。**
   此页 detail 10 有 11 个 required atoms，detail 22 有 13 个；精确分离标题后的当前
   primary/repair 只分别绑定 4/6 个。repair 包却只列 2 个 aggregate detail，未列出每个
   缺失 atom 的类型/约束/原因。`llm/section_writer.py` 的 paragraph repair packet 应附加
   每个未闭合 atom 的源约束、已写出的候选 span 与失败原因，内部 ID 保持 sidecar；
   不能让 Writer 猜 `CALL operation` 或要求它把 `sym:…` 写进论文。
   正文确实缺事实的交给 Writer；正文已陈述而缺 metadata 的交给绑定路径。
   V2 当前明确禁用隐藏低层 Binder（`binder_caller=None`），prompt 却承诺 separate Binder。
   若需要语义 Binder，必须使用既有 V2 显式 phase/调用计划、真实计量和独立 receipt，
   只在已冻结 Writer 文本中选择 span；不能直接恢复一个无账的嵌套调用，也不能以词汇重叠
   授权事实。interface atom 仍须保留，使用已证明的 owner/source 关系完成 metadata 绑定，
   不删除它来缩小验收集合。诊断同时报告 atom 与 detail 进度；不把部分 atom 增益当完整提交。

4. **单页脚本与生产验收共用实现，再进行一次 live。**
   `scripts/run_unified_single_page_writer.py` 当前仍自行实现 `_LiveCaller`、`_assessor`、
   `_AcceptanceSink`；导入共享 ledger/模型不等于复用生产编排，其 metrics 也未包含生产
   assessor 的全部 authority/formula 维度。抽取并共用当前生产 Writer 事务/验收边界，
   用同一响应验证微测和主入口给出一致决定；不要继续在脚本里维护第二套验收规则。
   先离线回放本次两份响应：格式误判须消失，合法调用不得受顶层加法误判；剩余拒绝必须
   精确指向真实缺失内容/绑定。旧正文若仍缺事实，不强求它变成成功样本。
   新 prompt/绑定代码改变后重新 prepare，绑定新摘要并重测 primary/repair；若新增 Binder，
   先把它计入独立 phase 的预算和总调用上限。之后只做一次有变化依据的同页 live，
   成功提交才做同身份 resume；保留本次零提交状态，完整 authoring 继续等待页级与预算闭环。

本次证据还修正一个计量表述：53,931 / 55,013 是包含 schema/wrapper 的预算 input，
provider 实际 prompt 是 49,666 / 50,748；不能把两组数字均称为实际 wire input。
本轮只有离线探针和文档更新，没有重新运行完整静态或任何 live。

#### 15.6.8 合同修复离线验证与单页真实验收结果（2026-09-14）

本片按 §15.6.7 的顺序执行，未重做旧行为图、Research 或完整 authoring。先用两份冻结的
真实响应做零模型验证，再在全新目录重新 prepare，并只发送一次 `1 primary + 1 repair`。
没有提交成功，不执行 resume；因此本片不能把该页记为完成，也不能宣称已有 Candidate。

**代码交付。** 已在当前生产路径完成以下收口：

- `authoring/writer_skill.py` 与公开 Writer prompt 按 transaction/section 模式区分 heading
  合同；`llm/section_writer.py` 只对已知 planned heading 做表示恢复，保留正文词序，未知
  heading 和 heading-only 输出仍拒绝。
- `agentic/publication_transaction_contract.py` 只把表达式顶层加法送入加法关系检查；调用
  参数、shape 内的 `+1` 不再触发整句加法门，同时保留相乘、漏加数和否定加法的拒绝反例。
- `llm/section_writer.py` 暴露生产统一的 Writer response/content assessor 与 progress
  assessor；单页脚本的 acceptance sink 和 live/resume progress 均调用该实现。repair packet
  逐 atom 列出约束、候选 span、失败原因和 owner（Writer/Binder），不把内部 target/source
  ID 放入模型可见字段。当前 V2 没有新增隐藏语义 Binder provider call；Binder owner 是显式
  后续绑定责任，不是本片已执行的额外调用。

**离线验收。** 新增并执行
`python scripts/validate_unified_single_page_frozen_responses.py --run /tmp/c2p-s3-single-page-20260914-02a75-r2 --output .tmp/c2p-s39-contract-repair-20260914/inspection.json`，结果为
`status=pass`、`provider_calls=0`。两份响应在生产 normalizer 中保留 **1,369 / 1,532** 个
正文字符；primary/repair 分别为 **8/24、10/24** 个有效 required atoms，剩余 **16/14**
个逐 atom 缺口；detail 22 的 13 个嵌套 shape atoms 均不再被算术误判。标题合同、共享
assessor、repair owner 分解和四个加法反例均通过；完整 detail 仍按预期拒绝。证据见
[`inspection.json`](../.tmp/c2p-s39-contract-repair-20260914/inspection.json) 和脚本
[`validate_unified_single_page_frozen_responses.py`](../scripts/validate_unified_single_page_frozen_responses.py)。

**静态验证。** 以下均为本片重新执行的命令：

```text
python -m pytest -q tests/test_llm_section_writer.py
  -> 107 passed
python -m pytest -q tests/test_agentic_publication_method_writer_unified.py
  -> 18 passed
python -m pytest -q tests/test_llm_section_writer.py tests/test_agentic_publication_method_writer.py tests/test_agentic_publication_method_writer_unified.py
  -> 269 passed, 6 warnings
python -m pytest -q tests/test_agentic_unified_context_compiler.py tests/test_agentic_detail_atom_binder_and_trace_v2.py
  -> 34 passed
python -m compileall -q src tests scripts
  -> exit 0
git diff --check
  -> exit 0
```

**真实 prepare/live。** 使用全新目录
[`/tmp/c2p-s3-single-page-20260914-02a75-r3`](/tmp/c2p-s3-single-page-20260914-02a75-r3)，
冻结输入为 `/tmp/c2p-unified-repair-20260914-s3-codex-20`，runtime 为
`http://127.0.0.1:8006/v1`、`qwen38-27b-nvfp4`、context 131072。prepare 的 health、models、
metrics 均为 HTTP 200，模型身份匹配；同一 tokenizer/model identity 下 prepare 计量为
53,969 input tokens，provider sends/generation calls 均为 0，prepare 通过。

live 命令实际只发送两次：

```text
python scripts/run_unified_single_page_writer.py live \
  --output /tmp/c2p-s3-single-page-20260914-02a75-r3 \
  --profile tests/live/profiles/qwen38_vllm_budgeted.example.env
```

| 项目 | primary | repair |
|---|---:|---:|
| client generation / provider send | 1 / 1 | 1 / 1 |
| 同一 meter 的 input | 53,969 | 58,174 |
| provider prompt / completion / total | 49,704 / 1,260 / 50,964 | 53,909 / 1,269 / 55,178 |
| finish / usage | `structured_complete`、seen | `structured_complete`、seen |
| transport receipt | accepted | accepted |
| content acceptance / repair commit | rejected / 0 | rejected / 0 |

两次失败均精确落在 detail 10/22 的 required target contract，且记录了
`response_blocked:paragraph_transaction`；没有 `single_page_submission.json`，两份 receipt 的
`resume_eligible=false`，所以没有执行 resume。新 prompt/表示恢复已经使本片不再出现
`non_substantive` 的标题格式失败；顶层加法误判也没有出现在失败列表中。repair 仍未闭合
全部 atom，且 `writer_repair_no_progress_stops=1`，因此剩余阻塞是证据 atom 的内容与绑定
闭合，不是空流、finish/usage 丢失或发送前预算超限。

真实证据：
[`live_result.json`](/tmp/c2p-s3-single-page-20260914-02a75-r3/live_result.json)、
[`execution_record.json`](/tmp/c2p-s3-single-page-20260914-02a75-r3/execution_record.json)、
[`last_live_receipt.json`](/tmp/c2p-s3-single-page-20260914-02a75-r3/last_live_receipt.json)，
以及对应 invocation 目录下的两份 provider response、receipt 和 content-acceptance sidecar。
该页保持 incomplete；下一步必须先为缺失 atom 提供有账的 Writer/Binder 闭合路径和对应
静态/离线证据，再申请新的变更依据 live。不得换目录重复当前两次请求，不得在无提交状态
验证 resume，不得启动完整 authoring。

### 15.7 全流程复核后的当前执行入口（更新至 2026-09-15 r5 终态）

本节更新执行优先级；§15.6 各片保留为历史证据，不再把早期 T1/T2 微测重复执行当作当前默认下一步。
完整依据见 [全流程现状复核](research_to_method_end_to_end_status_review_2026-09-14.md)。
具体负责函数、CLI 待实现合同、冻结输入、验收及续跑操作统一执行
[生产入口收敛执行文档（2026-09-15）](research_to_method_production_closure_execution_2026-09-15.md)；
下列 A/B/C 是其摘要，不再分别扩成新的修复计划。

- **已交付**：冻结 Research 的 Candidate 预检通过；r4 有 32 个机制级 accepted formula packages；
  单页 r7 有 committed submission 和零新增发送 resume。32 个包仅覆盖 83 条 preferred 中的 32 条，
  不是全部公式完成，也不是最终论文表达已合格。
- **未交付**：最新全文 r5 exit 2，Writer 发送 0，没有 Candidate/Verified；
  structural exit 已落盘且 eligible=false。r5 已越过原先的执行顺序错误，却在试分页适配时混用旧/新段落合同。
- **当前代码已变化**：请求计量驱动的 Narrative/页面修订、最终请求重计量和原始超大页先修订的顺序已存在。
  本次冻结 r4 零网络回放从 19 段修订为 21 段，18 页，最大 payload 估算 19,791，四类 detail/formula
  ID 集合守恒；不能将此扩大为真实 tokenizer 或完整生产 prepare 已通过。
- **推进方式需改**：r2–r5 共登记 216 次 Formalizer 发送，请求批次哈希完全一致，Writer 均未开始。
  下一次下游调试先消费已有合法成果；不以新目录重复整批生成作为确定性编译错误的验证手段。
- **r5 修复边界**：`_ordered_candidate_rows` 目前会把缩小的候选 row 换成原始 row，复活不属于该小页的
  required detail；还会丢弃 4 个新生成的 `__f1/__f2` 段落。零调用对照复现相同 detail 13 错误；仅在内存中
  保留候选 rows 后，37 次候选构造返回、21 段、failures=[]。这不是最终 page 缺证的结论，不能向小页硬补 13。

下一步只按三个交付检查点推进：

1. **A：完整生产准备合同。** 提取并共用现有准备逻辑，一次覆盖候选 row 复活、新片段丢弃、局部页绑定、
   全局目标守恒和完整请求计量。partial handoff 必须进入共用材料后才冻结，避免现有 18/18 envelope 漂移；
   正文事务/accepted 必须消费当前计划，不能仍按旧 5 节投影当前 2 节。Writer 与当前独立 Realizer 的 primary
   使用真实 builder 计量；未来 repair/Editor/Rewrite 输入预留后再实测。失败候选也落诊断，生成调用 0。
2. **B：成果续跑与全文集成。** 实现有限的已结束 Formalizer 阶段读取，再由 replay/正常入口薄包装暴露；
   不能直接用通用 invocation resume 重发 23 个不完整 main。r5 的 32 个包（13 个来自 partial）已离线验证，
   保留原失败、父证据、花费和未结算额度。正常 `method-agent run` 接入共用 tokenizer；Editor/Rewrite
   接入辅助调用预算与 durable 发送。通过 prepare → 正文事务 → Realizer/组合 → structural exit/resume 的集成。
   required/preferred 边界不变，不能强制 83 条 preferred 全完成或删掉 51 条未覆盖义务。
3. **C：真实全文交付。** A/B 通过后直接执行 pending authoring；完整 Candidate、最终正文/计划/trace/公式
   消费的同身份验收、实际计量与恢复共同交付。失败回到所属阶段，不换目录重发整批 Formalizer。
   还须验证正常 `code2paper method-agent run` 入口，不以 replay 完成替代产品可用。Candidate 与 Verified
   独立报告；不以三条 strict Research partial 额外阻塞已合格的 Candidate lane。

第二次核验修正第一版范围：必修 F1–F6 与真实证据见收敛文档 §1.1，公式论文表达按实际消费定向处理，
不在进入 Writer 前另开整体 Formalizer 架构重写。正常产品入口目前漏传 tokenizer，辅助角色也未被统一账本
覆盖；这些是已定位的接线工作，不能留到全文 live 再逐一暴露。

当前成果足以继续推进，无需重做 digest/attempt/R10 或重写总体架构。距离首份完整 Candidate 尚有上述
三个交付检查点；未到达阶段不能据静态数量估算“只差一轮”。本次核查模型/网络调用 0，相关测试 107 passed。
本次未干预 r5，其终态已追加；下一次 live 前先完成上述完整准备合同验收，不覆盖已冻结失败和调用花费。

## 16. 验证、真实运行和停止条件

### 16.1 每片证据合同

Codex 在 implementation 中逐片记录：问题、修改函数、远端来源、与当前基线的差异、
精确命令/exit status/摘要、code-state digest、fixture 与 frozen input、结果文件及未完成项。
只记录测试数不足以完成验收。所有测试文件以本片清单为准：已有文件扩展；注明“可新增”的文件创建后才能加入命令。

每片只跑相关测试；修改之后出现新失败再扩大。除 R1 已列的命令外，各片用
`python -m pytest -q` 加该节实际测试路径，保持命令完整记入 implementation。
涉及脚本改动时 compileall 纳入 scripts；`git diff --check` 每片必做。

G2、G3 两个集成里程碑各运行：

```bash
python -m pytest -q
python -m compileall -q src tests scripts
git diff --check
```

旧 digest/attempt/promotion/canonical handoff/终态测试进入每个相关片及里程碑。
性能只在 R1/R2/R4 可能引入重复图扫描或源码重读时比较同一冻结规模，报告时间与操作数量；
不要求每片重跑全部基准，不以单次时间绝对值替代正确性。

### 16.2 Frozen offline 的精确入口

以下是当前已存在的零模型离线脚本参数，不是已经执行的记录。
输出名应替换为**尚不存在**的片次目录；先核对 repo 目录和冻结 tree hash，profile 文件仅供离线预算读取。

```bash
python scripts/run_unified_ten_project_offline_matrix.py \
  'ebcar=/tmp/c2p-nodec-ebcar-unified-20260913-205759' \
  --repo 'ebcar=/data1/users/cuihengjia/code2paper/code_final/EBCAR - Embedding-Based Context-Aware Reranker' \
  --profile tests/live/profiles/qwen38_vllm_budgeted.example.env \
  --model-context-tokens 131072 \
  --output /tmp/c2p-unified-repair-20260914-s1-01/offline-ebcar.json
```

- 该脚本包含多阶段检查，Candidate/strict 判定继续分列，不要求伪造 formula/Writer 后续阶段成功。
  S1 已统一图重建与实际 replay；后续图/输入相关变更仍须保留实际入口零模型验证，
  单独运行上面命令不能替代它。Run E 原始输入另外保留作历史/兼容回归。
- 输入使用完整 Research facts/claims/configuration/graph 与公式义务；不得用零 obligations、
  空调用计划或只有源级 graph 的重建替代真实形状的离线验收。
- 非空、身份一致的实际 workset/plan/phase 输出才能证明该阶段被覆盖。deterministic 测试包不证明公式质量。
- 十项目矩阵只纳入输入完整的原定项目，缺文件列 BLOCKED/NOT_AVAILABLE；不缩小分母后宣称 10/10。
  新输入获取若需要真实 Research，先列明单独的输入采集范围、预算和授权，不为补矩阵自动批量启动模型。

### 16.3 Live 前置条件与顺序

本次文档任务不启动 live。后续运行由 Codex 在实际分片验收与既有授权范围内执行；
没有授权的预算/模型或扩大矩阵不能由本文自动取得。

1. 先完成绑定当前代码的静态、冻结 source/Research admission 和各 consumer 结构门。
   如果需要新的 Research 来补路径证据，使用独立且有预算的 Research 诊断，不能绕过 Writer admission。
2. 可执行的单项目 EBCAR 诊断必须与正式三项目 pilot/matrix 分开命名，不能因诊断成功跳过原定退出条件。
3. 正式扩大到 LinearRAG、DyG 或十项目之前遵守 09-08 文档的 offline 全项目结构门与 actual-caller/resume
   前置条件；历史缺失的输入不等于通过。三项目按 EBCAR→LinearRAG→DyG 串行，完成后才考虑更广矩阵。
4. 每次使用新目录、独立 run/attempt/revision、完整 manifest。复用冻结 Research 的 authoring replay 与
   重新启动 Research 的 full product run 分开标记，不能把前者当作 Research 新能力证据。
5. preflight 记录 health、models、实际模型/上下文、profile/launcher digest、queue/KV 状态和输出目录。
   当前指定 runtime 为 `http://127.0.0.1:8006/v1`、`qwen38-27b-nvfp4`、131072，profile 为
   `tests/live/profiles/qwen38_vllm_budgeted.example.env`，capability profile 为
   `tests/live/profiles/qwen38_vllm_budgeted_capabilities.json`。旧 8003/qwen36 仅属历史协议。
   profile 名字不等于实际模型，不把不同协议混成同协议前后对照。
   环境不符合拟定协议时记录差异并按已有授权处理，不静默改模型。
6. 首次诊断串行；若后来授权并发，遵守 AGENTS 的最多四个运行、资源容量与监控要求。
   长请求记录进度/队列/资源；等待持续或资源不安全时降低并发，不重复不变失败样本碰运气。

### 16.4 正文与最终产物验收

至少交付：真实各 phase admission、invocation plans/receipts、原始响应摘要与终态、
Candidate/Verified 独立状态、质量报告、content trace、callback journal、模型与代码身份。

| 检查面 | 所需实际证据 |
|---|---|
| Candidate 生成 | 文件确实存在、有非标题正文，状态与字节一致；阻塞前未生成则诚实 not_started |
| 作者逻辑 | 动机、顺序、机制、必要条件和科学输出可连贯阅读；缺口可追踪而非删除故事 |
| 公式 | 学术表达、符号解释、消费者唯一、条件正确；generated-but-unconsumed 单列 |
| 条件与数字 | 无极性翻转、分母/归约/适用范围扩大，无代码字符串硬塞正文过门 |
| Verified | 仅保留已反向验证的事实；允许不完整但不得混入作者意图事实 |
| Callback | fulfilled 与 committed 分开；未受影响正文保留，改动有具体语义增益 |
| 指标 | 缺测可见、计数和精确正文一致、发现率分母独立 |
| 耐久性 | 后期校验、Editor/Rewrite/API 失败不清空已生成 Candidate；partial/terminal 绑定正确 |

原论文只用于质量参考/盲评，不进入 production fact authority。一个 live 样本通过不等于 D5、默认切换或发布冻结。

### 16.5 停止和向 owning Agent 返回的条件

- 来源、owner、条件极性、精确配置或目标身份不能证明：保持失败，给出具体缺口与拥有者。
- 新下游门出现：冻结反例并定位 owning subsystem；不得扩大首片、删目标、跳过 validator 或降低阈值。
- 内容/证据/绑定错误：有界返回 Research/Formalizer/Architect/Writer；Harness 只修表示层损伤。
- 新状态或 revision 破坏旧 checkpoint/handoff 兼容：停止迁移，补 producer/consumer 与往返证据。
- API/sample 失败：保留真实响应与终态，先判因；不把新目录重跑当作修复。
- 原定证据缺失：明确未验收，不复制历史数字或用近似样本代替。

## 17. 审查清单与执行入口

Codex 每片实施后核查 diff、implementation 和冻结产物，记录 PASS / REPAIR / NEEDS_EVIDENCE，
必要时直接修复并补相关验证；区分“本片代码接受”和“下游产品接受”。PASS 不自动扩张为 live/rollout 权限。

1. 实施范围是否与该片一致；是否保留 unrelated dirty baseline 与第 2.4 节成果。
2. 是否真正修复机制，而非改变统计分母、分裂/删减目标或修改 fixture 期待结果来消除报错。
3. 所有 claim/condition/formula/owner 变更是否有完整来源和反向验证；摘要是否由正确内容重算。
4. 正反测试及实际 producer→consumer 路径是否覆盖；失败退出、未生成和已生成耐久性是否区分。
5. 真实证据与代码、输入、模型、协议是否绑定；缺测、缺文件和未运行阶段是否诚实报告。
6. 远端补丁采纳日志是否记录替代/拒绝项，是否误带 AGENTS/.agent 清理或旧 V1 batch/slicing。

当前执行入口是本文，由 `docs/README.md` 索引；过程记录使用现有 `.agent/implementation.md`。
当前从 §15.6 的 S3 收口开始；保留 S1/S2 与 R0–R10 既有成果，按用户指定执行者和既有授权推进，
在同一文档与 `.agent/implementation.md` 更新执行位置，不重新从 R0＋R1 开始。

## 附录 A：Run E 核心证据的文件字节摘要

以下摘要在编写本文时仅通过读取文件计算；不是运行验证或模型重算。路径相对于 Run E 根目录。
若临时文件之后消失，摘要仅能鉴别已有副本，不能代替缺失内容。

| 文件 | SHA-256（文件字节） |
|---|---|
| method_agent_result.json | 31bafd2ad1d03f3947e42044ccb6c8329b8abec9dd007d85be412c5abe205b5c |
| artifacts/candidate_handoff_v1.json | 02dca90bcec053e2b8ce96e806231c89626e0ff93aec224e692a4b5ab567392a |
| artifacts/observation_promotion_ledger_v1.json | a3da2422a0c8d40092636e91f77e73a4436d4b7a04426d655d671f48b3fc1a06 |
| artifacts/06_authoring/unified_live_admission_v1.formalizer.1.json | cbbef77f5c8061a71a1ad55a448ee7b98927bf0ab92645229c2e26a713ed4ca9 |
| artifacts/06_authoring/mechanism_context_set_v1.json | 980ccc83ab8198392ac42aab7ead28312f101726e72b1d81373a272c06ea177f |

## 附录 B：早期任务摘要（2026-09-14；当前执行以 §15.7 为准）

```text
在当前 Code2Paper dirty worktree 继续同一个任务。
先读 docs/README.md，再读 docs/research_to_method_unified_repair_execution_plan_2026-09-12.md。
从统一执行计划 §15.6 的 S3 收口开始；S1 当前图/零模型预检已消费，S2 累计发送账本已接线。
冻结 /tmp/c2p-unified-repair-20260914-s3-codex-20；最新复核在 .tmp/c2p-s3-review-20260914/。
S3-20 已有116个 completed receipts及execution_record，exit 2；113次发送，仍无Candidate。
T1：补失败请求/响应/finish reason/usage记录；Formalizer统一完整typed schema，去掉重复payload，验证有效package。
T2：一个空Writer页和一个标题页微测；修内容验收与receipt分层、repair不退化及resume选择，不再增加盲重试。
T3：明确retry reserve硬边界与后续phase primary保护；实际tokenizer或已校准上界计量，已发送未知费用不清零。
T4：按真实入口证明有效页复用和派生身份，再做完整authoring，交付Candidate、structural exit及质量/反向验证。
首次微测建议最多6次且逐次有预算/失败诊断；微测不等于完整验收。禁止无变化地再整轮重算。
必须保留 digest、attempt、canonical handoff、终态 disposition、性能索引和所有结构/Verified 门。
不得通过拆开 calls/CALL、删 detail、降低 core 或把 unknown 默认改为 conditional 来通过。
旧图阻塞已跨过；三个Realizer witness失败在S3-20均repair成功。保留这些修复，不继续围绕尾逗号扩散改动。
R10 保留作者约束与修订绑定；真正的新 Research 缺口按 typed 证据有界补齐，strict partial 单列。
当前模型为 8006/qwen38-27b-nvfp4，context 131072；使用当前 profile，按 §16.3 记录 preflight 与新目录。
每片运行相关验证，在集成节点执行所需全量静态，记录具体命令、exit、代码/输入/产物摘要和未决项。
当前执行者直接实现、自检并修复方向内问题；不 reset/clean/切分支/提交/合并，不覆盖历史审计结果。
每片报告实际消费的变化、消失的阻塞、新增正文/阶段产物，更新 implementation 与 §15 状态。
本次文档更新不启动上述实现或 live；执行阶段按用户任务范围及既有授权持续推进。
```
