# Gate-H 四组返修批次交付（2026-10-03）

状态：**submitted_for_independent_qa**。本文件为 owner 交付记录，不裁定 Gate-H PASS。正式 Gate-K 等待；第 03–08 份未启动。原 49 项仍为 2 完成 / 9 进行中 / 38 待实施（任务板枚举 planned）。

本批遵循[独立验收返修指导 §§3–4](../../../docs/dsh_execution_20260928/stage_whole_package_review_20261003.md)与[整阶段指导](../../../docs/dsh_execution_20260928/remaining_work_and_batch_repair_guidance_20261003.md)。既有 dirty 树作为基线；未切分支、提交、重置或修改内核。HEAD 为 `d48b4e4b22c94c82b45d2179ba452d72b164102d`。

## 四组修改与实际观察

| 组 | 修改 | 本批证据 |
|---|---|---|
| 激活 | 先按 active peer 对应安装回执核 compiler/依赖/lock/Node 版本与绑定，再验证 active 与 target runtime 实际 inventory、锁、版本及可信候选身份；manifest 指定的 Node 必须实际存在、与当前执行 Node 同字节且版本匹配；target 回执必需且逐字段匹配。临时 link/receipt 准备后 rename 提交，回执提交异常回滚 peer。activate 不建立新的安装基线 | `test_gate_h_entry_repair.py` 实际 Node 入口与 Python wrapper：compiler/lock 漂移、active/target 缺回执、错误 Node 版本、Node 缺失路径、同版本不同字节 Node/runtime/候选身份均拒绝且两个回执和链接保持。真实 fs rename 提交异常注入观察到回滚；两次合法切换并 verify 成功 |
| 审计 | setup/audit 共用 `LOOP_ORIGIN_TOUCHED` 与 pristine-base 验证。compatibility 独立登记的 base 身份、base manifest、实际树、锁均必需；实际五文件差分、manifest、compatibility 和当前候选 hash 一致才继续 | 实际 setup：正确五文件成功，少第五文件/额外文件/错 base 拒绝且无成功 manifest。实际 audit：漏声明、多文件、缺 base/manifest、错 base/候选/receipt 均拒绝；合法路径通过。测试只替代与本边界无关的 provisioning/staging 设施，真实 audit 与正常 doctor 另完整执行 |
| smoke | 从 `verify_staging()` 的 `tree_sha256` 取身份，核实际 staged build receipt 与 staging record；运行后再核 staging/receipt 不变。无 stage 的普通 Web 明确 `web_runtime_only`，compat 必须有有效 stage | 选择回归核显式 flag、仅环境选择、冲突、缺候选、旧默认入口；检查实际 launcher argv/env、默认证据文件、真实 JSON，以及旧 evidence 文件前后不变。正常 web/compat 各 exit 0，HTML/非空 assets HTTP 200、端口关闭、0 模型 turn、非空正确 staging 与 receipt |
| 交付 | 92/24/旧 hash 段落标历史，注明早期日志绑定不能从后来 93/26 日志反向补造。source 模块头、source patch、当前 interface 统一 capability 门控 API。compatibility 当前 build/stage 与旧 round9 分开 | 本批前后完整清单、driver、原始 argv/cwd/选择环境/内层退出及日志；当前 93 个源节点与两份实跑日志逐项匹配，未匹配 0；源 patch 与固定源码四文件 git diff 完全一致；三份声明与独立 tsc 输出一致 |

当前 API：`peekLoopDispatchOrigin` 只给 frozen session/signal 快照；`admitLoopDispatchOrigin` 保留导出，必须与私有 capability **对象同一**才一次消费；`runOutsideLoopDispatchOrigin` 只清空作用域。无 exported take/entry-ack。受信派发经静态模块入口、私有 WeakMap 及真实 runtime 身份，capability 不经公开 resolver；销毁只注销自身实例。来源/生命周期实现与 runtime 字节保留；本批固定源码仅修改模块头注释，并重新登记 source patch。

## 当前候选身份

| 对象 | delivery | source-built（仅源码等价证据） |
|---|---|---|
| runtime tree | `671daa1a7a06728d69a4bdec6da3d33a3616c4e788f63579ed07f3ae81e0e16c` | `3076d2fcdbf6b2b49167e8132ce9b5801d95079a36f9bd05af17302e8482be97` |
| staged build receipt | `b6d57b715301ca503be7afa8eec3339cb734545f9edfcff17c31e977b59b6c86` | `3993378a51bcbd4d4c19f5a19dca2b8a3e7c2f511b3b8174833e0b1bec192c91` |
| staging tree | `30f18c5f31ed58a302c22d1996c699b45d2ab565325a57f92b1e8e9d50bfad98` | `15bc87da05654b625f9c430830a41371a300a0b7e96d9d3007b0ff66d8c6e631` |

outputs digest 两侧仍为 `9c00688b090ab3bb744ba83975e5ab447fe75fd61798906d15ba13fa4e750e95`。pristine base `43490765…`、旧默认 runtime `7e8f199b…` 保持。source patch 当前 SHA-256 `87941d847abb581abe65a924773b980b702b95f03cda4a23831bba9cce3bb46b`；runtime patch script 保持 `b36b887f…`。类型三份未变。工具链脚本是 build config 输入，故按 source-built→delivery 串行重生成两侧 build/stage；最终 peer/global build 指向 delivery。

## 本批新鲜验证

