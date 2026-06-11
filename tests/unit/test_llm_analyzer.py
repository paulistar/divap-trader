from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.core.exceptions import AnalysisError
from src.detection.divap_scanner import DIVAPCriteria, DIVAPSignal
from src.analysis.llm_analyzer import LLMAnalyzer


def _signal(confluences: int = 3) -> DIVAPSignal:
    return DIVAPSignal(
        symbol="BTCUSDT",
        timeframe="4h",
        direction="buy",
        confidence="medium",
        criteria=DIVAPCriteria(
            divergence=True,
            volume=confluences >= 2,
            fibonacci=confluences >= 3,
            pattern=confluences >= 4,
        ),
        entry_price=Decimal("100"),
        stop_loss=Decimal("95"),
        targets=(Decimal("110"),),
        current_price=Decimal("100"),
        rsi_value=30.0,
        volume_ratio=1.5,
        divergence_type="bullish",
        pattern_detected="hammer",
        fibo_level=Decimal("1.0"),
        timestamp=datetime(2024, 6, 1, tzinfo=UTC),
    )


def test_analyze_rejects_low_confluence() -> None:
    analyzer = LLMAnalyzer(client=MagicMock())
    with pytest.raises(AnalysisError):
        analyzer.analyze(_signal(confluences=2))


@patch("src.analysis.llm_analyzer.settings")
def test_analyze_returns_content(mock_settings) -> None:
    mock_settings.openai_api_key = "test-key"
    mock_settings.openai_model = "gpt-4o"

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "## Validação DIVAP\nOK"
    mock_client.chat.completions.create.return_value = mock_response

    analyzer = LLMAnalyzer(client=mock_client)
    result = analyzer.analyze(_signal(confluences=3))

    assert "Validação DIVAP" in result
    mock_client.chat.completions.create.assert_called_once()
