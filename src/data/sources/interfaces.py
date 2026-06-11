from abc import ABC, abstractmethod

from src.data.models.candle import Candle


class ExchangeSource(ABC):
    """Abstract market data source — Binance MVP, Bybit Fase 3."""

    @abstractmethod
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> list[Candle]:
        """Fetch OHLCV candles for symbol/timeframe."""
