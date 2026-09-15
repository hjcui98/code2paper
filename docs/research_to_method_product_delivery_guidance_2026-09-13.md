# Research → Method：产品主链诊断与推进指导（2026-09-13）

**执行顺序需要调整。当前最直接的阻塞已定位到分支图与机制编译器之间的语义错误；应先修这一处，验证 Candidate 准入，再完成真实调用计量并取得正文。继续把五个 strict 报错当成同一个补证任务，会延长交付路径。**

本次针对当前代码、冻结 Run E、最新离线报告、补证探针及 R10/计量实现做独立复核。没有修改生产代码、冻结输入或既有运行产物，没有调用模型或 live API。新增诊断与证据位于 [本次审计目录](../.tmp/c2p-product-path-audit-20260913/)。这是执行优先级与根因解释的修订，不替代总体架构、Writer 设计、09-08 Unified 结构门或现有 Candidate/Verified 合同。

**1. 实际推进到了哪里**

| 层次 | 当前证据 | 对产品交付的含义 |
|---|---|---|
| Digest、attempt、执行账本、R10 作者约束与修订边界 | 已有修复和相应回归；本次 R10/计量相关测试 52 passed | 可靠性有实质进展；不能据此宣称正文质量或交付完成 |
| Research → Candidate handoff | `eligible`；重认证失败为空；`candidate_failure_codes=[]` | Candidate 的 Research 前置条件已经满足 |
| Strict Research | 三条 `partial_without_terminal_gap` 仍在 | 继续保留 strict 未通过的结论；不把它们额外变成 Candidate 前置条件 |
| Mechanism completeness | 两机制分别 157/217 个 operation，6/2 个 `explicitly_unresolved` | 这是当前 Candidate 主链仍需解决的两个结构门 |
| Unified 编译 | 887 atoms、131 页、4 worksets、三阶段计划 65/18/18，`failure_details=[]` | 证明计划可编译；各 phase 的 admission 状态仍为 fail，不能称三阶段执行通过 |
| 实际正文 | 本轮补证和修订后未找到新的 EBCAR authoring live/Candidate；冻结 Run E 仍是 `not_started` | 新发现尚未形成可阅读、可验收的产品产物 |

历史完整静态结果 `3440 passed, 3 skipped` 来自实施记录，本次没有重新执行全量套件。仓库其他日期/项目的 Candidate 不能替代这一条主链的验收。

**2. 新定位的直接根因：合法 else 被制造为双极性冲突**

本次从未处置 operation 反向追到了 active-path resolver 的实参，得到如下因果链：

```text
Python AST 遍历顺序
  → NEXT_CONTROL 把 if 真分支末尾连接到 else 开头
  → dominance 仅检查是否位于整个 if span 内
  → 真分支条件沿顺序边传播进 else，同时收到 FALSE_BRANCH
  → path_polarity_conflict → explicit_status=unknown
  → operation_disposition_unresolved → mechanism completeness 拒绝
```

代码定位：

- [python_behavior_adapter.py](../src/code2paper/agentic/python_behavior_adapter.py) 的 `add_sequential_control_relations`（1325 行附近）通过 `zip(self.nodes, self.nodes[1:])` 连接词法遍历邻居。其“可执行顺序”假设对互斥分支不成立。
- [mechanism_context_compiler.py](../src/code2paper/agentic/mechanism_context_compiler.py) 的 `_branch_dominance_guards`（478 行）以整个 if 的 span 约束传播，该范围同时包含两个分支。
- 同文件 `resolve_typed_guard`（2035 行）将冲突明确写为 `unknown`；`resolve_active_path_status`（348 行）先消费显式状态。这些调用的 `config_bindings` 为空。因此继续补配置值不能直接消除已经生成的冲突。

具体八处：6 个位于 `transformer_encoder_hybrid_attention.py:160`，冲突条件为 `return_attention`；2 个位于 `ebcar_dedicated_attention_model.py:171–174`，冲突条件为 `self.cfg.use_dedicated_attention`。两个分支在冻结源码中都是普通合法 `if/else`。

本次做了有界因果对照：用已校验源码的 AST 分支范围证明互斥性，**仅在内存中的 dominance 遍历排除跨互斥分支的 NEXT_CONTROL**；没有删除 operation、fact、claim，没有直接赋予 active 状态，没有修改完整性检查。

