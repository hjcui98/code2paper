# 第 03 份整批执行指令：唯一 Writer 合同与真实 worker 无模型往返

本指令形成于 2026-10-03，承接 [18:03 独立裁决 §4](stage_four_group_repair_acceptance_20261003.md)。**Gate-B/H 与正式 Gate-K 已通过；下一批为原第 03 份的 I01、C01、C00、C02、C03、C04，共六项。** 本文细化两窗口实施与交接，不新增任务或验收门，不表示实现已经开始。编写时台账仍为 11 done / 0 in_progress / 38 planned，六项均 planned。

整批终点：从已冻结的单页材料，经实际 DSH 请求投影、Python 唯一合同和真实 Python worker，完成无模型 prepare → record_output → ingest → 原 publication reader 读回；合法结果有可信来源和局部事务，非法输入按原合同拒绝。两窗口合交一个 `submitted_for_independent_qa` 包，由独立 QA 验 **Gate-C**。

## 1. 依据、顺序与当前状态

| 阅读顺序 | 文档与适用部分 | 本批用来决定什么 |
|---|---|---|
| 1 | [仓库文档入口](../README.md)及其架构权威顺序 | DSH 执行 Agent，Python 保留证据、预算、验收、发布权威；LangGraph 默认流程保持 |
| 2 | [DSH 总设计](../code2paper_dsh_plugin_design_20260922.md) §§8–10、14、15.1/15.2/15.4、21 WP1b | 接口分权、唯一合同、原 owner 抽取、组成身份、短 RPC 和取消原则 |
| 3 | [最新独立裁决](stage_four_group_repair_acceptance_20261003.md) §§3–5 | 已接受候选、H/K 放行、旧读集已释放、两个窗口的职责 |
| 4 | [原第 03 份](03_writer_contract_and_worker.md)全部六张任务卡及[原台账](task_board.json) | 任务范围、正式依赖、原 AT；本指令不削减这些要求 |
| 5 | [interfaces.md](interfaces.md) §§1–5、§7；[当前 H02 冻结](h02_interface_freeze_020.md) | 字段、版本、可信来源、真实 runtime API、资源所有权及幂等顺序 |
| 6 | [集中指导](remaining_work_and_batch_repair_guidance_20261003.md) §5；[verification.md](verification.md) §§2–4 | 全批缺口、Gate-C 范围、正反例与证据格式 |

日期较早的“Gate-H 未过／正式 K 等待／第 03 份不得启动”只描述当时的候选，已由 18:03 裁决接续。其产品合同仍有效，旧阻断状态不再作为本批前置。旧 H02 0.1.5 文档仅作历史参考；本批实际 API 按 `h02_interface_freeze_020.md` 的当前独立冻结部分。

当前分支为 `codex/agentic-p4-benchmark-cutover`，HEAD 为 `d48b4e4b22c94c82b45d2179ba452d72b164102d`，所有既有未提交内容作为起点。开发候选为 `0.2.0-rc.1+loop-origin.1`；其已验 runtime、receipt、stage 摘要见最新裁决 §3。`-built` 侧原证据只声明源码等价，不自动成为独立 worker 或生产准入证明。

`src/code2paper/integrations/dsh/` 及本批拟新增模块在本指令编写时尚不存在。另一个需要纠正的路径假设是：`integrations/dsh/compatibility.json` **已经存在，且是 B00 的历史冻结输入记录**；原 I01 卡片的“拟新增”标签不能据此覆盖旧文件。本批当前组成及证据索引另记于拟新增 `integrations/dsh/compatibility.stage03.json`，由窗口一写、窗口二提供实测输入；这只是记录路径细化，不能取代 Python 现场校验或充当 A01 准入回执。

## 2. 一整批的分工与推进规则

| 责任 | 窗口一 | 窗口二 |
|---|---|---|
| 主任务 | I01、C01、C02、C03、C04 的 Python 领域实现 | C00；C01 的 TS wire 消费者及双向 golden；真实 DSH renderer/adapter 联合证据 |
| 共享文件 | 独写 `protocol.py`、`authoring_execution_identity.py`、`VALIDATOR_BUNDLE_SOURCES` 和本批兼容记录 | 对共享 Python 文件提交字段、类型、拒绝语义与 fixture 需求，由窗口一落实 |
| TS 与构建 | 提供 Python 接口、fixture 和回执，不操作共享 TS 构建环境 | 独写 TS 消费者、相关 TS 测试；独占共享 peer、`integrations/dsh/lib`、build/stage/receipt 操作 |
| 联合交付 | Python 原 owner、真实 worker、局部事务和原 reader 证据 | 真实 Loader/child/Session、实际 pi-ai 假服务 wire、TS 消费及最终构建身份 |

