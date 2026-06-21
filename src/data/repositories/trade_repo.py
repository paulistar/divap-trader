import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor

from src.core.config import settings
from src.otc.periods import (
    DEFAULT_TIMEZONE,
    VALID_PERIODS,
    bucket_expr,
    current_period_predicate,
    normalize_period,
    same_period_as_ref,
)

OTC_VENUE = "iqoption"
OTC_PROFILE_ID = "otc"
# Trades Binance no painel — exclui IQ Option / OTC (mesma tabela `trades`).
BINANCE_SCOPE_SQL = f"AND COALESCE(venue, 'binance') <> '{OTC_VENUE}'"

OTC_STATS_SQL = """
SELECT
    COUNT(*) FILTER (WHERE close_reason = 'expiry') AS ops,
    COUNT(*) FILTER (WHERE close_reason = 'expiry' AND pnl_usdt > 0) AS win_l0,
    COUNT(*) FILTER (WHERE close_reason = 'expiry_p1') AS prot1,
    COUNT(*) FILTER (WHERE close_reason = 'expiry_p1' AND pnl_usdt > 0) AS win_p1,
    COUNT(*) FILTER (WHERE close_reason = 'expiry_p2') AS prot2,
    COUNT(*) FILTER (WHERE close_reason = 'expiry_p2' AND pnl_usdt > 0) AS win_p2,
    COUNT(*) FILTER (WHERE status = 'closed') AS legs,
    COALESCE(SUM(pnl_usdt) FILTER (WHERE status = 'closed'), 0) AS total_pnl
FROM trades
WHERE venue = %s
"""

LIST_OTC_TRADES_SQL = """
SELECT id, symbol, direction, status, quantity, pnl_usdt, pnl_pct,
       close_reason, opened_at, closed_at, exchange_order_id, trading_mode
FROM trades
WHERE venue = %s
ORDER BY COALESCE(closed_at, opened_at, created_at) DESC
LIMIT %s
"""

LIST_OTC_TRADES_BY_DAY_SQL = """
SELECT id, symbol, direction, status, quantity, pnl_usdt, pnl_pct,
       close_reason, opened_at, closed_at, exchange_order_id, trading_mode
FROM trades
WHERE venue = %s
  AND closed_at IS NOT NULL
  AND (closed_at AT TIME ZONE %s)::date = %s::date
ORDER BY closed_at DESC
LIMIT %s
"""

INSERT_TRADE_SQL = """
INSERT INTO trades (
    alert_id, symbol, timeframe, direction, confidence, status,
    entry_price, stop_loss, take_profit, quantity, quote_amount,
    context_verdict, context_score, exchange_order_id,
    stop_order_id, tp_order_id, trading_mode, opened_at,
    profile_id, goal_protected, market, venue,
    take_profit_levels, remaining_quantity, partials_taken, realized_pnl_usdt
) VALUES (
    %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s,
    %s, %s, %s,
    %s, %s, %s, %s,
    %s, %s, %s, %s,
    %s, %s, %s, %s
) RETURNING id
"""

SELECT_OPEN_TRADES_SQL = """
SELECT * FROM trades WHERE status = 'open' ORDER BY opened_at ASC
"""

SELECT_OPEN_BINANCE_TRADES_SQL = f"""
SELECT * FROM trades
WHERE status = 'open' {BINANCE_SCOPE_SQL}
ORDER BY opened_at ASC
"""

COUNT_OPEN_TRADES_SQL = """
SELECT COUNT(*) FROM trades WHERE status = 'open'
"""

COUNT_OPEN_TRADES_BY_PROFILE_SQL = """
SELECT COUNT(*) FROM trades WHERE status = 'open' AND COALESCE(profile_id, 'divap') = %s
"""

HAS_OPEN_TRADE_SQL = """
SELECT id FROM trades
WHERE status = 'open' AND symbol = %s AND timeframe = %s
  AND COALESCE(profile_id, 'divap') = %s
LIMIT 1
"""

CLOSE_TRADE_SQL = """
UPDATE trades SET
    status = 'closed',
    exit_price = %s,
    pnl_usdt = %s,
    pnl_pct = %s,
    fees_usdt = COALESCE(%s, fees_usdt),
    close_reason = %s,
    closed_at = %s
WHERE id = %s
RETURNING id
"""

UPDATE_ORDER_IDS_SQL = """
UPDATE trades SET stop_order_id = %s, tp_order_id = %s WHERE id = %s
"""

