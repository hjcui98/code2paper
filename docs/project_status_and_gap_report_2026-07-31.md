# Code2Paper 项目进度与目标差距报告

- `as_of`: 2026-08-01
- `status`: R8 六个真实项目 6/6 accepted；clean-checkout release freeze 待完成
- `analysis_basis`: R8 已实际通过，不再使用“假设通过”口径；权威摘要见
  [`r8_acceptance_status_2026-08-01.md`](r8_acceptance_status_2026-08-01.md)
- `scope`: 自主代码研究、Method 写作、证据约束、图示与产品切换
- `supersedes`: 仅取代旧报告中的“当前项目状态”表述，不改写其历史实验记录

## 结论

R8 六项目已经全部通过，但项目并不是“全部完成”，而是完成了最重要的一次
已知项目运行演练：live Agent、checkpoint、当前证据门、completion 和 readiness
能够在同一长流程中运行。它不能证明自主 Research Agent 已编译出最终证据，因为
四个已落盘项目的 generic sidecar 没有 claims，最终事实仍来自具名 profile。

由于“项目完成度”取决于目标范围，不能用一个百分比概括：

| 目标口径 | 当前 R8 六项目通过后的工程完成度 | 仍需完成 |
|---|---:|---:|
| 已知项目当前协议/运行工程 | 约 80%–90% | 约 10%–20% |
| 可信自主、信息完整的 Method 研究写作核心 | 约 50%–60% | 约 40%–50% |
| 可作为默认产品交付的通用 Code-to-Paper | 约 35%–45% | 约 55%–65% |

以上是工程置信区间，不是验收指标。较早的 75%–85% 核心完成度估计在检查四项目
paper/claim/final-text artifact 后不再成立：generic research 没有产出 claims、
具名 profile 仍拥有事实、正文信息覆盖过低且 repair 不是 Agent-owned。R8 的
pass/fail 已由六份统一 17 项 rechecked report 确认。当前仍不得把该结论扩张为
“可投稿 Method 完成”或“默认产品可切换”。

四个已落盘项目与原论文的专项对照见
[R8 四项目 Method 与原论文覆盖审计](r8_method_paper_coverage_audit_2026-07-31.md)。
该审计表明当前 accepted 结果仍只有 8–9 条压缩 implementation claims、0 safe
equations/0 safe numerics，且三个项目的正文被 deterministic 规则直接修改而没有
Rewrite Agent trace。因此当前协议通过不能等同于“Method 已完整”或“Agent 已完成
自修复”。

## 真实目标

本项目的目标不是让固定模板在几个仓库上产出文字，而是形成一个可自主运行的
研究写作 Agent：

1. 接收作者意图和代码仓库，自主决定应该调查哪些实现行为；
2. 通过细粒度代码工具形成 `CodeBehaviorGraph`、evidence packet、fact 和
   atomic claim，而不是依赖项目名或手写答案；
3. 作者意图决定研究重点与组织方式，可执行代码决定哪些事实可以写入或绘制；
4. validator 发现问题后，把 typed error 返回 owning Agent 做局部、有界修复；
5. harness 只兼容括号、逗号、截断等简单结构损伤，不能通过过滤内容、放宽硬门
   或减少 obligation 冒充成功；
6. 最终文字、公式、图示和交付包中的事实均可追溯到相应冻结 authority；
7. 最终正文 lexical token 均来自 Writer/Rewrite 响应，规则只检测、反馈和复验；
8. atomic claims 只作为验证单元，经 argument graph 组织成原理、形式化、机制、
   实现和输出完整的论文小节；
9. 写作发现缺失信息时能返回 Research Agent、Formalization Agent 或作者确认，
   而不是把 Method 压缩成已知 claim 摘要；
10. 在未知仓库、不同模型、不同语言和中断恢复条件下仍保持上述性质。

## R8 通过能够证明什么

R8 通过后，可以正式声明：

- 六个项目均通过统一 17 项当前协议重检；结果来自两个串行 matrix，报告与 resume
  digest 已汇总持久化，不冒充一次单矩阵 clean-checkout freeze；
- 正式 API 调用、角色配置和 generation trace 可追踪，非缓存 live 路径成立；
- 当前 Python 运行能落盘 intent、obligation、evidence、claim、final text 和验收
  artifact；但旧 criterion 不证明它们来自同一 generic compiler provenance；
