from __future__ import annotations

from typing import Any

from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.readiness_io import artifact_exists, artifact_json, dedupe, string_list
from code2paper.agentic.readiness_models import ReadinessCheck
from code2paper.agentic.readiness_plan_signatures import decision_trace_plan_mismatch


def check_decision_traces(state: AgenticRunState) -> ReadinessCheck:
    problems: list[str] = []
    artifact_keys: list[str] = []
    required_prompt_inputs = _policy_required_prompt_inputs(state)
    required_hard_rules = _policy_hard_rules(state)
    _check_router_trace(
        state,
        problems,
        artifact_keys,
        node="coverage_critic",
        decision_key="coverage_critic_decision",
        trace_key="coverage_critic_decision_trace",
        missing_message="coverage critic decision has no readable decision trace",
        required_prompt_inputs=required_prompt_inputs,
        required_hard_rules=required_hard_rules,
    )
    coverage_trace = artifact_json(state, "coverage_critic_decision_trace")
    if coverage_trace:
        attention_problem = _coverage_trace_attention_problem(
            trace=coverage_trace,
            rescan_report=artifact_json(state, "retrieval_rescan_report"),
        )
        if attention_problem:
            problems.append(attention_problem)
    _check_evidence_sufficiency_trace(state, problems, artifact_keys, required_prompt_inputs, required_hard_rules)
    _check_analysis_repair_trace(state, problems, artifact_keys, required_prompt_inputs, required_hard_rules)
    _check_revision_trace(state, problems, artifact_keys, required_prompt_inputs, required_hard_rules)
    _check_plan_trace(
        state,
        problems,
        artifact_keys,
        plan_key="authoring_plan",
        trace_key="authoring_plan_decision_trace",
        label="authoring plan",
        expected_node="authoring_planner",
        signature_kind="authoring_plan",
        required_prompt_inputs=required_prompt_inputs,
        required_hard_rules=required_hard_rules,
    )
    _check_plan_trace(
        state,
        problems,
        artifact_keys,
        plan_key="figure_plan",
        trace_key="figure_plan_decision_trace",
        label="figure plan",
        expected_node="figure_planner",
        signature_kind="figure_plan",
        required_prompt_inputs=required_prompt_inputs,
        required_hard_rules=required_hard_rules,
    )
    if not artifact_keys:
        return ReadinessCheck(
            name="agentic_decision_traces",
            passed=True,
            blocking=False,
            message="No model-merge decision artifacts were produced; decision traces are not required.",
        )
    return ReadinessCheck(
        name="agentic_decision_traces",
        passed=not problems,
        message="Agentic router decisions have auditable traces and contexts." if not problems else "; ".join(problems),
        artifact_keys=dedupe(artifact_keys),
    )


def _check_evidence_sufficiency_trace(
    state: AgenticRunState,
    problems: list[str],
    artifact_keys: list[str],
    required_prompt_inputs: dict[str, list[str]],
    required_hard_rules: list[str],
) -> None:
    _check_router_trace(
        state,
        problems,
        artifact_keys,
        node="evidence_sufficiency",
        decision_key="evidence_sufficiency_decision",
        trace_key="evidence_sufficiency_decision_trace",
        missing_message="evidence sufficiency decision has no readable decision trace",
        required_prompt_inputs=required_prompt_inputs,
        required_hard_rules=required_hard_rules,
        extra_artifact_keys=["evidence_sufficiency_report"],
    )
    if artifact_exists(state, "evidence_sufficiency_decision") and not artifact_json(state, "evidence_sufficiency_report"):
        problems.append("evidence sufficiency decision has no readable sufficiency report")


def _check_analysis_repair_trace(
    state: AgenticRunState,
    problems: list[str],
    artifact_keys: list[str],
    required_prompt_inputs: dict[str, list[str]],
    required_hard_rules: list[str],
) -> None:
    if not artifact_exists(state, "evidence_repair_focus"):
        return
    artifact_keys.extend(["evidence_repair_focus", "analysis_repair_tasks", "analysis_repair_router_decision", "analysis_repair_router_decision_trace"])
    if not artifact_json(state, "evidence_repair_focus"):
        problems.append("evidence repair focus is not readable")
    if not artifact_exists(state, "analysis_repair_tasks"):
        return
    if not artifact_json(state, "analysis_repair_router_decision"):
        problems.append("analysis repair tasks have no readable router decision")
    trace = artifact_json(state, "analysis_repair_router_decision_trace")
    if not trace:
        problems.append("analysis repair tasks have no readable router decision trace")
        return
    _append_prompt_problems(trace, problems, required_prompt_inputs, required_hard_rules)


def _check_revision_trace(
    state: AgenticRunState,
    problems: list[str],
    artifact_keys: list[str],
    required_prompt_inputs: dict[str, list[str]],
    required_hard_rules: list[str],
) -> None:
    _check_router_trace(
        state,
        problems,
        artifact_keys,
        node="revision_router",
        decision_key="revision_router_decision",
        trace_key="revision_router_decision_trace",
        missing_message="revision router decision has no readable decision trace",
        required_prompt_inputs=required_prompt_inputs,
        required_hard_rules=required_hard_rules,
        extra_artifact_keys=["revision_decision_context"],
    )
    if artifact_exists(state, "revision_router_decision") and not artifact_json(state, "revision_decision_context"):
        problems.append("revision router decision has no readable validator-aware context")


