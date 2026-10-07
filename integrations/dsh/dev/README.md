# Code2Paper 的隔离 DSH 开发环境

本目录记录 2026-09-27 建立、2026-09-28 按 **B02** 扩展、同日按 **H01** 接入本地 bundle 的隔离
开发环境。用户要求以本机已有 DSH 为基础开发并保留日常实例。运行环境、独立 TypeScript 工具链、
固定 compat 组成白名单、bundle staging、Python worker 环境与真实 Loader/preset 组成均已就绪；
child 首请求绑定（H02）、terminal 与原始来源（H03）尚未实施，本阶段没有宣称 Gate-H 已通过。

## 实际版本

- 来源：本机 `/home/cuihengjia/.npm/_npx/1e7f6d9597241db0` 的已安装 npm 树。
- DSH：`0.1.5-rc.3`；231 个 `dsh*` 包均为该版本。Node：`v25.8.2`。
- 已复制整个 npm 依赖树及 lock，共 25,478 个文件/链接，约 306 MB；没有执行 npm 更新或下载。
- 这是已构建软件的独立副本，包含 JS、类型声明与各包文档；不是完整上游 Git checkout。
  本机包没有提供已核实的源码 commit，因此记录 `upstream_commit: null`。
- npm lock SHA-256：`1695fdb6e095d9d6af4210d30aa5c061c093ed8be7365913a61af9fa8027d76d`。
- 运行树 SHA-256：`7e8f199b67027944d646e0c99f5041d4704360377e4d7466fce683c1d468d3ab`。
  算法为 [启动器](../../../scripts/dsh_dev.py) 的 `inventory` / `tree_digest`，包括逐文件 SHA-256 和相对链接目标。
- 开发工具链：TypeScript `5.9.3`、`@types/node` `25.9.3`（由 `integrations/dsh/package-lock.json` 锁定）。
- Python worker：CPython `3.13.9`，依赖由 [pyworker-requirements.lock](pyworker-requirements.lock) 按哈希锁定。

设计中的 `c36a83ff / 0.1.7-alpha.1` 保留为源码研究参考。后续 WP2 必须针对这里的
`0.1.5-rc.3` 实际运行合同验证；不能把参考版本的接口结论直接视为已验证。需要上游源码调试
时，再定位与实际 npm 包对应的源码；不得直接升级日常安装来对齐设计。

## 目录与隔离

下表的开发路径均位于仓库根目录下；整个 `.dsh-dev/` 已被 Git 忽略。

| 用途 | 日常 DSH | Code2Paper 开发实例 |
|---|---|---|
| 运行包 | 原 npm 缓存安装 | `.dsh-dev/runtime/`，独立复制，无共享硬链接 |
| Harness home | `/home/cuihengjia/.dsh` | `.dsh-dev/home/` |
| profile | 现有 `web` 及本地插件 | `code2paper-dev`（web）、`code2paper-dev-compat`（compat） |
| 工作目录 | 原来的项目目录 | `.dsh-dev/workspace/` |
| 可写 run root | 无 | `.dsh-dev/run/`，并以 `C2P_DSH_RUN_ROOT` 传给子进程 |
| 缓存、临时文件 | 原位置 | `.dsh-dev/cache/`、`.dsh-dev/tmp/` |
| TypeScript 工具链 | 无 | `integrations/dsh/node_modules/`（由 lock 安装，见下） |
| Python worker | 日常 conda 解释器 | `.dsh-dev/pyworker/`（独立 venv） |
| Web | 原入口 | `127.0.0.1:3081`（web）/ `3082`（compat）；测试使用随机空闲端口 |

启动器使用 `bubblewrap`：根文件系统只读，`.dsh-dev/` 可写挂载之后再将其中的 `runtime/`
显式重新挂为只读；开发 run root、私有 `/tmp` 和必要的虚拟设备/进程文件系统可写。原 DSH
安装、原 home、冻结 runtime 和 Code2Paper 业务代码均不在开发进程的可写范围内。缺少
`bwrap` 或隔离失败时直接停止，不退回普通启动。`web`、`config`、smoke 与测试入口在执行
子进程前都核对完整 runtime 文件/链接树，非 CLI 文件漂移也会拒绝。

