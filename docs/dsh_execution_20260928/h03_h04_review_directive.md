# H03 候选复核与 H04 实施纠偏指令

> 2026-09-28，LEAD。**当前调度已由 [执行入口 §3.1](README.md)、[第 01 份](01_baseline_and_dsh_compatibility.md) 和 [第 02 份](02_kernel_publication_and_request_guards.md) 接替：窗口二统一 H03/H04；窗口一转 K04；窗口三独立 QA。** Gate-H 未通过。
> §1–7 保留历次候选、反例和裁决。这里的双 TS 写者/短窗口调度不再生效；产品边界、未关闭反例与验收要求继续生效，关闭状态绑定对应字节。
> H02 的已验收代码与接口未变，不因未经证实的路由推断重新修改 H02。
> 本轮仅静态核对源码、公开运行时实现和已有日志；没有运行模型、构建或产品测试，也没有代修实现。

## 1. 首轮输入与证据口径（历史，当前候选见 §6）

H02 的 `session-binding 404f7984…`、`role-dispatch c8758e10…`、`request-contract d133fc43…`
及接口文档 `0ba7f1ce…` 仍与 [验收记录](h02_acceptance.md) 相同。

| 对象 | 本次读取的 SHA-256 |
|---|---|
| H03 `src/terminal-result.ts` | `b8084ba8c5f97e02b56437610e109e221abce7ec779ca38ef713b6aa0d9235ad` |
| H03 `tests/terminal.test.ts` | `d63a4d8435c78caa70096a8b8802f211f9c0ffeffcde141c767daabe4bfd7c24` |
| H03 `tests/provenance.test.ts` | `a98b75d79e1dde47e2ad949d2ab8f3d7b2907e631ed1402fb9b732e5ef409b6e` |
| H04 `src/request-accounting.ts` | `22886cefd926baddf7a0084d3a8ab5b2e1037a30898299cba81795c2e7ed2604` |
| H04 `tests/request-seam.test.ts` | `54943fd9b5331aaeed43bcb7aae190c267360a065f3d1da1cf90a126fb5c9434` |
| H04 `tests/cancellation.test.ts` | `68583e8426db952379a3e898a7b4dd875a7e47f0272545986464f15a80322dd7` |
| 构建回执 / outputs | `3fa4c2e5ad7828e795ce3d70aaea51df52eb36849a7bb081469afd0c52dfc2f8` / `55ab7e286ceab8b989baeb31505cec3bb606200609c4d9bf050eb605f6b24e3f` |
| staging 回执 / 树 | `bf2cb46c023a09f54a777d52f928a95ad01ee27b61d48fb4576de3ca0c1053b2` / `f441dbf3eb2abcabc6b7edd9d0f6524a0eb7dacf32ae3cb7ad36356982641ca5`，18 文件 |

构建回执的 7 个 `src_inputs` 与当前源码相符；这证明构建身份对应，不证明共享构建时无其他
写者。窗口一的 [H03 交付证据](../../integrations/dsh/dev/H03_terminal_evidence.md) 摘要为
`4f59da0fc629697600aa22e3d7eaf46195381d46c7c070fe6e5eb5e1ceb9d047`。
已有 H03 聚焦日志为 12/12；较晚组合日志为 **49 项、45 pass、4 fail**，不是全套通过。
窗口二较早的 33/37 与窗口三“文件尚未出现”的准备快照均按各自时间解释，不覆盖当前输入。

LEAD 的 [只读审查记录](/tmp/c2p-dsh-h03-h04-lead-review-20260928-jtfkzgit/review.json)
绑定上述身份、日志摘要和静态发现。以下代码路径可直接核对，但新增行为反例仍由 owner/QA
运行，不把静态审查写成已复现实验。`h03-verify.log` 当前为空；其他检查声明需引用真实非空
日志才能计为新证据，不为补记录盲目重跑未受影响的 Python/smoke。

## 2. 窗口二的两项请求：裁决

### 2.1 不批准 stock spawn 后补绑定；暂不改 H02 透传

