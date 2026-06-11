"""Celery tasks for periodic DIVAP scanning."""

import logging

from src.alerts.formatter import format_divap_alert
from src.alerts.telegram import TelegramNotifier
from src.alerts.trade_formatter import format_trade_execution
from src.api.push_service import notify_high_confidence_signal
from src.bankroll.execution_context import get_active_execution_profile
from src.execution.gate import should_execute_trade
from src.execution.trade_executor import TradeExecutor
from src.analysis.llm_analyzer import LLMAnalyzer
from src.context.collector import collect_market_context
from src.core.beat_state import record_beat_heartbeat
from src.core.config import settings
from src.core.scan_metrics import ScanMetrics
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
) -> dict[str, int | list[str] | dict]:
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
    metrics = ScanMetrics()

    signals_found: list[str] = []
    errors = 0

    for symbol in symbols:
        for timeframe in timeframes:
            metrics.pairs_scanned += 1
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

            metrics.setups_detected += 1

            if alert_repo.has_recent_alert(symbol, timeframe, signal.direction):
                metrics.duplicates_skipped += 1
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
            metrics.signals_saved += 1
            key = f"{symbol}:{timeframe}"
            signals_found.append(key)
            logger.info("DIVAP signal detected: %s (alert #%s)", key, alert_id)

            if signal.confidence == "high":
                notify_high_confidence_signal(
                    symbol=signal.symbol,
                    timeframe=signal.timeframe,
                    direction=signal.direction,
                    alert_id=alert_id,
                )

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

            _, execution, meta = get_active_execution_profile()
            goal_protected = bool(meta.get("protected_mode", False))

            if settings.trading_enabled:
                trade_result = executor.try_execute(signal, alert_id, market_context)
                if trade_result.executed:
                    metrics.trades_executed += 1
                    if notify and notifier.is_configured():
                        notifier.send(format_trade_execution(trade_result))
                elif trade_result.reason not in ("trading_disabled",):
                    metrics.record_gate_block(trade_result.reason)
            else:
                allowed, reason = should_execute_trade(
                    signal,
                    market_context,
                    settings,
                    execution,
                    goal_protected=goal_protected,
                )
                if not allowed:
                    metrics.record_gate_block(reason)

    return {
        "signals": len(signals_found),
        "errors": errors,
        "details": signals_found,
        "summary": metrics.to_dict(),
    }


@celery_app.task(name="src.alerts.scheduler.scan_all_symbols")
def scan_all_symbols() -> dict[str, int | list[str] | dict]:
    """Periodic scan — priority timeframes first."""
    record_beat_heartbeat()
    logger.info("Starting DIVAP periodic scan")
    result = run_divap_scan(timeframes=PRIORITY_TIMEFRAMES)
    record_scan(result)
    return result
