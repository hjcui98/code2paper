# Research → Method 第三次执行中方向复核（2026-09-13）

结论：保留当前架构与修复成果，调整下一步的验收重点。R7 multi-section 的**注入提案消费**已成立；
默认产品入口的自主组织尚未接通。R9 执行账本完整性和 R5 条件判定仍存在可复现的错误授权边界，
R6 还遗漏了同一 invocation 在不同 revision 下的未结算预算。先补这些边界，再推进定向 Research
补证和真实计量；R10 继续暂缓。

本报告承接[第二次方向复核](research_to_method_repair_direction_review_2026-09-13.md)及
[统一执行计划](research_to_method_unified_repair_execution_plan_2026-09-12.md)。本轮仅审查与离线诊断，
没有修改生产代码、已有测试或执行计划，没有启动模型、live、提交或合并。

## 1. 本次核对的状态与证据

代码 HEAD 为 `84371e4fee974071a580d7832af0ac14908c2d4b`，工作树保留已有未提交修改。
[R9 摘要](../.tmp/c2p-unified-repair-20260913-r9/offline/r9-summary.json)列出的 **17 个生产文件
sha256 全部与本次读取的代码相符**，本次探针运行期间这些文件未变化。这解决了上次“旧离线摘要
不能直接绑定当前修改”的证据身份问题；结论限于摘要列出的文件。

用户最新执行回报为 `3371 passed, 3 skipped`，并报告 compileall、git diff --check 通过。
本次没有重跑全量 pytest；以下新结论来自独立探针与当前代码，不把历史全量计数当作边界验收。
`.agent/implementation.md` 的早先全量记录仍为 3366，收尾段写“见下”但未附 3371 的具体输出，
后续应补上最终命令、日志位置与该次代码身份，避免两份状态口径长期并存。

| 项目 | 当前证据支持的结论 |
|---|---|
| R7 multi-section 提案消费 | 本次直接执行合法提案与非法提案回退两个现有测试，均通过；合法提案能改变 detail 分摊 |
| R7 单机制段落提案 | 本次直接执行合法提案消费测试，通过 |
| R5 上次五条条件反例 | 本次全部被条件约束函数拒绝，旧反例已修复 |
| R9 原来的调用者自填搜索回执 | 已改为执行层 ledger 派生、工具接收 receipt ID；该方向应保留 |
| R7 分页、章节 owner 与 R8 差异传播 | 当前代码及绑定摘要包含第二次复核后的修正；本次没有重新完成它们的全链验收 |
| 冻结 Run E source / archive | source pass，887 atoms，archive `sha256:6b2ec29d…` |
| active-path 原始混合状态 | `unknown_core_active_path_count=0` |
| 工作集与计划 | 131 页、4 worksets；Formalizer / Writer / Realizer 为 65 / 18 / 18 个计划调用 |
| 准入 | 两机制 `operation_disposition_unresolved`，strict lane 三条 partial 缺终态证明，仍为 fail |
| Candidate Research handoff | eligible，重验失败为空；只证明该 handoff 可接受 |
| 正文及真实运行 | 离线报告 `model_calls_allowed=false`，未新增 Candidate / Verified 正文生成证据 |

`failure_details=[]` 与上述五个 `failure_codes` 同时存在。代码编译链修通、Research handoff eligible、
完整 authoring admission 通过，必须分别报告。1,938,180 / 2,000,000 的差额 61,820 仍是计划余量，
没有真实 tokenizer、完整请求与重试消费的计量证明。

## 2. 本次发现

### P1-A：执行账本会丢掉已经发生的搜索，重新授权负结论

位置：[research_execution_ledger.py](../src/code2paper/agentic/research_execution_ledger.py)，
`record_tool_execution` 第 349–357 行、`iter_execution_records` 第 474–482 行；
真实调度入口为 [research_tools.py](../src/code2paper/agentic/research_tools.py) 的
`execute_research_tool`。

两个独立项目中立 fixture 都经过真实搜索、读取和 gap 工具：

1. 先执行 `forward` 搜索并读完所有结果，得到已关闭的回执。再执行 `train_loop` 搜索，发现两个
   未读结果，此时前沿正确打开。将**探针自己的**第二次搜索账本文件损坏后，读取器捕获异常并
   `continue`，未读候选从 2 变为 0；原先回执重新通过认证，gap 工具写出
   `unsupported_with_scoped_evidence`、`negative_evidence_authorized=true`。
2. 使用相同 `tool_call_id` 执行不同查询，第二个搜索实际成功并发现相同的两个新候选。
   记录器只因文件已经存在就返回旧记录，未核对请求和结果；账本记录数维持 3，queries 仍只有
   `search_code:forward`。新候选没有入账，gap 工具再次授权负结论。

