# Code-to-Paper + PaperBanana 依赖汇总

> **历史环境快照。** 本文记录 2026-04-17 的 legacy/PaperBanana 环境，包含
> 不可移植的本机路径，也未覆盖当前 agentic/R8 开发依赖。当前依赖以
> [`pyproject.toml`](pyproject.toml) 和 [`README.md`](README.md) 为准；
> 文档分类见 [`docs/README.md`](docs/README.md)。

生成日期：2026-04-17

建议统一使用 Python 3.11。`code2paper_agent` 本身支持 Python 3.10+，但当前 `/home/cuihengjia/agent/PosterGen/PaperBanana` 已有 3.10/3.11 运行痕迹，Python 3.11 是比较稳的折中。

## 一键 Conda 环境

从仓库根目录 `/home/cuihengjia/agent` 执行：

```bash
conda env create -f code2paper_agent/environment.paperbanana.yml
conda activate code2paper
```

这个环境只安装 `code2paper_agent` 和 `/home/cuihengjia/agent/PosterGen/PaperBanana` 图片链路需要的依赖；不安装 DeepScientist，也不安装 `PosterGen/paperany`。

## Code2Paper 核心依赖

来源：`code2paper_agent/pyproject.toml`

```text
python>=3.10
setuptools>=68
pydantic>=2.0
PyYAML>=6.0
```

## LLM API 依赖（Phase 2 / 可选增强）

当前主链路中，Phase 3/4 已经改为 deterministic evidence freeze 和 deterministic writer；`method_draft.md` 与 `method_draft.tex` 不再依赖多次 schema-gated LLM authoring。LLM provider 主要用于 Phase 2 代码理解，或者后续可选的单次 polish：

```text
openai
anthropic
google-genai
```

建议首版先接一个主 provider，再保留 provider 抽象层。常用环境变量：

```text
OPENAI_API_KEY
ANTHROPIC_API_KEY
GOOGLE_API_KEY
CODE2PAPER_LLM_PROVIDER
CODE2PAPER_LLM_MODEL
```

没有 API key 时，story-first `CodeIntakeAgent` / `CodeAnalyzerAgent` 会关闭可选 LLM review/synthesis，并使用 deterministic 代码扫描、snippet 抽取、alignment 和 method draft writer 继续产出 Phase 1-5 artifacts。

可选图导出：

```text
CairoSVG>=2.7
```

测试：

```text
pytest
```

## 一键运行当前主链路

下面命令运行当前 checked-in 主链路：Phase 2 负责代码理解，Phase 3 冻结 evidence-backed method IR，Phase 4 从 stage packets 确定性生成方法草稿并运行验证：

```bash
code2paper-run <project_root> \
  --author <author_markers.yaml> \
  --project-id <project_id> \
  --out-root <run_output_root>
```

如果当前 shell 还没刷新 console script，也可以使用模块入口：

```bash
PYTHONPATH=/home/cuihengjia/agent/code2paper_agent/src python -m code2paper.run_cli \
  <project_root> \
  --author <author_markers.yaml> \
  --project-id <project_id> \
  --out-root <run_output_root>
```

该命令会一次性生成当前 scaffold 产物：

```text
paper/method/raw_evidence_pack.json
paper/method/code_alignment_ir.json
paper/method/method_evidence.json
paper/claim_evidence_map.json
paper/method/method_draft.md
paper/method/method_draft.tex
paper/method/method_fidelity_report.json
paper/method/code2paper_run_report.json
```

## DeepScientist Skill 复用说明

code2paper 图片流程可以复用 DeepScientist 的 skill 思路，但不需要把 DeepScientist 安装进 conda 环境。

当前已增加：

```text
code_tex_fig/DeepScientist/src/skills/code-to-method/SKILL.md
```

它是 companion skill，负责指导 DeepScientist agent 调用：

```text
ingest -> align -> method_evidence -> claim_ground -> method_draft -> figure -> fidelity
```

可复用的现有 DeepScientist skills：

```text
write/SKILL.md
figure-polish/SKILL.md
```

- `write`：复用 `claim_evidence_map.json`、method draft、paper contract 的写作边界。
- `figure-polish`：复用 paper-facing figure 的 render-inspect-revise、导出格式和视觉规范。

只有当你要启动完整 DeepScientist 外壳或 MCP/quest runtime 时，才需要额外安装 DeepScientist：

```text
python>=3.11
setuptools>=68
cryptography>=42,<46
lark-oapi>=1.5,<2
mcp>=1.19,<2
Pillow>=10,<12
PyYAML>=6,<7
rich>=14,<15
textual>=0.80,<1
websockets>=15,<16
agent-client-protocol>=0.8,<1  # optional acp extra
```

可选安装命令：

```bash
pip install -e code_tex_fig/DeepScientist[acp]
```

## PaperBanana 核心依赖入口

来源：

- `PosterGen/PaperBanana/requirements.txt`

推荐安装入口是：

```bash
pip install -r PosterGen/PaperBanana/requirements.txt
```

PaperBanana 当前没有 `pyproject.toml` / `setup.py`，所以不需要 `pip install -e PosterGen/PaperBanana`。`code2paper` 会通过 `--paperbanana-root /home/cuihengjia/agent/PosterGen/PaperBanana` 直接调用 `skill/run.py`。

### requirements.txt 包

```text
google-genai
gradio>=5.0.0
streamlit
asyncio
aiofiles
pillow
numpy
tqdm
json_repair
anthropic
openai
matplotlib
python-dotenv
pyyaml
google-auth
huggingface_hub
```

## PaperBanana 配置

PaperBanana 支持两类配置方式：

```text
PosterGen/PaperBanana/configs/model_config.yaml
环境变量
```

常用环境变量：

```text
GOOGLE_API_KEY
OPENAI_API_KEY
ANTHROPIC_API_KEY
OPENROUTER_API_KEY
AIHUBMIX_API_KEY
MAIN_MODEL_NAME
IMAGE_GEN_MODEL_NAME
```

## 系统 / Conda 二进制依赖

精简 conda 环境里安装：

```text
poppler
cairo
pango
```

用途：

- `cairo` / `pango`：SVG/PDF/PNG 渲染转换。
- `poppler`：PDF 解析与图片转换。

可选项：

```text
inkscape  # 只有需要额外 SVG 编辑/转换工具时安装；如果 conda 找不到，用 apt 安装
wkhtmltopdf  # 只有需要 imgkit/HTML 截图链路时安装；当前 PaperBanana skill 主链路不强制需要
tectonic  # 只有需要 LaTeX 编译 gate 时安装
```

Ubuntu 可选系统安装：

```bash
sudo apt-get update
sudo apt-get install -y inkscape wkhtmltopdf
```
