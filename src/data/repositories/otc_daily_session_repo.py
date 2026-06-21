"""Persistência da sessão diária OTC (snapshot meia-noite)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor

SELECT_FOR_DATE_SQL = """
SELECT * FROM otc_daily_session WHERE session_date = %s::date
"""

SELECT_LATEST_SQL = """
SELECT * FROM otc_daily_session ORDER BY session_date DESC LIMIT 1
"""

UPSERT_SESSION_SQL = """
INSERT INTO otc_daily_session (
    session_date, reference_balance_usd, base_stake_usd,
    stop_win_usd, stop_loss_usd, stake_pct, stop_win_pct, stop_loss_pct,
    stake_risk_profile, source, captured_at
) VALUES (%s::date, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (session_date) DO NOTHING
RETURNING *
"""

SELECT_AFTER_CONFLICT_SQL = """
SELECT * FROM otc_daily_session WHERE session_date = %s::date
"""


def _dec(value: object) -> Decimal:
    return Decimal(str(value))


@dataclass(frozen=True, slots=True)
class OtcDailySessionRecord:
    session_date: str
    reference_balance_usd: Decimal
    base_stake_usd: Decimal
    stop_win_usd: Decimal
    stop_loss_usd: Decimal
    stake_pct: Decimal
    stop_win_pct: Decimal
    stop_loss_pct: Decimal
    stake_risk_profile: str
    source: str
    captured_at: datetime

    def to_dict(self) -> dict:
        return {
            "session_date": self.session_date,
            "reference_balance_usd": str(self.reference_balance_usd),
            "base_stake_usd": str(self.base_stake_usd),
            "stop_win_usd": str(self.stop_win_usd),
            "stop_loss_usd": str(self.stop_loss_usd),
            "stake_pct": str(self.stake_pct),
            "stop_win_pct": str(self.stop_win_pct),
            "stop_loss_pct": str(self.stop_loss_pct),
            "stake_risk_profile": self.stake_risk_profile,
            "source": self.source,
            "captured_at": self.captured_at.isoformat(),
        }


class OtcDailySessionRepository:
    def __init__(self, database_url: str | None = None) -> None:
        from src.core.config import settings

        self._database_url = database_url or settings.database_url

    def _connection(self):
        return psycopg2.connect(self._database_url)

    def get_for_date(self, session_date: str) -> OtcDailySessionRecord | None:
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(SELECT_FOR_DATE_SQL, (session_date,))
                row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def get_latest(self) -> OtcDailySessionRecord | None:
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(SELECT_LATEST_SQL)
                row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def upsert(self, session: OtcDailySessionRecord) -> OtcDailySessionRecord:
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    UPSERT_SESSION_SQL,
                    (
                        session.session_date,
                        session.reference_balance_usd,
                        session.base_stake_usd,
                        session.stop_win_usd,
                        session.stop_loss_usd,
                        session.stake_pct,
                        session.stop_win_pct,
                        session.stop_loss_pct,
                        session.stake_risk_profile,
                        session.source,
                        session.captured_at,
                    ),
                )
                row = cur.fetchone()
                if row is None:
                    cur.execute(SELECT_AFTER_CONFLICT_SQL, (session.session_date,))
                    row = cur.fetchone()
        return self._row_to_record(row)

    def _row_to_record(self, row: dict) -> OtcDailySessionRecord:
        captured = row["captured_at"]
        session_date = row["session_date"]
        if hasattr(session_date, "isoformat"):
            session_date = session_date.isoformat()
        return OtcDailySessionRecord(
            session_date=str(session_date),
            reference_balance_usd=_dec(row["reference_balance_usd"]),
            base_stake_usd=_dec(row["base_stake_usd"]),
            stop_win_usd=_dec(row["stop_win_usd"]),
            stop_loss_usd=_dec(row["stop_loss_usd"]),
            stake_pct=_dec(row["stake_pct"]),
            stop_win_pct=_dec(row["stop_win_pct"]),
            stop_loss_pct=_dec(row["stop_loss_pct"]),
            stake_risk_profile=str(row.get("stake_risk_profile") or "moderate"),
            source=str(row["source"]),
            captured_at=captured,
        )
