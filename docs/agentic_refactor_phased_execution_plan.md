# Code2Paper Agentic 重构分阶段执行文档

版本：2.3

日期：2026-07-18

状态：M0、P0、P1、P2、P3 已完成并通过阶段门禁；P4 的 25-run 机器矩阵已在 `9a98c17` 冻结完成，后续真实项目修复的 Gemma 复测受服务不可用阻塞，named human review、cutover 与 rollout 尚未完成

执行负责人：Codex

当前实施分支：`codex/agentic-p4-benchmark-cutover`

上位设计：[agentic_refactor_final_design.md](./agentic_refactor_final_design.md)

当前逐项验收：[agentic_refactor_completion_audit.md](./agentic_refactor_completion_audit.md)

## 0. 文档定位

本文不是新的架构讨论，而是把最终设计拆成可以逐项实现、逐项测试、逐门禁验收的执行规范。实施过程中若本文与最终设计冲突，以最终设计中的科研可信度不变量为准；若文档与实际代码冲突，以代码和实际生成 artifact 的直接核验结果为事实基线，并先修正文档或建立迁移说明，不能靠放宽 gate 让实现“看起来符合”。

执行目标保持不变：把 Code2Paper 从固定 Python 多阶段流水线升级为作者意图驱动、代码证据约束、LangGraph 编排的可决策研究写作 Agent，同时保证每个最终方法原子 claim，以及方法图中的节点、边、标注，都能回溯到同一代码快照中的直接证据。

本文覆盖：

- M0、P0、P1、P2、P3、P4 六个阶段的范围、任务、代码落点、测试和退出门槛；
- 本地 Gemma 4/vLLM 的接入、能力探测、真实测试和重复性测试；
- artifact、状态、工具、validator、checkpoint 和 benchmark 的迁移顺序；
- 阻塞、回滚、兼容和人工 review 规则；
- 每一阶段可以直接执行的首批任务清单。

本文不授权通过删除 validator、降低证据阈值、接受任意 evidence ID 或跳过最终产物审计来提高完成率。

## 1. 执行原则

### 1.1 信任顺序

系统中的信息按以下顺序获得写作授权：

1. 同一仓库快照中的精确代码片段；
2. 从代码片段建立的直接 evidence；
3. 经语义验证的 atomic claim；
4. 只包含可写 claim 的 authoring projection；
5. 受 projection 约束的 plan 和正文；
6. 从最终正文反向生成并重新验证的 text trace；
7. 受 relation evidence 约束的 figure scene；
8. 与 scene contract 对账后的真实图形 asset；
9. 聚合所有 gate 状态和 digest 的最终 package。

作者意图决定“优先研究什么、重点写什么”，不能决定“代码是否支持”。模型决定候选路线、组织和表达，不能决定 validator 的最终通过状态。

### 1.2 纵向闭环优先

每个阶段必须形成可运行的纵向切片。优先完成“输入 → artifact → validator → route → summary”的闭环，再扩展模型自主性。不得同时大规模重写 legacy pipeline、state、tools、renderer 和 benchmark。

### 1.3 保守失败

以下情况必须 block 或进入有预算的 repair，不能静默降级为 success：

- claim 只有合法 evidence ID，但语义不相干；
- partial claim 丢失必要限定词；
- 最终正文出现 plan/projection 外的方法事实；
- figure edge 没有直接关系证据；
- validator 报告存在但状态为 failed；
- 源码或上游 artifact digest 已变化；
- 最终图形 asset 不存在，或与 scene contract 不一致；
- 模型输出无法通过结构化 schema 验证。

无模型、模型超时、模型拒绝或服务不可用时，可以使用确定性安全 fallback，但 fallback 不能降低 trust gate。

### 1.4 Artifact 优先于进程内状态

所有关键决策和验证均必须落盘。最终判定只能消费带 schema version、输入 digest、producer version 和状态的 artifact，不能依赖未持久化的 Python 对象或日志文本。

### 1.5 每阶段单独可回滚

每个阶段新增的 V2 contract 均先采用 side-by-side 输出。旧 artifact 可继续生成用于比较，但不再作为新 gate 的权威输入。若阶段回滚，只回退该阶段的 graph route/feature flag，不修改或伪造已经冻结的证据和审计记录。

### 1.6 不夸大验证能力

最终报告可以声明“在指定代码快照、证据策略和 validator 版本下完成 evidence-grounded validation”，不能声明已经形式化证明代码语义、运行时行为、性能结论或论文整体正确。静态代码证据无法回答的运行时 claim 必须要求 runtime trace 或降级/阻塞。

## 2. 当前事实基线

### 2.1 已有能力

当前仓库已经具备：

- 真实 `StateGraph`、条件路由和 bounded retrieval/evidence/revision 决策；
- model proposal 与确定性 safety merge 分离的决策机制；
- 作者意图解析、symbol/config/shell 检索、coverage critic 和 evidence repair；
- evidence freeze、claim verification、authoring planner、figure planner；
- invariant、traceability ledger、readiness、completion、evaluation 和 benchmark artifact；
- 9 个 legacy stage wrapper 的 LangChain `StructuredTool` 表面契约。

这些能力应保留并逐步升级，不重新实现一套平行系统。

### 2.2 当前关键缺口

当前实现的主要风险不是“没有 Agent”，而是 trust plane 仍以 ID 集合闭包为主：

- claim verifier 主要检查 evidence ID 和声明状态，缺少 claim-to-code 语义蕴含验证；
- authoring constraints 没有过滤所有正向输入字段；
- `method_claim_map` 仍可能通过首个 claim/evidence fallback 或段落位置绑定建立伪 trace；
- final trace 不是从最终 post-processed 文本反向生成；
- figure edge 由节点顺序和节点 evidence 并集构造，没有直接 relation evidence；
- agentic rendering 只产生 plan/manifest，不保证真实方法图 asset；
- invariant 主要在 rendering 前运行，缺少 post-render audit；
- graph 使用 `StateGraph(dict)`，没有 durable checkpoint/resume；
- agentic 依赖、console scripts、预算参数和 README 尚未完整发布化。

### 2.3 测试基线

截至本文编写时：

- 精选 agentic 相关测试为 `88 passed`；
- 全量 `pytest -q` 在 collection 阶段被 `DEFAULT_FIGURE_IMAGE_MODEL` 导入不一致阻塞；
- 该问题必须在 M0 修复，不能把后续阶段的测试结果建立在“只运行部分测试”上；
- 工作树已有大量历史/用户改动，执行时必须只修改当前任务涉及的文件，不清理或覆盖无关变化。

### 2.4 本地 Gemma 4 MTP 基线

从 2026-07-17 起，Code2Paper 的默认真实模型测试 profile 固定为本地 MTP-enabled Gemma 4，而不是历史上的非 MTP profile。本次从宿主环境直接核验：

- API root：`http://127.0.0.1:8000`；
- OpenAI-compatible base URL：`http://127.0.0.1:8000/v1`；
- served model ID：`gemma4-31b-nvfp4`；
- main model：`/data1/users/cuihengjia/models/Gemma-4-31B-IT-NVFP4`；
- MTP assistant：`/data1/users/cuihengjia/models/Gemma-4-31B-it-assistant`；
- 进程：PID 343158，vLLM active；
- GPU：0、1；tensor parallel size = 2；
- speculative method：`mtp`；
- `num_speculative_tokens=1`；
- `draft_tensor_parallel_size=2`；
- max model length：131072；
- vLLM fingerprint：`vllm-0.1.dev1+g978de8335.d20260703-tp2-3758d845`；
- native `response_format=json_schema` 实测通过。
- 当前 Code2Paper `coverage_critic` 真实 proposal schema 以 512-token 上限调用、解析通过。

启动脚本为：

```text
/data1/users/cuihengjia/models/Gemma-4-31B-IT-NVFP4/serve_2x5090_qwen36_env.sh
```

其中 `GEMMA4_MTP_NUM_SPECULATIVE_TOKENS` 的稳定默认值在脚本第 21 行，实际 `--speculative-config` 在第 115–119 行构建。运行进程参数已确认包含：

```json
{
  "method": "mtp",
  "model": "/data1/users/cuihengjia/models/Gemma-4-31B-it-assistant",
  "num_speculative_tokens": 1,
  "draft_tensor_parallel_size": 2
}
```

部署方提供的同一 128-token 请求基准为：原始 15.04 token/s，MTP 29.95 token/s，约 1.99×；draft 接受率 80/80；GPU 0 约 30.9 GB，GPU 1 约 30.0 GB。上述吞吐、接受率和显存是部署基准，本次 Code2Paper preflight 没有重复压测；本次独立确认的是服务身份、进程 speculative config、普通 completion 和 strict JSON Schema 能力。

MTP 对 Code2Paper 客户端是服务端透明的：客户端仍请求 `gemma4-31b-nvfp4`，不在 chat payload 中发送 `num_speculative_tokens` 或 assistant 路径。run manifest/profile 记录 MTP 元数据用于复现和审计，vLLM 启动配置决定推理是否实际启用 MTP。

本次还发现一个必须进入 M0 的兼容性风险：合成的双字段 strict schema 在某些 prompt/property-order 下会生成一个字段后持续输出合法空白，直到 `max_tokens` 才结束，最终 JSON 截断。64/256-token 两次合成测试均复现；使用仓库全局默认 12000 时请求等待超过 90 秒后被人工中止。实际 `coverage_critic` schema 在 512-token 上限下通过，因此这不是“Code2Paper 完全不可用”，也不能仅凭现有证据归因于 MTP；它证明所有节点共用 12000 输出上限不安全。M0 必须配置 node-specific output token budgets、记录 `finish_reason`，并让 schema 截断快速进入一次有界 repair 或 deterministic fallback。

这些值是当前验证基线，不是永久假设。每次 live suite 仍必须重新检查 `/health`、`/v1/models`；在同一宿主机上还要核对进程参数中的 `--speculative-config`，避免服务重启后误连到非 MTP 实例。

### 2.5 T007 回归基线

FastGS 的历史 T007 运行是 P0 的核心回归样本。执行时必须直接读取以下实际 artifact，而不是信任旧 handoff 中的二次摘要：

- `agentic_claim_verification.json`；
- `agentic_authoring_constraints.json`；
- `method_claim_map.json`；
- `agentic_traceability_ledger.json`；
- `agentic_invariant_audit.json`；
- 最终正文文件。

直接复核已经确认 C1/C5 在 claim verification 中没有可写证据，却仍通过 authoring scaffold/trace 路径进入后续 artifact。P0 的验收不是简单把 C1/C5 加进黑名单，而是从 contract 上消除所有同类泄漏。

## 3. 总体交付路线

| 阶段 | 核心目标 | 主要可信度增量 | 真实 Gemma 4 验证 | 退出条件摘要 |
|---|---|---|---|---|
| M0 | 可安装、可收集、可调用、可复验 | 建立可靠工程和模型基线 | 接口能力探测、node smoke、旧路线复跑 | 全量测试可收集；agentic CLI 可安装；live profile 可审计 |
| P0 | 正文语义证据闭环 | 消除 unsupported/错配 claim 泄漏 | toy + FastGS 真实写作/验证 | 最终 text trace 来自最终文本；无伪绑定 |
| P1 | Evidence V2 与 freshness | 证据绑定精确代码快照 | 修改源码后的 stale invalidation | 精确 excerpt digest；旧报告自动失效 |
| P2 | 方法图执行闭环 | 节点、边和真实 asset 可追溯 | Gemma scene proposal + 确定性 SVG | direct edge evidence 100%；post-render 通过 |
| P3 | 工具细化与可恢复编排 | Agent 决策可扩展但不可绕 gate | live 中断/恢复、重复调用、预算耗尽 | typed state、checkpoint、幂等工具稳定 |
| P4 | Benchmark、cutover、legacy 降级 | 用证据精度决定默认路线 | 多项目、多次 Gemma 4 shadow run | 达到硬阈值后才切默认 agentic route |

依赖关系固定为：

```text
M0 -> P0 -> P1 -> P2 -> P3 -> P4
       |      |      |      |
       +------ trust contracts ------+
```

P0 可以先使用 V1 evidence 兼容视图实现语义正文闭环；P1 再升级 evidence 身份和 freshness。P2 依赖 P1 的 direct evidence contract。P3 必须在 P0-P2 的 artifact schema 稳定后进行，否则 checkpoint 会固化错误 contract。P4 只能消费 P0-P3 产生的新指标。

### 3.1 Gate A-G 上线映射

| Gate | 含义 | 首次实施 | 成为正式 hard gate | 主要验收 |
|---|---|---|---|---|
| A | Source Integrity | P1 RepoSnapshot/EvidenceSpanV2 | P1 | 修改源码使旧证据和报告 stale |
| B | Claim Semantics | P0 semantic validator | P0，P1 后绑定 V2 | 无关 evidence ID、同义 unsupported、强因果均失败 |
| C | Authoring Contract | P0 projection/plan/final trace | P0 | forbidden claim 不进入正向输入和最终正文 |
| D | Text Quality | 保留现有 validators，P0 修正 status/digest | P0 | failed report 不能因文件存在而通过 |
| E | Figure Contract | P2 relation/scene | P2 | node/edge/annotation 均有 direct binding |
| F | Rendered Artifact | P2 post-render audit | P2 | 真实 asset 增删改元素均被发现 |
| G | Final Lineage | P1 digest lineage，P2 完整 final asset，P3 resume | P2/P3 | final text/figure/package 均来自 exact passed inputs |

最终 invariant 只能聚合这些 gate 的真实状态，不能自行补推语义支持。

### 3.2 最终设计完成条件到执行阶段的追踪

| 最终条件 | 主阶段 | 证明 artifact/test |
|---|---|---|
| 作者意图影响检索、section plan 和 figure emphasis | P0、P2、P4 | intent spec、decision trace、paired-intent benchmark |
| 每个最终 atomic claim 有语义匹配的 direct code evidence | P0、P1 | text evidence validation、EvidenceSpanV2 |
| partial 只写 supported fragment 并保留 qualifier | P0 | projection、plan、final text adversarial tests |
| final trace 从最终文本反向生成 | P0 | final text digest 与 text trace input digest 一致 |
| 不存在位置式或首项 fallback | P0 | authoring code test、T007 regression |
| 图节点/边/标注独立可追溯 | P2 | scene graph、relation validation |
| 实际方法图通过 post-render audit | P2 | SVG、render manifest、post-render report |
| validator 检查状态和 digest | P0、P1 | failed-status/stale-artifact tests |
| pre/post/final invariant 不可绕过 | P2、P3 | topology/policy/route tests |
| LangGraph 有预算、checkpoint、resume 和 trace | M0、P3 | state/manifest/checkpoint integration tests |
| LangChain tools 有 schema、幂等和 evidence policy | P3 | tool contract audit |
| toy 和真实项目可信 success 或解释性 block | 各阶段、P4 | live run packages、benchmark |
| agentic 不降低语义证据精度 | P4 | fixed vs agentic benchmark |
| 不把验证能力描述为形式化证明 | M0 文档、P4 报告 | terminology/assertion tests 和人工 review |

## 4. 阶段通用交付模板

每个阶段完成时必须同时交付以下内容：

1. 代码实现和 schema migration；
2. 单元、对抗、集成测试；
3. 至少一次无模型安全路径测试；
4. 该阶段要求的本地 Gemma 4 真实测试；
5. 真实运行的 run manifest、decision trace、validator report 和 completion 状态；
6. 与阶段开始时 baseline 的对比报告；
7. 已知限制、blocked 原因和下一阶段输入；
8. README/CLI 文档同步；
9. 不涉及 secret 的可复现命令；
10. phase gate 清单全部通过，或明确停止在 blocked 状态。

阶段状态只允许：

- `ready`：依赖已满足，尚未开始；
- `in_progress`：正在实现；
- `validation`：实现完成，正在执行完整 gate；
- `complete`：所有退出门槛通过；
- `blocked`：三次以上复核后仍有同一外部/基础设施阻塞，且无法安全推进。

“代码写完但 live test 未跑”不得标为 complete。

## 5. 跨阶段契约

