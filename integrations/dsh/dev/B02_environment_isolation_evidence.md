# B02 · 扩展隔离环境与独立构建工具链（证据与交接）

> **后续变更（2026-09-28，H01）**：`integrations/dsh/package.json` 与 `package-lock.json` 因新增
> `@deepseek-ai/schemastery` peer 而改变，本报告 §1 中这两个文件的摘要已被取代；工具链已按新 lock
> 重装。见 [H01 交接记录](H01_loader_evidence.md) §5。其余内容与结论不变。

> 2026-09-28 实际执行记录。任务卡见 [01 执行文档](../../../docs/dsh_execution_20260928/01_baseline_and_dsh_compatibility.md)；
> 状态以 [台账](../../../docs/dsh_execution_20260928/task_board.json) 为准。本文件只登记本单元实际观测到的结果。

| 项 | 值 |
|---|---|
| 任务 / 验收 | B02 / AT-B02（planned_test：`development_environment_isolation`） |
| owner / reviewer | ENV / QA（本记录由 ENV 提交，等待独立复核） |
| 前置 | B00（done，独立 QA 通过） |
| 授权 | offline_implementation；未启动真实模型、未做 live 准入 |
| 输入身份 | 仓库 HEAD `d48b4e4b22c94c82b45d2179ba452d72b164102d`（dirty 树保留，未 commit/reset）；冻结 runtime `0.1.5-rc.3`，树摘要 `7e8f199b…8d3ab`；lock `1695fdb6…7d76d`；Node `v25.8.2` |
| 组成身份 | 开发期由 `.dsh-dev/manifest.json`、`.dsh-dev/toolchain.json`、`.dsh-dev/staging.json`、`integrations/dsh/lib/build-receipt.json` 分别记录 runtime / 工具链 / staging / bundle 构建身份；I01 尚未把这些并入正式 composition |

## 1. 改动范围（仅任务卡 owned paths）

| 文件 | 状态 | 内容 |
|---|---|---|
| `scripts/dsh_dev.py` | 修改 | 固定组成白名单与 profile 校验、可写 run root、工具链/staging/构建回执校验、Python worker 环境、`doctor --evidence`、`stage`、`compat`、环境变量卫生断言 |
| `scripts/dsh_dev_smoke.py` | 修改 | 增加 `--composition`（web/compat）与按组成命名证据；默认行为不变 |
| `integrations/dsh/dev/README.md` | 修改 | 记录工具链、组成白名单、staging、worker、命令与验证范围 |
| `integrations/dsh/dev/pyworker-requirements.lock` | 新增 | worker 依赖的哈希锁定（`--require-hashes`） |
| `integrations/dsh/dev/toolchain/toolchain.mjs` | 新增 | 独立工具链驱动：`install`/`verify`/`typecheck`/`build`，写 `lib/build-receipt.json` |
| `integrations/dsh/dev/toolchain/peer-probe.ts` | 新增 | 开发探针：真实 `import` Cordis + 类型面校验，用于 staging 解析验证 |
| `integrations/dsh/dev/toolchain/staging.test.ts` | 新增 | Node 内置测试：最终 staging 安装位置的 peer 解析与 runtime 未被写入 |
| `integrations/dsh/dev/toolchain/tsconfig.build.json` / `tsconfig.probe.json` | 新增 | 构建与探针的 tsc 项目 |
| `integrations/dsh/dev/tests/test_development_environment_isolation.py` | 新增 | AT-B02 反例测试（组成/端口/环境变量/bwrap/漂移/compat 门） |
| `integrations/dsh/package.json` | 新增 | bundle 清单 + 工具链 devDependencies；DSH/Cordis 仅 peer |
| `integrations/dsh/package-lock.json` | 新增 | `typescript@5.9.3`、`@types/node@25.9.3`、`undici-types@7.24.6`（`--legacy-peer-deps`） |
| `integrations/dsh/tsconfig.json` | 新增 | 严格 `nodenext` + `erasableSyntaxOnly` 的类型检查项目 |

