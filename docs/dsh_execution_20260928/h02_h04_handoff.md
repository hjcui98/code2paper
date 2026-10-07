# H02 → H03/H04 接口交接与 H04 实验约束

> 2026-09-28，LEAD 裁决。H01/H02 已通过验收；H02 最终接口 `0ba7f1ce…` 已批准 frozen，I1/I2 已关闭，见 [最终验收与并行派工](h02_acceptance.md)。本文保留接口交付要求和运行时约束；Gate-H 尚需 H03/H04。
> 2026-09-29：本文历史双 TS 写者调度已由 [执行入口 §3.1](README.md) 接替。H03/H04 统一归窗口二；S1 已推翻 llm/stream 的 scope 隔离假设，可信来源以 [第 01 份当前批次](01_baseline_and_dsh_compatibility.md) 的实验和验收约束为准，不改变已冻结 H02 类型合同。

## 1. 开工顺序与责任

H01/H02 已按 [第 01 部分](01_baseline_and_dsh_compatibility.md) 完成验收。当前窗口一实施 H03，窗口二实施 H04，窗口三独立准备与复核；已满足 H02 前置，不再等待一轮方案批准。最初责任分配见 [并行派工](h02_acceptance.md) §2–5；当前候选、发现与构建交接以 [H03/H04 审查指令](h03_h04_review_directive.md) 为准。

H02 的 DSH owner 负责 `src/session-binding.ts`、`src/role-dispatch.ts`、`tests/binding.test.ts`，并交付 `docs/dsh_execution_20260928/h02_interface_freeze.md`。`src/request-contract.ts` 的共享 Host 请求 recorder 类型已由窗口一交付、窗口二按消费者审查；H02 不实现 H04 middleware。LEAD 与 QA 已复核实际导出、类型及运行证据，正式登记 `interface_status=frozen`；后续保持只读消费。H04 只消费接口并写 `src/request-accounting.ts` 和自己的两份测试；需要改变共享接口时交回 H02 owner，不在另一个窗口同时编辑。

H03/H04 可并行编写互不冲突的文件，但共享 `build/stage/check:compat` 由指定的一名执行者串行运行。验收窗口冻结受测源码、配置、构建及 staging 代次，其他写者暂停修改这些输入；结束后再交还写权。Node 兼容测试默认 `--test-concurrency=1`；这不代替生产 Agent 的独立并发开关。

以下交付要求已由 H02 冻结记录满足；后续接口变更仍按它们复核：

1. 真实导出名、完整参数和返回类型、绑定文件摘要，标准 spawn 或窄 provider 的实测决议。不能把拟议的 `dispatchRole` 等名称当成现有 API。
2. claim 完成、绑定、prompt 材料读取、首工具访问、prepareCall、stream 的准确时序；调用者/执行/task/epoch/fence/组成引用的可信注入位置。故意阻塞 claim 时的零读取和零 adapter 调用证据。
3. 创建成功及部分创建失败后的资源 owner；Agent、Session、handle 的访问和处置方式；cancel、whenIdle、flush、dispose 的责任及 Promise 完成含义。
4. H04 可注入的最小 request recorder 完整接口与假的回执类型、拒绝/延迟/取消注入点，以及按真实导出类型编译的消费示例；仅给 `ClaimRecorder` 或手写宽松替代接口不满足交付。H03/H04 不通过全局变量或可变共享 preset 交换 task。

H02 不持有或交付真实 loop 私有的 prepared handle。它交付可信 binding 与 recorder 合同；H04 通过真实 loop 和公开 mock adapter 校准 prepare/dispatch。H03 负责 terminal/raw 和 Session flush 兼容证明，H04 负责取消及静止，后续 R/A 负责生产持久接线与准入。

## 2. recorder 的职责和后续生产接线

H04 是兼容性实验，使用无网络 mock adapter 和明确标注的 recorder。它不等待 C01/C04/R02 的生产 JSON-RPC，否则形成 Gate-H → Gate-K → C/R → H04 的循环依赖。C01/C04/R02 后续以 Python 合同、worker 协议和唯一账本接线，再复验同一行为；mock 回执不能批准生产发送，也不构成 durable balance。

下表冻结行为语义；具体 TypeScript 签名由 H02 的上述实际交接记录冻结。这里的 `request.*` 是自有 Host 接口名，不是 DSH 自带 API。

| recorder 方法 | 最小事实与回执关系 | H04 必验行为 |
|---|---|---|
| `request.reserve` | 接收可信 binding 引用、请求序号/用途、resolved config、含有序 messages/content 和 tools/schema 的版本化装配请求摘要、预留估量；成功返回绑定该摘要的 request/reservation 回执，失败明确拒绝 | 等待成功回执前不调用 next/adapter；拒绝及等待中取消均零 dispatch；不存在 TS 自行扣减余额 |
| `request.dispatch` | 引用同一 reservation、绑定及同一完整请求摘要；记录进入发送边界的意图/事实并返回回执 | 等待后在委托前重算实际请求摘要并核对，错配/过期/迟到回执不能绕过绑定；记录必须先于委托 next；此记录及 next/adapter 入口均不声称 HTTP 已送达 |
| `request.settle` | 引用同一 request、可观测 finish/usage/response 来源与摘要；缺失 usage 保持缺失 | 不能把本地取消、未知发送或终态缺失记成成功/零成本；不产生领域 acceptance |
| `request.mark_unknown` | 引用同一 request、最后可证实阶段与无法确认的原因 | 记录不确定性，不退款、不自动重发；生产阶段由 Python reducer 阻断相应 backend group |

