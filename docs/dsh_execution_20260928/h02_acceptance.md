# H02 最终验收与 H03/H04 并行实施指令

> 2026-09-28，LEAD：**AT-H02 PASS，H02 done，interface_status=frozen；H03、H04 ready。**
> I1、I2 均关闭，窗口一/二可按下列责任文件直接实施，窗口三独立复核。
> 本次仅审查证据、登记裁决和派工；未修改实现或受测接口文档，未运行产品测试/构建。
> Gate-H 尚需 AT-H03、AT-H04；本次不批准业务接入、模型 live 或默认切换。

## 1. 受测身份与裁决依据

冻结的消费者合同为 [h02_interface_freeze.md](h02_interface_freeze.md)。批准状态由本文及
[task_board.json](task_board.json) 登记，不为添加状态文字改写已受测的接口文档。

| 对象 | SHA-256 |
|---|---|
| `src/session-binding.ts` | `404f7984d01b51073a6f8f5941f56c9f594161be563a215f09b4ff2403348952` |
| `src/role-dispatch.ts` | `c8758e10565531f36ca8e3c4732ac919f559209ef9869deeb13fe2a8100999b4` |
| `src/request-contract.ts` | `d133fc43dc58909b7b300c90edc989cdac4cbc233ba46bd0d34fb804bd7341bb` |
| `tests/binding.test.ts` | `598359297f6e671ee82a3aa451d4513854c8fc4321fd33dc9a2d8039c6be9005` |
| 最终接口文档（29,677 bytes） | `0ba7f1ce88e834706bae45039ab934c4e42ffde23119da96a747b01a7345e9c5` |
| 构建回执 | `989b2076c99305dc6894a0d71a5fd741e95211ecb207e55ffb3c1a080ebddd95` |
| `outputs_digest` | `4a0dd15f612725ae6d6ee0f9eaca968883668aa12f3d38c8c6f21d283d17ceb5` |
| staging 回执 | `a44dec24da94ec8a33637a06dce65d2c64eda1d43735d8207c3fbde0d897c7ac` |
| staged 树（14 文件） | `525f0b45dd5c049f5ed70c2a27ec18ccfcc69a711ed498aa9a57e39a3352aa36` |
| 冻结 runtime，DSH `0.1.5-rc.3` | `7e8f199b67027944d646e0c99f5041d4704360377e4d7466fce683c1d468d3ab` |

窗口三 [追加复核报告](/tmp/c2p-dsh-h-qa-w3-20260928/reviews/H02_verification_revision.md) §7
的本次读取摘要为 `1505e56315d84918bca5d3e8626aac859de2cfbf168f9955d7fb7ddfd35e037e`。
LEAD 的 [只读复算记录](/tmp/c2p-dsh-h02-acceptance-20260928-g7a2s_v2/evidence-review.json)
核对了 12 个日志/探针/报告引用、50 个源清单文件及全部 14 个 staged 文件；受测字节相符。
本次规划文件更新发生在 QA 释放窗口之后，不回写 QA 原快照或历史结论。

| 证据 | 本次采用的结论与范围 |
|---|---|
| I2：provider 准入 | 第三轮及最终 R-1…R-5 独立结果 5/5、exit 0；仿冒对象零 start/prompt/child/claim/adapter，错误归属、撤销/替换前置拒绝，合法自定义名创建期绑定，创建取消无残留 |
| I1：示例生命周期 | 最终文档消费者和实际导出消费者均编译 exit 0；`example_lifecycle_issue=false`。LEAD 静态核对外层 root、内层 run 的 `try/finally`，请求发生在绑定活跃时；委派失败、请求失败及 run 清理抛错仍进入外层清理 |
| 机制与原绑定反例 | 机制 M1–M5 为 5/5、exit 0；旧绑定探针为 8/9、exit 1，唯一失败是已被取代的 C-H02-11 后置拒绝期望。该日志不标全绿；其要求由前置零启动 R-1 与已准入故障清理分别取代 |
| 构建及实施套件 | 采用第三轮 `check:compat` 27/27、exit 0，构建内容可复现；最终只改文档，不重跑这套或未受影响的 Python 套件 |
| 保护与身份 | QA 最终前后快照字节和 inode/mtime 清单均 UNCHANGED；只读 `stage --check` exit 0；代码/测试/lock/构建与第三轮一致 |

