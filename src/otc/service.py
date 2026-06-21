from __future__ import annotations

from decimal import Decimal, InvalidOperation

from src.core.config import settings
from src.data.repositories.otc_settings_repo import OtcSettingsRepository
from src.data.repositories.trade_repo import TradeRepository
from src.otc.broker import IqOptionBroker
from src.otc.config import load_otc_config, resolve_otc_telegram_chat_id
from src.otc.guard import decide_stop
from src.otc.martingale import stake_for_level
from src.otc.periods import PERIOD_LABELS, VALID_PERIODS, normalize_period
from src.otc.stake import risk_profiles_for_api
from src.otc.telegram_user_listener import user_listener_configured
from src.otc.iqoption_client import fetch_otc_capabilities, iqoption_configured, otc_transport
from src.otc.iqoption_client import reset_iqoption_client as reset_connections
from src.otc.mcp_client import mcp_configured


def _to_decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def build_otc_status() -> dict:
    config = load_otc_config()
    broker = IqOptionBroker(config)
    balance = None
    connection_ok = False
    connection_error: str | None = None
    mcp_mode: str | None = None
    transport = otc_transport()

    if iqoption_configured():
        try:
            balance = str(broker.get_balance_usd())
            connection_ok = True
            if transport == "mcp":
                caps = fetch_otc_capabilities() or {}
                mcp_mode = str(caps.get("mode") or "")
        except Exception as exc:
            reset_connections()
            connection_error = str(exc)
    else:
        connection_error = (
            "Credenciais IQ Option não configuradas "
            "(IQOPTION_MCP_TOKEN ou IQOPTION_EMAIL/PASSWORD)"
        )

    return {
        "profile_id": config.profile_id,
        "venue": config.venue,
        "account_mode": config.account_mode,
        "dry_run": config.dry_run,
        "otc_trading_enabled": settings.otc_trading_enabled,
        "transport": transport,
        "iqoption_configured": iqoption_configured(),
        "mcp_configured": mcp_configured(),
        "mcp_mode": mcp_mode,
        "connection_ok": connection_ok,
        "connection_error": connection_error,
        "balance_usd": balance,
        "default_stake_usd": str(config.default_stake_usd),
        "max_open_trades": config.max_open_trades,
        "expiry_minutes": config.expiry_minutes,
        "martingale": {
            "enabled": config.martingale.enabled,
            "max_protections": config.martingale.max_protections,
            "multiplier": str(config.martingale.multiplier),
        },
        "assets": list(config.assets),
        "telegram_listener": config.telegram.enabled,
        "telegram_mode": config.telegram.mode,
        "telegram_user_configured": user_listener_configured(),
        "telegram_chat_id": resolve_otc_telegram_chat_id(config) or None,
        "divap_scan": False,
    }


_LEVEL_LABELS = {
    "expiry": "Entrada",
    "expiry_p1": "1ª proteção",
    "expiry_p2": "2ª proteção",
}


def _serialize_otc_trade(row: dict) -> dict:
    close_reason = row.get("close_reason") or ""
    pnl = row.get("pnl_usdt")
    result = None
    if row.get("status") == "closed" and pnl is not None:
        result = "win" if Decimal(str(pnl)) > 0 else "loss"
    return {
        "id": row.get("id"),
        "asset": row.get("symbol"),
        "direction": row.get("direction"),
        "level_label": _LEVEL_LABELS.get(close_reason, "Entrada"),
        "stake_usd": str(row["quantity"]) if row.get("quantity") is not None else None,
        "pnl_usd": str(pnl) if pnl is not None else None,
        "result": result,
        "status": row.get("status"),
        "order_id": row.get("exchange_order_id"),
        "opened_at": row["opened_at"].isoformat() if row.get("opened_at") else None,
        "closed_at": row["closed_at"].isoformat() if row.get("closed_at") else None,
    }


def _goal_progress(pnl: Decimal | None, goal: Decimal | None) -> dict | None:
    if goal is None or goal <= 0:
        return None
    achieved = pnl or Decimal("0")
    pct = float((achieved / goal * Decimal("100"))) if goal else 0.0
    return {
        "goal_usd": str(goal),
        "achieved_usd": str(achieved),
        "progress_pct": round(pct, 2),
        "reached": achieved >= goal,
    }


def _stake_ladder_preview(base_stake: Decimal, config) -> list[str]:
    mg = config.martingale
    levels = max(0, mg.max_protections) + 1
    return [
        str(stake_for_level(base_stake, mg, level))
        for level in range(levels)
    ]