当前 `dispatchRole` 已将 `options.agentOptions` 传入 `subagents.start()`；窄 provider 已把它
传给 `resolveChildAgentOptions(parent, request.agentOptions, childDepth)`。冻结运行时该 helper
显式展开 `...requested`，subagent 服务也以 `...request` 构造 resolved request。
因此“缺少透传/被 helper 过滤”尚无证据；`stopReason:error` 和零 adapter 计数不能定位原因。

窗口二先在现有 H04 测试内记录同一委派的：请求 options、创建公告时 child.options、
`agent/request` 的解析配置、是否进入 llm seam，以及实际错误 code/message 和 session 终态。
使用既有 `dispatchRole → c2p-spawn`；先建立一次真实 reserve→dispatch→adapter→settle 的
正常对照，再做取消反例。不得用 stock spawn 启动后补登记 binding；那会重现 H02 已关闭的漏洞。
若最小证据确证 H02 丢失输入，再按原 owner 分配定向修改并重验受影响 H02 条款。

### 2.2 scope 结论目前不成立，先修正实验

`request-seam.test.ts` 的 `runChildTurn()` 在 finally 中调用 `run.dispose()`，随后才测宿主
裸派发。已经销毁的 child 监听为零不证明隔离。该测试仅创建一个 child，
`childScopes[1]` 是 undefined，`siblingChildScope !== firstChildScope` 没有检验兄弟隔离。

**H04-S1：先重做以下实验，保留原日志并注明该结论被撤回。**

- 同时保留两个真实 child 的 run/handle，测量前后断言两者仍在注册表、监听仍有效；最后统一释放。
- 分别触发 A、B 的真实 loop 派发以及宿主裸派发，核对每个活跃监听器的计数。
- 外部冒用 A 的现存 session ID、冒用 excluded ID、缺失 ID 都单列；相同 provider/model
  下仍不能取得可信任务身份。实验完成后再次从 A 派发，证明此前的零计数并非监听已失效。
- 在实际绑定的 `c2p-spawn` 路径复核，不把 stock spawn 特征实验直接当成产品路径证明。

子 scope 是否足够据此判定，暂不把“只有 delegated child 隔离”写成成立的设计前提。
`installRequestAccounting()` 当前通过 agent/created 安装，且默认会选择任一已有 binding
的 agent；代码并未限制为 delegated child。最终注册范围、真实来源和失败行为必须一致。

**受保护路由零漏计仍属于 H04，不移到后续任务再补。** 若公开 scope 不能覆盖该路由，
授权窗口二在自己的 `request-accounting.ts` 内实现最小 Host 路由/adapter 包装门并实测：
调用底层 adapter 前要求 Host 私有的一次性派发授权，绑定已接受 reservation、真实装配及
调用来源；仅凭 sessionId、模型字符串或相同 digest 不得取得授权。prepared/direct/回落
均受约束，失效/重用/未授权拒绝，合法调用仍成功。底层 mock adapter 只记录事实，不替包装门
实现拒绝逻辑；不引入 TS 持久余额或修改 runtime。公开接口无法证明时具名阻断 Gate-H。

受保护来源把 `provider` 改成别的值也不能因当前 `request.provider !== route` 分支直接
`next()` 而退出计量；合法 excluded 流量必须由可信组成范围识别。H04 的窄 gate 在本阶段
用 mock 权威验证，真实 Python 接线和最终 wire 仍留 R02/R03/V01。

## 3. 窗口二：其余静态发现与待补反例

按“最小反例 → 修现有 owner → 真实绑定通路验证”实施；不要只使当前 4 个红测试变绿。

