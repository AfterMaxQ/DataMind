"""SkillStateMachine — phase-based skill execution with .skill.yaml persistence.

Provides:
- :class:`PhaseStatus` — lifecycle states for a phase
- :class:`SkillPhase` — definition of a single phase
- :class:`SkillSessionState` — runtime state of a skill session
- :class:`SkillStateMachine` — validates transitions, persists to .skill.yaml
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class PhaseStatus(Enum):
    """Lifecycle status of a skill phase."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_HUMAN = "awaiting_human"
    COMPLETE = "complete"


@dataclass
class SkillPhase:
    """Definition of a single phase in a skill workflow.

    Attributes:
        id: Machine-readable kebab-case identifier (e.g. ``"propose-strategy"``).
        name: Human-readable name (e.g. ``"Propose Strategy"``).
        type: ``"AUTO"`` for automatic phases or ``"GATE"`` for human gates.
        description: One-line description of the phase.
    """

    id: str
    name: str
    type: str  # "AUTO" | "GATE"
    description: str = ""


@dataclass
class SkillSessionState:
    """Runtime state of a skill execution session.

    Persisted to ``.skill.yaml`` alongside session artifacts.
    """

    skill: str
    target: str
    session: str
    started_at: str
    completed_at: str | None = None
    phase: str = ""
    phases: dict[str, str] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    result: str | None = None
    usage: dict = field(default_factory=dict)


