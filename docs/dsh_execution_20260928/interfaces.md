# 跨语言接口与权威合同

> **2026-10-04 当前：[GC 集中返修独立 Gate-C PASS](stage03_gc_repair_acceptance_20261004.md)**，三组问题关闭，原第03份六项done。下批依[第04份整批指令](stage04_batch_execution_instructions_20261004.md)实现持久claim、唯一账本与真实Host/CLI；本文权威合同和Gate-R/V保持。下方较早门状态属于历史范围。

> 2026-10-03 23:03：[第03份独立 Gate-C 裁决](stage03_gate_c_review_and_batch_repair_20261003.md)为 CHANGES_REQUESTED；现按其 §3–§6 集中修复跨语言字符规则、冻结材料当前绑定及新 ingest 的投影引用完整性。本文原权威/合同继续适用，Gate-B/H/K 保持通过；第04份仍待 Gate-C。

> 2026-10-03 18:03 当前：[独立裁决](stage_four_group_repair_acceptance_20261003.md)已通过 Gate-B/H 和正式 Gate-K；实际 runtime API 以[当前 H02 冻结](h02_interface_freeze_020.md)为准。下一批按[第03份整批指令](stage03_batch_execution_instructions_20261003.md)实施，本文领域/wire/权限合同继续适用。下方旧日期提示及§0中2026-10-01的“尚待冻结／全拒绝”均是历史候选状态，不再阻断第03份。

> 2026-10-02 22:10：[模块级派发候选 Gate-H 审查](stage_static_entry_gate_h_review_20261002.md) GHS-1 表明公开 `streamWithRegistration(..., true)` 可取得受信派发，
> 不符合[接口裁决 §6.2](h04_loop_origin_escalation_20261001.md) 第 1 项"不得暴露可 mint/run 的入口"；GHS-2 表明 runtime 注册未随生命周期注销。
> 私有来源接口仍未冻结，Gate-H/K 未过，领域唯一权威不变；接续见 [README §3.15](README.md)。

> 2026-10-02当前：[返修差分与完整接续](stage_loop_origin_repair_acceptance_20261002.md)。LO1–3原回归独立通过、source/types已交付，公共admit预消费在交付/source-built真实复现，私有来源接口未冻结。既有§6.2-3禁止公共consume同样禁止改变状态的admission；来源不以state/timing/material授权。Gate-H仍CHANGES_REQUESTED，正式Gate-K未过。

> 2026-10-01 19:40：loop-origin.1已实装但尚未接口冻结；[独立裁决LO-1–4](stage_loop_origin_acceptance_20261001.md)记录普通公开入口、公共NO_ADAPTER、旧manifest及私有消费/source/types差异。原[接口裁决§6](h04_loop_origin_escalation_20261001.md)继续有效，不以当前JS导出替代已批准合同；Gate-H/K未过，领域唯一权威不变。

> 本文为49单元共享的实现约束。2026-09-29 开发目标选择 0.2.0-rc.1 候选；既有兼容实现和旧版验收保留，但不外推新版。依赖实际 DSH 能力的表示与时序由目标版本 H01–H04 冻结，领域权威不随版本迁移改变。

## 0. 目标版本和接口冻结范围

旧 `h02_interface_freeze.md` 绑定 0.1.5 与摘要 `0ba7f1ce…`，保持原字节。窗口二在
`h02_interface_freeze_020.md` 交付目标版本的真实导出、类型、创建时序、资源责任和消费示例，
QA/LEAD 复验冻结后才能用于新版依赖接线。类型适配不授权改变 Python 领域合同或增设 TS 持久账本。

Session V4 的独立 tool 消息和 0.2 的失败 step 恢复分别处理：合成错误结果不是成功 terminal，
工具结果未知不是模型请求已结算或可重发的证明。旧 V3 记录只通过具名只读 reader 诊断，
不能以宽松回退、自动迁移日常会话或给旧记录重新封摘要获得兼容。

`llm/stream` 的全局可见性、请求自报 ID、route+digest 相等、loop 标记与冻结对象均不单独
授予来源身份。可信授权必须关联具体准备与实际调用；session 计数和摘要队列需证明不能在合法
调用等待期间被裸请求抢占。prepared/direct 的底层入口均验同一授权，capture 与 accounting
消费同一可信来源。详细交付顺序和写权见 [第 01 份](01_baseline_and_dsh_compatibility.md)。

