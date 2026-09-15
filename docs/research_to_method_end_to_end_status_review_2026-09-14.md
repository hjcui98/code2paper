# Research → Method 全流程现状复核与交付纠偏（更新至 2026-09-15 r5 终态）

证据快照：2026-09-14 23:38:59 +08:00。当前工作树以 `84371e4` 为 HEAD，包含大量既有未提交修改。
本次沿实际 replay 入口、生产 Writer 编排、分页/计划、公式、事务、账本和最终产物核查；不是全仓逐行审计。
生产文件未修改，新模型调用及网络请求均为 0。18 个关键代码/配置文件的 SHA-256 和副本、218 个读取产物的
文件索引保存在 [审计目录](../.tmp/c2p-e2e-flow-review-20260914-01/)。

## 1. 结论

当前处于“冻结研究证据可进入 authoring、局部生成和单页恢复可用、全文生产链尚未跑通”的阶段。
最新已结束的完整尝试是 `c2p-candidate-live-20260914-r5`：exit 2，Writer 请求准备阶段失败，没有 Candidate 或 Verified。
同时存在单页 r7 的提交及零新增发送恢复证据，不能说所有修改都没有成果。

23:38 与 23:49 的 r5 观察曾为未决状态，保留在原快照中；00:02 追加终态后明确为 54 个 Formalizer receipts、
Writer 发送 0、exit 2。错误是试分页请求适配器重新引入旧段落合同，不是已经证明最终页面丢失 required detail。
见 [r5 终态](../.tmp/c2p-e2e-flow-review-20260914-01/r5-terminal-observation.json) 和 §4.1 的因果对照。

原定目标仍是完整、可读、事实权威分明的 Method Candidate，以及单独通过仓库反向验证的 Verified。
上位规范没有要求为了“安全”产出操作名堆叠，也没有要求每次修 Writer 都重跑相同 Formalizer。
信任方向应保留；执行方式需要纠偏：从逐个补异常后整轮 live，转为真实冻结输入上的阶段闭环、已验证成果复用、
再验证全文交付。不能按测试数量或 token 持续增长计算产品完成率。

## 2. 当前实际执行链

本轮真实命令使用 `scripts/run_authoring_replay.py`，从冻结 S3-20 研究产物重建 authoring，
不是从零执行新的 Research。产品入口 `run_autonomous_method_agent` 中的 Research 子图、作者约束和修订循环仍保留。

| 阶段 | 当前代码与职责 | 已观察结果 / 边界 |
|---|---|---|
| 冻结 Research → source/graph/handoff 预检 | replay → 当前源码重建 → Candidate handoff 重算 | r4 预检 pass，handoff eligible，revalidation failures 为空；3 supported + 3 partial，严格 Research 缺口仍单列 |
| Mechanism Context → Archive → formula worksets | `unified_context_compiler` / `mechanism_context_compiler` | r4 有 2 个机制、891 个 archive atoms、117 个 formula 技术页；34 个 main 调用，不再是义务×所有页 |
| Formalizer 主调用与修复 | `publication_method_writer::_run_unified_v2_formalizer_phase` | 34 main + 20 repair；32 个 accepted packages，覆盖 83 条 preferred obligations 中的 32 条；51 条尚未覆盖 |
| Narrative 组织 | `method_architect::build_narrative_plan_v3` | r4 生成 2 个 section、19 个 paragraph；这是计划，不是正文 |
| Writer phase prepare | 段落修订 → worksets → 实际请求计量 → invocation plan → admission | r4 在此失败；当前代码已有 request-aware estimator 和最多 3 轮重编译，完整入口尚无成功 live 证据 |
| Writer → Binder/段落事务/repair commit | `llm/section_writer` + `publication_transaction_contract` + 统一 ledger | 单页 r7 有 committed submission / resume；全文 r2–r4 的 Writer 发送为 0 |
| Realizer → 页/节组合与覆盖 | `_run_unified_v2_realizer_phase`、`mechanism_realizer_composer` | 代码及较早 S3-20 局部证据存在；本组全文 r2–r4 尚未到达 |
| Editor / Rewrite / 最终文本反向校验 | 生产 Writer 后段、final text validators、authorship ledger | 本组没有正文输入，不能用静态通过宣布这些阶段已完成 |
| Candidate / Verified / structural exit | 产物与独立质量/事实门 | r4 Candidate、Verified 均不存在；structural exit 文件存在，eligible=false |

