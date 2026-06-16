"""Integration tests for Task 5: Skill Migration to LangGraph.

Verifies all 7 skills parse correctly with YAML frontmatter,
have correct phase counts, GATE phase identification, and
SkillGraphBuilder integration.
"""
import os
import glob as glob_mod

import pytest

from datamind.engine.skills import SkillParser, SkillDefinition, SkillStep


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _skills_dir():
    return os.path.join(
        os.path.dirname(__file__), "..", "..", "skills"
    )


def _parse_skill(name: str) -> SkillDefinition:
    parser = SkillParser()
    path = os.path.join(_skills_dir(), f"{name}.md")
    return parser.parse_file(path)


# ---------------------------------------------------------------------------
# 1. YAML frontmatter extraction
# ---------------------------------------------------------------------------

class TestYamlFrontmatter:
    """Verify all 7 skills have YAML frontmatter extracted correctly."""

    def test_frontmatter_present_on_all_skills(self):
        """Every skill file must have non-empty frontmatter after parsing."""
        skill_files = glob_mod.glob(os.path.join(_skills_dir(), "*.md"))
        parser = SkillParser()

        for path in skill_files:
            content = open(path, encoding="utf-8").read()
            # Content must start with --- for YAML frontmatter
            assert content.startswith("---"), (
                f"{os.path.basename(path)} missing YAML frontmatter"
            )
            skill = parser.parse(content)
            assert skill.frontmatter is not None, (
                f"{os.path.basename(path)}: frontmatter is None"
            )
            assert "skill" in skill.frontmatter, (
                f"{os.path.basename(path)}: frontmatter missing 'skill' key"
            )
            assert "version" in skill.frontmatter, (
                f"{os.path.basename(path)}: frontmatter missing 'version' key"
            )
            assert skill.frontmatter["version"] == 2

    def test_data_cleaning_frontmatter(self):
        """data-cleaning has routing (2 gates) and tools config."""
        skill = _parse_skill("data-cleaning")
        fm = skill.frontmatter

        assert fm["skill"] == "data-cleaning"
        assert "gate-3" in fm["routing"]
        assert "gate-6" in fm["routing"]
        assert fm["routing"]["gate-3"]["approve"] == "execute"
        assert fm["routing"]["gate-3"]["reject"] == "propose-strategy"
        assert fm["routing"]["gate-6"]["approve"] == "archive"
        assert fm["routing"]["gate-6"]["reject"] == "execute"
        assert "tools" in fm
        assert "phase-1" in fm["tools"]
        assert "phase-4" in fm["tools"]

    def test_model_training_frontmatter(self):
        """model-training has parallel config and routing."""
        skill = _parse_skill("model-training")
        fm = skill.frontmatter

        assert fm["skill"] == "model-training"
        # Routing
        assert "gate-3" in fm["routing"]
        assert fm["routing"]["gate-3"]["approve"] == "train"
        assert fm["routing"]["gate-3"]["reject"] == "select-models"
        assert "gate-6" in fm["routing"]
        assert fm["routing"]["gate-6"]["approve"] == "archive"
        assert fm["routing"]["gate-6"]["reject"] == "train"
        # Tools
        assert "phase-1" in fm["tools"]
        assert "phase-4" in fm["tools"]
        # Parallel
        assert "parallel" in fm
        assert "train" in fm["parallel"]
        assert fm["parallel"]["train"]["candidates"] == 3
        assert fm["parallel"]["train"]["merge"] == "evaluate"

    def test_feature_engineering_frontmatter(self):
        """feature-engineering has routing (1 gate) and tools config."""
        skill = _parse_skill("feature-engineering")
        fm = skill.frontmatter

        assert fm["skill"] == "feature-engineering"
        assert "gate-3" in fm["routing"]
        assert fm["routing"]["gate-3"]["approve"] == "execute"
        assert fm["routing"]["gate-3"]["reject"] == "select-features"
        assert "phase-1" in fm["tools"]

    def test_linear_skill_frontmatter(self):
        """4 remaining linear skills have minimal frontmatter (skill + version)."""
        linear_skills = [
            "auto-archive",
            "requirement-discussion",
            "report-generation",
            "data-exploration",
        ]
        for name in linear_skills:
            skill = _parse_skill(name)
            fm = skill.frontmatter
            assert fm["skill"] == name, f"{name}: frontmatter['skill'] mismatch"
            assert fm["version"] == 2


# ---------------------------------------------------------------------------
# 2. Phase count validation
# ---------------------------------------------------------------------------

