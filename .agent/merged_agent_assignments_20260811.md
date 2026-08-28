# 自主 Method Agent 合并分派方案

- Date: 2026-08-11
- Purpose: 把原先 P0/A/B/C/D/E/F/G/H 细包合并成少数几个 OpenCode 对话可执行的大任务，减少同一文件并行修改冲突。
- Use with: `.agent/reorientation_report_20260811.md` and `.agent/parallel_work_packages_20260811.md`

## 0. 为什么合并

原细包适合分析依赖，但不适合直接并行开发。几个包会同时修改这些热点文件：

- `src/code2paper/agentic/publication_method_writer.py`
- `src/code2paper/agentic/method_argument_models.py`
- `src/code2paper/agentic/method_architect.py`
- `src/code2paper/llm/response_schemas.py`

所以实际分派改成 3 个大包。每个大包内部可以按原工作包细节推进，但文件所有权更清楚。

## 1. 合并后的 Agent 分派

### Agent 1 — Foundation / Planning Surface

合并原包：

```text
P0 共享产品契约
C 作者意图投影
D Method Architect 分级 gate
```

主目标：

把“作者意图 -> story spine -> lane-aware projection -> candidate/verified/readiness-aware section plan”这一层打通。它负责定义共享契约，避免其他 Agent 各自发明 lane/status/review schema。

主要文件所有权：

- `src/code2paper/agentic/method_argument_models.py`
- 可选新增 `src/code2paper/agentic/method_product_models.py`
- `src/code2paper/agentic/authoring_projection.py`
- `src/code2paper/agentic/intent_compiler_v2.py`
- `src/code2paper/agentic/intent_obligations.py`
- `src/code2paper/agentic/method_architect.py`

不要改或尽量不改：

- `src/code2paper/agentic/publication_method_writer.py`
- `src/code2paper/llm/section_writer.py`
- `src/code2paper/agentic/research_graph.py`
- `src/code2paper/cli/agentic_run.py`

交付重点：

1. 共享 lane/readiness/review/output policy 契约。
2. author-intent-first `author_story_spine` / equivalent projection。
3. writer/architect payload 区分：
   - repository verified facts；
   - partial facts；
   - mismatch；
   - author intent unverified；
   - literature/empirical/formalization pending；
   - review questions。
4. Architect 不再把 ordinary unresolved/external item 作为 candidate blocker。
5. exact placement / move proof / semantic frame 继续保留为 verified/audit metadata。

推荐测试：

- `tests/test_agentic_authoring_projection.py`
- `tests/test_agentic_intent_compiler_v2.py`
- `tests/test_agentic_method_architect_product_readiness.py`
- `tests/test_agentic_method_product_models.py`

交付记录：

```text
.agent/implementation_foundation_planning.md
```

### Agent 2 — Writer / Output / Validation / Callback Surface

合并原包：

```text
A candidate/verified/review 输出分离
E Writer content-first
G candidate/verified 验证分工
F callback/resume
```

主目标：

把写作和输出层恢复成产品语义：Writer 写 candidate，验证层筛出 repository verified，缺证进入 review/callback。这个 Agent 统一拥有 `publication_method_writer.py`，避免多个 Agent 抢这个核心文件。

主要文件所有权：

- `src/code2paper/agentic/publication_method_writer.py`
- `src/code2paper/llm/section_writer.py`
- `src/code2paper/llm/response_schemas.py`
- `src/code2paper/llm/role_config.py`
- `src/code2paper/agentic/final_text_claims.py`
- `src/code2paper/agentic/text_evidence_validator.py`
- `src/code2paper/agentic/writer_research_router.py`
- `src/code2paper/agentic/formalization_agent.py`

不要改或尽量不改：

- `src/code2paper/agentic/method_architect.py`
- `src/code2paper/agentic/authoring_projection.py`
- `src/code2paper/agentic/research_graph.py`
- `src/code2paper/cli/agentic_run.py`

交付重点：

1. `publication_candidate_method.md` 和 `repository_verified_method.md` 不再写同一文本。
2. `author_review_candidates.json` 必须有非空 `proposed_body`、确认问题、所需证据和建议动作。
3. ordinary evidence gaps 不阻止 candidate；只阻止 verified 或进入 review/callback。
4. Writer prose surface content-first，不再要求一次性填完 full IDs / moves / configs / equations / proofs。
5. post-processing / validation 决定哪些句子进入 verified。
6. candidate 可保留 caveated author-intent/review content；verified 保持 fail-closed。
7. repository/config/formalization callback 本地执行或返回明确 artifact；author/literature/empirical 生成 queue/review artifact，不再 silent `None`。
8. fulfilled callback 只恢复 affected section。
9. Writer decision 低温；Writer prose 中温配置可追踪。