实施顺序固定为 **I01 → C01 → C00 → C02 → C03 → C04 → 联合回归与封存 → 独立 Gate-C**。每个前置的有意义本地合同通过后，沿同一批继续；不必每完成一个 helper 就等用户重新派工。owner 自测不能把任务提前标成独立验收 done，正式依赖和原 AT 仍完整保留。

窗口二可在 I01/C01 期间交付实际 Loader/runtime/peer/build 的测量和公开 renderer 能力证据；C00 正式实现消费 C01 约定，不另造字段。等待交接时可准备本批 fixture、原 owner 对照与负例，不能凭假字段把后继接线写成已完成。两窗口不得同时写共享文件或同时改构建环境；交接记录说明当前可消费接口、输入身份、已过断言和待闭合项。

普通实现缺陷由对应窗口在本批连续修复。若实际公开 API 无法满足既定合同，集中提交最小反例、受影响 AT、可行方案和所需合同决策；保留不受影响的工作，不靠虚构 API、降低断言或返回占位成功推进。

## 3. 窗口一详细实施指令

### 3.1 I01：统一组成身份，核验实际运行字节

修改现有 `src/code2paper/agentic/authoring_execution_identity.py`，新建 DSH Python 包及 `protocol.py`，补 `tests/integrations/dsh/test_composition_identity.py`。复用已验开发 inventory/严格读取逻辑；新增的是生产 composition 原语及实际消费者的可复用合同，不重建一套开发隔离工具。

1. 同一组成对象绑定：实际 Loader 解析位置及 JS 字节、peer module 身份、bundle 源码/锁/构建输入和输出、DSH runtime 树、实际 Node、preset/persona/tool schema/renderer、Python 依赖与 worker 版本、有效 model/options/tokenizer/计量版本。保留原 engine/validator 身份；没有的 upstream source SHA 记 null，不借研究参考 SHA。
2. symlink 既核目标关系，也核实际解析目标字节；明确路径逻辑身份规则，不扫描可变 home/session/cache。manifest 中的声明不能替代实际读取与校验。
3. I01 先交可复用算法、必填字段与拒绝合同。C00 的新 renderer 落地后，按同一算法加入实际文件并重算；尚不存在的生产组成明确未就绪，不给未来文件编造摘要或登记到 validator 清单。
4. 原 `VALIDATOR_BUNDLE_SOURCES` 随每项实际落地的裁决逻辑更新，由窗口一单写。新增/抽取 helper 只要影响接受或拒绝，就必须受 validator 身份覆盖；不使用永远不变的外层版本号代替源码变化。

**AT-I01 必须实测：**源码未改而构建 JS 改；依赖 JS 改但 CLI/lock 未改；symlink 目标内容改；Loader 解析到另一个位置；新增裁决 helper 改动导致 validator digest 改；声明来源缺失明确拒绝。I01 不等未来 R03/R04/A01 实现才结束本地原语，但本批 C02 必须证明真实 prepare 消费该原语。

### 3.2 C01：先固定私有合同与跨语言 wire

新建 `writer_contract.py`，完善 `protocol.py` 和 `test_wire_schemas.py`；窗口二实现 `integrations/dsh/tests/wire.test.ts` 及必要 TS 消费代码。协议为 `c2p-dsh/1`，任务为 `WriterTaskContractV1`，结果为 `WriterTaskResultV1`，投影为 `WriterWireProjectionV1`；workflow/accounting/renderer/storage 各自显式版本化。