UPDATE_PARTIAL_SQL = """
UPDATE trades SET
    remaining_quantity = %s,
    partials_taken = %s,
    realized_pnl_usdt = %s
WHERE id = %s
"""

UPDATE_STOP_LOSS_SQL = """
UPDATE trades SET stop_loss = %s, stop_order_id = %s WHERE id = %s
"""

SELECT_TRADES_SQL = """
SELECT * FROM trades
WHERE status != 'simulated'
ORDER BY created_at DESC
LIMIT %s OFFSET %s
"""

SELECT_BINANCE_TRADES_SQL = f"""
SELECT * FROM trades
WHERE status != 'simulated' {BINANCE_SCOPE_SQL}
ORDER BY created_at DESC
LIMIT %s OFFSET %s
"""

SELECT_TRADE_SQL = """
SELECT * FROM trades WHERE id = %s
"""

PNL_HISTORY_SQL = """
SELECT id, closed_at, pnl_usdt, pnl_pct, profile_id
FROM trades
WHERE status = 'closed' AND closed_at IS NOT NULL
ORDER BY closed_at ASC
LIMIT %s
"""

BINANCE_PNL_HISTORY_SQL = f"""
SELECT id, closed_at, pnl_usdt, pnl_pct, profile_id
FROM trades
WHERE status = 'closed' AND closed_at IS NOT NULL {BINANCE_SCOPE_SQL}
ORDER BY closed_at ASC
LIMIT %s
"""

PROFILE_STATS_SQL = """
SELECT
    COALESCE(profile_id, 'divap') AS profile_id,
    COUNT(*) FILTER (WHERE status = 'closed') AS closed_count,
    COUNT(*) FILTER (WHERE status = 'open') AS open_count,
    COUNT(*) FILTER (WHERE status = 'closed' AND pnl_usdt > 0) AS wins,
    COUNT(*) FILTER (WHERE status = 'closed' AND pnl_usdt <= 0) AS losses,
    COALESCE(SUM(pnl_usdt) FILTER (WHERE status = 'closed'), 0) AS total_pnl_usdt,
    COALESCE(SUM(pnl_usdt) FILTER (
        WHERE status = 'closed'
          AND closed_at >= date_trunc('month', NOW() AT TIME ZONE 'UTC')
          AND closed_at < date_trunc('month', NOW() AT TIME ZONE 'UTC') + INTERVAL '1 month'
    ), 0) AS month_pnl_usdt,
    COALESCE(SUM(pnl_usdt) FILTER (
        WHERE status = 'closed'
          AND closed_at >= date_trunc('week', NOW() AT TIME ZONE 'UTC')
          AND closed_at < date_trunc('week', NOW() AT TIME ZONE 'UTC') + INTERVAL '1 week'
    ), 0) AS week_pnl_usdt
FROM trades
WHERE status != 'simulated'
GROUP BY COALESCE(profile_id, 'divap')
"""

RECENT_BY_PROFILE_SQL = """
SELECT id, symbol, timeframe, direction, status, pnl_usdt, profile_id,
       goal_protected, opened_at, closed_at
FROM trades
WHERE status != 'simulated'
  AND (%s IS NULL OR COALESCE(profile_id, 'divap') = %s)
ORDER BY COALESCE(closed_at, opened_at, created_at) DESC
LIMIT %s
"""

STATS_SQL = """
SELECT
    COUNT(*) FILTER (WHERE status = 'closed') AS closed_count,
    COUNT(*) FILTER (WHERE status = 'closed' AND pnl_usdt > 0) AS wins,
    COUNT(*) FILTER (WHERE status = 'closed' AND pnl_usdt <= 0) AS losses,
    COUNT(*) FILTER (WHERE status = 'open') AS open_count,
    COALESCE(SUM(pnl_usdt) FILTER (WHERE status = 'closed'), 0) AS total_pnl_usdt,
    COALESCE(AVG(pnl_pct) FILTER (WHERE status = 'closed'), 0) AS avg_pnl_pct,
    COALESCE(SUM(fees_usdt) FILTER (WHERE status = 'closed'), 0) AS total_fees_usdt
FROM trades
WHERE status != 'simulated'
"""

