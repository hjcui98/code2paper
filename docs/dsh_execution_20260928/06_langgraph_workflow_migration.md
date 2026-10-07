# 06 · 默认 LangGraph 主流程与 Research 跨进程恢复

> 2026-10-04：本份八项纳入[第04–06份长期模块](stage04_06_long_module_execution_20261004.md)E/F段。默认单主执行者连续负责，按需协作；当前全部planned，须先过原Gate-P，再按G01–G03/Gate-G0→G04–G08/Gate-G推进。业务拓扑保留，DSH仍显式opt-in，不因长期派工改变默认入口。

> 2026-09-28 执行计划；所有实现和新测试均待实施。历史代码/环境证据不计为任务完成。

依据：总设计 §§6.3–6.5、10.2、15.7–15.8、21 WP5。前后依赖以 [任务表](task_board.json) 为准；接口遵循 [interfaces.md](interfaces.md)。

保留默认业务拓扑，把模型执行外置到DSH，并以真实图、真实角色和新进程恢复证明接线完整。

### 先补状态承载，再迁移角色

G01–G03 是 WP5 的入场修复与验证，Gate-G0 通过才启动 G04 领域角色迁移。G03 运行真实图与确定的外部提案fixture；不是预先要求全部DSH角色完成，避免循环依赖。G05注册完整节点合同并实现所拥有的Authoring及Editor/Rewrite最小真实适配，复用已有编辑/来源/重验门；尚待G06独立验证、G07补证的分支具名pending，不默认推进。G08在G06/G07完成后验证全部16节点真实行为与恢复；不能等WP6才补基本Editor/Rewrite。F01完成更完整编辑场景和权限收口，F02/F03/F04完成全文事务/图/导出。Gate-G不声称这些最终交付已完成。

| 基线真实锚点 | 需要保留/修补 |
|---|---|
| [product_authoring_graph](../../src/code2paper/agentic/product_authoring_graph.py) :33/52/66/107/129 | 16节点、直接边、条件边、owner、失效范围；逐项建接口和验收矩阵 |
| 同文件 :625/715/767/774/817/834/1315 | 默认handler推进、未知route取第一分支、缺LangGraph回退；当前Writer只在最终overlay运行author_review_items，均不能当DSH主图实现 |
| [research_graph](../../src/code2paper/agentic/research_graph.py) :448/520/632/660 | 已有snapshot、immutable payload与strict restore，扩原owner；旧注释不是字段事实 |
| 同文件 :2507/3363/3501/3567/3588/3675 | context/route仍closure，9节点，结果holder/last_result；逐字段持久化或配置引用重建 |
| [autonomous_method_agent](../../src/code2paper/agentic/autonomous_method_agent.py) :502/562/568 | 隐藏enrichment、无checkpointer、last_result；不能整体包装无模型RPC |
| [writing_callback_fulfillment](../../src/code2paper/agentic/writing_callback_fulfillment.py) :781/907/1545/3712 | 同步Writer、错误checkpoint降级旧provider、无saver；新路径严格、legacy行为单列 |
| [publication_method_writer](../../src/code2paper/agentic/publication_method_writer.py) :3082/3203/8730 | Formalizer→Narrative细化→Writer/Realizer/验证→最终Binder，不能为并发倒序 |

### 实际拓扑和恢复矩阵

按构图代码而非docstring列全部节点/条件边。特别覆盖 supervisor 的 partial_gap→advancer、compile_evidence→compile、no_tool_calls→terminator；compile 的 compiled/partial→advancer、rejected→supervisor、blocked→terminator。Master/Research固定独立thread_id，严格serializer和持久saver，按实际LangGraph API验证同步durability。

Research context中的pending/merged decision、route、termination、trace、revision budget、deadline和语义verifier配置均有来源；Python对象从持久引用重建而不序列化可执行闭包。每节点边界在全新Python进程恢复，比较状态/支持边界/预算/下一步/发送账及副作用；库级小图、同进程重新建实例和JSON round-trip不够。

### 原生角色与控制权

主Agent只在当前合法动作中选择；只有一条合法后继时内核直接推进。Research提案经policy，确定性critic不新增模型调用；语义revision与全文reverse verifier使用独立DSH verify任务。Writer不能自判supported；验证缺失保持pending，不能设置None绕过。

正常write与research_required使用同一outbox/interrupt/receipt/resume协议；补证只失效受影响revision，原history/预算/lineage延续。DSH Session是交互记录，LangGraph checkpoint是流程状态，Python产物/账本是证据和预算权威；结果manifest替代last_result。

