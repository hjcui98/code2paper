# Python 内核阶段证据（K04 收口 → K01 → K02 → K03）

> 2026-09-29 · 窗口一按 [02_kernel_publication_and_request_guards.md](02_kernel_publication_and_request_guards.md)
> 连续实施。命令/节点/退出码/日志摘要见 §6；每个单元的设计证据见
> [k01_registry_evidence.md](k01_registry_evidence.md) 与
> [K04_evidence.md](../../tests/integrations/dsh/fixtures/K04_evidence.md) §16。

## 1. 本阶段交付范围

| 单元 | 交付 | 关键合同/失败码 |
|---|---|---|
| K04 收口 | 真实发送前拒绝的**分类与计数**；unknown-send 在相位边界报告**原始**阻断原因 | `rejected_before_send`（不再只认 `attempt_limit_exhausted:`）、`primary_cause=presend_refusal_without_send`、`writer_phase_boundary_blocked:primary_cause=send_outcome_unknown:…:downstream_not_run=realizer,…` |
| K01 | 创建封摘要 / 加载验摘要分离；完整来源身份；record/pointer/schema 交叉核对；同 ID 不同来源拒绝；legacy 具名只读 | §3 |
| K02 | 不可变多成员 + manifest + 派生回执；媒体感知校验；文件与目录 fsync；锁内 CAS（expected-active + 持久单调 fence）；member→record→manifest 分离准备/激活 | §4 |
| K03 | 索引按**权威 active 指针**消费 manifest；读取时同一次读取复算 manifest 与全部成员并核对不可变 registration；媒体感知读取（JSON/Markdown/bytes）；投影损坏不改权威 active、修复不重提交 | §5 |

## 2. K04 收口（原两个账本问题）

1. **发送前拒绝的分类与计数**（owner `writer_attempt_ledger.py`，原 R02 文件；按本阶段
   §3 授权做"必要修复"）。修前：只把 `attempt_limit_exhausted:` 前缀认成发送前拒绝，
   真实合同拒发（页字节/材料具名 code）被读成 `settled`，计数器 `rejected_before_send_events`
   为空、`last_rejection_code` 为空、invocation 级结论退化成 `reserved_not_sent/no_events`。
   修后：判据是"回执自称未越过边界（`sent_to_caller is False`）**且没有任何
   provider-request 证据**"，于是
   * 计数器与逐 attempt 分类都具名计入（`rejected_before_send_events=(2,)`）；
   * `last_rejection_code` 带出真实 code；
   * 发送前拒绝**不进** `unvalidated_attempts`（没有可评价响应，不得被要求本地结算）；
   * 状态仍是"可继续"（`reserved_not_sent`，allowed 含 `release_the_reservation`），
     但 `primary_cause=presend_refusal_without_send` 不再谎报"没有事件"。
   最小反例与节点：`tests/regression_20260917/test_ledger_recovery_matrix.py::test_gap1_rejected_empty_measured_digest_is_not_accepted_or_reusable`。
2. **unknown-send 不得被下游预算错误掩盖**（owner `publication_method_writer.py`）。
   修前：崩溃遗留的未结算预留（11155 tokens）保留后，realizer 的剩余预算被压成负数，整轮以
   `unified_consumer_request_rejected:realizer:…budget_exceeded…` 终止，writer 的真实根因被掩盖。
   修后：相位边界用同一个归约结论 `reduce_invocation_recovery` 检查每个必需页，
   `send_outcome_unknown` / `ledger_corrupt` 直接返回
   `blocked` + `writer_phase_boundary_blocked:blocked_by_stage=writer:primary_cause=…:
   invocation=…:unknown_reservations=[1]:downstream_not_run=realizer,binder,section_composition,publication_audit`，
   下游一个都不跑。节点：`test_gap3_unknown_send_keeps_reservation_and_blocks_a_blind_resend`。

两个修复都在既有 owner 内，未引入新运行控制层，也未改 DSH RPC/事件协议。

## 3. K01（严格注册读取与完整来源身份）

