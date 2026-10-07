# 02 · Python 内核持续开发任务：请求/恢复、注册、不可变发布与索引

> 2026-10-03 18:03：**正式 Gate-K PASS**，见[四组验收与前置闭合登记](stage_four_group_repair_acceptance_20261003.md) §4。
> 保留原 K01–K04 独立 component PASS，791份内核输入再次匹配，B01-D1/G1–G7已关闭，实际Gate-H前置现已满足；没有重跑4129或重做内核。本份收口，第03份待实施。以下旧等待状态按原日期解释。

> 2026-10-01当前接口裁决见README§3.10与[申请文档§6](h04_loop_origin_escalation_20261001.md)：窗口二在新隔离runtime来源候选连续施工，原内核791个源码/测试身份仍不变，component保持，正式Gate-K等待。窗口一无需重复准备/全量或提前写C/R/validator。

> 2026-10-01 11:36当前：791个Python源码/测试身份及原日志不变，component PASS保持，正式Gate-K等待Gate-H；窗口一第03份只读复用调查已交付，保持候选，不重复调查/全量或提前改C/R。当前入口README§3.9与[本批裁决](stage_handle_acceptance_20261001.md)。

> 2026-10-01：本阶段component PASS保持，原源码/测试/日志未变，受影响身份29项通过；不重跑全量。正式Gate-K等待Gate-H，当前第03/04份仅只读准备，详见[R2裁决](stage_r2_acceptance_20261001.md)与README§3.8。

> 2026-09-30 21:36 后最新：K-1/K-2返修已实际闭合，原六模块103与K04/身份/真实调用方
> 282项独立通过；owner4129完整全量日志/退出码/三live skip已核对。K01–K04本批
> **component PASS，Gate-K仍等待Gate-H**，见§4.4、[返修差分裁决](stage_repair_acceptance_20260930.md)
> 和verification §10。窗口一保持已验候选冻结，不重复旧返修；本批QA已结束、读集释放。
> 原AT/正式依赖不变，第03/04份、RPC、live均未启动。旧裁决及失败原文保留。

依据：[总设计](../code2paper_dsh_plugin_design_20260922.md)、[执行入口](README.md)、
[验证规则](verification.md)、下列四张原任务卡和 [台账](task_board.json)。不新建平行发布/账本管线。

## 1. 最终交付与当前起点

交付一个可被后续 Writer 接入直接复用的内核：发送前合同与恢复结论准确；registration 读取
不会重封篡改；g2 任一写点失败不破坏 g1；JSON/Markdown reader 只能看到同代完整成员；
预算、证据、作者意图、来源与验收门保持。K02 producer 与 K03 真 reader 必须联合验收。

前轮 K04 GAP 证据批仅改测试/夹具（历史起点）：
[K04 evidence](../../tests/integrations/dsh/fixtures/K04_evidence.md) §16 记录四组实际产物、
7 个定向节点、145 项受影响回归与非空公式族。该批为 owner 证据，尚未独立 PASS。保留
G3/G4 已获 QA 的关闭、旧反例与原日志；不重新从基线实现。该批暴露的两项原 owner 问题已由
本次阶段候选申报修复，并与 K01–K03 一并接受独立复核，详见 §4.1。

本阶段唯一实施者仍是窗口一。窗口二不改 Python 内核；独立 QA 按需启动，只写审查资产。
本批 owner 释放和 QA closing 已完成，最新 component 已通过，窗口一保持 §4.4 的已验
候选。下列实施顺序与责任域保留为原合同，不表示现在重开返修；实际新发现或共享输入变化
仍由原 owner 连续处理，不另等逐问题开工许可。

## 2. 连续实施顺序（内部任务，不是逐项交接点）

### 2.1 K04：完成发送/恢复边界，修复新发现，再继续

1. 读取现有真实四组产物与节点：rejected 空摘要、明确 no-send 无回执、unknown-send、
   accepted 合法缓存。复核测试各自直接运行及组合运行，不依赖另一测试先跑生成文件；共享
   一份产物可由显式 session fixture 生成，不以磁盘旧报告或执行顺序充当前置。
2. 在原 `writer_attempt_ledger.py`/统一 reducer 修复发送前拒绝只认
   `attempt_limit_exhausted:` 的分类缺口。根据权威结构化发送/拒绝事实与 canonical failure
   语义分类，保留真实合同拒绝原因和计数；不能让有事件账本变成 no_events，不增加一套 reducer，
   不从任意错误文本臆测 HTTP 是否发送，不将未知状态降为明确未发。