BINANCE_STATS_SQL = f"""
SELECT
    COUNT(*) FILTER (WHERE status = 'closed') AS closed_count,
    COUNT(*) FILTER (WHERE status = 'closed' AND pnl_usdt > 0) AS wins,
    COUNT(*) FILTER (WHERE status = 'closed' AND pnl_usdt <= 0) AS losses,
    COUNT(*) FILTER (WHERE status = 'open') AS open_count,
    COALESCE(SUM(pnl_usdt) FILTER (WHERE status = 'closed'), 0) AS total_pnl_usdt,
    COALESCE(AVG(pnl_pct) FILTER (WHERE status = 'closed'), 0) AS avg_pnl_pct,
    COALESCE(SUM(fees_usdt) FILTER (WHERE status = 'closed'), 0) AS total_fees_usdt
FROM trades
WHERE status != 'simulated' {BINANCE_SCOPE_SQL}
"""

PROFILE_STATS_BINANCE_SQL = f"""
SELECT
    COALESCE(profile_id, 'divap') AS profile_id,
    COUNT(*) FILTER (WHERE status = 'closed') AS closed_count,
    COUNT(*) FILTER (WHERE status = 'open') AS open_count,
    COUNT(*) FILTER (WHERE status = 'closed' AND pnl_usdt > 0) AS wins,
    COUNT(*) FILTER (WHERE status = 'closed' AND pnl_usdt <= 0) AS losses,
    COALESCE(SUM(pnl_usdt) FILTER (WHERE status = 'closed'), 0) AS total_pnl_usdt,
    COALESCE(SUM(pnl_usdt) FILTER (
        WHERE status = 'closed'
          AND closed_at >= date_trunc('month', NOW() AT TIME ZONE 'UTC')
          AND closed_at < date_trunc('month', NOW() AT TIME ZONE 'UTC') + INTERVAL '1 month'
    ), 0) AS month_pnl_usdt,
    COALESCE(SUM(pnl_usdt) FILTER (
        WHERE status = 'closed'
          AND closed_at >= date_trunc('week', NOW() AT TIME ZONE 'UTC')
          AND closed_at < date_trunc('week', NOW() AT TIME ZONE 'UTC') + INTERVAL '1 week'
    ), 0) AS week_pnl_usdt
FROM trades
WHERE status != 'simulated' {BINANCE_SCOPE_SQL}
GROUP BY COALESCE(profile_id, 'divap')
"""


@dataclass(frozen=True, slots=True)
class TradeRecord:
    id: int
    alert_id: int | None
    symbol: str
    timeframe: str
    direction: str
    confidence: str
    status: str
    entry_price: Decimal | None
    exit_price: Decimal | None
    stop_loss: Decimal | None
    take_profit: Decimal | None
    quantity: Decimal | None
    quote_amount: Decimal | None
    pnl_usdt: Decimal | None
    pnl_pct: Decimal | None
    fees_usdt: Decimal | None
    context_verdict: str | None
    context_score: int | None
    exchange_order_id: str | None
    stop_order_id: str | None
    tp_order_id: str | None
    close_reason: str | None
    trading_mode: str
    opened_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    profile_id: str | None = None
    goal_protected: bool = False
    market: str = "crypto"
    venue: str = "binance"
    take_profit_levels: tuple[Decimal, ...] | None = None
    remaining_quantity: Decimal | None = None
    partials_taken: int = 0
    realized_pnl_usdt: Decimal | None = None

    @property
    def effective_remaining(self) -> Decimal:
        if self.remaining_quantity is not None:
            return self.remaining_quantity
        return self.quantity or Decimal(0)

    @property
    def has_partial_exits(self) -> bool:
        return bool(self.take_profit_levels)


@dataclass(frozen=True, slots=True)
class TradeStats:
    closed_count: int
    wins: int
    losses: int
    open_count: int
    total_pnl_usdt: Decimal
    avg_pnl_pct: Decimal
    total_fees_usdt: Decimal

    @property
    def win_rate_pct(self) -> Decimal:
        if self.closed_count == 0:
            return Decimal(0)
        return (Decimal(self.wins) / Decimal(self.closed_count) * 100).quantize(
            Decimal("0.01")
        )


