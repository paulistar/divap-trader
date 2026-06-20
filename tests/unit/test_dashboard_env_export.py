from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.dashboard_env_export import build_env_export
from src.api.main import app
from src.core.config import Settings

client = TestClient(app)


def test_build_env_export_includes_operational_vars() -> None:
    cfg = Settings(
        TRADING_ENABLED=True,
        OTC_TRADING_ENABLED=True,
        TRADING_MODE="testnet",
        BINANCE_USE_TESTNET=True,
        OTC_TELEGRAM_CHAT_ID="-100123",
        BINANCE_API_KEY="secret-key",
    )
    text = build_env_export(cfg)
    assert "TRADING_ENABLED=true" in text
    assert "OTC_TRADING_ENABLED=true" in text
    assert "TRADING_MODE=testnet" in text
    assert "OTC_TELEGRAM_CHAT_ID=-100123" in text
    assert "secret-key" not in text
    assert "BINANCE_API_KEY=*** mantenha" in text


def test_build_env_export_empty_secrets() -> None:
    cfg = Settings()
    text = build_env_export(cfg)
    assert "BINANCE_API_KEY=" in text
    assert "*** mantenha" not in text.split("BINANCE_API_KEY=")[1].split("\n")[0]


def test_dashboard_settings_includes_env_export() -> None:
    with patch("src.api.routes.dashboard.settings") as mock_settings:
        mock_settings.app_env = "development"
        mock_settings.trading_enabled = False
        mock_settings.trading_mode = "testnet"
        mock_settings.binance_use_testnet = True
        mock_settings.trading_min_confidence = "high"
        mock_settings.trading_block_on_context_reject = True
        mock_settings.trading_max_open_trades = 5
        mock_settings.trading_dry_run = False
        mock_settings.context_enabled = True
        mock_settings.context_news_limit = 5
        mock_settings.otc_trading_enabled = True
        mock_settings.otc_telegram_chat_id = ""
        mock_settings.binance_api_key = ""
        mock_settings.binance_api_secret = ""
        mock_settings.iqoption_mcp_token = ""
        mock_settings.iqoption_email = ""
        mock_settings.iqoption_password = ""
        mock_settings.telegram_bot_token = ""
        mock_settings.iqoption_account_mode = "PRACTICE"
        mock_settings.iqoption_mcp_url = "https://digital-options.mcp.iqoption.com"
        mock_settings.openai_api_key = ""
        mock_settings.openai_model = "gpt-4o"
        mock_settings.openai_model_triage = "gpt-4o-mini"
        mock_settings.cryptopanic_api_key = ""
        mock_settings.telegram_chat_id = ""
        mock_settings.telegram_api_id = 0
        mock_settings.telegram_api_hash = ""
        mock_settings.telegram_user_session = ""
        mock_settings.dashboard_token = ""
        mock_settings.api_key = "change-me"
        mock_settings.vapid_public_key = ""
        mock_settings.vapid_private_key = ""
        mock_settings.vapid_claims_sub = "mailto:test@example.com"
        response = client.get("/dashboard/settings")
    assert response.status_code == 200
    data = response.json()["data"]
    assert "env_export" in data
    assert "TRADING_ENABLED=" in data["env_export"]


def test_dashboard_env_export_preview_from_form() -> None:
    with patch("src.api.routes.dashboard.settings") as mock_settings:
        mock_settings.app_env = "development"
        mock_settings.trading_enabled = False
        mock_settings.trading_mode = "testnet"
        mock_settings.binance_use_testnet = True
        mock_settings.trading_min_confidence = "high"
        mock_settings.trading_block_on_context_reject = True
        mock_settings.trading_max_open_trades = 5
        mock_settings.trading_dry_run = False
        mock_settings.context_enabled = True
        mock_settings.context_news_limit = 5
        mock_settings.otc_trading_enabled = True
        mock_settings.otc_telegram_chat_id = ""
        mock_settings.binance_api_key = ""
        mock_settings.binance_api_secret = ""
        mock_settings.iqoption_mcp_token = ""
        mock_settings.iqoption_email = ""
        mock_settings.iqoption_password = ""
        mock_settings.telegram_bot_token = ""
        mock_settings.iqoption_account_mode = "PRACTICE"
        mock_settings.iqoption_mcp_url = "https://digital-options.mcp.iqoption.com"
        mock_settings.openai_api_key = ""
        mock_settings.openai_model = "gpt-4o"
        mock_settings.openai_model_triage = "gpt-4o-mini"
        mock_settings.cryptopanic_api_key = ""
        mock_settings.telegram_chat_id = ""
        mock_settings.telegram_api_id = 0
        mock_settings.telegram_api_hash = ""
        mock_settings.telegram_user_session = ""
        mock_settings.dashboard_token = ""
        mock_settings.api_key = "change-me"
        mock_settings.vapid_public_key = ""
        mock_settings.vapid_private_key = ""
        mock_settings.vapid_claims_sub = "mailto:test@example.com"
        response = client.post(
            "/dashboard/settings/env-export",
            json={
                "binance_trading_enabled": True,
                "otc_trading_enabled": False,
                "trading_mode": "live",
            },
        )
    assert response.status_code == 200
    text = response.json()["data"]["env_export"]
    assert "TRADING_ENABLED=true" in text
    assert "OTC_TRADING_ENABLED=false" in text
    assert "TRADING_MODE=live" in text
