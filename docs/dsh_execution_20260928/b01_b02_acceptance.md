# B01/B02 独立验收与下一步交接

> 2026-09-28。LEAD 负责最终裁决。代码对照基线 `0918ee76d079b9392ec03400c0c4c9fdff5bc784`，HEAD `d48b4e4b22c94c82b45d2179ba452d72b164102d`；以下结果绑定当前未提交的任务文件及各证据中的摘要，不是旧 4014 回执的扩展。

## 1. 裁决与放行范围

| 单元/门 | 裁决 | 范围 |
|---|---|---|
| B01 | PASS | 原编译器/Writer 局部门夹具，以及真实 Formalizer 完成后的公式正例；未证明全局 Verified 或 DSH 接入 |
| B02 | PASS | 七项工具链、隔离及 staging 复核问题已关闭；独立 QA 通过 |
| Gate-B | PASS | B00/B01/B02 均完成；只放行离线兼容性实施 |
| H01 | ready | 由 ENV/DSH 窗口按第 01 部分 H01 卡执行；本轮尚未启动 |
| H04 | 未开工 | 先 H01→H02，经真实接口冻结后与 H03 并行 |

B01 首轮 QA 发现缺少 Formalizer 完成事实；B02 首轮 QA 发现工具链接线与隔离缺口。负责人安排原任务 owner 修复并重新验收，没有在此轮启动生产 K/C/R 实现。

## 2. B01 的补齐和独立验证

初始 39 项测试可重复通过，真实 compiler/request builder/parser/assessor/Binder 确有调用。但公式义务存在而 `formula_packages=()`，不能证明任务卡要求的已完成 Formalizer 输入。

补齐在 `tests/integrations/dsh/fixtures/` 原责任域内实施：新增合成源码及完整来源绑定，调用原 `execute_formalizer_invocation_plan`，保留默认 V2 parser 与 `validate_mechanism_formula_package`，由原 owner 产生非空 accepted 包和 complete receipt。经原 adapter、workset、Writer builder、公式 splice 与 Binder 后，局部 `formula_exact_body_count=1`、`formula_consumed_count=1`，非法字段/缺失义务/错误运算符均在 Writer 前拒绝。旧无公式正例、作者 header 无 atom 页和空白名单反例保留。

Golden 中的 receipt 是明确删去时钟字段的稳定观测投影，没有重新封印为真实回执；后继 C02 应使用生成器保存的完整 execution/receipt 或重新生成的真实结果，不得据观测投影批准生产发送。

| 执行者 | 验证 | 实际结果与证据 |
|---|---|---|
| 初审 QA | 原 39 项及独立 hash-seed 探针 | 39 passed；D1 独立复现；`/tmp/c2p-dsh-b01-independent-qa-20260928-nmyskmf1/verification.json` |
| 修复 owner | 新增 Formalizer 正反例，修前/修后 | 修前 4 failed，补齐后 43 passed；相邻 4 套 84 passed；`/tmp/c2p-dsh-b01-fixture-repair-20260928-_viipk9a/` 的 before/after-commands 与日志 |
| LEAD 独立验收 | `python -m pytest -q -p no:cacheprovider --basetemp /tmp/c2p-dsh-lead-acceptance-20260928-ks_qwck5/b01-pytest tests/integrations/dsh/test_legacy_characterization.py` | exit 0，43 passed in 5.58s；`/tmp/c2p-dsh-lead-acceptance-20260928-ks_qwck5/b01-independent.json` 绑定前后相同输入摘要和完整 argv；同目录 `b01-pytest.log` |

该 PASS 仅覆盖 AT-B01。Candidate/Verified 全局状态仍按真实产品门记录为未验证。

## 3. B02 首轮问题及负责范围

| 编号 | 已确认问题 | 修复 owner |
|---|---|---|
| R1 | `tests/**/*.test.ts` 没有被测试入口与 TypeScript include 覆盖 | ENV：package/tsconfig/toolchain |
| R2 | build→stage→test 顺序未形成可靠入口；stage 包含 dev/test；src input 键约定不同 | ENV：toolchain/staging |
| R3 | 整个开发根可写，导致其中 frozen runtime 也可写 | ENV：统一 sandbox argv 与实际写边界探针 |
| R4 | 启动仅检查 lock/CLI，其他 runtime JS 漂移仍可启动 | ENV：启动前完整运行树校验 |
| R5 | worker 继承 PIP/PYTHON/凭据等环境，可重定向安装 | ENV：白名单环境和隔离安装 |
| R6 | Node 兼容测试绕过 launcher 沙箱，并继承父环境 | ENV：隔离且断网的测试入口，默认串行 |
| R7 | stage/build 交错可以生成混代包，并被现有校验接受 | ENV：绑定固定 build receipt、逐项匹配 staged 字节并拒绝竞争 |

