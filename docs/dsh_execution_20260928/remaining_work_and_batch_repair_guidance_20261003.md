# Code2Paper DSH 全部剩余工作与整阶段修复指导

> 2026-10-03 18:03 状态接续：[四组返修验收](stage_four_group_repair_acceptance_20261003.md)已给出Gate-B/H PASS并正式登记Gate-K。
> 本指导§2–§4保留当时缺口与修法，现已收口；接下来执行§5的第03份，§6–§10仍按原阶段门推进。49项现为11 done / 38 planned，后续38项尚未实施，不再按旧检查点重复返修第01/02份。

> 后续实测接续（2026-10-03 16:05）：[冻结整包独立审查](stage_whole_package_review_20261003.md)已确认两侧 93 项、原来源/生命周期反例及类型通过。当前返修收敛到该报告 §3 的工具链、smoke 身份、回归和交付证据四组；本指导下面的首次核查事实保持原输入范围，完整后续 38 项路线继续有效。

本指导回应 2026-10-03 用户要求：把当前已知缺陷、尚缺验证和后续未实现工作一次列全，给出修改位置、实施顺序、验收反例和交付终点，避免逐个 helper 或报告字段往返交付。范围是原 8 份执行文档、49 个任务，不新增另一套任务编号或产品权威。

本次核查结论：第 01 份已有实质实现和 owner 自测，但交付身份、环境入口、清单生成和证据引用仍有确定缺陷；新的来源与生命周期实现需要完整独立差分验收。第 02 份 K01–K04 的组件成果保留，正式 Gate-K 等 Gate-H。第 03–08 份共 38 项仍 planned。本指导不登记任何 Gate PASS，也不授权 live、主图提前迁移或默认切换。

规范仍以 [仓库入口](../README.md)、[总设计](../code2paper_dsh_plugin_design_20260922.md)、[原执行入口](README.md)、[接口合同](interfaces.md)、[来源接口裁决 §6](h04_loop_origin_escalation_20261001.md) 和 [验证合同](verification.md) 为准。本指导是这些合同的集中实施补充，历史报告保留原输入范围。

## 1. 当前基线和证据范围

工作树为 codex/agentic-p4-benchmark-cutover，HEAD d48b4e4b22c94c82b45d2179ba452d72b164102d，既有 dirty 内容保留。本次只做诊断、无模型探针和指导文档；没有修改实现、共享 peer、候选 runtime、owner 封存证据或任务状态。

原台账共 49 项：B00、B01 为 done；B02/H01–H04 共 5 项 in_progress；K01–K04 共 4 项虽已 component PASS，正式依赖未闭合，仍是 in_progress；第 03–08 份 38 项 planned。该计数表示任务状态，不等于开发工时或产品完成百分比。

持久核查记录：[remaining_work_audit_20261003.json](remaining_work_audit_20261003.json)。其中保存原进度核查、新的补丁重建和 smoke 启动前探针、49 张任务卡与责任路径盘点。原始输出在该 JSON 记录的 fresh /tmp 根；文内结论仅绑定所列输入，不自动覆盖随后窗口二的修改。

| 对象 | 当前可确认结果 | 结论边界 |
|---|---|---|
| owner 第九轮封存 | 26 个登记文件的 bytes/hash 全匹配；两份原日志各记录 92 pass、0 fail、0 skip | 证明现存 owner 日志及封存一致；本轮未独立重跑这两套行为测试 |
| 类型声明 | 两包独立 tsc 退出 0；两个 index.d.ts 及 dispatch-origin.c2p.d.ts 与两侧候选相同 | GHS-3 的类型生成部分已确认；不代表交付清单和文档全部正确 |
| 补丁可重建性 | 用 pristine base 的 4 个输入文件，在 fresh 临时根运行原补丁脚本，退出 0；生成的 5 个文件全部与交付相同 | 覆盖补丁实际改动文件；未冒称新跑了完整 runtime provision/install |
| 源码构建 | source patch 等于源码工作树 git diff HEAD；两包源码 JS 与 -built 同字节 | delivery hunk JS 与 monorepo 编译 JS分别绑定，不要求不同打包形式互相逐字节相等 |
| 内核保留 | 历史已验 791 份 source/test 哈希无差异 | 保留 K01–K04 component；不重跑无变化的 4129 全量 |
| 当前直接 doctor | 指定 delivery 候选退出 1：peer link does not point at the frozen runtime | 当前共享链接指向 -built；属于交付环境未收口，不能解释成来源机制已复发 |
| smoke 入口 | 设置 delivery 的两个候选环境变量，在 read_manifest 前截获：仍选默认 .dsh-dev/runtime | 启动前因果探针，无进程启动、HTTP 或模型调用；此前 QA 自定义 driver 的成功仍保留自身范围 |

当前身份必须按候选逐行成组，禁止跨行拼接：

| 候选 | runtime tree 前缀 | 该候选 staged build receipt 前缀 | staging tree 前缀 | 声明范围 |
|---|---|---|---|---|
| delivery：0.2.0-rc.1+loop-origin.1 | 671daa1a | bce226e5 | 6f0c39cb | 正式 Gate-H 待验候选，需完整 B02/H01–H04 |
| source-built：0.2.0-rc.1+loop-origin.1-built | 3076d2fc | c10d1bca | 88341665 | 源码等价证据，Node 行为和源码/类型/构建对应；不声称 B02/doctor |

以上完整 hash 见核查 JSON。当前 compatibility/_020/w2_delivery 将 c10d1bca 与 6f0c39cb 放在同一组，是两个候选的混合身份。两个候选 outputs_digest 相同不使 receipt 可以互换。

## 2. 当前所有已知未闭合事项

本节将确定缺陷与验证缺口分开。验证缺口要求补足证据，不预先宣判实现失败；已确认有效的修复不重做。