推荐测试：

- `tests/test_agentic_publication_method_writer.py`
- `tests/test_llm_section_writer.py`
- `tests/test_llm_publication_schema_closed_sets.py`
- `tests/test_agentic_candidate_verified_split.py`
- `tests/test_agentic_final_text_trust.py`
- `tests/test_agentic_writing_route_execution.py`
- `tests/test_agentic_callback_resume_product.py`

交付记录：

```text
.agent/implementation_writer_output_validation.md
```

### Agent 3 — Research Product Runner / CLI Surface

合并原包：

```text
B Research 主流程
H 产品 CLI
```

主目标：

提供一个清晰产品入口：从 repo + author intent + claims 启动 autonomous research loop，产出 evidence/facts/claims/completeness/trace，然后调用 planning/writing surfaces 生成三类输出。它不负责重写 Writer 或 Architect 内部。

主要文件所有权：

- 可新增 `src/code2paper/agentic/autonomous_method_agent.py`
- `src/code2paper/agentic/research_graph.py`
- `src/code2paper/agentic/research_nodes.py`
- `src/code2paper/agentic/research_tools.py`
- `src/code2paper/agentic/runner.py`
- `src/code2paper/agentic/v3_runtime.py` only for compatibility isolation/adapters
- `src/code2paper/cli/agentic_run.py`

不要改或尽量不改：

- `src/code2paper/agentic/publication_method_writer.py`
- `src/code2paper/agentic/method_architect.py`
- `src/code2paper/llm/section_writer.py`
- `src/code2paper/llm/response_schemas.py`

交付重点：

1. 新增或重构 product runner，例如 `run_autonomous_method_agent(...)`。
2. product path 直接使用 research graph/tools，而不是 R8 legacy bridge / synthetic gaps / D5 matrix。
3. 输出标准 artifacts：
   - `evidence_packets.json`
   - `code_facts.json`
   - `atomic_claims.json`
   - `completeness_matrix.json`
   - `research_trace.json`
   - `typed_gaps.json`
4. 新增 CLI：

```text
code2paper method-agent run \
  --repo <repo> \
  --author-intent <file> \
  --claims <file> \
  --out <dir>
```

5. CLI summary 打印 candidate/verified/review/callback/gap 等产品信息，不默认运行 D5 matrix。

推荐测试：

- `tests/test_agentic_autonomous_method_agent.py`
- `tests/test_agentic_research_tools.py`
- `tests/test_agentic_v3_e2e.py`
- `tests/test_agentic_run_cli.py`
- `tests/test_agentic_autonomous_method_agent_cli.py`

交付记录：

```text
.agent/implementation_research_cli.md
```

## 2. 推荐调度

最稳调度：

```text
先跑 Agent 1，至少交付共享契约草案
  -> Agent 2 和 Agent 3 并行
  -> Agent 1 根据 Agent 2/3 反馈补契约兼容
  -> Codex 整合验收
```

如果必须三者同时开工：

1. Agent 1 先只做共享契约小提交/小 diff，尽快写入交付记录。
2. Agent 2 暂时通过 duck typing / optional imports 兼容契约未完成状态，但不要自建重复模型。
3. Agent 3 先做 product runner skeleton 和 CLI skeleton，暂不深入 Writer/Architect internals。

## 3. 给每个 Agent 的统一要求

每个 Agent 都必须：

1. 先读 `AGENTS.md`、`.agent/task.md`、`.agent/plan.md`、`.agent/reorientation_report_20260811.md`、本文件。
2. 不读写 `.agent-team/`。
3. 不 `git reset` / `git clean` / checkout / commit / merge。
4. 不修改 governing architecture/design/status/execution docs。
5. 不把 author intent 当 repository implementation fact。
6. 不降低 verified-output truth gates。
7. 不用 project literals / known answers 写 generic logic。
8. 交付记录写自己的 implementation 文件，不抢 `.agent/implementation.md`。

## 4. 最终整合验收

Codex 最后按下面检查：

1. 三个 Agent 是否共用 Agent 1 的契约。
2. candidate/verified/review 是否真正分离。
3. ordinary missing evidence 是否不再导致 candidate 空白。
4. verified unsupported positive implementation facts 是否为 0。
5. callback 是否 fulfilled 或 queued，不再 silent drop。
6. product runner 是否绕开 synthetic support / legacy matrix semantics。
7. 一个小 fixture 是否能产出：
   - candidate non-empty；
   - verified supported-only；
   - review JSON with proposed body；
   - trace with research/callback/gap reasons。
