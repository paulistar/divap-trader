"""Tests for OTC martingale auto-protection sequence."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from src.otc.executor import OtcExecutor
from src.otc.martingale import stake_for_level
from src.otc.models import OtcMartingale, OtcSignal, OtcTradeResult
from src.otc.signal_parser import parse_telegram_signal


EURJPY_SIGNAL = """
✅ ENTRADA CONFIRMADA ✅
🌎 Ativo: EURJPYOTC
⏳ Expiração: M1
📊 Direção: 🟢 COMPRA
⏰ Entrada: 15:52
👉 Fazer até 2 proteções em caso de loss!

1º PROTEÇÃO: TERMINA EM: 15:53h
2º PROTEÇÃO: TERMINA EM: 15:54h
"""


def _leg(
    level: int,
    pnl: Decimal | None,
    stake: Decimal,
    *,
    executed: bool = True,
) -> OtcTradeResult:
    return OtcTradeResult(
        executed=executed,
        reason="filled",
        asset="EUR/JPY (OTC)",
        direction="buy",
        stake_usd=stake,
        pnl_usd=pnl,
        protection_level=level,
    )


def test_stake_for_level_martingale() -> None:
    mg = OtcMartingale(enabled=True, max_protections=2, multiplier=Decimal("2.2"))
    base = Decimal("5")
    assert stake_for_level(base, mg, 0) == Decimal("5")
    assert stake_for_level(base, mg, 1) == Decimal("11.00")
    assert stake_for_level(base, mg, 2) == Decimal("24.20")


def test_parse_max_auto_protections_from_telegram() -> None:
    signal = parse_telegram_signal(EURJPY_SIGNAL)
    assert signal is not None
    assert signal.asset == "EURJPYOTC"
    assert signal.direction == "buy"
    assert signal.protection_level == 0
    assert signal.max_auto_protections == 2
    assert signal.entry_time is not None
    assert signal.entry_time.hour == 15
    assert signal.entry_time.minute == 52


def test_martingale_sequence_stops_on_first_win() -> None:
    broker = MagicMock()
    broker.place_binary.side_effect = [
        _leg(0, Decimal("4.15"), Decimal("5")),
    ]
    signal = OtcSignal(
        asset="EUR/JPY (OTC)",
        direction="buy",
        expiry_minutes=1,
        max_auto_protections=2,
    )
    executor = OtcExecutor(broker=broker, trade_repo=MagicMock())
    executor._repo.count_open_trades.return_value = 0
    with patch("src.otc.executor.settings") as mock_settings:
        mock_settings.otc_trading_enabled = True
        result = executor.try_execute(signal)
    assert result.reason == "sequence_win"
    assert len(result.legs) == 1
    assert result.total_pnl_usd == Decimal("4.15")
    broker.place_binary.assert_called_once()


def test_martingale_sequence_runs_three_legs_on_losses() -> None:
    broker = MagicMock()
    broker.place_binary.side_effect = [
        _leg(0, Decimal("-5"), Decimal("5")),
        _leg(1, Decimal("-11"), Decimal("11")),
        _leg(2, Decimal("-24.20"), Decimal("24.20")),
    ]
    signal = OtcSignal(
        asset="EUR/JPY (OTC)",
        direction="buy",
        expiry_minutes=1,
        max_auto_protections=2,
    )
    executor = OtcExecutor(broker=broker, trade_repo=MagicMock())
    executor._repo.count_open_trades.return_value = 0
    with patch("src.otc.executor.settings") as mock_settings:
        mock_settings.otc_trading_enabled = True
        result = executor.try_execute(signal)
    assert result.reason == "sequence_loss"
    assert len(result.legs) == 3
    assert result.total_pnl_usd == Decimal("-40.20")
    assert broker.place_binary.call_count == 3


def test_martingale_sequence_wins_on_second_protection() -> None:
    broker = MagicMock()
    broker.place_binary.side_effect = [
        _leg(0, Decimal("-5"), Decimal("5")),
        _leg(1, Decimal("9.35"), Decimal("11")),
    ]
    signal = OtcSignal(
        asset="EUR/JPY (OTC)",
        direction="buy",
        expiry_minutes=1,
        max_auto_protections=2,
    )
    executor = OtcExecutor(broker=broker, trade_repo=MagicMock())
    executor._repo.count_open_trades.return_value = 0
    with patch("src.otc.executor.settings") as mock_settings:
        mock_settings.otc_trading_enabled = True
        result = executor.try_execute(signal)
    assert result.reason == "sequence_win"
    assert len(result.legs) == 2
    assert result.total_pnl_usd == Decimal("4.35")
    assert broker.place_binary.call_count == 2
