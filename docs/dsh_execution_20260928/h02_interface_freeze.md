# H02 接口冻结记录（H02 → H03/H04）

> 2026-09-28，窗口一实施并提交。依据 [H02 任务卡](01_baseline_and_dsh_compatibility.md) 与
> [接口交接要求](h02_h04_handoff.md)。本文件登记**实际导出、实测时序、资源责任与可运行消费示例**；
> 状态在 LEAD/QA 复核后登记为 `frozen`，本文件本身不宣布已冻结。
> H01 已验收（[h01_acceptance.md](h01_acceptance.md)），Gate-H 仍需 H03/H04。

| 项 | 值 |
|---|---|
| 实现文件 | `integrations/dsh/src/session-binding.ts` `404f7984d01b51073a6f8f5941f56c9f594161be563a215f09b4ff2403348952`<br>`integrations/dsh/src/role-dispatch.ts` `c8758e10565531f36ca8e3c4732ac919f559209ef9869deeb13fe2a8100999b4`<br>`integrations/dsh/src/request-contract.ts` `d133fc43dc58909b7b300c90edc989cdac4cbc233ba46bd0d34fb804bd7341bb`（本轮未改） |
| 测试文件 | `integrations/dsh/tests/binding.test.ts` `598359297f6e671ee82a3aa451d4513854c8fc4321fd33dc9a2d8039c6be9005`（11 项） |
| 配置变更 | `integrations/dsh/package.json` `165d4452…`、`package-lock.json` `6a747c1d…`：新增 `@deepseek-ai/dsh-subagent`、`@deepseek-ai/dsh-llm` 两个 **peer**（仅声明，不从 registry 下载；staging 测试验证二者仍解析进冻结 runtime）。接线用途：前者提供 `SubagentProvider`/`SubagentRun` 合同与子 Agent 组合 helper，后者提供 `createUserMessage`。 |
| 构建 / staging | 回执 `989b2076c99305dc6894a0d71a5fd741e95211ecb207e55ffb3c1a080ebddd95`，`outputs_digest 4a0dd15f612725ae6d6ee0f9eaca968883668aa12f3d38c8c6f21d283d17ceb5`；staging 回执 `a44dec24…`，staged 树 `525f0b45dd5c049f5ed70c2a27ec18ccfcc69a711ed498aa9a57e39a3352aa36`（14 文件） |
| 冻结 runtime | DSH `0.1.5-rc.3`，树 `7e8f199b67027944d646e0c99f5041d4704360377e4d7466fce683c1d468d3ab` |
| 命令 | `npm --prefix integrations/dsh run check:compat` → exit 0，**27/27**（11 H02 + 10 H01 + 6 工具链） |

## 1. 实测决议：标准 spawn 不可用，采用公开窄 provider

**测量方法**（`binding.test.ts` 第 1 项）：注册一个只记录请求键并转发给真实 `spawn` provider 的
测量 provider（`ctx.subagents.getProvider('spawn')` 为公开 API），用真实父 Agent 启动一次子委托。

| 观测 | 实测结果 |
|---|---|
| provider 收到的请求键 | `['descriptor','parent','prompt','signal']` —— 只有数据，**没有 setup/callback 字段** |
| `ctx.subagents.start()` 解析时子会话日志 | `sandbox/mode, approval/policy, agent/inbox/spliced, turn/start, agent/inbox/spliced` |
| 含义 | 调用者拿到 handle 时，**prompt 已投递、首轮已 `turn/start`**；创建窗口早已关闭 |
| 更早的可观察点 | 只有 `agent/created` 公告（不是 hook）；`agent/pre-step` 晚于 prompt 装配 |
| 绑定结果 | 标准通路下 `bindings.resolve(child) === undefined` |

**决议**：采用窄 provider `c2p-spawn`（`Code2PaperSpawnProvider`）。它只调用公开
`agents.create({ setup })`，用与标准 driver 相同的**公开** helper 组合子 Agent
（`@deepseek-ai/dsh-subagent` 的 `childSessionMeta`/`resolveChildDepth`/`resolveChildAgentOptions`/
`applyChildComposition`/`captureDelegatedPolicyOverrides`/`appendDelegatedPolicyOverrides`），
在创建窗口内只增加一件事：可信绑定。**不替换全局 loop factory，不导入私有 helper
（无 `attachStructuredRuntime`、无 driver 内部模块），不在 start 返回后补绑。**

