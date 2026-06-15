"""E2E test: full skill execution through all phases.

Tests the complete DataMind Agent loop from skill loading through to
SkillComplete, verifying GATE pause/resume, .skill.yaml persistence,
and usage tracking at each stage.
"""

from pathlib import Path

import yaml

from datamind.engine.agent import (
    AgentResponse,
    DataMindAgent,
    SkillComplete,
    WaitForApproval,
)
from datamind.engine.llm import LLMResponse
from datamind.engine.prompt import TemplateManager
from datamind.engine.skill_state import PhaseStatus, SkillPhase
from datamind.engine.skills import SkillParser, SkillService, SkillSession
from datamind.engine.usage import UsageTracker

# ---------------------------------------------------------------------------
# Reuse MockLLMClient pattern from integration tests
# ---------------------------------------------------------------------------


class MockLLMClient:
    """Returns pre-configured LLMResponse objects in sequence.

    After exhausting *responses*, returns a default simple text response.
    """

    def __init__(self, responses=None, model="mock-model"):
        self.responses = list(responses) if responses else []
        self.model = model
        self.call_count = 0
        self.calls = []

    def chat(self, messages, tools=None, stream=False, **kwargs):
        self.calls.append({"messages": list(messages), "tools": tools})
        if self.call_count < len(self.responses):
            response = self.responses[self.call_count]
            self.call_count += 1
            return response
        return LLMResponse(
            content="Default mock response",
            model=self.model,
            usage={"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        )

    def list_models(self):
        return [self.model]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_mock_services():
    """Return mock services for SkillService construction."""
    class MockLineage:
        pass
    class MockCognition:
        pass
    class MockAssembly:
        pass
    return MockLineage(), MockCognition(), MockAssembly()


# ---------------------------------------------------------------------------
# T8.1: Full skill execution through all phases
# ---------------------------------------------------------------------------


class TestFullSkillExecution:
    """E2E: full data-cleaning skill execution through all 7 phases.

    Phases: Analyze (AUTO) -> Propose Strategy (AUTO) -> Gate: Approve Strategy (GATE)
         -> Execute (AUTO) -> Validate (AUTO) -> Gate: Review Results (GATE)
         -> Archive (AUTO)
    """

    DATA_CLEANING_SKILL = """# Data Cleaning

**Purpose:** Clean raw data files by detecting and fixing common issues.

**Inputs:** A dataset path from data/raw/

## Workflow

1. **Analyze** (AUTO) -- Read the describe/ output for the dataset, identify issues
2. **Propose Strategy** (AUTO) -- Generate a cleaning strategy with rationale
3. **Gate: Approve Strategy** (GATE) -- Present the strategy for human approval
4. **Execute** (AUTO) -- Generate and run a cleaning script
5. **Validate** (AUTO) -- Compare before/after statistics, verify integrity
6. **Gate: Review Results** (GATE) -- Show validation results for final sign-off
7. **Archive** (AUTO) -- Archive session artifacts for traceability

## Outputs

- Cleaned dataset in data/processed/
- Cleaning script in scripts/
"""

    def _create_skill_service(self, skills_dir: Path):
        """Write the data-cleaning.md skill and return a SkillService."""
        skills_dir.mkdir(parents=True, exist_ok=True)
        (skills_dir / "data-cleaning.md").write_text(self.DATA_CLEANING_SKILL, encoding="utf-8")
        return SkillService(str(skills_dir), *_make_mock_services())

    def _find_skill_yaml_path(self, session_base: Path) -> Path | None:
        """Find the .skill.yaml file inside the session directory."""
        yaml_files = list(session_base.rglob(".skill.yaml"))
        return yaml_files[0] if yaml_files else None

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_full_data_cleaning_workflow(self, tmp_project):
        """Run the full data-cleaning skill through all 7 phases.

        1. Load the skill via SkillService
        2. Create a SkillSession
        3. Run through all AUTO phases, pausing at GATEs
        4. Verify .skill.yaml persistence and usage tracking
        """
        tmp = Path(tmp_project)
        skills_dir = tmp / "skills"
        sessions_base = tmp / "sessions"

        # 1. Set up SkillService and load skill
        skill_svc = self._create_skill_service(skills_dir)
        skill_def = skill_svc.load_skill("data-cleaning")

        assert skill_def.name == "Data Cleaning"
        assert len(skill_def.phases) == 7
        assert skill_def.phases[0].id == "analyze"
        assert skill_def.phases[2].id == "gate-approve-strategy"
        assert skill_def.phases[5].id == "gate-review-results"

        # 2. Create a SkillSession with all phases
        sm = SkillSession.create(
            "data-cleaning",
            str(tmp / "data" / "raw" / "sales.csv"),
            str(sessions_base),
            skill_def.phases,
        )

        assert sm.state.phase == "analyze"
        assert sm.state.phases["analyze"] == PhaseStatus.IN_PROGRESS.value

        # Verify initial .skill.yaml exists
        yaml_path = self._find_skill_yaml_path(sessions_base)
        assert yaml_path is not None
        initial_data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        assert initial_data["phase"] == "analyze"

        # 3. Create MockLLMClient with 5 responses (2 + 2 + 1 AUTO phases)
        mock_llm = MockLLMClient(responses=[
            # Phase 1: Analyze
            LLMResponse(
                content="Analysis complete: found 3 issues in the dataset.",
                model="mock",
                usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
            ),
            # Phase 2: Propose Strategy
            LLMResponse(
                content="Proposed cleaning strategy: fix outliers, fill nulls.",
                model="mock",
                usage={"prompt_tokens": 80, "completion_tokens": 25, "total_tokens": 105},
            ),
            # Phase 4: Execute
            LLMResponse(
                content="Executing cleaning script: removed 3 outliers.",
                model="mock",
                usage={"prompt_tokens": 90, "completion_tokens": 15, "total_tokens": 105},
            ),
            # Phase 5: Validate
            LLMResponse(
                content="Validation passed: data integrity confirmed.",
                model="mock",
                usage={"prompt_tokens": 70, "completion_tokens": 20, "total_tokens": 90},
            ),
            # Phase 7: Archive
            LLMResponse(
                content="Archived session artifacts.",
                model="mock",
                usage={"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60},
            ),
        ])

        tracker = UsageTracker()
        agent = DataMindAgent(
            llm_client=mock_llm,
            prompt_manager=TemplateManager(templates_dir=str(tmp / "prompts")),
            usage_tracker=tracker,
        )

        # 4. First run: should process Analyze + Propose Strategy, then hit Gate: Approve Strategy
        result1 = agent.run(sm)
        assert isinstance(result1, WaitForApproval), (
            f"Expected WaitForApproval, got {type(result1).__name__}"
        )
        assert result1.phase_id == "gate-approve-strategy"
        assert result1.phase_name == "Approve Strategy"
        assert sm.state.phases["analyze"] == PhaseStatus.COMPLETE.value
        assert sm.state.phases["propose-strategy"] == PhaseStatus.COMPLETE.value
        assert sm.state.phases["gate-approve-strategy"] == PhaseStatus.AWAITING_HUMAN.value

        # Verify .skill.yaml persisted after first run
        post_run1 = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        assert post_run1["phase"] == "gate-approve-strategy"
        assert post_run1["phases"]["analyze"] == "complete"
        assert post_run1["phases"]["propose-strategy"] == "complete"
        assert post_run1["phases"]["gate-approve-strategy"] == "awaiting_human"

        # 5. Approve first gate: should process Execute + Validate, then hit Gate: Review Results
        result2 = agent.approve_gate({"approved": True, "comment": "strategy looks good"})
        assert isinstance(result2, WaitForApproval), (
            f"Expected WaitForApproval, got {type(result2).__name__}"
        )
        assert result2.phase_id == "gate-review-results"
        assert result2.phase_name == "Review Results"
        assert sm.state.phases["execute"] == PhaseStatus.COMPLETE.value
        assert sm.state.phases["validate"] == PhaseStatus.COMPLETE.value
        assert sm.state.phases["gate-review-results"] == PhaseStatus.AWAITING_HUMAN.value

        # Verify decision artifact was recorded
        assert "gate-approve-strategy" in sm.state.artifacts

        # Verify .skill.yaml persisted after second run
        post_run2 = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        assert post_run2["phase"] == "gate-review-results"
        assert post_run2["phases"]["execute"] == "complete"
        assert post_run2["phases"]["validate"] == "complete"
        assert post_run2["phases"]["gate-review-results"] == "awaiting_human"

        # 6. Approve second gate: should process Archive, then complete workflow
        result3 = agent.approve_gate({"signed_off": True})
        assert isinstance(result3, SkillComplete), (
            f"Expected SkillComplete, got {type(result3).__name__}"
        )
        assert result3.result == "pass"
        assert sm.state.result == "pass"
        assert sm.state.completed_at is not None
        assert sm.state.phases["archive"] == PhaseStatus.COMPLETE.value

        # Verify .skill.yaml persisted final state
        post_run3 = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        assert post_run3["result"] == "pass"
        assert post_run3["completed_at"] is not None
        for pid in ["analyze", "propose-strategy", "gate-approve-strategy",
                      "execute", "validate", "gate-review-results", "archive"]:
            assert post_run3["phases"].get(pid) == "complete", f"Phase {pid} not complete"

        # 7. Verify usage was tracked (5 AUTO phases, each with tokens)
        assert mock_llm.call_count == 5
        assert tracker.prompt_tokens == 100 + 80 + 90 + 70 + 50
        assert tracker.completion_tokens == 20 + 25 + 15 + 20 + 10
        assert tracker.total_tokens == 120 + 105 + 105 + 90 + 60

        # Verify SkillComplete carries usage data
        exported = result3.usage
        assert exported["totals"]["prompt_tokens"] == 390
        assert exported["totals"]["completion_tokens"] == 90
        assert exported["totals"]["total_tokens"] == 480


class TestSkillExecutionWithUserInput:
    """E2E: skill execution with initial user input."""

    DATA_CLEANING_SKILL = TestFullSkillExecution.DATA_CLEANING_SKILL

    def test_agent_run_with_user_message(self, tmp_project):
        """run() with user_input passes the message to the first LLM call."""
        tmp = Path(tmp_project)
        skills_dir = tmp / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        (skills_dir / "data-cleaning.md").write_text(self.DATA_CLEANING_SKILL, encoding="utf-8")

        skill_svc = SkillService(str(skills_dir), *_make_mock_services())
        skill_def = skill_svc.load_skill("data-cleaning")

        sessions_base = tmp / "sessions"
        sm = SkillSession.create(
            "data-cleaning",
            str(tmp / "data" / "raw" / "sales.csv"),
            str(sessions_base),
            skill_def.phases,
        )

        mock_llm = MockLLMClient(responses=[
            LLMResponse(
                content="Analyzed: focusing on outlier detection.",
                model="mock",
                usage={"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60},
            ),
            LLMResponse(
                content="Strategy: use IQR method.",
                model="mock",
                usage={"prompt_tokens": 40, "completion_tokens": 12, "total_tokens": 52},
            ),
            LLMResponse(
                content="Executed cleaning.",
                model="mock",
                usage={"prompt_tokens": 30, "completion_tokens": 8, "total_tokens": 38},
            ),
            LLMResponse(
                content="Validated.",
                model="mock",
                usage={"prompt_tokens": 25, "completion_tokens": 5, "total_tokens": 30},
            ),
            LLMResponse(
                content="Archived.",
                model="mock",
                usage={"prompt_tokens": 20, "completion_tokens": 5, "total_tokens": 25},
            ),
        ])

        agent = DataMindAgent(
            llm_client=mock_llm,
            prompt_manager=TemplateManager(templates_dir=str(tmp / "prompts")),
            usage_tracker=UsageTracker(),
        )

        # run() with a user-provided message
        user_msg = "Please clean the sales.csv file and focus on price outliers."
        result1 = agent.run(sm, user_input=user_msg)

        # First AUTO phase should receive user_input in messages
        assert isinstance(result1, WaitForApproval)
        assert mock_llm.call_count >= 1

        # The first call should include the user message
        first_call_messages = mock_llm.calls[0]["messages"]
        user_messages = [m for m in first_call_messages if m["role"] == "user"]
        assert len(user_messages) == 1
        assert user_msg in user_messages[0]["content"]

        # Second AUTO phase (Propose Strategy) should NOT have user_input
        # (user_input only applies to the first phase)
        second_call_messages = mock_llm.calls[1]["messages"]
        user_messages_2 = [m for m in second_call_messages if m["role"] == "user"]
        assert len(user_messages_2) == 0


class TestSkillExecutionPhases:
    """Verify each phase transition emits the correct event."""

    DATA_CLEANING_SKILL = TestFullSkillExecution.DATA_CLEANING_SKILL

    def test_all_phases_reach_complete_status(self, tmp_project):
        """After full workflow traversal, all 7 phases should be in 'complete' status."""
        tmp = Path(tmp_project)
        skills_dir = tmp / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        (skills_dir / "data-cleaning.md").write_text(self.DATA_CLEANING_SKILL, encoding="utf-8")

        skill_svc = SkillService(str(skills_dir), *_make_mock_services())
        skill_def = skill_svc.load_skill("data-cleaning")

        sessions_base = tmp / "sessions"
        sm = SkillSession.create(
            "data-cleaning",
            str(tmp / "data" / "raw" / "sales.csv"),
            str(sessions_base),
            skill_def.phases,
        )

        mock_llm = MockLLMClient(responses=[
            LLMResponse(content="Phase 1 done.", model="mock",
                        usage={"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13}),
            LLMResponse(content="Phase 2 done.", model="mock",
                        usage={"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13}),
            LLMResponse(content="Phase 4 done.", model="mock",
                        usage={"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13}),
            LLMResponse(content="Phase 5 done.", model="mock",
                        usage={"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13}),
            LLMResponse(content="Phase 7 done.", model="mock",
                        usage={"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13}),
        ])

        agent = DataMindAgent(
            llm_client=mock_llm,
            prompt_manager=TemplateManager(templates_dir=str(tmp / "prompts")),
            usage_tracker=UsageTracker(),
        )

        # Run through all phases, tracking transitions
        # run() 1: Analyze + Propose Strategy → GATE
        r1 = agent.run(sm)
        assert isinstance(r1, WaitForApproval)
        assert sm.state.phases["analyze"] == "complete"
        assert sm.state.phases["propose-strategy"] == "complete"

        # approve_gate 1: Execute + Validate → GATE
        r2 = agent.approve_gate({"ok": True})
        assert isinstance(r2, WaitForApproval)
        assert sm.state.phases["execute"] == "complete"
        assert sm.state.phases["validate"] == "complete"

        # approve_gate 2: Archive → complete
        r3 = agent.approve_gate({"ok": True})
        assert isinstance(r3, SkillComplete)
        assert r3.result == "pass"

        # All 7 phases are complete
        for pid in ["analyze", "propose-strategy", "gate-approve-strategy",
                      "execute", "validate", "gate-review-results", "archive"]:
            assert sm.state.phases.get(pid) == "complete", f"Phase {pid}: {sm.state.phases.get(pid)}"