设计与 AT 矩阵见 [k01_registry_evidence.md](k01_registry_evidence.md)。摘要：加载先比较
**声明摘要**与由声明字段重算值（不借模型 validator 重封损坏值），再按声明摘要定位磁盘不可变
record 并逐条比较逻辑内容；`registration_id` 绑定 producer/upstream/schema/完整逻辑内容；
同逻辑内容幂等（返回原 record），同 ID 不同来源与同路径不同内容拒绝；旧 `1.0` 走具名只读
reader（不迁移、不重写）。`authoring_artifact_registry.py` 进入 `VALIDATOR_BUNDLE_SOURCES`。

## 4. K02（不可变多成员发布与 CAS/fence）

| 合同 | 实现 |
|---|---|
| 冻结一代的成员集合 | `stage_publication_members` 内容寻址写 `artifacts/publication_members/<role>/<phase>/<member>.<token>.json`；同内容幂等、同路径不同字节拒绝 |
| manifest | `PublicationManifestV1`：role/phase/generation/成员（路径+字节摘要+语义摘要+schema+**media_type**）/`member_set_digest`/`read_set`/导出投影路径/自封摘要 |
| media 校验 | `application/json`（必须可解析 + producer validator）、`text/markdown`（UTF-8 文本）、`application/octet-stream`（不透明）；其它类型 stage 即拒绝 |
| fsync 顺序 | 成员与 manifest 用 `_durable_write`（文件 fsync + **目录 fsync**）；active 指针写入后 fsync 目录 |
| 状态提交 | journal：`reserved → validated → committed → registered`（`committed` 表示成员+manifest 已持久），**先持久记录再切换指针** |
| CAS/fence | `switch_publication_active`：排他锁（flock）内比较 `expected_active_manifest_digest` **与** `expected_fence`（持久单调，每 key +1），不符即 `PublicationCasError` 且**不写** |
| 分离准备/激活 | `prepare_artifact_registration`（只写不可变 record）与 `activate_artifact_registration`（只切注册表 active）；发布事务用前者，注册表 active 在权威指针**之后**切换 |
| 回执/重放 | `build_publication_receipt` **派生**回执（manifest + 权威指针 + journal 重建，无写入）；重放同内容 commit/switch 不新生产物、不改字节、fence 单调 |
| 故障注入 | `crash_at ∈ {after_reserved, after_member_write, after_validated, after_manifest_write, after_committed_record, after_registered, after_active_switch}` |

**g1 已在、g2 每个写点崩溃**（`tests/integrations/dsh/test_publication_generation.py::test_k02_g2_crash_at_every_write_point_never_replaces_g1`）：
每个写点都断言 g1 的成员字节与 manifest 字节逐字未变、权威 active 未被半成品替换；
恢复判定为 `uncommitted`（manifest 未落盘）/ `committed_unswitched`（manifest 可复核，
active 仍是 g1；用正确期望值重试 CAS 即可完成切换，不需要重发产物）/ `switched`
（切换已落盘）。成员缺失、角色混代、manifest 半写、成员/导出漂移、同 (role, generation)
不同字节、旧 fence、并发 CAS 均有具名拒绝节点。

## 5. K03（索引消费 manifest 与真实读取接线）

* 索引条目 `discovery="publication_generation"`，并带上 `publication_recovery` /
  `publication_members` / `publication_read_set` / `publication_fence`。
* **权威 active 只认持久发布指针**：注册表只提供来源身份。`committed_unswitched` 的下一代
  即使 manifest 已落盘、registration 已准备，也只能是 `superseded`；旧 active 不被"已登记"
  本身替换。仅"已准备未激活"的 manifest 也通过磁盘枚举可见（崩溃在激活之前的情形）。
* 读取（`read_artifact_validated`）在同一次读取里：复核整代（manifest 摘要 + 每个成员字节
  + 成员集合摘要 + 导出投影）、核对**同一 manifest 的不可变 registration**，再按媒体类型
  返回 `members`（JSON→对象、Markdown→文本、bytes→base64）与 `member_digests`/`member_media`；
  任一步不符即 `artifact_generation_invalid` / `artifact_registration_drift` /
  `artifact_member_bytes_changed_since_read` 等具名拒绝，不回退到"反正有 active"。
