# 05 · 多步工具、压缩与显式并发

> 当前接续（2026-10-07）：[独立 Gate-M PASS](stage05_M_acceptance_20261007.md)，28/49，M01–M03 完成；当前完整2103及 fresh cold1 经原严格读取器验收，全部独立读集释放。正式进入 P01–P04，保留 Gate-P/G0/G 阶段门；V2 Host API资格不代表默认CLI切换或Verified。下文早期状态按历史快照解释。

> 2026-10-04：本份七项纳入[第04–06份长期模块](stage04_06_long_module_execution_20261004.md)C/D段，默认单主执行者、按需协作。当前仍planned，正式实施沿原Gate-L→M→P前置；未获具体live授权时只做具名离线研究准备。实施人手可串行，P01–P04产品调度合同仍保留。

> 2026-09-28 执行计划；所有实现和新测试均待实施。历史代码/环境证据不计为任务完成。

依据：总设计 §§12、13、15.6、21 WP3c/WP4b。前后依赖以 [任务表](task_board.json) 为准；接口遵循 [interfaces.md](interfaces.md)。

在单 Writer 兼容门后增量开放多步与受控并发；改变吞吐，不改变默认LangGraph流程和验收。

### 先多步，后共享调度

L01 兼容门通过后依次 M01–M03、P01–P04；等待live授权时可以离线研究，但不能把离线实验计作越过 Gate-L 的集成完成。每个epoch限制请求、input/output、工具返回读取量、wall-clock，并只接受一个terminal candidate。多个内部step与内容repair不是同一计费单位，版本 c2p-dsh-task-loop-v1 明确二者。

RunCapsule和DSH压缩摘要都是派生视图。author surface、exact excerpt、occurrence与formula消费材料必须在真正生成正文的请求中可验证；缺失则正式恢复、留日志、重新计量，装不下回页编译owner。不能在provider前悄悄拼入未记录上下文。原始observations/claims的权限不会因摘要而升级。

### 并发配置与行为

| 配置 | 默认与合同 |
|---|---|
| execution.parallel_agents | false；本run串行且跨后端合计至多1个模型请求 |
| execution.max_parallel_agents | 开启后默认2个独立叶任务；父等待child/verify不占叶slot |
| backend_limits.<group>.max_inflight_requests | 每resource group默认1；本地不支持并发即可一直保持1 |
| backend_state_root | 同主机部署唯一SQLite队列，alias归并，持久permit但不另存费用余额 |
| 动态降低额度 | 停止新派发并等待在途排空；不把在途/unknown请求当作已释放 |

所有主/子/verify/compaction/title等模型请求共享门。开启时本run请求总上限为max_parallel_agents，后端再按max_inflight_requests收紧；两Agent任务可并行准备且后端仍串行。UI和CLI必须显示requested/effective限制；WP4b前显式开启返回unsupported。开关和上限在启动时冻结，运行中只允许有记录地降低有效值并排空；提高上限或从关闭改开启使用新执行配置。并发不授权跨阶段调度、同section revision多写者或新的事实来源。

### wave及恢复合同

wave冻结合法任务集合，单一join等待全部具名终态/回执；依赖按revision失效。scheduler用短事务联查run/backend容量、run公平轮转与run内FIFO。unknown占用保留并暂停整个resource group的新发送，不以TTL、Host心跳丢失或本地abort证明后端释放；可信not-sent或完整终态/恢复证据才能结算解冻。组内所有alias/进程共用配置身份和数据库，不接受私有队列伪称全局限制。请求槽保持到流可确认终态，再在spawn/等待工具前释放，避免父等待子死锁。仅保证同主机受控参与者；跨主机/其他裸客户端不在保证内。

QA必须真实多进程、不同run和alias，不用串行单元测试宣称无竞态。验证父等verify不占slot、混合开关、兄弟失败保留独立结果、老fence迟到、停止后不新派，覆盖真实账本读回和permit归属。

## 实施单元

每单元由owner实施、reviewer独立复核；同一文件只能由一个活动任务写入。“现有”路径已按当前树核对；“拟新增”为后续待实施文件，原责任范围和AT不变。

### M01 · 有界读取与证据权限

| 项 | 约定 |
|---|---|
| owner / reviewer | CONTRACT / QA |
| 前置 / WP | L01 / WP3c |
| 独占编辑范围 | `src/code2paper/integrations/dsh/facade.py`（现有）<br>`integrations/dsh/src/task-tools.ts`（现有）<br>`tests/integrations/dsh/test_scoped_reads.py`（拟新增）<br>`src/code2paper/agentic/authoring_execution_identity.py`（现有） |
| 步骤与交付 | 按task read-set开放限量句柄读取，导航与exact evidence分开；新观察由原内核晋升并引起相应revision，不让模型声明ID直接扩authority。 同步维护原VALIDATOR_BUNDLE_SOURCES版本化来源清单，仅添加本任务已落地的裁决文件；由LEAD串行分配该共享文件写权。 |
| 验收 AT-M01 | 越界路径、跨snapshot、摘要冒充完整span、超读取额度拒绝；合法定位可用，修改scope使旧TaskView失效。 仅改变新增/抽取的裁决逻辑即可使validator身份变化，缺来源文件明确拒绝。 |
| 待形成测试/证据 | `test_scoped_reads.py` |