阶段回退可继续使用固定旧引擎与fresh root参考运行，不把新账本给旧程序强制resume。opt-in路径遇缺handler/依赖/身份就失败，不默默回原Agent。全部角色到位后仍要G08生产入口证据，而不是测试一组未被产品调用的适配器。

## 实施单元

每单元由owner实施、reviewer独立复核；同一文件只能由一个活动任务写入。“现有”路径已按当前树核对；“拟新增”为后续待实施文件，原责任范围和AT不变。

### G01 · 严格主图入场与合法路由

| 项 | 约定 |
|---|---|
| owner / reviewer | FLOW / QA |
| 前置 / WP | P04 / WP5 |
| 独占编辑范围 | `src/code2paper/agentic/product_authoring_graph.py`（现有）<br>`src/code2paper/integrations/dsh/workflow_adapter.py`（拟新增）<br>`src/code2paper/agentic/checkpointing.py`（现有）<br>`tests/integrations/dsh/test_workflow_admission.py`（拟新增）<br>`src/code2paper/agentic/authoring_execution_identity.py`（现有） |
| 步骤与交付 | 为DSH opt-in要求真实LangGraph、完整handler、持久saver和稳定thread_id/严格序列化；未知route/缺handler明确失败，保留旧入口行为但不当新图实现。唯一合法下一步确定推进。 同步维护原VALIDATOR_BUNDLE_SOURCES版本化来源清单，仅添加本任务已落地的裁决文件；由LEAD串行分配该共享文件写权。 |
| 验收 AT-G01 | 缺每个handler、非法route、缺LangGraph/saver均失败；不可略过Formalizer或final验证；默认推进overlay不能通过此门，确定边不额外请求规划模型。 仅改变新增/抽取的裁决逻辑即可使validator身份变化，缺来源文件明确拒绝。 |
| 待形成测试/证据 | `test_workflow_admission.py` |

### G02 · Research运行状态持久重建

| 项 | 约定 |
|---|---|
| owner / reviewer | FLOW / QA |
| 前置 / WP | G01 / WP5 |
| 独占编辑范围 | `src/code2paper/agentic/research_graph.py`（现有）<br>`src/code2paper/agentic/autonomous_method_agent.py`（现有）<br>`src/code2paper/agentic/checkpointing.py`（现有）<br>`tests/integrations/dsh/test_research_state_hydration.py`（拟新增）<br>`src/code2paper/agentic/authoring_execution_identity.py`（现有） |
| 步骤与交付 | 扩现LoopStateSnapshot/immutable payload/strict restore；逐字段归属context的route/pending/decision/trace/deadline/budget/verifier配置。外部运行对象从已验证引用重建；结果从持久manifest读出，移除新路径last_result依赖；列真实9节点条件边。 同步维护原VALIDATOR_BUNDLE_SOURCES版本化来源清单，仅添加本任务已落地的裁决文件；由LEAD串行分配该共享文件写权。 |
| 验收 AT-G02 | 完整状态可在新进程按引用重建；错误摘要/身份/缺引用拒绝；stage checkpoint导入与逐节点checkpoint区分；不再造一套忽略已有observations的快照。 仅改变新增/抽取的裁决逻辑即可使validator身份变化，缺来源文件明确拒绝。 |
| 待形成测试/证据 | `test_research_state_hydration.py` |

### G03 · 实际Research图逐节点恢复入场门

| 项 | 约定 |
|---|---|
| owner / reviewer | QA / LEAD |
| 前置 / WP | G02 / WP5 |
| 独占编辑范围 | `tests/integrations/dsh/test_research_process_resume.py`（拟新增） |
| 步骤与交付 | 在真实9节点及条件边逐处新进程interrupt/resume，外部提案用确定fixture executor；比较支持边界、状态摘要、next node、预算、副作用和发送账。此门检验状态承载，再允许G04接真实DSH角色。 |
| 验收 AT-G03 | 包括supervisor partial_gap/compile/no_tool_calls和compile compiled/partial/rejected/blocked；不能用同进程round-trip或玩具图代替；每次恢复与不中断运行同义，无last_result。 |
| 待形成测试/证据 | `test_research_process_resume.py` |

### G04 · Research提案、工具与语义边界外置

