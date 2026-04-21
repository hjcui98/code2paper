from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple


BASE_ROLES = {
    "forward",
    "model_arch",
    "loss",
    "augmentation",
    "dataset",
    "training_loop",
    "config",
    "inference",
    "evaluation",
    "other",
}


def extract_dynamic_roles(method_summary: Dict[str, Any]) -> Set[str]:
    """
    从论文方法摘要中动态提取角色类型
    
    Args:
        method_summary: 论文方法摘要
    
    Returns:
        动态角色集合
    """
    roles = set(BASE_ROLES)
    method = method_summary.get("method", {}) if isinstance(method_summary, dict) else {}
    
    # 从 modules 提取角色
    for module in method.get("modules", []):
        if not isinstance(module, dict):
            continue
        name = str(module.get("name", "")).lower()
        module_id = str(module.get("module_id", "")).lower()
        role = str(module.get("role", "")).lower()
        
        # 从模块名提取关键词作为角色
        keywords = _extract_role_keywords(name + " " + module_id + " " + role)
        for kw in keywords:
            if kw and len(kw) >= 3:
                roles.add(kw)
    
    # 从 pipeline_steps 提取角色
    for step in method.get("pipeline_steps", []):
        if not isinstance(step, dict):
            continue
        name = str(step.get("name", "")).lower()
        keywords = _extract_role_keywords(name)
        for kw in keywords:
            if kw and len(kw) >= 3:
                roles.add(kw)
    
    # 从 losses 提取角色
    for loss in method.get("losses", []):
        if not isinstance(loss, dict):
            continue
        name = str(loss.get("name", "")).lower()
        keywords = _extract_role_keywords(name)
        for kw in keywords:
            if kw and len(kw) >= 3:
                roles.add(kw)
    
    return roles


def _extract_role_keywords(text: str) -> List[str]:
    """从文本提取可作为角色的关键词"""
    text = text.lower()
    keywords = []
    
    # 常见模块关键词映射
    keyword_mappings = [
        (["rotator", "rotation", "canonical", "invariant"], "rotator"),
        (["generator", "siren", "inr", "implicit"], "generator"),
        (["modulator", "conditional", "condition"], "modulator"),
        (["distill", "gradient match"], "distillation"),
        (["encoder", "encode"], "encoder"),
        (["decoder", "decode"], "decoder"),
        (["backbone", "feature extract"], "backbone"),
        (["classifier", "classification"], "classifier"),
        (["segment", "segmentation"], "segmentation"),
        (["attention", "transformer"], "attention"),
        (["outer loop", "outer_loop"], "outer_loop"),
        (["inner loop", "inner_loop"], "inner_loop"),
        (["data load", "dataloader"], "data_loading"),
    ]
    
    for triggers, role in keyword_mappings:
        if any(t in text for t in triggers):
            keywords.append(role)
    
    return keywords


def build_method_keyword_bank_enhanced(
    structured_sections: Dict[str, Any],
    method_summary: Optional[Dict[str, Any]] = None,
) -> Tuple[List[str], Dict[str, List[str]]]:
    """
    增强版方法关键词库构建
    
    Returns:
        (keyword_list, role_keywords_map)
    """
    bank = set()
    role_keywords = {}
    
    def add_tokens(text: str, role: Optional[str] = None):
        for tok in re.findall(r"[A-Za-z][A-Za-z0-9_\-]{2,}", text or ""):
            token = tok.lower()
            bank.add(token)
            if role:
                if role not in role_keywords:
                    role_keywords[role] = []
                if token not in role_keywords[role]:
                    role_keywords[role].append(token)
    
    sections = structured_sections.get("paper_sections", []) if isinstance(structured_sections, dict) else []
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        st = (sec.get("section_type") or "").lower()
        sn = (sec.get("section_name") or "").lower()
        if any(k in st or k in sn for k in ["method", "approach", "experiment", "evaluation", "results"]):
            content = sec.get("content")
            if isinstance(content, list):
                add_tokens(" ".join([str(x) for x in content]))
            elif isinstance(content, str):
                add_tokens(content)
    
    ms = method_summary or {}
    method = ms.get("method") if isinstance(ms, dict) else None
    
    if isinstance(method, dict):
        # 从 modules 提取
        for module in method.get("modules", []):
            if not isinstance(module, dict):
                continue
            name = str(module.get("name") or "")
            module_id = str(module.get("module_id") or "")
            role = str(module.get("role") or "")
            
            add_tokens(name, module_id.lower() if module_id else None)
            add_tokens(role, module_id.lower() if module_id else None)
            
            for step in module.get("io", {}) if isinstance(module.get("io"), dict) else []:
                add_tokens(str(step))
        
        # 从 pipeline_steps 提取
        for step in method.get("pipeline_steps", []):
            if not isinstance(step, dict):
                continue
            name = str(step.get("name") or "")
            step_id = str(step.get("step_id") or "")
            desc = str(step.get("description") or "")
            
            add_tokens(name, f"step_{step_id}" if step_id else None)
            add_tokens(desc)
        
        # 从 losses 提取
        for loss in method.get("losses", []):
            if not isinstance(loss, dict):
                continue
            name = str(loss.get("name") or "")
            add_tokens(name, "loss")
        
        # 从 innovations 提取
        for innov in method.get("innovations", []):
            if not isinstance(innov, dict):
                continue
            what = str(innov.get("what") or "")
            add_tokens(what)
    
    common = [
        "forward",
        "backbone",
        "decoder",
        "encoder",
        "loss",
        "augment",
        "dataset",
        "train",
        "eval",
        "inference",
        "optimizer",
    ]
    for c in common:
        bank.add(c)
    
    return sorted(bank)[:300], role_keywords


