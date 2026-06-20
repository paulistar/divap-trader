from __future__ import annotations

import logging
import sys

from src.core.config import settings
from src.otc.config import load_otc_config
from src.otc.telegram_listener import listener_configured as bot_listener_configured
from src.otc.telegram_listener import run_forever as run_bot_listener
from src.otc.telegram_user_listener import (
    run_forever as run_user_listener,
    user_listener_configured,
)

logger = logging.getLogger(__name__)


def run_forever() -> None:
    logging.basicConfig(level=settings.log_level.upper())
    from src.tasso.config import configured as tasso_configured

    cfg = load_otc_config()
    if not cfg.telegram.enabled and not tasso_configured():
        logger.error("Nenhum listener Telegram habilitado (OTC ou Tasso)")
        sys.exit(1)

    mode = cfg.telegram.mode.strip().lower() if cfg.telegram.enabled else "user"
    if mode == "user":
        if user_listener_configured():
            run_user_listener()
            return
        logger.error("Modo user selecionado mas credenciais Telethon incompletas")
        sys.exit(1)

    if mode == "bot" and bot_listener_configured():
        run_bot_listener()
        return

    if tasso_configured() and user_listener_configured():
        run_user_listener()
        return

    logger.error("Listener Telegram não configurado (mode=%s)", mode)
    sys.exit(1)


if __name__ == "__main__":
    run_forever()