| 编号（本指导内部索引） | 分类 | 证据和影响 | 完成位置 |
|---|---|---|---|
| D1 | 确定缺陷 | pristine→delivery 实际变化 5 文件；manifest、compatibility 和 loop_origin_setup 硬编码 touched 只列 4 个，漏 dispatch-origin.c2p.d.ts | §3.1 |
| D2 | 确定缺陷 | build receipt 与 staging 跨候选混用；当前共享 peer/global lib 属于 -built，delivery 直接 doctor 失败 | §3.2 |
| D3 | 确定缺陷 | scripts/dsh_dev_smoke.py 不消费候选选择，输出硬编码写 dev.DEV/evidence；环境变量无法使原脚本测试目标候选 | §3.3 |
| D4 | 确定缺陷 | evidence 的“本轮”身份表仍是旧 hash；interface-diff 和源码来源模块注释仍描述已删除 take/entry-ack；_020 的 README fragment 与实际标题不一致 | §3.6 |
| D5 | 确定缺陷 | compatibility 的 check-compat.log/b02-dev.log 不存在；实际为 check-compat-delivery.log/b02-pytest.log。封存 doctor 的 staging=fc454aa0，与最终 delivery staging=6f0c39cb 不同 | §3.6–§3.7 |
| V1 | 验证缺口 | GHS-1/2 的新实现已存在且 owner 自测通过，但尚无针对本次候选的完整独立 Gate-H 结论 | §3.4–§3.7 |
| V2 | 已定位的覆盖缺口 | C25 只跑 normal/prepared；C26 实际是 A/B 共存→销毁 B→A 恢复，没有执行报告所称“销毁 A→新建 B”原序列，也没有同时存活时 A/B prepared 归属对照 | §3.4 |
| V3 | 交付证明待齐 | 26 文件封存不等于全部被测 source/test/fixture/driver 的前后绑定；所有原 AT、当前测试集合和最终同一身份必须有映射 | §3.7 |

GHS-4 已按原裁决收窄为源码等价证据，保持这一范围即可；不再把补一套 -built Python worker 当作本批默认必修项。GHS-3 的类型部分和补丁五文件重建已获得正证据，主要修清单生产者和整包绑定。

## 3. 窗口二一次完成原第 01 份

窗口二仍负责 B02/H01–H04、窄 runtime 来源补丁、TS、工具链、peer、build/stage 和专属交付文档。以下是一个连续阶段内的工作，不是八次派工。正常修复、聚焦回归和失败后的同域修复连续进行；完整包满足 §3.8 后再交独立验收。

### 3.1 修清单生成和源码到候选的对应关系

负责文件：scripts/dsh_dev.py 的 loop_origin_setup、inventory/tree_digest；loop-origin.patch.py；loop-origin-source.patch；两候选 manifest；compatibility.0.2.0-rc.1+loop-origin.1.json；原 development environment/candidate-selection/staging 测试。

路径约定：补丁及 interface-diff/evidence 位于 integrations/dsh/dev/runtime-0.2.0-rc.1/loop-origin/；toolchain.mjs 位于 integrations/dsh/dev/toolchain/；兼容清单位于 integrations/dsh/；运行候选位于 .dsh-dev/candidates/；本次固定源码工作树为 .dsh-dev/sources/loop-origin-020/。后文同名简称均指这些现有文件，原任务卡的完整责任路径同时保存在核查 JSON 的 tasks 中。

1. touched 从 pristine 和 patched 的真实 inventory 差分派生，包含新增、修改、删除；与补丁脚本实际输出交叉核对。删除当前“四文件”硬编码，当前正确集合为两包 JS、两包 index.d.ts 和 agent-loop/dispatch-origin.c2p.d.ts。
2. 保留受允许改动域的检查：实际差分必须与登记一致，并落在本次窄补丁范围。不能为了不漏文件而直接允许整个 runtime 随意变化。
3. 固定 source commit、lock、源码 patch 和构建命令；delivery 由 pristine+hunk 得到，-built JS 由固定源码构建得到。类型从固定源码 tsc 生成，补丁如嵌入生成字节，登记输入/输出 hash 并验证同字节，避免手工维护两种声明。
4. 补丁在 fresh 根重建，完整候选生成后再核整树、新增声明依赖和 Loader 实际解析。未知基树、重复打补丁、原 hunk 不符必须明确拒绝。历史候选、历史证据不重封。
5. 扩原测试：故意遗漏新增声明、额外改一个未授权文件、把 source-built hash 写入 delivery 均被拒；合法五文件重建通过。测试验证实际生产者，不仅比较一份手写预期列表。

退出条件：实际差分、patch 输出、manifest、compatibility 和文档完全同集合；两条构建来源能各自重建，类型与源码对应。

### 3.2 固定候选选择、构建和最终环境

负责文件：toolchain.mjs 的 selectedCandidate/linkPeers/toolchainState/build/check；scripts/dsh_dev.py 的 assert_selection_agreement/select_candidate/toolchain_state/verify_build_receipt/verify_staging；原 sandbox/staging/candidate-selection 测试。

