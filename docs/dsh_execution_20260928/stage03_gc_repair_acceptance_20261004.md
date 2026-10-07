# 第 03 份 GC 集中返修独立验收与阶段接续

2026-10-04，独立裁决：**Gate-C PASS；GC-1、GC-2、GC-3 全部关闭。** 原第 03 份 I01/C01/C00/C02–C04 六项已满足本阶段原 AT 与真实联合接线要求，登记 done。第 01/02 份 Gate-B/H/K 已验结论保留。

49 项更新为 **17 done / 0 in_progress / 32 planned**。下一批按 [第 04 份整批执行指令](stage04_batch_execution_instructions_20261004.md)实施 R01–R04/V01/A01/V02；本轮只做验收与派工，七项尚未开始，Gate-R/V 尚未通过。局部 pending_validation 保留语义验证/反向验证义务，未调用真实模型，不授予默认切换、D5 或发布资格。

## 1. 验收范围和依据

验收 [GC 三组集中返修交付](stage03_gc_repair_delivery_20261003.md)及其完整冻结包
`.dsh-dev/run/stage03-gc-repair-w1-20261003/final-delivery/`，包括窗口二实际源码/运行字节/构建和全部联合证据。

依据 [前次独立裁决及修复要求](stage03_gate_c_review_and_batch_repair_20261003.md) GC-1/2/3、
[原第 03 份](03_writer_contract_and_worker.md)六项 AT、[原整批指令](stage03_batch_execution_instructions_20261003.md) §§3–7、
[interfaces](interfaces.md) §§1–7、[verification](verification.md) Gate-C；架构权威顺序按 [docs 入口](../README.md)。
没有将 owner 测试数字直接转换为独立通过，也未要求本阶段提前实现 R01/R02 的持久运行权限。

独立运行根：`/tmp/c2p-gate-c-gc-review-20261003-oawiwm_g/`。
独立稳定证据：[stage03-gc-qa-20261004-oawiwmg](../../.dsh-dev/run/stage03-gc-qa-20261004-oawiwmg/EVIDENCE_SEAL.md)。
[review.json](../../.dsh-dev/run/stage03-gc-qa-20261004-oawiwmg/review.json)为机器可读裁决；
[清单](../../.dsh-dev/run/stage03-gc-qa-20261004-oawiwmg/SEALED_FILES.sha256.json)封存 **3,541 个文件/链接**，SHA-256：
`d80c04d777f11bd2585fba161918c80392fe071b2110186e0ebedbcbebecf46b`。
清单不包含自身与 seal note；包含原始命令/日志、完整 RPC、driver 及改编差分、实际运行产物、输入副本和释放证明。

## 2. 三组问题逐项关闭

| 问题 | 独立确认的修后行为 | 核心证据 |
|---|---|---|
| **GC-1** Unicode 合同 | 上轮 12 例原始 Python/TS 差分全部一致；U+0085 纯空白两端拒绝，U+FEFF 两端接受。完整 TS 集合中的 12 个真实 native 正反例通过，非法不成功 callback/conclude、无第二请求；合法 FEFF/ASCII 再经真实 worker record_output。全 scalar Python 对照保持原接受域，未缩减 Unicode 义务 | `wire-differential.json`、`ts.log`、`c00/stage03-writer-request-JUkMVh/gc1-*`、`runs/gc-closure-unicode/` |
| **GC-2** 过期材料 prepare | 真 worker 对 revision/fence/snapshot/组合漂移均在 prepare 返回 `frozen_revision_snapshot_or_fence_stale`。正常材料仍通过；owner 正常新冻结 revision2/fence1 的完整链通过；准备途中 Host 变化、重编返回旧材料的真实 stdio 测试通过；原已提交缓存未被新检查破坏 | `focused.log`、`stale-prepare-results.json`及 transcript、`runs/joint-fresh-revision/`、`runs/cap-recompile-zero-send/` |
| **GC-3** 新 ingest 引用完整性 | draft/research_required/blocked 三终态合计 **99 个拒绝反例**全部通过，缺失、损坏、元数据/版本/绑定错误不生成新 active/generation/receipt。完整三终态分别得到 pending_validation/waiting/blocked；原 reader 读回 14 项依赖闭包。相同已提交重试、准备引用已缺失及新 Host revision/fence 后的合法恢复仍返回原 receipt | `runs/gc-closure-unicode/results.json`、`rpc-transcript.json`、各终态 `reader-members.json`与 `commands.json` |