| 编号 | 当前代码事实 | 必须修正或补证的行为 |
|---|---|---|
| H04-S3 最后等待后复核 | `await recorder.dispatch()` 后直接校验回执并进入 `next()`，无最后一次 abort/fence 检查；摘要检查在 next 之后 | 在 dispatch 等待期间分别 abort、通过新合法 claim 推进 fence、改变材料；回执返回后 next/底层 adapter 均不得调用。保留 reserve 等待点的对应反例 |
| H04-S4 finalize/清理 | record 位于循环尾部/catch，finally 只有 `await inner.return()` 且吞异常，没有超时边界 | break/return/abort/next 或 iterator 创建失败均进入一次本地终态记录路径；return 抛错或不结束要有界并具名 unsettled；记录自身失败不重试、不报结算成功 |
| H04-S5 usage/估量 | `finish:stop` 即选 settled，usage 缺失被 `?? 0` 补齐；reserve 的 inputTokens 固定为 0，估量来源没有被记录 | stop 无 usage 仍保留缺失，不伪造零成本；使用明确的本阶段估量器/版本/来源，校验有效 cap，不以未知/无效值通过。生产 tokenizer 校准另由 C00/V01 完成 |
| H04-S6 回执快照 | digest.parts 复制但未冻结；dispatch 参数仍携带原始 reservation；acceptDispatch 只比较传入 digest，没有自行核对它与 accepted.digest 相同 | 接受依据和发出的 reservation 都来自稳定 detached 快照，parts 亦不可改；等待期间突变原对象或给 dispatch 换一组自洽但非已接受的摘要均拒绝 |
| H04-S7 测试触发与污染 | C1 不等待 reserve 已进入就 abort；C2 只有零派发断言，无实际 reserve/refusal 见证；`refuseWith('')` 并未清除 refusal | 用明确 barrier 证明 reserve 已阻塞，再取消；C2 必须观察到预期拒绝且消除其他前置失败；逐例复位或隔离 recorder，拒绝后正常对照能恢复 |

当前 C2 不能作为有效准入证据：在模型请求根本未到该 seam 时也会通过。修复 fixture 后仍须
补全 [已批准矩阵](h02_acceptance.md) §4 的 prepared/direct、两等待点、scope、回执、cap、
异常终态和四项禁用断言；不能用五个 helper/特征测试覆盖整张矩阵。
资源计数须观测 enter 与 exit/仍在运行；累计 `adapterStreams > 0` 不证明取消后静止。
真实托管子进程范围存在时按独立有界 signal 验 `waitForExit`，不存在时只对该资源类记 N/A。

## 4. 窗口三：先对当前 H03 候选做独立复核

接受既有反例计划作为准备输入；H03 的 12/12 仍需独立验证。优先加入下列原有来源/恢复门
的最小反例，返回具名问题，由窗口一修原模块：

1. **跨会话/请求来源隔离。** host 级 `TerminalArgumentCapture` 目前仅以 tool-call id 为 key。
   两个存活 session 或先后两个请求复用同一 id 时，raw 不能拼接/串用；相同调用的 raw、
   normalized、parsed 必须能关联，部分 delta 不可冒称完整来源。`llm/stream` 看到的是
   adapter 输出的 delta，不自动证明捕获了 provider HTTP/SSE 原字节。
2. **重建不能只信事件名。** `rebuildTerminal()` 当前取最后一个 `c2p/terminal` 后直接断言
   类型返回 committed。独立构造缺字段、错版本、摘要与正文不符、重复冲突记录及与 tool
   成功事实不对应的日志；不能将损坏记录标为已验证恢复。只校验 H03 自己的表示/来源一致性，
   不在 TS 重写后续 Python 领域 assessor。
3. **terminal 后的其他工具。** 当前测试再次调用的是 terminal；另注册一个有可观测副作用
   的不同工具，验证 terminal 后其 body 不执行，原终态不改变。保留正常 terminal 和重复
   terminal 的对照，不依赖空工具集制造零执行。
4. **flush 与故障恢复。** 公开 `sessions.flush(session): Promise<boolean>` 与
   `sessionPersistence.flush(): Promise<void>` 是不同接口；不得把后者 void 当成前者 false。
   使用实际接口类型，核对 listener 与准确落盘记录。控制持久 listener 阻塞/失败或构造缺失
   字节的进程故障，结果不得从内存猜成成功。仅“未显式 flush 就杀进程”不保证没有后台写入，
   应按实际存在且验证过的磁盘字节判定，不能强求已落盘结果也 unresolved。

