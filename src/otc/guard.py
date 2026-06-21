"""Travas de risco do perfil OTC: stop win e stop loss diários.

Quando ativadas no painel, pausam a execução de novos sinais assim que a
meta do dia é atingida (stop win) ou a perda do dia ultrapassa um percentual
da banca inicial (stop loss).
"""

from __future__ import annotations

import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


def decide_stop(
    day_pnl_usd: Decimal,
    *,
    stop_win_enabled: bool,
    stop_loss_enabled: bool,
    daily_goal_usd: Decimal | None,
    initial_bankroll_usd: Decimal | None,
    daily_stop_loss_pct: Decimal | None,
    daily_stop_win_pct: Decimal | None = None,
) -> str | None:
    """Decide se as operações devem ser pausadas. Retorna o motivo ou ``None``.

    Função pura — toda a entrada vem de números já calculados.
    """
    if stop_win_enabled:
        if (
            daily_stop_win_pct
            and daily_stop_win_pct > 0
            and initial_bankroll_usd
            and initial_bankroll_usd > 0
        ):
            win_limit = initial_bankroll_usd * daily_stop_win_pct / Decimal("100")
            if day_pnl_usd >= win_limit:
                return "stop_win"
        elif daily_goal_usd and daily_goal_usd > 0:
            if day_pnl_usd >= daily_goal_usd:
                return "stop_win"

    if (
        stop_loss_enabled
        and daily_stop_loss_pct
        and daily_stop_loss_pct > 0
        and initial_bankroll_usd
        and initial_bankroll_usd > 0
    ):
        loss_limit = (initial_bankroll_usd * daily_stop_loss_pct / Decimal("100")).copy_abs()
        if day_pnl_usd <= -loss_limit:
            return "stop_loss"

    return None


def evaluate_otc_stop(trade_repo=None, settings_repo=None, timezone: str | None = None) -> str | None:
    """Avalia as travas usando dados reais do banco. Retorna motivo ou ``None``.

    Falha de forma segura (``None`` = liberado) caso o banco esteja indisponível,
    para nunca bloquear operação por erro de leitura de configuração.
    """
    try:
        from src.data.repositories.otc_settings_repo import OtcSettingsRepository
        from src.data.repositories.trade_repo import TradeRepository
        from src.otc.config import load_otc_config

        repo = trade_repo or TradeRepository()
        cfg_repo = settings_repo or OtcSettingsRepository()
        tz = timezone or load_otc_config().signal_timezone

        cfg = cfg_repo.get_settings()
        if not (cfg.stop_win_enabled or cfg.stop_loss_enabled):
            return None

        totals = repo.otc_period_totals(tz)
        day_pnl = Decimal(str(totals.get("day", {}).get("pnl_usd") or 0))
        reason = decide_stop(
            day_pnl,
            stop_win_enabled=cfg.stop_win_enabled,
            stop_loss_enabled=cfg.stop_loss_enabled,
            daily_goal_usd=cfg.daily_goal_usd,
            initial_bankroll_usd=cfg.initial_bankroll_usd,
            daily_stop_loss_pct=cfg.daily_stop_loss_pct,
            daily_stop_win_pct=cfg.daily_stop_win_pct,
        )
        if reason:
            from src.otc.stop_alert import notify_otc_stop_if_needed

            notify_otc_stop_if_needed(reason, day_pnl, timezone=tz)
        return reason
    except Exception as exc:  # pragma: no cover - proteção defensiva
        logger.warning("Falha ao avaliar stop OTC (liberando): %s", exc)
        return None
