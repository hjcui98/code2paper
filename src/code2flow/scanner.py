from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .defaults import ENTRYPOINT_NAME_HINTS, TOUCHPOINT_PATTERNS, ScanConfig
from .utils import read_text_safe, relpath

# Annotation parsing is intentionally disabled in this embedded scanner, but
# the report contract still exposes the accepted markers for compatibility.
ANNOTATION_MARKERS = ("CODE2PAPER:", "@code2paper", "code2paper:")

@dataclass
class FileScore:
    path: Path
    rel: str
    score: float
    reasons: list[str]
    touchpoints: dict[str, int]


def _is_ignored(path: Path, ignore_dirs: tuple[str, ...]) -> bool:
    parts = {p.lower() for p in path.parts}
    return any(name.lower() in parts for name in ignore_dirs)


def _iter_code_files(root: Path, cfg: ScanConfig) -> list[Path]:
    result: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if _is_ignored(path, cfg.ignore_dirs):
            continue
        if path.suffix.lower() not in cfg.include_exts:
            continue
        result.append(path)
    return result


def _collect_annotation_items(text: str, max_items: int = 20) -> list[dict[str, Any]]:
    _ = text, max_items
    return []


def _annotation_mode(mode: str) -> str:
    _ = mode
    return "disabled"


def _annotation_mode_profile(mode: str) -> dict[str, float]:
    _ = mode
    return {
        "hit_gain": 0.0,
        "hit_cap": 0.0,
        "strong_hint_gain": 0.0,
        "signal_gain": 0.0,
        "forced_ratio": 0.0,
        "prox_near": 0.0,
        "prox_mid": 0.0,
    }


def _score_file(path: Path, root: Path, text: str, annotation_priority: str = "balanced") -> FileScore:
    lower_name = path.stem.lower()
    lower_text = text.lower()

    score = 0.0
    reasons: list[str] = []
    touch_counts: dict[str, int] = {}

    # Entrypoint signals are useful but easy to over-trigger on auxiliary scripts.
    # Keep them as weak priors instead of dominant signals.
    if any(h in lower_name for h in ENTRYPOINT_NAME_HINTS):
        score += 1.2
        reasons.append("entrypoint_name_hint")

    if "if __name__ == '__main__'" in lower_text or 'if __name__ == "__main__"' in lower_text:
        score += 1.2
        reasons.append("python_main_guard")

    if re.search(r"\bdef\s+main\b|\bfunction\s+main\b|\bint\s+main\s*\(", lower_text):
        score += 1.0
        reasons.append("main_function")

    for tp, patterns in TOUCHPOINT_PATTERNS.items():
        cnt = 0
        for p in patterns:
            cnt += lower_text.count(p)
        touch_counts[tp] = cnt
        if cnt > 0:
            # Use logarithmic growth to avoid keyword-dense utility scripts dominating
            # the core ranking only by repetition count.
            tp_gain = min(1.0, 0.32 * (cnt ** 0.5))
            score += tp_gain
            reasons.append(f"touchpoint:{tp}:{cnt}:gain={round(tp_gain, 3)}")

    imports_cnt = len(re.findall(r"^\s*(from|import)\s+", text, flags=re.MULTILINE))
    if imports_cnt > 8:
        score += 1.0
        reasons.append("high_import_connectivity")

    score += min(1.5, len(text) / 18_000)
    reasons.append("size_signal")

    return FileScore(
        path=path,
        rel=relpath(path, root),
        score=round(score, 3),
        reasons=reasons,
        touchpoints=touch_counts,
    )


def _extract_annotations(text: str, max_items: int = 20) -> list[str]:
    _ = text, max_items
    return []


def _annotation_anchors(text: str, max_items: int = 20) -> list[dict[str, Any]]:
    _ = text, max_items
    return []


def _method_relevance_score(text: str) -> float:
    lower = text.lower()
    keys = (
        "module",
        "forward",
        "loss",
        "objective",
        "optimizer",
        "train",
        "eval",
        "attention",
        "token",
        "fusion",
        "encoder",
        "decoder",
    )
    hits = sum(lower.count(k) for k in keys)
    return float(min(10.0, hits))


def _window_snippet(text: str, line_no: int, radius: int = 12, max_chars: int = 2200) -> str:
    lines = text.splitlines()
    if not lines:
        return ""
    center = max(1, min(line_no, len(lines)))
    start = max(1, center - radius)
    end = min(len(lines), center + radius)
    body = "\n".join(lines[start - 1 : end]).strip()
    if len(body) > max_chars:
        body = body[:max_chars].rstrip()
    return body