* 投影损坏不改变权威 active；修投影不需要重提交（成员/manifest 未变，复核恢复即可）。
* 旧注册表默认 fail-closed（索引条目 invalid），`allow_legacy_registry=True` 才走具名只读。
* **未声称全文 Writer 已事务化**：`publication_method_writer._write_publication_outputs`
  （`src/code2paper/agentic/publication_method_writer.py:27974`）仍分别写 Markdown/authorship/
  checkpoint；局部 Writer 事务归 C03，全文迁移归 F02。`publish_artifact_transaction` 的现用
  调用者是 `authoring_execution_identity.py:1673` 与 `autonomous_method_agent.py:4120`，
  两者都进入 §6 的真实调用方回归。

## 6. 命令、节点、退出码与日志摘要

补证根：`.dsh-dev/run/w1-kernel-stage-final/`（未跟踪；不覆盖任何旧日志）。
脚本 `.dsh-dev/run/w1-kernel-stage/run_kernel_stage.sh` SHA-256
`e3be04ec79385616f0c88efd1adc9decb6d90c145008e25ffe4deb028aa401f6`
（`STAGE_OUT` 选择输出根；第一次运行落在 `w1-kernel-stage/`，其 S6 曾报出
`test_publication_transaction.py:187` 的多余空行——已修，最终代码状态以本根为准）。

| 日志 | 范围 | 退出码 | 结果 | 日志 SHA-256 |
|---|---|---|---|---|
| `S1_k04_closure_and_gaps.log` | K04 收口 + G1–G7 + GAP-1/2/3（两份账本套件、legacy characterization、closure、page recheck、formalization guards） | 0 | 27 passed（节点名在日志里，另有 176 deselected） | `8fe22eda848df18d9f6ddbd0d129a5b60f57349a1cb386bf3f740936eb3be01b` |
| `S2_k01_registry.log` | K01 AT 全集 | 0 | 15 passed | `97e0cdfbde79ebd647e7d591f1eb263cca634d1066e2b1bfa6601584db428298` |
| `S3_k02_publication.log` | K02 多成员/CAS/fence/崩溃矩阵/媒体/回执 | 0 | 8 passed | `2c2c223e5ccb600676bbddecd4f4fe34d7ee2c5fbea670d7d13ec4718dc2805e` |
| `S4_k03_real_reader.log` | K02+K03 真实 reader 故障矩阵 | 0 | 24 passed | `639c600bb391ca015c3cd60f73e67d47c17209aac3b0ae9cff1b0e0951e141ae` |
| `S5_real_callers_identity.log` | 真实调用方（publication/doctor/autonomous/vertical）+ 身份敏感性（execution identity、validator bundle） | 0 | 89 passed | `87afe3d01db41ebc484d70f2d06c89abf2202ab74f88756a7ce762d25bfb64b7` |
| `S6_docs_patch_check.log` | `git diff --check` + 范围界定链接检查 | 0 | 空白 0；本阶段文档链接 0 悬挂 | 该目录内同名日志（文档定稿后重跑） |
| `S7_identity.log` | 23 个阶段候选摘要 + validator 来源清单 + golden | 0 | 见 §7 | 该目录内同名日志（文档定稿后重跑） |

每个日志同目录有同名 `.exit`（内容 `0`）。S1–S5 的摘要是**最终代码/测试状态**下的结果；
S6/S7 只依赖文档与身份读数，在文档定稿后重跑，摘要以目录内日志为准。

另有一次同代码状态的**全量静态套件**（K04 收口后、K01–K03 落地后，多出的两条 K02/K03 断言
为测试专用）：`python -m pytest -q -p no:randomly` → **4114 passed, 3 skipped, 12 subtests
passed**，exit 0（10:23）。零失败、零 error、无超时；3 个 skip 为既有平台跳过项。

## 7. 身份、读集与写权

阶段候选 SHA-256（完整清单见 `S7_identity.log`）：

