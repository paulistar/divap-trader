from dataclasses import dataclass, field
from typing import Literal

TrendBias = Literal["bullish", "bearish", "sideways", "unknown"]
ContextVerdict = Literal["confirm", "caution", "reject", "unknown"]


@dataclass(frozen=True, slots=True)
class FearGreedReading:
    value: int
    classification: str
    timestamp: str


@dataclass(frozen=True, slots=True)
class GlobalMarketSnapshot:
    btc_dominance_pct: float | None
    market_cap_change_24h_pct: float | None
    total_market_cap_usd: float | None


@dataclass(frozen=True, slots=True)
class MacroIndexSnapshot:
    symbol: str
    label: str
    change_5d_pct: float | None
    trend: TrendBias


@dataclass(frozen=True, slots=True)
class NewsHeadline:
    title: str
    source: str
    published_at: str | None = None
    url: str | None = None


@dataclass(frozen=True, slots=True)
class MarketContext:
    symbol: str
    signal_timeframe: str
    fear_greed: FearGreedReading | None
    global_market: GlobalMarketSnapshot | None
    htf_trends: dict[str, TrendBias]
    macro_indices: tuple[MacroIndexSnapshot, ...]
    news_headlines: tuple[NewsHeadline, ...]
    risk_flags: tuple[str, ...]
    context_score: int
    context_verdict: ContextVerdict
    sources_ok: tuple[str, ...]
    sources_failed: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "signal_timeframe": self.signal_timeframe,
            "fear_greed": (
                {
                    "value": self.fear_greed.value,
                    "classification": self.fear_greed.classification,
                    "timestamp": self.fear_greed.timestamp,
                }
                if self.fear_greed
                else None
            ),
            "global_market": (
                {
                    "btc_dominance_pct": self.global_market.btc_dominance_pct,
                    "market_cap_change_24h_pct": self.global_market.market_cap_change_24h_pct,
                    "total_market_cap_usd": self.global_market.total_market_cap_usd,
                }
                if self.global_market
                else None
            ),
            "htf_trends": dict(self.htf_trends),
            "macro_indices": [
                {
                    "symbol": idx.symbol,
                    "label": idx.label,
                    "change_5d_pct": idx.change_5d_pct,
                    "trend": idx.trend,
                }
                for idx in self.macro_indices
            ],
            "news_headlines": [
                {
                    "title": n.title,
                    "source": n.source,
                    "published_at": n.published_at,
                    "url": n.url,
                }
                for n in self.news_headlines
            ],
            "risk_flags": list(self.risk_flags),
            "context_score": self.context_score,
            "context_verdict": self.context_verdict,
            "sources_ok": list(self.sources_ok),
            "sources_failed": list(self.sources_failed),
        }


@dataclass(frozen=True, slots=True)
class MarketContextParts:
    fear_greed: FearGreedReading | None = None
    global_market: GlobalMarketSnapshot | None = None
    htf_trends: dict[str, TrendBias] = field(default_factory=dict)
    macro_indices: tuple[MacroIndexSnapshot, ...] = ()
    news_headlines: tuple[NewsHeadline, ...] = ()
    sources_ok: tuple[str, ...] = ()
    sources_failed: tuple[str, ...] = ()
