from __future__ import annotations

import ast
import re
from typing import Any, Dict, List, Optional, Set


def analyze_modules(
    core_snippets: Dict[str, Any],
    method_code_alignment: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    模块分析: 从代码片段和对齐结果提取完整模块信息
    """
    modules = []
    snippets = core_snippets.get("snippets", [])
    snippet_map = {sn.get("snippet_id"): sn for sn in snippets if isinstance(sn, dict)}
    
    alignment_modules = method_code_alignment.get("modules", [])
    
    for am in alignment_modules:
        method_module = am.get("method_module", {})
        matched = am.get("matched_snippets", [])
        
        if not matched:
            continue
        
        first_match = matched[0]
        snippet_id = first_match.get("snippet_id")
        snippet = snippet_map.get(snippet_id, {})
        text = snippet.get("text", "") if isinstance(snippet, dict) else ""
        
        class_info = _extract_class_info(text)
        
        module = {
            "name": class_info.get("name") or first_match.get("class_name") or method_module.get("name", ""),
            "role": method_module.get("role") or _infer_role_from_name(method_module.get("name", "")),
            "method_ref": method_module.get("name", ""),
            "inheritance": class_info.get("inheritance", []),
            "interfaces": class_info.get("methods", [])[:5],
            "attributes": class_info.get("attributes", [])[:10],
            "methods": class_info.get("methods", [])[:10],
            "input_spec": _extract_input_spec(text),
            "output_spec": _extract_output_spec(text),
            "key_logic": _extract_key_logic(text, method_module.get("name", "")),
            "pseudo_code_ref": am.get("pseudo_code_ref"),
            "evidence_refs": [m.get("snippet_id") for m in matched if m.get("snippet_id")],
            "confidence": first_match.get("confidence", 0.5),
        }
        modules.append(module)
    
    for sn in snippets:
        if not isinstance(sn, dict):
            continue
        role = sn.get("role", "")
        if role in ["model_arch", "forward"]:
            sid = sn.get("snippet_id")
            if any(sid in m.get("evidence_refs", []) for m in modules):
                continue
            
            text = sn.get("text", "")
            class_info = _extract_class_info(text)
            
            if class_info.get("name"):
                modules.append({
                    "name": class_info.get("name"),
                    "role": role,
                    "method_ref": "",
                    "inheritance": class_info.get("inheritance", []),
                    "interfaces": class_info.get("methods", [])[:5],
                    "attributes": class_info.get("attributes", [])[:10],
                    "methods": class_info.get("methods", [])[:10],
                    "input_spec": _extract_input_spec(text),
                    "output_spec": _extract_output_spec(text),
                    "key_logic": _extract_key_logic(text, class_info.get("name", "")),
                    "pseudo_code_ref": None,
                    "evidence_refs": [sid],
                    "confidence": 0.6,
                })
    
    return modules


def analyze_pipeline_steps(
    core_snippets: Dict[str, Any],
    method_code_alignment: Dict[str, Any],
    modules: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    流程分析: 从对齐结果和模块信息构建完整 pipeline
    """
    pipeline_steps = []
    snippets = core_snippets.get("snippets", [])
    snippet_map = {sn.get("snippet_id"): sn for sn in snippets if isinstance(sn, dict)}
    
    alignment_steps = method_code_alignment.get("pipeline_steps", [])
    
    for i, as_ in enumerate(alignment_steps):
        method_step = as_.get("method_step", {})
        matched = as_.get("matched_snippets", [])
        
        step_id = method_step.get("step_id") or str(i + 1)
        step_name = method_step.get("name", "")
        step_desc = method_step.get("description", "")
        
        involved_modules = []
        key_operations = []
        evidence_refs = []
        
        for m in matched:
            sid = m.get("snippet_id")
            if sid:
                evidence_refs.append(sid)
                snippet = snippet_map.get(sid, {})
                if isinstance(snippet, dict):
                    class_name = _extract_class_name(snippet.get("text", ""))
                    if class_name and class_name not in involved_modules:
                        involved_modules.append(class_name)
        
        pipeline_steps.append({
            "step_id": step_id,
            "name": step_name,
            "description": step_desc,
            "input_data": _infer_step_input(step_name, i),
            "output_data": _infer_step_output(step_name, i),
            "involved_modules": involved_modules,
            "data_flow": _build_data_flow(step_name, involved_modules),
            "key_operations": _extract_key_operations(step_name),
            "algorithm_ref": method_step.get("algorithm_ref", ""),
            "evidence_refs": evidence_refs,
            "confidence": matched[0].get("confidence", 0.5) if matched else 0.3,
        })
    
    return pipeline_steps


def analyze_losses(
    core_snippets: Dict[str, Any],
    method_code_alignment: Dict[str, Any],
    paper_objects: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    损失分析: 从对齐结果和论文公式提取完整损失信息
    """
    losses = []
    snippets = core_snippets.get("snippets", [])
    snippet_map = {sn.get("snippet_id"): sn for sn in snippets if isinstance(sn, dict)}
    
    alignment_losses = method_code_alignment.get("losses", [])
    equations = paper_objects.get("equations", []) if isinstance(paper_objects, dict) else []
    equation_map = {eq.get("object_id"): eq for eq in equations if isinstance(eq, dict)}
    
    for al in alignment_losses:
        method_loss = al.get("method_loss", {})
        matched = al.get("matched_snippets", [])
        formula_ref = method_loss.get("formula_ref", "")
        
        formula_text = ""
        equation = equation_map.get(formula_ref, {})
        if isinstance(equation, dict):
            formula_text = equation.get("latex", "") or equation.get("text", "")
        
        evidence_refs = []
        implementation_func = ""
        computation_steps = []
        
        for m in matched:
            sid = m.get("snippet_id")
            if sid:
                evidence_refs.append(sid)
                snippet = snippet_map.get(sid, {})
                if isinstance(snippet, dict):
                    text = snippet.get("text", "")
                    func_name = _extract_function_name(text)
                    if func_name:
                        implementation_func = func_name
                    steps = _extract_computation_steps(text)
                    computation_steps.extend(steps)
        
        loss_name = method_loss.get("name", "")
        losses.append({
            "name": loss_name,
            "full_name": _get_full_loss_name(loss_name),
            "formula_ref": formula_ref,
            "formula_text": formula_text,
            "purpose": _infer_loss_purpose(loss_name),
            "inputs": _infer_loss_inputs(loss_name),
            "computation_steps": computation_steps[:5] if computation_steps else ["See implementation"],
            "implementation_function": implementation_func,
            "evidence_refs": evidence_refs,
            "confidence": matched[0].get("confidence", 0.5) if matched else 0.3,
        })
    
    for sn in snippets:
        if not isinstance(sn, dict):
            continue
        role = sn.get("role", "")
        if role == "loss":
            sid = sn.get("snippet_id")
            if any(sid in l.get("evidence_refs", []) for l in losses):
                continue
            
            text = sn.get("text", "")
            loss_names = _extract_loss_names(text)
            
            for ln in loss_names:
                losses.append({
                    "name": ln,
                    "full_name": _get_full_loss_name(ln),
                    "formula_ref": "",
                    "formula_text": "",
                    "purpose": _infer_loss_purpose(ln),
                    "inputs": _infer_loss_inputs(ln),
                    "computation_steps": ["See implementation"],
                    "implementation_function": _extract_function_name(text),
                    "evidence_refs": [sid],
                    "confidence": 0.5,
                })
    
    return losses


def analyze_training(
    core_snippets: Dict[str, Any],
) -> Dict[str, Any]:
    """
    训练分析: 从代码片段提取训练配置和循环结构
    """
    snippets = core_snippets.get("snippets", [])
    
    training_detail = {
        "type": "standard",
        "optimizer": {},
        "scheduler": {},
        "training_loop": {},
        "epochs": 0,
        "batch_size": 0,
        "evidence_refs": [],
    }
    
    training_snippets = []
    for sn in snippets:
        if not isinstance(sn, dict):
            continue
        role = sn.get("role", "")
        if role in ["training_loop", "outer_loop", "inner_loop"]:
            training_snippets.append(sn)
    
    if not training_snippets:
        return training_detail
    
    all_text = "\n".join([sn.get("text", "") for sn in training_snippets])
    evidence_refs = [sn.get("snippet_id") for sn in training_snippets if sn.get("snippet_id")]
    
    optimizers = _extract_optimizer_names(all_text)
    if optimizers:
        training_detail["optimizer"] = {"name": optimizers[0]}
    
    schedulers = _extract_scheduler_names(all_text)
    if schedulers:
        training_detail["scheduler"] = {"name": schedulers[0]}
    
    has_outer = any(sn.get("role") == "outer_loop" for sn in training_snippets)
    has_inner = any(sn.get("role") == "inner_loop" for sn in training_snippets)
    
    if has_outer and has_inner:
        training_detail["type"] = "bi-level optimization"
        training_detail["training_loop"] = {
            "outer_loop": {"target": "generator", "objective": "generation loss"},
            "inner_loop": {"target": "model", "objective": "task loss"},
        }
    
    epochs_match = re.search(r"epochs\s*[=:]\s*(\d+)", all_text, re.IGNORECASE)
    if epochs_match:
        training_detail["epochs"] = int(epochs_match.group(1))
    
    batch_match = re.search(r"batch[_\s]*size\s*[=:]\s*(\d+)", all_text, re.IGNORECASE)
    if batch_match:
        training_detail["batch_size"] = int(batch_match.group(1))
    
    training_detail["evidence_refs"] = evidence_refs
    
    return training_detail


def analyze_data(
    core_snippets: Dict[str, Any],
) -> Dict[str, Any]:
    """
    数据分析: 从代码片段提取数据集和数据加载信息
    """
    snippets = core_snippets.get("snippets", [])
    
    data_detail = {
        "datasets": [],
        "dataloader": {},
    }
    
    for sn in snippets:
        if not isinstance(sn, dict):
            continue
        role = sn.get("role", "")
        if role in ["dataset", "data_loading"]:
            text = sn.get("text", "")
            sid = sn.get("snippet_id")
            
            class_name = _extract_class_name(text)
            
            dataset = {
                "name": class_name or "Dataset",
                "type": "custom",
                "input_format": _infer_input_format(text),
                "output_format": _infer_output_format(text),
                "preprocessing": _extract_preprocessing(text),
                "augmentation": _extract_augmentation(text),
                "evidence_refs": [sid] if sid else [],
            }
            data_detail["datasets"].append(dataset)
            
            batch_match = re.search(r"batch[_\s]*size\s*[=:]\s*(\d+)", text, re.IGNORECASE)
            if batch_match:
                data_detail["dataloader"]["batch_size"] = int(batch_match.group(1))
    
    return data_detail


def validate_alignment(
    method_code_alignment: Dict[str, Any],
    modules: List[Dict[str, Any]],
    pipeline_steps: List[Dict[str, Any]],
    losses: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    对齐验证: 验证论文方法与代码的一致性
    """
    coverage = method_code_alignment.get("coverage_report", {})
    
    discrepancies = []
    for m in method_code_alignment.get("modules", []):
        completeness = m.get("implementation_completeness", {})
        for key, status in completeness.items():
            if status == "missing":
                discrepancies.append({
                    "aspect": key,
                    "paper_description": "Described in paper",
                    "code_implementation": "Not found in matched snippets",
                    "impact": "May affect functionality",
                    "confidence": 0.5,
                })
    
    missing = []
    for am in method_code_alignment.get("modules", []):
        if am.get("missing_implementation"):
            method_module = am.get("method_module", {})
            missing.append({
                "name": method_module.get("name", "Unknown"),
                "reason": "No matching code snippet found",
            })
    
    uncertainties = []
    for m in modules:
        if m.get("confidence", 0) < 0.7:
            uncertainties.append({
                "aspect": f"Module {m.get('name')}",
                "reason": "Low confidence in alignment",
                "suggestion": "Manual verification recommended",
            })
    
    return {
        "overall_score": coverage.get("overall_score", 0),
        "modules_coverage": coverage.get("modules_coverage", {}),
        "pipeline_coverage": coverage.get("pipeline_steps_coverage", {}),
        "losses_coverage": coverage.get("losses_coverage", {}),
        "discrepancies": discrepancies,
        "missing_implementations": missing,
        "uncertainties": uncertainties,
    }


def build_code_facts(
    core_snippets: Dict[str, Any],
    method_code_alignment: Dict[str, Any],
    paper_objects: Dict[str, Any],
    method_summary: Dict[str, Any],
    dynamic_roles: List[str],
) -> Dict[str, Any]:
    """
    构建完整的 code_facts（使用对齐结果，不重复提取）
    """
    modules = analyze_modules(core_snippets, method_code_alignment)
    pipeline_steps = analyze_pipeline_steps(core_snippets, method_code_alignment, modules)
    modules, pipeline_steps = _supplement_agentic_scan_facts(core_snippets, modules, pipeline_steps)
    losses = analyze_losses(core_snippets, method_code_alignment, paper_objects)
    training_detail = analyze_training(core_snippets)
    data_detail = analyze_data(core_snippets)
    alignment_validation = validate_alignment(method_code_alignment, modules, pipeline_steps, losses)
    
    key_insights = _extract_key_insights(modules, pipeline_steps, training_detail)
    diagram_hints = _build_diagram_hints(modules, pipeline_steps, losses)
    overview = build_code_overview(
        method_summary,
        modules,
        pipeline_steps,
        losses,
        training_detail,
        alignment_validation,
    )
    
    snippets = core_snippets.get("snippets", [])
    
    return {
        "meta": {
            "version": "v2",
            "producer": "code_analyzer",
            "total_snippets": len(snippets),
            "alignment_score": alignment_validation.get("overall_score", 0),
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


def _supplement_agentic_scan_facts(
    core_snippets: Dict[str, Any],
    modules: List[Dict[str, Any]],
    pipeline_steps: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Recover code-backed agent modules when author alignment is sparse."""

    snippets = [item for item in core_snippets.get("snippets", []) if isinstance(item, dict)]
    orchestrator_order: List[str] = []
    for snippet in snippets:
        text = str(snippet.get("text") or "")
        discovered = re.findall(r"\b([A-Z][A-Za-z0-9_]*(?:Agent|Processor))\s*\(", text)
        discovered.sort(key=lambda name: (not name.endswith("Agent"), text.find(name + "(")))
        for name in discovered:
            if name not in orchestrator_order:
                orchestrator_order.append(name)

    by_name = {str(item.get("name") or ""): item for item in modules if isinstance(item, dict)}
    class_snippets: Dict[str, Dict[str, Any]] = {}
    for snippet in snippets:
        text = str(snippet.get("text") or "")
        match = re.search(r"\bclass\s+([A-Z][A-Za-z0-9_]*)", text)
        if match:
            class_snippets[match.group(1)] = snippet

    for name in orchestrator_order:
        snippet = class_snippets.get(name)
        evidence_id = str((snippet or {}).get("snippet_id") or "")
        if name in by_name:
            if evidence_id:
                by_name[name]["evidence_refs"] = [evidence_id]
            continue
        by_name[name] = {
            "name": name,
            "role": "method_agent",
            "method_ref": "",
            "inheritance": [],
            "interfaces": [],
            "attributes": [],
            "methods": [],
            "input_spec": {},
            "output_spec": {},
            "key_logic": f"{name} participates in the code-backed orchestration flow.",
            "pseudo_code_ref": None,
            "evidence_refs": [evidence_id] if evidence_id else [],
            "confidence": 0.8 if evidence_id else 0.6,
        }

    ordered_modules = [by_name[name] for name in orchestrator_order if name in by_name]
    ordered_modules.extend(item for name, item in by_name.items() if name not in orchestrator_order)
    if not pipeline_steps and orchestrator_order:
        pipeline_steps = [
            {
                "step_id": str(index),
                "name": name,
                "description": f"Execute {name}.",
                "input_data": [],
                "output_data": [],
                "involved_modules": [name],
                "data_flow": [],
                "key_operations": [],
                "algorithm_ref": "",
                "evidence_refs": list(by_name[name].get("evidence_refs", [])),
                "confidence": by_name[name].get("confidence", 0.6),
            }
            for index, name in enumerate(orchestrator_order, start=1)
        ]
    return ordered_modules, pipeline_steps


def build_code_overview(
    method_summary: Dict[str, Any],
    modules: List[Dict[str, Any]],
    pipeline_steps: List[Dict[str, Any]],
    losses: List[Dict[str, Any]],
    training_detail: Dict[str, Any],
    alignment_validation: Dict[str, Any],
) -> Dict[str, Any]:
    method_section = method_summary.get("method", {}) if isinstance(method_summary, dict) else {}
    if not isinstance(method_section, dict):
        method_section = {}

    task_setting = str(method_section.get("task_setting") or "").strip()
    module_names = [
        str(item.get("name") or "").strip()
        for item in modules
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]
    step_names = [
        str(item.get("name") or "").strip()
        for item in pipeline_steps
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]
    loss_names = [
        str(item.get("name") or "").strip()
        for item in losses
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]

    optimizer = training_detail.get("optimizer", {}) if isinstance(training_detail, dict) else {}
    if not isinstance(optimizer, dict):
        optimizer = {}
    optimizer_name = str(optimizer.get("name") or "").strip()
    training_type = str((training_detail or {}).get("type") or "").strip() if isinstance(training_detail, dict) else ""

    score = alignment_validation.get("overall_score", 0.0) if isinstance(alignment_validation, dict) else 0.0
    discrepancies = alignment_validation.get("discrepancies", []) if isinstance(alignment_validation, dict) else []
    discrepancy_count = len(discrepancies) if isinstance(discrepancies, list) else 0

    implementation_parts = []
    if task_setting:
        implementation_parts.append(task_setting)
    if step_names:
        implementation_parts.append(f"The implementation follows {', '.join(step_names[:4])}.")
    if module_names:
        implementation_parts.append(f"Key code modules include {', '.join(module_names[:4])}.")

    architecture_parts = []
    if module_names:
        architecture_parts.append(f"The architecture is centered on {', '.join(module_names[:4])}.")
    if step_names:
        architecture_parts.append(f"End-to-end data flow is organized as {' -> '.join(step_names[:4])}.")

    training_parts = []
    if loss_names:
        training_parts.append(f"Optimization is driven by {', '.join(loss_names[:4])}.")
    if optimizer_name:
        training_parts.append(f"Detected optimizer: {optimizer_name}.")
    if training_type:
        training_parts.append(f"Training loop type: {training_type}.")
    if not training_parts and losses:
        training_parts.append("Training logic is partially evidenced by the detected loss implementations.")

    alignment_parts = [f"Paper-to-code alignment score is {float(score):.2f}."]
    alignment_parts.append(
        f"Mapped evidence covers {len(module_names)} modules, {len(step_names)} pipeline steps, and {len(loss_names)} losses."
    )
    if discrepancy_count:
        alignment_parts.append(f"{discrepancy_count} discrepancies or uncertainties remain in the current alignment pass.")

    return {
        "implementation_summary": " ".join(implementation_parts).strip(),
        "architecture_summary": " ".join(architecture_parts).strip(),
        "training_summary": " ".join(training_parts).strip(),
        "alignment_summary": " ".join(alignment_parts).strip(),
    }


def build_code_ir(code_facts: Dict[str, Any]) -> Dict[str, Any]:
    """
    构建 code_ir（用于图表生成）
    """
    nodes = []
    edges = []
    annotations = []
    node_ids = set()
    
    def add_node(node: Dict[str, Any]):
        nid = node.get("id")
        if not nid or nid in node_ids:
            return
        node_ids.add(nid)
        nodes.append(node)
    
    data_detail = code_facts.get("data_detail", {})
    if not isinstance(data_detail, dict):
        data_detail = {}
    datasets = data_detail.get("datasets", [])
    if not isinstance(datasets, list):
        datasets = []

    for d in datasets:
        if not isinstance(d, dict):
            continue
        name = d.get("name", "Dataset")
        add_node({
            "id": f"data:{name}",
            "type": "data",
            "label": name,
            "evidence_refs": d.get("evidence_refs", []),
        })
    
    if not any(n.get("type") == "data" for n in nodes):
        add_node({"id": "data:Input", "type": "data", "label": "Input", "evidence_refs": []})
    
    modules = code_facts.get("modules", [])
    if not isinstance(modules, list):
        modules = []
    for m in modules:
        if not isinstance(m, dict):
            continue
        name = m.get("name", "Module")
        add_node({
            "id": f"module:{name}",
            "type": "module",
            "label": name,
            "role": m.get("role", ""),
            "method_ref": m.get("method_ref", ""),
            "evidence_refs": m.get("evidence_refs", []),
        })
    
    losses = code_facts.get("losses", [])
    if not isinstance(losses, list):
        losses = []
    for l in losses:
        if not isinstance(l, dict):
            continue
        name = l.get("name", "Loss")
        add_node({
            "id": f"loss:{name}",
            "type": "loss",
            "label": name,
            "formula_ref": l.get("formula_ref", ""),
            "evidence_refs": l.get("evidence_refs", []),
        })
    
    training = code_facts.get("training_detail", {})
    if not isinstance(training, dict):
        training = {}
    optimizer = training.get("optimizer", {})
    if not isinstance(optimizer, dict):
        optimizer = {}
    opt = optimizer.get("name")
    if opt:
        add_node({
            "id": f"opt:{opt}",
            "type": "optimizer",
            "label": opt,
            "evidence_refs": training.get("evidence_refs", []),
        })
    
    data_nodes = [n for n in nodes if n.get("type") == "data"]
    module_nodes = [n for n in nodes if n.get("type") == "module"]
    loss_nodes = [n for n in nodes if n.get("type") == "loss"]
    opt_nodes = [n for n in nodes if n.get("type") == "optimizer"]
    
    pipeline_steps = code_facts.get("pipeline_steps", [])
    if not isinstance(pipeline_steps, list):
        pipeline_steps = []
    for step in pipeline_steps:
        if not isinstance(step, dict):
            continue
        data_flow = step.get("data_flow", [])
        if not isinstance(data_flow, list):
            continue
        for df in data_flow:
            if not isinstance(df, dict):
                continue
            from_id = df.get("from")
            to_id = df.get("to")
            if from_id and to_id:
                edges.append({
                    "from": from_id,
                    "to": to_id,
                    "label": df.get("op", ""),
                    "step_id": step.get("step_id", ""),
                })
    
    if not edges:
        if data_nodes and module_nodes:
            edges.append({"from": data_nodes[0]["id"], "to": module_nodes[0]["id"], "label": "input"})
        if module_nodes and loss_nodes:
            edges.append({"from": module_nodes[0]["id"], "to": loss_nodes[0]["id"], "label": "logits"})
    
    if loss_nodes and opt_nodes:
        edges.append({"from": loss_nodes[0]["id"], "to": opt_nodes[0]["id"], "label": "update"})
    
    for m in modules:
        if not isinstance(m, dict):
            continue
        if m.get("key_logic"):
            annotations.append({
                "target_id": f"module:{m.get('name')}",
                "note": m.get("key_logic"),
                "type": "description",
            })
    
    return {"nodes": nodes, "edges": edges, "annotations": annotations}


def build_entity_links(
    code_facts: Dict[str, Any],
    method_code_alignment: Dict[str, Any],
) -> Dict[str, Any]:
    """
    构建实体链接（论文-代码-图表关联）
    """
    links = []
    
    modules = code_facts.get("modules", [])
    if not isinstance(modules, list):
        modules = []
    for m in modules:
        if not isinstance(m, dict):
            continue
        name = m.get("name", "")
        method_ref = m.get("method_ref", "")
        evidence_refs = m.get("evidence_refs", [])
        if not isinstance(evidence_refs, list):
            evidence_refs = []
        
        if method_ref:
            links.append({
                "source_type": "paper_method",
                "source_id": method_ref,
                "target_type": "code_module",
                "target_id": name,
                "confidence": m.get("confidence", 0.5),
                "note": f"Module {name} implements {method_ref}",
            })
        
        for ev in evidence_refs:
            links.append({
                "source_type": "code_module",
                "source_id": name,
                "target_type": "snippet",
                "target_id": ev,
                "confidence": 0.8,
                "note": f"Module {name} defined in {ev}",
            })
    
    losses = code_facts.get("losses", [])
    if not isinstance(losses, list):
        losses = []
    for l in losses:
        if not isinstance(l, dict):
            continue
        name = l.get("name", "")
        formula_ref = l.get("formula_ref", "")
        evidence_refs = l.get("evidence_refs", [])
        if not isinstance(evidence_refs, list):
            evidence_refs = []
        
        if formula_ref:
            links.append({
                "source_type": "paper_equation",
                "source_id": formula_ref,
                "target_type": "code_loss",
                "target_id": name,
                "confidence": l.get("confidence", 0.5),
                "note": f"Loss {name} implements {formula_ref}",
            })
        
        for ev in evidence_refs:
            links.append({
                "source_type": "code_loss",
                "source_id": name,
                "target_type": "snippet",
                "target_id": ev,
                "confidence": 0.8,
                "note": f"Loss {name} defined in {ev}",
            })
    
    pipeline_steps = code_facts.get("pipeline_steps", [])
    if not isinstance(pipeline_steps, list):
        pipeline_steps = []
    for step in pipeline_steps:
        if not isinstance(step, dict):
            continue
        step_id = step.get("step_id", "")
        step_name = step.get("name", "")
        evidence_refs = step.get("evidence_refs", [])
        if not isinstance(evidence_refs, list):
            evidence_refs = []
        
        for ev in evidence_refs:
            links.append({
                "source_type": "pipeline_step",
                "source_id": step_id,
                "target_type": "snippet",
                "target_id": ev,
                "confidence": 0.7,
                "note": f"Step {step_name} implemented in {ev}",
            })
    
    return {"meta": {"version": "v2", "producer": "code_analyzer"}, "links": links}


def _extract_class_info(text: str) -> Dict[str, Any]:
    """从代码文本提取类信息"""
    info = {"name": "", "inheritance": [], "attributes": [], "methods": []}
    
    class_match = re.search(r"class\s+(\w+)\s*\(([^)]*)\)", text)
    if class_match:
        info["name"] = class_match.group(1)
        inheritance = class_match.group(2).strip()
        if inheritance:
            info["inheritance"] = [i.strip() for i in inheritance.split(",")]
    
    attr_matches = re.findall(r"self\.(\w+)\s*=", text)
    info["attributes"] = list(set(attr_matches))[:10]
    
    method_matches = re.findall(r"def\s+(\w+)\s*\(", text)
    info["methods"] = list(set(method_matches))[:10]
    
    return info


def _extract_class_name(text: str) -> str:
    """从代码文本提取类名"""
    match = re.search(r"class\s+(\w+)", text)
    if match:
        return match.group(1)
    return ""


def _extract_function_name(text: str) -> str:
    """从代码文本提取函数名"""
    match = re.search(r"def\s+(\w+)\s*\(", text)
    if match:
        return match.group(1)
    return ""


def _extract_input_spec(text: str) -> Dict[str, str]:
    """提取输入规格"""
    spec = {}
    forward_match = re.search(r"def\s+forward\s*\(([^)]+)\)", text)
    if forward_match:
        params = forward_match.group(1)
        for param in params.split(","):
            param = param.strip()
            if param and param != "self":
                if ":" in param:
                    name, ptype = param.split(":", 1)
                    spec[name.strip()] = ptype.strip()
                else:
                    spec[param] = "Tensor"
    return spec


def _extract_output_spec(text: str) -> Dict[str, str]:
    """提取输出规格"""
    spec = {}
    return_match = re.search(r"return\s+(.+)", text)
    if return_match:
        returns = return_match.group(1).strip()
        spec["return"] = returns
    return spec


def _extract_key_logic(text: str, name: str) -> str:
    """提取关键逻辑描述"""
    lines = text.split("\n")
    comments = [l.strip() for l in lines if l.strip().startswith("#")]
    if comments:
        return " ".join(comments[:2])
    
    if "siren" in name.lower() or "sine" in text.lower():
        return "SIREN-based implicit neural representation with sine activation"
    if "rotator" in name.lower() or "invariant" in name.lower():
        return "Rotation-invariant transformation with sign disambiguation"
    if "wrapper" in name.lower() or "modulator" in name.lower():
        return "Class-conditional modulation wrapper"
    
    return ""


def _infer_role_from_name(name: str) -> str:
    """从名称推断角色"""
    name_lower = name.lower()
    if "siren" in name_lower or "generator" in name_lower:
        return "generator"
    if "rotator" in name_lower or "invariant" in name_lower:
        return "rotator"
    if "wrapper" in name_lower or "modulator" in name_lower:
        return "modulator"
    if "loss" in name_lower:
        return "loss"
    if "dataset" in name_lower:
        return "dataset"
    return "module"


def _infer_step_input(step_name: str, index: int) -> List[str]:
    """推断步骤输入"""
    name_lower = step_name.lower()
    if "canonicalization" in name_lower or index == 0:
        return ["raw_point_cloud"]
    if "generation" in name_lower:
        return ["random_noise", "class_label"]
    if "distillation" in name_lower or "gradient" in name_lower:
        return ["synthetic_data", "real_data"]
    return [f"input_{index}"]


def _infer_step_output(step_name: str, index: int) -> List[str]:
    """推断步骤输出"""
    name_lower = step_name.lower()
    if "canonicalization" in name_lower:
        return ["canonical_repr"]
    if "generation" in name_lower:
        return ["synthetic_point_cloud"]
    if "distillation" in name_lower or "gradient" in name_lower:
        return ["loss_value"]
    return [f"output_{index}"]


def _build_data_flow(step_name: str, modules: List[str]) -> List[Dict[str, str]]:
    """构建数据流"""
    flow = []
    if modules:
        flow.append({"from": "input", "to": modules[0], "op": "forward"})
        if len(modules) > 1:
            for i in range(len(modules) - 1):
                flow.append({"from": modules[i], "to": modules[i + 1], "op": "forward"})
        flow.append({"from": modules[-1], "to": "output", "op": "output"})
    return flow


def _extract_key_operations(step_name: str) -> List[str]:
    """提取关键操作"""
    name_lower = step_name.lower()
    if "canonicalization" in name_lower:
        return ["PCA projection", "Sign disambiguation", "Rotation matrix computation"]
    if "generation" in name_lower:
        return ["Class embedding lookup", "Feature modulation", "SIREN forward pass"]
    if "distillation" in name_lower or "gradient" in name_lower:
        return ["Forward pass", "Gradient computation", "Gradient matching"]
    return []


def _extract_loss_names(text: str) -> List[str]:
    """提取损失名称"""
    low = text.lower()
    found = []
    mapping = [
        ("crossentropy", "CrossEntropy"),
        ("bcewithlogits", "BCEWithLogits"),
        ("mse", "MSE"),
        ("l1", "L1"),
        ("focal", "Focal"),
        ("dice", "Dice"),
        ("contrastive", "Contrastive"),
        ("triplet", "Triplet"),
        ("match_loss", "GradientMatching"),
        ("gradient", "GradientMatching"),
    ]
    for key, name in mapping:
        if key in low:
            found.append(name)
    return found[:3]


def _get_full_loss_name(name: str) -> str:
    """获取损失全名"""
    mapping = {
        "CrossEntropy": "Cross Entropy Loss",
        "BCEWithLogits": "Binary Cross Entropy with Logits",
        "MSE": "Mean Squared Error Loss",
        "Dice": "Dice Loss",
        "Focal": "Focal Loss",
        "GradientMatching": "Gradient Matching Loss",
        "L_shape": "Shape Classification Distillation Loss",
        "L_part": "Part Segmentation Distillation Loss",
    }
    return mapping.get(name, name)


def _infer_loss_purpose(name: str) -> str:
    """推断损失用途"""
    name_lower = name.lower()
    if "shape" in name_lower or "cls" in name_lower:
        return "Shape classification distillation"
    if "part" in name_lower or "seg" in name_lower:
        return "Part segmentation distillation"
    if "gradient" in name_lower or "match" in name_lower:
        return "Gradient matching for knowledge distillation"
    if "crossentropy" in name_lower:
        return "Classification loss"
    if "dice" in name_lower:
        return "Segmentation loss"
    return "Training objective"


def _infer_loss_inputs(name: str) -> List[str]:
    """推断损失输入"""
    name_lower = name.lower()
    if "gradient" in name_lower or "match" in name_lower:
        return ["synthetic_logits", "real_logits", "labels"]
    if "seg" in name_lower or "part" in name_lower:
        return ["predictions", "part_labels"]
    return ["predictions", "labels"]


def _extract_computation_steps(text: str) -> List[str]:
    """提取计算步骤"""
    steps = []
    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        if line.startswith("#"):
            steps.append(line[1:].strip())
        elif "=" in line and not line.startswith("def"):
            var = line.split("=")[0].strip()
            if var and not var.startswith("self"):
                steps.append(f"Compute {var}")
    return steps[:5]


def _extract_optimizer_names(text: str) -> List[str]:
    """提取优化器名称"""
    low = text.lower()
    found = []
    for name in ["adamw", "adam", "sgd", "rmsprop", "adagrad"]:
        if name in low:
            found.append(name.upper() if name != "adamw" else "AdamW")
    return found[:2]


def _extract_scheduler_names(text: str) -> List[str]:
    """提取调度器名称"""
    low = text.lower()
    found = []
    for name in ["cosineannealing", "steplr", "reducelronplateau", "onecyclelr"]:
        if name in low:
            found.append(name)
    return found[:2]


def _infer_input_format(text: str) -> str:
    """推断输入格式"""
    if "point" in text.lower():
        return "point cloud P ∈ R^{N×3}"
    if "image" in text.lower():
        return "image Tensor[B, C, H, W]"
    return "Tensor"


def _infer_output_format(text: str) -> str:
    """推断输出格式"""
    if "label" in text.lower() or "class" in text.lower():
        return "Tensor + label"
    if "seg" in text.lower():
        return "Tensor + part labels"
    return "Tensor"


def _extract_preprocessing(text: str) -> List[str]:
    """提取预处理步骤"""
    steps = []
    low = text.lower()
    if "normalize" in low:
        steps.append("normalize")
    if "center" in low:
        steps.append("center")
    if "pca" in low:
        steps.append("PCA projection")
    if "resize" in low:
        steps.append("resize")
    return steps


def _extract_augmentation(text: str) -> List[str]:
    """提取数据增强"""
    augs = []
    low = text.lower()
    if "rotation" in low or "rotate" in low:
        augs.append("random_rotation")
    if "jitter" in low:
        augs.append("jitter")
    if "scale" in low:
        augs.append("scaling")
    if "flip" in low:
        augs.append("flip")
    return augs


def _extract_key_insights(
    modules: List[Dict[str, Any]],
    pipeline_steps: List[Dict[str, Any]],
    training_detail: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """提取关键洞察"""
    insights = []
    
    if training_detail.get("type") == "bi-level optimization":
        insights.append({
            "insight": "The method uses bi-level optimization with outer/inner loops",
            "evidence_refs": training_detail.get("evidence_refs", []),
            "importance": "high",
        })
    
    for m in modules:
        if "siren" in m.get("name", "").lower():
            insights.append({
                "insight": "SIREN-based INR enables resolution-flexible generation",
                "evidence_refs": m.get("evidence_refs", []),
                "importance": "high",
            })
            break
    
    for m in modules:
        if "rotator" in m.get("role", "").lower() or "invariant" in m.get("name", "").lower():
            insights.append({
                "insight": "Sign disambiguation solves the 8-fold PCA ambiguity problem",
                "evidence_refs": m.get("evidence_refs", []),
                "importance": "medium",
            })
            break
    
    return insights


def _build_diagram_hints(
    modules: List[Dict[str, Any]],
    pipeline_steps: List[Dict[str, Any]],
    losses: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """构建图表提示"""
    key_nodes = []
    for m in modules:
        if m.get("confidence", 0) > 0.6:
            key_nodes.append(m.get("name", ""))
    
    key_edges = []
    for step in pipeline_steps:
        data_flow = step.get("data_flow", [])
        for df in data_flow[:2]:
            key_edges.append({
                "from": df.get("from", ""),
                "to": df.get("to", ""),
            })
    
    main_flow = []
    for step in pipeline_steps:
        modules_in_step = step.get("involved_modules", [])
        main_flow.extend(modules_in_step[:2])
    
    return {
        "main_flow": list(set(main_flow))[:5],
        "generation_flow": [m.get("name") for m in modules if "generator" in m.get("role", "").lower() or "siren" in m.get("name", "").lower()][:3],
        "training_flow": [l.get("name") for l in losses][:3],
        "key_nodes": key_nodes[:5],
        "key_edges": key_edges[:5],
    }
