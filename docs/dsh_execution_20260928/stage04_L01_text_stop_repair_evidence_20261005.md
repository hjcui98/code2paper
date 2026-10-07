# L01 packet11 普通文本结束返修证据（2026-10-05，进行中）

当前 24 done / 1 in_progress / 24 planned；Gate-L 未通过，M/P/G 正式实施仍受原独立门与读集释放约束。沿用[补充执行指令](stage04_L01_packet10_repair_and_continuation_20261005.md)及原 AT。Root 单独实现、直接执行真实测试；仅必要独立验收复用现有 reviewer。

## 已执行事实与身份

前一五组修复最终 engine `1ccece86beaff99ae4b1ac40a7a5c42a80c8561905845b8045ca60347bd4d48f`、validator `3f8c5bfcd89b88a5b7de998fbde18237db538446b4ceb299a5411f92f58086a5`。`/tmp/c2p-dsh-l01-admission-20261005-02` 完整1600和 fresh cold 通过两个原 reader，原 manager48049 exit0已回收；最终独立材料 review CLEAR/all readsets released，见 `/tmp/c2p-dsh-independent-l01-final-admission-packet11-20261005-01`。它们只证明绑定身份，以下新代码必须另冻结新证书。

用户明确授权 packet11 SHA `65f941c12d991d102a7f7c4b78a952b86caca3dbef748125c2b61eec56e962a5` / plan SHA `7a02a897fedd9122aa5676cee986fe44581a541d9da222cac213b6d047de533b`：1 primary、1非生成tokenize、retry/repair/aux0、32768输入/4096总输出/180秒、8006/GPU2、原观测费用结算及受信 normal-finish exact-owner release。实际原命令94723 exit1已回收；授权不复用或重发。包根 `/tmp/c2p-dsh-l01-packet-20261005-11` 保留原字节与授权。

实际 HTTP200、input7596/output1309/total8905/tokenizer7596、唯一stop/DONE；477 SSE frames，112709 bytes；delta.content 为普通 fenced JSON，tool_calls 分片0。旧 fetch observer在自然EOF归档之后拒绝stop，native Session记录 assistant/attempt+PI_AI_ERROR；没有native tool/call/result。原唯一账本已有usage，facts reserve/dispatch/adapter/usage/cancel，缺terminal+settlement，spent0/pending7596，taskcancelled/backendowned/domainreceipt null/providerquiescence null。不能把正文JSON转工具来源。

独立 `/tmp/c2p-dsh-independent-l01-packet11-postlive-20261005-01/{review.md,summary.json,verification.json,readset-release.json}` Gate-L FAIL，343实际输入SHA/长度，全读集释放后才修改源码。packet10 的 exact owner早已合法退役，其费用7463结清及领域失败保留；该原失败快照中的 held 为packet11；下述具名恢复后当前backend已empty，原领域FAIL保持。

## 同方向实现范围

- dev EOF观察允许唯一合法tool_calls/stop自然运输结束；missing/duplicate usage、tokenizer错配、异常finish仍拒绝。stop是否领域接受由原Host决定。
- Host先检查无terminal，再读callId；保存原native Session与独立text/plain，首因host_single_terminal_required。没有将正文解析/修复为tool参数。
- 单独 `DshRejectedTextProviderQuiescenceV1` + `DshRejectedTextFinishObservationV1`：private gated-adapter自然完成，活动execute claim登记；核对原scope/Session/请求config与tools、model source、所有text/reasoning block/delta、usage/finish/事件顺序和原唯一账本。recovery-only不能mint。缺/损坏证明继续pending/held；原工具类严格性不变。
- 具名 `text-stop-observed-fees-retirement/1` operator入口：绑定旧packet/grant/plan/bootstrap/request/claim/Session/SSE/tokenizer/已登记usage、当前实现、真实独立review与范围记录；追加原费用terminal+settlement及具名operator证据，不注册provider_quiescence、不改task/claim/正文。逐项不可变事件支持崩溃继续；exact owner事务内historyinsert/delete原子完成，损坏history/新owner拒绝。本次实际 canonical 操作及独立结果见下节；不代表领域接收。
- 明确 generic terminal 指令要求调用native function，禁止把JSON、code fence或模拟调用写在assistant正文。没有固定领域句子/源路径/答案或义务减少；不承诺模型必遵守。
- 新真实node entry和Python证明/历史恢复测试进入suite discovery，plan版本core/5、offline/5；实际新validator来源登记，不改旧证书标签。

## 实际验证与保留失败

外部主记录 `/tmp/c2p-dsh-l01-text-stop-repair-20261005-01` 保存修改前负责文件字节、plan、命令日志；现有dirty基线保留，未commit/切分支。