def align_method_to_code(
    method_summary: Dict[str, Any],
    paper_objects: Dict[str, Any],
    core_snippets: Dict[str, Any],
    dynamic_roles: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """
    建立论文方法与代码的对齐关系
    
    Args:
        method_summary: 论文方法摘要
        paper_objects: 论文对象 (pseudo_code, equations, algorithms)
        core_snippets: 代码片段
        dynamic_roles: 动态角色集合
    
    Returns:
        alignment: 对齐结果
    """
    alignment = {
        "modules": [],
        "pipeline_steps": [],
        "losses": [],
        "pseudo_code_alignment": [],
        "training_flow": {},
        "coverage_report": {},
        "dynamic_roles_used": list(dynamic_roles) if dynamic_roles else [],
    }
    
    method = method_summary.get("method", {}) if isinstance(method_summary, dict) else {}
    snippets = core_snippets.get("snippets", []) if isinstance(core_snippets, dict) else []
    
    # 1. 模块对齐
    for module in method.get("modules", []):
        module_alignment = _align_module(module, snippets, paper_objects, dynamic_roles)
        alignment["modules"].append(module_alignment)
    
    # 2. Pipeline 步骤对齐
    for step in method.get("pipeline_steps", []):
        step_alignment = _align_pipeline_step(step, snippets, dynamic_roles)
        alignment["pipeline_steps"].append(step_alignment)
    
    # 3. 损失函数对齐
    for loss in method.get("losses", []):
        loss_alignment = _align_loss(loss, snippets, paper_objects)
        alignment["losses"].append(loss_alignment)
    
    # 4. 伪代码对齐
    pseudo_codes = paper_objects.get("pseudo_code", []) if isinstance(paper_objects, dict) else []
    for pc in pseudo_codes:
        pc_alignment = _align_pseudo_code(pc, snippets)
        alignment["pseudo_code_alignment"].append(pc_alignment)
    
    # 5. 训练流程对齐
    algorithm_text = _extract_algorithm_text(paper_objects)
    if algorithm_text:
        alignment["training_flow"] = _align_training_flow(algorithm_text, snippets)
    
    # 6. 生成覆盖报告
    alignment["coverage_report"] = _build_coverage_report(alignment)
    
    return alignment


def _align_module(
    module: Dict[str, Any],
    snippets: List[Dict[str, Any]],
    paper_objects: Dict[str, Any],
    dynamic_roles: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """对齐单个模块"""
    module_name = str(module.get("name", "")).lower()
    module_id = str(module.get("module_id", "")).lower()
    module_role = str(module.get("role", "")).lower()
    
    keywords = _build_module_keywords(module_name, module_id, module_role)
    
    matched = []
    for sn in snippets:
        score = _compute_match_score(sn, keywords, dynamic_roles)
        if score > 0.3:
            matched.append({
                "snippet_id": sn.get("snippet_id"),
                "class_name": _extract_class_name(sn),
                "file": sn.get("source", {}).get("path", "") if isinstance(sn.get("source"), dict) else "",
                "lines": [
                    sn.get("source", {}).get("start_line") if isinstance(sn.get("source"), dict) else None,
                    sn.get("source", {}).get("end_line") if isinstance(sn.get("source"), dict) else None,
                ],
                "match_type": _determine_match_type(sn, score),
                "confidence": round(score, 2),
            })
    
    matched.sort(key=lambda x: x["confidence"], reverse=True)
    matched = matched[:5]
    
    pseudo_ref = _find_pseudo_code_ref(module_name, paper_objects)
    
    return {
        "method_module": module,
        "pseudo_code_ref": pseudo_ref,
        "matched_snippets": matched,
        "missing_implementation": len(matched) == 0,
        "implementation_completeness": _check_completeness(module, matched),
    }


def _build_module_keywords(module_name: str, module_id: str, module_role: str) -> List[str]:
    """构建模块搜索关键词"""
    keywords = []
    
    # 从模块名提取
    name_parts = re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}", module_name)
    keywords.extend([p.lower() for p in name_parts])
    
    # 从 module_id 提取
    if module_id:
        keywords.append(module_id)
    
    # 从 role 提取
    if module_role:
        keywords.extend(module_role.split())
    
    # 添加语义相关词
    name_lower = module_name.lower()
    if "rotator" in name_lower or "rotation" in name_lower or "canonical" in name_lower:
        keywords.extend(["rotator", "invariant", "canonical", "sign", "pca", "eigenvector"])
    if "generator" in name_lower or "siren" in name_lower or "inr" in name_lower:
        keywords.extend(["siren", "generator", "inr", "implicit", "sine", "layer"])
    if "modulator" in name_lower or "conditional" in name_lower:
        keywords.extend(["modulator", "wrapper", "condition", "lookup", "embedding", "class"])
    if "encoder" in name_lower:
        keywords.extend(["encoder", "encode", "feature"])
    if "decoder" in name_lower:
        keywords.extend(["decoder", "decode", "output"])
    
    return list(set(keywords))


def _compute_match_score(
    snippet: Dict[str, Any],
    keywords: List[str],
    dynamic_roles: Optional[Set[str]] = None,
) -> float:
    """计算片段与关键词的匹配分数"""
    text = str(snippet.get("text", "")).lower()
    class_name = _extract_class_name(snippet).lower()
    role = str(snippet.get("role", "")).lower()
    
    score = 0.0
    
    # 类名匹配 (高权重)
    for kw in keywords:
        if kw in class_name:
            score += 0.4
        elif kw in text:
            score += 0.1
    
    # 角色匹配
    if dynamic_roles and role in dynamic_roles:
        for kw in keywords:
            if kw in role:
                score += 0.2
    
    # 信号匹配
    signals = snippet.get("signals", [])
    if isinstance(signals, list):
        for sig in signals:
            sig_lower = str(sig).lower()
            for kw in keywords:
                if kw in sig_lower:
                    score += 0.1
    
    return min(score, 1.0)


def _extract_class_name(snippet: Dict[str, Any]) -> str:
    """从片段提取类名或函数名"""
    text = snippet.get("text", "")
    if not isinstance(text, str):
        return ""
    
    match = re.search(r"class\s+(\w+)", text)
    if match:
        return match.group(1)
    
    match = re.search(r"def\s+(\w+)", text)
    if match:
        return match.group(1)
    
    return ""


def _determine_match_type(snippet: Dict[str, Any], score: float) -> str:
    """确定匹配类型"""
    if score >= 0.7:
        return "implementation"
    elif score >= 0.4:
        return "partial"
    else:
        return "reference"


def _check_completeness(module: Dict[str, Any], matched: List[Dict]) -> Dict[str, str]:
    """检查实现完整性"""
    completeness = {}
    module_name = str(module.get("name", "")).lower()
    
    matched_text = " ".join([str(m) for m in matched]).lower()
    
    if "rotator" in module_name:
        completeness["sign_computation"] = "found" if "sign" in matched_text else "missing"
        completeness["canonical_method"] = "found" if "canonical" in matched_text else "missing"
    elif "generator" in module_name or "siren" in module_name:
        completeness["siren_layers"] = "found" if "siren" in matched_text or "sine" in matched_text else "missing"
        completeness["forward_method"] = "found" if "forward" in matched_text else "missing"
    elif "modulator" in module_name:
        completeness["condition_embedding"] = "found" if "embedding" in matched_text or "lookup" in matched_text else "missing"
        completeness["modulation_logic"] = "found" if "mod" in matched_text else "missing"
    
    return completeness


def _find_pseudo_code_ref(module_name: str, paper_objects: Dict[str, Any]) -> Optional[str]:
    """查找伪代码引用"""
    pseudo_codes = paper_objects.get("pseudo_code", []) if isinstance(paper_objects, dict) else []
    
    first_word = module_name.split()[0] if module_name else ""
    
    for pc in pseudo_codes:
        if not isinstance(pc, dict):
            continue
        code_text = str(pc.get("code_text", "")).lower()
        title = str(pc.get("title", "") or pc.get("caption", "")).lower()
        
        if first_word and first_word in code_text:
            return pc.get("object_id")
        if first_word and first_word in title:
            return pc.get("object_id")
    
    return None


def _align_pipeline_step(
    step: Dict[str, Any],
    snippets: List[Dict[str, Any]],
    dynamic_roles: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """对齐 Pipeline 步骤"""
    step_name = str(step.get("name", "")).lower()
    step_id = str(step.get("step_id", ""))
    step_desc = str(step.get("description", "")).lower()
    
    keywords = _build_step_keywords(step_name, step_desc)
    
    matched = []
    for sn in snippets:
        score = _compute_match_score(sn, keywords, dynamic_roles)
        if score > 0.25:
            matched.append({
                "snippet_id": sn.get("snippet_id"),
                "function": _extract_class_name(sn),
                "match_type": "pipeline_step",
                "confidence": round(score, 2),
            })
    
    matched.sort(key=lambda x: x["confidence"], reverse=True)
    matched = matched[:3]
    
    return {
        "method_step": step,
        "matched_snippets": matched,
    }


def _build_step_keywords(step_name: str, step_desc: str) -> List[str]:
    """构建步骤搜索关键词"""
    keywords = []
    
    name_parts = re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}", step_name)
    keywords.extend([p.lower() for p in name_parts])
    
    desc_parts = re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}", step_desc)
    keywords.extend([p.lower() for p in desc_parts[:20]])
    
    if "canonicalization" in step_name or "rotation" in step_name:
        keywords.extend(["rotator", "invariant", "canonical", "sign", "pca"])
    if "generation" in step_name or "generate" in step_name:
        keywords.extend(["generator", "siren", "forward", "noise", "generate"])
    if "distillation" in step_name or "gradient" in step_name:
        keywords.extend(["gradient", "match", "distill", "loss", "backward"])
    
    return list(set(keywords))


