from __future__ import annotations

import calendar
from datetime import UTC, datetime
from decimal import Decimal

from src.api.dashboard_service import build_market_overview
from src.data.repositories.bankroll_repo import BankrollRepository
from src.execution.binance_broker import BinanceBroker
from src.core.exceptions import ExchangeError
from src.profiles.advisor import assess_all_profiles
from src.profiles.loader import load_profile, protected_execution_profile
from src.profiles.models import ProfileExecution, TradingProfile


def get_active_execution_profile() -> tuple[TradingProfile | None, ProfileExecution, dict]:
    repo = BankrollRepository()
    settings = repo.get_settings()
    profile = load_profile(settings.active_profile_id) or load_profile("divap")
    meta = {
        "active_profile_id": settings.active_profile_id,
        "goal_reached": settings.goal_reached_at is not None,
        "goal_reached_at": settings.goal_reached_at.isoformat() if settings.goal_reached_at else None,
    }
    if settings.goal_reached_at is not None:
        if profile is None:
            execution = protected_execution_profile()
            return None, execution, meta
        protected = ProfileExecution(
            min_confidence="high",
            block_on_reject=True,
            min_risk_reward=profile.execution.min_risk_reward,
            max_open_trades=1,
            allowed_timeframes=profile.execution.allowed_timeframes,
            allocation_multiplier=Decimal("0.35"),
        )
        meta["protected_mode"] = True
        return profile, protected, meta
    if profile is None:
        execution = protected_execution_profile()
        return None, execution, meta
    return profile, profile.execution, meta


def _weeks_in_current_month() -> int:
    now = datetime.now(UTC)
    return len(calendar.monthcalendar(now.year, now.month))


def _week_of_month() -> int:
    return datetime.now(UTC).isocalendar()[1] - datetime.now(UTC).replace(day=1).isocalendar()[1] + 1


def build_bankroll_payload() -> dict:
    repo = BankrollRepository()
    settings = repo.get_settings()
    monthly_pnl = repo.monthly_pnl_usdt()
    weekly_pnl = repo.weekly_pnl_usdt()

    target = settings.monthly_target_usdt
    weekly_target: Decimal | None = None
    weekly_needed: Decimal | None = None
    progress_pct: Decimal | None = None
    goal_reached = settings.goal_reached_at is not None

    if target is not None and target > 0:
        progress_pct = ((monthly_pnl / target) * Decimal(100)).quantize(Decimal("0.1"))
        weeks = _weeks_in_current_month()
        weekly_target = (target / Decimal(weeks)).quantize(Decimal("0.01"))
        remaining = max(Decimal(0), target - monthly_pnl)
        weeks_left = max(1, weeks - _week_of_month() + 1)
        weekly_needed = (remaining / Decimal(weeks_left)).quantize(Decimal("0.01"))
        if monthly_pnl >= target and not goal_reached:
            updated = repo.mark_goal_reached()
            if updated:
                settings = updated
                goal_reached = True

    balance_usdt: Decimal | None = None
    try:
        balance_usdt = BinanceBroker().get_usdt_balance()
    except ExchangeError:
        pass

    return {
        "active_profile_id": settings.active_profile_id,
        "monthly_target_usdt": str(target) if target is not None else None,
        "monthly_pnl_usdt": str(monthly_pnl.quantize(Decimal("0.01"))),
        "weekly_pnl_usdt": str(weekly_pnl.quantize(Decimal("0.01"))),
        "weekly_target_usdt": str(weekly_target) if weekly_target is not None else None,
        "weekly_needed_usdt": str(weekly_needed) if weekly_needed is not None else None,
        "progress_pct": str(progress_pct) if progress_pct is not None else None,
        "goal_reached": goal_reached,
        "goal_reached_at": settings.goal_reached_at.isoformat() if settings.goal_reached_at else None,
        "protected_mode": goal_reached,
        "period_month": settings.period_month,
        "balance_usdt": str(balance_usdt.quantize(Decimal("0.01"))) if balance_usdt is not None else None,
    }


def build_profiles_payload() -> dict:
    repo = BankrollRepository()
    settings = repo.get_settings()
    market = build_market_overview()
    snapshots = assess_all_profiles(market, settings.active_profile_id)
    return {
        "active_profile_id": settings.active_profile_id,
        "goal_reached": settings.goal_reached_at is not None,
        "profiles": [
            {
                "id": snap.profile.id,
                "name": snap.profile.name,
                "tagline": snap.profile.tagline,
                "description": snap.profile.description,
                "is_active": snap.assessment.is_active,
                "fit_score": snap.assessment.fit_score,
                "status": snap.assessment.status,
                "headline": snap.assessment.headline,
                "detail": snap.assessment.detail,
            }
            for snap in snapshots
        ],
    }
