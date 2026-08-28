# Code2Paper Method Agent 现状复盘、Master Agent 主线与下一阶段代码级修复方案

- 日期：2026-08-17
- 文档性质：独立的上位复盘与执行文档
- 最终产品路线：新 Method Agent
- 最终总流程：Master Agent 顶层 LangGraph
- 当前前置状态：`.agent/review.md` 的 Round 7 结论仍是 `REPAIR`
- 适用范围：正式入口、旧路线隔离、研究子图、Concept Card、文章规划、Writer、写作回调、
  最终校验、检查点、终态和验收

## 0. 先给决策结论

本轮代码审计后的结论如下。

第一，新 Method Agent 的研究过程不是一段需要“重新包装”的普通 Python 循环。
`src/code2paper/agentic/research_graph.py` 已经用 LangGraph 实现了真实的多节点研究循环，包括研究
问题选择、工具调用、观察吸收、证据判断、事实编译、明确缺口和终止路由。这里不应再造一套重复图。

第二，当前仍然由普通 Python 顺序串联的是研究之外的整条产品流程：输入、研究结果汇总、Concept
Card、文章计划、Writer、写作回调、最终校验和产物发布。下一阶段需要新增的是这一层真正负责路由和
恢复的 Master Agent LangGraph。

第三，仓库里现在实际存在三条流程，而不是一条：

1. 最早的故事驱动 Phase 1–5 流水线；
2. 旧 R8 固定阶段 Agentic LangGraph；
3. 新 Method Agent 产品路线。

最终只把第三条路线继续建设成产品主线。前两条不立即删除：入口保留为明确的旧版或评测入口，代码
冻结，只复用其中与流程无关的通用服务。新 Master Agent 不调用前两条路线的编排器。

第四，新 Method Agent 已经有相当多正确能力，但仍存在多处跨模块风险，不能只增加一个顶层图就算
完成。最重要的包括：

- 当前 Writer/Rewrite 的条件修复仍未通过真实批次验收；
- 安装后的 `code2paper` 命令没有真正暴露新 Method Agent 的完整入口；
- Method Agent 成功返回码不能反映 Writer 或最终校验失败；
- Concept Card 可以静默退回旧 proposition 路线；
- Concept Card 的证据来源丢失了部分精确代码关系，字段绑定仍依赖词语重合；
- Concept Card 到章节、最终句子和原子陈述的归属存在过宽或静默遗漏的情况；
- Concept 路线的分节检查点没有绑定 Concept Card 摘要，可能复用错误的旧章节；
- 写作中的仓库回调没有回到原研究管理器，而是在冻结事实中做一次简化搜索；
- 形式化回调可能用整份形式化结果满足一个并未被它精确支持的问题；
- Writer 的模型可见输入已经相对精简，但后台校验仍依赖旧 `MethodEvidence`、旧 claim map 和旧
  authoring projection 三个兼容产物，不能直接删除。

因此，下一阶段不是“把 Python 换成 LangGraph”这么单一，而是先关闭现有发布缺陷，再逐层收紧数据
合同，最后把已验证模块接入顶层图。

## 1. 文档权威与使用规则

本文件是用户明确要求另写的上位文档，不复用、也不覆盖 `.agent/task.md` 或 `.agent/plan.md`。

权威顺序如下：

1. `docs/agentic_robust_langgraph_research_writing_design_2026-07-19.md` 继续约束总体架构和信任方向；
2. `docs/publication_ready_method_writer_design_2026-07-31.md` 继续约束 Writer 质量和多来源事实分权；
3. 本文件约束新 Method Agent 主线、Master Agent 编排、旧路线处置和下一阶段实施顺序；
4. `docs/post_r8_research_agent_execution_plan_2026-07-31.md` 保留 R8 历史批次、评测和 rollout 背景，
   但不再决定未来产品主线；
5. `docs/project_status_and_gap_report_2026-07-31.md` 只在其引用证据范围内说明状态；
6. `.agent/` 下的四个文件只协调一次具体实施和验收，不能降低本文件规定的门槛。

如果一次实施与本文件冲突，停止实施并返回 Codex，不能静默保留第四条产品路线，也不能通过删减
校验来换取“成功”。

本文件对代码名称采用以下规则：出现文件名或函数名时，紧接着说明其模块职责。文件名用于准确定位，
不要求汇报读者理解代码符号本身。

## 2. 本次复盘范围与事实边界

本次复盘阅读了文档入口、总体架构、Writer 设计、当前执行计划、状态报告、最新只读验收结论，以及
三条流程的入口、编排、研究、概念、规划、写作、回调、校验和检查点代码。

重点代码范围包括：

- `pyproject.toml`：安装命令实际指向哪里；
- `src/code2paper/main_cli.py` 和 `src/code2paper/run_cli.py`：最早的故事驱动入口；
- `src/code2paper/agentic/runner.py`、`graph.py`、`graph_topology.py`：旧 R8 固定阶段路线；
- `src/code2paper/agentic/autonomous_method_agent.py`：新 Method Agent 当前外层顺序编排；
- `src/code2paper/agentic/research_graph.py`、`state_v3.py`、`checkpointing.py`：研究子图及恢复；
- `src/code2paper/agentic/method_concept_card_*.py`：Concept Card 生成和逐字段证据判断；
- `src/code2paper/agentic/method_architect.py` 和 `method_argument_models.py`：文章结构规划；
- `src/code2paper/agentic/writer_view_projection.py`、`publication_method_writer.py`、
  `src/code2paper/llm/section_writer.py`：Writer 输入和发布流程；
- `src/code2paper/agentic/writing_callback_fulfillment.py` 和 `writer_research_router.py`：写作回调；
- `src/code2paper/agentic/final_text_claims.py`、`text_evidence_validator.py`、
  `publication_quality.py`、`trust_contracts.py`：最终反向校验与质量门。

本次没有运行测试、模型、真实 API 或基准；关于运行结果只引用 `.agent/review.md` 已冻结的证据。仓库
当前有大量既有未提交改动，这些改动属于当前基线，本文件不把它们误报为本轮新增。

用户先前复制的“stage2 开发完正在测试、stage 3/4/5 初步开发完”不是有效状态，本文件不使用该说法。

## 3. 当前实际存在的三条路线

### 3.1 路线总表

| 路线 | 当前入口 | 实际编排 | 当前用途 | 后续处置 |
|---|---|---|---|---|
| 最早故事驱动路线 | 安装命令 `code2paper` 当前指向 `main_cli.py`；另有 `code2paper-run` | Python 顺序执行 Phase 1–5 | 历史兼容、旧输出复现 | 明确标记 legacy，冻结编排，不再扩展 |
| 旧 R8 Agentic 路线 | `code2paper-agentic-run`，以及旧 `run_cli.py` 的 `agentic/shadow` 分支 | 固定阶段 LangGraph 加 V3 研究桥接 | R8 评测、历史对照、回滚 | 保留独立入口和评测工具，不进入新产品主图 |
| 新 Method Agent | `cli/agentic_run.py` 内部的 method-agent 入口；安装后尚未完整暴露 | 研究内部是 LangGraph，外层仍是 Python 顺序编排 | 未来唯一交付产品 | 修复后由 Master Agent 顶层 LangGraph 调度 |

### 3.2 最早故事驱动路线

主要文件：

- `src/code2paper/main_cli.py`：安装后的 `code2paper` 当前入口，提供 `run/intake/analyze/evidence/author/validate`；
- `src/code2paper/run_cli.py`：一键 Phase 1–5，并包含 legacy、agentic、shadow 三种历史切换；
- `src/code2paper/pipeline/orchestrator.py` 和 `src/code2paper/pipeline/stage*.py`：顺序阶段编排；
- `src/code2paper/pipeline/stages/`：另一套阶段实现和兼容入口。

它的核心顺序是：代码摄取 -> 代码分析 -> MethodEvidence -> 写作 -> fidelity 检查和可选图形。它以旧
MethodEvidence 和 claim map 为中心，与新 Method Agent 的“研究问题 -> 精确代码证据 -> Concept
Card -> 分节写作”不是同一产品模型。

后续不改造这条路线为 Master Agent，也不让它为新主线提供事实。它只在显式旧版命令下运行。

### 3.3 旧 R8 Agentic 路线

主要文件：

- `src/code2paper/cli/agentic_run.py` 中的 `main`：`code2paper-agentic-run` 的入口；
- `src/code2paper/agentic/runner.py`：旧 Agentic 运行器；
- `src/code2paper/agentic/graph.py`：固定阶段 LangGraph 构建器；
- `src/code2paper/agentic/graph_topology.py`：输入、摄取、分析、证据、grounding、写作、验证、渲染、
  收尾等固定节点；
