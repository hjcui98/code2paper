# L01 packet10 同范围整批返修记录（2026-10-05）

> **2026-10-05 最新执行状态：** packet11 一次生成授权已消耗，普通文本 JSON/finish stop、tool_calls0，领域失败保留。文本结束返修及具名原费用恢复经独立代码/方案、实际结果两次 PASS；原费用 spent7596/pending0，canonical backend empty，35旧文件、原task/claim/正文及provider_quiescence null保持不变。实际读集已释放；新完整注册证书及fresh cold待最终冻结运行。Gate-L仍FAIL，24/1/24；新模型请求需fresh packet具体一次授权，不重发旧packet。详见 [文本结束返修证据](stage04_L01_text_stop_repair_evidence_20261005.md)。


执行依据为 `stage04_L01_packet10_repair_and_continuation_20261005.md` §8。本记录是实施和验证证据，不是 Gate-L PASS。项目仍为 24 done / 1 in_progress / 24 planned；C–F 正式实现仍等待各自原前置。

## 冻结、基线和授权

packet10 独立事后 review 为 FAIL，全部实际读集明确释放，原证据 `/tmp/c2p-dsh-independent-packet10-postlive-20261005-01/{review.md,readset-release.json}`。释放后逐项核对六个 doc-sync 输入，再执行 `git apply --check` 和应用补丁，均 exit0。已有 dirty 基线保存于 `/tmp/c2p-dsh-l01-repair-20261005-main-01/baseline.json` 及 baseline/；未 reset、clean、切分支、commit 或合并。

原 live10 句柄97648在当前宿主已不可用，原 `/tmp/c2p-dsh-l01-live10-20261005.log` 记录 exit1，外部主执行索引已修正，不重启原命令。原 packet10 字节、task、ledger 保留；原费用7463/1182已结清，domain receipt=null，provider_quiescence=null，canonical owner在本段初始观察时尚未释放；后续具名退役结果见下文。独立QA及后续全部验证真实模型请求均0。旧 primary 授权已消费，不用于新发送。

## 五组交付

1. `facade.py` 明确展示 WriterTaskResultV1 外层 schema_version/result；原 section 要求仅作用于 result.draft，原 prompt 保留。formula 原占位符与 metadata 义务分开，detail/witness/Binder/assessor及原 closed atom 义务保持。full schema继续严格拒绝缺版本、错版本、字符串分支及多字段。
2. `task_store.py` 完成校验对 native blocked 要求唯一且绑定的 tool call/error result、raw与normalized严格JSON语义、事件顺序、完整usage及自然finish、原claim/来源。仅有 blocked 标签不构成证明。provider_quiescence 仍由活动execute claim登记；新Worker只读恢复，unknown继续held。
3. `workflow-driver.ts` 只在 observe_quiescence 成功后发布登记引用；最早terminal错误绑定request/session/call/raw，完成登记和cleanup作为后续错误。`l01.mjs` 增加 provider/费用/任务/backend/domain 分层报告，primary/tokenize/offline/aux到达数，以及清理错误链。
4. 新具名 operator-only `native-rejected-finish-retirement/1`，绑定旧packet/grant/plan/生产者/raw/SSE/Session/tokenizer/usage/费用、原task/claim和新实现身份；不提供recovery mint，不补登记、不重复settlement。canonical exact-owner事务仅允许释放及不可变 DshNativeRejectedBackendReleaseV1 history。packet02旧类保持严格；幂等、新owner、损坏history与事务切点均有反例。正式操作在独立代码/方案PASS后按原授权同范围实际执行，见下文。
5. 更新实际validator来源（新恢复模块及实际workflow-driver/writer-request），注册新Python与四个真实native场景，完整suite版本core/4、offline/4。TS typecheck/build/stage及候选audit完成；最终全注册certificate/cold须在独立必修关闭及代码、测试、提示、文档最终收口后统一冻结生成。

## 已观察验证（各自绑定执行时源码）

日志根 `/tmp/c2p-dsh-l01-repair-20261005-main-01`，不存在从测试计数推导质量门通过的声明。

