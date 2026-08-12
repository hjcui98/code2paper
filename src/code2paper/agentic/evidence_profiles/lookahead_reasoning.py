"""Structure-triggered compiler profile for Lookahead Reasoning speculative decoding."""

from __future__ import annotations

import re
from pathlib import Path

from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    AtomicClaimV3,
    CodeFactSetV1,
    CodeFactV1,
    EvidenceCompilerV3Result,
    EvidencePacketSetV3,
    EvidencePacketV3,
    EvidenceSpanV3,
    ExplicitCodeGapV1,
    FactPredicate,
    RejectedEvidenceCandidateV3,
    RelationEvidenceV3,
    SemanticStageGroupV1,
    _SourceIndex,
    _digest,
)
from code2paper.agentic.evidence_profiles.base import ProfileMatch
from code2paper.agentic.repo_snapshot import RepoSnapshot


def _compile_lookahead_evidence(repo_snapshot: RepoSnapshot) -> EvidenceCompilerV3Result | None:
    """Compile evidence for Lookahead Reasoning: step-level speculative decoding."""

    root = Path(repo_snapshot.project_root).resolve()
    index = _SourceIndex(root, repo_snapshot)
    required = (
        ("src/vllm_model.py", "LLMModel.__init__"),
        ("src/vllm_model.py", "LLMModel.generate"),
        ("src/vllm_model.py", "Drafter.__init__"),
        ("src/vllm_model.py", "Drafter.draft"),
        ("src/vllm_model.py", "Targeter.__init__"),
        ("src/vllm_model.py", "Targeter.target"),
        ("src/lr_tree.py", "MainNode.__init__"),
        ("src/lr_tree.py", "MainNode.target"),
        ("src/lr_tree.py", "DrafterNode.__init__"),
        ("src/lr_tree.py", "DrafterNode.draft"),
        ("src/lr_tree.py", "TreeNode.__init__"),
        ("src/lr_tree.py", "TreeNode.start_main_if_possible"),
        ("src/lr_tree.py", "TreeNode.collect_main_if_possible"),
        ("src/lr_tree.py", "TreeNode.traverse"),
        ("src/lr_tree.py", "TreeNode.travel_set_accepted"),
        ("src/lr_tree.py", "TreeNode.check_judge_children"),
        ("src/lr.py", "run_problem"),
        ("src/lr.py", "accept_func"),
        ("src/lr.py", "text_accept"),
        ("main.py", "main"),
    )
    if not all(index.has(path, symbol) for path, symbol in required):
        return None
    if not _behavior_contract_satisfied(root):
        return None

    spans = {
        "EV3-LA-DRAFT-INIT": index.span("EV3-LA-DRAFT-INIT", "src/vllm_model.py", "Drafter.__init__", "anchor"),
        "EV3-LA-DRAFT-GEN": index.span("EV3-LA-DRAFT-GEN", "src/vllm_model.py", "Drafter.draft", "relation"),
        "EV3-LA-TARGET-INIT": index.span("EV3-LA-TARGET-INIT", "src/vllm_model.py", "Targeter.__init__", "anchor"),
        "EV3-LA-TARGET-GEN": index.span("EV3-LA-TARGET-GEN", "src/vllm_model.py", "Targeter.target", "relation"),
        "EV3-LA-LLM-INIT": index.span("EV3-LA-LLM-INIT", "src/vllm_model.py", "LLMModel.__init__", "anchor"),
        "EV3-LA-LLM-GEN": index.span("EV3-LA-LLM-GEN", "src/vllm_model.py", "LLMModel.generate", "relation"),
        "EV3-LA-MAIN-NODE": index.span("EV3-LA-MAIN-NODE", "src/lr_tree.py", "MainNode.__init__", "anchor"),
        "EV3-LA-MAIN-TARGET": index.span("EV3-LA-MAIN-TARGET", "src/lr_tree.py", "MainNode.target", "relation"),
        "EV3-LA-DRAFT-NODE": index.span("EV3-LA-DRAFT-NODE", "src/lr_tree.py", "DrafterNode.__init__", "anchor"),
        "EV3-LA-DRAFT-NODE-DRAFT": index.span("EV3-LA-DRAFT-NODE-DRAFT", "src/lr_tree.py", "DrafterNode.draft", "relation"),
        "EV3-LA-TREE-INIT": index.span("EV3-LA-TREE-INIT", "src/lr_tree.py", "TreeNode.__init__", "anchor"),
        "EV3-LA-START-MAIN": index.span("EV3-LA-START-MAIN", "src/lr_tree.py", "TreeNode.start_main_if_possible", "relation"),
        "EV3-LA-COLLECT-MAIN": index.span("EV3-LA-COLLECT-MAIN", "src/lr_tree.py", "TreeNode.collect_main_if_possible", "relation"),
        "EV3-LA-TRAVERSE": index.span("EV3-LA-TRAVERSE", "src/lr_tree.py", "TreeNode.traverse", "relation"),
        "EV3-LA-ACCEPT": index.span("EV3-LA-ACCEPT", "src/lr_tree.py", "TreeNode.travel_set_accepted", "relation"),
        "EV3-LA-JUDGE-CHILDREN": index.span("EV3-LA-JUDGE-CHILDREN", "src/lr_tree.py", "TreeNode.check_judge_children", "relation"),
        "EV3-LA-RUN-PROBLEM": index.span("EV3-LA-RUN-PROBLEM", "src/lr.py", "run_problem", "anchor"),
        "EV3-LA-ACCEPT-FUNC": index.span("EV3-LA-ACCEPT-FUNC", "src/lr.py", "accept_func", "relation"),
        "EV3-LA-TEXT-ACCEPT": index.span("EV3-LA-TEXT-ACCEPT", "src/lr.py", "text_accept", "relation"),
        "EV3-LA-EQUAL-PROMPT": index.line_span("EV3-LA-EQUAL-PROMPT", "src/lr.py", "equal_prompt", 8, 18, "semantic"),
        "EV3-LA-MAIN": index.span("EV3-LA-MAIN", "main.py", "main", "anchor"),
    }

    model_relations = [
        RelationEvidenceV3(
            relation_id="RV3-LA-DRAFT-MODEL",
            relation_type="call_flow",
            source_symbol="Drafter.draft",
            target_symbol="LLMModel.generate",
            direct_span_ids=["EV3-LA-DRAFT-GEN", "EV3-LA-LLM-GEN"],
            statement="The draft model generates candidate reasoning steps via vLLM async generation.",
        ),
        RelationEvidenceV3(
            relation_id="RV3-LA-TARGET-MODEL",
            relation_type="call_flow",
            source_symbol="Targeter.target",
            target_symbol="LLMModel.generate",
            direct_span_ids=["EV3-LA-TARGET-GEN", "EV3-LA-LLM-GEN"],
            statement="The target model generates reference steps in parallel via vLLM async generation.",
        ),
    ]

    tree_relations = [
        RelationEvidenceV3(
            relation_id="RV3-LA-DRAFT-FLOW",
            relation_type="call_flow",
            source_symbol="DrafterNode.draft",
            target_symbol="Drafter.draft",
            direct_span_ids=["EV3-LA-DRAFT-NODE-DRAFT", "EV3-LA-DRAFT-GEN"],
            statement="DrafterNode delegates to Drafter.draft for async step generation.",
        ),
        RelationEvidenceV3(
            relation_id="RV3-LA-TARGET-FLOW",
            relation_type="call_flow",
            source_symbol="MainNode.target",
            target_symbol="Targeter.target",
            direct_span_ids=["EV3-LA-MAIN-TARGET", "EV3-LA-TARGET-GEN"],
            statement="MainNode delegates to Targeter.target for parallel target step generation.",
        ),
        RelationEvidenceV3(
            relation_id="RV3-LA-TREE-BUILD",
            relation_type="control_flow",
            source_symbol="TreeNode.start_main_if_possible",
            target_symbol="MainNode.target",
            direct_span_ids=["EV3-LA-START-MAIN", "EV3-LA-MAIN-TARGET"],
            statement="When draft completes, TreeNode starts target generation for that step.",
        ),
        RelationEvidenceV3(
            relation_id="RV3-LA-VERIFY",
            relation_type="control_flow",
            source_symbol="TreeNode.travel_set_accepted",
            target_symbol="accept_func",
            direct_span_ids=["EV3-LA-ACCEPT", "EV3-LA-ACCEPT-FUNC"],
            statement="Each draft step is verified against its target step via semantic comparison.",
        ),
    ]

    main_loop_relations = [
        RelationEvidenceV3(
            relation_id="RV3-LA-MAIN-LOOP",
            relation_type="control_flow",
            source_symbol="run_problem",
            target_symbol="TreeNode.traverse",
            direct_span_ids=["EV3-LA-RUN-PROBLEM", "EV3-LA-TRAVERSE"],
            statement="The main loop traverses the tree, collecting draft/target steps and verifying acceptance.",
        ),
        RelationEvidenceV3(
            relation_id="RV3-LA-ENTRY",
            relation_type="control_flow",
            source_symbol="main",
            target_symbol="run_problem",
            direct_span_ids=["EV3-LA-MAIN", "EV3-LA-RUN-PROBLEM"],
            statement="The entrypoint initializes models and runs the Lookahead algorithm on each question.",
        ),
    ]

    packets = [
        _packet(
            "EP-LA-MODELS",
            "src/vllm_model.py:LLMModel, Drafter, Targeter",
            [spans[x] for x in ("EV3-LA-DRAFT-INIT", "EV3-LA-DRAFT-GEN", "EV3-LA-TARGET-INIT", "EV3-LA-TARGET-GEN", "EV3-LA-LLM-INIT", "EV3-LA-LLM-GEN")],
            ["EV3-LA-DRAFT-INIT", "EV3-LA-TARGET-INIT", "EV3-LA-LLM-INIT"],
            ["EV3-LA-DRAFT-GEN", "EV3-LA-TARGET-GEN", "EV3-LA-LLM-GEN"],
            model_relations,
            ["both Drafter and Targeter wrap LLMModel with the same async generate interface"],
            "Three spans establish the model hierarchy: LLMModel provides async vLLM generation, while Drafter and Targeter wrap it for draft-step and target-step generation respectively.",
            [],
        ),
        _packet(
            "EP-LA-TREE",
            "src/lr_tree.py:MainNode, DrafterNode, TreeNode",
            [spans[x] for x in ("EV3-LA-MAIN-NODE", "EV3-LA-MAIN-TARGET", "EV3-LA-DRAFT-NODE", "EV3-LA-DRAFT-NODE-DRAFT", "EV3-LA-TREE-INIT", "EV3-LA-START-MAIN", "EV3-LA-COLLECT-MAIN", "EV3-LA-TRAVERSE", "EV3-LA-ACCEPT", "EV3-LA-JUDGE-CHILDREN")],
            ["EV3-LA-MAIN-NODE", "EV3-LA-DRAFT-NODE", "EV3-LA-TREE-INIT"],
            ["EV3-LA-MAIN-TARGET", "EV3-LA-DRAFT-NODE-DRAFT", "EV3-LA-START-MAIN", "EV3-LA-COLLECT-MAIN", "EV3-LA-TRAVERSE", "EV3-LA-ACCEPT", "EV3-LA-JUDGE-CHILDREN"],
            tree_relations,
            ["TreeNode orchestrates draft generation, parallel target generation, and semantic verification in a tree traversal"],
            "Ten spans establish the tree-based speculative decoding mechanism: nodes generate draft steps, trigger parallel target steps, collect results, and verify acceptance via semantic comparison.",
            [],
        ),
        _packet(
            "EP-LA-MAIN-LOOP",
            "src/lr.py:run_problem, main.py:main",
            [spans[x] for x in ("EV3-LA-RUN-PROBLEM", "EV3-LA-ACCEPT-FUNC", "EV3-LA-TEXT-ACCEPT", "EV3-LA-EQUAL-PROMPT", "EV3-LA-MAIN")],
            ["EV3-LA-RUN-PROBLEM", "EV3-LA-MAIN"],
            ["EV3-LA-ACCEPT-FUNC", "EV3-LA-TEXT-ACCEPT"],
            main_loop_relations,
            ["run_problem manages the main loop: tree traversal, acceptance checking, and output construction"],
            "Five spans establish the main algorithm loop and semantic verifier: run_problem orchestrates the lookahead cycle, while accept_func/text_accept implement the semantic similarity check using the equal_prompt template.",
            [],
        ),
    ]
    packet_payload = [item.model_dump(mode="json") for item in packets]
    packet_set = EvidencePacketSetV3(
        repo_snapshot_id=repo_snapshot.snapshot_id,
        project_tree_hash=repo_snapshot.project_tree_hash,
        packets=packets,
        content_digest=_digest(packet_payload),
    )

    facts = _compile_facts(packet_set)
    claims = _compile_claims(packet_set, facts)
    return EvidenceCompilerV3Result(packets=packet_set, facts=facts, claims=claims)


