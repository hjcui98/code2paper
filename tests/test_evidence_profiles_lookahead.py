"""Tests for LookaheadReasoningProfile: match, compile, behavior contract, and mutation rejection."""

from __future__ import annotations

from pathlib import Path

from code2paper.agentic.evidence_compiler_v3 import (
    compile_evidence_v3,
    validate_evidence_compiler_v3,
)
from code2paper.agentic.evidence_profiles.lookahead_reasoning import (
    LookaheadReasoningProfile,
    _behavior_contract_satisfied,
)
from code2paper.agentic.evidence_profiles.registry import (
    default_evidence_profile_registry,
)
from code2paper.agentic.repo_snapshot import build_repo_snapshot


def _write_minimal_fixture(root: Path) -> None:
    """Write minimal Lookahead Reasoning source files with all required symbols and patterns."""
    src = root / "src"
    src.mkdir(parents=True)

    (src / "vllm_model.py").write_text(
        '''import asyncio
from vllm.engine.async_llm_engine import AsyncLLM
from vllm.sampling_params import SamplingParams

class LLMModel:
    def __init__(self, model_path):
        self.engine = AsyncLLM.from_engine_args(model_path)
        self.SamplingParams = SamplingParams

    async def generate(self, prompt, temperature=0.7, top_p=0.95, top_k=50, stop=None):
        params = SamplingParams(temperature=temperature, top_p=top_p, top_k=top_k, stop=stop)
        result = await self.engine.generate(prompt, params)
        text = result.text
        finish_reason = result.finish_reason
        stop_reason = result.stop_reason
        num_tokens = result.num_tokens
        token_ids = result.token_ids
        return text, finish_reason, stop_reason, num_tokens, token_ids

class Drafter:
    def __init__(self, model_path):
        self.model = LLMModel(model_path)

    async def draft(self, prompt, temperature=0.7):
        return await self.model.generate(prompt, temperature=temperature)

class Targeter:
    def __init__(self, model_path):
        self.model = LLMModel(model_path)

    async def target(self, prompt, temperature=0.7):
        return await self.model.generate(prompt, temperature=temperature)
''',
        encoding="utf-8",
    )

    (src / "lr_tree.py").write_text(
        '''import asyncio

class MainNode:
    def __init__(self, targeter, prompt):
        self.targeter = targeter
        self.prompt = prompt
        self.result = None
        self.task = None

    async def target(self):
        self.task = asyncio.create_task(self.targeter.target(self.prompt))
        return self.task

class DrafterNode:
    def __init__(self, drafter, prompt):
        self.drafter = drafter
        self.prompt = prompt
        self.result = None
        self.task = None

    async def draft(self):
        self.task = asyncio.create_task(self.drafter.draft(self.prompt))
        return self.task

class TreeNode:
    def __init__(self, prompt, drafter, targeter, depth=0):
        self.prompt = prompt
        self.drafter = drafter
        self.targeter = targeter
        self.depth = depth
        self.children = []
        self.main_node = None
        self.draft_node = None
        self.accepted = False

    def start_main_if_possible(self):
        if self.draft_node and self.draft_node.result and not self.main_node:
            self.main_node = MainNode(self.targeter, self.prompt)
            self.main_task = self.main_node.target()

    def collect_main_if_possible(self):
        if self.main_node and self.main_node.task and self.main_node.task.done():
            self.main_node.result = self.main_node.task.result()

    def travel_set_accepted(self, accept_func):
        for child in self.children:
            child.accepted = accept_func(child.draft_node.result, child.main_node.result)

    def check_judge_children(self):
        return all(child.accepted for child in self.children)

    def traverse(self):
        self.draft_node = DrafterNode(self.drafter, self.prompt)
        self.draft_node.draft()
        self.start_main_if_possible()
        self.collect_main_if_possible()
        for child in self.children:
            child.traverse()

    def allocate_children(self, num_children):
        for _ in range(num_children):
            self.children.append(TreeNode(self.prompt, self.drafter, self.targeter, self.depth + 1))
''',
        encoding="utf-8",
    )

    (src / "lr.py").write_text(
        '''import asyncio

def equal_prompt(a, b):
    return a.strip() == b.strip()

def text_accept(draft_text, target_text):
    if equal_prompt(draft_text, target_text):
        return True
    # LLM-as-judge semantic comparison
    if "[aligned]" in draft_text and "[aligned]" in target_text:
        return True
    return "[unaligned]" in draft_text or "[unaligned]" in target_text

def accept_func(draft_text, target_text):
    return text_accept(draft_text, target_text)

def run_problem(question, drafter, targeter):
    root = TreeNode(question, drafter, targeter)
    root.traverse()
    root.travel_set_accepted(accept_func)
    root.check_judge_children()
    return root
''',
        encoding="utf-8",
    )

    (root / "main.py").write_text(
        '''import asyncio
from src.vllm_model import Targeter, Drafter
from src.lr import run_problem

def main():
    questions = ["What is 2+2?"]
    targeter = Targeter("target-model")
    drafter = Drafter("draft-model")
    for q in questions:
        result = run_problem(q, drafter, targeter)
        print(result)
    asyncio.run(main())

if __name__ == "__main__":
    main()
''',
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Positive match/compile tests
# ---------------------------------------------------------------------------

def test_minimal_fixture_match_and_compile_positive(tmp_path: Path) -> None:
    """Profile matches and compiles with minimal real source fixture."""
    _write_minimal_fixture(tmp_path)
    snapshot = build_repo_snapshot(tmp_path)

    profile = LookaheadReasoningProfile()
    match_result = profile.match(snapshot)
    assert match_result.matched, f"match failed: {match_result.reasons}"
    assert match_result.missing_required_fingerprints == []

    result = compile_evidence_v3(snapshot)
    assert result is not None, "compile returned None"
    assert result.profile_id == "lookahead_step_level_speculative_decoding"
    assert not validate_evidence_compiler_v3(result, snapshot)


def test_all_supported_claims_have_facts_and_spans(tmp_path: Path) -> None:
    """Every supported claim must have facts and direct spans from real code."""
    _write_minimal_fixture(tmp_path)
    snapshot = build_repo_snapshot(tmp_path)
    result = compile_evidence_v3(snapshot)
    assert result is not None

    fact_by_id = {f.fact_id: f for f in result.facts.facts if f.validation_status == "supported"}
    span_by_id = {s.span_id: s for packet in result.packets.packets for s in packet.spans}

    for claim in result.claims.claims:
        assert claim.status in ("supported", "partial"), f"{claim.claim_id}: status={claim.status}"
        assert len(claim.fact_ids) > 0, f"{claim.claim_id}: no fact_ids"
        assert len(claim.direct_evidence_ids) > 0, f"{claim.claim_id}: no direct_evidence_ids"

        for fact_id in claim.fact_ids:
            assert fact_id in fact_by_id, f"{claim.claim_id}: unknown fact {fact_id}"

        for span_id in claim.direct_evidence_ids:
            assert span_id in span_by_id, f"{claim.claim_id}: unknown span {span_id}"


# ---------------------------------------------------------------------------
# Mutation rejection tests
# ---------------------------------------------------------------------------

def test_missing_drafter_symbol_rejects(tmp_path: Path) -> None:
    """Removing Drafter.__init__ causes profile rejection."""
    _write_minimal_fixture(tmp_path)
    path = tmp_path / "src/vllm_model.py"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "class Drafter:",
            "class DrafterRenamed:",
        ),
        encoding="utf-8",
    )
    snapshot = build_repo_snapshot(tmp_path)
    assert compile_evidence_v3(snapshot) is None


