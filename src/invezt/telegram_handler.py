"""Handler Telethon para canal Maia / Invezt PREMIUM."""

from __future__ import annotations

import logging
from typing import Any

from src.invezt.config import chat_ref, configured
from src.invezt.parser import is_invezt_overview, parse_invezt_message
from src.invezt.store import save_briefing

logger = logging.getLogger(__name__)

_entity_cache: Any = None


async def _resolve_invezt_entity(client: Any) -> Any:
    global _entity_cache
    if _entity_cache is not None:
        return _entity_cache

    ref = chat_ref().strip()
    if ref:
        if ref.startswith("@"):
            _entity_cache = await client.get_entity(ref)
            return _entity_cache
        try:
            chat_id = int(ref)
        except ValueError:
            _entity_cache = await client.get_entity(ref)
            return _entity_cache

        async for dialog in client.iter_dialogs(limit=300):
            if dialog.id == chat_id:
                _entity_cache = dialog.entity
                logger.info("Invezt: canal resolvido por ID — %s", dialog.title or dialog.name)
                return _entity_cache

        if str(chat_id).startswith("-100"):
            from telethon.tl.types import PeerChannel

            channel_id = int(str(chat_id)[4:])
            _entity_cache = await client.get_entity(PeerChannel(channel_id))
            return _entity_cache

        _entity_cache = await client.get_entity(chat_id)
        return _entity_cache

    keywords = ("maia", "invezt", "premium")
    async for dialog in client.iter_dialogs(limit=300):
        title = (dialog.title or dialog.name or "").lower()
        if any(k in title for k in keywords):
            logger.info("Invezt: canal encontrado por título — %s", dialog.title or dialog.name)
            _entity_cache = dialog.entity
            return _entity_cache

    raise ValueError(
        "Canal Invezt/Maia não encontrado. Configure INVEZT_TELEGRAM_CHAT_REF com @ ou ID."
    )


async def process_invezt_message(event: Any) -> dict | None:
    if not configured():
        return None

    message = event.message
    text = str(message.message or message.text or "").strip()
    if not text or not is_invezt_overview(text):
        return None

    briefing = parse_invezt_message(text)
    if briefing is None:
        return {"skipped": True, "reason": "parse_failed"}

    save_briefing(briefing)
    logger.info(
        "Invezt briefing salvo kind=%s crypto=%s forex=%s",
        briefing.kind,
        len(briefing.crypto_picks),
        len(briefing.forex_picks),
    )
    return {
        "stored": True,
        "kind": briefing.kind,
        "crypto_picks": len(briefing.crypto_picks),
        "forex_picks": len(briefing.forex_picks),
        "title": briefing.title,
    }


async def register_invezt_handlers(client: Any) -> None:
    if not configured():
        logger.info("Invezt Telegram desabilitado — handler não registrado")
        return

    from telethon import events

    try:
        entity = await _resolve_invezt_entity(client)
    except Exception as exc:
        logger.error("Invezt: não foi possível registrar handler: %s", exc)
        return

    label = getattr(entity, "title", None) or getattr(entity, "username", chat_ref() or "invezt")

    @client.on(events.NewMessage(chats=entity))
    async def on_invezt(event: events.NewMessage.Event) -> None:
        try:
            outcome = await process_invezt_message(event)
        except Exception as exc:
            logger.exception("Invezt handler falhou: %s", exc)
            return
        if outcome is not None:
            logger.info("Invezt outcome: %s", outcome)

    logger.info("Invezt handler registrado — fonte=%s", label)