| 验证 | 原命令结果/行为 |
|---|---|
| typecheck02/build01/stage01 | exit0；初次typecheck01因putBytes类型声明缺text/plain而exit1，已修类型 |
| 新完成证明proof03 | 37pass/1.06s；包括schema/source/request/Session/raw/type/usage/order/finish/settlement反例，结构反例直接检查pre-settlement防止错ref掩盖 |
| native03 原launcher，`writer-text-stop.test.ts` | handle89012 exit0已回收；真实Loader/native/Session/worker/原账本与reader，1pass/0fail/0skip72.046s；仍领域拒绝，费用17结清/pending0/backendempty，fresh Worker零额外发送 |
| focused04 `test_text_rejection_completion.py test_host_recovery_boundaries.py test_coverage_use.py` | handle23566 exit0已回收；170pass/56subtests214.32s，原恢复与冷reader边界保留 |
| historical-proof05 | 51pass/1.22s，SSE/DONE/index/model/content/reasoning/usage/旧attempt-error链损坏拒绝 |
| operator08 | handle30431 exit0已回收；16pass67.18s，真实Worker/账本/SQLite UNIT fixture：幂等、task字节不变/new-owner/history/错授权/来源、terminal/settlement/history-delete崩溃继续且无双计费 |
| operator09 | handle7680 exit0已回收；106pass75.64s，补launch/start/tokenizer/原authorization绑定，三个新文件联合验证 |
| 原数据隔离恢复01 | handle82949 exit0已回收，engine55c4c450/validatored25，仅独立run/backend副本RW，rootRO/unshare-net；原数据完成费用7596并释放cloneowner。review/authorization明确fixture，**不代表真实review或canonical授权** |

native01在root同时新增test时因composition_source_unstable发送前拒绝，保留exit1；native02因新helper把合法model source的provider/model/replayState当非法字段拒绝，费用保持pending。改为严格匹配原请求provider/model后，仅原Session只读证明PASS；失败记录未覆盖。operator06缺pytest composition fixture，operator07最小UNIT loop缺provider使fixture装配KeyError，均未到迁移；修复测试fixture后operator08/09通过。完整native与focused期间源码不改。

准确日志/当前阶段见外部 `/tmp/c2p-dsh-l01-repair-execution-index-20261004-01.json`，测试数量不代替行为证据。

## 当前冻结实现的实际验证与原费用恢复

代码/方案冻结 engine `f61ce96fd5811aec66f24e43a56c384745e07dcd26730b22bddadc96426da880`、validator `7b77c88b240a561f077982637c9590e61358b5b9af94fdea1e7d9ddb5544a626`。focused10 原42977 exit0已回收，183pass219.64s；native04 原17352 exit0已回收，两真实原生entry（schema rejection/text stop）2pass/0fail/0skip149.624s。原数据隔离02按当前实现及35旧文件RO封存wrapper执行，原29237 exit0已回收；clone费用7596/pending0/backendempty，真实canonical未变；fixture批准不作为正式authority。

独立代码/具体计划审查 `/tmp/c2p-dsh-independent-l01-text-stop-code-plan-20261005-01` 实际439输入SHA/长度，code/plan PASS、原grant范围APPLIES、所有实际读集明确释放；真实review写入 `/tmp/c2p-dsh-l01-text-stop-recovery-package-20261005-01/independent-review.json`。plan `17bbbc47a72a08e2fba9c20e9d023176c3eff8e1993dfe9b5fcbb9af18ad4327`；wrapper `fb512109fdad7d30f6555f7a168486c146ec57f4c1a84fee6f61828fc0d60e2a`，rootRO/unshare-net，仅原run/backendRW、35旧run文件RO。原producer实际fetch reader.item.done→归档SSE→旧tool_calls断言错误链被实审，历史自然EOF不是idle或exit推断。

在实际review/readset release后，root派生原一次grant中观测费用+受信正常结束exact-owner释放范围记录，执行封存wrapper一次；原52748 exit0已回收，所有35原文件SHA/长度不变。仅新增具名operator evidence和确定accounting terminal/settlement，原prefix5、TaskDB/claim/cancelled状态、captured_source/receipt/provider_quiescence null、原packet/wire/SSE/Session/raw均未改；spent7596/pending0/completed1/call1，canonical empty。实际receipt `c607030e429b8a1e53679793d1df781684d7fd7ee7f942e2e778f91e11d85dfb`，不伪造execute/native/领域完成。

实际迁移结果独立 `/tmp/c2p-dsh-independent-l01-text-stop-migration-result-20261005-01` PASS，361实际输入SHA/长度；原verify_package/verify_original及task/ledger/budget/backend/history readers通过，四条actual history严格分类校验，三条旧记录与此前独立结果完全相同。所有实际读集明确释放后才进行本次文档收口。零新增模型/tokenizer请求，Gate-L仍FAIL。

## 最终版本测试同步

最终完整证书启动前只读检查发现两处当前suite版本断言和一处UNIT fixture仍为/4；同步为当前/5，保留原core/4和offline/2拒绝反例。生产源码未再改。`test_dsh_admission.py test_target_admission_integration.py` 原53668 exit0已回收，49pass25.19s；此处目标准入测试沿用原离线网络隔离，零模型请求。原拟03目录仅保存启动前旧freeze并明确superseded，完整未启动；最终fresh root改为 `/tmp/c2p-dsh-l01-admission-20261005-04`。

## 剩余门

当前代码/具体命令/原授权范围及实际恢复结果的独立门已通过并释放读集；原packet11领域失败和已消费生成授权保持。上节f61/7b77只绑定返修验证与迁移，文档收口后完整证书必须重新绑定最终身份。

随后关闭文档/版本/构建并冻结，跑一次新完整注册证书及fresh cold，准备实质变更的具体fresh packet并取得新一次授权。当前没有新的模型grant，不重跑packet11。独立Gate-L PASS+读集释放后才接M01–M03/Gate-M、P01–P04/Gate-P、G01–G03/Gate-G0、G04–G08/Gate-G；目标40/49，非D5/默认切换/发布。
