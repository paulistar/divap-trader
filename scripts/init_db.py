#!/usr/bin/env python3
"""Initialize TimescaleDB schema for DIVAP trader."""

import os
import sys

import psycopg2

SCHEMA_STATEMENTS: list[str] = [
    "CREATE EXTENSION IF NOT EXISTS timescaledb",
    """
    CREATE TABLE IF NOT EXISTS candles (
        symbol      TEXT NOT NULL,
        timeframe   TEXT NOT NULL,
        ts          TIMESTAMPTZ NOT NULL,
        open        NUMERIC(20, 8) NOT NULL,
        high        NUMERIC(20, 8) NOT NULL,
        low         NUMERIC(20, 8) NOT NULL,
        close       NUMERIC(20, 8) NOT NULL,
        volume      NUMERIC(30, 8) NOT NULL,
        PRIMARY KEY (symbol, timeframe, ts)
    )
    """,
    "SELECT create_hypertable('candles', 'ts', if_not_exists => TRUE)",
    """
    CREATE INDEX IF NOT EXISTS idx_candles_symbol_tf_ts
        ON candles (symbol, timeframe, ts DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS alerts (
        id              BIGSERIAL PRIMARY KEY,
        symbol          TEXT NOT NULL,
        timeframe       TEXT NOT NULL,
        direction       TEXT NOT NULL,
        confidence      TEXT NOT NULL,
        criteria        JSONB NOT NULL DEFAULT '{}',
        entry_price     NUMERIC(20, 8),
        stop_loss       NUMERIC(20, 8),
        targets         JSONB DEFAULT '[]',
        rsi_value       DOUBLE PRECISION,
        volume_ratio    DOUBLE PRECISION,
        divergence_type TEXT,
        pattern_detected TEXT,
        fibo_level      NUMERIC(10, 6),
        acknowledged    BOOLEAN NOT NULL DEFAULT FALSE,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts (created_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS analyses (
        id          BIGSERIAL PRIMARY KEY,
        alert_id    BIGINT NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
        content     TEXT NOT NULL,
        model       TEXT NOT NULL,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trades (
        id               BIGSERIAL PRIMARY KEY,
        alert_id         BIGINT REFERENCES alerts(id) ON DELETE SET NULL,
        symbol           TEXT NOT NULL,
        timeframe        TEXT NOT NULL,
        direction        TEXT NOT NULL,
        confidence       TEXT NOT NULL,
        status           TEXT NOT NULL DEFAULT 'open',
        entry_price      NUMERIC(20, 8),
        exit_price       NUMERIC(20, 8),
        stop_loss        NUMERIC(20, 8),
        take_profit      NUMERIC(20, 8),
        quantity         NUMERIC(30, 8),
        quote_amount     NUMERIC(20, 8),
        pnl_usdt         NUMERIC(20, 8),
        pnl_pct          NUMERIC(10, 4),
        fees_usdt        NUMERIC(20, 8) DEFAULT 0,
        context_verdict  TEXT,
        context_score    INTEGER,
        exchange_order_id TEXT,
        stop_order_id    TEXT,
        tp_order_id      TEXT,
        close_reason     TEXT,
        trading_mode     TEXT NOT NULL DEFAULT 'testnet',
        opened_at        TIMESTAMPTZ,
        closed_at        TIMESTAMPTZ,
        created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_trades_status ON trades (status)",
    "CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades (symbol, created_at DESC)",
    "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS context_score INTEGER",
    "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS context_verdict TEXT",
    "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS fear_greed INTEGER",
    "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS htf_1d TEXT",
    "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS htf_1w TEXT",
    "ALTER TABLE trades ADD COLUMN IF NOT EXISTS profile_id TEXT DEFAULT 'divap'",
    "ALTER TABLE trades ADD COLUMN IF NOT EXISTS goal_protected BOOLEAN NOT NULL DEFAULT FALSE",
    "CREATE INDEX IF NOT EXISTS idx_trades_profile_id ON trades (profile_id, closed_at DESC)",
    "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'crypto'",
    "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS venue TEXT NOT NULL DEFAULT 'binance'",
    "ALTER TABLE trades ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'crypto'",
    "ALTER TABLE trades ADD COLUMN IF NOT EXISTS venue TEXT NOT NULL DEFAULT 'binance'",
    "CREATE INDEX IF NOT EXISTS idx_trades_market ON trades (market, status, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_alerts_market ON alerts (market, created_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS bankroll_settings (
        id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
        active_profile_id TEXT NOT NULL DEFAULT 'divap',
        monthly_target_usdt NUMERIC(20, 2),
        goal_reached_at TIMESTAMPTZ,
        period_month TEXT NOT NULL DEFAULT to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM'),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
]


def main() -> int:
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://divap:divap@localhost:5432/divap",
    )
    print(f"Connecting to database...")
    try:
        conn = psycopg2.connect(database_url)
        conn.autocommit = True
        with conn.cursor() as cur:
            for statement in SCHEMA_STATEMENTS:
                cur.execute(statement)
        conn.close()
        print("Database schema initialized successfully.")
        return 0
    except Exception as exc:
        print(f"Error initializing database: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
