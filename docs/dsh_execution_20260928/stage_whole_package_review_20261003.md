# 原第 01 份冻结整包独立 Gate-H 审查（2026-10-03）

**结论：Gate-H CHANGES_REQUESTED，正式 Gate-K 继续等待。来源派发和实例生命周期的原 GHS-1/GHS-2 已独立关闭；当前剩余修改集中在 B02 新工具入口及交付证据。** 不要求重新设计已经通过的来源机制。第 03–08 份仍按原依赖排队。

本次由当前 Codex chat 独立执行，未参与窗口二本次实现。依据原第 01 份、[验证合同](verification.md)与[集中指导 §3](remaining_work_and_batch_repair_guidance_20261003.md)，复跑完整冻结候选并验证新入口的失败分支。owner 的“六组全部闭环”仍有下文四组未闭合事项；已通过成果明确保留。

持久核查数据：[stage_whole_package_review_20261003.json](stage_whole_package_review_20261003.json)。原始命令、输出、探针和输入清单位于 `/tmp/c2p-gate-h-whole-20261003-as7rfjgg/`。本报告只证明所列冻结输入，不外推到后续修改或模型 live。

## 1. 已独立确认的成果

| 检查 | 新鲜实测结果 | 对应结论 |
|---|---|---|
| 两侧原 launcher 套件 | 每侧 11 文件、93 pass / 0 fail / 0 skip，Node exit 0 | 93 个源测试节点与两份日志逐项匹配，未匹配 0；保留全部原断言 |
| 原来源边界独立反例 | 每侧 10/10，exit 0 | prepared/fallback 正例、resolver Proxy、伪能力同步观察、公开 iterator 获取/迭代、公开布尔入口均成立；合法 R/D/S/受保护 adapter 各一次 |
| 原销毁重建独立反例 | 每侧 3/3，exit 0 | A prepared/fallback 正例，销毁 A 后 B 两路均 completed、各计一次；GHS-2 原失败关闭 |
| C25–C27 | 两侧原套件均实际运行通过 | C25 包括 prepared/fallback；C26 观察两个 adapter 的实例标签和不同 session；C27 实际销毁 A→创建 B→两路完成 |
| 交付 B02 原 Python 目录 | 26 passed，exit 0 | 现有隔离测试通过；新增测试的有效性问题另列 §3.1–§3.3，数量不代替覆盖 |
| 交付正常 smoke | 原脚本 web/compat 均 exit 0，HTML/非空 assets HTTP 200，关闭后端口关闭，零模型 turn | D3 候选选择与正常入口已修；输出 staging 身份仍为 null，见 §3.3 |
| 交付 doctor / audit 正例 | 均 exit 0 | 当前 peer 指向 delivery；doctor 所报 staging 与最终候选一致；audit 的缺输入反例另列 §3.2 |
| 执行身份回归 | 24 passed，exit 0 | 实际执行原 test_execution_identity.py，未把它冒称全部跨进程业务恢复 |
| 三份类型声明 | 两包独立 tsc exit 0，两个 index.d.ts 与 dispatch-origin.c2p.d.ts 均同字节 | 交付和 -built 均匹配新生成类型；分别绑定 257/385 个编译依赖/编译器实现及配置，前后未变 |
| 源码及五文件差分 | source patch 等于固定源码四文件 git diff；两包源码 JS 等于 -built；两候选 touched 均等于实际五文件差分 | D1 当前产物清单已修；GHS-3 类型部分已通过，全文交付说明仍有余项 |
| owner 封存 | 42 个登记文件的 SHA-256/字节数全部一致 | 原日志 93/93、26、doctor、smoke 与声明对应；封存日志不是测试输入冻结清单 |
| Python 内核保持 | 原已验清单 791 份 src/tests 全匹配 | 保留 K01–K04 component；没有重跑 4129，没有启动 C/R |

同 child 的 `joint-child.test.ts` 两侧均通过真实 reserve→dispatch→adapter→terminal→settle→flush，再用 `spawnSync` 从落盘字节重建 committed。H01 Loader/generation、H02 创建期绑定、H03 raw/V4/错误终态/flush、H04 材料/回执/取消/资源等原合同的实际节点见核查数据所引用的 AT 矩阵。

`-built` 保持“源码等价证据”的既定范围。本轮没有要求或声称该侧 B02/doctor 完成；GHS-4 按范围澄清关闭，不把缺 worker 再列为当前阻断。

## 2. 本次冻结身份

分支 `codex/agentic-p4-benchmark-cutover`，HEAD `d48b4e4b22c94c82b45d2179ba452d72b164102d`，既有 dirty 内容保持。