1. 私有合同保存实际 `build_publication_writer_request` 的完整输入或可验证重建引用、已完成 Formalizer 回执、冻结 Narrative/manifest/plan、resolved read-set 和不可变对象摘要。页合同包含 `author_surface`、`binding_contract`、`technical_bytes` 三类实际重算摘要。
2. 绑定 task/scope/epoch/content revision、engine/model/validator/composition/renderer/tokenizer、有效参数、post-clamp cap 和有限 epoch 额度；首版模型请求上限为 1。prepare 的预算值只作观察快照；内容 revision 与 claim/reserve 等记账序号分开。
3. Python 以原 canonical serializer 计算权威 digest；TaskView 由该私有合同派生。TS 只消费合同及引用，不重新拼作者、证据、formula/detail/atom 义务。
4. `draft / research_required / blocked` 的 required/nullable/union/extra 条件完整保留；`accepted`、authority、可信 caller 与预算裁决不属于模型可自报字段。冻结稳定错误对象、版本拒绝、artifact 引用和能力注入边界。
5. 交给窗口二一个可执行合同包：schema/类型、Python 生成的合法与非法 goldens、每例预期结果/拒绝码、摘要算法及字段解释。窗口二给回 TS 实跑结果；不只交换一份说明文档。

**AT-C01 必须实测：**Unicode、null/absent、union、enum、extra、重复键、非有限数、整数安全范围、路径/摘要一致性；改作者、材料、模型、工具 schema 或有效配置能改变身份；只变记账序号不使内容合同自行 stale。wire bytes 摘要与语义摘要分别登记。

### 3.3 C02：真实 prepare 与三条路径共用解析评估

在 C00 实际 wire 对应证据成立后，修改现有 `section_writer.py`、`publication_method_writer.py`，新增 `facade.py`、`test_writer_prepare_ingest.py`。复用已有 owner 调查，不另建 parser/assessor。

1. 从 `section_writer.py` 的 structured caller 抽取纯 decode、表示恢复、formula splice、parse/normalize 和原评估入口，保留原 binding/research/callback 拒绝语义。旧同步 caller、新 facade、`_settle_recorded_writer_attempt` 都调用同一实现；补齐本地 settlement 原来缺的 decode/splice，不复制三套逻辑。
2. 首版输入为一个真实编译并通过原校验的 Unified V2 页，Formalizer 已完成，Narrative/manifest/plan 已冻结。prepare 不调用完整 authoring orchestrator，不借 `binder_caller=None` 取消本来必须的语义任务。
3. 完成领域输入冻结 → C00 无模型投影 → Python 实际计量、cap 核对/clamp/必要重编 → 重取投影 → 冻结合同。重编次数有界；材料或 cap 改变就重新投影，不在 seam 临时改正文或 cap，也不按源码长度猜实际 token 开销。
4. 真实 prepare 每次核 I01 实际组成，比较领域材料与投影。错误 runtime/build/renderer 不得只在独立 helper 单测拒绝，而真实入口照常放行。
5. 对所有 Python LLM/网络出口设置拒绝哨兵。需要独立模型语义验证的内容返回绑定正文、证据和 validator 身份的 `pending_validation`；不能清空 verifier/Binder 或让 Writer 自己声明 supported。

**AT-C02 必须实测：**同一输入和合法/非法响应经过旧 caller、新纯入口、本地 response-unsettled settlement，正文、metrics、失败码一致；heading-only、extra paragraph、错误公式、错误 atom/target 绑定均拒绝。必须同时有非空 atom/target 的合法技术页及反例、合法无 atom 的作者 header 页；B01 的 detail-only 样例不替代这些义务。

### 3.4 C03：可信 raw ingest 与局部不可变事务

新增 `result_ingest.py`、`test_result_provenance.py`，完善 facade，按需修改原 `final_text_authorship.py`，继续使用 K02 的 publication owner 与真实 reader。

1. Host 绑定层注入 caller/run/task/snapshot/epoch/claim/fence，以及实际 child/session/turn/step/tool-call/request 标识；模型 JSON 中的同名值不是凭据。本批使用明确受控的测试调用上下文，不伪称 R01 持久 claim 已完成。
2. 分开保存真实捕获的 provider HTTP/SSE、adapter arguments delta、normalized terminal arguments、parsed 对象及最终 prose 的引用与摘要；没有捕获的层明确 `not_observed`。不能用 normalized 对象重序列化冒充原始参数字节。
3. 原始参数经同一 parser/assessor/局部确定性 Binder/composer，JSON pointer 映射到允许角色的 lexical span；正文、acceptance、authorship 引用走同一个 K02 不可变局部事务。Host 只做表示恢复与允许的确定性组合，不补句、改限定词或替换公式。
4. 幂等键绑定 method/execution/task/epoch、实际重算 payload/result digest 及 validator digest；另保留不可绕过的同 task/epoch 唯一正式终态。先校验实际调用者权限与 execution，再查既有不可变回执；仅新提交继续核当前 revision/read-set。旧 fence 不得创建新副作用，合法已提交重试按明确规则取回原 receipt。
5. `research_required` 返回 waiting；`blocked` 保留稳定原因与恢复动作；独立语义验证未完成保留 `pending_validation`。局部接受不设置全文 `candidate_complete / verified_complete / publication_ready`，C03 局部 Binder 不冒充 G05 最终全文 Binder。