3. 在原 Writer 相位/恢复预检修复 unknown-send 根因被下游 realizer 预算失败掩盖的问题。
   已有预留不清零、不补零 usage、不降低预算门；运行结果和持久记录须指向原阻断与可执行
   下一步。合法预算不足仍保留原正确拒绝，不把所有预算错误改名成 unknown-send。
4. 完成 GAP-1/3 三消费者与持久重读、GAP-2 非空 obligation/package 家族，恢复原 AT 的
   总映射。已知未发允许原策略重新准入、unknown 保留预留且不盲重发、accepted 缓存不重封。
   修复后聚焦回归通过即可继续 K01；K04 独立验收标记留给阶段 QA。

### 2.2 K01：严格注册与来源身份

按原卡拆“创建封摘要”与“加载验摘要”；pointer 要解析并验证磁盘不可变 record，来源字段、
schema、id/key/generation/文件名与声明摘要互相一致。合法重复幂等，同 ID 不同内容拒绝；
旧记录按版本只读，不原地迁移或自动重封。同步身份源清单与读取者，局部 AT 通过后继续 K02。

### 2.3 K02：多成员不可变事务与激活

复用原发布/租约 owner，准备不可变成员、registration 和 manifest；保持必要的持久化顺序；
锁内验证 expected-active 与持久 fence，最后切 active。receipt 丢失可从事实重建，导出投影
不变成第二权威。消除原 register 内部提前激活等真实旁路，JSON/Markdown/bytes 均有校验。
先有 g1，再对 g2 每个持久化/激活点注入故障，验证 producer；随后直接接 K03 真 reader。

### 2.4 K03：真实读取、恢复与阶段回归

现有索引读取按同一 manifest 和 registration 验成员，不能跨代拼装；显式 digest 零命中与
损坏新协议不回退。投影修复不重提交，legacy 只读范围明示。完成 g1→g2 的真实 reader 故障
矩阵、CAS 竞争、旧 fence、重复发布、回包丢失重放；受影响现用调用者全部验证。
不宣称全文 Writer 已事务化：局部 Writer 正文迁移归 C03，全文归 F02。

## 3. 阶段责任域与自主修复权限

窗口一持 K01–K04 下列卡片 owned paths 的**并集**，顺序串行修改共享身份源清单；另含：

- `src/code2paper/agentic/writer_attempt_ledger.py`、`unified_invocation_ledger.py`：仅原
  Python 发送事实/恢复分类/预留结论的必要修复；`unified_context_models.py` 的相应真实回执
  表示与现有消费者。R02 的新 DSH RPC/事件协议仍未启动，不借此做平行余额或新运行控制层。
- `tests/regression_20260917/test_ledger_recovery.py`、`test_ledger_recovery_matrix.py`、
  `test_publication_transaction.py` 及各卡已列出的直接测试/夹具；允许把同层直接回归放入这些
  现有文件。非必要重构、其他业务阶段的文件不因此全域开放。
- 运行/持久证据更新既有 K04、K01 专属证据或本阶段 [kernel_stage_evidence.md](kernel_stage_evidence.md)；
  原始日志使用新鲜任务根，旧 release 脚本不能覆盖原日志。总派工与台账仍由 LEAD 维护。

范围内发现就地修原 owner并验证，不为每个函数申请额外路径。确需跨阶段公开协议、TS、日常
环境或更改验收语义，才给出具体必要变更交 LEAD 协调。已授权的原账本文件不再作为停工理由。

## 4. 本地验证、交付和阶段通过条件

内部持续运行有意义的聚焦测试，避免全套每改一处重跑。至少一次最终同代码状态的阶段集合：
K04 全部 AT/消费者恢复/家族语义，K01 篡改与幂等，K02+K03 多代真实 reader 故障矩阵，以及
真实调用方和身份敏感性回归。命令/fixture/节点可执行，未测项具名；零测试、必要 skip、异常
和超时不得算通过。报告成功行为、拒绝原因、持久状态与预算去向，不能只报总数。

全部内部验收完成后一次提交：阶段范围/接口版本，代码/测试/fixture/runtime（若读取）与
validator/config 身份，AT→正反例→节点→日志，旧/新存储与恢复边界，完整读集，写权释放。
窗口三可以提前只读审查一个真实设计风险，但不把咨询结论变成每单元开工许可。正式 QA 对
同一阶段候选集中审查，缺陷整批回交窗口一，改后只复验受影响项。