- `src/code2paper/agentic/v3_runtime.py`：先运行 V3 研究，再把结果接回旧固定阶段图的历史桥接器。

这条路线已经是真 LangGraph，但它的图是“旧流水线的图形化外壳”。`v3_runtime.py` 中的桥接器会运行
自主研究，再继续跑旧阶段图。这正是新主线不能照搬的地方：如果 Master Agent 复用这个桥接器，就会
重新把新研究接回旧写作流水线。

可复用的是其中的通用机制，例如稳定线程 ID、SQLite checkpointer、仓库快照校验、运行摘要和摘要
绑定思路；不可复用的是旧固定阶段拓扑和“V3 研究 + 旧图”的整条包装。

### 3.4 新 Method Agent 路线

主要入口在 `src/code2paper/agentic/autonomous_method_agent.py` 的
`run_autonomous_method_agent`。这个函数的含义是“当前整条 Method Agent 产品顺序流程”。

当前真实调用顺序如下：

1. 读取作者意图和用户声明；
2. 冻结仓库快照，编译研究问题清单；
3. 构建研究运行环境和研究管理器；
4. 调用现有研究 LangGraph；
5. 从研究循环内存结果汇总证据包、代码事实和原子陈述；
6. 写一个研究阶段 JSON 检查点；
7. 编译覆盖、完整性、公式、配置和文章故事顺序；
8. 生成 Concept Card，或者在条件不满足时退回 proposition；
9. 构建章节和论证单元；
10. 为旧 Writer 校验接口生成三个兼容产物；
11. 调用分节 Writer；
12. 在 Writer 返回请求后运行一个独立的简化回调循环；
13. 只恢复受影响章节；
14. 运行 Editor、Rewrite、最终句子拆分、证据反查和质量检查；
15. 写候选稿、仓库已验证稿、作者确认清单和运行摘要。

这条路线功能最接近最终产品，但步骤 1–15 目前由一个约两千行文件中的普通 Python 控制。节点状态、
阶段路由和中断恢复没有被一个顶层图统一拥有。

## 4. 当前新 Method Agent 的模块和工作方式

### 4.1 输入和仓库冻结

`autonomous_method_agent.py` 中的 `build_product_research_runtime` 是“构建研究运行环境”的入口。它：

- 验证仓库路径；
- 创建仓库快照和代码树摘要；
- 读取作者意图；
- 把用户声明补入研究义务；
- 生成研究清单；
- 创建研究管理器后端和工具环境。

正确点是作者意图只决定研究范围和文章组织，不直接授权实现事实。需要保留。

### 4.2 自主研究

`research_graph.py` 的 `build_research_subgraph` 是“研究 LangGraph 构建器”。当前拓扑是：

```text
输入与研究清单初始化
  -> 研究管理器选择下一步
  -> 代码工具执行
  -> 观察结果吸收
  -> 证据充分性判断
       -> 继续搜索
       -> 编译证据
       -> 记录明确缺口
       -> 安全阻止
  -> 推进到下一个研究问题
  -> 终止
```

研究图已经支持传入 LangGraph checkpointer。它还会把行为关系、信息增益、预算、观察、决策轨迹和
已编译证据写入不可变、按摘要命名的 JSON，再在图状态里保存引用和摘要。恢复时会检查文件位置和
摘要，不是完全从零开始。

当前产品调用的问题不在研究图内部，而在
`run_product_research_phase`——“Method Agent 调用研究阶段的薄包装”——没有传入 checkpointer 或
线程配置，并通过图外的 `last_result` 内存属性获取完整结果。这个方式适合一次进程内运行，不适合
顶层图跨进程恢复或父子图组合。

### 4.3 证据汇总

`merge_product_evidence` 是“合并每个研究问题的证据”的适配函数。它会去重证据包、代码事实和原子
陈述，并把原子陈述重新绑定到研究义务。

这部分可以继续作为确定性服务，但必须让输出成为文件支持的、带运行 ID、仓库快照和摘要的研究结果
合同，不能只从 Python 对象读取。

### 4.4 Concept Card

当前 Concept Card 分为四种来源：仓库、作者意图、外部材料、形式化。主要文件如下：

- `method_concept_card_models.py`：Concept Card、逐字段判断和绑定格式；
- `method_concept_card_compiler.py`：从原子陈述分组、调用 Concept Architect、绑定字段并做硬校验；
- `method_concept_card_provider.py`：Concept Architect 的模型请求；
- `method_concept_card_evidence_provider.py`：逐字段 Evidence Judge 的模型请求。

已有的正确边界包括：

- 每个字段是短语，不允许整段 prose；
- 仓库来源和作者意图分开；
- 作者意图不能进入已验证稿；
- 每个正向字段都需要单独判断；
- 模型只能选择封闭的 fragment 引用；
- 没有 Concept Architect 时记录明确缺口，不由规则层生成论文语言。

但当前候选输入只保存“原子陈述的规范句子 + 一组 span ID”。字段绑定先看模型选中的 fragment，再用
英文词语重合选择具体 fragment；代码调用关系、数据流关系、精确 claim/fact 归属没有完整保存在每个
fragment 里。目的判断还依赖一组硬编码英文词语。因此，它目前还不是最终可信的概念证据合同。

### 4.5 文章规划

`method_architect.py` 是“把证据和作者意图组织成章节”的模块。它构建章节、论证单元、章节之间的依赖、
必需写作动作、公式、配置和未解决项。

Concept Card 当前按来源义务与论证单元的义务求交集进行放置。一个卡片如果匹配多个单元，会按单元
遍历顺序放入第一个；如果一个也匹配不到，可能不进入任何单元，但没有一份完整的“全部卡片均已放置
或明确转为缺口”的报告。这会造成概念静默丢失。

### 4.6 Writer 输入

`writer_view_projection.py` 构建四层 WriterView：

1. 本节目的和读者问题；
2. 可以正向写出的概念；
3. 必须带说明、只能进入候选稿的概念；
4. 数字、公式、条件和回调机会等不可随意改变的约束。

`src/code2paper/llm/section_writer.py` 中的 `_llm_visible_section_payload` 是“过滤模型可见输入”的函数。
只要存在 WriterView，它已经会把大量内部 claim/fact/frame ID 留在后台，不发给 Writer 模型。这一点
是正确的，不需要推倒重来。

问题在后台校验合同：`publication_method_writer.py` 仍会载入完整原子陈述、事实、公式、配置、计划和
兼容的 authoring projection；最终反向校验还要求旧 `MethodEvidence`。所以“模型看到的接口”已经较
小，“模块之间真正依赖的接口”仍然很大，两者要分开处理。

### 4.7 Writer、Editor 和 Rewrite

`publication_method_writer.py` 是当前发布写作中心，约 8,600 行。它负责：

- 校验冻结输入；
- 按节调用 Writer；
- 保存分节不可变检查点；
- 读取和应用回调；
- 调用跨节 Editor；
- 生成局部 Rewrite 问题；
- 对每次修改做非退化事务检查；
- 拆分候选稿和已验证稿；
- 运行最终反向校验和质量门；
- 发布所有结果和追踪文件。

功能完整但职责过多。下一阶段不能一边接 Master Agent、一边大规模重写全部 Writer。应先通过窄接口
把它作为一个可调用子系统接入，再分批拆出输入构建、修改事务、最终校验和发布四个服务。

### 4.8 写作回调

当前回调流程由 `writer_research_router.py` 决定责任来源，由
`writing_callback_fulfillment.py` 执行。

来源分配本身是合理的：仓库问题去仓库工具，配置问题去配置处理，公式问题去形式化，作者、文献和
实验问题进入外部队列。

但仓库回调当前不是原研究管理器的继续运行。它新建一个简化 provider，按固定顺序做符号搜索和文件
读取，然后只能把新观察匹配到运行前已存在的代码事实。它不能生成新的证据包、代码事实、原子陈述
或 Concept Card 判断。因此“Writer 发现原研究遗漏”时，它没有能力真正补齐研究链。

### 4.9 最终反向校验

当前最终校验会：

- 把最终正文拆成原子句；
- 把句子映射到本节允许的概念；
- 将概念再映射到原子陈述；
- 根据证据包、条件、数字和公式判断支持、带说明、未支持或未验证；
- 根据 verdict 构造仓库已验证稿；
- 检查作者来源记录、章节完整性、重复、代码痕迹和概念覆盖。

