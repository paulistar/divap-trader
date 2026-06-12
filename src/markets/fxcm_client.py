from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from src.core.config import settings
from src.core.exceptions import ExchangeError

logger = logging.getLogger(__name__)


def fxcm_configured() -> bool:
    return bool(settings.fxcm_access_token.strip())


@lru_cache(maxsize=1)
def get_fxcm_connection() -> Any:
    token = settings.fxcm_access_token.strip()
    if not token:
        raise ExchangeError(
            "FXCM_ACCESS_TOKEN não configurado. Gere em Trading Station → "
            "User Account → Token Management."
        )
    try:
        import fxcmpy as fxcmpy_module
    except ImportError as exc:
        raise ExchangeError("Pacote fxcmpy não instalado") from exc

    server = settings.fxcm_server.strip().lower() or "demo"
    if server not in {"demo", "real"}:
        raise ExchangeError(f"FXCM_SERVER inválido: {server} (use demo ou real)")

    try:
        con = fxcmpy_module.fxcmpy(
            access_token=token,
            log_level="error",
            server=server,
        )
        con.is_connected()
        logger.info("FXCM connected (server=%s, accounts=%s)", server, con.account_ids)
        return con
    except Exception as exc:
        raise ExchangeError(f"Falha ao conectar FXCM: {exc}") from exc


def reset_fxcm_connection() -> None:
    get_fxcm_connection.cache_clear()
