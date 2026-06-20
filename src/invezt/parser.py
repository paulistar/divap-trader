"""Parse overviews Maia / Invezt PREMIUM."""

from __future__ import annotations

import re

from src.invezt.models import CryptoPick, ForexPick, InveztBriefing, PickBias

_FOREX_ARROW_RE = re.compile(
    r"([A-Z]{3}/[A-Z]{3})\s*[→]\s*(Compra|Venda)",
    re.IGNORECASE,
)
_FOREX_DASH_RE = re.compile(
    r"([A-Z]{3}/[A-Z]{3})\s*[—–-]\s*(COMPRA|VENDA|Compra|Venda)",
    re.IGNORECASE,
)
_FOREX_CHECK_RE = re.compile(
    r"✅\s*([A-Z]{3}/[A-Z]{3})\s*[→]\s*(Compra|Venda)",
    re.IGNORECASE,
)
_CRYPTO_LINE_RE = re.compile(
    r"🪙\s*(BTC|ETH|SOL|XRP|Bitcoin|Ethereum|Solana|XRP)\b",
    re.IGNORECASE,
)
_CRYPTO_RANK_RE = re.compile(
    r"\d+[°ºo]\s*[-–]?\s*(Solana|Ethereum|Bitcoin|XRP|BTC|ETH|SOL)\b",
    re.IGNORECASE,
)
_BIAS_BULL_RE = re.compile(r"🟢|otimista|viés\s*de\s*recuperação|continua\s+sendo\s+.*forte", re.IGNORECASE)
_BIAS_NEUT_RE = re.compile(r"🟡|neutro|cautela|consolidação|compasso\s+de\s+espera", re.IGNORECASE)
_BIAS_BEAR_RE = re.compile(r"🔴|pessimista|pressão\s+vendedora|correção", re.IGNORECASE)


def _normalize_crypto(raw: str) -> str:
    key = raw.strip().lower()
    mapping = {
        "bitcoin": "BTC",
        "btc": "BTC",
        "ethereum": "ETH",
        "eth": "ETH",
        "solana": "SOL",
        "sol": "SOL",
        "xrp": "XRP",
    }
    return mapping.get(key, raw.upper())


def _detect_kind(text: str) -> str:
    upper = text.upper()
    if "BOA NOITE" in upper or "FECHAMENTO DO MERCADO" in upper:
        return "closing"
    if "OVERVIEW FOREX" in upper or "FOREX MARKET" in upper or "💱 FOREX" in upper:
        return "forex"
    if any(
        token in upper
        for token in (
            "OVERVIEW CRIPTO",
            "OVERVIEW DO MERCADO CRIPTO",
            "PANORAMA CRIPTO",
            "CRIPTO MARKET",
            "MELHORES ENTRADAS",
            "RANKING DE MELHORES",
        )
    ):
        return "crypto"
    if "EUR/USD" in upper or "GBP/USD" in upper:
        return "forex"
    if any(sym in upper for sym in ("BTC", "BITCOIN", "ETHEREUM", "SOLANA")):
        return "crypto"
    return "unknown"


def _parse_forex(text: str) -> tuple[ForexPick, ...]:
    seen: set[str] = set()
    picks: list[ForexPick] = []
    for pattern in (_FOREX_CHECK_RE, _FOREX_ARROW_RE, _FOREX_DASH_RE):
        for match in pattern.finditer(text):
            pair = match.group(1).upper()
            if pair in seen:
                continue
            direction_raw = match.group(2).lower()
            direction = "buy" if "compra" in direction_raw else "sell"
            seen.add(pair)
            picks.append(ForexPick(pair=pair, direction=direction))  # type: ignore[arg-type]
    return tuple(picks)


def _bias_near(text: str, start: int) -> PickBias:
    window = text[start : start + 400]
    if _BIAS_BULL_RE.search(window):
        return "bullish"
    if _BIAS_BEAR_RE.search(window):
        return "bearish"
    if _BIAS_NEUT_RE.search(window):
        return "neutral"
    return "watch"


def _parse_crypto(text: str) -> tuple[CryptoPick, ...]:
    seen: set[str] = set()
    picks: list[CryptoPick] = []

    for match in _CRYPTO_LINE_RE.finditer(text):
        symbol = _normalize_crypto(match.group(1))
        if symbol in seen:
            continue
        seen.add(symbol)
        picks.append(CryptoPick(symbol=symbol, bias=_bias_near(text, match.start())))

    for match in _CRYPTO_RANK_RE.finditer(text):
        symbol = _normalize_crypto(match.group(1))
        if symbol in seen:
            continue
        seen.add(symbol)
        picks.append(CryptoPick(symbol=symbol, bias="bullish"))

    return tuple(picks)


def _extract_title(text: str) -> str:
    for line in text.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        if len(cleaned) > 8 and not cleaned.startswith("http"):
            return cleaned[:120]
    return "Briefing Invezt"


def _extract_headline(text: str) -> str | None:
    news_match = re.search(
        r"(?:Notícia de Destaque|Principal notícia|Principais notícias|Destaques da Semana)"
        r"\s*[:\n]\s*(.+?)(?:\n\n|\n🎯|\n📈|\n🔥|$)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if news_match:
        snippet = " ".join(news_match.group(1).split())
        return snippet[:280] if snippet else None
    return None


def _extract_summary(text: str) -> str | None:
    for label in (
        r"Resumo Operacional",
        r"Resumo Estratégico",
        r"Resumo",
        r"Estratégia do dia",
    ):
        match = re.search(rf"{label}\s*[:\n]\s*(.+?)(?:\n\n|☄️|Não é recomendação|$)", text, re.IGNORECASE | re.DOTALL)
        if match:
            snippet = " ".join(match.group(1).split())
            return snippet[:320] if snippet else None
    return None


def is_invezt_overview(text: str) -> bool:
    if not text or len(text.strip()) < 80:
        return False
    markers = (
        "invezt",
        "overview",
        "panorama cripto",
        "overview forex",
        "melhores entradas",
        "melhores oportunidades",
        "ranking de melhores",
        "boa noite, time da invezt",
    )
    lower = text.lower()
    return any(m in lower for m in markers)


def parse_invezt_message(text: str) -> InveztBriefing | None:
    if not is_invezt_overview(text):
        return None

    kind = _detect_kind(text)
    crypto = _parse_crypto(text)
    forex = _parse_forex(text)

    if kind == "unknown" and not crypto and not forex:
        return None

    return InveztBriefing(
        kind=kind,  # type: ignore[arg-type]
        title=_extract_title(text),
        headline=_extract_headline(text),
        strategic_summary=_extract_summary(text),
        crypto_picks=crypto,
        forex_picks=forex,
        raw_text=text,
    )
