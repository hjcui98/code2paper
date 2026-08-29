# Code2Paper 文档导航

本页是仓库文档的权威入口。文档中的日期表示快照时间，不代表它仍描述当前状态。
若历史报告与规范文档或当前状态报告冲突，以“规范 → 当前状态 → 历史证据”的顺序
解释。

## 当前状态

- [Research-Derived Method Authoring 下一阶段执行优化手册（2026-08-28）](code2paper_research_derived_authoring_optimization_execution_2026-08-28.md)：
  基于最新 EBCAR、DyG-Mamba、LinearRAG 真实产物与只看意图/代码的人工盲测基线，确认
  当前主要损失来自连续代码链缺失、Formalizer 多义务路由丢包、Writer 同步 witness 失败及
  Candidate 审计措辞污染；给出 connected dossier、typed derivation、AI-first Formalizer、
  两阶段 Writer/Binder、Candidate/Verified 独立完成语义和三项目真实回归的代码级执行顺序。
  它承接 2026-08-27 工作包并受 2026-08-22 执行权威约束，不修改 Verified 硬门。
- [Method Authoring 原文—意图—代码—运行链质量诊断与下一阶段执行计划（2026-08-27）](method_authoring_source_ledger_quality_execution_plan_2026-08-27.md)：
  基于三篇原文、作者意图、实际代码、冻结研究轨迹与 `225116` 产物，把质量损失分为
  not-discovered、discovered-but-blocked、rendered-low-quality 和 intent-code mismatch；
  定义 source-to-render 内容追踪、字段级对齐、段落合同、consumer-first Formalizer、
  semantic-delta repair/callback 及逐文件 WP0–WP7。这是 2026-08-22 执行权威之下的下一阶段
  工作包，不替代总体架构、Writer 规范或 Verified 门。
- [Method Authoring 最近六轮产物、分析与修复汇报（2026-08-27）](method_authoring_six_round_report_2026-08-27.md)：
  绑定 2026-08-25 23:09 至 2026-08-26 23:23 的 gated replay（`230920`→`011745`→
  `090052`→四洞修复+`211757`→薄内容修复→`225116`）。只证明该窗口的代码、冻结研究、
  模型与协议；不是执行权威，不是 `publication_ready` / D5 / §8 PASS。
- [Method 意图优先写作：质量失败诊断、架构修订与代码级执行计划（2026-08-22）](method_intent_first_authoring_redesign_2026-08-22.md)：
  绑定 DyG/LinearRAG live `133302`。Candidate 改为作者逻辑完整叙述 + 语义许可 +
  写作期回搜代码 + 学术 Formalizer + Rewrite 去代码味；Verified 仍 fail-closed。
  落实 2026-07-31 Writer 规范 §1.3/§1.6，并修订 2026-08-21「许可层纯确定性」仅针对
  Candidate 措辞权。这是 Method Authoring 质量的当前执行权威；不是新的总体架构规范，
  不得一次 `/implement` 全文。
- [Method 论证包编译：用一次综合编译替换逐 cluster Concept Card（2026-08-21）](method_argument_brief_compile_replacing_concept_cards_plan_2026-08-21.md)：
  冻结 Research 之后不再默认逐 cluster 生成 Concept Card；改为子句级许可的论证包。
  WP-A/B/C 已于 2026-08-22 只读验收 PASS。Candidate 语义许可与写作回搜以 2026-08-22
  意图优先计划为准。不是新的架构规范。
- [Method Authoring R5 质量退化根因与分片执行路线图（2026-08-20）](method_authoring_r5_quality_root_cause_and_code_execution_plan_2026-08-20.md)：
  R5 冻结 authoring 质量诊断与 WP0–WP6 分片。WP0 拷贝边界与后续 Writer/Formalizer/
  callback 门仍有效；WP1 把 Concept Card 写入 `--rebuild-authoring` 主链的部分由
  2026-08-21 论证包方案改道。不是新的架构规范，不得一次 `/implement` 全文。
- [Method Agent 现状复盘、Master Agent 主线与下一阶段代码级修复方案（2026-08-17）](method_agent_master_agent_mainline_execution_repair_plan_2026-08-17.md)：
  用户确认的新 Method Agent 唯一交付主线和独立上位文档；按实际代码梳理三条现存路线、
  当前模块与调用链，定义 Master Agent 顶层 LangGraph、现有研究子图复用、Concept Card
  精确绑定、真实研究回调、Writer 兼容迁移、父子检查点、旧路线冻结、逐文件修改和故障
  测试矩阵。该文件在上述范围内取代旧执行计划，高于一次任务的 `.agent/` 协调文件，
  但不取代总体架构和 Writer 规范。
- [R8 六项目验收状态（2026-08-01）](r8_acceptance_status_2026-08-01.md)：
  当前 R8 pass/fail 的权威入口；六项目 6/6 accepted，并记录 matrix、报告 digest、
  resume digest、统一 17 项硬门以及尚待完成的 clean-checkout release freeze。
- [项目进度与目标差距报告（2026-07-31）](project_status_and_gap_report_2026-07-31.md)：
  已更新到 2026-08-01；以 R8 实际通过为基线评估产品目标剩余差距。
- [R8 后 Research Agent 具体开发执行计划](post_r8_research_agent_execution_plan_2026-07-31.md)：
  将总体设计映射到当前代码、阶段性 R8 数据、具体修改模块和逐批退出条件。
