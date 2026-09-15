# Research → Method 第二次执行中方向复核（2026-09-13）

结论：总体方向继续保留，但当前不能接受“R5 条件、R7 叙事/分页、R8 局部 callback、R6 预算已全部闭合”。
R9 的负证据授权已出现可复现的错误放行。先修正本报告列出的生产边界并完成实际 producer→consumer
合同验证，再进入 R10；不以增加状态字段或通过局部测试代替功能闭合。

本报告承接 [第一次方向复核](research_to_method_repair_direction_review_2026-09-12.md)，
受 [统一执行计划](research_to_method_unified_repair_execution_plan_2026-09-12.md) 及其上位设计约束。
本轮只做代码/产物审查与零模型诊断，未修改生产代码、测试、已有执行计划或实现记录。

## 1. 目前实际推进到哪里

已读取 [实现记录](../.agent/implementation.md)、
[R7 离线报告](../.tmp/c2p-unified-repair-20260912-r7/offline/offline-ebcar-r7.json) 和
[R7 摘要及代码身份](../.tmp/c2p-unified-repair-20260912-r7/offline/r7-summary.json)。

| 层次 | 当前可支持的结论 |
|---|---|
| R1 原始 active-path unknown | R7 冻结重建仍为 0，原混合状态问题没有重新出现 |
| Source / archive | pass；887 atoms，archive digest 仍为 `6b2ec29d…` |
| 基础与扩展 worksets | 基础 113 页，Writer 扩展后 131 页、4 个 worksets |
| 三阶段计划 | Formalizer 65、Writer 18、Realizer 18 个 planned invocations，均能编译 |
| 三阶段 admission | 仍为 fail；`failure_details=[]` 不等于 `failure_codes=[]` |
| 残余冻结失败 | 两机制 `operation_disposition_unresolved`，strict lane 三条 `core_intent_partial_without_terminal_gap` |
| Candidate Research handoff | eligible，重验通过；不是完整 Candidate authoring PASS |
| 实际生成 | 该报告 `model_calls_allowed=false`；不能据此宣布 Candidate/Verified 正文生成成功 |
| 新实施范围 | 工作树已包含 R8、R8 纠偏及 R9；R10 尚未开始，R9 迁移验证仍记为未完成 |

实现记录的最近全量 `3325 passed, 3 skipped` 绑定 F1–F4/R7；R8 纠偏记录定向 `474 passed`，
R9 尚没有对应的 G3 完整闭环证据。本轮未重跑这些历史测试。
R7 摘要绑定的文件中，当前 `formalization_agent.py`、`publication_method_writer.py`、
`unified_invocation_ledger.py` 已继续修改，所以旧离线报告不能直接验收当前扣账与 callback 路径。

上次探针本轮重新执行后，三条旧条件反例均被拒绝，合法 Writer join 页成功编译。
这两项局部修复应保留；以下发现是更完整输入和新路径上的问题。

## 2. 优先修复项

### P1-A：R9 把调用者填写的回执当成实际搜索证据

位置：`research_tools.py:2813`、`:2881`、`:3068`；
`research_models.py:802`；`research_terminal.py:792`。

`SearchReceiptV1` 当前唯一生产构造点在 `record_explicit_code_gap` 内，内容取自 tool arguments。
`search_code`/读取工具尚未产生并认证该回执。`frontier_closed()` 只判断查询/已读列表非空、
未读/截断/失败标记为空；不校验结果和已读集合对应、查询是否执行、scope 覆盖、结果摘要或关系证明。
内容摘要证明的是这份声明未变化，不能证明声明中的搜索发生过。

本轮通过真实 `execute_research_tool` 入口复现，fixture 中搜索与读取调用次数均为 0：

- 调用参数声称执行过 `search_code`、`read_code_span`；
- queries 为从未执行的查询；read candidate 不存在，result IDs 与 read IDs 不一致；
- 搜索范围为 `train.py`，receipt 的 filter scope 却为 `README.md`；result digest 为空；
- 工具返回 `success`，持久化 `unsupported_with_scoped_evidence`、
  `negative_evidence_authorized=true`、`search_complete=true`。

这已经是负证据生产边界的错误授权。本轮没有把它扩写成最终 Verified 已被穿透。

修复方向：回执由实际执行层生成，gap 工具接收回执 ID 并从当前 run/revision 的可信产物独立重验，
核对 snapshot、obligation、查询/过滤条件、截断状态、完整 result/read/unread 集合、内容摘要和
命题范围内的关闭依据。terminal 消费者复用同一认证结果，不能再复制一次布尔列表检查。
无认证证据时只允许诚实的未决/预算停止。保留三种终态区分，先禁止未认证的负证据授权。
R9 的旧 checkpoint→coverage→handoff→Writer 迁移必须在 R10 前完成。

