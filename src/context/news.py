import logging
import xml.etree.ElementTree as ET

import httpx

from src.context.models import NewsHeadline
from src.core.config import settings

logger = logging.getLogger(__name__)

COINDESK_RSS_URL = "https://www.coindesk.com/arc/outboundfeeds/rss"
CRYPTOPANIC_URL = "https://cryptopanic.com/api/v1/posts/"


def fetch_news_headlines(
    symbol: str,
    limit: int | None = None,
    client: httpx.Client | None = None,
) -> tuple[NewsHeadline, ...]:
    """Headlines from CryptoPanic (if key) or CoinDesk RSS fallback."""
    max_items = limit or settings.context_news_limit
    currency = _symbol_to_currency(symbol)

    if settings.cryptopanic_api_key:
        headlines = _fetch_cryptopanic(currency, max_items)
        if headlines:
            return headlines

    return _fetch_coindesk_rss(max_items, client)


def _symbol_to_currency(symbol: str) -> str:
    normalized = symbol.upper().replace("/", "")
    if normalized.endswith("USDT"):
        return normalized[:-4]
    return normalized


def _fetch_cryptopanic(currency: str, limit: int) -> tuple[NewsHeadline, ...]:
    try:
        with httpx.Client(timeout=15.0) as http:
            response = http.get(
                CRYPTOPANIC_URL,
                params={
                    "auth_token": settings.cryptopanic_api_key,
                    "currencies": currency,
                    "filter": "important",
                    "public": "true",
                },
            )
            response.raise_for_status()
            rows = response.json().get("results") or []
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        logger.warning("CryptoPanic fetch failed: %s", exc)
        return ()

    headlines: list[NewsHeadline] = []
    for row in rows[:limit]:
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        source_name = "CryptoPanic"
        source = row.get("source") or {}
        if isinstance(source, dict) and source.get("title"):
            source_name = str(source["title"])
        headlines.append(
            NewsHeadline(
                title=title,
                source=source_name,
                published_at=str(row.get("published_at") or ""),
                url=str(row.get("url") or "") or None,
            )
        )
    return tuple(headlines)


def _fetch_coindesk_rss(
    limit: int,
    client: httpx.Client | None = None,
) -> tuple[NewsHeadline, ...]:
    own_client = client is None
    http = client or httpx.Client(timeout=15.0)
    try:
        response = http.get(
            COINDESK_RSS_URL,
            headers={"User-Agent": "DIVAP-Trader/1.0"},
            follow_redirects=True,
        )
        response.raise_for_status()
        root = ET.fromstring(response.text)
        items = root.findall(".//item")
        headlines: list[NewsHeadline] = []
        for item in items[:limit]:
            title_el = item.find("title")
            link_el = item.find("link")
            pub_el = item.find("pubDate")
            title = (title_el.text or "").strip() if title_el is not None else ""
            if not title:
                continue
            headlines.append(
                NewsHeadline(
                    title=title,
                    source="CoinDesk",
                    published_at=pub_el.text if pub_el is not None else None,
                    url=link_el.text if link_el is not None else None,
                )
            )
        return tuple(headlines)
    except (httpx.HTTPError, ET.ParseError) as exc:
        logger.warning("CoinDesk RSS fetch failed: %s", exc)
        return ()
    finally:
        if own_client:
            http.close()
