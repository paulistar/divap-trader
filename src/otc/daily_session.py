"""Sessão diária OTC — snapshot à meia-noite (America/Sao_Paulo).

Trava banca de referência, stops e entrada L0 para o dia inteiro.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from src.data.repositories.otc_daily_session_repo import (
    OtcDailySessionRecord,
    OtcDailySessionRepository,
)
from src.data.repositories.otc_settings_repo import OtcSettingsRecord
from src.otc.periods import DEFAULT_TIMEZONE
from src.otc.stake import (
    compute_session_limits,
    resolve_stake_from_settings,
    stake_max_usd_for_profile,
    stop_pcts_for_profile,
)

logger = logging.getLogger(__name__)

DEFAULT_STAKE_MIN_USD = Decimal("1.00")


def current_local_date(timezone: str = DEFAULT_TIMEZONE) -> str:
    return datetime.now(ZoneInfo(timezone)).strftime("%Y-%m-%d")


def build_session_from_balance(
    session_date: str,
    reference_balance_usd: Decimal,
    settings: OtcSettingsRecord,
    *,
    source: str,
    captured_at: datetime | None = None,
) -> OtcDailySessionRecord:
    stake_pct, profile = resolve_stake_from_settings(
        reference_balance_usd,
        stake_risk_profile=settings.stake_risk_profile,
        stake_pct=settings.stake_pct,
    )
    stake_min = settings.stake_min_usd or DEFAULT_STAKE_MIN_USD
    stake_max = settings.stake_max_usd or stake_max_usd_for_profile(
        reference_balance_usd, profile
    )
    stop_win_pct, stop_loss_pct = stop_pcts_for_profile(profile)

    limits = compute_session_limits(
        reference_balance_usd,
        stake_pct=stake_pct,
        stake_min_usd=stake_min,
        stake_max_usd=stake_max,
        daily_stop_win_pct=stop_win_pct,
        daily_stop_loss_pct=stop_loss_pct,
    )
    return OtcDailySessionRecord(
        session_date=session_date,
        reference_balance_usd=limits["reference_balance_usd"],
        base_stake_usd=limits["base_stake_usd"],
        stop_win_usd=limits["stop_win_usd"],
        stop_loss_usd=limits["stop_loss_usd"],
        stake_pct=stake_pct,
        stop_win_pct=stop_win_pct,
        stop_loss_pct=stop_loss_pct,
        stake_risk_profile=profile,
        source=source,
        captured_at=captured_at or datetime.now(UTC),
    )


def resolve_reference_balance(
    settings: OtcSettingsRecord,
    balance_fetcher: Callable[[], Decimal],
    session_repo: OtcDailySessionRepository,
) -> tuple[Decimal, str]:
    try:
        balance = balance_fetcher()
        if balance > 0:
            return balance, "live"
    except Exception as exc:
        logger.warning("Falha ao obter saldo IQ para snapshot OTC: %s", exc)

    if settings.initial_bankroll_usd and settings.initial_bankroll_usd > 0:
        return settings.initial_bankroll_usd, "fallback"

    last = session_repo.get_latest()
    if last and last.reference_balance_usd > 0:
        return last.reference_balance_usd, "fallback"

    raise RuntimeError("Não foi possível determinar banca de referência para sessão OTC")


def ensure_daily_session(
    *,
    session_repo: OtcDailySessionRepository | None = None,
    settings: OtcSettingsRecord,
    session_date: str,
    balance_fetcher: Callable[[], Decimal],
) -> OtcDailySessionRecord:
    """Retorna sessão do dia, criando snapshot lazy se ainda não existir."""
    repo = session_repo or OtcDailySessionRepository()
    existing = repo.get_for_date(session_date)
    if existing is not None:
        return existing

    reference, source = resolve_reference_balance(settings, balance_fetcher, repo)
    session = build_session_from_balance(
        session_date,
        reference,
        settings,
        source=source,
    )
    return repo.upsert(session)


def get_or_create_today_session(
    settings: OtcSettingsRecord,
    *,
    timezone: str = DEFAULT_TIMEZONE,
    session_repo: OtcDailySessionRepository | None = None,
    balance_fetcher: Callable[[], Decimal] | None = None,
) -> OtcDailySessionRecord:
    if balance_fetcher is None:
        from src.otc.iqoption_client import fetch_iqoption_balance

        balance_fetcher = fetch_iqoption_balance

    return ensure_daily_session(
        session_repo=session_repo,
        settings=settings,
        session_date=current_local_date(timezone),
        balance_fetcher=balance_fetcher,
    )
