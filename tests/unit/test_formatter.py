from datetime import UTC, datetime
from decimal import Decimal

from src.alerts.formatter import format_divap_alert
from src.detection.divap_scanner import DIVAPCriteria, DIVAPSignal


def _signal() -> DIVAPSignal:
    return DIVAPSignal(
        symbol="BTCUSDT",
        timeframe="4h",
        direction="buy",
        confidence="high",
        criteria=DIVAPCriteria(
            divergence=True, volume=True, fibonacci=True, pattern=True
        ),
        entry_price=Decimal("100000"),
        stop_loss=Decimal("98000"),
        targets=(Decimal("102000"), Decimal("105000")),
        current_price=Decimal("100000"),
        rsi_value=32.5,
        volume_ratio=1.8,
        divergence_type="bullish",
        pattern_detected="hammer",
        fibo_level=Decimal("1.0"),
        timestamp=datetime(2024, 6, 1, tzinfo=UTC),
    )


def test_format_divap_alert_contains_key_fields() -> None:
    message = format_divap_alert(_signal())
    assert "BTCUSDT" in message
    assert "COMPRA" in message
    assert "Divergência IFR" in message
    assert "8–12%" in message
