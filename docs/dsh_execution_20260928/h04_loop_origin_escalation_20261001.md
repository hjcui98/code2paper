# H04 派发来源裁决申请：公开 API 无法表达可信交接（H-R4）

> 窗口二 owner 提交，2026-10-01。绑定候选 `0.2.0-rc.1`（runtime `43490765…`）。
> 本文档请求 LEAD 对"本次调用来自实际 loop"的可表达性做接口裁决；在此之前 H04 派发来源保持 FAIL-CLOSED。
> 不修改 frozen runtime，不削弱门，不采用首次调用、微任务顺序、`awaiting-prepare` 状态、材料一致或公开 setter 作为来源凭据。

> **LEAD已裁决，当前执行§6。** 接受当前FAIL-CLOSED为安全停发检查点，不接受“H-R4完整关闭”或Gate-H通过。授权窗口二在新隔离候选开发最小runtime来源补丁；原43490765…树保留。§3方向认可，原样方案需修订，不能只清理公开llm.stream或公开origin store。

## 1. H-R4 实际调用链（本批 QA 探针复现，公开能力内成立）

前置：攻击者是可监听公开事件、使用公开 Host 服务（`agents`/`llm`）的扩展；不读私有 WeakMap、不伪造 claim、不直接 issue 授权、不改 runtime。

1. 合法 child 的 turn 进入 `dsh-agent-loop` `prepareRequest`：
   `dispatch.waterfall("agent/request", {turn, step, signal}, () => seedConfig)`。
2. 中间件的 `agent/request` listener（prepend）注册 ticket(agent, signal, `waterfall`)，返回
   `Promise.resolve(next()).finally(() => ticket → 'awaiting-prepare')`。
3. 攻击者以**更晚注册的 prepend listener** 成为最外层：其 listener 内 `await next()`（内部链完成，
   中间件 finally 已把 ticket 置 `awaiting-prepare`），其续延在瀑布 settle 之后、loop 的 prepareCall 之前运行。
4. 攻击者在该续延内调用公开 `llm.prepareCall(自有config, 同signal)`：中间件仅能以
   `state === 'awaiting-prepare'` 判定"这是 loop 的 prepareCall" → 认领武装 → 返回 claiming handle。
5. 攻击者用该 handle.stream 派发**自有材料**：reserve → dispatch → 授权 → adapter 进入 → settle，各一次；
   随后返回 config，loop 的 prepareCall 拿到普通 handle → 其派发无 claim → 被拒，合法 child 返回 error。
   与本批 QA `public-request-alias`/H-R4 结果一致（自有材料 R/D/S 各一次、合法 child error）。

**结论：`awaiting-prepare` 状态可被攻击者续延到达（窗口由最外层 listener 的返回时机控制），不能作为来源凭据。**

## 2. 逐一排除的公开凭据

| 凭据 | 失败方式 |
|---|---|
| signal 对象 | 公开事件载荷可取得并复制（QA 已实测） |
| request 对象同一性 | 同一对象可从公开 `llm/stream` 载荷取得并重入（H-R1） |
| 摘要/材料一致 | structuredClone 全量复制摘要不变；换材料变体同样被 H-R2 证明可计费 |
| provider/model | 攻击者自有材料任意指定 |
| 首个调用 / 微任务顺序 | 窗口由攻击者最外层 listener 的返回时机控制；指令明令禁止 |
| `awaiting-prepare` 状态 | §1 的 H-R4 链；指令明令禁止 |
| `agents.withInitiator` / `currentInitiator` | 公开 setter；文档明确 presence 不是授权 |
| config 对象上私有 Symbol 标记 | 攻击者作为最外层 listener `await next()` 可取得被标记对象并原样复用 |
| 会话 `request/header` 对照 | 派发时可被攻击者先观察到或补写；嵌套分发发生在合法 header 之后 |
| gated adapter 的 prepareCall | loop 与攻击者的 prepareCall 都经过它，无调用者身份 |

