from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.decisioning import supported_decision_prompt_hard_rule_nodes, supported_decision_prompt_inputs
from code2paper.agentic.decision_policy import AgenticDecisionPolicy
from code2paper.agentic.graph_catalog import AgenticGraphCatalog, AgenticGraphGate, AgenticGraphNode
from code2paper.agentic.langchain_tools import LangChainStageToolManifest
from code2paper.agentic.llm_decision_provider import supported_llm_decision_nodes
from code2paper.agentic.contract_audit_tool_alignment import (
    graph_stage_tool_alignment_problems,
    langchain_tool_manifest_alignment_problems,
)
from code2paper.agentic.tools import AgenticToolCatalog


class AgenticContractAuditCheck(BaseModel):
    """One consistency check across graph, policy, and tool contracts."""

    model_config = ConfigDict(extra="forbid")

    name: str
    passed: bool
    blocking: bool = True
    message: str = ""
    artifact_keys: list[str] = Field(default_factory=list)


class AgenticContractAudit(BaseModel):
    """Machine-readable audit that graph/policy/tool catalogs agree."""

    model_config = ConfigDict(extra="forbid")

    mode: str = "agentic-contract-audit"
    passed: bool
    blocking_failures: int = 0
    checks: list[AgenticContractAuditCheck] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


def build_agentic_contract_audit(
    *,
    graph_catalog: AgenticGraphCatalog,
    decision_policy: AgenticDecisionPolicy,
    tool_catalog: AgenticToolCatalog,
    langchain_tool_manifest: LangChainStageToolManifest | None = None,
) -> AgenticContractAudit:
    """Audit that static agentic contracts do not drift apart."""

    checks = [
        _check_graph_stage_tool_alignment(graph_catalog, tool_catalog),
        _check_graph_routes_resolve(graph_catalog),
        _check_policy_nodes_resolve(graph_catalog, decision_policy),
        _check_model_decision_schema_coverage(decision_policy),
        _check_policy_prompt_inputs_resolve(decision_policy),
        _check_policy_prompt_hard_rules_resolve(decision_policy),
        _check_policy_routes_match_graph(graph_catalog, decision_policy),
        _check_policy_artifacts_resolve(graph_catalog, decision_policy),
        _check_policy_invariants_are_cataloged(graph_catalog, decision_policy),
    ]
    if langchain_tool_manifest is not None:
        checks.append(_check_langchain_tool_manifest_alignment(tool_catalog, langchain_tool_manifest))
    blocking_failures = sum(1 for check in checks if check.blocking and not check.passed)
    return AgenticContractAudit(
        passed=blocking_failures == 0,
        blocking_failures=blocking_failures,
        checks=checks,
        recommended_actions=_recommended_actions(checks),
    )


