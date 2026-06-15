"""Click CLI for DataMind Studio."""

import os

import click
from datamind.config import initialize_project


@click.group()
@click.version_option()
def cli():
    """DataMind Studio -- AI-native data science research system."""
    pass


@cli.command()
@click.argument("project_root", type=click.Path(exists=True))
@click.option("--name", default=None, help="Project name")
def init(project_root, name):
    """Initialize a DataMind project at PROJECT_ROOT."""
    config = None
    if name:
        config = {"project_name": name}
    try:
        paths = initialize_project(project_root, config)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Initialized DataMind project at {project_root}")
    click.echo(f"  .datamind/  -> {paths['graph_db'].parent}")
    click.echo(f"  data/raw/   -> {paths['raw_data']}")
    click.echo(f"  data/processed/ -> {paths['processed_data']}")
    click.echo(f"  scripts/    -> {paths['scripts_dir']}")


@cli.group()
def lineage():
    """Query data lineage."""
    pass


@lineage.command("query")
@click.argument("project_root", type=click.Path(exists=True))
@click.option("--dataset", help="Dataset path to query lineage for")
def lineage_query(project_root, dataset):
    """Query ancestors and descendants for a dataset."""
    from datamind.engine.project import Project
    proj = Project(project_root)
    if dataset:
        node = proj.lineage.find_dataset_by_path(str(dataset))
        if not node:
            click.echo(f"Dataset not found: {dataset}")
            click.echo("Registered datasets:")
            for ds in proj.graph.list_nodes_by_type("dataset"):
                click.echo(f"  {ds.get('path', ds['name'])}")
            return
        ancestors = proj.lineage.query_ancestors(node["id"])
        descendants = proj.lineage.query_descendants(node["id"])
        click.echo(f"Lineage for: {node['name']}")
        if ancestors:
            click.echo("  Ancestors (upstream):")
            for a in ancestors:
                click.echo(f"    [{a['type']}] {a['name']}")
        if descendants:
            click.echo("  Descendants (downstream):")
            for d in descendants:
                click.echo(f"    [{d['type']}] {d['name']}")


@cli.group()
def context():
    """Manage context assembly."""
    pass


@context.command("inject")
@click.argument("project_root", type=click.Path(exists=True))
def context_inject(project_root):
    """Generate CONTEXT_MANIFEST.md for AI injection."""
    from datamind.engine.project import Project
    proj = Project(project_root)
    datasets = proj.graph.list_nodes_by_type("dataset")
    ds_info = [{"name": d["name"], "rows": "N/A", "columns": "N/A"} for d in datasets]
    proj.assembly.generate_datasets_md(ds_info)
    decisions = proj.cognition.get_recent_decisions(5)
    discoveries = proj.cognition.get_recent_discoveries(5)
    proj.assembly.generate_history_md(decisions, discoveries)
    click.echo(f"Context regenerated at {proj.assembly.context_dir}")
    click.echo(f"  Datasets: {len(datasets)}")


@cli.group()
def skill():
    """Manage skills."""
    pass


@skill.command("list")
@click.argument("project_root", type=click.Path(exists=True))
def skill_list(project_root):
    """List available skills."""
    from datamind.engine.project import Project
    proj = Project(project_root)
    skills = proj.skills.list_skills()
    if skills:
        click.echo("Available skills:")
        for s in skills:
            skill_def = proj.skills.load_skill(s)
            click.echo(f"  {s}: {skill_def.purpose}")
    else:
        click.echo("No skills found in skills/ directory")


@cli.group()
def chat():
    """Interactive chat with the DataMind agent."""
    pass


@chat.command("start")
@click.option("--message", required=True, help="User message to send")
@click.option("--skill", default=None, help="Optional skill name")
@click.option("--target", default=None, help="Optional target file path")
def chat_start(message, skill, target):
    """Start a streaming chat with the agent."""
    from datamind.engine.project import Project

    project_root = os.getcwd()
    try:
        proj = Project(project_root)
    except FileNotFoundError:
        click.echo("No .datamind/ found in current directory. Run 'datamind init' first.", err=True)
        raise SystemExit(1)

    system_prompt = proj.prompt_manager.render("data-scientist", {
        "context": f"Skill: {skill}" if skill else "General chat",
        "skills": ", ".join(proj.skills.list_skills()) if not skill else skill,
    })

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message},
    ]

    click.echo(f"DataMind (model: {proj.llm_client.model}):")
    try:
        stream = proj.llm_client.chat(messages=messages, stream=True)
        for chunk in stream:
            delta = chunk.content if hasattr(chunk, "content") else ""
            if delta:
                click.echo(delta, nl=False)
            if chunk.usage:
                proj.usage_tracker.record(
                    prompt_tokens=chunk.usage.get("prompt_tokens", 0),
                    completion_tokens=chunk.usage.get("completion_tokens", 0),
                    model=chunk.model or proj.llm_client.model,
                )
        click.echo()  # final newline
    except Exception as exc:
        click.echo(f"\nError: {exc}", err=True)
        raise SystemExit(1)


