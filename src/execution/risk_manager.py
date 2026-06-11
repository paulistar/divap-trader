from decimal import Decimal, ROUND_DOWN

from src.core.constants import BANK_ALLOCATION_PCT

MIN_ORDER_USDT = Decimal("10")


def allocation_pct(timeframe: str, confidence: str) -> Decimal:
    low, high = BANK_ALLOCATION_PCT.get(timeframe, (4, 6))
    if confidence == "high":
        return Decimal(high) / Decimal(100)
    midpoint = (low + high) / 2
    return Decimal(str(midpoint)) / Decimal(100)


def calculate_quote_amount(
    usdt_balance: Decimal,
    timeframe: str,
    confidence: str,
) -> Decimal:
    if usdt_balance <= 0:
        return Decimal(0)
    pct = allocation_pct(timeframe, confidence)
    amount = (usdt_balance * pct).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    return amount


def risk_reward_ratio(
    entry: Decimal,
    stop_loss: Decimal,
    target: Decimal,
) -> Decimal:
    risk = abs(entry - stop_loss)
    reward = abs(target - entry)
    if risk == 0:
        return Decimal(0)
    return (reward / risk).quantize(Decimal("0.01"))


def base_quantity_from_quote(quote_amount: Decimal, price: Decimal) -> Decimal:
    if price <= 0:
        return Decimal(0)
    return (quote_amount / price).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
