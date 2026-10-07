# 2026-09-30 返修候选差分验收与接续裁决

**Python K01–K04：本批 component PASS，正式 Gate-K 等待 Gate-H。DSH 第01份：
CHANGES_REQUESTED，Gate-H 未通过。第03/04份仍未启动。**

这是两位实施者交付返修候选后的实际独立复验。它接续
[上一批裁决](stage_acceptance_20260930.md)，不修改旧失败、旧报告或旧身份。
LEAD 没有修改产品代码；内核由未参与实现的 LEAD 只读复验，DSH 由独立 QA 复验。
窗口二仍需一次完成原阶段剩余合同；窗口一保持已验候选，当前没有新的内核返修项。

## 1. 当前代码、环境与证据

- 仓库 `/home/cuihengjia/agent/Code2Paper copy`，分支
  `codex/agentic-p4-benchmark-cutover`，HEAD
  `d48b4e4b22c94c82b45d2179ba452d72b164102d`，未提交改动保留。
- Python `/home/cuihengjia/miniconda3/bin/python` 3.13.9；Node v25.8.2、npm 11.11.1；
  复用现有锁、独立工具链和 target pyworker。Node 正式入口仍是隔离 launcher 的
  `node --test`；没有重装、QA 重 build/stage 或裸跑。
- 目标 `.dsh-dev/candidates/0.2.0-rc.1/`，runtime
  `43490765da460c4300cd7ad8ec75dbc5d5e6dbda93b74e37466c6709c1ab359c`，peer 未变。
  本批 build outputs `4bdd2ecea20393e663aba77f393816b3a594aa2636378c1be85a6a179403422f`；
  stage `a67555d1ecaadb447dbd642c1d7ac3ed31660cb8a9717d7bb1bb4b9c8a6baedf`。
  旧默认 `0.1.5-rc.3 / 7e8f199b…` 与日常 `0.1.7-rc.2` 保留。
- owner 交付：[内核证据 §10](kernel_stage_evidence.md)、
  [窗口二返修交付](../../integrations/dsh/dev/runtime-0.2.0-rc.1/w2_delivery.md)、
  [_020 接口候选](h02_interface_freeze_020.md)、
  [兼容清单](../../integrations/dsh/compatibility.0.2.0-rc.1.json)。交付声明与独立裁决分别记录。
- [DSH 独立返修报告原文副本](gate_h_repair_independent_review_20260930.md)，SHA-256
  `98d05925fcfb572bcf87f859f501ddf6b804f804aa6752919082fd3f15eb51b8`。
- 仓库可见证据镜像：`.dsh-dev/run/qa-stage-repair-review-20260930-y7m330na/`。
  `mirror_manifest.json` 绑定 410 个复制文件；`lead/` 保存内核 argv/log/exit、逐路径
  before/after、真实持久反例与 closing；`gate-h/`、`gate-h-probes/` 保存独立日志和公开
  API 探针。原 `/tmp` 和候选 QA 根保留，不覆盖上一批镜像。

## 2. 实际结果及性质

| 验证 | 结果 | 准确范围 |
|---|---|---|
| owner 完整 `check:compat` | exit 0，74 pass / 0 fail | typecheck/build/显式目标 stage/check/test 原日志及输入/产物身份核对；QA 不重封 |
| 独立 `test:compat` | exit 0，74 pass / 0 fail / 0 skip | 同一 stage、原 11 个 TS 文件、只读/断网 launcher；不等于全部原 AT 通过 |
| 独立 B02 原 dev 目录 | exit 0，23 passed | owner 单文件 20 与发现范围 3 项完整复验，未裁掉原集合 |
| 普通 Web 与 compat 真实 CLI | 各 exit 0 | 私有同字节 home/profile，候选 cwd，HTML 和各四资产 HTTP 200、模型 turn 0、退出及端口关闭 |
| LEAD 原六内核模块 | exit 0，103 passed | 同一候选原 registry/publication/index/ledger 与故障/真实恢复矩阵 |
| LEAD K04/身份/真实调用方 | exit 0，282 passed | 页合同、公式家族、closure、legacy、Formalizer、Writer、doctor/resume、autonomous/vertical 原文件 |
| owner 完整静态套件 | exit 0，4129 passed / 3 skipped / 12 subtests | 完整日志、argv、`.exit` 与摘要核对；三 skip 为原 `CODE2PAPER_RUN_LIVE_LLM` 门，未独立重复全量 |
| 独立 replay / manifest 原反例 | 各 exit 0 | 合法重放先落盘后矛盾回执仍 unknown；实际验证后换 g2 字节返回 typed digest mismatch |
| 实际 Writer/doctor 消费方 | 行为断言成立，见原始命令与观察 | 真实进程退出9留下请求、原诊断/receipt/replay owner、公共 Writer 入口；unknown 零 Writer/Realizer 新调用，corrupt 具名拒绝且预留保留 |
| DSH 公开来源新增探针 | exit 0 仅表示反例观察完成 | 三个裸请求实际 R/D/S 与 adapter 各一次，原合法 child 失败；负向来源合同不成立 |

