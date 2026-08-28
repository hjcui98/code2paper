from __future__ import annotations

import json
from pathlib import Path

from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    AtomicClaimV3,
    CodeFactSetV1,
    CodeFactV1,
)
from code2paper.agentic.scientific_claim_ir import (
    compile_math_ops,
    compile_technical_claims,
    l1_chain_length,
)


def _fact(**kwargs: object) -> CodeFactV1:
    payload = {
        "fact_id": "F1",
        "subject": "activate",
        "predicate": "branches_on",
        "object": "entity_score < iteration_threshold",
        "scope": "activate",
        "direct_span_ids": ["S1"],
        "exact_source_digest": "sha256:e",
        "canonical_identity": "sha256:f",
        "conditions": ["continue"],
        "semantic_context": ["if entity_score < iteration_threshold: continue"],
    }
    payload.update(kwargs)
    return CodeFactV1(**payload)  # type: ignore[arg-type]


def _claim(fact: CodeFactV1) -> AtomicClaimV3:
    return AtomicClaimV3(
        claim_id="C1",
        canonical_text=f"{fact.subject} {fact.predicate} {fact.object}",
        fact_ids=[fact.fact_id],
        covers_obligation_ids=["O-STAGE-02"],
        direct_evidence_ids=list(fact.direct_span_ids),
        allowed_wording_boundary="exact behavior predicate and operands from source span; no effect expansion",
        canonical_identity="sha256:c",
    )


def test_threshold_continue_licenses_exclude_below_not_eligible_if_less() -> None:
    fact = _fact()
    facts = CodeFactSetV1(
        repo_snapshot_id="snap",
        project_tree_hash="tree",
        evidence_packet_digest="sha256:p",
        facts=[fact],
        content_digest="sha256:facts",
    )
    ops = compile_math_ops(facts)
    assert ops[0].kind == "threshold_mask"
    assert ops[0].polarity.startswith("exclude")
    technical, atomic = compile_technical_claims(facts, [_claim(fact)], obligation_id="O-STAGE-02")
    assert technical
    text = technical[0].canonical_text.casefold()
    assert "exclud" in text or "fail" in text
    assert "eligible if" not in text
    assert atomic[0].claim_kind == "technical_semantic"
    assert atomic[0].inference_level == "E2"


def test_sparse_mm_becomes_sparse_matvec_and_incidence_l2() -> None:
    fact = _fact(
        fact_id="F2",
        predicate="propagates",
        object="entity_to_sentence",
        semantic_context=["torch.sparse.mm", "mention incidence"],
        conditions=[],
    )
    facts = CodeFactSetV1(
        repo_snapshot_id="snap",
        project_tree_hash="tree",
        evidence_packet_digest="sha256:p",
        facts=[fact],
        content_digest="sha256:facts",
    )
    ops = compile_math_ops(facts)
    assert any(op.kind == "sparse_matvec" for op in ops)
    technical, _atomic = compile_technical_claims(facts, [_claim(fact)])
    assert any("distribut" in item.canonical_text.casefold() for item in technical)


def test_lone_product_is_not_a_long_l1_chain() -> None:
    fact = _fact(
        fact_id="F3",
        predicate="computes_formula",
        object=["entity_score", "top_sentence_score"],
        semantic_context=["*"],
        conditions=[],
    )
    facts = CodeFactSetV1(
        repo_snapshot_id="snap",
        project_tree_hash="tree",
        evidence_packet_digest="sha256:p",
        facts=[fact],
        content_digest="sha256:facts",
    )
    assert l1_chain_length(facts) == 1


def test_product_mask_and_sparse_form_a_chain() -> None:
    facts = CodeFactSetV1(
        repo_snapshot_id="snap",
        project_tree_hash="tree",
        evidence_packet_digest="sha256:p",
        facts=[
            _fact(
                fact_id="Fa",
                predicate="computes_formula",
                object=["entity_score", "top_sentence_score"],
                semantic_context=["*"],
                conditions=[],
            ),
            _fact(),
            _fact(
                fact_id="Fc",
                predicate="propagates",
                object="mention",
                semantic_context=["sparse.mm"],
                conditions=[],
            ),
        ],
        content_digest="sha256:facts",
    )
    assert l1_chain_length(facts) >= 2


def test_vectorized_threshold_mask_l2_is_exclude_below_not_retain_template() -> None:
    fact = _fact(
        fact_id="F-mask",
        predicate="constructs_mask",
        object=["next_scores >= iteration_threshold", "result=active_indices"],
        semantic_context=["np.where", "next_scores >= iteration_threshold"],
        conditions=[],
    )
    facts = CodeFactSetV1(
        repo_snapshot_id="snap",
        project_tree_hash="tree",
        evidence_packet_digest="sha256:p",
        facts=[fact],
        content_digest="sha256:facts",
    )
    technical, atomic = compile_technical_claims(
        facts, [_claim(fact)], obligation_id="O-STAGE-02"
    )
    assert technical
    text = technical[0].canonical_text.casefold()
    assert "exclud" in text or "fail" in text
    assert "retains only scores that meet the minimum" not in text
    assert "STAGE" in " ".join(atomic[0].covers_obligation_ids)


