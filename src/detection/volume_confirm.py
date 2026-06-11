from src.data.models.candle import Candle
from src.indicators.volume import is_volume_above_average


def check_volume_confirmation(candles: list[Candle]) -> bool:
    """V — volume de reversão acima da média de 20 períodos."""
    return is_volume_above_average(candles)