| 对照 | 原始代码结果 | 诊断干预结果 |
|---|---|---|
| 普通 `if flag: value=1; else: value=2` 最小例 | 1 个伪极性冲突 | 0 个冲突，恢复分支条件 |
| 机制 `9773…` | 157 operations，6 unresolved，完整性失败 | 仍为 157 operations，0 unresolved，完整性失败列表为空 |
| 机制 `f6cf…` | 217 operations，2 unresolved，完整性失败 | 仍为 217 operations，0 unresolved，完整性失败列表为空 |
| 人工明确赋予同节点正负两条 typed branch 边 | 应拒绝 | 仍识别冲突，没有被过滤规则掩盖 |

冻结重建中只识别到两条相关跨分支边：掩码分支 `165–167 → 172`，attention 分支 `158 → 160`。恢复后的相关 operation 为带准确否定守卫的 `conditional`，没有被强行提升为无条件 `active`。

证据：[branch-control.json](../.tmp/c2p-product-path-audit-20260913/branch-control.json)、[explicit-conflict-control.json](../.tmp/c2p-product-path-audit-20260913/explicit-conflict-control.json)、[对照脚本](../.tmp/c2p-product-path-audit-20260913/branch_dominance_control.py)。**这是因果诊断，不是已落地的生产修复，也没有证明完整 Candidate authoring 已通过。**

正确修复应让控制边/支配推导具有分支身份与可信边界，包含源码路径、所属符号、互斥分支及汇合语义。不能仅按行号删除看似冲突的边，不能删除真实冲突处理；嵌套 if、elif、汇合、提前 return 等必须得到有界验证。优先修生产者及其必要消费约束，暂不扩展成全语言 CFG 重写项目。

**3. 当前执行中三个需要纠正的判断**

第一，区分 Candidate 与 strict。最新原始报告的 `gate_mode=strict`，所以各阶段列出五个失败码；但同一报告的 Candidate Research gate 已通过。[publication_method_writer.py](../src/code2paper/agentic/publication_method_writer.py) 的 `_candidate_lane_research_failures`（1232 行）只在 handoff 认证与既有资格条件满足时处理对应 partial。应按该真实入口重新验收，而不是要求 strict 全绿才验证 Candidate。Candidate 仍必须遵守结构、证据、措辞及完整性规则；这不是将 partial 升为 fully supported。

第二，正向补证与负结论采用不同结束条件。[补证清单](research_evidence_checklist_2026-09-13.md) 原本允许“可引用正向证据进入 claim/fact 编译”；后来补证报告却泛化成“frontier 未关闭，所有条目保持 unresolved”。可信正向证据仍需 snapshot、owner、精确 span、关系及 claim 绑定，但不必先关闭所有无关搜索命中。不存在/不支持等负结论才需要相应搜索范围的完整关闭证明。配置默认值还须与实际入口、覆盖链和分析场景区分；不能以 YAML 的 `True` 推断某次实际执行必走该分支。

另外，本次独立复现了一个关闭回执障碍：同 scope/query 先 `top_k=1` 截断，再 `top_k=10` 完整搜索并读完，`unread_candidate_ids=[]` 仍得到 `truncated=true`。原因是 [research_execution_ledger.py](../src/code2paper/agentic/research_execution_ledger.py) 第 961 行对全部历史执行取 `any(record.truncated)`。所以“再读完 33/6 个命中就能关闭”并不充分。负证据路径后续需要可认证的查询覆盖/替代关系；不得清空历史截断标志或换账本冒充关闭。这个问题不应挡住有效正向补证，也不应排在已定位的分支错误之前。

第三，“7/9 target resolved”只证明合成池中的谓词可匹配。[close_remaining_targets.py](../.tmp/c2p-gap-evidence-20260913/close_remaining_targets.py) 将五个文件的事实放入合成 obligation，未执行真实分题 packet → claim → promotion → handoff。独立复核发现，初始 dense retrieval 的 top-k 目标匹配到了“按 query_id 整理预处理数据”以及“末端 reranker 对 similarities 排序”的 SORT facts；所需 semantic slot 仍未匹配。它们不能证明初始检索已经实现。`src/utils.py` 的 top-k 是 nDCG 辅助逻辑，`main.py:34` 的 filter 是 warning filter，也不能按关键词当成 passage retrieval/filtering 事实。

因此应保留这些结果为检索线索，撤回“七个真实缺口已关闭”或“剩余问题全是读取覆盖不足”的推断。对每项正向补证，只统计生产 obligation、owner 和精确语义下真正消费的事实及其状态变化。

