"""Tests for the Click CLI."""
from click.testing import CliRunner
from datamind.cli.main import cli


def test_cli_init_creates_project(tmp_project):
    runner = CliRunner()
    result = runner.invoke(cli, ["init", str(tmp_project)])
    assert result.exit_code == 0
    assert (tmp_project / ".datamind").exists()
    assert (tmp_project / ".datamind" / "context").exists()
    assert "Initialized DataMind project" in result.output


def test_cli_init_with_name(tmp_project):
    runner = CliRunner()
    result = runner.invoke(
        cli, ["init", str(tmp_project), "--name", "myproject"]
    )
    assert result.exit_code == 0
    import yaml
    with open(tmp_project / ".datamind" / "config.yaml") as f:
        config = yaml.safe_load(f)
    assert config["project_name"] == "myproject"


def test_cli_init_preserves_existing(tmp_project):
    (tmp_project / ".datamind").mkdir()
    existing = tmp_project / ".datamind" / "existing.txt"
    existing.write_text("keep me")
    runner = CliRunner()
    result = runner.invoke(cli, ["init", str(tmp_project)])
    assert result.exit_code == 0
    assert existing.read_text() == "keep me"
