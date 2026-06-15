"""Tests for MCP Server tools."""
from unittest import mock

from datamind.config import initialize_project
from datamind.engine.project import Project
from datamind.mcp.server import (
    tool_read_context, tool_register_dataset,
    tool_log_decision, tool_list_datasets,
    tool_execute_skill, tool_list_models,
    tool_approve_gate,
)


def test_tool_read_context(tmp_project):
    initialize_project(tmp_project)
    proj = Project(str(tmp_project))
    result = tool_read_context(proj)
    assert isinstance(result, str)
    assert "Context" in result


def test_tool_register_dataset(tmp_project):
    initialize_project(tmp_project)
    raw = tmp_project / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "test.csv").write_text("x\n1\n")
    proj = Project(str(tmp_project))
    result = tool_register_dataset(proj, str(raw / "test.csv"))
    assert "test.csv" in result


def test_tool_log_decision(tmp_project):
    initialize_project(tmp_project)
    proj = Project(str(tmp_project))
    result = tool_log_decision(proj, "use forward fill", "stocks don't interpolate")
    assert result["what"] == "use forward fill"


def test_tool_list_datasets(tmp_project):
    initialize_project(tmp_project)
    raw = tmp_project / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "a.csv").write_text("x\n1\n")
    proj = Project(str(tmp_project))
    proj.lineage.register_dataset(str(raw / "a.csv"))
    result = tool_list_datasets(proj)
    assert len(result) >= 1


# ---------------------------------------------------------------------------
# v2 MCP tool tests
# ---------------------------------------------------------------------------