**AT-C03 必须实测：**模型自报 accepted、closing prose 替代 terminal 参数、Host 添加词句、错误来源、原始流不完整、跨 task/epoch 均拒绝；commit 后回包丢失的同内容合法重试得到同 receipt；同 key 不同 payload、同 task/epoch 换有效 key 提交不同结果仍冲突；原 reader 读到的正文、acceptance、authorship 是同一 generation。

### 3.5 C04：真实有界 worker 与权限分层

新增 `worker.py`、`test_worker_protocol.py`，完善 protocol/facade。通过真实子进程 stdio 测试；测试驱动可以发送受控协议包，但不能 stub Python RPC/领域验收器来代替真实往返。生产 Host pump/kernel-client 的 R03 接线留在下一阶段。

1. UTF-8 JSONL 上使用固定 JSON-RPC 2.0 请求/响应；建立连接时核协议/schema/validator、支持方法与大小。stdout 只协议，stderr 只诊断；固定 method allowlist，不提供 arbitrary eval/import/path。
2. 首版最大帧 1 MiB，单次读取 chunk 最多 64 KiB；输入输出均有界。大合同与结果用内核发行、绑定 scope 与 digest 的不可变 artifact 句柄；不接收任意宿主路径，不截断后继续解析。
3. prepare/record_output/ingest 为 Host 私有。模型权限只按本阶段已实现的窄入口注册；单请求 Writer 预载材料，不能借此提前开放 WP3c 多步读取。operator export/配置/管理不是模型工具。
4. 每个 RPC 为有界短操作，不在一次调用内等模型或跑完整 Agent。R01/R02 尚未完成的方法明确 unavailable/unsupported，不返回虚假的 claim/reserve/settle 成功。
5. 单次读取取消与整个 worker 生命周期分开；在途 mutation 要有明确提交/取消终态或可观察 provider 进程范围静止。需要清理时使用独立有界 cleanup signal；`waitForExit` 仅 true 证明范围静止，false/抛错仍阻断，父进程退出或请求 signal 已 abort 均不足。
6. 所有新增裁决来源及时进入原 validator 清单，联测重新计算身份，避免刚完成代码就使用前一版本的合同/回执。

**AT-C04 必须实测：**跨 run/task、越权句柄/路径、重复键、NaN/Infinity、未知字段/schema、越界整数、超帧、坏幂等键拒绝；越权者不能利用已命中的回执缓存读到内容；慢模型不占 worker 短 RPC；取消/静止边界可观测；所有方法无隐藏 Python LLM 调用。

## 4. 窗口二详细实施指令

本节与 §3 共用合同。窗口二负责 C00 和 TS 消费，并交付窗口一需要的实际环境测量；保持 H02 已冻的创建期绑定、私有来源、Session raw/flush 和销毁语义。