## 3. 最小接口差异（请求裁决的方案）

**方案（唯一提出）**：由 runtime 为"loop 自己的模型派发"提供私有来源标记，公开入口退出该标记。

1. `dsh-agent-loop`：在 step 内把派发表达式包进 runtime 私有的
   `AsyncLocalStorage`——`llmDispatchOrigin.run({ sessionId, signal, claimed: false }, () => preparedCall?.stream(request) ?? <loop 内部回落入口>)`。
2. `dsh-agent-loop`：NO_ADAPTER 回落改走 **loop 内部派发入口**（同一 `run` 内的闭包），
   不再调用公开 `llm.stream`；否则回落也会在公开入口退出标记后失去凭据。
3. `dsh-llm`：公开 `llm.stream(options)` 进入 waterfall 前以
   `llmDispatchOrigin.exit(() => streamWithRegistration(...))` 执行——**嵌套/公开调用永远看不到标记**。
4. 导出只读 `currentLlmDispatchOrigin()`（或等价 verifier）。
5. 中间件（owner 域）：accounting listener 同步体读取标记，作为唯一来源凭据；
   消费一次（`claimed = true`），嵌套/独立/延迟分发均无凭据或见已消费 → 具名拒绝。

**为什么sound**：标记由 runtime 私有 ALS 建立，只有 loop 的派发代码在其下运行；公开入口显式退出，攻击者的嵌套调用继承不到；`run` 的 store 对象私有，攻击者无法伪造或预消费。prepared 与 NO_ADAPTER 回落同被覆盖。

**成本**：dsh-agent-loop 一处包装 + 一个内部回落入口；dsh-llm 公开 `stream` 一次 `exit` 包装；一个导出。无语义变化，无新公开可写面。

**备选（若 LEAD 不接受 runtime 改动）**：接受 H04 来源门在该 runtime 上不可闭合，中间件维持 FAIL-CLOSED（现状），登记具名阻断；生产接线（R02）在获得该接口前不得开启受保护派发。

## 4. 当前候选状态（fail-closed，已验证）

- `request-accounting.ts`：prepareCall 不再武装、不再铸造任何 claiming closure；公开 `llm.stream` 对 owned ticket 的一切直连分发拒绝；accounting listener 对受保护会话的一切分发具名拒绝
  （诊断 `no loop preparation for this request signal`，chunk `dispatch_origin_unproven`）。
- cancellation 21 项：8 pass / 13 skip（原因=等待接口裁决）/ 0 fail。C0 为 fail-closed 控制；C9/C10/C13/C14/C14b 保留全部攻击拒绝与 fail-closed 断言。
- joint-child：同一真实绑定 child 上 seam/adapter/terminal 全关闭、flush 后新进程重建 `absent`。
- request-seam S2：合法 child 与冒充同样被拒（公开调用零 reserve/adapter）；S1 扇出测量、R-receipt、R-cap 不变。
- 五文件聚焦：37 pass / 13 skip / 0 fail；完整链见交付包。

## 5. 裁决请求

1. 认可/修订 §3 方案，并指定实施窗口（涉及 dsh-agent-loop 与 dsh-llm，属 frozen runtime 责任域）。
2. 或选择备选：登记 FAIL-CLOSED 为 0.2 阶段的正式状态，R02 接线阻塞项随附。
3. 裁决前窗口二不恢复任何时序/状态/材料类来源凭据。

## 6. LEAD接口裁决与完整续派（2026-10-01，当前有效）

### 6.1 当前状态与裁决

LEAD只读核对当前源码、实际安装runtime、staging和owner日志，没有修改实现或重跑产品验收。
当前源码9c671806…、build0c06c8f1…、stage6d1b6003…、outputs2a27b7b9…匹配；runtime26149项
与上批43490765…清单相同。owner完整链是71pass/0fail/13skip，B02是23passed，日志exit0。
合法child也被拒、联合恢复只有absent；这是安全停发，原正例/等待/取消/结算/联合AT未满足。
**H-R4记为“可利用路径已抑制、功能来源合同待实现”，保持CHANGES_REQUESTED；Gate-H/K未过。**
13skip不是通过，不把R02标成已启动后再延期补H04。791个Python源码/测试身份不变，保留
内核component及既有全量；窗口一只读准备已交付，不重复派调查或重跑4129。