1. 延用既有独占 peer 规则；候选参数、候选环境变量和根目录必须一致。build/stage/test/doctor/CLI 与其子进程消费同一选择，冲突拒绝而非回退默认环境。
2. 将 runtime、toolchain、build receipt、outputs、stage、实际解析路径按 candidate_id 分组。开发交付检查同时核“字段属于谁”和“实际字节是什么”；只比 outputs_digest 不够。
3. 当前工具链 install 会执行 npm ci，普通候选切换不应依赖重新安装。可在既有工具链加入窄的离线 activate（拟实现）：先核已安装 compiler/lock/依赖字节和目标 manifest，再切唯一 peer 并记录选择；失败不得自动更新信任基线。若复用现有受控切换方式，交付唯一实测命令及同等校验。
4. 最终验证顺序建议 -built 先、delivery 后；delivery 重新形成与本候选匹配的 global build/stage，并作为最终活动开发环境。每次切换前确认前一运行结束，禁止两套 check:compat 争用共享 lib/peer。
5. QA 需要同时读取两侧时，使用已验证的 namespace 只读 peer/receipt view；不能在审查中 rebuild/restage 候选。该视图必须指向候选自身的 staged receipt 与实际 runtime，不用替身修改业务逻辑。
6. 检查 toolchain 回执的 frozen_runtime 等声明是否与当前候选自洽。若回执本来只绑定 compiler，需要明确区分稳定编译器事实与本次候选选择；不得在 doctor 输出中展示旧 runtime 摘要却称当前整组一致。

退出条件：delivery 的正式命令直接成功；两侧各自 receipt/stage/runtime 自洽；错误候选、错误 receipt、错误实际解析均具名拒绝；最终 peer 不被最后一条 -built 命令留在错误目标。

### 3.3 修正常 smoke 入口，不只依靠 QA 自定义 driver

负责文件：scripts/dsh_dev_smoke.py 的 main/证据输出；scripts/dsh_dev.py 的候选选择和 EVIDENCE_DIR；原隔离测试。

1. main 在任何 read_manifest/require_compat_bundle/command 前，按 launcher 的同一合同解析候选，调用选择一致性检查和 select_candidate。命令行候选与环境冲突仍拒绝，不复制第二套默认规则。
2. 输出使用所选候选的 EVIDENCE_DIR 或显式 fresh run 根；移除写 dev.DEV/evidence 的默认根硬编码。每次输出登记 candidate、runtime/staging 身份、composition 和零模型 turn。
3. 增加启动前测试：显式候选、仅合法环境选择、参数/环境冲突、缺候选、默认旧环境五类；截获实际 launcher argv/cwd/输出路径。加入“目标候选 smoke 不写旧 evidence”的负例。
4. 修复后用正常脚本分别验证 delivery 的 web 和 compat：真实 HTTP 200、非空 JS/CSS assets、关闭后端口释放、零模型 turn、日志认证 URL 脱敏。旧 QA driver 的成功不冒称正常脚本已修。

退出条件：文档给出的正常命令本身选中正确候选并完成 HTTP/清理合同。

### 3.4 一次审清来源、prepared 和 deployment 生命周期

负责原 owner：DSH 源码 packages/core/agent-loop/src/agent.ts、dispatch-origin.c2p.ts、index.ts 和 packages/llm/llm/src/index.ts；同步源码 patch/hunk/types；Code2Paper request-accounting.ts 只保留 Host 原职责；扩 cancellation.test.ts 和 request-seam.test.ts。

保留当前 static-import entry、模块私有派发器和生命周期注销方向。审查完整调用链 AgentLoop.prepareRequest→prepareCall→prepared record→establish→runLoopDispatch→真实 runtime→waterfall→Host→adapter；若实际反例失败，由所属边界修复，不再在外围叠加信号/材料/时序猜测。

必须满足五条不变量：来源只由真实 loop 派发创建；capability 不穿过公开 resolver/可包装成员；prepared record 绑定真正拥有它的 runtime；公开等价调用在创建和全程迭代中均不继承来源；销毁只注销自己的 runtime，合法未销毁实例仍可用。

| 验证面 | 必须执行的场景 | 观察与通过条件 |
|---|---|---|
| 合法正例 | prepared、真实一次 NO_ADAPTER→loop fallback、同 deployment 两活跃 child A/B 交错 | child completed；每个合法请求 R/D/S/adapter 各一次，互不误拒 |
| 公开调用 | stream、公开可调用的 streamWithRegistration、prepareCall 返回 handle、预持 handle、runLoopDispatch 伪 capability | 保护会话零额外 reserve/adapter；合法 child 仍完成；普通不受保护 provider 仍成功 |
| 观察时机 | 真实准备等待、reserve 等待、dispatch 等待、同步 internal/get、async hook、llm/stream listener | 相同 ID/signal/完整请求/快照均不能预消费；攻击确实进入观察点，不以 import error 或无触发算拒绝 |
| Proxy | resolver 返回转发 Proxy，所有相关成员包装；prepared 和 fallback 两条路径 | 包装实际触发，截获实参不能获得合法 admission；成员 receiver 保持真实转发语义 |
| Symbol/实例身份 | inspect kRootRuntime 的取得路径、prepared record 归属和运行中实际解析；使用公开可达反射/转发对照 | Symbol 名称本身不是秘密证明；观察者不获得派发能力，真实 runtime 归属不能依赖未验的代理身份 |
| 惰性流 | 自定义 Symbol.asyncIterator 获取、next/return/throw、延迟迭代和结束后重放 | 公共流创建与迭代均隔离；真实合法流及清理不丢上下文；过期调用不新增发送 |
| 销毁重建 | 原 GHS-2：A 正常→销毁 A→新建 B→B prepared/fallback | B 两路均完成、各计一次；重复销毁安全，不残留旧注册 |
| 共存归属 | A/B 同时活跃，分别 prepared；两者 fallback；销毁任一后另一者再跑 | prepared 不串 runtime；歧义 fallback 拒绝且不结算；只余一个后两路恢复 |
| 失效资源 | 保留旧 prepared handle 后销毁所属 deployment、取消准备中的 child | 旧资源不能转投新 runtime；不误清其他实例，不把未发送判成成功 |

C25/C26 现有覆盖仅是该矩阵的一部分。补原序列和并存 prepared 测试时，断言 adapter 所属实例与 session、账本事件关联，不能只看 stopReason 或合计次数。对 Symbol/Proxy 尚未复现的问题标验证待定，不直接写成漏洞；任意进程改写权限不属于本合同的普通观察者能力。

