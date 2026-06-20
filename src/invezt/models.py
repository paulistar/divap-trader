"""Briefings Maia / Invezt PREMIUM para contexto Binance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

BriefingKind = Literal["crypto", "forex", "closing", "unknown"]
PickBias = Literal["bullish", "bearish", "neutral", "watch"]


@dataclass(frozen=True, slots=True)
class CryptoPick:
    symbol: str
    bias: PickBias
    note: str | None = None


@dataclass(frozen=True, slots=True)
class ForexPick:
    pair: str
    direction: Literal["buy", "sell"]
    note: str | None = None


@dataclass(frozen=True, slots=True)
class InveztBriefing:
    kind: BriefingKind
    title: str
    headline: str | None
    strategic_summary: str | None
    crypto_picks: tuple[CryptoPick, ...]
    forex_picks: tuple[ForexPick, ...]
    raw_text: str
    source_label: str = "Maia / Invezt"

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "title": self.title,
            "headline": self.headline,
            "strategic_summary": self.strategic_summary,
            "source_label": self.source_label,
            "crypto_picks": [
                {"symbol": p.symbol, "bias": p.bias, "note": p.note}
                for p in self.crypto_picks
            ],
            "forex_picks": [
                {"pair": p.pair, "direction": p.direction, "note": p.note}
                for p in self.forex_picks
            ],
            "received_at": None,
        }
