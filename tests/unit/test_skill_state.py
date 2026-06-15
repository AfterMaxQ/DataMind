"""Tests for SkillStateMachine and related data structures."""
import json
from pathlib import Path

import pytest
import yaml

from datamind.engine.skill_state import (
    PhaseStatus,
    SkillPhase,
    SkillSessionState,
    SkillStateMachine,
)

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

TEST_PHASES = [
    SkillPhase(id="analyze", name="Analyze", type="AUTO", description="Analyze data"),
    SkillPhase(id="gate-approve", name="Gate: Approve", type="GATE", description="Human approval"),
    SkillPhase(id="execute", name="Execute", type="AUTO", description="Execute plan"),
    SkillPhase(id="gate-result", name="Gate: Result", type="GATE", description="Final sign-off"),
]


def _make_state(phases=None, **overrides):
    """Build a SkillSessionState with sensible defaults for testing."""
    p = phases or TEST_PHASES
    first = p[0]
    phases_dict = {ph.id: PhaseStatus.PENDING.value for ph in p}
    phases_dict[first.id] = PhaseStatus.IN_PROGRESS.value

    defaults = dict(
        skill="test-skill",
        target="test-data.csv",
        session="2026-06-15T143000Z-test",
        started_at="2026-06-15T14:30:00Z",
        completed_at=None,
        phase=first.id,
        phases=phases_dict,
        artifacts={},
        result=None,
        usage={},
    )
    defaults.update(overrides)
    return SkillSessionState(**defaults)


def _make_sm(phases=None, **overrides):
    """Build a SkillStateMachine with test data."""
    p = phases or TEST_PHASES
    state = _make_state(phases=p, **overrides)
    return SkillStateMachine(state, p)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSkillStateMachineInit:
    def test_initialization_sets_first_phase_in_progress(self):
        """First phase should be IN_PROGRESS after session creation."""
        sm = _make_sm()
        current = sm.get_current_phase()
        assert current.id == "analyze"
        assert current.type == "AUTO"
        assert sm.state.phases["analyze"] == PhaseStatus.IN_PROGRESS.value


class TestCompletePhase:
    def test_complete_phase_advances(self):
        """Completing an AUTO phase advances to the next phase."""
        sm = _make_sm()
        next_id = sm.complete_phase("analyze", artifact_path="phase-1-analyze.md")
        assert next_id == "gate-approve"
        assert sm.state.phases["analyze"] == PhaseStatus.COMPLETE.value
        assert sm.state.artifacts["analyze"] == "phase-1-analyze.md"
        assert sm.state.phase == "gate-approve"
        assert sm.state.phases["gate-approve"] == PhaseStatus.AWAITING_HUMAN.value

    def test_gate_requires_approve(self):
        """complete_phase on a GATE phase raises ValueError."""
        sm = _make_sm()
        sm.complete_phase("analyze")  # advance to gate-approve
        with pytest.raises(ValueError, match="GATE"):
            sm.complete_phase("gate-approve")

    def test_invalid_transition_skipping_gate_rejected(self):
        """complete_phase on a non-current phase raises ValueError."""
        sm = _make_sm()
        with pytest.raises(ValueError, match="current phase"):
            sm.complete_phase("execute")

    def test_unknown_phase_rejected(self):
        """complete_phase on an unknown phase id raises ValueError."""
        sm = _make_sm()
        with pytest.raises(ValueError, match="Unknown"):
            sm.complete_phase("nonexistent")


class TestApproveGate:
    def test_approve_gate_advances(self):
        """approve_gate marks GATE COMPLETE and advances."""
        sm = _make_sm()
        sm.complete_phase("analyze")  # now at gate-approve
        assert sm.state.phase == "gate-approve"

        decision = {"approved": True, "notes": "looks good"}
        next_id = sm.approve_gate("gate-approve", decision=decision)
        assert next_id == "execute"
        assert sm.state.phases["gate-approve"] == PhaseStatus.COMPLETE.value
        assert sm.state.phase == "execute"
        assert sm.state.phases["execute"] == PhaseStatus.IN_PROGRESS.value
        # decision recorded as artifact
        assert "gate-approve" in sm.state.artifacts
        artifact_data = sm.state.artifacts["gate-approve"]
        assert json.loads(artifact_data) == decision

    def test_approve_gate_on_auto_phase_rejected(self):
        """approve_gate on an AUTO phase raises ValueError."""
        sm = _make_sm()
        with pytest.raises(ValueError, match="not a GATE"):
            sm.approve_gate("analyze")