因此“回执由执行层产生”还不足以证明执行前沿完整。这里已到达负证据生产边界；本次没有声称
最终 Verified 被穿透，也没有损坏任何既有运行产物。

修复要求：账本读取失败必须产生可传播的未决/完整性失败；同 ID 的幂等重放必须验证 snapshot、
obligation、完整请求身份及观察摘要，相同 ID 对应不同执行内容应明确拒绝。已有记录解析失败不能
返回一个被 dispatcher 当成功忽略的 `None`。关闭证明应绑定可检查的执行清单，重启或恢复不能因
记录缺失而缩小已知 frontier。序列化验证也应核对已有 digest，不能静默重算并覆盖不匹配的摘要。

验收应包含：新增未读结果 → 旧回执失效 → 文件损坏后仍不授权；相同 ID/相同请求的合法重放；
相同 ID/不同请求的拒绝；上述状态经过 checkpoint、terminal、handoff 后仍保持一致。

### P1-B：条件解析仍丢失语法，未知表达式被当成已证明

位置：[condition_structure.py](../src/code2paper/agentic/condition_structure.py)，
第 128、146、211–219、695–698 行；消费者为
[publication_transaction_contract.py](../src/code2paper/agentic/publication_transaction_contract.py)
的 `_witness_condition_and_polarity_satisfied`（第 638 行）。

| 声明 | witness 中的条件 | 本次消费者结果 |
|---|---|---|
| `x * y > 5` | `x / y > 5` | 放行 |
| `x + y > 5` | `x - y > 5` | 放行 |
| `!alpha` | `alpha` | 放行 |
| `alpha` | `When beta or when alpha, ...` | 放行 |
| `x.shape[0] > 0` | 完全相同的 `x.shape[0] > 0` | 拒绝 |

第一条取 `x=4, y=2` 即可证明不等价：乘积 8 满足阈值，商 2 不满足。
词法扫描使用 `finditer`，没有要求消耗全部输入；`*`、`/`、部分符号未进入结构，`!` 等符号被丢弃。
条件片段枚举又允许从内部 `when` 取后缀，并跳过包含该后缀的更大条件，造成额外 OR 分支被忽略。
相反，属性与下标里的标点会破坏合法 guard 的解析。

修复方向应收紧为“完整可解释的条件结构”，不能继续逐个补反例词表。首先检测并拒绝未消费语法，
保留完整表达式的作用域；代码侧尽量复用已有源语言 AST/结构化 predicate，保留算术运算、
属性/索引、比较与否定。自然语言 witness 的判定继续走受约束的语义绑定路径，无法证明时返回
拥有者修复；不得把词集合或偶然匹配的后缀作为等价证明。回归同时覆盖错误放行与合法 guard 误拒。

### P2-A：R6 对同 ID 的旧未结算 attempt 使用了新计划额度

位置：[unified_invocation_ledger.py](../src/code2paper/agentic/unified_invocation_ledger.py)
第 391–400 行。

本次通过真实 plan 登记和 started marker 写入接口构造：旧计划同一 invocation 额度为 900，
新 revision 降为 100，旧 attempt 尚无 completed receipt。计量函数返回：

```json
{"planned_input_tokens": 100, "plan_source": "current_plan", "plan_digest": "sha256:plan:old"}
```

记录仍承认它属于旧 plan，却少预留 800。此前“旧 ID 不在新计划里”的孤儿修复有效，但这里
`if matched` 在核对 started plan digest 前采用当前额度。同 ID 跨 revision 并非天然禁止：
`unified_context_compiler.py` 第 3193 行的 Formalizer repair ID 由机制与 obligation 组成，
不包含修订后的页面内容。

应先按 started marker 的原始 plan digest 计量；仅在与当前 plan 身份一致且验证通过时使用当前
额度。原计划缺失或损坏仍应阻塞。验收同时覆盖 ID 消失、ID 保留但额度升降，以及合法恢复。

### P2-B：R7 提案消费已实现，产品默认路径仍未请求提案

位置：[autonomous_method_agent.py](../src/code2paper/agentic/autonomous_method_agent.py)
第 3654 行显式传入 `architect_proposal_caller=None`；
[publication_method_writer.py](../src/code2paper/agentic/publication_method_writer.py)
第 17492 行的 wrapper 继续原样透传。
[method_architect.py](../src/code2paper/agentic/method_architect.py) 没有利用 `llm_config` 构造默认 caller，
只有 caller 非空时进入新提案分支。

本次在该产品 wrapper 上提供上下文及非空 `llm_config`、不注入 caller，结果为
`proposal_status=not_requested`、无 `proposal_applied`；三个注入 caller 的合法消费/非法回退
对照测试均通过。因此最新收尾报告关于**消费函数**的描述成立，“自主组织已完成”的范围仍需限定。