| 对象 | SHA-256 |
|---|---|
| delivery runtime | `671daa1a7a06728d69a4bdec6da3d33a3616c4e788f63579ed07f3ae81e0e16c` |
| delivery staged build receipt | `ea004d4592ce67bdeb26017eb4556e3f6fb601f375b2f7b8f3d32b9af33c4e89` |
| delivery staging tree | `60acfbb2ec14fedca2880eb6a40b035ccb4df15851b175eb09a6741f9b1bb304` |
| source-built runtime | `3076d2fcdbf6b2b49167e8132ce9b5801d95079a36f9bd05af17302e8482be97` |
| source-built staged build receipt | `78292cbed43d15d4c436601e784de68934cf49bd27ecd95a9328e3e8b5fc6250` |
| source-built staging tree | `b4c9e4454b8ba6b223b38861dbb9b91def444da12bd3dc9c67b95b9008a6b229` |
| outputs_digest | `9c00688b090ab3bb744ba83975e5ab447fe75fd61798906d15ba13fa4e750e95` |
| runtime patch script | `b36b887fc71e90de84080897169f79bddf370793a293ca1e54c03fbcb02c8e75` |
| source patch | `0db693e794feea78f8087198078df04d41614804898aec329cf5628a45987512` |

两侧原套件使用候选自身的真实 staged receipt 和 peer 的只读 mount 视图；先通过原 toolchain/staging 检查，再运行原测试。没有切换宿主 peer，没有 build/restage，没有合成替代回执。正常 smoke 使用原脚本，仅把会被 CLI 重写的开发 profile 映射到同字节临时副本。

## 3. 全部剩余修改：四组，同一原阶段连续完成

### 3.1 P2 · activate 把依赖漂移重新登记为可信，失败前会改 peer

位置：`integrations/dsh/dev/toolchain/toolchain.mjs:288`，尤其 `:306–307`；Python `activate_candidate()` 是该入口的真实调用方。对应集中指导 §3.2 的“先验证已有锁/依赖字节、失败不自动更新信任基线”。

独立探针复制真实工具链与已安装依赖到临时仓库，执行未修改的 `toolchain.mjs`；未改宿主工具链。结果：

| 单变量对照 | activate 前 verify | activate | activate 后 verify |
|---|---|---|---|
| 原字节 | exit 0 | 不需要重写 | 原回执不变 |
| typescript.js 只追加注释，版本号不变 | exit 1，明确 bytes drift | **exit 0，重写 toolchain.json** | **exit 0，漂移被接受** |
| package-lock.json 只增加换行 | exit 1，明确 lock changed | **exit 0，重写 toolchain.json** | **exit 0，漂移被接受** |

另一个目标候选声明错误 Node 版本：activate 最终 exit 1，但先前有效 peer 已被改指该错误目标。原因是只核两个包的版本字符串，就先 `linkPeers()`，再 `toolchainState({writeReceipt:true})`；已有回执的 bytes/lock 校验只在 false 分支执行。

证据：`activation-probe.json` 与 `activate-*.log`。这是实际入口行为，不是推测当前候选已经被污染；当前正式候选的已测字节仍有效。

一次修完：

1. 分离“已安装编译器的可信基线验证”和“目标候选的选择绑定”。先对已有安装回执核实际依赖字节、锁、版本、Node；候选切换不能重新确认已漂移的安装。
2. 在任何 unlink/symlink/receipt 写入前验证目标 manifest 的候选身份、runtime/lock/Node 实际字节。缺基线、缺目标或漂移均明确拒绝。只有原受控 install 才能在真实安装后建立新的安装基线。
3. 准备好目标链接和回执后再提交切换；失败保持旧链接与旧回执一致。校验失败不得留下半切换状态；写入失败也有明确恢复/回滚。沿用独占构建规则，不新增第二套产品权威。
4. 对实际 Node 入口和 Python wrapper 增加上述三个反例、缺回执和合法双向切换；检查失败前后两个对象均未变。不要只测试版本字符串或模拟返回成功。

### 3.2 P2 · audit 在 pristine base 不可用时跳过必要检查

位置：`scripts/dsh_dev.py:1228`。`if base/runtime.is_dir()` 包住整个实际差分与 declared touched 检查，缺目录时后续仍返回 PASS。

在只读 namespace 中覆盖候选 manifest/基树视图，真实运行 `python scripts/dsh_dev.py --candidate ... audit`：

| 对照 | 实际退出 |
|---|---|
| 正确 manifest、基树可用 | 0 / PASS |
| manifest 漏新增声明、基树可用 | 1 / 拒绝 |
| 同一个漏声明 manifest、基树不可用 | **0 / PASS** |