退出条件：原 GHS-1/2 与此前来源反例在两侧均有合法/拒绝对照；全部稳定场景进入原测试集合，独立 QA 能复验同一行为。

### 3.5 一次复核 B02 和 H01–H04 的完整原合同

下列矩阵表示不能漏验的范围。已有测试真实覆盖且实现未变时，保留并映射它，不再复制一套相同测试；缺口和变化影响面才补实现或反例。

| 原任务 | 必验行为 | 当前主要消费者/测试 |
|---|---|---|
| B02 | candidate/flag/env/root 一致；旧树及日常只读、无共享可写 inode；断网 mock；继承密钥/代理/Node/Python 注入拒绝；保留端口；缺 bubblewrap；合法 worker/lock/import；发现全部测试 | dsh_dev.py、toolchain.mjs、dev/tests、sandbox/staging/candidate-selection；正常 smoke |
| H01 | Loader 真正装入 bundle；缺包/inject/重复服务/坏 Config 失败；root/child 同 standing generation；scope/兄弟/销毁和正常工具入口 | index.ts、preset/cordis 配置、loader/composition |
| H02 | claim 后创建、setup 内完成可信绑定；阻塞绑定时零材料/零请求；旧 fence/旧父/伪 hint/provider 对象不一致拒绝；创建取消清理 | session-binding.ts、role-dispatch.ts、binding |
| H03 | raw delta/normalized/parsed/prose 分层；call/turn/step/isError 精确关联；坏 schema/双 terminal/terminal 后工具/closing-only 拒绝；未完整调用不能借别人完成；0.2 合成错误不算成功 | terminal-result.ts、terminal/provenance |
| H04 材料 | prepared 单次/config 约束；完整 messages/tools/config/cap digest；两个回执等待后最终 abort/fence/材料复核；接受回执 detached/deep-frozen | request-contract.ts、request-accounting.ts、request-seam/cancellation |
| H04 结算/资源 | 缺 usage 不归零；未知 cap 拒绝；next/adapter 不冒充 HTTP；throw/break/abort/return/recorder 失败各有事实；同步抛错/异步拒绝/永不返回清理有界 | cancellation C1–C18 及实际断言 |
| 联合恢复 | 同一可信 child：reserve→dispatch→adapter→terminal→settle→真实 flush→新进程从落盘字节重建 committed；无权请求不污染任何来源层 | joint-child；terminal 的真实 flush/partial 故障对照 |
| 组成约束 | retry/title/compaction/PTC 在该阶段确实关闭；非法第二请求拒绝；正常 Web 与兼容 Web 可启动且退出 | composition/loader、观测 adapter、正常 smoke |

资源范围必须具体：iterator return 超时、signal.aborted、child dispose 或本地 idle 不是远端停止证明。托管进程才使用独立 cleanupSignal 的 waitForExit，只有 true 证明其范围静止。H 阶段 recorder 是明确的兼容 fixture，持久余额权威仍在后续 R02。

### 3.6 由实际产物生成交付身份和引用

集中修复文件：compatibility.0.2.0-rc.1+loop-origin.1.json、h02_interface_freeze_020.md、interface-diff.md、evidence.md、H04_request_evidence.md、w2_delivery.md，以及实际生成器/工具链。

1. 使用一个可复算的开发交付检查入口，读取现有 runtime manifest、staging record、候选自身 staged build receipt、source patch、测试命令/结果和类型产物。可在既有 dev 工具新增 audit_candidate_delivery（拟实现）；这是证据校验工具，不是新产品账本，也不提前实现 I01。
2. 从上述输入派生候选分组和文档当前摘要；跨候选 receipt/stage、漏文件、坏链接、失配 hash、缺必测结果均返回非零。提供只检查模式，QA 不通过重写字段“修好”输入。
3. 当前正文写最新 API；历史内容明确标注日期、旧树、旧验证范围，不仅在顶部补一句历史提示。同步修源码模块和补丁注释，删除将 take/entry-ack 描述成当前接口的段落；区分“TS private 方法”与“JS 不可取得”。
4. 修正所有实际日志名及 README fragment。日志中的 candidate/receipt/stage 与声明值逐一匹配；26 文件 hash 相同只证明封存未变，不证明其内容一定对应最终候选。
5. doctor 的旧 fc454aa0 staging 回执保留为历史，不改原日志里的 hash。最终 delivery 环境稳定后重新运行 doctor 取得新证据，再更新索引。B02 同样绑定其真正执行的输入。
6. 在原工具链测试加入混合 receipt/stage、遗漏第五文件和错候选命令的拒绝对照；交付检查核引用文件是否存在。当前 API 说明与代码集中人工复核，不为自然语言措辞增加脆弱的断言。文本历史允许旧值，但当前区必须能区分；不靠全仓替换 hash 处理历史。

退出条件：交付清单可从磁盘重新生成/核验，正文和机器清单引用同一组当前事实，历史证据不可被重新标成最新。

### 3.7 最终验证、冻结和差分 QA

按以下顺序完成整包，避免“验证后又改 types/patch/文档身份再沿用旧结果”：

