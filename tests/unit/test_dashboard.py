from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_dashboard_page_returns_html() -> None:
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "DIVAP Trader" in response.text
    assert "stats-grid" in response.text
