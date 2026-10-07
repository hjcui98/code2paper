# Stage03 窗口二交接（实施中）

责任：C00、C01 TS 消费、真实 renderer/loop/pi-ai wire、唯一 peer/build/stage。
Python protocol、validator 清单及 compatibility.stage03.json 由窗口一单写。

本窗口正在测量接受候选 `0.2.0-rc.1+loop-origin.1` 的实际解析位置和字节。
阶段运行证据根：`.dsh-dev/run/stage03-20261003-w2/`，不覆盖 Gate-H 包。
尚未 build/stage；当前产物仍是已验 H 候选。最终构建前将在此登记时间窗口。

## 窗口一需要交付

- 可执行 C01 schema/goldens 路径，合法/非法 wire bytes 与预期稳定错误码。
- WriterInputRef 与 WriterWireProjectionV1 的字段及 Python canonical 规则。
- I01 测量输入格式；本窗口提供 Node/Loader/peer/build/runtime/preset/schema 实测记录。
- 明确 Writer prompt 和 TaskView 的终端指令转换，terminal JSON Schema，以及有效 model/options/cap。

公开 runtime 已有 `SystemPrompt.assemble`、`renderPrompt`、`renderContextSections`；
实际 loop 也调用这些公开函数。没有假设 DSH 存在 dry-run 请求 API。
正式投影实现等待 C01 接口，不自行定义与 Python 平行的领域合同。
测试将运行真实 pi-ai 适配器连接同一隔离网络 namespace 的本地假 SSE；prepare 零发送单独核验。

本文件仅由窗口二更新。窗口一可在自己的交接文件记录接口位置；本窗口会读取。
状态：in_progress，尚未提交 Gate-C。

## I01 实测交付

`node integrations/dsh/dev/stage03-measure.mjs DEV_ROOT OUTPUT_JSON` 已 exit 0。
当前实测 `.dsh-dev/run/stage03-20261003-w2/environment-before.json`：
26,150 runtime 文件/链接条目，Node executable、staged/development 两个消费者的
Loader/boot/Cordis/AgentLoop/SystemPrompt/pi-ai 等实际解析位置和 JS 摘要；
完整 runtime/build/staging 清单，preset/config/lock/receipt 原字节摘要。
该文件不自称最终 composition；Python 按 I01 canonical 原语核验/计算。

## 当前 C01/C00 接口需求

已读取窗口一新增 WriterWireProjectionV1 草稿；还缺 WriterInputRef/Host 输入接口。
请提供实际 builder 的 system prompt、user/TaskView 原文或序列化 bytes、terminal 标准 schema，
以及 projection seal 的 Python callback/RPC（TS 不替代 Python canonical digest 权威）。
measurement_ref / wire_equivalence_ref 必須由内核签发或受控测试来源，并明确 prepare 首次调用
如何获取已经覆盖同 renderer/model/options/schema 的 wire 等价证据，避免自引用/占位。

DSH 工具公开 schema 子集不支持 `$defs/$ref`、`anyOf`、minLength/minItems 等。
建议由窗口一给出结构等价的 native schema，以及原完整 schema；TS 工具运行入口仍按完整
schema 校验，Python ingest 再作原模型复验。不会直接删除约束。
TS 将严格解码 UTF-8/duplicate key/unsafe integer/nonfinite，并消费 Python 原 schema/goldens。
对于 Python canonical 的浮点格式差异，保留 Python 封存 bytes/digest，不用 JS stringify冒充。

## C00 第二次接线（窗口一补充合同已消费）

消费 `wire-v1/WriterInputRefV1.schema.json` 与 native-terminal shape/enforcement，
新增 `src/wire.ts`、`src/writer-request.ts`、两份真实测试；bridge 的 Host 私有
`prepare_projection(inputBytes, composition, authority)` 已落地，未注册模型工具。
authority 注入 validateInput / digestValue / evidenceFor / sealProjection，纯 Python 原模型
与 canonical 权威；首次缺 wire 证据明确拒绝，不发送来补证。

`renderer_digest` 在 C00 约定为实际执行 staged `lib/writer-request.js` 原字节 SHA-256（带前缀），
SystemPrompt/Loader/pi-ai/runtime 字节另外被 composition 覆盖，不以版本号代替。
system_text = 原完整 writer_request.prompt + 两个换行 + 显式 terminal_instruction；
user_text = Python 提供的 task_view_json 原字节。原材料不重拼、不做变量插值。
effective_options 首版只接受 provider / temperature / reasoningEffort / maxTokens；
maxTokens 必须与 post_clamp cap 相等。stop、动态 transport messages/images/files 等未覆盖拒绝。
模型 profile 内隐式参数必须进入 I01 config；实际 loop/provider 对照会复核有效值。

