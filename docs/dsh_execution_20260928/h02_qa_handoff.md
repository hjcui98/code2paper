# H02 第二轮候选交付：窗口三正式验收指令

> 2026-09-28，历史交接与裁决链。本文 §1–8 保留各轮指令、身份及当时状态。
> **当前 AT-H02 PASS、H02 done、接口 frozen，H03/H04 已放行，见 [最终裁决](h02_acceptance.md)。**
> 下文等待/收口状态不再代表当前进度；§6、§8 的 H04 行为约束继续适用。

## 1. 接收的是第二轮候选，不沿用准备期的过时状态

LEAD 只读核对当前文件与窗口一报告相符，构建 `src_inputs` 与源码一致，staging 回执绑定
当前构建回执。完整摘要见
[`identity-check.json`](/tmp/c2p-dsh-h02-qa-handoff-20260928-lf0mmsvc/identity-check.json)。

| 对象 | 第二轮候选身份 |
|---|---|
| `session-binding.ts` | `86cf5bcff5b0ecac93ad6dcabbe253ec0d227b321399d56ffe3a5b5c2b7849ed` |
| `role-dispatch.ts` | `466fba99010f227e5d2229b583f52f037d91ea2ab131900a9ccf0172aa777183` |
| `request-contract.ts` | `d133fc43dc58909b7b300c90edc989cdac4cbc233ba46bd0d34fb804bd7341bb` |
| `binding.test.ts` | `5f37582ec9b1862e25a0c2692f1c7c1cfda504ad621786b91e80878a89627772` |
| 接口候选记录 | `84321b6aa4d5bb051cdd4b62b930de5bb122593a9210d8ebf53ce3067c3a89d1` |
| 构建回执 / outputs | `03c7ccff…` / `c3b63c29…` |
| staging 回执 / staged 文件树 | `9baa607d…` / `3c9a706b…`，14 文件 |
| package / lock | `165d4452…` / `6a747c1d…`，本轮未变 |

窗口一报告 `check:compat` 27/27（11 H02 + 10 H01 + 6 工具链），LEAD 没有代跑。
旧候选的 23 项及更早 H01 的 16 项是各自实验身份，不能混算或要求当前总数仍为旧值。

窗口三准备期的 D1（caller 与新增符号缺失）已在新文档中有相应修订；静态可见不等于正式
关闭，仍由双消费者与 C-H02-14 确认。L1–L4 记录为“实现者报告修复，待独立验证”。

**接管前置是候选输入停止变动，不是 `interface_status=frozen`。** 窗口三原计划要求先批准
接口冻结再验收，会构成循环依赖。当前候选允许正式复核；只有 QA PASS 且剩余合同问题
收口后，LEAD 才登记接口批准冻结。窗口一释放写权不等于单元已通过。

## 2. 窗口三按修订后的验收口径执行

以 [QA v2 计划](/tmp/c2p-dsh-h-qa-w3-20260928/reviews/H02_delta_review_plan.md) 的
**C-H02-1…14 + S1–S5** 为基础，在自己的证据根修订并冻结探针，不回退到 12 条旧矩阵。
以下是本轮必须校准的口径，不增加 H02 对后继 H04 的依赖：

1. **双消费者均应与当前真实类型一致。** 重新依据本轮文档生成 consumer-doc，不把旧
   `caller` 反例原样当成新文档消费者；旧失败样本作为历史对照保留。正式验收不能继续用
   `--expect-doc-fail` 作为通过条件。新增 recorder 的实际 TS 方法是 `markUnknown`；
   `request.mark_unknown` 只是先前交接的语义名称，不要求增加第二个别名。
2. **C-H02-7 按取消阶段断言。** claim 等待/回执竞态可为 `claim-aborted`，取得回执后进入
   创建阶段为 `creation-aborted`；两者都要求相应的零副作用/回滚。不要给所有阶段写死一个码。
3. **C-H02-8/9 在 H02 验合同可消费性。** 受控 recorder 的顺序、错配/过期/拒绝/取消可测，
   未绑定主体不能取得授权；真实 `llm/stream → next → adapter` 计量接线由 H04 证明。
   H02 尚未安装请求 middleware，不能要求“执行工具自动产生 request 账本事件”才通过。
