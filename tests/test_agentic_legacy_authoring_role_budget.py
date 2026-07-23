from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.legacy_authoring_stage_tool import _llm_config
from code2paper.llm.role_config import METHOD_WRITER, apply_role_config


def test_legacy_authoring_defers_to_the_role_writer_budget(tmp_path: Path) -> None:
    """The V3 wrapper must not convert the writer's 8192 budget to 4096."""

    state = AgenticRunState(
        project_root=tmp_path,
        out_root=tmp_path / "out",
        llm_provider="openai",
        llm_model="gemma4-31b-nvfp4",
    )
    with patch.dict(
        "os.environ",
        {
            "CODE2PAPER_LLM_MAX_OUTPUT_TOKENS": "12000",
            "CODE2PAPER_LLM_TEMPERATURE": "0",
        },
        clear=False,
    ):
        base = _llm_config(state)
        writer = apply_role_config(base, METHOD_WRITER)

    assert base.max_output_tokens == 12000
    assert writer.max_output_tokens == 8192