1. 先完成实现、测试和当前接口描述，运行聚焦反例；失败回同一 owner 连续修复。固定最终 source、测试/fixture、源码 patch、候选选择、完整实际读取输入。
2. 生成并核对两侧候选；先 -built 的源码等价验证，再 delivery 的完整运行验证。涉及共享 peer/lib 的命令串行，别让后一个候选污染前一个证明。
3. delivery 最终运行显式候选 check:compat、原 B02 完整目录、doctor、两种正常 HTTP smoke、受影响 execution identity 回归及 patch hygiene。-built 运行完整 Node 原套件、来源/生命周期对照、独立源码/type parity；不补报未执行的 B02/doctor。
4. 每条命令保存 argv/cwd/非敏感选择环境、真实退出码、原始脱敏输出、实际测试集合/skip/timeout 和输入摘要。timeout、零测试、必测 skip、启动失败各自登记；禁止只保存外层 shell exit。
5. AT 映射落到“实际节点＋断言行为＋候选身份＋日志”，覆盖 §3.4/§3.5，而不是 92 这个数量。新补测试后数量自然变化，不以固定数量作为通过门。
6. 检查源码/测试/fixture/driver/patch、types 编译依赖、runtime inventory、toolchain、global 及 staged receipt、peer 在其验证窗口前后是否变化。报告输出不参与自引用 hash；产品 engine 身份仍按原算法计算，文档变化影响该身份时不能复用旧准入回执。
7. 所有运行结束并核对自己实际进程后，封存到候选外稳定根、交付完整清单并明确释放本批实际读集/写权。不能以受限 namespace 看不到进程就声称宿主全部清空。
8. 独立 QA 先校验冻结输入，再执行原 AT 和差分；集中列全发现及影响面。缺陷返回原第 01 份连续修复；没有新的外部依赖时不逐发现等用户重新派工。

最终命令模板（候选已合法激活、smoke 已按 §3.3 修好后使用；不是现在已通过的记录）：

~~~bash
export C2P_DSH_CANDIDATE='0.2.0-rc.1+loop-origin.1'
export C2P_DSH_DEV_ROOT="$PWD/.dsh-dev/candidates/$C2P_DSH_CANDIDATE"
npm --prefix integrations/dsh run check:compat
python -m pytest -q -p no:cacheprovider integrations/dsh/dev/tests
python scripts/dsh_dev.py --candidate "$C2P_DSH_CANDIDATE" doctor
python scripts/dsh_dev_smoke.py --composition web
python scripts/dsh_dev_smoke.py --composition compat
python -m pytest -q tests/regression_20260917/test_execution_identity.py
git diff --check
~~~

上列命令分别记录状态；smoke 实际候选参数以修复后的唯一接口为准，环境选择必须有前置测试。新的独立 QA 在冻结候选上只读运行，不执行会重建/重封的 check:compat；用已有 launcher 的测试模式和被核验的候选 view 执行原集合。

### 3.8 本阶段的一次交付完成条件

窗口二一次提交：D1–D5 关闭；§3.4/§3.5 所有原合同有当前候选证据；合法调用恢复且非法调用拒绝；源码/patch/types/runtime/build/stage 对应；正常入口环境可复现；全部引用可读；证据和读集释放齐备。owner 标 submitted_for_independent_qa，不自批 Gate-H。

独立 Gate-H 通过后，LEAD 核对内核保持及正式依赖，再放行 Gate-K。期间窗口一不重复实现 K01–K04、不重跑未变全量、不提前写 C/R。若新增补丁实际影响共享 Python/validator 合同，集中说明影响并只重验真实影响面。

## 4. 第 02 份的剩余工作

| 任务 | 保留成果 | 尚需完成 |
|---|---|---|
| K01 | 严格注册、来源/身份、legacy 只读已验组件 | Gate-H 后核对依赖及源字节保持；后续 C03 消费原 reader，不复制 registry |
| K02 | 不可变 generation、CAS/fence、多进程和故障恢复已验组件 | Gate-H 后正式依赖确认；C03 局部提交和 F02 全文事务分别接原 owner |
| K03 | 同次 manifest 字节与真实 reader、索引投影已验组件 | 正式 Gate-K；后续消费者保持验证与使用同一字节，不再次读漂移 active |
| K04 | 完整请求/页身份、发送/恢复边界和真实调用方已验组件 | 正式 Gate-K；后续 DSH dispatch 在 R03 接线，不以组件 PASS 代替跨语言运行验收 |

组件无新实测缺陷时没有额外编码任务。第 03 份所需原 owner 复用图已在 .agent/implementation.md 登记，直接继承，不再启动一轮重复调查。

## 5. 第 03 份全部待实现任务

前置：实际 Gate-H、正式 Gate-K。窗口一独占 Python、protocol.py、validator 来源清单；窗口二负责 C00/TS/唯一 build-stage。按 I01→C01→C00→C02→C03→C04 连续完成一个阶段。原任务卡见 [03_writer_contract_and_worker.md](03_writer_contract_and_worker.md)。当前 src/code2paper/integrations/dsh/ 尚不存在，以下拟新增模块不是现有能力。

