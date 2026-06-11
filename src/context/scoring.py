from src.context.models import ContextVerdict, MarketContextParts, TrendBias

NEGATIVE_NEWS_KEYWORDS = frozenset(
    {
        "hack",
        "exploit",
        "ban",
        "lawsuit",
        "sec ",
        "crash",
        "collapse",
        "bankrupt",
        "fraud",
        "sanction",
        "war",
        "emergency",
    }
)


def assess_market_context(
    symbol: str,
    signal_timeframe: str,
    signal_direction: str,
    parts: MarketContextParts,
) -> tuple[int, ContextVerdict, tuple[str, ...]]:
    """
    Rule-based pre-score (0–100) before LLM — alinhado ao workflow Apolo/DIVAP.

    O LLM ainda faz a validação final; isto estrutura flags objetivas.
    """
    score = 50
    flags: list[str] = []

    if parts.fear_greed:
        fg = parts.fear_greed.value
        if fg <= 20:
            flags.append("extreme_fear")
            score += 5 if signal_direction == "buy" else -10
        elif fg <= 35:
            flags.append("fear")
            score += 3 if signal_direction == "buy" else -5
        elif fg >= 80:
            flags.append("extreme_greed")
            score -= 15 if signal_direction == "buy" else 5
        elif fg >= 65:
            flags.append("greed")
            score -= 8 if signal_direction == "buy" else 3

    if parts.global_market and parts.global_market.market_cap_change_24h_pct is not None:
        change = parts.global_market.market_cap_change_24h_pct
        if change <= -3:
            flags.append("crypto_market_selloff_24h")
            score -= 10
        elif change >= 3:
            flags.append("crypto_market_rally_24h")
            score += 5 if signal_direction == "buy" else -3

    htf_1d = parts.htf_trends.get("1d", "unknown")
    htf_1w = parts.htf_trends.get("1w", "unknown")
    score, flags = _apply_htf_alignment(score, flags, signal_direction, htf_1d, "1d")
    score, flags = _apply_htf_alignment(score, flags, signal_direction, htf_1w, "1w")

    if signal_timeframe in ("15m", "1h") and htf_1d == "bearish" and signal_direction == "buy":
        flags.append("ltf_buy_vs_htf_bearish")
        score -= 12
    if signal_timeframe in ("15m", "1h") and htf_1d == "bullish" and signal_direction == "sell":
        flags.append("ltf_sell_vs_htf_bullish")
        score -= 12

    for headline in parts.news_headlines:
        lower = headline.title.lower()
        if any(keyword in lower for keyword in NEGATIVE_NEWS_KEYWORDS):
            flags.append(f"negative_news:{headline.title[:60]}")
            score -= 8
            break

    dxy = next((m for m in parts.macro_indices if m.symbol == "DX-Y.NYB"), None)
    if dxy and dxy.trend == "bullish" and signal_direction == "buy":
        flags.append("strong_dollar_headwind")
        score -= 5

    score = max(0, min(100, score))
    verdict = _score_to_verdict(score, flags)
    return score, verdict, tuple(flags)


def _apply_htf_alignment(
    score: int,
    flags: list[str],
    direction: str,
    trend: TrendBias,
    label: str,
) -> tuple[int, list[str]]:
    if trend == "unknown":
        return score, flags
    if direction == "buy" and trend == "bullish":
        score += 8
        flags.append(f"htf_{label}_aligned_bullish")
    elif direction == "sell" and trend == "bearish":
        score += 8
        flags.append(f"htf_{label}_aligned_bearish")
    elif direction == "buy" and trend == "bearish":
        score -= 10
        flags.append(f"htf_{label}_conflict_bearish")
    elif direction == "sell" and trend == "bullish":
        score -= 10
        flags.append(f"htf_{label}_conflict_bullish")
    return score, flags


def _score_to_verdict(score: int, flags: list[str]) -> ContextVerdict:
    if any(f.startswith("negative_news:") for f in flags) and score < 45:
        return "reject"
    if score >= 65:
        return "confirm"
    if score >= 45:
        return "caution"
    if score < 45:
        return "reject"
    return "unknown"