私有 sessions 根和 `compression:none` 可用于本单元；保留“未验证默认 zstd 读取”的范围
说明。暂不将最小 H03 fixture 工具装进常驻 preset，不为这轮申请修改 H01 的工具/preset。
最终 Gate-H 的联合 probe 必须让 H03 terminal 与 H04 accounting 在同一真实绑定 child 中
工作，经现有公开安装入口接线；不得只运行两套完全隔离的 fixture 就声称已完成联合接线。
确需共享 hook 时列出实际缺口再分配原 owner，不增加并行执行管线。

## 5. 写权、构建与交付顺序

**现在先给窗口三一个 H03 复核窗口。** 窗口一已释放 H03 写权；窗口二在接管声明时暂停
H04 文件写入，双方同时停止 build/stage/CLI/smoke。窗口三核对 §1 的双方输入与 staging，
按既定 snapshot2 流程运行 H03 定向反例，不重跑已知 4 项失败的兼容全套或旧 Python 套件。
H04 已知未通过不妨碍限定范围的 H03 审查，但不能因此判 Gate-H 通过。

窗口三报告并释放后，进入下一轮并行实施：

| 窗口 | 下一轮动作与所有权 |
|---|---|
| 一 | 处理 H03 独立发现；仍只改 H03 三个源码/测试文件及其 `dev/H03_terminal_evidence.md` 证据。该证据文件纳入本单元管理，不取得整个 dev 目录写权 |
| 二 | 按 §2–3 修实验、fixture 与 H04 原模块；仍只改 H04 三个文件。接管**下一轮唯一共享构建写权**，每次构建前等窗口一确认受测输入暂停写入 |
| 三 | 维护独立反例和报告；下一冻结候选先定向复核修复，再以同一组合候选复验 H01/H02/H03/H04 接线与兼容套件 |
| LEAD | 维护台账、裁决共享接口与 Gate-H；不代写实现，不替实施者运行产品验证 |

源码编辑可以并行；涉及共享 staging 的运行与双方输入写入不能并行。“只有一个 build 进程”
不足以满足这条约束。此前撞上其他窗口正在写入的构建只记诊断，不用它证明稳定验收身份。
后续每次交接声明当前写者、双方源码/测试集合、构建/staging/lock/接口摘要及释放状态。
逐条记录命令及退出码，日志展示去掉认证参数，原始失败证据保留。

无需窗口一确认现已存在的 agentOptions 透传；无需再提交同内容 H04 方案。按指令复现并实施。
不修改 frozen runtime、日常 DSH；不运行真实模型、不提交或推送 Git。

## 6. H03 修复候选接收与第二次定向复核

### 6.1 裁决与当前身份

窗口三的 **CHANGES_REQUESTED** 绑定首轮 `b8084ba8 / a98b75d7 / 3fa4c2e5`；
窗口一的 15/15 绑定修复轮 `c4a2d98b / 99b8b5b4 / 026f81e3`。两份报告不矛盾。
原 QA 的 R-H03-1、R-H03-2 保留为 **OPEN**，新交付接收为定向复验候选，尚不登记 AT-H03。
H04 三个文件与 §1 相同且已声明暂停写入；其四项失败仍不允许通过 Gate-H。

| 对象 | 本次从磁盘读取的 SHA-256 |
|---|---|
| H03 `src/terminal-result.ts` | `c4a2d98b101b3fd886e284938461823631fc61138652f889cacac107297b6b38` |
| H03 `tests/terminal.test.ts` | `d63a4d8435c78caa70096a8b8802f211f9c0ffeffcde141c767daabe4bfd7c24` |
| H03 `tests/provenance.test.ts` | `99b8b5b4db38d6550b93262dbefc2ec2b1b73930a65309c4bd61df7574d2deae` |
| H03 证据文档 | `802813d300597bda9dc4e41f7e878433ec697485431ef0f5c003984783af3d9e` |
| 构建回执 / outputs | `026f81e3f520102f33d21ac596d1642c017a63a641ebe5c8a7effddd20f772c6` / `2e66ab2e918eac3033c0d7553947cad82aa6707aa956dbe6cc7a2f5c99c90b18` |
| staging 回执 / 树 | `7009bee8088d621547dc921a1d109d839ce0a514110e37c61a207eba03745f60` / `f2175e648e9a7c386bbb1dd21492b82a0531285f5b0139b26664d4e6841bde5e`，18 文件 |