组合 helper 契约：child 的 preset join 由标准 `applyChildComposition` 完成（它内部的 join 是
optional-chained），因此 provider 在 **join 之后**用 `standingMountFor(childCtx)` 做后置校验：
**没有 join 就是失败（`unbound-child`），`undefined` 绝不当作成功**；父侧另有
`composedPreset(parent.ctx)`/`standingMountFor(parent.ctx)` 的前置校验。
（H01 的 `applyChildComposition(caller, childCtx, parentCtx)` 不能在此处再调一次：`composeFrom`
对已 join 的 scope 会抛错；root 路径仍使用 H01 的 `mountCode2PaperPreset`。）

### 1.1 LEAD 复核四项的收口（2026-09-28 第二轮）

| 项 | 问题 | 本轮收口 |
|---|---|---|
| **H02-L1** | 请求 recorder 合同未交付，§5 只有 claim 类型与“镜像形状”说明 | 新增 `src/request-contract.ts`：`RequestRecorder` 四方法 + 全部回执/拒绝类型 + 真实可编译的 mock 消费测试（见 §5） |
| **H02-L2** | `Code2PaperSpawnOptions` 要求 `caller`，示例/测试却没传；测试用 `Record<string, unknown>` 掩盖 | 先建立**最小编译反例**（真实类型下 `TS2345: Property 'caller' is missing`），再删去未使用的 `caller` 字段并统一实现/示例；测试改为 `typeof import('../src/*.js')` 关联真实导出类型，mock 以 `implements` 实现真实接口 |
| **H02-L3** | `assertTrusted` 只在有 fence hint 时比较；旧绑定本身仍可授权新 child | 新增 `requireCurrent()` 与 `stale-binding` 码；`assertTrusted`、`dispatchRole`、窄 provider `start()` 全部改为“先验绑定自身有效性，再谈 hint”。实测：父 fence=1 → 权威推进到 2 后，不带 hint、带当前 hint、经公开 provider 入口三条路径都在 claim/创建/材料投递前拒绝；当前父的成功对照保留 |
| **H02-L4** | `dispatchRole` 允许任意 `providerName`，只在 start 返回后补验绑定 | 新增 `BINDING_PROTOCOL = 'c2p-trusted-binding/1'` 与 `isBoundDelegationProvider()`；`dispatchRole` 在 **start 之前**用 `ctx.subagents.getProvider(name)` 校验已登记 provider 是否携带该协议，否则 `unbound-provider`。取得 run 后的校验失败由本入口负责 `run.dispose()` 后再拒绝（测试用带协议但不返回 localAgent 的 provider 验证恰好处置 1 次） |

### 1.2 第三轮：I2 与 I1 收口（2026-09-28）

窗口三的诱饵复现了 I2：只贴公开 `bindingProtocol` 字符串的诱饵通过前置检查，在返回 run 前已用真实
`agents.create` 建 child 并 `followup(prompt)`；事后 `dispose` 只能清理，不能撤回已投递的材料。
LEAD 裁决 CHANGES_REQUESTED。本轮收口：

| 项 | 修前 | 修后 |
|---|---|---|
| **I2 准入** | `dispatchRole` 只比较公开协议字符串（可伪造） | 改为**对象归属登记**：`registerCode2PaperSpawn` 用模块私有 `WeakMap` 记录「该 provider 对象 ←→ 该 `SessionBindings` ←→ 是否已撤销」，`dispatchRole` 在 `start()` 前查同一登记。公开标签降级为**仅表示意图**的诊断谓词 |
| I2 反例 | 诱饵通过检查、投递材料后才被清理 | 诱饵（同标签、真实建 child + followup）、错误 bindings 的 provider、已撤销注册：**start 前**分别以 `unbound-provider`/`misbound-provider` 具名拒绝；断言 `startCalls=0`、新 child 0、child claim 0、adapter 0 |
| I2 backstop | 用直接注册的假 provider 测试（新规则下会被前置拒绝） | 改为**已准入** provider 的独立故障场景：经注册 helper 登记一个 remote 形状（run 无 localAgent）的 provider，验证入口先 `dispose()`（恰好 1 次）再抛 `unbound-child` |
| **I1 示例** | §5 示例在 `root.dispose()` 之后才 `requests.reserve(...)`，不能代表「活跃绑定下发送」 | 示例改为在活跃 root/binding 下完成 reserve→dispatch→settle，最后在完整清理路径统一 dispose；异常分支不泄漏 |