4. **C-H02-11 分开前置拒绝和失败清理。** stock spawn 必须在 start 前拒绝；当前实现者的
   backstop 测试只返回无 localAgent 的合成 run，不能据此推断真实 child 已释放。QA 诱饵
   应带真实受管理 child，观察处置、registry/绑定及活动状态，保留 dispose 失败的具名结果。
   协议字符串是 Host 组合中的声明，不是创建期绑定已被证明的凭据；若诱饵在绑定之前已经
   投递材料/开始执行，单列为时序问题，不能因最终清理成功就把前置硬门判为通过。
5. **S1/C-H02-14 还应核对示例生命周期。** 新候选文档 §5 把 `root.dispose()` 放在后续
   `requests.reserve(requestBindingRef(root.binding))` 之前；该顺序不能作为“活跃绑定下发送”
   的示例。将此静态发现登记为文档问题，验证消费者应按明确的完整生命周期执行。
   不要求窗口一在 QA 正在运行时抢改文档；先汇总，再定向交回 owner。

执行顺序保持：身份/探针清单 → 独占 `check:compat`（合法构建写入单列）→ `snapshot2 before`
→ 双消费者/机制对照/独立反例/`test:compat` → `snapshot2 after` 分类比较 →
`stage --check`、doctor、身份复比、patch hygiene → `verification.json`。
每条命令分别记录退出码。未变化且与本候选无关的 Python/完整离线套件不机械重跑。

允许构建阶段重建生成物，但内容身份应可复现；**build/stage 不必然改变内容摘要**。
测试观测窗口内，受保护共享输入的同字节重写仍作为 `meta_only_changed` 具名报告。
QA 准备工具先定稿再取 before 快照；测试运行中不改受测输入或冻结探针。

## 3. 对窗口二附件的裁决

附件基于旧候选；其中“request-contract.ts 不存在”已经过时。保留 prepared 惰性 config
检查、messages/tools 不在 `callConfigEquals` 内等特征发现，仍须与真实 loop 集成分开。

### 3.1 可信来源由运行时权威证明，不能靠接口名称

`SessionBinding` 和 `RequestBindingRef` 都是结构化接口。把参数类型换成前者，不能保证
同形状对象无法构造；类型断言也不能生成授权。允许 Host 派生可序列化引用，H04 必须从
真实调用 scope 和 `SessionBindings.requireCurrent()` 取得当前绑定，校验 session/task/
epoch/fence/claim/composition 关系，再提交 recorder；不把模型字符串或回执自报字段当来源。

现有 `assertRequestBindingCurrent` 只比较 fence，是局部谓词；`parts` 包含三个名称也仅是
摘要覆盖声明。两者不能独立充当完整身份校验或载荷重算。QA 区分 helper 的真实保证与 Host
硬门，H04/生产 authority 必须补足调用链上的校验，不新增平行授权账本。

### 3.2 发送状态由可证实的阶段决定

不要求仅为返回 `{ok:false}` 而重写已经可消费的 Promise/`RequestRejection` 合同。明确拒绝
与传输异常/迟到回执要区分；某个新请求在 next/adapter 之前终止，可用控制流和独立计数证明
本次零派发，不依赖错误对象里写一个 `not-sent` 标签。该证明不能推断旧尝试或远端请求未发送。
进入发送边界后无法确认结果时保持 unknown，不退款、不自动重发；持久恢复仍由 R02/R03。

### 3.3 附件代码是讨论草稿，不是可直接复制的消费示例

草稿 `requestRef` 声明为字符串却读取 `.digest`，没有调用 `recorder.dispatch` 就 `next()`，
拒绝时静默结束流，并缺少中断迭代时的完整清理。因此不得将它标记为已编译、已满足顺序。
窗口二须基于本轮真实类型重写消费者；在所有拒绝/中断分支保留具名失败和结算/unknown 事实，
先 dispatch 回执、再委托，正确结束 iterator。实际 middleware 仍等 H02 通过后实施。

