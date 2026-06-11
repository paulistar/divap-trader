import logging

import httpx

from src.context.models import MacroIndexSnapshot, TrendBias

logger = logging.getLogger(__name__)

# Proxies institucionais via ETFs/índices (Yahoo Finance chart API, somente leitura)
MACRO_TICKERS: tuple[tuple[str, str, str], ...] = (
    ("SPY", "S&P 500 (proxy)", "macro_spy"),
    ("QQQ", "Nasdaq 100 (proxy)", "macro_qqq"),
    ("DX-Y.NYB", "Dólar (DXY)", "macro_dxy"),
    ("GLD", "Ouro (proxy)", "macro_gold"),
)

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"


def fetch_macro_indices(client: httpx.Client | None = None) -> tuple[MacroIndexSnapshot, ...]:
    own_client = client is None
    http = client or httpx.Client(timeout=15.0)
    results: list[MacroIndexSnapshot] = []

    try:
        for ticker, label, _ in MACRO_TICKERS:
            snapshot = _fetch_yahoo_snapshot(http, ticker, label)
            if snapshot is not None:
                results.append(snapshot)
    finally:
        if own_client:
            http.close()

    return tuple(results)


def _fetch_yahoo_snapshot(
    http: httpx.Client,
    ticker: str,
    label: str,
) -> MacroIndexSnapshot | None:
    try:
        response = http.get(
            YAHOO_CHART_URL.format(ticker=ticker),
            params={"interval": "1d", "range": "5d"},
            headers={"User-Agent": "DIVAP-Trader/1.0"},
        )
        response.raise_for_status()
        result = response.json()["chart"]["result"][0]
        closes = result["indicators"]["quote"][0]["close"]
        valid = [c for c in closes if c is not None]
        if len(valid) < 2:
            return None

        first, last = valid[0], valid[-1]
        change_pct = ((last - first) / first) * 100 if first else None
        trend = _trend_from_change(change_pct)

        return MacroIndexSnapshot(
            symbol=ticker,
            label=label,
            change_5d_pct=round(change_pct, 2) if change_pct is not None else None,
            trend=trend,
        )
    except (httpx.HTTPError, KeyError, TypeError, IndexError, ValueError) as exc:
        logger.warning("Macro index fetch failed %s: %s", ticker, exc)
        return None


def _trend_from_change(change_pct: float | None) -> TrendBias:
    if change_pct is None:
        return "unknown"
    if change_pct > 0.5:
        return "bullish"
    if change_pct < -0.5:
        return "bearish"
    return "sideways"
