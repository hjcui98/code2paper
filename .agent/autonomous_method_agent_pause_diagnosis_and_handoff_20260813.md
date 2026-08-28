# 自主 Method Agent 暂停执行后的诊断与交接报告

- 日期：2026-08-13
- 状态：`PAUSED_DIAGNOSTIC_ONLY`
- 范围：RAP 单义务研究、方法命题编译、Architect/Writer 重放，以及相关静态测试
- 当前决定：停止生产代码修改、模型调用、API 运行和测试；本文只总结已经发生的工作
- 产品目标：给定作者意图或 claims，Agent 自主研究代码仓库，把找到的证据提升为可读的
  方法语义，按作者 story spine 写出 Method candidate；仓库可证明的正向句进入 verified，
  其余内容进入自然 caveat、callback 或 author review

## 1. 执行结论

本轮没有把产品修到可验收状态。真正取得的进展有两项：

1. Research Manager 的代码接口已经从“只看到脚本状态、ID 和候选数量”改成可以看到真实的
   已编译证据陈述、已执行工具调用和 policy rejection，并允许 LLM 在被策略拒绝后重新选择
   查询；
2. OpenAI-compatible SSE 客户端的 `[DONE]` 和缓冲读取问题已经定位并修复，Writer 重放不再
   因客户端忽略流结束而假性挂死。

但是，第一项还没有通过一轮全新的、干净的 research-only 真实运行证明；第二项只解决传输，
不解决内容质量。当前最主要的产品阻塞已经转移到 research evidence 到 Method prose 之间的
“方法语义提升层”：

- 旧实现把源码操作压成 `subject + predicate + object`，Writer 得到的是代码流水账；
- 新增 proposition 层起初能生成方法卡片，但会把作者目的、下游用途和 harness 术语混入
  仓库事实，并把无关 sibling facts 一起绑定；
- 随后增加的原子性和字段校验虽然阻止了越权内容，却把所有仓库 proposition 都过滤掉；
- 最新 W 预处理运行只剩 1 条 author-intent partial proposition、0 条 repository proposition，
  因此安全但不可用，不能继续启动 Writer。

所以，对“LLM 只给脚本状态机选动作、不能理解工具结果并自主决定下一次查询”这个问题，
准确回答是：**代码入口已做实质修正，但尚未完成真实产品验收；整条端到端流程仍未解决。**

## 2. 本轮开始时观察到的产品现象

这些现象不是单纯的措辞不好，而是产品主链的语义所有权错位。

### 2.1 Research Agent 看似跑了很多 turn，却没有真正基于观察继续研究

此前四项目和 RAP 真实运行反复出现：

- Agent 可以调用 search/read/trace 工具，但 Supervisor 主要看到 action label、内部 ID、
  candidate count 和 closure 状态；
- query/path/symbol 很大程度由 deterministic fallback 决定，LLM 不拥有完整的下一步查询；
- 工具返回的实际源码内容没有以有界 observation 进入 Manager 的决策上下文；
- 读取一个正确函数后，模型仍再次建议同一 read，随后脚本 fallback 换工具；
- `max_turns`、duplicate/no-gain 或 fallback exhaustion 控制了终止，而不是 Agent 判断“证据够了”
  或“当前问题确实缺证据”。

这解释了为什么系统具备 LangGraph、工具节点和很多 typed state，却仍不像一个能够研究代码的
Agent：图在运行，但主要决策权仍在脚本状态机。

### 2.2 研究证据存在，Writer 却只得到代码操作句

RAP 的真实源码已经暴露了特征拼接、SH anisotropy、scale 排序、volume、opacity、局部/全局
z-score、percentile clipping 和归一化等机制。旧事实编译却直接产生类似内容：

- `sorted scales sorts scales along dimension 1`；
- `volume computes by taking the product`；
- `calls torch.quantile`；
- `normalizes (clipped - lower) / (upper - lower)`。

这些内容适合作为 evidence sidecar，不适合作为论文句子计划。Writer 只能对它们做表面改写，
无法自然恢复作者真正要讲的“每个 Gaussian 的描述符是什么、为什么这样构成、如何统一归一化、
再如何送入后续 predictor”。

### 2.3 Architect 的标题可能对，但内容组织并不对

旧 planning 会把同一 obligation 的 claims 再分成 `Implementation stage 1` 和
`Additional method mechanism`。两个 section 绑定同一批 propositions，产生确定性重复。
在更早的整篇 RAP 产物中，也出现过 story spine 标题正确但正文错位：Overview 写属性表构造，
Feature extraction 写代码操作，Learning framework 使用模板占位，Deployment 为空。

### 2.4 Writer/Rewrite 既慢又没有变成论文语言

Writer 重放时观察到：

- 局部 Rewrite 每进行一次 transaction，都会触发一次全篇、逐句的 proposition semantic
  alignment；
- 一个 section 的写作因而膨胀成大量串行 LLM 请求；
- 本地运行超过 15 分钟仍没有最终 candidate；
- vLLM 指标显示多次达到 length finish，未出现 OOM 或 abort，说明主要是请求设计和输出长度，
  不是 GPU 故障；
