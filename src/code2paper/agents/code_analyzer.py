import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from code2paper.agents.template import Template

from code2paper.agents.state.poster_state import PosterState
from code2paper.agents.utils.code_ir_builder import (
    analyze_modules,
    analyze_pipeline_steps,
    analyze_losses,
    analyze_training,
    analyze_data,
    validate_alignment,
    build_code_facts,
    build_code_overview,
    build_code_ir,
    build_entity_links,
)
from code2paper.agents.utils.artifact_meta import add_meta
from code2paper.agents.langgraph_utils import LangGraphAgent, extract_json, load_prompt
from code2paper.agents.logging_utils import log_agent_error, log_agent_info, log_agent_success, log_agent_warning


class CodeAnalyzerAgent:
    def __init__(self):
        self.name = "code_analyzer"
        self.synthesis_prompt = load_prompt("config/prompts/code_analyzer_synthesis.txt")

    def __call__(self, state: PosterState) -> PosterState:
        log_agent_info(self.name, "starting code analysis (v2)")

        try:
            output_dir = Path(state["output_dir"])
            content_dir = output_dir / "content"
            content_dir.mkdir(parents=True, exist_ok=True)

            core_snippets = state.get("core_snippets") or _load_json(content_dir / "core_snippets.json") or {}
            method_code_alignment = state.get("method_code_alignment") or _load_json(content_dir / "method_code_alignment.json") or {}
            code_intake_report = state.get("code_intake_report") or _load_json(content_dir / "code_intake_report.json") or {}
            method_summary = state.get("method_experiment_structured_summary") or _load_json(content_dir / "method_experiment_structured_summary.json") or {}
            paper_objects = state.get("paper_objects") or _load_json(content_dir / "paper_objects.json") or {}
            dynamic_roles = state.get("dynamic_roles") or []

            snippets = core_snippets.get("snippets") if isinstance(core_snippets, dict) else None
            if not isinstance(snippets, list) or not snippets:
                code_facts = _build_empty_code_facts()
                code_ir = {"nodes": [], "edges": [], "annotations": [{"note": "no core_snippets"}]}
                entity_links = {"meta": {"version": "v2"}, "links": []}
                _save_json(content_dir / "code_facts.json", code_facts)
                _save_json(content_dir / "code_ir.json", code_ir)
                _save_json(content_dir / "entity_links.json", entity_links)
                state["code_facts"] = code_facts
                state["code_ir"] = code_ir
                state["entity_links"] = entity_links
                state["current_agent"] = self.name
                return state

            log_agent_info(self.name, "running detailed analysis")

            modules = analyze_modules(core_snippets, method_code_alignment)
            log_agent_info(self.name, f"module analysis complete: {len(modules)} modules")

            pipeline_steps = analyze_pipeline_steps(core_snippets, method_code_alignment, modules)
            log_agent_info(self.name, f"pipeline analysis complete: {len(pipeline_steps)} steps")

            losses = analyze_losses(core_snippets, method_code_alignment, paper_objects)
            log_agent_info(self.name, f"loss analysis complete: {len(losses)} losses")

            training_detail = analyze_training(core_snippets)
            if not isinstance(training_detail, dict):
                log_agent_warning(self.name, "training_detail malformed; fallback to empty dict")
                training_detail = {}
            log_agent_info(self.name, f"training analysis complete: type={training_detail.get('type', 'standard')}")

            data_detail = analyze_data(core_snippets)
            if not isinstance(data_detail, dict):
                log_agent_warning(self.name, "data_detail malformed; fallback to empty dict")
                data_detail = {}
            log_agent_info(self.name, f"data analysis complete: {len(data_detail.get('datasets', []))} datasets")

            alignment_validation = validate_alignment(method_code_alignment, modules, pipeline_steps, losses)
            if not isinstance(alignment_validation, dict):
                log_agent_warning(self.name, "alignment_validation malformed; fallback to empty dict")
                alignment_validation = {}
            log_agent_info(self.name, f"alignment validation complete: score={alignment_validation.get('overall_score', 0):.2f}")

            detailed_analysis = {
                "modules": modules,
                "pipeline_steps": pipeline_steps,
                "losses": losses,
                "training_detail": training_detail,
                "data_detail": data_detail,
                "alignment_validation": alignment_validation,
            }

            enable_llm = state.get("enable_code_analyzer_llm", True)
            llm_result = None
            inp_tok = 0
            out_tok = 0

            if enable_llm and self.synthesis_prompt:
                log_agent_info(self.name, "running LLM synthesis")
                llm_result, inp_tok, out_tok = self._llm_synthesis(
                    core_snippets,
                    method_code_alignment,
                    paper_objects,
                    method_summary,
                    detailed_analysis,
                    dynamic_roles,
                    state,
                )
                if inp_tok or out_tok:
                    state["tokens"].add_text(inp_tok, out_tok)

            if isinstance(llm_result, dict) and llm_result.get("modules"):
                code_facts = _merge_llm_result(detailed_analysis, llm_result, method_summary, dynamic_roles)
            else:
                code_facts = build_code_facts(
                    core_snippets,
                    method_code_alignment,
                    paper_objects,
                    method_summary,
                    dynamic_roles,
                )
            code_facts = _normalize_code_facts(code_facts, detailed_analysis, method_summary, dynamic_roles)

            code_ir = build_code_ir(code_facts)
            entity_links = build_entity_links(code_facts, method_code_alignment)

            analysis_report = {
                "total_snippets": len(snippets),
                "modules_found": len(code_facts.get("modules", [])),
                "pipeline_steps_found": len(code_facts.get("pipeline_steps", [])),
                "losses_found": len(code_facts.get("losses", [])),
                "alignment_score": alignment_validation.get("overall_score", 0),
                "training_type": training_detail.get("type", "standard"),
                "datasets_found": len(data_detail.get("datasets", [])),
                "llm_used": enable_llm and llm_result is not None,
                "llm_tokens": {"input": inp_tok, "output": out_tok},
            }

            _save_json(content_dir / "code_facts.json", code_facts)
            _save_json(content_dir / "code_ir.json", code_ir)
            _save_json(content_dir / "entity_links.json", entity_links)
            _save_json(content_dir / "code_analysis_report.json", analysis_report)

            state["code_facts"] = code_facts
            state["code_ir"] = code_ir
            state["entity_links"] = entity_links
            state["code_analysis_report"] = analysis_report
            state["current_agent"] = self.name

            log_agent_success(self.name, f"code analysis complete: {len(code_facts.get('modules', []))} modules, alignment={alignment_validation.get('overall_score', 0):.2f}")
            return state

        except Exception as e:
            log_agent_error(self.name, f"failed: {e}")
            state["errors"].append(f"{self.name}: {e}")
            return state

    def _llm_synthesis(
        self,
        core_snippets: Dict[str, Any],
        method_code_alignment: Dict[str, Any],
        paper_objects: Dict[str, Any],
        method_summary: Dict[str, Any],
        detailed_analysis: Dict[str, Any],
        dynamic_roles: List[str],
        state: PosterState,
    ) -> Tuple[Optional[Dict[str, Any]], int, int]:
        if not self.synthesis_prompt:
            return None, 0, 0

        snippets = core_snippets.get("snippets", [])
        snippet_preview = []
        for sn in snippets[:30]:
            if not isinstance(sn, dict):
                continue
            text = str(sn.get("text") or "")
            head = "\n".join(text.splitlines()[:30])
            snippet_preview.append({
                "snippet_id": sn.get("snippet_id"),
                "role": sn.get("role"),
                "source": sn.get("source"),
                "head": head,
            })

        agent = LangGraphAgent("expert code analyzer", state["text_model"], state, "code_analyzer")
        prompt = Template(self.synthesis_prompt).render(
            method_code_alignment=json.dumps(method_code_alignment, ensure_ascii=False),
            core_snippets=json.dumps({"snippets": snippet_preview}, ensure_ascii=False),
            paper_objects=json.dumps(paper_objects, ensure_ascii=False),
            method_summary=json.dumps(method_summary if isinstance(method_summary, dict) else {}, ensure_ascii=False),
            detailed_analysis=json.dumps(detailed_analysis, ensure_ascii=False),
        )

        try:
            agent.reset()
            response = agent.step(prompt)
            result = extract_json(response.content)
            if isinstance(result, dict):
                return result, response.input_tokens, response.output_tokens
            return None, response.input_tokens, response.output_tokens
        except Exception as e:
            log_agent_warning(self.name, f"LLM synthesis failed: {e}")
            return None, 0, 0