保留项：合法默认名与合法自定义名照常成功；公开签名保持兼容（仅新增可选 `provider` 字段）；
request 合同未因 H04 草稿重写。

## 2. 真实导出与完整类型

### 2.1 `src/session-binding.ts`

```ts
export interface CallerRef { executionId: string; runId: string; hostGeneration: number }
export interface TaskRef { taskId: string; epoch: number }
export type ClaimPurpose = 'root' | 'child'
export interface ClaimRequest { caller: CallerRef; task: TaskRef; purpose: ClaimPurpose; parentClaimId?: string }
export interface ClaimReceipt { claimId: string; taskId: string; epoch: number; fence: number; compositionRef: string; grantedAt: number }
export interface ClaimRecorder { claim(request: ClaimRequest, options?: { signal?: AbortSignal }): Promise<ClaimReceipt> }
export interface GrantedTask { caller: CallerRef; task: TaskRef; receipt: ClaimReceipt }
export interface SessionBinding extends GrantedTask { sessionId: SessionId; parentSessionId?: SessionId; boundIn: 'creation-window' }
export type BindingRejectionCode = 'claim-rejected' | 'claim-aborted' | 'stale-fence' | 'stale-binding'
  | 'forged-task-id' | 'unbound-agent' | 'unbound-parent' | 'unbound-child'
  | 'unbound-provider' | 'misbound-provider' | 'creation-aborted'
export class BindingRejection extends Error { readonly code: BindingRejectionCode; constructor(code, message, options?: { cause?: unknown }) }
export interface SessionBindingsOptions { caller: CallerRef; recorder: ClaimRecorder }
export interface ClaimInput { task: TaskRef; purpose: ClaimPurpose; parentClaimId?: string; signal?: AbortSignal }
export interface TaskIdentityHint { taskId?: string; epoch?: number; fence?: number }

export class SessionBindings {
  constructor(options: SessionBindingsOptions)
  get size(): number
  claim(input: ClaimInput): Promise<GrantedTask>
  bind(sessionId: SessionId, granted: GrantedTask, options?: { parentSessionId?: SessionId }): SessionBinding
  release(sessionId: SessionId): void
  resolve(subject: SessionId | Agent): SessionBinding | undefined
  require(subject: SessionId | Agent): SessionBinding            // plain read: "was it bound"
  requireCurrent(subject: SessionId | Agent): SessionBinding      // authority read: refuses a superseded grant
  assertTrusted(subject: SessionId | Agent, hint: TaskIdentityHint): SessionBinding   // requireCurrent + hint compare
  currentFence(task: TaskRef): number | undefined
  dispose(): void
}

export interface BoundRootOptions {
  bindings: SessionBindings; sessionId: SessionId; task: TaskRef; cwd: string
  presetId?: string; signal?: AbortSignal; material?: (granted: GrantedTask) => Promise<void>
}
export interface BoundRoot { handle: AgentHandle; binding: SessionBinding; dispose(): Promise<void> }
export function createBoundRootAgent(caller: Context, options: BoundRootOptions): Promise<BoundRoot>
```

### 2.2 `src/role-dispatch.ts`