### 历史runtime来源接口裁决（2026-10-01；当前冻结见上方）

[LEAD裁决§6](h04_loop_origin_escalation_20261001.md)准许在新隔离本地patch候选为实际loop
内部派发提供私有来源。bridge只消费公开、只读、不能铸造/修改/预消费的核验接口；接口尚待
窗口二实现与独立冻结。public stream及public prepared handle等入口不继承来源；prepared/
NO_ADAPTER合法派发保留原registration/config/单次dispatch与全部Host守卫。来源不是预算授权。
原0.2树43490765…保留，patched树另记实际摘要，base version/候选ID/patch ABI/来源/构建
分别绑定；I01后消费同一完整composition，不用patch PASS批准原npm树。当前全拒绝/13skip
是安全检查点而非H04完成，原8份文档/49任务及领域权威不变。

## 1. 唯一权威及接口可见性

| 权威对象 | 唯一owner | 其他系统允许做什么 |
|---|---|---|
| 领域IR/evidence/read-set/authority | 原Python编译器、导入验证、索引 | DSH读取受授权投影，不能宣布新事实 |
| 合法流程/失效/验收/正式提交 | Python LangGraph、原assessor/Binder/发布owner | Host递交可信事实并读取回执 |
| Agent模型/工具循环/Session | DSH | Python不暗中运行模型循环 |
| 预算/发送/usage/恢复结论 | 原Pythoninvocation账本+唯一reducer | TS转发hook/RPC事实，Session展示，task_store持引用 |
| outbox/task/claim | Python task_store，fence复用原identity owner | Host领取执行，不自定余额 |
| 调度permit | Python同主机scheduler，费用仍原账本 | Host等队列；不能TTL释放unknown |
| 正文词句来源 | Writer/Formalizer/Editor/Rewrite的可信生成输出 | Host/Realizer/主Agent只能引用与确定性组合 |

模型可见只有限读、Research窄提案和typed terminal。Host私有方法包括task.prepare/claim/record_output/ingest/resume与request.reserve/dispatch/settle/mark_unknown；仅实现到对应owner完成的阶段。operator配置、迁移、恢复管理和export不注册普通模型工具。caller/run/task/snapshot/claim/fence由绑定层注入；模型同名字符串不是身份凭据。

H02→H03/H04 的当前真实导出、最小 mock recorder 和资源所有权见 [0.2 当前接口冻结](h02_interface_freeze_020.md)及[独立批准](stage_four_group_repair_acceptance_20261003.md)。旧版 [接口记录](h02_interface_freeze.md)、[最终批准](h02_acceptance.md)与[阶段交接要求](h02_h04_handoff.md)保留原版本范围。H04 不依赖后续 C/R 生产协议完成，也不把 recorder 当成 Python 权威账本。生产协议冻结后须复验接线，不能凭兼容实验回执批准模型请求。

## 2. 组成身份与版本

I01复用engine与validator身份，形成一个DSH composition对象，至少绑定：实际runtime树/lock/Node、bundle构建输入及实际JS、Loader解析位置/peer module identity、preset/persona/tool schema、wire renderer、Python依赖/worker版本、有效模型参数及tokenizer/计量版本。source SHA不可知时为null，不能借研究参考SHA；同字节不同安装根可按明确的逻辑身份规则规范化，但必须证明Loader解析到冻结字节。

同一个composition摘要用于prepare/dispatch/resume/离线回执；不能每层独立计算不同字段集合。新增裁决模块进入validator来源集合。源码与构建/runtime都冻结；只比package版本或lock不足以发现依赖JS被改。开发home/session/cache不是组成代码。

外层协议沿用总设计`c2p-dsh/1`；任务合同`WriterTaskContractV1`、领域结果`WriterTaskResultV1`、workflow/accounting/renderer/storage版本各显式记录，不用单一模糊version。字段不兼容升级拒绝旧任务；旧记录走具名reader，不原地改字节重新封印。

## 3. WriterTaskContractV1