| 原命令/证据 | 实际结果与证明范围 |
|---|---|
| `python -m pytest -q tests/integrations/dsh/test_host_recovery_boundaries.py tests/integrations/dsh/test_l01_binding_contract.py tests/integrations/dsh/test_legacy_retirement.py tests/integrations/dsh/test_coverage_use.py integrations/dsh/dev/tests/test_l01_meter.py`，focused01.log | exit0；195 passed/56 subtests；原恢复、计量、合同与旧协议基线，后续增量另列 |
| `python -m pytest -q -x tests/integrations/dsh/test_native_rejection_retirement.py tests/integrations/dsh/test_l01_binding_contract.py`，focused02.log | exit0；54 passed；新迁移和严格合同，先于最终事务/usage增量 |
| `python -m pytest -q tests/integrations/dsh/test_host_recovery_boundaries.py -k 'blocked_label or bound_native_blocked'`，blocked-proof03.log | exit0；15 passed；真实worker的blocked证明损坏反例 |
| `python -m pytest -q tests/integrations/dsh/test_host_recovery_boundaries.py tests/integrations/dsh/test_native_rejection_retirement.py -k 'total_mismatch or total-mismatch or original_grant or original-grant or atomic_transaction_cuts'`，focused04.log | exit0；4 passed；totalTokens一致性、原授权、事务提交前后恢复 |
| `python -m pytest -q tests/integrations/dsh/test_native_rejection_retirement.py -k bool`，boolean05.log | exit0，3 passed；原grant/dispatch严格整数及新授权整数反例，完整证书会重新发现 |
| `npm --prefix integrations/dsh run typecheck` / `build` / `stage`，typecheck03/build03/stage03.log | 均exit0；最后TS输入修改后的正式构建和stage，未调用模型 |
| `python scripts/dsh_dev.py --candidate 0.2.0-rc.1+loop-origin.1 audit`，audit03.log | exit0，PASS；实际候选读取 |
| `python scripts/dsh_dev.py --candidate 0.2.0-rc.1+loop-origin.1 test --output-root /tmp/c2p-dsh-l01-native-repair-20261005-04 --report-path /tmp/c2p-dsh-l01-native-repair-20261005-04/node-events.jsonl <四个绝对路径native测试>`，native04.log | exit0，4真实native场景全通过/0skip：packet10原字节、inline公式、formula metadata、缺witness；仅provider为fixture，其余Loader/native adapter/Session/worker/parser/assessor为原链 |
| `python -m pytest -q tests/integrations/dsh/test_dsh_admission.py tests/integrations/dsh/test_target_admission_integration.py`，plan-version04.log | 43通过，6项外层沙箱阻止bwrap NETLINK_ROUTE；未跳过或放宽隔离。六项以同原命令在允许namespace的宿主重跑，target-admission05.log，exit0/6passed |

早期native03暴露测试helper传入过大bootstrap帧和缺witness错误码预期错误，修helper为最小backend配置、使用实际writer_content_rejected；原日志保留。最初相对测试路径与launcher cwd不一致无测试发现，后改绝对路径。上述失败不记为通过。

真实L01 launcher分别运行 fresh 正常 `/tmp/c2p-dsh-l01-repair-normal-20261005-01`（exit0），原packet10字节拒绝 `/tmp/c2p-dsh-l01-native-terminal-rejection-20261005-01`（预期exit1），重复raw usage损坏 `/tmp/c2p-dsh-l01-repair-unknown-20261005-01`（预期exit1）。三者layered-outcome/failure/cleanup/sentinel原件保留。拒绝场景首因schema_invalid，registered=true，spent17/pending0，cancelled/无receipt/backendempty；unknown场景registered=false，spent0/pending6938/backendowned，不重发、不退款。正常局部blocked合法回执不宣称最终领域接受。均真实模型0；Python模型/网络拒绝哨兵有效。

原材料克隆迁移 `/tmp/c2p-dsh-l01-retirement-isolation-20261005-01/result.json` 在只读根、隔离网络及仅原packet/canonical路径的克隆RW挂载运行，exit0：exact-owner释放及history、相同replay、task DB/费用不变、新owner保留。该包review/auth明确fixture，不能代真实独立review或新同意；canonical mutations=0。

## 尚未验收的边界

独立代码/方案PASS和原owner退役exit0已完成，结果独立读回见后续记录；最终完整注册certificate与fresh cold-normal、fresh具体packet和该包一次明确授权、实际live及独立Gate-L仍待。不得给历史certificate09换标签。所有模型新增发送retry/repair=0，未经新包授权不执行。后续仅在Gate-L PASS及读集释放后进入M01–M03；后续Gate-M/P/G0/G各自独立验收。

## 当前代码/方案独立批准与正式本地退役

`/tmp/c2p-dsh-independent-l01-repair-code-20261005-01/review.md` 为PASS，387实际输入SHA/长度、当前engine7f82ffd4…/validator3f8c5bfc…两次一致，21项新迁移全文件独立pytest exit0/94.24s，全部实际读集释放。reviewer实际审查原producer fetch-reader natural EOF/DONE/archive-before-error协议，真实原包只读verify_original_finish PASS；正式package/independent-review.json由reviewer写入，非fixture。原用户授权适用于剩余exact-owner release/history，不增加primary/mint/settlement/task/raw/domain效果；租约PID/execution同步写单列认可。