- 已持久化句子仍是 “The sorted scales sort ...” 和
  “The volume computes by ...” 这种代码流水账。

### 2.5 Prompt 有问题，但 Prompt 不是唯一根因

Prompt 的确过长，混入了 rhetorical moves、proof、claim/fact ID、binding、callback、校验字段和
正文要求。但仅缩短 Prompt 不能修好以下结构性问题：

- 上游没有给出方法级语义，只给低层操作；
- 同一 proposition 错绑多个无关事实；
- Evidence Judge 只返回“哪些字段 supported”，没有逐字段说明证据为什么支持该语义；
- Author intent 和 repository evidence 在 proposition 生成时发生 authority expansion；
- Architect 用 obligation/claim 分桶，不用概念和作者 story 组织段落。

正确方向是先修输入表示、证据绑定和角色职责，再收缩 Prompt；不是继续追加禁词或 validator。

## 3. 真实运行与日志证据

所有 `/tmp` 目录只证明当时绑定的代码、输入和协议，不是当前正式验收结论。

### 3.1 P：最初的单义务 Research 运行

产物根：

`/tmp/code2paper-codex-rap-product-feature-20260813-p`

最终 immutable checkpoint：

`/tmp/code2paper-codex-rap-product-feature-20260813-p/artifacts/research_tool_data/immutable_checkpoints/16a2cfca62655b7838a428c032471b1a6c060e0667a4003b8e8760b531fd9b59.json`

输入问题是：从 raw Gaussian attributes 中抽取紧凑的 15 维特征并归一化。

核对结果：

| 项目 | 结果 |
|---|---:|
| Evidence packets | 2 |
| Code facts | 12 |
| Atomic claims | 11 |
| Agenda status | `partial` |
| Supported claim IDs | 8 |
| 最终动作 | `STOP_BLOCKED` |
| 最终原因 | `policy_merge_fallback_exhausted` |

决策序列：

1. T0：LLM 自主 `SEARCH_SYMBOLS`，寻找 15 维 Gaussian feature；
2. T1：LLM 自主读取 `GaussianModel.get_prune_input_f15`，方向正确；
3. 后续 LLM 再次建议已经执行过的 read，被 duplicate policy 拒绝；
4. T3：deterministic fallback 执行 `READ_CANDIDATE`；
5. T4：deterministic fallback 执行 `SEARCH_SYMBOLS`；
6. fallback 又命中已执行调用，终止为 `policy_merge_fallback_exhausted`。

值得注意的是，checkpoint 中 `compiled_evidence` 已经有 2 packets、12 facts、11 claims，
`gain_tracker` 也知道已发现 `get_prune_input_f15`、`percentile_cutoff_normalize` 和相关 spans；
但顶层 `recent_observations` 为空。也就是说数据平面找到了内容，控制平面没有把内容作为下一轮
推理的主要上下文。

结论：P 证明旧 Research loop 的确会“找到证据但不会自然继续研究”。它不是模型完全找不到
代码，也不是工具不可用。

### 3.2 Q/R：兼容 resume 与旧 proposition/plan 产物

兼容 research checkpoint：

`/tmp/code2paper-codex-rap-product-feature-resume-20260813-q/artifacts/research_product/research_stage_checkpoint_v1.json`

规划与 proposition 产物根：

`/tmp/code2paper-codex-rap-product-feature-resume-20260813-r`

R 中生成 13 条 propositions：11 条来自 repository evidence，2 条是完全重复的
author-intent proposition。仓库 propositions 中存在有价值的读者语义，例如：

- 从 SH coefficients、60 个采样方向和最大 SH degree 计算 anisotropy；
- 沿维度 1 排序 scales；
- 对 volume/opacity 做 log 和 global z-score；
- 拼接 distance、anisotropy、scales、volume、opacity 和 RGB 的局部/全局特征；
- 使用 0.01/0.99 percentile bounds 做 clipping/min-max normalization。

但 plan 出现三个错误：

1. 同一 obligation 被分成 2 节并重复绑定同一组内容；
2. `repository_partial` 被当成可进入 verified；
3. 总体 readiness 是 `verified_ready`，没有 review item。

这个运行证明“方法级 proposition”方向是对的，同时也证明 plan/readiness 当时会把 partial
错误升级成 verified。

### 3.3 S：Writer 重放

产物根：

`/tmp/code2paper-codex-rap-writer-replay-20260813-s`

已持久化的中间验证产物包含：

- 24 个 final-text units，共 2919 个正文字符；
- 28 个 atomic claims，共 2848 个字符；
- `agentic_text_evidence_validation.status = failed`；
- 没有形成最终 publication candidate。

代表性句子：

> The sorted scales sort the scales along dimension 1.

> The volume computes by taking the product of the scales along dimension 1.

> The global volume z-score computes by applying a logarithm to the volume ...

运行超过 15 分钟后仍在 Rewrite → transaction validation → whole-document proposition alignment
链中。监控期间 length-finished 请求持续增加，而 abort/preemption 没有对应增加。最终手动停止，
没有把它报告为成功。

