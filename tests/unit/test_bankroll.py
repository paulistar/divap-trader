from unittest.mock import MagicMock, patch

from src.bankroll.service import build_profile_performance


def test_build_profile_performance_includes_all_profiles() -> None:
    mock_row = {
        "profile_id": "divap",
        "closed_count": 2,
        "open_count": 0,
        "wins": 1,
        "losses": 1,
        "total_pnl_usdt": 10,
        "month_pnl_usdt": 10,
        "week_pnl_usdt": 5,
    }
    with patch("src.data.repositories.trade_repo.TradeRepository") as repo_cls:
        repo_cls.return_value.profile_stats.return_value = [mock_row]
        perf = build_profile_performance()
    ids = {p["profile_id"] for p in perf}
    assert "divap" in ids
    assert "scalper" in ids
    assert "position" in ids
    assert "anti_divap" in ids
    divap = next(p for p in perf if p["profile_id"] == "divap")
    assert divap["closed_count"] == 2
    assert divap["win_rate_pct"] == "50.0"
