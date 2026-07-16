from __future__ import annotations

from typing import Any

from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.decision_core import DecisionProvider, write_decision_trace
from code2paper.agentic.revision_context import build_revision_decision_context, write_revision_decision_context
from code2paper.agentic.revision_decisioning import revision_decision_trace
from code2paper.agentic.routing import decision_to_agent_decision, write_router_decision
from code2paper.core.output_names import artifact_dir


def revision_router_node(*, decision_provider: DecisionProvider | None = None):
    def _run(raw_state: dict[str, Any]) -> dict[str, Any]:
        state = AgenticRunState.model_validate(raw_state)
        artifacts = dict(state.artifacts)
        # Validators overwrite their reports on every revision. Rebuild this
        # derived context on every visit so the router never acts on a stale
        # validation result from an earlier loop.
        revision_context = build_revision_decision_context(state)
        context_path = artifact_dir(state.method_root, "10_run") / "revision_decision_context.json"
        write_revision_decision_context(context_path, revision_context)
        artifacts["revision_decision_context"] = str(context_path)
        state = state.model_copy(update={"artifacts": artifacts})
        decision, trace = revision_decision_trace(
            state,
            revision_context=revision_context,
            decision_provider=decision_provider,
        )
        decision_path = artifact_dir(state.method_root, "10_run") / "revision_router_decision.json"
        write_router_decision(decision_path, decision)
        trace_path = artifact_dir(state.method_root, "10_run") / "revision_router_decision_trace.json"
        write_decision_trace(trace_path, trace)
        artifacts = dict(state.artifacts)
        artifacts["revision_router_decision"] = str(decision_path)
        artifacts["revision_router_decision_trace"] = str(trace_path)
        updated = state.model_copy(
            update={
                "artifacts": artifacts,
                "decisions": [*state.decisions, decision_to_agent_decision("revision_router", decision)],
                "next_node": decision.recommended_next,
            }
        )
        if decision.recommended_next in {"analysis", "authoring"}:
            updated = updated.increment_loop("revision")
        return updated.model_dump(mode="json")

    return _run