请求、结果或取消对象中同名的模型字符串不能替换可信 binding。recorder 的事件列表可用于断言顺序，不实现第二套持久余额或完整恢复 reducer。对已经 reserve、但因取消没有进入发送边界的情况，应向权威侧报告可证明的阶段，由其裁决；不得将“尚未观测到”推断成“确定未发送”。

两个事件复制同一个旧 hash 不等于复核。摘要按显式版本覆盖受支持的全部模型可见字段，不能在 JSON 序列化时静默丢材料；AbortSignal 等运行对象不直接作为载荷。H04 还须证明 next 后至流迭代/adapter 实收前的材料不漂移，区分裸 API 特征与受保护的真实 loop 路径。装配摘要不等于最终 HTTP 字节，附件/图片及 adapter 投影仍由 C00/V01 校验。

## 3. H04 使用的实际运行时 API

绑定本机冻结 npm `0.1.5-rc.3`，运行树摘要 `7e8f199b67027944d646e0c99f5041d4704360377e4d7466fce683c1d468d3ab`。以下来自 `.d.ts` 和打包实现的静态核对；运行断言仍由 AT-H04 提供。

| 项目 | 校准后的实现要求 |
|---|---|
| 请求 seam | `dsh-llm/lib/types/index.d.ts:45` 的 `llm/stream` waterfall；没有 `llm/request`、`preparedCall` 事件或 `onRequest` |
| 冻结 config | `maxTokens`、`temperature`、`reasoningEffort`、`model` 等按 `callConfigEquals` 比较；不是 `maxOutputTokens`/`thinking`。`prepared.config` 是 detached deep-freeze |
| 同步拒绝 | 对 `prepared.stream(options)` 直接传入变更 config，或复用已 dispatch 的 prepared call，均同步抛 `INVALID_PREPARED_CALL`；用 `assert.throws`，监听器/adapter 计数为零 |
| waterfall 后再次校验 | 仅 prepared 通路在 `adapterStream` 内再次比较 config，异常转终态 failure chunk。直接 `llm.stream` 没有这道 prepared 比较。对可变 prepared 请求的中间件 config 篡改，应消费流断言 failure chunk 和零 adapter 调用，不能误用同步异常断言 |
| messages/tools 与标记 | `callConfigEquals` 不覆盖 messages/tools。`markAgentLoopRequest` 只打 WeakSet 标记；真实 loop 的 `buildRequest` 另行冻结 header/tools、消息及请求。打标、冻结和材料摘要是不同性质，不能相互替代 |
| prepared 的 owner | 真实 loop 在 `prepareRequest` 持有 prepared call，`llm/stream` 不公开该 handle；`NO_ADAPTER` 时 loop 可回落直接 stream。H04 须证明受支持组成走 prepared，直接/回落路径被拒或具备同等硬门，不伪造公开事件或要求 H02 传不存在的参数 |
| adapter 代次 | `PreparedAdapterCall` 捕获闭包及对应 model 信息；没有公开的 id/generation/epoch。`AdapterRegistrationHandle.replace(providers)` 只替换同一 adapter 的路由，不替换 adapter 实例；另测 disposer 后重新注册及动态设置变化，证明旧 prepared call 不重读新事实 |
| retry | 插件无所述 config 开关；使用真实组成禁用 `llm-retry`，或 provider 的 `{mode: 'normal', maxRetries: 0}`；诱发失败后核对无 retry、没有额外请求，并按真实异步事件语义检查恢复结果 |
| title/compaction/PTC | title 不发 `session/title-llm-request` 且 `title.source.model` 不出现；`compaction.config.auto === false`；工具为 native，实际请求无 `RUN_CODE_NAME`。不能仅根据插件名称推断已关闭 |
| 取消 | 用实际 `Agent.cancel(cause)`、`whenIdle()`、`AgentHandle.dispose()` 与所属资源的退出观测，分别断言调用与完成顺序；whenIdle 不代替持久 flush 或 provider 静止 |
| subprocess | `terminate()` 幂等；`waitForExit(signal?: AbortSignal): Promise<boolean>` 无 timeout 参数。独立 cleanupSignal 有界，true 才证明其托管范围为空；false/抛错保持阻断，不能复用已 aborted 的请求 signal |

H04 的 R3/R4 分别保留直接 config 改写与 prepared call 重用反例；补 waterfall 后 config 改写，区分两处拒绝表示。新增 `direct_stream_post_waterfall_config_drift`、`message_injection_undetected` 和“标记不冻结”的裸 API 特征对照，并对受保护路径在 next 前/后改写 messages/tools/config 独立断言零违规派发。R5 验闭包快照和注册替换；R8 对 retry/title/compaction/PTC 分别留行为证据。C1–C4 覆盖正常退出、取消后真正退出、cleanup 等待中止及无法观测的异常。若没有可观测的 subprocess 范围，不得以 `AgentHandle.dispose()` 已调用来报告 quiescent。

## 4. 测试发现和组成身份

B02 工具链必须递归发现 `dev/toolchain/**/*.test.ts` 与 `tests/**/*.test.ts`，并将两者纳入类型检查；H01 未创建 `tests/` 时仍能执行工具链测试。推荐入口为 `npm --prefix integrations/dsh run check:compat`，按 typecheck → build → stage → test 执行。独立 `test:compat` 只检查当前 staging，必须继续拒绝漂移，不能为了变绿悄悄重新 stage。

`compatibility.json` 的 B00 观测与 `bundle_build_digest=null` 保留历史含义；当前开发身份由 build/toolchain/staging 回执提供。I01 生成正式组成身份时引用真实构建、安装解析、有效配置和 worker 字节，不能把历史 B00 记录改写成已执行过的兼容证明。

[返回总执行入口](README.md)