GC-3 矩阵实际执行 **190 次 RPC**，未替换生产 worker/assessor/发布 owner。缺失或损坏注入只发生在 QA 私有 artifact 副本；原包与正式输入保持不变。拒绝码逐项断言，无“抛任何异常即可”的替代。

代码复核确认：`check_frozen_current` 覆盖 render、首次 prepare、重编返回和最终 seal/返回；新 ingest 在授权/输出完整性/合法已提交缓存之后调用 `verify_contract_dependencies`，复用 C02 投影/计量核对，持久化 `LocalWriterDependencyClosureV1`，manifest read_set 覆盖完整依据；发送、领域正文与余额权威未转移到 TS。

## 3. 独立复跑与实际身份

| 检查 | 本轮结果 |
|---|---|
| 五份 Python 专项 | **226 passed**，exit 0，181.98s |
| 七份原 owner 回归 | **265 passed**，exit 0，39.26s |
| 完整 TS 兼容/实际 native | **165 passed / 0 fail / 0 skip**，exit 0；原 93 项保留 |
| B02 全目录 | **48 passed**，exit 0 |
| typecheck、候选 audit | 均 exit 0；只读验证，没有 build/stage |
| 完整 schema/goldens 导出 | 用新临时目录真实运行导出入口，**12 个文件的文件集合和原字节全部一致** |
| 真 worker/DSH 主链 | 技术页、作者页、新 revision 三条完整 prepare→record_output→ingest→原 reader→合法重试通过 |
| 原联合协议/权限/缓存反例 | **34 次 RPC**通过 |
| 旧材料 prepare 对照 | 正常 + 四类漂移共 **5 组**通过 |
| cap 重编 | 4096→1024 原 owner 重编及新 C00 投影通过；旧 cap 拒绝，prepare 网络/LLM 哨兵有效、发送 0 |
| GC 三终态矩阵 | 99 个拒绝 + 3 类正常提交/恢复，190 次真 RPC，exit 0 |
| patch hygiene | `git diff --check` exit 0 |

精确 argv/cwd/runner、起止时间、退出码、日志摘要见证据根 `focused.command.json`、`owners.command.json`、`ts.command.json`、`b02.command.json`、`audit.command.json`、`readonly-checks.command.json`、`joint-commands.json`。
pytest 禁用缓存并使用独立 basetemp；Node 使用现有 toolchain 的只读 stage:verify/test 及 `bwrap --unshare-net`。所有 provider 连接为隔离本地假 HTTP/SSE，未连接 8006 或外部模型。

owner 的 **4355 passed / 3 skipped / 7 warnings / 12 subtests** 全静态日志、argv/exit 和冻结输入已核验，**本轮没有重跑这份全量，也不把它写成独立执行结果**。三项 skip 明确为未启用 live，本阶段必需 AT 无 skip。其通用 owner 抽取在前次已独立审查，本轮保留并重跑受影响集合。

| 身份（SHA-256） | owner 新封存 | 本轮 QA 新采集 |
|---|---|---|
| engine | `11b8bf42a49c28ab0ba366735e0a69a1f1384c0414b573689e67dab85fdc68ea` | `4e3969503b6ea37f4e0aa3348de0b8ecaaaad51d281b81b59e62f342d8a8e1b8` |
| validator | `a0f57a2583a65403b4231e37a0a7da835f01ef846a0db348be386c51ff62badc` | 相同 |
| composition，4096 cap | `5a750f7846b34bd0ee2a35a894dd0fce48051b8c42f11df8f78c026812926a07` | `e62f3bd3591ac29debb7024350d4a6dae5aa0d6767b90d3aeeb7b854a5bcd9c3` |

差异来自 owner 释放后声明的五份已有协调文件更新和一份新增交付报告；代码、测试、schema、fixture 相同。QA 使用新身份重建全部新 effect，没有沿用旧组成合同。联合 driver 只改输入定位/新输出根和日志预先脱敏，断言未改变，逐文件差分在 `joint-drivers/*.diff`。

