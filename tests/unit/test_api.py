"""Tests for FastAPI REST API."""
import pytest
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