- 已知输入上的 unsupported leakage、completion/readiness、checkpoint digest
  等当前硬门全部通过；
- 有界 thinking/output 配置可在真实长流程上运行，不需要把规则降级为软检查。

这足以把项目从“只有架构和单元能力”推进到“真实长流程已被演练”，但还不足以
声明“自主研究到完整 Method 的可信主链路已经被验证”。

## R8 通过仍不能证明什么

R8 是必要条件，但不能单独证明：

- **无项目特权的泛化。** 六个项目及其 evidence profile 已参与开发；尚需从未见
  仓库证明无需新增项目名、symbol literal 或定制 profile 也能完成研究。
- **恢复等价性。** 代码已有 checkpoint、完成态恢复和 best-state 保留路径，
  但仍需 live 证明中断恢复与 uninterrupted run 等价，并确认完成态 replay
  是否真正零调用。
- **自修复覆盖充分。** packet-scoped repair、typed issue、按 obligation 预算和
  结构恢复已有实现基础；仍需用真实内容错误、引用错误、长输出截断和重复输出
  证明 Agent 能局部修正且不会污染已通过的义务。
- **研究与写作质量达到产品标准。** `unsupported=0` 证明安全边界，不自动证明
  Method 完整、准确、简洁、不重复、符合作者意图或优于人工基线。
- **可投稿 Writer 闭环。** 当前只有保守 section writer/projection 路径，尚未
  实现 Method Architect、argument graph、Formalization、Cross-section Editor
  和 writing-time research callback。
- **语言通用。** 架构定义了 `LanguageBehaviorAdapter`，当前生产研究节点仍主要
  实例化 `PythonBehaviorAdapter`，不能据此声明支持任意语言。
- **模型与部署通用。** 单一 Qwen/profile/API 的成功不能代表不同 provider、
  sampling、上下文长度和推理模式。
- **默认产品切换。** migration policy 明确要求 `shadow → opt-in → canary →
  default_ready`；R8 不会自动把 agentic route 设为默认。
- **完整论文自主生成。** 当前最强证据集中在 Method 和代码图示。Introduction、
  Related Work、Experiments 等章节需要论文、数据集和运行结果等不同证据源，
  不能用代码证据规则直接代替。

## 当前能力地图

| 能力 | 当前判断 | 说明 |
|---|---|---|
| Intent 与代码证据分权 | 已实现，R8 已验证 | 意图控制优先级，证据控制事实授权 |
| Python 行为图与细粒度工具 | 已实现，六项目已运行 | `LanguageBehaviorAdapter` 目前只有 Python 主实现 |
| Evidence/fact/claim/final-text 信任链 | 组件已实现，generic 主链未闭合 | 四项目 generic sidecar 为 0 claims，最终仍由具名 profile 授权 |
| 公式授权 | 已实现 | 已有 `EquationClaimV1` 合同与投影/验证路径 |
| 图示与 post-render audit | 已实现，需产品级复验 | 与最终 package 的全场景一致性仍需持续验证 |
| Typed self-repair | 合同部分存在，正文路径不合格 | 三项目由规则直接改正文且无 Rewrite trace；必须改为 owning Agent repair |
| 简单结构错误兼容 | 部分完成 | 需继续覆盖截断、重复 JSON、内容/格式分离组合 |
| 可投稿 Method Writer | 设计已明确，尚未实现 | 当前仍是保守 section/projection 路径；缺 Method Architect、argument graph、Formalization、Editor 和 writing-time research callback |
| Checkpoint/resume | 部分完成 | digest/恢复路径存在；live 等价与零调用 replay 待证 |
| Benchmark/cutover 工具 | 已实现 | rollout 证据和默认切换尚未完成 |
| 非 Python 语言 | 未完成 | 缺少第二个生产 adapter 与相应真实项目矩阵 |
| 完整论文多章节 | 未完成/不在当前 R8 范围 | 需建立新的证据 authority 与验收协议 |

## R8 之后的优先执行顺序

具体模块、测试、依赖和退出条件见
[R8 后 Research Agent 具体开发执行计划](post_r8_research_agent_execution_plan_2026-07-31.md)。

### P0：完成“可信自主 Method”定义

