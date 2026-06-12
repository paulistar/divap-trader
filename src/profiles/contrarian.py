"""Regras de alinhamento contrarian para o perfil Anti-DIVAP."""

from __future__ import annotations

from src.context.models import MarketContext
from src.detection.divap_scanner import DIVAPSignal

FEAR_THRESHOLD = 35
GREED_THRESHOLD = 65


def contrarian_setup_aligned(
    signal: DIVAPSignal,
    market_context: MarketContext | None,
) -> tuple[bool, str]:
    """
    Anti-DIVAP: entradas contra o crowd em extremos de sentimento ou exaustão HTF.

    - Compra: medo (F&G baixo) ou tendência HTF bearish (reversão de fundo)
    - Venda: euforia (F&G alto) ou tendência HTF bullish (reversão de topo)
    """
    if market_context is None:
        return False, "contrarian_no_context"

    fg = market_context.fear_greed
    htf_1d = market_context.htf_trends.get("1d", "unknown")
    htf_1w = market_context.htf_trends.get("1w", "unknown")

    if signal.direction == "buy":
        fear_ok = fg is not None and fg <= FEAR_THRESHOLD
        exhaustion_ok = htf_1d == "bearish" or htf_1w == "bearish"
        if fear_ok or exhaustion_ok:
            return True, "ok"
        return False, "contrarian_buy_requires_fear_or_htf_bearish"

    if signal.direction == "sell":
        greed_ok = fg is not None and fg >= GREED_THRESHOLD
        exhaustion_ok = htf_1d == "bullish" or htf_1w == "bullish"
        if greed_ok or exhaustion_ok:
            return True, "ok"
        return False, "contrarian_sell_requires_greed_or_htf_bullish"

    return False, "contrarian_unknown_direction"
