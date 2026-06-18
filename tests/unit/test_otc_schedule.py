"""Tests for OTC entry-time scheduling (America/Sao_Paulo)."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from src.otc.models import OtcSignal
from src.otc.schedule import (
    deserialize_signal,
    leg_window_missed,
    resolve_leg_datetime,
    serialize_signal,
    wait_for_leg,
)
from src.otc.signal_parser import parse_telegram_signal

EURJPY_SIGNAL = """
✅ ENTRADA CONFIRMADA ✅
🌎 Ativo: EURJPYOTC
⏳ Expiração: M1
📊 Direção: 🟢 COMPRA
⏰ Entrada: 16:07
👉 Fazer até 2 proteções em caso de loss!

1º PROTEÇÃO: TERMINA EM: 16:08h
2º PROTEÇÃO: TERMINA EM: 16:09h
"""


def test_parse_protection_schedule_from_telegram() -> None:
    signal = parse_telegram_signal(EURJPY_SIGNAL)
    assert signal is not None
    assert signal.entry_time is not None
    assert signal.entry_time.hour == 16
    assert signal.entry_time.minute == 7
    assert signal.protection_schedule == (time(16, 8), time(16, 9))


def test_resolve_leg_datetime_entry_and_protections() -> None:
    signal = parse_telegram_signal(EURJPY_SIGNAL)
    assert signal is not None
    tz = "America/Sao_Paulo"
    now = datetime(2026, 6, 10, 16, 5, tzinfo=ZoneInfo(tz))

    entry = resolve_leg_datetime(signal, 0, tz, now=now)
    prot1 = resolve_leg_datetime(signal, 1, tz, now=now)
    prot2 = resolve_leg_datetime(signal, 2, tz, now=now)

    assert entry is not None and entry.hour == 16 and entry.minute == 7
    assert prot1 is not None and prot1.hour == 16 and prot1.minute == 8
    assert prot2 is not None and prot2.hour == 16 and prot2.minute == 9


def test_wait_for_leg_sleeps_until_target() -> None:
    signal = OtcSignal(
        asset="BTC/USD (OTC)",
        direction="buy",
        expiry_minutes=1,
        entry_time=datetime(1900, 1, 1, 16, 7),
    )
    tz = "America/Sao_Paulo"
    zone = ZoneInfo(tz)
    target = datetime(2026, 6, 10, 16, 7, 0, tzinfo=zone)
    clock = {"now": datetime(2026, 6, 10, 16, 5, 30, tzinfo=zone)}
    slept: list[float] = []

    def now_fn() -> datetime:
        return clock["now"]

    def sleep_fn(seconds: float) -> None:
        slept.append(seconds)
        if seconds > 0.1:
            clock["now"] = target - timedelta(milliseconds=40)
        else:
            clock["now"] = target

    ok, reason = wait_for_leg(
        signal,
        0,
        tz,
        sleep_fn=sleep_fn,
        now_fn=now_fn,
    )
    assert ok is True
    assert reason is None
    assert clock["now"] == target
    assert any(s > 80 for s in slept)


def test_wait_for_leg_rejects_one_second_late() -> None:
    signal = OtcSignal(
        asset="BTC/USD (OTC)",
        direction="buy",
        expiry_minutes=1,
        entry_time=datetime(1900, 1, 1, 16, 7),
    )
    tz = "America/Sao_Paulo"
    zone = ZoneInfo(tz)
    now = datetime(2026, 6, 10, 16, 7, 1, tzinfo=zone)

    ok, reason = wait_for_leg(signal, 0, tz, max_lateness_seconds=0, now_fn=lambda: now)
    assert ok is False
    assert reason is not None
    assert "scheduled_time_missed" in reason
    assert "lateness=1s" in reason


def test_wait_for_leg_rejects_32_seconds_late() -> None:
    signal = OtcSignal(
        asset="BTC/USD (OTC)",
        direction="buy",
        expiry_minutes=1,
        entry_time=datetime(1900, 1, 1, 16, 22),
    )
    tz = "America/Sao_Paulo"
    zone = ZoneInfo(tz)
    now = datetime(2026, 6, 10, 16, 22, 32, tzinfo=zone)

    missed, reason = leg_window_missed(signal, 0, tz, max_lateness_seconds=0, now=now)
    assert missed is True
    assert reason is not None
    assert "lateness=32s" in reason


def test_signal_serialization_roundtrip() -> None:
    signal = parse_telegram_signal(EURJPY_SIGNAL)
    assert signal is not None
    payload = serialize_signal(signal)
    restored = deserialize_signal(payload)
    assert restored.asset == signal.asset
    assert restored.entry_time == signal.entry_time
    assert restored.protection_schedule == signal.protection_schedule
