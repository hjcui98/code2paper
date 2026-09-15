# Research → Method 交付检查点复核（2026-09-14）

**当前应先修复回放消费旧行为图的问题，并将确定性准入检查前移。最新阻塞再次被误诊为配置缺证；据此启动完整 Research 重跑或扩大配置必查条件，会延长首份 Candidate 的交付路径。节点 A 有部分落地，节点 B 仍未闭环，节点 C 已真实执行三次但正文仍为 0。**

本次复核上一轮指导后的代码变动、A/B 离线检查点、三次 C 回放和当前 Research/计量实现。保留所有既有修改；没有修改生产代码，没有运行新 live，没有覆盖历史证据。新诊断绑定执行前后 415 个生产 Python/入口文件哈希，期间无漂移；新验证为 50 项相关测试通过及下面的独立反例。本报告修订当前根因与完成状态，不替代上位设计或放宽 Candidate/Verified 门。

**1. 进展的实际边界**

| 节点 | 已有实质进展 | 当前不能宣称完成的部分 |
|---|---|---|
| A：分支语义 | 普通 if/else 的跨臂顺序边已在 adapter 中修复；当前图离线重建通过 EBCAR 两机制完整性 | replay 仍加载旧图；嵌套 if、elif、提前 return 尚有反例 |
| B：准入与预算 | 离线报告分列 Candidate/strict；支持可选角色声明、单请求 cap 和提案 tally 的正常保存/恢复 | 提案没有进入累计 run 扣账；角色未声明、保存失败、损坏恢复及 tokenizer 缺失仍可发送；真实 tokenizer 未校准 |
| C：真实正文入口 | 8006 / `qwen38-27b-nvfp4` 已执行三次；Candidate 交接复制缺口与声明式分区排除中止得到修复 | 三次均 exit 2，正文段落 0，当前失败位于 Unified Formalizer admission；没有当前主链 Candidate |

三次运行目录分别为 `/tmp/c2p-nodec-ebcar-unified-20260913-202117`、`…-203506`、`…-205759`。每次 generation trace 汇总均为 37 calls、291,301 input tokens、324,182 total tokens；角色均为 7 次 `method_mechanism_draft_planner` 加 30 次 `semantic_verifier`。三次合计 **111 calls、873,903 input tokens、972,546 total tokens**，正文仍未生成。这些是本次读取的既有运行记录，不是本次审计的新模型消耗。

因此进度停滞既有执行顺序问题，也有验收输入不一致问题。测试通过和 JSON 产物增加证明了局部行为，却尚未证明真实产品入口消费了相同结果。

**2. P1：真实回放没有消费已修复的行为图**

三次 fresh root 的 `artifacts/behavior_graph_v1.json` 均与冻结 Run E **逐字节相同**，SHA-256 为 `11f301bc7bb1470e2c4188d2d87cbd878f401f1f2017cb0ba843c85ce19182ed`。

两条入口的差异明确存在于代码：

- [离线矩阵](../scripts/run_unified_ten_project_offline_matrix.py) `_rebuild_current_context_set` 第 450 行显式传 `behavior_graph=None`，由当前 adapter 重建图。
- [生产 Writer](../src/code2paper/agentic/publication_method_writer.py) 第 2030 行传入 `repo_ctx["behavior_graph"]`；该值由 `_load_repository_authoring_context` 第 15990 行附近从复制的旧 JSON 加载。
- [机制编译器](../src/code2paper/agentic/mechanism_context_compiler.py) 第 1970 行附近仅在 `graph is None` 时调用当前 adapter。换了代码、重新生成 source manifest，并不会自动改变已传入的历史图。

第三次回放中两处 unresolved 的 `activation_basis_ids` 和 detail `mismatch_reason` 都明确写着 `path_polarity_conflict:self.cfg.use_dedicated_attention`。独立捕获的 resolver 实参为：`explicit_status="unknown"`、`guard=""`、`config_bindings=[]`、`reachable=true`。显式冲突在配置解析之前已经确定结果，实施记录中的“因为没有配置定义，所以 else 未知”没有解释这条实际因果链。

本次通过生产 Writer 的 loader 读取第三次回放输入，做了一次有界对照：facts、claims、配置、作者输入、symbol index、源码分区和 verified source reader 全部相同，只切换历史图消费与当前 adapter 重建。

| 相同第三次回放输入 | 机制 `9773…` | 机制 `f6cf…` |
|---|---|---|
| 传入复制的历史图 | 125 operations，0 unresolved | 185 operations，2 unresolved，完整性失败 |
| 请求当前 adapter 重建图 | 157 operations，0 unresolved | 217 operations，0 unresolved，完整性通过 |
| operation 集合差异 | 新增 32、删除 0 | 新增 32、删除 0 |

配置文件仍包含原来的 unresolved claim，未补值、未升为 actual、未删事实或操作，两个机制却已通过。因此当前直接工作应是**统一图来源与派生身份**。配置的实际取值/覆盖链仍可能是后续事实问题，但不能继续冒充这两处当前结构失败的直接原因。

