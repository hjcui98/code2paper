# 2026-10-01 · prepareCall 返回闭包候选差分裁决

**Gate-H仍CHANGES_REQUESTED；内核component PASS保持，正式Gate-K等待。** 本批仅重放上一批
公开调用探针并核对新候选，不修改产品、build、stage或peer。QA已于
2026-10-01T11:36:17.003480+08:00结束并明确释放读集，窗口二直接续原第01份。
窗口一的第03份只读复用调查已交付，不要求重复调查或重跑内核全量。

## 1. 当前身份与实测

仓库 `/home/cuihengjia/agent/Code2Paper copy`，分支 `codex/agentic-p4-benchmark-cutover`，
HEAD `d48b4e4b22c94c82b45d2179ba452d72b164102d`；保留dirty树及原锁/工具链/worker。
开发目标0.2.0-rc.1，旧默认0.1.5-rc.3和日常0.1.7-rc.2受保护。

| 对象 | 实际SHA-256 |
|---|---|
| runtime树 | `43490765da460c4300cd7ad8ec75dbc5d5e6dbda93b74e37466c6709c1ab359c` |
| request-accounting.ts | `a5b209dbd59015f7b9c4a6537c0bb30f662684a46716a0b001430ed58c747b19` |
| build receipt | `17272dc43613b5bab067b8deb2209845aa57a1610f8842925e3646198eeaa8b3` |
| staging tree | `3dba363bc9b7accf0627c5efc0e288da6088655e22fbe3ff8c9261a3a00b438c` |
| outputs | `10a3248e866ada5cbfc67eb36ba70f2a5dd33c09939570db98a96111fa1bcc9a` |

stage中18文件、兼容清单的源码摘要匹配。runtime26149项字节/链接与上批完整清单相同。
791个Python源码/测试身份和内核原日志不变；保留component及4129/3 live skips/12 subtests记录。

| 证据 | 结果及边界 |
|---|---|
| owner完整check:compat | 核对final4原日志84pass/0fail/0skip、exit0；本批未独立重跑84项 |
| owner B02/doctor | 原B02日志23passed/exit0，doctor final2 exit0；与当前stage身份核对 |
| 独立原公开stream探针 | 3pass/0fail、真实exit0；合法child completed，公开调用均拒绝 |
| 独立原公开prepareCall探针 | 0pass/1fail、真实exit1；公开材料进入adapter，合法child error |

两命令用原断网隔离launcher的node --test，读取当前staged owner；只复制QA夹具，没有私有
WeakMap、签发授权或替换runtime。精确命令/脱敏原始日志/退出码及机器观察在
`.dsh-dev/run/qa-handle-acceptance-20261001-wrkclu0q/lead/`；探针在`probes/`。
`public-prepare-original`按测试名只重放原负例，未选历史诊断不算当前PASS。
前面三批证据及历史身份保留，不被新结果覆盖。
本批新日志自动打印的本地QA访问token已删除，命令/真实exit/断言及失败事实未变；
脱敏前后摘要记录在镜像`postchecks/log_sanitization.json`，没有保留token原文或改历史日志。

## 2. 结论

**H-R3原公开stream回落认领变体关闭。** fallback handle返回值消除了原公开llm.stream抢票，
原排入回调均拒绝，合法回落completed且恰计一次。仅关闭已重放变体，不替代prepareCall来源。

**H-R4仍未修复。** 原agent/request公开listener排入有限回调，经公开withInitiator及
llm.prepareCall(config, signal)取得handle。新候选第1回调仍得到可花费闭包，adapter收到
`R2 public preparation material`，reserve/dispatch/settle各1，裸调用finish stop；合法child为
`{"output":[],"stopReason":"error"}`。要求completed的保护断言失败，真实exit1。

原owner仍以`ticket.state === 'awaiting-prepare'`认定调用者owned。闭包只返回给调用者，
不能证明调用者是loop。`_020`关于公开回调不能到达该状态的不可达性论证被原探针否定；
C14b的非owned拒绝不覆盖此反例。旧C13/C14 listener重入已修事实保留，不能代替H-R4。

交付也有身份缺口：`h02_interface_freeze_020.md`身份表仍是c2da50e2/599a8d79/32fad720/
7731232f，实际stage/兼容清单已是上表新版。接口仍为候选，尚不能独立冻结。
原AT继续集中收口，真实持久写点不能仅以替换flush函数后断言替身抛错证明。

