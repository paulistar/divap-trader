from decimal import Decimal

from src.detection.divap_scanner import DIVAPSignal
from src.execution.trade_executor import TradeExecutionResult


def _fmt(value: Decimal | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2f}"


def format_trade_opened(
    signal: DIVAPSignal,
    result: TradeExecutionResult,
    *,
    profile_name: str,
) -> str:
    """Telegram quando uma ordem é efetivamente aberta (testnet/live/dry-run)."""
    direction = "COMPRA" if result.direction == "buy" else "VENDA"
    confidence = "ALTA" if signal.confidence == "high" else "MÉDIA"
    dry = result.reason == "dry_run"
    mode = " (simulado)" if dry else ""

    message = (
        f"✅ <b>Trade aberto{mode} — {result.symbol}</b>\n"
        f"Perfil: {profile_name}\n"
        f"{direction} · {signal.timeframe} · Confiança {confidence}\n"
    )
    if result.entry_price:
        message += (
            f"Entrada: {_fmt(result.entry_price)}\n"
            f"Quantidade: {_fmt(result.quantity)}\n"
            f"Valor: {_fmt(result.quote_amount)} USDT"
        )
    if result.trade_id:
        message += f"\nTrade ID: #{result.trade_id}"
    return message


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


def format_trade_partial(
    trade_id: int,
    symbol: str,
    direction: str,
    target_index: int,
    target_total: int,
    exit_price: Decimal,
    partial_pnl_usdt: Decimal,
    remaining_quantity: Decimal,
) -> str:
    direction_label = "COMPRA" if direction == "buy" else "VENDA"
    pnl_icon = "🟢" if partial_pnl_usdt >= 0 else "🔴"
    return (
        f"{pnl_icon} <b>Alvo {target_index}/{target_total} — {symbol}</b>\n"
        f"ID: #{trade_id} | {direction_label}\n"
        f"Saída parcial: {_fmt(exit_price)}\n"
        f"PnL parcial: {_fmt(partial_pnl_usdt)} USDT\n"
        f"Restante: {_fmt(remaining_quantity)}"
    )


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
