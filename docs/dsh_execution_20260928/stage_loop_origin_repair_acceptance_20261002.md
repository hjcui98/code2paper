# loop-origin.1 返修差分裁决与完整接续（2026-10-02）

> LEAD独立于窗口二实现者，只运行独立离线探针、读取身份与原日志并登记裁决；没有修改产品代码、原测试、runtime、peer、build/stage或Python validator。
> 当前执行入口为 [README §3.12](README.md)，原8份执行文档/49单元、AT与正式依赖不变。本记录补充本批事实与接续，不另建执行计划。

## 1. 当前状态与本批裁决

**Gate-H仍为CHANGES_REQUESTED；正式Gate-K未放行，第03/04份尚未实施。**

窗口二的返修有真实进展：普通公开调用、公共NO_ADAPTER语义和旧manifest读取均已独立通过；固定源码、类型与源码构建产物已交付。LO-4的私有消费合同仍未闭合：公开`admitLoopDispatchOrigin()`仍然修改一次性状态，独立公开观察者可以提前消费，阻断合法child。源码构建候选出现同一反例，不能以改导出名称、称为有界oracle或原86项通过代替修复。

| 对象 | 当前事实 |
|---|---|
| 原第01份 | 窗口二连续返修；B02/H01–H04仍in_progress，未自行登记done |
| 原第02份 | K01–K04既有独立component PASS保留；正式Gate-K等待实际Gate-H |
| 实现者完整链 | 交付候选86 pass/0 fail/0 skip，B02目录24 passed，doctor报告exit0；本批核对原日志/身份，没有宣称独立重跑完整链 |
| 本批独立探针 | 普通三入口及合法回落2/2；公开复制protected request1/1；公开admission在交付和源码构建候选上各1个合法正例通过、1个负例失败 |
| 本批旧manifest | default0.1.5、原0.2及补丁候选三个实际read_manifest均通过 |
| 内核保管 | 原791条Python源码/测试与九份原内核运行文件摘要不变，没有重跑4129项 |
| 下一阶段 | Gate-H与正式Gate-K满足后，第03份整包；Gate-C后第04份整包；live、全文事务、主图迁移、默认切换后置 |

## 2. 给新接手者的共同环境与文档入口

仓库：`/home/cuihengjia/agent/Code2Paper copy`。分支：`codex/agentic-p4-benchmark-cutover`。
本批实测HEAD：`d48b4e4b22c94c82b45d2179ba452d72b164102d`，工作树大量dirty改动就是接手基线。
Python：`/home/cuihengjia/miniconda3/bin/python`，3.13.9；Node：v25.8.2。
源构建工作目录：`.dsh-dev/sources/loop-origin-020/`，上游固定tag `dsh-v0.2.0-rc.1`、commit `4878cdabd87d4041bdaff61d04c966883b9fd07a`。

| 环境 | 用途与边界 |
|---|---|
| `.dsh-dev/candidates/0.2.0-rc.1+loop-origin.1/` | 当前交付/共享peer目标；本地补丁候选，包版本仍为上游0.2.0-rc.1 |
| `.dsh-dev/candidates/0.2.0-rc.1+loop-origin.1-built/` | 源码构建等价验证候选；本批裸JS字节对应已核对，不是共享peer目标 |
| `.dsh-dev/candidates/0.2.0-rc.1/` | 原未补丁基树，43490765…；保持原字节，不重封stage |
| `.dsh-dev/runtime` | 历史0.1.5-rc.3，7e8f199b…；只读对照 |
| 用户日常0.1.7-rc.2 | 保护环境，不升级、不切换、不共享可写inode；历史安装前hash缺失不追补 |

先读 [仓库入口](../README.md)，再读 [执行入口](README.md)、[台账](task_board.json)、[共享接口](interfaces.md)、[验证文档§15](verification.md)。
窗口二重读 [第01份](01_baseline_and_dsh_compatibility.md)、[接口裁决§6](h04_loop_origin_escalation_20261001.md)、本批§3–5。
窗口一使用 [第02份](02_kernel_publication_and_request_guards.md)、[内核证据§10](kernel_stage_evidence.md)，后续按 [第03份](03_writer_contract_and_worker.md) 和 [第04份](04_serial_writer_integration.md)。
`migration_0.2.0-rc.1_gaps.md`包含历史；当前新候选以`loop-origin/{interface-diff.md,evidence.md}`、`h02_interface_freeze_020.md`和台账最新裁决核对，不倒退到46/54或FAIL-CLOSED的旧检查点。

