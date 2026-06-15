"""Tests for the Click CLI."""
import os
from unittest import mock

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
    assert result.exit_code == 0


def test_cli_context_inject(tmp_project):
    from datamind.config import initialize_project
    initialize_project(tmp_project)
    runner = CliRunner()
    result = runner.invoke(cli, ["context", "inject", str(tmp_project)])
    assert result.exit_code == 0


def test_cli_skill_list(tmp_project):
    from datamind.config import initialize_project
    initialize_project(tmp_project)
    runner = CliRunner()
    result = runner.invoke(cli, ["skill", "list", str(tmp_project)])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# v2 CLI command tests
# ---------------------------------------------------------------------------


class TestV2ModelsCommands:
    """Tests for 'models' and 'models switch' CLI commands."""

    def test_models_list(self, tmp_project):
        """'datamind models' should list available models."""
        from datamind.config import initialize_project
        initialize_project(tmp_project)

        with mock.patch("datamind.engine.project.OpenAIClient") as mock_client_cls:
            mock_instance = mock.MagicMock()
            mock_instance.model = "gpt-4o"
            mock_instance.list_models.return_value = ["gpt-4o", "gpt-4o-mini"]
            mock_client_cls.return_value = mock_instance

            runner = CliRunner()
            with mock.patch("os.getcwd", return_value=str(tmp_project)):
                result = runner.invoke(cli, ["models"])
            assert result.exit_code == 0
            assert "Active model" in result.output
            assert "gpt-4o" in result.output

    def test_models_switch(self, tmp_project):
        """'datamind models switch <name>' should switch the active model."""
        from datamind.config import initialize_project
        initialize_project(tmp_project)

        with mock.patch("datamind.engine.project.OpenAIClient") as mock_client_cls:
            mock_instance = mock.MagicMock()
            mock_instance.model = "gpt-4o"
            mock_instance.list_models.return_value = ["gpt-4o", "gpt-4o-mini"]
            mock_client_cls.return_value = mock_instance

            runner = CliRunner()
            with mock.patch("os.getcwd", return_value=str(tmp_project)):
                result = runner.invoke(cli, ["models", "switch", "gpt-4o-mini"])
            assert result.exit_code == 0
            assert "Switched to model: gpt-4o-mini" in result.output

    def test_models_switch_unknown(self, tmp_project):
        """'datamind models switch <unknown>' should exit with error."""
        from datamind.config import initialize_project
        initialize_project(tmp_project)

        with mock.patch("datamind.engine.project.OpenAIClient") as mock_client_cls:
            mock_instance = mock.MagicMock()
            mock_instance.model = "gpt-4o"
            mock_instance.list_models.return_value = ["gpt-4o"]
            mock_client_cls.return_value = mock_instance

            runner = CliRunner()
            with mock.patch("os.getcwd", return_value=str(tmp_project)):
                result = runner.invoke(cli, ["models", "switch", "unknown"])
            assert result.exit_code == 1
            assert "not found" in result.output


class TestV2ChatCommands:
    """Tests for 'chat start' and 'chat skill' CLI commands."""

    def test_chat_start_no_project(self, tmp_project):
        """'datamind chat start' without a project fails."""
        runner = CliRunner()
        # Change to tmp_project dir which has no .datamind
        with mock.patch.dict(os.environ, {}, clear=False):
            result = runner.invoke(cli, ["chat", "start", "--message", "hello"])
        assert result.exit_code == 1

    def test_chat_start_with_project(self, tmp_project):
        """'datamind chat start' initializes a chat session."""
        from datamind.config import initialize_project
        initialize_project(tmp_project)

        class FakeChunk:
            def __init__(self):
                self.content = "Hello!"
                self.usage = None
                self.model = "gpt-4o"

        with mock.patch("datamind.engine.project.OpenAIClient") as mock_client_cls:
            mock_instance = mock.MagicMock()
            mock_instance.model = "gpt-4o"
            mock_instance.list_models.return_value = ["gpt-4o"]
            mock_instance.chat.return_value = [FakeChunk()]
            mock_client_cls.return_value = mock_instance

            runner = CliRunner()
            with mock.patch.dict(os.environ, {}, clear=False):
                with mock.patch("os.getcwd", return_value=str(tmp_project)):
                    result = runner.invoke(cli, [
                        "chat", "start", "--message", "hello",
                    ])
            assert result.exit_code == 0

    def test_chat_start_with_skill(self, tmp_project):
        """'datamind chat start --skill <name>' includes skill context."""
        from datamind.config import initialize_project
        initialize_project(tmp_project)

        class FakeChunk:
            def __init__(self, content="reply", usage=None):
                self.content = content
                self.usage = usage
                self.model = "gpt-4o"

        with mock.patch("datamind.engine.project.OpenAIClient") as mock_client_cls:
            mock_instance = mock.MagicMock()
            mock_instance.model = "gpt-4o"
            mock_instance.list_models.return_value = ["gpt-4o"]
            mock_instance.chat.return_value = [FakeChunk("Using SQL for analysis")]
            mock_client_cls.return_value = mock_instance

            runner = CliRunner()
            with mock.patch.dict(os.environ, {}, clear=False):
                with mock.patch("os.getcwd", return_value=str(tmp_project)):
                    result = runner.invoke(cli, [
                        "chat", "start", "--message", "analyze data",
                        "--skill", "data-analysis",
                    ])
            assert result.exit_code == 0