这直接对应统一执行计划 §12.2 的“接通现有 proposal caller”。下一片应把预算内的意图、阅读问题、
章节角色与 detail 语义投影送入真实适配器，并保留封闭 ID 校验；当前四个位置参数只有 ID/角色
列表，本身不足以表达科学组织依据。首轮 typed failure 应作为 repair 输入传回拥有者，记录
request/response、尝试次数与消费结果。当前两次调用使用相同参数，没有传回失败诊断。

先通过默认产品入口截获实际请求，再证明获准提案改变的 detail 归属进入真实 Writer request。
跨机制章节顺序可以继续明确保留在 author intent/story spine 下，无须为收尾扩大该权限。

## 3. 下一步执行顺序

1. **修正两个授权边界**：P1-A 的 ledger 完整性与重放身份、P1-B 的完整条件结构；绑定本次反例与
   合法对照，保持 terminal、条件、authority 门失败关闭。
2. **完成剩余集成点**：P2-A 原始计划计量，P2-B 默认提案接线与带诊断的有界修复。
   明确分别记录“消费合同已验收”“默认入口已接线”“真实模型已验证”。
3. **做一个范围固定的离线集成检查点**：覆盖执行记录→回执→gap→checkpoint/handoff，
   proposal→NarrativePlan→page revision→Writer request，以及跨 revision 预算。
   验证重点为不变量和拒绝行为；避免只复述全量测试数。R10 仍暂缓，此检查点不能宣称完整 G3 已通过。
4. **转入定向 Research 补证与计量校准**：围绕冻结 E 的两个 operation disposition 与三条 strict
   partial，逐项记录当前证据、缺少的入口/配置选择或关系依据、允许的查询范围及结束条件。
   在具体事实补证前保持未决，不把缺证改写成不存在。用完整序列化请求校准实际 tokenizer，
   分别记录 planned、reserved、measured、spent 与 unsettled。
5. **再判断 authoring live 的准入**：Research 补证诊断应执行自己的前置条件，不能要求它先满足
   依赖其结果的 Writer authoring admission。Writer 正文生成仍须通过自己的统一准入。
   后续真实运行按已授权范围执行，并按仓库规范绑定 `/health`、`/v1/models`、模型身份、
   队列/KV 状态和全新目录；本轮复核没有启动该步骤。

这次需要调整的是验收粒度与推进顺序：将测试已覆盖的局部消费能力准确结项，同时把实际执行完整性、
默认产品接线和 Research 补证作为明确剩余项。保持现有架构，不以改门槛或减少义务来消除冻结失败码。

## 4. 本次可复查产物

- [独立诊断脚本](../.tmp/c2p-direction-review-20260913-round3/review_probes.py)
- [诊断结果、17 个代码哈希及 fixture 路径](../.tmp/c2p-direction-review-20260913-round3/probe-results.json)
- [当前冻结离线链](../.tmp/c2p-unified-repair-20260913-r9/offline/offline-ebcar-r9.json)

执行命令：`python .tmp/c2p-direction-review-20260913-round3/review_probes.py`，exit 0，模型调用 0。
该 exit 0 表示诊断成功执行，输出包含上文的缺陷复现，并不表示产品通过验收。
fixture 均位于本次独立目录；原有 Run E、上一轮诊断与执行摘要未修改。
文档完成后 `git diff --check` exit 0；报告全部本地链接存在，再次核对上述 17 个生产文件哈希未变化。

## 5. 修复后的独立验收（2026-09-13，18 文件代码身份）

本节绑定用户报告 `3384 passed, 3 skipped` 后的代码；前四节保留为原复核快照。
最新 `r9-summary.json` 中 **18 个生产文件哈希均匹配当前工作树**。本次重跑
`python -m pytest -q tests/test_agentic_third_review_integration.py -p no:randomly`，
结果为 **4 passed，exit 0**；未重跑全量。冻结 Run E 五个准入失败码仍未变化。

独立复查已确认：第三轮的四个条件反例全部拒绝，属性/索引与算术同形两个合法对照均接受；
原始计划 900、新计划 100 的 started attempt 按 900 计量；损坏账本在回执/gap 生产边界抛出
完整性错误；默认提案适配器经注入传输能产生 accepted plan。上述修复应保留。

但当前还不能结项为“执行记录→终态消费、提案→分页→Writer 请求均闭合”。本次继续执行旧测试
没有走到的后续动作，复现以下问题。

### 5.1 P1：重放身份检查发生在执行之后，新候选仍可丢失

