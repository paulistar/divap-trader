from decimal import Decimal

from src.execution.risk_manager import (
    calculate_quote_amount,
    risk_reward_ratio,
    base_quantity_from_quote,
)


def test_calculate_quote_amount_high_confidence() -> None:
    balance = Decimal("10000")
    amount = calculate_quote_amount(balance, "4h", "high")
    assert amount == Decimal("1200.00")


def test_calculate_quote_amount_medium_confidence() -> None:
    balance = Decimal("10000")
    amount = calculate_quote_amount(balance, "1h", "medium")
    assert amount == Decimal("500.00")


def test_calculate_quote_amount_zero_balance() -> None:
    assert calculate_quote_amount(Decimal(0), "1h", "high") == Decimal(0)


def test_risk_reward_ratio() -> None:
    entry = Decimal("100")
    stop = Decimal("95")
    target = Decimal("110")
    assert risk_reward_ratio(entry, stop, target) == Decimal("2.00")


def test_risk_reward_below_minimum() -> None:
    entry = Decimal("100")
    stop = Decimal("95")
    target = Decimal("105")
    assert risk_reward_ratio(entry, stop, target) == Decimal("1.00")


def test_base_quantity_from_quote() -> None:
    qty = base_quantity_from_quote(Decimal("1000"), Decimal("50000"))
    assert qty == Decimal("0.02000000")