结论：S 同时暴露了 prose 输入质量问题和 transaction 级验证导致的请求爆炸。

### 3.4 T/U：proposition 与 Writer 的中间诊断

这两次不是可验收运行，主要发现：

- plan 合并后可以只保留一个 `Per-primitive feature descriptor` section；
- 15 维和属性组件开始进入 author-intent proposition；
- 重放脚本起初漏接 Evidence Judge，repository proposition 被错误当成 verified，因此停止 Writer；
- proposition 的公开 response schema 暴露内部 relation/fact IDs，本地模型生成上百个伪 ID，
  出现 schema echo 和长度耗尽；
- 改为语义-only response 后，transport 能完成，但 proposition 仍会混入 author purpose、
  downstream pruning、binding harness 等证据没有授权的文本。

这些运行用于定位协议问题，没有形成产品结论。

### 3.5 V：Evidence Judge 接入后的 prepare-only 运行

产物根：

`/tmp/code2paper-codex-rap-proposition-prepare-20260813-v`

结果：5 条 propositions，其中 4 条 repository proposition 被 Judge 判为 `entailed`，1 条为
author-intent partial。没有启动 Writer。

表面上覆盖增加，实际存在严重越权：

- proposition 是长段落，不是可控的 semantic card；
- 文本包含 “author intends to ... as a pruning signal”；
- 文本包含 “binding harness maps ...” 等产品内部元语言；
- 重复生成 `Scale magnitude representation`；
- 某条 proposition 同时绑定 volume product、其他 sibling operation 和无关 span；
- Judge 只返回 `supported_fields = [reader_subject, transformation]`，`rationale` 为空，仍把整段
  transformation 判为 entailed；
- Judge 第一次响应还发生 supported/unsupported field 不相交校验失败，第二次 repair 才通过。

结论：V 不是真正的证据验证成功，而是 proposition 过宽、binder 过宽、Judge 判定粒度过粗
共同造成的假阳性。

### 3.6 W：增加原子性/字段限制后的最新 prepare-only 运行

产物根：

`/tmp/code2paper-codex-rap-proposition-prepare-20260813-w`

结果：

- Architect structured response 正常完成；
- 只保留 1 条 proposition；
- 该 proposition 来自 author intent，lane 为 `repository_partial`，`may_enter_verified = false`；
- proposition 正确保留了 `15` 以及 distance、color anisotropy、scales、volume、opacity、DC color；
- repository propositions 为 0；
- Evidence Judge calls 为 0，因为没有合法 repository proposition 可审；
- 产生多条 `concept_not_atomic`、`concept_fields_missing` 和
  `concept_coverage_missing` gaps；
- 没有启动 Writer。

这说明新增 guard 做到了 fail-closed，却走向了另一端：它通过拒绝所有仓库内容获得安全，
没有把代码事实提升成可写的方法概念。W 是当前最准确的停止点。

## 4. 根因分析

### 4.1 根因 A：Research 控制平面与 evidence 数据平面断开

旧 Supervisor 决策输入没有稳定包含：

- 最近工具 observation 的源码摘要；
- 已确认的方法语义；
- 已执行过的 exact tool calls；
- policy rejection 的具体原因；
- 当前问题还缺哪一个语义字段。

因此 LLM 即使第一次选对函数，第二次也无法基于函数内容决定追 caller、data flow、normalizer
或 network。脚本 fallback 只能轮换工具，不能完成真正的研究推理。

### 4.2 根因 B：fact/claim 被错误用作写作单位

Atomic fact/claim 是验证单位，不是论文论证单位。当前旧链条的核心错误是：

```text
源码语句 -> fact(subject, predicate, object) -> Writer sentence
```

正确链条应是：

```text
多个相关源码片段
  -> 方法概念理解（operation / inputs / outputs / conditions）
  -> 对每个语义字段做 evidence judgment
  -> Method concept card
  -> paragraph brief
  -> Writer prose
```

没有中间的“方法理解”步骤，Writer 只能写代码流水账；让 Writer 自己从数十个低层 fact 恢复
方法，也会让它同时承担研究、验证和写作三个冲突职责。

### 4.3 根因 C：proposition 输出结构仍是自由长文本

当前 proposition 中 `transformation` 可以承载一整段文字。即使 Prompt 要求原子，模型仍可把：

- 实际操作；
- 作者动机；
- 下游用途；
- 代码标识符；
- binding harness 描述；
- 论文表达

全部塞进一个字段。后续 Judge 又把 `transformation` 当一个整体字段标记 supported，无法指出
哪一小段没有证据。

本质上需要改变 schema，不是继续增加 `concept_not_atomic` 字符规则。

### 4.4 根因 D：evidence binder 通过粗粒度词重叠扩张绑定

`_bind_source_fragments` 一类逻辑会根据 mechanism token 把 sibling statements 加入同一
proposition。结果是描述 volume 的卡片也可能拿到 anisotropy、percentile 或 concat 的 facts。
Judge 看到了很多真实代码，却无法区分哪些证据对应 proposition 中的哪一部分，于是宽泛文本
更容易被判为 entailed。

