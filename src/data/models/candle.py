from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Candle:
    symbol: str
    timeframe: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    def to_row(self) -> tuple:
        return (
            self.symbol,
            self.timeframe,
            self.timestamp,
            self.open,
            self.high,
            self.low,
            self.close,
            self.volume,
        )
