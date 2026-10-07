# H02 接口冻结 · 0.2.0-rc.1+loop-origin.1（2026-10-03）

**2026-10-03 18:03 独立冻结：Gate-H PASS。** 本记录的当前接受身份由[独立验收](stage_four_group_repair_acceptance_20261003.md) §§1–3证明；未参与该批实现的reviewer在读集释放后登记。公开接口正文保持已经通过的93节点及来源/生命周期合同。

| 当前接受对象 | SHA-256 |
|---|---|
| delivery runtime | `671daa1a7a06728d69a4bdec6da3d33a3616c4e788f63579ed07f3ae81e0e16c` |
| delivery staged build receipt | `b6d57b715301ca503be7afa8eec3339cb734545f9edfcff17c31e977b59b6c86` |
| delivery staging | `30f18c5f31ed58a302c22d1996c699b45d2ab565325a57f92b1e8e9d50bfad98` |
| source patch | `87941d847abb581abe65a924773b980b702b95f03cda4a23831bba9cce3bb46b` |

两侧runtime和三份类型声明保持，源码仅修模块头说明；构建脚本改变后新回执/staging成组核验。当前API为frozen peek、对象同一性能力门控admit、clear-only runner及模块私有派发；没有公开take/entry-ack。source-built范围仅为源码等价，不声称该侧B02/doctor。

## 历史：第九轮接口候选

以下旧构建/source patch哈希和“尚未冻结”状态仅描述第九轮快照；当前身份及裁决以上方冻结记录为准。旧公开接口清单和合同在未被后续明确修订时继续适用。