Research 使用真实 LangGraph。当前 replay 的 authoring 关键执行仍由大型顺序函数编排；
`product_authoring_graph` overlay 已存在，但其事后状态提交不等于它已接管这次分页异常的自主恢复。
这一点是阶段恢复能力不足的背景，不构成现在重写整个架构的理由。

## 3. 产物与成本盘点

| 尝试 | 可核对产物 | 实际边界 |
|---|---|---|
| 单页 r7 | `single_page_submission.json`、`resume_result.json`、attempt receipts/content sidecars | 单页提交已记录，resume 新发送 0；`live_result.json` 已记录恢复动作，不能把其中发送 0 理解为整个目录从未发送 |
| 全文 r1 | execution record、failure artifact | health 空响应被当成 JSON 解析失败；生成调用 0 |
| 全文 r2 | 54 个 Formalizer completed receipts、32 包、narrative、失败终态 | `paragraph closure 29060 > 20000`，Writer 未发送 |
| 全文 r3 | 同类公式与计划产物、失败终态 | Writer 计划请求 `70439 > 60000`，Writer 未发送 |
| 全文 r4 | 同类公式与计划产物、失败终态 | `paragraph closure 23980 > 20000`，Writer 未发送 |
| 全文 r5 | 54 个 Formalizer receipts、32 包、失败终态 | 试分页请求构造报 required detail 13 不在页；尚未生成最终 Writer manifest/plan |

r2/r3/r4 账本合计登记 **162 次发送，全部是 Formalizer**；provider usage 合计 input 1,364,361、output 291,462。
各轮首个 started 至最后 completed 分别约 22.37 / 22.72 / 15.52 分钟，合计 60.61 分钟，未包含所有预检时间。
两两比较这三轮的 54 个 provider-request 文件，内容 SHA-256 全部一致。请求相同不说明这些网络调用没发生；
它说明修下游准备阶段时，上游的同一批工作又被执行了一遍。正文交付没有随这部分消耗增加。

r5 又登记 54 次同批 Formalizer 发送，34 main + 20 repair，其 54 个 request 与 r4 全部同哈希。
加入 r5 后四轮合计 **216 次发送，input 1,819,148、output 388,616、调用区间约 76.99 分钟**，Writer 仍为 0。
这些是逐 run 账本与 provider usage 的合计，不是把输出相同误判为重复文件。

证据：[产物盘点](../.tmp/c2p-e2e-flow-review-20260914-01/inventory.json)、
[请求哈希与成本汇总](../.tmp/c2p-e2e-flow-review-20260914-01/flow-findings.json)、
[r4 execution record](/tmp/c2p-candidate-live-20260914-r4/execution_record.json)、
[单页 r7 submission](/tmp/c2p-s3-single-page-20260914-02a75-r7/single_page_submission.json)、
[单页 r7 resume](/tmp/c2p-s3-single-page-20260914-02a75-r7/resume_result.json)。

## 4. 五个需要纠偏的问题

### 4.1 当前分页有进展，但验证仍没有覆盖完整准备入口

上次复核时缺少的 request-aware 重编译已经进入当前工作树，不能继续笼统称为“完全没有分页恢复”。
当前还有“先修订 Narrative，再构建最终 manifest”的顺序修复，避免原始超大闭包先抛错。

本次使用冻结 r4 的 archive、83 个 obligations、32 个 packages、19 段 Narrative 做零网络重编译：
19 段变为 21 段，18 个 Writer 页面，最大 payload 估算 19,791；required/optional detail、formula obligation、
formula package 四类 ID 集合均守恒，失败列表为空。该探针证明 payload 分页可过，
**不证明真实 tokenizer 的完整请求、全部角色预算、完整生产入口或正文验收已通过**。

完整准备入口应一次性产出最终请求、计量表、manifest/plan/admission，然后才把控制权交给 live。
现有 `--deterministic-preflight-only` 主要关闭来源、行为图和 handoff；不覆盖这个下游合同。
故“preflight pass”与“完成 Formalizer 后才发现 Writer 不能准备”目前可以同时发生。