I1 的新增证据是当前消费者类型检查及嵌套 finally 控制流审查；不声称另外运行了三种故障注入。
此次简单文档修订以这些证据关闭，不追加产品测试。§5 代码块去掉末尾一个 LF 后为 1,602
字符，摘要 `e3ead04eeb53ef77945f9cfda9174379550c8f2a0e719449c9ea0a50a0e5d7dd`。
它是合同消费示例，不是 H04 的发送前计量门。

第二轮文档 `84321b6a…`、第三轮开窗 `cfdb9e8a…`、第三轮实际快照/交付 `314bfd69…`
保留为历史身份；最终消费者绑定 `0ba7f1ce…`。不把不同版本的偏移、编译结果或测试数量合并。
H01、B00/B01/B02 历史证据保持原样；Python 持久账本与生产 claim 仍由 R01–R03 接线复验。

## 2. 立即派工与写权

共同依据：[第 01 部分任务卡](01_baseline_and_dsh_compatibility.md)、
[实际接口](h02_interface_freeze.md)、[运行时约束](h02_h04_handoff.md)。
[前轮 QA 指令](h02_qa_handoff.md) §6、§8 的合同澄清继续适用；其中“等待 H02”的状态文字
已被本次放行取代。无需再交一轮同内容方案，按下列范围实施并交证据。

| 窗口 | 本次责任 | 独占实现文件 |
|---|---|---|
| 一 | H03：terminal、来源、flush/重启恢复 | `integrations/dsh/src/terminal-result.ts`；`integrations/dsh/tests/terminal.test.ts`；`integrations/dsh/tests/provenance.test.ts` |
| 二 | H04：请求计量、scope、prepared/direct、取消与静止 | `integrations/dsh/src/request-accounting.ts`；`integrations/dsh/tests/request-seam.test.ts`；`integrations/dsh/tests/cancellation.test.ts` |
| 三 | 独立 H03/H04 反例及 Gate-H 复核 | 自己的任务 run 根内的探针、快照、日志与报告，不代修实现 |
| LEAD | 冻结接口、共享路径分配、证据裁决和台账 | 执行文档、任务表及工作记录，不代写实现 |

H02 的三个源码文件、绑定测试和接口文档现在是只读消费输入。H01 的入口、工具、preset，
以及 package/lock/工具链等共享路径仍由原 owner 管理。确需接线或增加 peer 时，先列具体
调用点、最小 diff 与受影响任务，由 LEAD 分配一次写权；不新造平行入口或绕过真实调用链。
其他窗口的未提交改动是共享基线，不覆盖、不回滚。

## 3. 窗口一：实施 H03

1. 在真实 DSH Agent/工具通路上验证最小 terminal fixture。先试 object 根下 `result.oneOf`；
   若运行时子集不支持，给出等义 adapter 及反例，不删除 required/extra/union 等领域约束。
   H03 只证明兼容表示；完整 Python 结果模型及生产 ingest 仍归 C01/C03。
2. 分开记录 arguments delta、normalized terminal、parsed 及 prose 的来源与摘要。
   空白、转义、键序变化须能区分；`JSON.stringify` 的重建结果不能冒充 provider raw。
   没有观察到的来源标缺失，不以 closing text 补正文或替代 terminal。
3. 验证成功 terminal、双 terminal、坏 schema/参数、terminal 后工具及 fallback provider 的
   实际停止/拒绝行为。只通过公共 API 接入，不替换 loop factory。
4. child 释放前等待 `sessions.flush()`，确认真实持久 listener 和已落盘字节；通过重新启动
   的消费者从这些字节重建。内存对象、whenIdle 或 turn-end 不替代持久恢复证据。

交付每条 AT-H03 的真实调用路径、来源分类、最小反例、恢复结果、精确命令/退出码和文件摘要。
遇到确实不可满足的公开 API 能力，交具名实验结果由 LEAD 裁决，不修改冻结 runtime。

## 4. 窗口二：实施 H04

最新消费方案接受，以下作为实现与独立复核要点，不要求再改 H02 合同：

