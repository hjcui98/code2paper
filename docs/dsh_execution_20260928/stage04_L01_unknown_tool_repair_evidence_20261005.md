# L01 packet12 未注册工具返修证据（2026-10-05，进行中）

当前24 done / 1 in_progress / 24 planned，Gate-L FAIL；M/P/G正式实施仍等待原独立门及实际读集释放。原[执行指令](stage04_L01_packet10_repair_and_continuation_20261005.md)及AT不变。Root直接实现和执行，仅复用必要独立QA。

## 原请求与拒绝

packet12 `/tmp/c2p-dsh-l01-packet-20261005-12` 的packet SHA fe48f5de92ff680cf777721627e893c3f1015fe4dab3fec195f4c71063fedf3c、plan SHA cde24612e3456c8b469ffdf472824d4fc28eacda215b0628ddadb651a7c16b17取得用户具体一次授权，原handle44943已回收exit1。实际primary1/tokenize1/retry、repair、aux0，HTTP200；usage7648/1221/8869、finish tool_calls。原函数名为含引号、换行和参数标签的畸形名称，args为{}；真实Session ToolNotFoundError/UNKNOWN_TOOL后blocked。禁止剪裁名称、修补参数、把reasoning变成领域输出或重发旧包。

原唯一账本7事实已经spent7648/pending0；taskcancelled，captured_source、receipt、provider_quiescence均null，失败时backend由原packet12持有；下述已按原授权合法退役。Host领域拒绝正确，诊断却误报ordinary_model_text。独立事后QA `/tmp/c2p-dsh-independent-l01-packet12-postlive-20261005-01` Gate-L FAIL，367实际输入及读集已释放；随后才开始源码返修。

之前complete04 `/tmp/c2p-dsh-l01-admission-20261005-04` 的1707及freshcold1、原manager33395/readers55834 exit0，只证明engine9def7a6dcb9b0533d9819715d36581539bbaa2a1f3f8c388a707c42f5d602b56/validator7b77c88b240a561f077982637c9590e61358b5b9af94fdea1e7d9ddb5544a626；本批源码另需最终冻结完整验证。packet10、11的已验证历史退役和领域失败保持原身份，不重算费用或复用生成授权。

## 实现与验证

- Host区分普通文本与未注册native工具，逐字保存函数名、参数、callId及原Session；首因仍host_single_terminal_required，清理错误另列。
- 新具名DshRejectedUnknownToolProviderQuiescenceV1及FinishObservationV1只接原活动execute/private gated-adapter自然结束。严格校验scope、原请求/offered tools/config、model来源、单call/result UNKNOWN_TOOL、compact blocks/deltas、usage、finish和费用；不授权terminal候选。recovery-only不能铸造，缺损证据继续held。
- 新operator-only unknown-native-tool-retirement/1绑定原packet/grant/plan/launch/producer/SSE/Session/tokenizer/原费用及当前实现、具名独立review和范围判断。只做exact owner事务释放与immutable history，另有原协议lease。不会写TaskDB、旧artifact、费用事件或provider_quiescence。纯Session检查与原active完成授权分开；旧四类历史严格reader保持。
- Generic terminal指令补充exact function-name边界：引号、空白、markup、parameter tags不属于函数标识符；schema_version/result放arguments，按backend提供的序列化格式。原schema、formula/witness义务及验收均不减弱，不改返回名称。
- 新Python/Node入口进入core/6、offline/6及实际validator来源清单。最终完整验证尚待本批关闭，不把历史1707贴到新身份。

| 新观察 | 原句柄、准确结果与限制 |
|---|---|
| typecheck/build/stage | typecheck03原21887、build01原75774及stage01 exit0；早期配置和测试import失败日志保留 |
| 私有完成证明 | proof02原91994 exit0，58pass；pure checker提取后proof03原99754 exit0，95pass含旧text |
| 真实native三路径 | 原58585 exit0，3pass/0fail/0skip，225570.860ms；packet10原字节、text_stop、unknown_tool及新进程零重发，engineb641/validatorf22冻结 |
| 历史退役集中测试 | retirement04原41460 exit0，116pass169.67s；含新历史37、unknown58和旧native21，错误scope/transport/grant/history、新owner和事务切点 |
| 新合同与完成校验 | contract05原93910 exit0，133pass2.11s；不代表真实模型遵守 |
| 断网原数据克隆 | 原44142 exit0；engine4fc333/validatorfe1d8e，克隆backendempty/五条严格history；59个原文件绑定无变化，canonical仍held，fee/source/task零修改。review/auth明确测试fixture，不代独立批准 |