| 文件 | SHA-256 |
|---|---|
| `src/code2paper/agentic/writer_attempt_ledger.py` | `6046464f5d710beb46b863c86c1d4050b6a3262a754a7741cd86c720d5ee0d2e` |
| `src/code2paper/agentic/publication_method_writer.py` | `c8412d001aa210c301745a309f9db7f0b11a2d0c33c07b17090ee0a8a25cc4d9` |
| `src/code2paper/agentic/authoring_artifact_registry.py` | `b8a5588e3de1660e9cc2365558dfb6dc61532f6774254d372644952aebf567f4` |
| `src/code2paper/agentic/authoring_artifact_publication.py` | `ab8e870f825de2f3a229517b2fbb19f52b9bf177affb88ae691c9c0a0d9ecb8a` |
| `src/code2paper/agentic/authoring_artifact_index.py` | `3f018ae5f68f77cafa272d546847fcf46b90afc4acfeef59024bad7314fb6fc7` |
| `src/code2paper/agentic/authoring_execution_identity.py` | `48ce6928a6786e5641c7fe83191a216b34517460003749b0c97e4bec3045f4b0` |
| `tests/regression_20260917/test_artifact_registry.py` | `536f56d547702e35b342c37bb56c6093ca247e46b5cf4b449a9126e850e90f43` |
| `tests/regression_20260917/test_artifact_index.py` | `da450a9fe65d486c0151a6e627c46d4b956cbc213e5659652059d4784195f65a` |
| `tests/regression_20260917/test_publication_transaction.py` | `26dd8e3d922d3195dad013287a1c3719c1f25fd8c7dd412c9b6486c080d40b27` |
| `tests/integrations/dsh/test_publication_generation.py`（拟新增） | `25381791f59b3f990cd33eaf9029e350ab4d67f331695a500716cd52d3350401` |
| `tests/regression_20260917/test_ledger_recovery_matrix.py` | `19ec39c5fa99d6bdd19e72968abd464cae62bc46bbc35de807b73abe5faa9303` |
| `tests/integrations/dsh/fixtures/K04_evidence.md` | `7592484a3d796b586fd928fbbd874df72e4fab85e4e7655fab2ba0a67d4a3f40` |

`VALIDATOR_BUNDLE_SOURCES`（10 项，`failure_code` 空）bundle digest：
`sha256:bb9b903872d0233bc9f7108fc41d62653b312a2ff5d43fdea66333f07901a8ec`
（新入清单：`page_contract_recheck.py`（K04）、`authoring_artifact_registry.py`（K01）、
`authoring_artifact_publication.py`（K02）；`authoring_artifact_index.py` 原已在清单内）。
K04 释放的 `page_contract_recheck.py` `62a01ead…`、`unified_context_compiler.py` `9855889e…`、
`unified_context_models.py` `99fbce7e…`、`formalization_agent.py` `d8472634…` 本阶段**未变**。

**写权释放**：本阶段 owned paths 并集内改动，未触碰 `docs/dsh_execution_20260928/task_board.json`、
`docs/dsh_execution_20260928/verification.md` 或其它阶段的文件；共享的
`authoring_execution_identity.py` 仅按卡序串行添加三行来源清单。阶段结束不再写入。

## 8. 未测与边界

1. 未做**多进程真并发**的 CAS 竞争注入：锁 + 期望值顺序语义已由"同一期望值两次切换只有
   一次成功"覆盖；真实多进程竞争留给 QA 阶段复验（如需，可在同一脚本里 fork）。
2. 媒体类型只覆盖 JSON/Markdown/octet-stream；其它类型显式拒绝而不是猜测。
3. 导出投影只校验"与某个成员字节相同"，未覆盖"投影本身就是另一种渲染"的形态
   （生成式导出属 C03/F02 范围）。
4. legacy `1.0` 只读路径按"字段集与 `2.0` 相同"实现，见 K01 证据 §4。
5. 全文 Writer 仍未事务化（§5 末）；本阶段不据此宣称正文级原子发布。
6. Gate-K 尚未申报：K04 独立 QA 标记、K02+K03 联合独立复验、原前置 `B01,H03,H04` 与
   Gate-H 均未由本窗口自批。

