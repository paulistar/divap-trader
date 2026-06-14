import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor

from src.core.config import settings

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

COUNT_OPEN_TRADES_SQL = """
SELECT COUNT(*) FROM trades WHERE status = 'open'
"""

HAS_OPEN_TRADE_SQL = """
SELECT id FROM trades
WHERE status = 'open' AND symbol = %s AND timeframe = %s
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

    def count_open_trades(self) -> int:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(COUNT_OPEN_TRADES_SQL)
                return cur.fetchone()[0]

    def has_open_trade(self, symbol: str, timeframe: str) -> bool:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(HAS_OPEN_TRADE_SQL, (symbol, timeframe))
                return cur.fetchone() is not None

    def list_open_trades(self) -> list[TradeRecord]:
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(SELECT_OPEN_TRADES_SQL)
                rows = cur.fetchall()
        return [self._row_to_record(row) for row in rows]

    def list_trades(self, limit: int = 20, offset: int = 0) -> list[TradeRecord]:
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(SELECT_TRADES_SQL, (limit, offset))
                rows = cur.fetchall()
        return [self._row_to_record(row) for row in rows]

    def profile_stats(self) -> list[dict]:
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(PROFILE_STATS_SQL)
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
        return TradeStats(
            closed_count=row["closed_count"] or 0,
            wins=row["wins"] or 0,
            losses=row["losses"] or 0,
            open_count=row["open_count"] or 0,
            total_pnl_usdt=Decimal(str(row["total_pnl_usdt"] or 0)),
            avg_pnl_pct=Decimal(str(row["avg_pnl_pct"] or 0)),
            total_fees_usdt=Decimal(str(row["total_fees_usdt"] or 0)),
        )

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
