"""Testes dos pacotes de perfil de risco (entrada + stops alinhados)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.otc.stake import (
    MARTINGALE_CYCLE_MULTIPLIER,
    resolve_profile_limits,
    stop_pcts_for_profile,
    worst_cycle_loss_pct,
)


class TestRiskProfilePackages:
    @pytest.mark.parametrize(
        ("profile", "stake", "stop_win", "stop_loss"),
        [
            ("conservative", Decimal("0.75"), Decimal("1.2"), Decimal("2.0")),
            ("moderate", Decimal("1.5"), Decimal("2.0"), Decimal("3.0")),
            ("aggressive", Decimal("2.5"), Decimal("3.5"), Decimal("5.0")),
        ],
    )
    def test_stop_pcts_match_profile(self, profile, stake, stop_win, stop_loss):
        win, loss = stop_pcts_for_profile(profile)
        limits = resolve_profile_limits(profile)
        assert limits["stake_pct"] == stake
        assert win == stop_win
        assert loss == stop_loss

    def test_daily_stop_loss_at_least_2x_entry(self):
        for profile in ("conservative", "moderate", "aggressive"):
            limits = resolve_profile_limits(profile)
            ratio = limits["daily_stop_loss_pct"] / limits["stake_pct"]
            assert ratio >= Decimal("2")

    def test_worst_cycle_formula(self):
        assert worst_cycle_loss_pct(Decimal("1.5")) == Decimal("1.5") * MARTINGALE_CYCLE_MULTIPLIER
