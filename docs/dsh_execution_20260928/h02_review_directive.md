# H02 候选交付审查与三窗口补齐指令

> 2026-09-28，LEAD 静态审查与派工记录。H01 的独立 PASS 保持不变；H02 已提交候选实现，
> 本记录审查时状态为 `in_progress`，`interface_status=changes_requested_not_frozen`。
> 本记录不宣布 AT-H02 通过，不代替窗口三的运行验收。LEAD 不修改实现、不代跑测试。

第二轮候选已交付并进入 review；当前写权和验收指令见 [H02 QA 交接](h02_qa_handoff.md)。
下列首轮身份、缺口及当时派工保留作历史依据。

## 1. 以本记录绑定的候选输入为准

本轮读取确认以下文件与窗口一最新交付相符，构建回执的 `src_inputs` 已包含 H02 两个源文件。
窗口二“src/tests 不存在”和窗口三“新源码未进入构建、缺冻结文档”的报告描述更早的输入，
不再作为本候选的阻断理由；其运行时发现与独立反例计划仍保留。

| 对象 | 当前候选摘要 |
|---|---|
| `session-binding.ts` | `6324fbdee94bb63137871a50c582ee517c9c82378341680b59826a05d52a53b0` |
| `role-dispatch.ts` | `87cc8fef56d986542affe0c639789f625613cc9e2fe5a3f0dc69164c0be86f63` |
| `binding.test.ts` | `91957e6b8fed456ab53df68dd11ce7f1275368723d71344ca425ffc83cb5d458` |
| 接口候选文档 | `9ba130f4553e5b3d1ee51de835c5d5c2fc7e907dee1516f82e315ca861239e37` |
| 构建回执 / outputs | `173c846d…` / `03042429…` |
| staging 回执 / staged 文件树 | `e65aeb38…` / `5fa7ed64…`，两个摘要不是同一对象 |

完整读取快照见
[`candidate-before.json`](/tmp/c2p-dsh-h02-lead-review-20260928-dujd3wwv/candidate-before.json)。
23/23 等运行结果沿用窗口一的交付声明与证据引用，本轮 LEAD 未重跑。

认可“标准 spawn 不满足创建期绑定，改用公开窄 provider”的实现方向；独立 QA 仍须核对
真实时序。认可本次两个 peer 声明的范围偏离，限于 `dsh-subagent` / `dsh-llm` 的公开 API；
窗口三核对解析进冻结 runtime。不是重装或修改日常 DSH 的授权。

## 2. 本轮必须收口的四项

### H02-L1：请求 recorder 合同仍未交付

[接口候选记录](h02_interface_freeze.md) §5 只有 `ClaimRecorder.claim` 的类型和“镜像形状”说明。
它没有交付先前 [交接要求](h02_h04_handoff.md) §1–2 所需的
`request.reserve/dispatch/settle/mark_unknown` 完整参数、返回/拒绝类型及实际可编译的消费示例。
这是已核对的交付缺项。

窗口一负责新增 **`integrations/dsh/src/request-contract.ts`**，仅承载本阶段 Host 请求 recorder
合同及回执类型，不实现 H04 middleware、RPC、持久余额或 Python reducer。接口至少表达可信
binding 引用、请求序号/用途、版本化完整请求摘要、预留估量、reservation/request 引用、
finish/usage/响应来源、最后可证实阶段和 unknown 原因。reserve 与 dispatch 必须绑定同一摘要；
过期绑定、错配回执、延迟/拒绝/取消应能在 mock 中分别表达。

窗口二以消费者身份审查签名和语义；窗口一唯一写入共享合同及冻结记录。生产协议仍由 C/R
任务接线，不能要求先完成后继生产 RPC。示例应调用真实类型，不能用 `Record<string, unknown>`
或另抄一套接口避开编译检查。H02 证明合同可消费；实际 reserve/dispatch 硬门由 H04 证明。

### H02-L2：示例与真实导出类型不一致

`role-dispatch.ts:60` 的 `Code2PaperSpawnOptions` 要求 `caller`，但示例和测试在调用
`registerCode2PaperSpawn(ctx, { bindings })` 时没有传它。测试的 `DispatchModule` 又把 options
改写成 `Record<string, unknown>`，所以当前 typecheck 不能证明该示例符合真实导出合同。
这是静态确认的类型不一致，本轮没有运行 tsc 复现。

窗口一先用真实模块类型建立最小编译反例，再统一 API、实现、示例。可以收敛重复参数，
也可以明确实际消费方式；不能只放宽类型。测试即使运行时必须动态导入 staged bundle，
编译侧也须关联真实导出类型。窗口三独立编译真实消费者。

### H02-L3：无 fence 提示时，旧父绑定的有效性没有被核对

静态路径：`SessionBindings.assertTrusted()` 只在 `hint.fence` 存在时与 current fence 比较；
`require()` 只确认记录存在。窄 provider 的 `start()` 也先读取已有记录，没有独立核验其当前
有效性。故“旧 hint 被拒”尚未证明“旧绑定本身不能授权新 child”。本轮未动态复现。

窗口一先复现：父绑定 fence=1 → 同 task/epoch 的已知权威代次推进至 2 → 用旧父调用
`dispatchRole`，分别不带 fence 和带当前 fence=2；另经公开窄 provider 入口复核。
期望由可信绑定自身失效触发拒绝，在新 child claim/创建/材料投递之前停止；传当前 hint
不能把旧父升级为当前父。保留当前合法父的成功对照。修正在现有绑定/dispatch owner 中完成，
不新增第二套余额或跨进程恢复机制。窗口三补入 C-H02-5 独立反例。

