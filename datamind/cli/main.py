"""Click CLI for DataMind Studio."""

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


if __name__ == "__main__":
    cli()