def test_l2_covers_prefers_stage_family_from_parents() -> None:
    fact = _fact()
    parent = _claim(fact)
    parent = parent.model_copy(update={
        "covers_obligation_ids": ["O-METHOD-MAINLINE-01", "O-STAGE-02"],
    })
    facts = CodeFactSetV1(
        repo_snapshot_id="snap",
        project_tree_hash="tree",
        evidence_packet_digest="sha256:p",
        facts=[fact],
        content_digest="sha256:facts",
    )
    _technical, atomic = compile_technical_claims(facts, [parent])
    assert atomic
    covers = " ".join(atomic[0].covers_obligation_ids)
    assert "STAGE" in covers
    assert "MAINLINE" not in covers


def test_matmul_is_not_elementwise_product() -> None:
    fact = _fact(
        fact_id="F-mm",
        predicate="computes_formula",
        object=["hidden", "weight"],
        semantic_context=["matmul", "in_proj.weight"],
        conditions=[],
    )
    facts = CodeFactSetV1(
        repo_snapshot_id="snap",
        project_tree_hash="tree",
        evidence_packet_digest="sha256:p",
        facts=[fact],
        content_digest="sha256:facts",
    )
    assert compile_math_ops(facts) == []
    technical, _atomic = compile_technical_claims(facts, [_claim(fact)])
    assert technical == []


def test_null_check_branch_is_not_threshold_mask() -> None:
    fact = _fact(
        fact_id="F-none",
        predicate="branches_on",
        object="dts != None",
        semantic_context=["self.time_mamba and dts != None"],
        conditions=["dts != None"],
    )
    facts = CodeFactSetV1(
        repo_snapshot_id="snap",
        project_tree_hash="tree",
        evidence_packet_digest="sha256:p",
        facts=[fact],
        content_digest="sha256:facts",
    )
    assert compile_math_ops(facts) == []


def test_quoted_string_add_is_not_weighted_sum() -> None:
    fact = _fact(
        fact_id="F-name",
        predicate="computes_formula",
        object=["'hybrid_attention_'", "run_name"],
        semantic_context=["add", "'hybrid_attention_'", "run_name"],
        conditions=[],
    )
    facts = CodeFactSetV1(
        repo_snapshot_id="snap",
        project_tree_hash="tree",
        evidence_packet_digest="sha256:p",
        facts=[fact],
        content_digest="sha256:facts",
    )
    assert compile_math_ops(facts) == []


def test_l2_templates_are_operator_neutral() -> None:
    fact = _fact()
    facts = CodeFactSetV1(
        repo_snapshot_id="snap",
        project_tree_hash="tree",
        evidence_packet_digest="sha256:p",
        facts=[fact],
        content_digest="sha256:facts",
    )
    technical, _atomic = compile_technical_claims(facts, [_claim(fact)])
    assert technical
    text = technical[0].canonical_text.casefold()
    assert "entit" not in text
    assert "child activation" not in text
    assert "expansion" not in text


def test_technical_claims_sidecar_persists_l2_rows(tmp_path) -> None:
    from code2paper.agentic.scientific_claim_ir import write_technical_claims_sidecar

    fact = _fact()
    facts = CodeFactSetV1(
        repo_snapshot_id="snap",
        project_tree_hash="tree",
        evidence_packet_digest="sha256:p",
        facts=[fact],
        content_digest="sha256:facts",
    )
    _technical, atomic = compile_technical_claims(
        facts, [_claim(fact)], obligation_id="O-STAGE-02"
    )
    claim_set = AtomicClaimSetV3(
        repo_snapshot_id="snap",
        project_tree_hash="tree",
        evidence_packet_digest="sha256:p",
        code_fact_digest="sha256:facts",
        claims=[_claim(fact), *atomic],
        content_digest="sha256:claims",
    )
    atomic_path = tmp_path / "atomic_claims_v3.json"
    atomic_path.write_text(claim_set.model_dump_json(), encoding="utf-8")
    sidecar = write_technical_claims_sidecar(atomic_path, claim_set)
    payload = json.loads(Path(sidecar).read_text(encoding="utf-8"))
    assert payload["claims"]
    assert payload["claims"][0]["inference_level"] == "E2"
    assert Path(sidecar).name == "technical_claims_v1.json"