## 9. 2026-09-30 整包返修（窗口一新实施者）

本节追加在原 §1–§8 之后。原 S1–S7 日志、`w1-kernel-stage/` 与
`w1-kernel-stage-final/` 保持原字节。本窗口不把旧 4114 数字当作可审计全量通过。
不自登 K01–K04 PASS/done，不申报 Gate-K。

### 9.1 接管

分支 `codex/agentic-p4-benchmark-cutover`，HEAD
`d48b4e4b22c94c82b45d2179ba452d72b164102d`。Python
`/home/cuihengjia/miniconda3/bin/python` 3.13.9。接管时责任路径没有第二个 pytest
写者。读集按 verification §8.1 已释放。未改 `task_board.json`、`verification.md`、
TS、peer、build、stage。

### 9.2 旧 23 项与最终 12 项

两份清单都还在，成员不同，不能互相覆盖。

| 清单 | 位置 | 项数 |
|---|---|---|
| 阶段目录 S7 候选块 | `.dsh-dev/run/w1-kernel-stage/S7_identity.log` 第 3–25 行 | 23 |
| 最终目录 S7 | `.dsh-dev/run/w1-kernel-stage-final/S7_identity.log` 第 4–15 行 | 12 |
| 本文件 §7 表 | 上文 §7 | 12，与最终 S7 不是同一集合 |

23 项含 page recheck、编译器、receipt 模型、formalizer、两份账本测试、legacy
characterization、三个 probe、K04 证据，以及两份证据文档。最终 12 项只留
ledger/writer、registry/publication/index/identity 和四份发布测试加两份证据文档。
§7 表则用 matrix 与 `K04_evidence.md` 换下了那两份证据文档。本返修不改这些历史摘要。

### 9.3 本批行为

| 条款 | 节点 | 结果 |
|---|---|---|
| 回执未发送但 request 存在 | `test_unsent_receipt_with_request_evidence_is_not_releasable` | `send_outcome_unknown` / `send_claim_conflicts_with_persistent_evidence`；发送计数 0；禁止 `assume_not_sent` 与 `silently_retry` |
| 回执未发送但 response 存在，验收自称接受 | `test_unsent_receipt_with_response_evidence_is_not_accepted` | 不进入 `accepted_reusable`，不记发送成功 |
| request 损坏 | `test_unsent_receipt_with_damaged_request_is_ledger_corrupt` | `ledger_corrupt`；不退款；禁止拿新预算 |
| 合法未发 / 未知发送 / 预算耗尽 | `test_named_no_send_unknown_and_budget_exhaustion_stay_distinct` | 仍分别是 `presend_refusal_without_send`、`request_persisted_without_completed`、`content_attempts_exhausted:` |
| 冻结 `0918ee76` owner 生成真实 1.0 | `test_k01_frozen_0918_owner_bytes_stay_read_only` | 隔离子进程；具名只读；指针与 record 前后字节不变；损坏的 2.0 不降级 |
| 实际持久点 | `test_k02_persistence_points_name_real_owners` | 成员写点是 `after_member_durable_write`；回执 `derived_no_write`；导出投影不是 commit 写点 |
| 子进程退出后新 reader | `test_k02_subprocess_exit_at_real_write_points_recovers_in_a_new_reader` | 退出码 86；成员写点后仍读 g1；manifest 写点后 `committed_unswitched`；指针写点后 reader 读 g2，注册表 active 仍是 g1 |
| 双进程 barrier CAS | `test_k02_two_processes_race_the_same_fence` | 恰好一个成功、一个 `publication_active_cas_failed` 或 `fence_stale`；新进程 fence=2 |
| 三方 active 分歧 | `test_k03_reader_trusts_publication_when_registry_and_index_diverge` | 发布 g1、注册表 g2、索引路径 g3；reader 返回 g1 |
| 投影损坏与修复 | `test_k03_projection_repair_does_not_resubmit` | 权威指针与 manifest 字节不变；修好导出后不新增 generation、fence 不变 |

