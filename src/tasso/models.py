"""Sinais Financial Move Bot → Binance (perfis Tasso)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

TassoVariant = Literal["curto", "long"]
TassoSignalKind = Literal["new", "update", "stop_hit"]


@dataclass(frozen=True, slots=True)
class TassoSignal:
    profile_id: str
    variant: TassoVariant
    symbol: str | None
    direction: Literal["buy", "sell"] | None
    timeframe: str
    entry_price: Decimal | None
    stop_loss: Decimal | None
    take_profit: Decimal | None
    raw_alert_text: str
    raw_detail_text: str | None = None
    signal_kind: TassoSignalKind = "new"
    take_profit_levels: tuple[Decimal, ...] | None = None
    targets_hit: int = 0
    allocation_pct: Decimal | None = None
    leverage: int | None = None


@dataclass(frozen=True, slots=True)
class TassoMessageAction:
    """Próximo passo ao processar mensagem do Financial Move Bot."""

    action: Literal[
        "request_details",
        "parse_detail",
        "close_stop_hit",
        "ignore",
    ]
    profile_id: str | None = None
    variant: TassoVariant | None = None
    symbol_hint: str | None = None
    direction_hint: Literal["buy", "sell"] | None = None