### 5.1 ArtifactRef

所有新 artifact 引用至少包含：

```json
{
  "name": "agentic_text_evidence_validation",
  "path": ".../agentic_text_evidence_validation.json",
  "digest": "sha256:...",
  "schema_name": "TextEvidenceValidationReport",
  "schema_version": "2.0",
  "producer": "ValidateFinalTextEvidenceTool",
  "producer_version": "...",
  "input_artifact_digests": {
    "final_text": "sha256:...",
    "authoring_projection": "sha256:...",
    "evidence_snapshot": "sha256:..."
  },
  "created_at": "..."
}
```

`created_at` 只用于审计，不能参与语义 cache key。权威身份由 schema、producer、输入 digest 和内容 digest 构成。

### 5.2 GateResult

所有 gate 使用统一状态：

```text
passed | failed | blocked | skipped
```

其中：

- `passed`：所有 required checks 已执行且通过；
- `failed`：输入完整，但发现可信度违规；
- `blocked`：缺少输入、模型/工具不可用或预算耗尽，无法完成判断；
- `skipped`：仅允许显式非必需能力，hard gate 永远不能 skipped 后进入 finalize。

报告必须同时记录 `blocking_issues`、`warnings`、`repair_route`、`input_artifact_digests`。系统不能把 artifact 文件存在等同于 `passed`。

### 5.3 模型提议契约

Gemma 4 或其他模型的输出一律视为 proposal。处理顺序固定为：

```text
prompt + bounded context
  -> raw model response
  -> JSON/schema parse
  -> deterministic normalization
  -> deterministic safety merge
  -> validator
  -> persisted decision trace
```

raw response 解析失败时不能直接从自然语言猜测 route。允许在预算内执行一次 schema-repair prompt；仍失败则使用安全 fallback 或 block。

### 5.4 预算契约

目标 CLI/state 至少支持：

- `max_retrieval_rounds`；
- `max_evidence_revision_rounds`；
- `max_authoring_revision_rounds`；
- `max_figure_revision_rounds`；
- `max_semantic_verifier_calls`。

预算满足以下规则：

- CLI、state、checkpoint、run manifest 和 decision trace 使用同一值；
- 模型不能提高预算；
- 每次调用前原子扣减，失败调用也计入模型调用预算；
- cache hit 记录但不重复扣远程/本地模型调用成本；
- 预算耗尽时 route 只能是安全完成、人工 review 或 blocked。

### 5.5 Feature flag 与兼容

迁移期建议显式提供以下配置，名称可在实现时统一，但语义不能省略：

- `--trust-contract v1|v2`：迁移期选择 gate contract，P4 后默认 v2；
- `--semantic-validator deterministic|model-assisted`；
- `--figure-renderer structured-svg|paperbanana`；
- `--checkpoint-backend none|memory|sqlite`；
- `--resume-run-id`；
- `--live-model-profile` 或等价配置入口。

V1 只用于 shadow comparison。P0 之后，正式 agentic success 必须由 V2 text gate 决定；不得通过选择 V1 绕过。

### 5.6 Git 版本管理契约

#### 5.6.1 当前仓库事实

仓库已经初始化为 Git repository，不再重复执行会混淆历史的“重新初始化”。本文编写时的事实基线为：

- repository root：当前 Code2Paper workspace；
- 集成分支：`master`；
- 已存在的父基线提交：`dc4146d`，提交说明为 `chore: snapshot current story-first pipeline refactor`；
- 当前规划分支：`codex/agentic-refactor-plan`；
- 当前没有配置 remote；
- 工作树包含大量在本文之前已经存在的 modified/untracked 文件；
- Git 操作必须采用 scoped staging，禁止把既有改动和生成物混入阶段提交。

父基线 commit 只说明 Git 历史起点，不代表当前未提交 agentic 代码已经完整纳入版本管理。M0 必须完成 tracked/untracked inventory，明确哪些属于产品源码、测试、vendor/submodule、数据集和生成物。

#### 5.6.2 分支模型

采用短生命周期阶段分支：

```text
master
  └── codex/agentic-refactor-plan
        ├── codex/agentic-m0-baseline
        ├── codex/agentic-p0-text-trust
        ├── codex/agentic-p1-evidence-v2
        ├── codex/agentic-p2-figure-trust
        ├── codex/agentic-p3-tools-checkpoint
        └── codex/agentic-p4-benchmark-cutover
```

实际执行规则：

1. 当前规划分支只承载最终设计和执行文档基线；
2. M0 分支从规划基线 commit 创建；
3. 后续阶段从上一个通过 phase gate 的 commit/tag 创建；
4. 不从带有未审计失败 artifact 的临时 commit 创建下一阶段；
5. 每个阶段可以包含多个原子 commit，但只产生一个 phase-gate tag；
6. 阶段完成前不把下一阶段的大规模代码提前混入；
7. 合并策略优先保留可审计的原子 commit；若使用 squash，phase validation report 必须保留原任务映射；
8. 不允许对已经作为 benchmark 输入或 phase baseline 的共享分支执行 force push。

若仓库后续配置远程协作，默认分支保护至少要求 full suite、phase-specific gate 和 secret scan 通过。当前无 remote 时，同样在本地执行等价检查。

#### 5.6.3 原子提交规则

提交前固定执行：

```bash
git status --short
git diff -- <scoped paths>
git add -- <explicit paths>
git diff --cached --check
git diff --cached --stat
git diff --cached
```

禁止在当前脏工作树使用：

- `git add -A`；
- `git add .`；
- 为了获得干净状态而执行 `git reset --hard`；
- 未经逐文件确认的 `git clean`；
- 覆盖用户改动的 `git checkout -- <path>`；
- 把 API key、`.env`、模型 cache、完整输出目录或 checkpoint 数据库加入提交。

每个 commit 应满足一个清晰目的并保持可测试。推荐提交类型：

- `docs(agentic): ...`：设计、执行、迁移或验证文档；
- `chore(repo): ...`：ignore、packaging、scripts、CI 基线；
- `fix(cli): ...`：collection、CLI、provider compatibility；
- `feat(trust): ...`：projection、semantic validator、freshness、figure gate；
- `feat(agentic): ...`：graph、tools、state、checkpoint；
- `test(trust): ...`：gold/adversarial/集成测试；
- `bench(agentic): ...`：benchmark schema、runner 和规范化结果；
- `refactor(agentic): ...`：不改变信任语义的结构迁移。

一个 commit 不应同时包含“新增 schema”“重写 renderer”“更新 benchmark 阈值”等多个可独立回滚的目标。测试与对应实现可以同 commit，或先提交不会破坏主分支的 contract test；共享阶段分支上的每个 commit 都应通过其直接相关测试。

#### 5.6.4 阶段 commit 序列

每个阶段推荐使用以下序列：

```text
1. contract/schema + migration tests
2. deterministic implementation
3. graph/tool integration
4. adversarial tests
5. Gemma 4 live compatibility or behavior changes
6. docs/CLI updates
7. phase validation report
8. annotated phase tag
```

若 live test 暴露 bug，修复作为新的 commit，不修改或删除原失败记录。最终 validation report 同时引用失败 run 和修复后 run，证明问题确实关闭。

#### 5.6.5 Tag 与基线命名

通过 gate 后创建 annotated tag：

```text
agentic-plan-v1
agentic-m0-baseline-v1
agentic-p0-text-trust-v1
agentic-p1-evidence-v2-v1
agentic-p2-figure-trust-v1
agentic-p3-resumable-v1
agentic-p4-cutover-candidate-v1
```

tag message 至少包含：

- phase 和 contract version；
- commit identity；
- unit/full/live test 摘要；
- Gemma 4 model/capability profile digest；
- 成功/正确 block 的真实项目清单；
- 已知限制；
- validation report 路径。

未通过 phase gate 不得创建正式 phase tag。实验性里程碑使用 `exp/` 分支或轻量本地说明，不能伪装为 release baseline。

#### 5.6.6 应跟踪与不应跟踪的内容

应进入 Git：

- `src/` 下产品代码；
- 结构化 tests、fixtures、gold/adversarial 标注；
- schema、prompt template 和默认安全 policy；
- `pyproject.toml`、README、迁移和执行文档；
- 不含 secret 的 `.env.example`/model profile example；
- 小型、规范化、脱敏的 baseline index 和 phase validation report；
- 复现真实运行所需的命令模板和 artifact digest 清单。

默认不进入 Git：

- `outputs/`、`output/`、`results/`；
- checkpoints 和 `*.sqlite*`；
- LLM response cache；
- `.env`、API keys 和本地 endpoint credentials；
- `__pycache__`、pytest/mypy/ruff cache；
- 完整 Gemma 4 raw response/output package；
- 生成的 PDF/PNG、大型 SVG 或中间 TeX，除非是明确的小型 test golden；
- 数据集仓库副本、模型权重和 vendor nested `.git`。

大型 benchmark 产物存放在外部/本地 artifact root，Git 只跟踪 `run_index.json`、digest、schema version、model profile digest、评测摘要和可复现命令。需要长期共享大型二进制时，单独决策使用 Git LFS、DVC 或对象存储，不能直接塞进普通 Git history。

#### 5.6.7 `.gitignore` M0 要求

当前 `.gitignore` 本身尚未进入 tracked baseline，且缺少部分实际生成目录。M0 应以独立 commit 审计并补齐，而不是在文档 commit 中顺带吸收所有未跟踪文件。至少检查：

```gitignore
outputs/
checkpoints/
.code2paper/
.llm_cache/
*.sqlite
*.sqlite-shm
*.sqlite-wal
.env
.env.*
!.env.example
```

对 `datasets/`、`paperbanana_single_shot/`、`.agent-team/` 等现有目录不能盲目统一 ignore：先决定其角色是外部数据、vendor/submodule、执行记录还是正式源码，再通过单独 commit 落定。nested Git repository 优先使用 submodule 或明确的 vendor policy。

#### 5.6.8 Dirty worktree 协议

当前规划提交采用以下隔离方式：

1. 创建专用分支，但保留所有既有工作树改动原样；
2. 只 `git add -- docs/agentic_refactor_final_design.md docs/agentic_refactor_phased_execution_plan.md`；
3. 暂存后核对 staged diff 中只有两份文档；
4. 不 stash、不 reset、不 clean 其他文件；
5. 后续 M0 首先生成 untracked inventory，将产品代码与生成物分开；
6. 若某任务文件与既有用户改动重叠，先阅读 staged/unstaged diff，使用最小 patch，并在 commit message/validation report 说明。

阶段实现期间，每次提交前都必须执行：

```bash
git diff --name-only --cached
git status --short
```

只要 staged scope 出现非任务文件，就先取消该文件暂存并复核，不能“提交后再修”。

#### 5.6.9 回滚与修复

已共享或已打 phase tag 的提交使用 `git revert` 回滚，不重写历史。回滚 trust contract 时还必须：

- 提高/改变 schema version，或恢复到明确兼容版本；
- 使受影响的 checkpoint 和 artifact cache 失效；
- 标记哪些 benchmark run 不再可比较；
- 重跑对应 phase gate；
- 不删除旧失败 artifact/index。

仅本地、未共享且未作为任何 baseline 的临时 commit 可以交互式整理，但不能用破坏性 reset 处理用户工作树。

#### 5.6.10 Git 与 phase gate 的绑定

每个 phase validation report 必须记录：

```json
{
  "branch": "codex/agentic-p0-text-trust",
  "commit": "<full sha>",
  "parent_phase_tag": "agentic-m0-baseline-v1",
  "dirty": false,
  "scoped_dirty_exceptions": [],
  "contract_version": "2.0",
  "tests": {},
  "live_runs": [],
  "artifact_indexes": [],
  "phase_gate": "passed"
}
```

正式 benchmark 和 cutover 必须从 clean tracked commit 运行。若因当前仓库历史遗留不得不保留 scoped dirty 文件，必须列入 `scoped_dirty_exceptions` 并证明它们不在 repo snapshot/test scope；P4 前该例外列表应清零。

## 6. 本地 Gemma 4 真实测试规范

### 6.1 测试目的

本地 Gemma 4 用于验证：

- 真实模型是否能稳定生成每个 decision node 的结构化 proposal；
- 作者意图是否真实改变检索、section plan 和 figure emphasis；
- safety merge 是否能拒绝越权 proposal；
- 同一模型作为 writer/critic 时，trust plane 是否仍能阻止自我确认；
- 模型波动是否会产生伪 trace、错误 success 或不可解释 block；
- checkpoint/resume 后是否避免不必要的重复推理。

它不能作为唯一可信度 oracle。语义 verifier 可以模型辅助，但最终结论必须经过确定性规则、direct evidence contract 和保守 merge。

### 6.2 本地 profile

本地真实测试使用不含 secret 的 MTP profile 元数据。当前默认 profile 为：

```text
tests/live/profiles/gemma4_mtp_vllm.example.env
tests/live/profiles/gemma4_mtp_vllm_capabilities.json
```

示例环境：

```bash
export CODE2PAPER_LLM_PROVIDER=openai
export CODE2PAPER_OPENAI_BASE_URL=http://127.0.0.1:8000/v1
export CODE2PAPER_LLM_MODEL=gemma4-31b-nvfp4
export CODE2PAPER_DEFAULT_LLM_MODEL=gemma4-31b-nvfp4
export OPENAI_API_KEY=dummy-local-vllm
export CODE2PAPER_LLM_CACHE=0
export CODE2PAPER_LLM_TEMPERATURE=0
export CODE2PAPER_LLM_MAX_OUTPUT_TOKENS=4096
export CODE2PAPER_LLM_TIMEOUT_SECONDS=300
export CODE2PAPER_LLM_RETRY_MAX_ATTEMPTS=2
export CODE2PAPER_RUN_LIVE_LLM=1
export CODE2PAPER_LIVE_PROFILE=gemma4_mtp_vllm
```

`dummy-local-vllm` 只适用于无需真实鉴权的 loopback 服务。若本地服务启用鉴权，真实 key 只能存在于用户环境，不得写入 profile、artifact、日志或测试快照。

加载 profile：

```bash
source tests/live/profiles/gemma4_mtp_vllm.example.env
```

4096 是当前全局兼容上限，不是所有节点的目标输出长度。L0/L1 decision smoke 应显式使用 256–512；正文写作按独立 writer budget 配置。M0 完成 node-specific budget 后，profile 不再用一个全局值替代节点预算。

profile 还记录以下 deployment expectations，供 live harness 在同宿主机核验：`inference_mode=mtp`、TP=2、speculative tokens=1、draft TP=2 和 MTP assistant 路径。这些 expectation 当前不是 `LLMClient` 请求字段；M0 adapter/harness 实现后才自动检查。正式测试在自动检查上线前使用 `/v1/models` + process args 的人工/命令式 preflight。

除非专门进行 MTP on/off 性能对照，M0-P4 所有 `agentic_gemma4` 真实测试均指这个 `gemma4_mtp_vllm` profile。不得在同一 benchmark variant 内途中特意关闭 MTP 或调整 speculative tokens。

### 6.3 服务预检

每次 live suite 前执行四层预检。

第一层：服务健康和模型身份。

```bash
curl --fail --silent http://127.0.0.1:8000/health
curl --fail --silent http://127.0.0.1:8000/v1/models
```

记录：endpoint、model ID、max context、服务类型/版本（若接口提供）、检查时间。不得只检查端口是否打开。

第二层：MTP deployment identity。若测试与服务在同一宿主机，读取 vLLM process args，确认同时存在：

```text
--tensor-parallel-size 2
--device-ids 0,1
--speculative-config {"method":"mtp",...,"num_speculative_tokens":1,"draft_tensor_parallel_size":2}
```

如果测试端只能访问远程 API，则 deployment identity 必须由受控服务 manifest 提供；`/v1/models` 本身不能证明 speculative decoding 已启用。

第三层：普通 chat completion。

```bash
curl --fail --silent http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer dummy-local-vllm' \
  -d '{
    "model": "gemma4-31b-nvfp4",
    "temperature": 0,
    "max_tokens": 64,
    "messages": [
      {"role": "system", "content": "Return one JSON object only."},
      {"role": "user", "content": "Return {\"status\":\"ok\"}."}
    ]
  }'
```

