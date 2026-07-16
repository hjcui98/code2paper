"""T006: Tests for AuthorMarkers schema extensions (FastGS YAML compatibility).

Verifies:
- FastGS YAML loads without error and preserves all new fields.
- method_mainline accepts both str (backwards compat) and list[str] (FastGS).
- pipeline_steps[].related_components is explicitly modeled.
- key_building_blocks, possible_distinguishing_points, scope_constraints are modeled.
- Strict validation still rejects unrelated unknown top-level keys.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from pydantic import ValidationError

from code2paper.core.schemas import (
    AuthorKeyBuildingBlock,
    AuthorMarkers,
    AuthorPipelineStep,
    AuthorScopeConstraints,
)

_FASTGS_YAML = (
    Path(__file__).resolve().parent.parent
    / "datasets"
    / "FastGS"
    / "FastGS - Training 3D Gaussian Splatting in 100 Seconds.yaml"
)


class TestMethodMainlineBackwardsCompat(unittest.TestCase):
    """method_mainline must accept both str and list[str]."""

    def test_string_mainline_preserved(self) -> None:
        m = AuthorMarkers.model_validate(
            {"project_goal": "test", "method_mainline": "step1 -> step2 -> step3"}
        )
        self.assertEqual(m.method_mainline, "step1 -> step2 -> step3")

    def test_list_mainline_normalized_to_string(self) -> None:
        m = AuthorMarkers.model_validate(
            {"project_goal": "test", "method_mainline": ["step1", "step2", "step3"]}
        )
        self.assertIsInstance(m.method_mainline, str)
        self.assertEqual(m.method_mainline, "step1\nstep2\nstep3")

    def test_empty_list_mainline(self) -> None:
        m = AuthorMarkers.model_validate({"project_goal": "test", "method_mainline": []})
        self.assertEqual(m.method_mainline, "")

    def test_default_mainline_is_empty_string(self) -> None:
        m = AuthorMarkers.model_validate({"project_goal": "test"})
        self.assertEqual(m.method_mainline, "")


class TestRelatedComponents(unittest.TestCase):
    """pipeline_steps[].related_components must be explicitly modeled."""

    def test_related_components_accepted(self) -> None:
        m = AuthorMarkers.model_validate(
            {
                "project_goal": "test",
                "pipeline_steps": [
                    {
                        "name": "Densification",
                        "purpose": "Add Gaussians",
                        "related_components": ["VCD", "VCP"],
                    }
                ],
            }
        )
        self.assertEqual(m.pipeline_steps[0].related_components, ["VCD", "VCP"])

    def test_related_components_default_empty(self) -> None:
        step = AuthorPipelineStep(name="Init", purpose="Start")
        self.assertEqual(step.related_components, [])


class TestKeyBuildingBlocks(unittest.TestCase):
    """key_building_blocks must be explicitly modeled."""

    def test_building_blocks_loaded(self) -> None:
        m = AuthorMarkers.model_validate(
            {
                "project_goal": "test",
                "key_building_blocks": [
                    {"name": "VCD", "role": "Densification control", "emphasis": "high", "keep_name": True},
                    {"name": "CB", "role": "Rasterization", "emphasis": "medium", "keep_name": False},
                ],
            }
        )
        self.assertEqual(len(m.key_building_blocks), 2)
        self.assertEqual(m.key_building_blocks[0].name, "VCD")
        self.assertEqual(m.key_building_blocks[0].emphasis, "high")
        self.assertTrue(m.key_building_blocks[0].keep_name)
        self.assertEqual(m.key_building_blocks[1].emphasis, "medium")

    def test_invalid_emphasis_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AuthorMarkers.model_validate(
                {
                    "project_goal": "test",
                    "key_building_blocks": [{"name": "X", "emphasis": "critical"}],
                }
            )

    def test_empty_name_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AuthorKeyBuildingBlock(name="  ", role="test")


class TestPossibleDistinguishingPoints(unittest.TestCase):
    """possible_distinguishing_points must be explicitly modeled as list[str]."""

    def test_distinguishing_points_loaded(self) -> None:
        m = AuthorMarkers.model_validate(
            {
                "project_goal": "test",
                "possible_distinguishing_points": ["Point A", "Point B"],
            }
        )
        self.assertEqual(m.possible_distinguishing_points, ["Point A", "Point B"])

    def test_default_empty(self) -> None:
        m = AuthorMarkers.model_validate({"project_goal": "test"})
        self.assertEqual(m.possible_distinguishing_points, [])


class TestScopeConstraints(unittest.TestCase):
    """scope_constraints must be explicitly modeled."""

    def test_scope_constraints_loaded(self) -> None:
        m = AuthorMarkers.model_validate(
            {
                "project_goal": "test",
                "scope_constraints": {
                    "use_current_codebase_only": True,
                    "avoid_readme_only_claims": True,
                    "avoid_paper_only_novelty_claims": False,
                },
            }
        )
        self.assertTrue(m.scope_constraints.use_current_codebase_only)
        self.assertTrue(m.scope_constraints.avoid_readme_only_claims)
        self.assertFalse(m.scope_constraints.avoid_paper_only_novelty_claims)

    def test_default_scope_constraints(self) -> None:
        m = AuthorMarkers.model_validate({"project_goal": "test"})
        self.assertFalse(m.scope_constraints.use_current_codebase_only)
        self.assertFalse(m.scope_constraints.avoid_readme_only_claims)
        self.assertFalse(m.scope_constraints.avoid_paper_only_novelty_claims)


class TestStrictValidationPreserved(unittest.TestCase):
    """Unknown top-level keys must still be rejected."""

    def test_unknown_top_level_key_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AuthorMarkers.model_validate(
                {"project_goal": "test", "totally_unknown_field": "oops"}
            )

    def test_unknown_nested_key_in_pipeline_step_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AuthorMarkers.model_validate(
                {
                    "project_goal": "test",
                    "pipeline_steps": [
                        {"name": "X", "purpose": "Y", "bogus_field": True}
                    ],
                }
            )

    def test_unknown_key_in_scope_constraints_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AuthorScopeConstraints.model_validate({"unknown_bool": True})


@unittest.skipUnless(_FASTGS_YAML.exists(), "FastGS dataset not available")
class TestFastGSYAMLLoad(unittest.TestCase):
    """The real FastGS YAML must load through AuthorMarkers without error."""

    def test_fastgs_yaml_loads(self) -> None:
        from code2paper.core.author_questionnaire import load_author_markers

        markers = load_author_markers(_FASTGS_YAML)
        self.assertIsInstance(markers, AuthorMarkers)

    def test_fastgs_method_mainline_is_string(self) -> None:
        from code2paper.core.author_questionnaire import load_author_markers

        markers = load_author_markers(_FASTGS_YAML)
        self.assertIsInstance(markers.method_mainline, str)
        self.assertIn("Initialize", markers.method_mainline)

    def test_fastgs_key_building_blocks(self) -> None:
        from code2paper.core.author_questionnaire import load_author_markers

        markers = load_author_markers(_FASTGS_YAML)
        self.assertEqual(len(markers.key_building_blocks), 5)
        names = [b.name for b in markers.key_building_blocks]
        self.assertIn("Multi-View Consistent Densification (VCD)", names)

    def test_fastgs_pipeline_steps_have_related_components(self) -> None:
        from code2paper.core.author_questionnaire import load_author_markers

        markers = load_author_markers(_FASTGS_YAML)
        self.assertEqual(len(markers.pipeline_steps), 6)
        # Step 1 (Multi-view error computation) should reference VCD and VCP
        error_step = markers.pipeline_steps[1]
        self.assertEqual(error_step.related_components, ["VCD", "VCP"])

    def test_fastgs_scope_constraints(self) -> None:
        from code2paper.core.author_questionnaire import load_author_markers

        markers = load_author_markers(_FASTGS_YAML)
        self.assertTrue(markers.scope_constraints.use_current_codebase_only)
        self.assertTrue(markers.scope_constraints.avoid_readme_only_claims)
        self.assertTrue(markers.scope_constraints.avoid_paper_only_novelty_claims)

    def test_fastgs_possible_distinguishing_points(self) -> None:
        from code2paper.core.author_questionnaire import load_author_markers

        markers = load_author_markers(_FASTGS_YAML)
        self.assertEqual(len(markers.possible_distinguishing_points), 4)


if __name__ == "__main__":
    unittest.main()