证据：`audit-failure-probe.json` 与 `audit-missing-declaration-*.log`。宿主 manifest/runtime 均未修改。

一次修完：

1. 对声明为 patched 的候选，基树、基树 manifest 和可信基树身份是必需输入；缺失/不可读/身份不符返回具名非零，不能省略检查后返回 PASS。
2. 先验证基树实际 inventory 与其可信声明、当前候选记录的 base hash，再计算差分；同时核差分/允许改动域/manifest/compatibility 中的同一候选字段。避免只用一份可随意修改的 base 内容作参考。
3. `loop_origin_setup` 和 audit 共用允许改动域定义，实际差分仍由真实输入生成；不靠同步编辑三份手写列表证明一致。
4. 重写 `test_development_environment_isolation.py:478` 的新增测试：它当前只对本地构造字典算差分、比较手写列表，完全没有调用生产 setup/audit，删除生产校验也不影响该测试。测试应执行实际生产入口，覆盖正确五文件、漏第五文件、额外文件、缺基树、错基树身份、错候选回执，并核拒绝发生在写入/成功输出前。

### 3.3 P2 · 正常 smoke 缺最终 staging 绑定，回归断言未覆盖真实输出

位置：`scripts/dsh_dev_smoke.py:128`。实际 staging.json 的字段是 `tree_sha256`，脚本读取 `staging_tree_sha256`，因此两种新鲜正常 smoke 都输出 `"passed":true` 同时 `"staging_tree_sha256":null`。HTTP/关闭行为已通过，问题是证据身份缺失。

证据：`normal-smoke/web-smoke.json`、`normal-smoke/compat-smoke.json`。当前正确 staging 是 `60acfbb2…`，doctor/audit 均已确认。

一次修完：

1. 从已经验证的 staging 结果读取正确字段；对 compat 的必需身份要求非空并一致。普通 web 若采用不同证明范围，明确标注，而不是静默吞异常后给出空绑定。
2. 保留已经修好的候选选择、显式 evidence-dir、真实 HTTP 和清理逻辑。记录 candidate、runtime、实际 staging/receipt 与最终命令的一致关系。
3. 加强 `test_development_environment_isolation.py:409`：当前正例只执行显式 flag＋自定义证据目录；末尾检查不存在的 `web-smoke.synthetic-leak.json`，并不能证明真实默认输出没有写错地方。加入仅环境选择、候选默认 evidence 目录、实际 launcher argv、真实输出文件前后比较、非空且正确 staging 的断言；继续保留冲突和不存在候选反例。
4. 修后用同一正常脚本完成 web/compat，保存原始退出和结果 JSON。既有 HTTP 正例无需重新设计，正常结果不得借自定义 driver 改写身份字段。

### 3.4 P2 · 当前/历史文档与冻结输入仍未完整对应

已经修好的部分：compatibility 的当前 build/stage 数值和日志路径、五文件清单、interface-diff 的主机制描述、最终 doctor 记录都与本候选对应。剩余确定差异：

| 位置 | 仍未解决的内容 |
|---|---|
| `integrations/dsh/dev/runtime-0.2.0-rc.1/w2_delivery.md:135` 之后 | 仍以本日“第九轮整包交付”列 92/24，receipt 为旧 -built 的 c10d1bca、stage 为旧 delivery 的 6f0c39cb；最后引用的 round9 根现在是 93/26 日志 |
| `integrations/dsh/dev/H04_request_evidence.md:124` 之后 | 同日第九轮仍写 cancellation 29、总套件 92、B02 24；未与 C27/当前批次区分 |
| `integrations/dsh/dev/runtime-0.2.0-rc.1/loop-origin/evidence.md:96` 附近 | 当前核心修复段仍描述“删除公开 admit、peek＋take entry-ack”，与实际保留 capability-gated admit 的实现不符；早期段落没有逐段绑定旧候选 |
| 固定源码 `.dsh-dev/sources/loop-origin-020/packages/core/agent-loop/src/dispatch-origin.c2p.ts:5` | 模块头仍称公开消费已删除、存在 entry acknowledgement take，与当前导出不符 |
| 新 owner 封存清单 | 42 项为日志/命令/结果及说明；未包含完整受测 source/test/fixture/driver 的前后清单。compatibility 的 sources 列表与 build receipt 也没有覆盖 cancellation/B02/smoke 等全部测试输入 |

一次修完：

