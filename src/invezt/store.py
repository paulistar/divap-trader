"""Persistência Redis dos briefings Invezt."""

from __future__ import annotations

from datetime import UTC, datetime

from src.core.dashboard_cache import cache_get, cache_set
from src.invezt.models import CryptoPick, ForexPick, InveztBriefing

INVEZT_LATEST_KEY = "divap:invezt:latest"
INVEZT_CRYPTO_KEY = "divap:invezt:crypto"
INVEZT_FOREX_KEY = "divap:invezt:forex"
INVEZT_TTL_SECONDS = 7 * 24 * 3600


def _briefing_from_dict(data: dict) -> InveztBriefing:
    crypto = tuple(
        CryptoPick(
            symbol=str(p["symbol"]),
            bias=p.get("bias", "watch"),  # type: ignore[arg-type]
            note=p.get("note"),
        )
        for p in data.get("crypto_picks") or []
    )
    forex = tuple(
        ForexPick(
            pair=str(p["pair"]),
            direction=p.get("direction", "buy"),  # type: ignore[arg-type]
            note=p.get("note"),
        )
        for p in data.get("forex_picks") or []
    )
    return InveztBriefing(
        kind=data.get("kind", "unknown"),  # type: ignore[arg-type]
        title=str(data.get("title") or "Briefing Invezt"),
        headline=data.get("headline"),
        strategic_summary=data.get("strategic_summary"),
        crypto_picks=crypto,
        forex_picks=forex,
        raw_text=str(data.get("raw_excerpt") or ""),
        source_label=str(data.get("source_label") or "Maia / Invezt"),
    )


def _briefing_to_dict(briefing: InveztBriefing) -> dict:
    payload = briefing.to_dict()
    payload["received_at"] = datetime.now(UTC).isoformat()
    payload["raw_excerpt"] = briefing.raw_text[:1200]
    return payload


def save_briefing(briefing: InveztBriefing) -> None:
    payload = _briefing_to_dict(briefing)
    cache_set(INVEZT_LATEST_KEY, payload, INVEZT_TTL_SECONDS)
    if briefing.kind == "crypto" or briefing.crypto_picks:
        cache_set(INVEZT_CRYPTO_KEY, payload, INVEZT_TTL_SECONDS)
    if briefing.kind == "forex" or briefing.forex_picks:
        cache_set(INVEZT_FOREX_KEY, payload, INVEZT_TTL_SECONDS)


def get_latest_briefing() -> dict | None:
    return cache_get(INVEZT_LATEST_KEY)


def get_crypto_briefing() -> dict | None:
    return cache_get(INVEZT_CRYPTO_KEY) or cache_get(INVEZT_LATEST_KEY)


def get_dashboard_payload() -> dict | None:
    latest = get_latest_briefing()
    if latest is None:
        return None
    crypto = get_crypto_briefing()
    forex = cache_get(INVEZT_FOREX_KEY)
    return {
        "latest": latest,
        "crypto": crypto,
        "forex": forex,
    }


def briefing_for_advisor() -> InveztBriefing | None:
    data = get_crypto_briefing() or get_latest_briefing()
    if not data:
        return None
    return _briefing_from_dict(data)
