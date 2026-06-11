from datetime import UTC, datetime
from decimal import Decimal

from src.analysis.report_generator import build_user_message, signal_to_payload
from src.detection.divap_scanner import DIVAPCriteria, DIVAPSignal


def _signal() -> DIVAPSignal:
    return DIVAPSignal(
        symbol="ETHUSDT",
        timeframe="1h",
        direction="sell",
        confidence="medium",
        criteria=DIVAPCriteria(
            divergence=True, volume=True, fibonacci=False, pattern=False
        ),
        entry_price=Decimal("3000"),
        stop_loss=Decimal("3100"),
        targets=(Decimal("2900"),),
        current_price=Decimal("3000"),
        rsi_value=68.0,
        volume_ratio=1.2,
        divergence_type="bearish",
        pattern_detected=None,
        fibo_level=None,
        timestamp=datetime(2024, 6, 1, tzinfo=UTC),
    )


def test_signal_to_payload() -> None:
    payload = signal_to_payload(_signal())
    assert payload["symbol"] == "ETHUSDT"
    assert payload["confluence_count"] == 2
    assert payload["suggested_bank_allocation_pct"]["min"] == 4


def test_build_user_message_contains_json() -> None:
    msg = build_user_message(_signal())
    assert "ETHUSDT" in msg
    assert "```json" in msg