正确默认应是“模型选择的精确 source fragments”，只有存在明确 call/data/control/config
relation 且某个语义字段确实需要时，才允许扩展 sibling evidence。

### 4.5 根因 E：Evidence Judge 的协议粒度不足

当前 Judge 主要返回：

- proposition-level status；
- supported field names；
- unsupported field names；
- 一组 fact/span IDs；
- 可为空的 rationale。

它不能表达：`operation` 被哪个 span 支持、`purpose` 没有证据、数字 15 是作者给的还是代码算出的、
“for pruning” 是调用上下文推断还是作者意图。因此一旦 transformation 字段过宽，Judge 无法
可靠 fail-closed。

### 4.6 根因 F：Author intent 和 repository authority 在生成阶段混合

作者 intent 应决定研究范围和行文结构，也可以进入 candidate caveat；但它不能被写进
repository proposition。V 的 repository cards 出现 “author intends ...” 表明 authority
separation 太晚，直到验证阶段才试图纠正已经混合的文本。

应分别生成 repository concept cards 和 author-intent cards，再在 Architect/Writer 输入层并列，
而不是让一个生成响应同时混合两种 authority。

### 4.7 根因 G：覆盖目标设错了

为了不丢事实，compiler 要求每个 `calls / reduces / sorts / normalizes` statement 都被某条
proposition 覆盖。这会迫使模型为低层操作逐条写卡片，也会在严格化后产生大量
`concept_coverage_missing`。

产品需要覆盖的是作者 story 中的方法概念和重要机制，不是每条 AST/fact predicate。未使用的
低层 facts 应保留在 evidence ledger，不能强迫全部进入正文概念。

### 4.8 根因 H：Writer/Rewrite 验证位置不合理

最终 reverse validation 必须保留，但不需要每个局部 rewrite transaction 都重新调用 LLM
对整篇文档逐句对齐。该设计既昂贵，又让模型在协议性任务上消耗绝大多数上下文和时间。

中间 transaction 只需要检查修改 section 的确定性约束、数字/公式保持和授权 concept 集；
整篇 semantic reverse validation 在最终 draft 上做一次即可。

## 5. 本轮已经实施的内容

下面只列本轮能够确认的修改方向。当前工作树包含大量历史 OpenCode、用户修改、未跟踪文件和
生成的 `__pycache__`；不能把整个 `git diff` 都归因于本轮。

### 5.1 Research Manager 上下文与 policy repair

涉及：

- `src/code2paper/agentic/research_supervisor.py`
- `src/code2paper/agentic/gemma_supervisor_backend.py`
- `src/code2paper/agentic/research_nodes.py`
- `src/code2paper/agentic/research_graph.py`
- `src/code2paper/agentic/autonomous_method_agent.py`

已做：

- 新增 `ExecutedToolCallSummaryV1`；
- Supervisor context 增加当前 supported claim 的自然语言陈述；
- 增加已执行工具、query/path/symbol 摘要；
- 增加 policy feedback；
- Prompt 不再只暴露 opaque refs；
- LLM proposal 被 policy 拒绝后，允许一次带拒绝原因的 `repair_after_policy_rejection`，再由同一
  policy 校验；
- graph 在 direct 和 LangGraph 路径上投影真实 statement、exact calls 和 observation；
- resume 时可恢复历史 LLM decisions；
- 增加 research-stage checkpoint/resume 入口。

当前评价：这是正确方向，但只有单元/集成测试，没有 fresh research-only canary，因此状态是
`IMPLEMENTED_NOT_LIVE_ACCEPTED`。

### 5.2 SSE 客户端完成与缓冲读取

涉及：

- `src/code2paper/llm/client.py`
- `tests/test_llm_runtime.py`

已做：

- 收到 SSE `[DONE]` 后返回完整 JSON，或进入受控的 partial representation recovery；
- 删除对 urllib raw fd 的 `select.select` 依赖；
- 使用 socket read timeout 和 `response.readline()`，优先消费 Python 已缓冲的数据；
- 增加 `[DONE]` 和 buffered-read 回归测试。

真实效果：修复后 Writer replay 在服务端完成响应时可以立即进入下一请求。后来等待的 stack
位于真实 socket read，说明假性 idle/hang 已消除。

当前评价：`IMPLEMENTED_AND_RUNTIME_OBSERVED`，但它只解决传输层。

### 5.3 Method proposition 与 Evidence Judge 原型

涉及：

- `src/code2paper/agentic/method_proposition_models.py`
- `src/code2paper/agentic/method_proposition_provider.py`
- `src/code2paper/agentic/method_proposition_compiler.py`
- `src/code2paper/agentic/method_proposition_evidence_provider.py`
- `src/code2paper/agentic/method_proposition_alignment_provider.py`
- `src/code2paper/agentic/proposition_semantic_aligner.py`

已做：