### M02 · 多步材料恢复与compaction计量

| 项 | 约定 |
|---|---|
| owner / reviewer | DSH / QA |
| 前置 / WP | M01 / WP3c |
| 独占编辑范围 | `integrations/dsh/src/context-policy.ts`（拟新增）<br>`integrations/dsh/src/request-accounting.ts`（现有）<br>`tests/integrations/dsh/test_multistep_context.py`（拟新增）<br>`integrations/dsh/tests/context-replay.test.ts`（拟新增）<br>`src/code2paper/agentic/authoring_execution_identity.py`（现有） |
| 步骤与交付 | RunCapsule只派生，task/revision通过实际有来源admission进会话；导航与产文分步定义必需材料。压缩后检查真实请求，缺必需作者语义/occurrence/excerpt时从内核补回并重新计量；所有辅助模型调用经同账本。 同步维护原VALIDATOR_BUNDLE_SOURCES版本化来源清单，仅添加本任务已落地的裁决文件；由LEAD串行分配该共享文件写权。 |
| 验收 AT-M02 | 强制compaction后精确材料仍在产文请求；只剩摘要不算满足；装不下回原分页/合同owner；不得偷偷provider注入、缩义务或免费调用title/compact。 仅改变新增/抽取的裁决逻辑即可使validator身份变化，缺来源文件明确拒绝。 |
| 待形成测试/证据 | `test_multistep_context.py context-replay.test.ts` |

### M03 · epoch预算与多步恢复验收

| 项 | 约定 |
|---|---|
| owner / reviewer | QA / LEAD |
| 前置 / WP | M02 / WP3c |
| 独占编辑范围 | `tests/integrations/dsh/test_multistep_accounting.py`（拟新增）<br>`integrations/dsh/tests/multistep.test.ts`（拟新增） |
| 步骤与交付 | 对一个epoch最多一个terminal candidate，限制多请求/input/output/工具量/时限；分别验证表示失败与内容repair归属；复用同一reducer跨child/进程恢复。 |
| 验收 AT-M03 | 换child不清零，已发送格式失败/unfinished/research_required均留花费；pre-send/排队取消不收content attempt；超预算与辅助请求有真实发送零次或具名结算证据。 |
| 待形成测试/证据 | `test_multistep_accounting.py multistep.test.ts` |

### P01 · 同主机共享后端调度

| 项 | 约定 |
|---|---|
| owner / reviewer | RUN / QA |
| 前置 / WP | M03 / WP4b |
| 独占编辑范围 | `src/code2paper/integrations/dsh/backend_scheduler.py`（拟新增）<br>`src/code2paper/integrations/dsh/invocation_adapter.py`（拟新增）<br>`tests/integrations/dsh/test_backend_scheduler.py`（拟新增）<br>`src/code2paper/agentic/authoring_execution_identity.py`（现有） |
| 步骤与交付 | 部署唯一backend_state_root/SQLite；alias归并resource group，短事务联查run和backend上限；run公平轮转、run内FIFO。只存队列/permit元数据，费用仍原账本；未证实not-sent/终态不释放占用。 任一无法排除发送的unknown存在时暂停整个resource group的新发送，不只是扣一个slot。 同步维护原VALIDATOR_BUNDLE_SOURCES版本化来源清单，仅添加本任务已落地的裁决文件；由LEAD串行分配该共享文件写权。 |
| 验收 AT-P01 | 两个真实进程/两个run/两个alias共享上限；零额度、排队取消、usage缺失、流未结束、Host消失均正确；unknown不能靠TTL解冻；明确只保证同主机受控参与者。 组内不同配置身份/上限或各自私有数据库均拒绝声称共享限流。 仅改变新增/抽取的裁决逻辑即可使validator身份变化，缺来源文件明确拒绝。 |
| 待形成测试/证据 | `test_backend_scheduler.py` |

### P02 · 显式并发开关与两类限额

