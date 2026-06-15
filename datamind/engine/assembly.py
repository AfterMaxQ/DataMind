"""AssemblyService — context file generation and priority-ordered packing (Layer 3)."""

from pathlib import Path


class AssemblyService:
    """Generates context files from L1 + L2 data for AI consumption."""

    def __init__(self, lineage_service, cognition_service, context_dir: str):
        self._lineage = lineage_service
        self._cognition = cognition_service
        self.context_dir = Path(context_dir)

    def generate_project_md(self, project_name: str, datasets: list[str]) -> Path:
        lines = [f"# Project: {project_name}", "", "## Datasets"]
        for ds in datasets:
            lines.append(f"- {ds}")
        return self._write("PROJECT.md", "\n".join(lines))

    def generate_datasets_md(self, datasets_info: list[dict]) -> Path:
        lines = ["# Datasets", ""]
        for ds in datasets_info:
            lines.append(f"## {ds['name']}")
            lines.append(f"- Rows: {ds.get('rows', 'N/A')}")
            lines.append(f"- Columns: {ds.get('columns', 'N/A')}")
            if ds.get("describe_path"):
                lines.append(f"- Describe: `{ds['describe_path']}`")
            lines.append("")
        return self._write("DATASETS.md", "\n".join(lines))

    def generate_history_md(self, decisions: list[dict], discoveries: list[dict]) -> Path:
        lines = ["# History", ""]
        lines.append("## Decisions")
        for d in decisions:
            lines.append(f"- {d['what']}: {d['why']}")
        lines.append("")
        lines.append("## Discoveries")
        for disc in discoveries:
            lines.append(f"- {disc['finding']}")
        return self._write("HISTORY.md", "\n".join(lines))

    def _write(self, name: str, content: str) -> Path:
        path = self.context_dir / name
        path.write_text(content, encoding="utf-8")
        return path


def estimate_tokens(text: str) -> int:
    """Rough token estimation: ~8 characters per token for English text."""
    return len(text) // 8


def pack_manifest(
    context_dir: str, project_md_content: str = "", datasets_md_content: str = "",
    history_md_content: str = "", exploration_md_content: str = "",
    params_md_content: str = "", checkpoint_md_content: str = "",
) -> str:
    """Assemble CONTEXT_MANIFEST.md with priority-ordered sections. Truncates from bottom up when over budget."""
    TOKEN_BUDGET = 5000
    sections = [
        ("P1_PROJECT", project_md_content), ("P1_DATASETS", datasets_md_content),
        ("P2_HISTORY", history_md_content), ("P3_EXPLORATION", exploration_md_content),
        ("P3_PARAMS", params_md_content), ("P4_CHECKPOINT", checkpoint_md_content),
    ]
    parts = ["# Context Manifest", "", "> Priority-ordered context for AI injection.", ""]
    total = 0
    for label, content in sections:
        if not content:
            continue
        st = estimate_tokens(content)
        if total + st > TOKEN_BUDGET:
            remaining = TOKEN_BUDGET - total
            if remaining < 100:
                break
            truncated = content[:remaining * 4] + "\n\n[TRUNCATED — budget exceeded]"
            parts.append(f"\n## {label}\n")
            parts.append(truncated)
            break
        else:
            parts.append(f"\n## {label}\n")
            parts.append(content)
            total += st
    return "\n".join(parts)
