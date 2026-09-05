from __future__ import annotations

from pathlib import Path


METHOD_OUTPUTS = {
    "generated_author_markers_yaml": "artifacts/01_input/author_markers.generated.yaml",
    "generated_author_markers_json": "artifacts/01_input/author_markers.generated.json",
    "resolved_author_markers_yaml": "artifacts/01_input/author_markers.resolved.yaml",
    "resolved_author_markers_json": "artifacts/01_input/author_markers.resolved.json",
    "seed_markers_yaml": "artifacts/01_input/author_markers.seed.yaml",
    "seed_markers_json": "artifacts/01_input/author_markers.seed.json",
    "refined_markers_yaml": "artifacts/01_input/author_markers.refined.yaml",
    "refined_markers_json": "artifacts/01_input/author_markers.refined.json",
    "prepare_report": "artifacts/01_input/prepare_report.json",
    "input_manifest": "artifacts/01_input/input_manifest.json",
    "intent_spec": "artifacts/01_input/intent_spec.json",
    "evidence_raw": "artifacts/02_intake/evidence_raw.json",
    "sources": "artifacts/02_intake/sources.json",
    "snippets": "artifacts/02_intake/snippets.json",
    "intake_report": "artifacts/02_intake/intake_report.json",
    "intake_alignment": "artifacts/02_intake/intake_alignment.json",
    "author_summary": "artifacts/02_intake/author_summary.json",
    "evidence_index": "artifacts/02_intake/evidence_index.json",
    "intake_manifest": "artifacts/02_intake/intake_manifest.json",
    "alignment": "artifacts/03_analysis/code_alignment.json",
    "analysis": "artifacts/03_analysis/code_analysis.json",
    "facts": "artifacts/03_analysis/code_facts.json",
    "code_graph": "artifacts/03_analysis/code_graph.json",
    "entity_map": "artifacts/03_analysis/entity_map.json",
    "analysis_report": "artifacts/03_analysis/analysis_report.json",
    "analysis_repair_focus": "artifacts/03_analysis/analysis_repair_focus.json",
    "analysis_repair_tasks": "artifacts/03_analysis/analysis_repair_tasks.json",
    "analysis_manifest": "artifacts/03_analysis/analysis_manifest.json",
    "phase2_blocked_report": "artifacts/03_analysis/analysis_blocked_report.json",
    "phase2_code_report": "artifacts/03_analysis/analysis_code_report.json",
    "evidence": "artifacts/04_evidence/method_evidence.json",
    "claims": "artifacts/04_evidence/claim_evidence_map.json",
    "evidence_notes": "artifacts/04_evidence/method_evidence_notes.md",
    "evidence_manifest": "artifacts/04_evidence/evidence_manifest.json",
    "grounding_context": "artifacts/05_grounding/grounding_context.md",
    "equation_candidates": "artifacts/05_grounding/equation_candidates.json",
    "equations_tex": "artifacts/05_grounding/grounding_equations.tex",
    "symbols_tex": "artifacts/05_grounding/grounding_symbols.tex",
    "grounding_manifest": "artifacts/05_grounding/grounding_manifest.json",
    "write_prompt": "artifacts/06_authoring/authoring_prompt.md",
    "outline": "artifacts/06_authoring/method_outline.json",
    "method_plan": "artifacts/06_authoring/method_plan.json",
    "method_plan_quality": "artifacts/06_authoring/method_plan_quality.json",
    "semantic_issues": "artifacts/06_authoring/semantic_issues.json",
    "terms": "artifacts/06_authoring/terminology_table.json",
    "text_md": "artifacts/06_authoring/method_draft.md",
    "text_clean_md": "artifacts/06_authoring/method_clean.md",
    "text_tex": "artifacts/06_authoring/method_draft.tex",
    "text_clean_tex": "artifacts/06_authoring/method_clean.tex",
    "repository_verified_method": "artifacts/06_authoring/repository_verified_method.md",
    "publication_candidate_method": "artifacts/06_authoring/publication_candidate_method.md",
    "author_review_candidates": "artifacts/06_authoring/author_review_candidates.json",
    "method_section_plan_v2": "artifacts/06_authoring/method_section_plan_v2.json",
    "method_argument_briefs_v1": "artifacts/06_authoring/method_argument_briefs_v1.json",
    "method_argument_facets_v1": "artifacts/06_authoring/method_argument_facets_v1.json",
    "facet_evidence_alignments_v1": "artifacts/06_authoring/facet_evidence_alignments_v1.json",
    "candidate_facet_policies_v1": "artifacts/06_authoring/candidate_facet_policies_v1.json",
    "method_argument_facet_alignment_trace_v1": "artifacts/06_authoring/method_argument_facet_alignment_trace_v1.json",
    "method_propositions_v1": "artifacts/06_authoring/method_propositions_v1.json",
    "method_proposition_clusters_v1": "artifacts/06_authoring/method_proposition_clusters_v1.json",
    "method_proposition_architect_calls_v1": "artifacts/06_authoring/method_proposition_architect_calls_v1.json",
    "method_proposition_bindings_v1": "artifacts/06_authoring/method_proposition_bindings_v1.json",
    "method_proposition_alignment_v1": "artifacts/07_validation/method_proposition_alignment_v1.json",
    "method_proposition_alignment_calls_v1": "artifacts/07_validation/method_proposition_alignment_calls_v1.json",
    "formalization_result_v1": "artifacts/06_authoring/formalization_result_v1.json",
    "formalization_agent_result_v1": "artifacts/06_authoring/formalization_agent_result_v1.json",
    "formalization_section_results_v1": "artifacts/06_authoring/formalization_section_results_v1.json",
    "research_mechanism_dossiers_v1": "artifacts/06_authoring/research_mechanism_dossiers_v1.json",
    "derivation_records_v1": "artifacts/06_authoring/derivation_records_v1.json",
    "candidate_authority_validation_v1": "artifacts/07_validation/candidate_authority_validation_v1.json",
    "publication_candidate_annotated": "artifacts/06_authoring/publication_candidate_annotated.md",
    "publication_candidate_annotations_v1": "artifacts/06_authoring/publication_candidate_annotations_v1.json",
    "method_architect_trace_v1": "artifacts/06_authoring/method_architect_trace_v1.json",
    "publication_writer_result_v1": "artifacts/06_authoring/publication_writer_result_v1.json",
   "mechanism_context_set_v1": "artifacts/06_authoring/mechanism_context_set_v1.json",
    "mechanism_evidence_closures_v1": "artifacts/06_authoring/mechanism_evidence_closures_v1.json",
   "narrative_plan_v3": "artifacts/06_authoring/narrative_plan_v3.json",
    "product_authoring_state_v1": "artifacts/06_authoring/product_authoring_state_v1.json",
    "method_content_trace_v1": "artifacts/research_product/method_content_trace_v1.json",
    "method_content_trace_v2": "artifacts/research_product/method_content_trace_v2.json",
    "method_content_trace_v2_error": "artifacts/research_product/method_content_trace_v2.error.json",
    "mechanism_information_funnel_v1": "artifacts/research_product/mechanism_information_funnel_v1.json",
    "mechanism_shared_payload_trace_v1": "artifacts/research_product/mechanism_shared_payload_trace_v1.json",
    "publication_paragraph_transaction_assessments_v1": "artifacts/06_authoring/publication_paragraph_transaction_assessments_v1.json",
    "authoring_structural_exit_v1": "artifacts/06_authoring/authoring_structural_exit_v1.json",
    "method_generation_trace_v1": "artifacts/research_product/method_generation_trace_v1.json",
    "publication_section_checkpoint_v1": "artifacts/06_authoring/publication_section_checkpoint_v1.json",
    "publication_paragraph_checkpoint_v1": "artifacts/06_authoring/publication_paragraph_checkpoint_v1.json",
    "publication_candidate_checkpoint_v1": "artifacts/06_authoring/publication_candidate_checkpoint_v1.json",
    "writing_research_routes_v1": "artifacts/06_authoring/writing_research_routes_v1.json",
    "writing_research_callback_artifacts_v1": "artifacts/06_authoring/writing_research_callback_artifacts_v1.json",
    "external_research_queue_v1": "artifacts/06_authoring/external_research_queue_v1.json",
    "authoring_projection_v1": "artifacts/06_authoring/authoring_projection_v1.json",
    "method_draft_bundle_v1": "artifacts/06_authoring/method_draft_bundle_v1.json",
    "publication_editor_result_v1": "artifacts/06_authoring/publication_editor_result_v1.json",
    "publication_editor_transitions_v1": "artifacts/07_validation/publication_editor_transitions_v1.json",
    "text_claims": "artifacts/06_authoring/method_claim_map.json",
    "text_sidecar": "artifacts/06_authoring/method_sidecar.json",
    "authoring_blocked": "artifacts/06_authoring/authoring_blocked.json",
    "authoring_manifest": "artifacts/06_authoring/authoring_manifest.json",
    "final_text_authorship_ledger_v1": "artifacts/07_validation/final_text_authorship_ledger_v1.json",
    "final_text_claims": "artifacts/07_validation/agentic_final_text_claims.json",
    "text_evidence_validation": "artifacts/07_validation/agentic_text_evidence_validation.json",
    "publication_rewrite_transitions_v1": "artifacts/07_validation/publication_rewrite_transitions_v1.json",
    "publication_rewrite_results_v1": "artifacts/07_validation/publication_rewrite_results_v1.json",
    "publication_quality_report_v1": "artifacts/07_validation/publication_quality_report_v1.json",
    "section_content_witness_v1": "artifacts/07_validation/section_content_witness_v1.json",
    "self_check": "artifacts/07_validation/self_check.json",
    "self_check_clean": "artifacts/07_validation/self_check_clean.json",
    "qa_claims": "artifacts/07_validation/qa_claims.json",
    "qa_numbers": "artifacts/07_validation/qa_numbers.json",
    "qa_equations": "artifacts/07_validation/qa_equations.json",
    "qa_terms": "artifacts/07_validation/qa_terms.json",
    "qa_latex": "artifacts/07_validation/qa_latex.json",
    "fidelity": "artifacts/07_validation/fidelity_report.json",
    "validation_manifest": "artifacts/07_validation/validation_manifest.json",
    "pdf_report": "artifacts/08_rendering/method_pdf_report.json",
    "text_pdf": "final/method.pdf",
    "method_standalone_tex": "artifacts/08_rendering/method_standalone.tex",
    "rendering_manifest": "artifacts/08_rendering/rendering_manifest.json",
    "final_tex": "artifacts/09_finalize/final_method.tex",
    "final_pdf": "final/final_method.pdf",
    "final_pdf_report": "artifacts/09_finalize/final_pdf_report.json",
    "finalize_manifest": "artifacts/09_finalize/finalize_manifest.json",
    "package_manifest": "final/package_manifest.json",
    "run_report": "artifacts/10_run/run_report.json",
    "run_manifest": "artifacts/10_run/run_manifest.json",
    "holdout_acceptance_report_v1": "artifacts/10_run/holdout_acceptance_report_v1.json",
    "execution_profile": "artifacts/10_run/execution_profile_v1.json",
    "execution_route": "artifacts/10_run/execution_route_v1.json",
    "run_report_md": "final/run_report.md",
    "root_method_md": "final/method.md",
    "root_method_tex": "final/method.tex",
    "final_figures_dir": "final/figures",
}