| 边界 | 必须落实的行为 |
|---|---|
| 可信来源 | 优先实验 Agent scope 注册的真实可观测范围：自己的派发被观察、兄弟/裸 Context 不误入、外部冒用现存 protected/excluded ID 无法获得该来源身份。注册点取定 session；请求 `sessionId` 只用于比对，不能用于取得授权或退出计量 |
| scope 能力不足 | 不假设 Cordis 注册天然隔离。若实验不成立，报告最小能力缺口和公开接口方案；不降级为请求自报 ID 查表，不改 runtime |
| 回执快照 | 接受 reserve 时逐字段复制并冻结 H04 自有快照，包含 binding、digest 及 parts；后续 dispatch 只与此快照比较。保留 R-receipt-7：等待期间改写原回执不能替换已接受的依据 |
| 合同关系 | 实际方法为 `reserve/dispatch/settle/markUnknown`。DispatchReceipt 不增 binding 字段，凭版本、requestId/reservationId、digest、stage 链回已接受 reservation；`bare-excluded` 仅写 H04 diagnostics |
| 发送前复核 | 每个异步等待后的取消/fence/材料反例均覆盖；最后一次回执等待结束后、next 前重查当前绑定、abort 与实际 messages/tools/config 摘要。再证明 next 后至实际 adapter 入口材料不漂移 |
| prepared 与裸路径 | 保留 prepared 配置/单次 dispatch、直接 stream、NO_ADAPTER 回落及闭包代次对照。标记、冻结、模型字符串不能单独证明 prepared；mock adapter 只记录实收事实，不替包装层实现拒绝逻辑 |
| 估量 | 使用有效上限，未知 cap 具名拒绝。版本和 cap 来源由 H04 包装/诊断与本请求关联，RequestEstimate 不扩字段，TS 不维护持久余额 |
| 终态与清理 | next、iterator 创建/迭代、return/break、abort、清理抛错/超时及 recorder 失败全部纳入有界处理；一次本地终态记录尝试不声称 durable exactly-once。lastStage 只用实际观察，inner.next 不等于 adapter-entered |

finish/usage 齐全只支持对应请求事实的结算，不证明领域通过或 provider 已静止；缺失 usage
保持缺失。未知送达、终态不足或清理失败不得转为成功/退款/自动重发，保留 unknown/unsettled，
持久裁决归 Python。`dispatch-recorded`、next 和 adapter-entered 均不等于 HTTP 已送达。

按最新矩阵落实 R-scope-1…6、R-prepared-1…3、R-receipt-1…7、R-wait-1…6、R-cap-1…2
及 C1–C5；另保留 prepared 重用/漂移、next 后漂移和 retry/title/compaction/PTC 四项禁用的
行为证据。adapter 请求和托管子进程分开观测；子进程 `waitForExit` 使用独立有界 cleanupSignal，
仅 true 证明相应范围静止。未启动该类资源可具名 not-applicable；应观测而不可观测则阻断。

## 5. 窗口三与共享构建安排

窗口三现在并行准备 H03/H04 独立反例，按真实导出类型编译消费者。H03 重点为来源真实性、
终态拒绝及落盘恢复；H04 重点为实际 scope、等待期间漂移、稳定回执快照、无违规派发及取消后
真实静止。实现者仍在写入时只做准备，不对移动输入出正式验收结论。

共享构建协调者先指定为**窗口一**，与窗口二约定可编译的检查点。两边必须先暂停修改受测
src/tests/config，再由一人执行 typecheck/build/stage/check:compat；共享测试同样不能与输入
修改并行。没有可编译的共同检查点时，继续各自编码或只读调查，不对半写状态反复构建。
单写者是构建期间的输入冻结规则，不仅是避免同时启动两个 build 命令。

交给窗口三时，声明源码/测试集合、lock、构建回执、outputs、staging 回执/树和接口文档身份，
并释放写权。正式顺序：核对候选 → 必要的独占构建（单列其写入）→ snapshot before → 独立
反例及受影响套件 → snapshot after（字节与 inode/mtime 分类）→ 身份复比/只读 stage 检查 →
具名裁决。CLI/smoke 等可能写 profile 的动作与“不变输入”验证区间分开。

两个单元可以分别交付，但每轮验收必须说明实际包含的双方输入；最后按同一组合候选复核
H03/H04 的接线与 H01/H02 回归，均通过后再交 LEAD 裁决 Gate-H。旧失败日志保留，已取代的
断言要明确映射到新边界，不能计成通过或通过跳过仍有效的要求来变绿。

只用既有隔离 runtime 和无网络 mock；保留日常 DSH 不变，不自动提交、推送或执行 live。
工程窗口并行不改变产品 Agent 并发开关，产品仍按既定设计默认串行。

[返回执行入口](README.md)
