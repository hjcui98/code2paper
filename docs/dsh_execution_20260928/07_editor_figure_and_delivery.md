# 07 · 编辑、全文事务、方法图与交付展示

> 2026-09-28 执行计划；所有实现和新测试均待实施。历史代码/环境证据不计为任务完成。

依据：总设计 §§16–18、21 WP6；Writer设计和08-22 Candidate修订。前后依赖以 [任务表](task_board.json) 为准；接口遵循 [interfaces.md](interfaces.md)。

在主图迁移完成后，交付有完整来源与版本一致性的正文及同源方法图。

### 权限与事务的最后接线

允许正文词句来源只有Writer/Formalizer/Editor/Rewrite。Realizer、主Agent、Host、RunCapsule和deterministic assembler不能创作技术正文。Editor/Rewrite引发正文digest变化时必须重做受影响绑定/验证；未改span保持原来源，不能把全文重新标成Editor生成。

F02 显式替换原 [Writer全文输出](../../src/code2paper/agentic/publication_method_writer.py) :27880 的Markdown/authorship/checkpoint分写，用K02同一manifest承载真实全文。Candidate、Verified、publication-ready是不同谓词；Candidate可按08-22 policy记录作者specification，但不能晋升为repository Verified。Verified空须显示真实原因，不能按工具completed或局部accepted导出为最终已验证正文。

### Figure同源和范围

[figure_planner](../../src/code2paper/agentic/figure_planner.py) :98 已使用MethodEvidence/claim map；现 hard_gate_passed :166 的有节点/有evidence IDs不等于全文结构/方向正确。当前研究未在正常Method authoring入口找到完整Figure接线，F03必须证明正常入口实际触发。

复用既有IR/scene/relation validator，由canonical技术材料投影兼容输入；固定正文版本，登记section↔mechanism↔node/edge、条件分支和必要覆盖。caption通过允许措辞角色，图像与可编辑源、renderer/config摘要同时登记。反向箭头、虚构模块、漏必要节点、正文改变后复用旧图均拒绝。

离线可用确定renderer fixture验证管线；真实图像/模型服务需要额外live授权。无vision只报告视觉质量not_measured，不伪称视觉验收完成。operator export只读取已批准的对应级别产物，不新增事实/改文/升级状态；模型不得通过export或submit旁路提交。

## 实施单元

每单元由owner实施、reviewer独立复核；同一文件只能由一个活动任务写入。下列路径标“拟新增”的当前不存在，不是已有能力。

### F01 · Editor/Rewrite全文编辑场景与权限收口

| 项 | 约定 |
|---|---|
| owner / reviewer | CONTENT / QA |
| 前置 / WP | G08 / WP6 |
| 独占编辑范围 | `src/code2paper/agentic/publication_method_writer.py`（现有）<br>`src/code2paper/agentic/final_text_authorship.py`（现有）<br>`integrations/dsh/src/role-dispatch.ts`（拟新增）<br>`tests/integrations/dsh/test_editor_workflow.py`（拟新增）<br>`src/code2paper/agentic/authoring_execution_identity.py`（现有） |
| 步骤与交付 | 基于G05已接入的真实Editor/Rewrite，完成全文编辑场景、section-scoped patch及owner精确问题修复；同全文版本串行。正文变化更新digest、失效绑定和验证、重做必要Binder。未改span保持原来源，允许角色只Writer/Formalizer/Editor/Rewrite；不重复实现角色调用器。 同步维护原VALIDATOR_BUNDLE_SOURCES版本化来源清单，仅添加本任务已落地的裁决文件；由LEAD串行分配该共享文件写权。 |
| 验收 AT-F01 | 删唯一支持内容、Host补一词、缺response_ref均拒绝；旧验证不能发布新正文；语义差分和quality gate保持，不以少重复掩盖义务丢失。 仅改变新增/抽取的裁决逻辑即可使validator身份变化，缺来源文件明确拒绝。 |
| 待形成测试/证据 | `test_editor_workflow.py` |

### F02 · 全文输出接入同一发布事务

| 项 | 约定 |
|---|---|
| owner / reviewer | CORE / QA |
| 前置 / WP | F01 / WP6 |
| 独占编辑范围 | `src/code2paper/agentic/publication_method_writer.py`（现有）<br>`src/code2paper/agentic/authoring_artifact_publication.py`（现有）<br>`tests/integrations/dsh/test_full_publication.py`（拟新增）<br>`src/code2paper/agentic/authoring_execution_identity.py`（现有） |
| 步骤与交付 | 迁移_write_publication_outputs原Markdown/sidecar分写为K02原owner事务；有序正文来自共享composer，Candidate/Verified及authorship/acceptance/final-integrity同版本；固定路径导出可重建。 同步维护原VALIDATOR_BUNDLE_SOURCES版本化来源清单，仅添加本任务已落地的裁决文件；由LEAD串行分配该共享文件写权。 |
| 验收 AT-F02 | 真实Method入口g1→g2每个写点故障保持完整可读旧/新版本；仅局部accepted、缺Verified或sidecar不全不得设置publication_ready；旧归档不覆盖。 仅改变新增/抽取的裁决逻辑即可使validator身份变化，缺来源文件明确拒绝。 |
| 待形成测试/证据 | `test_full_publication.py` |