1. **冻结 R8 release evidence。** 六项目 pass/fail 已确认；下一步提交当前修复并从
   干净检出归档 commit、matrix ID、API/profile、artifact manifest、摘要和 recheck，
   使证据不依赖临时 run root。
2. **闭合 generic evidence compiler 并收回 profile 事实权限。** 未知项目必须由
   search/read 形成 packet/fact/claim，profile 只能提供 discovery hint。
3. **Reference Method 覆盖与质量门。** 论文/作者输入只生成搜索义务，不授权
   实现事实；逐项建立 supported/partial/mismatch/external-evidence/gap 矩阵，
   并评价重复率、结构连贯性和人工可编辑性。
4. **可投稿 Writer 工作流。** 将 atomic claim 与论文论证单元分离，开发 Method
   Architect、Section Research Writer、Formalization、Cross-section Editor 和
   写作中返回研究；多权威事实经匹配验证后才能进入 publication candidate。
5. **真实自修复、authorship 与恢复矩阵。** 每个正文 lexical span 回溯到
   Writer/Rewrite generation；同时覆盖 JSON 损伤、长输出截断、内容/引用错误、
   公平轮转、best-state、中断恢复和完成态 replay。
6. **无特权 holdout。** 至少选择两个开发期间未见的真实仓库，禁止新增
   project-specific profile、项目名分支和 symbol literal；加入重命名、行漂移、
   文件拆分等 mutation。

完成 P0 后，才适合声明“可信自主 Method 核心完成”。

### P1：证明通用性

6. **跨模型/provider 矩阵。** 以 capability profile 表达差异，不把某模型的
   sampling 或 token 数写死成全局协议。
7. **第二语言适配器。** 实现并验证至少一种非 Python 语言，包括调用关系、
   配置/build graph、动态行为的 evidence/gap 表达。
8. **最终图示与交付包复验。** 保证文字、公式、图节点/边、TeX/PDF 和 manifest
   使用同一证据链，且 post-render audit 在真实项目上通过。

### P2：完成产品化和默认切换

9. **正式 rollout。** 依次收集 shadow、opt-in、canary 证据，演练 incident 与
   rollback，最后由 cutover gate 产生 `default_ready`。
10. **运行治理。** 补齐版本迁移、可观测性、并发与成本上限、失败归因、artifact
   保留策略和可复现实例。
11. **若目标包含完整论文，扩展证据域。** 为文献、数据集、实验结果和外部事实
    建立独立 authority、引用和验收机制，再扩展到 Method 之外的章节。

## “真实目标完成”的判定标准

只有同时满足以下条件，才应把整个项目标记为完成：

- 当前协议 R8 从干净检出正式通过；
- 未见仓库不依赖项目特权即可通过；
- 内容错误能由 Agent 修复，简单格式错误由 harness 恢复，二者边界有回归测试；
- 中断/恢复、best-state 和 replay 在 live 条件下可复现；
- 至少两个模型/provider profile 和两个语言 adapter 通过各自真实矩阵；
- Method 质量/可用性评价通过，而不仅是 unsupported 为零；
- shadow、opt-in、canary 完成，cutover 决策达到 `default_ready`；
- 若承诺完整论文，则非代码证据域与多章节验收也已完成。

在此之前，最准确的项目表述是：**自主可信 Method 主链路接近闭环，通用化与
产品化仍在进行。**

## 文档阅读顺序

1. [文档导航](README.md)
2. [自主错误反馈与自修复原则](agentic_error_feedback_and_self_repair_principle.md)
3. [结构化输出恢复策略](agentic_structured_output_recovery_strategy.md)
4. [鲁棒 Research Agent 总体设计](agentic_robust_langgraph_research_writing_design_2026-07-19.md)
5. [R8 四项目 Method 与原论文覆盖审计](r8_method_paper_coverage_audit_2026-07-31.md)
6. [可投稿 Method Writer Agent 设计](publication_ready_method_writer_design_2026-07-31.md)
7. [R8 后具体开发计划](post_r8_research_agent_execution_plan_2026-07-31.md)
8. [Method 质量历史执行计划](agentic_method_quality_next_execution_plan_2026-07-19.md)
9. [迁移与切换指南](agentic_migration_guide.md)

旧审计和 JSON 证据的分类见[文档导航](README.md)。它们用于追溯历史，不覆盖
本报告的当前状态。
