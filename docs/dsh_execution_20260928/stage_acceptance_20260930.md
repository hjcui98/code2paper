# 2026-09-30 两阶段独立验收与集中返修裁决

**裁决：两份候选均为 CHANGES_REQUESTED；Gate-H、Gate-K 未通过。**
本轮已实际验收，区别于此前只读交接。两位新实施者已提交完整阶段候选并释放写权；
DSH 由独立审查人复验，Python 内核由未参与产品实现的 LEAD 复验。保留正向证据，
将下列实际反例集中交回原阶段负责人，不拆成逐缺陷派工。第 03/04 份仍未启动。

## 1. 身份、范围与证据入口

- 仓库 `/home/cuihengjia/agent/Code2Paper copy`；分支
  `codex/agentic-p4-benchmark-cutover`；HEAD
  `d48b4e4b22c94c82b45d2179ba452d72b164102d`，保留未提交树。
- 目标 `.dsh-dev/candidates/0.2.0-rc.1/`；独立同算法实算 runtime
  `43490765da460c4300cd7ad8ec75dbc5d5e6dbda93b74e37466c6709c1ab359c`。
  peer 仍指目标；旧默认树仍为
  `7e8f199b67027944d646e0c99f5041d4704360377e4d7466fce683c1d468d3ab`。
  用户日常 `0.1.7-rc.2` 未启动、未写入；没有日常安装前后 hash 比较证明，不能倒填。
- Python `/home/cuihengjia/miniconda3/bin/python` 3.13.9；Node v25.8.2。
  DSH 仍用原 launcher、只读/断网 bubblewrap 和 `node --test`。
  QA 未 build/stage、切 peer、安装依赖或修改产品代码。
- 窗口一交付：[kernel_stage_evidence §9](kernel_stage_evidence.md)；
  窗口二交付：[w2_delivery](../../integrations/dsh/dev/runtime-0.2.0-rc.1/w2_delivery.md)、
  [_020 接口候选](h02_interface_freeze_020.md)、
  [兼容清单](../../integrations/dsh/compatibility.0.2.0-rc.1.json)。这些是交付，不是批准。
- [DSH 独立报告原文副本](gate_h_independent_review_20260930.md)，SHA-256
  `804a83aac5a1ded1d3b192a1e0629312efcf92a240b437a8c2ec81719377b29c`。
  原报告、原首次失败与 owner 日志全部保留。
- 仓库可见证据镜像：
  `.dsh-dev/run/qa-stage-review-20260930-izdz_5y3/`。
  `mirror_manifest.json` 绑定 123 个复制文件的摘要；`lead/` 保存内核命令、退出码、探针
  与持久反例；`gate-h/` 保存独立运行、before/after 和 closing；`gate-h-probes/`
  保存公开 API/损坏日志探针。原 `/tmp` 与候选 QA 根也保留，不要求接手人能访问私有 `/tmp`。

## 2. 已核对结果与可保留的行为

| 验证 | 证据性质与实际退出码 | 结论 |
|---|---|---|
| 窗口二 `check:compat` 完整链 | owner 日志及冻结源码/build/stage 身份复比；报告 exit 0 | typecheck、build、显式目标 stage/check、11 个 TS 文件 71 pass；不重复重封 |
| 独立 `test:compat` | 真 exit 0，71 pass / 0 fail / 0 skip | 现有正向/反例回归可复现；不是全部 AT 通过 |
| Python 聚焦六模块 | LEAD 真 exit 0，99 passed，19.08s | 当前原测试全部复现；额外独立反例仍失败 |
| `python -m pytest -q -rs` | owner 完整日志、argv、`.exit=0` 和摘要均已核对 | 4125 passed、3 skipped、12 subtests；三次跳过均为原 live 门，未独立重复全量 |
| 内核重放冲突探针 | `kernel-replay-probe.exit=1`、`kernel-late-conflict-v2.exit=1` | 预期 fail-closed 断言失败，见 K-1 |
| 内核读取竞争探针 | `kernel-manifest-race.exit=1` | 预期拒绝断言失败，见 K-2 |
| DSH 独立补充探针 | 各 `.exit` 绑定真实运行 | exit 0 表示观察完成；产品负向合同是否成立见独立报告，不用退出码抹掉实测缺陷 |
| B02 原 Python 矩阵 | 独立 exit 1，20 pass / 2 fail | 两项候选夹具/API 适配失败，须保留并修复 |
| doctor 与真实 CLI | doctor(False) exit 0；compat smoke exit 0；web smoke exit 1 | compat HTTP/资源/端口关闭有效；普通 Web 40s 未就绪，原因未定 |

内核 full_static.log SHA-256 为
`5f5b525dca1b8a6d36eaca0e90b82de1b4a88a70b3ab01f28ee992cf65940814`。
不再把旧缺完整日志的 4114 数字当作本批全量证据。