```ts
export const CODE2PAPER_SPAWN_PROVIDER = 'c2p-spawn'
export const BINDING_PROTOCOL = 'c2p-trusted-binding/1'   // intent marker, NOT an authorization
export function isBoundDelegationProvider(provider: SubagentProvider | undefined): boolean   // diagnostic only
export interface Code2PaperSpawnOptions {
  bindings: SessionBindings
  providerName?: string                                   // L2: no `caller`
  provider?: SubagentProvider & { bindingProtocol?: string }   // Host-owned object; registered, not a bypass
}
export interface SpawnRegistration { providerName: string; dispose: () => void }   // dispose revokes the admission

export class Code2PaperSpawnProvider implements SubagentProvider {
  readonly name: string
  readonly capabilities = { agentOptions: true, outputSchema: false, depthLimit: true, toolFilter: false, persona: false }
  readonly inheritsParentContext = false
  readonly bindingProtocol = BINDING_PROTOCOL
  constructor(options: Code2PaperSpawnOptions)
  start(request: ResolvedSubagentStartRequest): Promise<SubagentRun>
}
export function registerCode2PaperSpawn(caller: Context, options: Code2PaperSpawnOptions): SpawnRegistration

export interface RoleDispatchOptions {
  parent: Agent; role: string; prompt: readonly ContentBlock[]; signal: AbortSignal
  bindings: SessionBindings; taskId?: string; epoch?: number; fence?: number
  agentOptions?: AgentOptions; providerName?: string
}
export interface RoleDispatch { run: SubagentRun; binding: SessionBinding }
export function dispatchRole(caller: Context, options: RoleDispatchOptions): Promise<RoleDispatch>
```

未声明能力（`outputSchema`/`persona`/`toolFilter`）由 subagent 服务在调用 provider 前**明确拒绝**
（测试断言 `UNSUPPORTED_CAPABILITY`），不是静默忽略。结构化输出属 H03 terminal 合同。

**provider 准入（I2）**：`role-dispatch.ts` 持有模块私有 `WeakMap<SubagentProvider, {bindings,
providerName, revoked}>`，只由 `registerCode2PaperSpawn` 写入、由其 disposer 置 `revoked`。
`dispatchRole` 在 `start()` 前依次判定：名字已登记（否则 `unbound-provider`）→ 该**对象**有准入记录
（否则 `unbound-provider`：同标签诱饵/外来对象）→ 记录未撤销（否则 `unbound-provider`）→ 记录的
`bindings` 与本次 `options.bindings` 同一实例（否则 `misbound-provider`）。这是进程内执行对象归属
记录，不是第二套任务权威或预算账本。

### 2.3 `src/request-contract.ts`（H02-L1）

