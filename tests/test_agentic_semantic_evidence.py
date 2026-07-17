from types import SimpleNamespace

from code2paper.agentic.semantic_evidence import concepts_semantically_related
from code2paper.agentic.text_evidence_validator import _relevant_to_evidence


def test_semantic_evidence_recognizes_mixed_domain_normalize_and_select_code() -> None:
    claim = (
        "For multiple domains, average the normalized domain-specific scores "
        "before the final selection."
    )
    evidence = (
        "score = score / torch.sum(score, dim=-1, keepdim=True)\n"
        "tmp = tmp + score\n"
        "topk_experts = torch.topk(tmp, k=128, dim=-1)[1]"
    )

    assert concepts_semantically_related(claim, evidence)


def test_semantic_evidence_recognizes_bounded_input_sampling() -> None:
    claim = "Collect a small number of demonstrations from the target domain."
    evidence = "data = [json.loads(item) for item in data[:25]]"

    assert concepts_semantically_related(claim, evidence)


def test_semantic_evidence_rejects_generic_runtime_vocabulary() -> None:
    claim = "Average normalized domain-specific scores before final expert selection."
    evidence = "def get_server_info(): return runtime_config"

    assert not concepts_semantically_related(claim, evidence)


def test_final_text_relevance_uses_code_operator_semantics_after_projection_match() -> None:
    claim = "For multiple domains, average normalized domain-specific scores before final selection."
    evidence = (
        "score = score / torch.sum(score, dim=-1, keepdim=True)\n"
        "tmp = tmp + score\n"
        "topk_experts = torch.topk(tmp, dim=-1)[1]"
    )

    assert _relevant_to_evidence(
        claim, evidence, [SimpleNamespace(supported_fragment=claim)]
    )


def test_semantic_evidence_matches_grouped_dynamic_filtering_stage() -> None:
    assert concepts_semantically_related(
        "C-MoE decoder with grouped dynamic filtering.",
        "Pack expert kernels into a single group convolution for parallel execution.",
    )


def test_semantic_evidence_matches_moe_in_moe_to_base_expert_composition() -> None:
    assert concepts_semantically_related(
        "MoE-in-MoE hierarchy with expert routing.",
        "Build routed expert kernels as compositions of a shared base-expert bank.",
    )