若 Gate-H 尚未完成，Python 全阶段仍可开发和独立 component review；**不能正式通过
Gate-K 或把依赖未满足的 K01/K04 标 done**。目标 Gate-H 与本阶段全部 AT 通过后才能进入
第 03/04 份集成。冻结期间保护实际读集，另一窗口不相关工作照常继续。

### 4.1 本次完整阶段候选与 QA 交接（2026-09-30）

owner 交付：[kernel_stage_evidence.md](kernel_stage_evidence.md)，摘要
`76ae499bc9baa7cb849819607f09c772a272df236debd2a5720f71ce46bd0e88`；写权释放记于
`.agent/implementation.md` 的“Python 内核阶段（K04 收口 → K01 → K02 → K03）写权释放”节。
LEAD 只读核对证据表 12 项及最终 S7 清单 12 项均命中。原始日志根
`.dsh-dev/run/w1-kernel-stage-final/` 的 S1–S5 摘要和退出码均与 owner 表一致；
27/15/8/24/89 是各命令结果，不能相加当成全部 AT 独立通过。全量 4114/3 skipped/12 subtests
由 owner 报告，QA 需核对原日志、运行身份与必要测试是否被跳过；无需仅为同步文档重跑全套。

本次新增生产变化为拒发分类/原始恢复原因、严格 registry、generation 发布与真实 reader；
页复核、编译器、receipt 模型、Formalizer 四文件延用上一批字节。窗口三沿已有 K04 反例，
在同一完整候选上集中验证 K01–K04；尤其补真实竞争/新进程恢复和历史格式事实，细项见
[verification 本批说明](verification.md)。未测先登记为 coverage gap，实测违约再登记缺陷。

身份元数据需在入场时一次对齐：证据 §6 称 S7 有 23 项，最终 S7 实际列 12 项，证据表也是
12 项且成员集合不同。不得将其称作完整读集；QA 将两表、实际测试/fixture/validator 依赖取
并集并在运行前快照，保留两份原始清单，不倒填 owner 历史运行身份。此整理属于同批入场，
不拆出一轮元数据派工。writer 释放不等于全 AT 通过，正式 Gate-K 仍未开放。

### 4.2 整阶段返修包（2026-09-30，沿原任务连续完成）

窗口一只读确认的缺口与 [LEAD 审查](verification.md) §7 合并为一次返修。本批读集明确
释放及 LEAD 核对已登记于同文件 §8；写入交接已完成，直接实施下列全部内容，直至可独立
复验的完整包，不再申请任务或逐项开工。

1. **证据与 runner。** 旧日志/报告只读保留，新根使用 `.dsh-dev/run/w1-kernel-rework/`
   或新鲜子目录。逐命令收真实退出码，保留首次失败；统一候选源/测试/fixture/validator/
   读集清单，明确旧 23 项、最终 12 项及各自身份，不能覆盖 S7 后仍引用旧项数。最终候选
   跑一次完整静态套件并保存完整日志、实际 argv、退出码与 `-rs` 的逐项 skip 原因；这是
   补首份可审计全量证据，不要求每次修一个缺口重跑全套。必需 AT 不得 skip。
2. **原账本冲突事实。** 持久回执说未发送而 request/response 证据存在或损坏时，原
   reducer 不得落成 `no_events`/可释放未发，不退款、不盲重发。request 文件存在不等于
   HTTP 已送达，不能因此伪造 usage/实际发送成功；按原 typed failure 与可信持久事实处理
   冲突。合法 accepted/no-send/unknown 的对照仍成立，正常预算耗尽仍走原具名预算拒绝，
   新 unknown/corrupt 相位门不能吞掉它。
3. **真实 1.0 兼容。** 从冻结 `0918ee7` owner 在隔离子进程生成并保存真实旧指针/record，
   记录冻结模块与所需依赖身份；新 reader 具名只读、前后字节不变。测试若暴露原 registry
   reader 缺陷就在原 owner 修，不把新记录改版本号当历史证据，不使损坏新格式降级。
