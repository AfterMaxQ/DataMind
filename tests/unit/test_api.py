"""Tests for FastAPI REST API."""
import pytest
from unittest import mock
from fastapi.testclient import TestClient
from datamind.config import initialize_project


@pytest.fixture
def api_client(tmp_project):
    initialize_project(tmp_project)
    raw = tmp_project / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "sales.csv").write_text("price\n10\n20\n30\n")
    from datamind.api.app import create_app
    app = create_app(str(tmp_project))
    return TestClient(app)


def test_health_endpoint(api_client):
    response = api_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_datasets(api_client):
    response = api_client.get("/datasets")
    assert response.status_code == 200


def test_context_endpoint(api_client):
    response = api_client.get("/context")
    assert response.status_code == 200
    assert "content" in response.json()


def test_register_dataset(api_client, tmp_project):
    new_csv = tmp_project / "data" / "raw" / "new_data.csv"
    new_csv.write_text("a,b\n1,2\n")
    response = api_client.post("/datasets/register", json={"file_path": str(new_csv)})
    assert response.status_code == 200
    assert "new_data.csv" in response.json()["name"]


def test_list_skills(api_client):
    response = api_client.get("/skills")
    assert response.status_code == 200


def test_log_decision(api_client):
    response = api_client.post("/decisions", json={"what": "test", "why": "testing"})
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# v2 API endpoint tests
# ---------------------------------------------------------------------------


class TestV2ModelsEndpoint:
    """Tests for GET /models and POST /models/switch."""

    def test_list_models_returns_active_and_list(self, tmp_project):
        """GET /models should return available models and the active model."""
        initialize_project(tmp_project)
        from datamind.api.app import create_app

        # Mock list_models to return a known set
        with mock.patch("datamind.engine.project.OpenAIClient") as mock_client_cls:
            mock_instance = mock.MagicMock()
            mock_instance.model = "gpt-4o"
            mock_instance.list_models.return_value = ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]
            mock_client_cls.return_value = mock_instance

            app = create_app(str(tmp_project))
            client = TestClient(app)
            resp = client.get("/models")
            assert resp.status_code == 200
            data = resp.json()
            assert "models" in data
            assert data["active"] == "gpt-4o"

    def test_switch_model_rejects_unknown_model(self, tmp_project):
        """POST /models/switch with unknown model returns 400."""
        initialize_project(tmp_project)
        from datamind.api.app import create_app

        with mock.patch("datamind.engine.project.OpenAIClient") as mock_client_cls:
            mock_instance = mock.MagicMock()
            mock_instance.model = "gpt-4o"
            mock_instance.list_models.return_value = ["gpt-4o", "gpt-4o-mini"]
            mock_client_cls.return_value = mock_instance

            app = create_app(str(tmp_project))
            client = TestClient(app)
            resp = client.post("/models/switch", json={"model": "unknown-model"})
            assert resp.status_code == 400

    def test_switch_model_persists_across_requests(self, tmp_project):
        """POST /models/switch should persist the model for subsequent GET /models.

        Verifies that the same Project instance is reused (via app.state) rather
        than creating a new one per request, which would lose the mutation.
        """
        initialize_project(tmp_project)
        from datamind.api.app import create_app
        from datamind.engine.project import Project

        with mock.patch("datamind.engine.project.OpenAIClient") as mock_client_cls:
            mock_instance = mock.MagicMock()
            mock_instance.model = "gpt-4o"
            mock_instance.list_models.return_value = ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]
            mock_client_cls.return_value = mock_instance

            app = create_app(str(tmp_project))
            client = TestClient(app)

            # Check that app.state has a cached project
            assert hasattr(app.state, "project")
            assert isinstance(app.state.project, Project)

            # Switch model via endpoint
            resp = client.post("/models/switch", json={"model": "gpt-4o-mini"})
            assert resp.status_code == 200

            # Verify the mutation is on the singleton instance
            assert app.state.project.llm_client.model == "gpt-4o-mini"

            # Next GET should see the switched model (same singleton)
            resp2 = client.get("/models")
            assert resp2.status_code == 200
            assert resp2.json()["active"] == "gpt-4o-mini"


class TestV2ChatStreamEndpoint:
    """Tests for GET /chat/stream."""

    def test_chat_stream_missing_message_returns_422(self, tmp_project):
        """GET /chat/stream without message param returns validation error."""
        initialize_project(tmp_project)
        from datamind.api.app import create_app
        app = create_app(str(tmp_project))
        client = TestClient(app)
        resp = client.get("/chat/stream")
        assert resp.status_code == 422