LEAD 已静态核对构建输入/输出与 staging 清单字节；7 个源码输入和 18 个 staged 文件匹配。
H01/H02 冻结输入未变。既有日志 `h03-fixes.log` 是 **15/15**；`h03-fix-check.log` 是
**52 项、48 pass、4 fail**。本轮没有由 LEAD 新跑任何产品测试、构建或模型。
绑定身份、旧 QA 日志摘要及本轮静态发现的 [审查记录](/tmp/c2p-dsh-h03-fix-lead-review-20260928-9ub1iigi/review.json)
单独保留；它不冒充窗口三的新行为验证。

### 6.2 原两项发现的剩余边界：一次列全，由窗口三定向验证

以下是读取当前实现及冻结 runtime 得到的静态缺口，**尚未由 LEAD 运行新反例**。
它们细分原来的来源归属/完整性与重建一致性要求，不增加新的领域验收器。

| 原发现 / 复验项 | 当前代码事实 | 最小反例与关闭条件 |
|---|---|---|
| R-H03-1a 调用与流归属 | 存储已按 `(streamIndex, callId)` 拆开，但 `raw(callId)` 仍通过 `latestByCall` 取最近流；提交端仍只传 `exec.callId`，`install()` 丢弃请求上下文 | 两个存活 session/request 复用同一 id，B 的流被观测后再提交/读取 A；A 必须取回 A 的 raw，B 仍取 B。覆盖交错流与延迟读取，不能只断言“读 B 时没有拼接”。捕获端与消费者须持有相同的可信请求/流关联；无法定位时明确缺失/歧义，不能猜最近条目 |
| R-H03-1b 协议完整性 | `completed=true` 仅表示 async iterator 正常结束；不检查该 tool call 的完成事实。冻结 runtime 会把 adapter 抛错归一化成 `finish(error/aborted)` 后正常结束迭代 | 经真实注册 adapter 产生部分 delta 后抛错，经过 `llm/stream` 归一化后仍应为 incomplete；另验 abort、缺少调用完成事实的截断流、消费者 break。保留真实完整调用成功对照，记录完整性的判据，不能只用直接 generator.throw 证明 runtime 路径 |
| R-H03-2a 真实成功与对应关系 | `loggedToolCalls` 仅用 callId 匹配，并以可选 `data.error` 缺失作为成功；没有检查 message 内 tool-result 的 `isError`、turn/step/事件对应及 arguments | 使用 `isError:true` 但无 `error` 元数据的合法错误结果，必须 unresolved。再验同 id 不同 turn/step、record 的 normalized 与实际 tool/call 不同、parsed 及其摘要同时改成另一个自洽结果。不能用“各自摘要自洽”代替与同一成功调用对应 |
| R-H03-2b 表示与字段校验 | 只检查少数字段是否 undefined；null/错误嵌套类型可在取属性或算摘要时抛错；terminalId/turn/step/schemaDigest/来源状态等未完整校验，成功夹具甚至使用 `schemaDigest:'z'` | 分别给 null、缺身份字段、坏嵌套字段、非法 raw 状态、错误 schemaDigest、最小 TerminalResult union 不合法但摘要自洽的记录；返回具名 unresolved，不崩溃、不 committed。使用真实 schema 摘要和成功记录作对照；只校验 H03 自有表示及来源一致性 |
| R-H03-2c 每条记录均须验证 | 多记录仅比 `terminalId` 与 `parsedDigest`，之后只校验第一条；相同这两项而其他来源/调用/版本字段不同的后续记录被忽略 | 同 id/parsedDigest 的第二条分别改 raw、normalized、prose、callId、turn/step 或版本；每条先校验，再判重复是否确实一致。损坏记录拒绝、有效冲突记录具名 conflicting-records；完全相同重复仍可接受，不得变成 first-one-wins |