**r5 终态的进一步定位：不是给小页补 detail 13。** 当前 `_ordered_candidate_rows`（生产 Writer 第 2542 行）
接收 compiler 已缩小的候选 row，却按 paragraph ID 从旧 `section_by_id` 重新取出完整 row。
在触发错误的候选里，required IDs 是空集、page 只声明 detail 19/3；适配器换回原 row 后，required IDs 又含 13，
Writer 按这个错误配对拒绝。候选小页的局部合同不等于全文义务；detail 13 仍需由其合法片段拥有，不能从全文删除。

零网络因果对照直接提取当前生产六个准备 helper 函数体，并调用真实分页器和 Writer 请求构造器：

- 原 helper：第 10 次候选请求构造复现与 r5 完全相同的 `unified_writer_required_detail_not_on_page:...:13`。
- 仅在内存中让排序 helper 保留传入候选 rows：37 次候选构造返回，修订 21 段、failures=[]。
- 对修订后的 rows 再应用原 helper，它还会丢掉 **4 个 `__f1/__f2` 新片段 ID**。只特判 detail 13 会漏掉这一类问题。

该对照刻意不调用 tokenizer，以 0 作为请求计量占位，仅用于隔离“计量之前的请求构造/归属”错误；
20,000 的真实 payload 分页门仍在。它不证明完整真实计量或 Candidate 成功。生产代码未改变。
证据：[r5-prepare-probe.json](../.tmp/c2p-e2e-flow-review-20260914-01/r5-prepare-probe.json)。

因此当前修复单位应是整个 prepare 合同：排序只能排列输入 row，不能把它换回旧版本或丢弃合法新片段；
候选行、候选页、最终行、最终页及实际 request 要明确对应同一 revision。所有段落一起验证，再允许新 live。

### 4.2 阶段复用没有成为实际操作路径

生产 ledger 有恢复能力。本次用当前 reader 验证 r4 的 54 个 receipts 后，针对原 Formalizer plan 得到：
18 个 invocation 可 reuse；36 个已有回执但 task incomplete；12 个未发送 slot。后二者不能冒充完成，
未激活 conditional slots 也不等于必须再发 12 次。

现行操作反复从 S3-20 开新目录，未把这个已验证的 Formalizer 检查点作为下游调试输入。
不能简单宣称“32 个包/54 个调用全部零发送复用”，但至少应保留可验证的成功 invocation 与 package fragments，
只失效受改动影响的依赖。若跨目录恢复尚无正式入口，就先使用 provider-free 冻结响应/成果回放验证 Writer 准备，
避免用完整生成来调试确定性错误。

第二次核验已直接验证 r5：54 条回执原身份一致、片段引用完整，32 个包与 aggregate 一致且当前绑定校验 32/32
通过；19 个包来自 complete 回执、13 个来自 partial。通用 resume 会复用 11 个 main/7 个 repair，安排 23 个
main 与 13 个已有失败 repair 重新执行，另有 12 个未发送 slot。当前 Formalizer 阶段在断言为空时已允许携带
preferred 失败继续，故下一步应读取这个合法已结束阶段，而非把所有调用变成 complete 再继续。阶段 loader
尚未实现；上述核验不等于当前 CLI 已能零发送续跑。见 [checkpoint-scope-audit.json](../.tmp/c2p-e2e-flow-review-20260914-01/checkpoint-scope-audit.json)。

### 4.3 形式化质量与论文目标出现具体偏差

32 个包的 `review_status=accepted`、authority 为 repository_verified，是当前验证器的接受状态，
不是论文数学表达质量的证明。实际样例包括：

```text
WRITE(outputs) → outputs
LOAD(document_id), LOAD(document_id[i]) → WRITE(temp_document_id)
```

当前 Formalizer prompt 要求 LaTeX 逐字保留 predicate 和所有 operand token；验证器又拒绝 `torch.`、`self.` 等
代码痕迹。这使部分任务形成合同冲突，也推动部分 accepted 输出成为操作描述。
r4 的 167 个 task failure 条目中，常见原因包括 code plumbing、operand mismatch、operator mismatch 和批响应解析失败。
51 条未覆盖义务全部为 preferred，不能改称 51 个 required 硬门，也不能删除它们来制造完成。

