from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

from src.context.models import MarketContext
from src.detection.divap_scanner import DIVAPCriteria, DIVAPSignal
from src.execution.gate import should_execute_trade


def _signal(
    confidence: str = "high",
    entry: str = "100",
    stop: str = "95",
    target: str = "110",
) -> DIVAPSignal:
    return DIVAPSignal(
        symbol="BTCUSDT",
        timeframe="4h",
        direction="buy",
        confidence=confidence,
        criteria=DIVAPCriteria(True, True, True, True),
        entry_price=Decimal(entry),
        stop_loss=Decimal(stop),
        targets=(Decimal(target),),
        current_price=Decimal(entry),
        rsi_value=35.0,
        volume_ratio=1.5,
        divergence_type="bullish",
        pattern_detected="hammer",
        fibo_level=Decimal("0.618"),
        timestamp=datetime.now(UTC),
    )


def _context(verdict: str = "confirm") -> MarketContext:
    return MarketContext(
        symbol="BTCUSDT",
        signal_timeframe="4h",
        fear_greed=None,
        global_market=None,
        htf_trends={},
        macro_indices=(),
        news_headlines=(),
        risk_flags=(),
        context_score=70,
        context_verdict=verdict,
        sources_ok=(),
        sources_failed=(),
    )


def test_gate_blocks_when_trading_disabled() -> None:
    cfg = MagicMock()
    cfg.trading_enabled = False
    allowed, reason = should_execute_trade(_signal(), _context(), cfg)
    assert allowed is False
    assert reason == "trading_disabled"


def test_gate_blocks_medium_when_min_high() -> None:
    cfg = MagicMock()
    cfg.trading_enabled = True
    cfg.trading_mode = "testnet"
    cfg.binance_use_testnet = True
    cfg.trading_min_confidence = "high"
    cfg.trading_block_on_context_reject = True
    allowed, reason = should_execute_trade(_signal(confidence="medium"), _context(), cfg)
    assert allowed is False
    assert reason == "confidence_below_threshold"


def test_gate_blocks_context_reject() -> None:
    cfg = MagicMock()
    cfg.trading_enabled = True
    cfg.trading_mode = "testnet"
    cfg.binance_use_testnet = True
    cfg.trading_min_confidence = "high"
    cfg.trading_block_on_context_reject = True
    allowed, reason = should_execute_trade(_signal(), _context("reject"), cfg)
    assert allowed is False
    assert reason == "context_reject"


def test_gate_blocks_low_rr() -> None:
    cfg = MagicMock()
    cfg.trading_enabled = True
    cfg.trading_mode = "testnet"
    cfg.binance_use_testnet = True
    cfg.trading_min_confidence = "high"
    cfg.trading_block_on_context_reject = True
    allowed, reason = should_execute_trade(
        _signal(entry="100", stop="95", target="105"), _context(), cfg
    )
    assert allowed is False
    assert reason.startswith("rr_below_minimum")


def test_gate_allows_valid_setup() -> None:
    cfg = MagicMock()
    cfg.trading_enabled = True
    cfg.trading_mode = "testnet"
    cfg.binance_use_testnet = True
    cfg.trading_min_confidence = "high"
    cfg.trading_block_on_context_reject = True
    allowed, reason = should_execute_trade(_signal(), _context("confirm"), cfg)
    assert allowed is True
    assert reason == "ok"
