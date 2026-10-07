# L01 packet14 错误流、服务兼容与 UNKNOWN 恢复（2026-10-05）

执行入口为[原长期模块 §9](stage04_06_long_module_execution_20261004.md#gate-l-unblock-20261005)。当前 **24 done / 1 in_progress / 24 planned，Gate-L FAIL，实际 live 七次**。本批模型、tokenize、服务修改和 canonical 恢复均为 0。packet14 授权已消耗，原 owner held、实际费用 UNKNOWN；不能复用正常结束释放授权。

## 原始失败及历史验证

packet14 为 `/tmp/c2p-dsh-l01-packet-20261005-14`：packet SHA256 d20fd9ebaf34853c545b18c543aa42fefec57f811bfa835157f0eeeb2e430649，plan967f4cbd5cf0bdf3aa3466b9304852ce80107a133d1a4bc7f596d0aa12312cac。原 live15585 已回收 exit1；1 primary、1 tokenize、0 retry/repair/aux。HTTP200 内162 JSONframes部分reasoning后SSE InternalServerError500/DONE，没有 usage、合法 finish 或 tool。Session为PI_AI_ERROR，task cancelled，captured_source/receipt/provider_quiescence均null。同请求 `chatcmpl-8a7221aeaf4f1d37-969dec6c` 的日志显示 grammar FSM/scheduler拒绝[13,198,248069]；不构成合法自然完成凭据。

原SDK默认usage0/0被旧账本误当validated，spent0/pending0/completed1仅旧观察，真实费用UNKNOWN。原七条费用事实、六条严格history、task/claim/SSE/Session/failure保持。独立事后[436输入审查](/tmp/c2p-dsh-independent-l01-packet14-postlive-20261005-01/review.md)为FAIL，实际读集释放，normal-finish授权DOES_NOT_APPLY。

完整09仅绑定engine f82b89a4488bb6c7a7f1f48ead4173a69fc1132f47f996a5cd131348b2bcfecf / validator5951bd878bd9fc3adca478612376e0e0d75935cdf9c39996a652ceb1fd3a6c12：1819/fresh cold1，manager33501和reader31459回收0。它是历史结果，不能贴当前源身份。

## 本批实际实现

- 原request-accounting拒绝SDK默认0/0，保留真实input0/output>0；错误/缺usage保留unknown reservation。Kernel和Python RPC拒绝伪零usage；非自然finish不能提供stream_complete。Host保存native provider首因与真实Session，L01保存SSE原始错误并作为首因，其他失败附为次因。
- L01 profile/worker/prepare同时显式off，现有PiAi兼容字段发送 `chat_template_kwargs.enable_thinking=false`，无reasoning_effort/thinking_token_budget，保持具名强制c2p_terminal、完整schema、内容/公式/witness门、32768/4096/180秒、零重试。未追加runtime补丁，default0.1.5不变。
- 共享Formalizer profile的thinking reserve保持1024，Writer measurement reserve单独为0并绑定descriptor/model/composition。发送前原Facade核验冻结composition中的模板参数与Writer reserve，省略/true/数值0/残留effort或budget/错误reserve均拒绝；不能仅凭calibration wire判断可以发送。
- `unknown_abort_recovery.py` 提供独立版本化、operator-only的 terminated-provider-unknown-retirement/1。需要真实整epoch终止证明、独立PASS及distinct授权；原正常结束授权不适用。保留UNKNOWN及input32768/output4096责任，旧run永久禁续，不退款、不改旧事实、不伪造execute来源。
- disposition先独占持久化/fsync；原run lease下原owner原子写入typed history并退役，事务断点可安全续办，外来owner保护、旧owner不可复用。history原reader严格校验字段类型、摘要格式、immutable plan/review identity、原attestation/task digest和原保守budget digest；重算selfdigest/key也不能放行篡改。
- registered core/offline计划版本10加入新operator与真实native生命周期覆盖，保持旧strict reader。测试数量不等于Gate-L或上线许可。

## 实际验证与集中审查返修

[首次集中独立审查](/tmp/c2p-dsh-independent-l01-unblock-code-plan-20261005-01/review.md)实际绑定1104输入，CHANGES_REQUIRED，全部实际读集释放。集中修复U1回执空/无绑定metadata、U2误改共享Formalizer reserve、U3缺真实native异常行；不以helper单测替代整链。

| 原命令/产物 | 实际退出与行为 |
|---|---|
| pytest新operator+L01 meter，`/tmp/c2p-dsh-l01-unblock-u1-u2-focused02.log` | 原71652回收0，48 passed/95.30s；含11组resealed metadata攻击拒绝、事务cut/新owner保护 |
| pytest native_tool_choice_projection+L01 meter，`/tmp/c2p-dsh-l01-unblock-nonthinking-admission01.log` | 原94932回收0，45 passed/17.78s；显式模板精确发送门及负例 |
| 原Loader/PiAi/HTTP/Session/Python Worker，`/tmp/c2p-dsh-l01-unblock-native-20261005-02` | 原67411回收0，35 passed/392054.180977ms；30 cancellation seam及五条native error/cache/draft/formula/text；自身历史身份保留 |
| 四条新真实native，`/tmp/c2p-dsh-l01-unblock-native-20261005-03` | 原26587回收1，3 pass/1 fail/0skip/cancel；断流、正常finish缺usage、有usage缺finish通过；timeout脚本错误要求terminalObservation，不是完成证明 |
| 修正timeout脚本，`/tmp/c2p-dsh-l01-unblock-native-20261005-04` | 原44995回收0，1 pass/71824.009724ms；真正请求到达后deadline，实际Session、pending/held、release拒绝及新worker0重发 |
| 原L01 prepare，`/tmp/c2p-dsh-l01-nonthinking-prepare-20261005-02` | 原73499回收0；完整wire仅按exact非thinking转换改变原14，Formalizer1024/Writer0；不是模型成功 |
| 本机安装tokenizer/template/parser/full-schema grammar CPU，`/tmp/c2p-dsh-l01-nonthinking-grammar-20261005-04` | 原76694回收0；网络/权重/模型/tokenize0；synthetic工具结构编译及actual parser提取通过，不证明loaded服务或领域输出 |
| 原14保护克隆，`/tmp/c2p-dsh-l01-packet14-abort-isolation-20261005-02` | 原25545回收0，七场景；独立网络namespace，原文件/后端字节不变；simulation授权不适用于canonical |
| L01实际隔离error整链，`/tmp/c2p-dsh-l01-provider-error-offline-20261005-03` | 原74526回收1（预期拒绝）；原task.prepare后SSE500首因/Host次因，pending7133/spent0/completed0/partial/held，新模型0；original-reader-verification.json PASS |
| 原toolchain typecheck05 | 原7574回收0；仅验证bundle类型，无runtime修改 |

保留所有失败历史：最初新digest校验误用无sha256前缀，76531回收1（17fail/31pass）、49918回收1（first fail），修正格式后48通过；typecheck02/03因未同时选择candidate/root提前拒绝，04/05回收0。native01原74719因relative testpath提前拒绝，未运行产品用例。L01 offline02原93642回收1，provider_options_mismatch/零发送，暴露发送前模板检查缺口；随后原Facade精确绑定修复，offline03走到预期错误流。上述失败不能隐去或标PASS。

## packet14具名操作方案及未满足的权威

[实际只读恢复材料](/tmp/c2p-dsh-l01-packet14-abort-preparation-20261005-01/readonly-preparation.json)绑定原10份frozen inputs、原七facts/六history、request/session/owner；三个修改后的源输入恢复成精确旧字节并校验SHA/长度，原14未改写。

[整epoch停止方案](/tmp/c2p-dsh-l01-packet14-abort-preparation-20261005-01/service-epoch-stop-proposal.json)绑定boot/epoch、PID3597064、3600274、3600277/start_ticks/pgrp3597064、GPU2 UUID `GPU-16167b06-839a-8ed9-321e-5fe1c4a7900e`。影响8006全部共享客户端（max-num-seqs16），不影响其他GPU/服务。先关闭该epoch准入，严格身份前检，再具名TERM/30秒等待及仅获授权的同epoch KILL升级；必须证明全进程、旧listener、全部旧epoch GPU contexts终止。实际argv证实MTP2、qwen3/qwen3_xml；日志/idle/API消失不能单独作为证明。

[非秘密重启配方观测](/tmp/c2p-dsh-l01-packet14-abort-preparation-20261005-01/nonsecret-restart-recipe.json)已从同一PID读取白名单环境，不打印或保存秘密；服务owner仍须确认配方及共享影响。顺序为真实stop确认→独立读回→绑定真实confirmation的恢复plan/review/distinct grant→原owner事务→独立结果/readset释放→新epoch重启/readiness→新包一次具体授权。当前未执行任何一步副作用，未形成真实termination/PASS操作review/授权。

UNKNOWN处置是保守责任持有，不是实际费用清零。原task/source/receipt/quiescence/seven facts与六history不变；恢复唯一新增immutable disposition+typed history+exact owner退役。真实受信终止与不同操作授权仍缺，canonical保持held；不增加模型探针或自动重发。

## 当前完整验证的绑定

完整10已实际完成：原manager13886回收exit0，Python1640 passed及56 subtests、Node226 passed、原operator1 passed，共1867；fresh cold1通过。原完整与cold读取器80140回收exit0，109依赖路径、版本10及fced96d6…/f466801c…身份稳定。产物保留在 `/tmp/c2p-dsh-l01-admission-20261005-10`，不改变原绑定。

[最终整包独立审查](/tmp/c2p-dsh-independent-l01-unblock-final-20261006-01/review.md)实际读取1606输入，复核完整/cold、11真实native场景及原14保护克隆通过；U1–U3闭合，但CHANGES_REQUIRED仅残余U4：授权approved整数1、嵌套task_epoch=false及终止subject同类字段因Python弱等值被接受。全部实际读集已释放，之后集中修复。现在结构绑定使用canonical JSON字节精确比较，授权仍须approved严格True，历史与终止owner/scope严格类型校验；证据及停止授权中的process列表、disposition与receipt的交叉引用也做类型保真绑定，拒绝重新seal后的别名攻击。新增9项真实拒绝路径测试，保留合法控制、UNKNOWN责任、断点与外来owner保护。 首次U4整组原67354回收exit1，31 passed/1 failed/130.86s；失败在既有fixture的request.reserve，因主执行者同时写文档触发composition_source_unstable，9项新增反例全部通过。保留原日志 `/tmp/c2p-dsh-l01-unblock-u4-focused01.log`；全部文件收口并冻结后重跑同组到focused02，实际结果记外部索引，本文不预宣称通过。

修复后10成为其原身份的历史通过记录，不能重贴为当前证书。全部源码、profile、合同与本文收口后，冻结新的版本10完整/fresh cold到 `/tmp/c2p-dsh-l01-admission-20261006-11`，再由原两读取器与独立审查验收。本文写入时11尚未开始；运行句柄、实际结果及独立readset释放写外部sole-writer `/tmp/c2p-dsh-l01-repair-execution-index-20261004-01.json`。验证/审查期间禁止源码与文档修改，不以历史10或聚焦通过代替当前准入。

新live必须原owner合法恢复、当前完整/cold、独立材料与具体新packet一次授权齐备。若显式非thinking新live仍同类grammar错误，转8006服务端专项，停止提示层试错。Gate-L独立PASS及读集释放后继续M01–M03→P01–P04→G01–G08，各阶段独立Gate，保持default单Writer、parallel=false；不据静态/单样本宣布D5、rollout或发布。

## 更早P1/P2聚焦验证历史

typecheck01失败两项可空字段类型，02原26584回收0；build01原81540回收0/stage01原exit0。focused01原11776回收1：62通过，4新增fixture错误调用不存在put_bytes，6默认bwrap NETLINK_ROUTE EPERM；修正fixture使用原ArtifactStore.put，原8833回收0四反例通过，原81015回收0六隔离准入通过。native01原97497回收1：30通过/2失败；旧C12b错误预期无usage迭代失败为unfinished settlement，新增错误场景实际先触发accounting_unsettled而非后续quiescence门。仅修上述准确断言，不放宽生产门；native02原37051回收exit0：原30项cancellation与真实PiAi错误流共31通过，76039.992619ms；真实Session错误、pending7107/spent0/completed0/held，新Worker零额外发送。L01原offline89326回收exit1（预期拒绝）：首因l01_provider_sse_error，次因host_provider_stream_error；原reader读回pending7134/spent0/completed0/provider_usage partial、task cancelled/null领域、isolated-fake原owner held。上述两份绑定refinement之前的fee0/80963身份，保留各自原身份。最终收紧为只有input与output同时零才拒绝，避免误拒cached输入；typecheck04原61467、build02原80485及stage02回收exit0，focused03原52352回收exit0，68通过及56subtests/272.57s。新增cached输入RPC正例原66781回收exit0，1通过/23 deselected/5.03s，证明input0/output3作为实际usage保留且缺finish不完成费用；当前完整/cold及独立代码审查尚未通过，不以这些聚焦结果替代Gate-L。