| 字段组 | 内容与约束 |
|---|---|
| 定位 | execution/workflow/node/task/scope/epoch与content revision；固定输入任务key |
| 私有输入 | 完整WriterSectionInput/对应可重建引用，已完成Formalizer回执、冻结Narrative/manifest/plan；不只保存模型可见压缩视图 |
| 来源 | resolved artifact snapshot/read-set、每个不可变对象/成员digest和authority；之后不读漂移active代替冻结版本 |
| 请求 | 真实build_publication_writer_request，再经冻结DSH renderer投影；实际工具schema、TaskView、模型配置与精确计量 |
| 页合同 | author_surface/binding_contract/technical_bytes三个摘要；段落集合/顺序/scope和真实技术bytes；实际值必须重算 |
| 身份 | engine/target/intent/claims/profile/model/validator/composition、parser/schema/renderer/tokenizer/accounting版本 |
| 有限额度 | post-clamp输出cap、epoch请求/input/output/工具量/wall-clock上限；首版模型请求上限1 |
| 观察快照 | prepare时remaining budget等只读值，不是可扣减余额；dispatch必须lease内重查 |

Python用既有canonical serializer生成合同digest，TaskView由此派生；TS不得独立重拼作者/证据/formula/detail义务。实际DSH prompt包括terminal指令，与旧response_format不同：保留领域内容，明确记录协议差异。C01先定schema；C00交付自有Host私有prepare_projection(WriterInputRef, composition)，形成不可变WriterWireProjectionV1供C02计量/复核后冻结合同。这不是DSH已有API；通过公开SystemPrompt assemble/render和固定native文本组成获取投影，以实际pi-ai连接隔离假HTTP/SSE端验证最终wire。assemble、loop请求、adapter后wire分别记录，不能视作同一对象；首版明确拒绝未覆盖的文件/图片转换。

准备握手是领域输入冻结→Host无模型投影→Python检查计量/cap并冻结；clamp导致cap或材料变化时重编并重取投影，不沿用旧页，次数有界。I01只提供原语，真实prepare绑定由C02、dispatch由R03、resume由R04、receipt由A01验收。最终发送的材料/工具/模型选项/cap须与冻结投影一致，transport随机ID与无语义字段按显式白名单单独记录而不能吞掉prompt差异；seam只核验/reserve/放行，不改材料/cap。若公开seam无法证明实际投影对应，C00失败并阻断后续，不虚构dry-run/private API或放宽计量。

内容revision只因领域材料/计划/正文相关状态变化；prepare、claim、reserve等记账状态有各自序号，不令任务刚准备就自发stale。elapsed时间从持久epoch起点计算，重启不重置额度；时间回拨/过期按明确拒绝规则处理。

## 4. 结果、原始来源与成功层次

领域结果固定draft / research_required / blocked。H03优先验证object根下result.oneOf；若DSH子集不支持则采用等义明确outcome字段，并由Python完整模型交叉校验。保留extra-forbid/required/nullable/union约束，不删领域条件来迁就工具schema。

Host的OutputEnvelope至少绑定task/epoch/claim/fence、真实child/session/turn/step、tool-call ID、model request/attempt ID、schema/parser、stopReason、usage可信事实及输出来源。原始来源分开记录：

1. provider raw HTTP/SSE字节：只有真实捕获才有ref/digest；否则显式not_observed。
2. adapter观测的tool arguments delta流：保存原始顺序字节、完整性与call ID；这是argument来源，不能冒充完整HTTP raw。
3. normalized terminal arguments：允许adapter重新序列化，单独ref/digest；不能倒推原字节。
4. parsed领域对象及最终prose：分别digest，JSON pointer映射到允许角色lexical span。

所用adapter若拿不到满足authorship合同的完整arguments来源，H03/Gate-V必须阻断或实现公开可验证捕获；不能用closing message、重新JSON.stringify的hash或虚构finish_reason补证。解码转义可做表示恢复，补句/改qualifier/改公式属于内容修复，返回授权生成角色。

DSH terminal成功→可信落盘输出→Python local accepted→独立验证→正式产品状态是不同步骤。child释放前await Session持久flush并确认listener，再获record_output回执。崩溃时只从真实落盘来源恢复；来源不够保持unresolved。SDK ok或stopReason=completed本身不表示领域通过。

