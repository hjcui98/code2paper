from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ReadinessCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    passed: bool
    blocking: bool = True
    message: str = ""
    artifact_keys: list[str] = Field(default_factory=list)


class AgenticRunReadinessReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = "agentic-run-readiness-report"
    passed: bool
    blocking_failures: int = 0
    checks: list[ReadinessCheck] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