- 新增方法 proposition 模型和聚类；
- 增加低温、批量的 Evidence Judge；
- Judge timeout 默认 90 秒、上限 180 秒、最多一次 repair；
- proposition 公开响应 schema 改成 semantic-only，不允许模型生成内部 IDs；
- 内部 IDs 和 digest 由 harness 生成；
- 为字段和数组增加长度上限；
- repair merge 尽量保留首轮合法 cards，避免 repair 覆盖好内容；
- author proposition 保留 15 维和 components；
- 增加重复、meta language、authority expansion、missing fields 等检查；
- 减少部分低层 predicate 的强制 coverage。

当前评价：`PROTOTYPE_NOT_ACCEPTED`。V 发生过度放行，W 发生过度拒绝，说明 schema、binder 和
Judge 必须重做，不应继续叠加字符串 validator。

### 5.4 Architect 与 readiness

涉及：

- `src/code2paper/agentic/method_architect.py`
- `src/code2paper/agentic/method_product_models.py`

已做：

- 同一 exact obligation 的 remaining claims 优先合并到已有 section，不再自动创建
  `Additional method mechanism`；
- 单 section 使用 method name/故事标题；
- 最后一节不强制 transition；
- `repository_partial` 不再默认进入 verified positive lanes；
- partial 进入 candidate + review/callback，而不是错误标记 `verified_ready`。

R 的冻结输入经过修改后观察到：两节可合并为一节，readiness 可变为
`candidate_ready_with_review`。当前评价：方向正确，但需在新 concept card 结构上重新验收。

### 5.5 Writer/Editor/Rewrite 请求收敛

涉及：

- `src/code2paper/agentic/publication_method_writer.py`
- `src/code2paper/agentic/cross_section_editor.py`
- `scripts/run_publication_writer_from_artifacts.py`
- `tests/live/profiles/qwen36_vllm_budgeted.example.env`

已做：

- 中间 rewrite transaction 的 `_rewrite_transaction_metrics` 不再调用整篇 semantic LLM
  validation；最终 draft 仍保留正式验证路径；
- Editor context 增加 candidate-only author narrative、reader-facing claims 和 section aliases；
- artifact replay 支持 proposition/readiness 输入；
- 增加 `--prepare-propositions` 和 `--prepare-only`，可在不启动 Writer 的情况下诊断语义层；
- Writer/Editor response mode 由 `json_object` 切到 runtime capability 已支持的
  `native_json_schema`。

当前评价：性能和诊断能力有进展，但没有得到一篇新的可接受正文。不能据此声称 Writer/Editor
质量已经修复。

## 6. 已执行测试与运行结果

本节记录本轮已经发生的结果，不重新运行。由于本轮早期没有把每个临时 focused command
完整写入一个统一 ledger，下面的结果按会话记录和相应测试范围归纳；不能替代后续正式验收的
精确 command/exit/artifact 记录。

### 6.1 静态/聚焦测试

| 时点/范围 | 结果 | 说明 |
|---|---|---|
| Research supervisor/graph/nodes/backend | 230 passed, 1 skipped | 覆盖新上下文、已执行 calls、policy repair、resume 投影 |
| LLM runtime focused | 21 passed | 包含 SSE `[DONE]` 和 buffered-read 回归 |
| Architect/rewrite 第一批 | 117 passed | section 合并和 transaction validation 变更后 |
| Partial readiness/proposition 一批 | 164 passed | partial 不进入 verified 等 |
| Semantic-only response schema 一批 | 156 passed | 内部 ID 不暴露给模型 |
| Proposition/runtime/profile 扩展一批 | 176 passed | provider 与 native schema 相关 |
| Repair merge/native 调整一批 | 157 passed | 保留合法首轮 cards |
| 最新相关 focused suite | 214 passed, 2 warnings | 最新 guard、compiler、runtime、Architect 相关测试 |

两条 warning 是 Writer 测试中的 Pydantic tuple/list serializer warning，不是本轮产品阻塞。

重要限制：

- **没有在最新 W 代码状态上执行全量静态 suite**；
- 没有在停止指令之后执行任何测试；
- 早期 OpenCode 报告的 2425 passed 或更早全量结果不能证明本轮后续修改；
- test count 只证明局部契约，没有证明 Agent 能自主研究或写出可用 Method。

### 6.2 本地模型/API 运行

授权 runtime：

- Base URL：`http://127.0.0.1:8003/v1`
- Model：`qwen36-27b-nvfp4`
- Context：131072

本轮开始时只读检查观察到 `/health` 和 `/v1/models` 为 200，队列 idle，KV cache 空闲；运行中
没有观察到 OOM。S 的长时间问题来自请求设计、length finish 和重复验证，不是 runtime 不存在。

真实运行结论：