research_required只能携typed gap与lineage；首个Writer只waiting，WP5后由原owner排补证。pending_validation不调用隐藏PythonLLM，也不把verifier置空；独立验证完成之前不产生Verified。

## 5. worker RPC及幂等

C04采用UTF-8 JSONL上的固定JSON-RPC 2.0请求/响应；stdout只协议，日志stderr。首版配置上限1 MiB/帧、单读chunk最多64 KiB字节；大合同/结果用内核发行的不可变artifact句柄传递，超界typed拒绝而非截断。具体参数进入composition与协议goldens；若真实fixture超过，先分引用或显式版本化调整。

Python/TS双方拒绝重复JSON键、非有限数、未知字段/版本、越界整数；跨语言整数限安全范围或使用显式字符串ID。冻结Unicode、null/absent、enum/union、extra、路径和摘要goldens。私有Host channel绑定能力与run/task，不能只靠请求里自报execution_id授权；模型工具和日志不得泄漏该能力。

方法均为有界短操作，不在RPC里等模型或跑完整Agent。取消单次读取不销毁整个Host/worker生命周期；停止mutation需明确终态或provider可观察进程范围quiescence。仅done/父进程退出不足；SubprocessHandle.waitForExit(cleanupSignal)只有返回true才证明provider范围静止，false/抛错保留阻断。cleanupSignal使用独立有界清理期限，不复用已aborted的请求signal。

幂等key绑定method/execution/task/epoch、实际重算的result/semantic payload digest及validator digest。另有不可绕过的(task, epoch)唯一正式终态约束：换一个有效key仍不能提交不同结果；不同内容需要新的内核授权epoch/revision。先校验实际调用者能力及execution，再检查既有不可变回执；同内容重复返回原receipt，内容冲突拒绝。仅对新提交检查当前content revision/read-set，避免已成功但回包丢失的重试因后继revision错误拒绝。旧fence不能创建新副作用；取消/停止后仅允许规则明确的读取和确定性结算，不自动派模型。

## 6. 发送、预算与未知结果

R02在原账本增加版本化事实：reserve、adapter-attempt、dispatch-confirmed或send-outcome-unknown、proven-not-sent、usage、terminal、cancel、settlement。稳定事件ID重复幂等，关联/内容冲突拒绝；模型不能提交可信usage/dispatch事实。prepare余额不作为权威；lease内核read-set/fence/unknown/实际预算，持久reserve成功后才放行。

next()/adapter入口不是HTTP证据。无法观察transport送达时记录证据等级并保守unknown；失去usage不等于零花费。已发送的格式失败、unfinished、research_required和content失败保留epoch费用；排队取消、prepare/schema/pre-send拒绝不收content attempt。representation恢复不新增正文，不成为无限免费repair。

DSH无第二durable balance；所有main/child/verify/compaction/title请求受同一run/backend政策。unknown保留reservation和permit，并阻断整个resource group新发送，即使容量2尚有空slot也不能放行；TTL、Host消失、本地abort不自动释放。已落盘response未验收只用共用parser/assessor本地结算，不另起幽灵attempt。

## 7. 发布与流程恢复

沿原publication owner发布不可变generation成员与record，manifest绑定media/schema、read-set、task/epoch、正文/acceptance/authorship/原结果及validator来源；active以expected-active+持久fence最后切换。成员按media验证同次字节，index只投影同一manifest，固定路径只导出。g1后g2逐写点故障必须经真实reader检验，旧active永不被半成品覆盖。

LangGraph节点只prepare/outbox/interrupt/apply receipt；Host图外执行Agent。持久thread_id、content revision及task key保证图重放不重发。Research context由已有snapshot/immutable payload扩展恢复；result来自持久manifest，不读last_result。旧stage checkpoint只能按认证导入语义用，不能冒充中间节点checkpoint。

共享接口变更由LEAD登记影响任务和需重验的AT；不能在某个TS adapter局部改枚举/canonical算法绕过Python合同。初版没有提供的能力明确unsupported；实际版本升级重新过Gate-H。

[返回总执行入口](README.md)
