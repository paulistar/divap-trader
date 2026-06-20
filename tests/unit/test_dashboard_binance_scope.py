from src.data.repositories.trade_repo import (
    BINANCE_PNL_HISTORY_SQL,
    BINANCE_SCOPE_SQL,
    BINANCE_STATS_SQL,
    SELECT_BINANCE_TRADES_SQL,
    SELECT_OPEN_BINANCE_TRADES_SQL,
)
from src.profiles.loader import load_all_profiles, load_binance_profiles


def test_load_binance_profiles_excludes_otc() -> None:
    all_ids = {p.id for p in load_all_profiles()}
    binance_ids = {p.id for p in load_binance_profiles()}
    assert "otc" in all_ids
    assert "otc" not in binance_ids
    assert all(p.kind != "otc" for p in load_binance_profiles())


def test_binance_sql_excludes_iqoption_venue() -> None:
    for sql in (
        BINANCE_SCOPE_SQL,
        SELECT_OPEN_BINANCE_TRADES_SQL,
        SELECT_BINANCE_TRADES_SQL,
        BINANCE_PNL_HISTORY_SQL,
        BINANCE_STATS_SQL,
    ):
        assert "iqoption" in sql
        assert "<>" in sql or "!=" in sql