所有人保留现有改动；没有reset/clean/换分支/commit/merge/push/live、日常升级或默认切换授权。LEAD只负责协调、独立裁决和文档；两位原owner实现，不逐测试重新派工。QA在完整冻结包就绪后按需启动，当前不常驻。

## 3. 独立反例、通过范围与身份

### 3.1 LO-4-PRECONSUME：公开oracle仍能消费私有状态

探针只使用`node:async_hooks.createHook`、包根公开的`peekLoopDispatchOrigin`和`admitLoopDispatchOrigin`。
不读取ALS实例、不修改runtime、不调用Host私有authorization、不替换loop factory。

native `AsyncLocalStorage.run(..., async () => …)`创建Promise时，公开async hook同步执行；此时snapshot的`dispatched=false`。观察者取公开snapshot里的真实request，调用公开`admitLoopDispatchOrigin(request)`得到`admitted`并置位。native随后自己的admission被拒，合法child返回error。

| 对照 | child结果 | reserve / dispatch / settle / adapter |
|---|---|---|
| 交付候选，未开启观察者 | completed | 1 / 1 / 1 / 1 |
| 交付候选，公开观察者 | error；观察者一次admitted | 0 / 0 / 0 / 0 |
| 源码构建候选，未开启观察者 | completed | 1 / 1 / 1 / 1 |
| 源码构建候选，公开观察者 | error；观察者一次admitted | 0 / 0 / 0 / 0 |

两条负例实际inner exit=1，合法对照通过；不是等待超时、源码验证夹具错误或全拒绝正例。
本批证明的是**公开预消费与合法派发被阻断**；不把它扩写为已经证明裸模型请求成功或预算被盗。
`interface-diff.md`中“同步admission窗口没有扩展执行、观察者无法预消费”的soundness声明不成立。
这违反既有§6.2-3，继续修原H04/LO-4，不新增产品任务、不需要重新申请普通返修许可。

### 3.2 本批已通过的实际行为

- LO-1：真实protected listener内普通`llm.stream`、循环前取得的prepared handle、当场prepareCall handle三入口均成功；另有loop外成功对照，普通adapter合计4次，合法child completed且四项各1。
- LO-2：公开prepareCall遇真实NO_ADAPTER原样抛出、无handle；native单次回落合法completed且四项各1。
- LO-3：default0.1.5、原0.2和补丁候选通过各自真实read_manifest；原两棵树未改。
- 公开protected request的结构复制：具名dispatch_origin_unproven，未额外reserve/adapter；合法child四项各1。这条通过，不把尚未实测的构造期旁路宣称为漏洞。
- 源码HEAD/四文件窄改实际可读；源码构建的agent-loop/llm两份JS分别与`-built`候选对应JS逐字节一致，两套候选都实跑同一公开预消费探针。类型/源码交付进展保留，不能外推完整私有ABI已验收。

### 3.3 当前完整身份

| 对象 | SHA-256 |
|---|---|
| 原0.2基树 | `43490765da460c4300cd7ad8ec75dbc5d5e6dbda93b74e37466c6709c1ab359c` |
| 当前交付runtime树 | `5f340b3aaa00baead17242bfdd947a7de40fe93319f79493534bd91b2788b3b5` |
| 源码构建候选runtime树 | `eb4625a68da0e4de5f12b5d594cfd1a423e7ff61459c6836d57c3b91dba15e12` |
| request-accounting.ts | `085523002bb3d38784f3306f95ccc4561af6e20b1ae339d9586b5e5c4c0e8f11` |
| runtime补丁脚本 | `9c98b72043fddfa2053289ddd5b647ba1aa30cc55c6d2bbcb91b611d81501cff` |
| runtime源码差分 | `80ffbdd8539879f5f1b44780586e50386ed4ee8aaec1be2ace87b1262f38ff78` |
| build receipt | `bec54f926dff0fa19bbfdb11d164e793306d592c2e9fbaf28118fa3546cdc398` |
| staging tree | `3981269e8009c134363070cd1e4f77b51dfab5ca367a5062e0a34cd4bb1c1bb5` |
| build outputs | `8be3cd0a53c00983fd172643374688d8effdbd3f149d4c50fafa1e8f20c48569` |

## 4. 立即派给窗口二：原第01份完整返修到冻结交付

**本批QA冻结已明确解除，直接接回原B02/H01–H04、窄来源源码、TS、peer、工具链、build/stage与本地补丁候选的唯一写权。** 原§6授权继续有效，无需逐缺陷、逐测试申请。