### H02-L4：provider 覆盖入口可能绕回后置绑定

静态路径：`dispatchRole()` 允许任意 `providerName`，先 await `subagents.start()`，再通过
`bindings.require(child)` 检查绑定。当前交付已经说明 stock `spawn` 在 start 返回前投递 prompt。
因此事后抛错不能证明首轮之前的绑定硬门；错误后的 run 资源归属也须明确。本轮未动态复现。

窗口一用 `providerName: 'spawn'` 建立最小反例；受保护的 dispatch 入口必须在 start 前只接受
具有本次绑定协议的已登记 provider，不能仅凭返回值补验。若保留自定义窄 provider 名称，
给出有效注册的成功对照。对已取得 run 后发生的校验失败，明确处置责任并验证无泄漏。
窗口三独立复核默认入口和覆盖入口，不以“最终 Promise 拒绝”替代零未绑定执行。

## 3. H04 运行时发现的设计裁决

以下依据窗口二的探针报告与 LEAD 对冻结 runtime 打包实现的静态核对；它们尚不是 H04
集成通过证据。准确约束同步写入 [接口交接要求](h02_h04_handoff.md)。

1. `callConfigEquals` 不包含 messages/tools；prepared 通路的第二次 config 检查不能证明
   完整请求不漂移。直接 `llm.stream` 无该 prepared 校验，须单独保留特征对照。
2. `markAgentLoopRequest` 只登记对象。真实 loop 另行冻结 header/tools、消息及请求，并调用
   自己持有的 `preparedCall.stream`。把可变对象手动打标所得结果，不能冒充真实 loop 漂移。
3. **不要求 H02 向 H04 传 `PreparedLlmCall` handle。** prepare 属真实 loop，请求 hook 没有
   该公开参数。H02 交绑定与 recorder 类型，H04 使用真实 loop + mock adapter 证明 prepared
   通路；loop 的 `NO_ADAPTER` fallback 及受保护请求的直接 stream 入口须显式拒绝或证明同等
   硬门，不能假定“有 loop 标记就必有 prepared”。不修改冻结 runtime 或替换 loop factory。
4. 请求摘要须覆盖版本化的完整受支持装配载荷，至少包括有序 messages/content、tools/schema
   与 resolved config；信号等运行对象不直接序列化。未覆盖的新载荷明确拒绝/声明不支持，
   不能因序列化丢字段而默默放行。H04 在等待回执后、委托 next 前对真实请求重新计算摘要，
   并证明之后不会被 middleware 改写；重复记录一个旧 hash 不算复核。
5. 必验 `next()` 前、返回后而流尚未迭代时的 config/message/tool 改写，并观测 mock adapter
   实收材料。裸 API 特征用例记录其实际接受行为；受保护路径的安全用例必须证明零违规派发。
   该摘要不冒充 provider HTTP 字节：runtime 还会投影附件/图片/adapter 可见消息，C00/V01
   的实际适配与 wire 校验继续保留。

另修正冻结记录的资源表：H03 负责 terminal/raw 与 Session flush 兼容证明，H04 负责取消、
静止和请求结算时序；R01–R03/A01 再做生产持久接线和准入。不能把 H03 的 flush 整体后移。

## 4. 三个窗口现在分别执行什么

| 窗口 | 当前指令 | 写入范围与结束条件 |
|---|---|---|
| 一：H02 owner | 按 §2 逐项最小反例、修现有 owner、补接口；保留已有成果与 H01 输入 | H02 原 owned paths 加 `src/request-contract.ts`；不开始 H03。测试发现已覆盖这些目录，无需改工具链。完成后 build→stage→test，登记源码/测试/接口/lock/回执/文件树完整摘要并释放窗口 |
| 二：H04 owner | 只读审查 §3 和窗口一提出的 request 合同，提交具体消费示例、R/C 矩阵修订建议 | 不写 H02 文件，不提前实施 `request-accounting.ts`。原始 API 特征与真实 loop 集成分开；探针需要执行时先协调独占环境，不与窗口一 build/stage 重叠 |
| 三：独立 QA | 更新 C-H02-1…12 与 S1–S5，加入 L2 的真实类型消费者及 L3/L4；保留 H01 历史证据 | 可在自己的 QA 根准备探针；此时不进行最终候选验收。收到窗口一重新冻结及释放声明后接管，完整独立复核并出 verification.json |

构建写权当前分配给窗口一；其余窗口不改共享源码、配置、构建和 staging。窗口三正式验收
开始前，窗口一/二及 LEAD 均暂停修改快照覆盖的输入，**包括执行文档**。

QA 顺序：核对候选身份 → 独占 `check:compat` 并单列构建造成的写入 → `snapshot2 before`
→ 真实类型消费者/机制对照/独立反例/`test:compat` → `snapshot2 after` 分类比较 →
`stage --check`/doctor/身份复比/patch hygiene。受保护共享输入出现 `meta_only_changed` 同样
报告；不能要求合法构建阶段的所有生成物 inode 不变，也不能把测试阶段的同字节重写忽略。
正常 CLI smoke 若会 prepare profile，应放在观测窗口之外单独记录。

四项均收口、窗口三 PASS 后，LEAD 才将 H02 标 done、接口标 frozen，并放行窗口一 H03 与
窗口二 H04 按文件域并行。只有新增变化或具体未决问题才重跑验证，不要求机械重复三遍。
当前无 live、无提交/推送授权；日常 DSH 与冻结 runtime 继续保持隔离。

[返回总执行入口](README.md)