| 集合/行为 | 结果 |
|---|---|
| 原 launcher 集合，11 文件 | 两侧各 93 passed / 0 failed / 0 skipped，内层 exit 0；原断言未修改 |
| 来源与生命周期独立反例 | 两侧各 10/10 与 3/3，内层 exit 0；prepared/fallback 正例均保留 |
| B02 全目录 | 48 passed / 0 failed / 0 skipped，exit 0。重写无效字典测试为真实 setup/audit 入口测试，新激活回归与 smoke 路由断言均实际执行 |
| 执行身份原集合 | 24 passed，exit 0；不冒称全部跨进程业务恢复 |
| 正常 doctor / audit | delivery exit 0 |
| 正常 web / compat smoke | 各 exit 0；身份、HTTP 与清理行为均符合上表 |
| 独立声明编译 | 两包 exit 0；257/385 个编译输入及 compiler/config 前后未变，三个声明与两套候选同字节 |
| patch hygiene | `git diff --check` exit 0 |
| 受测输入 | 108,615 项前后 bytes/link/inode/mtime 完全一致；首个 source-built suite 绑定 probe 设置修复前清单；差异严格限于 probe peer 复制目录，suite source/test/driver/runtime/receipt 不变（probe-setup-input-closure.json） |
| 已验内核 | 与原独立验收指定 baseline 的 791 份 src/tests SHA-256 全匹配；未跑 4129、未修改 Python 内核 |

历史 r1（B02 46 项）已完整封存，当前被 r2（48 项）替代：收口检查补上目标 manifest 指定 Node executable 的存在/字节/版本校验，并用实际入口补缺路径与同版本伪 executable 反例。r1 的完整包与原日志保持在 `.dsh-dev/run/w2-gate-h-repair-20261003-final/`，不当作当前结果。r1 曾遇到封存 driver 的 Node `ℹ`/TAP `#` 汇总格式及 791/764 核对清单选择错误，原内层成功结果保留；这些是历史 r1 汇总修正，不是 r2 产品失败。

r2 复制 probe 时误跟随 peer symlink，Node 在断言前因缺 transitive dependency 拒绝加载；随后恢复原链接，保留失败原日志/输入于 `probe-setup-diagnostic/`，设置修复与完整差分核对在 `probe-setup-repair.json` / `probe-setup-input-closure.json`。已经完成的 source-built 93 节点保持，全部探针最终实跑通过。产品源码、原测试、runtime 或 receipt 没有因这个设置修复变化。最初外层沙箱的 spawnSync EPERM 经获准宿主执行解决，项目自身 bwrap 断网/只读隔离保持。

## 冻结包与复验入口

稳定封存目录：`.dsh-dev/run/w2-gate-h-repair-20261003-final-r2/`。原始运行根：`/tmp/c2p-gate-h-repair-20261003-final-r2/`。这两个根对应同一批，不引用 round9 的覆盖日志作为新入口证明。

- `before-inputs.json` / `after-inputs.json` / `input-closure.json`：全部受测输入与前后核对。
- `probe-setup-diagnostic/before-inputs.json` / `probe-setup-input-closure.json`：第一套 source-built 实跑与 probe 设置修复的绑定。
- `FROZEN_INPUTS.tar.gz` / `archive-input-map.json`：逐成员核 SHA-256 后保存的完整受测字节及路径映射，含两候选/pristine/旧默认 runtime、Node/Python、安装工具链/worker、源码、测试、fixtures、drivers、profiles、build/stage；声明编译读集另并入。
- `*.command.json` / `*.exit` / `*.result.json` / `*.log`：原始命令、内层退出与输出；正常结果为 `normal-smoke/web-smoke.json` 和 `compat-smoke.json`。
- `candidate-identities.json`、四份 runtime inventory、两侧 manifest/toolchain/staging/staged receipt：同组身份。
- `original-at-node-matrix.json`、`gate-h-at-matrix.json`：原 93 节点与 AT 行为映射；本轮四组扩展对照指向原始执行证据。
- `kernel-baseline-inputs.json` / `kernel-preservation.json`：原 791 份受测内核保持；r1 的 764 项诊断副本仅保留历史来源。
- `release.json` / `status.json` / `SEALED_FILES.sha256.json`：运行器结束、读集释放、owner 状态和证据封存完整性。seal 不替代输入身份。

主要实际执行入口：

```bash
python <raw-root>/freeze_driver.py snapshot before
python <raw-root>/freeze_driver.py run
python <raw-root>/closure_driver.py
python <raw-root>/archive_inputs.py
```

`freeze_driver` 调用 `review_driver suite/probe <candidate>` 与 `ops_driver <delivery> b02/identity/doctor/audit/web/compat`；内层精确 argv/cwd 与选择记录在各 `.command.json`。原 suite 在已核候选 peer/staged receipt 的只读 namespace view 上执行，不 rebuild/restage。正常 smoke 仅把真实 CLI 会改写的 profile 映射到同字节临时副本，身份字段由原脚本生成。复验应读取冻结输入，不能用会重建候选的 `check:compat` 取代审查。

本交付文档、导航和 owner 提交记录在测试读集释放后写入，封存时另保存文档快照；不反向纳入已经结束的测试清单。Gate-H 四组及受影响行为仍交独立 reviewer 复验；通过后由 LEAD 确认正式 Gate-K，再按第 03 份顺序实施。无模型 live、默认切换或后续阶段授权。
