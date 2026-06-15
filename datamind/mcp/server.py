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


def tool_execute_skill(project: Project, skill_name: str, target: str) -> dict:
    """Execute a skill workflow against a target, returning phase results.

    Creates a skill session, runs the DataMind agent through all AUTO phases
    until a GATE is reached or the workflow completes.  If a GATE is
    encountered the caller must call :func:`tool_approve_gate` to continue.

    Returns a dict with ``session_id``, ``skill``, ``target``, the last
    ``phase`` completed, and any ``gate`` that is awaiting approval.
    """
    from datamind.engine.skills import SkillSession
    from datamind.engine.agent import DataMindAgent, WaitForApproval, AgentResponse, SkillComplete, AgentError

    # Load skill definition
    skill_def = project.skills.load_skill(skill_name)

    # Create session
    sessions_base = str(project.paths["data_dir"])
    sm = SkillSession.create(skill_name, target, sessions_base, skill_def.phases)

    agent = project.create_agent()

    # Run through AUTO phases
    result = agent.run(sm)

    if isinstance(result, AgentError):
        return {"session_id": sm.state.session, "skill": skill_name, "target": target,
                "error": result.error_message}

    if isinstance(result, WaitForApproval):
        return {"session_id": sm.state.session, "skill": skill_name, "target": target,
                "phase": sm.state.phase, "gate": {"phase_id": result.phase_id,
                "phase_name": result.phase_name, "context": result.context_message}}

    if isinstance(result, AgentResponse):
        return {"session_id": sm.state.session, "skill": skill_name, "target": target,
                "phase": result.phase_id, "content": result.content,
                "usage": result.usage}

    if isinstance(result, SkillComplete):
        return {"session_id": sm.state.session, "skill": skill_name, "target": target,
                "result": result.result, "usage": result.usage}

    return {"session_id": sm.state.session, "skill": skill_name, "target": target,
            "status": "unknown"}


def tool_approve_gate(project: Project, session_dir: str, decision: dict) -> dict:
    """Approve a GATE phase and continue skill execution.

    Loads the SkillStateMachine from the session ``.skill.yaml``, approves
    the current GATE phase with the provided *decision*, and if the next
    phase is AUTO, creates a DataMindAgent and runs through auto phases
    until the next GATE or workflow completion.

    Args:
        project: The DataMind Project instance.
        session_dir: Path to the session directory containing ``.skill.yaml``.
        decision: Dict capturing the human approval decision.

    Returns:
        A dict with ``phase``, ``result``, and optionally ``gate``,
        ``content``, ``usage``, or ``error``.
    """
    import os
    from datamind.engine.skill_state import SkillStateMachine
    from datamind.engine.agent import WaitForApproval, AgentResponse, SkillComplete, AgentError

    # Normalize path to .skill.yaml
    yaml_path = session_dir
    if not yaml_path.endswith(".skill.yaml"):
        yaml_path = os.path.join(session_dir, ".skill.yaml")

    try:
        sm = SkillStateMachine.load(yaml_path)
    except FileNotFoundError:
        return {"error": f"Session not found: {session_dir}"}

    current_phase = sm.state.phase
    try:
        next_phase = sm.approve_gate(current_phase, decision)
    except ValueError as e:
        return {"error": str(e)}

    # If next phase is AUTO, resume agent execution through it
    if next_phase:
        next_phase_obj = sm.get_current_phase()
        if next_phase_obj.type == "AUTO":
            agent = project.create_agent()
            agent_result = agent.run(sm)
            if isinstance(agent_result, AgentError):
                return {"phase": sm.state.phase, "result": sm.state.result,
                        "error": agent_result.error_message}
            if isinstance(agent_result, WaitForApproval):
                return {"phase": sm.state.phase, "result": sm.state.result,
                        "gate": {"phase_id": agent_result.phase_id,
                                 "phase_name": agent_result.phase_name,
                                 "context": agent_result.context_message}}
            if isinstance(agent_result, AgentResponse):
                return {"phase": agent_result.phase_id, "result": sm.state.result,
                        "content": agent_result.content, "usage": agent_result.usage}
            if isinstance(agent_result, SkillComplete):
                return {"phase": "", "result": agent_result.result,
                        "usage": agent_result.usage}

    return {"phase": next_phase, "result": sm.state.result}


def tool_list_models(project: Project) -> dict:
    """List available models and the active model."""
    try:
        available = project.llm_client.list_models()
    except Exception:
        available = [project.llm_client.model]
    return {"active": project.llm_client.model, "available": available}
