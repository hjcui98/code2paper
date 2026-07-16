from __future__ import annotations

from code2paper.agentic.tools import build_tool_catalog


def stage_tool_guidance_for_decision(stages: list[str]) -> dict[str, dict]:
    catalog = build_tool_catalog()
    return {
        stage: catalog.tool_guidance[stage].model_dump(mode="json")
        for stage in stages
        if stage in catalog.tool_guidance
    }
