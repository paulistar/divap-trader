from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class OtcMartingale:
    enabled: bool
    max_protections: int
    multiplier: Decimal


@dataclass(frozen=True, slots=True)
class OtcTelegramConfig:
    enabled: bool
    mode: str
    channel: str


@dataclass(frozen=True, slots=True)
class OtcProfileConfig:
    profile_id: str
    venue: str
    account_mode: str
    default_stake_usd: Decimal
    max_open_trades: int
    expiry_minutes: int
    dry_run: bool
    martingale: OtcMartingale
    assets: tuple[str, ...]
    asset_aliases: dict[str, str]
    telegram: OtcTelegramConfig
    signal_timezone: str = "America/Sao_Paulo"
    entry_max_lateness_seconds: int = 0


@dataclass(frozen=True, slots=True)
class OtcSignal:
    asset: str
    direction: str
    expiry_minutes: int
    entry_time: datetime | None = None
    raw_text: str = ""
    protection_level: int = 0
    max_auto_protections: int | None = None
    protection_schedule: tuple[time, ...] = ()


@dataclass(frozen=True, slots=True)
class OtcTradeResult:
    executed: bool
    reason: str
    trade_id: int | None = None
    order_id: str | None = None
    asset: str = ""
    direction: str = ""
    stake_usd: Decimal = Decimal("0")
    pnl_usd: Decimal | None = None
    dry_run: bool = False
    protection_level: int = 0


@dataclass(frozen=True, slots=True)
class OtcSettlementContext:
    """Ordem aberta aguardando resultado — usado entre open_binary e wait_settlement."""

    transport: str
    resolved_asset: str
    direction: str
    stake_usd: Decimal
    duration_minutes: int
    order_id: str | None = None
    mcp_asset_id: int | None = None
    legacy_order_id: object | None = None


@dataclass(frozen=True, slots=True)
class OtcSequenceResult:
    executed: bool
    reason: str
    legs: tuple[OtcTradeResult, ...]
    asset: str = ""
    direction: str = ""
    total_pnl_usd: Decimal | None = None
    dry_run: bool = False
