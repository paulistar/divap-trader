"""Bankroll settings and monthly goal tracking."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor

UPSERT_BANKROLL_SQL = """
INSERT INTO bankroll_settings (id, active_profile_id, active_profile_ids, monthly_target_usdt, period_month)
VALUES (1, %s, %s, %s, %s)
ON CONFLICT (id) DO UPDATE SET
    active_profile_id = EXCLUDED.active_profile_id,
    active_profile_ids = EXCLUDED.active_profile_ids,
    monthly_target_usdt = EXCLUDED.monthly_target_usdt,
    period_month = EXCLUDED.period_month,
    goal_reached_at = CASE
        WHEN bankroll_settings.period_month IS DISTINCT FROM EXCLUDED.period_month THEN NULL
        ELSE bankroll_settings.goal_reached_at
    END,
    updated_at = NOW()
RETURNING *
"""

SELECT_BANKROLL_SQL = "SELECT * FROM bankroll_settings WHERE id = 1"

MONTHLY_PNL_SQL = """
SELECT COALESCE(SUM(pnl_usdt), 0) AS total
FROM trades
WHERE status = 'closed'
  AND COALESCE(venue, 'binance') <> 'iqoption'
  AND closed_at >= date_trunc('month', NOW() AT TIME ZONE 'UTC')
  AND closed_at < date_trunc('month', NOW() AT TIME ZONE 'UTC') + INTERVAL '1 month'
"""

WEEKLY_PNL_SQL = """
SELECT COALESCE(SUM(pnl_usdt), 0) AS total
FROM trades
WHERE status = 'closed'
  AND COALESCE(venue, 'binance') <> 'iqoption'
  AND closed_at >= date_trunc('week', NOW() AT TIME ZONE 'UTC')
  AND closed_at < date_trunc('week', NOW() AT TIME ZONE 'UTC') + INTERVAL '1 week'
"""

SET_GOAL_REACHED_SQL = """
UPDATE bankroll_settings
SET goal_reached_at = %s, updated_at = NOW()
WHERE id = 1 AND goal_reached_at IS NULL
RETURNING *
"""


@dataclass(frozen=True, slots=True)
class BankrollRecord:
    active_profile_id: str
    active_profile_ids: tuple[str, ...]
    monthly_target_usdt: Decimal | None
    goal_reached_at: datetime | None
    period_month: str


class BankrollRepository:
    def __init__(self, database_url: str | None = None) -> None:
        from src.core.config import settings

        self._database_url = database_url or settings.database_url

    def _connection(self):
        return psycopg2.connect(self._database_url)

    def get_settings(self) -> BankrollRecord:
        period = _current_period_month()
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(SELECT_BANKROLL_SQL)
                row = cur.fetchone()
                if row is None:
                    cur.execute(
                        UPSERT_BANKROLL_SQL,
                        ("divap_ativo", json.dumps(["divap_ativo"]), None, period),
                    )
                    row = cur.fetchone()
                elif row["period_month"] != period:
                    cur.execute(
                        """
                        UPDATE bankroll_settings
                        SET period_month = %s, goal_reached_at = NULL, updated_at = NOW()
                        WHERE id = 1
                        RETURNING *
                        """,
                        (period,),
                    )
                    row = cur.fetchone()
        return self._row_to_record(row)

    def update_settings(
        self,
        active_profile_id: str | None = None,
        active_profile_ids: tuple[str, ...] | list[str] | None = None,
        monthly_target_usdt: Decimal | None = None,
    ) -> BankrollRecord:
        current = self.get_settings()
        if active_profile_ids is not None:
            profile_ids = tuple(active_profile_ids)
            primary = profile_ids[0] if profile_ids else current.active_profile_id
        else:
            profile_ids = current.active_profile_ids
            primary = active_profile_id or current.active_profile_id
        target = monthly_target_usdt if monthly_target_usdt is not None else current.monthly_target_usdt
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    UPSERT_BANKROLL_SQL,
                    (primary, json.dumps(list(profile_ids)), target, _current_period_month()),
                )
                row = cur.fetchone()
        return self._row_to_record(row)

    def mark_goal_reached(self) -> BankrollRecord | None:
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(SET_GOAL_REACHED_SQL, (datetime.now(UTC),))
                row = cur.fetchone()
        return self._row_to_record(row) if row else None

    def monthly_pnl_usdt(self) -> Decimal:
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(MONTHLY_PNL_SQL)
                row = cur.fetchone()
        return Decimal(str(row["total"] or 0))

    def weekly_pnl_usdt(self) -> Decimal:
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(WEEKLY_PNL_SQL)
                row = cur.fetchone()
        return Decimal(str(row["total"] or 0))

    def _row_to_record(self, row: dict) -> BankrollRecord:
        target = row.get("monthly_target_usdt")
        ids_raw = row.get("active_profile_ids")
        if ids_raw:
            parsed = json.loads(ids_raw) if isinstance(ids_raw, str) else ids_raw
            profile_ids = tuple(str(item) for item in parsed if item)
        else:
            profile_ids = (row["active_profile_id"],)
        if not profile_ids:
            profile_ids = ("divap",)
        primary = row["active_profile_id"] or profile_ids[0]
        return BankrollRecord(
            active_profile_id=primary,
            active_profile_ids=profile_ids,
            monthly_target_usdt=Decimal(str(target)) if target is not None else None,
            goal_reached_at=row.get("goal_reached_at"),
            period_month=row["period_month"],
        )


def _current_period_month() -> str:
    return datetime.now(UTC).strftime("%Y-%m")
