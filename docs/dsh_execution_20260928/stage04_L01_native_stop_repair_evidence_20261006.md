# L01 packet16：native stop 与 Writer 语义合同返修（2026-10-06）

本页记录解除冻结后本批开发范围。最终冻结身份、完整与冷启动结果以及独立审查以
`/tmp/c2p-dsh-packet16-diagnosis-20261006-01/` 的绑定产物为准；本页不是新 live 授权。

## 原执行与权限

packet16 一次真实执行：1 primary + 1 非生成 tokenize，0 retry/repair/aux；HTTP200，
真实 usage 7705/392/8097，原生 `c2p_terminal` 成功、自然 `stop`/DONE、无 grammar 错误。
原内容门拒绝，独立 Gate-L FAIL；原 task cancelled、receipt=null，六条费用事实结算
7705/pending0，但完成登记遗漏造成 exact owner held。旧七条 history 与 packet14 UNKNOWN
责任保持。项目24/49，实际 L01 生成共8次；M/P/G 尚未准入。

独立原执行审查：[585输入报告](/tmp/c2p-dsh-independent-l01-packet16-postlive-20261006-01/review.md)。
用户已明确“解除冻结，按具体方案开发验证”；该回复不授权新模型请求、重发packet16或直接
释放旧占用。恢复与 fresh live 必须先完成独立可审查的具体操作包。

## 实施合同

- 真实 registered terminal 分支允许 `stop` 和 `tool-calls` 登记自然完成；普通 text stop、
  unknown tool、缺 usage/finish、provider error 仍按各自拒绝与占用合同处理。Python 原
  raw/Session/args、真实 usage、顺序、结算及 exact owner 验证保持。
- Writer 可见投影保留 canonical `semantic_atom`、条件、极性、render policy 与 authority lane。
  atom 的 exact witness 仍归 Binder；它的正文语义要求不能随 witness 的隐藏一起丢失。
  内部 anchors/excerpts 不重复投影；原页、私有 targets、required atom、Formula 和关系门保持。
- `native_stop_retirement.py` 是独立历史 operator：验证原自然 stop/DONE、成功 Tool/Result、
  六 fees、拒绝结算、冻结请求和原授权；保留 task/raw/fees，只允许 exact owner CAS 退役并
  追加 `DshNativeStopBackendReleaseV1`。绑定此前 history 字节摘要、当前实现、具体 plan/review/auth，
  重入幂等、事务中断恢复、retired owner 禁止重获。它不注册旧 execute quiescence、
  不结算新费用、不产生候选、不调用 provider，也不进入 Worker RPC。

## 原失败交回 owning Agent

原 parser/assessor 对 packet16 原字节仍拒绝；保持正文不变，扩大 witness 或删除 witness
也不能通过。条件为空、极性未知，错误名称不能解释成实际缺条件或乘法错误。
`writer-owner-feedback.json` 通过原 paragraph repair 与 WriterSectionRepairPacketV1 builder
生成一次有界 Writer-owned 反馈，保留原 raw digest、缺失关系与既有 Formula 合同。
这是修复输入与追踪材料，不是新 Writer 正文或已闭合内容。后续真实生成仍需 fresh packet。

## 验证范围与收口

首次原边界与内容测试83 passed/56 subtests；新恢复与内容投影聚焦60 passed。
TypeScript typecheck/build/stage完成；native stop draft真实 Loader隔离链通过。
同轮拒绝用例遭并发源码修改触发 `composition_source_unstable`，该轮不作为完整验收；
源码收口后以新身份重新验证。原完整11的1876/cold证书只适用于旧595/c458身份，不能换标签。
新 required suite计划/11 已纳入两个 native stop用例和历史恢复测试。最终完整/cold及独立
审查完成前不启动 canonical 恢复或新 live。历史 packet10 待同步补丁不应用。


本批后续观察：稳定native stop两个场景通过、历史恢复聚焦32通过、保护克隆通过且
canonical逐字不变；独立恢复代码/方案457绑定PASS/APPLIES，读集释放。
完整12仅两处required plan版本断言未同步，已保存失败并通过原manager停止流程，
不计为验收；同步/11后新完整13和最终独立复验另绑定身份，旧review保持原0e63/4fd8。

## 完整14实际终止：行为通过，证书拒绝重复身份

完整13的第三处UNIT fixture仍使用旧/10，六个target integration案例提前被/11门拒绝；
原隔离单文件复现6 failed，保存原失败并具名停止原pytest、manager exit1。
仅同步该fixture版本后，三处版本表面及原准入反例49 passed，绑定新2bbb/4fd身份启动完整14。