R-H03-1b 中“流后来失败”和“该调用原文字节已完整结束”应按实际协议证据区分；若已有充分的
调用完成事实，可明确记录它，不需把随后另一调用的失败错误归到本调用。缺少这样的事实时，
不能仅因迭代返回 done 就标 captured。raw 保持 adapter delta 的来源级别，不声称 HTTP 原字节。
`not_observed`/`incomplete` 保留真实状态；不要求伪造完整 raw 才允许其他来源独立被验证。

R-H03-2 的成功判据依据冻结 `dsh-session` 的公开类型：`tool/result.error` 是可选内部失败身份，
失败事实由 message 的 tool-result block 表达；loop 原样保留 `isError`，可能不带 error 元数据。
应关联同一 session 中实际 call/result 事件及 turn/step，使用公开事件引用（存在时包括
sourceEventSeqs）消除 callId 复用歧义。重建的 normalized 必须等于对应 call 的日志文本，
parsed 与其解析结果语义一致，prose 对应同轮来源；完整 raw 与其他参数来源按语义核对，
不要求空白、转义与键序字节相同。无法唯一归属时返回 unresolved。

修正以上行为可调整 H03 自己的捕获/读取签名，窗口一同步 owned-path 测试和交付接口说明；
不修改 H02 合同、不在 TS 重写 Python assessor。需要超出 owned paths 的共享接口时，先交
具体调用缺口由 LEAD 分配；不要自行修改 H01/preset 或新建平行管线。

### 6.3 立即派工与窗口交接

1. **窗口三现在接管短定向复验窗口。** 先确认 §6.1 与 H04 三项暂停身份，再按 snapshot2
   做 before → 原两项反例及 §6.2 剩余边界 → H03 15 项 → after/分类比较 → 只读身份复比。
   路径使用 launcher 要求的绝对路径。当前 staged 候选完整，不为这次复验重建；不重跑已知
   四项红的兼容全套、Python、CLI/smoke。分别登记旧反例已关闭与仍失败的细分项，随后释放窗口。
2. **窗口一保持 H03 输入暂停，等本次复验退出后修剩余具名项。** 所有权仍为 H03 三个源码/
   测试文件和 `dev/H03_terminal_evidence.md`。保持原 QA/失败日志不变，按同一来源和恢复边界
   收口；报告新接口、最小反例前后结果与真实 loop/恢复接线。已经被旧 QA 验证的“其他工具
   body 拒绝”和 flush 接口差异保留为历史证据，不因两项缺口把它们重置成未研究。
3. **窗口二的 S1–S7 修正计划接受，不再等新一轮方案批准。** 仅在这个短复验窗口内继续
   暂停；窗口三明确释放后，与窗口一按各自 owned paths 并行实施，不必等 H03 最终 PASS。
   先做两个仍活着的真实绑定 child scope 测量和合法请求正常对照，再落请求门及剩余矩阵。
   窗口二是下一轮唯一 build/stage 写者，每次构建前双方明确暂停全部受测输入写入。
4. **Gate-H 联合复核另开窗口。** H03/H04 各自缺口收口、完整组合候选冻结后，窗口三才验
   同一真实绑定 child 内 terminal + accounting 接线，并复验受影响的 H01/H02 与兼容全套。
   52/48/4 不能因失败“归 H04”就批准 Gate-H；也不能用独立两套 fixture 替代联合接线。

对 H04 清理计划再明确一个 API 约束：通用 `AsyncIterator.return()` 没有标准的 AbortSignal
参数。独立有界 signal 用来约束等待及调用确实支持取消的资源 owner；超时结束等待不等于
底层 iterator/adapter 已停止。须分别记录取消/terminate 请求、可观测的退出事实与 unsettled，
不能把 Promise 超时当静止证据。“一次终态记录”是本地至多一次尝试，不声称持久 exactly-once。

本节的短复验已完成，当前派工由 §7 接续。LEAD 仅更新指令、台账和审查记录；不代改实现、不执行产品验证。

## 7. 短复验结论登记与并行修复放行

### 7.1 接受 CHANGES_REQUESTED，保留四个已关闭行为点

