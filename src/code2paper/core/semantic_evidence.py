from __future__ import annotations

import re


_CONCEPT_ALIASES: dict[str, set[str]] = {
    "aggregate": {"aggregate", "aggregated", "aggregating", "aggregation", "average", "averaging", "sum"},
    "bounded": {"few", "fewshot", "small"},
    "data": {"data", "dataset", "demonstration", "demonstrations", "sample", "samples"},
    "domain": {"domain", "domains", "mixed", "multi"},
    "dynamic_filter": {"conv2d", "convolution", "dynamic", "filter", "filtering", "kernel", "kernels"},
    "expert": {"expert", "experts", "idx", "idxs", "indices"},
    "gating": {"gate", "gating", "router", "routing"},
    "grouping": {"group", "grouped", "groups", "parallel"},
    "hierarchy": {"base", "bank", "compose", "composed", "composition", "hierarchical", "hierarchy", "nested"},
    "moe": {"moe", "mixture", "rmoe", "smoe", "fullmoe"},
    "norm": {"l2", "magnitude", "norm", "normalization", "normalize", "normalized", "norms"},
    "output": {"out", "output", "outputs"},
    "product": {"multiply", "multiplied", "product"},
    "representation": {"hidden", "representation", "state", "states", "x_before", "x_before_moe", "x_after", "x_after_moe"},
    "score": {"importance", "score", "scores", "weight", "weights"},
    "select": {"keep", "mask", "prune", "pruned", "pruning", "retain", "retained", "scatter", "select", "selection", "top", "topk"},
    "similarity": {"cos", "cosine", "similarity", "simibr"},
}


def concepts_semantically_related(claim_text: str, evidence_text: str) -> bool:
    """Conservatively recognize implementation operators hidden by prose/code syntax."""

    claim_concepts = semantic_concepts(claim_text)
    evidence_concepts = semantic_concepts(evidence_text)
    if "product" in claim_concepts and "*" in evidence_text:
        evidence_concepts.add("product")
    if "norm" in claim_concepts and re.search(
        r"\bscore\s*=\s*score\s*/\s*(?:torch\.)?sum\s*\(", evidence_text,
        flags=re.IGNORECASE,
    ):
        evidence_concepts.add("norm")
    if "bounded" in claim_concepts and re.search(
        r"\b(?:data|samples?)\s*\[[^\]\n]*:\s*\d+\s*\]", evidence_text,
        flags=re.IGNORECASE,
    ):
        evidence_concepts.add("bounded")
    overlap = claim_concepts & evidence_concepts
    if len(overlap) < 2:
        return False
    signatures = claim_concepts & {"aggregate", "bounded", "norm", "select", "similarity"}
    if signatures and not signatures.issubset(evidence_concepts):
        return False
    return len(overlap) / max(1, len(claim_concepts)) >= 0.5 or len(overlap) >= 3


def semantic_concepts(text: str) -> set[str]:
    normalized = re.sub(r"\bMoE\b", "moe", str(text or ""), flags=re.IGNORECASE)
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", normalized)
    compounds = set(re.findall(r"[a-z0-9]+(?:_[a-z0-9]+)+", normalized.lower()))
    tokens = set(re.findall(r"[a-z0-9]+", normalized.replace("_", " ").lower())) | compounds
    concepts = {
        concept
        for concept, aliases in _CONCEPT_ALIASES.items()
        if tokens & aliases
    }
    if re.search(r"\bmoe\s*(?:-|\s)\s*in\s*(?:-|\s)\s*moe\b", normalized, flags=re.IGNORECASE):
        concepts.add("hierarchy")
    return concepts
