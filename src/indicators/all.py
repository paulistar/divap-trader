from dataclasses import dataclass

from src.data.models.candle import Candle
from src.detection.divergence import DivergenceResult, detect_divergence
from src.indicators.fibonacci import price_at_extension_target
from src.indicators.patterns import detect_reversal_pattern
from src.indicators.rsi import compute_rsi_series
from src.indicators.volume import compute_volume_ma, is_volume_above_average, volume_ratio


@dataclass(frozen=True, slots=True)
class IndicatorSnapshot:
    rsi_series: list[float | None]
    rsi_current: float | None
    volume_ma: float | None
    volume_ratio: float | None
    volume_above_average: bool
    fibo_level: tuple | None
    pattern: str | None
    divergence: DivergenceResult | None


def compute_all_indicators(candles: list[Candle]) -> IndicatorSnapshot:
    rsi_series = compute_rsi_series(candles)
    rsi_current = rsi_series[-1] if rsi_series else None

    vol_ma = compute_volume_ma(candles[:-1]) if len(candles) > 1 else None
    vol_ma_float = float(vol_ma) if vol_ma is not None else None
    ratio = volume_ratio(candles[-1].volume, vol_ma) if vol_ma else None

    return IndicatorSnapshot(
        rsi_series=rsi_series,
        rsi_current=rsi_current,
        volume_ma=vol_ma_float,
        volume_ratio=ratio,
        volume_above_average=is_volume_above_average(candles),
        fibo_level=price_at_extension_target(candles),
        pattern=detect_reversal_pattern(candles),
        divergence=detect_divergence(candles, rsi_series),
    )
