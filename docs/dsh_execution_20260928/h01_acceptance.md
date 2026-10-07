# H01 验收裁决与 H02 开工交接

> 2026-09-28，LEAD：**AT-H01 PASS，H01 done，H02 ready**。窗口三已释放验证窗口。
> 本次只登记验收与派工；负责人未修改实现、未重跑产品测试、未启动内部实施 Agent。
> Gate-H 仍需 H02/H03/H04，未放行 Writer 业务接入或 live。

## 1. 验收依据与身份

实施交付见 [H01 修复证据](../../integrations/dsh/dev/H01_acceptance_fix_evidence.md)。
窗口三的 [正式报告](/tmp/c2p-dsh-h-qa-w3-20260928/reports/H01_verification_report.md)
保留两遍结果；pass 1 是完整主记录，pass 2 是同一冻结输入的复验，不替换前者：

| 记录 | SHA-256 |
|---|---|
| [pass 1](/tmp/c2p-dsh-h-qa-w3-20260928/reviews/H01_verification.json) | `88d2b5e5d83fc5cadfc3c1306eaf4652ad924f54264cf51d677f782843ccc334` |
| [pass 2](/tmp/c2p-dsh-h-qa-w3-20260928/reviews/H01_verification_pass2.json) | `e1b2fc6a64b79bdfb5f11078e54d89860565e7e3fc3ba3d825f7c67f9139cf9e` |
| 实施修复证据 | `1b7252384544f6a54d898fb85f5eb1e22e3309bda099fbe013a488578518d865` |

负责人只读重算两份 JSON 引用的 23 个命令日志/产物摘要，与声明相符；当前 26 个受测源文件
仍与 QA 前后快照一致，无差异。原始输出位于
`.dsh-dev/run/qa-w3-20260928/h01-recheck/` 的 `freeze/`、`freeze2/` 及各独立探针日志，
不作为新增源码纳入提交。准确 argv、退出码与日志摘要以两份 QA JSON 为准。

| 受测对象 | 冻结身份 |
|---|---|
| 业务代码对照基线 / HEAD | `0918ee76d079b9392ec03400c0c4c9fdff5bc784` / `d48b4e4b22c94c82b45d2179ba452d72b164102d`；工作树增量单列 |
| runtime | DSH `0.1.5-rc.3`；`7e8f199b67027944d646e0c99f5041d4704360377e4d7466fce683c1d468d3ab` |
| `src/index.ts` | `4053ef1095c3753bcd7fda53feb2e2b1768379c20b8a7bdb8b9edded53fe3c65` |
| `src/task-tools.ts` | `0ed976fe58e527e1101cc94f4124f18460e65b0fcf4030eed78cd839665a37b9` |
| `tests/loader.test.ts` | `4e6e6699864222fc0c18f3d57db0359a804eea131e387151468580d519821c24` |
| 构建回执 | `ea2289b147582a68cf284d7392a809261a97534cef18733396a5a70fb744a437` |
| `outputs_digest` | `6c1c6a0899670b98ffa9a77c1875cd4a084096a8c2ca9665195b09afbf6a45d3` |
| staging 回执 / staged 树 | `3a6716400cd1215ebadc1410770630e1598c95ebe0253357a6f465e277ef162f` / `abe6365d55d4bc6af128aecfbe49da5ff1867201d727f95c177c53fd41304f5f`，8 文件 |
| toolchain 回执 | `be8d002475d4572820f87a385b1209f5a37dd4bfee9a559fbbe50ae27ae8ad39` |
| QA 源清单 | `1caebd53ab092e3481c053b9e175c0b2d86fd53c16f20e1aa1e5f6e4e39b1830`，26 文件 |

B00 历史冻结及 `compatibility.json` 的 null build 观测不回填。H02 后续新增源码、配置或测试
必须另记实际执行身份；H01 记录不批准未来字节，更不批准模型请求。

## 2. 关闭的问题与实际证明

| 条款 | 窗口三两遍正式结果 |
|---|---|
| 真实 Loader、metadata、Host/preset 分层 | 真实组成加载；Host 无模型工具；加入 preset 后才可见/执行；无 default export 丢失本模块元数据 |
| H01-QA-1 实际 preset 身份 | root 为 `code2paper`；override/child 为 `qa3-drift`，不取伪造 session metadata；未 join 返回 `UNKNOWN_TOOL` 且无 note 写入 |
| H01-QA-2 共享输入保护 | 夹具仍存在时检查共享 profile 字节及 inode/mtime、module fallback、staging 等均未变；变更夹具只在本轮私有根 |
| H01-QA-3 重复注册与越域发布 | 分别触发真实同名冲突与 root-realm 泄漏守卫；既有 Agent 仍能经 public `ctx.tools.execute` 执行，原服务/standing 身份不变 |
| generation 与销毁 | child 继承父的同一 standing key/fiber；新 root 可读取变更 generation；单 Agent dispose 不毁共享组成，root teardown 释放组成 |
| boot 后失败清理 | 注入运行自行 exit 1，约 9.5 秒，未被 timeout 强杀；端口释放并经独立拒连确认，标记被消费、私有目录被清理；随后正常运行恢复成功 |