第四层：当前客户端实际使用的 strict JSON schema。

```bash
curl --fail --silent http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer dummy-local-vllm' \
  -d '{
    "model": "gemma4-31b-nvfp4",
    "temperature": 0,
    "max_tokens": 64,
    "messages": [
      {"role": "system", "content": "Return JSON matching the schema."},
      {"role": "user", "content": "Report status ok."}
    ],
    "response_format": {
      "type": "json_schema",
      "json_schema": {
        "name": "HealthResult",
        "strict": true,
        "schema": {
          "type": "object",
          "properties": {"status": {"type": "string"}},
          "required": ["status"],
          "additionalProperties": false
        }
      }
    }
  }'
```

能力报告必须区分：

- `native_json_schema=true`：服务端接受并约束 `response_format=json_schema`；
- `json_object_only=true`：只支持 JSON object mode；
- `prompt_json_only=true`：只能靠 prompt 约束，再由本地 Pydantic 验证；
- `unusable`：无法稳定返回可解析结构化结果。

当前 `LLMClient` 无条件为带 schema 的请求发送 `response_format=json_schema`。M0 必须根据 capability profile 选择请求策略，不能因本地服务不支持该字段就假装模型不可用，也不能去掉本地 schema 验证。

2026-07-17 的当前 MTP 实例结果为：`native_json_schema=true`。普通 prompt-only JSON 返回了带 Markdown fence 的 JSON，而 native JSON Schema 返回裸、合法且满足 schema 的 JSON。因此当前 profile 优先使用 native JSON Schema；prompt-only 仍只作为经过本地提取和 Pydantic 验证的降级路径。

Code2Paper L1 追加结果：真实 `CoverageCriticProposal` 在 512 tokens、60 秒 timeout、单次 attempt 下成功，返回 `proceed_to_analysis`，Pydantic 解析通过。合成 schema 的 whitespace saturation 作为单独 regression 保留；它不能被一个成功 schema 掩盖，也不能被错误表述为整个服务不支持 JSON Schema。

### 6.4 结构化输出降级策略

支持顺序固定为：

1. native JSON schema；
2. JSON object mode + schema 文本 + 本地 Pydantic 验证；
3. prompt-only JSON + 本地提取单个 JSON object + Pydantic 验证；
4. 一次 repair prompt；
5. deterministic fallback 或 blocked。

降级不能接受缺字段、额外越权字段或类型错误。每次降级必须写入 call trace：`requested_mode`、`effective_mode`、`parse_attempts`、`schema_errors` 和最终状态。

当前 MTP profile 已验证第 1 级可用。保留后续降级不是为了当前服务，而是防止 vLLM 升级、启动参数变化或更换 provider 后失去结构化输出兼容性。

### 6.5 模型调用留痕

每个真实调用至少记录：

- provider、base URL 的脱敏 origin、model ID；
- inference mode（当前为 `mtp`）、TP size、speculative token count、draft TP size；
- MTP assistant identifier/path 和可获得的 config digest；
- capability profile digest；
- prompt template ID/version/hash；
- input artifact digests；
- temperature、max tokens、timeout、retry policy；
- response hash，不默认存储完整敏感上下文；
- latency、cache hit、attempt count、blocked reason；
- parsed proposal；
- safety-merged decision；
- schema validation errors。

run manifest 必须能够回答“这次正文由哪个模型、哪个 prompt、基于哪一版 evidence 生成”。

### 6.6 Live test 分层

#### L0：服务 smoke

- `/health` 通过；
- `/v1/models` 可读；
- 当前模型 ID 和 max context 与 profile 一致；
- process/service manifest 证明 `method=mtp`、TP=2、speculative tokens=1；
- 普通 completion 可用；
- native strict JSON Schema 可用；
- 不运行 Code2Paper pipeline。

#### L1：单节点 contract

分别调用：

- coverage critic；
- evidence sufficiency；
- analysis repair router；
- authoring planner；
- revision router；
- figure planner；
- P0 后新增的 final claim extractor/semantic verifier。

每个节点至少测试正常 proposal、越权 proposal、格式错误三种输入。

#### L2：toy 端到端

使用 `tests/fixtures/toy_train_project` 和匹配 author markers。目标是快速验证 success 路径，运行时间应远低于真实项目。

#### L3：FastGS sentinel

使用：

```text
datasets/FastGS/FastGS - Training 3D Gaussian Splatting in 100 Seconds
datasets/FastGS/FastGS - Training 3D Gaussian Splatting in 100 Seconds.yaml
```

目标不是强行 success，而是：

- 支持的 claim 被正确写入；
- unsupported/contradicted claim 不进入最终正文；
- partial claim 只保留 supported fragment 和 required qualifier；
- C1/C5 类问题在 authoring 前或 text validation 后被修复/阻塞；
- blocked 时给出具体 claim、缺失 evidence 和建议 repair target；
- 不在 final invariant 才第一次发现早已知晓的泄漏。

#### L4：多项目 shadow

至少覆盖 FastGS、CTiV-LM、MOS、Spatial-SSRL、WANDERLAND 中三个可运行项目，外加 toy fixture。每个真实项目先做只读 smoke，再进入完整运行。

#### L5：稳定性和对抗

同一模型、同一 snapshot、cache disabled，至少运行三次。比较：

- route 差异；
- proposal 差异；
- final supported claim 集；
- block 原因；
- semantic precision；
- 图节点/边集合；
- artifact digest 中哪些允许变化。

文风可以变化，可信度判定和 evidence lineage 不应随机变化。

### 6.7 Live test 标记和默认行为

新增 `pytest` marker：

```ini
live_llm = requires an explicitly configured local/remote model service
slow = long-running integration or benchmark test
```

默认 `pytest` 不自动访问本地服务。真实测试必须显式执行，例如：

```bash
CODE2PAPER_RUN_LIVE_LLM=1 python3 -m pytest -m live_llm -q
```

live test 若未配置服务应 skip，并给出缺失条件；若明确设置 `CODE2PAPER_RUN_LIVE_LLM=1` 后服务不可用，应 fail，不能静默 skip。

## 7. M0：恢复可发布、可实测基线

### 7.1 阶段目标

M0 不改变科研 claim 的通过标准。它解决测试 collection、安装、CLI、预算和本地模型协议，使后续变化有可靠基线。

进入条件：最终设计已经冻结为当前上位文档；当前 scoped worktree 状态和测试失败已记录。

本阶段不做：不重写 authoring、evidence 或 figure trust algorithm，不以 M0 为由放宽现有 invariant。

### 7.2 M0-01：冻结当前基线

工作内容：

1. 记录当前 Git commit、dirty 状态和 Python 版本；
2. 记录 `langgraph==1.2.8`、`langchain-core==1.4.9` 的本地验证事实；
3. 将 T007 输出复制或引用为只读 baseline，不修改原始 JSON；
4. 生成 baseline index，包含每个关键 artifact 的 path、digest 和关键状态；
5. 保存当前 agentic 88-test 命令和结果；
6. 保存全量 collection 失败信息。
7. 生成 tracked/untracked/ignored inventory，区分产品源码、测试、生成物、数据集和 nested repositories；
8. 以独立 commit 建立 `.gitignore` 和 Git hygiene 基线；
9. 确认 M0 实现分支从 `agentic-plan-v1` 或等价规划基线创建。

建议输出：

```text
tests/baselines/agentic/m0_current_baseline.json
tests/baselines/agentic/t007_fastgs_index.json
```

baseline 文件不得包含 API key、完整模型敏感 prompt 或不必要的绝对用户目录信息。

### 7.3 M0-02：修复测试 collection

主要代码落点：

- `src/code2paper/llm/providers.py`；
- `src/code2paper/cli/run.py`；
- `tests/test_main_cli.py`；
- 与 figure preset 相关的 CLI tests。

执行要求：

- 统一 `DEFAULT_FIGURE_IMAGE_MODEL` 的定义与导入；
- 默认值只能定义一次，其他模块显式导入；
- 增加 default/preset/explicit override 的测试；
- 先运行 `python3 -m pytest --collect-only -q`，再运行全量测试；
- 不顺手修改 figure gate 语义。

验收：全量 tests 能完成 collection；不存在 import-time error。

### 7.4 M0-03：补齐安装和 console scripts

修改 `pyproject.toml`：

- 增加 `agentic` optional dependency；
- 以本地确认版本建立 CI/lock 基线，再设置经过测试的发布区间；
- 增加 `code2paper-agentic-run`；
- 增加 `code2paper-agentic-benchmark`；
- live model adapter 如新增依赖，应保持可选，基础 deterministic 路径不强制安装 provider SDK。

目标示例：

```toml
[project.optional-dependencies]
agentic = [
  "langgraph>=1.2.8,<1.3",
  "langchain-core>=1.4.9,<1.5",
]

[project.scripts]
code2paper-agentic-run = "code2paper.cli.agentic_run:main"
code2paper-agentic-benchmark = "code2paper.cli.agentic_benchmark:main"
```

版本区间只能在真实安装测试后确认，不能仅因本地恰好安装某版本就假定整个区间兼容。

安装验收：

```bash
python3 -m pip install -e '.[agentic,dev]'
code2paper-agentic-run --help
code2paper-agentic-benchmark --help
```

### 7.5 M0-04：补齐预算和退出语义

修改：

- `src/code2paper/agentic/contracts.py`；
- `src/code2paper/cli/agentic_run.py`；
- `src/code2paper/agentic/runner.py`；
- `src/code2paper/agentic/graph_routes.py`；
- run manifest/summary/evaluation；
- 对应 CLI、state、routing tests。

新增 state/CLI：

- `--max-evidence-revision-rounds`；
- `--max-authoring-revision-rounds`；
- `--max-figure-revision-rounds`；
- `--max-semantic-verifier-calls`。

默认值在 M0 采用 0 或保守小值，防止功能尚未实现时出现无效循环。P0/P2 开启对应 route 后再调整默认值。

明确退出码：

- `0`：执行完成；可能是 success，也可能是用户未要求 fail-on-blocked 的解释性 block；
- `1`：设置 `--fail-on-blocked` 且 run blocked；
- `2`：CLI、依赖、配置或基础设施错误；
- 其他非零：未捕获内部错误，必须视为 bug。

CI 一律使用 `--fail-on-blocked`，交互式本地调试可不使用。

### 7.6 M0-05：Gemma 4 capability adapter

修改：

- `src/code2paper/llm/providers.py`；
- `src/code2paper/llm/client.py`；
- `src/code2paper/llm/call_logger.py`；
- `src/code2paper/agentic/llm_decision_provider.py`；
- 新增 `src/code2paper/llm/capabilities.py`；
- 新增 unit/live tests。

实现内容：

1. base URL 规范化继续支持 `/v1` 和 `/chat/completions`；
2. capability profile 可以通过探测生成，也可以由用户显式指定；
3. schema request 根据 capability 选择 native/json_object/prompt_only；
4. 所有模式最终都经过同一 Pydantic schema；
5. 记录 response mode、parse error 和 repair attempt；
6. API key presence 检查支持 loopback dummy key，但不得对非 loopback 自动伪造 key；
7. endpoint 或 model ID 不写死为 Gemma 4；
8. 测试模拟 vLLM 支持/不支持 strict schema 的两种响应。
9. 审计 `code2paper.schemas` 与 `code2paper.core.schemas` 中重复的 `LLMConfig/LLMProvider`；新 agentic 路径使用一个权威定义，旧导入采用兼容 re-export 或等价收敛方式，避免两个 schema 漂移。
10. 引入 node-specific `max_output_tokens`：router/critic 使用小预算，authoring/claim extraction 使用独立预算；不再把全局 12000 直接用于所有 schema。
11. 记录 provider `finish_reason`/token usage；JSON 截断、空白填充到 cap 或超时只能执行一次有界 repair，随后 deterministic fallback/block。

安全要求：provider capability 只影响“怎样获得结构化 proposal”，不能改变 evidence policy 或 gate 结果。

### 7.7 M0-06：文档和最小真实运行

README 增加：

- deterministic agentic 命令；
- 本地 OpenAI-compatible/Gemma 4 命令；
- blocked 语义；
- artifact 入口；
- live tests 不默认执行的原因；
- secret 管理说明。

当前模块命令兼容形式：

```bash
PYTHONPATH=src python3 -m code2paper.cli.agentic_run \
  "tests/fixtures/toy_train_project" \
  --author "tests/fixtures/toy_train_project_author_markers.yaml" \
  --out-root /tmp/code2paper-m0-toy-gemma4 \
  --project-id toy_m0_gemma4 \
  --llm-provider openai \
  --llm-model gemma4-31b-nvfp4 \
  --max-retrieval-rounds 0 \
  --fail-on-blocked
```

console script 安装后改用 `code2paper-agentic-run`。

该命令使用 `--fail-on-blocked` 是为了让 CI 明确看到 pipeline block。M0 判断 live adapter 是否通过时，应读取 decision/call trace：只要 Gemma 4 真实调用、结构化校验和 safety merge 正常，旧 trust pipeline 的已知解释性 block 可以作为有效 M0 结果，但必须记录，不能误报为端到端 success。

### 7.8 M0 测试矩阵

必须执行：

```bash
python3 -m pytest --collect-only -q
python3 -m pytest tests/test_llm_runtime.py tests/test_agentic_llm_decision_provider.py -q
python3 -m pytest tests/test_agentic_run_cli.py tests/test_agentic_runner.py -q
python3 -m pytest tests/test_main_cli.py tests/test_run_cli.py -q
python3 -m pytest -q
CODE2PAPER_RUN_LIVE_LLM=1 python3 -m pytest -m live_llm -q
```

若全量测试包含历史上与本阶段无关的失败，必须逐个分类并建立明确基线；不能仅报告“多数通过”。collection 失败始终是 blocker。

### 7.9 M0 退出门槛

- 全量测试可收集；
- M0 新增测试全部通过；
- `pip install -e '.[agentic,dev]'` 成功；
- 两个 agentic console script 可运行；
- 五项预算进入 CLI/state/manifest/trace；
- Gemma 4 L0、L1 通过，toy L2 至少完成一次真实模型路径并产生可审计 proposal/merge trace；若 toy 因已知旧 trust gate block，必须准确分类，不能回退成 deterministic 后冒充 live pass；
- L0/L1 使用 `gemma4_mtp_vllm`，且 run/profile 证明实际连接的是 MTP-enabled TP=2 实例；
- capability profile 和 call trace 不包含 secret；
- deterministic path 不依赖 Gemma 4 服务；
- 当前 fixed/agentic 行为没有因 M0 被悄然放宽。
- 规划文档、M0 产品源码和测试均已进入 Git 跟踪；
- `outputs/`、checkpoint、cache、secret 和大型 live artifact 未进入 Git；
- M0 validation report 绑定 clean commit；
- 已创建 annotated `agentic-m0-baseline-v1` tag。

若 Gemma 服务暂时不可用，M0 工程功能可进入 validation，但阶段不能 complete，必须保留 live test 待完成项。

## 8. P0：正文语义证据闭环

### 8.1 阶段目标

P0 解决最紧急的科研可信度问题：正文中的 claim 是否真的由相关代码支持。它必须让 unsupported claim 在写作前消失，或在最终文本验证后进入有预算 repair，而不是依赖最终 invariant 才发现伪 trace。

进入条件：M0 complete；全量测试可收集；Gemma 4 L1 contract 已通过；T007 baseline digests 已冻结。

本阶段不做：不重写 evidence snapshot 身份，不引入 durable checkpoint，不优先优化方法图外观。

### 8.2 P0-01：定义正文 contract

新增/扩展 Pydantic schema：

- `AuthoringInputProjection`；
- `ProjectedClaim`；
- `ForbiddenClaim`；
- `FinalTextUnit`；
- `FinalAtomicClaim`；
- `TextClaimEvidenceVerdict`；
- `TextEvidenceValidationReport`；
- `TextTraceEntry`。

建议代码落点：