| 项 | 约定 |
|---|---|
| owner / reviewer | DSH / QA |
| 前置 / WP | P01 / WP4b |
| 独占编辑范围 | `integrations/dsh/src/execution-policy.ts`（拟新增）<br>`integrations/dsh/src/cli.ts`（拟新增）<br>`integrations/dsh/src/artifact-view.ts`（拟新增）<br>`tests/integrations/dsh/test_execution_policy.py`（拟新增）<br>`src/code2paper/agentic/authoring_execution_identity.py`（现有） |
| 步骤与交付 | CLI/UI显示execution.parallel_agents及effective值；默认关闭，单run跨后端合计至多一个模型请求。开启默认独立叶任务2、backend请求1，所有角色/verify/辅助调用受控；改小限额停止新派发并排空，不能偷取消或退款。 开启时本run所有父/子/verify/辅助模型请求合计上限为max_parallel_agents；后端再收紧。 同步维护原VALIDATOR_BUNDLE_SOURCES版本化来源清单，仅添加本任务已落地的裁决文件；由LEAD串行分配该共享文件写权。 |
| 验收 AT-P02 | 关=串行完整可用；开且任务2/backend1时模型仍串行；本地后端不支持并发可保持1；无效值拒绝；开关不改变合法流程/验收，无法约束其他未接入客户端要如实显示。 backend容量4、run上限2且父/辅助同时就绪时总在途仍≤2；请求槽在流可确认终态后、spawn/等待工具前释放，不能随stream对象返回提前释放。 仅改变新增/抽取的裁决逻辑即可使validator身份变化，缺来源文件明确拒绝。 |
| 待形成测试/证据 | `test_execution_policy.py` |

### P03 · 固定wave、join与叶任务名额

| 项 | 约定 |
|---|---|
| owner / reviewer | FLOW / QA |
| 前置 / WP | P02 / WP4b |
| 独占编辑范围 | `src/code2paper/integrations/dsh/task_store.py`（拟新增）<br>`integrations/dsh/src/workflow-driver.ts`（拟新增）<br>`tests/integrations/dsh/test_task_waves.py`（拟新增）<br>`src/code2paper/agentic/authoring_execution_identity.py`（现有） |
| 步骤与交付 | 冻结每个wave的合法task集合，一个等待点聚合回执；父等待child/verifier不占叶名额。互相独立scope才并发，同section revision单写者；新Research revision使受影响read-set失效。 同步维护原VALIDATOR_BUNDLE_SOURCES版本化来源清单，仅添加本任务已落地的裁决文件；由LEAD串行分配该共享文件写权。 |
| 验收 AT-P03 | 三任务限额、task等待verifier、兄弟失败、旧revision迟到提交无死锁/越权；独立已接受产物保留，受影响任务停止派发；join不能因为少一个结果就当完成。 仅改变新增/抽取的裁决逻辑即可使validator身份变化，缺来源文件明确拒绝。 |
| 待形成测试/证据 | `test_task_waves.py` |

### P04 · 共享调度故障与公平性复核

| 项 | 约定 |
|---|---|
| owner / reviewer | QA / LEAD |
| 前置 / WP | P03 / WP4b |
| 独占编辑范围 | `tests/integrations/dsh/test_scheduler_multiprocess.py`（拟新增）<br>`integrations/dsh/tests/concurrency.test.ts`（拟新增） |
| 步骤与交付 | 独立进程运行两run、混合开关、alias、停止/重启/迟到response，检查账本和permit一致性；有限确定任务序列验证轮转，不做无关压力live。 |
| 验收 AT-P04 | 没有双发、超额、饿死或永久父子互等；停止run不再新派；旧permit/fence重放拒绝；持久故障不会把unknown当空闲。 backend容量2且仅一个unknown时另一个空slot也不能发送；两个alias均受组级阻断。 |
| 待形成测试/证据 | `test_scheduler_multiprocess.py concurrency.test.ts` |

## 验证、交接与完成门

以下是实施后的执行命令，本轮未运行；所列旧文件已确认存在。新增任务测试落地后按上表AT逐项运行并登记实际节点/断言，不可只登记文件名。

```bash
python -m pytest -q tests/regression_20260917/test_ledger_recovery_matrix.py tests/test_agentic_unified_context_compiler.py
export C2P_DSH_CANDIDATE='0.2.0-rc.1+loop-origin.1'
export C2P_DSH_DEV_ROOT='/home/cuihengjia/agent/Code2Paper copy/.dsh-dev/candidates/0.2.0-rc.1+loop-origin.1'
npm --prefix integrations/dsh run typecheck
npm --prefix integrations/dsh run build
npm --prefix integrations/dsh run stage
npm --prefix integrations/dsh run test:compat
git diff --check
```

当前test:compat递归发现阶段Node测试；test:integration尚未定义，不能报告它已执行通过。新增runner须先验证发现/机器报告再纳入准入。实际运行经同一隔离launcher，不能因脚本缺失直接在日常profile启动。新增Python测试在tests/integrations/dsh/，Node测试在integrations/dsh/tests/；修原owner的反例也扩已有测试，不复制其实现。

交接包包含：任务ID、输入/代码/配置身份、接口及存储版本差异、改动文件、最小反例修前/修后结果、真实接线证据、准确命令/退出码/原始输出引用、未测项与恢复办法。独立reviewer依据 [verification.md](verification.md) 复核；Gate-M要求M01–M03；Gate-P另要求P01–P04。 各门要求对应AT及跨任务接线，不凭一个helper单测结案。

[返回总执行入口](README.md)
