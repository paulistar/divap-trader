"""Tests for profile exit policy (Fibo TP + time stop)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from src.data.models.candle import Candle
from src.data.repositories.trade_repo import TradeRecord
from src.detection.divap_scanner import DIVAPCriteria, DIVAPSignal
from src.execution.position_monitor import PositionMonitor
from src.profiles.exit_policy import (
    compute_partial_take_profit_levels,
    fibo_take_profit_price,
    partial_close_quantity,
    resolve_take_profit,
    should_time_stop,
)
from src.profiles.loader import load_profile


def _candle(ts: datetime, close: str) -> Candle:
    price = Decimal(close)
    return Candle(
        symbol="BTCUSDT",
        timeframe="15m",
        timestamp=ts,
        open=price,
        high=price,
        low=price,
        close=price,
        volume=Decimal("100"),
    )


def _signal(targets: tuple[Decimal, ...] = (Decimal("54000"),)) -> DIVAPSignal:
    return DIVAPSignal(
        symbol="BTCUSDT",
        timeframe="15m",
        direction="buy",
        confidence="high",
        criteria=DIVAPCriteria(True, True, True, True),
        entry_price=Decimal("50000"),
        stop_loss=Decimal("48000"),
        targets=targets,
        current_price=Decimal("50000"),
        rsi_value=35.0,
        volume_ratio=1.5,
        divergence_type="bullish",
        pattern_detected="hammer",
        fibo_level=Decimal("1.0"),
        timestamp=datetime.now(UTC),
    )


def test_divap_ativo_has_partial_take_profits() -> None:
    profile = load_profile("divap_ativo")
    assert profile is not None
    assert len(profile.exit.partial_take_profits) == 3
    assert profile.exit.move_stop_to_breakeven_after == 1


def test_compute_partial_take_profit_levels_buy() -> None:
    profile = load_profile("divap_ativo")
    assert profile is not None
    levels = compute_partial_take_profit_levels(
        Decimal("64040"),
        Decimal("68000"),
        "buy",
        profile.exit.partial_take_profits,
    )
    assert len(levels) == 3
    assert levels[0] == Decimal("64040") + (Decimal("68000") - Decimal("64040")) * Decimal("0.25")
    assert levels[1] == Decimal("64040") + (Decimal("68000") - Decimal("64040")) * Decimal("0.50")
    assert levels[2] == Decimal("68000")


def test_compute_partial_take_profit_levels_sell() -> None:
    profile = load_profile("divap_ativo")
    assert profile is not None
    entry = Decimal("1792.77")
    final_tp = Decimal("1101.01")
    levels = compute_partial_take_profit_levels(
        entry,
        final_tp,
        "sell",
        profile.exit.partial_take_profits,
    )
    move = entry - final_tp
    assert len(levels) == 3
    assert levels[0] == entry - move * Decimal("0.25")
    assert levels[1] == entry - move * Decimal("0.50")
    assert levels[2] == final_tp


def test_partial_close_quantity_equal_thirds() -> None:
    original = Decimal("0.9")
    remaining = Decimal("0.9")
    first = partial_close_quantity(original, remaining, 0, 3)
    assert first == Decimal("0.3")
    second = partial_close_quantity(original, Decimal("0.6"), 1, 3)
    assert second == Decimal("0.3")
    last = partial_close_quantity(original, Decimal("0.3"), 2, 3)
    assert last == Decimal("0.3")


def test_caixa_rapido_exit_rules() -> None:
    profile = load_profile("caixa_rapido")
    assert profile is not None
    assert profile.exit.take_profit_fibo == Decimal("1.0")
    assert profile.exit.time_stop_candles == 8
    assert profile.exit.time_stop_timeframes == ("15m",)


def test_fibo_take_profit_price_uses_ratio_one() -> None:
    candles = [
        _candle(datetime(2026, 1, 1, tzinfo=UTC), "100"),
        _candle(datetime(2026, 1, 1, 0, 15, tzinfo=UTC), "105"),
        _candle(datetime(2026, 1, 1, 0, 30, tzinfo=UTC), "110"),
    ]
    for i in range(20):
        candles.append(
            _candle(datetime(2026, 1, 1, 1, i, tzinfo=UTC), str(100 + i))
        )

    price = fibo_take_profit_price("buy", candles, Decimal("105"), Decimal("1.0"))
    assert price is not None
    assert price > Decimal("105")


def test_resolve_take_profit_prefers_fibo_for_caixa() -> None:
    profile = load_profile("caixa_rapido")
    assert profile is not None
    candles = []
    base = datetime(2026, 6, 1, tzinfo=UTC)
    for i in range(60):
        candles.append(_candle(base + timedelta(minutes=15 * i), str(100 + i * 0.5)))

    tp = resolve_take_profit(_signal(), profile, candles)
    assert tp is not None


def test_should_time_stop_after_flat_period() -> None:
    profile = load_profile("caixa_rapido")
    assert profile is not None
    opened = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    trade = TradeRecord(
        id=1,
        alert_id=1,
        symbol="BTCUSDT",
        timeframe="15m",
        direction="buy",
        confidence="high",
        status="open",
        entry_price=Decimal("100"),
        exit_price=None,
        stop_loss=Decimal("95"),
        take_profit=Decimal("110"),
        quantity=Decimal("1"),
        quote_amount=Decimal("100"),
        pnl_usdt=None,
        pnl_pct=None,
        fees_usdt=None,
        context_verdict="confirm",
        context_score=70,
        exchange_order_id="1",
        stop_order_id=None,
        tp_order_id=None,
        close_reason=None,
        trading_mode="testnet",
        opened_at=opened,
        closed_at=None,
        created_at=opened,
        profile_id="caixa_rapido",
    )
    candles = [
        _candle(opened + timedelta(minutes=15 * i), "100.1")
        for i in range(10)
    ]
    assert should_time_stop(trade, profile, candles) is True


def test_position_monitor_applies_time_stop() -> None:
    profile = load_profile("caixa_rapido")
    assert profile is not None
    opened = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    trade = TradeRecord(
        id=7,
        alert_id=1,
        symbol="BTCUSDT",
        timeframe="15m",
        direction="buy",
        confidence="high",
        status="open",
        entry_price=Decimal("100"),
        exit_price=None,
        stop_loss=Decimal("95"),
        take_profit=Decimal("110"),
        quantity=Decimal("1"),
        quote_amount=Decimal("100"),
        pnl_usdt=None,
        pnl_pct=None,
        fees_usdt=None,
        context_verdict="confirm",
        context_score=70,
        exchange_order_id="1",
        stop_order_id=None,
        tp_order_id=None,
        close_reason=None,
        trading_mode="testnet",
        opened_at=opened,
        closed_at=None,
        created_at=opened,
        profile_id="caixa_rapido",
    )
    candles = [
        _candle(opened + timedelta(minutes=15 * i), "100.1")
        for i in range(10)
    ]
    source = MagicMock()
    source.fetch_ohlcv.return_value = candles
    broker = MagicMock()
    broker.market_sell.return_value = {"id": "sell-1"}
    broker.parse_filled.return_value = (Decimal("100.1"), Decimal("1"), Decimal("100.1"))
    broker.fetch_ticker_price.return_value = Decimal("100.1")
    repo = MagicMock()
    repo.close_trade.return_value = True

    monitor = PositionMonitor(broker=broker, trade_repo=repo, market_source=source)
    with patch("src.execution.position_monitor.load_profile", return_value=profile):
        closed = monitor._apply_time_stop(trade)

    assert closed is True
    repo.close_trade.assert_called_once()
    assert repo.close_trade.call_args.kwargs["close_reason"] == "time_stop"


def test_position_monitor_executes_first_partial() -> None:
    trade = TradeRecord(
        id=10,
        alert_id=1,
        symbol="BTCUSDT",
        timeframe="4h",
        direction="buy",
        confidence="medium",
        status="open",
        entry_price=Decimal("64040"),
        exit_price=None,
        stop_loss=Decimal("62000"),
        take_profit=Decimal("68000"),
        quantity=Decimal("0.9"),
        quote_amount=Decimal("57636"),
        pnl_usdt=None,
        pnl_pct=None,
        fees_usdt=None,
        context_verdict="caution",
        context_score=50,
        exchange_order_id="1",
        stop_order_id="stop-1",
        tp_order_id=None,
        close_reason=None,
        trading_mode="testnet",
        opened_at=datetime(2026, 6, 14, tzinfo=UTC),
        closed_at=None,
        created_at=datetime(2026, 6, 14, tzinfo=UTC),
        profile_id="divap_ativo",
        take_profit_levels=(
            Decimal("65030"),
            Decimal("66020"),
            Decimal("68000"),
        ),
        remaining_quantity=Decimal("0.9"),
        partials_taken=0,
        realized_pnl_usdt=Decimal("0"),
    )
    broker = MagicMock()
    broker.fetch_ticker_price.return_value = Decimal("65100")
    broker.market_sell.return_value = {"id": "sell-1"}
    broker.parse_filled.return_value = (Decimal("65100"), Decimal("0.3"), Decimal("19530"))
    broker.place_stop_loss_limit.return_value = {"id": "stop-2"}
    broker.cancel_order = MagicMock()
    repo = MagicMock()
    profile = load_profile("divap_ativo")
    assert profile is not None

    monitor = PositionMonitor(broker=broker, trade_repo=repo)
    with patch("src.execution.position_monitor.load_profile", return_value=profile):
        closed = monitor._sync_buy_trade_partials(trade)

    assert closed is False
    broker.market_sell.assert_called_once()
    repo.record_partial_close.assert_called_once()
    broker.cancel_order.assert_called_once()


def test_position_monitor_executes_first_partial_sell() -> None:
    trade = TradeRecord(
        id=11,
        alert_id=1,
        symbol="ETHUSDT",
        timeframe="4h",
        direction="sell",
        confidence="medium",
        status="open",
        entry_price=Decimal("1792.77"),
        exit_price=None,
        stop_loss=Decimal("1900"),
        take_profit=Decimal("1101.01"),
        quantity=Decimal("0.9"),
        quote_amount=Decimal("1613.49"),
        pnl_usdt=None,
        pnl_pct=None,
        fees_usdt=None,
        context_verdict="caution",
        context_score=50,
        exchange_order_id="1",
        stop_order_id=None,
        tp_order_id=None,
        close_reason=None,
        trading_mode="testnet",
        opened_at=datetime(2026, 6, 14, tzinfo=UTC),
        closed_at=None,
        created_at=datetime(2026, 6, 14, tzinfo=UTC),
        profile_id="divap_ativo",
        take_profit_levels=(
            Decimal("1619.83"),
            Decimal("1446.89"),
            Decimal("1101.01"),
        ),
        remaining_quantity=Decimal("0.9"),
        partials_taken=0,
        realized_pnl_usdt=Decimal("0"),
    )
    broker = MagicMock()
    broker.fetch_ticker_price.return_value = Decimal("1610")
    broker.market_buy_quote.return_value = {"id": "buy-1"}
    broker.parse_filled.return_value = (Decimal("1610"), Decimal("0.3"), Decimal("483"))
    repo = MagicMock()
    profile = load_profile("divap_ativo")
    assert profile is not None

    monitor = PositionMonitor(broker=broker, trade_repo=repo)
    with patch("src.execution.position_monitor.load_profile", return_value=profile):
        closed = monitor._sync_sell_trade_partials(trade)

    assert closed is False
    broker.market_buy_quote.assert_called_once()
    repo.record_partial_close.assert_called_once()
    repo.update_stop_loss.assert_called_once_with(
        trade.id,
        trade.entry_price,
        None,
    )


def test_position_monitor_resolves_partial_levels_for_legacy_sell() -> None:
    trade = TradeRecord(
        id=12,
        alert_id=1,
        symbol="ETHUSDT",
        timeframe="4h",
        direction="sell",
        confidence="medium",
        status="open",
        entry_price=Decimal("1792.77"),
        exit_price=None,
        stop_loss=Decimal("1900"),
        take_profit=Decimal("1101.01"),
        quantity=Decimal("0.9"),
        quote_amount=Decimal("1613.49"),
        pnl_usdt=None,
        pnl_pct=None,
        fees_usdt=None,
        context_verdict="caution",
        context_score=50,
        exchange_order_id="1",
        stop_order_id=None,
        tp_order_id=None,
        close_reason=None,
        trading_mode="testnet",
        opened_at=datetime(2026, 6, 14, tzinfo=UTC),
        closed_at=None,
        created_at=datetime(2026, 6, 14, tzinfo=UTC),
        profile_id="divap_ativo",
        take_profit_levels=None,
        remaining_quantity=None,
        partials_taken=0,
        realized_pnl_usdt=None,
    )
    broker = MagicMock()
    broker.fetch_ticker_price.return_value = Decimal("2000")
    repo = MagicMock()
    profile = load_profile("divap_ativo")
    assert profile is not None

    monitor = PositionMonitor(broker=broker, trade_repo=repo)
    with patch("src.execution.position_monitor.load_profile", return_value=profile):
        closed = monitor._sync_sell_trade(trade)

    assert closed is False
    broker.market_buy_quote.assert_not_called()