- `src/code2paper/agentic/authoring_projection.py`；
- `src/code2paper/agentic/final_text_claims.py`；
- `src/code2paper/agentic/text_evidence_validator.py`；
- `src/code2paper/agentic/text_trace_builder.py`；
- `src/code2paper/agentic/contracts.py` 或独立 `trust_contracts.py`。

每条可写 claim 必须包含：claim text、支持状态、direct evidence IDs、supported fragment、required qualifiers、allowed wording boundary 和输入 digest。

### 8.3 P0-02：全字段 Authoring Input Projection

projection 是 writer 唯一可见的正向事实输入。构建时必须遍历并过滤：

- `MethodEvidence.claim_contracts`；
- `ClaimEvidenceMap`；
- `stage_packets[].claim_ids`；
- `stage_claim`、purpose、mechanism summary；
- outline/scaffold；
- author intent spine；
- equations、numeric facts、aliases、distinguishing points；
- grounding context；
- revision context；
- plan proposal context。

过滤规则：

- supported：保留，绑定 direct evidence；
- partial：只保留 supported fragment，附 required qualifiers；
- unsupported/contradicted/unverified：从所有正向字段删除；
- forbidden 区只保留 claim ID、reason 和 repair metadata，不保留可被模型直接复述的完整营销式表述；
- 任何无法识别来源的正向方法事实默认删除并报告。

输出：`agentic_authoring_input_projection.json`。

关键测试：对每个字符串字段递归扫描 excluded claim、同义改写关键词和 forbidden numeric/equation，不能只检查 claim ID 数组。

### 8.4 P0-03：Authoring plan hard gate

更新：

- `authoring_plan.py`；
- `authoring_plan_decisioning.py`；
- `authoring_context.py`；
- authoring planner graph node。

要求：

- section claim IDs 必须来自 projection；
- section evidence 必须等于或包含对应 claim direct evidence 的合法子集/并集；
- partial claim 的 plan entry 必须携带 qualifier template；
- plan 签名绑定 projection digest；
- 模型遗漏安全 claim 时，可由 deterministic fallback 补 section；
- 模型新增 projection 外 claim 时必须丢弃并留痕；
- 模型不得通过自由文本 section purpose 重新引入 forbidden claim。

### 8.5 P0-04：删除伪 trace fallback

修改 `src/code2paper/pipeline/stages/authoring.py`：

- 删除“找不到匹配时使用首个 supported claim”；
- 删除“无 evidence 时使用首个 known evidence”；
- 停止以段落位置为权威 claim binding；
- 旧 `method_claim_map.json` 标记 `legacy_scaffold`；
- scaffold 可以帮助生成，但不能进入 final invariant 的权威输入。

无 claim 匹配的段落有两类：

- 非事实衔接句：允许不绑定 evidence；
- 方法事实句：标记 unbound，进入 semantic validation/repair，不能自动补 ID。

### 8.6 P0-05：最终文本原子 claim 抽取

抽取必须发生在 Markdown/TeX 清洗、格式化和模型 revision 之后。输入使用最终交付候选文本的 exact digest。

处理流程：

1. 区分标题、普通句、公式、列表项、caption；
2. 识别非事实 discourse 句，不强行附 evidence；
3. 拆分包含并列、因果、条件和比较的复合句；
4. 保留原始 span、字符/行位置和规范化文本；
5. 生成候选 projection claim 和 evidence；
6. 模型抽取结果经过确定性完整性检查；
7. 抽取漏掉数字、公式或强因果词时必须失败。

输出：`agentic_final_text_claims.json`。

Gemma 4 可以辅助拆分和匹配，但 deterministic scanner 必须独立捕获：数字、百分比、复杂度、公式、`improves/outperforms/guarantees/ensures/causes` 等高风险表达。

### 8.7 P0-06：claim-to-code 语义验证

每条最终 atomic claim 使用三层验证：

第一层，确定性完整性：

- direct evidence ID 是否存在；
- evidence 是否来自允许 snapshot；
- 数值、配置值、公式 token 是否出现在证据或已验证 derived artifact；
- required qualifier 是否保留；
- claim 是否越过 allowed wording boundary；
- evidence 类型是否足以支持 claim 类型。

第二层，Gemma 4 语义 proposal：

- 只提供 claim、精确 evidence excerpt、必要上下文和严格 verdict schema；
- 要求分别给出 supported/unsupported fragment；
- 禁止模型调用仓库外知识；
- writer 与 verifier prompt、上下文和角色隔离；
- 高风险 claim 可做两次顺序反转或反证 prompt，但同一模型的两次结果不能称为独立 verifier。

第三层，确定性保守 merge：

- deterministic contradiction/缺失限定词优先；
- 模型 `supported` 不能覆盖 deterministic failure；
- 模型不确定、输出冲突或 schema error -> caveat/repair/block；
- partial 只授权 supported fragment；
- context evidence 不能替代 direct evidence。

输出：`agentic_text_evidence_validation.json`。

### 8.8 P0-07：后验 text trace 与 graph repair

只有验证通过的 atomic claim 才能写入 `agentic_text_claim_trace.json`。每条 trace 必须包含 final text span digest、claim verdict、direct evidence、validator report ref 和 projection ref。

新增 graph 节点：

```text
authoring
  -> final_text_claim_extractor
  -> text_evidence_validator
  -> text_trace_builder
  -> validation
```

新增 route：

- `text_trace_invalid -> authoring`；
- `claim_semantic_unsupported -> authoring`，若只是措辞越界；
- `claim_semantic_unsupported -> analysis`，若缺直接 evidence；
- `verifier_budget_exhausted -> blocked/review`；
- `passed -> quality validators`。

route 必须消耗 `max_authoring_revision_rounds` 或 `max_semantic_verifier_calls`，禁止无限循环。

### 8.9 P0-08：invariant、ledger、completion 迁移

修改：

- `invariant_audit.py`；
- `traceability_ledger.py`；
- `completion_report.py`；
- `readiness_report.py`；
- `evaluation_report.py`。

权威正文输入改为最终 text trace 和 validation report。检查：

- report status 为 passed；
- report input text digest 等于最终 text digest；
- 每个 factual unit 都有 supported/caveated verdict；
- trace evidence 与 verdict 中的 direct evidence 一致；
- legacy scaffold 不得独立满足 gate；
- completion 的 method text 只有在 text gate 通过时才 complete。

### 8.10 P0 测试矩阵

单元测试：

- projection 递归过滤所有正向字段；
- partial 只保留 supported fragment 和 qualifier；
- plan 自由文本不能泄漏 forbidden claim；
- 不再有首项 fallback；
- 最终文本复合句拆分；
- discourse 句不误判为方法事实；
- 合法 ID + 无关 evidence 失败；
- 同义改写 unsupported claim 失败；
- 强化因果/性能表述失败；
- numeric/equation/qualifier 缺失失败；
- report digest 与最终文本不一致失败。

集成测试：

- deterministic toy success；
- fake model 正常/越权/格式错误；
- Gemma 4 toy success；
- Gemma 4 FastGS bounded run；
- authoring revision 预算耗尽后解释性 block。

对抗 fixture 至少新增：

```text
tests/fixtures/adversarial_text/unrelated_legal_evidence.json
tests/fixtures/adversarial_text/paraphrased_unsupported.json
tests/fixtures/adversarial_text/stronger_causal_claim.json
tests/fixtures/adversarial_text/missing_qualifier.json
tests/fixtures/adversarial_text/postprocess_injected_claim.json
```

### 8.11 P0 Gemma 4 验收

推荐 FastGS 命令形态：

```bash
code2paper-agentic-run \
  "datasets/FastGS/FastGS - Training 3D Gaussian Splatting in 100 Seconds" \
  --author "datasets/FastGS/FastGS - Training 3D Gaussian Splatting in 100 Seconds.yaml" \
  --out-root /tmp/code2paper-p0-fastgs-gemma4 \
  --project-id FastGS_P0_Gemma4 \
  --llm-provider openai \
  --llm-model gemma4-31b-nvfp4 \
  --max-retrieval-rounds 1 \
  --max-evidence-revision-rounds 1 \
  --max-authoring-revision-rounds 2 \
  --max-semantic-verifier-calls 64 \
  --fail-on-blocked
```

若 `--fail-on-blocked` 返回 1，不自动视为阶段失败。读取 artifact 判断 block 是否正确。以下才是失败：

- unsupported claim 出现在最终正文但系统标 success；
- 合法但不相关 evidence 被接受；
- C1/C5 仅靠 hard-coded 名单消失，其他同类 claim 仍泄漏；
- 最终 trace 与最终文本 digest 不一致；
- block 没有具体 claim、evidence gap 和 repair 建议。

### 8.12 P0 退出门槛

- 全字段 projection 成为 writer 唯一正向事实输入；
- 首项 claim/evidence fallback 已删除；
- 最终 claim 从最终文本反向抽取；
- semantic validator 对每个 factual atomic claim 给出 verdict；
- invariant/ledger 不再消费 legacy scaffold 作为权威 trace；
- 所有 P0 对抗测试通过；
- Gemma 4 toy 通过；
- FastGS success 或正确 block，且无伪 trace；
- unsupported/paraphrased unsupported leakage 为 0；
- 新 gate 无法通过 feature flag 被正式 agentic run 绕过。

## 9. P1：Evidence V2、atomic claim 与 freshness

### 9.1 阶段目标

P1 确保“证据”不仅指向一个路径或摘要，而是指向可复验的仓库快照、文件和精确 excerpt。任何源码或上游 artifact 变化都必须使旧验证自动失效。

进入条件：P0 complete；AuthoringProjection、FinalAtomicClaim 和 TextEvidenceValidationReport schema 已稳定。

本阶段不做：不改变已通过 P0 校准的语义支持阈值，不以 schema migration 重新授权旧 claim。

### 9.2 P1-01：RepoSnapshot

新增 `repo_snapshot.json`，字段至少包含：

- `snapshot_id`；
- project root 的规范化身份；
- `project_tree_hash`；
- 可选 `git_commit`、branch、dirty flag；
- included/excluded path policy；
- symlink/submodule policy；
- hash algorithm；
- producer version；
- created time。

snapshot policy 必须排除输出目录、cache、`.git` objects 和无关大文件，但不能排除会影响方法行为的配置、shell、CUDA/C++ 源码和 submodule 工作树。

运行结束时可再次计算 tree hash。若运行中源码变化，final gate 必须报 `source_drift`，不能仅更新 manifest 为新 hash。

### 9.3 P1-02：EvidenceSpanV2

新增字段：

- snapshot/project tree identity；
- path、symbol、line start/end；
- exact excerpt；
- excerpt digest；
- file digest；
- source type、strength、extraction method；
- producer version；
- derived evidence lineage；
- 可选 runtime trace ref。

修正 `analysis/ingestion.py` 等所有入口：`excerpt_digest` 必须计算精确 excerpt，不得计算 `content_summary`。增加 round-trip 测试：按 path/line 重新读取后 hash 必须相同。

### 9.4 P1-03：AtomicClaimV2

将 P0 的文本 claim contract 与 evidence 阶段 claim contract 对齐：

- subject/predicate/object；
- conditions/qualifiers；
- claim type 和 risk；
- direct/context evidence；
- supported/unsupported fragment；
- wording boundary；
- verifier input digest；
- verdict rationale。

兼容层把旧 C1/C2 contract 转成 V2，但转换结果初始为 `unverified`，不能因旧 status 自动获得 V2 supported。

### 9.5 P1-04：Artifact freshness graph

新增 `CheckArtifactFreshnessTool` 和依赖图。每个 artifact 的 freshness 由以下条件决定：

```text
schema supported
AND content digest matches
AND producer version accepted
AND all input digests still current
AND repo snapshot still current
```

一旦 evidence snapshot 更新：

- semantic claim verification stale；
- authoring projection stale；
- plan/draft/text trace stale；
- figure scene/render audit stale；
- final package stale。

系统必须重跑相应节点，不能原地把新 digest 写进旧报告。

### 9.6 P1-05：freeze 和版本迁移

evidence freeze 后不可原地编辑。修复流程产生：

```text
evidence_snapshot_v1 -> repair -> evidence_snapshot_v2
```

新 snapshot 记录 parent、repair reason 和新增/删除 evidence。所有 claim verification 针对明确 snapshot version。

迁移期同时输出旧 evidence 文件和 V2 snapshot；旧文件只供 legacy composite tool 使用。P1 退出后，新 trust gate 只认 V2。

### 9.7 P1 测试矩阵

- exact excerpt digest round-trip；
- 修改 excerpt 内字符 -> stale；
- 修改同文件 excerpt 外内容 -> file/tree drift 触发策略性 stale；
- 修改输出目录 -> 不影响 repo snapshot；
- dirty Git repo 身份正确；
- submodule/source symlink policy 测试；
- evidence v1 -> v2 后下游自动失效；
- 旧 report 文件仍存在但 digest 过期 -> gate failed；
- cache key 包含 snapshot 和 producer version；
- FastGS 大仓库 snapshot 性能和排除规则测试。

Gemma 4 freshness 实测：

1. 对 toy/FastGS 运行到 text validation；
2. 在测试副本中修改一个被引用 excerpt；
3. 使用相同 run ID 尝试继续；
4. 期望 `stale_artifact`，回到 intake/evidence；
5. 旧模型 response cache 不得被错误复用；
6. 恢复原文件后重新运行，生成新的 snapshot lineage。

### 9.8 P1 退出门槛

- 所有直接 evidence 可按 snapshot/path/line/excerpt digest 重建；
- exact excerpt hash 路径统一；
- AtomicClaimV2 区分 direct/context evidence；
- 所有 trust report 绑定输入 digest；
- evidence 更新后旧报告自动 stale；
- 运行中源码漂移阻止 finalize；
- Gemma 4 stale/resume 实测通过；
- legacy V1 evidence 不再能独立满足正式 agentic gate。

## 10. P2：方法图证据与真实渲染闭环

### 10.1 阶段目标

P2 将方法图从“有 evidence ID 的计划”升级为“每个可见元素和每条关系均有直接证据、实际 asset 与计划一致”。

进入条件：P1 complete；EvidenceSpanV2、AtomicClaimV2 和 freshness 已成为正式 trust input。

本阶段不做：不把生成式图像质量作为可信度通过条件，不以节点顺序替代关系证据。

### 10.2 P2-01：EvidenceRelationV2

从代码分析结果中显式建立关系：

- data flow；
- call/control flow；
- configuration activates；
- consumes/produces；
- wraps/delegates；
- transforms；
- conditional branch；
- temporal stage order，仅在代码/脚本明确时成立。

每条 relation 包含 source/target entity、semantic statement、conditions、direct evidence 和 support status。

禁止：

- 因节点数组相邻就生成箭头；
- 因两个节点各自有证据就把证据并集用于边；
- 把作者意图描述当关系硬证据；
- 把 README pipeline 图当代码关系证据。

### 10.3 P2-02：FigureSceneGraph

新增：

- node；
- edge；
- annotation；
- group/container；
- omitted element；
- layout hint；
- evidence binding；
- visible text boundary。

Gemma 4 可以选择布局、分组和视觉层级，也可以从允许 wording 中选择短 label。safety merge 必须：

- 删除无 claim/relation 的元素；
- 恢复/强制 required qualifier；
- 禁止新增数值、公式、箭头；
- 将模型 label 与 claim semantic statement 做验证；
- 保留所有丢弃或改写记录。

输出：

- `agentic_figure_scene_graph.json`；
- `agentic_figure_relation_validation.json`；
- `agentic_figure_plan_decision_trace.json`。

### 10.4 P2-03：确定性结构化 renderer

优先实现 SVG：

- 每个 scene element 有稳定 `id` 和 `data-claim-id`/`data-relation-id`；
- text 节点不栅格化；
- edge endpoint 可解析；
- viewBox、字体 fallback、换行和箭头样式确定；
- scene digest 写入 SVG metadata；
- renderer 不添加任何 scene 外事实元素；
- PNG/PDF 由该 SVG 派生，并记录转换工具和输入 digest。

建议代码：

