# Codex 工作记录（最新独立检查点）

## 2026-10-04：扩为第04–06份长期模块，默认单主执行者、按需协作

用户明确可以不并行，要求根据执行文档布置更大的长期模块。本轮核对原第04–08份、任务依赖、总设计§§20–22及实际路径/脚本，发布[第04–06份长期模块](../docs/dsh_execution_20260928/stage04_06_long_module_execution_20261004.md)：23项连续责任，22项离线与1项具体准入的L01，终点Gate-G完整流程接线。第04份七项仍为立即可实施范围；后续按原Gate-R/V/L/M/P/G0/G接续，未改AT/depends_on，也未跳过Gate-L。第07/08份九项为后续模块。

默认一个主执行者可承担Python和TS全链；有稳定独立工作面才拆分。原两窗口表改为可选职责方案，共享Python协议/validator与peer/build始终各一位实际写者。实现人手可串行不删除P01–P04产品能力；默认产品parallel=false不变。独立QA在完整阶段包就绪后按需启动，可串行交接，不常驻。

长指令逐段给出修改落点、完整失败矩阵、真实9/16节点恢复及角色要求、准入和证据/会话接续；§8为可直接转交的统一指令。同步两级导航、第04细则及第04–06原执行文档/verification；纠正已存在路径被标“拟新增”和未定义test:integration命令。本轮仅改计划/协调记录，不实施产品、不运行pytest/build/live，17 done/32 planned保持；验收报告与封存原字节保留。

文档核验通过：23处新增链接/锚点存在，49项原任务除8处路径存在性标注外所有字段不变，第04–06份AT原文及verification门表不变；23项均planned，22项offline与L01 separate_live分类一致。相对2116项输入，只有9份协调文件和1份新增长期指令变化，其余源文件字节/metadata保持；`git diff --check` exit 0。完整前后快照、修改脚本与检查在 `/tmp/c2p-dsh-long-module-plan-20261004-seh65fat/verification.json`，没有重复运行产品测试。

## 2026-10-04：第03份 GC 返修独立 Gate-C PASS，发布第04份完整指令

用户提交两窗口联合冻结包要求验收与下一批指导。本轮未参与生产实现，完成GC-1/2/3和原六项AT的独立复验，三组关闭、Gate-C PASS，I01/C01/C00/C02–C04登记done。49项更新为17 done/0 in_progress/32 planned。完整[裁决](../docs/dsh_execution_20260928/stage03_gc_repair_acceptance_20261004.md)及[第04份整批指令](../docs/dsh_execution_20260928/stage04_batch_execution_instructions_20261004.md)已落地；后者含七项修改、全部必测反例、四次交接、实际命令、一次封存与§6可转发指令。本轮未启动04实现。

本轮独立226专项、265原owner、165 TS/真实native、48 B02、只读typecheck/audit、12份完整schema/goldens字节对照通过；原Unicode12例全部一致。真实worker技术/作者/新revision、新cap重编零发送、34次原协议RPC、5组旧材料prepare以及99个拒绝反例/三终态提交恢复190次RPC均通过。owner4355全静态/3原live skip日志和冻结输入已核验，未声称独立重跑。全部精确命令/退出/日志/产物/源码/driver差分及释放证明封于 `.dsh-dev/run/stage03-gc-qa-20261004-oawiwmg/`，3541项清单SHA-256 `d80c04d777f11bd2585fba161918c80392fe071b2110186e0ebedbcbebecf46b`。

owner34902项封存原字节、长度、链接和精确集合通过；窗口二三份日志的登记脱敏变换逐字节复算一致，五份已有协调输入和一份新增报告的封存后变化已分类，不掩盖代码漂移。2114项QA输入前后字节/metadata不变，最终composition相同；2026-10-04T00:15:40.644911+08:00明确释放，全部行为命令返回、相关宿主验证进程0，fake服务/child/worker清理完成。随后仅修改验收/派工和协调记录，保留生产代码/测试/构建/封存/分支HEAD及dirty基线，无真实模型调用。

第04份R01→R02→R03→R04→V01→A01→V02具备实施前置但仍planned。窗口一Python/唯一账本/共享协议/validator/A01，窗口二TS/Host/CLI/唯一build-stage，联合V01；按完整离线包交Gate-R/V，不逐helper停工。L01具体live授权与pending_validation义务保留。

协调登记后检查：仅九份已有协调文件和两份新增报告/指令变化，生产/测试/构建字节及其metadata未变；39处新增文档链接与锚点存在，49项原AT/依赖/责任路径和第03/04份AT原文未改，七项下一批及L01仍planned。`git diff --check` exit 0；3541项独立封存再次逐字节与精确集合核验通过。检查记录在 `/tmp/c2p-gate-c-gc-review-20261003-oawiwm_g/coordination-check.json` 与 `independent-seal-check.json`，不回写已封存证据。

## 2026-10-03 23:03：第03份 r2 独立 Gate-C 验收，三组集中返修

用户要求验收窗口一/二整包并给下一步完整指令。本轮未参与生产实现，依据原第03份、整批指令、interfaces/verification完成独立检查，裁决及完整两窗口指令见 [Gate-C报告](../docs/dsh_execution_20260928/stage03_gate_c_review_and_batch_repair_20261003.md)。Gate-C CHANGES_REQUESTED：GC-1 Unicode规则跨语言不同且真native terminal复现；GC-2旧revision/snapshot/fence材料被真worker prepare接受，之后ingest拒绝；GC-3合法已准备合同的projection/measurement/wire证据缺失损坏，新ingest仍发布pending_validation。

本轮独立105专项、265原owner、123 TS、48 B02、audit及技术页/作者页/34次RPC/4096→1024新投影联测通过。4234/3live skip为核验过的owner r2全静态日志，未声称独立重跑。Unicode12例中2分叉；真terminal扩展11项9pass/2fail；旧材料与引用缺失均用新worker及无旧receipt的QA私有副本证明。精确argv/cwd/退出/日志/探针差分/源码输入和释放见 `.dsh-dev/run/stage03-gate-c-qa-20261003-w04q7791/`，2997项封存清单SHA-256为a897af2244e240b426c7199aaa0752e0064988c721c985da6847ca8e009beb58。

2110输入前后字节及metadata不变，最终composition复核相同；owner r2 29279项、W2 135封存/72当前输入一致。23:03:47+08释放，所有行为命令返回、相关宿主验证进程0、假服务及句柄关闭。保留分支/HEAD/生产代码/测试/构建/owner封存；随后只写QA报告和协调文档/台账。当前11 done/6 in_progress/32 planned，H/K已验结论保留。纠正顶层协调“03未开始”与任务卡“已交付”的冲突。原第04份仍未启动，无真实模型/默认切换/提交。

## 2026-10-03：第03份整批派工指令（文档工作，未启动实现）

用户要求给出下一批依据和详细指令。本轮对照总设计§§8–10/14/15/21、原第03份、
interfaces、verification及18:03独立H/K裁决，形成
[完整指令](../docs/dsh_execution_20260928/stage03_batch_execution_instructions_20261003.md)。
保留原I01→C01→C00→C02→C03→C04依赖与六项AT；逐项列修改落点、正反例、两窗口交接、
真实worker最终演示、验证入口和统一submitted_for_independent_qa封存终点。
窗口一单写Python/protocol/validator，窗口二单写TS/peer/lib/build-stage。

读到interfaces顶部仍显示历史未放行，补当前裁决及0.2实际接口入口；旧记录保留历史范围。
纠正I01文档把现有B00 compatibility.json标“拟新增”的路径假设：保留原文件，后续本批
另记compatibility.stage03.json，仅作当前组成/证据索引，不替代现场校验或A01回执。
同步第03份与两级README导航。没有修改生产代码、测试、候选、既有验收报告或任务台账，
没有启动03实施、pytest、build/stage、模型调用或第04份。

本轮文档检查记录根：`/tmp/c2p-stage03-instructions-20261003-yyn09237/`。
新增23处相对文档链接全部存在；所列9个现有代码/回归入口存在，新增测试明确标待实施。
`git diff --check` exit 0；任务台账、18:03独立报告、B00 compatibility.json字节未变，
仍11 done / 38 planned，六项第03任务及其依赖保持。补充最终输入冻结顺序，避免把包含
自身的engine摘要回填仓库JSON或在测试中更新文档造成未申明身份漂移。

## 2026-10-03 18:03：四组返修独立验收，Gate-H / 正式 Gate-K PASS

用户提交 submitted_for_independent_qa 冻结包；本chat未参与该批生产实现，完成独立复验，
报告：[四组验收与阶段接续](../docs/dsh_execution_20260928/stage_four_group_repair_acceptance_20261003.md)，
数据：[核查JSON](../docs/dsh_execution_20260928/stage_four_group_repair_acceptance_20261003.json)。
原始根 `/tmp/c2p-gate-h-four-review-20261003-ciy9r4fd/`；原argv、内层退出、日志和前后输入齐全。

两侧原11文件93/0skip、来源各10/10、生命周期各3/3，B02原目录48、执行身份24、doctor与原audit正反例、
正常web/compat及env-only默认输出均通过。真实runtime只读视图下激活28条独立命令验证18次拒绝、
合法双向切换和提交失败回滚。四组关闭；201份owner封存匹配，108615项owner前后输入相同，
108990归档成员含52硬链接逐个核验。来源/runtime/types保持；本轮复核owner声明编译输入/封存并保留
前一独立tsc结论，未冒称重新tsc。原791份内核保持，未重跑4129。

109796主输入及3份补充driver前后一致，宿主1765进程扫描、相关验证PID0，18:03:42+08释放。
设置诊断（tar硬链接、临时CLI缺profile、diff短index、普通sandbox进程视图）均保留并纠正，
不是产品失败，未削弱原断言。测试未修改生产source/tests、peer、候选、owner证据，模型调用0。

释放后独立登记Gate-B/H PASS；LEAD据原K01–K04 component、无剩余缺陷、791保持及已满足H前置登记
正式Gate-K PASS，台账11 done / 38 planned。更新H02独立冻结及当前导航，历史owner sealed status不改。
第03份仅标实施前置满足，未写实现或启动03–08/live/默认切换；共享Python单写与后续原门保持。

释放后记录验证：`git diff --check` exit 0；22个新增报告/导航链接存在，JSON及新增文件空白检查通过。
原49项依赖和AT逐项未变，除本次完成的9项外其余40张任务对象未变，后续38项仍planned。
再次比较主读集，变化严格限于10份已登记协调文档，生产输入及owner封存无额外变化。
结果见原始根 `documentation-validation.json`，持久摘要并入本次核查JSON。

## 2026-10-03 16:05：冻结整包独立 Gate-H 审查与集中接续

用户提交窗口二冻结整包并提请验收。本 chat 未参与该批实现，直接完成原第 01 份独立复验；
报告：[冻结整包审查](../docs/dsh_execution_20260928/stage_whole_package_review_20261003.md)，
持久数据：[核查 JSON](../docs/dsh_execution_20260928/stage_whole_package_review_20261003.json)。
原始根 `/tmp/c2p-gate-h-whole-20261003-as7rfjgg/` 保存实际 argv、内层退出、原日志与反例。

两侧原 11 文件 93/0skip、原来源边界各 10/10、销毁重建各 3/3；交付 B02 26、身份回归 24、
doctor/audit 正例、正常 web/compat HTTP/退出均 exit 0。两包独立 tsc exit 0，三份声明与两候选同字节，
257/385 声明编译依赖（含编译器实现/配置）前后保持；source patch/源码构建 JS 和五文件 touched 对应。
owner 42 份封存核对通过；原内核 791 src/tests 未变，没有重跑 4129。93 个源节点逐一映射两侧日志，未匹配 0。

独立实际反例：未修改的 toolchain activate 在临时副本中把 compiler/lock 漂移重新封入回执，
verify 从拒绝变通过；错误 Node 目标导致失败前先改 peer。audit 的同一漏第五文件 manifest，
基树在时拒绝、缺基树时 PASS。两种正常 smoke 的 staging_tree_sha256 均 null（字段名读取错误）。
当前/历史文档、生产入口回归与完整冻结输入尚缺，集中列入报告四组；不把已过来源和生命周期重新列为失败。

Gate-H CHANGES_REQUESTED、正式 K 等待。工具链/证据仍归窗口二同一整包连续返修；
窗口一保持 component，03–08 不提前实施。审查中不改生产代码、原测试、候选、peer 或 owner 证据。
最终 1275 项 bytes/inode/mtime、四 runtime/manifest 及 peer 前后相同，宿主扫描 1766 进程、
相关验证 PID 0；2026-10-03 16:05:42+08 明确释放实际读集。释放后才写报告、索引及台账。

初始外层 sandbox 的 NETLINK_ROUTE 拒绝与 QA probe 未映射入 /tmp 的前置失败均保留，
修正运行环境后执行原断言，不算产品失败。实际命令入口与退出明细见报告 §5/核查数据；
没有模型调用、安装、原包重建、Git 提交或合并。

释放后的文档检查：`git diff --check` exit 0；新报告与六处导航的 10 个链接均存在，
报告/台账 JSON 解析及新增文件空白检查通过。任务板原 49 张卡的内容和依赖逐项保持，
仍为 2 done / 9 in_progress / 38 planned；仅更新有独立证据的缺陷处置、最新检查点和接续范围。
检查结果保存于上述原始根的 `documentation-validation.json`。

## 2026-10-03：全部剩余工作核查与整阶段修改指导

用户要求一次给出全部未解决问题和详细修改指导，避免逐点续派。本轮核对原 8 份文档、49 张任务卡、
第九轮交付证据和相关实际代码，形成
[集中指导](../docs/dsh_execution_20260928/remaining_work_and_batch_repair_guidance_20261003.md)及
[持久核查数据](../docs/dsh_execution_20260928/remaining_work_audit_20261003.json)。
仅新增指导/核查数据并补仓库入口、第 01 份与执行入口导航；保留所有既有 dirty 内容和任务状态。
这不是完整 Gate-H 独立验收，也不代替窗口二继续实现。

确定差异：补丁实际变化五文件而 touched 只登记四个；跨候选 receipt/stage 拼接、活动 peer 属于 -built；
正常 smoke 未消费候选环境且写旧 evidence 根；当前 API/身份文档与日志引用未同步；封存 doctor 的 staging
不同于最终 staging。C25/C26 的部分场景与报告完整声明存在覆盖差距，按验证缺口登记，不冒称新实现已有
实测漏洞。保留原类型/补丁正证据及 K01–K04 component；GHS-4 的 -built 仍仅声明源码等价范围。
第 03–08 份 38 项 planned 全部映射到修改位置、依赖、行为判据和阶段终点；不提前改其代码或放行。

本轮新增诊断：从 pristine 的原四文件复制到 fresh 根后执行
`python integrations/dsh/dev/runtime-0.2.0-rc.1/loop-origin/loop-origin.patch.py /tmp/c2p-consolidated-guidance-20261003-jh05854k/patch-rebuild`
退出 0，生成五文件均与 delivery 同字节。smoke 在 read_manifest 前截获候选选择，未启动进程/HTTP，
确认合法候选环境仍落默认根。准确 argv、退出和结果保存在该 fresh 根，探针结果同时嵌入持久核查 JSON。
前一进度核查的独立 tsc、doctor 与 owner 日志封存核对结果明确标作已有观察，没有冒称本轮重跑完整套件。

文档及输入保持验证命令：
`python /tmp/c2p-consolidated-guidance-20261003-jh05854k/validate_guidance.py`；
覆盖 49 项状态/依赖与指导对应、本次新增链接、新文件空白、`git diff --check`、743 个读取实现输入、
两候选 runtime/stage/receipt 和活动 peer 的前后保持；准确结果见同根 `guidance-validation.json` 及持久核查数据。
该命令退出 0：49 项无映射差异、19 个本次相关链接有效、新文件空白及 `git diff --check` 通过；
743 项读取实现输入无变化，两候选 runtime/stage/receipt 与活动 peer 保持原值。
本轮没有运行模型/live、重建原 runtime、改 peer、重封 owner 证据、提交或合并，也没有新增阶段 PASS。

## 2026-10-02 22:10：模块级派发候选独立 Gate-H 审查登记与原第 01 份整包续派（LEAD）

独立 reviewer 的[集中审查](../docs/dsh_execution_20260928/stage_static_entry_gate_h_review_20261002.md)覆盖交付
`392e4acf…` 与源码构建 `301a5e23…` 两侧：原套件各 89/0skip，原三类反例、Web/compat HTTP、交付 B02 24/doctor
成立；GHS-1 公开 `streamWithRegistration(..., true)` 受信派发与 GHS-2 注册表生命周期两侧真实失败，GHS-3
types 来源/全文身份、GHS-4 源码构建侧 B02 未闭合。Gate-H CHANGES_REQUESTED，正式 Gate-K 等待；
读集 22:10:34+08 释放，相关验证进程 0。

LEAD 未运行产品测试或验收，只登记 [README §3.15](../docs/dsh_execution_20260928/README.md)、
[verification §18](../docs/dsh_execution_20260928/verification.md)、`docs/README.md` 索引与
`task_board.json`：新 checkpoint（全部摘要逐项对照审查报告原文），旧 checkpoint/QA 完成记录/读集释放
追加入历史，新增 GHS-1–4 open issue，PC-1/PC-2/CAP-1/CAP-3 记为已观察关闭，CAP-2 余项并入 GHS-3；
任务状态仍为 2 done/9 in_progress/38 planned。派工：窗口二续原第 01 份整包，窗口一保持 component，
第 03 份等实际 Gate-H 与正式 Gate-K。LEAD 受理时只读看到 owner 的 `w2-lo-repair3` 无 `.exit`/argv
记录，源码构建与构建日志只在 `/tmp`；已列为下一交付包要求。

## 2026-10-02（下午）：窗口二能力门控候选三项返修闭环（CAP-1/PC-2/CAP-2 + 残留验证收尾，写权释放）

按[能力门控候选独立差分复核](docs/dsh_execution_20260928/stage_capability_entry_review_20261002.md)§4 连续完成：

- **残留验证收尾（CAP-3）**：终止归属本窗口的 `-built` 原 11 文件套件残留进程
  （PIDs 2202351/2202381/2202383/2202448，13:06 启动，C0 失败后挂起——根因是该次源码
  构建缺 `preparedDispatchRecords.set` 注册，已在源码修复）；部分日志与说明封存至
  `w2-loop-origin-private-20261001-182722/abandoned-verification-20261002/`。
- **CAP-1（转发 Proxy 截获 capability）**：capability 不再经由任何可拦截调用路径。
  loop 派发点改用静态模块导入的 `runLoopDispatch(options, preparedCall, capability)`
  （dsh-llm 模块级函数；静态 ESM 导入不经 cordis resolver/getter，转发 Proxy 无法
  插入）；入口第一动作做对象同一性校验，失败即隔离。真实实例经模块私有注册表
  （构造时注册）与 prepared record 的 `runtime: this` 解析，不经代理。symbol-keyed
  实例方法删除。回归 **C22**：internal/get listener 返回仅转发 Proxy、每个方法调用
  尝试 `admitLoopDispatchOrigin(args[2])`——proxyAdmissions=0，合法 child completed
  且 R/D/S 恰一次。
- **PC-2（源码/补丁/-built 构造期隔离）**：源码工作树的隔离构造与交付 hunk 对齐
  （waterfall 创建与 `Symbol.asyncIterator` 获取都在清空作用域内）。回归 **C23**：
  listener 提供的自定义 `Symbol.asyncIterator` 工厂在清空作用域内执行
  （seesOrigin=false），探针派发到达自身 provider，合法 child 各 1。
- **CAP-2（身份统一）**：兼容清单/`_020`/interface-diff/evidence 全部更新为当前
  实际身份（树 `392e4acf…`、补丁脚本 `eac2d8c5…`、源码补丁 `30133c39…`、receipt
  `352551db…`、staging `904f6ecf…`、outputs `2aeceb7b…`、源码构建候选树 `301a5e23…`）；
  manifest `touched` 列齐 4 文件；历史表述绑定旧树并注明。
- **双侧验证**：交付候选 check:compat **89/89**（0 skip，含 C22/C23 新回归）、B02
  **24 passed**、doctor exit0、`git diff --check` 干净；源码工作树 `pnpm install`/
  两包 `tsc -b`/`build:lib:host` exit0（一次 OOM 崩溃与一次 typert 显式注解失败均已
  修复并重跑成功）；源码构建产物换入 `-built` 候选（树 `301a5e23…`）后 89/89。
  日志 `run/w2-lo-repair3/`。

未动：原 0.2 树、旧 0.1.5、日常 0.1.7、Python 内核/validator、LEAD 台账、QA 权威根
（`qa-capability-entry-20261002-hum96d19/` 未触碰）。未跑 live；Gate-H 未自行登记
PASS，冻结候选待独立差分验收。写权释放：窗口一保持第02份；第03/04份等 Gate-H 与
正式 Gate-K。



## 2026-10-02 14:48：能力门控候选独立差分，原阶段继续返修

当前执行入口 [README §3.14](../docs/dsh_execution_20260928/README.md)；
[完整裁决](../docs/dsh_execution_20260928/stage_capability_entry_review_20261002.md)。
交付实际树 0adaffc8、源码构建 dcf69658、patch f1a310cd/23ab6350、receipt a6c69d83、stage 66458c03。
原交付 11 文件套件独立 87/0skip、显式 B02 24、只读 doctor/diff-check exit0；新边界探针
交付 4/5、源码构建 3/5，实际 Node exit1。普通伪造 capability 观察者与四文件 touched 已修；
公开 resolver 转发 Proxy 截获 symbol 调用实际能力并 admission 成功，两侧合法 child error/
零 RDS/adapter；源码侧 iterator 获取仍见来源，owner 当前身份/API 声明有旧值。
Gate-H CHANGES_REQUESTED、正式 K 等待；原 49 任务对象/AT/依赖不变，不启动03–08或live。

本批权威根 `.dsh-dev/run/qa-capability-entry-20261002-hum96d19/`；1054 输入/四 runtime/peer
未变，14:48:55+08 仅释放自己的读集，己方进程 0/命令全返回。另有此前 owner 源码构建
原套件进程仍活跃（输出 /tmp/lo-built2-compat.log）；初次全局 closing 失败及归属证据保留，
未终止他人进程、未登记全局清空/候选立即可写。窗口二先保存/收尾该运行、释放候选/peer，
再按同一完整第01份连续修能力封闭路径、双侧源码隔离/构建、原AT/同child恢复与身份冻结。
窗口一保持791源/测试未变的component。QA下一完整包按需再验，无产品/内核/peer/buildstage改动。
本条及导航/台账在本轮读集释放后更新，下方 owner 声明及更早记录完整保留。

# Codex 工作记录

## 2026-10-02（午）：窗口二三项返修闭环（能力门控内部派发，写权释放）

按独立验收三问题连续完成：

- **问题1（entry-ack 被同步 internal/get hook 预消费）**：entry-ack 子作用域方案删除。
  新设计为能力门控内部派发入口：来源作用域对象本身即能力（loop 私有 establish 创建，
  建立即权威，无独立可消费状态），仅在 loop 自己的调用帧里作为实参传给
  `LlmRuntime[loopDispatchEntry](options, preparedCall, capability)`（unique symbol
  门控）；入口第一件事做对象同一性校验（转调 agent-loop 的
  `admitLoopDispatchOrigin(capability)`，校验失败即走公开隔离路径）。entry 链上的
  hook（internal/get、async hook）看不到实参，无法伪造/偷取/抢先。C21 更新为用
  剩余公开面（peek + 伪造 capability 的 symbol entry + 受保护会话公开派发）实测：
  admission 恒拒、观察者派发具名拒绝、合法 child completed 且 R/D/S/adapter 各 1。
- **问题2（构造期隔离不完整）**：隔离构造包住 `Symbol.asyncIterator()` 的调用
  （waterfall 创建与迭代器获取都在空 store 内），隔离对象的
  `isolated[Symbol.asyncIterator]` 亦经清空式 runner 返回。
- **问题3（manifest touched）**：`scripts/dsh_dev.py` 的 loop_origin_patch 生成器与
  候选 manifest 按实际差分列齐 4 文件（2 JS + 2 types）。
- **双侧验证**：交付候选 check:compat 87/87（0 skip）、B02 24 passed、doctor exit0；
  源码工作树（commit `4878cdabd8…`）同步 v5（capability establish + symbol entry +
  WeakMap prepared record + trusted 参数），`pnpm install`/两包 `tsc -b`/
  `build:lib:host` exit0；源码构建产物换入 `-built` 候选（树 `dcf69658…`）后
  check:compat 87/87。源码差分 `loop-origin-source.patch`（`23ab6350…`）。
- **统一身份**：树 `a010ccdc…`、补丁脚本 `f1a310cd…`、receipt `a6c69d83…`、
  staging `66458c03…`、outputs `2aeceb7b…`。日志 `run/w2-lo-repair2/`。`_020` 第七轮
  合同节、interface-diff、evidence、兼容清单同步。证据封存根
  `w2-loop-origin-private-20261001-182722/` 维持。

未动：原 0.2 树、旧 0.1.5、日常 0.1.7、Python 内核/validator、LEAD 台账、QA 权威根。
未跑 live；Gate-H 未自行登记 PASS，冻结候选待独立差分验收。写权释放：窗口一保持
第02份；第03/04份等 Gate-H 与正式 Gate-K。


## 2026-10-02 12:12：私有消费候选独立差分复核、集中返修与明确释放

本次未参与该候选实现；只新增独立 QA 夹具/原始证据，释放实际读集后更新裁决文档/入口/台账。
产品、原测试、runtime、peer、build/stage、Python 内核与 validator 未改。
完整结论和一次接续指令：[私有消费独立复核](../docs/dsh_execution_20260928/stage_private_consumption_review_20261002.md)。

- 实际交付树 a010ccdc/source-built7ae6af55、source12f33263、patch e2a8cd2a/419d5a8d、
  receipt85a37546/stage950ba6d4/outputs2aeceb7b 均与交付清单匹配；两份 source-built JS
  对应固定源码构建输出同字节，14 封存 hash 全匹配。
- 原 11 文件 staging-only 套件独立 **87/87、0 skip、exit0**，C21 与同 child committed 恢复
  通过。显式候选环境 `python -m pytest -q integrations/dsh/dev/tests` **24 passed、exit0**；
  `python scripts/dsh_dev.py --candidate 0.2.0-rc.1+loop-origin.1 doctor` exit0，无 evidence 写入。
- 两棵候选各独立 4 项，prepared/fallback 两合法正例通过；公开 Cordis `internal/get` 在
  回落同步服务解析时成功 take entry-ack 一次，合法 child error、R/D/S/adapter 全 0；公开
  custom iterable 的 `Symbol.asyncIterator()` 获取看到外层来源。各 **2 pass / 2 fail、真实
  Node exit1**，未用 import error 或全拒绝正例充数。
- 实际 inventory 4 文件差分，compatibility touched 列齐；实际 manifest 与
  `loop_origin_setup` 生成器仍仅 2 JS，漏 2 types。将这三项集中作为 PC-1/2/3 返修，
  Gate-H CHANGES_REQUESTED、正式 K 未过；49 个原任务对象全部保持。
- 系统沙箱首轮阻止 bwrap socket，原 bootstrap 输出保留，后续自动审查允许在外层系统
  沙箱外继续原只读/断网 bwrap。B02 首轮 runner 漏传候选而落历史默认，原失败保留并纠正；
  两者不计产品缺陷。逐 argv/cwd/选择环境、inner exit、完整日志在本次候选外稳定根。
- 新权威根 `.dsh-dev/run/qa-private-consume-20261002-7o8lt6bj/`；992 输入 byte/metadata、
  四 runtime inventory 与 peer 前后同；791 已验 source/test 摘要未变，不重跑 4129。
  宿主扫描 1780，相关验证 0/不可读 0、全部启动命令返回；**12:12:01+08 明确释放**，
  before/after/closing 原文保存。后续文档与台账编辑发生在释放后。

窗口二接回原第01份完整写权，连续修三个问题、原 AT/联合恢复、源码双侧/稳定验证/封存与
重新冻结，完整包再独立 QA。窗口一保管 component；第03/04份原分工与实际 H/正式 K、C/R/V
及单独 live 门不变。未跑 live、未自行开下一阶段或登记 PASS。

## 2026-10-02（凌晨）：窗口二私有消费返修完成（公开预消费反例闭环，写权释放）

按[返修差分裁决](docs/dsh_execution_20260928/stage_loop_origin_repair_acceptance_20261002.md)§4 连续完成：

- **证据封存**：存活证据封存至 `.dsh-dev/run/w2-loop-origin-private-20261001-182722/`
  （14 文件 + hash 清单 + EVIDENCE_SEAL.md）；首轮 `w2-lo-final/` 与
  `qa-loop-origin-awkji3_e/` 因历史候选重建灭失，如实登记不补造。本轮候选重建
  先移出 run/ 再原样移回，不删证据。QA 权威根 `qa-loop-origin-repair-0yrz6nyl/` 未触碰。
- **私有消费兑现（LO-4-PRECONSUME 闭环）**：删除公开 `admitLoopDispatchOrigin`
  （QA 实测 async hook 在 ALS.run 建 Promise 时同步执行、抢先消费阻断合法 child）。
  一次性状态只在 agent-loop 模块私有域：来源作用域由私有 establish 建立（建立即权威）；
  loop 自己的同步 stream entry 经私有 `enterLoopDispatchOrigin` 子作用域标记；
  dsh-llm 仅读判定（peek + `takeLoopDispatchEntry`），对来源零变更。entry 调用链
  从子作用域进入到判定全程同步、无 Promise 创建，任何 hook/listener 无法先于 loop
  取走 ack。公共快照不含 request 对象（同一引用不能抢占）。
- **公开入口隔离**：存活作用域内的公开派发（async hook、listener、预持 handle、
  部署面）被清空式隔离——waterfall 创建与全部迭代都在空 store 内；普通公开流量
  sibling 直通；公共 NO_ADAPTER 原语义与内部回落单次合法保持。
- **回归**：新增 C21（公开 async-hook 观察者只用剩余公开面：peek + take + 受保护
  会话公开派发——实测 takeSucceeded=0、观察者派发具名 `dispatch_origin_unproven`、
  合法 child completed 且 R/D/S/adapter 各 1）；C13 期望更新为宿主具名拒绝
  （`dispatch_origin_unproven`，零 reserve/adapter——runtime 已无公共消费可被重入）。
- **双侧构建**：源码工作树（commit `4878cdabd8…`）同步 v4 设计；`pnpm install`、
  两包 `tsc -b`、`pnpm run build:lib:host` exit0；源码构建产物换入 `-built` 候选
  （树 `7ae6af55…`）后 check:compat 87/87（含 C21）。源码差分
  `loop-origin-source.patch`（`419d5a8d…`）。
- **验证（fresh）**：交付候选 check:compat **87/87**（0 skip，11 文件，含
  `sandbox.test.ts` 2 项与 `staging.test.ts` 4 项——修正上批清单）、B02 **24 passed**、
  doctor exit0、`git diff --check` 干净。日志 `run/w2-lo-repair/`。
- **统一身份**：树 `a010ccdc…`、补丁脚本 `e2a8cd2a…`、receipt `85a37546…`、
  staging `950ba6d4…`、outputs `2aeceb7b…`；manifest `touched` 按实际差分列齐 4 文件。
  `_020` 身份表与第六轮合同节、interface-diff、evidence、兼容清单同步。

未动：原 0.2 树、旧 0.1.5、日常 0.1.7、Python 内核/validator、LEAD 台账、QA 权威根。
未跑 live；Gate-H 未自行登记 PASS，冻结候选待独立差分验收。写权释放：窗口一保持
第02份；第03/04份等 Gate-H 与正式 Gate-K。


## 2026-10-02 00:02：LEAD返修差分、公开预消费阻断、完整续派与明确释放

owner86/0skip、B02dev24与doctor日志/身份已核对；独立LO1普通三入口、LO2公共NO_ADAPTER/native回落和LO3旧manifest读取通过，source固定commit/四文件及实际构建JS交付。LO4公共admit仍改一次性状态：公开async_hooks观察者拿admitted、合法child error/零RDSadapter；交付及source-built均实际exit1，各有合法completed/四项1正对照。GateH仍CHANGES_REQUESTED、正式K未过；不将改名oracle作为私有消费完成。

只写独立QA夹具/证据与LEAD裁决文档/台账，没有产品/原测试/runtime/peer/buildstage/Pythonvalidator改动。791Python源码/测试及九份原运行文件未变，不重跑4129。1023输入metadata/四runtime/peer前后同，宿主1754相关0/不可读0、全部命令返回；00:02:16+08明确释放实际读集，canonical根`.dsh-dev/run/qa-loop-origin-repair-0yrz6nyl/`。
上批候选内QA/owner根当前不存在，移除原因/时间未核实；原历史保留、不伪补，窗口二先将当前证据封到候选外。原01/§6完整写权恢复，连续私有native消费与公开入口隔离、真实反例/原AT/联合恢复、sourcebuild/finalcheck/冻结交付；窗口一只保管component，无早开C/R。两门满足后原03整阶段，再GateC后原04，正式R/V与单独live不减少。

完整环境/即时派工/后续分工：[本批裁决](../docs/dsh_execution_20260928/stage_loop_origin_repair_acceptance_20261002.md)。原8份执行文档49tasks全对象不变，本轮更新顶层checkpoint/issue disposition/closing/history；QA结束，无常驻reviewer。

## 2026-10-01（晚）：窗口二 loop-origin.1 验收返修完成（LO-1/2/3/4 闭环，写权释放）

按[验收返修指令](docs/dsh_execution_20260928/stage_loop_origin_acceptance_20261001.md)连续完成四项：

- **LO-1**：admission 改四值 oracle（`absent/admitted/refused/external`）；存活作用域内发起的
  公开派发（三入口 + 部署面）经清空式隔离返回，隔离以逐 `next()/return()/throw()` 再入空 store
  实现（首版只在创建 iterator 时包作用域，listener body 在迭代期仍见外层 origin——探针实测后纠正）。
  新增 C19：listener 内三入口向另一 provider 各成功一次，合法 child R/D/S 恰一次并 completed。
- **LO-2**：公开 `prepareCall` 恢复原 NO_ADAPTER 拒绝（移除回落 handle hunk）；loop 内部回落经
  公开 `llm.stream` 在 origin run 内 admitted 恰一次。新增 C20（(a) 具名拒绝无 handle；(b) 回落
  R/D/S=1 completed）。
- **LO-3**：`read_manifest` patched 字段检查仅在候选 id 带 `+` 时生效；B02 新增
  `test_unpatched_manifests_keep_the_original_format`（0.1.5-rc.3 与 0.2.0-rc.1 旧格式实测加载）；
  漂移/缺新身份/不一致拒绝保留。
- **LO-4**：新导出以 runtime 自身 `.d.ts` 声明（补丁域扩为 4 文件），Host 移除 unknown 断言；
  公共 `consumeLoopDispatchOrigin` 移除 → 单次 admission oracle + 清空式隔离 runner；
  源码交付：monorepo `deepseek-ai/deepseek-harness` tag `dsh-v0.2.0-rc.1`
  （commit `4878cdabd87d4041bdaff61d04c966883b9fd07a`，克隆 `.dsh-dev/sources/loop-origin-020/`），
  窄改 4 源文件，源码差分 `loop-origin-source.patch`（`80ffbdd8…`）；`pnpm install`、两包
  `tsc -b`、`pnpm run build:lib:host` 全部 exit0；源码构建产物换入验证候选
  `0.2.0-rc.1+loop-origin.1-built`（树 `eb4625a6…`，manifest 记 provenance）后
  check:compat 86/86 —— 行为等价。evidence 修正：11 文件 86 项全列，日志权威
  `run/w2-lo-rework/`。

验证（返修轮 fresh）：交付候选 check:compat **86/86**（0 skip）、B02 **24 passed**、doctor exit0；
日志 `run/w2-lo-rework/`。统一身份：树 `5f340b3a…`、补丁脚本 `9c98b720…`、receipt `bec54f92…`、
staging `3981269e…`、outputs `8be3cd0a…`。identity/docs 同步：`_020` 身份表与第五轮合同节、
`interface-diff.md`、`evidence.md`、`compatibility.0.2.0-rc.1+loop-origin.1.json`。

未动：原 0.2 树、旧 0.1.5、日常 0.1.7、Python 内核/validator、LEAD 台账、QA 证据根。未跑 live；
Gate-H 未自行登记 PASS，候选待独立差分验收。写权释放：窗口一保持第02份已验内核；第03/04份
仍等 Gate-H 放行。

## 2026-10-01 19:40：LEAD独立loop-origin.1验收、集中返修与明确释放

候选已实际落地，peer指向0.2.0-rc.1+loop-origin.1，runtime1e0e6fa2；基树434与旧默认7e8未改。
owner84/0skip、B02dev23、doctor0日志已核对；原H-R4独立32次publicprepare均拒绝，合法child
completed，R/D/S/adapter各一次。没有重处理此前后台完成通知。
独立原11文件83pass/一个QA RUN_ROOT断言fail exit1；按原launcher环境只复验sandbox2pass exit0。
驱动路径/沙箱/closing语法失败记录保留并纠正，未误归产品或覆写真实exit。
新增LO1普通public流及两类prepared继承ambient来源误拒，LO2公共NO_ADAPTER被改为返回handle，
LO3旧manifest遭新必需字段拒绝；LO4固定源码/原生构建/types及公共consume不满足既有§6合同。
GateH仍CHANGES_REQUESTED，正式GateK未过；下方owner交付是实现者结果，其“其他窗口可开始
第03份只读之外工作”不是LEAD授权。791Python源/测试及六份原日志未变，component保留。

只写独立QA夹具/证据与LEAD裁决文档/台账；未改产品/原测试/peer/buildstage/runtime/validator。
宿主1750进程中相关验证0、不可读0，全部启动命令返回；912受测输入、三棵runtime和peer
before/after同身份。19:40:04+08明确释放实际读集；窗口二直接接回原第01份+§6窄源码写权，
连续修LO1–4、原正反例/联合恢复，最终稳定checkcompat/B02/doctor/身份与写权释放，再独立QA。
窗口一保管已验内核，无新返修/重复调查/全量/提前C/R。第03/04仍等实际H/K，无live/默认切换。

完整裁决：[loop-origin.1验收](../docs/dsh_execution_20260928/stage_loop_origin_acceptance_20261001.md)。
证据与精确closing：`.dsh-dev/candidates/0.2.0-rc.1+loop-origin.1/run/qa-loop-origin-awkji3_e/`。
原8文档/49任务、AT/依赖/形式状态全部不改，原日志/报告和release历史保留。


## 2026-10-01：窗口二 loop-origin.1 完整阶段交付（写权释放）

按[接口裁决 §6](docs/dsh_execution_20260928/h04_loop_origin_escalation_20261001.md)与执行入口 §3.10
连续完成第01份 loop-origin.1 阶段。候选 `.dsh-dev/candidates/0.2.0-rc.1+loop-origin.1/`：
base `43490765…`（pristine 0.2.0-rc.1，未动）→ patched `1e0e6fa2…`；manifest 分离
`dsh_version=0.2.0-rc.1+loop-origin.1` / `upstream_dsh_version=0.2.0-rc.1` / `source_kind=local-patched`，
runtime package 版本保持上游不改。补丁域仅 `dsh-agent-loop`+`dsh-llm` 两文件逐字节 hunk
（脚本 `26d1d835…`，可重建 via `loop-origin-setup`）。

实现要点（实测）：cordis waterfall 的 listener wrapper 是惰性 async generator，body 在迭代时
执行，仅在"创建 iterator"外套 ALS.run 会在任何 listener/adapter 前关闭作用域（middleware 实测
origin=undefined）——因此 origin run 作用域扩展到整个 step 流消费，admission 同步先于 listener；
公开 prepared/回落 handle 均从该入口进入（prepareCall 不再抛 NO_ADAPTER，返回冻结回落 handle）。
作用域内存活重入由 runtime 以 `DISPATCH_ORIGIN_CONSUMED` 具名拒绝；作用域外/部署面冒名由 Host
拒绝（新增 root 面只读 guard：cordis 只运行组合 ctx 自身 hooks，受保护 agent listener 看不到
部署面派发——S2 的 impersonation/foreign-route 由 guard 具名拒绝）。核验经同一模块实例的
`currentLoopDispatchOrigin`（staging 与 runtime realpath 实测一致），runtime-checked 属性读，
未补丁 runtime 按名拒绝。

验证（全部本轮 fresh 实测，日志在候选 `run/w2-lo-final/`）：
- `npm --prefix integrations/dsh run check:compat` exit0，**84/84 pass，0 skip**
  （原 13 项 skip 全部恢复为真实执行；原被改成合法也拒的 S2/C9 等正例恢复）。
- `python -m pytest -q integrations/dsh/dev/tests` exit0，**23 passed**（B02 目录）。
- `python scripts/dsh_dev.py --candidate '0.2.0-rc.1+loop-origin.1' doctor --evidence` exit0。
- build receipt `b01543a9…`，staging tree `241639f9…`，outputs `68260b9d…`。

身份与证据：`integrations/dsh/dev/runtime-0.2.0-rc.1/loop-origin/{interface-diff.md,evidence.md}`、
`integrations/dsh/compatibility.0.2.0-rc.1+loop-origin.1.json`、
`docs/dsh_execution_20260928/h02_interface_freeze_020.md`（顶部身份表已改为 loop-origin.1 实测，
base 值保留对照）。测试修订：cancellation（C13/C14 改为捕获 runtime 具名 throw、C14b 以
post-legal 为基线）、joint-child（候选 id 断言、移除与 before() 重复的第二次 wait-window 攻击——
terminal 工具 concludeTurn 后不存在第二个 prepareCall 窗口）、request-seam（S2 部署面拒绝诊断
接受 guard 具名文本、外路由接受 guard 先拒）、B02 隔离测试（分离 manifest 合同：upstream 版本
+ upstream_dsh_version）、staging.test.ts（runtime 版本以 upstream_dsh_version 为字节权威）。

未动：原 0.2 候选树、旧 0.1.5、日常 0.1.7、Python 内核/validator、旧报告与失败日志。
未跑 live API，未登记 Gate-H PASS；候选待独立 QA。窗口二本轮写入范围见
`loop-origin/evidence.md` §5，写权释放：其他窗口可开始第03份只读准备之外的工作。

## 2026-10-01：R2候选独立验收与立即接续

LEAD只读验收，未写产品。独立83pass/B02整目录23pass/受影响identity29pass；内核原Python
输入/测试/完整日志身份不变，保留component PASS，不重跑4129。旧公开listener同对象/复制/延迟
变体拒绝，合法child各一次；公开prepareCall和排入微任务仍各能先领能力，裸RDS/adapter1，
合法child error。Gate-H仍CHANGES_REQUESTED，Gate-K及正式done不通过。

原QA会话两次自动内容检查中断后由未参与实现LEAD接手，83已返回不重复启动。原隔离
bwrap权限失败保存，获原隔离执行权限后真实负向probe各exit1；无裸跑/live。宿主明确
检查0匹配/0不可读，903输入/27owner日志/2678独立输入/runtime26149项全同，2026-10-01T00:54:43.353019+08:00
明确释放全部读集。证据.dsh-dev/run/qa-r2-acceptance-20261001-d4gkwv4k/；本批完整裁决docs/dsh_execution_20260928/stage_r2_acceptance_20261001.md。

窗口二继续原第01份整阶段，优先闭合两个首次认领来源，缺公开能力时交最小接口证据；
窗口一保持候选，只读准备第03份。第03份及第04份完整派工排队，实际Gate-H/K/C前置满足
才生效，不新增任务、驻QA或平行领域owner。保留dirty分支及所有旧报告、失败日志。


## 2026-09-30：返修候选差分验收与21:36后接续裁决

- LEAD仅协调、独立只读内核验证和文档台账；没有修改产品源码/测试、锁、peer、build/stage
  或日常环境。分支/HEAD仍codex/agentic-p4-benchmark-cutover / d48b4e4b，未提交树保留。
- DSH独立原test:compat74/74、B02原dev整个目录23/23，均exit0；私有同字节profile普通
  Web/compat真实HTTP与各四资源200、模型0、进程返回/端口关闭。未QA重build/stage。
- 原F1具名/F3/F4同步/F5与准备等待旧F2修复成立；H04公共同request引用及真正
  NO_ADAPTER回落同signal复制/不同messages仍各可裸RDS/adapter一次并使原child失败。
  第01份仍CHANGES_REQUESTED，完整原AT缺项由原Window2连续整包返修。
- LEAD原六内核模块103 passed、K04/身份/真实调用方282 passed，均exit0；原replay/
  manifest独立脚本exit0；实际Writer在有效矛盾回执下以unknown相位原因零发送、doctor
  同首因，损坏request具名拒绝/accepted=false/保留预留。全量4129/3原live skips/12subtests
  完整owner日志/argv/.exit已核对，不重复全量。K01–K04 component PASS、正式Gate-K等待H。
- 追加QA driver的前置/字段/receipt诊断语义假设与一项未启动产品的命令失败全保留；
  原非零exit没有改成0或裁为产品缺陷。actual_consumer_review、correction记录和最终
  corrupt continuation exit0与late-conflict已通过行为分别收口，不以失败整命令宣告成功。
- 新裁决[stage_repair_acceptance_20260930.md](../docs/dsh_execution_20260928/stage_repair_acceptance_20260930.md)；
  独立报告原文SHA98d05925…，历史原报告与第一次失败不覆盖。
  仓库证据镜像.dsh-dev/run/qa-stage-repair-review-20260930-y7m330na/，manifest410文件。
- 901输入/35owner记录及DSH2618输入/runtime26149项前后全同；DSH明确21:30:09释放，
  LEAD21:36:51释放。宿主精确QA/CLI匹配0、不可读0、所有命令返回，无pending；共享profile
  本批未写。日常安装前hash仍N/A，不倒填历史。
- 49任务原status/依赖/AT/责任域保留；记录component/原具名反例关闭与两条新来源发现，
  不自登正式Gate-H/K/done。当前窗口一保持已验候选、窗口二继续原完整阶段，QA结束按需
  再启。第03/04份、RPC、live、默认/日常切换、commit/merge/push未放行。

## 2026-09-30：完整 Python / DSH 0.2 候选独立验收与 LEAD 集中裁决

- 范围：LEAD 保持协调/裁决角色，没有修改产品源码、测试、配置、peer、锁、build 或 stage。
  两位新实施者已交完整原阶段包并释放写权，按现有执行文档启动一次独立验收；不建新计划、
  不配置常驻 QA，不开启第03/04份、live、日常更新或默认切换。
- 分支/HEAD仍为 `codex/agentic-p4-benchmark-cutover` /
  `d48b4e4b22c94c82b45d2179ba452d72b164102d`，保留 dirty 树与旧运行目录。
- DSH 由独立 QA 对冻结候选复跑原隔离 `test:compat`，11文件71 pass/0 fail/0 skip，
  exit0；不重复 build/stage。完整 owner `check:compat` / doctor 日志与真实源/产物回执
  已核对，runtime实算仍 `43490765…`，旧默认仍 `7e8f199b…`，peer未变。
- LEAD独立 `python -m pytest -q -rs -p no:cacheprovider --basetemp <新鲜QA根>` 对原六个
  内核模块99 passed，exit0，19.08s。owner完整全量 argv/log/.exit=0已核对：
  4125 pass、3既有live skips、12 subtests。没有重复运行全量，也没有启动live。
- 额外原owner反例真实失败：同validator验收重放将矛盾发送事实变成accepted_reusable，
  含合法重放先落盘的对照；reader验证后重读被替换manifest，返回g2成员却标g1权威摘要。
  三个反例的真实断言退出码均为1。追加探针初轮缺PYTHONPATH是QA夹具失败，保留后续v2。
- DSH额外反例：H03损坏日志仍committed/null event直接抛异常；H04公开withInitiator
  准备期抢票、全局requestDepth误拒合法B、同步iterator.return异常遗漏具名终态；
  B02 CLI cwd仍旧workspace，普通Web未就绪、原Python矩阵20pass/2夹具适配失败。
  探针exit0仅表示实际观察完成，不把反例失败写成合同通过。
- 完整裁决与集中连续返修：[stage_acceptance_20260930.md](../docs/dsh_execution_20260928/stage_acceptance_20260930.md)。
  独立报告原文副本SHA `804a83aac5a1ded1d3b192a1e0629312efcf92a240b437a8c2ec81719377b29c`。
  两包CHANGES_REQUESTED，Gate-H/K未过；K01–K04与B02/H01–H04仍in_progress，不以计数自登done。
- before/after与原始日志保存在仓库可见
  `.dsh-dev/run/qa-stage-review-20260930-izdz_5y3/`；899输入/30owner日志字节相同。
  DSH2618输入字节/inode相同，仅两个目标profile cordis.yml被真实CLI烟测改了mtime。
  该副作用单列，未还原掩盖，不宣称完整metadata冻结一致。
- QA 19:01:54+08明确结束并释放完整读集；宿主closing精确QA/目标CLI匹配0、不可读0，
  全部QA子进程已wait返回，无待写输出。LEAD内核命令亦已全部返回。窗口一、二直接
  接回各自原完整阶段集中返修，不逐缺陷派工；新完整冻结候选再按需独立差分验收。
- LEAD仅更新执行入口、第01/02份、verification、台账、仓库文档索引与本记录，保存两份
  新验收报告；49任务的ID/status/依赖/AT/责任域保持不变。链接和差分收尾检查另存QA根。

## 2026-09-16：P0–P6 产品集成闭环（未 V4 默认 cutover，未 P7 live）

- 依据：独立验收对 2026-09-16 执行文档实现的阻断项。本片修正常入口集成，
  不把 V4 设为默认，不启动 P7。
- 阻断 1：`method_propositions_v2` 进入 `build_product_planning` 返回字典，
  `persist_product_artifacts` 从 planning 读取并落盘。briefs 主线同时写出
  `intent_evidence_atoms_v1`。`test_compile_concept_cards_is_noop_without_live_llm`
  覆盖 planning→persist 真实链路。
- 阻断 2：V4 放入 `intent_narrative_envelope`（trace），不再向冻结 V3
  setattr。Writer 从 envelope 持久化 V4/bindings。仅当
  `CODE2PAPER_INTENT_NARRATIVE_PLAN=v4` 时用 V4 投影作为 workset/Writer
  身份（显式 canary）。
- 阻断 3：diagnostic checkpoint `complete=false`；clean 文件只写
  `clean_candidate_markdown`。fallback 只在 incumbent `complete=true` 时
  重发 clean Candidate，否则只发 diagnostic。
- 阻断 4：Writer 加载 V2 并投影到 aligner；alignment 缺失理由改为
  `method_propositions_missing`。最终验证写入 `ClaimVerificationReceiptV2`，
  `verification_mode` 由 receipt 派生，不再用“全 supported 且 0 次调用”
  冒充 exact。有 LLM 时才构造 semantic verifier。
- 阻断 5：Facet 阶段生产 atom/closure/field→atom trace。公式 identity 按
  `formula:facet:{id}` 与 `source_facet_ids` 桥接；`consumed_package_ids`
  与 `committed_paragraph_ids` 分列；required 未桥接保持 open。
- 阻断 6：`apply_local_rewrite_patches` 的产品调用强制传入
  `expected_incumbent_digest` 与 paragraph identity。
- 验证：组合回归 502 passed；全量 `python -m pytest -q` **3597 passed, 3 skipped**；
  `compileall` 与 `git diff --check` exit 0。未跑 P7 live，未默认 cutover。

## 2026-09-16：Author Intent spine 闭环修复（P0–P6 静态，未 cutover / 未 P7 live）

- 依据：`docs/intent_spine_authoring_closure_repair_execution_2026-09-16.md`。
  绑定 live10 `/tmp/c2p-production-entry-20260915-live10`；历史 live commit 与
  当前 probe 不得混作同一快照。未默认 cutover，未启动新的全文 live。
- P0：`_write_closure_metrics` 改为 schema 2.0，分母拆成
  `obligation_candidate_records` / unique symbols / unique obligations /
  must-cover atoms，并区分 search terminal、Candidate surface、repository
  proof。写出 `formula_identity_conservation_v1.json`。冻结夹具
  `tests/fixtures/intent_spine_ebcar/frozen_identity_v1.json`（5 节、28 units、
  7+84 公式 ID、26 包、44/17/6 获取记录；无仓库路径）。
- P1：新增 `IntentNarrativePlanV4` 与 `StoryMechanismBindingV1`。作者 section
  identity 先冻结，mechanism 只做多对多证据绑定；禁止 `Sym:*`/`mech_` 标题。
  产品路径仍以 V3 为 Writer 身份（P7 前不 cutover），V4 作为 sidecar 编译。
  Adapter 在 section id 对齐时按作者 section 回贴 argument units。
- P2：narrative unit 保持，证据拆 `IntentEvidenceAtomV1`；quote 不得窄于
  semantic fields；跨 span proof 拒绝不同 snapshot、互斥分支、未执行构造、
  部分 layer。`author_spec_only` 不能单独清零 Candidate surface。
- P3：canonical formula identity 桥接 7 个 legacy ID 与 84 个 mechanism
  obligation（原始交集 0 保留在 trace）。`formula_worthiness` 去掉
  LOAD/WRITE/RESHAPE 等 plumbing 的默认 display 资格。Mechanism 与 Section
  validator 共用 `formula_code_trace_failures`；冻结 WRITE 包被内容门拒绝。
- P4：clean Candidate 仅在全部 required section committed 后更新；partial
  进 diagnostic / checkpoint。失败 resume 保 incumbent。aggregate
  `completed_section_ids` 逐节保留，另有 `all_required_sections_complete`。
- P5：未知 failure 不默认 Rewrite；patch 校验 incumbent digest 与 paragraph
  identity；`no_progress` 停止同 owner 重试。
- P6：briefs 存在时仍编译 `method_propositions_v2`。词汇 overlap 只召回；
  加法→减法/乘法、极性/量词/条件破坏不能 deterministic exact。验证 mode
  为 `exact_verified|semantic|unresolved`，全 exact 允许 0 次语义调用。
- 验证：`python -m compileall -q src tests scripts` exit 0；`git diff --check`
  exit 0；执行文档列出的测试再加 writer/formalizer/issue-router/p0-closure
  共 467 passed。未跑全量静态、未做 P7 `method-agent run`。

## 2026-09-14：S3.6 后续——错误绑定与统一入口/预算校准检查点

- 依据：`docs/research_to_method_unified_repair_execution_plan_2026-09-12.md` §15.6.4
  及 `.tmp/c2p-s36-independent-review-20260914/review.md`。保留本工作树既有改动。
- P1：`publication_transaction_contract.py` 停止将 exact excerpt 的词汇重叠作为
  atom/detail 授权。加法源码的受限释义必须保留加法、全部加数与非否定极性；
  Binder 只在此检查通过后以词汇分数排序。精确源码摘录仍可通过；required atoms
  全有效后推导 detail 的合同未变。直接声明错误 witness 也由 assessor 拒绝。
  人工闭集反例：乘法正文 `valid=false`、0 atom；正常加法正文 `valid=true`；
  冻结 r6 原文局部 normalization 为 24 witnesses / 1 detail，乘法变体为
  9 witnesses / 0 detail / 1 required-target failure。以上 r6 只是当前代码离线
  回放，不写成真实 live commit。
- P2：`tests/test_agentic_publication_method_writer_unified.py` 通过生产
  `run_publication_method_writer` 入口将 accepted repair 的第二次同身份运行验证为
  零 Writer 重发，rejected repair 的 content receipts 验证为零 commit、不可 resume。
  该集成 fixture 是合成产物；冻结 r6 primary 的旧 `_p1__f1` 与当前 `_p1` 身份
  不兼容，不能将旧低层样本升级成生产统一入口成功提交。
- T3：只读预检 `8006` 的 `/health`、`/v1/models`、`/metrics` 均 HTTP 200，
  模型 `qwen38-27b-nvfp4`，running/waiting/KV/preemptions 均为 0。
  `/tokenize` 对当前冻结 18 个 Writer primary 的 wire chat 输入计数合计
  828,590 tokens，3 页超过现行 60,000 单请求上限；一页 primary 68,323、
  repair 68,873，而 UTF-8/4 仅估到约 40,000。校准只调用 tokenizer
  22 次，模型生成请求 0。证据：
  `/tmp/c2p-s37-calibration-20260914/all_writer_pages.json`、
  `calibration.json`、`budget-table.json`。旧 S3-20 账本的 116 completed / 113 sent
  保守代理已发送 1,990,033，其中 Formalizer 713,436、Writer 954,369、
  Realizer 322,228；113 次历史 provider usage 缺失，不将该代理视为真实 token。
  旧 envelope 2,000,000 与现 profile 2,500,000 身份不同；现 Writer/Realizer
  reserve 400,000/100,000 尚未由全角色真实计量证明。
- 检查：`python -m pytest -q tests/test_agentic_detail_atom_binder_and_trace_v2.py
  tests/test_llm_section_writer.py tests/test_agentic_publication_method_writer_unified.py
  tests/test_agentic_unified_context_compiler.py tests/test_llm_runtime.py -p no:randomly`
  → exit 0，178 passed；`python -m compileall -q src tests scripts` → exit 0；
  `git diff --check` → exit 0。生产合同文件 SHA-256
  `d958aaa15da95b3be41dc88730d179f4189919b7985395ed9e041350f2d55025`；
  预算表 SHA-256 `f1eead1f5e3f91342586b24cbeefebe9700efd7226df1e52fe7832a6a643d8dd`。
- 下一门：按当前 plan/page/schema 从统一入口做冻结响应注入的真实身份微测，
  同时校准 Formalizer/Realizer 与各 repair 的 wire token 上界、重建
  primary/future/spent/unsettled 总表，解决 3 个 Writer 单请求超限后方可
  启动完整 authoring。本片未修改 profile、未发送生成请求、未发布 Candidate/Verified。

## 2026-09-12：取消 OpenCode 协作流程

- 范围：仅修改 `AGENTS.md` 和 `.agent/`；保留工作区既有生产代码、测试和文档修改。
- 规则：Codex 直接负责诊断、实现、验证、审查与修复；取消 OpenCode 交接、`/implement`、
  按角色禁止编辑以及 Codex 只能只读验收的限制。小任务不要求四份协调文档。
- 清理：删除两份旧分派文件；13 份旧任务、计划、诊断及证据文件原样迁入
  [历史归档](archive/2026-09-12/README.md)，其中包含原实现日志的未提交内容。
- 边界：架构、Candidate/Verified 权威分离、证据硬门和 live 准入要求继续生效。
  本次不实现或验收历史产品任务，也不声明旧问题已解决。
- 验证（本次文档修改后的 dirty worktree）：`git diff --check -- AGENTS.md .agent` 通过；
  `python -` 内联检查退出码 0，确认 13 个归档 SHA-256 全部一致、新文档相对链接和
  `AGENTS.md` 的设计路径存在、当前目录仅含 README 与本记录。不运行 pytest、模型或真实 API。

## 2026-09-12：R0＋R1 统一下一步修复首片

执行入口：[Research → Method 统一下一步修复执行文档](../docs/research_to_method_unified_repair_execution_plan_2026-09-12.md)
（`docs/README.md` 已索引）。本片按该文档 §5/§6 实施；未开始 R2 及以后分片。

### R0 基线与反例冻结

- 实现身份：Code2Paper HEAD `84371e4fee974071a580d7832af0ac14908c2d4b`，保留原有未提交修复为基线。
  改动前 tracked diff 字节摘要（`git diff | sha256sum`）`d697160b…aca147`；R1 实施后
  `1ef313f3…7d6bc0`。相关文件：`mechanism_context_compiler.py` `771bc235…5140b`、
  `test_agentic_mechanism_detail_compiler.py` `ab295aba…f12f7`、
  `test_agentic_mechanism_evidence_closure.py` `ea54cfc4…e5c94f`、
  `test_agentic_unified_context_compiler.py` `587bb0fe…d9e4e8a`。子模块 `paperbanana_single_shot`
  `33a9edd6…`。`.tmp/` 为 task-specific 证据目录（gitignored），符合文档 §5 的“任务专属”要求。
- 被研究仓库身份（≠ 实现代码）：EBCAR repo HEAD `287506e3e2df30e3c840b8f6398b5010c25111e1`；
  Run E 冻结 snapshot/tree `repo:9b4f1a34…` / `sha256:9b4f1a34…`；
  核心源码文件 `src/model/ebcar_dedicated_attention_model.py`（当前字节 `d9c5c626…`）。
- profile/模型身份：`tests/live/profiles/qwen36_vllm_budgeted.example.env`
  `sha256:b6814884…79b32d1`（provider openai、base `http://127.0.0.1:8003/v1`、
  `CODE2PAPER_LLM_MODEL=qwen36-27b-nvfp4`、离线核算 context 131072）；Run E 实际模型为
  `qwen38-27b-nvfp4`，与 profile 名不是同一协议，不混用；不记录任何密钥。
- Run E 冻结（root `/tmp/ebcar-live-terminal-disposition-fix-20260911-142500`）：5 个关键文件
  均存在且字节 SHA-256 与文档附录 A 一致（`method_agent_result.json`
  `31bafd2a…05b5c`、`candidate_handoff_v1.json` `02dca90b…7392a`、
  `observation_promotion_ledger_v1.json` `a3da2422…c1a06`、
  `unified_live_admission_v1.formalizer.1.json` `cbbef77f…d4ca9`、
  `mechanism_context_set_v1.json` `980ccc83…ea177f`），本轮用文件工具与一次获准的完整访问重算核对，
  未覆写原 run；模型内 content_digest 与文件字节摘要分开记录。
- 盲修来源：commit `f58d806…ad00` 本地无对象、GitHub 不可达（fetch 134s 超时），
  依据为评审 `adoption-review.md` `d6fb3e17…0f083` 与缓存 `commit.diff`/`files.json`/`patches/`；
  逐项采纳决策已固化在文档 §3，本片据此生成 `adoption_ledger.json`（19 项：采纳/改写/拒绝/无需采纳）。
- 十项目冻结输入盘点：launcher 列出的 10 个 root 当前均存在（dyg、linearrag、ebcar、rap、
  lookahead、unimmad、codequant、domain_pruning、fastgs、learnat），按文档要求不以路径名
  代替内容完整性判定，逐项 listing 记入 `baseline_manifest.json`；本片不做矩阵扩项。
- 交付物（`.tmp/c2p-unified-repair-20260912-r0r1/`，JSON 均校验可解析）：
  `baseline_manifest.json` `c04ae8c6…ee8f1f`、`adoption_ledger.json` `ef3734ec…8da453`、
  `run_e_fixture_comparison.json` `26081e0e…0e1b3`；诊断/运行产物
  `offline/offline-ebcar-r1.json` `e5c4ef8e…22d66f`、
  `run_e_recompile_unknown_details.json` `cb5f56d1…4722c6`。

### R1 同操作条件与路径状态修复

- 问题（Run E 直接根因）：同一冻结 span `146:149`（EBCAR `forward` 内 `torch.zeros` 调用）在
  fact 视图 `calls` + guard `self.cfg.use_dedicated_attention` → `conditional`，在 graph 视图
  `CALL` + 空 guard → `active_default`；旧 `_operation_status` 对 `{conditional, active_default}`
  返回 `unknown`，使 core detail 22 触发 `core_detail_active_path_unknown` 与
  `unified_core_active_path_unknown`。
- 修改函数（均在 `src/code2paper/agentic/mechanism_context_compiler.py`）：
  `_branch_dominance_guards`（新增：typed TRUE/FALSE_BRANCH 与带 guard 的 CONTROL_DEPENDS_ON，
  以 branch span 包含 + NEXT_CONTROL 不越界限定支配范围；返回 recovered/unproven/conflicted 三类）、
  `_normalize_guard_text`、`_same_predicate_family`/`_proven_same_operation`（同作用域内
  同精确 span、同符号、同 operands/result 且谓词属同一通用语义族，如 calls↔CALL）、
  `_cluster_path_evidence`/`_path_evidence_marker_reason`（证据化聚合，替代旧 `_operation_status`，
  后者保留为投影）、`_graph_node_operation`（恢复 guard 与 activation basis 写入记录）、
  `compile_mechanism_evidence_closures`（节点级恢复 + 同精确 span 支配 `resolve_typed_guard`）、
  `annotate_mechanism_paper_details`（detail 的 status/conditions/activation_basis_ids/
  mismatch_reason 由同一证据函数产出；core+unknown 写入 compiler_diagnostics）。
- 远端对照：盲修未修改 `_operation_status`，其 same-span+predicate 相等规则会拆开 calls/CALL
  掩盖问题，明确不采纳（`adoption_ledger.json` 条目 `C-predicate-equality-merge`）。
- 规则要点：`{conditional, active_default}` 只有在证明为同一操作且仅有一个规范化 guard 时才对齐为
  `conditional`，并保留条件与 typed basis；guard 文本不一致 → `unknown`＋`guard_conflict`；
  对应关系不成立 → `unknown`＋`dual_view_correspondence_missing`；极性冲突 → `unknown`＋
  `path_polarity_conflict:*`；带 guard 边支配范围不足 → `unknown`＋`guard_dominance_unproven:*`；
  未证/冲突的 span 不参与同 span 支配。门禁（`validate_mechanism_context_completeness`、
  `validate_mechanism_context_structural_gates`、unified admission）未改，仍 fail-closed。
- 正反回归（项目中立 fixture，完整 owner/source/typed branch/fact-graph 绑定）：
  `tests/test_agentic_mechanism_evidence_closure.py`（节点级 TRUE_BRANCH 恢复、NEXT_CONTROL 不越界、
  极性冲突、支配不足、反向分支 `not (G)`、嵌套合取与顺序不变），
  `tests/test_agentic_mechanism_detail_compiler.py`（对齐通过并清空门禁失败、guard 冲突、
  同 span 不同操作、极性冲突、支配不足、无条件默认路径、未解析配置不升级为 selected、
  已解析 false 配置不升级、JSON 往返、跨 owner 不泄漏、同 span 支配与其 contested 负例），
  `tests/test_agentic_unified_context_compiler.py`（编译→archive detail atom 的消费者面
  status/conditions/basis 一致）。负例均经公共 compile→validate 路径断言，非仅测私有函数。
- 命令与结果（同一 dirty worktree，未跑全量、未调用模型）：
  - `python -m pytest -q tests/test_agentic_mechanism_evidence_closure.py tests/test_agentic_mechanism_detail_compiler.py tests/test_agentic_mechanism_formula_obligations.py tests/test_agentic_publication_method_writer_unified.py`
    → exit 0，`37 passed`。
  - `python -m pytest -q tests/test_agentic_research_models.py tests/test_agentic_candidate_handoff.py tests/test_agentic_autonomous_method_agent.py`
    → exit 0，`125 passed`。
  - 相关消费者回归批次（unified context、mechanism context models/projection/formalizer/realizer、
    behavior graph CALLS、p0 closure、compile candidate、v3 evidence chain、formalization guards、
    detail binder trace v2、research derived authoring、d6 portability、offline matrix）
    → exit 0，`192 passed`。
  - `python -m compileall -q src tests scripts` → exit 0；`git diff --check` → exit 0。
- 冻结离线派生链（零模型调用，Run E 完整 facts/graph/公式义务经真实 loader 重建）：
  `scripts/run_unified_ten_project_offline_matrix.py 'ebcar=/tmp/ebcar-live-terminal-disposition-fix-20260911-142500'
  --repo 'ebcar=/data1/…/EBCAR - Embedding-Based Context-Aware Reranker'
  --profile tests/live/profiles/qwen36_vllm_budgeted.example.env --model-context-tokens 131072`
  → 报告 `offline/offline-ebcar-r1.json`：`unknown_core_active_path_count=0`，两机制的
  `core_detail_active_path_unknown` 与 `unified_core_active_path_unknown` 均消失；Run E 原失败
  detail 22 的混合状态根因被消除。
- 未完成/未通过（不宣称 authoring PASS）：
  - `NEEDS_RESEARCH_EVIDENCE`：配置选择事实仍缺（`self.cfg.use_dedicated_attention` value=null、
    state=unresolved、definition/entrypoint spans 为空），本片只表达已被证明的条件行为；
    `mech_sym:9773c5add7af1f92`/`mech_sym:f6cf5bdfe2ae16f0` 的
    `operation_disposition_unresolved` 是同一类真实缺口（入口路径外未证操作），不靠本片发明证据。
  - strict Research 三条 `unified_core_intent_partial_without_terminal_gap` 与文档 §2.2 一致，未变。
  - 新观察到 `unified_workset_compile_failed:unified_page_projection_incomplete`
    （两页 20766/20868 tokens 超原子页预算）：属 R6 预算/R2 接线范畴，冻结记录、留待对应分片，
    未在本片降低阈值或过滤失败。
  - 本片不运行真实模型、不扩矩阵、不提交合并；R2–R10 未开始。
- 审查结论（文档 §17 清单）：范围与 R0/R1 一致，保留 unrelated dirty baseline 与 §2.4 成果；
  PASS（本片代码接受）＝ 机制证据与门禁行为按上述规则通过；不扩为 live/rollout 权限。

## 2026-09-12：R2 产物交接、源码冻结与准入口径

执行入口同上；按文档 §7 实施。同一 dirty worktree，未调用模型、未提交合并。

### 修改点

- `autonomous_method_agent.py::_writer_artifact_paths`：改为
  `_writer_artifact_paths(out_root, *, persisted_paths=None, allow_legacy_discovery=False)`。
  产品主路传入本次 `persist_product_artifacts` 返回的 `paths`，只解析本修订写出的文件；
  同名旧文件不会被补入。无 manifest 且未显式标记 legacy 时抛出
  `writer_artifact_manifest_required`；目录发现仅供显式标记的旧入口。
  callback 轮次使用同一个 `writer_artifact_paths`，因此每轮绑定同一修订 manifest。
- `repo_snapshot.py`：新增 `VerifiedSourceBytes` / `read_verified_snapshot_sources`：
  按 snapshot root 解析路径（拒绝绝对路径、`..` 与 root 外解析）、按 source manifest 校验
  partition（未列出/被排除的 kind 拒绝）、对照 manifest 与 snapshot 双方 content_digest、
  symlink 越界拒绝、binary/非 UTF-8 只做摘要验证不作为源码文本；字节首次读取后按修订冻结
  （工作区后来修改不改变已加载修订，新加载报 `unified_source_content_digest_mismatch`）。
  同时暴露与 snapshot 一致的 `repo_snapshot_id`/`project_tree_hash` 供 compiler 推导身份。
- `publication_method_writer.py::_load_repository_authoring_context`：`source_provider`
  改为此 reader（保留 `repo_snapshot` 字段用于身份校验）；unified 主路在编译后检查
  `reader.failures`，非空即 `unified_source_read_failed:<codes>` 失败。
  新增 `_evidence_identity_failures`：facts/atomic claims/equation claims 若声明
  snapshot/tree 身份，必须与本次 snapshot 完全一致，否则
  `unified_code_facts_snapshot_mismatch` 等拒绝；未声明身份的旧产物保持可读。
- `scripts/run_unified_ten_project_offline_matrix.py`：`_research_gate_failures` 直接调用产品的
  `_unified_research_gate_failures`，不再维护第二份 strict 判定；新增
  `_research_artifact_paths` 与 `_research_mode_failures`，用产品的
  `_load_authenticated_candidate_handoff` + `_candidate_lane_research_failures` 计算
  Candidate 车道，并在报告 `research` 段输出 `gate_mode`、`strict_failure_codes`、
  `candidate_failure_codes`、`candidate_gate_pass`、`candidate_handoff_status/digest/
  revalidation_failures`；行状态仍为 strict，Candidate 只是显式模式。
- 回归测试：新增 `tests/test_agentic_authoring_context_handoff.py`（manifest 交接、
  verified bytes 漂移/越界/未列出/二进制/排除 partition、reader `files` 视图不可绕过校验、
  跨 run 身份拒绝）；扩展 `tests/test_agentic_replay_execution_record.py`（`--repo` 必须匹配冻结
  tree hash、删除文件后拒绝、symlink 越界记录但不作为源码）、
  `tests/test_agentic_unified_ten_project_offline_matrix.py`（strict 与产品函数逐码一致、
  strict/Candidate 分列、缺 context 与产品一致）、`tests/test_agentic_14_vertical_tests.py`
  （legacy 发现需显式标记、manifest 只绑定本修订）。
  修正 `tests/test_agentic_publication_method_writer_unified.py` 的占位源码摘要
  （`sha256:source` 与真实字节不符），改为真实 digest——该 fixture 正是 R2 要拒绝的漂移样例。

### 命令与结果

- `python -m pytest -q tests/test_agentic_authoring_context_handoff.py` → exit 0，`10 passed`。
- `python -m pytest -q tests/test_agentic_unified_ten_project_offline_matrix.py` → exit 0，`6 passed`。
- `python -m pytest -q tests/test_agentic_replay_execution_record.py` → exit 0，`23 passed`。
- `python -m pytest -q tests/test_agentic_14_vertical_tests.py tests/test_agentic_publication_method_writer_unified.py`
  → exit 0，`21 passed`。
- `python -m pytest -q`（R2 完成后全量静态）→ exit 0，
  `3274 passed, 3 skipped, 7 warnings, 12 subtests passed`（521s）。
- `python -m compileall -q src tests scripts` → exit 0；`git diff --check` → exit 0；
  R2 后 tracked diff 摘要 `858ee3e3…ce9aa`。
- 冻结离线派生链（零模型调用，Run E 完整输入）：
  `scripts/run_unified_ten_project_offline_matrix.py 'ebcar=/tmp/ebcar-live-terminal-disposition-fix-20260911-142500'
  --repo 'ebcar=/data1/…/EBCAR - Embedding-Based Context-Aware Reranker' …`
  → `offline/offline-ebcar-r2.json`：`unknown_core_active_path_count=0`（R1 结论保持）；
  `gate_mode=strict`，strict 失败为三条 `unified_core_intent_partial_without_terminal_gap:*`；
  `candidate_failure_codes=[]`、`candidate_gate_pass=true`、`candidate_handoff_status=eligible`、
  `candidate_handoff_digest=sha256:d17433d2…`、重验失败为空——与文档 §2.2「3 supported＋3 qualified
  partial，handoff eligible」一致。行状态仍为 strict；Candidate 只作为显式模式输出。

### 未完成/移交

- 页预算失败（两页 20766/20868 tokens）仍按 R6 处理；本片未改阈值。
- offline harness 的 `source_provider` 仍使用重建出的 `RepoSnapshot`（其 digest 由重建保证一致），
  未切换到 `VerifiedSourceBytes`；产品侧已使用 reader。若 R6/矩阵需要同源读取口径，届时一并接线。
- 真实模型/live 未运行；R3 未开始。

## 2026-09-12：R3 质量与发现指标诚实计量

执行入口同上；按文档 §8 实施。同一 dirty worktree，未调用模型、未提交合并。

### 修改点

- `publication_quality.py`：新增 `SupportPrecisionMetricV1` 与共享函数
  `compute_support_precision_metric(report, text_digest, report_digest)`：
  缺报告 `not_measured`；报告 `blocked` → `blocked`；`input_text_digest` 与当前正文不符 →
  `invalid(support_precision_text_mismatch)`；计数为布尔/负数/非整数 →
  `invalid(support_precision_count_boolean|negative|invalid:<field>)`；
  `checked != supported+caveated+unsupported+unverified` → `invalid(count_mismatch)`；
  决定分母（supported+unsupported）为 0 → `not_applicable`；否则 `measured`，
  `precision=supported/(supported+unsupported)`，caveated 绝不并入 supported，
  unverified 保留并给出 `support_precision_unverified_claims_present`。
  `verified_authorized` 仅当报告 passed、mode=semantic 且 unsupported/unverified 均为 0，
  `lexical_only` 即使 precision=1.0 也不能授权 Verified。
  `EpistemicSafetyMetricsV1.support_precision` 改为 `float | None`（历史 V1 报告仍可读，
  但其 `support_precision_metric` 默认为 `not_measured`，不追认为已测）；
  `evaluate_publication_method_quality` 新增 `validation_report` 入参，用共享函数产出
  status/precision，并把 `unsupported_positive_claims` 取调用方与报告的较大值（只收紧不放松）。
- `publication_method_writer.py`：主路从 `final_validation_paths` 载入 `text_evidence_validation`
  并作为 `validation_report` 传入质量评估；新增 `_load_expected_operation_population`，
  从可选评估产物 `expected_mechanism_operations_v1` 读取独立 expected population
  （仅评估用），随 `expected_operation_source` 传给 trace。
- `method_content_trace.py`：`build/write_method_content_trace_v2` 新增
  `expected_operation_ids`、`expected_operation_source`；`MechanismInformationFunnelV1`
  新增 `mechanism_discovery_recall: float | None`、`discovery_recall_status`
  （measured/not_measured/not_applicable）、`expected_operation_count`、
  `discovery_population_source`、`closure_retention(_status)`、`zero_denominator_metrics`。
  发现率仅在独立 expected population 存在时计算（分子为 closure ∩ expected），
  不再用 closure 自身作分母；closure retention 单独计算；零分母的 legacy 比率保留历史数值
  但列入 `zero_denominator_metrics`，读者不会把 1.0 当成已测。
- `trust_contracts.py`：`TextEvidenceValidationReport` 的计数字段增加 `mode="before"` 校验，
  拒绝布尔冒充整数（此前 pydantic 会把 `true` 强转为 1）。
- `runner.py`：`_reconcile_publication_quality_with_final_validation` 改用共享 metric
  （不再把 caveated 计入 supported，也不再对零分母记 1.0）；`validation_passed` 要求
  metric 为 measured/not_applicable 且 digest 绑定；safety 回写 precision/metric；
  `_reconcile_publication_writer_result_with_quality` 的“无变化即跳过”判定加入
  candidate/verified validation status、warnings 分区与 quality digest，
  使总体状态不变时的可见状态变化仍会回写，并同步写入 `publication_quality_digest`。

### 回归测试

- `tests/test_agentic_publication_method_writer.py`：support precision 状态矩阵
  （缺测、零分母、计数不守恒、布尔、旧正文、blocked、全 caveated、semantic vs lexical_only），
  以及旧 V1 报告可读但不视为已测。
- `tests/test_agentic_runner.py`：runner 侧 measured/not_applicable/invalid 三例、
  Writer 与 runner 对同一报告结论一致的显式比对、总体状态不变但 validation 状态变化时回写。
- `tests/test_agentic_detail_atom_binder_and_trace_v2.py`：独立 expected population 正反例
  （缺 population→not_measured；空 population→not_applicable；漏一个→0.5；齐全→1.0）、
  closure retention 与零分母清单。

### 命令与结果

- `python -m pytest -q tests/test_agentic_runner.py tests/test_agentic_publication_method_writer.py
  tests/test_agentic_method_content_trace.py tests/test_agentic_detail_atom_binder_and_trace_v2.py
  tests/test_agentic_publication_method_writer_unified.py` → exit 0，`172 passed`。
- `python -m compileall -q src tests scripts` → exit 0；`git diff --check` → exit 0。
- `python -m pytest -q`（R3 完成后全量静态）→ exit 0，
  `3281 passed, 3 skipped, 7 warnings, 12 subtests passed`（521s）。
- R3 后 code state：tracked diff `fa7af109…1a42`；`publication_quality.py` `7aded663…e0dbac`、
  `method_content_trace.py` `c98503b9…1d2e85`、`runner.py` `8186775a…752989`、
  `trust_contracts.py` `b751b2ca…090f7b`。

### 未完成/移交

- 真实模型/live 未运行；R4 未开始。
- 发现率的独立 expected population 目前只能由评估产物提供；本片保证缺失时为 not_measured，
  不为补分母而生成清单。

## 2026-09-12：R4 Research 读取复用、记忆、符号与 parse 恢复

执行入口同上；按文档 §9 实施。同一 dirty worktree，未调用模型、未提交合并。

### 修改点

- `research_read_identity.py`：区分两类身份——`content_read_signature`（字节身份，用于缓存/复用）与
  新增 `obligation_read_signature`（`<obligation>|<byte identity>`，用于 no-gain 判定）。
- `research_policy.py::_no_duplicate_no_gain`：no-gain 改为按 obligation 判定（新增
  `_obligation_read_signature`；`_content_read_signature` 保留为字节身份）。同一 obligation 重读同一
  span 仍拒绝；**另一 obligation 读取同一 span 不再被拒绝**（字节可复用，但该问题仍需自己的图/claim 编译）。
- `research_graph.py::_executed_read_signatures`：改为发出 obligation-scoped 签名。
- `research_supervisor.py`：
  `_candidate_read_already_executed` 与 `build_decision_context` 的已读候选过滤都只看**当前 obligation**
  的执行记录；新增 `PriorReadMemoryV1` 与 `ResearchDecisionContextV1.relevant_prior_reads`/
  `prior_reads_truncated`/`prior_reads_projection_status`——从持久 `observation_history` 投影当前问题相关的
  先前精确读取（同 obligation → shared_symbol → shared_span → shared_path），带 `selection_reason`、
  `recency_rank`、按 `memory_budget` 限界；投影明确是 context 而非覆盖证明，被预算截断时置位标记。
- `research_nodes.py`/`research_graph.py`：把 `loop.observation_history` 传入决策上下文（检查点/resume 后
  历史来自恢复的 loop state，预算与选择规则不变）。
- `gemma_supervisor_backend.py`：`forbidden_exact_reads` 只列当前 obligation 的已执行读取，另有
  `reusable_prior_reads`（其他 obligation 的可复用记忆）与更新后的系统提示；新增
  `decision_failures` 记录：每次 proposal 边界失败记录 `failure_class`
  （llm_api_error/llm_blocked/llm_empty_response/llm_parse_error/representation_repair_failed/
  content_error_returned_to_owner）、prompt template、schema、model/provider、response_mode、
  finish_reason、blocked_reason、原始文本摘要（digest+preview）、恢复操作与摘要；恢复成功走既有
  recovery 且不记失败，恢复失败与内容错误走不同路径。
- `implementation_scope.py::_canonical_symbol_id`：compact path/name 引用只在**唯一匹配**时绑定；
  同名不同作用域或同文件多候选保持歧义（不再取第一个匹配）。
- `intent_compiler_v2.py`：`feature_combination` 只保留显式 concat 词表（CONCAT）；
  新增 `feature_fusion` 覆盖 combine/merge/fuse/aggregate（多形态谓词），作者显式拼接/顺序/条件要求不变。

### 回归测试

- `tests/test_agentic_research_policy.py`：同 obligation 重读拒绝、跨 obligation 允许（原两条
  cross-obligation 拒绝用例改写为同 obligation 拒绝 + 跨 obligation 允许）。
- `tests/test_agentic_graph_research_loop.py`：签名带 obligation，且不再以裸字节身份作 no-gain 键。
- `tests/test_agentic_research_supervisor.py`：当前 obligation 的已读抑制读取；其他 obligation 的读取不抑制；
  prior-read 投影选择原因、顺序、预算截断与状态；候选过滤仅按当前 obligation。
- `tests/test_agentic_gemma_supervisor_backend.py`：可恢复 JSON 损伤走恢复且不记失败；不可恢复解析失败
  `representation_repair_failed` 并保留真实终态；空响应/blocked 分类不同；未知工具属内容错误
  （`content_error_returned_to_owner`）而非表示损伤；prompt 的 forbidden/reusable 分区。
- `tests/test_agentic_research_models.py`：compact 符号唯一匹配正反例。
- `tests/test_agentic_intent_compiler_v2.py`：combine/merge/fuse 不强制 CONCAT，显式 concatenate 仍要求 CONCAT。

### 命令与结果

- 相关测试批次（supervisor/graph loop/policy/gemma backend/checkpoint resume/research models/
  intent compiler/tools extended/typed refs/target proposer）→ exit 0，`519 passed, 1 skipped`。
- `python -m compileall -q src tests scripts` → exit 0；`git diff --check` → exit 0。
- `python -m pytest -q`（R4 完成后全量静态）→ exit 0，
  `3292 passed, 3 skipped, 7 warnings, 12 subtests passed`（522s）。
- R4 后 code state：tracked diff `649b0658…4637a`；`research_read_identity.py` `0eb5f425…98b92`、
  `research_supervisor.py` `b8011375…f1abb`、`gemma_supervisor_backend.py` `279777c6…9b929`、
  `implementation_scope.py` `5f37df58…468c`、`intent_compiler_v2.py` `acbb715f…4d12`。

### 未完成/移交

- Run D 的原始 supervisor 响应在可访问证据中未找到（文档只标注“待绑定样本”，无冻结 root）；
  按 §9.6 只记录未复现缺口，不编造同样输入。协议级 synthetic 负例（可恢复/不可恢复/空/blocked/内容错误）
  已补齐；若后续取得 Run D 冻结产物，应按本片 `decision_failures` 字段归档并复核。
- 真实模型/live 未运行；R5 已开始（见下）。

## 2026-09-12：R5 公式身份、授权与论文条件表达

执行入口同上；按文档 §10 实施。同一 dirty worktree，未调用模型、未提交合并。

### 修改点

- `formalization_agent.py::adapt_mechanism_formula_package_to_legacy`：旧 sidecar 适配只有在
  `evidence_authority=repository_verified` 且 `formula_lane=repository_derived` 且
  `review_status=accepted` 且存在精确绑定（fact/equation/operation）时才给 `code_verified`；
  author-intent 映射为 `author_intent`/`author_intent_academic`/`review_required`，其余映射为
  `partial`/`hybrid_partial`/`review_required`；新包写 `schema_version="2.0"`（两处当前构建点同步）。
- `publication_transaction_contract.py::_formula_package_terminal_disposition`：只有缺版本标记或
  `1.0` 的历史包才允许走旧“默认 accepted”兼容分支；`2.0` 包缺 disposition 字段保持
  `review_required`，不会被当作历史默认接受。
- 条件绑定改为受控语义判定：新增 `_CONDITION_EQUIVALENCE_GROUPS`/`_CONDITION_NEGATION_TOKENS`/
  `_CONDITION_UNCONDITIONAL_TOKENS`/`_CONDITION_CONNECTIVES`/`_CONDITION_NOISE_TOKENS`/
  `_normalized_condition`/`_condition_token_matches`/`_condition_statement_matches`；
  `_witness_satisfies_constraints` 的条件比较走该判定（等价论文表述可绑定，缺失/反向/扩大范围失败），
  仍拒绝 substring 原码硬匹配与宽松关键词相交。
- `llm/section_writer.py::_compact_formula_packages_for_llm`：compact payload 保留
  `review_status`/`schema_version`/`source_detail_ids`（id-less 与常规两条路径都保留），机器可读 lane
  不因自然语言提示丢失。
- `_run_mechanism_formalizer_legacy`：读取真实 `LLMResponse.blocked_reason`/`text`/`content`；
  新增 `interface_failures`、`missing_binding_obligations`、`rejected_obligations`、
  `not_applicable_obligations`、`deterministic_obligation_ids`，正常缺包、失败包、rejected 与
  not_applicable 分开，接口异常不再被确定性 fallback 掩盖；逐页调用上界与既有 receipt/fragment 不变。
- display block 仍由 `canonical_formula_markdown_block` 只生成唯一 display-math 块；
  `splice_formula_placeholders` 的 `allowed_package_ids` 继续拒绝错误段落消费者。

### 回归测试

- `tests/test_agentic_formalization_guards.py`：author-intent 带 fact ID 不升级、review-required 不接受、
  repository-derived 需精确绑定、缺 disposition 的当前包不被历史默认接受、条件等价可绑定/反向失败、
  compact payload 保留机器可读元数据、legacy caller 读取真实 text 并记录 blocked、缺绑定与
  not_applicable 分类。
- 既有 `tests/test_llm_section_writer.py`（错误消费者拒绝）、`tests/test_v34prose_formula_and_leak_repair.py`
  （display block 不含整篇备忘录）继续通过。

### 命令与结果

- R5 指定测试批次（mechanism formalizer/formalization guards/formula obligation truths/formula
  obligations/detail atom binder/section writer/unified writer）→ exit 0，`169 passed`。
- `python -m compileall -q src tests scripts` → exit 0；`git diff --check` → exit 0。
- G2 全量静态与冻结离线链见下节（R6 后统一运行）。
- R5 后 code state（R6 前）：`formalization_agent.py` `4e35baf3…`、
  `publication_transaction_contract.py` `5bb44903…`、`llm/section_writer.py` `406ee327…`。

### 未完成/移交

- R5 未运行真实模型；V2 page/prompt/payload/receipt 的字节身份在 G2 冻结离线链中复核（见 R6 节）。
- 条件语义判定只覆盖论文条件表达与 witness 绑定；未引入固定 caveat 正则或原始条件逐字包含。

## 2026-09-12：R6 调用预算、真实入口与可移植产物（含 G2）

执行入口同上；按文档 §11 实施。同一 dirty worktree，未调用模型、未提交合并。

### 修改点（11.1 预算合同与计量）

- `unified_context_models.py`：新增 `UnifiedTokenMeterV1`（`method`/`tokenizer_identity`/`unit`/
  `measurement_basis`/`bytes_per_token`）、`RoleRequestBudgetV1`（prompt/output/thinking 预留）、
  `UnifiedRequestTokenAccountingV1`（system/prompt/payload/schema/wrapper 预留 + context/输出/thinking/
  margin + fits/overflow）。`RunInvocationBudgetEnvelopeV1` 新增 `token_meter`、
  `request_budget_by_role`、`max_request_input_tokens_by_role`、`safety_margin_tokens`、
  `model_context_tokens`，缺任一角色预算或每请求上限即校验失败。`ActualRequestReceiptV2` 增加
  `token_accounting`（被拒绝的请求也保留计量）。
- `unified_context_compiler.py`：新增 `measure_unified_tokens` 与 `account_unified_request_tokens`
  （计划与实际发送共用同一计量器与同一次计算；无真实 tokenizer 时使用显式标记的保守估算，
  不把 UTF-8 字节数声称为 tokenizer token 数）；`read_unified_budget_profile` 与
  `BUDGET_FIELD_BY_ENV` 扩展为唯一声明式合同（含 `max_binder_calls`、safety margin、prompt/thinking
  预留、每角色 output 预留与每请求输入上限），删除 2048/4096/8192 等代码内默认值。
  `build_consumer_invocation_plan_v1` 不再接收独立预留参数，只从 envelope 取名；
  `_plan_invocation_token_accounting` 在计划阶段用同一函数测量渲染 prompt、结构化 payload、
  response schema 与声明的 wrapper 预留，`max_input_tokens` 即该测量值，超过声明上限直接
  `unified_invocation_budget_exceeded`。admission 增加每请求上限、角色 output 预算一致性检查。
- 发送边界：writer/realizer 在真实发送前用 envelope 计量器测量实际请求，超过声明每请求上限即
  `..._input_tokens_exceeded` 拒绝并持久化 receipt；formalizer 的请求就是被准入的 consumer envelope，
  计划值与实际值必须完全相等，否则记录 mismatch。三者都不再把未计量请求交给 provider。
- `publication_method_writer.py`：profile 预算改由 `read_unified_budget_profile(os.environ)` 读取；
  formalizer executor 接收 `budget_envelope`。`scripts/run_unified_ten_project_offline_matrix.py`
  删除自带的第二份 profile 映射，直接使用同一 `BUDGET_FIELD_BY_ENV`/`read_unified_budget_profile`，
  离线与产品对同一缺失字段给出同一失败码。
- `tests/live/profiles/*.env` 与 unified writer 测试环境补齐声明值（binder calls、safety margin、
  prompt/thinking 预留、每角色 output 预留、每请求输入上限）。

### 修改点（页预算真相与超大原子报告）

- `_pack_pages_by_detail_graph` 的分组预算改为按**整页 payload**（header + obligation_ids + atoms +
  projection_proof）计量，而不是逐 atom 估算求和；真实页面因此不会再出现“打包接受、构造时超预算”。
  单页最小单位放不下时报告 `unified_atomic_page_over_budget:obligation:<id>:<tokens>><cap>` 与
  `...:contribution:<atom_id>:<tokens>`（最大贡献原子），不截断证据、不压低 obligations。
- mechanism 页与 join 页的超预算报告同样带贡献原子；section 页构建错误消息带最大原子及其 token。
- 冻结 Run E 离线链此前的 `unified_page_projection_incomplete: unified_atomic_page_over_budget:page:…`
  已消失：workset 编译通过（113 页，`status=pass`）。

### 修改点（11.2 独立兼容小修）

- `pyproject.toml`：安装入口 `code2paper` 改指向 `code2paper.cli.main:main`（已有唯一产品 parser，
  不再有第二个 parser 的转发缺口）；`code2paper.main_cli` 仍可导入。
- `writing_callback_fulfillment.py`：callback artifact 文件名可移植（`_portable_callback_filename`），
  逻辑 `artifact_id` 保留在 JSON 内；`_write_callback_artifact` 幂等（同内容不重写）、不同内容写入
  完整摘要区分名、再冲突则 `writing_callback_artifact_conflict` 失败关闭；artifact 记录新增显式
  `artifact_path`（`WritingResearchCallbackArtifactV1` 同步新增可选字段，空值在 Writer prompt payload
  中被剔除以保持 legacy 提示字节兼容；`tests/test_agentic_publication_method_writer.py` 的
  callback resume 用例证明 payload 形状未变）。
- `validators/latex_smoke_validator.py`：smoke 输入固定 LF，子进程显式 `encoding="utf-8"`、
  `errors="replace"`；`benchmark_review_workspace.py` 的 review context 写文件固定 LF。
  `tool_runtime.atomic_write_bytes` 已满足同目录原子替换与短前缀不影响最终目标/digest，补测试固定。
- 冻结离线链摘要可复现性修复（R2 交接面的集成缺陷）：`VerifiedSourceBytes` 暴露确定性
  `content_digest`（快照 id、tree hash、manifest digest 与排序后的路径/digest，不含捕获时间）；
  `RepoSnapshot.content_digest` 排除 `created_at`/`project_root`/git 观测字段；
  `_source_digest` 不再对无身份对象做 `str(object)` 回退（否则会哈希内存地址）；
  离线脚本改用 `read_verified_snapshot_sources`（与产品同源）与 `repo_snapshot_identity_digest`。
  修复前同一冻结输入两次进程得到的 archive/envelope digest 不同，修复后完全一致。

### 回归测试

- `tests/test_agentic_unified_context_compiler.py`：envelope 缺任一声明字段失败关闭、每请求上限在计划期
  拒绝、计划期与实际发送测量同一组 parts 且相等、超预算 overflow 由上限或 context 决定、
  整页计量导致合法拆分且不丢证据（含 atom-sum < page-cost 的对照）。
- `tests/test_agentic_publication_method_writer_unified.py`：新增“实际请求超过声明上限时先拒绝后发送”
  用例（模型零调用、receipt 记录 rejection 与 accounting）。
- `tests/test_agentic_autonomous_method_agent_cli.py`：安装入口 `code2paper` 转发 `method-agent`
  且其他子命令/帮助保留。
- `tests/test_r6_portability_and_budget_hygiene.py`：atomic write 幂等替换、callback 文件名可移植且
  逻辑 id 不变、同内容幂等/不同内容不覆盖/冲突失败、latex smoke LF 与显式解码、
  snapshot/reader 身份排除捕获时间、无身份 provider 的 digest 稳定。

### 命令与结果

- 相关测试批次（formaliz/unified/publication/authoring/autonomous/tool_runtime/portability/llm_runtime/
  method_agent）→ exit 0，`636 passed`；R6 定向批次 → exit 0。
- G2（R2–R6 后）：
  - `python -m pytest -q` → exit 0，`3316 passed, 3 skipped, 7 warnings, 12 subtests passed`（516s）。
  - `python -m compileall -q src tests scripts` → exit 0；`git diff --check` → exit 0。
  - 冻结 Run E 离线链（零模型调用，`--repo` 重水化，profile `qwen36_vllm_budgeted`）：
    `archive digest sha256:6b2ec29d…`（887 atoms，`status=pass`）、`worksets page_count=113`、
    `unique_tokens=459096`、`sent_tokens=270417`、`status=pass`；两次独立进程 digest 完全一致。
    残留失败码：`operation_disposition_unresolved`（入口路径之外的操作）、
    `unified_core_intent_partial_without_terminal_gap:*`（严格 lane 的诚实缺口）、
    `unified_narrative_plan_compile_failed:narrative_plan_v3_invalid`（R7 绑定切片）。
    证据：`.tmp/c2p-unified-repair-20260912-r6/offline/offline-ebcar-r6-final.json`。
- R6/G2 后 code state：tracked diff `d679c48b…`；`unified_context_models.py` `3269389f…`、
  `unified_context_compiler.py` `0b368267…`、`formalization_agent.py` `00597401…`、
  `publication_method_writer.py` `5651865a…`、`repo_snapshot.py` `6608f2dd…`、
  `writing_callback_fulfillment.py` `d4937ace…`、`mechanism_context_compiler.py` `624374ce…`、
  `scripts/run_unified_ten_project_offline_matrix.py` `6ba4bb68…`、
  `tests/test_r6_portability_and_budget_hygiene.py` `1c64057c…`。

### 未完成/移交

- 真实模型/live 未运行；G4 需另行授权。
- 冻结离线链在 workset 之后仍未进入 narrative plan 编译（R7 的 `missing_core_detail` 绑定缺口），
  该切片按计划在 G2 之后实施。
- 计划期 run reservation 仍按计划测量值累计（每请求另有声明上限约束）；如需把 cap 作为上界计入
  全 run 预留，应在 live 校准后再调整，不在本片猜测。
- 未执行 Windows 平台测试：文件名校验只覆盖 POSIX 行为，不宣称 Windows 已验收。

## 2026-09-12：R7 叙事 → controller 精确绑定（进行中）

按文档 §12 实施；同一 dirty worktree，未调用模型、未提交合并。

### 已完成

- `method_architect.py::build_narrative_plan_v3` 的“prior outline 章节数 > 机制数”分支重写：此前只用
  `context_items[0]` 把第一个机制的细节摊到全部旧章节，其余机制的 core clean detail 被静默丢弃
  （Run E 因此 `narrative_plan_v3_invalid:missing_core_detail` ×7）。现在按全部非 side-branch 机制
  角色排序后的扁平工作列表分配章节，段落仍只属于一个机制所有者（按机制边界与 8 条上限切块），
  每个 core clean detail 恰好放置一次；公式包只在拥有其 `source_detail_ids` 的段落放置一次，
  review 细节只附加到其机制的第一个段落；章节 `mechanism_ids`/unit `mechanism_context_ids` 记录
  该章节内不同所有者，空章节保留形状但不重复放置已归属细节。
- 新增 `tests/test_agentic_narrative_architect_v3.py::test_multi_section_outline_places_every_mechanism_core_detail`：
  两机制 + 四旧章节，断言无 `missing_core_detail`、全部 core detail 恰好放置一次、段落 owner 唯一、
  unit 覆盖两个机制。

### 命令与结果

- `tests/test_agentic_narrative_architect_v3.py`、`test_agentic_publication_method_writer_unified.py`、
  `test_agentic_unified_ten_project_offline_matrix.py` → exit 0，`17 passed`。
- 更宽批次（method architect product readiness/narrative/authoring plan/unified writer）→ exit 0，
  `55 passed`；`compileall`/`git diff --check` exit 0。
- 冻结 Run E 离线链：`narrative_plan_v3_invalid:missing_core_detail` 已消失，链推进到
  writer workset 扩展：
  `unified_writer_workset_extend_failed:unified_atomic_page_over_budget`，
  `section MA-S1 paragraph closure exceeds page budget 25618>20000`（最大原子 4290/3761/3310）。
  仍为 `fail`，未调用模型。

### 未完成/移交（下一步）

- 段落已是 Writer 事务的原子消费单位，但单个段落的闭包可以超过 `max_page_input_tokens`；R7 剩余工作
  是在计划阶段生成合法页/段落 revision（或经事务合同允许的段落分片），而不是截断证据或抬高阈值。
  下一步先核对 `publication_transaction_contract` 与 `_writer_section_inputs_v3` 对“同一段落跨页”的
  真实约束，再决定段落拆分（计划 revision）还是显式分片（页元数据 + witness 归属），并补相应正反测试。
- §12.2 的 proposal caller 权限与失败路径、`prior_sections < contexts` 分支的拆并章节单位/依赖保留
  尚未实施。

## 2026-09-12：方向复核后的 R5–R7 纠偏（F1–F4）

触发：`docs/research_to_method_repair_direction_review_2026-09-12.md` 的四项 P1 发现。按报告顺序
（条件授权 → 章节身份与 join 接线 → 合法分页与总预算 → 新的离线报告）在同一 dirty worktree 纠偏，
未调用模型、未提交合并。R5 条件部分的“等价短语可绑定”结论按报告要求撤回，改为结构授权。

### F1 条件授权纠偏（R5）

- 删除 `publication_transaction_contract.py` 中写入通用生产代码的项目答案
  （`_CONDITION_EQUIVALENCE_GROUPS` 的 `self.cfg.use_dedicated_attention` /
  `self.cfg.add_positional_encoding` 等）。词法匹配只用于定位候选子句，不再单独授权。
- 新增结构判定：子句切分保留 AND/OR 序列（`_condition_clauses`）、逐子句否定奇偶
  （`_condition_parity`）、比较运算符与数值字面量（`_condition_comparator`/`_condition_numbers`）、
  无条件标记拒绝、未匹配子句不得携带极性/比较或复述已声明谓词。标识符按词法部件比较
  （`self.cfg.use_dedicated_attention` → use/dedicated/attention），通用动词集合只允许动词层面
  改写（use↔enabled），不做项目词表。
- 授权路径：`_witness_condition_and_polarity_satisfied` 被 Binder 响应校验、确定性 Binder
  （Writer 声明 witness 若改变条件即丢弃并保持未绑定）与 `assess_paragraph_transaction`
  （Writer 事务路径）共同使用；结构无法证明时失败关闭，返回 owning Agent 有界修复，
  不引入项目白名单、不改回源码逐字包含。
- 回归：`tests/test_agentic_formalization_guards.py::test_condition_binding_is_structural_and_never_lexical`
  （AND↔OR、反向/追加反向条件、无条件、嵌套否定、比较边界、at least/at most），
  `tests/test_llm_section_writer.py::test_transaction_condition_binding_rejects_structure_changes`
  （真实 Binder/事务路径：错误条件不绑定、`assessment.valid is False`）。

### F2 章节身份纠偏（R7）

- `method_architect.py::build_narrative_plan_v3` 的“旧章节数 > 机制数”分支改为**按已证 owner 分配**：
  旧章节的 owner 只能来自其声明的 `mechanism_ids` 或其段落的 `mechanism_id`（唯一时才成立）。
  内容不再按位置均分；同一 owner 的多个章节按该 owner 的细节连续分配；机制在旧 outline 中没有
  已证章节时生成显式 revision 章节（`MA-REV-<slug>`）并在 trace 记录；owner 不可证明的旧章节
  不再复用，`trace["section_identity_failures"]` 显式列出 `prior_section_owner_unproven:<id>`。
- 复用段落保留其 id、`reader_goal` 与首尾 transition；公式包只在拥有其 source detail 的段落放置。
- `validate_narrative_plan` 新增 owner 一致性检查：段落 owner 必须属于其 section 与 unit 的
  mechanism 集合，且 required detail 必须属于该 owner 的上下文（`paragraph_owner_not_in_section`/
  `paragraph_owner_not_in_unit`/`paragraph_detail_owner_mismatch`/`unit_owner_not_in_section`）。
- 回归：多章节用例断言“旧章节声明的 owner 与其段落 owner、标题一致且不跨机制”，新增反序 outline
  用例与 owner 歧义显式阻塞用例。

### F3 join 页路由（R7）

- `build_consumer_invocation_plan_v1` 的 join 预扫描改为按消费者身份区分：公式 repair join 页
  （属于 formula workset 且带 `repair_obligation_id`）继续登记 repair 槽位；章节 join 页
  （属于 section workset、带一致 `join_dependency_proof`、无 repair id）作为合法 Writer/Realizer
  页通过；既无 repair id 又无依赖证明、或章节页伪造 repair id、或依赖证明与 header/atoms 不一致
  时失败关闭（`unified_page_projection_incomplete`）。
- 回归：`tests/test_agentic_unified_context_compiler.py` 的双机制章节 join 页走通
  writer plan，以及伪造 repair 身份/缺失依赖证明的负例。

### F4 预算闭合（R6，live 前）

- `RoleRequestBudgetV1`/accounting 新增声明的 `scaffolding_token_reserve`（每角色，profile 声明；
  正式化/binder 为 0，writer/realizer 4096）：计划期把它计入 `invocation.max_input_tokens`，
  使计划值成为该角色真实请求的上界；发送端测量真实 parts 时传 0，避免把 allowance 重复计入。
- 发送端合同（writer/realizer/formalizer 三处一致）：先测实际请求，依次检查角色每请求上限、
  计划上界（`planned_request_input_tokens`）、再按 ledger 的**已完成 receipt** 汇总本角色已用
  token 与该 phase plan 的 `reserved_input_tokens_by_role` 做原子扣账
  （`run_reservation:<needed>><remaining>`）。重试与 resume 复用同一 reservation，不再另起额度；
  `ConsumerInvocationPlanV1.reservation_contract = "atomic_debit_v1"` 明确记录该合同。
- 新增 `read_all_completed_receipts`（run 级汇总，按 plan digest 过滤）、
  `spend_input_tokens_by_role`、`remaining_run_input_tokens`；写端若 ledger 不可读则记
  `run_ledger_unreadable` 并拒绝发送。
- 回归：计划上界与 allowance（`test_writer_request_over_planned_bound_is_rejected_before_send`、
  `test_writer_request_over_declared_cap_fails_before_planning`）、envelope 缺 `scaffolding_*`
  失败关闭、以及重试/resume 扣账用例（同一 reservation、按 plan digest 过滤、resume 重算）。

### 命令与结果（本轮）

- 定向批次（formaliz/unified/publication/authoring/autonomous/tool_runtime/portability/llm_runtime/
  method_agent/narrative/binder/section_writer）→ exit 0，`721 passed`。
- `python -m compileall -q src tests scripts` → exit 0；`git diff --check` → exit 0。
- 全量静态（F1–F4 后）：`python -m pytest -q` → exit 0，`3325 passed, 3 skipped, 7 warnings,
  12 subtests passed`（332s）。
- 冻结 Run E 离线报告（零模型）：`.tmp/c2p-unified-repair-20260912-r7/offline/offline-ebcar-r7.json`，
  摘要与文件摘要见同目录 `r7-summary.json`。observations：
  - source `pass`（重水化 tree hash 与冻结一致）、archive `pass`（887 atoms，
    `sha256:6b2ec29d…`）、基础 worksets `pass`（113 页）；
  - writer workset 扩展后 131 页 / 4 worksets；formalizer/writer/realizer 三个 phase 均编译
    （65 / 18 / 18 planned calls，`reservation_contract=atomic_debit_v1`）；
  - `failure_details` 为空；残余 failure codes 仅为研究证据类：
    两机制 `operation_disposition_unresolved`、strict lane 三条
    `unified_core_intent_partial_without_terminal_gap`（Candidate gate `pass`，handoff eligible）；
  - 因此本片只声明“结构链路编译完成”，不声明 strict admission、正文质量或 live 通过。
- code state（F1–F4 后）：tracked diff `sha256:99e6acb39d8f4e55…`；
  `unified_context_compiler.py` `6d133a3a601a`、
  `unified_context_models.py` `1d9ac15a51e4`、
  `publication_transaction_contract.py` `ac2d02d6ec7b`、
  `method_architect.py` `a60bb2e01264`、
  `publication_method_writer.py` `a41d32d92c7b`、
  `formalization_agent.py` `84e8fec1c199`、
  `unified_invocation_ledger.py` `08b5e7790f51`。

### 未完成/移交（R8 待开始）

- §12.2 的 proposal 权限目前只记录“未消费”；把 proposal 真正接入组织/阅读问题/段落深度（仍在闭集内）
  属于 R7 后续或 R8 前置，不与已验证的 typed owner 分配混为一谈。
- strict lane 的三条 `core_intent_partial` 与两机制 `operation_disposition_unresolved` 仍需 Research 证据，
  不能以分页或预算调整掩盖；配置选择证据（`self.cfg.use_dedicated_attention`）仍为
  NEEDS_RESEARCH_EVIDENCE。
- `conservative_utf8_bytes_div_4` 仍是无 tokenizer 时的声明式估算；live 前若接入真实 tokenizer，
  必须记录 tokenizer 身份并按同一计量器重测计划与实际。
- 真实模型/live 未运行；R8–R10（callback 事务、搜索终态、假设修订）尚未开始。

## 2026-09-12：R8 局部 callback 事务与稳定比较分母

按计划 §13 实施；同一 dirty worktree，未调用模型、未提交合并。

### 修改点

- 新增 `callback_dependency_closure.py`（小型 typed bridge）：`CallbackAuthorityDeltaV1` 描述一轮 callback
  真正引入的 typed 变更（detail/operation/fact/claim/equation/configuration/condition/formula），
  `compute_callback_dependency_closure` 只经 typed 引用映射到 unit/paragraph/section
  （claim/equation/configuration → argument unit → owning sections **多对多**，detail → narrative
  paragraph → section）；无 typed 归属的目标进入 `unresolved_target_ids`，不做字符串搜索或静默丢弃；
  heading、章节顺序、措辞与生成时间不进入闭包（`content_digest` 对 heading 改名不变）。
  `narrow_resume_sections` 只在闭包非空、无未决目标且是请求集合子集时收窄 resume 范围；
  其余情况（未决/空/超集）保留请求范围并记录原因——重新验证更宽是安全的，跳过可达章节不是。
- `writing_callback_fulfillment.py`：每轮在 Writer resume 之前用该闭包计算并收窄
  `resume_section_ids`，trace 记录 `dependency_closure`/`resume_scope_source`/`requested_resume_section_ids`；
  未受影响兄弟章节不进入 resume，已提交正文/authorship/witness/placement 原样保留。
- 阶段状态分离并持久化：`WritingCallbackFulfillmentResultV1` 新增
  `research_fulfilled`/`revision_rebuilt`/`writer_resumed`/`prose_committed`/`final_validation_status`/
  `resume_scope_source`/`budget_rounds_consumed`/`dependency_closure`/`stage_identity`。
  `stage_identity` 在 initial、research 完成后、revision 重建后、Writer resume 后四个点记录
  mode/source_context_digest/page_manifest_digest/contract_present，三处中断恢复的身份可直接比对；
  Writer 失败时 `prose_committed=False`，不把 fulfillment 成功写成正文已提交。
- 回调轮次预算持久化：`artifacts/research_tool_data/writing_callback_budget_v1.json` 记录已消费轮次，
  每次进入循环前读取并从 `max_callback_rounds` 扣除，重放不再重置预算；
  预算耗尽返回 `callback_round_budget_exhausted_durably`。
- `publication_method_writer.py` 事务比较改用**独立计算的 required target set**：
  `_rewrite_required_target_rows`（target 类型/稳定 ID/所属 unit 的 authority lane/命题与 claim 的
  required_qualifiers 与 polarity，规范排序）+ `_rewrite_required_target_set`（单独 digest 与规范 ID 列表），
  写入每份 transaction metrics 并持久化为 `rewrite_transaction_metrics_v1`
  （`artifacts/07_validation/`，输出名已注册）。`_rewrite_transaction_has_cluster_gain` 先判
  `required_target_removed:*`（删目标不是增益），再对 incumbent∩candidate 做逐目标失败数非回归；
  合法新增目标形成新比较基线但交集仍受约束。

### 回归测试

- 新增 `tests/test_agentic_callback_dependency_closure.py`：typed 映射（claim/detail/共享 configuration
  多章节）、未决目标显式报告且不收窄、heading 改名不改变闭包 digest、子集收窄与超集保守、
  阶段状态分离、持久轮次预算读取/写入与损坏记录处理。
- 新增 `tests/test_agentic_rewrite_target_set.py`：target set digest 不受 heading/章节顺序影响且不等于
  整份 plan digest、删目标被拒（`required_target_removed`）、新增目标保留交集非回归。
- 既有 callback/continuation/writer 用例继续通过（`227 passed` 定向批次；更宽 R8 相关批次 `447 passed`）。

### 命令与结果

- `python -m compileall -q src tests scripts` → exit 0；`git diff --check` → exit 0。
- 全量静态见下方“R8 后全量”。

## 2026-09-12：R8 复核纠偏（三项 P1）

触发：`docs/research_to_method_repair_direction_review_2026-09-12.md` 之后的第二轮只读复核。R8 记录改为
“已实施并纠偏”，不再以第一版通过。未调用模型、未提交合并。

### 纠偏 1：恢复范围由重建后的权威差异决定

- `writing_callback_fulfillment.py::_authority_delta_from_revision`：从**修订前/后持久产物**计算 typed 权威差异
  （claim 合同字段 `status/claim_kind/required_qualifiers/polarity/math_op_kind/covers_obligation_ids`
  变化即计入，detail 集合增量为补充，round 收集的 operation/fact 作为兜底），不再只用本轮新增 id。
- 闭包改用**重建后的 plan 与 narrative plan** 映射；`narrow_resume_sections` 语义修正为：
  目标不可映射 → `closure_unresolved_targets_blocked` 且调用方 `blocked`
  （`callback_resume_scope_unproven:*`）；闭包超出请求集合 → **扩展**恢复集（`closure_expanded`），
  不再静默保留较窄范围；子集才收窄。
- Writer 调用后核对**实际采用范围**：优先 `resumed_section_ids`，否则用产品自身的
  `_actually_regenerated_section_ids(writer_aggregate, ...)`；有证据且缺少闭包内 section →
  `callback_resume_scope_not_adopted:*` 阻塞；无证据时 `resume_scope_evidence="unavailable"`、
  `resume_scope_verified=False`，不把缺失遥测当作已验证。

### 纠偏 2：中断与预算失败关闭

- `_read_consumed_rounds` 返回 `(rounds, ok)`；记录损坏/不可解析时返回 blocked
  `callback_budget_record_corrupt`，不再读成 0 轮（那会静默重启预算）。
- 新增 `writing_callback_stage_state_v1.json`：四个阶段（initial/research_fulfilled/revision_rebuilt/
  writer_resumed）的身份（mode/source_context_digest/page_manifest_digest/contract_present）持久化；
  重入时从磁盘播种 `stage_identity`，记录损坏时 blocked `callback_stage_record_corrupt`。
- `read_all_completed_receipts(strict=True)`：完成回执损坏不再静默跳过（`unified_receipt_corrupt`），
  writer/realizer/formalizer 三处扣账都使用严格读取并分类为 `run_ledger_corrupt`。
- 新增 `unsettled_started_attempts(ledger_root, plan, exclude=...)`：已开始但无完成回执的调用按该
  invocation 的计划输入保守预留（当前正在测量的尝试除外），覆盖崩溃后无法证明未消费的区间。

### 纠偏 3：完整目标合同参与比较

- `_rewrite_target_contract_map` 把每个 `kind:id` 的完整合同（required_qualifiers/polarity/claim_kind/
  math_op_kind/authority_lanes，多 owner 时取排序并集）纳入判定；同一 ID 的合同变化返回
  `required_target_contract_changed:<id>:<fields>`，删 qualifier、翻转极性或降低 authority 不再算增益。
- 目标集合新增 section 级与 paragraph 级 `formula_obligation`（后者来自 narrative plan 的段落所有者），
  删除公式义务返回 `required_target_removed:formula_obligation:*`。
- 复现探针：删除同一目标 qualifier 且仅改善文风 → `required_target_contract_changed`；保持合同时的
  纯文风改善仍返回 `monotonic_cluster_gain`。

### 回归测试

- `tests/test_agentic_callback_dependency_closure.py`：权威差异覆盖合同变化、stage 记录往返与损坏、
  严格回执读取、未结算尝试预留（含 exclude 当前尝试）、闭包扩展/阻塞/收窄三态。
- `tests/test_agentic_rewrite_target_set.py`：同 ID 合同变化（qualifier/极性/authority）被拒、
  公式义务进入分母且删除被拒、纯文风增益仍通过。
- 既有 callback/continuation/writer/unified 用例继续通过（定向批次 `474 passed`）。

### 未完成/移交

- 计划顶部状态与实现记录已统一为 R8 已实施并纠偏；R9（搜索终态）与 R10（假设修订）尚未开始。
- 全量静态与冻结离线报告需在 R9/R10 后按 G3 重跑；R7 计划输入上界合计 1,938,180 / 2,000,000 tokens
  （formalizer 692,690＋writer 637,914＋realizer 607,576），重试余量需在真实请求计量校准后确认，
  不得以运行后校准代替预算约束。
- 配置选择证据（`self.cfg.use_dedicated_attention`）与入口路径外 `operation_disposition_unresolved`
  仍为 Research 证据缺口，继续标 NEEDS_RESEARCH_EVIDENCE。

## 2026-09-12：R9 搜索终态（三种结果、回执与兼容迁移）

按计划 §14 实施；同一 dirty worktree，未调用模型、未提交合并。R8 纠偏见上一节。

### 修改点

- `research_models.py` 新增 typed 合同：`SearchReceiptV1`（run/snapshot 身份、obligation、规范查询与
  过滤范围、top_k、截断状态、结果 IDs 与 digest、已读/未读候选、关系检查、工具失败、预算、停止原因；
  `frontier_closed()` 仅在“有查询、有读取、无未读、未截断、无工具失败”时为真）、
  `TerminalSearchDispositionV1`（三种 outcome 各自的必需证明：inconclusive 需查询/观察与停止原因；
  budget_exhausted 需预算与剩余 frontier/未完成任务；unsupported_with_scoped_evidence 需冻结 scope、
  scope basis 与至少一份关闭回执）、`TerminalSearchOutcome`。
- `GapRequirementV1` 新增 `terminal_outcome`/`terminal_record_only`/`negative_evidence_authorized`/
  `search_receipt`；`research_terminal.py` 的终态判定改为读取 typed outcome 与回执，
  **删除** notes 字符串嗅探（原 `bounded_search_exhausted` 文本不再构成 exhausted）；
  未带 typed 证书的 legacy `explicit_gap` requirement 读为未决并保留原始数据。
- `research_tools.record_explicit_code_gap`：完整负结论必须有可证明关闭的 `search_receipt`
  （否则 `gap_search_receipt_not_provably_closed`）；新增 `terminal_record_only` 明确“有界停止”通道，
  记录 `search_inconclusive`/`budget_exhausted` 且 `negative_evidence_authorized=False`；
  payload 增加 `terminal_outcome`/`terminal_disposition`/`search_receipt`/`negative_evidence_authorized`。
- `research_nodes.gap_finalizer_node`：不再声称 `search_complete=True`；记录 typed stop（
  `missing_information` 追加 `terminal_stop:<outcome>` 作为调度信号，且该标记不进入工具 payload，
  保持幂等重放）；只有回执授权的结论才把 agenda 置为 `explicit_gap`，其余保留状态。
  `research_graph` 的调度谓词识别 `terminal_stop:`（搜索结束但非负证据），循环以
  `all_obligations_terminal`/`intent_coverage_blocked` 等有界原因终止，不再空转到 `max_turns`。
- 既有 `TypedResearchGapV1.status=unresolved` 与 completeness matrix 的 `unverified_by_repository`
  现在承载这种诚实终态；Candidate/strict 的结果不被提升为负结论。

### 回归测试

- 新增 `tests/test_agentic_terminal_search_disposition.py`：回执关闭条件（未读/截断/工具失败/未读取）、
  三种 outcome 的必需证明、legacy `explicit_gap` 无证书读为未决、typed 证书下才 terminal。
- 更新 `tests/test_agentic_research_models.py`（完整终态证明现在需要 typed 回执）、
  `tests/test_agentic_research_no_progress.py`（有界停止而非 `explicit_gap`，不得空转到 max_turns）、
  `tests/test_agentic_autonomous_method_agent.py`（unverifiable claim → `unresolved` 与
  `unverified_by_repository`，不再产生 `explicit_code_gap`）。

### 未完成/移交

- R9 的“旧 checkpoint/coverage/plan/Writer 一起往返验证”与 handoff/admission 的显式版本分支仍需在
  G3 前补齐；本片已保证缺证书不回填“完成”。
- R10（假设修订、作者约束不可缩水）尚未开始。

## 2026-09-13：第二次方向复核 P1-A–P1-F 纠偏（R9 认证负证据、R5 结构条件、R7 分页/身份、R8 权威差异、R6 跨修订扣账）

按 [第二次方向复核报告](../docs/research_to_method_repair_direction_review_2026-09-13.md) 给出的顺序执行：
先阻断未认证负证据并修条件与分页，再统一章节身份，再补 callback 完整差异与跨修订扣账，最后做集成检查点。
同一 dirty worktree，串行修改；未调用模型、未提交、未合并、未降低任何门禁。

### P1-A：R9 负证据只能来自执行层回执

- 新增 `src/code2paper/agentic/research_execution_ledger.py`：`execute_research_tool` 在每次真实执行后把
  discovery/read/relation 执行写入 run 级 ledger（工具名、obligation、snapshot/tree、查询、path_scope、
  top_k、截断、结果 IDs、已读 ID/路径/行区间、关系检查、失败、`node_budget`），ledger 写失败会写 poison
  记录并让该次调用 `invalid_request`，避免“丢记录=缩小 frontier”。
- 新增 `close_search_frontier` 工具：由执行层从 ledger 派生 `SearchReceiptV1`（新增 `ledger_digest`、
  `execution_record_ids`、`authentication="ledger_verified"`）并落盘 `search_receipts/`，返回 receipt id；
  frontier 未闭合时同样落盘但 `search_frontier_closed=false` 并给出未读/截断/失败原因。
- `record_explicit_code_gap` 不再接受调用者填写的回执内容（`gap_search_receipt_content_not_evidence`），
  只接受 `search_receipt_id` 并 `authenticate_search_receipt`：重载持久回执、按记录前缀重算 ledger digest、
  要求与当前 ledger 派生结果一致（否则 `search_receipt_stale`）、校验 snapshot/tree/obligation 与
  scope 覆盖；只有认证且 `frontier_closed()` 才产生 `unsupported_with_scoped_evidence`，否则记录
  `search_inconclusive`/`budget_exhausted`。
- 消费者复用同一认证裁决：`research_terminal._negative_evidence_authorized` 改调
  `verify_receipt_authentication`，`_search_exhausted` 不再只看声明的 outcome 字符串；
  completeness matrix 的 `_load_terminal_gap_artifacts` 只把认证过的
  `unsupported_with_scoped_evidence` 记录转成 `ExplicitCodeGapV1`，有界停止保持 `unresolved`。
- `research_tool_manifest` 的 StructuredTool runner 改走 `execute_research_tool`（原先绕过 dispatcher）。

### P1-C：R5 条件授权改为结构判定

- 新增 `src/code2paper/agentic/condition_structure.py`：显式语法（括号、AND/OR、NOT 重数、带符号数字、
  有序比较、操作数词形），固定短语表处理 `is at least`/`does not hold`/`is enabled` 等读者措辞；
  声明的条件树与 witness 条件片段必须规范形完全一致，未知语法保持未证。
- `publication_transaction_contract` 删除词表/子句列表/正则授权器，改为调用同一实现；
  复核报告的五类反例（布尔重新分组、`-5`→`5`、`not not`→`not`、比较两端交换、`alpha`→`alpha or beta`）
  在 `_condition_statement_matches`、`_witness_condition_and_polarity_satisfied` 与真实 Binder/Writer
  transaction 路径均被拒绝，合法等价措辞仍绑定。

### P1-B/P1-E：R7 分页合同守恒、公式/unit 归属与章节身份

- `fit_narrative_plan_to_page_budget`：按 `target_kind` 解析归属（detail 用 `target_id`、atom 用
  `detail_id`）并双侧规范化 `detail:` 前缀；比较完整 target 合同多重集（丢失/重复/改写即
  `paragraph_split_target_contract_not_conserved`）；无法归属的 target 阻塞
  （`paragraph_split_target_unassigned`）。公式按义务原子闭包路由到真正拥有的 fragment，无法证明时
  `paragraph_split_formula_consumer_incomplete`，不再统一搬到 `__f1`；unit 只保留自己原有的段落经拆分后的
  fragment；placement 按 package→义务归属重定向。
- 调用方（`publication_method_writer`）传入编译后的 formula packages，并对修订后的 plan 重新执行
  `validate_narrative_plan`；validator 新增 `witness_target_detail_not_owned`（目标必须属于本段）。
- `build_narrative_plan_v3`：`_prior_section_owners` 作为统一身份合同用于“少于/等于/多于”三种数量关系；
  等于/少于分支不再按位置 `prior_sections[sec_idx-1]` 复用，而是按稳定 section ID 对照 owner，
  未证明的 owner 记入 `section_identity.owner_unproven` 与 `section_identity_failures`。

### P1-D：R8 真实权威差异与冻结 before revision

- `_authority_revision_snapshot` 在**重建前**冻结 claims（含 `fact_ids`）、details、operations、facts、
  equations、configurations、formula packages/obligations、detail→operation/fact/condition 归属；
  `_authority_delta_from_snapshots` 对比两份快照并报告 added/changed/**removed**；
  unit 归属对象（claim/equation/configuration）只把“变化或删除”计为失效，纯新增不当作失效。
- `compute_callback_dependency_closure` 支持 `previous_plan`/`previous_narrative_plan`/`target_owner_map`/
  `added_target_ids`：删除/降级的 detail 经旧 narrative plan 解析，fact 经 claim→unit 与 detail→fact 双图解析，
  operation/condition/formula 经 `target_owner_map` 解析；纯新增且无人拥有进入
  `unmapped_added_target_ids`（记录但不阻塞），变化/删除无法归属仍进 `unresolved_target_ids` 并阻塞。
- 复核探针结果：`config:shared` true→false 产生 `configuration_ids=["config:shared"]` 且闭包覆盖 MA-S1、
  MA-S2；删除 `claim:alpha` 产生 `claim_ids=["claim:alpha"]`。

### P1-F：R6 跨 revision 扣账

- 三处发送前扣账（Formalizer / Writer / Realizer）改为 run 级：不再按当前 plan digest 过滤回执，
  历史修订消费计入同一 reservation；`register_invocation_plan` 持久化每份计划的 invocation 预留，
  `unsettled_started_attempt_records` 对旧计划孤儿 started attempt 从**其原始计划记录**读取预留，
  无法计量时 `plan_source="unknown"`，调用方以 `run_reservation_unsettled_unmetered` 阻塞（不再按 0 计）。
- 冻结计划 1,938,180 / 2,000,000 的差额记为计划余量，不是已验证重试余量（写入证据摘要 notes）。

### R9 迁移

- `build_candidate_handoff`：legacy `explicit_gap`（无 ledger 认证证书）记为
  `candidate_legacy_explicit_gap_unverified:<obligation>`（eligibility reason + warning），保持 handoff 不合格，
  不再作为“已穷尽缺口”进入 Writer；`evaluate_obligation_terminal_proof` 继续读为未决。

### 验证

- 新增/扩展测试：`tests/test_agentic_execution_ledger_receipts.py`（未认证回执被拒、真实执行派生回执、
  未读/截断/陈旧/poison、消费者复用认证）、`tests/test_agentic_formalization_guards.py`（五类结构反例）、
  `tests/test_llm_section_writer.py`（真实 transaction 路径五类反例）、
  `tests/test_agentic_unified_context_compiler.py`（分页 target 多重集守恒、run 级扣账、孤儿 started attempt）、
  `tests/test_agentic_narrative_architect_v3.py`（等量反序 outline 身份）、
  `tests/test_agentic_callback_dependency_closure.py`（配置变化/删除 claim/旧图解析/同路径重建快照）、
  `tests/test_agentic_candidate_handoff.py`（legacy gap 迁移）。
- 全量静态：`python -m pytest -q tests/ -p no:randomly` → `3366 passed, 3 skipped`（2026-09-13，当前代码）。
- 冻结 Run E 离线链（当前代码）：`.tmp/c2p-unified-repair-20260913-r9/offline/offline-ebcar-r9.json`，
  `model_calls_allowed=false`；source pass（rehydrate 同仓库）、archive `sha256:6b2ec29d…`（887 atoms）、
  131 页 / 4 worksets（duplication 1.0812）、三 phase 计划 65/18/18 均编译、
  `failure_details=[]`，admission 仍失败于 2×`operation_disposition_unresolved` 与
  3×strict `core_intent_partial_without_terminal_gap`；Candidate handoff eligible。
  代码身份与逐 phase 数据见 `.tmp/c2p-unified-repair-20260913-r9/offline/r9-summary.json`。
- 复核探针（脚本原样重跑）：`.tmp/r9-probe/review-probes-after.json` —— 五类条件反例全部拒绝；
  分页 6 targets → 2+2+2 且 `fit_failures=[]`；未执行搜索 → `invalid_request` 且 `terminal_gap=null`；
  反序 outline 的 heading 与 owner 一致。

### 未完成/移交

- R7 的“自主组织（proposal caller 仅记 `narrative_proposal_not_consumed`）”与同机制多章节的论证意图仍未闭环。
- R9 旧 checkpoint→coverage→handoff→Writer 已补 legacy 分支与调度读法，但完整往返验证仍需在 G3 中固化。
- R10（假设修订、作者约束不可缩水）未开始；真实模型与 live 仍需既有授权与准入前置。
- Research 证据缺口（配置选择、入口路径外 operation disposition）继续标 NEEDS_RESEARCH_EVIDENCE，
  不以调分页或阈值消除。

## 2026-09-13（续）：R7 自主组织提案消费 + R9 迁移往返验证

承接上一节的未完成项，仍在同一 dirty worktree；未调用模型、未提交合并、未降低门禁。

### R7：narrative organization 提案被真正消费

- `method_architect` 新增 `NARRATIVE_PARAGRAPH_ROLES` / `NARRATIVE_PARAGRAPH_DETAIL_LIMIT`、
  `_call_narrative_proposal`（保留原四位置参数并追加 `kind="narrative_organization"`，兼容旧 caller）、
  `_bounded_narrative_organization_proposal` 与 `_validate_narrative_organization_proposal`。
- 合同：提案只能对**本机制自己的** clean detail id 做分组，角色必须取自封闭集合，每个 clean detail
  必须恰好出现一次（组内重复与跨组重复都拒绝），单组 ≤8，机制 id 必须匹配；失败重试一次后记录
  typed failure（`narrative_proposal_unknown_detail`/`duplicate_detail`/`detail_unplaced`/
  `unknown_role`/`group_too_large`/`paragraphs_missing` 等）并回退确定性分组。
- `build_narrative_plan_v3`：提案通过后替换该机制的 paragraph 分组（review-only detail 仍留在
  `evidence_status` 段），trace 记 `proposal_status ∈ {accepted, partially_accepted, not_accepted}`、
  `proposal_applied`、`proposal_accepted_mechanism_ids`；未消费时仍记
  `narrative_proposal_not_consumed`。plan 仍要过 `validate_narrative_plan`，因此分组回归会导致构建失败。

### R9：旧 checkpoint→coverage→handoff→Writer 往返验证

- 新增往返测试：legacy `explicit_gap`（无认证证书）→ `build_candidate_handoff` 记
  `candidate_legacy_explicit_gap_unverified:<obligation>` 且不合格 → Writer 端
  `_writer_research_preadmission_failures` 报 `unified_core_intent_terminal_proof_missing:<obligation>`，
  证明旧 gap 既不会进入 handoff 的 supported/partial 集合，也不会在 Writer 预准入被当作已终态。

### 验证（本轮）

- `tests/test_agentic_narrative_architect_v3.py`：合法提案 → `accepted` 且每个 clean detail 恰好落一段；
  五类非法提案（未知 detail、重复 detail、丢 detail、未知 role、超限组）→ `not_accepted` +
  typed failure + 确定性回退且 plan 校验通过。
- `tests/test_agentic_candidate_handoff.py`：legacy gap 往返链路。
- 全量静态与冻结 Run E 离线链在本轮结束前重跑（见 §G3 证据与
  `.tmp/c2p-unified-repair-20260913-r9/offline/`）。

### 仍未完成

- R7 的 multi-section（prior outline 多于机制）分支尚未消费组织提案，仅记录未消费；同机制多章节的
  论证意图分摊仍是下一片的工作。
- R10 未开始。

## 2026-09-13（续二）：R7 multi-section 组织提案消费（收尾）

上一节记录的“multi-section 分支仅记录未消费组织提案”已补齐；同一 dirty worktree，未调用模型、未提交合并。

### 修改点

- `method_architect` 新增 section 级封闭提案合同：`_call_section_proposal`、
  `_validate_section_organization_proposal`、`_bounded_section_organization_proposal`
  （`kind="section_organization"`，兼容旧四位置参数）。
- 合同要求：只允许该机制**已证明拥有**的 section id 与它自己的 detail id；每个 section 恰好出现一次且
  非空，每个 detail 恰好出现一次（组内/跨组重复、未知 id、丢失 id、未分配 section 都拒绝）；
  detail 数少于 section 数时直接回退（`section_proposal_insufficient_details`），避免空论证章节。
  失败重试一次后记录 typed failure 并回退到确定性按数量分摊。
- 旧 outline 多于机制的路径（`count > 1`）现在：提案通过 → 每个 section 的 detail 集合由提案决定
  （trace 记 `proposal_applied[kind=section_organization]` 与 `proposal_accepted_mechanism_ids`）；
  未通过 → 保留原 count 分摊并记录失败原因。

### 验证

- 新增测试：合法提案使“3 details / 2 sections”从确定性 `[1,2]` 变为提案的 `[2,1]`，
  且 plan 仍过 `validate_narrative_plan`；非法提案（未知 section）→ `not_accepted` +
  `section_proposal_unknown_section` + 回退 `[1,2]`。
- 全量静态与冻结 Run E 离线链在本轮重跑（见下）。

### 仍未完成

- R10（假设修订、作者约束不可缩水）仍未开始（按你的指示暂缓）。
- 组织提案目前只覆盖“同机制多章节的 detail 归属”和单机制段落分组；跨机制的章节顺序提案尚未开放
  （当前顺序仍由 author intent/story spine 决定）。
- 真实模型与 live 仍需授权与准入前置；配置选择与入口路径外 operation disposition 仍为 Research 证据缺口。

## 2026-09-13（第三次复核 P1/P2 纠偏）

按 [第三次方向复核报告](../docs/research_to_method_repair_direction_review_2026-09-13_round3.md) 的顺序修正两个授权边界
（P1-A/P1-B）与两个集成点（P2-A/P2-B），并补一个固定范围的离线集成检查点；未调用模型、未提交合并。

### P1-A：执行账本完整性与重放身份

- `research_execution_ledger` 新增 `ExecutionLedgerError`/`ExecutionLedgerIntegrityError`/
  `ExecutionLedgerReplayMismatch` 与追加式 `_index.json` 清单（record_id → content_digest）。
- 读取：记录不可读/不可解析/`content_digest` 与实际内容不一致/被改写、索引缺失、索引与文件不一致、
  记录缺失（清单有而目录无）一律抛 typed 错误；`iter_execution_records`、`derive_frontier_receipt`、
  `authenticate_search_receipt` 全部 fail-closed，不再 `continue` 跳过。
- 写入：同一 `tool_call_id` 只在 snapshot/obligation/工具/参数/结果/读取集合完全一致时视为合法重放；
  同 ID 不同执行内容抛 `ExecutionLedgerReplayMismatch`，dispatcher 返回 `invalid_request`，
  不写 poison、不返回旧记录；其他账本错误同样以 `research_execution_ledger:<reason>` 拒绝。
- 消费：`verify_receipt_authentication` 可接 `ledger_reader` 复核；gap 工具把账本完整性问题记为
  `gap_search_ledger_integrity:*`；`close_search_frontier` 记 `search_ledger_integrity:*`。

### P1-B：完整条件结构

- `condition_structure` 重写词法：`* / + - % ** //`（含一元正负号）、`!`、括号、索引/属性标点全部进入结构；
  未识别字符产生 `SYNTAX` 单元并使解析失败（不再有“未消费语法被静默丢弃”）。
- 语法扩展为 `or/and/not` + 比较 + 算术链（`+ - * / % ** //`）+ 属性/索引操作数；操作数与运算符顺序、
  数字符号、否定重数都参与规范形比较（`x * y > 5` ≠ `x / y > 5`，`x + y > 5` ≠ `x - y > 5`）。
- witness 片段守卫改为：被匹配片段之外的任何 `JOIN/NEG/OP/UNCOND/SYNTAX` 都判失败，
  因此 `When beta or when alpha, ...` 不再为 `alpha` 授权。
- 合法 guard 恢复：`x.shape[0] > 0` 与同形 witness 现在绑定（此前因标点被丢弃而误拒）。

### P2-A：同 invocation 的旧 attempt 用原计划额度

- `unsettled_started_attempt_records`：先核对 started marker 的 `plan_digest`；与当前计划一致才用当前额度，
  否则从其原始计划记录读取；marker 无计划身份或原计划记录缺失 → `unknown`（调用方阻塞），不再默认取当前额度。

### P2-B：默认产品入口接通提案并回传修复诊断

- 新增 `src/code2paper/agentic/narrative_organization_proposal.py`：默认、受角色配置约束的提案 caller
  （无 provider key → 返回 None，离线路径保持 `not_requested`）；prompt 携带机制意图/阅读问题/角色与
  各 detail 语义投影，响应走封闭 schema；记录 request digest、input payload、响应摘要与错误。
- `build_narrative_plan_v3` 在 `proposal_caller is None and llm_config` 可用时构造默认 caller；
  trace 记 `proposal_default_caller`、`proposal_attempts`/`proposal_attempt_count` 与
  `proposal_call_accounting=recorded_not_in_invocation_plan`（这些调用尚未计入 unified invocation plan，
  真实计量时需并入账本）。
- 提案重试把首次 typed failure 作为 `repair_failures` 回传（prompt 与 input_payload 都带诊断）；
  `proposal_llm_caller` 作为产品 wrapper 的传输注入点（`run_publication_method_writer` → 叙事构建）。
- `autonomous_method_agent` 的 `architect_proposal_caller=None` 注释明确：None 表示“由 llm_config 构造默认
  caller”，不是跳过提案。

### 固定范围离线集成检查点

- 新增 `tests/test_agentic_third_review_integration.py`：执行记录→回执→gap→终态证明（含损坏账本、
  删除记录、陈旧回执拒绝）；组织提案→NarrativePlan→分页/Writer 行投影；跨修订预算（900 vs 100）。
- 另加：P1-A 账本完整性与重放测试 5 项、P1-B 第三轮条件反例/合法对照、P2-A 同 ID 跨修订额度、
  P2-B 默认入口与修复回传测试。此检查点是固定范围验证，不宣称完整 G3 或 live 验收。

### 验证

- 全量静态：见下一节“验证记录（当前代码）”；`compileall`、`git diff --check` 通过。
- 自建验收探针 `.tmp/r9-probe/third_review_check.py`（模型调用 0）：四项发现全部按预期拒绝/通过，
  结果存 `.tmp/r9-probe/`。第三方探针脚本本身在损坏账本处按设计抛出 integrity 错误（不再静默跳过）。

### 验证记录（当前代码）

- 命令：`python -m pytest -q tests/ -p no:randomly`；结果：`3384 passed, 3 skipped`（2026-09-13，exit 0）。
- 命令：`python -m compileall -q src tests`；`git diff --check`；均 exit 0。
- 代码身份：`git rev-parse HEAD` 与 18 个生产文件 sha256 记于
  `.tmp/c2p-unified-repair-20260913-r9/offline/r9-summary.json`（`code_state`）。
  早先记录的 3366/3371 计数对应更早的代码状态，此后每次变更都以本节命令重跑并以该摘要绑定；
  本文件不再以“见下”指代其它计数。
- 冻结 Run E 离线链（当前代码，`model_calls_allowed=false`）：archive `sha256:6b2ec29d…`（887 atoms）、
  131 页/4 worksets（duplication 1.0813）、Formalizer/Writer/Realizer 65/18/18 均编译、
  `failure_details=[]`；admission 仍为 2×`operation_disposition_unresolved` +
  3×strict `core_intent_partial_without_terminal_gap`；Candidate handoff eligible。
- 第三方探针：`.tmp/c2p-direction-review-20260913-round3/review_probes.py` 现在会在其“损坏账本”步骤
  按设计抛出 `ExecutionLedgerIntegrityError`（不再静默跳过），因此该脚本自身 exit 非 0；
  同一场景的验收结果由 `.tmp/r9-probe/third_review_check.py` 记录（模型调用 0）。

## 2026-09-13（第三次复核 §5 边界收尾）

按第三次复核报告 §5 修正两处 R9 生产边界、补齐 5.4 的下游验收，并修正提案 trace 的请求身份字段。

### 5.1 重放身份改为执行前核对 + 冲突持久状态

- 新增 `check_execution_call_identity(ctx, tool_call)`：在 executor 之前用 snapshot/obligation/工具/
  查询/path_scope/top_k 的请求投影与已有记录比对；不同即返回
  `execution_ledger_replay_mismatch_pre_execution:<call_id>:<record_id>`，**该请求不进入 executor**。
- 新增 `record_ledger_conflict(...)` 与 `<hash>.conflict.json`：若执行已经发生但记录无法提交
  （同请求不同结果），写入阻断记录（`status=ledger_conflict`、`tool_failure=execution_ledger_conflict:*`、
  `truncated=true`）并登记索引，使 `frontier_closed()` 保持 false，直到以新 call id 重做搜索。
- dispatcher 相应调整：执行前冲突直接拒绝；执行后冲突记 conflict 再拒绝。

### 5.2 终态消费者接入账本重验

- `research_terminal`：`evaluate_obligation_terminal_proof(..., receipt_verifier=None)` 新增适配器参数，
  贯穿 `_terminal_gap_bound`/`_negative_evidence_authorized`/`_search_exhausted`；
  **没有适配器时负证据读为未证**（不再仅凭存储的 `ledger_verified` 标记）。
- `research_execution_ledger.build_context_ledger_reader(ctx)`：返回用当前 revision 账本重新认证的
  适配器；`verify_receipt_authentication(..., ledger_reader=...)` 现在校验**身份一致**
  （receipt_id/content_digest/obligation/snapshot），不只是“非 None”。
- 生产消费者接线：`autonomous_method_agent._load_terminal_gap_artifacts`（由 runtime 构造 reader，
  损坏/删除/陈旧即不接受）、`publication_method_writer._writer_research_preadmission_failures`
  （由 terminal gap 路径推导 research 数据面 ledger root）、`research_graph` 调度
  （`_next_loop_obligation` 从 runtime 构造 reader；`explicit_gap` 必须能重认证才结束搜索，
  否则继续占用调度槽）。

### 5.3 提案 trace 请求身份（预算接线留待计量片）

- `_request_identity(request)` 读取真实属性 `input_hash`；trace 同时写
  `request_input_hash` 与兼容键 `request_prompt_digest`（同一值），并记录 `planned_input_tokens`。
- 统一预算接线（invocation reservation、发送前计量/扣减、started/completed receipt）仍按计划与
  tokenizer 校准合并执行；`proposal_call_accounting=recorded_not_in_invocation_plan` 继续如实标注。

### 5.4 集成检查点补到分页与真实 Writer 请求

- `tests/test_agentic_third_review_integration.py` 新增：
  提案 → NarrativePlan → `fit_narrative_plan_to_page_budget`（真实触发拆分）→
  `extend_writer_worksets_from_narrative_plan` → `build_consumer_invocation_plan_v1` →
  `_writer_section_inputs_v2`，并对**实际 Writer 请求 payload**断言：
  段落 detail 多重集守恒、每个 fragment 的 witness target 归属正确、
  完整 target 合同（6 个，含 `required_conditions`/`authority_lane`）进入 `binding_contract.detail_witness_contracts`。

### 验证（本轮）

- 全量静态：`python -m pytest -q tests/ -p no:randomly` → `3387 passed, 3 skipped`（exit 0）。
- 复核脚本 `.tmp/c2p-post-round3-verification-20260913/verify_boundaries.py` 重跑（exit 0）：
  `executions_before_rejection=[]`（执行前拒绝）、`loaded_explicit_gap_count=0`、
  `terminal_after_corruption=false`、`trace_request_digests` 与真实 `input_hash` 一致。
- 冻结 Run E 离线链：archive `sha256:6b2ec29d…`、131 页/4 worksets、65/18/18、`failure_details=[]`，
  五个准入失败码未变（`model_calls_allowed=false`）。
- 新增 `docs/research_evidence_checklist_2026-09-13.md`：五个失败码与配置证据缺口的补证清单
  （当前证据/缺失内容/允许查询范围/结束条件，以及负证据回写须先满足 R9 完整链路）。


## 2026-09-13：R10（§15）研究假设可修订、作者约束不可缩水

按统一执行计划 §15 实施；同一 dirty worktree，未调用模型、未提交合并。远端
``revision_reason`` 放行删除目标的规则未采纳。

### 合同（新增 `src/code2paper/agentic/research_revision_contract.py`）

- **来源类别**：`TargetProvenanceV1 = author_explicit | system_inferred | research_subquestion | unproven`；
  只有 `system_inferred` 可被替换/删除，作者显式约束与**无法证明来源的旧记录**都不可删除
  （`DELETABLE_PROVENANCE`）。`TypedBehaviorTargetV1` 新增 `provenance` 字段并进入 intent graph 摘要；
  `intent_compiler_v2._build_typed_targets` 标 `author_explicit`，`intent_target_proposer._normalize_target`
  标 `system_inferred`。
- **作者边界独立保存**：`AuthorConstraintSetV1`（goal/约束文本、target ids、必需 predicates/relations/
  conditions，内容寻址）；`build_author_constraint_set(graph)` 在提案之前捕获，
  `non_deletable_target_ids(graph)` 给出不可删除集合与覆盖分母。
- **只提案**：`RevisionProposalV1`（父 obligation、before/after target ids、来源类型、精确 observation/
  relation refs、原因、未决影响、预算；`extra="forbid"`，且 revision target 不能自称 `author_explicit`），
  无 status/authority 字段。
- **Harness 校验**：`assess_revision_proposal` 检查身份（重算 revision_id，伪造即
  `revision_forged_identity`）、父归属、来源（`unproven` 拒绝）、before 目标归属、
  跨 obligation 目标窃取、删除规则（作者/旧记录 → `revision_author_constraint_deleted`）、
  在**结果图**上做作者谓词/关系/条件守恒（含 `revision_generic_substitution`）、
  证据引用必须精确且已被观察、reason-only 拒绝、预算、子问题 parent、重复 resume；
  对作者目标的原地改写需要**独立**语义复核（无复核 → `pending_review`，复核失败 → rejected）。
- **原子应用与 journal**：`apply_revision` 通过模型构造器重建 graph（`model_copy` 会跳过摘要校验），
  只删除可删除来源的目标；`RevisionJournalEntryV1` 绑定改动对象摘要、覆盖分母、新增/删除目标、
  handoff 失效标记；`RevisionJournalV1` 拒绝重复应用并提供 `handoff_is_current`。
- **绑定工具**：`REVISION_BOUND_OBJECT_KEYS`、`object_digest`、`build_object_digests`、
  `missing_bound_objects`（§15.6 的 agenda/intent graph/coverage/claims/promotion/handoff/checkpoint/
  authoring plan 一起绑定）、`write_revision_journal`/`load_revision_journal`（输出名
  `research_revision_journal_v1`）。
- **接线**：`CandidateHandoffV1.revision_id` + `handoff_matches_revision`；
  `_writer_research_preadmission_failures` 在存在 journal 时拒绝 `research_revision_handoff_stale`；
  `persist_product_artifacts(..., revision_journal=...)` 把 journal 写入同一 artifact map。

### 测试

- 新增 `tests/test_agentic_research_revision_contract.py`（13 项）：允许推断层修订（含子问题独立预算）、
  拒绝删除作者约束/仅填 reason/未观察 span/错误 parent/伪造 revision/预算耗尽/重复 resume/
  跨 obligation 窃取/未证明来源删除/泛化谓词替换，作者边界复核不能自签（pending→独立复核），
  被拒修订不改变 graph 与分母，对象摘要绑定 + journal 往返，旧 handoff 在新修订下不可用，
  Writer 预准入拒绝陈旧 handoff。
- 扩展 `intent_target_proposer._apply_proposal` 的守恒检查：除 predicates/relations 外，
  作者侧 conditions 与 inputs 也不得在富化时丢失。
- 全量静态与冻结 Run E 离线链在本轮重跑（见验证记录）。

### R10 验证记录（当前代码）

- 命令：`python -m pytest -q tests/ -p no:randomly` → `3401 passed, 3 skipped`（exit 0）。
- 命令：`python -m pytest -q tests/test_agentic_research_revision_contract.py` → `14 passed`。
- `python -m compileall -q src tests`、`git diff --check` 均 exit 0。
- 冻结 Run E 离线链（当前代码，`model_calls_allowed=false`）：887 atoms、131 页 / 4 worksets、
  Formalizer/Writer/Realizer 65/18/18 编译、`failure_details=[]`；五个准入失败码未变；
  Candidate handoff `eligible` 且重验失败为空。archive digest 由 `6b2ec29d…` 变为 `58ad15ef…`：
  这是 intent graph 新增 `target_identity_digest` 字段带来的 schema 身份变化（atom/页/workset 与失败码不变）；
  旧 agenda/handoff 通过 legacy 摘要读法与 normalized handoff identity 保持可读（本轮实测）。
- 代码身份与 21 个生产文件 sha256 记于 `.tmp/c2p-unified-repair-20260913-r9/offline/r9-summary.json`。

### R10 仍未完成（下一片）

- supervisor/loop 侧的 revision proposal **生产**尚未接线（合同与 harness 已就绪，但没有真实提案调用点）。
  （已被本文件更晚小节取代：R10 第三片接入 `PROPOSE_TARGET_REVISION` 动作与 `propose_target_revision` 工具，并有产品路径端到端链路测试。）
- 新目标下 coverage/claims 适用性重算与 promotion/handoff/retry 的联动仍需按 §15.6 接完；
  journal 已能绑定并拒绝重复 resume，但 resume 路径尚未读取它。

## 2026-09-13（R10 第二轮）：实时修订应用、适用性重算与 resume 绑定

承接 R10 合同层，补齐 §15.6 的“同一 revision 下原子绑定 + 旧事实重新评估 + resume 不重复应用”。

### 修改点

- `research_revision_contract`：
  - `revise_research_targets(runtime, proposal, ...)`：单一路径的实时应用——从 runtime 的 intent graph 捕获作者约束、
    harness 评估、`apply_revision` 原子应用，然后**重新评估适用性**：目标变更的 obligation 用冻结事实
    (`align_target_to_facts`) 重新对齐，未解析目标/覆盖该 obligation 的 claim 会清空 `supported_claim_ids`、
    状态回 `in_progress`，并写入 `revision_revalidation_required:*`、`revision_target_unresolved:*`、
    `revision_claim_revalidation_required:*` 标记；未触及的兄弟 obligation 保持不变；
  - journal entry 通过构造器重建，绑定最终对象摘要（intent graph content/target identity、agenda、binding digest）；
  - `ResearchRevisionBindingV1` + `bind_research_revision` + `revision_resume_failures`：revision id、journal digest、
    intent graph/target identity/agenda digest、覆盖分母一起绑定；重复应用同一 revision、绑定陈旧、journal/graph/
    agenda 漂移都产生 typed failure；
  - `build_revision_proposal` / `build_subquestion_target`：确定性生产者与 LLM 提交同一 proposal 形态；
    子问题谓词必须来自注册词表且在证据图中被观察到。
- `autonomous_method_agent`：`persist_research_stage_checkpoint(..., revision_binding=...)` 把绑定量写入 checkpoint；
  `load_research_stage_checkpoint(..., revision_journal=...)` 在恢复前调用 `revision_resume_failures`（对照
  checkpoint 内的 agenda 对象），失败抛 `research_stage_checkpoint_revision_stale:*`。

### 测试与验证

- `tests/test_agentic_research_revision_contract.py` 扩到 **18 项**：新增实时应用与适用性重算、resume 绑定
  （重复应用/陈旧/漂移/正常四态）、checkpoint 绑定 + replay/stale 拒绝、确定性生产者与子问题谓词约束。
- 全量静态：`python -m pytest -q tests/ -p no:randomly` → `3405 passed, 3 skipped`；`compileall`、`git diff --check` 通过。
- 冻结 Run E 离线链：887 atoms、131 页 / 4 worksets、65/18/18 编译、`failure_details=[]`、五个准入失败码未变、
  Candidate handoff `eligible` 且重验为空。

### R10 仍未完成（下一片）

（历史快照：本节两条其后已由 R10 第三/四片完成，见更晚小节。）

- supervisor/loop 协议侧：把 `RevisionProposalV1` 作为 supervisor 的一种提案动作接线（当前 ingestion 入口
  `revise_research_targets` 与生产者已就绪，但循环决策尚未提交提案）。
- promotion/handoff/retry 在新 revision 下的联动读法（handoff 陈旧拒绝已实现；promotion ledger 与 retry 计数
  尚未随 revision 重算绑定）。

## 2026-09-13（R10 第三轮）：循环提交路径 + 第四次复核的四项跨阶段边界

第三轮先把提案提交接入真实循环（`PROPOSE_TARGET_REVISION` 动作 + `propose_target_revision` 工具 +
harness 摄取），随后按 [第四次方向复核报告](../docs/research_to_method_repair_direction_review_2026-09-13_round4.md)
修正该接线暴露的四个跨阶段缺陷。

### 修改点

- **循环提交路径**：`research_revision_ingest.py` 新增提交存储（内容寻址的 `target_revision_proposals/<sha256>.json`）、
  账本认证的已观察引用集合、harness 摄取（`ingest_revision_submissions`）与摄取结果落盘；
  `research_tools.propose_target_revision` 只写提交信封（`source_authority=semantic_hint`，永不报告接受）；
  supervisor 侧新增 `PROPOSE_TARGET_REVISION` 动作（词表 17 项）并在 `_MODEL_TOOL_TO_ACTION` / ready_tools /
  硬规则中暴露；`research_graph` 的两个循环实现（LangGraph 子图与 `ResearchLoopDriver`）在同一工具边界摄取，
  并把 `revision_journal` / 摄取结果 / 失败写到 `ResearchLoopResult`；产品路径把 journal 写入 checkpoint 与
  `research_revision_journal_v1` artifact，并给 Candidate handoff 盖上 revision id。
- **P1-A 作者边界冻结**：`build_author_constraint_set` 现在在**提炼之前**捕获每个作者目标的完整需求载荷与
  obligation 级需求（谓词/关系/条件/输入/变换/决策/输出/槽位种类）；`ResearchGraphRuntime.author_constraints`
  承载该冻结边界并随 checkpoint 传递（恢复时 digest 不一致即拒绝）；`assess_revision_proposal` 的守恒检查
  改为对照冻结边界（不再从可变图重建作者权威），并新增逐目标守恒（`revision_author_target_dropped`）。
  合法提炼把承载作者需求的目标标记为新的 `author_derived` 来源（仍可识别为推断层，但不可删除），
  未注册谓词由工具侧拒绝（`PROPOSABLE_PROVENANCE`）。
- **P1-B graph/agenda 同步**：`_revalidate_after_revision` 在同一事务内把修订后的目标**载荷**写入 agenda item，
  并在提交摘要与 journal 之前逐 obligation 校验 graph 与 agenda 目标逐字一致
  （不一致返回 `revision_agenda_target_mismatch:*`，不写 journal、不改 runtime）。
- **P2-A 预算分离**：新增 `DEFAULT_REVISION_RESEARCH_ALLOWANCE`；harness 的**修订次数**每次应用固定计 1，
  且从 append-only journal 推导（`min(调用方值, 3 - 已应用数)`），resume 不重置；提案的 `budget_requests`
  只作为子问题研究额度申请，单独计费并在 journal entry（`requested_budget`/`application_charge`）留痕。
- **P2-B 词表与相关性**：`assess_revision_proposal` 校验谓词/关系词表（`revision_predicate_unregistered`、
  `revision_relation_unregistered`）；`cited_predicate_support` 从运行中的 behavior graph 与冻结快照上同一抽取器
  建立“引用 → 已抽取谓词”索引，新增谓词若无任一被引证据支持则转 `pending_review`
  （`revision_ref_unsupportive` / `revision_predicate_unsupported`），未知 parent 在摄取前置拒绝。

### 测试与验证

- `tests/test_agentic_revision_proposal_loop.py` 扩到 **22 项**：提交工具（幂等/冲突/越权父级/作者来源）、
  摄取（认证引用、预算、replay、零预算绕过、额度分离、resume 不重置）、
  跨阶段不变量（提炼前后作者分母守恒与删除拒绝、修订后 agenda/graph 载荷一致、真实 `compile_candidate_node`
  按修订后目标对齐（spy 记录 `align_target_to_facts` 入参）、词表/相关性/错误父级/未读引用四类反例 + 合法对照、
  promotion ledger 重算与 retry 计数重置）。
- 复核探针复跑：`.tmp/c2p-r10-direction-review-20260913/results.json`（`model_call_attempts=0`，`probe_errors={}`）：
  P1-A 3→3 受保护目标、删除拒绝；P1-B graph==agenda；P2-A 四个零预算提案全部
  `revision_application_budget_exhausted:0/3`；P2-B 未注册谓词 `rejected`、已读无关引用 `pending_review`。
- 全量静态：`python -m pytest -q tests/ -p no:randomly` → `3429 passed, 3 skipped`；
  `python -m compileall -q src tests`、`git diff --check` 通过。
- 离线证据在本检查点重新派生：`.tmp/c2p-unified-repair-20260913-r10/offline/offline-ebcar-r10.json`
  与 `python .tmp/c2p-unified-repair-20260913-r10/build_summary.py` 生成的 `r10-summary.json`
  （24 个绑定文件 + 报告 sha256 同源）。报告与第三轮 payload 逐字节一致：archive `58ad15ef…`、887 atoms、
  131 页/4 worksets、formalizer/realizer/writer = 65/18/18、`failure_details=[]`、五个准入失败码不变；
  该轮 R10 改动未影响冻结链的分页/准入结果。`model_calls_allowed=false`，未启动 live。

### R10 仍未完成（下一片）

- 五个 Research 缺口的逐项补证：两个 mechanism 分解到具体 unresolved operation，三个 obligation 分解到
  未满足 targets，逐项记录入口/配置/关系证据、查询范围、读取与未读 frontier、回执、停止原因与 disposition；
  现有 `docs/research_evidence_checklist_2026-09-13.md` 仍主要是执行要求，未构成补证结果。
- 提案实际调用计量：完整请求的 planned/reserved/measured/spent/unsettled 全链（含失败尝试、retry、恢复）
  与绑定实际模型和完整序列化请求的 tokenizer 校准。

## 2026-09-13（Research 补证首片）：五缺口分解 + 三个未 resolved target 的首轮定向检索

第四次复核把“五个 Research 缺口逐项补证”列为跨阶段修复之后的下一片。本片完成其中的**分解**与
**首轮定向检索**，并把结果落成可复核文档，未做任何模型调用。

### 产物（全部由脚本派生，非人工转录）

- `.tmp/c2p-gap-evidence-20260913/decompose_gaps.py` → `gap-decomposition.{json,md}`：
  从冻结 Run E 的 `obligation_coverage_v2.json`、`mechanism_context_completeness_v1.json`、
  `intent_obligation_graph_v2.json` 与离线报告派生。
- `.tmp/c2p-gap-evidence-20260913/probe_unresolved_targets.py` → `unresolved-target-evidence.json`：
  用生产研究工具的确定性层（`search_code`/`read_code_span`/`close_search_frontier` + R9 账本）
  在冻结 EBCAR 快照上检索三个未 resolved target。
- `.tmp/c2p-gap-evidence-20260913/render_evidence_doc.py` → `docs/research_gap_evidence_2026-09-13.md`。

### 结果

- 两个 mechanism：离线重算码为 `operation_disposition_unresolved`，运行记录只留下
  `core_detail_active_path_unknown:detail:mech_sym:f6cf5bdfe2ae16f0:22`；逐 operation 清单需在
  `artifacts/06_authoring/mechanism_context_set_v1.json` 上重跑 completeness 编译器，**未完成**。
- 三个 strict obligation：`O-METHOD-MAINLINE-01-c8146479` 8 个 target 中 2 个未 resolved
  （`FILTER`/`MASK`、`CALL`/`COMPUTE` 的 partial），`O-STAGE-03-2c5bd758` 3 个中 1 个未 resolved
  （`FILTER`/`MASK`），`O-STAGE-01-039a963a` coverage=supported 且 0 个未 resolved
  → 其 strict 失败不是 target 证据缺口，须在 claim/qualifier 侧定位（不得编造 target 缺口）。
- 首轮检索取得有界正向线索：`src/model/transformer_encoder_hybrid_attention.py:45/51/104/113`、
  `src/model/ebcar_dedicated_attention_model.py:139-167`、`main.py:34`、
  `data/real/MS_MARCO_v2/preprocess.py:51-76`，并读取了部分 span；`close_search_frontier` 三个 target
  都给出账本回执（`receipt:9ac3b9003feaa083` / `receipt:96f17be405a3df00` / `receipt:7ba3556e345449ac`），
  但 `search_frontier_closed=false`（`mask` 检索截断、命中未读完）
  → 按 R9 规则三个 target 保持 `unresolved`，不写负结论。

### 下一步

1. 读取剩余命中并把候选 span 交给确定性证据编译（packet→facts→claims），或在读完后取关闭回执；
2. 在 `mechanism_context_set_v1.json` 上重跑 mechanism completeness，列出未处置 operation；
3. 在 claim/qualifier 侧定位 `O-STAGE-01-039a963a` 的 strict 失败；
4. 配置选择证据（definition span / 入口绑定 / override chain）；
5. 提案调用计量与 tokenizer 校准（`proposal_call_accounting=recorded_not_in_invocation_plan`）。

## 2026-09-13（R10 第四片）：产品路径端到端修订链路 + 计量缺口定位

### 新增：产品路径（`run_autonomous_method_agent`）的端到端修订链路测试

`tests/test_agentic_revision_proposal_loop.py::test_product_run_applies_a_revision_and_carries_it_to_every_artifact`
用一个“像真实 manager 一样”的 supervisor（在**同一次决策**里先 `read_symbol` 再提交引用该 span 的提案，
谓词取自运行自己抽取器的支持集）跑完整产品入口，验证修订确实贯穿每个下游产物：

- 真实读取把 span 写入 R9 执行账本 → 摄取用账本认证引用（跨 obligation 或未读引用都会被拒）；
- 修订落到持久化的 `intent_obligation_graph_v2`（新 target 在冻结图 dump 中）；
- `research_revision_journal_v1` artifact 存在且 entry 记录 `applied_target_ids` 与非空覆盖分母；
- checkpoint 的 `research_revision_binding_v1.revision_id` 与 journal 当前修订一致，
  `revision_ingest_outcomes[0].status == "applied"`；
- `candidate_handoff_v1.revision_id` 等于同一修订（旧 handoff 不可复用）。

该测试连续三次通过；与既有的 compiler-spy、checkpoint/resume、预算与词表/相关性反例一起，
构成第四次复核 §7.3 要求的“提炼 → 提交 → 接受/拒绝 → 实际编译 → promotion/handoff → checkpoint/resume”检查点。

### 计量缺口（下一片，已定位插入点）

第四次复核 §1/§7.5 要求的“提案调用计量”**未完成**，本轮只完成定位：

- 现状标记：`method_architect.py:8642` 在默认组织提案 caller 生效时写
  `proposal_call_accounting="recorded_not_in_invocation_plan"`；请求 trace 由
  `narrative_organization_proposal.py` 的 caller 记录（`request_input_hash`、`planned_input_tokens`），
  只有预留估算，没有完整序列化请求的实测。
- 不能在提案调用上直接复用 `ActualRequestReceiptV2`：它的 `consumer_role`/`phase`/`workset_id`/`page_id`/
  `plan_digest`/envelope digests 都绑定 unified pipeline 的真实 invocation；为提案调用伪造这些身份
  会产生假的投递证据。正确做法是**提案作用域的独立计量记录**（planned/reserved/measured/spent/unsettled、
  失败尝试与 retry、恢复），并显式标注它是否属于统一 invocation plan。
- 需要复用而不是新造的组件：`unified_context_compiler.measure_unified_tokens`（`UnifiedTokenMeterV1`，
  `model_tokenizer` 或声明的保守 meter）、`unified_invocation_ledger.publish_attempt_started/completed`
  的“先写 started、再写 completed”顺序语义、以及 `build_resume_plan`/`unsettled_started_attempts` 的
  恢复口径。
- 真实 tokenizer 校准必须绑定实际模型与完整序列化请求（prompt + input_payload + response schema），
  不能用预留余量当实测；校准结果随记录落盘。

### 追加：三个未 resolved target 的确定性编译探针（有界结论）

`.tmp/c2p-gap-evidence-20260913/close_unresolved_targets.py` 对首轮命中的三个候选文件
（`src/model/transformer_encoder_hybrid_attention.py`、`src/model/ebcar_dedicated_attention_model.py`、
`main.py`）用生产抽取器建 behavior 子图（701 节点）并编译事实（530 条，全部 supported），
再用冻结 target 对齐：

| target | 期望谓词 | 对齐状态 | 命中谓词 |
|---|---|---|---|
| `target-28d15b78c376` | FILTER, MASK | resolved | MASK |
| `target-d9c93c39b278` | CALL, COMPUTE | partial | CALL, COMPUTE |
| `target-c56c2da81fd1` | FILTER, MASK | resolved | MASK |

有界结论：两个 `FILTER`/`MASK` 缺口在冻结树中已有可编译证据，Run E 未解决是搜索/读取覆盖问题，
不是仓库缺操作；`target-d9c93c39b278` 谓词全中但 slot 未绑定（其他已 resolved target 同样如此，
属 coverage 阶段一般行为）。限制：本探针用合成 obligation id 一次性编译整文件节点，**不**等于生产
路径会把该 obligation 判为 supported；不写回 disposition、不关闭 frontier。结果渲染进
`docs/research_gap_evidence_2026-09-13.md` §4。

## 2026-09-13（计量片）：提案调用计量落地（caller 边界）

第四次复核 §7.5 要求的提案调用计量本轮实现到 **caller 边界**，并保持“未计量”与“已计量”的诚实区分。

### 新增

- `src/code2paper/agentic/proposal_call_accounting.py`：
  - `ProposalCallTallyV1`（每次尝试：planned/reserved/measured/spent、meter 与 tokenizer 身份、
    `request_input_hash`、状态与错误、起止时间、content_digest）与
    `ProposalCallAccountingV1`（`begin`/`finish`、`totals()`、`failed_call_ids()`、`unsettled_*`）；
  - **unsettled** = 只有 started 记录、没有 finish 记录的尝试的预留量（中断/崩溃/待恢复）；
  - **spent** = 已交到 caller 的尝试的实测输入（失败尝试同样计入，方向保守：宁可多记不可少记）；
  - `measure_proposal_request` 复用 `unified_context_compiler.measure_unified_tokens` 与
    `UnifiedTokenMeterV1`，对**完整序列化请求**分别测量 prompt / input_payload / response_schema；
  - `proposal_call_meter_from_envelope(envelope, ...)`：有 token meter 才计量；envelope 声明
    `model_tokenizer` 而本作用域没有 tokenizer 时返回 `None`（**不**用保守代理冒充实测）；
  - `write_proposal_call_accounting`/`load_proposal_call_accounting`（输出名已注册为
    `artifacts/06_authoring/proposal_call_accounting_v1.json`）。
- `narrative_organization_proposal.build_narrative_organization_proposal_caller(..., call_meter=...)`：
  每次尝试在**调用前**测量完整序列化请求、`begin` 写入待结项、调用后 `finish`；
  测量失败（如 tokenizer 缺失）记为 `failed` 且**不调用模型**；无 meter 时 `accounting=None`，
  保持 `recorded_not_in_invocation_plan`。
- `method_architect.build_narrative_plan_v3(..., proposal_call_meter=...)`：把 meter 传给默认 caller 构造，
  并在 trace 中写 `proposal_call_accounting`（有实测 tally 时为 `measured_with_proposal_accounting`）、
  `proposal_call_totals`、`proposal_call_accounting_digest`、`proposal_call_rows`。
- `publication_method_writer`：在构建 narrative plan 时从运行冻结 envelope 派生 proposal meter，
  经 `_build_narrative_plan_v3(..., proposal_call_meter=...)` 注入。

### 测试与验证

- `tests/test_agentic_proposal_call_accounting.py`（**10 项**）：planned/reserved/measured/spent/unsettled 区分、
  失败尝试保守计费、重复身份拒绝、持久化后 resume 的 unsettled 重算、tokenizer meter 必须配 tokenizer、
  envelope 派生拒绝伪造实测、caller 每次尝试独立 attempt 号、测量失败不触达模型、无 meter 保持 recorded-only、
  plan trace 携带实测 totals。
- 全量静态：`python -m pytest -q tests/ -p no:randomly` → `3440 passed, 3 skipped`；`compileall`、`git diff --check` 通过。
- 冻结 Run E 离线链在本片后重跑（`.tmp/c2p-unified-repair-20260913-r10/offline/offline-ebcar-r10-metering.json`），
  payload 与上一检查点**逐字节一致**（archive `58ad15ef…`、887 atoms、131 页/4 worksets、`failure_details=[]`、
  五个准入码不变）：离线链没有 provider key，提案 caller 不构建，计量不激活，因此不影响冻结结果。
  `r10-summary.json` 已按该报告重新派生。

### 仍未完成（计量）

- 把提案调用的 planned/reserved 并入**统一 invocation plan 的预留与发送前扣账**（当前是
  caller 边界的独立 tally + trace，尚未参与 run 级 planned/reserved 汇总）。
- 真实 tokenizer 校准：需要在产品 runner 一侧把实际 tokenizer 与完整序列化请求一起传入
  （writer 作用域没有 tokenizer；`model_tokenizer` envelope 下提案调用会保持未计量而不是伪造实测）。

## 2026-09-13（补证片二）：两个 mechanism 的逐 operation 分解与定向证据

承接上一片的五缺口分解，本片把**两个 mechanism**（`operation_disposition_unresolved`）分解到具体
未处置 operation，并给出逐项入口/配置/关系证据、读取、frontier、回执与停止原因。

### 方法（全部派生，模型调用 0）

- `.tmp/c2p-gap-evidence-20260913/decompose_mechanisms.py`：复用离线矩阵的
  `_load_research_inputs` / `_source_inputs` / `_rehydrate_source_inputs` /
  `_rebuild_current_context_set`，在冻结输入上以 `current_compiler_rebuild` 重跑
  `compile_mechanism_contexts` + `validate_mechanism_context_completeness`，输出
  `mechanism-decomposition.json`（含每个未处置 operation 的谓词、span、enclosing symbol、阻塞原因）。
- `.tmp/c2p-gap-evidence-20260913/probe_mechanism_operations.py`：对每个未处置 operation 用生产工具
  （`read_code_span`、`inspect_configuration`、`search_code`、`close_search_frontier` + R9 账本）
  收集读取、配置键命中、检索命中与回执，输出 `mechanism-operation-evidence.json`。
- `render_evidence_doc.py` 把两者（以及冻结的 `configuration_claims_v1.json`）渲染进
  `docs/research_gap_evidence_2026-09-13.md` §1.1/§1.2。

### 结果

- 失败码可稳定复现：`mech_sym:9773c5add7af1f92` 157 个 operation 中 6 个 `explicitly_unresolved`；
  `mech_sym:f6cf5bdfe2ae16f0` 217 个中 2 个；两者 terminal coverage 均为 1.0，
  即失败集中在少数操作而非整体覆盖。
- 8 个未处置 operation 全部位于“掩码装配/传入注意力层”的分支代码：
  `transformer_encoder_hybrid_attention.py:160`（`TransformerEncoderWithHybridAttention.forward`，
  LOAD/CALL/WRITE `attn_mask`/`key_padding_mask`/`causal_mask`/`src`）与
  `ebcar_dedicated_attention_model.py:171`（`EBCarRerankerHybridAttention.forward`，
  `dedicated_attention_mask = torch.zeros(...)`）；阻塞原因均为 `unresolved_detail:*`
  （对应 detail 的 active path 为 `unknown`）。
- 直接上游是配置选择证据缺口：冻结配置声明中 `self.cfg.use_dedicated_attention` 为
  `value=None`、`state='unresolved'`、`definition_span_ids=[]`、`entrypoint_span_ids=[]`，
  只有 1 条 override-chain 关系；本轮定向检索命中 `conf/config.yaml:19:use_dedicated_attention`
  定义，但**未**取得取值/入口绑定。
- 两个 mechanism 的 frontier 均未关闭（`search_result_truncated`，
  `unread_candidates:33` / `unread_candidates:6`），回执分别为
  `receipt:caf066735d668b4e`、`receipt:bf299b111cb62287`；按 R9 规则**未写回任何 disposition**，
  也未把“未找到取值”当作不存在。

### 下一步

1. 读完两个 mechanism 的未读命中（33 + 6），或在读完后取得关闭回执；
2. 解析 `use_dedicated_attention` 的取值/入口绑定与 override chain（配置选择证据第 3 节），
   再把对应 detail 的 active path 置为可判定，从而让 8 个 operation 得到 disposition；
3. 三个 strict obligation 侧：把已找到的 FILTER/MASK span 走生产 packet→fact→claim，
   并定位 `O-STAGE-01-039a963a` 的 claim/qualifier 侧失败。

## 2026-09-13（补证片三）：阻塞 detail 与配置选择证据

本片回答上一片留下的问题：“8 个未处置 operation 到底卡在哪”。

### 结果（全部由脚本从冻结产物派生，模型调用 0）

- 阻塞点不是“缺证据”，而是承载这些 operation 的 **supporting detail 的 `active_path_status=unknown`**：
  - `mech_sym:9773c5add7af1f92` → `detail:...:68`（`transformer_encoder_hybrid_attention.py:160`）；
  - `mech_sym:f6cf5bdfe2ae16f0` → `detail:...:39`、`detail:...:40`
    （`ebcar_dedicated_attention_model.py:171` / `171:174`）。
- 配置选择证据（清单第 3 节）本轮取得：
  - 定义 `conf/config.yaml:19` → **`use_dedicated_attention: True`**（span `span:conf/config.yaml:16:22`）；
  - override 链 `rel:83ef85703286c813`（`CONFIGURED_BY`）从
    `span:src/model/ebcar_dedicated_attention_model.py:145:174` 的分支指向该键的 LOAD 节点，
    即 `if self.cfg.use_dedicated_attention:` 正是 mechanism 2 掩码装配区间的守卫；
  - 消费/入口命中 `src/model/ebcar_dedicated_attention_model.py:145`、`src/train_ebcar.py:116`、
    `main.py:15/25`（OmegaConf loader）；直接检索 `config.yaml` 为 `success_empty`
    （配置按 loader 变量路径装配，不是字面量路径）。
- frontier 仍未关闭（`unread_candidates:11`，回执 `receipt:3d0d25cc227b84e0`），
  因此**只登记证据**：不写回配置 claim、不写回 operation disposition。
- 结论（有界）：mechanism 2 的 active-path 问题在本轮证据下已可判定
  （分支 + 配置取值 + 入口消费齐备），应由生产路径重新解析配置声明；
  mechanism 1 的阻塞 detail 位于 hybrid attention 编码器调用行，其守卫/选择证据尚未取得，
  需按同一方法继续检索。

### 脚本与产物

- `decompose_mechanisms.py`（新增 `blocking_details`）→ `mechanism-decomposition.json`
- `probe_config_evidence.py` → `config-evidence.json`
- `render_evidence_doc.py` → `docs/research_gap_evidence_2026-09-13.md` §1.3

## 2026-09-13（补证片四）：两个 mechanism 的守卫链与 active-path 判定证据

### 结果（冻结源码直读 + 生产工具，模型调用 0）

守卫链（每一环都可复核到冻结行号）：

| 环节 | 位置 | 事实 |
|---|---|---|
| 入口装配 | `main.py:24` | `@hydra.main(config_path="conf", config_name="config")` 把 `conf/config.yaml` 装配为 `cfg` |
| 模型构造 | `src/train_ebcar.py:136` | `reranker = EBCarRerankerHybridAttention(cfg, device)`，无分支 |
| 编码器构造 | `src/model/ebcar_dedicated_attention_model.py:22` | `__init__` 中无条件构造 `TransformerEncoderWithHybridAttention` |
| 分支守卫 | 同文件 `145`–`174` | `if self.cfg.use_dedicated_attention:`（145–167 建掩码） / `else:`（168–174 消融分支） |
| 配置取值 | `conf/config.yaml:19` | `use_dedicated_attention: True` |

有界结论：

- mechanism 2 的 2 个未处置 operation 位于 `else`（消融）分支（171–174），
  在冻结取值 `True` 下**不活跃**；
- mechanism 1 的 6 个 operation 位于 `TransformerEncoderWithHybridAttention.forward`
  （`span:...:160`），该编码器经上述无条件链条构造并调用，在 train 入口下**活跃**；
- 二者都不是“证据不存在”，而是 completeness 无法仅凭 evidence 判定 active path；
  判定所需的值/定义/入口/守卫证据已齐备。
- 工具旁证：`find_references` 只找到 `ebcar_dedicated_attention_model.py:13/22` 两处引用；
  `inspect_configuration` 对 `use_hybrid_attention`/`hybrid_attention`/`use_transformer_encoder`
  均 `success_empty`（不存在独立开关）；`conf/config.yaml` 的键集合已列出（`use_dedicated_attention`
  是唯一相关开关）。

仍未写回：frontier 未关闭（`unread_candidates:4`，回执 `receipt:9eb23389098ad608`），
且 Run E 是否经 `train_ebcar` 入口的 scenario 绑定需运行侧确认；本轮只登记证据。

### 产物

- `probe_mechanism1_guard.py` → `mechanism1-guard-evidence.json`
- `render_evidence_doc.py` → `docs/research_gap_evidence_2026-09-13.md` §1.3.1

## 2026-09-13（补证片五）：三条 strict 失败的精确条件

### 结果（读 strict lane 实际读取的对象）

`publication_method_writer` 的 strict 判定读 **research agenda**（不是 coverage 对象）：
`must_cover` 且 `status == "partial"` 时，必须同时具备 `supported_claim_ids`
与全部 `terminal == "explicit_gap"` 且带 `attempted_tools` 的 `gap_requirements`。

冻结 Run E 三条 must_cover 的实际状态：

| obligation | status | supported claims | gap requirements | terminal gap | 未满足 typed 要求 |
|---|---|---|---|---|---|
| `O-METHOD-MAINLINE-01-c8146479` | partial | 11 | 0 | False | `typed_semantic:transformations:scores`、`typed_predicate:FILTER`、`typed_predicate:SELECT` |
| `O-STAGE-01-039a963a` | partial | 1 | 0 | False | `typed_predicate:SELECT`、`typed_predicate:TRANSFORM` |
| `O-STAGE-03-2c5bd758` | partial | 8 | 0 | False | `typed_predicate:FILTER` |

直接原因是 **partial 但没有任何 terminal gap 记录**（`gap_requirement_count=0`），
并非“没有证据”（每条都已有 supported claim）。这也修正了上一片按 coverage 对象
（`O-STAGE-01` coverage=supported）作出的推断：strict 与 coverage 读的是不同对象。

下一步：要么补齐上表未满足的 typed 要求（`FILTER` 已有可编译证据线索），
要么为剩余要求写带 `attempted_tools` 的 terminal `explicit_gap`；
计入 `SELECT`/`TRANSFORM`/`transformations:scores` 的定向检索。

### 产物

`localize_strict_failures.py` → `strict-failure-localization.json` →
`docs/research_gap_evidence_2026-09-13.md` §2.1

## 2026-09-13（补证片六）：未满足 typed 要求的定向检索

对 §2.1 列出的未满足要求做定向检索（冻结快照、生产工具、模型调用 0）：

| 要求 | 线索 | 状态 |
|---|---|---|
| `SELECT` | 无字面命中（`select`/`argsort` 均 `success_empty`），但 `topk` 命中 `src/utils.py:41/51` | 需按 topk/排序类操作解释谓词 |
| `TRANSFORM` | 命中集中在配置/依赖（`conf/retrieval_model/*.yaml:7`、`requirements.txt:19`），无可编译变换操作 | 未定位 |
| `transformations:scores` | `data/real/MS_MARCO_v2/preprocess.py:51-76`（8 条截断命中） | 待读取编译 |
| `FILTER` | `main.py:34`（单条）；`mask` 命中注意力模型 139–141 等 | 与 §1 同源 |

三组检索的回执分别为 `receipt:282cb307beaea049`、`receipt:f0337ea76f93a837`、
`receipt:a216cafff28d876c`，全部 `search_frontier_closed=false`
（`search_result_truncated`、`search_ledger_has_no_read_candidate`，未读 26/16/9）
→ 未写回任何负结论，仅登记为下一轮读取/编译候选。

产物：`probe_remaining_requirements.py` → `remaining-requirement-evidence.json` →
`docs/research_gap_evidence_2026-09-13.md` §2.2。

## 2026-09-13（补证片七）：未满足要求的编译探针

对 §2.2 的候选文件（`src/utils.py`、`MS_MARCO_v2/preprocess.py`、`main.py` 与两个注意力模型文件）
用生产抽取器编译（1000 节点 / 761 条 supported fact），再对齐三条 strict obligation 中带
`SELECT/ SORT/ TOPK/ TRANSFORM/ FILTER/ MASK` 的 target：

- **7/9 对齐为 `resolved`**：`TRANSFORM`、`SORT`（SELECT 家族）、`MASK`（FILTER 家族）都取得可编译事实；
- 2 个仍 `partial`（`target-22340e7ccc67`、`target-b28bcf95a54c`，谓词已命中但状态未满）。

有界结论同上：这证明**冻结树中已存在可编译证据**，Run E 的 strict 缺口是搜索/读取覆盖问题；
不写回 disposition、不关闭 frontier，也不等于生产路径会判 supported。

产物：`close_remaining_targets.py` → `remaining-target-compile.json` →
`docs/research_gap_evidence_2026-09-13.md` §4.1。

## 2026-09-13（计量片二）：提案计量落成 durable 产物

- `proposal_call_accounting.accounting_from_plan_trace(trace)`：从 narrative plan trace 的
  `proposal_call_rows` / `proposal_call_totals` 重建 `ProposalCallAccountingV1`；
  **没有实测行时返回 `None`**（“recorded” 不会变成 “measured”）。
- `publication_method_writer` 在构建 narrative plan 之后把该 tally 写成
  `artifacts/06_authoring/proposal_call_accounting_v1.json` 并登记 `paths["proposal_call_accounting_v1"]`；
  写入失败不阻塞 authoring（计量是证据，不是门禁）。
- 测试：`tests/test_agentic_proposal_call_accounting.py` 增至 **11 项**，新增 trace→产物重建/回读一致性
  与“无实测行不得伪造 tally”。相关套件 177 passed。
- 仍未完成：把提案调用并入统一 invocation plan 的 run 级 planned/reserved 预留与发送前扣账；
  产品 runner 侧真实 tokenizer 校准。

## 2026-09-13（计量片二复核）：离线链在写入计量产物后仍逐字节一致

本轮 writer 侧新增了 proposal 计量产物的写入分支，因此重跑冻结 Run E 离线链复核：
`offline-ebcar-r10-metering2.json` 与既有 `offline-ebcar-r10.json` 的 project payload
**逐字节一致**（archive `58ad15ef…`、887 atoms、131 页/4 worksets、`failure_details=[]`、
五个准入码不变）。原因：离线链没有 provider key，提案 caller 不构建，计量分支不激活。
规范报告已用该次运行刷新，`r10-summary.json` 随之重新派生（24 文件 + 报告 sha256 同源）。

## 2026-09-13（检查点复核）：全量静态在当前代码上通过

在“提案计量 durable 产物 + 离线链复核”之后的当前工作树上重跑全量静态：

```text
python -m pytest -q tests/ -p no:randomly
3441 passed, 3 skipped, 7 warnings, 12 subtests passed in 523.06s
```

`python -m compileall -q src tests scripts` 与 `git diff --check` 亦通过。
本计数覆盖本轮全部生产改动（`proposal_call_accounting.py`、`narrative_organization_proposal.py`、
`method_architect.py`、`publication_method_writer.py`、`core/output_names.py`）；
此前记录的 `3440 passed` 是计量片一之后的检查点。

## 2026-09-13（计量并账前置定位）：run 级并账的确切插入点

下一片若要完成“提案调用并入统一 invocation plan 的 run 级预留/发送前扣账”，已定位到的确切事实：

- 统一预算角色是**封闭四元组**：`unified_context_compiler.UNIFIED_BUDGET_ROLES =
  ("formalizer", "writer", "realizer", "binder")`（第 83 行）；envelope 的
  `request_budget_by_role` / `max_request_input_tokens_by_role` 都只按这四个角色生成
  （第 2703/2725/2761 行）。提案角色 `method_proposition_architect`
  （`llm/role_config.py:80`）**不在**该集合内。
- run 级计划注册点：`publication_method_writer.py:3257`（writer 计划）、
  `publication_method_writer.py:17224`（realizer 计划）、`formalization_agent.py:2476`
  （formalizer 计划），均调用 `unified_invocation_ledger.register_invocation_plan`。
- 因此并账有两条互斥路线，必须在实现前选定并写入执行记录：
  1. **纳入计划**：把提案角色加入 `UNIFIED_BUDGET_ROLES` 与 profile/env 预算字段，
     让 envelope 为它生成 `RoleRequestBudgetV1` 与 per-request cap，再按同一
     `account_unified_request_tokens` 在发送前扣账、写 ledger receipt。
     代价：改动统一预算契约与 profile，需同步更新冻结 profile 摘要与全量测试。
  2. **计划外但受控**：保持四角色契约不变，提案调用继续使用当前 caller 边界 tally
     （planned/reserved/measured/spent/unsettled + durable 产物），并在 run 汇总里显式标注
     `invocation_plan_membership=recorded_not_in_invocation_plan`/`measured_with_proposal_accounting`，
     不把它计入 run 的 planned/reserved。代价：run 级总账不含提案调用，
     必须在准入/汇总中可见，避免被误读为“已全部计量”。
- tokenizer 校准：`measure_unified_tokens` 支持 `meter.method == "model_tokenizer"` +
  `tokenizer.encode`；产品路径要在 runner 侧把实际 tokenizer 传进
  `proposal_call_meter_from_envelope(..., tokenizer=...)`（writer 作用域没有 tokenizer，
  当前实现按诚实原则返回 `None`，即保持未计量）。

### 并账路线现状（未改契约，仅陈述事实）

当前代码实际处于**路线 2（计划外但受控）**：统一预算契约仍是四角色
（`UNIFIED_BUDGET_ROLES`），提案调用的计量只存在于 caller 边界 tally 与
`proposal_call_accounting_v1` 产物中，`invocation_plan_membership` 字段显式区分
`recorded_not_in_invocation_plan` 与 `measured_with_proposal_accounting`，
**未**计入 run 的 planned/reserved。

因此：
- 不存在“提案调用已被 run 级计划计量”的错误声明空间——归属由字段与产物共同说明；
- 路线 1（把提案角色纳入统一预算/envelope/发送前扣账）会改动统一预算契约与 profile 摘要，
  属于需要显式决策与全量复验的改动，尚**未**执行，也未在本轮擅自执行；
- 该选择的触发条件：当需要把提案调用计入 run 总账、或 live 计量需要对账时，走路线 1；
  在此之前路线 2 是当前状态而非“已完成 run 级并账”。

## 2026-09-13（计量片三）：route-2 的 run 汇总可见性

在路线 2（计划外但受控）下补齐“可见性”要求：`run_autonomous_method_agent` 在最终写
`run_summary.json` 之前，若 writer 已产出 `paths["proposal_call_accounting_v1"]`，
则把 tally 与摘要写入 run summary（`proposal_call_accounting` / `proposal_call_accounting_digest`）。

- **无实测提案调用的 run 不新增任何键**：因此既有测试、产品产物与冻结 Run E 离线链不受影响；
- 有计量时，summary 中的 `invocation_plan_membership` 明确说明它属于 caller 边界计量
  （`measured_with_proposal_accounting`），不是 run 级 planned/reserved；
- 计量失败/文件缺失一律静默跳过（计量是证据，不是门禁）。

验证：`tests/test_agentic_proposal_call_accounting.py`（12 项）+ `test_agentic_autonomous_method_agent.py`
+ `test_agentic_publication_method_writer.py` → **186 passed**；`compileall`、`git diff --check` 干净。

## 2026-09-13（交付节点 A）：分支控制关系与支配推导修复

按 [产品主链诊断与推进指导](../docs/research_to_method_product_delivery_guidance_2026-09-13.md) 的节点 A 执行。

### 生产入口消费了什么变化

- `python_behavior_adapter._BehaviorRelationVisitor`：新增互斥分支臂登记
  （`_exclusive_arm_groups`，绝对快照行范围）与 `_ast_span_id`/`_span_lines` 辅助；
  `add_sequential_control_relations` 现在
  1. **不再**在同一条 `if` 的两个互斥臂之间生成 `NEXT_CONTROL`（臂边界不是执行顺序），
  2. 改为把每个臂的末节点连到 `if` 之后的第一条语句（真实的控制流汇合点）。
- 支配推导（`mechanism_context_compiler._branch_dominance_guards`）与冲突处理**未改动**：
  真正的双极性冲突依旧被识别并保持 `unknown`。

### 哪一个当前阻塞消失

指导方诊断脚本 `branch_dominance_control.py` 在**生产代码**上重跑（模型调用 0，源码零漂移）：

| 指标 | 修复前 | 修复后 |
|---|---|---|
| 最小 if/else 伪冲突 | 1 | **0** |
| 冻结重建中的跨臂边 | 2 | **0** |
| `mech_sym:9773c5add7af1f92` operation / unresolved / completeness | 157 / 6 / `operation_disposition_unresolved` | **157 / 0 / []** |
| `mech_sym:f6cf5bdfe2ae16f0` operation / unresolved / completeness | 217 / 2 / `operation_disposition_unresolved` | **217 / 0 / []** |

真实冲突门保持：`test_graph_branch_dominance_reports_polarity_conflict`、
`test_polarity_conflict_keeps_operation_unresolved` 通过（人工赋予同节点正负两条 typed 分支边仍被拒绝）。

### 新增可验证产物

- `tests/test_agentic_branch_control_relations.py`（2 项）：断言臂间不存在 `NEXT_CONTROL`、
  每个臂都与 `if` 之后的语句有汇合边；
- `.tmp/c2p-product-path-audit-20260913/branch-control.json`（由指导方脚本重跑覆盖）
  现在记录 0 跨臂边、0 unresolved、无完整性失败。
- 相关套件：mechanism/behavior/branch 共 **161 passed**。

### 节点 A 的冻结链复核（新目录）

按指导方要求使用新目录绑定本次代码状态与输入身份：

- `.tmp/c2p-branchfix-checkpoint-20260913/offline/offline-ebcar-branchfix.json`（原始报告）
- `.tmp/c2p-branchfix-checkpoint-20260913/offline/summary.json`（派生汇总，**22 个绑定文件**
  含本轮改动的 `python_behavior_adapter.py`、`mechanism_context_compiler.py`、
  `unified_context_compiler.py`、`proposal_call_accounting.py`、`narrative_organization_proposal.py`、
  `method_architect.py` 等，报告 sha256 同源）

对照（修复前 → 修复后）：

| 项 | 修复前 | 修复后 |
|---|---|---|
| 准入失败码 | 2×`operation_disposition_unresolved` + 3×strict partial | **仅 3×strict partial** |
| archive | `58ad15ef…`（887 atoms） | `463c46ea…`（887 atoms） |
| 页/worksets | 131 / 4 | **135 / 4** |
| 调用计划 | 65 / 18 / 18（101 次） | 66 / 18 / 18（**102 次**） |
| `failure_details` | `[]` | `[]` |
| 三阶段 admission | fail | fail（尚未执行；计划可编译） |

结论：节点 A 在冻结链上闭环——两个结构门消失，operation 数与真实冲突门保持；
剩余失败码只剩 strict 三项（与 Candidate Research gate 分属不同 lane）。
按指导，分支修复后需重新编译工作集与调用计划：本次已重新编译（135 页 / 102 次调用），
后续计量与 Candidate 准入应以该新计划为准，不再引用修复前的 101 次/1,938,180 tokens 额度。

## 2026-09-13（交付节点 B 分析）：Candidate 阶段准入尚未按 lane 分列

在节点 A 之后同一检查点上读取离线报告（`.tmp/c2p-branchfix-checkpoint-20260913/offline/offline-ebcar-branchfix.json`）：

| 项 | 结果 |
|---|---|
| Candidate Research gate | **pass**（`candidate_gate_pass=True`、`candidate_failure_codes=[]`、handoff `eligible`、重认证失败 `[]`） |
| 结构完整性 | 两机制 `completeness_failures={9773…: [], f6cf…: []}` —— 节点 A 已闭环 |
| strict lane | 三条 `core_intent_partial_without_terminal_gap`（单独记录，与 Candidate 不同 lane） |
| 三阶段 admission | 仍为 `fail`，`admission_failure_codes` **只含 strict 三条** |

根因（生产/离线在同一处）：`run_unified_ten_project_offline_matrix.py` 的三处阶段准入
（`phase_admissions["formalizer"|"writer"|"realizer"]`，约 1145/1214/1244 行）都传
`research_failures=_research_gate_failures(research)`，即**严格 lane**；而同一脚本在
`_research_mode_failures`（1007 行）已经算出 `candidate_research_failures`，只用于并列报告，
未进入阶段准入。

节点 B 的最小实现（下一片）：

1. 在三处 `evaluate_unified_live_admission_v1(...)` 旁增加同参数、`research_failures=candidate_research_failures`
   的第二次求值，记为 `phase_admissions_candidate[phase]`；
2. `_phase_row`（约 895 行）在 `admission_failure_codes` 之外增加 `candidate_admission_failure_codes`，
   报告并列展示两个 lane，不改变 strict 结论；
3. 用同一代码/输入重跑离线链，确认 Candidate 三阶段准入为 pass（或给出其真实的第一个阻塞），
   strict 三条继续单列。
4. 计量并入统一 run 预算：按指导选择“纳入统一预算”，为提案角色/调用类别补最小预算与调用身份合同，
   复用现有 attempt 身份与 durable started，验证“开始后中断再恢复”和“超额发送前拒绝”，
   并验证四角色兼容性；新计划基线为 135 页 / 102 次调用（66/18/18）。

## 2026-09-13（交付节点 B 之一）：Candidate 阶段准入按 lane 分列

### 生产入口消费了什么变化

`scripts/run_unified_ten_project_offline_matrix.py`：
- 新增 `phase_admissions_candidate`，在 formalizer/writer/realizer 三处用**完全相同的参数**、
  以 `research_failures=candidate_research_failures` 再求值一次真实准入
  （此前三处都只按严格 lane 求值）；
- `_phase_row` 并列输出 `candidate_status` 与 `candidate_admission_failure_codes`；
- 项目级 `failure_codes`/`status` 仍按严格 lane 汇总，strict 结论未被改写或放宽。

### 哪一个当前阻塞消失

冻结 Run E（同一代码/输入，`.tmp/c2p-branchfix-checkpoint-20260913/offline/`）：

| phase | strict | candidate | calls | strict codes | candidate codes |
|---|---|---|---|---|---|
| formalizer | fail | **pass** | 66 | 3 | **[]** |
| writer | fail | **pass** | 18 | 3 | **[]** |
| realizer | fail | **pass** | 18 | 3 | **[]** |

Candidate Research gate：`pass`、`candidate_failure_codes=[]`、handoff `eligible`；
archive `463c46ea…`（887 atoms）、135 页 / 4 worksets。strict 三条
`core_intent_partial_without_terminal_gap` 单列保留。

### 新增可验证产物

- `.tmp/c2p-branchfix-checkpoint-20260913/offline/offline-ebcar-branchfix.json`（规范报告，含两 lane）
  与 `summary.json`（22 个绑定文件 + 报告 sha256 同源，含 `candidate_status`）；
- `tests/test_agentic_unified_ten_project_offline_matrix.py` 6 passed。

### 节点 B 剩余

计量并入统一 run 预算：按指导为提案角色/调用类别补最小预算与调用身份合同，复用现有 attempt 身份与
durable started，验证“开始后中断再恢复”“超额发送前拒绝”，并验证四角色兼容；
新计划基线 **135 页 / 102 次调用（66/18/18）**。

## 2026-09-13（节点 B 计量，受阻点记录）：`BUDGET_FIELD_BY_ENV` 是必需字段契约

尝试为“提案角色纳入统一预算”加入第五个角色时确认了一个硬约束，记录下来以免重复试错：

- `unified_context_compiler.BUDGET_FIELD_BY_ENV` 的每个条目都会被
  `read_unified_budget_profile` 读取，并在 envelope 构建处作为**必需字段**校验
  （缺失即 `unified_invocation_budget_missing: profile budget is missing required fields: [...]`）。
  因此**不能**把“可选角色列表/其预算字段”直接注册进该映射——会让所有现有 profile 失败
  （实测：`tests/test_agentic_unified_context_compiler.py` 6 failed）。
- 正确做法（下一片实现）：新增一个可选的读取路径
  （例如 `read_unified_optional_budget_profile(env)` → `extra_roles` + 该角色的四个预算字段），
  在 `build_run_invocation_budget_envelope_v1` 里合并：未声明 → 四角色契约与 envelope 摘要不变；
  声明完整 → 第五角色进入 `role_calls`/`request_budget_by_role`/`max_request_input_tokens_by_role`，
  声明不完整 → fail closed。
- 该实验已完整回滚（`git diff` 中 `unified_context_compiler.py` 只剩此前轮次的改动），
  编译器套件恢复 16 passed。

节点 B 计量剩余项不变：可选角色预算读取路径 → 提案调用按现有 attempt 身份/durable started 记账 →
验证“开始后中断再恢复”“超额发送前拒绝”→ 四角色兼容性与新计划（135 页 / 102 次调用）复跑。

## 2026-09-13（节点 B 计量之二）：提案角色可选纳入统一预算

按指导选择的“纳入统一预算”方向，用**可选读取路径**实现（不触碰必需字段契约）：

- `unified_context_compiler` 新增 `CODE2PAPER_UNIFIED_EXTRA_ROLES` 与
  `read_unified_extra_roles(env)`：列出角色即要求同时给出 `max_<role>_calls`、
  `output_token_reserve_<role>`、`max_request_input_tokens_<role>`、
  `scaffolding_token_reserve_<role>`；缺一即 `unified_invocation_budget_missing` fail closed。
- `build_run_invocation_budget_envelope_v1` 通过 `declared_extra_roles(profile_budget)` 把
  已声明完整的角色并入 `role_calls`，于是自动获得 `RoleRequestBudgetV1` 与 per-request cap。
- 接线：`publication_method_writer`（envelope 构建处）与离线矩阵 `_parse_budget` 都先
  `read_unified_budget_profile` 再 `update(read_unified_extra_roles(...))`。

实测（本地 envelope 构造）：

| 场景 | 结果 |
|---|---|
| 未声明 extra roles | 角色集合仍为 `binder/formalizer/realizer/writer`，envelope 摘要不变（`866ce853…`） |
| 完整声明 `method_proposition_architect` | 角色集合 +`method_proposition_architect`；其 reserve（prompt 20 / output 64 / thinking 0 / scaffolding 0）与 cap 256 进入 envelope；摘要改变（真实契约变更） |
| 只声明角色、缺字段 | 拒绝：`extra roles [...] are declared ... but missing budget fields` |

测试：`tests/test_agentic_proposal_call_accounting.py` **14 项**（新增可选角色契约测试：
默认四角色不变、opt-in 生效、半声明拒绝）；编译器/矩阵/writer-unified 套件 31 passed。
`git diff --check` 干净。

下一步（节点 B 收尾）：让提案调用真正走统一 attempt 身份与 durable started（
`publish_attempt_started`/`publish_attempt_completed`）+ 发送前按上述 cap 扣账，
并验证“开始后中断再恢复”“超额发送前拒绝”，随后复跑 135 页 / 102 次调用计划。

## 2026-09-13（节点 B 计量之三，收尾）：提案调用的发送边界与 durable started

节点 B 计量剩余项已实现并验证，范围保持在“复用统一 run 预算与调用身份语义”，未新增平行权威账本、
未伪造 page/workset 身份：

- **发送前上限**：`proposal_call_meter_from_envelope` 把 envelope 的
  `max_request_input_tokens_by_role[role]` 同时作为 `max_input_tokens`；`narrative_organization_proposal`
  在测量之后、调用模型之前比较，超限则该 attempt 记为 `failed`
  （`error=proposal_call_budget_exceeded:<measured>><cap>`）并按已测量输入扣账，**模型不会被调用**。
- **durable started**：`persist_proposal_call_state` 在 `begin` 之后、请求发出之前把 tally 写入
  `<out_root>/artifacts/06_authoring/proposal_call_accounting_v1.json`（与已注册产物同名同路径），
  `finish` 后再写一次；中途被杀死的进程会留下 `pending` 行。
- **恢复语义**：`load_durable_accounting` 在构造 caller 时回读该文件（角色不匹配则拒绝采用，
  避免把“别人的 token”当成本 run），于是恢复运行看到 `unsettled_call_ids`，
  同一 kind+target 的 attempt 编号继续递增（不会重用中断的身份）；
  `carry_over_unsettled` 保证后续 `accounting_from_plan_trace` 重写该文件时不会丢掉更早的未结算行。
- **为什么不写进页面 ledger**：`unified_invocation_ledger.unsettled_started_attempt_records`
  会拿每个 started 记录去当前 plan 里匹配 invocation，匹配不到即标为
  `plan_source == "unknown"`，而该模块文档明确要求 unknown 必须**阻塞** run-budget 决策而非按 0 计。
  提案调用不占页面 invocation，塞进去只会制造一个无法解析的 started 记录并阻塞预算——因此
  membership 标签保持诚实的 `measured_with_proposal_accounting`（“已按 run 预算计量”），
  而不是宣称 page/plan 成员。
- **真实 tokenizer 校准路径**：`run_publication_method_writer` / `_run_publication_method_writer_impl`
  新增可选 `proposal_tokenizer`，直接进入 `proposal_call_meter_from_envelope(tokenizer=...)`：
  提供即按 `measure_unified_tokens` 的 tokenizer 规则测量（identity 必须与 envelope 声明一致），
  未提供且 envelope 声明 `model_tokenizer` 时返回 `None` → 提案调用保持
  `recorded_not_in_invocation_plan`，不用代理规则冒充 tokenizer 计量。本 run 的 profile
  未声明 tokenizer，故提案调用与全 run 一样使用保守 meter，规则一致。
- **可选角色的 cap 必须容得下真实请求**：`max_request_input_tokens_<role>` 现在同时是发送前上限。
  用保守 meter 量一个代表性 `narrative_organization` 请求（prompt 242 / payload 13 / schema 88）
  约 **343 token**；因此测试中的示意值取 1024（不是 256，256 会拒绝真实请求），
  真实 run 声明该角色时应按实际请求规模给足 cap。

### 验证

- `tests/test_agentic_proposal_call_accounting.py` **21 passed**（新增 7 项：durable started 在调用期间
  已可见、恢复后 unsettled 保留且 attempt 递增、外部角色 tally 不被采用、carry-over 保留未结算行、
  超限发送前拒绝且模型零调用、envelope cap/durable 路径绑定、注入 tokenizer 后按 tokenizer 规则计量
  且未注入时不伪造）。writer 相关套件 166 passed。
- 相关套件：proposal accounting + unified matrix + writer-unified + unified compiler **50 passed**。
- 冻结链复跑（节点 A 基线回归）：`.tmp/c2p-nodeb-metering-checkpoint-20260913/offline/`
  的规范报告与节点 A 报告 **sha256 完全相同**（`sha256:9bd4e535…`）——135 页 / 102 次调用
  （66/18/18）、archive `463c46ea…`、strict 仍只有三个 agenda partial 码、
  三阶段 `candidate_status=pass` 且 `candidate_admission_failure_codes=[]`；
  捆绑文件与输入身份写入 `summary.json`（23 个文件 sha256 + HEAD）。

节点 B 至此收尾；下一节点 C（受权的一次受控 EBCAR 正文入口运行）需按授权与 live admission 执行。

## 2026-09-13（节点 C）：受控 EBCAR authoring 实跑 —— 第一处真实阻塞及有界修复

授权与准入：按执行计划“后续运行由 Codex 在实际分片验收与既有授权范围内执行”和交付指导节点 C，
在本地已授权 runtime 上执行一次受控 EBCAR authoring；未做发布/D5/Verified 结论。

**preflight（已记录）**：`http://127.0.0.1:8006/v1` `/health` 200、模型 `qwen38-27b-nvfp4`、
context 131072、`num_requests_running=0`、`num_requests_waiting=0`、`kv_cache_usage_perc=0`；
profile `tests/live/profiles/qwen38_vllm_budgeted.example.env`（含 unified 预算段）。
证据：`.tmp/c2p-nodec-checkpoint-20260913/preflight_*.{txt,json}`。

**run 1**（`/tmp/c2p-nodec-ebcar-unified-20260913-202117`，exit 2，37 calls / 324182 tokens）：
- 阻塞：`research_closure_admission_failed:unified_core_intent_terminal_proof_missing:O-METHOD-MAINLINE-01-c8146479,O-STAGE-01-039a963a,O-STAGE-03-2c5bd758`。
- 诊断（离线复现，零模型调用）：`_writer_research_preadmission_failures` 在“fresh root 只有旧研究复制集”时
  确实产出上述三个码；加入 `candidate_handoff_v1` + `observation_promotion_ledger_v1` +
  `candidate_retry_ledger_v1` 后，handoff 认证通过（eligible=True、revalidation failures 为空）、
  preadmission failures **为空**。根因是**生产入口的复制边界**：`scripts/run_authoring_replay.py` 的
  `RESEARCH_COPY_ARTIFACTS` 早于 Candidate 交接产物，fresh root 里没有 Writer 必须认证的 Candidate 权威，
  于是回退到 strict terminal proof。
- 有界修复：`OPTIONAL_RESEARCH_ARTIFACTS` 增加 `candidate_handoff_v1`、`observation_promotion_ledger_v1`、
  `candidate_retry_ledger_v1`、`research_revision_journal_v1`（可选：缺失时行为不变、由 Writer 自身 fail closed）。
  回归测试 `tests/test_agentic_replay_execution_record.py::test_candidate_lane_research_authority_is_carried_into_the_fresh_root`；
  套件 24 passed。绑定真实输入的复制边界探针：`analysis/copy_boundary_probe.json`（`writer_would_block: false`）。

**run 2**（`/tmp/c2p-nodec-ebcar-unified-20260913-203506`，exit 2，37 calls / 324182 tokens）：
- research closure admission **不再阻塞**，进入统一主链并产出 `method_section_plan_v2.json`，
  随后在统一源码读取处失败：
  `unified_pipeline_failed:ValueError:unified_source_read_failed:unified_source_partition_excluded:conf/dataset/conteb_test_01MLDR.yaml;…`。
- 定位：`repo_snapshot.py:351-355` 把 `_EXCLUDED_SOURCE_KINDS = {vendor, generated, submodule,
  dataset_or_checkpoint}` 记为 `unified_source_partition_excluded` 并返回空；`publication_method_writer.py:2010-2020`
  把**任何** source-read failure 直接提升为 `ValueError` → 整条 unified lane 中止。
  `repository_source_manifest_v1` 共 37 条：`dataset_or_checkpoint` 16、`first_party_executable` 11、
  `documentation` 5、`configuration` 5；被排除集合含 `conf/dataset/*.yaml`、`data/real/*/preprocess.py`、
  `src/dataset/*.py`。
- 未做的决定：是否把“已声明的分区排除”与“完整性/可用性失败（逃逸、未登记、缺失、不可读、摘要漂移、symlink、binary）”
  分开——前者是可预期分类结果，后者必须继续中止。这触及 R2 的 fail-closed 语义，需明确后再改，
  不以放宽门禁换取一次通过。

证据汇总：`.tmp/c2p-nodec-checkpoint-20260913/nodec_evidence.json`（含两次运行的 blocker、用量、
代码状态摘要与修复前后对照）；两次运行都由同一 `src` 代码状态 `sha256:4fe7c0ba…` 绑定（运行中无漂移）。

### 节点 C 阻塞 2 的有界修复：分区排除 ≠ 完整性失败

run 2 的真实阻塞是统一源码读取把“清单已声明的分区排除”和“完整性失败”混为一谈：

- `repo_snapshot.py` 新增 `PARTITION_EXCLUSION_FAILURE_CODE` 与 `split_source_read_failures()`：
  以 `unified_source_partition_excluded:` 开头的记录归为**声明式分区排除**，其余（path escape/
  invalid、not-in-manifest、missing、unreadable、content/snapshot digest mismatch、symlink、binary）
  仍为阻塞失败。
- `publication_method_writer.py` 把源码门拆成 `_unified_source_read_failures()`：
  阻塞失败照旧 `raise ValueError("unified_source_read_failed:…")`（R2 语义不变）；
  分区排除改为写入已注册产物 `unified_source_partition_exclusions_v1`
  （`artifacts/research_product/…`，含 `excluded_paths` 与 `content_digest`）并在 `paths` 中可见，
  不再中止整条 unified lane。
- 语义边界：分区排除只是“清单从未承诺这些字节可读”，既不授权任何事实，也不把空文本当证据；
  需要这些文件的 consumer 会因此拿到空源文本，其后果由后续真实门禁决定（下一处阻塞若出现即按同一方式有界修复）。

测试：`tests/test_agentic_authoring_context_handoff.py` 新增
`test_partition_exclusion_is_not_an_integrity_failure`（混合输入下 integrity 失败仍阻塞、分区排除去重保留、
无 failure 的 reader 不崩、产物路径与注册名一致）；该文件 11 passed，
writer unified/legacy 套件 164 passed。

### 节点 C run 3（修复后）：阻塞前移一层，暴露真实的下游根因

`/tmp/c2p-nodec-ebcar-unified-20260913-205759`（exit 2，37 calls / 324182 tokens，代码状态
`sha256:09dd9499…`）：

- 分区排除修复生效：产物 `artifacts/research_product/unified_source_partition_exclusions_v1.json`
  写出 16 条被排除路径，unified lane 不再因它们中止。
- 新阻塞：`unified_pipeline_failed:ValueError:unified_live_admission_failed:mech_sym:f6cf5bdfe2ae16f0:operation_disposition_unresolved`。
- 逐层定位（全部来自该 run 的产物）：
  - `mechanism_context_completeness_v1`：`mech_sym:9773c5add7af1f92` → `[]`；
    `mech_sym:f6cf5bdfe2ae16f0` → `['operation_disposition_unresolved']`。
  - 注解后的闭包 disposition 统计：125 ops 全部分类（115 supporting + 10 absorbed）；
    185 ops 中 **2 个** `explicitly_unresolved`（reason `unresolved_detail:…:39` / `…:40`）。
  - 这 2 个操作是 `span:src/model/ebcar_dedicated_attention_model.py:171:171`（WRITE）与
    `:171:174`（CALL，`torch.zeros`），`guard=""`、`active_path_status="unknown"`——它们位于
    `if self.cfg.use_dedicated_attention:` 的 **else（ablation）分支**。
  - **根因（输入侧证据缺口）**：冻结的 `configuration_claims_v1` 只有 3 条，其中
    `self.cfg.use_dedicated_attention` 与 `self.cfg.add_positional_encoding` 都是
    `state=unresolved`、`unresolved_reason=config_access_unresolved:no_definition_or_entrypoint_value_evidence`。
    分支条件取值无法判定 → else 臂操作 active path unknown → detail `evidence_authority=unresolved`
    → `explicitly_unresolved` → 完整性门 fail-closed。
  - 附带发现的**权威分区矛盾**：同一清单把 `src/dataset/ebcar_dataset.py` 归为
    `dataset_or_checkpoint`（排除），而唯一一条已解析的默认值 claim（`EBCARDatasetReal.__init__`）
    的 definition span 正是 `span:src/dataset/ebcar_dataset.py:27:27`；`conf/` 侧的
    `conf/config.yaml`、`conf/retrieval_model/{contriever,e5}.yaml`、`conf/validation_dataset/conteb_val.yaml`
    在 configuration 分区内，却没有 claim 把其中取值链到 `self.cfg.*` 访问。

结论：这不是门禁缺陷，也不是 writer 侧可修的表达问题，而是**冻结输入缺少配置定义证据**（以及数据集模块的分区归属需要重新判定）。
按“不削弱门禁、真实阻塞按所属阶段有界修复”的规则，下一步需要先决定配置证据/分区归属的处理方向，
再继续推进 Candidate。

证据：`.tmp/c2p-nodec-checkpoint-20260913/nodec_evidence.json`（run 1/2/3 的 blocker、用量、
根因链、disposition 统计与配置 claim 原文）。

### 分区归属修正（用户决定：先判定 src/dataset/*.py 归属）+ 配置证据缺口定位

分区归属修正（`source_inventory.py`）：
- 旧规则把**任何**路径分片命中数据词表（`data/dataset/datasets/checkpoint/checkpoints/weights/models/artifacts/runs/outputs/results`）
  的文件判为 `dataset_or_checkpoint`，于是 `src/dataset/ebcar_dataset.py`、`src/models/*.py`
  这类**第一方实现**被排除出可读源码分区——而唯一一条已解析的默认值 claim
  （`EBCARDatasetReal.__init__`）的 definition span 恰好落在 `span:src/dataset/ebcar_dataset.py:27:27`，
  形成“权威分区 vs 配置证据”自相矛盾。
- 新规则 `_is_data_container_path()`：数据后缀（权重/数组/checkpoint）永远是数据；**可执行源码**只有位于
  **顶层**数据容器下才算数据（`data/real/x/preprocess.py` 仍是数据工具），
  因此 `src/dataset/*.py`、`src/models/*.py` 回归 `first_party_executable`；
  非源码文件（如 `conf/dataset/*.yaml`）行为不变，避免扩大本次修复范围。
- 回归测试：`tests/test_agentic_14_vertical_tests.py::test_first_party_packages_named_after_data_vocabulary_stay_readable`；
  相关套件 26 passed，`-k "scope or inventory or partition or source_kind"` 79 passed。

配置证据缺口（下一处真实阻塞的完整链条，已定位到能力边界）：
- 代码里**已有**该能力：研究工具 `inspect_configuration`（`research_tools.py:1325`，扫描
  `.py/.yaml/.toml/.json` 的配置绑定，`research_nodes.py:152` 归入 `{"config"}` 需求，
  `research_supervisor.py:829` 负责参数化），并有 packet/fact/配置编译器承接正向证据。
- 但冻结的 Run E 输入没有为 `self.cfg.use_dedicated_attention`/`self.cfg.add_positional_encoding`
  取得定义证据（`state=unresolved`），而这两个键确实定义在**可读的** `conf/config.yaml:18-19`
  （`add_positional_encoding: True` / `use_dedicated_attention: True`，configuration 分区）。
- 因此要拿到首份 Candidate，需要一次**当前入口的完整运行**（Research 真正为这些键调用
  `inspect_configuration` 并产出 packet→fact→claim），而不是继续回放缺证据的冻结输入；
  或用有界的研究续跑补齐这两个键。

结论（本轮交付）：A/B 已完成；节点 C 的受控 authoring 已取得第一处真实下游阻塞的完整因果链与
可复现证据（复制边界 → 分区排除 → 配置定义证据缺失），分区排斥语义按用户确认保留，
分区归属已按用户决定修正。下一步需决定完整 live 运行或研究续跑。

### 确定性配置取证触发（用户决定：先加触发，再跑完整 live）

问题：`inspect_configuration` 工具、packet/fact 承接与 `compile_configuration_claims` 都已存在，
但研究循环没有任何确定性规则要求为“门控分支的未解析配置键”取证，于是冻结输入里这两个键一直是
`unresolved`，first Candidate 被完整性门拦下。

实现（有界、可测、不触碰门禁）：

- `research_nodes.py` 新增 `branch_configuration_evidence_requirements(facts, configuration_claims)`：
  只对 `branches_on` 事实里出现的配置访问叶子键（`self.cfg.<key>` / `cfg.<key>` / `args.<key>` …）生成
  `configuration:branch_key:<key>` 需求；已被解析的 claim（`state ∈ {default, actual, conditional}`）
  不再要求；非 `branches_on` 事实不触发。
- 在 `_compile_candidate_node_impl` 编译出 `fact_set` 后调用它，把需求并入该 obligation 的
  `missing_information`；只要有此类需求，obligation 就**不得**标记为 `supported`
  （`obligation_terminal = all_targets_resolved and not configuration_requirements`），
  证据走 `_partial_evidence` 通道。这加强了 strict lane（partial 仍是 partial），不放宽任何门。
- `_resolved_missing_information` 既有词表已把含 “config/parameter/setting/option” 的需求归入 `config`
  类别，只有成功的 `inspect_configuration` 观测才能解除；`_select_action` 的既有启发式因此确定性地
  选择 `INSPECT_CONFIG`。
- `research_supervisor.py`：`DeterministicSupervisorBackend._configuration_key()` 从待办需求里取出叶子键，
  `inspect_configuration` 的参数由“全库扫描 `config_key=""`”改为传入该键，避免把关键键留给运气。

测试：`tests/test_agentic_branch_configuration_requirements.py` 3 项（生产者语义：未解析才要求、
已解析跳过、非分支事实不触发；路由：待办需求 → `INSPECT_CONFIG` 且 `config_key` 精确等于叶子键；
无需求时仍为通用扫描）；研究侧套件（supervisor/agent/cli/callback）**119 passed**；
全量静态 **3459 passed, 3 skipped**。

随后按用户决定启动**当前入口的完整 live 运行**（Research + unified authoring，8006）：
`python -c "... supervised_method_agent_main ..." run --repo <EBCAR> --author-intent <paperyaml3 EBCAR yaml>
--out /tmp/c2p-nodec-full-20260914-011114 --max-research-turns 60
--llm-profile tests/live/profiles/qwen38_vllm_budgeted.example.env --llm-model qwen38-27b-nvfp4
--authoring-context-mode unified --run-id c2p-nodec-full-20260914-011114`
（代码状态 `sha256:bcd1fdbe…`；preflight 记录在 `.tmp/c2p-nodec-checkpoint-20260913/preflight_full_*`）。

## 2026-09-14（当前执行计划 §15.4）：S1 入口统一与 S2 预算闭合

本轮沿现有 dirty worktree 推进，不重做 R0–R10，不修改 Research 冻结输入，也未把完整
Research 重跑作为 S1/S2 前置。

### S1 结果

- `python_behavior_adapter.py` 的分支祖先关系改为完整 enclosing-branch 路径，终止控制流不再产生
  伪顺序边；新增嵌套 `if/elif/return` 回归。
- `research_nodes.py` 的配置需求按完整访问身份匹配，`other.cfg.mode` 不再消除
  `self.cfg.mode` 的缺口。
- `mechanism_context_compiler.py`、`publication_method_writer.py`、`run_authoring_replay.py` 与
  离线矩阵共用当前源码派生图；历史图只作为显式历史 artifact 保存，不再作为 unified Writer 输入。
- replay 在重建图并通过确定性 Candidate/strict 分列预检后，才允许进入模型阶段；新增
  `--deterministic-preflight-only` 与预检产物/telemetry。

S1 证据：相同冻结 EBCAR 输入的离线矩阵保留三条 strict partial，Candidate handoff eligible；
当前图 `315 nodes / 542 relations`，历史图 `1263 nodes / 3056 relations`，当前图 digest 为
`sha256:42a68…`，无 graph/mechanism completeness failure。实际 replay 预检目录为
`/tmp/c2p-unified-repair-20260914-s1-replay-codex-03`，exit 0、模型调用 0，并写出
`artifacts/06_authoring/deterministic_preflight_v1.json`、`behavior_graph_rebuild_v1.json` 和
`authoring_rebuild_manifest_v1.json`。

### S2 实现与验证

- `proposal_call_accounting.py`：严格 meter 绑定 role/run/revision/envelope/profile/model，
  累计 calls/total/role input 在发送前检查；started tally 原子写入，写失败阻止 transport；
  corrupt/foreign/cross-run tally fail closed；未发送拒绝不计 spend；辅助 wrapper 与 page ledger
  共用 `06_authoring/invocations` 预算根。
- `unified_invocation_ledger.py`：统一读取 page receipts、旧/当前 plan reservations、started
  未结算尝试和 auxiliary tallies；未知原计划不按 0；`check_run_budget_before_send` 成为实际页与
  辅助调用的共同累计门。
- `narrative_organization_proposal.py`、`formalization_agent.py`、Writer/Realizer 实际 send
  boundary 均在 transport 前做预算检查；四角色 profile 未显式声明 auxiliary role 时走既有确定性
  fallback，不能被注入 caller 绕过。
- replay 只有 profile 显式声明完整 extra-role budget 时才启用 planner/verifier/proposal；当前
  `qwen38` profile 仍为四角色，预检 telemetry 标为 `auxiliary_budget.status=not_declared`。

S2 验证命令与结果：

- `python -m pytest -q tests/test_agentic_proposal_call_accounting.py tests/test_agentic_unified_context_compiler.py tests/test_agentic_formalization_guards.py tests/test_agentic_publication_method_writer_unified.py tests/test_agentic_narrative_architect_v3.py tests/test_agentic_replay_execution_record.py tests/test_agentic_unified_ten_project_offline_matrix.py -p no:randomly` → **147 passed**。
- `python -m pytest -q` → **3475 passed, 3 skipped, 7 warnings, 12 subtests passed**，exit 0。
- `python -m compileall -q src tests`、`git diff --check` → exit 0。
- 新增严格回归覆盖：累计调用/总 input 超额、未声明角色、tokenizer 缺失、损坏/跨 run tally、
  started 写失败，所有拒绝场景假 transport 发送次数为 0；正常场景 tally 额度守恒并可恢复。

S2 退出条件已满足。下一步只执行一次绑定当前代码/profile 的受控 S3 authoring；不作默认切换、D5、
Verified 或发布结论。

## 2026-09-14（§15.4 S3：实际入口受控 authoring 结论）

### 运行边界与入口

按 S3 退出条件，使用当前 `run_authoring_replay.py` 实际入口对冻结 EBCAR 输入只运行一次最终
受控 authoring；没有以完整 Research 重跑或配置补证作为前置，也没有切换默认路径。运行目录为
`/tmp/c2p-unified-repair-20260914-s3-codex-05`，命令绑定
`tests/live/profiles/qwen38_vllm_budgeted.example.env`、`qwen38-27b-nvfp4`、unified context，
单并发执行。

运行前 `/health` 与 `/v1/models` 均为 HTTP 200，模型身份为 `qwen38-27b-nvfp4`，上下文上限为
131072；运行前后 running/waiting、KV-cache pressure、preemption、abort/error 均为 0。运行期
Formalizer 完成 66/66，Writer 完成 18/18；Realizer 计划 18 项并写出 18 条 receipt，其中
16 项实际送达 caller，2 项在 caller 前因 authority unresolved 被拒绝并审计为
`sent_to_caller=false`。模型调用没有运行时中止或资源错误。

### 严格结果

本次未取得 Candidate：`execution_record.json` 的 `candidate_digest` 为空，未写出
`authoring_structural_exit_v1.json`，终止原因为：

`unified_consumer_task_incomplete:realizer:inv:realizer:MA-REV-mech_sym-9773c5add7af1f92:page:e3b02f...`

Realizer 的失败属于内容/证据绑定门失败，不是 transport 或预算绕过。18 条 receipt 的结果为：
16 条送达后失败、2 条严格的 pre-send authority rejection；主要失败计数为
`realizer_witness_text_missing` 7、`realizer_detail_out_of_scope` 5、
`realizer_authority_unresolved` 2，以及 formula/atom witness out-of-scope、required detail
missing、response not JSON 各 1。两个未解析 authority 对应冻结输入中
`self.cfg.add_positional_encoding` 与 `self.cfg.use_dedicated_attention` 的配置证据缺口；
它们仍按 strict partial/unknown 保持 fail-closed，未用配置补证或放宽匹配来伪造通过。

本轮为真实入口补上的修复包括：Realizer 嵌套 witness 使用精确的 Pydantic response schema；
Realizer 在 caller 前拒绝时写出 rejected receipt 和 output fragment；所有 pre-send rejection
不计入已发送 spend；相应生产/回归测试均已通过。这些修复改善了审计完整性，但没有放宽
Realizer 的内容、绑定或证据门。

### 验证与交付判断

- `python -m pytest -q` → **3479 passed, 3 skipped, 7 warnings, 12 subtests passed**，exit 0。
- `python -m compileall -q src tests scripts/run_authoring_replay.py` → exit 0。
- `git diff --check` → exit 0。
- S1/S2 退出条件已满足；S3 已按实际入口取得完整运行证据，但 Candidate 退出条件未满足，
  因此不声明 Candidate、Verified、D5、默认切换或发布就绪。

主要产物：

- `/tmp/c2p-unified-repair-20260914-s3-codex-05/execution_record.json`
- `/tmp/c2p-unified-repair-20260914-s3-codex-05/artifacts/06_authoring/realizer_plan_execution_v2.json`
- `/tmp/c2p-unified-repair-20260914-s3-codex-05/artifacts/06_authoring/realizer_receipts_v2.json`
- `/tmp/c2p-unified-repair-20260914-s3-codex-05/artifacts/06_authoring/deterministic_preflight_v1.json`

剩余工作边界明确为 Realizer 的语义/证据绑定修复，以及两个配置 authority 缺口的后续取证；本轮
不继续重复 live，不把严格 partial 改写为成功。

### 2026-09-14：S3-20 终态独立复核与执行文档更新（本轮无生产代码修改）

用户要求判断当前进展并指导修复。本轮读取 S3-18/19/20、当前发送/解析/预算/正文验收路径，
模型调用 0；没有启动新的 live，也没有改写旧 run。

- S3-20 已继续落盘为 116 completed / 116 started、113 次发送、exit 2，execution record 存在；
  最终失败是 Realizer 总预算拒绝，Candidate 和 structural exit 仍不存在。
- Formalizer 34 main + 32 repair 全失败、0 accepted packages；Writer 最后响应为 5 空、3 仅标题、
  10 含非标题文本（未等同内容验收）；Realizer 三次 witness repair 均成功，完成 15/18 页。
- 代码反例：Formalizer 六个 required 字段缺 properties/类型，system/user 重复 payload；
  空 SSE finish 提前抛错漏读 terminal usage；repair 超声明 reserve 且未保护后续 primary；
  Writer receipt 在正文验证前按非空文本记 complete。已知 provider input 也高于全账本估算。
- 已更新统一执行计划 §15.6、顶部/状态表/附录 B 与 docs/README.md：保留 S1/S2，按失败诊断与
  Formalizer 合同 → Writer 内容事务 → 跨 phase 预算/真实计量 → 经验证恢复及完整 Candidate 收口。
  本小节更新此前 S3-05 的“剩余工作边界”，不宣称这些新发现已经修复。
- `python .tmp/c2p-s3-review-20260914/review.py`：exit 0；结果、434 个代码/产物摘要索引及
  8 个 Writer 失败页 + 1 个 Formalizer 诊断样本保存在该工作区目录。样本不是认证恢复包。
- `python -m pytest -q tests/test_llm_runtime.py -k stream tests/test_llm_section_writer.py -k 'stream' -p no:randomly`：
  exit 0，6 passed / 115 deselected。假 SSE 与预算反例另由上述脚本重现。未重复全量静态。
- `git diff --check`：exit 0；新文档链接/空白检查及来源代码摘要稳定性另行核对。

## 2026-09-14（§15.6：失败请求合同、内容验收与预算调度修复）

本轮按用户指定顺序处理 S3-20 暴露的问题；没有重建旧行为图、没有完整 Research 重跑、没有启动
新的 live 或 Candidate 链路。

- `response_schemas.py` 与 `unified_context_compiler.py` 现在对 Unified Formalizer 使用闭合的
  `UnifiedFormalizerResponseV2`：外层 `results` 与每行六个 required 字段均有明确类型，未知字段
  fail closed；`formalization_agent.py` 在默认解析入口再次验证该 schema。Unified V2 请求把技术页
 作为唯一 structured input，prompt 只保留角色合同，避免同一页在 system/user 两处重复计量。
- `client.py`、`formalization_agent.py`、`section_writer.py` 和统一 invocation ledger 保留空流/部分流
  的 partial text、finish/provider finish、terminal usage、事件诊断与 provider diagnostics；SSE 在
  finish 后继续读取 usage-only terminal event。Provider usage 缺失时仍使用已记录的确定性 request
  accounting，并在 run budget state 标为 `partial`，不把估算伪装成已验证 provider usage。
- Writer request record 新增明确的 transport response 状态；`task_status` 不再被内容验收回写为
  “complete”。内容验收另写 sidecar，分别记录 `content_acceptance_status`、
  `repair_committed`、`resume_eligible`。空/阻塞的 primary attempt 也保存 rejected sidecar；只有
  通过段落 transaction/evidence 验收的修复才可成为可复用 incumbent，resume 只读取 accepted
  sidecar。
- Writer section aggregate 现在同时要求 transport response 非空与 `content_accepted=true`；因此
  标题 JSON、仅非空文本或被拒绝的正文不会伪装成完成页。内容 repair 仍由原 invocation 的 bounded
  retry reserve 计量，并保护尚未发送的 primary pages；跨 revision 的 completed receipts、started
  未结算尝试和 provider-usage 缺失状态继续由统一 ledger 汇总。
- 增加空流 late-usage、Formalizer schema、Writer 空/标题修复、rejected/accepted content sidecar、
  repair reserve 与 resume 资格回归夹具。一次修复夹具产物保存在
  `/tmp/c2p-writer-repair-budget4/test_writer_content_repair_use0/`，包含 primary rejected、repair
  accepted 的 content-acceptance sidecar 与两次 transport receipt。

验证结果（本轮新执行）：

- `python -m pytest -q tests/test_agentic_publication_method_writer_unified.py tests/test_llm_runtime.py tests/test_agentic_unified_context_compiler.py tests/test_llm_section_writer.py tests/test_r6_portability_and_budget_hygiene.py -p no:randomly` → **164 passed**。
- `python -m pytest -q tests/test_agentic_formalization_guards.py -p no:randomly` → **53 passed**。
- `python -m pytest -q tests/test_agentic_replay_execution_record.py tests/test_agentic_runner.py -p no:randomly` → **36 passed**。
- `python -m compileall -q src tests`、`git diff --check` → exit 0。

本轮仍未取得有效 live Formalizer package，也未运行完整 Candidate；S3 的退出条件尚未满足，不能据此
声明 Candidate、Verified、D5 或发布就绪。下一步应先用受控入口验证一个有效 package 和一个空页/标题页
内容修复，再决定是否进入完整链路。

### §15.6 夹具收口补充

随后新增的两个实际 Writer 夹具分别覆盖空流页与标题-only 页。页面闸门仅在同一 immutable
invocation 的 primary 为空、且 bounded repair 返回非空响应时恢复；没有 repair 或 repair 仍为空时
继续 fail closed。最新组合回归为 **254 passed**（上述 Writer/LLM/预算/Formalizer/replay 集合），
`compileall` 与 `git diff --check` 仍为 exit 0。夹具产物位于
`/tmp/c2p-writer-empty-title2/`，每个 case 均有 primary rejected 与 repair accepted sidecar。

## 2026-09-14（§15.6 执行推进：T1 真实入口通过，T2/T3 保持边界）

在不修改 S3-20 冻结目录、不重建旧行为图、不启动完整 Research/Candidate 的前提下，继续执行
§15.6 的受控验证。

- 旧的 S3-20 Formalizer plan 在当前入口被 request-envelope digest 检查拒绝，
  `/tmp/c2p-s3-t1-formalizer-micro-20260914-01/formalizer_microtest_result.json` 记录
  `actual_calls=0`；这证明旧计划不能被当前合同直接复用，也没有把旧摘要当作当前产物。
- 按当前源码重建 plan 后，T1-04 在同一冻结 archive/manifest 上实际发送 1 个 Formalizer main，
  消费 1 个真实结构化响应，得到 1 个通过来源/条件/公式校验的 package；`repair=0`、
  `receipt=1`、`task_failures=[]`。结果在
  `/tmp/c2p-s3-t1-formalizer-micro-20260914-04/formalizer_microtest_result.json`，计划摘要为
  `sha256:1170f8316e934f1f0bc72a6822cc34e6322006e8358e0398ff2984401c90ca0b`，请求/响应与
  provider finish/usage 诊断均按 invocation sidecar 保存。此前两次各含 main+repair 的诊断微测
  暴露了复合 `RESHAPE -> WRITE` 的 LaTeX 等价箭头问题，已由提示约束和顺序链校验收口。
- 复核冻结 S3-20 的 Writer fragments：5 页两次均为空流，3 页为标题-only，10 页含非标题文本；
  这些仍是文本形状，不是内容/绑定验收。当前生产入口的空页与标题页夹具均生成 rejected primary、
  accepted bounded repair、`resume_eligible=true` 的 sidecar，产物位于
  `/tmp/c2p-writer-empty-title2/`；但尚未把这两个修复请求重新发送到真实模型，因此真实八页的
  T2 退出条件仍未满足，也不将旧 `complete` receipt 直接升级为可复用正文。
- 新增 provider-free 的真实冻结页回放
  `.tmp/c2p-s3-t2-replay-20260914/t2_replay_result.json`：从 S3-20 的实际 writer manifest、
  narrative plan、page projection 和当前 Writer schema 取一个空页与一个标题页，把历史 primary /
  repair 响应送入当前低层入口。4 个调用均走 `unified_writer_page_v2`，两个 bounded repair 均
  `writer_repair_commits=0`，`page_commit_count=0`、`resume_eligible_page_ids=[]`；该证据证明
  当前闸门不把旧空/标题响应升级为正文，但不冒充新的 provider recovery。
- 修正统一 ledger 的计划持久化：`is_repair` 不再在读取 `plans/*.json` 时丢失，future-primary
  预留不会把 repair 槽误算为主请求。新增反例覆盖 primary 100 / repair 500 的计划形状；累计
  revision、未知 started、最小扣账、repair reserve 与跨 phase 保护回归一并通过。
- 对旧 S3-20 invocation ledger 用当前读取器做只读审计，状态明确为 `provider_usage_status=partial`，
  113 个已发送 receipt 缺 provider usage，确定性 request accounting 为 1,990,033 input tokens；
  这只是保守账本估计，不被报告为已验证真实 token，故 T3 的真实计量退出仍保持未完成。
- 原计划再做至多 1 次真实 Writer repair；按 §16.3 先检查 8006 时，`/health`、`/v1/models` 和
  metrics 均返回 connection refused（HTTP 000），进程列表没有 vLLM/uvicorn。没有启动服务、没有
  发送新的 provider request，也没有把 runtime 不可用误记为 Writer 失败；对应 preflight 输出在
  `/tmp/c2p-s3-t2-live-health-20260914.txt` 与 `/tmp/c2p-s3-t2-live-models-20260914.json`。

本次新验证命令：

- `python -m pytest -q tests/test_agentic_unified_context_compiler.py tests/test_agentic_publication_method_writer_unified.py tests/test_llm_runtime.py tests/test_llm_section_writer.py tests/test_r6_portability_and_budget_hygiene.py tests/test_agentic_formalization_guards.py tests/test_agentic_replay_execution_record.py tests/test_agentic_runner.py -p no:randomly --basetemp=/tmp/c2p-contract-final-focused-20260914` → **256 passed**。
- `python -m pytest -q tests/test_agentic_unified_context_compiler.py -k 'future_primary_reservation_excludes_repairs or run_reservation_is_debited_by_retries_and_resume' -p no:randomly --basetemp=/tmp/c2p-future-primary-budget-20260914` → **2 passed**。
- `python -m compileall -q src tests`、`git diff --check` → exit 0。

当前结论：T1 已有真实有效 package；T2 真实失败页的正文恢复和 T3 provider usage/计量仍未闭合，
因此不启动完整 Candidate。S3-20 的 execution record、失败样本、旧 receipts 和已有 Realizer
witness 修复继续保留，Candidate/Verified/structural exit 均不宣称。

## 2026-09-14（§15.6 continuation：runtime wait 下的 T3 收口准备）

本次继续轮询指定 8006 runtime：`/health`、`/v1/models`、metrics 均 connection refused，未启动
服务、未发送 provider request。为 runtime 恢复后的单步继续，新增
`.tmp/c2p-s3-t2-live-repair-20260914/live_repair.py`：它只接受 fresh output root，先做模型/队列
preflight；primary 使用冻结空页响应，仅允许一个 `retry_max_attempts=1` 的真实 bounded repair，
preflight 失败即 provider call=0。

同时增加缺 usage 的预算回归：有发送 receipt 但 `provider_usage=None` 时，ledger 必须报告
`provider_usage_status=partial`，保留 request accounting 计费并报告 missing input tokens，不能把
该请求当成免费。该反例与 future-primary/repair 排除、累计 reservation 回归本次为 **3 passed**；
live probe 尚未执行，故不把脚本准备误报为 T2 恢复。

## 2026-09-14（§15.6 continuation：repair sidecar 与 resume 资格收口）

运行时仍未恢复，本片没有启动服务、没有发送新的 provider request，也没有改写冻结 S3-20。针对
Writer 失败合同继续做了一个方向内的离线修复：

- `llm/section_writer.py` 的 attempt sink 不再只记录空/blocked 响应，而是把每个 primary/representation
  attempt 写入 content sidecar；bounded repair 若为标题-only、空流、事务拒绝或无单调进展，则在
  不修改送回 Writer 的响应前，以 rejected 结果持久化该 repair attempt。
- `agentic/publication_method_writer.py` 不再按最大 attempt 或 response hash 盲选 receipt；同一
  response hash 在 primary/repair 间重复时，按尚未有 sidecar 的 attempt 绑定。最终 accepted
  callback 在 sidecar 已存在时不重写它，因此不会把有效 incumbent 覆盖到未提交 repair 上。
- 新增 `test_rejected_nonempty_writer_repair_is_not_resume_eligible`：真实统一 Writer producer→consumer
  入口注入 primary 空流与 repair 标题-only，两个 sidecar 均为 `content_acceptance_status=rejected`、
  `resume_eligible=false`，并验证同一 writer plan 的 `build_resume_plan` 返回 `execute`；这不是
  provider recovery，也不将失败页升级为正文。

验证（本片新执行）：

- `python -m pytest -q tests/test_agentic_publication_method_writer_unified.py tests/test_llm_section_writer.py -p no:randomly --basetemp=/tmp/c2p-writer-contract-20260914-r1` → **116 passed**。
- `python -m pytest -q tests/test_agentic_unified_context_compiler.py tests/test_agentic_publication_method_writer_unified.py tests/test_llm_runtime.py tests/test_llm_section_writer.py tests/test_r6_portability_and_budget_hygiene.py tests/test_agentic_formalization_guards.py tests/test_agentic_replay_execution_record.py tests/test_agentic_runner.py -p no:randomly --basetemp=/tmp/c2p-contract-final-focused-20260914-r3` → **258 passed**。
- `python -m pytest -q tests/test_agentic_unified_context_compiler.py -k 'future_primary_reservation_excludes_repairs or missing_provider_usage_without_zeroing_spend or run_reservation_is_debited_by_retries_and_resume' -p no:randomly --basetemp=/tmp/c2p-budget-boundary-20260914-r3` → **3 passed**。
- `python -m compileall -q src tests .tmp/c2p-s3-t2-replay-20260914 .tmp/c2p-s3-t2-live-repair-20260914`、`git diff --check` → exit 0。

当前阶段结论不变：T1 的有效 Formalizer package 保留；T2 真实空/标题页仍无新的 provider 内容，
T3 旧 run 的 113 个缺 usage receipt 仍为 `provider_usage_status=partial`，无 Candidate、无
structural exit、无 Verified。8006 恢复后仍按既有 fresh 单次 Writer repair probe 继续，不做完整
Research 或旧图重跑。

## 2026-09-14（§15.6：T2 两个受控 live repair 样本）

本片先在 sandbox 内检查 8006，Python/`curl` 因 localhost 网络权限失败；随后通过只读 escalated
preflight 确认 runtime 已恢复：`/health=200`、`/v1/models=200`，模型为 `qwen38-27b-nvfp4`、
`max_model_len=131072`，metrics 显示 running/waiting/KV/preemption 均为 0。未启动服务。

使用同一 frozen S3-20 Writer page projection、schema 与输入，执行两个 fresh、每个最多一次真实
repair 的 probe：

- 空页结果：[`r3/writer_repair_result.json`](/tmp/c2p-s3-t2-live-repair-20260914-r3/writer_repair_result.json)。
  1 次真实 repair；`finish_reason=stop`、`provider_finish_reason=stop`、`usage_seen=true`，
  prompt 50,220 / completion 1,192。模型返回 heading-only，内容/目标 contract 拒绝，
  `writer_repair_commits=0`，section incomplete。
- 标题页结果：[`r5/writer_repair_result.json`](/tmp/c2p-s3-t2-live-repair-20260914-r5/writer_repair_result.json)。
  修正 frozen primary 的 blocked 标记后重新执行 1 次真实 repair；usage 为 prompt 68,831 /
  completion 1,302，模型返回约 952 字正文，但缺 required detail witness，
  `required_target_contract` 拒绝，`writer_repair_commits=0`，section incomplete。
- r4 曾在修正 title primary 标记前发送 1 次 provider request，目录
  `/tmp/c2p-s3-t2-live-repair-20260914-r4/` 保留作 superseded diagnostic，不作为验收证据。

本片还修复并回归了一个低层 Writer 闸门：repair 仍携带 typed content failure 时不得因非空而
增加 `writer_repair_commits`。新增回归 `test_unified_v2_content_failed_repair_is_not_counted_as_commit`。

验证（本片新执行）：

- `python -m pytest -q tests/test_agentic_unified_context_compiler.py tests/test_agentic_publication_method_writer_unified.py tests/test_llm_runtime.py tests/test_llm_section_writer.py tests/test_r6_portability_and_budget_hygiene.py tests/test_agentic_formalization_guards.py tests/test_agentic_replay_execution_record.py tests/test_agentic_runner.py -p no:randomly --basetemp=/tmp/c2p-contract-final-focused-20260914-r4` → **259 passed**。
- `python -m compileall -q src tests .tmp/c2p-s3-t2-replay-20260914 .tmp/c2p-s3-t2-live-repair-20260914`、`git diff --check` → exit 0。
- escalated read-only post-check：runtime idle，`num_preemptions_total=0`。

结论：两个真实样本都产生了可解释的失败诊断，但没有正文通过内容/绑定门，因此 T2 不结项；
T3 provider usage/跨 phase 预算仍未闭合，Candidate、structural exit、Verified 均不存在。下一步
只能在既有 fresh 受控证据上修复明确的输出/绑定问题并重新验证，不能直接启动完整 Candidate。

## 2026-09-14（§15.6 continuation：deterministic revalidation 与预算边界）

本片不重跑旧行为图、不修改 frozen S3-20，也不新增 provider request。现行代码对实际保存的
[`r6 live response`](/tmp/c2p-s3-t2-live-repair-20260914-r6/writer_repair_result.json) 做
provider-free 重验证：24 个 required atom witness 全部绑定，推导 detail
`detail:mech_sym:9773c5add7af1f92:13`，无失败项，段落事务有效，正文 721 字符。r6 的原始 live
结果仍标记为当时入口下未提交；本次只是证明修复后的当前入口能够验收该响应，未把它写回 live
receipt，也未计入新的 provider 成功。

本片修复/固定了 V3 `detail_id` 的保留、closed exact-excerpt 的受限语义回退、条件 clause
锚点，以及 required atoms 全部完成时推导 detail witness 的 binder/assessor 一致性。预算回归
新增并通过：repair 不能挤占跨阶段 future-primary 预留；超过 retry reserve 必须在发送前
拒绝；缺失 usage 维持 conservative/partial 状态，不清零、不伪造精确值。

验证（本片新执行）：

- `python -m pytest -q tests/test_agentic_unified_context_compiler.py tests/test_agentic_publication_method_writer_unified.py tests/test_llm_runtime.py tests/test_llm_section_writer.py tests/test_r6_portability_and_budget_hygiene.py tests/test_agentic_formalization_guards.py tests/test_agentic_replay_execution_record.py tests/test_agentic_runner.py -p no:randomly --basetemp=/tmp/c2p-contract-t2t3-20260914-r5` → **264 passed**。
- 两项预算边界选择性回归 → **4 passed**；此前 124 项 Writer/binder focused 集合亦通过。
- `python -m compileall -q`（相关 `src/`、`tests/` 与 probe fixtures）、`git diff --check` → exit 0。

当前产物状态：T1 有效 Formalizer package 保留；r3 空页仍是内容失败，r5 标题页 live 请求仍未
提交，但 r6 实际响应已通过当前代码的离线内容/绑定验收；没有 Candidate。T3 的代码闸门已覆盖，
但旧 run 仍有 113 个 usage 缺失，ledger 为 partial，保守 input 计量 1,990,033，且历史
Writer repair 已花费 381,539、超过 200,000 声明 reserve；因此下一轮完整 plan 的真实计量、
跨阶段预算和 profile 上限尚未闭合。本片未修改 profile、未启动完整 Research/authoring。

## 2026-09-14（S3.6 独立复核：错误绑定反例与执行纠偏）

本轮回应用户“这些操作是不是改坏了”：只做代码/产物复核和离线探针，未修改生产代码、
profile、测试文件或既有 run，provider 请求 0。当前工作区包含后续 r3–r10 与 profile
提额，较早状态按各自时点解释；已更新 docs/README.md 和统一执行计划 §15.6.4。

确认 P1：新增 `_exact_excerpt_overlap` 在原语义锚点未通过时允许 3 个词形/0.30 重叠
替代事实绑定。源码要求 `embeddings + bias + residual`，正文写成相乘，当前 Binder +
assessor 仍 valid 并推导 detail；只在探针内禁用此新增回退则拒绝。真实 r6 页中加法
operation 的 witness 实为“保持 batch/sequence dimensions”；将求和改成相乘也仍获
24 witnesses、无失败。这不证明完整 Candidate/Verified 已错误放行，但局部验收已退化。

确认微测缺口：现有脚本直接调用低层 Writer/LLMClient，未走统一预算、content receipt、
resume 与生产 transaction assessor。实际 r6 响应局部 normalization 通过，当前低层
完整协议回放仍 repair commit 0、no-progress 1、incomplete；primary 的历史 `_p1__f1`
与当前 `_p1` 不兼容。不能把局部 normalization 当作统一入口恢复成功。

可见 Writer 微测有 7 次 provider usage（prompt 444,666 / completion 8,432），r7 缺
key 未发送也被脚本计为 provider_calls=1；r3/r8、r6/r9 请求和响应摘要均分别相同。
当前 profile 已提到 2,500,000 总额、Writer 400,000 / Realizer 100,000 reserve，
生产计量仍默认 UTF-8/4。停止未变化样本重跑，先收紧错误绑定、对齐实际统一入口，再校准
完整预算。保留 Formalizer schema、流式诊断、空/标题拒绝、账本分层和预算保护。

证据目录：`.tmp/c2p-s36-independent-review-20260914/`，含 review.md、probe.py、
probe-result.json、microtest-inventory.json、focused-tests.log、code-index.json；
7 个生产文件及当前微测脚本/profile 的副本在 code-snapshot，探针前后生产摘要一致。

新执行验证：

- `python .tmp/c2p-s36-independent-review-20260914/probe.py` → exit 0；上述反例成立，模型调用 0。
- `python -m pytest -q tests/test_agentic_detail_atom_binder_and_trace_v2.py tests/test_llm_section_writer.py tests/test_agentic_publication_method_writer_unified.py tests/test_agentic_unified_context_compiler.py tests/test_llm_runtime.py -p no:randomly` → exit 0，**173 passed**（7.43s）。现有回归未覆盖新反例。
- T1 `read_all_completed_receipts(..., strict=True)` → 1 个已发送 accepted/complete receipt，provider 诊断摘要链通过，绑定 prompt 3,787 / completion 1,114；保留一个真实 accepted repository-derived package 的局部成果。
- `git diff --check` → exit 0；新增证据链接存在，未重跑完整静态、Research、live 或 Candidate。

## 2026-09-14（S3.7 操作指引：计量接线与单页真实验收）

回应用户“现在真实测试？”及“按什么操作”：本轮核对实际代码和 S3.7 校准产物，更新统一
执行计划 §15.6.5 与 README 导航，交付可由执行者实施的范围、预算、命令交付要求和验收步骤。
未修改生产代码、profile 或测试，未调用 `/tokenize` 或模型生成接口。

确认当前三个历史错误加法反例（相乘、漏加数、否定加法）经 Binder + assessor 均 invalid，
rendered_detail_ids 为空；这是本轮新执行的零模型检查。178 passed/compileall 是执行者报告，
本轮没有重复跑该集合。确认 `--resume` 当前是 section 选择，尚无已验收的单页统一 CLI；
不能把旧低层 live_repair.py 当作当前生产提交和恢复验收入口。

读取 `/tmp/c2p-s37-calibration-20260914/`：18 个 Writer primary 共 828,590 chat tokens；
超 60,000 的三页分别 66,578、68,323、73,618；选定原空页 02a75… 为 49,678。
校准使用本地服务 `/tokenize`、记录生成调用 0；这次只读其文件，并未重新请求服务。
5 个源文件保存到 `.tmp/c2p-s37-calibration-evidence-20260914/`，source-index.json 记录摘要。

操作单要求先把 wire/tokenizer 身份接入 plan 与实际发送门，再提供复用统一 capturing
caller/assessor/sidecar/resume 的单页诊断入口及 prepare/live/resume 实际命令。提议独立
微测 Writer 最多 2 次生成、单请求 input 60,000、run input 120,000（含 repair reserve
60,000），output 最高 8,192、context 131,072；不是修改完整 run profile 或宣布 live 准入。
微测和整篇验收分别报告。全阶段和 repair 预算测完后再决定配置/分页及完整 authoring。

`git diff --check` → exit 0；本轮文档与证据更新未启动 live。

## 2026-09-14（S3.7 continuation：真实计量、单页入口与受控 live）

本轮按统一执行计划 §15.6.5 先完成代码接线，再运行真实 8006。未重做旧行为图、Research
或完整 authoring。

实现内容：

- 新增 `src/code2paper/llm/tokenizer.py`，通过 8006 `/tokenize` 计量实际 OpenAI-compatible
  chat wire sequence，并冻结 model/base URL/runtime identity；缺 tokenizer、identity mismatch
  或超限在 provider send 前拒绝。
- `unified_context_compiler.py`、`unified_context_models.py` 使用同一 chat-template meter；
  `section_writer.py` 暴露生产同构 Writer request 构造。
- 新增 `scripts/run_unified_single_page_writer.py`，提供 `prepare`、`live`、`resume`；只选
  原空页 `page:02a75f6a…` / section `MA-REV-mech_sym-f6cf5bdfe2ae16f0`，使用 production
  budget gate、receipt、content acceptance、repair assessor 和 resume plan。
- 更新计量回归与旧 fixture tokenizer identity；没有放宽内容 gate。

验证：

- `python -m pytest -q tests/test_agentic_unified_context_compiler.py tests/test_llm_section_writer.py tests/test_llm_writer_section_repair.py` → **134 passed**。
- `python -m pytest -q tests/test_agentic_publication_method_writer.py tests/test_agentic_publication_method_writer_unified.py` → **162 passed**。
- 相关 `py_compile` 与 `git diff --check` → exit 0。

真实命令与产物：

```bash
python scripts/run_unified_single_page_writer.py prepare \
  --frozen-root /tmp/c2p-unified-repair-20260914-s3-codex-20 \
  --output /tmp/c2p-s3-single-page-20260914-02a75-r2 \
  --profile tests/live/profiles/qwen38_vllm_budgeted.example.env
python scripts/run_unified_single_page_writer.py live \
  --output /tmp/c2p-s3-single-page-20260914-02a75-r2 \
  --profile tests/live/profiles/qwen38_vllm_budgeted.example.env
```

prepare 真实访问 8006，`/health`、`/v1/models`、`/metrics` 均 200，模型
`qwen38-27b-nvfp4`、context 131072；最终 wire input **53,931**，生成调用/发送均 0。
live 真实发送 **2 次**：1 primary + 1 repair；meter input 分别 **53,931 / 55,013**，
provider usage 分别 `49,666/1,370/51,036` 与 `50,748/1,393/52,141`（prompt/completion/total），
两次均 `finish_seen=true`、`usage_seen=true`、`structured_complete`。

结果：两次真实 receipt 和两份 content acceptance sidecar 都保留，但内容均 rejected，
`writer_repair_commits=0`、`writer_repair_no_progress_stops=1`，没有
`single_page_submission.json`，因此没有执行 resume，也没有把页记为完成。失败具体为：模型
输出 paragraph 仍带 heading，验收清理 heading 后判定 body non-substantive；required detail
10/22 的完整 atom witness contract 也未闭合。该失败不是空流、usage 缺失或预算超限；按停止
条件不换目录、不重复同一请求，后续必须先修输出合同/完整 witness 交付再申请新的 live。

## 2026-09-14（真实单页失败复核：§15.6.7 下一步合同修复）

本轮回应用户“下一步呢”，核对 r2 的实际请求、原始响应、24 个 required atoms 和当前代码，
只运行离线探针/严格 receipt 读取，未修改生产代码、旧 run 或调用模型。执行指引已写入
统一计划 §15.6.7，README 已索引。

发现：writer_skill 同一 prompt 要求 paragraph 不含 heading，又无条件要求以 H2 开始。
两份真实输出把已知 heading 与正文粘连；仅在诊断副本移除该精确前缀，保留全部正文词，
得到 1,369/1,532 字符，“无正文”失败消失，detail 仍缺失。故不能将本次描述为模型没写正文。
detail 10/22 各有 11/13 个 required atoms，分离标题后当前只绑定 4/6 个；repair 包只包含
两个 aggregate detail，没有展开各个缺失 atom 的原因。

确认新的算术检查适用范围错误：源码中任意 `+` 即触发整体加法验证，detail 22 的 torch.zeros
调用参数内 `+1` 被当作顶层求和；13 个 atoms 中 11 个即使用原授权源码摘录也被该检查拒绝。
应修表达式/target 结构分类并保留之前错误加法反例拒绝，不再按词汇阈值放宽。
V2 的低层 Binder 明确禁用，而 prompt 承诺 separate Binder；如需语义 Binder，应进入已有
显式 phase/预算/receipt，不恢复隐藏模型调用。单页脚本仍有自行实现的 caller/assessor/sink，
下一片应与生产共用事务验收实现并验证同响应一致性。

计量表述纠正：53,931 / 55,013 是含 schema/wrapper 的预算 input；provider prompt 为
49,666 / 50,748。真实发送两次的证据有效，既有零提交状态保留，不执行无提交的 resume。

验证与证据：

- `python .tmp/c2p-s38-next-step-review-20260914/probe.py` → exit 0，provider_calls=0；结果为 inspection.json，含缺失 atom 列表、前后失败、源码摘要和原文调用计量。
- `read_all_completed_receipts(..., strict=True)` 对 r2 → 2 个 receipt 摘要链通过、sent_to_caller=2。
- `git diff --check` 与新增链接检查 → exit 0；未重新跑完整静态或 live。

## 2026-09-14（§15.6.8 合同修复离线验证与 r3 单页真实验收）

本片按用户指定顺序执行：先离线回放两份冻结真实响应，再在新目录 prepare，随后只做一次
同页 `1 primary + 1 repair` live。没有重做旧行为图、Research 或完整 authoring；未执行无提交
resume。

实现与验证：

- 修正 Writer 的 section/paragraph heading 合同，并在生产 normalizer 中只恢复已知 heading；
  修正顶层加法识别，使 `torch.zeros` shape 内 `+1` 不再误伤，同时保留相乘、漏加数和否定
  加法拒绝；repair packet 展开逐 atom 缺口、候选 span、失败原因和 Writer/Binder owner；
  单页脚本改用生产共享 content assessor/progress assessor。
- `python scripts/validate_unified_single_page_frozen_responses.py --run /tmp/c2p-s3-single-page-20260914-02a75-r2 --output .tmp/c2p-s39-contract-repair-20260914/inspection.json`
  → exit 0，`provider_calls=0`，正文 1,369/1,532，valid atoms 8/24、10/24，detail 22 为
  13 个 shape atoms，四个加法反例均通过；完整 detail 仍拒绝。
- `python -m pytest -q tests/test_llm_section_writer.py` → 107 passed。
- `python -m pytest -q tests/test_agentic_publication_method_writer_unified.py` → 18 passed。
- `python -m pytest -q tests/test_llm_section_writer.py tests/test_agentic_publication_method_writer.py tests/test_agentic_publication_method_writer_unified.py`
  → 269 passed, 6 warnings。
- `python -m pytest -q tests/test_agentic_unified_context_compiler.py tests/test_agentic_detail_atom_binder_and_trace_v2.py`
  → 34 passed。
- `python -m compileall -q src tests scripts`、`git diff --check` → exit 0。

真实执行：

- prepare 输出：`/tmp/c2p-s3-single-page-20260914-02a75-r3/prepare_result.json`，状态 pass，
  8006 `/health`、`/v1/models`、`/metrics` 均 200，模型 `qwen38-27b-nvfp4` / context 131072，
  同一 tokenizer identity，meter input 53,969，generation/provider sends 0。
- live 输出：`/tmp/c2p-s3-single-page-20260914-02a75-r3/live_result.json`，状态 fail，实际
  provider sends 2。两次 provider usage 为 `49,704/1,260/50,964` 和 `53,909/1,269/55,178`
  （prompt/completion/total），meter input 为 53,969 和 58,174，均 finish/usage 完整、transport
  accepted；但 content acceptance 均 rejected，detail 10/22 required target contract 未闭合，
  repair commit 0、no-progress stop 1。
- `/tmp/c2p-s3-single-page-20260914-02a75-r3/single_page_submission.json` 不存在，两个
  sidecar 均 `resume_eligible=false`，故未发送 resume。该页和完整 Candidate 保持 incomplete；
  下一步需先补有账的 atom 内容/绑定闭合路径和离线验收，再申请新的 changed-basis live。

## 2026-09-14 23:38 全流程独立复核与执行优先级更新

回应用户要求重新梳理流程、产物、方向和距最终目标的差距。本次未修改生产代码，未启动模型、Research 或 live，
未干预已经运行的全文 r5。详见 `docs/research_to_method_end_to_end_status_review_2026-09-14.md` 和统一计划 §15.7；
README 已更新，早期 §15.6/T1/T2 记录保留历史性质。

- 绑定证据：`.tmp/c2p-e2e-flow-review-20260914-01/inventory.json`、`source-index.json`、`flow-findings.json`；
  18 个代码/配置文件副本与 SHA-256，218 个产物快照。快照时最新已结束全文 r4 exit 2，Writer 发送 0、无 Candidate；
  单页 r7 有提交/resume；全文 r5 为 20 completed / 21 started、无终态，不能扩张为通过或失败。
- r2/r3/r4 各 34 main + 20 repair Formalizer 调用，三批 request 文件哈希完全相同；总登记发送 162，
  provider input 1,364,361、output 291,462。各 32 个 accepted packages，83 条 preferred 中 51 条未覆盖。
  accepted 样例仍有 LOAD/WRITE 操作表达，与论文数学表达目标有差距；不把 preferred 偷换成 required 或删除。
- 当前代码零网络回放冻结 r4：19→21 paragraphs、18 pages、最大 payload 估算 19,791，required/optional detail、
  formula obligation/package 四类 ID 集合守恒。该探针没有宣称真实 wire/tokenizer 准入；见 `offline-probe.json`。
- 当前 reader 验证 r4 的 54 条 receipts；原 Formalizer plan 恢复判定为 18 reuse、36 incomplete execute、
  12 未发送 slots，未把后两者算作成功复用。需要把合法成果复用接入下游实际操作路径。
- 精确命令：`python .tmp/c2p-e2e-flow-review-20260914-01/inventory_evidence.py` exit 0；
  `python .tmp/c2p-e2e-flow-review-20260914-01/offline_probe.py` exit 0；
  `python -m pytest -q tests/test_agentic_unified_context_compiler.py tests/test_agentic_publication_method_writer_unified.py tests/test_agentic_detail_atom_binder_and_trace_v2.py tests/test_agentic_formalization_guards.py`
  exit 0，107 passed。未重跑全量静态；探针前后 18 个关键代码/配置文件 SHA-256 一致。
- 执行收敛为生产 phase prepare → 全文 Candidate → 同身份最终质量/恢复/Verified；保持既有信任边界，
  不再把 token 持续增长、微测通过或 static test count 当作全文交付进度。
- 23:49:31 最后只读观察：r5 已有 54 completed / 54 started，仍无 execution record 和 Candidate，结果待定；
  已写 `r5-last-observation.json`。`git diff --check` exit 0，报告链接存在，18 个代码/配置文件无漂移。

## 2026-09-15 r5 终态追加与 prepare 合同因果复核

用户在同一复核任务中补充 r5 再次失败。本次继续零模型/零网络核查，没有修改生产代码、没有启动新 live。
r5 最终 exit 2，54 个 Formalizer receipts，Writer 发送 0，无 Candidate。r2–r5 共登记 216 次相同请求批次发送，
input 1,819,148、output 388,616，调用区间合计约 76.99 分钟；`r5-terminal-observation.json` 绑定终态。

纠正“最终 page 丢 detail 13”的初步归因：真实错误发生在试分页请求构造，`_ordered_candidate_rows` 将输入候选
row 换回原始完整 row。候选页只包含 detail 19/3，候选 required 为空；换回旧行后要求 detail 13，导致拒绝。
它还会丢弃新段落 `__f1/__f2`，冻结修订中共 4 个。不是应该往每个小页补 13。

`python .tmp/c2p-e2e-flow-review-20260914-01/r5_prepare_probe.py` exit 0：直接提取六个生产准备 helper 函数体，
调用真实分页器/Writer 请求构造。原 helper 在第 10 次候选构造复现 live 同码；仅内存替换为保留传入 rows，
37 次候选构造返回，修订 21 段、failures=[]。请求计量返回 0 占位，仅隔离 tokenizer 前的合同错误，不宣称完整计量通过。
证据 `r5-prepare-probe.json` 和 `r5-sources/`；报告、README、统一计划 §15.7 已更新，要求整个生产 prepare 纵向验收，
不再按单个报错 ID 修补后重发整批 Formalizer。此前 107 项静态通过结论保留，本反例说明其入口覆盖边界。

## 2026-09-15 生产入口收敛执行文档

按用户“充分研究代码和产物，给出收敛执行文档”的要求，交付
`docs/research_to_method_production_closure_execution_2026-09-15.md`，同步 README、统一计划 §15.7 与现状复核的执行索引。
本次新增的是实施要求，未修改生产代码、未启动新 live/Research/模型服务。

- 收敛目标：现有生产 authoring 入口完成 EBCAR 全文 Candidate；Verified 独立验收，不宣称默认切换/D5 完成。
- A：保留候选 row 与合法片段身份，提取现有完整生产 prepare，覆盖全量页/请求/目标守恒及真实计量。
- B：现有 replay 新增阶段模式（待实现），校验并消费原 phase 成果、保留父记录和花费；同时检查公式表达、
  最终计划身份与 prepare → 事务/组合 → structural exit/resume 的离线集成。
- C：准备与集成通过后直接执行 pending 全文 authoring；只回到失败所属阶段，禁止无变化整批重发。
- 文档明确动态 repair/下游请求须发送前实测；没有把 lookahead 占位计量当作已完成真实准入。
- 复核前后 18 个关键代码/配置文件 SHA-256 未漂移。相关 107 项测试为本次前段复核结果；文档阶段未重复跑 pytest。
- 文档验收：`git diff --check` exit 0；本次执行文档/现状复核共 25 个本地链接目标均存在，
  18 个关键源码/配置摘要再次一致。结果已写 `.tmp/c2p-e2e-flow-review-20260914-01/execution-document-checks.json`；
  未把待新增 CLI、prepare 结果索引或真实全文验收记录成已实现。

## 2026-09-15 用户质疑后的执行方案第二次核验

第一版根因/成本盘点成立，但未充分覆盖后续真实调用边界，也未把正常产品入口作为独立验收；本轮继续核对并直接
修订同一份收敛执行文档，不新增另一份计划。生产代码未修改，模型/网络调用均为 0。

- `python .tmp/c2p-e2e-flow-review-20260914-01/checkpoint_scope_audit.py` exit 0：r5 54 条 receipt 原身份一致，
  引用片段无缺失，32 个包与 aggregate 一致，当前来源/条件/公式绑定 validator 32/32 通过；其中 13 个来自
  partial 回执。普通 resume 会安排 23 个 main 重发，故方案改为有限的已结束 Formalizer 阶段读取，保留失败。
- `python .tmp/c2p-e2e-flow-review-20260914-01/downstream_contract_audit.py` exit 0：r5 payload 修订 18 页，
  原生产 handoff 注入块让 18/18 request/envelope 摘要改变；当前旧 5 节与 unified 2 节 ID 交集为空。
  该探针使用真实 serializer/digest，未作 tokenizer 准入或生成成功声明；Candidate 组合有额外 ID 回退，
  未把正式 accepted 投影错位描述为正文必定丢失。
- 同一探针截获默认 Editor/Rewrite 的 client 调用（真实网络之前停止），两者未经过 unified 账本，Editor
  role 为空；正常 `_run_writer_surface` 的 unified 调用未传 tokenizer。上述事实绑定 8 个相关源码摘要。
- 执行限于 F1 row/片段、F2 handoff request material、F3 实际正文计划身份、F4 阶段结果读取、F5 正常入口
  runtime/tokenizer、F6 辅助角色预算。论文表达按实际消费定向处理，不把通用缓存或 Formalizer 全面重写作前置。
- 修正 Realizer primary 的依赖说明：当前由冻结 page/计划/公式独立构造，应在 prepare 用真实 builder 计量。
  第一版把它归为依赖未来 Writer 正文的请求不准确。
- 交付目标补充正常 `code2paper method-agent run` 入口及恢复，不以 replay 成功等同生产就绪；CLI 新参数均
  标为待实现。README、统一计划 §15.7 和现状复核同步修订。前次 107 项静态测试结果保留，本轮未重复 pytest。

## 2026-09-15 r25 真实代码修复与冻结响应复验

范围：响应用户“读真实代码，没有修复的再修复”。保留现有 dirty tree；本轮没有提交、改写历史 receipt 或启动模型请求。

### 代码核验与修改

- 读当前生产 Realizer 发现已有原子 guard 选择和 incumbent witness 携带修复，不能再称为“尚未修复”。本轮进一步将 guard 缩窄限定为 AST 中完整条件的等价合取；额外条件、OR/NOT 改义、相似变量、注释、重复位置和多行歧义均保留原完整 excerpt。修复回合只复用仍精确存在于新正文中的旧 witness，不生成正文。
- `publication_method_writer._assert_unified_v2_realizer_delivery` 改为报告最大 attempt 的失败，而非 `rows[0]`，历史 receipt 保持原样。r25 终态原先暴露的是第一次失败，遮住了修复响应丢失 witness 的实际最后边界。
- `splice_formula_placeholders` 在已校验 package/consumer 的原占位符位置保留重复公式的 occurrence 身份，并生成现有正文中的唯一精确 witness 窗口。Writer 接入该元数据恢复并留 trace；不推断没有占位符来源的重复公式，不覆盖模型已经提供的 witness，不修改正文/公式字节。
- 共用 Writer request builder 在 prepare/send 前按封闭页面设置 paragraph ID enum；修复回合复用相同 schema。ID 拼写错误仍拒绝，不通过 harness 改写 ID。
- r25 detail 13 的原正文条件为“configuration flag ... is active”，并非可以证明遗漏事实。条件解析器此前不认可该形式。本轮只对完整子句末尾的显式 `is active` 使用已有 `is enabled` 语法；否定、条件结构、运算符和名为 active 的操作数仍保留。没有普遍去除连字符，也没有接受所有语义相似表述。
- 收紧已有算术豁免：仅语义自身等于声明条件的 guard（兼容无 role 旧合同）可忽略关联源码中的加法；带条件的 operation 仍必须证明正确求和，错误乘法/缺操作数拒绝。

### 实际产物结论

证据目录：`.tmp/c2p-r25-repair-20260915/`。

1. `realizer_probe.py` 用 r25 两份原始响应调用当前生产 Realizer：第二份 accepted，13 个 witness 验证完成；9 个模型漏返的旧映射仅在新正文中仍有精确文本时重用。primary 摘要相同；修复合同已变化，repair 摘要不同，不能据此修改 r25 原回执。
2. `writer_pipeline_probe.py` 从原 Narrative/manifest/plan 构造实际生产 Writer 输入，使用注入的冻结 caller 执行公开 Writer 管线和内容 assessor。修复前的四个请求摘要与 r25 对应摘要一致。修复后 page 7589a97d 的第一份响应直接通过；page b70a29ab 的第二份响应通过。正文没有人工改写，没有采用诊断 counterfactual 的 ID 修改结果。
3. r25 有 Writer 正文草稿，但原运行 exit 2、无 Candidate digest。此次只证明原来三个失败页在新代码下的定向冻结回放，不证明完整 A→B→C、后续组合/Editor/最终 Candidate 或 Verified 已完成。当前不能宣布生产收敛完成。
4. `writer-before.json` 的早期低层重建丢失私有图结构，已由公开生产管线回放取代；`writer-identity-counterfactual.json` 仅用于定位，不能当作合法模型输出。正式证据为 `result.json`、`writer-pipeline.json` 和 `final-code-and-input-digests.json`（HEAD、30 个代码/测试/输入摘要）。

### 验证

- `conda run -n code2paper python -m pytest -q tests/test_agentic_condition_state_witness.py tests/test_agentic_formalization_guards.py tests/test_llm_section_writer.py tests/test_agentic_mechanism_realizer_composer.py tests/test_agentic_publication_method_writer_unified.py tests/test_agentic_publication_method_writer.py tests/test_agentic_unified_context_compiler.py tests/test_agentic_replay_execution_record.py tests/test_agentic_branch_control_relations.py`：exit 0，433 passed，6 个现有 Pydantic serializer warnings。日志 `targeted-tests.log`。覆盖正/负条件、运算、占位符身份、修复元数据和失败终态。
- `conda run -n code2paper python .tmp/c2p-r25-repair-20260915/realizer_probe.py`、`conda run -n code2paper python .tmp/c2p-r25-repair-20260915/writer_pipeline_probe.py`：均 exit 0；无网络或新生成调用。
- `conda run -n code2paper python -m compileall -q src tests`、`git diff --check`：exit 0。
- 过程中的一次测试收集失败（缺少 pytest import）及两项旧合同回归（缺 paper_role）均已修复，最终上述集合通过。
- `conda run -n code2paper python -m pytest -q`：exit 0，3567 passed、3 skipped、7 warnings、12 subtests passed，123.82 秒；日志 `full-static-tests.log`。随后最终审查进一步要求 guard 缩窄仅适用于 branch/condition role（不能把带条件的 transformation 只绑定到 guard），补负例并重跑 Realizer 定向测试与冻结回放。未重复整套测试；不以静态通过替代正常产品入口最终验收。

- 最终 guard role 收紧后：`conda run -n code2paper python -m pytest -q tests/test_agentic_mechanism_realizer_composer.py` exit 0，24 passed in 1.06s；生产 Realizer 冻结回放 exit 0。最终 `git diff --check` exit 0。

## 2026-09-15 Research → Candidate 终态与账本闭合修复

范围：按用户要求修复本轮 EBCAR 正常入口/旧 run28 产物审计发现的问题。保留 dirty worktree 与历史产物；没有提交、重写旧 checkpoint/receipt，也没有把仍由旧进程加载的 live8 当成新代码验证。

### 实现

- `research_tools.py` 在 `compile_code_facts` 内把 configuration-definition facts 合入后再一次性持久化；`validate_code_facts` 使用相同重算链验证，删除 `research_nodes.py` 的仅内存二次扩充，消除 persisted/in-memory fact-set identity 分裂。
- `research_graph.py` 从 live agenda、compiled claims、决策/工具调用与缺失关系持续计算 `QualityStateV2`，在采集/编译边界刷新 Pareto best；读取新 span 不再算 compile coverage gain。`intent_ledger.py` 同步不再用新 span 重置语义无进展计数；strict promotion 检查消费全部未闭合 promotion，而不是按 agenda 终态过滤。
- `publication_method_writer.py` 的 Narrative→Method adapter 只按 source/fact/equation/config/relation 的唯一精确锚点绑定旧 argument unit，并保留明确的 unmatched/ambiguous trace；可验证 obligation/move 绑定才进入当前计划。Candidate completion 现在同时检查 adapter、plan gate、epistemic safety、content-unit render chain，以及 accepted/consumed formula 的实际正文出现。
- Candidate authority/公式门新增 `Sym:*`、`mech_sym:*`、`MA-*`、`LOAD/WRITE/RESHAPE/CALL/...` 和 LaTeX 控制字符检测。`publication_quality.py` 从实际 Candidate display-math 与公式包正文出现计算 rendered/consumed，不再用旧 equation id 代替正文渲染。
- Unified Rewrite 不再复制 million-token writer view、authoring packets、mechanism packet 或 frozen page bytes；只保留 section-local contract/identity，并在 180 kB authority projection 上 fail-before-send，为 60k-token角色预算留出 incumbent、issue、schema 与响应空间。
- structural exit 新增 Candidate completion、quality/content chain 与 adapter 未绑定检查。live `method-agent run` 仅在 Candidate available+complete 时 exit 0，process artifact 记录 Candidate 阻塞原因；显式 `--no-live-llm` 仍是成功的离线诊断入口。
- replay 将 provider transaction success 与 Candidate completion 分开；terminal complete/exit 0 同时要求 Candidate complete 和 structural exit eligible。成功记录不引用旧 failure artifact；累计 token usage 优先从 `artifacts/06_authoring/invocations/**/attempt-*.completed.json` 持久回执汇总，而非只看当前进程内 trace。

### 产物复算与验证

- 旧 `/tmp/c2p-production-closure-20260915-28` 只读重算：原 27 个全未绑定 argument units 中 24 个按唯一精确源码锚点绑定到两个当前 Narrative sections；3 个未绑定（两个未被 Narrative 计划覆盖，一个没有任何 source/claim/equation/config/relation anchor）继续明确阻断，未猜测归属。
- 聚焦集合：516 passed，6 个既有 Pydantic serializer warnings。
- `python -m pytest -q`：exit 0，3582 passed、3 skipped、7 warnings、12 subtests passed，136.23 秒。
- `python -m compileall -q src tests scripts` 与 `git diff --check`：exit 0。本轮尚未启动新的模型请求或正常入口 live，因此不声明 Candidate/Verified 已交付。

## 2026-09-15 live9 配置证据包血缘修复与 partial Candidate 语义确认

范围：回应用户“Research 不必找齐全部可信证据，应能进入下一阶段”的产品语义。
保留 strict Research/Verified 硬门；Candidate 继续使用已实现的 bounded partial handoff，未减少
obligation、未过滤失败 claim、未放宽 span validator。

### 实现

- `generic_evidence_compiler.py` 在 packet 冻结前做确定性配置定义预编译：仅当已选
  `CONFIGURED_BY` 关系的精确 endpoint operand 与配置访问表达式一致时，才把冻结标量声明 span
  纳入 `semantic_span_ids`，并附加到该 configuration relation 的 `direct_span_ids`。因此该 span
  从 anchor 可达，packet source digest 也真实覆盖它。
- `configuration_definitions.append_configuration_definition_facts` 新增可选 packet-span 白名单；事实工具
  仅为已由 owning packet 承载的声明生成正向 configuration fact。`compile_code_facts` 与
  `validate_code_facts` 共用同一限定与重算路径。
- 该边界修复 live9 的具体错误
  `unknown_packet_span:span:conf/config.yaml:19:19`；没有将搜索未决冒充为“代码不存在”。
- 确认现有 Candidate 通道已符合所需语义：Stage 1/3 可以以 promoted claims + typed unresolved
  fields + qualifier + 一次 post-partial retry 交接；strict failure 仍保留，Verified 不因此放行。

### 验证

- 合成 packet/config 集成及 Research 工具：103 passed。
- Candidate handoff/正常产品入口/Unified Writer 阶段边界：122 passed。
- V3 证据链、mechanism closure 与配置条件：84 passed。
- 用 live9 的真实 EBCAR repo snapshot、behavior graph 及原 Mainline proposal 在新目录
  `/tmp/c2p-live9-config-replay-fix1` 零模型重放：proposal→packet→facts→fact validation 四步均
  `success`；`span:conf/config.yaml:19:19` 已在 packet，同一 configuration fact id 通过，packet/fact
  digest 同为 `sha256:8fd417bae83c6d7f8ad51c31d47ee79bc104fe63f2a9e5d137c879396d4f8238`。
- `python -m pytest -q`：exit 0，3584 passed、3 skipped、7 warnings、12 subtests passed，129.60 秒。
- `python -m compileall -q src tests` 与 `git diff --check`：exit 0。
- 尚未在这一 changed basis 上执行新的正常入口 live；因此目前只声明修复与静态/真实冻结重放通过，不声明新 Candidate/Verified 已交付。

## 2026-09-17 P7 V4 身份阻塞与公式误入修复

范围：只读分析 `/tmp/c2p-p7-ebcar-v4-w2p9KvoI`（原运行绑定 `287506e`），在当前 `2c290aa` 的 dirty worktree 上增量修复；未重写原产物、未提交、未发起模型请求。原运行先遇到 `NarrativePlanV3` 名称错误，该 import 在本轮开始前的工作树中已有修复；本轮针对随后复现的 `unknown_detail_id` 与公式误入补丁。

- V4 编译器不再给 section 内每个 story 复制全部机制 detail。多机制 story 分成同一作者 section 内单一 mechanism owner 的段落；每个 detail 只分配一次，ownerless 作者段落不承载 repository detail。argument unit 也只分配给一个段落。源 ID 交集用于优先定位，零交集回退有显式 trace，不能用回退证明语义对齐。V3 投影保留空机制的作者段落，不再按单机制 section 偷填 owner；witness、author surface 和公式 placement 同步投影。
- V4 所选产品路径编译失败时不再静默退回 V3。公式 package 的 source details 同置于一个机制段落，package/obligation/placement 身份守恒。
- P7 的 Formalizer 实际 2 main + 2 repair 均因把 `document_id.long()`/`self.cfg...` 等代码运算写进公式而被正确拒绝；后续 attempt 触发预发送预算拒绝。公式 worthiness 现在将无 equation/facet 来源、非 formalizable 的代码形 transformation 判为 prose/algorithm，不再为它发机制公式义务。P7 冻结 contexts 的两条此类义务离线复算均消失。此修复不将 7 个未桥接的作者 required 公式改为已完成。
- P7 冻结 story/prior plan/context 经当前产品 `_build_narrative_plan_v3` → V4 envelope → V3 projection → `validate_narrative_plan` 零模型重放：5 sections、32 paragraphs、28 唯一 argument units、0 validation failures；11 个 required detail 唯一归属，required fallback 为 0；122 个 optional detail 缺少 story 锚点，仍须后续审查，不能当成实现事实授权。
- 定向回归 `python -m pytest -q tests/test_agentic_intent_spine_authoring.py tests/test_agentic_mechanism_formula_obligations.py tests/test_agentic_candidate_handoff.py tests/test_agentic_publication_method_writer.py tests/test_agentic_unified_context_compiler.py`：221 passed。最终代码上的全量 `python -m pytest -q`：3601 passed、3 skipped、7 warnings、12 subtests passed，exit 0。`python -m compileall -q src tests scripts` 与 `git diff --check`：exit 0。
- 尚无新 Writer completed、Candidate 或 Verified；原目录属于旧 SHA，且本轮改变了 V4/公式政策，不应把旧 Formalizer receipt 当作新代码的成功。7 个作者 required 公式仍 open、Research partial，P7 §7.2 未验收；必须重新生成新 run 的身份与成果，再检查产品 Writer/Binder/最终门。

## 2026-09-18 按 20260917 修复方案执行 WP0/WP1

范围：按 `docs/code2paper_repair_execution_20260917.md` 的强制顺序开工，只做 S0/S1；
未续跑 `/tmp/c2p-p7-ebcar-v4-intent-j9L1bn`，未发起任何 live 模型调用。

### S0 事故回归固定（WP0，提交 0395e25）

- 新增 `tests/regression_20260917/`：`incident_archive.py` 冻结 15 个归档 fixture 的
  Git blob SHA 与 sha256（双重身份），`conftest.py` 拒绝真实网络并校验归档零改动，
  `test_archived_failure_facts.py` 固定六条事故事实：attempt 3/4 为预发送拒绝
  （sent_to_caller=false、provider_usage=null、3>2/4>2）、只有 attempt 1/2 到达
  provider 且 attempt 2 是唯一 content repair；MA-S3 receipt 15/16 且聚合未完成；
  第 2 次缺的是两个 detail witness（完整响应 17 条 atom、0 条 detail、
  rendered_detail_ids 为空）；Writer 请求中 P3–P17 共 15 个空槽（无机制/detail/
  formula、targets 为空、共用同一 section 级 reader_goal、对象无逐段作者语义字段）；
  `RunIdentity.code_commit_sha` 等于目标 RepoSnapshot 的 EBCAR commit 287506e3，
  身份模型没有引擎 HEAD 字段；Formalizer 空 manifest 与 Writer manifest 同时合法。

### S1 引擎身份与目录准入（WP1，提交 d09a5d7）

- 新增 `agentic/authoring_execution_identity.py`：内容寻址引擎指纹（逐文件 sha256，
  排除产物/缓存/密钥/数据库）、`AuthoringExecutionIdentityV2`（引擎/目标/输入摘要
  分离，engine_root 不参与 digest）、目录准入状态机（含
  resume_exhausted_invocation 与 resume_engine_identity_unavailable）、跨进程 flock
  单写者租约（进程内幂等）、`verify_research_import`、create-or-validate 身份写入
  （不一致即拒，不改写历史身份）、只读的 `scan_exhausted_invocations`。
- 接线：`run_autonomous_method_agent(..., run_open_mode=...)` 在任何产物写入前完成
  准入/租约/身份，runtime 建立后复查目标 commit；CLI 增加
  `--run-open-mode {auto,new,resume,fork_authoring}` 并先做只读预检（拒绝时返回 2、
  零写入），正式准入在锁内复查。
- 行为变更（有意 fail-closed）：非空目录且无 `AuthoringExecutionIdentityV2` 时
  `auto`/`new` 一律拒绝；旧 RunIdentityV1 目录只能显式 `fork_authoring`；已耗尽内容
  预算的 invocation 在 resume 时直接阻断。这正是事故"重启即必死"的入口。

### 验证

- `python -m pytest -q tests/regression_20260917 -m 'not live_llm'`：34 passed。
- `python -m pytest -q -m 'not live_llm'`：3635 passed、3 deselected、
  12 subtests passed、7 warnings，exit 0（基线 3601 + 新增 34，无回归）。
- `python -m compileall -q src tests scripts`：exit 0；归档在回归期间逐字节未变。

### 未完成 / 下一步

- WP2（作者意图到达 Writer：局部 `author_intent_surfaces`、槽位分类与合并、
  零交集不升级证据、intent digest 覆盖 statement）尚未开始。
- WP3–WP7 未开始；live 验证（L1/L2/L3）未执行，需方案 §14.1 的显式授权与全新
  out 目录。

## 2026-09-18 WP2：作者意图真正到达 Writer（S2）

范围：方案 §6。编译器把"一个 story 槽位 = 一个必须写出的段落"改成"作者单元分类 +
受限合并 + 可审计去向"，并把页内作者语义与权限送到实际模型表面。

### 实现

- `intent_spine_models.py`：新增 `AuthorIntentSurfaceV1`（author_statement / intended_role /
  local_reader_goal / authority_surface / implementation_status / supporting_detail_ids /
  unresolved_points / source_content_digest），`ParagraphKindV1`
  （grounded_content / author_specification / expository_bridge / structural_only /
  unresolved）；`IntentNarrativeParagraphV4` 增加 paragraph_kind、author_intent_surfaces、
  surface_digest、implementation_status、unresolved_ids、source_story_ids、source_slot_ids、
  disposition；`IntentNarrativePlanV4` 增加 `source_intent_digest_version`。
- `intent_narrative_compiler.py`：新增 `SlotBindingDecision`（overlap/status/needs_research，
  零交集只能是 organizational_fallback）、`compile_author_intent_surfaces`、
  `compile_authoring_units`（分类 + 合并：同 section/同 kind/同 role/同 authority 且不承载
  argument unit 或 intent atom 才合并；mechanism 不相容不合并）、
  `compile_intent_content_digest`（覆盖 statement/role/priority/notes/关联证据/顺序/atom，
  版本 `intent-content-v2`）。段落改为由单元生成：structural_only 不生成正文，
  unresolved 以受限作者描述出现（authority 绝不升级为 repository_statement，且不带必需
  detail），每个单元都带 disposition。trace 增加 unit_kind_counts、unresolved_story_ids、
  structural_only_story_ids、non_writable_unit_ids。
- `section_writer.py`：`_WRITER_PARAGRAPH_NARRATIVE_FIELDS` 增加 WP2 字段，
  新增 `_compact_writer_author_intent_surfaces_for_llm` 保留作者内容与权限（不再只传 ID）。
- V4→V3 投影携带上述字段（V3 段落模型 extra=allow，digest 因此随语义变化）。

### 验证

- `python -m pytest -q tests/regression_20260917 -m 'not live_llm'`：40 passed
  （新增 `test_intent_writer_surface.py`：空槽不变成 grounded 段落、15 个同形空槽合并为
  ≤2 个受限单元、每个 story 都有去向、请求表面确实带 author_statement/local_reader_goal/
  authority/implementation_status、改 statement 不改 ID 时 source_intent_digest 与
  surface_digest 必变、零交集只是组织 fallback、must-cover 无归属仍为 unresolved 而非
  仓库事实）。
- `python -m pytest -q -m 'not live_llm'`：3641 passed、3 deselected、
  12 subtests passed，exit 0（S1 后 3635 + 新增 6，无回归）。

## 2026-09-18 WP3（部分）：witness 两阶段验收与结构化失败（S3）

范围：方案 §7.2/§7.4/§7.5。

### 实现

- `publication_transaction_contract.py`：新增 `ContractFailureV1`
  （code/stage/paragraph_id/target_kind/target_id/expected/observed/repairable_by），
  `ParagraphTransactionAssessmentV1` 增加 `validation_stage` 与结构化 `failures`；
  `assess_paragraph_transaction(..., validation_stage=...)`：
  - `writer_content`：必需目标不含 Binder 负责的 atom；detail 义务由明确的 detail
    witness 或**完整** atom 集合履行，完整 atom 集合之外的 atom 声明不再自动补齐
    detail（事故里"17 条 atom、0 条 detail"不能再被掩盖）。
  - `final_bound`：保持既有严格语义（detail 需要 detail witness + 全部必需 atom，
    或完整 atom 集合），负例不退化。
  - 未知 stage 直接 fail-closed（`unknown validation_stage`）。
- 结构化失败码：paragraph_missing、detail_witness_missing、atom_witness_missing、
  formula_consumer_mismatch、exact_span_not_in_body、target_out_of_scope、
  detail_semantic_mismatch、input_material_missing；target id 含冒号时按两刀切分，
  并按 (code, kind, target) 去重；执行层不再需要解析拼接字符串。

### 明确未上线（不可单独上线）

方案 §7.1（Writer 表面剥离 Binder 所有的 atom）**本轮回退**：页级门仍是
`final_bound`，它要求模型枚举全部 atom witness；一旦 Writer 看不到 atom 目标，
detail 将永远无法满足——即半条 §7.1 会导致 fail-closed 死锁，而不是更安全。
§7.1 必须与 §7.2 的页级配对（页接受改用 writer_content + 由确定性 Binder 保障
final_bound atom 绑定）一起落地，并先核实 binder 阶段确实产出 atom 绑定。

### 验证

- `python -m pytest -q tests/regression_20260917 tests/test_agentic_detail_atom_binder_and_trace_v2.py
  tests/test_agentic_publication_method_writer.py -m 'not live_llm'`：202 passed。
- `python -m pytest -q -m 'not live_llm'`：3646 passed、3 deselected、
  12 subtests passed，exit 0（S2 后 3641 + 新增 5，无回归）。

## 2026-09-18 WP3 完成：页级配对与 Writer 表面剥离 atom

先核实再上线：`publication_method_writer.py` 的 Binder 阶段（`_write_unified_v2_binder_receipts`
→ `binder_receipts_v2`）确实消费最终接受的 Writer 段落与 `section_inputs`（含完整 canonical
witness 合同），且**缺少或失败的 Binder 回执会 fail-closed 阻断发布**。因此可以把页接受
降到 `writer_content`，atom/条件/极性/接口由 Binder 负责。

- 页级两处 `assess_paragraph_transaction(...)`（missing_paragraph/invalid_count/
  required_target_count 的来源）改为 `validation_stage="writer_content"`。
- §7.1 上线：`_compact_writer_witness_contract_for_llm` 从 Writer 视图剥离
  `target_kind="atom"` 的目标，并记录 `binder_owned={owner, target_count}`；canonical
  合同不变，Binder 仍取完整 atom。
- 既有测试 `test_unified_page_projection_keeps_page_and_compacts_duplicate_contracts`
  原先断言 Writer 视图包含必需 atom——这正是方案 §7.1 要修的行为，已改为断言
  Writer 视图 targets 为空 + `binder_owned`，同时断言 canonical 合同仍保留 atom。
- 新增/恢复 `test_witness_projection.py` 两例：合成合同剥离 2 个 atom；事故真实请求
  P1__f1 的必需 atom 在 Writer 视图消失、detail 目标保留。

验证：`python -m pytest -q -m 'not live_llm'` → 3648 passed、3 deselected、
12 subtests passed，exit 0（无回归）。

## 2026-09-18 WP4（估量层）：输出工作量估量与页契约联合评估

范围：方案 §8.2/§8.4 的纯函数部分。**未接线**分页器（见下）。

- 新增 `src/code2paper/agentic/writer_output_workload.py`：
  `WriterOutputWorkloadV1`（语义段落数、required detail occurrences、Writer-owned /
  Binder-owned witness 数、公式消费数、JSON 开销、目标正文量、安全余量、预计输出
  tokens、basis_version、confidence、unknown_reasons）与
  `estimate_writer_output_workload(...)`；
  `PageContractEvaluationV1` 与 `evaluate_page_contract(...)`：同时检查
  `input_tokens <= max_page_input_tokens`、预计输出 <= 可用输出预算、以及
  `max_semantic_paragraphs_per_page` 候选上限；**输出预算未知时默认 fail-closed**
  （`output_budget_unknown`，可显式放宽）。
  `narrative_ordinal()` 按叙事序号排序（P2 在 P10 之前）。
  经验系数可经 `calibrated_profile` 注入；未标定时 confidence=uncalibrated，
  `DEFAULT_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE=6` 仅作待标定候选。

未接线（必须与重新标定一起做）：`fit_narrative_plan_to_page_budget._over_budget` 与
`extend_writer_worksets_from_narrative_plan` 的候选页接受点尚未调用
`evaluate_page_contract`。原因：WP2 改变了段落数（15 空槽合并），旧的分页/Obligation
分布尚未重新测量；在没有端到端页数回归的前提下改预算门，可能把 fail-closed 变成
误杀或漏放。下一步：先测量新的页分布，再把联合预算接到候选页接受点并重建
invocation plan/admission（§8.5）。

验证：`python -m pytest -q -m 'not live_llm'` → 3657 passed、3 deselected、
12 subtests passed，exit 0（S3 后 3648 + 新增 9）。事故页形状（16 段 + 真实 detail
义务 + atom witness）在 8192 输出预算下被判为不可行；无 atom 的过渡页输出成本非零；
Binder-owned atom 不计入 Writer 负担。

## 2026-09-18 WP4 接线：候选页接受点加入语义段落预算

- `unified_context_compiler.py` 新增 `_max_semantic_paragraphs_per_page()`
  （默认取 WP4 候选值 6，可用 `CODE2PAPER_UNIFIED_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE`
  覆盖，0 = 显式关闭该维度，非法值回落候选值）。
- `extend_writer_worksets_from_narrative_plan` 的候选页接受点（含 flush 后的单组复查）
  在输入预算之外增加"候选页语义段落数 > 上限"判据：超限时**先拆页**（flush 当前页，
  新页从该组开始），单组仍超限则保持既有的 typed block
  `UNIFIED_ATOMIC_PAGE_OVER_BUDGET`。atom→页归属与义务守恒由原分页逻辑保证，本改动只
  让页更小，不做段落 fragment 预拆（§8.1/§8.3）。
- 事故页形状（16 段）在默认上限下会被拆成多页，而不是作为一次 16 段事务发出。

仍未完成（下一步）：WP2 之后的端到端页分布尚未重新测量与登记；§8.5 的
invocation plan / lookahead reservation / admission 重建（不足时报
`run_budget_insufficient_after_repage`）未接。

验证：`python -m pytest -q tests/test_agentic_unified_context_compiler.py` 30 passed；
`python -m pytest -q -m 'not live_llm'` → 3658 passed、3 deselected、12 subtests passed，
exit 0。

## 2026-09-18 WP4 §8.5：拆页后预算不足的可解释失败码

- `unified_context_models.py` 新增
  `UNIFIED_RUN_BUDGET_INSUFFICIENT_AFTER_REPAGE = "run_budget_insufficient_after_repage"`。
- `unified_context_compiler.py` 新增 `_repage_budget_failure_code(plan_revision, exceeded)`：
  `plan_revision > 1`（分页/修订后的 plan）且越过 whole-run 预算时给出该码；普通
  `plan_revision == 1` 仍报既有 `unified_invocation_budget_exceeded`（既有码保留，
  便于兼容既有断言与日志）。
- 接入点：invocation gate 的 role 调用数检查与 total input tokens 检查（这两处正是
  拆页会增加的量）。语义是"拆页也必须过 whole-run 预算；不足要显式报告，不能以
  '只是拆页'为由截掉剩余页"（§8.5）。

验证：`python -m pytest -q tests/test_agentic_unified_context_compiler.py` 30 passed；
`python -m pytest -q -m 'not live_llm'` → 3659 passed、3 deselected、12 subtests passed，
exit 0。

## 2026-09-18 WP5 账本核心：事件序号与真实发送计数分离

新增 `src/code2paper/agentic/writer_attempt_ledger.py`（只读派生，不改写历史记录，I8）：

- `WriterAttemptCountersV1`：`event_seq`（历史 attempt，不可变）、`provider_send_count`、
  `content_attempt_count`、`content_repair_count`、`rejected_before_send_events`。
- `read_invocation_ledger_state(out_root, invocation_id)`：从 `attempt-*.completed.json`
  与 `attempt-*.content-acceptance.json` 派生状态；**accepted 只取内容验收**——传输层
  `delivery_status=accepted` 不算（事故里两次 provider 调用的 delivery 都是 accepted，
  内容验收都是 rejected）；拒发事件（`attempt_limit_exhausted:`）计入诊断但不计入发送/
  内容次数，并从中读出 `content_attempt_limit`。
- `build_resume_preflight(...)` → `ResumePreflightV1`：进入 Writer 主循环前给出
  `resume_exhausted_invocation` 结构化阻断（execution_id、invocation_id、
  content_attempts_used/limit、last_provider_attempt、last_content_failure_codes、
  rejected_before_send_events、allowed_next_action），零新增调用；缺目录/缺回执**不算**
  已耗尽（不把缺失当结论）。
- 历史 acceptance 失败项映射为结构化码（detail_witness_missing / paragraph_missing /
  authority_surface_violation / input_material_missing / detail_semantic_mismatch），
  调用方不需要解析 `detail:detail:` 这类拼接串。

事故归档实测：`event_seq=4`、`provider_send_count=2`、`content_attempt_count=2`、
`content_repair_count=1`、`rejected_before_send_events=(3,4)`、`exhausted=True`、
`last_content_failure_codes` 含 `detail_witness_missing`；已接受页（MA-S1）不被误判为耗尽。

仍未完成（WP5 剩余）：把计数器接到 Writer 调用边界（预发送拒绝不得推进内容尝试次数）、
限流/超时的独立 transport policy 与 `send_outcome_unknown` 保留 reservation、§9.5 的
崩溃点恢复用例。

验证：`python -m pytest -q tests/regression_20260917` 63 passed；
`python -m pytest -q -m 'not live_llm'` → 3664 passed、3 deselected、12 subtests passed，
exit 0。

## 2026-09-18 阶段收敛：现状、证据与剩余项交接

本轮不新增功能改动，只固化当前状态与下一步，避免后续会话重复摸索。

### 已完成并各自带离线证据（34ae0cf 之后 9 个提交）

| 提交 | 阶段 | 内容 | 证据 |
|---|---|---|---|
| `4a5de49` | S0 前置 | 引入执行方案文档 | — |
| `0395e25` | WP0/S0 | 事故归档冻结 oracle（blob+sha256 双身份）+ 6 条事故事实 | `tests/regression_20260917/test_archived_failure_facts.py` |
| `7038808` | WP1/S1 | 引擎内容指纹、`AuthoringExecutionIdentityV2`、new/resume/fork 准入、耗尽阻断、单写者租约、CLI `--run-open-mode` | `test_execution_identity.py` |
| `5eba40a` | WP2/S2 | 作者单元分类/合并、页内 `author_intent_surfaces`、`intent-content-v2` 指纹 | `test_intent_writer_surface.py` |
| `87ad104` | WP3/S3 | 两阶段验收（writer_content/final_bound）、结构化 `ContractFailureV1` | `test_witness_projection.py` |
| `1b10d12` | WP3/S3 | 页级配对（页接受=writer_content，atom 交确定性 Binder）+ Writer 视图剥离 atom | 同上 + `test_llm_section_writer.py` 更新 |
| `11169b1` | WP4 | 输出工作量估量与页契约联合评估（纯函数） | `test_output_feasibility.py` |
| `9d6dca1` | WP4 | 候选页接受点加入语义段落预算（先拆页） | 同上 + `test_agentic_unified_context_compiler.py` |
| `ea710d3` | WP4/§8.5 | `run_budget_insufficient_after_repage` 可解释失败码 | 同上 |
| `a7c4fc1` | WP5 读侧 | 事件序号 vs 真实发送计数、恢复前置检查 | `test_ledger_recovery.py` |

最后一次全量离线：**3664 passed、3 deselected、12 subtests passed、exit 0**。
工作区只剩两项有意不提交的内容：`docs/1.txt`（草稿）与 `paperbanana_single_shot`（submodule 内容变更）。

### 剩余项（按建议顺序，均为可独立开工的边界）

1. **WP4 收尾**：用冻结证据重新测量 WP2 之后的真实页分布，登记语义段落上限标定值；
   确认 invocation plan 构建路径不存在"剩余页被截断"的分支（只允许显式失败）。
2. **WP5 写侧**：`publication_method_writer.py` 调用边界
   （`attempt = last_started_attempt(...) + 1` 与 `publish_attempt_started(...)`）目前仍以
   **事件序号**决定是否拒发；应改为以 `read_invocation_ledger_state(...)` 的
   `content_attempt_count` 决定内容预算，使"预发送拒绝"不再消耗内容尝试（§9.2）；
   随后补 transport policy（限流/超时）与 `send_outcome_unknown` 的 reservation 保留，
   以及 §9.5 的崩溃点恢复用例（reservation 后未 send / send 后无 response /
   response 后未 completed / completed 后未 acceptance）。
3. **WP3 剩余**：§7.3 repair packet（失败页定向修复语义）、§7.4 binder 端"atom 仅用于
   定位候选 span"、§7.6 单一正文表面（段落对象为唯一真源、section_markdown 派生）。
4. **WP6**：新增 `authoring_artifact_index.py`（`(logical_role, phase, generation)` 解析、
   active 指针、digest 解引用）与 `build/validate_authoring_run_contract` 的 N/A 一致性。
5. **WP7**：`build_selected_narrative_plan(selection, ...)`（v4 路径 legacy 调用归零、
   无静默 fallback）、Writer 必需页缺口在 phase boundary 前置暴露。
6. **live 验证（L1/L2/L3）**：需方案 §14.1 的显式授权与全新 out 目录；本轮未运行任何
   真实模型调用，也未续跑 `/tmp/c2p-p7-ebcar-v4-intent-j9L1bn`。

## 2026-09-18 WP5 写侧：内容预算按真实发送计数（不再被拒发事件吃掉）

- `writer_attempt_ledger.py` 新增纯函数 `content_budget_exhausted(state, max_attempts)`：
  已接受 → False；否则只有 `content_attempt_count >= max_attempts` 才算耗尽。
- `publication_method_writer.py` 调用边界：`attempt = last_started_attempt(...) + 1` 仍作为
  **事件序号**用于收据身份，但"是否拒发"改为
  `attempt > max_attempts and (content_budget_exhausted(...) or 没有拒发事件)`：
  连续两次预发送拒绝不再把内容预算耗尽（此前 `attempt 3 > 2` 直接拒发，等于用一个
  从未发送过请求的页永久锁死）。拒发仍保留诊断收据（§9.2 允许），但不消耗内容尝试。
- 新增回归：`test_presend_refusals_do_not_consume_content_budget`（两次拒发、零发送 →
  不算耗尽；事故页 2/2 → 耗尽）、`test_accepted_invocation_is_never_exhausted`。

验证：`python -m pytest -q tests/regression_20260917` 65 passed；
`tests/test_agentic_publication_method_writer.py + regression` 211 passed；
`python -m pytest -q -m 'not live_llm'` → 3666 passed、3 deselected、12 subtests passed，exit 0。

## 2026-09-18 WP5 崩溃点分类（§9.5）

`writer_attempt_ledger.py` 新增 `read_attempt_outcomes` / `unsettled_reservations` +
`AttemptOutcomeV1`，按 attempt 汇总崩溃点状态：

| 状态 | 预留 | 语义 |
|---|---|---|
| `reservation_without_send` | 释放 | 已预留未发送：不得计费 |
| `send_outcome_unknown` | **保留** | 已发请求无响应：结果未知，不自动退款/重发 |
| `response_without_completion` | **保留** | 有响应缺 completed：可由 validator 重建 |
| `completed_without_acceptance` | 释放 | 缺内容验收：确定性 validator 重放即可，无需再调模型 |
| `rejected_before_send` | 释放 | 预算/合同拒绝：不消耗内容预算 |
| `settled` / `not_started` | 释放 | — |

事故归档实测：attempt 1/2 = `settled`，3/4 = `rejected_before_send`（与内容预算判定一致）。

验证：regression 67 passed；全量离线 3668 passed、3 deselected、12 subtests passed、exit 0。

## 2026-09-18 WP6：阶段化产物索引与合同 N/A 一致性

- 新增 `src/code2paper/agentic/authoring_artifact_index.py`（新增解析层，不重命名历史文件）：
  `ArtifactIndexEntryV1(logical_role, phase, schema_version, generation, path, status,
  semantic_digest, file_bytes_digest)` 与 `AuthoringArtifactIndexV1`（active 指针 +
  content_digest）；`build_artifact_index(out_root, reference_digests=...)` 只读扫描已知
  产物；`resolve_artifact(index, role, phase, out_root=..., expected_digest=...,
  allow_empty=...)` 对未知 role/phase、active 歧义、缺失、语义摘要不符、路径逃逸一律
  阻断（不按 mtime/字典序/无后缀猜当前对象）。
  状态包含 `valid_empty`（合法空产物）与 `source_snapshot`（兼容源快照，不是独立语义
  对象），二者不会被当成 active 真身。
- 事故归档验证：`consumer_workset_manifest:formalizer` = 空基础 manifest（valid_empty）、
  `:writer` = `.writer.2` 真身（active），两者各自可解析；`narrative_plan:authoring`
  默认取 `revision.2`，当按适配器记录的参考摘要解引用时取回 `narrative_plan_v3`，
  另一代标为 `superseded`；`allow_empty=False` 时空 manifest 报
  `artifact_empty_not_allowed`。
- `authoring_context_contract.validate_authoring_run_contract` 与 builder 共用同一
  required-key 判定：正当 N/A 不再被误报缺失；`allow_blocked` 明确为"允许不完整状态
  被记录/展示"的展示开关，不改变 satisfied，也不能作为发布 verified 的后门。

验证：regression 71 passed；全量离线 3672 passed、3 deselected、12 subtests passed、exit 0。

## 2026-09-18 WP7 §11.1：单一计划选择（v4 不再白跑 legacy builder）

- `publication_method_writer._build_narrative_plan_v3` 重构：**选择在构建之前决定**。
  * `v4`：只构建 V4，并由 `project_intent_plan_to_narrative_v3` 给出**一次**兼容投影；
    legacy builder 完全不执行（trace 记 `legacy_builder_executed=False`）。
  * `v3`：只跑 legacy builder（既有默认路径不变）。
  * `shadow`：两者都建，但只有 `v3` 可执行，且在 envelope 中显式标注
    `executable_plan_version`；影子调用仍走各自的 trace/meter。
  * 显式选定 `v4`/`shadow` 时 V4 编译失败**必须失败**（不变量 I2，不静默 fallback）；
    `v4` 选定但未编译出计划时报 `intent_plan_v4_selected_but_not_compiled`。
- envelope 新增 `executable_plan_version`，trace 新增 `plan_selection` 与
  `legacy_builder_executed`，使"这次跑的是哪套计划、有没有影子调用"可被直接断言。

验证：regression 75 passed（新增 `test_plan_selection.py` 4 例：v4 不调用 legacy、
v3 调用、v4 编译失败仍失败、shadow 双建单执行）；全量离线 3676 passed、3 deselected、
12 subtests passed、exit 0。

## 2026-09-18 WP7 §11.2：Writer 阶段边界的依赖前置检查

- `publication_method_writer.py` 在加载 Writer 持久恢复状态之后、进入调用循环之前，
  对**账本已出现预发送拒绝**的必需 invocation 做前置检查（事故签名：
  `attempt_limit_exhausted` 记录）。命中即返回结构化阻断：
  `writer_phase_boundary_blocked:blocked_by_stage=writer:primary_cause=...:invocation=...:
  content_attempts=used/limit:rejected_before_send=[...]:downstream_not_run=realizer,binder,
  section_composition,publication_audit`，不再跑完整个 Writer 循环后靠
  `writer_v2_invocation_acceptance_count:0` 事后暴露根因。
- 判据刻意收窄为"有预发送拒绝记录"而非"内容尝试用满"：声明了 retry reserve 的 repair
  流程（`test_writer_content_repair_uses_declared_retry_reserve_and_commits_only_after_acceptance`）
  没有这种记录，不会被误判为耗尽——该误判在首次全量回归中被既有测试抓到并已修正。

验证：regression 76 passed；受影响套件 98 passed；全量离线 3677 passed、3 deselected、
12 subtests passed、exit 0。

## 2026-09-18 WP4 标定：页内语义段落边界的实测结果

数据源：事故归档 `artifacts/runs/2026-09-17-ebcar-intent-v4-p7-j9L1bn` 的 24 个 Writer 请求
（请求侧 `narrative_plan.paragraphs` 数 × 对应 content-acceptance 结果）。

**重要修正**：此前把 `technical_payload.paragraph_ids`（页的原子段落，事故页=1）当成
"一次要写多少段"是错的；真正的输出工作量在**请求侧**段落列表（事故页=16），WP4 的估量
与上限必须喂请求侧契约。

实测三点边界（已写成常量并由回归钉住）：

| 边界 | 值 | 证据 |
|---|---|---|
| 首次调用即接受的最大段落数 | **2** | 2 段页全部首次 accepted；1 段页有一例需 repair |
| repair 可恢复的最大段落数 | **6** | 4 段与 6 段页都是"首次 rejected → repair accepted" |
| 实测不可一次完成 | **16** | 事故页首次与 repair 均 rejected（内容预算耗尽） |

因此 `DEFAULT_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE = 6` 是"依赖 repair 的边界"，不是"首次
即可接受"的安全值；若要追求首次即接受应显式下调到 2（代价是更多页与更多调用）。两条
边界与事故形状都可被回归重算，任何改动都会在 `test_page_calibration.py` 失败。

验证：regression 79 passed；全量离线 3680 passed、3 deselected、12 subtests passed、exit 0。

## 2026-09-18 WP6 写侧：索引发布与阶段输入快照

- `authoring_artifact_index.py` 新增：
  * `publish_artifact_index(out_root, ...)`：先构建索引对象、原子写入
    `artifacts/06_authoring/authoring_artifact_index_v1.json`，**读回校验 content_digest**
    后才算发布成功（半写对象不得成为 active）；`index_revision` 在已有索引基础上递增。
  * `ResolvedAuthoringSnapshotV1` + `build_resolved_authoring_snapshot(index, out_root,
    phase, required_roles)` + `write_resolved_authoring_snapshot(...)`：把某阶段需要的
    产物解析结果（相对路径 + 字节摘要 + 索引摘要）冻结成
    `resolved_authoring_snapshot_v1.<phase>.json`；reader 执行期间不再反复读 active 指针
    （§10.3）。缺必需产物即 fail-closed。
- 产物命名：索引固定路径 `artifacts/06_authoring/authoring_artifact_index_v1.json`；
  阶段快照按 phase 后缀区分。

验证：regression 81 passed；全量离线 3682 passed、3 deselected、12 subtests passed、exit 0。

## 2026-09-18 WP5 transport policy（§9.2）

新增 `src/code2paper/agentic/transport_retry_policy.py`（纯决策函数，无 I/O）：

- `TransportRetryPolicyV1`：`max_transport_retries`（默认 2，可经
  `CODE2PAPER_TRANSPORT_MAX_RETRIES` 覆盖）、指数退避（base/max，默认 1s/30s）、可重试
  状态码（429/500/502/503/504）、`counts_against_call_budget=True`、
  `unknown_outcome_retries=0`。
- `classify_transport_failure(status_code=/exception=/sent=)`：429/5xx → `retryable_status`；
  其他 4xx → `terminal_status`；已发送的 timeout → `transport_timeout`；未发送的连接失败 →
  `connection_error`；无法判定 → `unknown`（按结果未知 fail-closed 处理）。
- `next_transport_action(...)`：结果未知（timeout/unknown）→ **`preserve_reservation`**
  （保留 reservation，不自动重发/退款）；可重试失败受 `max_transport_retries` 与
  **run 调用上限**双重约束（`transport_retry_exceeds_call_budget`）；终态失败 → `fail`。
- 坏配置回落默认（不会变成无限重试或负数）。

仍未完成：把该策略接到实际调用重试点（`_default_llm_caller` / writer provider 调用路径
的异常分支），以及 `unsettled_reservations` 与写侧预算核算合并（避免双重扣费）。

验证：regression 87 passed（新增 `test_transport_policy.py` 6 例）；全量离线 3688 passed、
3 deselected、12 subtests passed、exit 0。

## 2026-09-18 WP3 §7.3：Writer 定向修复包

新增 `src/code2paper/agentic/writer_repair_packet.py`（纯函数）：

- `WriterRepairPacketV1`：repair_kind、escalation（`repair_in_place` / `replan_required`）、
  paragraph_id/section_id、missing_targets（kind + canonical id + reason_code）、
  allowed_edits、allowed_paragraph_ids（**有且仅有失败段落**）、
  `preserve_other_paragraphs=True`、`frozen_paragraph_digests`（已接受段落摘要，失败段落
  被排除）、原正文、authority_refs 与 content_digest；`as_request_payload()` 只暴露模型
  需要的最小修复载荷（不含内部冻结摘要）。
- `build_writer_repair_packet(...)`：按失败码决定 repair_kind 与允许的编辑面
  （detail→`paragraph_content`+`detail_witnesses`；formula→`formula_references`）；
  **权限越界 / 目标越界一律升级为 `replan_required`**（§7.3 末句：不能硬让 Writer 在
  错误段落加一句话过门），此时 allowed_edits/allowed_paragraph_ids 为空。
- `contract_failures_from_legacy_strings(...)`：只读兼容适配（历史 acceptance 失败项 →
  (code, kind, target)），执行层不使用拼接字符串判断（§7.5）。修正了一处解析错误：
  段落 id 自身含冒号（`MA-S3:P1__f1:detail:detail:…`），必须按 `:<kind>:` 标记切分而不是
  按位置切分。
- 事故 attempt-2 实测：两个 detail witness 缺失 → `repair_in_place`，
  targets = `mech_sym:f6cf5bdfe2ae16f0:15/76`，只允许改 `MA-S3:P1__f1`，
  `MA-S3:P3/P4` 摘要被冻结。

验证：regression 92 passed（新增 `test_repair_packet.py` 5 例）；全量离线 3693 passed、
3 deselected、12 subtests passed、exit 0。

## 2026-09-18 WP5 接线：传输失败分类进入 provider 调用分支

- `transport_retry_policy.py` 新增 `transport_failure_failure_code(...)`：把传输失败映射为
  稳定失败码——结果未知 → `send_outcome_unknown:<ExcType>`（保留 reservation、不自动重发）；
  终态 → `transport_terminal_failure:<ExcType>`；可重试 → `transport_retryable_failure:<ExcType>`
  （本层不自动重试，重试必须经策略与 run 预算）。
- `publication_method_writer.py` 的 provider 调用异常分支现在调用该分类器，并把结果追加到
  `blocked_reason`（保留既有 `writer_call_error:<Type>` 前缀以兼容既有断言），使持久片段
  可区分"结果未知"与"内容失败"。
- 结构性守卫测试：provider 调用分支必须包含分类器调用，否则策略层形同虚设。

仍未完成：`unsettled_reservations` 并入写侧预算核算（避免与既有
`unsettled_started_attempt_records` 双重扣费）；真实超时下的端到端集成用例（需注入会
超时的 caller）。

验证：regression 94 passed；全量离线 3695 passed、3 deselected、12 subtests passed、exit 0。

## 2026-09-18 WP3 §7.6：单一正文表面

新增 `src/code2paper/agentic/paragraph_prose_composer.py`（纯函数）：

- `compose_section_markdown(payload, ...)`：由**有序段落对象**确定性拼接正文，顺序用
  `narrative_ordinal`（P2 在 P10 之前），不使用字典序。
- `audit_prose_surface(payload, required_paragraph_ids=...)` → `ProseSurfaceAuditV1`：
  **本地闭集校验**（每个 required id 恰好一次、无重复、无越界、顺序符合叙事序号），
  不依赖 provider 是否支持 JSON Schema 的数组约束；同时判定 `section_markdown` 是否为
  派生物。序列化结果显式带 `valid`。
- `normalize_writer_section_payload(...)`：把响应归一为"段落对象唯一真源"，
  `section_markdown` 一律替换为确定性派生结果并标 `section_markdown_derived=True`；
  模型自带的那份不再作为正文来源（消除两表面漂移）。
- 事故实测：attempt-2 完整响应含 `section_markdown` + 16 段 → 审计通过、段落为真源；
  attempt-1 只写了 1 段 → 本地校验报出 15 段缺失；合成用例覆盖重复段、越界段、乱序段。

验证：regression 100 passed；全量离线 3701 passed、3 deselected、12 subtests passed、exit 0。

## 2026-09-18 WP3 §7.4：atom 只能帮助定位，不能单独证明 detail

- `publication_transaction_contract.py` 新增 `_atom_path_detail_verified(detail_id,
  constraints, witness_by_key)`：当 detail **自身声明了语义要求**
  （semantic_atom / conditions / polarity）时，其 atom 文本必须同时满足这些要求才能
  触发"完整 atom 集合补全 detail"；atom 文本缺失或不满足 → 返回 False，由调用方给出
  `detail_semantic_mismatch` 细分错误并计入 missing，而不是"见到 atom 就算写了"。
  detail 未声明要求时，完整 atom 集合仍是既有契约认可的无损证明（行为不变）。
- 现状说明：detail 键的约束当前是聚合占位（`exact: ()`/`semantic_atom: ""`/
  `polarity: "unknown"`），真实的语义要求挂在 atom 约束上（semantic_anchor /
  exact_excerpts / conditions / polarity），本守卫对两者都适用，是面向未来的收口。
- 测试（`test_witness_projection.py` 新增 2 例）：atom 定位成立 → detail 可补全；
  atom 文本不落在契约/语义内 → 拒绝且给出细分类失败码；直接单测守卫在"无要求/要求成立/
  要求不成立/文本缺失"四种输入下的判定。

> 过程记录：本条目两次测试失败均来自我写错的期望（臆造的 `detail_requirements` 字段、
> 把中性句判定为 positive 极性），而不是实现缺陷；已按判定器的真实语义改写测试。

验证：regression 102 passed；全量离线 3703 passed、3 deselected、12 subtests passed、exit 0。

## 2026-09-18 收尾核对：预留视角防双重扣费 + invocation plan 截断审计

### 1. 两种预留视角（WP5）

- **崩溃点视角**（`writer_attempt_ledger.unsettled_reservations`）：只保留"可能已产生
  真实开销且结果未知"（`send_outcome_unknown` / `response_without_completion`）；
  "已预留未发送"可安全释放。
- **预算视角**（`unified_invocation_ledger.unsettled_started_attempt_records`）：保守地把
  "started 且无 completed"都算作未结算。
- 结论：两者语义不同，**不得相加**；写侧预算核算继续只使用后者，前者用于诊断与结果
  未知处理。已在模块 docstring 写明契约，并用回归钉住：
  * 事故归档 4 个 attempt 都有 completed 回执 → 两种视角都必须为空（拒发事件不计费）；
  * "已预留未发送" vs "已发送无响应"在两种视角下的差异被显式断言。

### 2. invocation plan 截断审计（WP4）

对 `unified_context_compiler.py` 的 invocation plan 构建段（约 4107–4540 行）做只读扫描：
未发现对页/调用集合的切片截断（唯一的 `[:8]` 是错误信息里截断 ID 列表用于展示），
预算越界一律走 `UNIFIED_INVOCATION_BUDGET_EXCEEDED` / `run_budget_insufficient_after_repage`
等显式失败（该文件内相关错误常量出现 98 处）。结论：不存在"剩余页被静默截掉"的分支，
符合 §8.5。

验证：regression 104 passed；全量离线 3705 passed、3 deselected、12 subtests passed、exit 0。

## 2026-09-18 §15：authoring doctor（只读诊断）

新增 `src/code2paper/agentic/authoring_doctor.py` + `AuthoringDoctorReportV1`：
一条命令给出执行身份（引擎/目标是否分离）、各阶段状态、逐页内容预算余量与拒发事件、
首个根因与下游阻断、空语义段落数、Binder-owned 目标仍暴露给 Writer 的数量、
critical 阻断与 next action；全程只读（不写文件、不发请求），供 live 准入的
"doctor 无 critical 阻断"使用。

事故归档实跑输出：

```
EXECUTION       legacy identity; engine fingerprint unavailable
TARGET          EBCAR - Embedding-Based Context-Aware Reranker @ 287506e3e2df
FORMALIZER      0 receipt(s)
WRITER          4/5 sections complete; incomplete
REALIZER        20 receipt(s)
BINDER          not produced
PAGES           19/20 accepted
BLOCKED         inv:writer:MA-S3:page:751aa8b5… (2/2 content attempts)
INTENT SURFACE  27 paragraph(s) lack per-paragraph material
WITNESS OWNER   110 Binder-owned target(s) still shown to Writer
FIRST CAUSE     …writer_v2_invocation_acceptance_count:…:0
NEXT ACTION     read-only diagnosis or explicit authoring fork
```

过程中的两处口径修正（均由测试与实跑暴露，非实现缺陷）：
1. 页"已接受"必须同时看内容验收记录**与分节回执**（resume 复用页没有新的验收记录）；
2. 账本需要区分两种接受语义——`accepted`（**任一**含 repair 的验收通过 = 页内容完成，
   用于判断是否还需发送）与 `primary_accepted`（非 repair 的首次交付接受 = 页交付门
   语义）。此前把 repair 接受排除在 `accepted` 外，导致 3 个 repair 后已完成的页被误判
   为耗尽。

验证：regression 108 passed；全量离线 3709 passed、3 deselected、12 subtests passed、exit 0。

## 2026-09-18 §15 收口：doctor 进入既有 CLI

- `code2paper method-agent doctor --out <dir> [--json]`：走既有产品入口（不新增第二套
  CLI），只读诊断；文本渲染等价于 §15.1 的样式，`--json` 给结构化报告供自动化消费。
- 冒烟（事故归档）：exit 0，输出 19/20 页接受、1 页耗尽（2/2）、27 段缺材料、
  110 个 Binder-owned 目标仍暴露给 Writer、根因链路完整。

验证：regression 109 passed；全量离线 3710 passed、3 deselected、12 subtests passed、exit 0。

## 2026-09-18 S8：离线端到端（产品路径 + 身份/索引/doctor 全链）

新增 `tests/regression_20260917/test_authoring_end_to_end_offline.py`（provider=NONE，
无需 live 授权，纳入常规回归）：

1. 离线产品 run 写出 RunIdentity 与 **AuthoringExecutionIdentityV2**（引擎 commit、
   目标 commit、intent/claims 摘要齐备）与 run summary；
2. 索引与 doctor 在真实 run 上一致：执行身份条目为 `active`、发布 index revision=1、
   doctor 报 `AuthoringExecutionIdentityV2` 且引擎指纹可用、无
   `engine_fingerprint_unavailable` 阻断；
3. 重开语义（WP1 准入实测）：`new` 对非空目录被拒（`run_directory_not_empty`），
   同一身份 + 相同输入走 `auto` 解析为 resume 且**身份字节不变**；
4. fail-closed 不变量：离线 run 不写出非空 candidate/verified，也不误报耗尽。

**端到端测试发现的真实缺陷（已修）**：产物索引把"不含 `worksets`/`pages` 键"的产物
（身份、回执、计划）一律判为 `valid_empty`，会让 `allow_empty=False` 的读者错误拒绝这些
产物。已把判空收窄为"仅在产物自身声明 manifest 形状时才判空"。

验证：regression 113 passed；全量离线 3714 passed、3 deselected、12 subtests passed、exit 0。

## 2026-09-18 §14.1：live 准入预检（离线可跑，授权到手即可进 L1）

新增 `src/code2paper/agentic/live_admission_preflight.py` +
`tests/regression_20260917/test_live_admission.py`，并接入既有 CLI
（`code2paper method-agent live-admission ...` / `record-offline-receipt ...`）。

§14.1 的每一条必要条件都变成一个有名 gate，`ready=False` 时给出**具体阻断码**：

| gate | 阻断码 | 判据 |
|---|---|---|
| engine_identity | engine_identity_unavailable | 引擎 commit + 逐文件内容指纹可用（工作树 dirty 被折进 digest 并告警） |
| target_identity | target_identity_unresolved | 目标仓库 commit/tree 指纹可解析 |
| author_materials | author_material_missing | 作者意图与 claims 存在且非空 |
| model_profile_identity | model_identity_unresolved | provider/model 显式声明 |
| declared_budget | run_budget_not_declared | 上下文窗口、writer 调用数、输入 token 预算均显式 > 0 |
| transport_policy | transport_policy_unbounded | 重试有界、未知结果不自动重试、重试计入预算 |
| offline_suite_receipt | offline_suite_receipt_missing / _not_passed / _stale | 离线全链**真实结果回执**，且绑定当前 engine source digest |
| runtime_model_identity | runtime_model_identity_mismatch | `/health` 正常且 `/v1/models` 真的服务所配置模型 |
| run_open_decision | run_open_rejected:<code> | 复用 WP1 准入状态机（new/resume/fork 语义不重写） |
| doctor_critical_clear | doctor_critical_blocker | 已有 run 时 doctor 无 critical 阻断 |

设计要点：

- **只读**：不建 out 目录、不写身份、不发请求（测试断言 out_root 事后不存在）。
- **回执绑定**：`record-offline-receipt` 跑真实 pytest 并解析真实汇总行；换一行源码即失效
  （engine digest 变），杜绝"之前跑过"当作现状。
- **不重写语义**：目录准入直接调用 WP1 的 `validate_run_open`，模型配置走产品同一路径
  （`_apply_llm_profile` + `load_llm_config_from_env`），因此预检身份与 run 身份同源。
- **退出码**：`live-admission` 0 = 可进 live，3 = 明确不可进，2 = 输入错误。

冒烟（冻结事故归档，`--run-open-mode resume`）：NOT READY，`run_open_rejected:*` ——
归档无引擎指纹且 invocation 已耗尽内容预算，符合 §14.2 "保持失败身份，修复后再明确 fork"。

验证：`tests/regression_20260917/test_live_admission.py` 12 passed；全量离线见下。

补记（同一轮，预检收口）：

- **fork_authoring（L2）**：预检与启动器共用 `verify_research_import`，研究导入
  参与身份；无可信 checkpoint 或空壳 JSON（缺 `run_id`/`repo_snapshot_id`/
  `project_tree_hash` 绑定）→ `research_import_unverifiable` + 准入拒绝。
  预检因此对 L2 也能给出与真实 run **一致**的 execution_id。
- **作者材料口径**：author intent 必需；claims 在产品入口可选——未声明只告警，
  **声明了却缺失/为空**才阻断（不静默把身份降级成"无 claims"）。
- **CLI 路由修复**：`code2paper method-agent doctor|live-admission|
  record-offline-receipt` 之前会被 `supervised_method_agent_main` 当成未知子命令
  而 `parser.error`（doctor 的 CLI 实际不可达），或更糟——被包进 worker 监督进程
  从而创建 attempt 目录/进程清单/日志，破坏"预检只读"。现在这三个命令直接走
  `method_agent_main`，测试断言只读命令不产生任何 out 目录副作用。
- `record-offline-receipt` 在 engine root 下执行 pytest，回执 command 字段记录 cwd。

验证：`tests/regression_20260917/` + `test_agentic_method_agent_cli.py` +
`test_agentic_candidate_handoff.py` 共 163 passed；全量离线见下。

### live 执行顺序（授权后可直接照做；顺序有硬约束）

**顺序约束**：任何文件改动（含文档）都会改变 engine source digest → 使已录制的离线回执失效。
因此必须：**改完 → 提交 → 录回执 → 预检 → live**，中间不得再改任何文件。

```bash
# 1) 提交后录制离线全链回执（真实 pytest 结果，绑定当前引擎指纹）
python -m code2paper.cli.main method-agent record-offline-receipt \
  --out /tmp/c2p-live/offline-receipt.json          # 回执必须放在引擎树之外

# 2) 准入预检（只读；READY 才进 live）
python -m code2paper.cli.main method-agent live-admission \
  --repo <EBCAR> --out /tmp/c2p-live/L1 \
  --llm-profile tests/live/profiles/qwen38_vllm_budgeted.example.env \
  --run-open-mode new --context-tokens 131072 \
  --max-writer-calls <N> --max-input-tokens <N> \
  --offline-receipt /tmp/c2p-live/offline-receipt.json \
  --health-json /tmp/c2p-live/health.json --models-json /tmp/c2p-live/models.json

# 3) L1 失败局部任务重验（复用冻结研究证据，经同一 production 投影重建 MA-S3 页）
python scripts/run_authoring_replay.py \
  artifacts/runs/2026-09-17-ebcar-intent-v4-p7-j9L1bn /tmp/c2p-live/L1 \
  --repo <EBCAR> --resume MA-S3 \
  --profile tests/live/profiles/qwen38_vllm_budgeted.example.env --force-profile \
  --authoring-context-mode unified

# 4) L2 仅 fork 研究证据、重做整个 authoring（产品入口 → 会创建 IdentityV2 并走准入）
python -m code2paper.cli.main method-agent run \
  --repo <EBCAR> --author-intent <...> --out /tmp/c2p-live/L2 \
  --llm-profile tests/live/profiles/qwen38_vllm_budgeted.example.env \
  --run-open-mode fork_authoring \
  --research-stage-checkpoint <冻结归档中已校验 checkpoint>

# 5) L3 端到端 fresh + 跨项目（项目集合与预算在运行前冻结）
```

已知口径差异（必须在报告里如实标注，不能被当成已满足）：

- L1 走 `run_authoring_replay.py`，它写 `execution_record.json`（命令、退出码、code-state
  digest、运行账本前后键），但**不**创建 `AuthoringExecutionIdentityV2`；L2 走产品入口则创建。
  若要求 L1 也有 IdentityV2，需要把 replay 入口接到 `create_or_validate_execution_identity`
  （独立小改动，可用 provider=NONE 离线验证）。
- L1 通过 ≠ L2/L3 通过；L2 失败不得清 ledger 后标记为同一修复验证成功。

## 2026-09-18 §14.2 L1 入口接上 WP1 身份 + 两个真实缺陷

用户选择"先不跑 live，继续离线加固（把 L1 入口也接上 IdentityV2 等）"。

### 1. L1（回放）入口与产品入口共用同一准入实现

- `autonomous_method_agent._open_authoring_execution` → 公开为
  `open_authoring_execution`（产品入口与回放共用，避免两套相近准入）。
- 新增 `research_import_digest` 形参：回放永远从冻结证据出发，非 fork 模式也必须把
  "导入的研究证据"绑进身份，否则两份不同冻结输入会得到同一个 execution_id；
  fork 模式下以 checkpoint 校验结果为准，显式摘要与文件冲突即拒绝。
- `scripts/run_authoring_replay.py`：新增 `--run-open-mode`（默认 `auto`）、
  `--research-import`、`--author-intent`；身份在**任何进程产物之前**建立（早于 runtime
  ledger/token 汇总/frozen 拷贝）；被拒 → exit 2 且 fresh 根零污染，拒绝证据写在
  `<fresh>.execution_identity_rejected.json`；`execution_record.json` 记录
  `execution_identity`。

冻结输入默认值：意图图 `artifacts/intent_obligation_graph_v2.json`，研究导入
`artifacts/research_product/research_stage_checkpoint_v1.json`（事故归档实测
`verify_research_import` 通过，digest `sha256:aca55aa7…`）。

### 2. 缺陷（已修，高危）：run 根位于 `artifacts/` 之下时产物写到引擎树

`output_names._out_root` 无条件截断到第一个 `artifacts` 之前 →
`out_root=<ws>/artifacts/runs/<run>` 的全部产物被写进 `<ws>`。冒烟实测：
`publication_writer_result_v1.json`、`deterministic_preflight_v1.json` 出现在仓库
`artifacts/06_authoring/`（已留档到证据目录并还原仓库）。若不修，我原本推荐的 live
运行根（`artifacts/runs/...`，引擎指纹排除路径）会静默把证据写到 run 之外。

修复：仅当 `artifacts` 后紧跟**已知阶段目录**（由 `METHOD_OUTPUTS` 派生：
`01_input`…`10_run`、`research_product`）时才做"子目录 → run 根"归一化。
回归：`tests/regression_20260917/test_output_root_normalization.py`（含 writer 级用例，
已确认对旧实现会失败）。

### 3. 缺陷（未修，已留证）：`prepare` 根把冻结历史用量记成本次 run 的 token 用量

`token_usage_summary_v1.json` 报 `calls=45 / input=1164056 / output=57144`，而同轮
`model_calls: 0`、`/health`、`/models`、`/metrics` 全 `Connection refused`、墙钟 < 1s。
来源：`prepare` 复制冻结 Formalizer 阶段的 invocation 回执（带历史 usage），随后被计入
本次 run。对 §14.3 的"发送调用数 / 真实 tokens / 无效调用量"是失真的，需要区分
"本次发送"与"复用证据用量"。涉及账本口径，未擅自改。

### 4. 测试污染教训（已修）

在测试里直接调用 `run_authoring_replay.main()` 会把默认 live profile 应用进进程环境，
污染同一 session 的后续测试（全量套件出现 8 个与本改动无关的失败）。测试内调用 CLI
必须传显式空 profile 并快照/恢复 `os.environ`。

验证：全量离线 3740 passed、3 deselected、12 subtests passed、exit 0。

## 2026-09-18 §14.3：token 用量区分"本次发送"与"复用证据"（缺陷 2 修复）

上轮留证的缺陷已修：`--authoring-stage prepare` 复制冻结 Formalizer 阶段的 invocation
回执后，token 汇总把这 45 次历史调用（1.16M input tokens）记成**本次 run** 的用量——
同一轮 `deterministic_preflight_v1.json` 却是 `model_calls: 0`。这既让 §14.3 的效率口径
（发送调用数/真实 tokens/无效调用量）失真，也让"这次尝试是否真的发过请求"这条判断
（prepared 根续跑分支依赖 `calls == 0 and total_tokens == 0`）永远不成立。

修复：

- 复制冻结 Formalizer 阶段时写出**来源索引**
  `artifacts/06_authoring/reused_evidence_receipts_v1.json`（相对路径 + 复制时摘要）；
- 汇总时按索引 + 摘要比对分类：一致 → `reused_evidence`；索引声明但内容已被改写 →
  按"本次发送"保守计入并在 `provenance.content_changed_after_copy*` 留痕；
- `token_usage_summary_v1.json` 语义明确化：
  - 顶层 `calls`/`*_tokens`/`status` = **本次发送**（恢复续跑判断所依赖的语义）；
  - `reused_evidence` = 复用冻结证据的用量（不丢失、不冒充）；
  - `all_receipts` = 两者之和（与旧口径可对账）；
  - `provenance` = {sent, reused_evidence, unclassified}。
- 无来源索引时（既有调用方/测试）行为与旧实现逐字段一致。

实测（真实事故归档 + EBCAR 目标，零模型调用）：
```
sent_calls=0 sent_total=0 | reused_evidence_calls=45 reused_evidence_total=1221200
| all_receipts_total=1221200
```
证据：`artifacts/runs/2026-09-18-live-admission/token-usage-provenance-evidence/`
（`before-fix-*` / `after-fix-*` 对照）。

验证：regression 新增 `tests/regression_20260917/test_token_usage_provenance.py`（5 项）；
全量离线 3745 passed、3 deselected、12 subtests passed、exit 0。

## 2026-09-18 §14.3：质量报告（只报可机械复算的维度）

方案 §14.3 要求"不能只报 accepted_pages / pages"。新增
`src/code2paper/agentic/authoring_quality_report.py` +
CLI `method-agent quality-report --out <dir> [--json]`（只读，走既有产品入口）。

六个维度的处理方式（不编分数）：

| 维度 | 状态 | 来源 |
|---|---|---|
| 效率 | measured | invocation 账本（发送数/内容尝试/拒发）+ 回执 provider_usage + 预算信封 |
| 恢复健壮性 | measured | `scan_exhausted_invocations`、doctor 阻塞页、未结算预留、耗尽页失败码 |
| 意图覆盖 | measured/partial | `obligation_coverage_v2`（must-cover/有依据/未解决/显式缺口）+ 意图表面代理指标 |
| 信息利用 | partial | `method_authoring_closure_metrics_v1` 各块 + 消费回执计数 |
| 叙事质量 | partial | 仅代理指标（无段落材料的段数、阻塞页数），并声明"为 0 ≠ 合格" |
| 忠实性 | **not_measured** | 需要冻结证据 + 正文 + 逐句/逐公式比对；离线无判断者，不报分 |

关键口径（事故实测得出）：**接受必须看账本的内容验收记录**，不能看回执的
`delivery_status`——事故里两次 provider 调用的 `delivery_status` 都是 accepted，而页
最终未被接受（`task_status=partial`）。因此效率指标的首次接受率用
`primary_accepted`，repair 收益用 `accepted` + `content_repair_count`。

同时把"复用证据"口径接进报告：复用证据索引抽到产品侧
`src/code2paper/agentic/reused_evidence_index.py`（回放脚本改为调用它），
prepared 根里复制自冻结根的回执不计入本次 run 的效率指标，但以
`reused_evidence_invocations/receipts` 显式报出，不被静默丢弃。

事故归档实测（冻结 oracle）：40 invocations / 45 provider sends（2 次拒发无 provider
request）/ 19 接受 / 首次接受率 0.4 / repair 5 次中 3 次成功 / 1,164,056 input tokens；
唯一阻塞页 2/2 内容尝试耗尽，失败码 `detail_witness_missing` + `detail_semantic_mismatch`；
7 个 allowed formula、消费 0；27 段缺段落材料；comparison 状态 `not_available`
（无候选产物，不伪造 baseline）。

验证：`tests/regression_20260917/test_quality_report.py` 8 项；全量离线 3753 passed、
3 deselected、12 subtests passed、exit 0。

## 2026-09-18 §14.3：对照比较器（同冻结输入/同模型配置才可比）

新增 `src/code2paper/agentic/authoring_quality_comparison.py` +
CLI `method-agent compare-quality --baseline <dir|json> --candidate <dir|json> [--json]`
（只读；exit 0 = 可比，3 = 不可比，2 = 输入缺失）。

- 质量报告新增 `comparability` 锚点（进 content_digest）：
  `frozen_input_digest`（由 `authoring_run_contract_v1` 的 repo_snapshot_id /
  project_tree_hash / run_identity_digest / code_commit_sha 复算）、
  `model_identity_digest` + `profile_digest`（预算信封）、
  `engine_source_digest` / `execution_id`（IdentityV2，legacy 根为空）。
- 比较规则（fail-closed，且**不产生任何综合评分**）：
  - 冻结输入锚点缺失或不一致 → `comparable=False`，**不给差值**；
  - 模型身份缺失或不一致 → 同上；
  - **引擎指纹不同不阻断**——修复正是要比较的对象，差异记入 `scope_notes`；
  - 只有极性明确的机械指标（`METRIC_POLARITY`，如发送数↓、接受率↑、token↓）才给
    `better/worse/same`，其余一律 `unknown` + 原始 delta；
  - 任一侧 `not_measured` 的维度只声明"哪侧没测、为什么"，不出差值；
  - 缺候选产物 → `partial_evidence=True` 并声明"差异只代表已存证据，不代表完整正文质量"
    （§14.3 不伪造旧完整输出）。

事故归档自比实测：COMPARABLE，71 个指标 delta 全 0，`partial_evidence=True`，
faithfulness 两侧未测量并给出原因。

验证：`tests/regression_20260917/test_quality_comparison.py` 9 项；全量离线 3762 passed、
3 deselected、12 subtests passed、exit 0。

## 2026-09-18 不变量 I1–I10 核验 + 修复 I10 缺口

对 §3 的十条不变量逐条找执行点与测试证据，发现并修掉一个真实缺口。

| 不变量 | 执行点 / 证据 | 结论 |
|---|---|---|
| I1 证据权威不变 | 作者意图只进组织/自述；实现事实由 source manifest/研究证据支持（`test_intent_writer_surface.py`） | ✓ |
| I2 单一语义计划 | `test_plan_selection.py::test_v4_selection_does_not_execute_legacy_builder`（legacy 调用为 0） | ✓ |
| I3 段落/任务分离 | 页 manifest 与 owner page 唯一化（`test_output_feasibility.py`） | ✓ |
| I4 义务按 occurrence 守恒 | `assess_paragraph_transaction(paragraph_id, validation_stage)`：键为 `(paragraph, target_kind, target_id, stage)`，同一 detail 在两个段落分别评估 | ✓（构造级） |
| I5 split 不丢条件 | 分页/条件分配（`test_page_calibration.py`、`test_output_feasibility.py`） | ✓ |
| I6 发送≠内容接受 | 账本 `accepted` 只看内容验收记录（`test_ledger_recovery.py`；本轮质量报告实测同结论） | ✓ |
| I7 恢复不重置成本 | 身份 + 租约 + `build_resume_preflight`（`test_execution_identity.py`） | ✓ |
| I8 旧证据不可覆盖 | 产物索引只引用旧对象（`test_artifact_index.py`）+ 归档冻结 fixture | ✓ |
| I9 失败内容不可发布 | `test_authoring_end_to_end_offline.py`（candidate/verified 为空） | ✓ |
| I10 验收规则变更 → 身份变更 | **原为缺口**：`validator_bundle_digest` 恒为 `unspecified`，身份对验收规则改动是盲的 | 已修 |

I10 修复：新增 `VALIDATOR_BUNDLE_SOURCES`（封闭集合：`publication_transaction_contract`、
`writer_output_workload`、`unified_context_compiler`、`mechanism_context_pages`、
`writer_attempt_ledger`、`authoring_artifact_index`、`paragraph_prose_composer`）与
`capture_validator_bundle_snapshot()`（逐文件内容指纹 + 缺失/不稳定失败码）；
`build_run_open_identity` 现在绑定该指纹，并接受 `tokenizer_identity`
（缺省为显式 `unspecified` 标记）。刻意只收 contract 层：把整个 writer 收进来会让任何
重构都使 resume 失效，身份会失去区分度。

验证：`tests/regression_20260917/test_validator_bundle_identity.py` 5 项（含"改验收规则 →
指纹与执行身份都变""缺失来源如实报失败码而非留空"）；全量离线 3767 passed、
3 deselected、12 subtests passed、exit 0。

## 2026-09-22 审计方案接手：PR A（运行身份与 new/resume/fork 语义）

依据 `docs/Code2Paper_代码审计与修复执行方案_20260922.md`（冻结基线 `3aa9db8`）。
本轮完成 PR A 的 A.1（目标内容身份、失败码消费、有效配置身份）与 A.1.6 的未知模式拒绝；
A.2/A.3（出生信息与锁内二次准入）、A.4（导入闭包）留待下一轮。

### 已核实的审计论断（在当前工作树复现）

- **F02 成立**：`capture_target_identity` 用 `dirty_manifest_digest`（只含路径状态、不含
  文件内容），而 `build_run_open_identity` 把 target HEAD 写进
  `target_repo_snapshot_digest`、把 porcelain 摘要写进 `target_project_tree_hash`。
  最小反例：同一文件保持 `M`、HEAD 不变，仅内容 A→B，旧实现得到**同一身份**。
- **A.1.5 成立**：`build_run_open_identity` 只取 `validator_bundle.digest`，不消费
  `failure_code`——来源缺失时也给出"看起来可用"的指纹。
- **A.1.6 成立**：`publication_method_writer._build_narrative_plan_v3` 对未知
  `CODE2PAPER_INTENT_NARRATIVE_PLAN` **静默回退 v3**；有效配置（context mode、输出协议、
  tokenizer）也未进入身份。

### 本轮修复

1. `TargetRepoIdentity` 改为**内容**身份：复用既有 `build_repo_snapshot` +
   `build_repository_source_manifest` 的文件选择规则，新增
   `source_snapshot_digest` / `project_tree_hash` / `source_manifest_digest` / `file_count` /
   `failure_code`；`commit_sha` 与 porcelain 摘要降为诊断。
   路径不存在或零源文件 → `target_snapshot_unavailable:*`（没有字节就没有内容身份）。
2. 身份模型新增 `effective_config_digest`（进 payload：模式变了就不能 resume）与
   `target_git_commit`（诊断，**不**进 payload：同内容换 commit 不应失效）。
3. `build_run_open_identity` 新增 `require_usable_inputs=True`：引擎/目标/验收规则来源
   任一不可用即抛错（在任何模型发送之前）；预检传 `False` 把这些事实报成阻断项。
4. 新增 `authoring_run_config.py` 作为**唯一 owner**：
   `normalize_narrative_plan_mode`（未知值抛 `unknown_narrative_plan_mode`）与
   `capture_effective_config_digest`（narrative/context/输出协议/prompt/tokenizer/
   验收规则身份）。writer 与身份构造消费同一实现。
5. 接线复核（审计 §0.1 提醒的调用点核对）：`autonomous_method_agent` 的 runtime 复查
   原先拿 `target_repo_snapshot_digest` 与 runtime commit 比较——现在改用诊断字段比 commit、
   用 `project_tree_hash` 比内容；replay 身份报告补充 manifest/commit/effective config 字段。
6. live 准入新增 `validator_bundle_identity` gate 与有效配置失败路径（不可比即拒绝，
   不再解引用空身份）。

### 测试

新增 `tests/regression_20260917/test_run_identity_content.py`（10 项），含审计点名的
`test_target_dirty_content_change_invalidates_resume`、
`test_same_target_content_in_another_path_has_same_content_identity`、
`test_missing_validator_source_blocks_before_provider_send`、
`test_unknown_narrative_mode_is_rejected`（含真实 builder 路径）。

**测试夹具缺陷（已修）**：`tests/test_agentic_candidate_handoff.py::test_supervisor_preserves_real_worker_exception_finalizer`
把**全局** `subprocess.Popen` 换成假对象，连 git 子进程一起拦掉。PR A 之前引擎快照
不可用只是被静默容忍，所以没暴露；现在 fail-closed 会让 worker 抛 `ValueError` 而不是
预期的 `RuntimeError`。夹具改为只拦截监督器的 worker spawn（其余委托真实 Popen，
并补齐 `args`/`communicate`/上下文管理），这样它测的仍是"worker 异常终结器"。

### PR A.2 / A.3：出生信息与锁内二次准入（本轮）

**A.2 出生信息（修 F03）**

- 新增 `BirthMetadataV1`（creation_mode / parent_execution_id / research_import_digest）
  与 `AuthoringExecutionIdentityV2.birth_metadata`；新增 `resolve_open_identity()` 作为
  "本次动作 → 身份"的唯一 owner：
  - `resume` / `auto` 且已有完整身份 → **继承**出生信息（实测 fork 执行现在可以 resume，
    修复前 `resume_identity_mismatch: creation_mode`）；
  - 其它动作 → 按本次动作新建出生信息；`fork_authoring` 的 `parent_execution_id` 取自
    导入 checkpoint 的 `execution_id`（若存在）；
  - `resume` 时**显式提供**另一份 checkpoint → 拒绝（`research_import_digest_mismatch`），
    不静默忽略操作者提供的证据；
  - 旧目录没有完整身份时不猜，仍由 `validate_run_open` 拒绝。
- `preflight_run_open` 改用同一 resolver，并把输入不可用/导入不匹配翻译成类型化拒绝。

**A.3 锁内二次准入与租约生命周期**

- `acquire_run_lease` 的进程内幂等改为**校验 owner**：不同 execution 在同一 root 上
  直接 `RunLeaseHeld`（旧行为只要 root 相同就返回别人的锁）。
- 新增 `PENDING_LEASE_OWNER` 与 `RunLease.bind(execution_id)`：支持"先取锁 → 锁内解析身份 →
  绑定 owner"的序列，绑定后再拒绝其它执行。
- `open_authoring_execution` 重写为：只读预检（早退明显错误）→ 取锁 → **锁内**重新解析
  身份与目录状态 → `validate_run_open` → 绑定 → create-or-validate；任一拒绝/异常都释放锁
  （租约不泄漏给后续尝试）。
- 产品入口 `run_autonomous_method_agent` 的 `finally` 释放 lease 并从 `_ACTIVE_RUN_LEASES`
  移除：长寿命进程里的连续任务不再被自己的旧 flock 挡住。

**测试**：`test_run_identity_content.py` 扩到 15 项（新增 5 项：fork resume 出生信息守恒、
new 不继承旧出生、导入变更拒绝续跑、两个 new 打开者不能都准入、租约成功/异常都释放）；
`test_execution_identity.py` 的租约用例改为审计语义（同 owner 幂等、异 owner 拒绝）并新增
绑定用例。全量离线 3783 passed、3 deselected、12 subtests passed、exit 0。

**本轮事故与纠正**：第一次改 `authoring_execution_identity.py` 时用大段字符串切片替换，
把 `build_run_open_identity`/`capture_target_identity`/`RunLease` 等函数整段删掉；
已 `git checkout --` 还原该文件后改用定点编辑重做（后续同类改动一律小步定点 + 每步
compile/定向测试）。

### PR A.4：研究导入的闭包校验（本轮）

审计 §A.4 指出 `verify_research_import` 只验证 checkpoint 外壳。新增
`verify_research_import_closure(checkpoint, *, expected_project_tree_hash=None)`：

- **外壳**（既有）：文件存在、可解析、含 run_id / repo_snapshot_id / project_tree_hash；
- **provenance 绑定**：checkpoint 的 `project_tree_hash` 必须等于当前目标仓库的**内容**
  tree hash（实测事故归档的 `sha256:9b4f1a34…` 与本机真实 EBCAR 目标完全一致 → 严格校验
  不影响合法 L2 fork）；
- **必备权威材料**（8 项，封闭集合 + 各自模型校验）：intent_graph / agenda /
  atomic_claims / evidence_packets / code_facts / source_manifest / symbol_index /
  implementation_scope；
- **内容一致性**：会自封摘要的模型做"删 digest 重算必须等于原值"；声明了
  repo_snapshot_id/project_tree_hash 的产物必须与顶层一致；facts→packets→claims 的
  digest 引用链必须闭合；
- **路径安全**：manifest / symbol index 中声明的仓库路径必须相对、无 `..`/`~`/绝对路径；
- **禁止继承**：出现 `writer_*` / `content_acceptance*` / `binder_receipt*` /
  `publication_candidate*` / `invocation_budget*` / `active_pointer*` / `run_lease*`
  等 payload 即拒绝。

接线：`resolve_open_identity` 的 fork 分支使用闭包（并复用同一份 target 快照，
不重复计算）；`preflight_run_open` 与 CLI 得到类型化拒绝码；回放脚本的导入校验同样升级为闭包。

新增 `tests/regression_20260917/research_import_fixture.py`：以归档 checkpoint 为基、
**只对改写过的产物重新封装摘要**，生成"内容与摘要自洽"的真实形状 fixture（空壳 JSON 正是
审计要求拒绝的对象）。负面用例：缺失依赖、摘要链断裂、路径越界、夹带写作 payload。
另加 skip-guarded 端到端正例：真实 EBCAR 目标 + 事故归档导入 → 准入允许（本机已跑通）。

验证：regression 185 项全绿；全量离线 3786 passed、3 deselected、12 subtests passed、exit 0。

## 2026-09-22 审计 PR B：统一账本与恢复矩阵（F04）

### 已复现的审计论断

- `_attempt_records`/`read_attempt_outcomes` 只 glob `completed`（+started）：孤立
  request/response、只有 started 的崩溃点不在 attempt 集合里；
- `_invocation_directory` 用 substring 命中后取 `matches[0]`（审计禁止）；
- `scan_exhausted_invocations` 只看"最新 completed 里有没有 attempt_limit_exhausted"，
  两次真实失败但没有第三次拒发记录时不报告；
- 发送侧 `_capturing_writer_caller` 用"事件号 > 上限 且（内容预算耗尽 或 没有拒发记录）"
  的混合条件。

### 本轮实现

新增统一归约层（`writer_attempt_ledger.py`）：

- `AttemptRecoveryStateV1` 八态 + `RECOVERY_ACTIONS`（每态自带允许/禁止动作）；
- `InvocationRecoveryV1`（state / primary_cause / counters / unknown_reservation_attempts /
  blocks / evidence / 契约 mismatch / allowed,forbidden actions）；
- `reduce_invocation_recovery(out_root, invocation_id, *, content_attempt_limit,
  contract_digests)`：attempt 集合来自**全部**事件文件的并集（正则解析
  `attempt-0001.<kind>.json`，点分隔）；损坏文件进入 `blocks` 而不是静默跳过；验收按
  execution/plan/validator 契约绑定，不匹配时记录 `contract_mismatch`。
- 目录解析改为精确匹配（精确名或 `精确名-单段摘要`，且回执自称的 invocation_id 必须一致）。

判定优先级（按信息量与可结算性）：`ledger_corrupt` > `accepted_reusable` >
`response_missing_or_ledger_inconsistent` > `validation_pending`（有响应**从未验收**，
可本地结算）> `content_budget_exhausted` > `response_received_unsettled` >
`send_outcome_unknown` > `reserved_not_sent`。

原有 reader 全部改为薄包装：`read_invocation_ledger_state`、`read_attempt_outcomes`、
`unsettled_reservations`、`scan_exhausted_invocations`（新增 `required_invocation_ids`/
`content_attempt_limit` 形参）、`authoring_doctor.DoctorPageV1`（新增
`recovery_state`/`primary_cause`/`unknown_reservation_attempts`）。

发送侧 `_capturing_writer_caller` 改为只消费归约结论：`content_budget_exhausted` →
`attempt_limit_exhausted:…`（保持既有码），`send_outcome_unknown` /
`response_received_unsettled` / `ledger_corrupt` → 各自的 typed 拒发码；删除
"事件号 + 拒发存在性"混合条件。pre-send 分类器同步识别新码。

事故归档实测分布：19 `accepted_reusable` / 20 `validation_pending`（已交付但从未验收的
realizer/writer 调用，本地即可结算）/ 1 `content_budget_exhausted`（MA-S3 页，即事故本身），
与归档事实一致；doctor 阻塞页由 1 变为正好 1（realizer 页不再被误判为阻塞）。

测试：新增 `tests/regression_20260917/test_ledger_recovery_matrix.py`（14 项）覆盖 §B.3 八行
状态表 + §B.6 补充反例（两次真实失败无拒发记录、两次纯拒发零发送、接受后残留拒发记录、
同页不同 validator、所有 reader 结论一致）。全量离线 3800 passed、3 deselected、
12 subtests passed、exit 0。

### PR B 尾部：本地验证重放结算（§B.5）与未知发送预留（§B.2）

- 新增 `ValidationReplayV1` + `publish_validation_replay` + `read_validation_replays`：
  本地结算写成**新增**的 `attempt-XXXX.validation-replay.<validator>.json`，显式携带
  `source_response_digest` / `validator_bundle_digest` / `contract_digest`；拒绝两种情况：
  该 attempt 已有历史 `content-acceptance.json`（不得冒充历史结论）、同一 validator 的
  重放已存在（重放自身幂等）。
- reducer 消费重放：当前 validator 身份且 accepted → `accepted_reusable`；同一 attempt 已
  结算过 → 不再算"待本地验收"；rejected 重放按其失败码计入内容预算；**旧 validator 身份**
  的重放被标为 `stale_validation_replay:<attempt>:<digest>` 并拒绝复用。
- §B.2 用测试钉住既有行为：`send_outcome_unknown` 的 attempt 在崩溃点视角
  （`unsettled_reservations`）与预算视角（`unsettled_started_attempt_records`）都保留，
  且 `acceptance_replayable=False` —— 未知结果既不能被当成"未发送"，也不能被当成
  "真实 0 tokens"。

测试：`test_ledger_recovery_matrix.py` 扩到 19 项。

## 2026-09-22 审计 PR C（F01）第一片：发送前实际请求复核（§C.6）

新增 `src/code2paper/agentic/page_contract_recheck.py`：

- `capture_page_contract_snapshot(out_root, invocation_id)`：从该 invocation **最早一次
  持久化请求**提取冻结契约（page_id / section_id / 段落 id **顺序** / detail·formula·
  rhetorical scope / 输出上限 / request digest）；
- `page_contract_snapshot_from_payload(...)`：同一次运行内，primary 的 provider-request 可能
  在响应处理之后才落盘，而 content repair 在响应处理中就已构造——因此 primary 用**内存中的
  实际请求**建立契约快照并缓存，repair 才回读磁盘（实测：不做这一步，repair 会因
  `frozen_page_contract_missing` 被误拒）；
- `compare_actual_request_to_page_contract(...)`：段落集合与**顺序**必须逐一相等、
  page/section 一致、scope 相等、输出上限不得超过冻结值；**repair 没有冻结契约即拒绝**
  （primary 由 envelope digest 兜底）。

接线：`_capturing_writer_caller` 在既有 page bytes/page id/tasks/prompt/schema/envelope
检查之后追加这一层，失败码 `actual_page_contract_mismatch:<detail>`，在发送前拒绝，
不消耗 content repair。

**新复现的事实（待 PR C 后续修）**：事故归档第一次 Writer 请求里的段落顺序是**字典序**
（`P10…P17, P1__f1, P3…P9`），而计划的叙述顺序是 `P1__f1, P3…P17`（归档
`INCIDENT_PAGE_PARAGRAPH_IDS`）。审计 §C.1 要求 packing unit 携带 explicit narrative order、
§4 的 I5 要求实际请求顺序与冻结契约一致——这是 C.1/C.4 的修复目标，已用
`test_frozen_request_order_is_lexical_not_narrative` 固定为"当前事实"。

测试：`tests/regression_20260917/test_page_contract_recheck.py` 9 项（真实归档请求上的
追加段落/重排/缩小 scope/抬高输出上限/repair 缺契约/只读确定性）。全量离线 3814 passed、
3 deselected、12 subtests passed、exit 0。

**PR C 剩余（下一轮）**：C.1 统一 packing unit（header 提前返回、无 atom 段落跳过）、
C.2 统一候选页判定并让段数上限成为辅助安全限、C.3 输出估量补齐 witness span 与 schema
骨架、C.4 页重组优先于拆段并记录 fragment 义务映射、C.5 重分页后重建 invocation/预算/
快照。

### PR C（F01）第二片：无 atom 的叙事段落按同一候选页契约分页（§C.1/§C.2）

复现的旧行为：`_build_section_pages` 在 `not atom_ids` 时**直接返回一张 header 页**，
把该 section 的全部段落塞进去，候选页段数上限完全没被使用（审计最小反例 A：7 个无 atom
作者段落 + 上限 6 仍是一页）。

修复：header 分支改为按**同一套候选页判据**分页——段数上限（辅助安全限）+
`max_page_input_tokens`（主限）；单个段落自身超限时给出说明**真实限制维度**的 typed
failure（`paragraph_count:N>limit` 或 `input_tokens:N>limit`），不再只打印一个其实未超的
不等式（§C.4 末条）。

回归：`test_narrative_only_section_is_paged_by_the_candidate_contract`（7 段无 atom →
≥2 页、每页 ≤ 上限、段落不丢不重）。全量离线 3815 passed、3 deselected、12 subtests passed。

**PR C 仍缺少（下一轮）**：
- C.1 混合 section：技术分组仍对 `not group_atoms` 执行 `continue`，叙事段落由 adapter
  追加到 residual 页——最终请求的段落数因此仍可能超出候选上限（当前由 §C.6 发送前复核
  fail-closed 拦住，但编译器本身还没统一 packing unit）；
- C.1 段落顺序：实测冻结请求是字典序而不是叙述顺序（见上一节）；
- C.2 段数上限的显式策略标注（0=关闭只能是显式实验配置，生产准入需标注）；
- C.3 输出估量补 witness span 与 schema 骨架计量；C.4 拆段义务映射；C.5 重分页后重建
  invocation/预算/快照。

### PR C（F01）第三片：页内段落顺序改为叙述顺序（§C.1 / I5）

**复现的机制**：`_section_page_payload` 与打包循环内的 `_payload` 都写
`"paragraph_ids": list(sorted(set(...)))` —— 段落顺序被换成**字典序**，计划的叙述顺序
（以及 narrative unit 的 paragraph 顺序）在进入请求前就丢了。这正是事故请求里
`P10..P17, P1__f1, P3..P9` 的来源。

修复：两处都改为保序去重（`dict.fromkeys`），页内段落顺序从此等于计划顺序。回归
`test_page_payload_preserves_the_narrative_paragraph_order` 用"字典序 ≠ 叙述顺序"的 id
夹具（`p1__f1, p3, p10`）钉住；旧实现下该断言必然失败。全量离线 3816 passed。

**本轮查清、下一轮要改的机制（混合 section）**：页面对外的段落清单来自
**adapter 对 narrative plan 的挂载**（事故请求的 `narrative_plan.page_paragraph_ids` 有 16 段），
而编译器打包时只看到技术分组里的 1 段（`not group_atoms: continue` 把叙事段落跳过，注释
里说"由 adapter 挂到 residual page"——但 `publication_method_writer` 里没有这段逻辑，
compiler 里也没有 residual 组装）。因此候选页判定看到的段落数与实际请求的段落数仍然不同。
要按 §C.1 统一 packing unit，必须把"计划层面的段落归属"前移到打包循环（技术闭包降为
packing unit 的一个属性），并同步 C.5 的重建步骤；这是下一轮 PR C 的主任务。

### PR C（F01）第四片：段数上限的显式策略标注（§C.2）

审核要求："段数上限可作为辅助安全限制，但不能替代 token 和义务估量。0=关闭上限只能作为
显式实验配置；生产准入必须标注该策略，不接受环境变量悄悄改变契约。"

- 新增 `semantic_paragraph_limit_policy(environment=None)`：返回
  `{value, source(default/environment/environment_invalid_fallback_default), valid,
  disabled, experiment_acknowledged}`；`_max_semantic_paragraphs_per_page()` 改为它的
  薄包装（单一 owner）。
- **进入有效配置身份**：`capture_effective_config_digest` 现在把该策略写入 payload，因此
  用环境变量改上限会改变执行身份（不能再"悄悄改契约"）。
- **live 准入新 gate** `semantic_paragraph_limit_policy`：关闭上限而未显式声明实验
  （`CODE2PAPER_UNIFIED_PARAGRAPH_LIMIT_EXPERIMENT=1`）→ 阻断
  `semantic_paragraph_limit_policy_unacknowledged`；非法值同样阻断（不再静默回落默认）。

测试：`test_page_contract_recheck.py` 扩到 13 项（策略取值/来源/实验声明/非法值 +
有效配置身份绑定 + 准入阻断与声明后放行）。全量离线 3818 passed、3 deselected、
12 subtests passed、exit 0。

### PR C（F01）第五片：输出估量补齐 witness 成本与标定门槛（§C.3）

复现的两个审计反例：

1. **witness 不计入总量**：`writer_owned_witness_count` 只被统计，`estimated_output_tokens`
   的求和里没有它 —— 保持段数/detail/goal 不变、只增加合法 Writer-owned witness，
   估量**完全不变**。
2. **非空字典即"已标定"**：`if not profile: uncalibrated else: calibrated`，因此只塞入
   两个系数（甚至无关键）的字典就能把 confidence 升级成 `calibrated`。

修复：

- 新增 `writer_witness_tokens`：按 occurrence 计（对象骨架成本 `per_witness_object_tokens`）
  加**预期 span 长度**（优先真实 span 文本，取字段
  `exact_span/span_text/expected_span/witness_text/target_text`；缺失时用保守默认长度），
  并计入总量；
- formula 引用改为**并集去重**（package 与 obligation 同列一个引用只计一次），
  另加 `formula_placeholder_count/tokens`（"义务"与"实际 placeholder 数"的显式映射）；
- `confidence` 升级为 `calibrated` 需要 `CALIBRATION_REQUIRED_KEYS` 全部非空
  （model_identity / tokenizer_identity / schema_or_prompt_identity / sample_scope /
  method）；缺失时保持 `uncalibrated` 并报
  `calibration_profile_incomplete:<keys>`；字符代理估算器仍单独标出
  `token_estimator_is_character_proxy`（calibrated 只描述系数来源）。

测试：`test_output_feasibility.py` 新增/更新 3 项（witness 计入且 atom 不计入、
package/obligation 不双计、标定门槛与完整 profile），并更新原先编码旧语义的
`test_calibrated_profile_changes_estimate_and_confidence`。全量离线 3820 passed、
3 deselected、12 subtests passed、exit 0。

### PR C（F01）第六片：最终段落集合的复核 owner（§C.1/§C.4）

**本轮查清了 F01 的完整机制**（用事故归档逐项核对）：

- 技术 payload 的 `paragraph_ids` 只有 **1** 段（`MA-S3:P1__f1`），实际请求的
  `narrative_plan.page_paragraph_ids` 有 **16** 段；
- `publication_method_writer` 里的 `paragraph_page_id` 决定每段归哪一页：先看该段是否
  出现在某页技术 payload 里，否则**按 detail 归属**路由到某一页；随后
  `page_paragraph_id_set = 技术段落 ∪ 路由段落` —— 页的最终段落集合是在这里才确定的；
- 候选页判定（段数上限/输出估量）发生在更早的技术分组阶段，看的是那 1 段。
  所以"被验收的对象 ≠ 实际执行的对象"在事故里具体表现为：**16 段的页按 1 段通过了判定**。

修复（在确定最终集合的同一 owner 上复核，§C.4 允许的"真实维度 typed failure"）：

- 新增 `assert_page_paragraph_set_within_limit(page_id, paragraph_ids, *, limit_policy=None)`：
  保序去重后按同一策略复核，超限即抛
  `UNIFIED_PAGE_CONTRACT_EXCEEDED_AFTER_ASSIGNMENT`，消息给出真实维度
  `paragraph_count:16>6`；`0=关闭上限` 的显式实验模式不做该检查（与 §C.2 一致）。
- `publication_method_writer` 在算出 `page_paragraph_id_set` 后立即调用它——事故形状
  （1 技术 + 15 叙事 = 16）现在会在发送前以明确理由失败，而不是进入一个注定写不完的请求。

测试：`test_final_page_paragraph_set_is_checked_against_the_limit`（等于上限放行、
事故形状 16 段被拒且消息带真实维度、去重不掩盖段数、实验模式放行）。全量离线 3821 passed、
3 deselected、12 subtests passed、exit 0。

**仍缺（下一轮）**：真正的**重分页**——在同一 owner 上把超限页拆成多页并重建
worksets/invocation plan/预算预留/阶段快照（§C.5）；本轮是"早失败"而不是"自动拆页"。

## 2026-09-22 审计 PR F 第一片：索引必须验证它声称冻结的字节（F.2/F.5）

复现的审计论断（全部成立）：

- 非法 JSON → `payload=None`，文件仍拿到 `active`；
- 显式 `reference_digests` 零命中 → 回退选最高 generation；
- `resolve_artifact` 不重算字节，只比较索引缓存里的 semantic digest；
- `upstream_digests` 恒为空。

修复：

- 新增 `invalid` 状态：解析失败 → invalid；声明了**不受支持** schema 版本 →
  invalid（`_KNOWN_SCHEMA_VERSIONS` 白名单，版本来自归档实测；未声明版本的 legacy
  产物照旧可读）。invalid 不参与 active、不被标 superseded、不可解析。
- 显式引用改为**必须唯一命中**，零命中即 active 置空 → `resolve_artifact` 抛错，
  不再"回退选最高代"。
- 新增 `read_artifact_validated(index, role, phase, *, out_root, expected_digest=None,
  allow_empty=True) -> ValidatedArtifactReadV1`：解析路径后**读取一次字节**，重算
  `file_bytes_digest` 与索引记录比对，并用 producer 模型（已注册 3 个 role）**复算**
  语义摘要；未注册 producer 的 role 如实标 `semantic_digest_verification="declared_only"`，
  不假装已复算。返回的 `payload` 就是被验证过的那份字节解码结果（避免 TOCTOU）。

测试（含 F.5 要求的变异测试）：`test_artifact_index.py` 新增 5 项——非法 JSON 不得 active、
不支持 schema 不得 active、显式引用零命中不得回退、**索引发布后改动文件在使用前失败**
（`artifact_bytes_changed_since_index`）、已注册 role 复算 vs 未注册 role 如实标注。
全量离线 3826 passed、3 deselected、12 subtests passed、exit 0。

**PR F 仍缺**：F.1 producer 注册制（`_KNOWN_ARTIFACTS` 退出生产穷举角色）、
F.3 `valid_empty` 的按阶段 required 语义、F.4 阶段快照不可覆盖（generation/摘要命名 +
发布事务的 orphan/incomplete 状态）、F.5 生产 consumer 迁移到 validated read
（主 writer/Realizer/Binder/replay/doctor/quality/summary）。

**PR C 仍缺**：自动重分页（§C.5 拆页并重建 worksets/invocation/预算/阶段快照）——
机制已在上一节记录，当前以 typed failure 早失败代替。

## 2026-09-22 审计 PR F.4 收口：阶段快照不可覆盖 + 证据可验证

复现的审计论断（成立）：`write_resolved_authoring_snapshot` 往**固定文件名**无条件覆盖写，
同一 phase 的第二次运行会抹掉第一次的输入证据；`frozen_snapshot_evidence` 的校验把
"证据文件字节 sha256"与"规范化 JSON 语义摘要"混为一谈，实际上永假（几乎必然报错）。

修复：

- 证据写进带 snapshot 摘要的不可变文件名（`resolved_authoring_snapshot_v1.<phase>.<digest16>.json`）：
  同内容重复写入幂等；同名不同内容 → `stage_snapshot_content_conflict`，拒绝覆盖历史证据。
- 固定文件名降级为**显式指针**：内容仍是完整快照（兼容既有 reader）并额外带
  `evidence_path`；指针与证据的 identity 字段必须一致，否则
  `stage_snapshot_pointer_evidence_mismatch`。
- `frozen_snapshot_evidence` 用读写两端共享的 `_snapshot_digest_payload` **重算**语义摘要，
  再与证据/指针声明比对：篡改（即使指针与证据一起改到"互相自洽"）→
  `stage_snapshot_evidence_changed`；旧格式无证据副本 → `stage_snapshot_evidence_missing`。

测试：`test_artifact_index.py` 新增 3 项（不可变+原子指针、篡改检测、旧格式如实报告），
14 项全绿。

**PR F 仍缺**：F.1 producer 注册制、F.3 `valid_empty` 的按阶段 required 语义、
F.4 发布事务的 orphan/incomplete 显式状态、F.5 生产 consumer 迁移到 validated read。

## 2026-09-22 审计 PR C.4：超限失败只报真实维度

复现的审计论断（成立）：技术页判定已把"段数上限"并入 `candidate_over_budget`，但失败文案
用三元表达式在 request/page 两个 token 不等式中二选一，**段数超限时会打印一个其实并未成立的
input token 不等式**。

修复：新增 `_page_contract_dimension_codes`，只列出真正越界的维度
（`input_tokens` / `request_input_tokens` / `paragraph_count`），三者都不越界时返回空元组，
调用方必须报 `unknown_dimension` 而不是编造；header 页与技术页两条失败路径都改用它。
header 路径现在会一次报出全部被违反的维度（旧实现只报第一个）。

测试：`test_page_contract_recheck.py` 新增 2 项（维度函数单元测试；真实接线：页预算小到单段
都装不下时报 `input_tokens:` 且不得出现 `paragraph_count:`）。16 项全绿；全量离线
3831 passed、3 deselected、12 subtests passed、exit 0。

## 2026-09-22 审计 PR D.1：authoring unit 合并必须无损

复现的审计论断（成立，逐条以 legacy 变体实测）：

- `compile_authoring_units` 的 merge 只拼接 story/slot/surface/argument/intent/unresolved，
  被合并槽位的 **optional detail、formula obligation、formula package 全部静默丢弃**；
- 合并键只有 (kind, role, authority)：**相隔多个槽位**的同键单元会被跨段并回前面的单元
  （A, B, A → [A+C, B]，叙述顺序被改）；
- 同键但 **implementation status / 局部 reader goal 不同**的单元也会被合并；
- 同一 detail ID 承载**不同内容**时静默保留第一个。

修复：

- `can_merge` 收紧：必须**相邻**（`existing_index == len(units) - 1`）、同 section、同
  implementation status、兼容 reader goal（相等或一方为空）、同 ID 同内容；
- 新增 `_merge_units`：surface/detail 按 canonical ID + 内容摘要保序合并（同 ID 不同内容 →
  `*_conflict`，不合并）；required/optional/formula obligation/formula package 保序去重全量保留；
  同一 detail 一侧 required 一侧 optional 时**提升为 required**（不是丢弃）；mechanism_ids 取并集；
- 同形空槽（`structural_only`/`unresolved`，无实现材料）仍可折叠：此时其它局部 reader goal
  记录进新字段 `merged_local_reader_goals` 并出现在 `as_trace()`；
- `as_trace()` 补齐 optional detail / formula obligation / formula package / mechanism / 统一掉的 goal，
  使"合并是否丢东西"可以直接从产物回答。

测试：新增 `tests/regression_20260917/test_authoring_unit_merge.py` 13 项；其中 5 项在
legacy merge 变体下失败（optional 丢弃、跨段合并、status 冲突、同 ID 不同内容、goal 冲突），
在新实现下全绿。

## 2026-09-22 审计 PR D.2：绑定决策进入真实 owner 选择

复现的审计论断（成立）：`_slot_binding_decision` 已存在但**没有任何生产调用**；argument
unit、detail、formula package 三处 owner 选择全部直接调用 `_best_slot`，零 overlap 的
组织落位与"证据完全缺失"混为一谈，也没有 typed gap/replan 记录。

修复：

- 三处 owner 选择改为"先 `_slot_binding_decision`，再 `_slot_for_decision` 落位"；
  `_slot_binding_decision` 内部复用同一个 `_best_slot` 原语（只剩一个选择器）。
- 新增 `binding_decisions` 与 `typed_binding_gaps` trace：每条绑定记录
  `narrative_binding`（grounded / organizational_fallback）与 `evidence_authority`
  两条**分开**的轴；零 overlap 的 required detail / formula package / argument unit
  另记 `reason=no_story_overlap`、`requested_action=bounded_planner_or_research`。
- zero-overlap 的段落权限不得被升级：实测该段落 `authority_surface=author_specification`
  （不是 `repository_statement`），coverage 仍保留 detail。
- optional 材料零 overlap 时单独记 `optional_detail_binding_fallback_ids`，留在候选
  上下文与 trace，不升级为强制 clean prose 义务。

测试：`test_intent_writer_surface.py` 新增 3 项——typed gap + 双轴 + coverage 保留、
optional 不进 gap、以及用 `wraps` 间谍断言**生产路径真的进入** `_slot_binding_decision`
（不是只 import）。

## 2026-09-22 审计 PR D.3：局部指纹与 sealed 模型更新

复现的审计论断（成立）：

- `_story_intent_payload` 不含 `reader_question`，而它会被消费成段落 `reader_goal`；
  只改 reader_question 时意图指纹不变（已用单元测试实测）；
- 更新 surface 的 implementation status 用 `surface.model_copy(update=...)`，绕过 model
  validator，`content_digest` 停在旧内容上（实测：copy digest == 旧 digest，重建后的
  digest 不同），而段落 `surface_digest` 是这些摘要的摘要。

修复：

- `_story_intent_payload` 纳入 `reader_question`；
- 新增 `_surface_with_status`：`model_dump(exclude={"content_digest"}) → 覆盖 status →
  model_validate` 重建验证，替换 `model_copy(update=...)`。

测试：`test_intent_writer_surface.py` 新增 3 项——reader_question 改指纹、重建 digest 与
"同字段重新构造"一致（并记录 model_copy 的旧 digest 反例）、unit 级生产路径必须拿到
重建后的 digest（该测试在 legacy `model_copy` 变体下失败）。13 项全绿；全量离线（含
D.1）3844 passed、3 deselected、12 subtests passed、exit 0。

## 2026-09-22 审计 PR D.4：Writer 可见字段 golden contract 与材料 lineage

复现的审计论断（成立）：`_WRITER_PARAGRAPH_NARRATIVE_FIELDS` 没有段落级
`authority_surface`（也没有 `required_author_surface_ids` / 
`required_repository_proposition_ids`），模型只能看到每条 surface 自己的 authority，
看不到本段整体授权边界；并且没有任何入口能回答"材料是未检索到，还是在投影/合并中丢了"。

修复：

- Writer 段落视图补上 `authority_surface`、`required_author_surface_ids`、
  `required_repository_proposition_ids`（技术事实仍只来自 canonical page，叙述合同里
  不复制 excerpt/atoms/shared_contexts）。
- 新增产品函数 `writer_paragraph_material_lineage(narrative_plan, page_payload)`：
  逐段落列出 required/optional detail 与必读 author surface，区分
  `materialized_detail_ids` 与 `missing_detail_ids`（页已编译却缺材料 = 投影/合并丢失）、
  `missing_author_surface_ids`；已进 `__all__`。这是只读诊断，不改请求内容。

测试：新增 `tests/regression_20260917/test_writer_surface_contract.py` 5 项——两个
compaction 函数的 golden 字段集（含 statement/reader goal/authority/status/supporting
detail/unresolved/disposition 真正到达）、技术材料不得被复制进叙述合同、lineage 能区分
"已物化"与"投影丢失"、surface 压缩保留内容与权限。回归目录 285 项、writer 相关 281 项全绿。

## 2026-09-22 审计 PR E.1/E.2（载荷部分）：canonical 失败归属与可执行修复载荷

复现的审计论断（成立）：

- `writer_repair_packet` 自带第二套 vocabulary（`missing_detail_witness` 等），与
  `publication_transaction_contract.ContractFailureV1.code`（`detail_witness_missing`
  等）不是同一集合，owner 也各写一份；
- 动作选择是 `repair_kind = codes[0]`，只有两个硬编码升级码；
- `as_request_payload` 把 `paragraph_markdown`、`authority_refs`、`allowed_paragraph_ids`
  一并丢掉——模型拿不到修复必需的局部内容（只剩 target id）。

修复：

- `publication_transaction_contract.py` 新增 canonical 表：`CANONICAL_FAILURE_OWNERS`
  （14 个 code → owner）、`CANONICAL_FAILURE_ALLOWED_EDITS`、
  `CANONICAL_FAILURE_OWNER_ACTIONS`、`FAILURE_ACTION_PRIORITY`、
  `LEGACY_FAILURE_CODE_ALIASES`，以及 `canonical_failure_code/owner/escalation` 与
  `select_failure_action`（返回 `FailureActionSelectionV1`）。
- 动作按责任与依赖选择：`ledger_corrupt`/`unknown_failure` → `typed_block`；
  authority/target scope → `replan_required`；formula closure → planner replan/recompile；
  input material → research；atom 绑定 → binder；writer_content 才允许原地改正文；
  transport/unknown-outcome → execution reconcile。空集合也归 `unknown_failure`
  （typed block），不默认改正文。
- `writer_repair_packet` 改为消费 canonical 表：`EscalationV1` 增加 `typed_block`，
  `_ESCALATING_CODES`/`_REPAIRABLE_EDITS` 删除；`contract_failures_from_legacy_strings`
  在**读取边界**输出 canonical code。
- `as_request_payload` 保留修复所需的局部合同（失败段正文、authority refs、允许段落、
  target 原因、escalation），只隐藏内部 `frozen_paragraph_digests`。

测试：`test_repair_packet.py` 扩到 10 项——事故包改用 canonical code、formula closure
升级到 planner、placeholder 缺失才是 Writer 原地修复、未知码 typed block、账本损坏优先于
其它失败、升级类优先于 `codes[0]`、canonical 查表与别名转换。回归目录 260 项、writer 侧
183 项全绿。

**PR E 仍缺**：E.2 的调用边界接线（生产 repair 请求真正消费 packet 与
`as_request_payload`）、E.3 原子提交与单调进展（repair 接受后 scope/冻结段/义务复核）、
E.4 的 `writer_content` vs `final_bound` 负例矩阵、E.5 paragraph objects 单一正文源的
生产路径复核。

## 2026-09-22 审计 PR E.2 接线：生产写侧消费 canonical 归属与局部修复合同

复现的审计论断（成立）：生产写侧自带第二套判定——`section_writer` 维护
`_WRITER_CONTENT_REPAIRABLE_FAILURE_PREFIXES` 前缀表来决定"能不能修"，与
`publication_transaction_contract` 的 code/owner 表平行；生产修复包
（`WriterSectionRepairPacketV1`）也没有 canonical owner/action，也没有"其余已接受段落"
的冻结摘要。

修复：

- `publication_transaction_contract` 增加生产 blocked_reason 的读取边界：
  `BLOCKED_REASON_LANE_DEFAULTS`、`_BLOCKED_REASON_TOKEN_CODES`、
  lane 内语义修正 `_BLOCKED_REASON_LANE_TOKEN_OVERRIDES`、
  `canonical_failure_codes_from_blocked_reason`、`canonical_failure_codes_from_text`、
  `classify_blocked_reason`；新增 canonical code `representation_damage`
  （owner=execution_owner，action=`representation_repair`，escalation=`representation_retry`）
  与 `witness_representation_invalid`（段落 lane 里模型自己写重复 witness 是表示缺陷，
  不是跨段权限问题，不得升级为 replan）。
- 段落 lane 的语义：`formula_consumer_mismatch` → `formula_placeholder_missing`
  （占位符缺失是 Writer 补引用），`invalid_count`/`invalid_witness_count` →
  `detail_semantic_mismatch`，`response_blocked:paragraph_transaction`/`non_substantive`
  → `paragraph_missing`，`duplicate_witness` → `witness_representation_invalid`。
- `section_writer`：删除前缀表，`_is_writer_content_repairable_failure` 改为查表
  （`WRITER_REPAIRABLE_ACTIONS = {writer_content_repair, representation_repair}`，
  即原有四条前缀的行为不变）；新增 `_classify_writer_repair_failure(s)`。
- 生产修复包与请求：`WriterSectionRepairPacketV1` 增加 `canonical_codes/owner/action/
  escalation/failed_paragraph_ids/frozen_paragraph_digests` 与 `as_request_payload()`
  （隐藏内部冻结摘要，保留正文/目标/允许段落等修复必需内容）；调用边界传入
  canonical 结论、失败段落集合（合同优先，section 级失败回退到"失败文本里的计划内
  段落 id"，不放大范围）与冻结的已接受兄弟段落摘要。

测试：`tests/test_llm_section_writer.py` 新增 5 项（可修复矩阵不变、归属结论、
冻结摘要不入请求、失败段落范围、以及用 `wraps` 间谍断言生产调用真的把 canonical
结论交给 packet）；`test_repair_packet.py` 新增 2 项（生产 blocked_reason → canonical
owner/action 全矩阵、可修动作集合恰好两条有界 lane）。回归目录 + writer 侧 393 项、
publication writer 侧 197 项全绿。

## 2026-09-22 审计 PR E.3：有界修复必须验证 scope 与冻结段落

复现的审计论断（成立）：`_merge_publication_repair_response` 只保证"候选没返回的段落落回
incumbent"，**不阻止**候选重写一个本来有效的兄弟段落——修复包虽然已经有冻结摘要，但没有任何
调用点核对它，于是"顺手重写别的段落"会被当成进展提交。

修复：

- 新增 `_publication_paragraph_digests(response)` 与
  `_publication_changed_frozen_paragraph_ids(response, frozen)`：用修复前冻结的字节摘要
  核对合并后的候选，越界段落即拒绝本次尝试（不提交、不算进展），并记入
  `writer_repair_transaction_rejections`（`reason=frozen_sibling_changed`，
  `paragraph_ids=[...]`）与 attempt ledger（`writer_content_repair_rejected:` 前缀）。
- 段落 scope 更准：`_publication_failed_paragraph_ids` 现在还会用
  `formula_packages[].consumer_paragraph_id` 把"只带 placeholder token"的公式失败定位到
  真正的 owner 段落；scope 无法确定时**不冻结**任何段落（此时请求本来就是 section 级，
  谎报"已冻结"比不冻结更危险），修复包里的 `failed_paragraph_ids` 如实为空。

测试：`tests/test_llm_section_writer.py` 新增 3 项——双段落最小反例（修复重写 p2 → 0 commit、
1 no-progress stop、rejection 记录 p2、越界文本不进任何产物、section 仍 incomplete）、
正例（只返回失败段落 → 正常提交且 p2 保持 incumbent 字节）、摘要辅助函数单元测试。
回归目录 + writer 侧 396 项全绿。

## 2026-09-22 审计 PR E.4：两阶段验收负例矩阵（argmax/argmin 缺口）

先用共享 assessor 探了审计点名的 7 个负例，结果是 **6 个已被拒绝、1 个漏过**：

- 加了 target id 但没有对应正文 → 拒（`detail_semantic_mismatch`）
- exact_text 不在段中 → 拒
- 比较方向反转 → 拒（`condition_or_polarity_mismatch`）
- 训练条件被写成无条件行为 → 拒
- 维度/归一化轴错误 → 拒
- 两个相似 operation 串错来源 → 拒
- **argmax 写成 argmin → 漏过**（valid=True）

原因：`_polarity_signature` 只有比较算子（gt/gte/lt/lte）与动作词（selects/excludes）
两根轴，而 argmax→argmin 的动作词完全一致，于是"词汇重叠"替代了关系正确性。

修复：新增极值轴 `_extremum_signature`（词边界正则覆盖 argmax/argmin、maximum/minimum、
highest/lowest、largest/smallest、top-k/bottom-k、ascending/descending），在
`_witness_condition_and_polarity_satisfied` 中"观察到相反极值"即拒绝；方向同时出现
（如 "max minus min"）或词内出现（administered/minibatch）不判定，避免误报。

测试：新增 `tests/regression_20260917/test_witness_relation_matrix.py` 8 项（7 个负例 +
极值签名无误报）。其中 argmax 用例在去掉极值轴后**失败**（legacy 变体实测 valid=True），
加上后全绿；assessor 相关套件 439 项全绿。

## 2026-09-22 审计 PR E.5：生产接收路径使用共享 composer + 消费 prose audit

复现的审计论断（成立）：`normalize_writer_section_payload` / `audit_prose_surface` 只有测试
调用，生产接收路径自带一份拼接逻辑（`"\n\n".join(parts)` + `## heading`），两个正文表面
的规则因此可以各自漂移；audit 的顺序判据只有自然数字序，与"段落顺序以 plan 显式顺序为准"
冲突（事故计划顺序 P10..P17 在 P1__f1/P3..P9 之前）。

修复：

- `audit_prose_surface` 增加顺序权威参数 `plan_paragraph_ids`：给了冻结计划顺序就以它为准
  （`order_reference="frozen_plan_order"`、`order_matches_plan`），没有计划顺序时才退回
  自然数字序并如实标注；`order_matches_narrative_ordinal` 仅作诊断保留。
  `normalize_writer_section_payload` 同步透传。
- 生产两处正文拼接（`_normalize_publication_paragraph_transaction` 的合法/保留分支、
  `_merge_publication_repair_response` 的修复合并）都改为 `_compose_publication_section_markdown`
  → 共享 `compose_section_markdown`，发布字节成为"有序 paragraph 对象的确定性函数"。
- 新增 `_publication_prose_surface_failures`：发布前用共享 audit 复核闭集/顺序/派生物一致性，
  不成立则返回 `prose_surface:*` typed failure 并 fail-closed（不再发布）。

测试：`test_prose_surface.py` 新增 3 项（计划顺序是权威、违反计划顺序被报、归一化载荷携带
按计划顺序的 audit）；`test_llm_section_writer.py` 新增 2 项（fail-closed 辅助函数四类
负例、以及 spy 断言生产归一化真的调用共享 audit 且 `plan_paragraph_ids` 来自冻结计划），
并把两条既有断言升级为"发布字节 == 共享 composer 派生结果"（含修复合并路径）。
回归目录 + writer 侧 402 项全绿。

## 2026-09-22 审计 PR F.3：空产物按阶段 required units 判定

复现的审计论断（成立）：是否允许空产物由调用方一个**共用**的 `allow_empty=True` 决定，
Formalizer（本来就可能没有公式任务）与 Writer（要写正文）用同一条规则；空对象也不记录
"为什么为空、哪些任务 not_applicable"。

修复：

- `authoring_artifact_index` 新增 `PHASE_EMPTY_POLICY`（按 role+phase 区分
  `requires_units` / `allowed_when_no_required_units`）与
  `assess_empty_artifact(role, phase, payload, required_units=...)`，返回
  `EmptyArtifactDispositionV1`（empty/allowed/reason/declared_not_applicable_task_ids/
  failures）；not_applicable 任务既支持 `not_applicable_task_ids` 字段，也支持
  `projection_diagnostics` 里的 `kind=not_applicable` 条目。
- `resolve_artifact` / `read_artifact_validated` 接受 `required_units`：该阶段策略为
  `requires_units` 且冻结单元 >0 时，`valid_empty` 直接 typed block
  （`artifact_empty_with_required_units:<role>:<phase>:<n>`），不再默认放行；读取结果
  额外带 `empty_disposition`，把空的原因与 not_applicable 任务一起交给调用方。
- 生产接线（doctor）：`run_authoring_doctor` 现在对 Formalizer/Writer manifest 与 Writer
  invocation plan 计算空产物处置，把"该阶段需要单元却为空"升级为 critical blocker，
  并在 `render()` 里打印 `EMPTY ARTIFACT` / `CRITICAL` 行；Writer 的 required units 由
  冻结 plan 的段落数推导。

测试：`test_artifact_index.py` 新增 3 项（按阶段+单元判定、空原因与 not_applicable 记录、
reader 在冻结单元下 typed block）；`test_authoring_doctor.py` 新增 2 项（有必需段落时空
manifest 成为 blocker 且可见、无必需单元时合法）。回归目录 278 项、writer 侧 277 项全绿。

## 2026-09-22 审计 PR F.1：producer 发布时向索引注册

复现的审计论断（成立）：索引的"当前生产对象"完全来自 `_KNOWN_ARTIFACTS` 文件名穷举 +
目录扫描；新的一代只有再写一个 `.writer.N` 分支才会被认出来，注册信息（角色/phase/
generation/schema/字节摘要/语义摘要/upstream refs）在整个链路里都不存在。

修复：

- 新增 `authoring_artifact_registry.py`：`ArtifactRegistrationV1`（不可变注册记录，
  文件名带内容摘要、同内容幂等、同名不同内容拒绝）与 `ArtifactRegistryV1`（固定名指针，
  每个 role:phase 指向当前一代）；`register_authoring_artifact(...)` 在产物已落盘后读取
  真实字节，记录 role/phase/generation/相对路径/产物 schema/字节与语义摘要/producer/
  upstream refs，并原子更新指针；路径越界、目标缺失、指针不可读一律 typed error。
- `build_artifact_index` 现在有两条来源：producer 注册（权威）与 legacy 扫描
  （`_KNOWN_ARTIFACTS` 退回为**只读导入规则**）。条目新增 `discovery`
  （`producer_registration` / `legacy_scan`）与 `upstream_refs`；注册指向的内容缺失或
  字节变化 → invalid，且该 key 显式不可解析（**不回退**到扫描出的另一代）；指针损坏 →
  索引里出现 `authoring_artifact_registry:research` 的 invalid 条目（可诊断，不静默忽略）；
  注册路径决定 active，因此新 generation 无需再改表。
- 生产接线：`create_or_validate_execution_identity` 发布身份产物时注册它（producer 名 +
  engine/target/intent/profile/effective_config/validator_bundle 引用）；resume 走
  "校验既有身份"分支，不产生第二条注册。

测试：新增 `test_artifact_registry.py` 8 项（注册身份与摘要、新 generation 无需改表、
注册后字节变化必须 invalid 且不回退、目标缺失、指针损坏可诊断、路径越界拒绝、无注册时
legacy 扫描不变、验证读取）；离线端到端新增 2 项（产品 run 留下 producer 注册且索引以
注册为权威、resume 不重复注册）。回归目录 288 项全绿。

## 2026-09-22 审计 PR F.4 收口：发布事务的 orphan/incomplete 状态

复现的审计论断（成立）：产物写入只有一次 `atomic_write_bytes`（临时文件 + rename），
没有"严格验证"这一步，也没有发布事务记录；一旦在"已落盘但尚未注册/指针未更新"之间中断，
外部只能看到一个**没有任何状态**的文件——无法区分"这次没产出"和"产出到一半"。

修复：

- 新增 `authoring_artifact_publication.py`：`publish_artifact_transaction(...)` 严格按
  §F.4 的顺序执行 `reserved → 临时文件 → 严格验证（JSON 可解析 + 可选 validator）→
  validated → 原子 replace → published → 注册（§F.1）→ registered → complete`，
  每一步写一条**不可变** journal 记录（append-only：5 个状态文件，读最新序号）。
  验证失败 → `incomplete`，目标文件**不创建/不覆盖**，临时文件清理；
  `scan_publication_transactions` / `incomplete_publications` / `scan_orphan_temp_files`
  让未完成发布与残留临时文件可被一条命令发现。
- 生产接线：`create_or_validate_execution_identity` 改用发布事务（validator 要求身份能被
  同一模型读回），失败即 `authoring_execution_identity_publish_incomplete` fail-closed。
- doctor：`AuthoringDoctorReportV1` 增加 `publications` / `orphan_publication_files`，
  未完成发布与 orphan 临时文件都升级为 critical blocker，并在 `render()` 打印
  `PUBLICATION` / `ORPHAN TEMP` 行。

测试：新增 `test_publication_transaction.py` 5 项——成功发布走完五步且无残留临时文件、
验证失败不发布、验证失败不覆盖既有内容、模拟"published 但未注册"中断时索引不把它当 active
且 doctor 报 blocker、orphan 临时文件被报告。回归目录 293 项全绿。

## 2026-09-22 审计 PR F.5（第一片）：doctor 消费已发布索引 + 变异测试

复现的审计论断（成立）：doctor 每次诊断都 `build_artifact_index(root)` **重新扫描**目录，
等于把"索引发布之后被改动的文件"重新认证一遍——所以"发布索引 → 改文件 → reader 必须
在使用前失败"这条要求在诊断路径上根本不成立（实测：改动回执后 doctor 仍按新内容给结论）。

修复：

- 新增 `load_published_artifact_index(out_root)`：读取**已发布**的索引 revision，并用
  规范化载荷**复算**其自身 content_digest（不信任磁盘声明），不一致即
  `artifact_index_digest_changed`。
- doctor 优先消费已发布 revision（报告新增 `artifact_index_source`，render 打印
  `INDEX SOURCE` 行），只有从未发布过索引时才退回临时扫描并如实标注；受索引管理的产物
  （invocation plan、分节回执、阶段回执、空产物处置）统一走 `_validated_payload` →
  `read_artifact_validated`，验证失败时该阶段显示 `blocked (...)`、blocker 升级为 critical，
  **不退回**按文件名再读一份的隐式 fallback。
- quality report 通过 doctor 自动继承同一行为（它不再自己读原始文件拼状态）。

测试（`test_authoring_doctor.py` 新增 2 项，均为变异测试）：索引发布后改动分节回执 →
doctor 报 `artifact_read_blocked:writer_section_receipts:writer:artifact_bytes_changed_since_index`，
注入的 invocation id 不出现在结论里；改动聚合回执 → 该阶段显示 blocked 且不再报
"sections complete"。回归目录 295 项全绿。

**F.5 仍缺**：主 writer / Realizer / Binder / replay / run summary 这些**运行期** reader
仍按 `method_output` 路径直接读文件；把它们迁到 validated read（或按阶段快照读取）需要
在运行内传递索引/快照上下文，留待后续。

## 2026-09-22 审计 PR C.5 收口：admitted 的一代必须冻结阶段快照

复现的审计论断（成立）：重分页会改变实际调用数、重复输入成本、repair lookahead 与 page ID；
代码确实重建了 worksets（`extend_writer_worksets_from_narrative_plan`）、invocation plan
（revision 2 + lookahead realizer plan）、admission（带 request material），但
`write_resolved_authoring_snapshot` 在生产里**没有任何调用者**——"最终 admitted 的一代"
没有冻结输入快照，事后无法证明某次 writer 执行消费的是哪一代 plan/manifest/plan revision。

修复：在 unified writer 通过 admission 之后（即重分页循环结束、plan/admission 已按最终
一代重建），用 `build_artifact_index` + `build_resolved_authoring_snapshot(phase="writer",
required_roles=("narrative_plan:authoring","consumer_workset_manifest:writer",
"consumer_invocation_plan:writer"))` 冻结阶段输入，并用 `write_resolved_authoring_snapshot`
落盘（不可变证据 + 原子指针），路径记入 `paths["resolved_authoring_snapshot_v1.writer"]`。
再次重分页只会追加新的证据文件（§F.4），不会覆盖旧证据。

关于 §C.5 的"预算预留"：writer 阶段没有像 formalizer 那样单独的 phase reservation——
它由 `unified_budget_envelope` + 全 run 累计 `cap` + 逐页 content attempt limit 共同约束，
新 page ID 不会获得额外 token 预算；重分页后的 plan/admission 都要用同一 envelope 重新
评估（本就在 admission 门里）。这一点在记录里如实说明，不假装存在一套独立预留机制。

测试：`test_agentic_publication_method_writer_unified.py` 新增 1 项（真实跑 unified 模式：
快照指针存在、三个 required role 都带字节摘要、证据文件与指针指向同一 snapshot 摘要）。
unified + publication + 回归目录 466 项全绿。

## 2026-09-22 审计 PR G.6：质量比较器的极性修正

复现的审计论断（成立）：`METRIC_POLARITY` 把任务集合/分母（`must_cover_obligations`、
`formula.required`）与受分页策略影响的原始计数（accepted pages / invocations / sends /
tokens）都标成"越少/越多越好"，于是"少一个必需公式""空候选的零 token""提前失败的少调用"
"隐藏 gap"都会显示为改善。

修复（`authoring_quality_comparison.py`）：

- `METRIC_POLARITY` 只保留**无歧义**的缺陷计数与同分母比率；任务集合/分母移入
  `TASK_SET_METRICS`（永远 `unknown`）。
- 新增 `CONDITIONAL_EFFICIENCY_POLARITY`：调用/token/accepted 计数只有在
  "同 scope（冻结目标集一致）+ 有效交付（接受页数不减少）+ 覆盖不退化"时才给方向，
  否则 `unknown` 并在 scope notes 写明原因（空候选与提前失败天然落在这里）。
- 新增 `DENOMINATOR_SENSITIVE` / `DENOMINATOR_GATED_POLARITY`：覆盖率、已解决数、
  formula consumed 只在**同一冻结分母**下才有方向；分母不同只报告集合差异。
- 新增 `COVERAGE_GATED_POLARITY`：`explicit_gaps` 只有覆盖不退化（支持率不降、未解决数不增）
  时才把 gap 减少读成改善。
- `dimensions_not_measured` 现在保留**两侧**原因（`baseline: ... | candidate: ...`），
  后一侧不再覆盖前一侧。

测试：`test_quality_comparison.py` 新增 5 项负例/正例（少必需公式不给方向、空候选零 token
不是效率、覆盖退化时隐藏 gap 不算改善且正例仍为 better、同 scope 效率方向仍生效、两侧未测
原因都保留），并更新既有极性断言以反映"条件表"。比较器 + 报告 22 项全绿。

## 2026-09-22 审计 PR G.1：离线 smoke 的范围声明必须可断言

复现的审计论断（成立）：`test_authoring_end_to_end_offline.py` 名叫"端到端"，但用的是
`provider=NONE` + `write_method_text=False`——它证明的是产品准入/诊断链，而不是写作链；
文档里没说、测试里也没有任何断言能防止它被当成"写作链已验收"。

修复：模块 docstring 明确写成 **product admission / diagnostic smoke**，新增
`TEST_SCOPE` 常量，并新增 `test_offline_run_scope_is_admission_only`：
`page_count == 0`、`accepted_page_count == 0`、Writer 阶段 not produced/blocked、
没有 `repository_verified_method.md`。写作链结论只能来自 §G.2/§G.3。

## 2026-09-22 审计 PR G.4：类型边界在消费前报 contract error

复现的审计论断（部分成立）：叙事计划的形状识别是"猜"的——`_narrative_plan_sections`
把任何不认识的输入（dict 没有 `sections`、list、str、数字）都当成**空计划**，于是错误
类型会在下游变成空 workset / 空证据继续写作（"退化成空证据后继续写作"）。另外三处边界
实测是安全的（Writer input 的 `argument_graph` 类型错 → typed failure；空 mechanism
context → 空 manifest 不抛 `.model_dump`；SimpleNamespace formula package → 正常 splice），
本轮把它们钉成回归。

修复：

- `unified_context_models` 新增 `UNIFIED_NARRATIVE_PLAN_INVALID`；
  `_narrative_plan_sections` 改为显式形状校验：`None` = "没有计划"（legacy 入口，仍返回
  空），带 `sections` 的映射/模型正常读取（显式空列表合法），其它形状一律 typed
  contract error。

测试：`test_page_contract_recheck.py` 新增 5 项（错误形状报 contract error、writer
worksets 拒绝无法识别的计划、Writer input 类型错走 typed failure、空 context 编译成空
manifest、SimpleNamespace 公式包正常 splice）。回归目录 + 编译器套件 336 项全绿。

## 2026-09-22 审计 PR G.2（第一片）：fake-provider 全链 + 发现"空合同 → 真空验收"

新增 `tests/regression_20260922/test_authoring_contract_closure.py`：复用真实产品入口
`run_publication_method_writer`、真实 adapter/assessor/Binder/composer 与真实产物写入，
只把模型/网络边界换成按请求生成合法响应的 fake provider（不返回"全局通过"）。

**复现的真实缺陷**（写场景 3 时发现，比文档描述更严重）：生产 writer 内容验收
`assess_publication_writer_response` 只从 `section.argument_graph["paragraphs"]` 取计划行，
而 V2 page lane 的 section 是空的（页内计划在 `prompt_payload["narrative_plan"]`）——
于是 `plans == ()`，循环体一次都不执行，**任何"段落有正文"的响应都被接受**：实测一个
detail witness 都没有、只声明 atom、还自带 `rendered_detail_ids` 的响应拿到了
`content_acceptance_status=accepted`。同一处还用默认的 `final_bound` 阶段打分，与页面
gate 的"writer_content"意图不一致。

修复（`section_writer.assess_publication_writer_response`）：

- 计划行按"section 合同 → 页内 `narrative_plan.paragraphs`"顺序解析；
- 两者都取不到、但响应确实返回了段落 → 记 `writer_acceptance_plan_missing` 并计入
  invalid_count（fail-closed，不做真空验收）；
- 段落事务打分显式使用 `validation_stage="writer_content"`（Writer 不必枚举
  Binder-owned atom，但 detail/公式/正文义务必须成立）。

新增测试 4 项（均为真实接线）：

1. 首次合法内容 → 真实验收 accepted + 发布文本来自共享 composer；
2. atom-only（丢光 detail witness）→ rejected、聚合回执不计完成、`repository_verified_method`
   为空（Candidate checkpoint 可保留被拒正文供复核，但不得冒充已验证内容）；
3. 模型追加计划外段落 → 拒绝且注入正文永不进入发布产物（composer 不得静默吞掉）；
4. 被拒页面 → 有界 repair（2 次 writer 调用，`build_writer_section_repair_packet` 间谍
   证实生产调用；packet 带 canonical owner/action 与 `failed_paragraph_ids`；请求仍然携带
   同一冻结 page id / 段落集合 / binding contract；内部冻结摘要不进入请求），并留下
   `repair_committed=True` 的可复用接受记录。repair 需要 run 显式声明 retry reserve
   （没有免费重试），测试里如实声明。

writer/publication/回归套件 610 项全绿。

G.2 追加场景 4：默认 fake provider 的正文能过 writer_content，但确定性 Binder 的闭集
不允许它声明的 atom witness（`binder_target_outside_closed_contract:*`），因此
`repository_verified_method` 为空、run 保持 incomplete——"Writer 接受 ≠ publication
acceptance"在真实接线上成立。Writer 聚合回执仍如实报内容阶段完成（§E.4 的两阶段分工），
这一点在测试里明确写成预期，而不是被误当成缺陷。

**G.2 仍缺**：正向 Verified 全链（需要一个"引用页面 atom exact excerpt、不写内部审计词"
的 fake writer，才能让确定性 Binder 真正绑定并过 candidate authority 门）、作者-only
段落路径（场景 5）、Formalizer 无任务（场景 7）、损坏索引下的 writing lane（场景 8）。
G.3 崩溃注入与 G.5 准入加强同样未做。

## 2026-09-22 审计 PR G.2/D（第二片）：内部机制标识符泄漏进正文标题

写正向写作链场景时发现（比 G.2 表格里的任何一条都更靠前）：统一链路的 section 标题
直接取机制显示名——实测 `narrative_plan_v3` 与 `method_section_plan_v2` 的 heading 都是
`Sym:Encoder`，而作者/架构计划的标题本来是干净的 `Encoder`。后果有两个：

1. 读者可见正文标题里出现内部标识符（违反 I1/D 的"内部标识符不得进入正文"）；
2. `validate_candidate_authority` 如实报 `candidate_contains_internal_audit_terms`，
   于是**干净候选路径被自己的内部标识符挡住**（实测 authority status=error）。

修复：`method_architect` 新增 `_reader_facing_section_heading(heading, mechanism_id,
mechanism_name)`：仅当标题被 `heading_is_internal_identifier` 判定为内部标识符时，剥掉
`Sym:`/`mech_sym:` 前缀、按 camelCase/下划线拆词并首字母大写（`Sym:InfoNCE_Loss` →
`Info NCE Loss`），人类标题原样保留；四处 heading 赋值点（V3 主路径的 prior/新 section、
第二处 prior/新 section）全部改用该投影。

实测效果：`narrative_plan_v3`/`method_section_plan_v2` 标题变成 `Encoder`，
`candidate_authority_validation_v1` 从 `error` 变为 **passed**（violations 为空）。
run 仍为 incomplete——那是确定性 Binder 的闭集拒绝了 mock 声明的 atom witness
（`binder_target_outside_closed_contract`），属于两阶段分工的正常结果。

测试：G.2 文件新增 1 项（单元 + 真实接线：标题不是内部标识符、candidate authority 通过）。
writer/publication/回归套件 482 项全绿。

**G.2 仍缺**：正向 Verified 全链需要一个"只声明 detail witness、并把页面 atom 的
exact excerpt 原样写进正文"的 fake writer，让确定性 Binder 真正绑定成功。

## 2026-09-22 审计 PR G.2/E.4（第三片）：Binder 闭集自我否定

写正向写作链场景时发现第二个真实缺陷（比"Binder 缺失/失败"更靠前）：确定性 Binder 的
**闭集**是用 `paragraph_binding_targets(transaction, plan_row=...)` 算出来的，而那个函数
会跳过 transaction 里**已声明/已绑定**的 key（它本来是"Binder 还能绑什么"的输入）。
于是 Binder 一旦按冻结合同绑定 atom，这些 atom 立刻从闭集里消失，随后被
`_reverse_failures` 报成 `binder_target_outside_closed_contract:atom:...`——**按合同做对
的事反而成了违规**，页面永远无法通过 final-bound。

实测证据（修复前）：page plan 的冻结合同有 4 个 required target（1 detail + 3 atom，
atom 的 `allowed_exact_excerpts` 是被授权的源码片段），但 `allowed_target_keys` 只有
`['detail:detail:mech_sym:encoder:1']`，`failure_codes` 是三条
`binder_target_outside_closed_contract:atom:...`。

修复：

- `publication_transaction_contract` 新增并导出 `closed_binding_target_keys(plan_row,
  formula_packages)`：闭集只由**冻结合同**决定（required targets + typed contract atoms +
  formula package 别名），与 transaction 已声明什么无关；
- Binder 的 `allowed_keys` 在该处补上这个闭集（保留原有 allowed_pairs/required_pairs）。

修复后实测：`allowed_target_keys` = detail + 3 atom，`failure_codes` 为空，
`missing_target_keys` 为空，4 个目标全部 witnessed；writer aggregate
`all_required_sections_complete=True`，candidate authority `passed`。

测试：G.2 新增 1 项（单元对比"还能绑什么"与"闭集"的语义差异 + 真实接线：用只声明
detail witness、正文引用 required semantic atom 与被授权源码片段的 contract-faithful
fake writer，断言 Binder 无失败、四目标全见证、聚合完成、authority 通过；同时断言
Verified 仍由原规则决定——本 writer 未渲染 argument unit，candidate/verified 门如实给出
具名原因）。原场景 4 按新事实更新：默认 fake provider 过 writer_content 与 Binder，
但 `publication_ready=False` 且 `verified_blocking_reasons` 具名（`verified_output_empty` 等）。
writer/binder/回归套件 622 项全绿。

**G.2 仍缺**：把 candidate 门也走通（渲染 argument unit、epistemic safety gate、
verified review block）以拿到真正的 Verified 产物；场景 5/7/8 与 G.3/G.5 同样未做。

## 2026-09-22 审计 PR G.2（第四片）：Verified 结论必须由真实反向校验判定

上一片留下的最后一个"看起来像隐藏门槛"的东西查清了：`quality.safety.hard_gate_passed`
为 false 的直接原因是 `final_text_validation_status = "pending"`，而 `pending` 的来源是
`_maybe_validate_final_text` 需要**同时**拿到 `evidence_packets_v3` 与
`method_evidence`（或 `evidence`）——测试夹具只有前者，所以反向校验从未运行，
Verified 就成了"因为没人验"而不是"因为规则拒绝"。

修复（测试夹具 + 断言，不改产品语义）：

- G.2 harness 新增 `with_method_evidence=True`：写一份最小 `MethodEvidence`
  （`project_id/method_name/method_goal/implementation_scope`）并挂到 artifact_paths；
- 新增测试 `test_verified_verdict_is_decided_by_the_real_validator`：断言
  `final_text_validation_status ∈ {passed, failed, error}`（**不允许 pending**），
  candidate 链完整（`writer_transaction_status=success`、聚合回执
  `all_required_sections_complete=True`），然后分支断言：
  * `passed` → `repository_verified_method` 必须有正文；
  * `failed` → 必须具名（`reverse_validation_failed` + `unsupported_positive_claims>0` +
    逐句 `verified_review_block:review-sentence:*`），且 Verified 正文为空。

实测结论：当前 contract-faithful fake writer 的句子尚未逐句 claim 对齐，因此真实反向
校验给出 **failed**（6 个 unsupported positive + FTU2..FTU7 逐句 review block）。这正是
"verified 与否由原规则决定"的证据；下一步只需让 fake provider 的每个句子都落在冻结
claim 上（semantic atom 句与 fenced 源码块目前都不被 claim 覆盖），不需要再动产品代码。

writer/回归套件 485 项全绿。

## 2026-09-22 审计 PR G.2（第五片）：Verified 判定链的具名原因 + Formalizer 阶段独立

1) 把"decided verdict"测试收紧到 claim 级：当真实反向校验给出 failed 时，必须能在
   section_results 里看到逐句原因（`Final claim FAC* reverse validation failed:
   no_semantically_matching_projected_claim; direct_evidence_missing` /
   `direct_evidence_excerpt_empty`）。实测结论：要让 Verified 真的 passed，还差两件事，
   而且都在 fake provider/夹具一侧，不是产品门槛：
   * 每个句子都要落在 projected claim 上（semantic atom 句与 fenced 源码块目前没有）；
   * 冻结证据 span 必须能解析出 excerpt（`direct_evidence_excerpt_empty` 说明夹具的
     span 没有可读的 path/line 信息）。
   为做对照试过的变体记录在案：把 claim 文本与 semantic atom 合成一句会**破坏 detail
   witness**（writer_content 仍接受，但 section 级段落义务判定报
   `paragraph_missing:...:detail:...`），把 claim 当正文、excerpt 当 detail witness 也会
   被 writer_content 拒绝——detail witness 必须由含 semantic atom 的句子承担。

2) 场景 7 的产品层断言：Formalizer 与 Writer 的 manifest 是两个独立阶段对象
   （不同路径、不同 content_digest，按 (role, phase) 分别解析），空合法性按阶段 + 冻结
   单元数判定（Formalizer 允许"没有任务"，Writer 冻结必需单元时不允许空），不允许拿
   Writer manifest 冒充 Formalizer 的；无公式任务时"零 probe"行为由既有单元测试覆盖。

G.2 文件 9 项、回归 + unified 套件全绿。

## 2026-09-22 审计 PR G.3（第一片）：真实持久边界的崩溃注入

新增 `tests/regression_20260922/test_crash_resume_boundaries.py`：先跑一遍真实产品入口得到
真实 run root，再按崩溃点**截断 attempt 事件文件**（started / provider-request /
provider-response / completed / content-acceptance），然后用计数 fake provider 走真正的
resume，断言"零重复发送 + 状态与 ledger 一致 + 不发布未验证正文"。

实测结果（每条都有断言）：

- 崩溃点 2（request 已落盘、结果未知）：reducer = `send_outcome_unknown`
  （primary_cause `request_persisted_without_completed`）；resume **0 次 writer 调用**，
  且恢复后状态**仍是** `send_outcome_unknown`——"未知"不会被当成"未发送"重试。
  （顺带发现：如果为了"别新开 attempt"而干脆不写 started marker，反而会把主因挤成
  `reserved_not_sent`；保持既有 marker 语义才是对的，这一条已回退。）
- 崩溃点 3（response 已落盘、completed 未落盘）：reducer = `response_received_unsettled`；
  resume 0 次调用，状态保持 unsettled（不重复请求同一份正文）。
- 崩溃点 4（completed 已落盘、acceptance 未落盘）：reducer = `validation_pending`；
  resume 0 次调用、不发布任何 verified 正文。
- 崩溃点 6（Writer 已接受、Binder 未跑）：删掉 binder 回执后 resume **0 次 writer 调用**，
  确定性 Binder 被重跑并重新落回执。
- 恢复运行的预算 profile 必须显式声明（复用冻结产物不等于复用环境）——测试里如实声明，
  否则会以 `unified_invocation_budget_missing` 阻断。

**已知缺口（strict xfail 钉住，修好后会自动提醒移除标记）**：崩溃点 4 目前没有"本地结算"
生产者——`publish_validation_replay` 在 reducer 里被消费但**生产侧没有调用者**，于是恢复
既没有结算已落盘的响应，又为一次从未发送的 attempt 写了拒绝 sidecar
（`attempt-0002.content-acceptance.json` + `transaction_metadata_missing`）。
下一步：在页面循环里对 `response_received_unsettled` / `validation_pending` 做本地结算
（解析账本里的 response_text → 同一 assessor → 发布 validation replay，必要时补 completed），
且**不新开 attempt**。

回归 + writer 套件 491 项通过、1 xfailed。

## 2026-09-22 审计 PR G.3（第二片）：本地结算补齐（validation replay 的生产者）

上一片用 strict xfail 钉住的缺口本轮修掉了：崩溃在 "response 已落盘、completed/acceptance
未落盘" 时，恢复既没有结算已落盘的响应，又为一次从未发送的 attempt 写了拒绝 sidecar
（`attempt-0002.content-acceptance.json` + `transaction_metadata_missing`）。

修复：

- `unified_invocation_ledger` 新增公开读取器 `read_recorded_provider_request` /
  `read_recorded_provider_response`：读取已落盘的 provider 诊断记录并**复算自摘要**
  （缺失/损坏返回 None，不静默当成可用）。
- `publication_method_writer` 新增 `_settle_recorded_writer_attempt(...)`：找到"有响应、
  无 acceptance"的最新 attempt → 读回 request/response → 重新解析
  `PublicationMethodSectionOutputV1` → 用**同一个** `assess_publication_writer_response`
  复验 → 把结论发布成不可变 `validation replay`（带 `source_response_digest` 与
  `validator_bundle_digest`）。无法结算时返回 None，由调用方退回原来的 typed failure。
- 页面循环里把 `response_received_unsettled` / `validation_pending` 接到本地结算：
  接受则**不新开 attempt、不发请求**，直接以本地结算的响应继续（记录 `settled_locally`）；
  拒绝则带上真实失败原因；结算不了才报 `response_received_unsettled`。
- 没有 run 身份时（直接调用产品 writer 的测试路径）用
  `capture_validator_bundle_snapshot()` 绑定**当前**验收规则身份，避免 replay 身份留空。

实测（崩溃注入测试全部转正，strict xfail 已移除）：

- 崩溃点 3（response 已落盘）：恢复后 reducer = `accepted_reusable`、`accepted=True`，
  留下 `attempt-0001.validation-replay.*.json`，且**没有任何 attempt-0002 记录**，0 次
  writer 调用；
- 崩溃点 4（completed 已落盘、acceptance 缺失）：同上，`accepted_reusable` + replay，
  0 次调用；
- 崩溃点 2（结果未知）仍然保持 `send_outcome_unknown` 且不重发；
- 崩溃点 6（Writer 已接受、Binder 未跑）仍只重跑确定性 Binder。

回归 + writer 套件 492 项全绿。

## 2026-09-22 审计 PR G.5：offline-ready 与 live-ready 分成两组门

复现的审计论断（成立）：预检只有一个 `ready`，且部署探测缺失时只是 warning——"离线全链
通过"与"当前服务可用"混在同一个结论里；离线回执也只绑定引擎指纹，validator/有效配置/
**必测集合**变化后旧回执照样算通过（§14.4 明确禁止"某条命令有 1 passed 就算跑完"）。

修复：

- `OfflineSuiteReceiptV1` 增加 `validator_bundle_digest` / `effective_config_digest` /
  `test_plan_ids` / `test_plan_digest` / `output_digest`；`matches(...)` 同时核对引擎、
  规则、有效配置与**必测集合**（`REQUIRED_OFFLINE_TEST_PLAN`：两个审计回归目录 +
  unified writer + section writer）。`build_offline_suite_receipt` 默认绑定当前
  validator bundle 身份与原始输出摘要。
- 预检新增 scope：`LiveAdmissionGateV1.scope`（offline/live）、报告新增
  `live_ready` / `readiness_scope` / `live_blockers` / `scope_note`（明说"offline-ready
  不证明当前服务可用"），`render()` 打印 `READINESS SCOPE` 与 `LIVE BLOCKER`。
  live 专属门：部署探测（health + 服务模型身份）、`role_call_budgets`、
  `output_limits`、`stop_conditions`（四角色预算/输出上限必须为正，停止条件必须显式声明）；
  这些门不阻断 offline-ready。
- 回执门细分：`offline_suite_test_plan_incomplete:<ids>`（声明了集合但没覆盖必测集合）、
  `offline_suite_receipt_stale`（引擎/规则身份变化）、旧格式回执（完全没绑定规则/测试集合）
  在 offline 只警告，在 live 记为 `offline_suite_receipt_identities_unbound`。
- CLI：新增 `--require-live-ready`；退出码区分 0=live-ready、3=不可进入、
  4=仅 offline-ready（未加该 flag 时仍返回 0，保持既有脚本兼容）。

测试：`test_live_admission.py` 新增 4 项（offline≠live 的四类 live blocker 与 scope 标注、
补齐 live 声明后 `live_ready=True` 且 policy 记录预算/停止条件、回执的规则与必测集合绑定
三类判定、CLI 退出码 0/4 与 scope 行）。回归目录 18 项 live 准入测试 + 两套审计回归全绿。

## 2026-09-22 审计 PR G.2（第六片）：场景 5 与场景 8

场景 5（只有作者说明、无 implementation atom）：用 `author_story_spine_v1` 注入一个
"只有作者说明、无 claim/obligation"的 story，并在 v4 intent 模式下跑真实产品入口。实测
计划里出现 `MA-S1:P1`（`paragraph_kind=unresolved`、`required_detail_ids=()`、
witness targets 为 0）与 `MA-S1:P2`（grounded，4 个 target）——作者-only 段落保留在计划里、
**不要求任何实现义务**，到达 Writer 的页合同同样没有 required detail/target（不伪造实现证明），
整条链路也没有出现空 context 的 `.model_dump` 崩溃。

场景 8（消费文件被改动）：baseline 之后改动真正的输入产物 `code_facts_v1`
（archive/plan 都由它派生），resume 必须在使用前失败——实测抛
`unified_consumer_request_rejected:...:unified_plan_corrupt:...`（注册的冻结计划与重建
内容不一致），且不发布任何已验证正文。测试断言 typed 失败 + verified 为空，杜绝"依赖缓存
摘要继续跑"。

G.2 文件 11 项全绿；回归 + unified 套件 350 项通过。

## 2026-09-22 审计 PR F.5（第二片）：run summary 的发布注册与验证读取

复现的审计论断（成立）：`artifacts/research_product/run_summary.json` 是索引里的
`run_summary:terminal` 产物，但产品入口只用 `_atomic_write_text` 写它（无验证、无注册），
也没有任何 reader 在使用前核对字节——索引里那份摘要与实际内容可以各自漂移。

修复：

- 产品 finalize 改为走 §F.4 journaled 事务发布 run summary（role=run_summary,
  phase=terminal, generation=1, producer=autonomous_method_agent.finalize,
  upstream refs=run/repo），失败即 `run_summary_publish_incomplete` fail-closed；
  注册由事务内的 §F.1 步骤完成。
- 新增 `authoring_doctor.load_run_summary_validated(out_root)`：优先读**已发布**索引
  revision（否则临时扫描），经 `read_artifact_validated` 验证字节与语义摘要后返回
  payload；验证失败返回 typed blocker 且 payload 为 None，**不退回**按文件名再读一份。

测试（真实产品 run）：summary 出现在 registry 的 active 注册里、journal 状态为 complete、
索引与当前字节一致时可读且 `run_id` 正确；发布索引后改动 summary →
`artifact_read_blocked:run_summary:terminal:artifact_bytes_changed_since_index:...` 且不返回内容。
另修正既有 resume 断言：身份注册不得新增（保持原意），而 summary 每次 finalize 都是新内容 →
新的不可变注册记录、指针前移属于预期。

回归 + unified 套件 351 项通过。

## 2026-09-22 审计 PR F.5（第三片）：重放入口验证受索引管理的输入

复现的审计论断（成立）：`scripts/run_authoring_replay.py` 完全不使用产物索引——26 处
`_read_json_mapping` 都按文件名直接读，包括身份、调用计划、回执这些**受索引管理**的产物，
"改动消费文件后使用前失败"在重放路径上不成立。

修复（区分"受管理"与"具名 legacy"两类读取）：

- 新增 `INDEX_MANAGED_REPLAY_INPUTS`（身份/legacy 身份/叙事计划/两代 workset manifest/
  调用计划/分节回执/聚合回执/run summary）与
  `verify_index_managed_replay_inputs(frozen)`：优先已发布索引 revision（否则临时扫描），
  逐个 `read_artifact_validated`；只验证**存在**的产物（没产出不算阻断），存在却验证失败 →
  `artifact_read_blocked:<role>:<phase>:...`。
- `_replay` 在"复制/使用冻结产物之前"调用该 gate：blocker 非空即 `terminal_reason =
  artifact_read_blocked:...`、`error_code=artifact_read_blocked`、退出码 2，并在 telemetry
  记录 `index_verified_inputs` / `index_blocked_inputs`。
- 其余私有 scratch 读取保持按名读取，但在 telemetry 里用
  `legacy_unverified_reads`（`LEGACY_UNVERIFIED_READ_NOTE`）**具名标注**未验证范围——
  这正是 §F.5 允许的"仅历史归档读取可用有名称的 legacy resolver，并在报告里标注"。

测试：真实产品 run + 发布索引 → 验证通过（身份/legacy 身份/run summary 在列）；
发布索引后改动 run summary → `run_summary:terminal` 不再通过且 blocker 含
`artifact_bytes_changed_since_index`；空目录不算阻断。回归 + 重放相关套件 375 项通过。

## 2026-09-22 审计 §4：I1–I10 不变量核对（可执行）

新增 `tests/regression_20260922/test_invariants_i1_i10.py`：每个不变量一条最小断言，并在
docstring 里写明**负责边界**（不新增门禁，只钉住已有 owner 的行为）：

| 不变量 | 核对方式 |
|---|---|
| I1 | 产品级：作者-only story（v4 计划）→ 段落 `required_detail_ids=()`、witness targets 为空，且其页 `page_kind=header`、technical payload 无 atom/detail（作者意图不能证明实现） |
| I2 | `normalize_narrative_plan_mode`：未知值抛 `unknown_narrative_plan_mode`，空值走显式默认 v3（不静默换主线） |
| I3 | 产品级：`narrative_plan_v3` 里每个 required detail 恰好一个 owner 段落；页合同 required 集合无重复 |
| I4 | 产品级：每页 atom ⊆ archive 闭包；workset 的 required atom 为集合语义（跨页共享不重复计成果） |
| I5 | `compare_actual_request_to_page_contract`：重排/改序被拒（`ACTUAL_PAGE_CONTRACT_MISMATCH`）；实际发送的 `max_output_tokens` 超过冻结值 → `output_cap` |
| I6 | 产品级：Writer 内容阶段 accepted、`writer_transaction_status=success`，但 `publication_ready=False`、`verified_blocking_reasons` 非空、verified 正文为空；同时证明闭集含 atom 义务而 writer_content 阶段不要求 Writer 枚举 |
| I7 | transport policy：`unknown_outcome_retries<=0`、计入调用预算；`transport_failure_failure_code(sent=True)` 以 `send_outcome_unknown` 开头，`sent=False` 则不是 |
| I8 | `publish_validation_replay` 拒绝覆盖历史 `content-acceptance`（`validation_replay_refuses_to_shadow_historical_acceptance`），历史文件保持原结论 |
| I9 | 显式 `reference_digests` 无命中 → `ArtifactIndexError` 且 `active` 里没有该 key（不猜最新文件） |
| I10 | 质量对照：删任务（`formula.required=0`）与空候选（0 token / 0 页）方向均为 `unknown`；段数上限关闭时 `experiment_acknowledged=False`（准入据此阻断） |

两条回归目录 340 项通过。

## 2026-09-22 审计 §13：A01–G06 矩阵覆盖映射（可核对）

新增 `tests/regression_20260922/test_matrix_coverage.py`：42 条矩阵行（A01–A08、B01–B08、
C01–C07、D01–D06、E01–E06、F01–F06、G01–G06）各指向仓库里**真实存在**的测试节点，并由测试
自身保证映射不腐烂：

- `test_every_matrix_row_is_mapped`：行集合必须与 §13 完全一致（缺行/多行都失败）；
- `test_every_mapped_evidence_exists`：每个节点必须存在（文件 + `def <name>(`），改名/删除即失败；
- `test_matrix_row_declares_what_it_asserts`：每行至少一条证据且不重复凑数。

映射要点（证据 = 审计点名的最小反例，尽量一一对应）：

- A01–A08 → `test_execution_identity.py` / `test_run_identity_content.py`（dirty 内容变化、
  目标内容身份与路径无关、fork birth 保持、导入依赖缺失/被改、validator 不可用、双 opener
  锁、lease 异常释放）；
- B01–B08 → `test_ledger_recovery_matrix.py` / `test_transport_policy.py` / 崩溃注入
  （预算耗尽、pre-send 拒绝不扣内容预算、request-only=unknown、response-only 本地结算、
  completed 无 response=inconsistent、acceptance 损坏=typed block、旧失败不覆盖新接受、
  retry 尊重 run 预算且 unknown 不重试）；
- C01/C02 → 审计点名的 7 个 atom-free 段落与"1 技术 + 15 叙事"事故形状测试；
  C03–C07 → 输出估量/闭包/重分页 typed failure/adapter 追加段落/提高 output cap；
- D01–D06 → merge 守恒、同 ID 异内容冲突、reader_question 与 surface digest 自洽、
  零 overlap 不伪造 grounded、typed gap 不塞第一段；
- E01–E06 → repair packet 的 canonical 路由、planner 而非 prose、有界 repair 提交、
  final-bound 仍需 atom、双 surface 以段落为准、未知 code = typed block；
- F01–F06 → 索引后改动被检测、显式 digest 无命中不回退、非法 JSON/schema 不 active、
  新 generation 不靠固定后缀、快照不可覆盖、阶段语义（Formalizer 空 vs Writer 必需）；
- G01–G06 → 假 provider 全链、局部 repair 全链、崩溃注入矩阵、空候选/删任务/隐藏失败
  均不得标为改善。

注意：本映射证明"每行有对应证据且证据存在"，证据本身的通过由完整离线套件保证
（本轮 3952+49 项全绿）。两条回归目录 389 项通过。

## 2026-09-22 审计 §16：完成定义自评（含禁止性验收逐条自查）

### §16.1 代码修复完成

| 要求 | 证据 | 结论 |
|---|---|---|
| A–F 关键反例通过 | §13 矩阵 42 行全部有证据（`test_matrix_coverage.py` 自检），逐条最小反例在各自 PR 记录里 | ✅ |
| 修改点不是孤立 helper | 每个切片都有产品入口行为测试：离线 e2e（run summary/registry/journal）、unified writer 真实运行（G.1/G.2/G.4/G.6）、崩溃注入（G.3）、replay 入口（F.5）、CLI（G.5 scope/退出码） | ✅ |
| 生产调用路径有行为测试 | `publish_artifact_transaction` 在 finalize/identity 真实调用；`closed_binding_target_keys` 在 Binder 真实调用；`_settle_recorded_writer_attempt` 在页面循环真实调用；`verify_index_managed_replay_inputs` 在 `_replay` 真实调用 | ✅ |
| 已有离线测试无意外退化 | 本轮 `python -m pytest -q -m 'not live_llm'` = **4001 passed / 3 deselected / 12 subtests / exit 0**；另 `record-offline-receipt` 重新生成（绑定当前 engine+validator+必测集合） | ✅ |
| 新 schema/身份语义迁移清楚 | 身份 `schema_version="2.0"` 为 `Literal`；旧 `run_identity_v1.json` 不被改写（模块 docstring 明示 I8）；legacy 身份 → `RESUME_IDENTITY_LEGACY` + `allowed_next_action=explicit_fork_authoring`（`test_legacy_identity_cannot_be_strictly_resumed`） | ✅ |
| 旧归档字节保持不变 | 自冻结基线 `3aa9db8d` 起 85 个提交共 158 个改动路径，**全部**落在 `src/`(61)、`tests/`(54)、`.agent/`(40)、`scripts/`(3)；无任何 `artifacts/`、归档或文档文件被改动；工作树既有脏改动（docs/README.md、paperbanana_single_shot、未跟踪 docs/artifacts）原样保留 | ✅ |

### §16.2 恢复机制完成

崩溃矩阵（G.3 六个落盘点）、预算与 ledger 口径一致（`test_all_readers_agree_on_the_same_conclusion`）、
未知发送不重复调用（`send_outcome_unknown` 保持且 0 次调用）、已收到响应本地继续
（validation replay 生产者，`accepted_reusable`）、fork 按相同 birth metadata 恢复
（`test_fork_authoring_can_resume_without_changing_birth_metadata`）、所有入口同一主因
（reducer 单一结论 + doctor 一致）——均 ✅。

### §16.3 质量改善得到证据

**未完成，且按本轮授权范围无法完成**：L1/L2/L3 的实际 scope/结果需要**授权的 live 运行**
（目标明确写"不做未授权 live"），可发表性需要指定盲评/人工核对。当前只有 offline-ready
证据（G.5 已把 offline-ready 与 live-ready 分成两组门并给出 live 阻断清单：
部署探测、四角色预算、输出上限、停止条件）。因此**不宣称质量改善已完成**。

### §16.4 禁止性验收逐条自查

| 禁止项 | 自查 |
|---|---|
| 只有新增模块和单元测试，没有生产接线 | 不适用：每个 PR 都有产品入口测试（见 §16.1 表） |
| 只有 pytest 总数，没有测试范围/engine 绑定 | 不适用：离线回执绑定 engine digest + validator bundle + 必测集合 + 原始输出摘要 |
| 只有 provider=NONE + write_method_text=False 的 smoke | 不适用：G.1/G.2 走真实 writer→binder→composition→发布边界（fake provider，真实链路） |
| 只有 prepare 产物，没有 Writer/Binder/正文交付 | **部分适用**：candidate 已完整（writer_content accepted + Binder 全目标见证 + 聚合完成），Verified 正文仍为空——原因是夹具证据 span 无 excerpt 且句子未逐句 claim 对齐（已具名记录），不是产品门缺失 |
| 只看到"6 段上限"，没有核对真实 request 中的全部段落 | 不适用：C02 核对**实际请求**段落集合/顺序与冻结契约 |
| 只看到 index 存在，没有复核消费字节和 upstream | 不适用：F.5 的 validated read + 改动检测（doctor/summary/replay 三处） |
| 只看到 accepted=true，没有对应 request/response/validator 绑定 | 不适用：acceptance sidecar 带 request/response digest 与 validator bundle；I6 证明 accepted ≠ published |
| 只看到更少 tokens，没有同任务集合与有效交付条件 | 不适用：G.4/G.5 要求任务集合一致且覆盖不退化 |
| 只在删除旧 ledger 后成功 | 不适用：崩溃注入只**截断到崩溃点**以构造现场，恢复过程不删账本（replay 亦为 append-only） |

### 结论

F01–F12 的代码修复与离线可验证部分（PR A–G、§4 不变量、§13 矩阵、§16.1/§16.2）已完成并有
可复算证据；**§16.3（live 质量改善证据）因未获授权而保持未完成**，这是目标本身划定的边界，
不是遗漏。

### §14.4 离线回执重新生成（本轮）

用真实命令重新生成 live 准入回执（不是声明值）：

```
python -c "from code2paper.cli.agentic_run import method_agent_main; ..."
  → method_agent_main(['record-offline-receipt', '--out',
     'artifacts/runs/2026-09-18-live-admission/offline-receipt.json'])
```

结果：`passed=True exit=0 passed_count=4001 failed=0 deselected=3`，并绑定当前
engine commit/source digest、`validator_bundle_digest`、必测集合（4/4）与原始输出摘要。
随后用 `live-admission` 预检复核：回执门 `PASS ... identities_bound=True test_plan=4/4`，
报告为 `READINESS SCOPE offline_ready`，live 阻断项如实列出（部署探测、四角色预算、
输出上限、停止条件）。该目录其余 BLOCKER（author materials/budget/run_open）来自它本身
是旧目录且未提供材料，与回执无关。

**操作注意**：回执同时绑定 `engine_commit_sha`，因此**任何新提交都会让它失效**；最后一次
提交之后必须重新生成（本轮已在最后一次提交后重跑）。

## 2026-09-22 审计 §3：F01–F12 收口核对（代码 owner + 生产接线 + 证据）

| 缺陷 | 代码 owner（修复点） | 生产接线 | 证据 |
|---|---|---|---|
| F01 分页未覆盖最终 Writer 合同 | `unified_context_compiler`（所有可写段落进同一候选页构建器、`assert_page_paragraph_set_within_limit`、`compare_actual_request_to_page_contract` 发送前复核） | 主 writer 的 page adapter + pre-send | `test_narrative_only_section_is_paged_by_the_candidate_contract`（7 段 vs 上限 6）、`test_final_page_paragraph_set_is_checked_against_the_limit`（1 技术+15 叙事）、`test_adapter_appending_paragraphs_is_rejected` |
| F02 目标内容身份漏变更 | `capture_target_identity` 改为内容快照（commit/porcelain 仅诊断） | `build_run_open_identity` + 预检 | `test_target_dirty_content_change_invalidates_resume`、`test_same_target_content_in_another_path_has_same_content_identity`、`test_target_identity_carries_content_not_commit` |
| F03 fork 恢复与锁内二次准入 | `autonomous_method_agent.open_authoring_execution`：预检 → **取锁 → 锁内重新解析身份 + `validate_run_open`** → bind → 建/校身份，异常释放锁；fork 分支保留 birth/导入摘要 | 产品入口 | `test_two_new_openers_cannot_both_admit_same_root`、`test_run_lease_released_on_success_and_exception`、`test_lease_is_exclusive_across_processes`、`test_fork_authoring_can_resume_without_changing_birth_metadata` |
| F04 账本四口径不一致 | 单一 reducer `reduce_invocation_recovery`（8 状态 + typed blocks），doctor/CLI/发送包装器只消费同一结论 | 主 writer 页面循环、doctor、replay | `test_ledger_recovery_matrix.py`（19 项：两次真实失败、只有 started/request/response、completed 缺 response、损坏 acceptance、旧拒发后合法接受、超时未知）、`test_all_readers_agree_on_the_same_conclusion` |
| F05 索引不验证冻结字节 | `authoring_artifact_index`：字节 digest 复算、显式 digest 零命中不回退、非法 JSON/不支持 schema 不 active、generation 显式消歧、阶段快照不可覆盖；`authoring_artifact_registry` + `authoring_artifact_publication` | doctor/summary/replay/doctor 读取路径 | `test_artifact_index.py`(17)、`test_artifact_registry.py`(8)、`test_publication_transaction.py`(5)、`test_authoring_doctor.py`(8) |
| F06 合并丢信息 + 绑定决策未接线 | `intent_narrative_compiler._merge_units`（optional details/formula/reader goal 守恒、冲突拒绝）；`_slot_binding_decision` 驱动 `_slot_for_decision` | `compile_authoring_units` → narrative 计划 | `test_authoring_unit_merge.py`(12)、`test_production_path_calls_the_binding_decision` |
| F07 语义摘要/权限/输入消费守恒 | `_story_intent_payload` 纳入 `reader_question`；`_surface_with_status` 重建 surface 并让 digest 自洽 | 意图摘要 → 页身份/复用 | `test_reader_question_changes_the_intent_digest`、`test_surface_status_update_rebuilds_the_sealed_digest`、`test_paragraph_surface_digest_follows_the_rebuilt_surface` |
| F08 失败码不统一 | `publication_transaction_contract` canonical 表 + legacy 别名 + owner/action/escalation；未知 code → typed block；`input_material_missing` → Research/Planner | repair packet 构造 + 主 writer 路由 | `test_repair_packet.py`(12)、`test_canonical_action_selection_table`、`test_unknown_failure_code_is_a_typed_block` |
| F09 输出估量未覆盖真实结构 | `writer_output_workload`：witness 出现次数独立计费、公式不重复计、未知预算 fail-closed、calibrated profile 需证据 | 分页与页准入 | `test_output_feasibility.py`(13)、`test_writer_witness_occurrences_are_charged_to_the_estimate`、`test_unknown_output_budget_is_fail_closed` |
| F10 单正文未进出版物 | `section_writer._normalize_publication_paragraph_transaction` → `_compose_publication_section_markdown` + `_publication_prose_surface_failures`（**委托** `paragraph_prose_composer.audit_prose_surface`，顺序取冻结计划 `expected_ids`），失败即 transaction incomplete | 真实 Writer 页解析路径（5425 行） | `test_prose_surface.py`(9)、`test_writer_surface_contract.py`(5)、`test_frozen_plan_order_is_the_order_authority`、`test_plan_order_violation_is_reported` |
| F11 离线准入/端到端证明范围不足 | G.1/G.2 假 provider 真实链路；`live_admission_preflight` 分 offline-ready/live-ready 两组门 + 回执绑定规则/必测集合 | 产品入口 + CLI | `test_authoring_contract_closure.py`(11)、`test_live_admission.py`(18) |
| F12 质量比较方向奖励错误行为 | `authoring_quality_comparison`：默认 direction=unknown、覆盖/分母/任务集合门控、both-sides not-measured | 质量对照 CLI/报告 | `test_quality_comparison.py`(14) |

约束复核（本轮实测）：`git diff --check` 干净；段数上限仍为默认 **6**（`source=default, disabled=False`，
未提高也未关闭）；自冻结基线以来**没有任何** ledger/回执/产物文件被删除；未执行任何 live。

## 2026-09-23 复核发现的缺口修复（C.6 上限复核接线 / F.5 索引回退 / C.05 证据强度）

复核在 `315aff7` 上复现了三处问题，本轮逐一修复并给出修复前/后证据。

### 1) §C.6 输出上限复核接线错误（真实缺陷）

旧代码：`actual_max_output = getattr(getattr(request, "config", None), "max_output_tokens", 0)`
——`LLMRequest` 是 dataclass，没有 `config` 字段；而真实 unified 页 payload 也不携带
`config`，于是 `page_contract_snapshot_from_payload` 冻结到 0。实测：`compare_actual_request_to_page_contract`
收到 `(frozen=0, actual=0)`，上限复核完全失效。

修复：

- `page_contract_recheck` 新增 `resolve_frozen_page_output_cap(snapshot, invocation)`
  （payload 声明优先，否则用**调用计划冻结的每页预算**）与 `page_output_cap_failures(...)`
  （实际值未知而冻结值 >0 → `unified_actual_output_cap_unknown` fail-closed；实际 > 冻结 →
  `unified_actual_request_page_contract_mismatch:output_cap:<actual>><frozen>`）。
- 页面循环：冻结上限解析后写回缓存快照；实际上限改为读取**本次调用真正使用的 config**
  （`_capturing_writer_caller(config, request)` 的 `config`，即 `_apply_writer_context_clamp`
  之后的 `call_config`），并追加 `page_output_cap_failures` 结果。

证据：新增 `test_writer_page_output_cap_comparison_uses_real_values`（spy 真实页循环）。
**修复前实测 `[(0, 0)]` 失败**；修复后冻结值等于计划预算（8192）、实际值非 0 且不高于冻结值。
另加 `test_page_output_cap_failures_are_fail_closed` 覆盖三种判定。

### 2) §F.5 已发布索引损坏被隐式回退绕过（真实缺陷）

旧代码在 `load_published_artifact_index` 抛错时一律 `build_artifact_index` 重扫：索引自身
摘要被破坏后，重扫会把**已经改动过的回执**重新认证一遍，原本的拒绝消失。

修复：`authoring_artifact_index.load_index_for_reading(out_root) -> (index, source)`——
只有 `artifact_index_missing` 才允许 `fresh_scan`；已发布但不可用（不可读/自身摘要变化/
schema 不支持）直接抛错。三个 reader 全部改为不回退：

- `scripts/run_authoring_replay.py::verify_index_managed_replay_inputs` → 返回
  `artifact_index_unusable:<err>` blocker，重放在使用前拒绝；
- `authoring_doctor.load_run_summary_validated` → 返回 `(None, artifact_index_unusable:...)`；
- `run_authoring_doctor` → `artifact_index_source = unusable...` 并记入 `critical_blockers`。

证据：`test_replay_refuses_when_the_published_index_is_unusable`（发布索引 → 改动 summary →
拒绝；再破坏索引摘要 → **仍然拒绝**）。**修复前实测失败**（重扫后把改动过的产物重新列为
verified），修复后 `artifact_index_unusable:artifact_index_digest_changed`；
`test_doctor_fails_closed_when_the_published_index_is_unusable` 覆盖 doctor 两个入口。

### 3) §C.05 映射证据过弱

原 C05 只断言失败码转换函数。新增
`test_repage_budget_insufficiency_blocks_without_truncating_obligations`：走真实准入评估器
`evaluate_unified_live_admission_v1`，用 `plan_revision=2` + 压到不足的
`max_total_input_tokens`，断言同时出现 `unified_invocation_budget_exceeded:total_input_tokens:...`
与 `run_budget_insufficient_after_repage:total_input_tokens:...`、准入不通过、且 manifest 的
义务集合**原样保留**（拒绝发送而非截尾）；对照组（`plan_revision=1`）不得冒充"拆页后不足"。
矩阵映射已把该测试置于 C05 首位。

本轮相关套件：`tests/regression_20260917` + `tests/regression_20260922` 394 项、
writer/compiler/section-writer 330 项全绿；全程未调用真实模型。

## 2026-09-27 复核复现的三个 C.6–C.7 缺口（62782ad 上仍到达假 provider 边界）

复核指出：上限**降低**未阻断、**空**公式白名单可被扩充、作者目标（reader_goal）改写未检出。
三处都在发送前复核这一层，逐条修复并给出修复前/后证据。

### 1) 上限必须**等于**估量使用的上限（降低同样阻断）

`compare_actual_request_to_page_contract` 原来只拒绝 `actual > frozen`；`page_output_cap_failures`
同样只判"提高"。审计 §C.6 要求"实际输出上限 == 本页估量使用的上限"，§C.7 明确
"实际 provider 输出 cap 降低 → 重编译/阻断，不能沿用旧页"。

修复：两处都改为**相等**判定，失败码统一为
`actual_page_contract_mismatch:output_cap:<actual>!=<frozen>`（冻结值 >0 而实际值未知时仍是
`unified_actual_output_cap_unknown`）。

### 2) 空 scope 也是契约

`compare_actual_request_to_page_contract` 的 scope 循环里有 `if not expected: continue`，
于是冻结为**空**的 `allowed_formula_package_ids` 被整段跳过，repair 往里塞未授权公式包
不会被发现。

修复：逐项比较**所有**冻结 scope 键（缺失视为空），失败码带上数量：
`...:scope:allowed_formula_package_ids:expected=0:actual=1`；并新增整体
`binding_contract` 摘要比较（仅当 scope 逐项未报错时，避免同一改动两种表述）。

### 3) 作者 surface 必须被冻结并比较

快照此前只冻结段落 ID/scope/上限，`reader_goal`/`role`/`transition_*`/`rhetorical_goal`
完全没进契约，repair 改写作者目标不会被发现。

修复：`PageContractSnapshotV1` 新增 `author_surface_digest` / `binding_contract_digest` /
`technical_bytes_digest`；`author_surface_projection(payload)` 提取作者 surface（顺序敏感），
比较时重算摘要并要求相等 → `...:author_surface`。编排层在 payload 未声明技术摘要时用
`page.technical_bytes_digest` 注入冻结值（`...:technical_bytes` 比较）。

### 证据（修复前复现 → 修复后通过）

- `test_any_output_cap_change_is_rejected`：提高与**降低到 1** 都被拒（修复前降低不报错）。
- `test_expanding_an_empty_formula_whitelist_is_rejected_before_send`：**修复前失败**。
- `test_lowered_author_goal_is_rejected_before_send`：reader_goal 与 rhetorical_goal 改写
  都被拒（**修复前失败**）；`test_repair_cannot_change_author_material_without_replanning`
  证明 `is_repair=True` 不豁免。
- 产品级 `test_lowered_writer_output_cap_is_refused_before_the_provider`：把
  `_apply_writer_context_clamp` 改成"悄悄降到 4096"（事故形态），断言 Writer 页请求
  **0 次到达 caller**、acceptance sidecar 里具名
  `unified_actual_request_rejected:actual_page_contract_mismatch:output_cap:4096!=8192`、
  `publication_ready=False`（**修复前实测请求确实发出**）。
- 生产接线 spy 测试同时断言冻结快照确实带 `author_surface_digest` / `binding_contract_digest`。

矩阵映射同步加强（C06 加入作者目标与空白名单两条，C07 加入产品级降低上限一条）；
本轮相关套件：两条回归目录 399 项 + writer/compiler 330 项全绿；全程未调用真实模型。

## 2026-09-27 审计 §C.04：多 detail 公式的跨页依赖闭包（补齐验收证据）

复核指出 C04 的映射只指向"公式成本去重"和"公式对象拼接"，不足以证明跨页依赖闭包。本轮
补**实际分页行为测试**（`tests/regression_20260917/test_formula_dependency_closure.py`），
用真实编译器 `build_unified_context_archive_v2` → `build_consumer_workset_manifest_v2`
驱动一个"一个机制 + 两个 detail + 一个依赖两个 detail 的公式义务"的夹具：

1. `test_multi_detail_formula_keeps_its_closure_on_one_page`：多 detail 公式**恰好**落在一页，
   该页携带**全部** source detail atom（`detail:d:one`、`detail:d:two`），且分页后义务集合
   守恒（每个义务只出现一次）。
2. `test_multi_detail_formula_closure_survives_a_tight_page_budget`：预算压到必须单独成页时，
   闭包仍完整（独占一页 + 两个 detail 都在），archive 里的 detail atom 一个不少。
3. `test_indivisible_over_budget_formula_is_blocked_not_truncated`：预算低于该不可分单元自身
   估算时 **typed failure**，报出真实限制维度与贡献 atom（`unified_atomic_page_over_budget:
   obligation:ob:multi:<tokens>><budget>` + `contribution:...`），且不截尾（detail atom 与
   义务集合原样保留）。

顺带把失败码做成机器可读：`build_consumer_workset_manifest_v2` 在**全部**阻断原因都是
"不可分单元超预算"时，失败码直接报 `unified_atomic_page_over_budget`（否则仍是
`unified_page_projection_incomplete` umbrella）。这是审计"返回说明真实限制维度的 typed
failure"的直接要求；修复前实测该场景只给 umbrella code + 消息。

证据对照：闭包两条在改动前**已经通过**（说明闭包规则本身早已存在，缺的是验收证据），
第三条在改动前失败（umbrella code），改动后按真实维度报错。矩阵 C04 映射已更新为这三条
（保留成本去重一条作为补充）。

两条回归目录 402 项通过；全程未调用真实模型。

## 2026-09-27 基线标记：`0918ee7` = DSH 接入前的代码对照基线

用户决定：以 **`0918ee7`**（`test: prove multi-detail formula closure across pages and its
budget failure`）作为 DSH（DeepSeek Harness）接入**之前**的代码对照基线；接入完成后再验证
集成行为与真实质量（§16.3 单列，需要授权 live）。

该提交上的状态：

- 全离线套件 `python -m pytest -q -m 'not live_llm'` = **4014 passed / 3 deselected /
  12 subtests passed / exit 0**；
- 离线准入回执 `artifacts/runs/2026-09-18-live-admission/offline-receipt.json`
  绑定 `engine_commit_sha=0918ee76d079…`（该回执属于该基线，后续任何提交都会让它失效，
  重新准入前必须重跑 `record-offline-receipt`）；
- 本轮文档提交（审计方案、DSH 插件设计、`docs/README.md` 索引项）不改动 `src/`、`tests/`、
  `scripts/` 的任何字节，因此**代码语义**仍等同 `0918ee7`；但 `docs/` 参与引擎 source
  digest，提交后 digest/commit 会变化，回执需按上一条重新生成。

## 2026-09-27 基于本机 DSH 的隔离开发环境

授权范围：用户要求先搭建隔离环境，依据已有 DSH 开发且不影响日常使用。本轮只完成环境、
启动/检查工具及操作说明，没有实现业务 bridge、调用模型、提交 Git 或切换默认产品入口。
开始时 HEAD 为 `d48b4e4`；保留已有两份文档修改、子模块 dirty、草稿和原始 run 目录。

实际发现的日常安装是 `/home/cuihengjia/.npm/_npx/1e7f6d9597241db0` 下的已构建 npm 软件，
DSH `0.1.5-rc.3`，231 个 `dsh*` 包版本一致，原 profile 模块链接指向该安装；日常 home 为
`/home/cuihengjia/.dsh`。依据最新用户要求，实际开发目标采用这个版本；设计中的
`c36a83ff / 0.1.7-alpha.1` 明确降为源码研究参考，不能借用其 commit 标记当前 npm 树。

新增 `scripts/dsh_dev.py`、`scripts/dsh_dev_smoke.py` 和 `integrations/dsh/dev/` 说明/离线 patch；
`.gitignore` 忽略整个 `.dsh-dev/`。运行包/lock/25,478 文件与链接已独立复制，无共享硬链接；
Node 使用原可执行文件 `v25.8.2`，每次启动检查版本。启动器固定独立 home/profile/workspace，
过滤继承的凭据与 DSH/Node 运行参数，并强制 bubblewrap 根目录只读、开发目录可写；无隔离
则拒绝启动。原端口 `3080`、`19387` 及模型端口 `8006` 明确拒绝；默认开发端口 `3081`。
模型适配器、模型重试/标题、遥测及 Web 搜索等按实际安装的 plugin ID 关闭，未拷贝凭据。
没有创建 Python worker 环境或修改既有 Python 依赖；它们属于后续接入工作。

验证及证据（当前环境的新增观测，不借用历史 pytest 计数）：

- `python scripts/dsh_dev.py setup`：exit 0，复制后的完整树与来源字节/相对链接完全一致。
- `python scripts/dsh_dev.py doctor`：exit 0，25,478 项完整摘要通过、共享原安装 inode 为 0，
  bubblewrap 内原 home 只读。开发 home 实际写入/删除临时 canary 通过。
- `python scripts/dsh_dev.py config`：exit 0，真实 launcher 生成组合树，离线关闭项落在实际
  plugin ID 上。`python -m py_compile scripts/dsh_dev.py scripts/dsh_dev_smoke.py`：exit 0。
- `python scripts/dsh_dev_smoke.py`：exit 0，真实 Web 首页及 4 个 JS/CSS 资源均 HTTP 200，
  无模型对话；测试结束后监听端口关闭。测试进程由 SIGTERM 结束（子进程 exit -15），
  脚本按检查结果 exit 0。初次外层沙箱阻止本地 listen（EPERM）；随后使用工具批准的本地
  监听权限重验，脚本内 bubblewrap 文件系统隔离未移除。
- 负例检查 exit 0：保留端口被拒、重复 setup 拒绝覆盖、继承的 `DSH_HOME` 不能指向日常
  home、API key/`NODE_OPTIONS` 不传给子进程、`HOME` 值保持原样。
- 原安装再次全量摘要与复制基线一致；原 home 的 15 个配置/凭据/插件配置文件未变。
  初始“全部 home 文件不变”检查发现另一个项目的会话和投影缓存共 2 个文件发生更新，
  因此不声称所有会话静止，也没有回滚它们。原目录在开发进程内只读是归因边界；日常会话
  更新不作为开发环境失败或修复目标。
- `git diff --check`：exit 0。未跑全项目 pytest，未生成新的离线准入回执，未触碰 `src/`、
  `tests/` 中的业务实现。

持久操作说明：`integrations/dsh/dev/README.md`。本机原始证据：`.dsh-dev/manifest.json`、
`runtime-inventory.json`、`evidence/doctor.json`、`evidence/composed-config.yaml`、
`evidence/web-smoke.json`、`evidence/web-smoke.redacted.log`、`evidence/launcher-checks.json`、
`evidence/everyday-preservation.json`；临时前置记录 `/tmp/c2p-dsh-env-20260927-_08f6ry6/`。
认证启动 URL/cookie 只留在测试内存，写入的日志已去除 URL；原配置/凭据只存摘要与元信息。

剩余：WP2 针对实际 `0.1.5-rc.3` 验证自定义插件 Loader、首请求绑定、terminal 参数来源、
取消与 LLM seam；未据环境启动声称这些兼容门完成。业务代码对照基线仍是 `0918ee7`，本轮
新增脚本与文档会影响实际 engine identity；历史回执不能批准后续 DSH live。

## 2026-09-28 DSH 接入的实现单元拆分与团队执行计划

授权范围：用户要求以总设计为意图，由负责人充分调查 `0918ee7` 和本机 DSH，拆分执行
文档、责任任务与步骤。本轮完成规划交付；没有开始业务改码、模型调用或主流程迁移。
用户明确授权团队分工，安排三个只读调查/复核职责：DSH 兼容、Python 内核、流程质量；
主 Agent 统一写文档。不使用 skill，不委托外部通信，不提交、切分支或改日常 DSH。

基线核对：HEAD 仍为 `d48b4e4b22c94c82b45d2179ba452d72b164102d`；逐文件比较 802 个
已跟踪 `src/`、`tests/`、`scripts/` 文件与 `0918ee76d079b9392ec03400c0c4c9fdff5bc784`
字节一致。前轮未跟踪的两份开发脚本、开发 README/patch 单列；没有称工作树干净。
DSH 实际为隔离 npm 快照 `0.1.5-rc.3`，Node `v25.8.2`，upstream SHA 未知；研究参考
`c36a83ff / 0.1.7-alpha.1` 不能给本机包盖章。保留子模块 dirty、草稿、原 run 目录及
原有文档修改。历史 4014 测试回执仍只属于 `0918ee7`，本轮未重新执行或生成回执。

交付 `docs/dsh_execution_20260928/`：8 份阶段执行文档、总入口、共享接口、验收矩阵、
机器可读任务表、源码/运行包清单，共 13 个文件。49 个任务均有 owner/reviewer、依赖、
独占文件范围、实施步骤、交付和具名 AT；B00 为 ready，其余 planned，无任务标成已实现。
总设计继续约束方向，执行文档细化工程流程；任务粒度是可审查单元，不强制一个单元一个提交。
`docs/README.md` 增加入口，总设计补 §0.5 并修正实际安装接口和阶段边界。

关键设计收口：

- 默认业务流程仍是 LangGraph，DSH 执行 Agent，Python 保留领域/账本/验收/提交权威；
  显式并发开关默认关闭，所有主/子/verify/辅助请求受 run 与 backend 两级限制。
- 实际包是 `dsh-agent-presets`，按目录扫描 `agent.cordis.yml`；Host service、preset 工具和
  child 绑定分层。`agent/created` 不 await Promise，`pre-step` 晚于 prompt assemble；
  标准 spawn 无法证明创建期绑定时，H02 以公开窄 provider 验证，不调用私有 helper。
- I01 只交付统一组成身份原语；C02/R03/R04/A01 分别验证 prepare/dispatch/resume/receipt
  接线，避免反向依赖。实际加载 JS、运行包、lock、Node、preset、schema 都绑定；不能只
  比 Git 可见源码。新增裁决任务按已落地文件更新原 validator 来源清单并做摘要变化反例。
- C00 单独承担真实请求 renderer 和自有无模型投影握手，依赖 C01 schema，供 C02 计量/
  clamp/重编后冻结。公开 assemble 与最终 provider wire 分别记录；真实 pi-ai 对隔离假
  HTTP/SSE 服务的测试前置到 Gate-C/Gate-V，不拿自建 mock adapter 代替真实转换证明。
- raw argument stream、normalized terminal、parsed object 与 prose 来源分别记录；
  pi-ai 会重新序列化最终参数；必须 await Session flush。取消只在独立 cleanupSignal 下
  `waitForExit` 返回 true 时确认 provider 范围静止；未知发送保留占用并暂停整个资源组。
- K02 在原 registry 拆 record 准备/active 激活，用持久 fence 和多成员 manifest；K02+K03
  经真实 reader 验证已有 g1 后 g2 每个写点故障。C03 局部事务与 F02 全文输出接线分开。
  parser、assessor、composer 和 invocation reducer 保持原 owner 共用。
- A01 先复现再修原准入 CLI：当前小 pytest 目标仍可默认登记全部必测 labels；该结论本轮
  为静态代码发现，未运行反例。新覆盖必须由实际 Python/Node 子命令及报告派生，读取重算，
  测试前后核对身份；不以增加一个 Node label 代替执行，不否定既有 4014 日志本身。
- 幂等回执绑定 execution、实际 result、validator；每个 task/epoch 至多一个正式终态，
  换有效 key 不能提交第二个不同结果。授权→已有回执→新提交 revision 检查顺序保留。
- G01–G03 是主图入场修复，G05 实现所拥有的角色并前置基本 Editor/Rewrite，待 G06/G07
  的验证/补证分支具名 pending。G08 才验全部 16 节点真实行为和恢复；F01 收口完整编辑
  场景，F02/F03/F04 交付全文事务、图和导出，不能以默认 handler 推进冒充迁移。
- 小 Qwen live、审计 §16.3 L1/L2/L3、盲评和默认切换分别设门；当前计划不批准任何 live。
  C1/C2 共用独立评价端与数据访问边界，不能按 C2 专用回执存在性评分。

交叉复核修正了：子门“全 AT”导致的循环前置、I01/H03 对未来接口的反向依赖、renderer
无人负责、registry 提前激活、RPC 到账本漏接责任、validator 清单维护责任、重复终态约束、
组级 unknown 冻结、共享配置/请求槽释放、Authoring 实际入口和 Figure authority 反例。
DSH/内核复核在修订后无剩余阻断；流程组最后指出 G05 不应提前要求 G06/G07 已完成，已按
上段分开 G05/G08 验收并同步总设计与任务表。以上是文档复核，不是实现测试通过。

本轮验证（只做文档与代码状态检查）：

- `python /tmp/c2p-dsh-plan-20260928-hvrzaco7/build_plan.py`：exit 0，生成 8 阶段、49 任务、
  13 文件；生成脚本留临时目录，不进入生产源码。
- `python /tmp/c2p-dsh-plan-20260928-hvrzaco7/validate_plan.py`：exit 0；49 唯一任务/AT、
  依赖 DAG 无环、任务卡/台账/验收映射一致、WP 覆盖齐全、120 本地链接有效、25 个引用的
  既有 pytest 文件存在、Markdown fence/新增文件空白检查通过。
- 同检查复算 14 个 Python 源文件摘要/40 个符号锚点、12 个 DSH 实际包文件摘要一致；
  前轮 4 个开发环境文件摘要未变。只核对源码和已存在测试路径，没有执行这些测试。
- `git diff --exit-code 0918ee76d079b9392ec03400c0c4c9fdff5bc784 -- src tests scripts`：
  exit 0，已跟踪业务/测试/脚本未改；`git diff --check`：exit 0。
- 未运行 pytest/Node 实现套件、未启动服务、未调用模型、未修改 frozen runtime/日常 home，
  未重生成离线回执。新文档改变工作树身份，后续 live 仍须按最终冻结执行状态重新准入。

原始规划记录：`/tmp/c2p-dsh-plan-20260928-hvrzaco7/{inventory.json,validation.json}`。
持久基线与摘要清单见 `docs/dsh_execution_20260928/source_inventory.json`；后续开发入口是
同目录 `README.md` 的 B00→B01/B02 派工步骤，不把本轮规划写成业务已完成。

## 2026-09-28 B00 由负责人执行、独立 QA 复核并放行 B01/B02

针对用户询问负责人任务如何分配，按既有执行计划由当前主 Agent 承担 B00，内核复核 Agent
独立验收；三个实施窗口不争抢同一份基线清单。范围仅开发输入冻结及台账交接，无业务接入。

实测 802 个已跟踪 src/tests/scripts 文件的路径集合、mode、Git blob和SHA-256与0918一致，
HEAD仍为d48b4e4；两个新增环境脚本单列。复算原安装与隔离runtime全部25,478条目
（25,468文件、10相对链接）一致，普通文件无共享inode；231个DSH包均为0.1.5-rc.3。
Node v25.8.2、实际可执行字节、8个配置来源及历史4014回执均绑定；9个尚缺组件明确记录
不存在，未伪造bundle build、worker lock或上游commit，也未读取日常home凭据/会话。

新增 `integrations/dsh/compatibility.json`，完整冻结对象存入执行目录source_inventory.json的
`b00_freeze`；原规划快照保留。冻结摘要为
`abb0b4324de04f94c9c8f393d750f74d781530469d4b62d1d2ba0e13b3f72099`。
可读证据与责任分配见 `docs/dsh_execution_20260928/b00_baseline_freeze.md`。
基线冻结不把仓库设只读，不等于release freeze；后续改动登记新阶段输入，运行准入仍归I01等任务。

准确命令与结果：

- `python /tmp/c2p-dsh-b00-20260928-0gijha3h/freeze_baseline.py`：exit0，生成唯一输入观测。
  首次命令因Git默认转义中文路径导致分类断言失败（写出观测之前），改用`--name-only -z`后通过。
- `python /tmp/c2p-dsh-b00-20260928-0gijha3h/check_baseline.py`：exit0，重算冻结摘要、compact
  manifest映射、802代码文件/25,478运行条目/8配置/9缺项及历史回执；五种内存篡改破坏冻结摘要。
  反例只验证记录覆盖，不是未来I01发送门测试。原始结果在同目录verification.json。
- QA / kernel_execution_units独立重算上述输入、清单映射与缺项，返回PASS，无阻断项；未写文件、
  启动服务或调用模型。负责人据此把B00记done，B01/B02记ready，其余46项仍planned。
- `git diff --exit-code 0918ee76d079b9392ec03400c0c4c9fdff5bc784 -- src tests scripts` 与
  `git diff --check`：exit0。文档链接、49任务DAG及状态/依赖复核通过。

未安装依赖、未执行pytest/Node集成或live、未探测8006、未改日常DSH、未提交Git或生成新离线
准入回执。此次只放行B01/B02离线实施，Gate-B仍需它们完成，Gate-H和live均未获放行。

## 2026-09-28 B01/B02 独立验收、修正与 Gate-B 放行

用户提交 B02 验收和 H04 API 校准/交接缺口。LEAD 安排两个独立复核：B01 的真实夹具接线，
B02 的环境、工具链与 staging；复现后由原任务 owner 修正，负责人和独立 QA 再验收。
最终裁决、精确命令引用和后继责任见
`docs/dsh_execution_20260928/b01_b02_acceptance.md`。

B02 除测试发现/typecheck 遗漏外，复核确认 frozen runtime 在 DEV 可写挂载内、非 CLI
runtime 漂移未在启动前拒绝、worker 继承安装重定向/凭据、Node 测试绕隔离及并发 staging
混代等问题。修复限制在原 ENV 路径：统一 sandbox argv、完整 runtime 校验、净化环境、
测试私有网络与文件级串行；固定 build receipt 及 staged 字节对应，失败保留旧安装。
check:compat 顺序为 typecheck→build→stage→test，独立 test:compat 不重封漂移。
根 .gitignore 增加 node_modules/lib/dev-toolchain-build 三个精确忽略目录，lock/源码/测试仍可提交。

B01 首轮 39 项通过但缺 Formalizer 完成正例。新增验收的修前 4 项失败；夹具补可读合成源，
调用原 execute_formalizer_invocation_plan 默认 parser/validator，由原 owner 生成 accepted
包和 complete receipt，再经原 Writer builder/splice/Binder。新增正例及三项具名拒绝，
未手造 accepted；receipt golden 明示观测投影，完整执行回执另存，不能批准生产。

实际验证：

- LEAD 独立 `python -m pytest -q -p no:cacheprovider --basetemp
  /tmp/c2p-dsh-lead-acceptance-20260928-ks_qwck5/b01-pytest
  tests/integrations/dsh/test_legacy_characterization.py`：exit 0，43 passed，输入前后摘要相同。
  记录：该根 `b01-independent.json` / `b01-pytest.log`。实施者相邻四套 84 passed，四种
  hash seed 重建 golden 一致；原三个 golden 字节保留，见 B01_formalizer_repair_evidence.md。
- B02 独立 QA：两份 dev/tests 共 22 passed、toolchain:verify、check:compat（6 项 Node）、
  doctor 和 diff-check 均 exit 0。19 项源文件集合/字节前后相同，重建生成物一致；独立
  多文件混代、伪自洽 staging、receipt 发布失败回滚三项探针通过。
  完整 argv/退出码/日志摘要：`/tmp/c2p-dsh-b02-independent-final-20260928-g53ve4_j/verification.json`。
- 实施者真实新测试失败/类型错误探针均按预期 exit 1，清理后恢复 exit 0；含源码的独立
  package 真 build/stage 成功；零模型 Web smoke 首页及四资源成功、端口释放。QA 核对同源
  smoke 不重复启动。见 `/tmp/c2p-b02-handoff-fix-d2735bdd/final-results.json` 及追加修复报告。
  外层工具最初拒绝网络命名空间，获准后仍保留 bwrap/私有网络通过；没有无隔离降级。
- 负责人文档/台账/49 单元 DAG、链接、忽略规则、B00 历史记录不变及旧跟踪业务文件对照检查，
  记录于 `/tmp/c2p-dsh-lead-acceptance-20260928-ks_qwck5/handoff-validation.json`。

现 B00/B01/B02 done，Gate-B PASS，H01 ready，其余 45 项 planned。H02 必交真实导出、
mock claim/request recorder 与资源责任冻结记录，H03/H04 才能并行；兼容阶段不等待 C/R
生产 RPC，生产持久性在 R01–R03 复验。共享 build/stage/验收窗口由一人控制。
B01-D1 页身份/叙述顺序漂移由 K04 修原 compiler 并反转特征测试，阻断 Gate-K；G1 同归 K04，
G2 非空 atom 场景归 C02。没有把特征测试通过当作这些生产缺口已关闭。

HEAD 仍 d48b4e4；src 生产代码未修改。B00 冻结及 compatibility.json 的 null build 观测
保持历史身份，I01 另生成正式组成。未重装工具链/worker，未调用真实模型或 live，未刷新
准入回执、未提交/推送、未启动 H01 实施；日常 DSH/runtime 维持原字节与使用入口。

## 2026-09-28 H01 独立验收通过、负责人放行窗口一实施 H02

本条续记 H01 后续进展，不改前条历史阶段的结论。H01 首轮提交后，负责人/内部协作者曾
介入修复；用户明确要求负责人只做指挥后，内部实施已停止，未回滚已有工作。窗口一接管
已有修改并完成补强及 boot 后异常清理，窗口三独立复验，负责人本轮只读核对证据并更新
设计/交接/任务台账；未改实现、未新建内部实施任务、未运行产品测试或构建。

裁决：AT-H01 PASS；H01 done，H02 ready，H03/H04 保持 planned。共 4 done / 1 ready /
44 planned，Gate-H 尚未通过。持久裁决、完整身份、N1–N5 非阻断备注和各窗口指令见
`docs/dsh_execution_20260928/h01_acceptance.md`；H02 接口冻结要求仍以 h02_h04_handoff.md 为准。

证据来源为窗口三的 `/tmp/c2p-dsh-h-qa-w3-20260928/reviews/H01_verification.json` 与
`H01_verification_pass2.json`，原始日志在 `.dsh-dev/run/qa-w3-20260928/h01-recheck/`。
两遍 check:compat exit 0（16/16）、独立 R1–R6 exit 0（8/8）、无标记恢复 exit 0（16/16）；
注入运行自行 exit 1，分别 9.577/9.534 秒，非 timeout 强杀，端口释放并独立拒连，标记/私有
目录清理；doctor、stage --check、diff-check 均 0。未变的 Python 套件按已绑定证据未重复跑。

负责人本轮以 Python 只读复算：两份 QA JSON 引用的 23 个日志/产物摘要均相符，当前 26 个
受测源文件与相同 before/after 快照一致，无差异。loader.test.ts 为 4e6e6699…，构建回执
ea2289b1…，staging 回执 3a671640… / staged 树 abe6365d…，runtime 7e8f199b…。
原三项缺口及 LEAD 的清理缺口均关闭。N1 的历史 profile 写者仍未知；冻结 CLI prepareProfile
无条件重写空 root 的静态机制不能当作历史事件归因。N2 硬杀未测，N3 快照写元数据增强交给
窗口三的新 H02 QA 工具，不重写 H01 历史证据。

窗口一按第 01 部分实施 session-binding/role-dispatch/binding.test，并形成真实导出、mock
claim/request recorder 及资源责任的接口记录。窗口三先准备独立反例，拿到冻结交付才接管
构建与复核；窗口二等待 H02 接口通过后实施 H04。H02 只验证创建前回执/创建期绑定时序，
生产持久性由 R01–R03 复验。用户的“负责人不自行修复”职责已写入阶段入口和台账。

本轮只更新 docs 与本记录。文档检查脚本
`/tmp/c2p-dsh-h01-acceptance-20260928-e8e7gcf9/validate_handoff.py` 完成：49 个任务/任务卡
一致，DAG 无环，159 个链接有效，B00/compatibility 历史身份未变，Git 补丁空白及旧跟踪
代码对照通过。另复算 26 个 H01 源输入仍一致，7 份交接文档无尾随空白。原始检查记录为
同目录 `handoff-validation.json`，证据核对为 `artifact-review.json`。未重跑实现套件，
未提交/推送，未更改日常 DSH、frozen runtime 或旧准入回执；新增文档不构成 live 授权。

## 2026-09-28 H02 候选审查、接口补齐与三窗口派工

负责人本轮只读源码/冻结 runtime 并更新执行文档；未修改实现、候选接口记录或构建，未运行
Node/pytest/模型测试，未启动内部实施 Agent。当前 H02 的 session-binding 6324fbde…、
role-dispatch 87cc8fef…、binding.test 91957e6b… 与最新交付相符，已进入构建回执 173c846d…；
窗口二/三较早的“文件不存在/尚未构建”描述已过时。23/23 等结果仅引用窗口一交付，非本轮
独立重跑；H01 原验收不变，H02 尚无窗口三正式 PASS。

裁决与可转发指令：docs/dsh_execution_20260928/h02_review_directive.md。H02 为 in_progress，
interface_status=changes_requested_not_frozen。静态确认 L1 缺完整 request recorder 合同、
L2 真实导出要求 caller 而示例/宽松替代类型绕开此要求；L3 旧父绑定省略 fence hint、L4 任意
provider 覆盖先 start 后查绑定，由窗口一先最小复现、修原 owner，窗口三独立验证，本轮未
将静态路径宣称为运行反例。追加 request-contract.ts 为窗口一的共享类型 owned path，
窗口二审查消费语义；不在 H02 提前实现 H04 middleware 或 Python 持久账本。

真实 runtime 静态校正：prepared 通路才有 adapterStream 第二次 config 比较，比较不含
messages/tools；markAgentLoopRequest 仅标记，真实 loop 另行冻结 header/messages/request，
自己持有 prepared call，且 NO_ADAPTER 分支可回落 direct stream。公开 llm/stream hook 无
prepared handle 参数，不要求 H02 传递不存在的公开对象。H04 增完整装配摘要和真实 loop
观测，分别验证裸 API 特征、回执前后/next 前后的材料约束和 direct/fallback 硬门；C00/V01
wire 校验保留。H03 的 Session flush 责任恢复为本阶段兼容证明，R/A 后续接生产持久路径。

窗口一持 H02 修订与 build/stage 写权；窗口二只读合同/实验设计；窗口三准备 QA 探针，
重新冻结后才开最终验收窗口。QA 快照加入 inode/mtime；构建阶段与只读测试阶段分开，
元数据变化具名报告。验收窗口覆盖的执行文档也停写；H02 PASS 且接口冻结后才放行 H03/H04。

负责人文档验证：/tmp/c2p-dsh-h02-lead-review-20260928-dujd3wwv/validate_handoff.py，exit 0；
49 任务/任务卡一致、DAG 无环、170 链接有效，4 done / 1 in_progress / 44 planned，
B00/compatibility 历史记录不变，git diff --check 与旧跟踪业务代码对照均 exit 0。
candidate-before/after.json 核对 12 项实现/测试/配置/候选接口/构建/staging 字节未变；
执行 Markdown 空白检查通过。仅 docs 与本记录变化；无 live、提交/推送或日常 DSH 操作。

## 2026-09-28 H02 第二轮候选接收、窗口三正式 QA 接管

负责人只读核对第二轮 H02 源码/测试/接口、窗口二附件和窗口三 v2 计划，未改实现、未运行
产品测试/构建、未启动内部实施。当前 session-binding 86cf5bcf…、role-dispatch 466fba99…、
request-contract d133fc43…、binding.test 5f37582e…、接口文档 84321b6a… 均与窗口一报告相符。
构建回执 03c7ccff… 的 src_inputs 全匹配；staging 回执 9baa607d… 绑定该构建，14 个 staged
文件的集合、大小与逐文件摘要均匹配。27/27 沿用实施者报告，不冒充负责人或独立 QA 实测。

当前派工及设计校准写入 docs/dsh_execution_20260928/h02_qa_handoff.md。H02 改为 review，
candidate_status=frozen_for_review，interface_status=review_pending；接口最终批准冻结须在
独立验收后，不能作为 QA 开始的前置。窗口三获得正式验收和独占构建窗口，窗口一/二保持
共享输入冻结；H03/H04 尚未放行。L1–L4 记为实施者已报告修复、待独立复核，未直接关闭。

QA 用 C-H02-1…14/S1–S5，更新双消费者并要求新文档正向编译，旧 expect-doc-fail 仅保留历史
反例；按取消阶段区别 claim-aborted/creation-aborted。H02 验 recorder 可消费，真实请求
middleware 硬门归 H04，避免形成循环依赖。诱饵 provider 用真实 child 验清理，并分别记录
前置绑定时序与失败后清理，不以 dispose 计数冒充前置门。候选文档示例在 root.dispose 之后
reserve 的静态顺序问题已交 QA 登记，等待汇总后定向修订，不在验收窗口抢改候选。

窗口二附件的 API 特征发现保留；结构化 SessionBinding 类型不证明对象可信来源，RequestBindingRef
可由 Host 派生，运行时必须核对当前 binding。附件草稿遗漏 dispatch、访问字符串 requestRef.digest、
拒绝时静默结束流，不能当可编译实现模板；由窗口二按已交付真实类型重写设计。reserve 失败的零
派发靠本次真实控制流/独立计数证明，不靠自报 not-sent；unknown 保持不退款/不自动重发。
Agent/handle 静止、adapter 请求结束、托管子进程退出区分范围，无此类子进程时可具名不适用。

文档验证脚本 /tmp/c2p-dsh-h02-qa-handoff-20260928-lf0mmsvc/validate_handoff.py exit 0：
49 任务/卡片一致、DAG 无环、176 链接有效，4 done / 1 review / 44 planned；历史 B00 与
compatibility.json 不变；git diff --check、旧跟踪业务代码对照均 exit 0。candidate-before/
after.json 核对 14 项候选源码/测试/配置/接口/构建/环境回执字节未变。
本轮仅更新规划文档、台账及本记录；写完后暂停改动 QA 快照覆盖的输入。无 live、提交或推送。

## 2026-09-28 H02 正式 QA 证据复审：I2 仍阻断，交回窗口一

窗口三报告 AT-H02 PASS 并释放验证窗口；负责人本轮只读核对正式 JSON、原始日志、最终探针
及 H04 消费方案附件，没有运行产品测试/构建或修改实现。QA JSON sha256 为
921ba816cbcf9ce6c3e6f77284dfb0bf369f13632b68210ed39263f38adfb57a；16 项候选输入与
21 个日志/记录/最终工具摘要均匹配。证据复算记录为
/tmp/c2p-dsh-h02-gate-review-20260928-6jm6yv7n/evidence-review.json。

LEAD 不采纳整体 PASS：C-H02-11 原始 binding_final.log 明确记录
decoyPromptDeliveredBeforeBinding=true，同时 decoyDisposeCalls=1。当前前置门只比较公开
bindingProtocol 字符串，诱饵经真实创建并 followup 后才被 backstop 清理。前者已经违反
首次材料投递前绑定，后者仅证明失败后清理；上一轮 h02_qa_handoff.md §2.4 明确不能互抵。
实际窄 provider 的正常创建期绑定等独立通过事实保留，QA 原报告/日志不改写。

最新裁决和派工写入 h02_qa_handoff.md §5–6。H02 回 in_progress，review_result 为
CHANGES_REQUESTED，interface_status=changes_requested_not_frozen；台账另保留
qa_reported_verdict=PASS 和判定分歧依据。I2 是原 L4 的未闭合硬门，不新增工作包；I1
文档生命周期问题同轮交回窗口一。窗口一修正式注册 provider 对象/Host/bindings 归属准入，
协议仿冒须 start/prompt/child/claim/adapter 全零；保留合法自定义名及独立 backstop 清理。
窗口三保留原证据、追加判定修订，拿到新冻结后针对性复验；H03/H04 尚未放行。

窗口二只读修订 H04 草稿：不能以请求自报/缺失 sessionId 退出受保护计量；实际返回的
dispatch 回执必须验证，不以请求与自身比较代替；等待回执后 next 前再次检查取消/当前绑定/
真实摘要，未知输出上限不填 0；next/iterator 异常、提前 return、abort 和清理失败必须有界
处理及留下准确结算/unknown 事实。统一正文与 C1–C5 的资源范围口径。这些归既有 H04 AT，
不要求 H02 先实现 middleware，也不改 Python 唯一账本或冻结 runtime。

负责人只更新规划/台账/本记录。文档检查脚本
/tmp/c2p-dsh-h02-gate-review-20260928-6jm6yv7n/validate_handoff.py exit 0：49 任务卡/台账
一致、DAG 无环、179 链接有效、4 done / 1 in_progress / 44 planned；历史 B00/compatibility
记录不变，git diff --check 及旧跟踪业务对照 exit 0。candidate-before/after 核对 16 项
候选输入不变，原 QA JSON 摘要不变；无 live、Git 提交/推送或日常 DSH 操作。

## 2026-09-28 H02 第三轮：I2 关闭，仅剩 I1 文档异常清理

负责人只读核对第三轮修订报告、freeze3/recheck_l4.log 及其 runner 输出/探针摘要，未重跑
产品测试或修改实现。日志 sha256 942ee0cadecfe21c1a0eb8e7433f3d9167c60a4fc4d1d7897acc5d6130e0a9fb，
5/5 exit 0：协议仿冒零 start/prompt、错误归属与撤销/替换前置拒绝、合法自定义名创建期绑定、
已准入 provider 创建期取消无残留。接受 I2 关闭，第三轮代码与原有通过证据保留。

当前代码为 role-dispatch c8758e10…、session-binding 404f7984…、binding.test 59835929…；
构建回执 989b2076…、staging 回执 a44dec24…。第三轮开窗清单的 15 项输入与当前比较，
唯一差异是接口文档：开窗 cfdb9e8a…，实际 before/after 快照及 closing identity 已为
314bfd69…（与当前及窗口一交付一致）。UNCHANGED 只证明 17:43:09–17:44:09 快照区间，
不能据此称整轮都是 cfdb9e8a…。原报告中 1389 字符/755、929 偏移不适用当前示例。

当前 §5 块为 1475 字符，reserve 位于 872、root.dispose 位于 1451，先请求后释放已修正。
剩余 I1 为异常清理：dispatchRole 在 try 外；run.dispose 抛错会跳过同 finally 中 root.dispose。
这些是文档示例控制流问题，不重新开启 I2 或生产实现。指令写入 h02_qa_handoff.md §7：
窗口一只修改该示例，用内外清理作用域保证两处异常也尝试 root 清理；窗口三按新文档及
代码块摘要定向复核类型/异常分支和证据身份，不运行 build/stage/兼容全套或旧 Python 套件。
H02 保持 in_progress，接口待最终批准；H03/H04 尚未开工。

窗口二的合同澄清已采纳并记入 §8：DispatchReceipt 通过已接受 ReservationReceipt 关联
binding；估量版本/来源由 H04 包装与证据承载，不为此改 H02 合同。scope 必须验证真实来源，
不能仅据请求 ID 查表；lastStage 按实际观测，inner.next 不等于 adapter-entered；本地一次
finalize 尝试不声称 durable exactly-once。其余既定 H04 约束保留，待准入后实施。

只读证据与身份差异记录：/tmp/c2p-dsh-h02-i1-closeout-20260928-khtbt3nc/review.json。
同目录 validate_handoff.py exit 0：49 任务卡/台账一致、DAG 无环、182 链接有效；4 done /
1 in_progress / 44 planned；B00/compatibility 历史记录不变；git diff --check、旧业务对照
exit 0。candidate-before/after 核对 15 项候选/构建/配置字节未变。本轮仅改规划文档、台账
与本记录，未代修接口示例、未执行产品测试/构建、无 live 或 Git 提交/推送。

## 2026-09-28 H02 最终验收通过，H03/H04 并行放行

LEAD 本轮只读复算最终 QA 报告、原始日志和候选身份；未启动内部实施 Agent，未修改实现、
测试、lock、受测接口文档或构建/staging。最终接口文档为
0ba7f1ce88e834706bae45039ab934c4e42ffde23119da96a747b01a7345e9c5；§5 代码块按去掉
末尾一个 LF 的规则为 1602 字符、e3ead04eeb53ef77945f9cfda9174379550c8f2a0e719449c9ea0a50a0e5d7dd。
其余代码与第三轮相同：session-binding 404f7984、role-dispatch c8758e10、request-contract
d133fc43、binding.test 59835929；构建回执 989b2076、staging a44dec24、staged 树 525f0b45。

QA 修订报告 §7 本次摘要为 1505e56315d84918bca5d3e8626aac859de2cfbf168f9955d7fb7ddfd35e037e。
负责人核对 12 个日志/探针/报告引用、50 个源清单文件与 14 个 staged 文件，均匹配。
I2 保留第三轮及最终 R-1…R-5 独立 5/5 证据；I1 按最终双消费者编译与嵌套 finally 静态控制流
关闭，不声称额外执行了文档消费者三种故障注入。机制 5/5；旧绑定探针 8/9、exit 1 如实保留，
唯一被取代的 C-H02-11 期望由前置零启动及已准入故障清理分别覆盖，不把该旧日志标为全绿。
第三轮 check:compat 27/27 与未受影响的 Python 证据继续引用，本轮不重跑产品套件。

裁决写入 docs/dsh_execution_20260928/h02_acceptance.md：AT-H02 PASS、H02 done、接口
frozen；H03/H04 ready。窗口一按原 owned paths 实施 terminal/raw/flush，窗口二实施请求
计量/scope/prepared/取消；窗口三准备独立反例、冻结后验收。H04 最新消费方案接受，先实测
Agent scope 可观测性，再落实稳定回执快照、最后异步等待后复核及准确的终态/静止事实。
不再要求提交同内容方案；不扩 H02 合同或 TS 持久余额。共享构建由窗口一协调，双方暂停
受测输入修改后才可执行；正式验收窗口交给窗口三。Gate-H 仍待 H03/H04，未授权 live。

同步任务板、文档入口和当前交接状态，历史 QA 指令保留并标注已由最终裁决取代。
只读复算与文档验证输出位于 /tmp/c2p-dsh-h02-acceptance-20260928-g7a2s_v2/。
validate_handoff.py exit 0：49 任务卡/台账一致、DAG 无环、199 链接有效，5 done / 2 ready /
42 planned；B00/compatibility 历史记录不变；git diff --check、旧跟踪业务对照 exit 0。
candidate-before/after 的 15 项候选、配置、接口和构建摘要完全相同。本轮只改规划与验收记录，
无模型调用、日常 DSH 操作、Git 提交或推送。

## 2026-09-28 H03 候选接收与 H04 实施审查、构建窗口重排

用户交付 H03 12/12、当前组合 45/49，以及 H04 部分实现与路由/scope 推断。LEAD 只读核对
源码、冻结 runtime 的公开实现和已有日志，没有执行构建/产品测试或代修。H02 五项受测输入
仍与最终验收相同。当前 H03 terminal-result b8084ba8、terminal.test d63a4d84、provenance
a98b75d7；H04 request-accounting 22886cef、request-seam 54943fd9、cancellation 68583e84；
构建回执 3fa4c2e5、outputs 55ab7e28、staging bf2cb46c、树 f441dbf3（18 文件）。
构建 src_inputs 的 7 个源码及 staged 的 18 个文件字节/长度均相符，不据此证明历史构建无并发写者。

裁决与步骤写入 docs/dsh_execution_20260928/h03_h04_review_directive.md。H03 登记 review，
H04 in_progress，Gate-H 未通过。静态发现：scope 探针在裸派发前已 dispose child，且未创建
第二个 child，不能证明 live child/兄弟隔离；agentOptions 实际已沿 dispatchRole、窄 provider
及运行时 resolver 传递，零 adapter/stopReason:error 尚不足定位丢路由。禁止用 stock spawn
启动后补绑定。H04 还缺最后一次 dispatch await 后 abort/fence 复核；终态记录不在 finally，
break 可漏记录，return 无界且吞错；stop 无 usage 被补零；inputTokens 恒为 0；parts 未冻结、
dispatch 仍传原 receipt；C1 未等 reserve 入场，C2 可空跑通过且空字符串不清除 refusal。
这些按静态事实交 owner 复现，不宣称 LEAD 已运行最小反例。

窗口三先在双方明确暂停输入写入后对 H03 做定向独立复核，优先跨 session/request 同 callId
来源、损坏/冲突恢复、不同工具的 terminal 后副作用、准确 flush 接口与落盘故障。
区分 SessionStore.flush(session) 的 boolean 与 backend.flush() 的 void；后台已落盘时不能
仅凭未显式 flush 断定 unresolved。H03 最小 fixture 暂不装常驻 preset。当前 h03-verify.log
为空，其他检查需真实非空日志支持，不为此重跑旧 Python/smoke。

QA 释放后，窗口一修 H03 发现，窗口二继续 H04 并接管下一轮唯一共享 build/stage 写权。
窗口二可在自己的 request-accounting.ts 实现必要的公开 Host 路由包装门，不能将漏计延后或
让 mock adapter 自带拒绝来制造通过。仍不改 runtime/日常 DSH，不维护 TS 持久余额。
每次构建前双方暂停受测源码/测试/配置修改，正式验收再次冻结完整双方输入。

证据根 /tmp/c2p-dsh-h03-h04-lead-review-20260928-jtfkzgit/：review.json 绑定原日志摘要及
静态发现；candidate-before/after 的 32 项受保护输入完全相同。validate_handoff.py exit 0：
49 任务卡/台账一致、DAG 无环、209 链接有效；5 done / 1 review / 1 in_progress / 42 planned；
B00/compatibility 历史记录不变，git diff --check 与旧跟踪业务对照 exit 0。仅更新审查/执行
文档、台账和本记录；无新产品测试、模型调用、Git 提交或推送。

## 2026-09-28 H03 修复轮静态审查与短定向复验派工

用户同时交回 H03 修复交付、H04 冻结/纠偏计划和绑定首轮的 QA CHANGES_REQUESTED。
LEAD 先按字节区分两候选：首轮 b8084ba8/a98b75d7；当前 c4a2d98b/99b8b5b4，
terminal.test 仍 d63a4d84。当前构建 026f81e3、outputs 2e66ab2e、staging 7009bee8、
树 f2175e64（18 文件）；H04 三文件 22886cef/54943fd9/68583e84 未变。
只读复算构建 src/asset/config/output 清单及 18 个 staged 文件均相符；核对旧 QA 三个日志
引用摘要。已有 owner 日志 h03-fixes.log 是 15/15，h03-fix-check.log 是 52/48/4。
这些是读取既有证据，不是本轮由 LEAD 新执行的产品验证。

H03 两项原发现仍 OPEN：拆分存储后 raw(callId) 仍取 latestByCall，提交端未关联所属流；
迭代正常结束不证明完整，冻结 runtime 会把 adapter 抛错转换成正常迭代结束的 finish/error。
rebuild 仅凭可选 data.error 缺失判成功，忽略真实 tool-result.isError；缺字段/坏嵌套类型、
schemaDigest 和来源状态校验不全；未校验 parsed/normalized 与同一真实成功调用对应；
重复记录仅比 terminalId/parsedDigest 且只校验首条，可能忽略后续冲突或损坏记录。
上述属于原 R-H03-1/2 的静态剩余边界，未运行新行为反例，不冒称已复现。

当前指令追加于 docs/dsh_execution_20260928/h03_h04_review_directive.md §6，历史 §1–5
保留。窗口三在双方暂停输入期间先做当前候选短定向复验；不重建、不重跑已知四项失败的
兼容全套或未受影响的 Python/CLI/smoke。释放后，窗口一修 H03 剩余项；窗口二按已经接受
的 S1–S7 计划继续实施，不必等 H03 最终 PASS。下一轮共享 build/stage 仍仅窗口二持有，
每次构建前双方暂停受测输入写入。通用 iterator.return 没有标准 AbortSignal 参数，超时
停止等待不证明底层已退出；清理须分别记录资源取消、实际静止与 unsettled。

H03 保持 review、H04 in_progress、Gate-H 未通过；任务板保留首轮 QA 候选与日志身份。
联合验收须后续冻结同一组合候选，在同一真实绑定 child 内验 terminal + accounting，
不得由两个分立 fixture 或 15/15 折抵。LEAD 本轮仅编辑指令、文档入口、台账及本记录，
未改实现/测试/锁文件/构建产物，未调用模型、提交或推送。
静态审查与文档验证证据根：/tmp/c2p-dsh-h03-fix-lead-review-20260928-9ub1iigi/。
validate_handoff.py exit 0：49 任务卡/台账一致、依赖 DAG 无环、210 个文件链接有效；
5 done / 1 review / 1 in_progress / 42 planned。B00/compatibility 历史记录未变；
git diff --check 与旧跟踪业务代码对照 exit 0。candidate-before/after 的 32 项受保护输入
完全相同，18 个 staged 文件再次逐字节匹配。本轮未触碰窗口一/二的交付字节或旧 QA 证据。

## 2026-09-28 H03 短复验 CHANGES_REQUESTED 登记，恢复双窗口实施

窗口三交回修复轮 QA。LEAD 只读核对 JSON 83d8b0e4、报告 f860282a、探针 28898f70 与
三条日志引用；受测 c4a2d98b/d63a4d84/99b8b5b4/802813d3、构建 026f81e3、staging
7009bee8、树 f2175e64（18 文件）与磁盘相符，H01/H02/H04 输入未变。日志 b2e41d66
为独立探针 11 项、6 pass、5 fail、exit 1；fb6024c3 为 owner 套件 15/15、exit 0；
ca938ba0 记录 bytes 与 inode/mtime 分类比较 UNCHANGED，0 差异。未由 LEAD 运行产品测试。

接受 CHANGES_REQUESTED：跨流不拼接、版本拒绝、摘要矛盾拒绝、无 tool/call 拒绝四个行为
点保留关闭；R-H03-1a/1b/2a/2b/2c 均改记已独立复现、OPEN，其中 normalized=null
真实抛 TypeError。仍未测的 abort/break/截断、调用与参数/turn/step 对应、其他坏字段、
重复记录的 raw/prose/callId/版本变体等逐项保留，不以五个已执行样例折抵整个 §6.2。

读 QA 探针同时发现正例局限：F1c 的 finish reason 是字符串 completed，经 unknown 强转，
缺真实 per-call 完成事实；F2f 的 call/normalized 为 {result:{}}，parsed 却为完整 draft，
tool/result 缺 turn/step、构造事件无 seq。不能把这两个观测到的成功当合法正例证明。
交窗口三从真实成功路径建立基准，单字段变异并断言拒绝原因，防止无关拒绝令错误修复过门。
保留原探针/报告；其 window 时间 19:35–19:55 与快照 22:12–22:13 的差异请追加更正，
当前缺陷绑定摘要与日志，不以不一致的时钟值证明独占；此项不阻塞 owner 继续实施。

当前指令追加至 h03_h04_review_directive.md §7。H03 从 review 回 in_progress，窗口一
按字段/恢复对应/逐条校验→协议完整性→来源归属真实接线修原 owner；H04 继续 in_progress，
窗口二立即执行已接受的 S1–S7，不等 H03 最终 PASS，并持有下一轮唯一 build/stage 写权。
每次构建、stage 和消费共享 staging 的测试期间，双方暂停受测输入写入。窗口三现只准备
自有 QA 夹具和未测矩阵，等待下一冻结候选；Gate-H 仍需同一绑定 child 联合接线与回归。

本轮仅更新指令、执行/验收入口、任务台账和此记录；不改实现、测试、锁文件、构建产物或
旧 QA 文件。证据及原报告/探针/日志副本在
/tmp/c2p-dsh-h03-fix-qa-handoff-20260928-pnh4hbws/，未运行模型、构建、产品套件或 Git 提交。
validate_handoff.py exit 0：49 卡片/台账一致、DAG 无环、213 文件链接有效；5 done /
2 in_progress / 42 planned，B00/compatibility 历史记录未变，git diff --check 与业务基线
对照均 exit 0。32 项受保护输入前后相同；六项原 QA 报告/探针/日志与读取时副本逐字节相同。

## 2026-09-28 按验证依赖重排工作：统一 TS 收口，提前启动 K04

用户指出当前并行未带来效率，要求负责人决策并使用已有执行文档。LEAD 读取任务依赖、
第 01/02 份计划、验证矩阵、最新 H03/H04 源码身份及既有日志，仅作规划，不运行产品验证。
确认 H03 新源码 3fcc5e99、两测试 86bb93ad/d7c0cc13、证据 36cdb16c；私有日志
5e206521 是 21/21。H04 主模块/seam 测试仍 22886cef/54943fd9，取消夹具改为38976204；
owner 报告 C0/S7 6/6 及漏传 agentOptions 根因，不归因 H02。共享 build 026f81e3/
staging 7009bee8 仍含旧 H03 c4a2d98b；当前源码尚无完整共享候选。QA v2 cff43330
只准备，未冒记正式验收。私有 H03 结果和局部取消结果不折抵完整 AT。

原分工只分文件，没有分开 TS 编译/staging、可信来源及验收依赖。调度重排直接写回
docs/dsh_execution_20260928/README.md §3.1、第01份当前交付批次、第02份K04启动安排、
verification.md；历史审查指令保留反例，头部标明旧双 TS 写者调度失效，不再追加另一套
日常指挥文档。总设计 §0.5 的执行计划引用同步说明开发与验收顺序的区别。

窗口二一次性接管窗口一当前 H03 交付，独占 H03/H04 原 owned paths 和共享 build/stage，
另授权一份 H04_request_evidence.md 批次证据。先联合正常路径，再完成全 AT/矩阵，最后
统一 check:compat 交窗口三，不逐子测试等待 LEAD。H03 的请求 sessionId 不是独立可信
来源证据，H03 capture 与 H04 请求门须在同一绑定 child 闭合来源与冒用隔离。
窗口三保持独立，候选前固定合法正例和精确拒绝码；坏第二条记录先报自身错误，不强制
所有变体都报 conflicting-records，不机械双跑已失效旧 probe。正式 QA 冻结批次读集。

窗口一停止 TS 写入，领取第02份 K04，状态 ready。显式增加唯一开发前置例外
implementation_depends_on=[B01]：已有 Python 页合同/编译器/caller 可用 B01 夹具独立
实施，不依赖新 DSH hook。原 depends_on=[B01,H03,H04] 和 completion_gate=Gate-H
保留，K04 不能提前 done，Gate-K 明确仍需 Gate-H；后续 I/C/R 顺序不变。窗口一持有
K04 Python 路径及相关 authoring_execution_identity validator 清单写权；K01–K03 仍 planned。
Node 读集之外的 Python 开发可并行，真正读取到相关身份的检查只短冻结对应文件，不能
忽略漂移或删读集。历史0918/B00/回执不改标，正常DSH、默认主流程和并发开关均未改变。

本轮只改执行/设计引用、台账及本记录，未改实现、测试、依赖、构建产物或 QA 工件。
证据根 /tmp/c2p-dsh-work-allocation-20260928-v3zzdpb7/，保存当前40项受保护输入及
依赖调整理由；没有模型调用、构建、产品测试、Git提交或推送。
文档/台账验证 exit 0：49 张任务卡一致、DAG 无环、219 文件链接有效，5 done /
2 in_progress / 1 ready / 41 planned。验证器分别检查开发启动和完成前置，限定提前例外
只能是 K04/B01，完成仍保留 B01/H03/H04 与 Gate-H；K04 与 H03/H04 owned paths 无交集。
B00/compatibility 历史记录未变；git diff --check 与已跟踪业务基线对照 exit 0。
40 项受保护源码、测试、配置、构建、QA 输入前后相同；本轮未代修任何窗口的实现。


## 2026-09-29 下一批分工：先证明 DSH 来源，K04 独立复核与条件启动 K01

LEAD 按用户要求只做只读诊断、调度、执行文档和台账；未代写实现、未派内部实现 Agent，
未运行产品测试、构建、CLI/smoke、模型或 live，未提交/推送。保留三个现有窗口及历史证据。
当前 runtime/隔离环境不更换，不重做 H01/H02，原 DSH 正常使用边界不变。

只读核对 H03 当前源码 3fcc5e99、H04 source 22886cef、cancellation 38976204，build
7eade607 / outputs 030521bf / staging c4b75942 / tree e97b48a8。owner 的四套件
8+13+5+6=32/32 不等于同 child 联合接线；seam 测试当前 a7732cd5，证据表仍记
54943fd9，要求分别绑定基线与 S1 测量身份，未自行重跑或改写 owner 证据。
LlmRuntime 实现的 streamWithRegistration 在自身 ctx 发射 waterfall，与 owner 三个同时
存活 child 都观察到兄弟和裸派发的 S1 结果一致；旧 scope 授权假设撤回。adapter 包装尚须
证明授权签发来源，不能在全局 hook 凭自报 ID 发证再以此认证。窗口二先交真实 bound-child
正例、裸请求冒用/重放等反例和可信来源链，再收口 S3–S6、H03 capture 和同 child 联合路径。
公开能力确实不足时交最小断点证据，不自行改运行时/loop factory；成功则直接继续，不逐步待批。

K04 owner 已交 120+10 的局部结果，代码摘要与报告一致；状态由 ready 更新为 review，
B01-D1/G1 保持 owner 已修、独立关闭待证据。窗口三现在对冻结 K04 集中复核，不空等尚未
就绪的 Gate-H。静态发现的验收证据疑问包括：跨 seed 探针只比较页信息、未覆盖实际 Writer
请求和紧预算多页；两种计划对照同时改变 ID 集，不能单独证明顺序；helper 无 envelope
比较，legacy 兜底须核对实际 caller。上述是 QA 任务，本轮未跑反例，不冒称新运行时缺陷。
Formalizer 当前已重算 technical_payload 并严格比摘要和 payload，不因其独立入口就扩写权。
QA 的 H03 R6 校准为该调用匹配 block-end 的完成事实，finish 单列；完整 P1 正例保留，
已完成 A 后 B 失败不得回溯否定 A；terminal 成功与持久提交继续独立验证。

窗口一在 K04 QA 期间只读准备 K01，负责收到汇总缺口后的补齐。K04 本单元全部 AT 独立
PASS 且实际 Python/identity 读集释放后，按条件授权直接开发 K01，仅 registry/test/
validator 清单和专属 k01_registry_evidence.md。K01 与 K04 的开发前置为 B01，完成前置
仍为 B01/H03/H04 + Gate-H；K01 目前 planned，K02/K03 无提前例外，C/R/后续门不跳过。
窗口二仍为唯一 TS/build/stage 写者，窗口三同一时间验一个批次；已开 K04 批次正常收口，
真正就绪的 Gate-H 使用下一个 QA 窗口。跨线身份读取单列短冻结，保留完整读集。

调度直接更新执行入口 §3.1、第01份当前批次、第02份当前安排、verification、task_board，
同步 docs/README、总设计 §0.5 及旧 H02 交接文档的调度替代提示；没有另建日常指挥文档。
证据根 /tmp/c2p-dsh-next-allocation-20260929-vs7beab9/：review.json、保护输入前后快照、
文档验证器和 handoff-validation.json。验证 exit 0：49 张卡/台账一致、DAG 无环、222 链接
有效，5 done / 2 in_progress / 1 review / 41 planned；K01 条件与 K04 待验收状态一致。
67 项受保护实现/测试/构建/接口/QA 输入与本轮开始时相同；已跟踪 src/tests/scripts 的
现有补丁摘要 1b3469e2 前后相同。B00/compatibility 历史记录保持原字节；git diff --check 0。
因 K04 已是授权业务变更，本轮验证“LEAD 未改现有补丁”，不再错误要求整个工作树仍等于0918。

## 2026-09-29 · K04-G1–G7 收口（窗口一接班）

接管前按第 02 份"最新检查点"核对冻结清单：首轮 10 个哈希全部命中，PMW `92161500…` 与
closure `bfa9acd4…` 即文档记载的 G1 修复检查点。保留 G1（待 QA），本轮完成 G2 六类实际
请求变异、G3 legacy envelope owner、G4 义务多重集守恒、G5 顺序家族判定、G6 实测摘要 spy 与
旧摘要出处、G7 Formalizer 发送前/no-send/合法复用；K01 未开工。

口径修正已落实：六例反例都保持**冻结合同**（来自合法 primary、不重算），只改实际发送侧，
并且合法初次发送与被变异的 repair **分开计数**（`primary_arrivals==1`、`repair_arrivals==0`）。
首轮"在构造点无差别变异"的失败实验不再计入证据。

产品侧改动：`unified_context_compiler.py`（G4 具名守恒阻断）、
`formalization_agent.py`（G7 no-send 回执来源、无请求不发行回执、reader 区分未实测）、
`page_contract_recheck.py`（仅注释改成可验证 owner 结论）；
`unified_context_models.py` 为**范围偏差**（R02 owned，planned）：`ActualRequestReceiptV2`
只把 `actual_technical_bytes_digest` 从无条件必填移出（accepted 仍必填），否则
"缺可重算材料"的 fail-closed 分支无法落盘。需 LEAD 登记到 R02。

验证：第 02 份 7 文件命令 140 passed；受影响 6 套件 539 passed；本轮定向选择器
20 passed；`git diff --check` 0；重新生成夹具仅 provenance.json 变，4 个页面 fixture 逐字节未变。
证据与未测项见 `tests/integrations/dsh/fixtures/K04_evidence.md` §6–15。K04 未 done（`B01,H03,H04`
与 Gate-H 不变），G1 与全部 AT 仍待 QA 独立复验。

## 2026-09-29 · K04 第二轮写权释放与交付身份（窗口一，本轮自立释放）

**本轮释放取代上一窗口的释放。** 上一窗口的释放绑定的是 G1 检查点（PMW `92161500…`、
closure `bfa9acd4…` 且无 G2–G7 交付），不能代替本轮释放；本节绑定的是本轮交付字节。

### 1. 写权释放声明

* **本轮最后一次写入就是本节**（写入 `.agent/implementation.md`）。写入完成后本窗口
  **不再写任何路径**：不改代码、测试、夹具、证据、台账或执行文档。
* **无待写缓冲区**：本节列出的全部改动都已落盘；没有待生成的产物、没有半成品分支、
  没有待补的测试。工作树即为交付物，未做也不申请 `git add/commit/merge/push`。
* **释放的交付身份**（与 `.dsh-dev/run/w1-k04-release/L8_identity_and_scope.log` 一致）：

| 文件 | SHA-256 |
|---|---|
| `src/code2paper/agentic/page_contract_recheck.py` | `62a01ead78569966853f506eba19ca7c5f3dc9dc26b5bd79627f04ea62899e24` |
| `src/code2paper/agentic/publication_method_writer.py` | `921615007246ca5681bdc27502e16a4284f72b2929a9820df569b8ed2fbe647e` |
| `src/code2paper/agentic/unified_context_compiler.py` | `9855889eafa812f8ca521883290c7e72d9b9acf2e5e518cf3fa5b40d0cb296a5` |
| `src/code2paper/agentic/authoring_execution_identity.py` | `8d2718e27a2c51513b4fcc7794ec339e5bd2472780e3540ca77a4b0e00e6f9be` |
| `src/code2paper/agentic/formalization_agent.py` | `d847263419657dce2d992d5a0f20fc9bfafad8e317fbdec3e000ff57a8dca738` |
| `src/code2paper/agentic/unified_context_models.py` | `99fbce7e7532a3b399a152b48d4e499a3db08f30440df880fcde155eb1156340` |
| `tests/regression_20260917/test_page_contract_recheck.py` | `bc0b5d2494bb97691e0fdc45b8572cbdb46a10452b31c74c41d0f25aff2150d5` |
| `tests/regression_20260922/test_authoring_contract_closure.py` | `5e9d278b6b2198f59782c3d54ff31c8c7bb8a543304574d0d5d9247ff3609d42` |
| `tests/integrations/dsh/test_legacy_characterization.py` | `b54c73478963d23c1293f9c2251a7c37dedeb9c8f29bc7ec3107ad4f134e1d1c` |
| `tests/integrations/dsh/fixtures/join_page_probe.py` | `bfd6c8c266ad908d00a46fd244a8bb62e9daa52cdf65ed1dbf97dba672276739` |
| `tests/integrations/dsh/fixtures/page_split_probe.py` | `554fa1a7417f621c15dab17fff5bf69ff2c42293f50fbafc475d89959b2662e2` |
| `tests/integrations/dsh/fixtures/legacy_fixture_builder.py` | `c10673a99387e185501dfd6bfd58cb5839e1896928801c8b4b29446661a0645d` |
| `tests/integrations/dsh/fixtures/golden/provenance.json` | `0e3545979d0034d32bae7bd3454b4c550d9228cb2bc91b4ebc30676aac6b7cda` |
| `tests/integrations/dsh/fixtures/README.md` | `f6a4d2fa77490e007cee92c2f015c914d248653bd9c987461bf668da7cdec464` |
| `tests/integrations/dsh/fixtures/K04_evidence.md` | `3e9e01fb9b878e7076fa9a18ccdd57185313bf993183d27f030bfd1abf548adc` |
| `tests/test_agentic_formalization_guards.py` | `374f4096042b528ea729c34e46d5b0922d1ebdc5fe2b78d35a56cc10c4add401` |

* 四个页面 fixture 未变：`d1311afe…`（legal）、`fbcd999d…`（author_no_atom）、
  `edb25f5d…`（invalid_counterexamples）、`d4c60b43…`（completed_formalizer）。
* **K01–K03 独占路径零改动**（`git diff --name-only` 对 registry/publication/index 为空）。
  `authoring_execution_identity.py` 本轮未改，仍为首轮 `8d2718e2…`。
* QA 一旦正式接管，其实际读集即冻结；本窗口不再改任何被读字节。

### 2. 完整读集（本轮实际读过；只读，不含写权推断）

执行文档与台账（LEAD 维护，只读）：`docs/dsh_execution_20260928/02_kernel_publication_and_request_guards.md`、
`…/README.md`、`…/interfaces.md`、`…/verification.md`、`…/task_board.json`（K04 卡）；
`docs/README.md`（仅 grep K04 行）。

产品代码（读法：全文件 / 区段 / grep）：`src/code2paper/agentic/page_contract_recheck.py`（全）、
`publication_method_writer.py`（区段 4700–5660、6290–6410、21190–21270、23000–23060 + grep）、
`unified_context_compiler.py`（区段 1583–1620、1759–2415、2785–2825、2985–3040、4226–4286 + grep）、
`unified_context_models.py`（区段 600–719、1170–1230、1480–1609 + grep）、
`unified_invocation_ledger.py`（区段 1295–1454）、
`formalization_agent.py`（区段 2395–2620、2700–3200、3195–3300 + grep）、
`llm/section_writer.py`（区段 1680–1755、3060–3140；属 C02/C03 领域，仅读）、
`agentic/method_architect.py`（区段 7915–7950）、
`agentic/authoring_execution_identity.py`（仅 grep）、`agentic/mechanism_context_pages.py`（仅 grep 命中）。

测试与夹具：`tests/regression_20260922/test_authoring_contract_closure.py`、
`tests/regression_20260917/test_page_contract_recheck.py`、
`tests/integrations/dsh/test_legacy_characterization.py`、
`tests/integrations/dsh/fixtures/{K04_evidence.md,README.md,legacy_fixture_builder.py,join_page_probe.py,completed_formalizer_fixture.py}`、
`tests/integrations/dsh/fixtures/golden/provenance.json`、`…/golden/legal_page_with_atoms.json`（脚本内读取）、
`tests/test_agentic_formalization_guards.py`、`tests/test_agentic_publication_method_writer_unified.py`、
`tests/regression_20260917/incident_archive.py`（经测试导入）、`.gitignore`（仅 grep）。

运行根（列出/读写）：`.dsh-dev/run/w1-k04-g2/`（探针，未跟踪）、`.dsh-dev/run/w1-k04-release/`（本轮日志，未跟踪）、
`.dsh-dev/run/qa-w3-k04/`（仅列出）。

**跨线只读登记**：读了 LEAD 的 docs/台账与 `section_writer.py`（C02/C03 领域），均只读、未写；
`unified_context_models.py`（R02，planned）是本轮**唯一**越出 K04 独占范围的写入，理由与影响见
`K04_evidence.md` §13，需 LEAD 登记追认，本窗口不再改动。未读 TS/`integrations/dsh/` 源码、
未读凭据或会话内容。

### 3. 本轮实际命令与日志路径/摘要

复现脚本（逐条含真实命令）：`.dsh-dev/run/w1-k04-release/run_verification.sh`，
SHA-256 `7a16468a9aa8f51137685d9be36418e35a3d523d4847a9c41d478c5e06cbab58`。
日志根：`/home/cuihengjia/agent/Code2Paper copy/.dsh-dev/run/w1-k04-release/`（未跟踪；新鲜任务根，
不依赖沙箱私有 /tmp）。

| 日志 | 命令要点 | 退出码 | 结果 | 日志 SHA-256 |
|---|---|---|---|---|
| `L1_doc_command.log` | 第 02 份所列 7 个文件 | 0 | **140 passed** | `9da96404f3f196864f748f722658436f0193c60687ee1d02c7e939cd5f360b0a` |
| `L2_affected_suites.log` | regression_20260917 + regression_20260922 + 4 个受影响套件 | 0 | **539 passed**（含 L1，不相加） | `a4f6d4e7abe36e5edbfe64cdcf952e8d637e37700c646579f061009ba2636a97` |
| `L3_round2_selector.log` | 4 个文件 `-k "g2_ or g3_ or g4_ or g5_ or g6_ or g7_"` | 0 | **20 passed**, 145 deselected | `bdde8ba9a87c0fe7b97662d90fd739c41788de0da6e42e57be8764f65b8e7765` |
| `L4_compileall.log` | `python -m compileall -q src tests` | 0 | 无输出 | `2fb4c88b7858c641ad133b2148ea154db49c6a38ed623b6d1a97b60bed77cdd7` |
| `L5_git_diff_check.log` | `git diff --check` | 0 | 无空白问题 | `d9fa0603076ec4a9ef02736cce0481b41de92e8cf7609304225d89fc1d1c57aa` |
| `L6_golden_regeneration.log` | 重新生成夹具 + 前后 sha256 | 0 | 5 个文件前后逐字节一致（4 页面 + provenance） | `f9f0a2bb79e3aaca7a5d14808b829658cdd8373fa30c8a4410f34c4cfb4c3646` |
| `L7_join_page_families.log` | G5 家族探针 ×4（`PYTHONHASHSEED=0`） | 0 | 默认 `page:806ec3e8…`/`sha256:d8776c5d…`；`narrative`→`p10,p2`/`page:ebe2e9d4…`；两个集合族不变 | `ddc9dac4f1c446dd174446bdfbfe198d4bd1a0607338cbe727a3c8920a53e822` |
| `L8_identity_and_scope.log` | 16 项候选 sha256 + `git diff --stat` + K01–K03 空证明 + `git status --short` | 0 | 见上表；K01–K03 未改 | `4c658160fae6ab8f29b69d948044ccb9971574fdc9c0a328f74bd0007f5533ab` |

每个日志同目录另有 `<name>.exit`（内容 `0`，SHA-256 `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`）。

**未持久化的观测（如实登记，不倒造日志）**：G7 的"修前/修后对照"是会话内临时还原两行修复后
跑 `tests/test_agentic_formalization_guards.py -k g7`（修前该用例失败、恢复后通过），当时未落日志；
本节不声称有日志。QA 可用 `K04_evidence.md` §12 记录的两行差异自行复现，本窗口不再改源码。

### 4. 交接状态与未决

* K04 仍 `in_progress` / `review_result=CHANGES_REQUESTED`：本轮不自批、不登记 done，
  `docs/dsh_execution_20260928/` 与 `task_board.json` 的裁决与 `candidate_status` 更新归 LEAD；
  G1 与全部 AT 待 QA 独立复验。
* 完成前置不变：`depends_on=[B01,H03,H04]`、目标 Gate-H；Gate-K 未过。
* 未测边界与恢复办法见 `K04_evidence.md` §15（TS/CLI/live、HTTP 层零发送、K01–K03 实现、
  索引/发布路径未动）。
* **K01 继续只读准备**：本轮未开工、未写 registry/identity 相关路径，也未新增
  `VALIDATOR_BUNDLE_SOURCES` 条目；其启动条件（K04 全部 AT 与阻断项独立关闭、读集释放）
  仍未满足，保持只读。

## 2026-09-29 · K04 第三批（GAP-1/2/3 合并补证）写权释放

**本批为“证据批”：零生产改动。** 只新增/修改两份账本**测试**、一个夹具探针与夹具 README；
产品文件（`unified_context_compiler` / `formalization_agent` / `unified_context_models` /
`page_contract_recheck` / `publication_method_writer` / `authoring_execution_identity`）
哈希与第二批逐字相同（见证据 §16.8 与 N4 日志）。

### 交付内容

* 片段 A（GAP-1+3 合并）：`test_ledger_recovery_matrix.py::build_gap13_artifact_runs` 用生产
  owner 一次性生成**同一组**四个真实持久产物（拒发+空实测摘要 / 无回执 / 真子进程崩溃
  `os._exit(9)` 的未知发送 / 合法接受），报告落在会话级基目录，两份账本测试**复读同一份报告**；
  先后经过 `read_invocation_ledger_state`、`read_attempt_outcomes`、
  `reduce_invocation_recovery`、`build_resume_preflight`、`unsettled_reservations`、
  `unsettled_started_attempt_records`（预算视角）与真实入口重跑。
* 片段 B（GAP-2）：`fixtures/formula_family_probe.py` 在真实编译器/页请求上给出**非空**
  `formula_obligation_ids` 与 `formula_package_ids`（各 2 个），分别只变一个家族顺序，三层报告
  （Narrative 序与闭包关联 / 冻结与重算身份 / scope 与整体 binding contract）。
* 两个**已复现但未修**的缺口按第 02 份要求登记最小反例 + 具体 owner，未扩成 R02：
  writer_attempt_ledger 的发送前拒绝诊断分类过窄；未知发送重跑把根因包成下游 realizer 预算错误。

### 本批身份（写权释放）

| 文件 | SHA-256 |
|---|---|
| `tests/regression_20260917/test_ledger_recovery.py` | `d9d8d180cf3d764ed9356d537d9fa3073e9c5210a05b47bc0749ede369817132` |
| `tests/regression_20260917/test_ledger_recovery_matrix.py` | `605b3d772776b043fc3760f082997c439cc0ab1dc5037d28923b730a79a6381b` |
| `tests/integrations/dsh/fixtures/formula_family_probe.py` | `547a5e672ca71c54cf82b269ebaec11ea8e0c5cfd287841011a10e362516a989` |
| `tests/integrations/dsh/fixtures/page_split_probe.py` | `23727000329b788859036de11fca5659a4d8fa518b1a87815ea487611dd83f64` |
| `tests/integrations/dsh/test_legacy_characterization.py` | `5ac6690d055817f1458fce957775266a1b338db9760c5a211962b7611338e172` |
| `tests/integrations/dsh/fixtures/README.md` | `c4805fc912fcb30c7f07c6d66acdc0156935f9f4bd80b7065c5a687e3991479a` |
| `tests/integrations/dsh/fixtures/K04_evidence.md` | `7592484a3d796b586fd928fbbd874df72e4fab85e4e7655fab2ba0a67d4a3f40`（§16 全部写入后；本记录自身的哈希见交接消息） |

* **本轮释放声明**：写入本节后本窗口**不再写任何路径**；无待写缓冲区、无待补测试、无未落盘产物。
  未执行 `git add/commit/merge/push`。
* K01–K03 独占路径零改动（N4 空证明）；四个页面 fixture 与 `provenance.json` 本批未变。
* 证据与复现：`tests/integrations/dsh/fixtures/K04_evidence.md` §16；补证根
  `.dsh-dev/run/w1-k04-gap/`（`run_gap_batch.sh` `05c314f1…`，N1 7 passed / N2 145 passed /
  N3 文档补丁 0 / N4 身份）。**未执行**第二批的 `run_verification.sh`，原日志未被覆盖。
* QA 复验入口：`pytest -q tests/regression_20260917/test_ledger_recovery.py
  tests/regression_20260917/test_ledger_recovery_matrix.py
  tests/integrations/dsh/test_legacy_characterization.py -k "gap1 or gap2 or gap3 or gap13"`。
* K04 仍未 done、未 component PASS：原前置 `B01,H03,H04` 与目标 Gate-H 不变；K01 继续只读准备。

## 2026-09-29 · Python 内核阶段（K04 收口 → K01 → K02 → K03）写权释放

按第 02 份执行文档连续完成四个单元；本记录给出范围、身份、验证与释放。详细证据：
[`docs/dsh_execution_20260928/kernel_stage_evidence.md`](../docs/dsh_execution_20260928/kernel_stage_evidence.md)、
[`docs/dsh_execution_20260928/k01_registry_evidence.md`](../docs/dsh_execution_20260928/k01_registry_evidence.md)、
[`tests/integrations/dsh/fixtures/K04_evidence.md`](../tests/integrations/dsh/fixtures/K04_evidence.md) §16。

### 1. K04 收口（原两个账本问题）

* **真实发送前拒绝的分类与计数**（`writer_attempt_ledger.py`）：判据改为"回执自称未越过边界
  **且**没有 provider-request 证据"。真实合同拒发现在被计成 `rejected_before_send`、
  进入 `rejected_before_send_events`、带出 `last_rejection_code`，不再落进
  `unvalidated_attempts`（没有可评价响应不该被要求本地结算），invocation 级原因由
  `no_events` 改为 `presend_refusal_without_send`；状态仍是可继续（`release_the_reservation`）。
* **unknown-send 不被下游掩盖**（`publication_method_writer.py`）：相位边界用同一归约结论
  检查每个必需页，`send_outcome_unknown` / `ledger_corrupt` 直接 `blocked`，reason 为
  `writer_phase_boundary_blocked:…primary_cause=send_outcome_unknown:…downstream_not_run=realizer,…`，
  不再让 realizer 的"预算被压负"取代 writer 根因。

### 2. K01 / K02 / K03

* **K01**：创建封摘要与加载验摘要分离（加载先比声明值，不借模型 validator 重封损坏值），
  按声明摘要交叉核对磁盘不可变 record、pointer 与 schema；`registration_id` 绑定
  producer/upstream/schema/完整逻辑内容；同逻辑内容幂等（返回原 record），同 ID 不同来源与
  同路径不同内容拒绝；旧 `1.0` 走具名只读 reader（不迁移/不重写/不重封）。
* **K02**：`stage_publication_members`（内容寻址 + 文件/目录 fsync + 媒体类型）→
  `build_publication_manifest`（成员集合 + 读集 + 导出投影 + 自封摘要）→
  `commit_publication_generation`（`reserved→validated→committed→registered`，**先持久后切换**）→
  `switch_publication_active`（flock 临界区内比较 expected-active **与持久单调 fence**，不符即
  `PublicationCasError` 且不写）。`prepare_artifact_registration` /
  `activate_artifact_registration` 拆开了不可变 record 与 active 切换，消除内部抢先激活旁路。
  派生 `build_publication_receipt` 可从已持久 manifest/指针/journal 重建，重放不新生产物。
* **K03**：索引以**持久发布 active 指针**为权威（注册表只提供来源身份）；已提交未切换的下一代
  只能是 `superseded`，仅"已准备未激活"的 manifest 也可见；读取在同一次读取里复算 manifest、
  全部成员字节与不可变 registration，按媒体返回 `members`/`member_digests`/`member_media`；
  投影损坏不改权威 active，修投影不重提交；旧注册表默认 fail-closed + 显式只读开关。
  **未声称全文 Writer 已事务化**（`publication_method_writer.py:27974` 仍分别写
  Markdown/authorship/checkpoint，归 C03/F02）。

### 3. 验证与身份

* 最终代码/测试状态聚焦批（补证根 `.dsh-dev/run/w1-kernel-stage-final/`，脚本
  `.dsh-dev/run/w1-kernel-stage/run_kernel_stage.sh` `e3be04ec…`）：S1 K04 27 passed、
  S2 K01 15 passed、S3 K02 8 passed、S4 K02+K03 真实 reader 24 passed、
  S5 真实调用方/身份 89 passed；S6 `git diff --check` 0（修掉一处多余空行）+ 文档链接 0 悬挂；
  S7 身份清单。全部 exit 0。
* 同代码状态全量静态套件 `python -m pytest -q -p no:randomly`：**4114 passed, 3 skipped,
  12 subtests passed**，exit 0（既有平台跳过项，无 error/超时）。
* `VALIDATOR_BUNDLE_SOURCES` 10 项、`failure_code` 空，bundle digest
  `sha256:bb9b903872d0233bc9f7108fc41d62653b312a2ff5d43fdea66333f07901a8ec`；新入清单
  `page_contract_recheck.py`（K04）、`authoring_artifact_registry.py`（K01）、
  `authoring_artifact_publication.py`（K02）。
* **本轮释放声明**：写入本节后本窗口不再写任何路径；未执行 `git add/commit`；
  `docs/dsh_execution_20260928/task_board.json`、`verification.md` 未触碰（LEAD owned）；
  K04/K01/K02/K03 均未自批 done，Gate-K/Gate-H 前置与验收要求不变。
* QA 复验入口：`pytest -q tests/regression_20260917/test_artifact_registry.py
  tests/integrations/dsh/test_publication_generation.py
  tests/regression_20260917/test_artifact_index.py
  tests/regression_20260917/test_publication_transaction.py
  tests/regression_20260917/test_ledger_recovery.py
  tests/regression_20260917/test_ledger_recovery_matrix.py`。

## 2026-09-30 · LEAD 接管：旧 QA closing 登记、整阶段续工与 DSH 检查点 3

当前请求限定 LEAD 负责规划、接口/写权、台账和门裁决，产品实现由两个现有 owner 完成。
沿 docs/README → DSH 执行入口 §§3.3–3.4 → 第 01/02 份、verification、interfaces 接管；
保留 8 份文档和 49 个单元，不新增协作体系、实施 Agent 或常驻 QA。

### 交接与裁决

- 读取旧 QA closing `80b1a4afec437713597ba4e703439cf8cc2ecec0fa4f74d1ef3dd42cba53b408`，
  §§2–4 明确无待写缓冲区/存活验证、释放本批 Python 读集并结束；closing 八项输入摘要
  全部匹配。原三份 component 报告与交付索引的完整摘要仍与 verification §7 一致。
- 13:20:10（Asia/Shanghai）以授权的宿主只读 `/proc` 检查本用户 122 个进程，相关 QA/
  项目验证匹配 0、不可读 0；排除本次检查与祖先，未保存原始 argv/环境变量、未发送信号。
  沙箱内 `/proc` 只见本次检查自身，未用于证明宿主无相关任务。明确释放加身份/宿主检查
  足以完成交接，窗口一直接连续做第 02 份 §4.2，不逐项等待。
- closing 中仍残留的三项“未声明/批后修订”和旧 runner/stage 建议继续按已生效裁决纠正；
  不重开身份争议、不改旧报告。`authoring_execution_identity.py` 在明确 Python 释放表内，
  仅由窗口一在原阶段串行维护；窗口二仍独占 TS/peer/build/stage。
- 读取 DSH 恢复检查点 3，摘要
  `a528487ea5ceba144807d76ba1345f0c8cc49c8bf2c5651a2493f5516d90ecc0`：owner 报告
  loader10/10、binding11/11、provenance13/13、request-seam6/6、cancellation6/6（1.70s），
  terminal0/8；typecheck/build/stage/config 报告 exit0。只读确认
  `request-accounting.ts` 的封闭摘要清单含 `toolHistory`，没有重跑这些套件。
- 窗口二继续 V4、完整 H04 来源/等待期/双 child/清理、组成保护及同 child 持久恢复联合
  证明；合法 S2 转绿不关闭全部 AT。完整同候选交付后才按需独立验收，未取得新完整候选。
  Gate-H/Gate-K 未通过，内核 CHANGES_REQUESTED 保持；第 03/04 份和 live 未启动。

### 证据、文件范围与验证入口

新鲜只读检查证据根：`/tmp/c2p-dsh-lead-handoff-20260930-vf8i1ndu/`，含
`inspection_before.json`（HEAD d48b4e4、863 项实现域文件清单和 QA 报告摘要）、
`qa_process_check.json`、旧报告读取副本、`dsh_checkpoint_at_takeover.md` 与
`task_board_before.json`。原 QA 报告/日志、旧 runtime 和 owner 检查点未被改写。

本轮只更新 docs/README、DSH 执行 README、第 01/02 份、verification、task_board 及本记录。
台账保存上一 DSH 检查点和旧 owner 报告；49 项原 status/depends_on/implementation_depends_on/
owned_paths/acceptance/AT/completion_gate 全部保留。新增的是已确认的读集释放、写权接回与
owner 检查点，不刷新离线回执或登记独立 PASS。

本会话可调用工具未提供向原窗口派发消息的能力，未取得原 owner 的续工回执；持续授权和
完整阶段指令已登记于同一执行入口供接续，不能将本次文档登记写成实施者已执行。
产品源码/测试/fixture/依赖/构建不由 LEAD 写入；产品测试、构建、模型/live 次数均为 0。
文档与台账校验、链接和 patch hygiene 的结果在下方追加，不以历史 4114 或 owner 数量替代。

### 本轮文档验证结果

- `python /tmp/c2p-dsh-lead-handoff-20260930-vf8i1ndu/validate_records.py`：exit 0。
  49 个唯一单元/AT、依赖无环，原任务状态/依赖/责任文件/验收语义与完成门保持；187 个本地
  链接可解析，零悬挂。863 项实现域文件前后相同；本次读取的五份旧 QA 报告未变，保存的
  DSH 检查点与记录摘要相符、读取期间原检查点未变。结果为同根 `validation.json`。
- `git diff --check`：exit 0，stdout/stderr 空；原始结果与状态在同根
  `git_diff_check.log` / `git_diff_check.exit`。该命令只检查 tracked patch，因此另对五个
  未跟踪的 LEAD 文档/台账运行 `git diff --no-index --check -- /dev/null <file>`。
- 初次未跟踪检查 runner 错把 no-index 的“有差异”exit 1 当成必须 exit 0，runner exit 1；
  五份命令实际均无 whitespace 诊断，原结果保存于 `untracked_patch_hygiene.json`，未覆盖。
  `python /tmp/c2p-dsh-lead-handoff-20260930-vf8i1ndu/check_untracked_hygiene.py`：exit 0；
  独立的故意 trailing-space 对照报具名诊断/exit 3，确认区别后纠正 runner 判据。
  更正与逐命令状态保存于 `untracked_patch_hygiene_v2.json`，不将首次 runner 失败写成通过。

以上仅文档/台账和交接检查，不构成产品套件、独立 component/Gate-H/Gate-K 验收。

### 2026-09-30 · 转回实施报告后的续工安排与仓库内释放清单

用户转回窗口二 checkpoint3（46/54 owner 结果）及窗口一按旧 pending 记录停写的报告，要求
下一步完整指令。LEAD 重读当前执行 README、verification §8 和台账，确认释放已登记。
在 verification §8.1 与 `read_set_release_record` 补入实施窗口可直接读取的 33 条确切路径：
候选12、validator来源10、证据文档2、历史K04读集16及另外两条原ledger责任路径去重；
原读集/报告不改，清单不倒填历史运行身份，也不新增依赖源的任意修改权。

closing 输入、日志目录和原报告摘要引用一并登记，跨会话私有 `/tmp` 不再成为重新等待的
前提。窗口一直接在新鲜 rework 根连续完成第02份 §4.2；窗口二连续完成 V4、完整 H04
AT 映射/缺项、组成保护、同 child 联合恢复、完整候选与接口冻结包。后继 QA 仍只在完整
候选就绪时独立集中启动，普通缺陷集中反馈给原 owner 连续返修。

H03 是现有六套件的剩余失败，组成/联合/冻结/独立 Gate-H 仍未完成；任务状态、依赖、AT
及 Gate-H/K 不变。当前收到的是转回报告，未收到释放后的开工/完整候选回执；LEAD 未改
产品实现、未运行产品测试/build/live、未启动新实施者或常驻 QA。

本轮文档/台账校验 exit 0：49 项原合同/状态/依赖不变、33 条释放路径均存在，历史 K04
read-set 摘要保持；189 个本地链接零悬挂。`git diff --check` exit 0；五份未跟踪文档/
台账的 `git diff --no-index --check -- /dev/null <file>` 为预期差异 exit 1、诊断为空。
新证据根 `/tmp/c2p-dsh-lead-continuation-20260930-7taqcc8q/` 的 `validation.json` 与
`hygiene.json` 保存范围、逐命令实际 argv/退出码和结果，没有覆盖上一轮检查记录。

### 2026-09-30 · 按当前代码起点补全新负责人交接

用户要求续工考虑实际代码与进度，并给新接手者完整分支/环境/文档/命令。LEAD 14:41
只读检查实际 source/test/launcher/manifest/peer，未修改产品实现或运行 build/test/live。
分支 `codex/agentic-p4-benchmark-cutover`，HEAD `d48b4e4b22c94c82b45d2179ba452d72b164102d`；
保留现有 dirty 内容和子模块。当前 Python 3.13.9、Node v25.8.2、npm 11.11.1，peer 解析
指向0.2；目标包/manifest身份读取确认，runtime全树没有重新计算或作独立通过裁决。

源码确认 toolHistory 与 direct/prepared gate 已有，不重做检查点3的首因定位；terminal
tool/来源/flush/新进程测试也已有，缺口在 loggedCalls 的旧嵌套结果读取。S1 已有全局扇出
对照，S2 裸请求反例则在合法结束后且不带signal，复制/重放使用独立授权对象；原 H04
等待期同signal/两个child真实计量仍待覆盖。当前第二回执等待后缺最后复核、settled缺usage
补零、inner.return无显式deadline、授权以provider+digest排队，按原S3–S6合同返修/验证。
kernel旧格式夹具改新pointer版本、竞争为顺序CAS、crash为本进程异常，原完整返修包保留。

新增实际 B02 接线发现：toolchain.mjs 虽按 C2P_DSH_DEV_ROOT 选root，但其
launcherEnvironment不传候选变量，Python stage/test argv无--candidate；Python默认
仅读取 C2P_DSH_CANDIDATE。完整npm链会选择旧默认根，不能据外层env断言全链0.2。
未运行该链尝试写旧stage，也未断言旧字节已被改变。窗口二应先在原driver补传和拒绝错配，
修好前使用显式0.2 launcher；目标pyworker也尚缺，旧worker不能顶替。两份_020冻结交付
文件与建议w1-kernel-rework根本次不存在；缺run根不构成开工阻塞或单独否定其他根的工作。

完整交接写入既有执行README §3.5，保留新LEAD角色、实施替代的单写者交接、两阶段持续
任务、严格门、版本隔离、现有命令入口。同步第01份和文档入口，修正README §6旧释放措辞。
台账global checkpoint已为3但stage_assignments内仍为2，现保留旧值入history并同步；
没有按测试数改49项状态/AT/依赖或通过Gate。独立QA旧批已结束，下批仍按完整候选触发。

本次输入/863个实现域文件摘要与修改前文档保存在
`/tmp/c2p-dsh-lead-code-handoff-20260930-wd5ya4k8/`；inspection.json区分代码事实、
覆盖不足与owner运行结果。未派新实施Agent、未使用此前拒绝的skill、未发送外部消息。

交接校验 exit 0：863个实现域文件字节未变，49个task对象（含状态/依赖/AT）未变，
释放记录保持；嵌套checkpoint与global最新记录一致；140个所查本地链接零悬挂。
`git diff --check` exit 0；三份未跟踪阶段文档/台账的 no-index check 为预期差异
exit 1且无诊断。实际argv/退出码、范围与结果落盘于同根validation.json。

### 2026-09-30 · 用户澄清为两个新实施者分别接窗口一和窗口二

此前把“新的人接手”默认解释成新LEAD，用户明确纠正：替换的是两条实施线，当前LEAD
保持协调/裁决身份。现更正执行README §3.5、文档入口与台账new_implementation_handoff：
新窗口一接原第02份Python整包返修、代码/测试/证据写权；新窗口二接原第01份完整0.2阶段，
独占TS/peer/toolchain/build/stage/目标环境。两者不能改LEAD台账/裁决或越界覆盖另一线。

已登记QA读集释放和原46/54证据均保持，不把实施者更换记成已开始修改或新验收。原写者
应停止对应责任域，交当前dirty字节、运行进程、构建/测试回执；尚未收到旧写者停止或
新实施者开工回执。不借QA释放推定原实现进程已经结束，也不重建QA等待门。窗口一不等
Gate-H才返修/提交component，正式Gate-K约束不变。窗口二保留检查点3并在完整阶段补
候选传递/worker、V4、完整H04、组成/生命周期、同child恢复和冻结交付。

17:07只读重核实际分支/HEAD、peer和关键源码身份，关键源码与上次快照相同，目标worker
及两份冻结文件仍不存在。未执行产品测试/build/live、未创建新实施Agent或新聊天，任务
状态和产品边界不变。修改前文档/台账与核验基线保存在
`/tmp/c2p-dsh-lead-two-window-handoff-20260930-ydb2qrof/`。

本次交接更正校验exit0：49个task对象、读集释放、LEAD模式及Gate-H/K状态保持；
863个实现域文件仍与前次代码核对一致；140个本地链接零悬挂。tracked diff check exit0，
两份未跟踪文档/台账no-index检查为差异exit1且无诊断；实际结果保存同根validation.json。

## 2026-09-30 · 窗口一新实施者接管（Python 内核整包返修）

身份：窗口一实施者，负责第 02 份 K04→K01→K02→K03 返修、测试与阶段证据。LEAD 台账与裁决不改。
起点：分支 `codex/agentic-p4-benchmark-cutover`，HEAD `d48b4e4b22c94c82b45d2179ba452d72b164102d`。
Python：`/home/cuihengjia/miniconda3/bin/python` 3.13.9。
接管核对：责任路径无第二个 pytest/写者；日常 `dsh web` 与仓库外服务未动。QA 读集按 verification §8.1 已释放。
未 pull/reset/clean、未切分支、未 commit。返修证据根：`.dsh-dev/run/w1-kernel-rework/`。

### 返修完成与本批写权释放

详细矩阵、23/12 身份和日志见
`docs/dsh_execution_20260928/kernel_stage_evidence.md` §9。
本批改了冲突归约、相位原因、发布崩溃退出/权威解析、索引只认发布指针，以及对应测试。
registry 与 execution identity 源码未改。真实 1.0 由冻结 `0918ee76` owner 在隔离子进程生成。

可审计全量：`.dsh-dev/run/w1-kernel-rework/run-S1sPM01x/full_static.log`，
`.exit` 为 0，4125 passed / 3 skipped / 12 subtests。三次跳过都是既有
`CODE2PAPER_RUN_LIVE_LLM` 门。聚焦 99 passed，退出码 0。`first_failure.txt` 不存在。

**写权释放**：本记录写入后停止修改第 02 份责任路径。不自登 PASS/done，不申报 Gate-K，
未 commit，未改 LEAD 台账。

### K-1/K-2 返修与再次释放

验收重放不再把矛盾发送或损坏账本结算成 `accepted=true`。reader 在消费 manifest
前核对声明摘要、复算摘要和发布权威。证据见 kernel_stage_evidence.md §10。
新鲜根 `.dsh-dev/run/w1-kernel-rework/run-uBEIctQW/`：聚焦 103 passed，全量
4129 passed / 3 skipped / 12 subtests，两份 `.exit` 都是 0。

**写权释放**：本段写入后再次停止第 02 份责任路径的修改。不自登 PASS/done。

## 2026-09-30 · 窗口一保管已验内核候选

按执行入口 §3.7 与第 02 份 §4.4 保管 K01–K04 component 候选。核对证据 §10 的六份源码/测试摘要、
`run-uBEIctQW` 的聚焦日志 `6becd0ea…` 与全量日志 `4bd9f61b…`，以及两份 `.exit` 均为 0。
HEAD 仍是 `d48b4e4b`。没有新的内核缺陷，未重跑套件，未改源码、测试、validator 清单或上述日志。
正式 done 与 Gate-K 仍等 LEAD 在 Gate-H 之后裁决。

第 03 份尚未实施。后续只能消费现有入口，不能另建发布、索引或账本：
`reduce_invocation_recovery` / `publish_validation_replay`，
`stage_publication_members` / `commit_publication_generation` / `switch_publication_active` /
`verify_publication_generation` / `bind_publication_manifest_bytes`，
`read_artifact_validated`，`load_artifact_registry` / `load_legacy_artifact_registry`，
以及 `VALIDATOR_BUNDLE_SOURCES`。C03 的局部正文事务走 K02 publication owner；全文仍是 F02。
`publication_method_writer.py` 在 C02 开工前保持本候选字节。共享清单增补仍由 LEAD 串行分配。

LEAD 确认（2026-09-30 22:25 后）：候选保管继续，不重复调查、不重跑全量、不提前改
C/R 模块或 validator 清单。C02 约束补记：旧 caller、本地结算
（`_settle_recorded_writer_attempt`）与新 facade 必须共用原
decode/splice/parser/assessor 路径；结算现在缺 decode/splice，属抽取时必改项。

## 2026-10-02 · 保管续核与后续阶段衔接登记

只读复核对账：六份候选源码/测试与 `run-uBEIctQW` 两份日志摘要全部命中，HEAD 仍
`d48b4e4b`，责任路径无运行中 pytest 写者。第 02 份 component PASS 继续保管；
未改 `publication_method_writer.py`、validator 清单，未创建 C/R 模块，未重跑全量。
复用清单（2026-09-30 23 时交付）继续有效，不重复调查。当前施工只在窗口二，
本窗口无新增工作。

后续派工（Gate-H/正式 Gate-K 满足后立即接续，本记录仅登记衔接）：

- 第 03 份窗口一序列：I01 composition 身份与严格校验 → C01 唯一 Python
  合同/schema/goldens → C00 补齐所需 Python 协议字段 → C02 抽取共用
  解析/decode/splice/评估并接旧 caller、本地结算、facade → C03 可信 ingest、
  局部发布事务、来源与幂等 → C04 有界 worker、最小权限 facade。
  Python 协议与 validator 单写权在窗口一；canonical digest 仍由 Python 计算。
  窗口二提供 runtime/loader/build 清单、wire 消费、真实 renderer/投影、
  跨语言 fixture、真实绑定 raw terminal 与 worker 接线。完整联合包验 Gate-C。
- 第 04 份（Gate-C 后）：窗口一 R01 持久 task/outbox/claim、R02 原账本与真实
  RPC、R04 Python 恢复、A01 真实覆盖回执；V01 与窗口二联合完成单 run 串行
  单 Writer 一个 mock 请求的真实闭环与新进程恢复。原 Gate-R/V 保留，Python
  仍是唯一预算与恢复权威。live、全文事务、完整主图迁移及默认切换不提前。

## 2026-10-03 · Gate-H 四组集中返修 owner 提交

范围遵循 stage_whole_package_review_20261003 §§3–4。修 activate 的 active 安装基线先验与 target 字节/身份/回执先验、临时文件准备及提交异常回滚；setup/audit 共用 pristine-base 身份和五文件改动域；smoke 修实际 staging tree 字段并核 staged receipt、前后不变及默认路径；新增真实入口反例，重写无效字典断言。固定源码模块头与当前 capability API 对齐，source patch 重登记（87941d84…）；runtime、声明及 Python 内核保持。

精确命令与原始退出在 `/tmp/c2p-gate-h-repair-20261003-final/`；稳定封存 `.dsh-dev/run/w2-gate-h-repair-20261003-final/`；durable 当前入口 `integrations/dsh/dev/gate_h_repair_batch_20261003.md`。source-built→delivery 串行 activate/build/stage 后，以 review_driver 的真实 launcher/只读 peer+staged receipt view 执行两侧原11文件93节点，各 exit0、93pass/0fail/0skip；两侧来源10/10、生命周期3/3 exit0；ops_driver 实际 B02目录46passed、执行身份24passed、doctor/audit正常入口及 web/compat正常smoke均 exit0；HTML/assets200、端口关闭、0模型 turn、tree/receipt identity一致。独立 types_audit 两包 tsc exit0，三声明同字节，257/385编译读集保持。git diff --check exit0。

108,614项完整输入的 bytes/link/inode/mtime 前后完全一致（before/after清单SHA均 d4780640…），原791份内核baseline全匹配。首套suite外层封存汇总误用TAP格式，后续封存内核计数误用764项操作快照，均属driver/清单选择修正，原始内层结果保留且产品输入不改，不重复成功suite；诊断与正确闭环在新包内登记。新 archive 输入逐成员核摘要，完整保存原测试、fixture、driver、运行包及工具链/worker输入，不用seal代替受测清单。初始外层EPERM获准宿主执行后保持项目bwrap自身隔离；无模型调用。

owner状态 submitted_for_independent_qa，不自批 Gate-H；正式 Gate-K等待、第03–08未实施，49项仍2done/9进行/38待实施。分支/dirty基线保持，无commit/merge/reset，原4129未重跑。后续由独立reviewer复验四组，Gate-H通过后LEAD正式确认Gate-K。当前交付不是产品完工或默认切换。


### 同日 r2 · 目标 Node executable 前置身份修复与当前冻结

r1 46项提交已完整封存，保留为历史。收口发现 manifest 指定的 Node executable 未在 activate 前读取：补存在、与当前执行 Node 同字节及实际版本检查；新实际 Node/Python wrapper 反例覆盖缺路径、同版本伪 executable，失败链接/两回执仍原样。当前提交改为 `/tmp/c2p-gate-h-repair-20261003-final-r2/` 与稳定 `.dsh-dev/run/w2-gate-h-repair-20261003-final-r2/`；runtime/types/build/stage 未变。

本轮两侧原93/0fail/0skip、来源10/10、生命周期3/3均exit0，B02实际48passed、执行身份24passed、doctor/audit及正常Web/compat均exit0；108615项前后bytes/link/inode/mtime完全相同（清单SHA a14e3ebf…），原791份内核保持，0模型调用。补源码侧已完成suite之后复制probe时误解引用symlink，Node在断言前缺依赖；保留失败raw/输入并恢复原peer symlink，再完成所有反例。before差异仅probe peer复制目录，source/test/driver/runtime/receipts不变；probe-setup-input-closure.json证明，不覆盖失败raw。最终peer为delivery。原类型独立编译读集、输出及driver同字节保留；完整归档108990个输入（含375个增补声明编译读集）与封存清单核验。owner仍submitted_for_independent_qa，独立Gate-H待裁决，正式Gate-K/第03份等待，49项实际2done/9in_progress/38planned不变。

### 2026-10-03 Stage03 窗口一：I01/C01/C02–C04（实施中）

用户明确按 stage03_batch_execution_instructions_20261003.md §3 分配；Gate-H/K 依据最新独立裁决已放行。保留原 dirty 树，不提交/切分支。Python/protocol/validator/compatibility.stage03 单写；窗口二独占 C00/TS/build/stage。活动交接在 docs/dsh_execution_20260928/stage03_window1_handoff_20261003.md，本次运行根 /tmp/c2p-stage03-w1-20261003。

I01 抽取原开发 inventory 为 stdlib runtime_inventory（开发 CLI 不需初始化领域包），原 inventory wire 保持；production composition 另绑定实际位置/解析字节/树/Node/配置以及原 engine、validator。CLI 合成测试副本补入其真实新增源码依赖。C01 导出严格模型/原 canonical/字节与语义两类摘要的 goldens。同步 Writer 原 structured_caller 的 decode/splice/normalize 已抽为 parse_publication_writer_response；同步/本地未结算响应共用，本地 settlement 保留当前完整 private section。新 facade 仍等真实 C00 组成与投影联验，未把 helper 自测当准入。

C03 候选保存 raw/normalized/parsed 分层，可信受控上下文由 Host 注入；局部原 publication owner/reader 提交正文/acceptance/authorship/raw/provenance，同 task/epoch 唯一终态，授权先于缓存，新副作用才核当前 revision/fence。C04 候选 private stdio 固定 RPC，有界 frame/chunk、bootstrap 与模型字段分权，R claim/reserve/dispatch 明确 unavailable。

阶段开发观察（均不能外推最终 Gate-C）：i01-c01.log exit 0 / 28 passed；parser-extraction.log exit 0 / 191 passed；three-path.log 修复测试对 outputs 的误用后 exit 0 / 8 passed（含真实编译 Formalizer+atom 与合法作者页）。provenance-b02.log 18 个 provenance 已通过；B02 旧默认候选 lock 与本批构建不同、合成 CLI 源依赖未拷贝导致三失败，逐项修复/切正确候选。worker.log 12 passed / 1 setup error：移动中的 TS 改变 engine identity，prepare/handshake 按设计拒绝 composition_drift；最终稳定后重测，未放宽身份。B02 candidate 回归还遇 Node spawnSync python EPERM，隔离临时副本的原入口回归请求自动审查的沙箱外执行；保留原日志，不把拒绝当 PASS。

compatibility.stage03.json 先登记版本和外部 evidence 定位，不回填被自身覆盖的 engine/composition 摘要；最终测试身份写外部根。最终状态、精确 argv/cwd/环境/退出与 AT 索引待同批冻结收口。

收口修复（新代码，待最终稳定身份验证）：I01树根原/解析位置与symlink关系纳入；inventory前后原engine/validator复算，拒绝混合状态。Formalizer逐包实际adapt输出匹配（含latex/绑定/qualifier全部字段），缺receipt拒绝；原adapt/schema来源加入validator。C01增research_required正向、0.0/0e0 Counter、float/bool Literal1原字节goldens，窗口二修TS词法保持。开发联合joint-6、author-2、cap-recompile-1已真实通过；因以上明确修复释放旧读集，不能借旧receipt声明最终相同身份。旧全静态4211passed/3skipped，指定owner265passed，新增82passed均保留历史日志；最终验证/联测/封存外部位置预先固定。未运行8006/真实provider，未实施R01/R02/R03或全局完成。

Stage03提交前复读返修：旧final-delivery包保留历史，撤为superseded_input（独立Gate-C未验，未宣告PASS）。
新作用ingest缺合同→当前revision/snapshot/fence/validator的绑定；修复为check_contract_current，新增完整identity/
read-set/material/config/schema/epoch比较，freeze绑定fence。已提交合法receipt缓存仍先于新作用状态检查。
新测试覆盖fresh Host借旧合同的三状态、五身份反例与合法缓存恢复；最后r2读集与所有观察证据重生成。
原final 91/265/4220 static、TS123都仅证明上一代码状态；TS/build无修改，下一Python校验/联合另冻结，
保持sameepoch唯一终态和pending_validation，不弱化已有原owner gate。

Stage03窗口一最终r2：submitted_for_independent_qa，索引 .dsh-dev/run/stage03-w1-20261003/final-delivery-r2/delivery-index.json。
最终精确命令与实际source前后快照见checks/commands.json：105focused、265原owner、4234全静态/3非本批live skips/7warnings/12subtests；compileall/diff-check均0，五步骤source一致。
C00最终TS123/0skip、唯一最终stage来自窗口二；r2技术和合法无atom作者页真实Loader/loop/fake wire→worker prepare/record/ingest→原publication reader和封存reader同代读回，domain pending_validation。
cap4096→1024原owner新plan/section/config/identity/projection，2次C00观测先完成，领域prepare网络/LLM哨兵下零发送；34真workerscope/权限/来源/冲突/runtime拒绝与cache恢复通过。
封存29279文件/链接全部长度/SHA复核，release核所有相关worker进程组静止、fake server关闭、parent/child/bindings释放。旧final-delivery保留历史，被r2替代。
最终读集显式释放后只更新协调/状态文档；当前engine因文档变化不同于封存8be7fe…，不得复用旧合同作新作用许可；代码/测试/fixture/runtime不改。
独立Gate-C待QA；不自批Gate-R/V/A/G/F/L、产品完成、默认切换/D5/发布，不调用8006/真实provider。不commit/merge/reset，原dirty保留。

## Stage03 Gate-C 集中返修（2026-10-03，窗口一）

独立裁决 CHANGES_REQUESTED，执行 stage03_gate_c_review_and_batch_repair_20261003.md。
保持 11 done / 6 in_progress / 32 planned，不进入第04份。r2 和 QA 封存不变。
GC-1：全 Unicode scalar census 确认旧 Pydantic/Rust `\\S` 的 25 个 White_Space 码点；
所有 Identifier 改为有版本的显式字符集规则，完整 exporter 覆盖八模型、native/enforcement、
character-rules 和双向 goldens。窗口二单写 TS/实际构建。
GC-2：check_frozen_current 复用在 render、初次 prepare、owner recompile 后及返回前，
校 revision/snapshot/fence、scope、身份与实际完整 refs/request/page/manifest；内容 revision 不混入记账序号。
GC-3：NEW ingest 在授权/输出完整性/合法缓存分支之后，复用 C02 投影、真实 wire 和本地计量核对；
所有 JSON refs 的 bytes/length/scope/media/semantic/schema 与跨绑定复核。完整14项依赖以
LocalWriterDependencyClosureV1 写入 provenance，原 publication manifest read_set 同步记录；
仍复用原 parser/assessor/authorship/generation/reader，局部 pending_validation。
测试结构：原 pre-C00 局部 ingest fixture 改为完整可核对的明确 UNIT test-double 引用图；
不会把它当真实 C00 证据。真实 DSH/pi-ai 假 HTTP/SSE、真实 worker 和原 reader 另走 fresh joint。
新 stdio lifecycle fixture 只在测试子进程注入外部 Host 状态变化/owner callback，不新增生产开关。
源内记录到此；最终命令、结果、代码状态、原日志、AT矩阵及释放写新 ignored 证据根
`.dsh-dev/run/stage03-gc-repair-w1-20261003/`。开发期 source_unstable 与 fixture 修正日志保留，
仅稳定输入结果用于新提交；owner 自测不改独立 Gate-C 裁决。


### Stage03 GC修复最终封存与释放（2026-10-03 23:46）

owner完整返修 submitted_for_independent_qa；独立Gate-C未自授PASS，仍11 done/6 in_progress/32 planned，第04份未启动。
最终专项226、原owner265、全静态4355/3原live skip/12 subtests、TS165、B02 48、audit/typecheck/build/stage/compileall/diff-check均exit0。
精确argv/cwd/runner/exit/耗时/source前后与原log在新包 checks/commands.json；全部新静态验证绑定同一11b8bf42…冻结engine。
真实技术页/作者页、新revision/fence owner正常freeze、新cap原owner重编、旧材料prepare、34原RPC、三终态99拒绝/3合法提交与缓存恢复/190RPC均通过。
真实FEFF和ASCII来自新native raw capture并由真实worker record_output通过；NEL非法拒绝与12真terminal双向对照见窗口二新包。
新封存34902文件/链接全部长度/hash/实际链接与文件集合复读一致，清单SHA ac40483b1cdaca1759906df205410f0f45cbb4b3a7919a4242aad6c07fa8e852。
最终身份、validator、composition与完整AT/GC矩阵见 docs/dsh_execution_20260928/stage03_gc_repair_delivery_20261003.md 和新 delivery-index。
释放2026-10-03T23:46:17.464627+08:00；原reader在档案复读，全部行为命令返回、worker进程组消失、Session/绑定/假服务关闭、端口可重绑；真实模型0、prepare发送0。
释放后仅更新本实施记录/报告/README/task_board/compatibility协调文件，当前engine会改变并另记ignored post-release-coordination.json；旧包不改标给当前树，原r2与独立QA包保持原字节。


## 2026-10-04 · DSH长期模块阶段A启动（单主执行者）

执行 stage04_06_long_module_execution_20261004.md 与第04份细则。当前只激活阶段A；保留当前dirty基线、HEAD/分支，无reset/commit/merge，无真实模型调用。运行根 `/tmp/c2p-dsh-stage04-20261004-ud6x5a4s`，start-state.json记录启动身份。R01 in_progress，其余任务依原前置连续推进；独立Gate-R/V尚未提交，done仍17/49。

新增task_store.py：SQLite FULL同步短事务/原run lease、稳定task/epoch/outbox、私有随机claim能力与独立claim fence、固定epoch起点、child绑定、取消、新进程读取及同一终态引用。task_store没有费用余额；不按PID/TTL回收claim。原lease新增scoped_run_lease，借用同进程租约时不释放owner的锁。facade新增具名durable模式，worker私有claim/resume/bind/cancel/read已接线；原stage03模式不允许生产claim。原ingest合法缓存仍先授权，新作用另验有效claim。新增裁决源纳入VALIDATOR_BUNDLE_SOURCES。

开发验证：`python -m pytest -q tests/integrations/dsh/test_task_recovery.py` exit0，5passed，3.30s，证明双Host barrier只有一个claim及跨进程epoch保持等原语；仅原语自测，不能记完整AT-R01。第一次联测 `python -m pytest -q tests/integrations/dsh/test_task_recovery.py tests/integrations/dsh/test_worker_protocol.py tests/integrations/dsh/test_result_provenance.py` exit1，146passed/1setup error，175.52s。原因是我在该验证进行中修改worker，原组成门正确拒绝composition_source_unstable；没有放宽门。随后先完成全部编辑，再冻结输入重验，原失败保留。新增真实worker生命周期用例使用已验compiler的UNIT投影材料，只证明RPC持久链，不冒充V01真provider闭环。

R01尚缺完整后端独占/恢复事实；R02预算与发送事件、R03实际Host、R04完整崩溃、V01/A01/V02仍待连续实现。下一动作：固定当前输入，运行新worker领取恢复与原C04/来源回归，再扩原统一账本。当前无常驻协作者，Python与TS/build写权均为root；独立QA在完整阶段包冻结后启动。


### 同日阶段A持续开发 · R01/R02真实私有RPC

先冻结编辑再验证：r01-worker-command.json / r01-worker-regression.log exit0，148passed（178.83s），覆盖新增真实worker领取/绑定/取消及新进程恢复和原C04/来源规则。后续补原run lease覆盖整个durable worker mutation，防止校验与publication提交之间取消；新增同主机具名后端持久独占原语，不按进程退出清除。backend_state_root/resource_key为显式operator组成配置；完整release/实际provider清理合同仍待R03/R04，不把保守占用当完整恢复交付。

R02新增DshInvocationEventV1和原统一账本内fsync持久事件，事件顺序/绑定/重复ID/冲突/引用损坏fail-closed。read_run_budget_state与reduce_invocation_recovery继续唯一裁决：reserve崩溃保守unknown；缺usage保留预留；适配器入口与dispatch-recorded不升级为HTTP到达；真实usage幂等；独立域验证仍pending。invocation_adapter接原材料/14依赖/模型profile/预算/claim/epoch期限与实际assembly重读；真实worker allowlist/schema接reserve/dispatch/settle/mark_unknown。adapter入口permit只能消费一次，恢复模式拒绝新dispatch；迟到事实可本地记账，原receipt缓存先授权，新作用另验live claim。发送格式失败通过有raw/Session引用的finish观察结算费用，不给出domain acceptance。

确切日志/argv/cwd/退出：r01-r02-rpc-command.json（65passed/28.81s/exit0）；r02-expanded-command.json（69passed/39.75s/exit0）。新增真实RPC反例包括实际assembly漂移、缺读取依赖、错epoch、取消、二次permit、原账本已有完成费用耗尽、真实目录写失败、跨worker恢复禁止派发、usage冲突以及格式失败费用保持；与旧恢复矩阵、身份及原worker receipt缓存回归同跑。projection、prior费用、format-failure Session都是明确UNIT材料；尚未经过R03真实DSH或V01隔离provider，不作为AT-R02完整通过或独立PASS。compileall聚焦及diff-check均0。

代码/测试基线保留，所有运行输出在fresh /tmp根。新增task_store/invocation_adapter/unified_invocation_ledger裁决源加入原validator闭合集合；只增已存在文件。R01/R02仍in_progress，17/49done不变；当前root独写Python/TS/build。接着R03固定argv/env/cwd的真实DSH subprocess kernel-client及Host recorder，不暂停逐helper等待派工。实际回收、所有崩溃点、V01/A01/V02和完整阶段冻结/独立QA尚待完成；8006请求0。

### 同日R03持续接线（尚未提交独立验收）

新增kernel-client.ts（真实DSH subprocess、固定operator argv/cwd/env、1MiB JSONL、严格帧/ID、RPC超时和迟到响应墓碑、fresh cleanup signal）、workflow-driver.ts（Python私有claim/request recorder及真实单Writer子任务pump）、execution-policy.ts（阶段A默认串行且拒绝parallel=true）。role-dispatch在未发布的child setup内await真实Python绑定；request-accounting新增实际assembly引用与真正适配器入口permit hook，不增加预算余额。Host原Session persistence flush后归档原events与raw，再由原worker record_output/ingest；真实Session tuple与normalized bytes在Python重核，原Python新增私有task.ingest_key提供幂等键，TS不另造算法。transport对照只允许合同已列的signal/sessionId/messages.id/createdAt，文本、tools、配置仍逐项保留。

新RPC新进程receipt重读自测22passed/34.69s（绑定上述后续transport改动前）；TS typecheck/build/stage exit0，25构建输出。真实DSH subprocess测试1passed/5974.73ms，生产worker领取/绑定/退出/新进程恢复/取消；该测试明确UNIT composition/projection，不是V01 provider PASS。精确观察写fresh根r03-development-observations.json；后续正式冻结需完整原日志与SHA矩阵。开发失败保留：外层sandbox不允许bwrap建loopback（经auto-review已授权在外层外运行原offline launcher）；相对路径在launcher包cwd不成立（改绝对路径）；locked pyworker不带pytest（去掉fixture生成链的pytest依赖，未安装/改锁）。测试Web URL输出需关闭实际web-runtime行；最新修正尚待复验。模型调用0。

R01/R02/R03均in_progress，done17不变；无常驻协作者，全部行为命令已返回，DSH测试context/managed worker已清理。下一动作为真实组成与C00观察驱动的完整Host/provider离线闭环，补失败费用/取消/epoch期限与R04逐崩溃点；再完成V01/A01/V02及整阶段全静态和独立Gate-R/V。仅StageA已激活，未越过L01准入。

### R03实际provider闭环及R04恢复前置（持续开发，未提交QA）

原来源/缓存回归r03-python-regression.log：165passed/206.94s/exit0。真实host-provider.test.ts已用实际Loader/peer/bundle/build/stage/Node/Python树冻结组成、真实DSH subprocess及原worker；C00隔离校准明确单列，task正式发送另计1次。真实pi-ai→假HTTP/SSE→raw/normalized Native Session→原Parser/Publication/Reader得到blocked receipt；原账本call_count=1/spent_input_tokens=17/pending=0。r03-real-provider-retained.log exit0/65078.92ms；后续测试专用guard worker只包装原main拒绝Python LLM/socket，先实际负probe，再计正式运行0模型/0网络。r03-real-provider-sentinel.log exit0/64010.37ms，sentinel闭合state=closed。原始运行根provider-retained-001/002在fresh /tmp包中，不是当前后续代码的PASS。

实际namespace发现启动器的/tmp为tmpfs，早期未共享测试产物退出即消失，不用其缺失产物背书。scripts/dsh_dev.py因此增--output-root：只允许新建canonical /tmp任务子目录，显式单目录bind，原runtime/源码只读及--unshare-net不变；不写HOME，不改变默认launcher根。新增隔离边界反例，r03-cancel-limits.log共25passed/39.45s/exit0。私有task.limits由原合同返回固定epoch起点/限额，Host派生不可重置的AbortSignal；取消写原账本cancel且保留未结费用。

R04当前决策：领取回包丢失不要求保存私有capability明文。TaskStore持久格式现为dsh-task-store/3（本阶段未发布版本；旧开发样本不迁移/重标）；持久存capability digest/claim lineage。可信私有task.recover在原run lease内更新claim fence，只给settlement-only，不延长epoch、不释放backend、不发新请求；旧Host mutation被新fence拒绝，reserve/dispatch再核durable grant_mode。新claim可绑定原费用事实的claim digest，不能给另一scope造费用或新派发。当前权限恢复聚焦r04-recovery-source.log 26passed/46.04s/exit0，但尚非AT-R04完整矩阵。

为terminal后/record_output前崩溃建立原始源持久点：TerminalArgumentCapture在真实block-end后、交付Native执行前await私有raw sink，raw octets落盘并记录task.capture_raw，只准本epoch一个不可变源、既有reservation和实际child/session/request绑定。Session/native成功证据flush后才record_output/ingest；Python还核同call的成功tool/result及completed turn/end，防止把normalized失败源恢复成成功。该新增raw sink和store/3仍待实际DSH重build/stage及恢复矩阵，不能沿用002的旧PASS。R01–R04 in_progress，17/49不变；下一动作先冻结这批输入，复验实际raw sink，再扩完整崩溃点、局部draft/author/research_required和清理，随后A01/V02。StageB模型准入未触发，8006调用0。

### R04真实进程中断与V01技术页前置（持续开发，未提交QA）

新私有request.status仅返回原reservation/reducer及原RecordedWriterOutput引用；Host recoverStoredOutput换发settlement-only凭证，已有输出只走原ingest_key/ingest，只有原始源时从实际Session persistence只读加载原events并归档。恢复不创建Agent、不进入adapter；Python仍核成功Native tool/result与completed turn/end，缺源不把normalized重序列化当raw。

r04-local-replay.log exit0，26passed/44.52s；r04-cuts-typecheck/build/stage最终exit0（初次typecheck拒绝测试直接.ts字面导入，改为实际URL动态导入，未改变compiler配置）。r04-real-provider-cuts.log exit0，3场景/237109.97ms：before-record、after-record、after-ingest分别在实际DSH管理的worker进程terminate后启动全新worker，丢弃旧私有capability并本地恢复。同一场景只有隔离C00校准1次+task派发1次，恢复新增发送0；原reader费用call_count=1/spent17/pending0。完整请求/SSE、Session/raw、result/cleanup、原SQLite/账本在provider-recovery-004三个fresh根，全部guard闭合state=closed、正式Python model/network计数0，假服务关闭后实际端口重绑定成功。该证据绑定当时源，随后fixture身份改动不能回填其身份。

新增test_host_crash_recovery.py：prepare后/reserve后/dispatch-recorded后/adapter-entry后实际SIGKILL worker并全新进程恢复，固定epoch、旧凭证失效、仅结算权限、未知预留不退款/不重发。此为内核journal矩阵，注入adapter-entry不是实际HTTP发送证明。初次4failed是断言用了不存在的错误名称task_settlement_only，修为实际task_recovery_cannot_dispatch后4passed/17.86s/exit0；原失败保留。随后fixture profile/model改为实际受控配置摘要、target绑定原archive source manifest、intent/claims绑定实际narrative/section材料、snapshot绑定archive，不再用标签摘要占位；这些身份仍明确controlled_offline_fixture，不宣称真实模型能力。r04-material-identities.log exit0，30passed/62.05s。

增加serial-writer.test.ts与serial-writer-research.test.ts复用同一实际链，技术draft使用原Formalizer fixture的provider原始placeholder正文，不搬运Binder后的文本；尚待实际运行。toolchain test:compat新增fresh --output-root传递，使递归发现的实际Host测试使用相同单目录隔离并保留产物；该toolchain修改待新build/stage和B02复验。R04仍缺terminal未flush/取消provider未知/父退子活与迟到/漂移完整矩阵，V01作者页和拒绝矩阵、A01/V02仍待实现。下一步冻结输入运行真实technical draft/research_required，再完成同阶段缺项；保持17/49，无独立PASS、无8006调用。

### V01技术页/typed gap实际闭环与A01首个修复（持续开发）

v01-terminal-typecheck/build/stage最终exit0。provider-terminal-005首次运行在发送前被严格Python model_validate拒绝requests列表（tuple_type），并暴露测试cleanup在bootstrap失败时读取不存在sentinel的额外错误；保持schema，改由model_validate_json(canonical_json_bytes(...))进入协议，并让cleanup把未启动sentinel具名null。原失败日志v01-real-provider-terminals.log保留。新根provider-terminal-006，v01-real-provider-terminals-repaired.log exit0，2场景/159886.12ms。technical draft来自原完成Formalizer材料的Writer placeholder原始文本，通过实际DSH/pi-ai/native/raw/原assessor/公式splice/Binder/authorship/publication，原receipt为pending_validation；research_required同链为waiting，不触发自动补证/第二请求。两者各C00校准1+正式task1、原费用17/调用1、恢复0新增发送、Python出口哨兵0、假服务端口释放。领域均未提升Verified。fixture身份现在绑定实际受控profile/model和原archive/narrative/section材料。

A01已重现默认覆盖漏洞并先取消build_offline_suite_receipt的默认完整四组test_plan_ids。单节点成功仅保留该命令passed，missing_test_plan_ids完整返回缺项；旧显式历史scope保留。test_dsh_admission.py首两个反例及原live_admission回归：a01-no-default-coverage.log，20passed/7.13s/exit0。这不是完整A01：原CLI版本化计划、actual Python/Node/CLI发现/报告、前后身份冻结、consumer复算/拒绝篡改，以及V02最终计划还未落地。新增文件只登记此范围，不拿该PASS作全套准入。

V01/A01进入in_progress；累计done仍17。当前无运行测试/模型进程；root持有Python/TS/build写权，独立QA未启动。接着实现机器报告和计划，同时完成作者无atom及错误内容/Unicode/预算/取消的同链V01矩阵；R04剩余父退子活/未知清理/late响应仍是实质未测项。

### A01实际机器报告与单目录路由（持续开发）

新增pytest_reporter.py，显式-p加载，记录实际解释器argv/cwd/rootdir、selected/discovered/deselected节点、setup/call/teardown及collection errors；缺call/phase、skip/error/not-run不会被passed覆盖。新增suite-reporter.mjs记录native Node metadata与enqueue/dequeue/pass/fail/summary（含skip/todo），保留文件容器的真实per-file summary。offline_admission.py只读重核报告字节SHA/长度、实际命令/cwd、发现集合/阶段/节点和计数；不凭summary或label造覆盖。新增三个已落地report/reader文件进入原VALIDATOR_BUNDLE_SOURCES。尚未有具名计划/聚合consumer/CLI v2准入，不能将这些reader视为A01已完成。

a01-actual-reports.log：11passed/4.62s/exit0，实际Python subprocess包括通过/失败/skip/零/collection失败；实际Node no-isolation用于外层sandbox内report-reader单元覆盖，正式DSH保持原launcher进程隔离。另一次真实Node子进程开发检查（require_escalated只为外层spawn限制，不联网）读回passed1/failed1/skipped1/exit1，consumer拒绝；两个正常节点真实process报告exit0并原reader读回tests2。原默认sandbox Node --test子进程失败日志保留，native no-isolation与真实process的差异明确，非候选DSH联测证据。机器报告目前为开发级，不替代完整冻结计划。

scripts/dsh_dev.py新增--report-path，必须直接位于新--output-root内、canonical且未存在；Node双reporter保留spec原日志与机器JSONL。同一--unshare-net/源码runtime只读/精确目录bind保留。toolchain递归test:compat自动生成fresh root及node-events.jsonl。a01-machine-route.log exit0，12passed/23deselected/4.72s；只聚焦reader与目录路由，明确不称全B02/全suite通过。下一步新build/stage后用同launcher验证实际报告文件、完成版本化计划及原CLI和consumer接线，再补V01作者/拒绝/R04完整矩阵和V02。当前无运行测试；无8006调用，17/49。

### A01具名计划及V01作者页实际闭环（持续开发）

实际launcher机器报告：a01-report-build/stage exit0；a01-real-launcher-report.log exit0，原wire 52场景/18499.99ms。报告器通过同一网络隔离launcher生成JSONL，原Python reader复算52个actual节点和native per-file completion，与source/runtime实际Node v25.8.2一致。中途读未完成文件被offline_node_file_not_passed拒绝，完整退出后才被接纳；没有把尾部summary缺失当成功。

新增suite_plan.py版本legacy-offline/2、dsh-stage04-offline/2，绑定实际递归发现文件SHA、原argv/cwd、public有效配置、engine/validator/组成、candidate与report路径。DSH必需Python/Node/CLI文件缺失则启动前具名拒绝，当前test_serial_writer_e2e.py/pi-ai-wire.test.ts/cli.test.ts等尚缺，不能造当前DSH完整准入。原budget/fee来源未改变。verify_suite_reports开始按固定计划与每个实际report/log引用、前后身份复算；还待原CLI runner及Receipt V2接线、完整反例和实际全套。a01-versioned-plans.log exit0，13passed/4.73s，为计划和报告开发检查，不是全A01。

按模块§2的稳定独立工作面，协作者author_fixture只写新author_page_fixture.py/test_author_page_material.py，已交回写权，5个原compiler/freeze/parser/assessor材料检查passed（协作者命令和exit0已收到，未冒充独立QA）。共享Python协议/validator及TS/build一直为root。作者fixture保留原完整archive/narrative/writer manifest中的technical obligations，原executor的无任务Formalizer结果仅说明作者scope不需要公式，provider.raw来自原offline_provider_response，未用Binder后文本。

主执行者将该材料接同一真实DSH链：v01-author-typecheck/build/stage exit0；provider-author-008（带actual Node机器报告），v01-real-provider-author.log exit0，1场景/79456.13ms，author draft为pending_validation；新进程失去旧cap后恢复同receipt，额外发送0；原ledger调用1/费用17，sentinel closed/正式model与network0，假provider端口释放。原archive历史source_manifest标签只在fixture retained，其任务target身份封实际archive digest+原标签，明确controlled fixture，不提升生产事实权威。

当前无运行测试/DSH进程。后续修report对pytest9实际subtests的显式phase记录（失败仍保留），报告artifact限32MiB而worker JSONL仍1MiB，然后继续A01聚合/CLI与V01拒绝/停止、R04完整矩阵。done仍17，无8006调用/独立PASS。

### A01聚合consumer及原CLI接线（持续开发，未提交QA）

原OfflineSuiteReceiptV1新增schema_version=2.0路径（保留显式1.0 legacy），machine_plan/machine_runs/coverage_failure_code；matches对V2重算实际计划、子报告/原日志SHA/长度、所有节点覆盖、parent counts/config/plan/output摘要，不能相信passed或手填labels。新build_machine_offline_suite_receipt从原reports构造，少suite、坏report/source漂移均failed，历史V1不升级DSH许可。pytest9 native SubtestReport显式记录subtest phase并保留失败；32MiB仅用于机器报告artifact，私有worker帧仍1MiB。

新增suite_runner.py，先重建注册plan，再一次执行每个suite；原Python/validator前后捕获，不重发，独立deadline、owned process group timeout清理只让验证failed，不退款领域费用。Node仍由原网络隔离launcher；真实candidate/root从冻结stage metadata与bootstrap现场匹配，public配置闭合，API密钥不进计划/报告。新owner文件加入原validator来源。原record-offline-receipt默认注册legacy计划，显式--pytest-target仍仅partial并前后核engine/validator；dsh-stage04须当前operator bootstrap/candidate且阶段必测文件齐全，缺项启动前拒绝。当前Dsh完整计划仍因实际缺文件而未执行/未通过。

开发验证：a01-subtests-plans.log exit0，15passed/5.92s；a01-aggregate-development.log exit0，16passed/6.57s；a01-machine-receipt.log exit0，34passed/12.69s；a01-cli-preregression.log exit0，34passed/12.57s；a01-original-cli.log exit0，36passed/14.81s；a01-config-closed.log exit0，36passed/14.59s。聚合正例是UNIT engine树上的真实四个pytest节点，不是当前项目全套回执；包含receipt统计伪造、少suite、同label替换命令、源码/validator/config漂移、日志篡改。实际原CLI单节点只给scope partial/1passed/零coverage labels，DSH缺bootstrap实际CLI exit2且不生成回执。实际源码未有完整V2执行证据，runner timeout/执行中漂移及DSH全部Node失败/CLI情形仍需完成。

当前无运行命令/协作者，root继续独写全部共享代码与构建。stage最新v01-author构建尚未包含后续A01源码身份，历史008证明仅限其当时输入；下一次实际DSH须重新冻结当前组成。下一动作补runner实际失败/timeout、CLI聚合与V01负例/R04取消恢复；随后V02及最终全套/独立QA。17/49保持，8006调用0，无PhaseB–F正式集成。

### V01真实正文拒收费用与A01 runner失败检查（持续开发）

原Parser/assessor抛出的WriterContentRejection保持原拒绝原因；只有原worker捕获该拒绝且原账本已有可信usage，才生成kernel-ingest-rejection费用事实并在原invocation_adapter结算。私有RPC不接受domain_rejection许可，不生成领域receipt、不commit正文；格式/绑定/证据门仍原裁决。v01-rejection-python.log：python -m pytest -q tests/integrations/dsh/test_invocation_events.py tests/integrations/dsh/test_task_recovery.py，exit0，26passed/44.78s。

v01-rejection-typecheck/build/stage最终exit0。第一次typecheck因只设candidate而未设对应C2P_DSH_DEV_ROOT被peer核对拒绝；补原规定的两个环境变量后通过，未重装/换peer。真实同一offline launcher的pi-ai-wire.test.ts：v01-real-provider-rejection.log exit0，1passed/75101.10ms，provider-rejection-009/stage04-provider-hma9Qe；实际原Binder拒绝formula_placeholder_missing，task cancelled/receipt null，original ledger call_count1/spent17/pending0/completed_receipt_count0。新worker丢旧cap恢复拒绝task_mutation_closed，模型发送仍C00校准1+正式1/恢复0；cleanup sentinel closed/model0/network0，假provider端口实际重绑定。完整原始机器报告/Session/raw/wire/SQLite/账本和refusal保留。后续仅加断言明确拒绝原因，并补report读取上限，未把本历史PASS回填新source identity。

A01 runner开发反例a01-runner-failures.log：test_dsh_admission.py，exit0，21passed/10.44s，包括实际Popen deadline清理和运行期间源码漂移，UNIT隔离identity不是当前完整suite。当前完整DSH计划仍缺test_serial_writer_e2e.py/cli.test.ts；A01/V02及R04清理矩阵未完成，独立QA未启动，17/49与8006调用0不变。当前root单写共享源码/构建，无协作者在写。

### A01当前legacy实际聚合与V01 Unicode边界开发

新增read_bound_report声明长度必须1..32MiB，只读取length+1快照并核digest，超长/增长/前缀匹配不能触发无界读取或通过；Node artifact同上限，worker frame不变。a01-bounded-report.log：python -m pytest -q tests/integrations/dsh/test_dsh_admission.py，22passed/10.27s/exit0。

原CLI首次执行当前完整legacy-offline/2：python -c 'from code2paper.cli.agentic_run import method_agent_main; raise SystemExit(method_agent_main())' record-offline-receipt --suite-plan legacy --out /tmp/c2p-dsh-stage04-20261004-ud6x5a4s/legacy-plan-011-receipt.json --output-root /tmp/c2p-dsh-stage04-20261004-ud6x5a4s/legacy-plan-011 --timeout-seconds 1800，cwd当前root，a01-actual-legacy-plan.log exit0；四组真实发现报告606passed/77.78s，schema2.0/passed True/failure empty。结束后原consumer matches当前engine/validator为True；只证明legacy具名范围，不准入DSH。后续源码/本文改变后该receipt成为历史绑定样本，不能拿旧身份许可当前入口。

v01-unicode-typecheck/build/stage exit0。provider-unicode-010首次实际链失败invalid_unicode（v01-real-provider-unicode.log，1failed/57730.49ms）；测试将一个UTF-16 surrogate pair切成两个独立JSON delta，使Native Session中出现单独surrogate，严格wire门拒绝；cleanup worker scope true/sentinel closed0/假port重绑定。未放松门，也不将失败计通过。合法正例改为raw tool JSON中的ASCII surrogate escape中途分delta，同时真实HTTP响应write在中文UTF-8字节中途断开；尚待同一实际链复验。独立API只读发现确认Agent.whenIdle/dispose、worker.waitForExit均不证明in-process/远端provider停止；R04未完成，不释放unknown backend占用。仍17/49，无8006调用。

### V01 Unicode合法边界复验与V02准入owner前置

v01-unicode-repaired-typecheck/build/stage exit0（一次root目录npm未指定prefix退出254，改用原npm --prefix integrations/dsh命令后通过；无peer变更）。v01-real-provider-unicode-repaired.log exit0，1passed/76905.92ms；provider-unicode-012/stage04-provider-hRHreZ实际HTTP中文UTF-8分字节及raw JSON ASCII surrogate escape分delta，原raw/Native Session/strict parser/receipt保存同一中文、emoji、组合字符与换行。typed blocked，original fees17/call1/pending0，新worker恢复0新发送；机器报告和cleanup同根保留。没有给单独surrogate放宽strict gate。

协作者python_host_e2e只写新test_serial_writer_e2e.py，已归还写权，未执行测试/构建/stage。该Python入口拟调用同一实际offline launcher和host-provider.test.ts，再核原机器报告与receipt/预算/恢复/cleanup；当前待主执行者实际执行，不称V01全范围PASS。

新增host_admission.py只读owner，绑定原I01实际composition和A01 schema2.0 dsh-stage04-offline/2真实机器覆盖，对candidate/runtime/effective config/bootstrap/engine/validator/source/report/log重核；平行true具名unsupported，artifact限32MiB、错误不回显bootstrap/secret，返回model_execution_authorized=False，不是live许可/模型permit。已加入原validator来源闭合，compileall及diff-check0；尚待V02 TS操作入口、正负测试及最终DSH全计划回执。该新增文件尚非完成CLI，也未启动模型。当前所有命令已返回，StageA仍in_progress/17done，无8006调用。

### V01 Python入口实际执行结果

主执行者审核并运行新test_serial_writer_e2e.py：python -m pytest -q -s tests/integrations/dsh/test_serial_writer_e2e.py（外层auto-review准许嵌套bwrap命名空间，内层禁网/源码runtime只读不变），v01-python-actual-host-e2e.log exit0，1passed/82.91s。完整链产物/tmp/c2p-dsh-python-e2e-hxvqvlez，实际launcher argv/Node metadata/native节点/manifest均重核，一次C00校准+一次正式blocked Writer、原receipt/费用17/恢复0新发送、cleanup guard closed0及假port释放。仅当前blocked入口场景，不给未测矩阵或CLI完整PASS。协作者写权已释放；当前无运行命令。下一步V02真正opt-in操作入口和准入正负情形，R04父退子活/unknown/迟到完整矩阵仍缺；阶段A6项in_progress，17done不变。

### V02 opt-in实际接线与持久恢复输入检查（持续开发）

新增cli.ts：必须experimentalDsh=true，默认parallel=false/true unsupported；admit命令调用原Python host_admission只读进程，对schema2.0完整dsh-stage04覆盖/当前组成配置重核，坏回执先于bootstrap读取具名拒绝。executeExperimentalWriter真实接startKernelWorker→initialize→prepare→KernelAuthority→runSingleWriter→close，不伪造claim/预算/assessor；准入不是模型许可或live授权，默认产品驱动未切换。当前可执行命令只有只读admit，完整operator run boot入口仍待接通及正例验证，不能登记V02完成。

协作者cli_negative_tests只写新cli.test.ts并交还写权：21个实际staged Node executable的选项/legacy/partial/missing/malformed回执拒绝，检查输出及任务根无变化；未启动测试/build/stage，不能计QA。root独写所有协议、validator、TS/build。TaskStore恢复读取新增JS安全fence边界、state/grant_mode集合及严格claim_lineage格式/数量/唯一性检查，阻止坏持久库换发权限；六个实际SQLite篡改/重开拒绝反例已落地，待聚焦执行。上述文件已compile/typecheck局部检查，尚无完整current CLI/DSH通过证据。

任务板仅V02进入in_progress，现在17done/7in_progress/25planned；StageA完整验收未提交，live0。下一动作冻结当前输入，先跑原task/recovery/admission及CLI可执行负例，再接operator完整run与剩余provider取消/unknown矩阵；最终A01必须重跑当前完整计划。

### V02实际拒绝矩阵及完整operator run接线（持续开发，尚待验证）

v02-admission-task-inputs.log：python -m pytest -q tests/integrations/dsh/test_task_recovery.py tests/integrations/dsh/test_dsh_admission.py，exit0，36passed/17.76s。v02-entry-final-typecheck/build/stage exit0；同一offline launcher实际staged cli.test.ts在cli-refusals-013生成机器报告，v02-actual-cli-refusals.log exit0，21passed/9368.08ms。legacy/partial坏回执在bootstrap之前拒绝，选项非法/parallel=true及unknown均无新任务根产物；这是实际只读admit命令负例，不是完整V02正例。cli.ts与execution-policy.ts新增已落地裁决源进入原validator bundle；旧证据按其旧绑定解释。

后续补齐可执行run及scripts/dsh_dev.py writer实验命令：离线原owner先重核A01/I01和冻结operator launch；启动器保持unshare-net，原prepared task_root可写，bootstrap/launch/receipt与各实际子报告/日志在任务bind之后逐文件只读覆盖，新output为task根fresh direct child。Node实际Loader/profile/公开PiAi adapter→原executeExperimentalWriter闭环，offline policy在operator overlays之后应用，Web URL打印关闭。原bootstrap严格closed字段仅添加可选版本化DshHostLaunchBindingV1；新CLI run必须有该绑定且A01 bootstrap_digest覆盖其bytes_digest/path/length，原worker启动再读固定source核bytes。未给旧bootstrap或offline回执增加live授权，原默认产品路径不改。

当前新增run/worker metadata/launcher读写边界还未实际验证；一次TS类型失败是公开AdapterRegistrationHandle被窄化成普通disposer（缺replace），改为原公开ReturnType后最新typecheck0。新增worker绑定source变化/长度/摘要/extra field拒绝和readonly input边界检查待执行。此前scope读取曾写错bootstrap.context.scope及run_root，已按原bootstrap.scope/artifact_root修正，不能将尚未跑的run当作通过。下一步冻结并验证该批，再补operator准备/最终A01与实际完整CLI正例、剩余R04/V01矩阵。17done/7in_progress/25planned，live0。

### V02最新入口检查、A01有界artifact与真实取消场景（持续开发）

上一批 v02-operator-bootstrap-boundaries.log：原worker protocol/task recovery/admission/dev isolation聚焦命令 exit1，91passed/2deselected/1failed（98.44s）。失败为test_frozen_runtime_has_no_development_dependencies选择旧default root，其package-lock与历史安装身份不匹配；没有重装或改default。只对该失败节点设置规定candidate与C2P_DSH_DEV_ROOT重验，v02-selected-candidate-runtime.log exit0，1passed/4.46s。v02-operator-final-typecheck/build/stage exit0；同offline launcher的cli-operator-refusals-014，v02-operator-actual-cli.log exit0，22passed/9577.91ms，包括run缺冻结launch拒绝。完整operator run正例仍未验证，不登记V02完成。

本轮suite_runner改为1MiB分块流式完整摘要，保留真实artifact长度，原consumer仍拒绝>32MiB。读前/后inode,size,mtime,ctime及路径身份核对，非regular/增长/替换均失败，不使用截断前缀冒充完整日志。host_admission新增nested composition类型/绝对路径检查；writer launcher在原准入后有界重读bootstrap/receipt并匹配准入摘要。a01-streaming-artifacts.log首次exit1，29passed/2failed：流式hash遗漏原digest_bytes的sha256:前缀，真实receipt consumer正确拒绝；修正前缀后a01-streaming-artifacts-fixed.log exit0，31passed/10.17s，包括实际runner成功/timeout/source drift、超大日志完整记录但消费拒绝及坏nested结构。

后续runSingleWriter新增内部AbortController，异常先abort实际delegated transport再task.cancel，不把dispose/idle视为provider停止。新增serial-writer-cancel实际链场景：仅隔离fake HTTP provider，C00后正式请求到达即取消且provider未给usage/terminal，拟验证新worker读取cancelled、无receipt、原pending预留不变、恢复0发送和Python出口哨兵。尚待typecheck/build/stage和真实launcher执行；不宣称R04/V01全矩阵或独立PASS。当前root独写共享代码、无其他写者，17done/7in_progress/25planned，8006调用0。

### R04实际取消复验及operator准备入口

r04-cancel-typecheck/build/stage exit0。首次launcher因传相对tests路径从repo cwd解析不存在，在启动前exit1（provider-cancel-015，没有模型/Host）；改实际绝对路径后provider-cancel-016真实链exit1，1failed/62148.27ms：已完成正式HTTP到达/取消/原pending保留，但恢复无raw时给kernel_receipt_invalid。原预算门没有放行。root修recoverStoredOutput为缺captured_source时kernel_recorded_output_not_ready，不造raw或重发。r04-cancel-repair-typecheck/build/stage exit0；provider-cancel-017真实同链exit0，1passed/63406.01ms（r04-actual-provider-cancel-repaired.log）。原ledger call_count1/pending_input_tokens6602/spent0/completed_receipt_count0/provider_usage_status partial；正式请求到达后abort，fake provider仍监听，任务cancelled/receipt null，新worker丢cap恢复具名不可恢复、ledger逐字段相同、额外send0。结束worker scope独立wait true、guard closed/model0/network0、fake port实际重绑定。未以client abort/worker done当provider静止，也未释放unknown占用。

按长期模块授权拆出稳定独立tests工作面，协作者provider_scope_process_tests只新增provider-scope.test.ts后释放写权，没有执行/build/stage。两条真实ctx.subprocess场景拟检验父正常退出而同范围survivor heartbeat仍增长、独立wait false，再terminate/abort后全新cleanupSignal true。该fixture只证明本地owned helper范围，不证明远端模型provider；API throw/忽略signal等场景仍未覆盖。root审核文件及r04-scope-operator-typecheck exit0，尚待实际执行。

root为完整CLI正例补测试专用operator preparation模式（正常suite默认关闭）：同Host/C00形成真实projection后证明task_not_prepared，冻结launch并将其SHA/length绑定原bootstrap，关闭初始worker；等外部原A01真实全套receipt后调用实际staged cliMain(run)，重新Loader/公开PiAi/原worker闭环，任务epoch从准入后prepare开始。实际config/overlay/profile/offline policy进入I01额外文件来源，test-only sentinel严格只准原worker及host_admission两个固定owner且禁止Python模型/socket。准备模式尚未实际跑，不伪造full passed receipt，不称V02正例完成。DSH固定必需Node集合新增取消/范围测试，最终计划仍须在源码冻结后真实生成。当前无运行测试或协作者写权，下一动作build/stage后执行真实范围场景，再准备operator+最终A01；StageA全矩阵/独立QA仍待，17done/7in_progress/25planned，live0。

R04范围实际执行补记：r04-scope-operator-build/stage exit0；同offline launcher provider-scope-018/r04-actual-managed-provider-scope.log exit0，2passed/2933.06ms。原observations分别记录direct_outcome正常0、wait false/signal aborted、全新cleanup wait true/signal非aborted，heartbeat实际增长再停止；无模型/worker或退款声明。并行独立原Python协议/准入回归a01-operator-protocol-regression.log exit0，64passed/87.06s。上述测试期间无源码/文档写入；root已释放读集，所有命令退出。

准备模式通过launcher新显式test --operator-package传递私有开关，闭合为当前candidate+fresh output+单个actual host-provider.test.ts，普通suite不继承任意C2P测试环境，也不会等待外部receipt。该新flag尚未执行；下一动作先完成operator package准备与实际原A01全计划，在同一离线网络命名空间里跑staged cliMain。外层scripts writer命令仍需单独验证readonly mounts及完整操作路径，不能把同进程cliMain测试冒充外层命令通过。StageA其余错公式/atom/ref/漂移及API异常清理矩阵也仍未完整。

### 当前A01完整计划首次启动及安全停机（未通过）

operator-package-019同实际offline launcher --operator-package，已真实C00、task.read拒绝task_not_prepared、写operator-ready.json/launch绑定并关闭初始worker，未启动正式Writer epoch。根/tmp/.../operator-package-019/stage04-provider-mUHyx7，v02-operator-package.log保留原ready路径。原record-offline-receipt --suite-plan dsh-stage04 --candidate 0.2.0-rc.1+loop-origin.1 --dsh-bootstrap该root/bootstrap.json --out该root/operator-offline-receipt.json --output-root该root/a01-full --timeout-seconds1800启动当前注册完整计划（a01-current-full-dsh.log），Python已真实执行至63%后由owner终止，不形成通过回执/完整机器报告，不把进度计验收。

运行期间只读检查发现旧H01/H02等Host fixture沿共享offline.patch boot，但未覆盖runtime web-app默认printUrl=true，会打印临时认证URL。在Node套件启动前终止本轮，未改冻结来源来让旧计划通过。第一次默认sandbox进程扫描看不到已escalated的owned进程；随后auto-review批准按精确本任务receipt/report/runroot绑定在外层终止owned runner/pytest process group及两个operator Node进程。runner terminal143，operator launcher terminal1，正式模型send0、任务仍未prepare；不能把异常退出当范围/费用释放证据。

释放读集后共享offline.patch只增加web-runtime printUrl=false/openBrowser=false，原所有模型/retry/title/telemetry禁用保留，原日常profile未修改。原CLI DSH bootstrap与stage读取也已复用原准入owner有界reader/类型检查。旧operator包绑定此改动之前源码/overlay，必须新鲜准备，不能拿019续当前组成或修改其回执身份。下一动作检查共享overlay及launcherflag，再新root准备、重新完整A01和实际CLI；R04/V01剩余矩阵、外层writer挂载正例及独立Gate-R/V仍待。17done/7in_progress/25planned、8006调用0、PhaseB–F未正式集成。

共享offline overlay修复后，原真实loader.test.ts+provider-scope.test.ts通过同launcher复验：offline-overlay-020/offline-overlay-actual-loader.log exit0，12passed/6289.71ms。原profile/staging字节保持、模型出口0、父退子活与独立cleanup仍通过；日志检查无dsh web:认证URL输出。原bounded CLI接线test_dsh_admission.py再次exit0，31passed/10.21s（a01-bounded-original-cli.log）；compileall及diff-check0。全部本轮tool handles已返回，无协作者写权。新operator package/完整DSH计划须用下一fresh根重建；019未通过且已终止，不能复用其当前身份，未生成准入成功或正式Writer发送。

### A01当前完整DSH实际结果与收敛修复（持续开发）

新operator-package-021/stage04-provider-Cq7fX6（v02-operator-package-current.log）实际C00及task_not_prepared检查通过，私有准备模式闭合冻结launch，不提前启动300s epoch。原CLI完整dsh-stage04-offline/2，a01-current-full-dsh-second.log terminal1：Python1020passed/466.91s，机器报告实际selected/discovered各1020、deselected0；Node实际200场景，199passed/1failed/0skip/0cancel。真实blocked/draft技术及作者页/research_required/Unicode/取消、三崩溃点lost-cap新worker恢复均在同一当前冻结代码运行。取消原pending6602/spent0/receipt null/恢复0send，其余正常样本费用17/pending0/恢复0send；非法内容样本领域receipt null但费用17结算。

唯一Node失败是dev/toolchain/sandbox.test.ts旧断言C2P_DSH_RUN_ROOT必须candidate/run，拒绝了已交付的fresh /tmp输出；实际网络/只读条件尚未执行到该断言后。原builder保持fail-closed，receipt passedFalse/coverage_failure_code offline_suite_binding_invalid。等待的operator实际cliMain run因此先于bootstrap prepare具名host_admission_full_dsh_receipt_required拒绝（terminal1），原正式task未启动/发送0；不手改回执、父计数或过滤失败。完整报告/原日志/每个真实场景结果都保留，未给Gate-R/V PASS。

读集全部释放后，root修sandbox测试为严格检查实际selected绝对canonical root，默认仍candidate/run；显式输出必须/tmp/task目录，actual root writable、源码runtime readonly、scrubbed env及only lo断言保留。另补原host_admission要求launch config_path/每个overlay都直接属于原I01 files读集，不能用有效composition_digest替未冻结Loader输入授权；当前正例已冻结这些实际输入。新增合法冻结/不同config/不同overlay/相对路径/坏类型反例。该批待typecheck、原admission聚焦及actual默认/显式输出两条launcher复验。当前无live测试/协作者写权，下一新scope才能生成当前A01成功回执；021属于失败且历史输入绑定，未完成CLI正例。17done/7in_progress/25planned，8006调用0。

该批修复复验：a01-fresh-root-typecheck.log exit0；a01-launch-read-set.log（test_dsh_admission.py）exit0，32passed/10.20s；真实launcher同sandbox.test.ts显式输出sandbox-explicit-022及原candidate默认run分别exit0，2passed/162.09ms及2passed/159.31ms（a01-actual-fresh-root.log、a01-actual-default-root.log）。原source/runtime W_OK拒绝、credential/proxy scrub、only-lo、local fixture server均执行并保留。读取失败021原dsh-tasks.sqlite3（mode=ro）实际tasks count0，确认拒绝在任务创建前；未将失败回执改passed。

当前所有计划/Host/聚焦工具handle均terminal，无独立QA读集/协作者写权。原完整021虽然Python1020和Node其余199行为已观察，仍整体失败，不是当前修复代码的成功准入。源码和文档修复后必须新的operator scope/A01机器报告，不能从旧报告改argv/计数/身份凑成功；剩余V01/R04矩阵及外层writer正例继续按原阶段交付。17/49不变，未处理具体L01 live准入。

### Stage A recovery and real Host fault matrix (2026-10-04, continuing)

- Added `tests/integrations/dsh/test_host_recovery_boundaries.py`: real private worker/process ownership, 14 parent cases and 56 prepared-read-set subtests. Explicit UNIT projections/Session and injected adapter observations do not prove provider arrival or native Session behavior. All 14 bound references are damaged/restored at reserve and adapter-entry; original fees remain unchanged. Includes wrong epoch, cancelled original epoch late fee-only settlement, composition drift, and authorized original receipt replay.
- Initial command `python -m pytest -q tests/integrations/dsh/test_host_recovery_boundaries.py` exited 1: 12 passed, 56 subtests passed, 2 failed in 76.90s. Original replay still unnecessarily read the damaged private section to locate its reservation.
- Repaired original `invocation_adapter.py`: local recorded request resolution uses the durable captured request ID and its original plan row, validates claim lineage/contract/epoch tuple; reserve and adapter-entry still require complete current read-set/composition. No second fee ledger or weakened send gate.
- Regression `python -m pytest -q tests/integrations/dsh/test_host_recovery_boundaries.py tests/integrations/dsh/test_invocation_events.py` exited 0: 32 passed, 56 subtests passed in 115.18s; `/tmp/c2p-dsh-stage04-20261004-ud6x5a4s/a-recovery-boundaries-repaired.log`.
- Extended actual Host/provider fixture and six wrappers: foreign formula package, foreign atom witness, cap drift, zero Writer call budget (original frozen profile/envelope), and missing/corrupt original raw capture. Provider arrival counts distinguish C00 calibration from formal dispatch. Raw damage cannot grant domain completion or clear original occupancy simply by restoring bytes. These new Host scenarios have NOT yet passed execution.
- Registered the new Python recovery file and all six Host fault wrappers in the mandatory full DSH offline plan. Current selected candidate typecheck/build passed; stage pending at this record. No full A01 replacement receipt, independent Gate-R/V, L01 authorization, live probe, or Stage A completion. Task board remains 17/49 done.

- Actual selected-candidate stage exited 0. Six real Host tests via original `scripts/dsh_dev.py test` in fresh `host-fault-matrix-023` exited 1: 3 passed / 3 failed, zero skip/cancel, 356.88s. Foreign formula, raw corruption, and raw absence passed. Atom was correctly rejected by original `publication_paragraph_transaction_failed:unknown_atom_witness` (test expected a different owner name). Cap drift and zero budget had actual native Session errors `writer_cap_mismatch` and `unified_invocation_budget_exceeded:calls:writer:1>0`, with no formal HTTP arrival; Host masked both as `host_single_terminal_required`.
- Repaired `workflow-driver.ts` to retain the first actual trusted pre-request/adapter gate error when native Agent resolves without a terminal. No domain authority comes from this error; the same cancellation and cleanup owners apply. Corrected atom expectation to the actual original transaction owner. Added actual Host composition drift of the per-task frozen config, refusing before claim/provider, restoring config only for a fresh reader. New seventh wrapper mandatory in A01. Repair rerun pending; full A01 and independent acceptance still incomplete.

- Fresh actual Host repair run `host-fault-matrix-024` exited 1: atom/cap passed; budget/composition failed (183.88s). Budget error originates at the real Python `reserve`, after pre-request material recording; extended the same private Host error retention across actual recorder reserve/dispatch calls. Composition refusal correctly left the durable task in `outbox` (no claim); corrected the expected state from `prepared`. Strengthened cap scenario to mutate the actual native stream request's maxTokens after C00, retaining the original immutable projection. All three boundary cases rerun pending; no gate completion.
- Mandatory-plan regression `python -m pytest -q tests/integrations/dsh/test_dsh_admission.py` exited 0 (32 passed, 10.21s). A preceding mistaken command also named nonexistent `test_offline_cli_plan.py`: exit 4/no tests; not counted as verification. Logs `a-fault-plan-admission*.log` preserve both.

- Fresh three-boundary run `host-fault-matrix-025` exited 1 (109.08s): zero budget and actual frozen config drift passed. Stronger cap test failed because the actual native GenerateOptions object is immutable; attempted property assignment threw before the accounting seam. This is test construction failure, not proof of a cap-gate pass. Replaced that injection with the public `agent/request` configuration waterfall returning a changed cap; actual native stream and frozen projection remain observable. Cap alone pending rerun.

- Actual public waterfall cap run `host-cap-waterfall-026` exited 0: 1 passed (original launcher, real candidate, private worker, real native stream). Frozen cap is 4096, actually observed formal native request cap is 4095, Host returns original `writer_cap_mismatch`, provider arrivals remain C00-only (formal sends 0), no reservation/cost/receipt, fresh worker reads cancelled state. Typecheck and patch hygiene exit 0. All seven new Host fault behaviors now have actual passing evidence across their bound runs; complete current A01, full static regression, executable positive CLI and independent whole-Stage-A Gate-R/V still pending. No 8006 probes or live calls.

- Full static attempt 027 was interrupted with exit 2 after a launcher mistake: --basetemp parent directory had not been created, so tmp_path fixtures raised FileNotFoundError (63 passed, 193 fixture errors, 3 live tests deselected, 66.45s). Only the owned pytest process matching exact argv and unique 027 path received SIGINT; its tool handle is terminal. No result is accepted from this attempt. Fresh 028 parent is explicitly created before the corrected full static run, with live_llm excluded and selected candidate environment.

### Stage A current full static checkpoint (2026-10-04)

- Corrected full static command (selected candidate environment, fresh explicitly-created parent): `python -m pytest -q -m 'not live_llm' --basetemp /tmp/c2p-dsh-stage04-20261004-ud6x5a4s/phaseA-static-028/pytest --junitxml /tmp/c2p-dsh-stage04-20261004-ud6x5a4s/phaseA-static-028/static.xml`. Exit 0: **4448 passed, 3 deselected, 7 warnings, 68 subtests passed in 1329.87s**. Log `a-current-full-static-corrected.log`; actual JUnit under `phaseA-static-028`. Deselection is explicit live_llm exclusion, not a full DSH coverage receipt. The earlier 027 fixture-directory failure remains separate and rejected.
- `python -m compileall -q src tests` exit 0; `git diff --check` exit 0. No model probe/call. A read-only exact-argv process diagnostic found no matching process because pytest had already exited; no signal was sent by that diagnostic and no quiescence/model claim was inferred.
- `/tmp/c2p-dsh-stage04-20261004-ud6x5a4s/phaseA-seven-fault-evidence-index.json` binds individual passing historical runs for all seven faults to original result/cleanup/provider-observation bytes and lengths. All seven actual cleanup records observed worker scope exit and rebind of their own fake provider port, Python sentinel model/network calls zero. Raw damaged results retain their original pending fee/reservation and no domain receipt; known content refusals settle cost but do not publish accepted domain output. These are scoped observations, not remote-model scope proof or independent gate completion.
- Next is a fresh actual original full `dsh-stage04` A01 receipt and bound positive CLI package. Source/docs remain frozen during those identity-sensitive runs. Old full 021 failed receipt cannot be reused. Complete Stage A independent Gate-R/V remains pending; task board **17/49 done** unchanged, long module active, Stage B L01 and formal C–F integration unadmitted.

### A01 full attempt 029 and executable proof repair

- Fresh original full dsh-stage04 attempt 029 exited 1; genuine receipt passed=false, exit_code=124, offline_suite_binding_invalid. Python machine run exited 0 (1035 passed, 56 subtests); Node run exhausted the shared 1800-second whole-plan deadline after 186 observed passes, before raw_missing and final summaries. This is incomplete coverage, not a passing stage. Engine, validator and composition before/after remained identical; original operator admission refused (exit 2) and its SQLite tasks count remains 0. Both runner/operator handles terminal; no unknown occupancy was released from elapsed time or process exit. Bound originals remain under operator-package-029/stage04-provider-TNC748/a01-full.
- Read-only CLI scope audit (phasea_cli_scope_audit) distinguishes direct cliMain operation contract, actual executable entry, and outer writer mounts. Replaced the operator fixture function call with asynchronous actual staged Node cli.js invocation, observing OS exit code, original receipt and fresh-worker readback while its own fake HTTP remains responsive. It preserves unshare-net and key scrubbing; no arbitrary environment forwarding to the outer launcher or NODE_OPTIONS injection. The outer writer end-to-end positive is not claimed by this fixture.
- Operator preparation wait increased from 2400 to 4800 seconds solely to allow a complete original offline suite. Next full-suite total harness deadline is 4200 seconds (original CLI default 7200); task epoch/300-second Writer deadline, usage budgets, retry zero, mandatory discovery and fail-closed admission unchanged. Current test change requires new source binding/fresh package and receipt. Independent whole-stage Gate-R/V and L01 remain pending; count remains 17/49.

- Actual physical operator mount test via selected-candidate pytest exited 0 (1 passed/25 deliberately unselected, 2.01s), a-actual-operator-mounts.log. Inside real bubblewrap, all five task-root input/report/log files reject append with EROFS, own probe output writes successfully, repository/runtime readonly and network only lo. This proves mount boundary only, not outer Writer domain execution.
- API-fault injection and executable negatives in fresh host-wait-cli-030 exited 1: 22 executable negatives passed, cancellation test failed solely on its new resend refusal expectation (task_claim_held observed, expected task_mutation_closed). Actual injected wait error rejected close and retained pending6602/spent0, fake provider still listening; original claim remains held and blocks fresh claim before mutation-state check. Corrected test to original task_claim_held owner; rerun pending. Actual provider quiescence is not inferred from API injection or worker exit.

- Corrected actual cancellation/wait-API-fault run host-wait-fault-031 exited 0 (1 passed, 0 failed/skipped/cancelled, 66.38s), a-wait-fault-corrected.log. close throws under injected wait failure with its own fresh bounded cleanup signal; original fee state remains pending6602/spent0 and receipt null, original claim refuses resend, new worker settlement-only recovery sends zero. The real fake provider stays listening/unfinished until separate fixture-owner cleanup; cleanup of worker/helper ranges is not remote-model proof. Prior 030 expectation failure is retained separately.
- All current tool handles and scope reviewer are terminal/released. Freeze current source/docs for fresh operator package 032 and full A01 at total suite timeout4200 seconds. Actual executable positive is a separate same-frozen-code operation result after original A01 admission; normal suite discovery is not claimed as execution of private operatorMode. Full static 028 is historical full-static evidence of production changes; subsequent additions are test-only, with current full A01 covering all altered tests. Complete independent AT matrix and whole-stage Gate-R/V remain required. No live model authorization/probe or later-stage integration.

### Stage A independent review and mandatory V02 coverage repair

- Fresh 032 original full A01 exited 0: Python1036 passed/56 subtests (546.33s), native Node207 passed/0 fail/skip/cancel (1324.66s), original receipt1243 passed, engine/validator/composition before/after equal. Separate actual staged cli.js run OS0 completed full original admission/Host, task epoch after admission, C00 calibration1/formalHTTP1, original blocked receipt and fresh-worker readback. Source pin c565d75054928cb4498885b0bd919978b68050d771d2a0216fb71a7193c60566, validator82476b1d399bc3fc165f4501e0f2dabe5e668df524c5eada47429c8031a93724. External finalized package phaseA-submission-032 indexes1379 artifacts; its first external indexing attempt failed on metadata rows without type, repaired as report-format handling only, then exited0. No production source changed during the package.
- Independent review /tmp/c2p-dsh-independent-stageA-20261004-rv/review.md: **Gate-R PASS; Gate-V CHANGES_REQUESTED**. Independent Python82+56subtests, nativeNode28, actualoutermount1 all exit0; whole source/validator/composition and1379 evidence items stable. Only finding QA-V02-COVERAGE-1: actual CLI positive was outside final A01 machine plan, so missing/failed positive would not invalidate its passed flag. All reviewer handles terminal, owned verification processes0, complete read-set explicitly released. Root accepts and repairs; 032 remains its original historical scope/identity, not promoted or rebound. Whole-stage A not complete; board17/49 unchanged, no live grant/probe/C-F.
- Repair decision: retain normal entry full-final-receipt-required. Add a separately named complete core verification scope and narrow offline qualification entry, bound to actual OS network namespace and frozen loopback provider plus original registered launcher/Host/fee/domain chain. Core proof cannot grant normal entry, live or final Gate-V. Original suite owner starts actual operator preparation, runs Python+Node core, records core evidence, waits for actual executable qualification/report/ledger/reader/cleanup, then aggregates **all three actual runs** into final stage receipt. Final plan/consumer must reject missing/failing/skipped/tampered/foreign CLI run, output, ledger, source or cleanup. No test-env authority, stub admission or bare operator-result audit node. Modified owner/validator require fresh source-bound core/operation/final execution; old032 is not reusable current admission.
- Implementation ownership remains root for shared Python protocol/validator/plan/runner/CLI parent; TS CLI/fixture may be delegated only after concrete interface is recorded, with no shared build/stage writes during tests. Production runtime/SDK/sampling are unchanged by this repair. Current L01 profile compatibility/tokenizer differences remain unverified and unapproved; prepare concrete scope only after Stage A closure.

### Stage A / V02 independent finding repair — 033 implementation, verification pending

Independent 032 verdict remains Gate-R PASS / Gate-V CHANGES_REQUESTED (QA-V02-COVERAGE-1), bound to its unchanged historical artifacts. Reviewer released all input files. Current repair implements registered `dsh-stage04-core/3` and `dsh-stage04-offline/3`: the original CLI owns fresh isolated preparation, captures actual parent network namespace, executes the complete core suites, writes a genuine original core certificate, and waits for the actual staged `cli.js qualify` process and native Node machine report. The final plan requires Python, Node and node-cli runs. Normal `admit`/`run` still require the final scope; core qualification additionally requires a distinct actual OS network namespace with loopback only and frozen literal loopback provider routes. Neither certificate is a model authorization.

New original validators `qualification.py`, `operator_evidence.py`, `operator_suite.py` are registered only after landing. Final aggregation binds exact launch/ready/bootstrap/core/result/stdout/stderr/sentinel/cleanup/database bytes plus complete original run and budget dependency trees. It reuses the original budget reader and a read-only TaskStore observation using the original metadata/row guards/decoder; observation does not create task stores, leases, journals or grants. Missing executable coverage, source changes, incomplete/tampered manifests or unfinished native outcomes remain failures. Local cleanup evidence does not prove a real provider stopped or refund unknown work.

Observed this repair: focused `python -m pytest -q tests/integrations/dsh/test_qualification.py tests/integrations/dsh/test_dsh_admission.py tests/integrations/dsh/test_task_recovery.py` exit0, 77 passed / 18.94s, log `/tmp/c2p-dsh-stage04-20261004-ud6x5a4s/v02-repair-focused-033.log`; includes actual bwrap network namespace test and unchanged database observation test. Initial TS typecheck found TS2322 (indexed JsonValue undefined); fixed by returning already validated qualification scope literal. Subsequent typecheck exit0 (`v02-ts-fix-typecheck.log`), actual build exit0 (`v02-repair-build-033.log`), candidate-only stage exit0 (`v02-repair-stage-033.log`). No default candidate replacement, no L01/8006/probe/model request. No new whole-stage PASS asserted. Task board remains 17/49; Stage A seven items require fresh complete machine chain, regression and independent review before done.

The next fresh source freeze includes this record. Full static and managed Stage A verification outputs will be written only to fresh `/tmp` paths. During those reads no source, docs, stage or composition input edits are allowed; subsequent necessary repairs first require all affected owned readers to finish/release, then create a new bound evidence run. The 032 receipts will not be relabeled or rebound.

### Stage A / V02 033 review blockers, original failed run, and fresh-target repair

The independent early review `/tmp/c2p-dsh-v02-prereview-033/stage04-v02-code-review.md` found four evidence defects plus a cold-entry architectural blocker. Managed 033 was deliberately stopped through only its positively identified owned core subprocess groups; the original manager remained alive to record the actual failure and clean its own operator. Original CLI terminal exit1, final receipt `passed=False`, `coverage_failure_code=offline_required_suite_missing`, no positive final coverage/cold normal result. Exact owned-process/stop records remain under the 033 `/tmp` root. No model run or L01 probe occurred. The separate full static reader finished normally: `C2P_DSH_CANDIDATE=0.2.0-rc.1+loop-origin.1 C2P_DSH_DEV_ROOT='<repo>/.dsh-dev/candidates/0.2.0-rc.1+loop-origin.1' python -m pytest -q -m 'not live_llm'`, exit0, **4479 passed / 3 deselected / 7 warnings / 68 subtests / 1311.93s**, `v02-repair-full-static-033.log`. This result binds pre-034 source and is not the final current qualification. All those readers released before repairs.

Already repaired: final original accounting requires successful status, empty failure codes, completed=1/pending=0, validated usage with no missing receipt/call/token facts, positive spend and no pending tokens; sentinel must have the recognized schema and closed state with strict integer zero counters; the recorded Python owner must equal the frozen launcher. The expensive complete core verification is isolated in one private helper solely to permit bounded semantic UNIT regressions. The top-level final validator tests use real byte/tree identities, original TaskStore APIs, and original invocation-event/ledger APIs, and rebind bytes after semantic mutations so failed status is genuinely reached. `test_operator_evidence.py` exit0 **27 passed / 3.16s**, `v02-semantic-focused-034.log`; its upstream UNIT isolation is not a passing complete certificate or native-run artifact. Actual bad original plan data produces `status=fail` while preserving call1/spent70/pending0, demonstrating the previously missed rejection condition.

The further HIGH blocker is confirmed in the normal CLI path: the 033 final certificate binds the already-terminal qualifier bootstrap. Normal root claim then fails; changing to a fresh task/bootstrap fails the exact certificate/config binding. Terminal replay is not a cold operational positive. The next in-direction repair retains conjunctive gates rather than relaxing fact or receipt matching:

- Original final A01 coverage revalidates its exact immutable source/validator/native suites/qualifier artifact dependencies on every use.
- A versioned explicit stable authority projection contains all registered runtime file/tree identities, versions/protocol, candidate, and the exact qualified model/options/provider configuration/backend resource. Missing or unknown composition keys fail. Target-local launch/config/overlay files and task/artifact/backend roots are not silently deleted from identity; they are fully frozen and validated by a separate original Python target-specific admission, including original full read-set, projection/measurement, budget envelope and empty durable initial state.
- A fresh target requires the exact qualified offline model/options/baseURL/backend resource and an actual distinct loopback-only OS namespace. A different live profile requires the separate L01 permit; neither environment flags nor the Stage A certificate authorize 8006/Qwen.
- The qualifier must exit and complete native reporting/cleanup before coverage issuance. A second fixed isolated package then rebinds the exact same numeric fake-provider port in its fresh namespace, creates a distinct execution/root, consumes the genuine final coverage, and runs the actual normal `cli.js run` with original target admission before task/epoch creation.
- A separately registered cold-use companion binds the coverage, target permit, actual command/native report, original receipt/reader/ledger/provider/ns/sentinel/cleanup. It cannot be recursively included in the certificate it consumes. The original CLI’s overall success requires both complete coverage and this cold normal result; Gate-V evaluates both. Unknown/missing/failed companions remain failed, not Stage A completion.

This repair follows original Python composition, fee and domain owners and preserves the single-request Stage A scope. No shared scheduling, multi-step or Research/Authoring migration is advanced across its prerequisite gates. The task board remains **17/49** until the complete current Stage A package obtains independent Gate-R and Gate-V PASS.

### Stage A / V02 034 fresh-target and cold-use implementation (acceptance pending)

Current repair landed original-owner `target_admission.py`, registered `coverage_use.py`, read-only original artifact/task/backend APIs, and normal CLI `DshTargetAdmissionV1` consumption. The immutable complete certificate is checked twice against original qualified materials; the fresh target separately rebuilds original input/projection/read-set/envelope and requires empty task/budget state. Exactly three owned local files follow the explicit byte/overlay relocation contract; all twenty shared files, three runtime trees, versions/protocol, model/options/provider route/backend resource remain exact authority. The normal fake provider binds the exact qualified numeric loopback port in a new OS namespace. Original `record-offline-receipt` now requires complete final coverage and the separate actual cold normal use; both consume one whole CLI deadline. Native coverage cannot recurse through its own consumer. Missing deadline or companion remains failure.

Observed: focused original owner 034b command `python -m pytest -q tests/integrations/dsh/test_operator_evidence.py tests/integrations/dsh/test_target_admission.py tests/integrations/dsh/test_dsh_admission.py tests/integrations/dsh/test_qualification.py tests/integrations/dsh/test_task_recovery.py` exit0 **143 passed / 19.94s**, `/tmp/c2p-dsh-stage04-20261004-ud6x5a4s/v02-owner-focused-034b.log`; initial034 failed18 predicates because extracted helper lacked local task_root and target wrapper checked launch before core/fullscope. Both repaired; initialfailed log retained. Native TS typecheck/build exit0; build outputs digest `5a75080dd954791480b99d7a918022d2b5ea64648766b5b34f91f0976b1f1444`, candidate-only stage exit0 build receipt `eded0ab3d07b2f0e64aa05dbf9deae4067e7982d4659fad2861f9e9d867562f0`. Current build targets only existing loop-origin candidate; no default cutover.

Actual native CLI negatives: original `python scripts/dsh_dev.py --candidate 0.2.0-rc.1+loop-origin.1 test --output-root /tmp/c2p-dsh-stage04-20261004-ud6x5a4s/native-cli-034b --report-path /tmp/c2p-dsh-stage04-20261004-ud6x5a4s/native-cli-034b/node-events.jsonl <repo>/integrations/dsh/tests/cli.test.ts`, exit0 **25 passed / 0 failed/skipped/cancelled / 11.07s**, `native-cli-034b.log`. Initial filesystem-sandbox invocation denied NETLINK_ROUTE before any native test; original offline launcher reran with approved escalation, preserving unshare-net/read-only mounts. New `test_coverage_use.py`: `python -m pytest -q tests/integrations/dsh/test_coverage_use.py` exit0 **87 passed / 1.12s**, explicitly UNIT schema/rejection contracts, no manufactured complete certificate/native proof.

New target integration test uses actual bwrap loopback-only namespace and original I01/frozen artifacts/input/projection/task/backend/ledger APIs. Only upstream complete-certificate checker is UNIT-isolated; syntax-only upstream fixture is never coverage evidence. Corrected focused six cases exit0 **6 passed / 14.74s**, `/tmp/c2p-target-admission-unit-fixed.log`: readonly admission, model/options/provider drift, actual prepared task and original spent budget refusal; byte and mtime inventories unchanged across admission. Initial sandbox denied namespace creation; next run discovered prepare fixture had not invoked original TaskStore.prepare, repaired only the fixture, retained initial failed observations. These six cases were incorrectly written over the existing39-case untracked test file; recovery is in progress and integration is being separated into `test_target_admission_integration.py`. Existing invariant coverage must be restored before final source freeze.

No current whole-stage acceptance is claimed. Full static033 remains historical; fresh complete current machine chain, cold normal companion and independent Gate-R/V remain pending. Count **17/49**, no L01 probe/model/live grant, no formal C-F integration.

034 pre-review freeze: original39-case test file restored exactly from original worker creation history, 9012bytes SHA256 `8ce532130dc2375357e162cfedefda4704f1ac4440c5903348c91156dc81f713`; preserved `/tmp/c2p-target-admission-original.py`. Integration cases moved to independent file, helper import updated. Actual combined focused `python -m pytest -q tests/integrations/dsh/test_target_admission.py tests/integrations/dsh/test_target_admission_integration.py` exit0 **45 passed / 14.99s**, `/tmp/c2p-target-admission-restored-and-integration.log`. Mandatory original plan includes both plus coverage-use UNIT tests, not invented native proof. Final repaired owner checks `python -m pytest -q tests/integrations/dsh/test_operator_evidence.py tests/integrations/dsh/test_dsh_admission.py tests/integrations/dsh/test_qualification.py tests/integrations/dsh/test_task_recovery.py` with selected candidate env, exit0 **104 passed / 19.95s**, `v02-owner-final-focused-034.log`. Compileall scoped src/tests DSH and `git diff --check` exit0. All focused readers terminal/released. Freeze current code/docs/build/stage for independent target/companion pre-review; source may change only after reviewer explicit release. Fresh whole-chain and full static still pending, no current full Stage A PASS.

### Stage A / V02 034 independent BLOCK and production mount repair

Independent pre-review `/tmp/c2p-dsh-v02-target-companion-prereview-034/stage04-v02-code-review.md` returned BLOCK/REQUEST_CHANGES on frozen ef88e7e/aef85c79 and released all reads before edits. HIGH1: `--tmpfs /tmp` masks final certificate/qualified bootstrap/core/report/output/original run and budget dependencies from the cold normal launcher; focused target UNIT uses another mount shape and did not prove this production boundary. HIGH2: public `dsh_dev.py writer` calls fresh target admission before unshare-net, deterministically failing the OS namespace guard, and then selects bare pyworker instead of frozen guarded launcher. MEDIUM: schema helper tests do not replace real launcher closure tests. These are accepted defects, not successful cold-normal evidence. Full-chain execution deliberately withheld until repairs.

Repair ownership: root owns original Python validator list, coverage transport helper, plan and records; cli_negative_tests owns scripts/dsh_dev.py and affected integrations/dsh/dev/tests/test_development_environment_isolation.py / test_dsh_admission.py tests, with no TS/build/validator edits. `offline_inputs.py` now calls the exact original full-qualified certificate/I01 verifier in the ordinary namespace solely to derive transport dependencies; it grants no target/Host/model/task authority. Enumerated read-only closure includes actual reports/output, every operation evidence file, full original run/budget directories plus bound leaves, and full I01 files/trees. Fresh task admission remains inside the actual isolated normal CLI. No namespace guard or fact gate is removed; the exact frozen guarded launcher is passed to execution. Physical production sandbox tests must prove the closure is readable/readonly and unrelated /tmp hidden while only the fresh task root is writable.

Root bounded transport UNIT verification `python -m pytest -q tests/integrations/dsh/test_offline_inputs.py` exit0 **14 passed / 1.06s**. Only pure closure enumeration and genuine default failed-receipt rejection are tested; transport fixtures have no passing certificate schema/flag, native report or grant. Full native operation remains pending. Validator registration includes actual new helper; mandatory Python plan includes actual new test file. Stage A remains incomplete, count17/49 unchanged, goal active, no L01/model/probe/C-F formal integration.

035 launcher repair observed: original `sandbox_command` now mounts canonical read-only files/directories and rejects directory ancestors of writable target roots; registered normal test launch passes complete closure before output creation. Public writer parent verifies only complete original coverage and immutable target I01/launch transport; no parent target admission. Actual inner normal CLI performs the full original fresh-task/ns gate before Host boot using exact frozen launcher. All shared runtime and qualified proof mounts are readonly; only the owned target root remains writable. Affected worker tests route the complete closure and explicitly fail if parent calls either normal admission function. Worker focused routing4pass/23deselected1.21s; returned all files before root physical run.

Root actual physical/routing command `C2P_DSH_CANDIDATE=0.2.0-rc.1+loop-origin.1 C2P_DSH_DEV_ROOT='<repo>/.dsh-dev/candidates/0.2.0-rc.1+loop-origin.1' python -m pytest -q integrations/dsh/dev/tests/test_development_environment_isolation.py -k 'operator_inputs_are_readonly or writer_parent_transports or node_machine_report_route or scoped_output_bind or actual_operator_mounts'` exit0 **5 passed / 22 deselected / 3.16s**, `/tmp/c2p-dsh-stage04-20261004-ud6x5a4s/v02-physical-closure-035.log`. Real original bwrap retains external/tmp certificate and nested directory under tmpfs, rejects append/create/delete with EROFS, hides unrelated/tmp, observes onlylo and readonlysource/runtime, and writes fresh ownedoutput. This is physical transport evidence only, not fabricated coverage/native Writer success. No TS changes/rebuild since current staged034 bytes; no model/live probe. Complete genuine managed finalcoverage→coldnormal chain and whole-stage independent gates still pending. Refreeze all source/docs/stage after this record for same independent reviewer.

### Stage A / V02 035 runtime authority blocker and 036 full profile/bundle repair

Independent 035 review `/tmp/c2p-dsh-v02-target-companion-prereview-035/stage04-v02-code-review.md` confirmed all034HIGH/MEDIUM repaired, then found a HIGH composition gap: actual `loadProfileDirectory` reads package.json/cordis.patch.yml and the normal executable imports stagedcli/transitive modules not directly bound by prior partial I01; broad DEV_ROOT writable mount could change them after parent staging check. Reviewer released all reads before repair.

Current authority schema explicitly adds `host_profile_package`, `host_profile_patch` and complete `host_profile_runtime`, `staged_bundle` trees; the stable shared projection now binds22files and5trees plus the same3explicitrelocatablelocals. Real Host fixture supplies the actual candidate profile directory and complete staged bundle. Original generic I01 inventories and hashes their actual members; runtime projection compares complete entries/digests, no new filtering or known-answer authority. Offline original sandbox remounts all candidate DSH_HOME/profiles and existing PYWORKER read-only afterDEV_ROOT mutable state bind and refuses writableoutput overriding a protected directory. Setup/install offlineFalse unaffected. Worker ownership remainedscript+devtests only; returned all writes before verification; root owned targetconstants/nativefixture/newdrifttests/sharedvalidator/records. No new fee/domain owner.

Observed `C2P_DSH_CANDIDATE=0.2.0-rc.1+loop-origin.1 C2P_DSH_DEV_ROOT='<repo>/.dsh-dev/candidates/0.2.0-rc.1+loop-origin.1' python -m pytest -q tests/integrations/dsh/test_offline_inputs.py tests/integrations/dsh/test_target_admission.py tests/integrations/dsh/test_target_admission_integration.py integrations/dsh/dev/tests/test_development_environment_isolation.py -k 'not actual_app_sandbox and not development_runtime and not runtime_manifest and not compatibility and not generated_profile and not smoke'`, exit0 **92passed / 2deselected / 25.08s**, `v02-runtime-closure-focused-036.log`. Includes actual physicalprofiles/staged CLI/transitive/Pythonreadonly EROFS and unknownprofilefilecreate refusal, complete closure mount/tmpfs proof, and original I01 genuinebyte drift for profilepackage/profilepatch/stagedcli/transitivemodule/newmodule. Drift tests separately assert treeidentity changed while engine/validator equal so refusal is genuinely runtime-material drift. Target original39 grows to41 via two new stablefiles; six readonlyoriginaltarget integrationcases remainactualnamespace tests. Native TypeScript typecheck exit0 `v02-runtime-typecheck-036.log`; changes are fixture-only on TS side, existing staged034productionlib bytes unchanged, no new default/stage activation.

Actual offline original Host under readonly profiles/Python, fullnewI01, and isolated fakeprovider: `python scripts/dsh_dev.py --candidate 0.2.0-rc.1+loop-origin.1 test --output-root /tmp/c2p-dsh-stage04-20261004-ud6x5a4s/native-runtime-036 --report-path /tmp/c2p-dsh-stage04-20261004-ud6x5a4s/native-runtime-036/node-events.jsonl <repo>/integrations/dsh/tests/host-provider.test.ts`, exit0 **1passed /0failed/skipped/cancelled /78.34s**, `native-runtime-036.log`; actual technicalblocked original receipt with fresh-process recovery. Original reader observed statuspass/call1/completed1/spent17/pending0 and cleanupwritten. This is single native regression scope, not current complete certificate/cold-normal/gate proof. Outputactualroot `native-runtime-036/stage04-provider-T8onl0`. No model/probe/L01, no formalC-F. WholeAcode-review/fullstatic/genuinefinalcoverage→coldnormal/independentGateR-V pending; board17/49 unchanged.

### Stage A / V02 036 Python identity blocker and 037 repair

Independent036 `/tmp/c2p-dsh-v02-target-companion-prereview-036/stage04-v02-code-review.md` confirmed035profile/stagedruntime repairs; sole remaining HIGH: frozen guarded launcher executes candidate pyworker/bin/python while I01 omitted the interpreter alias/canonicaltarget andpyvenv.cfg. Reviewer explicitly released all reads before changes. Added stable `python_executable` from the actual guarded command path and `python_environment` from actual pyvenv.cfg. Original I01 captures alias/path/resolvedtarget/content/symlink facts; exact shared authority now contains24stablefiles/5trees andsame3localrelocation. Original fullclosure resolves and readonlymounts the canonicalbinary/config, while completevenvreadonly protects the invoked alias. Actual nativefixture supplies these real paths, not inferredversions. Foundation hostfilesystem remains originalreadonlyroot.

Bounded UNIT originalI01 drift negatives now separately retarget the Python symlink to equalbytes, mutate canonicalinterpreterbytes, and changevenvconfig. Each asserts changedoriginalfileidentity with equalengine/validator and actualoriginal `composition_drift`, no passingcertificate/Host fabricated. Focused `C2P_DSH_CANDIDATE=0.2.0-rc.1+loop-origin.1 C2P_DSH_DEV_ROOT='<repo>/.dsh-dev/candidates/0.2.0-rc.1+loop-origin.1' python -m pytest -q tests/integrations/dsh/test_offline_inputs.py tests/integrations/dsh/test_target_admission.py tests/integrations/dsh/test_target_admission_integration.py` exit0 **71passed /17.21s**, `v02-python-identity-focused-037.log`. Typecheck exit0 `v02-python-identity-typecheck-037.log`. Source changes are originalauthority/nativefixture/tests; stagedproductionlib034unchanged. Compileall scopedsrc/scripts/tests anddiffhygiene exit0. Refreeze after thisrecord for boundedindependentreview; fullstatic/genuinecompletecoverage+coldnormal/wholeGateR-V remainpending. Count17/49, no model/live/L01probe, noC-Fformalchanges.


### Stage A / V02 037 observed full verification and 038 qualifier transport repair

Frozen037 source72bc7360b967ac3cd0701274f4559e75b4946f77242c5eddc2883af984ce059f / validator67c0a800ed33673659e8c80e4a1641fb86d8636cbe9ac4c2a0f28d579dafbc57 independently APPROVE in /tmp/c2p-dsh-v02-target-companion-prereview-037/stage04-v02-code-review.md. On that unchanged source, candidate-bound `python -m pytest -q -m 'not live_llm'` exit0: 4664passed,3live-deselected,7warnings,68subtests,1329.87s; log v02-final-full-static-037.log under /tmp/c2p-dsh-stage04-20261004-ud6x5a4s. Source and validator after full static matched frozen037 exactly. These are observed static results, not whole-stage acceptance.

Original `method_agent_main record-offline-receipt --suite-plan dsh-stage04 --candidate 0.2.0-rc.1+loop-origin.1 --out /tmp/c2p-dsh-stage04-20261004-ud6x5a4s/managed-final-037-receipt.json --output-root /tmp/c2p-dsh-stage04-20261004-ud6x5a4s/managed-full-037 --timeout-seconds 4200` exit1: complete Python1254passed/56subtests/568.19s and nativeNode210passed/0fail/skip/cancel/1336.681512s. Original operator-core-receipt.json passed=true,exit0,passed_count1464. Actual staged CLI qualify exited2 with host_admission_receipt_stale_or_incomplete; original final receipt passed=false/offline_suite_binding_invalid, cold-normal not executed. No failed receipt is promoted to success. All manager/core/qualifier readers released. Original TaskStore.observe_initial after failure confirms zero prepared tasks; original read_run_budget_state confirms call_count0,spent0,pending0,statuspass. Actual cleanup records worker scope quiescent, own fake port rebound and closed sentinel model/networkcalls0. External phaseA-current-running-037.json now records terminal failure and original observations.

Cause: qualifier sandbox starts before core, overlays /tmp, and originally mounts only operator child. The later core certificate inside operator child is visible but its sibling report/output dependencies are hidden by tmpfs. Repair transports the fixed managed output parent readonly before overlaying its operator child writable. cli_negative_tests owned only scripts/dsh_dev.py and dev isolation tests and released after verification; root owns operator_suite.py, suite_plan.py and plan assertion. --qualification-root is private operator-package-only, canonical existing /tmp direct parent of operator output, excludes /tmp itself. Generic readonly ancestor/equal-output rejection remains; this flag grants no certificate/Host/model authority. Manager and frozen plan bind identical exact qualification-root argv. Full original core validation remains mandatory.

Worker scope UNIT5passed/25deselected/0.11s and actual late-publication bwrap1passed/29deselected/1.08s, exit0 after original sandbox required approved escalation: proof created by parent AFTER namespace start is readable, append/unlink/mkdir on proof parent EROFS, operatorchild writable, unrelated/tmp hidden. Root combined `C2P_DSH_CANDIDATE=0.2.0-rc.1+loop-origin.1 C2P_DSH_DEV_ROOT='<repo>/.dsh-dev/candidates/0.2.0-rc.1+loop-origin.1' python -m pytest -q tests/integrations/dsh/test_dsh_admission.py tests/integrations/dsh/test_qualification.py integrations/dsh/dev/tests/test_development_environment_isolation.py` exit0:93passed/27.10s, qualification-transport-focused-038.log. No production TS changes/rebuild/stage activation. Fullstatic037 remains historical after this bounded launcher/plan/test repair; next complete registered current core covers changed files. Refreeze038 and independently review transport before fresh actual final-plus-cold-normal chain. Whole StageA GateR/V, L01 and formalC-F pending; board17/49 unchanged, no model authorization/probe/call.


### Stage A / V02 038 genuine qualifier success, final cleanup refusal and 039 producer ordering repair

On freeze038 source731917f0df7cbaaaffb66520f59ba1a0f0303042bf391a10e67d76e567a3ed9f / validator4673413ad3e99497006095046dbd063a121a96cc5fec97f8989efb87cae22d5e, original candidate-bound fullstatic `python -m pytest -q -m 'not live_llm'` exit0:4664passed/3live-deselected/7warnings/68subtests/1355.14s; v02-final-full-static-038.log. Source/validator after static exactly match freeze, usable/not unstable. Original managed record-offline-receipt command from037 with fresh managed-full-038/managed-final-038-receipt.json and whole4200s deadline exit1:Python1256passed/56subtests/568.30s; nativeNode210passed/0fail/skip/cancel/1342.23426488s; actual staged CLI qualifier OS0 and native1passed/0fail/skip/cancel (2013.372283743s including core wait). The parent RO proof transport now works. Original final certificate still passed=false/offline_operator_cleanup_unverified, cold-normal not executed. Manager/static/qualifier handles terminal; no failed evidence rewritten. Original readback shows terminal blocked receipt/call1/completed1/spent17/pending0, no supported/Verified publication.

Cause is producer observation order: actual qualifier closed its worker, then the fixture opened a fresh readback worker, saved sentinel.state=installed into operator-result.json before closing readback; after hook and actual sentinel correctly recorded closed. Original validator strictly requires all three final copies closed/equal and correctly refused. Fix ONLY integrations/dsh/tests/host-provider.test.ts: shared closedPythonSentinel awaits original KernelClient.close (positive worker exit; false wait throws), then asserts original sentinel schema/closed/probe_refused/zero model+networkcalls. Actual executable branch observes it after original task/budget readback; common native positive/refusal branch observes it after fresh-worker stored-output recovery. after hook still independently closes Host/fiber/server and proves fake port rebind; no validator, fees, claim, runtime profile, production TS/JS, build/stage or content logic changed.

Focused actual native `C2P_DSH_CANDIDATE=0.2.0-rc.1+loop-origin.1 C2P_DSH_DEV_ROOT='<repo>/.dsh-dev/candidates/0.2.0-rc.1+loop-origin.1' python scripts/dsh_dev.py --candidate 0.2.0-rc.1+loop-origin.1 test --output-root /tmp/c2p-dsh-stage04-20261004-ud6x5a4s/native-close-observation-039 --report-path /tmp/c2p-dsh-stage04-20261004-ud6x5a4s/native-close-observation-039/node-events.jsonl <repo>/integrations/dsh/tests/host-provider.test.ts` exit0:1passed/0fail/skip/cancel/80.555124783s. Original readonly TaskStore/read_run_budget_state verify terminal/call1/spent17/pending0; actual result/cleanup/sentinel all closed and byte-value equal. native-close-observation-result-039.json binds observations. This is a single real native closure regression, not a complete certificate or normal CLI proof. Candidate-bound `npm --prefix integrations/dsh run typecheck` exit0, native-close-typecheck-039.log; gitdiff hygiene exit0. No rebuild/stage required; production artifacts unchanged.

Read-only cryptographic source-delta proof source-delta-before-record-039.json reconstructs original038 engine digest by replacing ONLY current untracked host-provider fixture digest with its original source_files digest from actual038 plan; reproduced source731917... exactly and validator unchanged. Thus every other dirty source entry and HEAD were unchanged before this administrative record. Original038 composition stable24files and all5trees exactly equal current focused native inputs. Current source before record2c7c7f72c7a935faec92085f342438fbefbc854681b8d3b6a9af3fd98dda40de. This proof is metadata-only, never a reissued/granted certificate; original failed038 remains failed. Request independent review of using fullstatic038 as historical unchanged-Python broad coverage plus current focused/native/core evidence, avoiding another redundant broadstatic run for this fixture-only repair. Final gate decides adequacy; no source label/count is relabelled current. New complete managed core+actual qualification+cold-normal still required on039 frozen source.

At explicit later user request, only8006 health/models were read: bothHTTP200, modelqwen38-27b-nvfp4 at2026-10-04T03:59:00Z; runtime-health-user-request-038.json, inference0. L01 scope/caps still need concrete execution package and authorization; existing offline permit grants no live authority. Read-only L01 preparation indexes current locked adapter fields, tracked sampling/thinking differences, original model-owned tokenizer, oneprimary/no retry and stop conditions. Read-only timing diagnosis found cleanup0.236-0.318s and no safe removable fixedwait; identity/RPC hypothesis not profiled, no new tests/signals/modification. Board17/49, wholeStageA GateR/V pending, no formalB-F integration, model inference0.


### Stage A 039 complete actual acceptance; Stage B preparation

Source sha256:1ea010226f4ed4f68619c59c5ebfbda599feed2543de80d9842d57c48d301b76, validator sha256:4673413ad3e99497006095046dbd063a121a96cc5fec97f8989efb87cae22d5e: candidate-bound fullstatic `python -m pytest -q -m 'not live_llm'` exit0,4664passed/3live-deselected/68subtests/1348.07s, log /tmp/c2p-dsh-stage04-20261004-ud6x5a4s/v02-final-full-static-039.log. Original `method_agent_main record-offline-receipt --suite-plan dsh-stage04 --candidate 0.2.0-rc.1+loop-origin.1 --out /tmp/c2p-dsh-stage04-20261004-ud6x5a4s/managed-final-039-receipt.json --output-root /tmp/c2p-dsh-stage04-20261004-ud6x5a4s/managed-full-039 --timeout-seconds 4200` exit0,actualPython1256/nativeNode210/actualCLIqualifier1,originalcertificate passed=true1467, separate fresh cold-normal1 passed; original budget1/1/17/0. typecheck/compileall/diffhygiene exit0,source and validator before/after unchanged. All verification handles terminal. Seven genuine semantic refusals restored originalbytes and originalcertificate stillpasses. Sealed1484-entry package unchanged.

Independent /tmp/c2p-dsh-independent-stageA-039/review.md SHA2561f9bf679a9f84ace25b3ba71e7dd7185fc8b6c13a9edf1dfd9032bc52f09076a independently rechecked allmanifest/originalcertificate/cold-normal, allsevenAT PASS,GateR/V PASS,CLEAR/APPROVE,no blockers,QA-V02-COVERAGE-1 closed. All reads explicitlyreleased. Root records seven done and L01 offline preparation in_progress:24done/1inprogress/24planned, report docs/dsh_execution_20260928/stage04_stageA_acceptance_20261004.md. Administrative updates occur afterrelease and do notrelabel currentworkspace as039source or mutate acceptedpackage. No additionalfullsuite forstatusdocs. L01 concrete driver/input/options/meter/caps/deadline/currentreceipt/authorization remain; inference0; formalC-F await originalgates.

### L01 private development runner and current-admission preparation

Implemented integrations/dsh/dev/l01_worker.py,l01.mjs,l01_launch.py and explicit tests/live/profiles/qwen38_dsh_l01.json within L01 scope. Original Worker/Facade/request-meter injection, task/claim/backend/fee/ingest owners reused; no dependency patch or production DSH rebuild. Original validator source inventory extended with three actual private execution/admission sources. Only identity-source registration extends original production-file scope. New private meter rejects wrong wire/model/origin, unsafe/over-cap counts and host use of offline placeholders. Focused original identity + new meter tests26 passed/exit0. Initial development failures were original fixture import, Loader config-relative dependency resolution, missing explicit public local credential route and OpenAI developer-role mapping; no real API/model calls, original wire validator correctly refused mismatch. Native isolation05 now exit0: actual Qwen adapter wire roles system/user,temperature.6,reasoning_effort low,thinking_token_budget1024,cap4096, no top_p/top_k; calibrationfake1/formalfake1,original blocked receipt and fee settlement. This proof binds its own source before subsequent shared-backend/unique-execution and monitor additions, not final protocol acceptance.

Protocol docs/dsh_execution_20260928/stage04_L01_execution_protocol_20261004.md fixes one primary,0retry/probe/repair/title/compact,input32768/output4096/context131072,request180s,streamidle60s, exact original model tokenizer/non-generating preflight and rawusage/finish/unknown stops. Current DSH sampling differs from Python profile and is explicit; no equivalence claimed. Shared backend root is selected candidate backend-admission, one canonical model endpoint key, unique fresh run execution id. All scope/source/docs work completed before final offline06/packet01/new current full certificate; their status still pending here. Source will remain frozen during those executions. No extra broad fullstatic rerun; required current original registered certificate remains mandatory. Board24done/1inprogress/24planned, inference0; concrete live authorization pending, formalC-F await GateL.


L01 final native06 and packet01 completed exit0 on source0d8591da048e225f563f47a9ce5db8bed435c16300b063e8380c2776ca677982/validatora51a16c8000e79adaaba2e0f4c58a306eef5517a4ac451a0069ba0783b24e611. Native06 original blocked receipt,call_count1/completed_call_count1/spent17/pending0 (completed_receipt_count0 is a distinct original counter); worker closed/probe-refused/model0/network0. Packet01 SHA07905257135e6ad641a114d818f1d100d3f73f43f5c58c88ccfc27082fb7fb22,10boundfiles match,zero epoch/model. Readonly8006 health/models/metrics at05:48:06UTC all200,exactmodel/running0/waiting0/KV0. No tokenize/inference. Self-review identified native06 incorrectly acquired the actual model resource key in shared state; original SerialBackendAdmission deliberately has no release. No old row or fee altered. Correct private dev preparation to isolated-fake resource/local backend for offline formal proof and canonical candidate live-backend-admission/openai fixedkey for actual packets; selected authority provenance explicit fake versus operator-designated runtime. Old seeded row is a proven zero-model isolated fake observation, not a hidden unknown remote run; preserved. Original current admission01 manager interrupted viaSIGINT,exit130; its originalfinally runs before any new source mutation. Preserve incomplete reports. Final protocols now offline07/packet02/admission02; sourcefreeze and current certificate pending these corrected bytes, not relabel old successes.

## 2026-10-04 L01 actual single live FAIL and bounded in-direction repair

Current packet02/current original admission02 completed before the real run: 1476 passed and fresh normal-use exit0, original coverage/current source/validator bindings independently recomputed; source ad6c2522e663b676e89ea755883c3062625496dfe8dbdd62fd45d19781a27acd, validator1b417fb237fab1fd4a9a5a0d9e058739b9a5ef54d01613289d5a91426b7b8b14. User explicitly authorized the frozen one-primary scope. `python integrations/dsh/dev/l01_launch.py live --output /tmp/c2p-dsh-l01-packet-20261004-02 --receipt /tmp/c2p-dsh-l01-admission-20261004-02/receipt.json --authorization /tmp/c2p-dsh-l01-operator-authorization-20261004.json` exit1, session36363 terminal: HTTP200/usage7332input+851output/finish tool_calls, tokenizer7344; source/runtime/model not switched, no retry. Original schema also rejects raw result string with extra trailing brace. OriginalWorker cleanup/sentinel closed, probe refused, model/network0; provider stream ended; post-request readonly health200/metrics200 idle0/KV0. No local receipt/publication. Original read_run_budget_state call1/completed0/spent0/pending7344; canonical backend owner remains original execution. Prior permit consumed, no new live authorized.

Independent Gate-L report /tmp/c2p-dsh-independent-stageB-20261004-01/review.md SHA be075dc242f23ae13587b21feb7cffb5b361a88e11e7e412e0b22da458d7cbeb and recovery-addendum.md SHA5fca5f2e2b0ea21b8f4f69a32f16353023e0e2a74428af0b9e5f540ca4be6d3b: FAIL/BLOCK/REQUEST_CHANGES, all reads released. Manifest29424/655571351bytes matches; task/run SQLite was included, canonical backend needs immutable readback. Board24done/1inprogress/24planned; C-F gate unchanged.

Repair ownership stays original fee/schema/admission/dev owners: l01_worker tokenizer_request mirrors installed chat-template top-level effort override and explicit enable_thinking priority, meter/2 refuses old/1. Actual local AutoTokenizer/local_files_only reproduce old7344 versus7332; draft maps saved wire to7332, API/model0. Native redundant type+oneOf experiment was refused by actual DSH JsonSchemaError before any fake formal request; preserve failed /tmp/c2p-dsh-l01-stream-failure-20261004-01. Replace with supported schema description, keep all3branches/full guard, no string acceptance or response trimming. Export sync also retains original Python's existing optional Session capture field in OutputEnvelope; old schema lacked it. l01.mjs retains first stream failure plus secondary Host exception, creates original readonly owner-readback; l01_launch only permits explicit fault fixture in unshare-net offline mode.

R04 completion gap revealed by actual failure: task_store.SerialBackendAdmission.release_observed_finish privately validates closed single-task scope, original ledger terminal/settlement/usage-bound finish refs and nonempty raw/Session, no pending/failure, atomic exact-owner compare-delete and immutable SQLite release history; stale replay cannot delete new owner. This is original admission lifecycle, not scheduler/second fee ledger. Tests actual original worker/event reducer and reopened SQLite; no live backend release executed. No PID/TTL/private-root workaround.

Exact focused command `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q integrations/dsh/dev/tests/test_l01_meter.py tests/integrations/dsh/test_host_recovery_boundaries.py tests/integrations/dsh/test_task_recovery.py tests/integrations/dsh/test_wire_schemas.py` exit0, /tmp/c2p-dsh-l01-repair-focused-final-20261004.log:107passed/56subtests/107.24s. Earlier53-case command had one composition_source_unstable failure because root edited source while it ran; invalidated that observation and reran on stable source, not a gate repair. Native annotation change then isolated focused meter/branch checks19passed/1.07s, /tmp/c2p-dsh-l01-repair-meter-final-20261004.log. compileall relevant4 files exit0; Node --check and git diff --check exit0. No productionTS changed, build inputs remain unchanged, no rebuild/stage repeated.

`python integrations/dsh/dev/l01_launch.py offline --offline-stream-failure --output /tmp/c2p-dsh-l01-stream-failure-20261004-02` expected exit1 (session74508 terminal): fake calibration1/formal1, exact primary AssertionError missing/duplicate raw usage refused (secondary host_single_terminal_required), actual_model_inference_requests0. Original readbackcall1/completed0/pending6640, taskcancelled/receiptNone, worker closed/refusal sentinel0; isolated fake closed. This demonstrates first-error preservation and conservative fee retention, not compatibility acceptance. Fresh normal offline08/packet03/current certificate03 remain to execute on the post-record frozen source; no claim PASS yet.

Recovery script /tmp/c2p-dsh-l01-recovery-20261004-01/launch.py and recover.py bind SHA-verified old source overlays (no host rollback), preserve exact SSE args/Session and original cancelled task, settlement-only originalWorker RPC, no network/model and no backend release. Automatic approval review rejected the command BEFORE process creation: durable shared ledger settlement/consuming pending budget was not explicitly authorized. Concrete question submitted; no started.json/recovery process, ledger unchanged. Do not retry without explicit answer or bypass rejection. Archived old schema reconstructed only under exact historicalSHA (OutputEnvelope old omitted optional session_capture_ref); source overlays additionally preserve later administrative writes so original composition remains verifiable. New repair not independently accepted; current source/certificate must be frozen and revalidated before any new primary.


### L01 release completion — independent findings and owner repair, 2026-10-04

The source58/validator8fd repair was independently BLOCKed. Report `/tmp/c2p-dsh-independent-stageB-repair-20261004-01/review.md` SHA bddfdaefc3f92b36e78158c9c21bb20ee72a3ada48794c18fc0f0f9ad5099aef: arbitrary caller finish flag/nonempty artifacts, no normal successful release wiring, incomplete usage-status checks, and active task-board authorization reuse drift. Its registered managed03 manager was deliberately interrupted by exact-argv SIGINT after Python1281/56subtests/585.30s passed; original finally exited130 and its complete receipt was NOT produced. Preserve partial logs; no full suite PASS or current admission claimed. Earlier unsafe broad process match found two candidates and asserted before any signal; refined executable+exactoutput match interrupted only PID29847. Taskboard explicitly now says the earlier one-primary authorization was consumed and cannot be reused.

The first private RPC/native Session repair was independently BLOCKed again (`/tmp/c2p-dsh-independent-stageB-release-repair-20261004-01/review.md` SHA0a03c6b8ab5fcf27b45159cd400ed5566bdf2dde1806cd546dc817365ba9c0bc): hidden Facade.authorize reacquire, forgeable recovery observation, nonpersistent quiescence ref, finally first-error masking, and insufficient raw/Session ordering binding. Its focused original71/56subtests/204.84s and TS typecheck passed, but those do not close the findings. Read sets released before the next edits.

Current code keeps the original TaskStore/ledger/Host/gatedAdapter owners. Only an executing live claim can register `backend.observe_quiescence`, after actual Session/raw flush and observed usage, before terminal/settlement. It verifies the real SessionFileV4 streamed args/block/finish/usage/order against original capture/request/fees and persists the artifact ref with original claim digest/fence in the original task row (additive private record; old readonly rows decode None). No arbitrary artifact or recovery claim can mint this owner record. Standard success/rejection consumes the same stored fact through `backend.release`; new-worker recoverStoredOutput reads its bound ref and releases after original settlement/closed task. Unknown/cancel/throw without natural adapter completion keeps occupancy. Facade status/replay/settlement are readonly owner observations; only outbox execute claim acquires, and retirement history prevents reacquiring an old owner. CAS never changes another run's owner. Primary errors remain primary; cleanup/settlement/release errors are recorded as secondary.

Original Worker RPC-focused `/tmp/c2p-dsh-l01-release-repair-owner-focused-20261004-02.log`:11passed/46.84s; after persistence/order repair, `/tmp/c2p-dsh-l01-release-repair-owner-focused-20261004-03.log`:14passed/62.72s (15deselected), covering duplicate RPC release, closed claim refusal, released status/recovery without INSERT, different new-owner safety, recovery cannot mint via artifact.record, real new Worker at quiescence/terminal/settlement cuts, malformed/misbound/incomplete Session rejection. These are explicitly UNIT owner/format checks, not actual provider/native evidence. Four candidate TS typecheck attempts: initial `scripts/dsh_dev.py typecheck` is unsupported CLI syntax (exit2, no runtime); proper candidate-bound npm typecheck02/03/04 each exit0. Relevant compileall/diff hygiene exit0. Native normal/first-error/fresh CLI and final complete certificate remain pending at this record. Added real native assessor-rejection + release-fault regression to mandatory Node plan. One necessary TS build/stage follows changed production Host code; no full-repo static rerun.

The original failed live remains bound to ad6/1b417, one real primary consumed, Gate-L FAIL, original cancelled/no receipt/pending7344/shared backend held. The prepared original-owner settlement-only recovery was rejected before process creation by automatic approval; its specific user authorization remains pending. No recovery, canonical release, second model call, or formal C–F integration has occurred. Additional original source/build/test bytes were archived and verified against the old sealed manifest before replacement; old-runtime verification/recovery must restore the exact old read-only composition, not relabel new source as old.

### L01 current complete certificate04 report identity failure, 2026-10-04

The independent owner-release code review is CLEAR/APPROVE on source b734054a1e54c65d628fdca3452b9597646785ca6f8c73c9cfeee0c46f30c6fd / validator6fe7dc78197d6e9530942c315214eafc96de2f786d631f9f1eef212cdece87ed; all reads released. Original managed complete admission04 session15283 exited1. Actual Python1290/56subtests passed in636.67s and nativeNode211 passed,0fail/skip/cancel in1479.684s, with unchanged before/after identities. Original machine verifier then refused offline_node_duplicate: pi-ai-wire.test.ts and writer-release-failure.test.ts both enqueue host-provider.test.ts:317 with the same invalid_content/receipt name. The waiting CLI qualifier was stopped by the original manager (exit-15), cold-normal not executed. Receipt04 passed=false; no current complete admission is claimed.

Repair stays within the original test owner: append the backend-release-failure scenario to that native test name, preserve every registered test and all duplicate/missing/outcome assertions in the original machine reader. Also close the independent LOW by recording receipt_identical=false for actual content-refused/no-receipt paths. No production Host, parser, fee, schema, build or staging behavior changes; no rebuild needed. Next verification is the actual two colliding original native entry files through the existing isolated launcher, then one fresh original complete certificate on the final frozen source. Preserve failed04 and obsolete packet04 as historical bound artifacts. Original failed live ledger remains cancelled/no receipt/pending7344/backend owned (fresh readonly recheck /tmp/c2p-dsh-l01-original-owner-current-readonly-20261004.json); explicit local settlement authorization still pending, no canonical mutation or new model request. Progress24/49 and Gate-L FAIL remain unchanged.


### 2026-10-04 — L01 必要 legacy owner retirement 修复（未执行原任务）

原一次授权请求 Gate-L 仍 FAIL，24/49；C–F 未正式启动。certificate05 已为必要旧 owner 生命周期缺口取消，exit 130，未形成有效证书；packet05 因源码变化失效。不得把局部通过记为 Gate-L PASS。

新增 operator-only `legacy_retirement.py`，由 SerialBackendAdmission 显式入口调用，不进入 Worker RPC 或模型工具。要求已复核方案和明确 settlement+retirement 授权，绑定原 packet/manifest/producer/SSE/error Session/cleanup、原 request/contract/frozen identity，且原 Worker 先完成 cancelled settlement-only 结算。原账本 pending/missing usage 必须零；同一原 owner 事务 CAS + 独立 legacy release history，幂等重放，拒绝 owner 再占用和不同 owner，保留 cancelled/无内容回执、不铸 provider_quiescence、不调用模型。修复 reserve.contract_digest 应对照存储合同 task_digest，而非 ArtifactRef semantic_digest 的绑定错误。

验证：`python -m pytest -q tests/integrations/dsh/test_legacy_retirement.py`，exit 0，11 passed /21.62s，原始日志 `/tmp/c2p-dsh-legacy-focused05-20261004.log`；UNIT 只证明实现性质，不证明实际旧 owner 退役。`git diff --check` exit 0。原封存 registry 逐字恢复并匹配 manifest，51 文件及三个原目录只读 overlay；`python /tmp/c2p-dsh-l01-recovery-20261004-01/verify_launch.py` exit 0，原 ad6c/1b417/a726 身份恢复，网络/模型/任务/预算/后端写入均零。实际 transport-only 原始 SSE/Session/usage 与封存 manifest 校验通过，产物 `/tmp/c2p-dsh-l01-legacy-retirement-package-20261004-01/readonly-transport-check.json`，未造授权/未退役。独立代码复核已送 `/tmp/c2p-dsh-independent-legacy-retirement-code-20261004-01`，结果待回。

尚需独立复核与必修问题修复、最终源码冻结/注册证书与正常冷入口、可审查的原任务 settlement+retirement 执行包及用户授权、原 owner 实际执行结果，再另行批准新有界真实请求。此前自动审批拒绝原预算结算；尚未改写该预算或清除原占用。


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

### 2026-10-05：packet10 只读现状核查与完整接续指导

用户要求核实现有长期模块并细化缺漏。A独立Gate-R/V保留，项目24done/1in_progress/24planned，模块7/23done，L01未通过，C–F仅具名研究。packet10原授权一次调用HTTP200、7463/1182，原账本费用结清但backend仍held、领域无receipt。只读原WriterTaskResultV1复现缺schema_version；原_verify_native_quiescence准确在task_store.py:290拒绝Session blocked。真实native tool/result先出现schema_invalid，后端错误遮住该首因；raw与Session分片同字节，normalized仅表示不同且JSON等价。原输出另有inline公式取代要求占位符，未绕过schema做领域接受。

核查命令：PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python .dsh-dev/run/l01-packet10-status-20261005/verify_packet10.py，exit0；原费用/backend只读reader与owner读回一致，engine前后fb26901f…4698f、validator36fb99bd…28a7f。未跑产品套件/模型/网络，未改变任务、账本、backend、生产代码或runtime。本次不是完整独立Gate-L裁决。

完整指导：docs/dsh_execution_20260928/stage04_L01_packet10_repair_and_continuation_20261005.md；原始运行安全副本与verification/current-progress/doc-sync输入清单在.dsh-dev/run/l01-packet10-status-20261005/。要求一次修terminal/formula合同、native拒绝完成/释放、错误分层、历史exact-owner恢复和整包验证，并细化C的多请求/aux身份与D的每请求permit，再按原G0/G推进。packet10旧内容保持失败；已消费primary不得重发；已有normal-release授权不重复询问，相同scope之外的迁移先完成可审查方案。

本次核查时外部index仍source_writes_allowed=false、live10 running字段已过时；没有代其他reviewer释放。文档修订先封存为pending-doc-sync.patch，实际主写者须在当前独立QA读集释放后核对输入并合并；本记录进入主文件时不自动构成新的release证明。同步文档后下一份证书必须绑定最终完整身份。不能借本次修改回填或重标旧certificate09/StageA039。无默认切换、D5或发布。

## 2026-10-05 L01 packet10 complete repair batch

Scope: execution-guidance §8; five L01 repair groups, followed by independently gated M/P/G stages. Independent packet10 post-live QA is FAIL and actual readsets released: /tmp/c2p-dsh-independent-packet10-postlive-20261005-01/readset-release.json. Six pending-doc inputs matched, git apply --check exit0; patch merged after release. Prior dirty baseline sealed under /tmp/c2p-dsh-l01-repair-20261005-main-01/baseline.json. packet10 original raw/fees/receipt/backend unchanged; no model calls and no new grant. Original handle97648 unavailable on this host; original log reports exit1; never restart it. Progress stays24/49. Main executor owns Python, TS, tests, build and records.

本批五组代码、native离线反例和历史隔离证明已集中实现，详细变更、原命令/退出码/日志、基线与剩余门记录于 docs/dsh_execution_20260928/stage04_L01_repair_batch_evidence_20261005.md。注册suite升core/4、offline/4；完整certificate尚未跑，待独立必修关闭后统一冻结。packet10正式owner仍held，未执行迁移；新primary仍0，不沿用已消费授权。保持24/1/24及Gate-L未通过。

2026-10-05本批后续实际结果：独立代码/具体恢复方案 /tmp/c2p-dsh-independent-l01-repair-code-20261005-01/review.md PASS、全部读集释放；21项新增模块完整反例独立exit0，原producer和真实原包只读完成proof通过。按原normal-finish release授权执行具名迁移一次，exit0，句柄21502回收；正式package /tmp/c2p-dsh-l01-native-retirement-package-20261005-01。原canonical backend empty，原task/DB/费用7463spent/0pending及领域失败不变，receipt/quiescence均null，provider/tokenize0。独立迁移结果复核根 /tmp/c2p-dsh-independent-l01-native-retirement-result-20261005-01（按实际report验收）。完整suite core/4/offline/4的具体最终manager与机器入口已经写入整批证据doc；将冻结当前完整身份后运行原manager及fresh cold，不再边改docs边跑certificate。最终运行结果保存在外部执行索引与fresh证书/原reader，Gate-L仍FAIL，新primary仍需fresh包具体授权。

最终封存前：正式历史迁移独立结果报告实际PASS，读集释放，原reader及所有history/原账本/task/raw一致性通过；不以backendempty代替Gate-L。五组修复代码/方案与迁移结果两次独立复核均关闭，无生产代码新改动。

最终complete01实际exit1（source5fd/validator3f8），Python1384/56passed、Node214pass/1fail，cold未执行。失败是新增backend断言时点错误：故障注入旧kernel held，但健康新worker已依原registered finish合法释放后误预期owned。生产未改，修测试为旧故障后立即exact-held、恢复后empty+原严格finish/history证明，两个真实native focused exit0，2pass/0skip/172.153s，typecheck exit0。独立delta02 PASS并释放读集，98项生产/validator源SHA不变。failed01留档；当前最终fresh complete/cold采用 /tmp/c2p-dsh-l01-admission-20261005-02，完整命令同证据doc，仅更换fresh路径；冻结后结果只写外部机器记录/执行索引。当前source因测试与docs变化须新统一证书，不复用旧Python报告或旧身份。没有新的provider/tokenize，Gate-L仍FAIL。


## 2026-10-05 packet11 ordinary text-stop repair (active)

Final previous repair identity engine1ccece86/validator3f8: complete02 1600 and fresh cold passed both original readers; manager48049 exit0 reaped. Final independent material review CLEAR/all actual readsets released in `/tmp/c2p-dsh-independent-l01-final-admission-packet11-20261005-01`. User explicitly granted packet11 SHA65f941c1/plan7a02a897 once via question call_hYeoNWJfJmkVrNL3KOeBjETj; original launch94723 exit1 reaped, primary1/tokenize1/aux0/retry0. Actual SSE returned ordinary content fenced JSON, no tool_calls; usage7596/1309 total8905, finishstop. Original ledger usage persisted, no terminal/settlement, spent0/pending7596/backendowned/taskcancelled/domainnull. Original bytes and failure retained. Independent postlive `/tmp/c2p-dsh-independent-l01-packet11-postlive-20261005-01` Gate-L FAIL/all actual readsets released. No new inference authorized; M/P/G not integrated.

Root owns same-direction repair at `/tmp/c2p-dsh-l01-text-stop-repair-20261005-01` preserving responsible-file baseline. Add named private rejected-text completion proof, keep Writer tool/domain gates strict, check missing terminal before callId decoding, keep text provenance separate, natural stop fees/release independent of domain outcome. New helper verifies actual Session, native compact stream/block/usage/finish order, exact original request config/tools, scope and ledger, active-execute registration. Old tool completion and packet02/10 migrations unchanged. Pending original packet11 history recovery needs distinct reviewed operator procedure for its still-pending observed fees; no canonical mutation yet.

Observed verification: initial typecheck01 exit1 due putBytes media type declaration; fixed same owner's declaration for existing Worker text/plain support. typecheck02/build01/stage01 exit0. New proof01 37passed1.05s, then strengthen structural negatives to require_settlement=false so stale terminal refs cannot mask assertions. First actual native01 exit1 (original3023 reaped), composition_source_unstable before formal dispatch: root added unit test while bound scenario was running. Preserve failure; close current source before rerunning fresh native02, no source edits during run. All results are offline, fake provider only. Full/cold must be regenerated only after entire new repair/docs/tests/operator plan close.

Follow-up observed results: proof02 37passed1.08s (structural negatives verify pre-settlement proof). native02 original3931 exit1: model source legitimately contains provider/model/replayState; strict whole-source equality was wrong. Helper now checks kind=model and exact provider/model from frozen original request, keeps stream/usage/order gates. Original failed02 Session verified read-only with corrected helper; no state rewrite. proof03 37passed1.06s. Actual native03 `/tmp/c2p-dsh-l01-native-text-stop-20261005-03`, handle89012 exit0 reaped, 1pass/0fail/0skip72.046s: ordinary text stays rejected, captured_source/domainreceipt null, usage17 paid/pending0/backendempty, original strict release reader PASS, fresh Worker zero additional sends. Focused04 `python -m pytest -q tests/integrations/dsh/test_text_rejection_completion.py tests/integrations/dsh/test_host_recovery_boundaries.py tests/integrations/dsh/test_coverage_use.py` handle23566 exit0 reaped,170passed/56subtests214.32s. No source edits during native03 or focused04.

Readonly original packet11 recovery preparation at `/tmp/c2p-dsh-l01-text-stop-recovery-preparation-20261005-01/readonly-preparation.json` binds original task/ledger/budget/grant/plan/wire/SSE/Session and archived producer bytes. Distinct read-only historical transport helper now implemented: exact single stop/DONE, plain content and reasoning only, usage/order/model/index, original attempt/error stream and sequence match. Its external prototype verified original7596/1309 SSE and error Session (text1667bytes,reasoning3185bytes), no mutations. Operator full request/claim/fees/grant/identity binding, idempotent crash-safe settlement+exact-owner history transaction and independent review still pending; no new recovery execution or live grant.

Historical proof/operator update: `text_stop_transport_proof.py` + distinct `text_stop_recovery.py` use sealed old packet/plan/grant/producer/wire/SSE/Session and exact task/claim/ledger, original request projection whitelist, observed usage and current implementation identity. Operator records distinct historical settlement evidence, adds exactly immutable accounting terminal/settlement through original publisher, keeps task DB/claim/raw/domain/provider_quiescence unchanged. Owner/history delete transaction remains atomic; event cuts resume/idempotently spend once. New class history reader added without relaxing packet02/native-tool categories. Original real packet11 readonly full binding PASS, draft attestation under recovery-preparation.

Operator06 exit1 fixture composition not imported (no migration); operator07 exit1 minimal UNIT loop has no provider, fixture direct indexing failed (no migration). Test fixture now reflects its original minimal loop with optional provider, production checks unchanged. operator08 16passed67.18s; tightened launch/start/exact original authorization/tokenizer and whole-run budget checks, operator09 106passed75.64s (new three Python files), original7680 exit0 reaped. Real original-data isolation01 uses read-only root/unshare-net, only independent run/backend copies mounted RW at original paths. Fixture review/grant are explicitly simulation only. Original82949 exit0 reaped; clone paid7596/pending0 and history-released exact owner under engine55c4c450/validatored25. No canonical mutation, no model/tokenize call.

Current documentation entries/task_board synced to packet11 consumed/FAIL/held-pending and retain packet10 history. Generic terminal instructions explicitly prohibit JSON/code fences in ordinary assistant content instead of native c2p_terminal invocation; full schema/formula/witness/source obligations retained, no known-answer injection. This prompt change happens before future freeze/full; not a claim that future model must comply. Need final focused/native regression on closed code/docs, isolation command refreshed to final identity, actual independent code/plan/scope review+release before same-grant original fee/release operation; result QA before final new full/cold/live packet.


Current text-stop final verification and recovery closure: focused10 original42977 reaped exit0,183pass219.64s; native04 original17352 reaped exit0,2pass/0fail/0skip149.624s, no code edits during either. Current protected original-data isolation02 original29237 reaped0, enginef61/validator7b77; 35 original files RO, clone spent7596/pending0/backendempty, real original unchanged. Independent code/plan review439 inputs PASS, original-grant APPLIES and actual release in /tmp/c2p-dsh-independent-l01-text-stop-code-plan-20261005-01. Actual canonical original effect operation original52748 reaped0 under exact reviewed wrapperfb5121/plan17bbbc; original35files/taskDB/claim/raw/SSE/Session/domain and prefix5 unchanged, operator evidence+accounting terminal/settlement only, spent7596/pending0/backendempty. Actual independent result /tmp/c2p-dsh-independent-l01-text-stop-migration-result-20261005-01 PASS361 inputs, all four history original readers pass and old three histories unchanged; real readsets explicitly released before docs closure. No model/tokenizer, no new live grant, GateLFAIL/progress24/1/24. Final full/cold must bind newly closed source/docs identity and original manager/readers; do not reuse previous1600 or f61 identity after docs changes. Planned fresh final output /tmp/c2p-dsh-l01-admission-20261005-03, command: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -c 'from code2paper.cli.main import main; raise SystemExit(main())' method-agent record-offline-receipt --out /tmp/c2p-dsh-l01-admission-20261005-03/receipt.json --suite-plan dsh-stage04 --output-root /tmp/c2p-dsh-l01-admission-20261005-03/managed --candidate 0.2.0-rc.1+loop-origin.1 --timeout-seconds 7200. After source freeze results only external. Fresh actual Gate-L and concrete new one-time live authorization remain pending; M/P/G require Gate-L PASS and release.

Before any complete03 launch, readonly version scan found2 current plan assertions and1 insufficient UNIT receipt fixture still /4. Updated only these3 version literals to currentcore/5+offline/5, retained core/4 andoffline/2 negative admission test. Focused `test_dsh_admission.py test_target_admission_integration.py` original53668 reaped exit0,49pass25.19s, log version-delta11.log; no production change/newmodel. Original03 source-freeze marked superseded-before-execution and retained, no full run. New actual final fresh output reserved /tmp/c2p-dsh-l01-admission-20261005-04 with same original manager argv replacing03→04. Version/doc delta independent read-only closure precedes final freeze/full; subsequent outputs external only.


## 2026-10-05 packet12 malformed native tool rejection repair (active)

Final complete04 current9def/validator7b77 passed1707+freshcold1 and both original readers; original manager33395/readers55834 reaped0. Independent final material review498inputs CLEAR/preparation only, actual readsets released. User explicitly granted packet12 SHAfe48f5/plan cde246 once through call_ZGnx5G3Z9MXflYbKGx1l1Jtw; auth87dcd4ca, no reuse. Original live44943 reaped exit1, primary1/tokenize1/retryrepairaux0; actualHTTP200 input7648/output1221/total8869, finish_tool_calls. Raw function name exactly '"c2p_terminal"\n<parameter' with args{}; originalSession unknown-tool call/result ToolNotFoundError UNKNOWN_TOOL then blocked turn. Host correctly refused terminal, but diagnostic incorrectly called it ordinary_model_text/raw0. Original fee7 facts already spent7648pending0; taskcancelled/capturedsource/domainreceipt/providerquiescencenull/backendownedpacket12. Original bytes/failure preserved; no tool-name trimming or args repair, no resend authorization. Independent postlive367inputs /tmp/c2p-dsh-independent-l01-packet12-postlive-20261005-01 GateLFAIL/all actual readsets released. Cannot distinguish model serialization/server parser from current artifacts alone; optional public runtime config record requested, no server changes or extra calls.

Root owns same-direction unknown-tool diagnosis and private native-finish release repair; baseline /tmp/c2p-dsh-l01-unknown-tool-repair-20261005-01/baseline.json preserves responsible files. New distinct unknown-tool completion proof binds active execute/private naturalfinish, exact Session/blocks/deltas/request/tools/source/usage and original UNKNOWN_TOOL result; cannot be a terminal candidate, registered tool, caller finish or recovery-only observation. Host preserves exact names/args in diagnostic JSON separately from ordinary text. Original packet12 recovery must be a distinct sealed operator reviewed original naturalfinish/exact-owner procedure, no TaskDB/providerquiescence/fee mutation and no second settlement. Current code changes are under implementation; tests/build/native/independent review/full not yet observed. New model request needs substantively fixed actual request/runtime and fresh concrete packet grant; lifecycle-only change cannot justify unchanged-wire lucky resend. GateLFAIL/progress24/1/24; M/P/G formal implementation gated.

Unknown-tool initial verification: typecheck01 failed before compiler because default DEV_ROOT expected different peer symlink; kept current links, reran with explicit candidate/root. typecheck02 original39284 reaped exit1 due test isObject helper unimported; replaced assertion with native object check. typecheck03 original21887 reaped0. Focused proof01 original2099 reaped0,91pass1.20s (unknown54 + existingtext37), no native/model calls. Register new actualPython/node entries, core6/offline6; synchronize current version assertions+UNIT fixture while retaining old core4/offline2 negatives before final run. New active unknown proof has exact UNKNOWN_TOOL result/source/order and exact model request/offered tools, all compact blocks/args/usage/naturalfinish; oldtext/registeredtool contracts unchanged. Preparing build/stage and actual native3-path regression with no source edits during bound run; current canonical still packet12owned/fees7648paid, no operator execution.


Unknown-tool verification completed: proof02 original91994 exit0 58pass; typecheck03 original21887/build01 original75774/stage01 exit0. Native01 original58585 reaped0,3pass/0fail/0skip225570.860ms, engineb641/validatorf22 frozen throughout, log /tmp/c2p-dsh-l01-unknown-tool-repair-20261005-01/native01.log. Pure Session checker extraction preserves active private authority and adds distinct operator-only unknown-native-tool-retirement/1; no historical active quiescence or fee/task/source mint. Retirement01 fixture failed21 due UNIT projection lacking provider; retirement02 failed1 due unjustified child/session identity equality; corrected fixture to preserve absent optional provider and enforce separate bound child/nonempty and exact Session id (no equality invention). Retirement03 original16316 reaped0,21pass85.73s. New SSE representation negatives plus old native retirement and unknown proof retirement04 original41460 reaped0,116pass169.67s. Proof03 original99754 reaped0,95pass1.17s preserves text-stop.

Protected original-data clone /tmp/c2p-dsh-l01-unknown-tool-history-clone-20261005-01 original44142 reaped0 at engine4fc333/validatorfe1d8e: whole rootRO/networkunshared, only cloned canonical backend mapping and cloned lease mapping RW, explicit UNIT review/auth fixtures (not canonical authority). Actual original packet12 typed read-only proof passes; clonebackendempty/five strict history rows;59 protected original bindings unchanged, canonical still packet12owned, no model/tokenize/additional fee/source writes. Actual canonical independent code/plan/scope review and readset release pending. New operator schema does not weaken old four histories. Current final full/cold pending;1707 proves historical9def/7b77 only.

User supplied historical server script/template/log under /data1/users/cuihengjia/qwen3.8-modelopt. Script/log record qwen3_xml + qwen3 reasoning, no explicit --chat-template; file template defaultsXML. Current GET tokenizer_info/server_info both404; current on-disk historical vllm parser bytes and model directory cannot prove currently loaded server config. Initial commentary inferred XML prohibition incorrectly; immediate actualwire correction records no such prohibition. New generic terminal instruction specifies exact function-name value, excludes quotes/whitespace/markup/parameter tags from identifier, preserves arguments schema and backend serialization. This is a targeted request-material repair, not a response-name rewrite or proven server root cause. Runtime unchanged, no new inference authorization or resend; final live still requires fresh sealed packet and specific grant after all review/full/cold gates.


Unknown-tool canonical closure: independent code/plan525actualinputs PASS/APPLIES and actual readsets released (/tmp/c2p-dsh-independent-l01-unknown-tool-code-plan-20261005-01), exact plan6238d36/wrapper43d24f executed original98467 reaped0 at4362/af9. Root scope record derives old actualpacket12 grant, not new inference consent. Original42nonlease files/14attestedinputs and all7fees/taskview/claim/source/receipt/quiescencenull unchanged; originalleaseprotocol PID only, canonicalempty, five strict histories, old4byteidentical. Actual independent result364inputs PASS/allreadsets released (/tmp/c2p-dsh-independent-l01-unknown-tool-migration-result-20261005-01). Receipt89055036. Focusedcontract05 original93910 reaped0,133pass2.11s. All documentation/taskboard/current indexes now packet12 recovered lifecycle/domainFAIL, counts24/1/24. Oldnative b641 and protectedclones4fc/4362 keep own bindings; full1707 is historical9def only.

Final complete/cold new fresh root /tmp/c2p-dsh-l01-admission-20261005-05. Command: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -c 'from code2paper.cli.main import main; raise SystemExit(main())' method-agent record-offline-receipt --out /tmp/c2p-dsh-l01-admission-20261005-05/receipt.json --suite-plan dsh-stage04 --output-root /tmp/c2p-dsh-l01-admission-20261005-05/managed --candidate 0.2.0-rc.1+loop-origin.1 --timeout-seconds 7200. This doc records planned exact command only; actual handle/exit/results/source identity stored externally after freezing. After original manager reaped0 validate original complete coverage_readonly_inputs and fresh cold validate_coverage_use with validate-final-certificate.py and require independent final material review/readset release. Do not modify source/docs/tests during bound run or review; do not repeat unmodified full or TS build/stage. No new live until fresh actual packet material and specific usergrant. Gate-L FAIL still bars formal M/P/G.


## 2026-10-05：packet13 一次执行及 native 工具选择返修

用户对 packet13（packet `2eb2c5eeeeebbb6a192c8754060c7aec91bed9cc94cd806ec733dff319ad361a`、plan `3d13cc46b66039667cd6456cb36410d8571f87bd9549d000f0a9a53e1170fc97`）明确一次批准，原授权记录位于 `/tmp/c2p-dsh-l01-packet-20261005-13/user-authorization-record.json`，没有复用 packet12。新完整05原59877 exit0：Python1585+56 subtests、Node217、operator1，共1803；fresh cold1，原reader69726 exit0，独立材料505输入CLEAR/all released，均绑定关闭前7f77/af9身份。本节更新以后，不能把这些历史身份结果自动升级为当前新源验证。

原发送前只读检查45089 exit1（默认sandbox socket denied，未调用模型/tokenize）；原network只读检查75178 exit0。核验固定packet/plan/frozenfiles/7f77-af9、原完整与cold reader、原空backend/目标zero budget、health/models/metrics200且running/waiting/KV0。原授权live argv：`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python integrations/dsh/dev/l01_launch.py live --output /tmp/c2p-dsh-l01-packet-20261005-13 --receipt /tmp/c2p-dsh-l01-admission-20261005-05/receipt.json --authorization /tmp/c2p-dsh-l01-operator-authorization-20261005-13.json`；原handle86098已reaped exit1，原sandbox/10秒监控，实际primary1/tokenize1/auxiliary0/retry0/repair0。HTTP200/stop，usage7699/1359/9058；普通JSONwrapper文本1190bytes，tool_calls0，不得解析正文JSON或arguments字符串补造native工具来源。Host首因host_single_terminal_required/ordinary_model_text，secondarynull/cleanup[]。原Taskcancelled/captured_source=null/receipt=null，原DshRejectedTextProviderQuiescenceV1登记，7费用事实唯一spent7699/pending0，正常exact-owner释放、canonical empty。原日志/SSE/Session/费用/Task保持。

独立实际post-live `/tmp/c2p-dsh-independent-l01-packet13-postlive-20261005-01`：382实际输入，Gate-L FAIL、生命周期PASS；所有6历史严格读回通过、旧5不变，本人全部实际读集明确释放，7f77/af9于读集释放稳定。无需历史恢复或再结算。阶段仍24done/1in_progress/24planned，正式M/P/G不能越Gate-L。授权13已消耗，不能重发或额外probe。

当前可复现接口缺口：pi-ai openai-completions支持toolChoice，但原DSH PiAiAdapter/profile不把选择送至wire。`/tmp/c2p-dsh-l01-packet13-tool-choice-investigation-20261005-01`为隔离fake-fetch探索（非生产来源、非服务端能力证明）；probe03 exit0和validated-probe exit0证实只添加named tool_choice、其他wire字段一致；negative-probe02 exit0证实profile schema、12错误配置、4缺失/错误/重复tool选择、策略不可变和零fetch。前两次导出/schema读取fixture错误原日志保留。没有真实模型或tokenize。

返修方向：新增可重建、exact-hunk generic native tool-choice patch，显式profile选择/不可变snapshot、仅已支持API且声明工具匹配才可发送；未配置保持旧wire，原native adapter/stream decoder/私有origin/费用及领域合同不变。源patch初稿 `integrations/dsh/dev/runtime-0.2.0-rc.1/tool-choice/tool-choice.patch.py`已写，仅作用fresh copied runtime；原候选runtime及原13产物未改。尚未完成新candidate接线、source build等价、实际Loader/native/费用正反例、当前完整/cold/独立验收与fresh packet，未授权新live。下一步先完成这些实现/验证及材料，不以该原型或历史1803代新准入；当前8006 parser/template仍未证实，不能宣称model-vs-parser根因唯一。


Native tool-choice final closure (packet13 remains domainFAIL): source compile27263 caught unsupported neutral SimpleStreamOptions.toolChoice typing; finalcandidate2 uses public samplingParams.tool_choice with validated policy only. Isolated actualsource tsc84801 reaped0, exactapplycheck, originalsource unchanged, sourcebuiltnegative16 / original-vs-final-vs-sourcebuilt wire equivalence PASS; scope client/source only, not fullpackage equivalence or current server capability. Actual candidate2 setup68617/pyworker72130/typecheck86332/build42008 allreaped0, stage/audit0; runtime b451ebbf551eba55ecb72b1c0bf9aa0f11338418eca51e12558ffcd3c34744b4. Registered three original native finalcandidate2 scenarios72888 reaped0, actualnamedwire/draft accept/wrongformula reject/text reject/fees/naturalrelease/newprocessreader; output /tmp/c2p-dsh-l01-tool-choice-native-regression-20261005-04. Earlier neutralcandidate1 native76006 retains own historical binding. Candidate1 npm14234 lacked offline config (network not proven absent); candidate2 offline=true npm install0, pyworker exact6lockedwheels noindex. All earlier failed attempts retained in investigation logs. Final docs/taskboard now packet13 failed with original spent7699/pending0/backendempty/sixhistory rows and independent actual lifecyclePASS/readsetreleased; counts24/1/24/GateLFAIL. Freshcomplete/cold06 pending after sourceclosure; no newmodel/tokenize/grant. FormalM/P/G retain each independent gate.

Final admission source closure: added actual native-selection trusted admission sources to validator bundle (scripts/dsh_dev, base helper/finalparams patches/finalcandidate contract). Both original L01 launchers forbid backend aliases and retain oldcanonical root even when field omitted; explicitnull refused. Current focused identity/backend/oldGateH tests80418 reaped1:39pass/two default sandbox spawnSync Python EPERM, preserved log. Only two affected actualisolatedactivation tests88556 reaped0:2pass1.73s. L01 original Qwen profile offline51327 reaped0:actual blocked localreceipt/private nativecompletion/17spent/pending0/backendempty; 0realmodel/tokenize. Bound validatorfc116 at run; Node explicitnull guard and currentdocs closure afterwards do not retag this artifact. New complete06 will bind final current source, full registered discovery and cold companion.

Complete06 interrupted honestly: pre-run review missed original serial E2E hardcoded old candidate; discovered from actual registered source while originalmanager running. Exact originalmanager2303223 plus six descendants only SIGTERM, allseven actual/proc absent; toolhandle37498 reaped143; no certificate/cold and frozen source unchanged throughout. Evidence /tmp/c2p-dsh-l01-admission-20261005-06/interruption.json; never counted passing. Original E2E now uses frozen plan candidate with old standalone default, all original assertions retained. Currentcandidate2 original98919 reaped0,1pass (exact log final-serial-e2e-candidate2.log). No production native behavior changed. Newfreshcomplete/cold07 after recordsclosure. Readonly escalated currentprocess verification now proves servingPID3597064 owns127.0.0.1:8006 socket3832216482, CUDA_VISIBLE_DEVICES2, qwen38 modeldir /data1/users/cuihengjia/qwen3.8-modelopt, qwen3_xml/qwen3 parserargs, maxmodel131072/noexplicitchat-template; loaded templatebytes still not proved. Strict allowlist outputs only, no secret or service mutation/no model/tokenize. Prior uncertainty retains its historical bound scope.

Full07 original33100 reaped1: actualPython1597pass/56subtests/1fail1033.05s, oldcandidate smoke positive strict staging failure; Node/cold notexecuted; fullreceipt false/offline_required_suite_missing. Original operator observe_initial+budget readback confirms0task/call/spent/pending; originalmanager owns finally process-group stop, no fabricated cleanup artifact. Only affected smoke positive now captures plan candidate before deliberate env conflicts; 70503reaped0,1pass7.11s, all original assertions retained. Additional registeredNode candidate-gate scan finds original joint-child/cancellation onlyold1/built; added exactfinal2 to apply entire existing acceptance, no arbitrary suffix/prototype1 accepted, no assertion omitted. Actualoriginal native99157reaped0,31pass/0fail/skip/cancel24966.29241ms. Finaltypecheck40136/audit37857reaped0; productionTS/buildinputs unchanged so no rebuild of oldhistoricalruntime/staging. Source/docs close nowfreshcomplete/cold08 only; original06/07 remain failed histories. InstalledcurrentvLLM read-only8bindings confirms on-disk named protocol path and renderer-before-adjust semantics; no loaded-code attestation, no actualmodel/tokenize or servicechanges.

完整08原manager43570回收exit1，Python1598通过/56subtests、Node220断言通过/0失败；原机器reader因三个新增场景与旧场景名称重复拒绝offline_node_duplicate，原receipt仍false、cold未执行。source-freeze保留45e94/5951身份及失败事实。修复仅在原host-provider场景标题加入named native tool selection区分，原reporter/reader及全部断言不改。六个旧/新场景原2702回收exit0，6通过/0失败skipcancel，484845.683935ms；原validate_node_report实际接受六个独立ID，证据/tmp/c2p-dsh-l01-tool-choice-name-regression-20261005-01/original-reader-result.json。最终typecheck25827回收exit0；生产TS输入未改，无重复build。关闭当前记录后使用fresh完整/cold09；未授权packet14，Gate-L FAIL，24/1/24。

## 2026-10-05 packet14 实际流内错误与 unknown 返修（进行中）
当前完整09原33501回收exit0：1819/freshcold1，原reader31459回收0，enginef82/validator5951；packet14准备23422/原readback44880均0，独立747输入CLEAR/all实际读集release。用户明确一次grant call_Fk0MPkeZYT67BUCdZ9bOFXCg；packetd20fd9、plan967f4c、auth4a37e135，前检6648回收0，原exactlive15585回收exit1，1primary/1tokenize/0retryrepairaux。162SSEframes部分reasoning后InternalServerError500/DONE，无实际usage/finish/tools；同request实际server日志xgrammar/scheduler终止拒绝tokens[13,198,248069]，不等于自然finish。原Session PI_AI_ERROR，无assistant/message/工具；原taskcancelled/source/receipt/quiescencenull，canonical exact14 owned、旧6history不变。SDK默认usage0/0误登记validated/terminal/settlement，原reader spent0pending0/completed1不是远端实际零费用；未知费用及首因缺口P1/P2必须修。独立postlive436输入Gate-L FAIL/all实际读集release (/tmp/c2p-dsh-independent-l01-packet14-postlive-20261005-01)。自然finish释放授权DOES_NOT_APPLY，不能按idle/DONE/SDK零值释放原14或改写旧账本。
Root同方向修复：排除SDK零input默认usage，缺usage错误流markunknown保留reservation；Kernel/Python禁止默认zerousage/非自然finish完成凭据；Host报告nativeprovidererror及原Session，L01首因保留SSEerror。新增真实PiAi HTTP流内error/DONE native场景、跨进程unknown费用/held/refuse-resend/release反例及原RPC反例，suite版本8。旧14费用、task及原产物不重写，旧full09只历史f82/5951；新source完整/cold尚未验证。任何新abort/unknown恢复副作用必须先具体方案/隔离验证/独立审查及单独授权，14当前授权不适用。Gate-L FAIL/24-1-24，M/P/G仍门控。

packet14错误返修观测补充：native02原37051回收exit0，31pass/76039.992619ms，含原30cancellation和真实PiAi error/DONE；L01 offline89326回收exit1为预期严格拒绝，原reader pending7134/spent0/completed0/provider_usage partial/task cancelled/null/backend held、首因SSE error。两者绑定fee0/80963，不回填最终refinement身份。最终guard只拒input0且output0，保留cached输入input0/output>0；typecheck04原61467、build02原80485/stage02均0，focused03原52352回收0，68pass/56subtests272.57s。新增实际RPC cached使用正例。当前完整/cold尚未执行；下一完整fresh10在所有源/docs关闭后运行core/offline8并独立验收。
历史14恢复裁决：原seven费用事实和旧six history均保持；当前日志终止不是受信自然完成，真实usage/持久绑定完成凭据缺失，normal-finish旧grant不适用。依执行指令4.4保持exact14 held；不直接DELETE/改resource/默认费用退款/伪造abort类型。任何服务端变更或具名abort退役须先具体合同/隔离验证/独立审查及其授权，未实际执行；请求可用原provider计量与持久abort记录路径，同时继续离线完整验证。

关闭前最后cached输入RPC正例：原66781回收exit0，1pass/23deselected5.03s，input0/output3通过原publisher保留、未伪造finish/settlement；最终源码/docs冻结用于fresh完整/cold10，结果只写外部。生产TS/build输入未再改动，无重复build/stage。


## Gate-L whole unblock closure (2026-10-05)

按原长期模块§9直接实施，本批新model/tokenize/service/canonical操作均0，24/1/24与七次live/Gate-L FAIL保持。完整实施、文件责任、具体命令/原句柄退出、失败历史与范围见 `docs/dsh_execution_20260928/stage04_L01_provider_error_repair_evidence_20261005.md`。

非thinking profile、worker、native calibration与原Facade发送前合同绑定显式模板false，具名原生terminal不变。共享Formalizer reserve保持1024，Writer measurement reserve0单独绑定descriptor/model/composition；不改原义务和修复预算，不新增runtime补丁。真实Loader/PiAi/Session/worker覆盖正常缺usage、有usage缺finish、断流、真正请求后timeout，pending/held/null domain/跨进程0重发均核验。原L01整链先发现provider_options_mismatch/0发送（93642回收1），补精确原发送门后74526回收1是预期SSE500拒绝，原reader PASS/pending7133/partial/held。

UNKNOWN operator合同严格绑定immutable plan/review/termination/newgrant与exact owner；保守input32768/output4096责任、old run永久禁续；immutable disposition先fsync再typed history+exact delete原子事务；original receipt reader交叉核验identity/task/budget，11组重算摘要攻击拒绝。保护原14七场景25545回收0，原DB/run文件不变。真正stop/迁移未执行；正向模拟confirmation/grant不是真实授权。实际8006同epoch3process/GPU2/MTP2、原request日志、白名单非秘密配方已只读绑定；全共享服务stop/restart和distinct迁移授权仍缺。

集中独立审查1104输入CHANGES_REQUIRED/U1-U3已释放实际读集，随后同批修。当前聚焦：71652回收0/48pass95.30s；94932回收0/45pass17.78s；67411历史原native35pass；新增26587回收1/3pass1fail（timeout脚本误要求错误回执），修脚本44995回收0/1pass71824ms；7574 typecheck05回收0；本机grammar76694回收0；原native非thinking prepare73499回收0。初始digest前缀与toolchain选root失败保留，不当成验收。

所有代码/配置/合同/文档在完整10前关闭，原registered版本10生成当前完整及fresh cold，路径 `/tmp/c2p-dsh-l01-admission-20261005-10`，状态/身份/运行句柄写sole-writer `/tmp/c2p-dsh-l01-repair-execution-index-20261004-01.json`。本文关闭时未启动10；full09仅旧f82/5951历史。验证和独立整包审查期间源/文档冻结，随后需要真实恢复、新packet具体一次授权；同类grammar错误则转8006专项。Gate-L独立PASS/readset释放后继续M/P/G各门，不做default/D5/rollout宣告。


### 2026-10-06 Gate-L 最终独立审查 U4 集中修复

完整10原13886回收0：Python1640及56subtests/Node226/operator1，共1867，fresh cold1；原两reader80140回收0，109路径，fced96d6…/f466801c…稳定。最终独立审查 `/tmp/c2p-dsh-independent-l01-unblock-final-20261006-01` 绑定1606实读输入、U1–U3闭合，只剩U4授权与终止subject嵌套bool/int弱等值，全部实际readsets明确released/retained[]后才修源码。

责任文件仅unknown_abort_recovery.py及其测试，加相关状态文档：canonical JSON字节类型保真绑定authorization/review/subject/process/scope/marker/receipt，strict approved True及owner/scope校验；新增9项拒绝路径，无操作权限扩大。历史正常完成授权仍不适用。真实合法内容receipt与费用settlement分离保持；缺usage依然UNKNOWN/pending/不能quiescence或release，不强制销毁真实内容receipt。

首轮focused01原67354回收exit1，31 passed/1 failed/130.86s。主执行者期间写文档触发既有fixture request.reserve的composition_source_unstable；9新增反例均通过。记录并修正验证安排，先把全部文档收口冻结，再重跑 `/tmp/c2p-dsh-l01-unblock-u4-focused02.log`；其后新完整 `/tmp/c2p-dsh-l01-admission-20261006-11`、fresh cold、原两reader与独立QA。当前收口时均未开始，实际结果/身份/句柄/退出写外部 `/tmp/c2p-dsh-l01-repair-execution-index-20261004-01.json`，验证期不再改源或本文。旧完整10保留原绑定历史，不重贴当前证书。新最终保护原14克隆输出 `/tmp/c2p-dsh-l01-packet14-abort-isolation-20261006-04`，绑定同一新冻结身份；simulation不授权真实stop/retirement。

项目24/1/24、七次真实live、Gate-L FAIL；原packet14 actualUNKNOWN/held、七fees六history/raw/task/source不变。实际终止确认、服务owner配方确认、独立操作review、distinct stop/restart/retirement grants均缺，模型/tokenize/服务/canonical新增副作用0。按长期§9完成合法恢复和新包具体授权后才新请求；若仍grammar同类，转8006专项不再提示试错。


## 2026-10-06 packet16 native-stop与Writer witness返修（用户已解除源码冻结）

packet14实际具名UNKNOWN退役及独立验收PASS；8006按原配方GPU2重启ready。packet15仅tokenize1、primary0，因新history依赖在/tmp沙箱不可见被claim拒绝。外部精确20文件RO传输方案独立CLEAR，原595/c458源码身份保持；用户明确授权packet16+transport一次，原句柄42929回收exit1。packet16实际primary1/tokenize1/retry0：HTTP200/native c2p_terminal成功、usage7705/392/8097、唯一stop/DONE；领域paragraph/witness验收拒绝。六fees已settled7705/pending0/completed1，原16仍held且quiescence未登记，历史仅原7且不变；14UNKNOWN32768/4096仍保留。独立实际QA585输入FAIL且读集释放：/tmp/c2p-dsh-independent-l01-packet16-postlive-20261006-01。

用户明确回复“解除冻结，按具体方案开发验证”，记录与未应用草案原包：/tmp/c2p-dsh-packet16-diagnosis-20261006-01。当前实施三项：原native工具stop完成凭据/释放、Writer完整operands/operator/result关系witness、exact-owner历史正常完成恢复合同。最小三文件草案已应用，新增真实native stop成功/领域拒绝两种隔离测试正在实施；所有source/数学/Formula/atom门保留。新代码须新identity+staging+必要完整/cold+独立QA，不复用完整11标签。此次没有新模型授权、未重发16、未修改canonical permit或服务。原纯content三variant仍拒绝，不能伪造原候选成功；原底层native Session proof真实stop通过、伪finish/foreignsession拒绝，只是读取证明，不是authority。后续结果继续由sole-writer外部索引记录。


### 2026-10-06 packet16 解除冻结后 native stop/语义/恢复开发

按用户“解除冻结，按具体方案开发验证”实施，当前没有新模型或canonical release权限。
修改真实registered terminal stop登记/分型、原release组合；原native证明门保持。
模型投影保留canonical语义/条件/极性并保持Binder witness归属；新增独立历史native stop
operator，保留task/six fees/raw/old history，review/auth/current identity/prior history摘要
与exact owner CAS绑定。新增required套件/11与真实native两个用例。
原60聚焦PASS、83原边界PASS/56subtests；原typecheck/build/stage退出0。
首次focused native两个用例一通过、一因源码并发修改composition_source_unstable失败，
该轮不用于冻结验收；后续稳定身份验证与保护克隆详见外部本批绑定产物。
`/tmp/c2p-dsh-packet16-diagnosis-20261006-01/writer-owner-feedback.json`由原parser/assessor/
paragraph repair/WriterSectionRepairPacket builder产生，owner writer_content/action
writer_content_repair/attempt1；原响应仍拒绝且字节不变，不是接受回执或新正文。
完整11仅旧身份，不重标签；后续新完整/cold/独立审查与具体恢复包独立收口。

本批稳定native stop两个原Loader场景PASS，历史恢复最终聚焦32 PASS，保护克隆PASS，
canonical task/raw/七history逐字不变。独立恢复代码/方案原0e63/4fd8身份PASS/APPLIES、
457绑定及actual readset release：/tmp/c2p-dsh-independent-l01-native-stop-recovery-20261006-01。
完整12出现两处test_dsh_admission计划版本断言仍/10；已知失败下对精确原offline pytest
发送SIGINT，原manager失败终止并保留失败/中断/teardown诊断，未跑Node/cold，不记为PASS。
两处期望同步/11；生产代码无其他修改。原12与QA保持原身份，新完整13及最终独立审查
须重新绑定最新测试身份。所有正式canonical review/auth仍待具体验收；new provider/tokenize=0。
# 2026-10-06 packet16 返修：完整13的 UNIT 协议夹具同步

完整13原session40094观察到六个失败。单文件原隔离诊断 `tests/integrations/dsh/test_target_admission_integration.py`（session22258，exit1，6 failed/13.73s）及完整13原pytest报告确认，同一UNIT synthetic upstream fixture仍声明offline/10，当前真实target admission在进入UNIT seam前按offline/11拒绝。上一轮只同步了suite-plan的两个版本断言，遗漏了这处夹具。仅同步该UNIT fixture的版本，不改变其故意不完整性质、mock边界、真实准入门或六种target反例。原pytest1486580收到具名SIGINT，manager40094 reaped/exit1；完整13receipt passed=false、offline_required_suite_missing，Node/cold未运行，保留原失败及停止记录于 `/tmp/c2p-dsh-l01-admission-20261006-13/`，不改标为PASS。

既有独立预审500项输入记录位于 `/tmp/c2p-dsh-independent-l01-native-stop-final-20261006-01/`，真实读集已释放；其557/4fd代码/恢复包预审PASS及prepared17 CLEAR均保留原身份，完整/cold不可用。此次同步后绑定新身份集中完整/cold及最终独立验证，不复用557证书、恢复plan或prepared17；无新真实模型/tokenize、服务动作或canonical释放。用户原解除冻结的开发验证范围持续有效。后续恢复具体包仍需最终明确操作决定，fresh live仍需一次具体授权，Gate-L仍FAIL。
# 2026-10-06 packet16 返修：完整14机器证书的重复身份拒绝

原完整14 manager62468已reaped/exit1。原Python1682+56 subtests、Node228行为测试全部通过；完整receipt仍passed=false/passed_count0、failure=offline_node_duplicate，operator子进程被原manager终止，cold未执行。严格原reader按(file,line,column,name,nesting)拒绝重复，实际两个native stop wrapper与default draft/wrong_atom_binding名称碰撞。仅共享host-provider test title对实际nativeFinish=stop增加后缀；保留真实执行、严格唯一性/summary/来源门，不去重报告、不改标旧结果、不缩减required。原2bbb/4fd完整14、native stop两个原persisted readback均保持历史身份。聚焦真实Node及原机器reader/全局身份检查后重新冻结完整15；旧R3计划、prepared17不能换标签，实际16恢复和fresh live另形成新身份具体包后才审批。无原run/canonical/服务变更、无真实model/tokenize，Gate-L仍FAIL。

### 2026-10-06 最新用户 steering：身份差异采用差异验证，停止全量重跑循环

用户明确要求精简流程、快速解决并推进。完整14原始行为Python1682+56subtests、
Node228均通过，原certificate仍为duplicate FAIL；两例测试名修复后真实native-stop
DSH成功/拒绝恢复均PASS、session71499实际reaped/exit0。不启动完整15重复相同行为。
新增仅离线core复用通路，原报告保持历史绑定，差异审查覆盖当前验证层，Node按
entry-file保留来源；实际operator和cold需fresh执行，非继承成功。新差异验证只跑
相关reader/closure/operator测试。无canonical释放或新增模型/tokenize授权。


### 2026-10-06 L01 native schema/required witness 接续

- 当前用户要求必要live直接执行、身份差异不重复确认；具体一次包及真实依据仍记录。
- packet16具名退役实际PASS，原数据与费用保留。packet21一次1+1，7819/565，schema_invalid、正常释放。
- server-default省略SDK的strict:false，真实Qwen/XGrammar保留完整schema；actual SDK零网络及CPU完整grammar通过，未改runtime/服务。
- 完整15：原Python1716/Node228/operator1，共1945；fresh cold1；session93810 exit0/reaped，81871a/569636，无source漂移。独立材料CLEAR/读集释放。
- packet22：session94180 exit1/reaped，1+1、7815/223，原生stop及原usage/释放正常；原raw合法schema但缺witness，原required_target_contract拒绝。独立Gate-L FAIL/103 inputs，读集retained[]；当前backendempty/10严格history，旧14UNKNOWN保留。
- 当前负责writer_contract.py原native发射要求、writer-request.ts双schema guard及wire.test.ts遗漏字段反例；旧publication schema、语义/公式/来源门不变，当前验证中，未冒充完成。
- 产物：/tmp/c2p-dsh-schema-compat-20261006-01；/tmp/c2p-dsh-packet22-live-operation-20261006-01；/tmp/c2p-dsh-witness-emission-20261006-01。typecheck/build/stage均实际exit0；Node两次报告路径/fresh目录前置拒绝均零测试/零模型，node02为实际聚焦执行。
- 继续：必要验证/独立门后一次有变化fresh；Gate-L PASS才正式M/P/G，已收齐只读M01–M03接口准备。

### 2026-10-06 L01 Witness 合同独立发现 W23-1 与原 owner 修复

复用现有独立 QA（不新开代理）确认：packet23 的实际 paragraph_transaction_required 提示要求 Binder 提供所有 exact witnesses，而 DSH terminal 要求 Writer detail witness；native description 也未区分 Binder-owned atom。读集已释放 retained[]，原独立报告保留于 `/tmp/c2p-dsh-independent-l01-packet23-current-20261006-01/`，没有材料 CLEAR。最小修复仅在原 facade.TERMINAL_INSTRUCTION 明确前面的 Binder 指令只适用于 atom/internal sidecar，Writer 必须覆盖 frozen witness_contract.targets 中的 required detail，即使 rendered_detail_ids 空或省略；native description 同步限定 Writer-owned targets。通用 writer_skill、旧 raw、原内容/公式/语义/来源门不变。原 test_l01_binding_contract 增加真实 task payload 的 owner 分工反例。

完整16因上述新发现受控提前停止两个固定离线测试进程组（2175108/2175129，SIGTERM）；原 session56388 已 reaped/exit1，两个 terminal exit -15，原 receipt passed=false/offline_suite_binding_invalid，cold 未执行，不记 PASS。没有真实模型调用、服务操作或占用恢复。上一轮 Node 聚焦57/55PASS/2 source_unstable（运行中写文档造成）仍保留；最终稳定整包覆盖原两负例，不修改断言。packet23仅prepare/零模型，保留为修前快照；修后使用fresh24，不重写旧包。避免先完成已知有冲突的旧整包再重跑，修复收口后才冻结运行一次最终完整/cold，独立验收后按当前任务授权直接一次 changed live，不再身份确认。新聚焦/整包/CPU及最终材料结果将在外部绑定原始产物中记录，当前不预报通过。


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


## 2026-10-06 Gate-L 独立 PASS，接续 M01–M03

实际 packet26 单次 primary/tokenize，8055/441，原生 research_required/waiting；原费用结算与 exact-owner 自然释放。独立129输入验收 PASS，实际读集 released/retained=[]。完整19 1997 + cold1 属于冻结76d964/5326ac身份。L01 done、25/49、累计13次primary；正文未验证、旧14费用UNKNOWN保留。当前直接实现 M 的原生工具读取、Session材料恢复和同账本epoch控制，完成后独立Gate-M，不再做身份类确认或另抽L样本。任务细节及来源见 stage04_L01_acceptance_20261006.md。

### M 段首批实现（尚未 Gate-M 验收）

新增 scoped_reads.py：同一 TaskStore SQLite 保存具名 read-set/发行句柄/累积调用与实际返回字节，原 owner claim/session/snapshot/revision/fence 检查；RPC 仅接受 grant/range，不开放发行或路径。task-tools.ts 原注册表提供 V2 可用 c2p_read，耗尽要求停止 owner loop。V1工具面不改。当前真实 Python 聚焦12通过，包括双进程竞争、Worker RPC重启、摘要种类不能由模型改标、原始JSON包装UTF-8字节计量；这不证明V2真实循环已接通。

新增 context-policy.ts：真实 Session append/surface derive，原材料四类及源摘要匹配，summary不能满足，替换后明确恢复并await flush；恢复后重新度量/同原账本及真正V2循环接通仍待完成。context-replay.test.ts 使用实际 Session replacement/replay，不冒充真实compaction辅助调用验收。新裁决文件纳入 validator 来源清单。

一次合并聚焦运行发生43 PASS/1 setup composition_drift：期间修改 scoped_reads.py 引起绑定测试读取不同身份；属于本次验证安排错误，不是接受结果。停止跨测试改源码，首批收口后重新运行受影响的原测试，不另跑L全量/live。

首批收口后实际验证：`python -m pytest -q tests/integrations/dsh/test_scoped_reads.py tests/integrations/dsh/test_worker_protocol.py` 45 PASS/92.38s/exit0/session68499；随后增加 read_grant composition 复核后，`python -m pytest -q tests/integrations/dsh/test_scoped_reads.py` 最新12 PASS/exit0/session56472。原构建与stage最新exit0/session97788；实际隔离Node `context-replay.test.ts` 首轮1PASS/1FAIL（测试漏 original sourceEventSeqs），按原Session合同补真实shadowed节点引用；fresh output02最新2PASS/0FAIL/exit0/session14972，无skip/cancel/todo，实际事件报告在 `/tmp/c2p-dsh-m-context-native-20261006-02/events.jsonl`。原始失败报告保留。日志及进度 `/tmp/c2p-dsh-m01-m03-development-20261006-01/`。

接续明确：M01/M02均仍未标完成、Gate-M未裁决；V2真实循环/最终assembly材料守卫/每请求稳定ID及原账本累积预算/真实DSH compaction辅助调用/epoch唯一terminal/source-bound多步恢复仍需接通。不要将两个Session测试称作完整compaction验收；不再为L compatibility抽样。用户允许普通低风险决定直接执行，不重新询问身份授权。

### M 段 V2 合同与原账本 epoch 控制（2026-10-06，未验收）

新增 WriterEpochLimitsV2/WriterTaskContractV2 与 FrozenWriterInputV2，明确版本选择；原V1 Literal[1]与单请求入口保留。冻结时标准化限制，合同版本/限制必须对应原冻结对象；共用原内容owner及全部schema/witness/formula质量门。私有 context.materials RPC 返回完整原 request.input_payload 对应TaskView、原请求ref及task/session/snapshot/revision，不另写材料编译器、不给摘要事实权限。新增 epoch_accounting.py 只读原 DshInvocationEventV1 和原reducer，累计已花费/未结算输入输出与请求数，证明not-sent不收model/content debit，unknown不当零；不建第二费用账本。

新增 epoch_tools.py 在原TaskStore数据库记录不可变原ArtifactRef支持的工具来源/候选准入，所有raw候选在内容guard前登记；第一次非法terminal仍消耗唯一候选，第二个保存拒绝来源并关闭epoch；跨进程互斥、不重置额度、摘要/跨session/request及篡改原来源拒绝。原真实 TerminalArgumentCapture block-end 的await回调已增加显式V2登记分支，V1行为保留。新Python裁决来源进入原validator清单。

实际验证：最新40 PASS/41.45s/exit0/session38786/reaped；原隔离启动器真实Node 3 PASS/exit0/session4260/reaped（Session替换/恢复/replay + 原V1技术draft与新进程receipt恢复），没有skip/cancel/todo。typecheck/build/stage实际exit0。原core reader在默认沙箱的Node子进程只给文件容器事件，6项失败；允许真实本机子进程的原命令复验23 PASS/exit0，不改reader或重写失败。命令、源文件SHA及原日志见 `/tmp/c2p-dsh-m01-m03-development-20261006-01/v2-foundation-evidence.json`。全部handles已回收，未新增真实模型、修改服务或操作canonical旧占用。

下一步仍是正式M整段：动态V2实际请求/发送门和逐请求度量、原账本辅助role计划、独立绑定compaction子会话且保留Writer绑定、所有请求自然完成/原owner释放与unknown恢复、真实多步及强制compaction集成和独立Gate-M。**本批只是基础与回归验证，不能称V2模型循环或真实compaction已接通，M01–M03不标完成。** V2发送目前仍被原单请求adapter的V1解析/sequence限制拒绝，不能通过覆盖V1 max_model_requests绕过。当前总25/49、Gate-L历史独立PASS，必要普通可逆决策直接做，不重复身份类确认；旧14费用UNKNOWN不改变。

## 2026-10-06 · M 原生压缩事务与实际材料/读取接线

直接完成普通实现选择，无新增确认、真实模型调用或后台恢复操作。Gate-L 保留独立 PASS，25/49；Gate-M 仍未验收。

- 原 Worker 新增私有 `context.read_grants`：仅原公开 Writer TaskView 导航，额度来自冻结 V2 合同；重复发放不重置计数，V1/取消拒绝，不开放私有 section/read-set/golden。
- 原 `KernelAuthority.persistChildBinding` 在实际子会话装入原材料恢复、源标记请求检查及有界读取；读取失败合入 epoch abort，后续实际请求记录/准入拒绝。当前 V2 发送门仍保留拒绝，不能宣称实际多步已接通。
- `EpochCompactionEngine` 只定制实际 DSH `BasicCompactionEngine.summarize`；保持原压缩事务/日志/替换策略。私有 authority 回调要求独立 child、真实 usage、自然耗尽、原 settlement ref；不走直接 llm.stream 或伪造 parent `llmStreamCall`，隐式重试拒绝，每个原 transaction 只消费一次。该回调尚未接到生产辅助发送器。

新观测：`python -m pytest -q tests/integrations/dsh/test_multistep_context.py tests/integrations/dsh/test_scoped_reads.py tests/integrations/dsh/test_worker_protocol.py` exit 0，49 passed / 104.19s，session 7550 terminal/reaped。后续仅 TS 压缩 cache/cap 校验及 TS 测试调整，未改变这些 Python 逻辑；不声明跨版本全量身份验收。

最终 candidate typecheck/build/stage exit 0，sessions 66212/38245 terminal/reaped。原隔离启动器实际执行 `epoch-compaction.test.ts context-replay.test.ts serial-writer.test.ts`（命令使用绝对路径），fresh `/tmp/c2p-dsh-m-compaction-20261006-02/events.jsonl`：12 passed / 0 failed / 0 skip，exit 0，session 87788 terminal/reaped；11 为实际 SDK 压缩/Session 与明示的辅助回执 stand-in，1 为原 V1 实际 native 假 provider 正文及新进程恢复。不能替代实际 V2 辅助 child/原账本证据。compileall exit 0。

可续跑结果与当前源码 hashes：`/tmp/c2p-dsh-m01-m03-development-20261006-01/native-compaction-and-read-wiring-evidence.json`。剩余集中在动态 V2 每步 wire/计量/原账本发送、真正 compaction child/辅助计划、整个 epoch 正常完成与原 owner 释放；收口后再做阶段独立验收。


## 2026-10-07 · M 动态请求准入与逐步完成登记（Gate-M 未验收）

直接实施可逆决策，不增加身份审批、真实模型请求或 canonical owner 操作。原 Gate-L 独立 PASS / 25/49 保留；M01–M03 不以测试数量标完成。

- 新 `step_admission.py` 和原 Worker 私有 measure/reserve-step 接线：原 SDK 实际动态 wire 与原冻结选项/系统/完整材料/工具 schema 对照、重新 tokenizer 计量；按稳定 sequence 在原唯一调用账本注册累计计划及预留。未知/未完成费用拒绝下一步；实际双进程争同 sequence 只有一方得到原预留，不增加第二余额库。
- 新 `step-renderer.ts` 在独立本地 HTTP 接收器观察实际 SDK native serializer，不寻址真实模型；禁止隐式 retry/外部端点，拒绝伪 usage/生成结果。实际新增工具历史进入第二个 wire，原模型端点到达数 0。
- 实际 SDK 发现 `defineTool` 隐式参数对象根为 open，和 Kernel 预期不一致。现关闭其原编译 schema 对象，同时作用于实际注册 wire 与 SDK execute validator；未知路径参数在执行前拒绝，未放宽 read-set 或质量门。
- 新 `step_completion.py`：V2 每步完成须原预留/request digest、原材料 ref、原 Session/header/context、完整 native delta/block/usage/finish、step/end、工具调用/返回及原 pre-schema 参数来源全部相符。第二请求不得复用第一请求的 Session，旧 V1 完成凭证不适用于 V2。`KernelAuthority` 接入真实子会话的 pre-step：上一导航步 Session flush 与原费用结算先于下一步；terminal 留给原 ingest，拒绝继续生成。尚未提供完整 V2 driver/整 epoch release，因此不能称真实多步已跑通。

实际命令与结果：Python 新完成 fixture 首轮 12 PASS/12 FAIL/exit1（fixture 缺 provider；补实际模型字段，未改生产校验）。修复后 24 PASS/104.51s/exit0/session5150；增加同 assembly 旧 Session 复用反例后 25 PASS/107.63s/exit0/session45152。再收口真实 read-first 工具注册顺序并增加 native 原始来源/工具 end 矩阵，聚焦 6 PASS/25 deselected/27.85s/exit0/session83724。这些 Python Session 为明示 UNIT fixture；不冒充实际 SDK 多步。

原隔离 Node 首轮 step-renderer + serial-writer：3 PASS/1 FAIL/exit1/session79699；其中原 V1 技术正文/新进程恢复 PASS，失败为上述 SDK schema 差异。修复后 fresh `/tmp/c2p-dsh-m-step-renderer-20261007-01/events.jsonl`：实际 SDK 3 PASS/0 FAIL/exit0/session2141，无skip/cancel/todo，真实模型请求0。当前 pre-step TS 接线 typecheck exit0/session76348；build exit0/session95105（outputs digest cfdbf3e54c90b212029aa7589bce8125bfd729b5811baad52030b9c0fca0d5c8），stage exit0。compileall、git diff --check exit0。全部启动 handles terminal/reaped；未重跑 L 全量或 live。

逐项证据、当前源 SHA 与准确未完事项：`/tmp/c2p-dsh-m01-m03-development-20261006-01/dynamic-step-admission-and-completion-evidence-20261007.json`。下一步直接接完整 `runMultistepWriter`、最终全 epoch 受信 quiescence/原 owner 释放及真正独立 compaction child/原辅助预算，完成整体实际循环与恢复，再交独立 Gate-M；普通身份变化不再请求授权。README 的旧“当前”解阻入口已标历史，旧14费用 UNKNOWN 不变。


## 2026-10-07 · 实际两步 Writer、整 epoch 释放与新进程恢复已接通

在前一批证据后继续实现，没有请求身份授权。增加显式 `runMultistepWriter`，原 `runSingleWriter` 保留 V1 两消息/单步门；新增 `epoch_completion.py`，逐项核对整个 SDK Session 和原请求/工具来源/费用事实，再由原 `SerialBackendAdmission` 事务记录 `DshEpochSerialBackendReleaseV2` 释放，unknown/未完成拒绝。原 V1 验证抽成同语义 helper、历史 reader 增加严格 V2 版本；未操作 canonical 后端或旧14费用。

实际 SDK 接线发现并修复三处边界：恢复/导航采用真实 `PreStepDecision.messages` admitted batch，由 SDK 在 system 后写日志，发送前 flush，不修改 provider body，也不容忍 system 降成 user；唯一 system 首位/逐字 guard 保留。仅冻结非thinking DeepSeek 可接实际 serializer 的空 reasoning_content，占位本身全部计量，非空/其他角色拒绝。Session header/context 按原 SDK 变化日志继承最新原值，每个请求另以真实 assistant ordinal、自己的实际 assembly/wire、usage 与工具 raw 源校验，不能复用旧完成证明。

fresh 实际联测 `/tmp/c2p-dsh-m-actual-loop-20261007-06/events.jsonl` exit0/session59705/reaped：1 PASS / 0 FAIL / 0 skip / 89.0986s。实际 Loader/SDK/原pi-ai HTTP及原Python Worker：一次 calibration＋两步 task，实际具名导航 read → 原生 terminal → 原质量 assessor/Publications → 整 epoch 自然原 owner 释放 → 全新 Worker 恢复同 receipt，新增发送0。原 reducer usage34输入/22输出，requests2/pending0，backend empty，domain pending_validation。全部 provider 为隔离假服务，不是 Qwen live、normal CLI cutover、Verified 或 Gate-M。

原 V1 单步正文与新进程恢复在 output01 PASS（该组合exit1源于另一个新V2 test失败）。output01–05 失败均保留：system顺序、SDK角色变换、空reasoning占位、变化日志、测试错用不存在的输出统计字段；未篡改旧结果。output05已实际完成两步并释放，只在恢复前的测试字段断言失败，output06补完真实新进程恢复。

最终受影响反例：`python -m pytest -q tests/integrations/dsh/test_dynamic_wire_compat.py tests/integrations/dsh/test_step_admission.py::test_completed_session_cannot_close_a_new_request_with_identical_assembly tests/integrations/dsh/test_epoch_completion.py` exit0/session98732/reaped，9 PASS/43.43s；其中 Session 为明示UNIT fixture，original Worker/SQLite实际运行。最终 typecheck exit0/session26011；build exit0/session11919，outputs333cc401b465e83ca802260b87fa084d449441194f5a64fe04c63aa1cc8f2250，stage/compileall/hygiene exit0。

当前 source SHA、准确命令和边界见 `/tmp/c2p-dsh-m01-m03-development-20261006-01/actual-multistep-owner-release-and-recovery-evidence-20261007.json`。下一批集中真正独立 compaction child＋原辅助 role plan/fees、强制压缩整体联测及剩余 normal V2/读取 revision 合同，再收口阶段必要验证和独立 Gate-M。整体25/49不变，任务不按单个成功样本提前标完成；没有新增真实模型/服务变更/旧占用恢复。


## 2026-10-07 · 独立 compaction child 与强制压缩完整联测收口，进入 Gate-M 阶段验证

真实 SDK 流程已完成“导航 read → 独立 compaction child → 原生 Writer terminal”，沿原 TaskStore、RunInvocationBudgetEnvelope、调用 journal/reducer 与 exact-owner release；辅助 child 不覆盖原 Writer binding。原 Kernel 私有发行 transaction/input/prompt/cap 绑定，compaction 无工具/plain text，独立角色显式声明；所有实际 wire 重新序列化、计量并经同发送门。真实压缩后原完整材料通过 Session 记录恢复，最终实际 provider payload 逐项核对。原 V1 路径保留，公开 Host API 显式 V2 分流，正常 JSON CLI 仍 V1，未默认切换。

Python 聚焦 session39439 exit0/reaped，95 passed/253.75s（后续持久 invalidation 尚未包含）；真实 Node 五文件 session46571 exit0/reaped，14 passed/0 failed/0 skip/234.1867s。其中11为实际 SDK/Session 加明示回执 stand-in；3为实际 provider/原 Worker：强制压缩3请求51/33/pending0、整 epoch 原owner自然释放与新 Worker恢复0新增发送；未声明压缩预算实际辅助发送0/末步Writer0，原17/11费用保留、fake owner held；原V1单Writer及新进程恢复通过。证据 `/tmp/c2p-dsh-m01-m03-development-20261006-01/actual-compaction-epoch-evidence-20261007.json`，actual events `/tmp/c2p-dsh-m-stage-native-20261007-01/events.jsonl`。typecheck4371/build29438/stage exit0，outputs6ded3d8380f2e7d1d69b1df2a6901eb0be70b5bbe986b59872ef1d471e7dd131；随后 Python owner 边界变化需当前阶段复验，不复用旧完整身份。

M01 补实：原 TaskStore 增加仅撤销旧视图的 content_invalidations 元数据；原 Python owner 提交原 ResearchPromotionLedger 的完整 claim_promoted 链后，revision/fence各递增1，immutable promotion ref 持久化。Worker 默认current_state读取原持久指针；无模型RPC发行/晋升、无新的事实许可、不更新原claim/binding/receipt或费用。新内容仍须原编译/freeze及新epoch。真实正在运行/重启Worker均拒绝旧read和旧context.materials，未完整晋升拒绝；最新 scoped+target unit 57 passed/12.31s/exit0/session32381。首次新test错误遗漏contract_ref出现schema_invalid，保留13pass/1fail，修正测试参数后复验通过。

完整验证计划12新增M全部必需Python/Node文件，缺文件预先拒绝；不把旧plan11当新完整证明。计划/任务恢复聚焦57pass/6fail/session86169，6项全因默认沙箱拒绝 bwrap NETLINK_ROUTE，正在原命令允许实际隔离namespace复验；不修改测试/门绕过。当前Gate-M未独立裁决，25/49不变。未新增Qwen调用、修改服务、canonical占用或旧14 UNKNOWN费用。

阶段计划12补充记录：session36216 原隔离目标准入6 passed/16.06s/exit0/reaped；diff-check/compileall exit0。完整首次入口误用通用module（43668 exit2）及未安装console script（exit127），均没有启动测试；随后正确method-agent函数入口87384开始原managed计划。阶段复核发现新晋升模型research_promotion.py未列validator来源，已SIGINT中止该未完成套件（87384 exit130/reaped），并具名停止它留下的pytest group54831，原operator由finally关闭。/tmp/.../m-stage-admission-20261007-01保留中断事实，不计PASS。清理后仅新增原research_promotion.py来源（不修改其逻辑），再在fresh02集中一次完整验证；不得冒充旧计划11/上一中断identity已通过。

独立M-E1：原QA /tmp/c2p-dsh-independent-m01-m03-20261007-01 235输入原strict report reader拒同名重复节点，原verify_epoch_quiescence实际3请求51/33RO复核通过，缺aux/缺step/重复step拒，未声明role0aux0final/17原费用保留。current02 argv亦包含四个同名draft entry，必不可认证，因此原3485 SIGINT exit130/reaped、具名pytest group61711停止，operatorfinally关闭；保留partial log不作通过。QA明确全读集released/retained=[]。仅host-provider真实title增加multistep/forced compaction/undeclared auxiliary budget实际模式，不改strict reader或任何业务门。先复验实际四entry聚合+原strict reader，成功后一次fresh03完整计划12/cold，避免末尾才拒报告。


## 2026-10-07 · Gate-M 独立 PASS，接续 P01–P04

原 complete03 session96522 实际 exit0/reaped，Python1853+56subtests、Node249、operator1，共2103；fresh cold1。原 CLI record-offline-receipt dsh-stage04/candidate tool-choice.2，root `/tmp/c2p-dsh-m-stage-admission-20261007-03`。独立 final QA 原严格 complete/cold reader接受，3462绑定输入、proof36706 exit0/reaped，全部直接/传递readsets released/retained=[]。M-E1 title-only修复的当前4入口strict4复验通过；六项namespace失败在原隔离命令复验6pass，未弱化门。

M01–M03 done，28/49；正式P01 in_progress。详细范围、原身份和证据见 `docs/dsh_execution_20260928/stage05_M_acceptance_20261007.md`。实际强制compaction3请求51/33/原owner释放、新Worker0发送；持久旧scope撤销闭合。没有新Qwen/tokenize/service/canonical操作，旧14UNKNOWN保留；normal JSON CLI仍V1，V2 Host API资格不是默认cutover/Verified。P批以唯一同主机根的SQLite队列/permit元数据实现全run/alias限额、公平和unknown阻断，费用继续原reducer；保留Gate-P独立门，不重复当前全量。
