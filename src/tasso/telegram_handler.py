"""Handler Telethon para Financial Move Bot (Binance Tasso)."""

from __future__ import annotations

import logging
from typing import Any

from src.tasso.config import configured, financial_move_bot_ref, load_tasso_profile_config
from src.tasso.signal_dispatch import dispatch_tasso_signal
from src.tasso.signal_parser import (
    classify_message,
    is_curto_accept_prompt,
    is_full_trade_detail,
    parse_stop_hit,
    parse_trade_details,
    resolve_profile_from_detail,
)
from src.tasso.telegram_buttons import click_accept_button, click_trade_details_button

logger = logging.getLogger(__name__)

_bot_entity_cache: Any = None


async def _resolve_bot_entity(client: Any) -> Any:
    global _bot_entity_cache
    if _bot_entity_cache is not None:
        return _bot_entity_cache
    ref = financial_move_bot_ref()
    if not ref:
        raise ValueError("TASSO_FINANCIAL_MOVE_BOT não configurado")
    _bot_entity_cache = await client.get_entity(ref)
    return _bot_entity_cache


def _sender_is_financial_move_bot(event: Any, bot_id: int | None) -> bool:
    if bot_id is None:
        return False
    sender_id = getattr(event, "sender_id", None)
    chat_id = getattr(event, "chat_id", None)
    return sender_id == bot_id or chat_id == bot_id


def _message_has_accept_buttons(message: Any) -> bool:
    markup = getattr(message, "reply_markup", None)
    if markup is None:
        return False
    for row in getattr(markup, "rows", None) or []:
        for button in getattr(row, "buttons", None) or []:
            text = str(getattr(button, "text", "") or "").lower()
            if "aceitar" in text or "recusar" in text:
                return True
    return False


def _message_has_detail_button(message: Any) -> bool:
    markup = getattr(message, "reply_markup", None)
    if markup is None:
        return False
    for row in getattr(markup, "rows", None) or []:
        for button in getattr(row, "buttons", None) or []:
            text = str(getattr(button, "text", "") or "").lower()
            if "solicitar detalhes do trade" in text or "detalhes do trade" in text:
                return True
    return False


def _message_text(message: Any) -> str:
    return str(getattr(message, "message", None) or getattr(message, "text", None) or "").strip()


async def _fetch_trade_details_via_bot(
    client: Any,
    bot_entity: Any,
    message: Any,
) -> tuple[str | None, str | None]:
    """
    Fluxo unificado do Financial Move Bot:
    1. Clicar em "Solicitar detalhes do trade no bot"
    2a. Curto: Aceitar/Recusar → Aceitar → detalhes completos
    2b. Long: detalhes completos direto
    """
    long_cfg = load_tasso_profile_config("tasso_long")
    curto_cfg = load_tasso_profile_config("tasso_curto")
    if long_cfg is None and curto_cfg is None:
        return None, None

    detail_text = long_cfg.telegram.detail_button_text if long_cfg else "Solicitar detalhes do trade no bot"
    detail_index = long_cfg.telegram.detail_button_index if long_cfg else 0
    accept_text = curto_cfg.telegram.accept_button_text if curto_cfg else "Aceitar"

    try:
        async with client.conversation(bot_entity, timeout=60) as conv:
            clicked = await click_trade_details_button(
                message,
                preferred_text=detail_text,
                fallback_index=detail_index,
            )
            if not clicked:
                return None, None

            step1 = await conv.get_response()
            step1_text = _message_text(step1)

            if is_curto_accept_prompt(step1_text) or _message_has_accept_buttons(step1):
                if not await click_accept_button(step1, preferred_text=accept_text):
                    return None, None
                step2 = await conv.get_response()
                detail = _message_text(step2)
                return detail, "tasso_curto"

            if is_full_trade_detail(step1_text):
                return step1_text, "tasso_long"

            logger.warning(
                "Tasso: resposta inesperada após solicitar detalhes: %s",
                step1_text[:200],
            )
            return None, None
    except Exception as exc:
        logger.exception("Tasso: timeout no fluxo solicitar detalhes → aceitar: %s", exc)
        return None, None


async def process_tasso_bot_message(event: Any, client: Any) -> dict | None:
    """
    Processa mensagem do Financial Move Bot 3.0.
    Retorna outcome dict ou None se não for mensagem Tasso.
    """
    if not configured():
        return None

    try:
        bot_entity = await _resolve_bot_entity(client)
    except Exception as exc:
        logger.warning("Tasso: bot não resolvido: %s", exc)
        return None

    from telethon import utils

    bot_id = utils.get_peer_id(bot_entity)
    if not _sender_is_financial_move_bot(event, bot_id):
        return None

    message = event.message
    text = str(message.message or message.text or "").strip()
    if not text:
        return None

    has_detail_btn = _message_has_detail_button(message)
    action = classify_message(text, has_detail_button=has_detail_btn)
    if action is None:
        return None

    if action.action == "close_stop_hit":
        signal = parse_stop_hit(text)
        if signal is None:
            return {"skipped": True, "reason": "stop_hit_parse_failed"}
        return dispatch_tasso_signal(signal)

    detail_text = text
    profile_id = "tasso_long"
    variant = "long"
    symbol_hint = action.symbol_hint
    direction_hint = action.direction_hint

    if action.action == "request_details":
        detail_text, profile_hint = await _fetch_trade_details_via_bot(
            client, bot_entity, message
        )
        if not detail_text or not is_full_trade_detail(detail_text):
            return {
                "skipped": True,
                "reason": "detail_flow_failed",
                "detail_preview": (detail_text or "")[:200],
            }
        profile_id, variant = resolve_profile_from_detail(detail_text)
        if profile_hint == "tasso_curto":
            profile_id, variant = "tasso_curto", "curto"

    signal = parse_trade_details(
        detail_text,
        profile_id=profile_id,
        variant=variant,
        symbol_hint=symbol_hint,
        direction_hint=direction_hint,
        raw_alert_text=text,
    )
    if signal is None:
        return {
            "skipped": True,
            "reason": "detail_parse_failed",
            "profile_id": profile_id,
            "detail_preview": detail_text[:200],
        }

    return dispatch_tasso_signal(signal)


async def register_tasso_handlers(client: Any) -> None:
    """Registra handler adicional no mesmo Telethon client (não altera OTC)."""
    if not configured():
        logger.info("Tasso Telegram desabilitado ou incompleto — handler não registrado")
        return

    from telethon import events

    try:
        bot_entity = await _resolve_bot_entity(client)
    except Exception as exc:
        logger.error("Tasso: não foi possível registrar handler: %s", exc)
        return

    @client.on(events.NewMessage(from_users=bot_entity))
    async def on_financial_move(event: events.NewMessage.Event) -> None:
        try:
            outcome = await process_tasso_bot_message(event, client)
        except Exception as exc:
            logger.exception("Tasso handler falhou: %s", exc)
            return
        if outcome is not None:
            logger.info("Tasso outcome: %s", outcome)

    logger.info("Tasso handler registrado — bot=%s", financial_move_bot_ref())
