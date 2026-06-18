from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo

from src.otc.models import OtcSignal

logger = logging.getLogger(__name__)

DEFAULT_TIMEZONE = "America/Sao_Paulo"
DEFAULT_MAX_LATENESS_SECONDS = 45


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
    Aguarda até o horário da perna. Retorna (True, None) se OK para executar,
    ou (False, reason) se o horário já passou além da tolerância.
    """
    tz = _parse_timezone(timezone_name)
    if now_fn is None:
        now_fn = lambda: datetime.now(tz)

    target = resolve_leg_datetime(signal, level, timezone_name, now=now_fn())
    if target is None:
        return True, None

    now = now_fn()
    if now < target:
        delay = (target - now).total_seconds()
        logger.info(
            "OTC leg %s aguardando até %s (%s) — faltam %.0fs",
            level,
            target.strftime("%H:%M:%S"),
            timezone_name,
            delay,
        )
        sleep_fn(delay)
        now = now_fn()

    lateness = (now - target).total_seconds()
    if lateness > max_lateness_seconds:
        return (
            False,
            f"scheduled_time_missed:leg{level}:target={target.strftime('%H:%M')}:"
            f"lateness={int(lateness)}s",
        )

    logger.info(
        "OTC leg %s no horário (alvo %s, atraso %.0fs)",
        level,
        target.strftime("%H:%M:%S"),
        lateness,
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
