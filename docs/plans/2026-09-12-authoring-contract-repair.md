# 第一批修复：模型接口、研究上下文和质量指标

**目标：**落实根因报告 R1/R2/R9，先接通可验证的数据链，保持事实授权和 shared payload 契约。

**范围：**从 `284eaa9` 开始；保留本地 AGENTS 清理改动。Codex 直接实现、验证，不提交代码。后续研究策略、论文质量和真实模型验收不以本批静态测试替代。

## 1. Formalizer 客户端契约

- 修改 `src/code2paper/agentic/formalization_agent.py`。
- 在 `tests/test_agentic_mechanism_formalizer.py` 添加真实 LLMRequest/LLMResponse 类型回归：caller 必须被调用，读取 text，拒绝 blocked 和无效响应，不依靠 operation fallback 掩盖失败。
- 请求保存模板版本、义务及共享 payload 身份；响应仍须通过现有公式绑定检查。

## 2. 研究到 Writer 的上下文

- 修改 `autonomous_method_agent.py` 与 Writer repository context loader。
- 传递本次实际写出的 artifact paths，保留 briefs、snapshot、symbol index；保留旧入口所需的兼容读取。
- 对提供的 snapshot/index 验证身份与源码摘要。损坏、异源和漂移不能被吞成空值。
- 测试从产品入口到 context loader 的路径，以及跨文件 helper 读取、异源/损坏输入失败。

## 3. 评估口径

- 修改 `publication_quality.py`、`method_content_trace.py` 及 Writer 调用端。
- support precision 使用确实评估的文本及计数，缺报告、未验证或无分母返回未知；保持现有硬门。
- 将 Research 发现覆盖与 closure 内保留率区分，不再从 closure 自己构造发现分母；独立评估清单缺失时 discovery recall 标未知。
- 测试漏一个预期操作时发现覆盖下降；正文/报告摘要不一致不能混用；未验证文本不得 precision=1。

## 验证与交付

Formalizer 先以新增用例复现接口错误，再修复；其余环节添加对应回归用例。运行相关 Formalizer、产品入口、Writer、quality/content trace 测试。根据实际依赖选择本地隔离环境，记录命令、结果和本批尚未覆盖的真实运行条件。

当前状态：本批已完成。最终关联回归 262 passed、1 skipped；安装后的真实命令完成无模型冒烟，产物交接核验通过。真实模型 Method 质量验收尚未执行。

详细交付：[第一批修复与验证记录](<D:/agent poster/Code2Paper/Code2Paper/analysis/2026-09-12-code2paper/第一批修复与验证记录.md>)。

额外修复了 runner 的最终质量回写：它原本会把 caveated 计入 supported，并在零分母时写回满分。现在与 Writer 共用计数/正文摘要校验逻辑。

Windows 测试调整：使用可移植的临时目录和文件名；符号链接权限不足时只跳过独立的符号链接参数用例，越界、缺失和摘要篡改检查仍执行。

实际命令验证补充发现安装脚本指向旧 main_cli，无法识别 method-agent；现已增加到产品入口的转发，并加入安装入口回归。另修复 runner 在总状态未变化时未回写验证状态的问题。

扩展机制编译测试另有 2 项已有失败，在 git archive 导出的原始 HEAD 上复现；保留为后续问题，不修改断言或宣称全仓测试全通过。