4. **真实写点与并发/恢复。** 将 stage/prepare/commit/switch 现有 owner 的实际持久点
   映射到故障矩阵；成员阶段可以保留独立 API，但须纳入同一不可变/崩溃恢复保证，不强制
   为点名合并函数。真实多进程 barrier 竞争同一 expected-active/fence，新进程核对唯一
   成功者和持久单调 fence；关键写点让子进程退出，再用新进程真实 reader 恢复。派生
   receipt 无写点就登记 N/A；导出投影指明实际 owner/验证点，不能用夹具写入冒充生产
   写入，也不扩成 C03/F02 全文迁移或声称断电保证。
5. **三方权威与收口。** 故意使注册表 active、持久发布 active 与派生索引不同，断言
   原 reader 只认发布权威、不会自行挑代；单独验证投影损坏/修复不重提交。完成受影响
   AT、真实调用方与 validator 身份回归，再交统一输入、覆盖矩阵、日志和本批写权释放。

本批写权仍覆盖原 K01–K04 并集及已授权的原 ledger/model/identity/test owners；新增 DSH
RPC、领域合同、正文迁移没有放行。LEAD 已核对 `6046464f…`/`c8412d00…`/`19ec39c5…`
本就属于上个完整交付，不再要求补一次“未声明修订”。返修范围由实际缺陷/证据缺口决定。

### 4.3 本批独立反例与连续返修（2026-09-30 19:01 后，历史；接续见§4.4）

窗口一新实施者已交 [内核证据 §9](kernel_stage_evidence.md) 并释放写权。本轮真实
独立聚焦 99 passed；完整全量日志/argv/exit 与三项 live skip 已核对。真实旧 owner 1.0、
实际持久点/退出86/新 reader、双进程 barrier CAS、三方 active 与投影修复的新增节点
均已运行通过，保留有效证据，不从零重做 §4.2。

集中返修仍在原并集内，实际证据见 [本批裁决 K-1/K-2](stage_acceptance_20260930.md)：

1. **K04 原重放/归约接线：**同 validator 接受重放会把矛盾发送事实变成
   accepted_reusable、清空 unknown，而逐 attempt 仍保留预留。合法重放先落盘后
   引入矛盾回执也复现；损坏 request 时 accepted 标志亦不一致。原 reducer、缓存/
   resume 与相位边界一起闭合，正常 accepted/未发/unknown/预算耗尽对照不得退化。
2. **K03/K02 原真实 reader：**verifier 成功后 reader 再读被替换的 manifest，返回
   g2 成员却标 g1 摘要/已验证。保证同次消费的 manifest/成员字节确实绑定权威，
   不借创建 validator 重封损坏输入；保留发布 active、projection 与崩溃恢复行为。

本批 QA 结束、读集释放见 verification §9；窗口一继续原整阶段写权，不等 Gate-H，
不逐缺陷申请。新鲜 rework 子根保留本批首次失败/真实退出码；受影响 AT/真实调用方/
validator 身份回归齐后，最终稳定源码保留一次全量 `-rs` 日志，再交完整差分与释放。
正式 Gate-K 和原依赖/所有 AT 不变，C03/F02、RPC、live 未放行。

### 4.4 返修差分component通过与候选保持（2026-09-30 21:36 后，当前）

[内核证据§10](kernel_stage_evidence.md) 的源码、日志、统一输入和释放已核对；
[本批裁决§3](stage_repair_acceptance_20260930.md)绑定全部原AT与真实consumer。
独立原103/282集合和原反例重放通过：同validator重放不覆盖矛盾/损坏发送，已有合法replay
之后冲突仍unknown/accepted=false/预留保留；真正验证后换manifest字节具名拒绝。
真实Writer入口在有效矛盾回执下以原unknown相位原因零发送，doctor同首因；损坏字节更早
被原诊断完整性门拒绝，不退款、不盲发。创建期封摘要与读取期权威绑定保持分离。

本批接受K01–K04 component PASS；正式H03/H04/Gate-H前置未满足，不登记done或Gate-K通过。
窗口一核对并保管本批候选、validator与4129完整日志，当前没有新的本阶段返修项；可只读
准备第03份消费接口，不提前实施。实际共享输入变化由LEAD协调原owner必要变更及受影响
回归；无变化不重复整套或补派旧已闭合问题。旧§4.2–§4.3过程、日志与原QA裁决不覆盖改写。
closing/完整读集释放见verification§10，后续调度以执行入口§3.7为准。

### 当前实现与修补落点