def write_agentic_contract_audit(path: str | Path, audit: AgenticContractAudit) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(audit.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def load_agentic_contract_audit(path: str | Path) -> AgenticContractAudit:
    return AgenticContractAudit.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def _check_graph_stage_tool_alignment(
    graph_catalog: AgenticGraphCatalog,
    tool_catalog: AgenticToolCatalog,
) -> AgenticContractAuditCheck:
    problems = graph_stage_tool_alignment_problems(graph_catalog, tool_catalog)
    return AgenticContractAuditCheck(
        name="graph_stage_tool_alignment",
        passed=not problems,
        message="Graph stage nodes match LangChain stage tool contracts." if not problems else "; ".join(problems),
        artifact_keys=["agentic_graph_catalog", "agentic_tool_catalog"],
    )


def _check_langchain_tool_manifest_alignment(
    tool_catalog: AgenticToolCatalog,
    langchain_tool_manifest: LangChainStageToolManifest,
) -> AgenticContractAuditCheck:
    problems = langchain_tool_manifest_alignment_problems(tool_catalog, langchain_tool_manifest)
    return AgenticContractAuditCheck(
        name="langchain_tool_manifest_alignment",
        passed=not problems,
        message="LangChain tool manifest matches stage tool catalog."
        if not problems
        else "; ".join(problems),
        artifact_keys=["agentic_tool_catalog", "agentic_langchain_tool_manifest"],
    )


def _check_graph_routes_resolve(graph_catalog: AgenticGraphCatalog) -> AgenticContractAuditCheck:
    node_names = {node.name for node in graph_catalog.nodes}
    problems: list[str] = []
    for edge in graph_catalog.edges:
        if edge.source not in node_names:
            problems.append(f"edge {edge.source}->{edge.target}: unknown source")
        if edge.target not in node_names and edge.target != "END":
            problems.append(f"edge {edge.source}->{edge.target}: unknown target")
    for route in graph_catalog.conditional_routes:
        if route.source not in node_names:
            problems.append(f"{route.source}: conditional route source is unknown")
        for label, target in route.routes.items():
            if target not in node_names and target != "END":
                problems.append(f"{route.source}.{label}: unknown target {target}")
    return AgenticContractAuditCheck(
        name="graph_routes_resolve",
        passed=not problems,
        message="All graph edges and conditional route targets resolve." if not problems else "; ".join(problems),
        artifact_keys=["agentic_graph_catalog"],
    )


def _check_policy_nodes_resolve(
    graph_catalog: AgenticGraphCatalog,
    decision_policy: AgenticDecisionPolicy,
) -> AgenticContractAuditCheck:
    graph_nodes = {node.name: node for node in graph_catalog.nodes}
    problems: list[str] = []
    for policy in decision_policy.node_policies:
        graph_node = graph_nodes.get(policy.node)
        if graph_node is None:
            problems.append(f"{policy.node}: policy node is not in graph catalog")
            continue
        if policy.model_may_propose and not graph_node.allow_model_decision:
            problems.append(f"{policy.node}: policy allows model proposals but graph node does not")
        if graph_node.allow_model_decision and not policy.model_may_propose and graph_node.kind != "stage":
            problems.append(f"{policy.node}: graph allows model proposals but policy does not")
    return AgenticContractAuditCheck(
        name="policy_nodes_resolve",
        passed=not problems,
        message="Decision policy nodes resolve to graph nodes with matching model permissions."
        if not problems
        else "; ".join(problems),
        artifact_keys=["agentic_decision_policy", "agentic_graph_catalog"],
    )


def _check_policy_routes_match_graph(
    graph_catalog: AgenticGraphCatalog,
    decision_policy: AgenticDecisionPolicy,
) -> AgenticContractAuditCheck:
    route_targets_by_source = {route.source: set(route.routes.values()) for route in graph_catalog.conditional_routes}
    problems: list[str] = []
    for policy in decision_policy.node_policies:
        route_targets = route_targets_by_source.get(policy.node)
        if route_targets is None:
            continue
        allowed = set(policy.allowed_next_nodes)
        forbidden = set(policy.forbidden_next_nodes)
        if allowed and not allowed.issubset(route_targets):
            problems.append(f"{policy.node}: allowed_next_nodes missing from graph routes: " + ", ".join(sorted(allowed - route_targets)))
        if forbidden.intersection(route_targets):
            problems.append(f"{policy.node}: forbidden_next_nodes reachable in graph routes: " + ", ".join(sorted(forbidden & route_targets)))
    return AgenticContractAuditCheck(
        name="policy_routes_match_graph",
        passed=not problems,
        message="Policy route boundaries match graph conditional routes." if not problems else "; ".join(problems),
        artifact_keys=["agentic_decision_policy", "agentic_graph_catalog"],
    )


def _check_model_decision_schema_coverage(decision_policy: AgenticDecisionPolicy) -> AgenticContractAuditCheck:
    supported_nodes = set(supported_llm_decision_nodes())
    missing = [
        policy.node
        for policy in decision_policy.node_policies
        if policy.model_may_propose and policy.node not in supported_nodes
    ]
    return AgenticContractAuditCheck(
        name="model_decision_schema_coverage",
        passed=not missing,
        message="Every model-assisted policy node has a structured LLM proposal schema."
        if not missing
        else "Model-assisted policy nodes lack structured LLM proposal schemas: " + ", ".join(missing),
        artifact_keys=["agentic_decision_policy", "agentic_llm_decision_provider"],
    )


def _check_policy_prompt_inputs_resolve(decision_policy: AgenticDecisionPolicy) -> AgenticContractAuditCheck:
    supported_by_node = supported_decision_prompt_inputs()
    problems: list[str] = []
    for policy in decision_policy.node_policies:
        supported = set(supported_by_node.get(policy.node, ()))
        missing = [input_key for input_key in policy.required_prompt_inputs if input_key not in supported]
        if missing:
            problems.append(f"{policy.node}: required_prompt_inputs not emitted by decision prompt: " + ", ".join(missing))
    message = "Policy-required prompt inputs are emitted by model-assisted decision builders." if not problems else "; ".join(problems)
    return AgenticContractAuditCheck(name="policy_prompt_inputs_resolve", passed=not problems, message=message, artifact_keys=["agentic_decision_policy", "agentic_decision_prompt_contract"])


def _check_policy_prompt_hard_rules_resolve(decision_policy: AgenticDecisionPolicy) -> AgenticContractAuditCheck:
    supported_nodes = set(supported_decision_prompt_hard_rule_nodes())
    missing = [policy.node for policy in decision_policy.node_policies if policy.model_may_propose and policy.node not in supported_nodes]
    message = "Every model-assisted decision prompt includes policy hard rules."
    if missing:
        message = "Model-assisted policy nodes lack decision prompt hard rules: " + ", ".join(missing)
    return AgenticContractAuditCheck(
        name="policy_prompt_hard_rules_resolve",
        passed=not missing,
        message=message,
        artifact_keys=["agentic_decision_policy", "agentic_decision_prompt_contract"],
    )


def _check_policy_artifacts_resolve(
    graph_catalog: AgenticGraphCatalog,
    decision_policy: AgenticDecisionPolicy,
) -> AgenticContractAuditCheck:
    nodes_by_name = {node.name: node for node in graph_catalog.nodes}
    gates_by_node: dict[str, list[AgenticGraphGate]] = {}
    for gate in graph_catalog.evidence_gates:
        gates_by_node.setdefault(gate.node, []).append(gate)
    problems: list[str] = []
    for policy in decision_policy.node_policies:
        node = nodes_by_name.get(policy.node)
        if node is None:
            continue
        available = _node_artifacts(node)
        for gate in gates_by_node.get(policy.node, []):
            available.update(gate.required_artifacts)
        missing_context = [artifact for artifact in policy.required_context_artifacts if artifact not in available]
        missing_gate = [artifact for artifact in policy.required_gate_artifacts if artifact not in available]
        if missing_context:
            problems.append(f"{policy.node}: required_context_artifacts not cataloged: " + ", ".join(missing_context))
        if missing_gate:
            problems.append(f"{policy.node}: required_gate_artifacts not cataloged: " + ", ".join(missing_gate))
    return AgenticContractAuditCheck(
        name="policy_artifacts_resolve",
        passed=not problems,
        message="Policy-required artifacts are cataloged on matching graph nodes or gates."
        if not problems
        else "; ".join(problems),
        artifact_keys=["agentic_decision_policy", "agentic_graph_catalog"],
    )


def _check_policy_invariants_are_cataloged(
    graph_catalog: AgenticGraphCatalog,
    decision_policy: AgenticDecisionPolicy,
) -> AgenticContractAuditCheck:
    cataloged: set[str] = set()
    for node in graph_catalog.nodes:
        cataloged.update(_node_artifacts(node))
    for gate in graph_catalog.evidence_gates:
        cataloged.update(gate.required_artifacts)
    missing = [artifact for artifact in decision_policy.invariant_artifacts if artifact not in cataloged]
    return AgenticContractAuditCheck(
        name="policy_invariants_are_cataloged",
        passed=not missing,
        message="Policy invariant artifacts are represented in graph nodes or gates."
        if not missing
        else "Policy invariant artifacts are missing from graph catalog: " + ", ".join(missing),
        artifact_keys=["agentic_decision_policy", "agentic_graph_catalog"],
    )


def _node_artifacts(node: AgenticGraphNode) -> set[str]:
    return set(node.input_artifacts) | set(node.output_artifacts)


def _recommended_actions(checks: list[AgenticContractAuditCheck]) -> list[str]:
    actions: list[str] = []
    for check in checks:
        if check.passed or not check.blocking:
            continue
        actions.append(f"repair_{check.name}")
    if not actions:
        actions.append("agentic_contracts_are_consistent")
    return actions