### 3.4 静止结论要写明资源范围

H02 的 dispose/whenIdle 只覆盖其声明的 Agent/handle 活动，不自动证明 HTTP 请求、工具子进程
或 provider 的全部资源退出。`subprocess.waitForExit` 是托管子进程的观测方式，不是所有
资源唯一的通用证明。没有启动此类子进程时可标该项不适用并记录资源清单；若有应观测资源
却无法观测，保持相应阻断。mock adapter 的请求结束/取消需由 adapter 自身的可观测行为证明，
不能因环境没有 subprocess 就把整个 H04 永久阻塞。

## 4. 该次验收的写权和交付（已结束，当前以 §5 为准）

| 窗口 | 本轮指令 |
|---|---|
| 三 | **接管正式 QA 及独占构建窗口**，先落实 §2 的计划校准，再取基线、执行并提交完整 PASS 或具名问题；不修改产品实现/接口候选文档 |
| 一 | 保持本轮源码、测试、接口文档、配置与生成物冻结；不 build/stage，不开始 H03。等 QA 汇总后，若有缺口再按交接接回写权修订 |
| 二 | 按 §3 只读审查已交付真实类型、准备 H04 消费方案；结果通过报告交 QA，不写共享输入、不运行与 QA 冲突的环境探针、不开始 H04 实施 |
| LEAD | 本轮规划记录写完后释放执行文档写权；QA 快照窗口内不更改覆盖输入，不代修实现或代跑产品测试 |

QA PASS 后才最终裁决 H02，放行 H03/H04 的文件域并行。若有问题，保持 review/具名缺口，
收集完整后一次交回 owner，修订后重验受影响场景；不靠重复次数或测试数量批准接口。

## 5. 正式证据复审：不采纳 I2 为非阻断项，定向交回窗口一

### 5.1 已核对的证据及最终裁决

窗口三的 [H02_verification.json](/tmp/c2p-dsh-h-qa-w3-20260928/reviews/H02_verification.json)
摘要为 `921ba816cbcf9ce6c3e6f77284dfb0bf369f13632b68210ed39263f38adfb57a`。
LEAD 只读复算其 16 项候选输入，以及 21 个日志/记录/最终 QA 工具引用的摘要，全部一致；
核对记录见 [evidence-review.json](/tmp/c2p-dsh-h02-gate-review-20260928-6jm6yv7n/evidence-review.json)。
没有代跑产品测试、改候选或改 QA 原报告。

保留真实窄 provider 创建期绑定、旧父拒绝、合同消费、隔离/类型/清理等已通过证据。
但 QA 的整体 PASS 与同报告 I2 的实际观测不相容：

```text
C-H02-11:
stockSpawnRefusedBeforeStart = true
decoyDisposeCalls = 1
decoyPromptDeliveredBeforeBinding = true
```

原始输出在 [binding_final.log](../../.dsh-dev/run/qa-w3-20260928/h02-recheck/freeze/binding_final.log)。
探针的诱饵通过真实 `agents.create` 创建 child，并在返回 run 前 `followup(prompt)`。
当前 `isBoundDelegationProvider()` 只比较公开 `bindingProtocol` 字符串，故诱饵通过前置检查；
`dispatchRole()` 后续才 dispose。它证明了**事后清理有效**，也复现了**绑定之前材料已投递**。
dispose 不能撤回此前的材料或执行。§2.4 已明确两者不可互相折抵，这不是新增验收要求。

**LEAD 裁决：CHANGES_REQUESTED。** H02 回到 `in_progress`，接口不批准冻结，H03/H04 保持
planned。I2 为 H02-L4 尚未收口的阻断项；I1 同轮修正。QA 的成功日志与其他已通过事实保留，
不因该判定分歧推翻全部工作，也不把 9/9 的测试通过等同于满足全部不变量。

### 5.2 窗口一：仅收口 I2 与 I1

I2 修现有 `role-dispatch.ts` 的 provider 准入 owner，不改冻结 DSH、不在 H04 补救这个入口：

