from __future__ import annotations

import logging
import sys
import time
from typing import Any

import httpx
import redis

from src.core.config import settings
from src.otc.config import load_otc_config, resolve_otc_telegram_chat_id
from src.otc.signal_dispatch import dispatch_otc_signal
from src.otc.signal_parser import parse_telegram_signal

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}"
POLL_TIMEOUT_SECONDS = 30
DEDUP_TTL_SECONDS = 86_400


def _redis_client() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


def _dedup_key(chat_id: str, message_id: int) -> str:
    return f"otc:telegram:msg:{chat_id}:{message_id}"


def is_duplicate_message(chat_id: str, message_id: int) -> bool:
    client = _redis_client()
    key = _dedup_key(chat_id, message_id)
    created = client.set(key, "1", nx=True, ex=DEDUP_TTL_SECONDS)
    return created is None


def extract_message(update: dict[str, Any]) -> tuple[str, str, int] | None:
    """Retorna (chat_id, text, message_id) de message ou channel_post."""
    for key in ("message", "channel_post", "edited_message", "edited_channel_post"):
        payload = update.get(key)
        if not isinstance(payload, dict):
            continue
        text = payload.get("text") or payload.get("caption")
        if not text or not str(text).strip():
            continue
        chat = payload.get("chat") or {}
        chat_id = chat.get("id")
        message_id = payload.get("message_id")
        if chat_id is None or message_id is None:
            continue
        return str(chat_id), str(text), int(message_id)
    return None


def chat_id_matches(configured: str, incoming: str) -> bool:
    configured = configured.strip()
    incoming = incoming.strip()
    if not configured:
        return False
    if configured.startswith("@"):
        return configured.lower() == incoming.lower()
    try:
        return int(configured) == int(incoming)
    except ValueError:
        return configured == incoming


def process_telegram_text(
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


def process_update(update: dict[str, Any], *, source_chat_id: str) -> dict | None:
    extracted = extract_message(update)
    if extracted is None:
        return None
    chat_id, text, message_id = extracted
    return process_telegram_text(
        chat_id,
        text,
        message_id,
        source_chat_id=source_chat_id,
    )


def load_listener_offset() -> int:
    client = _redis_client()
    raw = client.get("otc:telegram:offset")
    if raw is None:
        return 0
    try:
        return int(raw)
    except ValueError:
        return 0


def save_listener_offset(offset: int) -> None:
    _redis_client().set("otc:telegram:offset", str(offset))


def fetch_updates(token: str, offset: int) -> list[dict[str, Any]]:
    url = f"{TELEGRAM_API.format(token=token)}/getUpdates"
    params = {
        "offset": offset,
        "timeout": POLL_TIMEOUT_SECONDS,
    }
    with httpx.Client(timeout=POLL_TIMEOUT_SECONDS + 10) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram getUpdates falhou: {payload}")
    result = payload.get("result")
    return result if isinstance(result, list) else []


def listener_configured() -> bool:
    cfg = load_otc_config()
    if not cfg.telegram.enabled:
        return False
    if not settings.telegram_bot_token.strip():
        return False
    return bool(resolve_otc_telegram_chat_id(cfg).strip())


def ensure_polling_mode(token: str) -> None:
    url = f"{TELEGRAM_API.format(token=token)}/deleteWebhook"
    with httpx.Client(timeout=15.0) as client:
        response = client.post(url, json={"drop_pending_updates": False})
        response.raise_for_status()
        payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram deleteWebhook falhou: {payload}")


def run_forever() -> None:
    logging.basicConfig(level=settings.log_level.upper())

    cfg = load_otc_config()
    if not cfg.telegram.enabled:
        logger.error("otc.telegram.enabled=false — listener não iniciado")
        sys.exit(1)

    token = settings.telegram_bot_token.strip()
    source_chat_id = resolve_otc_telegram_chat_id(cfg)
    if not token or not source_chat_id:
        logger.error(
            "Configure TELEGRAM_BOT_TOKEN e OTC_TELEGRAM_CHAT_ID (ou otc.telegram.channel)"
        )
        sys.exit(1)

    ensure_polling_mode(token)

    logger.info(
        "OTC Telegram listener ativo — chat=%s trading=%s dry_run=%s",
        source_chat_id,
        settings.otc_trading_enabled,
        cfg.dry_run,
    )

    offset = load_listener_offset()
    while True:
        try:
            updates = fetch_updates(token, offset)
        except Exception as exc:
            logger.exception("OTC Telegram poll falhou: %s", exc)
            time.sleep(5)
            continue

        for update in updates:
            update_id = int(update.get("update_id", 0))
            if update_id >= offset:
                offset = update_id + 1
            try:
                outcome = process_update(update, source_chat_id=source_chat_id)
            except Exception as exc:
                logger.exception("OTC Telegram processamento falhou: %s", exc)
                continue
            if outcome is not None:
                logger.info("OTC Telegram dispatch: %s", outcome)

        if updates:
            save_listener_offset(offset)


if __name__ == "__main__":
    run_forever()