Node 使用现有可执行文件，只读调用且每次检查版本；不修改全局 Node/npm/pnpm、shell 配置、
systemd 服务或默认启动命令。插件源码在仓库中编辑，DSH 进程读取它们进行加载。

没有复制日常 settings、凭据、会话或本地插件。启动时只继承少量基础环境变量，显式设置独立
`DSH_HOME`，不继承 API key、代理、`NODE_OPTIONS`、`NODE_PATH` 或其他实例的 `DSH_*`。
`HOME` 本身保持原值。工作目录选在独立空目录，避免自动加载 Code2Paper 的 `.env`。

[offline.patch.yml](offline.patch.yml) 在其他配置之后关闭标准模型适配器、模型重试、
模型标题、遥测、Web 搜索/抓取和远端插件目录。因此这套环境当前用于加载与界面检查，尚不能
发起真实写作。并发调度尚未接入，后续按设计默认串行；本次没有添加一个无实际作用的并发开关。

## 固定组成白名单

启动器只接受两条显式组成（`scripts/dsh_dev.py` 的 `COMPOSITIONS`），profile 里的 bundle 列表
必须与白名单**逐项相等**（顺序也一致），否则拒绝启动：

| 组成 | profile | bundle 行 |
|---|---|---|
| `web` | `code2paper-dev` | `@deepseek-ai/dsh-base`、`@deepseek-ai/dsh-web-app` |
| `compat` | `code2paper-dev-compat` | 上述两项 + `@code2paper/dsh-bundle` |

未知组成名、多一项/少一项、顺序变化都报错。`compat` 另外要求 staging 目录里存在真实的
`lib/index.js` 与 `cordis.patch.yml`，否则 `compat`、`config --composition compat` 与 compat
smoke 会在启动前明确失败，而不是把坏组成交给 Loader。

## Code2Paper bundle（H01）

`integrations/dsh/` 现在是一个可被真实 0.1.5-rc.3 Loader 加载的 bundle，分两个平面：

| 文件 | 平面 | 内容 |
|---|---|---|
| `src/index.ts` → `lib/index.js` | Host | `code2paperBridge` 服务；`mountCode2PaperPreset(caller, agentCtx, presetId?)`（root 创建，在 `setup` 中 await）与 `applyChildComposition(caller, agentCtx, parentCtx)`（child 创建，同步绑定父的同一 standing generation） |
| `src/task-tools.ts` → `lib/task-tools.js` | preset | `code2paper-tools` 行，注册模型可见的 `c2p_bridge_probe`（H01 组成探针，不是 C01/C03 领域工具） |
| `cordis.patch.yml` | bundle patch | `insert` 本 bundle 的 Host 行（`config: {presetId, presetRoot, runRoot}`），并**整行替换** web-app 插入的 `agent-presets` 行 config：`default: code2paper`、唯一 root 指向本 bundle 的 `presets/`、关闭 shipped/user root |
| `presets/code2paper/agent.cordis.yml` | preset 组成 | 目录扫描发现的普通插件 entry list；当前只有 tools 行 |

分层与作用域：Host 行发布进程级服务且**不注册任何模型工具**；preset 行挂在 agent scope 上，
只有 join 该 preset 的 agent 能看到 `c2p_bridge_probe`。standing mount 由多个 session 共享，
所以插件内不得保存 per-agent 可变状态——探针按执行 agent 的 session 记账，兄弟 session 与
未 join preset 的 session 互不可见。child 通过 `applyChildComposition` 绑定父的 generation：
父 preset 文件改动后，新 root session 组成新 generation，既有 child 不会漂移。

