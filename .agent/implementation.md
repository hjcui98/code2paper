# Codex 工作记录

## 2026-09-16：P0–P6 产品集成闭环（未 V4 默认 cutover，未 P7 live）

- 依据：独立验收对 2026-09-16 执行文档实现的阻断项。本片修正常入口集成，
  不把 V4 设为默认，不启动 P7。
- 阻断 1：`method_propositions_v2` 进入 `build_product_planning` 返回字典，
  `persist_product_artifacts` 从 planning 读取并落盘。briefs 主线同时写出
  `intent_evidence_atoms_v1`。`test_compile_concept_cards_is_noop_without_live_llm`
  覆盖 planning→persist 真实链路。
- 阻断 2：V4 放入 `intent_narrative_envelope`（trace），不再向冻结 V3
  setattr。Writer 从 envelope 持久化 V4/bindings。仅当
  `CODE2PAPER_INTENT_NARRATIVE_PLAN=v4` 时用 V4 投影作为 workset/Writer
  身份（显式 canary）。
- 阻断 3：diagnostic checkpoint `complete=false`；clean 文件只写
  `clean_candidate_markdown`。fallback 只在 incumbent `complete=true` 时
  重发 clean Candidate，否则只发 diagnostic。
- 阻断 4：Writer 加载 V2 并投影到 aligner；alignment 缺失理由改为
  `method_propositions_missing`。最终验证写入 `ClaimVerificationReceiptV2`，
  `verification_mode` 由 receipt 派生，不再用“全 supported 且 0 次调用”
  冒充 exact。有 LLM 时才构造 semantic verifier。
- 阻断 5：Facet 阶段生产 atom/closure/field→atom trace。公式 identity 按
  `formula:facet:{id}` 与 `source_facet_ids` 桥接；`consumed_package_ids`
  与 `committed_paragraph_ids` 分列；required 未桥接保持 open。
- 阻断 6：`apply_local_rewrite_patches` 的产品调用强制传入
  `expected_incumbent_digest` 与 paragraph identity。
- 验证：组合回归 502 passed；全量 `python -m pytest -q` **3597 passed, 3 skipped**；
  `compileall` 与 `git diff --check` exit 0。未跑 P7 live，未默认 cutover。

## 2026-09-16：Author Intent spine 闭环修复（P0–P6 静态，未 cutover / 未 P7 live）

- 依据：`docs/intent_spine_authoring_closure_repair_execution_2026-09-16.md`。
  绑定 live10 `/tmp/c2p-production-entry-20260915-live10`；历史 live commit 与
  当前 probe 不得混作同一快照。未默认 cutover，未启动新的全文 live。
- P0：`_write_closure_metrics` 改为 schema 2.0，分母拆成
  `obligation_candidate_records` / unique symbols / unique obligations /
  must-cover atoms，并区分 search terminal、Candidate surface、repository
  proof。写出 `formula_identity_conservation_v1.json`。冻结夹具
  `tests/fixtures/intent_spine_ebcar/frozen_identity_v1.json`（5 节、28 units、
  7+84 公式 ID、26 包、44/17/6 获取记录；无仓库路径）。
- P1：新增 `IntentNarrativePlanV4` 与 `StoryMechanismBindingV1`。作者 section
  identity 先冻结，mechanism 只做多对多证据绑定；禁止 `Sym:*`/`mech_` 标题。
  产品路径仍以 V3 为 Writer 身份（P7 前不 cutover），V4 作为 sidecar 编译。
  Adapter 在 section id 对齐时按作者 section 回贴 argument units。
- P2：narrative unit 保持，证据拆 `IntentEvidenceAtomV1`；quote 不得窄于
  semantic fields；跨 span proof 拒绝不同 snapshot、互斥分支、未执行构造、
  部分 layer。`author_spec_only` 不能单独清零 Candidate surface。
- P3：canonical formula identity 桥接 7 个 legacy ID 与 84 个 mechanism
  obligation（原始交集 0 保留在 trace）。`formula_worthiness` 去掉
  LOAD/WRITE/RESHAPE 等 plumbing 的默认 display 资格。Mechanism 与 Section
  validator 共用 `formula_code_trace_failures`；冻结 WRITE 包被内容门拒绝。
- P4：clean Candidate 仅在全部 required section committed 后更新；partial
  进 diagnostic / checkpoint。失败 resume 保 incumbent。aggregate
  `completed_section_ids` 逐节保留，另有 `all_required_sections_complete`。
- P5：未知 failure 不默认 Rewrite；patch 校验 incumbent digest 与 paragraph
  identity；`no_progress` 停止同 owner 重试。
- P6：briefs 存在时仍编译 `method_propositions_v2`。词汇 overlap 只召回；
  加法→减法/乘法、极性/量词/条件破坏不能 deterministic exact。验证 mode
  为 `exact_verified|semantic|unresolved`，全 exact 允许 0 次语义调用。
- 验证：`python -m compileall -q src tests scripts` exit 0；`git diff --check`
  exit 0；执行文档列出的测试再加 writer/formalizer/issue-router/p0-closure
  共 467 passed。未跑全量静态、未做 P7 `method-agent run`。

## 2026-09-14：S3.6 后续——错误绑定与统一入口/预算校准检查点

- 依据：`docs/research_to_method_unified_repair_execution_plan_2026-09-12.md` §15.6.4
  及 `.tmp/c2p-s36-independent-review-20260914/review.md`。保留本工作树既有改动。
- P1：`publication_transaction_contract.py` 停止将 exact excerpt 的词汇重叠作为
  atom/detail 授权。加法源码的受限释义必须保留加法、全部加数与非否定极性；
  Binder 只在此检查通过后以词汇分数排序。精确源码摘录仍可通过；required atoms
  全有效后推导 detail 的合同未变。直接声明错误 witness 也由 assessor 拒绝。
  人工闭集反例：乘法正文 `valid=false`、0 atom；正常加法正文 `valid=true`；
  冻结 r6 原文局部 normalization 为 24 witnesses / 1 detail，乘法变体为
  9 witnesses / 0 detail / 1 required-target failure。以上 r6 只是当前代码离线
  回放，不写成真实 live commit。
- P2：`tests/test_agentic_publication_method_writer_unified.py` 通过生产
  `run_publication_method_writer` 入口将 accepted repair 的第二次同身份运行验证为
  零 Writer 重发，rejected repair 的 content receipts 验证为零 commit、不可 resume。
  该集成 fixture 是合成产物；冻结 r6 primary 的旧 `_p1__f1` 与当前 `_p1` 身份
  不兼容，不能将旧低层样本升级成生产统一入口成功提交。
- T3：只读预检 `8006` 的 `/health`、`/v1/models`、`/metrics` 均 HTTP 200，
  模型 `qwen38-27b-nvfp4`，running/waiting/KV/preemptions 均为 0。
  `/tokenize` 对当前冻结 18 个 Writer primary 的 wire chat 输入计数合计
  828,590 tokens，3 页超过现行 60,000 单请求上限；一页 primary 68,323、
  repair 68,873，而 UTF-8/4 仅估到约 40,000。校准只调用 tokenizer
  22 次，模型生成请求 0。证据：
  `/tmp/c2p-s37-calibration-20260914/all_writer_pages.json`、
  `calibration.json`、`budget-table.json`。旧 S3-20 账本的 116 completed / 113 sent
  保守代理已发送 1,990,033，其中 Formalizer 713,436、Writer 954,369、
  Realizer 322,228；113 次历史 provider usage 缺失，不将该代理视为真实 token。
  旧 envelope 2,000,000 与现 profile 2,500,000 身份不同；现 Writer/Realizer
  reserve 400,000/100,000 尚未由全角色真实计量证明。
- 检查：`python -m pytest -q tests/test_agentic_detail_atom_binder_and_trace_v2.py
  tests/test_llm_section_writer.py tests/test_agentic_publication_method_writer_unified.py
  tests/test_agentic_unified_context_compiler.py tests/test_llm_runtime.py -p no:randomly`
  → exit 0，178 passed；`python -m compileall -q src tests scripts` → exit 0；
  `git diff --check` → exit 0。生产合同文件 SHA-256
  `d958aaa15da95b3be41dc88730d179f4189919b7985395ed9e041350f2d55025`；
  预算表 SHA-256 `f1eead1f5e3f91342586b24cbeefebe9700efd7226df1e52fe7832a6a643d8dd`。
- 下一门：按当前 plan/page/schema 从统一入口做冻结响应注入的真实身份微测，
  同时校准 Formalizer/Realizer 与各 repair 的 wire token 上界、重建
  primary/future/spent/unsettled 总表，解决 3 个 Writer 单请求超限后方可
  启动完整 authoring。本片未修改 profile、未发送生成请求、未发布 Candidate/Verified。

## 2026-09-12：取消 OpenCode 协作流程

- 范围：仅修改 `AGENTS.md` 和 `.agent/`；保留工作区既有生产代码、测试和文档修改。
- 规则：Codex 直接负责诊断、实现、验证、审查与修复；取消 OpenCode 交接、`/implement`、
  按角色禁止编辑以及 Codex 只能只读验收的限制。小任务不要求四份协调文档。
- 清理：删除两份旧分派文件；13 份旧任务、计划、诊断及证据文件原样迁入
  [历史归档](archive/2026-09-12/README.md)，其中包含原实现日志的未提交内容。
- 边界：架构、Candidate/Verified 权威分离、证据硬门和 live 准入要求继续生效。
  本次不实现或验收历史产品任务，也不声明旧问题已解决。
- 验证（本次文档修改后的 dirty worktree）：`git diff --check -- AGENTS.md .agent` 通过；
  `python -` 内联检查退出码 0，确认 13 个归档 SHA-256 全部一致、新文档相对链接和
  `AGENTS.md` 的设计路径存在、当前目录仅含 README 与本记录。不运行 pytest、模型或真实 API。

## 2026-09-12：R0＋R1 统一下一步修复首片

执行入口：[Research → Method 统一下一步修复执行文档](../docs/research_to_method_unified_repair_execution_plan_2026-09-12.md)
（`docs/README.md` 已索引）。本片按该文档 §5/§6 实施；未开始 R2 及以后分片。

### R0 基线与反例冻结

- 实现身份：Code2Paper HEAD `84371e4fee974071a580d7832af0ac14908c2d4b`，保留原有未提交修复为基线。
  改动前 tracked diff 字节摘要（`git diff | sha256sum`）`d697160b…aca147`；R1 实施后
  `1ef313f3…7d6bc0`。相关文件：`mechanism_context_compiler.py` `771bc235…5140b`、
  `test_agentic_mechanism_detail_compiler.py` `ab295aba…f12f7`、
  `test_agentic_mechanism_evidence_closure.py` `ea54cfc4…e5c94f`、
  `test_agentic_unified_context_compiler.py` `587bb0fe…d9e4e8a`。子模块 `paperbanana_single_shot`
  `33a9edd6…`。`.tmp/` 为 task-specific 证据目录（gitignored），符合文档 §5 的“任务专属”要求。
- 被研究仓库身份（≠ 实现代码）：EBCAR repo HEAD `287506e3e2df30e3c840b8f6398b5010c25111e1`；
  Run E 冻结 snapshot/tree `repo:9b4f1a34…` / `sha256:9b4f1a34…`；
  核心源码文件 `src/model/ebcar_dedicated_attention_model.py`（当前字节 `d9c5c626…`）。
- profile/模型身份：`tests/live/profiles/qwen36_vllm_budgeted.example.env`
  `sha256:b6814884…79b32d1`（provider openai、base `http://127.0.0.1:8003/v1`、
  `CODE2PAPER_LLM_MODEL=qwen36-27b-nvfp4`、离线核算 context 131072）；Run E 实际模型为
  `qwen38-27b-nvfp4`，与 profile 名不是同一协议，不混用；不记录任何密钥。
- Run E 冻结（root `/tmp/ebcar-live-terminal-disposition-fix-20260911-142500`）：5 个关键文件
  均存在且字节 SHA-256 与文档附录 A 一致（`method_agent_result.json`
  `31bafd2a…05b5c`、`candidate_handoff_v1.json` `02dca90b…7392a`、
  `observation_promotion_ledger_v1.json` `a3da2422…c1a06`、
  `unified_live_admission_v1.formalizer.1.json` `cbbef77f…d4ca9`、
  `mechanism_context_set_v1.json` `980ccc83…ea177f`），本轮用文件工具与一次获准的完整访问重算核对，
  未覆写原 run；模型内 content_digest 与文件字节摘要分开记录。
- 盲修来源：commit `f58d806…ad00` 本地无对象、GitHub 不可达（fetch 134s 超时），
  依据为评审 `adoption-review.md` `d6fb3e17…0f083` 与缓存 `commit.diff`/`files.json`/`patches/`；
  逐项采纳决策已固化在文档 §3，本片据此生成 `adoption_ledger.json`（19 项：采纳/改写/拒绝/无需采纳）。
- 十项目冻结输入盘点：launcher 列出的 10 个 root 当前均存在（dyg、linearrag、ebcar、rap、
  lookahead、unimmad、codequant、domain_pruning、fastgs、learnat），按文档要求不以路径名
  代替内容完整性判定，逐项 listing 记入 `baseline_manifest.json`；本片不做矩阵扩项。
- 交付物（`.tmp/c2p-unified-repair-20260912-r0r1/`，JSON 均校验可解析）：
  `baseline_manifest.json` `c04ae8c6…ee8f1f`、`adoption_ledger.json` `ef3734ec…8da453`、
  `run_e_fixture_comparison.json` `26081e0e…0e1b3`；诊断/运行产物
  `offline/offline-ebcar-r1.json` `e5c4ef8e…22d66f`、
  `run_e_recompile_unknown_details.json` `cb5f56d1…4722c6`。

### R1 同操作条件与路径状态修复

- 问题（Run E 直接根因）：同一冻结 span `146:149`（EBCAR `forward` 内 `torch.zeros` 调用）在
  fact 视图 `calls` + guard `self.cfg.use_dedicated_attention` → `conditional`，在 graph 视图
  `CALL` + 空 guard → `active_default`；旧 `_operation_status` 对 `{conditional, active_default}`
  返回 `unknown`，使 core detail 22 触发 `core_detail_active_path_unknown` 与
  `unified_core_active_path_unknown`。
- 修改函数（均在 `src/code2paper/agentic/mechanism_context_compiler.py`）：
  `_branch_dominance_guards`（新增：typed TRUE/FALSE_BRANCH 与带 guard 的 CONTROL_DEPENDS_ON，
  以 branch span 包含 + NEXT_CONTROL 不越界限定支配范围；返回 recovered/unproven/conflicted 三类）、
  `_normalize_guard_text`、`_same_predicate_family`/`_proven_same_operation`（同作用域内
  同精确 span、同符号、同 operands/result 且谓词属同一通用语义族，如 calls↔CALL）、
  `_cluster_path_evidence`/`_path_evidence_marker_reason`（证据化聚合，替代旧 `_operation_status`，
  后者保留为投影）、`_graph_node_operation`（恢复 guard 与 activation basis 写入记录）、
  `compile_mechanism_evidence_closures`（节点级恢复 + 同精确 span 支配 `resolve_typed_guard`）、
  `annotate_mechanism_paper_details`（detail 的 status/conditions/activation_basis_ids/
  mismatch_reason 由同一证据函数产出；core+unknown 写入 compiler_diagnostics）。
- 远端对照：盲修未修改 `_operation_status`，其 same-span+predicate 相等规则会拆开 calls/CALL
  掩盖问题，明确不采纳（`adoption_ledger.json` 条目 `C-predicate-equality-merge`）。
- 规则要点：`{conditional, active_default}` 只有在证明为同一操作且仅有一个规范化 guard 时才对齐为
  `conditional`，并保留条件与 typed basis；guard 文本不一致 → `unknown`＋`guard_conflict`；
  对应关系不成立 → `unknown`＋`dual_view_correspondence_missing`；极性冲突 → `unknown`＋
  `path_polarity_conflict:*`；带 guard 边支配范围不足 → `unknown`＋`guard_dominance_unproven:*`；
  未证/冲突的 span 不参与同 span 支配。门禁（`validate_mechanism_context_completeness`、
  `validate_mechanism_context_structural_gates`、unified admission）未改，仍 fail-closed。
- 正反回归（项目中立 fixture，完整 owner/source/typed branch/fact-graph 绑定）：
  `tests/test_agentic_mechanism_evidence_closure.py`（节点级 TRUE_BRANCH 恢复、NEXT_CONTROL 不越界、
  极性冲突、支配不足、反向分支 `not (G)`、嵌套合取与顺序不变），
  `tests/test_agentic_mechanism_detail_compiler.py`（对齐通过并清空门禁失败、guard 冲突、
  同 span 不同操作、极性冲突、支配不足、无条件默认路径、未解析配置不升级为 selected、
  已解析 false 配置不升级、JSON 往返、跨 owner 不泄漏、同 span 支配与其 contested 负例），
  `tests/test_agentic_unified_context_compiler.py`（编译→archive detail atom 的消费者面
  status/conditions/basis 一致）。负例均经公共 compile→validate 路径断言，非仅测私有函数。
- 命令与结果（同一 dirty worktree，未跑全量、未调用模型）：
  - `python -m pytest -q tests/test_agentic_mechanism_evidence_closure.py tests/test_agentic_mechanism_detail_compiler.py tests/test_agentic_mechanism_formula_obligations.py tests/test_agentic_publication_method_writer_unified.py`
    → exit 0，`37 passed`。
  - `python -m pytest -q tests/test_agentic_research_models.py tests/test_agentic_candidate_handoff.py tests/test_agentic_autonomous_method_agent.py`
    → exit 0，`125 passed`。
  - 相关消费者回归批次（unified context、mechanism context models/projection/formalizer/realizer、
    behavior graph CALLS、p0 closure、compile candidate、v3 evidence chain、formalization guards、
    detail binder trace v2、research derived authoring、d6 portability、offline matrix）
    → exit 0，`192 passed`。
  - `python -m compileall -q src tests scripts` → exit 0；`git diff --check` → exit 0。
- 冻结离线派生链（零模型调用，Run E 完整 facts/graph/公式义务经真实 loader 重建）：
  `scripts/run_unified_ten_project_offline_matrix.py 'ebcar=/tmp/ebcar-live-terminal-disposition-fix-20260911-142500'
  --repo 'ebcar=/data1/…/EBCAR - Embedding-Based Context-Aware Reranker'
  --profile tests/live/profiles/qwen36_vllm_budgeted.example.env --model-context-tokens 131072`
  → 报告 `offline/offline-ebcar-r1.json`：`unknown_core_active_path_count=0`，两机制的
  `core_detail_active_path_unknown` 与 `unified_core_active_path_unknown` 均消失；Run E 原失败
  detail 22 的混合状态根因被消除。
- 未完成/未通过（不宣称 authoring PASS）：
  - `NEEDS_RESEARCH_EVIDENCE`：配置选择事实仍缺（`self.cfg.use_dedicated_attention` value=null、
    state=unresolved、definition/entrypoint spans 为空），本片只表达已被证明的条件行为；
    `mech_sym:9773c5add7af1f92`/`mech_sym:f6cf5bdfe2ae16f0` 的
    `operation_disposition_unresolved` 是同一类真实缺口（入口路径外未证操作），不靠本片发明证据。
  - strict Research 三条 `unified_core_intent_partial_without_terminal_gap` 与文档 §2.2 一致，未变。
  - 新观察到 `unified_workset_compile_failed:unified_page_projection_incomplete`
    （两页 20766/20868 tokens 超原子页预算）：属 R6 预算/R2 接线范畴，冻结记录、留待对应分片，
    未在本片降低阈值或过滤失败。
  - 本片不运行真实模型、不扩矩阵、不提交合并；R2–R10 未开始。
- 审查结论（文档 §17 清单）：范围与 R0/R1 一致，保留 unrelated dirty baseline 与 §2.4 成果；
  PASS（本片代码接受）＝ 机制证据与门禁行为按上述规则通过；不扩为 live/rollout 权限。

## 2026-09-12：R2 产物交接、源码冻结与准入口径

执行入口同上；按文档 §7 实施。同一 dirty worktree，未调用模型、未提交合并。

### 修改点

- `autonomous_method_agent.py::_writer_artifact_paths`：改为
  `_writer_artifact_paths(out_root, *, persisted_paths=None, allow_legacy_discovery=False)`。
  产品主路传入本次 `persist_product_artifacts` 返回的 `paths`，只解析本修订写出的文件；
  同名旧文件不会被补入。无 manifest 且未显式标记 legacy 时抛出
  `writer_artifact_manifest_required`；目录发现仅供显式标记的旧入口。
  callback 轮次使用同一个 `writer_artifact_paths`，因此每轮绑定同一修订 manifest。
- `repo_snapshot.py`：新增 `VerifiedSourceBytes` / `read_verified_snapshot_sources`：
  按 snapshot root 解析路径（拒绝绝对路径、`..` 与 root 外解析）、按 source manifest 校验
  partition（未列出/被排除的 kind 拒绝）、对照 manifest 与 snapshot 双方 content_digest、
  symlink 越界拒绝、binary/非 UTF-8 只做摘要验证不作为源码文本；字节首次读取后按修订冻结
  （工作区后来修改不改变已加载修订，新加载报 `unified_source_content_digest_mismatch`）。
  同时暴露与 snapshot 一致的 `repo_snapshot_id`/`project_tree_hash` 供 compiler 推导身份。
- `publication_method_writer.py::_load_repository_authoring_context`：`source_provider`
  改为此 reader（保留 `repo_snapshot` 字段用于身份校验）；unified 主路在编译后检查
  `reader.failures`，非空即 `unified_source_read_failed:<codes>` 失败。
  新增 `_evidence_identity_failures`：facts/atomic claims/equation claims 若声明
  snapshot/tree 身份，必须与本次 snapshot 完全一致，否则
  `unified_code_facts_snapshot_mismatch` 等拒绝；未声明身份的旧产物保持可读。
- `scripts/run_unified_ten_project_offline_matrix.py`：`_research_gate_failures` 直接调用产品的
  `_unified_research_gate_failures`，不再维护第二份 strict 判定；新增
  `_research_artifact_paths` 与 `_research_mode_failures`，用产品的
  `_load_authenticated_candidate_handoff` + `_candidate_lane_research_failures` 计算
  Candidate 车道，并在报告 `research` 段输出 `gate_mode`、`strict_failure_codes`、
  `candidate_failure_codes`、`candidate_gate_pass`、`candidate_handoff_status/digest/
  revalidation_failures`；行状态仍为 strict，Candidate 只是显式模式。
- 回归测试：新增 `tests/test_agentic_authoring_context_handoff.py`（manifest 交接、
  verified bytes 漂移/越界/未列出/二进制/排除 partition、reader `files` 视图不可绕过校验、
  跨 run 身份拒绝）；扩展 `tests/test_agentic_replay_execution_record.py`（`--repo` 必须匹配冻结
  tree hash、删除文件后拒绝、symlink 越界记录但不作为源码）、
  `tests/test_agentic_unified_ten_project_offline_matrix.py`（strict 与产品函数逐码一致、
  strict/Candidate 分列、缺 context 与产品一致）、`tests/test_agentic_14_vertical_tests.py`
  （legacy 发现需显式标记、manifest 只绑定本修订）。
  修正 `tests/test_agentic_publication_method_writer_unified.py` 的占位源码摘要
  （`sha256:source` 与真实字节不符），改为真实 digest——该 fixture 正是 R2 要拒绝的漂移样例。

### 命令与结果

- `python -m pytest -q tests/test_agentic_authoring_context_handoff.py` → exit 0，`10 passed`。
- `python -m pytest -q tests/test_agentic_unified_ten_project_offline_matrix.py` → exit 0，`6 passed`。
- `python -m pytest -q tests/test_agentic_replay_execution_record.py` → exit 0，`23 passed`。
- `python -m pytest -q tests/test_agentic_14_vertical_tests.py tests/test_agentic_publication_method_writer_unified.py`
  → exit 0，`21 passed`。
- `python -m pytest -q`（R2 完成后全量静态）→ exit 0，
  `3274 passed, 3 skipped, 7 warnings, 12 subtests passed`（521s）。
- `python -m compileall -q src tests scripts` → exit 0；`git diff --check` → exit 0；
  R2 后 tracked diff 摘要 `858ee3e3…ce9aa`。
- 冻结离线派生链（零模型调用，Run E 完整输入）：
  `scripts/run_unified_ten_project_offline_matrix.py 'ebcar=/tmp/ebcar-live-terminal-disposition-fix-20260911-142500'
  --repo 'ebcar=/data1/…/EBCAR - Embedding-Based Context-Aware Reranker' …`
  → `offline/offline-ebcar-r2.json`：`unknown_core_active_path_count=0`（R1 结论保持）；
  `gate_mode=strict`，strict 失败为三条 `unified_core_intent_partial_without_terminal_gap:*`；
  `candidate_failure_codes=[]`、`candidate_gate_pass=true`、`candidate_handoff_status=eligible`、
  `candidate_handoff_digest=sha256:d17433d2…`、重验失败为空——与文档 §2.2「3 supported＋3 qualified
  partial，handoff eligible」一致。行状态仍为 strict；Candidate 只作为显式模式输出。

### 未完成/移交

- 页预算失败（两页 20766/20868 tokens）仍按 R6 处理；本片未改阈值。
- offline harness 的 `source_provider` 仍使用重建出的 `RepoSnapshot`（其 digest 由重建保证一致），
  未切换到 `VerifiedSourceBytes`；产品侧已使用 reader。若 R6/矩阵需要同源读取口径，届时一并接线。
- 真实模型/live 未运行；R3 未开始。

## 2026-09-12：R3 质量与发现指标诚实计量

执行入口同上；按文档 §8 实施。同一 dirty worktree，未调用模型、未提交合并。

### 修改点

- `publication_quality.py`：新增 `SupportPrecisionMetricV1` 与共享函数
  `compute_support_precision_metric(report, text_digest, report_digest)`：
  缺报告 `not_measured`；报告 `blocked` → `blocked`；`input_text_digest` 与当前正文不符 →
  `invalid(support_precision_text_mismatch)`；计数为布尔/负数/非整数 →
  `invalid(support_precision_count_boolean|negative|invalid:<field>)`；
  `checked != supported+caveated+unsupported+unverified` → `invalid(count_mismatch)`；
  决定分母（supported+unsupported）为 0 → `not_applicable`；否则 `measured`，
  `precision=supported/(supported+unsupported)`，caveated 绝不并入 supported，
  unverified 保留并给出 `support_precision_unverified_claims_present`。
  `verified_authorized` 仅当报告 passed、mode=semantic 且 unsupported/unverified 均为 0，
  `lexical_only` 即使 precision=1.0 也不能授权 Verified。
  `EpistemicSafetyMetricsV1.support_precision` 改为 `float | None`（历史 V1 报告仍可读，
  但其 `support_precision_metric` 默认为 `not_measured`，不追认为已测）；
  `evaluate_publication_method_quality` 新增 `validation_report` 入参，用共享函数产出
  status/precision，并把 `unsupported_positive_claims` 取调用方与报告的较大值（只收紧不放松）。
- `publication_method_writer.py`：主路从 `final_validation_paths` 载入 `text_evidence_validation`
  并作为 `validation_report` 传入质量评估；新增 `_load_expected_operation_population`，
  从可选评估产物 `expected_mechanism_operations_v1` 读取独立 expected population
  （仅评估用），随 `expected_operation_source` 传给 trace。
- `method_content_trace.py`：`build/write_method_content_trace_v2` 新增
  `expected_operation_ids`、`expected_operation_source`；`MechanismInformationFunnelV1`
  新增 `mechanism_discovery_recall: float | None`、`discovery_recall_status`
  （measured/not_measured/not_applicable）、`expected_operation_count`、
  `discovery_population_source`、`closure_retention(_status)`、`zero_denominator_metrics`。
  发现率仅在独立 expected population 存在时计算（分子为 closure ∩ expected），
  不再用 closure 自身作分母；closure retention 单独计算；零分母的 legacy 比率保留历史数值
  但列入 `zero_denominator_metrics`，读者不会把 1.0 当成已测。
- `trust_contracts.py`：`TextEvidenceValidationReport` 的计数字段增加 `mode="before"` 校验，
  拒绝布尔冒充整数（此前 pydantic 会把 `true` 强转为 1）。
- `runner.py`：`_reconcile_publication_quality_with_final_validation` 改用共享 metric
  （不再把 caveated 计入 supported，也不再对零分母记 1.0）；`validation_passed` 要求
  metric 为 measured/not_applicable 且 digest 绑定；safety 回写 precision/metric；
  `_reconcile_publication_writer_result_with_quality` 的“无变化即跳过”判定加入
  candidate/verified validation status、warnings 分区与 quality digest，
  使总体状态不变时的可见状态变化仍会回写，并同步写入 `publication_quality_digest`。

### 回归测试

- `tests/test_agentic_publication_method_writer.py`：support precision 状态矩阵
  （缺测、零分母、计数不守恒、布尔、旧正文、blocked、全 caveated、semantic vs lexical_only），
  以及旧 V1 报告可读但不视为已测。
- `tests/test_agentic_runner.py`：runner 侧 measured/not_applicable/invalid 三例、
  Writer 与 runner 对同一报告结论一致的显式比对、总体状态不变但 validation 状态变化时回写。
- `tests/test_agentic_detail_atom_binder_and_trace_v2.py`：独立 expected population 正反例
  （缺 population→not_measured；空 population→not_applicable；漏一个→0.5；齐全→1.0）、
  closure retention 与零分母清单。

### 命令与结果

- `python -m pytest -q tests/test_agentic_runner.py tests/test_agentic_publication_method_writer.py
  tests/test_agentic_method_content_trace.py tests/test_agentic_detail_atom_binder_and_trace_v2.py
  tests/test_agentic_publication_method_writer_unified.py` → exit 0，`172 passed`。
- `python -m compileall -q src tests scripts` → exit 0；`git diff --check` → exit 0。
- `python -m pytest -q`（R3 完成后全量静态）→ exit 0，
  `3281 passed, 3 skipped, 7 warnings, 12 subtests passed`（521s）。
- R3 后 code state：tracked diff `fa7af109…1a42`；`publication_quality.py` `7aded663…e0dbac`、
  `method_content_trace.py` `c98503b9…1d2e85`、`runner.py` `8186775a…752989`、
  `trust_contracts.py` `b751b2ca…090f7b`。

### 未完成/移交

- 真实模型/live 未运行；R4 未开始。
- 发现率的独立 expected population 目前只能由评估产物提供；本片保证缺失时为 not_measured，
  不为补分母而生成清单。

## 2026-09-12：R4 Research 读取复用、记忆、符号与 parse 恢复

执行入口同上；按文档 §9 实施。同一 dirty worktree，未调用模型、未提交合并。

### 修改点

- `research_read_identity.py`：区分两类身份——`content_read_signature`（字节身份，用于缓存/复用）与
  新增 `obligation_read_signature`（`<obligation>|<byte identity>`，用于 no-gain 判定）。
- `research_policy.py::_no_duplicate_no_gain`：no-gain 改为按 obligation 判定（新增
  `_obligation_read_signature`；`_content_read_signature` 保留为字节身份）。同一 obligation 重读同一
  span 仍拒绝；**另一 obligation 读取同一 span 不再被拒绝**（字节可复用，但该问题仍需自己的图/claim 编译）。
- `research_graph.py::_executed_read_signatures`：改为发出 obligation-scoped 签名。
- `research_supervisor.py`：
  `_candidate_read_already_executed` 与 `build_decision_context` 的已读候选过滤都只看**当前 obligation**
  的执行记录；新增 `PriorReadMemoryV1` 与 `ResearchDecisionContextV1.relevant_prior_reads`/
  `prior_reads_truncated`/`prior_reads_projection_status`——从持久 `observation_history` 投影当前问题相关的
  先前精确读取（同 obligation → shared_symbol → shared_span → shared_path），带 `selection_reason`、
  `recency_rank`、按 `memory_budget` 限界；投影明确是 context 而非覆盖证明，被预算截断时置位标记。
- `research_nodes.py`/`research_graph.py`：把 `loop.observation_history` 传入决策上下文（检查点/resume 后
  历史来自恢复的 loop state，预算与选择规则不变）。
- `gemma_supervisor_backend.py`：`forbidden_exact_reads` 只列当前 obligation 的已执行读取，另有
  `reusable_prior_reads`（其他 obligation 的可复用记忆）与更新后的系统提示；新增
  `decision_failures` 记录：每次 proposal 边界失败记录 `failure_class`
  （llm_api_error/llm_blocked/llm_empty_response/llm_parse_error/representation_repair_failed/
  content_error_returned_to_owner）、prompt template、schema、model/provider、response_mode、
  finish_reason、blocked_reason、原始文本摘要（digest+preview）、恢复操作与摘要；恢复成功走既有
  recovery 且不记失败，恢复失败与内容错误走不同路径。
- `implementation_scope.py::_canonical_symbol_id`：compact path/name 引用只在**唯一匹配**时绑定；
  同名不同作用域或同文件多候选保持歧义（不再取第一个匹配）。
- `intent_compiler_v2.py`：`feature_combination` 只保留显式 concat 词表（CONCAT）；
  新增 `feature_fusion` 覆盖 combine/merge/fuse/aggregate（多形态谓词），作者显式拼接/顺序/条件要求不变。

### 回归测试

- `tests/test_agentic_research_policy.py`：同 obligation 重读拒绝、跨 obligation 允许（原两条
  cross-obligation 拒绝用例改写为同 obligation 拒绝 + 跨 obligation 允许）。
- `tests/test_agentic_graph_research_loop.py`：签名带 obligation，且不再以裸字节身份作 no-gain 键。
- `tests/test_agentic_research_supervisor.py`：当前 obligation 的已读抑制读取；其他 obligation 的读取不抑制；
  prior-read 投影选择原因、顺序、预算截断与状态；候选过滤仅按当前 obligation。
- `tests/test_agentic_gemma_supervisor_backend.py`：可恢复 JSON 损伤走恢复且不记失败；不可恢复解析失败
  `representation_repair_failed` 并保留真实终态；空响应/blocked 分类不同；未知工具属内容错误
  （`content_error_returned_to_owner`）而非表示损伤；prompt 的 forbidden/reusable 分区。
- `tests/test_agentic_research_models.py`：compact 符号唯一匹配正反例。
- `tests/test_agentic_intent_compiler_v2.py`：combine/merge/fuse 不强制 CONCAT，显式 concatenate 仍要求 CONCAT。

### 命令与结果

- 相关测试批次（supervisor/graph loop/policy/gemma backend/checkpoint resume/research models/
  intent compiler/tools extended/typed refs/target proposer）→ exit 0，`519 passed, 1 skipped`。
- `python -m compileall -q src tests scripts` → exit 0；`git diff --check` → exit 0。
- `python -m pytest -q`（R4 完成后全量静态）→ exit 0，
  `3292 passed, 3 skipped, 7 warnings, 12 subtests passed`（522s）。
- R4 后 code state：tracked diff `649b0658…4637a`；`research_read_identity.py` `0eb5f425…98b92`、
  `research_supervisor.py` `b8011375…f1abb`、`gemma_supervisor_backend.py` `279777c6…9b929`、
  `implementation_scope.py` `5f37df58…468c`、`intent_compiler_v2.py` `acbb715f…4d12`。

### 未完成/移交

- Run D 的原始 supervisor 响应在可访问证据中未找到（文档只标注“待绑定样本”，无冻结 root）；
  按 §9.6 只记录未复现缺口，不编造同样输入。协议级 synthetic 负例（可恢复/不可恢复/空/blocked/内容错误）
  已补齐；若后续取得 Run D 冻结产物，应按本片 `decision_failures` 字段归档并复核。
- 真实模型/live 未运行；R5 已开始（见下）。

## 2026-09-12：R5 公式身份、授权与论文条件表达

执行入口同上；按文档 §10 实施。同一 dirty worktree，未调用模型、未提交合并。

### 修改点

- `formalization_agent.py::adapt_mechanism_formula_package_to_legacy`：旧 sidecar 适配只有在
  `evidence_authority=repository_verified` 且 `formula_lane=repository_derived` 且
  `review_status=accepted` 且存在精确绑定（fact/equation/operation）时才给 `code_verified`；
  author-intent 映射为 `author_intent`/`author_intent_academic`/`review_required`，其余映射为
  `partial`/`hybrid_partial`/`review_required`；新包写 `schema_version="2.0"`（两处当前构建点同步）。
- `publication_transaction_contract.py::_formula_package_terminal_disposition`：只有缺版本标记或
  `1.0` 的历史包才允许走旧“默认 accepted”兼容分支；`2.0` 包缺 disposition 字段保持
  `review_required`，不会被当作历史默认接受。
- 条件绑定改为受控语义判定：新增 `_CONDITION_EQUIVALENCE_GROUPS`/`_CONDITION_NEGATION_TOKENS`/
  `_CONDITION_UNCONDITIONAL_TOKENS`/`_CONDITION_CONNECTIVES`/`_CONDITION_NOISE_TOKENS`/
  `_normalized_condition`/`_condition_token_matches`/`_condition_statement_matches`；
  `_witness_satisfies_constraints` 的条件比较走该判定（等价论文表述可绑定，缺失/反向/扩大范围失败），
  仍拒绝 substring 原码硬匹配与宽松关键词相交。
- `llm/section_writer.py::_compact_formula_packages_for_llm`：compact payload 保留
  `review_status`/`schema_version`/`source_detail_ids`（id-less 与常规两条路径都保留），机器可读 lane
  不因自然语言提示丢失。
- `_run_mechanism_formalizer_legacy`：读取真实 `LLMResponse.blocked_reason`/`text`/`content`；
  新增 `interface_failures`、`missing_binding_obligations`、`rejected_obligations`、
  `not_applicable_obligations`、`deterministic_obligation_ids`，正常缺包、失败包、rejected 与
  not_applicable 分开，接口异常不再被确定性 fallback 掩盖；逐页调用上界与既有 receipt/fragment 不变。