class TestV2MCPTools:
    """Tests for tool_execute_skill and tool_list_models."""

    def test_tool_list_models(self, tmp_project):
        """tool_list_models returns active and available models."""
        initialize_project(tmp_project)
        proj = Project(str(tmp_project))
        # The project's LLM client may not have real models available;
        # just verify the structure
        result = tool_list_models(proj)
        assert "active" in result
        assert "available" in result
        assert isinstance(result["available"], list)

    def test_tool_list_models_with_mock(self, tmp_project):
        """tool_list_models reports list_models failures gracefully."""
        initialize_project(tmp_project)
        with mock.patch("datamind.engine.project.OpenAIClient") as mock_client_cls:
            mock_instance = mock.MagicMock()
            mock_instance.model = "gpt-4o"
            mock_instance.list_models.side_effect = Exception("API unavailable")
            mock_client_cls.return_value = mock_instance

            proj = Project(str(tmp_project))
            result = tool_list_models(proj)
            assert result["active"] == "gpt-4o"
            assert result["available"] == ["gpt-4o"]

    def test_tool_execute_skill_basic(self, tmp_project):
        """tool_execute_skill creates a session and runs agent through AUTO phases."""
        from datamind.config import initialize_project
        from datamind.engine.skill_state import SkillPhase
        initialize_project(tmp_project)

        # Create a skill file with AUTO phases only
        skills_dir = tmp_project / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        skill_md = skills_dir / "quick-summary.md"
        skill_md.write_text("""# Quick Summary
**Purpose:** Generate a quick summary
**Inputs:** Any CSV file

## Workflow
1. **Analyze** (AUTO) - Analyze the data
2. **Report** (AUTO) - Generate report

**Outputs:**
- summary.md
""")

        with mock.patch("datamind.engine.project.OpenAIClient") as mock_client_cls:
            mock_instance = mock.MagicMock()
            mock_instance.model = "gpt-4o"
            mock_instance.list_models.return_value = ["gpt-4o"]
            mock_client_cls.return_value = mock_instance

            with mock.patch("datamind.engine.agent.DataMindAgent") as mock_agent_cls:
                mock_agent = mock.MagicMock()
                from datamind.engine.agent import AgentResponse
                mock_agent.run.return_value = AgentResponse(
                    content="Analysis complete",
                    phase_id="report",
                    usage={"prompt_tokens": 10, "completion_tokens": 5},
                )
                mock_agent_cls.return_value = mock_agent

                proj = Project(str(tmp_project))
                result = tool_execute_skill(proj, "quick-summary", "data.csv")

            assert result["skill"] == "quick-summary"
            assert result["target"] == "data.csv"
            assert "session_id" in result
            # Either phase content or result is present
            assert "content" in result or "result" in result or "error" in result

    def test_tool_execute_skill_gate(self, tmp_project):
        """tool_execute_skill stops at GATE and returns gate info."""
        from datamind.config import initialize_project
        initialize_project(tmp_project)

        # Create a skill file with a GATE as first step
        skills_dir = tmp_project / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        skill_md = skills_dir / "gated-skill.md"
        skill_md.write_text("""# Gated Skill
**Purpose:** Test gated workflow
**Inputs:** Any CSV file

## Workflow
1. **Gate: Review** (GATE) - Human review required
2. **Execute** (AUTO) - Execute plan

**Outputs:**
- result.md
""")

        with mock.patch("datamind.engine.project.OpenAIClient") as mock_client_cls:
            mock_instance = mock.MagicMock()
            mock_instance.model = "gpt-4o"
            mock_instance.list_models.return_value = ["gpt-4o"]
            mock_client_cls.return_value = mock_instance

            with mock.patch("datamind.engine.agent.DataMindAgent") as mock_agent_cls:
                mock_agent = mock.MagicMock()
                from datamind.engine.agent import WaitForApproval
                mock_agent.run.return_value = WaitForApproval(
                    phase_id="gate-review",
                    phase_name="Gate: Review",
                    context_message="Please review the plan",
                )
                mock_agent_cls.return_value = mock_agent

                proj = Project(str(tmp_project))
                result = tool_execute_skill(proj, "gated-skill", "data.csv")

            assert result["skill"] == "gated-skill"
            assert "gate" in result
            assert result["gate"]["phase_id"] == "gate-review"

    def test_tool_execute_skill_complete(self, tmp_project):
        """tool_execute_skill returns result when skill completes immediately."""
        from datamind.config import initialize_project
        initialize_project(tmp_project)

        skills_dir = tmp_project / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        skill_md = skills_dir / "simple-skill.md"
        skill_md.write_text("""# Simple Skill
**Purpose:** Simple auto skill
**Inputs:** Any CSV file

## Workflow
1. **Process** (AUTO) - Process data

**Outputs:**
- result.md
""")

        with mock.patch("datamind.engine.project.OpenAIClient") as mock_client_cls:
            mock_instance = mock.MagicMock()
            mock_instance.model = "gpt-4o"
            mock_instance.list_models.return_value = ["gpt-4o"]
            mock_client_cls.return_value = mock_instance

            with mock.patch("datamind.engine.agent.DataMindAgent") as mock_agent_cls:
                mock_agent = mock.MagicMock()
                from datamind.engine.agent import SkillComplete
                mock_agent.run.return_value = SkillComplete(
                    result="pass",
                    usage={"totals": {"total_tokens": 50}},
                )
                mock_agent_cls.return_value = mock_agent

                proj = Project(str(tmp_project))
                result = tool_execute_skill(proj, "simple-skill", "data.csv")

            assert result["skill"] == "simple-skill"
            assert result["result"] == "pass"
            assert "usage" in result

    def test_tool_execute_skill_error(self, tmp_project):
        """tool_execute_skill returns error info when agent fails."""
        from datamind.config import initialize_project
        initialize_project(tmp_project)

        skills_dir = tmp_project / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        skill_md = skills_dir / "error-skill.md"
        skill_md.write_text("""# Error Skill
**Purpose:** Error test
**Inputs:** Any CSV file

## Workflow
1. **Process** (AUTO) - Process data

**Outputs:**
- result.md
""")

        with mock.patch("datamind.engine.project.OpenAIClient") as mock_client_cls:
            mock_instance = mock.MagicMock()
            mock_instance.model = "gpt-4o"
            mock_instance.list_models.return_value = ["gpt-4o"]
            mock_client_cls.return_value = mock_instance

            with mock.patch("datamind.engine.agent.DataMindAgent") as mock_agent_cls:
                mock_agent = mock.MagicMock()
                from datamind.engine.agent import AgentError
                mock_agent.run.return_value = AgentError(
                    error_message="LLM connection failed",
                )
                mock_agent_cls.return_value = mock_agent

                proj = Project(str(tmp_project))
                result = tool_execute_skill(proj, "error-skill", "data.csv")

            assert result["skill"] == "error-skill"
            assert "error" in result
            assert "LLM connection failed" in result["error"]


# ---------------------------------------------------------------------------
# tool_approve_gate tests
# ---------------------------------------------------------------------------