两个模块都**没有 default export**：0.1.5-rc.3 Loader 的 `unwrapExports` 优先取 `exports.default`，
非 null/undefined 的 default 若没有携带 `name`/`inject`/`Config`，命名导出不会补回这些字段。
`loader.test.ts` 的 default-only 反例具体证明：丢失 inject 后访问该服务会失败；不将其外推为
任意缺少 name/Config 都会自动拒绝。

`npm --prefix integrations/dsh run check:compat`（typecheck→build→stage→test）里的
[loader.test.ts](../../../integrations/dsh/tests/loader.test.ts) 用真实 `boot()` 启动 compat 组成，
验证根/child 组成与工具集合、peer 解析、named exports、缺包/缺 inject/服务泄漏/坏 Config/
default-export 失败路径、兄弟 session 不泄漏与销毁语义。`python scripts/dsh_dev_smoke.py
--composition compat` 另外用真实 CLI 启动同一组成并检查 Web 入口。

H01 首轮提交与独立复核的区别见 [原交付及勘误](H01_loader_evidence.md)。探针 note 状态只用于
验证 session 隔离，不是 Python invocation 账本、claim 或领域回执。后续 H02 必须使用可信
绑定接口，不能把 probe 成功或 `applyChildComposition` 返回 undefined 当作绑定成功。

## 独立 TypeScript 工具链

- [package.json](../../../integrations/dsh/package.json)：bundle 清单（`exports`、`dsh.bundle.patch`）
  与工具链 `devDependencies`；DSH/Cordis 只作为 `peerDependencies` 声明，**不随本包安装**。
- [package-lock.json](../../../integrations/dsh/package-lock.json)：锁定 `typescript`、`@types/node`
  及其传递依赖；用 `--legacy-peer-deps` 生成，peer 不会被解析下载。
- [tsconfig.json](../../../integrations/dsh/tsconfig.json)：严格、`nodenext`、`erasableSyntaxOnly`
  （保证测试可被 Node 原生类型擦除直接运行），检查 `src/**/*.ts`、`tests/**/*.ts` 和
  `dev/toolchain/**/*.ts`，排除构建输出。
- 开发期 peer 解析：`integrations/dsh/node_modules/@deepseek-ai` 是指向
  `.dsh-dev/runtime/node_modules/@deepseek-ai` 的符号链接，与 profile 的做法一致；它不是第二份
  Cordis/DSH，安装脚本会在 `npm ci` 之后重建并校验该链接。
- 工具链身份写入 `.dsh-dev/toolchain.json`（lock 摘要、TypeScript/@types 版本、Node 版本、
  `node_modules` 树摘要、peer 链接目标）；`doctor` 与 `toolchain:verify` 复核该记录，漂移即失败。
- 构建产物 `lib/` 与 `dev/toolchain/build/` 由 tsc 生成；`lib/build-receipt.json` 记录输入/输出
  摘要、Node/TypeScript 版本与冻结 runtime 身份。构建是确定性的：同样输入产生同样的
  `outputs_digest`。源码、preset/patch、配置或已产出字节在构建后被改动，`doctor` 与 `stage` 都会拒绝。

工具链命令（在仓库根目录执行）：

```bash
npm --prefix integrations/dsh run toolchain:install   # npm ci + 重建 peer 链接（需要网络）
npm --prefix integrations/dsh run toolchain:verify
npm --prefix integrations/dsh run check:compat       # typecheck → build → stage → test
```

也可依次执行这四步；源码或构建发生变化后按同一顺序重跑，无需保留旧构建来使测试通过：

```bash
npm --prefix integrations/dsh run typecheck
npm --prefix integrations/dsh run build
npm --prefix integrations/dsh run stage
npm --prefix integrations/dsh run test:compat
```

`build` 在 `src/**/*.ts` 不存在时只构建开发探针并如实记录 `src_present: false`；bundle 入口
`lib/index.js` 由 H01 提供，缺失时 compat 组成保持不可用。