- display block 仍由 `canonical_formula_markdown_block` 只生成唯一 display-math 块；
  `splice_formula_placeholders` 的 `allowed_package_ids` 继续拒绝错误段落消费者。

### 回归测试

- `tests/test_agentic_formalization_guards.py`：author-intent 带 fact ID 不升级、review-required 不接受、
  repository-derived 需精确绑定、缺 disposition 的当前包不被历史默认接受、条件等价可绑定/反向失败、
  compact payload 保留机器可读元数据、legacy caller 读取真实 text 并记录 blocked、缺绑定与
  not_applicable 分类。
- 既有 `tests/test_llm_section_writer.py`（错误消费者拒绝）、`tests/test_v34prose_formula_and_leak_repair.py`
  （display block 不含整篇备忘录）继续通过。

### 命令与结果

- R5 指定测试批次（mechanism formalizer/formalization guards/formula obligation truths/formula
  obligations/detail atom binder/section writer/unified writer）→ exit 0，`169 passed`。
- `python -m compileall -q src tests scripts` → exit 0；`git diff --check` → exit 0。
- G2 全量静态与冻结离线链见下节（R6 后统一运行）。
- R5 后 code state（R6 前）：`formalization_agent.py` `4e35baf3…`、
  `publication_transaction_contract.py` `5bb44903…`、`llm/section_writer.py` `406ee327…`。

### 未完成/移交

- R5 未运行真实模型；V2 page/prompt/payload/receipt 的字节身份在 G2 冻结离线链中复核（见 R6 节）。
- 条件语义判定只覆盖论文条件表达与 witness 绑定；未引入固定 caveat 正则或原始条件逐字包含。

## 2026-09-12：R6 调用预算、真实入口与可移植产物（含 G2）

执行入口同上；按文档 §11 实施。同一 dirty worktree，未调用模型、未提交合并。

### 修改点（11.1 预算合同与计量）

- `unified_context_models.py`：新增 `UnifiedTokenMeterV1`（`method`/`tokenizer_identity`/`unit`/
  `measurement_basis`/`bytes_per_token`）、`RoleRequestBudgetV1`（prompt/output/thinking 预留）、
  `UnifiedRequestTokenAccountingV1`（system/prompt/payload/schema/wrapper 预留 + context/输出/thinking/
  margin + fits/overflow）。`RunInvocationBudgetEnvelopeV1` 新增 `token_meter`、
  `request_budget_by_role`、`max_request_input_tokens_by_role`、`safety_margin_tokens`、
  `model_context_tokens`，缺任一角色预算或每请求上限即校验失败。`ActualRequestReceiptV2` 增加
  `token_accounting`（被拒绝的请求也保留计量）。
- `unified_context_compiler.py`：新增 `measure_unified_tokens` 与 `account_unified_request_tokens`
  （计划与实际发送共用同一计量器与同一次计算；无真实 tokenizer 时使用显式标记的保守估算，
  不把 UTF-8 字节数声称为 tokenizer token 数）；`read_unified_budget_profile` 与
  `BUDGET_FIELD_BY_ENV` 扩展为唯一声明式合同（含 `max_binder_calls`、safety margin、prompt/thinking
  预留、每角色 output 预留与每请求输入上限），删除 2048/4096/8192 等代码内默认值。
  `build_consumer_invocation_plan_v1` 不再接收独立预留参数，只从 envelope 取名；
  `_plan_invocation_token_accounting` 在计划阶段用同一函数测量渲染 prompt、结构化 payload、
  response schema 与声明的 wrapper 预留，`max_input_tokens` 即该测量值，超过声明上限直接
  `unified_invocation_budget_exceeded`。admission 增加每请求上限、角色 output 预算一致性检查。
- 发送边界：writer/realizer 在真实发送前用 envelope 计量器测量实际请求，超过声明每请求上限即
  `..._input_tokens_exceeded` 拒绝并持久化 receipt；formalizer 的请求就是被准入的 consumer envelope，
  计划值与实际值必须完全相等，否则记录 mismatch。三者都不再把未计量请求交给 provider。
- `publication_method_writer.py`：profile 预算改由 `read_unified_budget_profile(os.environ)` 读取；
  formalizer executor 接收 `budget_envelope`。`scripts/run_unified_ten_project_offline_matrix.py`
  删除自带的第二份 profile 映射，直接使用同一 `BUDGET_FIELD_BY_ENV`/`read_unified_budget_profile`，
  离线与产品对同一缺失字段给出同一失败码。
- `tests/live/profiles/*.env` 与 unified writer 测试环境补齐声明值（binder calls、safety margin、
  prompt/thinking 预留、每角色 output 预留、每请求输入上限）。

### 修改点（页预算真相与超大原子报告）

- `_pack_pages_by_detail_graph` 的分组预算改为按**整页 payload**（header + obligation_ids + atoms +
  projection_proof）计量，而不是逐 atom 估算求和；真实页面因此不会再出现“打包接受、构造时超预算”。
  单页最小单位放不下时报告 `unified_atomic_page_over_budget:obligation:<id>:<tokens>><cap>` 与
  `...:contribution:<atom_id>:<tokens>`（最大贡献原子），不截断证据、不压低 obligations。
- mechanism 页与 join 页的超预算报告同样带贡献原子；section 页构建错误消息带最大原子及其 token。
- 冻结 Run E 离线链此前的 `unified_page_projection_incomplete: unified_atomic_page_over_budget:page:…`
  已消失：workset 编译通过（113 页，`status=pass`）。

### 修改点（11.2 独立兼容小修）

- `pyproject.toml`：安装入口 `code2paper` 改指向 `code2paper.cli.main:main`（已有唯一产品 parser，
  不再有第二个 parser 的转发缺口）；`code2paper.main_cli` 仍可导入。
- `writing_callback_fulfillment.py`：callback artifact 文件名可移植（`_portable_callback_filename`），
  逻辑 `artifact_id` 保留在 JSON 内；`_write_callback_artifact` 幂等（同内容不重写）、不同内容写入
  完整摘要区分名、再冲突则 `writing_callback_artifact_conflict` 失败关闭；artifact 记录新增显式
  `artifact_path`（`WritingResearchCallbackArtifactV1` 同步新增可选字段，空值在 Writer prompt payload
  中被剔除以保持 legacy 提示字节兼容；`tests/test_agentic_publication_method_writer.py` 的
  callback resume 用例证明 payload 形状未变）。
- `validators/latex_smoke_validator.py`：smoke 输入固定 LF，子进程显式 `encoding="utf-8"`、
  `errors="replace"`；`benchmark_review_workspace.py` 的 review context 写文件固定 LF。
  `tool_runtime.atomic_write_bytes` 已满足同目录原子替换与短前缀不影响最终目标/digest，补测试固定。
- 冻结离线链摘要可复现性修复（R2 交接面的集成缺陷）：`VerifiedSourceBytes` 暴露确定性
  `content_digest`（快照 id、tree hash、manifest digest 与排序后的路径/digest，不含捕获时间）；
  `RepoSnapshot.content_digest` 排除 `created_at`/`project_root`/git 观测字段；
  `_source_digest` 不再对无身份对象做 `str(object)` 回退（否则会哈希内存地址）；
  离线脚本改用 `read_verified_snapshot_sources`（与产品同源）与 `repo_snapshot_identity_digest`。
  修复前同一冻结输入两次进程得到的 archive/envelope digest 不同，修复后完全一致。

### 回归测试

- `tests/test_agentic_unified_context_compiler.py`：envelope 缺任一声明字段失败关闭、每请求上限在计划期
  拒绝、计划期与实际发送测量同一组 parts 且相等、超预算 overflow 由上限或 context 决定、
  整页计量导致合法拆分且不丢证据（含 atom-sum < page-cost 的对照）。
- `tests/test_agentic_publication_method_writer_unified.py`：新增“实际请求超过声明上限时先拒绝后发送”
  用例（模型零调用、receipt 记录 rejection 与 accounting）。
- `tests/test_agentic_autonomous_method_agent_cli.py`：安装入口 `code2paper` 转发 `method-agent`
  且其他子命令/帮助保留。
- `tests/test_r6_portability_and_budget_hygiene.py`：atomic write 幂等替换、callback 文件名可移植且
  逻辑 id 不变、同内容幂等/不同内容不覆盖/冲突失败、latex smoke LF 与显式解码、
  snapshot/reader 身份排除捕获时间、无身份 provider 的 digest 稳定。

### 命令与结果

- 相关测试批次（formaliz/unified/publication/authoring/autonomous/tool_runtime/portability/llm_runtime/
  method_agent）→ exit 0，`636 passed`；R6 定向批次 → exit 0。
- G2（R2–R6 后）：
  - `python -m pytest -q` → exit 0，`3316 passed, 3 skipped, 7 warnings, 12 subtests passed`（516s）。
  - `python -m compileall -q src tests scripts` → exit 0；`git diff --check` → exit 0。
  - 冻结 Run E 离线链（零模型调用，`--repo` 重水化，profile `qwen36_vllm_budgeted`）：
    `archive digest sha256:6b2ec29d…`（887 atoms，`status=pass`）、`worksets page_count=113`、
    `unique_tokens=459096`、`sent_tokens=270417`、`status=pass`；两次独立进程 digest 完全一致。
    残留失败码：`operation_disposition_unresolved`（入口路径之外的操作）、
    `unified_core_intent_partial_without_terminal_gap:*`（严格 lane 的诚实缺口）、
    `unified_narrative_plan_compile_failed:narrative_plan_v3_invalid`（R7 绑定切片）。
    证据：`.tmp/c2p-unified-repair-20260912-r6/offline/offline-ebcar-r6-final.json`。
- R6/G2 后 code state：tracked diff `d679c48b…`；`unified_context_models.py` `3269389f…`、
  `unified_context_compiler.py` `0b368267…`、`formalization_agent.py` `00597401…`、
  `publication_method_writer.py` `5651865a…`、`repo_snapshot.py` `6608f2dd…`、
  `writing_callback_fulfillment.py` `d4937ace…`、`mechanism_context_compiler.py` `624374ce…`、
  `scripts/run_unified_ten_project_offline_matrix.py` `6ba4bb68…`、
  `tests/test_r6_portability_and_budget_hygiene.py` `1c64057c…`。

### 未完成/移交

- 真实模型/live 未运行；G4 需另行授权。
- 冻结离线链在 workset 之后仍未进入 narrative plan 编译（R7 的 `missing_core_detail` 绑定缺口），
  该切片按计划在 G2 之后实施。
- 计划期 run reservation 仍按计划测量值累计（每请求另有声明上限约束）；如需把 cap 作为上界计入
  全 run 预留，应在 live 校准后再调整，不在本片猜测。
- 未执行 Windows 平台测试：文件名校验只覆盖 POSIX 行为，不宣称 Windows 已验收。

## 2026-09-12：R7 叙事 → controller 精确绑定（进行中）

按文档 §12 实施；同一 dirty worktree，未调用模型、未提交合并。

### 已完成

- `method_architect.py::build_narrative_plan_v3` 的“prior outline 章节数 > 机制数”分支重写：此前只用
  `context_items[0]` 把第一个机制的细节摊到全部旧章节，其余机制的 core clean detail 被静默丢弃
  （Run E 因此 `narrative_plan_v3_invalid:missing_core_detail` ×7）。现在按全部非 side-branch 机制
  角色排序后的扁平工作列表分配章节，段落仍只属于一个机制所有者（按机制边界与 8 条上限切块），
  每个 core clean detail 恰好放置一次；公式包只在拥有其 `source_detail_ids` 的段落放置一次，
  review 细节只附加到其机制的第一个段落；章节 `mechanism_ids`/unit `mechanism_context_ids` 记录
  该章节内不同所有者，空章节保留形状但不重复放置已归属细节。
- 新增 `tests/test_agentic_narrative_architect_v3.py::test_multi_section_outline_places_every_mechanism_core_detail`：
  两机制 + 四旧章节，断言无 `missing_core_detail`、全部 core detail 恰好放置一次、段落 owner 唯一、
  unit 覆盖两个机制。

### 命令与结果

- `tests/test_agentic_narrative_architect_v3.py`、`test_agentic_publication_method_writer_unified.py`、
  `test_agentic_unified_ten_project_offline_matrix.py` → exit 0，`17 passed`。
- 更宽批次（method architect product readiness/narrative/authoring plan/unified writer）→ exit 0，
  `55 passed`；`compileall`/`git diff --check` exit 0。
- 冻结 Run E 离线链：`narrative_plan_v3_invalid:missing_core_detail` 已消失，链推进到
  writer workset 扩展：
  `unified_writer_workset_extend_failed:unified_atomic_page_over_budget`，
  `section MA-S1 paragraph closure exceeds page budget 25618>20000`（最大原子 4290/3761/3310）。
  仍为 `fail`，未调用模型。

### 未完成/移交（下一步）

- 段落已是 Writer 事务的原子消费单位，但单个段落的闭包可以超过 `max_page_input_tokens`；R7 剩余工作
  是在计划阶段生成合法页/段落 revision（或经事务合同允许的段落分片），而不是截断证据或抬高阈值。
  下一步先核对 `publication_transaction_contract` 与 `_writer_section_inputs_v3` 对“同一段落跨页”的
  真实约束，再决定段落拆分（计划 revision）还是显式分片（页元数据 + witness 归属），并补相应正反测试。
- §12.2 的 proposal caller 权限与失败路径、`prior_sections < contexts` 分支的拆并章节单位/依赖保留
  尚未实施。

## 2026-09-12：方向复核后的 R5–R7 纠偏（F1–F4）

触发：`docs/research_to_method_repair_direction_review_2026-09-12.md` 的四项 P1 发现。按报告顺序
（条件授权 → 章节身份与 join 接线 → 合法分页与总预算 → 新的离线报告）在同一 dirty worktree 纠偏，
未调用模型、未提交合并。R5 条件部分的“等价短语可绑定”结论按报告要求撤回，改为结构授权。

### F1 条件授权纠偏（R5）

- 删除 `publication_transaction_contract.py` 中写入通用生产代码的项目答案
  （`_CONDITION_EQUIVALENCE_GROUPS` 的 `self.cfg.use_dedicated_attention` /
  `self.cfg.add_positional_encoding` 等）。词法匹配只用于定位候选子句，不再单独授权。
- 新增结构判定：子句切分保留 AND/OR 序列（`_condition_clauses`）、逐子句否定奇偶
  （`_condition_parity`）、比较运算符与数值字面量（`_condition_comparator`/`_condition_numbers`）、
  无条件标记拒绝、未匹配子句不得携带极性/比较或复述已声明谓词。标识符按词法部件比较
  （`self.cfg.use_dedicated_attention` → use/dedicated/attention），通用动词集合只允许动词层面
  改写（use↔enabled），不做项目词表。
- 授权路径：`_witness_condition_and_polarity_satisfied` 被 Binder 响应校验、确定性 Binder
  （Writer 声明 witness 若改变条件即丢弃并保持未绑定）与 `assess_paragraph_transaction`
  （Writer 事务路径）共同使用；结构无法证明时失败关闭，返回 owning Agent 有界修复，
  不引入项目白名单、不改回源码逐字包含。
- 回归：`tests/test_agentic_formalization_guards.py::test_condition_binding_is_structural_and_never_lexical`
  （AND↔OR、反向/追加反向条件、无条件、嵌套否定、比较边界、at least/at most），
  `tests/test_llm_section_writer.py::test_transaction_condition_binding_rejects_structure_changes`
  （真实 Binder/事务路径：错误条件不绑定、`assessment.valid is False`）。

### F2 章节身份纠偏（R7）

- `method_architect.py::build_narrative_plan_v3` 的“旧章节数 > 机制数”分支改为**按已证 owner 分配**：
  旧章节的 owner 只能来自其声明的 `mechanism_ids` 或其段落的 `mechanism_id`（唯一时才成立）。
  内容不再按位置均分；同一 owner 的多个章节按该 owner 的细节连续分配；机制在旧 outline 中没有
  已证章节时生成显式 revision 章节（`MA-REV-<slug>`）并在 trace 记录；owner 不可证明的旧章节
  不再复用，`trace["section_identity_failures"]` 显式列出 `prior_section_owner_unproven:<id>`。
- 复用段落保留其 id、`reader_goal` 与首尾 transition；公式包只在拥有其 source detail 的段落放置。
- `validate_narrative_plan` 新增 owner 一致性检查：段落 owner 必须属于其 section 与 unit 的
  mechanism 集合，且 required detail 必须属于该 owner 的上下文（`paragraph_owner_not_in_section`/
  `paragraph_owner_not_in_unit`/`paragraph_detail_owner_mismatch`/`unit_owner_not_in_section`）。
- 回归：多章节用例断言“旧章节声明的 owner 与其段落 owner、标题一致且不跨机制”，新增反序 outline
  用例与 owner 歧义显式阻塞用例。

### F3 join 页路由（R7）

- `build_consumer_invocation_plan_v1` 的 join 预扫描改为按消费者身份区分：公式 repair join 页
  （属于 formula workset 且带 `repair_obligation_id`）继续登记 repair 槽位；章节 join 页
  （属于 section workset、带一致 `join_dependency_proof`、无 repair id）作为合法 Writer/Realizer
  页通过；既无 repair id 又无依赖证明、或章节页伪造 repair id、或依赖证明与 header/atoms 不一致
  时失败关闭（`unified_page_projection_incomplete`）。
- 回归：`tests/test_agentic_unified_context_compiler.py` 的双机制章节 join 页走通
  writer plan，以及伪造 repair 身份/缺失依赖证明的负例。

### F4 预算闭合（R6，live 前）

- `RoleRequestBudgetV1`/accounting 新增声明的 `scaffolding_token_reserve`（每角色，profile 声明；
  正式化/binder 为 0，writer/realizer 4096）：计划期把它计入 `invocation.max_input_tokens`，
  使计划值成为该角色真实请求的上界；发送端测量真实 parts 时传 0，避免把 allowance 重复计入。
- 发送端合同（writer/realizer/formalizer 三处一致）：先测实际请求，依次检查角色每请求上限、
  计划上界（`planned_request_input_tokens`）、再按 ledger 的**已完成 receipt** 汇总本角色已用
  token 与该 phase plan 的 `reserved_input_tokens_by_role` 做原子扣账
  （`run_reservation:<needed>><remaining>`）。重试与 resume 复用同一 reservation，不再另起额度；
  `ConsumerInvocationPlanV1.reservation_contract = "atomic_debit_v1"` 明确记录该合同。
- 新增 `read_all_completed_receipts`（run 级汇总，按 plan digest 过滤）、
  `spend_input_tokens_by_role`、`remaining_run_input_tokens`；写端若 ledger 不可读则记
  `run_ledger_unreadable` 并拒绝发送。
- 回归：计划上界与 allowance（`test_writer_request_over_planned_bound_is_rejected_before_send`、
  `test_writer_request_over_declared_cap_fails_before_planning`）、envelope 缺 `scaffolding_*`
  失败关闭、以及重试/resume 扣账用例（同一 reservation、按 plan digest 过滤、resume 重算）。

### 命令与结果（本轮）

- 定向批次（formaliz/unified/publication/authoring/autonomous/tool_runtime/portability/llm_runtime/
  method_agent/narrative/binder/section_writer）→ exit 0，`721 passed`。
- `python -m compileall -q src tests scripts` → exit 0；`git diff --check` → exit 0。
- 全量静态（F1–F4 后）：`python -m pytest -q` → exit 0，`3325 passed, 3 skipped, 7 warnings,
  12 subtests passed`（332s）。
- 冻结 Run E 离线报告（零模型）：`.tmp/c2p-unified-repair-20260912-r7/offline/offline-ebcar-r7.json`，
  摘要与文件摘要见同目录 `r7-summary.json`。observations：
  - source `pass`（重水化 tree hash 与冻结一致）、archive `pass`（887 atoms，
    `sha256:6b2ec29d…`）、基础 worksets `pass`（113 页）；
  - writer workset 扩展后 131 页 / 4 worksets；formalizer/writer/realizer 三个 phase 均编译
    （65 / 18 / 18 planned calls，`reservation_contract=atomic_debit_v1`）；
  - `failure_details` 为空；残余 failure codes 仅为研究证据类：
    两机制 `operation_disposition_unresolved`、strict lane 三条
    `unified_core_intent_partial_without_terminal_gap`（Candidate gate `pass`，handoff eligible）；
  - 因此本片只声明“结构链路编译完成”，不声明 strict admission、正文质量或 live 通过。
- code state（F1–F4 后）：tracked diff `sha256:99e6acb39d8f4e55…`；
  `unified_context_compiler.py` `6d133a3a601a`、
  `unified_context_models.py` `1d9ac15a51e4`、
  `publication_transaction_contract.py` `ac2d02d6ec7b`、
  `method_architect.py` `a60bb2e01264`、
  `publication_method_writer.py` `a41d32d92c7b`、
  `formalization_agent.py` `84e8fec1c199`、
  `unified_invocation_ledger.py` `08b5e7790f51`。

### 未完成/移交（R8 待开始）

- §12.2 的 proposal 权限目前只记录“未消费”；把 proposal 真正接入组织/阅读问题/段落深度（仍在闭集内）
  属于 R7 后续或 R8 前置，不与已验证的 typed owner 分配混为一谈。
- strict lane 的三条 `core_intent_partial` 与两机制 `operation_disposition_unresolved` 仍需 Research 证据，
  不能以分页或预算调整掩盖；配置选择证据（`self.cfg.use_dedicated_attention`）仍为
  NEEDS_RESEARCH_EVIDENCE。
- `conservative_utf8_bytes_div_4` 仍是无 tokenizer 时的声明式估算；live 前若接入真实 tokenizer，
  必须记录 tokenizer 身份并按同一计量器重测计划与实际。
- 真实模型/live 未运行；R8–R10（callback 事务、搜索终态、假设修订）尚未开始。

## 2026-09-12：R8 局部 callback 事务与稳定比较分母

按计划 §13 实施；同一 dirty worktree，未调用模型、未提交合并。

### 修改点

- 新增 `callback_dependency_closure.py`（小型 typed bridge）：`CallbackAuthorityDeltaV1` 描述一轮 callback
  真正引入的 typed 变更（detail/operation/fact/claim/equation/configuration/condition/formula），
  `compute_callback_dependency_closure` 只经 typed 引用映射到 unit/paragraph/section
  （claim/equation/configuration → argument unit → owning sections **多对多**，detail → narrative
  paragraph → section）；无 typed 归属的目标进入 `unresolved_target_ids`，不做字符串搜索或静默丢弃；
  heading、章节顺序、措辞与生成时间不进入闭包（`content_digest` 对 heading 改名不变）。
  `narrow_resume_sections` 只在闭包非空、无未决目标且是请求集合子集时收窄 resume 范围；
  其余情况（未决/空/超集）保留请求范围并记录原因——重新验证更宽是安全的，跳过可达章节不是。
- `writing_callback_fulfillment.py`：每轮在 Writer resume 之前用该闭包计算并收窄
  `resume_section_ids`，trace 记录 `dependency_closure`/`resume_scope_source`/`requested_resume_section_ids`；
  未受影响兄弟章节不进入 resume，已提交正文/authorship/witness/placement 原样保留。
- 阶段状态分离并持久化：`WritingCallbackFulfillmentResultV1` 新增
  `research_fulfilled`/`revision_rebuilt`/`writer_resumed`/`prose_committed`/`final_validation_status`/
  `resume_scope_source`/`budget_rounds_consumed`/`dependency_closure`/`stage_identity`。
  `stage_identity` 在 initial、research 完成后、revision 重建后、Writer resume 后四个点记录
  mode/source_context_digest/page_manifest_digest/contract_present，三处中断恢复的身份可直接比对；
  Writer 失败时 `prose_committed=False`，不把 fulfillment 成功写成正文已提交。
- 回调轮次预算持久化：`artifacts/research_tool_data/writing_callback_budget_v1.json` 记录已消费轮次，
  每次进入循环前读取并从 `max_callback_rounds` 扣除，重放不再重置预算；
  预算耗尽返回 `callback_round_budget_exhausted_durably`。
- `publication_method_writer.py` 事务比较改用**独立计算的 required target set**：
  `_rewrite_required_target_rows`（target 类型/稳定 ID/所属 unit 的 authority lane/命题与 claim 的
  required_qualifiers 与 polarity，规范排序）+ `_rewrite_required_target_set`（单独 digest 与规范 ID 列表），
  写入每份 transaction metrics 并持久化为 `rewrite_transaction_metrics_v1`
  （`artifacts/07_validation/`，输出名已注册）。`_rewrite_transaction_has_cluster_gain` 先判
  `required_target_removed:*`（删目标不是增益），再对 incumbent∩candidate 做逐目标失败数非回归；
  合法新增目标形成新比较基线但交集仍受约束。

### 回归测试

- 新增 `tests/test_agentic_callback_dependency_closure.py`：typed 映射（claim/detail/共享 configuration
  多章节）、未决目标显式报告且不收窄、heading 改名不改变闭包 digest、子集收窄与超集保守、
  阶段状态分离、持久轮次预算读取/写入与损坏记录处理。
- 新增 `tests/test_agentic_rewrite_target_set.py`：target set digest 不受 heading/章节顺序影响且不等于
  整份 plan digest、删目标被拒（`required_target_removed`）、新增目标保留交集非回归。
- 既有 callback/continuation/writer 用例继续通过（`227 passed` 定向批次；更宽 R8 相关批次 `447 passed`）。

### 命令与结果

- `python -m compileall -q src tests scripts` → exit 0；`git diff --check` → exit 0。
- 全量静态见下方“R8 后全量”。

## 2026-09-12：R8 复核纠偏（三项 P1）

触发：`docs/research_to_method_repair_direction_review_2026-09-12.md` 之后的第二轮只读复核。R8 记录改为
“已实施并纠偏”，不再以第一版通过。未调用模型、未提交合并。

### 纠偏 1：恢复范围由重建后的权威差异决定

- `writing_callback_fulfillment.py::_authority_delta_from_revision`：从**修订前/后持久产物**计算 typed 权威差异
  （claim 合同字段 `status/claim_kind/required_qualifiers/polarity/math_op_kind/covers_obligation_ids`
  变化即计入，detail 集合增量为补充，round 收集的 operation/fact 作为兜底），不再只用本轮新增 id。
- 闭包改用**重建后的 plan 与 narrative plan** 映射；`narrow_resume_sections` 语义修正为：
  目标不可映射 → `closure_unresolved_targets_blocked` 且调用方 `blocked`
  （`callback_resume_scope_unproven:*`）；闭包超出请求集合 → **扩展**恢复集（`closure_expanded`），
  不再静默保留较窄范围；子集才收窄。
- Writer 调用后核对**实际采用范围**：优先 `resumed_section_ids`，否则用产品自身的
  `_actually_regenerated_section_ids(writer_aggregate, ...)`；有证据且缺少闭包内 section →
  `callback_resume_scope_not_adopted:*` 阻塞；无证据时 `resume_scope_evidence="unavailable"`、
  `resume_scope_verified=False`，不把缺失遥测当作已验证。

### 纠偏 2：中断与预算失败关闭

- `_read_consumed_rounds` 返回 `(rounds, ok)`；记录损坏/不可解析时返回 blocked
  `callback_budget_record_corrupt`，不再读成 0 轮（那会静默重启预算）。
- 新增 `writing_callback_stage_state_v1.json`：四个阶段（initial/research_fulfilled/revision_rebuilt/
  writer_resumed）的身份（mode/source_context_digest/page_manifest_digest/contract_present）持久化；
  重入时从磁盘播种 `stage_identity`，记录损坏时 blocked `callback_stage_record_corrupt`。
- `read_all_completed_receipts(strict=True)`：完成回执损坏不再静默跳过（`unified_receipt_corrupt`），
  writer/realizer/formalizer 三处扣账都使用严格读取并分类为 `run_ledger_corrupt`。
- 新增 `unsettled_started_attempts(ledger_root, plan, exclude=...)`：已开始但无完成回执的调用按该
  invocation 的计划输入保守预留（当前正在测量的尝试除外），覆盖崩溃后无法证明未消费的区间。

### 纠偏 3：完整目标合同参与比较

- `_rewrite_target_contract_map` 把每个 `kind:id` 的完整合同（required_qualifiers/polarity/claim_kind/
  math_op_kind/authority_lanes，多 owner 时取排序并集）纳入判定；同一 ID 的合同变化返回
  `required_target_contract_changed:<id>:<fields>`，删 qualifier、翻转极性或降低 authority 不再算增益。
- 目标集合新增 section 级与 paragraph 级 `formula_obligation`（后者来自 narrative plan 的段落所有者），
  删除公式义务返回 `required_target_removed:formula_obligation:*`。
- 复现探针：删除同一目标 qualifier 且仅改善文风 → `required_target_contract_changed`；保持合同时的
  纯文风改善仍返回 `monotonic_cluster_gain`。

### 回归测试

- `tests/test_agentic_callback_dependency_closure.py`：权威差异覆盖合同变化、stage 记录往返与损坏、
  严格回执读取、未结算尝试预留（含 exclude 当前尝试）、闭包扩展/阻塞/收窄三态。
- `tests/test_agentic_rewrite_target_set.py`：同 ID 合同变化（qualifier/极性/authority）被拒、
  公式义务进入分母且删除被拒、纯文风增益仍通过。
- 既有 callback/continuation/writer/unified 用例继续通过（定向批次 `474 passed`）。

### 未完成/移交

- 计划顶部状态与实现记录已统一为 R8 已实施并纠偏；R9（搜索终态）与 R10（假设修订）尚未开始。
- 全量静态与冻结离线报告需在 R9/R10 后按 G3 重跑；R7 计划输入上界合计 1,938,180 / 2,000,000 tokens
  （formalizer 692,690＋writer 637,914＋realizer 607,576），重试余量需在真实请求计量校准后确认，
  不得以运行后校准代替预算约束。
- 配置选择证据（`self.cfg.use_dedicated_attention`）与入口路径外 `operation_disposition_unresolved`
  仍为 Research 证据缺口，继续标 NEEDS_RESEARCH_EVIDENCE。

## 2026-09-12：R9 搜索终态（三种结果、回执与兼容迁移）

按计划 §14 实施；同一 dirty worktree，未调用模型、未提交合并。R8 纠偏见上一节。

### 修改点

- `research_models.py` 新增 typed 合同：`SearchReceiptV1`（run/snapshot 身份、obligation、规范查询与
  过滤范围、top_k、截断状态、结果 IDs 与 digest、已读/未读候选、关系检查、工具失败、预算、停止原因；
  `frontier_closed()` 仅在“有查询、有读取、无未读、未截断、无工具失败”时为真）、
  `TerminalSearchDispositionV1`（三种 outcome 各自的必需证明：inconclusive 需查询/观察与停止原因；
  budget_exhausted 需预算与剩余 frontier/未完成任务；unsupported_with_scoped_evidence 需冻结 scope、
  scope basis 与至少一份关闭回执）、`TerminalSearchOutcome`。
- `GapRequirementV1` 新增 `terminal_outcome`/`terminal_record_only`/`negative_evidence_authorized`/
  `search_receipt`；`research_terminal.py` 的终态判定改为读取 typed outcome 与回执，
  **删除** notes 字符串嗅探（原 `bounded_search_exhausted` 文本不再构成 exhausted）；
  未带 typed 证书的 legacy `explicit_gap` requirement 读为未决并保留原始数据。
- `research_tools.record_explicit_code_gap`：完整负结论必须有可证明关闭的 `search_receipt`
  （否则 `gap_search_receipt_not_provably_closed`）；新增 `terminal_record_only` 明确“有界停止”通道，
  记录 `search_inconclusive`/`budget_exhausted` 且 `negative_evidence_authorized=False`；
  payload 增加 `terminal_outcome`/`terminal_disposition`/`search_receipt`/`negative_evidence_authorized`。
- `research_nodes.gap_finalizer_node`：不再声称 `search_complete=True`；记录 typed stop（
  `missing_information` 追加 `terminal_stop:<outcome>` 作为调度信号，且该标记不进入工具 payload，
  保持幂等重放）；只有回执授权的结论才把 agenda 置为 `explicit_gap`，其余保留状态。
  `research_graph` 的调度谓词识别 `terminal_stop:`（搜索结束但非负证据），循环以
  `all_obligations_terminal`/`intent_coverage_blocked` 等有界原因终止，不再空转到 `max_turns`。
- 既有 `TypedResearchGapV1.status=unresolved` 与 completeness matrix 的 `unverified_by_repository`
  现在承载这种诚实终态；Candidate/strict 的结果不被提升为负结论。

### 回归测试

- 新增 `tests/test_agentic_terminal_search_disposition.py`：回执关闭条件（未读/截断/工具失败/未读取）、
  三种 outcome 的必需证明、legacy `explicit_gap` 无证书读为未决、typed 证书下才 terminal。
- 更新 `tests/test_agentic_research_models.py`（完整终态证明现在需要 typed 回执）、
  `tests/test_agentic_research_no_progress.py`（有界停止而非 `explicit_gap`，不得空转到 max_turns）、
  `tests/test_agentic_autonomous_method_agent.py`（unverifiable claim → `unresolved` 与
  `unverified_by_repository`，不再产生 `explicit_code_gap`）。

### 未完成/移交

- R9 的“旧 checkpoint/coverage/plan/Writer 一起往返验证”与 handoff/admission 的显式版本分支仍需在
  G3 前补齐；本片已保证缺证书不回填“完成”。
- R10（假设修订、作者约束不可缩水）尚未开始。

## 2026-09-13：第二次方向复核 P1-A–P1-F 纠偏（R9 认证负证据、R5 结构条件、R7 分页/身份、R8 权威差异、R6 跨修订扣账）

按 [第二次方向复核报告](../docs/research_to_method_repair_direction_review_2026-09-13.md) 给出的顺序执行：
先阻断未认证负证据并修条件与分页，再统一章节身份，再补 callback 完整差异与跨修订扣账，最后做集成检查点。
同一 dirty worktree，串行修改；未调用模型、未提交、未合并、未降低任何门禁。

### P1-A：R9 负证据只能来自执行层回执

- 新增 `src/code2paper/agentic/research_execution_ledger.py`：`execute_research_tool` 在每次真实执行后把
  discovery/read/relation 执行写入 run 级 ledger（工具名、obligation、snapshot/tree、查询、path_scope、
  top_k、截断、结果 IDs、已读 ID/路径/行区间、关系检查、失败、`node_budget`），ledger 写失败会写 poison
  记录并让该次调用 `invalid_request`，避免“丢记录=缩小 frontier”。
- 新增 `close_search_frontier` 工具：由执行层从 ledger 派生 `SearchReceiptV1`（新增 `ledger_digest`、
  `execution_record_ids`、`authentication="ledger_verified"`）并落盘 `search_receipts/`，返回 receipt id；
  frontier 未闭合时同样落盘但 `search_frontier_closed=false` 并给出未读/截断/失败原因。
- `record_explicit_code_gap` 不再接受调用者填写的回执内容（`gap_search_receipt_content_not_evidence`），
  只接受 `search_receipt_id` 并 `authenticate_search_receipt`：重载持久回执、按记录前缀重算 ledger digest、
  要求与当前 ledger 派生结果一致（否则 `search_receipt_stale`）、校验 snapshot/tree/obligation 与
  scope 覆盖；只有认证且 `frontier_closed()` 才产生 `unsupported_with_scoped_evidence`，否则记录
  `search_inconclusive`/`budget_exhausted`。
- 消费者复用同一认证裁决：`research_terminal._negative_evidence_authorized` 改调
  `verify_receipt_authentication`，`_search_exhausted` 不再只看声明的 outcome 字符串；
  completeness matrix 的 `_load_terminal_gap_artifacts` 只把认证过的
  `unsupported_with_scoped_evidence` 记录转成 `ExplicitCodeGapV1`，有界停止保持 `unresolved`。
- `research_tool_manifest` 的 StructuredTool runner 改走 `execute_research_tool`（原先绕过 dispatcher）。

### P1-C：R5 条件授权改为结构判定

- 新增 `src/code2paper/agentic/condition_structure.py`：显式语法（括号、AND/OR、NOT 重数、带符号数字、
  有序比较、操作数词形），固定短语表处理 `is at least`/`does not hold`/`is enabled` 等读者措辞；
  声明的条件树与 witness 条件片段必须规范形完全一致，未知语法保持未证。
- `publication_transaction_contract` 删除词表/子句列表/正则授权器，改为调用同一实现；
  复核报告的五类反例（布尔重新分组、`-5`→`5`、`not not`→`not`、比较两端交换、`alpha`→`alpha or beta`）
  在 `_condition_statement_matches`、`_witness_condition_and_polarity_satisfied` 与真实 Binder/Writer
  transaction 路径均被拒绝，合法等价措辞仍绑定。

### P1-B/P1-E：R7 分页合同守恒、公式/unit 归属与章节身份

- `fit_narrative_plan_to_page_budget`：按 `target_kind` 解析归属（detail 用 `target_id`、atom 用
  `detail_id`）并双侧规范化 `detail:` 前缀；比较完整 target 合同多重集（丢失/重复/改写即
  `paragraph_split_target_contract_not_conserved`）；无法归属的 target 阻塞
  （`paragraph_split_target_unassigned`）。公式按义务原子闭包路由到真正拥有的 fragment，无法证明时
  `paragraph_split_formula_consumer_incomplete`，不再统一搬到 `__f1`；unit 只保留自己原有的段落经拆分后的
  fragment；placement 按 package→义务归属重定向。
- 调用方（`publication_method_writer`）传入编译后的 formula packages，并对修订后的 plan 重新执行
  `validate_narrative_plan`；validator 新增 `witness_target_detail_not_owned`（目标必须属于本段）。
