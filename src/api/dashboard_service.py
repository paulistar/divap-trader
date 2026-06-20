"""Aggregations and helpers for the web dashboard."""

from __future__ import annotations

import logging
from dataclasses import replace
from decimal import Decimal

import httpx

from src.context.fear_greed import fetch_fear_greed
from src.context.global_market import fetch_global_market
from src.context.htf_trend import fetch_htf_trends
from src.context.models import MarketContext, MarketContextParts
from src.context.scoring import assess_market_context
from src.core.constants import DEFAULT_SYMBOLS
from src.core.dashboard_cache import (
    BALANCE_CACHE_KEY,
    BALANCE_TTL_SECONDS,
    MARKET_CACHE_KEY,
    MARKET_TTL_SECONDS,
    cache_get,
    cache_set,
)
from src.core.exceptions import ExchangeError
from src.core.scan_state import get_scan_status
from src.core.config import settings
from src.data.repositories.alert_repo import AlertRecord
from src.data.repositories.trade_repo import TradeRepository
from src.detection.divap_scanner import DIVAPCriteria, DIVAPSignal
from src.execution.binance_broker import BinanceBroker
from src.execution.gate import should_execute_trade

logger = logging.getLogger(__name__)


def fetch_testnet_balance() -> dict | None:
    if not settings.binance_use_testnet:
        return None
    cached = cache_get(BALANCE_CACHE_KEY)
    if cached is not None:
        return cached
    try:
        broker = BinanceBroker()
        usdt = broker.get_usdt_balance()
        payload = {"usdt_free": str(usdt.quantize(Decimal("0.01")))}
        cache_set(BALANCE_CACHE_KEY, payload, BALANCE_TTL_SECONDS)
        return payload
    except ExchangeError:
        return None


def build_market_overview() -> dict:
    cached = cache_get(MARKET_CACHE_KEY)
    if cached is not None:
        return cached

    fear_greed_value: int | None = None
    btc_dominance: float | None = None
    market_change_24h: float | None = None
    scores: list[int] = []
    verdicts: list[str] = []
    shared = MarketContextParts()

    try:
        with httpx.Client(timeout=10.0) as http:
            fg = fetch_fear_greed(http)
            if fg:
                shared = replace(shared, fear_greed=fg)
                fear_greed_value = fg.value
            global_snap = fetch_global_market(http)
            if global_snap:
                shared = replace(shared, global_market=global_snap)
                btc_dominance = global_snap.btc_dominance_pct
                market_change_24h = global_snap.market_cap_change_24h_pct
    except Exception as exc:
        logger.warning("Market overview shared fetch failed: %s", exc)

    for symbol in DEFAULT_SYMBOLS[:4]:
        try:
            htf = fetch_htf_trends(symbol)
            sym_parts = replace(shared, htf_trends=htf or {})
            score, verdict, _ = assess_market_context(
                symbol=symbol,
                signal_timeframe="4h",
                signal_direction="buy",
                parts=sym_parts,
            )
            scores.append(score)
            verdicts.append(verdict)
        except Exception as exc:
            logger.warning("Market overview score failed for %s: %s", symbol, exc)

    avg_score = round(sum(scores) / len(scores)) if scores else None
    verdict_rank = {"confirm": 3, "caution": 2, "reject": 1, "unknown": 0}
    dominant_verdict = max(verdicts, key=lambda v: verdict_rank.get(v, 0)) if verdicts else "unknown"

    payload = {
        "fear_greed": fear_greed_value,
        "btc_dominance_pct": btc_dominance,
        "market_cap_change_24h_pct": market_change_24h,
        "avg_context_score": avg_score,
        "dominant_verdict": dominant_verdict,
    }
    cache_set(MARKET_CACHE_KEY, payload, MARKET_TTL_SECONDS)
    return payload


