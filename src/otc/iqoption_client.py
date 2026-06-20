from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from functools import lru_cache
from typing import Any

from src.core.config import settings
from src.core.exceptions import ExchangeError
from src.otc.mcp_client import (
    fetch_mcp_balance,
    fetch_mcp_capabilities,
    mcp_call,
    mcp_configured,
    reset_mcp_client,
)

logger = logging.getLogger(__name__)


def legacy_configured() -> bool:
    return bool(settings.iqoption_email.strip() and settings.iqoption_password.strip())


def iqoption_configured() -> bool:
    return mcp_configured() or legacy_configured()


def otc_transport() -> str | None:
    if mcp_configured():
        return "mcp"
    if legacy_configured():
        return "legacy"
    return None


def reset_iqoption_client() -> None:
    reset_mcp_client()
    get_iqoption_client.cache_clear()


@lru_cache
def get_iqoption_client() -> Any:
    email = settings.iqoption_email.strip()
    password = settings.iqoption_password.strip()
    if not email or not password:
        raise ExchangeError(
            "IQOPTION_EMAIL e IQOPTION_PASSWORD não configurados. "
            "Use conta demo/prática apenas."
        )
    try:
        from iqoptionapi.stable_api import IQ_Option
    except ImportError as exc:
        raise ExchangeError(
            "Pacote iqoptionapi não instalado. "
            "Instale: pip install websocket-client==0.56 "
            "git+https://github.com/Lu-Yi-Hsun/iqoptionapi.git"
        ) from exc

    api = IQ_Option(email, password)
    connected, reason = api.connect()
    if not connected:
        raise ExchangeError(f"Falha ao conectar IQ Option: {reason}")

    mode = settings.iqoption_account_mode.strip().upper() or "PRACTICE"
    try:
        api.change_balance(mode)
    except Exception as exc:
        logger.warning("IQ Option change_balance(%s) falhou: %s — usando saldo atual", mode, exc)

    logger.info("IQ Option conectada (modo=%s)", mode)
    return api


def fetch_iqoption_balance() -> Decimal:
    transport = otc_transport()
    if transport == "mcp":
        balance, _ = fetch_mcp_balance(settings.iqoption_account_mode)
        return balance

    api = get_iqoption_client()
    balance = api.get_balance()
    if balance is None:
        raise ExchangeError("IQ Option retornou saldo nulo")
    return Decimal(str(balance))


def fetch_otc_capabilities() -> dict[str, Any] | None:
    if not mcp_configured():
        return None
    return fetch_mcp_capabilities()


def mcp_find_asset_id(iq_asset_name: str) -> tuple[int, str]:
    payload = mcp_call("list_assets", {"only_enabled": True})
    assets = payload.get("assets") or []
    target = iq_asset_name.strip().lower()

    for asset in assets:
        name = str(asset.get("name") or "")
        if name.lower() == target:
            return int(asset["asset_id"]), name

    for asset in assets:
        name = str(asset.get("name") or "")
        name_lower = name.lower()
        if target in name_lower or name_lower in target:
            return int(asset["asset_id"]), name

    raise ExchangeError(f"Ativo OTC indisponível na IQ Option (MCP): {iq_asset_name}")


def _parse_mcp_deadline(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


def mcp_pick_instrument(
    asset_id: int,
    direction: str,
    expiry_minutes: int,
    *,
    now: datetime | None = None,
) -> tuple[str, int]:
    mcp_direction = "call" if direction == "buy" else "put"
    payload = mcp_call("get_instruments", {"asset_id": asset_id, "direction": mcp_direction})
    windows = payload.get("instruments") or []
    target_seconds = max(60, expiry_minutes * 60)
    now = now or datetime.now(UTC)

    candidates = [
        window
        for window in windows
        if int(window.get("period_seconds") or 0) == target_seconds
    ]
    if not candidates:
        candidates = windows

    if not candidates:
        raise ExchangeError(f"Sem instrumentos MCP para asset_id={asset_id}")

    open_windows = [
        window
        for window in candidates
        if (deadline := _parse_mcp_deadline(window.get("deadline"))) is not None
        and deadline > now
    ]
    if open_windows:
        open_windows.sort(key=lambda w: str(w.get("expiration") or ""))
        window = open_windows[0]
    else:
        window = candidates[0]
    strikes = window.get("instruments") or []
    chosen = next((s for s in strikes if str(s.get("strike")) == "SPT"), None)
    if chosen is None:
        chosen = next((s for s in strikes if s.get("direction") == mcp_direction), None)
    if chosen is None:
        raise ExchangeError("Instrumento MCP sem strike SPT/direction válido")

    instrument_id = str(chosen["instrument_id"])
    instrument_index = int(window["instrument_index"])
    return instrument_id, instrument_index
