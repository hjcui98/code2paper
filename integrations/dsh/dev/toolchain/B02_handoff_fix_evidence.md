# B02 工具链交接与隔离修复证据（2026-09-28）

本记录追加修复证据，不改写 [原 B02 报告](../B02_environment_isolation_evidence.md)。本轮完成
测试发现与类型覆盖、构建/stage 顺序、运行包边界、隔离启动入口、worker 安装环境及 stage
并发代次一致性修复。H01 源码/预设尚未实现，真实开发 staging 仍为 `src_present: false`、
`entry_present: false`、`patch_present: false`；这些结果不等于 DSH Agent/Loader 兼容通过。

## 代码与运行身份

- DSH `0.1.5-rc.3`，Node `v25.8.2`，TypeScript `5.9.3`，`@types/node` `25.9.3`。
- 完整 runtime 树：`7e8f199b67027944d646e0c99f5041d4704360377e4d7466fce683c1d468d3ab`。
- build receipt：`26ba248df5c9df30ae1d3954b8e942b1921470139a59ac8b7697a6cb274de5f6`。
- staging 树：`2d72f75ca6a859eea911e246923c94a39e09b722b0920c104cca457e75dba0b9`。
- 启动器 `scripts/dsh_dev.py`：`58c53869a855c0b0a356f9c421ca3e432e9a41274521cbfb5e62421dea70a55d`。
- 工具链 `toolchain.mjs`：`cf2be785baaf0a51633af5479c14d5ded2521919f7ad6adbb29b1cc9a3072008`。

全部改动文件及修前/修后摘要见
[final-source-manifest.json](/tmp/c2p-b02-handoff-fix-d2735bdd/final-source-manifest.json)。证据绑定
本次未提交的工作树和上述构建；后续 H01 实现须重新构建、stage、验收。本轮没有安装或升级
DSH、重装 Python worker、修改日常 home 或提交代码。

## 实现接线

| 文件 | 变化 |
|---|---|
| `integrations/dsh/package.json` | 增加 `stage`、`check:compat`，测试统一交给工具链入口 |
| `integrations/dsh/tsconfig.json` | 类型检查包含 `tests/**/*.ts`，排除构建输出 |
| `dev/toolchain/compat-tests.mjs` | 递归发现开发测试与未来 `tests/**/*.test.ts`；允许单个根目录缺失 |
| `dev/toolchain/toolchain.mjs` | 串联 typecheck→build→stage→test；test 仅验证、不重封损坏 stage；修正 `src/` 输入键并记录 preset/patch；npm/launcher 环境使用白名单 |
| `scripts/dsh_dev.py` | 完整 runtime 校验前置于运行入口；共享 bwrap 参数显式重新挂 runtime 为只读；测试清理环境并使用私有网络与 `--test-concurrency=1`；worker 在 bwrap 内创建/安装；stage 固定初始回执、校验每项字节、激活前重验、失败保留旧安装 |
| `dev/toolchain/staging.test.ts`、`peer-probe.ts` | 在最终安装位置验证 peer 解析和真实 Cordis `Service` 单例；编译探针不随运行包发布 |
| `dev/toolchain/sandbox.test.ts` | 真实验证清理环境、只读源/runtime、可写 run root、私有 loopback 和本地 fixture 通信 |
| `dev/tests/test_development_environment_isolation.py`、`test_toolchain_test_discovery.py` | 固定拒绝路径、worker 安装参数、非 CLI 漂移、并发混代与新测试发现反例 |

运行包只从 `package.json`、`lib/`、`presets/`、`cordis.patch.yml` 收集文件。候选 stage 必须与
开头固定回执的输出/资产逐项相等，不能用 stage 自己的树摘要证明来源。stage 写者以文件锁
串行；构建交错会被拒绝，发布失败可恢复原安装。测试、探针和 QA 期间仍要求一个工具链写者，
不要从另一窗口同时运行 build/stage。

## 修前与修后反例

原始修前输出见 [before.json](/tmp/c2p-b02-handoff-fix-d2735bdd/before.json)、
[before-isolation.json](/tmp/c2p-b02-handoff-fix-d2735bdd/before-isolation.json)、
[测试环境泄漏标记](/tmp/c2p-b02-handoff-fix-d2735bdd/before-test-env-marker.json)。独立 QA 的
混代反例及其源码摘要见
[read_only_findings.json](/tmp/c2p-b02-independent-qa-jzm1uifk/read_only_findings.json)。