| 任务 | 具体修改和交付 | 必须一次带上的验收 |
|---|---|---|
| I01 | 在 authoring_execution_identity.py 和新 protocol.py 提供同一 composition 构建/校验原语；包含 runtime/lock/Node、真实解析字节、bundle/source/build、preset/schema/renderer/tokenizer/config | 源码不变但 JS 改、依赖改、symlink 目标改、Loader 解析别处都拒绝；不扫 home/session/cache，不预登记未来 validator 文件 |
| C01 | 新 writer_contract.py/protocol.py 定唯一 Python 私有合同、派生 TaskView、结果及 wire schema；冻结 task/epoch/read-set/三类页摘要/post-clamp cap；Python 算 canonical digest | Python/TS 双向 golden：Unicode、null/absent、union、extra、重复键、整数范围；身份变化可见，记账序号不改变内容 revision |
| C00 | 新 writer-request.ts 和 Host 私有 prepare_projection；使用公开 assemble/render＋固定 native 文本 Writer 组成，产出不可变 WriterWireProjectionV1；Python 字段交窗口一修改 | 实际 pi-ai 接隔离假 HTTP/SSE，比对组装、loop 请求和最终 wire；工具/schema/model/sampling/thinking/cap 都核对；准备零发送；首版未覆盖图片/文件转换明确拒绝 |
| C02 | 从 section_writer.py 的 structured_caller 抽原 decode/binding/research/callback、formula splice、parse/normalize/assess；旧 caller、_settle_recorded_writer_attempt、新 facade 共用；prepare 消费 C00 投影并计量/必要重编 | 三路径同输入/响应正文、失败码、metrics 一致；现本地 settlement 缺 decode/splice，要在抽取时补齐；所有 Python LLM/网络出口设拒绝哨兵；非空 atom/target、heading-only、错公式/extra paragraph 和真实 composition 漂移反例 |
| C03 | 新 result_ingest.py/facade.py 消费真实 Host 绑定和 raw terminal envelope；JSON pointer→允许角色 lexical span；用 K02 产出正文/acceptance/authorship 的局部不可变事务 | Writer 自报 accepted、Host 补词、错误来源拒绝；同 task/epoch 换幂等 key 提交不同结果仍冲突；回包丢失重试返回原 receipt；缺独立语义验证保持 pending_validation |
| C04 | 新 worker.py/protocol.py/facade.py；有界 UTF-8 JSONL RPC，stdout 只协议、stderr 日志，1 MiB 帧/64 KiB 读块及 artifact handle；Host 私有方法与模型工具分开 | 跨 run/task、任意路径、未知版本/字段、重复键/非有限数/超帧拒绝；鉴权先于缓存；无隐藏 LLM；慢模型不占短 RPC；R01/R02 未落地前不返回假的 claim/reserve 成功 |

阶段末联合跑一个 grounded 技术页（含非空 atom/target 和真实 accepted Formalizer 包）、一个合法无 atom 作者页及非法响应集。真实 worker→共用 parser/assessor→局部发布 reader 往返，不能由手工拼 accepted 替代。Gate-C 只批准无模型合同与往返，尚不批准实际运行派发。

先交好四个跨阶段接口以减少后返工：I01 composition 由 C02/R03/R04/A01 共用；C00 投影由 C02 计量冻结、R03 发送前复核；C03 原始来源进入 F01/F02；C04 的 task/epoch/fence/幂等合同供 R01–R04 延续。接口没定清时先用真实 fixture 双向验证，再扩后继模块。

## 6. 第 04 份全部待实现任务

前置 Gate-C。窗口一负责 R01/R02、R04 Python 和 A01；窗口二负责 R03、R04 TS、V02、build-stage；V01 联合完成。原任务卡见 [04_serial_writer_integration.md](04_serial_writer_integration.md)。目标是一 run、一 Writer、一个 mock 请求的真实业务闭环。

| 任务 | 具体修改和交付 | 必须一次带上的验收 |
|---|---|---|
| R01 | 新 task_store.py/facade 持久 task/outbox/claim/epoch 和单 run 租约；复用原 fence，task_store 只持引用 | 两个 Host 同 epoch 只有一个有效 claim；准备后崩溃、旧 fence、迟到回包、回包丢失；重启不清零 epoch，不用 PID/TTL 证明静止 |
| R02 | 在 unified_invocation_ledger/unified_context_models/writer_attempt_ledger 原 owner 扩真实 DSH 事件，经新 invocation_adapter 和 worker RPC 接入；lease 内重查预算/unknown/材料后持久 reserve | 余额在 prepare 后耗尽、记录失败零发送；重复事件幂等、冲突拒绝；usage 缺失保留未知费用；adapter 入口与 transport 证据等级分开；已落盘响应本地结算不重发 |
| R03 | 新 kernel-client.ts/workflow-driver.ts/execution-policy.ts，把真实 subprocess worker 接进 Host：claim→创建绑定→实际请求复核/reserve→派发→flush/record_output→ingest | 真实 Python worker，无假 RPC；未绑定/过期 claim/第二请求/变化的 prepared 配置零发送；dispatch 前重核 I01/C00；TS 不存第二本余额 |
| R04 | task_store/invocation_adapter/kernel-client/workflow-driver 注入真实持久边界故障；统一 reducer 新进程恢复 | reserve 前后、dispatch 后、terminal 后、record_output 后、commit 后都测；unknown 不重发/退款；有响应只本地恢复；父退出子仍活跃不解锁；独立 cleanupSignal，waitForExit false/抛错保持阻断 |
| V01 | test_serial_writer_e2e.py、serial-writer.test.ts、pi-ai-wire.test.ts；真实 DSH Loader/child/Session＋真实 Python builder/parser/Binder/composer/publication，仅 provider 响应 mock | 合法 receipt 与 immutable 成员；research_required→waiting、坏内容、unknown、cap 漂移；实际 adapter 的假 HTTP/SSE wire；零隐藏 Python LLM，单页不设置全文完成 |
| A01 | 修 CLI _record_offline_receipt_main 和原 build_offline_suite_receipt；从真实 Python/Node 必测集合、runner/argv/报告/退出码/身份构建覆盖，不默认填四组 label | 当前代码仍存在默认 REQUIRED_OFFLINE_TEST_PLAN、CLI 未传实际覆盖的问题；先做单节点假完整最小反例，再测 Node 缺失/失败/零测试/必测 skip/伪 label/身份漂移全部拒绝 |
| V02 | 新 cli.ts/操作入口显示 requested/effective 配置，消费同一 I01 composition 和 A01 回执；默认串行，parallel=true 明确 unsupported | 原入口默认不切；伪造/过期/局部回执拒绝；真正 CLI 走完整 Host 闭环，新增 CLI 必测纳入阶段回执 |
| L01 | Gate-V 后按具体 live 协议另获授权，核 8006/qwen38-27b-nvfp4、131072、health/models/队列/KV 与真实 wire/tokenizer/预算；至多一个 primary、无自动 retry | tool 参数/raw/usage/finish/局部接收全绑定；能力 probe 也计 live；失败停止并按 owner 分类修复，不无变化重抽样 |