`test:compat` 先只读校验已有 build/stage，再递归发现 `dev/toolchain/**/*.test.ts` 和
`tests/**/*.test.ts`，交给 Node 内置测试器按文件串行执行。`tests/` 尚不存在时仍运行开发测试；
总发现结果为空则拒绝通过。任一测试失败都会返回非零。该命令不自动 build 或 stage，因此
损坏构建或 staging 不会被测试入口重新封印；`stage --check` 也可单独只读检查当前回执。

测试经同一个 Python 启动器执行，使用清理后的 `child_env` 和 `--test-concurrency=1`。
`bubblewrap --unshare-net` 为测试建立只有独立 loopback 的网络空间：测试可监听自己的
本地 HTTP/SSE fixture，无法访问主机的 `8006` 或外网 provider。仓库和 runtime 只读，
`.dsh-dev/run/` 可写。外层沙箱若禁止建立网络命名空间或配置 loopback，命令直接失败，
需要运行工具允许该隔离操作；不能去掉 `bwrap` 或回退到共享网络。

工具链按单一写者执行。测试共享开发 home/profile/staging，因此测试、发现探针和 QA 期间
不要在另一窗口重跑 build/stage；默认按文件串行与生产 Agent 的并发策略是不同边界。

## bundle staging 与漂移检查

`npm --prefix integrations/dsh run stage`（等同 `python scripts/dsh_dev.py stage`）先校验构建回执，
再仅把 `package.json`、`lib/`、`presets/`、`cordis.patch.yml` 复制到
最终安装位置 `.dsh-dev/home/profiles/node_modules/@code2paper/dsh-bundle/`，并把树摘要、
构建回执摘要、`entry_present`/`patch_present` 写入 `.dsh-dev/staging.json`。`doctor`、`compat`
与 `test:compat` 都会重新计算并拒绝以下情况：

- staging 目录字节与 staging 回执不一致（bundle 漂移）；
- staging 之后又重建了 bundle（构建回执摘要变化）；
- 源码、preset/patch 或 tsconfig/package.json 在最近一次构建之后被修改；
- `lib/` 下出现回执之外的额外文件。

stage 固定开头读取的构建回执及各项输入/输出摘要，在同目录的临时候选目录复制并逐文件
核对目标字节，发布前再次验证该构建代次。并发构建造成的变化会被拒绝，失败候选不会成为
可运行安装；此前有效的 staging 保留。stage 之间使用文件锁，不能用复制结果自身的摘要
来证明它来自某一构建代次。

`integrations/dsh/dev/toolchain/staging.test.ts` 另外在**最终 staging 安装位置**验证模块解析：
每个声明的 peer 都必须解析到冻结 runtime，按该安装位置解析出的 Cordis 做真实 `import`，
与开发侧导入得到同一个 `Service`。编译探针保留在开发目录，stage 和 npm 包都不包含
`src/`、`tests/`、`dev/` 或 `node_modules/`，不复制第二份 Cordis。可用以下只读清单检查打包内容：

```bash
npm --cache .dsh-dev/cache/npm --userconfig .dsh-dev/config/npmrc \
  pack ./integrations/dsh --dry-run --ignore-scripts --json
```

## Python worker 环境

`integrations/dsh/dev/pyworker-requirements.lock` 按 `--require-hashes` 锁定 worker 的解释器依赖
（`pydantic`、`PyYAML` 及传递依赖，版本与日常解释器一致）。`python scripts/dsh_dev.py
pyworker-setup` 在 `bubblewrap` 中创建 `.dsh-dev/pyworker` 独立 venv 并从 lock 安装，安装参数
显式指定该 venv 的 `--prefix` 与 `--no-user`。worker 安装与 npm 工具链安装都使用环境变量
白名单，清除外部安装重定向、Python/Node 加载钩子、代理和凭据；pip 配置固定为 `/dev/null`，
`HOME` 保持原值。不向日常 conda 环境安装任何东西，也不把 `code2paper` 装进仓库（检查时
通过受控的 `PYTHONPATH=<repo>/src` 导入）。
`doctor` 复核 `pip freeze` 与 lock 完全一致，并用该解释器真实导入 `code2paper`。

