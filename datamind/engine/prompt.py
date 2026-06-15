"""TemplateManager — markdown template loading, YAML frontmatter, and variable injection.

Provides:
- :class:`TemplateManager` — loads .md templates from a directory, parses YAML
  frontmatter, and renders templates with ``{{ variable }}`` substitution.
- ``DEFAULT_SYSTEM_PROMPT`` — built-in fallback when no template file exists.
"""

import re
from pathlib import Path

import yaml


DEFAULT_SYSTEM_PROMPT = """You are DataMind, an AI-native data science assistant.

You help users with data analysis, visualization, machine learning, and
statistical reasoning. You work with {{ context }}.

## Skills
{{ skills }}

Always provide clear, reproducible, and well-documented results.
"""


class TemplateManager:
    """Load and render markdown prompt templates with YAML frontmatter.

    Templates live as ``.md`` files in *templates_dir*.  Each file has
    optional YAML frontmatter between ``---`` markers, followed by a body
    that may contain ``{{ variable }}`` placeholders.
    """

    FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
    VARIABLE_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")

    def __init__(self, templates_dir: str = "prompts") -> None:
        self.templates_dir = Path(templates_dir)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_templates(self) -> list[str]:
        """Return sorted list of available template names (stem, no extension)."""
        if not self.templates_dir.exists():
            return []
        return sorted(
            p.stem for p in self.templates_dir.glob("*.md")
        )

    def load(self, name: str) -> dict:
        """Load a template by *name* (without ``.md``).

        Returns a dict with keys ``name``, ``frontmatter``, and ``body``.

        Raises :class:`FileNotFoundError` if the template file does not exist.
        """
        path = self.templates_dir / f"{name}.md"
        if not path.exists():
            raise FileNotFoundError(f"Template not found: {path}")

        text = path.read_text(encoding="utf-8")
        frontmatter: dict = {}
        body = text

        m = self.FRONTMATTER_RE.match(text)
        if m:
            try:
                frontmatter = yaml.safe_load(m.group(1)) or {}
            except yaml.YAMLError:
                frontmatter = {}
            body = text[m.end():].strip()

        return {"name": name, "frontmatter": frontmatter, "body": body}

    def render(self, name: str, variables: dict, fallback: bool = True) -> str:
        """Load template *name*, substitute *variables*, and return the rendered string.

        If *fallback* is ``True`` and the template file does not exist, the
        built-in :data:`DEFAULT_SYSTEM_PROMPT` is used instead.

        Raises :class:`FileNotFoundError` when *fallback* is ``False`` and
        the template is missing.
        """
        try:
            template = self.load(name)
        except FileNotFoundError:
            if fallback:
                return self._render_text(DEFAULT_SYSTEM_PROMPT, variables)
            raise

        rendered = self._render_text(template["body"], variables)
        return rendered

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _render_text(self, text: str, variables: dict) -> str:
        """Replace ``{{ var }}`` placeholders in *text* with values from *variables*."""
        def _replace(match: re.Match) -> str:
            key = match.group(1)
            return str(variables.get(key, match.group(0)))
        return self.VARIABLE_RE.sub(_replace, text)