Host 创建 render-only Agent，setup 内安装 complete 静态 prompt、抑制动态 context、清空 global tools
并 scoped 注册 c2p_terminal。工具 run 先完整 schema guard，再 concludeTurn；native shape 仅供注册。
seam 比较实际 request，拒绝 drift，没有任何就地材料/cap 修改。准备完成与失败均 dispose Agent。

20:50 后本窗口开始唯一 typecheck→build→stage；日志在本窗口根 build-1/。
package 增加 system-prompt peer，同时将 lock root 的旧 0.1.5 peer 声明同步为真实 0.2。
实际 toolchain:install 已执行（3 个原冻结开发依赖、无 runtime 安装），新回执不复用旧 H bundle 摘要。

C00 开发测试的 `C00DshMeasurementV1` 只证明 DSH 部分，明确不是完整 I01 生产组成；
最终 C02 必须叠加已存在 Python engine/validator/worker/dependency 实测，再重取投影。
测量字段由 kernel ArtifactStore 发行；fake-service tokenizer 明列 controlled UTF8 byte-id，仅本地假模型，
不宣称 Qwen/live 计量。最终联合输入请给出完整 composition/spec 及 renderer driver 需要的输入路径。

### 窗口一需修复的实际入口回归

`focused-1/wire-writer-request.log`：正常 `python scripts/dsh_dev.py --candidate ... test` 在测试前
`inventory()` 新委托 import `code2paper` 抛 ModuleNotFoundError（宿主 Python 未安装 editable；
脚本原正常入口没有 src sys.path）。请由唯一 Python 写者修复 CLI 实际运行导入路径，
并覆盖真实 setup/audit/test 入口。不是 runtime 漂移；没有放宽 inventory。
本窗口不改 scripts/dsh_dev.py；保留失败原始日志后等待该普通回归修好，再跑真实入口。

### 已观测真实 adapter wire（module 入口开发诊断）

实际 fake HTTP/SSE root：候选 `run/stage03-writer-request-M7m8GQ/`。
里面已有完整原真实 Formalizer/非空 atom request、provider-request.raw.json、provider-response.raw.sse、
loop-request.json、adapter-arguments.raw.json（2 chunks、captured）和 kernel-issued artifacts。
受控 send 1，真实 loop 1；作者/证据/TaskView/system/tools/model/temperature/max_tokens 全部实际对应。
此轮完整测试 17/21，余失败为 bridge 缺 agents inject（本窗口已修）及 raw semantic vs model 默认值摘要
区别（已修 test：golden semantic_digest 表达 raw object，而 parse_model 加 defaults 的 digest 是另一身份）。
没有将这轮写成 C00 PASS；失败日志完整保存 focused-module-2/。

窗口一 `_verify_projection` 请按实际 provider wire 修正两处转换合同：
1. pi-ai tools.function 有真实 `strict:false`；不可假设 adapter 输出与内部 ToolSchema 完全同 shape。
2. effective reasoningEffort='off' 在 deepseek dialect 映射 `thinking:{type:'disabled'}`，不发送 reasoning_effort。
这是显式 provider 转换，不能简单逐字段期望 `reasoning_effort == 'off'`。
transport 随机字段按实际层区分；provider body/tools/schema/参数属于语义，不列随机白名单。
本窗口将按新的 WriterMeasurementV1 / WriterWireEquivalenceV1 实际 schema 对齐证据产物。

### 真实聚焦入口已通过

窗口一修复 scripts 的导入后，正常入口 `focused-3/wire-writer-request.log` exit 0：
21 passed / 0failed / 0skip。typecheck→build→stage 的 build-3 三步均 exit 0。
测试证据根见该日志 `C00_EVIDENCE_ROOT=`；projection、measurement、wire-equivalence、comparison
均实物落盘，provider_wire_ref 保存真正 HTTP body 原字节，非 JSON 重序列化。
prepare_sends=0、受控 loop/provider 请求=1、raw 参数2chunks完整；资源已关闭。