def _align_loss(
    loss: Dict[str, Any],
    snippets: List[Dict[str, Any]],
    paper_objects: Dict[str, Any],
) -> Dict[str, Any]:
    """对齐损失函数"""
    loss_name = str(loss.get("name", "")).lower()
    formula_ref = loss.get("formula_ref", "")
    
    keywords = ["loss", "criterion"]
    
    if "shape" in loss_name or "classification" in loss_name:
        keywords.extend(["classification", "cls", "crossentropy", "ce"])
    if "part" in loss_name or "segmentation" in loss_name:
        keywords.extend(["seg", "segmentation", "dice", "part"])
    if "gradient" in loss_name or "match" in loss_name:
        keywords.extend(["gradient", "match", "distance"])
    
    matched = []
    for sn in snippets:
        text = str(sn.get("text", "")).lower()
        role = str(sn.get("role", "")).lower()
        
        if role == "loss" or any(kw in text for kw in keywords):
            score = 0.7 if role == "loss" else 0.5
            matched.append({
                "snippet_id": sn.get("snippet_id"),
                "function": _extract_class_name(sn),
                "match_type": "loss_function",
                "confidence": score,
            })
    
    matched.sort(key=lambda x: x["confidence"], reverse=True)
    matched = matched[:3]
    
    return {
        "method_loss": loss,
        "formula_ref": formula_ref,
        "matched_snippets": matched,
    }


