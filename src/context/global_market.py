import logging

import httpx

from src.context.models import GlobalMarketSnapshot

logger = logging.getLogger(__name__)

COINGECKO_GLOBAL_URL = "https://api.coingecko.com/api/v3/global"


def fetch_global_market(client: httpx.Client | None = None) -> GlobalMarketSnapshot | None:
    """BTC dominance and total market cap change (CoinGecko, free)."""
    own_client = client is None
    http = client or httpx.Client(timeout=15.0)
    try:
        response = http.get(COINGECKO_GLOBAL_URL)
        response.raise_for_status()
        data = response.json().get("data") or {}
        return GlobalMarketSnapshot(
            btc_dominance_pct=_as_float(data.get("market_cap_percentage", {}).get("btc")),
            market_cap_change_24h_pct=_as_float(
                data.get("market_cap_change_percentage_24h_usd")
            ),
            total_market_cap_usd=_as_float(data.get("total_market_cap", {}).get("usd")),
        )
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        logger.warning("Global market fetch failed: %s", exc)
        return None
    finally:
        if own_client:
            http.close()


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