```ts
export const REQUEST_CONTRACT_VERSION = 'c2p-host-request/1'

export interface RequestBindingRef { sessionId: SessionId; taskId: string; epoch: number; fence: number; claimId: string; compositionRef: string }
export interface RequestIdentity { sequence: number; purpose: string }
export type RequestPayloadPart = 'messages' | 'tools' | 'config'
export interface RequestDigest { digestVersion: string; algorithm: 'sha256'; value: string; parts: readonly RequestPayloadPart[] }
export interface RequestEstimate { inputTokens: number; outputTokens: number; wallClockMs?: number }

export interface RequestReserveRequest { binding: RequestBindingRef; identity: RequestIdentity; digest: RequestDigest; estimate: RequestEstimate }
export interface ReservationReceipt { contractVersion: string; reservationId: string; requestId: string; binding: RequestBindingRef; digest: RequestDigest; grantedAt: number }

export type RequestStage = 'reserved' | 'dispatch-recorded' | 'adapter-entered' | 'response-observed'
export interface RequestDispatchRequest { reservation: ReservationReceipt; digest: RequestDigest }
export interface DispatchReceipt { contractVersion: string; requestId: string; reservationId: string; digest: RequestDigest; stage: 'dispatch-recorded'; recordedAt: number }

export interface RequestUsage { inputTokens: number; outputTokens: number; source: string }
export type RequestFinish =
  | { kind: 'settled'; finishReason: string; usage: RequestUsage }
  | { kind: 'unfinished'; finishReason?: string; usage?: RequestUsage }
  | { kind: 'unknown'; reason: string; lastStage: RequestStage }
export type RequestResponseSource =
  | { kind: 'adapter-stream'; ref?: string; digest?: string }
  | { kind: 'provider-raw'; ref: string; digest: string }
  | { kind: 'none' }
export interface RequestSettleRequest { requestId: string; reservationId: string; finish: RequestFinish; response: RequestResponseSource }
export interface SettlementReceipt { contractVersion: string; requestId: string; settlementId: string; finish: RequestFinish; response: RequestResponseSource; settledAt: number }

export interface RequestMarkUnknownRequest { requestId: string; reservationId: string; lastStage: RequestStage; reason: string }
export interface UnknownReceipt { contractVersion: string; requestId: string; lastStage: RequestStage; reason: string; uncertainty: 'send-outcome-unknown'; recordedAt: number }

export type RequestRejectionCode = 'reserve-refused' | 'reserve-aborted' | 'stale-binding' | 'digest-mismatch'
  | 'unknown-reservation' | 'dispatch-refused' | 'settle-refused' | 'unknown-refused' | 'contract-unsupported'
export class RequestRejection extends Error { readonly code: RequestRejectionCode }

export interface RequestRecorder {
  reserve(request: RequestReserveRequest, options?: { signal?: AbortSignal }): Promise<ReservationReceipt>
  dispatch(request: RequestDispatchRequest, options?: { signal?: AbortSignal }): Promise<DispatchReceipt>
  settle(request: RequestSettleRequest, options?: { signal?: AbortSignal }): Promise<SettlementReceipt>
  markUnknown(request: RequestMarkUnknownRequest, options?: { signal?: AbortSignal }): Promise<UnknownReceipt>
}

export function requestBindingRef(binding: SessionBinding): RequestBindingRef
export function sameRequestDigest(a: RequestDigest, b: RequestDigest): boolean
export function assertRequestBindingCurrent(binding: RequestBindingRef, currentFence: number | undefined): void
export function assertReservationMatches(reservation: ReservationReceipt, dispatched: RequestDispatchRequest): void
export function assertSupportedDigest(digest: RequestDigest): void
```

形状不变式：reserve/dispatch 必须同一 `RequestDigest`（`assertReservationMatches`）；digest 必须声明
覆盖 `messages`/`tools`/`config` 全集（`assertSupportedDigest` 拒绝部分覆盖，而不是记一个残缺摘要）；
`DispatchReceipt.stage` 只有 `dispatch-recorded`，**不声称 HTTP 已送达**；缺失 usage 保持缺失；
`markUnknown` 只记录不确定性与最后可证实阶段，退款/阻断由生产权威裁决。

## 3. 时序与可信注入位置

**实测顺序**（`binding.test.ts`，全部经真实 `agents.create`/`ctx.subagents.start`）：

```text
dispatchRole / provider.start 前置门（都不产生副作用）
   ├─ provider 对象在本 Host 的准入登记中且归属本次 bindings   # I2：否则 unbound/misbound-provider，绝不进入 start
   └─ 父绑定 requireCurrent()                       # L3：过期绑定即 stale-binding，hint 不能升级它
   ▼
claim 等待（阻塞时）──▶ 0 材料读取 / 0 adapter 调用 / 0 绑定 / 0 agent·session
   │ 收到成功回执
   ▼
material(granted) 材料读取（可选端口，只在回执之后调用一次）
   ▼
agents.create({ setup })  ← 未发布
   ├─ mountCode2PaperPreset(caller, agentCtx)      # root：H01 公开 helper
   ├─（child）applyChildComposition → standingMountFor 后置校验
   └─ bindings.bind(session, granted, {parentSessionId})
   ▼
agent/created（公告）——此时绑定与组成均已存在（测试断言 true）
   ▼
首轮 prompt 投递 / agent/pre-step / 首工具访问 / 首模型请求（H02 全程 0 次 adapter 调用）
```

