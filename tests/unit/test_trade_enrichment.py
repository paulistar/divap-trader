from datetime import UTC, datetime
from decimal import Decimal

from src.data.repositories.trade_repo import TradeRecord
from src.trading.trade_enrichment import enrich_trade_for_dashboard


def _trade(**kwargs) -> TradeRecord:
    base = dict(
        id=1,
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
        quantity=Decimal("0.1"),
        quote_amount=Decimal("6404"),
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
        opened_at=datetime(2026, 6, 15, tzinfo=UTC),
        closed_at=None,
        created_at=datetime(2026, 6, 15, tzinfo=UTC),
        profile_id="divap_ativo",
        take_profit_levels=None,
        remaining_quantity=Decimal("0.1"),
        partials_taken=1,
        realized_pnl_usdt=Decimal("10"),
    )
    base.update(kwargs)
    return TradeRecord(**base)


def test_enrich_trade_open_with_partial_hit() -> None:
    trade = _trade()
    data = enrich_trade_for_dashboard(trade, {"BTCUSDT": Decimal("65100")})
    assert data["current_price"] == "65100"
    assert data["target_hits"] == [True, False, False]
    assert len(data["target_prices"]) == 3


def test_enrich_trade_closed_take_profit() -> None:
    trade = _trade(
        status="closed",
        exit_price=Decimal("68000"),
        close_reason="take_profit",
        partials_taken=0,
    )
    data = enrich_trade_for_dashboard(trade, {})
    assert data["exit_display"] == "68000"
    assert data["target_hits"] == [True, True, True]