| 运行 | 是否完成 | 能证明什么 | 不能证明什么 |
|---|---|---|---|
| P Research | terminal blocked | 工具能找到真实 feature 代码；旧 control loop 会重复/fallback 耗尽 | 新 Manager 已自主闭环 |
| R planning | 完成 | 旧 proposition 有部分有价值方法语义 | readiness 和 section 组织正确 |
| S Writer replay | 手动停止 | SSE 修复后请求能继续；Writer/validation 链真实过慢 | 可生成 publication candidate |
| T/U diagnostic | 主动停止 | ID schema、Judge 接线和 authority expansion 问题 | 产品质量 |
| V prepare-only | 完成 | Judge 原型能运行 | 4 条 `entailed` 真实可靠 |
| W prepare-only | 完成 | fail-closed guard 生效 | repository concept 覆盖或 Writer 可运行 |

没有进行四项目复跑，因为 RAP 单义务的 proposition 层尚未通过最小质量门。继续跑四项目只会
放大同一缺陷并消耗时间。

## 7. 当前各子系统的真实状态

| 子系统 | 当前状态 | 说明 |
|---|---|---|
| Tool registry/read/search/trace | 可用 | P 已找到正确源码；不是主要阻塞 |
| Research Manager 输入接口 | 已修改、未真实验收 | 能携带 observation/claims/exact calls/policy feedback，但缺 fresh canary |
| Research checkpoint/resume | 已实现兼容路径 | Q/R 可读取；尚未证明正常终止后 resume |
| SSE/OpenAI client | 已修复并观察 | `[DONE]`/buffer issue 基本解决 |
| Atomic facts/claims | 可作验证底座 | 不能直接作 Writer 句子计划 |
| Method proposition/compiler | 阻塞 | V 过度放行，W 过度拒绝 |
| Evidence binder | 阻塞 | 会把无关 sibling facts 绑进同一卡片 |
| Evidence Judge | 阻塞 | 不是逐语义字段判定，允许空 rationale |
| Architect | 部分修复 | 重复 section/readiness 问题已改，需对新概念结构重验 |
| Writer | 未验收 | 仍缺高质量、被证据授权的概念输入 |
| Editor/Rewrite | 未验收 | transaction 性能改善，但整节学术改写未证明 |
| Callback/resume | 历史主链有原型 | 本轮 feature-only 路径没有重新证明补到新证据 |
| Candidate/verified/review 三输出 | 历史上可生成 | 本轮新架构没有端到端产物 |
| 产品总体 | `BLOCKED_AT_METHOD_UNDERSTANDING` | 当前不能声称可用或投稿级 |

## 8. 后续修复原则

后续开发不应从 W 继续增加 validator，也不应直接重启 Writer。应先重做“方法理解”这一层。

必须保留的真实性边界：

- repository verified 正向句必须有 frozen repository evidence；
- 作者意图只能控制 scope/organization 或进入可见 caveat，不能授权实现事实；
- 数字、公式、配置、qualifier 和最终 reverse validation 继续 fail-closed；
- 缺输出不能算成功；
- harness 只修 representation，不改语义。

应移出正文主链的机制：

- 每条低层 predicate 都必须变成 proposition 的 coverage quota；
- 基于 mechanism token 的 sibling evidence 自动扩张；
- Writer prompt 中的 fact/claim/relation IDs、semantic frames 和 move proof 明细；
- 每个 rhetorical move 强制一段；
- 每个局部 rewrite 都做整篇 LLM semantic alignment；
- `Pending confirmation...`、`We aim to explain...` 之类占位正文。

## 9. 后续代码级修复方案

以下是未来计划，不是本轮已执行内容。应按顺序推进，在每个阶段通过最小真实例子后再进入下一步。

### Stage 0：冻结和归因当前中间状态

目标：避免在脏工作树中继续叠改而无法判断哪个机制有效。

措施：

1. 不使用 `git reset/clean/checkout`；
2. 以本文列出的文件和 `/tmp` 产物为边界，人工审查当前 proposition 相关 diff；
3. 把 W 的严格 guard 标记为实验性，不把它当成目标实现；
4. 在下一次开发前建立一个只记录本任务 exact commands、exit、artifacts 的简短 ledger；
5. 不清理或覆盖用户和 OpenCode 的无关修改。

退出条件：能够说明每个待改函数由哪个阶段负责，不存在两个并行任务改同一文件。

### Stage 1：只验 Research Manager，不碰 Writer

目标：证明 LLM 真正读取 observation 并自主决定下一次查询。

代码重点：

- `research_supervisor.py`
- `gemma_supervisor_backend.py`
- `research_graph.py`
- `research_nodes.py`

Manager 每轮最少看到：

- 当前自然语言 research question；
- 最近 1--3 个 observation excerpts；
- 已确认的方法结论；
- 已执行 exact calls；
- policy rejection；
- 当前缺失语义字段。

Manager 输出：

- 一个工具调用及完整参数，或最多 2--3 个明确独立调用；
- 为什么该调用能回答哪个缺失字段；
- 预期 stop condition；
- 或提交 typed gap/当前理解。

harness 只校验路径、symbol 来源、budget 和重复调用，不替 Manager 生成 query。

退出条件：一次 RAP 8--12 turn research-only run 中，Manager 读取 `get_prune_input_f15` 后能根据
代码内容主动选择追 normalization/inputs/caller，而不是重复 read；被 policy 拒绝后不再命中同一
exact call；最终为 completed/partial-with-explicit-gap，而不是 fallback exhaustion。