| 已有 owner（行号绑定0918ee7） | 当前事实 | 责任任务 |
|---|---|---|
| [registry](../../src/code2paper/agentic/authoring_artifact_registry.py) :61/73/97/128、:203/242 | 加载 validator 会重封摘要；registration ID 未绑定完整 producer/upstream，同 ID 可替换元数据 | K01 |
| [publication](../../src/code2paper/agentic/authoring_artifact_publication.py) :168/190/276/289 | 验证只支持 JSON；先覆盖固定目标再登记，无多成员 CAS/fence | K02 |
| [index](../../src/code2paper/agentic/authoring_artifact_index.py) :635/696/810 | 已拒损坏索引回退，并按字节验证；缺 manifest→record→多媒体成员的一致读取 | K03 |
| [page recheck](../../src/code2paper/agentic/page_contract_recheck.py) :319 | 基线缺陷：actual technical digest 为空时跳过；原空值跳过已修；首轮 QA 部分通过，G1–G3/G6 真实调用点证据待收口 | K04 |
| [Unified 编译器](../../src/code2paper/agentic/unified_context_compiler.py) :2928/2984/3035/3127 | B01-D1 基线 set 顺序漂移；首轮 QA 已证明跨 seed 完整 payload、同 ID 集顺序与紧预算守恒；G4/G5 另作单变量实验 | K04，Gate-K 阻断项关闭待 QA |
| [Writer caller](../../src/code2paper/agentic/publication_method_writer.py) :4742/4850/4949/5217/5395 | 外层另有真实字节逐字保护、计量、累计预算；只调用 helper 会丢这些保护 | K04 |

K01 的创建摘要和读取校验必须分开；新的 registration 协议严格，legacy reader 保留具名只读语义。重复注册以完整逻辑内容判幂等，观察时间不应使同一次提交变成新产物，也不能丢 provenance 来获得同 ID。

### 发布协议最低合同

原 lease owner 先取得持久单调 fence。写 generation/content-addressed 成员、不可变 registration、绑定正文/acceptance/authorship/原结果引用的 manifest，并完成必要文件及目录 fsync；在 lease 中比较 expected-active 和 fence，最后原子激活。commit receipt 应可从已持久 manifest/激活事实重建，不能出现“必须先有 receipt 才能激活、又必须激活才写 receipt”的不可恢复环。索引只是同一权威指针的派生视图，不能另选 active。

验证先建 g1，再对 g2 的每个 member、record、manifest、激活前后、receipt 与导出投影故障注入；覆盖并发 expected-active、旧 fence、回包丢失。K02 的 producer 测试只是局部证据，**K02+K03 用真实 reader 完成故障矩阵后才通过 Gate-K**。Markdown 不得绕过 publication owner 直接写文件。

### 范围和回归

现 publish_artifact_transaction 主要由 authoring_execution_identity :1670、autonomous_method_agent :4124 调用。Writer 全文 _write_publication_outputs :27880 仍分别写 Markdown、authorship、checkpoint。C03 接新局部 Writer 事务；F02 才迁移全文输出，不能在 K02 后声称所有正文已原子发布。

K04 从真实 actual bytes 重算，而非只比较两个声明 hash。旧 caller 与 DSH 后续 adapter 必须共用同一个公共复核。对合法旧输入由可信适配器补实测字段；缺材料不能靠“兼容”省略。已有 cap 相等、空白名单、作者语义及 C04 多 detail 公式闭包门继续运行。

B01-D1 由 K04 在原编译器修复：候选估量、合页与 flush 全程保持冻结 Narrative 顺序，不能通过固定 hash seed 或字典序排序隐藏缺陷。用多段落、非字典序 ID 的输入在多个独立进程和 hash seed 下验证段落顺序、page ID、技术字节及 writer 请求均一致；预算分裂时仍保持顺序与义务守恒。届时将 B01 的“确认漂移”特征测试改为稳定性回归，并更新该目录 provenance；不能留下一个要求缺陷继续存在才能通过的测试。此缺陷影响任务材料身份，不能直接等同于 I01 的运行组成摘要漂移。K04 完成前不得通过 Gate-K 或据此冻结 Writer 合同。

新存储协议失败时拒绝新路径；旧档案只读、不重写、不将错误新记录降级重扫。故障恢复只重建派生索引/receipt，不重算有争议事实为成功。

## 实施单元

每单元由owner实施、reviewer独立复核；同一文件只能由一个活动任务写入。下列路径标“拟新增”的当前不存在，不是已有能力。

### K01 · 严格注册读取与完整来源身份