def _build_empty_code_facts() -> Dict[str, Any]:
    return {
        "meta": {"version": "v2", "producer": "code_analyzer"},
        "overview": {
            "implementation_summary": "",
            "architecture_summary": "",
            "training_summary": "",
            "alignment_summary": "",
        },
        "modules": [],
        "pipeline_steps": [],
        "losses": [],
        "training_detail": {},
        "data_detail": {"datasets": [], "dataloader": {}},
        "alignment_validation": {"overall_score": 0},
        "key_insights": [],
        "diagram_hints": {},
        "missing_fields_report": {"snippets": "not_found"},
    }


def _merge_llm_result(
    detailed_analysis: Dict[str, Any],
    llm_result: Dict[str, Any],
    method_summary: Dict[str, Any],
    dynamic_roles: List[str],
) -> Dict[str, Any]:
    modules = _ensure_list_of_dicts(llm_result.get("modules"), detailed_analysis.get("modules", []))
    pipeline_steps = _ensure_list_of_dicts(llm_result.get("pipeline_steps"), detailed_analysis.get("pipeline_steps", []))
    losses = _ensure_list_of_dicts(llm_result.get("losses"), detailed_analysis.get("losses", []))
    training_detail = _ensure_dict(llm_result.get("training_detail"), detailed_analysis.get("training_detail", {}))
    data_detail = _ensure_dict(llm_result.get("data_detail"), detailed_analysis.get("data_detail", {}))
    alignment_validation = _ensure_dict(
        llm_result.get("alignment_validation"),
        detailed_analysis.get("alignment_validation", {}),
    )
    key_insights = _ensure_list_of_dicts(llm_result.get("key_insights"), [])
    diagram_hints = _ensure_dict(llm_result.get("diagram_hints"), {})
    overview = _ensure_dict(
        llm_result.get("overview"),
        build_code_overview(
            method_summary,
            modules,
            pipeline_steps,
            losses,
            training_detail,
            alignment_validation,
        ),
    )

    merged = {
        "meta": {
            "version": "v2",
            "producer": "code_analyzer",
            "source": "llm_synthesis",
            "dynamic_roles": dynamic_roles,
        },
        "overview": overview,
        "modules": modules,
        "pipeline_steps": pipeline_steps,
        "losses": losses,
        "training_detail": training_detail,
        "data_detail": data_detail,
        "alignment_validation": alignment_validation,
        "key_insights": key_insights,
        "diagram_hints": diagram_hints,
    }
    return merged


