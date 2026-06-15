"""E2E test: interrupt/resume recovery.

Tests that a skill session can be interrupted mid-workflow and successfully
resumed—even with a brand-new agent and state machine loaded from disk.
"""

from pathlib import Path

import yaml

from datamind.engine.agent import (
    DataMindAgent,
    SkillComplete,
    WaitForApproval,
)
from datamind.engine.llm import LLMResponse
from datamind.engine.prompt import TemplateManager
from datamind.engine.skill_state import PhaseStatus, SkillStateMachine
from datamind.engine.skills import SkillService, SkillSession
from datamind.engine.usage import UsageTracker

# ---------------------------------------------------------------------------
# Reuse MockLLMClient
# ---------------------------------------------------------------------------


class MockLLMClient:
    """Returns pre-configured LLMResponse objects in sequence."""

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
# Helpers
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


DATA_CLEANING_SKILL = """# Data Cleaning

**Purpose:** Clean raw data files.

**Inputs:** A dataset path.

## Workflow

1. **Analyze** (AUTO) -- Analyze data quality issues
2. **Propose Strategy** (AUTO) -- Generate cleaning strategy
3. **Gate: Approve Strategy** (GATE) -- Human approval
4. **Execute** (AUTO) -- Run cleaning script
5. **Validate** (AUTO) -- Validate results
6. **Gate: Review Results** (GATE) -- Final sign-off
7. **Archive** (AUTO) -- Archive artifacts

## Outputs

- Cleaned dataset
"""


# ---------------------------------------------------------------------------
# T8.2: Interrupt / Resume recovery
# ---------------------------------------------------------------------------


