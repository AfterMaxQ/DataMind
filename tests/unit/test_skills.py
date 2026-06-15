"""Tests for SkillService."""
from datamind.engine.skills import SkillParser, SkillDefinition, SkillStep


SAMPLE_SKILL_MD = """# Data Cleaning

**Purpose:** Clean raw data files by detecting and fixing common issues.

**Inputs:** A dataset path from data/raw/.

## Workflow

1. **Analyze** (AUTO) - Read describe/ and sample data to understand structure
2. **Propose Strategy** (AUTO) - Identify issues and propose cleaning approach
3. **Gate: Approve** (GATE) - Present proposal for human approval
4. **Execute** (AUTO) - Generate and run cleaning script
5. **Validate** (AUTO) - Check output statistics and report
6. **Gate: Result** (GATE) - Show before/after for human sign-off

## Outputs

- Cleaned dataset in data/processed/
- Cleaning script in scripts/
- Execution log in executions/
"""


def test_parse_skill_md_purpose():
    parser = SkillParser()
    skill = parser.parse(SAMPLE_SKILL_MD)
    assert skill.purpose == "Clean raw data files by detecting and fixing common issues."


def test_parse_skill_md_steps():
    parser = SkillParser()
    skill = parser.parse(SAMPLE_SKILL_MD)
    assert len(skill.steps) == 6
    assert skill.steps[0].step_type == "AUTO"
    assert skill.steps[0].name == "Analyze"
    assert skill.steps[2].step_type == "GATE"
    assert skill.steps[2].name == "Approve"
    assert skill.steps[5].step_type == "GATE"
    assert skill.steps[5].name == "Result"


def test_parse_skill_md_inputs():
    parser = SkillParser()
    skill = parser.parse(SAMPLE_SKILL_MD)
    assert "dataset path from data/raw/" in skill.inputs


def test_parse_empty_skill_md():
    parser = SkillParser()
    skill = parser.parse("")
    assert skill.purpose == ""
    assert skill.steps == []


# --- SkillService tests ---

from datamind.engine.skills import SkillService
import pytest


def test_load_skill_from_directory(tmp_project):
    skills_dir = tmp_project / "skills"
    skills_dir.mkdir()
    (skills_dir / "data-cleaning.md").write_text(SAMPLE_SKILL_MD)
    svc = SkillService(skills_dir=str(skills_dir), lineage_svc=None, cognition_svc=None, assembly_svc=None)
    skill = svc.load_skill("data-cleaning")
    assert skill.name == "Data Cleaning"
    assert len(skill.steps) == 6


def test_get_current_step_first(tmp_project):
    skills_dir = tmp_project / "skills"
    skills_dir.mkdir()
    (skills_dir / "data-cleaning.md").write_text(SAMPLE_SKILL_MD)
    svc = SkillService(str(skills_dir), None, None, None)
    skill = svc.load_skill("data-cleaning")
    step, step_index = svc.get_current_step(skill, step_index=0)
    assert step.step_type == "AUTO"
    assert step.name == "Analyze"


def test_is_gate_step(tmp_project):
    skills_dir = tmp_project / "skills"
    skills_dir.mkdir()
    (skills_dir / "test.md").write_text("""# Test
**Purpose:** Testing.

## Workflow

1. **Do X** (AUTO) - Do stuff
2. **Gate: Confirm** (GATE) - Wait for human
""")
    svc = SkillService(str(skills_dir), None, None, None)
    skill = svc.load_skill("test")
    assert svc.is_gate_step(skill, 0) is False
    assert svc.is_gate_step(skill, 1) is True


def test_advance_step(tmp_project):
    skills_dir = tmp_project / "skills"
    skills_dir.mkdir()
    (skills_dir / "test.md").write_text("""# Test
**Purpose:** Testing.

## Workflow

1. **Do X** (AUTO) - Step one
2. **Gate: Confirm** (GATE) - Step two
3. **Do Y** (AUTO) - Step three
""")
    svc = SkillService(str(skills_dir), None, None, None)
    skill = svc.load_skill("test")
    next_idx = svc.advance_step(skill, current_index=0)
    assert next_idx == 1
    step, _ = svc.get_current_step(skill, next_idx)
    assert step.step_type == "GATE"


def test_load_missing_skill(tmp_project):
    skills_dir = tmp_project / "skills"
    skills_dir.mkdir()
    svc = SkillService(str(skills_dir), None, None, None)
    with pytest.raises(FileNotFoundError):
        svc.load_skill("nonexistent")
