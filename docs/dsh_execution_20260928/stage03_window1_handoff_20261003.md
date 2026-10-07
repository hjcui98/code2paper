# Stage03 窗口一活动交接（2026-10-03）

当前范围 I01/C01/C02–C04；owner 本地实施中，未声明 Gate-C。
窗口二继续独占 TS 和 build/stage；本窗口不执行 npm/build/stage。

## 可消费 C01 包

- Python 源码：`src/code2paper/integrations/dsh/protocol.py`、`writer_contract.py`。
- Schema 与真实 UTF-8 wire goldens：`integrations/dsh/wire-v1/`。
- 生成器：`tests/integrations/dsh/test_wire_schemas.py::export_wire_package`。
- 本地 Python 验证：`/tmp/c2p-stage03-w1-20261003/i01-c01.log`，28 passed，exit 0。
- 每例 `raw` 是实际解析输入；`wire_digest` 与 `semantic_digest` 分开；重复键、NaN/Infinity、整数溢出、孤立 surrogate、null/absent、extra、union 均有具名拒绝。
- canonical 沿原 `code2paper.agentic.digest.canonical_json_bytes`，SHA-256 前缀 `sha256:`；不以 TS 复制 expected digest 替代真实解析。
- 结果为 object root `{schema_version: 'WriterTaskResultV1', result: ...}`，`outcome` 为 draft/research_required/blocked；draft 沿原 PublicationMethodSectionOutputV1。严格 schema 见实际文件。
- private contract 不含 capability、caller 或可扣余额；记账观察另载。artifact 只有 scope/digest/size/type，无宿主路径。
- projection 为 WriterWireProjectionV1：实际 system_text/user_text/tools/model/effective_options/cap，绑定 input/task-view/terminal-schema/renderer/composition 摘要、measurement_ref 与 wire_equivalence_ref。字段不能用预期值替代实际测量。
- `derive_task_view` 直接复制原 request builder 的 input_payload；TS 不重新编 author/evidence 义务。

## I01 测量输入

`CompositionSpecV1` 位于原 `authoring_execution_identity.py`：Host 指定 files/trees/effective_config。
files 必须含 loader/peer/bundle_source/bundle_lock/build_input/bundle_js/build_receipt/stage/node/preset/persona/tool_schema/renderer/python_dependencies/worker/tokenizer/meter；trees 必须含 runtime/dependencies/python_runtime。
路径首版采用 absolute-resolution-v1，位置和实际 resolved 字节均绑定；runtime/dependencies 只可指向受控代码树，不能 home/cache/session。
树 inventory 抽取自原 scripts/dsh_dev.py 算法，开发入口已委托共用原语并保留 inventory wire；composition 使用 Python canonical digest。
upstream_source_sha 未观测时 null。尚不存在 renderer/worker 的完整生产组成不得先捕获为 ready。

待窗口二：实际 Loader/peer/Node/build/stage 测量；TS wire goldens 实跑；C00 assemble/loop/pi-ai 假服务三层证据、可执行 prepare_projection 与 raw terminal fixture。C02 正式接线会核这些材料，不把 Python fixture projection 当 C00 验收。

## C00 输入与封摘要（第二次交接）

新增 `WriterInputRefV1`（schema 同在 wire-v1）包含 request_ref、完整实际 writer_request、Python canonical TaskView JSON、完整 terminal_schema/native_terminal_schema、native_schema_enforcement、显式 terminal_instruction、model/options/cap 和 composition/renderer/input 身份。
`writer_request` 为原 LLMRequest 的 prompt_template_id/prompt/input_payload/schema_name/response_json_schema 完整投影；request_ref 是该 canonical JSON 的内核引用。task_view_json 必须逐字等于原 input_payload 的 Python canonical 序列化。

`native-terminal.schema.json` 是注册 shape；`native-terminal.enforcement.json` 明列未被 native 子集表达的约束。必须在实际 terminal 入口运行完整 schema guard（保留 required/nullable/union/extra 等所有域条件），之后 Python 原模型复验。注册 shape 单独不授予接受；不能以此声称完整 schema 等价性已验。

Python byte/seal utility 已可运行：`python -m code2paper.integrations.dsh.writer_contract seal-projection`，stdin 为未封摘要 projection JSON，stdout 为 canonical sealed projection。仅计算 Python 权威摘要；不授予领域 accepted/prepare receipt。正式 worker 私有方法之后承接这一纯 helper。

measurement_ref / wire_equivalence_ref 的依赖顺序：C00 假服务测试先实际记录测量、loop/provider wire 及逐字段对照，使用受控 Host artifact broker 发行不可变引用，然后封投影；无证据的首次 prepare 必须返回未就绪，不能填未来摘要。C02 将从同 broker 读取并核 input/renderer/config/schema 的绑定。准备本身不能为获得证书发送请求；C00 受控测试发送另计。

