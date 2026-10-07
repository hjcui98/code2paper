# 2026-10-01 · R2候选验收与最快接续安排

**Gate-H仍CHANGES_REQUESTED；内核component PASS保留，正式Gate-K等待。**
本批QA已于2026-10-01T00:54:43.353019+08:00明确结束并释放实际读集。窗口二立即接回原第01份完整返修写权；
第03/04份只读准备，未授权提前实现。LEAD没有修改产品代码。

## 当前输入与真实结果

仓库 `/home/cuihengjia/agent/Code2Paper copy`，分支 `codex/agentic-p4-benchmark-cutover`，
HEAD `d48b4e4b22c94c82b45d2179ba452d72b164102d`。Python3.13.9、Node25.8.2/npm11.11.1，保留dirty树。
目标仍 `.dsh-dev/candidates/0.2.0-rc.1/`，runtime43490765…，request-accounting c2da50e2…，
build599a8d79…、stage32fad720…、outputs7731232f…，peer不变。
旧0.1.5对照与日常0.1.7保留，无live、切分支、reset/clean、commit/merge/push或默认切换授权。

| 证据 | 结果与边界 |
|---|---|
| owner check:compat | 最终log exit0，83pass/0fail；final2的exit1保留，不覆盖 |
| 独立原test:compat | exit0，83pass/0fail/0skip，66.74s；同一stage，未重build/stage |
| LEAD原B02 dev目录 | exit0，23passed；整目录，未裁掉原集合 |
| 受影响身份原两模块 | exit0，29passed；TS/合同会改变engine输入，Python validator源不变，不把六文件不变等同完整engine不变 |
| 已验内核 | 全部此前snapshot中的Python源码/测试及内核日志元数据不变，六份身份与§10相同；保留4129/3live skips/12subtests历史完整日志，不重跑全量 |
| 旧H-R1/H-R2具名反例 | 同实际request/完整复制/不同messages在合法stream listener内均拒绝；child completed且R/D/S各1，销毁后的延迟请求仍拒绝 |
| 新准备认领与回落认领 | 两条真实公开调用仍能先取得票据，裸请求R/D/S/adapter各1、合法child error，见下文 |

独立会话在83项已返回后两次被自动内容检查中断，没有自行释放读集。未参与实现的LEAD接手
只读验收；没有据会话失败推断进程结束。初次LEAD隔离启动因bwrap NETLINK权限在产品执行前
exit1；通过原隔离launcher获得执行权限后继续，首次失败保留，没有裸跑或真实模型。
原两份负向probe命令各exit1是真实断言失败；不能写成产品PASS。

证据镜像 `.dsh-dev/run/qa-r2-acceptance-20261001-d4gkwv4k/`，38份文件由mirror_manifest绑定；原tmp、候选QA根和前两批证据保留。
主日志 `independent/r2-call-lifecycle-authorized.log`、`independent/r2-preparation-order.log`；
探针 `probes/r2-call-lifecycle.test.ts`、`probes/r2-preparation-order.test.ts`；
机器观察 `lead/public_call_observations.json`。只复制QA夹具，不复制生产判定逻辑。

## 同一根因的两个剩余阻断

**H-R3：NO_ADAPTER首次回落认领仍是公开竞速。** 真实agent/request事件取得公开Agent、signal，
排入普通queueMicrotask，随后经公开withInitiator调用llm.stream。同provider/model、另一个messages
请求能在fallback-ready第一次认领。64次有限观察中第8回调成功；进一步单次对照中，提前7步
调用被拒且合法child成功，提前8步的单次调用R/D/S/adapter各1、合法child error。不是随机等绿。
冻结runtime在prepareRequest返回后、真正stream前仍有await continuation；_020关于无可调度
microtask间隙的前提已被实际调用否定。

**H-R4：公开prepareCall也能领走prepared闭包。** 公共agent/request回调排入调用，经公开
llm.prepareCall(config, signal)拿到stream再提交自己的材料；第一次公开回调被owned判为真实准备，
返回可花费的闭包。真实adapter看到`R2 public preparation material`，R/D/S各1、裸请求finish stop，
合法child error。未读取私有WeakMap、未签发authorization、未改runtime或loop factory。
因此只关闭NO_ADAPTER回落不能收口普通prepared来源。