Gate-R 对应 R01–R04，Gate-V 对应 V01/A01/V02；L01 是独立小型兼容门。首次实际局部 Writer 交付应在 V01/V02 明确展示原始输出、领域验收、未闭合原因和恢复路径，不能继续只展示环境测试总数。

## 7. 第 05 份全部待实现任务

前置 L01，顺序 M01→M02→M03→P01→P02→P03→P04。职责和完整路径见 [05_multistep_and_concurrency.md](05_multistep_and_concurrency.md)。这些工作不作为当前 Gate-H 的额外前置。

| 任务 | 修改方向和主要位置 | 完成行为 |
|---|---|---|
| M01 | facade.py/task-tools.ts 按 task read-set 发行限量句柄，区分导航与 exact evidence | 跨 snapshot/越域/摘要冒充 span/超读取量拒绝；新证据经 Python 原 owner 晋升并失效相关 revision |
| M02 | 新 context-policy.ts＋request-accounting；RunCapsule 派生，压缩后从内核恢复产文必需材料并重新计量 | 强制 compaction 后实际产文请求仍有作者语义/occurrence/excerpt；装不下回原编译 owner；辅助模型请求全部入账 |
| M03 | multistep Python/Node 真实恢复测试 | 一个 epoch 最多一个 terminal candidate；请求/input/output/工具量/时限均有界；换 child/重启不清零，已发送失败留花费 |
| P01 | 新 backend_scheduler.py；同主机唯一 SQLite、alias→resource group、run 公平轮转和 FIFO；费用仍原账本 | 真多进程/两 run/两 alias 共享限额；一个 unknown 阻断整个组，容量还有空位也不新发；配置/数据库分裂拒绝 |
| P02 | execution-policy.ts/cli.ts/artifact-view.ts 实现显式并发配置和实际有效值 | 默认关闭；开启默认叶任务 2/backend 1；父/子/verify/辅助合计守 run 上限；降低限额排空，不退款；增限用新执行配置 |
| P03 | task_store.py/workflow-driver.ts 固定 wave 和单一 join，父等 child/verifier 不占叶槽 | 同 section revision 单写；兄弟失败保留独立成果；新 revision 只失效相关任务；少一个结果不能当 join 完成，无父子死锁 |
| P04 | test_scheduler_multiprocess.py/concurrency.test.ts 独立进程故障和公平性复核 | 停止/重启/旧 permit/迟到 response 不双发；unknown 不 TTL 解冻；没有超额、永久等待或饿死 |

Gate-M 与 Gate-P 分别验收；离线研究可以准备，不能在 L01 未过时自报多步集成完成。

## 8. 第 06 份全部待实现任务

前置 Gate-P。先 G01–G03 状态承载与真实 Research 图恢复，Gate-G0 后再 G04–G08 原生角色。任务卡见 [06_langgraph_workflow_migration.md](06_langgraph_workflow_migration.md)。既有 Python 流程能力不自动等于其 DSH 接线已完成。

| 任务 | 修改方向和主要位置 | 完成行为 |
|---|---|---|
| G01 | product_authoring_graph.py、checkpointing.py、新 workflow_adapter.py：严格 opt-in handler/route/saver/thread_id | 缺任一 handler、LangGraph 或 saver，未知 route 都拒绝；单一合法后继确定推进，不额外调用规划模型 |
| G02 | research_graph.py/autonomous_method_agent.py 扩现 snapshot/immutable payload/strict restore，持久 context/route/decision/trace/budget/deadline/verifier 配置来源 | 从冻结引用重建对象，结果读 manifest；无 last_result/闭包兜底，代码/config漂移拒绝旧任务恢复 |
| G03 | test_research_process_resume.py 按原任务卡对真实 9 节点/条件边做新进程恢复 | 包括 supervisor partial_gap/compile/no_tool_calls 和 compile compiled/partial/rejected/blocked；状态/预算/下一步/副作用与不中断基线一致 |
| G04 | Research supervisor提案/enrichment/有限修复外置 DSH，Python 保留 observation/critic/compile/policy | 真 build_product_research_runtime 入口零隐藏 Python LLM；非法工具/跨 snapshot/无权 claim/额度耗尽拒绝；语义 revision 待独立 verify |
| G05 | publication_method_writer/workflow_adapter/role-dispatch 按原角色顺序接入；接管 planning 模型路径，16 节点合同齐全 | plan→Formalizer→同计划版本 Narrative→Writer/Realizer→验证→Binder；Editor/Rewrite 最小真实适配本阶段完成，不留到 F01；Realizer 无新措辞权 |
| G06 | result_ingest/原 Writer owner 增独立 verify 任务，冻结正文/evidence/validator/task identity 并按原规则合并 | Writer 自报 supported 不接受；错 revision/无支持句拒绝；缺验证保持 pending，编辑使旧回执失效，Verified 不放宽 |
| G07 | writing_callback_fulfillment.py/workflow_adapter：typed gap→Research→依赖重编→新 Writer | 正常写作和 research_required 共用 interrupt/receipt/resume；无新证据不能 fulfilled；lineage/预算跨进程延续，只失效相关材料 |
| G08 | full_workflow_recovery/no_hidden_python_llm 测试，真实产品入口覆盖全部角色和 16 节点 | outbox/checkpoint/output/ingest/commit 各边界恢复；旧 fence/停止后不新派；已存响应本地结算，unknown 不重发；不以 fixture executor 或 pending 占位宣称完整迁移 |

G03 先验状态，不能反向要求全部 DSH 角色已完成；G08 才要求全部必要分支真实闭合。G05 的最小 Editor/Rewrite 调用器由 F01 扩场景，不重复实现。

## 9. 第 07 份全部待实现任务

