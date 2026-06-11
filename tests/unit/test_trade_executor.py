from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

from src.context.models import MarketContext
from src.detection.divap_scanner import DIVAPCriteria, DIVAPSignal
from src.execution.trade_executor import TradeExecutor


def _signal() -> DIVAPSignal:
    return DIVAPSignal(
        symbol="BTCUSDT",
        timeframe="4h",
        direction="buy",
        confidence="high",
        criteria=DIVAPCriteria(True, True, True, True),
        entry_price=Decimal("50000"),
        stop_loss=Decimal("48000"),
        targets=(Decimal("54000"),),
        current_price=Decimal("50000"),
        rsi_value=35.0,
        volume_ratio=1.5,
        divergence_type="bullish",
        pattern_detected="hammer",
        fibo_level=Decimal("0.618"),
        timestamp=datetime.now(UTC),
    )


def _context() -> MarketContext:
    return MarketContext(
        symbol="BTCUSDT",
        signal_timeframe="4h",
        fear_greed=None,
        global_market=None,
        htf_trends={},
        macro_indices=(),
        news_headlines=(),
        risk_flags=(),
        context_score=70,
        context_verdict="confirm",
        sources_ok=(),
        sources_failed=(),
    )


@patch("src.execution.trade_executor.settings")
def test_executor_skips_when_trading_disabled(mock_settings: MagicMock) -> None:
    mock_settings.trading_enabled = False
    executor = TradeExecutor(broker=MagicMock(), trade_repo=MagicMock())
    result = executor.try_execute(_signal(), alert_id=1, market_context=_context())
    assert result.executed is False
    assert result.reason == "trading_disabled"


@patch("src.execution.trade_executor.settings")
def test_executor_dry_run_creates_simulated_trade(mock_settings: MagicMock) -> None:
    mock_settings.trading_enabled = True
    mock_settings.trading_mode = "testnet"
    mock_settings.binance_use_testnet = True
    mock_settings.trading_min_confidence = "high"
    mock_settings.trading_block_on_context_reject = True
    mock_settings.trading_max_open_trades = 5
    mock_settings.trading_dry_run = True

    broker = MagicMock()
    broker.get_usdt_balance.return_value = Decimal("10000")
    broker.min_notional.return_value = Decimal("10")

    repo = MagicMock()
    repo.count_open_trades.return_value = 0
    repo.has_open_trade.return_value = False
    repo.create_trade.return_value = 42

    executor = TradeExecutor(broker=broker, trade_repo=repo)
    result = executor.try_execute(_signal(), alert_id=7, market_context=_context())

    assert result.executed is True
    assert result.reason == "dry_run"
    assert result.trade_id == 42
    repo.create_trade.assert_called_once()
    call_kwargs = repo.create_trade.call_args.kwargs
    assert call_kwargs["status"] == "simulated"


@patch("src.execution.trade_executor.settings")
def test_executor_live_buy(mock_settings: MagicMock) -> None:
    mock_settings.trading_enabled = True
    mock_settings.trading_mode = "testnet"
    mock_settings.binance_use_testnet = True
    mock_settings.trading_min_confidence = "high"
    mock_settings.trading_block_on_context_reject = True
    mock_settings.trading_max_open_trades = 5
    mock_settings.trading_dry_run = False

    broker = MagicMock()
    broker.get_usdt_balance.return_value = Decimal("10000")
    broker.min_notional.return_value = Decimal("10")
    broker.market_buy_quote.return_value = {
        "id": "order-1",
        "average": 50000,
        "filled": 0.024,
        "cost": 1200,
    }
    broker.place_stop_loss_limit.return_value = {"id": "stop-1"}
    broker.place_take_profit_limit.return_value = {"id": "tp-1"}
    broker.parse_filled.return_value = (
        Decimal("50000"),
        Decimal("0.024"),
        Decimal("1200"),
    )

    repo = MagicMock()
    repo.count_open_trades.return_value = 0
    repo.has_open_trade.return_value = False
    repo.create_trade.return_value = 99

    executor = TradeExecutor(broker=broker, trade_repo=repo)
    result = executor.try_execute(_signal(), alert_id=3, market_context=_context())

    assert result.executed is True
    assert result.reason == "ok"
    assert result.trade_id == 99
    broker.market_buy_quote.assert_called_once()