Concept 路线当前仍借用 proposition 命名字段承载 Concept key，并通过本节概念的词语重合选择一个概念。
随后，概念不是映射到它实际使用的精确 claim，而是扩大到同一来源义务下的全部 claim。虽然下游还会
继续做证据匹配，这仍会放宽候选范围并造成错误归属。下一阶段必须拆掉这层兼容借名和义务级扩大。

## 5. 当前已经做对、必须保留的机制

以下机制在后续重构中必须原样保留其安全含义：

1. 最终正向 Method 事实必须来自冻结仓库证据和反向校验；
2. 作者意图只负责范围、组织和候选内容，不负责实现事实授权；
3. 候选稿、仓库已验证稿和作者确认清单分离；
4. 仓库、作者、外部材料、配置、形式化等来源分开；
5. 缺失、过期、摘要不一致、来源歧义时失败关闭；
6. 研究工具有预算、无进展判断和重复调用限制；
7. 研究图有真实多节点路由，不是单函数伪图；
8. 研究检查点的大对象已放在按摘要命名的不可变文件中；
9. Writer 只允许 Writer、Formalizer、Editor 或 Rewrite 产生最终 prose 词语；
10. Writer 模型可见输入已通过 WriterView 隐藏大部分内部 ID；
11. 分节 Writer 输出采用不可变文件和摘要检查；
12. 已发布回调 bundle 的相对路径和文件摘要校验；
13. 已接受的“支持句只覆盖其实际章节”，不能退回全篇平铺覆盖；
14. 已接受的正文和标题结构检查必须继续失败关闭；
15. 局部修改只有在目标问题改善且其他安全维度不退化时才提交。

## 6. 已确认的问题清单和代码级修复方向

### 6.1 P0：条件修复与 Method 风格检查仍可能互相锁死

证据：`.agent/review.md` 的 Round 7 `REPAIR`。真实批次中 Rewrite 已生成要求的精确条件，但修改事务
仍以 `method_style_regressed` 拒绝。

根因是条件授权来源曾有两份：最终质量门从冻结 plan/claims 读取，局部修改事务从 Writer 输入子集读取。
当前工作树已有向统一映射收敛的代码，但尚未被新的三项目最终批次验收，不能声明完成。

必须修改的代码位置：

- `publication_method_writer.py` 的 `_qualifier_terms_by_section`：生成“章节 -> 精确条件”的唯一基线；
- 同文件的 `_rewrite_transaction_metrics`：局部修改前后都使用同一基线和当前 validator verdict；
- `publication_quality.py` 的 `_remove_authorized_qualifier_bindings`：只允许括号中的完整反引号条件，不
  允许把正文中任何相同代码词语全局删掉后再检查；
- 修改事务追踪：保存修改前后 style 片段、章节条件清单、目标 verdict 数量和拒绝原因。

完成条件：嵌套括号、tuple membership、数组下标、点式配置、`.shape[0]`、`len(...)` 等条件均在授权
形式中通过；同节其他未授权代码仍被检出；DyG、LinearRAG、EBCAR 在同一最终代码摘要上重新通过。

### 6.2 P1：正式命令入口分裂

当前 `pyproject.toml` 把 `code2paper` 指向 `src/code2paper/main_cli.py`，这是旧故事驱动 CLI。
`src/code2paper/cli/main.py` 虽然有 `method-agent` 子命令，却不是安装后的 `code2paper` 入口，而且没有
转发 `--concept-cards` 和 `--compile-concept-cards`。

修复：

1. 把安装命令 `code2paper` 指向 `code2paper.cli.main:main`，即当前较完整的统一命令分派器；
2. 在 `cli/main.py` 补齐 Concept Card、Master checkpoint、resume、回调预算和失败返回参数；
3. 可新增直接命令 `code2paper-method-agent` 指向 `method_agent_main`，作为脚本和测试使用的稳定入口；
4. 旧 `code2paper-run` 和 `code2paper-agentic-run` 保留原指向，明确表示旧版和 R8 路线；
5. 第一阶段不把 `code2paper run` 静默改成新主线，避免破坏旧用户；新主线先用明确的
   `code2paper method-agent run`；通过产品验收后再单独决定默认切换。

### 6.3 P2：命令返回码不能表达产品失败

`cli/agentic_run.py` 的 `method_agent_main` 在没有抛异常时总是返回 0，即使 Writer blocked、最终验证
failed 或产品 incomplete。

修复：定义清楚三类退出码：

- 0：Master Agent 到达 `trusted`，要求的交付物存在且最终完整性门通过；
- 1：运行正常完成但产品是 `incomplete` 或 `blocked`；
- 2：输入、合同、文件、依赖或运行故障。

如果需要让 review-only 结果不使自动化失败，可加显式参数，而不能默认把失败当成功。

### 6.4 P3：外层产品流程不是顶层 LangGraph

`autonomous_method_agent.py` 同时负责状态、顺序、路由、文件写入和摘要。这导致：

- 只能在少数人工阶段点恢复；
- Writer 回调是图外第二循环；
- 子模块失败后只能靠 if/try 组合；
- “阶段完成”和“交付可信”容易混在一个 summary 中；
- 无法让 LangGraph 检查点记录真实产品路由。

修复：新增 Master Agent 状态、节点、路由和图构建器。旧函数暂时变成兼容 facade：准备初始状态、
调用 Master Graph、读取最终结果。不能保留原顺序流程作为主执行，再让顶层图只做记录。

### 6.5 P4：研究子图虽有检查点，产品调用没有接入

`run_product_research_phase` 构建研究子图时没有 checkpointer，调用时 config 为 `None`，并从
`last_result` 内存持有者取结果。

修复：

- Master 的研究节点为子图创建稳定子线程，例如 `<master-thread>/research/main`；
- 传入和 Master 相同的 SQLite saver，但使用不同 thread ID；
- 子图终止后把研究结果写成不可变 `research_result` 文件；
- Master 状态只接收文件引用、摘要、终态和计数；
- 恢复时先验证仓库快照、研究子线程和 result 文件摘要；
- `last_result` 仅保留为同进程兼容接口，Master 不以它作为唯一事实来源。

### 6.6 P5：当前研究阶段 JSON 检查点不是顶层真实恢复

`persist_research_stage_checkpoint` 会把完整研究结果另写一个 JSON。它适合“研究完成后跳过研究”，
但不能恢复研究中间节点，也不能说明 Concept、Writer 或回调执行到哪里。

修复：保留它作为导出或兼容 checkpoint，但 Master 以 LangGraph checkpoint 为运行恢复权威。阶段导出
文件必须记录 master thread、child thread、状态合同版本、图合同版本和所有输入摘要，不能只比较
run ID、snapshot ID 和 tree hash。

### 6.7 P6：Concept Card 仍会静默退回 proposition

`build_product_planning` 只有在显式要求、存在 live LLM 且有 claims 时才编译 Concept Card；否则只要
没有外部卡片，就继续编译 proposition。

修复：新 Method Agent 主线的模式固定为 Concept Card。缺少模型、卡片生成失败、逐字段判断失败时：

- 产生明确 gap；
- 产品进入 `incomplete` 或 review 状态；
- 不调用 proposition 编译器；
- 不把 proposition 作为隐藏 fallback。

旧 R8 和历史 replay 仍可显式使用 proposition，但它们不能由新主线自动选择。

### 6.8 P7：Concept Card 输入没有保存足够精确的来源关系

当前候选 cluster 的 `source_fragments` 是 claim 规范句子，`source_span_ids` 是另一组平行数组。两者并非
强制一对一，后续有 `zip(..., strict=False)`，长度不一致时会静默丢项。fact ID、claim ID、relation ID、
条件和义务也没有按 fragment 放在同一条记录中。

修复：新增一个“Concept 来源片段”合同。推荐文件仍放在
`method_concept_card_models.py`。每条片段至少包含：

```text
fragment_key              模型可选择的短标识
exact_text                模型可见的精确片段文字
claim_ids                 后台精确原子陈述归属
fact_ids                  后台精确代码事实归属
span_ids                  后台精确代码位置
relation_ids              后台精确调用/数据流/控制流关系
obligation_ids            来源研究问题
required_qualifiers       该片段必须保留的条件
source_authority          仓库、作者、外部或形式化
content_digest            本条记录摘要
```

模型只看 `fragment_key + exact_text`，其他 ID 留在后台。卡片字段只能选 fragment key；harness 再从同一
记录取得精确 ID。禁止继续依赖平行数组。

### 6.9 P8：Concept 字段绑定和目的判断仍依赖英文词语表

`method_concept_card_compiler.py` 中的字段绑定使用词语交集和一组手写同义词；目的判断使用 “for
pruning”“predictor”等硬编码英文标记。这些规则可做诊断，不能拥有证据授权。

