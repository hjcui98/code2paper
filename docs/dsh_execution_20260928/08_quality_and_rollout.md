# 08 · 完整离线、真实质量与迁移评审

> 2026-09-28 执行计划；所有实现和新测试均待实施。历史代码/环境证据不计为任务完成。

依据：总设计 §§19–24、21 WP7；审计 §§14.5、16.3。前后依赖以 [任务表](task_board.json) 为准；接口遵循 [interfaces.md](interfaces.md)。

将实现验收、模型兼容、真实质量、对比实验和默认迁移分开，用各自绑定证据给出结论。

### 验收层次

| 层次 | 结论上限 |
|---|---|
| 单元/合同/故障注入 | 绑定代码、输入与mock行为；不证明真实生成质量 |
| V01/A01/V02 | 独立单Writer的离线集成；不是主图迁移 |
| L01 | 一个真实Qwen请求兼容；不是审计L1 |
| G08/F04/Q01 | 全图、全文、图和导出的离线接线及完整准入 |
| Q02 | 固定材料/确定响应下迁移行为等价；实际协议差异明列 |
| Q03 | 授权的审计L1/L2/L3及指定质量评价 |
| Q04 | 隔离C0/C1/C2与消融的有限样本结论 |
| Q05 | 迁移评审及操作者批准；不自动宣布D5/默认cutover/release freeze |

### §16.3的具体执行合同

按 [审计方案](../Code2Paper_代码审计与修复执行方案_20260922.md) §14.5、§16.3：L1至少包含grounded冻结段落、无atom作者段落、局部repair；L2完整EBCAR冻结Research authoring fork；L3至少一个不同结构/公式密度项目。逐层冻结输入、角色预算、attempt/repair/callback次数、停止条件、模型和validator/config/DSH组成，生成匹配离线回执并单独获得live授权。

对每层记录required义务守恒、事实/权限/公式/authorship/final-integrity硬门、真实连贯性/完整性/可发表性评价。运行前指定盲评协议、评审者与人工核对范围；如现有文档未固定评分阈值，在Q03 ready前由质量负责人和操作者确认，不能看完结果再调及格线。主观评分和确定门各报结果，不以较少tokens/accepted布尔/测试数代替质量。

### 可比评测与发布

C0旧驱动、C1原生DSH无专用IR、C2领域插件使用同冻结任务/模型/预算/截止条件；生成与评测资源隔离，gold只在评测端。不同条件的session/memory不可共享，不读其他候选或开发答案。复用Research既报增量成本又报含摊销的端到端成本，全部失败和辅助请求入账；任务分母、预算或停止规则不等时不得归因为效率提升。

Q01扩A01同一准入owner的阶段必测集合，不能再建一套手写报告放行。全离线命令用python -m pytest -q -m 'not live_llm'；Node typecheck/build/test:compat/test:integration由B02定义。必测跳过、零测试、runner失败、身份在测试期间变化均阻断；历史0918结果只作参考。一次全套通过后不在无变化时反复跑，代码/validator/config/composition变更则重新准入。

live授权缺失时停在具体live门，继续允许不依赖结果的离线分析，不标任务完成。上线材料必须包含完整证据、未测项、故障恢复演练和回退到旧固定引擎+fresh root的方法；不把新schema强制交旧版resume。实际push/merge/部署/默认开关均按届时用户授权执行，当前规划不授权它们。

## 实施单元

每单元由owner实施、reviewer独立复核；同一文件只能由一个活动任务写入。下列路径标“拟新增”的当前不存在，不是已有能力。

### Q01 · 完整跨语言离线准入

| 项 | 约定 |
|---|---|
| owner / reviewer | QA / LEAD |
| 前置 / WP | F04 / WP7 |
| 独占编辑范围 | `src/code2paper/agentic/live_admission_preflight.py`（现有）<br>`tests/integrations/dsh/test_dsh_admission.py`（拟新增）<br>`integrations/dsh/tests/`（拟新增）<br>`src/code2paper/agentic/authoring_execution_identity.py`（现有） |
| 步骤与交付 | 在V02的同一准入owner扩完整必测集合，执行Python全离线、Node build/typecheck/compat/integration、崩溃矩阵及环境保护；逐子命令退出码/原始输出摘要进入聚合回执，绑定当前engine/validator/config/bundle/runtime。 同步维护原VALIDATOR_BUNDLE_SOURCES版本化来源清单，仅添加本任务已落地的裁决文件；由LEAD串行分配该共享文件写权。 |
| 验收 AT-Q01 | 未运行的集合不可自报覆盖；任一skip必测/子进程失败/身份漂移阻断；4014旧回执不充数；offline-ready与live-ready继续分开。 仅改变新增/抽取的裁决逻辑即可使validator身份变化，缺来源文件明确拒绝。 |
| 待形成测试/证据 | `full_offline_admission` |

### Q02 · 迁移行为等价与差异归因

