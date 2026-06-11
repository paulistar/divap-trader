from src.profiles.advisor import assess_profile
from src.profiles.loader import load_profile


def test_assess_profile_returns_status() -> None:
    profile = load_profile("divap")
    assert profile is not None
    market = {
        "fear_greed": 45,
        "dominant_verdict": "confirm",
        "avg_context_score": 55,
        "market_cap_change_24h_pct": 1.5,
    }
    result = assess_profile(profile, market, active_profile_id="divap")
    assert result.is_active is True
    assert result.fit_score >= 50
    assert result.status in ("otimo", "bom", "neutro", "ruim")


def test_caixa_rapido_penalized_low_volatility() -> None:
    profile = load_profile("caixa_rapido")
    assert profile is not None
    low_vol = {
        "fear_greed": 50,
        "dominant_verdict": "confirm",
        "avg_context_score": 50,
        "market_cap_change_24h_pct": 0.2,
    }
    high_vol = {**low_vol, "market_cap_change_24h_pct": 3.5}
    low = assess_profile(profile, low_vol, active_profile_id="divap")
    high = assess_profile(profile, high_vol, active_profile_id="divap")
    assert high.fit_score > low.fit_score
