from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.dashboard_auth import (
    create_session_token,
    dashboard_login_hint,
    validate_dashboard_secret,
    verify_session_token,
)
from src.api.main import app

client = TestClient(app)


def test_dashboard_page_returns_html() -> None:
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "DIVAP Trader" in response.text
    assert "dashboard.js" in response.text or "fetchDashboard" in response.text


def test_session_token_roundtrip() -> None:
    with patch("src.api.dashboard_auth.settings") as mock_settings:
        mock_settings.api_key = "test-secret-key-12345"
        token = create_session_token()
        assert verify_session_token(token) is True
        assert verify_session_token("invalid") is False


def test_validate_dashboard_secret() -> None:
    with patch("src.api.dashboard_auth.settings") as mock_settings:
        mock_settings.app_env = "production"
        mock_settings.api_key = "correct-key"
        mock_settings.dashboard_token = "panel-pin"
        assert validate_dashboard_secret("correct-key") is True
        assert validate_dashboard_secret("panel-pin") is True
        assert validate_dashboard_secret('"panel-pin"') is True
        assert validate_dashboard_secret("wrong") is False


def test_dashboard_login_hint_prefers_token() -> None:
    with patch("src.api.dashboard_auth.settings") as mock_settings:
        mock_settings.dashboard_token = "pin"
        assert "DASHBOARD_TOKEN" in dashboard_login_hint()
        mock_settings.dashboard_token = ""
        assert "API_KEY" in dashboard_login_hint()


def test_dashboard_auth_endpoint() -> None:
    with patch("src.api.routes.dashboard.validate_dashboard_secret", return_value=True):
        response = client.post("/dashboard/auth", json={"secret": "any"})
        assert response.status_code == 200
        assert "divap_dashboard" in response.cookies

    with patch("src.api.routes.dashboard.validate_dashboard_secret", return_value=False):
        response = client.post("/dashboard/auth", json={"secret": "bad"})
        assert response.status_code == 401
