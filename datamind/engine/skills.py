"""SkillService — SKILL.md parsing, AUTO/GATE execution, pipeline composition (Layer 4)."""

import re
from dataclasses import dataclass, field
from pathlib import Path


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
    outputs: list[str] = field(default_factory=list)


class SkillParser:
    """Parse SKILL.md files into SkillDefinition objects."""

    STEP_RE = re.compile(r"^\d+\.\s+\*\*(.+?)\*\*\s*\((\w+)\)\s*[-—]\s*(.+)$", re.MULTILINE)

    def parse(self, content: str) -> SkillDefinition:
        skill = SkillDefinition()

        name_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if name_match:
            skill.name = name_match.group(1).strip()

        purpose_match = re.search(r"\*\*Purpose:\*\*\s*(.+?)$", content, re.MULTILINE)
        if purpose_match:
            skill.purpose = purpose_match.group(1).strip()

        inputs_match = re.search(r"\*\*Inputs:\*\*\s*(.+?)$", content, re.MULTILINE)
        if inputs_match:
            skill.inputs = inputs_match.group(1).strip()

        for match in self.STEP_RE.finditer(content):
            step_name = match.group(1).strip()
            step_type_raw = match.group(2).strip().upper()
            description = match.group(3).strip()
            if step_type_raw == "GATE" or "GATE" in step_name.upper():
                step_type = "GATE"
                step_name = re.sub(r"^Gate:\s*", "", step_name)
            else:
                step_type = "AUTO"
            skill.steps.append(SkillStep(name=step_name, step_type=step_type, description=description))

        outputs_match = re.search(r"\*\*Outputs?\*\*\s*\n((?:\s*[-*]\s*.+\n?)*)", content, re.MULTILINE)
        if outputs_match:
            outputs_text = outputs_match.group(1)
            skill.outputs = [re.sub(r"^\s*[-*]\s*", "", line).strip() for line in outputs_text.strip().split("\n") if line.strip()]

        return skill

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
