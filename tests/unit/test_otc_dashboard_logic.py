"""Testes da lógica pura do painel OTC: travas (stop) e agregação por período."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.otc.guard import decide_stop
from src.otc.periods import (
    VALID_PERIODS,
    bucket_expr,
    current_period_predicate,
    normalize_period,
    same_period_as_ref,
)


class TestDecideStop:
    def test_no_stops_enabled_returns_none(self):
        assert (
            decide_stop(
                Decimal("100"),
                stop_win_enabled=False,
                stop_loss_enabled=False,
                daily_goal_usd=Decimal("50"),
                initial_bankroll_usd=Decimal("1000"),
                daily_stop_loss_pct=Decimal("10"),
            )
            is None
        )

    def test_stop_win_triggers_when_goal_reached(self):
        assert (
            decide_stop(
                Decimal("50"),
                stop_win_enabled=True,
                stop_loss_enabled=False,
                daily_goal_usd=Decimal("50"),
                initial_bankroll_usd=None,
                daily_stop_loss_pct=None,
                daily_stop_win_pct=None,
            )
            == "stop_win"
        )

    def test_stop_win_triggers_by_pct_of_bankroll(self):
        # 5% de 1000 = 50
        assert (
            decide_stop(
                Decimal("50"),
                stop_win_enabled=True,
                stop_loss_enabled=False,
                daily_goal_usd=None,
                initial_bankroll_usd=Decimal("1000"),
                daily_stop_loss_pct=None,
                daily_stop_win_pct=Decimal("5"),
            )
            == "stop_win"
        )

    def test_stop_win_pct_has_priority_over_usd_goal(self):
        assert (
            decide_stop(
                Decimal("40"),
                stop_win_enabled=True,
                stop_loss_enabled=False,
                daily_goal_usd=Decimal("30"),
                initial_bankroll_usd=Decimal("1000"),
                daily_stop_loss_pct=None,
                daily_stop_win_pct=Decimal("5"),
            )
            is None
        )

    def test_stop_win_not_triggered_below_goal(self):
        assert (
            decide_stop(
                Decimal("49.99"),
                stop_win_enabled=True,
                stop_loss_enabled=False,
                daily_goal_usd=Decimal("50"),
                initial_bankroll_usd=None,
                daily_stop_loss_pct=None,
                daily_stop_win_pct=None,
            )
            is None
        )

    def test_stop_loss_triggers_at_limit(self):
        # 10% de 1000 = 100 → perda de -100 dispara
        assert (
            decide_stop(
                Decimal("-100"),
                stop_win_enabled=False,
                stop_loss_enabled=True,
                daily_goal_usd=None,
                initial_bankroll_usd=Decimal("1000"),
                daily_stop_loss_pct=Decimal("10"),
                daily_stop_win_pct=None,
            )
            == "stop_loss"
        )

    def test_stop_loss_not_triggered_above_limit(self):
        assert (
            decide_stop(
                Decimal("-99.99"),
                stop_win_enabled=False,
                stop_loss_enabled=True,
                daily_goal_usd=None,
                initial_bankroll_usd=Decimal("1000"),
                daily_stop_loss_pct=Decimal("10"),
                daily_stop_win_pct=None,
            )
            is None
        )

    def test_stop_win_has_priority_over_loss(self):
        reason = decide_stop(
            Decimal("60"),
            stop_win_enabled=True,
            stop_loss_enabled=True,
            daily_goal_usd=Decimal("50"),
            initial_bankroll_usd=Decimal("1000"),
            daily_stop_loss_pct=Decimal("10"),
            daily_stop_win_pct=None,
        )
        assert reason == "stop_win"

    def test_missing_config_does_not_trigger(self):
        assert (
            decide_stop(
                Decimal("-500"),
                stop_win_enabled=True,
                stop_loss_enabled=True,
                daily_goal_usd=None,
                initial_bankroll_usd=None,
                daily_stop_loss_pct=None,
                daily_stop_win_pct=None,
            )
            is None
        )


class TestPeriods:
    def test_normalize_period_valid(self):
        for period in VALID_PERIODS:
            assert normalize_period(period) == period

    def test_normalize_period_invalid_falls_back_to_day(self):
        assert normalize_period("decade") == "day"
        assert normalize_period(None) == "day"
        assert normalize_period("") == "day"

    @pytest.mark.parametrize("period", ["day", "week", "month", "quarter", "year"])
    def test_bucket_expr_uses_date_trunc(self, period):
        expr = bucket_expr(period, "closed_at", "America/Sao_Paulo")
        assert f"date_trunc('{period}'" in expr
        assert "AT TIME ZONE 'America/Sao_Paulo'" in expr

    def test_bucket_expr_semester_is_custom(self):
        expr = bucket_expr("semester", "closed_at", "America/Sao_Paulo")
        assert "date_trunc('year'" in expr
        assert "interval '6 months'" in expr

    def test_current_period_predicate_compares_buckets(self):
        pred = current_period_predicate("month", "closed_at", "America/Sao_Paulo")
        assert "=" in pred
        assert pred.count("date_trunc('month'") == 2

    def test_same_period_as_ref_uses_parameter(self):
        pred = same_period_as_ref("day", "closed_at", "America/Sao_Paulo")
        assert "%s::timestamptz" in pred
        assert "date_trunc('day'" in pred
