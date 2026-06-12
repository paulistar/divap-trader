from unittest.mock import MagicMock, patch

from src.alerts.scheduler import run_divap_scan


def test_run_divap_scan_imports_scanner() -> None:
    with patch("src.alerts.scheduler.BinanceSource") as src_cls:
        src_cls.return_value.fetch_ohlcv.return_value = []
        with patch("src.alerts.scheduler.DIVAPScanner") as scanner_cls:
            scanner_cls.return_value.scan.return_value = None
            result = run_divap_scan(
                symbols=("BTCUSDT",),
                timeframes=("1m",),
                use_llm=False,
                notify=False,
            )
    assert result["signals"] == 0
    scanner_cls.return_value.scan.assert_called_once()
