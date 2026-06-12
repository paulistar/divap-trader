from decimal import Decimal

# Ativos monitorados no MVP (fallback quando perfil não define symbols)
DEFAULT_SYMBOLS: tuple[str, ...] = (
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "ADAUSDT",
)

# Top 20 liquidez crypto (Binance spot USDT) — Perfil DIVAP
CRYPTO_TOP_20_SYMBOLS: tuple[str, ...] = (
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "DOGEUSDT",
    "TRXUSDT",
    "AVAXUSDT",
    "LINKUSDT",
    "DOTUSDT",
    "POLUSDT",
    "SHIBUSDT",
    "LTCUSDT",
    "BCHUSDT",
    "UNIUSDT",
    "ATOMUSDT",
    "XLMUSDT",
    "NEARUSDT",
    "ICPUSDT",
)

# Majors para scalper e position (foco de liquidez)
CRYPTO_MAJOR_SYMBOLS: tuple[str, ...] = (
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
)

# Timeframes de scan
DEFAULT_TIMEFRAMES: tuple[str, ...] = ("15m", "1h", "4h", "1d")

# Prioridade operacional (maior assertividade)
PRIORITY_TIMEFRAMES: tuple[str, ...] = ("1h", "4h", "1d")

# Fibonacci — extensão (alvos)
FIBO_TARGETS: tuple[Decimal, ...] = (
    Decimal("0.618"),
    Decimal("1.0"),
    Decimal("1.618"),
    Decimal("2.0"),
    Decimal("2.618"),
)

FIBO_PRIORITY_TARGETS: tuple[Decimal, ...] = (
    Decimal("1.0"),
    Decimal("1.618"),
)

# RSI
RSI_PERIOD: int = 14
DIVERGENCE_LOOKBACK: int = 20

# Volume
VOLUME_MA_PERIOD: int = 20

# Proximidade ao nível Fibonacci (0.3%)
FIBO_TOLERANCE_PCT: Decimal = Decimal("0.003")

# Stop margin para violinada (por símbolo)
STOP_MARGIN_PCT: dict[str, Decimal] = {
    "BTCUSDT": Decimal("0.015"),
    "ETHUSDT": Decimal("0.02"),
    "default": Decimal("0.02"),
}

# Confluências mínimas para alerta
MIN_CONFLUENCES_FOR_ALERT: int = 3
MIN_CONFLUENCES_HIGH_CONFIDENCE: int = 4

# % da banca por timeframe (skill risk-management)
BANK_ALLOCATION_PCT: dict[str, tuple[int, int]] = {
    "15m": (1, 2),
    "1h": (4, 6),
    "4h": (8, 12),
    "1d": (10, 15),
}
