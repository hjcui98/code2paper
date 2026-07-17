from __future__ import annotations

import json
from types import SimpleNamespace
import unittest
from pathlib import Path

from code2paper.agents.bridge import _build_raw_pack_from_snippets
from code2paper.agentic.contracts import AgenticRunState, StageStatus
from code2paper.agentic.coverage_decisioning import coverage_decision_trace
from code2paper.agentic.graph_retrieval_nodes import coverage_critic_node
from code2paper.agentic.legacy_stage_tools import build_legacy_stage_tool_registry
from code2paper.agentic.legacy_retrieval_focus import rescan_focus_from_state
from code2paper.agentic.retrieval import (
    AgenticRetrievalPlan,
    RetrievalCoverageReport,
    RetrievalDecisionCandidate,
    RetrievalDecisionContext,
    RetrievalDecisionGap,
    RetrievalRescanGuidance,
    RetrievalRescanItem,
    RetrievalRescanPlan,
    RetrievalTarget,
    augment_retrieval_rescan_plan_with_guidance,
    build_agentic_retrieval_plan,
    build_retrieval_decision_context,
    build_retrieval_coverage_report,
    build_retrieval_rescan_plan,
    build_retrieval_rescan_report,
    build_symbol_index,
    enrich_plan_with_orchestrator_targets,
    load_retrieval_decision_context,
    load_retrieval_rescan_plan,
    load_retrieval_rescan_report,
    SymbolIndexEntry,
    SymbolIndexReport,
)
from code2paper.agentic.retrieval_summary import (
    RetrievalEvidenceSummary,
    RetrievalPriorityTarget,
    build_retrieval_evidence_summary,
    load_retrieval_evidence_summary,
    write_retrieval_evidence_summary,
)
from code2paper.agentic.retrieval_strategy_manifest import load_retrieval_strategy_manifest
from code2paper.agentic.rescan_evidence_freeze import freeze_rescan_symbol_index_evidence
from code2paper.core.schemas import LLMConfig, RawEvidencePack, SourceType
from code2paper.pipeline.stages.intake import _merge_retrieval_hints
from tests.tempdir_support import workspace_tempdir


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
TOY_MARKERS = FIXTURES / "toy_train_project_author_markers.yaml"
TOY_PROJECT = FIXTURES / "toy_train_project"