这项修复应明确区分内部操作绑定与对读者展示的数学表达；Agent 可以提出符号/数学结构，确定性校验保护
运算、参数、条件和证据。不是仅放宽 validator，也不是把每个 LOAD/WRITE 都变成一条“论文公式”。
Candidate 尚未生成，本报告不据这些样例推断最终正文已经错误发布。

### 4.4 失败汇总还混用了不同阶段的计划身份

r4 的 unified Narrative 是 2 节/19 段；失败后的 structural exit 却依据 method-section 适配层报告 7 段未评估，
并记录 `plan_digest_mismatch`。其 `accepted_formula_packages=0` 也不能抹掉机制层已经落盘的 32 个包。
`authoring_failure.direct_reason` 指向 `MA-S1` 的未评估段落，而 terminal reason 才是实际的分页失败。

这些都是未开始正文后的级联诊断，不是又出现 7 个正文 bug。需要让根因、阶段未运行、旧适配计划和当前实际
Narrative/公式产物分别带身份；不能靠过滤错误码令 structural exit 通过。

第二次沿正文路径核验发现，问题不止失败汇总：`_run_publication_method_writer_impl` 的正式 accepted 投影
仍遍历 `plan.sections`（约 5808–6240 行），r5 的旧 5 节与 unified 2 节 ID 交集为空。该路径需要统一有效
计划或显式适配；只换 structural exit 的计数仍不够。Candidate 组合有额外 output-ID 回退，故不能据此断言
未来文件必为空，但实际正文验收和最终门仍会错位。本组尚未真实到达这一阶段。

### 4.5 文档和验收粒度落后于实际工作

README/§15.6.8 仍停在单页 r3；单页 r7 和全文 r1–r5 已经发生。单页脚本硬编码目标页和单次 60,000，
它是诊断入口，其成功不会覆盖多 section、全部页和完整预算。当前脚本与产品共享了一些关键函数，
但不能据此宣称整个运行协议等价。

最新 107 项相关静态测试全部通过，同时 r5 的真实 helper 反例仍成立，说明现有验收集没有替代“真实冻结输入经过完整
phase prepare → 所有正文 → 最终提交”的交付检查点。继续增加相邻局部用例，不能单独解决这个差距。

### 4.6 第二次核验：冻结后的 handoff、辅助调用与正常产品入口

- Writer 计划在约 2906 行冻结，约 3537 行才把三条 partial handoff 追加进全部 `writer_inputs`；serializer
  保留该字段。用 r5 payload 修订的全部 18 页执行真实注入块、serializer 与 envelope 函数，18/18 请求和
  envelope 摘要改变。当前发送门校验 immutable primary envelope；必须在共用 builder 中先携带 handoff
  再计量/冻结，不能删约束或放松比对。该探针未调用 tokenizer，也未执行 full live。
- 默认 Editor/Rewrite 路径直接到 `LLMClient.complete`；本次离线在 client 边界截获，未传 unified envelope/
  ledger。Editor config role 为空，Rewrite 为 `local_rewrite`；现有辅助调用计量器可复用，但当前接线缺失。
  不能把四个 page role 的预算通过扩大为所有后续模型调用都已受控。
- 正常产品入口 `autonomous_method_agent._run_writer_surface` 未向共享 Writer 传 `unified_tokenizer`，
  replay 有传入。离线调用边界记录亦证实这一点；当前 profile 使用 `model_tokenizer`，不能仅在 replay 验收。
- 当前 Realizer primary 由冻结 page/计划/公式独立构造，不接收 Writer 正文。第一版执行文档把它归为未来正文
  依赖过于笼统，现已改为提前通过真实 builder 计量；只有动态 repair 和正文 Editor/Rewrite 等在输入就绪后计量。

证据：[downstream-contract-audit.json](../.tmp/c2p-e2e-flow-review-20260914-01/downstream-contract-audit.json)。
第一版执行文档未把这些调用边界逐项落实，不能据其已经写完宣布方案足够收敛；现已直接修订同一文档的 F1–F6。

## 5. 离最终目标还有什么

不提供“90% 完成”或“再一轮必成”的估计：尚未进入的阶段缺少本协议下的实测，无法据静态数量推算。