下一步窗口二补实际新 cap 重投影、创建期绑定/终端反例、无网络 projection CLI，
再与窗口一正式 full-I01 composition 下的真实 worker 联测。C00 单独 DSH测量不偷换完整组成。

## 联合可执行 driver（已写，等待 full-I01 bootstrap 实跑）

`node integrations/dsh/dev/stage03-project.mjs TRUSTED_CONFIG_JSON`：
config keys 为 mode='observe'|'prepare'、output_root（新建目录已存在）、bootstrap_path（真实worker bootstrap）、
input_path（facade.render_input真实输出），observe另给terminal_raw_path；prepare给evidence_path。
可选fake_http_port/context_tokens/safety_margin_tokens/thinking_tokens。必须在同一离线launcher namespace运行。
实际读取 bootstrap composition/spec，通过 Python原validate_execution_composition核实；实际源Node/renderer/peer再核。
observe跑真实Loader、creation-window SessionBindings（明确controlled fixture grant，不是R01）、原preset、loop/pi-ai假服务，
发行kernel artifacts、真实raw/normalized/SSE/Session/Hostbinding及OutputEnvelopeV1；然后prepare本身零发送。
prepare模式不挂provider，只消费已观测evidence、真实公开renderer与Pythonseal输出projection/ref。

默认driver以 deepseek route / deepseek-v4-flash 的真实pi-ai协议访问本地假服务；请full-I01 effective_config采用
model='deepseek-v4-flash'、options={provider:'deepseek',temperature:0.2,reasoningEffort:'off',maxTokens:cap}，
renderer_version='native-text/1'、meter_version='controlled-utf8-byte-id/1'；若预先指定端口可在effective_config
加入fake_provider_endpoint，driver核实际端点。measurement的tokenizer_digest取actual composition.files.tokenizer.digest。
tokenizer/meter是假服务声明的UTF8 byte-id，不称真实DeepSeek/Qwen tokens。

窗口一还需：worker允许已声明本地byte-id meter；bootstrap总大小不得默认套RPC的1MiB
（完整runtime inventory一树约4MiB，Host可信bootstrap须另有明确界限/引用）。
OutputEnvelope的turn/step来自真实Session.tool/call；请bootstrap context与driver使用的整数标识保持一致。
不是复用旧fixture的虚构turn-1字符串来代替实际观测。driver调用范围只在Stage03，不实现R03 pump。

原 H01 回归固定 root inject=['agentPresets']，本窗口已保留该合同：projection authority额外显式注入
`agentHost` Context capability，bridge核同hostGeneration再使用其agents，不扩原Loader必需依赖。
此前build-3本地C00通过的两个inject只是开发中间版，最终build会恢复原元数据。
这是Host进程能力，不是writer wire/RPC/model字段，TSauthority注入与Python领域合同无冲突。

Full-I01 spec请额外绑定完整staged bundle树（实际lib/wire.js/所有helper输出），不能只列index.js与receipt；
源码未改而某个ignored helper JS漂移必须实际prepare拒绝。受控stage目录无session/cache，允许安全全树扫描。
开发node_modules有外部peer symlink，不直接作为runtime_inventory树；使用实际runtime/node_modules完整依赖树，
编译器/TS库另按真实路径绑定；本窗口environment-before已提供完整build/staging/lock/Node/runtime清单。

### 联合前稳定窗口（当前）

build-5 typecheck/build/stage 全部 exit0；focused-4 正常真实入口 23 passed / 0failed / 0skip。
新增 cap1024 重新实际发送获得新测量/等价引用，再 prepare 零发送；旧cap projection拒绝。
真实 c2p_terminal 对 native shape 可接受但完整schema禁止的空reason拒绝、无接受回调。
原H01 root inject已恢复 ['agentPresets']，现在执行完整 compat 保留原93。

stage03-project.mjs 已改为真实父→子原生 agents.create(parentAgent)；原applyChildComposition
在创建窗口加入父standing generation，再SessionBindings.bind(parentSessionId)并安装Writer。
因此联合bootstrap必须 child_id == session_id（实际native child session），父session由driver
取 session_id+'-parent'；turn/step来自Session事件，首轮为'1'/'1'。
假service tool_call_id仍从可信bootstrap指定（adapter实际收到），不从模型claims取task身份。
真实父未followup且无发送，两句柄/两binding都释放。此fixture不声称R01 durable claim。
当前TS/lib源码与driver已稳定；本交接更新后可抓full组成并实跑。窗口二继续记录compat日志，
不修改被身份覆盖的源码，若发现失败会通知新的稳定窗口。

