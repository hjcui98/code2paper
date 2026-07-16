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