修复：

- Concept Architect 选择每个字段的 fragment key；
- Evidence Judge 对每个字段返回 fragment key 和判断；
- harness 只检查 key 是否属于当前封闭集合、逐字段判断是否完整、来源是否允许；
- 调用或数据流目的必须绑定 `relation_ids`，不能靠句子里出现 “caller/predictor” 判定；
- 词语重合只可用来生成告警或排序候选，不可用来授权、扩充或替换绑定；
- 删除面向某个示例项目的词语别名，通用代码只识别结构化关系。

### 6.10 P9：Concept Card 的章节放置可能静默遗漏或按遍历顺序选择

`method_architect.py` 当前用义务集合相交放置卡片，并用 `placed_keys` 保证只放一次。多个候选时先到
先得，零候选时没有完整关闭报告。

修复：新增 Concept 放置报告，规则如下：

- 恰好一个候选论证单元：确定性放置；
- 多个候选：只把封闭候选集交给 Architect 选择一次，选择结果必须在候选集内；
- 零候选：记录 `unplaced_concept`，进入 review/incomplete，不能丢弃；
- 每张卡最终只能处于 placed、candidate-only queue 或 explicit gap 三种状态之一；
- 计划合同验证全部卡片 key 均被覆盖一次；
- 计划摘要绑定 Concept Card 集摘要和放置报告摘要。

### 6.11 P10：Concept 到最终句子的映射过宽

当前 `_align_final_claims_to_concept_cards` 按词语重合在本节选一个概念；`_concept_claim_ids` 再把该概念
扩大到同一义务下全部 claims。Concept key 还借用了
`candidate_method_proposition_ids` 这个旧字段。

修复分三步：

1. 在最终句子合同中新增真正的 `candidate_method_concept_keys`，含义是“本句可能对应的 Concept”；
2. 新增 Concept 语义对齐器，只能从本节封闭概念集合选择，保存每句候选、判断、歧义和调用追踪；
   零匹配或多义时不授权；
3. Concept 到 claim 的后台映射只使用上一节新增来源片段里的精确 `claim_ids`，禁止按 obligation 扩大。

旧 proposition 字段仅供旧路线读取；新 Concept 验证分支不再把 Concept 假装成 proposition。

### 6.12 P11：Concept 路线的 Writer 分节检查点没有绑定 Concept 摘要

`publication_method_writer.py` 的分节检查点只保存 `proposition_set_digest`。Concept 路线传空字符串，
因此改变 Concept Card 后仍可能复用旧章节输出。

修复：把该字段升级为通用的 `writer_input_digest`，它至少覆盖：

- 章节计划摘要；
- 原子陈述摘要；
- Concept Card 集摘要；
- Concept 放置报告摘要；
- 章节条件授权摘要；
- 公式、配置和形式化摘要；
- WriterView 摘要；
- 已接受回调 bundle 摘要。

恢复任何章节时必须全部相同。保留旧 `proposition_set_digest` 只用于读取历史 checkpoint，不能写入新
Concept checkpoint。

### 6.13 P12：Writer 后台仍依赖旧格式

`autonomous_method_agent.py` 的 `_method_evidence_template` 会创建最小旧 MethodEvidence；随后
`build_authoring_projection` 和 `projected_writer_inputs` 又生成旧 `method_evidence` 与
`claim_evidence_map`。`_maybe_validate_final_text` 没有旧 MethodEvidence 时只返回 pending。

这些不是旧流程入口，却是新流程为了调用现有最终校验而保留的兼容适配。不能马上删，否则反向校验
直接停止。

修复采用双轨迁移：

1. 新增“发布校验输入”合同，直接携带项目身份、仓库快照、精确 claims、evidence packets、Concept
   绑定、作者来源片段和条件授权；
2. 最终句子提取与证据校验先支持新合同；
3. 同一冻结输入同时用新合同和旧适配合同运行确定性校验，结果必须相同；
4. Writer 主线切到新合同；
5. 只有在静态测试、三个真实项目和旧 replay 都证明一致后，才停止写三个兼容产物。

### 6.14 P13：Writer 文件职责过多

8,600 行中心文件使 Master 接入、局部修复和最终发布互相影响。下一阶段不做一次性重写，而是逐步拆出：

- Writer 输入加载与合同检查；
- 分节生成与分节 checkpoint；
- Writer/Editor/Rewrite 修改事务；
- 最终反向校验；
- 三份交付物发布。

每次抽取保持原函数为薄转发，并先做等价测试。禁止边抽取边改变所有行为。

### 6.15 P14：仓库回调没有回到同一个 Research Manager

`_BudgetedRepositoryCallbackProvider` 是简化搜索器，只能匹配已有 facts。它无法证明新发现，也不继承原
研究清单、行为关系、信息增益、工具调用去重和决策历史。

修复：仓库类 Writer 请求转成同一个研究状态中的新增义务，带上：

- 原请求 ID、请求摘要；
- 原 section 和 argument unit；
- Concept key 和已使用 fragment；
- 缺失字段；
- 允许搜索的符号或路径；
- 原研究子线程和 checkpoint；
- 本次附加预算。

然后恢复原研究子图。研究子图可以产生新 evidence/fact/claim 或明确 gap。回调完成后只重编受影响的
Concept、放置、WriterView 和章节，不能全局重跑所有章节。

### 6.16 P15：配置和形式化回调授权过宽

配置回调目前按候选词精确匹配已有配置项，方向基本正确，但回调 artifact 仍应绑定请求摘要和配置来源
摘要。

形式化回调目前只要存在一份有摘要的 formalization result，就能返回 fulfilled，没有证明它回答了当前
问题。必须改为：

- 由请求生成精确 proof obligation；
- 形式化模块返回该 obligation 的 ID、结论、假设、推导、状态和来源摘要；
- 只有 status 是 supported/approved 且 request digest、obligation ID、公式/事实引用闭合时才 fulfilled；
- 整份形式化文件的摘要本身不能满足任意请求。

### 6.17 P16：回调 artifact 的“validated”布尔值不是充分证明

当前 callback artifact 主要检查 ID、lane、摘要格式和 `validated=True`。虽然发布时还会验证文件引用，
但状态仍不足以证明“这个结果确实解决这个请求”。

新回调结果至少增加：request digest、parent checkpoint、repo snapshot、输入 Concept digest、输出
evidence/fact/claim/concept digest、remaining gaps 和 owning validator report digest。`validated` 必须是
校验器计算结果，不允许 provider 自行写 True 后直接获得授权。

### 6.18 P17：顶层成功状态不够严格

当前 Method Agent summary 分别记录研究、Writer 和验证，但没有一个严格计算的最终 product status；
CLI 也不依据这些字段返回失败。

Master 最终状态必须由确定性终态节点计算，至少要求：

- 仓库快照和全部输入摘要一致；
- 研究有可信终态或明确 gap；
- Concept Card 和放置闭合；
- 必需章节均有可编辑正文；
- 回调无未处理的本地硬请求；
- 候选稿最终反向校验通过；
- 已验证稿无未支持正向事实；
- 章节覆盖、来源记录、结构和最终完整性门通过；
- 所有发布文件存在且摘要有效。

任何一项不满足都不能输出 `trusted`。

## 7. 目标 Master Agent 架构

### 7.1 总体图

```text
START
  -> 输入解析与仓库冻结
  -> 作者意图与研究义务
  -> 现有 Research LangGraph 子图
  -> 研究结果冻结与汇总
  -> Concept 来源片段
  -> Concept Architect
  -> 逐字段 Evidence Judge
  -> Concept 放置与文章计划
  -> Writer 输入冻结
  -> 分节 Writer
  -> Writer 结果路由
       |-- 内容完整 -----------------------> Editor / Rewrite
       |-- 缺仓库证据 -> 恢复同一研究子图 --|
       |-- 缺配置事实 -> 配置模块 ----------|
       |-- 缺形式化证明 -> 形式化模块 -------|
       `-- 缺作者/文献/实验 -> 外部队列
  -> 只恢复受影响章节
  -> 最终句子拆分与证据反查
  -> 候选稿 / 已验证稿 / 作者确认清单
  -> 最终完整性门
  -> trusted | incomplete | blocked | interrupted