def _merge_line_windows(windows: list[tuple[int, int]], max_line: int) -> list[tuple[int, int]]:
    if not windows:
        return []
    norm = []
    for s, e in windows:
        s2 = max(1, min(s, max_line))
        e2 = max(1, min(e, max_line))
        if s2 > e2:
            s2, e2 = e2, s2
        norm.append((s2, e2))
    norm.sort()
    merged: list[tuple[int, int]] = []
    cur_s, cur_e = norm[0]
    for s, e in norm[1:]:
        if s <= cur_e + 1:
            cur_e = max(cur_e, e)
        else:
            merged.append((cur_s, cur_e))
            cur_s, cur_e = s, e
    merged.append((cur_s, cur_e))
    return merged


def _snippet_from_line_windows(text: str, windows: list[tuple[int, int]], max_chars: int) -> str:
    lines = text.splitlines()
    if not lines:
        return ""
    merged = _merge_line_windows(windows, len(lines))
    chunks: list[str] = []
    used = 0
    for s, e in merged:
        block = "\n".join(lines[s - 1 : e]).strip()
        if not block:
            continue
        block_len = len(block) + 2
        if used + block_len > max_chars and chunks:
            break
        chunks.append(block)
        used += block_len
        if used >= max_chars:
            break
    return "\n\n".join(chunks).strip()[:max_chars].strip()


def _snippet_from_text(text: str, max_chars: int) -> str:
    lines = text.splitlines()
    if len(lines) <= 180 and len(text) <= max_chars:
        return text.strip()

    signal_patterns = [
        r"\bclass\s+\w+",
        r"\bdef\s+\w+",
        r"\bif __name__ == [\"']__main__[\"']",
        r"\boptimizer\b|\bloss\b|\bmetric\b|\bdataloader\b",
    ]
    compiled = [re.compile(p, flags=re.IGNORECASE) for p in signal_patterns]
    windows: list[tuple[int, int]] = []
    for i, line in enumerate(lines, start=1):
        if any(p.search(line) for p in compiled):
            windows.append((i - 6, i + 12))
    if windows:
        content = _snippet_from_line_windows(text, windows, max_chars=max_chars)
        if content:
            return content
    return text[:max_chars].strip()


def _topic_patterns(
    custom_topics: dict[str, list[str]] | None = None,
    extra_keywords: list[str] | None = None,
) -> dict[str, tuple[str, ...]]:
    topics: dict[str, tuple[str, ...]] = {
        "shared_projection_with_residual": (
            r"shared|global|common",
            r"aligner|adapter|projection|mapping|transform",
            r"modulelist|per[- ]layer|layer[- ]specific|idx|index",
            r"residual|low[- ]rank|lora|factoriz|decomposition",
            r"weight\s*\+\s*\(.*@.*\)",
        ),
        "cross_layer_token_composition": (
            r"\bbeta\b",
            r"previous|prev",
            r"compose|composition|blend|mixture|fuse|aggregate|accumulate|propagate",
            r"token|context|representation|state|feature",
            r"layer|stage|block",
            r"\(1\s*-\s*beta\)",
        ),
        "objective_decomposition": (
            r"loss|criterion|objective",
            r"cross[_ -]?entropy|bce|mse|mae|kl|nll|dice|focal|triplet",
            r"cosine_similarity|regulariz|weight_decay|distill|teacher",
            r"reg_weight|lambda|alpha|beta|gamma",
            r"total loss|overall objective|return\s+loss|loss\s*=",
            r"logits|score|prediction",
        ),
        "inference_policy_decoupling": (
            r"for_inference|inference|test[- ]time|eval mode|not\s+self\.training",
            r"decouple|policy|route|routing|gate|switch|branch|fallback",
            r"base|novel|seen|unseen|in[- ]domain|out[- ]of[- ]domain|ood|zero[- ]shot",
            r"if\s+.*test|if\s+.*eval|if\s+.*training",
        ),
        "upper_layer_injection_policy": (
            r"inject|insertion|insert|attach|prepend|append",
            r"starting layer|from layer|layer j|upper layer|higher layer|late layer|selected layers",
            r"if self\.layer in|for layer in|layer_idx|block_idx",
        ),
        "insertion_anchor_policy": (
            r"insert|inject|insertion|concat|concatenate|cat\(|append|prepend|splice",
            r"after|before|between|order|position|index|offset|anchor",
            r"token|sequence|embedding|hidden|state|prompt|prefix|suffix|patch",
        ),
        "trainability_boundary": (
            r"requires_grad\s*=\s*False",
            r"frozen|freeze|fixed|not trainable",
            r"trainable|learnable|named_parameters",
            r"projection|head|adapter|lora",
        ),
    }
    if extra_keywords:
        kws = [k.strip() for k in extra_keywords if str(k).strip()]
        if kws:
            topics["custom_mechanism_keywords"] = tuple(re.escape(k) for k in kws)
    if custom_topics:
        for topic, kws in custom_topics.items():
            t = str(topic or "").strip()
            if not t:
                continue
            normalized = [str(x).strip() for x in (kws or []) if str(x).strip()]
            if not normalized:
                continue
            escaped = tuple(re.escape(x) for x in normalized)
            if t in topics:
                topics[t] = tuple(list(topics[t]) + list(escaped))
            else:
                topics[t] = escaped
    return topics


