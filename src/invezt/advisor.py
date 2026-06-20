"""Enriquece avaliação de perfis Binance com briefing Invezt."""

from __future__ import annotations

from src.invezt.models import InveztBriefing
from src.profiles.models import TradingProfile


def invezt_note_for_profile(profile: TradingProfile, briefing: InveztBriefing | None) -> str | None:
    if briefing is None:
        return None

    notes: list[str] = []
    volatility = profile.advisor.volatility
    picks = briefing.crypto_picks

    if picks:
        bullish = [p.symbol for p in picks if p.bias == "bullish"]
        neutral = [p.symbol for p in picks if p.bias in ("neutral", "watch")]
        if profile.id in ("tasso_curto", "scalper", "caixa_rapido", "agressivo") and bullish:
            notes.append(f"Invezt destaca momentum em {', '.join(bullish[:3])}")
        if profile.id in ("conservador", "position", "tasso_long") and bullish:
            leaders = [s for s in bullish if s in ("BTC", "ETH")]
            if leaders:
                notes.append(f"Invezt favorece líderes {', '.join(leaders)} (acumulação)")
        if volatility == "low" and len(bullish) >= 3:
            notes.append("Invezt lista várias altcoins — perfil conservador: priorize BTC/ETH")
        if not notes and neutral:
            notes.append(f"Invezt monitora {', '.join(neutral[:3])} com cautela")

    if briefing.forex_picks and profile.id not in ("otc",):
        pairs = ", ".join(f"{p.pair} ({'compra' if p.direction == 'buy' else 'venda'})" for p in briefing.forex_picks[:3])
        notes.append(f"Forex Invezt: {pairs}")

    if briefing.strategic_summary and not notes:
        notes.append(briefing.strategic_summary[:140])

    return " · ".join(notes) if notes else None


def invezt_score_adjustment(profile: TradingProfile, briefing: InveztBriefing | None) -> int:
    if briefing is None or not briefing.crypto_picks:
        return 0
    bullish_count = sum(1 for p in briefing.crypto_picks if p.bias == "bullish")
    if profile.advisor.volatility == "high" and bullish_count >= 2:
        return 4
    if profile.advisor.volatility == "low" and any(p.symbol == "BTC" and p.bias == "bullish" for p in briefing.crypto_picks):
        return 5
    if profile.id == "anti_divap" and any(p.bias == "neutral" for p in briefing.crypto_picks):
        return 3
    return 0