1. **I01 支持：**在现有隔离候选中记录实际 Node/Loader/peer/runtime/build/stage/preset/schema 的位置与字节，提供可复用测量结果。不要把旧 package version、源码 SHA 或 receipt 自报摘要当作实际运行字节。Python 校验器和 canonical 计算由窗口一写。
2. **C01 TS 消费：**根据窗口一的 schema/goldens 实现严格解析与测试；双方共同锁定缺省/null/union/整数等拒绝语义。跨语言 fixture 可互相读取验证，但各自从真实 bytes 解析，不能只比两端复制的一份 expected digest。
3. **C00 自有接口：**新建 `integrations/dsh/src/writer-request.ts`、`integrations/dsh/tests/writer-request.test.ts`，实现 bridge 的 Host 私有 `prepare_projection(WriterInputRef, composition)`，返回不可变 `WriterWireProjectionV1`。这是本项目新接口；DSH 并没有因此多出一个已知 dry-run API。用实际公开 `SystemPrompt` assemble/render 与冻结 native 文本 Writer 组成，不访问私有 helper。
4. **证明三层对应：**分别捕获组装投影、真实 loop 的首请求、实际 pi-ai 适配器发往隔离假 HTTP/SSE 服务的 provider wire。逐项比较作者/证据实际 bytes、TaskView、terminal/tool schema、model、sampling/thinking、post-clamp cap；不得用自写“仿 provider serializer”替代实际 adapter。
5. **准备与验证分开：**prepare_projection 本身无 send、无 content attempt；wire 等价性测试会对本地假服务产生受控 HTTP 请求，另记计数，不冒称测试全程零网络。禁止访问真实模型或外部 provider，本批不调用 8006 live 服务。未覆盖的动态图片、文件及其转换明确拒绝。
6. **闭合双向握手：**Python 要求 cap/材料变化时重新生成投影；返回新的 bytes/组成/renderer/计量引用。最终 frozen 合同与投影一致；seam 只核验并沿原合同放行，不能补材料、变 cap 或掩盖差异。transport 随机字段只能按显式无语义白名单单独记录。
7. **配合 C02–C04 联合测试：**使用真实创建期绑定与落盘 raw terminal fixture，证明其可被 Python 真正消费；保留 flush/listener/资源释放要求。不得为本批成功提前编造 R 阶段生产 claim/reserve/pump。需要共享 Python 变更时交给窗口一，不自行改 protocol/validator。
8. **唯一构建责任：**TS 代码落地后由窗口二串行 typecheck → build → stage → test。按实际变化重算本批 build/receipt/stage/composition，旧 Gate-H 的 bundle 摘要不能给新代码背书；保留旧封存包、原 runtime 来源补丁和历史证据。若改动影响 H 合同，带上对应原回归；若必须改变已冻 runtime 接口，明确其影响和重新验收需求，不能静默换候选继续引用旧 PASS。

**C00 交给窗口一的最小可用包：**可执行 TS 入口；已达成本地合同的 schema/goldens；projection JSON/不可变引用；实际 loop 请求及假服务 wire 原始记录；比较白名单与差异断言；renderer/实际构建/运行组成摘要；合法、漂移、unsupported 正反例的真实命令和退出码。C00 不以“assemble 看起来一样”收工。

## 5. 四次交接与阶段最终演示

| 交接 | 谁交给谁 | 下一步开始前必须可核验 |
|---|---|---|
| 组成与 schema | 窗口一 ↔ 窗口二 | I01 同一算法及实际测量；C01 Python/TS goldens、版本、拒绝语义；Python 共享文件只有一个写者 |
| 实际投影 | 窗口二 → 窗口一 | C00 的 assemble/loop/provider 三层对照通过；prepare 无发送，cap/材料变化能重取投影 |
| ingest 与 worker | 窗口一 ↔ 窗口二 | C02 三路径一致；真实 raw/绑定能进入 C03；C04 真进程处理并由原 reader 读回，权限/幂等负例成立 |
| 整包冻结 | 两窗口 → 独立 QA | 六项全部 AT、联合接线、受影响回归、最终组成、原始证据、封存和运行释放同一批闭合 |

最终必须展示三组行为，不以测试数量替代产品结果：

1. **合法技术页：**含非空 atom/target、真实 accepted Formalizer 包和冻结页材料；从真实投影冻结合同，经真实 worker prepare/record_output/ingest，共用 parser/assessor/局部 Binder/composer，原 reader 读回同 generation 的正文/acceptance/authorship；所需语义验证未完成时如实保持 pending_validation。
2. **合法作者页：**无 atom 的作者 header 按其真实 scope 合法处理，与技术页义务区分；不得一律拒绝所有无 atom 输入来“通过”技术反例。
3. **非法与恢复集合：**材料/构建/renderer/cap 漂移、缺/错 formula/atom、额外段落、伪来源/Host 补词、坏协议/权限、冲突提交、提交成功但回包丢失；检查具体拒绝或同 receipt 恢复，不能只断言“抛任意异常”。

本批测的是无模型准备/结果结算、真实 renderer wire 与 worker 合同。下一阶段 R03/V01 才将完整持久 claim、真实预算 reserve、Host pump 与单 Writer DSH 运行串起来；本批不能据受控上下文宣布 Gate-R/V 已通过。

## 6. 实施后验证命令与结果记录

下面是实施后的命令，**编写本指令时未运行，拟新增测试不能因文件不存在、零测试或 skip 计通过**。先按 AT 做有针对性的开发验证，最终代码稳定后执行阶段联合回归。测试原始 argv、cwd、runner/Node/Python、候选、内层退出码与日志都要保存。

