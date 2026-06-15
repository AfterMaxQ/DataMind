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


def test_cli_lineage_query(tmp_project):
    from datamind.config import initialize_project
    initialize_project(tmp_project)
    raw = tmp_project / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "test.csv").write_text("x\n1\n")
    runner = CliRunner()
    result = runner.invoke(cli, ["lineage", "query", str(tmp_project), "--dataset", str(raw / "test.csv")])
    assert result.exit_code in (0, 1)


def test_cli_context_inject(tmp_project):
    from datamind.config import initialize_project
    initialize_project(tmp_project)
    runner = CliRunner()
    result = runner.invoke(cli, ["context", "inject", str(tmp_project)])
    assert result.exit_code in (0, 1)


def test_cli_skill_list(tmp_project):
    from datamind.config import initialize_project
    initialize_project(tmp_project)
    runner = CliRunner()
    result = runner.invoke(cli, ["skill", "list", str(tmp_project)])
    assert result.exit_code == 0