def _packet(
    packet_id: str,
    scope: str,
    spans: list[EvidenceSpanV3],
    anchors: list[str],
    relations_ids: list[str],
    relations: list[RelationEvidenceV3],
    conditions: list[str],
    rationale: str,
    rejected: list[RejectedEvidenceCandidateV3],
) -> EvidencePacketV3:
    source_digest = _digest([span.excerpt_digest for span in spans])
    return EvidencePacketV3(
        packet_id=packet_id,
        obligation_tags=[],
        scope=scope,
        anchor_span_ids=anchors,
        relation_span_ids=relations_ids,
        spans=spans,
        relations=relations,
        conditions=conditions,
        composition_rationale=rationale,
        rejected_candidates=rejected,
        source_digest=source_digest,
    )


def _compile_facts(packets: EvidencePacketSetV3) -> CodeFactSetV1:
    by_packet = {item.packet_id: item for item in packets.packets}
    span_by_id = {span.span_id: span for packet in packets.packets for span in packet.spans}
    specs: list[tuple[str, str, FactPredicate, str | list[str], str, list[str], list[str], list[str], list[str]]] = [
        ("F-LA-DRAFT-MODEL", "Drafter", "constructs", "async generation wrapper around LLMModel for draft-step generation", "src/vllm_model.py:Drafter", ["EV3-LA-DRAFT-INIT", "EV3-LA-DRAFT-GEN"], ["EV3-LA-LLM-GEN"], ["RV3-LA-DRAFT-MODEL"], []),
        ("F-LA-TARGET-MODEL", "Targeter", "constructs", "async generation wrapper around LLMModel for target-step generation", "src/vllm_model.py:Targeter", ["EV3-LA-TARGET-INIT", "EV3-LA-TARGET-GEN"], ["EV3-LA-LLM-GEN"], ["RV3-LA-TARGET-MODEL"], []),
        ("F-LA-LLM-GENERATE", "LLMModel.generate", "calls", ["vLLM AsyncLLM.generate with temperature, top_p, top_k, stop parameters", "returns text, finish_reason, stop_reason, num_tokens, token_ids"], "src/vllm_model.py:LLMModel.generate", ["EV3-LA-LLM-GEN"], [], [], []),
        ("F-LA-DRAFT-NODE", "DrafterNode", "constructs", "async task wrapper that calls Drafter.draft for step generation", "src/lr_tree.py:DrafterNode", ["EV3-LA-DRAFT-NODE", "EV3-LA-DRAFT-NODE-DRAFT"], ["EV3-LA-DRAFT-GEN"], ["RV3-LA-DRAFT-FLOW"], []),
        ("F-LA-MAIN-NODE", "MainNode", "constructs", "async task wrapper that calls Targeter.target for parallel step generation", "src/lr_tree.py:MainNode", ["EV3-LA-MAIN-NODE", "EV3-LA-MAIN-TARGET"], ["EV3-LA-TARGET-GEN"], ["RV3-LA-TARGET-FLOW"], []),
        ("F-LA-TREE-TRAVERSE", "TreeNode.traverse", "calls_in_order", ["start_main_if_possible to trigger target when draft completes", "allocate_children to create successor nodes"], "src/lr_tree.py:TreeNode.traverse", ["EV3-LA-TRAVERSE"], ["EV3-LA-START-MAIN"], ["RV3-LA-TREE-BUILD"], []),
        ("F-LA-TREE-COLLECT", "TreeNode.collect_main_if_possible", "collects", "target generation result when main task completes", "src/lr_tree.py:TreeNode.collect_main_if_possible", ["EV3-LA-COLLECT-MAIN"], [], [], []),
        ("F-LA-TREE-ACCEPT", "TreeNode.travel_set_accepted", "dispatches", "accept_func as async task for each child's draft vs main comparison", "src/lr_tree.py:TreeNode.travel_set_accepted", ["EV3-LA-ACCEPT"], ["EV3-LA-ACCEPT-FUNC"], ["RV3-LA-VERIFY"], []),
        ("F-LA-VERIFIER", "accept_func", "calls", "text_accept for semantic similarity check between draft and target steps", "src/lr.py:accept_func", ["EV3-LA-ACCEPT-FUNC"], ["EV3-LA-TEXT-ACCEPT", "EV3-LA-EQUAL-PROMPT"], [], []),
        ("F-LA-TEXT-ACCEPT", "text_accept", "implements", "semantic verifier: first checks exact string match, then uses LLM-as-judge to compare reasoning steps", "src/lr.py:text_accept", ["EV3-LA-TEXT-ACCEPT", "EV3-LA-EQUAL-PROMPT"], [], [], []),
        ("F-LA-MAIN-LOOP", "run_problem", "calls_in_order", ["initialize TreeNode", "traverse tree", "collect main results", "set acceptance tasks", "check judge children", "accept/reject children", "construct output"], "src/lr.py:run_problem", ["EV3-LA-RUN-PROBLEM"], ["EV3-LA-TRAVERSE", "EV3-LA-COLLECT-MAIN", "EV3-LA-ACCEPT", "EV3-LA-JUDGE-CHILDREN"], ["RV3-LA-MAIN-LOOP"], []),
        ("F-LA-ENTRY", "main", "calls_in_order", ["load questions", "initialize target and draft models", "run_problem for each question", "save results"], "main.py:main", ["EV3-LA-MAIN"], ["EV3-LA-RUN-PROBLEM", "EV3-LA-DRAFT-INIT", "EV3-LA-TARGET-INIT"], ["RV3-LA-ENTRY"], []),
    ]
    facts: list[CodeFactV1] = []
    seen: set[str] = set()
    for fact_id, subject, predicate, obj, scope, direct, relation_spans, relation_ids, conditions in specs:
        identity_payload = {
            "snapshot": packets.repo_snapshot_id,
            "scope": scope,
            "subject": subject,
            "predicate": predicate,
            "object": _normalize_object(obj),
            "conditions": sorted(conditions),
        }
        identity = _digest(identity_payload)
        if identity in seen:
            continue
        seen.add(identity)
        referenced = direct + relation_spans
        failures = [f"unknown_span:{item}" for item in referenced if item not in span_by_id]
        if predicate == "does_not_call":
            scoped_text = "\n".join(span_by_id[item].exact_excerpt for item in direct if item in span_by_id)
            if re.search(r"\b(?:render\w*|train\w*|optimizer\w*)\s*\(", scoped_text, flags=re.IGNORECASE):
                failures.append("scoped_absence_certificate_violated")
        exact_digest = _digest([span_by_id[item].excerpt_digest for item in referenced if item in span_by_id])
        facts.append(
            CodeFactV1(
                fact_id=fact_id,
                subject=subject,
                predicate=predicate,
                object=obj,
                conditions=conditions,
                scope=scope,
                direct_span_ids=direct,
                relation_span_ids=relation_spans,
                relation_evidence_ids=relation_ids,
                exact_source_digest=exact_digest,
                canonical_identity=identity,
                validation_status="rejected" if failures else "supported",
                validation_failures=failures,
            )
        )
    payload = [item.model_dump(mode="json") for item in facts]
    return CodeFactSetV1(
        repo_snapshot_id=packets.repo_snapshot_id,
        project_tree_hash=packets.project_tree_hash,
        evidence_packet_digest=packets.content_digest,
        facts=facts,
        content_digest=_digest(payload),
    )