完整compat-1 exit0：116 tests / 116pass / 0fail / 0skip（原93 + 新23）。
audit-2正常进程exit0且无spawn错误：runtime树仍671daa1a7a06728d69a4bdec6da3d33a3616c4e788f63579ed07f3ae81e0e16c；
新receipt=3107bb3916d40d0a50e7a3cff7348776e0b9e4b6b1e8e3e0fe18596f523b2af9；
新stage=64e0d6d6988f597e241d39269328e5c4e5ac4967ec227b41581c9cca030b324e。
audit-1虽内层PASS/status0，外层spawnSync EPERM，保留但不作为有效最终审计；audit-2已解决。
driver已记录实际adapter-chunks.json，envelope stop_reason/usage取实际finish/usage事件，
不复制fake配置数字冒充观察。driver所有变更目前完成；此交接是最后一次源内更新，
正式组成捕获后本窗口仅往外部/ignored运行根写证据，直到读集释放。

### joint-3 实际组成输入缺项（需要重新捕获）

已读 joint-3：verifyWriterComposition 的 actual-import pin 核验拒绝 composition_drift，
不是TS/lib漂移；完整spec.files尚缺SystemPrompt实际导入入口。
请外部 full-composition-plan.py files 添加 system_prompt =
DEV/'runtime/node_modules/@deepseek-ai/dsh-system-prompt/lib/index.js'，保留原runtime全树，
重新捕获组成/源和输入。TS同时核自己renderer、Node、实际SystemPrompt是刻意fail-closed；
不要去掉这个检查或用预期pin替代实际导入。此前joint错误如实保留。
本交接修改使旧source读集失效，显式释放并重新抓身份；TS/lib本身未变，无需重建。
窗口二已有独立输入72文件封存+前后核对在
.dsh-dev/run/stage03-20261003-w2/frozen-window-two/；这是补交接前的开发证据身份，
最终joint的当前源身份由新的capture负责，不冒称旧回执仍同身份。

joint-5 observe 已成功且release actual_sends1/prepare_sends0/bindings0/serverfalse；
实际parent/child、turn/step和adapter来源均已观测。检查envelope发现DSH finish.reason
是 {kind:'tool-calls'} 对象，而OutputEnvelope.stop_reason合同为string|null。
现修driver取实际 finish.reason.kind（完整对象仍保留adapter-chunks.json），不取fixture预期值。
只改dev driver，无TS/lib变化；请释放joint-5读集并重新capture运行下一批。
不能把旧envelope就地修成成功证据；保留joint-5失败/中间产物。

## C01 strict 词法修复（最终返修，2026-10-03 21:07）

收到窗口一新goldens，compat-final真实失败118/121：三个integer float/exponent反例，保留日志。
wire.ts已保留每个JSON pointer的原number词法（私有WeakMap，不写入JSON/摘要）；
integer schema才拒绝小数/指数，number仍允许，覆盖nested array/ref/union和pointer转义。
parseWire原始root number也按词法判断；decodeWire→validateWireSchema的对象保留词法。
native terminal入口改为验证实际TerminalArgumentCapture raw bytes，再核normalized对象一致；
不能先JSON.stringify(args)折叠重复键/数值词法再当原始schema guard。监听随作用域销毁。
新增真实假SSE重复键terminal拒绝（normalizer可折叠但callback不接受，受控后续请求禁止）。
build-7三步exit0；focused-5在正常入口运行新goldens与真实terminal。全部源码修改目前完成，
本条后窗口二仅写ignored运行根；focused结果见该目录，成功后仅补最终串行build/stage/compat证据。
请等待窗口二最终build/stage结束再capture；旧receipt3107…/stage64e0…只保留为历史，
新的实际renderer/wire lib摘要必须用最终stage抓取，不复用joint-6旧组成。

### 最终构建已释放，允许捕获新 full-I01（21:10）