- `src/code2paper/rendering/scene_svg.py`；
- `src/code2paper/rendering/figure_manifest.py`；
- `src/code2paper/agentic/figure_scene.py`；
- `src/code2paper/agentic/figure_relation_validator.py`。

### 10.5 P2-04：PaperBanana 兼容

PaperBanana 只作为可选 stylist：

- 输入是锁定的 scene contract；
- 不能新增/删除/改写事实元素；
- 生成结果必须经过 post-render audit；
- 纯 raster 无法可靠验证时，不得替代结构化 SVG 作为唯一可信交付；
- stylist 失败时可回退 deterministic SVG，但必须在 manifest 记录。

在 P2 初期，不以美观度阻塞 deterministic SVG 的可信交付。

### 10.6 P2-05：Pre/Post render audits

拓扑调整：

```text
figure_scene_planner
  -> figure_relation_validator
  -> pre_render_invariant_audit
  -> structured_renderer
  -> post_render_element_audit
  -> final_invariant_audit
```

pre-render 检查 scene contract；post-render 检查真实 asset：

- scene element 数量；
- element IDs；
- visible labels；
- edge source/target；
- annotation/公式/数值；
- 必需元素缺失；
- scene 外元素；
- asset digest 与 render manifest。

输出：

- `agentic_pre_render_audit.json`；
- `agentic_post_render_audit.json`；
- `rendering_manifest.json`；
- `final/figures/method_overview.svg`；
- 可选 PNG/PDF 派生物。

### 10.7 P2 测试矩阵

- 无 direct relation evidence 不生成 supported edge；
- 两节点 evidence 并集不能支撑边；
- 模型改写节点 label 为新机制时被拒绝；
- 模型增加箭头、公式、数字时被拒绝；
- SVG 删除元素 -> post audit fail；
- SVG 增加标签/箭头 -> post audit fail；
- edge endpoint 改变 -> post audit fail；
- scene digest 与 SVG metadata 不一致 -> stale/fail；
- completion 没有真实 asset -> incomplete；
- deterministic SVG 两次输入相同 -> digest 相同；
- PaperBanana drift -> repair 或 fallback，不得 success。

Gemma 4 实测至少包括：toy scene、FastGS scene 和一个故意诱导模型绘制无证据因果箭头的 adversarial scene prompt。

### 10.8 P2 退出门槛

- `zip(nodes, nodes[1:])` 不再自动产生 supported edge；
- 每条可见边有 direct EvidenceRelationV2；
- agentic rendering 生成真实 SVG asset；
- pre-render 和 post-render audit 均为 hard gate；
- completion 要求 asset + manifest + passed post audit；
- Gemma 4 只能影响布局/合法 wording，不能突破 scene contract；
- 图形 element semantic precision 和 direct edge evidence rate 为 100%；
- rendered element drift 为 0。

## 11. P3：LangChain 工具细化、typed state 与 checkpoint

### 11.1 阶段目标

在 trust contract 稳定后，P3 扩大 Agent 的可决策空间：细粒度工具、typed state、幂等缓存、持久 checkpoint 和安全 resume。

进入条件：P0-P2 complete；正文、证据和图形的 V2 artifact schema 已冻结版本。

本阶段不做：不改变 validator 的支持结论，不让 dynamic tool selection 直接获得文件系统或 finalize 权限。

### 11.2 P3-01：细粒度 LangChain tools

优先抽取：

- `BuildAuthoringProjectionTool`；
- `ExtractFinalTextClaimsTool`；
- `ValidateClaimAgainstEvidenceTool`；
- `BuildTextTraceTool`；
- `CheckArtifactFreshnessTool`；
- `BuildEvidenceRelationTool`；
- `ValidateFigureRelationTool`；
- `RenderStructuredFigureTool`；
- `ValidateRenderedFigureTool`。

随后抽取检索工具：

- `BuildRetrievalPlanTool`；
- `SearchCodeTool`；
- `BuildSymbolIndexTool`；
- `ReadEvidenceSpanTool`；
- `AssessCoverageTool`；
- `FreezeEvidenceSnapshotTool`。

每个 tool spec 必须声明 input/output Pydantic schema、artifact requirements、evidence policy、side effects、idempotency key、timeout/cost class、hard failure 和 safe recovery。

legacy 9-stage wrapper 暂时保留，并在内部调用新工具；不能存在一条 wrapper 路径绕过 V2 gate。

### 11.3 P3-02：AgenticRunStateV2

从 path bag 迁移为 typed state：

```text
run identity
repo snapshot ref
intent ref
budgets
artifact refs
phase statuses
pending gaps
decisions
loop counters
model profile ref
checkpoint metadata
```

要求：

- graph 使用 typed schema，而不是 `StateGraph(dict)`；
- artifact map、decisions、issues、counters 定义 reducer；
- 节点输入只接受需要的 state slice；
- state migration 明确 V1 -> V2；
- extra fields 仍 forbid，防止模型/旧 checkpoint 注入未知状态。

### 11.4 P3-03：Checkpoint 和 resume

实现两级 backend：

- memory：单元/快速集成测试；
- SQLite 或其他本地 durable backend：真实运行。

具体 checkpointer 包和 API 要以当前 `langgraph==1.2.8` 的验证结果为准；若使用额外 `langgraph-checkpoint-sqlite`，加入 agentic optional dependency 并锁定兼容范围。

resume identity：

```text
run_id + repo_snapshot_id + graph_contract_version
```

恢复时必须：

1. 验证 checkpoint schema/version；
2. 重新检查 repo snapshot；
3. 重新检查所有 artifact digest；
4. 重新执行待进入 gate 的 freshness；
5. 保留原 loop counters 和预算消耗；
6. 不重复执行已成功且 cache key 相同的幂等工具；
7. 不复用失败或输入已变化的模型 response。

### 11.5 P3-04：受限 tool selection

模型只看到 readiness context 允许的工具。例如：

- evidence 未 freeze：允许 search/read/analyze，不允许 author/render；
- text semantic fail：允许 rewrite/request evidence，不允许 finalize；
- figure relation fail：允许 relation repair/omit edge，不允许 renderer；
- stale artifact：允许回到 producer，不允许仅重写 digest。

tool selection 仍是 proposal，最终由 deterministic policy 检查 precondition、预算和 evidence policy。

### 11.6 P3-05：缓存和幂等

cache key 至少包含：

- tool/producer version；
- input artifact digests；
- repo snapshot；
- model/prompt/capability profile（若调用模型）；
- relevant configuration；
- schema version。

写操作采用临时文件 + 原子替换，失败不得留下看似完整的 artifact。多个分支不能写同一路径而无版本区分。

### 11.7 P3 测试矩阵

- typed state 拒绝未知字段；
- reducers 不丢 decision/artifact；
- checkpoint 在 evidence 后中断并恢复；
- authoring 后中断并恢复；
- rendering 后中断并恢复；
- resume 后最终 digest 与 uninterrupted run 一致；
- 源码变化后 resume 被 freshness 拒绝；
- graph contract 升级后旧 checkpoint 明确迁移或拒绝；
- 模型请求越权 tool 被 policy 拒绝；
- cache hit 不重复调用 Gemma 4；
- cache disabled 的重复 live run 仍保持 trust verdict 稳定；
- 预算在 checkpoint 后不重置。

### 11.8 P3 Gemma 4 实测

执行一次 FastGS bounded run，在以下位置注入可控中断：

1. evidence freeze 后；
2. final text validation 后；
3. structured render 后。

每次使用同一 run ID 恢复，记录：

- 跳过的已完成节点；
- 重新执行的 freshness gate；
- 模型调用次数变化；
- artifact digest；
- loop counters；
- 最终 success/block 是否与 uninterrupted control 一致。

### 11.9 P3 退出门槛

- 关键 trust 能力已成为结构化 LangChain tools；
- graph 使用 typed state 和 reducers；
- durable checkpoint/resume 可用；
- resume 不绕过 freshness/gate；
- tool selection 受 readiness/evidence policy 约束；
- legacy composite tools 不能绕过 V2 trust plane；
- Gemma 4 中断恢复实测与 uninterrupted control 等价；
- 模型调用、缓存和预算均可审计。

### 11.10 2026-07-17 实施状态

已落地：9 个 P0-P2 trust-plane `StructuredTool` 及完整工具契约、`AgenticRunStateV2`
reducers、V1→V2 migration、memory/SQLite checkpointer、CLI run identity/resume、恢复前
repo/artifact freshness fail-closed 校验、受限 tool proposal policy、原子写入和幂等 cache。
全量测试当前为 `385 passed, 2 skipped, 6 subtests passed`。

FastGS 冻结快照（1613 files）已完成 evidence freeze、final text validation、structured render
三处 SQLite 中断恢复 replay；三次恢复均跳过已完成节点、重新通过 freshness、保留预算/loop
counters，并与 uninterrupted control 得到相同最终 digest。报告：
`tests/baselines/agentic/p3_checkpoint_validation_report.json`。

随后通过获批的宿主 loopback 访问完成 fresh Gemma 4 验收：`/health=200`，served model 为
`gemma4-31b-nvfp4`，vLLM 进程和 MTP config 均现场可见。FastGS control 产生 1 次真实网络
语义验证调用；evidence、final text validation、structured render 三处 SQLite 中断恢复的最终
digest 均为 `sha256:3554a640...eafd6`，freshness 全部通过，已完成节点均未重跑，预算和 loop
counters 与 control 一致。final text gate 之后的两次恢复均新增 0 次模型调用。禁用 cache 后
连续 3 次真实调用都得到 `passed / supported / E1` 的相同 trust signature。完整模型 trace、
token usage、cache hit 和 MTP preflight 位于
`tests/baselines/agentic/p3_gemma4_checkpoint_validation_report.json`。P3 退出门槛据此通过。

## 12. P4：Benchmark、cutover 与 legacy 降级

### 12.1 阶段目标

P4 不再增加核心架构，而是证明 agentic route 在多项目、多次真实模型运行中提高或至少不降低证据语义精度，并据此决定默认路线。

进入条件：P3 complete；checkpoint、指标和各阶段 hard gate 已稳定；至少一个真实项目已完成 V2 success 或解释性 block。

本阶段不做：不为提高 benchmark 完成率修改 gold label 或降低 gate，不根据单次最好结果切换默认路线。

### 12.2 P4-01：Gold/Adversarial benchmark set

建立两类标注：

第一类，人工 gold：

- 可支持 atomic claims；
- 必需 qualifiers；
- direct evidence spans；
- 允许/禁止的图关系；
- 应成功或应 block 的关键理由。

第二类，对抗 mutation：

- 合法 evidence ID 错配；
- unsupported 同义改写；
- 相关性夸大；
- 因果强化；
- 数值/公式注入；
- figure edge 伪证据；
- post-render element drift；
- source/artifact stale。

至少覆盖 toy + 3 个真实项目；FastGS 必须包含。

还要为至少一个真实仓库构造两份互斥但合法的 author intent，例如“一份强调训练加速机制，一份强调表示/渲染流程”。两次运行应改变 retrieval priority、section ordering 和 figure emphasis，但不能改变相同代码事实的 support verdict，也不能为迎合意图制造新 claim。

### 12.3 P4-02：Variant 设计

最少比较：

- `fixed_legacy`：当前固定路线；
- `agentic_deterministic`：LangGraph + 无模型 proposal；
- `agentic_gemma4_mtp`：LangGraph + 当前 MTP-enabled Gemma 4 proposal/writer/verifier；
- 可选 `agentic_gemma4_mtp_no_revision`：消融 repair loops；
- 可选 `agentic_gemma4_mtp_no_intent`：消融 author intent priority，但保留 trust plane；
- 可选 `agentic_gemma4_no_mtp_perf_control`：仅用于受控性能对照，不参与可信度策略排名。

所有 variant 使用同一 repo snapshot、author input、evidence/validator policy 和 gold set。不能给 agentic variant 更宽松 gate。

### 12.4 P4-03：指标升级

现有 benchmark report 增加：

- atomic claim semantic precision/recall；
- unsupported leakage rate；
- paraphrased unsupported leakage rate；
- qualifier preservation rate；
- text trace exactness；
- figure element semantic precision；
- direct edge evidence rate；
- rendered element drift rate；
- source/artifact stale detection rate；
- correct-block/false-block rate；
- usable completion rate；
- retrieval/evidence/authoring/figure loop 数；
- 模型调用、latency、token 和 cache savings；
- checkpoint 恢复收益。
- author-intent adherence：已支持重点是否按 intent 进入检索、计划和图形；
- paired-intent sensitivity：同仓库不同 intent 是否产生预期组织差异，同时保持 support verdict 稳定。

完成率不能覆盖信任硬门槛。

### 12.5 P4-04：Gemma 4 重复运行

每个 `agentic_gemma4_mtp` case 至少运行三次，cache disabled。每次使用独立 out root 和 run ID，但固定：

- repo snapshot；
- intent/author input；
- model ID/capability profile；
- inference mode、MTP assistant、TP size 和 speculative tokens；
- prompt version；
- budgets；
- temperature；
- renderer。

聚合报告同时展示平均值和最差值。cutover 以最差可信度表现为准，不能只选最好一次。

### 12.6 P4-05：硬阈值

默认路线切换前至少满足：

- curated adversarial unsupported leakage = 0；
- paraphrased unsupported leakage = 0；
- high-risk claim false-supported = 0；
- qualifier preservation = 100%；
- text trace exactness = 100%；
- figure direct edge evidence = 100%；
- rendered element drift = 0；
- stale detection = 100%；
- 所有 success run 的 final invariant = passed；
- 所有 completion=complete 的真实 asset 和 lineage 完整；
- Gemma 4 三次重复中没有一次绕过 gate；
- false-block rate 达到团队设定的可用阈值，并逐 case 审核；
- agentic usable completion 不低于 legacy，或下降有明确的旧路线伪成功证据。

语义 recall、文风和运行时间是优化指标，不得抵消上述硬失败。

### 12.7 P4-06：Shadow、canary、default

切换顺序：

1. shadow：legacy 仍交付，agentic 后台生成对比，不对用户宣称完成；
2. opt-in：`--mode agentic` 显式使用；
3. canary：限定项目默认 agentic，legacy 可显式回退；
4. default：`code2paper run` 默认 agentic；
5. legacy downgrade：保留 `--mode legacy` 和 composite tools；
6. 连续多个版本稳定后才删除重复 orchestration。

回退到 legacy 时必须明确标注其 trust contract 较弱，不能让 legacy 产物冒充 V2 final invariant passed。

### 12.8 P4 退出门槛

- benchmark gold 和 adversarial set 可复现；
- fixed/deterministic/Gemma 4 variant 同条件比较；
- 三次重复运行完成；
- 所有硬可信度阈值达到；
- blocked 与 false-block 已人工抽查；
- README、CLI 和 migration guide 完整；
- shadow/canary 结果支持切换默认路线；
- legacy fallback 明确标注 contract version；
- 最终 Definition of Done 的 12 项全部满足。

### 12.9 2026-07-17 实施状态

P4 已从 clean tracked commit `9a98c17aaa4dd5134804ee057d7ff5d5d81e281e`
冻结并完整执行 25-run protocol，覆盖 5 个 case-intent 组合：每组 fixed legacy 1 次、
agentic deterministic 1 次、cache-disabled Gemma 4 MTP 3 次。protocol digest 为
`sha256:f662f28c...768b06c`；5 个 deterministic run 全部达到 `success` 与
`completion=complete`，13 个 curated mutation 仍为 13/13 检出。
正式 protocol 还固定了 capability profile 的绝对路径、文件摘要
`sha256:1dce0d3e1e07a6dda065309cdade03907f414187b97e3a401fb6038b737af3a7`
与运行时环境变量；每个 model-backed run 启动前都会重新校验 profile，
防止 fixed/Gemma 子矩阵在不同推理配置下被误合并。

模型路径不再把 Gemma 限制为 planner：`projection-constrained-llm-writer` 真实生成 Method
prose，最终 atomic claim validator 和 invariant gate 再做交付裁决。实现期间两类 live
失败推动了边界收紧：无 projection 匹配的模型段落被确定性剔除；被 semantic verifier
拒绝的 projection claim IDs 在下一轮 writer view 中撤销写作权限。原始 projection 和拒绝
verdict 仍保留用于审计，不能通过过滤改写历史。