class AgenticRetrievalTests(unittest.TestCase):
    def test_retrieval_plan_is_derived_from_author_markers_without_llm_key(self) -> None:
        plan = build_agentic_retrieval_plan(
            author_markers_path=TOY_MARKERS,
            llm_config=LLMConfig(provider="none"),
        )

        self.assertEqual(plan.mode, "deterministic")
        self.assertIn("train.py", plan.priority_files)
        self.assertIn("configs/base.yaml", plan.priority_files)
        self.assertTrue(any(target.target_type == "pipeline_step" for target in plan.targets))
        self.assertTrue(any("training" in keyword for keyword in plan.search_keywords))

    def test_coverage_report_marks_targets_covered_or_missing(self) -> None:
        plan = AgenticRetrievalPlan(
            author_goal="test",
            priority_files=["train.py", "missing.py"],
            targets=[
                RetrievalTarget(
                    target_id="RT1",
                    target_type="pipeline_step",
                    query="Training execution",
                    paths=["train.py"],
                ),
                RetrievalTarget(
                    target_id="RT2",
                    target_type="pipeline_step",
                    query="Missing stage",
                    paths=["missing.py"],
                ),
            ],
        )
        snippets = {
            "snippets": [
                {
                    "snippet_id": "S1",
                    "source": {"path": "/repo/train.py", "symbol": "main"},
                    "text": "def main(): run training execution",
                }
            ]
        }

        report = build_retrieval_coverage_report(plan=plan, snippets_payload=snippets)

        by_id = {item.target_id: item for item in report.items}
        self.assertEqual(by_id["RT1"].support_status, "covered")
        self.assertEqual(by_id["RT2"].support_status, "missing")
        self.assertEqual(report.covered_targets, 1)
        self.assertEqual(report.missing_targets, 1)
        self.assertIn("rescan_missing_paths_or_symbols", report.recommended_actions)

    def test_coverage_report_does_not_cover_exact_symbol_targets_with_mentions_only(self) -> None:
        plan = AgenticRetrievalPlan(
            author_goal="agent orchestration",
            targets=[
                RetrievalTarget(
                    target_id="RT1",
                    target_type="orchestrator_symbol",
                    query="PlannerAgent",
                    paths=["agents/planner_agent.py"],
                    symbols=["PlannerAgent"],
                    priority="high",
                )
            ],
        )
        snippets = {
            "snippets": [
                {
                    "snippet_id": "S-mention",
                    "source": {"path": "utils/paperviz_processor.py", "symbol": "PaperVizProcessor"},
                    "text": "processor = PaperVizProcessor(planner_agent=PlannerAgent())",
                },
                {
                    "snippet_id": "S-class",
                    "source": {"path": "agents/planner_agent.py", "symbol": "PlannerAgent"},
                    "text": "class PlannerAgent:\n    pass",
                },
            ]
        }

        report = build_retrieval_coverage_report(plan=plan, snippets_payload=snippets)

        self.assertEqual(report.items[0].support_status, "covered")
        self.assertEqual(report.items[0].matched_snippet_ids, ["S-class"])

    def test_coverage_score_prefers_explicit_retrieval_targets_over_legacy_alignment(self) -> None:
        plan = AgenticRetrievalPlan(
            author_goal="agent orchestration",
            targets=[
                RetrievalTarget(
                    target_id="RT1",
                    target_type="orchestrator_symbol",
                    query="PlannerAgent",
                    paths=["agents/planner_agent.py"],
                    symbols=["PlannerAgent"],
                    priority="high",
                )
            ],
        )
        snippets = {
            "snippets": [
                {
                    "snippet_id": "S-class",
                    "source": {"path": "agents/planner_agent.py", "symbol": "PlannerAgent"},
                    "text": "class PlannerAgent:\n    pass",
                }
            ]
        }

        report = build_retrieval_coverage_report(
            plan=plan,
            snippets_payload=snippets,
            alignment_payload={"coverage_report": {"overall_score": 0.0}},
        )

        self.assertEqual(report.covered_targets, 1)
        self.assertEqual(report.missing_targets, 0)
        self.assertEqual(report.overall_score, 1.0)
        self.assertEqual(report.target_coverage_score, 1.0)
        self.assertEqual(report.legacy_alignment_score, 0.0)
        self.assertEqual(report.score_basis, "retrieval_targets")

    def test_symbol_index_ranks_author_targeted_python_symbols(self) -> None:
        plan = build_agentic_retrieval_plan(
            author_markers_path=TOY_MARKERS,
            llm_config=LLMConfig(provider="none"),
        )

        report = build_symbol_index(project_root=TOY_PROJECT, plan=plan)

        self.assertGreaterEqual(report.indexed_files, 1)
        self.assertGreaterEqual(report.indexed_symbols, 1)
        top = report.candidates[0]
        self.assertEqual(top.path, "train.py")
        self.assertEqual(top.symbol, "main")
        self.assertIn("RT1", top.matched_target_ids)
        self.assertTrue(top.text_hash.startswith("sha256:"))

    def test_rescan_symbol_index_locations_freeze_into_evidence_ids(self) -> None:
        with workspace_tempdir() as tmpdir:
            project_root = Path(tmpdir)
            config_path = project_root / "configs" / "base.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("dataset:\n  path: data/train.jsonl\n", encoding="utf-8")
            rescan_plan = RetrievalRescanPlan(
                items=[
                    RetrievalRescanItem(
                        item_id="RS1",
                        source="coverage_gap",
                        path="configs/base.yaml",
                        symbol="dataset.path",
                        query="dataset path",
                    )
                ]
            )
            symbol_index = SymbolIndexReport(
                project_root=str(project_root),
                indexed_files=1,
                indexed_symbols=1,
                candidates=[
                    SymbolIndexEntry(
                        path="configs/base.yaml",
                        symbol="dataset.path",
                        kind="config_key",
                        start_line=2,
                        end_line=2,
                    )
                ],
            )

            freeze = freeze_rescan_symbol_index_evidence(
                project_root=project_root,
                raw_pack=RawEvidencePack(project_id="toy", project_root=str(project_root)),
                snippets_payload={"snippets": []},
                evidence_index={},
                rescan_plan=rescan_plan,
                symbol_index=symbol_index,
            )
            report = build_retrieval_rescan_report(
                plan=rescan_plan,
                snippets_payload=freeze.snippets_payload,
                snippet_to_evidence=freeze.evidence_index,
                symbol_index=symbol_index,
            )

        self.assertEqual(freeze.frozen_count, 1)
        self.assertEqual(freeze.raw_pack.evidence_items[0].source_type, SourceType.CONFIG)
        self.assertEqual(freeze.raw_pack.evidence_items[0].config_key, "dataset.path")
        self.assertEqual(report.covered_items, 1)
        self.assertEqual(report.partial_items, 0)
        self.assertEqual(report.items[0].evidence_ids, ["E1"])

    def test_bridge_preserves_agentic_rescan_snippet_evidence_metadata(self) -> None:
        with workspace_tempdir() as tmpdir:
            project_root = Path(tmpdir)
            raw_pack, evidence_index = _build_raw_pack_from_snippets(
                repo=project_root,
                author_markers=SimpleNamespace(ignore_files=[]),
                core_snippets={
                    "snippets": [
                        {
                            "snippet_id": "AGENTIC_RESCAN_E4",
                            "source": {
                                "path": "configs/base.yaml",
                                "symbol": "dataset.path",
                                "start_line": 2,
                                "end_line": 2,
                            },
                            "text": "  path: data/train.jsonl",
                            "summary": "Agentic rescan froze symbol-index location dataset.path.",
                            "role": "agentic_rescan_symbol_index",
                            "confidence": 0.82,
                        }
                    ]
                },
                project_id="toy",
            )

        item = raw_pack.evidence_items[0]
        self.assertEqual(evidence_index, {"AGENTIC_RESCAN_E4": "E1"})
        self.assertEqual(item.source_type, SourceType.CONFIG)
        self.assertEqual(item.config_key, "dataset.path")
        self.assertEqual(item.tags, ["agentic_rescan", "symbol_index", "snippet_id:AGENTIC_RESCAN_E4"])

    def test_symbol_index_covers_config_keys_and_shell_entrypoints(self) -> None:
        with workspace_tempdir() as tmpdir:
            root = Path(tmpdir)
            config = root / "configs" / "base.yaml"
            script = root / "scripts" / "train.sh"
            config.parent.mkdir(parents=True)
            script.parent.mkdir(parents=True)
            config.write_text(
                "optimizer:\n  type: adamw\n  lr: 0.0003\ntraining:\n  epochs: 8\n",
                encoding="utf-8",
            )
            script.write_text(
                "run_training() {\n  python train.py --config configs/base.yaml\n}\n",
                encoding="utf-8",
            )
            plan = AgenticRetrievalPlan(
                author_goal="config driven training",
                priority_files=["configs/base.yaml", "scripts/train.sh"],
                search_keywords=["optimizer", "training"],
                targets=[
                    RetrievalTarget(
                        target_id="RT1",
                        target_type="config",
                        query="optimizer learning rate config",
                        paths=["configs/base.yaml"],
                        symbols=["optimizer.lr"],
                        priority="high",
                    ),
                    RetrievalTarget(
                        target_id="RT2",
                        target_type="entrypoint",
                        query="training shell entrypoint",
                        paths=["scripts/train.sh"],
                        symbols=["run_training"],
                        priority="high",
                    ),
                ],
            )

            report = build_symbol_index(project_root=root, plan=plan)

        by_kind = {(entry.kind, entry.symbol): entry for entry in report.candidates}
        self.assertIn(("config_key", "optimizer.lr"), by_kind)
        self.assertIn(("shell_function", "run_training"), by_kind)
        self.assertIn("RT1", by_kind[("config_key", "optimizer.lr")].matched_target_ids)
        self.assertIn("RT2", by_kind[("shell_function", "run_training")].matched_target_ids)
        self.assertGreaterEqual(report.indexed_files, 2)

    def test_orchestrator_imports_become_agentic_retrieval_targets(self) -> None:
        with workspace_tempdir() as tmpdir:
            root = Path(tmpdir)
            agents = root / "agents"
            agents.mkdir()
            (root / "main.py").write_text(
                "from agents.planner_agent import PlannerAgent\n\n"
                "def main():\n"
                "    return PlannerAgent().process('paper')\n",
                encoding="utf-8",
            )
            (agents / "planner_agent.py").write_text(
                "class PlannerAgent:\n"
                "    def process(self, paper):\n"
                "        return {'plan': paper}\n",
                encoding="utf-8",
            )
            plan = AgenticRetrievalPlan(
                author_goal="agent orchestration",
                priority_files=["main.py"],
                targets=[],
            )

            enriched = enrich_plan_with_orchestrator_targets(project_root=root, plan=plan)
            symbol_index = build_symbol_index(project_root=root, plan=enriched)

        orchestrator_targets = [
            target for target in enriched.targets if target.target_type == "orchestrator_symbol"
        ]
        self.assertEqual(len(orchestrator_targets), 1)
        self.assertEqual(orchestrator_targets[0].paths, ["agents/planner_agent.py"])
        self.assertEqual(orchestrator_targets[0].symbols, ["PlannerAgent"])
        self.assertEqual(orchestrator_targets[0].priority, "high")
        planner_entry = next(entry for entry in symbol_index.candidates if entry.symbol == "PlannerAgent")
        self.assertIn(orchestrator_targets[0].target_id, planner_entry.matched_target_ids)

    def test_retrieval_decision_context_summarizes_gaps_and_ranked_candidates(self) -> None:
        coverage = build_retrieval_coverage_report(
            plan=AgenticRetrievalPlan(
                targets=[
                    RetrievalTarget(
                        target_id="RT1",
                        target_type="pipeline_step",
                        query="optimizer schedule",
                        paths=["optim.py"],
                    )
                ]
            ),
            snippets_payload={"snippets": []},
        )
        symbol_index = SymbolIndexReport(
            project_root="/repo",
            candidates=[
                SymbolIndexEntry(
                    path="optim.py",
                    symbol="build_scheduler",
                    kind="function",
                    start_line=4,
                    end_line=12,
                    score=9.0,
                    matched_target_ids=["RT1"],
                    reasons=["symbol_target"],
                )
            ],
        )

        context = build_retrieval_decision_context(coverage=coverage, symbol_index=symbol_index)

        self.assertEqual(context.coverage_score, 0.0)
        self.assertEqual(context.gaps[0].target_id, "RT1")
        self.assertEqual(context.gaps[0].suggested_candidates[0].symbol, "build_scheduler")
        self.assertIn("optim.py", context.recommended_paths)
        self.assertIn("build_scheduler", context.recommended_symbols)
        self.assertIn("coverage=0.00", context.summary)

    def test_retrieval_rescan_plan_combines_coverage_gaps_and_repair_tasks(self) -> None:
        coverage = build_retrieval_coverage_report(
            plan=AgenticRetrievalPlan(
                targets=[
                    RetrievalTarget(
                        target_id="RT1",
                        target_type="pipeline_step",
                        query="optimizer schedule",
                        paths=["optim.py"],
                    )
                ]
            ),
            snippets_payload={"snippets": []},
        )
        context = build_retrieval_decision_context(
            coverage=coverage,
            symbol_index=SymbolIndexReport(
                project_root="/repo",
                candidates=[
                    SymbolIndexEntry(
                        path="optim.py",
                        symbol="build_scheduler",
                        kind="function",
                        score=9.0,
                        matched_target_ids=["RT1"],
                    )
                ],
            ),
        )

        plan = build_retrieval_rescan_plan(
            coverage=coverage,
            context=context,
            repair_tasks_payload={
                "tasks": [
                    {
                        "claim_id": "C2",
                        "claim_query": "C2: scheduler behavior",
                        "candidates": [
                            {"path": "optim.py", "symbol": "build_scheduler", "score": 8.0, "evidence_ids": []},
                            {"path": "train.py", "symbol": "main", "score": 3.0, "evidence_ids": ["E1"]},
                        ],
                    }
                ]
            },
        )

        self.assertEqual(plan.mode, "retrieval-rescan-plan")
        self.assertEqual(plan.coverage_score, 0.0)
        self.assertIn("retrieval_coverage", plan.source_artifacts)
        self.assertIn("analysis_repair_tasks", plan.source_artifacts)
        self.assertIn("optim.py", plan.recommended_paths)
        self.assertIn("build_scheduler", plan.recommended_symbols)
        self.assertEqual(plan.items[0].source, "analysis_repair_task")
        self.assertEqual(plan.items[0].claim_id, "C2")
        self.assertIn("rank:claim_evidence_repair", plan.items[0].reasons)
        self.assertTrue(any(item.source == "analysis_repair_task" and item.claim_id == "C2" for item in plan.items))
        self.assertFalse(any(item.path == "train.py" and item.source == "analysis_repair_task" for item in plan.items))

    def test_retrieval_rescan_plan_preserves_location_diversity_under_bounded_queue(self) -> None:
        coverage = RetrievalCoverageReport(overall_score=0.0, missing_targets=30)
        generic = RetrievalDecisionCandidate(
            path="runtime/server_args.py", symbol="ServerArgs", kind="class", score=100.0
        )
        method_specific = RetrievalDecisionCandidate(
            path="pruning/expert_selection.py", symbol="main", kind="function", score=10.0
        )
        context = RetrievalDecisionContext(
            coverage_score=0.0,
            missing_targets=30,
            gaps=[
                RetrievalDecisionGap(
                    target_id=f"RT{index}",
                    query=f"expert pruning target {index}",
                    support_status="missing",
                    suggested_candidates=[generic, method_specific],
                )
                for index in range(30)
            ],
        )

        plan = build_retrieval_rescan_plan(
            coverage=coverage,
            context=context,
            max_items=40,
        )

        paths = [item.path for item in plan.items]
        self.assertIn("pruning/expert_selection.py", paths)
        self.assertLessEqual(paths.count("runtime/server_args.py"), 4)
        self.assertLessEqual(paths.count("pruning/expert_selection.py"), 4)

    def test_retrieval_rescan_plan_keeps_deterministic_recommended_path_seed(self) -> None:
        plan = build_retrieval_rescan_plan(
            coverage=RetrievalCoverageReport(overall_score=0.5),
            context=RetrievalDecisionContext(
                coverage_score=0.5,
                recommended_paths=["pruning/expert_selection.py"],
            ),
        )

        self.assertEqual(len(plan.items), 1)
        self.assertEqual(plan.items[0].source, "deterministic_intent_seed")
        self.assertEqual(plan.items[0].path, "pruning/expert_selection.py")

    def test_retrieval_rescan_plan_accepts_coverage_critic_model_guidance(self) -> None:
        coverage = RetrievalCoverageReport(overall_score=0.25, missing_targets=1)
        base_plan = build_retrieval_rescan_plan(
            coverage=coverage,
            context=build_retrieval_decision_context(coverage=coverage),
        )

        plan = augment_retrieval_rescan_plan_with_guidance(
            plan=base_plan,
            guidance=RetrievalRescanGuidance(
                recommended_paths=["src/model.py"],
                recommended_symbols=["Model.forward"],
                recommended_queries=["forward pass evidence"],
            ),
        )

        model_items = [item for item in plan.items if item.source == "coverage_critic_decision"]
        self.assertEqual(len(model_items), 1)
        self.assertEqual(model_items[0].path, "src/model.py")
        self.assertEqual(model_items[0].symbol, "Model.forward")
        self.assertEqual(model_items[0].query, "forward pass evidence")
        self.assertIn("model_recommended_path", model_items[0].reasons)
        self.assertIn("coverage_critic_decision", plan.source_artifacts)
        self.assertIn("src/model.py", plan.recommended_paths)
        self.assertIn("Model.forward", plan.recommended_symbols)

    def test_coverage_critic_node_writes_model_guided_rescan_artifacts(self) -> None:
        with workspace_tempdir() as tmpdir:
            root = Path(tmpdir)
            method_root = root / "run"
            coverage_path = root / "retrieval_coverage.json"
            snippets_path = root / "snippets.json"
            evidence_index_path = root / "evidence_index.json"
            coverage_path.write_text(
                json.dumps(RetrievalCoverageReport(overall_score=0.25, missing_targets=1).model_dump(mode="json")),
                encoding="utf-8",
            )
            snippets_path.write_text(
                json.dumps(
                    {
                        "snippets": [
                            {
                                "snippet_id": "S-model",
                                "source": {"path": "src/model.py", "symbol": "Model.forward"},
                                "text": "class Model:\n    def forward(self, x): return x",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            evidence_index_path.write_text(json.dumps({"S-model": "E-model"}), encoding="utf-8")
            state = AgenticRunState(
                project_root=root,
                out_root=method_root,
                project_id="toy",
                artifacts={
                    "retrieval_coverage": str(coverage_path),
                    "snippets": str(snippets_path),
                    "evidence_index": str(evidence_index_path),
                },
                max_retrieval_rounds=1,
            )

            result = coverage_critic_node(
                decision_provider=lambda _prompt: {
                    "decision": "rescan_intake",
                    "rationale": "model selected missing forward implementation",
                    "recommended_next": "intake",
                    "recommended_paths": ["src/model.py"],
                    "recommended_symbols": ["Model.forward"],
                    "recommended_queries": ["forward pass evidence"],
                }
            )(state.model_dump(mode="json"))

            updated = AgenticRunState.model_validate(result)
            rescan_plan = load_retrieval_rescan_plan(updated.artifacts["retrieval_rescan_plan"])
            rescan_report = load_retrieval_rescan_report(updated.artifacts["retrieval_rescan_report"])
            model_items = [item for item in rescan_plan.items if item.source == "coverage_critic_decision"]
            self.assertEqual(model_items[0].path, "src/model.py")
            self.assertEqual(model_items[0].symbol, "Model.forward")
            self.assertEqual(rescan_report.items[0].status, "covered")
            self.assertEqual(rescan_report.items[0].evidence_ids, ["E-model"])
            self.assertEqual(updated.next_node, "intake")

    def test_retrieval_rescan_report_marks_items_covered_partial_or_missing(self) -> None:
        plan = build_retrieval_rescan_plan(
            coverage=RetrievalCoverageReport(overall_score=0.0),
            context=build_retrieval_decision_context(coverage=RetrievalCoverageReport(overall_score=0.0)),
            repair_tasks_payload={
                "tasks": [
                    {
                        "claim_id": "C2",
                        "claim_query": "C2: scheduler behavior",
                        "candidates": [
                            {"path": "optim.py", "symbol": "build_scheduler", "evidence_ids": []},
                            {"path": "train.py", "symbol": "main", "evidence_ids": []},
                            {"path": "missing.py", "symbol": "missing_fn", "evidence_ids": []},
                        ],
                    }
                ]
            },
        )

        report = build_retrieval_rescan_report(
            plan=plan,
            snippets_payload={
                "snippets": [
                    {
                        "snippet_id": "S1",
                        "source": {"path": "/repo/optim.py", "symbol": "build_scheduler"},
                        "text": "def build_scheduler(): pass",
                    },
                    {
                        "snippet_id": "S2",
                        "source": {"path": "/repo/train.py", "symbol": "main"},
                        "text": "def main(): pass",
                    },
                ]
            },
            snippet_to_evidence={"S1": "E1"},
        )

        by_path = {item.path: item for item in report.items}
        self.assertEqual(by_path["optim.py"].status, "covered")
        self.assertEqual(by_path["train.py"].status, "partial")
        self.assertEqual(by_path["missing.py"].status, "missing")
        self.assertEqual(by_path["missing.py"].priority, "high")
        self.assertIn("rank:claim_evidence_repair", by_path["missing.py"].reasons)
        self.assertEqual(report.covered_items, 1)
        self.assertEqual(report.partial_items, 1)
        self.assertEqual(report.missing_items, 1)
        self.assertEqual(report.high_priority_missing_items, 1)
        self.assertEqual(report.coverage_score, 0.5)
        self.assertIn("continue_high_priority_rescan_for_missing_items", report.recommended_actions)
        self.assertIn("continue_bounded_rescan_for_missing_items", report.recommended_actions)

    def test_retrieval_rescan_report_uses_symbol_index_as_partial_location_evidence(self) -> None:
        plan = build_retrieval_rescan_plan(
            coverage=RetrievalCoverageReport(overall_score=0.5),
            context=build_retrieval_decision_context(
                coverage=RetrievalCoverageReport(
                    overall_score=0.5,
                    items=[
                        {
                            "target_id": "RT1",
                            "query": "Configuration loading",
                            "support_status": "partial",
                            "missing_paths": ["configs/base.yaml"],
                        }
                    ],
                ),
                symbol_index=SymbolIndexReport(
                    project_root="/repo",
                    candidates=[
                        SymbolIndexEntry(
                            path="configs/base.yaml",
                            symbol="dataset.path",
                            kind="config_key",
                            docstring="data/train.jsonl",
                            matched_target_ids=["RT1"],
                        )
                    ],
                ),
            ),
        )

        report = build_retrieval_rescan_report(
            plan=plan,
            snippets_payload={"snippets": []},
            symbol_index=SymbolIndexReport(
                project_root="/repo",
                candidates=[
                    SymbolIndexEntry(
                        path="configs/base.yaml",
                        symbol="dataset.path",
                        kind="config_key",
                        docstring="data/train.jsonl",
                        matched_target_ids=["RT1"],
                    )
                ],
            ),
        )

        by_symbol = {item.symbol: item for item in report.items}
        self.assertEqual(by_symbol["dataset.path"].status, "partial")
        self.assertEqual(by_symbol["dataset.path"].evidence_ids, [])
        self.assertEqual(report.missing_items, 0)
        self.assertIn("map_matched_rescan_snippets_to_evidence_ids", report.recommended_actions)
        self.assertNotIn("continue_bounded_rescan_for_missing_items", report.recommended_actions)

    def test_retrieval_summary_compacts_ranking_gaps_and_rescan_evidence(self) -> None:
        coverage = build_retrieval_coverage_report(
            plan=AgenticRetrievalPlan(
                targets=[
                    RetrievalTarget(
                        target_id="RT1",
                        target_type="pipeline_step",
                        query="training entrypoint",
                        paths=["train.py"],
                    )
                ]
            ),
            snippets_payload={"snippets": []},
        )
        symbol_index = SymbolIndexReport(
            project_root=".",
            indexed_symbols=1,
            candidates=[
                SymbolIndexEntry(
                    path="train.py",
                    symbol="main",
                    kind="function",
                    score=7.5,
                    matched_target_ids=["RT1"],
                    reasons=["keyword:train"],
                )
            ],
        )
        context = build_retrieval_decision_context(coverage=coverage, symbol_index=symbol_index)
        rescan_plan = build_retrieval_rescan_plan(coverage=coverage, context=context)
        rescan_report = build_retrieval_rescan_report(
            plan=rescan_plan,
            snippets_payload={"snippets": [{"snippet_id": "S1", "path": "train.py", "text": "def main(): pass"}]},
            snippet_to_evidence={"S1": "E1"},
        )

        summary = build_retrieval_evidence_summary(
            coverage=coverage,
            symbol_index=symbol_index,
            context=context,
            rescan_report=rescan_report,
        )

        self.assertEqual(summary.top_symbols[0].path, "train.py")
        self.assertEqual(summary.gaps[0].target_id, "RT1")
        self.assertEqual(summary.prioritized_targets[0].target_id, "RT1")
        self.assertEqual(summary.prioritized_targets[0].path, "train.py")
        self.assertEqual(summary.prioritized_targets[0].symbol, "main")
        self.assertEqual(summary.prioritized_targets[0].status, "covered")
        self.assertIn("rescan_status:covered", summary.prioritized_targets[0].reasons)
        self.assertIn("coverage=", summary.summary)
        self.assertIn("E1", summary.evidence_ids_found)

        _decision, trace = coverage_decision_trace(coverage, retrieval_summary=summary)
        priority_attention = trace.prompt.inputs["retrieval_priority_attention"]
        self.assertEqual(priority_attention["top_prioritized_targets"][0]["target_id"], "RT1")
        self.assertEqual(priority_attention["top_prioritized_targets"][0]["path"], "train.py")

    def test_retrieval_summary_round_trips_to_json(self) -> None:
        coverage = RetrievalCoverageReport(overall_score=1.0)
        context = build_retrieval_decision_context(coverage=coverage)
        summary = build_retrieval_evidence_summary(
            coverage=coverage,
            symbol_index=SymbolIndexReport(project_root=".", indexed_symbols=0),
            context=context,
            rescan_report=build_retrieval_rescan_report(
                plan=build_retrieval_rescan_plan(coverage=coverage, context=context),
                snippets_payload={},
            ),
        )
        with workspace_tempdir() as tmpdir:
            path = Path(tmpdir) / "agentic_retrieval_summary.json"
            write_retrieval_evidence_summary(path, summary)
            loaded = load_retrieval_evidence_summary(path)

        self.assertEqual(loaded.mode, "agentic-retrieval-evidence-summary")

    def test_retrieval_summary_priority_targets_feed_next_intake_focus(self) -> None:
        summary = RetrievalEvidenceSummary(
            prioritized_targets=[
                RetrievalPriorityTarget(
                    target_id="RT9",
                    claim_id="C2",
                    query="scheduler behavior",
                    path="optim.py",
                    symbol="build_scheduler",
                    status="missing",
                    priority="high",
                    score=8.5,
                    reasons=["gap_status:missing"],
                ),
                RetrievalPriorityTarget(
                    target_id="RT10",
                    query="already evidenced path",
                    path="train.py",
                    symbol="main",
                    status="covered",
                    priority="medium",
                    score=4.0,
                    evidence_ids=["E1"],
                ),
            ]
        )
        with workspace_tempdir() as tmpdir:
            summary_path = Path(tmpdir) / "agentic_retrieval_summary.json"
            write_retrieval_evidence_summary(summary_path, summary)
            state = AgenticRunState(
                project_root=TOY_PROJECT,
                out_root=Path(tmpdir) / "agentic_run",
                project_id="toy_train_project",
                author_markers_path=str(TOY_MARKERS),
                artifacts={"retrieval_summary": str(summary_path)},
            )

            focus = rescan_focus_from_state(state)

        self.assertEqual(focus["priority_paths"], ["optim.py"])
        self.assertEqual(focus["search_keywords"], ["scheduler behavior"])
        self.assertEqual(focus["focus_claim_ids"], ["C2"])
        self.assertEqual(focus["symbol_targets"][0]["source"], "retrieval_priority_summary")
        self.assertEqual(focus["symbol_targets"][0]["target_id"], "RT9")
        self.assertEqual(focus["claim_targets"][0]["claim_id"], "C2")
        self.assertEqual(focus["claim_targets"][0]["candidates"][0]["path"], "optim.py")
        self.assertNotIn("train.py", focus["priority_paths"])

    def test_intake_overlay_preserves_repair_claim_targets_and_keywords(self) -> None:
        merged = _merge_retrieval_hints(
            {"retrieval_hints": {"priority_paths": ["train.py"]}},
            {
                "priority_paths": ["src/encoder.py"],
                "search_keywords": ["encoder repair"],
                "claim_targets": [
                    {
                        "claim_id": "C2",
                        "claim_query": "C2: encoder behavior",
                        "candidates": [{"path": "src/encoder.py", "symbol": "Encoder.forward"}],
                    }
                ],
            },
        )

        hints = merged["retrieval_hints"]
        self.assertEqual(hints["priority_paths"], ["train.py", "src/encoder.py"])
        self.assertEqual(hints["search_keywords"], ["encoder repair"])
        self.assertEqual(hints["claim_targets"][0]["claim_id"], "C2")

    def test_legacy_intake_tool_writes_retrieval_decision_artifacts(self) -> None:
        with workspace_tempdir() as tmpdir:
            state = AgenticRunState(
                project_root=TOY_PROJECT,
                out_root=Path(tmpdir) / "agentic_run",
                project_id="toy_train_project",
                author_markers_path=str(TOY_MARKERS),
                llm_provider="none",
            )
            result = build_legacy_stage_tool_registry()["intake"].invoke(state)

            self.assertEqual(result.status, StageStatus.SUCCESS)
            self.assertIn("retrieval_plan", result.artifacts)
            self.assertIn("symbol_index", result.artifacts)
            self.assertIn("retrieval_coverage", result.artifacts)
            self.assertIn("retrieval_decision_context", result.artifacts)
            self.assertIn("retrieval_rescan_plan", result.artifacts)
            self.assertIn("retrieval_rescan_report", result.artifacts)
            self.assertIn("retrieval_summary", result.artifacts)
            self.assertIn("retrieval_strategy_manifest", result.artifacts)
            self.assertTrue(Path(result.artifacts["retrieval_plan"]).exists())
            self.assertTrue(Path(result.artifacts["symbol_index"]).exists())
            self.assertTrue(Path(result.artifacts["retrieval_coverage"]).exists())
            loaded_context = load_retrieval_decision_context(result.artifacts["retrieval_decision_context"])
            self.assertIsNotNone(loaded_context)
            loaded_rescan_plan = load_retrieval_rescan_plan(result.artifacts["retrieval_rescan_plan"])
            self.assertIsNotNone(loaded_rescan_plan)
            loaded_rescan_report = load_retrieval_rescan_report(result.artifacts["retrieval_rescan_report"])
            self.assertIsNotNone(loaded_rescan_report)
            loaded_summary = load_retrieval_evidence_summary(result.artifacts["retrieval_summary"])
            self.assertGreaterEqual(loaded_summary.indexed_symbols, 1)
            loaded_strategy = load_retrieval_strategy_manifest(result.artifacts["retrieval_strategy_manifest"])
            self.assertEqual(loaded_strategy.coverage_score_basis, "retrieval_targets")
            self.assertIn("author_intent_priority_files", loaded_strategy.symbol_ranking_signals)
            self.assertIn("coverage_gap", loaded_strategy.rescan_queue_sources)
            self.assertIn("code_evidence_alignment", loaded_strategy.summary_uses)
            self.assertEqual(result.decisions[0].node, "retrieval_planner")
            self.assertIn("retrieval_strategy_manifest", result.decisions[0].artifact_keys)
            self.assertGreaterEqual(result.metrics["retrieval_targets"], 1)
            self.assertGreaterEqual(result.metrics["symbol_candidates"], 1)
            self.assertIn("rescan_plan_items", result.metrics)
            self.assertIn("rescan_covered_items", result.metrics)
            self.assertIn("retrieval_summary_actions", result.metrics)
            self.assertIn("retrieval_strategy_rules", result.metrics)

    def test_legacy_intake_tool_applies_coverage_critic_rescan_focus(self) -> None:
        with workspace_tempdir() as tmpdir:
            root = Path(tmpdir)
            decision_path = root / "coverage_critic_decision.json"
            decision_path.write_text(
                json.dumps(
                    {
                        "decision": "rescan_intake",
                        "rationale": "targeted retry",
                        "coverage_score": 0.25,
                        "missing_targets": 1,
                        "partial_targets": 0,
                        "recommended_next": "intake",
                        "recommended_paths": ["train.py"],
                        "recommended_symbols": ["main"],
                        "recommended_queries": ["training entrypoint"],
                        "artifact_keys": ["retrieval_coverage", "symbol_index"],
                    }
                ),
                encoding="utf-8",
            )
            state = AgenticRunState(
                project_root=TOY_PROJECT,
                out_root=root / "agentic_rescan",
                project_id="toy_train_project",
                author_markers_path=str(TOY_MARKERS),
                llm_provider="none",
                artifacts={"coverage_critic_decision": str(decision_path)},
            )

            result = build_legacy_stage_tool_registry()["intake"].invoke(state)

            self.assertEqual(result.status, StageStatus.SUCCESS)
            self.assertIn("rescan_focus", result.artifacts)
            self.assertTrue(Path(result.artifacts["rescan_focus"]).exists())
            self.assertEqual(result.metrics["focused_paths"], 1)
            self.assertEqual(result.metrics["focused_symbols"], 1)
            plan = json.loads(Path(result.artifacts["retrieval_plan"]).read_text(encoding="utf-8"))
            self.assertIn("Coverage critic rescan focus", plan["llm_decision_note"])


if __name__ == "__main__":
    unittest.main()
