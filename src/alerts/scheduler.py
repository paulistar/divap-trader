"""Celery tasks for periodic DIVAP scanning."""

import logging

from src.alerts.formatter import format_divap_alert
from src.alerts.telegram import TelegramNotifier
from src.alerts.trade_formatter import format_trade_execution
from src.execution.trade_executor import TradeExecutor
from src.analysis.llm_analyzer import LLMAnalyzer
from src.context.collector import collect_market_context
from src.core.beat_state import record_beat_heartbeat
from src.core.config import settings
from src.core.scan_state import record_scan
from src.core.constants import DEFAULT_SYMBOLS, DEFAULT_TIMEFRAMES, PRIORITY_TIMEFRAMES
from src.core.celery_app import celery_app
from src.core.exceptions import AnalysisError, ExchangeError
from src.data.repositories.alert_repo import AlertRepository
from src.data.repositories.candle_repo import CandleRepository
from src.data.sources.binance import BinanceSource
from src.detection.divap_scanner import DIVAPScanner

logger = logging.getLogger(__name__)

CANDLE_LIMIT = 100


def run_divap_scan(
    symbols: tuple[str, ...] | None = None,
    timeframes: tuple[str, ...] | None = None,
    use_llm: bool = True,
    notify: bool = True,
) -> dict[str, int | list[str]]:
    """Scan symbols/timeframes, persist alerts, optional LLM + Telegram."""
    symbols = symbols or DEFAULT_SYMBOLS
    timeframes = timeframes or DEFAULT_TIMEFRAMES

    source = BinanceSource()
    candle_repo = CandleRepository()
    alert_repo = AlertRepository()
    scanner = DIVAPScanner()
    notifier = TelegramNotifier()
    analyzer = LLMAnalyzer()
    executor = TradeExecutor()

    signals_found: list[str] = []
    errors = 0

    for symbol in symbols:
        for timeframe in timeframes:
            try:
                candles = source.fetch_ohlcv(symbol, timeframe, limit=CANDLE_LIMIT)
                candle_repo.upsert_many(candles)
                signal = scanner.scan(symbol, timeframe, candles)
            except ExchangeError as exc:
                logger.error("Scan failed %s %s: %s", symbol, timeframe, exc)
                errors += 1
                continue

            if signal is None:
                continue

            if alert_repo.has_recent_alert(symbol, timeframe, signal.direction):
                logger.info(
                    "Duplicate setup skipped %s %s (%s)",
                    symbol,
                    timeframe,
                    signal.direction,
                )
                continue

            market_context = collect_market_context(
                symbol, timeframe, signal.direction
            )

            alert_id = alert_repo.save_signal(signal, market_context)
            key = f"{symbol}:{timeframe}"
            signals_found.append(key)
            logger.info("DIVAP signal detected: %s (alert #%s)", key, alert_id)

            analysis_text: str | None = None
            if use_llm and settings.openai_api_key:
                try:
                    analysis_text = analyzer.analyze(signal, market_context)
                    alert_repo.save_analysis(alert_id, analysis_text, settings.openai_model)
                except AnalysisError as exc:
                    logger.warning("LLM analysis skipped for %s: %s", key, exc)

            if notify and notifier.is_configured():
                message = format_divap_alert(signal, analysis_text, market_context)
                notifier.send(message)

            if settings.trading_enabled:
                trade_result = executor.try_execute(signal, alert_id, market_context)
                if trade_result.executed or trade_result.reason not in (
                    "trading_disabled",
                    "confidence_below_threshold",
                ):
                    if notify and notifier.is_configured():
                        notifier.send(format_trade_execution(trade_result))

    return {
        "signals": len(signals_found),
        "errors": errors,
        "details": signals_found,
    }


@celery_app.task(name="src.alerts.scheduler.scan_all_symbols")
def scan_all_symbols() -> dict[str, int | list[str]]:
    """Periodic scan — priority timeframes first."""
    record_beat_heartbeat()
    logger.info("Starting DIVAP periodic scan")
    result = run_divap_scan(timeframes=PRIORITY_TIMEFRAMES)
    record_scan(result)
    return result