### P1-B：R7 合法分页会清空 witness 合同，且未被 validator 拦下

位置：`unified_context_compiler.py:1710`、`:1815`；
`method_architect.py:7670`；产品调用位置 `publication_method_writer.py:2136`。

分页筛选使用 `target.detail_id.removeprefix("detail:") in fragment_detail_set`，
但实际合同有两种目标：detail 目标只有 `target_id`，atom 目标才有 `detail_id`。
前者必然被筛掉；后者的正式 ID 自带 `detail:` 前缀时，又被单边去前缀而无法匹配。

项目中立的正式 ID fixture 经过真实 plan builder→page revision：

```text
required detail 数量：3 → 3
witness targets 数量：6 → 0
fit failures：[]
validate_narrative_plan：[]
```

因此仅观察 required_detail_ids 守恒或 page fit 成功会漏掉 witness、条件与 authority 合同丢失。
当前测试/离线链不能据此证明分页保持了完整约束。

修复方向：按 target_kind 解析目标归属，保留 canonical ID；拆分前后核查完整 target 合同多重集守恒
（条件、极性、authority、anchor/exact 等）。修订后的 plan 重验并重算身份，实际 Writer request
也必须携带这些目标。公式不能统一搬到第一 fragment，必须证明该消费者拥有其完整 source detail
和依赖；多 unit 章节拆分时也不能把所有新段落挂到每一个 unit。

### P1-C：R5 条件判定仍然不是完整逻辑结构验证

位置：`publication_transaction_contract.py:668`、`:707`、`:766`、`:790`。

删除项目白名单和保留 AND/OR 是进展，但当前实现仍丢弃括号、负号，用词集合计算否定奇偶，
用无序对象词匹配比较式，并允许额外不重复声明词的子句。下列五项均被实际条件/极性约束函数放行：

| 声明 | 改写后被放行的条件 | 损失 |
|---|---|---|
| `(alpha or beta) and gamma` | `alpha or (beta and gamma)` | 布尔分组 |
| `value > -5` | `value > 5` | 数值符号 |
| `not not alpha` | `not alpha` | 重复否定次数 |
| `alpha < beta` | `beta < alpha` | 比较两端方向 |
| `alpha` | `alpha or beta` | 条件范围被扩大 |

修复方向仍是第一次报告的合同：实现条件保留可验证的完整表达结构；措辞等价交由既有独立语义
验证路径，绑定精确 witness 和冻结来源。受控表达式可用明确语法解析，但不能继续把词表、子句列表
和正则堆叠成事实授权器。未知语法/语义保持未证并返回 owning Agent 修复。
补这些反例到 Binder 与真实 Writer transaction 路径，不能只测私有 helper。

### P1-D：R8 权威差异遗漏配置改变、删除和既有 detail 合同变化

位置：`writing_callback_fulfillment.py:1733`、`:1799`、`:1806`、`:1432`；
`callback_dependency_closure.py:97`。

`_authority_delta_from_revision` 目前只读 claim 的部分合同字段与 detail ID 新增集合；
没有读取 configuration/equation/formula 合同，删除旧 claim/detail 不进入差异。
因此 closure mapper 能映射共享 configuration，不代表真实生产者会发出 configuration delta。

本轮使用真实 ConfigurationClaimSetV1 文件与现有共享配置 fixture：

- `config:shared` 的值由 true 变为 false；该配置由 MA-S1、MA-S2 共用；
- delta 与 affected sections 都为空，resume 保留请求中的 MA-S1，原因 `closure_empty`；
- 独立删除 `claim:alpha` 的探针，delta 同样为空。

另一个接线风险是差异在重建产物之后通过路径读取“旧值”；重建使用同一 out_root 持久化产物，
旧路径不等于旧字节。必须在写入前冻结 before 内容/身份，不能只保存两个路径字典。
此外 fact/operation/condition/formula 目前一律列 unresolved，尚未通过 source→detail 的依赖传播。

修复方向：从不可变 before/after revision 计算所有授权对象的 added/changed/removed；
同时通过旧依赖图和新依赖图传播，保证已删除/降级事实原来支持的兄弟正文也失效。
无法确定差异或归属时明确阻塞，不能当作空差异继续。以实际 callback 重建和请求截获验证恢复范围，
不要只手工构造一个完整 delta 测 mapper。

### P1-E：R7 普通章节分支仍按位置复用身份

位置：`method_architect.py:8192`、`:8530`。

typed owner 修复只进入 `prior_sections > contexts` 分支。两机制、两个章节且旧 outline 反向排列时：

```text
sec_method_2：heading=mech_beta，owner beta → alpha
sec_method_1：heading=mech_alpha，owner alpha → beta
validate_narrative_plan = []
```