- `build_narrative_plan_v3`：`_prior_section_owners` 作为统一身份合同用于“少于/等于/多于”三种数量关系；
  等于/少于分支不再按位置 `prior_sections[sec_idx-1]` 复用，而是按稳定 section ID 对照 owner，
  未证明的 owner 记入 `section_identity.owner_unproven` 与 `section_identity_failures`。

### P1-D：R8 真实权威差异与冻结 before revision

- `_authority_revision_snapshot` 在**重建前**冻结 claims（含 `fact_ids`）、details、operations、facts、
  equations、configurations、formula packages/obligations、detail→operation/fact/condition 归属；
  `_authority_delta_from_snapshots` 对比两份快照并报告 added/changed/**removed**；
  unit 归属对象（claim/equation/configuration）只把“变化或删除”计为失效，纯新增不当作失效。
- `compute_callback_dependency_closure` 支持 `previous_plan`/`previous_narrative_plan`/`target_owner_map`/
  `added_target_ids`：删除/降级的 detail 经旧 narrative plan 解析，fact 经 claim→unit 与 detail→fact 双图解析，
  operation/condition/formula 经 `target_owner_map` 解析；纯新增且无人拥有进入
  `unmapped_added_target_ids`（记录但不阻塞），变化/删除无法归属仍进 `unresolved_target_ids` 并阻塞。
- 复核探针结果：`config:shared` true→false 产生 `configuration_ids=["config:shared"]` 且闭包覆盖 MA-S1、
  MA-S2；删除 `claim:alpha` 产生 `claim_ids=["claim:alpha"]`。

### P1-F：R6 跨 revision 扣账

- 三处发送前扣账（Formalizer / Writer / Realizer）改为 run 级：不再按当前 plan digest 过滤回执，
  历史修订消费计入同一 reservation；`register_invocation_plan` 持久化每份计划的 invocation 预留，
  `unsettled_started_attempt_records` 对旧计划孤儿 started attempt 从**其原始计划记录**读取预留，
  无法计量时 `plan_source="unknown"`，调用方以 `run_reservation_unsettled_unmetered` 阻塞（不再按 0 计）。
- 冻结计划 1,938,180 / 2,000,000 的差额记为计划余量，不是已验证重试余量（写入证据摘要 notes）。

### R9 迁移

- `build_candidate_handoff`：legacy `explicit_gap`（无 ledger 认证证书）记为
  `candidate_legacy_explicit_gap_unverified:<obligation>`（eligibility reason + warning），保持 handoff 不合格，
  不再作为“已穷尽缺口”进入 Writer；`evaluate_obligation_terminal_proof` 继续读为未决。

### 验证

- 新增/扩展测试：`tests/test_agentic_execution_ledger_receipts.py`（未认证回执被拒、真实执行派生回执、
  未读/截断/陈旧/poison、消费者复用认证）、`tests/test_agentic_formalization_guards.py`（五类结构反例）、
  `tests/test_llm_section_writer.py`（真实 transaction 路径五类反例）、
  `tests/test_agentic_unified_context_compiler.py`（分页 target 多重集守恒、run 级扣账、孤儿 started attempt）、
  `tests/test_agentic_narrative_architect_v3.py`（等量反序 outline 身份）、
  `tests/test_agentic_callback_dependency_closure.py`（配置变化/删除 claim/旧图解析/同路径重建快照）、
  `tests/test_agentic_candidate_handoff.py`（legacy gap 迁移）。
- 全量静态：`python -m pytest -q tests/ -p no:randomly` → `3366 passed, 3 skipped`（2026-09-13，当前代码）。
- 冻结 Run E 离线链（当前代码）：`.tmp/c2p-unified-repair-20260913-r9/offline/offline-ebcar-r9.json`，
  `model_calls_allowed=false`；source pass（rehydrate 同仓库）、archive `sha256:6b2ec29d…`（887 atoms）、
  131 页 / 4 worksets（duplication 1.0812）、三 phase 计划 65/18/18 均编译、
  `failure_details=[]`，admission 仍失败于 2×`operation_disposition_unresolved` 与
  3×strict `core_intent_partial_without_terminal_gap`；Candidate handoff eligible。
  代码身份与逐 phase 数据见 `.tmp/c2p-unified-repair-20260913-r9/offline/r9-summary.json`。
- 复核探针（脚本原样重跑）：`.tmp/r9-probe/review-probes-after.json` —— 五类条件反例全部拒绝；
  分页 6 targets → 2+2+2 且 `fit_failures=[]`；未执行搜索 → `invalid_request` 且 `terminal_gap=null`；
  反序 outline 的 heading 与 owner 一致。

### 未完成/移交

- R7 的“自主组织（proposal caller 仅记 `narrative_proposal_not_consumed`）”与同机制多章节的论证意图仍未闭环。
- R9 旧 checkpoint→coverage→handoff→Writer 已补 legacy 分支与调度读法，但完整往返验证仍需在 G3 中固化。
- R10（假设修订、作者约束不可缩水）未开始；真实模型与 live 仍需既有授权与准入前置。
- Research 证据缺口（配置选择、入口路径外 operation disposition）继续标 NEEDS_RESEARCH_EVIDENCE，
  不以调分页或阈值消除。

## 2026-09-13（续）：R7 自主组织提案消费 + R9 迁移往返验证

承接上一节的未完成项，仍在同一 dirty worktree；未调用模型、未提交合并、未降低门禁。

### R7：narrative organization 提案被真正消费

- `method_architect` 新增 `NARRATIVE_PARAGRAPH_ROLES` / `NARRATIVE_PARAGRAPH_DETAIL_LIMIT`、
  `_call_narrative_proposal`（保留原四位置参数并追加 `kind="narrative_organization"`，兼容旧 caller）、
  `_bounded_narrative_organization_proposal` 与 `_validate_narrative_organization_proposal`。
- 合同：提案只能对**本机制自己的** clean detail id 做分组，角色必须取自封闭集合，每个 clean detail
  必须恰好出现一次（组内重复与跨组重复都拒绝），单组 ≤8，机制 id 必须匹配；失败重试一次后记录
  typed failure（`narrative_proposal_unknown_detail`/`duplicate_detail`/`detail_unplaced`/
  `unknown_role`/`group_too_large`/`paragraphs_missing` 等）并回退确定性分组。
- `build_narrative_plan_v3`：提案通过后替换该机制的 paragraph 分组（review-only detail 仍留在
  `evidence_status` 段），trace 记 `proposal_status ∈ {accepted, partially_accepted, not_accepted}`、
  `proposal_applied`、`proposal_accepted_mechanism_ids`；未消费时仍记
  `narrative_proposal_not_consumed`。plan 仍要过 `validate_narrative_plan`，因此分组回归会导致构建失败。

### R9：旧 checkpoint→coverage→handoff→Writer 往返验证

- 新增往返测试：legacy `explicit_gap`（无认证证书）→ `build_candidate_handoff` 记
  `candidate_legacy_explicit_gap_unverified:<obligation>` 且不合格 → Writer 端
  `_writer_research_preadmission_failures` 报 `unified_core_intent_terminal_proof_missing:<obligation>`，
  证明旧 gap 既不会进入 handoff 的 supported/partial 集合，也不会在 Writer 预准入被当作已终态。

### 验证（本轮）

- `tests/test_agentic_narrative_architect_v3.py`：合法提案 → `accepted` 且每个 clean detail 恰好落一段；
  五类非法提案（未知 detail、重复 detail、丢 detail、未知 role、超限组）→ `not_accepted` +
  typed failure + 确定性回退且 plan 校验通过。
- `tests/test_agentic_candidate_handoff.py`：legacy gap 往返链路。
- 全量静态与冻结 Run E 离线链在本轮结束前重跑（见 §G3 证据与
  `.tmp/c2p-unified-repair-20260913-r9/offline/`）。

### 仍未完成

- R7 的 multi-section（prior outline 多于机制）分支尚未消费组织提案，仅记录未消费；同机制多章节的
  论证意图分摊仍是下一片的工作。
- R10 未开始。

## 2026-09-13（续二）：R7 multi-section 组织提案消费（收尾）

上一节记录的“multi-section 分支仅记录未消费组织提案”已补齐；同一 dirty worktree，未调用模型、未提交合并。

### 修改点

- `method_architect` 新增 section 级封闭提案合同：`_call_section_proposal`、
  `_validate_section_organization_proposal`、`_bounded_section_organization_proposal`
  （`kind="section_organization"`，兼容旧四位置参数）。
- 合同要求：只允许该机制**已证明拥有**的 section id 与它自己的 detail id；每个 section 恰好出现一次且
  非空，每个 detail 恰好出现一次（组内/跨组重复、未知 id、丢失 id、未分配 section 都拒绝）；
  detail 数少于 section 数时直接回退（`section_proposal_insufficient_details`），避免空论证章节。
  失败重试一次后记录 typed failure 并回退到确定性按数量分摊。
- 旧 outline 多于机制的路径（`count > 1`）现在：提案通过 → 每个 section 的 detail 集合由提案决定
  （trace 记 `proposal_applied[kind=section_organization]` 与 `proposal_accepted_mechanism_ids`）；
  未通过 → 保留原 count 分摊并记录失败原因。

### 验证

- 新增测试：合法提案使“3 details / 2 sections”从确定性 `[1,2]` 变为提案的 `[2,1]`，
  且 plan 仍过 `validate_narrative_plan`；非法提案（未知 section）→ `not_accepted` +
  `section_proposal_unknown_section` + 回退 `[1,2]`。
- 全量静态与冻结 Run E 离线链在本轮重跑（见下）。

### 仍未完成

- R10（假设修订、作者约束不可缩水）仍未开始（按你的指示暂缓）。
- 组织提案目前只覆盖“同机制多章节的 detail 归属”和单机制段落分组；跨机制的章节顺序提案尚未开放
  （当前顺序仍由 author intent/story spine 决定）。
- 真实模型与 live 仍需授权与准入前置；配置选择与入口路径外 operation disposition 仍为 Research 证据缺口。

## 2026-09-13（第三次复核 P1/P2 纠偏）

按 [第三次方向复核报告](../docs/research_to_method_repair_direction_review_2026-09-13_round3.md) 的顺序修正两个授权边界
（P1-A/P1-B）与两个集成点（P2-A/P2-B），并补一个固定范围的离线集成检查点；未调用模型、未提交合并。

### P1-A：执行账本完整性与重放身份

- `research_execution_ledger` 新增 `ExecutionLedgerError`/`ExecutionLedgerIntegrityError`/
  `ExecutionLedgerReplayMismatch` 与追加式 `_index.json` 清单（record_id → content_digest）。
- 读取：记录不可读/不可解析/`content_digest` 与实际内容不一致/被改写、索引缺失、索引与文件不一致、
  记录缺失（清单有而目录无）一律抛 typed 错误；`iter_execution_records`、`derive_frontier_receipt`、
  `authenticate_search_receipt` 全部 fail-closed，不再 `continue` 跳过。
- 写入：同一 `tool_call_id` 只在 snapshot/obligation/工具/参数/结果/读取集合完全一致时视为合法重放；
  同 ID 不同执行内容抛 `ExecutionLedgerReplayMismatch`，dispatcher 返回 `invalid_request`，
  不写 poison、不返回旧记录；其他账本错误同样以 `research_execution_ledger:<reason>` 拒绝。
- 消费：`verify_receipt_authentication` 可接 `ledger_reader` 复核；gap 工具把账本完整性问题记为
  `gap_search_ledger_integrity:*`；`close_search_frontier` 记 `search_ledger_integrity:*`。

### P1-B：完整条件结构

- `condition_structure` 重写词法：`* / + - % ** //`（含一元正负号）、`!`、括号、索引/属性标点全部进入结构；
  未识别字符产生 `SYNTAX` 单元并使解析失败（不再有“未消费语法被静默丢弃”）。
- 语法扩展为 `or/and/not` + 比较 + 算术链（`+ - * / % ** //`）+ 属性/索引操作数；操作数与运算符顺序、
  数字符号、否定重数都参与规范形比较（`x * y > 5` ≠ `x / y > 5`，`x + y > 5` ≠ `x - y > 5`）。
- witness 片段守卫改为：被匹配片段之外的任何 `JOIN/NEG/OP/UNCOND/SYNTAX` 都判失败，
  因此 `When beta or when alpha, ...` 不再为 `alpha` 授权。
- 合法 guard 恢复：`x.shape[0] > 0` 与同形 witness 现在绑定（此前因标点被丢弃而误拒）。

### P2-A：同 invocation 的旧 attempt 用原计划额度

- `unsettled_started_attempt_records`：先核对 started marker 的 `plan_digest`；与当前计划一致才用当前额度，
  否则从其原始计划记录读取；marker 无计划身份或原计划记录缺失 → `unknown`（调用方阻塞），不再默认取当前额度。

### P2-B：默认产品入口接通提案并回传修复诊断

- 新增 `src/code2paper/agentic/narrative_organization_proposal.py`：默认、受角色配置约束的提案 caller
  （无 provider key → 返回 None，离线路径保持 `not_requested`）；prompt 携带机制意图/阅读问题/角色与
  各 detail 语义投影，响应走封闭 schema；记录 request digest、input payload、响应摘要与错误。
- `build_narrative_plan_v3` 在 `proposal_caller is None and llm_config` 可用时构造默认 caller；
  trace 记 `proposal_default_caller`、`proposal_attempts`/`proposal_attempt_count` 与
  `proposal_call_accounting=recorded_not_in_invocation_plan`（这些调用尚未计入 unified invocation plan，
  真实计量时需并入账本）。
- 提案重试把首次 typed failure 作为 `repair_failures` 回传（prompt 与 input_payload 都带诊断）；
  `proposal_llm_caller` 作为产品 wrapper 的传输注入点（`run_publication_method_writer` → 叙事构建）。
- `autonomous_method_agent` 的 `architect_proposal_caller=None` 注释明确：None 表示“由 llm_config 构造默认
  caller”，不是跳过提案。

### 固定范围离线集成检查点

- 新增 `tests/test_agentic_third_review_integration.py`：执行记录→回执→gap→终态证明（含损坏账本、
  删除记录、陈旧回执拒绝）；组织提案→NarrativePlan→分页/Writer 行投影；跨修订预算（900 vs 100）。
- 另加：P1-A 账本完整性与重放测试 5 项、P1-B 第三轮条件反例/合法对照、P2-A 同 ID 跨修订额度、
  P2-B 默认入口与修复回传测试。此检查点是固定范围验证，不宣称完整 G3 或 live 验收。

### 验证

- 全量静态：见下一节“验证记录（当前代码）”；`compileall`、`git diff --check` 通过。
- 自建验收探针 `.tmp/r9-probe/third_review_check.py`（模型调用 0）：四项发现全部按预期拒绝/通过，
  结果存 `.tmp/r9-probe/`。第三方探针脚本本身在损坏账本处按设计抛出 integrity 错误（不再静默跳过）。

### 验证记录（当前代码）

- 命令：`python -m pytest -q tests/ -p no:randomly`；结果：`3384 passed, 3 skipped`（2026-09-13，exit 0）。
- 命令：`python -m compileall -q src tests`；`git diff --check`；均 exit 0。
- 代码身份：`git rev-parse HEAD` 与 18 个生产文件 sha256 记于
  `.tmp/c2p-unified-repair-20260913-r9/offline/r9-summary.json`（`code_state`）。
  早先记录的 3366/3371 计数对应更早的代码状态，此后每次变更都以本节命令重跑并以该摘要绑定；
  本文件不再以“见下”指代其它计数。
- 冻结 Run E 离线链（当前代码，`model_calls_allowed=false`）：archive `sha256:6b2ec29d…`（887 atoms）、
  131 页/4 worksets（duplication 1.0813）、Formalizer/Writer/Realizer 65/18/18 均编译、
  `failure_details=[]`；admission 仍为 2×`operation_disposition_unresolved` +
  3×strict `core_intent_partial_without_terminal_gap`；Candidate handoff eligible。
- 第三方探针：`.tmp/c2p-direction-review-20260913-round3/review_probes.py` 现在会在其“损坏账本”步骤
  按设计抛出 `ExecutionLedgerIntegrityError`（不再静默跳过），因此该脚本自身 exit 非 0；
  同一场景的验收结果由 `.tmp/r9-probe/third_review_check.py` 记录（模型调用 0）。

## 2026-09-13（第三次复核 §5 边界收尾）

按第三次复核报告 §5 修正两处 R9 生产边界、补齐 5.4 的下游验收，并修正提案 trace 的请求身份字段。

### 5.1 重放身份改为执行前核对 + 冲突持久状态

- 新增 `check_execution_call_identity(ctx, tool_call)`：在 executor 之前用 snapshot/obligation/工具/
  查询/path_scope/top_k 的请求投影与已有记录比对；不同即返回
  `execution_ledger_replay_mismatch_pre_execution:<call_id>:<record_id>`，**该请求不进入 executor**。
- 新增 `record_ledger_conflict(...)` 与 `<hash>.conflict.json`：若执行已经发生但记录无法提交
  （同请求不同结果），写入阻断记录（`status=ledger_conflict`、`tool_failure=execution_ledger_conflict:*`、
  `truncated=true`）并登记索引，使 `frontier_closed()` 保持 false，直到以新 call id 重做搜索。
- dispatcher 相应调整：执行前冲突直接拒绝；执行后冲突记 conflict 再拒绝。

### 5.2 终态消费者接入账本重验

- `research_terminal`：`evaluate_obligation_terminal_proof(..., receipt_verifier=None)` 新增适配器参数，
  贯穿 `_terminal_gap_bound`/`_negative_evidence_authorized`/`_search_exhausted`；
  **没有适配器时负证据读为未证**（不再仅凭存储的 `ledger_verified` 标记）。
- `research_execution_ledger.build_context_ledger_reader(ctx)`：返回用当前 revision 账本重新认证的
  适配器；`verify_receipt_authentication(..., ledger_reader=...)` 现在校验**身份一致**
  （receipt_id/content_digest/obligation/snapshot），不只是“非 None”。
- 生产消费者接线：`autonomous_method_agent._load_terminal_gap_artifacts`（由 runtime 构造 reader，
  损坏/删除/陈旧即不接受）、`publication_method_writer._writer_research_preadmission_failures`
  （由 terminal gap 路径推导 research 数据面 ledger root）、`research_graph` 调度
  （`_next_loop_obligation` 从 runtime 构造 reader；`explicit_gap` 必须能重认证才结束搜索，
  否则继续占用调度槽）。

### 5.3 提案 trace 请求身份（预算接线留待计量片）

- `_request_identity(request)` 读取真实属性 `input_hash`；trace 同时写
  `request_input_hash` 与兼容键 `request_prompt_digest`（同一值），并记录 `planned_input_tokens`。
- 统一预算接线（invocation reservation、发送前计量/扣减、started/completed receipt）仍按计划与
  tokenizer 校准合并执行；`proposal_call_accounting=recorded_not_in_invocation_plan` 继续如实标注。

### 5.4 集成检查点补到分页与真实 Writer 请求

- `tests/test_agentic_third_review_integration.py` 新增：
  提案 → NarrativePlan → `fit_narrative_plan_to_page_budget`（真实触发拆分）→
  `extend_writer_worksets_from_narrative_plan` → `build_consumer_invocation_plan_v1` →
  `_writer_section_inputs_v2`，并对**实际 Writer 请求 payload**断言：
  段落 detail 多重集守恒、每个 fragment 的 witness target 归属正确、
  完整 target 合同（6 个，含 `required_conditions`/`authority_lane`）进入 `binding_contract.detail_witness_contracts`。

### 验证（本轮）

- 全量静态：`python -m pytest -q tests/ -p no:randomly` → `3387 passed, 3 skipped`（exit 0）。
- 复核脚本 `.tmp/c2p-post-round3-verification-20260913/verify_boundaries.py` 重跑（exit 0）：
  `executions_before_rejection=[]`（执行前拒绝）、`loaded_explicit_gap_count=0`、
  `terminal_after_corruption=false`、`trace_request_digests` 与真实 `input_hash` 一致。
- 冻结 Run E 离线链：archive `sha256:6b2ec29d…`、131 页/4 worksets、65/18/18、`failure_details=[]`，
  五个准入失败码未变（`model_calls_allowed=false`）。
- 新增 `docs/research_evidence_checklist_2026-09-13.md`：五个失败码与配置证据缺口的补证清单
  （当前证据/缺失内容/允许查询范围/结束条件，以及负证据回写须先满足 R9 完整链路）。


## 2026-09-13：R10（§15）研究假设可修订、作者约束不可缩水

按统一执行计划 §15 实施；同一 dirty worktree，未调用模型、未提交合并。远端
``revision_reason`` 放行删除目标的规则未采纳。

### 合同（新增 `src/code2paper/agentic/research_revision_contract.py`）

- **来源类别**：`TargetProvenanceV1 = author_explicit | system_inferred | research_subquestion | unproven`；
  只有 `system_inferred` 可被替换/删除，作者显式约束与**无法证明来源的旧记录**都不可删除
  （`DELETABLE_PROVENANCE`）。`TypedBehaviorTargetV1` 新增 `provenance` 字段并进入 intent graph 摘要；
  `intent_compiler_v2._build_typed_targets` 标 `author_explicit`，`intent_target_proposer._normalize_target`
  标 `system_inferred`。
- **作者边界独立保存**：`AuthorConstraintSetV1`（goal/约束文本、target ids、必需 predicates/relations/
  conditions，内容寻址）；`build_author_constraint_set(graph)` 在提案之前捕获，
  `non_deletable_target_ids(graph)` 给出不可删除集合与覆盖分母。
- **只提案**：`RevisionProposalV1`（父 obligation、before/after target ids、来源类型、精确 observation/
  relation refs、原因、未决影响、预算；`extra="forbid"`，且 revision target 不能自称 `author_explicit`），
  无 status/authority 字段。
- **Harness 校验**：`assess_revision_proposal` 检查身份（重算 revision_id，伪造即
  `revision_forged_identity`）、父归属、来源（`unproven` 拒绝）、before 目标归属、
  跨 obligation 目标窃取、删除规则（作者/旧记录 → `revision_author_constraint_deleted`）、
  在**结果图**上做作者谓词/关系/条件守恒（含 `revision_generic_substitution`）、
  证据引用必须精确且已被观察、reason-only 拒绝、预算、子问题 parent、重复 resume；
  对作者目标的原地改写需要**独立**语义复核（无复核 → `pending_review`，复核失败 → rejected）。
- **原子应用与 journal**：`apply_revision` 通过模型构造器重建 graph（`model_copy` 会跳过摘要校验），
  只删除可删除来源的目标；`RevisionJournalEntryV1` 绑定改动对象摘要、覆盖分母、新增/删除目标、
  handoff 失效标记；`RevisionJournalV1` 拒绝重复应用并提供 `handoff_is_current`。
- **绑定工具**：`REVISION_BOUND_OBJECT_KEYS`、`object_digest`、`build_object_digests`、
  `missing_bound_objects`（§15.6 的 agenda/intent graph/coverage/claims/promotion/handoff/checkpoint/
  authoring plan 一起绑定）、`write_revision_journal`/`load_revision_journal`（输出名
  `research_revision_journal_v1`）。
- **接线**：`CandidateHandoffV1.revision_id` + `handoff_matches_revision`；
  `_writer_research_preadmission_failures` 在存在 journal 时拒绝 `research_revision_handoff_stale`；
  `persist_product_artifacts(..., revision_journal=...)` 把 journal 写入同一 artifact map。

### 测试

- 新增 `tests/test_agentic_research_revision_contract.py`（13 项）：允许推断层修订（含子问题独立预算）、
  拒绝删除作者约束/仅填 reason/未观察 span/错误 parent/伪造 revision/预算耗尽/重复 resume/
  跨 obligation 窃取/未证明来源删除/泛化谓词替换，作者边界复核不能自签（pending→独立复核），
  被拒修订不改变 graph 与分母，对象摘要绑定 + journal 往返，旧 handoff 在新修订下不可用，
  Writer 预准入拒绝陈旧 handoff。
- 扩展 `intent_target_proposer._apply_proposal` 的守恒检查：除 predicates/relations 外，
  作者侧 conditions 与 inputs 也不得在富化时丢失。
- 全量静态与冻结 Run E 离线链在本轮重跑（见验证记录）。

### R10 验证记录（当前代码）

- 命令：`python -m pytest -q tests/ -p no:randomly` → `3401 passed, 3 skipped`（exit 0）。
- 命令：`python -m pytest -q tests/test_agentic_research_revision_contract.py` → `14 passed`。
- `python -m compileall -q src tests`、`git diff --check` 均 exit 0。
- 冻结 Run E 离线链（当前代码，`model_calls_allowed=false`）：887 atoms、131 页 / 4 worksets、
  Formalizer/Writer/Realizer 65/18/18 编译、`failure_details=[]`；五个准入失败码未变；
  Candidate handoff `eligible` 且重验失败为空。archive digest 由 `6b2ec29d…` 变为 `58ad15ef…`：
  这是 intent graph 新增 `target_identity_digest` 字段带来的 schema 身份变化（atom/页/workset 与失败码不变）；
  旧 agenda/handoff 通过 legacy 摘要读法与 normalized handoff identity 保持可读（本轮实测）。
- 代码身份与 21 个生产文件 sha256 记于 `.tmp/c2p-unified-repair-20260913-r9/offline/r9-summary.json`。

### R10 仍未完成（下一片）

- supervisor/loop 侧的 revision proposal **生产**尚未接线（合同与 harness 已就绪，但没有真实提案调用点）。
  （已被本文件更晚小节取代：R10 第三片接入 `PROPOSE_TARGET_REVISION` 动作与 `propose_target_revision` 工具，并有产品路径端到端链路测试。）
- 新目标下 coverage/claims 适用性重算与 promotion/handoff/retry 的联动仍需按 §15.6 接完；
  journal 已能绑定并拒绝重复 resume，但 resume 路径尚未读取它。

## 2026-09-13（R10 第二轮）：实时修订应用、适用性重算与 resume 绑定

承接 R10 合同层，补齐 §15.6 的“同一 revision 下原子绑定 + 旧事实重新评估 + resume 不重复应用”。

### 修改点

- `research_revision_contract`：
  - `revise_research_targets(runtime, proposal, ...)`：单一路径的实时应用——从 runtime 的 intent graph 捕获作者约束、
    harness 评估、`apply_revision` 原子应用，然后**重新评估适用性**：目标变更的 obligation 用冻结事实
    (`align_target_to_facts`) 重新对齐，未解析目标/覆盖该 obligation 的 claim 会清空 `supported_claim_ids`、
    状态回 `in_progress`，并写入 `revision_revalidation_required:*`、`revision_target_unresolved:*`、
    `revision_claim_revalidation_required:*` 标记；未触及的兄弟 obligation 保持不变；
  - journal entry 通过构造器重建，绑定最终对象摘要（intent graph content/target identity、agenda、binding digest）；
  - `ResearchRevisionBindingV1` + `bind_research_revision` + `revision_resume_failures`：revision id、journal digest、
    intent graph/target identity/agenda digest、覆盖分母一起绑定；重复应用同一 revision、绑定陈旧、journal/graph/
    agenda 漂移都产生 typed failure；
  - `build_revision_proposal` / `build_subquestion_target`：确定性生产者与 LLM 提交同一 proposal 形态；
    子问题谓词必须来自注册词表且在证据图中被观察到。
- `autonomous_method_agent`：`persist_research_stage_checkpoint(..., revision_binding=...)` 把绑定量写入 checkpoint；
  `load_research_stage_checkpoint(..., revision_journal=...)` 在恢复前调用 `revision_resume_failures`（对照
  checkpoint 内的 agenda 对象），失败抛 `research_stage_checkpoint_revision_stale:*`。

### 测试与验证

- `tests/test_agentic_research_revision_contract.py` 扩到 **18 项**：新增实时应用与适用性重算、resume 绑定
  （重复应用/陈旧/漂移/正常四态）、checkpoint 绑定 + replay/stale 拒绝、确定性生产者与子问题谓词约束。
- 全量静态：`python -m pytest -q tests/ -p no:randomly` → `3405 passed, 3 skipped`；`compileall`、`git diff --check` 通过。
- 冻结 Run E 离线链：887 atoms、131 页 / 4 worksets、65/18/18 编译、`failure_details=[]`、五个准入失败码未变、
  Candidate handoff `eligible` 且重验为空。

### R10 仍未完成（下一片）

（历史快照：本节两条其后已由 R10 第三/四片完成，见更晚小节。）

- supervisor/loop 协议侧：把 `RevisionProposalV1` 作为 supervisor 的一种提案动作接线（当前 ingestion 入口
  `revise_research_targets` 与生产者已就绪，但循环决策尚未提交提案）。
- promotion/handoff/retry 在新 revision 下的联动读法（handoff 陈旧拒绝已实现；promotion ledger 与 retry 计数
  尚未随 revision 重算绑定）。

## 2026-09-13（R10 第三轮）：循环提交路径 + 第四次复核的四项跨阶段边界

第三轮先把提案提交接入真实循环（`PROPOSE_TARGET_REVISION` 动作 + `propose_target_revision` 工具 +
harness 摄取），随后按 [第四次方向复核报告](../docs/research_to_method_repair_direction_review_2026-09-13_round4.md)
修正该接线暴露的四个跨阶段缺陷。

### 修改点

- **循环提交路径**：`research_revision_ingest.py` 新增提交存储（内容寻址的 `target_revision_proposals/<sha256>.json`）、
  账本认证的已观察引用集合、harness 摄取（`ingest_revision_submissions`）与摄取结果落盘；
  `research_tools.propose_target_revision` 只写提交信封（`source_authority=semantic_hint`，永不报告接受）；
  supervisor 侧新增 `PROPOSE_TARGET_REVISION` 动作（词表 17 项）并在 `_MODEL_TOOL_TO_ACTION` / ready_tools /
  硬规则中暴露；`research_graph` 的两个循环实现（LangGraph 子图与 `ResearchLoopDriver`）在同一工具边界摄取，
  并把 `revision_journal` / 摄取结果 / 失败写到 `ResearchLoopResult`；产品路径把 journal 写入 checkpoint 与
  `research_revision_journal_v1` artifact，并给 Candidate handoff 盖上 revision id。
- **P1-A 作者边界冻结**：`build_author_constraint_set` 现在在**提炼之前**捕获每个作者目标的完整需求载荷与
  obligation 级需求（谓词/关系/条件/输入/变换/决策/输出/槽位种类）；`ResearchGraphRuntime.author_constraints`
  承载该冻结边界并随 checkpoint 传递（恢复时 digest 不一致即拒绝）；`assess_revision_proposal` 的守恒检查
  改为对照冻结边界（不再从可变图重建作者权威），并新增逐目标守恒（`revision_author_target_dropped`）。
  合法提炼把承载作者需求的目标标记为新的 `author_derived` 来源（仍可识别为推断层，但不可删除），
  未注册谓词由工具侧拒绝（`PROPOSABLE_PROVENANCE`）。
- **P1-B graph/agenda 同步**：`_revalidate_after_revision` 在同一事务内把修订后的目标**载荷**写入 agenda item，
  并在提交摘要与 journal 之前逐 obligation 校验 graph 与 agenda 目标逐字一致
  （不一致返回 `revision_agenda_target_mismatch:*`，不写 journal、不改 runtime）。
- **P2-A 预算分离**：新增 `DEFAULT_REVISION_RESEARCH_ALLOWANCE`；harness 的**修订次数**每次应用固定计 1，
  且从 append-only journal 推导（`min(调用方值, 3 - 已应用数)`），resume 不重置；提案的 `budget_requests`
  只作为子问题研究额度申请，单独计费并在 journal entry（`requested_budget`/`application_charge`）留痕。
- **P2-B 词表与相关性**：`assess_revision_proposal` 校验谓词/关系词表（`revision_predicate_unregistered`、
  `revision_relation_unregistered`）；`cited_predicate_support` 从运行中的 behavior graph 与冻结快照上同一抽取器
  建立“引用 → 已抽取谓词”索引，新增谓词若无任一被引证据支持则转 `pending_review`
  （`revision_ref_unsupportive` / `revision_predicate_unsupported`），未知 parent 在摄取前置拒绝。

### 测试与验证

- `tests/test_agentic_revision_proposal_loop.py` 扩到 **22 项**：提交工具（幂等/冲突/越权父级/作者来源）、
  摄取（认证引用、预算、replay、零预算绕过、额度分离、resume 不重置）、
  跨阶段不变量（提炼前后作者分母守恒与删除拒绝、修订后 agenda/graph 载荷一致、真实 `compile_candidate_node`
  按修订后目标对齐（spy 记录 `align_target_to_facts` 入参）、词表/相关性/错误父级/未读引用四类反例 + 合法对照、
  promotion ledger 重算与 retry 计数重置）。
- 复核探针复跑：`.tmp/c2p-r10-direction-review-20260913/results.json`（`model_call_attempts=0`，`probe_errors={}`）：
  P1-A 3→3 受保护目标、删除拒绝；P1-B graph==agenda；P2-A 四个零预算提案全部
  `revision_application_budget_exhausted:0/3`；P2-B 未注册谓词 `rejected`、已读无关引用 `pending_review`。
- 全量静态：`python -m pytest -q tests/ -p no:randomly` → `3429 passed, 3 skipped`；
  `python -m compileall -q src tests`、`git diff --check` 通过。
- 离线证据在本检查点重新派生：`.tmp/c2p-unified-repair-20260913-r10/offline/offline-ebcar-r10.json`
  与 `python .tmp/c2p-unified-repair-20260913-r10/build_summary.py` 生成的 `r10-summary.json`
  （24 个绑定文件 + 报告 sha256 同源）。报告与第三轮 payload 逐字节一致：archive `58ad15ef…`、887 atoms、
  131 页/4 worksets、formalizer/realizer/writer = 65/18/18、`failure_details=[]`、五个准入失败码不变；
  该轮 R10 改动未影响冻结链的分页/准入结果。`model_calls_allowed=false`，未启动 live。

### R10 仍未完成（下一片）

- 五个 Research 缺口的逐项补证：两个 mechanism 分解到具体 unresolved operation，三个 obligation 分解到
  未满足 targets，逐项记录入口/配置/关系证据、查询范围、读取与未读 frontier、回执、停止原因与 disposition；
  现有 `docs/research_evidence_checklist_2026-09-13.md` 仍主要是执行要求，未构成补证结果。
- 提案实际调用计量：完整请求的 planned/reserved/measured/spent/unsettled 全链（含失败尝试、retry、恢复）
  与绑定实际模型和完整序列化请求的 tokenizer 校准。

## 2026-09-13（Research 补证首片）：五缺口分解 + 三个未 resolved target 的首轮定向检索

第四次复核把“五个 Research 缺口逐项补证”列为跨阶段修复之后的下一片。本片完成其中的**分解**与
**首轮定向检索**，并把结果落成可复核文档，未做任何模型调用。

### 产物（全部由脚本派生，非人工转录）

- `.tmp/c2p-gap-evidence-20260913/decompose_gaps.py` → `gap-decomposition.{json,md}`：
  从冻结 Run E 的 `obligation_coverage_v2.json`、`mechanism_context_completeness_v1.json`、
  `intent_obligation_graph_v2.json` 与离线报告派生。
- `.tmp/c2p-gap-evidence-20260913/probe_unresolved_targets.py` → `unresolved-target-evidence.json`：
  用生产研究工具的确定性层（`search_code`/`read_code_span`/`close_search_frontier` + R9 账本）
  在冻结 EBCAR 快照上检索三个未 resolved target。
- `.tmp/c2p-gap-evidence-20260913/render_evidence_doc.py` → `docs/research_gap_evidence_2026-09-13.md`。

### 结果

- 两个 mechanism：离线重算码为 `operation_disposition_unresolved`，运行记录只留下
  `core_detail_active_path_unknown:detail:mech_sym:f6cf5bdfe2ae16f0:22`；逐 operation 清单需在
  `artifacts/06_authoring/mechanism_context_set_v1.json` 上重跑 completeness 编译器，**未完成**。
- 三个 strict obligation：`O-METHOD-MAINLINE-01-c8146479` 8 个 target 中 2 个未 resolved
  （`FILTER`/`MASK`、`CALL`/`COMPUTE` 的 partial），`O-STAGE-03-2c5bd758` 3 个中 1 个未 resolved
  （`FILTER`/`MASK`），`O-STAGE-01-039a963a` coverage=supported 且 0 个未 resolved
  → 其 strict 失败不是 target 证据缺口，须在 claim/qualifier 侧定位（不得编造 target 缺口）。
- 首轮检索取得有界正向线索：`src/model/transformer_encoder_hybrid_attention.py:45/51/104/113`、
  `src/model/ebcar_dedicated_attention_model.py:139-167`、`main.py:34`、
  `data/real/MS_MARCO_v2/preprocess.py:51-76`，并读取了部分 span；`close_search_frontier` 三个 target
  都给出账本回执（`receipt:9ac3b9003feaa083` / `receipt:96f17be405a3df00` / `receipt:7ba3556e345449ac`），
  但 `search_frontier_closed=false`（`mask` 检索截断、命中未读完）
  → 按 R9 规则三个 target 保持 `unresolved`，不写负结论。

### 下一步

1. 读取剩余命中并把候选 span 交给确定性证据编译（packet→facts→claims），或在读完后取关闭回执；
2. 在 `mechanism_context_set_v1.json` 上重跑 mechanism completeness，列出未处置 operation；
3. 在 claim/qualifier 侧定位 `O-STAGE-01-039a963a` 的 strict 失败；
4. 配置选择证据（definition span / 入口绑定 / override chain）；
5. 提案调用计量与 tokenizer 校准（`proposal_call_accounting=recorded_not_in_invocation_plan`）。

## 2026-09-13（R10 第四片）：产品路径端到端修订链路 + 计量缺口定位

### 新增：产品路径（`run_autonomous_method_agent`）的端到端修订链路测试

`tests/test_agentic_revision_proposal_loop.py::test_product_run_applies_a_revision_and_carries_it_to_every_artifact`
用一个“像真实 manager 一样”的 supervisor（在**同一次决策**里先 `read_symbol` 再提交引用该 span 的提案，
谓词取自运行自己抽取器的支持集）跑完整产品入口，验证修订确实贯穿每个下游产物：

- 真实读取把 span 写入 R9 执行账本 → 摄取用账本认证引用（跨 obligation 或未读引用都会被拒）；
- 修订落到持久化的 `intent_obligation_graph_v2`（新 target 在冻结图 dump 中）；
- `research_revision_journal_v1` artifact 存在且 entry 记录 `applied_target_ids` 与非空覆盖分母；
- checkpoint 的 `research_revision_binding_v1.revision_id` 与 journal 当前修订一致，
  `revision_ingest_outcomes[0].status == "applied"`；
- `candidate_handoff_v1.revision_id` 等于同一修订（旧 handoff 不可复用）。

该测试连续三次通过；与既有的 compiler-spy、checkpoint/resume、预算与词表/相关性反例一起，
构成第四次复核 §7.3 要求的“提炼 → 提交 → 接受/拒绝 → 实际编译 → promotion/handoff → checkpoint/resume”检查点。

### 计量缺口（下一片，已定位插入点）

第四次复核 §1/§7.5 要求的“提案调用计量”**未完成**，本轮只完成定位：

- 现状标记：`method_architect.py:8642` 在默认组织提案 caller 生效时写
  `proposal_call_accounting="recorded_not_in_invocation_plan"`；请求 trace 由
  `narrative_organization_proposal.py` 的 caller 记录（`request_input_hash`、`planned_input_tokens`），
  只有预留估算，没有完整序列化请求的实测。
- 不能在提案调用上直接复用 `ActualRequestReceiptV2`：它的 `consumer_role`/`phase`/`workset_id`/`page_id`/
  `plan_digest`/envelope digests 都绑定 unified pipeline 的真实 invocation；为提案调用伪造这些身份
  会产生假的投递证据。正确做法是**提案作用域的独立计量记录**（planned/reserved/measured/spent/unsettled、
  失败尝试与 retry、恢复），并显式标注它是否属于统一 invocation plan。
- 需要复用而不是新造的组件：`unified_context_compiler.measure_unified_tokens`（`UnifiedTokenMeterV1`，
  `model_tokenizer` 或声明的保守 meter）、`unified_invocation_ledger.publish_attempt_started/completed`
  的“先写 started、再写 completed”顺序语义、以及 `build_resume_plan`/`unsettled_started_attempts` 的
  恢复口径。
- 真实 tokenizer 校准必须绑定实际模型与完整序列化请求（prompt + input_payload + response schema），
  不能用预留余量当实测；校准结果随记录落盘。

### 追加：三个未 resolved target 的确定性编译探针（有界结论）

`.tmp/c2p-gap-evidence-20260913/close_unresolved_targets.py` 对首轮命中的三个候选文件
（`src/model/transformer_encoder_hybrid_attention.py`、`src/model/ebcar_dedicated_attention_model.py`、
`main.py`）用生产抽取器建 behavior 子图（701 节点）并编译事实（530 条，全部 supported），
再用冻结 target 对齐：

| target | 期望谓词 | 对齐状态 | 命中谓词 |
|---|---|---|---|
| `target-28d15b78c376` | FILTER, MASK | resolved | MASK |
| `target-d9c93c39b278` | CALL, COMPUTE | partial | CALL, COMPUTE |
| `target-c56c2da81fd1` | FILTER, MASK | resolved | MASK |

有界结论：两个 `FILTER`/`MASK` 缺口在冻结树中已有可编译证据，Run E 未解决是搜索/读取覆盖问题，
不是仓库缺操作；`target-d9c93c39b278` 谓词全中但 slot 未绑定（其他已 resolved target 同样如此，
属 coverage 阶段一般行为）。限制：本探针用合成 obligation id 一次性编译整文件节点，**不**等于生产
路径会把该 obligation 判为 supported；不写回 disposition、不关闭 frontier。结果渲染进
`docs/research_gap_evidence_2026-09-13.md` §4。

## 2026-09-13（计量片）：提案调用计量落地（caller 边界）

第四次复核 §7.5 要求的提案调用计量本轮实现到 **caller 边界**，并保持“未计量”与“已计量”的诚实区分。

### 新增

- `src/code2paper/agentic/proposal_call_accounting.py`：
  - `ProposalCallTallyV1`（每次尝试：planned/reserved/measured/spent、meter 与 tokenizer 身份、
    `request_input_hash`、状态与错误、起止时间、content_digest）与
    `ProposalCallAccountingV1`（`begin`/`finish`、`totals()`、`failed_call_ids()`、`unsettled_*`）；
  - **unsettled** = 只有 started 记录、没有 finish 记录的尝试的预留量（中断/崩溃/待恢复）；
  - **spent** = 已交到 caller 的尝试的实测输入（失败尝试同样计入，方向保守：宁可多记不可少记）；
  - `measure_proposal_request` 复用 `unified_context_compiler.measure_unified_tokens` 与
    `UnifiedTokenMeterV1`，对**完整序列化请求**分别测量 prompt / input_payload / response_schema；
  - `proposal_call_meter_from_envelope(envelope, ...)`：有 token meter 才计量；envelope 声明
    `model_tokenizer` 而本作用域没有 tokenizer 时返回 `None`（**不**用保守代理冒充实测）；
  - `write_proposal_call_accounting`/`load_proposal_call_accounting`（输出名已注册为
    `artifacts/06_authoring/proposal_call_accounting_v1.json`）。
- `narrative_organization_proposal.build_narrative_organization_proposal_caller(..., call_meter=...)`：
  每次尝试在**调用前**测量完整序列化请求、`begin` 写入待结项、调用后 `finish`；
  测量失败（如 tokenizer 缺失）记为 `failed` 且**不调用模型**；无 meter 时 `accounting=None`，
  保持 `recorded_not_in_invocation_plan`。
- `method_architect.build_narrative_plan_v3(..., proposal_call_meter=...)`：把 meter 传给默认 caller 构造，
  并在 trace 中写 `proposal_call_accounting`（有实测 tally 时为 `measured_with_proposal_accounting`）、
  `proposal_call_totals`、`proposal_call_accounting_digest`、`proposal_call_rows`。
- `publication_method_writer`：在构建 narrative plan 时从运行冻结 envelope 派生 proposal meter，
  经 `_build_narrative_plan_v3(..., proposal_call_meter=...)` 注入。

### 测试与验证

- `tests/test_agentic_proposal_call_accounting.py`（**10 项**）：planned/reserved/measured/spent/unsettled 区分、
  失败尝试保守计费、重复身份拒绝、持久化后 resume 的 unsettled 重算、tokenizer meter 必须配 tokenizer、
  envelope 派生拒绝伪造实测、caller 每次尝试独立 attempt 号、测量失败不触达模型、无 meter 保持 recorded-only、
  plan trace 携带实测 totals。
- 全量静态：`python -m pytest -q tests/ -p no:randomly` → `3440 passed, 3 skipped`；`compileall`、`git diff --check` 通过。
- 冻结 Run E 离线链在本片后重跑（`.tmp/c2p-unified-repair-20260913-r10/offline/offline-ebcar-r10-metering.json`），
  payload 与上一检查点**逐字节一致**（archive `58ad15ef…`、887 atoms、131 页/4 worksets、`failure_details=[]`、
  五个准入码不变）：离线链没有 provider key，提案 caller 不构建，计量不激活，因此不影响冻结结果。
  `r10-summary.json` 已按该报告重新派生。

### 仍未完成（计量）

- 把提案调用的 planned/reserved 并入**统一 invocation plan 的预留与发送前扣账**（当前是
  caller 边界的独立 tally + trace，尚未参与 run 级 planned/reserved 汇总）。
- 真实 tokenizer 校准：需要在产品 runner 一侧把实际 tokenizer 与完整序列化请求一起传入
  （writer 作用域没有 tokenizer；`model_tokenizer` envelope 下提案调用会保持未计量而不是伪造实测）。

## 2026-09-13（补证片二）：两个 mechanism 的逐 operation 分解与定向证据

承接上一片的五缺口分解，本片把**两个 mechanism**（`operation_disposition_unresolved`）分解到具体
未处置 operation，并给出逐项入口/配置/关系证据、读取、frontier、回执与停止原因。

### 方法（全部派生，模型调用 0）

- `.tmp/c2p-gap-evidence-20260913/decompose_mechanisms.py`：复用离线矩阵的
  `_load_research_inputs` / `_source_inputs` / `_rehydrate_source_inputs` /
  `_rebuild_current_context_set`，在冻结输入上以 `current_compiler_rebuild` 重跑
  `compile_mechanism_contexts` + `validate_mechanism_context_completeness`，输出
  `mechanism-decomposition.json`（含每个未处置 operation 的谓词、span、enclosing symbol、阻塞原因）。
- `.tmp/c2p-gap-evidence-20260913/probe_mechanism_operations.py`：对每个未处置 operation 用生产工具
  （`read_code_span`、`inspect_configuration`、`search_code`、`close_search_frontier` + R9 账本）
  收集读取、配置键命中、检索命中与回执，输出 `mechanism-operation-evidence.json`。
- `render_evidence_doc.py` 把两者（以及冻结的 `configuration_claims_v1.json`）渲染进
  `docs/research_gap_evidence_2026-09-13.md` §1.1/§1.2。

### 结果

- 失败码可稳定复现：`mech_sym:9773c5add7af1f92` 157 个 operation 中 6 个 `explicitly_unresolved`；
  `mech_sym:f6cf5bdfe2ae16f0` 217 个中 2 个；两者 terminal coverage 均为 1.0，
  即失败集中在少数操作而非整体覆盖。
- 8 个未处置 operation 全部位于“掩码装配/传入注意力层”的分支代码：
  `transformer_encoder_hybrid_attention.py:160`（`TransformerEncoderWithHybridAttention.forward`，
  LOAD/CALL/WRITE `attn_mask`/`key_padding_mask`/`causal_mask`/`src`）与
  `ebcar_dedicated_attention_model.py:171`（`EBCarRerankerHybridAttention.forward`，
  `dedicated_attention_mask = torch.zeros(...)`）；阻塞原因均为 `unresolved_detail:*`
  （对应 detail 的 active path 为 `unknown`）。
- 直接上游是配置选择证据缺口：冻结配置声明中 `self.cfg.use_dedicated_attention` 为
  `value=None`、`state='unresolved'`、`definition_span_ids=[]`、`entrypoint_span_ids=[]`，
  只有 1 条 override-chain 关系；本轮定向检索命中 `conf/config.yaml:19:use_dedicated_attention`
  定义，但**未**取得取值/入口绑定。
- 两个 mechanism 的 frontier 均未关闭（`search_result_truncated`，
  `unread_candidates:33` / `unread_candidates:6`），回执分别为
  `receipt:caf066735d668b4e`、`receipt:bf299b111cb62287`；按 R9 规则**未写回任何 disposition**，
  也未把“未找到取值”当作不存在。

### 下一步

1. 读完两个 mechanism 的未读命中（33 + 6），或在读完后取得关闭回执；
2. 解析 `use_dedicated_attention` 的取值/入口绑定与 override chain（配置选择证据第 3 节），
   再把对应 detail 的 active path 置为可判定，从而让 8 个 operation 得到 disposition；
3. 三个 strict obligation 侧：把已找到的 FILTER/MASK span 走生产 packet→fact→claim，
   并定位 `O-STAGE-01-039a963a` 的 claim/qualifier 侧失败。

## 2026-09-13（补证片三）：阻塞 detail 与配置选择证据

本片回答上一片留下的问题：“8 个未处置 operation 到底卡在哪”。

### 结果（全部由脚本从冻结产物派生，模型调用 0）

- 阻塞点不是“缺证据”，而是承载这些 operation 的 **supporting detail 的 `active_path_status=unknown`**：
  - `mech_sym:9773c5add7af1f92` → `detail:...:68`（`transformer_encoder_hybrid_attention.py:160`）；
  - `mech_sym:f6cf5bdfe2ae16f0` → `detail:...:39`、`detail:...:40`
    （`ebcar_dedicated_attention_model.py:171` / `171:174`）。
- 配置选择证据（清单第 3 节）本轮取得：
  - 定义 `conf/config.yaml:19` → **`use_dedicated_attention: True`**（span `span:conf/config.yaml:16:22`）；
  - override 链 `rel:83ef85703286c813`（`CONFIGURED_BY`）从
    `span:src/model/ebcar_dedicated_attention_model.py:145:174` 的分支指向该键的 LOAD 节点，
    即 `if self.cfg.use_dedicated_attention:` 正是 mechanism 2 掩码装配区间的守卫；
  - 消费/入口命中 `src/model/ebcar_dedicated_attention_model.py:145`、`src/train_ebcar.py:116`、
    `main.py:15/25`（OmegaConf loader）；直接检索 `config.yaml` 为 `success_empty`
    （配置按 loader 变量路径装配，不是字面量路径）。
- frontier 仍未关闭（`unread_candidates:11`，回执 `receipt:3d0d25cc227b84e0`），
  因此**只登记证据**：不写回配置 claim、不写回 operation disposition。
- 结论（有界）：mechanism 2 的 active-path 问题在本轮证据下已可判定
  （分支 + 配置取值 + 入口消费齐备），应由生产路径重新解析配置声明；
  mechanism 1 的阻塞 detail 位于 hybrid attention 编码器调用行，其守卫/选择证据尚未取得，
  需按同一方法继续检索。

### 脚本与产物

- `decompose_mechanisms.py`（新增 `blocking_details`）→ `mechanism-decomposition.json`
- `probe_config_evidence.py` → `config-evidence.json`
- `render_evidence_doc.py` → `docs/research_gap_evidence_2026-09-13.md` §1.3

## 2026-09-13（补证片四）：两个 mechanism 的守卫链与 active-path 判定证据

### 结果（冻结源码直读 + 生产工具，模型调用 0）

守卫链（每一环都可复核到冻结行号）：

| 环节 | 位置 | 事实 |
|---|---|---|
| 入口装配 | `main.py:24` | `@hydra.main(config_path="conf", config_name="config")` 把 `conf/config.yaml` 装配为 `cfg` |
| 模型构造 | `src/train_ebcar.py:136` | `reranker = EBCarRerankerHybridAttention(cfg, device)`，无分支 |
| 编码器构造 | `src/model/ebcar_dedicated_attention_model.py:22` | `__init__` 中无条件构造 `TransformerEncoderWithHybridAttention` |
| 分支守卫 | 同文件 `145`–`174` | `if self.cfg.use_dedicated_attention:`（145–167 建掩码） / `else:`（168–174 消融分支） |
| 配置取值 | `conf/config.yaml:19` | `use_dedicated_attention: True` |

有界结论：

- mechanism 2 的 2 个未处置 operation 位于 `else`（消融）分支（171–174），
  在冻结取值 `True` 下**不活跃**；
- mechanism 1 的 6 个 operation 位于 `TransformerEncoderWithHybridAttention.forward`
  （`span:...:160`），该编码器经上述无条件链条构造并调用，在 train 入口下**活跃**；
- 二者都不是“证据不存在”，而是 completeness 无法仅凭 evidence 判定 active path；
  判定所需的值/定义/入口/守卫证据已齐备。
- 工具旁证：`find_references` 只找到 `ebcar_dedicated_attention_model.py:13/22` 两处引用；
  `inspect_configuration` 对 `use_hybrid_attention`/`hybrid_attention`/`use_transformer_encoder`
  均 `success_empty`（不存在独立开关）；`conf/config.yaml` 的键集合已列出（`use_dedicated_attention`
  是唯一相关开关）。

仍未写回：frontier 未关闭（`unread_candidates:4`，回执 `receipt:9eb23389098ad608`），
且 Run E 是否经 `train_ebcar` 入口的 scenario 绑定需运行侧确认；本轮只登记证据。

### 产物

- `probe_mechanism1_guard.py` → `mechanism1-guard-evidence.json`
- `render_evidence_doc.py` → `docs/research_gap_evidence_2026-09-13.md` §1.3.1

## 2026-09-13（补证片五）：三条 strict 失败的精确条件

### 结果（读 strict lane 实际读取的对象）

`publication_method_writer` 的 strict 判定读 **research agenda**（不是 coverage 对象）：
`must_cover` 且 `status == "partial"` 时，必须同时具备 `supported_claim_ids`
与全部 `terminal == "explicit_gap"` 且带 `attempted_tools` 的 `gap_requirements`。

冻结 Run E 三条 must_cover 的实际状态：

| obligation | status | supported claims | gap requirements | terminal gap | 未满足 typed 要求 |
|---|---|---|---|---|---|
| `O-METHOD-MAINLINE-01-c8146479` | partial | 11 | 0 | False | `typed_semantic:transformations:scores`、`typed_predicate:FILTER`、`typed_predicate:SELECT` |
| `O-STAGE-01-039a963a` | partial | 1 | 0 | False | `typed_predicate:SELECT`、`typed_predicate:TRANSFORM` |
| `O-STAGE-03-2c5bd758` | partial | 8 | 0 | False | `typed_predicate:FILTER` |

直接原因是 **partial 但没有任何 terminal gap 记录**（`gap_requirement_count=0`），
并非“没有证据”（每条都已有 supported claim）。这也修正了上一片按 coverage 对象
（`O-STAGE-01` coverage=supported）作出的推断：strict 与 coverage 读的是不同对象。

下一步：要么补齐上表未满足的 typed 要求（`FILTER` 已有可编译证据线索），
要么为剩余要求写带 `attempted_tools` 的 terminal `explicit_gap`；
计入 `SELECT`/`TRANSFORM`/`transformations:scores` 的定向检索。

### 产物

`localize_strict_failures.py` → `strict-failure-localization.json` →
`docs/research_gap_evidence_2026-09-13.md` §2.1

## 2026-09-13（补证片六）：未满足 typed 要求的定向检索

对 §2.1 列出的未满足要求做定向检索（冻结快照、生产工具、模型调用 0）：

| 要求 | 线索 | 状态 |
|---|---|---|
| `SELECT` | 无字面命中（`select`/`argsort` 均 `success_empty`），但 `topk` 命中 `src/utils.py:41/51` | 需按 topk/排序类操作解释谓词 |
| `TRANSFORM` | 命中集中在配置/依赖（`conf/retrieval_model/*.yaml:7`、`requirements.txt:19`），无可编译变换操作 | 未定位 |
| `transformations:scores` | `data/real/MS_MARCO_v2/preprocess.py:51-76`（8 条截断命中） | 待读取编译 |
| `FILTER` | `main.py:34`（单条）；`mask` 命中注意力模型 139–141 等 | 与 §1 同源 |

三组检索的回执分别为 `receipt:282cb307beaea049`、`receipt:f0337ea76f93a837`、
`receipt:a216cafff28d876c`，全部 `search_frontier_closed=false`
（`search_result_truncated`、`search_ledger_has_no_read_candidate`，未读 26/16/9）
→ 未写回任何负结论，仅登记为下一轮读取/编译候选。

产物：`probe_remaining_requirements.py` → `remaining-requirement-evidence.json` →
`docs/research_gap_evidence_2026-09-13.md` §2.2。

## 2026-09-13（补证片七）：未满足要求的编译探针

对 §2.2 的候选文件（`src/utils.py`、`MS_MARCO_v2/preprocess.py`、`main.py` 与两个注意力模型文件）
用生产抽取器编译（1000 节点 / 761 条 supported fact），再对齐三条 strict obligation 中带
`SELECT/ SORT/ TOPK/ TRANSFORM/ FILTER/ MASK` 的 target：

- **7/9 对齐为 `resolved`**：`TRANSFORM`、`SORT`（SELECT 家族）、`MASK`（FILTER 家族）都取得可编译事实；
- 2 个仍 `partial`（`target-22340e7ccc67`、`target-b28bcf95a54c`，谓词已命中但状态未满）。

有界结论同上：这证明**冻结树中已存在可编译证据**，Run E 的 strict 缺口是搜索/读取覆盖问题；
不写回 disposition、不关闭 frontier，也不等于生产路径会判 supported。

产物：`close_remaining_targets.py` → `remaining-target-compile.json` →
`docs/research_gap_evidence_2026-09-13.md` §4.1。

## 2026-09-13（计量片二）：提案计量落成 durable 产物

- `proposal_call_accounting.accounting_from_plan_trace(trace)`：从 narrative plan trace 的
  `proposal_call_rows` / `proposal_call_totals` 重建 `ProposalCallAccountingV1`；
  **没有实测行时返回 `None`**（“recorded” 不会变成 “measured”）。
- `publication_method_writer` 在构建 narrative plan 之后把该 tally 写成
  `artifacts/06_authoring/proposal_call_accounting_v1.json` 并登记 `paths["proposal_call_accounting_v1"]`；
  写入失败不阻塞 authoring（计量是证据，不是门禁）。
- 测试：`tests/test_agentic_proposal_call_accounting.py` 增至 **11 项**，新增 trace→产物重建/回读一致性
  与“无实测行不得伪造 tally”。相关套件 177 passed。
- 仍未完成：把提案调用并入统一 invocation plan 的 run 级 planned/reserved 预留与发送前扣账；
  产品 runner 侧真实 tokenizer 校准。

## 2026-09-13（计量片二复核）：离线链在写入计量产物后仍逐字节一致

本轮 writer 侧新增了 proposal 计量产物的写入分支，因此重跑冻结 Run E 离线链复核：
`offline-ebcar-r10-metering2.json` 与既有 `offline-ebcar-r10.json` 的 project payload
**逐字节一致**（archive `58ad15ef…`、887 atoms、131 页/4 worksets、`failure_details=[]`、
五个准入码不变）。原因：离线链没有 provider key，提案 caller 不构建，计量分支不激活。
规范报告已用该次运行刷新，`r10-summary.json` 随之重新派生（24 文件 + 报告 sha256 同源）。

## 2026-09-13（检查点复核）：全量静态在当前代码上通过

在“提案计量 durable 产物 + 离线链复核”之后的当前工作树上重跑全量静态：

```text
python -m pytest -q tests/ -p no:randomly
3441 passed, 3 skipped, 7 warnings, 12 subtests passed in 523.06s
```

`python -m compileall -q src tests scripts` 与 `git diff --check` 亦通过。
本计数覆盖本轮全部生产改动（`proposal_call_accounting.py`、`narrative_organization_proposal.py`、
`method_architect.py`、`publication_method_writer.py`、`core/output_names.py`）；
此前记录的 `3440 passed` 是计量片一之后的检查点。

## 2026-09-13（计量并账前置定位）：run 级并账的确切插入点

下一片若要完成“提案调用并入统一 invocation plan 的 run 级预留/发送前扣账”，已定位到的确切事实：

- 统一预算角色是**封闭四元组**：`unified_context_compiler.UNIFIED_BUDGET_ROLES =
  ("formalizer", "writer", "realizer", "binder")`（第 83 行）；envelope 的
  `request_budget_by_role` / `max_request_input_tokens_by_role` 都只按这四个角色生成
  （第 2703/2725/2761 行）。提案角色 `method_proposition_architect`
  （`llm/role_config.py:80`）**不在**该集合内。
- run 级计划注册点：`publication_method_writer.py:3257`（writer 计划）、
  `publication_method_writer.py:17224`（realizer 计划）、`formalization_agent.py:2476`
  （formalizer 计划），均调用 `unified_invocation_ledger.register_invocation_plan`。
- 因此并账有两条互斥路线，必须在实现前选定并写入执行记录：
  1. **纳入计划**：把提案角色加入 `UNIFIED_BUDGET_ROLES` 与 profile/env 预算字段，
     让 envelope 为它生成 `RoleRequestBudgetV1` 与 per-request cap，再按同一
     `account_unified_request_tokens` 在发送前扣账、写 ledger receipt。
     代价：改动统一预算契约与 profile，需同步更新冻结 profile 摘要与全量测试。
  2. **计划外但受控**：保持四角色契约不变，提案调用继续使用当前 caller 边界 tally
     （planned/reserved/measured/spent/unsettled + durable 产物），并在 run 汇总里显式标注
     `invocation_plan_membership=recorded_not_in_invocation_plan`/`measured_with_proposal_accounting`，
     不把它计入 run 的 planned/reserved。代价：run 级总账不含提案调用，
     必须在准入/汇总中可见，避免被误读为“已全部计量”。
- tokenizer 校准：`measure_unified_tokens` 支持 `meter.method == "model_tokenizer"` +
  `tokenizer.encode`；产品路径要在 runner 侧把实际 tokenizer 传进
  `proposal_call_meter_from_envelope(..., tokenizer=...)`（writer 作用域没有 tokenizer，
  当前实现按诚实原则返回 `None`，即保持未计量）。

### 并账路线现状（未改契约，仅陈述事实）

当前代码实际处于**路线 2（计划外但受控）**：统一预算契约仍是四角色
（`UNIFIED_BUDGET_ROLES`），提案调用的计量只存在于 caller 边界 tally 与
`proposal_call_accounting_v1` 产物中，`invocation_plan_membership` 字段显式区分
`recorded_not_in_invocation_plan` 与 `measured_with_proposal_accounting`，
**未**计入 run 的 planned/reserved。

因此：
- 不存在“提案调用已被 run 级计划计量”的错误声明空间——归属由字段与产物共同说明；
- 路线 1（把提案角色纳入统一预算/envelope/发送前扣账）会改动统一预算契约与 profile 摘要，
  属于需要显式决策与全量复验的改动，尚**未**执行，也未在本轮擅自执行；
- 该选择的触发条件：当需要把提案调用计入 run 总账、或 live 计量需要对账时，走路线 1；
  在此之前路线 2 是当前状态而非“已完成 run 级并账”。

## 2026-09-13（计量片三）：route-2 的 run 汇总可见性

在路线 2（计划外但受控）下补齐“可见性”要求：`run_autonomous_method_agent` 在最终写
`run_summary.json` 之前，若 writer 已产出 `paths["proposal_call_accounting_v1"]`，
则把 tally 与摘要写入 run summary（`proposal_call_accounting` / `proposal_call_accounting_digest`）。

- **无实测提案调用的 run 不新增任何键**：因此既有测试、产品产物与冻结 Run E 离线链不受影响；
- 有计量时，summary 中的 `invocation_plan_membership` 明确说明它属于 caller 边界计量
  （`measured_with_proposal_accounting`），不是 run 级 planned/reserved；
- 计量失败/文件缺失一律静默跳过（计量是证据，不是门禁）。

验证：`tests/test_agentic_proposal_call_accounting.py`（12 项）+ `test_agentic_autonomous_method_agent.py`
+ `test_agentic_publication_method_writer.py` → **186 passed**；`compileall`、`git diff --check` 干净。

## 2026-09-13（交付节点 A）：分支控制关系与支配推导修复

按 [产品主链诊断与推进指导](../docs/research_to_method_product_delivery_guidance_2026-09-13.md) 的节点 A 执行。

### 生产入口消费了什么变化

- `python_behavior_adapter._BehaviorRelationVisitor`：新增互斥分支臂登记
  （`_exclusive_arm_groups`，绝对快照行范围）与 `_ast_span_id`/`_span_lines` 辅助；
  `add_sequential_control_relations` 现在
  1. **不再**在同一条 `if` 的两个互斥臂之间生成 `NEXT_CONTROL`（臂边界不是执行顺序），
  2. 改为把每个臂的末节点连到 `if` 之后的第一条语句（真实的控制流汇合点）。
- 支配推导（`mechanism_context_compiler._branch_dominance_guards`）与冲突处理**未改动**：
  真正的双极性冲突依旧被识别并保持 `unknown`。

### 哪一个当前阻塞消失

指导方诊断脚本 `branch_dominance_control.py` 在**生产代码**上重跑（模型调用 0，源码零漂移）：

| 指标 | 修复前 | 修复后 |
|---|---|---|
| 最小 if/else 伪冲突 | 1 | **0** |
| 冻结重建中的跨臂边 | 2 | **0** |
| `mech_sym:9773c5add7af1f92` operation / unresolved / completeness | 157 / 6 / `operation_disposition_unresolved` | **157 / 0 / []** |
| `mech_sym:f6cf5bdfe2ae16f0` operation / unresolved / completeness | 217 / 2 / `operation_disposition_unresolved` | **217 / 0 / []** |

真实冲突门保持：`test_graph_branch_dominance_reports_polarity_conflict`、
`test_polarity_conflict_keeps_operation_unresolved` 通过（人工赋予同节点正负两条 typed 分支边仍被拒绝）。

### 新增可验证产物

- `tests/test_agentic_branch_control_relations.py`（2 项）：断言臂间不存在 `NEXT_CONTROL`、
  每个臂都与 `if` 之后的语句有汇合边；
- `.tmp/c2p-product-path-audit-20260913/branch-control.json`（由指导方脚本重跑覆盖）
  现在记录 0 跨臂边、0 unresolved、无完整性失败。
- 相关套件：mechanism/behavior/branch 共 **161 passed**。

### 节点 A 的冻结链复核（新目录）

按指导方要求使用新目录绑定本次代码状态与输入身份：

- `.tmp/c2p-branchfix-checkpoint-20260913/offline/offline-ebcar-branchfix.json`（原始报告）
- `.tmp/c2p-branchfix-checkpoint-20260913/offline/summary.json`（派生汇总，**22 个绑定文件**
  含本轮改动的 `python_behavior_adapter.py`、`mechanism_context_compiler.py`、
  `unified_context_compiler.py`、`proposal_call_accounting.py`、`narrative_organization_proposal.py`、
  `method_architect.py` 等，报告 sha256 同源）

对照（修复前 → 修复后）：

| 项 | 修复前 | 修复后 |
|---|---|---|
| 准入失败码 | 2×`operation_disposition_unresolved` + 3×strict partial | **仅 3×strict partial** |
| archive | `58ad15ef…`（887 atoms） | `463c46ea…`（887 atoms） |
| 页/worksets | 131 / 4 | **135 / 4** |
| 调用计划 | 65 / 18 / 18（101 次） | 66 / 18 / 18（**102 次**） |
| `failure_details` | `[]` | `[]` |
| 三阶段 admission | fail | fail（尚未执行；计划可编译） |

结论：节点 A 在冻结链上闭环——两个结构门消失，operation 数与真实冲突门保持；
剩余失败码只剩 strict 三项（与 Candidate Research gate 分属不同 lane）。
按指导，分支修复后需重新编译工作集与调用计划：本次已重新编译（135 页 / 102 次调用），
后续计量与 Candidate 准入应以该新计划为准，不再引用修复前的 101 次/1,938,180 tokens 额度。

## 2026-09-13（交付节点 B 分析）：Candidate 阶段准入尚未按 lane 分列

在节点 A 之后同一检查点上读取离线报告（`.tmp/c2p-branchfix-checkpoint-20260913/offline/offline-ebcar-branchfix.json`）：

| 项 | 结果 |
|---|---|
| Candidate Research gate | **pass**（`candidate_gate_pass=True`、`candidate_failure_codes=[]`、handoff `eligible`、重认证失败 `[]`） |
| 结构完整性 | 两机制 `completeness_failures={9773…: [], f6cf…: []}` —— 节点 A 已闭环 |
| strict lane | 三条 `core_intent_partial_without_terminal_gap`（单独记录，与 Candidate 不同 lane） |
| 三阶段 admission | 仍为 `fail`，`admission_failure_codes` **只含 strict 三条** |

根因（生产/离线在同一处）：`run_unified_ten_project_offline_matrix.py` 的三处阶段准入
（`phase_admissions["formalizer"|"writer"|"realizer"]`，约 1145/1214/1244 行）都传
`research_failures=_research_gate_failures(research)`，即**严格 lane**；而同一脚本在
`_research_mode_failures`（1007 行）已经算出 `candidate_research_failures`，只用于并列报告，
未进入阶段准入。

节点 B 的最小实现（下一片）：

1. 在三处 `evaluate_unified_live_admission_v1(...)` 旁增加同参数、`research_failures=candidate_research_failures`
   的第二次求值，记为 `phase_admissions_candidate[phase]`；
2. `_phase_row`（约 895 行）在 `admission_failure_codes` 之外增加 `candidate_admission_failure_codes`，
   报告并列展示两个 lane，不改变 strict 结论；
3. 用同一代码/输入重跑离线链，确认 Candidate 三阶段准入为 pass（或给出其真实的第一个阻塞），
   strict 三条继续单列。
4. 计量并入统一 run 预算：按指导选择“纳入统一预算”，为提案角色/调用类别补最小预算与调用身份合同，
   复用现有 attempt 身份与 durable started，验证“开始后中断再恢复”和“超额发送前拒绝”，
   并验证四角色兼容性；新计划基线为 135 页 / 102 次调用（66/18/18）。

## 2026-09-13（交付节点 B 之一）：Candidate 阶段准入按 lane 分列

### 生产入口消费了什么变化

`scripts/run_unified_ten_project_offline_matrix.py`：
- 新增 `phase_admissions_candidate`，在 formalizer/writer/realizer 三处用**完全相同的参数**、
  以 `research_failures=candidate_research_failures` 再求值一次真实准入
  （此前三处都只按严格 lane 求值）；
- `_phase_row` 并列输出 `candidate_status` 与 `candidate_admission_failure_codes`；
- 项目级 `failure_codes`/`status` 仍按严格 lane 汇总，strict 结论未被改写或放宽。

### 哪一个当前阻塞消失

冻结 Run E（同一代码/输入，`.tmp/c2p-branchfix-checkpoint-20260913/offline/`）：

| phase | strict | candidate | calls | strict codes | candidate codes |
|---|---|---|---|---|---|
| formalizer | fail | **pass** | 66 | 3 | **[]** |
| writer | fail | **pass** | 18 | 3 | **[]** |
| realizer | fail | **pass** | 18 | 3 | **[]** |

Candidate Research gate：`pass`、`candidate_failure_codes=[]`、handoff `eligible`；
archive `463c46ea…`（887 atoms）、135 页 / 4 worksets。strict 三条
`core_intent_partial_without_terminal_gap` 单列保留。

### 新增可验证产物

- `.tmp/c2p-branchfix-checkpoint-20260913/offline/offline-ebcar-branchfix.json`（规范报告，含两 lane）
  与 `summary.json`（22 个绑定文件 + 报告 sha256 同源，含 `candidate_status`）；
- `tests/test_agentic_unified_ten_project_offline_matrix.py` 6 passed。

### 节点 B 剩余

计量并入统一 run 预算：按指导为提案角色/调用类别补最小预算与调用身份合同，复用现有 attempt 身份与
durable started，验证“开始后中断再恢复”“超额发送前拒绝”，并验证四角色兼容；
新计划基线 **135 页 / 102 次调用（66/18/18）**。

## 2026-09-13（节点 B 计量，受阻点记录）：`BUDGET_FIELD_BY_ENV` 是必需字段契约

尝试为“提案角色纳入统一预算”加入第五个角色时确认了一个硬约束，记录下来以免重复试错：

- `unified_context_compiler.BUDGET_FIELD_BY_ENV` 的每个条目都会被
  `read_unified_budget_profile` 读取，并在 envelope 构建处作为**必需字段**校验
  （缺失即 `unified_invocation_budget_missing: profile budget is missing required fields: [...]`）。
  因此**不能**把“可选角色列表/其预算字段”直接注册进该映射——会让所有现有 profile 失败
  （实测：`tests/test_agentic_unified_context_compiler.py` 6 failed）。
- 正确做法（下一片实现）：新增一个可选的读取路径
  （例如 `read_unified_optional_budget_profile(env)` → `extra_roles` + 该角色的四个预算字段），
  在 `build_run_invocation_budget_envelope_v1` 里合并：未声明 → 四角色契约与 envelope 摘要不变；
  声明完整 → 第五角色进入 `role_calls`/`request_budget_by_role`/`max_request_input_tokens_by_role`，
  声明不完整 → fail closed。
- 该实验已完整回滚（`git diff` 中 `unified_context_compiler.py` 只剩此前轮次的改动），
  编译器套件恢复 16 passed。

节点 B 计量剩余项不变：可选角色预算读取路径 → 提案调用按现有 attempt 身份/durable started 记账 →
验证“开始后中断再恢复”“超额发送前拒绝”→ 四角色兼容性与新计划（135 页 / 102 次调用）复跑。

## 2026-09-13（节点 B 计量之二）：提案角色可选纳入统一预算

按指导选择的“纳入统一预算”方向，用**可选读取路径**实现（不触碰必需字段契约）：

- `unified_context_compiler` 新增 `CODE2PAPER_UNIFIED_EXTRA_ROLES` 与
  `read_unified_extra_roles(env)`：列出角色即要求同时给出 `max_<role>_calls`、
  `output_token_reserve_<role>`、`max_request_input_tokens_<role>`、
  `scaffolding_token_reserve_<role>`；缺一即 `unified_invocation_budget_missing` fail closed。
- `build_run_invocation_budget_envelope_v1` 通过 `declared_extra_roles(profile_budget)` 把
  已声明完整的角色并入 `role_calls`，于是自动获得 `RoleRequestBudgetV1` 与 per-request cap。
- 接线：`publication_method_writer`（envelope 构建处）与离线矩阵 `_parse_budget` 都先
  `read_unified_budget_profile` 再 `update(read_unified_extra_roles(...))`。

实测（本地 envelope 构造）：

| 场景 | 结果 |
|---|---|
| 未声明 extra roles | 角色集合仍为 `binder/formalizer/realizer/writer`，envelope 摘要不变（`866ce853…`） |
| 完整声明 `method_proposition_architect` | 角色集合 +`method_proposition_architect`；其 reserve（prompt 20 / output 64 / thinking 0 / scaffolding 0）与 cap 256 进入 envelope；摘要改变（真实契约变更） |
| 只声明角色、缺字段 | 拒绝：`extra roles [...] are declared ... but missing budget fields` |

测试：`tests/test_agentic_proposal_call_accounting.py` **14 项**（新增可选角色契约测试：
默认四角色不变、opt-in 生效、半声明拒绝）；编译器/矩阵/writer-unified 套件 31 passed。
`git diff --check` 干净。

下一步（节点 B 收尾）：让提案调用真正走统一 attempt 身份与 durable started（
`publish_attempt_started`/`publish_attempt_completed`）+ 发送前按上述 cap 扣账，
并验证“开始后中断再恢复”“超额发送前拒绝”，随后复跑 135 页 / 102 次调用计划。

## 2026-09-13（节点 B 计量之三，收尾）：提案调用的发送边界与 durable started

节点 B 计量剩余项已实现并验证，范围保持在“复用统一 run 预算与调用身份语义”，未新增平行权威账本、
未伪造 page/workset 身份：

- **发送前上限**：`proposal_call_meter_from_envelope` 把 envelope 的
  `max_request_input_tokens_by_role[role]` 同时作为 `max_input_tokens`；`narrative_organization_proposal`
  在测量之后、调用模型之前比较，超限则该 attempt 记为 `failed`
  （`error=proposal_call_budget_exceeded:<measured>><cap>`）并按已测量输入扣账，**模型不会被调用**。
- **durable started**：`persist_proposal_call_state` 在 `begin` 之后、请求发出之前把 tally 写入
  `<out_root>/artifacts/06_authoring/proposal_call_accounting_v1.json`（与已注册产物同名同路径），
  `finish` 后再写一次；中途被杀死的进程会留下 `pending` 行。
- **恢复语义**：`load_durable_accounting` 在构造 caller 时回读该文件（角色不匹配则拒绝采用，
  避免把“别人的 token”当成本 run），于是恢复运行看到 `unsettled_call_ids`，
  同一 kind+target 的 attempt 编号继续递增（不会重用中断的身份）；
  `carry_over_unsettled` 保证后续 `accounting_from_plan_trace` 重写该文件时不会丢掉更早的未结算行。
- **为什么不写进页面 ledger**：`unified_invocation_ledger.unsettled_started_attempt_records`
  会拿每个 started 记录去当前 plan 里匹配 invocation，匹配不到即标为
  `plan_source == "unknown"`，而该模块文档明确要求 unknown 必须**阻塞** run-budget 决策而非按 0 计。
  提案调用不占页面 invocation，塞进去只会制造一个无法解析的 started 记录并阻塞预算——因此
  membership 标签保持诚实的 `measured_with_proposal_accounting`（“已按 run 预算计量”），
  而不是宣称 page/plan 成员。
- **真实 tokenizer 校准路径**：`run_publication_method_writer` / `_run_publication_method_writer_impl`
  新增可选 `proposal_tokenizer`，直接进入 `proposal_call_meter_from_envelope(tokenizer=...)`：
  提供即按 `measure_unified_tokens` 的 tokenizer 规则测量（identity 必须与 envelope 声明一致），
  未提供且 envelope 声明 `model_tokenizer` 时返回 `None` → 提案调用保持
  `recorded_not_in_invocation_plan`，不用代理规则冒充 tokenizer 计量。本 run 的 profile
  未声明 tokenizer，故提案调用与全 run 一样使用保守 meter，规则一致。
- **可选角色的 cap 必须容得下真实请求**：`max_request_input_tokens_<role>` 现在同时是发送前上限。
  用保守 meter 量一个代表性 `narrative_organization` 请求（prompt 242 / payload 13 / schema 88）
  约 **343 token**；因此测试中的示意值取 1024（不是 256，256 会拒绝真实请求），
  真实 run 声明该角色时应按实际请求规模给足 cap。

### 验证

- `tests/test_agentic_proposal_call_accounting.py` **21 passed**（新增 7 项：durable started 在调用期间
  已可见、恢复后 unsettled 保留且 attempt 递增、外部角色 tally 不被采用、carry-over 保留未结算行、
  超限发送前拒绝且模型零调用、envelope cap/durable 路径绑定、注入 tokenizer 后按 tokenizer 规则计量
  且未注入时不伪造）。writer 相关套件 166 passed。
- 相关套件：proposal accounting + unified matrix + writer-unified + unified compiler **50 passed**。
- 冻结链复跑（节点 A 基线回归）：`.tmp/c2p-nodeb-metering-checkpoint-20260913/offline/`
  的规范报告与节点 A 报告 **sha256 完全相同**（`sha256:9bd4e535…`）——135 页 / 102 次调用
  （66/18/18）、archive `463c46ea…`、strict 仍只有三个 agenda partial 码、
  三阶段 `candidate_status=pass` 且 `candidate_admission_failure_codes=[]`；
  捆绑文件与输入身份写入 `summary.json`（23 个文件 sha256 + HEAD）。

节点 B 至此收尾；下一节点 C（受权的一次受控 EBCAR 正文入口运行）需按授权与 live admission 执行。

## 2026-09-13（节点 C）：受控 EBCAR authoring 实跑 —— 第一处真实阻塞及有界修复

授权与准入：按执行计划“后续运行由 Codex 在实际分片验收与既有授权范围内执行”和交付指导节点 C，
在本地已授权 runtime 上执行一次受控 EBCAR authoring；未做发布/D5/Verified 结论。

**preflight（已记录）**：`http://127.0.0.1:8006/v1` `/health` 200、模型 `qwen38-27b-nvfp4`、
context 131072、`num_requests_running=0`、`num_requests_waiting=0`、`kv_cache_usage_perc=0`；
profile `tests/live/profiles/qwen38_vllm_budgeted.example.env`（含 unified 预算段）。
证据：`.tmp/c2p-nodec-checkpoint-20260913/preflight_*.{txt,json}`。

**run 1**（`/tmp/c2p-nodec-ebcar-unified-20260913-202117`，exit 2，37 calls / 324182 tokens）：
- 阻塞：`research_closure_admission_failed:unified_core_intent_terminal_proof_missing:O-METHOD-MAINLINE-01-c8146479,O-STAGE-01-039a963a,O-STAGE-03-2c5bd758`。
- 诊断（离线复现，零模型调用）：`_writer_research_preadmission_failures` 在“fresh root 只有旧研究复制集”时
  确实产出上述三个码；加入 `candidate_handoff_v1` + `observation_promotion_ledger_v1` +
  `candidate_retry_ledger_v1` 后，handoff 认证通过（eligible=True、revalidation failures 为空）、
  preadmission failures **为空**。根因是**生产入口的复制边界**：`scripts/run_authoring_replay.py` 的
  `RESEARCH_COPY_ARTIFACTS` 早于 Candidate 交接产物，fresh root 里没有 Writer 必须认证的 Candidate 权威，
  于是回退到 strict terminal proof。
- 有界修复：`OPTIONAL_RESEARCH_ARTIFACTS` 增加 `candidate_handoff_v1`、`observation_promotion_ledger_v1`、
  `candidate_retry_ledger_v1`、`research_revision_journal_v1`（可选：缺失时行为不变、由 Writer 自身 fail closed）。
  回归测试 `tests/test_agentic_replay_execution_record.py::test_candidate_lane_research_authority_is_carried_into_the_fresh_root`；
  套件 24 passed。绑定真实输入的复制边界探针：`analysis/copy_boundary_probe.json`（`writer_would_block: false`）。

**run 2**（`/tmp/c2p-nodec-ebcar-unified-20260913-203506`，exit 2，37 calls / 324182 tokens）：
- research closure admission **不再阻塞**，进入统一主链并产出 `method_section_plan_v2.json`，
  随后在统一源码读取处失败：
  `unified_pipeline_failed:ValueError:unified_source_read_failed:unified_source_partition_excluded:conf/dataset/conteb_test_01MLDR.yaml;…`。
- 定位：`repo_snapshot.py:351-355` 把 `_EXCLUDED_SOURCE_KINDS = {vendor, generated, submodule,
  dataset_or_checkpoint}` 记为 `unified_source_partition_excluded` 并返回空；`publication_method_writer.py:2010-2020`
  把**任何** source-read failure 直接提升为 `ValueError` → 整条 unified lane 中止。
  `repository_source_manifest_v1` 共 37 条：`dataset_or_checkpoint` 16、`first_party_executable` 11、
  `documentation` 5、`configuration` 5；被排除集合含 `conf/dataset/*.yaml`、`data/real/*/preprocess.py`、
  `src/dataset/*.py`。
- 未做的决定：是否把“已声明的分区排除”与“完整性/可用性失败（逃逸、未登记、缺失、不可读、摘要漂移、symlink、binary）”
  分开——前者是可预期分类结果，后者必须继续中止。这触及 R2 的 fail-closed 语义，需明确后再改，
  不以放宽门禁换取一次通过。

证据汇总：`.tmp/c2p-nodec-checkpoint-20260913/nodec_evidence.json`（含两次运行的 blocker、用量、
代码状态摘要与修复前后对照）；两次运行都由同一 `src` 代码状态 `sha256:4fe7c0ba…` 绑定（运行中无漂移）。

### 节点 C 阻塞 2 的有界修复：分区排除 ≠ 完整性失败

run 2 的真实阻塞是统一源码读取把“清单已声明的分区排除”和“完整性失败”混为一谈：

- `repo_snapshot.py` 新增 `PARTITION_EXCLUSION_FAILURE_CODE` 与 `split_source_read_failures()`：
  以 `unified_source_partition_excluded:` 开头的记录归为**声明式分区排除**，其余（path escape/
  invalid、not-in-manifest、missing、unreadable、content/snapshot digest mismatch、symlink、binary）
  仍为阻塞失败。
- `publication_method_writer.py` 把源码门拆成 `_unified_source_read_failures()`：
  阻塞失败照旧 `raise ValueError("unified_source_read_failed:…")`（R2 语义不变）；
  分区排除改为写入已注册产物 `unified_source_partition_exclusions_v1`
  （`artifacts/research_product/…`，含 `excluded_paths` 与 `content_digest`）并在 `paths` 中可见，
  不再中止整条 unified lane。
- 语义边界：分区排除只是“清单从未承诺这些字节可读”，既不授权任何事实，也不把空文本当证据；
  需要这些文件的 consumer 会因此拿到空源文本，其后果由后续真实门禁决定（下一处阻塞若出现即按同一方式有界修复）。

测试：`tests/test_agentic_authoring_context_handoff.py` 新增
`test_partition_exclusion_is_not_an_integrity_failure`（混合输入下 integrity 失败仍阻塞、分区排除去重保留、
无 failure 的 reader 不崩、产物路径与注册名一致）；该文件 11 passed，
writer unified/legacy 套件 164 passed。

### 节点 C run 3（修复后）：阻塞前移一层，暴露真实的下游根因

`/tmp/c2p-nodec-ebcar-unified-20260913-205759`（exit 2，37 calls / 324182 tokens，代码状态
`sha256:09dd9499…`）：

- 分区排除修复生效：产物 `artifacts/research_product/unified_source_partition_exclusions_v1.json`
  写出 16 条被排除路径，unified lane 不再因它们中止。
- 新阻塞：`unified_pipeline_failed:ValueError:unified_live_admission_failed:mech_sym:f6cf5bdfe2ae16f0:operation_disposition_unresolved`。
- 逐层定位（全部来自该 run 的产物）：
  - `mechanism_context_completeness_v1`：`mech_sym:9773c5add7af1f92` → `[]`；
    `mech_sym:f6cf5bdfe2ae16f0` → `['operation_disposition_unresolved']`。
  - 注解后的闭包 disposition 统计：125 ops 全部分类（115 supporting + 10 absorbed）；
    185 ops 中 **2 个** `explicitly_unresolved`（reason `unresolved_detail:…:39` / `…:40`）。
  - 这 2 个操作是 `span:src/model/ebcar_dedicated_attention_model.py:171:171`（WRITE）与
    `:171:174`（CALL，`torch.zeros`），`guard=""`、`active_path_status="unknown"`——它们位于
    `if self.cfg.use_dedicated_attention:` 的 **else（ablation）分支**。
  - **根因（输入侧证据缺口）**：冻结的 `configuration_claims_v1` 只有 3 条，其中
    `self.cfg.use_dedicated_attention` 与 `self.cfg.add_positional_encoding` 都是
    `state=unresolved`、`unresolved_reason=config_access_unresolved:no_definition_or_entrypoint_value_evidence`。
    分支条件取值无法判定 → else 臂操作 active path unknown → detail `evidence_authority=unresolved`
    → `explicitly_unresolved` → 完整性门 fail-closed。
  - 附带发现的**权威分区矛盾**：同一清单把 `src/dataset/ebcar_dataset.py` 归为
    `dataset_or_checkpoint`（排除），而唯一一条已解析的默认值 claim（`EBCARDatasetReal.__init__`）
    的 definition span 正是 `span:src/dataset/ebcar_dataset.py:27:27`；`conf/` 侧的
    `conf/config.yaml`、`conf/retrieval_model/{contriever,e5}.yaml`、`conf/validation_dataset/conteb_val.yaml`
    在 configuration 分区内，却没有 claim 把其中取值链到 `self.cfg.*` 访问。

结论：这不是门禁缺陷，也不是 writer 侧可修的表达问题，而是**冻结输入缺少配置定义证据**（以及数据集模块的分区归属需要重新判定）。
按“不削弱门禁、真实阻塞按所属阶段有界修复”的规则，下一步需要先决定配置证据/分区归属的处理方向，
再继续推进 Candidate。

证据：`.tmp/c2p-nodec-checkpoint-20260913/nodec_evidence.json`（run 1/2/3 的 blocker、用量、
根因链、disposition 统计与配置 claim 原文）。

### 分区归属修正（用户决定：先判定 src/dataset/*.py 归属）+ 配置证据缺口定位

分区归属修正（`source_inventory.py`）：
- 旧规则把**任何**路径分片命中数据词表（`data/dataset/datasets/checkpoint/checkpoints/weights/models/artifacts/runs/outputs/results`）
  的文件判为 `dataset_or_checkpoint`，于是 `src/dataset/ebcar_dataset.py`、`src/models/*.py`
  这类**第一方实现**被排除出可读源码分区——而唯一一条已解析的默认值 claim
  （`EBCARDatasetReal.__init__`）的 definition span 恰好落在 `span:src/dataset/ebcar_dataset.py:27:27`，
  形成“权威分区 vs 配置证据”自相矛盾。
- 新规则 `_is_data_container_path()`：数据后缀（权重/数组/checkpoint）永远是数据；**可执行源码**只有位于
  **顶层**数据容器下才算数据（`data/real/x/preprocess.py` 仍是数据工具），
  因此 `src/dataset/*.py`、`src/models/*.py` 回归 `first_party_executable`；
  非源码文件（如 `conf/dataset/*.yaml`）行为不变，避免扩大本次修复范围。
- 回归测试：`tests/test_agentic_14_vertical_tests.py::test_first_party_packages_named_after_data_vocabulary_stay_readable`；
  相关套件 26 passed，`-k "scope or inventory or partition or source_kind"` 79 passed。

配置证据缺口（下一处真实阻塞的完整链条，已定位到能力边界）：
- 代码里**已有**该能力：研究工具 `inspect_configuration`（`research_tools.py:1325`，扫描
  `.py/.yaml/.toml/.json` 的配置绑定，`research_nodes.py:152` 归入 `{"config"}` 需求，
  `research_supervisor.py:829` 负责参数化），并有 packet/fact/配置编译器承接正向证据。
- 但冻结的 Run E 输入没有为 `self.cfg.use_dedicated_attention`/`self.cfg.add_positional_encoding`
  取得定义证据（`state=unresolved`），而这两个键确实定义在**可读的** `conf/config.yaml:18-19`
  （`add_positional_encoding: True` / `use_dedicated_attention: True`，configuration 分区）。
- 因此要拿到首份 Candidate，需要一次**当前入口的完整运行**（Research 真正为这些键调用
  `inspect_configuration` 并产出 packet→fact→claim），而不是继续回放缺证据的冻结输入；
  或用有界的研究续跑补齐这两个键。

结论（本轮交付）：A/B 已完成；节点 C 的受控 authoring 已取得第一处真实下游阻塞的完整因果链与
可复现证据（复制边界 → 分区排除 → 配置定义证据缺失），分区排斥语义按用户确认保留，
分区归属已按用户决定修正。下一步需决定完整 live 运行或研究续跑。

### 确定性配置取证触发（用户决定：先加触发，再跑完整 live）

问题：`inspect_configuration` 工具、packet/fact 承接与 `compile_configuration_claims` 都已存在，
但研究循环没有任何确定性规则要求为“门控分支的未解析配置键”取证，于是冻结输入里这两个键一直是
`unresolved`，first Candidate 被完整性门拦下。

实现（有界、可测、不触碰门禁）：

- `research_nodes.py` 新增 `branch_configuration_evidence_requirements(facts, configuration_claims)`：
  只对 `branches_on` 事实里出现的配置访问叶子键（`self.cfg.<key>` / `cfg.<key>` / `args.<key>` …）生成
  `configuration:branch_key:<key>` 需求；已被解析的 claim（`state ∈ {default, actual, conditional}`）
  不再要求；非 `branches_on` 事实不触发。
- 在 `_compile_candidate_node_impl` 编译出 `fact_set` 后调用它，把需求并入该 obligation 的
  `missing_information`；只要有此类需求，obligation 就**不得**标记为 `supported`
  （`obligation_terminal = all_targets_resolved and not configuration_requirements`），
  证据走 `_partial_evidence` 通道。这加强了 strict lane（partial 仍是 partial），不放宽任何门。
- `_resolved_missing_information` 既有词表已把含 “config/parameter/setting/option” 的需求归入 `config`
  类别，只有成功的 `inspect_configuration` 观测才能解除；`_select_action` 的既有启发式因此确定性地
  选择 `INSPECT_CONFIG`。
- `research_supervisor.py`：`DeterministicSupervisorBackend._configuration_key()` 从待办需求里取出叶子键，
  `inspect_configuration` 的参数由“全库扫描 `config_key=""`”改为传入该键，避免把关键键留给运气。

测试：`tests/test_agentic_branch_configuration_requirements.py` 3 项（生产者语义：未解析才要求、
已解析跳过、非分支事实不触发；路由：待办需求 → `INSPECT_CONFIG` 且 `config_key` 精确等于叶子键；
无需求时仍为通用扫描）；研究侧套件（supervisor/agent/cli/callback）**119 passed**；
全量静态 **3459 passed, 3 skipped**。

随后按用户决定启动**当前入口的完整 live 运行**（Research + unified authoring，8006）：
`python -c "... supervised_method_agent_main ..." run --repo <EBCAR> --author-intent <paperyaml3 EBCAR yaml>
--out /tmp/c2p-nodec-full-20260914-011114 --max-research-turns 60
--llm-profile tests/live/profiles/qwen38_vllm_budgeted.example.env --llm-model qwen38-27b-nvfp4
--authoring-context-mode unified --run-id c2p-nodec-full-20260914-011114`
（代码状态 `sha256:bcd1fdbe…`；preflight 记录在 `.tmp/c2p-nodec-checkpoint-20260913/preflight_full_*`）。

## 2026-09-14（当前执行计划 §15.4）：S1 入口统一与 S2 预算闭合

本轮沿现有 dirty worktree 推进，不重做 R0–R10，不修改 Research 冻结输入，也未把完整
Research 重跑作为 S1/S2 前置。

### S1 结果

- `python_behavior_adapter.py` 的分支祖先关系改为完整 enclosing-branch 路径，终止控制流不再产生
  伪顺序边；新增嵌套 `if/elif/return` 回归。
- `research_nodes.py` 的配置需求按完整访问身份匹配，`other.cfg.mode` 不再消除
  `self.cfg.mode` 的缺口。
- `mechanism_context_compiler.py`、`publication_method_writer.py`、`run_authoring_replay.py` 与
  离线矩阵共用当前源码派生图；历史图只作为显式历史 artifact 保存，不再作为 unified Writer 输入。
- replay 在重建图并通过确定性 Candidate/strict 分列预检后，才允许进入模型阶段；新增
  `--deterministic-preflight-only` 与预检产物/telemetry。

S1 证据：相同冻结 EBCAR 输入的离线矩阵保留三条 strict partial，Candidate handoff eligible；
当前图 `315 nodes / 542 relations`，历史图 `1263 nodes / 3056 relations`，当前图 digest 为
`sha256:42a68…`，无 graph/mechanism completeness failure。实际 replay 预检目录为
`/tmp/c2p-unified-repair-20260914-s1-replay-codex-03`，exit 0、模型调用 0，并写出
`artifacts/06_authoring/deterministic_preflight_v1.json`、`behavior_graph_rebuild_v1.json` 和
`authoring_rebuild_manifest_v1.json`。

### S2 实现与验证

- `proposal_call_accounting.py`：严格 meter 绑定 role/run/revision/envelope/profile/model，
  累计 calls/total/role input 在发送前检查；started tally 原子写入，写失败阻止 transport；
  corrupt/foreign/cross-run tally fail closed；未发送拒绝不计 spend；辅助 wrapper 与 page ledger
  共用 `06_authoring/invocations` 预算根。
- `unified_invocation_ledger.py`：统一读取 page receipts、旧/当前 plan reservations、started
  未结算尝试和 auxiliary tallies；未知原计划不按 0；`check_run_budget_before_send` 成为实际页与
  辅助调用的共同累计门。
- `narrative_organization_proposal.py`、`formalization_agent.py`、Writer/Realizer 实际 send
  boundary 均在 transport 前做预算检查；四角色 profile 未显式声明 auxiliary role 时走既有确定性
  fallback，不能被注入 caller 绕过。
- replay 只有 profile 显式声明完整 extra-role budget 时才启用 planner/verifier/proposal；当前
  `qwen38` profile 仍为四角色，预检 telemetry 标为 `auxiliary_budget.status=not_declared`。

S2 验证命令与结果：

- `python -m pytest -q tests/test_agentic_proposal_call_accounting.py tests/test_agentic_unified_context_compiler.py tests/test_agentic_formalization_guards.py tests/test_agentic_publication_method_writer_unified.py tests/test_agentic_narrative_architect_v3.py tests/test_agentic_replay_execution_record.py tests/test_agentic_unified_ten_project_offline_matrix.py -p no:randomly` → **147 passed**。
- `python -m pytest -q` → **3475 passed, 3 skipped, 7 warnings, 12 subtests passed**，exit 0。
- `python -m compileall -q src tests`、`git diff --check` → exit 0。
- 新增严格回归覆盖：累计调用/总 input 超额、未声明角色、tokenizer 缺失、损坏/跨 run tally、
  started 写失败，所有拒绝场景假 transport 发送次数为 0；正常场景 tally 额度守恒并可恢复。

S2 退出条件已满足。下一步只执行一次绑定当前代码/profile 的受控 S3 authoring；不作默认切换、D5、
Verified 或发布结论。

## 2026-09-14（§15.4 S3：实际入口受控 authoring 结论）

### 运行边界与入口

按 S3 退出条件，使用当前 `run_authoring_replay.py` 实际入口对冻结 EBCAR 输入只运行一次最终
受控 authoring；没有以完整 Research 重跑或配置补证作为前置，也没有切换默认路径。运行目录为
`/tmp/c2p-unified-repair-20260914-s3-codex-05`，命令绑定
`tests/live/profiles/qwen38_vllm_budgeted.example.env`、`qwen38-27b-nvfp4`、unified context，
单并发执行。

运行前 `/health` 与 `/v1/models` 均为 HTTP 200，模型身份为 `qwen38-27b-nvfp4`，上下文上限为
131072；运行前后 running/waiting、KV-cache pressure、preemption、abort/error 均为 0。运行期
Formalizer 完成 66/66，Writer 完成 18/18；Realizer 计划 18 项并写出 18 条 receipt，其中
16 项实际送达 caller，2 项在 caller 前因 authority unresolved 被拒绝并审计为
`sent_to_caller=false`。模型调用没有运行时中止或资源错误。

### 严格结果

本次未取得 Candidate：`execution_record.json` 的 `candidate_digest` 为空，未写出
`authoring_structural_exit_v1.json`，终止原因为：

`unified_consumer_task_incomplete:realizer:inv:realizer:MA-REV-mech_sym-9773c5add7af1f92:page:e3b02f...`

Realizer 的失败属于内容/证据绑定门失败，不是 transport 或预算绕过。18 条 receipt 的结果为：
16 条送达后失败、2 条严格的 pre-send authority rejection；主要失败计数为
`realizer_witness_text_missing` 7、`realizer_detail_out_of_scope` 5、
`realizer_authority_unresolved` 2，以及 formula/atom witness out-of-scope、required detail
missing、response not JSON 各 1。两个未解析 authority 对应冻结输入中
`self.cfg.add_positional_encoding` 与 `self.cfg.use_dedicated_attention` 的配置证据缺口；
它们仍按 strict partial/unknown 保持 fail-closed，未用配置补证或放宽匹配来伪造通过。

本轮为真实入口补上的修复包括：Realizer 嵌套 witness 使用精确的 Pydantic response schema；
Realizer 在 caller 前拒绝时写出 rejected receipt 和 output fragment；所有 pre-send rejection
不计入已发送 spend；相应生产/回归测试均已通过。这些修复改善了审计完整性，但没有放宽
Realizer 的内容、绑定或证据门。

### 验证与交付判断

- `python -m pytest -q` → **3479 passed, 3 skipped, 7 warnings, 12 subtests passed**，exit 0。
- `python -m compileall -q src tests scripts/run_authoring_replay.py` → exit 0。
- `git diff --check` → exit 0。
- S1/S2 退出条件已满足；S3 已按实际入口取得完整运行证据，但 Candidate 退出条件未满足，
  因此不声明 Candidate、Verified、D5、默认切换或发布就绪。

主要产物：

- `/tmp/c2p-unified-repair-20260914-s3-codex-05/execution_record.json`
- `/tmp/c2p-unified-repair-20260914-s3-codex-05/artifacts/06_authoring/realizer_plan_execution_v2.json`
- `/tmp/c2p-unified-repair-20260914-s3-codex-05/artifacts/06_authoring/realizer_receipts_v2.json`
- `/tmp/c2p-unified-repair-20260914-s3-codex-05/artifacts/06_authoring/deterministic_preflight_v1.json`

剩余工作边界明确为 Realizer 的语义/证据绑定修复，以及两个配置 authority 缺口的后续取证；本轮
不继续重复 live，不把严格 partial 改写为成功。

### 2026-09-14：S3-20 终态独立复核与执行文档更新（本轮无生产代码修改）

用户要求判断当前进展并指导修复。本轮读取 S3-18/19/20、当前发送/解析/预算/正文验收路径，
模型调用 0；没有启动新的 live，也没有改写旧 run。

- S3-20 已继续落盘为 116 completed / 116 started、113 次发送、exit 2，execution record 存在；
  最终失败是 Realizer 总预算拒绝，Candidate 和 structural exit 仍不存在。
- Formalizer 34 main + 32 repair 全失败、0 accepted packages；Writer 最后响应为 5 空、3 仅标题、
  10 含非标题文本（未等同内容验收）；Realizer 三次 witness repair 均成功，完成 15/18 页。
- 代码反例：Formalizer 六个 required 字段缺 properties/类型，system/user 重复 payload；
  空 SSE finish 提前抛错漏读 terminal usage；repair 超声明 reserve 且未保护后续 primary；
  Writer receipt 在正文验证前按非空文本记 complete。已知 provider input 也高于全账本估算。
- 已更新统一执行计划 §15.6、顶部/状态表/附录 B 与 docs/README.md：保留 S1/S2，按失败诊断与
  Formalizer 合同 → Writer 内容事务 → 跨 phase 预算/真实计量 → 经验证恢复及完整 Candidate 收口。
  本小节更新此前 S3-05 的“剩余工作边界”，不宣称这些新发现已经修复。
- `python .tmp/c2p-s3-review-20260914/review.py`：exit 0；结果、434 个代码/产物摘要索引及
  8 个 Writer 失败页 + 1 个 Formalizer 诊断样本保存在该工作区目录。样本不是认证恢复包。
- `python -m pytest -q tests/test_llm_runtime.py -k stream tests/test_llm_section_writer.py -k 'stream' -p no:randomly`：
  exit 0，6 passed / 115 deselected。假 SSE 与预算反例另由上述脚本重现。未重复全量静态。
- `git diff --check`：exit 0；新文档链接/空白检查及来源代码摘要稳定性另行核对。

## 2026-09-14（§15.6：失败请求合同、内容验收与预算调度修复）

本轮按用户指定顺序处理 S3-20 暴露的问题；没有重建旧行为图、没有完整 Research 重跑、没有启动
新的 live 或 Candidate 链路。

- `response_schemas.py` 与 `unified_context_compiler.py` 现在对 Unified Formalizer 使用闭合的
  `UnifiedFormalizerResponseV2`：外层 `results` 与每行六个 required 字段均有明确类型，未知字段
  fail closed；`formalization_agent.py` 在默认解析入口再次验证该 schema。Unified V2 请求把技术页
 作为唯一 structured input，prompt 只保留角色合同，避免同一页在 system/user 两处重复计量。
- `client.py`、`formalization_agent.py`、`section_writer.py` 和统一 invocation ledger 保留空流/部分流
  的 partial text、finish/provider finish、terminal usage、事件诊断与 provider diagnostics；SSE 在
  finish 后继续读取 usage-only terminal event。Provider usage 缺失时仍使用已记录的确定性 request
  accounting，并在 run budget state 标为 `partial`，不把估算伪装成已验证 provider usage。
- Writer request record 新增明确的 transport response 状态；`task_status` 不再被内容验收回写为
  “complete”。内容验收另写 sidecar，分别记录 `content_acceptance_status`、
  `repair_committed`、`resume_eligible`。空/阻塞的 primary attempt 也保存 rejected sidecar；只有
  通过段落 transaction/evidence 验收的修复才可成为可复用 incumbent，resume 只读取 accepted
  sidecar。
- Writer section aggregate 现在同时要求 transport response 非空与 `content_accepted=true`；因此
  标题 JSON、仅非空文本或被拒绝的正文不会伪装成完成页。内容 repair 仍由原 invocation 的 bounded
  retry reserve 计量，并保护尚未发送的 primary pages；跨 revision 的 completed receipts、started
  未结算尝试和 provider-usage 缺失状态继续由统一 ledger 汇总。
- 增加空流 late-usage、Formalizer schema、Writer 空/标题修复、rejected/accepted content sidecar、
  repair reserve 与 resume 资格回归夹具。一次修复夹具产物保存在
  `/tmp/c2p-writer-repair-budget4/test_writer_content_repair_use0/`，包含 primary rejected、repair
  accepted 的 content-acceptance sidecar 与两次 transport receipt。

验证结果（本轮新执行）：

- `python -m pytest -q tests/test_agentic_publication_method_writer_unified.py tests/test_llm_runtime.py tests/test_agentic_unified_context_compiler.py tests/test_llm_section_writer.py tests/test_r6_portability_and_budget_hygiene.py -p no:randomly` → **164 passed**。
- `python -m pytest -q tests/test_agentic_formalization_guards.py -p no:randomly` → **53 passed**。
- `python -m pytest -q tests/test_agentic_replay_execution_record.py tests/test_agentic_runner.py -p no:randomly` → **36 passed**。
- `python -m compileall -q src tests`、`git diff --check` → exit 0。

本轮仍未取得有效 live Formalizer package，也未运行完整 Candidate；S3 的退出条件尚未满足，不能据此
声明 Candidate、Verified、D5 或发布就绪。下一步应先用受控入口验证一个有效 package 和一个空页/标题页
内容修复，再决定是否进入完整链路。

### §15.6 夹具收口补充

随后新增的两个实际 Writer 夹具分别覆盖空流页与标题-only 页。页面闸门仅在同一 immutable
invocation 的 primary 为空、且 bounded repair 返回非空响应时恢复；没有 repair 或 repair 仍为空时
继续 fail closed。最新组合回归为 **254 passed**（上述 Writer/LLM/预算/Formalizer/replay 集合），
`compileall` 与 `git diff --check` 仍为 exit 0。夹具产物位于
`/tmp/c2p-writer-empty-title2/`，每个 case 均有 primary rejected 与 repair accepted sidecar。

## 2026-09-14（§15.6 执行推进：T1 真实入口通过，T2/T3 保持边界）

在不修改 S3-20 冻结目录、不重建旧行为图、不启动完整 Research/Candidate 的前提下，继续执行
§15.6 的受控验证。

- 旧的 S3-20 Formalizer plan 在当前入口被 request-envelope digest 检查拒绝，
  `/tmp/c2p-s3-t1-formalizer-micro-20260914-01/formalizer_microtest_result.json` 记录
  `actual_calls=0`；这证明旧计划不能被当前合同直接复用，也没有把旧摘要当作当前产物。
- 按当前源码重建 plan 后，T1-04 在同一冻结 archive/manifest 上实际发送 1 个 Formalizer main，
  消费 1 个真实结构化响应，得到 1 个通过来源/条件/公式校验的 package；`repair=0`、
  `receipt=1`、`task_failures=[]`。结果在
  `/tmp/c2p-s3-t1-formalizer-micro-20260914-04/formalizer_microtest_result.json`，计划摘要为
  `sha256:1170f8316e934f1f0bc72a6822cc34e6322006e8358e0398ff2984401c90ca0b`，请求/响应与
  provider finish/usage 诊断均按 invocation sidecar 保存。此前两次各含 main+repair 的诊断微测
  暴露了复合 `RESHAPE -> WRITE` 的 LaTeX 等价箭头问题，已由提示约束和顺序链校验收口。
- 复核冻结 S3-20 的 Writer fragments：5 页两次均为空流，3 页为标题-only，10 页含非标题文本；
  这些仍是文本形状，不是内容/绑定验收。当前生产入口的空页与标题页夹具均生成 rejected primary、
  accepted bounded repair、`resume_eligible=true` 的 sidecar，产物位于
  `/tmp/c2p-writer-empty-title2/`；但尚未把这两个修复请求重新发送到真实模型，因此真实八页的
  T2 退出条件仍未满足，也不将旧 `complete` receipt 直接升级为可复用正文。
- 新增 provider-free 的真实冻结页回放
  `.tmp/c2p-s3-t2-replay-20260914/t2_replay_result.json`：从 S3-20 的实际 writer manifest、
  narrative plan、page projection 和当前 Writer schema 取一个空页与一个标题页，把历史 primary /
  repair 响应送入当前低层入口。4 个调用均走 `unified_writer_page_v2`，两个 bounded repair 均
  `writer_repair_commits=0`，`page_commit_count=0`、`resume_eligible_page_ids=[]`；该证据证明
  当前闸门不把旧空/标题响应升级为正文，但不冒充新的 provider recovery。
- 修正统一 ledger 的计划持久化：`is_repair` 不再在读取 `plans/*.json` 时丢失，future-primary
  预留不会把 repair 槽误算为主请求。新增反例覆盖 primary 100 / repair 500 的计划形状；累计
  revision、未知 started、最小扣账、repair reserve 与跨 phase 保护回归一并通过。
- 对旧 S3-20 invocation ledger 用当前读取器做只读审计，状态明确为 `provider_usage_status=partial`，
  113 个已发送 receipt 缺 provider usage，确定性 request accounting 为 1,990,033 input tokens；
  这只是保守账本估计，不被报告为已验证真实 token，故 T3 的真实计量退出仍保持未完成。
- 原计划再做至多 1 次真实 Writer repair；按 §16.3 先检查 8006 时，`/health`、`/v1/models` 和
  metrics 均返回 connection refused（HTTP 000），进程列表没有 vLLM/uvicorn。没有启动服务、没有
  发送新的 provider request，也没有把 runtime 不可用误记为 Writer 失败；对应 preflight 输出在
  `/tmp/c2p-s3-t2-live-health-20260914.txt` 与 `/tmp/c2p-s3-t2-live-models-20260914.json`。

本次新验证命令：

- `python -m pytest -q tests/test_agentic_unified_context_compiler.py tests/test_agentic_publication_method_writer_unified.py tests/test_llm_runtime.py tests/test_llm_section_writer.py tests/test_r6_portability_and_budget_hygiene.py tests/test_agentic_formalization_guards.py tests/test_agentic_replay_execution_record.py tests/test_agentic_runner.py -p no:randomly --basetemp=/tmp/c2p-contract-final-focused-20260914` → **256 passed**。
- `python -m pytest -q tests/test_agentic_unified_context_compiler.py -k 'future_primary_reservation_excludes_repairs or run_reservation_is_debited_by_retries_and_resume' -p no:randomly --basetemp=/tmp/c2p-future-primary-budget-20260914` → **2 passed**。
- `python -m compileall -q src tests`、`git diff --check` → exit 0。

当前结论：T1 已有真实有效 package；T2 真实失败页的正文恢复和 T3 provider usage/计量仍未闭合，
因此不启动完整 Candidate。S3-20 的 execution record、失败样本、旧 receipts 和已有 Realizer
witness 修复继续保留，Candidate/Verified/structural exit 均不宣称。

## 2026-09-14（§15.6 continuation：runtime wait 下的 T3 收口准备）

本次继续轮询指定 8006 runtime：`/health`、`/v1/models`、metrics 均 connection refused，未启动
服务、未发送 provider request。为 runtime 恢复后的单步继续，新增
`.tmp/c2p-s3-t2-live-repair-20260914/live_repair.py`：它只接受 fresh output root，先做模型/队列
preflight；primary 使用冻结空页响应，仅允许一个 `retry_max_attempts=1` 的真实 bounded repair，
preflight 失败即 provider call=0。

同时增加缺 usage 的预算回归：有发送 receipt 但 `provider_usage=None` 时，ledger 必须报告
`provider_usage_status=partial`，保留 request accounting 计费并报告 missing input tokens，不能把
该请求当成免费。该反例与 future-primary/repair 排除、累计 reservation 回归本次为 **3 passed**；
live probe 尚未执行，故不把脚本准备误报为 T2 恢复。

## 2026-09-14（§15.6 continuation：repair sidecar 与 resume 资格收口）

运行时仍未恢复，本片没有启动服务、没有发送新的 provider request，也没有改写冻结 S3-20。针对
Writer 失败合同继续做了一个方向内的离线修复：

- `llm/section_writer.py` 的 attempt sink 不再只记录空/blocked 响应，而是把每个 primary/representation
  attempt 写入 content sidecar；bounded repair 若为标题-only、空流、事务拒绝或无单调进展，则在
  不修改送回 Writer 的响应前，以 rejected 结果持久化该 repair attempt。
- `agentic/publication_method_writer.py` 不再按最大 attempt 或 response hash 盲选 receipt；同一
  response hash 在 primary/repair 间重复时，按尚未有 sidecar 的 attempt 绑定。最终 accepted
  callback 在 sidecar 已存在时不重写它，因此不会把有效 incumbent 覆盖到未提交 repair 上。
- 新增 `test_rejected_nonempty_writer_repair_is_not_resume_eligible`：真实统一 Writer producer→consumer
  入口注入 primary 空流与 repair 标题-only，两个 sidecar 均为 `content_acceptance_status=rejected`、
  `resume_eligible=false`，并验证同一 writer plan 的 `build_resume_plan` 返回 `execute`；这不是
  provider recovery，也不将失败页升级为正文。

验证（本片新执行）：

- `python -m pytest -q tests/test_agentic_publication_method_writer_unified.py tests/test_llm_section_writer.py -p no:randomly --basetemp=/tmp/c2p-writer-contract-20260914-r1` → **116 passed**。
- `python -m pytest -q tests/test_agentic_unified_context_compiler.py tests/test_agentic_publication_method_writer_unified.py tests/test_llm_runtime.py tests/test_llm_section_writer.py tests/test_r6_portability_and_budget_hygiene.py tests/test_agentic_formalization_guards.py tests/test_agentic_replay_execution_record.py tests/test_agentic_runner.py -p no:randomly --basetemp=/tmp/c2p-contract-final-focused-20260914-r3` → **258 passed**。
- `python -m pytest -q tests/test_agentic_unified_context_compiler.py -k 'future_primary_reservation_excludes_repairs or missing_provider_usage_without_zeroing_spend or run_reservation_is_debited_by_retries_and_resume' -p no:randomly --basetemp=/tmp/c2p-budget-boundary-20260914-r3` → **3 passed**。
- `python -m compileall -q src tests .tmp/c2p-s3-t2-replay-20260914 .tmp/c2p-s3-t2-live-repair-20260914`、`git diff --check` → exit 0。

当前阶段结论不变：T1 的有效 Formalizer package 保留；T2 真实空/标题页仍无新的 provider 内容，
T3 旧 run 的 113 个缺 usage receipt 仍为 `provider_usage_status=partial`，无 Candidate、无
structural exit、无 Verified。8006 恢复后仍按既有 fresh 单次 Writer repair probe 继续，不做完整
Research 或旧图重跑。

## 2026-09-14（§15.6：T2 两个受控 live repair 样本）

本片先在 sandbox 内检查 8006，Python/`curl` 因 localhost 网络权限失败；随后通过只读 escalated
preflight 确认 runtime 已恢复：`/health=200`、`/v1/models=200`，模型为 `qwen38-27b-nvfp4`、
`max_model_len=131072`，metrics 显示 running/waiting/KV/preemption 均为 0。未启动服务。

使用同一 frozen S3-20 Writer page projection、schema 与输入，执行两个 fresh、每个最多一次真实
repair 的 probe：

- 空页结果：[`r3/writer_repair_result.json`](/tmp/c2p-s3-t2-live-repair-20260914-r3/writer_repair_result.json)。
  1 次真实 repair；`finish_reason=stop`、`provider_finish_reason=stop`、`usage_seen=true`，
  prompt 50,220 / completion 1,192。模型返回 heading-only，内容/目标 contract 拒绝，
  `writer_repair_commits=0`，section incomplete。
- 标题页结果：[`r5/writer_repair_result.json`](/tmp/c2p-s3-t2-live-repair-20260914-r5/writer_repair_result.json)。
  修正 frozen primary 的 blocked 标记后重新执行 1 次真实 repair；usage 为 prompt 68,831 /
  completion 1,302，模型返回约 952 字正文，但缺 required detail witness，
  `required_target_contract` 拒绝，`writer_repair_commits=0`，section incomplete。
- r4 曾在修正 title primary 标记前发送 1 次 provider request，目录
  `/tmp/c2p-s3-t2-live-repair-20260914-r4/` 保留作 superseded diagnostic，不作为验收证据。

本片还修复并回归了一个低层 Writer 闸门：repair 仍携带 typed content failure 时不得因非空而
增加 `writer_repair_commits`。新增回归 `test_unified_v2_content_failed_repair_is_not_counted_as_commit`。

验证（本片新执行）：

- `python -m pytest -q tests/test_agentic_unified_context_compiler.py tests/test_agentic_publication_method_writer_unified.py tests/test_llm_runtime.py tests/test_llm_section_writer.py tests/test_r6_portability_and_budget_hygiene.py tests/test_agentic_formalization_guards.py tests/test_agentic_replay_execution_record.py tests/test_agentic_runner.py -p no:randomly --basetemp=/tmp/c2p-contract-final-focused-20260914-r4` → **259 passed**。
- `python -m compileall -q src tests .tmp/c2p-s3-t2-replay-20260914 .tmp/c2p-s3-t2-live-repair-20260914`、`git diff --check` → exit 0。
- escalated read-only post-check：runtime idle，`num_preemptions_total=0`。

结论：两个真实样本都产生了可解释的失败诊断，但没有正文通过内容/绑定门，因此 T2 不结项；
T3 provider usage/跨 phase 预算仍未闭合，Candidate、structural exit、Verified 均不存在。下一步
只能在既有 fresh 受控证据上修复明确的输出/绑定问题并重新验证，不能直接启动完整 Candidate。

## 2026-09-14（§15.6 continuation：deterministic revalidation 与预算边界）

本片不重跑旧行为图、不修改 frozen S3-20，也不新增 provider request。现行代码对实际保存的
[`r6 live response`](/tmp/c2p-s3-t2-live-repair-20260914-r6/writer_repair_result.json) 做
provider-free 重验证：24 个 required atom witness 全部绑定，推导 detail
`detail:mech_sym:9773c5add7af1f92:13`，无失败项，段落事务有效，正文 721 字符。r6 的原始 live
结果仍标记为当时入口下未提交；本次只是证明修复后的当前入口能够验收该响应，未把它写回 live
receipt，也未计入新的 provider 成功。

本片修复/固定了 V3 `detail_id` 的保留、closed exact-excerpt 的受限语义回退、条件 clause
锚点，以及 required atoms 全部完成时推导 detail witness 的 binder/assessor 一致性。预算回归
新增并通过：repair 不能挤占跨阶段 future-primary 预留；超过 retry reserve 必须在发送前
拒绝；缺失 usage 维持 conservative/partial 状态，不清零、不伪造精确值。

验证（本片新执行）：

- `python -m pytest -q tests/test_agentic_unified_context_compiler.py tests/test_agentic_publication_method_writer_unified.py tests/test_llm_runtime.py tests/test_llm_section_writer.py tests/test_r6_portability_and_budget_hygiene.py tests/test_agentic_formalization_guards.py tests/test_agentic_replay_execution_record.py tests/test_agentic_runner.py -p no:randomly --basetemp=/tmp/c2p-contract-t2t3-20260914-r5` → **264 passed**。
- 两项预算边界选择性回归 → **4 passed**；此前 124 项 Writer/binder focused 集合亦通过。
- `python -m compileall -q`（相关 `src/`、`tests/` 与 probe fixtures）、`git diff --check` → exit 0。

当前产物状态：T1 有效 Formalizer package 保留；r3 空页仍是内容失败，r5 标题页 live 请求仍未
提交，但 r6 实际响应已通过当前代码的离线内容/绑定验收；没有 Candidate。T3 的代码闸门已覆盖，
但旧 run 仍有 113 个 usage 缺失，ledger 为 partial，保守 input 计量 1,990,033，且历史
Writer repair 已花费 381,539、超过 200,000 声明 reserve；因此下一轮完整 plan 的真实计量、
跨阶段预算和 profile 上限尚未闭合。本片未修改 profile、未启动完整 Research/authoring。

## 2026-09-14（S3.6 独立复核：错误绑定反例与执行纠偏）

本轮回应用户“这些操作是不是改坏了”：只做代码/产物复核和离线探针，未修改生产代码、
profile、测试文件或既有 run，provider 请求 0。当前工作区包含后续 r3–r10 与 profile
提额，较早状态按各自时点解释；已更新 docs/README.md 和统一执行计划 §15.6.4。

确认 P1：新增 `_exact_excerpt_overlap` 在原语义锚点未通过时允许 3 个词形/0.30 重叠
替代事实绑定。源码要求 `embeddings + bias + residual`，正文写成相乘，当前 Binder +
assessor 仍 valid 并推导 detail；只在探针内禁用此新增回退则拒绝。真实 r6 页中加法
operation 的 witness 实为“保持 batch/sequence dimensions”；将求和改成相乘也仍获
24 witnesses、无失败。这不证明完整 Candidate/Verified 已错误放行，但局部验收已退化。

确认微测缺口：现有脚本直接调用低层 Writer/LLMClient，未走统一预算、content receipt、
resume 与生产 transaction assessor。实际 r6 响应局部 normalization 通过，当前低层
完整协议回放仍 repair commit 0、no-progress 1、incomplete；primary 的历史 `_p1__f1`
与当前 `_p1` 不兼容。不能把局部 normalization 当作统一入口恢复成功。

可见 Writer 微测有 7 次 provider usage（prompt 444,666 / completion 8,432），r7 缺
key 未发送也被脚本计为 provider_calls=1；r3/r8、r6/r9 请求和响应摘要均分别相同。
当前 profile 已提到 2,500,000 总额、Writer 400,000 / Realizer 100,000 reserve，
生产计量仍默认 UTF-8/4。停止未变化样本重跑，先收紧错误绑定、对齐实际统一入口，再校准
完整预算。保留 Formalizer schema、流式诊断、空/标题拒绝、账本分层和预算保护。

证据目录：`.tmp/c2p-s36-independent-review-20260914/`，含 review.md、probe.py、
probe-result.json、microtest-inventory.json、focused-tests.log、code-index.json；
7 个生产文件及当前微测脚本/profile 的副本在 code-snapshot，探针前后生产摘要一致。

新执行验证：

- `python .tmp/c2p-s36-independent-review-20260914/probe.py` → exit 0；上述反例成立，模型调用 0。
- `python -m pytest -q tests/test_agentic_detail_atom_binder_and_trace_v2.py tests/test_llm_section_writer.py tests/test_agentic_publication_method_writer_unified.py tests/test_agentic_unified_context_compiler.py tests/test_llm_runtime.py -p no:randomly` → exit 0，**173 passed**（7.43s）。现有回归未覆盖新反例。
- T1 `read_all_completed_receipts(..., strict=True)` → 1 个已发送 accepted/complete receipt，provider 诊断摘要链通过，绑定 prompt 3,787 / completion 1,114；保留一个真实 accepted repository-derived package 的局部成果。
- `git diff --check` → exit 0；新增证据链接存在，未重跑完整静态、Research、live 或 Candidate。

## 2026-09-14（S3.7 操作指引：计量接线与单页真实验收）

回应用户“现在真实测试？”及“按什么操作”：本轮核对实际代码和 S3.7 校准产物，更新统一
执行计划 §15.6.5 与 README 导航，交付可由执行者实施的范围、预算、命令交付要求和验收步骤。
未修改生产代码、profile 或测试，未调用 `/tokenize` 或模型生成接口。

确认当前三个历史错误加法反例（相乘、漏加数、否定加法）经 Binder + assessor 均 invalid，
rendered_detail_ids 为空；这是本轮新执行的零模型检查。178 passed/compileall 是执行者报告，
本轮没有重复跑该集合。确认 `--resume` 当前是 section 选择，尚无已验收的单页统一 CLI；
不能把旧低层 live_repair.py 当作当前生产提交和恢复验收入口。

读取 `/tmp/c2p-s37-calibration-20260914/`：18 个 Writer primary 共 828,590 chat tokens；
超 60,000 的三页分别 66,578、68,323、73,618；选定原空页 02a75… 为 49,678。
校准使用本地服务 `/tokenize`、记录生成调用 0；这次只读其文件，并未重新请求服务。
5 个源文件保存到 `.tmp/c2p-s37-calibration-evidence-20260914/`，source-index.json 记录摘要。

操作单要求先把 wire/tokenizer 身份接入 plan 与实际发送门，再提供复用统一 capturing
caller/assessor/sidecar/resume 的单页诊断入口及 prepare/live/resume 实际命令。提议独立
微测 Writer 最多 2 次生成、单请求 input 60,000、run input 120,000（含 repair reserve
60,000），output 最高 8,192、context 131,072；不是修改完整 run profile 或宣布 live 准入。
微测和整篇验收分别报告。全阶段和 repair 预算测完后再决定配置/分页及完整 authoring。

`git diff --check` → exit 0；本轮文档与证据更新未启动 live。

## 2026-09-14（S3.7 continuation：真实计量、单页入口与受控 live）

本轮按统一执行计划 §15.6.5 先完成代码接线，再运行真实 8006。未重做旧行为图、Research
或完整 authoring。

实现内容：

- 新增 `src/code2paper/llm/tokenizer.py`，通过 8006 `/tokenize` 计量实际 OpenAI-compatible
  chat wire sequence，并冻结 model/base URL/runtime identity；缺 tokenizer、identity mismatch
  或超限在 provider send 前拒绝。
- `unified_context_compiler.py`、`unified_context_models.py` 使用同一 chat-template meter；
  `section_writer.py` 暴露生产同构 Writer request 构造。
- 新增 `scripts/run_unified_single_page_writer.py`，提供 `prepare`、`live`、`resume`；只选
  原空页 `page:02a75f6a…` / section `MA-REV-mech_sym-f6cf5bdfe2ae16f0`，使用 production
  budget gate、receipt、content acceptance、repair assessor 和 resume plan。
- 更新计量回归与旧 fixture tokenizer identity；没有放宽内容 gate。

验证：

- `python -m pytest -q tests/test_agentic_unified_context_compiler.py tests/test_llm_section_writer.py tests/test_llm_writer_section_repair.py` → **134 passed**。
- `python -m pytest -q tests/test_agentic_publication_method_writer.py tests/test_agentic_publication_method_writer_unified.py` → **162 passed**。
- 相关 `py_compile` 与 `git diff --check` → exit 0。

真实命令与产物：

```bash
python scripts/run_unified_single_page_writer.py prepare \
  --frozen-root /tmp/c2p-unified-repair-20260914-s3-codex-20 \
  --output /tmp/c2p-s3-single-page-20260914-02a75-r2 \
  --profile tests/live/profiles/qwen38_vllm_budgeted.example.env
python scripts/run_unified_single_page_writer.py live \
  --output /tmp/c2p-s3-single-page-20260914-02a75-r2 \
  --profile tests/live/profiles/qwen38_vllm_budgeted.example.env
```

prepare 真实访问 8006，`/health`、`/v1/models`、`/metrics` 均 200，模型
`qwen38-27b-nvfp4`、context 131072；最终 wire input **53,931**，生成调用/发送均 0。
live 真实发送 **2 次**：1 primary + 1 repair；meter input 分别 **53,931 / 55,013**，
provider usage 分别 `49,666/1,370/51,036` 与 `50,748/1,393/52,141`（prompt/completion/total），
两次均 `finish_seen=true`、`usage_seen=true`、`structured_complete`。

结果：两次真实 receipt 和两份 content acceptance sidecar 都保留，但内容均 rejected，
`writer_repair_commits=0`、`writer_repair_no_progress_stops=1`，没有
`single_page_submission.json`，因此没有执行 resume，也没有把页记为完成。失败具体为：模型
输出 paragraph 仍带 heading，验收清理 heading 后判定 body non-substantive；required detail
10/22 的完整 atom witness contract 也未闭合。该失败不是空流、usage 缺失或预算超限；按停止
条件不换目录、不重复同一请求，后续必须先修输出合同/完整 witness 交付再申请新的 live。

## 2026-09-14（真实单页失败复核：§15.6.7 下一步合同修复）

本轮回应用户“下一步呢”，核对 r2 的实际请求、原始响应、24 个 required atoms 和当前代码，
只运行离线探针/严格 receipt 读取，未修改生产代码、旧 run 或调用模型。执行指引已写入
统一计划 §15.6.7，README 已索引。

发现：writer_skill 同一 prompt 要求 paragraph 不含 heading，又无条件要求以 H2 开始。
两份真实输出把已知 heading 与正文粘连；仅在诊断副本移除该精确前缀，保留全部正文词，
得到 1,369/1,532 字符，“无正文”失败消失，detail 仍缺失。故不能将本次描述为模型没写正文。
detail 10/22 各有 11/13 个 required atoms，分离标题后当前只绑定 4/6 个；repair 包只包含
两个 aggregate detail，没有展开各个缺失 atom 的原因。

确认新的算术检查适用范围错误：源码中任意 `+` 即触发整体加法验证，detail 22 的 torch.zeros
调用参数内 `+1` 被当作顶层求和；13 个 atoms 中 11 个即使用原授权源码摘录也被该检查拒绝。
应修表达式/target 结构分类并保留之前错误加法反例拒绝，不再按词汇阈值放宽。
V2 的低层 Binder 明确禁用，而 prompt 承诺 separate Binder；如需语义 Binder，应进入已有
显式 phase/预算/receipt，不恢复隐藏模型调用。单页脚本仍有自行实现的 caller/assessor/sink，
下一片应与生产共用事务验收实现并验证同响应一致性。

计量表述纠正：53,931 / 55,013 是含 schema/wrapper 的预算 input；provider prompt 为
49,666 / 50,748。真实发送两次的证据有效，既有零提交状态保留，不执行无提交的 resume。

验证与证据：

- `python .tmp/c2p-s38-next-step-review-20260914/probe.py` → exit 0，provider_calls=0；结果为 inspection.json，含缺失 atom 列表、前后失败、源码摘要和原文调用计量。
- `read_all_completed_receipts(..., strict=True)` 对 r2 → 2 个 receipt 摘要链通过、sent_to_caller=2。
- `git diff --check` 与新增链接检查 → exit 0；未重新跑完整静态或 live。

## 2026-09-14（§15.6.8 合同修复离线验证与 r3 单页真实验收）

本片按用户指定顺序执行：先离线回放两份冻结真实响应，再在新目录 prepare，随后只做一次
同页 `1 primary + 1 repair` live。没有重做旧行为图、Research 或完整 authoring；未执行无提交
resume。

实现与验证：

- 修正 Writer 的 section/paragraph heading 合同，并在生产 normalizer 中只恢复已知 heading；
  修正顶层加法识别，使 `torch.zeros` shape 内 `+1` 不再误伤，同时保留相乘、漏加数和否定
  加法拒绝；repair packet 展开逐 atom 缺口、候选 span、失败原因和 Writer/Binder owner；
  单页脚本改用生产共享 content assessor/progress assessor。
- `python scripts/validate_unified_single_page_frozen_responses.py --run /tmp/c2p-s3-single-page-20260914-02a75-r2 --output .tmp/c2p-s39-contract-repair-20260914/inspection.json`
  → exit 0，`provider_calls=0`，正文 1,369/1,532，valid atoms 8/24、10/24，detail 22 为
  13 个 shape atoms，四个加法反例均通过；完整 detail 仍拒绝。
- `python -m pytest -q tests/test_llm_section_writer.py` → 107 passed。
- `python -m pytest -q tests/test_agentic_publication_method_writer_unified.py` → 18 passed。
- `python -m pytest -q tests/test_llm_section_writer.py tests/test_agentic_publication_method_writer.py tests/test_agentic_publication_method_writer_unified.py`
  → 269 passed, 6 warnings。
- `python -m pytest -q tests/test_agentic_unified_context_compiler.py tests/test_agentic_detail_atom_binder_and_trace_v2.py`
  → 34 passed。
- `python -m compileall -q src tests scripts`、`git diff --check` → exit 0。

真实执行：

- prepare 输出：`/tmp/c2p-s3-single-page-20260914-02a75-r3/prepare_result.json`，状态 pass，
  8006 `/health`、`/v1/models`、`/metrics` 均 200，模型 `qwen38-27b-nvfp4` / context 131072，
  同一 tokenizer identity，meter input 53,969，generation/provider sends 0。
- live 输出：`/tmp/c2p-s3-single-page-20260914-02a75-r3/live_result.json`，状态 fail，实际
  provider sends 2。两次 provider usage 为 `49,704/1,260/50,964` 和 `53,909/1,269/55,178`
  （prompt/completion/total），meter input 为 53,969 和 58,174，均 finish/usage 完整、transport
  accepted；但 content acceptance 均 rejected，detail 10/22 required target contract 未闭合，
  repair commit 0、no-progress stop 1。
- `/tmp/c2p-s3-single-page-20260914-02a75-r3/single_page_submission.json` 不存在，两个
  sidecar 均 `resume_eligible=false`，故未发送 resume。该页和完整 Candidate 保持 incomplete；
  下一步需先补有账的 atom 内容/绑定闭合路径和离线验收，再申请新的 changed-basis live。

## 2026-09-14 23:38 全流程独立复核与执行优先级更新

回应用户要求重新梳理流程、产物、方向和距最终目标的差距。本次未修改生产代码，未启动模型、Research 或 live，
未干预已经运行的全文 r5。详见 `docs/research_to_method_end_to_end_status_review_2026-09-14.md` 和统一计划 §15.7；
README 已更新，早期 §15.6/T1/T2 记录保留历史性质。

- 绑定证据：`.tmp/c2p-e2e-flow-review-20260914-01/inventory.json`、`source-index.json`、`flow-findings.json`；
  18 个代码/配置文件副本与 SHA-256，218 个产物快照。快照时最新已结束全文 r4 exit 2，Writer 发送 0、无 Candidate；
  单页 r7 有提交/resume；全文 r5 为 20 completed / 21 started、无终态，不能扩张为通过或失败。
- r2/r3/r4 各 34 main + 20 repair Formalizer 调用，三批 request 文件哈希完全相同；总登记发送 162，
  provider input 1,364,361、output 291,462。各 32 个 accepted packages，83 条 preferred 中 51 条未覆盖。
  accepted 样例仍有 LOAD/WRITE 操作表达，与论文数学表达目标有差距；不把 preferred 偷换成 required 或删除。
- 当前代码零网络回放冻结 r4：19→21 paragraphs、18 pages、最大 payload 估算 19,791，required/optional detail、
  formula obligation/package 四类 ID 集合守恒。该探针没有宣称真实 wire/tokenizer 准入；见 `offline-probe.json`。
- 当前 reader 验证 r4 的 54 条 receipts；原 Formalizer plan 恢复判定为 18 reuse、36 incomplete execute、
  12 未发送 slots，未把后两者算作成功复用。需要把合法成果复用接入下游实际操作路径。
- 精确命令：`python .tmp/c2p-e2e-flow-review-20260914-01/inventory_evidence.py` exit 0；
  `python .tmp/c2p-e2e-flow-review-20260914-01/offline_probe.py` exit 0；
  `python -m pytest -q tests/test_agentic_unified_context_compiler.py tests/test_agentic_publication_method_writer_unified.py tests/test_agentic_detail_atom_binder_and_trace_v2.py tests/test_agentic_formalization_guards.py`
  exit 0，107 passed。未重跑全量静态；探针前后 18 个关键代码/配置文件 SHA-256 一致。
- 执行收敛为生产 phase prepare → 全文 Candidate → 同身份最终质量/恢复/Verified；保持既有信任边界，
  不再把 token 持续增长、微测通过或 static test count 当作全文交付进度。
- 23:49:31 最后只读观察：r5 已有 54 completed / 54 started，仍无 execution record 和 Candidate，结果待定；
  已写 `r5-last-observation.json`。`git diff --check` exit 0，报告链接存在，18 个代码/配置文件无漂移。

## 2026-09-15 r5 终态追加与 prepare 合同因果复核

用户在同一复核任务中补充 r5 再次失败。本次继续零模型/零网络核查，没有修改生产代码、没有启动新 live。
r5 最终 exit 2，54 个 Formalizer receipts，Writer 发送 0，无 Candidate。r2–r5 共登记 216 次相同请求批次发送，
input 1,819,148、output 388,616，调用区间合计约 76.99 分钟；`r5-terminal-observation.json` 绑定终态。

纠正“最终 page 丢 detail 13”的初步归因：真实错误发生在试分页请求构造，`_ordered_candidate_rows` 将输入候选
row 换回原始完整 row。候选页只包含 detail 19/3，候选 required 为空；换回旧行后要求 detail 13，导致拒绝。
它还会丢弃新段落 `__f1/__f2`，冻结修订中共 4 个。不是应该往每个小页补 13。

`python .tmp/c2p-e2e-flow-review-20260914-01/r5_prepare_probe.py` exit 0：直接提取六个生产准备 helper 函数体，
调用真实分页器/Writer 请求构造。原 helper 在第 10 次候选构造复现 live 同码；仅内存替换为保留传入 rows，
37 次候选构造返回，修订 21 段、failures=[]。请求计量返回 0 占位，仅隔离 tokenizer 前的合同错误，不宣称完整计量通过。
证据 `r5-prepare-probe.json` 和 `r5-sources/`；报告、README、统一计划 §15.7 已更新，要求整个生产 prepare 纵向验收，
不再按单个报错 ID 修补后重发整批 Formalizer。此前 107 项静态通过结论保留，本反例说明其入口覆盖边界。

## 2026-09-15 生产入口收敛执行文档

按用户“充分研究代码和产物，给出收敛执行文档”的要求，交付
`docs/research_to_method_production_closure_execution_2026-09-15.md`，同步 README、统一计划 §15.7 与现状复核的执行索引。
本次新增的是实施要求，未修改生产代码、未启动新 live/Research/模型服务。

- 收敛目标：现有生产 authoring 入口完成 EBCAR 全文 Candidate；Verified 独立验收，不宣称默认切换/D5 完成。
- A：保留候选 row 与合法片段身份，提取现有完整生产 prepare，覆盖全量页/请求/目标守恒及真实计量。
- B：现有 replay 新增阶段模式（待实现），校验并消费原 phase 成果、保留父记录和花费；同时检查公式表达、
  最终计划身份与 prepare → 事务/组合 → structural exit/resume 的离线集成。
- C：准备与集成通过后直接执行 pending 全文 authoring；只回到失败所属阶段，禁止无变化整批重发。
- 文档明确动态 repair/下游请求须发送前实测；没有把 lookahead 占位计量当作已完成真实准入。
- 复核前后 18 个关键代码/配置文件 SHA-256 未漂移。相关 107 项测试为本次前段复核结果；文档阶段未重复跑 pytest。
- 文档验收：`git diff --check` exit 0；本次执行文档/现状复核共 25 个本地链接目标均存在，
  18 个关键源码/配置摘要再次一致。结果已写 `.tmp/c2p-e2e-flow-review-20260914-01/execution-document-checks.json`；
  未把待新增 CLI、prepare 结果索引或真实全文验收记录成已实现。

## 2026-09-15 用户质疑后的执行方案第二次核验

第一版根因/成本盘点成立，但未充分覆盖后续真实调用边界，也未把正常产品入口作为独立验收；本轮继续核对并直接
修订同一份收敛执行文档，不新增另一份计划。生产代码未修改，模型/网络调用均为 0。

- `python .tmp/c2p-e2e-flow-review-20260914-01/checkpoint_scope_audit.py` exit 0：r5 54 条 receipt 原身份一致，
  引用片段无缺失，32 个包与 aggregate 一致，当前来源/条件/公式绑定 validator 32/32 通过；其中 13 个来自
  partial 回执。普通 resume 会安排 23 个 main 重发，故方案改为有限的已结束 Formalizer 阶段读取，保留失败。
- `python .tmp/c2p-e2e-flow-review-20260914-01/downstream_contract_audit.py` exit 0：r5 payload 修订 18 页，
  原生产 handoff 注入块让 18/18 request/envelope 摘要改变；当前旧 5 节与 unified 2 节 ID 交集为空。
  该探针使用真实 serializer/digest，未作 tokenizer 准入或生成成功声明；Candidate 组合有额外 ID 回退，
  未把正式 accepted 投影错位描述为正文必定丢失。
- 同一探针截获默认 Editor/Rewrite 的 client 调用（真实网络之前停止），两者未经过 unified 账本，Editor
  role 为空；正常 `_run_writer_surface` 的 unified 调用未传 tokenizer。上述事实绑定 8 个相关源码摘要。
- 执行限于 F1 row/片段、F2 handoff request material、F3 实际正文计划身份、F4 阶段结果读取、F5 正常入口
  runtime/tokenizer、F6 辅助角色预算。论文表达按实际消费定向处理，不把通用缓存或 Formalizer 全面重写作前置。
- 修正 Realizer primary 的依赖说明：当前由冻结 page/计划/公式独立构造，应在 prepare 用真实 builder 计量。
  第一版把它归为依赖未来 Writer 正文的请求不准确。
- 交付目标补充正常 `code2paper method-agent run` 入口及恢复，不以 replay 成功等同生产就绪；CLI 新参数均
  标为待实现。README、统一计划 §15.7 和现状复核同步修订。前次 107 项静态测试结果保留，本轮未重复 pytest。

## 2026-09-15 r25 真实代码修复与冻结响应复验

范围：响应用户“读真实代码，没有修复的再修复”。保留现有 dirty tree；本轮没有提交、改写历史 receipt 或启动模型请求。

### 代码核验与修改

- 读当前生产 Realizer 发现已有原子 guard 选择和 incumbent witness 携带修复，不能再称为“尚未修复”。本轮进一步将 guard 缩窄限定为 AST 中完整条件的等价合取；额外条件、OR/NOT 改义、相似变量、注释、重复位置和多行歧义均保留原完整 excerpt。修复回合只复用仍精确存在于新正文中的旧 witness，不生成正文。
- `publication_method_writer._assert_unified_v2_realizer_delivery` 改为报告最大 attempt 的失败，而非 `rows[0]`，历史 receipt 保持原样。r25 终态原先暴露的是第一次失败，遮住了修复响应丢失 witness 的实际最后边界。
- `splice_formula_placeholders` 在已校验 package/consumer 的原占位符位置保留重复公式的 occurrence 身份，并生成现有正文中的唯一精确 witness 窗口。Writer 接入该元数据恢复并留 trace；不推断没有占位符来源的重复公式，不覆盖模型已经提供的 witness，不修改正文/公式字节。
- 共用 Writer request builder 在 prepare/send 前按封闭页面设置 paragraph ID enum；修复回合复用相同 schema。ID 拼写错误仍拒绝，不通过 harness 改写 ID。
- r25 detail 13 的原正文条件为“configuration flag ... is active”，并非可以证明遗漏事实。条件解析器此前不认可该形式。本轮只对完整子句末尾的显式 `is active` 使用已有 `is enabled` 语法；否定、条件结构、运算符和名为 active 的操作数仍保留。没有普遍去除连字符，也没有接受所有语义相似表述。
- 收紧已有算术豁免：仅语义自身等于声明条件的 guard（兼容无 role 旧合同）可忽略关联源码中的加法；带条件的 operation 仍必须证明正确求和，错误乘法/缺操作数拒绝。

### 实际产物结论

证据目录：`.tmp/c2p-r25-repair-20260915/`。

1. `realizer_probe.py` 用 r25 两份原始响应调用当前生产 Realizer：第二份 accepted，13 个 witness 验证完成；9 个模型漏返的旧映射仅在新正文中仍有精确文本时重用。primary 摘要相同；修复合同已变化，repair 摘要不同，不能据此修改 r25 原回执。
2. `writer_pipeline_probe.py` 从原 Narrative/manifest/plan 构造实际生产 Writer 输入，使用注入的冻结 caller 执行公开 Writer 管线和内容 assessor。修复前的四个请求摘要与 r25 对应摘要一致。修复后 page 7589a97d 的第一份响应直接通过；page b70a29ab 的第二份响应通过。正文没有人工改写，没有采用诊断 counterfactual 的 ID 修改结果。
3. r25 有 Writer 正文草稿，但原运行 exit 2、无 Candidate digest。此次只证明原来三个失败页在新代码下的定向冻结回放，不证明完整 A→B→C、后续组合/Editor/最终 Candidate 或 Verified 已完成。当前不能宣布生产收敛完成。
4. `writer-before.json` 的早期低层重建丢失私有图结构，已由公开生产管线回放取代；`writer-identity-counterfactual.json` 仅用于定位，不能当作合法模型输出。正式证据为 `result.json`、`writer-pipeline.json` 和 `final-code-and-input-digests.json`（HEAD、30 个代码/测试/输入摘要）。

### 验证

- `conda run -n code2paper python -m pytest -q tests/test_agentic_condition_state_witness.py tests/test_agentic_formalization_guards.py tests/test_llm_section_writer.py tests/test_agentic_mechanism_realizer_composer.py tests/test_agentic_publication_method_writer_unified.py tests/test_agentic_publication_method_writer.py tests/test_agentic_unified_context_compiler.py tests/test_agentic_replay_execution_record.py tests/test_agentic_branch_control_relations.py`：exit 0，433 passed，6 个现有 Pydantic serializer warnings。日志 `targeted-tests.log`。覆盖正/负条件、运算、占位符身份、修复元数据和失败终态。
- `conda run -n code2paper python .tmp/c2p-r25-repair-20260915/realizer_probe.py`、`conda run -n code2paper python .tmp/c2p-r25-repair-20260915/writer_pipeline_probe.py`：均 exit 0；无网络或新生成调用。
- `conda run -n code2paper python -m compileall -q src tests`、`git diff --check`：exit 0。
- 过程中的一次测试收集失败（缺少 pytest import）及两项旧合同回归（缺 paper_role）均已修复，最终上述集合通过。
- `conda run -n code2paper python -m pytest -q`：exit 0，3567 passed、3 skipped、7 warnings、12 subtests passed，123.82 秒；日志 `full-static-tests.log`。随后最终审查进一步要求 guard 缩窄仅适用于 branch/condition role（不能把带条件的 transformation 只绑定到 guard），补负例并重跑 Realizer 定向测试与冻结回放。未重复整套测试；不以静态通过替代正常产品入口最终验收。

- 最终 guard role 收紧后：`conda run -n code2paper python -m pytest -q tests/test_agentic_mechanism_realizer_composer.py` exit 0，24 passed in 1.06s；生产 Realizer 冻结回放 exit 0。最终 `git diff --check` exit 0。

## 2026-09-15 Research → Candidate 终态与账本闭合修复

范围：按用户要求修复本轮 EBCAR 正常入口/旧 run28 产物审计发现的问题。保留 dirty worktree 与历史产物；没有提交、重写旧 checkpoint/receipt，也没有把仍由旧进程加载的 live8 当成新代码验证。

### 实现

- `research_tools.py` 在 `compile_code_facts` 内把 configuration-definition facts 合入后再一次性持久化；`validate_code_facts` 使用相同重算链验证，删除 `research_nodes.py` 的仅内存二次扩充，消除 persisted/in-memory fact-set identity 分裂。
- `research_graph.py` 从 live agenda、compiled claims、决策/工具调用与缺失关系持续计算 `QualityStateV2`，在采集/编译边界刷新 Pareto best；读取新 span 不再算 compile coverage gain。`intent_ledger.py` 同步不再用新 span 重置语义无进展计数；strict promotion 检查消费全部未闭合 promotion，而不是按 agenda 终态过滤。
- `publication_method_writer.py` 的 Narrative→Method adapter 只按 source/fact/equation/config/relation 的唯一精确锚点绑定旧 argument unit，并保留明确的 unmatched/ambiguous trace；可验证 obligation/move 绑定才进入当前计划。Candidate completion 现在同时检查 adapter、plan gate、epistemic safety、content-unit render chain，以及 accepted/consumed formula 的实际正文出现。
- Candidate authority/公式门新增 `Sym:*`、`mech_sym:*`、`MA-*`、`LOAD/WRITE/RESHAPE/CALL/...` 和 LaTeX 控制字符检测。`publication_quality.py` 从实际 Candidate display-math 与公式包正文出现计算 rendered/consumed，不再用旧 equation id 代替正文渲染。
- Unified Rewrite 不再复制 million-token writer view、authoring packets、mechanism packet 或 frozen page bytes；只保留 section-local contract/identity，并在 180 kB authority projection 上 fail-before-send，为 60k-token角色预算留出 incumbent、issue、schema 与响应空间。
- structural exit 新增 Candidate completion、quality/content chain 与 adapter 未绑定检查。live `method-agent run` 仅在 Candidate available+complete 时 exit 0，process artifact 记录 Candidate 阻塞原因；显式 `--no-live-llm` 仍是成功的离线诊断入口。
- replay 将 provider transaction success 与 Candidate completion 分开；terminal complete/exit 0 同时要求 Candidate complete 和 structural exit eligible。成功记录不引用旧 failure artifact；累计 token usage 优先从 `artifacts/06_authoring/invocations/**/attempt-*.completed.json` 持久回执汇总，而非只看当前进程内 trace。

### 产物复算与验证

- 旧 `/tmp/c2p-production-closure-20260915-28` 只读重算：原 27 个全未绑定 argument units 中 24 个按唯一精确源码锚点绑定到两个当前 Narrative sections；3 个未绑定（两个未被 Narrative 计划覆盖，一个没有任何 source/claim/equation/config/relation anchor）继续明确阻断，未猜测归属。
- 聚焦集合：516 passed，6 个既有 Pydantic serializer warnings。
- `python -m pytest -q`：exit 0，3582 passed、3 skipped、7 warnings、12 subtests passed，136.23 秒。
- `python -m compileall -q src tests scripts` 与 `git diff --check`：exit 0。本轮尚未启动新的模型请求或正常入口 live，因此不声明 Candidate/Verified 已交付。

## 2026-09-15 live9 配置证据包血缘修复与 partial Candidate 语义确认

范围：回应用户“Research 不必找齐全部可信证据，应能进入下一阶段”的产品语义。
保留 strict Research/Verified 硬门；Candidate 继续使用已实现的 bounded partial handoff，未减少
obligation、未过滤失败 claim、未放宽 span validator。

### 实现

- `generic_evidence_compiler.py` 在 packet 冻结前做确定性配置定义预编译：仅当已选
  `CONFIGURED_BY` 关系的精确 endpoint operand 与配置访问表达式一致时，才把冻结标量声明 span
  纳入 `semantic_span_ids`，并附加到该 configuration relation 的 `direct_span_ids`。因此该 span
  从 anchor 可达，packet source digest 也真实覆盖它。
- `configuration_definitions.append_configuration_definition_facts` 新增可选 packet-span 白名单；事实工具
  仅为已由 owning packet 承载的声明生成正向 configuration fact。`compile_code_facts` 与
  `validate_code_facts` 共用同一限定与重算路径。
- 该边界修复 live9 的具体错误
  `unknown_packet_span:span:conf/config.yaml:19:19`；没有将搜索未决冒充为“代码不存在”。
- 确认现有 Candidate 通道已符合所需语义：Stage 1/3 可以以 promoted claims + typed unresolved
  fields + qualifier + 一次 post-partial retry 交接；strict failure 仍保留，Verified 不因此放行。

### 验证

- 合成 packet/config 集成及 Research 工具：103 passed。
- Candidate handoff/正常产品入口/Unified Writer 阶段边界：122 passed。
- V3 证据链、mechanism closure 与配置条件：84 passed。
- 用 live9 的真实 EBCAR repo snapshot、behavior graph 及原 Mainline proposal 在新目录
  `/tmp/c2p-live9-config-replay-fix1` 零模型重放：proposal→packet→facts→fact validation 四步均
  `success`；`span:conf/config.yaml:19:19` 已在 packet，同一 configuration fact id 通过，packet/fact
  digest 同为 `sha256:8fd417bae83c6d7f8ad51c31d47ee79bc104fe63f2a9e5d137c879396d4f8238`。
- `python -m pytest -q`：exit 0，3584 passed、3 skipped、7 warnings、12 subtests passed，129.60 秒。
- `python -m compileall -q src tests` 与 `git diff --check`：exit 0。
- 尚未在这一 changed basis 上执行新的正常入口 live；因此目前只声明修复与静态/真实冻结重放通过，不声明新 Candidate/Verified 已交付。

## 2026-09-17 P7 V4 身份阻塞与公式误入修复

范围：只读分析 `/tmp/c2p-p7-ebcar-v4-w2p9KvoI`（原运行绑定 `287506e`），在当前 `2c290aa` 的 dirty worktree 上增量修复；未重写原产物、未提交、未发起模型请求。原运行先遇到 `NarrativePlanV3` 名称错误，该 import 在本轮开始前的工作树中已有修复；本轮针对随后复现的 `unknown_detail_id` 与公式误入补丁。

- V4 编译器不再给 section 内每个 story 复制全部机制 detail。多机制 story 分成同一作者 section 内单一 mechanism owner 的段落；每个 detail 只分配一次，ownerless 作者段落不承载 repository detail。argument unit 也只分配给一个段落。源 ID 交集用于优先定位，零交集回退有显式 trace，不能用回退证明语义对齐。V3 投影保留空机制的作者段落，不再按单机制 section 偷填 owner；witness、author surface 和公式 placement 同步投影。
- V4 所选产品路径编译失败时不再静默退回 V3。公式 package 的 source details 同置于一个机制段落，package/obligation/placement 身份守恒。
- P7 的 Formalizer 实际 2 main + 2 repair 均因把 `document_id.long()`/`self.cfg...` 等代码运算写进公式而被正确拒绝；后续 attempt 触发预发送预算拒绝。公式 worthiness 现在将无 equation/facet 来源、非 formalizable 的代码形 transformation 判为 prose/algorithm，不再为它发机制公式义务。P7 冻结 contexts 的两条此类义务离线复算均消失。此修复不将 7 个未桥接的作者 required 公式改为已完成。
- P7 冻结 story/prior plan/context 经当前产品 `_build_narrative_plan_v3` → V4 envelope → V3 projection → `validate_narrative_plan` 零模型重放：5 sections、32 paragraphs、28 唯一 argument units、0 validation failures；11 个 required detail 唯一归属，required fallback 为 0；122 个 optional detail 缺少 story 锚点，仍须后续审查，不能当成实现事实授权。
- 定向回归 `python -m pytest -q tests/test_agentic_intent_spine_authoring.py tests/test_agentic_mechanism_formula_obligations.py tests/test_agentic_candidate_handoff.py tests/test_agentic_publication_method_writer.py tests/test_agentic_unified_context_compiler.py`：221 passed。最终代码上的全量 `python -m pytest -q`：3601 passed、3 skipped、7 warnings、12 subtests passed，exit 0。`python -m compileall -q src tests scripts` 与 `git diff --check`：exit 0。
- 尚无新 Writer completed、Candidate 或 Verified；原目录属于旧 SHA，且本轮改变了 V4/公式政策，不应把旧 Formalizer receipt 当作新代码的成功。7 个作者 required 公式仍 open、Research partial，P7 §7.2 未验收；必须重新生成新 run 的身份与成果，再检查产品 Writer/Binder/最终门。

## 2026-09-18 按 20260917 修复方案执行 WP0/WP1

范围：按 `docs/code2paper_repair_execution_20260917.md` 的强制顺序开工，只做 S0/S1；
未续跑 `/tmp/c2p-p7-ebcar-v4-intent-j9L1bn`，未发起任何 live 模型调用。

### S0 事故回归固定（WP0，提交 0395e25）

- 新增 `tests/regression_20260917/`：`incident_archive.py` 冻结 15 个归档 fixture 的
  Git blob SHA 与 sha256（双重身份），`conftest.py` 拒绝真实网络并校验归档零改动，
  `test_archived_failure_facts.py` 固定六条事故事实：attempt 3/4 为预发送拒绝
  （sent_to_caller=false、provider_usage=null、3>2/4>2）、只有 attempt 1/2 到达
  provider 且 attempt 2 是唯一 content repair；MA-S3 receipt 15/16 且聚合未完成；
  第 2 次缺的是两个 detail witness（完整响应 17 条 atom、0 条 detail、
  rendered_detail_ids 为空）；Writer 请求中 P3–P17 共 15 个空槽（无机制/detail/
  formula、targets 为空、共用同一 section 级 reader_goal、对象无逐段作者语义字段）；
  `RunIdentity.code_commit_sha` 等于目标 RepoSnapshot 的 EBCAR commit 287506e3，
  身份模型没有引擎 HEAD 字段；Formalizer 空 manifest 与 Writer manifest 同时合法。

### S1 引擎身份与目录准入（WP1，提交 d09a5d7）

- 新增 `agentic/authoring_execution_identity.py`：内容寻址引擎指纹（逐文件 sha256，
  排除产物/缓存/密钥/数据库）、`AuthoringExecutionIdentityV2`（引擎/目标/输入摘要
  分离，engine_root 不参与 digest）、目录准入状态机（含
  resume_exhausted_invocation 与 resume_engine_identity_unavailable）、跨进程 flock
  单写者租约（进程内幂等）、`verify_research_import`、create-or-validate 身份写入
  （不一致即拒，不改写历史身份）、只读的 `scan_exhausted_invocations`。
- 接线：`run_autonomous_method_agent(..., run_open_mode=...)` 在任何产物写入前完成
  准入/租约/身份，runtime 建立后复查目标 commit；CLI 增加
  `--run-open-mode {auto,new,resume,fork_authoring}` 并先做只读预检（拒绝时返回 2、
  零写入），正式准入在锁内复查。
- 行为变更（有意 fail-closed）：非空目录且无 `AuthoringExecutionIdentityV2` 时
  `auto`/`new` 一律拒绝；旧 RunIdentityV1 目录只能显式 `fork_authoring`；已耗尽内容
  预算的 invocation 在 resume 时直接阻断。这正是事故"重启即必死"的入口。

### 验证

- `python -m pytest -q tests/regression_20260917 -m 'not live_llm'`：34 passed。
- `python -m pytest -q -m 'not live_llm'`：3635 passed、3 deselected、
  12 subtests passed、7 warnings，exit 0（基线 3601 + 新增 34，无回归）。
- `python -m compileall -q src tests scripts`：exit 0；归档在回归期间逐字节未变。

### 未完成 / 下一步

- WP2（作者意图到达 Writer：局部 `author_intent_surfaces`、槽位分类与合并、
  零交集不升级证据、intent digest 覆盖 statement）尚未开始。
- WP3–WP7 未开始；live 验证（L1/L2/L3）未执行，需方案 §14.1 的显式授权与全新
  out 目录。

## 2026-09-18 WP2：作者意图真正到达 Writer（S2）

范围：方案 §6。编译器把"一个 story 槽位 = 一个必须写出的段落"改成"作者单元分类 +
受限合并 + 可审计去向"，并把页内作者语义与权限送到实际模型表面。

### 实现

- `intent_spine_models.py`：新增 `AuthorIntentSurfaceV1`（author_statement / intended_role /
  local_reader_goal / authority_surface / implementation_status / supporting_detail_ids /
  unresolved_points / source_content_digest），`ParagraphKindV1`
  （grounded_content / author_specification / expository_bridge / structural_only /
  unresolved）；`IntentNarrativeParagraphV4` 增加 paragraph_kind、author_intent_surfaces、
  surface_digest、implementation_status、unresolved_ids、source_story_ids、source_slot_ids、
  disposition；`IntentNarrativePlanV4` 增加 `source_intent_digest_version`。
- `intent_narrative_compiler.py`：新增 `SlotBindingDecision`（overlap/status/needs_research，
  零交集只能是 organizational_fallback）、`compile_author_intent_surfaces`、
  `compile_authoring_units`（分类 + 合并：同 section/同 kind/同 role/同 authority 且不承载
  argument unit 或 intent atom 才合并；mechanism 不相容不合并）、
  `compile_intent_content_digest`（覆盖 statement/role/priority/notes/关联证据/顺序/atom，
  版本 `intent-content-v2`）。段落改为由单元生成：structural_only 不生成正文，
  unresolved 以受限作者描述出现（authority 绝不升级为 repository_statement，且不带必需
  detail），每个单元都带 disposition。trace 增加 unit_kind_counts、unresolved_story_ids、
  structural_only_story_ids、non_writable_unit_ids。
- `section_writer.py`：`_WRITER_PARAGRAPH_NARRATIVE_FIELDS` 增加 WP2 字段，
  新增 `_compact_writer_author_intent_surfaces_for_llm` 保留作者内容与权限（不再只传 ID）。
- V4→V3 投影携带上述字段（V3 段落模型 extra=allow，digest 因此随语义变化）。

### 验证

- `python -m pytest -q tests/regression_20260917 -m 'not live_llm'`：40 passed
  （新增 `test_intent_writer_surface.py`：空槽不变成 grounded 段落、15 个同形空槽合并为
  ≤2 个受限单元、每个 story 都有去向、请求表面确实带 author_statement/local_reader_goal/
  authority/implementation_status、改 statement 不改 ID 时 source_intent_digest 与
  surface_digest 必变、零交集只是组织 fallback、must-cover 无归属仍为 unresolved 而非
  仓库事实）。
- `python -m pytest -q -m 'not live_llm'`：3641 passed、3 deselected、
  12 subtests passed，exit 0（S1 后 3635 + 新增 6，无回归）。

## 2026-09-18 WP3（部分）：witness 两阶段验收与结构化失败（S3）

范围：方案 §7.2/§7.4/§7.5。

### 实现

- `publication_transaction_contract.py`：新增 `ContractFailureV1`
  （code/stage/paragraph_id/target_kind/target_id/expected/observed/repairable_by），
  `ParagraphTransactionAssessmentV1` 增加 `validation_stage` 与结构化 `failures`；
  `assess_paragraph_transaction(..., validation_stage=...)`：
  - `writer_content`：必需目标不含 Binder 负责的 atom；detail 义务由明确的 detail
    witness 或**完整** atom 集合履行，完整 atom 集合之外的 atom 声明不再自动补齐
    detail（事故里"17 条 atom、0 条 detail"不能再被掩盖）。
  - `final_bound`：保持既有严格语义（detail 需要 detail witness + 全部必需 atom，
    或完整 atom 集合），负例不退化。
  - 未知 stage 直接 fail-closed（`unknown validation_stage`）。
- 结构化失败码：paragraph_missing、detail_witness_missing、atom_witness_missing、
  formula_consumer_mismatch、exact_span_not_in_body、target_out_of_scope、
  detail_semantic_mismatch、input_material_missing；target id 含冒号时按两刀切分，
  并按 (code, kind, target) 去重；执行层不再需要解析拼接字符串。

### 明确未上线（不可单独上线）

方案 §7.1（Writer 表面剥离 Binder 所有的 atom）**本轮回退**：页级门仍是
`final_bound`，它要求模型枚举全部 atom witness；一旦 Writer 看不到 atom 目标，
detail 将永远无法满足——即半条 §7.1 会导致 fail-closed 死锁，而不是更安全。
§7.1 必须与 §7.2 的页级配对（页接受改用 writer_content + 由确定性 Binder 保障
final_bound atom 绑定）一起落地，并先核实 binder 阶段确实产出 atom 绑定。

### 验证

- `python -m pytest -q tests/regression_20260917 tests/test_agentic_detail_atom_binder_and_trace_v2.py
  tests/test_agentic_publication_method_writer.py -m 'not live_llm'`：202 passed。
- `python -m pytest -q -m 'not live_llm'`：3646 passed、3 deselected、
  12 subtests passed，exit 0（S2 后 3641 + 新增 5，无回归）。

## 2026-09-18 WP3 完成：页级配对与 Writer 表面剥离 atom

先核实再上线：`publication_method_writer.py` 的 Binder 阶段（`_write_unified_v2_binder_receipts`
→ `binder_receipts_v2`）确实消费最终接受的 Writer 段落与 `section_inputs`（含完整 canonical
witness 合同），且**缺少或失败的 Binder 回执会 fail-closed 阻断发布**。因此可以把页接受
降到 `writer_content`，atom/条件/极性/接口由 Binder 负责。

- 页级两处 `assess_paragraph_transaction(...)`（missing_paragraph/invalid_count/
  required_target_count 的来源）改为 `validation_stage="writer_content"`。
- §7.1 上线：`_compact_writer_witness_contract_for_llm` 从 Writer 视图剥离
  `target_kind="atom"` 的目标，并记录 `binder_owned={owner, target_count}`；canonical
  合同不变，Binder 仍取完整 atom。
- 既有测试 `test_unified_page_projection_keeps_page_and_compacts_duplicate_contracts`
  原先断言 Writer 视图包含必需 atom——这正是方案 §7.1 要修的行为，已改为断言
  Writer 视图 targets 为空 + `binder_owned`，同时断言 canonical 合同仍保留 atom。
- 新增/恢复 `test_witness_projection.py` 两例：合成合同剥离 2 个 atom；事故真实请求
  P1__f1 的必需 atom 在 Writer 视图消失、detail 目标保留。

验证：`python -m pytest -q -m 'not live_llm'` → 3648 passed、3 deselected、
12 subtests passed，exit 0（无回归）。

## 2026-09-18 WP4（估量层）：输出工作量估量与页契约联合评估

范围：方案 §8.2/§8.4 的纯函数部分。**未接线**分页器（见下）。

- 新增 `src/code2paper/agentic/writer_output_workload.py`：
  `WriterOutputWorkloadV1`（语义段落数、required detail occurrences、Writer-owned /
  Binder-owned witness 数、公式消费数、JSON 开销、目标正文量、安全余量、预计输出
  tokens、basis_version、confidence、unknown_reasons）与
  `estimate_writer_output_workload(...)`；
  `PageContractEvaluationV1` 与 `evaluate_page_contract(...)`：同时检查
  `input_tokens <= max_page_input_tokens`、预计输出 <= 可用输出预算、以及
  `max_semantic_paragraphs_per_page` 候选上限；**输出预算未知时默认 fail-closed**
  （`output_budget_unknown`，可显式放宽）。
  `narrative_ordinal()` 按叙事序号排序（P2 在 P10 之前）。
  经验系数可经 `calibrated_profile` 注入；未标定时 confidence=uncalibrated，
  `DEFAULT_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE=6` 仅作待标定候选。

未接线（必须与重新标定一起做）：`fit_narrative_plan_to_page_budget._over_budget` 与
`extend_writer_worksets_from_narrative_plan` 的候选页接受点尚未调用
`evaluate_page_contract`。原因：WP2 改变了段落数（15 空槽合并），旧的分页/Obligation
分布尚未重新测量；在没有端到端页数回归的前提下改预算门，可能把 fail-closed 变成
误杀或漏放。下一步：先测量新的页分布，再把联合预算接到候选页接受点并重建
invocation plan/admission（§8.5）。

验证：`python -m pytest -q -m 'not live_llm'` → 3657 passed、3 deselected、
12 subtests passed，exit 0（S3 后 3648 + 新增 9）。事故页形状（16 段 + 真实 detail
义务 + atom witness）在 8192 输出预算下被判为不可行；无 atom 的过渡页输出成本非零；
Binder-owned atom 不计入 Writer 负担。

## 2026-09-18 WP4 接线：候选页接受点加入语义段落预算

- `unified_context_compiler.py` 新增 `_max_semantic_paragraphs_per_page()`
  （默认取 WP4 候选值 6，可用 `CODE2PAPER_UNIFIED_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE`
  覆盖，0 = 显式关闭该维度，非法值回落候选值）。
- `extend_writer_worksets_from_narrative_plan` 的候选页接受点（含 flush 后的单组复查）
  在输入预算之外增加"候选页语义段落数 > 上限"判据：超限时**先拆页**（flush 当前页，
  新页从该组开始），单组仍超限则保持既有的 typed block
  `UNIFIED_ATOMIC_PAGE_OVER_BUDGET`。atom→页归属与义务守恒由原分页逻辑保证，本改动只
  让页更小，不做段落 fragment 预拆（§8.1/§8.3）。
- 事故页形状（16 段）在默认上限下会被拆成多页，而不是作为一次 16 段事务发出。

仍未完成（下一步）：WP2 之后的端到端页分布尚未重新测量与登记；§8.5 的
invocation plan / lookahead reservation / admission 重建（不足时报
`run_budget_insufficient_after_repage`）未接。

验证：`python -m pytest -q tests/test_agentic_unified_context_compiler.py` 30 passed；
`python -m pytest -q -m 'not live_llm'` → 3658 passed、3 deselected、12 subtests passed，
exit 0。

## 2026-09-18 WP4 §8.5：拆页后预算不足的可解释失败码

- `unified_context_models.py` 新增
  `UNIFIED_RUN_BUDGET_INSUFFICIENT_AFTER_REPAGE = "run_budget_insufficient_after_repage"`。
- `unified_context_compiler.py` 新增 `_repage_budget_failure_code(plan_revision, exceeded)`：
  `plan_revision > 1`（分页/修订后的 plan）且越过 whole-run 预算时给出该码；普通
  `plan_revision == 1` 仍报既有 `unified_invocation_budget_exceeded`（既有码保留，
  便于兼容既有断言与日志）。
- 接入点：invocation gate 的 role 调用数检查与 total input tokens 检查（这两处正是
  拆页会增加的量）。语义是"拆页也必须过 whole-run 预算；不足要显式报告，不能以
  '只是拆页'为由截掉剩余页"（§8.5）。

验证：`python -m pytest -q tests/test_agentic_unified_context_compiler.py` 30 passed；
`python -m pytest -q -m 'not live_llm'` → 3659 passed、3 deselected、12 subtests passed，
exit 0。

## 2026-09-18 WP5 账本核心：事件序号与真实发送计数分离

新增 `src/code2paper/agentic/writer_attempt_ledger.py`（只读派生，不改写历史记录，I8）：

- `WriterAttemptCountersV1`：`event_seq`（历史 attempt，不可变）、`provider_send_count`、
  `content_attempt_count`、`content_repair_count`、`rejected_before_send_events`。
- `read_invocation_ledger_state(out_root, invocation_id)`：从 `attempt-*.completed.json`
  与 `attempt-*.content-acceptance.json` 派生状态；**accepted 只取内容验收**——传输层
  `delivery_status=accepted` 不算（事故里两次 provider 调用的 delivery 都是 accepted，
  内容验收都是 rejected）；拒发事件（`attempt_limit_exhausted:`）计入诊断但不计入发送/
  内容次数，并从中读出 `content_attempt_limit`。
- `build_resume_preflight(...)` → `ResumePreflightV1`：进入 Writer 主循环前给出
  `resume_exhausted_invocation` 结构化阻断（execution_id、invocation_id、
  content_attempts_used/limit、last_provider_attempt、last_content_failure_codes、
  rejected_before_send_events、allowed_next_action），零新增调用；缺目录/缺回执**不算**
  已耗尽（不把缺失当结论）。
- 历史 acceptance 失败项映射为结构化码（detail_witness_missing / paragraph_missing /
  authority_surface_violation / input_material_missing / detail_semantic_mismatch），
  调用方不需要解析 `detail:detail:` 这类拼接串。

事故归档实测：`event_seq=4`、`provider_send_count=2`、`content_attempt_count=2`、
`content_repair_count=1`、`rejected_before_send_events=(3,4)`、`exhausted=True`、
`last_content_failure_codes` 含 `detail_witness_missing`；已接受页（MA-S1）不被误判为耗尽。

仍未完成（WP5 剩余）：把计数器接到 Writer 调用边界（预发送拒绝不得推进内容尝试次数）、
限流/超时的独立 transport policy 与 `send_outcome_unknown` 保留 reservation、§9.5 的
崩溃点恢复用例。

验证：`python -m pytest -q tests/regression_20260917` 63 passed；
`python -m pytest -q -m 'not live_llm'` → 3664 passed、3 deselected、12 subtests passed，
exit 0。

## 2026-09-18 阶段收敛：现状、证据与剩余项交接

本轮不新增功能改动，只固化当前状态与下一步，避免后续会话重复摸索。

### 已完成并各自带离线证据（34ae0cf 之后 9 个提交）

| 提交 | 阶段 | 内容 | 证据 |
|---|---|---|---|
| `4a5de49` | S0 前置 | 引入执行方案文档 | — |
| `0395e25` | WP0/S0 | 事故归档冻结 oracle（blob+sha256 双身份）+ 6 条事故事实 | `tests/regression_20260917/test_archived_failure_facts.py` |
| `7038808` | WP1/S1 | 引擎内容指纹、`AuthoringExecutionIdentityV2`、new/resume/fork 准入、耗尽阻断、单写者租约、CLI `--run-open-mode` | `test_execution_identity.py` |
| `5eba40a` | WP2/S2 | 作者单元分类/合并、页内 `author_intent_surfaces`、`intent-content-v2` 指纹 | `test_intent_writer_surface.py` |
| `87ad104` | WP3/S3 | 两阶段验收（writer_content/final_bound）、结构化 `ContractFailureV1` | `test_witness_projection.py` |
| `1b10d12` | WP3/S3 | 页级配对（页接受=writer_content，atom 交确定性 Binder）+ Writer 视图剥离 atom | 同上 + `test_llm_section_writer.py` 更新 |
| `11169b1` | WP4 | 输出工作量估量与页契约联合评估（纯函数） | `test_output_feasibility.py` |
| `9d6dca1` | WP4 | 候选页接受点加入语义段落预算（先拆页） | 同上 + `test_agentic_unified_context_compiler.py` |
| `ea710d3` | WP4/§8.5 | `run_budget_insufficient_after_repage` 可解释失败码 | 同上 |
| `a7c4fc1` | WP5 读侧 | 事件序号 vs 真实发送计数、恢复前置检查 | `test_ledger_recovery.py` |

最后一次全量离线：**3664 passed、3 deselected、12 subtests passed、exit 0**。
工作区只剩两项有意不提交的内容：`docs/1.txt`（草稿）与 `paperbanana_single_shot`（submodule 内容变更）。

### 剩余项（按建议顺序，均为可独立开工的边界）

1. **WP4 收尾**：用冻结证据重新测量 WP2 之后的真实页分布，登记语义段落上限标定值；
   确认 invocation plan 构建路径不存在"剩余页被截断"的分支（只允许显式失败）。
2. **WP5 写侧**：`publication_method_writer.py` 调用边界
   （`attempt = last_started_attempt(...) + 1` 与 `publish_attempt_started(...)`）目前仍以
   **事件序号**决定是否拒发；应改为以 `read_invocation_ledger_state(...)` 的
   `content_attempt_count` 决定内容预算，使"预发送拒绝"不再消耗内容尝试（§9.2）；
   随后补 transport policy（限流/超时）与 `send_outcome_unknown` 的 reservation 保留，
   以及 §9.5 的崩溃点恢复用例（reservation 后未 send / send 后无 response /
   response 后未 completed / completed 后未 acceptance）。
3. **WP3 剩余**：§7.3 repair packet（失败页定向修复语义）、§7.4 binder 端"atom 仅用于
   定位候选 span"、§7.6 单一正文表面（段落对象为唯一真源、section_markdown 派生）。
4. **WP6**：新增 `authoring_artifact_index.py`（`(logical_role, phase, generation)` 解析、
   active 指针、digest 解引用）与 `build/validate_authoring_run_contract` 的 N/A 一致性。
5. **WP7**：`build_selected_narrative_plan(selection, ...)`（v4 路径 legacy 调用归零、
   无静默 fallback）、Writer 必需页缺口在 phase boundary 前置暴露。
6. **live 验证（L1/L2/L3）**：需方案 §14.1 的显式授权与全新 out 目录；本轮未运行任何
   真实模型调用，也未续跑 `/tmp/c2p-p7-ebcar-v4-intent-j9L1bn`。

## 2026-09-18 WP5 写侧：内容预算按真实发送计数（不再被拒发事件吃掉）

- `writer_attempt_ledger.py` 新增纯函数 `content_budget_exhausted(state, max_attempts)`：
  已接受 → False；否则只有 `content_attempt_count >= max_attempts` 才算耗尽。
- `publication_method_writer.py` 调用边界：`attempt = last_started_attempt(...) + 1` 仍作为
  **事件序号**用于收据身份，但"是否拒发"改为
  `attempt > max_attempts and (content_budget_exhausted(...) or 没有拒发事件)`：
  连续两次预发送拒绝不再把内容预算耗尽（此前 `attempt 3 > 2` 直接拒发，等于用一个
  从未发送过请求的页永久锁死）。拒发仍保留诊断收据（§9.2 允许），但不消耗内容尝试。
- 新增回归：`test_presend_refusals_do_not_consume_content_budget`（两次拒发、零发送 →
  不算耗尽；事故页 2/2 → 耗尽）、`test_accepted_invocation_is_never_exhausted`。

验证：`python -m pytest -q tests/regression_20260917` 65 passed；
`tests/test_agentic_publication_method_writer.py + regression` 211 passed；
`python -m pytest -q -m 'not live_llm'` → 3666 passed、3 deselected、12 subtests passed，exit 0。

## 2026-09-18 WP5 崩溃点分类（§9.5）

`writer_attempt_ledger.py` 新增 `read_attempt_outcomes` / `unsettled_reservations` +
`AttemptOutcomeV1`，按 attempt 汇总崩溃点状态：

| 状态 | 预留 | 语义 |
|---|---|---|
| `reservation_without_send` | 释放 | 已预留未发送：不得计费 |
| `send_outcome_unknown` | **保留** | 已发请求无响应：结果未知，不自动退款/重发 |
| `response_without_completion` | **保留** | 有响应缺 completed：可由 validator 重建 |
| `completed_without_acceptance` | 释放 | 缺内容验收：确定性 validator 重放即可，无需再调模型 |
| `rejected_before_send` | 释放 | 预算/合同拒绝：不消耗内容预算 |
| `settled` / `not_started` | 释放 | — |

事故归档实测：attempt 1/2 = `settled`，3/4 = `rejected_before_send`（与内容预算判定一致）。

验证：regression 67 passed；全量离线 3668 passed、3 deselected、12 subtests passed、exit 0。

## 2026-09-18 WP6：阶段化产物索引与合同 N/A 一致性

- 新增 `src/code2paper/agentic/authoring_artifact_index.py`（新增解析层，不重命名历史文件）：
  `ArtifactIndexEntryV1(logical_role, phase, schema_version, generation, path, status,
  semantic_digest, file_bytes_digest)` 与 `AuthoringArtifactIndexV1`（active 指针 +
  content_digest）；`build_artifact_index(out_root, reference_digests=...)` 只读扫描已知
  产物；`resolve_artifact(index, role, phase, out_root=..., expected_digest=...,
  allow_empty=...)` 对未知 role/phase、active 歧义、缺失、语义摘要不符、路径逃逸一律
  阻断（不按 mtime/字典序/无后缀猜当前对象）。
  状态包含 `valid_empty`（合法空产物）与 `source_snapshot`（兼容源快照，不是独立语义
  对象），二者不会被当成 active 真身。
- 事故归档验证：`consumer_workset_manifest:formalizer` = 空基础 manifest（valid_empty）、
  `:writer` = `.writer.2` 真身（active），两者各自可解析；`narrative_plan:authoring`
  默认取 `revision.2`，当按适配器记录的参考摘要解引用时取回 `narrative_plan_v3`，
  另一代标为 `superseded`；`allow_empty=False` 时空 manifest 报
  `artifact_empty_not_allowed`。
- `authoring_context_contract.validate_authoring_run_contract` 与 builder 共用同一
  required-key 判定：正当 N/A 不再被误报缺失；`allow_blocked` 明确为"允许不完整状态
  被记录/展示"的展示开关，不改变 satisfied，也不能作为发布 verified 的后门。

验证：regression 71 passed；全量离线 3672 passed、3 deselected、12 subtests passed、exit 0。

## 2026-09-18 WP7 §11.1：单一计划选择（v4 不再白跑 legacy builder）

- `publication_method_writer._build_narrative_plan_v3` 重构：**选择在构建之前决定**。
  * `v4`：只构建 V4，并由 `project_intent_plan_to_narrative_v3` 给出**一次**兼容投影；
    legacy builder 完全不执行（trace 记 `legacy_builder_executed=False`）。
  * `v3`：只跑 legacy builder（既有默认路径不变）。
  * `shadow`：两者都建，但只有 `v3` 可执行，且在 envelope 中显式标注
    `executable_plan_version`；影子调用仍走各自的 trace/meter。
  * 显式选定 `v4`/`shadow` 时 V4 编译失败**必须失败**（不变量 I2，不静默 fallback）；
    `v4` 选定但未编译出计划时报 `intent_plan_v4_selected_but_not_compiled`。
- envelope 新增 `executable_plan_version`，trace 新增 `plan_selection` 与
  `legacy_builder_executed`，使"这次跑的是哪套计划、有没有影子调用"可被直接断言。

验证：regression 75 passed（新增 `test_plan_selection.py` 4 例：v4 不调用 legacy、
v3 调用、v4 编译失败仍失败、shadow 双建单执行）；全量离线 3676 passed、3 deselected、
12 subtests passed、exit 0。

## 2026-09-18 WP7 §11.2：Writer 阶段边界的依赖前置检查

- `publication_method_writer.py` 在加载 Writer 持久恢复状态之后、进入调用循环之前，
  对**账本已出现预发送拒绝**的必需 invocation 做前置检查（事故签名：
  `attempt_limit_exhausted` 记录）。命中即返回结构化阻断：
  `writer_phase_boundary_blocked:blocked_by_stage=writer:primary_cause=...:invocation=...:
  content_attempts=used/limit:rejected_before_send=[...]:downstream_not_run=realizer,binder,
  section_composition,publication_audit`，不再跑完整个 Writer 循环后靠
  `writer_v2_invocation_acceptance_count:0` 事后暴露根因。
- 判据刻意收窄为"有预发送拒绝记录"而非"内容尝试用满"：声明了 retry reserve 的 repair
  流程（`test_writer_content_repair_uses_declared_retry_reserve_and_commits_only_after_acceptance`）
  没有这种记录，不会被误判为耗尽——该误判在首次全量回归中被既有测试抓到并已修正。

验证：regression 76 passed；受影响套件 98 passed；全量离线 3677 passed、3 deselected、
12 subtests passed、exit 0。

## 2026-09-18 WP4 标定：页内语义段落边界的实测结果

数据源：事故归档 `artifacts/runs/2026-09-17-ebcar-intent-v4-p7-j9L1bn` 的 24 个 Writer 请求
（请求侧 `narrative_plan.paragraphs` 数 × 对应 content-acceptance 结果）。

**重要修正**：此前把 `technical_payload.paragraph_ids`（页的原子段落，事故页=1）当成
"一次要写多少段"是错的；真正的输出工作量在**请求侧**段落列表（事故页=16），WP4 的估量
与上限必须喂请求侧契约。

实测三点边界（已写成常量并由回归钉住）：

| 边界 | 值 | 证据 |
|---|---|---|
| 首次调用即接受的最大段落数 | **2** | 2 段页全部首次 accepted；1 段页有一例需 repair |
| repair 可恢复的最大段落数 | **6** | 4 段与 6 段页都是"首次 rejected → repair accepted" |
| 实测不可一次完成 | **16** | 事故页首次与 repair 均 rejected（内容预算耗尽） |

因此 `DEFAULT_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE = 6` 是"依赖 repair 的边界"，不是"首次
即可接受"的安全值；若要追求首次即接受应显式下调到 2（代价是更多页与更多调用）。两条
边界与事故形状都可被回归重算，任何改动都会在 `test_page_calibration.py` 失败。

验证：regression 79 passed；全量离线 3680 passed、3 deselected、12 subtests passed、exit 0。

## 2026-09-18 WP6 写侧：索引发布与阶段输入快照

- `authoring_artifact_index.py` 新增：
  * `publish_artifact_index(out_root, ...)`：先构建索引对象、原子写入
    `artifacts/06_authoring/authoring_artifact_index_v1.json`，**读回校验 content_digest**
    后才算发布成功（半写对象不得成为 active）；`index_revision` 在已有索引基础上递增。
  * `ResolvedAuthoringSnapshotV1` + `build_resolved_authoring_snapshot(index, out_root,
    phase, required_roles)` + `write_resolved_authoring_snapshot(...)`：把某阶段需要的
    产物解析结果（相对路径 + 字节摘要 + 索引摘要）冻结成
    `resolved_authoring_snapshot_v1.<phase>.json`；reader 执行期间不再反复读 active 指针
    （§10.3）。缺必需产物即 fail-closed。
- 产物命名：索引固定路径 `artifacts/06_authoring/authoring_artifact_index_v1.json`；
  阶段快照按 phase 后缀区分。

验证：regression 81 passed；全量离线 3682 passed、3 deselected、12 subtests passed、exit 0。

## 2026-09-18 WP5 transport policy（§9.2）

新增 `src/code2paper/agentic/transport_retry_policy.py`（纯决策函数，无 I/O）：

- `TransportRetryPolicyV1`：`max_transport_retries`（默认 2，可经
  `CODE2PAPER_TRANSPORT_MAX_RETRIES` 覆盖）、指数退避（base/max，默认 1s/30s）、可重试
  状态码（429/500/502/503/504）、`counts_against_call_budget=True`、
  `unknown_outcome_retries=0`。
- `classify_transport_failure(status_code=/exception=/sent=)`：429/5xx → `retryable_status`；
  其他 4xx → `terminal_status`；已发送的 timeout → `transport_timeout`；未发送的连接失败 →
  `connection_error`；无法判定 → `unknown`（按结果未知 fail-closed 处理）。
- `next_transport_action(...)`：结果未知（timeout/unknown）→ **`preserve_reservation`**
  （保留 reservation，不自动重发/退款）；可重试失败受 `max_transport_retries` 与
  **run 调用上限**双重约束（`transport_retry_exceeds_call_budget`）；终态失败 → `fail`。
- 坏配置回落默认（不会变成无限重试或负数）。

仍未完成：把该策略接到实际调用重试点（`_default_llm_caller` / writer provider 调用路径
的异常分支），以及 `unsettled_reservations` 与写侧预算核算合并（避免双重扣费）。

验证：regression 87 passed（新增 `test_transport_policy.py` 6 例）；全量离线 3688 passed、
3 deselected、12 subtests passed、exit 0。

## 2026-09-18 WP3 §7.3：Writer 定向修复包

新增 `src/code2paper/agentic/writer_repair_packet.py`（纯函数）：

- `WriterRepairPacketV1`：repair_kind、escalation（`repair_in_place` / `replan_required`）、
  paragraph_id/section_id、missing_targets（kind + canonical id + reason_code）、
  allowed_edits、allowed_paragraph_ids（**有且仅有失败段落**）、
  `preserve_other_paragraphs=True`、`frozen_paragraph_digests`（已接受段落摘要，失败段落
  被排除）、原正文、authority_refs 与 content_digest；`as_request_payload()` 只暴露模型
  需要的最小修复载荷（不含内部冻结摘要）。
- `build_writer_repair_packet(...)`：按失败码决定 repair_kind 与允许的编辑面
  （detail→`paragraph_content`+`detail_witnesses`；formula→`formula_references`）；
  **权限越界 / 目标越界一律升级为 `replan_required`**（§7.3 末句：不能硬让 Writer 在
  错误段落加一句话过门），此时 allowed_edits/allowed_paragraph_ids 为空。
- `contract_failures_from_legacy_strings(...)`：只读兼容适配（历史 acceptance 失败项 →
  (code, kind, target)），执行层不使用拼接字符串判断（§7.5）。修正了一处解析错误：
  段落 id 自身含冒号（`MA-S3:P1__f1:detail:detail:…`），必须按 `:<kind>:` 标记切分而不是
  按位置切分。
- 事故 attempt-2 实测：两个 detail witness 缺失 → `repair_in_place`，
  targets = `mech_sym:f6cf5bdfe2ae16f0:15/76`，只允许改 `MA-S3:P1__f1`，
  `MA-S3:P3/P4` 摘要被冻结。

验证：regression 92 passed（新增 `test_repair_packet.py` 5 例）；全量离线 3693 passed、
3 deselected、12 subtests passed、exit 0。

## 2026-09-18 WP5 接线：传输失败分类进入 provider 调用分支

- `transport_retry_policy.py` 新增 `transport_failure_failure_code(...)`：把传输失败映射为
  稳定失败码——结果未知 → `send_outcome_unknown:<ExcType>`（保留 reservation、不自动重发）；
  终态 → `transport_terminal_failure:<ExcType>`；可重试 → `transport_retryable_failure:<ExcType>`
  （本层不自动重试，重试必须经策略与 run 预算）。
- `publication_method_writer.py` 的 provider 调用异常分支现在调用该分类器，并把结果追加到
  `blocked_reason`（保留既有 `writer_call_error:<Type>` 前缀以兼容既有断言），使持久片段
  可区分"结果未知"与"内容失败"。
- 结构性守卫测试：provider 调用分支必须包含分类器调用，否则策略层形同虚设。

仍未完成：`unsettled_reservations` 并入写侧预算核算（避免与既有
`unsettled_started_attempt_records` 双重扣费）；真实超时下的端到端集成用例（需注入会
超时的 caller）。

验证：regression 94 passed；全量离线 3695 passed、3 deselected、12 subtests passed、exit 0。

## 2026-09-18 WP3 §7.6：单一正文表面

新增 `src/code2paper/agentic/paragraph_prose_composer.py`（纯函数）：

- `compose_section_markdown(payload, ...)`：由**有序段落对象**确定性拼接正文，顺序用
  `narrative_ordinal`（P2 在 P10 之前），不使用字典序。
- `audit_prose_surface(payload, required_paragraph_ids=...)` → `ProseSurfaceAuditV1`：
  **本地闭集校验**（每个 required id 恰好一次、无重复、无越界、顺序符合叙事序号），
  不依赖 provider 是否支持 JSON Schema 的数组约束；同时判定 `section_markdown` 是否为
  派生物。序列化结果显式带 `valid`。
- `normalize_writer_section_payload(...)`：把响应归一为"段落对象唯一真源"，
  `section_markdown` 一律替换为确定性派生结果并标 `section_markdown_derived=True`；
  模型自带的那份不再作为正文来源（消除两表面漂移）。
- 事故实测：attempt-2 完整响应含 `section_markdown` + 16 段 → 审计通过、段落为真源；
  attempt-1 只写了 1 段 → 本地校验报出 15 段缺失；合成用例覆盖重复段、越界段、乱序段。

验证：regression 100 passed；全量离线 3701 passed、3 deselected、12 subtests passed、exit 0。

## 2026-09-18 WP3 §7.4：atom 只能帮助定位，不能单独证明 detail

- `publication_transaction_contract.py` 新增 `_atom_path_detail_verified(detail_id,
  constraints, witness_by_key)`：当 detail **自身声明了语义要求**
  （semantic_atom / conditions / polarity）时，其 atom 文本必须同时满足这些要求才能
  触发"完整 atom 集合补全 detail"；atom 文本缺失或不满足 → 返回 False，由调用方给出
  `detail_semantic_mismatch` 细分错误并计入 missing，而不是"见到 atom 就算写了"。
  detail 未声明要求时，完整 atom 集合仍是既有契约认可的无损证明（行为不变）。
- 现状说明：detail 键的约束当前是聚合占位（`exact: ()`/`semantic_atom: ""`/
  `polarity: "unknown"`），真实的语义要求挂在 atom 约束上（semantic_anchor /
  exact_excerpts / conditions / polarity），本守卫对两者都适用，是面向未来的收口。
- 测试（`test_witness_projection.py` 新增 2 例）：atom 定位成立 → detail 可补全；
  atom 文本不落在契约/语义内 → 拒绝且给出细分类失败码；直接单测守卫在"无要求/要求成立/
  要求不成立/文本缺失"四种输入下的判定。

> 过程记录：本条目两次测试失败均来自我写错的期望（臆造的 `detail_requirements` 字段、
> 把中性句判定为 positive 极性），而不是实现缺陷；已按判定器的真实语义改写测试。

验证：regression 102 passed；全量离线 3703 passed、3 deselected、12 subtests passed、exit 0。

## 2026-09-18 收尾核对：预留视角防双重扣费 + invocation plan 截断审计

### 1. 两种预留视角（WP5）

- **崩溃点视角**（`writer_attempt_ledger.unsettled_reservations`）：只保留"可能已产生
  真实开销且结果未知"（`send_outcome_unknown` / `response_without_completion`）；
  "已预留未发送"可安全释放。
- **预算视角**（`unified_invocation_ledger.unsettled_started_attempt_records`）：保守地把
  "started 且无 completed"都算作未结算。
- 结论：两者语义不同，**不得相加**；写侧预算核算继续只使用后者，前者用于诊断与结果
  未知处理。已在模块 docstring 写明契约，并用回归钉住：
  * 事故归档 4 个 attempt 都有 completed 回执 → 两种视角都必须为空（拒发事件不计费）；
  * "已预留未发送" vs "已发送无响应"在两种视角下的差异被显式断言。

### 2. invocation plan 截断审计（WP4）

对 `unified_context_compiler.py` 的 invocation plan 构建段（约 4107–4540 行）做只读扫描：
未发现对页/调用集合的切片截断（唯一的 `[:8]` 是错误信息里截断 ID 列表用于展示），
预算越界一律走 `UNIFIED_INVOCATION_BUDGET_EXCEEDED` / `run_budget_insufficient_after_repage`
等显式失败（该文件内相关错误常量出现 98 处）。结论：不存在"剩余页被静默截掉"的分支，
符合 §8.5。

验证：regression 104 passed；全量离线 3705 passed、3 deselected、12 subtests passed、exit 0。

## 2026-09-18 §15：authoring doctor（只读诊断）

新增 `src/code2paper/agentic/authoring_doctor.py` + `AuthoringDoctorReportV1`：
一条命令给出执行身份（引擎/目标是否分离）、各阶段状态、逐页内容预算余量与拒发事件、
首个根因与下游阻断、空语义段落数、Binder-owned 目标仍暴露给 Writer 的数量、
critical 阻断与 next action；全程只读（不写文件、不发请求），供 live 准入的
"doctor 无 critical 阻断"使用。

事故归档实跑输出：

```
EXECUTION       legacy identity; engine fingerprint unavailable
TARGET          EBCAR - Embedding-Based Context-Aware Reranker @ 287506e3e2df
FORMALIZER      0 receipt(s)
WRITER          4/5 sections complete; incomplete
REALIZER        20 receipt(s)
BINDER          not produced
PAGES           19/20 accepted
BLOCKED         inv:writer:MA-S3:page:751aa8b5… (2/2 content attempts)
INTENT SURFACE  27 paragraph(s) lack per-paragraph material
WITNESS OWNER   110 Binder-owned target(s) still shown to Writer
FIRST CAUSE     …writer_v2_invocation_acceptance_count:…:0
NEXT ACTION     read-only diagnosis or explicit authoring fork
```

过程中的两处口径修正（均由测试与实跑暴露，非实现缺陷）：
1. 页"已接受"必须同时看内容验收记录**与分节回执**（resume 复用页没有新的验收记录）；
2. 账本需要区分两种接受语义——`accepted`（**任一**含 repair 的验收通过 = 页内容完成，
   用于判断是否还需发送）与 `primary_accepted`（非 repair 的首次交付接受 = 页交付门
   语义）。此前把 repair 接受排除在 `accepted` 外，导致 3 个 repair 后已完成的页被误判
   为耗尽。

验证：regression 108 passed；全量离线 3709 passed、3 deselected、12 subtests passed、exit 0。

## 2026-09-18 §15 收口：doctor 进入既有 CLI

- `code2paper method-agent doctor --out <dir> [--json]`：走既有产品入口（不新增第二套
  CLI），只读诊断；文本渲染等价于 §15.1 的样式，`--json` 给结构化报告供自动化消费。
- 冒烟（事故归档）：exit 0，输出 19/20 页接受、1 页耗尽（2/2）、27 段缺材料、
  110 个 Binder-owned 目标仍暴露给 Writer、根因链路完整。

验证：regression 109 passed；全量离线 3710 passed、3 deselected、12 subtests passed、exit 0。

## 2026-09-18 S8：离线端到端（产品路径 + 身份/索引/doctor 全链）

新增 `tests/regression_20260917/test_authoring_end_to_end_offline.py`（provider=NONE，
无需 live 授权，纳入常规回归）：

1. 离线产品 run 写出 RunIdentity 与 **AuthoringExecutionIdentityV2**（引擎 commit、
   目标 commit、intent/claims 摘要齐备）与 run summary；
2. 索引与 doctor 在真实 run 上一致：执行身份条目为 `active`、发布 index revision=1、
   doctor 报 `AuthoringExecutionIdentityV2` 且引擎指纹可用、无
   `engine_fingerprint_unavailable` 阻断；
3. 重开语义（WP1 准入实测）：`new` 对非空目录被拒（`run_directory_not_empty`），
   同一身份 + 相同输入走 `auto` 解析为 resume 且**身份字节不变**；
4. fail-closed 不变量：离线 run 不写出非空 candidate/verified，也不误报耗尽。

**端到端测试发现的真实缺陷（已修）**：产物索引把"不含 `worksets`/`pages` 键"的产物
（身份、回执、计划）一律判为 `valid_empty`，会让 `allow_empty=False` 的读者错误拒绝这些
产物。已把判空收窄为"仅在产物自身声明 manifest 形状时才判空"。

验证：regression 113 passed；全量离线 3714 passed、3 deselected、12 subtests passed、exit 0。

## 2026-09-18 §14.1：live 准入预检（离线可跑，授权到手即可进 L1）

新增 `src/code2paper/agentic/live_admission_preflight.py` +
`tests/regression_20260917/test_live_admission.py`，并接入既有 CLI
（`code2paper method-agent live-admission ...` / `record-offline-receipt ...`）。

§14.1 的每一条必要条件都变成一个有名 gate，`ready=False` 时给出**具体阻断码**：

| gate | 阻断码 | 判据 |
|---|---|---|
| engine_identity | engine_identity_unavailable | 引擎 commit + 逐文件内容指纹可用（工作树 dirty 被折进 digest 并告警） |
| target_identity | target_identity_unresolved | 目标仓库 commit/tree 指纹可解析 |
| author_materials | author_material_missing | 作者意图与 claims 存在且非空 |
| model_profile_identity | model_identity_unresolved | provider/model 显式声明 |
| declared_budget | run_budget_not_declared | 上下文窗口、writer 调用数、输入 token 预算均显式 > 0 |
| transport_policy | transport_policy_unbounded | 重试有界、未知结果不自动重试、重试计入预算 |
| offline_suite_receipt | offline_suite_receipt_missing / _not_passed / _stale | 离线全链**真实结果回执**，且绑定当前 engine source digest |
| runtime_model_identity | runtime_model_identity_mismatch | `/health` 正常且 `/v1/models` 真的服务所配置模型 |
| run_open_decision | run_open_rejected:<code> | 复用 WP1 准入状态机（new/resume/fork 语义不重写） |
| doctor_critical_clear | doctor_critical_blocker | 已有 run 时 doctor 无 critical 阻断 |

设计要点：

- **只读**：不建 out 目录、不写身份、不发请求（测试断言 out_root 事后不存在）。
- **回执绑定**：`record-offline-receipt` 跑真实 pytest 并解析真实汇总行；换一行源码即失效
  （engine digest 变），杜绝"之前跑过"当作现状。
- **不重写语义**：目录准入直接调用 WP1 的 `validate_run_open`，模型配置走产品同一路径
  （`_apply_llm_profile` + `load_llm_config_from_env`），因此预检身份与 run 身份同源。
- **退出码**：`live-admission` 0 = 可进 live，3 = 明确不可进，2 = 输入错误。

冒烟（冻结事故归档，`--run-open-mode resume`）：NOT READY，`run_open_rejected:*` ——
归档无引擎指纹且 invocation 已耗尽内容预算，符合 §14.2 "保持失败身份，修复后再明确 fork"。

验证：`tests/regression_20260917/test_live_admission.py` 12 passed；全量离线见下。

补记（同一轮，预检收口）：

- **fork_authoring（L2）**：预检与启动器共用 `verify_research_import`，研究导入
  参与身份；无可信 checkpoint 或空壳 JSON（缺 `run_id`/`repo_snapshot_id`/
  `project_tree_hash` 绑定）→ `research_import_unverifiable` + 准入拒绝。
  预检因此对 L2 也能给出与真实 run **一致**的 execution_id。
- **作者材料口径**：author intent 必需；claims 在产品入口可选——未声明只告警，
  **声明了却缺失/为空**才阻断（不静默把身份降级成"无 claims"）。
- **CLI 路由修复**：`code2paper method-agent doctor|live-admission|
  record-offline-receipt` 之前会被 `supervised_method_agent_main` 当成未知子命令
  而 `parser.error`（doctor 的 CLI 实际不可达），或更糟——被包进 worker 监督进程
  从而创建 attempt 目录/进程清单/日志，破坏"预检只读"。现在这三个命令直接走
  `method_agent_main`，测试断言只读命令不产生任何 out 目录副作用。
- `record-offline-receipt` 在 engine root 下执行 pytest，回执 command 字段记录 cwd。

验证：`tests/regression_20260917/` + `test_agentic_method_agent_cli.py` +
`test_agentic_candidate_handoff.py` 共 163 passed；全量离线见下。

### live 执行顺序（授权后可直接照做；顺序有硬约束）

**顺序约束**：任何文件改动（含文档）都会改变 engine source digest → 使已录制的离线回执失效。
因此必须：**改完 → 提交 → 录回执 → 预检 → live**，中间不得再改任何文件。

```bash
# 1) 提交后录制离线全链回执（真实 pytest 结果，绑定当前引擎指纹）
python -m code2paper.cli.main method-agent record-offline-receipt \
  --out /tmp/c2p-live/offline-receipt.json          # 回执必须放在引擎树之外

