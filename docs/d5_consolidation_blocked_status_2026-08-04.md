# D5 合并里程碑当前状态

- 状态：`BLOCKED`（plan §12）
- 日期：2026-08-04
- 依据文档：`.agent/task.md`、`.agent/plan.md`、`.agent/implementation.md`

## 一、当前问题

模型产出质量不达标，不是机制问题。

全部 D5 机制已实现且 fail-closed：
- fail-closed final-text validation、有界 Writer owner-retry（monotonic budget）
- move/role text-witness gate、锚定 supported recall、语义+跨节 claim 重复检测
- config key+value rendering、`sym:`/闭集 ID 内部词汇扫描、`_section_editable`
- 有界 Formalization owner path（operand/operator/theory-upgrade guard，一次重试）
- route 执行（configuration/formalization 自动满足；author/empirical/literature 外部队列）
- affected-only resume（未影响节的 checkpoint digest 不变）
- 真实 Editor Pareto/no-loss 决策（现场拒绝删唯一内容的候选，精确还原 incumbent + transitions）
- Rewrite（typed-issue scope，候选失败精确回滚）
- CrossSectionEditResultV1 digest 重建、空 enum schema 引擎致命 bug 修复、duplicate rate 双计 bug 修复
- role 语义（非 required move 不再误判角色缺失）

静态：2299 passed, 3 skipped, 12 subtests passed（最终代码态；compileall 和 diff-check clean）。

三次真实矩阵（qwen36-27b-nvfp4 @ 127.0.0.1:8003，thinking 保持开启）：
- attempt-1（冻结 RAP）：16/18 节接受，safety 3/4 通过，utility 全 false
- attempt-2：技能 v1.1 提示词击穿 JSON 合规 → 2/18 接受（根因链：空 enum → engine crash + v1.1/v1.2 规则使模型 JSON 合规从 3/3 降到 0/3）
- attempt-3（v1.0 skill + regenerated RAP + 全部修复）：14/18 接受，RAP/DyG safety 通过、recall 1.0

但 utility 一律 false，根因是 **Writer 产出的 prose 质量不达标**：
- 正文仍是 code-audit 清单（claims 本质是 fact 序列化记录，"X calls Y, Z"）
- 方程被写成裸片段（"x + y when ..."）或不渲染
- Rewrite（owner 修复通道）同样 schema/再验证失败

且 **prompt 层加内容规则会击穿 json_object 模式的 JSON 合规性**（受控探针：v1.0 3/3 vs v1.2 1/3），无法通过 prompt engineering 强制提升质量。

## 二、预计如何解决

需要从架构层面决定，不在本次实现权限内。可能方向：

1. **更强的 Writer 模型** — 换模型（更严格的结构化输出可靠性 + 更好的内容生成能力）。qwen36 在 json_object 模式下不可靠，native schema 历史上也大面积失败（v6 comment）。
2. **D2.5 claims 质量提升** — 不把 fact 序列化记录当 canonical_text，改从 behavior graph symbols 编译可读 claim 语句。RAP 的 `sym:<hash>` 修复后仍留有 fact-inventory 形式；其他三个项目同理。
3. **接受当前安全/utility 的差距** — Codex 判断是否需要在保持 fail-closed 的前提下调整 D5 退出条件（例如，在一定 writer skill 提升前承认 utility 不闭合）。

## 三、还没完成

- **Phase G 盲评** — 需要各项目「通过自动化门的最终候选」才能制包，当前没有项目通过 utility/final-integrity。
- **Phase F 的最终通过矩阵** — 三次 attempt 后证据已排除了「改代码能解决」的可能（除非换模型或重新设计 claim 源头）。
- `utility_gate=true` / `final_integrity_gate_passed=true` 在任何项目上均为 false——这是当前的质量天花板。

## 证据位置

- 实现文档：`.agent/implementation.md`（BLOCKED，完整根因链、探针数据、三次 attempt 的逐项目终端字段）
- 矩阵 attempt roots：
  - `/tmp/code2paper-post-r8-d5-consolidated-20260804-1`（冻结 RAP fix10）
  - `/tmp/code2paper-post-r8-d5-consolidated-20260804-2`（v1.1 skill + regenerated RAP）
  - `/tmp/code2paper-post-r8-d5-consolidated-20260804-3`（v1.0 skill + regenerated RAP + 全部修复，最优状态）
- D2.5 再生 RAP：`/tmp/code2paper-static-rap-regenerated-20260804`（从 `/tmp/rap-fixture-fixed` + 当前通用管线）
- 静态：`2299 passed` 最终代码态（最终 static milestone 已通过）。