日志、负责文件baseline及原生封存见 `/tmp/c2p-dsh-l01-unknown-tool-repair-20261005-01`；保护方案及原reader结果见 `/tmp/c2p-dsh-l01-unknown-tool-history-clone-20261005-01`。初次历史单测fixture错误（缺可选provider、错误假定child等于Session id）已经修正，retirement01/02原失败日志保留；没有削弱原实际Session绑定或费用要求。

## 当前剩余门与服务配置限制

canonical方案已取得独立code/plan PASS、原授权范围APPLIES（525实际输入及明确读集释放）。按原wrapper执行后，实际结果独立PASS（364实际输入及明确释放）；详见下节。源码/测试/文档现集中关闭，下一步冻结并运行唯一新完整/cold输出根 `/tmp/c2p-dsh-l01-admission-20261005-05`，原reader验绑定身份；本记录不提前报告未运行结果。

用户提供的历史serve_gpu6_128k.sh和启动日志记录qwen3_xml/qwen3，脚本未显式指定chat-template；模型目录chat_template.jinja默认XML。当前公共tokenizer_info/server_info均404，进程namespace看不到实际server，不能证明当前实例载入这些历史文件。actual packet12 prompt没有禁止XML-style text；先前commentary的相反推断已更正。记录摘要在 `/tmp/c2p-dsh-l01-packet12-rootcause-20261005-01/historical-runtime-records.json`。不据此宣称已确定模型/服务parser唯一根因，未改服务配置。

下一次模型请求只能在以上门完成后准备实质修正的fresh实际wire及具体一次授权；当前无resend授权。合法释放不把packet12或Gate-L改成成功；Gate-L实际PASS和释放后才连续接M→P→G。

## 原owner实际恢复闭合

当前关闭方案/source/docs之前身份engine4362c325bfc135f6abf545fd69f2983d8e47ed27fa53249917601609394f688e、validatoraf9fdb96f4a5aa238943f5d7d3733346ce653dc92148bfaba7417e599124cc44。独立 `/tmp/c2p-dsh-independent-l01-unknown-tool-code-plan-20261005-01` 525实际输入、PASS/APPLIES、全读集释放，实际具名review由reviewer写入。Root据原packet12 grant与该范围判断生成scope record，不是新生成授权。

原98467回收exit0，严格执行plan6238d36eee0fc147cc663a847079ba6478213df62899fe915371898f9e01cc09、wrapper43d24f5e6fdabb80a1399b911bfe3d075c54244827501c9c87591025e5a53f6d，断网/rootRO，只有原canonical backend和原lease协议可写。receipt selfdigest890550366e12ed7d63837c19287aeefe23529431db66ce1372952663d6fab00b，原数据/账本reader实际backendempty、7648spent/pending0。42个非lease旧run文件与14项attested输入SHA/长度无变化且无run新增；七费用事实、TaskDB/taskview/claim/cancelled、source/receipt/quiescence null逐值不变。59为克隆的绑定数（含重复），不是59个unique文件。

独立 `/tmp/c2p-dsh-independent-l01-unknown-tool-migration-result-20261005-01` 364实际输入，实际结果PASS、原verify_package/verify_original_finish及五条typedhistory严格reader均通过，旧四row bytes与审查原canonical及克隆相同，仅新增原packet12的具名history。reviewer没有再次执行operator；实际全读集已释放，之后才更新本记录。原领域失败不变；无新模型/tokenize/费用/成果凭据。完整与cold新身份封存尚未运行，新live仍须fresh具体一次grant。
