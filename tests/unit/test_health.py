from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_health_returns_ok_envelope() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"
    assert body["error"] is None
