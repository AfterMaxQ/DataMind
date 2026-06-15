"""Tests for TemplateManager — template loading, YAML frontmatter, and variable injection."""
import pytest
from pathlib import Path

from datamind.engine.prompt import TemplateManager, DEFAULT_SYSTEM_PROMPT


SAMPLE_TEMPLATE = """---
role: data-scientist
description: Primary data science assistant
---
You are a {{ role }} working on {{ context }}.

## Skills Available
{{ skills }}

Always be helpful.
"""


@pytest.fixture
def templates_dir(tmp_project):
    """Create a temporary directory with a sample template."""
    d = tmp_project / "prompts"
    d.mkdir()
    (d / "data-scientist.md").write_text(SAMPLE_TEMPLATE, encoding="utf-8")
    return d


@pytest.fixture
def empty_dir(tmp_project):
    """Create an empty temporary directory."""
    d = tmp_project / "empty_prompts"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# test_load_template
# ---------------------------------------------------------------------------

def test_load_template(templates_dir):
    """load() returns a dict with name, frontmatter, and body."""
    mgr = TemplateManager(templates_dir=str(templates_dir))
    result = mgr.load("data-scientist")
    assert result["name"] == "data-scientist"
    assert result["frontmatter"]["role"] == "data-scientist"
    assert result["frontmatter"]["description"] == "Primary data science assistant"
    assert "{{ role }}" in result["body"]
    assert "{{ context }}" in result["body"]
    assert "{{ skills }}" in result["body"]


# ---------------------------------------------------------------------------
# test_render_injects_variables
# ---------------------------------------------------------------------------

def test_render_injects_variables(templates_dir):
    """render() replaces {{ variable }} placeholders with provided values."""
    mgr = TemplateManager(templates_dir=str(templates_dir))
    rendered = mgr.render("data-scientist", {
        "role": "Data Scientist",
        "context": "a customer churn analysis",
        "skills": "- data-cleaning\n- eda",
    })
    assert "Data Scientist" in rendered
    assert "customer churn analysis" in rendered
    assert "- data-cleaning" in rendered
    assert "{{ role }}" not in rendered
    assert "{{ context }}" not in rendered
    assert "{{ skills }}" not in rendered


# ---------------------------------------------------------------------------
# test_missing_template_fallback_to_default
# ---------------------------------------------------------------------------

def test_missing_template_fallback_to_default(templates_dir):
    """When a template is missing and fallback=True, the built-in default is used."""
    mgr = TemplateManager(templates_dir=str(templates_dir))
    rendered = mgr.render("nonexistent", {"context": "test task"}, fallback=True)
    assert "DataMind" in rendered
    assert "data science" in rendered.lower()


# ---------------------------------------------------------------------------
# test_missing_template_no_fallback_raises
# ---------------------------------------------------------------------------

def test_missing_template_no_fallback_raises(templates_dir):
    """When a template is missing and fallback=False, FileNotFoundError is raised."""
    mgr = TemplateManager(templates_dir=str(templates_dir))
    with pytest.raises(FileNotFoundError):
        mgr.load("nonexistent")
    with pytest.raises(FileNotFoundError):
        mgr.render("nonexistent", {"context": "test"}, fallback=False)


# ---------------------------------------------------------------------------
# test_builtin_default_when_no_file
# ---------------------------------------------------------------------------

def test_builtin_default_when_no_file(empty_dir):
    """TemplateManager works even with an empty template directory."""
    mgr = TemplateManager(templates_dir=str(empty_dir))
    assert mgr.list_templates() == []
    # Rendering with fallback should still work
    rendered = mgr.render("any-template", {"context": "test"}, fallback=True)
    assert "DataMind" in rendered


# ---------------------------------------------------------------------------
# test_list_templates
# ---------------------------------------------------------------------------

def test_list_templates(templates_dir):
    """list_templates() returns all .md filenames (without extension) in the directory."""
    mgr = TemplateManager(templates_dir=str(templates_dir))
    templates = mgr.list_templates()
    assert "data-scientist" in templates
    assert len(templates) == 1

    # Add another template
    (templates_dir / "code-reviewer.md").write_text("""---
role: code-reviewer
---
Review this code: {{ context }}""", encoding="utf-8")
    templates = mgr.list_templates()
    assert len(templates) == 2
    assert "code-reviewer" in templates