| 可信注入位置 | 由谁注入 | 说明 |
|---|---|---|
| `caller`（executionId/runId/hostGeneration） | Host 组合创建 `SessionBindings` 时 | 绝不来自模型输入、session metadata 或请求字段 |
| `task`/`epoch` | 调用 `claim` 的 Host | 模型/请求里的同名字符串只能经 `assertTrusted` 比较，不能替换 |
| `fence` | claim 回执 | `SessionBindings` 记录每个 (task, epoch) 的当前代次；低于当前值即 `stale-fence`；绑定自身过期即 `stale-binding`（无需 hint） |
| `compositionRef` | claim 回执 | H02 只记录不解释；I01 生成正式组成身份时消费 |
| 子 Agent 的 task/epoch | **父的可信绑定** | child claim 以 `parentClaimId` 关联；prompt 文本中的 task id 完全惰性（测试断言） |

**零读取/零 adapter 证据**：阻塞 claim 时断言材料端口调用 0、`llm/stream` 计数 0、绑定 0、
agent/session 列表不变；全部拒绝路径结束时 adapter 计数仍为 0。伪造 task ID 在 claim 之前
即被拒绝；L3 的过期父绑定（不带/带当前 hint/经 provider 入口）与 L4 的 stock `spawn` 覆盖
均在 **claim、创建与材料投递之前**被拒（`recorder.requests` 与 agent 列表不变）。

## 4. 资源 owner 与处置责任

| 资源 | owner | 处置方式与完成含义 |
|---|---|---|
| 子 Agent 运行 | `SubagentRun`（provider 返回） | `run.result` 在子 Agent 达到静止后以 `SubagentResult` 完成（不因领域失败 reject）；`run.dispose()` 取消剩余工作、等待静止、释放 `AgentHandle`，并**释放该子会话的绑定**；幂等 |
| root Agent | `BoundRoot`（`createBoundRootAgent` 返回） | `bound.dispose()` 处置 handle 并在 `finally` 中释放绑定；直接处置裸 handle 会留下缓存绑定，直到 `SessionBindings.dispose()` |
| 绑定注册表 | `SessionBindings` 实例（Host 组合） | `dispose()` 清空；**非持久**：丢失只丢缓存，权威仍是 claim recorder |
| 取消 | 调用者信号 | `request.signal` 是 delegation 的规范取消通道：发布前取消由 `agents.create` 事务回滚（`creation-aborted`），发布后取消经 `child.cancel({kind:'parent'})` 落到 run |
| `whenIdle()` | provider | 只表示子 Agent 自身活动静止，**不**代表持久 flush；H02 不声称持久化 |
| flush | **H03**（terminal/raw 与 Session flush 兼容证明） | H02 的绑定不落盘，也不声称 flush；持久 flush 的兼容证明归 H03，生产持久接线与准入归 R01–R03/A01 |
| 取消/静止/请求结算时序 | **H04** | 取消、provider 静止与请求结算的顺序由 H04 证明；H02 只提供 delegation 侧的取消通道 |
| 取得 run 后校验失败 | `dispatchRole`（本入口） | **已准入** provider 下不应发生；一旦发生，本入口先 `run.dispose()`（失败作为 cause 保留）再抛 `unbound-child`，绝不把未绑定 child 交给调用者。用独立故障场景证明：经注册 helper 登记一个 remote 形状（run 无 `localAgent`）的 provider，断言恰好处置 1 次 |
| 部分创建失败 | 创建事务 | setup 抛错或提交失败即回滚：不发布 agent/session、不发出公告、`release()` 清掉可能的绑定（测试断言列表与绑定均无残留） |

**失败路径清理验证**（一次性故障注入，验证后已还原受测字节）：在首项测试内注入
`assert.fail` 并运行 `python scripts/dsh_dev.py test -- …/binding.test.ts` →
exit **1**（6 pass / 1 fail），运行结束后 `.dsh-dev/run/` 中**没有** `h02-binding-*` 残留，
说明测试失败时 `after()` 仍执行并删除本次私有根。此前两次被强杀（timeout/SIGTERM）的运行确实
留下了私有根，已清理；那属于进程被硬杀，不在本验证范围（H01 N2 同样只证明异常清理）。


## 5. 交给 H04 的请求 recorder 合同与注入点