| 交付目标 | 剩余可验收工作 |
|---|---|
| 第一份完整 Candidate | 完整 Writer/Realizer 请求准备可通过；所有必需段落、条件、公式消费和 witness 闭合；全文组合及作者权/质量/structural exit 通过 |
| 仓库 Verified | 在同一最终正文上做反向验证；严格 Research partial、配置/证据缺口按实际要求解决；不能借 Candidate eligible 宣布完成 |
| 稳定的通用产品 | 当前协议下的多项目/holdout、失败恢复、质量与成本验证；历史 R8/旧协议成功不能替代这些证据 |

因此不是从零开始，但也不能说“只差分页这一个补丁”。最近的完整交付目标应该固定为第一份可审阅 Candidate，
再讨论更广的 rollout；R10、旧 digest/attempt 修复不重做，不额外把所有 strict Research 缺口设为 Candidate 的前置。

## 6. 下一步只按三个交付检查点推进

本节保留复核结论；具体实施顺序、负责函数、CLI 合同与验收以
[生产入口收敛执行文档（2026-09-15）](research_to_method_production_closure_execution_2026-09-15.md)为准。
该文档把下游确定性集成前移到 live 之前，细化为准备、成果续跑/全文集成、真实全文交付三个检查点。

1. **生产阶段准备闭环。** 从已冻结且身份验证通过的 Research/Formalizer/Narrative 输入，调用与 live 相同的
   Writer phase prepare；先关闭已知的 29,060/23,980 页闭包和 70,439 请求反例。输出最终所有页的真实 tokenizer
   计量、primary/repair/后续角色预算、manifest/plan/admission 和全量义务守恒证明。固定输入可复现，生成调用 0；
   tokenizer `/tokenize` 可作为随后受控计量，不能用估算冒充实测。单页微测也复用这个生产准备函数。
2. **全文正文与公式交付。** 准备通过后，只执行实际 pending 的 authoring。修复范围指向首个 owning stage，
   保留合法的已有成果和花费；形式化合同同时按 §4.3 保护事实并修正论文表达，不能把 83 条 preferred 清空。
   成功标准是完整 Candidate 文件及其段落/公式消费记录，不是更多 receipt。失败只进入受影响 phase 的回放/修复。
3. **最终一致性与质量。** 在同一 Candidate、Narrative/适配计划、content trace、formula consumption 和 ledger
   身份下运行最终验收；检查根因/级联报告、整链 resume、文章可读性和反向验证。Candidate 与 Verified 独立报告。

不新增一轮大架构改造，也不再用“修一个下游分支 → 重发整批 Formalizer”作为默认诊断方式。
本次未干预 r5，已把其失败终态追加进同一事实表。下一次执行应先覆盖 §4.1 的旧 row 复活与新片段丢弃两类反例，
以及全部页面进入生产 Writer 请求构造这一整段，不是再次只修报错中的一个 ID 后重发整批 Formalizer。

## 7. 本次核验

- `python .tmp/c2p-e2e-flow-review-20260914-01/inventory_evidence.py`：exit 0，冻结状态/代码索引。
- `python .tmp/c2p-e2e-flow-review-20260914-01/offline_probe.py`：exit 0，r4 payload 重分页守恒、54 条回执读取与原 plan 恢复判定。
- `python .tmp/c2p-e2e-flow-review-20260914-01/r5_prepare_probe.py`：exit 0；原生产 helper 复现 r5、内存候选-row 对照构造通过；模型/网络调用 0。
- `python -m pytest -q tests/test_agentic_unified_context_compiler.py tests/test_agentic_publication_method_writer_unified.py tests/test_agentic_detail_atom_binder_and_trace_v2.py tests/test_agentic_formalization_guards.py`：exit 0，107 passed。
- 未重跑全量静态、未启动 Research/live/模型服务、未修改生产代码；探针前后 18 个关键代码/配置文件 SHA-256 一致。
- `git diff --check`：exit 0；报告链接检查无缺失。

详细结果：[offline-probe.json](../.tmp/c2p-e2e-flow-review-20260914-01/offline-probe.json)、
[测试日志](../.tmp/c2p-e2e-flow-review-20260914-01/focused-tests.log)、
[source-index.json](../.tmp/c2p-e2e-flow-review-20260914-01/source-index.json)。
