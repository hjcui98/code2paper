# 能力门控候选独立差分复核与整包接续（2026-10-02 14:48）

本批结论：**Gate-H 仍 CHANGES_REQUESTED，正式 Gate-K 未通过。** 当前继续执行原
[第 01 份](01_baseline_and_dsh_compatibility.md)，行为合同仍为
[接口裁决 §6](h04_loop_origin_escalation_20261001.md)。本报告补充候选差分与派工，
不增加执行阶段、任务或验收门；原 8 份文档、49 个任务对象和所有 AT/依赖不变。

## 1. 实际身份与复核范围

| 对象 | 本批实际 SHA-256 |
|---|---|
| 交付 runtime | `0adaffc80805256ea2ac6fe23ad30d6c395cbd7c30d9623d83b7669b27d0b192` |
| 源码构建 runtime | `dcf6965805225e788ea919284be88f6def54d419ec54e0b6c7c6467035aea109` |
| 原 0.2 runtime | `43490765da460c4300cd7ad8ec75dbc5d5e6dbda93b74e37466c6709c1ab359c` |
| 补丁脚本 | `f1a310cdbdc723bfa2bfe6dabd066c6ac88c87d1d7b6cb51c54f58b7ba5d4625` |
| 源码补丁 | `23ab63505e1e4ce14aba75935b51d2493dbafb3b7b994d07ffaa3184005d43fb` |
| 源码 commit | `4878cdabd87d4041bdaff61d04c966883b9fd07a` |
| Host request-accounting | `12f33263f16a26dc4c85c170e05fe3ce02fadd0cf6cb713db6be1c09d129d810` |
| build receipt | `a6c69d834fe562f333721e5ca9d9bba9f0f05d1100ce3681a2d9f02d0cc35aab` |
| staging tree | `66458c03c5a4be9db28d9a79f4f5569b504c7bea52a0c71ede70784edae28128` |
| build outputs | `2aeceb7bbeb5e18a07ed6d4f01bf7b15c32d0cf9d3a846157c593eebebc1b620` |

源码补丁逐字节等于固定 commit 上四份源码的实际 `git diff HEAD`；两包源码工作树
`lib/index.js` 与 `-built` 实际字节一致。源码侧行为失败不能解释为用了旧编译产物。
本批没有执行 pnpm/tsc/build，也没有切换共享 peer 或重 stage；这些构建命令的成功属于
owner 提交声明。本批独立运行交付原套件和两侧边界探针，不将 owner 的源码侧 87 项声明
写成独立复验结果。

权威根：[`qa-capability-entry-20261002-hum96d19`](../../.dsh-dev/run/qa-capability-entry-20261002-hum96d19/)。
每侧探针拥有直接指向该侧 runtime 的包解析链接，不借交付 peer 测源码候选。

## 2. 独立运行结果与已修部分

| 场景 | 交付候选 | 源码构建候选 |
|---|---|---|
| 合法 prepared child | completed；R/D/S/adapter 各 1 | 同左 |
| 合法 NO_ADAPTER 内部回落 | completed；R/D/S/adapter 各 1 | 同左 |
| 同步 internal/get 观察者：伪造 capability + symbol 派发 | admission 0；攻击具名拒绝；合法 child 各 1 | 同左 |
| 普通公开流的自定义 iterator 获取 | listener、获取均无来源 | listener 无来源，获取看到外层来源；真实失败 |
| 公开服务 resolver 返回转发 Proxy，观察实际 symbol 调用实参 | capability 被消费 1；合法 child error，R/D/S/adapter 全 0 | 同左，真实失败 |
| 新探针总计 | 5 项：4 pass / 1 fail / 0 skip；Node exit 1 | 5 项：3 pass / 2 fail / 0 skip；Node exit 1 |

交付已有 stage 验证后运行原 11 文件套件：**87 pass / 0 fail / 0 skip、exit 0**，
含原 C21 和同 child terminal→settle→flush→新进程 committed 恢复；没有 build/restage。
显式选择本候选的原 B02 目录 **24 passed、exit 0**；只读 doctor **exit 0**；
`git diff --check` **exit 0**。源码构建侧原 11 文件完整套件本批未重跑。

