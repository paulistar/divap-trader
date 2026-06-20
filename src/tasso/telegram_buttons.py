"""Clica em botões inline do Financial Move Bot."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

ACCEPT_BUTTON_KEYWORDS = ("aceitar",)
DETAIL_BUTTON_KEYWORDS = (
    "solicitar detalhes do trade",
    "detalhes do trade",
)


def _button_text(button: Any) -> str:
    return str(getattr(button, "text", "") or "")


async def click_inline_button(
    message: Any,
    *,
    preferred_text: str | None = None,
    keywords: tuple[str, ...] = (),
    fallback_index: int | None = None,
) -> bool:
    """
    Clica no primeiro botão que bater preferred_text ou keywords.
    """
    markup = getattr(message, "reply_markup", None)
    if markup is None:
        logger.warning("Tasso: mensagem sem botões inline")
        return False

    rows = getattr(markup, "rows", None) or []
    preferred_lower = (preferred_text or "").lower()

    for row in rows:
        buttons = getattr(row, "buttons", None) or []
        for col_idx, button in enumerate(buttons):
            text = _button_text(button).lower()
            if preferred_lower and preferred_lower in text:
                await message.click(col_idx)
                logger.info("Tasso: clicou botão (col=%s text=%s)", col_idx, _button_text(button))
                return True
            if any(k in text for k in keywords):
                await message.click(col_idx)
                logger.info("Tasso: clicou botão (col=%s text=%s)", col_idx, _button_text(button))
                return True

    if fallback_index is not None and rows:
        first_row = getattr(rows[0], "buttons", None) or []
        if len(first_row) > fallback_index:
            await message.click(fallback_index)
            logger.info("Tasso: clicou botão fallback index=%s", fallback_index)
            return True

    logger.warning("Tasso: nenhum botão inline encontrado")
    return False


async def click_accept_button(message: Any, *, preferred_text: str = "Aceitar") -> bool:
    return await click_inline_button(
        message,
        preferred_text=preferred_text,
        keywords=ACCEPT_BUTTON_KEYWORDS,
        fallback_index=0,
    )


async def click_trade_details_button(message: Any, *, preferred_text: str, fallback_index: int) -> bool:
    return await click_inline_button(
        message,
        preferred_text=preferred_text,
        keywords=DETAIL_BUTTON_KEYWORDS,
        fallback_index=fallback_index,
    )