交付修复应让 offline 与实际入口消费同一套按冻结源码派生的当前图/上下文。保留历史 Research 图作原始观察，记录新派生图的 snapshot、producer 版本、输入/输出 digest 和必要的旧新关系；沿既有重建/修订合同处理绑定。不能仅为过门在 Writer 中悄悄丢弃历史图、过滤 operation 或跳过冲突校验。`--rebuild-authoring` 也应明确覆盖哪些派生层，不能让选项名称掩盖图仍旧的事实。

证据：[graph-input-control.json](../.tmp/c2p-delivery-review-20260914/graph-input-control.json)。此对照证明当前结构门的原因与修复方向，**没有证明完整 Candidate、公式或最终反向验证已经通过**。

**3. P1：确定性失败应在昂贵的重建调用之前暴露**

[run_authoring_replay.py](../scripts/run_authoring_replay.py) 第 2057 行先执行 `_rebuild_derived_authoring`；该函数创建 draft planner、编译 argument briefs、运行 facet semantic verifier。到第 2189 行才进入 `run_publication_method_writer`，随后进行 Research/源码/机制准入。

这解释了为什么三次都消费 37 次正文前调用，再分别发现 handoff 缺失、source partition 处理、旧图冲突。上述问题可以在确定性输入准备阶段发现。当前“135 页 / 102 次调用的离线 Candidate pass”没有覆盖真实 replay 在前置重建阶段的执行成本和输入选择。

最小推进方式：在 fresh root 的冻结输入复制/身份校验与当前图重建完成后，运行与 Writer 共用的确定性 Candidate 预检，再进入需要模型的 authoring 重建。后续依赖新生成内容的门仍在其真实阶段执行；前移检查不替代后续门。将上游 planner/verifier、组织提案及 Formalizer/Writer/Realizer 的开销明确归入适用预算，不能把前置 37 calls 遗漏在“整次 authoring 总额”之外。

修复接线后，先用模型调用必抛异常的离线探针走实际 replay 准备入口，证明它使用当前图、Candidate 预检通过且模型调用为 0。原有缺 handoff、坏源码或旧图不兼容反例，应在任何模型发送前给出 typed 失败。这样才有理由启动下一次受控正文运行。

**4. P1：节点 B 的“收尾”结论超出了实现**

当前 [proposal_call_accounting.py](../src/code2paper/agentic/proposal_call_accounting.py) 的 meter 从 envelope 取了 per-request cap，但没有承接 `max_calls_by_role`、run 总额与其他阶段的已用/预留量；[narrative_organization_proposal.py](../src/code2paper/agentic/narrative_organization_proposal.py) 发送前也只比较单次输入大小。`unified_invocation_ledger.py` 没有消费这份提案 tally。

本次用独立临时目录与假 transport 验证，全部真实模型调用为 0：

| 条件 | 当前观察 | 应有边界 |
|---|---|---|
| 没有声明提案角色 | 创建 cap=0、planned/reserved=0 的 meter，仍发送 1 次 | 缺少必要预算不能等于不限额 |
| envelope 声明最多 1 次、run input 400；单次 cap 2048 | 连续发送 3 次，测量合计 735 | 累计调用数与总额均应在发送前约束；此探针测试 caller 边界，不冒充完整 Writer admission |
| durable 写入抛 `OSError` | 异常被吞，仍发送 1 次 | 无法保存 started 时不得启动受账本约束的请求 |
| 恢复文件不可解析 | 返回 None，按新账本执行并覆盖，仍发送 1 次 | 保留并报告损坏状态，不能丢弃未结算预留 |
| 声明 model tokenizer，未提供 tokenizer | meter=None，仍发送 1 次 | 缺测量时拒绝受预算约束的发送或走已批准的组织回退路径 |

第三次真实运行的 envelope 只有 binder/formalizer/realizer/writer 四角色，使用 `conservative_utf8_bytes_div_4`；profile 没有启用提案 extra role。21 项计量测试以及新增可选参数证明了部分机制，不能证明该实际 profile 上提案已有 run 级约束或真实 tokenizer 校准。

下一片按“发送是否会被正确拒绝”验收：共用 run 预算权威，纳入累计 calls、已花费、预留与旧 attempt 未结算额度；使用原子 durable started/settlement，损坏或写入失败保留 typed 阻塞；绑定 run/revision/envelope/model 身份。修 schema、计量文件和 summary 都只服务这个闭环，不再把保存一份 tally 记为完成。未就绪的可选组织提案应走其既有明确回退合同，不能以未声明角色或无 meter 状态调用模型。

**5. A 的通用回归范围不足，新增配置硬条件也需要收窄依据**

