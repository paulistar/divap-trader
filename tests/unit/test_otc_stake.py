"""Testes de cálculo de entrada e limites da sessão diária OTC."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.otc.stake import (
    compute_session_limits,
    normalize_risk_profile,
    resolve_daily_base_stake,
    resolve_stake_from_settings,
    stake_pct_for_profile,
)


class TestRiskProfiles:
    def test_default_is_moderate(self):
        assert normalize_risk_profile(None) == "moderate"
        assert normalize_risk_profile("invalid") == "moderate"

    @pytest.mark.parametrize(
        ("profile", "expected_pct"),
        [
            ("conservative", Decimal("0.75")),
            ("moderate", Decimal("1.5")),
            ("aggressive", Decimal("2.5")),
        ],
    )
    def test_profile_operating_pct(self, profile, expected_pct):
        assert stake_pct_for_profile(profile) == expected_pct


class TestResolveDailyBaseStake:
    def test_moderate_profile_on_typical_bankroll(self):
        # 1,5% de 8272,80 ≈ 124,09
        stake = resolve_daily_base_stake(
            Decimal("8272.80"),
            stake_pct=Decimal("1.5"),
            stake_min_usd=Decimal("1"),
            stake_max_usd=Decimal("165.46"),
        )
        assert stake == Decimal("124.09")

    def test_conservative_profile(self):
        # 0,75% de 8272,80 ≈ 62,05
        stake = resolve_daily_base_stake(
            Decimal("8272.80"),
            stake_pct=Decimal("0.75"),
            stake_min_usd=Decimal("1"),
            stake_max_usd=Decimal("82.73"),
        )
        assert stake == Decimal("62.05")

    def test_respects_minimum(self):
        stake = resolve_daily_base_stake(
            Decimal("100"),
            stake_pct=Decimal("0.75"),
            stake_min_usd=Decimal("1"),
            stake_max_usd=Decimal("10"),
        )
        assert stake == Decimal("1.00")

    def test_zero_reference_raises(self):
        with pytest.raises(ValueError, match="reference"):
            resolve_daily_base_stake(
                Decimal("0"),
                stake_pct=Decimal("1.5"),
                stake_min_usd=Decimal("1"),
                stake_max_usd=Decimal("100"),
            )


class TestComputeSessionLimits:
    def test_moderate_session_from_reference(self):
        limits = compute_session_limits(
            Decimal("8272.80"),
            stake_pct=Decimal("1.5"),
            stake_min_usd=Decimal("1"),
            stake_max_usd=Decimal("165.46"),
            daily_stop_win_pct=Decimal("2.0"),
            daily_stop_loss_pct=Decimal("3.0"),
        )
        assert limits["base_stake_usd"] == Decimal("124.09")
        assert limits["stop_win_usd"] == Decimal("165.46")
        assert limits["stop_loss_usd"] == Decimal("248.18")


class TestResolveStakeFromSettings:
    def test_uses_profile_when_no_manual_pct(self):
        pct, profile = resolve_stake_from_settings(
            Decimal("8000"),
            stake_risk_profile="conservative",
            stake_pct=None,
        )
        assert profile == "conservative"
        assert pct == Decimal("0.75")