窗口一在仓库根运行本批集合和原 owner 回归：

```bash
python -m pytest -q tests/integrations/dsh/test_composition_identity.py tests/integrations/dsh/test_wire_schemas.py tests/integrations/dsh/test_writer_prepare_ingest.py tests/integrations/dsh/test_result_provenance.py tests/integrations/dsh/test_worker_protocol.py
python -m pytest -q tests/test_llm_section_writer.py tests/test_agentic_publication_method_writer_unified.py tests/regression_20260922/test_authoring_contract_closure.py tests/test_agentic_final_text_authorship.py tests/regression_20260917/test_execution_identity.py tests/integrations/dsh/test_publication_generation.py tests/integrations/dsh/test_legacy_characterization.py
```

窗口二在仓库根显式选择接受的开发候选，串行构建新阶段产物：

```bash
export C2P_DSH_CANDIDATE='0.2.0-rc.1+loop-origin.1'
export C2P_DSH_DEV_ROOT='/home/cuihengjia/agent/Code2Paper copy/.dsh-dev/candidates/0.2.0-rc.1+loop-origin.1'
npm --prefix integrations/dsh run typecheck
npm --prefix integrations/dsh run build
npm --prefix integrations/dsh run stage
npm --prefix integrations/dsh run test:compat
python scripts/dsh_dev.py --candidate "$C2P_DSH_CANDIDATE" audit
```

`test:compat` 通过现有隔离 launcher 运行并检查 staging；核实新增 `wire.test.ts`、`writer-request.test.ts` 都被真实发现执行，保留原集合全部必需断言。build/stage 会更新共享产物，仅窗口二执行；窗口一和 QA 不在其间运行依赖一半旧、一半新组成的测试。

本批抽取会改通用 Writer caller、settlement/validator 等入口。除上述针对性回归外，最终稳定候选应按仓库 broad-change 规则跑一次当下全量静态 `python -m pytest -q`，记录真实 collected/pass/fail/skip 与环境；不是为复现旧“4129”凑数量，亦不对未变旧基线反复重跑。失败先区分已有环境问题与本批回归，未通过或必需项未执行不能自称 Gate-C 已齐备。外部模型仍禁止；测试所需隔离本地假服务按限定范围运行。

受本批实际修改影响的 B02/Loader/H02/H03/H04 原回归须覆盖；若仅复用未变原 runtime 补丁，可引用已有来源等价证据并记录保持检查，不强制重建 source-built 树凑双份数量。最终运行 `git diff --check`；没有新代码变化、失败或未解问题时，不无故重复已过检查。

独立 QA 消费冻结包进行复验，使用只读验证/测试入口；`check:compat` 内含 build/stage，不能拿它作为“保持输入不变”的独立复验命令。

## 7. 一次性交付清单与停止位置

两窗口共用一个本批 delivery index，分别标明每份材料由谁生成。运行原始输出放新建 `/tmp/c2p-stage03-<唯一后缀>/`，最终封存复制到本批独立且不随候选重建而消失的稳定根（例如新建 `.dsh-dev/run/stage03-<唯一后缀>/`），不覆盖旧 Gate-H owner/QA 封存。worker 的 run/artifact 根须在隔离进程间显式共享可读，不能假设每个 namespace 的 `/tmp` 相通。

**先冻结输入，再生成该输入的证据。** 当前 `capture_engine_source_snapshot` 会纳入未排除的 Git dirty/untracked 文件，包含仓库内文档/JSON。`compatibility.stage03.json` 先写定版本、输入定位和预分配的外部证据位置，再捕获身份；最终 engine/composition 摘要及测试结果写到独立运行/封存根。不得向被自身摘要覆盖的文件回填同一个摘要，形成自引用，也不得临时扩大排除规则使漂移消失。测试后若更新仓库协调文档，明确记录读集释放、变化范围及测试所绑定的冻结身份，不能声称新工作树与旧回执完全同身份。

