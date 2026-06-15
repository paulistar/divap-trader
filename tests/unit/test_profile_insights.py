from unittest.mock import MagicMock, patch

from src.profiles.advisor import assess_profile
from src.profiles.llm_insights import _parse_insights, generate_profile_insights
from src.profiles.loader import load_profile


def test_parse_insights_json() -> None:
    raw = '{"divap": "Bom para swing.", "conservador": "Aguarde."}'
    parsed = _parse_insights(raw)
    assert parsed["divap"] == "Bom para swing."


def test_generate_profile_insights_without_api_key() -> None:
    profile = load_profile("divap")
    assert profile is not None
    market = {"fear_greed": 50, "dominant_verdict": "confirm", "avg_context_score": 55}
    assessment = assess_profile(profile, market, active_profile_ids=["divap"])
    from src.profiles.models import ProfileSnapshot

    snap = ProfileSnapshot(profile=profile, assessment=assessment)
    with patch("src.profiles.llm_insights.settings") as mock_settings:
        mock_settings.openai_api_key = ""
        result = generate_profile_insights(market, [snap], active_profile_id="divap")
    assert result == {}


def test_generate_profile_insights_uses_cache() -> None:
    profile = load_profile("divap")
    assert profile is not None
    market = {"fear_greed": 50, "dominant_verdict": "confirm", "avg_context_score": 55}
    assessment = assess_profile(profile, market, active_profile_ids=["divap"])
    from src.profiles.models import ProfileSnapshot

    snap = ProfileSnapshot(profile=profile, assessment=assessment)
    with patch("src.profiles.llm_insights.settings") as mock_settings:
        mock_settings.openai_api_key = "sk-test"
        with patch("src.profiles.llm_insights.cache_get", return_value={"divap": "cached"}):
            result = generate_profile_insights(market, [snap], active_profile_id="divap")
    assert result["divap"] == "cached"
