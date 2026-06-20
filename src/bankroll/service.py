from __future__ import annotations

import calendar
from datetime import UTC, datetime
from decimal import Decimal

from src.api.dashboard_service import build_market_overview
from src.data.repositories.bankroll_repo import BankrollRepository
from src.execution.binance_broker import BinanceBroker
from src.core.exceptions import ExchangeError
from src.profiles.advisor import assess_all_profiles


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
        "active_profile_ids": list(settings.active_profile_ids),
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


def build_profile_performance() -> list[dict]:
    from src.profiles.loader import load_binance_profiles
    from src.data.repositories.trade_repo import TradeRepository

    stats_rows = TradeRepository().profile_stats_binance()
    stats_map = {row["profile_id"]: row for row in stats_rows}
    performance: list[dict] = []

    for profile in load_binance_profiles():
        row = stats_map.get(profile.id, {})
        closed = int(row.get("closed_count") or 0)
        wins = int(row.get("wins") or 0)
        win_rate = round((wins / closed) * 100, 1) if closed else 0.0
        performance.append(
            {
                "profile_id": profile.id,
                "name": profile.name,
                "closed_count": closed,
                "open_count": int(row.get("open_count") or 0),
                "wins": wins,
                "losses": int(row.get("losses") or 0),
                "win_rate_pct": str(win_rate),
                "total_pnl_usdt": str(Decimal(str(row.get("total_pnl_usdt") or 0)).quantize(Decimal("0.01"))),
                "month_pnl_usdt": str(Decimal(str(row.get("month_pnl_usdt") or 0)).quantize(Decimal("0.01"))),
                "week_pnl_usdt": str(Decimal(str(row.get("week_pnl_usdt") or 0)).quantize(Decimal("0.01"))),
            }
        )
    return performance


def build_profile_history(limit_per_profile: int = 5) -> dict[str, list[dict]]:
    from src.profiles.loader import load_binance_profiles
    from src.data.repositories.trade_repo import TradeRepository

    repo = TradeRepository()
    history: dict[str, list[dict]] = {}
    for profile in load_binance_profiles():
        rows = repo.recent_trades_for_profile(profile.id, limit_per_profile)
        history[profile.id] = [
            {
                "id": row["id"],
                "symbol": row["symbol"],
                "timeframe": row["timeframe"],
                "direction": row["direction"],
                "status": row["status"],
                "pnl_usdt": str(row["pnl_usdt"]) if row["pnl_usdt"] is not None else None,
                "goal_protected": bool(row.get("goal_protected", False)),
                "opened_at": row["opened_at"].isoformat() if row.get("opened_at") else None,
                "closed_at": row["closed_at"].isoformat() if row.get("closed_at") else None,
            }
            for row in rows
        ]
    return history


def build_profiles_payload() -> dict:
    repo = BankrollRepository()
    settings = repo.get_settings()
    market = build_market_overview()
    snapshots = assess_all_profiles(market, settings.active_profile_ids)
    performance = {p["profile_id"]: p for p in build_profile_performance()}
    from src.invezt.store import get_dashboard_payload

    invezt_briefing = get_dashboard_payload()
    return {
        "active_profile_id": settings.active_profile_id,
        "active_profile_ids": list(settings.active_profile_ids),
        "goal_reached": settings.goal_reached_at is not None,
        "performance": list(performance.values()),
        "history": build_profile_history(),
        "invezt_briefing": invezt_briefing,
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
                "performance": performance.get(snap.profile.id),
                "ai_insight": None,
            }
            for snap in snapshots
        ],
    }


def build_profile_insights_payload() -> dict[str, str]:
    from src.invezt.store import get_dashboard_payload
    from src.profiles.llm_insights import generate_profile_insights

    repo = BankrollRepository()
    settings = repo.get_settings()
    market = build_market_overview()
    snapshots = assess_all_profiles(market, settings.active_profile_ids)
    invezt = get_dashboard_payload()
    return generate_profile_insights(
        market,
        snapshots,
        active_profile_id=settings.active_profile_id,
        goal_reached=settings.goal_reached_at is not None,
        invezt_briefing=invezt,
    )