```bash
cd '/home/cuihengjia/agent/Code2Paper copy'
export C2P_DSH_CANDIDATE='0.2.0-rc.1+loop-origin.1'
export C2P_DSH_DEV_ROOT="$PWD/.dsh-dev/candidates/$C2P_DSH_CANDIDATE"
git branch --show-current
git rev-parse HEAD
```

按以下完整顺序连续完成，内部步骤可据实际依赖调整：

1. **保存受测证据和当前身份。** 将现有候选/owner运行证据封存到候选根之外的新鲜`.dsh-dev/run/w2-loop-origin-private-<fresh>/`。本批独立QA权威根在`.dsh-dev/run/qa-loop-origin-repair-0yrz6nyl/`，不能删除或覆盖。runtime需要重建时不能顺带清空run/home历史。Node夹具仍使用launcher准许的可写run目录；外层逐命令日志/退出码及完整候选证据封存到稳定根。
2. **从固定源码兑现私有派发能力。** prepared与内部NO_ADAPTER回落均走可信runtime内部派发入口；一次性admission/consume只在runtime私有域或受信native消费者内可达。包根及实际公开通配导出不得留下能消费、铸造或复位来源的oracle/helper。公共只读查询不能改变派发状态；同一snapshot/request引用不能抢占合法派发。不得只给`admit`换名、包装一个有界接口、提前置位或改用首调/微任务/状态/signal/摘要授权。
3. **一起完成所有公开入口隔离。** `llm.stream`、公开prepareCall新handle、预持handle及等价入口在进入任何公开hook前清空外层来源；构造、同步listener和惰性next/return/throw都覆盖。内部回落不借“公开stream碰巧是首个同request调用”取得权限。保留registration/config/单次dispatch与原NO_ADAPTER语义、普通公开provider成功、protected复制/同引用/延迟重放零reserve/adapter。
4. **将真实反例纳入原owner回归。** 本批两份public-admission探针有合法child正对照；原C13/C14/C14b、H-R4、公开async hook预消费、prepared/fallback、A/B兄弟、公开普通三入口一并覆盖。不得仅将被删除导出的旧探针变成import error：删除公共mutator后证明剩余公开面无法预消费，同时合法child仍各一次。Host只消费明示只读核验，ABI缺失/版本/模块实例不一致fail-closed，领域账本仍由Python负责。
5. **连续收口原全部AT与联合接线。** 等待期abort/fence/材料漂移、cap、usage缺失、同步/异步return异常及250ms截止、未知发送/unfinished结算，H03严格V3/V4/来源/完整性/flush失败/部分落盘、新进程恢复均保持。一个真实绑定child走reserve→dispatch→adapter→terminal→settle→flush→新进程committed恢复；普通API正例和公开来源反例不能分在互不相干的伪夹具里。原H01/H02生命周期、组成关闭/白名单/断网与B02隔离保护按影响复验。
6. **从源码与交付双侧形成同一稳定候选。** 在固定commit/lock上构建native源码并保留真实构建日志/退出码；新types与Host消费同步。只重建本地补丁候选，基树/旧默认/日常不动；源码构建验证候选也重放新反例和原合法链，实际Loader/module/peer路径与字节入身份，不靠口头“行为等价”。仅在依赖确有意义时串行切换shared peer，唯一写者始终是你。
7. **一次最终完整验证与提交。** 目标check:compat、原B02目录、doctor--evidence；必测不得skip、零测试不得当通过。保留首次失败、逐命令实际argv/cwd/runner/log/.exit；稳定后只做一次完整收口，聚焦随修复推进。同步`_020`、source/interface差分、兼容清单、AT→真实节点/断言、base/source/lock/patch/types/runtime/build/stage/outputs/loader统一身份及未测项，再释放全部责任域写权。LEAD/独立QA整包差分验收，不以86/N项单独申报Gate-H。

最终验证沿用实际入口，不裸跑Node或vitest：

```bash
npm --prefix integrations/dsh run check:compat
/home/cuihengjia/miniconda3/bin/python -m pytest -q integrations/dsh/dev/tests
/home/cuihengjia/miniconda3/bin/python scripts/dsh_dev.py --candidate "$C2P_DSH_CANDIDATE" doctor --evidence
git diff --check
```

具体source包命令按本批已成立的锁与构建方法运行并记录：`pnpm install --frozen-lockfile`、两包`tsc -b`、`pnpm run build:lib:host`。不要用新版源码同时重封旧环境。

本批交付表还需一次校正：原日志实际11文件含`dev/toolchain/sandbox.test.ts`的2项、`staging.test.ts`的4项，不存在所列`toolchain.test.ts`；完整86日志真实。manifest的`touched`仍列2个JS，实际补丁域已包括2个types，要按实际差分列齐。核表与补齐实际命令退出码随整包完成，不为表格单独重跑已通过测试。