完整14原manager62468实际exit1：Python1682及56 subtests通过，Node228全部通过且0失败，
但严格机器reader报`offline_node_duplicate`，完整receipt passed=false/passed_count0，cold未执行。
真实重复恰为两个native stop wrapper与原default draft/wrong_atom_binding共享同一
host-provider文件/行/列/名称/层级。原验证与拒绝门均保留，不能把行为计数替换为完整证书。
两次真实native stop回读确认：一terminal有领域receipt、一cancelled无receipt；均已注册
native stop quiescence、费用17/pending0、各自隔离backend owner空；这不改变canonical旧16。

仅在共享test title为实际`nativeFinish=stop`增加区分后缀，不改行为、门禁或覆盖计数。
聚焦真实Node与原机器reader、全局身份冲突检查收口后绑定新身份完整/cold及最终独立审查。
完整14所有原日志、失败receipt和原2bbb身份保留于`/tmp/c2p-dsh-l01-admission-20261006-14/`。
当前用户开发验证授权有效；仍无新真实生成/tokenize、canonical恢复或服务修改。

## 2026-10-06 用户要求精简后的差异验收

用户明确要求身份类差异不再导致原地全量重跑，随后要求快速解决并推进。
因此，上一段计划启动完整15的做法被本节替代：保留完整14的原失败证书、原
Python1682/56subtests及Node228实际通过报告，改名后的两例真实隔离DSH测试已通过
（173.23秒），不重新执行相同的整个行为套件。旧报告不会改标签或覆盖。

为使已有报告能被原操作入口消费，增加仅离线的core证据复用入口：原serial Node
事件按真实entry-file划分并调用原严格reader，跨文件同名测试保留独立身份，同一
文件重复、缺结果、fail/skip及总数不一致仍拒绝。复用必须绑定原source/plan/runs、
当前独立差异审查与聚焦验证；只允许文档、已证明的纯测试名插入和此离线验证层
变化，业务代码变化仍拒绝复用，实际runtime字节仍逐项比较。原始费用、内容门、
完成与恢复规则没有变化。还须新执行原operator与fresh cold，两者不能继承PASS。
具体原始报告与验证产物保存在 `/tmp/c2p-dsh-core-reuse-20261006-01`。

当前具体恢复和fresh live仍按已授权范围准备；不因测试名或文档更新重复请求
源码解冻。开发授权本身不作为新增模型调用或直接释放canonical的授权。


## packet16 恢复、packet21/22 实际执行与当前发射合同修复

用户后续明确要求精简身份确认、修复后继续测试，并在当前goal中授权必要真实live直接执行。
此指令覆盖当前同范围操作；每次仍形成具体fresh包并记录真实授权依据，不伪造旧问答，
不复用旧packet授权，不增加无变化采样。源码和文档变化不再单独请求解冻。

原packet16已按具体受信native stop恢复计划执行，原非lease文件与七条旧history逐字保持。
原费用7705/392及领域失败保留，canonical占用已恢复；具名结果：
`/tmp/c2p-dsh-gate-l-next-operation-20261006-01/recovery-result.json`。

packet21一次1 primary+1 tokenize、usage7819/565，原生stop完成登记与释放成功；
schema缺schema_version/含额外字段，独立Gate-L FAIL。定位到实际Qwen XGrammar将
显式strict:false解释为参数约束退出；原SDK公开compat开关可省略该字段，完整声明schema
保持原值。当前实际SDK零网络对照及部署venv中的qwen_3_coder CPU完整grammar编译通过，
未修改runtime/服务。on-disk/CPU证据不冒充已加载实例或模型结果。

改动涉及实际投影裁决，执行原完整15一次，Python1716、Node228、原operator1，共1945；
原fresh cold1通过，session93810实际exit0/reaped。两个固定独立suite并行执行，原命令、
覆盖及reader不变，均绑定81871a219cfecd2f7e9a27a55be76830f81fc9e060c714fb327cdb33303e617d /
569636b89ccd0ba3bdd564922370eb7141197239526b102242779c5fc73cf284。原报告：
`/tmp/c2p-dsh-l01-admission-20261006-15`。代码/最终材料各独立PASS/CLEAR并释放读集。

packet22按当前范围具体计划一次执行，session94180实际exit1/reaped：1 primary+1 tokenize，
HTTP200、唯一stop/DONE、原生c2p_terminal及Session来源闭合，usage7815/223/8038与tokenizer
一致，spent7815/pending0、完成登记true、backend empty。779字节原raw已独立按冻结完整schema
验证合法，但paragraph未提供witnesses，原required_target_contract拒绝；不得把正确服务端
序列化或正确计量当作Gate-L。独立结果与实际读集释放：
`/tmp/c2p-dsh-independent-l01-packet22-postlive-20261006-01`。原10条严格history通过、旧9条
逐字保持；旧14费用UNKNOWN/pending32768/1保留，未据此次生成补写旧usage。