以下新增节点在本批聚焦独立运行中通过：冻结 `0918ee76` owner 在隔离子进程生成真实
1.0 档案并具名只读；损坏 2.0 不降级；成员/manifest/指针实际持久点的退出码 86 与新进程
reader；双进程 barrier CAS 唯一成功者/fence=2；三方 active 分歧只认发布权威；投影
损坏/修复不新增 generation 或 fence。旧正向账本预算、明确未发和未知发送对照继续有效。
这些不抵销 K-1/K-2，也不将 K01/K02 单独登记 done。

新版候选传递与 worker 已补齐，H03 V4 合法成功/版本分派和同 child 的
reserve→dispatch→adapter→terminal→settle→flush→新进程恢复也已独立复现。
两次回执等待期间完整材料复制、公开同 signal 裸请求被拒且合法原请求各成功；双 child
在 reserve 边界真实交错计量成立。此前“terminal 0/8”“候选传递缺失”“worker 不存在”
已是历史检查点，不能继续作为当前缺口。

QA 夹具的首次失败另外保留：内核追加探针初轮缺 PYTHONPATH；DSH 初轮重复注册 mock；
外层沙箱初轮无法创建网络命名空间。修正只涉及 QA 调用/夹具，均不作为产品缺陷。
owner 的首次完整链 5 项失败日志保留；首次 doctor 失败日志曾被 owner 覆盖的事实也保留。

## 3. 窗口一：两项实际阻断

### K-1 · 同 validator 重放覆盖冲突发送事实（K04）

原 owner：[writer_attempt_ledger.py](../../src/code2paper/agentic/writer_attempt_ledger.py)，
重点 448、480–529；真实消费方 `publication_method_writer.py` 4757–4789。

持久 request/response 存在而 completed 声称 `sent_to_caller=false`，无重放的对照
正确归约为 `send_outcome_unknown / send_claim_conflicts_with_persistent_evidence`。
但同 validator 的 `publish_validation_replay(accepted=True)` 经原公开 API 落盘后，
同一个 reducer 返回 **accepted_reusable、accepted=true、unknown_reservations=[]**；
逐 attempt 仍为 unknown 且保留预留。invocation 与 attempt 的权威结论互相矛盾。

第二个独立对照先持久化正常已发送的合法验收重放，再引入矛盾 completed 回执，仍复现。
本次实际 validator bundle 是
`sha256:b553ad50ae36fc5a11a09fed0c4cf6e45c5df429460afbfce59a20d60eb452ef`。
正常发送+同身份重放为 accepted，旧 validator 重放不能抹掉冲突，两项正对照均成立。
request 损坏虽为 ledger_corrupt，但 accepted 标志也会被重放置真，须一起核对真实消费者。

证据：`lead/kernel-probe/observed.json`、`lead/kernel-late-conflict/observed.json`、
对应脚本/日志/argv/exit。没有复制 reducer、修源码或调用模型。

返修应在原归约/重放 owner 内闭合冲突与完整性优先级，使逐 attempt、invocation、缓存/
resume 和 Writer 相位边界一致。保留正常 accepted、明确未发、未知发送与预算耗尽原因；
不得用“验收内容通过”释放冲突预留、恢复盲发或伪造发送计数。

### K-2 · 验证后重读 manifest，错误归属另一代成员（K03/K02 联合）

原 owner：[authoring_artifact_index.py](../../src/code2paper/agentic/authoring_artifact_index.py)
1197–1271；`PublicationManifestV1` 的创建期重封 validator 见 publication 558–564。

合法 g1 发布与 reader 正对照先通过。在原 verifier 返回成功之后、reader 第二次读取
manifest 之前，QA 仅在临时产物根把该文件替换为已合法 stage 的 g2 manifest 字节；
registry loader 仍返回原真实结果，未伪造验证结论。reader 实际返回 g2 的成员值，
却标注 g1 权威摘要及 `generation_members_recomputed`。

观察：`value=QA-unverified-g2`、payload generation=2；reported g1 digest
`sha256:68887db37d1d8fecb0c6b383164c02951640d25a22e5f6564f6d87b55e069fb9`，
实际 payload digest
`sha256:874a89fb2f68ca4a7210a50ae85b72a0267c65960fdc4bf990aa0c1df338ff09`。
再次调用原 verifier 才报 `publication_manifest_digest_mismatch`。

证据：`lead/manifest-race/race-result.json` 与对应探针/日志/exit。
这是原 AT-K03“同次已验证字节”的受控写入竞争，不是断电或 C03/F02 新范围。
由原 reader 保证消费字节与所验证权威/成员集合一致，不借模型重封接受替换，也不把
“文件按约定不可变”作为拒绝篡改的替代。保持三方 active 和投影恢复的已通过行为。

## 4. 窗口二：集中缺陷与未完成的原 AT

详细控制、权限范围、实际节点与原始输出见独立报告 F1–F5；下列均属于第 01 份。