@chat.command("skill")
@click.argument("skill_name")
@click.argument("target")
def chat_skill(skill_name, target):
    """Execute a skill with GATE interaction."""
    from datamind.engine.project import Project
    from datamind.engine.skills import SkillSession
    from datamind.engine.agent import DataMindAgent, WaitForApproval, AgentResponse, SkillComplete, AgentError

    project_root = os.getcwd()
    try:
        proj = Project(project_root)
    except FileNotFoundError:
        click.echo("No .datamind/ found in current directory. Run 'datamind init' first.", err=True)
        raise SystemExit(1)

    # Load skill
    try:
        skill_def = proj.skills.load_skill(skill_name)
    except FileNotFoundError:
        click.echo(f"Skill not found: {skill_name}", err=True)
        click.echo(f"Available: {proj.skills.list_skills()}", err=True)
        raise SystemExit(1)

    # Create session
    sessions_base = str(proj.paths["data_dir"])
    sm = SkillSession.create(skill_name, target, sessions_base, skill_def.phases)
    click.echo(f"Session: {sm.state.session}")
    click.echo(f"Skill: {skill_name} -> {target}")
    click.echo(f"Phases: {len(skill_def.phases)}")

    agent = proj.create_agent()

    # Run loop
    result = agent.run(sm)
    while True:
        if isinstance(result, AgentError):
            click.echo(f"Error: {result.error_message}", err=True)
            raise SystemExit(1)
        elif isinstance(result, WaitForApproval):
            click.echo(f"\nGATE: {result.phase_name} ({result.phase_id})")
            click.echo(f"Context: {result.context_message}")
            choice = click.prompt("Approve? (y/n)", type=str, default="n")
            if choice.lower() in ("y", "yes"):
                result = agent.approve_gate({"approved": True, "comment": "Approved via CLI"})
            else:
                result = agent.approve_gate({"approved": False, "comment": "Rejected via CLI"})
        elif isinstance(result, AgentResponse):
            click.echo(f"\nPhase complete: {result.phase_id}")
            click.echo(result.content[:200] + "..." if len(result.content) > 200 else result.content)
            result = agent.run(sm)
        elif isinstance(result, SkillComplete):
            click.echo(f"\nSkill complete: {result.result}")
            usage = result.usage
            click.echo(f"Tokens: {usage.get('totals', {}).get('total_tokens', 0)}")
            break
        else:
            break


@cli.group(invoke_without_command=True)
@click.pass_context
def models(ctx):
    """Manage AI models."""
    if ctx.invoked_subcommand is None:
        # Default: list models
        from datamind.engine.project import Project
        project_root = os.getcwd()
        try:
            proj = Project(project_root)
        except FileNotFoundError:
            click.echo("No .datamind/ found in current directory. Run 'datamind init' first.", err=True)
            raise SystemExit(1)
        try:
            available = proj.llm_client.list_models()
        except Exception:
            available = [proj.llm_client.model]
        click.echo(f"Active model: {proj.llm_client.model}")
        click.echo(f"Available models ({len(available)}):")
        for m in available:
            marker = " *" if m == proj.llm_client.model else ""
            click.echo(f"  {m}{marker}")


@models.command("switch")
@click.argument("model_name")
def models_switch(model_name):
    """Switch the active model."""
    from datamind.engine.project import Project
    project_root = os.getcwd()
    try:
        proj = Project(project_root)
    except FileNotFoundError:
        click.echo("No .datamind/ found in current directory. Run 'datamind init' first.", err=True)
        raise SystemExit(1)
    available = proj.llm_client.list_models()
    if model_name not in available:
        click.echo(f"Model '{model_name}' not found. Available: {available}", err=True)
        raise SystemExit(1)
    proj.llm_client.model = model_name
    click.echo(f"Switched to model: {model_name}")


if __name__ == "__main__":
    cli()