当前仅补原Writer的native emission：新候选显式提供structured paragraphs和每段witnesses，
移除这些字段的旧默认值提示，原native及完整schema guard均先于concludeTurn执行。
旧publication schema/数据读取保持原语义；空witness数组仍由原段落required-target/content
owner拒绝，所有semantic/qualifier/formula/evidence门保持。没有在schema放入正确正文或
已知exact_text，没有修旧raw或服务配置。当前发射合同验证进行中；完整15是上述绑定身份的
历史完整结果，不冒充新返修代码已验收。Gate-L仍FAIL、24/49；下一次只执行有变化fresh包。


### 2026-10-06 packet24 实际结论与有界算术 owner 修复

原完整17实际1948通过（1717 Python、230 Node、1原operator）、fresh cold1，原session51924 exit0/reaped；7c7a15fb379f698b66f9954093444b5155892b5980a66a1e22aa01f6d3636fde / d01ff787d5a664adf2a2207ea0b7ed6f761b95aa535084a8362e272b29fc38cb。独立最终材料CLEAR且读集释放。packet24按当前用户同范围live任务指令具体一次，session15871 exit1/reaped；1 primary+1 tokenize，真实usage8009/324/8333，native stop注册、完整schema与detail witness存在；spent8009/pending0、原owner自然释放、canonical empty/11严格history，旧14费用UNKNOWN保留。没有重发或服务修改。

独立实际Gate-L FAIL：原exact source `return a * x`，闭合semantic为scalar a/input x/output y；原witness为完整主动句“multiplies … by …, yielding …”。anchor与condition/polarity均通过，仅原算术表达语法拒绝，不能把reported condition_or_polarity标签当作真实极性丢失。原失败/raw不改、不倒签。独立证据及实际读集释放：`/tmp/c2p-dsh-independent-l01-packet24-postlive-20261006-01/`。当前在原publication_transaction_contract owner增加单一source AST双标识符乘法的完整主动句，结果和operand roles由closed semantic contract导出，全句匹配；没有项目答案注入。新完整parser/assessor正负例及泛化符号反例验证中，旧完整17仅历史绑定，不冒充新代码验收。

用户明确普通无破坏性决策直接执行，沿同范围修复/必要验证/独立阶段验收/fresh changed25推进，不再增加身份确认流程。源码修复涉及实际内容判定，收口后一次必要当前完整/cold；保留旧失败、质量门、一次请求及预算。Gate-L PASS后连续M01–M03→P01–P04→G01–G08，分别独立验收。当前24/49、Gate-L FAIL、actual primaries11。

本批复验：原完整 parser/assessor及算术/条件/极性/绑定/Writer/Method质量八套聚焦，`PYTHONPATH=src:. PYTHONDONTWRITEBYTECODE=1 python -m pytest -q tests/integrations/dsh/test_l01_binding_contract.py tests/regression_20260917/test_witness_relation_matrix.py tests/regression_20260917/test_witness_projection.py tests/test_agentic_detail_atom_binder_and_trace_v2.py tests/test_llm_section_writer.py tests/test_agentic_method_authoring_p0_closure.py tests/test_agentic_14_vertical_tests.py tests/regression_20260922/test_invariants_i1_i10.py`，session47084 exit0/reaped，277 passed/7.81s；`git diff --check` exit0。首次仅算术补丁的actual24零网络复核仍missingatom，保留失败diagnostic；进一步定位Binder只从整句找atom，没有利用Writer已供完整detail子句。原Binder现在仅同detail_id、唯一原文子串、detail约束和atom独立锚点/约束均通过时复用，不裁切/改文，不借用sibling，不降低匹配阈值。新增八反例覆盖wronginput/result/foreign/detail与atom source disagree/重复/无witness；整体formula postfix原parser/assessor例通过。
当前actual24原raw零网络原owner复验 accepted=true、atom1、formula1、authority0/failures[]，路径 `/tmp/c2p-dsh-active-product-20261006-01/actual24-current-owner-diagnostic-binder.json`；原24 live失败与immutable raw保持。独立代码审查待结束，最终一次完整18/cold及fresh25尚未开始，不预报PASS。代码/文档收口后验证期只写外部/tmp产物。


### 2026-10-06 packet25 实际领域拒绝与 native cardinality 修复