- [R8 四项目 Method 与原论文覆盖审计](r8_method_paper_coverage_audit_2026-07-31.md)：
  对照 RAP、EBCAR、DyG、LinearRAG 的原稿、代码、claims 和最终正文，定位信息
  丢失、paper-code mismatch 与 deterministic prose repair。
- [可投稿 Method Writer Agent 设计](publication_ready_method_writer_design_2026-07-31.md)：
  把事实验证与论文论证分层，定义多权威写作、argument graph、专用
  Architect/Writer/Formalization/Editor、写作中返回研究和 publication utility
  验收。
- [根 README](../README.md)：安装、入口和两条运行路线。
- [迁移与切换指南](agentic_migration_guide.md)：`shadow → opt-in → canary →
  default_ready` 的正式切换规则。

## 规范性设计

下列文档规定系统应该如何工作，而不是记录某次运行结果：

- [自主错误反馈与自修复原则](agentic_error_feedback_and_self_repair_principle.md)：
  validator 发现的实质错误必须返回 owning Agent 做有界修复；不得靠降级硬门、
  静默过滤或缩减义务来通过；最终正文词句必须来自 Writer/Rewrite。
- [结构化输出恢复策略](agentic_structured_output_recovery_strategy.md)：
  harness 可修复简单语法损伤；内容、引用和证据错误必须交回 Agent。
- [鲁棒 LangGraph Research Agent 总体设计](agentic_robust_langgraph_research_writing_design_2026-07-19.md)：
  当前自主研究写作架构与信任边界。
- [可投稿 Method Writer Agent 设计](publication_ready_method_writer_design_2026-07-31.md)：
  Writer 子系统的当前规范；说明代码缺失、作者确认、形式化、文献和实验等不同
  authority 如何在不放松真实性的前提下形成完整论文叙事。
- [Method 质量下一阶段执行计划](agentic_method_quality_next_execution_plan_2026-07-19.md)：
  R0–R8 的历史实施基线；当前进度和下一批开发由 R8 后执行计划跟踪。

## 外部实现参考

- [五个 Agent 仓库的代码级参考研究（2026-08-10）](reference_agent_framework_code_research_2026-08-10.md)：
  面向当前 Research Agent 与 Method Writer 目标，对 Hermes Agent、OpenClaw、OpenHands SDK、
  PydanticAI 和 PydanticAI Harness 的固定版本进行文件/核心代码级比较；属于架构参考，
  不替代规范、执行计划或验收状态。
- [五个 Agent 仓库运行时深挖（2026-08-10）](reference_agent_framework_runtime_deep_dive_2026-08-10.md)：
  展开关键调用链、候选/提交/崩溃状态机、失败矩阵和外部测试代码证明链，并标明源码、测试、
  推断与采用建议的证据等级。
- [外部 Agent 机制落到 Code2Paper 的逐函数蓝图（2026-08-10）](reference_agent_framework_code2paper_blueprint_2026-08-10.md)：
  校正本项目已实现机制，定位 budget、QualityState、semantic frame、callback receipt、terminal
  identity 等真实调用链缺口，并给出文件级落点与纵向故障测试矩阵。

## 操作与验证

- [Agentic 路线迁移指南](agentic_migration_guide.md)
- [R8 设计差距审计快照](agentic_design_gap_audit_2026-07-21.md)
- [Gemma-4 R8 历史进度报告](agentic_r8_gemma4_progress_report_2026-07-20.md)

R8 日志与临时产物用于诊断，不是长期文档。正式验收结论必须绑定 matrix ID、
干净检出、配置、模型/API provenance、产物摘要和最终 recheck 报告。

## 历史设计与审计

这些文档保留决策背景和演进记录，不应单独用于声明当前能力：

- [早期最终设计](agentic_refactor_final_design.md)
- [分阶段执行计划](agentic_refactor_phased_execution_plan.md)
- [早期路线图](agentic_refactor_roadmap.md)
- [V2 研究写作设计](agentic_research_writing_agent_v2_design.md)
- [V2 执行计划](agentic_research_writing_agent_v2_execution_plan.md)
- [P4 完成审计](agentic_refactor_completion_audit.md)
- [Behavior template 过渡参考](agentic_behavior_template_transition_reference_2026-07-19.md)

## 机器可读证据

`docs/*.json` 是带日期的验收、评测或 rollout 证据快照：

- `agentic_p4_*_2026-07-18.json`：P4 review、adjudication 和 rollout 记录；
- `agentic_real_*_2026-07-18.json`、`agentic_domain_pruning_*`：真实项目基线；
- `agentic_rap_gemma*_2026-07-19.json`：RAP/Gemma 质量实验；
- `agentic_cutover_review_gate_2026-07-18.json`：历史 cutover 决策。

这些文件只证明其固定 commit、输入和协议下的结果。旧协议成功不能自动升级为
当前协议成功。

## 文档维护约定

1. R8 pass/fail 更新 R8 状态报告；项目级进度更新目标差距报告；实验细节写入新的
   带日期报告。
2. 状态报告必须写明 `as_of`、实际/假设状态、范围和证据位置。
3. 规范变化直接更新规范文档，并在状态报告中说明影响。
4. 历史报告原则上不重写结论；若已过时，在顶部添加 superseded 提示。
5. 不把 `/tmp` 路径、未结束日志或工作区测试通过数写成正式验收结论。
6. 默认路线切换只能由 migration/cutover 门禁授权，不能由单次 R8 代替。