def _targeted_evidence_from_text(
    rel_path: str,
    text: str,
    max_chars: int,
    topic_patterns: dict[str, tuple[str, ...]],
) -> list[dict[str, Any]]:
    lines = text.splitlines()
    if not lines:
        return []
    out: list[dict[str, Any]] = []
    for topic, pats in topic_patterns.items():
        compiled = [re.compile(p, flags=re.IGNORECASE) for p in pats]
        hits: list[int] = []
        for i, line in enumerate(lines, start=1):
            if any(p.search(line) for p in compiled):
                hits.append(i)
        if not hits:
            continue
        windows: list[tuple[int, int]] = []
        for h in hits[:6]:
            windows.append((h - 10, h + 24))
        snippet = _snippet_from_line_windows(text, windows, max_chars=max_chars)
        if not snippet:
            continue
        out.append(
            {
                "path": rel_path,
                "topic": topic,
                "line": int(hits[0]),
                "hit_count": len(hits),
                "relevance_score": _method_relevance_score(snippet) + min(3.0, 0.3 * len(hits)),
                "source": "line_window",
                "snippet": snippet,
            }
        )
    return out


def _iter_python_blocks(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    if not lines:
        return []
    try:
        tree = ast.parse(text)
    except Exception:
        return []
    blocks: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = int(getattr(node, "lineno", 0) or 0)
            end = int(getattr(node, "end_lineno", 0) or 0)
            if start <= 0 or end <= 0 or end < start:
                continue
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            name = str(getattr(node, "name", "") or "")
            code = "\n".join(lines[start - 1 : end]).strip()
            if not code:
                continue
            blocks.append({"kind": kind, "name": name, "start": start, "end": end, "code": code})
    blocks.sort(key=lambda x: int(x.get("start") or 0))
    return blocks


def _line_no_from_offset(text: str, offset: int) -> int:
    off = max(0, min(len(text), int(offset)))
    return text.count("\n", 0, off) + 1


def _find_matching_brace(text: str, open_idx: int) -> int:
    if open_idx < 0 or open_idx >= len(text) or text[open_idx] != "{":
        return -1
    depth = 0
    in_str: str | None = None
    esc = False
    i = open_idx
    while i < len(text):
        ch = text[i]
        if in_str is not None:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == in_str:
                in_str = None
        else:
            if ch in {"'", '"', "`"}:
                in_str = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return -1


def _iter_js_ts_blocks(text: str) -> list[dict[str, Any]]:
    patterns = [
        re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z_$][\w$]*)[^{\n]*\{", re.MULTILINE),
        re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{", re.MULTILINE),
        re.compile(
            r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{",
            re.MULTILINE,
        ),
    ]
    blocks: list[dict[str, Any]] = []
    for pat in patterns:
        for m in pat.finditer(text):
            name = m.group(1) if m.groups() else ""
            open_idx = text.find("{", m.start())
            if open_idx < 0:
                continue
            close_idx = _find_matching_brace(text, open_idx)
            if close_idx < 0:
                continue
            start_line = _line_no_from_offset(text, m.start())
            end_line = _line_no_from_offset(text, close_idx)
            code = text[m.start() : close_idx + 1].strip()
            if not code:
                continue
            kind = "class" if "class" in m.group(0) else "function"
            blocks.append({"kind": kind, "name": name, "start": start_line, "end": end_line, "code": code})
    blocks.sort(key=lambda x: int(x.get("start") or 0))
    # Deduplicate by (start,end,name)
    uniq: list[dict[str, Any]] = []
    seen: set[tuple[int, int, str]] = set()
    for b in blocks:
        k = (int(b.get("start") or 0), int(b.get("end") or 0), str(b.get("name") or ""))
        if k in seen:
            continue
        seen.add(k)
        uniq.append(b)
    return uniq


def _targeted_evidence_from_blocks(
    rel_path: str,
    text: str,
    suffix: str,
    max_chars: int,
    topic_patterns: dict[str, tuple[str, ...]],
) -> list[dict[str, Any]]:
    ext = (suffix or "").lower()
    if ext == ".py":
        blocks = _iter_python_blocks(text)
        source = "ast"
    elif ext in {".js", ".jsx", ".ts", ".tsx"}:
        blocks = _iter_js_ts_blocks(text)
        source = "regex_block"
    else:
        return []
    if not blocks:
        return []

    out: list[dict[str, Any]] = []
    for topic, pats in topic_patterns.items():
        compiled = [re.compile(p, flags=re.IGNORECASE) for p in pats]
        cands: list[dict[str, Any]] = []
        for b in blocks:
            code = str(b.get("code") or "")
            if not code:
                continue
            hit = sum(1 for p in compiled if p.search(code))
            if hit <= 0:
                continue
            snippet = code[:max_chars].strip()
            score = _method_relevance_score(snippet) + min(4.0, 0.7 * hit)
            cands.append(
                {
                    "path": rel_path,
                    "topic": topic,
                    "line": int(b.get("start") or 1),
                    "hit_count": int(hit),
                    "relevance_score": float(score),
                    "source": source,
                    "snippet": snippet,
                }
            )
        cands.sort(
            key=lambda x: (float(x.get("relevance_score") or 0.0), int(x.get("hit_count") or 0)),
            reverse=True,
        )
        out.extend(cands[:2])
    return out


def _mechanism_path_bonus(rel_path: str) -> float:
    p = (rel_path or "").lower()
    bonus = 0.0
    if "/scripts/" in p or p.endswith(".sh"):
        bonus -= 2.0
    if "/eval/" in p or p.endswith("_evaluator.py"):
        bonus -= 1.2
    if "/serve/" in p:
        bonus -= 1.2
    if "/pretrained_weight/" in p:
        bonus -= 1.0
    return bonus


def scan_repository(
    repo_root: Path,
    cfg: ScanConfig,
    focus_filename: str = "",
    focus_filenames: list[str] | None = None,
    mechanism_keywords: list[str] | None = None,
    mechanism_topics: dict[str, list[str]] | None = None,
    annotation_priority: str = "balanced",
) -> dict[str, Any]:
    ann_mode = _annotation_mode(annotation_priority)
    ann_profile = _annotation_mode_profile(ann_mode)
    files = _iter_code_files(repo_root, cfg)
    topic_patterns = _topic_patterns(
        custom_topics=mechanism_topics,
        extra_keywords=mechanism_keywords,
    )
    scored: list[FileScore] = []
    snippets: dict[str, str] = {}
    annotations_by_file: dict[str, list[str]] = {}
    annotated_snippets: list[dict[str, Any]] = []
    annotation_anchor_lines: dict[str, list[int]] = {}
    targeted_evidence: list[dict[str, Any]] = []

    for f in files:
        text = read_text_safe(f, cfg.max_file_bytes)
        if not text.strip():
            continue
        fs = _score_file(f, repo_root, text, annotation_priority=ann_mode)
        scored.append(fs)
        snippets[fs.rel] = _snippet_from_text(text, cfg.max_snippet_chars)
        targeted_evidence.extend(
            _targeted_evidence_from_text(
                fs.rel,
                text,
                cfg.max_snippet_chars,
                topic_patterns=topic_patterns,
            )
        )
        targeted_evidence.extend(
            _targeted_evidence_from_blocks(
                fs.rel,
                text,
                f.suffix.lower(),
                cfg.max_snippet_chars,
                topic_patterns=topic_patterns,
            )
        )

        ann = _extract_annotations(text)
        if ann:
            annotations_by_file[fs.rel] = ann
            anchors = _annotation_anchors(text)
            annotation_anchor_lines[fs.rel] = [int(a.get("line") or 1) for a in anchors]
            for anchor in anchors:
                snippet = _window_snippet(text, int(anchor["line"]), radius=14, max_chars=cfg.max_snippet_chars)
                rel_score = _method_relevance_score(snippet + "\n" + str(anchor["text"]))
                annotated_snippets.append(
                    {
                        "path": fs.rel,
                        "line": int(anchor["line"]),
                        "marker": str(anchor.get("marker") or ""),
                        "annotation": str(anchor["text"]),
                        "relevance_score": rel_score,
                        "snippet": snippet,
                    }
                )

    scored.sort(key=lambda x: x.score, reverse=True)
    core = scored[: cfg.core_top_k]

    raw_focus_names = list(focus_filenames or [])
    if focus_filename and str(focus_filename).strip():
        raw_focus_names.append(str(focus_filename).strip())
    # normalize and deduplicate while preserving order
    norm_focus: list[str] = []
    seen_focus: set[str] = set()
    for item in raw_focus_names:
        n = Path(str(item).strip()).name.lower()
        if not n or n in seen_focus:
            continue
        seen_focus.add(n)
        norm_focus.append(n)

    focused_matches: list[FileScore] = []
    if norm_focus:
        focused_map = {name: [] for name in norm_focus}
        for s in scored:
            n = s.path.name.lower()
            if n in focused_map:
                focused_map[n].append(s)
        for name in norm_focus:
            arr = focused_map.get(name) or []
            if arr:
                # highest scored candidate for each requested focus filename
                focused_matches.append(sorted(arr, key=lambda x: x.score, reverse=True)[0])
        if focused_matches:
            existing = {c.rel for c in core}
            focused_front = [f for f in focused_matches if f.rel not in existing]
            if focused_front:
                keep_n = max(0, cfg.core_top_k - len(focused_front))
                remainder = [c for c in core if c.rel not in {f.rel for f in focused_front}]
                core = focused_front + remainder[:keep_n]

    # Keep annotation influence bounded: hint-priority, not hard trust.
    annotated_rel = set(annotations_by_file.keys())
    if annotated_rel:
        annotated_candidates = [s for s in scored if s.rel in annotated_rel]
        annotated_candidates.sort(key=lambda x: x.score, reverse=True)
        forced_n = max(1, int(round(cfg.core_top_k * float(ann_profile["forced_ratio"]))))
        max_forced = min(len(annotated_candidates), max(2 if ann_mode == "strong" else 1, forced_n))

        existing = {c.rel for c in core}
        forced: list[FileScore] = []
        for cand in annotated_candidates:
            if cand.score < 1.0:
                continue
            if cand.rel in existing:
                forced.append(cand)
                continue
            if len(forced) >= max_forced:
                break
            forced.append(cand)

        forced_rel = {f.rel for f in forced}
        remainder = [c for c in core if c.rel not in forced_rel]
        merged = forced + remainder
        if len(merged) < cfg.core_top_k:
            merged_rel = {m.rel for m in merged}
            for cand in scored:
                if cand.rel in merged_rel:
                    continue
                merged.append(cand)
                merged_rel.add(cand.rel)
                if len(merged) >= cfg.core_top_k:
                    break
        core = merged[: cfg.core_top_k]

    touchpoint_summary: dict[str, int] = {k: 0 for k in TOUCHPOINT_PATTERNS}
    for item in core:
        for k, v in item.touchpoints.items():
            touchpoint_summary[k] += int(v)

    annotated_snippets_sorted = sorted(
        annotated_snippets,
        key=lambda x: (float(x.get("relevance_score") or 0.0), -int(x.get("line") or 0)),
        reverse=True,
    )
    core_rel_set = {c.rel for c in core}
    # Keep only higher-confidence annotation anchors for primary LLM context.
    # Rule: include anchors from core files, or non-core anchors with enough method relevance.
    annotated_snippets_selected: list[dict[str, Any]] = []
    for item in annotated_snippets_sorted:
        path = str(item.get("path") or "")
        rel_score = float(item.get("relevance_score") or 0.0)
        if path in core_rel_set or rel_score >= 2.5:
            annotated_snippets_selected.append(item)
        if len(annotated_snippets_selected) >= 16:
            break

    # Mechanism-level evidence selection for robust method extraction.
    # Generic preference: core files + annotated files + focus-related paths.
    topic_best: dict[str, dict[str, Any]] = {}
    focus_stem = Path(str(focus_filename or "")).stem.lower()
    generic_stems = {"model", "train", "main", "run", "app", "cli"}
    annotated_rel_set = set(annotations_by_file.keys())

    def _focus_path_bonus(path: str) -> float:
        p = (path or "").lower()
        if not focus_stem or focus_stem in generic_stems:
            return 0.0
        return 2.0 if focus_stem in p else 0.0

    def _annotation_proximity_bonus(item: dict[str, Any]) -> float:
        path = str(item.get("path") or "")
        line = int(item.get("line") or 0)
        anchors = annotation_anchor_lines.get(path) or []
        if not anchors or line <= 0:
            return 0.0
        nearest = min(abs(line - a) for a in anchors)
        if nearest <= 20:
            return float(ann_profile["prox_near"])
        if nearest <= 60:
            return float(ann_profile["prox_mid"])
        return 0.0

    targeted_sorted = sorted(
        targeted_evidence,
        key=lambda x: (
            1 if _annotation_proximity_bonus(x) >= 2.0 else 0,
            2 if str(x.get("source") or "") == "ast" else (1 if str(x.get("source") or "") == "regex_block" else 0),
            1 if str(x.get("path") or "") in core_rel_set else 0,
            1 if str(x.get("path") or "") in annotated_rel_set else 0,
            _focus_path_bonus(str(x.get("path") or "")),
            _annotation_proximity_bonus(x),
            _mechanism_path_bonus(str(x.get("path") or "")),
            float(x.get("relevance_score") or 0.0),
            int(x.get("hit_count") or 0),
        ),
        reverse=True,
    )
    for item in targeted_sorted:
        topic = str(item.get("topic") or "")
        if topic and topic not in topic_best:
            topic_best[topic] = item
    selected_mechanism = list(topic_best.values())
    selected_paths = {(x.get("path"), x.get("topic")) for x in selected_mechanism}
    for item in targeted_sorted:
        key = (item.get("path"), item.get("topic"))
        if key in selected_paths:
            continue
        selected_mechanism.append(item)
        selected_paths.add(key)
        if len(selected_mechanism) >= 10:
            break

    report = {
        "repo_root": str(repo_root),
        "scanned_files": len(scored),
        "core_file_count": len(core),
        "focus_file": focus_filename,
        "focus_file_in_core": bool(
            (Path(str(focus_filename).strip()).name.lower() if focus_filename else "")
            and any(c.path.name.lower() == Path(str(focus_filename).strip()).name.lower() for c in core)
        ),
        "focus_files": norm_focus,
        "focus_files_in_core_count": sum(1 for n in norm_focus if any(c.path.name.lower() == n for c in core)),
        "annotation_policy": "annotations_are_hints_not_mandatory_claims",
        "annotation_priority": ann_mode,
        "annotation_marker": ANNOTATION_MARKERS[0],
        "annotation_markers": list(ANNOTATION_MARKERS),
        "annotated_file_count": len(annotations_by_file),
        "annotated_files": [
            {"path": rel, "annotations": anns}
            for rel, anns in sorted(annotations_by_file.items())
        ],
        "annotated_snippet_count": len(annotated_snippets_sorted),
        "annotated_snippet_selected_count": len(annotated_snippets_selected),
        "annotated_snippets_selected": annotated_snippets_selected,
        "annotated_snippets": annotated_snippets_sorted[:24],
        "targeted_mechanism_evidence_count": len(targeted_evidence),
        "targeted_mechanism_evidence_selected_count": len(selected_mechanism),
        "targeted_mechanism_evidence": selected_mechanism[:10],
        "targeted_mechanism_sources": {
            "ast": sum(1 for x in targeted_evidence if str(x.get("source") or "") == "ast"),
            "regex_block": sum(1 for x in targeted_evidence if str(x.get("source") or "") == "regex_block"),
            "line_window": sum(1 for x in targeted_evidence if str(x.get("source") or "") == "line_window"),
        },
        "mechanism_topic_names": sorted(topic_patterns.keys()),
        "custom_mechanism_keywords": [str(x).strip() for x in (mechanism_keywords or []) if str(x).strip()],
        "custom_mechanism_topics": {
            str(k): [str(x).strip() for x in (v or []) if str(x).strip()]
            for k, v in (mechanism_topics or {}).items()
            if str(k).strip()
        },
        "core_files": [
            {
                "path": c.rel,
                "score": c.score,
                "reasons": c.reasons,
                "touchpoints": c.touchpoints,
            }
            for c in core
        ],
        "touchpoint_summary": touchpoint_summary,
        "core_snippets": {c.rel: snippets.get(c.rel, "") for c in core},
        # Backward compatibility
        "snippets": {c.rel: snippets.get(c.rel, "") for c in core},
    }
    return report

