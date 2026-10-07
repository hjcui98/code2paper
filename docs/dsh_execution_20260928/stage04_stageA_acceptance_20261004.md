# 第04份 Stage A 独立验收与 L01 接续（2026-10-04）

Stage A 的 R01/R02/R03/R04/V01/A01/V02 全部独立 PASS，**Gate-R、Gate-V PASS**。
任务表据此从17/49推进到 **24 done / 1 in_progress / 24 planned**；L01仅进入离线准备，真实推理请求为0。
C–F保留原Gate-L/M/P/G0/G前置，长期模块23项中已完成7项。

## 验收依据和身份

独立报告：[review.md](/tmp/c2p-dsh-independent-stageA-039/review.md)，SHA256 `1f9bf679a9f84ace25b3ba71e7dd7185fc8b6c13a9edf1dfd9032bc52f09076a`。
结论为 codeQualityStatus=CLEAR、recommendation=APPROVE、blockers=[]；QA-V02-COVERAGE-1关闭。
独立验收结束已明确释放所有源码、runtime及封存产物读集。

039封存包：[c2p-dsh-stage04-20261004-ud6x5a4s/phaseA-submission-039](/tmp/c2p-dsh-stage04-20261004-ud6x5a4s/phaseA-submission-039/submission.json)。
受验source为 `sha256:1ea010226f4ed4f68619c59c5ebfbda599feed2543de80d9842d57c48d301b76`，validator为 `sha256:4673413ad3e99497006095046dbd063a121a96cc5fec97f8989efb87cae22d5e`。
独立复算全部1484个manifest条目和顶层seal一致，原完整回执及cold-normal使用校验均通过。
本次文档、任务表和实施记录更新发生在释放后，不将更新后的工作树重新标为039受测身份；旧证据保持原字节。
L01必须在其代码、配置、产物冻结后取得匹配的新离线回执。

| 原AT | 裁决 | 行为范围 |
|---|---|---|
| AT-R01 | PASS | 持久task/outbox/claim、fence、单run/backend独占、跨进程恢复 |
| AT-R02 | PASS | 原Python唯一账本和真实worker reserve/dispatch/usage/unknown、费用幂等 |
| AT-R03 | PASS | 真实DSH child/Host/worker/terminal/Session/ingest及发送前组成核验 |
| AT-R04 | PASS | 全规定崩溃切点、取消、静止证明、unknown保留与本地恢复 |
| AT-V01 | PASS | 技术页/作者页、三终态、原parser/Binder/reader及Python零模型哨兵 |
| AT-A01 | PASS | 实际三suite机器覆盖、伪标签/缺报告/退出失败/漂移拒绝 |
| AT-V02 | PASS | opt-in默认串行、真实CLI qualifier、fresh cold-normal消费完整证书 |

## 已观察验证

所有命令均在上述039身份上结束，退出码0。候选为 `0.2.0-rc.1+loop-origin.1`，C2P_DSH_DEV_ROOT指向其现有隔离候选目录。

- `python -m pytest -q -m 'not live_llm'`：4664 passed、3明确live deselected、68 subtests，1348.07s；[日志](/tmp/c2p-dsh-stage04-20261004-ud6x5a4s/v02-final-full-static-039.log)。
- 原 `method_agent_main record-offline-receipt --suite-plan dsh-stage04 --candidate 0.2.0-rc.1+loop-origin.1 --out /tmp/c2p-dsh-stage04-20261004-ud6x5a4s/managed-final-039-receipt.json --output-root /tmp/c2p-dsh-stage04-20261004-ud6x5a4s/managed-full-039 --timeout-seconds 4200`：Python1256、Node210、实际CLI qualifier1，原完整证书passed=true、1467通过；[管理日志](/tmp/c2p-dsh-stage04-20261004-ud6x5a4s/managed-full-039.log)。
- 完整证书生成后，独立fresh cold-normal实际CLI1通过，原target admission先于epoch、原预算call/completed/spent/pending=1/1/17/0；normal结果不参与铸造证书，没有循环自证。
- 原validator拒绝七项实际完成产物的有界语义反例，每次恢复原字节，最终原证书仍通过。
- 候选typecheck、compileall、git diff --check通过；前后source/validator无漂移；所有验证进程已终止。

完整证书SHA256 `134197f7e8500b2c66b49b4a855f7474065c07960f46944642ec931707f72e08`，77885bytes；
cold-normal SHA256 `27198e56b4b86c7c51cf7de03f64e6c3f735b92c2b3cfaf9db1711f49bfd84c7`，31438bytes。
独立报告中的LOW项是Node wrapper事件file归属显示，审查已由实际argv/env/节点/summary核实覆盖，不是阻断或新增门。

## 后继工作和边界

按[长期模块](stage04_06_long_module_execution_20261004.md)连续进入B，准备L01真实Qwen wire、原输入、计量、单primary额度/时限/停止条件和可执行命令，然后集中处理原具体live授权。
8006的`/health`与`/v1/models`在2026-10-04T03:59:00Z均HTTP200、模型id=qwen38-27b-nvfp4；这是同服务两个接口的历史只读观察，live前仍核当前队列/KV。
独立Stage A并未批准L01、主图迁移、默认切换、D5、Verified或发布；领域pending_validation边界保持。