## 5. 证据保管缺口必须随本包处置

上批引用的`.../run/qa-loop-origin-awkji3_e/`与`.../run/w2-lo-final/`在本会话当前仓库路径均不存在；稳定的R2/内核独立根仍可读。**具体移除方式和时间未核实**，本批不替原报告补造日志、退出码或closing。原报告/台账历史记录保留，但附注其raw路径当前不可读，不能继续称全部历史原始证据可审计。

先查本人已有封存副本；找到则复制原字节到稳定仓库根、登记来源/原hash及路径映射。没有原副本就如实登记不可用，未来新鲜完整候选补齐当前必需证明，不把新测结果冒充历史结果。后续候选重建只替换受控runtime/build/stage，不删除独立QA和owner原日志。

## 6. 立即派给窗口一：保管已验内核，不重复施工

原第02份内核component已通过，无新内核返修。保持Python候选、validator清单、账本/发布/注册/索引原owner及4129/3既有live skip/12 subtests证据。791源码/测试与九份本批核对的原运行文件不变。
复用调查已经交付，不重复调查、不重跑全量、不改publication_method_writer或创建C/R模块。保持接手记录可用；现在只有窗口二有必要施工，不为凑两窗口提前开放下一阶段。

收到LEAD基于完整独立证据的Gate-H及正式Gate-K放行后，直接接第03份整阶段，不再等逐任务派工。你独占所有Python协议/facade/worker与`authoring_execution_identity.py`/`VALIDATOR_BUNDLE_SOURCES`；窗口二需要的Python字段由你在本阶段串行合入，双方不同时写共享文件。

## 7. 两门满足后启用原第03份整阶段：I01→C01→C00→C02→C03→C04

以下是已排队的完整任务，**本批不提前授权实现**。激活条件是实际Gate-H与正式Gate-K，不是owner释放或测试数达标。

| 单元 | 实际责任 | 连续交付与不变合同 |
|---|---|---|
| I01 | 窗口一；窗口二交实际runtime/loader/build字节清单 | 同一composition构建/严格校验原语，含真实JS/DSH树/Node/锁/preset/persona/schema/renderer；校验symlink解析目标，不扫描可变home/cache。新裁决文件实际落地后才进原validator清单 |
| C01 | 窗口一Python合同/schema/goldens；窗口二TS wire消费/测试 | 唯一WriterTaskContract、派生TaskView、raw结果schema；Unicode/null/union/extra/整数范围两侧一致。canonical digest仍由Python计算，prepare剩余额度只是快照 |
| C00 | 窗口二renderer及TS测试；Pythonprotocol仅窗口一写 | 自有prepare_projection接口，真实SystemPrompt assemble/render；真实adapter接隔离假HTTP/SSE证明首请求与最终wire。准备无模型请求、不记send/content attempt；未覆盖图片/文件/转换明确拒绝 |
| C02 | 窗口一 | 从原structured_caller抽纯解析/decode/splice/归一化路径；旧caller、已落盘响应本地结算、新facade共用。消费C00实际投影计量/clamp，有界重投影后冻结；网络/Python LLM出口哨兵下可运行 |
| C03 | 窗口一，窗口二供真实绑定/raw terminal fixture | ingest只认真实Host与原terminal来源，走同一parser/assessor/局部绑定/composer与publication owner；正文/acceptance/authorship同代提交。未知语义验证pending，不把局部接受写成全文complete/verified/publication_ready |
| C04 | 窗口一；窗口二接跨语言真实worker fixture | 有界JSONL短RPC、固定method/路径句柄、stdout协议与stderr日志；授权先于幂等缓存。prepare/record_output/ingest是Host私有，模型只窄读/terminal；R01/R02未实现不得伪造claim/reserve成功 |

窗口一真实复用入口已经核对：`build_publication_writer_request`是唯一request builder；C02从`section_writer.structured_caller`抽decode/公式splice/parser/assessor，并修接`publication_method_writer._settle_recorded_writer_attempt`当前缺失的decode/splice路径。旧caller、本地结算、新facade不能另建三套解析。
局部提交消费已验publication/registry/index入口，receipt仍为派生；不误用单文件publish_artifact_transaction当多成员一代事务。

内部依赖按有意义的本地合同衔接：I01/C01先交稳定schema及goldens，再C00，之后C02/C03/C04。阶段内普通问题由两位owner连续修；缺跨语言合同才集中协调，不逐测试请求开工。原正式depends_on、AT-I01/AT-C00–C04和Gate-C全部保留，只有真实worker无模型prepare/ingest联合包就绪才独立验收。

