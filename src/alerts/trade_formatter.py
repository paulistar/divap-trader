from decimal import Decimal

from src.execution.trade_executor import TradeExecutionResult


def _fmt(value: Decimal | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2f}"


def format_trade_execution(result: TradeExecutionResult) -> str:
    direction = "COMPRA" if result.direction == "buy" else "VENDA"
    status_icon = "✅" if result.executed else "⏭️"

    message = (
        f"{status_icon} <b>Execução {direction} — {result.symbol}</b>\n"
        f"Status: {'executado' if result.executed else 'ignorado'}\n"
        f"Motivo: {result.reason}"
    )

    if result.executed and result.entry_price:
        message += (
            f"\nEntrada: {_fmt(result.entry_price)}"
            f"\nQuantidade: {_fmt(result.quantity)}"
            f"\nValor: {_fmt(result.quote_amount)} USDT"
        )
        if result.trade_id:
            message += f"\nTrade ID: #{result.trade_id}"

    return message


def format_trade_closed(
    trade_id: int,
    symbol: str,
    direction: str,
    exit_price: Decimal,
    pnl_usdt: Decimal,
    pnl_pct: Decimal,
    reason: str,
) -> str:
    direction_label = "COMPRA" if direction == "buy" else "VENDA"
    pnl_icon = "🟢" if pnl_usdt >= 0 else "🔴"
    reason_labels = {
        "take_profit": "Alvo atingido",
        "stop_loss": "Stop loss",
        "manual": "Manual",
    }

    return (
        f"{pnl_icon} <b>Trade fechado — {symbol}</b>\n"
        f"ID: #{trade_id} | {direction_label}\n"
        f"Saída: {_fmt(exit_price)}\n"
        f"PnL: {_fmt(pnl_usdt)} USDT ({pnl_pct:.2f}%)\n"
        f"Motivo: {reason_labels.get(reason, reason)}"
    )