1. 当前交付只有一个准确入口，按候选成组引用本批输入和产物；旧 92 项报告明确标历史，并绑定其原输入/日志范围。历史原始输出不改数值、不冒称当前，无法读取的旧证据诚实登记。
2. 统一 current API 说明；所有 take/entry-ack 历史段落标明旧机制，当前段落说明能力同一性校验及一次消费。只更正注释/说明所需的源变更也记录进 patch/source 身份，不能直接修改冻结候选字节后复用旧树 hash。
3. 新最终批次使用 fresh、独立封存根，保存准确 argv/cwd/选择环境、内层退出、测试集合、完整实际读集前后、生成器/验证 driver、运行包和两候选回执。seal 校验覆盖证据完整性，输入清单覆盖“究竟测了什么”，二者分工明确。
4. 将本报告已通过的 93 节点映射及原 AT 行为继续作为基础，新增 §3.1–§3.3 的生产入口反例；不按测试数量或一份 status=PASS 汇总关闭全部问题。当前审查的前后清单可以证明本次新鲜运行，不能反向补造 owner 历史测试的输入。

## 4. 一次返修的顺序与终点

窗口二仍负责原第 01 份，按以下一个连续批次完成，不逐发现等用户续派：

1. 先修 activate 的前置验证/失败保持，再修 audit 的必需输入与差分合同；给实际生产入口补行为回归。
2. 修 smoke 身份字段及证据路径断言，同时统一当前 API/历史范围、交付索引和冻结输入清单。
3. 新工具链属于 build receipt 的配置输入；按实际变化重新生成相应 receipt/stage，候选成组绑定。若 runtime/source/types 字节未变，保留本批来源、生命周期及类型结论，不重新探索接口；有相关源变更时准确列影响并复验。
4. 聚焦反例通过后，执行一次最终阶段原集合及正常入口验证；写入新的完整冻结包。共享 peer/lib 操作串行，最终回到 delivery。-built 仍只声明源码等价范围。
5. 提交后独立复验本报告四组及真实受影响面，检查原 AT/输入保持，给出一次完整 Gate-H 裁决。owner 状态仍 submitted_for_independent_qa，不自批 Gate-H。

窗口一保留 791 份未变内核及已验 component，不重复实现/调查/4129。只有实际 Gate-H PASS 后，LEAD 确认正式 Gate-K，才启动原第 03 份 I01→C01→C00→C02→C03→C04；Gate-C 后第 04 份。原 49 项任务状态和 live/默认切换边界不变。

## 5. 命令、独立性及读集释放

本批实际运行器：

```bash
python /tmp/c2p-gate-h-whole-20261003-as7rfjgg/review_driver.py /tmp/c2p-gate-h-whole-20261003-as7rfjgg suite 0.2.0-rc.1+loop-origin.1
python /tmp/c2p-gate-h-whole-20261003-as7rfjgg/review_driver.py /tmp/c2p-gate-h-whole-20261003-as7rfjgg suite 0.2.0-rc.1+loop-origin.1-built
python /tmp/c2p-gate-h-whole-20261003-as7rfjgg/activation_probe.py
python /tmp/c2p-gate-h-whole-20261003-as7rfjgg/audit_failure_probe.py
python /tmp/c2p-gate-h-whole-20261003-as7rfjgg/types_audit.py
```

`review_driver.py probe <candidate> capability-boundaries.test.ts/registry-lifecycle.test.ts` 两侧分别实际执行；`ops_driver.py <delivery> b02/doctor/audit/web/compat/identity` 各执行一次。每条内层 argv/退出/原始输出见 raw 根对应 `.command.json/.exit/.result.json`；activate/audit 反例逐命令数据见各 probe JSON。Python 目录测试均关闭 pytest cache，正常 smoke 指向本批证据根。

前置环境问题如实保留：第一次外层 sandbox 阻止 bubblewrap NETLINK_ROUTE，尚未启动产品测试；获准使用宿主执行环境后，仍保留项目自身断网/只读隔离。第一次独立探针未映射进 launcher 的 /tmp 视图，Node 未加载文件；补只读映射后原断言执行通过。这两类失败不算产品缺陷，也没有把外层 runner 的 exit 0 当 Node 通过。

**正式释放：2026-10-03 16:05:42+08。** 主读集 1275 项 bytes/inode/mtime 全部相同；四棵 runtime 与 manifest 身份相同，宿主 peer、两侧 staged/global receipt、owner 封存未变。类型编译依赖另有前后清单。宿主扫描 1766 个进程，相关验证 PID 0、不可读 cmdline 0，全部记录命令已返回。

审查期间没有修改生产代码、原测试、共享链接、候选/owner 证据，没有安装或重建原包，没有模型调用。读集释放后才新增本报告、持久核查数据和协调记录；这些文档变更不改写上述冻结运行结论，也不复用旧离线回执授权未来 live。
