"""Testes da sessão diária OTC (snapshot meia-noite)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.data.repositories.otc_daily_session_repo import OtcDailySessionRecord
from src.data.repositories.otc_settings_repo import OtcSettingsRecord
from src.otc.daily_session import (
    build_session_from_balance,
    current_local_date,
    ensure_daily_session,
)


def _settings(**overrides) -> OtcSettingsRecord:
    base = OtcSettingsRecord(
        stake_usd=None,
        initial_bankroll_usd=Decimal("8000"),
        daily_goal_usd=None,
        monthly_goal_usd=None,
        daily_stop_loss_pct=Decimal("2.0"),
        daily_stop_win_pct=Decimal("1.2"),
        stop_win_enabled=True,
        stop_loss_enabled=True,
        usd_brl_rate=None,
        stake_pct=None,
        stake_min_usd=Decimal("1"),
        stake_max_usd=None,
        stake_risk_profile="moderate",
    )
    return base if not overrides else replace(base, **overrides)


class TestBuildSessionFromBalance:
    def test_computes_all_fields(self):
        session = build_session_from_balance(
            "2026-06-22",
            Decimal("8272.80"),
            _settings(),
            source="beat",
            captured_at=datetime(2026, 6, 22, 3, 0, tzinfo=UTC),
        )
        assert session.session_date == "2026-06-22"
        assert session.reference_balance_usd == Decimal("8272.80")
        assert session.base_stake_usd == Decimal("124.09")
        assert session.stop_win_usd == Decimal("165.46")
        assert session.stop_loss_usd == Decimal("248.18")
        assert session.stake_risk_profile == "moderate"
        assert session.source == "beat"


class TestEnsureDailySession:
    def test_returns_existing_session_without_fetch(self):
        existing = build_session_from_balance(
            "2026-06-22",
            Decimal("5000"),
            _settings(),
            source="beat",
        )
        repo = MagicMock()
        repo.get_for_date.return_value = existing

        result = ensure_daily_session(
            session_repo=repo,
            settings=_settings(),
            session_date="2026-06-22",
            balance_fetcher=lambda: Decimal("9999"),
        )
        assert result == existing
        repo.get_for_date.assert_called_once_with("2026-06-22")
        repo.upsert.assert_not_called()

    def test_creates_session_when_missing(self):
        repo = MagicMock()
        repo.get_for_date.return_value = None
        repo.upsert.side_effect = lambda session: session

        result = ensure_daily_session(
            session_repo=repo,
            settings=_settings(),
            session_date="2026-06-22",
            balance_fetcher=lambda: Decimal("8272.80"),
        )
        repo.upsert.assert_called_once()
        assert result.reference_balance_usd == Decimal("8272.80")
        assert result.base_stake_usd == Decimal("124.09")

    def test_fallback_to_initial_bankroll_when_fetch_fails(self):
        repo = MagicMock()
        repo.get_for_date.return_value = None
        repo.upsert.side_effect = lambda session: session

        def fail_fetch():
            raise RuntimeError("IQ offline")

        result = ensure_daily_session(
            session_repo=repo,
            settings=_settings(initial_bankroll_usd=Decimal("7500")),
            session_date="2026-06-22",
            balance_fetcher=fail_fetch,
        )
        assert result.reference_balance_usd == Decimal("7500")
        assert result.source == "fallback"


class TestCurrentLocalDate:
    @patch("src.otc.daily_session.datetime")
    def test_uses_timezone(self, mock_dt):
        from zoneinfo import ZoneInfo

        mock_dt.now.return_value = datetime(2026, 6, 22, 1, 30, tzinfo=ZoneInfo("America/Sao_Paulo"))
        assert current_local_date("America/Sao_Paulo") == "2026-06-22"
