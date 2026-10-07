# 第03份 Gate-C 三组集中返修交付

> 后续独立裁决（2026-10-04）：[Gate-C PASS，GC-1/2/3全部关闭](stage03_gc_repair_acceptance_20261004.md)，六项登记done。下文保留owner提交时的状态与冻结身份；原封存未修改。下一批见[第04份整批指令](stage04_batch_execution_instructions_20261004.md)。

2026-10-03，窗口一/窗口二完成 GC-1/GC-2/GC-3 集中返修并重新封存，状态为 **submitted_for_independent_qa**。前次独立 Gate-C 裁决 **CHANGES_REQUESTED** 保留；本包等待独立复验，不自登记 PASS/done。49 项仍为 **11 done /6 in_progress /32 planned**，第04份未启动，真实模型/8006、默认切换、D5及发布未执行。

实施范围与验收依据：[集中返修指令](stage03_gate_c_review_and_batch_repair_20261003.md)全文和原第03份六项 AT。原 r2 和独立 QA 包未覆盖；本报告是新 owner 记录，不改写其历史结论。

## 冻结包及身份

新包：[delivery-index.json](../../.dsh-dev/run/stage03-gc-repair-w1-20261003/final-delivery/delivery-index.json)，
[AT/GC 矩阵](../../.dsh-dev/run/stage03-gc-repair-w1-20261003/final-delivery/at-matrix.json)，
[SHA/字节清单](../../.dsh-dev/run/stage03-gc-repair-w1-20261003/final-delivery/archive-manifest.json)，
[外部封印](../../.dsh-dev/run/stage03-gc-repair-w1-20261003/final-delivery-seal.json)。
清单覆盖 **34,902 个文件/链接**，包括 delivery-index；清单本身由外部封印绑定，避免循环摘要。
清单 SHA-256：`ac40483b1cdaca1759906df205410f0f45cbb4b3a7919a4242aad6c07fa8e852`。
全部项目的原字节/长度/链接目标、索引与清单摘要、精确文件集合已重新读取核验，见
[archive-verified.json](../../.dsh-dev/run/stage03-gc-repair-w1-20261003/archive-verified.json)和同根 verification/ 的实际核验 driver/命令/log。

| 身份 | 本批冻结值，SHA-256 |
|---|---|
| engine | `11b8bf42a49c28ab0ba366735e0a69a1f1384c0414b573689e67dab85fdc68ea` |
| validator | `a0f57a2583a65403b4231e37a0a7da835f01ef846a0db348be386c51ff62badc` |
| composition，4096 cap | `5a750f7846b34bd0ee2a35a894dd0fce48051b8c42f11df8f78c026812926a07` |
| build receipt | `cbe3da5b3198516f184b7f6fe0a228fc56c7ffa69c27bf7060505bf77a2a7985` |
| stage | `b820ceea431868271687a0f4f1aca57d3ceb6ab9ba4fe18376fd50b602ca0e61` |
| runtime，原字节保留 | `671daa1a7a06728d69a4bdec6da3d33a3616c4e788f63579ed07f3ae81e0e16c` |

保留分支 `codex/agentic-p4-benchmark-cutover` / HEAD `d48b4e4b22c94c82b45d2179ba452d72b164102d` 与原 dirty 基线，没有提交或切分支。
source/ 下是本批生产代码、schema/goldens、测试/fixture、实施前冻结协调输入的实际副本；runtime/ 为实际 Loader/peer/bundle/Node/Python依赖及构建字节，原 symlink 关系和路径映射记录在 runtime-root-references.json。窗口二源码/测试、平台与 runtime 字节、完整165项和 B02/audit、原始 native 运行材料整体消费于 window-two/。repair-diff-against-qa.patch 提供相对独立 QA 冻结代码的实际修复差分。

## 修复与真实入口证据

| 问题 | 修后行为及验证 |
|---|---|
| GC-1 | 所有 Identifier 共用 `unicode-white-space-nonblank/1`，明确25个 Unicode White_Space 码点；Python全 scalar census与原 Rust `\\S` 接受域相同，FEFF/001C–001F合法，NEL/NBSP/行段分隔纯空白拒绝。TS消费版本/字符集合，拒绝未知规则，长度保持 Unicode codepoint。28个扩展 goldens、12个真实 native 正反例通过；非法不 callback/conclude、不自动第二次请求；合法 FEFF/ASCII 另经真实 worker `task.record_output`，不是只测 helper。 |
| GC-2 | `check_frozen_current` 在 render、初次 prepare、owner recompile 返回后及 seal/返回前复核 scope/revision/snapshot/fence、实际身份和 refs/request/page/manifest 一致性。真 worker 的 revision/fence/snapshot/组合过期均以 `frozen_revision_snapshot_or_fence_stale` 拒绝；同调用 Host 变化以 `task_revision_or_fence_stale` 拒绝；旧重编输入拒绝。合法同状态、owner 正常新冻结 revision2/fence1、4096→1024原 owner 重编均通过，不修改旧 frozen 元数据冒充来源。 |
| GC-3 | NEW ingest 在授权、scope/输出完整性、合法已提交缓存分支之后，复用 C02 投影/计量/真实 wire 核对，消费 projection/measurement/wire_equivalence/comparison/loop_request/provider_wire 的原字节、长度/hash、scope/media/schema及语义摘要、input/material/model/options/cap/组成/renderer/tokenizer 绑定。完整14个依赖以 `LocalWriterDependencyClosureV1` 写入 provenance，原 manifest read_set 同步记录。三终态真实 worker 共99个负例和3个完整提交/恢复正例，190次RPC通过；拒绝期间无 active/generation/receipt，仅有本地锁。 |

