import logging

import httpx

from src.context.models import FearGreedReading

logger = logging.getLogger(__name__)

FEAR_GREED_URL = "https://api.alternative.me/fng/?limit=1&format=json"


def fetch_fear_greed(client: httpx.Client | None = None) -> FearGreedReading | None:
    """Crypto Fear & Greed Index (Alternative.me)."""
    own_client = client is None
    http = client or httpx.Client(timeout=15.0)
    try:
        response = http.get(FEAR_GREED_URL)
        response.raise_for_status()
        payload = response.json()
        entries = payload.get("data") or []
        if not entries:
            return None
        row = entries[0]
        return FearGreedReading(
            value=int(row["value"]),
            classification=str(row.get("value_classification", "unknown")),
            timestamp=str(row.get("timestamp", "")),
        )
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        logger.warning("Fear & Greed fetch failed: %s", exc)
        return None
    finally:
        if own_client:
            http.close()