H04 需要的请求账本 seam 已由 [§2.3](#23-srcrequest-contracttsh02-l1) 的
`src/request-contract.ts` **实际交付**（不是“镜像形状”）：`RequestRecorder` 的
`reserve`/`dispatch`/`settle`/`markUnknown` 四个方法、全部请求与回执类型、拒绝码，以及
`requestBindingRef`/`sameRequestDigest`/`assertRequestBindingCurrent`/`assertReservationMatches`/
`assertSupportedDigest` 五个纯函数。H02 的测试以真实类型实现了 mock recorder（`implements
RequestRecorder`）并跑通 reserve→dispatch→settle 与 mark_unknown，证明合同可消费；**实际
reserve/dispatch 硬门由 H04 在真实 loop 上证明**。

对应 [交接要求](h02_h04_handoff.md) §2 的语义：`reserve` 成功前不调用 `next`/adapter；
`dispatch` 必须先于委托 next 记录且不声称 HTTP 送达；`settle` 不把本地取消/未知记成成功或零成本；
`markUnknown` 只记录不确定性。生产实现由 R02 接线，TS 不建第二套余额。

### 注入点（H02 的两个 mock 已实现，H04 照搬形状）

| 注入点 | claim mock（`MockClaimRecorder`） | request mock（`MockRequestRecorder`） | 断言用途 |
|---|---|---|---|
| 延迟 | `block()` / `release()` | `block()` / `release()` | 等待期零 dispatch、零材料、零创建 |
| 拒绝 | `refuseWith()` / `forgive()` | `refuseWith()` / `forgive()` | 拒绝即零 dispatch、无残留 |
| 取消 | 调用者 `signal`（含**已 abort** 的信号，mock 先读 `aborted` 再挂监听） | 同左 | 取消即零 dispatch |
| 代次推进 | `supersede(task)` | 复用 `SessionBindings.currentFence` | 旧回执/旧绑定被拒（`stale-fence`/`stale-binding`） |
| 错配回执 | — | `assertReservationMatches`（同 reservation + 同 digest） | `digest-mismatch`/`unknown-reservation` |
| 部分覆盖摘要 | — | `assertSupportedDigest` | `contract-unsupported`，不记残缺摘要 |

H03/H04 **不得**通过全局变量或可变共享 preset 交换 task：task/epoch/fence 只能经
`SessionBindings` 与回执传递，子 Agent 的权威只来自父的可信绑定。

### 可运行的消费示例（与测试同源，全部使用真实类型）

**生命周期顺序（I1）**：root 一获得就进入**外层** `try/finally`，`dispatchRole` 与请求调用都在该
作用域内，因此委派被拒或请求调用失败仍会释放 root；run 有自己的**内层** `try/finally`，
`run.dispose()` 抛错时外层 `finally` 仍会尝试 `root.dispose()`。两处都不 `catch`，异常照常向外
传播，不被静默吞掉。请求事实在 root 绑定仍然**活跃**时提交。

这是 H02 的**合同消费示例**：它证明冻结的请求 recorder 合同可被真实类型调用，**不是发送门**。
真实模型请求的计量与 `next`/adapter 时序由 H04 的 loop middleware 证明；在 `run.result` 之后调用
mock 账本不能冒充发送前的 reserve/dispatch 硬门。

```ts
// 1. Host 组合启动后：登记可信 caller 与 claim 权威 seam，注册窄 provider。
const bindings = new SessionBindings({ caller: { executionId, runId, hostGeneration }, recorder });
registerCode2PaperSpawn(ctx, { bindings });          // L2：不再需要 caller 参数

// 2. 先 claim，后创建；材料只在回执之后读取。
const root = await createBoundRootAgent(ctx, {
  bindings, sessionId, task: { taskId: 'T-1', epoch: 1 }, cwd,
  material: async (granted) => { /* C00 投影；只在回执之后执行 */ },
});

// 3. root 一拿到就进入外层清理作用域：其后的任何失败——dispatchRole 被拒、请求调用失败、
//    run.dispose() 抛错——都必须回到这里释放 root。
try {
  // 4. 委派角色；run 拥有自己的内层清理作用域。
  const { run } = await dispatchRole(ctx, {
    parent: root.handle.agent, role: 'writer', prompt: [{ type: 'text', text: '…' }], signal, bindings,
  });
  try {
    await run.result;    // 子 Agent 静止后的结果（H03 负责领域 terminal）

    // 5. 合同消费示例（不是发送门）：在 root 绑定仍然活跃时提交请求账本事实。
    const requests: RequestRecorder = new MockRequestRecorder(bindings);
    const reservation = await requests.reserve({
      binding: requestBindingRef(root.binding),          // 活跃绑定，不是已释放的引用
      identity: { sequence: 1, purpose: 'writer' },
      digest, estimate: { inputTokens: 512, outputTokens: 256 },
    });
    const dispatched = await requests.dispatch({ reservation, digest });   // digest 必须与 reserve 相同
    await requests.settle({ requestId: reservation.requestId, reservationId: reservation.reservationId,
      finish: { kind: 'unfinished' }, response: { kind: 'none' } });       // 缺 usage 就保持缺失
  } finally {
    await run.dispose();   // 内层清理：即使抛错，也只向外传播，不阻止外层释放 root
  }
} finally {
  await root.dispose();    // 外层清理：无论上面哪一步失败都会执行
}
```

可执行版本即 `integrations/dsh/tests/binding.test.ts`（`npm --prefix integrations/dsh run check:compat`
的 `test` 阶段真实运行，非伪代码）；其 mock 类以 `implements` 实现真实接口，示例与导出类型在
编译期一致。

## 6. 边界（H02 不声称的部分）

1. **无生产 claim 持久性**：recorder 只有 mock；durable claim/outbox/恢复由 R01–R03 接线复验，TS 不建第二套账本。
2. **无领域结果**：`SubagentRun.result` 只映射 stop reason；typed terminal/原始来源属 H03，领域模型属 C01/C03。
3. **无模型请求**：全程 offline，`llm/stream` 计数为 0；H04 才建 mock adapter 与真实 seam 探针。
4. **未验证会话持久 flush**：`whenIdle()` 不等于落盘。
5. **绑定不跨进程恢复**：进程重启后由权威重新授权（R01–R03），`SessionBindings` 不参与恢复。
6. `agentOptions` 透传由 `resolveChildAgentOptions` 决定；H02 不解释模型路由语义。

## 7. 证据位置

| 证据 | 位置 / 摘要 |
|---|---|
| 完整门日志（typecheck→build→stage→test） | `.dsh-dev/run/h02-logs/check-compat-i2.log`（**27/27**） |
| 仅 H02 测试日志（11/11） | `.dsh-dev/run/h02-logs/binding-i2.log` |
| I2 修前反例 | 窗口三诱饵：`stockSpawnRefusedBeforeStart=true`、`decoyDisposeCalls=1`、`decoyPromptDeliveredBeforeBinding=true`（原始输出 `.dsh-dev/run/qa-w3-20260928/h02-recheck/freeze/binding_final.log`）。本轮把它作为**修前对照**复用：修后同一形状的诱饵在 `start()` 之前被拒，`startCalls=0`、新 child 0、child claim 0、adapter 0 |
| L2 最小编译反例（修前） | `tsc` 报 `TS2345: Property 'caller' is missing …`；修后同一真实类型调用通过（探针已删除，等价调用保留在测试内） |
| 失败路径清理注入运行 | `.dsh-dev/run/h02-logs/fault-run.log`（exit 1，无私有根残留；注入已还原） |
| 外部共享输入前后对比 | 一次完整 `check:compat` 前后：staging 回执/staged 文件/profile 文件/共享模块回退顶层/preset 根条目集合逐字相同 |
| 复跑一致性 | 冻结输入下 `check:compat` 连续通过；构建回执与 staged 树摘要稳定（见文首身份表） |

I2/I1 对应测试节点（`binding.test.ts`）：`the dispatch entry admits only provider objects this Host
registered, before any start`（诱饵 / 错误 bindings / 已撤销注册 / 合法默认名与自定义名 / 已准入
provider 的 backstop 清理）。

以上命令均在隔离环境内、无网络 mock 下运行；未改冻结 runtime、日常 DSH，无 live，无 Git 提交。