原 PC-1 的公开 entry-ack 已删除；新同步观察者使用当前真实公开 API，伪造值与冻结
snapshot 均不能 admission，攻击流具名 `dispatch_origin_unproven`，合法回落完成。
原 PC-3 已关闭：实际 runtime 差分、候选 manifest、兼容清单与生成器均列齐 2 JS + 2 types。
原 PC-2 仅交付侧关闭，源码/源码补丁/源码构建侧仍失败。旧结论按旧树保留。

## 3. 集中阻塞项

### 3.1 CAP-1：capability 经过公开 resolver 返回的方法，实参可截获

原调用是 `this.loopCtx.llm[loopDispatchEntry](request, preparedCall, capability)`。
`this.loopCtx.llm` 触发公开 Cordis `internal/get` waterfall；listener 调用 `next()` 得到
实际已注册的服务，返回仅转发的 Proxy。在其 symbol 方法包装函数中，第三实参就是
真实来源作用域对象。调用公开 `admitLoopDispatchOrigin(args[2])` 成功，随后转发原方法
时 admission 已被消费，合法 child 进入公开隔离路径并 error。

两侧均实测 resolver lookup 1、symbol wrapper call 1、成功 admission 1，
R/D/S/adapter 全 0；同时各有正常 prepared/fallback 和普通伪造能力观察者的正对照。
该探针不修改 runtime 文件、LLM 服务注册、全局 loop factory 或私有 helper；Proxy 由
公开 resolver 的返回通道提供，原方法使用原目标和原实参转发。

因此“getter/hook 看不到实参”“对象从不经任何公开面暴露”的声明不成立。反例证明的
是实际能力引用泄漏与预消费，不用任意 throw 或 import error 代替来源合同失败；
没有把尚未运行的能力复位/重放推测记为已验证攻击。

### 3.2 PC-2：源码、源码补丁与源码构建仍漏隔离 iterator 获取

源码 `packages/llm/llm/src/index.ts` 仍是
`runIsolated(() => this.ctx.waterfall(...))[Symbol.asyncIterator]()`，获取发生在 runner
返回之后；自己的 `isolatedIterable[Symbol.asyncIterator]` 也直接返回。交付 hunk 已把
获取移入 runner 并隔离自身返回。相同公开自定义 iterable 在交付侧 seesOrigin=false，
源码构建侧 seesOrigin=true；两侧合法 child 均完成，普通 sibling 也实际到达 adapter。
须修源码并重新导出补丁、构建与双侧验证，不能只改 hunk 或引用原 87 项计数。

### 3.3 CAP-2：冻结身份与接口说明尚未统一

实际交付树为 `0adaffc8…`，manifest/inventory/receipt 对应新字节；兼容 JSON 的
`dsh.runtime_tree_sha256`、`_020` 当前身份表/第七轮、evidence 当前表和最新 owner
implementation 仍写 `a010ccdc…`。interface-diff 的源码补丁/源码构建树仍写旧
`419d5a8d…`/`7ae6af55…`；部分正文仍描述已删除的 take/entry-ack 及旧 receipt/staging。
兼容清单里所有 `sources_sha256` 实际匹配，但不能据此称整包统一身份已经成立。
本报告记录实际值，不替 owner 改动冻结 JSON 或伪造旧回执。

### 3.4 CAP-3：另有未结束的源码构建验证，须先由 owner 收尾

首次 closing 发现 4 个相关进程，未登记全局清空；归属核对表明这是此前启动的
`-built` 原 11 文件套件（npm 父进程 2202264；bwrap/Node 2202351、2202381、2202383、
2202448），运行已约 100 分钟，非本轮命令，输出 `/tmp/lo-built2-compat.log`。
该日志快照有 C0 合法 child 失败，没有完整计数/终态退出证明。它不证明当前冻结树
另一次 owner 87 项声明为假，但也不能作为该声明或写权释放的证据。
本批未终止这些进程；不能宣称全局 pending=false，或在其仍读候选时批准重建。

