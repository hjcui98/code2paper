# L01 有界真实兼容执行协议（2026-10-04）

> 当前接续（2026-10-06）：[独立 Gate-L PASS](stage04_L01_acceptance_20261006.md)，25/49，packet26 waiting / actual usage 8055/441 / 后端自然释放。M01–M03 正式开发中；下文早期进度和授权条件按其历史快照解释。普通可逆决定直接执行，保留各阶段质量验收。

> **下一批按原长期模块 [§9 Gate-L 集中解阻](stage04_06_long_module_execution_20261004.md#gate-l-unblock-20261005) 执行。** 先统一验证显式非thinking的profile/worker/实际wire，保留强制原生c2p_terminal与原全部内容门；packet14错误流修复及具名abort/unknown恢复包同期闭合。一次收口后再冻结当前完整/cold与新包。下述low/1024及旧命令属于已执行历史配置；新方案已实施并有完整native隔离/本机grammar证明，完整10实际1867/cold1通过，但最终QA的U4类型绑定修复改变身份，当前新完整11与真实服务端验证仍待，旧授权不复用。

> **packet14 最新：** 服务端grammar错误、实际usage/finish缺失、费用UNKNOWN/原owner held，Gate-L FAIL。错误流计量与首因返修进行中；[当前证据](stage04_L01_provider_error_repair_evidence_20261005.md)。下方packet13状态为历史。

> **packet13 历史状态：** packet13 一次授权已消耗，普通文本/原生工具调用0，Gate-L FAIL；受信自然完成已登记、实际费用7699/pending0、原 owner 正常释放，canonical empty及六条严格history，独立生命周期PASS、实际读集释放。当前原生工具选择返修使用tool-choice.2开发候选；来源构建、wire对照、三项真实native及严格审计通过，统一关闭后冻结新完整/cold09。历史1803仅7f77/af9；24/1/24，M/P/G保持原阶段门。详见[原生工具选择返修证据](stage04_L01_native_tool_choice_repair_evidence_20261005.md)。

> **packet12历史执行状态：** packet12具体一次授权已消耗，UNKNOWN_TOOL领域FAIL保留。受信完成/诊断/历史退役经真实native及focused、原数据保护克隆；独立代码方案PASS/APPLIES和实际退役PASS，原费用7648/pending0、canonical empty，42非lease旧run文件及14原输入未变。读集已释放；当前关闭文档后冻结新完整/cold（05），历史1707仅9def/7b77。Gate-L FAIL、24/1/24；详见[未注册工具返修证据](stage04_L01_unknown_tool_repair_evidence_20261005.md)。

> **packet11历史恢复状态（后续packet13见上）：** packet11 一次生成授权已消耗，普通文本 JSON/finish stop、tool_calls0，领域失败保留。文本结束返修及具名原费用恢复经独立代码/方案、实际结果两次 PASS；原费用 spent7596/pending0，canonical backend empty，35旧文件、原task/claim/正文及provider_quiescence null保持不变。实际读集已释放；新完整注册证书及fresh cold待最终冻结运行。Gate-L仍FAIL，24/1/24；新模型请求需fresh packet具体一次授权，不重发旧packet。详见 [文本结束返修证据](stage04_L01_text_stop_repair_evidence_20261005.md)。


> **2026-10-05 当前状态与下一批：** Stage A 七项独立 Gate-R/V PASS，项目 24 done / 1 in_progress / 24 planned；长期模块 7/23 done。packet10 已消费一次具体授权，HTTP200、7463 输入/1182 输出、tokenizer 一致、费用结清；terminal 缺 schema_version 被拒，当次 Session blocked 触发旧完成凭据拒绝，原领域无回执。原 backend 的后续具名退役已完成，当前 empty。Gate-L 未通过：packet10 独立事后裁决 FAIL，读集已明确释放（/tmp/c2p-dsh-independent-packet10-postlive-20261005-01/readset-release.json）。五组代码及具体历史恢复方案已独立 PASS；原 exact owner 已按既有 normal-finish release 授权合法退役，canonical backend empty，费用不变且原领域失败保留。当前完整证书和新包具体授权仍待；证据见 [整批返修记录](stage04_L01_repair_batch_evidence_20261005.md)。Gate-L PASS 后连续推进 C–F。本指导不授权新的模型调用。 详见 [stage04_L01_packet10_repair_and_continuation_20261005.md](stage04_L01_packet10_repair_and_continuation_20261005.md)。下方准备态、packet02/09 和待审批表述均保留各自历史时点，不是当前动作指令。

前置：[Stage A 独立 Gate-R/V PASS](stage04_stageA_acceptance_20261004.md)。
本协议准备一个可审查的小型 Writer 请求；**没有批准推理调用**。真实执行前按原第04份取得对下列具体范围的授权，并复核匹配当前代码的新离线回执。

## 实际入口和输入

开发入口为 `integrations/dsh/dev/l01_launch.py` → `l01.mjs` → `l01_worker.py`。
仍使用原只读 sandbox、真实 Loader/DSH/native pi-ai adapter、原 Worker/Facade、TaskStore、唯一预算账本、terminal/Session、parser/Binder/composer/reader。私有开发 bootstrap 只通过已有 request_meter 注入点绑定冻结的实际 wire tokenizer 回执；不复制预算或领域裁决。
这三份执行/准入源码已加入原 validator 来源清单；生产默认入口和已验 staging 不切换。

输入为 B01 单页 scalar/rescale synthetic source，保留原 compiler、atom义务、公式包和离线 Formalizer provenance；不作为产品仓库事实或真实 Qwen Formalizer 成果。
隔离fake正式联测使用fresh task/backend和`isolated-fake:`资源键；真实packet使用候选`live-backend-admission`共享根与`openai:`固定物理模型键。原串行锁不自动释放，不能把假联测占用登记成真实模型占用，也不按PID/TTL清理任何旧锁。
正式 Writer 从模型生成；校准假响应仅返回具名 blocked，不提供 fixture Writer 标准答案给真实请求。
最终 packet 绑定 descriptor/bootstrap、实际 messages/tools wire、profile、launcher和执行源码的 SHA256/长度，以及完整 I01 composition。

## 数值和调用范围

| 项 | 固定范围 |
|---|---|
| 地址/模型 | `http://127.0.0.1:8006/v1` / `qwen38-27b-nvfp4` |
| context | 131072 |
| primary / retry / repair / title / compaction / probe | 1 / 0 / 0 / 0 / 0 / 0 |
| 输入上限 | 32768个实际model tokens；超限不发送 |
| 输出总上限 | 4096，包含思考及答案；不是额外4096答案 |
| 请求墙钟 | 180秒；stream idle 60秒；worker RPC保持原30秒 |
| 执行并发 | false；共享原 SerialBackendAdmission，每个fresh run唯一execution id |
| 真实tokenizer | 1次非生成`/tokenize`，原vLLM owner，精确messages+tools及chat-template字段；不以schema组件估算替代 |
| 预检/监控 | health/models/metrics各一次；请求期间metrics每10秒、单次5秒超时，最多请求墙钟范围 |
| 输出 | fresh packet目录，只执行一次；保留raw SSE、usage/finish、原Session、原账本和局部receipt |

计量先由真实 tokenizer 固定wire digest与token数量；worker模型/网络出口仍拒绝，正式dispatch之前复算绑定。
隔离假服务校准采用显式 `isolated_offline_placeholder`，必须验证不同网络命名空间且只有lo；该数值不声称Qwen计量。live必先替换为真实tokenizer来源，placeholder不能作为live准入。

## 实际 adapter 差异

已执行packet14及本次核验时的[专用profile](../../tests/live/profiles/qwen38_dsh_l01.json)选用temperature=0.6、reasoning_effort=low、thinking_token_budget=1024、max_tokens=4096、system/user角色、usage streaming、0 retry。

下一批目标为显式 `chat_template_kwargs.enable_thinking=false`、移除low/1024字段并保留具名 `c2p_terminal`；同时修复worker硬编码与prepare精确断言，重新生成相同模板字段的tokenizer投影。完整实施和验收以[长期模块§9](stage04_06_long_module_execution_20261004.md#gate-l-unblock-20261005)为准。当前profile/worker/prepare及原Facade发送门已精确绑定显式false，Writer reserve单独0、Formalizer1024保持；完整wire/安装模板grammar及native错误矩阵有隔离证据，尚未证明真实服务成功。完整10的1867/cold1保留历史原身份；U4集中修复后的新完整11与独立QA见当前证据文档。
关闭OpenAI developer-role/store投影以匹配本地服务及原冻结合同；实际校准wire必须逐字节匹配正式wire。
`thinking_token_budget`是发送字段，服务是否执行该细分限额由实际响应观察；4096是总输出硬限额。

当前DSH adapter不转发`top_p/top_k`，本次限定为上述实际可表达字段和服务默认sampling，**不等价于Python profile的top_p=0.95/top_k=20，也不验收这两个条件**。
如果操作授权要求这两个字段或完整Python-profile等价，本协议拒绝启动，先实现实际能力，不静默删字段。一次L01通过只覆盖其实际已测条件。

## 命令与冻结证据

以下命令和目录保留2026-10-04的历史绑定。当前执行须按[长期模块§9.6](stage04_06_long_module_execution_20261004.md#gate-l-unblock-20261005)核对实际candidate、注册计划与完整argv，使用fresh目录和当前身份；不得直接重用下列旧packet、receipt或authorization。

离线联测（真实模型0）：

```bash
python integrations/dsh/dev/l01_launch.py offline --output /tmp/c2p-dsh-l01-offline-20261004-07
```

冻结准备（仅独立namespace假8006校准、没有task claim或真实模型请求）：

```bash
python integrations/dsh/dev/l01_launch.py prepare --output /tmp/c2p-dsh-l01-packet-20261004-02
```

匹配当前代码的原完整离线证书由 `method-agent record-offline-receipt --suite-plan dsh-stage04 --candidate 0.2.0-rc.1+loop-origin.1` 生成到 `/tmp/c2p-dsh-l01-admission-20261004-02/receipt.json`，output-root为同根`managed`，原共享deadline4200秒。不将039旧证书重新标成当前身份，也不另跑一次全仓静态套件。
准确实际argv、退出码与报告由外部 execution-index 记录；本协议发布时这些最终命令尚待执行，不提前登记成功。

授权后唯一真实命令：

```bash
python integrations/dsh/dev/l01_launch.py live \
  --output /tmp/c2p-dsh-l01-packet-20261004-02 \
  --receipt /tmp/c2p-dsh-l01-admission-20261004-02/receipt.json \
  --authorization /tmp/c2p-dsh-l01-operator-authorization-20261004.json
```

authorization须绑定最终packet digest、模型、1 primary、0 retry、32768/4096、180秒及已获得的具体用户授权；实现者在实际授权后记录，不能由离线回执代发。
执行前原owner复算完整offline coverage/current engine/validator；原I01、task/claim、lease/reserve及send-time核验继续执行。离线许可不升级为真实模型权威。

## 停止和验收

启动前队列非空、缓存压力≥90%、health/models不匹配、身份或wire变化、输入超限均停止。
执行期间额外running/waiting、缓存压力、monitor失败或deadline中止；缺usage/finish/terminal、内容/公式/atom/authority失败按原owner拒绝。
raw usage需有效且与精确tokenizer input数量一致；usage缺失/损坏不得默认0。
未知发送保留原预算预留与后端占用，不退款、不重发；有已存响应只允许原确定性本地恢复。
DSH idle或本地worker退出不证明远端停机；cleanup分别记录原worker范围证明与实际provider stream观察。
最终由独立Gate-L检查真实tool参数、usage/finish、原文来源、账本和局部接收；未通过前不正式进入C–F。

## 2026-10-04 实际执行、独立失败与修复

packet02 的具体授权已由用户明确给出并消费：仅1 primary，0 retry/repair。原当前完整证书1476和fresh normal-entry通过，源码ad6c2522…与10个冻结文件核对一致；`live`原命令exit1。真实HTTP200，finish=tool_calls，usage7332输入/851输出，模型仍为8006/GPU2/qwen38。tokenizer7344与实际usage不一致，原发送链正确拒绝；原始result另为字符串且内部多一个`}`，原完整WriterTaskResultV1拒绝。没有局部receipt，没有发布。

独立[Gate-L报告](/tmp/c2p-dsh-independent-stageB-20261004-01/review.md)裁决FAIL/BLOCK/REQUEST_CHANGES，读集已释放；[恢复补充](/tmp/c2p-dsh-independent-stageB-20261004-01/recovery-addendum.md)明确旧输出不能修补为通过，旧授权不能复用。任务表保持24/49，C–F未正式准入。原账本读回call1/completed0/spent0/pending7344；canonical backend仍归该execution。原worker已关闭、Python拒绝哨兵模型/网络0、provider stream结束；后续只读health/metrics200且running/waiting/KV全0，空闲观测不释放持久占用。

零网络的实际本机tokenizer复现了原因：缺reasoning模板变量时7344，chat路径的reasoning_effort=low/enable_thinking=True时7332。修复只在原dev tokenizer投影中复现服务merge规则：top-level effort覆盖同名模板变量，显式enable_thinking保留；meter升级`/2`，旧`/1`拒绝。严格usage等值门继续保留。

实际DSH拒绝同时声明type与oneOf，故撤回该表示实验（隔离fake失败，真实请求0），改为原native schema支持的description明确object编码，三分支/full-schema guard保持。重新导出时还对齐原Python OutputEnvelope的既有可选session_capture_ref，未添加新正文或权威。旧live的无效参数仍拒绝。dev流观察保留首个错误及secondary Host错误；隔离重复usage场景已证明首因为missing/duplicate raw usage，假正式发送1、call1/completed0/pending保留、task cancelled/无receipt、worker关闭/模型0。

R04原owner新增`release_observed_finish`，仅在原terminal+settlement、完整已绑定finish/raw/session、零pending预算、单任务cancelled/terminal及exact owner成立时原子退役，并在同一SQLite事务留下不可变release history；没有PID/TTL或私有库绕行。聚焦恢复、claim、schema、计量107项及56 subtests通过；native annotation调整后计量/三分支拒绝19项通过。这里仅证明隔离测试，未调用该入口释放真实backend；新增readback只观察原task/budget/backend，必须在新提交包中封存。

原合同允许同cancelled epoch的settlement-only恢复，已准备[/tmp恢复脚本](/tmp/c2p-dsh-l01-recovery-20261004-01/launch.py)，用逐文件SHA匹配的ad6c只读source overlays运行原worker，网络隔离、保留原错误参数；不会改判内容或释放backend。自动审批拒绝执行，理由为共享账本的持久结算副作用需明确授权；已提交具体授权问题，目前未执行、预留未改变。

下一步先完成当前代码隔离正常闭环和匹配的新完整证书，再交新修复包独立验收。恢复须等上述授权；安全退役旧占用与任何新的primary也须按可审查具体范围处理，不能以本段文字代发。旧证书和packet02保留原身份，不重新标为当前修复源码。此记录发布时新的正常闭环/packet/完整证书尚待执行；不重复全仓静态、无变化build/stage或旧A验收。


### 原 owner 释放与恢复修复（2026-10-04；独立验收尚未通过）

两次有限独立复核指出：原 finish flag 不足以证明 provider 已结束，正常路径未接线；后续修复还必须去除 Facade replay 隐式 acquire、持久登记结束凭据、禁止 recovery mint 并保留第一错误。当前实现由原执行 claim 经私有 `backend.observe_quiescence` 登记实际 gatedAdapter 自然结束后的 raw/Session/usage 绑定；原 TaskStore 保存其 claim/fence/ref，success、rejection 和新 Worker 本地恢复消费同一记录。status/settlement/replay 只读，不重新占用退休 owner；unknown 无凭据则继续 held。只读/结算恢复不能通过 artifact.record 补造该 owner 记录。

原 Worker 有关幂等、后续 owner、伪造登记和三个跨进程结算 cut 的14项限定检查已通过；真实 native 接线、完整当前准入和独立复核仍待，不作为新的 Gate-L PASS。已被复核 BLOCK 的 managed03 在 Python部分通过后主动停止，exit130，未产生完整回执；保存日志，不复用其覆盖。以前的一次真实授权已消费。原共享账本 settlement-only 授权待答，尚未执行恢复或释放，也未增加真实请求。当前24/49，C–F正式前置未越过。


### 2026-10-04：必要旧 owner 退役实现的独立复核与集中修复

独立代码复核 `/tmp/c2p-dsh-independent-legacy-retirement-code-20261004-01/review.md` 为 BLOCK/REQUEST_CHANGES，已释放全部读集；三项必修为旧错误 Session 的 transport-only 边界、两类 release_history 行与回执/key 的绑定、以及可变外部执行脚本/argv/mount 的授权绑定。另补 task/bootstrap/原 claim lineage 交叉绑定。没有执行原任务。

集中修复后，legacy Session 拒绝任何 block-end/native completion，按原 reserve.reserved_input_tokens 与实际 usage 动态精确匹配 tokenizer mismatch 错误；原 bootstrap.scope、封存实际 child/session binding 与 claim_lineage 首个执行 claim 必须一致。原 bootstrap 的 child/session 启动前占位值不能冒充实际绑定，实际校验使用 attestation.task_binding 与原错误 Session。两类 history 均验证严格schema/self-digest/行key/key projection；legacy replay 必须等于当前完整 binding，所有历史行均先校验，冲突或损坏继续拒绝。

封存 plan 增加七类外部文件 binding 和精确 settlement/retirement argv。组合入口只运行已复核授权中的命令，先校验全部脚本/计划，started guard 禁止盲重跑；退役原任务目录 RO，仅现存 .run_lease.lock 最小 RW，canonical backend 为退役写入目标，产物位于任务专属 /tmp。入口和计划准备脚本语法校验通过，准备命令不执行副作用、不造授权。

稳定源码下验证：`python -m pytest -q tests/integrations/dsh/test_legacy_retirement.py tests/integrations/dsh/test_host_recovery_boundaries.py`，exit0，45 passed/56 subtests，189.22s；原日志 `/tmp/c2p-dsh-legacy-focused08-20261004.log`。覆盖 Session block-end/其他错误/计量改变、key损坏/不同binding/正常schema损坏、封存可执行文件漂移、bootstrap/child/lineage错配，以及原正常 release/跨进程结算恢复。此前focused07在源码修复期间出现 composition_drift，属非冻结运行，保留失败日志，不用于当前验收。`git diff --check` exit0。当前真实历史 transport 用修复后校验器只读验证通过，实际模型/原 task/原 budget/原 backend 新写入均0。

下一步交当前源码、实际 attestation 和精确执行 plan 做差分独立复核，再冻结当前完整注册证书与正常冷入口。组合结算+退役须明确用户授权，真实新增 primary 须另有最终 packet 的具体授权。当前24/49，Gate-L仍FAIL，C–F正式前置不变。


#### 2026-10-04 — 第二次差分复核后的最后一个封存边界修复

`/tmp/c2p-dsh-independent-legacy-retirement-code-20261004-02/review.md` 保留BLOCK，已关闭H1/H2/M1及精确挂载；剩余H3为执行前必须重验四份manifest的成员字节/目录闭包及其与sealed overlay argv的等价投影，读集已全部释放。新增 `verify_execution_mounts` 在每次 `verify_package` 内实际读回所有成员SHA/长度，严格schema/canonical path/唯一target/目录exact files+dirs，拒绝symlink与额外/缺失；settlement命令必须按目录再文件的封存投影以RO挂载，拒绝遗漏、重复、RW替代与后续覆盖。旧Node目录manifest增加historical_path字段，逐项对照原sealed evidence manifest后规范化，不改任何归档源码。实际147个归档成员及精确命令投影的只读校验通过，未执行命令。

UNIT执行脚本改用与att producer不同的文件以隔离新plan边界；claim反例保留原lineage长度和末项，只替换首claim；新增成员修改/缺失/额外以及RO→RW命令错配反例。`python -m pytest -q tests/integrations/dsh/test_legacy_retirement.py` exit0，17 passed/52.99s，原日志 `/tmp/c2p-dsh-legacy-focused09-20261004.log`。原正常退役/恢复代码自focused08以来未改，45/56的原证明仍按其身份引用，不无变化重跑；`git diff --check` exit0。packet06离线prepare exit0，但其源码身份早于H3最后修复，未授权且不作为当前live准入。原预算与owner仍未修改，新真实模型请求0。待最终差分独立复核及当前完整注册证书、明确原本地结算+退役授权和后续fresh packet授权；24/49、Gate-L FAIL不变。


最后投影差分：独立03复核发现后置子路径挂载遗漏（实际plan无此挂载），读集已释放。修复为显式解析v1实际bwrap挂载语法；未知挂载语法拒绝。非projection挂载不能是受验目录/文件的后代，基础祖先挂载只允许在受验projection覆盖之前，受验目录+文件自身组合保留。新增后置bind/ro-bind/try/dev-bind/tmpfs反例；actual plan的内存子挂载探针全部拒绝、执行0，产物 `actual-command-overlap-negative-check.json`。当前所属文件 `python -m pytest -q tests/integrations/dsh/test_legacy_retirement.py` exit0，17 passed/52.92s，日志 `/tmp/c2p-dsh-legacy-focused10-20261004.log`。原normal release源码未改。完成本次修复后再次冻结最终执行plan，交最后差分独立复核；真实授权仍未增加，原费用/owner未写入，Gate-L FAIL和24/49不变。


### 2026-10-04 — 已授权结算完成，退役仅续作，不重跑原结算

用户明确授权「本地结算及原占用退役」，原授权记录为 `/tmp/c2p-dsh-l01-legacy-retirement-package-20261004-01/user-authorization-record.json`。组合原命令 exit1：原 ad6c Worker 已完成本地结算（settlement.log、recovery/after.json），call/completed=1/1、spent=7332、pending=0、usage validated；task 仍 cancelled/无内容回执/无 provider_quiescence。退役在原子释放之前拒绝，旧 owner 仍 held，原因是 actual request 与 calibration 的本地 session/message ID 不同；新增模型及 tokenize 请求均0。保留原 execution-started 和执行日志，禁止重复结算。

同范围修复复用原 reserve owner 的不可变 WriterWireEquivalenceV1.transport_whitelist 与 _assembly_material；重新绑定原实际 request digest、归档 calibration loop 和逐字 provider wire，只有原合同明确声明的传输字段可不同，正文/tools/options 不放宽。另修正常冷入口的机器验证：自然结束已释放的 backend 必须 empty，并证明原 TaskStore quiescence、完整 Session/raw/usage/settlement 及 exact normal release history，不能继续要求 owned 或只靠 empty 放行。

当前聚焦命令 `python -m pytest -q tests/integrations/dsh/test_legacy_retirement.py tests/integrations/dsh/test_coverage_use.py` exit0，106 passed/62.61s，日志 `/tmp/c2p-dsh-legacy-cold-repair-focused13-20261004.log`。包含原 frozen whitelist 的允许/未声明字段/模型材料改变和 held/真实正常 history/缺 history 反例。原 packet02 材料及 native cold06 正常 release 凭据用当前 helper 只读校验通过。certificate06 原核心 passed=true（Python1307/56 subtests、Node211、operator1），但 cold companion 因旧 owned 比较拒绝，manager exit1；不能作为当前完整准入。两项修复后须最终差分复核和一份当前注册完整证书，不重验旧 A 或全仓静态。

退役续作包 `/tmp/c2p-dsh-l01-legacy-retirement-package-20261004-02` 保留原 attestation、原用户授权来源与已完成结算事实，仅运行修复后的 retirement command；不改变已授权 effects，不再请求同一退役批准。新真实 primary 仍须最终 fresh packet 的具体授权，原 primary 已消费。当前24/49，Gate-L仍FAIL，C–F按原前置继续。


### 2026-10-04 — packet09 已执行、结清及独立拒绝；源绑定合同集中修复

已按用户对 packet09 的明确授权执行一次 native DSH primary，命令 `python integrations/dsh/dev/l01_launch.py live --output /tmp/c2p-dsh-l01-packet-20261004-09 --receipt /tmp/c2p-dsh-l01-admission-20261004-08/receipt.json --authorization /tmp/c2p-dsh-l01-operator-authorization-20261004-09.json`，exit1，原始 driver-live.log/failure.json 保留。health/models/metrics均200；1次tokenize、1次primary、0 retry/repair；HTTP200、usage7359输入/891输出、finish tool_calls，tokenizer一致，额度内。原TaskStore cancelled/无domain receipt、有合法provider_quiescence；原预算call/completed1/1、spent7359、pending0；canonical backend empty及原strict normal release成立；Worker退出/Python模型与网络0。独立 `/tmp/c2p-dsh-independent-l01-live09-review-20261004-01/review.md` 为 Gate-L FAIL，已释放全部读集。原packet02结算7332/pending0及原占用退役已在package02实际完成并独立PASS，不能再结算或退役。

此前当前源码182f90/validator0a393的完整certificate08实际exit0（1521，Python1309/56 subtests、Node211、operator1、独立冷入口1），原完整及cold reader均PASS；只证明该绑定源码的离线准入，不证明live内容接受。该证书随以下源码修复成为历史证据，后续准入须重新冻结。

拒绝根因是L01测试材料准备：required atom没有closed atom→detail归属，且语义锚仅为内部标识“step for mech_rescale”，detail没有可验证自己的锚；自然缩放正文和公式不足以通过原exact witness门。修复 completed_formalizer_fixture 的required目标，从原archive所属detail/witness atom派生归属/摘录/锚，L01 opt-in可读语义由已接受、绑定同detail和操作的原code_verified Formalizer explanation派生；同一required detail也有明确源语义合同，全部detail/atom/formula义务保留。facade的单请求终态指令明确Writer原schema所需的detail witness与唯一正文substring；Python仍负责atom Binder、原parser/assessor和公式splice，无额外模型辅助。

必要范围偏差：补充源锚后原通用词汇匹配可把`a times z`误判为源`a * x`，故修复原publication_transaction_contract的简单双标识符源乘法检查；从源AST读取实际操作数，必须在同一乘法关系内，拒绝缺/换操作数、换加法、否定、附加乘除。任意源名称适用，无项目事实/路径/答案进入generic生产代码；不修改旧validation_stage、matching阈值、过滤声明或降低义务。该共享validator已在原VALIDATOR_BUNDLE_SOURCES，内容变化自然更新身份。旧packet09永远保持拒绝，不按新输入回填接受。

验证：原六文件聚焦链 `python -m pytest -q tests/integrations/dsh/test_l01_binding_contract.py tests/integrations/dsh/test_writer_prepare_ingest.py tests/test_agentic_detail_atom_binder_and_trace_v2.py tests/regression_20260917/test_witness_relation_matrix.py tests/regression_20260917/test_witness_projection.py tests/regression_20260917/test_publication_transaction.py` exit0、66 passed/8.81s，日志 `/tmp/c2p-dsh-l01-contract-regression-20261004-02.log`；补任意操作数/额外乘除反例后新文件 `python -m pytest -q tests/integrations/dsh/test_l01_binding_contract.py` exit0、21 passed/1.51s，日志 `/tmp/c2p-dsh-l01-contract-focused-20261004-03.log`。早期诊断/失败输出保留，不冒充新结果；无新增API/tokenize/真实模型调用。

接着同范围独立审查修复、冻结当前完整离线准入与fresh packet，再集中处理下一次具体live授权。当前24/49，L01 in_progress/Gate-L FAIL；C–F只读准备已有真实9/16节点及接口清单，正式接线仍按原前置。无需再次启动A验收或无变化全仓测试。


#### 2026-10-04 — 独立binding审查后的完整乘法关系修复

独立 `/tmp/c2p-dsh-independent-l01-binding-repair-review-20261004-01/review.md` 指出HIGH：局部关系正则遗漏`a*x-z`、`a*x squared`、`twice a*x`，原parser/assessor三者实际误接受；CHANGES_REQUESTED，读集释放。已按原owner修复为完整源AST表达式或有界完整正文关系证明；不能用局部匹配证明没有附加算术，未知词法/系数/幂/减法保留拒绝。源标识符大小写及拼写保持，x/X/xs不互换；不扩展semantic阈值，不删义务，不重跑live。

当前六文件同命令exit0，78 passed/8.95s，原日志 `/tmp/c2p-dsh-l01-contract-regression-20261004-03.log`；新增三个独立反例、附加幂与变量大小写/复数反例，原20 prepare/settlement链及旧Binder/关系矩阵/投影/事务仍通过。前66/21结果按修前身份保留。完整注册证书尚未因这次修复启动，避免在审查必修未关闭时反复跑全计划；接着提交最终差分复核后再一次冻结当前准入和fresh packet。