| 项 | 约定 |
|---|---|
| owner / reviewer | QA / LEAD |
| 前置 / WP | Q01 / WP7 |
| 独占编辑范围 | `tests/integrations/dsh/test_execution_equivalence.py`（拟新增）<br>`/tmp/<fresh-task-run>/evaluation-evidence/`（拟新增） |
| 步骤与交付 | 用相同冻结材料与确定响应比较旧C0和新C2的义务/权限/验收/恢复/产物；逐项记录terminal协议、prompt wrapper、wire和模型参数差异，不能在不可比条件推断效率。 |
| 验收 AT-Q02 | 没有靠少段落/少公式/更宽门提升指标；所有aux与Research复用成本可追踪；流程差异均有设计依据和复核，未测质量不写改善。 |
| 待形成测试/证据 | `test_execution_equivalence.py` |

### Q03 · 审计§16.3真实L1/L2/L3质量验收

| 项 | 约定 |
|---|---|
| owner / reviewer | QA / LEAD |
| 前置 / WP | Q02 / WP7 |
| 独占编辑范围 | `tests/live/profiles/`（现有）<br>`docs/dsh_execution_20260928/quality-evaluation-protocol.md`（拟新增） |
| 步骤与交付 | 逐层另获live授权和匹配回执，执行L1 grounded/无atom作者段/局部repair，L2完整EBCAR冻结Research authoring fork，L3不同结构或公式密度项目；冻结盲评/人工标准与评审者，保留全部尝试。 |
| 验收 AT-Q03 | required义务不减，事实/公式/权限/authorship/final-integrity硬门全过且指定质量评价完成；Candidate/Verified分开结论；不把L01小live或静态计数当§16.3完成。 |
| 待形成测试/证据 | `audit_16_3_L1_L2_L3` |

授权边界：该任务的模型/服务调用须单独live授权；本执行计划不是调用批准。

### Q04 · C0/C1/C2隔离评测与消融

| 项 | 约定 |
|---|---|
| owner / reviewer | QA / LEAD |
| 前置 / WP | Q03 / WP7 |
| 独占编辑范围 | `docs/dsh_execution_20260928/benchmark-protocol.md`（拟新增）<br>`/tmp/<fresh-task-run>/evaluation-evidence/`（拟新增） |
| 步骤与交付 | 冻结同repo/intent/marks、模型、预算、停止条件和完整case集合；C0旧驱动、C1原生DSH、C2领域插件。每条件隔离session/memory，gold只在独立评测端；明确复用Research成本和小样本不确定性。 C1/C2具有相同安全/数据访问边界，使用同一独立评价端，盲化候选顺序与条件名；C1流程差异单列。 |
| 验收 AT-Q04 | 泄漏gold/其他候选/开发答案即该次无效；分母/预算不等不归因更高效；有盲评、可复算成本及失败集合；额外live和评审服务纳入单独授权额度。 评价不因C2专用receipt存在而加分，也不因C1缺该receipt直接判低质量。 |
| 待形成测试/证据 | `isolated_benchmark_and_ablation` |

授权边界：该任务的模型/服务调用须单独live授权；本执行计划不是调用批准。

### Q05 · 迁移评审、渐进切换与回滚演练

| 项 | 约定 |
|---|---|
| owner / reviewer | LEAD / QA |
| 前置 / WP | Q04 / WP7 |
| 独占编辑范围 | `docs/dsh_execution_20260928/`（现有）<br>`integrations/dsh/dev/`（现有） |
| 步骤与交付 | 汇总所有门与残余限制，演练旧固定版本+fresh root回退及已验证Research import；拟定opt-in→小范围→默认的具体切换材料，最后提交操作者明确批准。新schema数据不强塞旧程序resume。 |
| 验收 AT-Q05 | 回滚可执行且不会覆盖新/旧产物；默认切换、rollout、release freeze分别有证据和授权，不自动宣布D5；正常DSH使用不被开发配置替换。 |
| 待形成测试/证据 | `rollout_review_and_rollback` |

授权边界：先形成具体可审查材料和回滚证据，实际切换另获批准。

## 验证、交接与完成门

以下是实施后的执行命令，本轮未运行；所列旧文件已确认存在。新增任务测试落地后按上表AT逐项运行并登记实际节点/断言，不可只登记文件名。

```bash
python -m pytest -q tests/regression_20260917/test_quality_comparison.py tests/regression_20260917/test_live_admission.py tests/regression_20260922/test_matrix_coverage.py
npm --prefix integrations/dsh run typecheck
npm --prefix integrations/dsh run build
npm --prefix integrations/dsh run test:integration
git diff --check
```

Node脚本由B02/H01先定义并锁定，实际运行必须经隔离launcher，不能因脚本缺失而直接在日常profile启动。新增Python测试在tests/integrations/dsh/，Node测试在integrations/dsh/tests/；修原owner的反例也扩已有测试，不复制其实现。

交接包包含：任务ID、输入/代码/配置身份、接口及存储版本差异、改动文件、最小反例修前/修后结果、真实接线证据、准确命令/退出码/原始输出引用、未测项与恢复办法。独立reviewer依据 [verification.md](verification.md) 复核；Q01先形成完整offline-ready，Q02形成迁移等价报告；Gate-Q要求Q03/Q04各自授权与质量证据。Q05实际切换仍需操作者明确批准。 各门要求对应AT及跨任务接线，不凭一个helper单测结案。

[返回总执行入口](README.md)