1. 在进入 `subagents.start()` 前，核对**本 Host 正式注册的 provider 对象及其所归属的
   SessionBindings**。公开字符串、包名、自报字段或类名只能表示协议意图，不能独立授权。
   可由现有注册 helper 建立模块私有的对象登记/能力引用，dispatch 查询同一登记；这是
   进程内执行对象归属记录，不是第二套持久任务权威或预算账本。
2. 只贴相同协议标签的已登记诱饵、错误 bindings 的 provider、被替换/已撤销的注册必须在
   start 前具名拒绝。合法默认名和合法自定义名保留成功对照。保留现有公开签名优先；确需
   改签名时同步真实消费者及接口记录，再通知窗口二。
3. 直接沿用已复现的诱饵作为修前反例。修后要求 `startCalls=0`、prompt 投递 0、新 child 0、
   child claim 0、adapter 0；不能只断言最终 reject 或 child 已销毁。保留已准入 provider
   出错后的 backstop 清理，用单独故障场景证明，不为测试给生产入口增加绕门开关。
4. I1 只修接口文档生命周期：在活跃 root/binding 下完成请求示例，最终在完整清理路径
   dispose；异常分支不泄漏。更新文档身份，旧 `84321b6a…` 仍是第二轮 QA 历史证据。

owned paths 仍为 H02 已分配的 `src/role-dispatch.ts`、`tests/binding.test.ts`、接口记录；
若确需协同 `session-binding.ts`，限绑定对象归属边界并说明。request 合同无需因 H04 草稿而
重写。完成后重新 build→stage→test，交付受影响反例、真实类型消费者、完整新身份与写权释放。

### 5.3 窗口三：保留证据，修正判定并做针对性独立复验

原 `H02_verification.json` 与首次失败/成功日志不改写成另一场实验。增加判定修订记录，
将 C-H02-11 拆为“未获准 provider 零启动”和“已获准 provider 失败后清理”，前者不能由
后者通过而通过。新候选到达后重点验正式登记/归属、协议仿冒、注册替换/撤销、合法自定义名、
清理、I1 文档消费者及共享输入不变；完整 `check:compat` 覆盖 H01/H02 相关回归。
未受影响的机制证明、旧 Python 套件不要求重新全跑，更不要求整套机械重复多遍。

当前写权交窗口一，窗口三准备修订后的独立用例；再次交付后才接管构建/运行窗口。
I2/I1 关闭且 LEAD 批准后，按已定依赖放行 H03/H04，不重新讨论整体架构。

## 6. 窗口二：H04 消费草稿继续校准，不新增 H02 工作包

最新附件已使用真实 `RequestRecorder` 签名，方向与资源范围说明可保留；仍是未编译、未执行
的设计草稿。本轮仅只读修改方案并反馈，不写 `request-accounting.ts`。以下按现有 AT-H04
准备反例，不能把草稿直接标为已满足硬门：

| 草稿问题 | 必须落实的行为与反例 |
|---|---|
| `sessionId` 缺失或 `isProtected` 为假就 `next()` | 受保护范围由可信 Host 组成/任务 scope 决定；受保护来源的缺失、伪造或越域 sessionId 必须拒绝，不能靠请求自报 ID 退出计量。裸 API 特征组与受保护组明确隔离 |
| 文字说 direct/fallback 拒绝，代码无该判断 | 通过真实 loop + 已登记 mock adapter 证明 prepared 通路，验证 direct/NO_ADAPTER 不能绕门；标记、冻结或模型路由字符串都不能各自当 prepared 的证明 |
| `assertReservationMatches(reservation, {reservation, digest})` 未检查返回的 `DispatchReceipt` | 独立核对 reserve 与 dispatch 的实际返回回执：合同版本、request/reservation 身份、可信 binding、digest、阶段；错配回执在 next 前拒绝。不能将本地请求与自身比较当回执验证 |
| 等待 dispatch 时仍可能取消、绑定过期或请求漂移 | 最后一次异步回执之后、调用 next 之前重新检查取消、当前绑定和实际请求摘要；每个等待点布置延迟/推进 fence/修改材料反例。next 后的检查不能代替这道检查 |
| `maxTokens ?? 0` | 未知输出上限不能伪造为 0；使用已解析且与合同一致的上限，否则具名拒绝。估量有明确版本/来源 |
| next/iterator 创建在 try 外，提前 return/异常跳过尾部 settle | 覆盖 next 抛错、迭代器创建/迭代抛错、调用者 break/return、abort、return 清理抛错或超时；按可证实阶段完成有界清理及一次终态记录，不能静默丢 settlement/unknown。记录本身失败也保持具名未结算，不自动重发 |
| 正文资源范围正确，但 C1–C5 表仍写“只用 waitForExit，无范围即阻断” | 统一为 adapter 请求由 adapter 观测、真实托管子进程由 waitForExit 观测；未启动该类资源可具名不适用，应观测而不可观测的范围才阻断 |

