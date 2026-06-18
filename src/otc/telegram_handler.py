from __future__ import annotations

import logging

from src.otc.signal_dispatch import dispatch_otc_signal
from src.otc.signal_parser import parse_telegram_signal
from src.otc.telegram_dedup import is_duplicate_message
from src.otc.telegram_utils import chat_id_matches

logger = logging.getLogger(__name__)


def process_incoming_message(
    chat_id: str,
    text: str,
    message_id: int,
    *,
    source_chat_id: str,
    dedup: bool = True,
) -> dict | None:
    if not chat_id_matches(source_chat_id, chat_id):
        return None
    if dedup and is_duplicate_message(chat_id, message_id):
        logger.debug("OTC Telegram ignorando duplicata chat=%s msg=%s", chat_id, message_id)
        return None

    signal = parse_telegram_signal(text)
    if signal is None:
        return None

    logger.info(
        "OTC Telegram sinal detectado chat=%s msg=%s asset=%s entrada=%s",
        chat_id,
        message_id,
        signal.asset,
        signal.entry_time.strftime("%H:%M") if signal.entry_time else "?",
    )
    return dispatch_otc_signal(signal)