ALIASES = {
    "phase1_manifest": "intake_manifest",
    "phase2_manifest": "analysis_manifest",
    "phase3_manifest": "evidence_manifest",
    "phase4_manifest": "grounding_manifest",
    "phase5_manifest": "authoring_manifest",
    "phase5_blocked": "authoring_blocked",
    "phase6_manifest": "validation_manifest",
    "phase7_manifest": "rendering_manifest",
    "phase8_manifest": "finalize_manifest",
}


def method_output(base: Path, key: str) -> Path:
    canonical_key = ALIASES.get(key, key)
    path = _out_root(base) / METHOD_OUTPUTS[canonical_key]
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def artifact_dir(base: Path, stage: str) -> Path:
    path = _out_root(base) / "artifacts" / stage
    path.mkdir(parents=True, exist_ok=True)
    return path


def final_dir(base: Path, name: str = "") -> Path:
    path = _out_root(base) / "final" / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def _out_root(base: Path) -> Path:
    base = Path(base)
    parts = base.parts
    if len(parts) >= 2 and parts[-2:] == ("paper", "method"):
        return base.parent.parent
    if base.name == "artifacts":
        return base.parent
    if "artifacts" in parts:
        index = parts.index("artifacts")
        return Path(*parts[:index]) if index else Path(".")
    return base