class TestInterruptResumeRecovery:
    """E2E: interrupt mid-workflow and resume via .skill.yaml reload."""

    def test_interrupt_after_two_auto_phases_and_resume(self, tmp_project):
        """Interrupt after 2 AUTO phases, reload state, new agent resumes and completes.

        1. Create skill session and run 2 AUTO phases (Analyze + Propose Strategy)
        2. Read .skill.yaml to capture current state
        3. Simulate "context loss": create a brand-new SkillStateMachine from .skill.yaml
        4. Create a new DataMindAgent
        5. Resume execution from the current phase
        6. Complete the workflow via approve_gate calls
        """
        tmp = Path(tmp_project)
        skills_dir = tmp / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        (skills_dir / "data-cleaning.md").write_text(DATA_CLEANING_SKILL, encoding="utf-8")

        skill_svc = SkillService(str(skills_dir), *_make_mock_services())
        skill_def = skill_svc.load_skill("data-cleaning")

        sessions_base = tmp / "sessions"

        # ---- Step 1: Create session and run first 2 AUTO phases ----
        sm1 = SkillSession.create(
            "data-cleaning",
            str(tmp / "data" / "raw" / "sales.csv"),
            str(sessions_base),
            skill_def.phases,
        )

        # Find the session directory
        session_dirs = list(sessions_base.iterdir())
        assert len(session_dirs) == 1
        session_dir = session_dirs[0]
        yaml_path = session_dir / ".skill.yaml"

        # Agent for initial run
        mock_llm1 = MockLLMClient(responses=[
            LLMResponse(content="Analyzed data.", model="mock",
                        usage={"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60}),
            LLMResponse(content="Proposed strategy.", model="mock",
                        usage={"prompt_tokens": 40, "completion_tokens": 12, "total_tokens": 52}),
        ])

        agent1 = DataMindAgent(
            llm_client=mock_llm1,
            prompt_manager=TemplateManager(templates_dir=str(tmp / "prompts")),
            usage_tracker=UsageTracker(),
        )

        # Run: processes Analyze + Propose Strategy, pauses at Gate: Approve Strategy
        result1 = agent1.run(sm1)
        assert isinstance(result1, WaitForApproval)
        assert result1.phase_id == "gate-approve-strategy"
        assert sm1.state.phases["analyze"] == PhaseStatus.COMPLETE.value
        assert sm1.state.phases["propose-strategy"] == PhaseStatus.COMPLETE.value
        assert sm1.state.phases["gate-approve-strategy"] == PhaseStatus.AWAITING_HUMAN.value

        # ---- Step 2: Read .skill.yaml to capture state ----
        assert yaml_path.exists()
        captured_data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        assert captured_data["phase"] == "gate-approve-strategy"
        assert captured_data["phases"]["analyze"] == "complete"
        assert captured_data["phases"]["propose-strategy"] == "complete"
        assert captured_data["skill"] == "data-cleaning"

        # ---- Step 3: Simulate "context loss" — load fresh state machine ----
        sm2 = SkillStateMachine.load(str(yaml_path))

        # Verify restored state matches
        assert sm2.state.skill == captured_data["skill"]
        assert sm2.state.target == captured_data["target"]
        assert sm2.state.phase == "gate-approve-strategy"
        assert sm2.state.phases["analyze"] == PhaseStatus.COMPLETE.value
        assert sm2.state.phases["propose-strategy"] == PhaseStatus.COMPLETE.value
        assert sm2.state.phases["gate-approve-strategy"] == PhaseStatus.AWAITING_HUMAN.value

        # ---- Step 4: Create a new agent (simulating fresh session) ----
        mock_llm2 = MockLLMClient(responses=[
            LLMResponse(content="Executed cleaning.", model="mock",
                        usage={"prompt_tokens": 30, "completion_tokens": 8, "total_tokens": 38}),
            LLMResponse(content="Validated results.", model="mock",
                        usage={"prompt_tokens": 25, "completion_tokens": 5, "total_tokens": 30}),
            LLMResponse(content="Archived.", model="mock",
                        usage={"prompt_tokens": 20, "completion_tokens": 5, "total_tokens": 25}),
        ])

        tracker2 = UsageTracker()
        agent2 = DataMindAgent(
            llm_client=mock_llm2,
            prompt_manager=TemplateManager(templates_dir=str(tmp / "prompts")),
            usage_tracker=tracker2,
        )

        # ---- Step 5: Resume: set state machine and approve the current gate ----
        # run() must be called first to bind the state machine to the new agent.
        # Since we're at a GATE, run() returns WaitForApproval immediately (no LLM).
        resume_check = agent2.run(sm2)
        assert isinstance(resume_check, WaitForApproval)
        assert resume_check.phase_id == "gate-approve-strategy"

        # Now approve the gate (Gate: Approve Strategy) → Execute + Validate
        result2 = agent2.approve_gate({"approved": True, "resumed": True})

        # Should process Execute + Validate, then hit Gate: Review Results
        assert isinstance(result2, WaitForApproval), (
            f"Expected WaitForApproval, got {type(result2).__name__}"
        )
        assert result2.phase_id == "gate-review-results"
        assert sm2.state.phases["execute"] == PhaseStatus.COMPLETE.value
        assert sm2.state.phases["validate"] == PhaseStatus.COMPLETE.value
        assert sm2.state.phases["gate-review-results"] == PhaseStatus.AWAITING_HUMAN.value

        # Approve final gate — should process Archive and complete
        result3 = agent2.approve_gate({"signed_off": True})
        assert isinstance(result3, SkillComplete), (
            f"Expected SkillComplete, got {type(result3).__name__}"
        )
        assert result3.result == "pass"

        # ---- Step 6: Verify final result ----
        assert sm2.state.result == "pass"
        assert sm2.state.completed_at is not None
        assert mock_llm2.call_count == 3

        # All phases complete in the state machine
        for pid in ["analyze", "propose-strategy", "gate-approve-strategy",
                      "execute", "validate", "gate-review-results", "archive"]:
            assert sm2.state.phases.get(pid) == PhaseStatus.COMPLETE.value, (
                f"Phase {pid}: {sm2.state.phases.get(pid)}"
            )

        # Verify .skill.yaml persisted through the resumed execution
        final_data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        assert final_data["result"] == "pass"
        assert final_data["completed_at"] is not None
        assert final_data["phases"]["archive"] == "complete"


class TestInterruptBeforeGateAndResume:
    """E2E: interrupt right before a GATE, reload, approve gate, and continue."""

    def test_reload_before_gate_then_approve(self, tmp_project):
        """After reload, approve_gate works correctly on restored state machine."""
        tmp = Path(tmp_project)
        skills_dir = tmp / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        (skills_dir / "data-cleaning.md").write_text(DATA_CLEANING_SKILL, encoding="utf-8")

        skill_svc = SkillService(str(skills_dir), *_make_mock_services())
        skill_def = skill_svc.load_skill("data-cleaning")

        sessions_base = tmp / "sessions"
        sm = SkillSession.create(
            "data-cleaning",
            str(tmp / "data" / "raw" / "sales.csv"),
            str(sessions_base),
            skill_def.phases,
        )

        # Run 2 AUTO phases, pause at Gate
        mock_llm1 = MockLLMClient(responses=[
            LLMResponse(content="Analysis done.", model="mock",
                        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
            LLMResponse(content="Strategy proposed.", model="mock",
                        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
        ])
        agent1 = DataMindAgent(
            llm_client=mock_llm1,
            prompt_manager=TemplateManager(templates_dir=str(tmp / "prompts")),
            usage_tracker=UsageTracker(),
        )
        agent1.run(sm)

        session_dirs = list(sessions_base.iterdir())
        yaml_path = session_dirs[0] / ".skill.yaml"

        # ---- Simulate context loss: reload ----
        restored = SkillStateMachine.load(str(yaml_path))
        assert restored.state.phase == "gate-approve-strategy"

        # New agent
        mock_llm2 = MockLLMClient(responses=[
            LLMResponse(content="Executed.", model="mock",
                        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
            LLMResponse(content="Validated.", model="mock",
                        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
            LLMResponse(content="Archived.", model="mock",
                        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
        ])

        agent2 = DataMindAgent(
            llm_client=mock_llm2,
            prompt_manager=TemplateManager(templates_dir=str(tmp / "prompts")),
            usage_tracker=UsageTracker(),
        )

        # Bind the state machine to the new agent
        resume_check = agent2.run(restored)
        assert isinstance(resume_check, WaitForApproval)
        assert resume_check.phase_id == "gate-approve-strategy"

        # Approve the gate on the restored machine
        r1 = agent2.approve_gate({"approved": True})
        assert isinstance(r1, WaitForApproval)
        assert r1.phase_id == "gate-review-results"

        r2 = agent2.approve_gate({"ok": True})
        assert isinstance(r2, SkillComplete)
        assert r2.result == "pass"

        assert restored.state.result == "pass"


class TestInterruptMidAutoAndResume:
    """E2E: interrupt mid-workflow (at a GATE), reload, and complete."""

    def test_resume_from_yaml_preserves_artifacts(self, tmp_project):
        """After reload, previously recorded artifacts are still accessible."""
        tmp = Path(tmp_project)
        skills_dir = tmp / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        (skills_dir / "data-cleaning.md").write_text(DATA_CLEANING_SKILL, encoding="utf-8")

        skill_svc = SkillService(str(skills_dir), *_make_mock_services())
        skill_def = skill_svc.load_skill("data-cleaning")

        sessions_base = tmp / "sessions"
        sm = SkillSession.create(
            "data-cleaning",
            str(tmp / "data" / "raw" / "sales.csv"),
            str(sessions_base),
            skill_def.phases,
        )

        # Run 2 AUTO phases
        mock_llm1 = MockLLMClient(responses=[
            LLMResponse(content="Found 3 issues.", model="mock",
                        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
            LLMResponse(content="Use IQR method.", model="mock",
                        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
        ])
        agent1 = DataMindAgent(
            llm_client=mock_llm1,
            prompt_manager=TemplateManager(templates_dir=str(tmp / "prompts")),
            usage_tracker=UsageTracker(),
        )
        agent1.run(sm)

        # Reload
        session_dirs = list(sessions_base.iterdir())
        yaml_path = session_dirs[0] / ".skill.yaml"
        restored = SkillStateMachine.load(str(yaml_path))

        # Verify loaded data
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        assert data["skill"] == "data-cleaning"
        assert data["target"].endswith("sales.csv")
        assert len(data["phase_definitions"]) == 7
        assert data["phases"]["analyze"] == "complete"
        assert data["phases"]["propose-strategy"] == "complete"
        assert data["phase"] == "gate-approve-strategy"

        # Verify the restored machine has working methods
        current = restored.get_current_phase()
        assert current.id == "gate-approve-strategy"
        assert current.type == "GATE"

        # Approve gate and continue with new agent
        mock_llm2 = MockLLMClient(responses=[
            LLMResponse(content="Executed.", model="mock",
                        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
            LLMResponse(content="Validated.", model="mock",
                        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
            LLMResponse(content="Archived.", model="mock",
                        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
        ])
        agent2 = DataMindAgent(
            llm_client=mock_llm2,
            prompt_manager=TemplateManager(templates_dir=str(tmp / "prompts")),
            usage_tracker=UsageTracker(),
        )

        # Bind state machine to new agent
        resume_check = agent2.run(restored)
        assert isinstance(resume_check, WaitForApproval)
        assert resume_check.phase_id == "gate-approve-strategy"

        r1 = agent2.approve_gate({"ok": True})
        assert isinstance(r1, WaitForApproval)

        r2 = agent2.approve_gate({"ok": True})
        assert isinstance(r2, SkillComplete)
        assert r2.result == "pass"


# ---------------------------------------------------------------------------
# T8.2b: Interrupt at GATE (not after AUTO) and resume directly
# ---------------------------------------------------------------------------


class TestInterruptAtGateAndResume:
    """E2E: interrupt while waiting at a GATE, reload, approve."""

    def test_interrupt_at_gate_reload_and_approve(self, tmp_project):
        """Session is interrupted while waiting at a GATE.

        Reload the state machine from .skill.yaml, create a new agent,
        and approve the gate to continue.
        """
        tmp = Path(tmp_project)
        skills_dir = tmp / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        (skills_dir / "data-cleaning.md").write_text(DATA_CLEANING_SKILL, encoding="utf-8")

        skill_svc = SkillService(str(skills_dir), *_make_mock_services())
        skill_def = skill_svc.load_skill("data-cleaning")

        sessions_base = tmp / "sessions"
        sm = SkillSession.create(
            "data-cleaning",
            str(tmp / "data" / "raw" / "sales.csv"),
            str(sessions_base),
            skill_def.phases,
        )

        # Run first 2 AUTO phases → pauses at Gate
        mock_llm1 = MockLLMClient(responses=[
            LLMResponse(content="Analysis done.", model="mock",
                        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
            LLMResponse(content="Strategy proposed.", model="mock",
                        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
        ])
        agent1 = DataMindAgent(
            llm_client=mock_llm1,
            prompt_manager=TemplateManager(templates_dir=str(tmp / "prompts")),
            usage_tracker=UsageTracker(),
        )
        result1 = agent1.run(sm)
        assert isinstance(result1, WaitForApproval)

        # ---- Interrupt: reload state from disk ----
        session_dirs = list(sessions_base.iterdir())
        yaml_path = session_dirs[0] / ".skill.yaml"

        restored_sm = SkillStateMachine.load(str(yaml_path))
        assert restored_sm.state.phase == "gate-approve-strategy"

        # New agent, new LLM client
        mock_llm2 = MockLLMClient(responses=[
            LLMResponse(content="Executed.", model="mock",
                        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
            LLMResponse(content="Validated.", model="mock",
                        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
            LLMResponse(content="Archived.", model="mock",
                        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
        ])
        agent2 = DataMindAgent(
            llm_client=mock_llm2,
            prompt_manager=TemplateManager(templates_dir=str(tmp / "prompts")),
            usage_tracker=UsageTracker(),
        )

        # Bind the state machine to the new agent first
        resume_check = agent2.run(restored_sm)
        assert isinstance(resume_check, WaitForApproval)
        assert resume_check.phase_id == "gate-approve-strategy"

        # Approve the gate on the restored machine
        r1 = agent2.approve_gate({"approved": True, "note": "resumed after interrupt"})
        assert isinstance(r1, WaitForApproval)
        assert r1.phase_id == "gate-review-results"

        r2 = agent2.approve_gate({"signed_off": True})
        assert isinstance(r2, SkillComplete)
        assert r2.result == "pass"

        # Verify restored state machine completed successfully
        assert restored_sm.state.result == "pass"
