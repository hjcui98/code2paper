# code2paper_agent

Story-first code-to-paper pipeline with embedded `CodeIntakeAgent` and
`CodeAnalyzerAgent`, deterministic Method authoring, and Phase 5 PaperBanana
figure generation.

The new agentic route keeps author intent and code evidence deliberately
separate: intent controls what the graph investigates and emphasizes, while
frozen code evidence and validators control what may be written or drawn.

## Overview

Current end-to-end flow:

1. `author_markers.yaml + code repo`
2. Phase 1 `CodeIntakeAgent`:
   `code_sources.json`, `core_snippets.json`, `method_code_alignment.json`, `code_intake_report.json`, `raw_evidence_pack.json`
3. Phase 2 `CodeAnalyzerAgent`:
   `code_facts.json`, `code_method_analysis.json`, `code_alignment_ir.json`, `code_ir.json`, `entity_links.json`, `code_analysis_report.json`
4. Phase 3 Method Evidence Freeze:
   `method_evidence.json`, `claim_evidence_map.json`, `method_evidence_review.md`
5. Phase 4 Deterministic Method Writer:
   `method_draft.md`, `method_draft.tex`, `method_outline.json`, `terminology_table.json`, `draft_claim_map.json`, validation reports
6. Phase 5 PaperBanana:
   `method_overview.paperbanana_input.txt`, `method_overview.png`, `method_overview.meta.json`

## Run

```bash
PYTHONPATH=src python3 -m code2paper.run_cli \
  /path/to/code_repo \
  --author examples/author_markers.story_first.example.yaml \
  --out-root /tmp/code2paper_run \
  --llm-provider openai \
  --llm-model kimi-k2.5 \
  --figure-backend paperbanana \
  --paperbanana-root /home/cuihengjia/agent/PosterGen/PaperBanana \
  --retrieval-setting random \
  --num-candidates 1 \
  --aspect-ratio 16:9 \
  --exp-mode demo_full \
  --allow-fidelity-fail
```

Default Phase 5 behavior:

- backend: `paperbanana`
- retrieval: `random`
- fallback on figure error: disabled by default (`--no-fallback-on-figure-error`)

Enable fallback SVG explicitly:

```bash
--fallback-on-figure-error
```

## Main CLI

```bash
PYTHONPATH=src python3 -m code2paper.main_cli run ...
```

Subcommands:

- `run`: full Phase 1-5
- `intake`: story-first Phase 1 only
- `analyze`: story-first Phase 2 only
- `evidence`: Phase 3 only
- `author`: Phase 4 only
- `validate`: fidelity check only

## Agentic LangGraph route

Install the optional orchestration dependencies and run the deterministic
safe path:

```bash
python3 -m pip install -e '.[agentic,dev]'
code2paper-agentic-run tests/fixtures/toy_train_project \
  --author tests/fixtures/toy_train_project_author_markers.yaml \
  --out-root /tmp/code2paper-agentic-toy \
  --llm-provider none \
  --fail-on-blocked
```

For a local OpenAI-compatible model (including vLLM), set the endpoint and
model in the environment, then choose `--llm-provider openai`. A loopback
endpoint may use the non-secret placeholder `dummy-local-vllm`; never commit a
real API key or `.env` file.

```bash
export CODE2PAPER_OPENAI_BASE_URL=http://127.0.0.1:8000/v1
export CODE2PAPER_LLM_MODEL=gemma4-31b-nvfp4
export OPENAI_API_KEY=dummy-local-vllm
code2paper-agentic-run tests/fixtures/toy_train_project \
  --author tests/fixtures/toy_train_project_author_markers.yaml \
  --out-root /tmp/code2paper-agentic-toy-live \
  --llm-provider openai \
  --llm-model gemma4-31b-nvfp4 \
  --fail-on-blocked
```

Exit code `1` means the graph ended in an evidence-preserving explanatory
block when `--fail-on-blocked` was requested. Exit code `2` is a CLI,
dependency, configuration, or infrastructure error. Run artifacts and the
decision/audit summaries are under `<out-root>/artifacts/10_run/`. Live model
tests are opt-in (`CODE2PAPER_RUN_LIVE_LLM=1`) so the default suite never
contacts a service unexpectedly.

Every formal agentic run freezes `repo_snapshot.json` before analysis and
emits `evidence_snapshot_v2.json`, `atomic_claims_v2.json`, and
`agentic_artifact_freshness_report.json`. Evidence V2 stores the exact source
excerpt plus file/tree digests; the authoring projection, final-text validator,
traceability ledger, readiness report, and completion report are bound to that
same snapshot. If source code changes while a run is in progress, continuation
blocks with `source_drift` before model or response-cache reuse. Evidence repair
creates a versioned child snapshot with `parent_evidence_snapshot_id` instead
of editing the frozen parent in place.

## Tests

```bash
python3 -m pytest -q
```

## Key Paths

- schemas: `src/code2paper/schemas.py`
- story-first adapter: `src/code2paper/story_first.py`
- phase wrappers: `src/code2paper/pipeline/`
- embedded agents: `src/code2paper/agents/`
- figure backends: `src/code2paper/figures/`