未改动：冻结 runtime、日常 `/home/cuihengjia/.dsh`、日常 npm 安装、仓库 `.gitignore`、任何他人 owned 路径
（`integrations/dsh/src/`、`presets/`、`cordis.patch.yml`、`tests/loader.test.ts` 等留给 H01）。

文件摘要（SHA-256，本次提交状态）：

```text
adaf380f744b7f41c10877577a9025805e7a2b2aa7be3b29d12210e1478fd766  scripts/dsh_dev.py
5c4126d5567b5f02e6bff06c76d57472d9e3313775debc5cc867db297bf9e5bc  scripts/dsh_dev_smoke.py
38c483e58ae83fd79f90448efbbf27bb5144da4c312c9b89dbfe4e0c34b1b10e  integrations/dsh/package.json
abb78e4365c5defc1ebf65a6877664712ffc64fe2a2a9ac5336713af669103c1  integrations/dsh/package-lock.json
f2770d85525138d175d8878a301bf0c4459c48f7c352efab1e57450cd6af7de8  integrations/dsh/tsconfig.json
33d4f1c5271e91a5b639f5946a1952637090af70887e5cb1b81778bcfd2a5eed  integrations/dsh/dev/toolchain/toolchain.mjs
bd921e1dd5b8dbd9c5313ed7e4065abe91234dac5975c19e60b98fc0b9c77cb6  integrations/dsh/dev/toolchain/peer-probe.ts
c1cd68cc2717378df7be454c34e97da4ba3ed14ed56ce0c5880ec01f8aa0eef5  integrations/dsh/dev/toolchain/staging.test.ts
5f64dd3944e4a3e1cc209335c065d722b8120ab47d17d3cae853f5afa656e9ed  integrations/dsh/dev/tests/test_development_environment_isolation.py
acaa6c3a04cab9bb3f30f9f1bafcfb3567cb0aefe526cdcf437b148c95d5ffdb  integrations/dsh/dev/pyworker-requirements.lock
546f20de4a866bf16ab868697c94b40752a450c29f2bd4a8957c9ac83b6eb709  integrations/dsh/dev/README.md
```

## 2. AT-B02 逐条对照

