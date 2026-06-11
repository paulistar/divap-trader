from __future__ import annotations

from decimal import Decimal

from src.data.repositories.bankroll_repo import BankrollRepository
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


def get_execution_context() -> tuple[str, bool]:
    repo = BankrollRepository()
    settings = repo.get_settings()
    _, _, meta = get_active_execution_profile()
    return settings.active_profile_id, bool(meta.get("protected_mode", False))