def _check_router_trace(
    state: AgenticRunState,
    problems: list[str],
    artifact_keys: list[str],
    *,
    node: str,
    decision_key: str,
    trace_key: str,
    missing_message: str,
    required_prompt_inputs: dict[str, list[str]],
    required_hard_rules: list[str],
    extra_artifact_keys: list[str] | None = None,
) -> None:
    if not artifact_exists(state, decision_key):
        return
    artifact_keys.extend([decision_key, trace_key, *(extra_artifact_keys or [])])
    trace = artifact_json(state, trace_key)
    if not trace:
        problems.append(missing_message)
        return
    _append_prompt_problems(trace, problems, required_prompt_inputs, required_hard_rules)


def _check_plan_trace(
    state: AgenticRunState,
    problems: list[str],
    artifact_keys: list[str],
    *,
    plan_key: str,
    trace_key: str,
    label: str,
    expected_node: str,
    signature_kind: str,
    required_prompt_inputs: dict[str, list[str]],
    required_hard_rules: list[str],
) -> None:
    if not artifact_exists(state, plan_key):
        return
    artifact_keys.extend([plan_key, trace_key])
    plan = artifact_json(state, plan_key)
    trace = artifact_json(state, trace_key)
    if not trace:
        problems.append(f"{label} has no readable model/fallback decision trace")
        return
    _append_prompt_problems(trace, problems, required_prompt_inputs, required_hard_rules)
    mismatch = decision_trace_plan_mismatch(trace=trace, plan=plan, expected_node=expected_node, signature_kind=signature_kind)
    if mismatch:
        problems.append(mismatch)


def _append_prompt_problems(
    trace: dict[str, Any],
    problems: list[str],
    required_by_node: dict[str, list[str]],
    required_hard_rules: list[str],
) -> None:
    prompt_input_problem = _decision_trace_prompt_input_problem(trace, required_by_node)
    if prompt_input_problem:
        problems.append(prompt_input_problem)
    hard_rule_problem = _decision_trace_hard_rule_problem(trace, required_hard_rules)
    if hard_rule_problem:
        problems.append(hard_rule_problem)


def _policy_required_prompt_inputs(state: AgenticRunState) -> dict[str, list[str]]:
    policy = artifact_json(state, "agentic_decision_policy")
    policies = policy.get("node_policies") if isinstance(policy.get("node_policies"), list) else []
    required_by_node: dict[str, list[str]] = {}
    for node_policy in policies:
        if not isinstance(node_policy, dict):
            continue
        node = str(node_policy.get("node") or "").strip()
        required = string_list(node_policy.get("required_prompt_inputs"))
        if node and required:
            required_by_node[node] = required
    return required_by_node


def _policy_hard_rules(state: AgenticRunState) -> list[str]:
    policy = artifact_json(state, "agentic_decision_policy")
    rules = policy.get("hard_rules") if isinstance(policy.get("hard_rules"), list) else []
    return [str(rule.get("description") or "").strip() for rule in rules if isinstance(rule, dict) and str(rule.get("description") or "").strip()]


def _decision_trace_prompt_input_problem(trace: dict[str, Any], required_by_node: dict[str, list[str]]) -> str:
    node = str(trace.get("node") or "").strip()
    required = required_by_node.get(node, [])
    if not required:
        return ""
    prompt = trace.get("prompt") if isinstance(trace.get("prompt"), dict) else {}
    inputs = prompt.get("inputs") if isinstance(prompt.get("inputs"), dict) else {}
    missing = [input_key for input_key in required if input_key not in inputs]
    if missing:
        return f"{node} decision trace missing policy prompt inputs: " + ", ".join(missing)
    return ""


def _decision_trace_hard_rule_problem(trace: dict[str, Any], required_hard_rules: list[str]) -> str:
    if not required_hard_rules:
        return ""
    node = str(trace.get("node") or "").strip()
    prompt = trace.get("prompt") if isinstance(trace.get("prompt"), dict) else {}
    prompt_rules = string_list(prompt.get("hard_rules"))
    missing = [rule for rule in required_hard_rules if rule not in prompt_rules]
    if missing:
        return f"{node} decision trace missing policy hard rules: " + "; ".join(missing)
    return ""


def _coverage_trace_attention_problem(*, trace: dict[str, Any], rescan_report: dict[str, Any]) -> str:
    high_priority_missing = int(rescan_report.get("high_priority_missing_items") or 0) if rescan_report else 0
    if high_priority_missing <= 0:
        return ""
    prompt = trace.get("prompt") if isinstance(trace.get("prompt"), dict) else {}
    inputs = prompt.get("inputs") if isinstance(prompt.get("inputs"), dict) else {}
    attention = inputs.get("retrieval_rescan_attention") if isinstance(inputs.get("retrieval_rescan_attention"), dict) else {}
    attention_count = int(attention.get("high_priority_missing_items") or 0) if attention else 0
    items = attention.get("missing_high_priority_items") if isinstance(attention.get("missing_high_priority_items"), list) else []
    if attention_count != high_priority_missing or not items:
        return "coverage critic trace does not expose high-priority rescan attention"
    return ""