class SkillStateMachine:
    """Validates phase transitions and persists execution state.

    Combines a :class:`SkillSessionState` with a list of :class:`SkillPhase`
    definitions to enforce correct workflow progression.
    """

    def __init__(self, state: SkillSessionState, phase_definitions: list[SkillPhase]) -> None:
        self.state = state
        self._phase_defs = list(phase_definitions)
        self._phase_map: dict[str, SkillPhase] = {p.id: p for p in self._phase_defs}
        self._phase_order: list[str] = [p.id for p in self._phase_defs]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_current_phase(self) -> SkillPhase:
        """Return the :class:`SkillPhase` definition for the current phase."""
        return self._phase_map[self.state.phase]

    def complete_phase(self, phase_id: str, artifact_path: str | None = None) -> str:
        """Mark an AUTO phase as COMPLETE, record its artifact, and advance.

        Args:
            phase_id: The phase to complete (must be the current phase).
            artifact_path: Optional file path to the phase's output artifact.

        Returns:
            The id of the next phase, or ``""`` if the workflow is finished.

        Raises:
            ValueError: If *phase_id* is not the current phase, is unknown,
                or is a GATE phase (use :meth:`approve_gate` instead).
        """
        if phase_id not in self._phase_map:
            raise ValueError(f"Unknown phase: '{phase_id}'")
        if phase_id != self.state.phase:
            raise ValueError(
                f"Cannot complete phase '{phase_id}': current phase is '{self.state.phase}'"
            )
        if self._phase_map[phase_id].type == "GATE":
            raise ValueError(
                f"Phase '{phase_id}' is a GATE phase; use approve_gate() instead"
            )

        self.state.phases[phase_id] = PhaseStatus.COMPLETE.value
        if artifact_path is not None:
            self.state.artifacts[phase_id] = artifact_path

        return self._advance(phase_id)

    def approve_gate(self, phase_id: str, decision: dict | None = None) -> str:
        """Mark a GATE phase as COMPLETE, record the decision, and advance.

        Args:
            phase_id: The gate phase to approve (must be the current phase).
            decision: Optional dict capturing the human decision (serialized
                as JSON in the artifacts record).

        Returns:
            The id of the next phase, or ``""`` if the workflow is finished.

        Raises:
            ValueError: If *phase_id* is not the current phase, is unknown,
                or is not a GATE phase.
        """
        if phase_id not in self._phase_map:
            raise ValueError(f"Unknown phase: '{phase_id}'")
        if phase_id != self.state.phase:
            raise ValueError(
                f"Cannot approve gate '{phase_id}': current phase is '{self.state.phase}'"
            )
        if self._phase_map[phase_id].type != "GATE":
            raise ValueError(
                f"Phase '{phase_id}' is not a GATE phase; use complete_phase() instead"
            )

        self.state.phases[phase_id] = PhaseStatus.COMPLETE.value
        if decision is not None:
            self.state.artifacts[phase_id] = json.dumps(decision)

        return self._advance(phase_id)

    def get_active_artifacts(self) -> list[str]:
        """Return artifact paths for all COMPLETE phases."""
        return [
            path
            for pid, path in self.state.artifacts.items()
            if self.state.phases.get(pid) == PhaseStatus.COMPLETE.value
        ]

    def save(self, path: str) -> None:
        """Persist the current state to a ``.skill.yaml`` file."""
        import yaml

        data = {
            "skill": self.state.skill,
            "target": self.state.target,
            "session": self.state.session,
            "started_at": self.state.started_at,
            "completed_at": self.state.completed_at,
            "phase": self.state.phase,
            "phase_definitions": [
                {"id": p.id, "name": p.name, "type": p.type, "description": p.description}
                for p in self._phase_defs
            ],
            "phases": self.state.phases,
            "artifacts": self.state.artifacts,
            "result": self.state.result or "pending",
            "usage": self.state.usage,
        }
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

    @staticmethod
    def load(path: str) -> "SkillStateMachine":
        """Restore a :class:`SkillStateMachine` from a ``.skill.yaml`` file.

        Raises:
            FileNotFoundError: If *path* does not exist.
        """
        import yaml

        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Skill state file not found: {path}")

        data = yaml.safe_load(p.read_text(encoding="utf-8"))

        phase_defs = [
            SkillPhase(
                id=pd["id"],
                name=pd["name"],
                type=pd["type"],
                description=pd.get("description", ""),
            )
            for pd in data.get("phase_definitions", [])
        ]

        state = SkillSessionState(
            skill=data["skill"],
            target=data["target"],
            session=data["session"],
            started_at=data["started_at"],
            completed_at=data.get("completed_at"),
            phase=data["phase"],
            phases=data.get("phases", {}),
            artifacts=data.get("artifacts", {}),
            result=data.get("result") if data.get("result") != "pending" else None,
            usage=data.get("usage", {}),
        )

        return SkillStateMachine(state, phase_defs)

    @staticmethod
    def create_session(
        skill_name: str,
        target: str,
        phases: list[SkillPhase],
        session_dir: str,
    ) -> "SkillStateMachine":
        """Factory: create a new skill session directory and initial state.

        Creates a timestamped subdirectory inside *session_dir*, writes the
        initial ``.skill.yaml``, and returns a ready-to-use state machine.
        """
        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%Y-%m-%dT%H%M%SZ")
        skill_slug = skill_name.lower().replace(" ", "-")
        target_slug = Path(target).stem
        session_id = f"{timestamp}-{skill_slug}-{target_slug}"

        first_phase = phases[0]
        phases_dict: dict[str, str] = {p.id: PhaseStatus.PENDING.value for p in phases}
        phases_dict[first_phase.id] = PhaseStatus.IN_PROGRESS.value

        state = SkillSessionState(
            skill=skill_name,
            target=target,
            session=session_id,
            started_at=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            completed_at=None,
            phase=first_phase.id,
            phases=phases_dict,
            artifacts={},
            result=None,
            usage={},
        )

        sm = SkillStateMachine(state, phases)

        # Create session directory and persist initial state
        full_session_dir = Path(session_dir) / session_id
        full_session_dir.mkdir(parents=True, exist_ok=True)
        sm.save(str(full_session_dir / ".skill.yaml"))

        return sm

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _advance(self, current_phase_id: str) -> str:
        """Move to the next phase and set its initial status.

        Returns the next phase id, or ``""`` when the workflow is complete.
        """
        idx = self._phase_order.index(current_phase_id)
        if idx + 1 < len(self._phase_order):
            next_id = self._phase_order[idx + 1]
            next_phase = self._phase_map[next_id]
            self.state.phase = next_id
            if next_phase.type == "GATE":
                self.state.phases[next_id] = PhaseStatus.AWAITING_HUMAN.value
            else:
                self.state.phases[next_id] = PhaseStatus.IN_PROGRESS.value
            return next_id
        else:
            self.state.completed_at = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            return ""