窗口三的 [修复轮报告](/tmp/c2p-dsh-h-qa-w3-20260928/reports/H03_fixround_verification_report.md)
及 [机器记录](/tmp/c2p-dsh-h-qa-w3-20260928/reviews/H03_fixround_verification.json) 绑定 §6.1
的 `c4a2d98b / 99b8b5b4 / 026f81e3 / 7009bee8 / f2175e64`。LEAD 已核对当前候选、
18 个 staged 文件及报告引用的三个日志摘要，未重建或运行产品测试。

- QA JSON：`83d8b0e496bf59cee67bd3010004936502fe86388449e03f0099a1927673cde3`。
- 独立探针：`28898f701d401646ff3fc704f690ab9798e38ab1ce24e8b3bc8e9f2262eb1315`；
  日志 `b2e41d66…`，exit 1，**11 项、6 pass、5 fail**。
- 实施者套件独立复现：日志 `fb6024c3…`，exit 0，**15/15**。
- before/after 分类比较：`ca938ba0…`，**UNCHANGED，0 差异**，包括字节和 inode/mtime。

四个具体行为点登记关闭：**跨流文本不再拼接、版本错误具名拒绝、摘要与正文矛盾具名拒绝、
缺对应 tool/call 具名拒绝**。这不是 R-H03-1/2 整项关闭；“原 6 项中的 4 项”是探针子例
口径，台账仍使用两项主发现和五个剩余子边界，避免不同粒度的计数混用。

§6.2 的五个子边界由“静态待复现”改为 **已独立复现、OPEN**：

| 编号 | 已观测行为 | 本轮证据的范围 |
|---|---|---|
| R-H03-1a | 同 id 的 A/B 流，raw 取 B，无索取 A 或歧义表示的接口 | 证明捕获读取接口取最近流；两个真实存活 session 的交错提交/延迟读取仍须在修复后补接线证据 |
| R-H03-1b | 真实注册 adapter 抛错被 runtime 归一化，正常结束迭代后仍 captured | 已证实归一化异常路径；abort、break、无完成事实截断仍未覆盖 |
| R-H03-2a | `isError:true`、缺可选 error 元数据仍 committed | 已证实成功判据错误；turn/step、参数与调用对应仍待补 |
| R-H03-2b | normalized=null 抛 TypeError；坏 schemaDigest/raw 状态/union、缺 terminalId 仍 committed | 已证实崩溃和误接收；其他嵌套错误及 turn/step 仍待补 |
| R-H03-2c | 同 terminalId/parsedDigest、第二条 normalized 不同仍 committed | 已证实忽略后续记录；raw/prose/callId/turn/step/版本变体仍待补 |

裁决：**H03 回到 in_progress，AT-H03 不登记；H04 继续 in_progress；Gate-H 未通过。**
短复验窗口已释放，以下实施不再等待一次放行回复。

### 7.2 窗口一：按现有 owner 收口 H03

写权恢复至 H03 原三个源码/测试文件及 `dev/H03_terminal_evidence.md`，不扩展到 H01/H02、
package/lock 或冻结 runtime。依次完成：

1. **先修重建边界 R-H03-2b → 2a → 2c。** 完整检查未知/坏结构再取字段，损坏输入返回
   具名 unresolved；使用真实 tool-result 成功事实、调用事件及参数对应；校验每条记录后
   才判重复/冲突。同批补齐 QA 明列未测的字段、对应关系和第二条记录变体。
2. **再修协议完整性 R-H03-1b。** 用真实类型和 per-call 完成事实区分完整调用、归一化
   failure/abort、消费者提前返回与截断，不以 iterator done 充抵。沿用 §6.2 的边界：若该
   调用已有充分完成事实，随后另一个调用失败不自动否定它；无完成事实不得冒称 captured。
3. **最后闭合归属 R-H03-1a 及真实消费接线。** 捕获端、terminal 消费者持有同一可信
   请求/流引用；同 id 的 A/B 都能取回自身来源，不能统一降级成 not_observed 来绕过正常
   捕获。无法唯一关联时具名缺失/歧义。验证两个存活 session 的交错流及延迟提交/读取。

