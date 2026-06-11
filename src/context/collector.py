import logging
from dataclasses import replace

import httpx

from src.context.fear_greed import fetch_fear_greed
from src.context.global_market import fetch_global_market
from src.context.htf_trend import fetch_htf_trends
from src.context.macro_indices import fetch_macro_indices
from src.context.models import MarketContext, MarketContextParts
from src.context.news import fetch_news_headlines
from src.context.scoring import assess_market_context
from src.core.config import settings
from src.data.sources.binance import BinanceSource

logger = logging.getLogger(__name__)


class MarketContextCollector:
    """Agrega sentimento, macro, HTF e notícias — workflow Apolo + cisne negro DIVAP."""

    def __init__(
        self,
        binance_source: BinanceSource | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._binance = binance_source or BinanceSource()
        self._http = http_client

    def collect(
        self,
        symbol: str,
        signal_timeframe: str,
        signal_direction: str = "buy",
    ) -> MarketContext:
        parts = MarketContextParts()
        ok: list[str] = []
        failed: list[str] = []

        with self._client() as http:
            fg = fetch_fear_greed(http)
            if fg:
                parts = replace(parts, fear_greed=fg)
                ok.append("fear_greed")
            else:
                failed.append("fear_greed")

            global_snap = fetch_global_market(http)
            if global_snap:
                parts = replace(parts, global_market=global_snap)
                ok.append("global_market")
            else:
                failed.append("global_market")

            macro = fetch_macro_indices(http)
            if macro:
                parts = replace(parts, macro_indices=macro)
                ok.append("macro_indices")
            else:
                failed.append("macro_indices")

            news = fetch_news_headlines(symbol, client=http)
            if news:
                parts = replace(parts, news_headlines=news)
                ok.append("news")
            else:
                failed.append("news")

        try:
            htf = fetch_htf_trends(symbol, source=self._binance)
            if htf:
                parts = replace(parts, htf_trends=htf)
                ok.append("htf_trends")
            else:
                failed.append("htf_trends")
        except Exception as exc:
            logger.warning("HTF trends collection failed: %s", exc)
            failed.append("htf_trends")

        parts = replace(parts, sources_ok=tuple(ok), sources_failed=tuple(failed))

        score, verdict, flags = assess_market_context(
            symbol=symbol,
            signal_timeframe=signal_timeframe,
            signal_direction=signal_direction,
            parts=parts,
        )

        return MarketContext(
            symbol=symbol,
            signal_timeframe=signal_timeframe,
            fear_greed=parts.fear_greed,
            global_market=parts.global_market,
            htf_trends=parts.htf_trends,
            macro_indices=parts.macro_indices,
            news_headlines=parts.news_headlines,
            risk_flags=flags,
            context_score=score,
            context_verdict=verdict,
            sources_ok=parts.sources_ok,
            sources_failed=parts.sources_failed,
        )

    def _client(self) -> httpx.Client:
        if self._http is not None:
            return _SharedClient(self._http)
        return httpx.Client(timeout=15.0)


class _SharedClient:
    """Wrapper so caller can pass an external client without closing it."""

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def __enter__(self) -> httpx.Client:
        return self._client

    def __exit__(self, *args: object) -> None:
        return None


def collect_market_context(
    symbol: str,
    signal_timeframe: str,
    signal_direction: str = "buy",
) -> MarketContext | None:
    if not settings.context_enabled:
        return None
    return MarketContextCollector().collect(symbol, signal_timeframe, signal_direction)