| 项 | 约定 |
|---|---|
| owner / reviewer | CORE / QA |
| 前置 / WP | B01, H03, H04 / WP1a |
| 当前开发启动 | 窗口一；K04 前置实现与本地合同/恢复回归通过后直接开发，不等待 K04 独立 PASS；原完成前置和目标 Gate-H 仍约束 done |
| 独占编辑范围 | `src/code2paper/agentic/authoring_artifact_registry.py`（现有）<br>`tests/regression_20260917/test_artifact_registry.py`（现有）<br>`src/code2paper/agentic/authoring_execution_identity.py`（现有）<br>`docs/dsh_execution_20260928/k01_registry_evidence.md`（拟新增，仅本单元证据） |
| 步骤与交付 | 拆创建封摘要与加载验摘要；新record身份覆盖producer/upstream及完整逻辑内容。加载核对磁盘不可变record、pointer、schema；同完整内容幂等，同ID不同来源拒绝。旧记录具名只读，不原地迁移归档。 同步维护原VALIDATOR_BUNDLE_SOURCES版本化来源清单，仅添加本任务已落地的裁决文件；由LEAD串行分配该共享文件写权。 |
| 验收 AT-K01 | 篡改upstream/producer而保留声明摘要、删record、pointer替换、同ID不同来源均失败；合法重复保持原record，不借model validator重新封印损坏值。 仅改变新增/抽取的裁决逻辑即可使validator身份变化，缺来源文件明确拒绝。 |
| 待形成测试/证据 | `test_artifact_registry.py` |

### K02 · 不可变多成员发布与CAS/fence

| 项 | 约定 |
|---|---|
| owner / reviewer | CORE / QA |
| 前置 / WP | K01 / WP1a |
| 当前开发启动 | K01 实现与本地合同通过即可继续；不要求 K01 已独立 done，正式完成依赖不变 |
| 独占编辑范围 | `src/code2paper/agentic/authoring_artifact_publication.py`（现有）<br>`src/code2paper/agentic/authoring_execution_identity.py`（现有）<br>`tests/integrations/dsh/test_publication_generation.py`（拟新增）<br>`tests/regression_20260917/test_publication_transaction.py`（现有，真实发布回归）<br>`src/code2paper/agentic/authoring_artifact_registry.py`（现有） |
| 步骤与交付 | 扩原发布owner为generation/content-addressed成员、不可变record与manifest；明确JSON/Markdown/bytes media校验及fsync顺序。原lease owner提供持久单调fence；active最后在锁内比较expected-active/fence切换；receipt/replay及投影可重建。 在原register_authoring_artifact拆开不可变record准备与active切换，消除内部抢先激活的旁路。 同步维护原VALIDATOR_BUNDLE_SOURCES版本化来源清单，仅添加本任务已落地的裁决文件；由LEAD串行分配该共享文件写权。 |
| 验收 AT-K02 | 先有完整g1再让g2每个写点崩溃，只能读完整g1或g2；旧fence、并发CAS、已commit回包丢失、重复激活均安全；成员及来源不能被后代覆盖。 仅改变新增/抽取的裁决逻辑即可使validator身份变化，缺来源文件明确拒绝。 |
| 待形成测试/证据 | `test_publication_generation.py` |

### K03 · 索引消费manifest与兼容读取接线

| 项 | 约定 |
|---|---|
| owner / reviewer | CORE / QA |
| 前置 / WP | K02 / WP1a |
| 当前开发启动 | K02 producer 本地合同通过即接真实 reader；K02/K03 联合独立验收，完成依赖不变 |
| 独占编辑范围 | `src/code2paper/agentic/authoring_artifact_index.py`（现有）<br>`src/code2paper/agentic/authoring_artifact_publication.py`（现有）<br>`tests/regression_20260917/test_artifact_index.py`（现有）<br>`src/code2paper/agentic/authoring_execution_identity.py`（现有） |
| 步骤与交付 | 让验证读取按同一manifest校验成员和不可变registration；扩media-aware读取，固定文件名只是导出投影。原现用publication调用者保持正确；explicit digest零命中/损坏索引不回退。列出旧正文尚未迁移路径。 同步维护原VALIDATOR_BUNDLE_SOURCES版本化来源清单，仅添加本任务已落地的裁决文件；由LEAD串行分配该共享文件写权。 |
| 验收 AT-K03 | JSON与Markdown均读取同次已验证字节；manifest成员不全/角色混代/record漂移拒绝；投影损坏不改变权威active，修投影不重提交；不宣称全文Writer已事务化。 仅改变新增/抽取的裁决逻辑即可使validator身份变化，缺来源文件明确拒绝。 |
| 待形成测试/证据 | `test_artifact_index.py` |