def build_otc_overview() -> dict:
    """Status + banca + estatísticas + metas + travas para a tela IQ Option."""
    status = build_otc_status()
    config = load_otc_config()
    tz = config.signal_timezone

    repo = TradeRepository()
    settings_repo = OtcSettingsRepository()

    cfg = settings_repo.get_settings()
    daily_session = None
    try:
        from src.otc.daily_session import get_or_create_today_session

        daily_session = get_or_create_today_session(cfg, timezone=tz)
    except Exception:
        daily_session = None

    try:
        stats = repo.otc_stats()
    except Exception:
        stats = {}
    try:
        period_totals = repo.otc_period_totals(tz)
    except Exception:
        period_totals = {}
    try:
        trades = [_serialize_otc_trade(t) for t in repo.list_otc_trades(50)]
    except Exception:
        trades = []

    balance = _to_decimal(status.get("balance_usd"))
    initial_bankroll = cfg.initial_bankroll_usd
    accumulated_pnl = _to_decimal(stats.get("total_pnl_usd")) or Decimal("0")

    profit_abs: Decimal | None = None
    profit_pct: float | None = None
    if balance is not None and initial_bankroll is not None and initial_bankroll > 0:
        profit_abs = balance - initial_bankroll
        profit_pct = round(float(profit_abs / initial_bankroll * Decimal("100")), 2)

    day_pnl = _to_decimal((period_totals.get("day") or {}).get("pnl_usd")) or Decimal("0")
    month_pnl = _to_decimal((period_totals.get("month") or {}).get("pnl_usd")) or Decimal("0")

    stop_win_usd = daily_session.stop_win_usd if daily_session else None
    stop_loss_usd = daily_session.stop_loss_usd if daily_session else None
    reference_balance = (
        daily_session.reference_balance_usd if daily_session else cfg.initial_bankroll_usd
    )

    stop_reason = decide_stop(
        day_pnl,
        stop_win_enabled=cfg.stop_win_enabled,
        stop_loss_enabled=cfg.stop_loss_enabled,
        daily_goal_usd=cfg.daily_goal_usd,
        initial_bankroll_usd=reference_balance,
        daily_stop_loss_pct=cfg.daily_stop_loss_pct,
        daily_stop_win_pct=cfg.daily_stop_win_pct,
        stop_win_usd=stop_win_usd,
        stop_loss_usd=stop_loss_usd,
    )

    session_payload = None
    if daily_session is not None:
        session_payload = {
            **daily_session.to_dict(),
            "stake_ladder_usd": _stake_ladder_preview(
                daily_session.base_stake_usd, config
            ),
        }

    return {
        **status,
        "settings": cfg.to_dict(),
        "daily_session": session_payload,
        "risk_profiles": risk_profiles_for_api(),
        "stats": stats,
        "trades": trades,
        "period_totals": period_totals,
        "period_labels": PERIOD_LABELS,
        "bankroll": {
            "balance_usd": str(balance) if balance is not None else None,
            "initial_bankroll_usd": str(initial_bankroll) if initial_bankroll is not None else None,
            "reference_balance_usd": (
                str(reference_balance) if reference_balance is not None else None
            ),
            "profit_abs_usd": str(profit_abs) if profit_abs is not None else None,
            "profit_pct": profit_pct,
            "accumulated_pnl_usd": str(accumulated_pnl),
        },
        "goals": {
            "daily": _goal_progress(day_pnl, cfg.daily_goal_usd),
            "monthly": _goal_progress(month_pnl, cfg.monthly_goal_usd),
        },
        "stop": {
            "win_enabled": cfg.stop_win_enabled,
            "loss_enabled": cfg.stop_loss_enabled,
            "active_reason": stop_reason,
            "blocked": stop_reason is not None,
            "stop_win_usd": str(stop_win_usd) if stop_win_usd is not None else None,
            "stop_loss_usd": str(stop_loss_usd) if stop_loss_usd is not None else None,
            "day_pnl_usd": str(day_pnl),
        },
        "usd_brl_rate": str(cfg.usd_brl_rate) if cfg.usd_brl_rate is not None else None,
    }


def build_otc_pnl(period: str = "day", limit: int = 30) -> dict:
    period = normalize_period(period)
    repo = TradeRepository()
    tz = load_otc_config().signal_timezone
    try:
        series = repo.otc_pnl_series(period, limit=limit, timezone=tz)
    except Exception:
        series = []
    for point in series:
        bucket_raw = point.get("bucket")
        if not bucket_raw:
            continue
        try:
            from datetime import datetime

            ref = datetime.fromisoformat(str(bucket_raw).replace("Z", "+00:00"))
            point["breakdown"] = repo.otc_pnl_breakdown_at(ref, tz)
        except Exception:
            point["breakdown"] = None
    total = sum((Decimal(item["pnl_usd"]) for item in series), Decimal("0"))
    return {
        "period": period,
        "label": PERIOD_LABELS.get(period, period),
        "series": series,
        "total_usd": str(total),
        "available_periods": [
            {"id": p, "label": PERIOD_LABELS[p]} for p in VALID_PERIODS
        ],
    }


def build_otc_trades_for_day(day: str, limit: int = 500) -> dict:
    """Operações OTC fechadas em um dia (fuso do sinal)."""
    repo = TradeRepository()
    tz = load_otc_config().signal_timezone
    try:
        rows = repo.list_otc_trades_by_day(day, timezone=tz, limit=limit)
    except Exception:
        rows = []
    trades = [_serialize_otc_trade(t) for t in rows]
    total_pnl = sum(
        (Decimal(t["pnl_usd"]) for t in trades if t.get("pnl_usd") is not None),
        Decimal("0"),
    )
    return {
        "date": day,
        "trades": trades,
        "count": len(trades),
        "total_pnl_usd": str(total_pnl),
    }


def update_otc_settings(payload: dict) -> dict:
    """Persiste configurações do painel e devolve o overview atualizado."""
    from src.otc.stake import stake_pct_for_profile, stop_pcts_for_profile

    if payload.get("stake_risk_profile"):
        profile = str(payload["stake_risk_profile"]).strip().lower()
        stop_win, stop_loss = stop_pcts_for_profile(profile)
        payload = {
            **payload,
            "stake_pct": stake_pct_for_profile(profile),
            "daily_stop_win_pct": stop_win,
            "daily_stop_loss_pct": stop_loss,
        }

    repo = OtcSettingsRepository()
    repo.update_settings(**payload)
    return build_otc_overview()