# 2) 准入预检（只读；READY 才进 live）
python -m code2paper.cli.main method-agent live-admission \
  --repo <EBCAR> --out /tmp/c2p-live/L1 \
  --llm-profile tests/live/profiles/qwen38_vllm_budgeted.example.env \
  --run-open-mode new --context-tokens 131072 \
  --max-writer-calls <N> --max-input-tokens <N> \
  --offline-receipt /tmp/c2p-live/offline-receipt.json \
  --health-json /tmp/c2p-live/health.json --models-json /tmp/c2p-live/models.json

# 3) L1 失败局部任务重验（复用冻结研究证据，经同一 production 投影重建 MA-S3 页）
python scripts/run_authoring_replay.py \
  artifacts/runs/2026-09-17-ebcar-intent-v4-p7-j9L1bn /tmp/c2p-live/L1 \
  --repo <EBCAR> --resume MA-S3 \
  --profile tests/live/profiles/qwen38_vllm_budgeted.example.env --force-profile \
  --authoring-context-mode unified

# 4) L2 仅 fork 研究证据、重做整个 authoring（产品入口 → 会创建 IdentityV2 并走准入）
python -m code2paper.cli.main method-agent run \
  --repo <EBCAR> --author-intent <...> --out /tmp/c2p-live/L2 \
  --llm-profile tests/live/profiles/qwen38_vllm_budgeted.example.env \
  --run-open-mode fork_authoring \
  --research-stage-checkpoint <冻结归档中已校验 checkpoint>