## 使用

前台启动开发界面（在任意目录执行）：

```bash
python '/home/cuihengjia/agent/Code2Paper copy/scripts/dsh_dev.py' web
python '/home/cuihengjia/agent/Code2Paper copy/scripts/dsh_dev.py' compat   # H01 之后可用
```

在终端使用 DSH 打印的本地登录链接打开页面；链接包含临时认证信息，不要提交或粘贴到记录。
`Ctrl-C` 停止本次开发实例。默认端口 `3081`（compat `3082`）；被占用会报错，不会终止其他进程。
需要随机空闲端口时追加 `--port 0`。启动器拒绝 `3080`、`19387` 和模型服务 `8006`。

核对运行树、工具链、staging、worker 与只读边界：

```bash
python '/home/cuihengjia/agent/Code2Paper copy/scripts/dsh_dev.py' doctor --evidence
```

查看配置树，或运行一次自动退出的无模型 Web 检查：

```bash
python '/home/cuihengjia/agent/Code2Paper copy/scripts/dsh_dev.py' config
python '/home/cuihengjia/agent/Code2Paper copy/scripts/dsh_dev_smoke.py' [--composition compat]
```

Smoke 访问真实首页和最多 4 个 JS/CSS 资源，随后关闭自己的实例并检查端口释放。认证 URL 和
cookie 仅留在内存，保存的日志去除 URL。若外层沙箱禁止监听本地端口，需要该工具允许本地监听；
脚本内的文件系统隔离仍保留。

仅在尚未建立 `.dsh-dev/` 的工作副本中执行初始化：

```bash
python '/home/cuihengjia/agent/Code2Paper copy/scripts/dsh_dev.py' setup
```

初始化从原 profile 的模块链接定位现有 npm 安装，不运行 `npx` 或获取 latest。目录存在时拒绝
覆盖。`--from-existing` 可显式指定包含 `package-lock.json` 与 `node_modules` 的现有安装目录。
已存在的 `.dsh-dev/` 不会重跑 setup；`doctor`/`stage`/`web` 会补齐缺失的开发目录与 profile 行，
但不会覆盖已有 profile 的 bundle 列表（列表不在白名单内即报错）。

## 本次验证范围

已实际执行（原始输出见 [B02 证据记录](B02_environment_isolation_evidence.md)）：`toolchain:install`、
`typecheck`、`build`（两次，`outputs_digest` 相同）、`test:compat`、B02 Python 隔离测试、
`doctor --evidence`、真实 Web smoke（首页 + 4 个静态资源 HTTP 200、端口释放）以及各条拒绝路径
（错误组成、bundle 漂移、保留端口、无 bubblewrap、API key 继承、compat 无 bundle 入口）。

上述为原 B02 历史记录，未重写。后续测试发现、类型覆盖、构建/stage 顺序和打包修复另见
[B02 工具链交接修复记录](toolchain/B02_handoff_fix_evidence.md)；该轮使用零模型 Web smoke，
没有提交模型请求，也没有重装 worker 或升级 DSH。

原配置和凭据按摘要核对；原安装按 lock/CLI 摘要与硬链接检查核对，运行树按完整逐文件摘要核对。
日常会话可能由原实例同时更新，不能用“整个原 home 所有文件均不变化”作为通过条件，也不复制或
回滚这些会话。开发进程的只读挂载才是禁止它写入原 home 的边界。

这不是 WP2 Agent/terminal/取消兼容验收、Writer 集成验收、live 准入或产品默认切换。下一步在这套
环境内实现本地 Code2Paper bundle，并按 H01→H02→H03 逐项验证实际版本的扩展接口。