| 项 | 约定 |
|---|---|
| owner / reviewer | FLOW / QA |
| 前置 / WP | G03 / WP5 |
| 独占编辑范围 | `src/code2paper/agentic/research_nodes.py`（现有）<br>`src/code2paper/agentic/research_graph.py`（现有）<br>`src/code2paper/integrations/dsh/facade.py`（现有）<br>`integrations/dsh/src/task-tools.ts`（现有）<br>`tests/integrations/dsh/test_research_dsh_execution.py`（拟新增）<br>`src/code2paper/agentic/autonomous_method_agent.py`（现有）<br>`src/code2paper/agentic/authoring_execution_identity.py`（现有） |
| 步骤与交付 | 拆supervisor提案与policy merge，intent enrichment/有限拒绝修复由DSH；内核执行合法observation/critic/compile至下一外部边界。语义revision需独立verify待回执；stop/record_gap也经policy。 从实际build_product_research_runtime入口移出enrichment模型调用，不能只修改未被入口使用的adapter。 同步维护原VALIDATOR_BUNDLE_SOURCES版本化来源清单，仅添加本任务已落地的裁决文件；由LEAD串行分配该共享文件写权。 |
| 验收 AT-G04 | Python出口拒绝哨兵下真实图运行；unknown tool/跨snapshot/authority伪造/耗尽均拒绝；确定性critic无新增模型调用；旧Research整函数不能包装为无模型RPC。 仅改变新增/抽取的裁决逻辑即可使validator身份变化，缺来源文件明确拒绝。 |
| 待形成测试/证据 | `test_research_dsh_execution.py` |

### G05 · Authoring各角色原生DSH接线

| 项 | 约定 |
|---|---|
| owner / reviewer | CONTRACT / QA |
| 前置 / WP | G04 / WP5 |
| 独占编辑范围 | `src/code2paper/agentic/publication_method_writer.py`（现有）<br>`src/code2paper/integrations/dsh/workflow_adapter.py`（拟新增）<br>`integrations/dsh/src/role-dispatch.ts`（现有）<br>`tests/integrations/dsh/test_authoring_role_workflow.py`（拟新增）<br>`src/code2paper/agentic/autonomous_method_agent.py`（现有）<br>`src/code2paper/agentic/authoring_execution_identity.py`（现有） |
| 步骤与交付 | 按真实顺序初始plan→Formalizer→同plan版本化Narrative细化→Writer/Realizer→验证→最终Binder；每角色唯一受限合同，保留已有IR与纯投影。Realizer不能获得新正文措辞权。 接管build_product_planning的可选模型路径，并与G04交接同一产品入口文件。 同时接入默认16节点必需的Editor/Rewrite最小真实DSH适配，复用已有编辑、authorship、失效/重验合同；split/review节点有真实确定性handler，不留缺口等WP6。 同步维护原VALIDATOR_BUNDLE_SOURCES版本化来源清单，仅添加本任务已落地的裁决文件；由LEAD串行分配该共享文件写权。 |
| 验收 AT-G05 | fake provider走真实各builder/parser/assessor，顺序错误拒绝；atom/detail置换、sum→mean、条件丢失拒绝；必要公式与最终Binder不可被Writer成功掩盖。 全部16节点合同完整注册，本任务拥有的Authoring/Editor/Rewrite适配真实运行；尚待G06验证、G07补证的分支保持具名pending，不默认推进。Editor/Rewrite至少一次真实mock调用及已有确定性重验，不能用no-op代替。 仅改变新增/抽取的裁决逻辑即可使validator身份变化，缺来源文件明确拒绝。 |
| 待形成测试/证据 | `test_authoring_role_workflow.py` |

### G06 · 独立语义验证任务与确定性合并

| 项 | 约定 |
|---|---|
| owner / reviewer | CONTRACT / QA |
| 前置 / WP | G05 / WP5 |
| 独占编辑范围 | `src/code2paper/agentic/publication_method_writer.py`（现有）<br>`src/code2paper/integrations/dsh/result_ingest.py`（现有）<br>`integrations/dsh/src/role-dispatch.ts`（现有）<br>`tests/integrations/dsh/test_independent_verifier.py`（拟新增）<br>`src/code2paper/agentic/authoring_execution_identity.py`（现有） |
| 步骤与交付 | 将proposition alignment、reverse semantic verifier和Research revision semantic callback外置独立verify任务；冻结正文/evidence/validator/task身份，按原裁决合并。完成前pending，不置空verifier。 同步维护原VALIDATOR_BUNDLE_SOURCES版本化来源清单，仅添加本任务已落地的裁决文件；由LEAD串行分配该共享文件写权。 |
| 验收 AT-G06 | Writer自报supported不接受；错revision/缺原文/无支持句拒绝；缺verify仍pending，Python无隐藏LLM；编辑使旧回执失效，Verified只由原硬门产生。 仅改变新增/抽取的裁决逻辑即可使validator身份变化，缺来源文件明确拒绝。 |
| 待形成测试/证据 | `test_independent_verifier.py` |

