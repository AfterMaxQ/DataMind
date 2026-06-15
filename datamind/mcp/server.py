"""MCP Server — wraps the DataMind engine as MCP tools."""

from datamind.engine.project import Project


def tool_read_context(project: Project) -> str:
    """Return the current context for AI injection."""
    decisions = project.cognition.get_recent_decisions(5)
    discoveries = project.cognition.get_recent_discoveries(5)
    datasets = project.graph.list_nodes_by_type("dataset")
    lines = ["# DataMind Context", ""]
    lines.append(f"## Datasets ({len(datasets)})")
    for d in datasets:
        lines.append(f"- {d['name']}")
    lines.append("")
    lines.append(f"## Recent Decisions ({len(decisions)})")
    for d in decisions:
        lines.append(f"- {d['what']}: {d['why']}")
    return "\n".join(lines)


def tool_register_dataset(project: Project, file_path: str) -> str:
    """Register a dataset and auto-describe it."""
    node_id = project.lineage.register_dataset(str(file_path))
    node = project.graph.get_node(node_id)
    return f"Registered dataset: {node['name']} (id: {node_id})"


def tool_log_decision(project: Project, what: str, why: str, alternatives: list[str] | None = None) -> dict:
    """Log a decision to the cognitive journey."""
    d_id = project.cognition.log_decision(what=what, why=why, alternatives=alternatives or [])
    return {"id": d_id, "what": what, "why": why}


def tool_list_datasets(project: Project) -> list[dict]:
    """List all registered datasets."""
    datasets = project.graph.list_nodes_by_type("dataset")
    return [{"id": d["id"], "name": d["name"], "path": d.get("path", ""), "created_at": d["created_at"]} for d in datasets]
