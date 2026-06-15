"""Tests for SkillService."""
from pathlib import Path
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


def test_all_builtin_skills_parse():
    """Verify all built-in SKILL.md files parse without errors."""
    skills_dir = Path("skills")
    assert skills_dir.exists(), "skills/ directory not found"
    parser = SkillParser()
    skill_count = 0
    for skill_path in sorted(skills_dir.glob("*.md")):
        skill = parser.parse_file(str(skill_path))
        assert skill.name, f"{skill_path.name}: missing name"
        assert skill.purpose, f"{skill_path.name}: missing purpose"
        assert len(skill.steps) > 0, f"{skill_path.name}: missing steps"
        gate_steps = [s for s in skill.steps if s.step_type == "GATE"]
        assert len(gate_steps) > 0, f"{skill_path.name}: missing GATE steps"
        skill_count += 1
    assert skill_count >= 5, f"Expected at least 5 skills, found {skill_count}"


# ---------------------------------------------------------------------------
# Phase extraction tests (SkillParser v2)
# ---------------------------------------------------------------------------


def test_phase_extraction_from_skill_md():
    """SkillParser extracts SkillPhase objects with correct fields."""
    parser = SkillParser()
    skill = parser.parse(SAMPLE_SKILL_MD)
    assert len(skill.phases) == 6

    # First phase
    p0 = skill.phases[0]
    assert p0.id == "analyze"
    assert p0.name == "Analyze"
    assert p0.type == "AUTO"

    # Gate phase (index 2)
    p2 = skill.phases[2]
    assert p2.id == "gate-approve"
    assert p2.name == "Approve"
    assert p2.type == "GATE"

    # Last gate phase
    p5 = skill.phases[5]
    assert p5.id == "gate-result"
    assert p5.name == "Result"
    assert p5.type == "GATE"


def test_duplicate_phase_ids_rejected():
    """Duplicate phase ids raise ValueError."""
    duplicate_md = """# Test
**Purpose:** Testing.

## Workflow

1. **Do Stuff** (AUTO) - First
2. **Do Stuff** (AUTO) - Same name different desc
"""
    parser = SkillParser()
    with pytest.raises(ValueError, match="Duplicate"):
        parser.parse(duplicate_md)


def test_empty_phases_rejected():
    """Skills with no phases raise ValueError."""
    empty_md = """# Empty Skill
**Purpose:** Nothing here.

## Workflow

"""
    parser = SkillParser()
    with pytest.raises(ValueError, match="at least one"):
        parser.parse(empty_md)


def test_gate_type_identification():
    """GATE type is correctly identified from (GATE) tag and Gate: prefix."""
    gate_md = """# Gate Test
**Purpose:** Test gate detection.

## Workflow

1. **Auto Step** (AUTO) - Just runs
2. **Gate: Confirm** (GATE) - Needs human
3. **Gate: Review** (GATE) - Also needs human
4. **Finalize** (AUTO) - Cleanup
"""
    parser = SkillParser()
    skill = parser.parse(gate_md)
    assert skill.phases[0].type == "AUTO"
    assert skill.phases[1].type == "GATE"
    assert skill.phases[2].type == "GATE"
    assert skill.phases[3].type == "AUTO"

    # Names should have "Gate: " stripped
    assert skill.phases[1].name == "Confirm"
    assert skill.phases[2].name == "Review"


def test_phase_id_generation_kebab_case():
    """Phase IDs are kebab-case: lowercase, spaces replaced with hyphens."""
    parser = SkillParser()
    skill = parser.parse(SAMPLE_SKILL_MD)

    assert skill.phases[0].id == "analyze"  # "Analyze"
    assert skill.phases[1].id == "propose-strategy"  # "Propose Strategy"
    assert skill.phases[2].id == "gate-approve"  # "Gate: Approve"
    assert skill.phases[3].id == "execute"  # "Execute"
    assert skill.phases[4].id == "validate"  # "Validate"
    assert skill.phases[5].id == "gate-result"  # "Gate: Result"


def test_parser_backward_compatible():
    """Existing skills still parse with steps populated (backward compat)."""
    parser = SkillParser()
    skill = parser.parse(SAMPLE_SKILL_MD)
    # steps list still populated
    assert len(skill.steps) == 6
    assert skill.steps[0].name == "Analyze"
    assert skill.steps[0].step_type == "AUTO"
    # phases list also populated
    assert len(skill.phases) == 6
    assert skill.phases[0].id == "analyze"


# ---------------------------------------------------------------------------
# SkillSession tests
# ---------------------------------------------------------------------------

from datamind.engine.skill_state import SkillPhase
from datamind.engine.skills import SkillSession


def test_skill_session_create(tmp_project):
    """SkillSession.create() creates a time-stamped session directory."""
    from datamind.engine.skills import SkillSession

    phases = [
        SkillPhase(id="analyze", name="Analyze", type="AUTO", description="Analyze"),
        SkillPhase(id="execute", name="Execute", type="AUTO", description="Execute"),
    ]
    sessions_base = str(tmp_project / "sessions")
    sm = SkillSession.create("data-cleaning", "sales.csv", sessions_base, phases)

    assert sm is not None
    assert sm.state.skill == "data-cleaning"
    assert sm.state.target == "sales.csv"
    assert sm.state.phase == "analyze"
    assert sm.state.phases["analyze"] == "in_progress"

    # Directory created with timestamp
    session_path = Path(sessions_base)
    dirs = list(session_path.iterdir())
    assert len(dirs) == 1
    assert "data-cleaning" in dirs[0].name
    assert "sales" in dirs[0].name


def test_skill_session_resume(tmp_project):
    """SkillSession.resume() loads a previously saved session."""
    phases = [
        SkillPhase(id="analyze", name="Analyze", type="AUTO", description="Analyze"),
        SkillPhase(id="execute", name="Execute", type="AUTO", description="Execute"),
    ]
    sessions_base = str(tmp_project / "sessions")
    sm = SkillSession.create("data-cleaning", "sales.csv", sessions_base, phases)

    # Complete first phase
    sm.complete_phase("analyze", artifact_path="phase-1.md")
    sm.save(str(Path(sessions_base) / list(Path(sessions_base).iterdir())[0].name / ".skill.yaml"))

    # Resume
    session_dir = str(list(Path(sessions_base).iterdir())[0])
    restored = SkillSession.resume(session_dir)

    assert restored is not None
    assert restored.state.skill == "data-cleaning"
    assert restored.state.phase == "execute"
    assert restored.state.phases["analyze"] == "complete"
    assert restored.state.phases["execute"] == "in_progress"