具体package `/tmp/c2p-dsh-l01-native-retirement-package-20261005-01` 封存旧attestation、plan、实际独立review、从原grant导出的authorization-scope-record及execution-wrapper/started/result/log/before/after。命令 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python /tmp/c2p-dsh-l01-native-retirement-package-20261005-01/execute-reviewed.py`，exit0，原句柄21502已回收。该父脚本逐项比对已review的bwrap argv再调用封存module命令，RO根/unshare-net，仅canonical admission root与现存原.run_lease.lock RW；原packet/task/证据其余RO。严格原owner reader：backendempty、task DB及task语义不变、spent7463/pending0预算不变、receipt=null、provider_quiescence=null；新provider/tokenize0。history key `sha256:fb2102f9d329315264b02f91d67178a9a8678b74b731eaca2fb8526069b8713a`，原release_binding验证schema/selfdigest/key/owner通过。

当前身份fresh隔离02原材料克隆也exit0，结果 `/tmp/c2p-dsh-l01-retirement-isolation-20261005-02/result.json`；不替代正式结果。独立正式迁移结果只读复核 `/tmp/c2p-dsh-independent-l01-native-retirement-result-20261005-01/review.md` 实际PASS、读集全部释放：真实canonical history全部严格selfdigest/key/binding，原exact owner唯一key等于正式receipt；task/DB字节、完整facts/ledger、预算及raw/attestation文件不变，wrapper SHA/actual/moduleargv与独立code-review一致。只读verify exit0，新执行/模型0。Gate-L仍FAIL。

## 最终注册验证执行计划与机器结果入口

代码/测试/提示/docs全部收口后，统一冻结并运行一次原完整manager：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -c 'from code2paper.cli.main import main; raise SystemExit(main())' method-agent record-offline-receipt --out /tmp/c2p-dsh-l01-admission-20261005-01/receipt.json --suite-plan dsh-stage04 --output-root /tmp/c2p-dsh-l01-admission-20261005-01/managed --candidate 0.2.0-rc.1+loop-origin.1 --timeout-seconds 7200
```

上述01命令实际已执行并失败，详见下面的具体原因和修复。后续最终运行采用fresh02，结果只按其receipt/managed原report及exit采信，不能回填或复用失败01。完整包括注册Python、Node、operator和独立fresh cold-normal，来源门/原namespace/模型拒绝哨兵保持。外部主执行索引记录实际句柄/exit与原complete/cold reader；在此冻结验证及随后fresh packet绑定期间不再改engine输入文档。最终receipt、`original-complete-reader-validation.json`、`original-cold-reader-validation.json`及fresh packet均位于上述fresh外部根，准入依赖这些机器记录。纯docs收口后的engine不同于代码review身份，生产代码/validator与review相比无变更；保存独立差分，不能给旧review或旧certificate换标签。

## 完整01失败及测试时点修复（最终冻结前）

最终冻结01为engine `sha256:5fd5000c1a915266d9781b70a7d13dc7675432e633e6e4fd7f4123abc27af378` / validator3f8c5bfc…。原manager实际exit1（句柄98244回收），Python1384/56subtests通过、Node214pass/1fail/0skip，cold-normal未执行，receipt passed=false。失败是主执行者新增的backend断言时点错误：原kernel.call注入release异常后原owner确为held，但断言放在健康新worker已执行原recoverStoredOutput.finally.releaseBackend之后，误预期仍owned。原baseline没有这个新assert；生产恢复/完成/释放规则始终未改。

只修 `integrations/dsh/tests/host-provider.test.ts`：旧故障/worker-cut后立即以原reader断言exact original owner held；健康新进程恢复后断言empty，再调用原 `verify_finished_backend` 证明registered finish/raw/Session/usage/settlement及exact不可变history。result保存两个时点及严格release receipt，原领域拒绝仍为primary、cleanup仍为secondary，recovery发送0。未把empty单独当证明，不弱化原门。

`npm --prefix integrations/dsh run typecheck` exit0（typecheck06.log）；原launcher两个绝对路径 `writer-release-failure.test.ts` / `host-recovery-before-record.test.ts` 在fresh `/tmp/c2p-dsh-l01-release-recovery-20261005-06` 完整运行，exit0、2pass/0fail/0skip、172.153s，句柄21910已回收，日志release-recovery06.log。独立 `/tmp/c2p-dsh-independent-l01-recovery-test-delta-20261005-02/review.md` PASS、读集释放：原严格finish/history/费用reader逐目录PASS，98项production/dev/validator源码SHA与已审查字节一致。只有测试/文档改变，不重复build/stage；旧complete01结果仍按原身份保留。

此次源输入变更与真实失败已解释，因此新的统一完整运行不是无变化幸运重跑。所有代码/测试/提示/docs现再次收口后冻结，最终命令沿用上面的原manager，仅fresh路径为 `/tmp/c2p-dsh-l01-admission-20261005-02/receipt.json` 与 `/tmp/c2p-dsh-l01-admission-20261005-02/managed`，共享deadline仍7200s。原complete/cold reader机器输出写入02根；外部主执行索引保存实际句柄/exit/结果。在本次冻结与fresh packet绑定阶段不再写engine输入文档。新模型请求仍0，Gate-L未通过，正式C–F不越门。
