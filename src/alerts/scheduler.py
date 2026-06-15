"""Celery tasks for periodic DIVAP scanning."""

import logging

from src.alerts.trade_formatter import format_trade_opened
from src.alerts.telegram import TelegramNotifier
from src.api.push_service import notify_trade_opened
from src.bankroll.execution_context import get_execution_profile_for
from src.execution.gate import should_execute_trade
from src.execution.trade_executor import TradeExecutor
from src.analysis.llm_analyzer import LLMAnalyzer
from src.context.collector import collect_market_context
from src.core.beat_state import record_beat_heartbeat
from src.core.config import settings
from src.core.scan_metrics import ScanMetrics
from src.core.scan_plan import get_active_scan_plan, get_active_scan_plans, should_run_scan
from src.core.scan_state import get_last_scan_at, record_scan
from src.core.constants import DEFAULT_SYMBOLS, DEFAULT_TIMEFRAMES
from src.core.celery_app import celery_app
from src.core.exceptions import AnalysisError, ExchangeError
from src.data.repositories.alert_repo import AlertRepository
from src.data.repositories.candle_repo import CandleRepository
from src.data.sources.binance import BinanceSource
from src.detection.divap_scanner import DIVAPScanner
from src.markets.instruments import instrument_from_symbol

logger = logging.getLogger(__name__)

CANDLE_LIMIT = 100


def run_divap_scan(
    symbols: tuple[str, ...] | None = None,
    timeframes: tuple[str, ...] | None = None,
    use_llm: bool = True,
    notify: bool = True,
    profile_id: str | None = None,
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
    effective_profile_id = profile_id or get_active_scan_plan().profile_id
    profile, execution, meta = get_execution_profile_for(effective_profile_id)
    profile_name = profile.name if profile else effective_profile_id
    goal_protected = bool(meta.get("protected_mode", False))

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

            market_context = collect_market_context(
                symbol, timeframe, signal.direction
            )

            if alert_repo.has_recent_alert(symbol, timeframe, signal.direction):
                existing_id = alert_repo.find_recent_alert_id(
                    symbol, timeframe, signal.direction
                )
                if existing_id is None:
                    continue
                metrics.duplicates_skipped += 1
                alert_id = existing_id
                logger.info(
                    "Reusing recent alert #%s for %s %s (%s) profile %s",
                    alert_id,
                    symbol,
                    timeframe,
                    signal.direction,
                    effective_profile_id,
                )
            else:
                instrument = instrument_from_symbol(signal.symbol)
                alert_id = alert_repo.save_signal(
                    signal,
                    market_context,
                    market=instrument.market_value,
                    venue=instrument.venue_value,
                )
                metrics.signals_saved += 1
                key = f"{symbol}:{timeframe}"
                signals_found.append(key)
                logger.info("DIVAP signal detected: %s (alert #%s)", key, alert_id)

                analysis_text: str | None = None
                if use_llm and settings.openai_api_key:
                    try:
                        analysis_text = analyzer.analyze(signal, market_context)
                        alert_repo.save_analysis(
                            alert_id, analysis_text, settings.openai_model
                        )
                    except AnalysisError as exc:
                        logger.warning("LLM analysis skipped for %s: %s", key, exc)

            if settings.trading_enabled:
                trade_result = executor.try_execute(
                    signal,
                    alert_id,
                    market_context,
                    profile_id=effective_profile_id,
                )
                if trade_result.executed:
                    metrics.trades_executed += 1
                    if notify and notifier.is_configured():
                        notifier.send(
                            format_trade_opened(
                                signal,
                                trade_result,
                                profile_name=profile_name,
                            )
                        )
                    notify_trade_opened(
                        symbol=signal.symbol,
                        timeframe=signal.timeframe,
                        direction=signal.direction,
                        trade_id=trade_result.trade_id,
                    )
                elif trade_result.reason not in ("trading_disabled",):
                    metrics.record_gate_block(trade_result.reason)
            else:
                allowed, reason = should_execute_trade(
                    signal,
                    market_context,
                    settings,
                    execution,
                    goal_protected=goal_protected,
                    profile=profile,
                    candles=candles,
                )
                if not allowed:
                    metrics.record_gate_block(reason)

    return {
        "signals": len(signals_found),
        "errors": errors,
        "details": signals_found,
        "summary": metrics.to_dict(),
    }


def run_profile_scan(*, notify: bool = True) -> dict[str, int | list[str] | dict | str]:
    """Manual scan — runs all active profiles."""
    plans = get_active_scan_plans()
    combined: dict[str, int | list[str] | dict | str] = {
        "signals": 0,
        "errors": 0,
        "details": [],
        "summary": {},
        "profiles": [],
    }
    for plan in plans:
        result = run_divap_scan(
            symbols=plan.symbols,
            timeframes=plan.timeframes,
            notify=notify,
            profile_id=plan.profile_id,
        )
        record_scan(plan.profile_id, result)
        combined["signals"] = int(combined["signals"]) + int(result.get("signals", 0))
        combined["errors"] = int(combined["errors"]) + int(result.get("errors", 0))
        combined["details"] = list(combined["details"]) + list(result.get("details", []))
        combined["profiles"].append(plan.profile_id)
    combined["profile_id"] = ",".join(combined["profiles"])
    return combined


@celery_app.task(name="src.alerts.scheduler.scan_all_symbols")
def scan_all_symbols() -> dict[str, int | list[str] | dict | bool | str]:
    """Periodic scan — each active profile on its own schedule."""
    record_beat_heartbeat()
    plans = get_active_scan_plans()
    combined_signals = 0
    combined_errors = 0
    combined_details: list[str] = []
    scanned_profiles: list[str] = []
    skipped_profiles: list[str] = []

    for plan in plans:
        last_at = get_last_scan_at(plan.profile_id)
        if not should_run_scan(plan, last_at):
            skipped_profiles.append(plan.profile_id)
            logger.info(
                "Scan skipped for %s — interval %ss not elapsed",
                plan.profile_id,
                plan.interval_seconds,
            )
            continue

        logger.info(
            "Starting profile scan %s (%s) — TFs %s",
            plan.profile_id,
            plan.profile_name,
            ",".join(plan.timeframes),
        )
        result = run_divap_scan(
            symbols=plan.symbols,
            timeframes=plan.timeframes,
            profile_id=plan.profile_id,
        )
        record_scan(plan.profile_id, result)
        scanned_profiles.append(plan.profile_id)
        combined_signals += int(result.get("signals", 0))
        combined_errors += int(result.get("errors", 0))
        combined_details.extend(result.get("details", []))

    if not scanned_profiles and skipped_profiles:
        return {
            "skipped": True,
            "profile_id": ",".join(skipped_profiles),
            "signals": 0,
            "errors": 0,
            "details": [],
            "summary": {},
        }

    return {
        "skipped": False,
        "profile_id": ",".join(scanned_profiles or skipped_profiles),
        "signals": combined_signals,
        "errors": combined_errors,
        "details": combined_details,
        "summary": {},
    }