### F03 · 同源Figure计划、渲染与正文一致性

| 项 | 约定 |
|---|---|
| owner / reviewer | CONTENT / QA |
| 前置 / WP | F02 / WP6 |
| 独占编辑范围 | `src/code2paper/agentic/figure_planner.py`（现有）<br>`src/code2paper/integrations/dsh/workflow_adapter.py`（拟新增）<br>`integrations/dsh/src/role-dispatch.ts`（拟新增）<br>`tests/integrations/dsh/test_figure_workflow.py`（拟新增）<br>`src/code2paper/agentic/authoring_execution_identity.py`（现有） |
| 步骤与交付 | 复用EvidenceBackedFigurePlan及scene/relation validator；同canonical技术存储投影、冻结正文版本，建立section/mechanism/node-edge映射与必要覆盖。渲染产出可编辑源和renderer/config/image摘要；caption来自允许措辞角色。 evidence-backed图只表达已授权实现；作者说明/未验证设计若单列展示，需机器侧与视觉authority标注，不升级repository支持。 同步维护原VALIDATOR_BUNDLE_SOURCES版本化来源清单，仅添加本任务已落地的裁决文件；由LEAD串行分配该共享文件写权。 |
| 验收 AT-F03 | 正常Method入口实际接线，反箭头/虚构模块/漏必要节点/旧正文版本图拒绝；无vision视觉质量标not_measured。离线renderer fixture先验，真实模型/图像服务另授权。 作者Candidate段的未实现模块不能画成已实证模块，caption同样不得升级事实。 仅改变新增/抽取的裁决逻辑即可使validator身份变化，缺来源文件明确拒绝。 |
| 待形成测试/证据 | `test_figure_workflow.py` |

### F04 · 操作者导出与状态展示

| 项 | 约定 |
|---|---|
| owner / reviewer | DSH / QA |
| 前置 / WP | F03 / WP6 |
| 独占编辑范围 | `integrations/dsh/src/artifact-view.ts`（拟新增）<br>`integrations/dsh/src/cli.ts`（拟新增）<br>`src/code2paper/integrations/dsh/facade.py`（拟新增）<br>`tests/integrations/dsh/test_export_authority.py`（拟新增）<br>`src/code2paper/agentic/authoring_execution_identity.py`（现有） |
| 步骤与交付 | 展示waiting/blocked/local accepted/Candidate/Verified/publication-ready及具名原因；operator export只读已获准不可变成员，模型没有export/prepare/submit。导出不提升产品等级。 同步维护原VALIDATOR_BUNDLE_SOURCES版本化来源清单，仅添加本任务已落地的裁决文件；由LEAD串行分配该共享文件写权。 |
| 验收 AT-F04 | 损坏/错版本成员拒绝导出；候选不标Verified；普通模型工具不能访问管理RPC；历史产物按身份可浏览，不能成为新run事实依据。 仅改变新增/抽取的裁决逻辑即可使validator身份变化，缺来源文件明确拒绝。 |
| 待形成测试/证据 | `test_export_authority.py` |

## 验证、交接与完成门

以下是实施后的执行命令，本轮未运行；所列旧文件已确认存在。新增任务测试落地后按上表AT逐项运行并登记实际节点/断言，不可只登记文件名。

```bash
python -m pytest -q tests/test_agentic_final_text_authorship.py tests/test_agentic_publication_method_writer.py tests/test_agentic_figure_planner.py tests/test_agentic_figure_trust_p2.py
npm --prefix integrations/dsh run typecheck
npm --prefix integrations/dsh run build
npm --prefix integrations/dsh run test:integration
git diff --check
```

Node脚本由B02/H01先定义并锁定，实际运行必须经隔离launcher，不能因脚本缺失而直接在日常profile启动。新增Python测试在tests/integrations/dsh/，Node测试在integrations/dsh/tests/；修原owner的反例也扩已有测试，不复制其实现。

交接包包含：任务ID、输入/代码/配置身份、接口及存储版本差异、改动文件、最小反例修前/修后结果、真实接线证据、准确命令/退出码/原始输出引用、未测项与恢复办法。独立reviewer依据 [verification.md](verification.md) 复核；Gate-F要求F01–F04。 各门要求对应AT及跨任务接线，不凭一个helper单测结案。

[返回总执行入口](README.md)