接受的开发候选仍为 `0.2.0-rc.1+loop-origin.1`：

- runtime：`671daa1a7a06728d69a4bdec6da3d33a3616c4e788f63579ed07f3ae81e0e16c`；原运行库字节保留。
- build receipt：`cbe3da5b3198516f184b7f6fe0a228fc56c7ffa69c27bf7060505bf77a2a7985`。
- stage：`b820ceea431868271687a0f4f1aca57d3ceb6ab9ba4fe18376fd50b602ca0e61`。
- peer 指向上述交付候选；本轮未重建 source-built 候选，未改日常安装/profile。

## 4. 封存审计、原 AT 及局限

owner 总包 **34,902 项（34,865 文件、37 链接）**的原字节/长度/链接、精确文件集合与外部封印全部复核通过；清单 SHA-256 为 `ac40483b1cdaca1759906df205410f0f45cbb4b3a7919a4242aad6c07fa8e852`，delivery-index SHA-256 为 `16d9324f42a2d13ba519b0477f83d0bd6949acf562890e54b0dd6dd13f3449e0`。

窗口二内层 5,005 项清单中，复制进总包的三份日志经过总包再次脱敏，因此不能直接拿内层原件摘要验证脱敏副本。本轮逐字节确认原件符合原清单、三处均列入 `log-redactions.json`，且副本恰好等于登记正则变换；总包最终摘要匹配。最初严格校验的 exit 1 保留为作用域校准记录，后续 `package-verification-reconciled.json` 与 `package-verification-final.json` 解释并关闭所有差异，不改 owner 封存。

同理，1,038 项冻结源与当前树之间的五处差异均是声明的已有协调文件更新；第六处是封存后新增报告，本来不在 source 清单。当前源码、schema、测试未漂移。不存在用文档身份变化掩盖生产差异的情况。

六项 AT 的完成依据为：I01 实际组成/漂移/validator 来源；C01 双向严格 wire 和明确字符规则；C00 真实公开 renderer→loop→实际 pi-ai wire、native 终态和零发送 prepare；C02 原三路径解析、合法技术/作者页、新 cap 与新状态；C03 原始来源、14 项依赖、新提交与合法缓存、唯一终态、原 reader；C04 真进程短协议、scope/权限/帧限制及取消边界。专项节点和实际联合矩阵同时成立，故可完整登记 Gate-C。

本阶段允许受控 Host fixture；生产持久 claim、预算 reserve、完整 Host pump 与真实离线准入回执仍归第 04 份。当前通过不证明这些后续能力存在；也不证明语义/reverse validation、主图迁移、多步并发、真实 Qwen 兼容或默认切换完成。

## 5. 读集释放、状态登记与下一批

**2026-10-04 00:15:40 +08:00 明确释放 QA 读集。** 2,114 项输入的字节/metadata 前后一致，最终实际 composition 完全相同；全部行为验证命令返回，相关宿主验证进程 0，真实 worker 进程组消失、fake server/child/Session/bindings 关闭。原始释放在证据根 `read-set-release.json` 与 `host-process-release.json`，逐运行释放另有真实产物。

本轮没有修改生产源码、测试或构建，没有切分支/reset/clean/commit/merge。释放后更新本报告、下一批指令、索引/台账/兼容与实施记录；这些协调修改会改变后续 engine identity，不把 QA 测试合同改标给新工作树。

登记 I01/C01/C00/C02/C03/C04 done，关闭三个原问题，原依赖/AT 不变。第 04 份七项仍 planned、具备实施前置；详细修改落点、全套负例、两窗口交接、命令与封存、可直接转发的指令全部见 [第 04 份整批执行指令](stage04_batch_execution_instructions_20261004.md)。

实施顺序为 **R01→R02→R03→R04→V01→A01→V02**，以一个完整离线包交 Gate-R/V；没有逐 helper 重新请示的要求。窗口一持 Python/协议/validator/原账本与 A01 写权，窗口二持 TS/Host/CLI 和唯一 build-stage 写权。L01 保持单独的具体 live 授权边界。