实施阶段可先明确归属接口再编码，以上是修复与验证的优先级，不要求保留已知错误 API。
H03 内部签名可按 §6.2 调整并同步类型消费者；交付须列出真实导出/参数变化和旧反例映射。
每个反例以合法基准只改变该目标条件，断言预期拒绝原因；不能仅以任意 unresolved 或
总测试数增长结案。下一次交付必须覆盖完整 §6.2，不只修这轮已经执行的五个样例。

### 7.3 窗口三：修正正例夹具，准备剩余矩阵

当前 CHANGES_REQUESTED 与已观测缺陷成立。不过 LEAD 读到独立探针的两项正例局限，
须由窗口三在自己的 QA 根修正，原探针/日志保持原字节：

| 正例 | 当前写法 | 下一轮要求 |
|---|---|---|
| F1c 协议完成 | `reason:'completed'` 经 `as unknown as StreamChunk` 绕过类型；只有 delta 和 finish，没有该调用的 block-end 完成事实 | 使用冻结 runtime 的真实 StreamChunk/FinishReason 类型和完整合法事件序列（包括相应调用完成事件，正常 finish 为 `{kind:'stop'}`）；以真实调用日志确认。原 F1c 只证明当前实现把这个流标 captured，不计为协议完整性通过 |
| F2f 合法重建 | normalized 与 tool/call 文本均为 `{"result":{}}`，parsed 却是含 title/body 的 draft；tool/result 缺 turn/step，事件构造无 seq | 从真实成功 terminal 路径取一份带实际事件关联的合法基准；normalized/parsed、turn/step/调用/结果对应。逐例只变异目标字段，校验具体 reasonCode。原 F2f 的 committed 是观测值，不计为合法恢复正例 |

这些夹具局限不撤销四个已观察到的修复行为或五个阻断现象；下一轮必须防止通过另一处
无关前置错误得到拒绝，从而误称某个门已修好。旧断言若因新 API 取代，保留原日志并列明
新测试所接替的语义；不能只把失败文件移出发现集合。

窗口三现在可以在自有 QA 根准备修正版消费者、正例与 §7.1 未测矩阵；双方实现移动期间
不运行消费共享 staging 的正式验证、不修改实现。收到下一冻结候选后再执行定向验证。
另对报告 window 时间追加更正：JSON 写 19:35–19:55+08:00，引用快照生成于
22:12:41–22:13:45+08:00；按实际日志解释时间来源，保留原文件。此元数据更正不阻塞修复，
当前缺陷结论以受测摘要和日志事实绑定，不用不一致的时间值证明独占性。

### 7.4 窗口二：立即恢复 H04；共享构建由本窗口协调

按已接受的 §2–3/S1–S7 计划，在 `request-accounting.ts`、`request-seam.test.ts`、
`cancellation.test.ts` 三个文件内继续。先证明两个真实绑定 child 均存活时的 scope 行为，
并建立合法 reserve→dispatch→adapter→settle 对照，再验拒绝/取消及路由门；不等 H03 PASS，
不改 H02 已冻结接口，不用 stock spawn 后补绑定。

**下一轮唯一共享 build/stage 写者是窗口二。** 编辑可与窗口一并行；执行构建、stage 或
消费共享 staging 的测试前，双方先明确暂停受测源码/测试/配置的写入，并保持到该运行
窗口结束。不能只保证没有第二个 build 进程。窗口一需要验证时，由窗口二按当前双方输入
统一构建，再按交接窗口跑各自聚焦套件；不得自行重建或在另一方移动输入上宣布通过。

下一次联合交付由窗口二汇总双方文件集合、接口变更、lock、build/outputs、staging/树与
逐命令结果，双方各自声明释放写权。H03/H04 定向反例先收口，再由窗口三在同一冻结组合
中验证同一真实绑定 child 的 terminal + accounting、受影响 H01/H02 和兼容全套，最后
交 LEAD 裁决 Gate-H。当前 52/48/4 只保留为历史结果，不重复跑未变化套件等待变绿。

LEAD 的 [本轮证据核对与派工记录](/tmp/c2p-dsh-h03-fix-qa-handoff-20260928-pnh4hbws/review.json)
保留报告、探针与日志摘要及上述范围限定；仅更新执行文档/台账，不代改代码或执行产品测试。

[返回执行入口](README.md)