def _align_pseudo_code(pc: Dict[str, Any], snippets: List[Dict[str, Any]]) -> Dict[str, Any]:
    """对齐伪代码"""
    code_text = str(pc.get("code_text", ""))
    components = _extract_pseudo_components(code_text)
    
    component_alignments = []
    for comp in components:
        comp_name = str(comp.get("name", "")).lower()
        keywords = [comp_name]
        
        if comp_name == "rotator":
            keywords.extend(["invariant", "sign", "canonical"])
        elif "generator" in comp_name or "conditional" in comp_name:
            keywords.extend(["wrapper", "condition", "lookup", "siren"])
        
        matched_sn = None
        best_score = 0
        for sn in snippets:
            score = _compute_match_score(sn, keywords, None)
            if score > best_score:
                best_score = score
                matched_sn = sn
        
        component_alignments.append({
            "pseudo_component": comp.get("name"),
            "matched_snippet_id": matched_sn.get("snippet_id") if matched_sn else None,
            "matched_class": _extract_class_name(matched_sn) if matched_sn else None,
            "confidence": round(best_score, 2),
        })
    
    return {
        "pseudo_code_id": pc.get("object_id"),
        "title": pc.get("caption") or pc.get("title") or "Pseudo Code",
        "components": component_alignments,
    }


