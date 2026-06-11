import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import psycopg2
from psycopg2.extras import Json, RealDictCursor

from src.core.config import settings
from src.detection.divap_scanner import DIVAPSignal

INSERT_ALERT_SQL = """
INSERT INTO alerts (
    symbol, timeframe, direction, confidence, criteria,
    entry_price, stop_loss, targets, rsi_value, volume_ratio,
    divergence_type, pattern_detected, fibo_level
) VALUES (
    %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s,
    %s, %s, %s
) RETURNING id, created_at
"""

INSERT_ANALYSIS_SQL = """
INSERT INTO analyses (alert_id, content, model)
VALUES (%s, %s, %s)
RETURNING id
"""

SELECT_ALERTS_SQL = """
SELECT * FROM alerts ORDER BY created_at DESC LIMIT %s OFFSET %s
"""

SELECT_ALERT_SQL = """
SELECT * FROM alerts WHERE id = %s
"""

SELECT_ANALYSIS_SQL = """
SELECT * FROM analyses WHERE alert_id = %s ORDER BY created_at DESC LIMIT 1
"""

ACKNOWLEDGE_SQL = """
UPDATE alerts SET acknowledged = TRUE WHERE id = %s RETURNING id
"""


@dataclass(frozen=True, slots=True)
class AlertRecord:
    id: int
    symbol: str
    timeframe: str
    direction: str
    confidence: str
    criteria: dict
    entry_price: Decimal | None
    stop_loss: Decimal | None
    targets: list
    rsi_value: float | None
    volume_ratio: float | None
    divergence_type: str | None
    pattern_detected: str | None
    fibo_level: Decimal | None
    acknowledged: bool
    created_at: datetime


class AlertRepository:
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

    def save_signal(self, signal: DIVAPSignal) -> int:
        targets_json = Json([str(t) for t in signal.targets])
        criteria_json = Json(signal.criteria.to_dict())

        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    INSERT_ALERT_SQL,
                    (
                        signal.symbol,
                        signal.timeframe,
                        signal.direction,
                        signal.confidence,
                        criteria_json,
                        signal.entry_price,
                        signal.stop_loss,
                        targets_json,
                        signal.rsi_value,
                        signal.volume_ratio,
                        signal.divergence_type,
                        signal.pattern_detected,
                        signal.fibo_level,
                    ),
                )
                row = cur.fetchone()
                return row[0]

    def save_analysis(self, alert_id: int, content: str, model: str) -> int:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(INSERT_ANALYSIS_SQL, (alert_id, content, model))
                return cur.fetchone()[0]

    def list_alerts(self, limit: int = 20, offset: int = 0) -> list[AlertRecord]:
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(SELECT_ALERTS_SQL, (limit, offset))
                rows = cur.fetchall()
        return [self._row_to_record(row) for row in rows]

    def get_alert(self, alert_id: int) -> AlertRecord | None:
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(SELECT_ALERT_SQL, (alert_id,))
                row = cur.fetchone()
        return self._row_to_record(row) if row else None

    def get_analysis(self, alert_id: int) -> str | None:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(SELECT_ANALYSIS_SQL, (alert_id,))
                row = cur.fetchone()
        return row[0] if row else None

    def acknowledge(self, alert_id: int) -> bool:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(ACKNOWLEDGE_SQL, (alert_id,))
                return cur.fetchone() is not None

    def _row_to_record(self, row: dict) -> AlertRecord:
        return AlertRecord(
            id=row["id"],
            symbol=row["symbol"],
            timeframe=row["timeframe"],
            direction=row["direction"],
            confidence=row["confidence"],
            criteria=row["criteria"] if isinstance(row["criteria"], dict) else json.loads(row["criteria"]),
            entry_price=row["entry_price"],
            stop_loss=row["stop_loss"],
            targets=row["targets"] if isinstance(row["targets"], list) else json.loads(row["targets"]),
            rsi_value=row["rsi_value"],
            volume_ratio=row["volume_ratio"],
            divergence_type=row["divergence_type"],
            pattern_detected=row["pattern_detected"],
            fibo_level=row["fibo_level"],
            acknowledged=row["acknowledged"],
            created_at=row["created_at"],
        )
