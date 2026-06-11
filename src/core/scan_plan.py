"""Profile-aware scan schedule for periodic Celery scans."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from src.core.constants import DEFAULT_SYMBOLS
from src.data.repositories.bankroll_repo import BankrollRepository
from src.profiles.loader import load_profile
from src.profiles.models import TradingProfile


@dataclass(frozen=True, slots=True)
class ScanPlan:
    profile_id: str
    profile_name: str
    interval_seconds: int
    timeframes: tuple[str, ...]
    symbols: tuple[str, ...]


def _resolve_symbols(profile: TradingProfile) -> tuple[str, ...]:
    if profile.scan.symbols:
        return profile.scan.symbols
    return DEFAULT_SYMBOLS


def get_active_scan_plan() -> ScanPlan:
    repo = BankrollRepository()
    settings = repo.get_settings()
    profile = load_profile(settings.active_profile_id) or load_profile("divap")
    if profile is None:
        return ScanPlan(
            profile_id="divap",
            profile_name="DIVAP",
            interval_seconds=900,
            timeframes=("1h", "4h", "1d"),
            symbols=DEFAULT_SYMBOLS,
        )
    return ScanPlan(
        profile_id=profile.id,
        profile_name=profile.name,
        interval_seconds=profile.scan.interval_seconds,
        timeframes=profile.scan.timeframes,
        symbols=_resolve_symbols(profile),
    )


def should_run_scan(
    plan: ScanPlan,
    last_scan_at: datetime | None,
    now: datetime | None = None,
) -> bool:
    if last_scan_at is None:
        return True
    current = now or datetime.now(UTC)
    if last_scan_at.tzinfo is None:
        last_scan_at = last_scan_at.replace(tzinfo=UTC)
    elapsed = (current - last_scan_at).total_seconds()
    return elapsed >= plan.interval_seconds
