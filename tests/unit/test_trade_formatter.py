from decimal import Decimal

from src.alerts.trade_formatter import format_trade_closed, format_trade_execution
from src.execution.trade_executor import TradeExecutionResult


def test_format_trade_execution_executed() -> None:
    result = TradeExecutionResult(
        trade_id=1,
        executed=True,
        reason="ok",
        symbol="BTCUSDT",
        direction="buy",
        quote_amount=Decimal("1200"),
        entry_price=Decimal("50000"),
        quantity=Decimal("0.024"),
    )
    message = format_trade_execution(result)
    assert "BTCUSDT" in message
    assert "executado" in message
    assert "#1" in message


def test_format_trade_closed_profit() -> None:
    message = format_trade_closed(
        trade_id=5,
        symbol="ETHUSDT",
        direction="buy",
        exit_price=Decimal("3500"),
        pnl_usdt=Decimal("120.50"),
        pnl_pct=Decimal("3.45"),
        reason="take_profit",
    )
    assert "ETHUSDT" in message
    assert "120.50" in message
    assert "Alvo atingido" in message


def test_format_trade_partial() -> None:
    from src.alerts.trade_formatter import format_trade_partial

    message = format_trade_partial(
        trade_id=8,
        symbol="BTCUSDT",
        direction="buy",
        target_index=1,
        target_total=3,
        exit_price=Decimal("65030"),
        partial_pnl_usdt=Decimal("45.20"),
        remaining_quantity=Decimal("0.02"),
    )
    assert "Alvo 1/3" in message
    assert "45.20" in message