原顺序两次 CAS 与本进程 `PublicationInterruptedError` 测试仍在。半写 manifest 的读取拒绝码现为
`artifact_publication_authority_unreadable`（权威 manifest 自身不可解析，不回退）。

冻结 owner 依赖身份（git blob）：

| 模块 | `0918ee76` blob |
|---|---|
| `authoring_artifact_registry.py` | `8b37f5719e473b17a1989bbdfe7408a66cf958f4` |
| `digest.py` | `1d22de99a30956af37b518d4e1ea1f29e0565853` |
| `tool_runtime.py` | `758d3d1d55900371edcd7af966a9d7ed56e23eaf` |

`authoring_artifact_registry.py` 与 `authoring_execution_identity.py` 本批字节未改
（registry `b8a5588e…`，identity `48ce6928…`）。真实 1.0 已能被现有具名 reader 读出。

### 9.4 命令与日志

根：`.dsh-dev/run/w1-kernel-rework/run-S1sPM01x/`。退出码来自各命令的 `.exit`，
没有用尾部 echo 判断。`first_failure.txt` 不存在。

| 命令 | argv | 退出码 | 日志 SHA-256 | 结果 |
|---|---|---|---|---|
| focused | `focused_kernel.argv.txt` | 0 | `84d20a2f06d93f2604542dc8ae69603734e266263b9d88d5c5f2bdb6d7c8910e` | 99 passed |
| `python -m pytest -q -rs` | `full_static.argv.txt` | 0 | `5f5b525dca1b8a6d36eaca0e90b82de1b4a88a70b3ab01f28ee992cf65940814` | 4125 passed, 3 skipped, 12 subtests passed |

三次跳过都是既有 live 门，不是本阶段 AT：

- `tests/test_agentic_gemma4_live.py:36`：`set CODE2PAPER_RUN_LIVE_LLM=1`
- `tests/test_agentic_gemma4_live.py:44`：同上
- `tests/test_agentic_gemma_supervisor_backend.py:1523`：同上

### 9.5 本批候选摘要

| 文件 | SHA-256 |
|---|---|
| `src/code2paper/agentic/writer_attempt_ledger.py` | `797878c17a98de0bcae886c8bb8abe8c28c098aa7836f176c19dfa5a3ad38721` |
| `src/code2paper/agentic/publication_method_writer.py` | `0e59fe98592c3ad311cf53be40817d8fddc02660cad3ff9cb07377e24fd84a23` |
| `src/code2paper/agentic/authoring_artifact_publication.py` | `201cb8c321b3bf726e0447ef43bc930cc39bdaeda791838f44b7362d65f34879` |
| `src/code2paper/agentic/authoring_artifact_index.py` | `7aef9f83b30fda3eda2a59f0afa671ae3fa49f52478fd0efb604f23634153d14` |
| `tests/regression_20260917/test_ledger_recovery_matrix.py` | `5cde7afb83f8bafd52ffc12c1eb01a1c10c01558d9b3c7ded68a278f2a3427bd` |
| `tests/regression_20260917/test_artifact_registry.py` | `5bc814ebc0a69192e2dea6ba68813f11a22ec92abfeca3ee4e78b7936dc1d5cd` |
| `tests/regression_20260917/test_artifact_index.py` | `0e8e58dca98e2cee50b791e27ebd073ac1cbf72731019251a0286f7780085360` |
| `tests/integrations/dsh/test_publication_generation.py` | `1e8133ebe3101715673e9566e2f392cd9d352b10139503acdef5f76ef6fd1191` |

### 9.6 未测与写权

未测：断电持久性（子进程 `os._exit(86)` 只证明进程消失后的恢复）；C03/F02 全文
事务；DSH RPC；live。导出投影的生产写入不在 commit owner 内，核验点是
`verify_publication_generation`。派生回执没有写点。

**写权释放**：本节写入后，本窗口停止修改第 02 份责任路径。LEAD 台账与裁决未改。
未 commit。Gate-K 仍待独立验收和原集成前置。

## 10. 2026-09-30 验收反例返修（K-1 / K-2）