```

### 7.2 LangGraph 和 LangChain 的分工

LangGraph 负责：

- 顶层阶段和条件路由；
- 研究循环；
- Writer 回调循环；
- 检查点和恢复；
- 局部重试次数；
- 终态。

LangChain 继续负责把代码搜索、精确读取、调用追踪、数据流、控制流、配置检查等细粒度能力包装成研究
管理器可以调用的工具。

确定性函数继续负责摘要、文件校验、闭合 ID 校验、句子拆分、证据反查、质量计算和发布。没有必要把
每个普通函数变成 Agent。

### 7.3 Master 节点必须拥有的真实路由

| 节点职责 | 最小输入 | 持久输出 | 可走的下一步 |
|---|---|---|---|
| 输入与冻结 | repo、作者输入、用户声明 | 输入清单、repo snapshot、tree hash | 研究；输入阻止 |
| 研究 | 研究义务、子线程、预算 | research result、evidence/fact/claim/gap refs | Concept；研究不完整；阻止 |
| Concept | 精确来源片段、Architect/Judge 配置 | cards、field verdicts、bindings、gaps | 规划；review；阻止 |
| 规划 | 作者组织、Concept、完整性 | section plan、placement report、readiness | Writer；review；阻止 |
| Writer | 冻结 Writer input | 分节输出、请求、来源记录 | Editor；回调；局部 Writer 修复 |
| 回调路由 | 精确请求和 lane | route decision | 研究；配置；形式化；外部队列 |
| 回调合并 | owner 结果 | 更新后的研究/Concept/plan/Writer input | 恢复指定章节；不完整 |
| Editor/Rewrite | 指定章节、问题集合、授权边界 | 事务记录、更新章节 | 再验证；再次局部修复；阻止 |
| 最终校验 | 完整候选稿和全部冻结合同 | final claims、verdict、quality、ledger | 发布；局部修复；不完整；阻止 |
| 发布与终态 | 已通过的全部报告 | 三份交付物、manifest、final status | END |

每个节点必须是幂等的：相同输入摘要重复执行时得到相同 artifact identity，或读取已经存在且摘要正确
的输出；不能向同一个可变文件追加不确定内容。

## 8. Master 状态和文件合同

### 8.1 顶层状态只保存引用

建议新增 `src/code2paper/agentic/method_master_state.py`。文件含义是“顶层 Method Agent 的版本化状态
合同”。推荐状态字段如下：

```text
身份：state_version、graph_version、run_id、master_thread_id
仓库：repo_snapshot_ref、repo_snapshot_id、project_tree_hash
输入：author_intent_ref/digest、claims_ref/digest、run_config_ref/digest
研究：research_thread_id、research_state_ref、research_result_ref、evidence/fact/claim/gap refs
概念：concept_fragment_ref、concept_card_ref、concept_binding_ref、concept_placement_ref
规划：completeness_ref、section_plan_ref、plan_readiness_ref、qualifier_authority_ref
写作：writer_input_ref、section_checkpoint_ref、callback_bundle_ref、editor/rewrite refs
交付：candidate_ref、verified_ref、review_ref、final_validation_ref、quality_ref、ledger_ref
路由：active_phase、active_section_ids、active_callback_ids、remaining_budgets
终态：status、reason、blocking_artifact_refs
```

状态中不放完整源码、行为图、证据包、完整 prompt 或正文。它们写入不可变文件，状态只保存路径和
SHA-256 摘要。

### 8.2 统一 artifact 引用

建议新增一个通用小合同，表示“某个节点输出文件”：

```text
artifact_type
schema_version
path
sha256
run_id
repo_snapshot_id
project_tree_hash
producer_node
producer_code_digest 或执行记录摘要
input_digests
```

所有父子图、回调和 Writer resume 都使用它。相对路径必须从所属 bundle 目录解析；禁止路径穿越、
符号链接逃逸、文件缺失和摘要不一致。

### 8.3 终态定义

- `trusted`：所需交付物和所有硬门通过；
- `incomplete`：运行正常，存在明确缺口、外部待办或预算结束，且没有伪装完成；
- `blocked`：继续运行会违反证据、来源、合同或安全边界；
- `interrupted`：进程或人工中断，存在可验证的恢复点；
- `failed`：工具、模型、文件或代码异常导致节点无法形成可信结果。

研究子图的 `trusted` 只表示研究循环的终止判断，不能直接等于产品 `trusted`。

## 9. 父图如何复用现有研究 LangGraph

### 9.1 不再包一套重复研究图

保留 `build_research_subgraph` 的节点和路由。Master 只增加一个父级“运行/恢复研究子图”的节点。

### 9.2 必须新增的父子图适配

建议新增 `src/code2paper/agentic/method_master_nodes.py`，其中研究节点按以下逻辑工作：

```python
def run_research_child(master_state):
    # master_state 是顶层小状态；先校验仓库和输入摘要。
    child_state = build_child_state_from_master(master_state)
    # child_thread_id 是该 Master 运行下研究子图的稳定线程。
    child_graph = build_research_subgraph(runtime, checkpointer=shared_saver)
    child_graph.invoke(child_state, config={"configurable": {"thread_id": child_thread_id}})
    # 不直接依赖内存 last_result；把终态和编译证据写成不可变 result 文件。
    result_ref = persist_authenticated_research_result(...)
    return project_research_result_to_master(result_ref)
```

以上函数名是建议代码锚点，分别表示“父状态转子状态”“保存带摘要的研究结果”“把结果引用投影回父
状态”。实现时可调整名称，但职责不能混回一个大函数。

### 9.3 研究终止文件

研究子图的 terminator 应额外产生一个可序列化 result manifest，至少包含：

- 最终研究状态和原因；
- turns、预算、无进展计数；
- decision trace 和 node trace 摘要；
- immutable loop payload 引用和摘要；
- evidence packet、fact、claim、gap 的引用和摘要；
- active/terminal obligation 状态；
- repo snapshot 和 graph contract。

Master 只接受这个文件，不能只接受 `last_result` Python 对象。

### 9.4 检查点命名

建议线程层级：

```text
<run-id>:<snapshot-id>:method-master-v1
<run-id>:<snapshot-id>:method-master-v1/research/main
<run-id>:<snapshot-id>:method-master-v1/research/callback/<request-id>
```

研究回调应优先恢复 `/research/main` 并追加义务；如果 LangGraph saver 不允许在已终止线程上安全追加，
才创建 callback 子线程，但必须载入并验证 main 的 immutable loop payload，且 parent checkpoint 明确
记录继承关系。不能新建一个无历史的简化研究器。

## 10. Concept Card 的目标数据流

### 10.1 生成前

```text
原子陈述 + 精确代码 span + 调用/数据流关系 + 条件
  -> Concept 来源片段文件
  -> 按研究问题和真实关系分组
  -> 模型只看 fragment key 和 exact text