class TestV2UsageEndpoint:
    """Tests for GET /usage."""

    def test_usage_returns_export_data(self, tmp_project):
        """GET /usage should return usage tracker export dict."""
        initialize_project(tmp_project)
        from datamind.api.app import create_app
        app = create_app(str(tmp_project))
        client = TestClient(app)
        resp = client.get("/usage")
        assert resp.status_code == 200
        data = resp.json()
        assert "totals" in data
        assert "by_model" in data
        assert "cost" in data
        assert "history" in data


class TestV2SkillSessionsEndpoint:
    """Tests for GET /skill-sessions."""

    def test_skill_sessions_returns_list(self, tmp_project):
        """GET /skill-sessions returns a sessions list even if empty."""
        initialize_project(tmp_project)
        from datamind.api.app import create_app
        app = create_app(str(tmp_project))
        client = TestClient(app)
        resp = client.get("/skill-sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data
        assert isinstance(data["sessions"], list)


class TestV2SkillGateEndpoint:
    """Tests for POST /skill/gate."""

    def test_gate_decision_not_found(self, tmp_project):
        """POST /skill/gate with nonexistent session returns 404."""
        initialize_project(tmp_project)
        from datamind.api.app import create_app
        app = create_app(str(tmp_project))
        client = TestClient(app)
        resp = client.post("/skill/gate", json={
            "session_dir": "/nonexistent/path",
            "decision": {"approved": True},
        })
        assert resp.status_code == 404

    def test_gate_approve_starts_agent_if_next_is_auto(self, tmp_project):
        """POST /skill/gate: if next phase is AUTO, agent should run through it."""
        from datamind.engine.skill_state import (
            SkillPhase, SkillStateMachine,
        )

        # Create a skill session with phases: GATE -> AUTO -> GATE
        phases = [
            SkillPhase(id="gate-review", name="Gate Review", type="GATE"),
            SkillPhase(id="auto-execute", name="Auto Execute", type="AUTO"),
            SkillPhase(id="gate-final", name="Gate Final", type="GATE"),
        ]

        initialize_project(tmp_project)
        sessions_dir = str(tmp_project / "data")
        from pathlib import Path
        Path(sessions_dir).mkdir(parents=True, exist_ok=True)
        sm = SkillStateMachine.create_session(
            "test-skill", "target.csv", phases, sessions_dir
        )

        # Get the yaml path for the gate endpoint
        session_subdir = str(Path(sessions_dir) / sm.state.session)
        yaml_path = session_subdir + "/.skill.yaml"

        from datamind.api.app import create_app
        app = create_app(str(tmp_project))
        client = TestClient(app)

        with mock.patch("datamind.engine.agent.DataMindAgent") as mock_agent_cls:
            mock_agent = mock.MagicMock()
            from datamind.engine.agent import WaitForApproval

            def fake_run(sm_instance, user_input=None):
                # Simulate completing the AUTO phase and advancing to next GATE
                sm_instance.complete_phase("auto-execute")
                return WaitForApproval(
                    phase_id="gate-final",
                    phase_name="Gate Final",
                    context_message="awaiting final approval",
                )

            mock_agent.run.side_effect = fake_run
            mock_agent_cls.return_value = mock_agent

            resp = client.post("/skill/gate", json={
                "session_dir": yaml_path,
                "decision": {"approved": True},
            })
            assert resp.status_code == 200
            data = resp.json()
            # Should have advanced past gate-review and stopped at gate-final
            assert data["phase"] == "gate-final"
            # Verify agent was created with services from app
            assert mock_agent_cls.called

    def test_gate_approve_skips_agent_if_next_is_gate(self, tmp_project):
        """POST /skill/gate: if next phase is also GATE, just return it."""
        import yaml
        from datamind.engine.skill_state import (
            SkillPhase, SkillStateMachine, PhaseStatus,
        )

        # Two consecutive GATE phases
        phases = [
            SkillPhase(id="gate-review", name="Gate Review", type="GATE"),
            SkillPhase(id="gate-final", name="Gate Final", type="GATE"),
        ]

        initialize_project(tmp_project)
        sessions_dir = str(tmp_project / "data")
        from pathlib import Path
        Path(sessions_dir).mkdir(parents=True, exist_ok=True)
        sm = SkillStateMachine.create_session(
            "test-skill", "target.csv", phases, sessions_dir
        )

        session_subdir = str(Path(sessions_dir) / sm.state.session)
        yaml_path = session_subdir + "/.skill.yaml"

        from datamind.api.app import create_app
        app = create_app(str(tmp_project))
        client = TestClient(app)

        with mock.patch("datamind.engine.agent.DataMindAgent") as mock_agent_cls:
            resp = client.post("/skill/gate", json={
                "session_dir": yaml_path,
                "decision": {"approved": True},
            })
            assert resp.status_code == 200
            data = resp.json()
            # Next phase is GATE, agent should NOT be created
            assert data["phase"] == "gate-final"
            mock_agent_cls.assert_not_called()
