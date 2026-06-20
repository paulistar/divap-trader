"""Parse mensagens do Financial Move Bot 3.0."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from src.tasso.models import TassoMessageAction, TassoSignal, TassoVariant

_LONG_SYMBOL_RE = re.compile(
    r"\b([A-Z0-9]{2,15}USDT)\s*\(\s*LONG\s*\)",
    re.IGNORECASE,
)
_SHORT_SYMBOL_RE = re.compile(
    r"\b([A-Z0-9]{2,15}USDT)\s*\(\s*SHORT\s*\)",
    re.IGNORECASE,
)
_SYMBOL_RE = re.compile(r"\b([A-Z0-9]{2,15}USDT)\b", re.IGNORECASE)
_TRADE_CURTO_RE = re.compile(r"TRADE\s+CURTO", re.IGNORECASE)
_CURTO_RISK_PROMPT_RE = re.compile(
    r"trade\s+curto\s+com\s+alto\s+risco",
    re.IGNORECASE,
)
_CURTO_DETAIL_MARKER_RE = re.compile(
    r"trade\s+mais\s+curto\s+e\s+mais\s+agressivo",
    re.IGNORECASE,
)
_LONG_DETAIL_MARKER_RE = re.compile(
    r"operações\s+alavancadas\s+são\s+de\s+alto\s+risco",
    re.IGNORECASE,
)
_TEASER_RE = re.compile(
    r"trade\s+novo|clique\s+no\s+botão\s+abaixo\s+para\s+ver\s+os\s+detalhes",
    re.IGNORECASE,
)
_STOP_HIT_RE = re.compile(r"hora\s+de\s+parar", re.IGNORECASE)
_STOP_HIT_SYMBOL_RE = re.compile(
    r"stop\s+atingido\s+em\s+#?\s*([A-Z0-9]{2,20})",
    re.IGNORECASE,
)
_UPDATE_MARKER_RE = re.compile(
    r"(?:stoploss\s+atualizado|stoploss\s+antigo|✅\s*\d+[ªa°]?\s*zona\s+de\s+venda)",
    re.IGNORECASE,
)
_BUY_RANGE_RE = re.compile(
    r"preço\s+para\s+compra\s*[:\-]?\s*([\d.,]+)\s*-\s*([\d.,]+)",
    re.IGNORECASE,
)
_BUY_SINGLE_RE = re.compile(
    r"(?:preço\s+para\s+compra|entrada|entry)\s*[:\-]?\s*\$?\s*([\d.,]+)",
    re.IGNORECASE,
)
_STOP_UPDATED_RE = re.compile(
    r"stoploss\s+atualizado\s*[:\-]?\s*([\d.,]+)",
    re.IGNORECASE,
)
_STOP_RE = re.compile(
    r"stop\s*loss\s*[:\-]?\s*([\d.,]+)",
    re.IGNORECASE,
)
_TP_ZONE_RE = re.compile(
    r"(✅|🔜)\s*\d+[ªa°]?\s*zona\s+de\s+venda\s*[:\-]?\s*([\d.,]+)",
    re.IGNORECASE,
)
_ALLOCATION_RE = re.compile(
    r"alocação\s+de\s+patrimônio\s*[:\-]?\s*([\d.,]+)\s*%?",
    re.IGNORECASE,
)
_LEVERAGE_RE = re.compile(
    r"alavancagem\s*[:\-]?\s*(\d+)",
    re.IGNORECASE,
)
_DETAIL_TF_RE = re.compile(
    r"(?:timeframe|tempo|tf|gráfico|grafico|periodo|período)\s*[:\-]?\s*"
    r"(1m|5m|15m|30m|1h|2h|4h|1d|1w)",
    re.IGNORECASE,
)
_TF_TOKEN_RE = re.compile(r"\b(1m|5m|15m|30m|1h|2h|4h|1d|1w)\b", re.IGNORECASE)

TASSO_FALLBACK_TIMEFRAME = "external"


def _parse_decimal(raw: str) -> Decimal | None:
    cleaned = raw.strip().replace("$", "").replace(" ", "")
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def is_full_trade_detail(text: str) -> bool:
    if not text or not str(text).strip():
        return False
    has_symbol = bool(_LONG_SYMBOL_RE.search(text) or _SHORT_SYMBOL_RE.search(text))
    has_params = bool(_BUY_RANGE_RE.search(text) or _BUY_SINGLE_RE.search(text))
    has_stop = bool(_STOP_UPDATED_RE.search(text) or _STOP_RE.search(text))
    return has_symbol and has_params and has_stop


def normalize_tasso_symbol(raw: str) -> str:
    symbol = raw.upper().strip().lstrip("#")
    if symbol.endswith("USDT"):
        return symbol
    return f"{symbol}USDT"


def is_trade_teaser(text: str) -> bool:
    """Teaser inicial (TRADE NOVO ou TRADE CURTO) antes de solicitar detalhes."""
    if not text or is_full_trade_detail(text):
        return False
    if _CURTO_RISK_PROMPT_RE.search(text):
        return False
    return bool(_TEASER_RE.search(text) or _TRADE_CURTO_RE.search(text))


def is_long_teaser(text: str) -> bool:
    return is_trade_teaser(text) and bool(_TEASER_RE.search(text))


def is_stop_hit_message(text: str) -> bool:
    if not text:
        return False
    return bool(_STOP_HIT_RE.search(text) and _STOP_HIT_SYMBOL_RE.search(text))


def parse_stop_hit(text: str) -> TassoSignal | None:
    if not is_stop_hit_message(text):
        return None
    match = _STOP_HIT_SYMBOL_RE.search(text)
    if not match:
        return None
    symbol = normalize_tasso_symbol(match.group(1))
    return TassoSignal(
        profile_id="tasso_long",
        variant="long",
        symbol=symbol,
        direction=None,
        timeframe=TASSO_FALLBACK_TIMEFRAME,
        entry_price=None,
        stop_loss=None,
        take_profit=None,
        raw_alert_text=text,
        signal_kind="stop_hit",
    )


def is_curto_accept_prompt(text: str) -> bool:
    if not text:
        return False
    if is_full_trade_detail(text):
        return False
    return bool(_TRADE_CURTO_RE.search(text) or _CURTO_RISK_PROMPT_RE.search(text))


def is_trade_update(text: str) -> bool:
    return bool(_UPDATE_MARKER_RE.search(text))


def resolve_profile_from_detail(text: str) -> tuple[str, TassoVariant]:
    """Curto vs long pelo texto de risco — (LONG) aparece nos dois."""
    if _CURTO_DETAIL_MARKER_RE.search(text):
        return "tasso_curto", "curto"
    return "tasso_long", "long"


def classify_message(text: str, *, has_detail_button: bool = False) -> TassoMessageAction | None:
    """
    Decide como tratar mensagem do Financial Move Bot.
    """
    if not text or not str(text).strip():
        return None

    if is_stop_hit_message(text):
        stop = parse_stop_hit(text)
        return TassoMessageAction(
            action="close_stop_hit",
            symbol_hint=stop.symbol if stop else None,
        )

    if is_trade_teaser(text) or (has_detail_button and not is_full_trade_detail(text)):
        return TassoMessageAction(action="request_details")

    if not is_full_trade_detail(text):
        return None

    if not is_trade_update(text):
        return None

    profile_id, variant = resolve_profile_from_detail(text)
    long_match = _LONG_SYMBOL_RE.search(text)
    short_match = _SHORT_SYMBOL_RE.search(text)
    symbol = None
    direction: str | None = None
    if long_match:
        symbol = long_match.group(1).upper()
        direction = "buy"
    elif short_match:
        symbol = short_match.group(1).upper()
        direction = "sell"

    return TassoMessageAction(
        action="parse_detail",
        profile_id=profile_id,
        variant=variant,
        symbol_hint=symbol,
        direction_hint=direction,  # type: ignore[arg-type]
    )


def classify_alert_text(text: str) -> tuple[str, TassoVariant, str | None, str | None] | None:
    """Compatibilidade com testes — retorna classificação para mensagens completas."""
    action = classify_message(text)
    if action is None or action.action == "ignore":
        return None
    if action.action == "request_details":
        return ("tasso_long", "long", None, None)
    if action.action == "parse_detail" and action.profile_id and action.variant:
        return (
            action.profile_id,
            action.variant,
            action.symbol_hint,
            action.direction_hint,
        )
    return None


def _parse_timeframe(text: str) -> str:
    match = _DETAIL_TF_RE.search(text)
    if match:
        return match.group(1).lower()
    token = _TF_TOKEN_RE.search(text)
    if token:
        return token.group(1).lower()
    return TASSO_FALLBACK_TIMEFRAME


def _parse_entry(text: str) -> Decimal | None:
    range_match = _BUY_RANGE_RE.search(text)
    if range_match:
        low = _parse_decimal(range_match.group(1))
        high = _parse_decimal(range_match.group(2))
        if low is not None and high is not None:
            return (low + high) / 2
    single = _BUY_SINGLE_RE.search(text)
    if single:
        return _parse_decimal(single.group(1))
    return None


def _parse_stop(text: str) -> Decimal | None:
    updated = _STOP_UPDATED_RE.search(text)
    if updated:
        return _parse_decimal(updated.group(1))
    stop = _STOP_RE.search(text)
    if stop:
        return _parse_decimal(stop.group(1))
    return None


def _parse_tp_zones(text: str) -> tuple[tuple[Decimal, ...], int]:
    zones: list[Decimal] = []
    hits = 0
    for match in _TP_ZONE_RE.finditer(text):
        price = _parse_decimal(match.group(2))
        if price is None:
            continue
        zones.append(price)
        if match.group(1) == "✅":
            hits += 1
    return tuple(zones), hits


def parse_trade_details(
    text: str,
    *,
    profile_id: str,
    variant: TassoVariant,
    symbol_hint: str | None,
    direction_hint: str | None,
    raw_alert_text: str,
) -> TassoSignal | None:
    if not text or not str(text).strip():
        return None

    detail_profile_id, detail_variant = resolve_profile_from_detail(text)
    profile_id = detail_profile_id
    variant = detail_variant

    symbol = symbol_hint
    long_match = _LONG_SYMBOL_RE.search(text)
    short_match = _SHORT_SYMBOL_RE.search(text)
    if long_match:
        symbol = long_match.group(1).upper()
    elif short_match:
        symbol = short_match.group(1).upper()
    elif not symbol:
        sym_match = _SYMBOL_RE.search(text)
        if sym_match:
            symbol = sym_match.group(1).upper()

    if not symbol:
        return None

    direction = direction_hint
    if long_match:
        direction = "buy"
    elif short_match:
        direction = "sell"
    if direction is None:
        direction = "buy"

    entry = _parse_entry(text)
    stop = _parse_stop(text)
    tp_levels, targets_hit = _parse_tp_zones(text)
    tp = tp_levels[0] if tp_levels else None

    alloc_match = _ALLOCATION_RE.search(text)
    allocation_pct = _parse_decimal(alloc_match.group(1)) if alloc_match else None
    lev_match = _LEVERAGE_RE.search(text)
    leverage = int(lev_match.group(1)) if lev_match else None

    return TassoSignal(
        profile_id=profile_id,
        variant=variant,
        symbol=symbol,
        direction=direction,  # type: ignore[arg-type]
        timeframe=_parse_timeframe(text),
        entry_price=entry,
        stop_loss=stop,
        take_profit=tp,
        raw_alert_text=raw_alert_text,
        raw_detail_text=text,
        signal_kind="update" if is_trade_update(text) else "new",
        take_profit_levels=tp_levels or None,
        targets_hit=targets_hit,
        allocation_pct=allocation_pct,
        leverage=leverage,
    )