**裁决：准许窗口二开发最小、隔离、可重建的runtime来源补丁候选，继续原第01份完整阶段。**
不选择永久保持全拒绝作为阶段交付。解除“不改runtime”的限制仅适用于下面新候选与窄源码域；
原0.2安装树、旧0.1.5、日常0.1.7均不修改，LEAD不实现代码。补丁仍须独立Gate-H验收。

### 6.2 对§3的必要修订

已读实际`dsh-agent-loop/lib/index.js`的step/prepareRequest和`dsh-llm/lib/index.js`：
公开prepared handle的stream直接调用streamWithRegistration，绕过公开llm.stream。
因此只在llm.stream执行ALS.exit不能隔离该公开入口。以下是实现合同，不是已验证能力：

1. **来源由runtime实际loop的内部派发建立。** prepared和NO_ADAPTER回落都从该可信入口进入，
   public prepareCall/返回handle仅表达适配器准备，不能取得loop来源。内部入口必须持runtime
   私有能力，不得作为Host服务、插件export、src通配导出或远程方法暴露可mint/run的入口。
   不用公开事件、caller字符串、signal、摘要、首调或状态来补足来源。
2. **隔离所有公开发起路径。** public llm.stream、public prepareCall返回handle.stream和其他
   实际公开等价入口均不可继承外层loop来源；覆盖最外层prepend的await next、嵌套同request、
   prepareCall新handle、预先持有handle、排入微任务/nextTick/定时器及销毁后的延迟重放。
   若增加loop内部prepared入口，保留原registration/config/单次dispatch检查，不从公共句柄
   上可偷取的Symbol字段选择“内部模式”。
3. **只读核验不暴露store。** 不导出ALS实例、run/enterWith、可变claimed/token/store，也不
   给扩展一个可预消费合法票据的公共consume接口。只读查询返回不可变事实或等价核验结果；
   一次性状态留在runtime私有域/受信消费者内，绑定当前实际派发实例与真实request。
   观察者拿到相同snapshot/引用不能铸造、复位、预消费或把新裸请求认证为loop。
4. **实际执行边界可证明。** 当前waterfall同步进入，但middleware可以延迟next、包装惰性
   AsyncIterable；不能只用ALS.run包“创建iterator”就假定稍后的next/return/throw有来源。
   核验在真实admission处成立，接续/迭代/清理只延续本次派发，不重铸凭据。退出后拒绝
   重放；合法A/B、等待期取消/fence与未知发送守卫继续成立，不引入全局requestDepth。
5. **保留域权威。** 来源证明仅解决loop调用来源，不代替Host绑定、完整摘要、cap、reserve/
   dispatch回执和Python余额/恢复。新增接口缺失、版本或模块实例不一致时明确拒绝，不能
   回到旧时序武装；bridge只消费明示接口，不import runtime私有helper或替换全局loop factory。

ALS可作为私有承载方式；批准的是以上行为合同，没有批准§3原样实现的soundness声明。

### 6.3 候选、源码与环境边界

- 原候选`.dsh-dev/candidates/0.2.0-rc.1/`冻结保留，43490765…是未改runtime的基树身份。
- 拟新增候选`.dsh-dev/candidates/0.2.0-rc.1+loop-origin.1/`；这是本地patch身份，非官方发行。
  patched runtime必须重算完整树，不能继续报43490765…；base identity与patch identity分别记录。