两处共同问题是把公开API的第一个调用当作可信loop调用。provider/model、摘要、signal、对象同一性
和公开currentInitiator不能补足来源。H-R1/H-R2上一批具体listener变体可关闭，但H04完整来源仍失败。

原AT不能以83计数折抵。保留合法兄弟、取消/fence、cap、async return与unfinished等有效新增节点。
H03新增flush用例直接替换flush方法后断言它抛错，只证明QA替身抛错；不单独认作实际持久写点
失败/阻塞证明。阶段交付仍需完整原AT→真实节点/状态/日志，未测或不适用写明依据。

## 立即给两个窗口的指令

**窗口二：继续原第01份整阶段，优先一次关闭H-R3/H-R4。**

1. 从本批新QA根复制两份probe到自己的新鲜返修根，保留合法prepared/fallback/销毁后对照与
   公开prepareCall/排入回调的反例；使用原隔离node--test，逐命令落盘argv/log/真实exit，不覆盖本批证据。
2. 修复目标是“实际loop拥有本次准备与派发能力”。先沿真实公开API查清调用者上下文与能力交接点，
   再由原owner作最小修复；不能再用首个调用、队列步数、provider/model或公开setter当来源。
   如公开API确实无法表达，交真实调用链、合法/裸调用对照和最小所需公开接口给LEAD一次裁决。
   不修改冻结runtime、私有helper、全局loop factory、排除原观测者或降低原AT来过门。
3. 闭合两个来源入口后，一次复验合法A/B各一次、公开调用零adapter、两receipt等待期、prepared
   重复/config漂移、terminal来源与flush/新进程联合；原有效证据直接引用，实际缺项集中补齐。
4. 稳定后只跑一次完整目标check:compat、原B02目录、doctor--evidence，更新_020/兼容清单/覆盖矩阵，
   交统一source/build/stage/runtime身份及写权释放。普通问题连续修，不逐缺陷/测试停派工。

**窗口一：保持已验第02份候选，只读完成第03份准备。**
核对真实builder、原parser/assessor、已落盘响应settlement、publication/index/registry的消费入口，
列出复用和抽取位置；原账本/发布/索引保持单一权威。当前没有内核返修，不重跑4129，不实施
C/R新模块。共享Python输入确需变更由LEAD协调原owner与受影响回归。

## Gate-H/K满足后的一次完整阶段派工

这是排队方案，**现在不生效为实现许可**，不新增执行文档或拆一套任务。

- 窗口一负责第03份I01→C01→C02→C03→C04：实际composition原语、Python唯一合同/TaskView、
  原caller/恢复/facade共用解析、可信ingest与原owner局部发布、短调用JSONL worker。
  protocol.py与authoring_execution_identity.py/validator清单由窗口一单写，增补实际已落地判定源。
- 窗口二负责原C00及TS wire消费：真实公开SystemPrompt/renderer形成无模型projection，实际pi-ai
  对隔离假HTTP/SSE的wire对照，以及唯一peer/toolchain/build/stage。C01本地schema可消费后接入，
  protocol字段需求交窗口一写，双方不同时改共享Python文件。
- 阶段内依赖按前置实现和有意义本地合同连续衔接，不等逐单元独立PASS。整包验Gate-C，要求
  I01及C00–C04原AT与真实worker无模型往返；新TS不建立parser/账本，不能隐藏Python模型调用。
- Gate-C之后接第04份R01→R02→R03→R04→V01→A01→V02离线完整链：持久task/claim、原Python
  唯一账本真实RPC、Host pump、跨进程恢复、单run串行单Writer mock、真实覆盖回执和opt-in入口。
  Gate-R/Gate-V独立保留；L01需单独live授权，完整主图/质量/默认切换仍后置。

## 收尾

903个LEAD输入、27份owner日志、2678个独立QA输入的hash/inode/mtime/size全部不变；runtime26149项
完整bytes/link清单相同。宿主精确本批验证进程0、不可读0，全部启动命令已返回，无pending。
未重跑无变化CLI，引用上批同字节launcher/profile的实际HTTP/端口关闭证据。
closing原文在镜像lead/closing_release.json与closing_process_check.json，释放不是超时推断。
49任务的原依赖、AT、正式状态不变；窗口二继续本阶段唯一实施线，QA结束不常驻。

[执行入口](README.md) · [台账](task_board.json) · [原第03份](03_writer_contract_and_worker.md) · [原第04份](04_serial_writer_integration.md)