§9 的 1.0、退出恢复、barrier CAS、三方 active 和投影修复继续有效。本轮只闭合
验收重放和验证后重读 manifest。QA 反例保留在
`.dsh-dev/run/qa-stage-review-20260930-izdz_5y3/lead/`。

| 条款 | 节点 | 结果 |
|---|---|---|
| 冲突后不能再发布接受重放 | `test_matching_replay_cannot_cover_a_conflicting_send` | `validation_replay_refuses_conflicting_send_evidence`；invocation 与 attempt 都是 unknown，`accepted=false`，预留保留 |
| 合法重放先落盘，之后出现矛盾回执 | `test_replay_recorded_before_a_contradictory_receipt_stays_unknown` | 重放文件保留，归约回到 `send_claim_conflicts_with_persistent_evidence`，发送计数 0 |
| 损坏账本不能带 accepted | `test_replay_cannot_mark_a_damaged_ledger_accepted` | `ledger_corrupt` 且 `accepted=false`；损坏后再发布重放被拒绝 |
| 验证后替换 manifest | `test_k03_replaced_manifest_bytes_are_not_read_as_the_verified_generation` | reader 拒绝 `artifact_manifest_digest_mismatch`；随后 verifier 报 `publication_manifest_digest_mismatch` |

正常 accepted、明确未发、未知发送和预算耗尽的原节点仍在同一矩阵里通过。
Writer 相位边界继续消费 `reduce_invocation_recovery` 的 `send_outcome_unknown` /
`ledger_corrupt`，因此冲突重放不会进入缓存复用。

读取期用 `bind_publication_manifest_bytes` 比较声明摘要、复算摘要和发布权威。
`PublicationManifestV1` 的创建期重封不能代替这次比较。

### 10.1 命令

根：`.dsh-dev/run/w1-kernel-rework/run-uBEIctQW/`。`.exit` 为真实退出码。
`first_failure.txt` 不存在。

| 命令 | 退出码 | 日志 SHA-256 | 结果 |
|---|---|---|---|
| 聚焦六模块 | 0 | `6becd0ea8d1d52b4da7f843622c44de00f4cad511eb7cf7018bbcd293dd29720` | 103 passed |
| `python -m pytest -q -rs` | 0 | `4bd9f61bc8fe5a9907c8ec3d3bea5db1cb896dfc7e1604b5569f63a446689902` | 4129 passed, 3 skipped, 12 subtests |

三次跳过仍是 `CODE2PAPER_RUN_LIVE_LLM`：`test_agentic_gemma4_live.py:36`、
`:44`，以及 `test_agentic_gemma_supervisor_backend.py:1523`。

### 10.2 本轮摘要

| 文件 | SHA-256 |
|---|---|
| `src/code2paper/agentic/writer_attempt_ledger.py` | `ca75779f238158d6377ad9336ca790b21bd498c4224d8b7084d2a5d4b53013f5` |
| `src/code2paper/agentic/publication_method_writer.py` | `83092a77ddbfbdf74605d739104507504d45ec75a9f21d3c5f662b58997c6c4e` |
| `src/code2paper/agentic/authoring_artifact_publication.py` | `57ee645b6622b994794bee69869a7d24ce4f0820008e7e309578fbc2ecc66ade` |
| `src/code2paper/agentic/authoring_artifact_index.py` | `cff1594eb00584466087d3a4a06dce02fe69461f8f2d83984b75b74823f33cc9` |
| `tests/regression_20260917/test_ledger_recovery_matrix.py` | `271d9037fde47853766c91363060d3d431c86d9adafd204dfa0db51553d9ef3c` |
| `tests/regression_20260917/test_artifact_index.py` | `dd407c67921a026a11b67b92a131968412bf001f5c0d85bb7ea65168fcb68eee` |

`writer_attempt_ledger.py`、`authoring_artifact_publication.py`、
`authoring_artifact_index.py` 仍在 `VALIDATOR_BUNDLE_SOURCES`。身份测试随聚焦套件通过。

未测仍是断电、C03/F02、DSH RPC 和 live。不自登 PASS/done，不申报 Gate-K。

**写权释放**：本节写入后停止修改第 02 份责任路径。未改 LEAD 台账，未 commit。