- 源码补丁/可重建脚本/类型与接口差分/证据归
  `integrations/dsh/dev/runtime-0.2.0-rc.1/loop-origin/`（拟新增）。独立源码工作目录可使用
  `.dsh-dev/sources/loop-origin-020/`（拟新增），先找现有只读源码，绑定实际核验的固定commit/锁。
  原monorepo责任域为`packages/core/agent-loop`、`packages/llm/llm`及必需的私有来源模块。
  不直接改npm树当源码，不改已有DSH源码对照；补丁影响超出来源/必需构建类型时报告真实差异。
- window2单写runtime源码补丁、B02 launcher、TS、peer、build、stage与新候选。新root独立
  home/workspace/run/manifest/inventory/receipt/worker，无共享可写inode，不复制旧home/session。
- 候选ID与上游版本须严格区分。现select_candidate把ID直接赋给VERSION；window2在原launcher
  增加明确manifest合同：candidate_id=`0.2.0-rc.1+loop-origin.1`，upstream_dsh_version=
  `0.2.0-rc.1`，source_kind=`local-patched`，必需base/patch/build/runtime身份。
  保留原未补丁候选校验、env/root/flag不一致拒绝、断网和只读runtime；不改package.version
  假装满足选择，不把版本校验变成接受任意manifest。toolchain每子命令传同一候选。
- runtime/source/patch/构建/安装变动的实际字节均绑定；新receipt证明实际Loader/peer解析到
  新字节、上游基树未动及保护环境无共享写入。shared peer仍只能由window2独占切换。

新root和manifest/launcher合同落地后才使用：

```bash
cd '/home/cuihengjia/agent/Code2Paper copy'
export C2P_DSH_CANDIDATE='0.2.0-rc.1+loop-origin.1'
export C2P_DSH_DEV_ROOT="$PWD/.dsh-dev/candidates/$C2P_DSH_CANDIDATE"
```

本仓库仍在`codex/agentic-p4-benchmark-cutover`/`d48b4e4b`的dirty树，不切分支/reset/clean/
commit/merge/push，不动Python内核/validator，不授权live、日常升级、发布或默认切换。

### 6.4 一次完整阶段任务与交付终点

窗口二直接连续：源码/可重建patch与runtime接口→新候选严格选择/隔离→Host来源消费→
原反例及合法正例→恢复全部13skip与曾改成“合法也拒”的S2/C9等原正例→同child完整恢复→
新版H01/H02/B02复验→一次完整稳定check:compat/B02/doctor→冻结身份与写权释放。
不逐函数/逐测试等审批；实际公开接口不能兑现§6.2时一次给具体调用链/差异，不能再猜时序。

必须保留缺来源fail-closed负控，同时恢复原成功合同：合法prepared/fallback/A/B恰各R/D/S一次，
公开调用零reserve/adapter；准备/reserve/dispatch等待、abort/fence/漂移/cap、usage/return/
异常与unknown均真实运行，不遗留“等裁决”skip。真实同child完成reserve→dispatch→adapter→
terminal→settle→flush→新进程按版本重建committed，absent只作为负控。适当运行受影响
runtime原测试和Code2Paper身份回归；不重跑不变Python全量。

统一交真实公开API/types、原ABI差分、base与patched树、source/patch/lock/build/stage/outputs、
Loader/peer解析位置、完整AT→节点/日志、逐命令真实exit/首次失败/skip、未测项和写权释放。
`_020`正文已写FAIL-CLOSED，但当前顶部身份表仍是c2da/599a/32fa/7731；必须纠正实际冻结
身份，保留旧版本历史，不能只改正文后宣称全包同步。新本地候选兼容清单单独版本化。

QA只在完整冻结候选后按需启动；正式Gate-H只批准该明确本地patch候选，不借它批准原npm树。
component保持，正式Gate-K等待目标Gate-H；随后仍按原第03份整包，再第04份串行mock。
原8份文档、49单元及AT/依赖不减少，没有新增R02假实现或平行账本。

本轮为接口/源码/owner日志只读裁决，未启动产品测试或新QA冻结。owner已释放写权，window2
立即接回上述完整阶段；window1保管已验内核，没有新返修或重复准备任务。