Terminal 指令：保留原 Writer 领域材料和真实 prompt；追加明确 terminal 输出协议（draft 内沿原结构，或 typed research_required/blocked），使用 c2p_terminal，不从 closing prose 取正文。如需转换原 JSON 响应指令，在 input 中显式记录 conversion，由三层对应实测；不能静默重写作者/证据。

`scripts/dsh_dev.py::inventory` 已复用原身份模块的 runtime_inventory，inventory wire 不变。请在本批稳定时带 B02 原回归；脚本仍由本窗口负责这一个 Python 修改，窗口二请勿覆盖。

## C00 evidence broker 合同（第三次交接）

已落地 `artifacts.py::ArtifactStore(root, TaskScope)`，受控 Host 按实际捕获 raw bytes 调 `put` 或 `put_json` 获 ArtifactRefV1，只有内核选择目录；read 重算 scope/bytes/semantic。root 需在 Node 与 Python 隔离进程间显式共享。

新增 `WriterMeasurementV1` / `WriterWireEquivalenceV1`，实际 schema 将导出 wire-v1。equivalence 的 projection_material_digest 覆盖 renderWriterInput 返回的完整 binding；loop_request_ref/provider_wire_ref/comparison_ref 指向各自实际捕获。comparison JSON 必含 binding、loop_digest、provider_digest；Python 还独立读取 loop/provider 字节核材料/schema/model/options/cap，不信 PASS 标志。
measurement 含 input/renderer/tokenizer/meter 绑定、实际 measured_input_tokens、context/safety/thinking/cap、measured_wire_digest；不能用源码长度或编造 token 数。Python prepare 还会调用 Host 注入的原 meter 对真实 provider wire 重新计量。

已写 `facade.py` 候选，prepare 尚未用 C00 实证运行，当前不能声称 C02 已完成。其依赖 current composition/renderer 明确；freeze_input 从原 _writer_section_inputs_v2 重建校验完整材料；render_input 构造 WriterInputRefV1；prepare 需真实 projection callback 与此前假服务证据，无证据不 ready。

## 实际入口返修与联合字段（第四次交接）

已修 scripts/dsh_dev.py 的 src 导入定位；当前真实 CLI 应不再因 code2paper 未 editable 安装失败。B02 原回归正在运行（provenance-b02.log）。窗口二可继续其正常 test/audit；不要覆盖这个单写 Python 文件。

局部 C03/C04 候选已落地；受控 parser/ingest 测试不声称 C00 已通过、生产 claim 已完成。Worker 为 private stdio，仅 initialize→固定方法，frame/chunk 1MiB/64KiB；当前不开放模型读取、claim/reserve/dispatch/settle。bootstrap 由 Host 明确 scope/context/composition/spec/run 根，不从 RPC/模型读取任意路径。

请联合证据使用 WriterMeasurementV1 / WriterWireEquivalenceV1 的实际 schema（已导出）而非 C00 测试自己的测量对象。provider_wire_ref 必须保存真实 HTTP body 原字节；不能以 JSON.parse 后 put_json 代替原 body。ArtifactStore.put(raw, media_type='application/json', semantic_digest=digest_json(strict_json_loads(raw))) 可以同时保留 raw bytes 与语义摘要。comparison 对象为 {binding, loop_digest, provider_digest}；projection_material_digest 是 Python digest_json(binding)。Loop raw 也分别保留，Python读 captured内容核验，非 matched/PASS 自报。

Python已按实际pi-ai provider tools 的 function.strict=false 对照；该固定表示差异明确记录。meter callback 改为接收真实 provider raw bytes，防止 canonical 重序列化改变计量。当前 C04 bootstrap 原 meter 保留 conservative_utf8_bytes_div_4 的真实代理计量；假服务联合测试应使用已明确 controlled-utf8-byte-id/1 的本地专用 meter（下一步补 Worker bootstrap），不冒称 Qwen token 测量。

C02 prepare 必須消耗完整 I01 composition、真实 staged renderer JS digest；新 renderer/worker 来源已进入 validator，最终全部 stable 后才抓最终身份与证据。不在源码覆盖的兼容记录内回填自身摘要。

CLI inventory 再次收敛为 `runtime_inventory.py` stdlib-only（不初始化 code2paper 包），scripts/dsh_dev.py 直接从自己仓库受控源码定位加载这一纯原语。合成 Gate-H CLI 副本现在也复制这个真实新依赖。上一次 candidate 测试的剩余问题是 Node spawnSync Python 的沙箱 EPERM 及移动中 build source digest；未删断言。B02-entry-unsandboxed.log 记录原激活回归的自动审批后实跑。

Python provider 对照还将明确允许 deepseek/off → thinking.type=disabled 的实际转换；不是将 thinking 放随机白名单。

## Full I01 / joint driver 输入计划