```

分组不能只靠函数名或单词。优先使用同一研究义务、共享 fact、共享 span、相连 relation；没有关系的
内容不放入同一 cluster。

### 10.2 Concept Architect

Architect 只产生方法主体、操作、输入、输出、条件、数字、公式、已知部分、缺失部分和候选说明，并为
每个字段选择 fragment key。它不产生内部 ID，不决定 verified 权限。

### 10.3 Evidence Judge

Judge 对每个非空字段逐一返回 entailed、partial、contradicted 或 not_found，并选精确 fragment key。
Harness 必须检查：

- 字段全集没有缺失或重复；
- key 全部来自本 cluster；
- repository card 没有作者目的扩张；
- 数字和公式来自明确来源；
- purpose 字段有调用或数据流 relation；
- 只有全部正向字段 entailed 的 repository card 才能进入 verified。

### 10.4 放置和写作

Concept placement report 把每张卡绑定到一个论证单元和章节。WriterView 只从这个报告读取，不再自己
根据 obligation 推断。

### 10.5 最终验证

最终句子先限定在实际章节，再由 Concept semantic aligner 从该节 closed set 中判断；Concept key 再
通过精确 fragment binding 取得 claim IDs。任何歧义都不授权。最后仍由原子陈述、证据包、条件、数字
和公式检查决定 supported，不因 Concept 相似就通过。

## 11. Writer 迁移方案

### 11.1 不推翻已工作的模型可见接口

保留 WriterView 和 `section_writer.py` 的可见字段过滤。下一阶段重点是把后台合同从旧适配迁到新发布
校验合同。

### 11.2 新发布校验输入

建议新增 `src/code2paper/agentic/publication_writer_inputs.py`，含义是“Writer 和最终校验共享的冻结输入
清单”。它不包含论文 prose，至少引用：

- repo snapshot；
- evidence packets、facts、atomic claims；
- Concept Cards、精确 bindings、placement；
- completeness 和 section plan；
- qualifier authority；
- equations、configurations、formalization；
- author-attested artifacts；
- callback bundle；
- WriterView per section；
- 所有摘要。

### 11.3 迁移顺序

1. 先让旧 Writer 同时接收新 input manifest，但仍使用旧适配做最终校验；
2. 新增从 manifest 直接构建 authoring authorization 的代码；
3. 新旧两条确定性校验对同一正文产生相同 verdict；
4. 主线改用新校验；
5. 历史 replay 仍可通过兼容 loader 生成新 manifest；
6. 删除新主线对 `MethodEvidence`、`ClaimEvidenceMap` 和旧 projection 的写依赖；
7. 最后再决定是否保留只读兼容 loader。

### 11.4 分节 checkpoint 升级

checkpoint 版本升级，写入 `writer_input_digest`。读取旧版时：

- proposition replay 可按旧 digest 恢复；
- Concept 主线不得把缺少 Concept digest 的旧 checkpoint 当有效；
- 任何 plan、Concept、条件、回调或 WriterView 摘要变化，只使受影响章节失效；
- 未受影响章节只有在其 section-specific digest 不变时才复用。

### 11.5 条件授权文件

把当前函数内的条件映射持久化为独立 `section_qualifier_authority_v1.json`。每条记录包含 section、claim、
final claim（如已有）、精确条件、来源 artifact、授权形式和摘要。Writer、Rewrite 事务、风格检查和最终
质量都读取同一文件。

## 12. 写作回调的目标流程

### 12.1 请求

Writer 仍可生成结构化请求，但请求必须绑定当前 Writer input digest 和 Concept binding。请求本身不能
扩大搜索范围。

### 12.2 路由

- repository：回到研究子图；
- configuration：只查询精确配置链；
- formalization：创建精确 proof obligation；
- author、literature、empirical：进入外部队列；
- expository bridge：如果无事实内容，返回 Writer；如果需要新事实，按来源重新路由。

### 12.3 合并

仓库回调的新证据不能直接塞进 Writer preview。它必须依次通过：

```text
新观察
  -> behavior graph
  -> evidence packet
  -> code fact
  -> atomic claim / explicit gap
  -> affected Concept field judgment
  -> affected placement / WriterView
  -> resume affected section
