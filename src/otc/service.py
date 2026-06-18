from __future__ import annotations

from src.core.config import settings
from src.otc.broker import IqOptionBroker
from src.otc.config import load_otc_config
from src.otc.iqoption_client import fetch_otc_capabilities, iqoption_configured, otc_transport
from src.otc.iqoption_client import reset_iqoption_client as reset_connections
from src.otc.mcp_client import mcp_configured


def build_otc_status() -> dict:
    config = load_otc_config()
    broker = IqOptionBroker(config)
    balance = None
    connection_ok = False
    connection_error: str | None = None
    mcp_mode: str | None = None
    transport = otc_transport()

    if iqoption_configured():
        try:
            balance = str(broker.get_balance_usd())
            connection_ok = True
            if transport == "mcp":
                caps = fetch_otc_capabilities() or {}
                mcp_mode = str(caps.get("mode") or "")
        except Exception as exc:
            reset_connections()
            connection_error = str(exc)
    else:
        connection_error = (
            "Credenciais IQ Option não configuradas "
            "(IQOPTION_MCP_TOKEN ou IQOPTION_EMAIL/PASSWORD)"
        )

    return {
        "profile_id": config.profile_id,
        "venue": config.venue,
        "account_mode": config.account_mode,
        "dry_run": config.dry_run,
        "otc_trading_enabled": settings.otc_trading_enabled,
        "transport": transport,
        "iqoption_configured": iqoption_configured(),
        "mcp_configured": mcp_configured(),
        "mcp_mode": mcp_mode,
        "connection_ok": connection_ok,
        "connection_error": connection_error,
        "balance_usd": balance,
        "default_stake_usd": str(config.default_stake_usd),
        "max_open_trades": config.max_open_trades,
        "expiry_minutes": config.expiry_minutes,
        "martingale": {
            "enabled": config.martingale.enabled,
            "max_protections": config.martingale.max_protections,
            "multiplier": str(config.martingale.multiplier),
        },
        "assets": list(config.assets),
        "telegram_listener": config.telegram.enabled,
        "divap_scan": False,
    }