### K04 · 抽完整实际请求复核并封住缺失摘要

| 项 | 约定 |
|---|---|
| owner / reviewer | CONTRACT / QA |
| 前置 / WP | B01, H03, H04 / WP1a |
| 当前开发启动 | 窗口一；仅开发前置为 B01（已 done）；原前置仍约束完成/集成，AT 不减少 |
| 独占编辑范围 | `src/code2paper/agentic/page_contract_recheck.py`（现有）<br>`src/code2paper/agentic/publication_method_writer.py`（现有）<br>`tests/regression_20260917/test_page_contract_recheck.py`（现有）<br>`tests/regression_20260922/test_authoring_contract_closure.py`（现有）<br>`src/code2paper/agentic/authoring_execution_identity.py`（现有）<br>`src/code2paper/agentic/unified_context_compiler.py`（B01-D1 原 owner）<br>`tests/integrations/dsh/test_legacy_characterization.py`、`tests/integrations/dsh/fixtures/`（B01 完成交接后转交，仅更新 D1/G1 回归及 provenance）<br>`src/code2paper/agentic/formalization_agent.py`、`tests/test_agentic_formalization_guards.py`（本轮新增窄写权，仅 G7）<br>`src/code2paper/agentic/unified_context_models.py`（本轮窄范围依赖，仅 ActualRequestReceiptV2 被拒请求的未实测表示；R02 未启动）<br>`tests/regression_20260917/test_ledger_recovery.py`、`tests/regression_20260917/test_ledger_recovery_matrix.py`（真实消费者/恢复）<br>`src/code2paper/agentic/writer_attempt_ledger.py`、`src/code2paper/agentic/unified_invocation_ledger.py`（本阶段新增：仅原发送事实/恢复分类/预留 owner，不提前实现 R02 DSH RPC） |
| 步骤与交付 | 公共入口整合现捕获caller对shared_contexts真实技术字节的重算与页合同；旧caller和后续DSH共用。缺材料/必需digest拒绝，声明值不能替代重算；保留页scope/作者语义/post-clamp cap/真实计量门。修复 B01-D1 原编译器保序，并反转其特征测试。同步维护原VALIDATOR_BUNDLE_SOURCES版本化来源清单，仅添加本任务已落地的裁决文件；由LEAD串行分配该共享文件写权。 |
| 验收 AT-K04 | 缺digest、改材料保留旧hash、伪造hash、repair改材料、cap升降、空公式scope扩张、作者目标改变都在真实发送点零发送；合法旧请求经可信adapter从bytes补值仍通过。B01-D1 跨进程/多 hash seed 的非字典序多段落输入保持 Narrative 顺序、页身份和请求稳定；紧预算分裂守恒。仅改变新增/抽取的裁决逻辑即可使validator身份变化，缺来源文件明确拒绝。 |
| 待形成测试/证据 | `test_page_contract_recheck.py test_authoring_contract_closure.py test_legacy_characterization.py`；G7 影响时追加 `test_agentic_formalization_guards.py`，全部映射至真实 owner |

## 验证、交接与完成门

以下保留原执行入口；当前实际运行范围见阶段证据与本批验收裁决，不能把入口列表视为本轮
全部已逐条运行。新增任务测试落地后按上表AT逐项登记实际节点/断言，不可只登记文件名。

```bash
python -m pytest -q tests/regression_20260917/test_artifact_registry.py tests/regression_20260917/test_publication_transaction.py tests/regression_20260917/test_artifact_index.py tests/regression_20260917/test_page_contract_recheck.py tests/regression_20260917/test_formula_dependency_closure.py tests/regression_20260922/test_authoring_contract_closure.py tests/integrations/dsh/test_legacy_characterization.py
git diff --check
```

交接包包含：任务ID、输入/代码/配置身份、接口及存储版本差异、改动文件、最小反例修前/修后结果、真实接线证据、准确命令/退出码/原始输出引用、未测项与恢复办法。独立reviewer依据 [verification.md](verification.md) 复核；Gate-K要求K01–K04及K02+K03真实reader故障矩阵。 各门要求对应AT及跨任务接线，不凭一个helper单测结案。

[返回总执行入口](README.md)