mock adapter 对实收材料的观测必须保留，它是测试 oracle，不可在测试里独自实现生产包装层
本来缺失的拒绝逻辑来使测试通过。完整消息/工具/config 摘要与 middleware 时序由 H04 实现；
最终 provider wire 校验、Python 唯一账本和 durable unknown 恢复仍归既定 C/R/V 单元。

## 7. 第三轮复核后的最终文档收口指令

### 7.1 I2 关闭，代码与相关运行证据保留

LEAD 读取 [QA 判定修订记录](/tmp/c2p-dsh-h-qa-w3-20260928/reviews/H02_verification_revision.md)
及 [第三轮独立日志](../../.dsh-dev/run/qa-w3-20260928/h02-recheck/freeze3/recheck_l4.log)，
复核后者摘要 `942ee0cadecfe21c1a0eb8e7433f3d9167c60a4fc4d1d7897acc5d6130e0a9fb`、
其绑定的 runner 输出/探针摘要及 R-1…R-5 结果。未重跑产品测试。

**接受 I2 关闭**：未经 helper 登记的协议仿冒对象零启动/零投递；错误绑定归属、撤销和
同名替换均前置拒绝；合法自定义名仍在公告前绑定；已准入 provider 创建期取消无残留。
当前实现与该轮证据一致：session-binding `404f7984…`、role-dispatch `c8758e10…`、
binding.test `59835929…`、request-contract `d133fc43…`、构建回执 `989b2076…`、
staging 回执 `a44dec24…`。H02 代码本轮不再要求修改。

### 7.2 I1 必须按当前文档字节判断，不能沿用旧块的偏移

LEAD 的 [只读核对记录](/tmp/c2p-dsh-h02-i1-closeout-20260928-khtbt3nc/review.json)
确认了同一轮记录中的版本差异：

| 观测位置 | 文档 `h02_interface_freeze.md` 摘要 |
|---|---|
| `freeze3/freeze.txt` 开窗 | `cfdb9e8aab92f0f5b19aa0aa4e60a14c47ba3905232a7680c488ffbf9ca7cb28` |
| 实际 before/after 快照及 `identity_after.txt` | `314bfd69e9f2dbc0588205850425510134ac25af98a772d3ac8fd0e2411b0d18` |
| 本轮当前磁盘读取 | 同上 `314bfd69…` |

`UNCHANGED` 证明的是 17:43:09–17:44:09 的快照区间内字节及元数据不变，不能推出整轮文档
一直为 `cfdb9e8a…`。代码/测试/构建身份未受这处文档差异影响，I2 不重开。
当前 §5 示例块为 1475 字符，reserve 位于 872，root.dispose 位于 1451；**先请求、后释放
的顺序已正确**。QA 报告的 1389 字符、755/929 偏移属于另一版本，不能用于判当前文件。

当前 I1 剩余的是先前要求的**异常分支完整清理**，静态可见两处：

1. `dispatchRole()` 位于 `try` 外；root 已成功创建时，委派失败会跳过 root 的 finally。
2. 同一个 finally 先 `await run.dispose()` 再 `await root.dispose()`；前者抛错会跳过后者。

这两项仍属于 I1 示例生命周期，不是新的生产实现缺陷，也不要求新增产品模块。

### 7.3 窗口一：只改接口文档的示例，随后立即释放写权