class TradeRepository:
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

    def create_trade(
        self,
        *,
        alert_id: int | None,
        symbol: str,
        timeframe: str,
        direction: str,
        confidence: str,
        status: str,
        entry_price: Decimal,
        stop_loss: Decimal,
        take_profit: Decimal,
        quantity: Decimal,
        quote_amount: Decimal,
        context_verdict: str | None,
        context_score: int | None,
        exchange_order_id: str | None,
        stop_order_id: str | None,
        tp_order_id: str | None,
        trading_mode: str,
        opened_at: datetime,
        profile_id: str = "divap",
        goal_protected: bool = False,
        market: str = "crypto",
        venue: str = "binance",
        take_profit_levels: tuple[Decimal, ...] | None = None,
        remaining_quantity: Decimal | None = None,
        partials_taken: int = 0,
        realized_pnl_usdt: Decimal | None = None,
    ) -> int:
        levels_json = (
            json.dumps([str(level) for level in take_profit_levels])
            if take_profit_levels
            else None
        )
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    INSERT_TRADE_SQL,
                    (
                        alert_id,
                        symbol,
                        timeframe,
                        direction,
                        confidence,
                        status,
                        entry_price,
                        stop_loss,
                        take_profit,
                        quantity,
                        quote_amount,
                        context_verdict,
                        context_score,
                        exchange_order_id,
                        stop_order_id,
                        tp_order_id,
                        trading_mode,
                        opened_at,
                        profile_id,
                        goal_protected,
                        market,
                        venue,
                        levels_json,
                        remaining_quantity if remaining_quantity is not None else quantity,
                        partials_taken,
                        realized_pnl_usdt or Decimal(0),
                    ),
                )
                return cur.fetchone()[0]

    def count_open_trades(self, profile_id: str | None = None) -> int:
        with self._connection() as conn:
            with conn.cursor() as cur:
                if profile_id:
                    cur.execute(COUNT_OPEN_TRADES_BY_PROFILE_SQL, (profile_id,))
                else:
                    cur.execute(COUNT_OPEN_TRADES_SQL)
                return cur.fetchone()[0]

    def has_open_trade(self, symbol: str, timeframe: str, profile_id: str = "divap") -> bool:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(HAS_OPEN_TRADE_SQL, (symbol, timeframe, profile_id))
                return cur.fetchone() is not None

    def list_open_trades(self) -> list[TradeRecord]:
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(SELECT_OPEN_TRADES_SQL)
                rows = cur.fetchall()
        return [self._row_to_record(row) for row in rows]

    def list_binance_open_trades(self) -> list[TradeRecord]:
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(SELECT_OPEN_BINANCE_TRADES_SQL)
                rows = cur.fetchall()
        return [self._row_to_record(row) for row in rows]

    def list_trades(self, limit: int = 20, offset: int = 0) -> list[TradeRecord]:
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(SELECT_TRADES_SQL, (limit, offset))
                rows = cur.fetchall()
        return [self._row_to_record(row) for row in rows]

    def list_binance_trades(self, limit: int = 20, offset: int = 0) -> list[TradeRecord]:
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(SELECT_BINANCE_TRADES_SQL, (limit, offset))
                rows = cur.fetchall()
        return [self._row_to_record(row) for row in rows]

    def profile_stats(self) -> list[dict]:
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(PROFILE_STATS_SQL)
                return list(cur.fetchall())

    def profile_stats_binance(self) -> list[dict]:
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(PROFILE_STATS_BINANCE_SQL)
                return list(cur.fetchall())

    def recent_trades_for_profile(
        self, profile_id: str | None = None, limit: int = 5
    ) -> list[dict]:
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(RECENT_BY_PROFILE_SQL, (profile_id, profile_id, limit))
                return list(cur.fetchall())

    def pnl_history(self, limit: int = 100) -> list[dict]:
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(PNL_HISTORY_SQL, (limit,))
                return list(cur.fetchall())

    def binance_pnl_history(self, limit: int = 100) -> list[dict]:
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(BINANCE_PNL_HISTORY_SQL, (limit,))
                return list(cur.fetchall())

    def get_trade(self, trade_id: int) -> TradeRecord | None:
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(SELECT_TRADE_SQL, (trade_id,))
                row = cur.fetchone()
        return self._row_to_record(row) if row else None

    def close_trade(
        self,
        trade_id: int,
        exit_price: Decimal,
        pnl_usdt: Decimal,
        pnl_pct: Decimal,
        close_reason: str,
        closed_at: datetime,
        fees_usdt: Decimal | None = None,
    ) -> bool:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    CLOSE_TRADE_SQL,
                    (
                        exit_price,
                        pnl_usdt,
                        pnl_pct,
                        fees_usdt,
                        close_reason,
                        closed_at,
                        trade_id,
                    ),
                )
                return cur.fetchone() is not None

    def update_protective_orders(
        self, trade_id: int, stop_order_id: str | None, tp_order_id: str | None
    ) -> None:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(UPDATE_ORDER_IDS_SQL, (stop_order_id, tp_order_id, trade_id))

    def record_partial_close(
        self,
        trade_id: int,
        remaining_quantity: Decimal,
        partials_taken: int,
        realized_pnl_usdt: Decimal,
    ) -> None:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    UPDATE_PARTIAL_SQL,
                    (remaining_quantity, partials_taken, realized_pnl_usdt, trade_id),
                )

    def update_stop_loss(
        self,
        trade_id: int,
        stop_loss: Decimal,
        stop_order_id: str | None,
    ) -> None:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(UPDATE_STOP_LOSS_SQL, (stop_loss, stop_order_id, trade_id))

    def get_stats(self) -> TradeStats:
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(STATS_SQL)
                row = cur.fetchone()
        return self._stats_from_row(row)

    def get_binance_stats(self) -> TradeStats:
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(BINANCE_STATS_SQL)
                row = cur.fetchone()
        return self._stats_from_row(row)

    @staticmethod
    def _stats_from_row(row: dict) -> TradeStats:
        return TradeStats(
            closed_count=row["closed_count"] or 0,
            wins=row["wins"] or 0,
            losses=row["losses"] or 0,
            open_count=row["open_count"] or 0,
            total_pnl_usdt=Decimal(str(row["total_pnl_usdt"] or 0)),
            avg_pnl_pct=Decimal(str(row["avg_pnl_pct"] or 0)),
            total_fees_usdt=Decimal(str(row["total_fees_usdt"] or 0)),
        )

    def otc_stats(self) -> dict:
        """Estatísticas agregadas das operações OTC (sequências e proteções)."""
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(OTC_STATS_SQL, (OTC_VENUE,))
                row = cur.fetchone() or {}

        ops = int(row.get("ops") or 0)
        win_l0 = int(row.get("win_l0") or 0)
        prot1 = int(row.get("prot1") or 0)
        win_p1 = int(row.get("win_p1") or 0)
        prot2 = int(row.get("prot2") or 0)
        win_p2 = int(row.get("win_p2") or 0)
        wins = win_l0 + win_p1 + win_p2
        losses = max(ops - wins, 0)
        win_rate = round(wins / ops * 100, 2) if ops else 0.0
        return {
            "operations": ops,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": win_rate,
            "win_no_gale": win_l0,
            "protection1_count": prot1,
            "protection1_wins": win_p1,
            "protection2_count": prot2,
            "protection2_wins": win_p2,
            "went_to_gale": prot1,
            "legs": int(row.get("legs") or 0),
            "total_pnl_usd": str(Decimal(str(row.get("total_pnl") or 0))),
        }

    def otc_period_totals(self, timezone: str = DEFAULT_TIMEZONE) -> dict:
        """PnL e nº de operações do período corrente para cada granularidade."""
        selects = []
        for period in VALID_PERIODS:
            pred = current_period_predicate(period, "closed_at", timezone)
            selects.append(
                f"COALESCE(SUM(pnl_usdt) FILTER (WHERE {pred}), 0) AS {period}_pnl"
            )
            selects.append(
                f"COUNT(*) FILTER (WHERE close_reason = 'expiry' AND {pred}) AS {period}_ops"
            )
        sql = (
            "SELECT " + ", ".join(selects) + " FROM trades "
            "WHERE venue = %s AND status = 'closed' AND closed_at IS NOT NULL"
        )
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, (OTC_VENUE,))
                row = cur.fetchone() or {}
        return {
            period: {
                "pnl_usd": str(Decimal(str(row.get(f"{period}_pnl") or 0))),
                "operations": int(row.get(f"{period}_ops") or 0),
            }
            for period in VALID_PERIODS
        }

    def otc_pnl_series(
        self, period: str = "day", limit: int = 30, timezone: str = DEFAULT_TIMEZONE
    ) -> list[dict]:
        """Série de PnL por bucket do período pedido (mais recentes primeiro -> ascendente)."""
        period = normalize_period(period)
        bucket = bucket_expr(period, "closed_at", timezone)
        sql = (
            f"SELECT {bucket} AS bucket, "
            "COALESCE(SUM(pnl_usdt), 0) AS pnl, "
            "COUNT(*) FILTER (WHERE close_reason = 'expiry') AS ops "
            "FROM trades "
            "WHERE venue = %s AND status = 'closed' AND closed_at IS NOT NULL "
            f"GROUP BY {bucket} ORDER BY bucket DESC LIMIT %s"
        )
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, (OTC_VENUE, limit))
                rows = cur.fetchall()
        series = [
            {
                "bucket": row["bucket"].isoformat() if row["bucket"] else None,
                "pnl_usd": str(Decimal(str(row["pnl"] or 0))),
                "operations": int(row["ops"] or 0),
            }
            for row in rows
        ]
        series.reverse()
        return series

    def list_otc_trades(self, limit: int = 50) -> list[dict]:
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(LIST_OTC_TRADES_SQL, (OTC_VENUE, limit))
                return list(cur.fetchall())

    def list_otc_trades_by_day(
        self,
        day: str,
        *,
        timezone: str = DEFAULT_TIMEZONE,
        limit: int = 500,
    ) -> list[dict]:
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    LIST_OTC_TRADES_BY_DAY_SQL,
                    (OTC_VENUE, timezone, day, limit),
                )
                return list(cur.fetchall())

    def otc_pnl_breakdown_at(
        self, ref: datetime, timezone: str = DEFAULT_TIMEZONE
    ) -> dict[str, dict[str, str | int]]:
        """PnL e nº de ops por período (dia/semana/...) que contém ``ref``."""
        selects: list[str] = []
        for period in VALID_PERIODS:
            pred = same_period_as_ref(period, "closed_at", timezone)
            selects.append(
                f"COALESCE(SUM(pnl_usdt) FILTER (WHERE {pred}), 0) AS {period}_pnl"
            )
            selects.append(
                f"COUNT(*) FILTER (WHERE close_reason = 'expiry' AND {pred}) AS {period}_ops"
            )
        sql = (
            "SELECT " + ", ".join(selects) + " "
            "FROM trades "
            "WHERE venue = %s AND status = 'closed' AND closed_at IS NOT NULL"
        )
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                params: tuple = tuple(ref for _ in VALID_PERIODS) + (OTC_VENUE,)
                cur.execute(sql, params)
                row = cur.fetchone() or {}
        return {
            period: {
                "pnl_usd": str(Decimal(str(row.get(f"{period}_pnl") or 0))),
                "operations": int(row.get(f"{period}_ops") or 0),
            }
            for period in VALID_PERIODS
        }

    def _row_to_record(self, row: dict) -> TradeRecord:
        levels_raw = row.get("take_profit_levels")
        take_profit_levels: tuple[Decimal, ...] | None = None
        if levels_raw:
            parsed = json.loads(levels_raw) if isinstance(levels_raw, str) else levels_raw
            take_profit_levels = tuple(Decimal(str(price)) for price in parsed)

        return TradeRecord(
            id=row["id"],
            alert_id=row["alert_id"],
            symbol=row["symbol"],
            timeframe=row["timeframe"],
            direction=row["direction"],
            confidence=row["confidence"],
            status=row["status"],
            entry_price=row["entry_price"],
            exit_price=row["exit_price"],
            stop_loss=row["stop_loss"],
            take_profit=row["take_profit"],
            quantity=row["quantity"],
            quote_amount=row["quote_amount"],
            pnl_usdt=row["pnl_usdt"],
            pnl_pct=row["pnl_pct"],
            fees_usdt=row["fees_usdt"],
            context_verdict=row["context_verdict"],
            context_score=row["context_score"],
            exchange_order_id=row["exchange_order_id"],
            stop_order_id=row["stop_order_id"],
            tp_order_id=row["tp_order_id"],
            close_reason=row["close_reason"],
            trading_mode=row["trading_mode"],
            profile_id=row.get("profile_id"),
            goal_protected=bool(row.get("goal_protected", False)),
            market=row.get("market") or "crypto",
            venue=row.get("venue") or "binance",
            take_profit_levels=take_profit_levels,
            remaining_quantity=row.get("remaining_quantity"),
            partials_taken=int(row.get("partials_taken") or 0),
            realized_pnl_usdt=row.get("realized_pnl_usdt"),
            opened_at=row["opened_at"],
            closed_at=row["closed_at"],
            created_at=row["created_at"],
        )
