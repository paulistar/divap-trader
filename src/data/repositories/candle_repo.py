from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal

import psycopg2
from psycopg2.extras import execute_values

from src.core.config import settings
from src.core.exceptions import DataNotFoundError
from src.data.models.candle import Candle

UPSERT_SQL = """
INSERT INTO candles (symbol, timeframe, ts, open, high, low, close, volume)
VALUES %s
ON CONFLICT (symbol, timeframe, ts) DO UPDATE SET
    open = EXCLUDED.open,
    high = EXCLUDED.high,
    low = EXCLUDED.low,
    close = EXCLUDED.close,
    volume = EXCLUDED.volume
"""

SELECT_RECENT_SQL = """
SELECT symbol, timeframe, ts, open, high, low, close, volume
FROM candles
WHERE symbol = %s AND timeframe = %s
ORDER BY ts DESC
LIMIT %s
"""


class CandleRepository:
    def __init__(self, database_url: str | None = None) -> None:
        self._database_url = database_url or settings.database_url

    @contextmanager
    def _connection(self):
        conn = psycopg2.connect(self._database_url)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def upsert_many(self, candles: list[Candle]) -> int:
        if not candles:
            return 0

        rows = [c.to_row() for c in candles]
        with self._connection() as conn:
            with conn.cursor() as cur:
                execute_values(cur, UPSERT_SQL, rows)
        return len(rows)

    def get_recent(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> list[Candle]:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(SELECT_RECENT_SQL, (symbol, timeframe, limit))
                rows = cur.fetchall()

        if not rows:
            raise DataNotFoundError(
                f"No candles for {symbol} {timeframe}"
            )

        candles = [
            Candle(
                symbol=row[0],
                timeframe=row[1],
                timestamp=row[2],
                open=Decimal(str(row[3])),
                high=Decimal(str(row[4])),
                low=Decimal(str(row[5])),
                close=Decimal(str(row[6])),
                volume=Decimal(str(row[7])),
            )
            for row in rows
        ]
        # Return chronological order (oldest first)
        return list(reversed(candles))