唯一修改目标为 `docs/dsh_execution_20260928/h02_interface_freeze.md` §5：

- 获取 root 后立即进入保证 root 清理的外层 try/finally，将 `dispatchRole` 放在该作用域内。
- 获取 run 后使用内层清理作用域；run 清理失败仍要尝试 root 清理，异常不可被静默吞掉。
- reserve/dispatch/settle 位于相应绑定活跃期间。准确说明这是 H02 的合同消费示例；真实
  模型请求计量发生在 H04 的 loop middleware，不能以 run.result 后调用 mock 账本冒充发送门。
- 只改必要示例及其说明。完成后**重新从磁盘读取**该 §5 代码块，计算整个文件及代码块摘要，
  确认所交付内容与声明一致，关闭持有旧缓冲区的写者，再交回窗口三。

禁止借此重写 TS 接口、源码、测试、lock 或构建产物。本轮不执行 build/stage/check:compat、
smoke 或 Python 套件。该文档不是 bundle 构建输入，不必为它重建。

### 7.4 窗口三：只复核该示例与版本绑定，不重跑已通过集合

新 I1 证据使用独立目录，保留旧报告及 freeze3 原始字节。收到文档后：

1. 先登记文档全文摘要、§5 代码块摘要及长度，确认与窗口一交付相同；按当前块检查，避免
   复用旧 consumer 或缓存输出。修订记录明确上述开窗与快照身份差异，不再声称整轮同一文档。
2. 编译当前示例的真实类型消费者，定向验证：正常结束；`dispatchRole` 拒绝仍清理 root；
   `run.dispose` 抛错仍尝试 root 清理；请求调用失败仍进入相应清理。此处可用独立消费者
   注入失败来验证示例控制流，不重新启动 DSH 或制造模型请求。
3. 再核对文档/受保护代码与构建摘要、patch hygiene；若只发生预期文档变更，引用第三轮
   既有运行证据，出 I1 CLOSED 与最终 H02 PASS。不要把已被取代的旧 C-H02-11 期望当回归。

LEAD 收到与最终文档身份绑定的 PASS 后登记 H02 done / interface frozen，按既定任务卡放行
窗口一 H03、窗口二 H04 并行。当前状态仍是 H02 `in_progress`，仅剩文档收口。

## 8. 窗口二附件中的合同澄清裁决

以下澄清接受为 H04 的实现约束，不修改 H02 的请求合同，也不再要求窗口二反复重写整份方案：

- **DispatchReceipt 没有 binding。** 先验证 reservation 中的可信 binding/digest，再将
  dispatch 的 requestId/reservationId/版本/digest/stage 链回该已接受 reservation；不能读取
  不存在的字段。校验依据是已接受的稳定快照，不能在等待期间被回执对象的后续改写替换。
- **估量版本与来源由 H04 包装及证据记录承载。** RequestEstimate 本体保持不变；后续生产
  C/R 接线仍须把来源与本次请求关联，不把 TS 包装当持久余额。
- 三值 scope 分类、默认拒绝、独立裸 API 特征组可采用；判定要能观测实际可信调用来源。
  用请求自报 sessionId 查询 Host 表仍不足以证明来源，R-scope 必须覆盖冒用现存 protected
  和 excluded ID。`bare-excluded` 是 H04 诊断事件，不是现有四方法之外的 recorder 方法。
- 最后一次回执等待后的复核、未知 cap 拒绝、返回回执校验、资源范围区分及不带拒绝逻辑的
  mock adapter 观测均保留。direct/prepared 路径的实际可观测性由 H04 实验说明，不能只靠标记。
- finalize 负责一次本地终态记录尝试及有界清理，不声称 durable exactly-once。调用
  `inner.next()` 或收到迭代异常不自动证明 `adapter-entered`；lastStage 只使用确实观测到的
  阶段。缺失 finish、调用者 break 或 abort 不能自动转为成功结算，无法确认时保留 unknown/
  unsettled；持久裁决仍由 Python 权威负责。

窗口二继续只读准备，待 H02 最终批准后直接按已有 owned paths 实施与验证。

[返回总执行入口](README.md)