实际定位 `/tmp/c2p-stage03-w1-20261003/full-composition-plan.py` 和 composition-spec.json，最终capture会在代码stable后输出到候选可共享run根；Node driver在offline bwrap能读写，Host /tmp只作外层日志。配置已对齐 deepseek-v4-flash、provider deepseek、temperature0.2、reasoningEffort off、cap4096、controlled-utf8-byte-id/1。meter/tokenizer源码 local_meter.py 均进入validator且绑定实际字节；bootstrap允许显式32MiB（RPC仍1MiB）。turn/step允许实际整数或原runtime的字符串ID，禁止代替真实观察。

Python inventory已覆盖bundle实际external peer symlink：production只允许解析到composition显式受控树集合里的目标，链接关系/实际resolved位置和目标树字节全绑定；原开发inventory默认继续拒绝绝对/外链。不扫描home/cache、不排除peer使漂移消失。

窗口一所有Python候选已存在，剩余主要是full组成→stage03-project真实observe/prepare→workerprepare/record/ingest→原reader演示及最终回归。请窗口二在正式联合运行前完成其源码/构建并确认安静窗口（本文件外部身份计划不声明最终freeze）。当前sources身份仍会因两窗口修改而改变，开发中composition_drift如实保存；不重试旧身份来等“幸运样本”。

C04不再提供无实际读取操作的cancel_read占位RPC；单次消费者取消等待与worker生命分离由真实stdio等待/在途回执测试表达。worker.shutdown明确不证明provider scope；cleanup barrier仅接受waitForExit结果===true，其余保持typed阻断。

### 联合运行前最后合同校正

render_input现核原plan的单页有效cap及composition.options.maxTokens相等；不能静默用新cap覆盖旧plan/组成。prepare若context clamp需新cap，必须通过有界原owner recompile callback产生新frozen ref/组成再取投影；无callback返回cap_plan_recompile_required（不发送）。worker不等待重编/模型，Host完成该确定性准备再发短RPC。
已接受Formalizer的真实每条ActualRequestReceiptV2复验来源摘要/plan绑定、已消费obligation成功集合，保留早期失败与修复回执，不把normalized对象冒充原始provider参数。
所有私有源以及OutputEnvelope schema已导出；Python主体当前正在最终域测试，准备交给stage03-project的full输入。最终 Node build/stage由窗口二执行，窗口一不动。

## 正式联合重抓读集（stop_reason 修复后）

收到窗口二 actual SystemPrompt 定位和 finish.reason.kind 修复，旧 joint-1…5 / author-1 全保留失败记录，不改包。
新增 Python 82 passed，指定原 owner 265 passed；全静态套件运行中。
现在两窗口进入源/文档读集冻结：本条后窗口一只写 ignored run 与 /tmp，窗口二请也只写 ignored run；
确需修复时先显式释放并告知重新capture。joint-6 / author-2 将重新抓 full-I01，不复用旧合同。
cap 原 owner 正向重编联测随后执行。最终证据报告是在释放后另写，并区分文档变化后当前身份。

## 读集释放：联合正向通过，C01 数值词法反例待闭合

joint-6 / joint-author-2 / cap-recompile-1 均 exit0。实际worker+原reader+lost-reply技术/作者页通过；
cap4096→1024 经原 build_run_invocation_budget_envelope_v1 / build_consumer_invocation_plan_v1 / _writer_section_inputs_v2 重编，
新 actual provider/loop/projection 引用，旧plan在无callback时拒绝，不临时改cap。
现在显式释放以上读集，准备一项 C01 修复：Python strict Counter 对 JSON task_epoch:1.0/1e0 拒绝 schema_invalid，
而当前 TS decodeWire丢失number词法后 integer校验允许 Number.isSafeInteger(1)。
窗口一将增加实际 raw goldens（research_required positive / integral_float_counter / integral_exponent_counter /
float_literal_request_limit），请窗口二按 exported Python strict语义保留数值词法并在 integer schema节点拒绝小数/指数，
不要全局拒绝合法number字段或弱化Python strict。仅受控 TS schema guard 不能做最终权限。
请修复/重建/正常入口聚焦回归后，再共同进入最后冻结。全静态套件仍运行中；不会把旧快照当最终身份。

补充最后修复：facade冻结公式现在逐包与实际 accepted Formalizer package 的原 adapt输出比较，
拒绝伪包/公式内容替换；新增两反例。I01树根保留原位置/resolve/symlink关系，长inventory前后重算
engine+validator，混合源码状态拒绝 composition_source_unstable。所有来源仍在原validator封闭列表。
窗口一等待窗口二 strict数值词法修复/最终build稳定后再跑最终focused+联合；此条后不再编辑源码。
全静态本轮4211 passed /3 skipped /7warnings /12subtests（403.38s，修复前代码状态，非最终新身份）。