**4. 计量已有代码，但还不是可靠的调用预算闭环**

`proposal_call_accounting.py` 已实现 caller 计量行与 tally，Writer 也会在 narrative plan 返回后写 durable 产物。这是有效进展，剩余应收敛为实际发送边界的一次接线工作：

- 当前 Writer 构造 meter 时没有传 tokenizer；envelope 声明 `model_tokenizer` 时工厂返回 `None`。如实记录未测量有助诊断，但不能替代受预算约束的执行。
- `begin` 位于内存，plan 返回后才落盘；当前产品写入分支还有 `except Exception: pass`。已有 tally 保存/恢复测试不能证明真实调用开始后、plan 返回前进程中断仍有 durable started 记录。
- 尚未将这些真实请求的预留/发送前扣账计入同一 run 的预算，不能以多了一份 JSON 宣称闭环完成。

当前静态计划本身已有 **101 次主调用、1,938,180 input tokens**，对 2,000,000 上限只剩 61,820（约 3.1%）的计划余量。65/18/18 不能解读为三次调用，`max_attempts=2` 也不表示总预算覆盖两倍尝试；组织提案、实际 chat template/schema、失败重试和残留未结算预留都需要纳入。这个规模有实际运行成本，不能在未校准前直接启动完整多项目矩阵。

这些数字绑定修复前的离线计划；分支修复后必须重新编译实际工作集与调用计划，沿既有 revision 谱系核算，不能直接复用上述额度作为新计划的实测结果。

应复用现有统一 run 预算与 attempt 身份，覆盖真实序列化请求、model/tokenizer 身份、发送前预留、durable started、成功/失败结算、retry/resume；缺少必要计量或持久记录时在发送边界明确阻塞。附加诊断 tally 可以保留，不要再新增一套平行权威账本，也不要伪造 page/workset 身份以塞入计划。

审阅期间实施侧又在 `autonomous_method_agent.py` 增加了 tally → run summary 展示，实施记录称为“路线 2：计划外但受控”。这改善了可见性，但总额中缺少这些调用时，不能证明它们受 run 预算控制。**本指导选择“纳入统一预算”作为下一片的验收方向**：现有四角色合同如不能表达提案调用，应为实际提案角色/调用类别补充必要的预算与调用身份合同，记录这项局部修订并验证现有四角色兼容性。单独展示不作为 run 并账完成，也不再以需要另选路线为由连续增加汇总层代码。

**5. 下一步只沿三个可交付节点推进**

| 顺序 | 负责范围与动作 | 必须交付的结果与停止条件 |
|---|---|---|
| A：修真实结构根因 | `python_behavior_adapter.py` 与 `mechanism_context_compiler.py` 的分支控制关系/支配推导 | 普通 if/else 不再误报；嵌套、elif、汇合、提前 return、真正矛盾及缺少支配证据的反例成立；冻结 Run E 157/217 operation 数不变，8 unresolved 消除，两个 completeness 失败消除。若仍有 unknown，交付其 resolver 实参和 typed 来源，按真实原因继续修 |
| B：完成 Candidate 入口与调用准备 | 生产 Writer 的 Candidate handoff 认证、Unified admission，以及计量真实入口接线 | 同一代码/输入重算 Candidate 模式的各阶段 admission；strict 三项单独记录。真实 tokenizer 校准、提案计量与 run 扣账共用口径，验证“开始后中断再恢复”和超额发送前拒绝。若规划超额，沿现有合法计划修订/预算合同处理，不删 obligation 或伪造实测 |
| C：取得第一份当前主链正文 | 在适用授权范围内，用当前入口与全新输出目录执行一次受控 EBCAR authoring | 记录 runtime health/models、模型身份、队列/KV 状态；产出所有必需章节的实质正文、对应证据/公式/qualifier/反向验证与质量结果，或第一处实际阻塞的请求、响应、失败码及所属阶段。单机制 smoke 只算诊断；完整 Candidate 才算该交付节点完成 |

A、B 不以 strict 三项清零为共同前置；Research 定向诊断/计量校准只需满足自身的条件，不能要求先通过依赖它们的 Writer gate。C 不授权发布、默认切换、D5 完成或 Verified 标记。遇到真实新阻塞按所属阶段有界修复，不重复未改变输入和实现的整轮回放来等待偶然成功。

