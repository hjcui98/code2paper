# Research → Method 生产入口收敛执行文档（2026-09-15，第二次核验修订）

## 1. 执行目标与边界

**交付目标：当前 EBCAR 输入能够从正常 `code2paper method-agent run` 产品入口完成 authoring，交付完整、可审阅、通过 Candidate 验收的 Method，并能可靠恢复。** 先用冻结证据打通共享生产函数，再验证正常产品入口；replay 成功只是中间检查点。同一正文的 Verified 结果独立报告，Candidate 成功不能冒充 Verified、通用上线或默认切换完成。

执行顺序固定为 **A：完整准备合同 → B：成果续跑与全文集成 → C：真实全文交付**。A/B 是同一修复批次的两个验收面，条件满足后直接进入 C，不再另开一轮计划、单页抽样或无变化整轮重跑。每次报告以正文提交与最终产物为主，测试数和 token 增长只作辅助证据。

本文件细化[统一执行计划 §15.7](research_to_method_unified_repair_execution_plan_2026-09-12.md#157-全流程复核后的当前执行入口更新至-2026-09-15-r5-终态)，替代历史片次的“默认下一步”，不修改[文档入口](README.md)索引的总体架构、Writer 设计、intent-first authoring 或 Unified 信任边界。已落地的 digest、attempt、Research 图和 R10 修复保留；不默认重跑 Research，不把全局架构重写、所有 preferred 公式补齐或十项目验收加为第一份 Candidate 的新前置。真实事实缺口仍走所属 Agent 的有界补证路径。

**文档状态：生产代码修复与静态闭合已完成，正常入口 live 验收待执行。** 2026-09-15 的后续实现已落地 prepare/execute-prepared、统一调用账本、当前 Narrative 计划适配，以及本轮 Research→Candidate 终态修复。全量静态验证为 3582 passed、3 skipped；旧 EBCAR run28 的只读重算把 27 个旧 argument units 中 24 个按唯一源码锚点绑定，余下 3 个真实缺少 Narrative 锚点并会 fail-closed。该结果不等于新的 live Candidate；C 的真实正常入口交付仍须按 §5 验收。下文“待新增/尚未实现”措辞保留其历史制定时点，不能反向覆盖本状态更新。

### 1.1 对第一版的纠正与本次必修清单

第一版的 r5 根因和成本盘点成立，但“足以指导尽快进入真实生产”的结论过早：没有把后续请求漂移、实际正文验收仍用旧计划、正常产品入口漏传 tokenizer 定位到执行分支；阶段复用写得过于宽泛，还把 Realizer primary 误归为依赖未来 Writer 正文。第二次核验补齐如下有限范围，不要求执行者先建通用恢复平台。

| 必修项 | 已观察到的代码/产物证据 | 修改位置与完成判据 |
|---|---|---|
| F1 候选/片段合同 | r5 原 helper 复活旧 required detail，另丢 4 个新片段 | Writer prepare 的排序/临时计划；所有最终 row/page 对应且目标守恒 |
| F2 冻结后请求漂移 | 计划构造后才追加 3 条 partial handoff；同一 payload 分页下 18/18 请求哈希及 envelope 改变 | `publication_method_writer.py` 的 `_writer_request_for_page`、最终 request material 和 handoff 注入；全部 primary 的 prepare/send 摘要一致 |
| F3 正文验收身份错位 | unified 是 2 节；`plan.sections` 仍为 MA-S1…MA-S5，交集为空；正式 accepted 投影遍历旧计划 | 同文件正文事务/accepted/Editor/最终验收路径及 replay structural exit；实际正文按当前计划验收，旧接口有明确适配 |
| F4 阶段结束不等于调用全部成功 | 32 个包能从回执还原，当前绑定校验全部通过；其中 13 个来自 partial 调用；通用 resume 会重做 23 个 main | Formalizer 阶段读取与共用 Writer 入口；合法已结束阶段可直接继续，不把 preferred 失败改成成功或重新发送 |
| F5 正常产品入口缺 tokenizer | `autonomous_method_agent._run_writer_surface` 在 unified 下未传 `unified_tokenizer`，replay 则传入 | 共用 runtime/tokenizer 准备并接入两个调用者；正常产品入口得到同身份的实际计量 |
| F6 Editor/Rewrite 绕过统一发送账本 | 默认 caller 可直接进入 `LLMClient.complete`；当前 envelope 只有四个 page roles，Editor 的 config role 为空 | 共用 Writer 内包装 Editor/Rewrite 的辅助调用，明确角色和额度；发送前持久化/扣账，保留正式角色身份 |

F1–F3 在 A 关闭；F4–F6 在 B 关闭；C 交付真实全文和正常入口证据。Formula 的原运算绑定校验保留，论文表达质量按实际消费包定向处理，不把重写整个 Formalizer 变成进入 Writer 的前置。

证据：[阶段读取核验](../.tmp/c2p-e2e-flow-review-20260914-01/checkpoint-scope-audit.json)、[下游合同核验](../.tmp/c2p-e2e-flow-review-20260914-01/downstream-contract-audit.json)。两者均为模型/网络调用 0 的有界探针；F2 使用真实生产注入代码、serializer 和 digest 函数，不包含 tokenizer 准入；F3 不声称正文必然丢失，Candidate 组合有输出 ID 回退，但正式 accepted/最终门仍有身份问题；F5/F6 拦截在调用边界，没有执行真实网络。

## 2. 从这个事实基线出发

| 项目 | 已核实状态 | 对执行的约束 |
|---|---|---|
| 最新全文 r5 | `/tmp/c2p-candidate-live-20260914-r5`，exit 2；54 次 Formalizer，Writer 发送 0，无 Candidate/Verified | 从这里的合法上游成果开始准备，保留失败现场 |
| 重复成本 | r2–r5 共 216 次 Formalizer 发送；每批 54 个 provider request 内容哈希相同；input 1,819,148、output 388,616，调用区间合计约 76.99 分钟 | 下游确定性修复不能再默认触发整批上游生成 |
| 已有上游成果 | r5 有 32 个 accepted 机制公式包；83 条公式义务均为 preferred，51 条未覆盖；原始 Narrative 为 2 节/19 段 | accepted 不等于论文表达合格；未覆盖状态保留，不偷换成 required 或删除 |
| 分页已有实现 | 编译器已有按 detail/依赖分片及按完整请求计量修订；离线 payload 回放为 21 段/18 页 | 修复生产接线和合同，不重新造一套分页器；21/18 不是生产硬编码目标 |
| r5 直接根因 | `_ordered_candidate_rows` 把候选 row 换回旧完整 row，并丢弃原计划中没有的新片段 ID | 必须同时修旧合同复活和新片段丢弃，不特判 detail 13 |
| 单页 r7 | 已有 committed submission、resume 新发送 0；archive 与全文不同 | 可保留为恢复回归，不移植成全文成功证据 |
| 恢复能力 | 本次对 r5 的 54 个回执及全部 32 个片段核验：身份/引用缺失为 0、aggregate 与片段一致；当前包校验 32/32 | 阶段成果可用于实现确定性续跑；还没有可执行的生产阶段 loader |

r5 零网络因果对照：原生产 helper 在第 10 次候选请求构造复现相同错误；仅在内存中保留传入候选 row 后，37 次构造返回、修订 21 段、失败列表为空。该探针以 0 占位请求 token 计量，**只证明 tokenizer 之前的合同根因**，没有证明真实请求准入。

详细证据与局限见[全流程复核](research_to_method_end_to_end_status_review_2026-09-14.md)、[r5 因果探针](../.tmp/c2p-e2e-flow-review-20260914-01/r5-prepare-probe.json)、[r5 终态](../.tmp/c2p-e2e-flow-review-20260914-01/r5-terminal-observation.json)、[输入与代码索引](../.tmp/c2p-e2e-flow-review-20260914-01/inventory.json)。本次复核的 18 个关键源码/配置摘要未漂移；其他工作树改动仍是需保留的既有基线。

开始实施时把实际使用的 r5 输入、原计划、回执及其引用的请求/响应/验收文件连同摘要清单复制到工作区专属 `.tmp` 证据目录，检查依赖可完整读取；不要只保留指向 `/tmp` 的路径。代码状态同时记录 HEAD、工作树相关文件 SHA-256。第二次核验已直接验证 r5，不再以 r4 的恢复数字推定其资格。

## 3. A：一次关闭生产准备合同

### 3.1 负责位置与最小改动

主要修改 [publication_method_writer.py](../src/code2paper/agentic/publication_method_writer.py) 中 `_run_publication_method_writer_impl` 的 Narrative → Writer prepare 段、`_ordered_candidate_rows`、`_temporary_narrative_plan`、`_writer_section_inputs_v3/_v2`；必要时修改 [unified_context_compiler.py](../src/code2paper/agentic/unified_context_compiler.py) 的 `fit_narrative_plan_to_page_budget` 和 Writer workset 扩展函数。

把现有请求计量修订循环提取为一个可直接调用的生产准备函数，建议名 `prepare_unified_writer_phase`（待新增）；优先放在现有模块，复用现有模型/编译器。完整入口和诊断调用同一函数，不另写一套“预检专用”分页逻辑。不要求先完成全函数解耦、通用工作流引擎或任意阶段缓存。

该函数消费经过校验的 archive、workset、Narrative、公式义务/包、预算 envelope 和 tokenizer；返回同一修订的 Narrative、最终 manifest、实际 Writer 请求材料、Writer invocation plan、后续阶段预算计划及准备报告。失败也落盘已完成的候选测量与首个根因，不能像当前路径一样只在循环全部通过后写测量表。

### 3.2 必须一次覆盖的合同

1. **row 版本与顺序。** 排序只能排列传入 row，不能按 ID 取回旧 row。合法片段 ID 由编译器修订结果及其父段落关系确认，不以“旧列表里不存在”丢弃。保留作者既定 section/段落顺序与片段顺序，未知身份和重复提交仍拒绝。
2. **局部归属与全局守恒。** 候选 row 使用候选 page；最终 row 使用最终 manifest。每个最终段落有合法承载页，其 required detail、公式及依赖闭包均可在该页按合同解析。required/optional detail、formula obligation/package 的全局集合分别守恒，不降级、不删目标；共享依赖与段落提交身份分开检查。
3. **完整请求材料封闭后再冻结。** 模型实际接收的 prompt、页面、schema、partial handoff/qualifier 等由同一生产 builder 组装，计量与发送绑定同一材料和摘要。把当前约第 3537 行的 handoff 注入移入共用请求构造合同，不能计量后再追加，也不能删掉它绕过 envelope 检查。候选和最终请求都含适用 handoff；页面不重复携带；禁止底层发送时静默拆已冻结请求。primary 在冻结后不得变更；内容 repair 使用已有显式 repair envelope。
4. **两层预算分别说明。** 当前 20,000 是页面 payload 门，60,000 是配置的单请求输入门，131,072 是模型上下文；三者不是同一个量。用匹配模型的 tokenizer 测量完整请求，不能用 UTF-8/4 宣布通过。页可拆时按 detail/依赖闭包修订；不可拆原子或总额度不足时给出 typed 阻塞和具体测量，不截证据、不默认提高上限。
5. **按实际依赖计量。** Writer 和当前独立 Realizer 的 primary 都由冻结 page、计划和公式包构造，prepare 应通过各自真实 request builder 提前计量。当前 `_run_unified_v2_realizer_phase` 不接收 Writer 正文；不能以“等待未来正文”为由只测其简化 lookahead prompt。repair feedback 与 Editor/Rewrite 依赖未来响应，先预留有来源的上界/额度，发送前再真实计量。保留 future-primary 与 retry reserve。
6. **无生成副作用。** prepare 不触发 Formalizer、Writer、组织提案或其他生成调用。tokenizer 可本地执行，或单独记录 `/tokenize` 请求；服务不可用时可完成合同检查，但不能把未实测标成准入通过。

### 3.3 A 的退出产物与验收

复用已有 `narrative_plan_v3`、`consumer_workset_manifest_v2`、Writer plan 和 `writer_request_measurements_v1` 输出。新增一份 `authoring_prepare_result_v1.json`（待实现的结果索引），链接输入/代码/模型/tokenizer/请求摘要、修订历史、全量目标归属核对、预算、准入及失败细节，不复制一套事实账本。

以下一起通过才结束 A；出现哪个报错就修哪个 ID 不算通过：

| 验收输入 | 必须证明的行为 |
|---|---|
| 缩小候选 row 与旧 row 共享 paragraph ID | serializer 消费缩小后的 required 集合；原 row 的 detail 不会复活 |
| 编译器产生原计划没有的片段 ID | 全部合法片段进入最终 plan/request，顺序与父段落关系保留；未知片段拒绝 |
| r5 完整冻结输入 | 所有候选和最终段落经过真实生产 prepare，目标守恒、局部绑定通过；不是只测 detail 13 |
| 29,060/23,980 payload 与 70,439 完整请求反例 | 在同一准备入口完成合法修订，或对真正不可拆/总额度不足给出准确阻塞；不提前发送生成请求 |
| 预算和修订边界 | 精确上限、越界、修订次数耗尽、发送材料漂移都受控；失败报告可读取 |
| r5 三条 partial handoff | 所有最终 Writer primary 的真实 serializer 材料和 envelope 在 prepare/send 一致，handoff 约束仍存在 |
| 旧 5 节与当前 2 节 | Writer 输出进入当前段落事务、accepted 和最终验收；不能只改变 structural exit 的计数来源 |

冻结输入探针保留诊断用途。正式回归应调用提取后的生产函数，不能继续依赖 AST 提取私有 helper 或以 token=0 的对照替代实测验收。

F3 的最小修复在当前产品通路统一有效计划：优先消费 Narrative 已声明的 section/paragraph/target；必须调用旧类型接口时生成显式、可验证的适配模型，同时保留原 author scope 与义务映射。审计当前 `_run_publication_method_writer_impl` 中所有影响正文的 `plan.sections` 消费点，至少包括事务、缺失段落修复、accepted、Editor section order、authorship、最终验证和 product bundle。不要只用新 ID 改名、不要伪造 argument/evidence 字段；类型不兼容处修改调用适配，不触碰旧 lane 的语义。

## 4. B：把合法成果接入续跑，并预查全文下游

### 4.1 只新增一个明确的阶段操作合同

负责 [publication_method_writer.py](../src/code2paper/agentic/publication_method_writer.py) 的 `_run_unified_v2_formalizer_phase` 入口、[run_authoring_replay.py](../scripts/run_authoring_replay.py) 与 [unified_invocation_ledger.py](../src/code2paper/agentic/unified_invocation_ledger.py)。复用严格读取、片段摘要和现有预算账本；通用 `build_resume_plan` 的成功定义保持不变。

**先实现一个有限能力：读取已结束且当前仍适用的 Formalizer 阶段。** r5 的阶段断言为空、34 main 已执行、有界 repair 为 20、包数 32，生产函数当时已允许进入 Narrative；83 个 preferred 中的失败被记录但不阻塞这次阶段转移。新 loader 返回等价的已验证 phase outcome 和未满足义务，直接继续 Narrative/prepare。它不调用 `execute_formalizer_invocation_plan`，不把 partial receipt 改成 complete。当前普通 resume 会安排 23 个 main 重做；18 个可 reuse invocation 只包含 19 个包，另外 13 个合法包在 partial 回执中，不能丢失。

loader 验证原 archive/manifest/plan/模型/请求/全部 started-completed/片段闭包，重建包集合并用当前 validator 重验，核对阶段断言及 required/preferred disposition；记录原失败、已花费和阶段结束依据。只有源身份/内容合同变化影响这些成果，才生成明确失效清单。无需建立跨任意代码修订的自动缓存：本轮只支持严格等价成果、当前校验及明确失效，不能用全局 code digest 被拒绝作为重新发送相同 54 请求的理由。

在现有两个位置参数 `frozen_root fresh_root` 下新增 `--authoring-stage {full,prepare,execute-prepared}`（**待实现**）。默认 `full` 保持现有兼容行为：

| 模式 | 必须实现的含义 |
|---|---|
| `prepare` | 从 `frozen_root` 用上述 loader 读取阶段成果，在全新 `fresh_root` 准备 authoring；生成调用为 0；缺输入返回明确缺口，不能隐式退回整批 Formalizer |
| `execute-prepared` | 读取同一 `fresh_root` 的准备结果，重新验证摘要与准入，执行实际 pending 的 authoring；同目录再次调用按账本恢复，不覆盖已提交正文或重发已完成请求 |

当前已有 `--resume` 只是 section 选择，`--deterministic-preflight-only` 只覆盖上游确定性预检；它们均不能冒充上述功能。两个新模式与不兼容的 rebuild/旧 resume 参数显式互斥，CLI 测试验证无意外生成调用。必须交付真实 `--help`、参数校验和两个模式的运行证据，才可使用下节示例。

CLI 只是共享阶段读取/准备函数的薄包装。正常 `method-agent run` 增加可选 `--authoring-phase-checkpoint`（待实现），经主流程传递到相同 loader；不重新造第二套导入/信任合同，不要求新项目必须有旧 checkpoint。优先交付共享生产函数和确定性全页回归，再接这几个参数，不能只完成 CLI 后宣布可续跑。

阶段成果读取必须满足：

- 原 receipt 在原 plan 身份下验证，保留请求/响应/usage/验收证据；不能改旧 digest 让它匹配新 plan。
- package fragment 可复用须有可追溯的生产验收，并通过当前合同重验。transport accepted、task partial 和段落 content accepted 分开解释；不能因包文件存在就把整个 invocation 标成完成。
- 为新准备结果记录父输入与依赖关系。当前代码、schema 或请求语义变化使哪些成果失效，就重验/重做哪些依赖；不把全仓任一文件变化等同整批 Formalizer 失效，也不能绕过现有 digest 拒绝。若现有 reader 不支持这一转换，显式派生新阶段记录并保留父证据。
- 从 r5 延续工作的实际花费、未结算调用与剩余额度继续保留；新目录不是预算归零许可。r2–r4 的独立历史诊断成本另列，不能重复计入或隐去。未知 usage 不当作 0；未发送 conditional slot 只在触发时激活。
- 写下哪些成功结果复用、哪些不完整结果仍待处理。对本次纯 Writer 准备修复，合法且不受影响的上游结果无需新生成；不得声称 r5 的 54 个调用全部完成、32 个包全部免重验。

### 4.2 生产 runtime 与辅助角色发送闭环

F5 负责 [autonomous_method_agent.py](../src/code2paper/agentic/autonomous_method_agent.py) 的 `_run_writer_surface`、[tokenizer.py](../src/code2paper/llm/tokenizer.py) 及 replay 的 `_build_replay_unified_tokenizer`。从 replay 提取必要的 runtime/tokenizer 准备，正常产品入口与 replay 使用同一实现和身份记录。正常 `method-agent run --authoring-context-mode unified` 经当前链路未向共享 Writer 传 tokenizer；只修 replay 无法结项。已有 `--research-stage-checkpoint` 可跳过重复 Research，但不能代替 Formalizer phase checkpoint。

F6 负责共用 Writer 的 Editor/Rewrite caller 接线、[cross_section_editor.py](../src/code2paper/agentic/cross_section_editor.py)、[rewrite_agent.py](../src/code2paper/agentic/rewrite_agent.py) 和 [proposal_call_accounting.py](../src/code2paper/agentic/proposal_call_accounting.py)。沿用现有 `build_budgeted_auxiliary_llm_caller` 的辅助调用账本模式：Editor 使用明确角色，Rewrite 保留 `local_rewrite`；在 profile/envelope 声明调用数、请求上限和预留，共享同一 run 总额/继承花费。Editor 当前 role 为空，不能原样接包装后留下一个必然的缺角色拒绝。

这些请求不是 page consumer，不强行伪造 page_id 或扩成通用四角色协议重写。实际发送前按真实材料计量、持久化 started、核对预算，响应完成后记录 usage/未结算状态。后续 primary 的预算也须受保护。未声明角色、零剩余额度、tokenizer 不可用和 started 落盘失败时调用数均为 0；正常声明时能通过并正确扣账。不能靠关闭 Editor/Rewrite、隐去其调用或默增总额度来通过。

### 4.3 公式表达只做必要的定向修复

负责 [formalization_agent.py](../src/code2paper/agentic/formalization_agent.py) 的机制公式校验及 Unified Formalizer prompt，和 `run_authoring_replay.py::_record_authoring_structural_exit`。

已有 accepted 包出现 `WRITE(outputs) → outputs`、`LOAD(document_id) … → WRITE(temp_document_id)`；prompt 强制原 predicate/operand 进入 LaTeX，而 validator 又排斥代码痕迹。先用冻结包离线核对**来源绑定、论文表达、公式消费**各自状态，把内部操作绑定与展示表达分开。必要修复须同时覆盖 prompt、闭合 schema/解析与反向校验，不能只关闭 code-plumbing 或运算匹配检查。符号映射必须可验证，源码加法仍不能被写成乘法。

保留 83 条 preferred 及 51 条未覆盖的真实状态；按现有规则决定哪些数学论证需要定向 Formalizer repair，哪些 preferred 尚未满足但不阻塞 Candidate。不要制造“全 83 个完成才准许 Writer”的新门；也不要靠删公式义务生成缺少方法数学表达的安全代码摘要。若修复影响部分包，只失效其消费路径并重做准备，不重发整批相同请求。

本次绑定重验 32/32 通过，故不以“可能有问题”重新生成它们；论文表达仍须审阅。记录实际消费包中的代码操作表达、其论文改写要求及对应 owning Formalizer/Editor 修复，已可用内容保留。正文收尾身份错位按 A/F3 修，不能仅修改报告计数。优先得到同一正文的具体质量反馈，不把全套公式架构改造追加到 live 前。

### 4.4 B 的唯一集成检查点

使用同一生产路径做 **prepare → Writer 请求/验收 → Realizer 事务与组合 → 最终计划投影/structural exit → resume** 的零生成调用集成检查。冻结全文输入覆盖全量页身份；小型通用 fixture 用明确标注的测试响应覆盖提交和故障恢复。不得把 assessor、Binder、验收器或最终门直接 mock 为成功；测试目录不能发布成真实 Candidate 证据。

同时覆盖：合法 repair 后提交且同身份恢复零重发；空/标题-only/错误运算响应零提交；中断后已完成页不重发；准备结果/父记录被改写时拒绝；正文义务不会在组合/适配时丢失。未来模型是否写好全文只能由 C 证明，但这些确定性接线错误应在这里发现。

追加本次明确反例：3 条 handoff 的所有 primary envelope 一致；2 个 unified section 进入实际 accepted/最终验收；32 个已验证包含 13 个 partial 来源全部保存而 Formalizer 新调用为 0；正常产品入口 tokenizer 身份与 replay 一致；Editor/Rewrite 辅助发送在额度/持久化失败时拒绝、有额度时记账。只测原 helper、只测请求能构造、只测 CLI 参数解析均不足以结束 B。

**B 退出要求：** 两个新模式可运行，r5 阶段读取与失效清单可审查，上述集成通过，待发送角色/任务/预算明确。若既有最终门暴露额外阻塞，先归到其所属阶段并用冻结输入复现；不要换目录重新生成来定位。

## 5. C：一次受控全文生产执行，按实际阶段收尾

### 5.1 运行前与操作示例

A/B 通过后使用指定 `8006/qwen38-27b-nvfp4`、上下文 131072，以及 [qwen38 profile](../tests/live/profiles/qwen38_vllm_budgeted.example.env)。记录 `/health`、`/v1/models`、模型/tokenizer 身份、可用的队列/KV 状态和输出目录；有资源压力则等待或减少并发。先校验健康状态码/响应类型，避免 r1 空 health body 的旧解析错误。不得记录密钥。

**以下是待交付 CLI 的验收示例；当前脚本还不支持 `--authoring-stage`，实现并验证后才能执行。** 第一次 prepare 目录须全新；execute-prepared 使用原准备目录。若执行日期/目录已变，替换输出目录一次，并把最终精确命令写入 implementation。

```bash
python scripts/run_authoring_replay.py \
  /tmp/c2p-candidate-live-20260914-r5 \
  /tmp/c2p-production-closure-20260915-01 \
  --profile tests/live/profiles/qwen38_vllm_budgeted.example.env \
  --force-profile --authoring-context-mode unified \
  --authoring-stage prepare

python scripts/run_authoring_replay.py \
  /tmp/c2p-candidate-live-20260914-r5 \
  /tmp/c2p-production-closure-20260915-01 \
  --profile tests/live/profiles/qwen38_vllm_budgeted.example.env \
  --force-profile --authoring-context-mode unified \
  --authoring-stage execute-prepared
```

prepare 通过后执行 Writer 及其下游；实际需要的修复按原有有界预算进行。所有依赖未来输出的请求在发送前完成真实计量/预留/started 持久化。不能先发送，再补算 admission。

### 5.2 正常产品入口必须验收，不能停在 replay

共享生产函数首次交付全文后，使用实际存在的 `code2paper method-agent run`，指定 `--repo`、`--author-intent`/`--claims`、`--out`、`--llm-profile`、`--authoring-context-mode unified`。按源树/作者意图/配置一致的已验证 `--research-stage-checkpoint` 复用 Research；按 B 新增的 `--authoring-phase-checkpoint` 复用适用 authoring 阶段。实施者须从实际文件生成精确命令，记录 checkpoint 的验证结果；r5 目录不是天然合法的 Research checkpoint，禁止拿目录或摘要冒充它。

该入口的生成调用仍受同一累计预算和恢复规则约束，先做零生成调用的入口集成，再做有变化依据的真实执行。正常入口须交付与 §5.4 同标准的完整 Method、来源/模型身份、终态、预算与恢复记录。不得为检验入口而无条件再发相同整批 Formalizer；优先使用已验证阶段和已接受页。若当前输入不满足 Verified，正常 Candidate 产品仍按其原规则报告，不能伪造 Verified。

进入受控真实使用的完成条件是“正常入口 + 全文验收 + 可恢复 + 所有实际模型调用可计量”。更广项目的推广/默认切换继续受既有 D5/holdout 要求约束；本文件不把这部分省略为已经生产就绪。

### 5.3 失败只回到所属阶段

| 发生位置 | 处理与续跑范围 |
|---|---|
| prepare 的 row/page/请求/预算错误 | 保存该修订输入与失败材料，零生成调用修复并重新 prepare；不发送 Formalizer 验证分页 |
| Formalizer 内容或符号绑定错误 | 复用未受影响包，对实际需要的义务有界修复；受影响的 Writer 请求重新准备 |
| Writer transport / 表示 / 内容失败 | 按已有分层处理；内容反馈回 Writer，只有通过事务验收才能提交；保留其他已提交页 |
| Realizer witness/覆盖失败 | 使用实际 Writer 输出修复所属映射/组合；不改证据或机械篡改正文凑 witness，不重跑上游无关页 |
| Editor/Rewrite/最终一致性失败 | 在相同全文身份下由所属 Agent 有界修复，重新校验受影响文本；不要重新启动 Research/Formalizer |
| 额度耗尽、不可拆原子、真实缺证、无进展 | 诚实停止并输出根因、已提交成果与下一可执行动作；不换目录碰运气或扩大额度掩盖失败 |

保留阶段完成点；同合同重复失败且没有代码/输入/反馈变化时不再次发送。确需修订 manifest/plan 时生成显式新版本，重新验证受影响依赖；已冻结旧文件与历史花费保留。模型服务运行稳定只说明请求仍在处理，不能作为进度验收。

### 5.4 交付清单

C 只有同时提供以下结果才算交付首份完整 Candidate；正常产品入口还须通过 §5.2：

- `artifacts/06_authoring/publication_candidate_method.md` 存在且为完整 Method；所有必需段落完成事务提交，章节/方法论证连贯，不用占位正文补齐。
- Narrative、最终 manifest/plan、段落提交、witness、公式消费、authorship/content trace 和最终正文身份一致；required 覆盖以及最终事实、条件、数值/公式、作者权和完整性门均按适用 lane 通过。
- `execution_record.json` 与 `authoring_structural_exit_v1.json` 对应本次实际链路，Candidate 准入和执行退出一致；不得只靠文件存在判成功。
- 真实发送/usage、planned/reserved/measured/spent/unsettled 和继承花费可核对。相同已接受结果再执行恢复时，新增生成调用为 0；尚待处理任务不冒称零调用完成。
- Verified 独立标明通过或具体缺口。若 strict Research/事实义务仍阻塞 Verified，记录到其真实目标上，既不假报 Verified，也不额外否定按 Candidate 规则已合格的正文。
- 人工审阅正文的机制说明、核心数学表达、限定语和连贯性，记录具体结论。单个项目成功不授权 D5、默认切换或发布冻结；后续按已有产品验收要求推进，不另造本轮前置清单。

## 6. 验证与报告纪律

扩展现有测试文件为主；跨 prepare/execute 的集成用例可新增一个文件，创建后记录准确路径。当前可用的相关集合：

```bash
python -m pytest -q \
  tests/test_agentic_unified_context_compiler.py \
  tests/test_agentic_publication_method_writer_unified.py \
  tests/test_agentic_detail_atom_binder_and_trace_v2.py \
  tests/test_agentic_formalization_guards.py \
  tests/test_agentic_replay_execution_record.py \
  tests/test_agentic_autonomous_method_agent.py \
  tests/test_agentic_proposal_call_accounting.py
python -m compileall -q src tests scripts
git diff --check
```

前次复核实际跑过上列前四个文件：107 passed；未把 replay/产品入口/辅助调用集合或全量静态记作本次已通过。本次追加的两个探针命令为 `python .tmp/c2p-e2e-flow-review-20260914-01/checkpoint_scope_audit.py` 和 `python .tmp/c2p-e2e-flow-review-20260914-01/downstream_contract_audit.py`，结果及边界见 §1.1。实施中每处改动跑相关集合；A/B 集成里程碑完成、进入 C 前按仓库要求运行一次全量 `python -m pytest -q`。新失败或后续实质改动才按影响范围补跑，不为日志数字重复全套。`prepare` 的模型生成调用数必须为 0，tokenizer 网络请求另计。

每个检查点只更新[实施记录](../.agent/implementation.md)和本文件状态，不再层叠新修复计划。报告固定六项：

1. 当前阶段及首个阻塞根因，绑定代码/输入/plan 摘要。
2. 新增实际发送按角色分类，已复用/待处理 invocation 数与原因。
3. 正文已提交段落数 / 当前最终计划必需段落数。
4. 公式实际消费、通过验收及未解决义务，required/preferred 分列。
5. Candidate 路径/摘要/验收结果，Verified 独立结果。
6. 下一次执行的具体命令与影响范围；禁止无变化整批重跑。

本轮执行完成的判断依据是 §5.4 全文交付及 §5.2 正常产品入口。A/B 通过但 C 未完成时记录“生产准备完成，全文未交付”；replay 通过而正常入口未通过时记录“共享 authoring 已交付，产品入口未验收”。不得用静态通过、局部 repair 或 replay 成功表述为已进入可交付生产状态。
