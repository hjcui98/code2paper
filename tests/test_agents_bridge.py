from types import SimpleNamespace

from code2paper.agents.bridge import _build_code_method_analysis_payload
from code2paper.core.schemas import AuthorMode, EvidenceItem, RawEvidencePack, SourceType


def test_bridge_rebinds_stale_stage_snippet_refs_to_author_scoped_file() -> None:
    raw = RawEvidencePack(
        project_id="demo",
        project_root="/repo",
        author_mode=AuthorMode.ENHANCED,
        evidence_items=[
            EvidenceItem(evidence_id="E1", source_type=SourceType.SOURCE, path="unrelated.py", line_start=1,
                         line_end=2, confidence=0.9, content_summary="Unrelated code."),
            EvidenceItem(evidence_id="E2", source_type=SourceType.SOURCE, path="data/flip.py", line_start=3,
                         line_end=8, confidence=0.9, content_summary="Flip implementation."),
        ],
    )
    author_step = SimpleNamespace(
        name="Patch flipping", related_files=["data/flip.py"], highlight_level=SimpleNamespace(value="main")
    )
    markers = SimpleNamespace(
        pipeline_steps=[author_step], paper_story_order=[], innovation_claims=[],
        paper_method_goal="", project_goal="",
    )

    payload = _build_code_method_analysis_payload(
        code_facts={"pipeline_steps": [{
            "name": "Patch flipping", "description": "Flip a selected patch.",
            "evidence_refs": ["stale-snippet-id"],
        }]},
        core_snippets={"snippets": []},
        author_markers=markers,
        snippet_to_evidence={},
        raw_pack=raw,
    )

    assert payload["candidate_mechanisms"][0]["supporting_span_ids"] == ["E2"]


def test_bridge_rebinds_repair_candidates_by_claim_text_not_ephemeral_id() -> None:
    raw = RawEvidencePack(
        project_id="demo",
        project_root="/repo",
        author_mode=AuthorMode.ENHANCED,
        evidence_items=[
            EvidenceItem(evidence_id="E1", source_type=SourceType.SOURCE, path="base/moe.py", line_start=1,
                         line_end=20, confidence=0.9, content_summary="Generic MoE code."),
            EvidenceItem(evidence_id="E2", source_type=SourceType.SOURCE, path="pruning/expert_selection.py", line_start=7,
                         line_end=44, confidence=0.9, content_summary="Output-aware expert scoring."),
        ],
    )
    author_step = SimpleNamespace(
        name="Per-token expert importance computation", related_files=[],
        highlight_level=SimpleNamespace(value="main"),
    )
    markers = SimpleNamespace(
        pipeline_steps=[author_step], paper_story_order=[], innovation_claims=[],
        paper_method_goal="", project_goal="",
    )

    payload = _build_code_method_analysis_payload(
        code_facts={"pipeline_steps": [{
            "name": "Per-token expert importance computation",
            "description": "Compute the product of the gating value and the L2 norm of the expert output.",
            "evidence_refs": ["stale"],
        }]},
        core_snippets={"snippets": []},
        author_markers=markers,
        snippet_to_evidence={"stale": "E1"},
        raw_pack=raw,
        evidence_repair_focus={
            "claim_targets": [{
                "claim_id": "C35",
                "claim_query": "C35: Use the product of gating value and output L2 norm to measure expert importance.",
                "candidates": [{"path": "pruning/expert_selection.py"}],
            }]
        },
    )

    # The repaired span is promoted even though the current freeze may later
    # renumber C35. Existing evidence remains available for conservative gates.
    assert payload["candidate_mechanisms"][0]["supporting_span_ids"] == ["E2", "E1"]


def test_bridge_prefers_rescanned_code_that_matches_multiple_method_concepts() -> None:
    raw = RawEvidencePack(
        project_id="demo",
        project_root="/repo",
        author_mode=AuthorMode.ENHANCED,
        evidence_items=[
            EvidenceItem(evidence_id="E1", source_type=SourceType.SOURCE, path="runtime.py", line_start=1,
                         line_end=20, confidence=0.9, content_summary="Generic runtime."),
            EvidenceItem(evidence_id="E2", source_type=SourceType.SOURCE,
                         path="pruning/expert_selection.py", line_start=7, line_end=44,
                         confidence=0.9, content_summary="Direct pruning implementation."),
        ],
    )
    markers = SimpleNamespace(
        pipeline_steps=[], paper_story_order=[], innovation_claims=[],
        paper_method_goal="", project_goal="",
    )
    payload = _build_code_method_analysis_payload(
        code_facts={"pipeline_steps": [{
            "name": "Expert pruning",
            "description": "Keep top-M experts per layer based on aggregated scores.",
            "evidence_refs": ["stale"],
        }]},
        core_snippets={"snippets": [
            {"snippet_id": "stale", "source": {"path": "runtime.py"},
             "text": "def request_runtime(): return server_info"},
            {"snippet_id": "rescanned", "role": "agentic_rescan_symbol_index",
             "source": {"path": "pruning/expert_selection.py", "symbol": "main"},
             "text": "export_scores = torch.sum(torch.stack(score_list), dim=0)\n"
                     "topk_experts = torch.topk(export_scores, target_number, dim=-1)[1]\n"
                     "mask.scatter_(1, topk_experts, 1)"},
        ]},
        author_markers=markers,
        snippet_to_evidence={"stale": "E1", "rescanned": "E2"},
        raw_pack=raw,
    )

    assert payload["candidate_mechanisms"][0]["supporting_span_ids"] == ["E2"]