应把同一身份映射合同用于少于/等于/多于三种数量关系；按稳定 section ID 对照旧 owner 与新 owner，
显式记录合法 revision、unit/dependency/rationale 保全，不能只比较新 plan 内部字段相互一致。
同机制多章节仍按数量分摊 detail 也不能证明章节论证意图正确。
proposal caller 目前仍只记录 `narrative_proposal_not_consumed`，R7 的自主组织部分尚未完成。

### P1-F（live 前）：跨 revision 的预算仍会漏记历史消费

位置：`unified_context_compiler.py:3195`；`unified_invocation_ledger.py:235`；
`publication_method_writer.py:3084` 与 Formalizer/Realizer 对应调用。

本轮未观察到真实超支；以下是当前预算计算边界的可复现缺口：

- caller 只传当前 plan digest 统计 receipt，但 reservation 累积父计划额度；
  旧 plan 已消费 900、累计 reservation 2000 时，换 plan digest 后返回剩余 2000，而非 1100。
- 旧页 started 但未 completed，在新 plan 中找不到旧 invocation 时，其预留 tokens 变成 0；
  因而跨页/revision 的中断消耗并未被新补的 unsettled 逻辑完整覆盖。

修复方向：消费绑定 run/envelope 与完整修订谱系，实际请求、已拒绝未发送请求、未知是否发送的
started attempt 分开计量；旧页预留从其原始计划/持久扣账记录读取。原子发布单个 receipt 不自动
等于 read-check-debit 原子事务，需绑定发送边界与恢复协议。
冻结计划 1,938,180 / 2,000,000 的差额 61,820 只是计划额度差，不能声称是已验证的重试余量。

## 3. 执行顺序建议

1. **先停止 R9 未认证负证据授权，修条件和分页合同丢失。** 保留诚实未决终态，R10 暂不进入。
2. **统一 R7 的三种章节数量路径。** 同时补齐 canonical target 守恒、公式消费者、修订身份与
   controller→实际 request 的验证；不要继续只以页数/编译完成作为接受标准。
3. **补 R8 的真实 delta 生产与前后 revision 冻结。** 配置变更、事实删除/降级、共享依赖和中断
   必须沿真实 callback 流程触发正确恢复范围。
4. **完成 R6 跨 revision 扣账与 R9 完整迁移后做集成检查点。** 静态里程碑与冻结离线链绑定当前
   代码，分别报告编译成功、admission、模型调用、正文提交和最终验证；旧测试数不能挪作当前验收。
5. **将真实研究证据缺口单独推进。** 配置选择/入口路径证据属于 Research；保持三条 partial 与
   Candidate/strict 分列。满足现有授权和结构前置后，再做有预算的单项目补证/诊断，正式扩项仍走矩阵门。

不建议继续“消掉眼前错误码后就把切片记为完成”。本轮直接证明，同一 plan 能同时满足页预算、
detail 数量和 schema 校验，却已经丢失全部 witness targets。退出证据必须覆盖实际授权对象与来源。

## 4. 本轮证据和验证范围

- [独立探针脚本](../.tmp/c2p-direction-review-20260913/review_probes.py)。
- [完整结果与十二个生产文件 SHA-256](../.tmp/c2p-direction-review-20260913/probe-results.json)。
  其中保存新旧 narrative plan、typed config 文件和实际写出的 terminal gap 所在 fixture 目录。
- [旧探针重查结果](../.tmp/c2p-direction-review-20260913/prior-probes-recheck.json)。
  旧脚本四章节输出按位置 zip 的 `prior_owners` 不适用于重排序后的逐 ID 比较；本报告未据此报错，
  P1-E 使用独立的两章节反序探针。

精确命令：

```bash
python .tmp/c2p-direction-review-20260913/review_probes.py > .tmp/c2p-direction-review-20260913/probe-results.json
python .tmp/c2p-direction-review-20260912/review_probes.py > .tmp/c2p-direction-review-20260913/prior-probes-recheck.json
```

两条命令均 exit 0，模型调用为 0。新脚本开头/结尾校验十二个生产文件字节身份未变化。
探索阶段曾因读取不存在的 observation.output_payload、重建 fixture 未清除 source_context_digest
出现诊断脚本错误；已改为读取真实持久 gap 和重建派生摘要后复现，不计为生产故障或测试结果。
没有运行完整 pytest、live、性能基准或 provider API。

当前文档状态仍不一致：README 写 R7 已完成且又保留“R7–R10 未开始”；计划顶部写 R8、R9 未开始，
实现记录却已有 R9。建议下一次实施更新把“已编码 / 定向验证 / 集成接受 / 实际运行”分开记录，
本报告不覆写正在执行任务的计划和日志。
