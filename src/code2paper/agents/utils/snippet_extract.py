from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from code2paper.agents.utils.code_scan import read_file_lines


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


def extract_snippets(
    paths: List[Dict[str, Any]],
    rules: Optional[Dict[str, Any]] = None,
    budgets: Optional[Dict[str, Any]] = None,
    dynamic_roles: Optional[Set[str]] = None,
    role_keywords_map: Optional[Dict[str, List[str]]] = None,
) -> List[Dict[str, Any]]:
    """
    提取代码片段
    
    Args:
        paths: 文件路径列表
        rules: 规则配置
        budgets: 预算配置
        dynamic_roles: 动态角色集合（从论文内容提取）
        role_keywords_map: 角色到关键词的映射
    
    Returns:
        代码片段列表
    """
    rule_cfg = rules or {}
    budget_cfg = budgets or {}
    
    max_total_lines = int(budget_cfg.get("max_total_snippet_lines", 2200))
    max_single_lines = int(budget_cfg.get("max_single_snippet_lines", 180))
    top_k_per_role = int(budget_cfg.get("top_k_per_role", 8))
    
    allowed_roles = BASE_ROLES | (dynamic_roles or set())
    
    snippets: List[Dict[str, Any]] = []
    used_lines = 0
    per_role_counts: Dict[str, int] = {}
    
    snippet_idx = 0
    
    for f in paths:
        path = f.get("path")
        if not path:
            continue
        sha1 = f.get("sha1", "")
        language = (f.get("language") or "").lower()
        
        lines = read_file_lines(path)
        if not lines:
            continue
        
        candidates = []
        if language == "python":
            candidates = _python_candidates(lines, dynamic_roles, role_keywords_map)
        if not candidates:
            candidates = _regex_candidates(lines, dynamic_roles, role_keywords_map)
        
        for role, start, end, signals in candidates:
            if role not in allowed_roles:
                role = _map_to_base_role(role, dynamic_roles)
            if role not in allowed_roles:
                role = "other"
            
            if per_role_counts.get(role, 0) >= top_k_per_role:
                continue
            
            start = max(1, start)
            end = min(len(lines), end)
            if end < start:
                continue
            
            length = end - start + 1
            if length > max_single_lines:
                end = start + max_single_lines - 1
                length = max_single_lines
            
            if used_lines + length > max_total_lines:
                return snippets
            
            snippet_idx += 1
            snippet_id = f"sn{snippet_idx}"
            text = "\n".join(lines[start - 1 : end])
            
            snippets.append({
                "snippet_id": snippet_id,
                "role": role,
                "source": {"path": path, "start_line": start, "end_line": end, "sha1": sha1},
                "text": text,
                "signals": signals,
                "relevance": {"paper_section_ids": [], "score": 0.0, "reason": ""},
                "quality": {"parsable": True, "length_lines": length, "has_external_deps": False},
            })
            
            used_lines += length
            per_role_counts[role] = per_role_counts.get(role, 0) + 1
    
    return snippets