```

### 12.4 增量范围

每个回调保存受影响集合：obligation、claim、concept、argument unit、section。只有这些集合重编。若无法
证明影响范围，宁可将产品标记 incomplete，也不能全局合并后假装只影响一节。

### 12.5 停止条件

- 请求已由 owning validator 精确满足；
- 得到明确 gap；
- 无进展；
- 请求预算耗尽；
- 全局安全预算耗尽；
- 外部来源待办。

“重新读到已有事实”不算进展，也不能把请求标为 fulfilled。

## 13. 另外两条旧路径如何处理

### 13.1 处置原则

旧代码分四类处理，不按整个 `agentic/` 目录一刀切。

| 类别 | 含义 | 操作 |
|---|---|---|
| 冻结旧编排 | 只为历史、回滚或评测存在的整条流程 | 保留独立入口，不再新增新主线能力 |
| 复用通用服务 | 不拥有产品路线，只提供快照、工具、校验等能力 | 新 Master 可直接调用 |
| 临时兼容适配 | 新主线暂时为旧 Writer/validator 生成旧格式 | 双写验证后逐步移除 |
| 新主线专属 | Master、Concept 精确绑定、新回调和新发布合同 | 只服务新 Method Agent |

### 13.2 最早故事驱动路线：冻结

冻结范围：

- `src/code2paper/main_cli.py`；
- `src/code2paper/run_cli.py` 中的 legacy 主流程；
- `src/code2paper/pipeline/` 的旧阶段编排；
- 旧 Phase 1–5 的输出目录语义。

允许修改的情况只有：严重安全问题、安装兼容、明确 legacy 标签、确保它不被新入口误调用。禁止把
Master Agent 节点接到这些 stage 函数来“快速复用”。

### 13.3 旧 R8 路线：保留为评测和回归

冻结编排范围：

- `agentic/runner.py`；
- `agentic/graph.py`；
- `agentic/graph_topology.py`；
- `agentic/v3_runtime.py` 的“研究后接回旧图”包装；
- R8 benchmark、cutover、rollout 和 legacy audit 入口。

它们继续用于历史 replay、R8 证据和旧图回归，但不能成为 Master 的父图，也不能决定新 Method Agent
的最终状态。

### 13.4 可跨路线复用的通用服务

以下能力不属于某条旧编排，可继续复用：

- 仓库快照和 tree hash；
- source authority policy；
- Python/JavaScript 行为适配器；
- 研究工具和工具策略；
- evidence/fact/claim 编译；
- 公式和配置解析；
- LangGraph SQLite saver 和稳定线程 ID 思路；
- 最终句子拆分、证据校验和作者来源 ledger；
- Writer、Editor、Rewrite、Formalizer 的角色配置；
- 不可变文件、摘要、相对路径和原子写入；
- 通用运行 manifest 和执行记录。

复用服务时直接调用服务模块，不通过旧 runner 或旧 graph 进入。

### 13.5 临时保留的兼容适配

暂时保留：

- V3 claims -> 旧 MethodEvidence；
- V3 claims -> 旧 ClaimEvidenceMap；
- V3 evidence -> 旧 AuthoringInputProjection；
- 历史 proposition replay loader；
- 旧分节 checkpoint reader。

这些适配不能拥有新事实，只能做等价格式转换。每个适配产物必须标记 `compatibility_only`，记录来源新
合同摘要。

### 13.6 兼容适配的删除条件

只有同时满足以下条件才删除：

1. 新发布输入能直接驱动最终句子提取和反向校验；
2. 新旧确定性 verdict 在固定 fixture 上完全一致；
3. Concept 主线的三个真实项目通过；
4. 历史 proposition replay 仍能通过只读兼容 loader；
5. 没有生产入口读取旧产物；
6. 文档、脚本和测试均已转向新 key；
7. Codex 单独只读验收通过。

### 13.7 入口隔离的最终形态

```text
code2paper method-agent run    新产品主线，最终由 Master Agent 执行
code2paper-run                 最早故事驱动 legacy
code2paper-agentic-run         旧 R8 Agentic 评测/回归
code2paper-method-agent        可选的新主线直接入口
```

在新主线通过验收前，不删除旧命令，不把旧命令静默重定向到新实现。

## 14. 逐文件实施指导

### 14.1 新增文件

| 建议文件 | 职责 | 不得包含 |
|---|---|---|
| `agentic/method_master_state.py` | 顶层小状态、版本、终态和 artifact 引用 | 完整源码、全文、模型 client |
| `agentic/method_master_graph.py` | Master LangGraph 节点注册、边和条件路由 | 具体证据编译、prose 生成 |
| `agentic/method_master_nodes.py` | 节点薄适配：校验输入、调用现有服务、返回小更新 | 另一套研究算法 |
| `agentic/method_master_routes.py` | 纯确定性的下一步选择 | 文件写入、模型调用 |
| `agentic/publication_writer_inputs.py` | 新 Writer/最终校验冻结输入合同 | 旧流程编排 |
| `agentic/method_concept_alignment.py` | 最终句子到本节 Concept 的封闭对齐和追踪 | 证据授权规则替代品 |
| `agentic/section_qualifier_authority.py` | 唯一章节条件授权构建、加载和校验 | Writer payload 子集推断 |

文件名可以在实施时按现有风格调整，但职责必须保持分离。

### 14.2 现有入口文件

`pyproject.toml`

- 把 `code2paper` 指向完整统一 CLI；
- 可增加 `code2paper-method-agent`；
- 保留旧两个命令；
- 不改 benchmark 命令语义。

`src/code2paper/cli/main.py`

- 补齐 Concept、Master checkpoint/resume、callback budget、fail-on-incomplete 参数；
- 明确转发所有参数；
- 加旧命令说明；
- 为新主线调用 `method_agent_main`，不能导入旧 runner。

`src/code2paper/cli/agentic_run.py`

- 暂时保留旧 R8 `main`；
- 把 `method_agent_main` 改成调用 Master facade；
- 根据最终 product status 返回 0/1/2；
- 结果文件原子写入，不再直接 `Path.write_text`；
- 不在 CLI 中计算事实或质量。

### 14.3 当前外层 Method Agent

`src/code2paper/agentic/autonomous_method_agent.py`

- 保留输入模型、运行环境构建、证据合并和 artifact 写入等可复用函数；
- 将 `run_autonomous_method_agent` 缩成 Master facade；
- 删除新主线的 proposition 自动 fallback；
- `persist_product_artifacts` 改为按节点/合同写入，不再一次写所有阶段；
- `_writer_artifact_paths` 由新 writer input manifest 取代；
- `_method_evidence_template` 移入明确 compatibility 模块；
- `_run_writer_surface` 返回结构化状态，不吞掉所有异常后只给字符串。

### 14.4 研究子图和检查点

`src/code2paper/agentic/research_graph.py`

- 保留现有拓扑；
- terminator 写 authenticated result manifest；
- 将 result manifest ref 放入可序列化 state；
- 保留 `last_result` 供旧测试，但新 Master 不依赖；
- 新义务追加时验证 parent checkpoint 和已消耗预算；
- 回调新增义务不得清空原 behavior graph、gain tracker 和 tool-call 去重集合。

`src/code2paper/agentic/state_v3.py`

- 增加 research result ref/digest 和 parent continuation identity；
- 更新 schema/graph contract 版本；
- 为旧 checkpoint 提供显式 migration 或直接拒绝，不能静默按新状态解释。

`src/code2paper/agentic/checkpointing.py`

- 增加 Master thread helper；
- 验证父子线程绑定；
- resume 同时检查 repo snapshot、tree hash、graph version、state version 和 result artifacts；
- 不复用旧 V2/V3 dispatch 来猜 Master 状态。

### 14.5 Concept Card

`method_concept_card_models.py`

- 新增单条来源片段合同；
- binding 增加精确 claim/fact/span/relation/qualifier 引用；
- card set 记录 source fragment set digest；
- 禁止 verified card 缺 field verdict 或精确 binding。

`method_concept_card_compiler.py`

- 从精确来源片段分组；
- 移除平行数组 zip；
- 词语重合不再授权字段；
- relation 决定 purpose/data-flow；
- 缺 Architect/Judge 时明确 incomplete，不 fallback；
- 每个未使用 fragment 留在 evidence ledger，不强制每条低层 fact 变成 card。

`method_concept_card_provider.py`

- 模型只看 fragment key 和 exact text；
- 去掉示例项目词语；
- 维修轮只返回失败字段和封闭 fragment 集；
- 调用 trace 绑定输入和输出摘要。

`method_concept_card_evidence_provider.py`

- 强制返回全部非空字段；
- 每个 entailed/partial 字段有 fragment key；
- purpose 判断要求 relation witness 的后台校验；
- judge 失败时 fail closed。

### 14.6 文章规划

`method_architect.py`

- 使用 Concept placement report，不用 first-match 静默放置；
- 多候选只允许从 closed candidate units 选择；
- 零候选形成 unplaced；
- plan identity 和 trace 绑定 Concept digest；
- 受回调影响时只重建关联 unit/section。

`method_argument_models.py`

- 增加 Concept placement 记录和闭合校验；
- 计划验证全部 card 恰好有一种终态；
- callback request 增加 request/input/parent checkpoint digest；
- callback artifact 增加 owner validation report 和更新后的 artifact refs；
- 保留旧字段默认值供历史读取，但新主线必须填新字段。

### 14.7 Writer 和最终校验

`writer_view_projection.py`

- Concept constraints 补入精确 required qualifiers；
- constraints 从 Concept binding/qualifier authority 读取，不从模型文本猜；
- WriterView digest 纳入回调机会和条件授权；
- proposition builder 只供旧路线。

`publication_method_writer.py`

- 先完成 P0 条件修复验收；
- 加载新 writer input manifest；
- 分节 checkpoint 使用通用 writer input digest；
- Concept 最终对齐调用专用模块；
- 最终校验不再按 obligation 扩大 claim；
- 新主线不再把 Concept key 写入 proposition 字段；
- 将输入、事务、最终校验和发布逐步抽出；
- 保留已接受的 section-scoped coverage、callback rebasing 和结构检查。

`trust_contracts.py` 和 `final_text_claims.py`

- 新增 Concept key 字段；
- 分开 proposition 和 Concept，禁止同时出现；
- 最终 claim 保存 section identity 和对齐 artifact ref；
- 重新计算摘要。

`text_evidence_validator.py`

- 增加 Concept 专用输入；
- 只从 exact concept binding 取得 claims；
- 旧 proposition 参数留在兼容分支；
- 缺或歧义 Concept 不授权；
- qualifier authority 使用独立文件。

`publication_quality.py`

- 指标改为同时支持 concept mode 和 legacy proposition mode；
- 新主线报告使用 concept 名称，不再把 concept 统计写成 proposition；
- 条件豁免只接受精确授权形式；
- 保留句子到章节的真实覆盖关系。

### 14.8 回调

`writer_research_router.py`

- 路由结果绑定 request digest；
- repository route 输出“恢复研究子图”指令，不直接调用简化 provider；
- formalization route 输出 proof obligation；
- 外部队列保持显式。

`writing_callback_fulfillment.py`

- 删除新主线对 `_BudgetedRepositoryCallbackProvider` 的依赖；
- 旧 provider 可移到 legacy compatibility 文件供旧测试；
- 新实现调用 Master 的 owner 节点；
- 合并 owner result 后重编 affected set；
- fulfillment 必须由校验报告决定；
- resume 只使用新的 section-specific writer input digest。

### 14.9 输出名称和脚本

`src/code2paper/core/output_names.py`

- 增加 Master state、research result、Concept fragments/placement、writer input、qualifier authority、
  callback validation 和 final manifest 的稳定名称。

`scripts/run_publication_writer_from_artifacts.py`

- 增加新 writer input manifest；
- 历史 replay 走显式 compatibility loader；
- 运行记录区分 concept 与 proposition。

其他 D5/R8 脚本只在需要消费新 artifact 时修改，不能让架构重构顺便改变历史评测口径。

## 15. 实施顺序和每一阶段的停止门

### 15.1 批次 A：关闭当前发布 `REPAIR`

只修条件授权和局部修改事务，不做 Master 大重构。

停止门：聚焦测试、全静态里程碑、同一代码摘要三项目冻结写作、Codex 只读验收全部通过。

### 15.2 批次 B：先加新合同，不改产品路由

新增 Master state、artifact ref、Concept source fragment、placement、writer input 和 qualifier authority
合同及序列化测试。旧流程继续运行，进行双写。

停止门：新合同能从当前产物无损构建；摘要篡改、缺文件、跨快照、重复/未知 ID 全部失败关闭。

### 15.3 批次 C：收紧 Concept 链

改精确 fragment、field binding、relation purpose、placement 和 final concept alignment。新旧最终验证做
差异比较。

停止门：无词语重合授权、无 obligation 扩大、无未放置静默丢失、Concept checkpoint 绑定正确。

### 15.4 批次 D：迁移 Writer 后台合同

Writer 模型可见接口保持不变；后台切到新 writer input 和 qualifier authority。旧三个适配产物继续双写
但不再作为新主线权威。

停止门：同一正文新旧 verdict 一致；分节恢复在 Concept 变化时失效、在无关章节不变时复用。

### 15.5 批次 E：建立 Master Agent 顶层图

把输入、研究、Concept、规划、Writer、验证和发布接入图。原
`run_autonomous_method_agent` 变薄 facade。

停止门：节点 trace 证明真实路由由图决定；中断后不重复已完成模型调用；任何硬门失败不会发布 trusted。

### 15.6 批次 F：写作回调回到原研究管理器

先实现 repository 回调 continuation，再实现配置和形式化精确结果；外部队列保持不自动执行。

停止门：回调能新增真实 evidence/fact/claim/concept；重复已有事实不算 fulfilled；只恢复受影响章节；
篡改 parent checkpoint 或 request digest 失败关闭。

### 15.7 批次 G：正式入口和旧路线隔离

切统一 CLI，补完整参数和返回码，增加 import boundary 测试。保留旧命令。

停止门：安装后的命令能直接运行新 Master；新主线运行期间没有导入或调用旧 runner/graph/pipeline
编排器；旧两个命令的聚焦回归仍通过。

### 15.8 批次 H：真实纵向验收

先做一个小仓库全链，再做 DyG、LinearRAG、EBCAR 同摘要批次，最后再讨论更多项目和默认切换。

没有任何单次成功可以提前跳过前面停止门。

## 16. 测试与故障注入矩阵

### 16.1 现有测试文件应扩展

| 测试文件 | 增加的重点 |
|---|---|
| `tests/test_agentic_autonomous_method_agent.py` | 新主线无 proposition fallback；Master facade；真实终态 |
| `tests/test_agentic_autonomous_method_agent_cli.py` | 完整参数转发；0/1/2 返回码；安装入口 |
| `tests/test_main_cli.py` | method-agent Concept/checkpoint/callback 参数全部转发；旧命令隔离 |
| `tests/test_agentic_research_checkpoint_resume.py` | 父子线程、跨进程恢复、result manifest、回调 continuation |
| `tests/test_agentic_method_concept_cards.py` | 精确 fragment、relation purpose、placement、无词语授权 |
| `tests/test_agentic_publication_method_writer.py` | qualifier、Concept checkpoint digest、final exact mapping、局部恢复 |
| `tests/test_agentic_final_text_trust.py` | Concept 字段与 proposition 字段分离；歧义不授权 |
| `tests/test_agentic_autonomous_callback_fulfillment.py` | 同 Research Manager、真正新证据、形式化精确匹配 |
| `tests/test_run_cli.py` | 旧 story-first 命令保持原语义 |
| `tests/test_agentic_runner.py` | 旧 R8 路线保持独立，不成为 Master 依赖 |

### 16.2 建议新增测试文件

- `tests/test_agentic_method_master_graph.py`：顶层节点和条件路由；
- `tests/test_agentic_method_master_resume.py`：中断、恢复、幂等和不重复调用；
- `tests/test_agentic_method_master_legacy_isolation.py`：新主线不得导入旧编排器；
- `tests/test_agentic_publication_writer_input_contract.py`：新 manifest 和旧适配等价；
- `tests/test_agentic_method_concept_alignment.py`：句子只在本节封闭集合中精确对齐；
- `tests/test_agentic_section_qualifier_authority.py`：唯一条件授权和复杂谓词解析。

### 16.3 必须覆盖的负例

1. Concept fragment 文本相似但 claim ID 不同，不能互相授权；
2. 同一 obligation 下两张卡，只能使用卡片绑定的 claims；
3. 一个 Concept 匹配两个章节，未作封闭选择时必须 incomplete；
4. 一张卡匹配零章节，必须出现在 placement gap；
5. 改变 Concept Card 后旧分节 checkpoint 不可恢复；
6. 只改变无关章节输入时，受影响集合外的 checkpoint 可以恢复；
7. callback 重读已有 span，不算新进展；
8. callback 新读到代码但未编译出 claim，不能 fulfilled；
9. formalization 文件存在但不回答请求，不能 fulfilled；
10. request digest 或 parent checkpoint 被改，回调拒绝；
11. child research result 文件缺失或摘要错，Master blocked；
12. Master checkpoint 来自另一个 repo snapshot，恢复拒绝；
13. Writer blocked、validation failed、quality false 时 CLI 不能返回 0；
14. 新主线不能调用 `build_code2paper_graph`、`run_agentic_code2paper` 或 pipeline stage 编排；
15. 旧两个入口仍可独立解析和运行聚焦 fixture；
16. 条件只在精确括号反引号形式豁免，正文裸代码仍告警；
17. 多章节条件集合不串用；
18. Concept 和 proposition 同时出现时新主线拒绝。

### 16.4 检查点故障测试

在每个节点之后模拟中断，重新创建进程内对象后恢复，验证：

- 已完成节点不再次调用模型；
- 预算不重置；
- tool-call 去重记录不丢；
- behavior graph 和 compiled evidence 不丢；
- callback 继承原研究状态；
- Writer 未受影响章节不重写；
- 最终 manifest 与不中断运行在同一支持边界上。

不要求模型 prose 字节完全相同，但冻结输入、被授权事实、缺口和最终安全状态必须一致。

## 17. 验证命令和证据要求

具体实施由 OpenCode 按一次任务计划执行；Codex 最终只读验收不重跑测试或 API。

每个批次至少记录：

```text
python -m pytest -q <本批次聚焦测试>
python -m compileall -q src tests
git diff --check
```

只有计划明确到静态里程碑时才运行：

```text
python -m pytest -q
```

真实运行必须使用新的 `/tmp` 目录，记录：

- 执行前 `/health` 和 `/v1/models`；
- 模型 identity；
- queue、KV cache、OOM、abort 等运行状态；
- 精确命令和退出码；
- 代码摘要、输入摘要、Master/child thread；
- 每个节点、模型和工具调用摘要；
- 最终三份交付物和所有硬门；
- 运行后健康状态。

禁止把不同代码摘要上的最好结果拼成一个验收结论。

## 18. 最终验收标准

### 18.1 架构

- 新 Method Agent 是唯一未来交付主线；
- Master Agent 是真实顶层 LangGraph；
- 现有 Research LangGraph 作为子图复用；
- Writer 回调由 Master 路由并回到原研究状态；
- 新主线不调用两条旧编排；
- 旧路线仍有明确独立入口。

### 18.2 数据和证据

- Concept 每个字段有精确 fragment 和后台 claim/fact/span/relation 绑定；
- Concept 到章节、句子、claim 的映射不使用词语重合授权或 obligation 扩大；
- 作者意图不进入仓库正向事实；
- 条件、数字、公式和配置都有唯一来源；
- 回调新增内容经过完整 evidence -> fact -> claim -> concept 链；
- 缺失和歧义均失败关闭。

### 18.3 Writer 和发布

- 模型只看精简 WriterView；
- 后台校验使用新发布输入；
- 分节 checkpoint 绑定 Concept 和全部相关摘要；
- Writer/Editor/Rewrite 来源记录完整；
- 条件修复不会被另一套风格授权误拒绝；
- 候选稿无未支持正向事实；
- 已验证稿无未支持正向事实；
- 作者确认清单和外部队列真实；
- 最终完整性门通过。

### 18.4 恢复和终态

- Master 和研究子图均可跨实例恢复；
- resume 不重复已完成模型调用；
- 篡改或漂移失败关闭；
- 本地硬回调未解决时不能 trusted；
- CLI 返回码与产品状态一致；
- run summary、manifest 和 artifact 摘要相互闭合。

### 18.5 当前 P0 额外验收

- DyG、LinearRAG、EBCAR 在同一最终代码摘要上；
- 三个候选稿反向校验通过，unsupported positives 为 0；
- 所有计划标题和正文可编辑、结构完整；
- 支持句只覆盖实际章节；
- callback bundle 自解析且摘要有效；
- 已验证稿继续失败关闭；
- `final_integrity_gate_passed=true`。

## 19. 明确禁止的实现方式

- 不在现有 Research LangGraph 外再造一套重复研究图；
- 不用旧 R8 `V3GraphWrapper` 作为新 Master；
- 不让 Master 调用旧 story-first 或旧固定阶段 graph；
- 不保留 Concept -> proposition 的自动 fallback；
- 不用词语重合、硬编码项目词语或 obligation 扩大获得事实授权；
- 不因 Concept 改变而复用无 Concept digest 的旧章节；
- 不用整份 formalization 摘要满足任意请求；
- 不把 provider 写入的 `validated=True` 当成充分校验；
- 不让缺文件、空输出或异常成为成功；
- 不在架构重构中降低 evidence、qualifier、numeric、formula、authorship、callback、checkpoint 或 final
  integrity 门；
- 不删除旧路线以制造“只剩一条路径”的表面整洁；
- 不一次性重写 8,600 行 Writer；
- 不用单个项目或单次抽样宣布默认切换；
- 不把不同代码摘要的成功结果混用。

## 20. 下一次实施返回必须包含

1. 修改文件和每个文件的职责；
2. Master 图节点、边和条件路由清单；
3. 新旧入口实际指向；
4. 两条旧路线的隔离证明；
5. 新状态和 artifact 合同版本；
6. 父子线程、checkpoint 和恢复证据；
7. Concept fragment、field binding、placement 和 final alignment 证据；
8. Writer 新旧校验差异报告；
9. callback 回到同一研究状态的 trace；
10. 受影响章节集合和局部恢复证明；
11. 条件授权文件和修改事务前后诊断；
12. 精确测试命令、退出码、摘要和代码状态；
13. 真实运行的健康、模型、队列、KV cache、OOM/abort 记录；
14. 候选稿、已验证稿、作者确认清单和最终 manifest；
15. 未完成项和真实阻止原因。

## 21. 最终回答用户提出的 LangGraph 问题

目前 Method Agent 的“研究内部”已经是 LangGraph，不需要重新包一遍。

目前 Method Agent 的“产品外层”仍是 Python 顺序编排，有必要改成 Master Agent LangGraph，因为这里
确实存在研究、Concept、规划、Writer、回调、局部恢复和最终校验之间的状态与条件路由。

正确结构是“一个 Master Agent 顶层图 + 一个现有 Research 子图 + Writer/Editor/Rewrite/形式化等
明确模块”，而不是“把所有 Python 函数都改成 Agent”，也不是“让旧 R8 图成为新主流程”。
