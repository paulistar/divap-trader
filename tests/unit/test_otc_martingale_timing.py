"""Martingale timing — proteção no horário mesmo com settlement da perna anterior."""

from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from src.otc.executor import OtcExecutor
from src.otc.models import OtcSettlementContext, OtcTradeResult
from src.otc.signal_parser import parse_telegram_signal

EURAUD_SIGNAL = """
✅ ENTRADA CONFIRMADA ✅
🌎 Ativo: EUR/AUD (OTC)
⏳ Expiração: M1
📊 Direção: 🟢 COMPRA
⏰ Entrada: 16:51
👉 Fazer até 2 proteções em caso de loss!

1º PROTEÇÃO: TERMINA EM: 16:52h
2º PROTEÇÃO: TERMINA EM: 16:53h
"""


def _open_leg(asset: str, stake: Decimal, order_id: str) -> tuple[OtcTradeResult, OtcSettlementContext]:
    return (
        OtcTradeResult(
            executed=True,
            reason="opened",
            order_id=order_id,
            asset=asset,
            direction="buy",
            stake_usd=stake,
            pnl_usd=None,
        ),
        OtcSettlementContext(
            transport="mcp",
            resolved_asset=asset,
            direction="buy",
            stake_usd=stake,
            duration_minutes=1,
            order_id=order_id,
            mcp_asset_id=123,
        ),
    )


def test_martingale_waits_next_leg_while_settling_previous() -> None:
    signal = parse_telegram_signal(EURAUD_SIGNAL)
    assert signal is not None

    broker = MagicMock()
    broker.open_binary.side_effect = [
        _open_leg("EUR/AUD (OTC)", Decimal("5"), "main-order"),
        _open_leg("EUR/AUD (OTC)", Decimal("11"), "prot-order"),
    ]
    broker.wait_settlement.side_effect = [Decimal("-5"), Decimal("9.48")]

    executor = OtcExecutor(broker=broker, trade_repo=MagicMock())
    executor._repo.count_open_trades.return_value = 0
    executor._config = replace(executor._config, dry_run=False)

    with patch("src.otc.executor.settings") as mock_settings:
        mock_settings.otc_trading_enabled = True
        with patch("src.otc.executor.wait_for_leg", return_value=(True, None)):
            result = executor.try_execute(signal)

    assert result.reason == "sequence_win"
    assert len(result.legs) == 2
    assert broker.open_binary.call_count == 2

    first_wait_kwargs = broker.wait_settlement.call_args_list[0].kwargs
    sync_until = first_wait_kwargs.get("sync_until")
    assert sync_until is not None
    assert sync_until.hour == 16
    assert sync_until.minute == 52
    assert sync_until.second == 0


def test_three_leg_sequence_each_protection_on_time() -> None:
    """Entrada + 1ª + 2ª proteção: cada perna sincroniza para o horário seguinte."""
    signal = parse_telegram_signal(EURAUD_SIGNAL)
    assert signal is not None

    broker = MagicMock()
    broker.open_binary.side_effect = [
        _open_leg("EUR/AUD (OTC)", Decimal("5"), "main-order"),
        _open_leg("EUR/AUD (OTC)", Decimal("11"), "prot1-order"),
        _open_leg("EUR/AUD (OTC)", Decimal("24.20"), "prot2-order"),
    ]
    # entrada loss, 1ª proteção loss, 2ª proteção win
    broker.wait_settlement.side_effect = [Decimal("-5"), Decimal("-11"), Decimal("12.10")]

    executor = OtcExecutor(broker=broker, trade_repo=MagicMock())
    executor._repo.count_open_trades.return_value = 0
    executor._config = replace(executor._config, dry_run=False)

    with patch("src.otc.executor.settings") as mock_settings:
        mock_settings.otc_trading_enabled = True
        with patch("src.otc.executor.wait_for_leg", return_value=(True, None)):
            result = executor.try_execute(signal)

    assert result.reason == "sequence_win"
    assert len(result.legs) == 3
    assert broker.open_binary.call_count == 3
    assert broker.wait_settlement.call_count == 3

    calls = broker.wait_settlement.call_args_list
    sync0 = calls[0].kwargs.get("sync_until")
    sync1 = calls[1].kwargs.get("sync_until")
    sync2 = calls[2].kwargs.get("sync_until")

    # entrada sincroniza para 1ª proteção (16:52)
    assert sync0 is not None and (sync0.hour, sync0.minute, sync0.second) == (16, 52, 0)
    # 1ª proteção sincroniza para 2ª proteção (16:53)
    assert sync1 is not None and (sync1.hour, sync1.minute, sync1.second) == (16, 53, 0)
    # 2ª proteção é a última — sem sincronização (não trava em loop)
    assert sync2 is None