分支修复的 `_arm_position` 只返回第一个包含该节点的分支臂。对嵌套分支，内层两个互斥臂会同时匹配外层同一臂，原错误仍能出现。新添加的 join 也无条件把 arm 末节点连到后继，包括已经 return 的节点。

独立源码 fixture 的结果为：普通 if/else 冲突 0；**嵌套 if/else 冲突 2；elif 冲突 1；提前 return 仍有 1 条 NEXT_CONTROL 出边**。所以 A 可记录 EBCAR 普通分支改善，但不能记录完整通用验收。修复需保留所有祖先分支归属、正确选择当前语句块汇合点，并尊重终止控制流；完成既定嵌套/elif/return/真实矛盾反例即可，不扩成无界 CFG 项目。

当前又新增 `branch_configuration_evidence_requirements`，把配置需求直接加入 `all_targets_resolved` 之后的终态条件。这不是已定位旧图错误的修复。带明确条件的可支持事实与要求证明某次实际配置选路的事实，应按原有 typed target/qualifier 区分，不能因误诊统一增加实际取值前置。

该新函数还仅用配置键最后一段判断“已解决”：探针中 `self.cfg.mode` 的需求被无关 `other.cfg.mode` 的 default claim 消除，缺少访问主体、scope 和来源绑定。应按确切访问与证据关系产生/解除需求，保留原有事实与作者约束；在进入新 Research 运行前先修这项识别，避免增加无效检索或错误关闭。

证据：[results.json](../.tmp/c2p-delivery-review-20260914/results.json) 的 `branch_regressions`、`accounting_controls`、`configuration_identity_control`。这些是有界反例，未据此放宽任何现有 gate。

**6. 下一步的执行顺序与退出条件**

1. **一个交付切片完成“实际入口使用当前图 + 确定性预检前移”。** 复用同一输入准备/编译入口，处理必要的派生图身份，补既定分支回归；以第三次真实回放输入做零模型端到端预检。交付当前图 digest、operation 集合变化、Candidate 各阶段准入和模型调用 0 的证据。直接根因未消除前，不再发起完整 Research 重跑。
2. **完成已确定的 run 发送边界。** 用本次反例验收累计预算、未声明角色、保存失败、损坏恢复、tokenizer 缺失；在实际 8006 profile 或明确冻结的合法修订 profile 上验证。允许沿既有组织回退合同处理不可用的可选提案，仍如实记录 feature 状态；不把这说成提案预算实现完成。
3. **执行一次受控当前主链 authoring。** 使用新输出目录、既有授权及 live admission 条件，保留 health/models/queue/KV 与请求证据。以 Formalizer 实际完成、Writer 产生实质段落、最终完整 Candidate 为阶段产物。发生真实新门时只处理所属阶段，沿有效 checkpoint/派生身份恢复，避免无变化地重算全部前置模型任务。

三条 strict partial、真正的配置选择证据、R10 扩展、其他项目矩阵继续保留，按真实消费者需求推进。此次对照已经证明旧配置输入可以解除当前两个结构失败，不能继续要求用户在“完整 live Research”与“配置续跑”之间选择来绕过图来源问题。

进度记录应改为：A“普通分支修复已落地，入口/嵌套回归未闭合”；B“单次 cap 与正常 tally 持久化已落地，累计 run 与异常恢复未闭合”；C“三次真实入口运行，正文 0，直接阻塞为历史图仍被消费”。这些边界明确后，下一次检查只需看实际消费图是否更新、预检是否前移、累计预算是否拒绝反例、正文是否增加。

**7. 复核身份与验证记录**

HEAD 仍为 `84371e4fee974071a580d7832af0ac14908c2d4b`，使用既有 dirty worktree；不能以 HEAD 单独代表当前实现。完整证据索引见 [evidence-index.json](../.tmp/c2p-delivery-review-20260914/evidence-index.json)，含三次运行摘要/输入哈希、此次诊断代码与结果哈希。

本次新执行：

```bash
python -m pytest -q tests/test_agentic_branch_control_relations.py tests/test_agentic_branch_configuration_requirements.py tests/test_agentic_proposal_call_accounting.py tests/test_agentic_replay_execution_record.py -p no:randomly
# exit 0；50 passed in 1.96s

python .tmp/c2p-delivery-review-20260914/review_probes.py
# exit 0；上文各有界反例与相同输入图重建对照；真实模型调用 0；生产源码无漂移
```

诊断脚本首次运行曾因 loader 字段映射错误在编译前退出；修正该审计脚本后得到上面的完整 exit 0 结果，未改生产行为。未重复全量静态，未将旧 3440/后续局部测试数加总为当前整体验收。

另需保持证据不可变：上一轮审计的 `branch-control.json` 曾被实施侧用新代码重跑覆盖，实施记录已明确注明。本次使用独立目录；历史报告/哈希仍只说明当时绑定的结果，不应覆盖后再追认为同一次验收。README 中旧“修复未落地”及实施记录中“A/B 完成、C 是配置缺证”的现状解释，以本次证据为准。
