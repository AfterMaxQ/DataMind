"""SkillService — SKILL.md parsing, AUTO/GATE execution, pipeline composition (Layer 4)."""

import re
from dataclasses import dataclass, field
from pathlib import Path

from datamind.engine.skill_state import SkillPhase, SkillStateMachine


@dataclass
class SkillStep:
    name: str
    step_type: str  # "AUTO" | "GATE"
    description: str = ""


@dataclass
class SkillDefinition:
    name: str = ""
    purpose: str = ""
    inputs: str = ""
    steps: list[SkillStep] = field(default_factory=list)
    phases: list[SkillPhase] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    frontmatter: dict = field(default_factory=dict)


class SkillParser:
    """Parse SKILL.md files into SkillDefinition objects.

    Extracts both legacy :class:`SkillStep` objects (backward compatible) and
    new :class:`SkillPhase` objects with kebab-case ids and type classification.
    """

    STEP_RE = re.compile(r"^\d+\.\s+\*\*(.+?)\*\*\s*\((\w+)\)\s*[-—]\s*(.+)$", re.MULTILINE)

    def parse(self, content: str) -> SkillDefinition:
        skill = SkillDefinition()

        # Parse YAML frontmatter if present
        frontmatter = {}
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    import yaml
                    frontmatter = yaml.safe_load(parts[1]) or {}
                except Exception:
                    frontmatter = {}
                content = parts[2]  # Use only the markdown portion

        skill.frontmatter = frontmatter

        name_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if name_match:
            skill.name = name_match.group(1).strip()

        purpose_match = re.search(r"\*\*Purpose:\*\*\s*(.+?)$", content, re.MULTILINE)
        if purpose_match:
            skill.purpose = purpose_match.group(1).strip()

        inputs_match = re.search(r"\*\*Inputs:\*\*\s*(.+?)$", content, re.MULTILINE)
        if inputs_match:
            skill.inputs = inputs_match.group(1).strip()

        # Parse steps (backward compatible) and phases (new)
        for match in self.STEP_RE.finditer(content):
            raw_name = match.group(1).strip()
            step_type_raw = match.group(2).strip().upper()
            description = match.group(3).strip()

            # Determine type and generate display name
            if step_type_raw == "GATE" or "GATE" in raw_name.upper():
                step_type = "GATE"
                display_name = re.sub(r"^Gate:\s*", "", raw_name)
            else:
                step_type = "AUTO"
                display_name = raw_name

            # Phase ID uses raw name (keeps "gate-" prefix for GATE phases)
            phase_id = self._to_phase_id(raw_name)

            skill.steps.append(SkillStep(name=display_name, step_type=step_type, description=description))
            skill.phases.append(
                SkillPhase(id=phase_id, name=display_name, type=step_type, description=description)
            )

        self._validate_phases(skill.phases, content)

        outputs_match = re.search(r"\*\*Outputs?\*\*\s*\n((?:\s*[-*]\s*.+\n?)*)", content, re.MULTILINE)
        if outputs_match:
            outputs_text = outputs_match.group(1)
            skill.outputs = [re.sub(r"^\s*[-*]\s*", "", line).strip() for line in outputs_text.strip().split("\n") if line.strip()]

        return skill

    # ------------------------------------------------------------------
    # Phase helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_phase_id(name: str) -> str:
        """Convert a human-readable phase name to a kebab-case id.

        ``"Propose Strategy"`` becomes ``"propose-strategy"``.
        ``"Gate: Approve"`` becomes ``"gate-approve"``.
        """
        clean = name.strip().lower()
        clean = re.sub(r"[^a-z0-9\s-]", "", clean)
        clean = re.sub(r"\s+", "-", clean)
        clean = re.sub(r"-{2,}", "-", clean)
        return clean.strip("-")

    @staticmethod
    def _validate_phases(phases: list[SkillPhase], content: str = "") -> None:
        """Validate the extracted phase list.

        Raises:
            ValueError: If there are duplicate ids, or if a Workflow section
                exists but contains no phases.
        """
        has_workflow = bool(re.search(r"^##\s+Workflow", content, re.MULTILINE | re.IGNORECASE))

        if has_workflow and not phases:
            raise ValueError("Skill must have at least one phase")

        if phases and phases[-1].type == "GATE":
            raise ValueError("Final phase must not be a GATE")

        seen: set[str] = set()
        for p in phases:
            if p.id in seen:
                raise ValueError(f"Duplicate phase id: '{p.id}'")
            seen.add(p.id)

    def parse_file(self, file_path: str) -> SkillDefinition:
        content = Path(file_path).read_text(encoding="utf-8")
        return self.parse(content)


class SkillService:
    """Load, execute, and manage skills (Layer 4)."""

    def __init__(self, skills_dir: str, lineage_svc, cognition_svc, assembly_svc):
        self.skills_dir = Path(skills_dir)
        self.lineage = lineage_svc
        self.cognition = cognition_svc
        self.assembly = assembly_svc
        self.parser = SkillParser()

    def load_skill(self, skill_name: str) -> SkillDefinition:
        skill_path = self.skills_dir / f"{skill_name}.md"
        if not skill_path.exists():
            raise FileNotFoundError(f"Skill not found: {skill_path}")
        return self.parser.parse_file(str(skill_path))

    def list_skills(self) -> list[str]:
        if not self.skills_dir.exists():
            return []
        return sorted(p.stem for p in self.skills_dir.glob("*.md"))

    def get_current_step(self, skill: SkillDefinition, step_index: int = 0) -> tuple[SkillStep, int]:
        if step_index >= len(skill.steps):
            return SkillStep(name="DONE", step_type="DONE", description="All steps complete"), step_index
        return skill.steps[step_index], step_index

    def is_gate_step(self, skill: SkillDefinition, step_index: int) -> bool:
        step, _ = self.get_current_step(skill, step_index)
        return step.step_type == "GATE"

    def advance_step(self, skill: SkillDefinition, current_index: int) -> int:
        next_idx = current_index + 1
        if next_idx >= len(skill.steps):
            return -1
        return next_idx

    def compose_pipeline(self, skill_names: list[str]) -> list[SkillDefinition]:
        return [self.load_skill(name) for name in skill_names]


class SkillSession:
    """Convenience wrapper around :class:`SkillStateMachine` for session management.

    Provides factory methods to create and resume skill execution sessions.
    """

    @staticmethod
    def create(
        skill_name: str,
        target: str,
        session_dir_base: str,
        phases: list[SkillPhase],
    ) -> SkillStateMachine:
        """Create a new timestamped session directory and initialise state.

        Args:
            skill_name: Name of the skill (e.g. ``"data-cleaning"``).
            target: Target data file or resource (e.g. ``"sales.csv"``).
            session_dir_base: Parent directory for session subdirectories.
            phases: Ordered list of :class:`SkillPhase` definitions.

        Returns:
            A ready-to-use :class:`SkillStateMachine`.
        """
        return SkillStateMachine.create_session(skill_name, target, phases, session_dir_base)

    @staticmethod
    def resume(session_dir: str) -> SkillStateMachine:
        """Resume an existing session from its ``.skill.yaml`` file.

        Args:
            session_dir: Path to the session directory containing ``.skill.yaml``.

        Returns:
            The restored :class:`SkillStateMachine`.
        """
        yaml_path = Path(session_dir) / ".skill.yaml"
        return SkillStateMachine.load(str(yaml_path))