正式结果：5 个 fixed legacy 运行均正常结束，但在当前 V2 gold 审计下 5/5 都是
`legacy_false_success_candidate`，没有 relation lineage、post-render audit 或 authoritative
V2 final invariant。15 个 agentic Gemma 运行中 11 个 `success + complete`，4 个因
`text_claim_authoring_revision_budget_exhausted` 安全阻断；11 个交付产物的最终 unsupported
rate 全为 0，4 个阻断没有产出可交付包，false completion 为 0。分组完成率为：toy 3/3，
FastGS training 2/3，FastGS rendering 2/3，Spatial-SSRL 3/3，MOS 1/3。15/15 均记录
真实 model writer provenance；总耗时 4185.191 秒，中位数 242.69 秒。

25-entry review queue 已包含 25/25 run records，缺失记录为 0，但 reviewer/reviewed_at 仍是
强制待填字段，named human review 为 0/25，不能由自动化结果代替。完整机器摘要保存在
`tests/baselines/agentic/p4_live_matrix_status.json`。因此机器矩阵已完成，但 P4 与总目标仍
不能宣告 complete：默认路线继续 `hold / legacy`，必须完成具名人工 review、shadow、
opt-in 和 canary 后，才可依据 cutover policy 决定是否转为 agentic default。

### 12.10 外部真实项目原文盲测

为避免只在仓库内置 fixture 上优化，P4 增加一组来自
`/data1/users/cuihengjia/code2paper` 的外部真实项目盲测。生成阶段只能读取代码与
author intent YAML；对应论文原文必须等生成结束后才由独立 evaluator 打开，只能用于
评估，不能进入 prompt、retrieval、evidence、validator 或 revision context。若
`input_manifest` 或 run summary 出现原文路径或原文摘要，reference isolation 直接失败。

首批选择三种互补项目：

| Case | 代码规模/侧重点 | author intent | 评估原文 |
|---|---|---|---|
| UniMMAD | 14 个 Python 文件；多模态异常检测、FCM、C-MoE | `paperyaml/UniMMAD.yaml` | `paper_final/114_UniMMAD.md` |
| CodeQuant | 16 个 Python 文件；旋转、聚类、置换、LUT kernel | `paperyaml2/CodeQuant - Unified Clustering and Quantization for Enhanced Outlier Smoothing in Low-Precision Mixture-of-Experts.yaml` | `paper_final/088_CodeQuant - Unified Clustering and Quantization for Enhanced Outlier Smoothing in Low-Precision Mixture-of-Experts.md` |
| Domain-Specific Pruning | 456 个 Python 文件；few-shot MoE expert pruning | `paperyaml4/Domain-Specific Pruning of Large Mixture-of-Experts Models with.yaml` | `paper_final/024_Domain-Specific Pruning of Large Mixture-of-Experts Models with.md` |

可复现的后置对照工具为
`code2paper-agentic-real-project-blind-eval`，case 与 intent-derived 概念词组冻结在
`tests/fixtures/real_project_blind_eval_cases.json`。概念覆盖只扫描正文而不扫描 Markdown
标题，降低“把 intent 复制成小节名”造成的虚高；它仍然只是透明的表面覆盖指标，不能替代
人工语义质量 review。运行方式：

```bash
PYTHONPATH=src python3 -m code2paper.cli.agentic_real_project_blind_eval \
  --manifest tests/fixtures/real_project_blind_eval_cases.json \
  --data-root /data1/users/cuihengjia/code2paper \
  --runs-root /tmp/code2paper-realset-a51518c \
  --output /tmp/code2paper-realset-a51518c/blind_eval_report.json
```

第一轮在 `4d8e4e5` 上发现 projection writer 会把内部“paper-facing stage named”
claim-contract 写入正文，并重复输出同一机制句，造成可复现 false-block。修复原则不是放宽
validator，而是在 writer 边界移除元 claim、按正文归一化去重，并在同文 claim 冲突时合并
所有 qualifier，防止无 qualifier 的弱副本覆盖严格约束。同一 Gemma toy 回归由 blocked
恢复为 `success + completion=complete + final invariant passed`。

随后在 clean generation commit `a51518cffbebf0c3811928a11d9ae129d536348a`
上重新执行三例 deterministic 盲测，结果如下：

| Case | Run 结果 | 生成正文/原文 intent 概念覆盖 | 最终文本 unsupported | 可信度结论 |
|---|---:|---:|---:|---|
| UniMMAD | success，completion=complete | 28.57% / 85.71% | 0% | text/figure/invariant/trace/package 全通过，但正文只展开 FCM 与 anomaly inference |
| CodeQuant | success，completion=complete | 100% / 100% | 0% | 五个 intent 概念全部出现；LUT claim 保留“当前代码证据不支持”限定，不作无条件事实 |
| Domain-Specific Pruning | success，completion=complete | 66.67% / 100% | 0% | trust 全通过；few-shot statistics 与 mixed-domain 展开仍不足 |

本轮 reference isolation 为 3/3 passed，可追溯交付为 3/3，假完成和最终 unsupported
leakage 均为 0。projection writer 修复后，三例正文唯一行比例均为 1.0，旧重复已消失。
它同时揭示了不能被可信度指标掩盖的质量差距：UniMMAD 仅覆盖 2/7 个冻结正文概念，
Domain-Specific Pruning 覆盖 4/6；原文分别覆盖 6/7 与 6/6。因此 trust-complete 不等于
reference-quality complete，Gemma authoring 与人工 review 仍需重点检查漏写而非只查幻觉。
因此 P4 必须分别报告：

1. **scientific trust**：陈述和图能否回溯到冻结代码证据，unsupported 是否零泄漏；
2. **intent/reference quality**：关键方法是否展开、组织是否接近作者意图、是否存在重复；
3. **usable completion**：同时通过前两类要求且完成人工审核的交付比例。

正式矩阵结束后，又在 commit `9a98c17` 和同一冻结 Gemma profile 上对三例执行模型盲测。
生成命令仅传入 `code_final/<project>` 与对应 paperyaml；三次生成全部结束后，独立 evaluator
才读取 `paper_final` 原文。reference isolation 3/3 passed，结果如下：

| Case | Gemma 结果 | 生成正文/原文 intent 概念覆盖 | 最终文本 unsupported | 交付结论 |
|---|---:|---:|---:|---|
| UniMMAD | blocked：direct evidence budget exhausted | 28.57% / 85.71% | 85.71% | fail-closed，不交付 |
| CodeQuant | success，completion=complete | 60% / 100% | 0% | text/figure/invariant/trace/package 全通过 |
| Domain-Specific Pruning | blocked：direct evidence budget exhausted | 0% / 100% | 100% | fail-closed，不交付 |

因此模型盲测的可追溯交付为 1/3，trust block 为 2/3，false completion 为 0。CodeQuant
交付稿覆盖 AOS rotation、adaptive clustering 和 permutation grouping，但未覆盖 router KL
与 LUT GEMM；两份 blocked candidate 只能用于定位 retrieval/evidence 缺口，不能作为论文
交付或质量成功计数。完整报告 digest 为 `sha256:ee851fa3...cde26f8`，机器摘要保存在
`tests/baselines/agentic/p4_real_project_blind_status.json`。下一步由具名 reviewer 对 1 个
success 与 2 个 block 分别检查语义质量、漏写和 false-block；原文仍不升级为代码证据。

### 12.11 真实项目 evidence repair 稳定身份回归（2026-07-18）

对 Domain-Specific Pruning 的 block 反查发现，bounded repair 已经检索到
`pruning/model_new.py`、`pruning/expert_selection.py` 和 mixed-domain selection，但第二次
evidence freeze 会重新分配 `C<number>`；analysis bridge 仍沿用旧 snippet/fallback 绑定，
导致 repair candidate 没有进入当前 mechanism 的 direct evidence。修复后 repair task 以
claim 文本与当前 mechanism 做保守语义匹配，`C<number>` 只作审计标签，不再作跨 freeze
身份；author claim 引用也被限制在 MethodEvidence 冻结 ID 集合，越界 ID 清空且保持
unsupported，禁止 dangling reference 阻塞或进入 prose。

同一真实项目、同一代码+intent、相同预算的无模型端到端回归位于
`/tmp/code2paper-domain-pruning-repair-deterministic-v2`：`success + complete`，final
invariant 0 个 blocking failure，5/5 final factual claims 通过，unsupported=0。run summary
digest 为 `sha256:326ed37a...832458`，text validation digest 为
`sha256:cf885de1...bb8e33`。全量测试更新为 `431 passed, 2 skipped, 6 subtests passed`。

随后使用宿主机 `gemma4-31b-nvfp4` 做 cache-independent live 复测，结果仍为
`text_claim_authoring_revision_budget_exhausted`，false completion=0。该次失败不是 repair
重绑定回归：模型 retrieval proposal 在 repair 前就没有把 `pruning/*.py` 纳入 raw evidence，
而选择了 `bench_serving.py`、`olmoe.py`、`mixtral.py` 等通用 MoE 文件；14 次 semantic
verifier 调用后，最终 6/6 candidate claims 被拒绝并安全阻断。run summary digest 为
`sha256:14dc44bc...ad70fd`，text validation digest 为 `sha256:d03f2b23...db7bb`。

因此下一项机器工程不是放宽 semantic gate，也不是增加 writer 次数，而是给 retrieval
增加不可被模型 proposal 覆盖的 author-intent lexical seed：诸如 `pruning/`、
`expert_selection.py`、`model_new.py` 这类与方法词和顶层目录同时匹配的候选必须进入 bounded
rescan；模型仍可排序和扩展，但不能删除 deterministic seed。完成该项并重新 live 复测前，
Domain-Specific Pruning 继续计为解释性 trust block，不计为可用完成。

该 retrieval 修复随后落地：rescan queue 对同一路径设定上限，并从 deterministic
symbol-index context 注入最多 20 个 path-diverse seeds，避免一个通用 symbol 因匹配所有 gap
而占满 40 项预算。用上一份失败 live context 重放时，queue 从 10 个 unique paths 提升到
22 个，并包含 `expert_selection.py`、`expert_selection_mix_domain.py` 和 `model_new.py`。
新的真实仓库离线端到端运行位于
`/tmp/code2paper-domain-pruning-diverse-retrieval-deterministic`：raw evidence 实际冻结上述
三个 pruning 文件，18 个 seed 对应 18 个 unique paths，`success + complete`，4/4 final
factual claims 通过且 unsupported=0。run summary digest 为
`sha256:2b9b23b2...2e7a8e`，text validation digest 为
`sha256:048dc012...63483`；全量测试为 `433 passed, 2 skipped, 6 subtests passed`。
Gemma 对新 retrieval freeze 的 cache-independent 复测仍需执行，在此之前不回写正式 P4
baseline，也不把旧 safe block 改计为成功。

### 12.12 真实项目 intent-to-code 语义闭环回归（2026-07-18）

在 diverse retrieval 已把三个 pruning 文件纳入 raw evidence 后，继续反查发现 analysis
mechanism 仍可能沿用首次 freeze 中的通用 SGLang runtime/scheduler span。此次修复在 bridge
边界加入保守的内容算子匹配：只有代码片段同时满足 mechanism 所需的高特异性签名，才允许
替换旧 evidence，例如 `data[:25]` 的有界采样、gating 与 expert-output L2 norm 的乘积、
MoE 前后表示的 cosine 差异、score 聚合与 top-k，以及 mixed-domain 的逐域归一化再聚合。
仅路径名或通用 MoE 词汇不能建立支持关系。相同匹配规则被复用到 AtomicClaimV2、authoring
projection 与 final text validator，避免三个边界对同一代码算子作出相互冲突的判断。

同时修复两类 intent 丢失：Unicode hyphen 和标点先统一后再做 stage 匹配，使 few-shot
motivation 对齐 Data sampling、mixed-domain pruning 对齐 Multi-domain extension；内部
`paper-facing stage named ...` claim-contract 只保留为结构 scaffold，不再作为 writer 正向事实。
全量回归为 `444 passed, 2 skipped, 6 subtests passed`，实现提交为
`03c3b62ed3c36d14ff2e208f6feb7f617c56b501`。

真实 Domain-Specific Pruning deterministic v6 位于
`/tmp/code2paper-domain-pruning-content-rebind-deterministic-v6`。它只读取代码与 author intent，
结果为 `success + complete`，final invariant 0 个 blocking failure；最终正文 7 个 factual
atomic claims 全部有 direct evidence，unsupported=0，text/figure/invariant/traceability 全通过。
最终正文覆盖 few-shot demonstration、top-M、gating × output L2 norm、`1-cosine`、token
aggregation 和 mixed-domain normalized score averaging。最终文本 digest 为
`sha256:86cdb9dbc8c1ea5cbd515aa58a7be300c3a1e5ce844edba8815848fb411c58bf`。

生成结束后才打开冻结原文做独立 blind comparison，reference isolation passed。透明表面指标
给出生成稿 5/6（83.33%）、原文 6/6（100%）；唯一自动 miss 为 `few_shot_statistics`，但生成稿
明确写有 “Collect a small number of demonstrations from the target domain(s).”。这是冻结 alias
未包含该措辞造成的表面匹配 false negative，本轮保留原始 5/6，禁止事后修改 fixture 抬分。
input manifest、生成稿和原文 digest 分别为
`sha256:ea1c4262...c8f5c`、`sha256:86cdb9db...58bf`、
`sha256:53621707...429a`。机器可读记录保存在
`docs/agentic_domain_pruning_real_project_eval_2026-07-18.json`。

旧 commit `05cfbc6` 的 Gemma live run 已经检索到上述 pruning 文件，但因 mechanism 仍绑定通用
runtime evidence，semantic verifier 拒绝全部 10 个最终 claims，并以
`text_claim_direct_evidence_missing_budget_exhausted` 安全阻断；这证明 gate 没有把错误绑定放行。
实现修复后再次检查 `127.0.0.1:8000/v1/models` 返回连接失败（HTTP 000），因此新 Gemma
cache-independent 复测保持 pending，不能用 deterministic 成功替代。正式冻结 P4 baseline
仍为 `9a98c17`，具名 human review 和 shadow → opt-in → canary 仍未完成，默认切换继续 hold。

### 12.13 真实项目 intent-matched code operator 回归（2026-07-18）

继续以 UniMMAD 为质量探针时发现，retrieval 已经冻结 `mymodels/cmoe.py`，analysis 也产生了
“Domain-specific decompression via C-MoE” mechanism，但 section title 与 mechanism 的匹配分数
为 0.3393，略低于旧阈值 0.34，导致该阶段没有绑定证据。此次修复加入保守的 distinctive
compound acronym 匹配；只有双方共享 `C-MoE` 这类复合缩写才提升匹配，通用 `MoE`、`CNN`、
`MLP` 不获得同样权限。

更重要的是，反查暴露了一个 evidence identity 错误：当 symbol 为常见 `forward` 时，旧 extractor
会用整个文件源码判定行为，却把结论绑定到一个局部 evidence span。现在 AST fallback 只读取证据
ID 所覆盖的精确行区间，并按 exact/nested symbol 过滤同文件无关 span；过滤后无证据则不产生行为。
在此基础上新增三类可泛化 code-operator detector：`groups=B*E` 的 batched group convolution、
`expert_base + experts + softmax + einsum` 的 base-expert composition，以及 `topk + softmax` 的
normalized top-k gate。语义 matcher 下沉至 core 层，由 evidence、projection 和 validator 共用，
避免 pipeline/agentic 环依赖和边界判定漂移。

operator submechanism 只能投影到语义匹配的 stage；高特异性 top-k、group convolution、MoE-in-MoE
还必须由 stage 显式请求相应概念，防止在 CodeQuant 或 Domain Pruning 中串入别的项目机制。partial
claim 若没有显式 qualifier 现在直接以 `partial_claim_missing_explicit_qualifier` 禁止，不再自动追加
含糊的通用 caveat。该规则在 UniMMAD 中正确剔除了代码证据不足的“high parameter efficiency and
fast inference”陈述。全量测试为 `455 passed, 2 skipped, 6 subtests passed`，实现提交为
`671bce1b12b6f214dd994a15e4ac4eed7f0f6058`。