> 2026-10-02 22:10 Gate-H 审查见 [2026-10-02 22:10 静态入口审查报告](stage_static_entry_gate_h_review_20261002.md)。
> 当前返修执行依据与逐项对应见 [README.md §3.15](README.md#315-当前模块级派发候选-gate-h-独立审查与原第-01-份整包续派2026-10-02-2210)。
> 实际交付树为 `671daa1a…`、源码构建树 `3076d2fc…`；
> GHS-1（受信派发身份不能被公开参数声明）、GHS-2（注册表生命周期跟随 deployment 销毁注销）、
> GHS-3（types 来源与 independent tsc 逐字节对齐）、GHS-4（-built 范围收窄为源码等价证据，不声称 B02/doctor）全部闭环。
> 全套测试 93/93 pass（0 skip, 0 fail），B02 26 passed，doctor exit 0。
> 本文尚未独立冻结，Gate-H 等待独立 QA 复核。旧轮次保留历史记录。

> 窗口二 owner 提交的版本化接口候选。LEAD / 独立 QA 尚未冻结，本文不登记 Gate-H PASS 或任务 done。
> 绑定候选 `0.2.0-rc.1`，runtime 树 `43490765da460c4300cd7ad8ec75dbc5d5e6dbda93b74e37466c6709c1ab359c`。
> 旧接口记录保持原字节。
>
> **当前生效候选为 [`0.2.0-rc.1+loop-origin.1`](../../integrations/dsh/compatibility.0.2.0-rc.1+loop-origin.1.json)**
> （[接口裁决 §6](h04_loop_origin_escalation_20261001.md) 授权的 runtime 私有派发来源补丁；
> 身份与差分见
> [loop-origin evidence](../../integrations/dsh/dev/runtime-0.2.0-rc.1/loop-origin/evidence.md) 与
> [interface-diff](../../integrations/dsh/dev/runtime-0.2.0-rc.1/loop-origin/interface-diff.md)）。

## 身份（loop-origin.1 本轮实测；base 值保留在括号内供对照）

| 对象 | SHA-256（loop-origin.1） | base 0.2.0-rc.1 |
|---|---|---|
| `index.ts` | `d322f53c707bed1bfa7ad4b86fb59fec153dc8f8f1267abee69d31f2271c2f2a` | 同 |
| `task-tools.ts` | `0ed976fe58e527e1101cc94f4124f18460e65b0fcf4030eed78cd839665a37b9` | 同 |
| `session-binding.ts` | `404f7984d01b51073a6f8f5941f56c9f594161be563a215f09b4ff2403348952` | 同 |
| `role-dispatch.ts` | `06c7376ef589530def2e32205387fe7ceb8816efd28c6a85007dd05eba6b2e07` | 同 |
| `request-contract.ts` | `5ad7a07ee1b895af01ab6098b387e2c163b1ad7348dab3420dce7cf05557ccc3` | 同 |
| `request-accounting.ts` | `efaa899ce0950a317ea0ab90d6581ea9811755980b1c9538c3048242a4ee0453` | `c2da50e24aa6fa130faec9cdcc51c192016350669ac9b6724784161810de594b` |
| `terminal-result.ts` | `5ef6174659140fc1b1098e01456223a296296796dfdfef52daa12133ea918ecb` | 同 |
| build receipt | `ea004d4592ce67bdeb26017eb4556e3f6fb601f375b2f7b8f3d32b9af33c4e89` | `599a8d79732753e0bdfc81826b15416f2b0c05b78aa700b3d714f644eb4cdbd0` |
| staging tree | `60acfbb2ec14fedca2880eb6a40b035ccb4df15851b175eb09a6741f9b1bb304` | `32fad7202183511b9311c13dc753d718be895d6f193281731963784ba57f4bc3` |
| runtime 树（patched） | `671daa1a7a06728d69a4bdec6da3d33a3616c4e788f63579ed07f3ae81e0e16c` | `43490765da460c4300cd7ad8ec75dbc5d5e6dbda93b74e37466c6709c1ab359c` |
| 补丁脚本 | `b36b887fc71e90de84080897169f79bddf370793a293ca1e54c03fbcb02c8e75` | — |
| 源码补丁（commit `4878cdabd8…` = tag `dsh-v0.2.0-rc.1`） | `0db693e794feea78f8087198078df04d41614804898aec329cf5628a45987512` | — |

构建输出摘要 `9c00688b090ab3bb744ba83975e5ab447fe75fd61798906d15ba13fa4e750e95`
（base 候选旧值 `7731232ff45651b54eef4f67ea5490347d41cb306c0dd763b3fe9d06008aa3f2`）。
manifest 分离记录：`dsh_version=0.2.0-rc.1+loop-origin.1`、`upstream_dsh_version=0.2.0-rc.1`、
`source_kind=local-patched`；runtime 内 package 版本保持上游 `0.2.0-rc.1`。

## 完整公开导出（消费者按这些名字接入）

`index.ts`（bundle 入口， Cordis 插件行）：

- `name = 'code2paper-bridge'`、`inject = ['agentPresets']`、`Config`（zod）、`BridgeConfig`、`SessionLedger`
- `Code2PaperBridge extends Service`：`mountPreset(agentCtx, presetId?)`、`joinChild(agentCtx, parentCtx)`
- `apply(ctx, config)`：发布宿主面 bridge
- `mountCode2PaperPreset(caller, agentCtx, presetId?)`：root 组成；必须在 `agents.create({ setup })` 内 await
- `applyChildComposition(caller, agentCtx, parentCtx)`：child 加入父代同代 standing 组成；同步、无文件读取

`session-binding.ts`：`SessionBindings`（`claim`/`bind`/`require`/`requireCurrent`/`assertTrusted`/`currentFence`/`resolve`/`release`/`dispose`）、`BindingRejection`（具名 code）、`ClaimReceipt`/`GrantedTask`/`SessionBinding`/`TaskIdentityHint`、`createBoundRootAgent(caller, options)`。

`role-dispatch.ts`：`Code2PaperSpawnProvider`、`registerCode2PaperSpawn(caller, options)`（返回 `{providerName, dispose}`）、`dispatchRole(caller, options)`（返回 `{run, binding}`）、`RoleDispatchOptions`（含 `providerName`/`agentOptions`/`taskId`/`epoch`/`fence`）。

`request-contract.ts`：`REQUEST_CONTRACT_VERSION='c2p-host-request/1'`、`RequestRecorder`（`reserve`/`dispatch`/`settle`/`markUnknown`）、全部 receipt/request 形状、`RequestRejection`、`requestBindingRef`、`sameRequestDigest`、`assertRequestBindingCurrent`、`assertReservationMatches`。

`request-accounting.ts`：`installRequestAccounting(hostCtx, options)`（返回 `{authorizations, dispose}`）、`DispatchAuthorizations`（`issue`/`consume`/`revoke`/`outstanding`）、`gatedAdapter(underlying, authorizations, diagnostics?)`、`digestSupportedRequest`、`acceptReservation`/`acceptDispatch`、`boundedIteratorReturn`、`REQUEST_DIGEST_VERSION`、`STAGE_ESTIMATOR_VERSION/SOURCE`、`ITERATOR_RETURN_BUDGET_MS`。

`terminal-result.ts`：`TERMINAL_TOOL`、`TERMINAL_PARAMETERS`、`TERMINAL_SCHEMA_VERSION`、`TerminalResult`、`TerminalRecord`、`installTerminalTool(agentCtx, {capture, session})`（`TerminalHandle`: `committed`/`refusals`/`dispose`）、`TerminalArgumentCapture`（`install`/`observe`/`raw`）、`rebuildTerminal(events, formatVersion)`、`digestText`/`digestJson`、`SESSION_FORMAT_V3/V4`。

## 活跃 binding 生命周期示例（真实消费者形状）

```ts
const bindings = new SessionBindings({
  caller: { executionId, runId, hostGeneration: bridge.hostGeneration },
  recorder,                                  // Python claim 权威的本地替身/接线
});
registerCode2PaperSpawn(ctx, { bindings });  // 一次；dispose 撤销 admission
const root = await createBoundRootAgent(ctx, {
  bindings, sessionId, task: { taskId, epoch }, cwd,
});
const dispatched = await dispatchRole(ctx, {
  parent: root.handle.agent, role: 'writer',
  prompt: [{ type: 'text', text: '...' }],
  signal, bindings,
  agentOptions: { provider: route, model, maxTokens },
});
// dispatched.binding 在创建窗口内已可 requireCurrent；
// run.result 是 child 自身 turn 的结果；run.dispose() 释放 child 并撤销绑定。
await dispatched.run.result;
await dispatched.run.dispose();
```

资源责任：`SessionBindings` 是进程内授权缓存，不是持久账本；binding 随 `run.dispose()`/agent 销毁释放；claim/fence 的持久权威在 Python 侧（R01–R03 接线）。本候选不新增 TS 持久余额，不改 frozen runtime。

## 派发来源合同（2026-10-01 第三轮：H-R4 后 FAIL-CLOSED）

- **`agents.withInitiator`、公开 Agent、公开 signal、复制摘要、同一 request 对象、首次调用、微任务顺序、provider/model 材料一致、`awaiting-prepare` 状态，单独或组合都不是派发授权。**
- **H-R4（已实测）**：最外层 `agent/request` listener 可以 `await next()` 后在瀑布 settle 与 loop prepareCall 之间的窗口调用公开 `llm.prepareCall`（同 signal），窃取任何状态型武装并取得 claiming closure；其自有材料完成 reserve/dispatch/settle，合法 child 返回 error。**因此 prepareCall 不再武装、不再铸造任何 claiming closure；当前不存在任何可获得的认领凭据。**
- **FAIL-CLOSED（裁决前状态）**：accounting listener 对受保护会话的一切分发具名拒绝（诊断 `no loop preparation for this request signal`，chunk `dispatch_origin_unproven`）；公开 `llm.stream` 对 owned ticket 的一切直连分发在进入任何 listener/adapter 前拒绝；wrapper 比 child fiber 长，child 销毁后拒绝仍成立。
- 准备票据按 signal 注册、只对受保护 agent 注册；`waterfall → awaiting-prepare` 之后不再推进。claiming 状态（`dispatchable/dispatched/entered/fallback-ready`）为裁决后机制保留。
- 合法 child 与一切公开调用同样被拒：零 reserve、零 adapter、child 不完成。等待/取消/清理矩阵在该状态下无法开启其 recorder 门，13 项以具名原因 skip（见 `cancellation.test.ts` 的 `LOOP_ORIGIN_PENDING`）。
- 退出条件与最小接口差异见 [h04_loop_origin_escalation_20261001.md](h04_loop_origin_escalation_20261001.md)：runtime 私有 loop-origin ALS 标记 + 公开 `llm.stream` 退出标记 + loop 内部回落入口；或 LEAD 选择维持 FAIL-CLOSED 并登记 R02 阻塞。
- `AsyncIterator.return` 250ms 截止、缺 usage 不补 0、`TOOL_NOT_STARTED`/`TOOL_OUTCOME_UNKNOWN` 不作为成功等合同不变。
## 派发来源合同（2026-10-01 第四轮：loop-origin.1 落地，裁决 §6 实现）

- **runtime 私有来源已落地**（候选 `0.2.0-rc.1+loop-origin.1`；补丁域仅
  `dsh-agent-loop` 与 `dsh-llm` 两个文件的逐字节 hunk，见
  [interface-diff](../../integrations/dsh/dev/runtime-0.2.0-rc.1/loop-origin/interface-diff.md)）。
- **来源建立**：`AgentLoop` step 的整个流消费包在私有 `AsyncLocalStorage.run({sessionId, signal, request, dispatched:false}, …)` 内；admission（`streamWithRegistration` 的同步 peek+consume）先于任何 listener body。prepared 与 NO_ADAPTER 回落 handle 的 stream 都从该入口进入；公开 `prepareCall` 返回的 handle 不携带来源。
- **runtime 具名拒绝**：作用域存活期内重入（嵌套、复制 request、同 signal 的新请求）由 admission 以 `DISPATCH_ORIGIN_CONSUMED` 拒绝；作用域外的公开派发 store 为空，由 Host 拒绝。
- **只读核验**：dsh-llm 导出 `currentLoopDispatchOrigin()`（冻结快照转读）；`peekLoopDispatchOrigin`/`consumeLoopDispatchOrigin` 为 runtime 导出面，consume 的一次性成功窗口只含 loop 自己的 admission 调用。不导出 ALS 实例、run/enterWith、可变 token；无预消费/铸造面。
- **Host 核验**（`request-accounting.ts`，`1bc8d00b…`）：受保护 agent listener 与 root 面只读 guard 都经 runtime-checked 的 `currentLoopDispatchOrigin` 属性读核验（未补丁 runtime 无此导出 → 按名拒绝）。核验条件：origin 存在、`dispatched===true`、会话一致、signal 同一性。作用域外/部署面冒名拒绝 chunk `dispatch_origin_unproven`（诊断 `public surface dispatch claims a protected session without a loop origin` 或 agent 面的 `no loop preparation for this request signal`）；外路由仍由 agent 面 `protected_route_mismatch` 具名拒绝（部署面由 guard 先拒）。
- **恢复的合法合同**：合法 prepared/回落/A-B 各 R/D/S 恰一次；原 13 项 skip 全部恢复为真实执行；等待/取消/清理矩阵、缺 usage 不补 0、`AsyncIterator.return` 250ms 截止、`TOOL_NOT_STARTED`/`TOOL_OUTCOME_UNKNOWN` 不作为成功等合同不变。
- **身份**：见本文顶部身份表（loop-origin.1 实测）；base `43490765…` 未动，patched `1e0e6fa2…`，`dsh_version`/`upstream_dsh_version` 分离记录。check:compat 84/84、B02 23、doctor exit0（日志 `run/w2-lo-final/`）。未登记 Gate-H PASS。

## 派发来源合同（2026-10-01 第五轮：验收返修 LO-1/2/3/4 闭环）

- **LO-1**：admission 改为四值 oracle（`absent/admitted/refused/external`）。存活作用域内发起的公开派发（公开 `llm.stream`、prepared handle、当场 prepareCall handle，含部署面）经清空式隔离返回——隔离以逐 `next()/return()/throw()` 再入空 store 实现，与惰性 listener wrapper 的迭代时机一致。C19 实测三入口在受保护 child 的 listener 内各成功一次（其他 provider 恰 3 次），合法 child R/D/S 恰一次并 completed；冒用仍零 reserve/adapter。
- **LO-2**：公开 `prepareCall` 恢复原 NO_ADAPTER 拒绝（C20(a) 具名、无 handle）；loop 内部回落经公开 `llm.stream` 在 origin run 内 admitted 恰一次（C20(b)），真无 adapter 对照保留（C14b）。
- **LO-3**：`read_manifest` 的 patched 字段检查仅在候选 id 带 `+` 时生效；旧默认 `0.1.5-rc.3` 与原 `0.2.0-rc.1` manifest 沿原格式加载（B02 新增两版本实测）；漂移/缺新身份/不一致拒绝保留。
- **LO-4**：新导出以 runtime 自身 `.d.ts` 声明（两包类型 hunk），Host 移除 unknown 断言；公共 `consumeLoopDispatchOrigin` 移除，替换为单次 admission oracle + 清空式隔离 runner（后者只能清空，不能建立/铸造来源）；源码补丁交付于固定 commit `4878cdabd87d4041bdaff61d04c966883b9fd07a`（tag `dsh-v0.2.0-rc.1`），源码 tsc/完整 host 构建通过，源码构建产物换入验证候选后 86/86 行为等价。
- 身份：见顶部表（返修后实测：树 `5f340b3a…`、补丁脚本 `9c98b720…`、源码补丁 `80ffbdd8…`、receipt `bec54f92…`、staging `3981269e…`、outputs `8be3cd0a…`）。check:compat 86/86、B02 24、doctor exit0（日志 `run/w2-lo-rework/`）。未登记 Gate-H PASS。

## 派发来源合同（2026-10-02 第六轮：公开预消费反例闭环，私有消费兑现）

- **反例机理**：`AsyncLocalStorage.run(..., async () => …)` 创建 Promise 时公开 async
  hook 同步执行，彼时快照未消费；观察者经公开 admission oracle 取真实 request 抢先
  置位，合法 child 被阻断（QA 双候选复现，均有合法正对照）。
- **修复**：公开 admission oracle 删除。一次性状态只在 runtime 私有域：来源作用域由
  loop 私有 establish 建立（建立即权威，无独立消费步骤）；loop 自己的同步 stream
  entry 经模块私有 admission 子作用域标记；`takeLoopDispatchEntry()` 消费的是
  entry-ack（非来源状态），该 ack 仅存在于 loop 自己的 entry 调用窗口（公共调用者
  无法进入），被首次判定消费后不可复用，据此放行的派发仍需 Host 只读核验。
- **隔离不变**：存活作用域内发起的一切公开派发（async hook、listener、预持 handle、
  部署面）被清空式隔离——waterfall 创建与全部迭代都在空 store 内；普通公开流量
  sibling 直通成功（C19），公开 NO_ADAPTER 原语义（C20(a)）与内部回落单次合法
  （C20(b)）保持。
- **回归 C21（更新）**：公开观察者（同步 internal/get hook、async hook）只用剩余公开面
  （peek + 以伪造 capability 调用 symbol entry + 受保护会话公开派发）实测 admission
  恒拒、观察者派发具名 `dispatch_origin_unproven`、合法 child completed 且
  R/D/S/adapter 各 1；交付候选与源码构建候选均 87/87。entry-ack 方案被同步
  internal/get hook 抢先消费的反例已由能力门控设计取代。
- **证据封存**：存活证据封存于 `.dsh-dev/run/w2-loop-origin-private-20261001-182722/`；
  首轮 `w2-lo-final/` 与 `qa-loop-origin-awkji3_e/` 因历史候选重建灭失，已如实登记
  （`EVIDENCE_SEAL.md`），不补造。本轮起候选重建不删除 run/ 与封存根。
- 身份：见顶部表（树 `a010ccdc…`、补丁脚本 `e2a8cd2a…`、源码补丁 `419d5a8d…`、
  receipt `85a37546…`、staging `950ba6d4…`、outputs `2aeceb7b…`、源码构建候选树
  `7ae6af55…`）。check:compat 89/89、B02 24、doctor exit0（日志 `run/w2-lo-repair3/`）。
  未登记 Gate-H PASS。

## 派发来源合同（2026-10-02 第七轮：同步 hook 预消费反例闭环，能力门控内部派发）

- **反例机理**：entry-ack 子作用域方案下，entry 调用链内的 `this.loopCtx.llm` 触发
  cordis `internal/get` waterfall——同步 hook 在 ack 被 loop 取走之前消费它，合法
  NO_ADAPTER 回落 child 变 error（R/D/S/adapter 全 0；双候选复现，均有合法正对照）。
- **修复**：entry-ack 删除。能力门控内部派发入口：来源作用域对象本身即能力，由
  loop 私有 establish 创建、仅在 loop 自己的调用帧里作为实参传给
  `LlmRuntime[loopDispatchEntry](options, preparedCall, capability)`；入口第一件事
  是对象同一性校验（转调 agent-loop 的 `admitLoopDispatchOrigin(capability)`），
  校验失败即走公开隔离路径。公共面无任何可被 entry 链上 hook 抢先消费的状态。
- **隔离不变**：公开 `streamWithRegistration` 对来源零变更——来源可见且非 trusted
  → 整个构造（含调用方自定义 `Symbol.asyncIterator` 的创建）与迭代都被清空式隔离。
- 身份：见顶部表（树 `a010ccdc…`、补丁脚本 `f1a310cd…`、源码补丁 `23ab6350…`、
  receipt `a6c69d83…`、staging `66458c03…`、outputs `2aeceb7b…`、源码构建候选树
  `dcf69658…`）。check:compat 87/87、B02 24、doctor exit0（日志 `run/w2-lo-repair2/`）。
  未登记 Gate-H PASS。

## 派发来源合同（2026-10-02 第八轮：转发 Proxy capability 截获反例闭环，模块级能力门控派发）

- **反例机理（CAP-1）**：capability 作为实参经 `this.loopCtx.llm[entry](…)` 传递时，
  cordis `internal/get` listener 可调用 `next()` 后返回仅转发 Proxy——其方法包装截获
  实参中的真实 capability 并抢先 `admitLoopDispatchOrigin(realCapability)`，合法 child
  error（R/D/S/adapter 全 0；双候选复现，均有合法正对照）。"getter/hook 看不到实参"
  的声明不成立。
- **修复**：capability 永不经由可拦截表面。loop 的派发点改用 **静态模块导入的
  `runLoopDispatch(options, preparedCall, capability)`**（dsh-llm 模块级函数）——静态
  ESM 导入不经 cordis resolver/getter，转发 Proxy 无法插入该调用链。入口第一件事做
  对象同一性校验（`admitLoopDispatchOrigin(capability)`：capability 必须就是活跃作用域
  对象），失败 → 公开隔离路径；成功 → 消费一次并在真实 runtime 实例上受信派发
  （实例注册表 + prepared record 携带 `runtime: this`，单实例规则 fail-closed）。
  symbol-keyed 实例方法移除（CAP-1 的泄漏通道）。
- **PC-2 闭环**：源码/源码补丁/源码构建的构造期隔离与交付侧对齐（waterfall 创建与
  `Symbol.asyncIterator` 获取都在清空作用域内）；回归 **C23**（listener 提供的自定义
  `Symbol.asyncIterator` 工厂在清空作用域内执行，seesOrigin=false，探针派发到达自身
  provider，合法 child 各 1）。
- **回归 C22**（CAP-1）：internal/get listener 返回仅转发 Proxy、方法包装对每个调用
  尝试 `admitLoopDispatchOrigin(args[2])`——实测 proxyAdmissions=0、合法 child
  completed 且 R/D/S 恰一次、仅合法 child 到 adapter。
- 身份：见顶部表（树 `392e4acf…`、补丁脚本 `eac2d8c5…`、源码补丁 `30133c39…`、
  receipt `352551db…`、staging `904f6ecf…`、outputs `2aeceb7b…`、源码构建候选树
  `301a5e23…`）。check:compat 89/89、B02 24、doctor exit0（日志 `run/w2-lo-repair3/`）。
  未登记 Gate-H PASS。

## 派发来源合同（2026-10-03 第九轮：Gate-H 审查后 GHS-1～4 返修整包交付）

- **GHS-1（P1 受信派发身份不能被公开参数声明）**：
  - 完全移除 `streamWithRegistration` 的 `trustedLoopDispatch = false` 公开声明参数。公开方法、公开参数、公开 resolver 可能包装的对象，均不能声明或携带“受信”。
  - 受信派发必须且只能经 runtime 私有通路进入：仅在 `AgentLoop` step 派发点建立来源并持有私有 capability，通过静态模块导入调用 `runLoopDispatch(options, preparedCall, capability)`，并在通过 `admitLoopDispatchOrigin(capability)` 同一性校验后，从模块私有 WeakMap `privateLoopDispatchers.get(runtime)` 获取私有派发器执行。
  - 受信路径上的实例解析与 prepared record 彻底消除代理包装：在 `LlmRuntime` 构造器中植入模块私有 Symbol `kRootRuntime`；`unwrapRuntime` 辅助函数可靠穿透 Cordis `createTraceable` / `withProps` 或公开 resolver 的转发 Proxy，将 `preparedRecord.runtime` 与 `runLoopDispatch` 解析严格锚定于原始真实 `LlmRuntime` 实例，杜绝了 Proxy 身份不匹配导致的 `DISPATCH_ORIGIN_CONSUMED` 误判。
  - Host 保持只读核验：更新 `request-accounting.ts` `verifyOrigin` 上方注释，明确只读核验 session/signal，不新增权威。
  - 回归探针：**C24**（测试公开布尔控制、公开方法或未授权调用者无法铸造受信派发权）；**C25**（测试 resolver Proxy 包装受信路径涉及的全部成员时，无法截获或铸造派发权，且合法 child 正确完成）。
- **GHS-2（P1 注册表生命周期跟随 deployment 销毁注销）**：
  - 在 `LlmRuntime` 构造器中通过 `this.ctx.effect` 挂载销毁生命周期钩子，在 deployment / fiber dispose 时自动从 `loopDispatchRuntimes` 与 `privateLoopDispatchers` 注销。
  - 销毁 Deployment A、新建 Deployment B 后，Deployment B 的 prepared 派发与 NO_ADAPTER 回落派发均正常完成且各计 1 次。
  - 两个 deployment 同时存活时的明确语义：prepared 派发按 prepare 时的 runtime 实例严格归属绑定派发，绝不跨 deployment 串号；无 prepared 记录的直接回落（fallback）因缺乏唯一 runtime 归属而严格 **fail-closed**（拒绝派发、不计 adapter、不产生 settle）。
  - 回归探针：**C26**（验证 deployment 销毁后注销、并发双 deployment 下直接回落 fail-closed，以及销毁后恢复单个 deployment 时的完整派发能力）；**C27**（验证 deployment 生命周期完整序列：销毁 A -> 新建 B -> B prepared 与 fallback 均成功，重复销毁 A 安全幂等）。
- **GHS-3（P2 types 来源与全文身份）**：
  - 交付候选与 `-built` 候选中的 `.d.ts` 声明文件均来自源码真实 `tsc -p ... --emitDeclarationOnly` 编译输出，杜绝手改或假借。
  - `dsh-llm/lib/types/index.d.ts`（SHA-256 `320517790cd0770206834fbea83603e544b54f22dd1eb91000d1d5869fb1e20f`）、`dsh-agent-loop/lib/types/index.d.ts`（`a3509f051a061ee2c6d6c7ac2fbf8f7d4a4acbce34dcfff9138557a84d7f2d40`）与 `dispatch-origin.c2p.d.ts`（`baadf757589e385085d3d8409d1ef3d7dbc5ede84a114ad121d5a44484e36188`）在 delivery 候选、`-built` 候选与源码 tsc 独立产物之间逐字节 100% 对齐。
- **GHS-4（P2 源码构建侧 B02：LEAD 默认裁定）**：
  - 遵照 LEAD 裁决，`-built` 候选声明范围明确收窄为“源码等价证据”（JS/types 严格一致、原 89+ 探针通过 93/93、沙箱与 HTTP 正常），明确标注“不声称 B02/doctor”。
- **实测完整结果**：
  - 交付候选 `0.2.0-rc.1+loop-origin.1`：`check:compat` **93 tests / 93 pass / 0 fail / 0 skipped**；B02 `pytest` **26 passed**；`doctor` exit 0（`bytes_match=true`，`compat_composition_ready=true`）；`test_execution_identity.py` **24 passed**；`smoke-web` / `smoke-compat` exit 0；`git diff --check` 干净。
  - 源码构建候选 `0.2.0-rc.1+loop-origin.1-built`：`check:compat` **93 tests / 93 pass / 0 fail / 0 skipped**。
  - 身份：见顶部表（树 `671daa1a…`、补丁脚本 `b36b887f…`、源码补丁 `0db693e7…`、receipt `ea004d45…`、staging `60acfbb2…`、outputs `9c00688b…`、源码构建候选树 `3076d2fc…`、-built receipt `78292cbe…`、-built staging `b4c9e445…`）。
  - 本文尚未独立冻结，未登记 Gate-H PASS，等待独立 QA 复核。
