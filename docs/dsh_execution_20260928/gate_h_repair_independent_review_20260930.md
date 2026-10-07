# DSH 0.2 返修候选独立 QA：CHANGES_REQUESTED

2026-09-30，Asia/Shanghai。独立审查人 `/root/gate_h_independent_qa`。本批只读受测产品、源码/测试、锁、peer、build/staging、owner证据及正式文档；仅新QA根和报告根写探针、私有夹具、日志。不更新正式Gate、台账或任务状态，不运行live、不重新build/stage/install。

**建议 Gate-H 保持 CHANGES_REQUESTED。** 本轮原目标 Node 链独立74/74、原B02 Python整个dev目录23/23，原F1具名反例、F3、F4同步异常与F5行为已修复。H04依然存在两条真实公开来源抢票：prepared请求对象可以从公开事件取得并重入消费；NO_ADAPTER回落给任何携同signal的裸请求补来源标记，完整复制和不同messages都能抢票。三种反例均到真实观察型adapter、R/D/S各一次，而原合法child失败。原未完成的等待期联合来源/部分异常矩阵也不能由74总数折抵。以下PASS仅指已列行为，正式Gate裁决由LEAD负责。

## 1. 本批身份、冻结与证据

仓库 `/home/cuihengjia/agent/Code2Paper copy`；分支 `codex/agentic-p4-benchmark-cutover`；HEAD `d48b4e4b22c94c82b45d2179ba452d72b164102d`，dirty tree保留。Node v25.8.2。目标0.2显式双env，peer指目标；默认旧runtime仍0.1.5，未切日常0.1.7。

| 对象 | 本次实际身份 |
|---|---|
| 目标runtime完整26149项 | `43490765da460c4300cd7ad8ec75dbc5d5e6dbda93b74e37466c6709c1ab359c` |
| 旧default runtime | `7e8f199b67027944d646e0c99f5041d4704360377e4d7466fce683c1d468d3ab` |
| 目标runtime lock | `67f3a677bb15ec9ef11aab15c24482cf053910ab5f67834223f6e96e70b3e3ba` |
| 构建回执 | `47586456373fc7b9678a0a97c1019eaf7e1cf8e1bccc6d1f5f2fd391049d9ced` |
| 输出摘要 | `4bdd2ecea20393e663aba77f393816b3a594aa2636378c1be85a6a179403422f` |
| 目标stage（18文件） | `a67555d1ecaadb447dbd642c1d7ac3ed31660cb8a9717d7bb1bb4b9c8a6baedf` |
| request-accounting.ts | `266dc3fa4d8fe02aeabdb87e898223ac51779201e59fae69822a92e0320f7785` |
| terminal-result.ts | `5ef6174659140fc1b1098e01456223a296296796dfdfef52daa12133ea918ecb` |
| scripts/dsh_dev.py | `f5233069e88e0b2cb410ace8c29cc87d0fd44b5458fa306751ba7a76f1ca2795` |

完整实际源码/合同/lib/stage/worker/profile/peer输入在 `before.json` / `after.json`：2618项hash、inode、mtime_ns、mode全部一致；目标runtime全项相同，旧default树相同，branch/HEAD相同，missing=[]、changed={}。兼容清单9项声明源码hash均匹配。本批没有上一批共享profile mtime副作用；上一批两个mtime变化的历史记录保持原字节，不恢复或掩盖。

目标pyworker6个锁包匹配且 `import code2paper` 成功（`read-only-final-identity.json`）。候选来自npm安装，**无安装前日常hash快照**，真实 `hash_compared=false` / applicable=false；当前日常路径存在、共享inode=0、日常路径不在候选可写根。只能证明当前隔离与本批没有日常写路径，不能倒填之前安装过程的字节证明。

QA输出：`/home/cuihengjia/agent/Code2Paper copy/.dsh-dev/candidates/0.2.0-rc.1/run/qa-gate-h-repair-n60vnt00`。本报告原根：`/tmp/c2p-gate-h-repair-qa-20260930-3aemexrp`，全部日志/探针和报告镜像到候选QA根；旧报告 `/tmp/c2p-gate-h-independent-20260930-zny3hfyo/Gate_H_independent_review.md` 保持原字节，不改71轮为74轮。