GC-3覆盖六必需引用的缺失/损坏，全部引用的长度/摘要/scope/semantic/version反例、来自另一实际合法1024 cap C00投影的错绑定；draft/research_required/blocked均覆盖。comparison/loop/provider原始请求没有自造版本，按其实际结构与绑定拒绝不兼容载荷。错误码逐例记录，含 `artifact_unavailable`、`artifact_bytes_mismatch`、`artifact_scope_mismatch`、`artifact_semantic_mismatch`、`schema_invalid`、`wire_comparison_mismatch`、`projection_material_mismatch`。

[真实矩阵结果](../../.dsh-dev/run/stage03-gc-repair-w1-20261003/final-delivery/runs/gc-closure-unicode/results.json)及同目录 rpc-transcript.json 记录输入/回包；FEFF/ASCII/research-terminal 子目录保存实际 DSH/loop/pi-ai HTTP/SSE/adapter/session 及释放。draft、blocked、research_required 完整正例发布局部 pending_validation/blocked/waiting，原 reader 读回14项闭包。每类在准备引用已缺失、随后新 Host revision/fence 下均取回原不可变回执；授权先缓存和同 epoch 唯一终态不变。

runs/joint-technical、joint-author、joint-fresh-revision 为三条完整真实 DSH→prepare→record_output→ingest→原 reader→合法重试；runs/cap-recompile-zero-send 记录原 owner重新编译及两次先验真实C00观测，prepare回调期间Python LLM/socket哨兵有效；runs/stale-prepare 记录旧材料五组对照，runs/joint-negative 保留34次原联合负例。

测试中的局部 UNIT 引用图是明确 test double，用于快速反例，不计作真实 C00；真实证据来自以上实际 pi-ai 捕获。Host/owner生命周期 fault fixture 仅在测试子进程注入状态变化与重编返回值，没有生产开关。新增生产裁决均在已登记 validator 源文件中。

完整导出命令：`python -m tests.integrations.dsh.test_wire_schemas integrations/dsh/wire-v1`，覆盖八个模型 schema、native schema/enforcement、character-rules.json 和 goldens；WriterTaskContractV1没有增加字段或静默放宽旧版本。

## 同一冻结输入的验证与释放

[commands.json](../../.dsh-dev/run/stage03-gc-repair-w1-20261003/final-delivery/checks/commands.json)记录精确argv/cwd/runner/耗时/exit及每次source前后；原始log和226个精确节点保存在同目录。

| 命令集合 | 结果 |
|---|---|
| 指令§5五份 Python 专项 | 226 passed，exit0，无必需skip |
| 指令§5七份原 owner 回归 | 265 passed，exit0 |
| `python -m pytest -q -rs` | 4355 passed、3原live skip、12 subtests，exit0；7 warnings，635.22s |
| `python -m compileall -q src tests` / `git diff --check` | 均exit0 |
| 窗口二最终 typecheck→build→stage | 三步exit0，build-final-r2 |
| 完整 TS / B02 / candidate audit | 165 passed /48 passed /exit0，原93项保留，必需skip0 |

本批真实模型调用0，领域 prepare send0。所有行为验证命令和 worker 已返回，相关进程组消失；实际 Session/child/bindings关闭、假服务 server false，原 reader 在档案中再次核验，见
[release.json](../../.dsh-dev/run/stage03-gc-repair-w1-20261003/final-delivery/release.json)及 archived-reader-check.json。假端口39037重绑定成功。日志URL令牌在封存前脱敏，未保存provider认证header。

开发期 schema/fixture修正、并发源码修改触发的 composition_source_unstable/漂移拒绝，以及窗口二构建失败均单列 development-history，不混作最终通过。最终完整集合均在 engine相同且构建不再变化的输入上执行；r2的4234不是本批结果。

**读集于2026-10-03T23:46:17.464627+08:00释放。** 34,902项原字节与链接、冻结source/组成均核验一致后，才写本报告及协调索引。封存包不再修改；这些源内协调更新会形成新的当前engine identity，另记同根 post-release-coordination.json。旧身份只属于封存输入，QA在当前树创建新 effect 必须重新捕获组成，不能把本批冻结合同改标给新树。第04份继续等独立 Gate-C 放行。