| 项 | 事实与原 owner | 返修目标 |
|---|---|---|
| H-1 / H03 | `terminal-result.ts` 779–821：null tool/call 抛 TypeError；非布尔 isError、null content、损坏 error.code 仍 committed | 逐条严格结构/成功事实校验，返回具名 unresolved；合法 V3/V4、新进程与 synthetic 拒绝保留 |
| H-2 / H04 | `request-accounting.ts` 304–383：监听公开事件取得 Agent/signal，公开 withInitiator 在真实 prepare 等待期让不同材料裸请求 R/D/S 且抢掉原合法票据 | 来源授权必须绑定真实本次准备/装配和派发；不能把公开归属 setter、signal 或摘要当可信授权 |
| H-3 / H04 | 同 owner 317、334–340：A 的 request waterfall 等待时，合法 B 因全局 requestDepth 被拒，adapter=0、recorder为空 | 保证各 child 的准备/消费归属独立，重叠合法 A/B 均成功且恰计一次，不以串行夹具折抵 |
| H-4 / H04 | 同 owner 71–80、546–565：同步 iterator.return 抛错；真实 child 最终 error，但 recorder 已 settled、无具名诊断 | 覆盖同步 throw、异步 reject、超时/abort 的结算与 cleanup 终态，截止不代表静止 |
| B-1 / B02 | `scripts/dsh_dev.py` 454、467–474：候选选择后 CLI `--chdir` 仍为旧 `.dsh-dev/workspace` | 真实 CLI/worker/probe 默认 cwd 随显式候选；所有目标运行路径与选择一致 |

待收口的原 AT：B02 普通 Web 未就绪的首个断点；原 Python 隔离矩阵两项候选适配；
日常安装可比较身份及无共享 inode/读写通路的证明；provider/title/retry/compaction/PTC/
OTel/desktop/Schedule 的实际 active scoped 组成与禁止行为映射。两个 Python 失败目前
是旧夹具/API 假设，不是已证权限绕过；Web 未就绪原因未定，不把 B-1 推作唯一根因。
不得删测试、自动信任漂移、补装 vitest、裸跑或增大 timeout 碰运气。

H-2 的攻击者只使用现有公开 Host 服务/事件，没有读私有票据、签授权、伪造 claim 或
修改 runtime。第 01 份已明确包含这个能力边界。若公开能力确实不足，按该文件停止条件
提交合法/反例、首个断点与最小接口差异供 LEAD 裁决；不能隐含排除可监听扩展或弱化门。

## 5. 冻结、验证副作用与写权接续

LEAD before/after 复比：899 项源码/测试/文档/回执与 30 项 owner 日志字节全部匹配。
DSH 独立 before/after：2618 项输入的字节与 inode 保持，两个 runtime/peer/build/stage
身份不变。**两个目标 profile 的 cordis.yml 在真实 CLI smoke 中发生 mtime 改写**，
字节及 inode 相同。严格 metadata 冻结未完全满足，不声明全批 metadata 未变；不还原
mtime，也不把该副作用推成源码/runtime 字节漂移。反例使用的 staged/source/runtime
字节身份仍有效。后续 QA 的可写 startup/profile 夹具应在独立 run 根中，显式记录实际读集。

DSH QA 的宿主 closing 检查：121 个本用户进程，精确 QA 根/目标 CLI 匹配 0、不可读 0；
全部启动的子进程已 wait 返回，未就绪 Web 已停止，无待写输出。Python 聚焦及三个
反例命令也已返回，真实退出码落盘。没有凭等待超时或会话状态推定释放。

**2026-09-30 19:01:54+08，DSH QA 明确释放本批完整读集；LEAD 内核验收亦已结束。**
closing、完整输入清单及原始输出保存在上述仓库可见镜像；台账登记新 release，不覆盖
13:20 的历史 closing。写权接续如下：

- 窗口一继续持有第 02 份原 K04→K01→K02→K03 并集代码/测试/阶段证据写权，完成
  K-1/K-2 与受影响真实消费者/身份/恢复/完整 AT。可直接返修，不等 Gate-H。
- 窗口二继续持有第 01 份 B02/H01–H04、TS、peer、工具链、build/stage 和目标候选根的
  唯一写权，集中完成 H-1–H-4/B-1 与原 AT、组成/保护/合法联合恢复。只重封 0.2。
- 阶段内普通问题自主修复；沿现有 rework 根建立新鲜子根，保留首次失败与逐命令真实
  退出码。稳定候选交完整差分、统一输入、AT→实际节点、日志与写权释放，再按需独立
  验收。Python 源码本批将改变，最终稳定候选仍需一份完整 `-rs` 全量日志；不逐缺陷重跑。
- 不自行登记 PASS/done/Gate，不开启第 03/04 份、live、日常更新、默认切换或提交/合并。
  共享身份输入确有交叉时短暂协调；失去并行收益则串行，不配置常驻 QA。

LEAD 只写本批裁决、执行入口、台账和工作记录，未自行修改产品实现。

[返回执行入口](README.md) · [验证规则](verification.md)