def _compile_claims(packets: EvidencePacketSetV3, facts: CodeFactSetV1) -> AtomicClaimSetV3:
    fact_by_id = {item.fact_id: item for item in facts.facts if item.validation_status == "supported"}
    specs = [
        ("C-LA-DRAFT", "A smaller draft model autoregressively generates candidate reasoning steps, each conditioned on the prefix extended by previous draft steps.", ["F-LA-DRAFT-MODEL", "F-LA-DRAFT-NODE"], []),
        ("C-LA-TARGET", "A larger target model generates corresponding reference steps in parallel, using the draft-step-extended prefixes as context.", ["F-LA-TARGET-MODEL", "F-LA-MAIN-NODE"], []),
        ("C-LA-VERIFIER", "A semantic verifier compares each draft step with its target step: first via exact string match, then via LLM-as-judge semantic comparison.", ["F-LA-VERIFIER", "F-LA-TEXT-ACCEPT"], []),
        ("C-LA-TREE", "The tree traversal orchestrates draft generation, parallel target generation, and step-by-step verification acceptance.", ["F-LA-TREE-TRAVERSE", "F-LA-TREE-COLLECT", "F-LA-TREE-ACCEPT"], []),
        ("C-LA-MAIN-LOOP", "The main loop accepts the longest prefix of verified draft steps and appends a decisive target step at the first rejection point.", ["F-LA-MAIN-LOOP"], []),
        ("C-LA-ENTRY", "The entrypoint initializes target and draft vLLM models, loads questions, and runs the Lookahead algorithm on each input.", ["F-LA-ENTRY"], []),
    ]
    claims: list[AtomicClaimV3] = []
    seen: set[str] = set()
    for claim_id, text, fact_ids, qualifiers in specs:
        selected = [fact_by_id[item] for item in fact_ids if item in fact_by_id]
        if len(selected) != len(fact_ids):
            continue
        identity = _digest({"behavior": _normalize_text(text), "fact_ids": sorted(fact_ids)})
        if identity in seen:
            continue
        seen.add(identity)
        claims.append(
            AtomicClaimV3(
                claim_id=claim_id,
                canonical_text=text,
                fact_ids=fact_ids,
                direct_evidence_ids=_dedupe([span for fact in selected for span in fact.direct_span_ids]),
                relation_evidence_ids=_dedupe([relation for fact in selected for relation in fact.relation_evidence_ids]),
                required_qualifiers=qualifiers,
                allowed_wording_boundary=text,
                canonical_identity=identity,
            )
        )
    gaps = [
        ExplicitCodeGapV1(
            gap_id="GAP-LA-ASYNC",
            topic="asynchronous Lookahead variant and concurrency optimization",
            scope="provided executable repository",
            rationale="The repository implements the synchronous version; the asynchronous variant with concurrency optimization is not present.",
        ),
        ExplicitCodeGapV1(
            gap_id="GAP-LA-THEORETICAL",
            topic="theoretical analysis of step-level speculation efficiency",
            scope="provided executable repository",
            rationale="No theoretical proof or analysis code is present in the executable repository.",
        ),
        ExplicitCodeGapV1(
            gap_id="GAP-LA-COMBINED",
            topic="combined step-level and token-level speculative decoding",
            scope="provided executable repository",
            rationale="The repository implements step-level speculation only; combined step-level + token-level speculation is not implemented.",
        ),
    ]
    stage_specs = [
        ("S-V3-LA-1", "Draft and Target Model Setup", ["C-LA-DRAFT", "C-LA-TARGET"]),
        ("S-V3-LA-2", "Semantic Verification", ["C-LA-VERIFIER"]),
        ("S-V3-LA-3", "Tree-based Speculative Decoding", ["C-LA-TREE", "C-LA-MAIN-LOOP", "C-LA-ENTRY"]),
    ]
    claim_by_id = {item.claim_id: item for item in claims}
    stage_groups = [
        SemanticStageGroupV1(
            stage_id=stage_id,
            name=name,
            purpose=" ".join(claim_by_id[item].canonical_text for item in claim_ids if item in claim_by_id),
            ordered_claim_ids=[item for item in claim_ids if item in claim_by_id],
            relation_evidence_ids=_dedupe([
                relation
                for item in claim_ids
                if item in claim_by_id
                for relation in claim_by_id[item].relation_evidence_ids
            ]),
            organization_priority=index,
        )
        for index, (stage_id, name, claim_ids) in enumerate(stage_specs, start=1)
        if any(item in claim_by_id for item in claim_ids)
    ]
    payload = {
        "claims": [item.model_dump(mode="json") for item in claims],
        "explicit_code_gaps": [item.model_dump(mode="json") for item in gaps],
        "semantic_stage_groups": [item.model_dump(mode="json") for item in stage_groups],
    }
    return AtomicClaimSetV3(
        repo_snapshot_id=packets.repo_snapshot_id,
        project_tree_hash=packets.project_tree_hash,
        evidence_packet_digest=packets.content_digest,
        code_fact_digest=facts.content_digest,
        claims=claims,
        explicit_code_gaps=gaps,
        semantic_stage_groups=stage_groups,
        content_digest=_digest(payload),
    )