最终交付报告已预写 stage03_delivery_evidence_20261003.md，外部final-delivery根固定。validator补入实际复用的
formalization_agent / method_argument_models / unified_context_models原裁决来源。Python源码已稳定；
等窗口二严格数值修复后的唯一构建/测试稳定通知，再抓最终full组成。此后本窗口只向外部根写记录。

## 提交前复读返修：新副作用必须核合同与当前上下文（释放旧final读集）

此前 final-delivery（source eb0aca… / composition cf2db…）保留为历史包；不作为当前最终提交。
发现旧合同可在新Host bootstrap下借用当前状态：ingest新提交只核facade current，但未核合同expected revision、
冻结snapshot/fence或合同validator与实际当前composition。现在 freeze记录fence，ingest仅新副作用执行
check_contract_current：revision/snapshot/fence、完整identity、实际refs/read-set、三类页材料、model/options/
renderer/schema/epoch限额全部匹配；缓存已提交合法重试仍在这些新作用检查之前返回原receipt。
增加8项stale/identity反例与fresh Host合法缓存恢复；unit helper renderer_version改为其实际fixture composition，
不放宽gate。窗口二TS/build未改，不需重build；窗口一将重新freeze并跑final-r2全部验证与联合。
窗口二请保持源码/文档不动，若更新交付，只写ignored根。整批Gate-C仍未自批。

r2最后补 scope/page/primary plan cap、配置maxTokens 和材料/模型/read-set反例，新增共14项，
预期最终105项focused（以实跑为准）。worker测试fixture任何初始化失败也finally关闭真子进程。
代码已稳定；最终预分配root为 .dsh-dev/run/stage03-w1-20261003/final-delivery-r2。
本条后再冻结；窗口二保持现已冻结123项/最终TS stage，只写ignored根。

## 窗口一最终提交（r2，读集已释放）

final-delivery-r2/delivery-index.json已生成：105focused、265owner、4234全静态（3个非本批live skip），
所有五检查exit0/source前后不变；技术/作者真实联测、cap先观测再零发送prepare与34真worker反例均通过。
原reader/封存reader同代五成员，pending_validation；29279项封存长度/SHA全部复核。TS123原stage保持。
代码/runtime不再修改；本条及状态/README/03/compatibility/task_board文档更新在显式释放后进行，
不得把新工作树宣称与r2冻结engine同身份。旧final-delivery标为superseded但实物保留。
owner状态submitted_for_independent_qa，整批独立Gate-C仍待QA，后续R/V/A/live/default/D5未启动。

## Gate-C 集中返修接口，2026-10-03 23:xx

窗口一确认旧 Pydantic `\\S` 全 Unicode scalar census 仅排除 25 个 White_Space 码点。
Identifier 现用显式 negated class，schema extension `x-c2p-character-rule` 为
`unicode-white-space-nonblank/1`；完整定义在 wire-v1/character-rules.json（WireCharacterRulesV1），
范围 0009–000D、0020、0085、00A0、1680、2000–200A、2028–2029、202F、205F、3000。
FEFF 及 001C–001F 合法；要求至少一个范围外码点，长度仍 1–256 Unicode codepoints。
禁止宿主 `\\s/\\S` 推断。所有 Identifier 字段共用该规则；Digest 保持 ASCII pattern。
完整导出命令：`python -m tests.integrations.dsh.test_wire_schemas integrations/dsh/wire-v1`，
现覆盖全部 8 个模型 schema、native schema/enforcement、goldens、character-rules。
扩展 corpus 的 identifier_* 28 例已生成；Python 另有全 scalar 等价 census。
GC-2/3 不计划改变 WriterTaskContractV1 字段；新 ingest 在缓存分支后重新验证完整投影闭包，
完整依赖以 LocalWriterDependencyClosureV1 随 provenance 及 manifest read_set 持久化。
TS 不需产生新的摘要或合同字段。窗口二可现在消费规则并做 native 反例；构建仍由窗口二独占。

### 本批 Python/fixture 接口就绪

当前全部 schema 导出完成；GC-2/3 保持合同字段/version 不变。
check_frozen_current 全生命周期 + verify_contract_dependencies NEW effect 闭包落地，
完整14个 refs 的 LocalWriterDependencyClosureV1 随 provenance/manifest 落盘，缓存顺序保留。
新增 true stdio Host transition / stale owner callback 和三终态六引用损坏反例。
开发期并发修改导致 composition_source_unstable/漂移拒绝如实保留；等待窗口二最终
构建/源冻结后一起抓 fresh engine/composition，再跑稳定全集与 joint。
窗口一从本条开始不改 source；若稳定测试发现产品缺陷再明确释放并返修。
新 ignored 根 `.dsh-dev/run/stage03-gc-repair-w1-20261003/coordination-w1.json` 提供后续状态。