def test_bridge_does_not_promote_rescan_from_path_hint_without_content_match() -> None:
    raw = RawEvidencePack(
        project_id="demo", project_root="/repo", author_mode=AuthorMode.ENHANCED,
        evidence_items=[
            EvidenceItem(evidence_id="E1", source_type=SourceType.SOURCE, path="runtime.py",
                         line_start=1, line_end=20, confidence=0.9, content_summary="Runtime."),
            EvidenceItem(evidence_id="E2", source_type=SourceType.SOURCE,
                         path="pruning/unrelated.py", line_start=1, line_end=10,
                         confidence=0.9, content_summary="Unrelated."),
        ],
    )
    markers = SimpleNamespace(
        pipeline_steps=[], paper_story_order=[], innovation_claims=[],
        paper_method_goal="", project_goal="",
    )
    payload = _build_code_method_analysis_payload(
        code_facts={"pipeline_steps": [{
            "name": "Expert pruning", "description": "Keep top-M experts from aggregated scores.",
            "evidence_refs": ["stale"],
        }]},
        core_snippets={"snippets": [
            {"snippet_id": "stale", "source": {"path": "runtime.py"}, "text": "runtime"},
            {"snippet_id": "rescanned", "role": "agentic_rescan_symbol_index",
             "source": {"path": "pruning/unrelated.py"}, "text": "def load_config(): return config"},
        ]},
        author_markers=markers,
        snippet_to_evidence={"stale": "E1", "rescanned": "E2"}, raw_pack=raw,
    )

    assert payload["candidate_mechanisms"][0]["supporting_span_ids"] == ["E1"]


def test_bridge_rebinds_output_norm_and_cosine_mechanisms_to_direct_code() -> None:
    raw = RawEvidencePack(
        project_id="demo", project_root="/repo", author_mode=AuthorMode.ENHANCED,
        evidence_items=[
            EvidenceItem(evidence_id="E1", source_type=SourceType.SOURCE, path="runtime.py",
                         line_start=1, line_end=5, confidence=0.9, content_summary="Runtime."),
            EvidenceItem(evidence_id="E2", source_type=SourceType.SOURCE, path="pruning/model.py",
                         line_start=10, line_end=30, confidence=0.9, content_summary="MoE statistics."),
            EvidenceItem(evidence_id="E3", source_type=SourceType.SOURCE, path="pruning/model.py",
                         line_start=31, line_end=45, confidence=0.9, content_summary="Token similarity."),
            EvidenceItem(evidence_id="E4", source_type=SourceType.SOURCE,
                         path="pruning/expert_selection_mix_domain.py", line_start=7, line_end=30,
                         confidence=0.9, content_summary="Mixed-domain score aggregation."),
        ],
    )
    markers = SimpleNamespace(
        pipeline_steps=[], paper_story_order=[], innovation_claims=[],
        paper_method_goal="", project_goal="",
    )
    payload = _build_code_method_analysis_payload(
        code_facts={"pipeline_steps": [
            {"name": "Expert importance", "description":
             "Compute the product of gating value and L2 norm of expert output.",
             "evidence_refs": ["stale"]},
            {"name": "Token contribution", "description":
             "Compute weight as 1 - cosine similarity of hidden states before and after MoE.",
             "evidence_refs": ["stale"]},
            {"name": "Multi-domain extension", "description":
             "For multiple domains, average normalized domain-specific scores before final selection.",
             "evidence_refs": ["stale"]},
        ]},
        core_snippets={"snippets": [
            {"snippet_id": "stale", "source": {"path": "runtime.py"}, "text": "runtime"},
            {"snippet_id": "stats", "role": "agentic_rescan_symbol_index",
             "source": {"path": "pruning/model.py", "symbol": "MoE.forward"},
             "text": "weights, indices = self.gate(x)\n"
                     "expert_out = expert(x[idx])\n"
                     "norms = torch.norm(expert_out, p=2, dim=1)"},
            {"snippet_id": "similarity", "role": "agentic_rescan_symbol_index",
             "source": {"path": "pruning/model.py", "symbol": "Block.forward"},
             "text": "x_before_moe = x.clone()\n"
                     "cos_sim = F.cosine_similarity(x_before_moe, x_after_moe)"},
            {"snippet_id": "mixed", "role": "agentic_rescan_symbol_index",
             "source": {"path": "pruning/expert_selection_mix_domain.py", "symbol": "main"},
             "text": "score = score / torch.sum(score, dim=-1, keepdim=True)\n"
                     "tmp = tmp + score\n"
                     "topk_experts = torch.topk(tmp, k=128, dim=-1)[1]"},
        ]},
        author_markers=markers,
        snippet_to_evidence={"stale": "E1", "stats": "E2", "similarity": "E3", "mixed": "E4"},
        raw_pack=raw,
    )

    assert payload["candidate_mechanisms"][0]["supporting_span_ids"] == ["E2"]
    assert payload["candidate_mechanisms"][1]["supporting_span_ids"] == ["E3"]
    assert payload["candidate_mechanisms"][2]["supporting_span_ids"] == ["E4"]
