from __future__ import annotations

import asyncio
import logging
import sys

from src.core.config import settings
from src.otc.config import load_otc_config, resolve_otc_telegram_chat_id
from src.otc.telegram_handler import process_incoming_message

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL_SECONDS = 30


async def _heartbeat_loop(client, interval: int = HEARTBEAT_INTERVAL_SECONDS) -> None:
    """Marca o listener como vivo no Redis enquanto a conexão estiver ativa."""
    from src.otc.heartbeat import record_listener_heartbeat

    while True:
        try:
            if client.is_connected():
                record_listener_heartbeat()
        except Exception:
            logger.debug("OTC heartbeat falhou", exc_info=True)
        await asyncio.sleep(interval)


async def _resolve_telethon_entity(client, source_chat: str):
    source_chat = source_chat.strip()
    if source_chat.startswith("@"):
        return await client.get_entity(source_chat)

    try:
        chat_id = int(source_chat)
    except ValueError:
        return await client.get_entity(source_chat)

    async for dialog in client.iter_dialogs(limit=200):
        if dialog.id == chat_id:
            return dialog.entity

    if str(chat_id).startswith("-100"):
        from telethon.tl.types import PeerChannel

        channel_id = int(str(chat_id)[4:])
        return await client.get_entity(PeerChannel(channel_id))

    return await client.get_entity(chat_id)


def user_listener_configured() -> bool:
    from src.tasso.config import configured as tasso_configured

    if tasso_configured():
        if (
            settings.telegram_api_id
            and settings.telegram_api_hash.strip()
            and settings.telegram_user_session.strip()
        ):
            return True

    cfg = load_otc_config()
    if not cfg.telegram.enabled or cfg.telegram.mode != "user":
        return False
    if not settings.telegram_api_id or not settings.telegram_api_hash.strip():
        return False
    if not settings.telegram_user_session.strip():
        return False
    return bool(resolve_otc_telegram_chat_id(cfg).strip())


async def run_user_listener_async() -> None:
    from telethon import TelegramClient, events
    from telethon.sessions import StringSession

    from src.tasso.telegram_handler import register_tasso_handlers

    cfg = load_otc_config()
    otc_chat_ready = (
        cfg.telegram.enabled
        and cfg.telegram.mode.strip().lower() == "user"
        and bool(resolve_otc_telegram_chat_id(cfg).strip())
    )
    session = settings.telegram_user_session.strip()
    api_id = settings.telegram_api_id
    api_hash = settings.telegram_api_hash.strip()

    client = TelegramClient(StringSession(session), api_id, api_hash)
    await client.start()

    from src.otc.heartbeat import record_listener_heartbeat

    record_listener_heartbeat()

    if otc_chat_ready:
        entity = await _resolve_telethon_entity(client, resolve_otc_telegram_chat_id(cfg))
        from telethon import utils

        resolved_chat_id = str(utils.get_peer_id(entity))
        chat_label = getattr(entity, "title", None) or getattr(
            entity, "username", resolve_otc_telegram_chat_id(cfg)
        )
        logger.info(
            "OTC Telethon listener ativo — fonte=%s (id=%s) trading=%s dry_run=%s",
            chat_label,
            resolved_chat_id,
            settings.otc_trading_enabled,
            cfg.dry_run,
        )

        @client.on(events.NewMessage(chats=entity))
        async def on_message(event: events.NewMessage.Event) -> None:
            message = event.message
            text = message.message or message.text or ""
            if not str(text).strip():
                return
            try:
                outcome = process_incoming_message(
                    str(event.chat_id),
                    str(text),
                    int(message.id),
                    source_chat_id=resolved_chat_id,
                )
            except Exception as exc:
                logger.exception("OTC Telethon processamento falhou: %s", exc)
                return
            if outcome is not None:
                logger.info("OTC Telethon dispatch: %s", outcome)

    await register_tasso_handlers(client)

    heartbeat_task = asyncio.create_task(_heartbeat_loop(client))
    try:
        await client.run_until_disconnected()
    finally:
        heartbeat_task.cancel()


def run_forever() -> None:
    logging.basicConfig(level=settings.log_level.upper())
    from src.tasso.config import configured as tasso_configured

    cfg = load_otc_config()
    if not cfg.telegram.enabled and not tasso_configured():
        logger.error("Nenhum listener Telegram habilitado (OTC ou Tasso)")
        sys.exit(1)
    if not user_listener_configured():
        logger.error(
            "Modo user: configure TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_USER_SESSION "
            "e OTC_TELEGRAM_CHAT_ID ou TASSO_TELEGRAM_ENABLED + TASSO_FINANCIAL_MOVE_BOT"
        )
        sys.exit(1)
    asyncio.run(run_user_listener_async())


if __name__ == "__main__":
    run_forever()