前置 G08，F01→F02→F03→F04；任务卡见 [07_editor_figure_and_delivery.md](07_editor_figure_and_delivery.md)。

| 任务 | 修改方向和主要位置 | 完成行为 |
|---|---|---|
| F01 | 原 Writer/final_text_authorship/role-dispatch 扩全文和 section-scoped Editor/Rewrite，同版本串行 | 未改 span 保持原来源；改文重做相关绑定/验证；删唯一支持、Host 补词、缺 response_ref 拒绝 |
| F02 | 原 _write_publication_outputs 接 K02 同一事务，正文/Candidate/Verified/authorship/acceptance/final-integrity 同版本 | 正常 Method 入口 g1→g2 每写点故障新进程可读完整旧/新版本；局部 accepted、缺 sidecar 或 Verified 不冒充 publication_ready |
| F03 | figure_planner/workflow_adapter 复用 IR/scene/relation，冻结正文版本及 section↔mechanism↔node/edge 映射 | 正常入口真正出图；反箭头/虚构模块/缺必要节点/旧正文图拒绝；caption 由允许角色生成；无 vision 标 not_measured，真实图像服务另授权 |
| F04 | artifact-view/cli/facade 做只读 operator export 与准确状态展示 | Candidate 不显示为 Verified；损坏/错版本拒绝导出；模型无管理 RPC，历史产物不升级为新 run 事实 |

## 10. 第 08 份全部待实现任务

前置 F04，Q01→Q02→Q03→Q04→Q05；任务卡见 [08_quality_and_rollout.md](08_quality_and_rollout.md)。

| 任务 | 修改方向和主要位置 | 完成行为 |
|---|---|---|
| Q01 | 在 A01 同一 live_admission_preflight owner 扩完整阶段必测集合，运行全 Python 离线＋Node＋桥接/故障/环境矩阵 | 必测 skip、零测试、子进程失败、身份漂移不能产生完整回执；offline-ready/live-ready 分开 |
| Q02 | 同冻结材料/确定响应对照旧 C0 与新 C2；test_execution_equivalence.py | 义务/公式/权限/验收/恢复不减少；协议/wire 差异有记录；全部失败与辅助/Research复用成本可复算 |
| Q03 | 事前冻结 quality-evaluation-protocol，按审计 §16.3 逐层授权 L1/L2/L3 | L1 grounded/无 atom 作者页/局部 repair；L2 全 EBCAR；L3 不同结构项目；确定硬门和盲评各报告，评审者/阈值在看结果前确定 |
| Q04 | 事前冻结 benchmark-protocol；C0/C1/C2 同任务/模型/预算/停止规则、隔离 session/memory/gold | 泄漏其他条件或 gold 则无效；不因 C2 专用 receipt 给质量加分；分母/预算不一致不宣称更高效；额外服务调用另授权 |
| Q05 | 汇总门与残余限制，演练旧固定引擎＋fresh root/已验证 Research import 回退；提交具体迁移材料 | 不把新 schema 强交旧版 resume；实际切换最后由操作者批准；默认切换/D5/release freeze 各保留原证据和授权要求 |

## 11. 减少后续返工的统一工作方式

1. 开工前一次列全“本阶段公开入口、实际消费者、合法正例、失败/恢复、身份和交付”的矩阵，按本指导追到原任务卡；不用上一轮发现列表代替完整合同。
2. 任何 API 变更同轮更新 source、hunk、types、消费者、测试和当前合同说明；任何候选变更同轮更新其 runtime/build/stage/命令视图。已有生成逻辑负责机器清单，人工文档引用派生结果。
3. 测试从实际行为观察权威：真实 adapter 到达、真实落盘/新进程 reader、真实消费者和逐项请求内容。测试名、通过数、相同输出 hash、DSH completed 都不单独证明阶段完成。
4. 每次返修先检查同一机制的相邻入口、对称生命周期和失败分支。公开 stream 出问题时同时核 prepared/fallback/回调/惰性迭代；销毁出问题时同时核重建/共存/旧句柄/取消，不等下一轮 QA 再逐个提出。
5. 新测试和验证脚本也属于输入。最终验证开始后不修改受测 source/test/fixture/runtime；确有必要变更时记录新候选，只重跑变化的影响面和规定的最终阶段集合。
6. 窗口按整阶段负责，文件单写；共享接口采用一次具体交接。最终裁决集中反馈全部发现，正常问题回原 owner 持续处理，不要求用户逐点续派。
7. 复用未变的已验成果，避免重复全量；扩大验证以具体新改动、失败或未决合同为依据。所有未测项明确分类到当前必修或后续任务，不能混写成“以后再看”。

一份指导无法保证未知缺陷永远不出现；本次交付承诺的是：原 49 项无遗漏、当前已知问题集中列齐、每个必修项都有修改责任与观察判据，后续反馈按整阶段和共同根因处理。

## 12. 可直接交给窗口二的执行要求

连续完成原第 01 份 B02/H01–H04，并按本指导 §3.1–§3.8 一次处理源码补丁五文件清单、候选身份/环境、正常 smoke 入口、来源与生命周期矩阵、原 H01–H04/联合恢复、全文 API/证据引用、最终验证与封存。保持当前私有来源方向及已验内核；缺陷由所属 owner 修，不削弱任何 gate，不引入第二账本，不把未来 C/R 伪装为已实现。阶段中间进展记录后继续，完整冻结包才交独立 QA；只在真实跨域协议冲突、接口能力不足或外部授权缺失时集中升级。

后续接续已完整列在 §§4–10：Gate-H→正式 Gate-K→第 03 份 Gate-C→第 04 份 Gate-R/V→单独 L01→第 05 份→第 06 份→第 07 份→第 08 份。各阶段内部按原依赖连续推进，不再拆成用户逐点审批。

[返回执行入口](README.md)