| 反例 | 修前实际结果 | 修后实际结果 |
|---|---|---|
| 新 `tests/**/*.test.ts` 主动抛错 | `test:compat` 退出 0，未发现新文件 | 退出 1；7 项中新增项实际执行并失败，标记写入独立 run root |
| 同文件包含 string→number 类型错误 | `typecheck` 退出 0 | npm 退出 1，tsc 退出 2，报告该文件 `TS2322` |
| tests 根目录不存在 | 仅固定开发 glob | 正常发现并执行 6 项开发测试；全部根目录无测试时拒绝通过 |
| `.dsh-dev/runtime` 位于 DEV 可写挂载下 | 实际 sandbox 中目录与 CLI 的 `test -w` 均退出 0 | 同一 sandbox 参数下 runtime/CLI 的 `test ! -w` 成功，run root 可写 |
| 仅修改非 CLI runtime JS | `/tmp` runtime 的 `read_manifest` 错误接受 | 相同类别 fixture 在启动前报 `runtime bytes drifted` |
| worker 继承安装重定向/加载钩子/凭据 | `PIP_TARGET/PREFIX/CONFIG_FILE`、`PYTHONPATH/PYTHONHOME`、合成 API key/代理均进入 worker 环境 | 捕获 setup 两次 subprocess 参数：均 bwrap，环境无外部重定向/凭据，pip config 为 `/dev/null`，prefix 固定独立 venv，HOME 原样保留 |
| Node 直接继承父进程环境与网络 | 合成 API key、日常 DSH_HOME 均可见 | 真实新增测试中 key、原 DSH_HOME、PYTHONPATH 均不可见；独立 loopback 可互通，只有 `lo` 接口 |
| stage 复制 A 后交错构建 B | QA 验证错误接受 A/B 混合文件 | 确定性 fixture 报 `build changed during staging`；之前 stage 和 staging receipt 字节均保留 |

以上对真实 frozen runtime 的测试仅检查写权限与摘要，没有尝试修改其字节。worker setup 的
安装参数/环境测试使用捕获 subprocess 的夹具，未真实执行安装；现有 worker 用 doctor 实际
检查 lock、venv prefix 和 `code2paper` 导入。新增测试探针仅清理本轮独占创建的文件/目录。

## 最小完整命令与本轮结果

在已有冻结 runtime 和已安装锁定工具链的仓库根目录执行：

```bash
npm --prefix integrations/dsh run check:compat
```

该命令依次执行 typecheck→build→stage→test。也可按同一顺序单独调用；正常重建不要求保留
旧输出。`npm --prefix integrations/dsh run test:compat` 本身不改构建与 staging，漂移须先
修正输入并重新 build/stage。

本机外层工具沙箱曾拒绝 bwrap 创建 NETLINK_ROUTE socket，完整 check 当时退出 1，见
[受限上下文输出](/tmp/c2p-b02-handoff-fix-d2735bdd/after-isolation-check-compat.log)。随后工具的
外层隔离操作放行获准，同一 bwrap/私有网络参数下完成下表验证，没有移除隔离或引入 fallback。

完整命令数组、退出码、耗时、日志地址见
[final-results.json](/tmp/c2p-b02-handoff-fix-d2735bdd/final-results.json)；本轮驱动脚本为
[final_verify.py](/tmp/c2p-b02-handoff-fix-d2735bdd/final_verify.py)。

| 命令 | 退出码与可观察行为 |
|---|---|
| `npm --prefix integrations/dsh run check:compat` | 0；类型/构建/stage/6 项 Node 测试通过 |
| `npm --prefix integrations/dsh run test:compat`（临时失败探针） | 1；真实执行新文件后失败，合成环境标记未继承 |
| `npm --prefix integrations/dsh run typecheck`（临时类型探针） | 1；包含 `TS2322` |
| `npm --prefix integrations/dsh run test:compat`（探针清理后） | 0；6 项通过 |
| `python -m pytest -q integrations/dsh/dev/tests/test_development_environment_isolation.py integrations/dsh/dev/tests/test_toolchain_test_discovery.py` | 0；22 项通过 |
| `npm --cache .dsh-dev/cache/npm --userconfig .dsh-dev/config/npmrc pack ./integrations/dsh --dry-run --ignore-scripts --json` | 0；仅 package.json 与 lib/build-receipt.json，`bundled: []`，没有 dev/tests/node_modules |
| `python scripts/dsh_dev.py doctor` | 0；完整 runtime 树未变、原安装 lock/CLI 匹配、无共享 inode、runtime/日常 home/仓库只读、run root 可写、worker 正常 |
| `python scripts/dsh_dev_smoke.py` | 0；零模型请求，首页及 4 项 JS/CSS HTTP 200，随机端口 45513 已关闭 |
| `git diff --check` | 0 |

另外，在 `/tmp` 的独立 package 副本加入 `src/index.ts`、patch 和 preset，使用已安装的
TypeScript 真正 build，再调用实际 staging/校验函数；未安装依赖或启动 DSH。
[src-build-fixture.json](/tmp/c2p-b02-handoff-fix-d2735bdd/src-build-fixture.json) 记录
`src_inputs` 的 `src/index.ts` 键与 6 个运行文件，entry/patch/src 均为 true。该夹具补充验证
未来有源码分支，不能代替 H01 真 bundle 验收。

最终 doctor 和 smoke 分别见
[final-doctor.json](/tmp/c2p-b02-handoff-fix-d2735bdd/final-doctor.json)、
[final-web-smoke.json](/tmp/c2p-b02-handoff-fix-d2735bdd/final-web-smoke.json)。smoke 只启动并停止
自己的随机端口实例，认证信息只在内存，归档日志已去除 URL。旧报告引用的 smoke 文件在本轮
归档后按原字节恢复，见
[historical-smoke-preserved.json](/tmp/c2p-b02-handoff-fix-d2735bdd/historical-smoke-preserved.json)。

剩余验收由独立 QA 针对同一最终源码与产物复核；本报告记录实现者结果，不提前宣布 QA 放行。
