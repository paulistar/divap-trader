from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import yaml

from src.profiles.models import ProfileAdvisorRules, ProfileExecution, ProfileScan, TradingProfile

_PROFILES_DIR = Path(__file__).resolve().parent
_DEFAULT_ORDER = ("divap", "conservador", "caixa_rapido", "agressivo")


def _parse_profile(data: dict) -> TradingProfile:
    execution_raw = data["execution"]
    advisor_raw = data["advisor"]
    scan_raw = data.get("scan") or {}
    allowed_tfs = tuple(execution_raw.get("allowed_timeframes", ("4h",)))
    return TradingProfile(
        id=data["id"],
        name=data["name"],
        tagline=data.get("tagline", ""),
        description=data.get("description", ""),
        execution=ProfileExecution(
            min_confidence=execution_raw["min_confidence"],
            block_on_reject=bool(execution_raw.get("block_on_reject", True)),
            min_risk_reward=Decimal(str(execution_raw.get("min_risk_reward", "2.0"))),
            max_open_trades=int(execution_raw.get("max_open_trades", 5)),
            allowed_timeframes=allowed_tfs,
            allocation_multiplier=Decimal(str(execution_raw.get("allocation_multiplier", "1.0"))),
        ),
        advisor=ProfileAdvisorRules(
            ideal_fear_greed_min=int(advisor_raw.get("ideal_fear_greed_min", 20)),
            ideal_fear_greed_max=int(advisor_raw.get("ideal_fear_greed_max", 80)),
            preferred_verdicts=tuple(advisor_raw.get("preferred_verdicts", ("confirm",))),
            min_avg_score=int(advisor_raw.get("min_avg_score", 35)),
            volatility=str(advisor_raw.get("volatility", "medium")),
            needs_momentum=bool(advisor_raw.get("needs_momentum", False)),
        ),
        scan=ProfileScan(
            interval_seconds=int(scan_raw.get("interval_seconds", 900)),
            timeframes=tuple(scan_raw.get("timeframes", allowed_tfs)),
            symbols=tuple(scan_raw["symbols"]) if scan_raw.get("symbols") else None,
            monitor_interval_seconds=int(scan_raw.get("monitor_interval_seconds", 300)),
        ),
    )


@lru_cache
def load_profile(profile_id: str) -> TradingProfile | None:
    path = _PROFILES_DIR / f"{profile_id}.yaml"
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _parse_profile(data)


@lru_cache
def load_all_profiles() -> tuple[TradingProfile, ...]:
    profiles: list[TradingProfile] = []
    for profile_id in _DEFAULT_ORDER:
        profile = load_profile(profile_id)
        if profile:
            profiles.append(profile)
    for path in sorted(_PROFILES_DIR.glob("*.yaml")):
        if path.stem not in _DEFAULT_ORDER:
            profile = load_profile(path.stem)
            if profile:
                profiles.append(profile)
    return tuple(profiles)


def protected_execution_profile() -> ProfileExecution:
    """Após meta mensal atingida — só entradas de alta certeza."""
    base = load_profile("conservador")
    if base is None:
        return ProfileExecution(
            min_confidence="high",
            block_on_reject=True,
            min_risk_reward=Decimal("2.5"),
            max_open_trades=1,
            allowed_timeframes=("4h", "1d"),
            allocation_multiplier=Decimal("0.35"),
        )
    return ProfileExecution(
        min_confidence="high",
        block_on_reject=True,
        min_risk_reward=base.execution.min_risk_reward,
        max_open_trades=1,
        allowed_timeframes=base.execution.allowed_timeframes,
        allocation_multiplier=Decimal("0.35"),
    )