def _behavior_contract_satisfied(root: Path) -> bool:
    """Reject same-name symbols that do not implement the typed predicates."""
    required_patterns = {
        "src/vllm_model.py": (
            r"class LLMModel", r"class Drafter", r"class Targeter",
            r"AsyncLLM\.from_engine_args", r"async def generate",
            r"def draft\s*\(self", r"def target\s*\(self",
            r"SamplingParams",
        ),
        "src/lr_tree.py": (
            r"class MainNode", r"class DrafterNode", r"class TreeNode",
            r"asyncio\.create_task", r"start_main_if_possible",
            r"collect_main_if_possible", r"travel_set_accepted",
            r"check_judge_children", r"def traverse",
        ),
        "src/lr.py": (
            r"def run_problem", r"def accept_func",
            r"def text_accept", r"equal_prompt",
            r"\[aligned\]", r"\[unaligned\]",
        ),
        "main.py": (
            r"def main", r"Targeter", r"Drafter",
            r"run_problem", r"asyncio\.run",
        ),
    }
    for relative, patterns in required_patterns.items():
        try:
            text = (root / relative).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False
        if not all(re.search(pattern, text) for pattern in patterns):
            return False
    return True


def _normalize_object(value: str | list[str]) -> str | list[str]:
    return _normalize_text(value) if isinstance(value, str) else [_normalize_text(item) for item in value]