原owner日志真实存在：`w2-repair-20260930-195254/check-compat.log`（`9a3ab9c49fff368c121e53153be1fe4cce07107fa577a0d7dff8d2894ef736bc`）含typecheck/build/stage/check/test真实argv、74/74和exit:0；`b02-pytest.log`（`5dbff4c8b1ae868f739a79b5b47b3b7b32fc9bff1518086a2d8201f7399b4b99`）为20项单文件、exit:0。另有discovery3项日志。LEAD入场35项owner记录摘要在 `/tmp/c2p-dsh-lead-repair-review-20260930-yuk7omy7/inputs_before.json`，本批逐路径复核记录见 `owner-log-path-verification.json` 与 `lead-owner-log-after.json`。此前把 `rg --files` 的忽略规则列表误当目录全清单而报告日志不存在，已纠正；不是实际缺文件或沙箱可见性问题，未据此裁决缺证。

## 2. 已运行与退出码

| 运行/日志名称 | 真实退出码 | 实际行为 |
|---|---:|---|
| test-compat | 0 | 原 `npm --prefix integrations/dsh run test:compat`；11个原TS文件，74 pass/0 fail/0 skip，66.30s；显式0.2双env，原只读断网launcher。未执行会重封的check:compat |
| b02-runner-initial | 1 | QA wrapper构建argv误用了ROOT常量，测试未启动；已保留原错误并改QA runner为REPO，不是产品失败 |
| b02-original-dev | 0 | 原 `integrations/dsh/dev/tests` 整目录，23 passed，12.08s；20项环境文件+3项工具链发现，不删原集合 |
| strict-reader | 0 | H03新staged公共reader正反例完成；原F1均具名拒绝，V3/V4不混读、synthetic拒绝；额外结构观察见范围说明 |
| prior-public-and-accounting | 0 | 旧公开withInitiator准备等待攻击拒绝且原请求成功；reserve/dispatch完整copy+同signal均拒绝；真实双child R(A),R(B),D(A),D(B),S,S；A准备未完B完成；实际sync return具名诊断 |
| public-request-alias | 0 | 公开同对象来源抢票反例完成；**产品负向合同未满足** |
| public-fallback | 0 | 正式NO_ADAPTER回落、公开同signal完整copy与不同messages抢票反例完成；**产品负向合同未满足** |
| web-private-smoke | 0 | 8.62s，普通Web真CLI HTML200、4资源200、modelturn0、端口33095关闭 |
| compat-private-smoke | 0 | 8.50s，compat真CLI HTML200、4资源200、modelturn0、端口42177关闭 |

真实argv、offline/选定根在同名 `.command.json`，退出码在 `.exit`，首次QA wrapper失败原文保留。**探针exit0仅表示观察完成，并非负向产品合同通过；Node探针名称中的“must not/cannot”不是裁决。** 重负载test:compat/B02结束后已通知LEAD，后续内核集不与其重负载重叠。

所有来源探针引用同一个新staged公共模块与真实绑定委派路径。来源能力限于公开Host扩展：观察公开event、使用公开Agent/signal/llm/agents接口；不读取私有WeakMap、不自行签发authorization、不修改runtime/loop factory、不后置补binding。观察型mock只记录adapter进入，拒绝由正式accounting/gatedAdapter负责。回落通过mock adapter一次抛真实 `LlmError('…','NO_ADAPTER')`，真实loop catch进入原分支；之后adapter可用，保持合法回落正向模型能力，未绕开门。

## 3. 阻断发现

### H-R1：prepared来源能力经公开request对象泄漏

实际代码：`integrations/dsh/src/request-accounting.ts:354`（takePreparation，354–363）、`:390`（prepared.stream mark，390–394），误把“公有调用者无法取得此对象”作为前提的说明在`:103`。冻结0.2 `dsh-llm/lib/index.js:2367`/`:2371` 将实际options对象交给公开 `llm/stream` waterfall。

最小复现：真实绑定child已通过agent/request、真实prepareCall并调用prepared.stream；公开 `{prepend:true}` 的 `llm/stream` listener收到实际request对象。listener只调用 `deployment.llm.stream(request)`，待其结束后继续 `next()`。嵌套裸请求首先消费该对象标记并完成reserve→dispatch→真实adapter→settle。合法原请求随后进入accounting时标记已删除，来源拒绝。

