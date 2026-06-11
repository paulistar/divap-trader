from abc import ABC, abstractmethod

from src.data.models.candle import Candle


class MarketDataSource(ABC):
    """Abstract market data source — Binance MVP, OANDA Fase 2."""

    @abstractmethod
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> list[Candle]:
        """Fetch OHLCV candles for symbol/timeframe."""


# Backward-compatible alias (ADR 002)
ExchangeSource = MarketDataSource