### Stage 2：以 Method Concept Card 取代自由长 proposition

目标：把多个低层 facts 合成为 3--8 个读者可理解的方法概念。

建议新模型（字段名可调整）：

```text
MethodConceptCardV1
  concept_key                 # harness 生成
  authority_lane             # repository / author_intent / external / formalization
  research_question
  method_subject
  operation
  inputs[]
  outputs[]
  conditions[]
  numeric_constraints[]
  formula_constraints[]
  evidence_fragment_refs[]   # 模型从当前有界 source fragments 中选择
  story_node
  known_parts[]
  missing_parts[]
  candidate_caveat
```

关键规则：

- 不再提供一个可以容纳整段 prose 的 `transformation` 字段；
- `operation/inputs/outputs/conditions` 都是短语，有严格但合理的长度；
- repository card 的输入只包含 repository observations，不包含 author purpose；
- author card 单独编译，不能变成 `may_enter_verified=true`；
- 一个 card 可以覆盖多个真正相关的 low-level facts；
- 不要求每条 `calls/reduces/sorts` 都生成 card；
- 未用于正文的 facts 留在 evidence ledger。

RAP feature 问题的预期概念不是十几个 AST 操作，而应类似：

1. per-primitive geometric/photometric descriptor composition；
2. distance/anisotropy statistics；
3. scale-derived volume and opacity transformations；
4. local/global standardization；
5. percentile clipping/min-max normalization；
6. 作者声称的“精确 15 维”中代码尚未闭合的部分。

退出条件：prepare-only 能得到少量、无重复、无内部元语言的 cards；读者不用看函数名也能理解
方法；15 维和 components 不丢失。

### Stage 3：精确 evidence binding 和逐字段 Judge

目标：消除 V 的假阳性。

Binder：

1. 默认只绑定 card 明确选择的 source fragments；
2. fragment refs 必须来自本 cluster 的 closed candidate set；
3. 只有存在已验证的 call/data/control/config relation 且某字段需要时，才补 sibling evidence；
4. 禁止仅凭共同 token 或 mechanism label 扩张；
5. 每个 binding 记录 `field -> exact fragment refs`，而不是 card -> 一大组 facts。

Judge 输出建议：

```text
field_judgments[]:
  field_name
  proposed_value
  verdict: entailed | partial | contradicted | not_found
  evidence_fragment_refs[]
  rationale
overall_verdict
```

判定规则：

- repository card 只有所有正向语义字段分别 entailed 才可进入 verified lane；
- rationale 不能为空；
- purpose/downstream claim 如果没有 caller/dataflow evidence 就必须 partial/not_found；
- 数字 15 必须明确标记来自代码、作者还是两者；
- 一条 card 不能靠无关 facts 的总体存在通过。

退出条件：V 中 “author intends”“binding harness” 和无证据 pruning purpose 被逐字段拒绝；
volume card 只绑定 volume/product/log/normalization 的精确证据，不绑定 anisotropy 或 percentile。

### Stage 4：重建 Architect → Writer → Editor 的最小语义接口

Architect 输入：

- 作者 story spine；
- repository concept cards；
- caveated author cards；
- mismatch/external/formalization gaps。

Architect 输出 3--6 个 reader-facing sections/paragraph briefs，每个 concept 只分配一次。不要再按
claim count 或 rhetorical move 数量膨胀 section。

Writer Prompt 收缩为四层：

1. 本节需要回答的问题和段落目标；
2. 可以正向陈述的 repository-supported Method concepts；
3. 必须显式 caveat 的 author-intent/partial concepts；
4. 不得改变的数字、条件和公式。

低层 fact/claim IDs 和 semantic frames 放在 sidecar，由 harness 做授权映射，不进入 Writer 主
上下文。Writer 输出正文和使用/延迟的 concept ordinal，harness 再映射内部 ID。

Editor 应收到整节 prose、同一组 concepts、术语表和学术风格 rubric，可以整节重写；它不能
新增 concept、数字或因果。Rewrite 只处理某个明确 issue，不重新规划全文。

退出条件：frozen good cards 的 writer-only RAP 产物满足：

- 不是代码执行顺序；
- 没有内部路径/ID/harness 元语言；
- 每段有明确主题和逻辑连接；
- caveat 是有内容的论文表达，不是占位句；
- supported concept 的自然语言覆盖足够；
- 最终 reverse validation 后 verified 只保留真正支持的正向句。

### Stage 5：把 callback 接回同一个 Research Manager

Writer 不应只请求 `limitations_or_mismatch` 这种修辞标签。callback 需要携带：

- section/concept；
- 缺失字段；
- 当前为什么不能写；
- 建议查找的语义问题，而不是强制工具调用；
- 当前使用过的 evidence refs。

Research Manager 可以在预算内多轮调用工具，由 LLM 决定次数，设置总 rounds/tool turns 上限。
停止条件：字段被新证据回答、明确 mismatch/typed gap、或连续无新信息。fulfillment 必须产生新
observation/evidence/concept verdict，不能只在旧 facts 中重做 span overlap。只 resume 受影响
section。