| 验收条款 | 实际观测 | 证据位置 |
|---|---|---|
| 可重复 build/typecheck | `typecheck` exit 0；`build` 连续两次得到同一 `outputs_digest=192eecee…6181`；带 `src/**/*.ts` 时同样两次一致（`ef9a830f…e1a2`，临时探针文件已删除，未触碰 H01 路径） | §3 命令 1–3 |
| 正常 Web 入口仍工作 | 真实启动、首页 HTTP 200（27,724 bytes）、4 个静态资源 200、模型提交 0、关闭后端口释放 | `.dsh-dev/evidence/web-smoke.json` |
| 日常 home/安装只读 | bwrap 内 `test ! -w ~/.dsh`、`test ! -w <repo>`、`test -w .dsh-dev/run` 均通过；原安装 lock/CLI 摘要与冻结值一致；runtime 与原安装无共享 inode | `doctor` 的 `isolation`/`original_installation` |
| HOME 不重设 | `child_env` 断言 `HOME` 与父进程相同；测试注入 `DSH_HOME=/home/someone/.dsh` 后子环境仍指向 `.dsh-dev/home` | `test_api_keys_proxies_and_other_harness_env_are_not_inherited` |
| 无全局安装/原 runtime 覆盖 | 工具链由 `npm ci --legacy-peer-deps --ignore-scripts` 装在 `integrations/dsh/node_modules`，npm cache 指向 `.dsh-dev/cache/npm`、`npm_config_global=false`；runtime 全树摘要仍为 `7e8f199b…8d3ab`，其中不存在 `typescript` | `toolchain:verify`、`doctor`、`staging.test.ts` |
| 错误组成拒绝 | profile bundle 列表必须与白名单逐项相等；多一项、少一项、顺序变化、未知组成名均报错 | `test_only_whitelisted_compositions_are_accepted` |
| bundle 漂移拒绝 | staging 字节漂移、staging 后重建、源码/配置在构建后变化、`lib/` 出现回执外文件均拒绝 | `test_bundle_drift_is_refused`、`test_rebuild_after_staging_is_refused` |
| API key 继承拒绝 | `DEEPSEEK_API_KEY`/`OPENAI_API_KEY`/`ANTHROPIC_AUTH_TOKEN`/`HTTPS_PROXY`/`NODE_OPTIONS`/`NODE_PATH`/`PYTHONPATH`/其他实例 `DSH_*` 均不进入子环境 | 同上测试 |
| 保留端口拒绝 | `3080`、`19387`、`8006` 在启动前拒绝；`0/3081/3082/65535` 通过；越界拒绝 | `test_reserved_ports_are_refused`（见 §3 命令 4 的 CLI 实测） |
| 无 bubblewrap 拒绝 | `shutil.which("bwrap")` 为空时 `require_bwrap`/`read_manifest` 均失败，无普通启动回退 | `test_bubblewrap_is_required` |
| 独立锁定 TS 工具链 | `package-lock.json` 锁定 3 个包；工具链身份写入 `.dsh-dev/toolchain.json`（含 `node_modules` 树摘要），`toolchain:verify` 复核 | §3 命令 1 |
| Node 内置测试入口 | `test:compat` = `node --test dev/toolchain/*.test.ts`（Node 原生类型擦除，无 vitest/tsx） | §3 命令 4 |
| Python worker 环境 | `.dsh-dev/pyworker` 独立 venv，6 个包按哈希锁定，`pip freeze` 与 lock 全等，`import code2paper` 成功；日常 conda 环境未被写入；lock 被篡改时拒绝 | `doctor` 的 `pyworker`、`test_python_worker_environment_matches_its_lock`、`test_python_worker_drift_is_refused` |
| DSH/Cordis 作外部 peer + 最终 staging 解析 | 5 个 peer 在 `integrations/dsh/package.json` 声明；`integrations/dsh/node_modules/@deepseek-ai` 为指向冻结 runtime 的符号链接（非 vendored 副本）；从 `.dsh-dev/home/profiles/node_modules/@code2paper/dsh-bundle` 解析全部 peer 均落在冻结 runtime，并从该位置真实 `import` Cordis 成功 | `staging.test.ts` 4 项 |
| 明确可写 run root | `.dsh-dev/run/`，子进程收到 `C2P_DSH_RUN_ROOT`；bwrap 内实测可写 | `doctor` 的 `isolation.run_root_writable` |
| 冻结 runtime 不装开发依赖 | 见上；`@types/node@26.6.3`/`undici-types` 属 DSH 自身依赖树，测试断言其字节与日常安装完全一致 | `staging.test.ts` 第 4 项 |

## 3. 实际命令与退出码

在仓库根目录、当前 dirty 树执行（原始输出保存在 `.dsh-dev/evidence/`）：

| # | 命令 | 退出码 | 关键结果 |
|---|---|---|---|
| 1 | `npm --prefix integrations/dsh run toolchain:verify` | 0 | TypeScript 5.9.3 / @types/node 25.9.3 / Node v25.8.2；`node_modules` 271 文件，树摘要 `d4d6ee6c…5bfe`；peer 链接指向冻结 runtime |
| 2 | `npm --prefix integrations/dsh run typecheck` | 0 | `tsc -p integrations/dsh/tsconfig.json`，无诊断 |
| 3 | `npm --prefix integrations/dsh run build` | 0 | `src_present=false entry_present=false outputs=1 outputs_digest=192eecee46d422a7d5dbf9276b910c02174e28e2cd95151504c75d6d65556181` |
| 4 | `npm --prefix integrations/dsh run test:compat` | 0 | 4 tests / 4 pass（staging 存在、peer 解析、staging 内 Cordis 运行时导入、runtime 未被写入） |
| 5 | `python -m pytest -q integrations/dsh/dev/tests/test_development_environment_isolation.py` | 0 | 12 passed |
| 6 | `python scripts/dsh_dev.py stage` | 0 | 16 个文件落到 `…/profiles/node_modules/@code2paper/dsh-bundle`，`entry_present=false patch_present=false` |
| 7 | `python scripts/dsh_dev.py doctor --evidence` | 0 | 全部分区通过；`compat_composition_ready=false`（H01 入口未实现，符合预期） |
| 8 | `python scripts/dsh_dev_smoke.py` | 0 | `passed=true`、HTTP 200、4 资源 200、`model_turns_submitted=0`、端口已释放 |
| 9 | `python -m pytest -q tests/regression_20260917/test_execution_identity.py` | 0 | 24 passed（执行文档列出的既有节点，未受本单元影响） |
| 10 | `git diff --check` | 0 | 无空白/冲突标记 |

