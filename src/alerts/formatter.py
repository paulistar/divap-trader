from decimal import Decimal

from src.core.constants import BANK_ALLOCATION_PCT
from src.context.models import MarketContext
from src.detection.divap_scanner import DIVAPSignal

HTF_LABELS = {
    "bullish": "alta",
    "bearish": "baixa",
    "sideways": "lateral",
    "unknown": "desconhecida",
}


def _htf_label(bias: str | None) -> str:
    if not bias:
        return "?"
    return HTF_LABELS.get(bias, bias)


def _fmt_price(value: Decimal) -> str:
    return f"{value:.2f}"


def format_divap_alert(
    signal: DIVAPSignal,
    analysis: str | None = None,
    market_context: MarketContext | None = None,
) -> str:
    bank = BANK_ALLOCATION_PCT.get(signal.timeframe, (4, 6))
    direction_label = "COMPRA" if signal.direction == "buy" else "VENDA"
    confidence_label = "ALTA" if signal.confidence == "high" else "MÉDIA"

    criteria = signal.criteria
    checklist = (
        f"{'✅' if criteria.divergence else '❌'} Divergência IFR\n"
        f"{'✅' if criteria.volume else '❌'} Volume\n"
        f"{'✅' if criteria.fibonacci else '❌'} Alvo Fibonacci\n"
        f"{'✅' if criteria.pattern else '❌'} Padrão reversão"
    )

    targets = ", ".join(_fmt_price(t) for t in signal.targets[:3]) or "N/A"

    message = (
        f"🔔 <b>Setup DIVAP — {signal.symbol}</b>\n"
        f"Timeframe: {signal.timeframe} | Confiança: {confidence_label}\n\n"
        f"<b>{direction_label}</b>\n"
        f"Entrada: {_fmt_price(signal.entry_price)}\n"
        f"Stop: {_fmt_price(signal.stop_loss)}\n"
        f"Alvos: {targets}\n\n"
        f"RSI: {signal.rsi_value:.1f} | Vol ratio: {signal.volume_ratio:.2f}x\n"
        f"Fibo: {signal.fibo_level or 'N/A'} | Padrão: {signal.pattern_detected or 'N/A'}\n\n"
        f"<b>Checklist D-V-A-P:</b>\n{checklist}\n\n"
        f"💰 Banca sugerida: {bank[0]}–{bank[1]}% (timeframe {signal.timeframe})"
    )

    if market_context:
        fg = market_context.fear_greed
        fg_line = (
            f"{fg.value} ({fg.classification})" if fg else "N/A"
        )
        message += (
            f"\n\n<b>Contexto mercado:</b>\n"
            f"Score: {market_context.context_score}/100 | "
            f"Veredito: {market_context.context_verdict}\n"
            f"Fear &amp; Greed: {fg_line}\n"
            f"HTF 1d/1w: {_htf_label(market_context.htf_trends.get('1d'))}/"
            f"{_htf_label(market_context.htf_trends.get('1w'))}"
        )

    if analysis:
        truncated = analysis[:1500] + "..." if len(analysis) > 1500 else analysis
        message += f"\n\n<b>Análise IA:</b>\n{truncated}"

    return message
