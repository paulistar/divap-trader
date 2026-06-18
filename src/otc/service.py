from __future__ import annotations

from src.core.config import settings
from src.otc.broker import IqOptionBroker
from src.otc.config import load_otc_config
from src.otc.iqoption_client import iqoption_configured, reset_iqoption_client


def build_otc_status() -> dict:
    config = load_otc_config()
    broker = IqOptionBroker(config)
    balance = None
    connection_ok = False
    connection_error: str | None = None

    if iqoption_configured():
        try:
            balance = str(broker.get_balance_usd())
            connection_ok = True
        except Exception as exc:
            reset_iqoption_client()
            connection_error = str(exc)
    else:
        connection_error = "Credenciais IQ Option não configuradas"

    return {
        "profile_id": config.profile_id,
        "venue": config.venue,
        "account_mode": config.account_mode,
        "dry_run": config.dry_run,
        "otc_trading_enabled": settings.otc_trading_enabled,
        "iqoption_configured": iqoption_configured(),
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