## 3. 现在给两个窗口的指令

共同先读[仓库入口](../README.md)、[执行入口§3.9](README.md)、[台账](task_board.json)、
[共享接口](interfaces.md)、[验证§12](verification.md)。使用上述当前分支/HEAD与dirty树；
Python3.13.9、Node25.8.2/npm11.11.1、既有锁和worker复用，不安装/重封旧runtime。
无切分支/reset/clean/commit/merge/push、真实模型、日常更新或默认切换授权。

**窗口二继续[第01份](01_baseline_and_dsh_compatibility.md)完整B02/H01–H04阶段，独占TS、
peer、工具链、build、stage及0.2根写权。**

1. 新鲜返修根重放本批原公开prepareCall负例，保留合法prepared/fallback正对照和首次失败。
   修闭包获取来源，普通prepared与NO_ADAPTER返回handle都要覆盖：合法loop可获取，公开
   listener使用相同Agent/signal/setter/config不能获取；合法A/B各一次，裸请求零reserve/adapter。
   首次调用、微任务顺序、awaiting状态、公开材料/request同一性不能代替调用者来源。
2. 沿真实公开API确认可信能力交接点后修原owner；若公共能力确实不能表达，一次交合法/
   裸调用事实与最小所需公开接口差异给LEAD裁决，不自行改冻结runtime、私有helper、
   全局loop factory或原验收语义，不以不可达性文字替代原探针。
3. 保留有效证据，集中复验受影响准备/两回执等待、abort/fence/漂移、cap、兄弟、清理结算、
   同child terminal→settle→flush→新进程恢复，补齐原AT→真实节点/状态/日志。
4. 稳定后一次目标check:compat、原B02目录、doctor --evidence；同步_020身份表/源码注释/
   兼容清单/覆盖矩阵，交统一源码/build/stage/runtime/read-set和写权释放。阶段内连续修，
   不逐缺陷/逐测试申请派工；完整冻结候选才交独立QA。

```bash
cd '/home/cuihengjia/agent/Code2Paper copy'
export C2P_DSH_DEV_ROOT="$PWD/.dsh-dev/candidates/0.2.0-rc.1"
export C2P_DSH_CANDIDATE='0.2.0-rc.1'
```

Python stage/test带`--candidate 0.2.0-rc.1`；正式Node仍原隔离node --test。
源码改变由窗口二typecheck→build→目标stage→聚焦验证，完整稳定后才最终check:compat。
逐命令保存argv/真实exit，不覆盖旧失败或QA证据。

**窗口一保持[第02份§4.4](02_kernel_publication_and_request_guards.md)已验内核；第03份只读准备已收下。**
核对builder/parser/assessor/reducer/settlement等具名入口与当前源码位置一致，不重复调查、
K-1/K-2或4129全量，不提前改publication_method_writer.py、validator清单或C/R模块。
后续C02从原structured_caller抽同一纯解析/表示恢复/splice链，让旧caller、本地结算、新facade
共用；当前_settle_recorded_writer_attempt缺decode/splice，是原C02接线落点。真实请求仍从
build_publication_writer_request来，页技术字节实际重算，八态reducer及publication/registry/index
保持唯一权威；prepare额度快照不成为R02余额。

## 4. 后续按原文档推进

Gate-H与正式Gate-K满足后一次启用[第03份](03_writer_contract_and_worker.md)整包：
I01→C01→C00→C02→C03→C04。窗口一Python/共享protocol/validator/原逻辑抽取；
窗口二C00真实renderer/TS wire/唯一buildstage。C01本地合同后接C00，C02再消费真实投影，
阶段内连续衔接，整包验Gate-C；现在只读调查不等于已实现。
Gate-C后按[第04份](04_serial_writer_integration.md)推进R01–R04→V01→A01→V02完整离线链，
保留Gate-R/V，首个目标单run、串行、单Writer真实mock。live/全文事务/默认切换后置。
保留8份执行文档、49单元，不新建平行计划/账本/parser/协作体系。

本批2692输入、34份owner文件（33份.log）字节/元数据前后不变，runtime26149项不变；
宿主本批与仓库验证进程0、不可读0、全部命令返回、无pending。closing原文在镜像`lead/`。
明确释放后窗口二直接接回原阶段，QA结束不常驻。
