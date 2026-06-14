from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PartialTakeProfitLevel:
    distance_pct: int


@dataclass(frozen=True, slots=True)
class ProfileExit:
    take_profit_fibo: Decimal | None
    time_stop_candles: int
    time_stop_min_move_pct: Decimal
    time_stop_timeframes: tuple[str, ...]
    partial_take_profits: tuple[PartialTakeProfitLevel, ...] = ()
    move_stop_to_breakeven_after: int = 0


@dataclass(frozen=True, slots=True)
class ProfileScan:
    interval_seconds: int
    timeframes: tuple[str, ...]
    symbols: tuple[str, ...] | None
    monitor_interval_seconds: int


@dataclass(frozen=True, slots=True)
class ProfileAdvisorRules:
    ideal_fear_greed_min: int
    ideal_fear_greed_max: int
    preferred_verdicts: tuple[str, ...]
    min_avg_score: int
    volatility: str
    needs_momentum: bool


@dataclass(frozen=True, slots=True)
class ProfileExecution:
    min_confidence: str
    block_on_reject: bool
    min_risk_reward: Decimal
    max_open_trades: int
    allowed_timeframes: tuple[str, ...]
    allocation_multiplier: Decimal
    min_risk_reward_by_timeframe: dict[str, Decimal] | None = None


@dataclass(frozen=True, slots=True)
class TradingProfile:
    id: str
    name: str
    tagline: str
    description: str
    execution: ProfileExecution
    advisor: ProfileAdvisorRules
    scan: ProfileScan
    exit: ProfileExit


@dataclass(frozen=True, slots=True)
class ProfileAssessment:
    profile_id: str
    fit_score: int
    status: str
    headline: str
    detail: str
    is_active: bool


@dataclass(frozen=True, slots=True)
class ProfileSnapshot:
    profile: TradingProfile
    assessment: ProfileAssessment