def execution_reason_for_alert(alert: AlertRecord) -> str:
    if not settings.trading_enabled:
        return "Trading desligado"

    min_conf = settings.trading_min_confidence.lower()
    if min_conf == "high" and alert.confidence != "high":
        return "Não opera — confiança média"

    verdict = alert.context_verdict or "unknown"
    if settings.trading_block_on_context_reject and verdict == "reject":
        return "Bloqueado — contexto reject"

    if alert.confidence == "high" and verdict == "caution":
        return "Aguardando gates"

    signal = _alert_to_signal(alert)
    if signal:
        allowed, reason = should_execute_trade(signal, _alert_to_context(alert))
        if not allowed and reason not in ("trading_disabled", "confidence_below_threshold", "context_reject"):
            return f"Gate: {reason.replace('_', ' ')}"
        if allowed:
            return "Elegível para execução"

    if alert.confidence == "high":
        return "Alta confiança — aguardando setup"
    return "Monitorando"


def _alert_to_signal(alert: AlertRecord) -> DIVAPSignal | None:
    if alert.entry_price is None or alert.stop_loss is None:
        return None
    targets = alert.targets or []
    if not targets:
        return None
    from datetime import UTC, datetime

    criteria = alert.criteria or {}
    return DIVAPSignal(
        symbol=alert.symbol,
        timeframe=alert.timeframe,
        direction=alert.direction,
        confidence=alert.confidence,
        criteria=DIVAPCriteria(
            divergence=bool(criteria.get("divergence")),
            volume=bool(criteria.get("volume")),
            fibonacci=bool(criteria.get("fibonacci")),
            pattern=bool(criteria.get("pattern")),
        ),
        entry_price=Decimal(str(alert.entry_price)),
        stop_loss=Decimal(str(alert.stop_loss)),
        targets=tuple(Decimal(str(t)) for t in targets),
        current_price=Decimal(str(alert.entry_price)),
        rsi_value=float(alert.rsi_value or 0),
        volume_ratio=float(alert.volume_ratio or 0),
        divergence_type=alert.divergence_type or "",
        pattern_detected=alert.pattern_detected,
        fibo_level=Decimal(str(alert.fibo_level)) if alert.fibo_level else None,
        timestamp=alert.created_at or datetime.now(UTC),
    )


def _alert_to_context(alert: AlertRecord) -> MarketContext | None:
    if alert.context_score is None and not alert.context_verdict:
        return None
    from src.context.models import MarketContext

    htf: dict[str, str] = {}
    if alert.htf_1d:
        htf["1d"] = alert.htf_1d
    if alert.htf_1w:
        htf["1w"] = alert.htf_1w

    fg = None
    if alert.fear_greed is not None:
        from src.context.models import FearGreedReading

        fg = FearGreedReading(alert.fear_greed, "", "")

    return MarketContext(
        symbol=alert.symbol,
        signal_timeframe=alert.timeframe,
        fear_greed=fg,
        global_market=None,
        htf_trends=htf,
        macro_indices=(),
        news_headlines=(),
        risk_flags=(),
        context_score=alert.context_score or 0,
        context_verdict=alert.context_verdict or "unknown",
        sources_ok=(),
        sources_failed=(),
    )


def alert_to_dashboard_dict(alert: AlertRecord) -> dict:
    from src.api.routes.alerts import _alert_to_dict

    data = _alert_to_dict(alert)
    data["execution_reason"] = execution_reason_for_alert(alert)
    return data


def get_scan_status_payload() -> dict:
    return get_scan_status()


def build_pnl_series(limit: int = 100) -> list[dict]:
    repo = TradeRepository()
    rows = repo.binance_pnl_history(limit)
    cumulative = Decimal(0)
    series: list[dict] = []
    for row in rows:
        pnl = Decimal(str(row["pnl_usdt"] or 0))
        cumulative += pnl
        closed = row["closed_at"]
        series.append(
            {
                "trade_id": row["id"],
                "closed_at": closed.isoformat() if closed else None,
                "pnl_usdt": str(pnl),
                "cumulative_usdt": str(cumulative.quantize(Decimal("0.01"))),
            }
        )
    return series
