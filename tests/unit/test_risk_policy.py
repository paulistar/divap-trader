from decimal import Decimal

from src.execution.risk_policy import effective_min_risk_reward


def test_effective_min_rr_uses_timeframe_defaults() -> None:
    assert effective_min_risk_reward("1h", Decimal("2.0"), None) == Decimal("1.2")
    assert effective_min_risk_reward("4h", Decimal("1.0"), None) == Decimal("1.5")


def test_effective_min_rr_profile_override() -> None:
    overrides = {"1h": Decimal("1.5")}
    assert effective_min_risk_reward("1h", Decimal("1.2"), overrides) == Decimal("1.5")
