from decimal import Decimal

from src.indicators.fibonacci import (
    calculate_extension_levels,
    find_nearest_extension_level,
)


def test_extension_levels_bullish_move() -> None:
    # Swing low 100 -> swing high 200, range 100
    levels = calculate_extension_levels(
        swing_low=Decimal("100"),
        swing_high=Decimal("200"),
        direction="up",
    )
    assert levels[Decimal("0.618")] == Decimal("261.8")
    assert levels[Decimal("1.0")] == Decimal("300")
    assert levels[Decimal("1.618")] == Decimal("361.8")


def test_find_nearest_extension_level() -> None:
    levels = calculate_extension_levels(
        swing_low=Decimal("100"),
        swing_high=Decimal("200"),
        direction="up",
    )
    hit = find_nearest_extension_level(
        price=Decimal("299"),
        levels=levels,
        tolerance_pct=Decimal("0.01"),
    )
    assert hit is not None
    assert hit[0] == Decimal("1.0")


def test_find_nearest_returns_none_when_far() -> None:
    levels = calculate_extension_levels(
        swing_low=Decimal("100"),
        swing_high=Decimal("200"),
        direction="up",
    )
    hit = find_nearest_extension_level(
        price=Decimal("150"),
        levels=levels,
        tolerance_pct=Decimal("0.003"),
    )
    assert hit is None