class TestV2ToolApproveGate:
    """Tests for tool_approve_gate MCP tool."""

    def test_approve_gate_runs_auto_phase(self, tmp_project):
        """tool_approve_gate: approve GATE, next AUTO runs agent through it."""
        from datamind.engine.skill_state import SkillPhase, SkillStateMachine
        initialize_project(tmp_project)

        # Create a session with GATE -> AUTO phases
        phases = [
            SkillPhase(id="gate-review", name="Gate Review", type="GATE"),
            SkillPhase(id="auto-execute", name="Auto Execute", type="AUTO"),
        ]
        sessions_dir = str(tmp_project / "data")
        from pathlib import Path
        Path(sessions_dir).mkdir(parents=True, exist_ok=True)
        sm = SkillStateMachine.create_session(
            "test-skill", "target.csv", phases, sessions_dir,
        )
        session_dir = str(Path(sessions_dir) / sm.state.session)

        with mock.patch("datamind.engine.project.OpenAIClient") as mock_client_cls:
            mock_instance = mock.MagicMock()
            mock_instance.model = "gpt-4o"
            mock_instance.list_models.return_value = ["gpt-4o"]
            mock_client_cls.return_value = mock_instance

            with mock.patch("datamind.engine.agent.DataMindAgent") as mock_agent_cls:
                mock_agent = mock.MagicMock()
                from datamind.engine.agent import AgentResponse
                mock_agent.run.return_value = AgentResponse(
                    content="Auto phase done",
                    phase_id="auto-execute",
                    usage={"prompt_tokens": 5, "completion_tokens": 3},
                )
                mock_agent_cls.return_value = mock_agent

                proj = Project(str(tmp_project))
                result = tool_approve_gate(proj, session_dir, {"approved": True})

            assert "phase" in result
            assert "result" in result

    def test_approve_gate_gate_to_gate(self, tmp_project):
        """tool_approve_gate: approve GATE, next GATE returns gate info."""
        from datamind.engine.skill_state import SkillPhase, SkillStateMachine
        initialize_project(tmp_project)

        # Two consecutive GATE phases
        phases = [
            SkillPhase(id="gate-review", name="Gate Review", type="GATE"),
            SkillPhase(id="gate-final", name="Gate Final", type="GATE"),
        ]
        sessions_dir = str(tmp_project / "data")
        from pathlib import Path
        Path(sessions_dir).mkdir(parents=True, exist_ok=True)
        sm = SkillStateMachine.create_session(
            "test-skill", "target.csv", phases, sessions_dir,
        )
        session_dir = str(Path(sessions_dir) / sm.state.session)

        with mock.patch("datamind.engine.project.OpenAIClient") as mock_client_cls:
            mock_instance = mock.MagicMock()
            mock_instance.model = "gpt-4o"
            mock_instance.list_models.return_value = ["gpt-4o"]
            mock_client_cls.return_value = mock_instance

            proj = Project(str(tmp_project))
            result = tool_approve_gate(proj, session_dir, {"approved": True})

        # Next phase is GATE, should return the next phase info
        assert result["phase"] == "gate-final"

    def test_approve_gate_completion(self, tmp_project):
        """tool_approve_gate: approve last GATE, workflow completes."""
        from datamind.engine.skill_state import SkillPhase, SkillStateMachine
        initialize_project(tmp_project)

        # Single GATE followed by AUTO
        phases = [
            SkillPhase(id="gate-review", name="Gate Review", type="GATE"),
            SkillPhase(id="auto-final", name="Auto Final", type="AUTO"),
        ]
        sessions_dir = str(tmp_project / "data")
        from pathlib import Path
        Path(sessions_dir).mkdir(parents=True, exist_ok=True)
        sm = SkillStateMachine.create_session(
            "test-skill", "target.csv", phases, sessions_dir,
        )
        session_dir = str(Path(sessions_dir) / sm.state.session)

        with mock.patch("datamind.engine.project.OpenAIClient") as mock_client_cls:
            mock_instance = mock.MagicMock()
            mock_instance.model = "gpt-4o"
            mock_instance.list_models.return_value = ["gpt-4o"]
            mock_client_cls.return_value = mock_instance

            with mock.patch("datamind.engine.agent.DataMindAgent") as mock_agent_cls:
                mock_agent = mock.MagicMock()
                from datamind.engine.agent import SkillComplete
                mock_agent.run.return_value = SkillComplete(
                    result="pass",
                    usage={"totals": {"total_tokens": 42}},
                )
                mock_agent_cls.return_value = mock_agent

                proj = Project(str(tmp_project))
                result = tool_approve_gate(proj, session_dir, {"approved": True})

            assert result["result"] == "pass"
            assert "usage" in result

    def test_approve_gate_not_found(self, tmp_project):
        """tool_approve_gate: nonexistent session returns error."""
        initialize_project(tmp_project)
        with mock.patch("datamind.engine.project.OpenAIClient") as mock_client_cls:
            mock_instance = mock.MagicMock()
            mock_instance.model = "gpt-4o"
            mock_instance.list_models.return_value = ["gpt-4o"]
            mock_client_cls.return_value = mock_instance

            proj = Project(str(tmp_project))
            result = tool_approve_gate(proj, "/nonexistent/path", {"approved": True})

        assert "error" in result
