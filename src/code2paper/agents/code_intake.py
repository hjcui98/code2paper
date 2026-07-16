import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from code2paper.agents.template import Template

from code2paper.agents.state.poster_state import PosterState
from code2paper.agents.utils.code_scan import scan_repo, select_candidate_files
from code2paper.agents.utils.snippet_extract import apply_role_overrides, build_method_keyword_bank, extract_snippets, extract_symbol_snippets
from code2paper.agents.utils.retrieval_strategy import derive_orchestrator_symbol_targets
from code2paper.agents.utils.method_code_alignment import (
    align_method_to_code,
    extract_dynamic_roles,
    build_method_keyword_bank_enhanced,
    fill_relevance_from_alignment,
    extract_rescan_files,
    infer_snippet_role_from_alignment,
)
from code2paper.agents.langgraph_utils import LangGraphAgent, extract_json, load_prompt
from code2paper.agents.logging_utils import log_agent_error, log_agent_info, log_agent_success, log_agent_warning


class CodeIntakeAgent:
    def __init__(self):
        self.name = "code_intake"
        self.llm_retrieval_plan_prompt = load_prompt("config/prompts/code_intake_retrieval_plan.txt")
        self.llm_review_prompt = load_prompt("config/prompts/code_intake_llm_review.txt")
        self.llm_review_enhanced_prompt = load_prompt("config/prompts/code_intake_llm_review_enhanced.txt")

    def __call__(self, state: PosterState) -> PosterState:
        log_agent_info(self.name, "starting code intake")

        try:
            output_dir = Path(state["output_dir"])
            content_dir = output_dir / "content"
            content_dir.mkdir(parents=True, exist_ok=True)

            repo_path = (state.get("repo_path") or "").strip() if isinstance(state.get("repo_path"), str) else ""
            files_path_list = state.get("files_path_list")
            manual_snippets = state.get("manual_snippets")

            if not repo_path and not files_path_list and not manual_snippets:
                report = {
                    "status": "fail",
                    "blocking_reasons": ["no_input"],
                    "coverage_check": {"roles_covered": [], "roles_missing": []},
                    "quality_check": {"oversized_files": [], "low_signal_files": [], "unparsable_snippets": []},
                    "consistency_check": {"method_keyword_hit_rate": 0.0, "suspicious_mismatch": False},
                    "budgets": {"files": 0, "bytes": 0, "snippet_lines": 0},
                    "recommended_actions": ["请提供 repo_path 或 files_path_list 或 manual_snippets"]
                }
                _save_json(content_dir / "code_intake_report.json", report)
                state["code_intake_report"] = report
                state["current_agent"] = self.name
                log_agent_warning(self.name, "no inputs provided, skipping code intake")
                return state

            if manual_snippets:
                core_snippets = _build_manual_core_snippets(manual_snippets)
                code_sources = {
                    "meta": {"repo_id": "", "root_path": None, "scan_time": None, "filters": {}, "scan_stats": {}},
                    "project_files": [],
                    "repo_structure_hints": {},
                    "errors": [],
                    "warnings": [],
                }
                budgets_used = {"files": 0, "bytes": 0, "snippet_lines": _count_snippet_lines(core_snippets)}
                report = _build_report(code_sources, core_snippets, budgets=budgets_used)
                report["budget_used"] = budgets_used

                _save_json(content_dir / "code_sources.json", code_sources)
                _save_json(content_dir / "core_snippets.json", core_snippets)
                _save_json(content_dir / "code_intake_report.json", report)

                state["code_sources"] = code_sources
                state["core_snippets"] = core_snippets
                state["code_intake_report"] = report
                state["current_agent"] = self.name
                log_agent_success(self.name, "manual snippets ingested")
                return state

            if files_path_list:
                code_sources = _build_code_sources_from_file_list(files_path_list)
                file_index = code_sources.get("project_files", [])
            else:
                filters = {"excluded_dirs": [".git", "__pycache__", ".venv", "venv", "node_modules", "build", "dist", "output", "hf"]}
                budgets = {"max_total_files": 160, "max_total_bytes": 20 * 1024 * 1024, "max_single_file_bytes": 768 * 1024}
                code_sources = scan_repo(repo_path, filters=filters, budgets=budgets)
                file_index = code_sources.get("project_files", [])
                if not file_index:
                    core_snippets = build_core_snippets([])
                    budgets_used = {"files": 0, "bytes": 0, "snippet_lines": 0}
                    report = _build_report(code_sources, core_snippets, budgets=budgets_used)
                    report["budget_used"] = budgets_used
                    _save_json(content_dir / "code_sources.json", code_sources)
                    _save_json(content_dir / "core_snippets.json", core_snippets)
                    _save_json(content_dir / "code_intake_report.json", report)
                    state["code_sources"] = code_sources
                    state["core_snippets"] = core_snippets
                    state["code_intake_report"] = report
                    state["current_agent"] = self.name
                    return state

            method_summary = state.get("method_experiment_structured_summary") or {}
            paper_objects = state.get("paper_objects") or {}
            structured_sections = state.get("structured_sections") or {}

            dynamic_roles = extract_dynamic_roles(method_summary)
            keyword_bank, role_keywords_map = build_method_keyword_bank_enhanced(structured_sections, method_summary)

            retrieval_hints = method_summary.get("retrieval_hints", {}) if isinstance(method_summary, dict) else {}
            priority_paths = [str(x) for x in retrieval_hints.get("priority_paths", []) if str(x).strip()] if isinstance(retrieval_hints, dict) else []
            symbol_targets = list(retrieval_hints.get("symbol_targets", [])) if isinstance(retrieval_hints, dict) and isinstance(retrieval_hints.get("symbol_targets"), list) else []
            orchestrator_targets = derive_orchestrator_symbol_targets(file_index, priority_paths)
            symbol_targets.extend(orchestrator_targets)

            config = state.get("config", {}) or {}
            code_intake_config = config.get("code_intake", {}) if isinstance(config, dict) else {}
            enable_plan = state.get("enable_code_intake_llm_retrieval_planning", state.get("enable_code_intake_llm_review", True))
            llm_plan = None
            plan_in = plan_out = 0
            if enable_plan:
                llm_plan, plan_in, plan_out = self._llm_retrieval_plan(
                    code_sources=code_sources,
                    method_summary=method_summary,
                    structured_sections=structured_sections,
                    keyword_bank=keyword_bank,
                    state=state,
                )
                if llm_plan and llm_plan.get("status") != "blocked":
                    priority_paths.extend(str(x) for x in llm_plan.get("priority_files", []) if str(x).strip())
                    symbol_targets.extend(item for item in llm_plan.get("symbol_targets", []) if isinstance(item, dict))
                    keyword_bank.extend(str(x) for x in llm_plan.get("search_keywords", []) if str(x).strip())

            candidate_files = select_candidate_files(file_index, keyword_bank, top_k=120)
            priority_candidates = [
                item for item in file_index
                if any(str(item.get("path") or "").replace("\\", "/").endswith(path.replace("\\", "/")) for path in priority_paths)
            ]
            candidate_files = _dedupe_candidate_files(priority_candidates + candidate_files)
            snippet_budget = code_intake_config.get("snippet_budget", {}) if isinstance(code_intake_config, dict) else {}
            llm_review_config = code_intake_config.get("llm_review", {}) if isinstance(code_intake_config, dict) else {}
            alignment_config = code_intake_config.get("method_alignment", {}) if isinstance(code_intake_config, dict) else {}

            max_total_lines = int(snippet_budget.get("max_total_snippet_lines", 4000))
            max_single_lines = int(snippet_budget.get("max_single_snippet_lines", 300))
            top_k_per_role = int(snippet_budget.get("top_k_per_role", 12))

            snippets = extract_snippets(
                candidate_files,
                rules={},
                budgets={
                    "max_total_snippet_lines": max_total_lines,
                    "max_single_snippet_lines": max_single_lines,
                    "top_k_per_role": top_k_per_role,
                },
                dynamic_roles=dynamic_roles,
                role_keywords_map=role_keywords_map,
            )
            symbol_snippets = extract_symbol_snippets(
                file_index,
                symbol_targets,
                budgets={"max_single_snippet_lines": max_single_lines},
            )
            snippets = _merge_snippets(symbol_snippets, snippets)
            core_snippets = build_core_snippets(snippets, dynamic_roles)

            budgets_used = {
                "files": code_sources.get("meta", {}).get("scan_stats", {}).get("scanned_files", 0),
                "bytes": code_sources.get("meta", {}).get("scan_stats", {}).get("scanned_bytes", 0),
                "snippet_lines": _count_snippet_lines(core_snippets),
            }

            alignment = align_method_to_code(method_summary, paper_objects, core_snippets, dynamic_roles)

            max_iterations = int(llm_review_config.get("max_iterations", 3))
            min_coverage = float(alignment_config.get("min_coverage_score", 0.7))
            auto_rescan = alignment_config.get("auto_rescan", True)

            iteration_count = 0
            coverage_score = alignment.get("coverage_report", {}).get("overall_score", 0)

            while coverage_score < min_coverage and iteration_count < max_iterations and auto_rescan:
                iteration_count += 1
                log_agent_info(self.name, f"alignment iteration {iteration_count}, coverage={coverage_score:.2f}")

                rescan_paths = extract_rescan_files(alignment)
                if not rescan_paths:
                    missing = alignment.get("coverage_report", {}).get("missing_implementations", [])
                    for m in missing:
                        if isinstance(m, dict) and m.get("suggested_file"):
                            rescan_paths.append(m["suggested_file"])

                if not rescan_paths:
                    break

                rescan_candidates = _match_rescan_files(file_index, rescan_paths)
                if not rescan_candidates:
                    break

                extra_snippets = extract_snippets(
                    rescan_candidates,
                    rules={},
                    budgets={
                        "max_total_snippet_lines": 1500,
                        "max_single_snippet_lines": max_single_lines,
                        "top_k_per_role": 6,
                    },
                    dynamic_roles=dynamic_roles,
                    role_keywords_map=role_keywords_map,
                )

                merged = _merge_snippets(core_snippets.get("snippets", []), extra_snippets)
                core_snippets = build_core_snippets(merged, dynamic_roles)

                alignment = align_method_to_code(method_summary, paper_objects, core_snippets, dynamic_roles)
                coverage_score = alignment.get("coverage_report", {}).get("overall_score", 0)

                budgets_used["snippet_lines"] = _count_snippet_lines(core_snippets)

            core_snippets = fill_relevance_from_alignment(core_snippets, alignment)

            for sn in core_snippets.get("snippets", []):
                if not isinstance(sn, dict):
                    continue
                new_role = infer_snippet_role_from_alignment(sn, alignment, dynamic_roles)
                if new_role != sn.get("role"):
                    sn["role"] = new_role

            report = _build_report(
                code_sources,
                core_snippets,
                budgets=budgets_used,
                dynamic_roles=dynamic_roles,
            )
            report["budget_used"] = budgets_used
            report["method_code_alignment"] = {
                "coverage_score": coverage_score,
                "iterations": iteration_count,
                "dynamic_roles": list(dynamic_roles),
            }
            report["author_guided_retrieval"] = {
                "priority_paths": list(dict.fromkeys(priority_paths)),
                "symbol_targets_requested": len(symbol_targets),
                "symbol_snippets_found": len(symbol_snippets),
                "orchestrator_symbol_targets_added": len(orchestrator_targets),
            }
            report["llm_retrieval_planning"] = {
                "enabled": bool(enable_plan),
                "llm_used": bool(llm_plan and llm_plan.get("status") != "blocked"),
                "status": str((llm_plan or {}).get("status") or ("disabled" if not enable_plan else "blocked")),
                "input_tokens": plan_in,
                "output_tokens": plan_out,
                "symbol_targets_added": len((llm_plan or {}).get("symbol_targets", [])),
            }

            review_overrides = {}
            llm_review = None
            inp_tok = 0
            out_tok = 0
            if state.get("enable_code_intake_llm_review", True):
                llm_review, inp_tok, out_tok = self._llm_review_enhanced(
                    code_sources, core_snippets, method_summary, paper_objects, alignment, dynamic_roles, state
                )
            if llm_review:
                report["code_intake_llm_review"] = llm_review
                overrides = llm_review.get("snippet_role_overrides") if isinstance(llm_review, dict) else None
                if isinstance(overrides, dict):
                    review_overrides = {k: v for k, v in overrides.items() if isinstance(k, str) and isinstance(v, str)}
            if inp_tok or out_tok:
                state["tokens"].add_text(inp_tok, out_tok)

            if review_overrides:
                core_snippets["snippets"] = apply_role_overrides(
                    core_snippets.get("snippets", []), review_overrides, dynamic_roles
                )

            _save_json(content_dir / "code_sources.json", code_sources)
            _save_json(content_dir / "core_snippets.json", core_snippets)
            _save_json(content_dir / "code_intake_report.json", report)
            _save_json(content_dir / "method_code_alignment.json", alignment)

            state["code_sources"] = code_sources
            state["core_snippets"] = core_snippets
            state["code_intake_report"] = report
            state["method_code_alignment"] = alignment
            state["dynamic_roles"] = list(dynamic_roles)
            state["current_agent"] = self.name

            log_agent_success(self.name, f"selected {len(core_snippets.get('snippets', []))} snippets, coverage={coverage_score:.2f}")
            return state

        except Exception as e:
            log_agent_error(self.name, f"failed: {e}")
            state["errors"].append(f"{self.name}: {e}")
            return state

    def _llm_retrieval_plan(
        self,
        *,
        code_sources: Dict[str, Any],
        method_summary: Dict[str, Any],
        structured_sections: Dict[str, Any],
        keyword_bank: List[str],
        state: PosterState,
    ) -> Tuple[Optional[Dict[str, Any]], int, int]:
        if not self.llm_retrieval_plan_prompt:
            return None, 0, 0
        agent = LangGraphAgent("evidence retrieval planner", state["text_model"], state, "code_intake_retrieval")
        prompt = Template(self.llm_retrieval_plan_prompt).render(
            retrieval_goal="Find direct implementation evidence only.",
            method_summary=json.dumps(method_summary, ensure_ascii=False)[:12000],
            structured_sections=json.dumps(structured_sections, ensure_ascii=False)[:8000],
            repo_structure=json.dumps(code_sources.get("repo_structure_hints") or {}, ensure_ascii=False)[:6000],
            file_preview=json.dumps(code_sources.get("project_files", [])[:220], ensure_ascii=False)[:14000],
            existing_keyword_bank=json.dumps(keyword_bank[:120], ensure_ascii=False),
        )
        for _attempt in range(3):
            try:
                agent.reset()
                response = agent.step(prompt)
                result = extract_json(response.content)
                if isinstance(result, dict):
                    result.setdefault("status", "ok")
                    result.setdefault("priority_files", [])
                    result.setdefault("symbol_targets", [])
                    return result, response.input_tokens, response.output_tokens
            except Exception as exc:
                last_error = exc
        log_agent_warning(self.name, f"llm_retrieval_plan failed: {last_error}")
        return {"status": "blocked", "blocked_reason": str(last_error)}, 0, 0

    def _llm_review(
        self, code_sources: Dict[str, Any], core_snippets: Dict[str, Any], keyword_bank: List[str], state: PosterState
    ) -> Tuple[Optional[Dict[str, Any]], int, int]:
        if not self.llm_review_prompt:
            return None, 0, 0

        snippets = core_snippets.get("snippets") or []
        snippet_preview = []
        for sn in snippets[:20]:
            if not isinstance(sn, dict):
                continue
            text = sn.get("text") or ""
            preview = "\n".join(text.splitlines()[:20])
            snippet_preview.append({
                "snippet_id": sn.get("snippet_id"),
                "role": sn.get("role"),
                "source": sn.get("source"),
                "preview": preview,
            })

        agent = LangGraphAgent("expert code intake reviewer", state["text_model"], state, "code_intake")
        prompt = Template(self.llm_review_prompt).render(
            code_sources=json.dumps({
                "meta": code_sources.get("meta"),
                "repo_structure_hints": code_sources.get("repo_structure_hints"),
            }, ensure_ascii=False),
            snippet_preview=json.dumps(snippet_preview, ensure_ascii=False),
            keyword_bank=json.dumps(keyword_bank[:80], ensure_ascii=False),
        )
        try:
            agent.reset()
            response = agent.step(prompt)
            result = extract_json(response.content)
            if isinstance(result, dict):
                return result, response.input_tokens, response.output_tokens
            return None, response.input_tokens, response.output_tokens
        except Exception as e:
            log_agent_warning(self.name, f"llm_review failed: {e}")
            return None, 0, 0

    def _llm_review_enhanced(
        self,
        code_sources: Dict[str, Any],
        core_snippets: Dict[str, Any],
        method_summary: Dict[str, Any],
        paper_objects: Dict[str, Any],
        alignment: Dict[str, Any],
        dynamic_roles: Set[str],
        state: PosterState,
    ) -> Tuple[Optional[Dict[str, Any]], int, int]:
        if not self.llm_review_enhanced_prompt:
            return self._llm_review(code_sources, core_snippets, [], state)

        config = state.get("config", {}) or {}
        code_intake_config = config.get("code_intake", {}) if isinstance(config, dict) else {}
        llm_review_config = code_intake_config.get("llm_review", {}) if isinstance(code_intake_config, dict) else {}

        max_snippets = int(llm_review_config.get("max_snippets_preview", 40))
        max_lines = int(llm_review_config.get("max_lines_per_snippet", 40))

        snippets = core_snippets.get("snippets") or []
        snippet_preview = []
        for sn in snippets[:max_snippets]:
            if not isinstance(sn, dict):
                continue
            text = sn.get("text") or ""
            preview = "\n".join(text.splitlines()[:max_lines])
            snippet_preview.append({
                "snippet_id": sn.get("snippet_id"),
                "role": sn.get("role"),
                "source": sn.get("source"),
                "relevance": sn.get("relevance"),
                "preview": preview,
            })

        method = method_summary.get("method", {}) if isinstance(method_summary, dict) else {}
        pseudo_codes = paper_objects.get("pseudo_code", []) if isinstance(paper_objects, dict) else []
        pseudo_code_text = ""
        for pc in pseudo_codes[:2]:
            if isinstance(pc, dict):
                pseudo_code_text += str(pc.get("code_text", ""))[:2000] + "\n\n"

        algorithm_text = ""
        equations = paper_objects.get("equations", []) if isinstance(paper_objects, dict) else []
        for eq in equations:
            if isinstance(eq, dict) and "Algorithm" in str(eq.get("text", "")):
                algorithm_text = str(eq.get("text", ""))[:1500]
                break

        current_alignment = {
            "coverage_score": alignment.get("coverage_report", {}).get("overall_score", 0),
            "modules_found": sum(1 for m in alignment.get("modules", []) if m.get("matched_snippets")),
            "steps_found": sum(1 for s in alignment.get("pipeline_steps", []) if s.get("matched_snippets")),
        }

        agent = LangGraphAgent("expert code intake reviewer", state["text_model"], state, "code_intake")
        prompt = Template(self.llm_review_enhanced_prompt).render(
            method_summary=json.dumps(method, ensure_ascii=False)[:4000],
            pseudo_code=pseudo_code_text[:3000],
            algorithm_text=algorithm_text[:2000],
            snippet_preview=json.dumps(snippet_preview, ensure_ascii=False)[:8000],
            current_alignment=json.dumps(current_alignment, ensure_ascii=False),
            dynamic_roles=json.dumps(sorted(list(dynamic_roles)), ensure_ascii=False),
        )
        last_error: Exception | None = None
        for _attempt in range(3):
            try:
                agent.reset()
                response = agent.step(prompt)
                result = extract_json(response.content)
                if isinstance(result, dict):
                    return result, response.input_tokens, response.output_tokens
            except Exception as exc:
                last_error = exc
        log_agent_warning(self.name, f"llm_review_enhanced failed: {last_error}")
        return None, 0, 0