def test_wait_settlement_hard_timeout_without_sync() -> None:
    """Última perna (sync_until=None) não pode rodar para sempre."""
    from src.otc.broker import IqOptionBroker

    broker = IqOptionBroker()
    ctx = OtcSettlementContext(
        transport="legacy",
        resolved_asset="EUR/AUD (OTC)",
        direction="buy",
        stake_usd=Decimal("24.20"),
        duration_minutes=1,
        order_id="2",
        legacy_order_id=2,
    )
    clock = {"now": datetime(2026, 6, 10, 16, 53, 0)}

    def now_fn() -> datetime:
        return clock["now"]

    def sleep_fn(seconds: float) -> None:
        from datetime import timedelta

        clock["now"] = clock["now"] + timedelta(seconds=seconds)

    broker._poll_settlement_once = lambda _ctx: None  # type: ignore[method-assign]
    pnl = broker.wait_settlement(ctx, sync_until=None, sleep_fn=sleep_fn, now_fn=now_fn)
    assert pnl is None
    # parou perto do teto (1min + 25s), não em loop infinito
    assert (clock["now"] - datetime(2026, 6, 10, 16, 53, 0)).total_seconds() <= 95


def test_wait_settlement_holds_pnl_until_sync_until() -> None:
    from src.otc.broker import IqOptionBroker

    broker = IqOptionBroker()
    ctx = OtcSettlementContext(
        transport="legacy",
        resolved_asset="EUR/AUD (OTC)",
        direction="buy",
        stake_usd=Decimal("5"),
        duration_minutes=1,
        order_id="1",
        legacy_order_id=1,
    )
    tz = ZoneInfo("America/Sao_Paulo")
    sync_until = datetime(2026, 6, 10, 16, 52, 0, tzinfo=tz)
    clock = {"now": datetime(2026, 6, 10, 16, 51, 59, 500000, tzinfo=tz)}
    poll = {"calls": 0}

    def now_fn() -> datetime:
        return clock["now"]

    def sleep_fn(seconds: float) -> None:
        if seconds <= 0.1:
            clock["now"] = sync_until

    def poll_once(_ctx: OtcSettlementContext) -> Decimal | None:
        poll["calls"] += 1
        if poll["calls"] == 1:
            return Decimal("-5")
        return None

    broker._poll_settlement_once = poll_once  # type: ignore[method-assign]
    pnl = broker.wait_settlement(ctx, sync_until=sync_until, sleep_fn=sleep_fn, now_fn=now_fn)
    assert pnl == Decimal("-5")
    assert clock["now"] >= sync_until


def test_protection_leg_allows_lateness_after_settlement() -> None:
    """Reproduz Ford 11:14 — loss confirmado 3s após horário da proteção."""
    from dataclasses import replace
    from zoneinfo import ZoneInfo

    signal = parse_telegram_signal(
        """
✅ ENTRADA CONFIRMADA ✅
🌎 Ativo: FORDOTC
⏳ Expiração: M1
📊 Direção: 🔴 VENDA
⏰ Entrada: 11:14
👉 Fazer até 2 proteções em caso de loss!
1º PROTEÇÃO: TERMINA EM: 11:15h
2º PROTEÇÃO: TERMINA EM: 11:16h
"""
    )
    assert signal is not None
    tz = ZoneInfo("America/Sao_Paulo")
    broker = MagicMock()
    broker.open_binary.side_effect = [
        _open_leg("Ford (OTC)", Decimal("5"), "main-order"),
        _open_leg("Ford (OTC)", Decimal("11"), "prot-order"),
    ]
    broker.wait_settlement.side_effect = [Decimal("-5"), Decimal("9.48")]

    executor = OtcExecutor(broker=broker, trade_repo=MagicMock())
    executor._repo.count_open_trades.return_value = 0
    executor._config = replace(
        executor._config,
        dry_run=False,
        entry_max_lateness_seconds=0,
        protection_max_lateness_seconds=30,
    )

    # Leg 0 ok no horário; leg 1 chega 3s atrasada (settlement MCP)
    wait_calls: list[int] = []

    def wait_side_effect(sig, level, tz_name, *, max_lateness_seconds=0, **kwargs):
        wait_calls.append((level, max_lateness_seconds))
        if level == 0:
            return True, None
        now = datetime(2026, 6, 20, 11, 15, 3, tzinfo=tz)
        missed, reason = __import__(
            "src.otc.schedule", fromlist=["leg_window_missed"]
        ).leg_window_missed(
            sig,
            level,
            tz_name,
            max_lateness_seconds=max_lateness_seconds,
            now=now,
        )
        return (not missed, reason)

    with patch("src.otc.executor.settings") as mock_settings:
        mock_settings.otc_trading_enabled = True
        with patch("src.otc.executor.wait_for_leg", side_effect=wait_side_effect):
            result = executor.try_execute(signal)

    assert wait_calls[0] == (0, 0)
    assert wait_calls[1] == (1, 30)
    assert result.reason == "sequence_win"
    assert len(result.legs) == 2
    assert broker.open_binary.call_count == 2