两遍 `check:compat` 均 exit 0、16/16；独立 R1–R6 均 exit 0、8/8；无标记恢复均
exit 0、16/16。注入运行预期 exit 1，失败只在 H01 before hook，6 个工具链用例仍通过。
`doctor`、`stage --check`、`git diff --check` 均 exit 0；构建内容可复现、输入快照无变化。
Python 相关文件未变，按既有绑定证据未重复执行。上述是 QA 执行结果，不是负责人本轮新跑。

## 3. 非阻断备注及后续责任

- **N1：旧 profile 同内容重写。** 两个验收窗口前的 12:39:36 写者仍未识别。
  已静态定位冻结 CLI `prepareProfile()` 无条件重写空 `cordis.yml` 的机制
  （`dsh/lib/profile-boot-Dk-7KqJc.js:192–209`），不能据此断定历史事件的写者。
  后续 QA 将 CLI/smoke 与输入不变验证分开，窗口一/三共同遵守单写者交接。
- **N2：未演练 SIGKILL。** H01 只证明本次 boot 后异常的清理；不声称硬杀恢复已验证。
  私有测试目录的残留不阻断 H02，生产故障恢复仍由后继任务独立验收。
- **N3：外围快照只记字节。** 本次另有全窗口 profile mtime 早于开窗及探针内 inode/mtime
  证据，接受本次结论。窗口三在 H02 QA 准备时改进自己的快照器，显式记录写元数据；
  保留 H01 已冻结探针、快照和报告原字节，使用新任务目录/版本。
- **N4：实验身份不同。** 首轮 13 项与最终 16 项分别绑定输入；两遍通过不合并成新测试数量。
- **N5：命令退出码归属。** pass 1 的 shell 链误读由独立重跑澄清，pass 2 未再现。
  后续逐条记录命令及其退出码，不引用误读为产品失败。

实施报告 §9.6 的边界解释以此为准：`boot()` 内部已创建 context，失败时由其 catch
调用 `ctx.fiber.dispose()`；成功返回后的清理由调用方负责。本次注入只验证后者，
没有据此宣称 `boot()` 内部所有失败路径已实测。为保留受测身份，不改原交付报告。

## 4. H02 派工与交接

**窗口一执行 H02**，依据 [第 01 部分 H02 任务卡](01_baseline_and_dsh_compatibility.md)
及 [接口交接要求](h02_h04_handoff.md)，拥有以下拟新增文件：

- `integrations/dsh/src/session-binding.ts`
- `integrations/dsh/src/role-dispatch.ts`
- `integrations/dsh/tests/binding.test.ts`
- `docs/dsh_execution_20260928/h02_interface_freeze.md`

使用明确标注的 mock claim recorder 验证时序：成功回执先于创建；在 `agents.create({setup})`
内完成可信绑定与组成，材料准备、工具访问和模型请求均不能抢先。生产 claim 持久性留
R01–R03 接线复验，不在 TS 建第二套持久账本。

先调查标准 spawn 的实际路径并保存实验依据；若不能满足上述时序，按既定设计使用公开窄
provider 调用现有 `agents.create({setup})`，保留 loop factory，在接口冻结记录中写明决议。
不通过异步 `agent/created`、`pre-step` 或 start 返回后补绑来绕过门。

交付必须包含：阻塞/拒绝 claim 时零材料访问、零 adapter 调用；伪造 task ID、未绑定 child、
旧 fence、创建取消的拒绝与清理；真实导出/类型、mock claim/request recorder 签名、资源
owner 与取消/flush/dispose 责任、可运行的 H03/H04 消费示例。组合 helper 的 caller 必须
声明 `code2paperBridge` inject，child 的 `undefined` 返回不能当成成功；H01 note ledger
不是任务身份或权限权威。

窗口一拥有本轮 build/stage 写权，交付后冻结输入、释放给窗口三。必要的共享入口/配置
改动先列明接线用途，由 LEAD 分配写权，不能让其他窗口同时修改。只用隔离环境和无网络
mock；不改冻结 runtime、日常 DSH，不做 live、不提交 Git。

**窗口三准备并独立验收 H02**：先维护自己的新版本证据工具与反例计划，不与窗口一同时
构建。拿到冻结输入后核对真实调用顺序和资源清理，输出具名结论，不自行修实现。

**窗口二保留 H04 准备**：可只读评审 H02 消费需求，不预造接口或开始 H04 实现。
H02 通过且接口由 LEAD/QA 确认冻结后，窗口一 H03 与窗口二 H04 才能并行；共享构建仍串行。

本次状态为 4 项 done（B00/B01/B02/H01）、H02 ready、其余 44 项 planned。
负责人只处理设计、分工、证据与裁决，不直接或通过内部 Agent 代替实施窗口修改实现。

[返回执行入口](README.md)