实测：`gotActual=true`；嵌套finish stop；adapterDelta=1；R/D/S各1且settle=settled；原child `{output:[],stopReason:'error'}`；诊断 `no loop preparation for this request signal`。不需要withInitiator、私有票据或任意进程修改权。相同对象不等于可信派发；复制摘要拒绝的已有helper/等待期控制不能折抵此公开引用。

证据：QA根 `public-request-alias.test.ts`，报告根 `public-request-alias.log/.exit`，记录 `QA_PUBLIC_ALIAS`。合同：第01份§2公开引用/对象同一性边界、AT-H04合法准备不得抢占、原请求随后仍成功。**CHANGES_REQUESTED**。

### H-R2：NO_ADAPTER回落为同signal裸请求补来源

代码：`request-accounting.ts:401`（fallback-ready），`:410`/`:413`/`:415`：只因preparation处于fallback-ready且公开signal相同就标记任何options。此处未绑定prepared来源能力或本次可信dispatch材料。原loop分支在冻结 `dsh-agent-loop/lib/index.js:1189`/`:1192`。

最小复现：一次真实NO_ADAPTER从adapter.prepareCall传到LlmRuntime再由Agent loop捕获；合法fallback的公开llm/stream listener获得完整实际请求和同signal，并从公开agent/request取得Agent。在该listener内 `agents.withInitiator(agent, ()=>llm.stream(copied))`。copied为除signal外完整structuredClone+原公开signal。第二变体更换messages，同时保留公开session/route/signal。

两变体均嵌套finish stop、adapterDelta=1、R/D/S各1、合法原child error。完整copy摘要相等；不同messages摘要分别 `81444938…` / `bdbec747…`，也能消费准备票据并按裸材料计量/结算。原回落未发生授权adapter进入。信号不是秘密，公开setter亦非授权。

证据：`public-fallback-probe.test.ts`，`public-fallback.log/.exit`，两条 `QA_PUBLIC_FALLBACK`。该反例独立于H-R1：无需同request对象，复制全材料或不同materials均成立。**CHANGES_REQUESTED**。

应在原owner/source能力与回落入口闭合合同，再一次集中复验准备期、两回执等待点、双child及联合持久来源；不能靠排除公开可取引用的未经执行权限假设或只证明后置重放拒绝放行。本文不替实现者指定新架构、不代修产品。

## 4. 原F1–F5差分结果

| 原项 | 本轮真实差分 | 范围/结论 |
|---|---|---|
| F1 event=null、tool/call data=null、string/number isError、content=null、坏error identity | typed event/tool-call/tool-result-malformed；不抛异常。合法V4与V3 committed；错header形状typed拒绝；true/TOOL_NOT_STARTED/TOOL_OUTCOME_UNKNOWN unresolved | 原具名反例已修复。完整Message schema校验不以这些少数变体推定 |
| F2 publicwithInitiator+不同messages在真实prepareCall等待 | adapter0/RDS0、finish dispatch_origin_unproven；释放原请求completed且RDS各1 | 旧反例关闭。公开同对象与正式fallback仍失败，见H-R1/H-R2；不能登记整体来源PASS |
| F3 A真实agent/request准备未结束时B开始 | B先completed/RDS各1；释放A后Acompleted，合计adapter2/各RDS2；不同session | 原误拒合法兄弟已修复；不是串行A后B夹具 |
| F4 return同步抛错 | helper=threw；真实accounting完整finish/usage之后：adapter1/settle1，`iterator-return-threw` + outcome=unsettled诊断，child completed | 同步call已受try保护。记录已结算不重试；cleanup失败另记。异步reject/timeout helper绿不等于全实际异常矩阵已验 |
| F5 CLI cwd/原Python集合 | 真实launcher argv --chdir为0.2/workspace，B02整目录23/23，Web/compat实际HTTP及端口关闭 | 原cwd/适配问题修复。HMR ENOSPC仍可见但两个HTTP正常；不倒推上轮40s空日志唯一原因 |