def _normalize_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9_]+", value.lower()))


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in values if item))


class LookaheadReasoningProfile:
    profile_id = "lookahead_step_level_speculative_decoding"

    _required = [
        "draft_model_and_generation",
        "target_model_and_generation",
        "tree_node_orchestration",
        "semantic_verifier",
        "main_loop_with_acceptance",
    ]

    def match(self, repo_snapshot: RepoSnapshot) -> ProfileMatch:
        root = Path(repo_snapshot.project_root).resolve()
        index = _SourceIndex(root, repo_snapshot)
        checks = {
            "draft_model_and_generation": all((
                index.has("src/vllm_model.py", "Drafter.__init__"),
                index.has("src/vllm_model.py", "Drafter.draft"),
                index.has("src/vllm_model.py", "LLMModel.generate"),
            )),
            "target_model_and_generation": all((
                index.has("src/vllm_model.py", "Targeter.__init__"),
                index.has("src/vllm_model.py", "Targeter.target"),
            )),
            "tree_node_orchestration": all((
                index.has("src/lr_tree.py", "TreeNode.__init__"),
                index.has("src/lr_tree.py", "TreeNode.start_main_if_possible"),
                index.has("src/lr_tree.py", "TreeNode.collect_main_if_possible"),
                index.has("src/lr_tree.py", "TreeNode.travel_set_accepted"),
                index.has("src/lr_tree.py", "TreeNode.check_judge_children"),
            )),
            "semantic_verifier": all((
                index.has("src/lr.py", "accept_func"),
                index.has("src/lr.py", "text_accept"),
            )),
            "main_loop_with_acceptance": all((
                index.has("src/lr.py", "run_problem"),
                index.has("main.py", "main"),
            )),
        }
        matched_fingerprints = [name for name, passed in checks.items() if passed]
        missing_fingerprints = [name for name, passed in checks.items() if not passed]
        symbol_matched = not missing_fingerprints

        # Also check behavior contract to avoid match=True but compile=None
        behavior_ok = _behavior_contract_satisfied(root)
        matched = symbol_matched and behavior_ok

        reasons = []
        if symbol_matched:
            reasons.append(f"required executable symbols matched: {', '.join(matched_fingerprints)}")
        else:
            reasons.append(f"missing executable symbols: {', '.join(missing_fingerprints)}")
        if behavior_ok:
            reasons.append("behavior contract satisfied (async vLLM generation, tree traversal, semantic verifier)")
        else:
            reasons.append("behavior contract FAILED: missing vLLM async patterns, tree traversal, or semantic verifier predicates")

        return ProfileMatch(
            profile_id=self.profile_id,
            matched=matched,
            required_fingerprints=list(self._required),
            matched_fingerprints=matched_fingerprints,
            missing_required_fingerprints=missing_fingerprints,
            reasons=reasons,
        )

    def _compile_legacy(self, repo_snapshot: RepoSnapshot) -> EvidenceCompilerV3Result | None:
        """Archived migration fixture; never exposed by the production view."""
        return _compile_lookahead_evidence(repo_snapshot)


__all__ = ["LookaheadReasoningProfile"]