class TestSaveAndLoad:
    def test_save_creates_yaml_file(self, tmp_project):
        """save() writes a valid .skill.yaml file."""
        sm = _make_sm()
        sm.complete_phase("analyze", artifact_path="phase-1-analyze.md")
        sm.approve_gate("gate-approve", decision={"approved": True})

        yaml_path = tmp_project / ".skill.yaml"
        sm.save(str(yaml_path))

        assert yaml_path.exists()
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        assert data["skill"] == "test-skill"
        assert data["target"] == "test-data.csv"
        assert data["phase"] == "execute"
        assert data["phases"]["analyze"] == "complete"
        assert data["phases"]["gate-approve"] == "complete"
        assert data["phases"]["execute"] == "in_progress"
        assert data["artifacts"]["analyze"] == "phase-1-analyze.md"
        assert len(data["phase_definitions"]) == 4

    def test_load_restores_state(self, tmp_project):
        """load() restores a previously saved state machine."""
        sm = _make_sm()
        sm.complete_phase("analyze", artifact_path="phase-1-analyze.md")
        sm.approve_gate("gate-approve", decision={"approved": True})

        yaml_path = tmp_project / ".skill.yaml"
        sm.save(str(yaml_path))

        restored = SkillStateMachine.load(str(yaml_path))
        assert restored.state.skill == "test-skill"
        assert restored.state.phase == "execute"
        assert restored.state.phases["analyze"] == PhaseStatus.COMPLETE.value
        assert restored.state.phases["gate-approve"] == PhaseStatus.COMPLETE.value
        assert restored.state.phases["execute"] == PhaseStatus.IN_PROGRESS.value
        assert restored.state.artifacts["analyze"] == "phase-1-analyze.md"
        assert restored.get_current_phase().id == "execute"

    def test_load_creates_fresh_if_missing(self, tmp_project):
        """load() raises FileNotFoundError when path does not exist."""
        missing = tmp_project / "nonexistent" / ".skill.yaml"
        missing.parent.mkdir(parents=True, exist_ok=True)
        with pytest.raises(FileNotFoundError):
            SkillStateMachine.load(str(missing))


class TestFullWorkflow:
    def test_full_workflow_completes_with_pass(self, tmp_project):
        """End-to-end: complete all phases and verify final state."""
        sm = _make_sm()

        # Phase 1: AUTO
        assert sm.get_current_phase().id == "analyze"
        next_id = sm.complete_phase("analyze", artifact_path="phase-1-analyze.md")
        assert next_id == "gate-approve"

        # Phase 2: GATE
        assert sm.state.phases["gate-approve"] == PhaseStatus.AWAITING_HUMAN.value
        next_id = sm.approve_gate("gate-approve", decision={"approved": True})
        assert next_id == "execute"

        # Phase 3: AUTO
        next_id = sm.complete_phase("execute", artifact_path="phase-3-execute.md")
        assert next_id == "gate-result"

        # Phase 4: GATE (final)
        assert sm.state.phases["gate-result"] == PhaseStatus.AWAITING_HUMAN.value
        next_id = sm.approve_gate("gate-result", decision={"signed_off": True})
        assert next_id == ""  # workflow complete

        assert sm.state.completed_at is not None
        assert sm.state.result == "pass"
        for ph in ["analyze", "gate-approve", "execute", "gate-result"]:
            assert sm.state.phases[ph] == PhaseStatus.COMPLETE.value


class TestSessionState:
    def test_session_contains_expected_fields(self):
        """SkillSessionState has all required fields."""
        state = _make_state(phases=TEST_PHASES)
        assert state.skill == "test-skill"
        assert state.target == "test-data.csv"
        assert state.session == "2026-06-15T143000Z-test"
        assert state.started_at == "2026-06-15T14:30:00Z"
        assert state.completed_at is None
        assert state.phase == "analyze"
        assert isinstance(state.phases, dict)
        assert isinstance(state.artifacts, dict)
        assert state.result is None
        assert isinstance(state.usage, dict)


class TestActiveArtifacts:
    def test_active_artifacts_lists_completed(self):
        """get_active_artifacts() returns paths only for COMPLETE phases."""
        sm = _make_sm()
        sm.complete_phase("analyze", artifact_path="a.md")
        sm.approve_gate("gate-approve", decision={"ok": True})
        sm.complete_phase("execute", artifact_path="e.md")

        artifacts = sm.get_active_artifacts()
        assert "a.md" in artifacts
        assert "e.md" in artifacts
        # gate-result is not yet complete, should not appear
        for path in artifacts:
            assert "gate-result" not in path


class TestCreateSession:
    def test_create_session_sets_up_correctly(self, tmp_project):
        """create_session() factory creates dir, saves .skill.yaml, initialises state."""
        session_dir = str(tmp_project / "sessions")
        sm = SkillStateMachine.create_session(
            "data-cleaning", "sales.csv", TEST_PHASES, session_dir
        )

        assert sm.state.skill == "data-cleaning"
        assert sm.state.target == "sales.csv"
        assert sm.state.phase == "analyze"
        assert sm.state.phases["analyze"] == PhaseStatus.IN_PROGRESS.value

        # Session directory created
        session_path = Path(session_dir)
        dirs = list(session_path.iterdir())
        assert len(dirs) >= 1

        # .skill.yaml exists
        yaml_path = None
        for d in dirs:
            if d.name.endswith(".skill.yaml") or d.is_dir():
                # The session dir is inside session_dir
                if d.is_dir():
                    yaml_path = d / ".skill.yaml"
        # Find the yaml file by walking
        yaml_files = list(session_path.rglob(".skill.yaml"))
        assert len(yaml_files) == 1
        assert yaml_files[0].exists()