def _extract_pseudo_components(code_text: str) -> List[Dict[str, str]]:
    """从伪代码提取组件"""
    components = []
    matches = re.findall(r"class\s+(\w+)", code_text, re.IGNORECASE)
    for m in matches:
        components.append({"name": m, "type": "class"})
    
    matches = re.findall(r"def\s+(\w+)", code_text, re.IGNORECASE)
    for m in matches:
        components.append({"name": m, "type": "function"})
    
    return components


def _extract_algorithm_text(paper_objects: Dict[str, Any]) -> Optional[str]:
    """提取算法描述文本"""
    equations = paper_objects.get("equations", []) if isinstance(paper_objects, dict) else []
    for eq in equations:
        if not isinstance(eq, dict):
            continue
        text = str(eq.get("text", ""))
        if "Algorithm" in text or "Input:" in text or "Output:" in text:
            return text
    return None


def _align_training_flow(algorithm_text: str, snippets: List[Dict[str, Any]]) -> Dict[str, Any]:
    """对齐训练流程"""
    flow_steps = []
    
    step_patterns = [
        ("Sample batch from training data", ["sample", "batch", "loader", "data"]),
        ("Sample noise from uniform distribution", ["noise", "uniform", "u(0,1)", "random"]),
        ("Generate synthetic point clouds", ["generate", "forward", "g(", "synthetic"]),
        ("Compute gradients and losses", ["gradient", "backward", "loss", "compute"]),
        ("Update generator parameters", ["update", "optimizer", "step", "generator"]),
        ("Inner loop: train model", ["inner", "loop", "train", "model"]),
    ]
    
    for step_name, keywords in step_patterns:
        matched = None
        best_score = 0
        for sn in snippets:
            text = str(sn.get("text", "")).lower()
            role = str(sn.get("role", "")).lower()
            
            score = sum(0.15 for kw in keywords if kw in text)
            if role in ["training_loop", "outer_loop", "inner_loop"]:
                score += 0.2
            
            if score > best_score:
                best_score = score
                matched = sn
        
        flow_steps.append({
            "step": step_name,
            "matched_snippet_id": matched.get("snippet_id") if matched else None,
            "confidence": round(min(best_score, 1.0), 2),
        })
    
    completeness = sum(1 for s in flow_steps if s["matched_snippet_id"]) / len(flow_steps)
    
    return {
        "algorithm_ref": "Algorithm from paper",
        "flow_steps": flow_steps,
        "completeness": round(completeness, 2),
    }


def _build_coverage_report(alignment: Dict[str, Any]) -> Dict[str, Any]:
    """构建覆盖报告"""
    modules = alignment.get("modules", [])
    steps = alignment.get("pipeline_steps", [])
    losses = alignment.get("losses", [])
    training = alignment.get("training_flow", {})
    
    modules_found = sum(1 for m in modules if m.get("matched_snippets"))
    steps_found = sum(1 for s in steps if s.get("matched_snippets"))
    losses_found = sum(1 for l in losses if l.get("matched_snippets"))
    
    modules_score = modules_found / max(len(modules), 1)
    steps_score = steps_found / max(len(steps), 1)
    losses_score = losses_found / max(len(losses), 1)
    training_score = training.get("completeness", 0) if training else 0
    
    overall = (modules_score + steps_score + losses_score + training_score) / 4
    
    return {
        "modules_coverage": {
            "total": len(modules),
            "found": modules_found,
            "score": round(modules_score, 2),
        },
        "pipeline_steps_coverage": {
            "total": len(steps),
            "found": steps_found,
            "score": round(steps_score, 2),
        },
        "losses_coverage": {
            "total": len(losses),
            "found": losses_found,
            "score": round(losses_score, 2),
        },
        "training_flow_coverage": {
            "completeness": round(training_score, 2),
        },
        "overall_score": round(overall, 2),
    }


