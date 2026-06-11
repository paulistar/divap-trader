from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.core.exceptions import DataNotFoundError
from src.data.models.candle import Candle
from src.data.repositories.candle_repo import CandleRepository


def _sample_candle() -> Candle:
    return Candle(
        symbol="BTCUSDT",
        timeframe="1h",
        timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        volume=Decimal("1000"),
    )


def test_upsert_many_empty_returns_zero() -> None:
    repo = CandleRepository()
    assert repo.upsert_many([]) == 0


@patch("src.data.repositories.candle_repo.execute_values")
@patch("src.data.repositories.candle_repo.psycopg2.connect")
def test_upsert_many_calls_execute_values(
    mock_connect: MagicMock,
    mock_execute_values: MagicMock,
) -> None:
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    repo = CandleRepository(database_url="postgresql://test")
    count = repo.upsert_many([_sample_candle()])

    assert count == 1
    mock_execute_values.assert_called_once()
    mock_conn.commit.assert_called_once()


@patch("src.data.repositories.candle_repo.psycopg2.connect")
def test_get_recent_raises_when_empty(mock_connect: MagicMock) -> None:
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = []
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    repo = CandleRepository(database_url="postgresql://test")
    with pytest.raises(DataNotFoundError):
        repo.get_recent("BTCUSDT", "1h", limit=10)


@patch("src.data.repositories.candle_repo.psycopg2.connect")
def test_get_recent_returns_chronological_order(mock_connect: MagicMock) -> None:
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = [
        (
            "BTCUSDT",
            "1h",
            datetime(2024, 1, 1, 13, 0, tzinfo=UTC),
            Decimal("105"),
            Decimal("115"),
            Decimal("95"),
            Decimal("110"),
            Decimal("2000"),
        ),
        (
            "BTCUSDT",
            "1h",
            datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
            Decimal("100"),
            Decimal("110"),
            Decimal("90"),
            Decimal("105"),
            Decimal("1000"),
        ),
    ]
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    repo = CandleRepository(database_url="postgresql://test")
    candles = repo.get_recent("BTCUSDT", "1h", limit=2)

    assert len(candles) == 2
    assert candles[0].timestamp < candles[1].timestamp