def build_core_snippets(snippets: List[Dict[str, Any]], dynamic_roles: Optional[Set[str]] = None) -> Dict[str, Any]:
    base_roles = {"forward", "model_arch", "loss", "augmentation", "dataset", "training_loop", "config", "inference", "evaluation", "other"}
    all_roles = base_roles | (dynamic_roles or set())

    roles_covered = sorted({sn.get("role") for sn in snippets if isinstance(sn, dict) and sn.get("role")})
    roles_missing = sorted(list(all_roles - set(roles_covered)))

    by_file: Dict[str, int] = {}
    for sn in snippets:
        src = sn.get("source") if isinstance(sn, dict) else None
        path = src.get("path") if isinstance(src, dict) else None
        if path:
            by_file[path] = by_file.get(path, 0) + 1

    top_files = sorted(by_file.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "meta": {"selection_version": "v2", "selection_budget": {}, "selection_rules": {}},
        "snippets": snippets,
        "coverage": {
            "roles_covered": roles_covered,
            "roles_missing": roles_missing,
            "top_files_by_snippet_count": [p for p, _ in top_files],
            "dynamic_roles": list(dynamic_roles) if dynamic_roles else [],
        },
        "warnings": [],
    }


def _match_rescan_files(file_index: List[Dict[str, Any]], paths: List[str]) -> List[Dict[str, Any]]:
    if not paths:
        return []
    out = []
    for f in file_index:
        if not isinstance(f, dict):
            continue
        p = f.get("path")
        if not isinstance(p, str):
            continue
        if any(p.startswith(rp) or rp in p for rp in paths):
            out.append(f)
    return out


