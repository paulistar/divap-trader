from __future__ import annotations

import re
from datetime import datetime

from src.otc.models import OtcSignal

_ASSET_RE = re.compile(
    r"(?:ativo|asset|par)\s*[:\-]?\s*(.+?)(?:\n|$)",
    re.IGNORECASE,
)
_EXPIRY_RE = re.compile(r"(?:expira(?:ç|c)ão|expiry|timeframe)\s*[:\-]?\s*(M?\d+)", re.IGNORECASE)
_DIRECTION_RE = re.compile(
    r"\b(COMPRA|VENDA|CALL|PUT|UP|DOWN)\b",
    re.IGNORECASE,
)
_ENTRY_TIME_RE = re.compile(
    r"(?:entrada|entry|hor[aá]rio)\s*[:\-]?\s*(\d{1,2}:\d{2})",
    re.IGNORECASE,
)
_MAX_PROTECTIONS_RE = re.compile(
    r"(?:fazer\s+at[eé]\s+|at[eé]\s+)?(\d+)\s+prote(?:ç|c)[õo]es",
    re.IGNORECASE,
)
_MANUAL_PROTECTION_LEVEL_RE = re.compile(
    r"(?:^|\n)\s*(?:executar\s+)?prote(?:ç|c)ão\s*(\d+)\s*(?:manual|$)",
    re.IGNORECASE,
)


def _normalize_direction(raw: str) -> str:
    value = raw.strip().upper()
    if value in ("COMPRA", "CALL", "UP"):
        return "buy"
    if value in ("VENDA", "PUT", "DOWN"):
        return "sell"
    return value.lower()


def _parse_expiry_minutes(raw: str) -> int:
    text = raw.strip().upper()
    if text.startswith("M"):
        return max(1, int(text[1:]))
    return max(1, int(text))


def parse_telegram_signal(text: str) -> OtcSignal | None:
    """Parse sinais estilo sala: ENTRADA CONFIRMADA + ativo + M1 + COMPRA/VENDA."""
    if not text or "ENTRADA" not in text.upper():
        return None

    asset_match = _ASSET_RE.search(text)
    direction_match = _DIRECTION_RE.search(text)
    if not asset_match or not direction_match:
        return None

    asset = asset_match.group(1).strip()
    direction = _normalize_direction(direction_match.group(1))

    expiry = 1
    expiry_match = _EXPIRY_RE.search(text)
    if expiry_match:
        expiry = _parse_expiry_minutes(expiry_match.group(1))

    entry_time: datetime | None = None
    time_match = _ENTRY_TIME_RE.search(text)
    if time_match:
        try:
            entry_time = datetime.strptime(time_match.group(1), "%H:%M")
        except ValueError:
            entry_time = None

    max_auto_protections: int | None = None
    max_match = _MAX_PROTECTIONS_RE.search(text)
    if max_match:
        max_auto_protections = int(max_match.group(1))

    protection_level = 0
    manual_level_match = _MANUAL_PROTECTION_LEVEL_RE.search(text)
    if manual_level_match:
        protection_level = int(manual_level_match.group(1))

    return OtcSignal(
        asset=asset,
        direction=direction,
        expiry_minutes=expiry,
        entry_time=entry_time,
        raw_text=text,
        protection_level=protection_level,
        max_auto_protections=max_auto_protections,
    )