## 8. Gate-C后启用原第04份完整串行闭环

窗口一负责Python R01/R02、R04恢复原owner与A01真实准入回执；窗口二负责R03 Host/kernel-client/workflow-driver/execution-policy、R04 TS侧、V02操作入口/唯一buildstage；V01联合验证由两位按语言/文件边界分担。共享Python协议与validator仍只由窗口一写。

连续实现顺序：R01→R02→R03→R04→V01→A01→V02。原Gate-R裁决R01–R04，原Gate-V裁决V01/A01/V02及真实接线，正式AT与依赖不减少。

- R01：持久task/outbox/claim、fence和单run/后端租约；task_store只存生命周期/引用，不存第二本可扣余额。
- R02：把真实reserve/adapter-attempt/dispatch/not-sent/usage/terminal/cancel/unknown接到Python原账本/reducer及真实worker RPC。lease内重读预算/read-set/fence/unknown；零预算/账本失败零发送，unknown不退款、不盲重发。
- R03：真实DSH child + 真实Python worker，Host仅RPC/hook adapter，不补领域内容；dispatch前核实际组成/config/generation，未绑定/旧claim/第二请求拒绝。已有request-accounting继续扩原owner，不从零造平行实现。
- R04：reserve前后、dispatch后、terminal后、record_output后、commit后真实进程退出及新进程恢复；落盘响应只本地结算，回包丢失同receipt；有界清理截止不等于底层静止，无法证明停止保留unknown。
- V01：一个run、串行、一个Writer、一个受控mock请求完整走prepare→outbox→claim/bind→reserve→dispatch→terminal/flush→record_output→ingest/局部commit→真实receipt读取/新进程恢复。
- A01：修原CLI“单pytest节点却默认四组label”缺口，覆盖从实际Python+Node argv/cwd/runner/退出码/机器报告派生；未启动、失败、零测试、必测skip、伪填label或身份漂移不能准入。
- V02：显式opt-in入口，parallel=false；true返回unsupported；retry/title/compaction/recursive/content repair关闭，默认产品入口保持原驱动。

Gate-V之后仅形成可单独申请L01的离线候选。尚无live授权，不访问真实8006模型做免费probe；全文F02、完整LangGraph迁移、并发调度、质量验收与默认切换按后续文档/门推进。

## 9. 独立QA证据、退出码与明确释放

权威稳定证据根：`.dsh-dev/run/qa-loop-origin-repair-0yrz6nyl/`；Node临时输出在各自候选允许的run子根。
原始输出只脱敏临时本地Web token。所有runner保存实际inner `.exit`与argv；外层Python wrapper退出0不冒充Node退出0。

| 实际命令/节点 | 真退出码 | 证据 |
|---|---|---|
| public-admission，交付候选 | 1 | 1合法通过/1预消费失败；public-admission.{command.json,log,exit,result.json} |
| public-construction，交付候选 | 0 | protected结构复制拒绝、合法child完成；public-construction.* |
| ordinary-and-fallback，纠正后 | 0 | 2通过；ordinary-and-fallback.* |
| public-admission，源码构建候选，纠正后 | 1 | 同一1通过/1失败；built-/public-admission.* |
| 三版本实际read_manifest | 0 | manifest-compatibility.json/.exit |
| closing读集/宿主进程 | 0/0 | closing_input_check.json、closing_process_check.json |

首轮ordinary夹具未使用resolved maxTokens而触发原INVALID_PREPARED_CALL、built夹具使用交付根导致EROFS、manifest报告helper字段错误均保留first-attempt/bootstrap记录并纠正，未计产品缺陷。旧QA路径缺失的bootstrap亦保留，未伪造旧探针；当前探针用稳定R2真实fixture生成。

LEAD于**2026-10-02T00:02:16.056112+08:00**明确释放本批实际读集：1023项输入的字节/mtime/inode/size不变，四棵runtime完整inventory和peer不变；宿主pid namespace扫描1754个进程，相关QA/候选CLI/仓库pytest/launcher为0，不可读为0；全部本批命令已返回，无pending。
精确清单：inputs_before.json/inputs_after.json；机器核对：closing_input_check.json；释放：closing_release.json。
窗口二直接接回§4完整写权，窗口一保持已验候选；后续LEAD文档/台账修改发生在释放后，不倒称是未变受测输入。下一完整冻结候选再触发独立差分验收，无常驻QA。