strict-reader额外原始观察也保留：missing tool/call scope被跳过；missing tool-result.content、数组内null、text字段数字仍committed。当前reader校验已消费成功身份/flag与自己的record，而非完整DSH Message schema。本轮只确认原具名F1修复，不把它写成任意损坏结构均拒绝；这些观察不使用任意伪造持久事实来补来源PASS。

## 5. 原AT→实际节点/断言/输出/范围矩阵

全部行消费§1同一runtime/source/build/stage；“suite”是本批真实 `test-compat.log`，不是owner汇报。源码/测试准确文件见before清单。PASS仅绑定表中行为；“未测/覆盖不足”不被总数折抵。

| 原AT条款 | 实际节点与断言 | 本轮证据 | 裁决/准确范围 |
|---|---|---|---|
| B02明确候选与匹配拒绝 | candidate-selection原29/41行：flag/env/root错配拒绝；launchertest传选中根 | suite；b02-original-dev | PASS |
| B02可复现typecheck/build/stage | owner完整check原链argv+exit0；build输入/output/stage真实同一身份；QA仅verify_staging | owner check-compat.log；before/after；read-only-final-identity | 身份/owner链成立；QA不重建 |
| B02普通Web | 原command，真实候选cwd；隔离同字节profile/home；HTML+四资产200，无模型 | web-private-smoke；private-profile-copy | PASS启动/HTTP范围；HMR warning未当成功依据 |
| B02兼容CLI | 相同compat组成和全部bundle字节；HTML+四资产200；无模型 | compat-private-smoke | PASS |
| B02隔离/禁止裸跑 | 原bwrap ro-bind /与runtime，候选root可写；两个真实隔离探测、runtime不可写/run可写 | suite sandbox；B02原356行；commands | PASS；没有裸Node降级 |
| B02日常环境/默认旧版本 | 当前日常无共享inode且outside writable；历史default树前后相同 | read-only-final-identity；after | 当前PASS；日常预安装hash比较N/A，不能倒填历史 |
| B02不继承secret/proxy/Harness/注入/端口/无bwrap | 原环境123等/保留端口/白名单/drift/refuse检查 | b02-original-dev23项；suite sandbox/candidate | PASS，未执行live |
| B02全部测试发现 | 11个原TS文件+3项Python发现边界（nested/dev/ignored artifacts与失败exit） | suite；b02-original-dev | PASS；owner20单文件与本批23目录明确区分 |
| B02 worker锁/导入/注入排除 | 6锁包与code2paper导入；PIP env隔离安装合同在fake fixture，不实际install | read-only-final-identity；B02原325 | PASS当前worker与安装argv合同，非本批重装 |
| H01真实Loader/preset导出 | loader435/451：实际named name/inject/Config、roster行、runtimepeer | suite | PASS |
| H01根/工具与兄弟/未join | loader471/484：await setup，真正ToolRuntime执行/render，兄弟note分开、未join拒绝 | suite | PASS |
| H01父child同standing generation | loader507：修改私有preset夹具后child保持父代，override实际身份 | suite | PASS；共享preset未写 |
| H01缺包/inject/Config/丢metadata | loader539：真实创建拒绝、无live residue；global service越域558与重复服务573 | suite | PASS |
| H01销毁与输入保护 | loader585/599：agentlive state removed、standing retained、两host modelCalls0、共享字节不变 | suite；before/after | PASS受影响生命周期 |
| H02先claim后读/创建 | binding530/570/602：standard spawn窗口拒绝、blocked claim零read/adapter/create、setup先绑定 | suite | PASS |
| H02伪造/旧fence/取消 | binding639/695/723：unbound/forged拒绝，current控制可用，receipt前/创建前取消无残留 | suite | PASS |
| H02binding生命周期与真实消费 | binding769/792/844：disposal撤销；四request方法实际类型/调用；延迟/拒绝/cancel具名 | suite | PASS本地合同；非PythonRPC持久账本 |
| H02旧父hint/对象归属 | binding884/936：superseded父不可借current hint升权、只收Host注册provider对象 | suite | PASS |
| H02新版接口完整冻结 | _020真实hash/四方法有记录；actual docs仍称currentInitiator且未逐一枚举完整真实导出/活跃binding消费示例 | interface020；sources | 交付描述待补/纠正；未正式冻结，不能提前消费错误来源前提 |
| H03真实成功/版本分读 | terminal241真工具成功；provenance517 V4独立消息/V3嵌套按header、不混读 | suite；strict-reader | PASS列明版本/成功关联 |
| H03closing/双terminal/坏schema/后工具 | terminal324/333/351/367，实际后不同工具body不执行、原terminal不改 | suite | PASS |
| H03raw/normalized/parsed/prose | provenance65/90/108/123/181/297：原文空白转义键序分digest，按可信session与request/call隔离，缺raw具名 | suite | PASS表示来源；不是HTTP/SSE原字节证明 |
| H03complete per matchingblockend | provenance207/332、terminal394：A完成B失败独立，未完成为incomplete；finish独立 | suite | PASS |
| H03record全校验/重复冲突 | provenance238/381/430/476：先结构/digest/真实工具对应，再比较多record；损坏自原因、duplicate call ambiguous | suite；strict-reader | PASS既定节点；完整Message shape边界见§4 |
| H03synthetic不能提交 | provenance517与joint新进程synthetic；typed true/两代码 unresolved | suite；strict-reader | PASS不作为terminal成功。TSsynthetic不是领域refund/retry实测 |
| H03flush与新进程 | terminal241 await真实persistence.flush+落盘、进程reader按header重建 | suite | PASS合法持久路径；阻塞/失败listener、缺字节故障的完整对照未另验 |
| H03/H04同child联合正向 | joint-child230：同绑定child reserve/dispatch/adapter/terminal/settle/flush/新reader；format header读 | suite | PASS已存在正向；不是几套独立fixture替代 |
| 同child等待期污染反例 | joint-child只在child.whenIdle/commit以后裸调用，无准备/reserve/dispatch等待期污染与恢复 | joint代码230–316；H-R1/H-R2 | CHANGES_REQUESTED原等待期可信来源前置未满足；不能借postcommit无变化通过 |
| H04scope fanout与真正双child | S1无veto先量真实fanout并存活；独立两child reserve barrier，每session各RDS一次；B在A准备时先完成 | suite S1；prior-public-and-accounting | PASS扇出/计量/兄弟可推进；不把fanout当隔离 |
| H04合法来源正向/完成后裸ID/route拒绝 | S2真实dispatchRole/c2p-spawn正向RDS；裸liveID来源拒绝；foreign route拒绝 | suite S2 | PASS列明正反例；等待期来源仍CR |
| H04准备期间公开sameSignal/withInitiator | C9 waterfall中；C10真实adapter.prepare等待；旧独立不同材料拒绝且合法原请求one | suite；prior-public-and-accounting | 旧准备等待攻击PASS；准备结束公共同对象H-R1失败 |
| H04prepared/public full actualreference | 正式prepared.stream标记后公开observer reenter actualrequest | public-request-alias | CHANGES_REQUESTED，H-R1 |
| H04direct/NO_ADAPTER回落来源 | 全材料deepcopy+公开same signal+withInitiator；不同messages variant实际loop fallback | public-fallback | CHANGES_REQUESTED，H-R2；不是仅无adapter错误的terminal fallbacktest |
| H04reserve/dispatch等待期完整copy | originalrequest公开观察完整clone保留signal，两phaseattack均adapter0，释放原请求completed/RDS各1 | prior-public-and-accounting QA_FULL_COPY | PASS此copy控制；不是完整所有payload drift/abort/fence交叉矩阵 |
| H04一次授权/摘要/跨session与回执 | S2注册表helperissue/consume恰一次、crosssession拒绝/outstanding；R-receipt detached/deep-frozenparts与receipt/digest错配 | suite S2/R-receipt | PASShelper断言；不能证明原来源能力/真实全部outstanding撤销 |
| H04prepared二次dispatch/config漂移 | gate prepared捕获代次/consume一次的源码；S2多为授权表helper，不是同真实prepared对象第二dispatch/config漂移完整行为 | accounting源码/原测试 | 覆盖不足：不以helper或来源拒绝充抵原必测 |
| H04两回执后最终abort/fence/digest | 源码recheck两次；C1真实reserve中abort，C6实际dispatch后fence advance adapter0 | suite C1/C6；代码548等 | 已测部分PASS；dispatch abort、reserve fence和两phase真实完整assembly漂移各独立反例未齐 |
| H04完整digest/cap/估量/usage | R-cap封闭覆盖含toolHistory未知keys拒绝；C7stop无usage→unknown usage-missing，估量utf8非zero；cap源码safeCount | suite R-cap/C7 | PASS所列断言；未知/非法cap在同真实child的拒绝没由测试名证明 |
| H04取消/拒绝/recorder失败一次终态 | C0–C4真实delegate正向、明确reserve barrier+abort、refusal后可恢复、recorder失败一次namedunsettled | suite | PASS对应节点；next/create/iteration/break/throw/return/abort完整真实矩阵未齐 |
| H04return同步/异步/250ms | helperC8 sync/async reject/timedout；C12与独立真实sync wrapper保持next来源、RDS一次并namedcleanup | suite；prior-public-and-accounting | PASS真实同步与helper有界；实际async/timeout/abandoned的完整路径不得由helper折抵 |
| H04abort不是quiescent/unknown不退款 | C5明说资源范围，无退款API/持久余额；上面cleanup不作为adapter底层结束证明 | suite C5；resource inventory | 不能claim全静止；托管waitForExit资源类N/A，本批CLI退出/端口关闭独立实测 |
| H04provider/title/retry/PTC/compaction/OTel组成 | offline patch真实globally-disabled网络/LLMtitle/retry/OTel；本候选Code2Paper scoped preset只挂tools；标准preset含compaction/PTC且profiledump不能仅按包名/出现disabled判断所有scope | loader实际ToolRuntime；suitecomposition；冻结patch/dump | mock目标关闭/无触发路径可保留；不扩大到standard preset或任意新child/图像请求完整运行 |
| H04imageOffload/Schedule/desktop | base默认presetimageoffload存在；Code2Paper自有preset无此row；runtime有schedule但profilebundle白名单无；desktop包未装 | sourcepreset/offline/composition；ownerconfig | 仅目标mock/puretext范围，无live/图像offload恢复或Schedule场景PASS |

