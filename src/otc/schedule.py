from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo

from src.otc.models import OtcSignal

logger = logging.getLogger(__name__)

DEFAULT_TIMEZONE = "America/Sao_Paulo"
DEFAULT_MAX_LATENESS_SECONDS = 0
COARSE_SLEEP_BUFFER_SECONDS = 0.05
FINE_POLL_INTERVAL_SECONDS = 0.005


def _parse_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception as exc:
        raise ValueError(f"Timezone OTC inválida: {name}") from exc


def _time_from_parsed(value: datetime) -> dt_time:
    return dt_time(hour=value.hour, minute=value.minute)


def resolve_leg_datetime(
    signal: OtcSignal,
    level: int,
    timezone_name: str,
    *,
    now: datetime | None = None,
) -> datetime | None:
    """Horário local (sala Telegram) para abrir a perna `level` (0=entrada)."""
    tz = _parse_timezone(timezone_name)
    now = now or datetime.now(tz)

    if level == 0:
        if signal.entry_time is None:
            return None
        leg_time = _time_from_parsed(signal.entry_time)
    else:
        schedule_index = level - 1
        if schedule_index < len(signal.protection_schedule):
            leg_time = signal.protection_schedule[schedule_index]
        elif signal.entry_time is not None:
            base_minutes = signal.entry_time.hour * 60 + signal.entry_time.minute
            target_minutes = base_minutes + level
            leg_time = dt_time(
                hour=(target_minutes // 60) % 24,
                minute=target_minutes % 60,
            )
        else:
            return None

    candidate = datetime.combine(now.date(), leg_time, tzinfo=tz)
    if candidate < now - timedelta(hours=12):
        candidate += timedelta(days=1)
    return candidate


def lateness_seconds(now: datetime, target: datetime) -> int:
    """Segundos inteiros após o alvo (16:22:00 → 16:22:31 = 31)."""
    return max(0, int((now - target).total_seconds()))


def leg_window_missed(
    signal: OtcSignal,
    level: int,
    timezone_name: str,
    *,
    max_lateness_seconds: int = DEFAULT_MAX_LATENESS_SECONDS,
    now: datetime | None = None,
) -> tuple[bool, str | None]:
    """True se o horário da perna já passou (tolerância zero por padrão)."""
    tz = _parse_timezone(timezone_name)
    now = now or datetime.now(tz)
    target = resolve_leg_datetime(signal, level, timezone_name, now=now)
    if target is None:
        return False, None
    late = lateness_seconds(now, target)
    if late > max_lateness_seconds:
        return (
            True,
            f"scheduled_time_missed:leg{level}:target={target.strftime('%H:%M:%S')}:"
            f"lateness={late}s",
        )
    return False, None


def wait_for_leg(
    signal: OtcSignal,
    level: int,
    timezone_name: str,
    *,
    max_lateness_seconds: int = DEFAULT_MAX_LATENESS_SECONDS,
    sleep_fn=time.sleep,
    now_fn=None,
) -> tuple[bool, str | None]:
    """
    Aguarda até o segundo exato do horário (ex.: 16:22:00).
    Se já passou do alvo, rejeita — sem tolerância de dezenas de segundos.
    """
    tz = _parse_timezone(timezone_name)
    if now_fn is None:
        now_fn = lambda: datetime.now(tz)

    target = resolve_leg_datetime(signal, level, timezone_name, now=now_fn())
    if target is None:
        return True, None

    missed, reason = leg_window_missed(
        signal,
        level,
        timezone_name,
        max_lateness_seconds=max_lateness_seconds,
        now=now_fn(),
    )
    if missed:
        logger.warning("OTC leg %s rejeitada — %s", level, reason)
        return False, reason

    now = now_fn()
    if now < target:
        remaining = (target - now).total_seconds()
        logger.info(
            "OTC leg %s aguardando até %s (%s) — faltam %.2fs",
            level,
            target.strftime("%H:%M:%S"),
            timezone_name,
            remaining,
        )
        coarse = remaining - COARSE_SLEEP_BUFFER_SECONDS
        if coarse > 0:
            sleep_fn(coarse)
        while now_fn() < target:
            sleep_fn(FINE_POLL_INTERVAL_SECONDS)

    now = now_fn()
    late = lateness_seconds(now, target)
    if late > max_lateness_seconds:
        reason = (
            f"scheduled_time_missed:leg{level}:target={target.strftime('%H:%M:%S')}:"
            f"lateness={late}s"
        )
        logger.warning("OTC leg %s rejeitada após espera — %s", level, reason)
        return False, reason

    logger.info(
        "OTC leg %s no horário exato (alvo %s, relógio %s)",
        level,
        target.strftime("%H:%M:%S"),
        now.strftime("%H:%M:%S"),
    )
    return True, None


def serialize_signal(signal: OtcSignal) -> dict:
    return {
        "asset": signal.asset,
        "direction": signal.direction,
        "expiry_minutes": signal.expiry_minutes,
        "entry_time": (
            signal.entry_time.strftime("%H:%M") if signal.entry_time is not None else None
        ),
        "raw_text": signal.raw_text,
        "protection_level": signal.protection_level,
        "max_auto_protections": signal.max_auto_protections,
        "protection_schedule": [
            t.strftime("%H:%M") for t in signal.protection_schedule
        ],
    }


def deserialize_signal(data: dict) -> OtcSignal:
    entry_raw = data.get("entry_time")
    entry_time = datetime.strptime(entry_raw, "%H:%M") if entry_raw else None
    schedule = tuple(
        datetime.strptime(item, "%H:%M").time()
        for item in (data.get("protection_schedule") or [])
    )
    return OtcSignal(
        asset=str(data["asset"]),
        direction=str(data["direction"]),
        expiry_minutes=int(data.get("expiry_minutes") or 1),
        entry_time=entry_time,
        raw_text=str(data.get("raw_text") or ""),
        protection_level=int(data.get("protection_level") or 0),
        max_auto_protections=data.get("max_auto_protections"),
        protection_schedule=schedule,
    )


def utc_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()
