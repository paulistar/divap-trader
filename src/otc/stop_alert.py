"""Alertas Telegram quando stop win / stop loss diário OTC é atingido."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import redis

from src.alerts.telegram import TelegramNotifier
from src.core.config import settings
from src.otc.periods import DEFAULT_TIMEZONE

logger = logging.getLogger(__name__)

DEDUP_TTL_SECONDS = 86_400


def _redis_client() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


def _dedup_key(local_date: str, reason: str) -> str:
    return f"otc:stop:alert:{local_date}:{reason}"


def _fmt_usd(amount: Decimal) -> str:
    abs_val = abs(amount).quantize(Decimal("0.01"))
    text = f"{abs_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if amount >= 0:
        return f"+US$ {text}"
    return f"-US$ {text}"


def format_otc_stop_alert(
    reason: str,
    day_pnl_usd: Decimal,
    triggered_at: datetime,
    *,
    timezone: str = DEFAULT_TIMEZONE,
) -> str:
    """Mensagem HTML para o bot de alertas (@divap_trader_alert_bot)."""
    tz = ZoneInfo(timezone)
    local_dt = triggered_at.astimezone(tz) if triggered_at.tzinfo else triggered_at.replace(tzinfo=UTC).astimezone(tz)
    when = local_dt.strftime("%d/%m/%Y %H:%M")
    positive = day_pnl_usd >= 0
    result_label = "POSITIVO" if positive else "NEGATIVO"
    amount_line = (
        f"Valor ganho no dia: <b>{_fmt_usd(day_pnl_usd)}</b>"
        if positive
        else f"Valor perdido no dia: <b>{_fmt_usd(day_pnl_usd)}</b>"
    )

    if reason == "stop_win":
        header = "🎯 <b>Stop Win — IQ Option</b>"
        footer = "Meta de lucro do dia atingida. Operações pausadas até o próximo dia."
    else:
        header = "🛑 <b>Stop Loss — IQ Option</b>"
        footer = "Limite de perda do dia atingido. Operações pausadas até o próximo dia."

    return (
        f"{header}\n\n"
        f"Resultado do dia: <b>{result_label}</b>\n"
        f"{amount_line}\n\n"
        f"📅 {when} ({timezone})\n\n"
        f"{footer}"
    )


def should_send_stop_alert(local_date: str, reason: str) -> bool:
    """Retorna True apenas na primeira vez no dia para cada tipo de stop."""
    client = _redis_client()
    created = client.set(_dedup_key(local_date, reason), "1", nx=True, ex=DEDUP_TTL_SECONDS)
    return created is not None


def notify_otc_stop_if_needed(
    reason: str,
    day_pnl_usd: Decimal,
    *,
    timezone: str = DEFAULT_TIMEZONE,
    triggered_at: datetime | None = None,
    notifier: TelegramNotifier | None = None,
) -> bool:
    """Envia alerta Telegram uma vez por dia por tipo de stop."""
    if reason not in ("stop_win", "stop_loss"):
        return False

    at = triggered_at or datetime.now(UTC)
    tz = ZoneInfo(timezone)
    local_date = at.astimezone(tz).date().isoformat()

    if not should_send_stop_alert(local_date, reason):
        return False

    tg = notifier or TelegramNotifier()
    if not tg.is_configured():
        logger.warning("Telegram não configurado — alerta OTC stop %s não enviado", reason)
        return False

    message = format_otc_stop_alert(reason, day_pnl_usd, at, timezone=timezone)
    try:
        sent = tg.send(message)
        if sent:
            logger.info("Alerta OTC %s enviado ao Telegram (PnL dia=%s)", reason, day_pnl_usd)
        return sent
    except Exception as exc:  # pragma: no cover - proteção defensiva
        logger.warning("Falha ao enviar alerta OTC %s: %s", reason, exc)
        return False


def check_and_notify_otc_stop(
    *,
    trade_repo=None,
    settings_repo=None,
    timezone: str | None = None,
    notifier: TelegramNotifier | None = None,
) -> str | None:
    """Avalia stop diário e dispara alerta Telegram se acabou de ser atingido."""
    from src.data.repositories.otc_settings_repo import OtcSettingsRepository
    from src.data.repositories.trade_repo import TradeRepository
    from src.otc.config import load_otc_config
    from src.otc.guard import decide_stop

    try:
        repo = trade_repo or TradeRepository()
        cfg_repo = settings_repo or OtcSettingsRepository()
        cfg = load_otc_config()
        tz = timezone or cfg.signal_timezone

        settings_row = cfg_repo.get_settings()
        if not (settings_row.stop_win_enabled or settings_row.stop_loss_enabled):
            return None

        from src.otc.daily_session import get_or_create_today_session

        session = get_or_create_today_session(settings_row, timezone=tz)

        totals = repo.otc_period_totals(tz)
        day_pnl = Decimal(str(totals.get("day", {}).get("pnl_usd") or 0))
        reason = decide_stop(
            day_pnl,
            stop_win_enabled=settings_row.stop_win_enabled,
            stop_loss_enabled=settings_row.stop_loss_enabled,
            daily_goal_usd=settings_row.daily_goal_usd,
            initial_bankroll_usd=session.reference_balance_usd,
            daily_stop_loss_pct=settings_row.daily_stop_loss_pct,
            daily_stop_win_pct=settings_row.daily_stop_win_pct,
            stop_win_usd=session.stop_win_usd,
            stop_loss_usd=session.stop_loss_usd,
        )
        if reason:
            notify_otc_stop_if_needed(
                reason,
                day_pnl,
                timezone=tz,
                notifier=notifier,
            )
        return reason
    except Exception as exc:  # pragma: no cover
        logger.warning("Falha ao checar alerta OTC stop: %s", exc)
        return None