## 4. 一次整包返修：窗口二继续原第 01 份

先收尾属于自己的残留源码侧验证，保存真实命令、日志、退出/资源状态，核对相关
进程退出及 candidate/peer 读集释放；不要修改仍被验证进程读取的 runtime/peer/stage。
原全阶段授权继续有效，无需为普通返修逐缺陷申请权限。

随后连续完成：

1. 兑现原 §6 私有来源合同：真实 capability 不得传入经公共服务解析/属性 getter 返回
   的可包装方法；原生入口与实际 runtime/准备记录的可信绑定由 runtime 自己建立。
   保留 prepared 与 NO_ADAPTER 正例，以及原 Host/Python 权威。新公开面仍不能泄漏、
   消费、复位或铸造来源。若现有 ABI 无法兑现，一次提交具体调用链作方向裁决，不能
   以排除 resolver hook、只认伪造值或改变原合法正例来关闭 CAP-1。
2. 同步修源码与 hunk 的全构造隔离，含 waterfall、自定义 iterable 获取与全部
   next/return/throw；导出新源码补丁，固定 commit/锁，记录实际构建命令及退出。
3. 将本批 5 场景纳入稳定回归，双侧各自解析实际候选，保持全部原 AT/0 skip/正反例；
   同 child 贯穿 reserve→dispatch→adapter→terminal→settle→flush→新进程 committed。
4. 一次最终 check:compat/B02/doctor/卫生核对，核对 manifest 四文件差分，统一新
   runtime/patch/source/receipt/stage/outputs 和当前 API 文档；历史表述明确绑定旧树。
   生存日志先封存至候选外，再重建；冻结完整包并明确释放全部 owner 验证与读集。

独立 QA 到下一个完整冻结包再启动；不常驻循环验收单个 helper。当前 reviewer 没有
实施产品返修、切换 peer、重建候选、跑 live 或登记 PASS。

## 5. 统一进度与后续分工

当前执行 [README §3.14](README.md)：窗口二原第 01 份 B02/H01–H04 仍返修，窗口一
保持原第 02 份 K01–K04 已验 component。791 份原 Python source/test 哈希仍匹配
历史冻结清单，不新开内核返修或重跑 4129 全量。正式 Gate-K 仍等实际 Gate-H。

原任务对象保持 **2 done / 9 in_progress / 38 planned**，不能以代码落地/87 项代替
阶段完成。实际 H 与正式 K 后进入原第 03 份：窗口一 I01/C01/C02–C04 与共享 Python/
validator 单写，窗口二 C00/TS/唯一 buildstage；Gate-C 后原第 04 份
R01→R02→R03→R04→V01→A01→V02，保留 R/V 门和单独 L01 授权。
原第 05–08 份排队，完整主图/live/default cutover 未获准提前执行。

## 6. 证据与收尾边界

- `review_driver.py` 与 `supplement_audit.py` 记录实际命令/审计方法；各命令 `.command.json`、
  `.exit`、`.log`、`.result.json` 记录真实 Node/Python 退出。驱动器返回 0 不代表 Node 成功。
- `independent-case-results.json`、`delivery-audit.json`、`identity-parity-audit.json`、
  `kernel-preservation.json` 绑定场景、差分、身份和 791 份未变输入。
- `owner-log-copies/` 原样保存本次 owner 3 份已归档日志并附摘要清单；14 份旧封存
  SHA-256 全匹配，上一轮两个 QA 权威根未变，不补造已灭失历史证据。
- `closing_release.json` 于 **2026-10-02 14:48:55+08** 仅释放本轮独立复核读集：
  1054 输入字节/metadata、四 runtime 与 peer 未变，本轮命令全部返回、本轮进程 0。
  全局仍有上述 4 个外部验证进程，`released_for_window2_candidate_write=false`；
  窗口二确认其退出后才接回候选写权。首次 closing 失败及 PID 归属核对保留，未隐去。
- 本报告、导航/派工/台账更新发生在本轮读集释放之后；与产品冻结快照分开记录。
  后置文档检查另存证据，不重写 before/after 证明。本轮没有产品或内核修改。
