# loop-origin.1 · runtime 私有派发来源接口差分（模块级能力门控派发版）

> 2026-10-03 整阶段接续：[全部剩余工作与集中修改指导](../../../../../docs/dsh_execution_20260928/remaining_work_and_batch_repair_guidance_20261003.md) §3 与 [README §3.15](../../../../../docs/dsh_execution_20260928/README.md#315-当前模块级派发候选-gate-h-独立审查与原第-01-份整包续派2026-10-02-2210)。
> 交付候选 `0.2.0-rc.1+loop-origin.1`（树 `671daa1a…`）与源码构建候选 `-built`（树 `3076d2fc…`）。
> 闭环 GHS-1（私有派发不暴露布尔入口、unwrapRuntime 穿透 Proxy）、GHS-2（LlmRuntime 销毁注销与双 deployment fail-closed）、
> GHS-3（manifest 列齐 5 文件、对齐 types 来源）、以及 smoke 候选路由与动态审计。
> 历史 2026-10-02 审查结论见 [Gate-H 审查](../../../../../docs/dsh_execution_20260928/stage_static_entry_gate_h_review_20261002.md)。

> 窗口二按 [接口裁决 §6](../../../../../docs/dsh_execution_20260928/h04_loop_origin_escalation_20261001.md)
> 开发，经 2026-10-01 验收（LO-1/2/3/4）与 2026-10-02 返修差分（公开预消费反例）
> 完成的 runtime 来源补丁。绑定候选 `0.2.0-rc.1+loop-origin.1`。上游基树 `43490765…` 未动。
> 本文是接口差分与行为合同，不是 Gate-H 验收记录。

## 1. 补丁域与可重建产物

编译 hunk（逐字节、漂移即拒；`scripts/dsh_dev.py loop-origin-setup` 从 pristine base
复制后应用）：

- `node_modules/@deepseek-ai/dsh-agent-loop/lib/index.js`
- `node_modules/@deepseek-ai/dsh-agent-loop/lib/types/dispatch-origin.c2p.d.ts`
- `node_modules/@deepseek-ai/dsh-agent-loop/lib/types/index.d.ts`
- `node_modules/@deepseek-ai/dsh-llm/lib/index.js`
- `node_modules/@deepseek-ai/dsh-llm/lib/types/index.d.ts`

源码交付（LO-4）：固定 monorepo 源码 `deepseek-ai/deepseek-harness`
tag `dsh-v0.2.0-rc.1` = commit `4878cdabd87d4041bdaff61d04c966883b9fd07a`
（`.dsh-dev/sources/loop-origin-020/`）。窄改：`packages/core/agent-loop/src/{agent.ts,index.ts}`、
新增 `packages/core/agent-loop/src/dispatch-origin.c2p.ts`、`packages/llm/llm/src/index.ts`。
源码差分 `loop-origin-source.patch`（`87941d847abb581abe65a924773b980b702b95f03cda4a23831bba9cce3bb46b`）。

源码构建（返修轮实测）：`pnpm install --frozen-lockfile` exit0；两包 `tsc -b` exit0；
`pnpm run build:lib:host` exit0；源码构建产物换入 `0.2.0-rc.1+loop-origin.1-built`
（树 `3076d2fcdbf6b2b49167e8132ce9b5801d95079a36f9bd05af17302e8482be97`）后完整 launcher 套件 **93/93 pass**（含公开 async-hook
预消费回归 C21、Proxy capability 截获回归 C22、构造期隔离 C23、公开布尔参数与未授权调用者 C24、全链路成员 Proxy 包装 C25、注册表生命周期与双 deployment C26、生命周期序列 A->B 与幂等注销 C27）——源码产物与 hunk 补丁行为一致。逐字节权威仍是 hunk 补丁
（npm 发布压缩变体未单独复刻，见 evidence §5）。

## 2. 私有消费入口（2026-10-02 第三次返修核心：模块级能力门控派发，CAP-1 闭环）

**公开面不存在任何能消费、铸造或复位来源的 oracle/helper/ack，且来源能力不经过任何
可被代理拦截的调用路径。** 三轮独立实测证伪了三类方案：公开 admission oracle
（async hook 在 establishment 窗口抢先消费）；entry-ack 子作用域（同步 internal/get
hook 在 entry 调用链内抢先消费）；capability 作为经 `this.loopCtx.llm[entry](…)` 传递的
实参（公开 resolver 的 internal/get listener 返回转发 Proxy，其方法包装截获实参中的
真实 capability 并抢先消费——合法 child R/D/S/adapter 全 0）。

新设计（模块级能力门控派发，capability 永不经由可拦截表面）：

- **一个模块私有 ALS**：`dispatchOrigin`。来源作用域仅由 `AgentLoop` step 的派发点经
  内部 `establishLoopDispatchOrigin({sessionId, signal, request})` 建立（该函数返回
  `{run, capability}`，capability 即活跃作用域对象本身）。建立即权威，无独立可消费状态。
- **模块级受信派发函数**：dsh-llm 导出
  `runLoopDispatch(options, preparedCall, capability)`——loop 的派发点经 **静态模块
  导入**（`import { runLoopDispatch } from '@deepseek-ai/dsh-llm'`）调用它。静态 ESM
  导入不经 cordis resolver、不经属性 getter、不存在可插入的转发 Proxy——capability
  在 loop 自己的调用帧内直达 dsh-llm 模块函数，任何 hook/listener 都无法截获。
- **capability 门控**：`runLoopDispatch` 第一个动作是
  `admitLoopDispatchOrigin(capability)`（agent-loop 导出；对象同一性校验：capability
  必须就是活跃作用域对象，且未消费）。失败 → 公开隔离路径；成功 → 消费一次并在
  **真实 runtime 实例**上执行受信派发。
- **真实实例解析不经代理（GHS-1）**：每个 `LlmRuntime` 实例在构造时挂载模块私有 `kRootRuntime` 符号；
  `unwrapRuntime` 辅助函数可靠穿透 Cordis `createTraceable` / `withProps` 或公开 resolver 的转发 Proxy，
  使 `preparedRecord.runtime` 与 `runLoopDispatch` 解析严格锚定于原始真实 `LlmRuntime` 实例。
  通过模块私有 WeakMap `privateLoopDispatchers.get(runtime)` 获取私有派发器，不再经过任何公开方法或包装对象。
- **注册表生命周期注销（GHS-2）**：在 `LlmRuntime` 构造器中通过 `this.ctx.effect` 挂载销毁生命周期钩子，
  在 deployment / fiber dispose 时自动从 `loopDispatchRuntimes` 与 `privateLoopDispatchers` 注销。
  双 deployment 存活时：prepared 派发严格按 prepare 时的 runtime 实例隔离派发；直接 fallback 回落
  因缺乏唯一 runtime 归属严格 fail-closed。
- **公开面剩余导出（只读或能力门控）**：`peekLoopDispatchOrigin()`（冻结
  {sessionId, signal}，不含 request/可变状态）、`admitLoopDispatchOrigin(capability)`
  （无正确 capability 即什么都不做）、`runOutsideLoopDispatchOrigin(fn)`（清空式
  隔离）。
- `streamWithRegistration(options, prepared)`：纯私有方法，移除公开 `trustedLoopDispatch = false` 参数。
  任何在来源可见作用域内发起的非受信派发（waterfall 创建、含调用方自定义 `Symbol.asyncIterator` 的获取及全部迭代）
  均被清空式隔离。
## 3. 攻击面闭环（对应裁决 §6.2 逐条）

1. 来源仅由 loop 的 step 派发建立（establish 不导出）；prepared 与 NO_ADAPTER
   回落都从 loop 自己的 entry（entry 子作用域内）进入。
2. 公开等价入口（`llm.stream`、公开 prepareCall 新 handle、预持 handle、async hook、
   listener、惰性 next/return/throw）在存活作用域内发起时被隔离；作用域外则本就
   无来源。隔离覆盖 waterfall 创建（同步 listener 调用）与全部迭代。
3. 公共查询只读且无状态转移：peek 冻结且不含 request；已彻底移除任何有状态 entry-ack 导出。
   受信派发由静态模块导入的 runLoopDispatch 承接，来源判定通过模块私有能力同一性校验门控，
   任何外部观察者、async hook、resolver 均无法截获或抢占来源（C21、C22、C24、C25 实测）。
4. 执行边界：entry 判定在 `streamWithRegistration` 同步段成立；隔离流的构造与
   全部迭代都在空 store 内；origin 作用域只围绕 loop 自己的消费。
5. 域权威不变：Host 绑定、摘要、cap、reserve/dispatch 回执、Python 账本不受影响；
   Host 只消费明示只读核验，ABI 缺失/版本/实例不一致 fail-closed。

## 4. NO_ADAPTER 与普通公开流量

- `prepareCall` 无补丁改动：真实 NO_ADAPTER 原样抛出（C20(a)）。
- loop 内部回落：loop 的 `prepareRequest` 捕获 NO_ADAPTER 后，`runLoopDispatch(request, undefined, capability)`
  在单 deployment 下自动解析到唯一活跃 runtime 派发，admitted 恰一次（C20(b)）；在多 deployment 并发存活时因无法确定归属而严格 fail-closed（C26）。
- 普通公开流量（不声称受保护会话）：隔离后 sibling 直通，各自 provider 成功
  （C19 三入口 + QA ordinary 探针）。

## 5. 旧格式兼容（LO-3 保持）

`read_manifest` 的 patched 字段检查仅在候选 id 带 `+` 时生效；B02
`test_unpatched_manifests_keep_the_original_format` 以 0.1.5-rc.3 与 0.2.0-rc.1
实测。补丁候选的 manifest `touched` 按实际差分列齐 5 文件（2 JS + 3 types）。

## 6. 回归与反例归属

- QA 公开预消费反例 → C21（公开 async-hook 观察者，只用剩余公开面）。
- 原抢票反例（H-R4 预持 handle）→ C10；同 request 重入 → C13（具名
  `dispatch_origin_unproven`，零 reserve/adapter）；复制/延迟重放 → C14/C14b；
  普通三入口 → C19；公开 NO_ADAPTER/内部回落 → C20。
- 转发 Proxy 截获反例（CAP-1）→ C22；构造期隔离反例（PC-2）→ C23。
- GHS-1 公开参数与未授权调用反例 → C24；GHS-1 全链路成员 Proxy 包装反例 → C25。
- GHS-2 注册表生命周期注销与双 deployment fail-closed 反例 → C26。
- GHS-2 deployment 生命周期序列 A->B 与幂等注销回归 → C27。