def _merge_snippets(base: List[Dict[str, Any]], extra: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    merged = []
    for sn in base + extra:
        if not isinstance(sn, dict):
            continue
        src = sn.get("source") if isinstance(sn.get("source"), dict) else {}
        key = (sn.get("role"), src.get("path"), src.get("start_line"), src.get("end_line"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(sn)
    return merged


def _dedupe_candidate_files(files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: Set[str] = set()
    result: List[Dict[str, Any]] = []
    for item in files:
        path = str(item.get("path") or "") if isinstance(item, dict) else ""
        if not path or path in seen:
            continue
        seen.add(path)
        result.append(item)
    return result


def _build_report(
    code_sources: Dict[str, Any],
    core_snippets: Dict[str, Any],
    budgets: Dict[str, Any],
    dynamic_roles: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    roles_covered = (core_snippets.get("coverage") or {}).get("roles_covered") or []
    roles_missing = (core_snippets.get("coverage") or {}).get("roles_missing") or []

    status = "pass"
    blocking_reasons = []
    if not roles_covered:
        status = "fail"
        blocking_reasons.append("no_snippets")
    elif ("forward" not in roles_covered) and ("model_arch" not in roles_covered):
        status = "warn"

    scan_warnings = code_sources.get("warnings") or []
    if scan_warnings and status == "pass":
        status = "warn"

    recommended_actions = []
    if status == "warn" and ("forward" not in roles_covered) and ("model_arch" not in roles_covered):
        recommended_actions.append("请提供模型定义文件路径（含 forward）")

    return {
        "status": status,
        "blocking_reasons": blocking_reasons,
        "coverage_check": {"roles_covered": roles_covered, "roles_missing": roles_missing, "notes": "", "dynamic_roles": list(dynamic_roles) if dynamic_roles else []},
        "quality_check": {"oversized_files": [], "low_signal_files": [], "unparsable_snippets": []},
        "consistency_check": {"method_keyword_hit_rate": 0.0, "suspicious_mismatch": False},
        "budgets": budgets,
        "recommended_actions": recommended_actions,
    }


def _build_manual_core_snippets(manual_snippets: Any) -> Dict[str, Any]:
    snippets = []
    if isinstance(manual_snippets, str):
        text = manual_snippets.strip()
        if text:
            snippets.append({
                "snippet_id": "manual_1",
                "role": "other",
                "source": {"path": "manual", "start_line": 1, "end_line": len(text.splitlines()), "sha1": ""},
                "text": text,
                "signals": ["manual"],
                "relevance": {"paper_section_ids": [], "score": 0.0, "reason": ""},
                "quality": {"parsable": True, "length_lines": len(text.splitlines()), "has_external_deps": False},
            })
    elif isinstance(manual_snippets, list):
        for i, item in enumerate(manual_snippets):
            if isinstance(item, str) and item.strip():
                text = item.strip()
                snippets.append({
                    "snippet_id": f"manual_{i+1}",
                    "role": "other",
                    "source": {"path": "manual", "start_line": 1, "end_line": len(text.splitlines()), "sha1": ""},
                    "text": text,
                    "signals": ["manual"],
                    "relevance": {"paper_section_ids": [], "score": 0.0, "reason": ""},
                    "quality": {"parsable": True, "length_lines": len(text.splitlines()), "has_external_deps": False},
                })
    return build_core_snippets(snippets)


def _count_snippet_lines(core_snippets: Dict[str, Any]) -> int:
    total = 0
    for sn in core_snippets.get("snippets") or []:
        if not isinstance(sn, dict):
            continue
        q = sn.get("quality")
        if isinstance(q, dict) and isinstance(q.get("length_lines"), int):
            total += q["length_lines"]
        else:
            text = sn.get("text") or ""
            total += len(str(text).splitlines())
    return total


def _save_json(path: Path, data: Dict[str, Any]):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def code_intake_node(state: PosterState) -> PosterState:
    return CodeIntakeAgent()(state)


def _build_code_sources_from_file_list(files_path_list: Any) -> Dict[str, Any]:
    paths = []
    warnings = []
    errors = []
    total_bytes = 0

    if isinstance(files_path_list, str):
        files = [files_path_list]
    elif isinstance(files_path_list, list):
        files = [p for p in files_path_list if isinstance(p, str)]
    else:
        files = []

    for raw in files[:200]:
        p = Path(raw).expanduser()
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        if not p.exists() or not p.is_file():
            warnings.append(f"missing_file:{str(p)}")
            continue
        try:
            st = p.stat()
        except Exception as e:
            errors.append(f"stat_failed:{str(p)}:{e}")
            continue
        total_bytes += st.st_size
        sha1 = _sha1_file(p)
        ext = p.suffix.lower()
        paths.append({
            "path": str(p),
            "ext": ext,
            "language": "python" if ext == ".py" else "unknown",
            "size_bytes": st.st_size,
            "sha1": sha1,
            "kind": "source",
        })

    return {
        "meta": {
            "repo_id": "",
            "root_path": None,
            "filters": {"mode": "files_path_list"},
            "scan_stats": {"scanned_files": len(paths), "scanned_bytes": total_bytes},
        },
        "project_files": paths,
        "repo_structure_hints": {},
        "errors": errors,
        "warnings": warnings,
    }


def _sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 64)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()