R10 不应因为旧文档的“暂缓”继续冻结：当前已经进入修订循环，作者约束、graph/agenda 同步和额度边界有修复证据。保留并使用这些成果；首份 Candidate 前，只继续修复它实际触发的问题。跨机制排序、新修订策略等扩展留待主链产出后的证据决定，不再把“R10 全部功能完成”设为交付前置。

三条 strict partial、真实配置场景、负证据 frontier 可关闭性仍是保留任务。推进正向补证时，每片必须把证据接入真实 packet/事实/claim 与 revision 绑定的 agenda、promotion、handoff，而非只生成新探针。涉及 author intent 的修订必须守住作者约束，不得为了过门重写问题、缩小目标或把初始检索替换成最终排序。

**6. 改变进度记录方式，结束持续拆片却不交付的循环**

当前变慢的直接表现是：补证不断增加探针与文字，五个离线失败码不变；计量不断增加结构与产物，实际发送/恢复路径尚未闭合；静态测试在增加，正文调用仍未发生。前几次复核也过度围绕新增边界缺陷排队，没有持续把 Candidate 的第一处阻塞作为执行顺序的锚点。这次应以因果对照和产品路径重新排序。

以后每片只报告三个问题：**生产入口消费了什么变化；哪一个当前阻塞消失；哪个可阅读或可验证产物因此新增。** 没有变化也应记录具体阻塞和证据，不再以“又完成一轮探针/全量静态”替代产品推进。

验收冻结使用新的目录，一次命令绑定代码状态、输入身份、原始报告和派生汇总，执行前后核对代码没有漂移。本次曾确认 `r10-summary.json` 的 24 个文件与原始报告摘要匹配，随后实施侧又修改了 `autonomous_method_agent.py`；最新核对以本次 `verification.json` 为准，不把运行中的修改追认为旧报告已覆盖。其固定清单也没有覆盖 `python_behavior_adapter.py`、`mechanism_context_compiler.py`、`unified_context_compiler.py`、`proposal_call_accounting.py`，而事后给旧报告补当前文件哈希不能证明该报告执行时的代码状态。应补齐采集方式，而非反复人工刷新摘要。

针对上述实际改动运行相关测试；到 A/B 集成节点再做所需全量静态，随后进入受控产品验证。保留门禁，不将无关边界扩展成新的串行前置，不先扩到十项目，也不靠增加报告数量推进。

**7. 本次证据与复现**

- 基线 HEAD：`84371e4fee974071a580d7832af0ac14908c2d4b`，包含既有大量未提交修改；HEAD 单独不代表本次代码身份。
- [results.json](../.tmp/c2p-product-path-audit-20260913/results.json)：Candidate/strict 分列、未处置 operation、resolver 实参、合成 target 的实际 witness、frontier 对照；绑定 415 个生产 Python/入口文件哈希，执行前后无漂移。
- [branch-control.json](../.tmp/c2p-product-path-audit-20260913/branch-control.json)：最小 if/else、两条跨互斥分支边及冻结重建对照；相关源码哈希与本次主审计一致。
- [verification.json](../.tmp/c2p-product-path-audit-20260913/verification.json)：命令、结果、产物摘要与末尾代码状态核对。

诊断完成后、撰写指导期间，其他实施更新了 `autonomous_method_agent.py` 的 summary 展示和相关测试；本次 52 项结果绑定更新前的测试集，不含随后新增测试。分支 adapter、机制编译器及本次因果实验直接依赖的代码未发生对应变化；不因此重跑全部无关测试，也不宣称新汇总路径已经由本次验收。

本次新执行的针对性验证：

```bash
python -m pytest -q tests/test_agentic_research_revision_contract.py tests/test_agentic_revision_proposal_loop.py tests/test_agentic_proposal_call_accounting.py -p no:randomly
# exit 0；52 passed

python -m pytest -q tests/test_agentic_mechanism_evidence_closure.py::test_graph_branch_dominance_reports_polarity_conflict tests/test_agentic_mechanism_detail_compiler.py::test_polarity_conflict_keeps_operation_unresolved -p no:randomly
# exit 0；2 passed

python .tmp/c2p-product-path-audit-20260913/audit_product_path.py
python .tmp/c2p-product-path-audit-20260913/branch_dominance_control.py
# 两个诊断均 exit 0；模型调用 0；结果是诊断证据，不是 production fix/live 验收
```