独立初审证据：`/tmp/c2p-b02-independent-qa-jzm1uifk/read_only_findings.json`。runtime 可写性只用实际 sandbox 内的 `test -w` 检查；漂移、pip 环境和交错探针在临时夹具中复现，没有改动冻结 runtime 或日常安装。

LEAD 已在根 `.gitignore` 增加 `integrations/dsh/node_modules/`、`integrations/dsh/lib/`、`integrations/dsh/dev/toolchain/build/`，并验证 lock、源码及测试可纳入 Git。未提交任何文件。

修复和实现者证据见 [B02 追加报告](../../integrations/dsh/dev/toolchain/B02_handoff_fix_evidence.md)，原交付报告保留。独立 QA 的最终记录为 `/tmp/c2p-dsh-b02-independent-final-20260928-g53ve4_j/verification.json`，含完整 argv、日志及摘要；裁决 **PASS**。19 项受测源码及文件集合前后不变，独立重建后的生成物摘要一致。

| 独立 QA 执行 | 结果与行为 |
|---|---|
| `python -B -m pytest -q -p no:cacheprovider integrations/dsh/dev/tests/test_development_environment_isolation.py integrations/dsh/dev/tests/test_toolchain_test_discovery.py` | exit 0；22 passed |
| `npm --prefix integrations/dsh run toolchain:verify` | exit 0；锁定工具链和外部 peer 解析有效 |
| `npm --prefix integrations/dsh run check:compat` | exit 0；typecheck→build→stage→6 项 Node 测试；注入的合成凭据、其他 DSH_HOME 和加载路径未继承，保留 bubblewrap 私有网络 |
| `python -B scripts/dsh_dev.py doctor` | exit 0；runtime 摘要保持 `7e8f199b…8d3ab`；日常 home/安装、业务树和冻结 runtime 隔离条件满足，run root 可写，现有 worker 正常 |
| QA `/tmp` 独立 staging 探针 | exit 0；A/B 多文件混代拒绝、stage 自哈希一致但不匹配 build 拒绝、receipt 发布失败恢复旧 stage/receipt 并清理候选 |
| `git diff --check` | exit 0 |

QA 同时核对实现者的同源 Web smoke：`/tmp/c2p-b02-handoff-fix-d2735bdd/final-web-smoke.json`，首页及 4 个资源成功、随机端口已释放、`model_turns_submitted=0`；没有重复启动服务。测试发现和类型覆盖另用真实临时反例验证：未来 `tests/**/*.test.ts` 中主动失败的测试确实执行并使命令退出 1，类型错误产生 TS2322；移除本轮探针后恢复通过。临时独立 package 含 `src/index.ts` 时真实 build/stage 成功，验证源码键约定；它不冒充 H01 实现。

worker 安装修改通过 subprocess 参数/环境捕获及真实 sandbox 边界验证；本轮未重装依赖，现有 worker 的 lock、prefix、导入由 doctor 实际核验。没有运行 H01–H04、真实模型或 live。

下一窗口使用统一命令 `npm --prefix integrations/dsh run check:compat`。独立 `test:compat` 保留漂移拒绝，不自动重建/stage；多窗口编写 H03/H04 时，构建和验收窗口仍由一个执行者控制。

## 4. 后继责任和接口

- **B01-D1 → K04，阻断 Gate-K。** 修原 `unified_context_compiler.py` 的 set 保序缺陷；跨进程/多 hash seed、非字典序多段落和紧预算分裂均须守恒。届时将 D1 特征断言改为稳定性回归；固定 seed 不算修复。
- **B01-G1 → K04。** 缺失 actual technical digest 与真实技术字节复核收敛到原公共 owner；更新当前 characterization，不保留“绕过才通过”的测试。
- **B01-G2 → C02。** 当前 detail-only/空 target 样例只证明窄场景；C02 补显式非空 atom/target 的正反例，技术页闭合与作者 header 合法无 atom 分别验证。
- **H02 → H03/H04。** [交接要求](h02_h04_handoff.md) 规定实际导出、mock claim/request recorder、资源与取消语义，由 H02 写 `h02_interface_freeze.md` 后经 LEAD/QA 冻结。H04 不等待后继 C/R 生产 RPC；生产持久性在 R01–R03 复验。

B00 的 `compatibility.json` 与 `source_inventory.json.b00_freeze` 保持历史观测；其中 `bundle_build_digest=null` 不回填。当前开发 build/toolchain/staging 身份与 I01 未来正式 composition 分开记录。H01 入口未实施时 `compat_composition_ready=false` 合理，不能据此伪造通过 Gate-H。

最终状态：49 项中 B00/B01/B02 三项 done、H01 一项 ready、其余 45 项 planned。负责人复核任务卡/台账、依赖无环、链接、忽略规则以及基线旧业务文件；结果见 `/tmp/c2p-dsh-lead-acceptance-20260928-ks_qwck5/handoff-validation.json`。未修改 `src/` 的生产代码，未重新生成准入回执，未提交或推送。

[返回执行入口](README.md)
