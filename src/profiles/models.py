from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


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


@dataclass(frozen=True, slots=True)
class TradingProfile:
    id: str
    name: str
    tagline: str
    description: str
    execution: ProfileExecution
    advisor: ProfileAdvisorRules
    scan: ProfileScan


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