def extract_symbol_snippets(
    paths: List[Dict[str, Any]],
    symbol_targets: List[Dict[str, Any]],
    budgets: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Extract exact code spans for requested file/symbol pairs."""
    max_lines = int((budgets or {}).get("max_single_snippet_lines", 300))
    snippets: List[Dict[str, Any]] = []
    for file_info in paths:
        path = str(file_info.get("path") or "")
        lines = read_file_lines(path) if path else []
        if not lines:
            continue
        normalized = str(Path(path)).replace("\\", "/")
        try:
            tree = ast.parse("\n".join(lines))
        except SyntaxError:
            tree = None
        for target in symbol_targets:
            hint = str(target.get("path") or "").replace("\\", "/")
            symbol = str(target.get("symbol") or "")
            if not hint or not symbol or not (normalized.endswith(hint) or hint.endswith(normalized)):
                continue
            wanted = symbol.split(".")[-1]
            span = None
            if tree is not None:
                for node in ast.walk(tree):
                    if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name == wanted:
                        span = (node.lineno, getattr(node, "end_lineno", node.lineno))
                        break
                    if isinstance(node, ast.ClassDef) and symbol.startswith(node.name + "."):
                        for child in node.body:
                            if isinstance(child, ast.FunctionDef) and child.name == wanted:
                                span = (child.lineno, getattr(child, "end_lineno", child.lineno))
                                break
            if span is None:
                continue
            start, end = span
            end = min(end, start + max_lines - 1)
            snippets.append(
                {
                    "snippet_id": f"sym{len(snippets) + 1}",
                    "role": str(target.get("role") or "author_symbol"),
                    "source": {
                        "path": path,
                        "start_line": start,
                        "end_line": end,
                        "sha1": file_info.get("sha1", ""),
                        "symbol": symbol,
                    },
                    "text": "\n".join(lines[start - 1 : end]),
                    "signals": ["author_symbol_target", symbol],
                    "relevance": {"paper_section_ids": [], "score": 1.0, "reason": f"Exact symbol {symbol}"},
                    "quality": {"parsable": True, "length_lines": end - start + 1, "has_external_deps": False},
                }
            )
    return snippets


def _map_to_base_role(role: str, dynamic_roles: Optional[Set[str]]) -> str:
    """将动态角色映射到基础角色"""
    if not dynamic_roles or role in BASE_ROLES:
        return role
    
    role_lower = role.lower()
    
    if any(k in role_lower for k in ["rotator", "rotation", "canonical", "invariant"]):
        return "model_arch"
    if any(k in role_lower for k in ["generator", "siren", "inr", "implicit"]):
        return "model_arch"
    if any(k in role_lower for k in ["modulator", "condition", "wrapper"]):
        return "model_arch"
    if any(k in role_lower for k in ["encoder", "decoder", "backbone"]):
        return "model_arch"
    if any(k in role_lower for k in ["distill", "gradient"]):
        return "training_loop"
    if any(k in role_lower for k in ["outer_loop", "inner_loop"]):
        return "training_loop"
    if any(k in role_lower for k in ["data_load", "dataloader"]):
        return "dataset"
    
    return role


def _python_candidates(
    lines: List[str],
    dynamic_roles: Optional[Set[str]] = None,
    role_keywords_map: Optional[Dict[str, List[str]]] = None,
) -> List[Tuple[str, int, int, List[str]]]:
    """提取 Python 代码候选片段"""
    text = "\n".join(lines)
    try:
        tree = ast.parse(text)
    except Exception:
        return []
    
    candidates: List[Tuple[str, int, int, List[str]]] = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            start = getattr(node, "lineno", None)
            end = getattr(node, "end_lineno", None)
            if not start or not end:
                continue
            
            class_name = node.name
            body_lines = lines[start - 1 : end]
            
            role = _infer_role_from_class_name(class_name, body_lines, dynamic_roles, role_keywords_map)
            signals = _signals_from_block(body_lines, dynamic_roles)
            
            candidates.append((role, start, end, signals))
        
        if isinstance(node, ast.FunctionDef):
            start = getattr(node, "lineno", None)
            end = getattr(node, "end_lineno", None)
            if not start or not end:
                continue
            
            name = node.name.lower()
            body_lines = lines[start - 1 : end]
            
            role = _infer_role_from_function_name(name, body_lines, dynamic_roles, role_keywords_map)
            signals = _signals_from_block(body_lines, dynamic_roles)
            
            candidates.append((role, start, end, signals))
    
    candidates.sort(key=lambda x: (x[0], x[1]))
    return candidates


def _infer_role_from_class_name(
    class_name: str,
    body_lines: List[str],
    dynamic_roles: Optional[Set[str]] = None,
    role_keywords_map: Optional[Dict[str, List[str]]] = None,
) -> str:
    """根据类名和内容推断角色（支持动态角色）"""
    name_lower = class_name.lower()
    body_text = "\n".join(body_lines).lower()
    
    if dynamic_roles:
        for role in dynamic_roles:
            if role in name_lower:
                return role
            
            keywords = role_keywords_map.get(role, []) if role_keywords_map else []
            for kw in keywords:
                if kw in name_lower or kw in body_text:
                    return role
    
    if any(k in name_lower for k in ["rotator", "invariant", "canonical"]):
        return "rotator" if dynamic_roles and "rotator" in dynamic_roles else "model_arch"
    if any(k in name_lower for k in ["siren", "generator", "inr"]):
        return "generator" if dynamic_roles and "generator" in dynamic_roles else "model_arch"
    if any(k in name_lower for k in ["wrapper", "modulator", "condition"]):
        return "modulator" if dynamic_roles and "modulator" in dynamic_roles else "model_arch"
    if any(k in name_lower for k in ["distill", "match"]):
        return "distillation" if dynamic_roles and "distillation" in dynamic_roles else "training_loop"
    
    if "loss" in name_lower or "criterion" in body_text:
        return "loss"
    if "dataset" in name_lower or "dataloader" in name_lower:
        return "dataset"
    if "augment" in name_lower or "transform" in name_lower:
        return "augmentation"
    if "train" in name_lower:
        return "training_loop"
    
    if "nn.module" in body_text or "nn.Module" in body_text:
        return "model_arch"
    
    return "other"


def _infer_role_from_function_name(
    name: str,
    body_lines: List[str],
    dynamic_roles: Optional[Set[str]] = None,
    role_keywords_map: Optional[Dict[str, List[str]]] = None,
) -> str:
    """根据函数名和内容推断角色"""
    body_text = "\n".join(body_lines).lower()
    
    if dynamic_roles:
        for role in dynamic_roles:
            keywords = role_keywords_map.get(role, []) if role_keywords_map else []
            for kw in keywords:
                if kw in name or kw in body_text:
                    return role
    
    if name == "forward":
        return "forward"
    if "loss" in name or "criterion" in body_text:
        return "loss"
    if "train" in name or _block_has_any(body_lines, ["optimizer", "backward"]):
        if "inner" in name or "inner_loop" in body_text:
            return "inner_loop" if dynamic_roles and "inner_loop" in dynamic_roles else "training_loop"
        if "outer" in name or "outer_loop" in body_text:
            return "outer_loop" if dynamic_roles and "outer_loop" in dynamic_roles else "training_loop"
        return "training_loop"
    if "eval" in name or "metric" in name:
        return "evaluation"
    if "infer" in name or "predict" in name:
        return "inference"
    if "main" in name:
        return "training_loop"
    
    return "other"


def _regex_candidates(
    lines: List[str],
    dynamic_roles: Optional[Set[str]] = None,
    role_keywords_map: Optional[Dict[str, List[str]]] = None,
) -> List[Tuple[str, int, int, List[str]]]:
    """正则表达式提取候选片段"""
    candidates: List[Tuple[str, int, int, List[str]]] = []
    
    for i, line in enumerate(lines, start=1):
        low = line.lower()
        
        if "def forward" in low:
            start, end = _expand_block(lines, i)
            candidates.append(("forward", start, end, ["def forward"]))
        
        if "class " in low:
            match = re.search(r"class\s+(\w+)", low)
            if match:
                class_name = match.group(1).lower()
                start, end = _expand_block(lines, i)
                role = _infer_role_from_class_name(class_name, lines[start - 1 : end], dynamic_roles, role_keywords_map)
                signals = _signals_from_block(lines[start - 1 : end], dynamic_roles)
                candidates.append((role, start, end, signals))
        
        if "loss" in low and ("=" in low or "criterion" in low):
            start, end = _expand_window(lines, i, 15)
            candidates.append(("loss", start, end, ["loss"]))
        
        if "dataset" in low and ("class" in low or "def" in low):
            start, end = _expand_window(lines, i, 20)
            candidates.append(("dataset", start, end, ["dataset"]))
        
        if "optimizer" in low or "backward" in low:
            start, end = _expand_window(lines, i, 25)
            candidates.append(("training_loop", start, end, ["optimizer", "backward"]))
        
        if "argparse" in low or "yaml" in low or "omegaconf" in low:
            start, end = _expand_window(lines, i, 20)
            candidates.append(("config", start, end, ["argparse", "yaml"]))
        
        if "augment" in low or "transforms" in low:
            start, end = _expand_window(lines, i, 20)
            candidates.append(("augmentation", start, end, ["augment", "transforms"]))
    
    uniq = {}
    for role, start, end, signals in candidates:
        key = (role, start, end)
        if key not in uniq:
            uniq[key] = (role, start, end, signals)
    result = list(uniq.values())
    result.sort(key=lambda x: (x[0], x[1]))
    return result


def _signals_from_block(block_lines: List[str], dynamic_roles: Optional[Set[str]] = None) -> List[str]:
    """从代码块提取信号"""
    sample = "\n".join(block_lines).lower()
    signals = []
    
    base_signals = ["def forward", "nn.module", "dataset", "optimizer", "loss", "augment", "transforms", "argparse", "yaml"]
    for s in base_signals:
        if s in sample:
            signals.append(s)
    
    if dynamic_roles:
        for role in dynamic_roles:
            if role in sample:
                signals.append(role)
    
    return signals[:15]


def _block_has_any(block_lines: List[str], terms: List[str]) -> bool:
    sample = "\n".join(block_lines).lower()
    return any(t in sample for t in terms)


def _expand_block(lines: List[str], lineno: int) -> Tuple[int, int]:
    start = lineno
    indent = len(lines[lineno - 1]) - len(lines[lineno - 1].lstrip(" "))
    end = lineno
    for i in range(lineno, len(lines)):
        cur = lines[i]
        if not cur.strip():
            end = i + 1
            continue
        cur_indent = len(cur) - len(cur.lstrip(" "))
        if cur_indent <= indent and i + 1 > lineno:
            break
        end = i + 1
    return start, end


def _expand_window(lines: List[str], lineno: int, radius: int) -> Tuple[int, int]:
    start = max(1, lineno - radius)
    end = min(len(lines), lineno + radius)
    return start, end


def build_method_keyword_bank(structured_sections: Dict[str, Any], method_summary: Optional[Dict[str, Any]] = None) -> List[str]:
    bank = set()
    
    def add_tokens(text: str):
        for tok in re.findall(r"[A-Za-z][A-Za-z0-9_\\-]{2,}", text or ""):
            bank.add(tok.lower())
    
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
        for step in method.get("pipeline_steps") or []:
            if isinstance(step, dict):
                add_tokens(step.get("name") or "")
                add_tokens(step.get("description") or "")
        for m in method.get("modules") or []:
            if isinstance(m, dict):
                add_tokens(m.get("name") or "")
        for l in method.get("losses") or []:
            if isinstance(l, dict):
                add_tokens(l.get("name") or "")
    
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
    
    return sorted(bank)[:300]


def apply_role_overrides(snippets: List[Dict[str, Any]], overrides: Dict[str, str], dynamic_roles: Optional[Set[str]] = None) -> List[Dict[str, Any]]:
    if not overrides:
        return snippets
    
    allowed_roles = BASE_ROLES | (dynamic_roles or set())
    
    for sn in snippets:
        sid = sn.get("snippet_id")
        if not sid:
            continue
        new_role = overrides.get(sid)
        if new_role and new_role in allowed_roles:
            sn["role"] = new_role
    return snippets