# 5) L3 端到端 fresh + 跨项目（项目集合与预算在运行前冻结）
```

已知口径差异（必须在报告里如实标注，不能被当成已满足）：

- L1 走 `run_authoring_replay.py`，它写 `execution_record.json`（命令、退出码、code-state
  digest、运行账本前后键），但**不**创建 `AuthoringExecutionIdentityV2`；L2 走产品入口则创建。
  若要求 L1 也有 IdentityV2，需要把 replay 入口接到 `create_or_validate_execution_identity`
  （独立小改动，可用 provider=NONE 离线验证）。
- L1 通过 ≠ L2/L3 通过；L2 失败不得清 ledger 后标记为同一修复验证成功。

## 2026-09-18 §14.2 L1 入口接上 WP1 身份 + 两个真实缺陷

用户选择"先不跑 live，继续离线加固（把 L1 入口也接上 IdentityV2 等）"。

### 1. L1（回放）入口与产品入口共用同一准入实现

- `autonomous_method_agent._open_authoring_execution` → 公开为
  `open_authoring_execution`（产品入口与回放共用，避免两套相近准入）。
- 新增 `research_import_digest` 形参：回放永远从冻结证据出发，非 fork 模式也必须把
  "导入的研究证据"绑进身份，否则两份不同冻结输入会得到同一个 execution_id；
  fork 模式下以 checkpoint 校验结果为准，显式摘要与文件冲突即拒绝。
- `scripts/run_authoring_replay.py`：新增 `--run-open-mode`（默认 `auto`）、
  `--research-import`、`--author-intent`；身份在**任何进程产物之前**建立（早于 runtime
  ledger/token 汇总/frozen 拷贝）；被拒 → exit 2 且 fresh 根零污染，拒绝证据写在
  `<fresh>.execution_identity_rejected.json`；`execution_record.json` 记录
  `execution_identity`。

冻结输入默认值：意图图 `artifacts/intent_obligation_graph_v2.json`，研究导入
`artifacts/research_product/research_stage_checkpoint_v1.json`（事故归档实测
`verify_research_import` 通过，digest `sha256:aca55aa7…`）。

### 2. 缺陷（已修，高危）：run 根位于 `artifacts/` 之下时产物写到引擎树

`output_names._out_root` 无条件截断到第一个 `artifacts` 之前 →
`out_root=<ws>/artifacts/runs/<run>` 的全部产物被写进 `<ws>`。冒烟实测：
`publication_writer_result_v1.json`、`deterministic_preflight_v1.json` 出现在仓库
`artifacts/06_authoring/`（已留档到证据目录并还原仓库）。若不修，我原本推荐的 live
运行根（`artifacts/runs/...`，引擎指纹排除路径）会静默把证据写到 run 之外。

修复：仅当 `artifacts` 后紧跟**已知阶段目录**（由 `METHOD_OUTPUTS` 派生：
`01_input`…`10_run`、`research_product`）时才做"子目录 → run 根"归一化。
回归：`tests/regression_20260917/test_output_root_normalization.py`（含 writer 级用例，
已确认对旧实现会失败）。

### 3. 缺陷（未修，已留证）：`prepare` 根把冻结历史用量记成本次 run 的 token 用量

`token_usage_summary_v1.json` 报 `calls=45 / input=1164056 / output=57144`，而同轮
`model_calls: 0`、`/health`、`/models`、`/metrics` 全 `Connection refused`、墙钟 < 1s。
来源：`prepare` 复制冻结 Formalizer 阶段的 invocation 回执（带历史 usage），随后被计入
本次 run。对 §14.3 的"发送调用数 / 真实 tokens / 无效调用量"是失真的，需要区分
"本次发送"与"复用证据用量"。涉及账本口径，未擅自改。

### 4. 测试污染教训（已修）

在测试里直接调用 `run_authoring_replay.main()` 会把默认 live profile 应用进进程环境，
污染同一 session 的后续测试（全量套件出现 8 个与本改动无关的失败）。测试内调用 CLI
必须传显式空 profile 并快照/恢复 `os.environ`。

验证：全量离线 3740 passed、3 deselected、12 subtests passed、exit 0。

## 2026-09-18 §14.3：token 用量区分"本次发送"与"复用证据"（缺陷 2 修复）

上轮留证的缺陷已修：`--authoring-stage prepare` 复制冻结 Formalizer 阶段的 invocation
回执后，token 汇总把这 45 次历史调用（1.16M input tokens）记成**本次 run** 的用量——
同一轮 `deterministic_preflight_v1.json` 却是 `model_calls: 0`。这既让 §14.3 的效率口径
（发送调用数/真实 tokens/无效调用量）失真，也让"这次尝试是否真的发过请求"这条判断
（prepared 根续跑分支依赖 `calls == 0 and total_tokens == 0`）永远不成立。

修复：

- 复制冻结 Formalizer 阶段时写出**来源索引**
  `artifacts/06_authoring/reused_evidence_receipts_v1.json`（相对路径 + 复制时摘要）；
- 汇总时按索引 + 摘要比对分类：一致 → `reused_evidence`；索引声明但内容已被改写 →
  按"本次发送"保守计入并在 `provenance.content_changed_after_copy*` 留痕；
- `token_usage_summary_v1.json` 语义明确化：
  - 顶层 `calls`/`*_tokens`/`status` = **本次发送**（恢复续跑判断所依赖的语义）；
  - `reused_evidence` = 复用冻结证据的用量（不丢失、不冒充）；
  - `all_receipts` = 两者之和（与旧口径可对账）；
  - `provenance` = {sent, reused_evidence, unclassified}。
- 无来源索引时（既有调用方/测试）行为与旧实现逐字段一致。

实测（真实事故归档 + EBCAR 目标，零模型调用）：
```
sent_calls=0 sent_total=0 | reused_evidence_calls=45 reused_evidence_total=1221200
| all_receipts_total=1221200
```
证据：`artifacts/runs/2026-09-18-live-admission/token-usage-provenance-evidence/`
（`before-fix-*` / `after-fix-*` 对照）。

验证：regression 新增 `tests/regression_20260917/test_token_usage_provenance.py`（5 项）；
全量离线 3745 passed、3 deselected、12 subtests passed、exit 0。

## 2026-09-18 §14.3：质量报告（只报可机械复算的维度）

方案 §14.3 要求"不能只报 accepted_pages / pages"。新增
`src/code2paper/agentic/authoring_quality_report.py` +
CLI `method-agent quality-report --out <dir> [--json]`（只读，走既有产品入口）。

六个维度的处理方式（不编分数）：

| 维度 | 状态 | 来源 |
|---|---|---|
| 效率 | measured | invocation 账本（发送数/内容尝试/拒发）+ 回执 provider_usage + 预算信封 |
| 恢复健壮性 | measured | `scan_exhausted_invocations`、doctor 阻塞页、未结算预留、耗尽页失败码 |
| 意图覆盖 | measured/partial | `obligation_coverage_v2`（must-cover/有依据/未解决/显式缺口）+ 意图表面代理指标 |
| 信息利用 | partial | `method_authoring_closure_metrics_v1` 各块 + 消费回执计数 |
| 叙事质量 | partial | 仅代理指标（无段落材料的段数、阻塞页数），并声明"为 0 ≠ 合格" |
| 忠实性 | **not_measured** | 需要冻结证据 + 正文 + 逐句/逐公式比对；离线无判断者，不报分 |

关键口径（事故实测得出）：**接受必须看账本的内容验收记录**，不能看回执的
`delivery_status`——事故里两次 provider 调用的 `delivery_status` 都是 accepted，而页
最终未被接受（`task_status=partial`）。因此效率指标的首次接受率用
`primary_accepted`，repair 收益用 `accepted` + `content_repair_count`。

同时把"复用证据"口径接进报告：复用证据索引抽到产品侧
`src/code2paper/agentic/reused_evidence_index.py`（回放脚本改为调用它），
prepared 根里复制自冻结根的回执不计入本次 run 的效率指标，但以
`reused_evidence_invocations/receipts` 显式报出，不被静默丢弃。

事故归档实测（冻结 oracle）：40 invocations / 45 provider sends（2 次拒发无 provider
request）/ 19 接受 / 首次接受率 0.4 / repair 5 次中 3 次成功 / 1,164,056 input tokens；
唯一阻塞页 2/2 内容尝试耗尽，失败码 `detail_witness_missing` + `detail_semantic_mismatch`；
7 个 allowed formula、消费 0；27 段缺段落材料；comparison 状态 `not_available`
（无候选产物，不伪造 baseline）。

验证：`tests/regression_20260917/test_quality_report.py` 8 项；全量离线 3753 passed、
3 deselected、12 subtests passed、exit 0。

## 2026-09-18 §14.3：对照比较器（同冻结输入/同模型配置才可比）

新增 `src/code2paper/agentic/authoring_quality_comparison.py` +
CLI `method-agent compare-quality --baseline <dir|json> --candidate <dir|json> [--json]`
（只读；exit 0 = 可比，3 = 不可比，2 = 输入缺失）。

- 质量报告新增 `comparability` 锚点（进 content_digest）：
  `frozen_input_digest`（由 `authoring_run_contract_v1` 的 repo_snapshot_id /
  project_tree_hash / run_identity_digest / code_commit_sha 复算）、
  `model_identity_digest` + `profile_digest`（预算信封）、
  `engine_source_digest` / `execution_id`（IdentityV2，legacy 根为空）。
- 比较规则（fail-closed，且**不产生任何综合评分**）：
  - 冻结输入锚点缺失或不一致 → `comparable=False`，**不给差值**；
  - 模型身份缺失或不一致 → 同上；
  - **引擎指纹不同不阻断**——修复正是要比较的对象，差异记入 `scope_notes`；
  - 只有极性明确的机械指标（`METRIC_POLARITY`，如发送数↓、接受率↑、token↓）才给
    `better/worse/same`，其余一律 `unknown` + 原始 delta；
  - 任一侧 `not_measured` 的维度只声明"哪侧没测、为什么"，不出差值；
  - 缺候选产物 → `partial_evidence=True` 并声明"差异只代表已存证据，不代表完整正文质量"
    （§14.3 不伪造旧完整输出）。

事故归档自比实测：COMPARABLE，71 个指标 delta 全 0，`partial_evidence=True`，
faithfulness 两侧未测量并给出原因。

验证：`tests/regression_20260917/test_quality_comparison.py` 9 项；全量离线 3762 passed、
3 deselected、12 subtests passed、exit 0。

## 2026-09-18 不变量 I1–I10 核验 + 修复 I10 缺口

对 §3 的十条不变量逐条找执行点与测试证据，发现并修掉一个真实缺口。

| 不变量 | 执行点 / 证据 | 结论 |
|---|---|---|
| I1 证据权威不变 | 作者意图只进组织/自述；实现事实由 source manifest/研究证据支持（`test_intent_writer_surface.py`） | ✓ |
| I2 单一语义计划 | `test_plan_selection.py::test_v4_selection_does_not_execute_legacy_builder`（legacy 调用为 0） | ✓ |
| I3 段落/任务分离 | 页 manifest 与 owner page 唯一化（`test_output_feasibility.py`） | ✓ |
| I4 义务按 occurrence 守恒 | `assess_paragraph_transaction(paragraph_id, validation_stage)`：键为 `(paragraph, target_kind, target_id, stage)`，同一 detail 在两个段落分别评估 | ✓（构造级） |
| I5 split 不丢条件 | 分页/条件分配（`test_page_calibration.py`、`test_output_feasibility.py`） | ✓ |
| I6 发送≠内容接受 | 账本 `accepted` 只看内容验收记录（`test_ledger_recovery.py`；本轮质量报告实测同结论） | ✓ |
| I7 恢复不重置成本 | 身份 + 租约 + `build_resume_preflight`（`test_execution_identity.py`） | ✓ |
| I8 旧证据不可覆盖 | 产物索引只引用旧对象（`test_artifact_index.py`）+ 归档冻结 fixture | ✓ |
| I9 失败内容不可发布 | `test_authoring_end_to_end_offline.py`（candidate/verified 为空） | ✓ |
| I10 验收规则变更 → 身份变更 | **原为缺口**：`validator_bundle_digest` 恒为 `unspecified`，身份对验收规则改动是盲的 | 已修 |

I10 修复：新增 `VALIDATOR_BUNDLE_SOURCES`（封闭集合：`publication_transaction_contract`、
`writer_output_workload`、`unified_context_compiler`、`mechanism_context_pages`、
`writer_attempt_ledger`、`authoring_artifact_index`、`paragraph_prose_composer`）与
`capture_validator_bundle_snapshot()`（逐文件内容指纹 + 缺失/不稳定失败码）；
`build_run_open_identity` 现在绑定该指纹，并接受 `tokenizer_identity`
（缺省为显式 `unspecified` 标记）。刻意只收 contract 层：把整个 writer 收进来会让任何
重构都使 resume 失效，身份会失去区分度。

验证：`tests/regression_20260917/test_validator_bundle_identity.py` 5 项（含"改验收规则 →
指纹与执行身份都变""缺失来源如实报失败码而非留空"）；全量离线 3767 passed、
3 deselected、12 subtests passed、exit 0。

## 2026-09-22 审计方案接手：PR A（运行身份与 new/resume/fork 语义）

依据 `docs/Code2Paper_代码审计与修复执行方案_20260922.md`（冻结基线 `3aa9db8`）。
本轮完成 PR A 的 A.1（目标内容身份、失败码消费、有效配置身份）与 A.1.6 的未知模式拒绝；
A.2/A.3（出生信息与锁内二次准入）、A.4（导入闭包）留待下一轮。

### 已核实的审计论断（在当前工作树复现）

- **F02 成立**：`capture_target_identity` 用 `dirty_manifest_digest`（只含路径状态、不含
  文件内容），而 `build_run_open_identity` 把 target HEAD 写进
  `target_repo_snapshot_digest`、把 porcelain 摘要写进 `target_project_tree_hash`。
  最小反例：同一文件保持 `M`、HEAD 不变，仅内容 A→B，旧实现得到**同一身份**。
- **A.1.5 成立**：`build_run_open_identity` 只取 `validator_bundle.digest`，不消费
  `failure_code`——来源缺失时也给出"看起来可用"的指纹。
- **A.1.6 成立**：`publication_method_writer._build_narrative_plan_v3` 对未知
  `CODE2PAPER_INTENT_NARRATIVE_PLAN` **静默回退 v3**；有效配置（context mode、输出协议、
  tokenizer）也未进入身份。

### 本轮修复

1. `TargetRepoIdentity` 改为**内容**身份：复用既有 `build_repo_snapshot` +
   `build_repository_source_manifest` 的文件选择规则，新增
   `source_snapshot_digest` / `project_tree_hash` / `source_manifest_digest` / `file_count` /
   `failure_code`；`commit_sha` 与 porcelain 摘要降为诊断。
   路径不存在或零源文件 → `target_snapshot_unavailable:*`（没有字节就没有内容身份）。
2. 身份模型新增 `effective_config_digest`（进 payload：模式变了就不能 resume）与
   `target_git_commit`（诊断，**不**进 payload：同内容换 commit 不应失效）。
3. `build_run_open_identity` 新增 `require_usable_inputs=True`：引擎/目标/验收规则来源
   任一不可用即抛错（在任何模型发送之前）；预检传 `False` 把这些事实报成阻断项。
4. 新增 `authoring_run_config.py` 作为**唯一 owner**：
   `normalize_narrative_plan_mode`（未知值抛 `unknown_narrative_plan_mode`）与
   `capture_effective_config_digest`（narrative/context/输出协议/prompt/tokenizer/
   验收规则身份）。writer 与身份构造消费同一实现。
5. 接线复核（审计 §0.1 提醒的调用点核对）：`autonomous_method_agent` 的 runtime 复查
   原先拿 `target_repo_snapshot_digest` 与 runtime commit 比较——现在改用诊断字段比 commit、
   用 `project_tree_hash` 比内容；replay 身份报告补充 manifest/commit/effective config 字段。
6. live 准入新增 `validator_bundle_identity` gate 与有效配置失败路径（不可比即拒绝，
   不再解引用空身份）。

### 测试

新增 `tests/regression_20260917/test_run_identity_content.py`（10 项），含审计点名的
`test_target_dirty_content_change_invalidates_resume`、
`test_same_target_content_in_another_path_has_same_content_identity`、
`test_missing_validator_source_blocks_before_provider_send`、
`test_unknown_narrative_mode_is_rejected`（含真实 builder 路径）。

**测试夹具缺陷（已修）**：`tests/test_agentic_candidate_handoff.py::test_supervisor_preserves_real_worker_exception_finalizer`
把**全局** `subprocess.Popen` 换成假对象，连 git 子进程一起拦掉。PR A 之前引擎快照
不可用只是被静默容忍，所以没暴露；现在 fail-closed 会让 worker 抛 `ValueError` 而不是
预期的 `RuntimeError`。夹具改为只拦截监督器的 worker spawn（其余委托真实 Popen，
并补齐 `args`/`communicate`/上下文管理），这样它测的仍是"worker 异常终结器"。

### PR A.2 / A.3：出生信息与锁内二次准入（本轮）

**A.2 出生信息（修 F03）**

- 新增 `BirthMetadataV1`（creation_mode / parent_execution_id / research_import_digest）
  与 `AuthoringExecutionIdentityV2.birth_metadata`；新增 `resolve_open_identity()` 作为
  "本次动作 → 身份"的唯一 owner：
  - `resume` / `auto` 且已有完整身份 → **继承**出生信息（实测 fork 执行现在可以 resume，
    修复前 `resume_identity_mismatch: creation_mode`）；
  - 其它动作 → 按本次动作新建出生信息；`fork_authoring` 的 `parent_execution_id` 取自
    导入 checkpoint 的 `execution_id`（若存在）；
  - `resume` 时**显式提供**另一份 checkpoint → 拒绝（`research_import_digest_mismatch`），
    不静默忽略操作者提供的证据；
  - 旧目录没有完整身份时不猜，仍由 `validate_run_open` 拒绝。
- `preflight_run_open` 改用同一 resolver，并把输入不可用/导入不匹配翻译成类型化拒绝。

**A.3 锁内二次准入与租约生命周期**

- `acquire_run_lease` 的进程内幂等改为**校验 owner**：不同 execution 在同一 root 上
  直接 `RunLeaseHeld`（旧行为只要 root 相同就返回别人的锁）。
- 新增 `PENDING_LEASE_OWNER` 与 `RunLease.bind(execution_id)`：支持"先取锁 → 锁内解析身份 →
  绑定 owner"的序列，绑定后再拒绝其它执行。
- `open_authoring_execution` 重写为：只读预检（早退明显错误）→ 取锁 → **锁内**重新解析
  身份与目录状态 → `validate_run_open` → 绑定 → create-or-validate；任一拒绝/异常都释放锁
  （租约不泄漏给后续尝试）。
- 产品入口 `run_autonomous_method_agent` 的 `finally` 释放 lease 并从 `_ACTIVE_RUN_LEASES`
  移除：长寿命进程里的连续任务不再被自己的旧 flock 挡住。

**测试**：`test_run_identity_content.py` 扩到 15 项（新增 5 项：fork resume 出生信息守恒、
new 不继承旧出生、导入变更拒绝续跑、两个 new 打开者不能都准入、租约成功/异常都释放）；
`test_execution_identity.py` 的租约用例改为审计语义（同 owner 幂等、异 owner 拒绝）并新增
绑定用例。全量离线 3783 passed、3 deselected、12 subtests passed、exit 0。

**本轮事故与纠正**：第一次改 `authoring_execution_identity.py` 时用大段字符串切片替换，
把 `build_run_open_identity`/`capture_target_identity`/`RunLease` 等函数整段删掉；
已 `git checkout --` 还原该文件后改用定点编辑重做（后续同类改动一律小步定点 + 每步
compile/定向测试）。

### PR A.4：研究导入的闭包校验（本轮）

审计 §A.4 指出 `verify_research_import` 只验证 checkpoint 外壳。新增
`verify_research_import_closure(checkpoint, *, expected_project_tree_hash=None)`：

- **外壳**（既有）：文件存在、可解析、含 run_id / repo_snapshot_id / project_tree_hash；
- **provenance 绑定**：checkpoint 的 `project_tree_hash` 必须等于当前目标仓库的**内容**
  tree hash（实测事故归档的 `sha256:9b4f1a34…` 与本机真实 EBCAR 目标完全一致 → 严格校验
  不影响合法 L2 fork）；
- **必备权威材料**（8 项，封闭集合 + 各自模型校验）：intent_graph / agenda /
  atomic_claims / evidence_packets / code_facts / source_manifest / symbol_index /
  implementation_scope；
- **内容一致性**：会自封摘要的模型做"删 digest 重算必须等于原值"；声明了
  repo_snapshot_id/project_tree_hash 的产物必须与顶层一致；facts→packets→claims 的
  digest 引用链必须闭合；
- **路径安全**：manifest / symbol index 中声明的仓库路径必须相对、无 `..`/`~`/绝对路径；
- **禁止继承**：出现 `writer_*` / `content_acceptance*` / `binder_receipt*` /
  `publication_candidate*` / `invocation_budget*` / `active_pointer*` / `run_lease*`
  等 payload 即拒绝。

接线：`resolve_open_identity` 的 fork 分支使用闭包（并复用同一份 target 快照，
不重复计算）；`preflight_run_open` 与 CLI 得到类型化拒绝码；回放脚本的导入校验同样升级为闭包。

新增 `tests/regression_20260917/research_import_fixture.py`：以归档 checkpoint 为基、
**只对改写过的产物重新封装摘要**，生成"内容与摘要自洽"的真实形状 fixture（空壳 JSON 正是
审计要求拒绝的对象）。负面用例：缺失依赖、摘要链断裂、路径越界、夹带写作 payload。
另加 skip-guarded 端到端正例：真实 EBCAR 目标 + 事故归档导入 → 准入允许（本机已跑通）。

验证：regression 185 项全绿；全量离线 3786 passed、3 deselected、12 subtests passed、exit 0。
