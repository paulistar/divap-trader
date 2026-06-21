"""Tests for MCP settlement matching across martingale legs."""

from decimal import Decimal
from unittest.mock import patch

from src.otc.broker import IqOptionBroker
from src.otc.models import OtcSettlementContext


def _ctx(
    *,
    order_id: str = "1001",
    stake: str = "11",
    position_id: int | None = 42,
) -> OtcSettlementContext:
    return OtcSettlementContext(
        transport="mcp",
        resolved_asset="Litecoin (OTC)",
        direction="buy",
        stake_usd=Decimal(stake),
        duration_minutes=1,
        order_id=order_id,
        mcp_asset_id=77,
        mcp_position_id=position_id,
    )


def test_poll_settlement_prefers_position_id_from_context() -> None:
    broker = IqOptionBroker()
    ctx = _ctx(position_id=42)

    with patch("src.otc.broker.mcp_call") as mock_call:
        mock_call.side_effect = [
            {"positions": []},
            {
                "history": [
                    {
                        "position_id": 99,
                        "order_id": 1000,
                        "asset_id": 77,
                        "amount": 11,
                        "profit": -5,
                    },
                    {
                        "position_id": 42,
                        "order_id": 1002,
                        "asset_id": 77,
                        "amount": 11,
                        "profit": 9.57,
                    },
                ]
            },
        ]
        pnl = broker._poll_settlement_mcp_once(ctx)

    assert pnl == Decimal("9.57")


def test_poll_settlement_matches_order_id_as_int_or_str() -> None:
    broker = IqOptionBroker()
    ctx = _ctx(order_id="1001", position_id=None)

    with patch("src.otc.broker.mcp_call") as mock_call:
        mock_call.side_effect = [
            {"positions": []},
            {
                "history": [
                    {
                        "position_id": 55,
                        "order_id": 1001,
                        "asset_id": 77,
                        "amount": 11,
                        "profit": -11,
                    }
                ]
            },
        ]
        pnl = broker._poll_settlement_mcp_once(ctx)

    assert pnl == Decimal("-11")


def test_open_binary_mcp_seeds_position_id() -> None:
    broker = IqOptionBroker()
    signal = __import__("src.otc.models", fromlist=["OtcSignal"]).OtcSignal(
        asset="Litecoin (OTC)",
        direction="buy",
        expiry_minutes=1,
    )

    with patch.object(broker, "_config") as mock_config:
        mock_config.dry_run = False
        mock_config.account_mode = "PRACTICE"
        mock_config.default_stake_usd = Decimal("5")
        with patch("src.otc.broker.iqoption_configured", return_value=True):
            with patch("src.otc.broker.otc_transport", return_value="mcp"):
                with patch("src.otc.broker.fetch_mcp_balance", return_value=(Decimal("1000"), 1)):
                    with patch("src.otc.broker.mcp_find_asset_id", return_value=(77, "Litecoin (OTC)")):
                        with patch(
                            "src.otc.broker.mcp_pick_instrument",
                            return_value=("inst-1", 0),
                        ):
                            with patch(
                                "src.otc.broker.mcp_call",
                                side_effect=[
                                    {"order_id": 9001},
                                    {
                                        "positions": [
                                            {
                                                "position_id": 321,
                                                "asset_id": 77,
                                                "amount": 11,
                                                "order_id": 9001,
                                            }
                                        ]
                                    },
                                ],
                            ):
                                open_result, ctx = broker._open_binary_mcp(
                                    signal,
                                    "Litecoin (OTC)",
                                    Decimal("11"),
                                )

    assert open_result.executed is True
    assert ctx.mcp_position_id == 321
    assert ctx.order_id == "9001"