拒绝路径实测（均非零退出，且在启动 DSH 之前失败）：

```text
python scripts/dsh_dev.py compat          -> dsh-dev: the staged bundle has no lib/index.js; …(H01 deliverable)
python scripts/dsh_dev.py config --composition compat -> 同上
python scripts/dsh_dev.py web --port 3080 -> dsh-dev: port 3080 is reserved for the everyday instances (3080, 19387, 8006)
python scripts/dsh_dev.py web --port 8006 -> 同上
```

## 4. 产物引用

| 产物 | 摘要 |
|---|---|
| `.dsh-dev/evidence/development-environment-isolation.json` | `6ee576ef24812982283b998a2c54b2e8fe4c9ae7df686de3f6e91bc2db83e707` |
| `.dsh-dev/evidence/web-smoke.json` | `e7673e99fe6f79c1ebcbeef86e074ad70ecafe340abc3d950c3508cdb9fa2b5e` |
| `.dsh-dev/evidence/web-smoke.redacted.log` | `2c93b40a9efa87c0203369e16b48794d6c4bb9d59db8aedabcab3473bc64ee95`（URL 已脱敏） |
| `integrations/dsh/lib/build-receipt.json` | `72c20ed026e5a69e2d9140f7eddb0aa4b05ec434d67530dd20af37510f69aa89` |
| `.dsh-dev/toolchain.json`、`.dsh-dev/staging.json` | 工具链与 staging 身份；内容随重建更新，不纳入 Git |

## 5. 未测项、限制与移交事项

1. **compat 组成尚不可启动**：`lib/index.js`、`cordis.patch.yml`、`presets/`、`src/index.ts` 属 H01；
   本单元只保证“入口存在且未被漂移时才能启动”，没有宣称 Loader/preset 兼容已通过。
2. **未做真实模型、terminal、取消实验**：属 H03/H04；本阶段 smoke 只发静态资源请求，
   `model_turns_submitted=0`。
3. **未纳入 composition 正式身份**：工具链/staging/构建回执是开发期身份，I01 负责并入正式
   composition；`integrations/dsh/compatibility.json` 仍记录 `bundle_build_digest: null`，
   其更新属 LEAD/I01 范围。
4. **仓库卫生待 LEAD 决定**：`integrations/dsh/node_modules/`（26 MB，工具链）与
   `integrations/dsh/lib/`（构建产物）是生成物，位于当前未被跟踪的 `integrations/` 下。
   本单元未改根 `.gitignore`（不在 owned paths）；建议在提交 `integrations/` 前加入忽略规则，
   或改为把工具链装到 `.dsh-dev/` 下。
5. **未复核原安装全树**：`doctor` 对日常安装只比对 lock/CLI 摘要与硬链接（B00 已做过全树冻结）；
   runtime 侧仍是全树逐文件摘要。
6. **依赖网络**：`toolchain:install` 与 `pyworker-setup`（首次）需要访问 npm/PyPI；离线机器需
   预热 `.dsh-dev/cache/npm`、`.dsh-dev/cache/pip`。已安装状态下的 `typecheck`/`build`/
   `test:compat`/`doctor` 不需要网络。
7. **QA 复核建议**：独立重跑 §3 的 1–8，重点核对 `doctor` 的 `isolation`/`original_installation`/
   `toolchain` 分区，并故意破坏一个 staging 字节确认 `doctor` 拒绝（`test_bundle_drift_is_refused`
   已在临时目录覆盖该逻辑，未改动真实 dev root）。