def test_missing_targeter_symbol_rejects(tmp_path: Path) -> None:
    """Removing Targeter.__init__ causes profile rejection."""
    _write_minimal_fixture(tmp_path)
    path = tmp_path / "src/vllm_model.py"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "class Targeter:",
            "class TargeterRenamed:",
        ),
        encoding="utf-8",
    )
    snapshot = build_repo_snapshot(tmp_path)
    assert compile_evidence_v3(snapshot) is None


def test_missing_tree_node_traverse_rejects(tmp_path: Path) -> None:
    """Removing TreeNode.traverse causes profile rejection."""
    _write_minimal_fixture(tmp_path)
    path = tmp_path / "src/lr_tree.py"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "def traverse(self):",
            "def traverse_renamed(self):",
        ),
        encoding="utf-8",
    )
    snapshot = build_repo_snapshot(tmp_path)
    assert compile_evidence_v3(snapshot) is None


def test_missing_asyncio_create_task_rejects_behavior(tmp_path: Path) -> None:
    """Removing asyncio.create_task pattern causes behavior contract rejection."""
    _write_minimal_fixture(tmp_path)
    path = tmp_path / "src/lr_tree.py"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "asyncio.create_task",
            "None  # create_task removed",
        ),
        encoding="utf-8",
    )
    assert not _behavior_contract_satisfied(tmp_path)
    snapshot = build_repo_snapshot(tmp_path)
    assert compile_evidence_v3(snapshot) is None