| 必交内容 | 完成标准 |
|---|---|
| 修改清单与状态 | 六项任务逐一列真实文件、接口差异、已闭合/未闭合项；主报告状态 `submitted_for_independent_qa`，不自批 Gate-C |
| 实际身份 | HEAD/dirty/source、Python/Node/依赖、Loader/runtime/peer、build/receipt/stage、renderer/schema/validator/config/composition；原身份与新身份范围清楚 |
| AT 矩阵 | AT-I01、AT-C01、AT-C00、AT-C02、AT-C03、AT-C04 各映射真实 `file::node`、输入 digest、行为断言、argv/退出码、原始日志和产物摘要；required skip/timeout/零测试不算通过 |
| 联合演示 | §5 三组场景的冻结输入、真实投影/wire、raw terminal、worker 通信、领域回执及原 publication reader 读回；未观测的来源不伪造 |
| 回归与限制 | 原 owner/TS/受影响隔离测试、稳定版本全量静态结果；pending_validation、未支持转换、未实施 R/G/F/L 语义如实记录 |
| 封存 | 最终源码/测试/fixture/运行 driver/配置/实际运行字节与所有原始日志的路径、字节数、SHA-256；日志先脱敏，凭据/URL token 不入包；封存后不继续边改边声明同一冻结身份 |
| 释放 | 所有本批命令返回；相关 worker、假 HTTP/SSE、child/Session 资源关闭，端口释放；实际清理结果与剩余进程有明确记录 |
| 文档 | 同步第 03 份交付证据、当前兼容记录及任务实做状态；保留原依赖/AT和未开始任务，不把计划当完成 |

停止点就是这份完整待独立 QA 包。独立 Gate-C 通过并登记后，下一批才按[第 04 份](04_serial_writer_integration.md)实施 R01–R04/V01/A01/V02。真实模型 L01 仍需其独立 live 条件和授权；本批不触发多步/并发、完整主图迁移、默认切换、D5 或 release freeze。

## 8. 可直接复制给两个窗口的启动指令

### 发给窗口一

```text
执行 docs/dsh_execution_20260928/stage03_batch_execution_instructions_20261003.md，
完整阅读 §1–§7，并按 §3 承担原第 03 份 I01、C01、C02、C03、C04。
依据最新 stage_four_group_repair_acceptance_20261003.md §4，Gate-H/K 已放行；
旧文档的等待状态只作历史。保留当前分支和 dirty 基线。

你负责全部 Python 领域实现、protocol.py、authoring_execution_identity.py、
validator 来源清单及 compatibility.stage03.json，以上共享 Python 文件由你单写。
窗口二负责 C00/TS 和唯一 build/stage；接收其实际运行测量，先交 C01 schema/goldens，
C00 三层 wire 对应通过后再完成 C02 prepare 接线，连续做 C03/C04 和真 worker 联测。
不要重建 parser/assessor/账本，也不要覆盖旧 B00 compatibility.json。

整批必须完成原六项 AT 的 Python 部分、三路径等价、原始来源/幂等、协议/权限/
取消反例及原 reader 局部事务读回。普通缺陷在本批连续修好，不每个 helper 停一次。
按 §6 执行针对性与最终稳定版本回归，与窗口二共交 §7 完整冻结证据包，
状态 submitted_for_independent_qa，等独立 Gate-C。不要提前实施 R/live/默认切换。
```

### 发给窗口二

```text
执行 docs/dsh_execution_20260928/stage03_batch_execution_instructions_20261003.md，
完整阅读 §1–§7，并按 §4 承担 C00、C01 TS wire 消费及联合接线支持。
Gate-H/K 的最新独立裁决已通过；本批继续原第 03 份，不再重做第 01 份整包。

先向窗口一提供实际 Loader/runtime/peer/build 测量；消费其 C01 schema/goldens，
实现 Host 私有 prepare_projection 和不可变 WriterWireProjectionV1。
用真实公开 assemble/render、真实 loop 与实际 pi-ai 接隔离假 HTTP/SSE，
证明作者/证据 bytes、schema、model/options 和 post-clamp cap 三层对应；
prepare 本身零发送，未覆盖动态文件/图片转换明确拒绝，不调用真实模型。

你独占 TS 消费者/测试以及 peer/lib/build/stage；protocol.py 和 validator 清单
只向窗口一提需求，不并行修改。将实际投影、goldens、wire 原记录和最终身份交给窗口一，
共同完成 C02–C04 的 raw 来源和真实 worker 往返，保留原 H 兼容断言。
普通缺陷连续闭环，按 §6 构建验证，按 §7 合交一个冻结包，
状态 submitted_for_independent_qa，等独立 Gate-C。不要伪造 R 阶段 claim/reserve，
不要提前启动第 04 份或真实模型 live。
```

[返回原第 03 份](03_writer_contract_and_worker.md) · [返回执行入口](README.md)