focused-5 exit0：30/30；build-final typecheck/build/stage均exit0；audit-final正常exit0/PASS。
最终receipt=4b378ced6e73e5b2c3fd24854ba20546b0e0bc760f3903655c3193f1c4518fda；
最终stage=08d40fb06972e2ec9ad0c8087277a7b8550c0de9396e37b63969f7a24256b128；runtime保持原671daa…。
窗口二不再改源码/文档，不再build/stage；现在启动兼容终轮 compat-final-r2（read-only，输出只在ignored run）。
可捕获新的full组成并联合运行；最终compat退出/数字直接读 compat-final-r2/compat.command.json 与compat.log。
窗口二提交索引将写ignored根 window-two-submission.md；完整源码/tests/drivers/原始证据与前后核对封存该根。
此前116/116以及最终修复前118/121各绑定其旧输入，保留历史，不能混作新stage验收。

## Gate-C CHANGES_REQUESTED 后新批（GC-1/2/3，23:17）

已读 stage03_gate_c_review_and_batch_repair_20261003.md 全文；窗口二接 GC-1 TS/native、唯一构建及联合支持。
原123及 r2封存只保留历史。请窗口一提供明确字符规则、完整导出schema/corpus/enforcement约定；
当前所有导出patterns只含 Identifier 的 `\\S`（33处）和 ASCII digest（50处）。
TS将不再直接用宿主RegExp解释未经证明的pattern。建议在Identifier schema附带有版本的显式规则描述
及Unicode whitespace范围（由Python定义），消费者按该范围判断；或者导出等价明确字符集合pattern。
请明确extension字段名/版本/取值；窗口二不自改Python接受域或只特判blocked.reason。
窗口二会补全wire双向corpus及真实terminal U+0085拒绝/U+FEFF和ASCII接受，
并提供合法raw给窗口一真实worker record_output验证。GC-2/3若改wire合同请同步完整导出。
新运行根预分配 .dsh-dev/run/stage03-gc-repair-w2-20261003/，原包不覆盖。
协调暂用本文件；最终源码冻结后更新改写ignored运行根中的coordination.json，避免重复改变engine读集。

### GC-1 接口已消费（23:28，新批开发中）

TS按 character-rules.json 完整版本/显式范围实现 Identifier，全字段共用，拒绝未知版本、缺失标记或不支持的pattern；不再宿主RegExp解释Unicode。
ASCII Digest也改精确字符/长度检查，避免JS `$`尾随换行差异。新双向28 goldens、描述符逐字段对照、全部25 whitespace、FEFF/001C–001F/nonBMP长度及真实terminal12例已加入。
build-1 typecheck/build/stage exit0；focused-1当前运行，日志会生成在新根，最终成功通知另发，尚不允许最终capture。
开发 native-before 运行碰到旧staged codec与新schema混用，保留失败记录，不作为Unicode裁决或最终身份。
真实terminal每例把同一raw传原Python parse_model，存HTTP/SSE/adapter/session/result，所有fixture全局限制step1。
stage03-project 同样补全局单请求限额，拒绝不引入自动循环；支持 terminal_raw_path 原始Unicode，窗口一可用最终组成重抓FEFF合法worker record_output和NEL拒绝。
窗口一请真实 worker 复验合法FEFF/ASCII，不只纯parse_model；真实native12 raw将保存于候选run/stage03-writer-request-* 的gc1-*-adapter-arguments.raw.json。
stage03-run新增 b02 模式保留准确命令/log/status。最终最终构建之后会停止改读集，并在ignored根协调全部联测/封存。

### GC-1 最终构建稳定，允许 fresh full-I01 捕获（23:30）

focused-1 exit0，72/72，真实terminal12例与原C00全通过；对应C00目录 stage03-writer-request-9I86mf，release: closed/server false/16 handles/16 requests/prepare 0。
最终 build-final-r2 三步 exit0：receipt cbe3da5b3198516f184b7f6fe0a228fc56c7ffa69c27bf7060505bf77a2a7985，stage b820ceea431868271687a0f4f1aca57d3ceb6ab9ba4fe18376fd50b602ca0e61；runtime原字节保持。
第一次 build-final 仅新增测试索引类型编译失败，已修正后完整重建；原日志保留，不能混作最终成功。
从本条起窗口二只写 ignored /tmp/run，不改源码/文档，不再build/stage。请窗口一读完本条后冻结自己的读集并捕获新组成。
启动 compat-final/b02-final/audit-final；唯一最终交付根为 .dsh-dev/run/stage03-gc-repair-w2-20261003/final-window-two。
后续状态见新根 coordination-w2.json；请窗口一确保最终整包包含全部Unicode真terminal/Python raw对照以及真实worker合法FEFF和ASCII，GC2/3全反例、新技术/作者页及cap重编。
