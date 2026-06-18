from __future__ import annotations

import logging
from decimal import Decimal
from functools import lru_cache
from typing import Any

from src.core.config import settings
from src.core.exceptions import ExchangeError

logger = logging.getLogger(__name__)


def iqoption_configured() -> bool:
    return bool(settings.iqoption_email.strip() and settings.iqoption_password.strip())


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


def reset_iqoption_client() -> None:
    get_iqoption_client.cache_clear()


def fetch_iqoption_balance() -> Decimal:
    api = get_iqoption_client()
    balance = api.get_balance()
    if balance is None:
        raise ExchangeError("IQ Option retornou saldo nulo")
    return Decimal(str(balance))