本批原完整18实际1988（Python1757/56 subtests、Node230、原operator1）、fresh cold1全部通过，session11872 exit0/reaped，source b552057c84434a6d5c0cbbd762b31127723ae2265723c4773b9a5f9d16213dba / validator b0413693986e8b9834d1bf890c5cd76d60812d57519d632926b9865506b71915。独立算术/Binder CODE_PASS，真实原24 private refs/raw全链离线接受，仅诊断，不倒签旧失败；最终材料独立CLEAR/183输入并全部读集释放。

packet25在当前直接live范围下具体once执行，原session78607 exit1/reaped；1 primary+1 tokenize，8009/301/8310、HTTP200/native stop注册、spent8009/pending0/completed1。唯一实际content rejection为required_target_contract，raw950B/aaea08f2f14948ade4e7df272895c4058161a95bf86b005b929ad3e214d6ff1c，witnesses=[]。未把尚未正式评估的formula作为额外失败。独立 actual Gate-L FAIL/105输入，12严格history与旧11不变，canonical empty，旧14 UNKNOWN pending32768/1/completed0保留。报告 `/tmp/c2p-dsh-independent-l01-packet25-postlive-20261006-01/`；实际direct/transitive读集已released retained[]。没有重试、重发、服务变更。

当前最小接线修复：从原kernel冻结的model-visible Writer detail targets派生每paragraph native witnesses.minItems与明确paragraph_id scope；Binder atom/private exact anchors不进入schema。原DSH基础typed schema helper不支持minItems，但公开raw register/schemaOf在native mode原样携带参数schema。本项目writer-request仅认可并严格检查这一有限extension（array/safe nonnegative integer），其余结构仍由原DSH helper验证；原parseWire在concludeTurn前强制minItems，原完整schema/领域门保持。没有SDK/runtime补丁、正文注入或承认自报target事实。混合optional paragraph不被错误要求提供witness；同样target数量不代替内容/每target验证。

原96聚焦PASS（session45466 exit0/reaped/11.08s）；完整18保留历史绑定，当前业务变化未冒充已完整验收。新增真实C00原Loader/loop/pi-ai fakewire与empty witness拒绝用例、CPU actual grammar和独立审查待收口。首次typecheck未指定candidate，原peer selection门拒绝exit1，零测试/构建/模型；改用既定candidate/dev root精确配置，未修改环境绕门。继续只做有实际变化的fresh26，不复用25计划或旧授权、不重复身份确认。24/49，Gate-L仍FAIL。


WC-1 收口：首次真实 C00/host-provider 聚焦 native02 保留 20 PASS / 3 FAIL（session14081 exit1/reaped），原因是合法冻结合同的 required_detail_ids 非空、visible targets 为空，第一版只读后者。独立审查 BLOCK/WC-1 已释放全部读集。当前 native witness 数量统一由 required_detail_ids 与 required visible detail targets 的去重并集派生；paragraphs.minItems 同步覆盖原合同全部冻结段落要求。可选 detail 不被提升为 required，原完整内容门不变。新 default fixture 与重复来源反例补齐；三文件聚焦 session38470 exit0/reaped，98 passed/9.75s；git diff --check exit0。下一步原 DSH 同组 fresh native03、fresh CPU grammar、独立 WC-1 关闭后再集中一次最终完整19/cold；当前没有新 live、没有服务或 canonical 变更。


WC-1 独立关闭 CODE_PASS：fresh native03 原真实 Loader/loop/pi-ai 两文件23 PASS/0 FAIL/skip/cancel，session93065 exit0/reaped，103068ms；typecheck session19506 exit0/reaped。fresh probe02 仅 prepare/零模型分词网络，actual wire SHA256 7636d6bbb394ac75d72641fd2dc9bf66856f54c1b2baaea7e621a67fd0b67124；部署 xgrammar 实际 builtin CPU编译 PASS、原 builtin bytes4543784a…不变，无 loaded-instance success 冒认。独立报告 /tmp/c2p-dsh-independent-l01-witness-cardinality-20261006-02/ CODE_PASS/WC-1 closed，原23 report严格reader、原24 raw/current schema诊断合法、原25空witness与空paragraph拒绝、optional与去重/Binder排除均核验，21实际输入读集全部释放 retained=[]。旧24/25 actual FAIL保持，当前Gate-L仍FAIL。
修复收口，此后当前完整19/cold与fresh26材料验证期间不再改源码/文档；只有/tmp外部产物。当前12严格history/20只读证明已由原reader收集，backend empty、旧14 UNKNOWN责任不变。一次当前完整19/cold结束及独立材料CLEAR后直接按当前同范围任务指令执行changed fresh26，无重试/服务变更/身份确认。