全量静态日志 SHA-256 为
`4bd9f61bc8fe5a9907c8ec3d3bea5db1cb896dfc7e1604b5569f63a446689902`。
不相加测试数作为任务/产品完成证明。

追加内核 QA 驱动首次错误全部保留，包括预算 preflight/doctor 字段语义假设、错误回执
seal/usage 变异、原正对照前置未满足和一个未启动产品的文件名错误。前置不成立的探针
没有裁为产品缺陷，也没有修改任何产品门使其通过。各 `probe_fixture_correction*.json`、
`first_failure.txt` 和非零 `.exit` 均在镜像中。`real_writer_consumers_final.exit=1` 对应
损坏场景对全局 unknown tuple 的过强假设；此前 late-conflict 的真实 Writer/doctor 断言
已全部通过，保存在 `real-writer-crash-replay-final/observed.json`。
损坏场景由 `corrupt_consumer_continuation.exit=0` 收口：公共 reservation reader 保留 attempt1，
reducer 为 ledger_corrupt/accepted=false，真实入口零发送并具名完整性拒绝，doctor 不报已接受。
全局 corrupt 状态与逐 attempt 的保留预留字段分别按原合同核对，不倒填整条失败命令为0。

## 3. 内核 component 通过与正式依赖

| 原单元/反例 | 本批行为证据 |
|---|---|
| K01 | 原严格 record/pointer/schema/producer/upstream 篡改与幂等；冻结 0918 owner 真1.0 子进程只读；损坏2.0不降级；缺来源/改变裁决文件使身份变化 |
| K02 | 实际成员/manifest/active 持久点退出86后新进程读取；多进程 barrier CAS 唯一成功/fence2；旧 fence、回包丢失、重复提交与三媒体原节点 |
| K03 / K-2 | 同代真实成员读取、混代/来源漂移拒绝、三方 active、projection 损坏/修复；独立原 manifest race 实际换 g2 被 `artifact_manifest_digest_mismatch` 拒绝 |
| K04 / K-1 | 原发送点 G1–G7、非空家族、跨 seed/紧预算与身份回归；冲突后拒绝发布接受 replay，已有合法 replay 后冲突仍 unknown，损坏 accepted=false；真实缓存/恢复/相位消费与正常预算对照 |

具体新回归节点见内核证据 §10；独立原 six-file 和 affected-consumers 的准确 argv/exit
在 `lead/`。实际 late-conflict 的公共入口返回
`writer_phase_boundary_blocked:…primary_cause=send_outcome_unknown:…unknown_reservations=[1]:…`，
provider templates 为空，replay 字节不变，doctor 首因同为 send_outcome_unknown。
真实损坏 request 在更早的原诊断完整性门拒绝，保留预留且不盲发；不要求它越过该门才拒绝。

本批接受 K01–K04 完整 **component PASS**，关闭上批 K-1/K-2 与已实测的原局部覆盖问题。
H03/H04 前置与 Gate-H 未满足，K01–K04 仍不登记正式 done，Gate-K 不通过。
保持本批 Python 源码、测试、validator 身份和完整日志；只因后续实际共享输入/合同变化才
做受影响复验。断电、C03/F02、DSH RPC 与 live 仍不在本批证明范围。

## 4. DSH 集中剩余项与修复方向

**H-R1：公开同 request 引用重入抢 prepared 票据。**
`request-accounting.ts` 354–363、390–394 把准备能力放在 request 对象的 WeakMap 标记上。
真实 `llm/stream` waterfall 会公开同一对象。公开 prepend listener 仅执行
`deployment.llm.stream(request)` 就完成裸 R/D/S/adapter；原 child 随后因来源票据消耗失败。
无私有标记读取、授权签发或 runtime 改动。

**H-R2：NO_ADAPTER 回落给任意同 signal 请求补来源。**
同文件 401、410–415 的 fallback-ready 入口把公开 signal 当作可重建准备能力。
真实 loop 接到一次 typed NO_ADAPTER 后，公开 Agent/signal/withInitiator + 全材料复制，
以及改 messages 两种裸请求都完成派发/结算，原 child 失败。它不依赖 H-R1 的同对象。

修复仍在原 source/accounting/route owner 内：可信单次派发能力须在进入可重入公开回调前
归属于真实 loop continuation，并在内部一路交接；公开 request 对象、signal、归属 setter
或完整摘要不能重新获得能力。先复现原正负对照，再选择最小实现，不把此方向理解为
要求新建持久权威、私有 factory、全局串行锁或任意新架构。合法兄弟独立推进与单次计量保留。
如果当前公开 API 真不能表达此硬门，提交公共 API 调用事实和最小接口差异给 LEAD 裁决。

原 F1 具名反例、准备等待的旧 F2、F3 合法兄弟、F4 同步 return、F5 cwd/Web/矩阵已修复，
不得从零再派。剩余原 AT 以独立报告 §5 为准，窗口二一次补齐：

