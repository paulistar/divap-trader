from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from src.core.constants import (
    FIBO_TARGETS,
    MIN_CONFLUENCES_FOR_ALERT,
    MIN_CONFLUENCES_HIGH_CONFIDENCE,
    STOP_MARGIN_PCT,
)
from src.data.models.candle import Candle
from src.detection.divergence import DivergenceResult, detect_divergence
from src.detection.fibonacci_zone import check_fibonacci_zone
from src.detection.reversal_pattern import check_reversal_pattern
from src.detection.volume_confirm import check_volume_confirmation
from src.indicators.fibonacci import calculate_extension_levels, find_swing_points
from src.indicators.rsi import compute_rsi_series
from src.indicators.volume import compute_volume_ma, volume_ratio

Confidence = Literal["medium", "high"]
Direction = Literal["buy", "sell"]

BULLISH_PATTERNS = frozenset({"hammer", "bullish_engulfing", "harami"})
BEARISH_PATTERNS = frozenset({"shooting_star", "bearish_engulfing", "harami"})


@dataclass(frozen=True, slots=True)
class DIVAPCriteria:
    divergence: bool
    volume: bool
    fibonacci: bool
    pattern: bool

    @property
    def count(self) -> int:
        return sum([self.divergence, self.volume, self.fibonacci, self.pattern])

    def to_dict(self) -> dict[str, bool]:
        return {
            "divergence": self.divergence,
            "volume": self.volume,
            "fibonacci": self.fibonacci,
            "pattern": self.pattern,
        }


@dataclass(frozen=True, slots=True)
class DIVAPSignal:
    symbol: str
    timeframe: str
    direction: Direction
    confidence: Confidence
    criteria: DIVAPCriteria
    entry_price: Decimal
    stop_loss: Decimal
    targets: tuple[Decimal, ...]
    current_price: Decimal
    rsi_value: float
    volume_ratio: float
    divergence_type: str
    pattern_detected: str | None
    fibo_level: Decimal | None
    timestamp: datetime


def count_confluences(criteria: DIVAPCriteria) -> int:
    return criteria.count


def resolve_confidence(criteria: DIVAPCriteria) -> Confidence | None:
    if not criteria.divergence:
        return None
    if criteria.count < MIN_CONFLUENCES_FOR_ALERT:
        return None
    if criteria.count >= MIN_CONFLUENCES_HIGH_CONFIDENCE:
        return "high"
    return "medium"


def direction_from_divergence(divergence: DivergenceResult) -> Direction:
    return "buy" if divergence.divergence_type == "bullish" else "sell"


def pattern_aligns_with_direction(pattern: str | None, direction: Direction) -> bool:
    if pattern is None:
        return False
    if direction == "buy":
        return pattern in BULLISH_PATTERNS
    return pattern in BEARISH_PATTERNS


def calculate_stop_loss(
    direction: Direction,
    candles: list[Candle],
    symbol: str,
) -> Decimal:
    margin = STOP_MARGIN_PCT.get(symbol, STOP_MARGIN_PCT["default"])
    window = candles[-5:] if len(candles) >= 5 else candles

    if direction == "buy":
        extreme = min(c.low for c in window)
        return extreme * (Decimal("1") - margin)

    extreme = max(c.high for c in window)
    return extreme * (Decimal("1") + margin)


def calculate_targets(
    direction: Direction,
    candles: list[Candle],
    entry_price: Decimal,
) -> tuple[Decimal, ...]:
    swings = find_swing_points(candles)
    if swings is None:
        return ()

    swing_low, swing_high = swings
    ext_direction = "up" if direction == "buy" else "down"
    levels = calculate_extension_levels(swing_low, swing_high, ext_direction)

    if direction == "buy":
        prices = [levels[r] for r in FIBO_TARGETS if levels[r] > entry_price]
        return tuple(sorted(prices))

    prices = [levels[r] for r in FIBO_TARGETS if levels[r] < entry_price]
    return tuple(sorted(prices, reverse=True))


class DIVAPScanner:
    def scan(
        self,
        symbol: str,
        timeframe: str,
        candles: list[Candle],
    ) -> DIVAPSignal | None:
        if len(candles) < 25:
            return None

        rsi_series = compute_rsi_series(candles)
        rsi_current = rsi_series[-1]
        if rsi_current is None:
            return None

        divergence = detect_divergence(candles, rsi_series)
        volume_ok = check_volume_confirmation(candles)
        fibo_hit = check_fibonacci_zone(candles)
        pattern = check_reversal_pattern(candles)

        criteria = DIVAPCriteria(
            divergence=divergence is not None,
            volume=volume_ok,
            fibonacci=fibo_hit is not None,
            pattern=pattern is not None,
        )

        confidence = resolve_confidence(criteria)
        if confidence is None or divergence is None:
            return None

        direction = direction_from_divergence(divergence)

        # Padrão deve alinhar com direção quando presente
        if criteria.pattern and not pattern_aligns_with_direction(pattern, direction):
            return None

        current = candles[-1]
        entry = current.close
        stop = calculate_stop_loss(direction, candles, symbol)
        targets = calculate_targets(direction, candles, entry)

        average = compute_volume_ma(candles[:-1])
        vol_ratio = volume_ratio(current.volume, average) if average else 0.0

        fibo_level = fibo_hit[0] if fibo_hit else None

        return DIVAPSignal(
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            confidence=confidence,
            criteria=criteria,
            entry_price=entry,
            stop_loss=stop,
            targets=targets,
            current_price=entry,
            rsi_value=rsi_current,
            volume_ratio=vol_ratio,
            divergence_type=divergence.divergence_type,
            pattern_detected=pattern,
            fibo_level=fibo_level,
            timestamp=current.timestamp,
        )