## 6. CLI/资源与能力边界

`private-profile-copy.json`逐项记录源与私有home/profiles：553项regular bytes或link目标完全相同，regular inode独立。bundle复制含18个同字节staged文件，peer链接保持同runtime目标。运行使用原readonly bwrap、原candidateworkspace cwd和相同profile/overlay/bundles，只把DSH_HOME指向新QA私有home；未更改共享home/profile。认证startup URL/cookie只在官方smoke内存中；持久日志原始startup段做URL redact，不打印token。

两组成HTML34812字节、四资产字节631135/740575/29288/75665，全部HTTP200。模型turn0。HMR均有ENOSPCwarning、仍实际HTTP正常；本批HTTP证据比owner仅ready行更完整。startup socket需要宿主loopback，使用原HTTP smoke readonly sandbox而非无网络namespace；原Node模型mock测试仍 `--unshare-net` 且外连拒绝，未凭Web启动宣称断网。

真实CLI进程有界terminate/wait返回-15，33095/42177端口在officialsmoke与closing两次关闭。Host `/proc`本用户125进程，按确切QA probe/runner与targetCLI argv匹配0、不可读0；见 `closing_process_check.json`。该事实只证明本批启动CLI/验证进程结束，不泛称所有模型或其他窗口底层资源静止。产品托管subprocess `waitForExit`没有实际启动的资源，原C5范围为N/A；不以AgentHandle.dispose/whenIdle或250ms截止取代true。

本批没有DSH RPC/生产余额、全文主图迁移、C03/F02、live、质量总验收或默认业务切换。现存H01/H02局部PASS、B02通过、合法joint持久路径及修复证据继续保留；源码修复归原owner连续整阶段，不逐缺陷停派工。

## 7. 收尾与读集释放

所有本批测试/探针/CLI子进程已返回，无pending写入/待运行检查。before清单2618实际路径、runtime全26149项、旧default树、上述owner日志/接口输入及其读取依赖，在本报告完成时明确释放给LEAD协调；本QA不继续读取移动候选、不常驻等待、不自行改Gate或产品。

closing时间、输入/输出准确hash清单、镜像报告位置与完全释放声明见同根 `closing_release.json`。读集释放不等于Gate-H通过。
