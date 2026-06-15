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


if __name__ == "__main__":
    cli()