def _ensure_dict(value: Any, fallback: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(fallback, dict):
        return fallback
    return {}


def _ensure_list_of_dicts(value: Any, fallback: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(fallback, list):
        return [item for item in fallback if isinstance(item, dict)]
    return []


def _normalize_code_facts(
    code_facts: Any,
    detailed_analysis: Dict[str, Any],
    method_summary: Dict[str, Any],
    dynamic_roles: List[str],
) -> Dict[str, Any]:
    facts = code_facts if isinstance(code_facts, dict) else {}
    default_meta = {"version": "v2", "producer": "code_analyzer", "dynamic_roles": dynamic_roles}
    meta = _ensure_dict(facts.get("meta"), default_meta)
    if not meta.get("version"):
        meta["version"] = "v2"
    if not meta.get("producer"):
        meta["producer"] = "code_analyzer"
    if not isinstance(meta.get("dynamic_roles"), list):
        meta["dynamic_roles"] = list(dynamic_roles)

    normalized = {
        "meta": meta,
        "overview": _ensure_dict(
            facts.get("overview"),
            build_code_overview(
                method_summary,
                _ensure_list_of_dicts(facts.get("modules"), detailed_analysis.get("modules", [])),
                _ensure_list_of_dicts(facts.get("pipeline_steps"), detailed_analysis.get("pipeline_steps", [])),
                _ensure_list_of_dicts(facts.get("losses"), detailed_analysis.get("losses", [])),
                _ensure_dict(facts.get("training_detail"), detailed_analysis.get("training_detail", {})),
                _ensure_dict(
                    facts.get("alignment_validation"),
                    detailed_analysis.get("alignment_validation", {}),
                ),
            ),
        ),
        "modules": _ensure_list_of_dicts(facts.get("modules"), detailed_analysis.get("modules", [])),
        "pipeline_steps": _ensure_list_of_dicts(facts.get("pipeline_steps"), detailed_analysis.get("pipeline_steps", [])),
        "losses": _ensure_list_of_dicts(facts.get("losses"), detailed_analysis.get("losses", [])),
        "training_detail": _ensure_dict(facts.get("training_detail"), detailed_analysis.get("training_detail", {})),
        "data_detail": _ensure_dict(facts.get("data_detail"), detailed_analysis.get("data_detail", {})),
        "alignment_validation": _ensure_dict(
            facts.get("alignment_validation"),
            detailed_analysis.get("alignment_validation", {}),
        ),
        "key_insights": _ensure_list_of_dicts(facts.get("key_insights"), []),
        "diagram_hints": _ensure_dict(facts.get("diagram_hints"), {}),
    }
    if isinstance(facts.get("missing_fields_report"), dict):
        normalized["missing_fields_report"] = facts["missing_fields_report"]
    return normalized


def _load_json(path: Path):
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_json(path: Path, data: Dict[str, Any]):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(add_meta(data, "code_analyzer"), f, indent=2, ensure_ascii=False)


def code_analyzer_node(state: PosterState) -> PosterState:
    return CodeAnalyzerAgent()(state)
