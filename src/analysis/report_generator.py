import json
from decimal import Decimal
from pathlib import Path

from src.core.constants import BANK_ALLOCATION_PCT
from src.detection.divap_scanner import DIVAPSignal

PROMPT_PATH = Path(__file__).parent / "prompts" / "divap_analysis.txt"


def _decimal_default(obj: object) -> str:
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def signal_to_payload(signal: DIVAPSignal) -> dict:
    bank_range = BANK_ALLOCATION_PCT.get(signal.timeframe, (4, 6))
    return {
        "symbol": signal.symbol,
        "timeframe": signal.timeframe,
        "direction": signal.direction,
        "confidence": signal.confidence,
        "criteria": signal.criteria.to_dict(),
        "confluence_count": signal.criteria.count,
        "entry_price": signal.entry_price,
        "stop_loss": signal.stop_loss,
        "targets": list(signal.targets),
        "current_price": signal.current_price,
        "rsi_value": signal.rsi_value,
        "volume_ratio": signal.volume_ratio,
        "divergence_type": signal.divergence_type,
        "pattern_detected": signal.pattern_detected,
        "fibo_level": signal.fibo_level,
        "timestamp": signal.timestamp.isoformat(),
        "suggested_bank_allocation_pct": {
            "min": bank_range[0],
            "max": bank_range[1],
        },
    }


def build_user_message(signal: DIVAPSignal) -> str:
    payload = signal_to_payload(signal)
    return (
        "Analise o setup DIVAP abaixo. Use APENAS os números fornecidos.\n\n"
        f"```json\n{json.dumps(payload, indent=2, default=_decimal_default)}\n```"
    )


def load_system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")