class TestPhaseCounts:
    """Verify each skill has the expected number of phases."""

    EXPECTED = {
        "data-cleaning": 7,
        "model-training": 7,
        "feature-engineering": 8,
        "auto-archive": 5,
        "requirement-discussion": 7,
        "report-generation": 6,
        "data-exploration": 5,
    }

    @pytest.mark.parametrize("skill_name,expected_count", EXPECTED.items())
    def test_phase_count(self, skill_name, expected_count):
        skill = _parse_skill(skill_name)
        assert len(skill.phases) == expected_count, (
            f"{skill_name}: expected {expected_count} phases, got {len(skill.phases)}"
        )


# ---------------------------------------------------------------------------
# 3. GATE phase identification
# ---------------------------------------------------------------------------

class TestGatePhaseIdentification:
    """Verify GATE phases are correctly identified in each skill."""

    EXPECTED_GATES = {
        "data-cleaning": 2,
        "model-training": 2,
        "feature-engineering": 2,
        "auto-archive": 1,
        "requirement-discussion": 2,
        "report-generation": 2,
        "data-exploration": 1,
    }

    @pytest.mark.parametrize("skill_name,expected_gates", EXPECTED_GATES.items())
    def test_gate_count(self, skill_name, expected_gates):
        skill = _parse_skill(skill_name)
        gate_phases = [p for p in skill.phases if p.type == "GATE"]
        assert len(gate_phases) == expected_gates, (
            f"{skill_name}: expected {expected_gates} GATE phases, got {len(gate_phases)}"
        )

    def test_no_gate_as_final_phase(self):
        """No skill ends with a GATE phase."""
        for skill_name in self.EXPECTED_GATES:
            skill = _parse_skill(skill_name)
            assert skill.phases[-1].type != "GATE", (
                f"{skill_name}: final phase must not be GATE"
            )

    def test_gate_phases_have_kebab_ids(self):
        """All GATE phases have 'gate-' prefix in their ids."""
        for skill_name in self.EXPECTED_GATES:
            skill = _parse_skill(skill_name)
            gate_phases = [p for p in skill.phases if p.type == "GATE"]
            for gp in gate_phases:
                assert gp.id.startswith("gate-"), (
                    f"{skill_name}: GATE phase '{gp.id}' missing 'gate-' prefix"
                )


# ---------------------------------------------------------------------------
# 4. SkillGraphBuilder integration
# ---------------------------------------------------------------------------

class TestSkillGraphBuilderIntegration:
    """Verify SkillGraphBuilder can build compiled graphs from all skills."""

    @pytest.mark.parametrize("skill_name", [
        "data-cleaning", "model-training", "feature-engineering",
        "auto-archive", "requirement-discussion", "report-generation",
        "data-exploration",
    ])
    def test_build_graph_from_skill(self, skill_name):
        """SkillGraphBuilder.build() succeeds for each skill."""
        from datamind.engine.langgraph_agent import SkillGraphBuilder
        from langgraph.graph import StateGraph

        skill = _parse_skill(skill_name)
        builder = SkillGraphBuilder(skill_def=skill)
        compiled = builder.build()

        # Must be compiled (not raw StateGraph)
        assert not isinstance(compiled, StateGraph)
        assert hasattr(compiled, "invoke")

        # All phase nodes must be present
        node_names = list(compiled.nodes.keys())
        for phase in skill.phases:
            assert phase.id in node_names, (
                f"{skill_name}: node '{phase.id}' not found in graph"
            )

    def test_model_training_graph_uses_frontmatter_routing(self):
        """model-training graph uses frontmatter routing for reject edges."""
        from datamind.engine.langgraph_agent import SkillGraphBuilder

        skill = _parse_skill("model-training")
        builder = SkillGraphBuilder(skill_def=skill)
        compiled = builder.build()

        branches = compiled.builder.branches
        # Gate at index 2 (gate-3) should have reject → "select-models"
        gate_branch = branches.get("gate-model-choice")
        assert gate_branch is not None, "gate-model-choice must have a branch"
        branch_spec = list(gate_branch.values())[0]
        assert branch_spec.ends["reject"] == "select-models", (
            f"Expected reject → select-models, got {branch_spec.ends.get('reject')}"
        )

    def test_data_cleaning_graph_uses_frontmatter_routing(self):
        """data-cleaning graph uses frontmatter routing for reject edges."""
        from datamind.engine.langgraph_agent import SkillGraphBuilder

        skill = _parse_skill("data-cleaning")
        builder = SkillGraphBuilder(skill_def=skill)
        compiled = builder.build()

        branches = compiled.builder.branches
        # Gate at index 2 (gate-3) should have reject → "propose-strategy"
        gate_branch = branches.get("gate-approve-strategy")
        assert gate_branch is not None, "gate-approve-strategy must have a branch"
        branch_spec = list(gate_branch.values())[0]
        assert branch_spec.ends["reject"] == "propose-strategy", (
            f"Expected reject → propose-strategy, got {branch_spec.ends.get('reject')}"
        )
