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
