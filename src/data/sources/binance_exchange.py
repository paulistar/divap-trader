import ccxt

from src.core.config import settings


def build_binance_exchange() -> ccxt.binance:
    exchange = ccxt.binance(
        {
            "apiKey": settings.binance_api_key or None,
            "secret": settings.binance_api_secret or None,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        }
    )
    if settings.binance_use_testnet or settings.trading_mode == "testnet":
        exchange.set_sandbox_mode(True)
    return exchange