def test_missing_main_function_rejects(tmp_path: Path) -> None:
    """Removing main() from main.py causes rejection."""
    _write_minimal_fixture(tmp_path)
    path = tmp_path / "main.py"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "def main():",
            "def main_renamed():",
        ),
        encoding="utf-8",
    )
    snapshot = build_repo_snapshot(tmp_path)
    assert compile_evidence_v3(snapshot) is None


def test_missing_text_accept_rejects_behavior(tmp_path: Path) -> None:
    """Removing text_accept function causes behavior contract rejection."""
    _write_minimal_fixture(tmp_path)
    path = tmp_path / "src/lr.py"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "def text_accept(",
            "def removed_text_accept(",
        ),
        encoding="utf-8",
    )
    assert not _behavior_contract_satisfied(tmp_path)
    snapshot = build_repo_snapshot(tmp_path)
    assert compile_evidence_v3(snapshot) is None


# ---------------------------------------------------------------------------
# Same-name but no behavior tests
# ---------------------------------------------------------------------------

def test_same_name_symbols_no_behavior_no_match(tmp_path: Path) -> None:
    """Symbols with the same names but no corresponding behavior must not match."""
    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / "src/vllm_model.py").write_text(
        '''class LLMModel:
    def __init__(self, path): pass
    def generate(self, prompt): return "text", "ok", "ok", 1, []
class Drafter:
    def __init__(self, path): pass
    def draft(self, prompt): return "text", "ok", "ok", 1, []
class Targeter:
    def __init__(self, path): pass
    def target(self, prompt): return "text", "ok", "ok", 1, []
''',
        encoding="utf-8",
    )
    (tmp_path / "src/lr_tree.py").write_text(
        '''class MainNode:
    def __init__(self): pass
    def target(self): pass
class DrafterNode:
    def __init__(self): pass
    def draft(self): pass
class TreeNode:
    def __init__(self): pass
    def start_main_if_possible(self): pass
    def collect_main_if_possible(self): pass
    def traverse(self): pass
    def travel_set_accepted(self): pass
    def check_judge_children(self): pass
''',
        encoding="utf-8",
    )
    (tmp_path / "src/lr.py").write_text(
        '''def run_problem(): pass
def accept_func(): pass
def text_accept(): pass
''',
        encoding="utf-8",
    )
    (tmp_path / "main.py").write_text(
        '''def main(): pass
''',
        encoding="utf-8",
    )
    profile = LookaheadReasoningProfile()
    snapshot = build_repo_snapshot(tmp_path)
    match_result = profile.match(snapshot)
    assert not match_result.matched, f"should not match without behavior: {match_result.reasons}"
    assert not _behavior_contract_satisfied(tmp_path)


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------

def test_registry_selects_lookahead_profile(tmp_path: Path) -> None:
    """Registry correctly selects LookaheadReasoningProfile for the fixture."""
    _write_minimal_fixture(tmp_path)
    snapshot = build_repo_snapshot(tmp_path)
    profile, matches = default_evidence_profile_registry().select(snapshot)
    assert profile is not None
    assert profile.profile_id == "lookahead_step_level_speculative_decoding"
    la_match = next(m for m in matches if m.profile_id == "lookahead_step_level_speculative_decoding")
    assert la_match.matched
    assert la_match.missing_required_fingerprints == []


def test_registry_does_not_select_lookahead_without_drafter(tmp_path: Path) -> None:
    """Registry must not select Lookahead profile when Drafter.draft is missing."""
    _write_minimal_fixture(tmp_path)
    path = tmp_path / "src/vllm_model.py"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "async def draft(self,",
            "async def draft_renamed(self,",
        ),
        encoding="utf-8",
    )
    snapshot = build_repo_snapshot(tmp_path)
    profile, matches = default_evidence_profile_registry().select(snapshot)
    assert profile is None or profile.profile_id != "lookahead_step_level_speculative_decoding"
    la_match = next(m for m in matches if m.profile_id == "lookahead_step_level_speculative_decoding")
    assert "draft_model_and_generation" in la_match.missing_required_fingerprints


def test_profile_does_not_activate_from_project_name_or_prose(tmp_path: Path) -> None:
    """Profile must not activate from project name or paper prose alone."""
    (tmp_path / "paper.md").write_text(
        "Lookahead Reasoning uses speculative decoding with vLLM async generation.",
        encoding="utf-8",
    )
    snapshot = build_repo_snapshot(tmp_path)
    assert compile_evidence_v3(snapshot) is None