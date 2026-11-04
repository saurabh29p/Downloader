from fastapi.testclient import TestClient

from anyget import __version__
from anyget.main import create_app

client = TestClient(create_app())


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version() -> None:
    body = client.get("/api/version").json()
    assert body["name"] == "anyget"
    assert body["version"] == __version__


def test_openapi_has_operation_ids() -> None:
    schema = client.get("/api/openapi.json").json()
    assert schema["paths"]["/api/health"]["get"]["operationId"] == "getHealth"
