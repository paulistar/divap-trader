from datetime import UTC, datetime
from decimal import Decimal

from src.context.models import MarketContext
from src.detection.divap_scanner import DIVAPCriteria, DIVAPSignal
from src.execution.gate import should_execute_trade
from src.profiles.contrarian import contrarian_setup_aligned
from src.profiles.loader import load_profile
from src.profiles.models import ProfileExecution


def _signal(direction: str = "buy") -> DIVAPSignal:
    return DIVAPSignal(
        symbol="BTCUSDT",
        timeframe="4h",
        direction=direction,
        confidence="high",
        criteria=DIVAPCriteria(True, True, True, True),
        entry_price=Decimal("100"),
        stop_loss=Decimal("95"),
        targets=(Decimal("115"),),
        current_price=Decimal("100"),
        rsi_value=35.0,
        volume_ratio=1.5,
        divergence_type="bullish" if direction == "buy" else "bearish",
        pattern_detected="hammer",
        fibo_level=Decimal("0.618"),
        timestamp=datetime.now(UTC),
    )


def _context(
    *,
    fear_greed: int | None = 50,
    htf_1d: str = "sideways",
    htf_1w: str = "sideways",
    verdict: str = "caution",
) -> MarketContext:
    return MarketContext(
        symbol="BTCUSDT",
        signal_timeframe="4h",
        fear_greed=fear_greed,
        global_market=None,
        htf_trends={"1d": htf_1d, "1w": htf_1w},
        macro_indices=(),
        news_headlines=(),
        risk_flags=(),
        context_score=55,
        context_verdict=verdict,
        sources_ok=(),
        sources_failed=(),
    )


def test_contrarian_buy_at_fear() -> None:
    ok, reason = contrarian_setup_aligned(_signal("buy"), _context(fear_greed=25))
    assert ok is True
    assert reason == "ok"


def test_contrarian_buy_rejected_in_neutral_greed() -> None:
    ok, reason = contrarian_setup_aligned(
        _signal("buy"), _context(fear_greed=60, htf_1d="bullish")
    )
    assert ok is False
    assert reason == "contrarian_buy_requires_fear_or_htf_bearish"


def test_contrarian_sell_at_greed() -> None:
    ok, reason = contrarian_setup_aligned(_signal("sell"), _context(fear_greed=75))
    assert ok is True


def test_gate_anti_divap_blocks_neutral_sentiment() -> None:
    profile = load_profile("anti_divap")
    assert profile is not None
    from unittest.mock import MagicMock

    cfg = MagicMock()
    cfg.trading_enabled = True
    cfg.trading_mode = "testnet"
    cfg.binance_use_testnet = True
    allowed, reason = should_execute_trade(
        _signal("buy"),
        _context(fear_greed=55, htf_1d="bullish", htf_1w="bullish"),
        cfg,
        profile.execution,
        profile=profile,
    )
    assert allowed is False
    assert reason == "contrarian_buy_requires_fear_or_htf_bearish"


def test_gate_anti_divap_allows_context_reject() -> None:
    profile = load_profile("anti_divap")
    assert profile is not None
    from unittest.mock import MagicMock

    cfg = MagicMock()
    cfg.trading_enabled = True
    cfg.trading_mode = "testnet"
    cfg.binance_use_testnet = True
    allowed, reason = should_execute_trade(
        _signal("sell"),
        _context(fear_greed=80, verdict="reject"),
        cfg,
        profile.execution,
        profile=profile,
    )
    assert allowed is True
    assert reason == "ok"