退出条件：一次 RAP full run 至少一个真实 callback 能产生新 evidence 或准确 gap，并局部 resume；
如果仓库确实没有证据，也能以 author caveat/review 完成 candidate，而不是无限循环。

### Stage 6：端到端和四项目验收

只有 Stage 1--5 分别通过后才跑整篇 RAP；RAP 达到基本可读后再跑 EBCAR、LinearRAG、
DyG-Mamba。授权 runtime 支持时四项目可独立并发，最多四路，并监控 waiting、KV cache、OOM、
abort 和 length finish；资源压力高时主动降并发。

## 10. 后续测试计划

测试应围绕产品行为，不以 hash 数量或测试总数作为主要进度。

### 10.1 确定性单元测试

- Manager context 确实包含 recent observation、exact call 和 rejection；
- duplicate rejection 后的 LLM repair 不能重复 exact call；
- concept schema 不暴露内部 IDs；
- repository/author authority 物理分离；
- binder 只能选择 closed fragments，不能 token-overlap 扩张；
- Judge 必须逐字段给 evidence 和非空 rationale；
- partial 不能进入 verified；
- concept 每节只分配一次；
- rewrite transaction 不调用全篇 semantic aligner；
- 最终 reverse validation 仍 fail-closed。

### 10.2 小型真实模型探针

按以下顺序，每步失败先修，不继续跑后面：

1. **Research-only RAP**：一个 feature obligation，8--12 turns；
2. **Concept-only RAP**：使用冻结 facts，生成/判断 concept cards，不启动 Writer；
3. **Writer-only RAP**：使用人工验收过的 frozen concept cards；
4. **Full RAP**：含 callback/resume 和三输出；
5. **四项目**：验证泛化，不使用项目特定答案进入生产逻辑。

### 10.3 产品级验收指标

Research：

- policy rejection 后 exact duplicate call 为 0；
- 每次新工具调用能对应一个缺失语义字段；
- stop 原因是 evidence sufficient、typed gap 或预算下的无增益，而不是 fallback exhaustion；
- trace 能看到模型如何基于上一个 observation 改变查询。

Concept synthesis：

- 每个核心 story node 有少量方法 cards；
- repository cards 无 author purpose、内部 ID 和 harness 元语言；
- 无重复 cards；
- 每个语义字段有精确 evidence；
- 代码中找不到的作者内容仍保留为 caveated author card，不被删除。

Writer：

- 章节顺序与作者 story spine 一致；
- 正文以方法机制而不是文件/函数/调用顺序组织；
- 没有空 section 和模板占位句；
- 数字、公式、qualifier 不漂移；
- candidate 可以完整，verified 可以更短；
- review item 有可编辑 proposed body 和具体问题。

运行：

- 单 section 请求数量有上限；
- 不再出现每次 local rewrite 触发整篇逐句 LLM 验证；
- 没有 SSE 完成后客户端仍等待的假 hang；
- length finish 有明确 owning repair，不能靠无限重试。

## 11. 需要保留的产物

建议保留以下目录直到下一次正式接手完成对照：

- `/tmp/code2paper-codex-rap-product-feature-20260813-p`
- `/tmp/code2paper-codex-rap-product-feature-resume-20260813-q`
- `/tmp/code2paper-codex-rap-product-feature-resume-20260813-r`
- `/tmp/code2paper-codex-rap-writer-replay-20260813-s`
- `/tmp/code2paper-codex-rap-proposition-authoring-replay-20260813-t`
- `/tmp/code2paper-codex-rap-proposition-authoring-replay-20260813-u`
- `/tmp/code2paper-codex-rap-proposition-prepare-20260813-v`
- `/tmp/code2paper-codex-rap-proposition-prepare-20260813-w`

其中 P 是旧 Research 控制平面失败的证据，R 是有价值 proposition 与错误 planning/readiness
并存的证据，S 是 Writer 流水账和请求爆炸证据，V/W 分别代表 proposition 过度放行和过度拒绝。

## 12. 最终交接判断

当前不应继续做以下事情：

- 直接从 W 启动 Writer；
- 为了让 repository propositions 数量变多而放松 evidence gate；
- 为了让测试绿而删除 obligation、过滤失败内容或减少作者 story；
- 再增加一套 hash/proof/closed-ID 合同作为主要修复；
- 立刻跑四项目矩阵；
- 把本地模型质量当成唯一原因。

下一次开发应从 Stage 1 的 fresh research-only proof 开始，然后重做 Method Concept Card、精确
binder 和逐字段 Judge。只有 semantic cards 能准确、简洁地表达 RAP feature mechanism 后，
Writer/Editor 优化才有真实意义。

本轮停止时的最诚实结论是：**Research loop 的关键接口已向真正 Agent 化迈进，运行传输问题
已修；但方法语义提升尚未成立，Writer 产品因此仍不可用。当前代码是中间实验状态，不是完成
状态。**