def fill_relevance_from_alignment(
    core_snippets: Dict[str, Any],
    alignment: Dict[str, Any],
) -> Dict[str, Any]:
    """根据对齐结果填充 relevance 字段"""
    snippets = core_snippets.get("snippets", [])
    if not isinstance(snippets, list):
        return core_snippets
    
    snippet_to_info = {}
    
    for m in alignment.get("modules", []):
        module_name = ""
        if isinstance(m.get("method_module"), dict):
            module_name = m.get("method_module", {}).get("name", "")
        
        for ms in m.get("matched_snippets", []):
            sid = ms.get("snippet_id")
            if sid:
                snippet_to_info[sid] = {
                    "paper_section_ids": [module_name] if module_name else [],
                    "score": ms.get("confidence", 0),
                    "reason": f"Matched to method module: {module_name}",
                }
    
    for s in alignment.get("pipeline_steps", []):
        step_name = ""
        if isinstance(s.get("method_step"), dict):
            step_name = s.get("method_step", {}).get("name", "")
        
        for ms in s.get("matched_snippets", []):
            sid = ms.get("snippet_id")
            if sid:
                if sid in snippet_to_info:
                    snippet_to_info[sid]["paper_section_ids"].append(step_name)
                else:
                    snippet_to_info[sid] = {
                        "paper_section_ids": [step_name],
                        "score": ms.get("confidence", 0),
                        "reason": f"Matched to pipeline step: {step_name}",
                    }
    
    for sn in snippets:
        if not isinstance(sn, dict):
            continue
        sid = sn.get("snippet_id")
        if sid in snippet_to_info:
            sn["relevance"] = snippet_to_info[sid]
    
    return core_snippets


def extract_rescan_files(alignment: Dict[str, Any]) -> List[str]:
    """从对齐结果提取需要重扫描的文件"""
    files = set()
    
    for m in alignment.get("modules", []):
        if m.get("missing_implementation"):
            completeness = m.get("implementation_completeness", {})
            for key, status in completeness.items():
                if status == "missing":
                    pass
    
    for pc in alignment.get("pseudo_code_alignment", []):
        for comp in pc.get("components", []):
            if comp.get("confidence", 0) < 0.5:
                pass
    
    return list(files)


def infer_snippet_role_from_alignment(
    snippet: Dict[str, Any],
    alignment: Dict[str, Any],
    dynamic_roles: Set[str],
) -> str:
    """根据对齐结果推断片段角色"""
    current_role = snippet.get("role", "other")
    snippet_id = snippet.get("snippet_id")
    
    if not snippet_id:
        return current_role
    
    for m in alignment.get("modules", []):
        module_id = ""
        if isinstance(m.get("method_module"), dict):
            module_id = m.get("method_module", {}).get("module_id", "")
        
        for ms in m.get("matched_snippets", []):
            if ms.get("snippet_id") == snippet_id:
                if module_id and module_id in dynamic_roles:
                    return module_id
                if ms.get("confidence", 0) >= 0.7:
                    name = m.get("method_module", {}).get("name", "").lower()
                    if "rotator" in name:
                        return "rotator"
                    if "generator" in name:
                        return "generator"
                    if "modulator" in name:
                        return "modulator"
    
    for s in alignment.get("pipeline_steps", []):
        step_id = ""
        if isinstance(s.get("method_step"), dict):
            step_id = s.get("method_step", {}).get("step_id", "")
        
        for ms in s.get("matched_snippets", []):
            if ms.get("snippet_id") == snippet_id:
                name = s.get("method_step", {}).get("name", "").lower()
                if "canonicalization" in name or "rotation" in name:
                    return "rotator"
                if "generation" in name:
                    return "generator"
                if "distillation" in name:
                    return "distillation"
    
    return current_role