三个当前实现上的 deterministic 运行均只读取代码和 author intent，结果均为 `success + complete`、
final invariant passed、最终 unsupported=0：UniMMAD 6/6 factual claims supported，CodeQuant 4/4，
Domain-Specific Pruning 7/7。随后才由独立 evaluator 打开原文，完整报告位于
`/tmp/code2paper-realset-final-operators/blind_eval_report.json`，digest 为
`sha256:a4ce1fcd7257df33ac0c6bd1a6d3413366f037f9a5e963e0219870db995d331a`，manifest digest 为
`sha256:e02eba1c005d41e7f4a045539980dd6325731bf7d57b723872e6603df18b79c7`；reference isolation、
traceable delivery 均为 3/3，三例正文唯一行比例均为 1.0。

| Case | 当前生成稿/原文冻结概念覆盖 | 相对旧 deterministic | 可信度结论 |
|---|---:|---:|---|
| UniMMAD | 5/7（71.43%）/ 6/7（85.71%） | 由 2/7 增至 5/7 | FCM、condition router、grouped filtering、MoE-in-MoE 与 anomaly inference 均有 direct evidence |
| CodeQuant | 5/5（100%）/ 5/5（100%） | 保持完整 | 4/4 final claims supported |
| Domain-Specific Pruning | 5/6（83.33%）/ 6/6（100%） | 保持 5/6 raw score | 7/7 final claims supported；few-shot 仍是冻结 alias false negative |

UniMMAD 未写 `general_to_specific` 的因果性“缓解干扰”叙事，是因为当前代码证据只能支持算子结构，
不能直接支持该效果解释；系统按可信度约束主动省略。`C-MoE` 已在 section title 中出现，正文指标
按冻结规则不扫描标题，因此不复制标题来抬高分数。机器可读记录为
`docs/agentic_real_project_operator_eval_2026-07-18.json`。本轮不改写正式 P4 冻结矩阵；宿主机
`127.0.0.1:8000` 仍不可达，post-fix Gemma cache-independent 复测、具名 review 和 rollout
序列继续 pending，默认路线保持 hold。

### 12.14 Cutover named-review 来源门禁（2026-07-18）

P4 完成度审计发现一个 rollout 授权边界缺口：`code2paper-agentic-benchmark` 允许通过
`--observations` 直接加载 `BenchmarkObservationV2`。旧 `decide_cutover()` 虽然要求 observation
provenance 中存在 `reviewer` 和 `reviewed_at`，却无法区分这些字段是由 digest-pinned
`BenchmarkRunReviewV2` 经真实 artifact 回读产生，还是由 observation JSON 自行声明。因而一个构造的
observations 文件配合完整 rollout 数字，理论上可能生成 `default_ready`；同样，旧 run CLI 会接受一个
手写的、字段表面完整的 `CutoverDecisionV2`。这违反“具名人工 review 必须绑定被审产物 digest，且
默认切换只能消费已验证 review”的 P4 要求。

修复提交 `7ad7535ce8f8fbeac2a61c95074b9d11e2714eb7` 将 cutover decision contract 升级为
`2.1`，并新增独立的 `NamedReviewEvidenceV2`。该 evidence 不能从 `RolloutEvidenceV2` JSON 自报：
只有 CLI 的 `--review` 路径在逐份完成 review schema 校验、run summary digest 回读、所有必需 artifact
digest 回读和 mutation trial digest 回读之后，才按实际 review 文件内容计算 SHA-256 列表并传入
decision。列表必须覆盖冻结 protocol 的全部 25 个唯一 run identity，digest 必须是唯一且合法的
SHA-256；否则固定失败码为 `digest_pinned_named_review_artifacts_not_validated`，状态保持
`hold / legacy`。

`--observations` 仍可用于报告和诊断，但不能授权 shadow 之后的切换。隐式默认路线只接受 schema 2.1、
`default_ready`、无失败且携带 validated review digests 的 decision；旧 2.0 decision 和缺少 review
evidence 的手写 decision 均 fail closed 到 legacy。显式 `--mode agentic` 仍作为用户主动 opt-in，
不等同于修改默认路线。定向 cutover/run CLI 测试为 24 passed，全量测试为
`459 passed, 2 skipped, 6 subtests passed`。机器记录保存在
`docs/agentic_cutover_review_gate_2026-07-18.json`。

正式 P4 基线和 review queue 不因本次 gate 修复发生计数变化：25-run matrix 仍冻结在 `9a98c17`，
具名 review 仍为 0/25，因此新 gate 的当前正确结果仍是 hold。它修复的是“将来 review 完成时如何
可信地签发切换决策”，不能替代实际人工审核、shadow、opt-in 或 canary。

### 12.15 具名人工 review workspace（2026-07-18）

12.14 收紧了 cutover 的 review 来源，但冻结 queue 仍只有一个包含 25 个嵌套 template 的大 JSON。
reviewer 若手工复制模板，容易遗漏 run identity，误改 summary/protocol/snapshot/model binding，或直到
最终 benchmark 聚合时才发现 mutation trial 与 claim inventory 漂移；这会让真正的 25-entry 人工
流程难以执行。此次新增 `code2paper-agentic-benchmark-review-workspace`，它不作任何语义裁决，只把
既有 queue 安全地变成可填写、可批量验证的工作区。

`materialize` 为每个 frozen protocol identity 生成一个 `reviews/*.json` 和一个 `contexts/*.md`。
review JSON 保留具名 reviewer 与时区 ISO-8601 占位符；context 列出 run summary、最终方法文本、方法
图、text validator、final invariant、package、code-grounded gold claims/relations 及其 digest，明确不把
论文原文放入 evidence context。目标目录非空时拒绝执行，避免覆盖已填写的人工判断。

`validate` 必须同时通过 queue digest、workspace manifest、protocol commit、exact identity coverage、
review schema 和以下不可变绑定：run summary、protocol spec、repo snapshot、model/profile、agentic
atomic claim inventory 与 validator verdict，以及 mutation artifact path/digest。占位符未填写返回
`pending_human_review`，篡改/缺失/重复/路径逃逸返回 `failed`；两者都不产生 observations。只有全部
review 通过真实 artifact extraction 和 protocol observation validation 后，才输出 observation，并可由
`code2paper-agentic-benchmark --review-workspace ... --review-queue ...` 一次性消费全部 review file，
继承 12.14 的 `NamedReviewEvidenceV2` cutover 门禁。

实现提交为 `da90c610447928925b3806a21e5c51454552fb27`。定向 review/cutover/run CLI 测试
34 passed，全量测试为 `469 passed, 2 skipped, 6 subtests passed`。冻结 queue 已在
`/tmp/code2paper-p4-review-workspace-9a98c17-v2` 真实物化为 25 个 review + 25 个 context；当前 validation
为 `pending_human_review`，0 validated、25 pending、0 invalid、`observations_emitted=false`，因此没有把
物化动作冒充人工评审完成。机器记录为 `docs/agentic_p4_review_workspace_2026-07-18.json`。

该工具消除了人工流程的机械阻力和绑定漂移风险，但不能填写 reviewer、不能判断语义质量，也不能把
0/25 改计为完成。正式 P4 baseline 仍为 `9a98c17`，默认路线继续 hold。

### 12.16 Figure human-review 空集门禁（2026-07-18）

在 12.15 的 workspace 上继续做 completion audit 时发现，`BenchmarkRunReviewV2.figures` 默认是空
列表，而旧 `evaluate_observation()` 对空 figure elements 使用 `empty=1.0`。因此一个实际已经渲染方法
图的成功 run，如果 reviewer 完全不填写图节点和边，仍可能得到
`figure_element_semantic_precision=1.0`、`direct_edge_evidence_rate=1.0` 和
`rendered_element_drift_rate=0.0`。这会把“没有审核图”误计为“图审核满分”，直接违背图节点/边分别
取证和 post-render 人工抽查的要求。

修复提交 `daaf1136917e96788b1b503fc8daea2e6035e0bb` 后，review queue 从 run summary 中读取
digest-pinned `figure_scene`，把每个可见 node、edge、annotation、group 物化为不可删减的
`FigureAdjudicationV2`。每项冻结 `element_id`、kind、label、scene element digest 和内部 relation ID；
reviewer 只能填写 gold 映射与语义判断。每个元素必须显式填写 `semantically_supported` 和
`rendered_drift`，每条 edge 还必须填写 `direct_relation_evidence`。workspace validator 和 observation
extractor 都重新比较 exact inventory，删除、增加、重复或改绑任一元素均 fail closed。

`BenchmarkObservationV2` 同时记录 expected figure/relation inventory count 与
`figure_inventory_reviewed`。对 completion-complete run，空或不完整 inventory 现在产生
`complete_without_full_figure_human_review_inventory`，对应 figure precision/edge evidence 强制为 0、
rendered drift 强制为 1；对没有生成图的 safe block 保持中性，不因不存在的产物制造假失败。边场景的
对抗测试证明，即使 source/target node 都已审核，edge 未显式裁决 direct relation evidence 仍不能通过。

冻结 `9a98c17` 的 25-run queue 已重建为
`/tmp/code2paper-p4-review-queue-9a98c17-figure-inventory.json`，并物化到
`/tmp/code2paper-p4-review-workspace-9a98c17-v3-figure-inventory`。20 个 agentic records 中，16 个成功
交付包含共 28 个 visible scene nodes，4 个 safe block 没有 figure asset；当前正式产物没有 scene edge，
但 edge gate 已由独立 relation fixture 覆盖。workspace validation 仍正确报告 0 validated、25 pending、
0 invalid、不输出 observations。定向测试 35 passed，全量测试为
`473 passed, 2 skipped, 6 subtests passed`。机器记录为
`docs/agentic_p4_figure_review_inventory_2026-07-18.json`。

旧 v2 workspace 的 queue 没有 figure inventory，现已标记 superseded，不能用于完成具名 review 或签发
cutover。正式 baseline run 本身未改变，named review 仍为 0/25，默认路线继续 hold。

### 12.17 Final atomic claim human-review 完整性门禁（2026-07-18）

继续审计单文件 `--review` 路径时发现，旧 observation extractor 只遍历 reviewer 实际提交的
`claims`。因此即使 workspace 模板完整，直接传入一个删掉部分 final atomic claims 的 review 文件，
被删除的最终方法句也不会进入 human semantic precision/recall；这会把“没有审核”误计成“不存在”。

修复提交 `d1f85f2c0f293b639f4758b96d7b568d74fc3815` 后，最终文本的三份权威 inventory——
`final_text_claims.atomic_claims`、`text_evidence_validation.verdicts` 和
`final_text_trace.entries`——都必须是带 atomic ID 的 object list，内部 ID 唯一且三者 ID 集合完全
相等。human review 必须逐项覆盖同一集合；claim text 必须与 final artifact 字节一致，review 中的
validator verdict 必须显式填写且等于冻结 validator verdict。删除、增加、重复、改名、改写或留空
任一项均 fail closed。completion-complete run 还必须具有全部三份权威 artifact，且至少包含一条 factual
claim，不能用空 inventory 绕过评审。

冻结 `9a98c17` 的 queue 已按 claim + figure 双重完整 inventory 重建为
`/tmp/code2paper-p4-review-queue-9a98c17-claim-figure-inventory.json`，并物化到
`/tmp/code2paper-p4-review-workspace-9a98c17-v4-claim-figure-inventory`。25 个 entries 中有 20 个
agentic records，合计 53 条 final atomic claims；16 个成功 agentic deliveries 仍包含 28 个 visible
figure elements。workspace validation 正确报告 0 validated、25 pending、0 invalid、
`observations_emitted=false`。定向测试 36 passed，全量测试为
`474 passed, 2 skipped, 6 subtests passed`。机器记录为
`docs/agentic_p4_claim_review_inventory_2026-07-18.json`。

旧 v3 figure-only workspace 没有被本次 claim artifact digest 重新验证，现仅作为历史审计证据；完成
具名评审和签发 cutover 必须使用 v4 claim + figure inventory。正式 baseline run 未改变，默认路线继续
hold。

### 12.18 Claim-to-code human semantic gate 与 review context 绑定（2026-07-18）

对 12.17 的人审聚合继续做反向审计时发现，旧 `atomic_claim_semantic_precision` 只要求 reviewer 把
final claim 映射到一个合法 gold claim ID；它没有要求 reviewer 独立确认 validator 所列
`direct_evidence_ids` 是否真的语义支持该句。因此“句子与 gold 语义接近、引用代码却无关”的结果仍可
被计为正确 positive。这与“每个最终 atomic claim 必须回到 direct code evidence”的总目标不一致。

实现提交 `069e1180cd021f4e43825108e13c3487442b834b` 增加逐 claim 的
`direct_evidence_support` 三态人审字段。每条 final claim 必须显式裁决；选择 true 时 validator artifact
必须确实包含 direct evidence IDs。benchmark 只有在 gold claim 语义映射和 direct-evidence 人审同时为
真时，才把该 positive 计入 semantic precision/recall。缺省字段、空 direct evidence 上的肯定裁决、
或人审否定均 fail closed/计为未命中，不能由 validator 自报 supported 代替人工代码证据判断。

同一提交还把 protocol 的 canonical gold digest、gold code evidence spans 和 frozen repo root 写入
review queue；workspace context 现在直接列出 evidence snapshot/index、final claims、final trace、
validator 和 gold spans。后续提交 `6610aaa6c1857dc929a0d52ff8c6c964ff3abf68` 为每个 context 增加摘要，
并把 context、template 和 immutable review binding 的校验移到 placeholder 判定之前。因此人工评审尚未
开始时，只要上下文或模板发生漂移，就立即返回 failed，而不是误报普通 pending。

冻结 `9a98c17` 的新 queue 为
`/tmp/code2paper-p4-review-queue-9a98c17-code-evidence-adjudication.json`，canonical gold digest 为
`sha256:c88d55e9ffdbd5f68772634ff672ffce8044446b9a855ba35676201d2f2913e9`；最终 workspace 为
`/tmp/code2paper-p4-review-workspace-9a98c17-v7-code-evidence-adjudication`。它保留 25 entries、20 个
agentic records、53 条 final atomic claims、28 个 visible figure elements，且 25/25 context digests
齐全。当前 53 个 direct-evidence decisions 和全部具名评审仍待人工填写，validation 为 0 validated、
25 pending、0 invalid、`observations_emitted=false`。定向测试 39 passed，全量测试为
`477 passed, 2 skipped, 6 subtests passed`。机器记录为
`docs/agentic_p4_code_evidence_adjudication_2026-07-18.json`。

旧 v4 claim + figure workspace 没有 direct-evidence 人审字段、gold digest 和 context digest，现仅保留为
历史审计证据；不能用于完成 named review 或授权 cutover。正式 baseline run 未改变，默认路线继续
hold。

### 12.19 Fixed legacy exact human-review inventory（2026-07-18）

对新 workspace 的 variant 对称性审计发现，旧 fixed legacy template 的 `claims=[]`、`figures=[]`；同时
旧 `LegacyV2AuditReport` 只记录 factual/supported/unsupported 数量，不保留逐句文本。以 toy 为例，旧
audit 报告 43 个 factual claims，但 reviewer 可以提交空列表或只选择有利句子。legacy 图虽然存在 SVG，
也完全没有人审 inventory。这样会使 fixed baseline 的 precision/recall 与 figure metrics 受到选择性遗漏
影响，不能作为 agentic 对照。

提交 `3841fdc73efa5f6d408362557651e4f39510e7e6` 后，final claim extractor 首先隐藏不渲染的 Markdown
HTML comments，同时保持原始字符和行偏移；旧 `c2p` 元数据不再被误计为论文 claim。legacy V2 audit
现在冻结每个可见 factual atomic claim 的 ID、原文、claim digest、validator verdict、direct evidence
IDs 和风险标记，并绑定 exact draft digest。它也绑定 SVG digest，将每个可见 `<text>` 作为 annotation、
每个带 `marker-end` 的 line/path/polyline 作为 edge。提交
`892d62170ec053c037059f1bce19f213c88fb748` 明确保持这种可见元素分类，避免把多行 SVG 文本错误合并
成虚构 scene node。