### G07 · callback补证与增量续作

| 项 | 约定 |
|---|---|
| owner / reviewer | FLOW / QA |
| 前置 / WP | G06 / WP5 |
| 独占编辑范围 | `src/code2paper/agentic/writing_callback_fulfillment.py`（现有）<br>`src/code2paper/integrations/dsh/workflow_adapter.py`（拟新增）<br>`tests/integrations/dsh/test_callback_workflow.py`（拟新增）<br>`src/code2paper/agentic/authoring_execution_identity.py`（现有） |
| 步骤与交付 | 拆typed gap/lineage校验→Research任务→依赖重编→新Writer；复用Research history/预算/问题lineage。受影响unit新revision/epoch，独立receipt保留；DSH路径checkpoint不兼容拒绝，旧legacy fallback显式隔离。 同步维护原VALIDATOR_BUNDLE_SOURCES版本化来源清单，仅添加本任务已落地的裁决文件；由LEAD串行分配该共享文件写权。 |
| 验收 AT-G07 | 正常写作与research_required续作都通过interrupt/receipt/resume；无新证据不fulfilled；同路径新字节触发失效；预算跨进程保留，旧scope正文不得重用。 仅改变新增/抽取的裁决逻辑即可使validator身份变化，缺来源文件明确拒绝。 |
| 待形成测试/证据 | `test_callback_workflow.py` |

### G08 · 完整主图流程与角色恢复独立验收

| 项 | 约定 |
|---|---|
| owner / reviewer | QA / LEAD |
| 前置 / WP | G07 / WP5 |
| 独占编辑范围 | `tests/integrations/dsh/test_full_workflow_recovery.py`（拟新增）<br>`tests/integrations/dsh/test_no_hidden_python_llm.py`（拟新增） |
| 步骤与交付 | 全链重新检查G01/G03和真实DSH角色；在outbox后checkpoint前、output后ingest前、commit后checkpoint前、旧fence callback及run停止后重启处注入故障。比对旧流程语义，不只比节点数。 范围为流程和全部必需角色；全文对外发布仍等待F02，图和导出等待F03/F04，不在此设置交付完成。 |
| 验收 AT-G08 | 所有模型调用归DSH且同账本；真实图无缺handler/default route/last_result退路；响应已存本地结算、unknown不重发、幂等apply；停止后不派新模型，仍可确定性恢复读取。 G06/G07完成后，全部16节点的真实领域行为与恢复闭合，不能仍以待实现pending或fixture executor计完整迁移。 |
| 待形成测试/证据 | `test_full_workflow_recovery.py test_no_hidden_python_llm.py` |

## 验证、交接与完成门

以下是实施后的执行命令，本轮未运行；所列旧文件已确认存在。新增任务测试落地后按上表AT逐项运行并登记实际节点/断言，不可只登记文件名。

```bash
python -m pytest -q tests/test_agentic_product_authoring_graph.py tests/test_agentic_research_checkpoint_resume.py tests/test_agentic_graph_research_loop.py tests/test_agentic_research_graph_callback_continuation.py tests/test_agentic_callback_dependency_closure.py tests/test_agentic_callback_resume_product.py tests/regression_20260922/test_authoring_contract_closure.py
export C2P_DSH_CANDIDATE='0.2.0-rc.1+loop-origin.1'
export C2P_DSH_DEV_ROOT='/home/cuihengjia/agent/Code2Paper copy/.dsh-dev/candidates/0.2.0-rc.1+loop-origin.1'
npm --prefix integrations/dsh run typecheck
npm --prefix integrations/dsh run build
npm --prefix integrations/dsh run stage
npm --prefix integrations/dsh run test:compat
git diff --check
```

当前test:compat递归发现阶段Node测试；test:integration尚未定义，不能报告它已执行通过。新增runner须先验证发现/机器报告再纳入准入。实际运行经同一隔离launcher，不能因脚本缺失直接在日常profile启动。新增Python测试在tests/integrations/dsh/，Node测试在integrations/dsh/tests/；修原owner的反例也扩已有测试，不复制其实现。

交接包包含：任务ID、输入/代码/配置身份、接口及存储版本差异、改动文件、最小反例修前/修后结果、真实接线证据、准确命令/退出码/原始输出引用、未测项与恢复办法。独立reviewer依据 [verification.md](verification.md) 复核；Gate-G0只要求G01–G03；Gate-G要求后续G04–G08并复验入场门，不反向阻塞G04。 各门要求对应AT及跨任务接线，不凭一个helper单测结案。

[返回总执行入口](README.md)