1. 真 prepared 对象的第二派发/配置漂移；两回执等待期分别覆盖 abort、fence、完整
   messages/tools/toolHistory/config 漂移及 cap 无法建立；拒绝须零 adapter、保留准确预留结论。
2. 实际 async-return reject/timeout、iteration/break/throw/abort/next 等异常和 recorder
   清理矩阵；已结算不二记，unknown 不退款，250ms 截止不等于底层静止。只测 helper 不收口。
3. H03 支持消息合同的严格读取、flush 阻塞/失败/缺字节与新进程恢复。QA 另保留 missing
   content/null block/非字符串 text 的观察：对照真实 V3/V4 支持类型裁定，支持成功合同的
   畸形必须具名拒绝；合法空结果只按明确协议处理，不做任意宽松回退或声称完整 Message
   schema 已验。此前具名 F1 修复保留。
4. 同一个真实绑定 child 中，在准备/reserve/dispatch 等待时做上述攻击，合法原 terminal、
   settle、flush 与新进程来源保持正确。现有 joint 在 commit 之后的裸调用只证明其原范围。
5. active scoped 组成/禁止路径的逐 AT 映射、接口完整交付：纠正 `_020` 对 currentInitiator
   的旧授权表述，枚举真实导出/四 recorder 方法/活跃 binding 示例与资源责任。明确 mock
   puretext、imageOffload/Schedule/desktop/standard preset 的已测或不适用范围，不扩大 PASS。

## 5. 给两位接手实施者的完整指令

双方先读仓库 `docs/README.md`、执行入口最新 §3.7、当前 `task_board.json`、`interfaces.md`、
本裁决和 verification §10；不要以 §3.6 历史派工覆盖本批代码事实。复核当前分支/HEAD/
未提交差分与 owner 释放记录，保留全部既有修改。没有 live、日常更新、旧环境重封、
reset/clean/切分支/commit/merge/push 授权。

**窗口一：**接手原第02份 K01–K04 候选与身份保管。本批独立 component 已通过，
立即核对内核证据 §10、103/282 原命令、4129 全量日志与本批 closing。保持此候选冻结；
没有新发现时不再重做 K-1/K-2 或重跑完整套件。可只读准备原第03份的消费接口/依赖清单，
不启动 C/R 新实现。窗口二不改 Python 核心；共享 Python/validator 输入实际需要变化时，
由 LEAD 协调原 owner 的窄范围变更与受影响回归。Gate-H 后由 LEAD 核对正式前置，再开
第03/04份原阶段。只在实际合同冲突或输入变化时汇报，不配置等待 QA 的循环任务。

**窗口二：**独占原第01份 B02/H01–H04、TS/peer/工具链/build/stage/0.2候选根写权。
在当前74项和本批有效修复上连续完成 §4 整包：两条来源抢票 → 真正异常/等待矩阵与
H03原 AT → 同 child 等待期来源及新进程联合 → scoped组成与完整 `_020` 交付。
阶段内普通问题自主修复，不逐缺陷/逐测试申请开工。

```bash
cd '/home/cuihengjia/agent/Code2Paper copy'
git branch --show-current
git rev-parse HEAD
git status --short
export C2P_DSH_DEV_ROOT='/home/cuihengjia/agent/Code2Paper copy/.dsh-dev/candidates/0.2.0-rc.1'
export C2P_DSH_CANDIDATE='0.2.0-rc.1'
```

环境身份不符先解释实际差异，不切分支还原。内部选择必要聚焦入口；稳定完整候选再跑
`npm --prefix integrations/dsh run check:compat`、原 B02 dev 目录矩阵与
`python scripts/dsh_dev.py --candidate 0.2.0-rc.1 doctor --evidence`。
全部 Python stage/test 子命令保持显式候选；Node仍用原隔离器。新鲜返修子根保存每命令
实际 argv/log/exit、首次失败、AT→节点/持久状态、统一源/build/stage/runtime/接口身份、
差分、未测项与写权释放。完整候选再独立复验，不以新总数申报 Gate-H。

## 6. 本批 closing 与台账

DSH QA release 为 **21:30:09+08**，LEAD 为 **21:36:51+08**；各对应 closing 原文在镜像。
LEAD 901 输入和35 owner日志 hash/inode/mtime/size 完全相同；DSH2618项完整元数据与
runtime26149项相同。所有本批命令返回，无 pending；宿主精确 QA/目标CLI匹配0、不可读0，
两 CLI 端口再次关闭。本批共享profile未写。npm 安装前日常 hash 缺失仍为 N/A，不倒填。

旧13:20、19:01 releasing/history保留。LEAD 此后只更新裁决、入口、台账和工作记录；
49个单元的依赖、AT、原责任域不变，正式状态不以计数改为done。
DSH窗口二接回上述原阶段完整写权；内核已验候选保持冻结。QA结束，不常驻第三窗口。

[返回执行入口](README.md) · [验证规则](verification.md)
