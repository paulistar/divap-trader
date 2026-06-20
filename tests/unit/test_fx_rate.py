import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from src.api.fx_rate import fetch_usd_brl_rate
from src.core.exceptions import ExchangeError


def test_fetch_usd_brl_rate_frankfurter() -> None:
    with patch("src.api.fx_rate._fetch_frankfurter", new_callable=AsyncMock) as mock_ff:
        mock_ff.return_value = Decimal("5.4321")
        rate, source, fetched_at = asyncio.run(fetch_usd_brl_rate())
    assert rate == Decimal("5.4321")
    assert source == "Frankfurter"
    assert fetched_at.tzinfo is not None


def test_fetch_usd_brl_rate_falls_back_to_awesomeapi() -> None:
    with patch("src.api.fx_rate._fetch_frankfurter", new_callable=AsyncMock) as mock_ff:
        mock_ff.side_effect = RuntimeError("down")
        with patch("src.api.fx_rate._fetch_awesomeapi", new_callable=AsyncMock) as mock_aa:
            mock_aa.return_value = Decimal("5.41")
            rate, source, _ = asyncio.run(fetch_usd_brl_rate())
    assert rate == Decimal("5.41")
    assert source == "AwesomeAPI"


def test_fetch_usd_brl_rate_raises_when_all_fail() -> None:
    with patch("src.api.fx_rate._fetch_frankfurter", new_callable=AsyncMock) as mock_ff:
        mock_ff.side_effect = RuntimeError("down")
        with patch("src.api.fx_rate._fetch_awesomeapi", new_callable=AsyncMock) as mock_aa:
            mock_aa.side_effect = RuntimeError("down too")
            with pytest.raises(ExchangeError):
                asyncio.run(fetch_usd_brl_rate())