当前 `research_tools.py:3258` 先调用 executor，之后才由记录器校验重放身份；
`:3271` 捕获冲突后返回 invalid_request，没有记录这次已经发生的执行，也未使旧关闭证明失效。

探针先搜索 `forward` 并读完结果、取得关闭回执，再用相同 ID 搜索 `train_loop`。对实际 executor
做只观察的包装后，捕获到第二次搜索 **success，发现两个新候选**；dispatcher 随后返回
`execution_ledger_replay_mismatch`。但账本仍只包含原查询，frontier 仍 closed，旧 receipt 再次
使 gap 工具返回 success、`negative_evidence_authorized=true`。

现有同 ID 测试在第一次搜索后没有读取结果，其前沿本来就是打开的，因此“冲突后仍未关闭”的
断言没有覆盖上述路径。修复应在执行前核对完整请求身份，保证拒绝的请求没有进入 executor；
若执行已经发生而记录无法提交，则必须保留阻断关闭的持久状态，直到观察得到正确登记。
验收必须从**已关闭前沿**开始，同时断言 executor 是否运行及后续 gap 的授权结果。

### 5.2 P1：已有 gap 的消费者仍未使用新的账本重验能力

`research_execution_ledger.py:1013` 新增的 `ledger_reader` 参数没有被两个生产消费者传入：
`autonomous_method_agent.py:1529` 的 `_load_terminal_gap_artifacts`，以及
`research_terminal.py:843` 的终态证明判断，仍仅消费旧 receipt 字段。

在独立 fixture 中先正常生成 gap，再损坏其搜索记录：生产工具正确返回
`gap_search_ledger_integrity:...unparsable`，但随后调用实际消费者仍得到：

```text
evaluate_obligation_terminal_proof(...).terminal = true
_load_terminal_gap_artifacts(runtime) -> 1 个 ExplicitCodeGapV1
```

现有集成测试保留并断言旧 gap 的 `negative_evidence_authorized=true`，没有继续调用上述消费者。
保留历史文件可以维持审计历史；当前 revision 的准入必须使用重新认证的结果。拥有 runtime 的
加载器应连接实际 ledger；纯终态函数可以消费由调用者提供的、绑定当前 revision 的认证结论。
适配器须检查认证成功与身份一致，不得仅判断返回对象非 None。补充损坏、删除、陈旧回执经过
terminal、coverage/handoff 的拒绝断言。

### 5.3 真实 authoring 前仍须完成提案预算与追踪接线

`narrative_organization_proposal.py:245` 直接调用传输，当前没有统一 invocation reservation、
发送前计量/扣减或该调用的 started/completed receipt。角色配置和每机制两次尝试的上限不能证明
整个 run 的调用与输入预算成立。`recorded_not_in_invocation_plan` 诚实记录了剩余工作，但不是
预算准入的替代；应在任何会触发默认提案的真实 authoring 前完成该接线。

本次还发现提案 trace 的 `request_prompt_digest` 实际为空：`:252` 读取 `prompt_digest` /
`input_digest`，而 `LLMRequest` 的实际属性是 `input_hash`。两次注入传输捕获到的真实 request
hash 均非空，写入提案 trace 的值却都是空字符串。使用真实请求身份，并按统一预算合同记录
planned/reserved/measured/spent/unsettled；发送前必须能够拒绝无预算或无法计量的调用。

### 5.4 固定集成检查点的实际覆盖范围需要补足

`test_proposal_to_page_revision_to_writer_projection`（集成文件第 244 行附近）实际只构建 plan、
比较 `paragraph.model_dump()` 和同一 paragraph 的字段、检查 detail 集合。它未调用 page revision
编译器或 Writer request 构造器。因此当前证据支持“提案进入 plan”，尚不证明跨分页传递。
补一个确实触发分页的输入，并截获实际 Writer request，断言 detail、完整 witness target 合同和
公式消费者归属保持；不要继续用 plan 自身的序列化结果代替下游请求。

下一步仍保持小范围：先补 5.1–5.2 的实际执行/消费边界，以及 5.4 的验收缺口；提案预算接线与
tokenizer 校准合并为明确的计量工作。可以并行准备定向 Research 的证据清单和查询范围，
使用负证据回写前须先满足 R9 的完整链路。R10 继续暂缓，不扩大跨机制组织权限。

新增证据：[复核脚本](../.tmp/c2p-post-round3-verification-20260913/verify_boundaries.py)、
[结果及 18 文件哈希](../.tmp/c2p-post-round3-verification-20260913/results.json)。
命令 `python .tmp/c2p-post-round3-verification-20260913/verify_boundaries.py`，exit 0；
包含上述缺陷复现及合法对照，模型调用 0。未修改生产代码、已有测试或运行产物。