Queue 构建现在强制 legacy audit 存在并重新校验 run report、draft、SVG 和 inventory count；review
template 冻结 legacy audit path/digest 以及 exact claim/figure inventory。workspace 在 reviewer 占位符
阶段就检查 legacy/agentic 两类 inventory；observation extractor 再从 digest-pinned audit 重建 expected
集合，删除、增加、重复、改写、改 verdict 或改风险标记均失败。legacy `usable_completion` 也不能超过
audit 的 `v2_usable_completion`。

冻结五个 legacy runs 重建后共有 112 条可见 factual claims，均被当前 curated V2 validator 判为
unsupported；五张 SVG 共有 45 个可见 review elements（30 个 text annotations、15 条 arrows）。与
agentic 的 53 claims/28 elements 合并后，新 queue 含 165 条 claim evidence decisions 和 73 个图元素。
Queue 为 `/tmp/code2paper-p4-review-queue-9a98c17-agentic-legacy-inventory.json`，workspace 为
`/tmp/code2paper-p4-review-workspace-9a98c17-v8-agentic-legacy-inventory`；validation 仍为 0 validated、
25 pending、0 invalid、`observations_emitted=false`。机器记录为
`docs/agentic_p4_legacy_review_inventory_2026-07-18.json`。

### 12.20 Digest-pinned rollout authorization（2026-07-18）

继续审计 shadow → opt-in → canary 路径时发现，旧 `RolloutEvidenceV2` 的 `shadow_cases`、
`shadow_reviewed`、`opt_in_cases`、`canary_cases` 和 `canary_incidents` 全由 `--rollout` JSON 自报，CLI
不重读任何 rollout run、人工 review 或前序授权 decision。因此即使 25 个 benchmark reviews 将来完成，
手写计数也可能把状态直接推进到 `default_ready`。

提交 `a4ebab084c233d4417e6de91c2096238d5358d33` 后，这些旧计数被明确降级为不可信输入；非零自报值
产生 `self_reported_rollout_progress_not_accepted`。新增 `RolloutTrialArtifactV2` 和重复
`--rollout-artifact` 输入，每个 artifact 必须绑定 stage/case、具名 reviewer、带时区时间、accepted
decision、前序授权 decision path/digest、可信 agentic run summary 和 complete report；shadow 还必须
绑定 legacy comparison run。授权 decision 必须绑定同一 protocol commit、canonical gold digest 和
digest-pinned named reviews。重复 case-stage、摘要漂移、未接受 trial、越级 opt-in/canary 或 canary
incident 都 fail closed。

Cutover decision 升级为 schema 2.2，保存 invocation-derived `ValidatedRolloutEvidenceV2`、protocol
commit、gold digest 和完整 benchmark case IDs。`run_cli` 的隐式默认切换重新要求所有 benchmark cases
均具有 shadow、opt-in 和 canary artifact coverage、0 canary incidents、唯一 artifact digests 以及完整
named review evidence；旧 2.1 或只含自报计数的 decision 保持 legacy。当前实际 rollout artifacts 仍为
0，正确状态仍是 hold。定向测试 34 passed，全量测试为
`481 passed, 2 skipped, 6 subtests passed`。机器记录为
`docs/agentic_p4_rollout_artifact_gate_2026-07-18.json`。

## 13. 代码落点总表

| 能力 | 主要现有文件 | 计划新增/重点修改 |
|---|---|---|
| 模型接入 | `llm/client.py`, `llm/providers.py` | `llm/capabilities.py`, call trace/schema mode |
| CLI/预算 | `cli/agentic_run.py`, `agentic/contracts.py` | 五项预算、profile、resume、trust mode |
| Authoring projection | `authoring_constraints.py`, `authoring_context.py` | `authoring_projection.py` |
| 最终 claim | `pipeline/stages/authoring.py` | `final_text_claims.py` |
| 语义验证 | `claim_verifier.py`, validators | `text_evidence_validator.py` |
| Text trace | `traceability_models.py`, `traceability_ledger.py` | `text_trace_builder.py` |
| Evidence V2 | `core/schemas.py`, `analysis/ingestion.py` | snapshot/evidence migration modules |
| Freshness | `runner.py`, run manifest | artifact refs/dependency/freshness tool |
| Figure contract | `figure_planner.py` | relation/scene/validation modules |
| Renderer | `legacy_late_stage_tools.py`, rendering | deterministic SVG + post-render audit |
| Graph | `graph.py`, `graph_topology.py`, `graph_*_nodes.py` | final-text/pre/post-render nodes/routes |
| Tools | `langchain_tools.py`, `tool_specs.py`, `tools.py` | fine-grained trust/retrieval tools |
| State/checkpoint | `contracts.py`, `graph.py`, `runner.py` | V2 typed state/reducers/checkpointer |
| Final gates | `invariant_audit.py`, completion/readiness | A-G aggregate + exact digest lineage |
| Evaluation | evaluation/benchmark modules | semantic, figure, drift, block metrics |

实际实施前必须再检查文件是否被其他用户改动；若目标行与未提交改动重叠，只做最小 patch 并保留原意。

## 14. 测试组织方案

### 14.1 测试层级

```text
tests/unit-like existing files
tests/fixtures/adversarial_text
tests/fixtures/adversarial_figure
tests/live
tests/integration
tests/benchmark
```

不要求立即重排所有旧测试目录；新测试按能力分组即可，避免大规模机械移动造成无关 diff。

### 14.2 每次变更的最小测试

每个任务至少运行：

1. 直接相关 test file；
2. agentic graph/contracts/invariant 回归；
3. full collection；
4. 阶段完成前全量测试。

若修改 LLM adapter，再运行 live L0/L1；修改 writer/validator，再运行 toy L2；修改完整 gate，再运行 FastGS L3。

### 14.3 测试结果记录

每次 phase validation 生成：

```json
{
  "phase": "P0",
  "commit_or_tree_hash": "...",
  "commands": [],
  "unit": {"passed": 0, "failed": 0, "skipped": 0},
  "full_suite": {},
  "live_runs": [],
  "known_failures": [],
  "gate_status": "passed"
}
```

命令可以记录环境变量名称，但不得记录 secret 值。

## 15. 人工 review 与解释性 block

尽管实现和执行由 Codex 完成，以下语义决策必须生成用户可读 review artifact：

- 作者核心 claim 被判断为 partial/unsupported；
- static code 不能证明需要 runtime evidence 的行为；
- 高风险 claim 的 verifier 结果冲突；
- 关键方法图箭头因关系证据不足被删除；
- 预算耗尽；
- agentic 与 legacy 的作者意图解释发生实质冲突；
- cutover benchmark 出现高 false-block。

review request 至少包含：

- 原作者意图；
- 当前可支持片段；
- 不支持/冲突片段；
- 精确 evidence refs；
- 缺失证据类型；
- 建议检索路径/符号/运行实验；
- 接受删除、降级或补证据分别会产生什么影响。

人工可以修改 intent、补代码或补 runtime trace，不能直接把 unsupported verdict 改成 supported。

## 16. 风险、缓解与回滚

### 16.1 Gemma 4 结构化输出不稳定

缓解：capability detection、Pydantic validation、一次 repair、deterministic fallback、低温、短上下文和 node-specific schema。回滚只切回 deterministic proposal，不关闭 trust gate。

### 16.2 同一模型写作和验证造成自我确认

缓解：prompt/上下文隔离、确定性规则优先、反证式 verifier、高风险双 pass、direct evidence 强制、人工 review。报告中不得把同模型双 pass 宣称为独立一致性证明。

### 16.3 语义 validator false block 过高

缓解：保存 supported/unsupported fragment、精确 reason、gold set 校准和 authoring rewrite。不得通过接受无关 evidence 降低 false block。

### 16.4 Artifact 版本迁移破坏 legacy

缓解：side-by-side V1/V2 输出、显式 converter、schema version、feature flag 和 contract tests。V1 兼容只服务旧工具，不满足 V2 final gate。

### 16.5 Graph 循环成本失控

缓解：五项预算、调用前扣减、cache、repair target 去重和预算耗尽 block。模型不得修改预算。

### 16.6 FastGS 运行慢

缓解：unit/fake model/toy 先行；FastGS 只在阶段 gate 和关键 vertical slice 运行；使用 checkpoint 降低 P3 后的重复成本。不能用跳过真实项目代替最终 gate。

### 16.7 Renderer 漂移或 OCR 不可靠

缓解：结构化 SVG 为权威 asset，raster 仅派生；PaperBanana 为可选 stylist；无法稳定审计的纯 raster 不作为唯一最终图。

### 16.8 Dirty worktree 冲突

缓解：每个任务开始前检查 scoped status/diff；只修改任务文件；不用 reset/checkout 清理用户改动；重叠时先最小化 patch 并执行 targeted tests。

## 17. 首轮实际执行批次

### Batch A：M0 工程基线

顺序：

1. 从 `agentic-plan-v1` 创建 `codex/agentic-m0-baseline`；
2. M0-01 tracked/untracked inventory、baseline index 和 `.gitignore` 独立提交；
3. M0-02 collection import fix；
4. M0-03 packaging/scripts；
5. M0-04 budgets/exit semantics；
6. full collection + targeted tests；
7. M0-05 Gemma capability adapter；
8. L0/L1/L2 live tests；
9. full test；
10. README 和 M0 validation report；
11. 核对 clean tracked commit 并创建 annotated `agentic-m0-baseline-v1` tag。

Batch A 不改 authoring/figure 的可信度算法。

### Batch B：P0 projection 和 fallback 封堵

顺序：

1. schema + projection；
2. recursive leakage tests；
3. plan hard gate；
4. 删除 authoring fallback；
5. T007 artifact-level regression；
6. toy deterministic/fake model integration。

完成此批后，即使 final semantic validator 尚未全部上线，也应已经消除已知正向输入泄漏路径。

### Batch C：P0 final text semantic loop

顺序：

1. final text unit/claim extractor；
2. deterministic checks；
3. Gemma semantic proposal；
4. conservative verdict merge；
5. text trace builder；
6. graph repair routes/budgets；
7. invariant/ledger/completion migration；
8. adversarial suite；
9. Gemma toy + FastGS；
10. P0 validation report。

### Batch D：P1 evidence/freshness

按 snapshot → exact excerpt → AtomicClaimV2 → dependency digests → stale route → live mutation test 的顺序执行。

### Batch E：P2 figure

按 relation → scene → pre-audit → deterministic SVG → post-audit → optional PaperBanana 的顺序执行。不能先接生成式美化再补 relation evidence。

### Batch F：P3/P4

先完成 tools/state/checkpoint，再启动 benchmark。避免在 graph contract 仍频繁变化时积累不可恢复 checkpoint 和无效 benchmark。

## 18. 任务级完成定义

任一任务只有同时满足以下条件才能完成：

- 代码和 schema 已实现；
- 相关旧行为的兼容/废弃策略明确；
- 正常、失败、越权/对抗路径有测试；
- artifact 包含输入 digest 和 producer version；
- graph route 可解释且受预算约束；
- 不降低任何已有 hard gate；
- 相关测试实际运行并记录结果；
- 若任务触及模型边界，Gemma 4 对应层级已实测；
- 文档和 CLI 与实现一致；
- 没有覆盖无关用户改动。

## 19. 阶段验收检查表

### M0

- [x] 规划文档已有 Git baseline/tag
- [x] tracked/untracked/ignored inventory 完成
- [x] `.gitignore` 已审计并单独提交
- [x] 全量 collection 通过
- [x] agentic extra 可安装
- [x] console scripts 可运行
- [x] 五项预算全链路一致
- [x] Gemma capability profile 可生成
- [x] L0/L1/L2 live tests 完成
- [x] full suite 结果已记录
- [x] M0 validation report 绑定 clean commit
- [x] annotated phase tag 已创建

### P0

- [x] writer 只消费 projection
- [x] 无首项 claim/evidence fallback
- [x] final claims 从最终文本提取
- [x] semantic validation 绑定 direct evidence
- [x] partial qualifier 强制保留
- [x] final text trace 为后验权威 trace
- [x] adversarial leakage 为 0
- [x] FastGS 正确 success/block

### P1

- [x] repo snapshot 可复验
- [x] exact excerpt digest 可 round-trip
- [x] direct/context evidence 分离
- [x] report 绑定 input digests
- [x] evidence 更新使下游 stale
- [x] source drift 阻止 finalize
- [x] live mutation/resume 通过

### P2

- [x] edge 仅来自 direct relation evidence
- [x] scene 每个可见元素可追溯
- [x] 真实 SVG asset 生成
- [x] pre/post-render audit 均为 hard gate
- [x] completion 不再接受 plan-only
- [x] Gemma/PaperBanana drift 被拒绝或回退

### P3

- [x] 细粒度工具契约完整
- [x] typed state + reducers
- [x] durable checkpoint/resume
- [x] freshness 在 resume 时重检
- [x] tool selection 不可越权
- [x] cache/预算/调用可审计
- [x] fresh Gemma 4 三处中断恢复与 uninterrupted control 等价

### P4

- [x] gold/adversarial benchmark 可复现
- [x] 三个以上真实项目
- [x] Gemma 4 每 case 三次（正式 25-run protocol 中 5 个 case-intent 组合各 3 次）
- [ ] 所有可信度硬阈值达到
- [ ] shadow/canary 完成
- [ ] 默认路线切换有数据支持
- [x] legacy contract version 明确

## 20. 最终交付形态

完成全部阶段后，一次可信 Code2Paper 运行至少产出：

```text
artifacts/
  01_input/intent_spec.json
  02_intake/repo_snapshot.json
  04_evidence/evidence_snapshot.json
  04_evidence/atomic_claim_contracts.json
  04_evidence/semantic_claim_verification.json
  06_authoring/agentic_authoring_input_projection.json
  06_authoring/agentic_authoring_plan.json
  06_authoring/agentic_final_text_claims.json
  06_authoring/agentic_text_evidence_validation.json
  06_authoring/agentic_text_claim_trace.json
  07_validation/validation_manifest.json
  08_rendering/agentic_figure_scene_graph.json
  08_rendering/agentic_figure_relation_validation.json
  08_rendering/agentic_pre_render_audit.json
  08_rendering/rendering_manifest.json
  08_rendering/agentic_post_render_audit.json
  10_run/agentic_traceability_ledger.json
  10_run/agentic_final_invariant_audit.json
  10_run/agentic_run_completion_report.json
  10_run/agentic_run_evaluation_report.json
  10_run/run_manifest.json
checkpoints/
final/
  method.md
  method.tex
  figures/method_overview.svg
  package_manifest.json
```

最终 package manifest 必须把 final text、figure 和 PDF（若生成）绑定到已通过 gate 的 exact digests。

## 21. 执行结束判定

整个重构只有在以下事实同时成立时结束：

1. 作者意图影响检索和组织，但不能覆盖代码证据；
2. 每个最终方法 atomic claim 通过 direct code evidence 语义验证；
3. partial claim 只写支持片段并保留限定词；
4. final text trace 从最终文本反向生成；
5. 任意合法但无关 evidence ID 都不能通过；
6. 每个图节点、边和标注独立可追溯；
7. 真实图形 asset 通过 post-render audit；
8. 所有 gate 检查状态和 digest，不只检查文件存在；
9. LangGraph 决策有预算、checkpoint、resume 和完整 trace；
10. LangChain 工具有结构化 contract、幂等和 evidence policy；
11. toy 与真实项目能够可信 success 或解释性 block；
12. Gemma 4 多次真实运行没有造成 gate 绕过；
13. benchmark 证明 agentic route 的语义证据精度不低于 legacy；
14. 默认路线切换经过 shadow/canary，而不是基于单次 demo。

最近的实际执行入口是 Batch A。M0 完成前，不进入 P0 大规模实现；P0 语义正文 gate 完成前，不以方法图美化或多 Agent 自主性作为优先工作。
